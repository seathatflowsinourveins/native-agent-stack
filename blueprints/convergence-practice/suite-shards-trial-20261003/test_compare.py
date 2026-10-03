"""Tests of the suite-shards trial's oracle, generator, inventory gate, recorder and workflows (stdlib only).

  python3 -m unittest discover -s blueprints/convergence-practice/suite-shards-trial-20261003 -p "test_*.py" -v

The run directories are built in temporary directories from fixtures/ (real local runs of a fixture suite and of
the controls, made by make_fixtures.py) with synthetic meta, runtime, timing and checkout files. blueprints/ is
not a package, so the repository's own suite never collects this file; the trial's compare jobs run it before
compare.py, fail-closed.
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

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import compare  # noqa: E402
import logparse  # noqa: E402
import make_fixtures  # noqa: E402
import make_shards  # noqa: E402

ROOT = HERE.parents[2]
FIXTURES = HERE / "fixtures"
INDEX = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))
FIXTURE_WEIGHTS = FIXTURES / "weights-fixture.json"
WORKFLOWS = {"ubuntu-24.04": ROOT / ".github/workflows/suite-shards-trial-linux.yml",
             "macos-15": ROOT / ".github/workflows/suite-shards-trial-macos.yml"}
OS = "ubuntu-24.04"
SHA = "0123456789abcdef0123456789abcdef01234567"
PYTHON = json.loads((FIXTURES / "controls/foreground.probe.json").read_text(encoding="utf-8"))["python_version"]
NEEDS = {"inventory": {"result": "success", "outputs": {}}, "serial": {"result": "failure", "outputs": {}},
         "shards": {"result": "failure", "outputs": {}}, "controls": {"result": "failure", "outputs": {}},
         "controls-check": {"result": "success", "outputs": {}}}
RUN_EXITS = {(item["arm"], item.get("list"), item.get("repeat")): item["exit_code"] for item in INDEX["runs"]}
CONTROL_EXITS = {item["module"]: item["exit_code"] for item in INDEX["controls"]}


def fixture(relative: str) -> str:
    return (FIXTURES / relative).read_text(encoding="utf-8")


def nanoseconds(seconds) -> int:
    value = Fraction(str(seconds)) * 10 ** 9
    assert value.denominator == 1
    return int(value)


class Tree:
    """A results tree and an inventory directory in a temporary directory, built from the fixtures."""

    def __init__(self, root: Path):
        self.results = root / "results"
        self.results.mkdir()
        self.inventory = root / "inventory"
        shutil.copytree(FIXTURES / "inventory", self.inventory)

    def common(self, directory: Path, arm: str, repeat: int, seconds, job_status="failure"):
        directory.mkdir(parents=True)
        (directory / "meta.json").write_text(json.dumps({
            "os": OS, "arm": arm, "repeat": repeat, "checkout_sha": SHA, "python_version": PYTHON,
            "platform": "fixture", "runner_image": "fixture", "job_status": job_status}))
        (directory / "runtime.json").write_text(json.dumps({"run_attempt": "1"}))
        if seconds is not None:
            ns = nanoseconds(seconds)
            (directory / "timing.json").write_text(json.dumps({"clock": "fixture", "step_ns": ns, "wall_ns": ns,
                                                                "problems": []}))
        (directory / "git-status.txt").write_text("")

    def serial(self, repeat: int, seconds=100, log: str | None = None):
        directory = self.results / f"{OS}-S-r{repeat}"
        self.common(directory, "S", repeat, seconds)
        (directory / "log.txt").write_text(log if log is not None else fixture(f"runs/S-r{repeat}.log"))
        (directory / "exit-code.txt").write_text(f"{RUN_EXITS[('S', None, repeat)]}\n")
        (directory / "command.txt").write_text("python3 -m unittest -v\n")
        return directory

    def sharded(self, arm: str, repeat: int, seconds=40):
        directory = self.results / f"{OS}-{arm}-r{repeat}"
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
        directory = self.results / f"{OS}-controls"
        self.common(directory, "controls", 1, None)
        shutil.copy(FIXTURES / "controls/foreground.probe.json", directory / "foreground.probe.json")
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
        return compare.build_result(self.results, self.inventory, SHA, OS, needs, weights=FIXTURE_WEIGHTS, **kwargs)


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
        done, _ = self.build({"tests/test_raises.py": "raise RuntimeError('planted')\n"})
        self.assertEqual(done.returncode, 1)


# --------------------------------------------------------------------------- record.py


class RecordTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "repo"
        self.repo.mkdir()
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        for args in (["init", "-q"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty",
                                      "-m", "t"]):
            subprocess.run(["git", *args], cwd=self.repo, env=environment, check=True)
        self.out = Path(tmp.name) / "out"
        self.env = dict(environment, GITHUB_RUN_ATTEMPT="1", JOB_STATUS="failure")

    def record(self, *args, **popen):
        return subprocess.run([sys.executable, str(HERE / "record.py"), *args], cwd=self.repo, env=self.env,
                              capture_output=True, text=True, check=True, **popen)

    def test_a_timed_run_directory(self):
        self.record("runtime", str(self.out))
        self.record("start", str(self.out))
        self.record("probe", str(self.out), "shard-0")
        self.record("finish", str(self.out), "--os", OS, "--arm", "G4", "--repeat", "2")
        timing = json.loads((self.out / "timing.json").read_text())
        meta = json.loads((self.out / "meta.json").read_text())
        self.assertEqual(compare.timing_problems(timing), [])
        self.assertEqual(json.loads((self.out / "runtime.json").read_text())["run_attempt"], "1")
        self.assertEqual((meta["os"], meta["arm"], meta["repeat"], meta["job_status"]), (OS, "G4", 2, "failure"))
        self.assertEqual(len(meta["checkout_sha"]), 40)
        self.assertEqual((self.out / "git-status.txt").read_text(), "")
        probe = json.loads((self.out / "shard-0.probe.json").read_text())
        self.assertEqual(set(probe["env_present"]), {
            compare.CONTROL_ENV_NAME, "CHILD_USAGE_SHELL_PARSER", "LANDSCAPE_SWEEP_SKILLS_YAML", "PROMOTION_GATE_PYTHON",
            "REQUIRE_PROMOTION_GATE_VENV", "GITHUB_ACTIONS", "CI"})
        self.assertTrue(all(isinstance(value, bool) for value in probe["env_present"].values()), "names only, no values")

    def test_finish_without_start_is_untimed_and_a_dirty_checkout_is_recorded(self):
        (self.repo / "untracked.txt").write_text("x")
        self.record("finish", str(self.out), "--os", OS, "--arm", "S", "--repeat", "1")
        timing = json.loads((self.out / "timing.json").read_text())
        self.assertIsNone(timing["step_ns"])
        self.assertTrue(compare.timing_problems(timing))
        self.assertEqual((self.out / "git-status.txt").read_text(), "?? untracked.txt\n")

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
        shard = self.tree.results / f"{OS}-G4-r2" / "shard-0.log"
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
        serial = self.tree.results / f"{OS}-S-r3" / "log.txt"
        self.edit(serial, "test_passes (tests.test_alpha.AlphaTests.test_passes) ... ok",
                  "test_passes (tests.test_alpha.AlphaTests.test_passes) ... skipped 'flaky'")
        self.edit(serial, "skipped=1, expected", "skipped=2, expected")
        verdict = self.verdict()
        self.assertEqual(verdict["baseline"]["flaky_ids"], ["tests.test_alpha.AlphaTests.test_passes"])
        self.assertEqual(verdict["outcome"], "adopt")

    def test_a_module_run_twice_or_never_is_ineligible(self):
        self.tree.full()
        run = self.tree.results / f"{OS}-G4-r1"
        shutil.copy(run / "shard-0.log", run / "shard-2.log")  # alpha twice, epsilon and the tail module never
        entry = self.run_entry(self.tree.result(), f"{OS}-G4-r1")
        self.assertFalse(entry["eligible"])
        self.assertEqual(entry["repeated_total"], 4)
        self.assertEqual(entry["missing_total"], 3)

    def test_the_command_must_be_the_shards_list(self):
        self.tree.full()
        command = self.tree.results / f"{OS}-G4T-r1" / "shard-3.command"
        command.write_text("python3 -m unittest -v tests.test_epsilon tests.test_delta\n")
        entry = self.run_entry(self.tree.result(), f"{OS}-G4T-r1")
        self.assertTrue(any("command" in reason for reason in entry["reasons"]), entry["reasons"])

    def test_the_serial_command_must_be_exact(self):
        self.tree.full()
        (self.tree.results / f"{OS}-S-r1" / "command.txt").write_text("python3 -X dev -m unittest -v\n")
        verdict = self.verdict()
        self.assertEqual(verdict["outcome"], "no verdict")

    def test_the_run_lists_must_be_the_inventory_lists(self):
        self.tree.full()
        (self.tree.results / f"{OS}-G4-r3" / "shard-0.txt").write_text("tests.test_beta\n")
        entry = self.run_entry(self.tree.result(), f"{OS}-G4-r3")
        self.assertIn("the run's shard lists are not the inventory artifact's lists for this arm", entry["reasons"])

    def test_an_exit_status_that_disagrees_with_the_status_line(self):
        self.tree.full()
        (self.tree.results / f"{OS}-G4-r1" / "shard-0.exit").write_text("1\n")
        entry = self.run_entry(self.tree.result(), f"{OS}-G4-r1")
        self.assertTrue(any("disagrees with the status line" in reason for reason in entry["reasons"]))

    def test_a_missing_shard_exit_status_is_ineligible(self):
        self.tree.full()
        (self.tree.results / f"{OS}-G4-r1" / "shard-1.exit").unlink()
        self.assertFalse(self.run_entry(self.tree.result(), f"{OS}-G4-r1")["eligible"])

    def test_checkout_attempt_and_head_rules(self):
        mutations = {
            "dirty": lambda d: (d / "git-status.txt").write_text("?? stray.txt\n"),
            "no status": lambda d: (d / "git-status.txt").unlink(),
            "status failed": lambda d: (d / "git-status.txt").write_text("git status failed\n"),
            "attempt 2": lambda d: (d / "runtime.json").write_text(json.dumps({"run_attempt": "2"})),
            "no runtime": lambda d: (d / "runtime.json").unlink(),
            "other head": lambda d: self.rewrite_meta(d, checkout_sha="f" * 40),
            "other python": lambda d: self.rewrite_meta(d, python_version="3.12.3"),
            "no timing": lambda d: (d / "timing.json").unlink(),
            "clocks disagree": lambda d: (d / "timing.json").write_text(json.dumps(
                {"step_ns": nanoseconds(40), "wall_ns": nanoseconds(60), "problems": []})),
        }
        for label, mutate in mutations.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(Path(tmp)).full()
                mutate(tree.results / f"{OS}-G4T-r2")
                result = tree.result()
                self.assertFalse(self.run_entry(result, f"{OS}-G4T-r2")["eligible"], label)
                self.assertFalse(result["verdicts"][OS]["arms"]["G4T"]["eligible"], label)

    def rewrite_meta(self, directory: Path, **fields):
        meta = json.loads((directory / "meta.json").read_text())
        meta.update(fields)
        (directory / "meta.json").write_text(json.dumps(meta))

    def test_a_background_step_on_another_interpreter_is_ineligible(self):
        self.tree.full()
        probe = self.tree.results / f"{OS}-G4-r1" / "shard-2.probe.json"
        data = json.loads(probe.read_text())
        data["python_version"] = "3.9.6"
        probe.write_text(json.dumps(data))
        entry = self.run_entry(self.tree.result(), f"{OS}-G4-r1")
        self.assertTrue(any("ran python '3.9.6'" in reason for reason in entry["reasons"]), entry["reasons"])

    def test_a_unittest_parallel_header_is_ineligible(self):
        self.tree.full()
        log = self.tree.results / f"{OS}-G4-r1" / "shard-0.log"
        log.write_text("Running 1 test suites (4 total tests) across 1 workers\n" + log.read_text())
        self.assertFalse(self.run_entry(self.tree.result(), f"{OS}-G4-r1")["eligible"])

    def test_a_serial_run_must_execute_the_inventory(self):
        self.tree.full()
        (self.tree.results / f"{OS}-S-r2" / "log.txt").write_text(fixture("runs/G4-shard-0.log"))
        result = self.tree.result()
        self.assertFalse(self.run_entry(result, f"{OS}-S-r2")["eligible"])
        self.assertEqual(self.verdict(result)["outcome"], "no verdict")

    def test_serial_runs_on_two_python_versions_give_no_verdict(self):
        self.tree.full()
        self.rewrite_meta(self.tree.results / f"{OS}-S-r3", python_version="3.12.3")
        self.assertEqual(self.verdict()["outcome"], "no verdict")

    def test_failed_controls_reject(self):
        self.tree.full()
        (self.tree.results / f"{OS}-controls" / "shard-2.exit").write_text("0\n")
        result = self.tree.result()
        self.assertFalse(result["controls"][OS]["passed"])
        self.assertEqual((self.verdict(result)["outcome"], self.verdict(result)["reasons"]),
                         ("reject", ["no sharded arm is eligible"]))

    def test_a_failed_controls_check_job_fails_the_controls(self):
        needs = json.loads(json.dumps(NEEDS))
        needs["controls-check"]["result"] = "failure"
        result = self.tree.full().result(needs=needs)
        self.assertFalse(result["controls"][OS]["passed"])
        self.assertEqual(self.verdict(result)["outcome"], "reject")

    def test_partial_and_cancelled_runs_are_incomplete_not_a_rule_outcome(self):
        cases = {
            "missing run directory": (lambda tree: shutil.rmtree(tree.results / f"{OS}-G4T-r3"), NEEDS),
            "cancelled job status": (lambda tree: self.rewrite_meta(tree.results / f"{OS}-S-r1", job_status="cancelled"),
                                     NEEDS),
            "cancelled job": (lambda tree: None, {**NEEDS, "shards": {"result": "cancelled"}}),
            "skipped job": (lambda tree: None, {**NEEDS, "serial": {"result": "skipped"}}),
            "no control run": (lambda tree: shutil.rmtree(tree.results / f"{OS}-controls"), NEEDS),
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
        self.assertIn("no run directory", verdict["reasons"][0])

    def test_a_failed_inventory_gate_gives_no_verdict(self):
        needs = {**NEEDS, "inventory": {"result": "failure"}, "serial": {"result": "skipped"},
                 "shards": {"result": "skipped"}}
        self.assertEqual(self.verdict(self.tree.result(needs=needs))["outcome"], "no verdict")

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
        self.assertEqual(other["outcome"], "no verdict")
        self.assertIn("no run directory", other["reasons"][0])

    def test_the_cli_writes_the_three_outputs(self):
        self.tree.full()
        needs = self.tree.results.parent / "needs.json"
        needs.write_text(json.dumps(NEEDS))
        out = self.tree.results.parent
        with contextlib.redirect_stdout(io.StringIO()):
            code = compare.main(["verdict", "--results", str(self.tree.results), "--inventory", str(self.tree.inventory),
                                 "--expected-sha", SHA, "--os", OS, "--needs", str(needs),
                                 "--out", str(out / "result.json"), "--summary-md", str(out / "summary.md"),
                                 "--checkout-status", str(out / "checkout-status.json"), "--skip-list-recompute"])
        self.assertEqual(code, 0)
        result = json.loads((out / "result.json").read_text())
        self.assertEqual(result["verdicts"][OS]["outcome"], "adopt")
        self.assertFalse(result["inputs"]["inventory"]["lists_recomputed"])
        self.assertIn("**ubuntu-24.04**: adopt G4", (out / "summary.md").read_text())
        status = json.loads((out / "checkout-status.json").read_text())
        self.assertTrue(status["ok"])
        self.assertEqual(len(status["runs"]), 10)


# --------------------------------------------------------------------------- compare.py: the controls


class ControlTests(TreeCase):
    def setUp(self):
        super().setUp()
        self.directory = self.tree.controls()

    def check(self, job_result="failure"):
        return compare.check_controls(self.directory, OS, job_result, SHA)

    def test_the_real_control_runs_pass(self):
        report = self.check()
        self.assertTrue(report["passed"], report["problems"])
        self.assertEqual([item["exit_code"] for item in report["shards"]], [0, 1, 3, None])
        self.assertFalse(report["background_ignores_sigquit"])

    def test_the_control_job_must_fail(self):
        self.assertFalse(self.check("success")["passed"])
        self.assertFalse(self.check(None)["passed"])

    def test_each_expectation_is_checked(self):
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
        }
        for label, mutate in mutations.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                directory = Tree(Path(tmp)).controls()
                mutate(directory)
                self.assertFalse(compare.check_controls(directory, OS, "failure", SHA)["passed"], label)

    def probe(self, directory: Path, label: str, env=True, python=None):
        path = directory / f"{label}.probe.json"
        data = json.loads(path.read_text())
        data["env_present"][compare.CONTROL_ENV_NAME] = env
        if python:
            data["python_version"] = python
        path.write_text(json.dumps(data))

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
            self.assertEqual(compare.main(["controls", "--dir", str(self.directory), "--os", OS,
                                           "--job-result", "failure", "--expected-sha", SHA]), 0)
            self.assertEqual(compare.main(["controls", "--dir", str(self.directory), "--os", OS,
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

    def shard_steps(self, job: str) -> list:
        group = job.split("      - parallel:\n", 1)[1].split("\n      - ", 1)[0]
        return re.split(r"(?m)^          - ", group)[1:]

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
                    self.assertNotIn("${{", step)
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

    def test_the_concurrency_limits(self):
        expected = {"ubuntu-24.04": "2", "macos-15": "1"}
        for os_name, text in self.texts.items():
            for name in ("serial", "shards"):
                with self.subTest(os_name=os_name, job=name):
                    self.assertIn(f"max-parallel: {expected[os_name]}\n", jobs(text)[name])
                    self.assertIn("fail-fast: false\n", jobs(text)[name])

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

    def test_artifacts_and_run_directories_match_the_oracle(self):
        for os_name, text in self.texts.items():
            with self.subTest(os_name):
                found = jobs(text)
                self.assertIn(f"RUN_NAME: {os_name}-S-r${{{{ matrix.repeat }}}}", found["serial"])
                self.assertIn(f"RUN_NAME: {os_name}-${{{{ matrix.arm }}}}-r${{{{ matrix.repeat }}}}", found["shards"])
                self.assertIn(f"RUN_NAME: {os_name}-controls", found["controls"])
                for name in ("serial", "shards"):
                    self.assertTrue(compare.RUN_DIR_RE.match(f"{os_name}-S-r1"))
                    self.assertIn(f"name: arm-{os_name}-", found[name])
                uploads = text.count("uses: actions/upload-artifact@")
                self.assertEqual(uploads, 5)
                self.assertEqual(len(re.findall(r"(?m)^ +overwrite: false$", text)), uploads)
                self.assertEqual(len(re.findall(r"(?m)^ +retention-days: 30$", text)), uploads)
                compare_job = found["compare"]
                self.assertIn("needs: [inventory, serial, shards, controls, controls-check]\n    if: always()\n", compare_job)
                self.assertIn('python3 -m unittest discover -s "$TRIAL_DIR" -p "test_*.py" -v', compare_job)
                self.assertIn("NEEDS_JSON: ${{ toJSON(needs) }}", compare_job)
                self.assertIn("name: compare\n", compare_job)


if __name__ == "__main__":
    unittest.main()
