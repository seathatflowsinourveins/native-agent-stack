#!/usr/bin/env python3
"""Regenerate fixtures/ from real local runs (stdlib only; local, never in CI).

  python3 make_fixtures.py --work SCRATCH_DIR [--python INTERPRETER]

It writes a small fixture suite (SUITE below: six test files, one of them a wrapper that adds a class through
load_tests under a bare module name, and one standing in for the trial's serial-tail module) into
SCRATCH_DIR/suite, then runs, with one interpreter and stdout and stderr in one file as the trial workflows do:

  - inventory.py --os ubuntu-24.04 on that suite with FIXTURE_WEIGHTS (the inventory, the id map, the G4 and
    G4T lists);
  - the serial command `python3 -m unittest -v` three times (S r1 to r3);
  - every G4 and G4T list as `python3 -m unittest -v <modules>`, one process per list, and the G4T tail;
  - every control module of controls/ alone in an empty directory with the same command, the hang control
    stopped after HANG_LIMIT seconds (it then writes no exit status, as a killed step does), each with a
    record.py probe, plus one foreground probe.

SCRATCH_DIR must lie outside the checkout and be empty or absent; the tool creates every directory in it and
deletes none. Logs and probes are sanitized (scratch, interpreter and home prefixes become <work>, <python>
and <home>) and written to fixtures/, with fixtures/index.json listing each file's sha256, command and exit
status. test_compare.py reads only fixtures/ and requires index.json to match the files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]  # the checkout root: <root>/blueprints/convergence-practice/<this directory>
FIXTURES = HERE / "fixtures"
HANG_LIMIT = 3
FIXTURE_OS = "ubuntu-24.04"
FIXTURE_WEIGHTS = {"tests.test_alpha": "4.000", "tests.test_beta": "3.000", "tests.test_gamma": "2.000",
                   "tests.test_delta": "1.500", "tests.test_epsilon": "1.000", "tests.test_secret_path_guard": "2.500"}
SUITE = {
    "tests/__init__.py": "",
    "tests/test_alpha.py": '''"""Fixture: a pass, a skip, passing subtests and an expected failure."""
import unittest


class AlphaTests(unittest.TestCase):
    def test_passes(self):
        self.assertEqual(2 + 2, 4)

    @unittest.skip("planted skip")
    def test_skipped(self):
        pass

    def test_subtests_pass(self):
        for value in (1, 2):
            with self.subTest(value=value):
                self.assertGreater(value, 0)

    @unittest.expectedFailure
    def test_expected_failure(self):
        self.assertEqual(1, 2)
''',
    "tests/test_beta.py": '''"""Fixture: a failure, an error and a failing subtest with a docstring."""
import unittest


class BetaTests(unittest.TestCase):
    def test_fails(self):
        self.assertEqual("left", "right")

    def test_errors(self):
        raise RuntimeError("planted error")

    def test_subtest_fails(self):
        """A failing subtest with a docstring."""
        for value in (1, 2):
            with self.subTest(value=value):
                self.assertEqual(value, 1)
''',
    "tests/test_gamma.py": '''"""Fixture: a setUpClass error, an unexpected success and printed output."""
import unittest


class GammaFixtureError(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raise RuntimeError("planted setUpClass error")

    def test_never_runs(self):
        pass


class GammaTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_unexpected_success(self):
        pass

    def test_prints_output(self):
        print("output between records")
''',
    "tests/test_delta.py": '''"""Fixture: a wrapper that adds a class through load_tests under a bare module name."""
import importlib.util
import pathlib
import unittest

_SPEC = importlib.util.spec_from_file_location("delta_extra_tests", pathlib.Path(__file__).with_name("delta_extra.py"))


def load_tests(loader, tests, pattern):
    module = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(module)
    tests.addTests(loader.loadTestsFromModule(module))
    return tests


class DeltaTests(unittest.TestCase):
    def test_passes(self):
        pass
''',
    "tests/delta_extra.py": '''"""Fixture: loaded only by tests/test_delta.py, under the bare module name delta_extra_tests."""
import unittest


class ExtraTests(unittest.TestCase):
    def test_from_wrapper(self):
        pass
''',
    "tests/test_epsilon.py": '''"""Fixture: module fixtures and two passes."""
import unittest

CALLS = []


def setUpModule():
    CALLS.append("setUpModule")


def tearDownModule():
    CALLS.append("tearDownModule")


class EpsilonTests(unittest.TestCase):
    def test_one(self):
        self.assertEqual(CALLS, ["setUpModule"])

    def test_two(self):
        self.assertTrue(CALLS)
''',
    "tests/test_secret_path_guard.py": '''"""Fixture stand-in for the trial's serial-tail module; not the repository's tests/test_secret_path_guard.py."""
import time
import unittest


class TailTests(unittest.TestCase):
    def test_timing(self):
        time.sleep(0.05)
''',
}
PRIVATE = re.compile(r"/(?:home|Users)/[A-Za-z0-9_.-]+")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitizer(work: Path, python: str):
    prefixes = sorted({str(work.resolve()), str(work)}, key=len, reverse=True)
    base = subprocess.run([python, "-c", "import sys; print(sys.base_prefix); print(sys.prefix)"],
                          capture_output=True, text=True, check=True).stdout.split()
    interpreter = sorted(set(base), key=len, reverse=True)

    def clean(text: str) -> str:
        for prefix in prefixes:
            text = text.replace(prefix, "<work>")
        for prefix in interpreter:
            text = text.replace(prefix, "<python>")
        text = text.replace(str(Path.home()), "<home>")
        return PRIVATE.sub("<home>", text)
    return clean


def run(python: str, args: list, cwd: Path, log: Path, timeout: int | None = None):
    """Run python with args in cwd, stdout and stderr to log; the exit status, or None when stopped at timeout."""
    with log.open("wb") as handle:
        process = subprocess.Popen([python, *args], cwd=cwd, stdout=handle, stderr=subprocess.STDOUT)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args(argv)
    work = args.work.resolve()
    if work == ROOT or ROOT in work.parents:
        parser.error("--work must lie outside the checkout")
    if work.exists() and any(work.iterdir()):
        parser.error("--work must be empty or absent")
    python = args.python
    clean = sanitizer(work, python)
    suite, raw, controls = work / "suite", work / "raw", work / "controls"
    for directory in (suite / "tests", raw, controls):
        directory.mkdir(parents=True)
    for name, text in SUITE.items():
        (suite / name).write_text(text, encoding="utf-8")
    weights = work / "weights-fixture.json"
    weights.write_text(json.dumps({"schema": "suite-shards-weights/1", "unit": "seconds",
                                   "source": "fixture weights of make_fixtures.py",
                                   "weights": {k: float(v) for k, v in FIXTURE_WEIGHTS.items()}}, indent=2) + "\n",
                       encoding="utf-8")
    inventory = work / "inventory"
    code = subprocess.run([python, str(HERE / "inventory.py"), "--os", FIXTURE_OS, "--root", str(suite), "--weights",
                           str(weights), "--out", str(inventory)], check=False).returncode
    if code != 0:
        sys.exit(f"inventory.py failed on the fixture suite (exit {code})")
    runs = []
    for repeat in (1, 2, 3):
        log = raw / f"S-r{repeat}.log"
        runs.append({"file": f"runs/S-r{repeat}.log", "arm": "S", "repeat": repeat,
                     "command": "python3 -m unittest -v", "exit_code": run(python, ["-m", "unittest", "-v"], suite, log)})
    for arm in ("G4", "G4T"):
        lists = sorted((inventory / "shards" / arm).glob("shard-*.txt")) + [inventory / "shards" / arm / "tail.txt"]
        for listed in lists:
            modules = listed.read_text(encoding="utf-8").split()
            if not modules:
                continue
            label = listed.stem
            log = raw / f"{arm}-{label}.log"
            runs.append({"file": f"runs/{arm}-{label}.log", "arm": arm, "list": label,
                         "command": "python3 -m unittest -v " + " ".join(modules),
                         "exit_code": run(python, ["-m", "unittest", "-v", *modules], suite, log)})
    control_runs = []
    probe_names = ["foreground"]
    subprocess.run([python, str(HERE / "record.py"), "probe", str(controls), "foreground"], check=True)
    for index, module in enumerate(("test_ctl_pass", "test_ctl_fail", "test_ctl_crash", "test_ctl_hang")):
        directory = work / f"control-{index}"
        directory.mkdir()
        shutil.copy(HERE / "controls" / f"{module}.py", directory / f"{module}.py")
        env_probe = dict(os.environ, SUITE_SHARDS_ENV_PROBE="1")
        subprocess.run([python, str(HERE / "record.py"), "probe", str(controls), f"shard-{index}"], check=True,
                       env=env_probe)
        probe_names.append(f"shard-{index}")
        log = controls / f"shard-{index}.log"
        code = run(python, ["-m", "unittest", "-v", module], directory, log,
                   timeout=HANG_LIMIT if module == "test_ctl_hang" else 60)
        control_runs.append({"file": f"controls/shard-{index}.log", "module": module,
                             "command": f"python3 -m unittest -v {module}", "exit_code": code})
    # Sanitized copies into fixtures/.
    if FIXTURES.exists():
        for old in sorted(FIXTURES.rglob("*"), reverse=True):
            if old.is_file():
                old.unlink()
    targets = {}
    for item in runs:
        targets[item["file"]] = clean((raw / Path(item["file"]).name).read_text(encoding="utf-8", errors="replace"))
    for item in control_runs:
        targets[item["file"]] = clean((controls / Path(item["file"]).name).read_text(encoding="utf-8", errors="replace"))
    for name in probe_names:
        data = json.loads((controls / f"{name}.probe.json").read_text(encoding="utf-8"))
        data["python_executable"] = clean(data["python_executable"])
        targets[f"controls/{name}.probe.json"] = json.dumps(data, indent=2, sort_keys=True) + "\n"
    for path in sorted(inventory.rglob("*")):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            targets[f"inventory/{path.relative_to(inventory).as_posix()}"] = clean(text)
    targets["weights-fixture.json"] = weights.read_text(encoding="utf-8")
    files = []
    for relative, text in sorted(targets.items()):
        target = FIXTURES / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        if PRIVATE.search(text):
            sys.exit(f"{relative}: a home path survived sanitizing")
        files.append({"file": relative, "sha256": sha256(target)})
    index = {"schema": "suite-shards-fixtures/1",
             "evidence_class": "synthetic fixture: real local runs of a fixture suite and of the controls, not a "
                               "GitHub-hosted runner",
             "generator": "make_fixtures.py --work <scratch>",
             "host": {"python_version": platform.python_version(), "machine": platform.machine(),
                      "system": platform.system()},
             "sanitized_prefixes": {"<work>": "the scratch directory", "<python>": "the interpreter's prefix",
                                    "<home>": "a home directory"},
             "hang_limit_seconds": HANG_LIMIT, "fixture_os": FIXTURE_OS, "runs": runs, "controls": control_runs,
             "files": files}
    (FIXTURES / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(files)} fixture files and index.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
