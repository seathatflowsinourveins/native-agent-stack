#!/usr/bin/env python3
"""Round 3: copy the cited private outputs into raw/round3/, sanitized and hashed.

Same policy as export_raw.py: the host home becomes $HOME; every UUID (thread, turn, item and
session ids) becomes `redacted-id:<sha256 prefix>`; the user name (word-bounded) becomes $USER
and the host name $HOSTNAME. The resumed Claude session is exported as a usage-only excerpt of
the lines this round appended. The generated native schema is recorded by sha256 and size only.
Usage: export_round3.py
"""
from __future__ import annotations

import hashlib
import json
import re
import socket
from pathlib import Path

HOME = Path.home()
USER = HOME.name
HOST = socket.gethostname()
R3 = HOME / ".cache/gap-wave2-20260923/agent-sdks/round3"
DEST = Path(__file__).resolve().parents[3] / "evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks/raw/round3"
FILES = {  # destination name -> source relative to R3
    **{f"step-{s}.json": f"runs/step-{s}.json" for s in (
        "stage", "controls", "config", "worker-bare", "events", "worker-ctxmode", "claude-resume",
        "schema-attempt1", "schema-attempt2", "schema-attempt3", "schema-attempt4", "schema-attempt5-prereview", "schema", "mcp-startup",
        "stage-np", "config-np", "mcp-startup-np", "worker-bare-np")},
    "config-parent.json": "runs/config-parent.json",
    "claude-resume.json": "runs/claude-resume.json",
    "schema-dispatch.json": "runs/schema-dispatch.json",
    "bare-config-iso.json": "bare/out/config-iso.json",
    "bare-worker-iso.json": "bare/out/worker-iso.json",
    "bare-worker-iso.prompt": "bare/out/worker-iso.prompt",
    "bare-mcp-startup.json": "bare/out/mcp-startup.json",
    "bare-np-config-iso.json": "bare-np/out/config-iso.json",
    "bare-np-worker-iso.json": "bare-np/out/worker-iso.json",
    "bare-np-worker-iso.prompt": "bare-np/out/worker-iso.prompt",
    "bare-np-mcp-startup.json": "bare-np/out/mcp-startup.json",
    "events-turn.json": "events/out/events-turn.json",
    "ctxmode-config-iso.json": "ctxmode/out/config-iso.json",
    "ctxmode-c4-t2-iso.json": "ctxmode/out/c4-t2-iso.json",
    "ctxmode-c4-t2.prompt": "ctxmode/out/c4-t2.prompt",
}
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
# Word-bounded, also after a JSON escape such as \\n (whose `n` would otherwise count as a word character).
USER_RE = re.compile(r"(?:(?<=\\[nrt])|(?<![A-Za-z0-9_]))" + re.escape(USER) + r"(?![A-Za-z0-9_])")


def clean(text: str) -> str:
    text = UUID.sub(lambda m: "redacted-id:" + hashlib.sha256(m.group(0).lower().encode()).hexdigest()[:16], text)
    text = text.replace(str(HOME), "$HOME").replace(HOST, "$HOSTNAME")
    return USER_RE.sub("$USER", text)


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    written = []
    for dst, src in FILES.items():
        out = DEST / dst
        out.write_text(clean((R3 / src).read_text()))
        written.append(out)
    # Claude resume: usage-only excerpt of the lines appended by this round's query.
    rec = json.loads((HOME / ".cache/gap-wave2-20260923/agent-sdks/runs/claude-interrupt.json").read_text())
    resumed = json.loads((R3 / "runs/claude-resume.json").read_text())
    sid = rec["session_id"]
    hits = list((HOME / ".claude/projects").glob(f"*/{sid}.jsonl"))
    keep = []
    for ln in hits[0].read_text().splitlines()[resumed["session_jsonl_lines_before"]:resumed["session_jsonl_lines_after"]]:
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        msg = r.get("message") or {}
        slim = {k: r.get(k) for k in ("type", "timestamp", "sessionId")}
        if isinstance(msg, dict) and isinstance(msg.get("usage"), dict):
            slim["message"] = {k: msg.get(k) for k in ("id", "model", "stop_reason", "usage")}
        keep.append(json.dumps(slim))
    out = DEST / "claude-resume.session-appended-excerpt.jsonl"
    out.write_text(clean("\n".join(keep) + "\n"))
    written.append(out)
    schema = R3 / "schema/ServerNotification.json"
    out = DEST / "native-schema-servernotification.json"
    out.write_text(json.dumps({"file": "ServerNotification.json", "generated_by": "codex app-server generate-json-schema --experimental (codex-cli 0.155.1)",
                               "sha256": hashlib.sha256(schema.read_bytes()).hexdigest(), "bytes": schema.stat().st_size,
                               "schema_files": sum(1 for _ in (R3 / "schema").rglob("*.json"))}, indent=2) + "\n")
    written.append(out)
    # Review-2 fix outputs are written straight into DEST by stage_listing.py and a copy of otel_probe.py output.
    written += sorted(DEST.glob("review2-*.json"))
    manifest = {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size} for p in sorted(written)}
    (DEST / "SHA256SUMS.json").write_text(json.dumps({"files": manifest}, indent=2) + "\n")
    print(json.dumps({"files": len(manifest)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
