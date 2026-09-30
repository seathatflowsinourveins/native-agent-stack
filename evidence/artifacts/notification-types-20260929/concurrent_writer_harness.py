#!/usr/bin/env python3
"""Test harness for replace_bell_group_controls.py: run the replacement tool in this process, with a synthetic HOME already set by the caller, and inject one other writer's save of
the live settings file at a chosen moment (the client and other tools save this file too). It edits the top-level `model` key only and prints one marker line on stderr when it does, so a
case can require that the injection really happened.
  after-merge    the save lands after the tool has merged on its private copy and before it compares the live file with its read;
  at-backup      the save lands just before the tool's backup copy is taken, so the backup holds the newer content;
  during-backup  an ATOMIC save (a new file under the same name, as the client writes it) lands after the tool's backup opened its source and before it copied it: the copy still reads the old
                 file, so the backup holds the bytes the tool read and the live file does not;
  after-backup   the save lands right after the backup copy was taken: the backup holds the bytes the tool read, the live file does not;
  at-replace     the save lands at the rename that installs the merged copy, after the tool's last comparison: the documented residual (the save is lost, and it is in neither file).
The tool's own SystemExit propagates (message on stderr, nonzero exit), so the caller sees exactly what a user would.
usage: concurrent_writer_harness.py after-merge|at-backup|during-backup|after-backup|at-replace <script> <checkout> <tool arguments ...>"""
import json, os, runpy, shutil, subprocess, sys
from pathlib import Path

MODES = ("after-merge", "at-backup", "during-backup", "after-backup", "at-replace")
mode, script, checkout, *arguments = sys.argv[1:]
if mode not in MODES:
    sys.exit("usage: concurrent_writer_harness.py " + "|".join(MODES) + " <script> <checkout> <tool arguments ...>")
live = Path.home() / ".claude/settings.json"
MARK = "harness: another writer saved the settings file"
real_replace = os.replace


def other_writer(atomic=False):
    data = json.loads(live.read_text(encoding="utf-8"))
    data["model"] = "changed-by-another-writer"
    if atomic:
        staging = live.with_name(live.name + ".other-writer")
        staging.write_text(json.dumps(data, indent=2), encoding="utf-8")
        real_replace(staging, live)
    else:
        live.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"{MARK} ({mode})", file=sys.stderr)


if mode == "after-merge":
    real_run = subprocess.run

    def run(*args, **kwargs):
        result = real_run(*args, **kwargs)
        if args and isinstance(args[0], list) and any("apply_claude_settings" in str(part) for part in args[0]):
            other_writer()
        return result

    subprocess.run = run
elif mode == "at-replace":
    def replace(source, destination, *args, **kwargs):
        if os.path.realpath(destination) == os.path.realpath(live):   # the rename that installs the merged copy
            other_writer()
        return real_replace(source, destination, *args, **kwargs)

    os.replace = replace
elif mode == "during-backup":
    real_copyfileobj = shutil.copyfileobj

    def copyfileobj(source, destination, *args, **kwargs):
        other_writer(atomic=True)   # the backup has opened its source; the copy below still reads the old file
        return real_copyfileobj(source, destination, *args, **kwargs)

    shutil.copyfileobj = copyfileobj
else:
    sys.path.insert(0, str(Path(checkout) / "tools/adoption"))
    import apply_claude_settings as acs  # the tool imports this same module object

    real_backup = acs.write_backup

    def backup(target):
        if mode == "at-backup":
            other_writer()
        made = real_backup(target)
        if mode == "after-backup":
            other_writer()
        return made

    acs.write_backup = backup
sys.argv = [script, checkout, *arguments]
runpy.run_path(script, run_name="__main__")
