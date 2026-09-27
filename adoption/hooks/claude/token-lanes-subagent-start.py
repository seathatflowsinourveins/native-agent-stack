#!/usr/bin/env python3
"""Inject sibling token-lanes text for non-blind subagents; fail open on errors.

SubagentStart supplies agent_type: https://code.claude.com/docs/en/hooks#subagentstart
Fail-open/output pattern: adoption/hooks/claude/effort-default-guard.py.
"""

import json
import os
import sys


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    agent_type = data.get("agent_type")
    if isinstance(agent_type, str) and agent_type.startswith("blind-"):
        return
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token-lanes-block.md")
    with open(path, encoding="utf-8") as source:
        block = source.read()
    if not block:
        return
    output = {"hookSpecificOutput": {
        "hookEventName": "SubagentStart", "additionalContext": block,
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
