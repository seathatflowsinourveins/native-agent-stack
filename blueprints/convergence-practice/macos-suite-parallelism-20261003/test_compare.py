"""Tests for the suite-parallelism oracle (stdlib unittest; local integration and synthetic fixtures).

  python3 -m unittest discover -s blueprints/convergence-practice/macos-suite-parallelism-20261003 -p test_compare.py

fixtures/real/ holds sanitized logs of real local runs of the controls (make_fixtures.py,
fixtures/index.json); fixtures/mutated/ holds copies with declared edits that the oracle
must flag. Results directories are assembled from those logs in temporary directories, in
the workflow's layout: every run directory also holds git-status.txt (empty: a clean
checkout) and runtime.json (run_attempt "1"), and every timed run also carries passing
records of 29 synthetic ids with the shape of the six B1 classes, as runs of the trial head
do, so that the production id rule (compare.B1_*) holds between the base and trial
inventories. None of this is upstream acceptance or a GitHub-hosted run.
"""

import collections
import contextlib
import hashlib
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIXTURES = HERE / "fixtures"
WORKFLOW = ROOT / ".github" / "workflows" / "macos-suite-parallel-trial.yml"


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
# The real shape of the B1 classes at base 56473e4b (ids.py on the base: 29 ids in these six classes, in the order
# of compare.B1_CLASSES), with synthetic method names.
B1_SHAPE = (("memory_patch_evidence_tests", (("EvidenceTests", 6), ("FunctionalFactsTests", 7))),
            ("application_portability_tests", (("MakeBoundaryTests", 2), ("RecipeHistoryTests", 2),
                                               ("RestartPortTests", 2))),
            ("wsl_transport_evidence_tests", (("TransportEvidenceTests", 10),)))
B1_BASE = [f"{module}.{cls}.test_{n}" for module, classes in B1_SHAPE for cls, count in classes
           for n in range(1, count + 1)]
B1_PREFIX = "tests.test_native_maintenance."
B1_TRIAL = [B1_PREFIX + item for item in B1_BASE]
CONTROL_IDS = (FIXTURES / "inventory-controls.txt").read_text(encoding="utf-8").split("\n")[:-1]


def fixture_text(relative):
    return (FIXTURES / relative).read_text(encoding="utf-8")


def inventory_text(ids):
    return "".join(f"{item}\n" for item in sorted(ids))


def with_b1_records(text, arm_spec):
    """The log with passing records of the 29 prefixed B1 ids added, as a timed run of the trial head carries them:
    the Ran count grows by 29 and a unittest-parallel header by 29 tests and one module suite (module level) or six
    class suites (class level), with workers min(suites, jobs) (UP main.py:131). A serial log gets one result line
    per test (CPY runner.py:56-75), a parallel log a start and a result line (UP main.py:377-419)."""
    lines = text.split("\n")
    header = compare.HEADER_RE.search(lines[0])
    records = []
    for item in B1_TRIAL:
        description = f"{item.rsplit('.', 1)[1]} ({item})"
        records.extend([f"{description} ...", f"{description} ... ok"] if header else [f"{description} ... ok"])
    at = 2 if header else 0
    lines[at:at] = records
    for index, line in enumerate(lines):
        ran = compare.RAN_RE.match(line)
        if ran:
            lines[index] = f"Ran {int(ran.group(1)) + len(B1_TRIAL)} tests in {ran.group(2)}s"
    if header:
        suites, total, workers = (int(header.group(n)) for n in (1, 2, 3))
        if arm_spec and arm_spec["runner"] == "unittest_parallel":
            suites += 1 if arm_spec["level"] == "module" else sum(len(classes) for _, classes in B1_SHAPE)
            workers = max(1, min(suites, arm_spec["jobs"]))
        lines[0] = (lines[0][:header.start()]
                    + f"Running {suites} test suites ({total + len(B1_TRIAL)} total tests) across {workers} workers")
    return "\n".join(lines)


def control_run(relative, os_name=None, arm=None, exit_code=None, text=None):
    entry = RUNS.get(relative, {})
    arm = arm or entry["config"]
    run = compare.Run(relative, os_name or OS_OF[arm], arm, entry.get("kind", "controls"), 1)
    run.exit_code = entry.get("exit_code") if exit_code is None else exit_code
    run.parsed = compare.parse_log(fixture_text(relative) if text is None else text)
    return run


class Layout:
    """A results directory in the trial layout, built from fixture logs, with the production-shaped base and trial
    inventories: the control ids plus the 29 B1 ids, bare in the base and prefixed in the trial."""

    def __init__(self, root):
        self.root = Path(root)
        self.inventory = self.root / "inventory.txt"
        self.inventory.write_text(inventory_text(CONTROL_IDS + B1_TRIAL), encoding="utf-8")
        self.base_inventory = self.root / "inventory-base.txt"
        self.base_inventory.write_text(inventory_text(CONTROL_IDS + B1_BASE), encoding="utf-8")

    def add(self, name, log, exit_code=None, seconds=100.0, command=None, sha="synthetic-fixture-sha", text=None,
            python_version=None, git_status="", runtime=None, b1=True):
        """git_status None leaves git-status.txt out; runtime is runtime.json's content (default run_attempt "1"),
        or False to leave it out; b1 False keeps a timed run's log without the B1 records."""
        match = compare.RUN_DIR_RE.match(name)
        arm = match.group("arm")
        entry = RUNS.get(log, {})
        directory = self.root / "results" / name
        directory.mkdir(parents=True)
        body = fixture_text(log) if text is None else text
        if b1 and match.group("rep"):
            body = with_b1_records(body, compare.ARMS[match.group("os")].get(arm))
        (directory / "log.txt").write_text(body, encoding="utf-8")
        code = entry.get("exit_code") if exit_code is None else exit_code
        (directory / "exit-code.txt").write_text(f"{code}\n", encoding="utf-8")
        meta = {"os": match.group("os"), "arm": arm, "repeat": int(match.group("rep") or match.group("krep") or 1),
                "command": command or entry.get("command"), "python_version": python_version or INDEX["host"]["python_version"],
                "platform": INDEX["host"]["platform"], "runner_image": "local fixture (not a GitHub-hosted runner)",
                "checkout_sha": sha, "step_seconds": seconds}
        (directory / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        if git_status is not None:
            (directory / "git-status.txt").write_text(git_status, encoding="utf-8")
        if runtime is not False:
            runtime = {"run_attempt": "1"} if runtime is None else runtime
            (directory / "runtime.json").write_text(json.dumps(runtime), encoding="utf-8")
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
        """build_result over the layout; base replaces the base inventory's ids (the trial inventory stays)."""
        base_path = self.base_inventory
        if base is not None:
            base_path = self.root / "inventory-base-replaced.txt"
            base_path.write_text("".join(f"{item}\n" for item in base), encoding="utf-8")
        return compare.build_result(self.root / "results", base_path, self.inventory,
                                    HERE / "controls" / "control_expectations.json", min_repeats)

    def write(self, name, filename, text=None):
        """Replace (text) or remove (None) one file of a run directory."""
        path = self.root / "results" / name / filename
        if text is None:
            path.unlink()
        else:
            path.write_text(text, encoding="utf-8")


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


class FixtureFreezeTests(unittest.TestCase):
    """experiment.json freezes fixtures/index.json and fixtures/inventory-controls.txt by hash. Every other file under
    fixtures/ is frozen through the per-file sha256 that index.json lists for it, which this test checks, so a changed,
    added or removed fixture log fails here and in the trial's compare job."""

    def test_every_fixture_log_matches_its_sha256_in_the_index(self):
        listed = {entry["file"]: entry["sha256"] for entry in INDEX["runs"] + INDEX["mutations"]}
        self.assertEqual(len(listed), len(INDEX["runs"]) + len(INDEX["mutations"]), "a file is listed twice")
        self.assertEqual((len(INDEX["runs"]), len(INDEX["mutations"])), (20, 7))
        present = sorted(path.relative_to(FIXTURES).as_posix() for path in FIXTURES.rglob("*") if path.is_file())
        self.assertEqual(present, sorted([*listed, "index.json", "inventory-controls.txt"]))
        for relative, digest in sorted(listed.items()):
            with self.subTest(file=relative):
                self.assertEqual(hashlib.sha256((FIXTURES / relative).read_bytes()).hexdigest(), digest)


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
            argv = ["--results", str(layout.root / "results"), "--inventory-base", str(layout.base_inventory),
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
            # Equal timings miss the speed rule on macos-15; ubuntu-24.04 has no run directory and is listed anyway.
            self.assertEqual(printed.getvalue(), "macos-15: reject\nubuntu-24.04: no verdict\n")
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

    def test_the_speed_rule_compares_exact_ratios(self):
        # F1: true ratios of 0.600040 and 0.750040 round to the thresholds at four decimals but exceed them.
        s = (100000.0, 100000.0, 100000.0)
        cases = [("median ratio 0.600040", (60004.0, 60004.0, 70000.0), "reject", "15001/25000", "7/10"),
                 ("max ratio 0.750040", (50000.0, 50000.0, 75004.0), "reject", "1/2", "18751/25000"),
                 ("both exactly at 0.6000 and 0.7500", (60000.0, 60000.0, 75000.0), "adopt", "3/5", "3/4")]
        for label, p3, outcome, median_exact, max_exact in cases:
            with self.subTest(label):
                verdict = self.verdict({"S": s, "P3": p3}, ("S", "P3"))
                self.assertEqual((verdict["outcome"], verdict["selected_arm"]),
                                 (outcome, "P3" if outcome == "adopt" else None))
                entry = verdict["arms"]["P3"]
                self.assertEqual(entry["meets_speed_rule"], outcome == "adopt")
                self.assertEqual((entry["median_vs_s_median_exact"], entry["max_vs_s_fastest_exact"]),
                                 (median_exact, max_exact))
                # The rounded fields are for display only: 0.600040 shows as 0.6 and still rejects.
                self.assertLessEqual(entry["median_vs_s_median"], 0.6)
                self.assertLessEqual(entry["max_vs_s_fastest"], 0.75)
        # The unpooled preference is exact too: 1.10 x the pooled median applies, one second more does not.
        for p3f, applied in (((55000.0, 55000.0, 55000.0), True), ((55001.0, 55001.0, 55001.0), False)):
            with self.subTest(p3f=p3f):
                verdict = self.verdict({"S": s, "P3": (50000.0, 50000.0, 50000.0), "P3F": p3f}, ("S", "P3", "P3F"))
                self.assertEqual(verdict["unpooled_preference"]["applied"], applied)
                self.assertEqual(verdict["selected_arm"], "P3F" if applied else "P3")


class ExactCommandTests(unittest.TestCase):
    """F2: a run's command must be its arm's preregistered command token for token (S may add --durations N)."""

    def test_wrappers_interpreter_flags_and_other_spellings_are_rejected(self):
        macos, linux = compare.ARMS["macos-15"], compare.ARMS["ubuntu-24.04"]
        rejected = [
            ("coverage run -m unittest -v", macos["S"]),
            ("python3 -X dev -m unittest -v", macos["S"]),
            ("python3 -O -m unittest_parallel -j 3 --level module -v", macos["P3"]),
            ("timeout 300 python3 -m unittest -v", macos["S"]),
            ("python -m unittest -v", macos["S"]),
            ("python3 -m unittest -v --durations 0", macos["S"]),
            ("python3 -m unittest -v --durations 25 --durations 5", macos["S"]),
            ("python3 -m unittest --durations 25 -v", macos["S"]),
            ("python3 -m unittest_parallel -j 3 --level module -v --durations 25", macos["P3"]),
            ("python3 -m unittest_parallel -v -j 3 --level module", macos["P3"]),
            ("python3 -m unittest_parallel -j3 --level module -v", macos["P3"]),
            ("python3 -m unittest_parallel --jobs 3 --level=module -v", macos["P3"]),
            ("unittest-parallel -j 3 --level module -v", macos["P3"]),
            ("python3 -m unittest_parallel -j 4 --level module -v -s .", linux["L4"]),
        ]
        for command, spec in rejected:
            with self.subTest(command=command):
                problems = compare.command_problems(command, spec)
                self.assertTrue(problems)
                self.assertIn("is not the arm's preregistered command", problems[0])
        flagged = compare.command_problems("coverage run -m unittest -v", macos["S"])
        self.assertTrue(any("before the runner" in problem and "coverage" in problem for problem in flagged), flagged)
        accepted = [(" ".join(spec["command"]), spec) for arms in compare.ARMS.values() for spec in arms.values()]
        accepted.append(("python3 -m unittest -v --durations 25", linux["S"]))
        for command, spec in accepted:
            with self.subTest(command=command):
                self.assertEqual(compare.command_problems(command, spec), [])

    def test_a_wrapped_command_makes_the_run_ineligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.standard(arms=("S", "P3"), seconds={"S": (100.0, 100.0, 100.0), "P3": (40.0, 40.0, 40.0)})
            meta_path = layout.root / "results" / "macos-15-P3-r2" / "meta.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["command"] = "python3 -X dev -m unittest_parallel -j 3 --level module -v"
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            result = layout.result()
        self.assertFalse(run_named(result, "macos-15-P3-r2")["eligible"])
        self.assertEqual(result["verdicts"]["macos-15"]["outcome"], "reject")


class StrictIdMappingTests(unittest.TestCase):
    """F3: the single prefix on exactly the 29 base ids of the six B1 classes, as a bijection; else no verdict."""

    COMMON = ["tests.test_a.A.test_1", "tests.test_b.B.test_1"]

    def test_a_partial_rewrite_or_another_prefix_fails(self):
        base = sorted(self.COMMON + B1_BASE)
        self.assertTrue(compare.check_id_mapping(base, sorted(self.COMMON + B1_TRIAL))["ok"])
        wsl = "wsl_transport_evidence_tests."
        trials = {
            "28 of 29 rewritten": sorted(self.COMMON + B1_TRIAL[1:] + B1_BASE[:1]),
            "another prefix for one module": sorted(
                self.COMMON + [("tests.other." if item.startswith(wsl) else B1_PREFIX) + item for item in B1_BASE]),
            "one other prefix for every module": sorted(self.COMMON + ["tests.native." + item for item in B1_BASE]),
            "a non-B1 id renamed as well": sorted(["tests.test_native_maintenance.tests.test_a.A.test_1",
                                                   "tests.test_b.B.test_1"] + B1_TRIAL),
        }
        for label, trial in trials.items():
            with self.subTest(label):
                report = compare.check_id_mapping(base, trial)
                self.assertFalse(report["ok"], report)

    def test_the_base_must_hold_the_29_b1_ids(self):
        # 28 base ids, all rewritten with the right prefix: a bijection, but not the preregistered rewrite.
        base = sorted(self.COMMON + B1_BASE[1:])
        trial = sorted(self.COMMON + B1_TRIAL[1:])
        report = compare.check_id_mapping(base, trial)
        self.assertFalse(report["ok"])
        self.assertIn("the base inventory holds 28 ids of the six B1 classes; the preregistration names 29",
                      report["problems"])

    def test_a_failed_mapping_gives_no_verdict_on_every_os(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.standard(seconds={"S": (100.0, 100.0, 100.0), "P3": (50.0, 50.0, 50.0), "P3C": (55.0, 56.0, 57.0)})
            layout.standard(os_name="ubuntu-24.04", arms=("S", "L4", "L4C"),
                            seconds={"S": (100.0, 100.0, 100.0), "L4": (50.0, 50.0, 50.0), "L4C": (55.0, 56.0, 57.0)})
            passing = layout.result()
            broken = {"an extra base id": sorted(CONTROL_IDS + B1_BASE + ["tests.test_gone.G.test_1"]),
                      "28 of the 29 B1 base ids": sorted(CONTROL_IDS + B1_BASE[1:])}
            results = {label: layout.result(base=base) for label, base in broken.items()}
        self.assertTrue(passing["id_mapping"]["ok"], passing["id_mapping"]["problems"])
        self.assertEqual({os_name: (verdict["outcome"], verdict["selected_arm"])
                          for os_name, verdict in passing["verdicts"].items()},
                         {"macos-15": ("adopt", "P3"), "ubuntu-24.04": ("adopt", "L4")})
        for label, result in results.items():
            with self.subTest(label):
                self.assertFalse(result["id_mapping"]["ok"])
                self.assertEqual(sorted(result["verdicts"]), ["macos-15", "ubuntu-24.04"])
                for os_name, verdict in result["verdicts"].items():
                    self.assertEqual((verdict["outcome"], verdict["selected_arm"]), ("no verdict", None), os_name)
                    self.assertIn("id_mapping.ok is false", verdict["reasons"][0])


class EveryOsListedTests(unittest.TestCase):
    """Every OS of compare.ARMS is listed in result.json and in the summary. An OS without any run directory gets no
    verdict with the reason "no run directory", and a failed id mapping gives every OS no verdict, with or without
    runs."""

    SECONDS = {"S": (100.0, 100.0, 100.0), "P3": (40.0, 40.0, 40.0)}

    def test_an_os_without_run_directories_is_listed_with_no_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.standard(arms=("S", "P3"), seconds=self.SECONDS)
            result = layout.result()
        self.assertEqual(sorted(result["verdicts"]), sorted(compare.ARMS))
        macos, linux = result["verdicts"]["macos-15"], result["verdicts"]["ubuntu-24.04"]
        self.assertEqual((macos["outcome"], macos["selected_arm"]), ("adopt", "P3"))
        self.assertEqual((linux["outcome"], linux["selected_arm"], linux["reasons"]),
                         ("no verdict", None, ["no run directory"]))
        self.assertEqual(sorted(linux["arms"]), sorted(compare.ARMS["ubuntu-24.04"]))
        for arm, entry in linux["arms"].items():
            with self.subTest(arm=arm):
                self.assertEqual((entry["runs"], entry["eligible_runs"], entry["eligible"]), (0, 0, False))
        self.assertEqual(linux["baseline"]["s_runs"], 0)
        summary = compare.summary_markdown(result)
        self.assertIn("- **ubuntu-24.04**: no verdict (no run directory); flaky ids in S: 0", summary)
        for arm in compare.ARMS["ubuntu-24.04"]:
            self.assertIn(f"| ubuntu-24.04 | {arm} | 0 | 0 | - | - | - | - | - | - | - | no |", summary)

    def test_an_empty_results_directory_gives_no_verdict_on_every_os(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            (layout.root / "results").mkdir()
            result = layout.result()
        self.assertTrue(result["id_mapping"]["ok"], result["id_mapping"]["problems"])
        self.assertEqual(sorted(result["verdicts"]), sorted(compare.ARMS))
        for os_name, verdict in result["verdicts"].items():
            with self.subTest(os=os_name):
                self.assertEqual((verdict["outcome"], verdict["selected_arm"], verdict["reasons"]),
                                 ("no verdict", None, ["no run directory"]))
        summary = compare.summary_markdown(result)
        for os_name in compare.ARMS:
            self.assertIn(f"- **{os_name}**: no verdict (no run directory)", summary)

    def test_a_failed_mapping_gives_no_verdict_to_an_os_with_or_without_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.standard(arms=("S", "P3"), seconds=self.SECONDS)
            result = layout.result(base=sorted(CONTROL_IDS + B1_BASE[1:]))
        self.assertFalse(result["id_mapping"]["ok"])
        macos, linux = result["verdicts"]["macos-15"], result["verdicts"]["ubuntu-24.04"]
        for verdict in (macos, linux):
            self.assertEqual((verdict["outcome"], verdict["selected_arm"]), ("no verdict", None))
            self.assertIn("id_mapping.ok is false", verdict["reasons"][0])
        self.assertEqual(linux["reasons"][1:], ["no run directory"])
        summary = compare.summary_markdown(result)
        self.assertIn("- **macos-15**: no verdict (id_mapping.ok is false", summary)
        self.assertIn("; no run directory); flaky ids in S: 0", summary)
        self.assertIn("- id mapping: FAILED, so no OS gets a verdict", summary)


class CheckoutStatusTests(unittest.TestCase):
    """F4, ORACLE PART 2: every run directory's git-status.txt exists and is empty, controls included."""

    def outcome(self, name, text):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.standard(arms=("S", "P3"), seconds={"S": (100.0, 100.0, 100.0), "P3": (40.0, 40.0, 40.0)})
            if name is not None:
                layout.write(name, "git-status.txt", text)
            return layout.result()

    def test_a_dirty_or_unrecorded_run_makes_its_arm_ineligible(self):
        self.assertEqual(self.outcome(None, None)["verdicts"]["macos-15"]["outcome"], "adopt")
        cases = {"dirty": ("?? tests/test_leftover.py\n", "the checkout was not clean after the run"),
                 "missing": (None, "git-status.txt is missing"),
                 "git status failed": ("git status failed\n", "says git status failed"),
                 "blank line": ("\n", "the checkout was not clean after the run")}
        for label, (text, reason) in cases.items():
            with self.subTest(label):
                result = self.outcome("macos-15-P3-r2", text)
                run = run_named(result, "macos-15-P3-r2")
                self.assertFalse(run["eligible"])
                self.assertTrue(any(reason in item for item in run["reasons"]), run["reasons"])
                verdict = result["verdicts"]["macos-15"]
                self.assertFalse(verdict["arms"]["P3"]["eligible"])
                self.assertEqual((verdict["outcome"], verdict["selected_arm"]), ("reject", None))

    def test_a_dirty_s_run_leaves_the_os_without_a_verdict(self):
        result = self.outcome("macos-15-S-r1", " M tests/test_native_maintenance.py\n")
        self.assertEqual(result["verdicts"]["macos-15"]["outcome"], "no verdict")
        self.assertFalse(run_named(result, "macos-15-S-r1")["eligible"])
        self.assertEqual(run_named(result, "macos-15-S-r1")["checkout_clean"], False)

    def test_a_dirty_or_unrecorded_control_run_fails_its_arm(self):
        for name, text in (("macos-15-P3-controls", "?? leftover\n"), ("macos-15-P3-crash", None)):
            with self.subTest(name):
                result = self.outcome(name, text)
                control = next(item for item in result["controls"] if item["name"] == name)
                self.assertFalse(control["passed"])
                verdict = result["verdicts"]["macos-15"]
                self.assertFalse(verdict["arms"]["P3"]["eligible"])
                self.assertEqual(verdict["outcome"], "reject")


class RunAttemptTests(unittest.TestCase):
    """F5: a job re-run voids the run; run_attempt above 1, or none recorded, is ineligible (fail-closed)."""

    def outcome(self, name, runtime):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.standard(arms=("S", "P3"), seconds={"S": (100.0, 100.0, 100.0), "P3": (40.0, 40.0, 40.0)})
            if name is not None:
                layout.write(name, "runtime.json", None if runtime is None else json.dumps(runtime))
            return layout.result()

    def test_a_re_run_or_an_unrecorded_attempt_makes_the_run_ineligible(self):
        clean = self.outcome(None, None)
        self.assertEqual(clean["verdicts"]["macos-15"]["outcome"], "adopt")
        self.assertEqual(self.outcome("macos-15-P3-r2", {"run_attempt": 1})["verdicts"]["macos-15"]["outcome"],
                         "adopt")
        cases = {"attempt 2": ({"run_attempt": "2"}, "run_attempt 2: a job re-run voids this run"),
                 "attempt 3 as a number": ({"run_attempt": 3}, "run_attempt 3"),
                 "no run_attempt key": ({"image_os": "macos15"}, "the run attempt is unrecorded"),
                 "empty run_attempt": ({"run_attempt": ""}, "the run attempt is unrecorded"),
                 "attempt 0": ({"run_attempt": "0"}, "the run attempt is unrecorded"),
                 "no runtime.json": (None, "runtime.json is missing")}
        for label, (runtime, reason) in cases.items():
            with self.subTest(label):
                result = self.outcome("macos-15-P3-r2", runtime)
                run = run_named(result, "macos-15-P3-r2")
                self.assertFalse(run["eligible"])
                self.assertTrue(any(reason in item for item in run["reasons"]), run["reasons"])
                self.assertEqual(result["verdicts"]["macos-15"]["outcome"], "reject")
        self.assertEqual({run["run_attempt"] for run in clean["runs"]}, {1})

    def test_a_re_run_s_or_control_run_blocks_the_verdict(self):
        self.assertEqual(self.outcome("macos-15-S-r3", {"run_attempt": "2"})["verdicts"]["macos-15"]["outcome"],
                         "no verdict")
        for name in ("macos-15-P3-controls", "macos-15-P3-crash"):
            with self.subTest(name):
                result = self.outcome(name, {"run_attempt": "2"})
                control = next(item for item in result["controls"] if item["name"] == name)
                self.assertFalse(control["passed"])
                self.assertEqual(control["run_attempt"], 2)
                self.assertEqual(result["verdicts"]["macos-15"]["outcome"], "reject")


class IdMappingTests(unittest.TestCase):
    # The six B1 classes with their real id counts at base 56473e4b (29 ids; this set held 12 before the rule
    # required exactly those 29).
    BASE_ONLY = B1_BASE
    COMMON = ["tests.test_a.A.test_1", "tests.test_b.B.test_1"]
    PREFIX = B1_PREFIX

    def test_a_dotted_prefix_rewrite_of_six_classes_is_a_bijection(self):
        trial = sorted(self.COMMON + [self.PREFIX + item for item in self.BASE_ONLY])
        report = compare.check_id_mapping(sorted(self.COMMON + self.BASE_ONLY), trial)
        self.assertTrue(report["ok"], report["problems"])
        self.assertEqual((report["mapped"], len(report["classes"])), (29, 6))
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

    def test_identical_inventories_fail_without_the_b1_rewrite(self):
        # This test asserted ok for identical inventories while the rule allowed "no rewrite at all"; the trial head
        # must carry the B1 rewrite of exactly the 29 base ids, so identical inventories now fail.
        self.assertFalse(compare.check_id_mapping(self.COMMON, self.COMMON)["ok"])
        both = sorted(self.COMMON + self.BASE_ONLY)
        report = compare.check_id_mapping(both, both)
        self.assertFalse(report["ok"])
        self.assertIn("29 of the 29 B1 base ids are not rewritten in the trial", " | ".join(report["problems"]))


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


class MakeFixturesGuardTests(unittest.TestCase):
    """F6: --work must lie outside the checkout and be empty or absent; the tool deletes nothing it did not create.
    The interpreter given is a path that does not exist, so nothing past the guard can run."""

    def run_tool(self, work, cwd):
        missing_python = str(Path(tempfile.gettempdir()) / "no-such-dir-for-make-fixtures" / "python")
        return subprocess.run([sys.executable, str(HERE / "make_fixtures.py"), "--parallel-python", missing_python,
                               "--work", str(work)], cwd=cwd, capture_output=True, text=True, timeout=120)

    def test_work_at_or_inside_the_checkout_is_rejected(self):
        before = sorted(path.name for path in ROOT.iterdir())
        for work in (".", "tests", ROOT, ROOT / "tests", HERE, ROOT / "no-such-directory-yet"):
            with self.subTest(work=str(work)):
                completed = self.run_tool(work, ROOT)
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn("--work must be outside the checkout", completed.stderr)
        self.assertEqual(sorted(path.name for path in ROOT.iterdir()), before)
        self.assertFalse((ROOT / "no-such-directory-yet").exists())

    def test_a_non_empty_work_directory_is_refused_and_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            keep = Path(tmp) / "controls-S-r1" / "keep.txt"
            keep.parent.mkdir()
            keep.write_text("not created by make_fixtures.py\n", encoding="utf-8")
            completed = self.run_tool(tmp, tmp)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("--work must be an empty or absent directory", completed.stderr)
            self.assertEqual(keep.read_text(encoding="utf-8"), "not created by make_fixtures.py\n")


class PreregistrationAgreementTests(unittest.TestCase):
    """The oracle's arms, the trial workflow and README.md name the same commands, and the workflow records what
    the oracle reads (git-status.txt and runtime.json with the run attempt) without overwriting any artifact."""

    def steps(self):
        return WORKFLOW.read_text(encoding="utf-8").split("\n      - name: ")

    def test_the_workflow_and_the_readme_run_exactly_the_oracles_commands(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        found = collections.defaultdict(set)
        for match in re.finditer(r"^ +(\w+)\)\n +set -- (python3 [^\n]+)$", text, re.M):
            found[match.group(1)].add(tuple(match.group(2).split()))
        expected = {arm: {spec["command"]} for arms in compare.ARMS.values() for arm, spec in arms.items()}
        self.assertEqual(dict(found), expected)
        self.assertEqual(text.count('set -- "$@" --durations 25'), 2)
        readme = (HERE / "README.md").read_text(encoding="utf-8")
        rows = re.findall(r"^\| (macos-15|ubuntu-24\.04) \| (\w+) \| `([^`]+)` \|$", readme, re.M)
        self.assertEqual({(os_name, arm): tuple(command.split()) for os_name, arm, command in rows},
                         {(os_name, arm): spec["command"] for os_name, arms in compare.ARMS.items()
                          for arm, spec in arms.items()})

    def test_the_arm_specs_agree_with_their_commands(self):
        for os_name, arms in compare.ARMS.items():
            for arm, spec in arms.items():
                with self.subTest(arm=f"{os_name}-{arm}"):
                    parsed = compare.parse_command(" ".join(spec["command"]))
                    self.assertEqual((parsed["runner"], parsed["before"], parsed["verbose"], parsed["extra"]),
                                     (spec["runner"], [], True, []))
                    for field in ("jobs", "level", "pooling"):
                        self.assertEqual(parsed.get(field), spec.get(field))

    def test_every_upload_refuses_to_overwrite_and_every_recorder_writes_the_attempt(self):
        steps = self.steps()
        uploads = [step for step in steps if "uses: actions/upload-artifact@" in step]
        self.assertEqual(len(uploads), 6)
        for step in uploads:
            with self.subTest(step=step.split("\n", 1)[0]):
                self.assertRegex(step, r"\n +overwrite: false\n")
        self.assertNotIn("overwrite: true", WORKFLOW.read_text(encoding="utf-8"))
        recorders = [step for step in steps if step.startswith("Record the")]
        self.assertEqual(len(recorders), 4)
        for step in recorders:
            with self.subTest(step=step.split("\n", 1)[0]):
                self.assertIn('"git-status.txt"', step)
                self.assertIn('"runtime.json"', step)
                self.assertIn('"run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "")', step)


if __name__ == "__main__":
    unittest.main()
