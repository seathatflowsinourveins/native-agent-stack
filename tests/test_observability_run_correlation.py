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

Codex launch tag and call ids (reviewed 2026-09-29, openai/codex rust-v0.157.1 = 36650394):
- codex-rs/otel/src/provider.rs:53,360-389: otel.environment becomes the resource
  attribute env (codex-rs/config/src/types.rs:52,605-606; codex-rs/core/src/otel_init.rs:88)
- codex-rs/otel/src/tool_result.rs:61 and codex-rs/otel/src/events/session_telemetry.rs:1112,1121:
  call_id on codex.tool_result and codex.tool_decision
- codex-rs/core/src/tools/code_mode/delegate.rs:323 with codex-rs/code-mode-protocol/src/lib.rs:51:
  nested code-mode calls get exec-<uuid v4> ids
- codex-rs/core/src/agent_communication.rs:44-66: spawn events carry no conversation.id
- open-telemetry/opentelemetry-collector-contrib v0.161.0, pkg/ottl/ottlfuncs/README.md
  (delete_key; IsMatch uses regexp.MatchString and returns false for nil)

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
import uuid
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

# Codex launch-tag and call-id guards: the registry-name character class, at most 128 characters.
ENV_GUARD = ('delete_key(attributes, "env") where attributes["env"] != nil and not IsMatch(attributes["env"], '
             '"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")')
CALL_ID_GUARD = ('delete_key(attributes, "call_id") where attributes["call_id"] != nil and not IsMatch('
                 'attributes["call_id"], "^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")')


def keep_list(section: str) -> list[str]:
    """The first keep_keys(attributes, [...]) list in a section, located with str.index (a linear scan)."""
    start = section.index("keep_keys(attributes, [") + len("keep_keys(attributes, ")
    return json.loads(section[start:section.index("]", start) + 1])


def statement_lines(section: str) -> list[str]:
    """Statement-depth YAML list items of one transform group, without comments (line scan, no regex)."""
    return [line[len("          - "):] for line in section.splitlines() if line.startswith("          - ")]


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

    def test_codex_launch_tag_and_call_id_are_kept(self):
        # Codex exports otel.environment as the logs resource attribute env (provider.rs:53,381) and call_id on
        # codex.tool_result and codex.tool_decision (tool_result.rs:61; session_telemetry.rs:1112,1121).
        text = COLLECTOR.read_text()
        # The call_id guard must sit in the last transform/tool_names group, which has no conditions, so it applies
        # to every log record. A guard in a conditioned group would let call_id on other events pass unchecked.
        tool_names = text.partition("  transform/tool_names:\n")[2].partition("  transform/privacy:\n")[0]
        final = tool_names.rpartition("      - context: log\n")[2]
        with self.subTest(check="call_id shape guard in the last, unconditioned transform/tool_names group"):
            self.assertEqual([line for line in final.splitlines() if line.lstrip().startswith("conditions:")], [])
            self.assertIn(CALL_ID_GUARD, statement_lines(final))
        privacy = text.partition("  transform/privacy:\n")[2]
        logs, _, metrics = privacy.partition("    metric_statements:\n")
        metrics = metrics.partition("  delta_to_cumulative:\n")[0]
        resource = logs.partition("      - context: scope\n")[0]
        records = logs.partition("      - context: log\n")[2]
        statements = statement_lines(resource)
        keep = next(i for i, s in enumerate(statements) if s.startswith("keep_keys(attributes, ["))
        with self.subTest(check="env shape guard before the resource allowlist"):
            self.assertIn(ENV_GUARD, statements[:keep])
        resource_keys = keep_list(resource)
        with self.subTest(check="resource allowlist keeps env but not host.name"):
            self.assertIn("env", resource_keys)
            self.assertNotIn("host.name", resource_keys)
        log_keys = keep_list(records)
        with self.subTest(check="log allowlist keeps call_id right after tool_use_id"):
            self.assertEqual(log_keys[log_keys.index("tool_use_id") + 1], "call_id")
        for key in ("env", "call_id"):
            with self.subTest(check="metric statements never keep it", key=key):
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

    def test_codex_launch_tag_and_call_id_reach_loki(self):
        """The launch tag (resource env) and call ids join Codex records in Loki; malformed values are dropped."""
        self.maxDiff = None  # Report every observed count on failure.
        self.start = time.time_ns() - 1_000_000_000
        tag = "synthetic-run.B.task.1"
        # call_ plus 24 letters/digits for model calls; exec-<uuid v4> for nested code-mode calls. UUIDs are
        # assembled at runtime: the publication scan (scripts/validate.py) rejects UUID literals.
        model_call = "call_" + "SyntheticCallIdentifier1"
        nested_call = f"exec-{uuid.UUID(int=0xAAAAAAAA_BBBB_4CCC_8DDD_EEEEEEEEEEEE)}"
        longest_call = "call_" + "b" * 123  # 128 characters: the guard's upper bound
        untagged_call = "call_" + "SecondResourceIdentifier"
        receipt_call = "call_" + "SdkReceiptIdentifier1"  # an SDK receipt file must never export a call id
        dropped = {"129-character id": "call_" + "d" * 124, "id with spaces": "call id with spaces",
                   "tag with spaces": "synthetic run B", "host name": "synthetic-host-name", "content": self.SECRET,
                   "SDK receipt call id": receipt_call}
        result = {"event.name": "codex.tool_result", "conversation.id": "synthetic-conversation",
                  "tool_name": "exec_command", "tool_namespace": "functions", "duration_ms": "3", "success": "true",
                  "arguments": json.dumps({"cmd": self.SECRET}), "output": self.SECRET}
        tagged = [
            {"event.name": "codex.tool_decision", "conversation.id": "synthetic-conversation",
             "tool_name": "exec_command", "tool_namespace": "functions", "call_id": model_call,
             "decision": "approved", "source": "config"},
            {**result, "call_id": model_call},
            {**result, "call_id": nested_call},
            {**result, "call_id": longest_call},
            {**result, "call_id": dropped["129-character id"]},
            {**result, "call_id": dropped["id with spaces"]},
            {"event.name": "codex.agent_communication", "kind": "spawn", "state": "send", "content": self.SECRET,
             "sender_thread_id": str(uuid.UUID(int=0x11111111_2222_4333_8444_555555555555)),
             "receiver_thread_id": str(uuid.UUID(int=0x66666666_7777_4888_8999_AAAAAAAAAAAA))},
        ]
        # Codex's logs resource: service.name, service.version, env and host.name (provider.rs:360-389).
        resources = [
            ({"service.name": "codex_exec", "service.version": "0.157.1", "env": tag,
              "host.name": dropped["host name"]}, tagged),
            ({"service.name": "codex_exec", "service.version": "0.157.1", "env": dropped["tag with spaces"]},
             [{**result, "call_id": untagged_call}]),
            ({"service.name": "codex-sdk-receipt", "ecosystem.client.scope": "sdk-receipt"},
             [{"event.name": "ecosystem.sdk_receipt", "receipt_id": "synthetic-sdk", "call_id": receipt_call}]),
        ]
        body = {"resourceLogs": [
            {"resource": {"attributes": otlp_attributes(attributes)},
             "scopeLogs": [{"scope": {"name": "synthetic"}, "logRecords": [
                 {"timeUnixNano": str(time.time_ns() + i), "body": {"stringValue": self.SECRET},
                  "attributes": otlp_attributes(record)} for i, record in enumerate(records)]}]}
            for attributes, records in resources]}
        request = urllib.request.Request(f"http://127.0.0.1:{self.otlp}/v1/logs", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=10) as response:
            self.assertFalse(json.load(response).get("partialSuccess"))

        selector = '{service_name="codex_exec"}'
        deadline = time.monotonic() + 30
        receipts = '{service_name="codex-sdk-receipt"}'
        while (len(self.query_rows(selector)) < 8 or len(self.query_rows(receipts)) < 1) and time.monotonic() < deadline:
            time.sleep(0.2)
        launch = selector + f' | env="{tag}"'
        results = launch + ' | event_name="codex.tool_result"'
        queries = {
            "all records": selector,
            "records with the launch tag": launch,
            "tagged spawn event without conversation_id":
                launch + ' | event_name="codex.agent_communication" | conversation_id=""',
            "tagged decision for the model call": launch + f' | event_name="codex.tool_decision" | call_id="{model_call}"',
            "tagged result for the model call": results + f' | call_id="{model_call}"',
            "tagged result for the nested call": results + f' | call_id="{nested_call}"',
            "tagged result for the 128-character id": results + f' | call_id="{longest_call}"',
            "tagged results whose call_id was dropped": results + ' | call_id=""',
            "records without a launch tag": selector + ' | env=""',
            "untagged result keeping its call_id": selector + f' | env="" | call_id="{untagged_call}"',
            "SDK receipts": receipts,
            "SDK receipts without a call id": receipts + ' | call_id=""',
        }
        observed = {name: len(self.query_rows(query)) for name, query in queries.items()}
        self.assertEqual(observed, {
            "all records": 8, "records with the launch tag": 7, "tagged spawn event without conversation_id": 1,
            "tagged decision for the model call": 1, "tagged result for the model call": 1,
            "tagged result for the nested call": 1, "tagged result for the 128-character id": 1,
            "tagged results whose call_id was dropped": 2, "records without a launch tag": 1,
            "untagged result keeping its call_id": 1, "SDK receipts": 1, "SDK receipts without a call id": 1,
        })
        loki = json.dumps(self.api("query_range", query='{service_name=~"codex_exec|codex-sdk-receipt"}',
                                   start=str(self.start), end=str(time.time_ns()),
                                   direction="forward", limit="100"))
        for name, value in dropped.items():
            with self.subTest(dropped=name, sink="Loki"):
                self.assertFalse(value in loki, f"{name} reached Loki")
        series = self.api("series", **{"match[]": selector, "start": str(self.start), "end": str(time.time_ns())})
        self.assertEqual(series, [{"service_name": "codex_exec"}], "the tag and call ids must not become index labels")

        deadline = time.monotonic() + 10
        while True:
            contents = self.output.read_text() if self.output.exists() else ""
            try:
                exported = [json.loads(line) for line in contents.splitlines()]
            except json.JSONDecodeError:
                exported = []  # The file exporter may still be finishing a line.
            exported_records = [(group["resource"], record) for batch in exported for group in batch["resourceLogs"]
                                for scope in group["scopeLogs"] for record in scope["logRecords"]]
            if len(exported_records) >= 9 or time.monotonic() >= deadline:
                break
            time.sleep(0.1)
        self.assertEqual(len(exported_records), 9)
        for name, value in dropped.items():
            with self.subTest(dropped=name, sink="event file"):
                self.assertFalse(value in contents, f"{name} reached the event file")
        # Name the kept values so a failure prints no fixture identifier.
        names = {tag: "launch tag", model_call: "model call", nested_call: "nested call",
                 longest_call: "128-character id", untagged_call: "untagged call"}
        kept = {}
        for resource, record in exported_records:
            env = {a["key"]: next(iter(a["value"].values())) for a in resource["attributes"]}.get("env")
            attrs = {a["key"]: next(iter(a["value"].values())) for a in record["attributes"]}
            key = (names.get(env, env and "unexpected"), attrs.get("event.name"),
                   names.get(attrs.get("call_id"), attrs.get("call_id") and "unexpected"))
            kept[key] = kept.get(key, 0) + 1
        self.assertEqual(kept, {
            ("launch tag", "codex.tool_decision", "model call"): 1,
            ("launch tag", "codex.tool_result", "model call"): 1,
            ("launch tag", "codex.tool_result", "nested call"): 1,
            ("launch tag", "codex.tool_result", "128-character id"): 1,
            ("launch tag", "codex.tool_result", None): 2,
            ("launch tag", "codex.agent_communication", None): 1,
            (None, "codex.tool_result", "untagged call"): 1,
            (None, "ecosystem.sdk_receipt", None): 1,
        })


if __name__ == "__main__":
    unittest.main()
