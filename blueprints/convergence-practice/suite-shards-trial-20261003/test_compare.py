"""Tests of the suite-shards trial's oracle, generator, inventory gate, recorder and workflows (stdlib only).

  python3 -m unittest discover -s blueprints/convergence-practice/suite-shards-trial-20261003 -p "test_*.py" -v

The run directories are built in temporary directories from fixtures/ (real local runs of a fixture suite and of
the controls, made by make_fixtures.py) with synthetic meta, runtime, timing and checkout files, in the layout the
compare job downloads: one directory arm-<run name> per arm artifact and the directory controls for the control
artifact. blueprints/ is not a package, so the repository's own suite never collects this file; the trial's compare
jobs run it before compare.py, fail-closed.
"""

from __future__ import annotations

import collections
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import compare  # noqa: E402
import inventory  # noqa: E402
import logparse  # noqa: E402
import make_fixtures  # noqa: E402
import make_shards  # noqa: E402

ROOT = HERE.parents[2]
FIXTURES = HERE / "fixtures"
INDEX = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))
FIXTURE_WEIGHTS = FIXTURES / "weights-fixture.json"
WORKFLOWS = {"ubuntu-24.04": ROOT / ".github/workflows/suite-shards-trial-linux.yml",
             "macos-15": ROOT / ".github/workflows/suite-shards-trial-macos.yml"}
DECISION_RECORD = ROOT / "docs/decisions/2026-10-03-suite-shards-trial.md"
OS = "ubuntu-24.04"
SHA = "0123456789abcdef0123456789abcdef01234567"
PYTHON = json.loads((FIXTURES / "controls/foreground.probe.json").read_text(encoding="utf-8"))["python_version"]
NEEDS = {"inventory": {"result": "success", "outputs": {}}, "serial": {"result": "failure", "outputs": {}},
         "shards": {"result": "failure", "outputs": {}}, "controls": {"result": "failure", "outputs": {}},
         "controls-check": {"result": "success", "outputs": {}}}
RUN_EXITS = {(item["arm"], item.get("list"), item.get("repeat")): item["exit_code"] for item in INDEX["runs"]}
CONTROL_EXITS = {item["module"]: item["exit_code"] for item in INDEX["controls"]}
STARTED = {"start": {"outcome": "success", "conclusion": "success"}}
CONTROL_STEPS = {compare.FOREGROUND_STEP: {"outcome": "success", "conclusion": "success"},
                 **{spec["step"]: {"outcome": spec["outcome"], "conclusion": spec["outcome"]}
                    for spec in compare.CONTROL_SHARDS}}
SECOND = 10 ** 9


def fixture(relative: str) -> str:
    return (FIXTURES / relative).read_text(encoding="utf-8")


def nanoseconds(seconds) -> int:
    value = Fraction(str(seconds)) * 10 ** 9
    assert value.denominator == 1
    return int(value)


class Tree:
    """A results tree (the compare job's artifact layout) and an inventory directory, built from the fixtures."""

    def __init__(self, root: Path):
        self.results = root / "results"
        self.results.mkdir()
        self.inventory = root / "inventory"
        shutil.copytree(FIXTURES / "inventory", self.inventory)

    def run_dir(self, name: str) -> Path:
        """The run directory <name> inside its arm artifact's directory arm-<name>."""
        return self.results / f"{compare.ARM_ARTIFACT_PREFIX}{name}" / name

    @property
    def control_artifact(self) -> Path:
        return self.results / compare.CONTROL_ARTIFACT

    @property
    def control_dir(self) -> Path:
        return self.control_artifact / f"{OS}-controls"

    def common(self, directory: Path, arm: str, repeat: int, seconds, job_status="failure", steps=None):
        directory.mkdir(parents=True)
        (directory / "meta.json").write_text(json.dumps({
            "os": OS, "arm": arm, "repeat": repeat, "checkout_sha": SHA, "python_version": PYTHON,
            "platform": "fixture", "runner_image": "fixture", "job_status": job_status,
            "steps": STARTED if steps is None else steps}))
        (directory / "runtime.json").write_text(json.dumps({"run_attempt": "1"}))
        if seconds is not None:
            ns = nanoseconds(seconds)
            (directory / "timing.json").write_text(json.dumps({"clock": "fixture", "step_ns": ns, "wall_ns": ns,
                                                                "problems": []}))
        (directory / "git-status.txt").write_text("")

    def serial(self, repeat: int, seconds=100, log: str | None = None):
        directory = self.run_dir(f"{OS}-S-r{repeat}")
        self.common(directory, "S", repeat, seconds)
        (directory / "log.txt").write_text(log if log is not None else fixture(f"runs/S-r{repeat}.log"))
        (directory / "exit-code.txt").write_text(f"{RUN_EXITS[('S', None, repeat)]}\n")
        (directory / "command.txt").write_text("python3 -m unittest -v\n")
        return directory

    def sharded(self, arm: str, repeat: int, seconds=40):
        directory = self.run_dir(f"{OS}-{arm}-r{repeat}")
        self.common(directory, arm, repeat, seconds)
        probe = fixture("controls/foreground.probe.json")
        source = self.inventory / "shards" / arm
        labels = [path.stem for path in sorted(source.glob("shard-*.txt"))]
        shutil.copy(source / "tail.txt", directory / "tail.txt")
        if (source / "tail.txt").read_text():
            labels.append("tail")
        for label in labels:
            listed = (source / f"{label}.txt").read_text()
            if label != "tail":
                shutil.copy(source / f"{label}.txt", directory / f"{label}.txt")
            (directory / f"{label}.log").write_text(fixture(f"runs/{arm}-{label}.log"))
            (directory / f"{label}.exit").write_text(f"{RUN_EXITS[(arm, label, None)]}\n")
            (directory / f"{label}.command").write_text("python3 -m unittest -v " + " ".join(listed.split()) + "\n")
            (directory / f"{label}.probe.json").write_text(probe)
        return directory

    def controls(self):
        directory = self.control_dir
        self.common(directory, "controls", 1, None, steps=CONTROL_STEPS)
        shutil.copy(FIXTURES / "controls/foreground.probe.json", directory / "foreground.probe.json")
        shutil.copy(FIXTURES / "controls/heartbeat.json", directory / "heartbeat.json")
        for index, spec in enumerate(compare.CONTROL_SHARDS):
            label = f"shard-{index}"
            (directory / f"{label}.txt").write_text(spec["module"] + "\n")
            (directory / f"{label}.command").write_text(f"python3 -m unittest -v {spec['module']}\n")
            shutil.copy(FIXTURES / f"controls/{label}.log", directory / f"{label}.log")
            shutil.copy(FIXTURES / f"controls/{label}.probe.json", directory / f"{label}.probe.json")
            code = CONTROL_EXITS[spec["module"]]
            if code is not None:
                (directory / f"{label}.exit").write_text(f"{code}\n")
        return directory

    def full(self, s=(100, 100, 100), g=(40, 40, 40), gt=(45, 45, 45)):
        for repeat, seconds in enumerate(s, 1):
            self.serial(repeat, seconds)
        arms = list(make_shards.ARMS[OS])
        for repeat, seconds in enumerate(g, 1):
            self.sharded(arms[0], repeat, seconds)
        for repeat, seconds in enumerate(gt, 1):
            self.sharded(arms[1], repeat, seconds)
        self.controls()
        return self

    def result(self, needs=NEEDS, **kwargs):
        kwargs.setdefault("compare_attempt", "1")
        return compare.build_result(self.results, self.inventory, SHA, OS, needs, weights=FIXTURE_WEIGHTS, **kwargs)


def rewrite_json(path: Path, **fields):
    data = json.loads(path.read_text())
    data.update(fields)
    path.write_text(json.dumps(data))


def setup_failure(directory: Path, steps=None):
    """What the finish step leaves when a step before the clock failed: meta.json (the clock step skipped), an
    untimed timing.json and git-status.txt, and nothing else (record.py finish, `if: always()`)."""
    for path in list(directory.iterdir()):
        if path.name not in ("meta.json", "git-status.txt"):
            path.unlink()
    rewrite_json(directory / "meta.json",
                 steps={"start": {"outcome": "skipped", "conclusion": "skipped"}} if steps is None else steps)
    (directory / "timing.json").write_text(json.dumps({
        "clock": "fixture", "step_ns": None, "wall_ns": None,
        "problems": ["timing-start.json is missing or unreadable: the test phase was never timed"]}))


def lose(directory: Path, label: str):
    """What a control step whose script never ran (a runner fault) leaves: its list, which an earlier step wrote, and
    no probe, command, log or exit status; for the hang control also no heartbeat (record.py finish then writes none)."""
    for suffix in (".probe.json", ".command", ".log", ".exit"):
        (directory / f"{label}{suffix}").unlink(missing_ok=True)
    if label == "shard-3":
        rewrite_json(directory / "heartbeat.json", beats=[], beats_after_recheck=0)


class TreeCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = Tree(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def verdict(self, result=None):
        return (result or self.tree.result())["verdicts"][OS]

    def run_entry(self, result, name):
        return next(item for item in result["runs"] if item["name"] == name)

    def edit(self, path: Path, old: str, new: str, count: int = 1):
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, count))

    def assertIncomplete(self, verdict, fragment: str):
        self.assertEqual(verdict["outcome"], "incomplete", verdict["reasons"])
        self.assertIsNone(verdict["selected_arm"])
        self.assertTrue(any(fragment in reason for reason in verdict["reasons"]), verdict["reasons"])


# --------------------------------------------------------------------------- fixtures and provenance


class FixtureTests(unittest.TestCase):
    def test_index_lists_every_fixture_file_with_its_hash(self):
        listed = {item["file"]: item["sha256"] for item in INDEX["files"]}
        present = {path.relative_to(FIXTURES).as_posix() for path in FIXTURES.rglob("*") if path.is_file()} - {"index.json"}
        self.assertEqual(sorted(present), sorted(listed))
        for name, digest in listed.items():
            self.assertEqual(hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest(), digest, name)

    def test_fixtures_carry_no_host_path(self):
        for path in FIXTURES.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(make_fixtures.PRIVATE.search(text), path.name)
                self.assertNotIn("/" + "tmp" + "/", text, path.name)  # assembled, so this file holds no such path

    def test_every_real_log_parses_without_anomalies(self):
        for item in INDEX["runs"] + [entry for entry in INDEX["controls"] if entry["module"] in ("test_ctl_pass", "test_ctl_fail")]:
            parsed = logparse.parse_log(fixture(item["file"]))
            self.assertEqual(parsed.anomalies, [], item["file"])
            self.assertEqual(parsed.mode, "serial", item["file"])
            self.assertEqual(parsed.status_word == "OK", item["exit_code"] == 0, item["file"])

    def test_the_sharded_runs_hold_the_serial_records(self):
        serial = compare.groups([compare.Log("S", [], parsed=logparse.parse_log(fixture("runs/S-r1.log")))])
        for arm in make_shards.ARMS[OS]:
            logs = [compare.Log(item["list"], [], parsed=logparse.parse_log(fixture(item["file"])))
                    for item in INDEX["runs"] if item["arm"] == arm]
            self.assertEqual(compare.groups(logs), serial, arm)

    def test_the_control_fixtures_ran_with_the_hosted_limits(self):
        self.assertEqual((INDEX["hang_limit_seconds"], INDEX["control_limit_seconds"]), (60, 300))
        self.assertEqual([item["exit_code"] for item in INDEX["controls"]], [0, 1, 3, None])

    def test_logparse_is_the_recorded_copy(self):
        text = (HERE / "logparse.py").read_text(encoding="utf-8")
        digests = re.findall(r"(?m)^    block [12] \(lines [0-9-]+\): +([0-9a-f]{64})$", text)
        self.assertEqual(len(digests), 2, "the header names the sha256 of both copied blocks")
        body = text.split("import re\n\n", 1)[1]
        lines = body.split("\n")
        first = "\n".join(lines[:34]) + "\n"
        self.assertEqual(lines[34:36], ["", ""])
        second = "\n".join(lines[36:])
        self.assertEqual(hashlib.sha256(first.encode()).hexdigest(), digests[0])
        self.assertEqual(hashlib.sha256(second.encode()).hexdigest(), digests[1])


# --------------------------------------------------------------------------- make_shards.py


class MakeShardsTests(unittest.TestCase):
    MODULES = [f"tests.test_{name}" for name in ("a", "b", "c", "d", "e", "f")]

    def test_longest_first_to_the_least_loaded_shard(self):
        weights = {"tests.test_a": 5000, "tests.test_b": 4000, "tests.test_c": 3000, "tests.test_d": 3000,
                   "tests.test_e": 2000, "tests.test_f": 1000}
        plan = make_shards.assign(self.MODULES, weights, 2, (), 0)
        # a(5)->0; b(4)->1; c(3)->1 (4<5); d(3)->0 (5<7); e(2)->0? loads 8,7 -> 1; f(1) -> 0 (8<9)
        self.assertEqual(plan["shards"], [["tests.test_a", "tests.test_d", "tests.test_f"],
                                          ["tests.test_b", "tests.test_c", "tests.test_e"]])
        self.assertEqual(plan["loads_ms"], [9000, 9000])

    def test_ties_go_by_name_then_to_the_lowest_shard(self):
        weights = {module: 1000 for module in self.MODULES}
        plan = make_shards.assign(self.MODULES, weights, 3, (), 0)
        self.assertEqual(plan["shards"], [["tests.test_a", "tests.test_d"], ["tests.test_b", "tests.test_e"],
                                          ["tests.test_c", "tests.test_f"]])

    def test_a_module_without_a_weight_takes_the_default_and_is_listed(self):
        weights = {module: 1000 for module in self.MODULES[:-1]}
        plan = make_shards.assign(self.MODULES, weights, 2, (), make_shards.default_weight(weights))
        self.assertEqual(plan["defaulted"], ["tests.test_f"])
        self.assertIn("tests.test_f", [module for members in plan["shards"] for module in members])
        self.assertEqual(make_shards.coverage_problems(self.MODULES, plan), [])

    def test_the_tail_leaves_the_shards_and_must_exist(self):
        plan = make_shards.assign(self.MODULES, {}, 2, ("tests.test_c",), 1000)
        self.assertEqual(plan["tail"], ["tests.test_c"])
        self.assertNotIn("tests.test_c", [module for members in plan["shards"] for module in members])
        with self.assertRaises(make_shards.ShardError):
            make_shards.assign(self.MODULES, {}, 2, ("tests.test_zz",), 1000)

    def test_an_empty_shard_is_refused(self):
        with self.assertRaises(make_shards.ShardError):
            make_shards.assign(self.MODULES[:2], {}, 3, (), 1000)

    def test_coverage_problems_name_duplicates_and_gaps(self):
        problems = make_shards.coverage_problems(["tests.test_a", "tests.test_b"],
                                                 {"shards": [["tests.test_a"], ["tests.test_a"]], "tail": []})
        self.assertTrue(any("twice" in problem for problem in problems))
        self.assertTrue(any("tests.test_b is in no list" in problem for problem in problems))

    def test_bad_weights_files_are_refused(self):
        cases = {"negative": {"tests.test_a": -1}, "sub-millisecond": {"tests.test_a": 0.0005},
                 "text": {"tests.test_a": "1"}, "bad name": {"test_a": 1}, "boolean": {"tests.test_a": True}}
        with tempfile.TemporaryDirectory() as tmp:
            for label, weights in cases.items():
                path = Path(tmp) / "w.json"
                path.write_text(json.dumps({"schema": make_shards.WEIGHTS_SCHEMA, "weights": weights}))
                with self.subTest(label), self.assertRaises(make_shards.ShardError):
                    make_shards.load_weights(path)
            path.write_text(json.dumps({"schema": "other", "weights": {"tests.test_a": 1}}))
            with self.assertRaises(make_shards.ShardError):
                make_shards.load_weights(path)

    def test_written_lists_read_back_exactly(self):
        modules = self.MODULES + ["tests.test_secret_path_guard"]
        plan = make_shards.plan_for(OS, modules, {module: 1000 + index for index, module in enumerate(modules)})
        with tempfile.TemporaryDirectory() as tmp:
            make_shards.write_plan(plan, Path(tmp))
            for arm, arm_plan in plan.items():
                shards = [make_shards.read_list(Path(tmp) / arm / f"shard-{index}.txt")
                          for index in range(len(arm_plan["shards"]))]
                self.assertEqual(shards, arm_plan["shards"])
                self.assertEqual(make_shards.read_list(Path(tmp) / arm / "tail.txt"), arm_plan["tail"])

    def test_the_preregistered_arms(self):
        self.assertEqual({os_name: {arm: (spec["shards"], spec["tail"]) for arm, spec in arms.items()}
                          for os_name, arms in make_shards.ARMS.items()},
                         {"ubuntu-24.04": {"G4": (4, ()), "G4T": (4, ("tests.test_secret_path_guard",))},
                          "macos-15": {"G3": (3, ()), "G3T": (3, ("tests.test_secret_path_guard",))}})

    def test_the_frozen_weights_file(self):
        weights = make_shards.load_weights(HERE / "weights.json")
        self.assertEqual(len(weights), 233)
        self.assertEqual(sum(weights.values()), 1269971)
        self.assertEqual(make_shards.default_weight(weights), 5450)
        self.assertEqual(max(weights, key=weights.get), "tests.test_token_e2e_grader")


# --------------------------------------------------------------------------- inventory.py


class InventoryTests(unittest.TestCase):
    def build(self, extra: dict | None = None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        suite = Path(tmp.name) / "suite"
        for name, text in {**make_fixtures.SUITE, **(extra or {})}.items():
            (suite / name).parent.mkdir(parents=True, exist_ok=True)
            (suite / name).write_text(text)
        out = Path(tmp.name) / "inventory"
        done = subprocess.run([sys.executable, str(HERE / "inventory.py"), "--os", OS, "--root", str(suite),
                               "--weights", str(FIXTURE_WEIGHTS), "--out", str(out)],
                              capture_output=True, text=True, check=False)
        return done, out

    def test_the_fixture_suite_passes_and_reproduces_the_committed_inventory(self):
        done, out = self.build()
        self.assertEqual(done.returncode, 0, done.stderr)
        for name in ("inventory.txt", "module_ids.json"):
            self.assertEqual((out / name).read_text(), fixture(f"inventory/{name}"), name)
        for path in (FIXTURES / "inventory" / "shards").rglob("*.txt"):
            self.assertEqual((out / "shards" / path.relative_to(FIXTURES / "inventory" / "shards")).read_text(),
                             path.read_text(), path.name)
        report = json.loads((out / "report.json").read_text())
        self.assertTrue(report["ok"] and report["parity"])

    def test_an_import_failure_fails_the_gate(self):
        done, out = self.build({"tests/test_broken.py": "import a_module_that_does_not_exist\n"})
        self.assertEqual(done.returncode, 1)
        self.assertFalse(json.loads((out / "report.json").read_text())["ok"])
        self.assertIn("loader", done.stderr)

    def test_an_id_loaded_twice_fails_the_gate(self):
        twin = make_fixtures.SUITE["tests/test_delta.py"].replace("class DeltaTests", "class Unused")
        done, _ = self.build({"tests/test_zeta.py": twin})
        self.assertEqual(done.returncode, 1)
        self.assertIn("loaded twice", done.stderr)

    def test_a_discovered_file_outside_the_shard_pattern_fails_the_gate(self):
        done, _ = self.build({"tests/testextra.py": "import unittest\n\n\nclass Extra(unittest.TestCase):\n"
                                                    "    def test_x(self):\n        pass\n"})
        self.assertEqual(done.returncode, 1)
        self.assertIn("loaded by no test file", done.stderr)

    def test_an_exception_at_import_fails_the_gate(self):
        done, out = self.build({"tests/test_raises.py": "raise RuntimeError('planted')\n"})
        self.assertEqual(done.returncode, 1)
        report = json.loads((out / "report.json").read_text())
        self.assertTrue(report["problems"], "a finding")
        self.assertEqual(report["execution_problems"], [])

    @unittest.skipUnless(hasattr(signal, "SIGKILL"), "POSIX signals")
    def test_a_child_stopped_from_outside_is_an_execution_problem_not_a_finding(self):
        # F12: the discovery child ends by SIGTERM, as a runner or the out-of-memory killer (SIGKILL) would end it.
        # The gate still fails, but report.json records no finding, so compare.py makes the run incomplete.
        stopped = "import os\nimport signal\n\nos.kill(os.getpid(), signal.SIGTERM)\n"
        done, out = self.build({"tests/test_stopped.py": stopped})
        self.assertEqual(done.returncode, 1, done.stderr)
        report = json.loads((out / "report.json").read_text())
        self.assertFalse(report["ok"])
        self.assertIsNone(report["parity"])
        self.assertEqual(report["problems"], [])
        self.assertEqual(len(report["execution_problems"]), 1, report["execution_problems"])
        self.assertIn("the discover child interpreter was stopped by SIGTERM from outside",
                      report["execution_problems"][0])

    @unittest.skipUnless(hasattr(signal, "SIGKILL"), "POSIX signals")
    def test_only_a_signal_from_outside_is_an_execution_problem(self):
        # F12: a child that ends itself by a fault (SIGSEGV, SIGABRT), exits non-zero or prints no JSON is a finding.
        self.assertIsInstance(inventory.child_failure("discover", -signal.SIGKILL, ""), inventory.ChildStopped)
        self.assertIsInstance(inventory.child_failure("by-name", -signal.SIGINT, ""), inventory.ChildStopped)
        for code in (-signal.SIGSEGV, -signal.SIGABRT, 1, 2):
            with self.subTest(code=code):
                failure = inventory.child_failure("discover", code, "")
                self.assertIsInstance(failure, RuntimeError)
                self.assertNotIsInstance(failure, inventory.ChildStopped)


# --------------------------------------------------------------------------- record.py


class RecordTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("GIT_") and key != "STEPS_JSON"}
        for args in (["init", "-q"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty",
                                      "-m", "t"]):
            subprocess.run(["git", *args], cwd=self.repo, env=environment, check=True)
        self.out = self.tmp / "out"
        self.env = dict(environment, GITHUB_RUN_ATTEMPT="1", JOB_STATUS="failure")

    def record(self, *args, **popen):
        return subprocess.run([sys.executable, str(HERE / "record.py"), *args], cwd=self.repo, env=self.env,
                              capture_output=True, text=True, check=True, **popen)

    def test_a_timed_run_directory(self):
        self.env["STEPS_JSON"] = json.dumps({"start": {"outputs": {"note": "dropped"}, "outcome": "success",
                                                       "conclusion": "success"}})
        self.record("runtime", str(self.out))
        self.record("start", str(self.out))
        self.record("probe", str(self.out), "shard-0")
        self.record("finish", str(self.out), "--os", OS, "--arm", "G4", "--repeat", "2")
        timing = json.loads((self.out / "timing.json").read_text())
        meta = json.loads((self.out / "meta.json").read_text())
        self.assertEqual(compare.timing_problems(timing), [])
        self.assertEqual(json.loads((self.out / "runtime.json").read_text())["run_attempt"], "1")
        self.assertEqual((meta["os"], meta["arm"], meta["repeat"], meta["job_status"]), (OS, "G4", 2, "failure"))
        self.assertEqual(meta["steps"], STARTED, "outcome and conclusion of each step with an id, outputs dropped")
        self.assertEqual(compare.unstarted_reasons(meta, compare.START_STEP), [])
        self.assertEqual(len(meta["checkout_sha"]), 40)
        self.assertEqual((self.out / "git-status.txt").read_text(), "")
        probe = json.loads((self.out / "shard-0.probe.json").read_text())
        self.assertEqual(set(probe["env_present"]), {
            compare.CONTROL_ENV_NAME, "CHILD_USAGE_SHELL_PARSER", "LANDSCAPE_SWEEP_SKILLS_YAML", "PROMOTION_GATE_PYTHON",
            "REQUIRE_PROMOTION_GATE_VENV", "GITHUB_ACTIONS", "CI"})
        self.assertTrue(all(isinstance(value, bool) for value in probe["env_present"].values()), "names only, no values")
        self.assertTrue(timing["start_monotonic_ns"] < probe["monotonic_ns"] < timing["end_monotonic_ns"])
        self.assertIsInstance(probe["wall_ns"], int)

    def test_finish_without_start_is_untimed_and_a_dirty_checkout_is_recorded(self):
        (self.repo / "untracked.txt").write_text("x")
        self.record("finish", str(self.out), "--os", OS, "--arm", "S", "--repeat", "1")
        timing = json.loads((self.out / "timing.json").read_text())
        meta = json.loads((self.out / "meta.json").read_text())
        self.assertIsNone(timing["step_ns"])
        self.assertTrue(compare.timing_problems(timing))
        self.assertIsNone(meta["steps"], "no STEPS_JSON: the step outcomes are unrecorded")
        self.assertTrue(compare.unstarted_reasons(meta, compare.START_STEP))
        self.assertEqual((self.out / "git-status.txt").read_text(), "?? untracked.txt\n")

    def test_invalid_step_outcomes_are_unrecorded(self):
        self.env["STEPS_JSON"] = "not json"
        self.record("finish", str(self.out), "--os", OS, "--arm", "S", "--repeat", "1")
        self.assertIsNone(json.loads((self.out / "meta.json").read_text())["steps"])

    def test_finish_records_the_hang_controls_heartbeat(self):
        beats = self.tmp / "test_ctl_hang.heartbeat"
        beats.write_text("100 7\n200 7\n300 1\n40")  # the last line is still being written
        self.record("finish", str(self.out), "--os", OS, "--arm", "controls", "--repeat", "1", "--heartbeat", str(beats))
        record = json.loads((self.out / "heartbeat.json").read_text())
        self.assertEqual(record["beats"], [[100, 7], [200, 7], [300, 1]])
        self.assertEqual((record["file"], record["beats_after_recheck"]), ("test_ctl_hang.heartbeat", 3))
        self.assertEqual(record["end_monotonic_ns"], json.loads((self.out / "timing.json").read_text())["end_monotonic_ns"])

    @unittest.skipUnless(hasattr(signal, "SIGQUIT"), "POSIX signals")
    def test_a_probe_sees_ignored_signals(self):
        def ignore():
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            signal.signal(signal.SIGQUIT, signal.SIG_IGN)
        self.record("probe", str(self.out), "ignored", preexec_fn=ignore)
        self.record("probe", str(self.out), "default", preexec_fn=lambda: (
            signal.signal(signal.SIGINT, signal.SIG_DFL), signal.signal(signal.SIGQUIT, signal.SIG_DFL)))
        ignored = json.loads((self.out / "ignored.probe.json").read_text())["signals"]
        default = json.loads((self.out / "default.probe.json").read_text())["signals"]
        self.assertTrue(ignored["SIGINT"]["ignored"] and ignored["SIGQUIT"]["ignored"])
        self.assertFalse(default["SIGINT"]["ignored"] or default["SIGQUIT"]["ignored"])
        self.assertIn("SIG_DFL", default["SIGQUIT"]["handler"])


# --------------------------------------------------------------------------- compare.py: the verdict


class VerdictTests(TreeCase):
    def test_equal_and_fast_shards_adopt_the_faster_arm(self):
        result = self.tree.full(s=(100, 110, 90), g=(50, 40, 45), gt=(55, 45, 50)).result()
        verdict = self.verdict(result)
        self.assertEqual((verdict["outcome"], verdict["selected_arm"]), ("adopt", "G4"), verdict["reasons"])
        self.assertTrue(all(run["eligible"] for run in result["runs"]), [r["reasons"] for r in result["runs"]])
        self.assertTrue(result["controls"][OS]["passed"], result["controls"][OS]["problems"])
        self.assertEqual(verdict["arms"]["G4"]["median_vs_s_median_exact"], "9/20")
        self.assertEqual(result["inputs"]["compare_run_attempt"], "1")
        self.assertEqual(result["inputs"]["ignored_entries"], [])

    def test_the_tail_arm_wins_when_its_median_is_smaller(self):
        verdict = self.verdict(self.tree.full(g=(50, 50, 50), gt=(45, 45, 45)).result())
        self.assertEqual(verdict["selected_arm"], "G4T")

    def test_a_tie_goes_to_the_arm_without_a_tail(self):
        verdict = self.verdict(self.tree.full(g=(40, 50, 45), gt=(45, 40, 50)).result())
        self.assertEqual(verdict["selected_arm"], "G4")

    def test_the_speed_rule_is_exact_at_both_bounds(self):
        # S median 100, fastest S 100: the median may be 60 and the slowest run 75, not a nanosecond more.
        cases = {((60, 60, 75), "adopt"), ((60, 60, Fraction(75) + Fraction(1, 10 ** 9)), "reject"),
                 ((Fraction(60) + Fraction(1, 10 ** 9),) * 2 + (61,), "reject")}
        for g, outcome in cases:
            with self.subTest(g=g), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(Path(tmp)).full(s=(100, 100, 100), g=g, gt=(99, 99, 99))
                verdict = tree.result()["verdicts"][OS]
                self.assertEqual(verdict["outcome"], outcome, verdict["reasons"])

    def test_no_fall_through_to_a_slower_arm(self):
        # G4 has the smaller median but one slow run; G4T would pass both bounds, yet the rule rejects.
        verdict = self.verdict(self.tree.full(s=(100, 100, 100), g=(40, 40, 80), gt=(50, 50, 50)).result())
        self.assertEqual((verdict["outcome"], verdict["fastest_eligible_arm"]), ("reject", "G4"))

    def test_a_changed_outcome_makes_the_run_and_its_arm_ineligible(self):
        self.tree.full()
        shard = self.tree.run_dir(f"{OS}-G4-r2") / "shard-0.log"
        self.edit(shard, "test_passes (tests.test_alpha.AlphaTests.test_passes) ... ok",
                  "test_passes (tests.test_alpha.AlphaTests.test_passes) ... skipped 'mutated'")
        self.edit(shard, "OK (skipped=1, expected failures=1)", "OK (skipped=2, expected failures=1)")
        result = self.tree.result()
        entry = self.run_entry(result, f"{OS}-G4-r2")
        self.assertFalse(entry["eligible"])
        self.assertEqual(entry["mismatch_total"], 1)
        self.assertEqual(entry["mismatches"][0]["id"], "tests.test_alpha.AlphaTests.test_passes")
        verdict = self.verdict(result)
        self.assertFalse(verdict["arms"]["G4"]["eligible"])
        self.assertEqual(verdict["selected_arm"], "G4T")

    def test_ids_that_differ_among_the_serial_runs_are_flaky_and_excluded(self):
        self.tree.full()
        serial = self.tree.run_dir(f"{OS}-S-r3") / "log.txt"
        self.edit(serial, "test_passes (tests.test_alpha.AlphaTests.test_passes) ... ok",
                  "test_passes (tests.test_alpha.AlphaTests.test_passes) ... skipped 'flaky'")
        self.edit(serial, "skipped=1, expected", "skipped=2, expected")
        verdict = self.verdict()
        self.assertEqual(verdict["baseline"]["flaky_ids"], ["tests.test_alpha.AlphaTests.test_passes"])
        self.assertEqual(verdict["outcome"], "adopt")

    def test_a_module_run_twice_or_never_is_ineligible(self):
        self.tree.full()
        run = self.tree.run_dir(f"{OS}-G4-r1")
        shutil.copy(run / "shard-0.log", run / "shard-2.log")  # alpha twice, epsilon and the tail module never
        entry = self.run_entry(self.tree.result(), f"{OS}-G4-r1")
        self.assertFalse(entry["eligible"])
        self.assertEqual(entry["repeated_total"], 4)
        self.assertEqual(entry["missing_total"], 3)

    def test_the_command_must_be_the_shards_list(self):
        self.tree.full()
        command = self.tree.run_dir(f"{OS}-G4T-r1") / "shard-3.command"
        command.write_text("python3 -m unittest -v tests.test_epsilon tests.test_delta\n")
        entry = self.run_entry(self.tree.result(), f"{OS}-G4T-r1")
        self.assertTrue(any("command" in reason for reason in entry["reasons"]), entry["reasons"])

    def test_the_serial_command_must_be_exact(self):
        self.tree.full()
        (self.tree.run_dir(f"{OS}-S-r1") / "command.txt").write_text("python3 -X dev -m unittest -v\n")
        verdict = self.verdict()
        self.assertEqual(verdict["outcome"], "no verdict")

    def test_the_run_lists_must_be_the_inventory_lists(self):
        self.tree.full()
        (self.tree.run_dir(f"{OS}-G4-r3") / "shard-0.txt").write_text("tests.test_beta\n")
        entry = self.run_entry(self.tree.result(), f"{OS}-G4-r3")
        self.assertIn("the run's shard lists are not the inventory artifact's lists for this arm", entry["reasons"])

    def test_an_exit_status_that_disagrees_with_the_status_line(self):
        self.tree.full()
        (self.tree.run_dir(f"{OS}-G4-r1") / "shard-0.exit").write_text("1\n")
        entry = self.run_entry(self.tree.result(), f"{OS}-G4-r1")
        self.assertTrue(any("disagrees with the status line" in reason for reason in entry["reasons"]))

    def test_a_missing_shard_exit_status_is_ineligible(self):
        self.tree.full()
        (self.tree.run_dir(f"{OS}-G4-r1") / "shard-1.exit").unlink()
        self.assertFalse(self.run_entry(self.tree.result(), f"{OS}-G4-r1")["eligible"])

    def test_a_started_shard_that_never_reached_its_command_is_ineligible_not_incomplete(self):
        # The test phase started (the clock step succeeded): a shard step that then fails before its command is a
        # property of the sharded arm, so its run is ineligible and the other arm may still be selected. F11: the
        # passed-over arm, ineligible only through that step, is flagged for the outcome record.
        self.tree.full()
        run = self.tree.run_dir(f"{OS}-G4-r1")
        for name in ("shard-2.command", "shard-2.log", "shard-2.exit", "shard-2.probe.json"):
            (run / name).unlink()
        result = self.tree.result()
        self.assertFalse(self.run_entry(result, f"{OS}-G4-r1")["eligible"])
        self.assertTrue(self.run_entry(result, f"{OS}-G4-r1")["test_phase_started"])
        verdict = self.verdict(result)
        self.assertEqual((verdict["outcome"], verdict["selected_arm"]), ("adopt", "G4T"))
        self.assertTrue(verdict["arms"]["G4"]["ineligible_only_through_unfinished_steps"])
        self.assertEqual(verdict["arms"]["G4"]["unfinished_steps"], {f"{OS}-G4-r1": ["shard-2"]})
        self.assertEqual(len(verdict["flags"]), 1, verdict["flags"])
        self.assertIn("arm G4 was ineligible only because steps never wrote an exit status (ubuntu-24.04-G4-r1: "
                      "shard-2)", verdict["flags"][0])
        self.assertIn("FLAG ubuntu-24.04: arm G4", compare.summary_markdown(result))

    def test_a_step_stopped_before_its_exit_status_is_flagged_too(self):
        # F11: a shard step stopped after its first test line, without an exit status (as a lost step would be).
        self.tree.full()
        run = self.tree.run_dir(f"{OS}-G4-r2")
        (run / "shard-2.log").write_text((run / "shard-2.log").read_text().split("\n", 1)[0] + "\n")
        (run / "shard-2.exit").unlink()
        verdict = self.verdict()
        self.assertEqual((verdict["outcome"], verdict["selected_arm"]), ("adopt", "G4T"))
        self.assertEqual(verdict["arms"]["G4"]["unfinished_steps"], {f"{OS}-G4-r2": ["shard-2"]})
        self.assertEqual(len(verdict["flags"]), 1, verdict["flags"])

    def test_a_passed_over_arm_with_another_problem_is_not_flagged(self):
        # F11: besides the unfinished step, a finished shard of the same run changed an outcome, which is the arm's
        # own failure: no flag.
        self.tree.full()
        run = self.tree.run_dir(f"{OS}-G4-r1")
        for name in ("shard-2.command", "shard-2.log", "shard-2.exit", "shard-2.probe.json"):
            (run / name).unlink()
        self.edit(run / "shard-0.log", "test_passes (tests.test_alpha.AlphaTests.test_passes) ... ok",
                  "test_passes (tests.test_alpha.AlphaTests.test_passes) ... skipped 'mutated'")
        self.edit(run / "shard-0.log", "OK (skipped=1, expected failures=1)", "OK (skipped=2, expected failures=1)")
        verdict = self.verdict()
        self.assertEqual((verdict["outcome"], verdict["selected_arm"]), ("adopt", "G4T"))
        self.assertFalse(verdict["arms"]["G4"]["ineligible_only_through_unfinished_steps"])
        self.assertEqual(verdict["arms"]["G4"]["unfinished_steps"], {})
        self.assertEqual(verdict["flags"], [])

    def test_a_reject_with_no_eligible_arm_flags_an_arm_lost_to_unfinished_steps(self):
        # F11: G4 lost only a shard step's exit status, G4T changed an outcome: no sharded arm is eligible, reject, and
        # the flag names G4 only.
        self.tree.full()
        (self.tree.run_dir(f"{OS}-G4-r3") / "shard-1.exit").unlink()
        shard = self.tree.run_dir(f"{OS}-G4T-r1") / "shard-0.log"
        self.edit(shard, "test_passes (tests.test_alpha.AlphaTests.test_passes) ... ok",
                  "test_passes (tests.test_alpha.AlphaTests.test_passes) ... skipped 'mutated'")
        self.edit(shard, "OK (skipped=1, expected failures=1)", "OK (skipped=2, expected failures=1)")
        verdict = self.verdict()
        self.assertEqual((verdict["outcome"], verdict["reasons"]), ("reject", ["no sharded arm is eligible"]))
        self.assertEqual(len(verdict["flags"]), 1, verdict["flags"])
        self.assertIn("arm G4 was ineligible only because", verdict["flags"][0])
        self.assertIn("no sharded arm eligible", verdict["flags"][0])

    def test_checkout_attempt_and_head_rules(self):
        mutations = {
            "dirty": lambda d: (d / "git-status.txt").write_text("?? stray.txt\n"),
            "no status": lambda d: (d / "git-status.txt").unlink(),
            "status failed": lambda d: (d / "git-status.txt").write_text("git status failed\n"),
            "other head": lambda d: rewrite_json(d / "meta.json", checkout_sha="f" * 40),
            # The job recorded another python than its steps' probes show: the within-job check.
            "other python": lambda d: rewrite_json(d / "meta.json", python_version="3.12.3"),
            "clocks disagree": lambda d: (d / "timing.json").write_text(json.dumps(
                {"step_ns": nanoseconds(40), "wall_ns": nanoseconds(60), "problems": []})),
        }
        for label, mutate in mutations.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(Path(tmp)).full()
                mutate(tree.run_dir(f"{OS}-G4T-r2"))
                result = tree.result()
                self.assertFalse(self.run_entry(result, f"{OS}-G4T-r2")["eligible"], label)
                self.assertFalse(result["verdicts"][OS]["arms"]["G4T"]["eligible"], label)

    def test_a_background_step_on_another_interpreter_is_ineligible(self):
        self.tree.full()
        probe = self.tree.run_dir(f"{OS}-G4-r1") / "shard-2.probe.json"
        data = json.loads(probe.read_text())
        data["python_version"] = "3.9.6"
        probe.write_text(json.dumps(data))
        entry = self.run_entry(self.tree.result(), f"{OS}-G4-r1")
        self.assertTrue(any("ran python '3.9.6'" in reason for reason in entry["reasons"]), entry["reasons"])

    def test_a_unittest_parallel_header_is_ineligible(self):
        self.tree.full()
        log = self.tree.run_dir(f"{OS}-G4-r1") / "shard-0.log"
        log.write_text("Running 1 test suites (4 total tests) across 1 workers\n" + log.read_text())
        self.assertFalse(self.run_entry(self.tree.result(), f"{OS}-G4-r1")["eligible"])

    def test_a_serial_run_must_execute_the_inventory(self):
        self.tree.full()
        (self.tree.run_dir(f"{OS}-S-r2") / "log.txt").write_text(fixture("runs/G4-shard-0.log"))
        result = self.tree.result()
        self.assertFalse(self.run_entry(result, f"{OS}-S-r2")["eligible"])
        self.assertEqual(self.verdict(result)["outcome"], "no verdict")

    def test_serial_runs_on_two_python_versions_are_incomplete_not_no_verdict(self):
        # R4-1: an image rollout during a run changed the interpreter between two S jobs, an environment fault.
        # Previous head: every S run ineligible, so no verdict, final under the deciding-run rule.
        self.tree.full()
        rewrite_json(self.tree.run_dir(f"{OS}-S-r3") / "meta.json", python_version="3.12.3")
        result = self.tree.result()
        self.assertIncomplete(self.verdict(result), f"the arm runs recorded 2 python versions (3.12.3: [{OS}-S-r3] (1); ")
        self.assertIncomplete(self.verdict(result), "the runtime changed during the run (an environment fault)")
        self.assertTrue(self.run_entry(result, f"{OS}-S-r3")["eligible"])

    def test_a_sharded_run_on_another_python_version_than_s_is_incomplete_not_a_handover(self):
        # R4-1: G4 r1's job and all its steps ran another release than every other run (its probes agree with its job,
        # so the within-job check holds). Previous head: G4 r1 ineligible, so G4T decided: adopt G4T.
        self.tree.full()
        run = self.tree.run_dir(f"{OS}-G4-r1")
        rewrite_json(run / "meta.json", python_version="3.12.3")
        for probe in run.glob("*.probe.json"):
            rewrite_json(probe, python_version="3.12.3")
        result = self.tree.result()
        self.assertIncomplete(self.verdict(result), f"the arm runs recorded 2 python versions (3.12.3: [{OS}-G4-r1] (1)")
        self.assertTrue(self.run_entry(result, f"{OS}-G4-r1")["eligible"], "no longer an ineligibility")

    def test_arm_runs_on_two_machines_are_incomplete(self):
        # R4-1: runtime.json's machine differs between two runs of one OS. Previous head: not compared, adopt.
        for machines, outcome in ((("x86_64", "arm64"), "incomplete"), (("x86_64", "x86_64"), "adopt")):
            with self.subTest(machines), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(Path(tmp)).full()
                rewrite_json(tree.run_dir(f"{OS}-S-r1") / "runtime.json", machine=machines[0])
                rewrite_json(tree.run_dir(f"{OS}-G4T-r2") / "runtime.json", machine=machines[1])
                verdict = tree.result()["verdicts"][OS]
                self.assertEqual(verdict["outcome"], outcome, verdict["reasons"])
                if outcome == "incomplete":
                    self.assertIncomplete(verdict, "the arm runs recorded 2 machines (arm64: [ubuntu-24.04-G4T-r2] (1); "
                                                   "x86_64: [ubuntu-24.04-S-r1] (1))")

    def test_another_runner_image_with_the_same_python_version_is_only_a_flag(self):
        # R4-1: an image rollout that left the interpreter and the machine unchanged is reported, never judged.
        # Previous head: no flag. R5-1 keeps it: no record differs from S here.
        self.tree.full()
        rewrite_json(self.tree.run_dir(f"{OS}-G4T-r3") / "meta.json", runner_image="20260907.0337.1")
        result = self.tree.result()
        verdict = self.verdict(result)
        self.assertEqual((verdict["outcome"], verdict["selected_arm"]), ("adopt", "G4"), verdict["reasons"])
        self.assertTrue(all(run["eligible"] for run in result["runs"]))
        self.assertEqual(verdict["flags"], [f"the arm runs ran on 2 runner images (20260907.0337.1: [{OS}-G4T-r3] (1); "
                                            f"fixture: [{OS}-G4-r1, {OS}-G4-r2, {OS}-G4-r3, {OS}-G4T-r1, {OS}-G4T-r2, "
                                            "...] (8)): the outcome record must address it"])
        self.assertIn("- FLAG ubuntu-24.04: the arm runs ran on 2 runner images", compare.summary_markdown(result))

    def test_a_record_mismatch_beside_another_runner_image_is_incomplete_not_a_rule_outcome(self):
        # R5-1: an image provides tools and versions that tests gate on, so a record that differs from S while the arm
        # runs ran on two images may come from the image, not from sharding. Previous head: only the image flag, so a
        # mismatch in G4 r2 handed the decision to G4T (adopt G4T), and one in both arms rejected. Kept: on one image
        # the mismatch is the arm's failure. R6-1: a run ineligible only through a step that never wrote its exit status
        # is no exception on two images (the previous head handed the decision to G4T, flagged).
        image, g4, g4t = "20260907.0337.1", f"{OS}-G4-r2", f"{OS}-G4T-r1"
        every_run = [f"{OS}-{arm}-r{repeat}" for arm in compare.arms_of(OS) for repeat in (1, 2, 3)]

        def differ(tree: Tree, name: str):
            shard = tree.run_dir(name) / "shard-0.log"
            self.edit(shard, "test_passes (tests.test_alpha.AlphaTests.test_passes) ... ok",
                      "test_passes (tests.test_alpha.AlphaTests.test_passes) ... skipped 'tool not on PATH'")
            self.edit(shard, "OK (skipped=1, expected failures=1)", "OK (skipped=2, expected failures=1)")

        for label, differing, imaged in (("one arm differs, which must not hand over", [g4], [g4]),
                                         ("both arms differ, which must not reject", [g4, g4t], [g4]),
                                         ("the other image is an S run's", [g4], [f"{OS}-S-r3"])):
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(Path(tmp)).full()
                for name in differing:
                    differ(tree, name)
                for name in imaged:
                    rewrite_json(tree.run_dir(name) / "meta.json", runner_image=image)
                verdict = tree.result()["verdicts"][OS]
                self.assertIncomplete(verdict, f"the records of sharded runs [{', '.join(differing)}] ({len(differing)}) "
                                               "differ from the S baseline while the arm runs ran on 2 runner images "
                                               f"({image}: [{', '.join(imaged)}] (1); fixture: [")
                self.assertIncomplete(verdict, "the difference may come from the image (tools or versions the tests "
                                               "gate on), not from sharding")
                self.assertFalse(verdict["arms"]["G4"]["eligible"])
                self.assertEqual(verdict["arms"]["G4T"]["eligible"], g4t not in differing)
                self.assertEqual(len(verdict["flags"]), 1, verdict["flags"])
                self.assertIn("the arm runs ran on 2 runner images", verdict["flags"][0])
        with self.subTest("kept: every arm run on one image, the new one"), tempfile.TemporaryDirectory() as tmp:
            tree = Tree(Path(tmp)).full()
            differ(tree, g4)
            for name in every_run:
                rewrite_json(tree.run_dir(name) / "meta.json", runner_image=image)
            verdict = tree.result()["verdicts"][OS]
            self.assertEqual((verdict["outcome"], verdict["selected_arm"], verdict["flags"]), ("adopt", "G4T", []),
                             verdict["reasons"])
        with self.subTest("a step that never wrote its exit status, on two images, which must not hand over"), \
                tempfile.TemporaryDirectory() as tmp:
            tree = Tree(Path(tmp)).full()
            run = tree.run_dir(g4)
            (run / "shard-2.log").write_text((run / "shard-2.log").read_text().split("\n", 1)[0] + "\n")
            (run / "shard-2.exit").unlink()
            rewrite_json(run / "meta.json", runner_image=image)
            result = tree.result()
            verdict = result["verdicts"][OS]
            self.assertGreater(self.run_entry(result, g4)["mismatch_total"], 0)
            self.assertEqual(verdict["arms"]["G4"]["unfinished_steps"], {g4: ["shard-2"]})
            self.assertIncomplete(verdict, f"the records of sharded runs [{g4}] (1) differ from the S baseline while "
                                           f"the arm runs ran on 2 runner images ({image}: [{g4}] (1); fixture: [")
            self.assertEqual(len(verdict["flags"]), 1, verdict["flags"])
            self.assertIn("the arm runs ran on 2 runner images", verdict["flags"][0])

    def test_a_shard_step_hung_until_its_limit_on_another_runner_image_is_incomplete_not_a_handover(self):
        # R6-1: a test that gates on a tool or version of the other image hangs until the shard step's timeout-minutes
        # stops the step: its log ends inside that test, it writes no exit status, the ids after it never run, and its
        # records differ from the S baseline. Previous head: the run was ineligible only through that step, so the rule
        # handed the decision to G4T (adopt G4T, flagged) although G4 had the smaller median. Kept: on one image the
        # same run stays ineligible and the rule passes over its arm with rule 5's flag (preregistered).
        image, g4 = "20260907.0337.1", f"{OS}-G4-r2"
        every_run = [f"{OS}-{arm}-r{repeat}" for arm in compare.arms_of(OS) for repeat in (1, 2, 3)]
        for label, imaged, incomplete in (("two images: incomplete", [g4], True),
                                          ("kept: one image, the new one: ineligible and flagged", every_run, False)):
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(Path(tmp)).full()
                run = tree.run_dir(g4)
                log = run / "shard-2.log"
                log.write_text(log.read_text().split("\n", 1)[0]
                               + "\ntest_two (tests.test_epsilon.EpsilonTests.test_two) ... ")
                (run / "shard-2.exit").unlink()
                rewrite_json(run / "timing.json", step_ns=nanoseconds(1505), wall_ns=nanoseconds(1505))
                for name in imaged:
                    rewrite_json(tree.run_dir(name) / "meta.json", runner_image=image)
                result = tree.result()
                verdict = result["verdicts"][OS]
                entry = self.run_entry(result, g4)
                self.assertFalse(entry["eligible"])
                self.assertIn("1 inventory ids never ran: [tests.test_secret_path_guard.TailTests.test_timing] (1)",
                              entry["reasons"])
                self.assertEqual(entry["mismatch_total"], 2)
                self.assertEqual(verdict["arms"]["G4"]["unfinished_steps"], {g4: ["shard-2"]})
                self.assertTrue(verdict["arms"]["G4"]["ineligible_only_through_unfinished_steps"])
                if incomplete:
                    self.assertIncomplete(verdict, f"the records of sharded runs [{g4}] (1) differ from the S baseline "
                                                   f"while the arm runs ran on 2 runner images ({image}: [{g4}] (1); "
                                                   "fixture: [")
                    self.assertEqual(len(verdict["flags"]), 1, verdict["flags"])
                    self.assertIn("the arm runs ran on 2 runner images", verdict["flags"][0])
                else:
                    self.assertEqual((verdict["outcome"], verdict["selected_arm"]), ("adopt", "G4T"),
                                     verdict["reasons"])
                    self.assertEqual(len(verdict["flags"]), 1, verdict["flags"])
                    self.assertIn(f"arm G4 was ineligible only because steps never wrote an exit status ({g4}: "
                                  "shard-2)", verdict["flags"][0])

    def test_a_serial_step_lost_to_a_runner_fault_is_incomplete_not_no_verdict(self):
        # R4-2: the clock step succeeded, but the S step left none of its files: its script never ran (a runner
        # fault), as a lost control step. Previous head: S r2 ineligible, so no verdict, final. Kept: an S step that
        # wrote its command and log but no exit status (stopped before its end) leaves evidence, which is judged.
        self.tree.full()
        for name in ("command.txt", "log.txt", "exit-code.txt"):
            (self.tree.run_dir(f"{OS}-S-r2") / name).unlink()
        result = self.tree.result()
        self.assertIncomplete(self.verdict(result), f"{OS}-S-r2: the test phase started, but the S step left no "
                                                    "command.txt, log.txt or exit-code.txt (a step lost to a runner fault)")
        self.assertTrue(self.run_entry(result, f"{OS}-S-r2")["test_phase_started"])
        with tempfile.TemporaryDirectory() as tmp:
            tree = Tree(Path(tmp)).full()
            (tree.run_dir(f"{OS}-S-r2") / "exit-code.txt").unlink()
            self.assertEqual(tree.result()["verdicts"][OS]["outcome"], "no verdict")

    def test_failed_controls_reject(self):
        self.tree.full()
        (self.tree.control_dir / "shard-2.exit").write_text("0\n")
        result = self.tree.result()
        self.assertFalse(result["controls"][OS]["passed"])
        self.assertEqual((self.verdict(result)["outcome"], self.verdict(result)["reasons"]),
                         ("reject", ["no sharded arm is eligible"]))

    def test_a_failed_controls_check_job_whose_checks_pass_here_is_incomplete_not_reject(self):
        # F1: compare.py's own check of the same control artifact passes, so the controls-check job failed outside the
        # checks it repeats (a setup step, the head assertion, the download, a lost runner). Previous head: the controls
        # failed, every sharded arm became ineligible, and the OS got reject.
        needs = json.loads(json.dumps(NEEDS))
        needs["controls-check"]["result"] = "failure"
        result = self.tree.full().result(needs=needs)
        self.assertTrue(result["controls"][OS]["passed"], result["controls"][OS]["problems"])
        self.assertEqual(result["controls"][OS]["controls_check_result"], "failure")
        self.assertIncomplete(self.verdict(result), "job controls-check: result 'failure', although compare.py's own "
                                                    "check of the same control artifact passed")

    def test_a_failed_controls_check_job_and_a_failed_check_here_reject(self):
        # F1: both checks fail on the recorded evidence: the controls failed, so no sharded arm is eligible.
        needs = json.loads(json.dumps(NEEDS))
        needs["controls-check"]["result"] = "failure"
        self.tree.full()
        (self.tree.control_dir / "shard-2.exit").write_text("0\n")
        result = self.tree.result(needs=needs)
        self.assertFalse(result["controls"][OS]["passed"])
        self.assertEqual((self.verdict(result)["outcome"], self.verdict(result)["reasons"]),
                         ("reject", ["no sharded arm is eligible"]))

    def test_unrecorded_control_step_outcomes_give_no_verdict_not_reject(self):
        # F4 and S2: the control run records the foreground step's outcome but none of the four control steps', and
        # every other expectation holds: the steps context carries no background step's outcome on this platform, so
        # the controls cannot be judged. Previous head: the controls failed and the OS got reject, final under the
        # deciding-run rule; incomplete would repeat for ever.
        needs = json.loads(json.dumps(NEEDS))
        needs["controls-check"]["result"] = "failure"  # the check job fails on the same evidence
        self.tree.full()
        rewrite_json(self.tree.control_dir / "meta.json",
                     steps={compare.FOREGROUND_STEP: {"outcome": "success", "conclusion": "success"}})
        result = self.tree.result(needs=needs)
        verdict = self.verdict(result)
        self.assertEqual((verdict["outcome"], verdict["selected_arm"]), ("no verdict", None), verdict["reasons"])
        self.assertTrue(any(reason.startswith("the controls are unmeasurable") for reason in verdict["reasons"]),
                        verdict["reasons"])
        self.assertIn("UNMEASURABLE", compare.summary_markdown(result))

    def test_a_recorded_wrong_control_step_outcome_still_rejects(self):
        # F4: a recorded outcome that is wrong (the failing step masked as success) fails the controls.
        self.tree.full()
        rewrite_json(self.tree.control_dir / "meta.json",
                     steps={**CONTROL_STEPS, "control-1": {"outcome": "success", "conclusion": "success"}})
        result = self.tree.result()
        self.assertFalse(result["controls"][OS]["unmeasurable"])
        self.assertEqual((self.verdict(result)["outcome"], self.verdict(result)["reasons"]),
                         ("reject", ["no sharded arm is eligible"]))

    def test_unrecorded_outcomes_beside_another_failed_expectation_reject(self):
        # F4: with no control step outcome recorded, a control that misbehaved on the recorded evidence (the crashing
        # control exited 1, not 3) still fails the controls.
        self.tree.full()
        rewrite_json(self.tree.control_dir / "meta.json",
                     steps={compare.FOREGROUND_STEP: {"outcome": "success", "conclusion": "success"}})
        (self.tree.control_dir / "shard-2.exit").write_text("1\n")
        result = self.tree.result()
        self.assertTrue(result["controls"][OS]["outcomes_unrecorded"])
        self.assertFalse(result["controls"][OS]["unmeasurable"])
        self.assertEqual(self.verdict(result)["outcome"], "reject")

    def test_any_unrecorded_control_step_outcome_alone_gives_no_verdict_not_reject(self):
        # R3-3: an absent outcome is never evidence of failure. One, two or three of the four control step outcomes are
        # unrecorded, no recorded one is wrong and every other expectation holds: the controls are unmeasurable.
        # Previous head: unmeasurable only when all four were missing, so each of these rejected.
        needs = json.loads(json.dumps(NEEDS))
        needs["controls-check"]["result"] = "failure"  # the check job fails on the same evidence
        for missing in (("control-3",), ("control-0", "control-2"), ("control-0", "control-1", "control-2")):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(Path(tmp)).full()
                rewrite_json(tree.control_dir / "meta.json",
                             steps={key: value for key, value in CONTROL_STEPS.items() if key not in missing})
                result = tree.result(needs=needs)
                verdict = result["verdicts"][OS]
                self.assertTrue(result["controls"][OS]["unmeasurable"], result["controls"][OS]["problems"])
                self.assertEqual((verdict["outcome"], verdict["selected_arm"]), ("no verdict", None), verdict["reasons"])
                self.assertIn(f"records no outcome for {', '.join(missing)} ", verdict["reasons"][0])

    def test_a_wrong_recorded_outcome_beside_an_unrecorded_one_rejects(self):
        # R3-3: a recorded wrong outcome is evidence: control-1 recorded as success (a masked failure) beside an
        # unrecorded control-3 still fails the controls.
        self.tree.full()
        steps = {key: value for key, value in CONTROL_STEPS.items() if key != "control-3"}
        steps["control-1"] = {"outcome": "success", "conclusion": "success"}
        rewrite_json(self.tree.control_dir / "meta.json", steps=steps)
        result = self.tree.result()
        self.assertFalse(result["controls"][OS]["unmeasurable"])
        self.assertEqual((self.verdict(result)["outcome"], self.verdict(result)["reasons"]),
                         ("reject", ["no sharded arm is eligible"]))

    def test_a_control_step_lost_to_a_runner_fault_is_incomplete_not_reject(self):
        # R3-4: after the foreground step succeeded, a control step left no probe, no log and no exit status: its
        # script never ran (a runner fault inside the control group), so nothing shows how that control behaves, and
        # its recorded outcome (failure, wrong for the passing control) is the fault's. The OS is incomplete. Previous
        # head: the controls failed, both sharded arms became ineligible, and the OS got reject.
        needs = json.loads(json.dumps(NEEDS))
        needs["controls-check"]["result"] = "failure"
        for index in range(len(compare.CONTROL_SHARDS)):
            label = f"shard-{index}"
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(Path(tmp)).full()
                lose(tree.control_dir, label)
                rewrite_json(tree.control_dir / "meta.json", steps={
                    **CONTROL_STEPS, f"control-{index}": {"outcome": "failure", "conclusion": "failure"}})
                result = tree.result(needs=needs)
                self.assertIncomplete(result["verdicts"][OS], "a runner fault inside the control group), and no other "
                                                              f"control evidence failed: {label}")
                controls = result["controls"][OS]
                self.assertEqual(controls["lost_steps"], [label])
                self.assertTrue(controls["failed_only_through_lost_steps"], controls["problems"])
                self.assertFalse(controls["passed"] or controls["unmeasurable"])
                self.assertIn("INCOMPLETE (steps lost to a runner fault", compare.summary_markdown(result))

    def test_a_lost_control_step_beside_an_unrecorded_outcome_is_incomplete(self):
        # R3-4 before R3-3: a lost step makes the OS incomplete, which comes before the no verdict of unmeasurable
        # controls; neither gap is evidence.
        self.tree.full()
        lose(self.tree.control_dir, "shard-2")
        rewrite_json(self.tree.control_dir / "meta.json",
                     steps={key: value for key, value in CONTROL_STEPS.items() if key not in ("control-0", "control-2")})
        result = self.tree.result()
        self.assertFalse(result["controls"][OS]["unmeasurable"])
        self.assertIncomplete(self.verdict(result), "a runner fault inside the control group")

    def test_a_lost_control_step_beside_wrong_recorded_evidence_rejects(self):
        # R3-4: evidence that exists and shows wrong behaviour still fails the controls: control shard 2 is lost, and
        # the failing control's exit status is 0 although its log says FAILED.
        self.tree.full()
        lose(self.tree.control_dir, "shard-2")
        (self.tree.control_dir / "shard-1.exit").write_text("0\n")
        result = self.tree.result()
        self.assertEqual((self.verdict(result)["outcome"], self.verdict(result)["reasons"]),
                         ("reject", ["no sharded arm is eligible"]))
        self.assertEqual(result["controls"][OS]["lost_steps"], ["shard-2"])
        self.assertFalse(result["controls"][OS]["failed_only_through_lost_steps"])
        # The lost step's list comes from an earlier step, so a wrong one is evidence too.
        (self.tree.control_dir / "shard-1.exit").write_text("1\n")
        (self.tree.control_dir / "shard-2.txt").write_text("test_ctl_pass\n")
        controls = self.tree.result()["controls"][OS]
        self.assertFalse(controls["failed_only_through_lost_steps"], controls["problems"])

    def test_a_cancelled_control_job_status_is_incomplete_not_reject(self):
        # F6: the control run's own job status cancelled (for example after a job-level timeout that the needs context
        # reports as a failure). Previous head: only a failed control expectation, so reject.
        self.tree.full()
        rewrite_json(self.tree.control_dir / "meta.json", job_status="cancelled")
        self.assertIncomplete(self.verdict(), f"cancelled jobs: {OS}-controls")

    def test_partial_and_cancelled_runs_are_incomplete_not_a_rule_outcome(self):
        cases = {
            "missing run directory": (lambda tree: shutil.rmtree(tree.run_dir(f"{OS}-G4T-r3").parent), NEEDS),
            "cancelled job status": (lambda tree: rewrite_json(tree.run_dir(f"{OS}-S-r1") / "meta.json",
                                                               job_status="cancelled"), NEEDS),
            "cancelled job": (lambda tree: None, {**NEEDS, "shards": {"result": "cancelled"}}),
            "skipped job": (lambda tree: None, {**NEEDS, "serial": {"result": "skipped"}}),
            "no control run": (lambda tree: shutil.rmtree(tree.control_artifact), NEEDS),
        }
        for label, (mutate, needs) in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(Path(tmp)).full()
                mutate(tree)
                verdict = tree.result(needs=needs)["verdicts"][OS]
                self.assertEqual(verdict["outcome"], "incomplete", verdict["reasons"])
                self.assertIsNone(verdict["selected_arm"])

    def test_no_run_directory_at_all_is_incomplete(self):
        verdict = self.verdict()
        self.assertEqual(verdict["outcome"], "incomplete")
        self.assertTrue(any("no run directory" in reason for reason in verdict["reasons"]), verdict["reasons"])

    def test_a_failed_inventory_gate_gives_no_verdict(self):
        rewrite_json(self.tree.inventory / "report.json", ok=False, parity=False,
                     problems=["1 ids are loaded twice by name: [tests.test_zeta.Unused.test_one (planted)]"])
        needs = {**NEEDS, "inventory": {"result": "failure"}, "serial": {"result": "skipped"},
                 "shards": {"result": "skipped"}}
        self.assertEqual(self.verdict(self.tree.result(needs=needs))["outcome"], "no verdict")

    def test_an_inventory_gate_stopped_from_outside_is_incomplete_not_no_verdict(self):
        # F12: the gate's own child interpreter was stopped by a signal from outside (the out-of-memory killer, a
        # runner fault): report.json records an execution problem and no finding. Previous head: no verdict, final.
        rewrite_json(self.tree.inventory / "report.json", ok=False, parity=None, problems=[],
                     execution_problems=["the discover child interpreter was stopped by SIGKILL from outside: "])
        needs = {**NEEDS, "inventory": {"result": "failure"}, "serial": {"result": "skipped"},
                 "shards": {"result": "skipped"}}
        self.assertIncomplete(self.verdict(self.tree.result(needs=needs)),
                              "(execution problems: the discover child interpreter was stopped by SIGKILL")

    def test_an_inventory_job_that_failed_before_its_gate_reported_is_incomplete(self):
        # E2: a setup failure of the inventory job (checkout, setup-python, the upload) is a partial run; on the
        # previous head it gave no verdict, which the deciding-run rule would have made final.
        (self.tree.inventory / "report.json").unlink()
        needs = {**NEEDS, "inventory": {"result": "failure"}, "serial": {"result": "skipped"},
                 "shards": {"result": "skipped"}}
        self.assertIncomplete(self.verdict(self.tree.result(needs=needs)), "the gate never reported")

    def test_an_unusable_inventory_gives_no_verdict(self):
        mutations = {
            "report not ok": lambda inv: (inv / "report.json").write_text(json.dumps({"ok": False, "parity": True,
                                                                                    "os": OS})),
            "lists not make_shards'": lambda inv: (inv / "shards/G4/shard-0.txt").write_text("tests.test_beta\n") or
            (inv / "shards/G4/shard-1.txt").write_text("tests.test_alpha\n"),
            "id map gap": lambda inv: (inv / "module_ids.json").write_text(json.dumps(
                {k: v for k, v in json.loads(fixture("inventory/module_ids.json")).items() if k != "tests.test_beta"})),
        }
        for label, mutate in mutations.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(Path(tmp)).full()
                mutate(tree.inventory)
                verdict = tree.result()["verdicts"][OS]
                self.assertEqual(verdict["outcome"], "no verdict", verdict["reasons"])

    def test_every_preregistered_os_is_listed(self):
        result = self.tree.full().result()
        self.assertEqual(set(result["verdicts"]), set(make_shards.ARMS))
        other = result["verdicts"]["macos-15"]
        self.assertEqual(other["outcome"], "not measured")
        self.assertIn("no run directory", other["reasons"][0])

    def test_the_os_a_run_did_not_measure_is_not_measured_never_no_verdict(self):
        # R3-9: a Linux-only result.json lists macOS as not measured, and a macOS-only one Linux, never as no verdict,
        # which the deciding-run rule could have read as that OS's decision. Previous head: no verdict.
        result = self.tree.full().result()
        self.assertEqual(result["verdicts"]["macos-15"]["outcome"], "not measured")
        self.assertIn("- **macos-15**: not measured (no run directory", compare.summary_markdown(result))
        macos = compare.build_result(self.tree.results, self.tree.inventory, SHA, "macos-15", NEEDS,
                                     weights=FIXTURE_WEIGHTS, compare_attempt="1")
        self.assertEqual(macos["verdicts"]["ubuntu-24.04"]["outcome"], "not measured")
        self.assertEqual(macos["verdicts"]["macos-15"]["outcome"], "incomplete", "its own OS, without runs")
        unscoped = compare.build_result(self.tree.results, self.tree.inventory, SHA, None, NEEDS,
                                        weights=FIXTURE_WEIGHTS, compare_attempt="1")
        self.assertEqual((unscoped["verdicts"][OS]["outcome"], unscoped["verdicts"]["macos-15"]["outcome"]),
                         ("adopt", "not measured"))

    def test_an_inventory_file_absent_after_a_successful_inventory_job_is_incomplete(self):
        # R3-2: the inventory job succeeded, so its gate wrote and uploaded every file; a file absent from the compare
        # job's download is a partly downloaded artifact set (a runner fault). Previous head: no verdict, final under
        # the deciding-run rule. A file that is present but inconsistent still gives no verdict (the test above).
        for name in ("report.json", "inventory.txt", "module_ids.json", "shards/G4/shard-1.txt", "shards/G4T/tail.txt",
                     None):
            with self.subTest(name or "the whole artifact"), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(Path(tmp)).full()
                if name is None:
                    shutil.rmtree(tree.inventory)
                    tree.inventory.mkdir()
                else:
                    (tree.inventory / name).unlink()
                self.assertIncomplete(tree.result()["verdicts"][OS], "a partly downloaded artifact set (a runner fault)")
        rewrite_json(self.tree.full().inventory / "report.json", ok=False)
        self.assertEqual(self.verdict()["outcome"], "no verdict", "present but inconsistent")

    def cli(self, out: Path, summary: Path, status: Path) -> int:
        needs = self.tree.results.parent / "needs.json"
        needs.write_text(json.dumps(NEEDS))
        return compare.main(["verdict", "--results", str(self.tree.results), "--inventory", str(self.tree.inventory),
                             "--expected-sha", SHA, "--run-attempt", "1", "--os", OS, "--needs", str(needs),
                             "--out", str(out), "--summary-md", str(summary), "--checkout-status", str(status),
                             "--skip-list-recompute"])

    def test_a_failed_summary_or_status_write_leaves_no_result_json(self):
        # R3-1: summary.md and checkout-status.json are written before result.json, so a failure in either leaves no
        # result.json and no outcome line, and the run is incomplete; a failure after result.json exists is impossible
        # by construction. Previous head: result.json came first and stayed beside the failure, decisive in a run that
        # the protocol then called repeatable.
        self.tree.full()
        out = self.tree.results.parent
        missing = out / "no-such-directory"
        for label, summary, status in (("summary.md", missing / "summary.md", out / "checkout-status.json"),
                                       ("checkout-status.json", out / "summary.md", missing / "checkout-status.json")):
            with self.subTest(label):
                with contextlib.redirect_stdout(io.StringIO()) as printed, self.assertRaises(OSError):
                    self.cli(out / "result.json", summary, status)
                self.assertFalse((out / "result.json").exists())
                self.assertEqual(printed.getvalue(), "")

    def test_result_json_appears_whole_and_before_the_outcome_lines(self):
        # R3-1: result.json is renamed into place from a temporary file, which a failed rename removes; the outcome
        # lines are printed only once result.json exists.
        self.tree.full()
        out = self.tree.results.parent
        with mock.patch.object(compare.os, "replace", side_effect=OSError("no space left")), \
                contextlib.redirect_stdout(io.StringIO()) as printed, self.assertRaises(OSError):
            self.cli(out / "result.json", out / "summary.md", out / "checkout-status.json")
        self.assertEqual([path.name for path in out.iterdir() if path.name.startswith("result.json")], [])
        self.assertEqual(printed.getvalue(), "")
        seen = []
        with mock.patch("builtins.print", side_effect=lambda *args, **kwargs: seen.append((out / "result.json").exists())):
            self.assertEqual(self.cli(out / "result.json", out / "summary.md", out / "checkout-status.json"), 0)
        self.assertEqual(seen, [True] * len(compare.OSES))
        self.assertEqual(json.loads((out / "result.json").read_text())["verdicts"][OS]["outcome"], "adopt")

    def test_the_cli_writes_the_three_outputs(self):
        self.tree.full()
        needs = self.tree.results.parent / "needs.json"
        needs.write_text(json.dumps(NEEDS))
        out = self.tree.results.parent
        with contextlib.redirect_stdout(io.StringIO()):
            code = compare.main(["verdict", "--results", str(self.tree.results), "--inventory", str(self.tree.inventory),
                                 "--expected-sha", SHA, "--run-attempt", "1", "--os", OS, "--needs", str(needs),
                                 "--out", str(out / "result.json"), "--summary-md", str(out / "summary.md"),
                                 "--checkout-status", str(out / "checkout-status.json"), "--skip-list-recompute"])
        self.assertEqual(code, 0)
        result = json.loads((out / "result.json").read_text())
        self.assertEqual(result["verdicts"][OS]["outcome"], "adopt")
        self.assertEqual(result["inputs"]["compare_run_attempt"], "1")
        self.assertFalse(result["inputs"]["inventory"]["lists_recomputed"])
        summary = (out / "summary.md").read_text()
        self.assertIn("**ubuntu-24.04**: adopt G4", summary)
        self.assertIn("result.json, the exit files and the job results are the record", summary)
        status = json.loads((out / "checkout-status.json").read_text())
        self.assertTrue(status["ok"])
        self.assertEqual(len(status["runs"]), 10)


class RerunTests(TreeCase):
    """E1: any re-run (a run attempt other than 1 anywhere) makes the OS incomplete, never a rule outcome."""

    def test_a_rerun_arm_run_is_incomplete_not_a_handover_to_the_other_arm(self):
        # On the previous head the re-run voided only G4 r1, so the rule picked G4T: adopt G4T.
        self.tree.full()
        rewrite_json(self.tree.run_dir(f"{OS}-G4-r1") / "runtime.json", run_attempt="2")
        self.assertIncomplete(self.verdict(), "ubuntu-24.04-G4-r1: run_attempt '2'")

    def test_a_rerun_serial_run_is_incomplete_not_no_verdict(self):
        # Previous head: no verdict (S ineligible).
        self.tree.full()
        rewrite_json(self.tree.run_dir(f"{OS}-S-r2") / "runtime.json", run_attempt="2")
        self.assertIncomplete(self.verdict(), "ubuntu-24.04-S-r2: run_attempt '2'")

    def test_a_rerun_control_run_is_incomplete_not_reject(self):
        # Previous head: the attempt failed the controls, every sharded arm became ineligible, and the OS got reject.
        # A re-run of the control job also re-runs controls-check, whose result is applied after the attempt check.
        needs = json.loads(json.dumps(NEEDS))
        needs["controls-check"]["result"] = "failure"
        self.tree.full()
        rewrite_json(self.tree.control_dir / "runtime.json", run_attempt="2")
        for case in (NEEDS, needs):
            with self.subTest(controls_check=case["controls-check"]["result"]):
                self.assertIncomplete(self.verdict(self.tree.result(needs=case)), "the control run: run_attempt '2'")

    def test_an_unrecorded_attempt_is_a_partial_run_not_a_rerun(self):
        # F8: no runtime.json is what a setup step that failed before the run directory was prepared leaves; it is
        # reported as an unrecorded attempt, never as a re-run.
        self.tree.full()
        (self.tree.run_dir(f"{OS}-G4T-r2") / "runtime.json").unlink()
        verdict = self.verdict()
        self.assertIncomplete(verdict, "ubuntu-24.04-G4T-r2: the run attempt is unrecorded (runtime.json is missing or "
                                       "not JSON)")
        self.assertFalse(any(reason.startswith("a re-run") for reason in verdict["reasons"]), verdict["reasons"])

    def test_an_unrecorded_control_attempt_is_a_partial_run_not_a_rerun(self):
        # F8, for the control run.
        self.tree.full()
        (self.tree.control_dir / "runtime.json").unlink()
        verdict = self.verdict()
        self.assertIncomplete(verdict, "the control run: the run attempt is unrecorded")
        self.assertFalse(any(reason.startswith("a re-run") for reason in verdict["reasons"]), verdict["reasons"])

    def test_the_compare_jobs_own_attempt_decides_before_anything_else(self):
        # Previous head: build_result took no attempt (TypeError) and the CLI had no --run-attempt (exit 2).
        self.tree.full()
        for attempt in ("2", "", None):
            with self.subTest(attempt=attempt):
                result = self.tree.result(compare_attempt=attempt)
                self.assertIncomplete(result["verdicts"][OS], "the compare job's own run attempt")
                self.assertEqual(result["inputs"]["compare_run_attempt"], attempt)
        needs = {**NEEDS, "inventory": {"result": "failure"}, "serial": {"result": "skipped"},
                 "shards": {"result": "skipped"}}
        rewrite_json(self.tree.inventory / "report.json", ok=False)
        self.assertIncomplete(self.verdict(self.tree.result(needs=needs, compare_attempt="2")),
                              "the compare job's own run attempt")

    def test_the_cli_requires_the_run_attempt(self):
        self.tree.full()
        out = self.tree.results.parent / "result.json"
        base = ["verdict", "--results", str(self.tree.results), "--inventory", str(self.tree.inventory),
                "--expected-sha", SHA, "--os", OS, "--out", str(out)]
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            compare.main(base)
        self.assertEqual(raised.exception.code, 2)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(compare.main(base + ["--run-attempt", "2"]), 0)
        self.assertEqual(json.loads(out.read_text())["verdicts"][OS]["outcome"], "incomplete")


class SetupFailureTests(TreeCase):
    """E2: a run whose test phase never started, or a control group that never started, is partial (incomplete)."""

    def test_a_g4_setup_failure_with_g4t_fine_is_incomplete_not_adopt_g4t(self):
        # Previous head: G4 r1 was merely ineligible, so G4T decided: adopt G4T.
        cases = {
            "clock step skipped, nothing but the finish step's files": lambda d: setup_failure(d),
            "clock step failed": lambda d: rewrite_json(d / "meta.json", steps={
                "start": {"outcome": "failure", "conclusion": "failure"}}),
            "no step outcomes recorded": lambda d: rewrite_json(d / "meta.json", steps=None),
            "no clock start in timing.json": lambda d: (d / "timing.json").write_text(json.dumps(
                {"clock": "fixture", "step_ns": None, "wall_ns": None, "problems": ["never timed"]})),
            "no timing.json": lambda d: (d / "timing.json").unlink(),
            "no meta.json": lambda d: (d / "meta.json").unlink(),
        }
        for label, mutate in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(Path(tmp)).full()
                mutate(tree.run_dir(f"{OS}-G4-r1"))
                result = tree.result()
                self.assertIncomplete(result["verdicts"][OS], "ubuntu-24.04-G4-r1: ")
                self.assertFalse(self.run_entry(result, f"{OS}-G4-r1")["test_phase_started"])

    def test_a_job_cancelled_before_its_clock_names_both_causes(self):
        # A cancelled job whose finish step saw an empty steps context: incomplete, with the cancellation and the
        # missing clock-start outcome both in the reasons.
        self.tree.full()
        directory = self.tree.run_dir(f"{OS}-G4T-r3")
        setup_failure(directory, steps={})
        rewrite_json(directory / "meta.json", job_status="cancelled")
        verdict = self.verdict()
        self.assertIncomplete(verdict, "cancelled jobs: ubuntu-24.04-G4T-r3")
        self.assertIncomplete(verdict, "ubuntu-24.04-G4T-r3: the 'start' step's outcome is None, not 'success'")

    def test_a_serial_setup_failure_is_incomplete_not_no_verdict(self):
        self.tree.full()
        setup_failure(self.tree.run_dir(f"{OS}-S-r2"))
        self.assertIncomplete(self.verdict(), "the test phase never started")

    def test_a_control_group_that_never_started_is_incomplete_not_reject(self):
        # Previous head: a control directory without probes or logs failed the controls: reject.
        def finish_only(directory: Path):
            for path in list(directory.iterdir()):
                if path.name not in ("meta.json", "git-status.txt", "runtime.json"):
                    path.unlink()
            rewrite_json(directory / "meta.json", steps={"foreground": {"outcome": "skipped", "conclusion": "skipped"}})

        cases = {
            "setup failure before the foreground probe": finish_only,
            "foreground probe missing": lambda d: (d / "foreground.probe.json").unlink(),
            "foreground step failed": lambda d: rewrite_json(d / "meta.json", steps={
                **CONTROL_STEPS, "foreground": {"outcome": "failure", "conclusion": "failure"}}),
        }
        needs = json.loads(json.dumps(NEEDS))
        needs["controls-check"]["result"] = "failure"
        for label, mutate in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(Path(tmp)).full()
                mutate(tree.control_dir)
                result = tree.result(needs=needs)
                self.assertFalse(result["controls"][OS]["started"])
                self.assertIncomplete(result["verdicts"][OS], "the control run's parallel group never started")


class ArtifactTests(TreeCase):
    """S2: a run directory counts only from the artifact whose name gives it."""

    def test_an_artifact_holding_another_runs_directory_makes_its_run_ineligible(self):
        self.tree.full()
        victim = self.tree.run_dir(f"{OS}-G4T-r1")
        stray = self.tree.run_dir(f"{OS}-G4-r1").parent / victim.name
        shutil.copytree(victim, stray)
        (stray / "shard-0.log").write_text("planted\n")
        result = self.tree.result()
        entry = self.run_entry(result, f"{OS}-G4-r1")
        self.assertTrue(any("holds entries besides its run directory" in reason for reason in entry["reasons"]))
        self.assertTrue(self.run_entry(result, victim.name)["eligible"], "the victim is read from its own artifact")
        self.assertEqual(self.verdict(result)["selected_arm"], "G4T")

    def test_a_bare_or_misdelivered_run_directory_is_not_attributed(self):
        self.tree.full()
        moved = self.tree.run_dir(f"{OS}-S-r1")
        shutil.move(str(moved), str(self.tree.results / moved.name))
        (self.tree.results / f"{compare.ARM_ARTIFACT_PREFIX}{moved.name}").rmdir()
        other = self.tree.run_dir(f"{OS}-G4-r2")
        shutil.move(str(other), str(other.parent / "elsewhere"))
        result = self.tree.result()
        self.assertEqual(result["inputs"]["ignored_entries"],
                         ["arm-ubuntu-24.04-G4-r2 (holds no ubuntu-24.04-G4-r2 directory)", "ubuntu-24.04-S-r1"])
        self.assertIncomplete(result["verdicts"][OS], "arm S: no run directory for repeat 1")

    def test_a_stray_entry_in_the_control_artifact_fails_the_controls(self):
        self.tree.full()
        (self.tree.control_artifact / "stray").mkdir()
        report = compare.check_controls(self.tree.control_artifact, OS, "failure", SHA)
        self.assertFalse(report["passed"])
        self.assertIn("the control artifact holds entries besides ubuntu-24.04-controls: [stray] (1)", report["problems"])


# --------------------------------------------------------------------------- compare.py: the controls


class ControlTests(TreeCase):
    def setUp(self):
        super().setUp()
        self.directory = self.tree.controls()

    def check(self, job_result="failure", artifact=None):
        return compare.check_controls(artifact or self.tree.control_artifact, OS, job_result, SHA)

    def test_the_real_control_runs_pass(self):
        report = self.check()
        self.assertTrue(report["passed"], report["problems"])
        self.assertTrue(report["started"])
        self.assertEqual([item["exit_code"] for item in report["shards"]], [0, 1, 3, None])
        self.assertEqual([item["step_outcome"] for item in report["shards"]],
                         ["success", "failure", "failure", "failure"])
        self.assertFalse(report["background_ignores_sigquit"])
        self.assertFalse(report["outcomes_unrecorded"] or report["unmeasurable"])
        hang = report["hang"]
        # make_fixtures.py stops the hang control's own process at 60 s, so its step's stop is its last heartbeat.
        self.assertEqual(hang["stop_seen_as"], "last heartbeat")
        self.assertGreaterEqual(hang["stop_after_probe_seconds"], compare.HANG_STOP_MIN_NS / 1e9)
        self.assertLess(hang["stop_after_probe_seconds"], hang["stop_deadline_after_probe_seconds"])
        self.assertLess(hang["group_end_after_probe_seconds"], compare.HANG_GROUP_MAX_NS / 1e9)
        self.assertGreaterEqual(hang["group_end_after_probe_seconds"], 120, "the crash control ends the group")
        self.assertFalse(hang["outlived_step"], "make_fixtures.py stops the hang control's own process")
        self.assertLess(report["start_spread_seconds"], 5)

    def test_the_control_job_must_fail(self):
        self.assertFalse(self.check("success")["passed"])
        self.assertFalse(self.check(None)["passed"])

    def test_each_expectation_is_checked(self):
        def steps(**changed):
            return lambda d: rewrite_json(d / "meta.json", steps={
                **CONTROL_STEPS, **{step: {"outcome": value, "conclusion": value} for step, value in changed.items()}})

        mutations = {
            "the hang wrote an exit status": lambda d: (d / "shard-3.exit").write_text("0\n"),
            "the crash exited 1": lambda d: (d / "shard-2.exit").write_text("1\n"),
            "the failing shard exited 0": lambda d: (d / "shard-1.exit").write_text("0\n"),
            "the passing shard failed": lambda d: (d / "shard-0.exit").write_text("1\n"),
            "a command differs": lambda d: (d / "shard-0.command").write_text("python3 -m unittest test_ctl_pass\n"),
            "a step never reached its command": lambda d: (d / "shard-3.command").unlink(),
            "the hang never started": lambda d: (d / "shard-3.log").write_text("\n"),
            "an export did not reach a background step": lambda d: self.probe(d, "shard-1", env=False),
            "a background step ran another interpreter": lambda d: self.probe(d, "shard-2", python="3.9.6"),
            "a list names another module": lambda d: (d / "shard-0.txt").write_text("test_ctl_fail\n"),
            "dirty checkout": lambda d: (d / "git-status.txt").write_text("?? x\n"),
            # E3: each step's own outcome, the concurrency of the steps and the hang control's span.
            "the failing step's own outcome was masked": steps(**{"control-1": "success"}),
            "the crashing step's own outcome was masked": steps(**{"control-2": "success"}),
            "the hang step was cancelled, not failed": steps(**{"control-3": "cancelled"}),
            "the passing step failed on its own": steps(**{"control-0": "failure"}),
            "the step outcomes are unrecorded": lambda d: rewrite_json(d / "meta.json", steps={
                "foreground": {"outcome": "success", "conclusion": "success"}}),
            # R3-3: one outcome missing beside recorded ones is unmeasurable too (previous head: failed, reject).
            "one control step's outcome is unrecorded": lambda d: rewrite_json(d / "meta.json", steps={
                key: value for key, value in CONTROL_STEPS.items() if key != "control-3"}),
            # F5: 16 s apart is beyond the 15 s spread.
            "the steps did not run together": lambda d: self.probe(d, "shard-1", shift=16 * SECOND),
            "a probe holds no start time": lambda d: self.probe(d, "shard-2", drop="monotonic_ns"),
            "the failing control's probe holds no start time": lambda d: self.probe(d, "shard-1", drop="monotonic_ns"),
            "the hang was stopped before its limit": lambda d: self.beats(d, keep_until=40 * SECOND),
            "the group waited for the hang": lambda d: self.beats(d, end_after=300 * SECOND),
            "no heartbeat": lambda d: (d / "heartbeat.json").unlink(),
        }
        for label, mutate in mutations.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(Path(tmp))
                directory = tree.controls()
                mutate(directory)
                report = compare.check_controls(tree.control_artifact, OS, "failure", SHA)
                self.assertFalse(report["passed"], label)
                self.assertTrue(report["started"], label)
                self.assertEqual(report["unmeasurable"], label in ("the step outcomes are unrecorded",
                                                                   "one control step's outcome is unrecorded"), label)
                self.assertEqual((report["lost_steps"], report["failed_only_through_lost_steps"]), ([], False), label)

    def probe(self, directory: Path, label: str, env=True, python=None, shift=0, drop=None):
        path = directory / f"{label}.probe.json"
        data = json.loads(path.read_text())
        data["env_present"][compare.CONTROL_ENV_NAME] = env
        if python:
            data["python_version"] = python
        data["monotonic_ns"] += shift
        if drop:
            del data[drop]
        path.write_text(json.dumps(data))

    def beats(self, directory: Path, keep_until=None, end_after=None, parent=None, after_recheck=None):
        """Rewrite heartbeat.json relative to the hang control's probe."""
        start = json.loads((directory / "shard-3.probe.json").read_text())["monotonic_ns"]
        data = json.loads((directory / "heartbeat.json").read_text())
        if keep_until is not None:
            data["beats"] = [beat for beat in data["beats"] if beat[0] - start <= keep_until]
            data["beats_after_recheck"] = len(data["beats"])
        if end_after is not None:
            data["end_monotonic_ns"] = start + end_after
        if parent is not None:
            changed_from, pid = parent
            data["beats"] = [[ns, pid if ns - start >= changed_from else first]
                             for (ns, first) in data["beats"]]
        if after_recheck is not None:
            data["beats_after_recheck"] = after_recheck
        (directory / "heartbeat.json").write_text(json.dumps(data))

    def synthesize(self, directory: Path, last: int, lost=None, pid=1):
        """Rewrite heartbeat.json as a process that beat once a second from the hang control's probe until `last`
        seconds, its parent pid changing to `pid` from `lost` seconds on (None: never), with the finish step at
        `last` + 1 s and the process still beating during the recheck."""
        start = json.loads((directory / "shard-3.probe.json").read_text())["monotonic_ns"]
        data = json.loads((directory / "heartbeat.json").read_text())
        parent = data["beats"][0][1]
        data["beats"] = [[start + second * SECOND + SECOND // 25, parent if lost is None or second < lost else pid]
                         for second in range(last + 1)]
        data["end_monotonic_ns"] = start + (last + 1) * SECOND
        data["beats_after_recheck"] = len(data["beats"]) + 3
        (directory / "heartbeat.json").write_text(json.dumps(data))

    def test_a_process_that_outlived_a_step_stopped_at_its_limit_passes(self):
        # S4 and F2: the runner signals only a stopped step's shell (actions/runner v2.337.0, ProcessInvoker.cs), so
        # its python child may live on, re-parented, until the job ends. The README's expected hosted case: the shell
        # ends about 67.5 s after the step started (SIGINT at 60 s, SIGTERM 7.5 s later) and the process beats on.
        self.synthesize(self.directory, last=120, lost=67)
        report = self.check()
        self.assertTrue(report["passed"], report["problems"])
        hang = report["hang"]
        self.assertTrue(hang["outlived_step"])
        self.assertEqual(hang["stop_seen_as"], "parent pid changed")
        self.assertEqual((hang["stop_after_probe_seconds"], hang["parent_lost_after_probe_seconds"]), (67.04, 67.04))
        self.assertGreaterEqual(hang["alive_after_probe_seconds"], 120)

    def test_a_hang_step_stopped_early_fails_though_its_process_beats_on(self):
        # F2: the shell ended 20 s after the step started and the re-parented process beat on to the group's end.
        # Previous head: judged by the last heartbeat (120 s after the probe), the controls passed.
        self.synthesize(self.directory, last=120, lost=20)
        report = self.check()
        self.assertFalse(report["passed"])
        self.assertTrue(any("before its 1-minute limit" in problem for problem in report["problems"]),
                        report["problems"])

    def test_a_hang_step_stopped_only_after_the_failing_control_could_fail_fails(self):
        # F2: a shell that ended 95 s after the step started, after the failing control's probe plus 90 s, may have
        # been stopped by a sibling's failure rather than by its own 1-minute limit. Previous head: passed.
        self.synthesize(self.directory, last=120, lost=95)
        report = self.check()
        self.assertFalse(report["passed"])
        self.assertTrue(any("not attributable to the 1-minute limit" in problem for problem in report["problems"]),
                        report["problems"])

    def test_a_hang_process_that_kept_its_parent_to_the_end_fails(self):
        # F2: the parent pid never changed and the process beat until the group ended: nothing shows that the step
        # was stopped at its limit. Previous head: passed.
        self.synthesize(self.directory, last=120, lost=None)
        report = self.check()
        self.assertFalse(report["passed"])
        self.assertTrue(any("not attributable to the 1-minute limit" in problem for problem in report["problems"]),
                        report["problems"])

    def test_the_checks_across_steps_judge_only_the_steps_that_ran(self):
        # R3-4: a lost hang step leaves no heartbeat to judge and a lost failing step no deadline, and the start spread
        # is taken over the steps that ran; what the steps that ran recorded is still judged.
        for label in ("shard-3", "shard-1"):
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(Path(tmp))
                directory = tree.controls()
                lose(directory, label)
                report = compare.check_controls(tree.control_artifact, OS, "failure", SHA)
                self.assertIsNotNone(report["start_spread_seconds"])
                if label == "shard-1":
                    self.assertIsNotNone(report["hang"]["stop_after_probe_seconds"])
                    self.assertIsNone(report["hang"]["stop_deadline_after_probe_seconds"])
                else:
                    self.assertIsNone(report["hang"]["stop_after_probe_seconds"])
                self.assertEqual(report["lost_steps"], [label])
                self.assertTrue(report["failed_only_through_lost_steps"], report["problems"])
                if label == "shard-3":
                    continue
                self.beats(directory, keep_until=40 * SECOND)  # the hang step stopped early: recorded wrong behaviour
                report = compare.check_controls(tree.control_artifact, OS, "failure", SHA)
                self.assertFalse(report["failed_only_through_lost_steps"])
                self.assertTrue(any("before its 1-minute limit" in problem for problem in report["problems"]))

    def test_unrecorded_control_step_outcomes_alone_are_unmeasurable(self):
        # F4: only the four control steps' outcomes are missing; the foreground step's is recorded.
        rewrite_json(self.directory / "meta.json", steps={compare.FOREGROUND_STEP: {"outcome": "success",
                                                                                     "conclusion": "success"}})
        report = self.check()
        self.assertFalse(report["passed"])
        self.assertTrue(report["outcomes_unrecorded"] and report["unmeasurable"])
        self.assertTrue(report["started"])
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(compare.main(["controls", "--artifact", str(self.tree.control_artifact), "--os", OS,
                                           "--job-result", "failure", "--expected-sha", SHA]), 1)
        self.assertIn("controls ubuntu-24.04: UNMEASURABLE", out.getvalue())

    def test_the_controls_outlive_the_hang_limit(self):
        # E3: control shards 1 and 2 fail only after control shard 3's 1-minute limit, 1 before 2, and the hang
        # control would run far beyond its limit; checked on the frozen modules' text.
        def constant(module: str, name: str) -> int:
            text = (HERE / "controls" / f"{module}.py").read_text(encoding="utf-8")
            return int(re.search(rf"(?m)^{name} = ([0-9]+)$", text).group(1))

        fail, crash = constant("test_ctl_fail", "SLEEP_SECONDS"), constant("test_ctl_crash", "SLEEP_SECONDS")
        hang = constant("test_ctl_hang", "SLEEP_SECONDS")
        self.assertEqual(fail * SECOND, compare.FAIL_CONTROL_AFTER_NS)
        self.assertGreater(crash, fail)
        self.assertGreater(hang, compare.HANG_GROUP_MAX_NS // SECOND)
        # F5: the hang step is stopped at most 70 s after its start (the 60 s limit, then SIGINT, 7.5 s, SIGTERM,
        # 2.5 s and a kill: ProcessInvoker.cs at v2.337.0). With every probe within the start spread, the failing
        # control fails only after that stop, and the crashing control only after the failing control's failure.
        stop_ceiling = 70 * SECOND
        self.assertGreater(fail * SECOND, stop_ceiling + compare.CONTROL_START_SPREAD_MAX_NS)
        self.assertGreater(crash * SECOND, fail * SECOND + compare.CONTROL_START_SPREAD_MAX_NS)
        self.assertLess(compare.HANG_STOP_MIN_NS, 60 * SECOND)
        self.assertEqual(constant("test_ctl_hang", "HEARTBEAT_SECONDS"), 1)

    def test_ignored_signals_are_reported_not_judged(self):
        path = self.directory / "shard-0.probe.json"
        data = json.loads(path.read_text())
        data["signals"]["SIGQUIT"]["ignored"] = True
        path.write_text(json.dumps(data))
        report = self.check()
        self.assertTrue(report["passed"])
        self.assertTrue(report["background_ignores_sigquit"])

    def test_the_controls_cli(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(compare.main(["controls", "--artifact", str(self.tree.control_artifact), "--os", OS,
                                           "--job-result", "failure", "--expected-sha", SHA]), 0)
            self.assertEqual(compare.main(["controls", "--artifact", str(self.tree.control_artifact), "--os", OS,
                                           "--job-result", "success"]), 1)


# --------------------------------------------------------------------------- the two workflows


def jobs(text: str) -> dict:
    body = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"(?m)^  ([A-Za-z0-9_-]+):[ \t]*$", body)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.texts = {os_name: path.read_text(encoding="utf-8") for os_name, path in WORKFLOWS.items()}

    def test_the_trial_runs_only_when_its_pull_request_opens_or_reopens(self):
        for os_name, text in self.texts.items():
            with self.subTest(os_name):
                head = text.split("\npermissions:", 1)[0]
                self.assertIn("  pull_request:\n    types: [opened, reopened]\n    paths:\n"
                              f"      - .github/workflows/{WORKFLOWS[os_name].name}\n", head)
                self.assertNotIn("synchronize", head.split("\non:\n", 1)[1])

    def test_a_reopen_cancels_a_run_in_progress(self):
        # E4: one attended run per OS, never an unattended second run queued behind the first.
        for os_name, text in self.texts.items():
            with self.subTest(os_name):
                block = text.split("\nconcurrency:\n", 1)[1].split("\n\n", 1)[0]
                self.assertIn(f"group: suite-shards-trial-{os_name.split('-')[0].replace('ubuntu', 'linux')}-"
                              "${{ github.event.pull_request.number }}", block)
                self.assertRegex(block, r"(?m)^  cancel-in-progress: true$")

    def test_the_jobs_and_their_runners(self):
        runner = {"ubuntu-24.04": "ubuntu-24.04", "macos-15": "macos-15"}
        for os_name, text in self.texts.items():
            with self.subTest(os_name):
                found = jobs(text)
                self.assertEqual(list(found), ["inventory", "serial", "shards", "controls", "controls-check", "compare"])
                for name in ("serial", "shards", "controls"):
                    self.assertIn(f"runs-on: {runner[os_name]}\n", found[name])
                for name in ("inventory", "controls-check", "compare"):
                    self.assertIn("runs-on: ubuntu-24.04\n", found[name])
                self.assertIn(f"  OS_LABEL: {os_name}\n", text)

    def test_every_job_checks_out_and_asserts_the_pull_request_head(self):
        for os_name, text in self.texts.items():
            for name, job in jobs(text).items():
                with self.subTest(os_name=os_name, job=name):
                    self.assertIn("ref: ${{ github.event.pull_request.head.sha }}", job)
                    self.assertIn('if [ "$actual" != "$PR_HEAD_SHA" ]; then', job)
                    self.assertIn("persist-credentials: false", job)

    def test_the_serial_step_is_the_production_command(self):
        for os_name, text in self.texts.items():
            with self.subTest(os_name):
                serial = jobs(text)["serial"]
                self.assertIn('          python3 -m unittest -v > "$out/log.txt" 2>&1 || status=$?\n', serial)
                self.assertEqual(serial.count("python3 -m unittest"), 2)  # the command and its record
                self.assertIn("matrix:\n        repeat: [1, 2, 3]\n", serial)

    def group(self, job: str) -> str:
        return job.split("      - parallel:\n", 1)[1].split("\n      - ", 1)[0]

    def shard_steps(self, job: str) -> list:
        return re.split(r"(?m)^          - ", self.group(job))[1:]

    def test_the_shard_steps_follow_the_arm_table(self):
        limit = {"ubuntu-24.04": "25", "macos-15": "40"}
        for os_name, text in self.texts.items():
            with self.subTest(os_name):
                job = jobs(text)["shards"]
                steps = self.shard_steps(job)
                counts = {spec["shards"] for spec in make_shards.ARMS[os_name].values()}
                self.assertEqual(counts, {len(steps)})
                bodies = set()
                for index, step in enumerate(steps):
                    self.assertTrue(step.startswith(f"name: Shard {index}\n"), step[:40])
                    self.assertIn(f"timeout-minutes: {limit[os_name]}\n", step)
                    self.assertIn(f"SHARD: shard-{index}\n", step)
                    self.assertNotIn("if:", step)
                    bodies.add(step.split("run: |\n", 1)[1].rstrip("\n"))
                self.assertEqual(len(bodies), 1, "every shard step runs the same body")
                body = bodies.pop()
                self.assertIn('python3 -m unittest -v "${modules[@]}" > "$out/$SHARD.log" 2>&1 || status=$?', body)
                self.assertIn('exit "$status"', body)
                arms = re.findall(r"\{repeat: ([1-3]), arm: ([A-Z0-9]+)\}", job)
                self.assertEqual(sorted(arms), sorted((str(r), arm) for r in (1, 2, 3) for arm in make_shards.ARMS[os_name]))
                tail_arm = next(arm for arm, spec in make_shards.ARMS[os_name].items() if spec["tail"])
                self.assertIn(f"if: ${{{{ !cancelled() && matrix.arm == '{tail_arm}' && steps.start.outcome == 'success' }}}}",
                              job)
                self.assertIn(body.replace("\n              ", "\n          ").strip(), job.split("SHARD: tail\n", 1)[1])

    def test_no_step_inside_a_parallel_group_takes_an_expression_an_action_or_an_environment_write(self):
        # S1: zizmor's coverage inside parallel groups is experimental (README.md, "Limits"), so these stay out of them.
        for os_name, text in self.texts.items():
            for name in ("shards", "controls"):
                with self.subTest(os_name=os_name, job=name):
                    group = self.group(jobs(text)[name])
                    for forbidden in ("${{", "uses:", "GITHUB_ENV", "GITHUB_PATH", "if:"):
                        self.assertNotIn(forbidden, group)

    def test_the_finish_steps_record_the_step_outcomes(self):
        # E2 and E3: the clock-start, foreground and control steps carry ids, and every finish step records the steps
        # context, from which compare.py reads whether the test phase or the control group started.
        for os_name, text in self.texts.items():
            found = jobs(text)
            for name in ("serial", "shards", "controls"):
                with self.subTest(os_name=os_name, job=name):
                    self.assertEqual(found[name].count("STEPS_JSON: ${{ toJSON(steps) }}"), 1)
            for name in ("serial", "shards"):
                with self.subTest(os_name=os_name, job=name):
                    self.assertIn("      - name: Start the clock\n        id: start\n", found[name])
            with self.subTest(os_name=os_name, job="controls"):
                self.assertIn(f"        id: {compare.FOREGROUND_STEP}\n        run: python3 \"$TRIAL_DIR/record.py\" "
                              "probe \"$RUNNER_TEMP/results/$RUN_NAME\" foreground\n", found["controls"])
                self.assertEqual(re.findall(r"(?m)^            id: (\S+)$", self.group(found["controls"])),
                                 [spec["step"] for spec in compare.CONTROL_SHARDS])
                self.assertIn('--heartbeat "$RUNNER_TEMP/control-suite/test_ctl_hang.heartbeat"', found["controls"])

    def test_the_concurrency_limits(self):
        expected = {"ubuntu-24.04": "2", "macos-15": "1"}
        for os_name, text in self.texts.items():
            for name in ("serial", "shards"):
                with self.subTest(os_name=os_name, job=name):
                    self.assertIn(f"max-parallel: {expected[os_name]}\n", jobs(text)[name])
                    self.assertIn("fail-fast: false\n", jobs(text)[name])

    def test_every_macos_python_setup_pins_one_release_that_its_interpreter_check_asserts(self):
        # R4-1: an image rollout during a run can change the cached 3.13 patch release between jobs. An exact version
        # takes the same release in every job (from the tool cache, else a download), and each job's interpreter
        # check asserts it before the clock starts, so another release gives an unstarted run (incomplete). Linux
        # runs the image's system python3, compared across runs by compare.py.
        text = self.texts["macos-15"]
        self.assertEqual(re.findall(r"(?m)^ +python-version: '([^']*)'$", text), ["3.13.15"] * 4)
        self.assertEqual(re.findall(r"(?m)^ +check-latest: (\S+)$", text), ["false"] * 4)
        self.assertEqual(re.findall(r"sys\.version_info\[:[23]\] == \(([0-9, ]+)\)", text), ["3, 13, 15"] * 4)
        self.assertNotIn("python-version:", self.texts["ubuntu-24.04"])

    def test_the_control_job_matches_the_oracle(self):
        for os_name, text in self.texts.items():
            with self.subTest(os_name):
                job = jobs(text)["controls"]
                written = re.findall(r"printf '%s\\n' (test_ctl_[a-z]+) > \"\$out/shard-([0-9])\.txt\"", job)
                self.assertEqual(written, [(spec["module"], str(index)) for index, spec in enumerate(compare.CONTROL_SHARDS)])
                steps = self.shard_steps(job)
                self.assertEqual(len(steps), len(compare.CONTROL_SHARDS))
                self.assertEqual([re.search(r"timeout-minutes: ([0-9]+)", step).group(1) for step in steps],
                                 ["5", "5", "5", "1"])
                self.assertIn(f'echo "{compare.CONTROL_ENV_NAME}=1" >> "$GITHUB_ENV"', job)
                check = jobs(text)["controls-check"]
                self.assertIn("needs: controls\n    if: always()\n", check)
                self.assertIn("CONTROLS_RESULT: ${{ needs.controls.result }}", check)
                self.assertIn("pattern: controls\n          path: ${{ runner.temp }}/results/controls\n", check)
                self.assertIn('compare.py" controls --artifact "$RUNNER_TEMP/results/controls"', check)

    def test_artifacts_and_run_directories_match_the_oracle(self):
        for os_name, text in self.texts.items():
            with self.subTest(os_name):
                found = jobs(text)
                self.assertIn(f"RUN_NAME: {os_name}-S-r${{{{ matrix.repeat }}}}", found["serial"])
                self.assertIn(f"RUN_NAME: {os_name}-${{{{ matrix.arm }}}}-r${{{{ matrix.repeat }}}}", found["shards"])
                self.assertIn(f"RUN_NAME: {os_name}-controls", found["controls"])
                self.assertIn(f"name: {compare.ARM_ARTIFACT_PREFIX}{os_name}-S-r${{{{ matrix.repeat }}}}\n", found["serial"])
                self.assertIn(f"name: {compare.ARM_ARTIFACT_PREFIX}{os_name}-${{{{ matrix.arm }}}}-r${{{{ matrix.repeat }}}}\n",
                              found["shards"])
                self.assertIn(f"name: {compare.CONTROL_ARTIFACT}\n", found["controls"])
                self.assertTrue(compare.RUN_DIR_RE.match(f"{os_name}-S-r1"))
                uploads = text.count("uses: actions/upload-artifact@")
                self.assertEqual(uploads, 5)
                self.assertEqual(len(re.findall(r"(?m)^ +overwrite: false$", text)), uploads)
                self.assertEqual(len(re.findall(r"(?m)^ +retention-days: 30$", text)), uploads)
                compare_job = found["compare"]
                self.assertIn("needs: [inventory, serial, shards, controls, controls-check]\n    if: always()\n", compare_job)
                self.assertIn('python3 -m unittest discover -s "$TRIAL_DIR" -p "test_*.py" -v', compare_job)
                self.assertIn("NEEDS_JSON: ${{ toJSON(needs) }}", compare_job)
                self.assertIn('--run-attempt "$GITHUB_RUN_ATTEMPT"', compare_job)
                self.assertIn("name: compare\n", compare_job)
                # S2: the arm-runs are not merged; only the single inventory artifact is downloaded with merging.
                self.assertIn("pattern: arm-*\n          path: ${{ runner.temp }}/results\n", compare_job)
                self.assertIn("pattern: controls\n          path: ${{ runner.temp }}/results/controls\n", compare_job)
                self.assertEqual(text.count("merge-multiple"), 1)
                self.assertIn("pattern: inventory\n          merge-multiple: true\n", compare_job)


def normalized(text: str) -> str:
    """text with each line's leading whitespace and comment markers (#) removed and every run of whitespace one space."""
    return " ".join(" ".join(re.sub(r"^\s*#*", "", line) for line in text.splitlines()).split())


class ProtocolTextTests(unittest.TestCase):
    """The protocol (compare.PROTOCOL) reads word for word the same wherever it is stated."""

    def test_every_document_states_the_protocol_word_for_word(self):
        # Three review rounds each found a document that stated a rule differently from the others.
        record = json.loads((HERE / "experiment.json").read_text(encoding="utf-8"))
        documents = {"README.md": (HERE / "README.md").read_text(encoding="utf-8"),
                     "experiment.json quality_rule": record["predeclared_metrics"]["quality_rule"],
                     DECISION_RECORD.name: DECISION_RECORD.read_text(encoding="utf-8")}
        for path in WORKFLOWS.values():
            documents[f"{path.name} header"] = path.read_text(encoding="utf-8").split("\non:\n", 1)[0]
        self.assertEqual(len(compare.PROTOCOL), 7)
        for name, text in documents.items():
            text = normalized(text)
            for sentence in compare.PROTOCOL:
                with self.subTest(document=name, sentence=sentence[:48]):
                    self.assertIn(sentence, text)


if __name__ == "__main__":
    unittest.main()
