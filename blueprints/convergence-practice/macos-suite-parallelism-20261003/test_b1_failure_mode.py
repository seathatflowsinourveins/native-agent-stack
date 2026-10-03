"""Regression test for the failure mode of the B1 wrapper (fix round item 7; stdlib unittest, local integration).

  python3 -m unittest discover -s blueprints/convergence-practice/macos-suite-parallelism-20261003 \
      -p test_b1_failure_mode.py

tests/test_native_maintenance.py loads three blueprint test modules when it is imported, so that a spawned
unittest-parallel worker can unpickle their classes (B1). Fix round item 7: a blueprint that raises while it loads
must not abort a named run. As at base 56473e4b, where load_tests loaded the blueprints, the loader turns the error
into one failing test (CPython Lib/unittest/loader.py loadTestsFromModule, v3.12.3 :109-118, v3.13.16 :113-122), the
run prints its Ran line and exits 1, and a module named beside the wrapper still runs. The wrapper also leaves no
partly loaded blueprint registered in sys.modules.

The test builds each scenario in a temporary directory and never writes to tests/: the suite under trial stays
unchanged. A tree holds tests/__init__.py and tests/test_native_maintenance.py, copied from this checkout, a
co-listed module tests/test_co_listed.py with one passing test, and the three blueprint directories the wrapper loads
from, as symbolic links to this checkout's own. The blueprint tests resolve their own paths through the links, so a
healthy tree runs the real 29 tests. A broken tree replaces one of the links with a directory that holds only a stub
of the loaded file, which raises RuntimeError when it is imported. Every child Python runs with
PYTHONDONTWRITEBYTECODE=1, so nothing is written through the links.

None of this is upstream acceptance or a GitHub-hosted run. The trial workflow runs only test_compare.py, not this
file.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WRAPPER = ROOT / "tests" / "test_native_maintenance.py"
PACKAGE_INIT = ROOT / "tests" / "__init__.py"
BLUEPRINTS = ROOT / "blueprints" / "convergence-practice"
# The wrapper's blueprint modules in its load order: the child module name under tests.test_native_maintenance and
# the loaded file, relative to blueprints/convergence-practice.
LOADED = (
    ("memory_patch_evidence_tests", "mac-memory-patch/test_evidence.py"),
    ("application_portability_tests", "application-delivery/test_portability.py"),
    ("wsl_transport_evidence_tests", "wsl-transport-recovery/test_transport_evidence.py"),
)
BROKEN_MESSAGE = "B1 failure-mode regression: this blueprint raises while it loads"
BROKEN_STUB = f"raise RuntimeError({BROKEN_MESSAGE!r})\n"
CO_LISTED = ("import unittest\n\n\n"
             "class CoListedTests(unittest.TestCase):\n"
             "    def test_runs(self):\n"
             "        self.assertTrue(True)\n")
CO_LISTED_RECORD = "test_runs (tests.test_co_listed.CoListedTests.test_runs) ... ok"
# CPython names the test it makes for a failed load_tests after the module (loader.py _make_failed_load_tests);
# 3.11 and later print "<module> (unittest.loader._FailedTest.<module>)".
FAILED_LOAD_RECORD = (r"(?m)^tests\.test_native_maintenance "
                      r"\(unittest\.loader\._FailedTest(?:\.tests\.test_native_maintenance)?\) \.\.\. ERROR$")
CHILD_PREFIX = "tests.test_native_maintenance."


def build_tree(root: Path, broken: str | None = None) -> None:
    """The scenario tree under root; broken names the child module whose file is replaced by a raising stub."""
    tests = root / "tests"
    tests.mkdir()
    shutil.copyfile(PACKAGE_INIT, tests / "__init__.py")
    shutil.copyfile(WRAPPER, tests / "test_native_maintenance.py")
    (tests / "test_co_listed.py").write_text(CO_LISTED, encoding="utf-8")
    target = root / "blueprints" / "convergence-practice"
    target.mkdir(parents=True)
    for short, relative in LOADED:
        directory = relative.split("/", 1)[0]
        if short == broken:
            (target / directory).mkdir()
            (target / relative).write_text(BROKEN_STUB, encoding="utf-8")
        else:
            (target / directory).symlink_to(BLUEPRINTS / directory, target_is_directory=True)


def run_python(root: Path, *args: str) -> subprocess.CompletedProcess:
    """This interpreter in root, with no bytecode written and no inherited import path."""
    child = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "PYTHONSAFEPATH")}
    child["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run([sys.executable, *args], cwd=root, env=child, capture_output=True, text=True,
                          timeout=600, check=False)


class B1WrapperFailureModeTests(unittest.TestCase):
    def test_the_tree_mirrors_the_wrappers_load_list(self):
        source = WRAPPER.read_text(encoding="utf-8")
        for short, relative in LOADED:
            with self.subTest(module=short):
                self.assertIn(f'("{short}", ROOT / "{relative}")', source)
                self.assertTrue((BLUEPRINTS / relative).is_file())

    def test_a_healthy_tree_runs_the_29_blueprint_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            build_tree(Path(tmp))
            done = run_python(Path(tmp), "-m", "unittest", "tests.test_native_maintenance", "-v")
        self.assertEqual(done.returncode, 0, done.stderr[-4000:])
        self.assertRegex(done.stderr, r"(?m)^Ran 29 tests in \d+\.\d{3}s$")
        self.assertRegex(done.stderr, r"(?m)^OK$")
        self.assertEqual(done.stderr.count(" ... ok\n"), 29)

    def test_a_blueprint_that_raises_while_loading_fails_one_test_and_the_named_run_goes_on(self):
        for short, _ in LOADED:
            with self.subTest(broken=short):
                with tempfile.TemporaryDirectory() as tmp:
                    build_tree(Path(tmp), broken=short)
                    done = run_python(Path(tmp), "-m", "unittest", "tests.test_native_maintenance",
                                      "tests.test_co_listed", "-v")
                self.assertEqual(done.returncode, 1, done.stderr[-4000:])
                self.assertRegex(done.stderr, r"(?m)^Ran 2 tests in \d+\.\d{3}s$")
                self.assertRegex(done.stderr, r"(?m)^FAILED \(errors=1\)$")
                self.assertRegex(done.stderr, FAILED_LOAD_RECORD)
                self.assertIn(CO_LISTED_RECORD, done.stderr)
                self.assertIn(f"RuntimeError: {BROKEN_MESSAGE}", done.stderr)

    def test_a_failed_load_leaves_no_partly_loaded_module_registered(self):
        probe = ("import json, sys\n"
                 "import tests.test_native_maintenance\n"
                 f"print(json.dumps(sorted(name for name in sys.modules if name.startswith({CHILD_PREFIX!r}))))\n")
        for index, (short, _) in enumerate(LOADED):
            with self.subTest(broken=short):
                with tempfile.TemporaryDirectory() as tmp:
                    build_tree(Path(tmp), broken=short)
                    done = run_python(Path(tmp), "-c", probe)
                self.assertEqual(done.returncode, 0, done.stderr[-4000:])
                registered = json.loads(done.stdout)
                self.assertNotIn(CHILD_PREFIX + short, registered)
                # Only modules loaded before the broken one may stay registered (the load stops at the error).
                earlier = [CHILD_PREFIX + name for name, _ in LOADED[:index]]
                self.assertEqual([name for name in registered if name not in earlier], [])


if __name__ == "__main__":
    unittest.main()
