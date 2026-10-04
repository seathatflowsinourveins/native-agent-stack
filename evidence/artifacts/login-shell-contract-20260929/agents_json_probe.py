#!/usr/bin/env python3
"""Measure what `claude agents --json` prints on this host: how many rows, of which kinds and statuses, which fields, and whether
`--cwd` (a path that holds no session) and `--all` change it. Read-only: the command starts no session and makes no model call. Prints
counts, kinds and field names only, never a name, path or session id. This is a live snapshot of the host's sessions.
usage: python3 -B agents_json_probe.py
"""
import json, re, subprocess
from collections import Counter
from pathlib import Path

CLAUDE = str(Path.home() / ".local/bin/claude")


def rows(*extra):
    run = subprocess.run([CLAUDE, "agents", "--json", *extra], capture_output=True, text=True, timeout=90, cwd="/tmp")
    return json.loads(run.stdout) if run.returncode == 0 else None


def describe(found):
    if found is None:
        return None
    return {"rows": len(found), "kinds": dict(Counter(r.get("kind") for r in found)), "statuses": dict(Counter(r.get("status") for r in found)),
            "fields": sorted({k for r in found for k in r})}


help_text = subprocess.run([CLAUDE, "agents", "--help"], capture_output=True, text=True, timeout=60).stdout
match = re.search(r"^\s+--json\s+(.*?)(?=^\s+-{1,2}[A-Za-z]|\Z)", help_text, re.M | re.S)
json_flag = " ".join(match.group(1).split()) if match else None
print(json.dumps({"help_text_for_json_flag": json_flag, "default": describe(rows()), "cwd_with_no_session": describe(rows("--cwd", "/var/empty")),
                  "all": describe(rows("--all"))}, indent=2))
