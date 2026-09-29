"""Native PreToolUse hook, following SDK example 33_hooks.

QMD query scoping is an argument constraint, separate from tool-name filtering.
The four-collection index itself is created by native QMD collection commands.
"""

import json
from pathlib import Path
import sys


def permitted(event):
    if event.get("tool_name") != "qmd_query":
        return True
    args = event.get("tool_input", {})
    # MCPToolAction holds the actual parameters in data at this SDK pin.
    args = args.get("data", args)
    allowed = json.loads((Path(__file__).parent / "config/mcp-policy.json").read_text())["qmd"]["collections"]
    selected = args.get("collections")
    searches = args.get("searches")
    return bool(
        isinstance(selected, list) and selected
        and all(isinstance(item, str) and item in allowed for item in selected)
        and isinstance(searches, list) and searches
        and all(isinstance(item, dict) and item.get("type") == "lex" for item in searches)
        and args.get("rerank") is False and not args.get("query")
    )


def main():
    if not permitted(json.load(sys.stdin)):
        print(json.dumps({"decision": "deny", "reason": "Use explicit allowed collections, lex searches and rerank:false."}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
