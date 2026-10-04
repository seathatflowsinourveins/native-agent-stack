#!/usr/bin/env python3
"""Do the `--selftest` controls of a tmux probe notice when the safety checks of the server identity or of the control's cleanup are removed? (findings F7 of the post-merge read, U1 and U12 of the post-merge GPT read and B3 of the Codex review bot's read of the repairs, 2026-10).
`server_identity` decides which process the probe may signal. Five mutated copies under /var/tmp, each of which must make the copy's selftest FAIL in the named control while the unmutated probe's selftest passes:
  (a) the comparison of the command line is removed (any process named `tmux: server` is accepted): the control that answers the pid of ANOTHER tmux server fails;
  (b) the socket argument is compared as a substring instead of exactly: only the control that answers the pid of a server whose socket path has ours as a prefix fails;
  (c) the servers that a control caused are not stopped when the measurement raises: the cleanup control fails (the leaked servers end by themselves within two minutes: their panes are `sleep 120`);
  (d) the socket directories of a failing control are not removed: the cleanup control fails (and the shutdown-failure control, which keeps the sockets of three of its modes until its own cleanup);
  (e) the removal is not scoped to the directories this probe made (any parent of a recorded socket goes): the scope control fails.
A mutant that removes a cleanup leaves what the cleanup would have removed: after each run the socket directories of the probe's own shape (`tb` or `ts` plus eight characters) that the run made are emptied by stopping their servers by exact socket path and removed. Prints one line per run and a verdict. Exit 0 when the unmutated selftest passes and every mutant is caught by the named control, 1 otherwise. Needs tmux. usage: tmux_identity_mutant.py <checkout> <bell|sync>"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

checkout, which = Path(sys.argv[1]).resolve(), sys.argv[2]
relative = {"bell": "evidence/artifacts/notification-types-20260929/tmux_bell_probe.py", "sync": "evidence/artifacts/terminal-lane-cross-family-review-20260930/tmux_sync_probe.py"}[which]
text = (checkout / relative).read_text(encoding="utf-8")
COMPARISON = ' or b"-S" not in argv or argv[argv.index(b"-S") + 1] != socket'
EXACT = 'argv[argv.index(b"-S") + 1] != socket'
CLEANUP = ('                for each in sorted(known):\n'
           '                    subprocess.run([real, "-S", each, "kill-server"], capture_output=True)      # by exact socket path, never by pid or by name\n')
REMOVAL = "                        remove_work_directory(each)      # the directory of a socket of ours: also when the measurement raised something other than ServerNotStopped\n"
SCOPE_TEST = '    if parent.parent == Path("/tmp") and re.fullmatch(WORK_PREFIX + "[a-z0-9_]{8}", parent.name):\n'
MUTANTS = [
    ("the comparison of the command line is removed", COMPARISON, "", "FAIL shutdown-failure control"),
    ("the socket argument is compared as a substring", EXACT, 'socket not in argv[argv.index(b"-S") + 1]', "FAIL shutdown-failure control"),
    ("the servers of a failing control are not stopped", CLEANUP, "                pass\n", "FAIL cleanup control"),
    ("the socket directories of a failing control are not removed", REMOVAL, "                        pass\n", "FAIL cleanup control"),
    ("the removal is not scoped to this probe's own directories", SCOPE_TEST, "    if True:\n", "FAIL scope control"),
]
verdicts = []
SHAPE = re.compile(r"t[bs][a-z0-9_]{8}")


def work_directories():
    return frozenset(path for path in Path("/tmp").iterdir() if path.is_dir() and SHAPE.fullmatch(path.name))


def remove_leftovers(before):
    """Stop the servers on the sockets of the directories this run made, by exact socket path, and remove the directories."""
    for directory in sorted(work_directories() - before):
        for entry in directory.iterdir():
            subprocess.run(["tmux", "-S", str(entry), "kill-server"], capture_output=True)
        shutil.rmtree(directory, ignore_errors=True)


for label, body in [("unmutated", text)] + [(name, None) for name, *_rest in MUTANTS]:
    if body is None:
        old, new, expected = next((o, n, e) for name, o, n, e in MUTANTS if name == label)
        assert text.count(old) == 1, f"{label}: the mutation site was not found exactly once ({text.count(old)})"
        body = text.replace(old, new)
    else:
        expected = None
    before = work_directories()
    with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="tim-") as raw:
        path = Path(raw) / "probe.py"
        path.write_text(body, encoding="utf-8")
        try:
            run = subprocess.run([sys.executable, "-B", str(path), "--selftest"], capture_output=True, text=True, timeout=900)
        finally:
            remove_leftovers(before)
    lines = [line.split(":")[0] for line in run.stdout.splitlines() if "control" in line.split(":")[0]]
    caught = expected is not None and run.returncode != 0 and expected in lines
    verdicts.append((label, run.returncode == 0) if expected is None else (label, caught))
    print(f"{which}, {label}: exit {run.returncode} | {lines}" + ("" if expected is None else f" | caught by '{expected}': {caught}"), flush=True)
unmutated_ok = verdicts[0][1]
caught_all = all(ok for _label, ok in verdicts[1:])
print(f"the unmutated selftest passes: {unmutated_ok}; every mutant is caught by the named control: {caught_all}")
sys.exit(0 if unmutated_ok and caught_all else 1)
