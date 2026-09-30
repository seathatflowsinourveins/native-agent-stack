#!/usr/bin/env python3
"""Test harness for replace_bell_group_controls.py: run the replacement tool in this process, with a synthetic HOME already set by the caller, and inject one other writer's save of
the live settings file at a chosen moment (the client and other tools save this file too). It edits the top-level `model` key only.
  after-merge   the save lands after the tool has merged on its private copy and before it compares the live file with its read;
  at-backup     the save lands just before the tool's backup copy is taken, so the backup holds the newer content.
The tool's own SystemExit propagates (message on stderr, nonzero exit), so the caller sees exactly what a user would.
usage: concurrent_writer_harness.py after-merge|at-backup <script> <checkout> <tool arguments ...>"""
import json, runpy, subprocess, sys
from pathlib import Path

mode, script, checkout, *arguments = sys.argv[1:]
if mode not in ("after-merge", "at-backup"):
    sys.exit("usage: concurrent_writer_harness.py after-merge|at-backup <script> <checkout> <tool arguments ...>")
live = Path.home() / ".claude/settings.json"


def other_writer():
    data = json.loads(live.read_text(encoding="utf-8"))
    data["model"] = "changed-by-another-writer"
    live.write_text(json.dumps(data, indent=2), encoding="utf-8")


if mode == "after-merge":
    real_run = subprocess.run

    def run(*args, **kwargs):
        result = real_run(*args, **kwargs)
        if args and isinstance(args[0], list) and any("apply_claude_settings" in str(part) for part in args[0]):
            other_writer()
        return result

    subprocess.run = run
else:
    sys.path.insert(0, str(Path(checkout) / "tools/adoption"))
    import apply_claude_settings as acs  # the tool imports this same module object

    real_backup = acs.write_backup

    def backup(target):
        other_writer()
        return real_backup(target)

    acs.write_backup = backup
sys.argv = [script, checkout, *arguments]
runpy.run_path(script, run_name="__main__")
