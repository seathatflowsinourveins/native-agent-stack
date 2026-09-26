#!/usr/bin/env python3
"""Value-free: is each production hook file already in the byte form install-hooks writes
(2-space pretty JSON, UTF-8, key order kept)? Prints booleans and counts only."""
import json
import os
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
out = {}
for name, path in (("claude_settings", HOME / ".claude/settings.json"), ("codex_hooks", HOME / ".codex/hooks.json"),
                   ("claude_settings_at_22:43Z_backup", HOME / ".claude/settings.json.bak.20260925T225148Z")):
    raw = path.read_text()
    obj = json.loads(raw)
    pretty = json.dumps(obj, indent=2, ensure_ascii=False)
    out[name] = {"fixed_point_with_trailing_newline": raw == pretty + "\n",
                 "fixed_point_without_trailing_newline": raw == pretty,
                 "has_backslash_u_escapes": "\\u" in raw,
                 "lines": raw.count("\n"),
                 "lines_differing_from_pretty": sum(1 for a, b in zip(raw.splitlines(), pretty.splitlines()) if a != b)
                 + abs(len(raw.splitlines()) - len(pretty.splitlines()))}
print(json.dumps(out, indent=1))
