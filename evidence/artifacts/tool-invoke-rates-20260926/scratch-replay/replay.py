"""u6 replay harness (run with: uv run -q --no-project --with pyyaml python replay.py <command> ...).

Commands
  build-config  derive a scratch logs-only Collector config from the staged collector.yaml: the logs pipeline's
                processors are copied verbatim; receivers/exporters/extensions/telemetry are scratch-only.
  post          replay OTLP/JSON export lines (file exporter format) to the scratch OTLP HTTP receiver, tagging each
                record with an allowlisted receipt_id for matching; optionally append synthetic sentinel records.
  assert        compare the exported file with the inputs; prints PASS/FAIL per assertion.
  loki          run the staged dashboard's new Loki targets against a scratch Loki and compare with the exported file.

Output never prints attribute values of content keys; only keys, counts and bounded name values.
"""
from __future__ import annotations

import argparse
import collections
import copy
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

PRODUCTION_PORTS = {"13000", "13100", "19090", "19095", "24317", "24318", "24333", "28888", "28889"}
CONTENT_KEYS = {"tool_parameters", "tool_input", "arguments", "output", "content", "error", "prompt", "response",
                "full_command", "bash_command", "user.email", "user.account_id", "user.account_uuid", "user.id",
                "organization.id", "cmd", "description", "script", "message"}
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
TOKEN_RUN = re.compile(r"[A-Za-z0-9]{24}")  # a key- or token-shaped run is never a name
# Written by Claude Code or Codex from their registries: shape-checked, else "other".
REGISTRY_NAME_KEYS = ["mcp_server.name", "mcp_tool.name", "skill.name", "originator", "client"]
# Agent types: the built-in agents of https://code.claude.com/docs/en/sub-agents ("Built-in subagents", fetched
# 2026-09-26) plus the workflow child seen in the probes, and Claude Code's own redacted value; else "custom".
AGENT_TYPE_KEYS = ["subagent_type", "agent.name", "agent_type"]
BUILTIN_AGENTS = {"general-purpose", "Explore", "Plan", "claude", "statusline-setup", "claude-code-guide",
                  "workflow-subagent", "custom"}
# Typed by the model (the Skill tool's skill_name is simply not copied; these two input keys are never exported).
NOT_EXPORTED = ["workflow.name", "agent_name"]
NAME_KEYS = REGISTRY_NAME_KEYS + AGENT_TYPE_KEYS
DERIVED_KEYS = ["tool_family", "actor", "shell_rtk", "tool_details"] + NAME_KEYS + NOT_EXPORTED + [
    "workflow.run_id", "kind", "state", "sender_thread_id", "receiver_thread_id", "total_tool_uses",
    "invocation_trigger"]
SENTINEL = "U6SENTINEL"
HISTORICAL_CAPTURE_FILES = {"claude-A-logs.json", "claude-B-logs.json", "claude-C-logs.json", "codex-logs.json"}

results = {"pass": 0, "fail": 0}


def check(name: str, ok: bool, detail: str = "") -> None:
    results["pass" if ok else "fail"] += 1
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" :: {detail}" if detail else ""))


# ---------------------------------------------------------------- OTLP/JSON helpers
def value_of(v: dict):
    if not v:
        return None
    kind, inner = next(iter(v.items()))
    if kind == "arrayValue":
        return [value_of(x) for x in inner.get("values", [])]
    if kind == "kvlistValue":
        return {x["key"]: value_of(x["value"]) for x in inner.get("values", [])}
    if kind == "intValue":
        return int(inner)
    return inner


def attrs(items: list) -> dict:
    return {a["key"]: value_of(a["value"]) for a in items or []}


def to_otlp_value(v):
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}
    return {"stringValue": str(v)}


def records(path: Path):
    """Yield (resource attrs, scope name, record dict, record attrs) for every log record in an export file."""
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        for rl in json.loads(line).get("resourceLogs", []):
            resource = attrs(rl.get("resource", {}).get("attributes"))
            for sl in rl.get("scopeLogs", []):
                for record in sl.get("logRecords", []):
                    yield resource, sl.get("scope", {}).get("name"), record, attrs(record.get("attributes"))


# ---------------------------------------------------------------- build-config
def build_config(args) -> None:
    config = yaml.safe_load(Path(args.collector).read_text())
    logs = config["service"]["pipelines"]["logs"]
    processors = {name: config["processors"][name] for name in logs["processors"]}
    exporters = {"file/replay": {"path": args.file, "flush_interval": "200ms"}}
    pipeline_exporters = ["file/replay"]
    if args.loki_port:
        exporters["otlphttp/scratchloki"] = {"endpoint": f"http://127.0.0.1:{args.loki_port}/otlp",
                                             "sending_queue": {"enabled": False},
                                             "retry_on_failure": {"enabled": True, "max_elapsed_time": "60s"}}
        pipeline_exporters.append("otlphttp/scratchloki")
    scratch = {
        "receivers": {"otlp": {"protocols": {"http": {"endpoint": f"127.0.0.1:{args.otlp_port}"}}}},
        "processors": processors,
        "exporters": exporters,
        "extensions": {"health_check": {"endpoint": f"127.0.0.1:{args.health_port}"}},
        "service": {"extensions": ["health_check"],
                    "telemetry": {"logs": {"level": "warn"}, "metrics": {"level": "none"}},
                    "pipelines": {"logs": {"receivers": ["otlp"], "processors": list(logs["processors"]),
                                           "exporters": pipeline_exporters}}},
    }
    if args.receipts_dir:
        # The staged SDK-receipt pipeline (file receiver -> transform/sdk_receipt -> tool_names -> privacy), reading
        # a scratch directory; the persistent storage extension is left out.
        receiver = copy.deepcopy(config["receivers"]["file_log/sdk_receipts"])
        receiver["include"] = [f"{args.receipts_dir}/*.json"]
        receiver.pop("storage", None)
        receipts = config["service"]["pipelines"]["logs/sdk_receipts"]
        scratch["receivers"]["file_log/sdk_receipts"] = receiver
        scratch["processors"].update({n: config["processors"][n] for n in receipts["processors"]})
        scratch["exporters"]["file/receipts"] = {"path": args.receipts_file, "flush_interval": "200ms"}
        scratch["service"]["pipelines"]["logs/sdk_receipts"] = {
            "receivers": ["file_log/sdk_receipts"], "processors": list(receipts["processors"]),
            "exporters": ["file/receipts"]}
        check("scratch config keeps the staged SDK-receipt processors verbatim, in order",
              list(receipts["processors"]) == ["memory_limiter", "transform/sdk_receipt", "transform/tool_names",
                                               "transform/privacy", "batch"]
              and all(scratch["processors"][n] == config["processors"][n] for n in receipts["processors"]),
              f"processors={receipts['processors']}")
    text = yaml.safe_dump(scratch, sort_keys=False, width=10_000)
    ports = set(re.findall(r"127\.0\.0\.1:(\d+)", text))
    Path(args.out).write_text(text)
    check("scratch config uses only scratch loopback ports (no production endpoint)",
          not (ports & PRODUCTION_PORTS) and all(45000 <= int(p) <= 45999 for p in ports),
          f"ports={sorted(ports)}")
    check("scratch config keeps the staged logs processors verbatim, in order",
          list(logs["processors"]) == ["memory_limiter", "transform/tool_names", "transform/privacy", "batch"]
          and all(processors[n] == config["processors"][n] for n in logs["processors"]),
          f"processors={logs['processors']}")


# ---------------------------------------------------------------- synthetic sentinel records
def synthetic_batches(now_ns: int) -> list[dict]:
    """Adversarial records that exercise every guard. Every content value carries the U6SENTINEL marker."""
    def rec(i, a):
        return {"timeUnixNano": str(now_ns + i * 1000), "observedTimeUnixNano": str(now_ns + i * 1000),
                "body": {"stringValue": f"synthetic {SENTINEL} body"},
                "attributes": [{"key": k, "value": to_otlp_value(v)} for k, v in a.items()]}

    tp = json.dumps
    claude = [
        {"event.name": "tool_result", "tool_name": "Bash", "success": "false",
         "tool_parameters": tp({"bash_command": "rtk", "full_command": f"rtk git status {SENTINEL}-full-command-1",
                                "description": f"{SENTINEL}-description-1", "timeout": 1000}),
         "tool_input": tp({"command": f"rtk git status {SENTINEL}-tool-input-1"}), "error": f"{SENTINEL}-error-1",
         "user.email": f"{SENTINEL}@example.invalid"},
        {"event.name": "tool_result", "tool_name": "Bash",
         "tool_parameters": tp({"bash_command": "git", "full_command": f"git log {SENTINEL}-full-command-2"})},
        {"event.name": "tool_result", "tool_name": "mcp_tool",
         "tool_parameters": tp({"mcp_server_name": "qmd", "mcp_tool_name": "query"}),
         "tool_input": tp({"searches": f"{SENTINEL}-mcp-args /srv/example/someone-private"})},
        {"event.name": "tool_decision", "tool_name": "Skill", "decision": "accept",
         "tool_parameters": tp({"skill_name": f"rm -rf /tmp/{SENTINEL}-skill"})},
        {"event.name": "tool_result", "tool_name": "Agent",
         "tool_parameters": tp({"subagent_type": "general-purpose"}),
         "tool_input": tp({"prompt": f"{SENTINEL}-subagent-prompt", "subagent_type": "general-purpose"})},
        {"event.name": "tool_result", "tool_name": "mcp_tool",
         "tool_parameters": '{"mcp_server_name": "qmd", ' + f"{SENTINEL}-malformed"},
        {"event.name": "tool_result", "tool_name": "Workflow", "workflow.run_id": "wf_abc123def456",
         "workflow.name": "otel-probe", "tool_input": tp({"script": f"{SENTINEL}-workflow-script"})},
        {"event.name": "tool_result", "tool_name": "mcp_tool",
         "tool_parameters": tp({"mcp_server_name": "server with space", "mcp_tool_name": f"{SENTINEL} tool"})},
        {"event.name": "api_request", "query_source": "agent:builtin:general-purpose", "agent.name": "general-purpose",
         "mcp_server.name": "qmd", "mcp_tool.name": "query", "model": "claude-haiku-4-5-20251001"},
        {"event.name": "api_request", "query_source": "agent_summary", "model": "claude-haiku-4-5-20251001"},
        # values a client, a file or a model could supply (review round): derived keys, an address, a token-shaped
        # name, an enumeration outside its set, and a server name that only resembles context-mode
        {"event.name": "tool_result", "tool_name": "Read", "tool_details": f"cat /private/{SENTINEL}-forged",
         "actor": f"{SENTINEL} actor", "shell_rtk": SENTINEL, "tool_family": SENTINEL},
        {"event.name": "skill_activated", "skill.name": f"{SENTINEL}@example.invalid",
         "invocation_trigger": f"rm -rf {SENTINEL}", "skill.source": "userSettings"},
        {"event.name": "tool_result", "tool_name": "mcp_tool",
         "tool_parameters": tp({"mcp_server_name": f"{SENTINEL}tokenA1b2C3d4E5f6G7", "mcp_tool_name": "x"})},
        {"event.name": "tool_result", "tool_name": "mcp_tool",
         "tool_parameters": tp({"mcp_server_name": "not-context-mode", "mcp_tool_name": "ctx_stats"})},
        # review round 2: identifier-shaped values the model types (a file name as a skill or subagent type, a
        # workflow script's name), a rejected launch, and custom agent names on native events
        {"event.name": "tool_result", "tool_name": "Skill", "success": "false",
         "tool_parameters": tp({"skill_name": f"{SENTINEL}-notes.txt"})},
        {"event.name": "tool_decision", "tool_name": "Agent", "decision": "accept",
         "tool_parameters": tp({"subagent_type": f"{SENTINEL}-notes.txt"})},
        {"event.name": "tool_decision", "tool_name": "Agent", "decision": "reject",
         "tool_parameters": tp({"subagent_type": "Explore"})},
        {"event.name": "tool_decision", "tool_name": "Workflow", "decision": "accept",
         "workflow.run_id": "wf_abc123def457", "workflow.name": f"{SENTINEL}-flow"},
        {"event.name": "subagent_completed", "agent_type": f"{SENTINEL}-agent", "total_tool_uses": "3"},
        {"event.name": "api_request", "query_source": "agent:custom", "agent.name": f"{SENTINEL}-agent",
         "model": "claude-haiku-4-5-20251001"},
    ]
    t1, t2 = "11111111_2222_4333_8444_555555555555", "66666666_7777_4888_8999_aaaaaaaaaaaa"
    codex = [
        {"event.name": "codex.tool_result", "tool_name": "exec_command", "tool_namespace": "functions",
         "arguments": tp({"cmd": f"rtk git log -1 {SENTINEL}-codex-cmd-1"}), "output": f"{SENTINEL}-codex-output-1",
         "agent_name": "/root/worker_one", "mcp_server": "", "mcp_server_origin": "", "originator": "codex_exec",
         "conversation.id": t2, "user.email": f"{SENTINEL}@example.invalid"},
        {"event.name": "codex.tool_result", "tool_name": "exec_command", "tool_namespace": "functions",
         "arguments": tp({"cmd": f"ls -la {SENTINEL}-codex-cmd-2"}), "agent_name": "/root", "mcp_server": "",
         "originator": "codex_exec", "conversation.id": t1},
        {"event.name": "codex.tool_result", "tool_name": "apply_patch", "tool_namespace": "functions",
         "arguments": f"*** Begin Patch {SENTINEL}-patch", "agent_name": f"/srv/example/{SENTINEL} path",
         "mcp_server": "", "originator": "codex_exec", "conversation.id": t1},
        {"event.name": "codex.tool_result", "tool_name": "query", "tool_namespace": "mcp__qmd", "mcp_server": "qmd",
         "mcp_server_origin": "stdio", "arguments": tp({"searches": f"{SENTINEL}-codex-mcp-args"}),
         "agent_name": "/root", "originator": "codex_exec", "conversation.id": t1},
        {"event.name": "codex.agent_communication", "communication_id": t2, "kind": "spawn", "state": "send",
         "sender_thread_id": t1, "receiver_thread_id": t2, "content": f"{SENTINEL}-agent-content"},
        {"event.name": "codex.agent_communication", "communication_id": t2, "kind": f"{SENTINEL} weird",
         "state": "receive"},
        {"event.name": "codex.tool_result", "tool_name": "exec_command", "tool_namespace": "mcp__foo",
         "mcp_server": "foo", "arguments": tp({"cmd": f"rtk {SENTINEL}-mcp-cmd"}), "agent_name": "/root",
         "originator": f"git log {SENTINEL}", "conversation.id": t1},
    ]
    # review round 2: two front-ends of one app-server (same service.name), a first-party "Codex <App>" originator,
    # an originator with a command in it, and an agent path with a dotted hidden segment
    app_server = [
        {"event.name": "codex.tool_result", "tool_name": "status", "tool_namespace": "mcp__qmd", "mcp_server": "qmd",
         "agent_name": "/root", "originator": "codex_vscode", "conversation.id": t1},
        {"event.name": "codex.tool_result", "tool_name": "status", "tool_namespace": "mcp__qmd", "mcp_server": "qmd",
         "agent_name": "/root", "originator": "Codex Desktop", "conversation.id": t2},
        {"event.name": "codex.tool_result", "tool_name": "exec_command", "tool_namespace": "functions",
         "arguments": tp({"cmd": f"cat {SENTINEL}-app-cmd"}), "agent_name": f"/root/.cache_{SENTINEL}/key_file",
         "originator": "codex_vscode", "conversation.id": t2},
        {"event.name": "codex.tool_result", "tool_name": "read_file", "tool_namespace": "functions",
         "agent_name": "/root", "originator": f"Codex {SENTINEL} run", "conversation.id": t1},
    ]

    def batch(service, scope, base, rows):
        return {"resourceLogs": [{"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]},
                                  "scopeLogs": [{"scope": {"name": scope},
                                                 "logRecords": [rec(base + i, a) for i, a in enumerate(rows)]}]}]}
    return [batch("claude-code", "com.anthropic.claude_code.events", 0, claude),
            batch("codex_exec", "codex_otel.log_only", 100, codex),
            batch("codex-app-server", "codex_otel.log_only", 200, app_server)]


# ---------------------------------------------------------------- post
def post(args) -> None:
    url = f"http://127.0.0.1:{args.port}/v1/logs"
    tags = {}
    sent = 0
    batches = []
    for index, path in enumerate(args.inputs):
        for line_no, line in enumerate(Path(path).read_text().splitlines()):
            if line.strip():
                batches.append((f"u6r{index}", line_no, json.loads(line)))
    # Shift every captured timestamp by one offset so the newest record lands two minutes before now. Timing inside
    # the captures is kept; the pipeline never reads timestamps. A scratch Loki 3.7.8 accepted (HTTP 204) but did
    # not return entries about 2 h old right after ingestion (round2/loki_probe.py), so unshifted captures made the
    # Loki stage depend on the time of day.
    captured = [(Path(p).name, r) for p in args.inputs for _, _, r, _ in records(Path(p))]
    if not captured and not args.synthetic:
        raise SystemExit("no capture records; pass --synthetic to replay the synthetic fixture")
    recent = time.time_ns() - 120_000_000_000
    latest = max((max(int(r.get("timeUnixNano") or 0), int(r.get("observedTimeUnixNano") or 0))
                  for _, r in captured), default=recent)
    shift = max(0, recent - latest)
    historical = HISTORICAL_CAPTURE_FILES <= {name for name, _ in captured}
    print("INFO historical capture set: " + ("present" if historical else "absent"))
    if args.synthetic:
        # Just after the newest captured record: Loki accepts out-of-order entries only within max_chunk_age/2.
        for line_no, doc in enumerate(synthetic_batches(latest + shift + 1_000_000_000)):
            batches.append(("u6s", line_no, doc))
    for prefix, line_no, doc in batches:
        n = 0
        for rl in doc.get("resourceLogs", []):
            if args.task_id and prefix.startswith("u6r"):
                # prove.sh's scope key (u1 keeps ecosystem.task.id on the logs resource); captures only
                rl.setdefault("resource", {}).setdefault("attributes", []).append(
                    {"key": "ecosystem.task.id", "value": {"stringValue": args.task_id}})
            for sl in rl.get("scopeLogs", []):
                for record in sl.get("logRecords", []):
                    if prefix.startswith("u6r"):
                        for field in ("timeUnixNano", "observedTimeUnixNano"):
                            if int(record.get(field) or 0):
                                record[field] = str(int(record[field]) + shift)
                    tag = f"{prefix}-{line_no}-{n}"
                    n += 1
                    record.setdefault("attributes", []).append({"key": "receipt_id", "value": {"stringValue": tag}})
                    tags[tag] = prefix
                    sent += 1
        request = urllib.request.Request(url, data=json.dumps(doc).encode(), method="POST",
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise SystemExit(f"POST failed with HTTP {response.status}")
    Path(args.tags).write_text(json.dumps(tags))
    print(f"posted records={sent} requests={len(batches)} inputs={len(args.inputs)} synthetic={bool(args.synthetic)}"
          f" capture_time_shift_s={shift / 1e9:.0f}")


# ---------------------------------------------------------------- reference specification (independent of OTTL)
def family_claude(tool: str | None) -> str:
    table = {"Bash": "shell", "PowerShell": "shell", "Read": "read", "Grep": "read", "Glob": "read", "LS": "read",
             "NotebookRead": "read", "Edit": "edit", "MultiEdit": "edit", "Write": "edit", "NotebookEdit": "edit",
             "mcp_tool": "mcp", "Skill": "skill", "ToolSearch": "toolsearch", "WebFetch": "web", "WebSearch": "web",
             "Agent": "agent", "Task": "agent", "Workflow": "agent"}
    return table.get(tool or "", "other")


def family_codex(tool: str | None, namespace: str | None) -> str:
    tool, namespace = tool or "", namespace or ""
    if namespace.startswith("mcp__"):
        return "mcp"
    if namespace == "functions" and tool in ("exec", "wait"):
        return "code_mode"
    if namespace == "collaboration" or tool in ("spawn_agent", "send_input", "send_message", "followup_task",
                                                "wait_agent", "close_agent", "resume_agent", "list_agents",
                                                "interrupt_agent"):
        return "agent"
    if tool == "tool_search":
        return "toolsearch"
    if namespace == "web" or tool == "web_search":
        return "web"
    if tool == "apply_patch":
        return "edit"
    if tool in ("read_file", "list_dir", "grep_files", "view_image"):
        return "read"
    if tool in ("exec_command", "write_stdin", "shell", "shell_command", "local_shell"):
        return "shell"
    return "other"


def guard(key: str, value):
    if value is None:
        return None
    text = str(value)
    if key in REGISTRY_NAME_KEYS:
        return value if NAME.match(text) and not TOKEN_RUN.search(text) else "other"
    if key in AGENT_TYPE_KEYS:
        return value if isinstance(value, str) and value in BUILTIN_AGENTS else "custom"
    if key in NOT_EXPORTED:
        return None
    patterns = {"workflow.run_id": r"^wf_[A-Za-z0-9_-]{1,32}$", "sender_thread_id": r"^[0-9A-Fa-f-]{36}$",
                "receiver_thread_id": r"^[0-9A-Fa-f-]{36}$", "kind": r"^(spawn|message|followup|result)$",
                "state": r"^(send|receive)$", "total_tool_uses": r"^[0-9]{1,9}$",
                "tool_family": r"^(shell|read|edit|mcp|skill|toolsearch|web|agent|code_mode|other)$",
                "actor": r"^(main|subagent|workflow|main_or_subagent|auxiliary)$", "shell_rtk": r"^(true|false)$",
                "tool_details": r"^unparsed$", "invocation_trigger": r"^(user-slash|claude-proactive|nested-skill)$"}
    if key in patterns:
        return value if re.match(patterns[key], text) else None
    return value


def normalized_originator(value):
    """First-party desktop clients are named "Codex <App>" (codex-rs default_client.rs is_first_party_originator)."""
    if not isinstance(value, str):
        return value
    match = re.fullmatch(r"Codex ([A-Za-z]{1,32})", value)
    return ("codex_" + match.group(1) if match else value).lower()


def expected_derived(a: dict, resource: dict | None = None) -> dict:
    """Expected values of DERIVED_KEYS for one input record, from the design (not from the OTTL)."""
    service = (resource or {}).get("service.name")
    out = {k: a.get(k) for k in ("mcp_server.name", "mcp_tool.name", "skill.name", "agent.name", "agent_type",
                                 "workflow.run_id", "originator", "kind", "state", "sender_thread_id",
                                 "receiver_thread_id", "total_tool_uses", "invocation_trigger", "subagent_type")}
    out.update({"tool_family": None, "actor": None, "shell_rtk": None, "tool_details": None, "client": None})
    out["originator"] = normalized_originator(out["originator"])
    event = a.get("event.name")
    if event in ("tool_result", "tool_decision"):
        params = a.get("tool_parameters")
        parsed = None
        if isinstance(params, str):
            try:
                parsed = json.loads(params)
            except ValueError:
                parsed = None
            if not isinstance(parsed, dict):
                out["tool_details"] = "unparsed"
                parsed = None
        elif params is not None:
            out["tool_details"] = "unparsed"
        parsed = parsed or {}
        # skill_name is not copied: the Skill tool's input is typed by the model
        for src, dst in (("mcp_server_name", "mcp_server.name"), ("mcp_tool_name", "mcp_tool.name"),
                         ("subagent_type", "subagent_type")):
            if isinstance(parsed.get(src), str):
                out[dst] = parsed[src]
        if isinstance(parsed.get("bash_command"), str):
            out["shell_rtk"] = "true" if re.match(r"^(.*/)?rtk$", parsed["bash_command"]) else "false"
        out["tool_family"] = family_claude(a.get("tool_name"))
        out["actor"] = "workflow" if a.get("workflow.run_id") is not None else "main_or_subagent"
        out["client"] = service
    elif event in ("api_request", "assistant_response"):
        source = str(a.get("query_source") or "")
        out["actor"] = "auxiliary"
        if re.match(r"^(repl_main_thread|sdk)", source):
            out["actor"] = "main"
        if source.startswith("agent:"):
            out["actor"] = "subagent"
        if a.get("workflow.run_id") is not None:
            out["actor"] = "workflow"
    elif event in ("codex.tool_result", "codex.tool_decision"):
        server = a.get("mcp_server")
        if isinstance(server, str) and server != "":
            out["mcp_server.name"] = server
        if str(a.get("tool_namespace") or "").startswith("mcp__"):
            out["mcp_tool.name"] = a.get("tool_name")
        if a.get("tool_namespace") == "functions" and a.get("tool_name") == "exec_command" \
                and isinstance(a.get("arguments"), str):
            try:
                cmd = json.loads(a["arguments"]).get("cmd")
            except (ValueError, AttributeError):
                cmd = None
            if isinstance(cmd, str):
                out["shell_rtk"] = "true" if re.match(r"^\s*(\S*/)?rtk(\s|$)", cmd) else "false"
        out["tool_family"] = family_codex(a.get("tool_name"), a.get("tool_namespace"))
        if a.get("agent_name") == "/root":
            out["actor"] = "main"
        elif a.get("agent_name") is not None:
            out["actor"] = "subagent"
        out["client"] = service
        if service == "codex-app-server" and isinstance(out["originator"], str) and out["originator"] != "":
            out["client"] = out["originator"]
    for key in list(out):
        out[key] = guard(key, out[key])
    return {k: v for k, v in out.items() if v is not None}


def leaves(value, prefix=""):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from leaves(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(value, list):
        for v in value:
            yield from leaves(v, prefix)
    elif isinstance(value, str):
        yield prefix, value


def content_strings(a: dict) -> list[tuple[str, str]]:
    """(key path, text) for content-bearing keys and their JSON leaves."""
    found = []
    for key in ("tool_parameters", "tool_input", "arguments", "output", "content", "error", "prompt", "response"):
        value = a.get(key)
        if not isinstance(value, str):
            continue
        found.append((key, value))
        try:
            parsed = json.loads(value)
        except ValueError:
            continue
        found.extend((f"{key}.{path}", v) for path, v in leaves(parsed))
    return found


# ---------------------------------------------------------------- assert
def load(args):
    tags = json.loads(Path(args.tags).read_text())
    inputs = {}
    for index, path in enumerate(args.inputs):
        for line_no, line in enumerate(Path(path).read_text().splitlines()):
            if not line.strip():
                continue
            n = 0
            for rl in json.loads(line).get("resourceLogs", []):
                resource = attrs(rl.get("resource", {}).get("attributes"))
                for sl in rl.get("scopeLogs", []):
                    for record in sl.get("logRecords", []):
                        inputs[f"u6r{index}-{line_no}-{n}"] = (Path(path).name, resource, attrs(record.get("attributes")))
                        n += 1
    for line_no, doc in enumerate(synthetic_batches(0)):
        n = 0
        for rl in doc["resourceLogs"]:
            resource = attrs(rl["resource"]["attributes"])
            for sl in rl["scopeLogs"]:
                for record in sl["logRecords"]:
                    tag = f"u6s-{line_no}-{n}"
                    if tag in tags:
                        inputs[tag] = ("synthetic", resource, attrs(record["attributes"]))
                    n += 1
    outputs = {}
    for resource, scope, record, a in records(Path(args.out)):
        outputs[a.get("receipt_id")] = (resource, scope, record, a)
    return tags, inputs, outputs


def staged_allowlists(collector: Path):
    config = yaml.safe_load(collector.read_text())
    groups = config["processors"]["transform/privacy"]["log_statements"]
    def quoted(context):
        statement = next(s for g in groups if g["context"] == context for s in g["statements"] if s.startswith("keep_keys("))
        return set(re.findall(r'"([^"]+)"', statement.split("[", 1)[1].split("]", 1)[0]))
    return quoted("resource"), quoted("log")


def historical_assertions(inputs, outputs, shared) -> None:
    # spot checks against the probe tables (fixed expectations, independent of the reference spec)
    def rows(file_name, event):
        return [outputs[t][3] for t in shared if inputs[t][0] == file_name and outputs[t][3].get("event.name") == event]
    b_tools = rows("claude-B-logs.json", "tool_result")
    servers = collections.Counter(r.get("mcp_server.name") for r in b_tools if r.get("tool_family") == "mcp")
    check("B (details on): MCP tool_result by server = context-mode plugin 1, qmd 2",
          servers == collections.Counter({"plugin_context-mode_context-mode": 1, "qmd": 2}), f"got={dict(servers)}")
    tools = collections.Counter(r.get("mcp_tool.name") for r in b_tools if r.get("tool_family") == "mcp")
    check("B: MCP tool_result by tool = ctx_stats 1, status 2",
          tools == collections.Counter({"ctx_stats": 1, "status": 2}), f"got={dict(tools)}")
    check("B: skill_activated names the skill (codebase-design); the Skill tool_result carries no skill name",
          [r.get("skill.name") for r in b_tools if r.get("tool_name") == "Skill"] == [None]
          and [r.get("skill.name") for r in rows("claude-B-logs.json", "skill_activated")] == ["codebase-design"])
    check("B: the Agent tool_result and its accepted tool_decision name the subagent type (general-purpose)",
          [r.get("subagent_type") for r in b_tools if r.get("tool_name") == "Agent"] == ["general-purpose"]
          and [(r.get("decision"), r.get("subagent_type")) for r in rows("claude-B-logs.json", "tool_decision")
               if r.get("tool_name") == "Agent"] == [("accept", "general-purpose")])
    rtk = [r.get("shell_rtk") for r in b_tools if r.get("tool_family") == "shell"]
    check("B: the Bash call carries shell_rtk=true (the hook-rewritten command starts with rtk)", rtk == ["true"],
          f"got={rtk}")
    actors = collections.Counter((r.get("tool_name"), r.get("actor")) for r in b_tools)
    check("B: the workflow child's ToolSearch and MCP results are actor=workflow; the other 8 are main_or_subagent",
          actors[("mcp_tool", "workflow")] == 1 and actors[("ToolSearch", "workflow")] == 1
          and sum(n for (t, a), n in actors.items() if a == "main_or_subagent") == 8, f"got={dict(actors)}")
    b_api = collections.Counter((r.get("actor"), r.get("mcp_server.name")) for r in rows("claude-B-logs.json", "api_request")
                                if r.get("mcp_server.name"))
    check("B: api_request consuming MCP results = main/context-mode 1, subagent/qmd 1, workflow/qmd 1",
          b_api == collections.Counter({("main", "plugin_context-mode_context-mode"): 1, ("subagent", "qmd"): 1,
                                        ("workflow", "qmd"): 1}), f"got={dict(b_api)}")
    sub = rows("claude-B-logs.json", "subagent_completed")
    check("B: subagent_completed keeps agent_type and total_tool_uses",
          len(sub) == 1 and sub[0].get("agent_type") == "general-purpose" and str(sub[0].get("total_tool_uses", "")).isdigit())
    for run in ("A", "C"):
        tools = rows(f"claude-{run}-logs.json", "tool_result")
        check(f"{run} (details off): MCP calls counted as tool_family=mcp without names; nothing unparsed",
              sum(1 for r in tools if r.get("tool_family") == "mcp") == 3
              and not any("mcp_server.name" in r or "tool_details" in r for r in tools))
        check(f"{run}: skill_activated keeps the redacted placeholder custom_skill",
              [r.get("skill.name") for r in rows(f"claude-{run}-logs.json", "skill_activated")] == ["custom_skill"])
    c_session = {r.get("session.id") is not None for r in rows("claude-C-logs.json", "tool_result")}
    check("C: session.id survives on events (u1 correlation id kept); A has none",
          c_session == {True} and not any("session.id" in r for r in rows("claude-A-logs.json", "tool_result")))
    codex = rows("codex-logs.json", "codex.tool_result")
    check("Codex: ctx_stats result is tool_family=mcp, mcp_server.name=context-mode, mcp_tool.name=ctx_stats",
          [(r.get("tool_family"), r.get("mcp_server.name"), r.get("mcp_tool.name")) for r in codex
           if r.get("tool_family") == "mcp"] == [("mcp", "context-mode", "ctx_stats")])
    check("Codex: actor main on 6 root-thread results, subagent on 2 sub-agent results; the agent path is not exported",
          collections.Counter(r.get("actor") for r in codex) == collections.Counter({"main": 6, "subagent": 2})
          and not any("agent_name" in r for r in codex))
    families = collections.Counter(r.get("tool_family") for r in codex)
    check("Codex: families code_mode 3 (exec wrappers kept apart), shell 2, agent 2, mcp 1",
          families == collections.Counter({"code_mode": 3, "shell": 2, "agent": 2, "mcp": 1}), f"got={dict(families)}")
    check("Codex: exec_command results carry shell_rtk (command text deleted)",
          all(r.get("shell_rtk") in ("true", "false") for r in codex if r.get("tool_name") == "exec_command"))
    comms = rows("codex-logs.json", "codex.agent_communication")
    check("Codex: agent_communication keeps kind/state/sender/receiver, drops content",
          sorted((r.get("kind"), r.get("state")) for r in comms if r.get("state") == "send")
          == [("result", "send"), ("spawn", "send")]
          and all(r.get("sender_thread_id") and r.get("receiver_thread_id") for r in comms if r.get("state") == "send")
          and not any("content" in r for r in comms))
    check("Codex: originator kept (codex_exec) and client codex_exec on tool results",
          {r.get("originator") for r in codex} == {"codex_exec"} and {r.get("client") for r in codex} == {"codex_exec"})
    check("Claude: client is the service name (claude-code) on every tool event of A, B and C",
          {r.get("client") for run in "ABC" for event in ("tool_result", "tool_decision")
           for r in rows(f"claude-{run}-logs.json", event)} == {"claude-code"})


def run_assertions(args) -> None:
    tags, inputs, outputs = load(args)
    resource_allow, log_allow = staged_allowlists(Path(args.collector))
    exported = sum(1 for _ in records(Path(args.out)))
    check("every replayed record was exported exactly once",
          set(outputs) == set(tags) == set(inputs) and exported == len(tags), f"sent={len(tags)} exported={exported}")
    shared = sorted(set(outputs) & set(inputs))

    # u1 invariants
    bad_resource = sorted({k for t in shared for k in outputs[t][0] if k not in resource_allow})
    check("u1 invariant: resource keys stay within the u1 resource allowlist", not bad_resource, f"extra={bad_resource}")
    check("u1 invariant: every body is [content omitted] and every scope is native-agent-telemetry",
          all(value_of(outputs[t][2].get("body", {})) == "[content omitted]" and outputs[t][1] == "native-agent-telemetry"
              for t in shared))
    extra = sorted({k for t in shared for k in outputs[t][3] if k not in log_allow})
    check("exported record keys stay within the staged log allowlist", not extra, f"extra={extra}")
    leaked = sorted({k for t in shared for k in outputs[t][3] if k in CONTENT_KEYS})
    check("no content or identity key is exported (tool_parameters, tool_input, arguments, output, content, error,"
          " prompt, user.*)", not leaked, f"leaked={leaked}")

    # derived attributes equal the independent reference specification, record by record
    mismatches = collections.Counter()
    for tag in shared:
        expected = expected_derived(inputs[tag][2], inputs[tag][1])
        actual = {k: v for k, v in outputs[tag][3].items() if k in DERIVED_KEYS}
        for key in set(expected) | set(actual):
            if str(expected.get(key)) != str(actual.get(key)):
                mismatches[(inputs[tag][2].get("event.name"), key)] += 1
    check("derived names/families/actors equal the reference spec on every record (all captures + synthetic)",
          not mismatches, f"mismatches={dict(mismatches)}")

    # name fields obey the name patterns
    bad_names = collections.Counter()
    for tag in shared:
        a = outputs[tag][3]
        for key in REGISTRY_NAME_KEYS:
            if key in a and not NAME.match(str(a[key])):
                bad_names[key] += 1
        for key in AGENT_TYPE_KEYS:
            if key in a and a[key] not in BUILTIN_AGENTS:
                bad_names[key] += 1
    check("every exported registry name matches its name pattern; every agent type is built-in or custom",
          not bad_names, f"bad={dict(bad_names)}")
    carried = collections.Counter(k for t in shared for k in outputs[t][3] if k in NOT_EXPORTED)
    check("model-typed workflow names and Codex agent paths are never exported", not carried, f"found={dict(carried)}")

    # no command/prompt/script/argument text reaches the exporter. Only input fields that carry a name by design
    # (the Skill tool's skill, a subagent type or model, a Codex task_name, the MCP name fields) may reappear, and
    # only when they pass the name rules; the exemption never depends on the output under test.
    name_paths = {"tool_input.skill", "tool_input.subagent_type", "tool_input.model",
                  "tool_parameters.mcp_server_name", "tool_parameters.mcp_tool_name", "tool_parameters.skill_name",
                  "tool_parameters.subagent_type"}
    forbidden = {}
    for tag in inputs:
        origin = "synthetic" if tag.startswith("u6s") else "capture"
        event = inputs[tag][2].get("event.name")
        for key, text in content_strings(inputs[tag][2]):
            if len(text) < 8:
                continue
            if key in name_paths and NAME.match(text) and not TOKEN_RUN.search(text):
                continue
            forbidden.setdefault(text, (origin, f"{event}:{key}"))
    exported_text = Path(args.out).read_text()
    hits = [where for text, where in forbidden.items()
            if text in exported_text or json.dumps(text)[1:-1] in exported_text]
    by_source = collections.Counter(where for where in forbidden.values())
    check("no command, prompt, script, argument, output or agent-message text reaches the exporter",
          not hits and forbidden, f"forbidden strings checked={len(forbidden)} found={len(hits)} {sorted(hits)}")
    print("INFO forbidden strings by source (origin, event:key -> count): "
          + "; ".join(f"{o} {w}={n}" for (o, w), n in sorted(by_source.items())))
    check("no synthetic sentinel reaches the exporter", SENTINEL not in exported_text,
          f"synthetic records={sum(1 for t in tags if t.startswith('u6s'))}")

    if HISTORICAL_CAPTURE_FILES <= {row[0] for row in inputs.values()}:
        historical_assertions(inputs, outputs, shared)
    else:
        print("INFO historical capture assertions skipped: complete A/B/C/Codex capture set absent")
    synthetic = {t: outputs[t][3] for t in shared if t.startswith("u6s")}
    by_input = {t: inputs[t][2] for t in synthetic}
    malformed = [synthetic[t] for t, a in by_input.items() if SENTINEL + "-malformed" in str(a.get("tool_parameters"))]
    check("synthetic: malformed tool_parameters -> tool_details=unparsed, no name, no content",
          len(malformed) == 1 and malformed[0].get("tool_details") == "unparsed" and "mcp_server.name" not in malformed[0])
    bad_skill = [synthetic[t] for t, a in by_input.items() if a.get("tool_name") == "Skill"]
    check("synthetic: a skill name typed into the Skill tool (a command, a file name) is not exported",
          len(bad_skill) == 2 and not any("skill.name" in r for r in bad_skill))
    typed_agent = [synthetic[t].get("subagent_type") for t, a in by_input.items()
                   if a.get("tool_name") == "Agent" and SENTINEL in str(a.get("tool_parameters"))]
    check("synthetic: a file-name-shaped subagent_type typed into the Agent tool becomes custom", typed_agent == ["custom"])
    custom = [(synthetic[t].get("agent_type"), synthetic[t].get("agent.name")) for t, a in by_input.items()
              if SENTINEL in str(a.get("agent_type", "")) + str(a.get("agent.name", ""))]
    check("synthetic: agent names outside the built-in agents become custom (subagent_completed, api_request)",
          sorted(map(str, custom)) == sorted(map(str, [("custom", None), (None, "custom")])))
    flows = [synthetic[t] for t, a in by_input.items() if "workflow.name" in a]
    check("synthetic: workflow names are never exported (tool_result and tool_decision)",
          len(flows) == 2 and not any("workflow.name" in r for r in flows))
    app = {t: synthetic[t] for t, a in by_input.items() if inputs[t][1].get("service.name") == "codex-app-server"}
    check("synthetic: two app-server front-ends get their own client; a first-party Codex <App> originator is"
          " normalized; an originator with a command becomes other",
          sorted((r.get("client"), r.get("originator")) for r in app.values())
          == [("codex_desktop", "codex_desktop"), ("codex_vscode", "codex_vscode"), ("codex_vscode", "codex_vscode"),
              ("other", "other")])
    dotted = [r for t, r in app.items() if ".cache_" in str(by_input[t].get("agent_name"))]
    check("synthetic: an agent path with a dotted hidden segment is not exported; actor subagent",
          [(r.get("actor"), "agent_name" in r) for r in dotted] == [("subagent", False)])
    spaced = [synthetic[t].get("mcp_server.name") for t, a in by_input.items()
              if "server with space" in str(a.get("tool_parameters"))]
    check("synthetic: server name with spaces is exported as other", spaced == ["other"])
    codex_rtk = sorted(str(synthetic[t].get("shell_rtk")) for t, a in by_input.items()
                       if a.get("tool_name") == "exec_command" and a.get("tool_namespace") == "functions")
    check("synthetic: Codex exec_command shell_rtk true for an rtk command, false otherwise (codex_exec and app-server)",
          codex_rtk == ["false", "false", "true"], f"got={codex_rtk}")
    weird = [synthetic[t] for t, a in by_input.items() if str(a.get("kind", "")).startswith(SENTINEL)]
    check("synthetic: unexpected agent_communication kind is deleted", len(weird) == 1 and "kind" not in weird[0])
    forged = [synthetic[t] for t, a in by_input.items() if a.get("tool_name") == "Read"]
    check("synthetic: client-supplied derived keys are replaced or deleted (tool_family, actor, shell_rtk, tool_details)",
          [(r.get("tool_family"), r.get("actor"), "shell_rtk" in r, "tool_details" in r) for r in forged]
          == [("read", "main_or_subagent", False, False)])
    address = [synthetic[t] for t, a in by_input.items() if a.get("event.name") == "skill_activated"]
    check("synthetic: an address as skill name becomes other; a trigger outside its set is deleted",
          [(r.get("skill.name"), "invocation_trigger" in r) for r in address] == [("other", False)])
    token = [synthetic[t].get("mcp_server.name") for t, a in by_input.items()
             if "tokenA1b2" in str(a.get("tool_parameters"))]
    check("synthetic: a token-shaped server name becomes other", token == ["other"])
    mcp_exec = [synthetic[t] for t, a in by_input.items() if a.get("tool_namespace") == "mcp__foo"]
    check("synthetic: an MCP tool named exec_command gets no shell_rtk; an originator with spaces becomes other",
          [(r.get("tool_family"), "shell_rtk" in r, r.get("originator"), r.get("client")) for r in mcp_exec]
          == [("mcp", False, "other", "codex_exec")])


def forbidden_file(args) -> None:
    """Content strings of the captures (not name-like), one per line, for prove_check.py --forbidden-file."""
    texts = set()
    for path in args.inputs:
        for _, _, _, a in records(Path(path)):
            for _, text in content_strings(a):
                if len(text) >= 8 and "\n" not in text and not NAME.match(text):
                    texts.add(text)
    Path(args.out).write_text("".join(t + "\n" for t in sorted(texts)))
    check("forbidden-string file written from the captures", bool(texts), f"strings={len(texts)}")


# ---------------------------------------------------------------- SDK receipts (review round)
U6_KEYS = ["tool_family", "actor", "shell_rtk", "tool_details", "client", "mcp_server.name", "mcp_tool.name",
           "skill.name", "invocation_trigger", "subagent_type", "agent.name", "agent_type", "total_tool_uses",
           "workflow.run_id", "originator", "kind", "state", "sender_thread_id", "receiver_thread_id",
           "workflow.name", "agent_name"]


def write_receipts(args) -> None:
    """One receipt in the helper's shape and one file that tries to add u6 keys through the shared allowlist."""
    directory = Path(args.dir)
    directory.mkdir(parents=True, exist_ok=True)
    legit = {"observation_id": "u6-legit-receipt", "status": "completed", "configured_model": "gpt-6-astra",
             "duration_ms": 1234, "usage_status": "reported",
             "usage": {"total": {"inputTokens": 10, "outputTokens": 5, "cachedInputTokens": 0,
                                 "reasoningOutputTokens": 0, "totalTokens": 15}}}
    forged = {"observation_id": "u6-forged-receipt", "status": "completed", "usage_status": "unavailable",
              "skill.name": f"cat /private/{SENTINEL}-receipt", "tool_family": SENTINEL, "mcp_server.name": "qmd",
              "agent_name": "/root/x", "originator": "codex_exec", "kind": "spawn", "tool_input": SENTINEL,
              "client": "codex_vscode", "subagent_type": "general-purpose"}
    for name, body in (("legit", legit), ("forged", forged)):
        (directory / f"{name}.json").write_text(json.dumps(body, indent=2) + "\n")
    check("scratch SDK receipts written (helper shape + forged u6 keys)", True, "files=2")


def assert_receipts(args) -> None:
    rows = [(resource, a) for resource, _, _, a in records(Path(args.out))] if Path(args.out).exists() else []
    by_id = {a.get("receipt_id"): a for _, a in rows}
    check("both SDK receipts were exported by the receipt pipeline", sorted(by_id) == ["u6-forged-receipt",
                                                                                       "u6-legit-receipt"],
          f"receipts={sorted(map(str, by_id))}")
    forged = by_id.get("u6-forged-receipt", {})
    check("a receipt file cannot add u6 names or derived keys through the shared allowlist",
          bool(forged) and not any(k in forged for k in U6_KEYS) and "tool_input" not in forged,
          f"u6 keys present={[k for k in U6_KEYS if k in forged]}")
    legit = by_id.get("u6-legit-receipt", {})
    check("the helper-shaped receipt keeps its u1 fields (event.name, usage_status, total_token_count)",
          legit.get("event.name") == "ecosystem.sdk_receipt" and legit.get("usage_status") == "reported"
          and float(legit.get("total_token_count", -1)) == 15.0)
    check("no sentinel from a receipt file reaches the exporter", SENTINEL not in Path(args.out).read_text()
          if Path(args.out).exists() else False)


# ---------------------------------------------------------------- loki
def loki_label_map(resource: dict, a: dict) -> dict:
    labels = {"service_name": resource.get("service.name")}
    for key, value in a.items():
        labels[re.sub(r"[^A-Za-z0-9_]", "_", key)] = value
    return labels


def expectation(panel: int, ref: str, rows: list[dict], window_s: float):
    """Expected instant-query result for one new dashboard target, computed from the exported records."""
    def tool_results(r, events=("tool_result", "codex.tool_result")):
        return r.get("event_name") in events
    claude = [r for r in rows if str(r.get("service_name", "")).startswith("claude-code")]
    rate = 60.0 / window_s

    def grouped(selection, keys, weight=lambda r: 1):
        out = collections.Counter()
        for r in selection:
            out[tuple((k, str(r[k])) for k in keys if r.get(k) not in (None, ""))] += weight(r)
        return {k: v * rate for k, v in out.items()}

    def ratio(numerator, denominator):
        n, d = len(numerator), len(denominator)
        return None if d == 0 else {(): n / d}

    ctx = lambda r: str(r.get("mcp_server_name", "")) in ("context-mode", "plugin_context-mode_context-mode")
    codex = [r for r in rows if r.get("event_name") == "codex.tool_result"]
    ctool = [r for r in claude if r.get("event_name") == "tool_result"]
    table = {
        (29, "A"): lambda: grouped(ctool, ["tool_family"]),
        (30, "A"): lambda: grouped(codex, ["tool_family"]),
        (31, "A"): lambda: grouped([r for r in rows if tool_results(r) and r.get("tool_family") == "mcp"],
                                   ["client", "mcp_server_name"]),
        (32, "A"): lambda: grouped([r for r in claude if r.get("event_name") == "skill_activated"],
                                   ["skill_name", "invocation_trigger"]),
        (33, "A"): lambda: grouped([r for r in claude if r.get("event_name") == "tool_decision"
                                    and r.get("decision") == "accept" and r.get("tool_name") in ("Agent", "Task")],
                                   ["subagent_type"]),
        (33, "B"): lambda: grouped([r for r in claude if r.get("event_name") == "tool_decision"
                                    and r.get("decision") == "accept" and r.get("tool_name") == "Workflow"],
                                   ["service_name"]),
        (33, "C"): lambda: grouped([r for r in rows if r.get("event_name") == "codex.agent_communication"
                                    and r.get("kind") == "spawn" and r.get("state") == "send"], ["service_name"]),
        (34, "A"): lambda: grouped([r for r in rows if tool_results(r) and r.get("tool_family") != "code_mode"],
                                   ["client", "actor"]),
        (34, "B"): lambda: grouped([r for r in claude if r.get("event_name") == "subagent_completed"], ["agent_type"],
                                   weight=lambda r: float(r.get("total_tool_uses", 0))),
        (35, "A"): lambda: ratio([r for r in ctool if r.get("tool_family") == "mcp"], ctool),
        (35, "B"): lambda: ratio([r for r in codex if r.get("tool_family") == "mcp"],
                                 [r for r in codex if r.get("tool_family") != "code_mode"]),
        (36, "A"): lambda: ratio([r for r in ctool if ctx(r)],
                                 [r for r in ctool if r.get("tool_family") in ("shell", "read", "web") or ctx(r)]),
        (36, "B"): lambda: ratio([r for r in codex if ctx(r)],
                                 [r for r in codex if r.get("tool_family") in ("shell", "read", "web") or ctx(r)]),
        (36, "C"): lambda: ratio([r for r in ctool if r.get("shell_rtk") == "true"],
                                 [r for r in ctool if r.get("shell_rtk") not in (None, "")]),
        (36, "D"): lambda: ratio([r for r in codex if r.get("shell_rtk") == "true"],
                                 [r for r in codex if r.get("shell_rtk") not in (None, "")]),
        (37, "A"): lambda: {(): float(sum(1 for r in ctool if r.get("tool_family") == "mcp"
                                          and not r.get("mcp_server_name")))},
        (37, "B"): lambda: {(): float(sum(1 for r in rows if r.get("tool_details") == "unparsed"))},
        (37, "C"): lambda: {(): float(sum(1 for r in rows if any(r.get(k) == "other" for k in (
            "mcp_server_name", "mcp_tool_name", "skill_name", "originator", "client"))))},
        (38, "A"): lambda: grouped([r for r in claude if r.get("event_name") == "api_request"
                                    and r.get("mcp_server_name")], ["actor", "mcp_server_name"]),
    }
    return table[(panel, ref)]()


def loki(args) -> None:
    base = f"http://127.0.0.1:{args.port}"
    rows = [loki_label_map(resource, a) for resource, _, _, a in records(Path(args.out))]
    total = len(rows)
    window = args.window
    window_s = {"h": 3600, "m": 60}[window[-1]] * float(window[:-1])

    def instant(expr):
        query = urllib.parse.urlencode({"query": expr, "time": f"{args.at:.3f}"})
        try:
            with urllib.request.urlopen(f"{base}/loki/api/v1/query?{query}", timeout=60) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, {"error": error.read().decode(errors="replace")[:300]}

    deadline = time.time() + 90
    ingested = -1
    while time.time() < deadline:
        status, body = instant(f'sum(count_over_time({{service_name=~".+"}} | receipt_id=~"u6.+" | keep service_name [{window}]))')
        result = body.get("data", {}).get("result", []) if status == 200 else []
        ingested = int(float(result[0]["value"][1])) if result else 0
        if ingested >= total:
            break
        time.sleep(2)
    check("scratch Loki ingested every exported record (OTLP, u1 Loki template)", ingested == total,
          f"exported={total} ingested={ingested}")

    status, body = instant(f'sum by (service_name) (count_over_time({{service_name=~".+"}} [{window}]))')
    labels = sorted(r["metric"].get("service_name", "") for r in body.get("data", {}).get("result", []))
    check("only service_name is a stream label; names stay structured metadata",
          status == 200 and labels == sorted({str(r["service_name"]) for r in rows}), f"streams={labels}")
    query = urllib.parse.urlencode({"query": '{service_name=~".+"} | receipt_id=~"u6.+"', "limit": 5000,
                                    "start": str(int((args.at - window_s) * 1e9)), "end": str(int(args.at * 1e9))})
    request = urllib.request.Request(f"{base}/loki/api/v1/query_range?{query}",
                                     headers={"X-Loki-Response-Encoding-Flags": "categorize-labels"})
    with urllib.request.urlopen(request, timeout=60) as response:
        streams = json.load(response)["data"]["result"]
    metadata_text = json.dumps(streams)
    label_sets = {tuple(sorted(s["stream"])) for s in streams}
    check("every stream's labels are exactly {service_name}: no name or id is a stream label",
          bool(streams) and label_sets == {("service_name",)}, f"label sets={sorted(label_sets)}")
    resource_allow, log_allow = staged_allowlists(Path(args.collector))
    loki_name = lambda key: re.sub(r"[^A-Za-z0-9_]", "_", key)
    allowed = {loki_name(k) for k in resource_allow | log_allow} | {
        "detected_level", "observed_timestamp", "scope_name", "severity_number", "severity_text", "flags",
        "trace_id", "span_id"}  # Loki's own OTLP fields
    metadata_keys = {k for s in streams for e in s["values"] if len(e) > 2 and isinstance(e[2], dict)
                     for k in e[2].get("structuredMetadata", {})}
    check("every structured-metadata key comes from the staged allowlists or Loki's own OTLP fields",
          bool(metadata_keys) and metadata_keys <= allowed, f"keys={len(metadata_keys)} extra={sorted(metadata_keys - allowed)}")
    truncated = sum(len(s["values"]) for s in streams) >= 5000
    check("the Loki record fetch was not truncated", not truncated, f"records={sum(len(s['values']) for s in streams)}")
    check("no sentinel or content key is stored in Loki (lines and structured metadata)",
          SENTINEL not in metadata_text and not any(f'"{k}"' in metadata_text for k in
                                                    ("tool_parameters", "tool_input", "arguments", "full_command")))

    panels = [p for p in json.loads(Path(args.dashboard).read_text())["panels"] if p["id"] >= 28 and p.get("targets")]
    for panel in panels:
        for target in panel["targets"]:
            expr = target["expr"].replace("$__auto", window)
            status, body = instant(expr)
            name = f"panel {panel['id']}{target['refId']} ({panel['title']})"
            if status != 200:
                check(name, False, f"HTTP {status} {body.get('error', '')}")
                continue
            got = {}
            for r in body["data"]["result"]:
                key = tuple(sorted((k, v) for k, v in r.get("metric", {}).items()))
                got[key] = float(r["value"][1])
            want = expectation(panel["id"], target["refId"], rows, window_s)
            want = {} if want is None else {tuple(sorted(k)): v for k, v in want.items()}
            ok = set(got) == set(want) and all(abs(got[k] - want[k]) <= 1e-6 * max(1.0, abs(want[k])) for k in want)
            shown = "; ".join(f"{dict(k) or '{}'}={v:.4g}" for k, v in sorted(got.items())[:8])
            check(name, ok, f"series={len(got)} {shown}" + ("" if ok else f" expected={ {str(dict(k)): round(v, 6) for k, v in want.items()} }"))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build-config")
    p.add_argument("--collector", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--otlp-port", type=int, required=True)
    p.add_argument("--health-port", type=int, required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--loki-port", type=int)
    p.add_argument("--receipts-dir")
    p.add_argument("--receipts-file")
    p = sub.add_parser("receipts")
    p.add_argument("--dir", required=True)
    p = sub.add_parser("assert-receipts")
    p.add_argument("--out", required=True)
    p = sub.add_parser("post")
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--task-id")
    p.add_argument("--tags", required=True)
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("inputs", nargs="*")
    p = sub.add_parser("forbidden")
    p.add_argument("--out", required=True)
    p.add_argument("inputs", nargs="+")
    p = sub.add_parser("assert")
    p.add_argument("--out", required=True)
    p.add_argument("--tags", required=True)
    p.add_argument("--collector", required=True)
    p.add_argument("inputs", nargs="*")
    p = sub.add_parser("loki")
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--collector", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--dashboard", required=True)
    p.add_argument("--window", default="3h")
    p.add_argument("--at", type=float, default=time.time())
    args = parser.parse_args()
    {"build-config": build_config, "post": post, "assert": run_assertions, "loki": loki,
     "forbidden": forbidden_file, "receipts": write_receipts, "assert-receipts": assert_receipts}[args.command](args)
    print(f"SUMMARY {args.command}: {results['pass']} passed, {results['fail']} failed")
    sys.exit(1 if results["fail"] else 0)


if __name__ == "__main__":
    main()
