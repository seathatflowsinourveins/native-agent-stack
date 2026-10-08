#!/usr/bin/env python3
"""Route marked coordinators' search to research; record targeted fetch attempts.

Claude Code 2.1.294 hook protocol: https://code.claude.com/docs/en/hooks
(`PreToolUse` input/decision control and `UserPromptSubmit` input/decision control;
primary docs checked 2026-10-08). Denial uses hookSpecificOutput, not a top-level
decision. Fetch warnings use additionalContext without permissionDecision or
updatedInput, so the client's normal permissions still apply.

Correction 2026-10-08: the live unversioned UserPromptSubmit documentation led
to an earlier top-level additionalContext implementation. Installed 2.1.294
requires it inside hookSpecificOutput: public native binary SHA-256
27122ca7b624f537546fbef35b80c66370d974ff258f3d9b10ac50bb8771f262;
output schema at byte 211365006, nested UserPromptSubmit at 211365933, and
translation at 215326530. The installed contract governs both event outputs.

Only coordinator launchers supply NAS_RESEARCH_COORDINATOR_ROLE (command-center
or co-op) and NAS_RESEARCH_COORDINATOR_SESSION_ID matching the native session_id.
An inherited marker cannot mark a new lane or research session. A nonempty
agent_id also exempts a subagent when provided, but the documented PreToolUse
common schema does not guarantee that field: in-process subagents sharing a
marked session cannot be promised an exemption on that basis.

UserPromptSubmit resets the per-turn fetch count. PreToolUse records one JSONL
entry per requested URL, retaining the latest 256 entries per session. This is
an attempt log, not proof the tool passed permissions or the claim was verified.
Neither credentials/configuration nor the transcript are read. URL userinfo,
fragments and credential query parameters are omitted; only the supplied claim
or source label is logged, never headers or the complete tool payload.

Unmarked calls are silent and create no state. Search denial needs no state I/O.
Marked fetch/log/reset failures produce an explicit verification-unavailable
warning and leave normal permissions intact; malformed marked hook input exits
1 with a payload-free error (Claude's native nonblocking error contract).
"""

import fcntl
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROLES = {"command-center", "co-op"}
FETCH_TOOLS = {
    "WebFetch",
    "mcp__context_mode__ctx_fetch_and_index",
    "mcp__context-mode__ctx_fetch_and_index",
    "mcp__plugin_context-mode_context-mode__ctx_fetch_and_index",
}
DISPATCH = "tools/research/dispatch --question '<research question>'"
MAX_LOG_LINES = 256
MAX_CLAIM_CHARS = 320
NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
SECRET_KEY = re.compile(
    r"(?:password|passwd|secret|token|api[-_]?key|access[-_]?key|"
    r"credential|signature|authorization|auth|^key$)", re.I
)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def safe_url(value):
    """Keep public citation parameters; discard URL-carried credential fields."""
    try:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return "[non-HTTP URL omitted]"
        query = [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
                 if not SECRET_KEY.search(key)]
        # rsplit removes both username and password without retaining either.
        return urlunsplit((parts.scheme, parts.netloc.rsplit("@", 1)[-1],
                           parts.path, urlencode(query), ""))
    except (TypeError, ValueError):
        return "[invalid URL omitted]"


def safe_claim(value):
    if not isinstance(value, str) or not value.strip():
        return "unprovided"
    text = " ".join(value.split())
    text = re.sub(r"https?://[^\s<>\"']+", lambda m: safe_url(m.group()), text)
    text = re.sub(r"(?i)\b(?:bearer|basic)\s+[^\s,;]+", "[authorization omitted]", text)
    text = re.sub(
        r"(?i)\b(password|passwd|secret|token|api[-_]?key|access[-_]?key|"
        r"credential|signature|authorization|auth)[\"']?\s*[:=]\s*[\"']?[^\s,;]+",
        r"\1=[omitted]", text,
    )
    return text[:MAX_CLAIM_CHARS]


def fetch_items(tool, tool_input):
    if not isinstance(tool_input, dict):
        raise ValueError("missing native tool_input")
    if tool == "WebFetch":
        requests = [{"url": tool_input.get("url"), "prompt": tool_input.get("prompt")}]
    else:
        requests = tool_input.get("requests") or [{"url": tool_input.get("url")}]
    if not isinstance(requests, list) or not requests:
        raise ValueError("missing fetch requests")
    items = []
    for request in requests:
        if not isinstance(request, dict) or not isinstance(request.get("url"), str):
            raise ValueError("missing fetch URL")
        candidates = (("prompt", request.get("prompt")),) if tool == "WebFetch" else (
            ("source", request.get("source")), ("intent", tool_input.get("intent")),
            ("source", tool_input.get("source")),
        )
        claim_source, claim = next(
            ((source, value) for source, value in candidates
             if isinstance(value, str) and value.strip()), ("unprovided", "unprovided"),
        )
        items.append({"url": safe_url(request["url"]), "claim_checked": safe_claim(claim),
                      "claim_source": claim_source})
    return items


def read_private(path):
    fd = os.open(path, os.O_RDONLY | NOFOLLOW)
    with os.fdopen(fd, encoding="utf-8") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise OSError("research state is not a regular file")
        return stream.read()


def write_private(path, text):
    fd, temporary = tempfile.mkstemp(prefix=".research-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def update_state(session, role, event, tool=None, items=None):
    state_root = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    directory = (state_root / "native-agent-stack/research-routing" /
                 hashlib.sha256(session.encode("utf-8")).hexdigest())
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    if directory.is_symlink():
        raise OSError("research state directory is a symlink")
    lock_fd = os.open(directory / "lock", os.O_CREAT | os.O_RDWR | NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, "r+") as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise OSError("research state lock is not a regular file")
        fcntl.flock(lock, fcntl.LOCK_EX)
        counter = directory / "turn.json"
        if event == "UserPromptSubmit":
            write_private(counter, json.dumps({"turn_started_utc": utc_now(), "fetches": 0}) + "\n")
            return 0
        try:
            current = json.loads(read_private(counter))
        except FileNotFoundError:
            current = {"turn_started_utc": None, "fetches": 0}
        if (not isinstance(current, dict) or type(current.get("fetches")) is not int
                or current["fetches"] < 0):
            raise ValueError("invalid research turn state")
        log = directory / "verification.jsonl"
        try:
            records = deque(read_private(log).splitlines(), maxlen=MAX_LOG_LINES)
        except FileNotFoundError:
            records = deque(maxlen=MAX_LOG_LINES)
        for item in items:
            current["fetches"] += 1
            records.append(json.dumps({
                "session_id": session, "role": role, "utc": utc_now(), "tool": tool,
                "stage": "requested", "turn_started_utc": current.get("turn_started_utc"),
                "fetches_this_turn": current["fetches"], **item,
            }, ensure_ascii=False))
        write_private(log, "\n".join(records) + "\n")
        write_private(counter, json.dumps(current) + "\n")
        return current["fetches"]


def emit(event, **fields):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, **fields}}))


def main():
    role = os.environ.get("NAS_RESEARCH_COORDINATOR_ROLE")
    marker = os.environ.get("NAS_RESEARCH_COORDINATOR_SESSION_ID")
    if role not in ROLES or not marker:
        return 0
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("hook input must be an object")
    except (ValueError, OSError):
        print("Research routing guard: invalid native hook input; scope could not be established.",
              file=sys.stderr)
        return 1
    session = payload.get("session_id")
    if not isinstance(session, str) or session != marker or payload.get("agent_id"):
        return 0
    event = payload.get("hook_event_name")
    tool = payload.get("tool_name")
    if event == "PreToolUse" and tool == "WebSearch":
        emit(event, permissionDecision="deny", permissionDecisionReason=(
            f"Coordinator research must use the research runtime. Run {DISPATCH}; "
            "it returns a cited result file. Targeted primary-source WebFetch remains available."
        ))
        return 0
    if event != "UserPromptSubmit" and not (event == "PreToolUse" and tool in FETCH_TOOLS):
        return 0
    try:
        items = fetch_items(tool, payload.get("tool_input")) if event == "PreToolUse" else None
        count = update_state(session, role, event, tool, items)
    except (OSError, ValueError, TypeError) as error:
        emit(event, additionalContext=(
            f"Research routing verification unavailable ({type(error).__name__}); "
            "the fetch log or turn reset did not complete. Normal client permissions still apply. "
            f"Route research with {DISPATCH}."
        ))
        return 0
    if event == "PreToolUse" and count >= 3:
        emit(event, additionalContext=(
            f"Research verification fetch count this turn: {count}. Three or more fetches "
            f"in one turn counts as research; use {DISPATCH}. Normal client permissions still apply."
        ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
