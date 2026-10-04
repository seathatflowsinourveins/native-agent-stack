#!/usr/bin/env python3
"""Discriminating control for the signal-disposition repair of `adoption_status.py --pinned-versions`.

The independent review of the first 2026-09-26 repair found that the check replaced an inherited SIG_IGN:
under nohup, a SIGHUP ended it with status 129, while adoption/bootstrap-linux.sh, which traps only EXIT,
keeps running. This driver prints, in order:

1. a bash reference: how a bash script with an EXIT trap answers SIGTERM and SIGHUP at their default
   action and when they were ignored on entry;
2. the repair's signal tests against the first repair's script and against the fixed one, in scratch trees
   that differ only in scripts/adoption_status.py;
3. the fixed script's tests from runners that inherit SIGHUP ignored (nohup) or SIGINT ignored (a
   background job of a non-interactive shell), with the first repair's test file as the control, whose
   process-level test did not set the check's signal dispositions itself, and that file with the first
   repair's script under nohup, where it passed only because that script replaced the ignored SIGHUP.

Each run records its command, UTC start and end, exit status and output. The driver writes only under one
temporary directory, which it removes, and prints scratch paths, the interpreter and the home directory as
placeholders.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

NEW_TESTS = ("tests.test_adoption_status.PinnedVersionInterruptionTests",
             "tests.test_adoption_status.ProbeSignalDispositionTests")
OLD_TEST = ("tests.test_adoption_status.PinnedVersionInterruptionTests."
            "test_an_interrupted_check_kills_the_running_probe_s_process_group",)
SIGNALS = ("SIGINT", "SIGTERM", "SIGHUP")
# Sets each named signal's disposition, then execs the rest of argv (an ignored disposition survives exec).
EXEC_WITH = ("import json, os, signal, sys\n"
             "for name, action in json.loads(sys.argv[1]).items():\n"
             "    signal.signal(getattr(signal, name), signal.SIG_IGN if action == 'ignore' else signal.SIG_DFL)\n"
             "os.execvp(sys.argv[2], sys.argv[2:])\n")
SHOW_DISPOSITIONS = ("import signal\n"
                     "def shown(name):\n"
                     "    handler = signal.getsignal(getattr(signal, name))\n"
                     "    if handler is signal.default_int_handler:\n"
                     "        return 'default_int_handler'  # installed only when SIGINT starts at SIG_DFL\n"
                     "    return handler.name if isinstance(handler, signal.Handlers) else 'another handler'\n"
                     "print('runner dispositions: ' + ', '.join(f'{name}={shown(name)}'\n"
                     "                                          for name in ('SIGINT', 'SIGTERM', 'SIGHUP')))\n")
BASH_SCRIPT = 'trap "echo EXIT trap ran" EXIT; sleep 2; echo "ran to the end"'
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
HOME = re.compile(r"/(?:home|Users)/[A-Za-z0-9_.-]+")


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def with_defaults(argv: list[str], **actions: str) -> list[str]:
    """argv started with SIGINT, SIGTERM and SIGHUP at their defaults, apart from ``actions``."""
    dispositions = {name: actions.get(name, "default") for name in SIGNALS}
    return [sys.executable, "-c", EXEC_WITH, json.dumps(dispositions), *argv]


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


def bash_reference(record: Recorder) -> None:
    record.add("===== Part 1: bash reference (the behaviour adoption/bootstrap-linux.sh gets from bash) =====")
    record.add(f"# bash -c '{BASH_SCRIPT}', sent the signal 0.5 s after it starts")
    bash = shutil.which("bash")
    for name, action in (("SIGTERM", "default"), ("SIGHUP", "default"), ("SIGTERM", "ignore"),
                         ("SIGHUP", "ignore")):
        start = now()
        process = subprocess.Popen(with_defaults([bash, "-c", BASH_SCRIPT], **{name: action}),
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True)
        time.sleep(0.5)
        process.send_signal(getattr(signal, name))
        output, _ = process.communicate(timeout=30)
        said = "; ".join(line for line in output.splitlines() if line) or "(nothing)"
        status = (f"ended by the signal (returncode {process.returncode})" if process.returncode < 0
                  else f"exit {process.returncode}")
        record.add(f"{name} {'ignored on entry' if action == 'ignore' else 'at its default'}: "
                   f"{status}, printed: {said} ({start} to {now()})")
    record.add()


def run_tests(record: Recorder, title: str, tree: Path, tests: tuple[str, ...], runner: str) -> int:
    """runner: "default" (the three signals at their defaults), "nohup", or "background" (an asynchronous list
    of a non-interactive /bin/sh, which starts with SIGINT and SIGQUIT ignored)."""
    unittest = [sys.executable, "-m", "unittest", "-v", *tests]
    show = [sys.executable, "-c", SHOW_DISPOSITIONS]
    if runner == "default":
        argv, probe = with_defaults(unittest), with_defaults(show)
    elif runner == "nohup":
        argv, probe = with_defaults(["nohup", *unittest]), with_defaults(["nohup", *show])
    else:
        wrap = ["/bin/sh", "-c", '"$@" & wait "$!"', "sh"]
        argv, probe = with_defaults([*wrap, *unittest]), with_defaults([*wrap, *show])
    record.add(f"===== {title} =====")
    record.add(f"# tree: {tree}")
    record.add(f"# runner: {runner}; command: {' '.join(unittest)}")
    shown = subprocess.run(probe, cwd=tree, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
    record.add(f"# {shown.stdout.strip()}")
    start = now()
    result = subprocess.run(argv, cwd=tree, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)
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
                        help="the repaired checkout: its scripts/adoption_status.py and tests/ are copied")
    parser.add_argument("--first-repair-script", type=Path, required=True)
    parser.add_argument("--first-repair-tests", type=Path, required=True)
    args = parser.parse_args()
    fixed, tests = args.checkout / "scripts/adoption_status.py", args.checkout / "tests/test_adoption_status.py"
    init = args.checkout / "tests/__init__.py"
    with tempfile.TemporaryDirectory(prefix="signal-control-") as scratch:
        root = Path(scratch)
        first = tree(root, "first-repair-tree", args.first_repair_script, tests, init)
        repaired = tree(root, "fixed-tree", fixed, tests, init)
        control = tree(root, "fixed-tree-first-tests", fixed, args.first_repair_tests, init)
        original = tree(root, "first-repair-tree-first-tests", args.first_repair_script, args.first_repair_tests,
                        init)
        record = Recorder([(str(first), "<first-repair-tree>"), (str(repaired), "<fixed-tree>"),
                           (str(control), "<fixed-tree-first-tests>"),
                           (str(original), "<first-repair-tree-first-tests>"), (scratch, "<tmp>"),
                           (sys.executable, "<python>"), (str(Path.home()), "~"),
                           (tempfile.gettempdir(), "<tmpdir>")])
        record.add("# --pinned-versions signal dispositions: discriminating control (2026-09-26)")
        record.add(f"# Python {sys.version.split()[0]}; driver sha256 {sha256(Path(__file__))}")
        record.add(f"# first repair's scripts/adoption_status.py sha256 {sha256(args.first_repair_script)}")
        record.add(f"# fixed scripts/adoption_status.py sha256 {sha256(fixed)}")
        record.add(f"# this repair's tests/test_adoption_status.py sha256 {sha256(tests)}")
        record.add(f"# first repair's tests/test_adoption_status.py sha256 {sha256(args.first_repair_tests)}")
        record.add()
        summary_at = len(record.lines)
        bash_reference(record)
        statuses = [
            run_tests(record, "Part 2, run A: the first repair's script, this repair's tests", first, NEW_TESTS,
                      "default"),
            run_tests(record, "Part 2, run B: the fixed script, this repair's tests", repaired, NEW_TESTS,
                      "default"),
            run_tests(record, "Part 3, run C: the fixed script, this repair's tests, under nohup", repaired,
                      NEW_TESTS, "nohup"),
            run_tests(record, "Part 3, run D: the fixed script, this repair's tests, as a background job",
                      repaired, NEW_TESTS, "background"),
            run_tests(record, "Part 3, run E: the fixed script, the first repair's test, under nohup", control,
                      OLD_TEST, "nohup"),
            run_tests(record, "Part 3, run F: the fixed script, the first repair's test, as a background job",
                      control, OLD_TEST, "background"),
            run_tests(record, "Part 3, run G: the first repair's script and test, under nohup", original,
                      OLD_TEST, "nohup"),
        ]
        record.lines.insert(summary_at, record.clean(f"# exit statuses, runs A to G: {statuses}\n"))
        sys.stdout.write(record.text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
