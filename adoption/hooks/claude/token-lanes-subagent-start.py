#!/usr/bin/env python3
"""Inject the sibling token-lanes text matched to a non-blind subagent's role; fail open on errors.

SubagentStart supplies agent_type: https://code.claude.com/docs/en/hooks#subagentstart
Fail-open/output pattern: adoption/hooks/claude/effort-default-guard.py.
Role blocks name only lanes the role's `tools:` allowlist grants (https://code.claude.com/docs/en/sub-agents);
docs/decisions/2026-09-27-token-lanes-subagent-start.md, role-matched addendum.
"""

import json
import os
import sys

# Exact agent_type -> sibling block. Unmapped types inherit tools and receive the full default block.
ROLE_BLOCKS = {
    "stack-researcher": "token-lanes-block.researcher.md",
    "stack-verifier": "token-lanes-block.verifier.md",
    "evidence-reviewer": "token-lanes-block.reviewer.md",
    "security-reviewer": "token-lanes-block.reviewer.md",
    "isolated-builder": "token-lanes-block.builder.md",
    "source-scout": "token-lanes-block.scout.md",
}
# Allowlisted roles that no carrier line fits; they receive nothing, like blind-* roles.
SILENT_ROLES = frozenset({"semantic-evidence-reviewer"})


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    agent_type = data.get("agent_type")
    name = "token-lanes-block.md"
    if isinstance(agent_type, str):
        if agent_type.startswith("blind-") or agent_type in SILENT_ROLES:
            return
        name = ROLE_BLOCKS.get(agent_type, name)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
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
