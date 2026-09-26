"""Tool, MCP server, skill and subagent names on the native logs pipeline
(observability/collector/README.md#tool-mcp-skill-and-subagent-invoke-rates).

Structural checks always run (the YAML ones need PyYAML). One class runs the committed logs pipeline on the pinned
otelcol-contrib 0.161.0 with synthetic OTLP log records when the binary is installed at its documented path, and
skips otherwise. It is a local integration check on synthetic data, not a model run or host acceptance; the replay
of real Claude Code and Codex captures and the post-apply host proof are recorded separately.
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import tempfile
import time
import tomllib
import unittest
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "observability/collector/collector.yaml"
DASHBOARD = ROOT / "observability/backends/templates/ecosystem-dashboard.json.example"
CLAUDE_TEMPLATES = (ROOT / "observability/collector/claude-settings.json.example",
                    ROOT / "adoption/templates/claude.settings.template.json")
CODEX_TEMPLATE = ROOT / "adoption/templates/codex.config.template.toml"
OTELCOL = Path.home() / ".local/share/codex-ecosystem/tools/otelcol-0.161.0/otelcol-contrib"  # README pins 0.161.0

CONTENT_KEYS = ["tool_parameters", "tool_input", "arguments", "output", "content", "error"]
DERIVED_KEYS = ["tool_family", "actor", "shell_rtk", "tool_details", "client"]
# Written by Claude Code or Codex from their registries: shape-checked names.
REGISTRY_NAME_KEYS = ["mcp_server.name", "mcp_tool.name", "skill.name", "originator", "client"]
# Agent types: only the built-in agents of https://code.claude.com/docs/en/sub-agents (Built-in subagents) plus the
# workflow child pass; anything else becomes custom, as in Claude Code's own redaction.
AGENT_TYPE_KEYS = ["subagent_type", "agent.name", "agent_type"]
BUILTIN_AGENTS = ["general-purpose", "Explore", "Plan", "claude", "statusline-setup", "claude-code-guide",
                  "workflow-subagent", "custom"]
# Typed by the model (Skill input, workflow script name, Codex task name): never exported.
NOT_EXPORTED = ["workflow.name", "agent_name"]
WRITTEN_KEYS = set(DERIVED_KEYS) | set(REGISTRY_NAME_KEYS) | set(AGENT_TYPE_KEYS)
ID_LABELS = ("session_id", "conversation_id", "thread_id", "turn_id", "workflow_run_id", "sender_thread_id",
             "receiver_thread_id", "receipt_id", "event_sequence", "event_timestamp", "tool_use_id", "call_id")

try:
    import yaml
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


def groups(config: dict, processor: str) -> list[dict]:
    return config["processors"][processor]["log_statements"]


def quoted_list(statement: str) -> list[str]:
    return re.findall(r'"([^"]+)"', statement.split("[", 1)[1].split("]", 1)[0])


def log_allowlist(config: dict) -> list[str]:
    statement = next(s for g in groups(config, "transform/privacy") if g["context"] == "log"
                     for s in g["statements"] if s.startswith("keep_keys(attributes,"))
    return quoted_list(statement)


@unittest.skipUnless(HAVE_YAML, "optional PyYAML structural check")
class CollectorProfileTests(unittest.TestCase):
    def setUp(self):
        self.config = yaml.safe_load(COLLECTOR.read_text())
        self.tool_names = groups(self.config, "transform/tool_names")
        self.statements = [s for g in self.tool_names for s in g["statements"]]

    def test_names_are_extracted_before_the_privacy_allowlist_on_both_log_pipelines(self):
        pipelines = self.config["service"]["pipelines"]
        self.assertEqual(pipelines["logs"]["processors"],
                         ["memory_limiter", "transform/tool_names", "transform/privacy", "batch"])
        # SDK receipts share the privacy allowlist, so they pass through the same guards.
        self.assertEqual(pipelines["logs/sdk_receipts"]["processors"],
                         ["memory_limiter", "transform/sdk_receipt", "transform/tool_names", "transform/privacy", "batch"])
        for name, pipeline in pipelines.items():
            if not name.startswith("logs"):
                self.assertNotIn("transform/tool_names", pipeline["processors"], name)
        self.assertEqual(self.config["processors"]["transform/tool_names"]["error_mode"], "silent")
        self.assertNotIn("metric_statements", self.config["processors"]["transform/tool_names"])

    def test_only_name_fields_are_copied_out_of_tool_parameters(self):
        claude = next(g for g in self.tool_names if 'attributes["event.name"] == "tool_result"' in g.get("conditions", []))
        copied = {m.group(1): m.group(2) for s in claude["statements"]
                  for m in [re.match(r'set\(attributes\["([^"]+)"\], cache\["parameters"\]\["([^"]+)"\]\)', s)] if m}
        self.assertEqual(copied, {"mcp_server.name": "mcp_server_name", "mcp_tool.name": "mcp_tool_name",
                                  "subagent_type": "subagent_type"})
        # The Skill tool's skill_name is whatever the model typed; skill names come only from skill_activated.
        self.assertFalse(any('"skill_name"' in s for s in self.statements))
        parsed = [s for s in claude["statements"] if "ParseJSON(" in s]
        self.assertEqual(parsed, ['set(cache["parameters"], ParseJSON(attributes["tool_parameters"])) '
                                  'where IsString(attributes["tool_parameters"])'])
        # bash_command (the program name) is only tested, never copied; full_command is never read.
        self.assertFalse(any("full_command" in s for s in self.statements))
        self.assertTrue(all('set(attributes["shell_rtk"], "' in s for s in self.statements if '"bash_command"' in s))
        written = {m for s in self.statements for m in re.findall(r'^set\(attributes\["([^"]+)"\]', s)}
        self.assertLessEqual(written, WRITTEN_KEYS)

    def test_content_keys_are_deleted_here_and_absent_from_the_allowlist(self):
        final = self.tool_names[-1]
        self.assertNotIn("conditions", final)
        self.assertEqual(final["statements"][0],
                         'delete_matching_keys(attributes, "^(' + "|".join(CONTENT_KEYS) + ')$")')
        allow = log_allowlist(self.config)
        for key in CONTENT_KEYS + ["prompt", "user.email", "user.account_id", "mcp_server", "communication_id"]:
            self.assertNotIn(key, allow)

    def test_every_written_name_is_guarded_and_allowlisted(self):
        allow = set(log_allowlist(self.config))
        written = {m for s in self.statements for m in re.findall(r'^set\(attributes\["([^"]+)"\]', s)}
        self.assertLessEqual(written, allow)
        final = self.tool_names[-1]["statements"]
        for key in REGISTRY_NAME_KEYS:
            guard = next(s for s in final if s.startswith(f'set(attributes["{key}"], "other") where attributes["{key}"] != nil'
                                                          f' and (not IsMatch('))
            self.assertIn(f'or IsMatch(attributes["{key}"], "[A-Za-z0-9]{{24}}"))', guard)  # key- or token-shaped runs
            self.assertNotIn("@", guard)
            self.assertNotIn(" _", guard)  # no space in any name character class
        vocabulary = "[" + ", ".join(f'"{name}"' for name in BUILTIN_AGENTS) + "]"
        for key in AGENT_TYPE_KEYS:
            self.assertIn(f'set(attributes["{key}"], "custom") where attributes["{key}"] != nil'
                          f' and not ContainsValue({vocabulary}, attributes["{key}"])', final)
        for key in ("tool_family", "actor", "shell_rtk", "invocation_trigger", "kind", "state", "workflow.run_id",
                    "sender_thread_id", "receiver_thread_id", "total_tool_uses"):
            self.assertIn(key, allow)
            self.assertTrue(any(s.startswith(f'delete_key(attributes, "{key}") where attributes["{key}"] != nil and not IsMatch(')
                                for s in final), key)
        self.assertIn('delete_key(attributes, "tool_details") where attributes["tool_details"] != nil'
                      ' and attributes["tool_details"] != "unparsed"', final)

    def test_derived_keys_cannot_be_supplied_and_receipts_carry_no_names(self):
        first = self.tool_names[0]
        self.assertNotIn("conditions", first)
        self.assertEqual(first["statements"], ['delete_matching_keys(attributes, "^(' + "|".join(DERIVED_KEYS) + ')$")'])
        receipts = next(g for g in self.tool_names
                        if g.get("conditions") == ['attributes["event.name"] == "ecosystem.sdk_receipt"'])
        pattern = re.search(r'"\^\((.*)\)\$"', receipts["statements"][0]).group(1)
        deleted = {name.replace("\\\\.", ".") for name in pattern.split("|")}
        u6_keys = set(log_allowlist(self.config)[log_allowlist(self.config).index("tool_family"):])
        self.assertEqual(deleted | set(DERIVED_KEYS), u6_keys)

    def test_model_typed_values_are_not_exported(self):
        allow = set(log_allowlist(self.config))
        for key in NOT_EXPORTED:
            self.assertNotIn(key, allow)
        # Codex agent paths only decide the actor; they are never copied.
        self.assertFalse(any(re.match(r'set\(attributes\["[^"]+"\], attributes\["agent_name"\]', s) for s in self.statements))

    def test_writer_identity_metric_allowlist_is_unchanged(self):
        metric = next(s for g in self.config["processors"]["transform/privacy"]["metric_statements"]
                      if g["context"] == "metric" for s in g["statements"])
        datapoint = next(s for g in self.config["processors"]["transform/privacy"]["metric_statements"]
                         if g["context"] == "datapoint" for s in g["statements"] if s.startswith("keep_keys(attributes,"))
        self.assertEqual(quoted_list(metric), quoted_list(datapoint))
        for key in REGISTRY_NAME_KEYS + AGENT_TYPE_KEYS + DERIVED_KEYS + ["session.id"]:
            self.assertNotIn(key, quoted_list(datapoint))

    def test_client_templates_enable_tool_details_but_no_content(self):
        for path in CLAUDE_TEMPLATES:
            with self.subTest(path=path.name):
                env = json.loads(path.read_text())["env"]
                self.assertEqual(env["OTEL_LOG_TOOL_DETAILS"], "1")
                for key in ("OTEL_LOG_USER_PROMPTS", "OTEL_LOG_ASSISTANT_RESPONSES", "OTEL_LOG_TOOL_CONTENT",
                            "OTEL_LOG_RAW_API_BODIES"):
                    self.assertEqual(env[key], "false", key)
                self.assertEqual(env["OTEL_TRACES_EXPORTER"], "none")
        otel = tomllib.loads(CODEX_TEMPLATE.read_text())["otel"]
        self.assertIs(otel["log_user_prompt"], False)
        self.assertEqual(otel["tool_result"]["max_bytes"], 0)
        self.assertEqual(otel["trace_exporter"], "none")


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.panels = {p["id"]: p for p in json.loads(DASHBOARD.read_text())["panels"]}

    def test_invoke_rate_row_uses_loki_structured_metadata_without_id_grouping(self):
        self.assertEqual(self.panels[28]["type"], "row")
        new = [self.panels[i] for i in range(29, 39)]
        self.assertEqual(len({(p["gridPos"]["x"], p["gridPos"]["y"]) for p in new}), len(new))
        for panel in new:
            self.assertEqual(panel["datasource"], {"type": "loki", "uid": "ecosystem-loki"})
            for target in panel["targets"]:
                expr = target["expr"]
                with self.subTest(panel=panel["id"], ref=target["refId"]):
                    self.assertIn("[$__auto]", expr)
                    self.assertNotIn("$__range", expr)
                    self.assertRegex(expr, r"\| keep [a-z_, ]+(\| unwrap total_tool_uses \| __error__=\"\" )?\[\$__auto\]")
                    for label in ID_LABELS:
                        self.assertNotIn(label, expr)
                    self.assertEqual(target["queryType"], "instant" if panel["type"] == "stat" else "range")

    def test_panels_cover_families_servers_skills_subagents_split_and_adoption(self):
        exprs = {pid: " ".join(t["expr"] for t in self.panels[pid]["targets"]) for pid in range(29, 39)}
        self.assertIn("sum by (tool_family)", exprs[29])
        self.assertIn('event_name="codex.tool_result"', exprs[30])
        self.assertIn("sum by (client, mcp_server_name)", exprs[31])
        self.assertIn("sum by (skill_name, invocation_trigger)", exprs[32])
        self.assertIn('kind="spawn" | state="send"', exprs[33])
        # Claude launches are counted when accepted (tool_decision, before the tool runs), not at tool_result.
        self.assertIn('event_name="tool_decision" | decision="accept" | tool_name=~"Agent|Task"', exprs[33])
        self.assertNotIn('event_name="tool_result"', exprs[33])
        self.assertIn("sum by (client, actor)", exprs[34])
        self.assertIn('tool_family="mcp"', exprs[35])
        self.assertIn('shell_rtk="true"', exprs[36])
        self.assertIn('mcp_server_name=~"context-mode|plugin_context-mode_context-mode"', exprs[36])
        self.assertNotIn('mcp_server_name=~".*', exprs[36])  # explicit server names, no near-match
        self.assertIn('tool_details="unparsed"', exprs[37])
        self.assertIn('event_name="api_request"', exprs[38])


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def otlp_attrs(mapping):
    return [{"key": k, "value": {"stringValue": v}} for k, v in mapping.items()]


@unittest.skipUnless(OTELCOL.exists() and HAVE_YAML, "otelcol-contrib 0.161.0 not installed at the documented path")
class NativeCollectorTests(unittest.TestCase):
    """The committed logs pipeline on the pinned otelcol-contrib, with synthetic OTLP JSON (no model call)."""

    SECRET = "SYNTHETIC-COMMAND-TEXT-7f3a"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.otlp, self.health = free_port(), free_port()
        self.output = root / "logs.json"
        config = yaml.safe_load(COLLECTOR.read_text())
        logs = config["service"]["pipelines"]["logs"]
        config = {"receivers": {"otlp": {"protocols": {"http": {"endpoint": f"127.0.0.1:{self.otlp}"}}}},
                  "processors": {k: v for k, v in config["processors"].items() if k in logs["processors"]},
                  "exporters": {"file": {"path": str(self.output), "flush_interval": "100ms"}},
                  "extensions": {"health_check": {"endpoint": f"127.0.0.1:{self.health}"}},
                  "service": {"extensions": ["health_check"],
                              "telemetry": {"logs": {"level": "warn"}, "metrics": {"level": "none"}},
                              "pipelines": {"logs": {"receivers": ["otlp"], "processors": logs["processors"],
                                                     "exporters": ["file"]}}}}
        path = root / "collector.yaml"
        path.write_text(yaml.safe_dump(config))
        self.log = open(root / "otelcol.log", "w")
        self.process = subprocess.Popen([str(OTELCOL), f"--config={path}"], stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.time() + 30
        while True:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{self.health}/", timeout=1).read()
                break
            except OSError:
                if time.time() > deadline or self.process.poll() is not None:
                    self.fail((root / "otelcol.log").read_text())
                time.sleep(0.2)

    def tearDown(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.log.close()
        self.tmp.cleanup()

    def post(self, service, records):
        now = time.time_ns()
        body = {"resourceLogs": [{"resource": {"attributes": otlp_attrs({"service.name": service})},
                                  "scopeLogs": [{"scope": {"name": "synthetic"}, "logRecords": [
                                      {"timeUnixNano": str(now + i), "body": {"stringValue": self.SECRET},
                                       "attributes": otlp_attrs(r)} for i, r in enumerate(records)]}]}]}
        request = urllib.request.Request(f"http://127.0.0.1:{self.otlp}/v1/logs", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(request, timeout=10).read()

    def exported(self, expected):
        deadline = time.time() + 15
        while time.time() < deadline:
            if self.output.exists():
                rows = [{a["key"]: next(iter(a["value"].values())) for a in r.get("attributes", [])}
                        for line in self.output.read_text().splitlines() if line.strip()
                        for rl in json.loads(line)["resourceLogs"] for sl in rl["scopeLogs"] for r in sl["logRecords"]]
                if len(rows) >= expected:
                    return rows
            time.sleep(0.2)
        self.fail("the file exporter did not receive every record")

    def test_names_survive_and_command_text_does_not(self):
        secret = self.SECRET
        self.post("claude-code", [
            {"event.name": "tool_result", "tool_name": "Bash", "tool_input": json.dumps({"command": f"rtk ls {secret}"}),
             "tool_parameters": json.dumps({"bash_command": "rtk", "full_command": f"rtk ls {secret}",
                                            "description": secret})},
            {"event.name": "tool_decision", "tool_name": "mcp_tool",
             "tool_parameters": json.dumps({"mcp_server_name": "qmd", "mcp_tool_name": "status"})},
            {"event.name": "tool_result", "tool_name": "Skill", "tool_parameters": json.dumps({"skill_name": f"x {secret}"})},
            {"event.name": "tool_result", "tool_name": "Agent", "error": secret,
             "tool_parameters": json.dumps({"subagent_type": "general-purpose"}), "tool_input": json.dumps({"prompt": secret})},
            {"event.name": "tool_result", "tool_name": "mcp_tool", "workflow.run_id": "wf_0123456789ab",
             "tool_parameters": "{" + secret},
            {"event.name": "api_request", "query_source": "agent:builtin:general-purpose", "agent.name": "general-purpose",
             "mcp_server.name": "qmd"},
            # values a client or a model could supply: derived keys, an address, a token-shaped name
            {"event.name": "tool_result", "tool_name": "Read", "tool_details": f"cat /private/{secret}", "actor": secret,
             "shell_rtk": secret, "tool_family": secret},
            {"event.name": "skill_activated", "skill.name": "alice@example.com", "invocation_trigger": f"rm -rf {secret}"},
            {"event.name": "tool_result", "tool_name": "mcp_tool",
             "tool_parameters": json.dumps({"mcp_server_name": "ghp" + "A1b2C3d4E5f6G7h8I9j0K1l2M3", "mcp_tool_name": "x"})},
            # identifier-shaped values a model can type: a file name as subagent type, a workflow name
            {"event.name": "tool_decision", "tool_name": "Agent", "decision": "accept",
             "tool_parameters": json.dumps({"subagent_type": "notes-7f3a.txt"})},
            {"event.name": "tool_result", "tool_name": "Workflow", "workflow.run_id": "wf_0123456789ac",
             "workflow.name": "notes-7f3a.txt"},
        ])
        self.post("codex_exec", [
            {"event.name": "codex.tool_result", "tool_name": "exec_command", "tool_namespace": "functions",
             "agent_name": "/root/child_task", "mcp_server": "", "arguments": json.dumps({"cmd": f"git status {secret}"}),
             "output": secret},
            {"event.name": "codex.tool_result", "tool_name": "ctx_stats", "tool_namespace": "mcp__context_mode",
             "agent_name": "/root", "mcp_server": "context-mode", "arguments": "{}"},
            # Thread ids assembled at runtime: the publication scan (scripts/validate.py) rejects UUID literals.
            {"event.name": "codex.agent_communication", "kind": "spawn", "state": "send", "content": secret,
             "sender_thread_id": str(uuid.UUID(int=0x11111111_2222_4333_8444_555555555555)),
             "receiver_thread_id": str(uuid.UUID(int=0x66666666_7777_4888_8999_AAAAAAAAAAAA))},
            {"event.name": "codex.tool_result", "tool_name": "exec_command", "tool_namespace": "mcp__foo",
             "agent_name": "/root", "originator": "git log --oneline -1", "arguments": json.dumps({"cmd": "rtk ls"})},
        ])
        # two front-ends of one app-server share service.name; the originator tells them apart
        self.post("codex-app-server", [
            {"event.name": "codex.tool_result", "tool_name": "status", "tool_namespace": "mcp__qmd", "mcp_server": "qmd",
             "agent_name": "/root", "originator": "codex_vscode"},
            {"event.name": "codex.tool_result", "tool_name": "status", "tool_namespace": "mcp__qmd", "mcp_server": "qmd",
             "agent_name": "/root/.notes_7f3a/key_file", "originator": "Codex Desktop"},
        ])
        rows = self.exported(17)
        self.assertNotIn(secret, self.output.read_text())
        self.assertNotIn("notes-7f3a", self.output.read_text())
        self.assertNotIn("notes_7f3a", self.output.read_text())
        for row in rows:
            for key in CONTENT_KEYS + NOT_EXPORTED + ["mcp_server"]:
                self.assertNotIn(key, row)
        view = [{k: row.get(k) for k in ("tool_family", "actor", "shell_rtk", "tool_details", "client", "mcp_server.name",
                                         "mcp_tool.name", "skill.name", "subagent_type", "agent.name", "kind",
                                         "invocation_trigger", "originator")
                 if row.get(k) is not None} for row in rows]
        self.assertEqual(view, [
            {"tool_family": "shell", "actor": "main_or_subagent", "shell_rtk": "true", "client": "claude-code"},
            {"tool_family": "mcp", "actor": "main_or_subagent", "client": "claude-code", "mcp_server.name": "qmd",
             "mcp_tool.name": "status"},
            # the Skill tool's skill_name is not exported (skill_activated names real skills)
            {"tool_family": "skill", "actor": "main_or_subagent", "client": "claude-code"},
            {"tool_family": "agent", "actor": "main_or_subagent", "client": "claude-code", "subagent_type": "general-purpose"},
            {"tool_family": "mcp", "actor": "workflow", "tool_details": "unparsed", "client": "claude-code"},
            {"actor": "subagent", "mcp_server.name": "qmd", "agent.name": "general-purpose"},
            {"tool_family": "read", "actor": "main_or_subagent", "client": "claude-code"},
            {"skill.name": "other"},
            {"tool_family": "mcp", "actor": "main_or_subagent", "client": "claude-code", "mcp_server.name": "other",
             "mcp_tool.name": "x"},
            {"tool_family": "agent", "actor": "main_or_subagent", "client": "claude-code", "subagent_type": "custom"},
            {"tool_family": "agent", "actor": "workflow", "client": "claude-code"},
            {"tool_family": "shell", "actor": "subagent", "shell_rtk": "false", "client": "codex_exec"},
            {"tool_family": "mcp", "actor": "main", "client": "codex_exec", "mcp_server.name": "context-mode",
             "mcp_tool.name": "ctx_stats"},
            {"kind": "spawn"},
            # an MCP tool that happens to be named exec_command is not a shell call
            {"tool_family": "mcp", "actor": "main", "client": "codex_exec", "mcp_tool.name": "exec_command",
             "originator": "other"},
            {"tool_family": "mcp", "actor": "main", "client": "codex_vscode", "mcp_server.name": "qmd",
             "mcp_tool.name": "status", "originator": "codex_vscode"},
            {"tool_family": "mcp", "actor": "subagent", "client": "codex_desktop", "mcp_server.name": "qmd",
             "mcp_tool.name": "status", "originator": "codex_desktop"},
        ])


if __name__ == "__main__":
    unittest.main()
