#!/usr/bin/env python3
"""Read-only acceptance: would applying the linux-wsl2 overlay change the live ~/.claude/settings.json?

On a host whose settings already carry the decision's values the answer must be no; on a new host it lists the top-level keys the merge would change.

Runs the repository's own merge tool with --dry-run (it prints the merged result and writes nothing) and compares the result with the
live file as JSON. That comparison alone cannot see the Notification matcher: the merge de-duplicates hooks by command anywhere in the event,
so a host that has the bell command in a catch-all group, or with an older and narrower matcher, merges to itself. The script therefore also
checks that exactly one Notification group holds the command and that its matcher equals the overlay's. Prints booleans and key names only,
never a value.

Revised 2026-09-30 after a cross-family review: it ignored `disableAllHooks` (a supported setting that switches every hook off) and called the result 'overlay in effect' although it reads only the USER
settings file (managed, project and local settings and command-line flags are not read). It now also needs hooks not disabled and labels the result as what it is. The review also asked for a check that
the bell hook occurs once; an independent reading of the installed client showed that it runs identical command hooks once (it de-duplicates them after matching), so a hook repeated inside one group does
not ring twice: the occurrences are printed as information and do not decide. A SECOND group that holds the command still fails, because a different matcher there would ring for other types.
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
command = wanted["hooks"][0]["command"]
groups = [g for g in live.get("hooks", {}).get("Notification", []) if isinstance(g, dict) and any(isinstance(h, dict) and h.get("command") == command for h in g.get("hooks", []))]
occurrences = sum(1 for g in live.get("hooks", {}).get("Notification", []) if isinstance(g, dict) for h in g.get("hooks", []) if isinstance(h, dict) and h.get("command") == command)
disabled = live.get("disableAllHooks") is True
print("groups holding the overlay's bell command in live:", len(groups), "| exactly one:", len(groups) == 1)
print("bell hook occurrences across the Notification event:", occurrences, "(information only: the client runs identical command hooks once)")
print("that group's matcher equals the overlay's:", len(groups) == 1 and groups[0].get("matcher") == wanted["matcher"])
print("disableAllHooks is true in the user settings:", disabled)
print("user settings file carries the overlay (merge is a no-op, one bell hook in one group, same matcher, hooks not disabled; managed, project and local settings and flags not read):",
      merged == live and len(groups) == 1 and groups[0].get("matcher") == wanted["matcher"] and not disabled)
