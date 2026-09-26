"""Tests for scripts/codex_quota.py against a fake `codex app-server` on PATH (no network, no real account).

The fake speaks the app-server stdio protocol as openai/codex defines it at rust-v0.155.1 and rust-v0.157.1
(codex-rs/app-server-protocol: no "jsonrpc" field, `initialize` then the `initialized` notification, then
`account/rateLimits/read`; error answers {"id", "error": {"code", "message"}}), records what it received, and can
stay silent, exit early, answer with an error, interleave notifications and a server request, ignore SIGTERM and
leave a child that ignores SIGTERM.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "codex_quota.py"
_spec = importlib.util.spec_from_file_location("codex_quota", SCRIPT)
codex_quota = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codex_quota)

RESETS_AT = 1790990880  # 2026-10-03T01:28:00Z

FAKE_CODEX = """#!{python}
import json, os, signal, subprocess, sys, time
config = json.load(open(os.environ["FAKE_QUOTA_CONFIG"]))
if sys.argv[1:] != ["-c", 'sandbox_mode="read-only"', "app-server"]:  # the probe asks for no writable roots
    sys.exit(64)
state = {{"pid": os.getpid(), "cwd": os.getcwd(), "rust_log": sorted(k for k in os.environ if k.startswith("RUST_LOG")),
         "received": []}}
def save():
    if config.get("record"):
        with open(config["record"] + ".tmp", "w") as out:
            json.dump(state, out)
        os.replace(config["record"] + ".tmp", config["record"])
def send(obj):
    sys.stdout.write(json.dumps(obj) + "\\n")
    sys.stdout.flush()
if config.get("ignore_term"):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
if config.get("stubborn_child"):
    child = subprocess.Popen([sys.executable, "-c", "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                              "time.sleep(120)"])
    state["child_pid"] = child.pid
save()
if "exit_code" in config:
    sys.exit(config["exit_code"])
initialized = False
for line in sys.stdin:
    msg = json.loads(line)
    state["received"].append(msg)
    save()
    method = msg.get("method")
    if method is not None and method == config.get("hang"):
        time.sleep(600)  # never answers and never reads its input again
    if method == "initialize":
        if config.get("noise"):
            sys.stdout.write("a log line that is not JSON\\n")
            send({{"method": "account/updated", "params": {{}}}})
            send([1, 2])
        send({{"id": msg["id"], "result": {{"userAgent": "fixture/0", "codexHome": "/nonexistent",
                                           "platformFamily": "unix", "platformOs": "linux"}}}})
    elif method == "initialized":
        initialized = True
    elif method == "account/rateLimits/read":
        if not initialized:
            send({{"id": msg["id"], "error": {{"code": -32600, "message": "Not initialized"}}}})
            continue
        if config.get("noise"):
            send({{"id": "server-1", "method": "item/tool/requestUserInput", "params": {{}}}})
            send({{"id": 99, "result": {{"rateLimits": {{"primary": {{"usedPercent": 1}}}}}}}})
            send({{"method": "account/rateLimits/updated", "params": {{"rateLimits": {{}}}}}})
        if "error" in config:
            send({{"id": msg["id"], "error": config["error"]}})
        else:
            send({{"id": msg["id"], "result": config["result"]}})
"""


def window(used, minutes=10080, resets=RESETS_AT):
    return {"usedPercent": used, "windowDurationMins": minutes, "resetsAt": resets}


def snapshot(used=63, *, secondary=None, reached=None, limit_id="codex", slug=None, plan="prolite"):
    return {"limitId": limit_id, "limitName": None, "normalModelSlug": slug,
            "primary": window(used) if used is not None else None, "secondary": secondary,
            "credits": {"hasCredits": False, "unlimited": False, "balance": None}, "individualLimit": None,
            "spendControlReached": None, "planType": plan, "rateLimitReachedType": reached}


def answer(used=63, *, allowed=True, **snapshot_args):
    main = snapshot(used, **snapshot_args)
    return {"ordinaryUsageAllowed": allowed, "rateLimits": main,
            "rateLimitsByLimitId": {"codex": main, "codex_other": snapshot(12, limit_id="codex_other",
                                                                           slug="gpt-6-other")},
            "rateLimitResetCredits": {"availableCount": 2, "credits": None},
            "accountId": "acct-fixture-never-printed", "rateLimitUpsell": {"title": "fixture banner"}}


def process_alive(pid: int) -> bool:
    """True while pid runs; a zombie (exited, not yet reaped by its new parent) counts as gone."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(state) and not state.startswith("Z")


class QuotaProbeCase(unittest.TestCase):
    def setUp(self):
        self.bin = Path(tempfile.mkdtemp(prefix="codex-quota-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.bin, ignore_errors=True)
        fake = self.bin / "codex"
        fake.write_text(FAKE_CODEX.format(python=sys.executable), encoding="utf-8")
        fake.chmod(0o755)
        self.config_path = self.bin / "config.json"
        self.record_path = self.bin / "record.json"
        self.env = {**os.environ, "PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
                    "FAKE_QUOTA_CONFIG": str(self.config_path)}

    def fake(self, **config):
        config.setdefault("record", str(self.record_path))
        self.config_path.write_text(json.dumps(config), encoding="utf-8")

    def probe(self, *args, env=None, timeout=60):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], capture_output=True, text=True,
                              env=env or self.env, timeout=timeout, check=False)

    def probe_json(self, *args, **kwargs):
        done = self.probe("--json", *args, **kwargs)
        lines = done.stdout.splitlines()
        self.assertEqual(len(lines), 1, done.stdout + done.stderr)  # --json: one object and nothing else
        self.assertEqual(done.stderr, "")
        return done.returncode, json.loads(lines[0])

    def record(self):
        return json.loads(self.record_path.read_text(encoding="utf-8"))


class SnapshotTests(QuotaProbeCase):
    def test_snapshot_fields_and_protocol(self):
        self.fake(result=answer())
        self.env["RUST_LOG"] = "trace"
        code, out = self.probe_json()
        self.assertEqual(code, 0)
        self.assertEqual((out["used_percent"], out["window_minutes"], out["resets_at_utc"], out["plan_type"]),
                         (63, 10080, "2026-10-03T01:28Z", "prolite"))
        self.assertIsNone(out["secondary"])
        self.assertEqual((out["limit_id"], out["rate_limit_reached_type"], out["ordinary_usage_allowed"],
                          out["reset_credits_available"]), ("codex", None, True, 2))
        self.assertEqual(sorted(out["buckets"]), ["codex", "codex_other"])
        self.assertEqual(out["buckets"]["codex_other"]["normal_model_slug"], "gpt-6-other")
        self.assertEqual(out["buckets"]["codex_other"]["primary"]["used_percent"], 12)
        self.assertNotIn("gate", out)
        self.assertRegex(out["checked_at_utc"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        text = json.dumps(out)
        self.assertNotIn("acct-fixture-never-printed", text)
        self.assertNotIn("fixture banner", text)
        record = self.record()
        # initialize with clientInfo, then the initialized notification, then the read in its background-poll form.
        self.assertEqual([m.get("method") for m in record["received"]],
                         ["initialize", "initialized", "account/rateLimits/read"])
        initialize, initialized, read = record["received"]
        self.assertEqual((initialize["id"], sorted(initialize["params"])), (1, ["clientInfo"]))
        self.assertTrue(initialize["params"]["clientInfo"]["name"] and initialize["params"]["clientInfo"]["version"])
        self.assertEqual(initialized, {"method": "initialized"})
        self.assertEqual(read, {"id": 2, "method": "account/rateLimits/read",
                                "params": {"excludeResetCreditDetails": True}})
        self.assertFalse(any("jsonrpc" in m for m in record["received"]))
        self.assertEqual(record["rust_log"], [])
        cwd = Path(record["cwd"])
        self.assertFalse(cwd.exists(), "the probe's empty working directory was left behind")
        self.assertFalse(str(cwd).startswith(str(ROOT)))
        self.assertFalse(process_alive(record["pid"]))

    def test_interleaved_messages_and_a_server_request(self):
        self.fake(result=answer(40), noise=True)
        code, out = self.probe_json()
        self.assertEqual((code, out["used_percent"]), (0, 40))  # not the unrelated answer to id 99
        replies = [m for m in self.record()["received"] if m.get("id") == "server-1"]
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0]["error"]["code"], -32601)

    def test_text_output(self):
        self.fake(result=answer(63, secondary=window(20, 300)))
        done = self.probe("--gate", "95")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), "codex quota: 63% of the 10080-minute window used, resets "
                         "2026-10-03T01:28Z (plan prolite); secondary 20% of 300 min, resets 2026-10-03T01:28Z; "
                         "gate 95%: not reached")

    def test_summary_tolerates_missing_and_mistyped_fields(self):
        out = codex_quota.summarize({"rateLimits": {"primary": {"usedPercent": True, "resetsAt": 10 ** 20},
                                                    "planType": 5}})
        self.assertEqual((out["used_percent"], out["resets_at_utc"], out["plan_type"], out["buckets"]),
                         (None, None, None, None))
        with self.assertRaises(codex_quota.ProbeError):
            codex_quota.summarize({"rateLimits": None})


class GateTests(QuotaProbeCase):
    def test_gate_outcomes(self):
        cases = [
            ("below", answer(63), "95", 0, False, []),
            ("equal", answer(63), "63", 3, True, ["primary window 63% used >= 63%"]),
            ("above", answer(96), "95", 3, True, ["primary window 96% used >= 95%"]),
            ("reached type", answer(10, reached="workspace_member_usage_limit_reached"), "95", 3, True,
             ["rateLimitReachedType workspace_member_usage_limit_reached"]),
            ("usage not allowed", answer(10, allowed=False), "95", 3, True, ["ordinaryUsageAllowed false"]),
            ("secondary", answer(10, secondary=window(97, 300)), "95", 3, True, ["secondary window 97% used >= 95%"]),
            ("fractional", answer(95), "95.5", 0, False, []),
        ]
        for name, result, percent, want_code, want_reached, want_reasons in cases:
            with self.subTest(name):
                self.fake(result=result)
                code, out = self.probe_json("--gate", percent)
                self.assertEqual(code, want_code)
                self.assertEqual((out["gate"]["percent"], out["gate"]["reached"]), (float(percent), want_reached))
                self.assertEqual(len(out["gate"]["reasons"]), len(want_reasons))
                for reason, prefix in zip(out["gate"]["reasons"], want_reasons):
                    self.assertTrue(reason.startswith(prefix), reason)
        self.assertIn("resets 2026-10-03T01:28Z", codex_quota.judge(codex_quota.summarize(answer(96)), 95)[1][0])

    def test_a_snapshot_with_nothing_to_judge(self):
        self.fake(result=answer(None, allowed=None))
        code, out = self.probe_json()
        self.assertEqual((code, out["used_percent"]), (0, None))  # a valid read without the gate
        code, out = self.probe_json("--gate", "95")
        self.assertEqual((code, out["gate"]["reached"], out["error"]["stage"]), (2, None, "gate"))

    def test_bad_gate_values_are_usage_errors(self):
        self.fake(result=answer())
        for value in ("0", "101", "nan", "abc"):
            with self.subTest(value):
                done = self.probe("--json", "--gate", value)
                self.assertEqual(done.returncode, 2)
                self.assertIn("--gate", done.stderr)
                self.assertFalse(self.record_path.exists())  # refused before codex started


class FailureTests(QuotaProbeCase):
    def test_error_answers(self):
        for error in ({"code": -32600, "message": "codex account authentication required to read rate limits"},
                      {"code": -32603, "message": "failed to fetch codex rate limits: no snapshots returned",
                       "data": {"detail": "fixture"}}):
            with self.subTest(error["code"]):
                self.fake(error=error)
                code, out = self.probe_json("--gate", "95")
                self.assertEqual(code, 2)
                self.assertEqual(out["error"], {"stage": "account/rateLimits/read", "code": error["code"],
                                                "message": error["message"]})
                self.assertNotIn("used_percent", out)
                self.assertFalse(process_alive(self.record()["pid"]))
        self.fake(error={"code": -32600, "message": "x" * 5000})
        self.assertEqual(len(self.probe_json()[1]["error"]["message"]), codex_quota.MESSAGE_CHARS)

    def test_a_server_that_never_answers_is_stopped_with_its_process_group(self):
        # It ignores SIGTERM and EOF and leaves a child that ignores SIGTERM too: only the group KILL ends both.
        self.fake(hang="initialize", ignore_term=True, stubborn_child=True)
        began = time.monotonic()
        code, out = self.probe_json("--timeout", "1", "--gate", "95")
        elapsed = time.monotonic() - began
        self.assertEqual(code, 2)
        self.assertEqual(out["error"]["stage"], "initialize")
        self.assertIn("timeout", out["error"]["message"])
        self.assertLess(elapsed, 20)
        record = self.record()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and (process_alive(record["pid"]) or process_alive(record["child_pid"])):
            time.sleep(0.1)
        self.assertFalse(process_alive(record["pid"]), "the silent server survived the probe")
        self.assertFalse(process_alive(record["child_pid"]), "a child that ignored SIGTERM survived the probe")

    def test_a_server_silent_on_the_read_times_out(self):
        self.fake(hang="account/rateLimits/read")
        code, out = self.probe_json("--timeout", "1")
        self.assertEqual((code, out["error"]["stage"]), (2, "account/rateLimits/read"))
        self.assertIn("timeout", out["error"]["message"])
        self.assertFalse(process_alive(self.record()["pid"]))

    def test_a_server_that_exits_early(self):
        self.fake(exit_code=7)
        began = time.monotonic()
        code, out = self.probe_json("--timeout", "30")
        self.assertEqual((code, out["error"]["stage"]), (2, "initialize"))
        self.assertRegex(out["error"]["message"], "exited with code 7|closed its (input|output)")
        self.assertLess(time.monotonic() - began, 15)  # EOF ends the wait, not the deadline

    def test_codex_missing_from_path(self):
        empty = Path(tempfile.mkdtemp(prefix="codex-quota-nopath-"))
        self.addCleanup(shutil.rmtree, empty, ignore_errors=True)
        code, out = self.probe_json(env={**self.env, "PATH": str(empty)})
        self.assertEqual((code, out["error"]["stage"], out["error"]["message"]), (2, "start", "codex is not on PATH"))
        done = self.probe(env={**self.env, "PATH": str(empty)})
        self.assertEqual((done.returncode, done.stdout), (2, ""))
        self.assertIn("codex is not on PATH", done.stderr)


if __name__ == "__main__":
    unittest.main()
