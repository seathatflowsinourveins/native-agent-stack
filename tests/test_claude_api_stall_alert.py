"""Checks for the Claude session API-stall rule (observability/backends/templates/ns2604-claude-api-stall.yaml.example).

Text checks always run. A YAML structural check runs when PyYAML is importable. The replay check starts a scratch
Loki at the pinned version (observability/backends/pins.json) when that binary is installed, pushes synthetic Claude
Code events with the structured metadata the Collector keeps, and evaluates the rule's own expression: a session
whose last request failed and a session with only errors match, a recovered session and a clean one do not. It skips,
rather than fails, when the binary is absent, matching tests/test_observability_backends_alerts.py.
"""
from __future__ import annotations

import json
import re
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULE = ROOT / "observability/backends/templates/ns2604-claude-api-stall.yaml.example"
PINNED_LOKI = {c["id"]: c["version"] for c in json.loads((ROOT / "observability/backends/pins.json").read_text())["components"]}["loki"]

try:
    import yaml
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


def seconds(value: str) -> int:
    match = re.fullmatch(r"(\d+)([smh])", value)
    if not match:
        raise AssertionError(f"not a duration: {value!r}")
    return int(match.group(1)) * {"s": 1, "m": 60, "h": 3600}[match.group(2)]


def rule_expression(text: str) -> str:
    """The folded `expr: >-` block of refId A, joined as YAML folds it (single spaces between lines)."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "expr: >-")
    indent = len(lines[start + 1]) - len(lines[start + 1].lstrip())
    body = []
    for line in lines[start + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) < indent:
            break
        body.append(line.strip())
    return " ".join(part for part in body if part)


def loki_binary() -> Path | None:
    layout = Path.home() / f".local/share/codex-ecosystem/tools/ecosystem-loki-{PINNED_LOKI}/loki"
    for candidate in (layout, shutil.which("loki")):
        if candidate and Path(candidate).is_file():
            out = subprocess.run([str(candidate), "--version"], capture_output=True, text=True).stdout
            if f"version {PINNED_LOKI} " in out:
                return Path(candidate)
    return None


class RuleTextTests(unittest.TestCase):
    def setUp(self):
        self.text = RULE.read_text(encoding="utf-8")

    def test_intervals_and_pending_period_are_multiples_of_ten_seconds(self):
        values = re.findall(r"^\s*(?:interval|for):\s*(\S+)\s*$", self.text, re.M)
        self.assertEqual(len(values), 2, values)
        for value in values:
            self.assertEqual(seconds(value) % 10, 0, value)
        self.assertEqual(re.search(r"^\s*for:\s*(\S+)", self.text, re.M).group(1), "10m")

    def test_the_query_reads_loki_and_compares_the_two_native_events_by_sequence(self):
        expr = rule_expression(self.text)
        self.assertIn("datasourceUid: ns2604-loki", self.text)
        self.assertEqual(expr.count('event_name="api_error"'), 2)
        self.assertEqual(expr.count('event_name="api_request"'), 2)
        self.assertEqual(expr.count("unwrap event_sequence"), 4)
        self.assertIn("> on (session_id)", expr)
        self.assertIn("unless on (session_id)", expr)
        self.assertEqual(set(re.findall(r"\[(\w+)\]", expr)), {"2h"})

    def test_no_notification_route_or_external_receiver_is_added(self):
        body = "\n".join(line for line in self.text.splitlines() if not line.lstrip().startswith("#"))
        for word in ("notification_settings", "contactPoints", "url:"):
            self.assertNotIn(word, body)

    @unittest.skipUnless(HAVE_YAML, "PyYAML is not installed")
    def test_structure_matches_the_hosts_provisioning_format(self):
        doc = yaml.safe_load(self.text)
        self.assertEqual(doc["apiVersion"], 1)
        (group,) = doc["groups"]
        self.assertEqual((group["orgId"], group["folder"], group["interval"]), (1, "Ecosystem", "1m"))
        (rule,) = group["rules"]
        self.assertEqual(rule["condition"], "B")
        refs = {item["refId"]: item for item in rule["data"]}
        self.assertEqual(set(refs), {"A", "B"})
        self.assertEqual(refs["A"]["datasourceUid"], "ns2604-loki")
        self.assertEqual(refs["A"]["model"]["expr"], rule_expression(self.text))
        evaluator = refs["B"]["model"]["conditions"][0]["evaluator"]
        self.assertEqual((refs["B"]["model"]["expression"], evaluator["type"], evaluator["params"]), ("A", "gt", [0]))
        self.assertEqual((rule["noDataState"], rule["execErrState"]), ("OK", "Error"))
        self.assertIn("{{ $labels.session_id }}", rule["annotations"]["summary"])


@unittest.skipUnless(loki_binary(), f"Loki {PINNED_LOKI} is not installed")
class RuleReplayTests(unittest.TestCase):
    """The rule's expression on a scratch Loki with four synthetic sessions."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="claude-stall-loki-"))
        self.http, self.grpc = self.port(), self.port()
        config = self.dir / "loki.yml"
        config.write_text(json.dumps({
            "auth_enabled": False,
            "server": {"http_listen_address": "127.0.0.1", "http_listen_port": self.http,
                       "grpc_listen_address": "127.0.0.1", "grpc_listen_port": self.grpc, "log_level": "warn"},
            "common": {"instance_addr": "127.0.0.1", "path_prefix": str(self.dir),
                       "storage": {"filesystem": {"chunks_directory": str(self.dir / "chunks"),
                                                  "rules_directory": str(self.dir / "rules")}},
                       "replication_factor": 1, "ring": {"kvstore": {"store": "inmemory"}}},
            "schema_config": {"configs": [{"from": "2024-01-01", "store": "tsdb", "object_store": "filesystem",
                                           "schema": "v13", "index": {"prefix": "index_", "period": "24h"}}]},
            "limits_config": {"allow_structured_metadata": True, "reject_old_samples": False},
            "analytics": {"reporting_enabled": False},
        }))
        self.process = subprocess.Popen([str(loki_binary()), f"-config.file={config}"], stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                if urllib.request.urlopen(f"http://127.0.0.1:{self.http}/ready", timeout=2).status == 200:
                    return
            except OSError:
                time.sleep(0.5)
        self.fail("scratch Loki did not become ready")

    def tearDown(self):
        self.process.terminate()
        self.process.wait(timeout=30)
        shutil.rmtree(self.dir, ignore_errors=True)

    @staticmethod
    def port() -> int:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def push(self, events):
        now = time.time()
        values = [[str(int((now - minutes_ago * 60) * 1e9)), json.dumps({"event": name}),
                   {"event_name": name, "session_id": session, "event_sequence": str(sequence)}]
                  for session, name, sequence, minutes_ago in events]
        body = json.dumps({"streams": [{"stream": {"service_name": "claude-code"}, "values": values}]}).encode()
        request = urllib.request.Request(f"http://127.0.0.1:{self.http}/loki/api/v1/push", data=body,
                                         headers={"Content-Type": "application/json"})
        self.assertEqual(urllib.request.urlopen(request, timeout=10).status, 204)

    def query(self, expr):
        q = urllib.parse.urlencode({"query": expr, "time": str(int(time.time() * 1e9))})
        return json.load(urllib.request.urlopen(f"http://127.0.0.1:{self.http}/loki/api/v1/query?{q}", timeout=30))

    def test_only_sessions_whose_last_request_failed_match(self):
        self.push([
            ("stalled", "api_request", 1, 30), ("stalled", "api_error", 2, 20),
            ("recovered", "api_request", 1, 40), ("recovered", "api_error", 2, 30), ("recovered", "api_request", 3, 25),
            ("errors-only", "api_error", 1, 15),
            ("clean", "api_request", 1, 10), ("clean", "api_request", 2, 5),
        ])
        expr = rule_expression(RULE.read_text(encoding="utf-8"))
        deadline = time.time() + 30
        while True:
            result = self.query(expr)["data"]["result"]
            matched = {item["metric"]["session_id"]: float(item["value"][1]) for item in result}
            if matched or time.time() > deadline:
                break
            time.sleep(1)
        self.assertEqual(matched, {"stalled": 2.0, "errors-only": 1.0})


if __name__ == "__main__":
    unittest.main()
