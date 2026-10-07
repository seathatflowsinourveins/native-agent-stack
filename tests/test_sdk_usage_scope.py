"""Synthetic SDK observations through the native Collector and dashboard query.

Sources: openai/codex rust-v0.159.2 sdk/python/src/openai_codex/_run.py,
generated/v2_all.py (ThreadTokenUsage), and codex-rs/protocol/src/protocol.rs
(TokenUsageInfo::append_last_usage); opentelemetry-collector-contrib v0.161.0
processor/transformprocessor, receiver/filelogreceiver, and exporter/fileexporter.
The isolated Collector/Loki fixture reuses test_observability_run_correlation.
These are local integration checks, not new provider runs or upstream tests.
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import socket
import tempfile
import time
import unittest
import uuid

from tests import test_observability_run_correlation as native

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(native.yaml and native.OTELCOL.exists() and native.LOKI.exists(),
                     f"requires PyYAML, otelcol-contrib {native.OTELCOL_VERSION} and Loki 3.7.8; set OTELCOL_TEST_BIN for a scratch install")
class NativeSDKUsageScopeTests(unittest.TestCase):
    """Exercise the actual SDK file receiver, processors, and Loki aggregation."""

    start_process = native.NativeRunCorrelationTests.start_process
    stop_process = staticmethod(native.NativeRunCorrelationTests.stop_process)
    api = native.NativeRunCorrelationTests.api
    query_rows = native.NativeRunCorrelationTests.query_rows

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.receipts = self.root / "sdk-receipts"
        self.receipts.mkdir()
        sockets = [socket.socket() for _ in range(3)]
        try:
            for sock in sockets:
                sock.bind(("127.0.0.1", 0))
            self.health, self.loki, grpc = [sock.getsockname()[1] for sock in sockets]
        finally:
            for sock in sockets:
                sock.close()

        loki = native.yaml.safe_load(native.LOKI_CONFIG.read_text().replace("@DATA_ROOT@", str(self.root)))
        loki["server"].update(http_listen_port=self.loki, grpc_listen_port=grpc)
        self.start_process("loki", loki, native.LOKI, "-config.file", ["-ingester.min-ready-duration=0s"],
                           f"http://127.0.0.1:{self.loki}/ready")

        template = native.yaml.safe_load(native.COLLECTOR.read_text())
        pipeline = template["service"]["pipelines"]["logs/sdk_receipts"]
        receiver = template["receivers"]["file_log/sdk_receipts"]
        receiver["include"] = [str(self.receipts / "*.json")]
        self.output = self.root / "events.jsonl"
        template["exporters"]["otlphttp/loki"]["endpoint"] = f"http://127.0.0.1:{self.loki}/otlp"
        template["exporters"]["file/events"]["path"] = str(self.output)
        (self.root / "queue").mkdir()
        config = {
            "receivers": {"file_log/sdk_receipts": receiver},
            "processors": {key: template["processors"][key] for key in pipeline["processors"]},
            "exporters": {key: template["exporters"][key] for key in pipeline["exporters"]},
            "extensions": {
                "file_storage": {"directory": str(self.root / "queue")},
                "health_check": {"endpoint": f"127.0.0.1:{self.health}"},
            },
            "service": {
                "extensions": ["file_storage", "health_check"],
                "telemetry": {"logs": {"level": "warn"}, "metrics": {"level": "none"}},
                "pipelines": {"logs/sdk_receipts": pipeline},
            },
        }
        self.start_process("collector", config, native.OTELCOL, "--config", [],
                           f"http://127.0.0.1:{self.health}/")
        source = ast.parse((ROOT / "blueprints/us-equities/workers/native_worker.py").read_text())
        helper = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == "write_observation")
        scope = {"os": os, "uuid": uuid, "json": json, "Path": Path}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), "native_worker.py", "exec"), scope)
        self.publish = scope["write_observation"]
        dashboard = json.loads((ROOT / "observability/backends/templates/ecosystem-dashboard.json.example").read_text())
        panel = next(p for p in dashboard["panels"] if p["id"] == 20)
        self.aggregate = panel["targets"][0]["expr"].replace("$__range", "5m")
        self.selector = '{service_name="codex-sdk-receipt"}'
        self.start = time.time_ns() - 1_000_000_000

    def wait_for_records(self, count):
        deadline = time.monotonic() + 20
        while True:
            rows = self.query_rows(self.selector)
            if len(rows) >= count or time.monotonic() >= deadline:
                break
            time.sleep(0.1)
        self.assertEqual(len(rows), count, "all observations must reach Loki before checking the aggregate")
        return rows

    def assert_no_additive_usage(self, stage):
        result = self.api("query", query=self.aggregate, time=str(time.time_ns()))
        print(json.dumps({"stage": stage, "dashboard_result": result["result"]}, sort_keys=True), flush=True)
        self.assertEqual(result["result"], [], "cumulative or unavailable usage must be absent, never an additive total or zero")

    def test_cumulative_start_resume_replay_and_missing_baseline_are_not_additive(self):
        # Numeric allowlist from the already published native qualification receipt.
        # Constructed SDK-shaped snapshots are a replay fixture, not provider execution.
        qualification = json.loads((ROOT / "evidence/artifacts/runtime-sdk-20260930/receipt.json").read_text())
        snapshots = [attempt["native_thread_cumulative_usage"] for attempt in qualification["live_attempts"]
                     if "native_thread_cumulative_usage" in attempt]
        self.assertEqual([snapshot["total_tokens"] for snapshot in snapshots], [26045, 52286])
        results = []
        for snapshot in snapshots:
            total = {"inputTokens": snapshot["input_tokens"], "outputTokens": snapshot["output_tokens"],
                     "cachedInputTokens": snapshot["cached_input_tokens"],
                     "reasoningOutputTokens": snapshot["reasoning_output_tokens"],
                     "totalTokens": snapshot["total_tokens"]}
            result = {"status": "completed", "configured_model": "synthetic-model",
                      "usage_status": "reported", "usage_scope": "native_thread_cumulative",
                      "usage": {"total": total, "last": {"totalTokens": 1}},
                      "thread_id": "PRIVATE_THREAD_ID", "items": ["PRIVATE_CONTENT"]}
            results.append(result)
            self.publish(self.receipts, result)
        self.wait_for_records(2)
        self.assert_no_additive_usage("start_and_resume")
        self.assertEqual(len(self.query_rows(self.selector + ' | usage_scope="native_thread_cumulative"')), 2)

        # Re-serialize the same observation ID so the receiver sees a new file
        # fingerprint; replay identity is retained through the actual dashboard.
        first = next(self.receipts.glob("*.json"))
        replay = json.loads(first.read_text())
        (self.receipts / "replay.json").write_text(json.dumps(replay, indent=4, sort_keys=True) + "\n")
        self.publish(self.receipts, results[1])  # Republishing cannot turn cumulative usage into a delta.
        self.wait_for_records(4)
        self.assert_no_additive_usage("same_id_replay_and_new_id_republication")
        self.assertEqual(len(self.query_rows(self.selector + f' | receipt_id="{replay["observation_id"]}"')), 2)

        self.publish(self.receipts, {"status": "failed", "usage": None,
                                    "usage_scope": None, "usage_status": "unavailable_after_failure"})
        # Legacy files may bypass the corrected producer. No scope/baseline, an
        # unrecognized scope, and prefilled additive fields must remain excluded.
        for index, scope in enumerate((None, "unknown", "native_thread_cumulative")):
            legacy = {"observation_id": f"legacy-{index}", "usage_status": "reported",
                      "usage": results[1]["usage"], "total_token_count": 52286,
                      "input_token_count": 52206, "output_token_count": 80,
                      "cached_token_count": 38528, "reasoning_token_count": 10}
            if scope is not None:
                legacy["usage_scope"] = scope
            (self.receipts / f"legacy-{index}.json").write_text(json.dumps(legacy, indent=2) + "\n")
        rows = self.wait_for_records(8)
        self.assert_no_additive_usage("unavailable_and_legacy_without_additive_baseline")
        self.assertEqual({row[1] for row in rows}, {"[content omitted]"})
        self.assertEqual(len(self.query_rows(self.selector + ' | usage_status="unavailable_after_failure"')), 1)
        self.assertEqual(len(self.query_rows(self.selector + ' | usage_scope="native_thread_cumulative"')), 5)

        events = [json.loads(line) for line in self.output.read_text().splitlines() if line]
        records = [record for event in events for resource in event["resourceLogs"]
                   for scope in resource["scopeLogs"] for record in scope["logRecords"]]
        self.assertEqual(len(records), 8)
        additive = {"input_token_count", "output_token_count", "cached_token_count",
                    "reasoning_token_count", "total_token_count"}
        for record in records:
            keys = {attribute["key"] for attribute in record["attributes"]}
            self.assertFalse(keys & additive, keys)
        self.assertNotIn("PRIVATE_", self.output.read_text())


if __name__ == "__main__":
    unittest.main()
