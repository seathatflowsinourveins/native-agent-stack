#!/usr/bin/env python3
"""Negative controls for the scan's reader and its tests. (1) On each installed release binary named on the command line, read the matcher values with the scan and with a copy whose catalog pattern is the
scan's first one (`\\w+` for the minified spread name, which cannot match a `$` such as `P$o` in 2.1.283): the count of matcher values shows what the first pattern missed without an error. (2) Run the
repository's ScanReaderTests against two mutated copies of the scan (the first pattern; an exit code that ignores a blind reader): each must make exactly the tests named for it fail. Reads only; the
mutated copies live in a private temporary directory that is removed.
usage: python3 -B scan_reader_mutants.py <checkout> [<release binary> ...]"""
import importlib.util, io, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
BINARIES = [Path(a) for a in sys.argv[2:]]
SCAN = ROOT / "evidence/artifacts/notification-types-20260929/notification_types_scan.py"
sys.path.insert(0, str(ROOT / "tests"))
sys.dont_write_bytecode = True
import test_windows_terminal_defaults as T  # noqa: E402

text = SCAN.read_text(encoding="utf-8")
FIRST_PATTERN = (r"values:\[\.\.\.[\w$]+((?:", r"values:\[\.\.\.\w+((?:")
BLIND_EXIT = ("return 1 if report[\"unknown\"] or report[\"decision_disagrees_with_the_overlay\"] or reader_blind else 0",
              "return 1 if report[\"unknown\"] or report[\"decision_disagrees_with_the_overlay\"] else 0")
MUTANTS = {"the scan's first catalog pattern (no dollar sign)": (FIRST_PATTERN, {"test_the_catalog_is_read_whatever_the_minified_spread_name_is [$a]", "test_the_catalog_is_read_whatever_the_minified_spread_name_is [P$o]"}),
           "an exit code that ignores a blind reader": (BLIND_EXIT, {"test_a_reader_that_finds_nothing_exits_nonzero_instead_of_passing"})}


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mutated(old, new, directory):
    assert text.count(old) == 1, old[:60]
    path = Path(directory) / "notification_types_scan.py"
    path.write_text(text.replace(old, new), encoding="utf-8")
    return path


bad = 0
with tempfile.TemporaryDirectory(prefix="srm") as raw:
    first = load(mutated(*FIRST_PATTERN, raw), "first_pattern_scan")
    current = load(SCAN, "current_scan")
    for binary in BINARIES:
        old_found, new_found = first.scan(binary), current.scan(binary)
        old_count = sum(1 for row in old_found["types"].values() if row["matcher_value"])
        new_count = sum(1 for row in new_found["types"].values() if row["matcher_value"])
        print(f"{binary.name}: matcher values read by the first pattern {old_count} (catalog found: {old_found['catalog_found']}), by the current reader {new_count} (catalog found: {new_found['catalog_found']})")
    for name, ((old, new), expected) in MUTANTS.items():
        with tempfile.TemporaryDirectory(prefix="srm") as directory:
            path = mutated(old, new, directory)
            T.SCAN, T._SCAN_PATH = load(path, "mutant_scan"), path
            stream = io.StringIO()
            result = unittest.TextTestRunner(stream=stream, verbosity=0).run(unittest.defaultTestLoader.loadTestsFromTestCase(T.ScanReaderTests))
            failed = {f"{str(test).split(' ')[0]}" + (f" [{str(test).split('[')[-1].rstrip(')').rstrip(']')}]" if "[" in str(test) else "") for test, _trace in result.failures + result.errors}
            ok = failed == expected
            bad += 0 if ok else 1
            print(("ok    " if ok else "WRONG ") + f"mutant, {name}: ran {result.testsRun} tests, failing {sorted(failed)}" + ("" if ok else f" | expected {sorted(expected)}"))
print(f"{len(MUTANTS)} mutants, {bad} problems")
sys.exit(1 if bad else 0)
