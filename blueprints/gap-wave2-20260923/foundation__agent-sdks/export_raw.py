#!/usr/bin/env python3
"""Copy cited raw outputs into the layer evidence directory, sanitized and hashed.

Sanitization: the host home prefix becomes $HOME; native Codex thread ids, the
Claude session id and every other UUID become `redacted-id:<sha256 prefix>` (the
README policy and scripts/validate.py keep native identifiers out of published
artifacts); the user name in path-derived ids and the host name are replaced too.
Rollout and Claude session
logs are exported as excerpts: only token accounting / abort lines, verbatim apart
from the same substitutions. Everything else is copied whole.
"""
from __future__ import annotations

import hashlib
import json
import re
import socket
import sys
from pathlib import Path

HOME = str(Path.home())
USER = Path.home().name
HOST = socket.gethostname()
RUNS = Path(sys.argv[1])
DEST = Path(sys.argv[2])
FILES = ["config-diff.json", "limits.json", "tool-turn.json", "resume-turn.json", "cancel.json",
         "cancel-streaming.json", "claude-interrupt.json", "worker-persist-t1.json", "worker-resume-t2.json",
         "worker-t1.prompt", "worker-t2.prompt", "c4-inspect.json", "c4-t1.json", "c4-t2.json", "c4-t3.json",
         "c4-t1-root.json", "c4-t1.prompt", "c4-t2.prompt", "c4-t3.prompt", "langgraph-start.json",
         "langgraph-resume.json", "temporal-restart.json", "openhands-first.json", "openhands-reload.json",
         "openhands-install.log", "gap8-runs.json", "sdk-0155-fresh-prefix.log", "c4-inspect-fresh.json",
         # fix round 2: tool turn and resume through the committed worker; Context Mode window scan
         "worker-tool-t1.json", "worker-tool-t2.json", "worker-tool-runs.json", "worker-tool-t1.prompt",
         "worker-tool-t2.prompt", "ctxmode-c4-window.json"]
# stderr logs of the OpenHands runs are not exported: rich console wrapping splits UUIDs across
# lines, which defeats redaction; gap8-runs.json keeps each run's exit code instead.


def ids() -> dict[str, str]:
    found: set[str] = set()
    state = json.loads((RUNS / "tool-state.json").read_text())
    found.add(state["thread_id"])
    for name in ("worker-persist-t1.json", "worker-resume-t2.json", "worker-tool-t1.json", "worker-tool-t2.json"):
        tid = json.loads((RUNS / name).read_text()).get("thread_id")
        if tid:
            found.add(tid)
    for name in ("tool-turn.json", "cancel.json", "cancel-streaming.json"):
        text = (RUNS / name).read_text()
        found.update(re.findall(r"rollout-[0-9T:-]+-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", text))
    sid = json.loads((RUNS / "claude-interrupt.json").read_text()).get("session_id")
    if sid:
        found.add(sid)
    return {i: "redacted-id:" + hashlib.sha256(i.encode()).hexdigest()[:16] for i in found}


UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)


def clean(text: str, mapping: dict[str, str]) -> str:
    for raw, red in mapping.items():
        text = text.replace(raw, red)
    # Every other UUID (turn, item, message, conversation ids) is replaced the same way,
    # deterministically, so equal ids stay equal inside and across files.
    text = UUID.sub(lambda m: "redacted-id:" + hashlib.sha256(m.group(0).lower().encode()).hexdigest()[:16], text)
    text = text.replace(HOME, "$HOME").replace("home-" + USER + "-", "home-$USER-")
    text = text.replace(f"username='{USER}'", "username='$USER'").replace(HOST, "$HOSTNAME")
    return text


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    mapping = ids()
    written = []
    for name in FILES:
        out = DEST / name
        out.write_text(clean((RUNS / name).read_text(), mapping))
        written.append(out)
    # Rollout excerpts: token_count / task and abort events only.
    for name in ("tool-turn.json", "cancel.json", "cancel-streaming.json"):
        rec = json.loads((RUNS / name).read_text())
        roll = (rec.get("rollout") or rec.get("rollout_after_second_settle") or {}).get("rollout_name")
        hits = list((Path(HOME) / ".codex" / "sessions").rglob(roll)) if roll else []
        if hits:
            keep = [ln for ln in hits[0].read_text().splitlines()
                    if '"type":"token_count"' in ln or '"type":"turn_aborted"' in ln
                    or '"type":"task_started"' in ln or '"type":"task_complete"' in ln]
            out = DEST / (Path(name).stem + ".rollout-excerpt.jsonl")
            out.write_text(clean("\n".join(keep) + "\n", mapping))
            written.append(out)
    sid = json.loads((RUNS / "claude-interrupt.json").read_text()).get("session_id")
    hits = list((Path(HOME) / ".claude" / "projects").glob(f"*/{sid}.jsonl")) if sid else []
    if hits:
        keep = []
        for ln in hits[0].read_text().splitlines():
            try:
                rec = json.loads(ln)
            except json.JSONDecodeError:
                continue
            msg = rec.get("message") or {}
            if isinstance(msg, dict) and isinstance(msg.get("usage"), dict):
                slim = {k: rec.get(k) for k in ("type", "timestamp", "uuid", "parentUuid", "sessionId", "version")}
                slim["message"] = {k: msg.get(k) for k in ("id", "model", "stop_reason", "usage")}
                keep.append(json.dumps(slim))
            elif "interrupt" in ln.lower():
                keep.append(json.dumps({k: rec.get(k) for k in ("type", "timestamp", "uuid", "sessionId")}
                                       | {"interrupt_marker": True}))
        out = DEST / "claude-interrupt.session-usage-excerpt.jsonl"
        out.write_text(clean("\n".join(keep) + "\n", mapping))
        written.append(out)
    manifest = {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
                for p in sorted(written)}
    (DEST / "SHA256SUMS.json").write_text(json.dumps({"redacted_ids": len(mapping), "files": manifest}, indent=2) + "\n")
    print(json.dumps({"files": len(manifest), "redacted_ids": len(mapping)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
