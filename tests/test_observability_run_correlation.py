"""Run/tool/cost retention and Codex privacy through the Collector/Loki profiles.

Sources (reviewed 2026-09-27):
- https://code.claude.com/docs/en/monitoring-usage (API/tool events and resource attributes)
- open-telemetry/opentelemetry-collector-contrib v0.161.0:
  processor/transformprocessor/README.md and pkg/ottl/ottlfuncs/func_keep_keys.go
- https://grafana.com/docs/loki/latest/send-data/otel/ (structured metadata)
- https://grafana.com/docs/loki/latest/reference/loki-http-api/ (query and series APIs)
- open-telemetry/opentelemetry-proto v1.9.0, docs/specification.md (OTLP HTTP JSON)
- openai/codex rust-v0.157.1, codex-rs/otel/src/tool_result.rs:25-110,
  codex-rs/otel/src/events/shared.rs and codex-rs/core/src/tools/call_trace.rs

The subprocess/OTLP pattern follows test_observability_tool_names.py. Native
tests use the documented installed pins and synthetic records only; they skip
when the binaries or PyYAML are absent. This is local integration evidence,
not live Claude execution, deployment acceptance or unchanged upstream tests.
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "observability/collector/collector.yaml"
LOKI_CONFIG = ROOT / "observability/backends/templates/ecosystem-loki.yml.example"
TOOLS = Path.home() / ".local/share/codex-ecosystem/tools"
OTELCOL = TOOLS / "otelcol-0.161.0/otelcol-contrib"
LOKI = TOOLS / "ecosystem-loki-3.7.8/loki-linux-amd64"

try:
    import yaml
except ImportError:
    yaml = None


class CollectorProfileTests(unittest.TestCase):
    def test_log_allowlist_keeps_run_tool_and_estimated_cost(self):
        # Keep this small configuration regression active without optional deps.
        privacy = COLLECTOR.read_text().split("  transform/privacy:\n", 1)[1]
        logs, metrics = privacy.split("    metric_statements:\n", 1)
        resource, records = logs.split("      - context: log\n", 1)
        resource_keys = json.loads(re.search(r"keep_keys\(attributes, (\[.*\])\)", resource)[1])
        log_keys = json.loads(re.search(r"keep_keys\(attributes, (\[.*\])\)", records)[1])
        self.assertIn("ecosystem.task.id", resource_keys)
        for key in ("workflow.run_id", "session.id", "tool_use_id", "cost_usd"):
            with self.subTest(attribute=key):
                self.assertIn(key, log_keys)
        for key in ("ecosystem.task.id", "workflow.run_id", "tool_use_id", "cost_usd"):
            self.assertNotIn(f'"{key}"', metrics)

    @unittest.skipUnless(yaml, "optional PyYAML structural check")
    def test_loki_indexes_only_service_name(self):
        config = yaml.safe_load(LOKI_CONFIG.read_text())
        limits = config["limits_config"]
        self.assertIs(limits["allow_structured_metadata"], True)
        self.assertEqual(limits["otlp_config"]["resource_attributes"], {
            "ignore_defaults": True,
            "attributes_config": [{"action": "index_label", "attributes": ["service.name"]}],
        })

    def test_codex_measurement_metadata_survives_without_content(self):
        privacy = COLLECTOR.read_text().split("  transform/privacy:\n", 1)[1]
        logs = privacy.split("    metric_statements:\n", 1)[0]
        records = logs.split("      - context: log\n", 1)[1]
        keys = json.loads(re.search(r"keep_keys\(attributes, (\[.*\])\)", records)[1])
        for key in ("tool_name", "tool_namespace", "mcp_server.name", "duration_ms", "success",
                    "arguments_length", "output_length", "output_line_count", "output_truncated",
                    "conversation.id", "thread.id", "turn.id", "ecosystem.task.id"):
            with self.subTest(attribute=key):
                self.assertIn(key, keys)
        for key in ("arguments", "output", "prompt", "content"):
            self.assertNotIn(key, keys)


def otlp_attributes(values):
    result = []
    for key, value in values.items():
        if isinstance(value, bool):
            encoded = {"boolValue": value}
        elif isinstance(value, int):
            encoded = {"intValue": str(value)}
        elif isinstance(value, float):
            encoded = {"doubleValue": value}
        else:
            encoded = {"stringValue": value}
        result.append({"key": key, "value": encoded})
    return result


@unittest.skipUnless(yaml and OTELCOL.exists() and LOKI.exists(),
                     "requires PyYAML, otelcol-contrib 0.161.0 and Loki 3.7.8 at documented paths")
class NativeRunCorrelationTests(unittest.TestCase):
    """Synthetic OTLP -> native Collector -> native Loki, on isolated loopback ports."""

    SECRET = "SYNTHETIC-CONTENT-MUST-BE-REMOVED"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        sockets = [socket.socket() for _ in range(4)]
        try:
            for sock in sockets:
                sock.bind(("127.0.0.1", 0))
            self.otlp, self.health, self.loki, grpc = [sock.getsockname()[1] for sock in sockets]
        finally:
            for sock in sockets:
                sock.close()

        loki = yaml.safe_load(LOKI_CONFIG.read_text().replace("@DATA_ROOT@", str(self.root)))
        loki["server"].update(http_listen_port=self.loki, grpc_listen_port=grpc)
        self.start_process("loki", loki, LOKI, "-config.file", ["-ingester.min-ready-duration=0s"],
                           f"http://127.0.0.1:{self.loki}/ready")

        config = yaml.safe_load(COLLECTOR.read_text())
        pipeline = config["service"]["pipelines"]["logs"]
        self.assertEqual(pipeline["exporters"], ["otlphttp/loki", "file/events"])
        self.output = self.root / "events.jsonl"
        config["exporters"]["otlphttp/loki"]["endpoint"] = f"http://127.0.0.1:{self.loki}/otlp"
        config["exporters"]["file/events"]["path"] = str(self.output)
        (self.root / "queue").mkdir()
        config = {
            "receivers": {"otlp": {"protocols": {"http": {"endpoint": f"127.0.0.1:{self.otlp}"}}}},
            "processors": {key: config["processors"][key] for key in pipeline["processors"]},
            "exporters": {key: config["exporters"][key] for key in pipeline["exporters"]},
            "extensions": {
                "file_storage": {"directory": str(self.root / "queue")},
                "health_check": {"endpoint": f"127.0.0.1:{self.health}"},
            },
            "service": {
                "extensions": ["file_storage", "health_check"],
                "telemetry": {"logs": {"level": "warn"}, "metrics": {"level": "none"}},
                "pipelines": {"logs": pipeline},
            },
        }
        self.start_process("collector", config, OTELCOL, "--config", [],
                           f"http://127.0.0.1:{self.health}/")

    def start_process(self, name, config, binary, flag, args, health):
        path = self.root / f"{name}.yaml"
        path.write_text(yaml.safe_dump(config))
        log_path = self.root / f"{name}.log"
        log = log_path.open("w")
        self.addCleanup(log.close)
        process = subprocess.Popen([str(binary), f"{flag}={path}", *args], stdout=log, stderr=subprocess.STDOUT)
        self.addCleanup(self.stop_process, process)
        deadline = time.monotonic() + 45
        while True:
            try:
                with urllib.request.urlopen(health, timeout=1):
                    return
            except OSError:
                if process.poll() is not None or time.monotonic() >= deadline:
                    # Native diagnostics contain only temporary fixture paths; sanitize those too.
                    self.fail(log_path.read_text().replace(str(self.root), "<fixture>"))
                time.sleep(0.1)

    @staticmethod
    def stop_process(process):
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def api(self, endpoint, **params):
        query = urllib.parse.urlencode(params)
        with urllib.request.urlopen(f"http://127.0.0.1:{self.loki}/loki/api/v1/{endpoint}?{query}", timeout=10) as response:
            result = json.load(response)
        self.assertEqual(result["status"], "success")
        return result["data"]

    def query_rows(self, query):
        data = self.api("query_range", query=query, start=str(self.start), end=str(time.time_ns()),
                        direction="forward", limit="100")
        return [row for stream in data["result"] for row in stream["values"]]

    def test_runs_costs_and_tool_joins_survive_into_loki_as_metadata(self):
        self.start = time.time_ns() - 1_000_000_000
        resources, expected = [], {}
        cases = [
            ("synthetic-run", "wf_synthetic_a", "synthetic-session-a", "100", "0.0125"),
            ("synthetic-run", "wf_synthetic_b", "synthetic-session-b", "200", 0.025),
            ("synthetic-run.B.task.1", None, "synthetic-session-c", "0", 0.0),
            ("synthetic-run-other.B.task.1", None, "synthetic-session-d", "999", "0.1"),
        ]
        for run, workflow, session, tokens, cost in cases:
            common = {"session.id": session, "ecosystem.task.id": run}
            if workflow is not None:
                common["workflow.run_id"] = workflow
            records = [
                {"event.name": "api_request", "model": "synthetic-model", "input_tokens": tokens,
                 "output_tokens": "3", "cache_read_tokens": "4", "cache_creation_tokens": "5", "cost_usd": cost},
                {"event.name": "tool_decision", "tool_name": "Read", "decision": "accept", "tool_use_id": "toolu_synthetic"},
                {"event.name": "tool_result", "tool_name": "Read", "success": "true", "tool_use_id": "toolu_synthetic"},
            ]
            logs = []
            for record in records:
                attrs = {**common, **record, "prompt": self.SECRET, "tool_input": self.SECRET,
                         "user.email": self.SECRET}
                expected[(session, record["event.name"])] = {**common, **record}
                logs.append({"timeUnixNano": str(time.time_ns()), "body": {"stringValue": self.SECRET},
                             "attributes": otlp_attributes(attrs)})
            # Claude documents custom attributes on both the resource and each event record:
            # https://code.claude.com/docs/en/monitoring-usage#multi-team-organization-support
            resources.append({"resource": {"attributes": otlp_attributes({
                "service.name": "claude-code", "ecosystem.task.id": run, "user.id": self.SECRET,
            })}, "scopeLogs": [{"scope": {"name": "synthetic"}, "logRecords": logs}]})

        # Missing cost/run/tool fields must stay absent, not become zero or a fabricated identity.
        resources.append({"resource": {"attributes": otlp_attributes({"service.name": "claude-code"})},
                          "scopeLogs": [{"logRecords": [{"timeUnixNano": str(time.time_ns()),
                              "attributes": otlp_attributes({"event.name": "api_request"})}]}]})
        request = urllib.request.Request(f"http://127.0.0.1:{self.otlp}/v1/logs",
                                         data=json.dumps({"resourceLogs": resources}).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=10) as response:
            accepted = json.load(response)
        self.assertFalse(accepted.get("partialSuccess"), accepted)

        selector = '{service_name="claude-code"}'
        deadline = time.monotonic() + 30
        while True:
            rows = self.query_rows(selector)
            if len(rows) >= 13 or time.monotonic() >= deadline:
                break
            time.sleep(0.2)
        self.assertEqual(len(rows), 13, "all fixture events must reach Loki before reconciliation")
        self.assertEqual({row[1] for row in rows}, {"[content omitted]"})

        # Loki regex label filters include exact run IDs and dot-suffixed arms, but not adjacent runs.
        # https://grafana.com/docs/loki/latest/query/log_queries/#label-filter-expression
        whole_run = selector + r' | ecosystem_task_id=~"synthetic-run(\\..+)?"'
        self.assertEqual(len(self.query_rows(whole_run)), 9)
        self.assertEqual(len(self.query_rows(selector + ' | ecosystem_task_id="synthetic-run"')), 6)
        self.assertEqual(len(self.query_rows(selector + ' | ecosystem_task_id="synthetic-run.B.task.1"')), 3)

        for run, workflow, session, tokens, cost in cases:
            with self.subTest(session=session):
                run_query = selector + f' | ecosystem_task_id="{run}" | session_id="{session}"'
                if workflow:
                    run_query += f' | workflow_run_id="{workflow}"'
                else:
                    run_query += ' | workflow_run_id=""'
                self.assertEqual(len(self.query_rows(run_query)), 3)
                self.assertEqual(len(self.query_rows(run_query + ' | tool_use_id="toolu_synthetic"')), 2)
                price = format(cost, "g") if isinstance(cost, float) else cost
                self.assertEqual(len(self.query_rows(run_query + f' | event_name="api_request" | cost_usd="{price}"')), 1)

        grouped = self.api("query", query='sum by (workflow_run_id) (sum_over_time('
                           + selector + ' | ecosystem_task_id="synthetic-run" | event_name="api_request"'
                           + ' | unwrap input_tokens | __error__="" [5m]))', time=str(time.time_ns()))
        self.assertEqual({row["metric"]["workflow_run_id"]: float(row["value"][1]) for row in grouped["result"]},
                         {"wf_synthetic_a": 100.0, "wf_synthetic_b": 200.0})
        series = self.api("series", **{"match[]": selector, "start": str(self.start), "end": str(time.time_ns())})
        self.assertEqual(series, [{"service_name": "claude-code"}], "correlation and cost must not become index labels")

        deadline = time.monotonic() + 10
        while True:
            contents = self.output.read_text() if self.output.exists() else ""
            try:
                exported = [json.loads(line) for line in contents.splitlines()]
            except json.JSONDecodeError:
                exported = []  # The file exporter may still be finishing a line.
            records = [(group["resource"], record) for batch in exported for group in batch["resourceLogs"]
                       for scope in group["scopeLogs"] for record in scope["logRecords"]]
            if len(records) >= 13 or time.monotonic() >= deadline:
                break
            time.sleep(0.1)
        self.assertEqual(len(records), 13)
        self.assertNotIn(self.SECRET, contents)
        for resource, record in records:
            attrs = {a["key"]: next(iter(a["value"].values())) for a in record["attributes"]}
            if "session.id" in attrs:
                wanted = expected[(attrs["session.id"], attrs["event.name"])]
                for key, value in wanted.items():
                    self.assertEqual(attrs.get(key), value, key)
                resource_attrs = {a["key"]: next(iter(a["value"].values())) for a in resource["attributes"]}
                self.assertEqual(resource_attrs["ecosystem.task.id"], attrs["ecosystem.task.id"])
            else:
                for key in ("cost_usd", "tool_use_id", "workflow.run_id"):
                    self.assertNotIn(key, attrs)
                self.assertNotIn("ecosystem.task.id", [a["key"] for a in resource["attributes"]])

    def test_codex_arguments_are_removed_and_measurement_metadata_reaches_loki(self):
        self.start = time.time_ns() - 1_000_000_000
        # Codex rust-v0.157.1 tool_result.rs logs arguments even with max_bytes=0.
        # Its length counters are trace-branch fields: the second synthetic record
        # exercises retention when supplied, not a claim that native logs emit them.
        records = [
            {"tool_name": "exec_command", "tool_namespace": "functions", "mcp_server": "",
             "arguments": json.dumps({"cmd": self.SECRET}), "output_truncated": True},
            {"tool_name": "ctx_execute", "tool_namespace": "mcp__context_mode", "mcp_server": "context-mode",
             "arguments": json.dumps({"code": self.SECRET}), "output_truncated": False,
             "arguments_length": 31, "output_length": 47, "output_line_count": 2},
            {"tool_name": "ctx_stats", "tool_namespace": "mcp__context_mode",
             "arguments": self.SECRET, "output_truncated": True},
        ]
        common = {"event.name": "codex.tool_result", "duration_ms": "7", "success": "true",
                  "conversation.id": "synthetic-conversation", "thread.id": "synthetic-thread",
                  "turn.id": "synthetic-turn", "ecosystem.task.id": "synthetic-run.B.task.1"}
        logs = [{"timeUnixNano": str(time.time_ns() + i), "body": {"stringValue": self.SECRET},
                 "attributes": otlp_attributes({**common, **record, "output": self.SECRET})}
                for i, record in enumerate(records)]
        resource = {"service.name": "codex_exec", "ecosystem.task.id": "synthetic-run.B.task.1"}
        request = urllib.request.Request(f"http://127.0.0.1:{self.otlp}/v1/logs",
            data=json.dumps({"resourceLogs": [{"resource": {"attributes": otlp_attributes(resource)},
                             "scopeLogs": [{"logRecords": logs}]}]}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=10) as response:
            self.assertFalse(json.load(response).get("partialSuccess"))

        selector = '{service_name="codex_exec"}'
        deadline = time.monotonic() + 30
        while True:
            rows = self.query_rows(selector)
            if len(rows) >= len(records) or time.monotonic() >= deadline:
                break
            time.sleep(0.2)
        self.assertEqual(len(rows), len(records))
        self.assertNotIn(self.SECRET, json.dumps(rows))
        self.assertEqual({row[1] for row in rows}, {"[content omitted]"})
        deadline = time.monotonic() + 10
        while True:
            contents = self.output.read_text() if self.output.exists() else ""
            try:
                exported = [json.loads(line) for line in contents.splitlines()]
            except json.JSONDecodeError:
                exported = []
            output_records = [record for batch in exported for group in batch["resourceLogs"]
                              for scope in group["scopeLogs"] for record in scope["logRecords"]]
            if len(output_records) >= len(records) or time.monotonic() >= deadline:
                break
            time.sleep(0.1)
        self.assertEqual(len(output_records), len(records))
        self.assertNotIn(self.SECRET, contents)
        by_tool = {}
        for record in output_records:
            attrs = {a["key"]: next(iter(a["value"].values())) for a in record["attributes"]}
            by_tool[attrs["tool_name"]] = attrs
        for record in records:
            with self.subTest(tool=record["tool_name"]):
                query = selector + f' | tool_name="{record["tool_name"]}"'
                metadata = by_tool[record["tool_name"]]
                for key in ("arguments", "output", "mcp_server"):
                    self.assertNotIn(key, metadata)
                    query += f' | {key}=""'
                expected = {**common, **{key: value for key, value in record.items()
                                        if key not in ("arguments", "mcp_server")}}
                for key, value in expected.items():
                    formatted = str(value).lower() if isinstance(value, bool) else str(value)
                    self.assertEqual(metadata.get(key), value if isinstance(value, bool) else str(value), key)
                    query += f' | {key.replace(".", "_")}={json.dumps(formatted)}'
                if record.get("mcp_server"):
                    self.assertEqual(metadata.get("mcp_server.name"), record["mcp_server"])
                    query += f' | mcp_server_name="{record["mcp_server"]}"'
                else:
                    self.assertNotIn("mcp_server.name", metadata)
                    query += ' | mcp_server_name=""'
                for key in ("arguments_length", "output_length", "output_line_count"):
                    if key not in record:
                        self.assertNotIn(key, metadata)
                self.assertEqual(len(self.query_rows(query)), 1)
        # Namespace is sufficient for code-mode MCP calls whose server metadata is absent.
        self.assertEqual(len(self.query_rows(selector + ' | tool_namespace="mcp__context_mode"')), 2)
        series = self.api("series", **{"match[]": selector, "start": str(self.start), "end": str(time.time_ns())})
        self.assertEqual(series, [{"service_name": "codex_exec"}])


if __name__ == "__main__":
    unittest.main()
