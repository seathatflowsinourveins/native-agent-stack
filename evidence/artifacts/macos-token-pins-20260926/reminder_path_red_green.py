"""Red/green check of the macOS rtk reminder's config path, with this repository's own tests.

Usage, from the root of the fixed tree:
  python3 evidence/artifacts/macos-token-pins-20260926/reminder_path_red_green.py \
      --bash32 <bash 3.2 binary> [--before <a tree of this change before the config path fix>]

Runs RtkConfigPathTests and PortedFunctionsUnderRealBash32Tests from
tests/test_adoption_bootstrap_macos.py, with BASH32_BINARY set, in up to three trees:
  before  (optional) a copy of the given tree with this tree's test file written over its own,
          so the same tests judge the code and docs as they were before the fix;
  mutant  a copy of this tree whose rtk_config_reminder `local config=` line is reverted to the
          Linux path, ${XDG_CONFIG_HOME:-$HOME/.config}/rtk/config.toml, and nothing else;
  fixed   this tree as it is.
Each run prints the sha256 of the tree's adoption/bootstrap-macos.sh and test file, the reminder's
`local config=` line, the `python3 -m unittest -v` output and a verdict line. Paths are sanitized:
each tree as <before>, <mutant> or <fixed>, the bash 3.2 binary as <bash-VERSION>, temporary
directories as <tmp> and the home directory as ~; each line over 400 characters is cut there and
marked.

It fails closed. --bash32 must print a GNU bash 3.2 version line, or nothing runs (exit 2). The
tests fall back to /bin/bash or PATH's bash only when that is 3.2, so on a host without one any
other --bash32 makes them skip PortedFunctionsUnderRealBash32Tests and drop RtkConfigPathTests'
bash 3.2 cases. In every tree the run must report as many tests as the fixed tree's test loader
counts in the two classes, with none skipped and none erroring; the fixed tree must then pass
("OK", exit 0) and every other tree must fail on at least one test failure ("FAILED", nonzero
exit). Exits 0 only when every tree meets that, 1 otherwise.

local_integration: a harness written for this change. No rtk, uv, network or Mac runs; every
reminder case uses a temporary HOME.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = "adoption/bootstrap-macos.sh"
TESTS = "tests/test_adoption_bootstrap_macos.py"
CLASSES = ("tests.test_adoption_bootstrap_macos.RtkConfigPathTests",
           "tests.test_adoption_bootstrap_macos.PortedFunctionsUnderRealBash32Tests")
MAC_LINE = '  local config="$HOME/Library/Application Support/rtk/config.toml"\n'
LINUX_LINE = '  local config="${XDG_CONFIG_HOME:-$HOME/.config}/rtk/config.toml"\n'
CUT = 400
BASH32_VERSION = re.compile(r"GNU bash, version (3\.2\.\d+)")
RAN = re.compile(r"^Ran (\d+) tests? in \S+$", re.M)
STATUS = re.compile(r"^(OK|FAILED)(?: \(([^)]*)\))?$", re.M)
COUNT_TESTS = ("import sys, unittest; "
               "print(unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:]).countTestCases())")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config_line(tree: Path) -> str:
    text = (tree / SCRIPT).read_text(encoding="utf-8")
    body = text[text.index("rtk_config_reminder() {"):]
    return next(line.strip() for line in body.splitlines() if line.strip().startswith("local config="))


def copy_tree(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, symlinks=True,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))


def bash32_version(binary: Path) -> str | None:
    """The binary's first --version line when it is GNU bash 3.2, else None."""
    try:
        result = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    line = (result.stdout.splitlines() or [""])[0]
    return line if result.returncode == 0 and BASH32_VERSION.match(line) else None


def outcome(output: str) -> tuple[int | None, str | None, dict[str, int]]:
    """unittest's last "Ran N tests" count, the status line after it and that line's counts."""
    ran = list(RAN.finditer(output))
    if not ran:
        return None, None, {}
    status = STATUS.search(output, ran[-1].end())
    if status is None:
        return int(ran[-1].group(1)), None, {}
    counts = {}
    for item in filter(None, (status.group(2) or "").split(", ")):
        key, _, value = item.partition("=")
        counts[key] = int(value) if value.isdigit() else -1
    return int(ran[-1].group(1)), status.group(1), counts


def verdict(returncode: int, output: str, should_pass: bool, expected: int) -> list[str]:
    """Every way this tree's run falls short of its expected result; empty when it meets it."""
    ran, status, counts = outcome(output)
    problems = []
    if ran is None:
        problems.append("no 'Ran N tests' line")
    elif ran != expected:
        problems.append(f"ran {ran} tests, not the {expected} the two classes hold")
    problems += [f"{counts[key]} {key}" for key in ("skipped", "errors", "expected failures", "unexpected successes")
                 if counts.get(key)]
    if should_pass and (returncode != 0 or status != "OK" or counts.get("failures")):
        problems.append(f"exit {returncode} with {status or 'no status line'}, not OK with exit 0")
    if not should_pass and (returncode == 0 or status != "FAILED" or counts.get("failures", 0) < 1):
        problems.append(f"exit {returncode} with {status or 'no status line'}, not a test failure")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bash32", required=True, type=Path, help="a bash 3.2 binary")
    parser.add_argument("--before", type=Path, help="a tree of this change before the config path fix")
    args = parser.parse_args()
    fixed = Path.cwd().resolve()
    if not (fixed / SCRIPT).is_file() or not (fixed / TESTS).is_file():
        parser.error("run from the root of the fixed tree")
    if args.before is not None and not (args.before / SCRIPT).is_file():
        parser.error(f"--before must be a tree holding {SCRIPT}")
    bash32 = args.bash32.resolve()
    bash_version = bash32_version(bash32)
    if bash_version is None:
        parser.error("--bash32 must print a GNU bash 3.2 version line; with any other bash the bash 3.2 tests "
                     "are skipped or dropped")
    label = f"<bash-{BASH32_VERSION.match(bash_version).group(1)}>"
    replacements = [(str(bash32), label), (str(fixed), "<fixed>")]
    environment = {key: value for key, value in os.environ.items() if key != "XDG_CONFIG_HOME"}
    environment["BASH32_BINARY"] = str(bash32)
    counted = subprocess.run([sys.executable, "-c", COUNT_TESTS, *CLASSES], cwd=fixed, capture_output=True,
                             text=True, env=environment, timeout=300)
    if counted.returncode != 0 or not counted.stdout.strip().isdigit() or int(counted.stdout) < 1:
        parser.error(f"cannot count the tests of {' and '.join(CLASSES)} in this tree")
    expected = int(counted.stdout)
    work = Path(tempfile.mkdtemp(prefix="rtk-path-red-green-"))
    try:
        trees: list[tuple[str, Path, bool]] = []
        if args.before is not None:
            before = work / "before"
            copy_tree(args.before.resolve(), before)
            shutil.copyfile(fixed / TESTS, before / TESTS)
            trees.append(("before", before, False))
            replacements.insert(0, (str(before), "<before>"))
        mutant = work / "mutant"
        copy_tree(fixed, mutant)
        script = (mutant / SCRIPT).read_text(encoding="utf-8")
        if script.count(MAC_LINE) != 1:
            parser.error(f"{SCRIPT} does not hold the macOS config line exactly once")
        (mutant / SCRIPT).write_text(script.replace(MAC_LINE, LINUX_LINE), encoding="utf-8")
        trees.append(("mutant", mutant, False))
        replacements.insert(0, (str(mutant), "<mutant>"))
        trees.append(("fixed", fixed, True))
        replacements.append((str(Path.home()), "~"))
        temporary = re.compile(re.escape(tempfile.gettempdir()) + r"/tmp[A-Za-z0-9_]+")

        def clean(text: str) -> str:
            for old, new in replacements:
                text = text.replace(old, new)
            text = temporary.sub("<tmp>", text)
            return "\n".join(line if len(line) <= CUT else f"{line[:CUT]} ...[cut: {len(line) - CUT} more characters]"
                             for line in text.split("\n"))

        print(f"# macOS rtk reminder config path: red/green with the repository's own tests, "
              f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ}")
        print(f"# Python {sys.version.split()[0]}; BASH32_BINARY={label} ({bash_version})")
        print(f"# the test file is byte-identical in every tree: sha256 {sha256(fixed / TESTS)}")
        print(f"# every tree must run the {expected} tests the fixed tree's loader counts in the two classes, "
              f"none skipped or erroring; the fixed tree must pass and every other tree must fail")
        failures = 0
        for name, tree, should_pass in trees:
            print(f"\n## {name}: {SCRIPT} sha256 {sha256(tree / SCRIPT)}; {TESTS} sha256 {sha256(tree / TESTS)}")
            print(f"## rtk_config_reminder: {config_line(tree)}")
            print(f"$ cd <{name}> && BASH32_BINARY={label} python3 -m unittest -v {' '.join(CLASSES)}")
            result = subprocess.run([sys.executable, "-m", "unittest", "-v", *CLASSES], cwd=tree,
                                    capture_output=True, text=True, env=environment, timeout=900)
            print(clean(result.stdout + result.stderr).rstrip("\n"))
            print(f"[exit {result.returncode}; expected {'0' if should_pass else 'nonzero'}]")
            problems = verdict(result.returncode, result.stdout + result.stderr, should_pass, expected)
            print(f"[verdict: {'as expected' if not problems else 'FAILED: ' + '; '.join(problems)}]")
            failures += bool(problems)
        if failures:
            print(f"\n# result: FAIL ({failures} of {len(trees)} trees did not meet their verdict)")
            return 1
        print(f"\n# result: PASS (every tree ran all {expected} tests with none skipped or erroring, "
              f"the fixed tree passed and every other tree failed)")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
