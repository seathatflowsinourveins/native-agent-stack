#!/usr/bin/env python3
"""Round 3, gap 10: one Codex SDK turn meant to emit many notification types (run inside iso_ns.sh).

The turn registers one dynamic (custom) tool through thread/start dynamicTools, and the prompt asks
for a plan update, a shell command, a file edit and the tool call. Two collectors drain the SDK's
turn queue and its global queue, so notifications without a turn id are counted too. Every received
notification is checked for typing (UnknownNotification = untyped). Usage: events_turn.py CODEX_BIN
CODEX_HOME WORKSPACE OUT
"""
from __future__ import annotations

import json
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
TOOL = {"type": "function", "name": "vault_lookup",
        "description": "Return the stored value for a key from the caller's private vault.",
        "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}},
                        "required": ["key"], "additionalProperties": False}}


class Loose(BaseModel):
    model_config = ConfigDict(extra="allow")


def main() -> int:
    codex_bin, home, ws, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    value = "ve-" + secrets.token_hex(6)
    requests: list[dict] = []

    def handler(method: str, params: dict | None) -> dict:
        requests.append({"method": method, "at": time.time()})
        if method == "item/tool/call":
            ok = (params or {}).get("tool") == "vault_lookup"
            return {"contentItems": [{"type": "inputText", "text": value if ok else "unknown tool"}], "success": ok}
        if method.endswith("requestApproval"):
            return {"decision": "decline"}
        return {}

    events: list[dict] = []
    lock = threading.Lock()

    items: list[dict] = []

    def record(source: str, n) -> None:
        typed = not isinstance(n.payload, UnknownNotification)
        with lock:
            events.append({"at": time.time(), "source": source, "method": n.method, "typed": typed})
            if typed and n.method == "item/completed":
                item = n.payload.model_dump(mode="json", by_alias=True).get("item") or {}
                items.append({"type": item.get("type"), "status": item.get("status"),
                              "text": item.get("text") if item.get("type") == "agentMessage" else None,
                              "tool": item.get("tool"), "exitCode": item.get("exitCode")})

    cfg = CodexConfig(codex_bin=codex_bin, cwd=str(ws), env={"CODEX_HOME": str(home)})
    rec: dict = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    with CodexClient(cfg, approval_handler=handler) as client:
        client.initialize()

        def drain_global():
            try:
                while True:
                    record("global", client.next_notification())
            except Exception as error:  # closed transport ends the drain
                rec["global_drain_end"] = type(error).__name__

        threading.Thread(target=drain_global, daemon=True).start()
        started = client.request("thread/start", {
            "cwd": str(ws), "model": MODEL, "ephemeral": False, "sandbox": "workspace-write",
            "approvalPolicy": "never", "dynamicTools": [TOOL],
            "developerInstructions": "You are a test worker in a disposable workspace."}, response_model=Loose)
        thread_id = started.model_dump(mode="json", by_alias=True)["thread"]["id"]
        prompt = ("Do these steps in order in this workspace: 1) create a short plan with your plan tool "
                  "(three steps) and mark steps complete as you go; 2) run the shell command `echo events-ok`; "
                  "3) create the file notes.txt containing the line `hello` using your file-editing tool; "
                  "4) call the vault_lookup tool with key \"alpha\". Finally reply with the value it returned.")
        turn = client.turn_start(thread_id, prompt, {"model": MODEL, "summary": "detailed"})
        turn_id = turn.turn.id
        deadline = time.time() + 240
        completed = None
        while time.time() < deadline:
            n = client.next_turn_notification(turn_id)
            record("turn", n)
            if n.method == "turn/completed":
                completed = n.payload.model_dump(mode="json", by_alias=True).get("turn") or {}
                break
        time.sleep(3)  # let trailing global notifications arrive
    counts: dict[str, int] = {}
    for e in events:
        counts[e["method"]] = counts.get(e["method"], 0) + 1
    documented = set(NOTIFICATION_MODELS)
    rec.update({
        "turn_status": (completed or {}).get("status"),
        "turn_error": (completed or {}).get("error"),
        "method_counts": dict(sorted(counts.items())),
        "sources": {m: sorted({e["source"] for e in events if e["method"] == m}) for m in sorted(counts)},
        "untyped_methods": sorted({e["method"] for e in events if not e["typed"]}),
        "documented_types": len(documented),
        "received_documented": sorted(set(counts) & documented),
        "received_undocumented": sorted(set(counts) - documented),
        "server_requests": sorted({r["method"] for r in requests}),
        "completed_items": items,
        "final_answer_has_tool_value": any(value in (i.get("text") or "") for i in items),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    rec["received_documented_count"] = len(rec["received_documented"])
    rec["notes_txt_created"] = (ws / "notes.txt").is_file()
    out.write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: rec[k] for k in ("turn_status", "received_documented_count", "untyped_methods")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
