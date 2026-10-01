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
`local config=` line and the `python3 -m unittest -v` output. Paths are sanitized: each tree as
<before>, <mutant> or <fixed>, the bash 3.2 binary as <bash-3.2.57>, temporary directories as
<tmp> and the home directory as ~; each line over 400 characters is cut there and marked.
Exits 0 only when the fixed tree passes and every other tree fails.

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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config_line(tree: Path) -> str:
    text = (tree / SCRIPT).read_text(encoding="utf-8")
    body = text[text.index("rtk_config_reminder() {"):]
    return next(line.strip() for line in body.splitlines() if line.strip().startswith("local config="))


def copy_tree(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, symlinks=True,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bash32", required=True, type=Path, help="a bash 3.2 binary")
    parser.add_argument("--before", type=Path, help="a tree of this change before the config path fix")
    args = parser.parse_args()
    fixed = Path.cwd().resolve()
    if not (fixed / SCRIPT).is_file() or not (fixed / TESTS).is_file():
        parser.error("run from the root of the fixed tree")
    bash32 = args.bash32.resolve()
    replacements = [(str(bash32), "<bash-3.2.57>"), (str(fixed), "<fixed>")]
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

        def clean(text: str) -> str:
            for old, new in replacements:
                text = text.replace(old, new)
            text = re.sub(r"/tmp/tmp[A-Za-z0-9_]+", "<tmp>", text)
            return "\n".join(line if len(line) <= CUT else f"{line[:CUT]} ...[cut: {len(line) - CUT} more characters]"
                             for line in text.split("\n"))

        bash_version = subprocess.run([str(bash32), "--version"], capture_output=True, text=True,
                                      check=True).stdout.splitlines()[0]
        print(f"# macOS rtk reminder config path: red/green with the repository's own tests, "
              f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ}")
        print(f"# Python {sys.version.split()[0]}; BASH32_BINARY=<bash-3.2.57> ({bash_version})")
        print(f"# the test file is byte-identical in every tree: sha256 {sha256(fixed / TESTS)}")
        failures = 0
        for label, tree, should_pass in trees:
            print(f"\n## {label}: {SCRIPT} sha256 {sha256(tree / SCRIPT)}; {TESTS} sha256 {sha256(tree / TESTS)}")
            print(f"## rtk_config_reminder: {config_line(tree)}")
            print(f"$ cd <{label}> && BASH32_BINARY=<bash-3.2.57> python3 -m unittest -v {' '.join(CLASSES)}")
            environment = {key: value for key, value in os.environ.items() if key != "XDG_CONFIG_HOME"}
            environment["BASH32_BINARY"] = str(bash32)
            result = subprocess.run([sys.executable, "-m", "unittest", "-v", *CLASSES], cwd=tree,
                                    capture_output=True, text=True, env=environment, timeout=900)
            print(clean(result.stdout + result.stderr).rstrip("\n"))
            print(f"[exit {result.returncode}; expected {'0' if should_pass else 'nonzero'}]")
            if (result.returncode == 0) != should_pass:
                failures += 1
        print(f"\n# result: {'PASS' if failures == 0 else 'FAIL'} (the fixed tree passes and every other tree fails)")
        return 0 if failures == 0 else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
