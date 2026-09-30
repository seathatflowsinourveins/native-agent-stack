#!/usr/bin/env python3
"""Negative controls for the scan's reader and its tests. (1) On each release binary named on the command line, read the matcher values with the current reader and print the catalogs
it resolved (spread identifier, number of array assignments found for it, base size). (2) Run the repository's ScanReaderTests against mutated copies of the scan, one guard removed
per copy: each mutant must make exactly the tests named for it fail (an exact set, so a test that passes whatever the reader does would show). The mutated copies live in a private
temporary directory that is removed. Reads only.
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
SUBTESTS = "test_the_catalog_is_read_whatever_the_minified_spread_name_is"
EXITS = {"test_a_reader_that_finds_nothing_exits_nonzero_instead_of_passing", "test_two_different_arrays_assigned_to_one_name_fail_closed",
         "test_a_catalog_whose_name_has_no_array_assignment_fails_closed", "test_a_base_without_the_required_names_fails_closed",
         "test_a_property_assignment_of_the_same_short_name_is_not_the_catalog_base"}
# name: (old text, new text, the tests that must fail)
MUTANTS = {
    "the spread name may not contain a dollar sign": (r"values:\[\.\.\.([\w$]+)", r"values:\[\.\.\.(\w+)", {f"{SUBTESTS} [$a]", f"{SUBTESTS} [P$o]"}),
    "a blind or unresolved reader exits 0": ('reader_blind = not found["catalog_found"] or not found["catalogs_resolved"]', "reader_blind = False", EXITS),
    "the base is any array of names, not the one the spread name is assigned": (
        "return rb'(?<![\\w$.])' + re.escape(spread) + b'=' + NAMES_ARRAY", "return rb'(?<![\\w$])[\\w$]+=' + NAMES_ARRAY",
        {"test_an_unrelated_longer_array_of_the_same_names_is_not_taken_for_the_base", "test_a_catalog_whose_name_has_no_array_assignment_fails_closed", "test_every_catalog_counts",
         "test_a_property_assignment_of_the_same_short_name_is_not_the_catalog_base"}),
    "a property assignment of the same short name counts as the catalog's array": (
        "return rb'(?<![\\w$.])' + re.escape(spread)", "return rb'(?<![\\w$])' + re.escape(spread)", {"test_a_property_assignment_of_the_same_short_name_is_not_the_catalog_base"}),
    "a Set of names counts as an assignment of the name": ("b'=' + NAMES_ARRAY", "b'=(?:new Set[(])?' + NAMES_ARRAY", {"test_a_name_reused_for_a_set_or_a_map_is_not_an_array_assignment"}),
    "two assignments of one name are accepted": ("if len(arrays) == 1 else []", "if arrays else []", {"test_two_different_arrays_assigned_to_one_name_fail_closed"}),
    "only the first catalog counts": ("for found in CATALOG.finditer(data):", "for found in list(CATALOG.finditer(data))[:1]:", {"test_every_catalog_counts"}),
    "the base need not name permission_prompt and idle_prompt": ("REQUIRED_IN_BASE <= frozenset(base)", "bool(base)", {"test_a_base_without_the_required_names_fails_closed"}),
}


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bad = 0
current = load(SCAN, "current_scan")
for binary in BINARIES:
    found = current.scan(binary)
    print(f"{binary.name}: catalogs resolved {found['catalogs_resolved']}, "
          f"{[(c['spread'], c['base_candidates'], c['base_size'], len(c['extras'])) for c in found['catalogs']]} (spread name, array assignments found, base size, extra values), "
          f"{sum(1 for row in found['types'].values() if row['matcher_value'])} matcher values")
for name, (old, new, expected) in MUTANTS.items():
    assert text.count(old) == 1, f"mutation site not found exactly once: {old[:70]}"
    with tempfile.TemporaryDirectory(prefix="srm") as directory:
        path = Path(directory) / "notification_types_scan.py"
        path.write_text(text.replace(old, new), encoding="utf-8")
        T.SCAN, T._SCAN_PATH = load(path, "mutant_scan"), path
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=0).run(unittest.defaultTestLoader.loadTestsFromTestCase(T.ScanReaderTests))
        failed = {f"{str(test).split(' ')[0]}" + (f" [{str(test).split('[')[-1].rstrip(')').rstrip(']')}]" if "[" in str(test) else "") for test, _trace in result.failures + result.errors}
    ok = failed == expected
    bad += 0 if ok else 1
    print(("ok    " if ok else "WRONG ") + f"mutant, {name}: ran {result.testsRun} tests, failing {sorted(failed)}" + ("" if ok else f" | expected {sorted(expected)}"))
print(f"{len(MUTANTS)} mutants, {bad} problems")
sys.exit(1 if bad else 0)
