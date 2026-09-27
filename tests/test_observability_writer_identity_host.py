"""Host recipe of the writer-identity change (evidence/artifacts/telemetry-writer-identity-20260926/host).

prove.py runs against an in-process fake of the Prometheus and Loki query APIs that answers from a small event model
(a test double, not PromQL or LogQL). apply.sh and rollback.sh run in a sandbox home with fake service managers,
collector, promtool, codex and curl; nothing here reaches a real service. These are local checks of the scripts'
decisions on synthetic data, not host acceptance.
"""
from __future__ import annotations

import http.server
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "evidence/artifacts/telemetry-writer-identity-20260926/host"
COLLECTOR = ROOT / "observability/collector/collector.yaml"
LAUNCHER = ROOT / "observability/collector/codex-identity-launcher.sh.example"
SCRAPE = ROOT / "observability/backends/templates/ecosystem-prometheus.yml.example"

try:
    import yaml
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

CLAUDE = "ecosystem_claude_code_token_usage_tokens_total"
CODEX_SUM = "ecosystem_codex_turn_token_usage_sum"
CODEX_COUNT = "ecosystem_codex_turn_token_usage_count"
CLAUDE_FIELDS = {"input_tokens": "input", "output_tokens": "output", "cache_read_tokens": "cacheRead",
                 "cache_creation_tokens": "cacheCreation"}
CODEX_FIELDS = {"input_token_count": "input", "output_token_count": "output", "cached_token_count": "cached_input",
                "reasoning_token_count": "reasoning_output"}
RULES = ("EcosystemTokenCounterResets", "EcosystemDeltaConversionDropped", "EcosystemUnscopedTokenWriters")
FEATURES = "created-timestamp-zero-ingestion,promql-extended-range-selectors"
BUCKET_DROP = "ecosystem_codex_.+_bucket;"


def group_labels(query):
    match = re.match(r"\s*\w+\s+by\s*\(([^)]*)\)", query)
    return [label.strip() for label in match.group(1).split(",")] if match else []


def range_seconds(query):
    match = re.search(r"\[(\d+)s\]", query)
    return float(match.group(1)) if match else 0.0


def misplaced_modifier(query):
    """Prometheus 3.15 parses `x[5m] anchored`; `x[5m anchored]` is a parse error (checked on the pinned binary)."""
    return re.search(r"\[\d+[smhd] +(anchored|smoothed)\]", query) is not None


def grouped(rows, labels):
    """rows: [(label dict, value)] -> the sum by `labels` as Prometheus/Loki vector entries."""
    out = {}
    for metric, value in rows:
        key = tuple(metric.get(label, "") for label in labels)
        out[key] = out.get(key, 0.0) + value
    return [({label: part for label, part in zip(labels, key) if part}, value) for key, value in out.items()]


class Matrix(list):
    """A range-vector answer: rows of (label dict, [(time, value)])."""


class Telemetry:
    """An event model answered through the query shapes prove.py sends.

    Claude writers: events (time, {type: tokens}, query_source); Prometheus sees an event `lag` seconds after it
    happened, scaled by `scale`. Codex processes: a start time and token events (time, {loki field: tokens});
    `present=False` means none of its tokens reached Prometheus. The collector-health `up` series has a sample
    every 15 s unless `up_times` lists its sample times."""

    def __init__(self, now):
        self.now = now
        self.claude = {}
        self.codex = {}
        self.collector_up = 1.0
        self.up_times = None
        self.dropped = {}
        self.accepted = 5000.0
        self.unscoped = {}
        self.resets_scoped = [0, 0]
        self.resets_unscoped = []
        self.features = FEATURES
        self.rules = list(RULES)
        self.config_yaml = "scrape_configs:\n- job_name: collector-native\n  metric_relabel_configs:\n  - regex: " \
                           + BUCKET_DROP + "\n    action: drop\n"
        self.unknown = []

    def add_claude(self, key, events, lag=25.0, scale=1.0, instance=None):
        self.claude[key] = {"instance": instance or key, "events": events, "lag": lag, "scale": scale}

    def add_codex(self, instance, start, events, lag=45.0, scale=1.0, present=True, turns_in_loki=True):
        self.codex[instance] = {"start": start, "events": events, "lag": lag, "scale": scale, "present": present,
                                "turns_in_loki": turns_in_loki}

    def up_samples(self, at, span):
        """The collector-health `up` samples in (at - span, at]."""
        if self.collector_up is None:
            return []
        times = self.up_times
        if times is None:
            times = [15.0 * k for k in range(math.floor((at - span) / 15.0), math.floor(at / 15.0) + 1)]
        return [(when, self.collector_up) for when in times if at - span < when <= at]

    # ---- Prometheus
    def prom(self, query, at):
        span = range_seconds(query)
        if "resets(" in query:
            values = self.resets_unscoped if 'instance="unscoped"' in query else self.resets_scoped
            if not values:
                return []
            return [({}, float(max(values) if query.lstrip().startswith("max") else sum(values)))]
        if 'up{job="collector-health"}' in query:  # the raw samples of the window: a range-vector (matrix) answer
            samples = self.up_samples(at, span)
            return Matrix([({"job": "collector-health", "instance": "127.0.0.1:28888"}, samples)] if samples else [])
        if 'otelcol_deltatocumulative_datapoints{error!=""}' in query:
            return [({"error": error}, value) for error, value in self.dropped.items()]
        if 'otelcol_deltatocumulative_datapoints{error=""}' in query:
            return [] if self.accepted is None else [({}, self.accepted)]
        if "last_over_time(" in query and 'instance="unscoped"' in query:
            return [({"job": job}, value) for job, value in self.unscoped.items()]
        if CLAUDE in query:
            if 'instance="unscoped"' in query:
                return []
            subagent = 'query_source="subagent"' in query
            rows = []
            for writer in self.claude.values():
                seen = at - writer["lag"]
                for when, tokens, source in writer["events"]:
                    if (subagent and source != "subagent") or not seen - span < when <= seen:
                        continue
                    rows += [({"instance": writer["instance"], "type": kind}, n * writer["scale"])
                             for kind, n in tokens.items()]
            result = grouped(rows, group_labels(query))
            if re.search(r"\)\s*>\s*0\s*$", query):
                result = [(metric, value) for metric, value in result if value > 0]
            return result
        if CODEX_SUM in query or CODEX_COUNT in query:
            if 'instance="unscoped"' in query:
                return []
            rows = []
            for instance, process in self.codex.items():
                if not process["present"]:
                    continue
                seen = at - process["lag"]
                for when, tokens in process["events"]:
                    if not seen - span < when <= seen:
                        continue
                    if CODEX_COUNT in query:
                        rows.append(({"instance": instance, "token_type": "input"}, 1.0))
                    else:
                        rows += [({"instance": instance, "token_type": CODEX_FIELDS[field]}, n * process["scale"])
                                 for field, n in tokens.items()]
            return grouped(rows, group_labels(query))
        for name, value in (("prometheus_tsdb_head_series", 12709.0), ("prometheus_tsdb_storage_blocks_bytes", 8.0e7),
                            ("prometheus_tsdb_wal_storage_size_bytes", 2.0e7),
                            ("prometheus_tsdb_retention_limit_bytes", 536870912.0),
                            ("prometheus_tsdb_lowest_timestamp_seconds", 2.5 * 86400),
                            ("prometheus_tsdb_size_retentions_total", 0.0),
                            ("otelcol_deltatocumulative_streams_tracked", 184.0),
                            ("otelcol_deltatocumulative_streams_limit", 10000.0)):
            if name in query:
                return [({}, value)]
        if "count by (job)" in query:
            return [({"job": "claude-code"}, 120.0), ({"job": "codex_exec"}, 300.0)]
        self.unknown.append(query)
        return []

    # ---- Loki
    def codex_events(self, instance):
        process = self.codex[instance]
        return [process["start"]] + [when for when, _ in process["events"]]

    def loki(self, query, at):
        span = range_seconds(query)

        def inside(when):
            return at - span < when <= at
        if "codex.conversation_starts" in query:
            return [({"service_instance_id": i}, 1.0) for i, p in self.codex.items() if inside(p["start"])]
        if '{service_name="codex_exec"}' in query and "event_name" not in query:
            rows = [({"service_instance_id": i}, float(sum(inside(t) for t in self.codex_events(i))))
                    for i in self.codex]
            return [(metric, value) for metric, value in rows if value > 0]
        if "codex.sse_event" in query:
            if 'service_instance_id=""' in query:
                return []
            field = re.search(r"unwrap (\w+)", query).group(1)
            rows = [({"service_instance_id": i}, float(sum(tokens.get(field, 0) for when, tokens in p["events"]
                                                            if inside(when))))
                    for i, p in self.codex.items() if p["turns_in_loki"]]
            return [(metric, value) for metric, value in rows if value > 0]
        if "api_request" in query:
            if 'session_id="" and service_instance_id=""' in query:
                return []
            unwrap = re.search(r"unwrap (\w+)", query)
            kind = CLAUDE_FIELDS[unwrap.group(1)] if unwrap else None
            rows = []
            for key, writer in self.claude.items():
                for when, tokens, _ in writer["events"]:
                    if inside(when):
                        rows.append(({"session_id": key}, 1.0 if kind is None else float(tokens.get(kind, 0))))
            result = grouped(rows, group_labels(query))
            return [(metric, value) for metric, value in result if value > 0]
        self.unknown.append(query)
        return []

    def loki_range(self, query, start, end, step):
        span = range_seconds(query) or 60.0
        result = []
        for instance in self.codex:
            values = []
            ts = start
            while ts <= end + 1e-6:
                count = sum(ts - span < when <= ts for when in self.codex_events(instance))
                if count:
                    values.append([ts, str(count)])
                ts += step
            if values:
                result.append({"metric": {"service_instance_id": instance}, "values": values})
        return result


class FakeApis:
    """Serves Telemetry on a loopback port with the Prometheus and Loki HTTP API paths prove.py calls."""

    def __init__(self, model):
        model_ref = model

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                parts = urllib.parse.urlsplit(self.path)
                params = dict(urllib.parse.parse_qsl(parts.query))
                body = self.route(parts.path, params)
                data = json.dumps(body).encode()
                self.send_response(200 if body.get("status") == "success" else 400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def route(self, path, params):
                if path == "/api/v1/status/flags":
                    return {"status": "success", "data": {"enable-feature": model_ref.features}}
                if path == "/api/v1/rules":
                    rules = [{"name": name, "state": "inactive"} for name in model_ref.rules]
                    return {"status": "success", "data": {"groups": [
                        {"name": "native-telemetry-integrity", "rules": rules}]}}
                if path == "/api/v1/alerts":
                    return {"status": "success", "data": {"alerts": []}}
                if path == "/api/v1/status/config":
                    return {"status": "success", "data": {"yaml": model_ref.config_yaml}}
                if path == "/api/v1/targets":
                    return {"status": "success", "data": {"droppedTargets": [], "activeTargets": [
                        {"labels": {"job": "collector-health", "instance": "127.0.0.1:28888"},
                         "scrapePool": "collector-health", "scrapeInterval": "15s", "health": "up"}]}}
                if path == "/api/v1/query":
                    at = float(params["time"])
                    if misplaced_modifier(params["query"]):
                        return {"status": "error", "errorType": "bad_data", "error": "parse error: unexpected "
                                "character: 'a', expected ':'"}
                    rows = model_ref.prom(params["query"], at)
                    return matrix(rows) if isinstance(rows, Matrix) else vector(rows, at)
                if path == "/loki/api/v1/query":
                    at = int(params["time"]) / 1e9
                    return vector(model_ref.loki(params["query"], at), at)
                if path == "/loki/api/v1/query_range":
                    start, end = int(params["start"]) / 1e9, int(params["end"]) / 1e9
                    step = float(params["step"].rstrip("s"))
                    return {"status": "success", "data": {"resultType": "matrix", "result": model_ref.loki_range(
                        params["query"], start, end, step)}}
                return {"status": "error", "error": "unknown path " + path}

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def vector(rows, at):
    return {"status": "success", "data": {"resultType": "vector", "result": [
        {"metric": metric, "value": [at, repr(float(value))]} for metric, value in rows]}}


def matrix(rows):
    return {"status": "success", "data": {"resultType": "matrix", "result": [
        {"metric": metric, "values": [[when, repr(float(value))] for when, value in samples]}
        for metric, samples in rows]}}


class ProveTests(unittest.TestCase):
    """prove.py verdicts over a 30-minute window that ends 120 s before the run (T1)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.now = time.time()
        self.t1 = self.now - 120
        self.t0 = self.t1 - 1800
        self.model = Telemetry(self.now)
        self.apis = FakeApis(self.model)
        # Host files the setup checks read.
        eco = root / "eco"
        real = eco / "tools/codex-0.157.1/bin/codex"
        real.parent.mkdir(parents=True)
        real.write_text("#!/bin/sh\necho codex-cli 0.157.1\n")
        real.chmod(0o755)
        (eco / "bin").mkdir()
        launcher = eco / "bin/codex"
        launcher.write_text(LAUNCHER.read_text().replace("@CODEX_BIN@", str(real)))
        launcher.chmod(0o755)
        self.eco = eco
        self.collector = root / "collector.yaml"
        shutil.copy(COLLECTOR, self.collector)
        self.settings = root / "settings.json"
        self.settings.write_text(json.dumps({"env": {"OTEL_METRICS_INCLUDE_SESSION_ID": "true"}}))
        self.out = root / "out"

    def tearDown(self):
        self.apis.close()
        self.tmp.cleanup()

    # ---- scenario pieces
    def claude_session(self, key, offset, tokens, subagent=False, **kw):
        events = [(self.t0 + offset + 60 * i, dict(tokens), "main") for i in range(5)]
        if subagent:
            events.append((self.t0 + offset + 400, dict(tokens), "subagent"))
        self.model.add_claude(key, events, **kw)

    def codex_process(self, instance, offset, **kw):
        start = self.t0 + offset
        events = [(start + 30, {"input_token_count": 12000, "output_token_count": 800, "cached_token_count": 9000,
                                "reasoning_token_count": 300}),
                  (start + 70, {"input_token_count": 15000, "output_token_count": 500, "cached_token_count": 14000,
                                "reasoning_token_count": 100})]
        self.model.add_codex(instance, start, events, **kw)

    def claude_pair(self):
        tokens = {"input": 40, "output": 900, "cacheRead": 120000, "cacheCreation": 6000}
        self.claude_session("session-a", 300, tokens, subagent=True)
        self.claude_session("session-b", 330, tokens)

    def clean_scenario(self):
        self.claude_pair()
        self.codex_process("codex-p1", 600)
        self.codex_process("codex-p2", 610)

    def prove(self, script="prove.py", extra=(), env=None):
        command = [sys.executable, str(HOST / script)] if script.endswith(".py") else [str(HOST / script)]
        args = ["--window", "30m", "--end-offset", "120s", "--prom", self.apis.url, "--loki", self.apis.url,
                "--eco", str(self.eco), "--collector-config", str(self.collector),
                "--claude-settings", str(self.settings), *extra]
        if not any(arg == "--out" for arg in extra):
            args += ["--out", str(self.out)]
        result = subprocess.run(command + args, capture_output=True, text=True, env=env, timeout=120)
        report = json.loads((self.out / "report.json").read_text()) if (self.out / "report.json").exists() else {}
        return result, report

    def assertVerdict(self, verdict, failed=None):
        result, report = self.prove()
        detail = result.stdout + result.stderr + "\nunknown queries: " + json.dumps(self.model.unknown)
        self.assertEqual(report.get("verdict"), verdict, detail)
        self.assertEqual(result.returncode, {"PASS": 0, "FAIL": 1, "INCONCLUSIVE": 2}[verdict], detail)
        if failed is not None:
            self.assertEqual(sorted(report["failed_checks"]), sorted(failed), detail)
        return report

    # ---- verdicts
    def test_clean_window_passes(self):
        self.clean_scenario()
        self.assertVerdict("PASS", [])

    def test_claude_counters_five_percent_low_fail(self):
        self.clean_scenario()
        self.model.claude["session-a"]["scale"] = 0.95
        self.assertVerdict("FAIL", ["claude.prometheus_vs_loki"])

    def test_codex_process_whose_tokens_never_reached_prometheus_fails(self):
        # The flush at exit is the likeliest loss: every token of that process is missing from Prometheus.
        self.clean_scenario()
        self.codex_process("codex-p3", 620, present=False)
        self.assertVerdict("FAIL", ["codex.prometheus_vs_loki"])

    def test_missing_collector_self_metrics_fail(self):
        # No collector-health scrape: a zero dropped-points count proves nothing.
        self.clean_scenario()
        self.model.collector_up = None
        self.model.accepted = None
        report = self.assertVerdict("FAIL")
        self.assertIn("integrity.collector_self_metrics", report["failed_checks"])

    def test_no_accepted_delta_points_while_codex_is_compared_fails(self):
        self.clean_scenario()
        self.model.accepted = 0.0
        self.assertVerdict("FAIL", ["integrity.delta_to_cumulative_errors"])

    def test_window_without_the_scenario_is_inconclusive(self):
        self.assertVerdict("INCONCLUSIVE", [])

    def test_resumed_session_restarting_each_series_once_passes(self):
        self.clean_scenario()
        self.model.resets_scoped = [1, 1, 1, 1, 1, 0]
        self.assertVerdict("PASS", [])

    def test_repeated_resets_of_one_series_fail(self):
        self.clean_scenario()
        self.model.resets_scoped = [5, 0]
        self.assertVerdict("FAIL", ["integrity.claude_counter_resets"])

    def test_writer_active_at_a_window_edge_is_left_out(self):
        # session-c's large request 5 s before T1 reaches Prometheus 25 s later, after the read at T1 + lag: a
        # whole-window sum would miss it; the per-writer comparison leaves session-c out and compares the rest.
        self.clean_scenario()
        tokens = {"input": 10, "output": 200, "cacheRead": 3000, "cacheCreation": 100}
        big = {"input": 5000, "output": 30000, "cacheRead": 900000, "cacheCreation": 90000}
        self.model.add_claude("session-c", [(self.t0 + 900, tokens, "main"), (self.t1 - 5, big, "main")])
        report = self.assertVerdict("PASS", [])
        self.assertEqual(report["claude"]["compared_writers"], 2)
        self.assertEqual(len(report["claude"]["left_out_at_edges"]), 1)

    def test_codex_processes_without_a_completed_turn_are_not_evidence(self):
        # Two processes that only started: nothing completed in Loki and nothing in Prometheus is 0 against 0 and
        # says nothing about the Codex counters, so the window lacks the Codex half of the scenario.
        self.claude_pair()
        self.model.add_codex("codex-idle-1", self.t0 + 601, [])
        self.model.add_codex("codex-idle-2", self.t0 + 612, [])
        report = self.assertVerdict("INCONCLUSIVE", [])
        self.assertEqual(report["codex"]["compared_processes"], 0)
        self.assertEqual(len(report["codex"]["finished_without_a_completed_turn"]), 2)

    def test_codex_process_with_turn_tokens_only_in_prometheus_fails(self):
        # Loki saw it start but has no completed turn, while Prometheus counted turns for it: a disagreement to
        # report, not an idle process to skip.
        self.clean_scenario()
        self.codex_process("codex-p3", 620, turns_in_loki=False)
        report = self.assertVerdict("FAIL", ["codex.prometheus_vs_loki"])
        self.assertEqual(report["codex"]["compared_processes"], 3)
        self.assertEqual(report["codex"]["finished_without_a_completed_turn"], [])

    def test_sequential_codex_processes_in_one_minute_are_not_concurrent(self):
        # The first finishes before the second starts, both inside one minute: a shared minute is not shared time.
        self.claude_pair()
        turn = {"input_token_count": 9000, "output_token_count": 400, "cached_token_count": 7000,
                "reasoning_token_count": 50}
        first, second = self.t0 + 601, self.t0 + 634
        self.model.add_codex("codex-s1", first, [(first + 11, dict(turn)), (first + 22, dict(turn))])
        self.model.add_codex("codex-s2", second, [(second + 12, dict(turn)), (second + 23, dict(turn))])
        report = self.assertVerdict("INCONCLUSIVE", [])
        self.assertEqual(report["codex"]["compared_processes"], 2)
        self.assertEqual(report["coverage"]["max_compared_codex_processes_active_together"], 1)

    def test_overlapping_codex_processes_are_concurrent(self):
        self.clean_scenario()
        report = self.assertVerdict("PASS", [])
        self.assertEqual(report["coverage"]["max_compared_codex_processes_active_together"], 2)

    def test_self_metrics_only_at_the_end_of_the_window_do_not_cover_it(self):
        # Four samples in the last minute: min_over_time(up) is 1, yet the window before them was not observed, so
        # zero dropped points proves nothing about it.
        self.clean_scenario()
        self.model.up_times = [self.t1 - 50, self.t1 - 35, self.t1 - 20, self.t1 - 5]
        report = self.assertVerdict("FAIL")
        self.assertIn("integrity.collector_self_metrics", report["failed_checks"])
        self.assertIn("integrity.delta_to_cumulative_errors", report["failed_checks"])

    def test_a_scrape_gap_inside_the_window_fails_the_self_metrics_check(self):
        self.clean_scenario()
        grid = [15.0 * k for k in range(math.floor(self.t0 / 15.0), math.floor(self.t1 / 15.0) + 1)]
        self.model.up_times = [when for when in grid if not self.t0 + 600 < when < self.t0 + 900]
        report = self.assertVerdict("FAIL")
        self.assertIn("integrity.collector_self_metrics", report["failed_checks"])
        self.assertGreaterEqual(report["integrity"]["collector_self_metrics"]["longest_gap_s"], 300.0)

    def test_codex_process_with_events_after_the_window_is_not_compared(self):
        self.clean_scenario()
        start = self.t0 + 900
        self.model.add_codex("codex-p4", start, [(start + 20, {"input_token_count": 5000, "output_token_count": 90}),
                                                 (self.t1 + 30, {"input_token_count": 7000,
                                                                 "output_token_count": 70})])
        report = self.assertVerdict("PASS", [])
        self.assertEqual(report["codex"]["compared_processes"], 2)

    def test_report_states_capacity_against_the_limits(self):
        self.clean_scenario()
        report = self.assertVerdict("PASS", [])
        capacity = report["capacity"]
        self.assertEqual(capacity["head_series"], 12709.0)
        self.assertEqual(capacity["retention_limit_bytes"], 536870912.0)
        self.assertEqual(capacity["delta_streams_limit"], 10000.0)
        self.assertEqual(capacity["warnings"], [])

    def test_prove_sh_keeps_reports_in_the_private_state_directory(self):
        self.clean_scenario()
        scripts = Path(self.tmp.name) / "scripts"
        shutil.copytree(HOST, scripts)  # a copy: nothing may be written beside the scripts
        state = Path(self.tmp.name) / "state"
        env = {**os.environ, "XDG_STATE_HOME": str(state)}
        command = [str(scripts / "prove.sh"), "--window", "30m", "--end-offset", "120s", "--prom", self.apis.url,
                   "--loki", self.apis.url, "--eco", str(self.eco), "--collector-config", str(self.collector),
                   "--claude-settings", str(self.settings)]
        result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        reports = list((state / "native-agent-stack/g1-writer-identity").glob("prove-*/report.json"))
        self.assertEqual(len(reports), 1, result.stdout)
        self.assertEqual(stat.S_IMODE(reports[0].parent.parent.stat().st_mode), 0o700)
        self.assertEqual(list(scripts.glob("prove-*")), [])


# ---------------------------------------------------------------------------------------------- apply / rollback

FAKE_CURL = r'''"""Answers the curl calls apply.sh and rollback.sh make, from the sandbox files the fake services would load.

Prometheus answers only on the port of its unit's --web.listen-address (Prometheus's default 9090 without one)."""
import json, os, re, sys, time, urllib.parse
from pathlib import Path

args = sys.argv[1:]
state = Path(os.environ["FAKE_STATE"])
cfg = Path(os.environ["HOME"]) / ".config/ecosystem-observability"
unit = Path(os.environ["HOME"]) / ".config/systemd/user/ecosystem-prometheus.service"
url = next(arg for arg in args if arg.startswith("http"))
extra = [args[i + 1] for i, arg in enumerate(args) if arg == "--data-urlencode"]
out = args[args.index("-o") + 1] if "-o" in args else None
with open(state / "curl.log", "a") as log:
    log.write(url + " " + " ".join(extra) + "\n")
parts = urllib.parse.urlsplit(url)
params = dict(urllib.parse.parse_qsl(parts.query))
params.update(dict(item.split("=", 1) for item in extra))


def reply(body, code=0):
    if out is None or out == "-":
        sys.stdout.write(body)
    elif out != "/dev/null":
        Path(out).write_text(body)
    sys.exit(code)


def features():
    if "FAKE_FEATURES" in os.environ:
        return os.environ["FAKE_FEATURES"]
    text = unit.read_text() if unit.exists() else ""
    return text.split("--enable-feature=", 1)[1].split()[0] if "--enable-feature=" in text else ""


def prometheus_port():
    match = re.search(r"--web\.listen-address=\S*:(\d+)", unit.read_text() if unit.exists() else "")
    return int(match.group(1)) if match else 9090


def rfc3339(epoch, fraction=True):
    seconds, nanos = divmod(int(round(epoch * 1e9)), 10 ** 9)
    whole = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(seconds))
    return whole + (".%09d" % nanos if fraction else "") + "Z"


if parts.path == "/":
    reply("ok")
if (parts.path == "/-/ready" or parts.path.startswith("/api/v1/")) and parts.port != prometheus_port():
    sys.stderr.write("curl: (7) Failed to connect\n")
    sys.exit(7)
if parts.path == "/-/ready":
    reply("ok")
if parts.path == "/api/v1/status/runtimeinfo":
    # Started (and loaded its config) at the last restart; before any restart, long before the sandbox files.
    restarted = state / "prometheus.restarted"
    started = float(restarted.read_text()) if restarted.exists() else time.time() - 116000.0
    reply(json.dumps({"status": "success", "data": {"startTime": rfc3339(started),
                                                    "lastConfigTime": rfc3339(started, fraction=False),
                                                    "reloadConfigSuccess": True}}))
if parts.path == "/api/v1/status/flags":
    reply(json.dumps({"status": "success", "data": {"enable-feature": features()}}))
if parts.path == "/api/v1/rules":
    import yaml
    doc = yaml.safe_load((cfg / "ecosystem-prometheus-rules.yml").read_text()) or {}
    groups = [{"name": g["name"], "rules": [{"name": r.get("alert") or r.get("record")} for r in g.get("rules", [])]}
              for g in doc.get("groups") or []]
    reply(json.dumps({"status": "success", "data": {"groups": groups}}))
if parts.path == "/api/v1/query":
    if "anchored" in params.get("query", "") and ("promql-extended-range-selectors" not in features()
                                                  or os.environ.get("FAKE_ANCHORED_FAILS") == "1"):
        sys.stderr.write("curl: (22) The requested URL returned error: 400\n")
        sys.exit(22)
    reply(json.dumps({"status": "success", "data": {"resultType": "vector", "result": []}}))
if parts.path == "/api/v1/status/config":
    reply(json.dumps({"status": "success", "data": {"yaml": (cfg / "ecosystem-prometheus.yml").read_text()}}))
if parts.path == "/metrics":
    restarted = state / "otelcol.restarted"
    since = time.time() - float(restarted.read_text()) if restarted.exists() else 116000.0
    uptime = float(os.environ.get("FAKE_OTELCOL_UPTIME", since))
    lines = ["otelcol_process_uptime %f" % uptime,
             'otelcol_processor_incoming_items{otel_signal="metrics",processor="memory_limiter"} 40']
    if "groupbyattrs/session" in (cfg / "collector.yaml").read_text() and os.environ.get("FAKE_NO_GROUPBY") != "1":
        lines.append('otelcol_processor_incoming_items{otel_signal="metrics",processor="groupbyattrs/session"} 40')
    reply("\n".join(lines) + "\n")
sys.stderr.write("curl: (7) Failed to connect\n")
sys.exit(7)
'''

FAKE_SYSTEMCTL = '''#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_STATE/systemctl.log"
case "$*" in
  *"restart "*) [ "${FAKE_RESTART_RC:-0}" = 0 ] || exit "$FAKE_RESTART_RC" ;;
esac
case "$*" in
  *"restart ecosystem-otelcol.service"*) date +%s.%N > "$FAKE_STATE/otelcol.restarted" ;;
  *"restart ecosystem-prometheus.service"*) date +%s.%N > "$FAKE_STATE/prometheus.restarted" ;;
  *is-active*) echo active ;;
esac
exit 0
'''

FAKE_VERIFY = '''#!/bin/sh
[ "${FAKE_VERIFY_RC:-0}" = 0 ] || echo "ecosystem-prometheus.service: Command /x is not executable" >&2
exit "${FAKE_VERIFY_RC:-0}"
'''

FAKE_OTELCOL = '''#!/bin/sh
[ "${FAKE_OTELCOL_RC:-0}" = 0 ] || echo "Error: invalid configuration: processors::transform/privacy" >&2
exit "${FAKE_OTELCOL_RC:-0}"
'''

FAKE_PROMTOOL = '''#!/bin/sh
echo "Checking $3"
[ "${FAKE_PROMTOOL_RC:-0}" = 0 ] && echo "  SUCCESS: file is valid" || echo "  FAILED: bad file"
exit "${FAKE_PROMTOOL_RC:-0}"
'''

FAKE_CODEX = '''#!/bin/sh
[ "${FAKE_CODEX_BROKEN:-0}" = 1 ] && exit 1
[ "$1" = --version ] && echo "codex-cli 0.157.1"
exit 0
'''


def old_collector_profile():
    """The repository collector.yaml without the writer-identity parts: the host state before the change."""
    config = yaml.safe_load(COLLECTOR.read_text())
    config["processors"].pop("groupbyattrs/session")
    config["processors"]["deltatocumulative"] = config["processors"].pop("delta_to_cumulative")
    config["service"]["pipelines"]["metrics"]["processors"] = [
        "memory_limiter", "transform/privacy", "deltatocumulative", "batch"]
    groups = config["processors"]["transform/privacy"]["metric_statements"]
    groups[:] = [g for g in groups if g["context"] != "metric"]
    for group in groups:
        group["statements"] = [s for s in group["statements"] if "session.id" not in s]
    return yaml.safe_dump(config, sort_keys=False, width=4096)


def old_prometheus_config(cfg):
    doc = yaml.safe_load(SCRAPE.read_text().replace("@CONFIG_ROOT@", str(cfg)))
    for job in doc["scrape_configs"]:
        job.pop("metric_relabel_configs", None)
    return yaml.safe_dump(doc, sort_keys=False)


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("bash") and HAVE_YAML,
                     "the host recipe targets Linux user services and needs bash and PyYAML")
class ApplyRollbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.scripts = root / "scripts"
        shutil.copytree(HOST, self.scripts)  # a copy: nothing may be written beside the scripts
        self.home = root / "home"
        self.state = root / "state"
        self.fake_state = root / "fake-state"
        self.fake_state.mkdir()
        fake = root / "fake-bin"
        fake.mkdir()
        (root / "fake_curl.py").write_text(FAKE_CURL)
        curl = f'#!/bin/sh\nexec "{sys.executable}" "{root / "fake_curl.py"}" "$@"\n'
        for name, body in (("curl", curl), ("systemctl", FAKE_SYSTEMCTL), ("systemd-analyze", FAKE_VERIFY),
                           ("sleep", "#!/bin/sh\nexit 0\n")):
            (fake / name).write_text(body)
            (fake / name).chmod(0o755)
        eco = self.home / ".local/share/codex-ecosystem"
        for relative, body in (("tools/otelcol-0.161.0/otelcol-contrib", FAKE_OTELCOL),
                               ("tools/ecosystem-prometheus-3.15.0/promtool", FAKE_PROMTOOL),
                               ("tools/codex-0.157.1/bin/codex", FAKE_CODEX)):
            path = eco / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body)
            path.chmod(0o755)
        (eco / "bin").mkdir()
        self.codex_real = eco / "tools/codex-0.157.1/bin/codex"
        self.codex_link = eco / "bin/codex"
        self.codex_link.symlink_to(self.codex_real)
        self.cfg = self.home / ".config/ecosystem-observability"
        (self.cfg / "ecosystem-grafana-dashboards").mkdir(parents=True)
        (self.cfg / "collector.yaml").write_text(old_collector_profile())
        (self.cfg / "port-overrides.json").write_text("{}\n")
        (self.cfg / "ecosystem-prometheus.yml").write_text(old_prometheus_config(self.cfg))
        (self.cfg / "ecosystem-prometheus-rules.yml").write_text("groups: []\n")
        (self.cfg / "ecosystem-grafana-dashboards/ecosystem-dashboard.json").write_text("{}\n")
        (self.cfg / "ecosystem-grafana-dashboards/research-grand.json").write_text("{}\n")
        self.unit = self.home / ".config/systemd/user/ecosystem-prometheus.service"
        self.unit.parent.mkdir(parents=True)
        self.unit.write_text("[Service]\nExecStart=/old/prometheus --web.listen-address=127.0.0.1:19090\n")
        self.settings = self.home / ".claude/settings.json"
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(json.dumps({"model": "keep-me", "env": {
            "OTEL_METRICS_INCLUDE_SESSION_ID": "false", "OTHER": "unchanged"}}, indent=2) + "\n")
        self.watched = [self.cfg / "collector.yaml", self.cfg / "ecosystem-prometheus.yml",
                        self.cfg / "ecosystem-prometheus-rules.yml", self.unit, self.settings,
                        self.cfg / "ecosystem-grafana-dashboards/ecosystem-dashboard.json",
                        self.cfg / "ecosystem-grafana-dashboards/research-grand.json"]
        self.original = {path: path.read_bytes() for path in self.watched}
        (root / "tmp").mkdir()
        env = {k: v for k, v in os.environ.items()
               if k not in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "REPO", "PY") and not k.startswith("FAKE_")}
        env.update(HOME=str(self.home), XDG_STATE_HOME=str(self.state), FAKE_STATE=str(self.fake_state),
                   PATH=f"{fake}:{os.environ.get('PATH', '/usr/bin:/bin')}", PY=sys.executable,
                   TMPDIR=str(root / "tmp"))
        self.env = env
        # No real service manager may be reachable from here.
        self.assertEqual(shutil.which("systemctl", path=env["PATH"]), str(fake / "systemctl"))
        self.assertEqual(shutil.which("curl", path=env["PATH"]), str(fake / "curl"))

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, name, *args, **fake_env):
        env = {**self.env, **fake_env}
        return subprocess.run([str(self.scripts / name), *args], capture_output=True, text=True, env=env,
                              timeout=300, cwd=self.tmp.name)

    def apply(self, *args, **fake_env):
        return self.run_script("apply.sh", "--repo", str(ROOT), *args, **fake_env)

    def restarts(self):
        log = self.fake_state / "systemctl.log"
        return [line for line in log.read_text().splitlines() if "restart" in line] if log.exists() else []

    def backups(self):
        return sorted((self.state / "native-agent-stack/g1-writer-identity").glob("backup-*"))

    def use_prometheus_port(self, port):
        """This host moved Prometheus off its template port (configure.py --port-overrides)."""
        (self.cfg / "port-overrides.json").write_text(json.dumps({"19090": port}) + "\n")
        for path in (self.cfg / "ecosystem-prometheus.yml", self.unit):
            path.write_text(path.read_text().replace("127.0.0.1:19090", f"127.0.0.1:{port}"))
        self.original = {path: path.read_bytes() for path in self.watched}

    # ---- validation stops the script
    def test_dry_run_changes_nothing(self):
        result = self.apply()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("dry run only; nothing was changed", result.stdout)
        self.assertEqual({path: path.read_bytes() for path in self.watched}, self.original)
        self.assertTrue(self.codex_link.is_symlink())
        self.assertEqual(self.restarts(), [])

    def test_collector_validation_failure_stops_the_script(self):
        result = self.apply(FAKE_OTELCOL_RC="1")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("otelcol-contrib validate: ok", result.stdout)
        self.assertNotIn("step prometheus", result.stdout)

    def test_collector_validation_failure_installs_nothing_on_apply(self):
        result = self.apply("--apply", FAKE_OTELCOL_RC="1")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual({path: path.read_bytes() for path in self.watched}, self.original)
        self.assertEqual(self.restarts(), [])

    def test_unit_verification_failure_stops_the_script(self):
        result = self.apply(FAKE_VERIFY_RC="1")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("step prometheus", result.stdout)

    def test_codex_that_does_not_answer_its_version_stops_the_script(self):
        result = self.apply(FAKE_CODEX_BROKEN="1")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("step prometheus", result.stdout)

    # ---- read-backs after the restarts
    def test_prometheus_without_both_features_stops_the_apply(self):
        result = self.apply("--apply", FAKE_FEATURES="created-timestamp-zero-ingestion")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("rollback.sh", result.stderr)

    def test_anchored_query_that_does_not_parse_stops_the_apply(self):
        result = self.apply("--apply", FAKE_ANCHORED_FAILS="1")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("rollback.sh", result.stderr)

    def test_collector_that_did_not_restart_stops_the_apply(self):
        result = self.apply("--apply", FAKE_OTELCOL_UPTIME="116000")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("rollback.sh", result.stderr)

    def test_collector_without_the_session_grouping_stops_the_apply(self):
        result = self.apply("--apply", FAKE_NO_GROUPBY="1")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("rollback.sh", result.stderr)

    def test_apply_and_rollback_read_prometheus_back_on_its_overridden_port(self):
        # Nothing may be read from the template port 19090: another instance could answer there.
        self.use_prometheus_port(29090)
        result = self.apply("--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--web.listen-address=127.0.0.1:29090", self.unit.read_text())
        undo = self.run_script("rollback.sh", "--apply")
        self.assertEqual(undo.returncode, 0, undo.stdout + undo.stderr)
        self.assertEqual({path: path.read_bytes() for path in self.watched}, self.original)
        self.assertNotIn("127.0.0.1:19090", (self.fake_state / "curl.log").read_text())

    # ---- a rerun reads the running services back even when every file is already in place
    def test_rerun_after_a_failed_prometheus_read_back_checks_the_service_again(self):
        first = self.apply("--apply", FAKE_FEATURES="created-timestamp-zero-ingestion")
        self.assertEqual(first.returncode, 1, first.stdout + first.stderr)
        restarts = len(self.restarts())
        again = self.apply("--apply", FAKE_FEATURES="created-timestamp-zero-ingestion")
        self.assertEqual(again.returncode, 1, again.stdout + again.stderr)
        self.assertIn("rollback.sh", again.stderr)
        self.assertIn("restart ecosystem-prometheus.service", "\n".join(self.restarts()[restarts:]))

    def test_rerun_after_a_failed_collector_read_back_checks_the_service_again(self):
        first = self.apply("--apply", FAKE_OTELCOL_UPTIME="116000")
        self.assertEqual(first.returncode, 1, first.stdout + first.stderr)
        again = self.apply("--apply", FAKE_OTELCOL_UPTIME="116000")
        self.assertEqual(again.returncode, 1, again.stdout + again.stderr)
        self.assertIn("rollback.sh", again.stderr)

    def test_rerun_restarts_a_prometheus_that_predates_its_installed_files(self):
        # The first run installs the Prometheus files and its restart fails; on the rerun every file matches, but
        # the running Prometheus still serves what it loaded before them.
        first = self.apply("--apply", FAKE_RESTART_RC="1")
        self.assertNotEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertIn("--enable-feature=", self.unit.read_text())
        restarts = len(self.restarts())
        again = self.apply("--apply")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertIn("restart ecosystem-prometheus.service", "\n".join(self.restarts()[restarts:]))

    # ---- backup, idempotence and rollback
    def test_apply_backs_up_privately_and_rollback_restores_every_file(self):
        result = self.apply("--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        backups = self.backups()
        self.assertEqual(len(backups), 1, result.stdout)
        self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(backups[0].parent.stat().st_mode), 0o700)
        self.assertEqual(list(self.scripts.glob("backup-*")) + list(self.scripts.glob("apply-*")), [])
        # Installed: the launcher, the merged configs; only the one settings key changed.
        self.assertFalse(self.codex_link.is_symlink())
        self.assertIn("Codex telemetry identity launcher", self.codex_link.read_text())
        self.assertIn("groupbyattrs/session", (self.cfg / "collector.yaml").read_text())
        installed = yaml.safe_load((self.cfg / "ecosystem-prometheus.yml").read_text())
        before = yaml.safe_load(self.original[self.cfg / "ecosystem-prometheus.yml"])
        job = next(j for j in installed["scrape_configs"] if j["job_name"] == "collector-native")
        self.assertIn("metric_relabel_configs", job)
        job.pop("metric_relabel_configs")
        self.assertEqual(installed, before)
        self.assertIn("--enable-feature=created-timestamp-zero-ingestion,promql-extended-range-selectors",
                      self.unit.read_text())
        settings = json.loads(self.settings.read_text())
        self.assertEqual(settings["env"], {"OTEL_METRICS_INCLUDE_SESSION_ID": "true", "OTHER": "unchanged"})
        self.assertEqual(settings["model"], "keep-me")
        # A second apply finds everything in place and restarts nothing.
        restarts = len(self.restarts())
        again = self.apply("--apply")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(len(self.restarts()), restarts, again.stdout)
        # Rollback finds the newest backup by itself and restores every byte.
        dry = self.run_script("rollback.sh")
        self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
        self.assertIn(str(backups[0]), dry.stdout)
        undo = self.run_script("rollback.sh", "--apply")
        self.assertEqual(undo.returncode, 0, undo.stdout + undo.stderr)
        self.assertEqual({path: path.read_bytes() for path in self.watched}, self.original)
        self.assertTrue(self.codex_link.is_symlink())
        self.assertEqual(os.readlink(self.codex_link), str(self.codex_real))

    def test_rollback_refuses_a_file_changed_after_apply(self):
        self.assertEqual(self.apply("--apply").returncode, 0)
        edited = (self.cfg / "collector.yaml").read_text() + "# edited after apply\n"
        (self.cfg / "collector.yaml").write_text(edited)
        undo = self.run_script("rollback.sh", "--apply")
        self.assertNotEqual(undo.returncode, 0, undo.stdout)
        self.assertIn("refused", undo.stdout + undo.stderr)
        self.assertEqual((self.cfg / "collector.yaml").read_text(), edited)

    def test_rollback_refuses_a_settings_key_changed_after_apply(self):
        self.assertEqual(self.apply("--apply").returncode, 0)
        applied = {path: path.read_bytes() for path in self.watched}
        settings = json.loads(self.settings.read_text())
        settings["env"]["OTEL_METRICS_INCLUDE_SESSION_ID"] = "1"  # the user's own later choice
        self.settings.write_text(json.dumps(settings, indent=2) + "\n")
        edited = self.settings.read_bytes()
        undo = self.run_script("rollback.sh", "--apply")
        self.assertEqual(undo.returncode, 1, undo.stdout + undo.stderr)
        self.assertIn("refused", undo.stdout)
        self.assertEqual(self.settings.read_bytes(), edited)
        self.assertEqual((self.cfg / "collector.yaml").read_bytes(), applied[self.cfg / "collector.yaml"])
        forced = self.run_script("rollback.sh", "--apply", "--force")
        self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
        self.assertEqual(json.loads(self.settings.read_text())["env"]["OTEL_METRICS_INCLUDE_SESSION_ID"], "false")

    def test_rollback_restores_nothing_when_a_backup_copy_is_missing(self):
        self.assertEqual(self.apply("--apply").returncode, 0)
        applied = {path: path.read_bytes() for path in self.watched}
        manifest = json.loads((self.backups()[0] / "manifest.json").read_text())
        copies = [entry["backup"] for entry in manifest if entry.get("backup")]
        Path(copies[-1]).unlink()
        undo = self.run_script("rollback.sh", "--apply")
        self.assertNotEqual(undo.returncode, 0, undo.stdout)
        self.assertEqual({path: path.read_bytes() for path in self.watched}, applied)
        self.assertFalse(self.codex_link.is_symlink())


if __name__ == "__main__":
    unittest.main()
