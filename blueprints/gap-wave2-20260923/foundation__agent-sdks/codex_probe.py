#!/usr/bin/env python3
"""Bounded Codex SDK probes for the agent-sdks gap wave (2026-09-23).

Uses only the official `openai_codex` package (public `CodexClient` with an
`approval_handler`, `request`, `turn_start`, `turn_interrupt` and routed
notifications) against the native Codex binary and native sign-in. No
credential file is opened. Host lifecycle hooks, plugins, MCP servers and OTLP
exporters are disabled by per-process config overrides unless a mode keeps one
named server on purpose.

Modes
  config-diff   effective config / MCP / hooks for the parent vs isolated worker (no inference)
  limits        account/rateLimits/read only (no inference)
  tool-turn     persistent thread, one dynamic (custom) tool, one turn
  resume-turn   new process: thread/resume by id, turn 2 must recall turn-1 tool output
  cancel        one long turn interrupted mid-stream; usage + rollout token_count comparison
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import threading
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from openai_codex.client import CodexClient, CodexConfig
from openai_codex.generated.notification_registry import NOTIFICATION_MODELS
from openai_codex.models import UnknownNotification

MODEL = "gpt-6-astra"
HOST_MCP = ("context-mode", "jcodemunch", "serena", "socraticode", "ai-memory")
BASE_ISOLATE = (
    "features.hooks=false",
    "features.plugin_hooks=false",
    "features.apps=false",
    'otel.exporter="none"',
    'otel.metrics_exporter="none"',
    "analytics.enabled=false",
)
ISOLATE: tuple[str, ...] = BASE_ISOLATE  # extended per workspace by resolve_isolation()


def resolve_isolation(args) -> tuple[str, ...]:
    """Disable every plugin and MCP server the parent's effective config enables for this cwd."""
    with CodexClient(make_config(args, ())) as client:
        client.initialize()
        conf = raw(client, "config/read", {"cwd": str(args.workspace.resolve()), "includeLayers": False}).get("config") or {}
    # Dotted -c paths do not unquote "a@b" plugin keys, so the table is replaced as one TOML value.
    plugins = {name: {**(v or {}), "enabled": False} for name, v in (conf.get("plugins") or {}).items()}
    extra = ["plugins={" + ",".join(json.dumps(n) + "={enabled=false}" for n in plugins) + "}"] if plugins else []
    extra += [f"mcp_servers.{name}.enabled=false" for name, v in (conf.get("mcp_servers") or {}).items()
              if (v or {}).get("enabled", True)]
    return BASE_ISOLATE + tuple(extra)


class Loose(BaseModel):
    model_config = ConfigDict(extra="allow")


def raw(client: CodexClient, method: str, params: dict | None) -> dict:
    return client.request(method, params, response_model=Loose).model_dump(mode="json", by_alias=True)


def make_config(args, overrides: tuple[str, ...]) -> CodexConfig:
    return CodexConfig(codex_bin=args.codex_bin, cwd=str(args.workspace.resolve()),
                       config_overrides=overrides,
                       env={"CODEX_HOME": str(args.codex_home.resolve())})


def now() -> float:
    return time.time()


def limits_snapshot(client: CodexClient) -> dict:
    data = raw(client, "account/rateLimits/read", {})
    bucket = (data.get("rateLimitsByLimitId") or {}).get("codex") or data.get("rateLimits") or {}
    out = {k: {f: (bucket.get(k) or {}).get(f) for f in ("usedPercent", "resetsAt", "windowDurationMins")}
           for k in ("primary", "secondary") if bucket.get(k)}
    return {"at": now(), "windows": out, "ordinaryUsageAllowed": data.get("ordinaryUsageAllowed")}


class ToolHost:
    """Answers `item/tool/call` server requests for the one registered dynamic tool."""

    def __init__(self, value: str):
        self.value = value
        self.calls: list[dict] = []
        self.other_requests: list[str] = []

    def __call__(self, method: str, params: dict | None) -> dict:
        if method == "item/tool/call":
            p = params or {}
            ok = p.get("tool") == "vault_lookup"
            self.calls.append({"at": now(), "tool": p.get("tool"), "arguments": p.get("arguments"),
                               "call_id_present": bool(p.get("callId")), "answered": ok})
            text = self.value if ok else "unknown tool"
            return {"contentItems": [{"type": "inputText", "text": text}], "success": ok}
        self.other_requests.append(method)
        # Anything else (command/file approvals) is declined; the worker is read-only.
        if method in ("item/commandExecution/requestApproval", "item/fileChange/requestApproval"):
            return {"decision": "decline"}
        return {}


TOOL_SPEC = {"type": "function", "name": "vault_lookup",
             "description": "Return the stored value for a key from the caller's private vault.",
             "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}},
                             "required": ["key"], "additionalProperties": False}}


def collect(client: CodexClient, turn_id: str, deadline: float, on_event=None) -> tuple[list[dict], dict | None]:
    """Drain routed notifications for one turn until turn/completed or deadline."""
    events: list[dict] = []
    completed = None
    box: dict = {}

    def pump():
        try:
            while True:
                n = client.next_turn_notification(turn_id)
                rec = {"at": now(), "method": n.method,
                       "typed": not isinstance(n.payload, UnknownNotification)}
                payload = n.payload
                if n.method == "thread/tokenUsage/updated" and rec["typed"]:
                    rec["tokenUsage"] = payload.model_dump(mode="json", by_alias=True).get("tokenUsage")
                if n.method in ("item/started", "item/completed") and rec["typed"]:
                    item = payload.model_dump(mode="json", by_alias=True).get("item") or {}
                    rec["item_type"] = item.get("type")
                    if item.get("type") in ("mcpToolCall", "dynamicToolCall"):
                        rec["tool"] = {k: item.get(k) for k in ("server", "tool", "namespace", "status", "success")}
                if n.method == "turn/completed" and rec["typed"]:
                    turn = payload.model_dump(mode="json", by_alias=True).get("turn") or {}
                    rec["turn_status"] = turn.get("status")
                    rec["turn_error"] = turn.get("error")
                events.append(rec)
                if on_event:
                    on_event(rec)
                if n.method == "turn/completed":
                    box["completed"] = rec
                    return
        except Exception as error:  # transport closed etc.
            box["error"] = f"{type(error).__name__}: {error}"

    worker = threading.Thread(target=pump, daemon=True)
    worker.start()
    worker.join(max(0.0, deadline - now()))
    completed = box.get("completed")
    if "error" in box:
        events.append({"at": now(), "method": "__collector_error__", "error": box["error"][:500]})
    return events, completed


def summarize(events: list[dict]) -> dict:
    counts: dict[str, int] = {}
    untyped = set()
    for e in events:
        counts[e["method"]] = counts.get(e["method"], 0) + 1
        if not e.get("typed", True):
            untyped.add(e["method"])
    usage = [e["tokenUsage"] for e in events if e.get("tokenUsage")]
    tools = [e["tool"] for e in events if e.get("tool") and e["method"] == "item/completed"]
    items = sorted({e["item_type"] for e in events if e.get("item_type")})
    return {"method_counts": counts, "untyped_methods": sorted(untyped),
            "documented_notification_types": len(NOTIFICATION_MODELS),
            "received_types_documented": sorted(set(counts) & set(NOTIFICATION_MODELS)),
            "received_types_undocumented": sorted(set(counts) - set(NOTIFICATION_MODELS) - {"__collector_error__"}),
            "documented_types_not_received": len(set(NOTIFICATION_MODELS) - set(counts)),
            "item_types": items, "tool_items": tools,
            "last_token_usage": usage[-1] if usage else None}


def rollout_token_counts(path: str | None) -> dict:
    if not path or not Path(path).is_file():
        return {"rollout_found": False}
    rows = []
    for line in Path(path).read_text().splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        pl = rec.get("payload") or {}
        if rec.get("type") == "event_msg" and pl.get("type") == "token_count":
            info = pl.get("info") or {}
            rows.append({"timestamp": rec.get("timestamp"),
                         "total": info.get("total_token_usage"), "last": info.get("last_token_usage")})
        if rec.get("type") == "event_msg" and pl.get("type") in ("turn_aborted", "task_complete", "task_started"):
            rows.append({"timestamp": rec.get("timestamp"), "event": pl.get("type"), "reason": pl.get("reason")})
    return {"rollout_found": True, "rollout_name": Path(path).name, "entries": rows}


def thread_path(client: CodexClient, thread_id: str) -> str | None:
    data = raw(client, "thread/read", {"threadId": thread_id, "includeTurns": False})
    return (data.get("thread") or {}).get("path")


def mode_config_diff(args) -> dict:
    out = {}
    for label, overrides in (("parent", ()), ("isolated_worker", resolve_isolation(args))):
        with CodexClient(make_config(args, overrides)) as client:
            client.initialize()
            cfg = raw(client, "config/read", {"cwd": str(args.workspace.resolve()), "includeLayers": False})
            mcp = raw(client, "mcpServerStatus/list", {})
            hooks = raw(client, "hooks/list", {"cwds": [str(args.workspace.resolve())]})
        conf = cfg.get("config") or {}
        servers = conf.get("mcp_servers") or {}
        out[label] = {
            "overrides": list(overrides),
            "features": {k: (conf.get("features") or {}).get(k) for k in ("hooks", "plugin_hooks", "apps")},
            "mcp_servers_enabled": sorted(n for n, v in servers.items() if (v or {}).get("enabled", True)),
            "mcp_servers_disabled": sorted(n for n, v in servers.items() if (v or {}).get("enabled", True) is False),
            "plugins": {n: (v or {}).get("enabled") for n, v in (conf.get("plugins") or {}).items()},
            "otel": {k: (conf.get("otel") or {}).get(k) for k in ("exporter", "metrics_exporter")},
            "analytics": conf.get("analytics"),
            "mcp_status_names": sorted((s or {}).get("name") for s in (mcp.get("data") or [])),
            "hooks_list": hooks,
        }
    p, i = out["parent"], out["isolated_worker"]
    out["diff"] = {k: {"parent": p[k], "isolated_worker": i[k]}
                   for k in ("features", "mcp_servers_enabled", "plugins", "otel", "analytics", "mcp_status_names")
                   if p[k] != i[k]}
    return out


def mode_limits(args) -> dict:
    with CodexClient(make_config(args, ISOLATE)) as client:
        client.initialize()
        return limits_snapshot(client)


def start_thread(client: CodexClient, args, dynamic: bool, instructions: str) -> str:
    params = {"cwd": str(args.workspace.resolve()), "model": MODEL, "ephemeral": False,
              "sandbox": "read-only", "approvalPolicy": "never",
              "developerInstructions": instructions}
    if dynamic:
        params["dynamicTools"] = [TOOL_SPEC]
    return raw(client, "thread/start", params)["thread"]["id"]


def mode_tool_turn(args) -> dict:
    state = {"value": "vx-" + secrets.token_hex(6)}
    host = ToolHost(state["value"])
    rec: dict = {"mode": "tool-turn"}
    with CodexClient(make_config(args, ISOLATE), approval_handler=host) as client:
        client.initialize()
        rec["limits_before"] = limits_snapshot(client)
        thread_id = start_thread(client, args, True,
                                 "You are a test worker. Use only the vault_lookup tool when asked; run no shell commands.")
        state["thread_id"] = thread_id
        started = client.turn_start(thread_id, "Call the vault_lookup tool with key \"alpha\". "
                                    "Remember the exact value it returns for later. Reply with only the word STORED.",
                                    {"model": MODEL})
        turn_id = started.turn.id
        events, completed = collect(client, turn_id, now() + args.deadline)
        rec["thread_path_name"] = Path(thread_path(client, thread_id) or "").name
        rec["limits_after"] = limits_snapshot(client)
        rollout = rollout_token_counts(thread_path(client, thread_id))
    rec.update(summarize(events))
    rec["turn_completed"] = completed
    rec["tool_host_calls"] = host.calls
    rec["other_server_requests"] = host.other_requests
    rec["tool_round_trip"] = (len(host.calls) >= 1 and all(c["answered"] for c in host.calls)
                             and any(t.get("tool") == "vault_lookup" and t.get("status") == "completed"
                                     for t in rec["tool_items"]))
    rec["host_mcp_tool_items"] = [t for t in rec["tool_items"] if t.get("server")]
    rec["rollout"] = rollout
    args.state.write_text(json.dumps(state))
    os.chmod(args.state, 0o600)
    return rec


def mode_resume_turn(args) -> dict:
    state = json.loads(args.state.read_text())
    rec: dict = {"mode": "resume-turn", "new_process_pid": os.getpid()}
    with CodexClient(make_config(args, ISOLATE), approval_handler=ToolHost("not-the-value")) as client:
        client.initialize()
        resumed = raw(client, "thread/resume", {"threadId": state["thread_id"], "model": MODEL,
                                                "cwd": str(args.workspace.resolve()),
                                                "sandbox": "read-only", "approvalPolicy": "never"})
        rec["resumed_thread_matches"] = (resumed.get("thread") or {}).get("id") == state["thread_id"]
        started = client.turn_start(state["thread_id"],
                                    "Without calling any tool, what exact value did vault_lookup return earlier "
                                    "in this conversation? Reply with only that value.", {"model": MODEL})
        events, completed = collect(client, started.turn.id, now() + args.deadline)
        answer = "".join(e.get("delta", "") for e in events)
        items = raw(client, "thread/read", {"threadId": state["thread_id"], "includeTurns": True})
    turns = (items.get("thread") or {}).get("turns") or []
    last_msgs = [it.get("text") for it in (turns[-1].get("items") if turns else []) if it.get("type") == "agentMessage"]
    final = (last_msgs[-1] or "").strip() if last_msgs else ""
    rec.update(summarize(events))
    rec["turn_completed"] = completed
    rec["turns_in_thread"] = len(turns)
    rec["final_answer_matches_turn1_tool_value"] = final.strip().strip("`\"'. ") == state["value"]
    rec["final_answer_contains_value"] = state["value"] in final
    rec["turn2_prompt_contains_value"] = False  # value never sent in the turn-2 prompt
    return rec


def mode_cancel(args) -> dict:
    rec: dict = {"mode": "cancel", "interrupt_after_seconds": args.interrupt_after, "effort": args.effort}
    with CodexClient(make_config(args, ISOLATE)) as client:
        client.initialize()
        rec["limits_before"] = limits_snapshot(client)
        thread_id = start_thread(client, args, False, "You are a test worker. Run no tools.")
        started = client.turn_start(thread_id, "Without using any tool, write a detailed 3000-word essay on the "
                                    "history of double-entry bookkeeping, with numbered sections.",
                                    {"model": MODEL, **({"effort": args.effort} if args.effort else {})})
        turn_id = started.turn.id
        rec["turn_started_at"] = now()
        first_delta = threading.Event()

        def on_event(e):
            if e["method"] in ("item/agentMessage/delta", "item/reasoning/summaryTextDelta", "item/reasoning/textDelta"):
                first_delta.set()

        box: dict = {}
        collector = threading.Thread(target=lambda: box.update(
            zip(("events", "completed"), collect(client, turn_id, now() + args.deadline, on_event))), daemon=True)
        collector.start()
        first_delta.wait(args.interrupt_after)
        rec["streaming_observed_before_interrupt"] = first_delta.is_set()
        time.sleep(2 if first_delta.is_set() else 0)
        rec["interrupt_requested_at"] = now()
        rec["interrupt_response"] = client.turn_interrupt(thread_id, turn_id).model_dump(mode="json", by_alias=True)
        collector.join(args.deadline)
        events, completed = box.get("events", []), box.get("completed")
        rec["turn_completed"] = completed
        rec.update(summarize(events))
        rec["events_after_interrupt"] = sum(1 for e in events if e["at"] > rec["interrupt_requested_at"])
        rec["deltas_after_completed"] = sum(1 for e in events if completed and e["at"] > completed["at"])
        time.sleep(args.settle)
        path = thread_path(client, thread_id)
        rec["rollout_after_settle"] = rollout_token_counts(path)
        rec["limits_after"] = limits_snapshot(client)
        time.sleep(args.settle)
        rec["rollout_after_second_settle"] = rollout_token_counts(path)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("config-diff", "limits", "tool-turn", "resume-turn", "cancel"))
    ap.add_argument("--codex-bin", required=True)
    ap.add_argument("--codex-home", type=Path, required=True)
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--state", type=Path)
    ap.add_argument("--deadline", type=float, default=240)
    ap.add_argument("--interrupt-after", type=float, default=20)
    ap.add_argument("--settle", type=float, default=20)
    ap.add_argument("--effort", help="turn reasoning effort override for the cancel mode")
    args = ap.parse_args()
    if args.out.exists():
        ap.error("refusing to overwrite an existing output")
    started = now()
    global ISOLATE
    if args.mode != "config-diff":
        ISOLATE = resolve_isolation(args)
    fn = {"config-diff": mode_config_diff, "limits": mode_limits, "tool-turn": mode_tool_turn,
          "resume-turn": mode_resume_turn, "cancel": mode_cancel}[args.mode]
    try:
        rec = fn(args)
        rec["status"] = "ok"
        code = 0
    except Exception as error:
        rec = {"status": "failed", "error_type": type(error).__name__, "error": str(error)[:2000]}
        code = 1
    rec.update({"isolation_overrides": list(ISOLATE), "sdk": "openai-codex", "started_at": started, "finished_at": now(),
                "python_env_keys": sorted(os.environ)})
    args.out.write_text(json.dumps(rec, indent=2, default=str) + "\n")
    print(json.dumps({"mode": args.mode, "status": rec["status"]}))
    return code


if __name__ == "__main__":
    sys.exit(main())
