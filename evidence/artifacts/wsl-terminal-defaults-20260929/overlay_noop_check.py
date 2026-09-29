#!/usr/bin/env python3
"""Read-only acceptance: would applying the linux-wsl2 overlay change the live ~/.claude/settings.json?

On a host whose settings already carry the decision's values the answer must be no; on a new host it lists the top-level keys the merge would change.

Runs the repository's own merge tool with --dry-run (it prints the merged result and writes nothing) and compares the result with the
live file as JSON. That comparison alone cannot see the Notification matcher: the merge de-duplicates hooks by command anywhere in the event,
so a host that has the bell command in a catch-all group, or with an older and narrower matcher, merges to itself. The script therefore also
checks that exactly one Notification group holds the command and that its matcher equals the overlay's. Prints booleans and key names only,
never a value.
usage: python3 -B overlay_noop_check.py <worktree>
"""
import json, subprocess, sys
from pathlib import Path

worktree = Path(sys.argv[1]).resolve()
overlay = worktree / "adoption/templates/claude.settings.linux-wsl2.overlay.json"
live_path = Path.home() / ".claude/settings.json"
run = subprocess.run([sys.executable, "-B", str(worktree / "tools/adoption/apply_claude_settings.py"), "--template", str(overlay),
                      "--target", str(live_path), "--dry-run"], capture_output=True, text=True, timeout=60)
print("dry-run exit:", run.returncode, "| stderr bytes:", len(run.stderr))
merged = json.loads(run.stdout)
live = json.loads(live_path.read_text(encoding="utf-8"))
print("merged equals live:", merged == live)
if merged != live:
    for key in sorted(list(merged) + [k for k in live if k not in merged]):
        if merged.get(key) != live.get(key):
            print("  differs at top-level key:", key, "| in live:", key in live, "| in merged:", key in merged)
    live_notify = live.get("hooks", {}).get("Notification")
    merged_notify = merged.get("hooks", {}).get("Notification")
    print("  Notification groups live/merged:", len(live_notify or []), len(merged_notify or []))

template = json.loads(overlay.read_text(encoding="utf-8"))
wanted = template["hooks"]["Notification"][0]
groups = [g for g in live.get("hooks", {}).get("Notification", []) if any(h.get("command") == wanted["hooks"][0]["command"] for h in g.get("hooks", []))]
print("groups holding the overlay's bell command in live:", len(groups), "| exactly one:", len(groups) == 1)
print("that group's matcher equals the overlay's:", len(groups) == 1 and groups[0].get("matcher") == wanted["matcher"])
print("overlay in effect (merge is a no-op, one group, same matcher):", merged == live and len(groups) == 1 and groups[0].get("matcher") == wanted["matcher"])
