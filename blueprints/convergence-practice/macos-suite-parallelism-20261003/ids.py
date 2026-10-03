#!/usr/bin/env python3
"""Print the sorted, de-duplicated unittest ids of a checkout, one per line (stdlib only).

  python3 ids.py [--root DIR] > inventory.txt

Discovery only: unittest.TestLoader().discover("tests", top_level_dir=".") imports the
test modules and honours load_tests (CPython Lib/unittest/loader.py, v3.13.16
TestLoader.discover/_find_tests), and the suite it returns is flattened without being
called, so no test body, setUpClass or setUpModule runs. Run it with the same
interpreter and installed packages as the arms, from the checkout root (or --root),
because module-level skips and import errors become ids of their own.

A summary goes to stderr: unique ids, countTestCases() (the "Ran N" of a full run
counts duplicates and tests behind a failed class fixture's setUpClass are not run,
so the two can differ), duplicated ids and loader-made ids (import failures).
"""

from __future__ import annotations

import argparse
import collections
import os
import sys
import unittest

LOADER_MADE = ("unittest.loader._FailedTest.", "unittest.loader.ModuleSkipped.")


def iter_cases(suite):
    """Every TestCase in a (nested) suite, in discovery order."""
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_cases(item)
        else:
            yield item


def discover(root: str, start: str = "tests", top: str = ".", pattern: str = "test*.py"):
    """(ids in discovery order, countTestCases(), loader errors) for the checkout at root."""
    here = os.path.dirname(os.path.abspath(__file__))
    # This directory holds compare.py and ids.py; keep it off the import path so a test
    # module importing a same-named top-level module cannot resolve to these files.
    sys.path[:] = [entry for entry in sys.path if os.path.abspath(entry or os.curdir) != here]
    os.chdir(root)
    loader = unittest.TestLoader()
    suite = loader.discover(start, pattern=pattern, top_level_dir=top)
    return [case.id() for case in iter_cases(suite)], suite.countTestCases(), list(loader.errors)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--root", default=".", help="checkout root (default: the current directory)")
    parser.add_argument("--start-directory", default="tests", help="discovery start (default: tests)")
    parser.add_argument("--top-level-directory", default=".", help="top-level directory (default: .)")
    parser.add_argument("--pattern", default="test*.py", help="module pattern (default: test*.py)")
    args = parser.parse_args(argv)
    ids, total, errors = discover(args.root, args.start_directory, args.top_level_directory, args.pattern)
    unique = sorted(set(ids))
    if not unique:
        print("ids.py: discovery found no tests", file=sys.stderr)
        return 1
    sys.stdout.write("".join(f"{item}\n" for item in unique))
    duplicated = sum(count - 1 for count in collections.Counter(ids).values() if count > 1)
    loader_made = [item for item in unique if item.startswith(LOADER_MADE)]
    print(f"ids.py: {len(unique)} unique ids; countTestCases() {total}; {duplicated} duplicate "
          f"occurrences; {len(loader_made)} loader-made ids; {len(errors)} loader errors", file=sys.stderr)
    for item in loader_made:
        print(f"ids.py: loader-made id {item}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
