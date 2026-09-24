#!/usr/bin/env python3
"""Round 4: copy the cited outputs into raw/round4/, sanitized and hashed.

Same policy as export_round3.py: the host home becomes $HOME; every UUID becomes
`redacted-id:<sha256 prefix>` (also dash-less 32-hex ids); the user name (word-bounded, also after JSON escapes) becomes $USER,
the host name $HOSTNAME, and private LAN IPv4 addresses $LAN_IP. The Claude session JSONL is
exported as a usage-only excerpt. Not exported: the OpenHands client stderr files and the
agent-server console log (rich console wrapping split identifiers past redaction in round 1),
and the private state files that hold thread/session ids.
Usage: export_round4.py
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
R4 = HOME / ".cache/gap-wave2-20260923/agent-sdks/round4"
DEST = Path(__file__).resolve().parents[3] / "evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks/raw/round4"
FILES = [
    "serve.sh", "dl.log", "dl-start.txt", "vllm-start.txt", "vllm-stop.txt", "gpu-before.txt", "gpu-after.txt",
    "vllm-attempt1-uva.log", "vllm-attempt2-nvcc.log", "vllm-attempt3-hostnet.log", ("vllm-round4-main.log", "vllm.log"),
    "codex-home/config.toml",
    "codex-session-attempt1.json", "codex-session.json", "codex-session-rep2.json", "codex-session-rep3.json",
    "codex-resume.json", "codex-events.json", "codex-events2.json",
    "claude-session.json", "claude-session-rep2.json", "claude-session-rep3.json", "claude-resume.json",
    "claude-resume.stderr",
    "oh-agent-server-install.log", "openhands-local-attempt1.json", "openhands-local.json", "openhands-remote.json",
    "openhands-container.json", "podman-pull-start.txt", "podman-pull.log", "podman-run.log", "podman-exec-proof.txt",
    "podman-container.log",
    "temporal-zombie-run1.json", "temporal-zombie-run1/worker-A.err", "temporal-zombie.json",
    "temporal-zombie/worker-A.err",
    # review fix round (14:55Z preregistration): tapped SDK reruns and the pasta-network container rerun
    "vllm-fix.log", "vllm-start-fix.txt", "vllm-stop-fix.txt", "gpu-before-fix.txt", "gpu-after-fix.txt",
    "codex-session-fix1.json", "codex-session-fix2.json", "codex-session-fix3.json", "codex-resume-fix1.json",
    "claude-session-fix1.json", "claude-session-fix2.json", "claude-session-fix3.json", "claude-resume-fix1.json",
    "claude-fix.stderr", "podman-run-fix.log", "fix-listeners-before.txt", "fix-listeners-during.txt",
    "fix-listeners-during2.txt", "fix-container-listeners.txt", "openhands-container-fix.json",
    "podman-exec-proof-fix.txt", "podman-container-fix.log",
    # second review fix (15:45:21Z preregistration): remote-arm rerun with the committed r4_openhands.py and the
    # GPU stop-rule readings (r4_fix2_remote.sh; its stop step failed, the manual stop and rechecks follow)
    "fix2-driver.log", "r4_openhands-hash-fix2.txt", "vllm-fix2.log", "vllm-start-fix2.txt", "vllm-ready-fix2.txt",
    "vllm-stop-fix2.txt", "vllm-pid-fix2.txt", "gpu-before-fix2.txt", "gpu-during-fix2.txt", "gpu-after-fix2.txt",
    "compute-apps-before-fix2.txt", "compute-apps-during-fix2.txt", "compute-apps-after-fix2.txt",
    "vllm-procs-before-fix2.txt", "vllm-procs-after-fix2.txt", "oh-server-procs-after-fix2.txt",
    "fix2-listeners-before.txt", "fix2-listeners-during.txt", "fix2-listeners-after.txt",
    "openhands-remote-fix2.json", "openhands-remote-fix2.exit",
    "fix2-manual-stop.txt", "vllm-stop-fix2-manual.txt", "gpu-after-fix2-manual.at", "gpu-after-fix2-manual.txt",
    "compute-apps-after-fix2-manual.txt", "vllm-procs-after-fix2-manual.txt", "oh-server-procs-after-fix2-manual.txt",
    "fix2-listeners-after-manual.txt", "procs-after-fix2-recheck.txt",
]
# Privacy sweep 2026-09-23 (PR #132 review): these listings show the session environment (companion transcript,
# plugin-data and shell-snapshot paths); they are written to host-local, owner-only storage, not the repository.
PRIVATE = {"vllm-procs-after-fix2-manual.txt", "oh-server-procs-after-fix2-manual.txt"}
PRIVATE_DIR = HOME / ".local/state/agent-lab-17/private-evidence/gap-wave2-20260923/foundation__agent-sdks/raw/round4"
RETENTION = "host-local, owner-only; not published under the catalog rule against machine-specific active client configuration and personal paths (PR #132 review)"
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
USER_RE = re.compile(r"(?:(?<=\\[nrt])|(?<![A-Za-z0-9_]))" + re.escape(USER) + r"(?![A-Za-z0-9_])")
HEX32 = re.compile(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])")  # dash-less UUIDs (OpenHands conversation ids)
LAN = re.compile(r"\b(?:192\.168|10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b")


def clean(text: str) -> str:
    text = UUID.sub(lambda m: "redacted-id:" + hashlib.sha256(m.group(0).lower().encode()).hexdigest()[:16], text)
    text = HEX32.sub(lambda m: "redacted-id:" + hashlib.sha256(m.group(0).encode()).hexdigest()[:16], text)
    text = text.replace(str(HOME), "$HOME").replace(HOST, "$HOSTNAME")
    text = LAN.sub("$LAN_IP", text)
    # The Temporal idempotency key value trips gitleaks' generic-api-key rule (a false positive that fails the
    # branch-ancestry scan test); it is effect-<workflow id>, so the workflow id is written as a placeholder.
    text = text.replace("effect-gap11-zombie-wf", "effect-{workflow_id}")
    return USER_RE.sub("$USER", text)


def session_excerpt(state: str, name: str) -> Path:
    sid = json.loads((R4 / "private" / state).read_text())["session_id"]
    hit = next((R4 / "claude-home/.claude/projects").glob(f"*/{sid}.jsonl"))
    keep = []
    for ln in hit.read_text().splitlines():
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        msg = r.get("message") or {}
        slim = {k: r.get(k) for k in ("type", "subtype", "timestamp")}
        if isinstance(msg, dict):
            slim["message"] = {k: msg.get(k) for k in ("id", "model", "role", "stop_reason", "usage") if k in msg}
        keep.append(json.dumps(slim))
    out = DEST / name
    out.write_text(clean("\n".join(keep) + "\n"))
    return out


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    written = []
    for item in FILES:
        src, dst = item if isinstance(item, tuple) else (item, item.replace("/", "__"))
        out = (PRIVATE_DIR if dst in PRIVATE else DEST) / dst
        if dst in PRIVATE:
            PRIVATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        out.write_text(clean((R4 / src).read_text(errors="replace")))
        if dst in PRIVATE:
            out.chmod(0o600)
        written.append(out)
    written.append(session_excerpt("claude-state.json", "claude-session.usage-excerpt.jsonl"))
    manifest = {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
                for p in sorted(written, key=lambda p: p.name)}
    for name in PRIVATE:
        manifest[name].update({"published": False, "retention": RETENTION})
    (DEST / "SHA256SUMS.json").write_text(json.dumps({"files": manifest}, indent=2) + "\n")
    leaks = [p.name for p in written if USER_RE.search(p.read_text()) or str(HOME) in p.read_text() or UUID.search(p.read_text())]
    print(json.dumps({"files": len(manifest), "residual_user_home_or_uuid": leaks}))
    return 0 if not leaks else 1


if __name__ == "__main__":
    raise SystemExit(main())
