#!/usr/bin/env python3
"""Discriminating control for the interrupt-window fix of `adoption_status.py --pinned-versions`.

The cross-family verification of this repair found that a SIGTERM delivered after a probe's fork but before
subprocess.Popen returned it ended the check with status 143 and left the probe running: run_version_probe
registered the group kill only once Popen had returned. A second signal as that kill began could stop it the
same way. The fix holds such an interruption back until the process is bound to its cleanup, or until the
group is killed and reaped. This driver copies the pre-fix script and the fixed one into two scratch trees that
differ only in scripts/adoption_status.py, each with the fixed checkout's tests, and runs the two signal test
classes:

- run A: the pre-fix script;
- run B: the fixed script;
- runs C and D: the fixed script from a runner under nohup (SIGHUP ignored) and from a background job of a
  non-interactive shell (SIGINT ignored).

Runs A and B start with SIGINT, SIGTERM and SIGHUP at their defaults. Each run records its command, UTC start
and end, exit status and output. The driver writes only under one temporary directory, which it removes, and
prints scratch paths, the interpreter and the home directory as placeholders.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

TESTS = ("tests.test_adoption_status.PinnedVersionInterruptionTests",
         "tests.test_adoption_status.ProbeSignalDispositionTests")
SIGNALS = ("SIGINT", "SIGTERM", "SIGHUP")
# Sets each named signal's disposition, then execs the rest of argv (an ignored disposition survives exec).
EXEC_WITH = ("import json, os, signal, sys\n"
             "for name, action in json.loads(sys.argv[1]).items():\n"
             "    signal.signal(getattr(signal, name), signal.SIG_IGN if action == 'ignore' else signal.SIG_DFL)\n"
             "os.execvp(sys.argv[2], sys.argv[2:])\n")
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
HOME = re.compile(r"/(?:home|Users)/[A-Za-z0-9_.-]+")


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def with_defaults(argv: list[str]) -> list[str]:
    """argv started with SIGINT, SIGTERM and SIGHUP at their defaults."""
    return [sys.executable, "-c", EXEC_WITH, json.dumps({name: "default" for name in SIGNALS}), *argv]


class Recorder:
    def __init__(self, replacements: list[tuple[str, str]]):
        # Longest first, so a path is never cut by a shorter path that is its prefix.
        self.replacements = sorted(replacements, key=lambda pair: len(pair[0]), reverse=True)
        self.lines: list[str] = []

    def clean(self, text: str) -> str:
        for old, new in self.replacements:
            text = text.replace(old, new)
        return text

    def add(self, text: str = "") -> None:
        self.lines.append(self.clean(text))

    def text(self) -> str:
        output = "\n".join(self.lines) + "\n"
        if UUID.search(output) or HOME.search(output):
            raise SystemExit("unsanitized output: a UUID or a home path is left")
        return output


def run_tests(record: Recorder, title: str, tree: Path, runner: str) -> int:
    """runner: "default" (the three signals at their defaults), "nohup", or "background" (an asynchronous list
    of a non-interactive /bin/sh, which starts with SIGINT and SIGQUIT ignored)."""
    unittest = [sys.executable, "-m", "unittest", "-v", *TESTS]
    if runner == "default":
        argv = with_defaults(unittest)
    elif runner == "nohup":
        argv = with_defaults(["nohup", *unittest])
    else:
        argv = with_defaults(["/bin/sh", "-c", '"$@" & wait "$!"', "sh", *unittest])
    record.add(f"===== {title} =====")
    record.add(f"# tree: {tree}")
    record.add(f"# runner: {runner}; command: {' '.join(unittest)}")
    start = now()
    result = subprocess.run(argv, cwd=tree, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=900)
    record.add(f"# {start} to {now()}, exit {result.returncode}")
    record.add("\n".join(part for part in (result.stdout.rstrip(), result.stderr.rstrip()) if part))
    record.add()
    return result.returncode


def tree(root: Path, name: str, script: Path, tests: Path, init: Path) -> Path:
    path = root / name
    (path / "scripts").mkdir(parents=True)
    (path / "tests").mkdir()
    shutil.copyfile(script, path / "scripts" / "adoption_status.py")
    shutil.copyfile(tests, path / "tests" / "test_adoption_status.py")
    shutil.copyfile(init, path / "tests" / "__init__.py")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checkout", type=Path, required=True,
                        help="the fixed checkout: its scripts/adoption_status.py and tests/ are copied")
    parser.add_argument("--pre-fix-script", type=Path, required=True)
    args = parser.parse_args()
    fixed, tests = args.checkout / "scripts/adoption_status.py", args.checkout / "tests/test_adoption_status.py"
    init = args.checkout / "tests/__init__.py"
    with tempfile.TemporaryDirectory(prefix="interrupt-window-") as scratch:
        root = Path(scratch)
        before = tree(root, "pre-fix-tree", args.pre_fix_script, tests, init)
        after = tree(root, "fixed-tree", fixed, tests, init)
        record = Recorder([(str(before), "<pre-fix-tree>"), (str(after), "<fixed-tree>"), (scratch, "<tmp>"),
                           (sys.executable, "<python>"), (str(Path.home()), "~"),
                           (tempfile.gettempdir(), "<tmpdir>")])
        record.add("# --pinned-versions interrupt window: discriminating control (2026-09-26)")
        record.add(f"# Python {sys.version.split()[0]} on {platform.system()} {platform.machine()}; "
                   f"driver sha256 {sha256(Path(__file__))}")
        record.add(f"# pre-fix scripts/adoption_status.py sha256 {sha256(args.pre_fix_script)}")
        record.add(f"# fixed scripts/adoption_status.py sha256 {sha256(fixed)}")
        record.add(f"# tests/test_adoption_status.py sha256 {sha256(tests)} (both trees)")
        record.add()
        summary_at = len(record.lines)
        statuses = [
            run_tests(record, "Run A: the pre-fix script", before, "default"),
            run_tests(record, "Run B: the fixed script", after, "default"),
            run_tests(record, "Run C: the fixed script, under nohup", after, "nohup"),
            run_tests(record, "Run D: the fixed script, as a background job", after, "background"),
        ]
        record.lines.insert(summary_at, record.clean(f"# exit statuses, runs A to D: {statuses}\n"))
        sys.stdout.write(record.text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
