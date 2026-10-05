#!/usr/bin/env python3
"""Inject the sibling main-session token-lanes text at SessionStart; fail open on errors.

SessionStart supplies source and, for `claude --agent <name>`, agent_type; its additionalContext reaches the
main session before the first prompt: https://code.claude.com/docs/en/hooks#sessionstart
Fail-open/output pattern: adoption/hooks/claude/token-lanes-subagent-start.py, whose blind-* and silent roles
receive nothing here either; docs/decisions/2026-09-27-token-lanes-subagent-start.md, main-session addendum.
"""

import json
import os
import sys

BLOCK = "token-lanes-block.main.md"
# The SubagentStart carrier's silent set: allowlisted roles that no carrier line fits receive nothing, like blind-*.
SILENT_ROLES = frozenset({"semantic-evidence-reviewer"})


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    agent_type = data.get("agent_type")
    if isinstance(agent_type, str) and (agent_type.startswith("blind-") or agent_type in SILENT_ROLES):
        return
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), BLOCK)
    with open(path, encoding="utf-8") as source:
        block = source.read()
    if not block:
        return
    output = {"hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": block,
    }}
    # Unbuffered output leaves no failing flush to change the exit status at shutdown.
    encoded = (json.dumps(output) + "\n").encode("utf-8")
    while encoded:
        encoded = encoded[os.write(1, encoded):]


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
