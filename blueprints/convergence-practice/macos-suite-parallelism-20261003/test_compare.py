"""Tests for the suite-parallelism oracle (stdlib unittest; local integration and synthetic fixtures).

  python3 -m unittest discover -s blueprints/convergence-practice/macos-suite-parallelism-20261003 -p test_compare.py

fixtures/real/ holds sanitized logs of real local runs of the controls (make_fixtures.py,
fixtures/index.json); fixtures/mutated/ holds copies with declared edits that the oracle
must flag. Results directories are assembled from those logs in temporary directories.
None of this is upstream acceptance or a GitHub-hosted run.
"""

import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


compare = _load("suite_parallelism_compare", "compare.py")
make_fixtures = _load("suite_parallelism_make_fixtures", "make_fixtures.py")
INDEX = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))
EXPECTATIONS = json.loads((HERE / "controls" / "control_expectations.json").read_text(encoding="utf-8"))
RUNS = {entry["file"]: entry for entry in INDEX["runs"]}
PASS_ID = "test_zz_trial_controls.TrialControlsA.test_pass"
OS_OF = {"S": "macos-15", "P3": "macos-15", "P3F": "macos-15", "P3C": "macos-15", "P4": "macos-15",
         "L4": "ubuntu-24.04", "L4F": "ubuntu-24.04", "L4C": "ubuntu-24.04"}


def fixture_text(relative):
    return (FIXTURES / relative).read_text(encoding="utf-8")


def control_run(relative, os_name=None, arm=None, exit_code=None, text=None):
    entry = RUNS.get(relative, {})
    arm = arm or entry["config"]
    run = compare.Run(relative, os_name or OS_OF[arm], arm, entry.get("kind", "controls"), 1)
    run.exit_code = entry.get("exit_code") if exit_code is None else exit_code
    run.parsed = compare.parse_log(fixture_text(relative) if text is None else text)
    return run


class Layout:
    """A results directory in the trial layout, built from fixture logs."""

    def __init__(self, root):
        self.root = Path(root)
        self.inventory = self.root / "inventory.txt"
        shutil.copy(FIXTURES / "inventory-controls.txt", self.inventory)

    def add(self, name, log, exit_code=None, seconds=100.0, command=None, sha="synthetic-fixture-sha", text=None,
            python_version=None):
        match = compare.RUN_DIR_RE.match(name)
        arm = match.group("arm")
        entry = RUNS.get(log, {})
        directory = self.root / "results" / name
        directory.mkdir(parents=True)
        (directory / "log.txt").write_text(fixture_text(log) if text is None else text, encoding="utf-8")
        code = entry.get("exit_code") if exit_code is None else exit_code
        (directory / "exit-code.txt").write_text(f"{code}\n", encoding="utf-8")
        meta = {"os": match.group("os"), "arm": arm, "repeat": int(match.group("rep") or match.group("krep") or 1),
                "command": command or entry.get("command"), "python_version": python_version or INDEX["host"]["python_version"],
                "platform": INDEX["host"]["platform"], "runner_image": "local fixture (not a GitHub-hosted runner)",
                "checkout_sha": sha, "step_seconds": seconds}
        (directory / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return directory

    def standard(self, os_name="macos-15", arms=("S", "P3", "P3C"), seconds=None):
        """Three repeats per arm from the real control logs, plus each arm's controls and crash runs."""
        seconds = seconds or {}
        for arm in arms:
            config = arm if arm in compare.ARMS["macos-15"] or arm in ("L4F", "L4C") else {"L4": "P4"}[arm]
            for repeat in (1, 2, 3):
                log = f"real/controls-{config}-r{repeat}.log"
                if log not in RUNS:
                    log = f"real/controls-{config}-r1.log"
                times = seconds.get(arm, (100.0, 100.0, 100.0))
                self.add(f"{os_name}-{arm}-r{repeat}", log, seconds=times[repeat - 1])
            self.add(f"{os_name}-{arm}-controls", f"real/controls-{config}-r1.log")
            self.add(f"{os_name}-{arm}-crash", f"real/crash-{config}-r1.log")

    def result(self, min_repeats=3, base=None):
        base_path = self.inventory
        if base is not None:
            base_path = self.root / "inventory-base.txt"
            base_path.write_text("".join(f"{item}\n" for item in base), encoding="utf-8")
        return compare.build_result(self.root / "results", base_path, self.inventory,
                                    HERE / "controls" / "control_expectations.json", min_repeats)


def run_named(result, name):
    return next(run for run in result["runs"] if run["name"] == name)


class RealControlLogTests(unittest.TestCase):
    def test_every_real_control_log_parses_and_meets_the_expectations(self):
        controls = [entry for entry in INDEX["runs"] if entry["kind"] == "controls"]
        self.assertEqual(len(controls), 13)
        for entry in controls:
            with self.subTest(log=entry["file"]):
                run = control_run(entry["file"])
                self.assertEqual(run.parsed.anomalies, [])
                self.assertEqual(compare.check_controls(run, EXPECTATIONS), [])
                self.assertEqual(run.parsed.mode, "serial" if entry["config"] == "S" else "parallel")
                self.assertNotEqual(entry["exit_code"], 0)

    def test_serial_bare_fixture_status_is_named_from_the_error_report(self):
        lines = fixture_text("real/controls-S-r1.log").split("\n")
        xpass = next(i for i, line in enumerate(lines) if line.endswith(" ... unexpected success"))
        self.assertEqual(lines[xpass + 1], "ERROR")  # CPython runner.py:124-140 leave _newline False
        parsed = compare.parse_log("\n".join(lines))
        self.assertIn(("fixture", "setUpClass (test_zz_trial_controls.TrialControlsFixture)", "ERROR"),
                      parsed.records())

    def test_class_level_logs_interleave_yet_carry_the_same_records(self):
        texts = [fixture_text(f"real/controls-P3C-r{n}.log") for n in (1, 2, 3)]
        orders = {tuple(line for line in text.split("\n") if " ... " in line) for text in texts}
        records = [sorted(compare.parse_log(text).records()) for text in texts]
        self.assertGreater(len(orders), 1, "the three real class-level runs should interleave differently")
        self.assertEqual(records[0], records[1])
        self.assertEqual(records[0], records[2])
        serial = sorted(compare.parse_log(fixture_text("real/controls-S-r1.log")).records())
        self.assertEqual(records[0], serial)

    def test_crash_controls_fail_closed(self):
        crash = [entry for entry in INDEX["runs"] if entry["kind"] == "crash"]
        self.assertEqual(len(crash), 7)
        for entry in crash:
            with self.subTest(log=entry["file"]):
                run = control_run(entry["file"])
                self.assertIn("no 'Ran N tests' line", run.parsed.anomalies[0])
                self.assertEqual(compare.check_controls(run, EXPECTATIONS), [])
                self.assertEqual(entry["exit_code"], 3 if entry["config"] == "S" else 124)
                opened = control_run(entry["file"], exit_code=0)
                self.assertTrue(any("fails open" in p for p in compare.check_controls(opened, EXPECTATIONS)))

    def test_a_crash_run_that_never_started_the_test_fails(self):
        run = control_run("real/crash-P3-r1.log", text="Running 1 test suites (1 total tests) across 1 workers\n")
        self.assertTrue(any("never started" in p for p in compare.check_controls(run, EXPECTATIONS)))


class MutatedFixtureTests(unittest.TestCase):
    EXPECTED = {
        "mutated/dropped-line-parallel.log": f"no result line for started test {PASS_ID}",
        "mutated/dropped-line-serial.log": "7 tests started in the log but the summary says Ran 8",
        "mutated/changed-outcome-unbalanced.log": "2 'skipped' records but the status line says skipped=1",
        "mutated/truncated.log": "no 'Ran N tests' line",
        "mutated/missing-ran-line.log": "no 'Ran N tests' line",
    }

    def test_each_mutated_copy_is_its_source_with_the_declared_edits(self):
        self.assertEqual(len(INDEX["mutations"]), 7)
        for spec in INDEX["mutations"]:
            with self.subTest(file=spec["file"]):
                expected = make_fixtures.apply_mutation(fixture_text(spec["source"]), spec["ops"])
                self.assertEqual(fixture_text(spec["file"]), expected)
                self.assertNotEqual(expected, fixture_text(spec["source"]))

    def test_log_level_mutations_are_flagged_by_the_parser(self):
        for relative, reason in self.EXPECTED.items():
            with self.subTest(file=relative):
                anomalies = compare.parse_log(fixture_text(relative)).anomalies
                self.assertTrue(any(reason in anomaly for anomaly in anomalies), anomalies)

    def test_self_consistent_mutations_parse_cleanly_and_fail_against_s(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.standard()
            shutil.rmtree(layout.root / "results" / "macos-15-P3-r2")
            layout.add("macos-15-P3-r2", "mutated/changed-outcome.log", exit_code=5,
                       command=RUNS["real/controls-P3-r1.log"]["command"])
            shutil.rmtree(layout.root / "results" / "macos-15-P3C-r3")
            layout.add("macos-15-P3C-r3", "mutated/extra-id.log", exit_code=5,
                       command=RUNS["real/controls-P3C-r1.log"]["command"])
            result = layout.result()
        self.assertEqual(compare.parse_log(fixture_text("mutated/changed-outcome.log")).anomalies, [])
        self.assertEqual(compare.parse_log(fixture_text("mutated/extra-id.log")).anomalies, [])
        changed = run_named(result, "macos-15-P3-r2")
        self.assertFalse(changed["eligible"])
        self.assertEqual(len(changed["reasons"]), 1, changed["reasons"])
        self.assertIn("1 ids differ from the S baseline", changed["reasons"][0])
        self.assertEqual(changed["mismatch_total"], 1)
        self.assertEqual(changed["count_deltas_vs_s"], {"skipped": 1})
        self.assertEqual(changed["mismatches"][0]["id"], PASS_ID)
        self.assertEqual(changed["mismatches"][0]["S"], [["test", PASS_ID, "ok"]])
        self.assertEqual(changed["mismatches"][0]["arm"], [["test", PASS_ID, "skipped"]])
        extra = run_named(result, "macos-15-P3C-r3")
        self.assertFalse(extra["eligible"])
        self.assertEqual(extra["extra_ids"], ["test_zz_trial_controls.TrialControlsA.test_extra"])
        self.assertTrue(any("ids outside the trial inventory ran" in reason for reason in extra["reasons"]))
        for name in ("macos-15-S-r1", "macos-15-P3-r1", "macos-15-P3-r3", "macos-15-P3C-r1"):
            self.assertTrue(run_named(result, name)["eligible"], run_named(result, name)["reasons"])
        arms = result["verdicts"]["macos-15"]["arms"]
        self.assertFalse(arms["P3"]["eligible"])
        self.assertFalse(arms["P3C"]["eligible"])


class ResultsDirectoryTests(unittest.TestCase):
    def test_real_s_and_parallel_logs_are_equivalent_and_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.standard(seconds={"S": (100.0, 104.0, 108.0), "P3": (50.0, 52.0, 55.0),
                                     "P3C": (45.0, 47.0, 70.0)})
            result = layout.result()
        for run in result["runs"]:
            self.assertTrue(run["eligible"], (run["name"], run["reasons"]))
            self.assertEqual(run["mismatch_total"], 0)
        self.assertTrue(all(item["passed"] for item in result["controls"]), result["controls"])
        verdict = result["verdicts"]["macos-15"]
        self.assertEqual(verdict["baseline"]["flaky_total"], 0)
        self.assertEqual(verdict["fastest_eligible_arm"], "P3C")
        self.assertEqual(verdict["arms"]["P3C"]["median_vs_s_median"], round(47 / 104, 4))
        self.assertEqual(verdict["arms"]["P3C"]["max_vs_s_fastest"], 0.7)
        self.assertEqual((verdict["outcome"], verdict["selected_arm"]), ("adopt", "P3C"))
        self.assertFalse(verdict["arms"]["P4"]["eligible"])
        self.assertTrue(result["id_mapping"]["ok"])

    def test_flaky_ids_in_s_are_listed_and_excluded(self):
        changed = make_fixtures.apply_mutation(fixture_text("real/controls-S-r1.log"), INDEX["mutations"][2]["ops"])
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.standard()
            shutil.rmtree(layout.root / "results" / "macos-15-S-r2")
            layout.add("macos-15-S-r2", "real/controls-S-r2.log", text=changed)
            result = layout.result()
        baseline = result["verdicts"]["macos-15"]["baseline"]
        self.assertEqual(baseline["flaky_ids"], [PASS_ID])
        for run in result["runs"]:
            self.assertTrue(run["eligible"], (run["name"], run["reasons"]))

    def test_run_level_integrity_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.standard()
            cases = {
                "macos-15-P4-r1": dict(log="real/controls-P3-r1.log"),  # P3's command under the P4 name
                "macos-15-P3F-r1": dict(log="real/controls-P3F-r1.log", exit_code=0),
                "macos-15-P3F-r2": dict(log="real/controls-P3F-r1.log", sha="another-sha"),
                "macos-15-P3F-r3": dict(log="real/controls-S-r1.log",
                                        command="python3 -m unittest_parallel -j 3 --level module "
                                                "--disable-process-pooling -v"),
                "ubuntu-24.04-L4F-r1": dict(log="real/controls-L4F-r1.log", python_version="3.12.3"),
                "macos-15-ZZ-r1": dict(log="real/controls-P3-r1.log"),
            }
            for name, kwargs in cases.items():
                layout.add(name, **kwargs)
            layout.add("ubuntu-24.04-S-r1", "real/controls-S-r1.log")
            (layout.root / "results" / "notes").mkdir()
            result = layout.result()
        reasons = {run["name"]: " | ".join(run["reasons"]) for run in result["runs"]}
        self.assertIn("command jobs=3, the arm needs 4", reasons["macos-15-P4-r1"])
        self.assertIn("exit status 0 disagrees with the status line FAILED", reasons["macos-15-P3F-r1"])
        self.assertIn("is not the frozen corpus synthetic-fixture-sha", reasons["macos-15-P3F-r2"])
        self.assertIn("no 'Running N test suites", reasons["macos-15-P3F-r3"])
        self.assertIn("python_version '3.12.3' differs from S", reasons["ubuntu-24.04-L4F-r1"])
        self.assertIn("arm ZZ is not preregistered for macos-15", reasons["macos-15-ZZ-r1"])
        self.assertTrue(any(item.startswith("notes:") for item in result["inputs"]["ignored_entries"]))
        self.assertEqual(result["verdicts"]["ubuntu-24.04"]["outcome"], "no verdict")

    def test_s_runs_on_different_interpreters_void_the_os(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.standard()
            shutil.rmtree(layout.root / "results" / "macos-15-S-r3")
            layout.add("macos-15-S-r3", "real/controls-S-r3.log", python_version="3.13.0")
            result = layout.result()
        for run in result["runs"]:
            self.assertIn("the S runs used different python_version values", " | ".join(run["reasons"]))
        self.assertEqual(result["verdicts"]["macos-15"]["outcome"], "no verdict")

    def test_a_serial_log_with_a_parallel_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.add("macos-15-S-r1", "real/controls-P3-r1.log", command="python3 -m unittest -v")
            result = layout.result(min_repeats=1)
        self.assertIn("a unittest-parallel header in a serial log", run_named(result, "macos-15-S-r1")["reasons"])

    def test_cli_writes_result_and_summary_and_rejects_bad_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.standard()
            out, summary = layout.root / "result.json", layout.root / "summary.md"
            argv = ["--results", str(layout.root / "results"), "--inventory-base", str(layout.inventory),
                    "--inventory-trial", str(layout.inventory), "--out", str(out), "--summary-md", str(summary)]
            printed, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(errors):
                self.assertEqual(compare.main(argv), 0)
                result = json.loads(out.read_text(encoding="utf-8"))
                self.assertEqual(result["schema"], compare.SCHEMA)
                self.assertIn("| macos-15 | P3 | 3 | 3 | 100.0 | 100.0 | 100.0 | 1.000 | 1.000 |",
                              summary.read_text(encoding="utf-8"))
                unsorted = layout.root / "unsorted.txt"
                unsorted.write_text("b.C.test\na.C.test\n", encoding="utf-8")
                argv[3] = str(unsorted)
                self.assertEqual(compare.main(argv), 2)
                unsorted.write_text("", encoding="utf-8")
                self.assertEqual(compare.main(argv), 2)
            self.assertEqual(printed.getvalue(), "macos-15: reject\n")  # equal timings miss the speed rule
            self.assertIn("not sorted and de-duplicated", errors.getvalue())
            self.assertIn("the inventory is empty", errors.getvalue())


class DecisionRuleTests(unittest.TestCase):
    def verdict(self, seconds, arms):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.standard(arms=arms, seconds=seconds)
            return layout.result()["verdicts"]["macos-15"]

    def test_the_unpooled_arm_is_preferred_within_ten_percent(self):
        verdict = self.verdict({"S": (100.0, 110.0, 120.0), "P3": (50.0, 55.0, 60.0), "P3F": (52.0, 58.0, 59.0)},
                               ("S", "P3", "P3F"))
        self.assertEqual(verdict["fastest_eligible_arm"], "P3")
        self.assertEqual(verdict["unpooled_preference"]["applied"], True)
        self.assertEqual((verdict["outcome"], verdict["selected_arm"]), ("adopt", "P3F"))

    def test_a_fastest_arm_missing_the_rule_rejects_without_falling_through(self):
        verdict = self.verdict({"S": (100.0, 110.0, 120.0), "P3": (40.0, 45.0, 90.0), "P3C": (60.0, 60.0, 61.0)},
                               ("S", "P3", "P3C"))
        self.assertEqual(verdict["fastest_eligible_arm"], "P3")
        self.assertTrue(verdict["arms"]["P3C"]["meets_speed_rule"])
        self.assertEqual((verdict["outcome"], verdict["selected_arm"]), ("reject", None))

    def test_a_missing_control_blocks_adoption(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.standard(arms=("S", "P3"), seconds={"S": (100.0, 100.0, 100.0), "P3": (40.0, 40.0, 40.0)})
            shutil.rmtree(layout.root / "results" / "macos-15-P3-crash")
            verdict = layout.result()["verdicts"]["macos-15"]
        self.assertIn("no crash run", verdict["arms"]["P3"]["reasons"])
        self.assertEqual(verdict["outcome"], "reject")


class IdMappingTests(unittest.TestCase):
    BASE_ONLY = [f"{module}.{cls}.test_{n}" for module, classes in (
        ("memory_patch_evidence_tests", ("EvidenceTests", "FunctionalFactsTests")),
        ("application_portability_tests", ("MakeBoundaryTests", "RecipeHistoryTests", "RestartPortTests")),
        ("wsl_transport_evidence_tests", ("TransportEvidenceTests",))) for cls in classes for n in (1, 2)]
    COMMON = ["tests.test_a.A.test_1", "tests.test_b.B.test_1"]
    PREFIX = "tests.test_native_maintenance."

    def test_a_dotted_prefix_rewrite_of_six_classes_is_a_bijection(self):
        trial = sorted(self.COMMON + [self.PREFIX + item for item in self.BASE_ONLY])
        report = compare.check_id_mapping(sorted(self.COMMON + self.BASE_ONLY), trial)
        self.assertTrue(report["ok"], report["problems"])
        self.assertEqual((report["mapped"], len(report["classes"])), (12, 6))
        self.assertEqual(report["prefixes"]["memory_patch_evidence_tests"], ["tests.test_native_maintenance"])

    def test_any_other_difference_fails(self):
        base = sorted(self.COMMON + self.BASE_ONLY)
        renamed = sorted(self.COMMON + [self.PREFIX + item for item in self.BASE_ONLY[1:]]
                         + ["tests.renamed_memory_patch_evidence_tests.EvidenceTests.test_1"])
        extra = sorted(self.COMMON + ["tests.test_c.C.test_1"] + [self.PREFIX + item for item in self.BASE_ONLY])
        mixed = sorted(self.COMMON + ["x." + self.BASE_ONLY[0]] + [self.PREFIX + item for item in self.BASE_ONLY[1:]])
        for trial in (renamed, extra, mixed):
            with self.subTest(trial=trial[:3]):
                self.assertFalse(compare.check_id_mapping(base, trial)["ok"])

    def test_identical_inventories_pass(self):
        self.assertTrue(compare.check_id_mapping(self.COMMON, self.COMMON)["ok"])


class IdsScriptTests(unittest.TestCase):
    def run_ids(self, root, *extra):
        return subprocess.run([sys.executable, str(HERE / "ids.py"), "--root", str(root), *extra],
                              capture_output=True, text=True, check=True, timeout=120)

    def test_ids_lists_sorted_unique_ids_honours_load_tests_and_runs_no_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
            marker = root / "ran"
            body = (f"import pathlib, unittest\nMARK = pathlib.Path({str(marker)!r})\n"
                    "def setUpModule():\n    MARK.write_text('setUpModule')\n"
                    "class B(unittest.TestCase):\n"
                    "    @classmethod\n    def setUpClass(cls):\n        MARK.write_text('setUpClass')\n"
                    "    def test_z(self):\n        MARK.write_text('body')\n"
                    "    def test_a(self):\n        MARK.write_text('body')\n")
            (root / "tests" / "test_b.py").write_text(body, encoding="utf-8")
            (root / "extra_cases.py").write_text(
                "import unittest\nclass Extra(unittest.TestCase):\n    def test_x(self):\n        raise SystemExit(9)\n",
                encoding="utf-8")
            (root / "tests" / "test_loader.py").write_text(
                "import importlib.util, pathlib, unittest\n"
                "def load_tests(loader, tests, pattern):\n"
                "    path = pathlib.Path(__file__).resolve().parents[1] / 'extra_cases.py'\n"
                "    spec = importlib.util.spec_from_file_location('extra_cases_bare', path)\n"
                "    module = importlib.util.module_from_spec(spec)\n    spec.loader.exec_module(module)\n"
                "    suite = unittest.TestSuite()\n    suite.addTests(loader.loadTestsFromModule(module))\n"
                "    return suite\n", encoding="utf-8")
            completed = self.run_ids(root)
            self.assertFalse(marker.exists(), "discovery ran a test body or fixture")
        self.assertEqual(completed.stdout.split("\n"),
                         ["extra_cases_bare.Extra.test_x", "tests.test_b.B.test_a", "tests.test_b.B.test_z", ""])
        self.assertIn("3 unique ids; countTestCases() 3", completed.stderr)

    def test_ids_reproduces_the_stored_control_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(HERE / "controls" / "test_zz_trial_controls.py", tmp)
            completed = self.run_ids(tmp, "--start-directory", ".")
        self.assertEqual(completed.stdout, fixture_text("inventory-controls.txt"))
        self.assertEqual(len(completed.stdout.split("\n")) - 1, 9)


class ParserEdgeCaseTests(unittest.TestCase):
    """Synthetic edits of real fixture logs that reproduce shapes seen in real CI logs."""

    def serial(self):
        return fixture_text("real/controls-S-r1.log").split("\n")

    def test_a_status_after_test_output_or_glued_to_it_is_recovered(self):
        lines = self.serial()
        index = lines.index(f"test_pass ({PASS_ID}) ... ok")
        later = lines[:index] + [f"test_pass ({PASS_ID}) ... ", "exporter 127.0.0.1:49275 deregistered", "ok"] + lines[index + 1:]
        glued = lines[:index] + [f"test_pass ({PASS_ID}) ... ", '{"status": "checked"}', '{"a": 1}}}}ok'] + lines[index + 1:]
        for text in ("\n".join(later), "\n".join(glued)):
            parsed = compare.parse_log(text)
            self.assertEqual(parsed.anomalies, [])
            self.assertIn(("test", PASS_ID, "ok"), parsed.records())
            self.assertEqual(len(parsed.notes), 2)

    def test_the_summary_need_not_be_the_last_block(self):
        text = fixture_text("real/controls-S-r1.log") + '{"flushed": "stdout at exit"}\nRan 3 tests in nothing\n'
        parsed = compare.parse_log(text)
        self.assertEqual((parsed.anomalies, parsed.ran), ([], 8))

    def test_a_durations_table_is_skipped(self):
        lines = self.serial()
        ran = next(i for i, line in enumerate(lines) if line.startswith("Ran 8 tests in "))
        table = ["Slowest test durations", compare.SEP2, f"0.002s     test_pass ({PASS_ID})", ""]
        parsed = compare.parse_log("\n".join(lines[:ran - 1] + table + lines[ran - 1:]))
        self.assertEqual(parsed.anomalies, [])
        self.assertTrue(parsed.durations_section)

    def test_parallel_output_glued_before_or_after_records_is_tolerated(self):
        lines = fixture_text("real/controls-P3C-r1.log").split("\n")
        result = f"test_pass ({PASS_ID}) ... ok"
        index = lines.index(result)
        lines[index] = '{"pending_lanes": 1}}}}' + result  # a partial stdout chunk of another worker
        # UP main.py:392 writes "<description>\n<docstring> ... ok" and then "\n" in a second write;
        # another worker's complete line can land between the two writes.
        skip = "test_skip (test_zz_trial_controls.TrialControlsA.test_skip) ... skipped 'control: skipped on purpose'"
        lines.remove(skip)
        doc = lines.index("Control: this first docstring line becomes a second description line. ... ok")
        lines[doc:doc + 1] = [lines[doc] + skip, ""]
        parsed = compare.parse_log("\n".join(lines))
        self.assertEqual(parsed.anomalies, [])
        self.assertEqual(sorted(parsed.records()),
                         sorted(compare.parse_log(fixture_text("real/controls-P3C-r1.log")).records()))
        self.assertTrue(any("glued before" in note for note in parsed.notes))
        self.assertTrue(any("glued after the docstring line" in note for note in parsed.notes))

    def test_a_subtest_status_written_after_other_workers_text_is_reattached(self):
        # CPython runner.py:64-75 writes "  <description>\n<docstring>" and " ... FAIL\n" as separate
        # flushes; both shapes below were seen in real local unittest-parallel runs of a noisy suite.
        original = fixture_text("real/controls-P3C-r1.log")
        lines = original.split("\n")
        sub = "  test_subtest_fails (test_zz_trial_controls.TrialControlsB.test_subtest_fails) (i=1)"
        doc = "Control: subtest i=1 fails; i=0 and i=2 pass."
        skip = "test_skip (test_zz_trial_controls.TrialControlsA.test_skip) ... skipped 'control: skipped on purpose'"
        at = lines.index(sub)
        self.assertEqual(lines[at + 1], doc + " ... FAIL")
        own_line = list(lines)
        own_line.remove(skip)
        at = own_line.index(sub)
        own_line[at + 1:at + 2] = [doc + skip, " ... FAIL"]
        multi = "test_multiline_docstring (test_zz_trial_controls.TrialControlsB.test_multiline_docstring)"
        multi_doc = "Control: this first docstring line becomes a second description line."
        on_start = [line for line in lines if line not in (multi, multi_doc + " ...", multi_doc + " ... ok")]
        at = on_start.index(sub)
        on_start[at + 1:at + 2] = [doc + multi, multi_doc + " ... ... FAIL", "", multi, multi_doc + " ... ok"]
        expected = sorted(compare.parse_log(original).records())
        for text in ("\n".join(own_line), "\n".join(on_start)):
            parsed = compare.parse_log(text)
            self.assertEqual(parsed.anomalies, [])
            self.assertEqual(sorted(parsed.records()), expected)
            self.assertTrue(any("completed by a separately written fragment" in note for note in parsed.notes))


class PlacementTests(unittest.TestCase):
    def test_controls_stay_outside_production_discovery(self):
        # python3 -m unittest discovers from the checkout root and descends only into packages
        # (CPython Lib/unittest/loader.py, v3.13.16 :385-429 _find_test_path); no directory from the root
        # down to the controls may hold an __init__.py, or the failing controls would join CI.
        root = HERE.parents[2]
        self.assertTrue((root / "tests" / "__init__.py").is_file())
        directory = HERE / "controls" / "crash_control"
        while directory != root:
            self.assertFalse((directory / "__init__.py").exists(), directory.relative_to(root))
            directory = directory.parent


if __name__ == "__main__":
    unittest.main()
