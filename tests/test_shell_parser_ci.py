"""Tripwire and structure checks for the pinned tree-sitter-bash parser on CI (PR-A unit U1d).

examples/claude-native/workflows/child-usage.mjs reads command position with tree-sitter-bash and fails closed
without a verified install: cli_lanes is "parser_unavailable" and the lane tests skip. Nothing installed the
parser on CI, so the required validate job passed while it exercised only that fail-closed gate. validate.yml now
installs the parser with the command in examples/claude-native/workflows/shell-parser.pin.json. This module keeps
that true. A GitHub Actions job (GITHUB_ACTIONS=true) fails when the loader does not report the pinned, hash-verified
install, and the suite fails when the provisioning step is dropped, moved after the suite, retyped away from the pin,
no longer exports the directory, or can be skipped.

Every Actions job is held to that runtime tripwire except the recorded gaps. Two other jobs run the whole suite under
GITHUB_ACTIONS=true without installing the parser: adoption-bootstrap.yml validate-macos (a required check in
.github/main-ruleset.json) and catalog-freshness.yml freshness. Holding them to the tripwire would fail both, and
those workflows are outside this unit's owned paths, so KNOWN_UNPROVISIONED records them and the tripwire skips there
and says so. A job that is not listed fails closed, as does an Actions environment that names no job. A whole-suite
job that neither provisions nor is listed there fails the suite, so the list can only shrink.

Rules and their sources (read 2026-09-29):
- GITHUB_ACTIONS is always "true" in Actions, GITHUB_JOB is the job id and GITHUB_WORKFLOW_REF is
  owner/repo/.github/workflows/<file>@<ref>: github/docs@f4e8afc6979acd8de6b5da035066281b9a5f4025,
  content/actions/reference/workflows-and-actions/variables.md lines 36, 50 and 70 (line 70 names
  data/reusables/actions/workflow-ref-description.md).
- A variable written to the GITHUB_ENV file reaches the later steps of the job, not the writing step: the same
  commit, content/actions/reference/workflows-and-actions/workflow-commands.md line 652.
- `npm install --ignore-scripts` runs no package script and `--prefix` makes a non-global command run in that
  folder: npm/cli@dd3c80e9965d240957684e9951603cf22eaae74c (v10.9.8, the ubuntu-24.04 image's npm),
  workspaces/config/lib/definitions/definitions.js lines 863 and 1521-1522.
- The runner: actions/runner-images@7ef9dd0112f1827264dbca2dff8b13eb9f1a5534, images/ubuntu/Ubuntu2404-Readme.md
  lines 11, 26, 28 and 37 (image 20260920.314.1: Node.js 22.23.2, Python 3.12.3, npm 10.9.8).
- The sibling contract for a provisioned venv: tests/test_promotion_gate.py, WorkflowProvisioningContract.

Failure messages are fixed strings and reason codes: no assertion here prints a child process's output, a path or the
text of a command.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

from tests.test_workflow_hardening import jobs, runs_whole_suite, uncommented, unittest_invocations

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
VALIDATE_YML = WORKFLOWS / "validate.yml"
HANDBOOK = ROOT / "docs/token-session-handbook.md"
PIN_PATH = "examples/claude-native/workflows/shell-parser.pin.json"
KERNEL = ROOT / "examples/claude-native/workflows/child-usage.mjs"
ENV_NAME = "CHILD_USAGE_SHELL_PARSER"
# The one job that provisions the parser today, and so the one job whose provisioning step this module inspects.
PROVISIONING_WORKFLOW = "validate.yml"
PROVISIONING_JOB = "validate"
# Whole-suite jobs that do not provision the parser yet: adoption-bootstrap.yml runs the suite on macOS in its
# validate-macos job (step "Run the full test suite (gating on macOS)"; the job is a required check in
# .github/main-ruleset.json) and catalog-freshness.yml runs it weekly in its freshness job (step "Run project test
# suite"). Their lane tests skip today, and the runtime tripwire skips in exactly these jobs and says so. Provision
# the job in its own workflow, then delete its entry:
# test_every_whole_suite_job_provisions_the_parser_or_is_a_recorded_gap fails while an entry is stale.
KNOWN_UNPROVISIONED = {"adoption-bootstrap.yml:validate-macos", "catalog-freshness.yml:freshness"}
# The read-only check the handbook gives a host, run from the repository root.
CHECK_PREFIX = "node --input-type=module -e "
TRIPWIRE = "tests.test_shell_parser_ci.ShellParserInstalledInCI"


def load_pin():
    return json.loads((ROOT / PIN_PATH).read_text(encoding="utf-8"))


def pinned_record(pin=None):
    """The versions and wasm sha256 values that a verified load reports (child-usage.mjs loadShellParser)."""
    pin = pin or load_pin()
    return {"versions": {"tree_sitter_bash": pin["packages"]["tree-sitter-bash"]["version"],
                         "web_tree_sitter": pin["packages"]["web-tree-sitter"]["version"]},
            "wasm_sha256": {"tree_sitter_bash": pin["files"]["node_modules/tree-sitter-bash/tree-sitter-bash.wasm"],
                            "web_tree_sitter": pin["files"]["node_modules/web-tree-sitter/web-tree-sitter.wasm"]}}


def workflow_file(ref):
    """The file name in a GITHUB_WORKFLOW_REF value (owner/repo/.github/workflows/<file>@<ref>); '' when it has none."""
    _, found, tail = ref.partition("/.github/workflows/")
    return tail.partition("@")[0] if found else ""


def job_key(env):
    """'<workflow file>:<job id>' of the Actions job that `env` describes (an empty part for an unset variable)."""
    return f"{workflow_file(env.get('GITHUB_WORKFLOW_REF', ''))}:{env.get('GITHUB_JOB', '')}"


def stand_down(env):
    """None when the loader must report the pinned install in a process with `env`; otherwise why the tripwire does not
    apply: outside GitHub Actions, or in a job recorded in KNOWN_UNPROVISIONED. Anything else fails closed, including an
    Actions environment that names no job."""
    if env.get("GITHUB_ACTIONS") != "true":
        return "not in GitHub Actions (GITHUB_ACTIONS is not 'true')"
    if job_key(env) in KNOWN_UNPROVISIONED:
        return "a recorded gap: this job runs the whole suite without installing the parser (KNOWN_UNPROVISIONED)"
    return None


# The kernel's URL goes into the script text, not into argv: child-usage.mjs runs its command line when process.argv[1]
# is its own path.
PROBE = ("const kernel = await import(%s);"
         "await kernel.loadShellParser();"
         "process.stdout.write(JSON.stringify(kernel.shellParserStatus()));") % json.dumps(KERNEL.as_uri())


def loader_status(env):
    """What loadShellParser() reports in a node process with `env`: the kernel's own record ({ok, versions,
    wasm_sha256} or {ok: false, reason}), which carries no path, or a probe_failed / node_missing reason."""
    node = shutil.which("node", path=env.get("PATH"))
    if node is None:
        return {"ok": False, "reason": "node_missing"}
    try:
        done = subprocess.run([node, "--input-type=module", "-e", PROBE], env=env,
                              capture_output=True, text=True, timeout=120, check=False)
        record = json.loads(done.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {"ok": False, "reason": "probe_failed"}
    return record if isinstance(record, dict) else {"ok": False, "reason": "probe_failed"}


def verified(status):
    """True when the loader reports a successful load of exactly the pinned versions and wasm hashes (extra fields
    the kernel may add to its record are not compared)."""
    return status.get("ok") is True and all(status.get(key) == value for key, value in pinned_record().items())


def describe(status):
    """A path-free reason for a status that is not the verified record."""
    if status.get("ok") is True:
        return "the loader's record differs from the pin"
    reason = status.get("reason")
    return f"reason={reason}" if isinstance(reason, str) and reason.isidentifier() else "reason=unrecognized"


def simulated_ci_env(home, drop=(), **extra):
    """The environment of the validate job as far as the tripwire reads it, over a clean host: no inherited GITHUB_ or
    CHILD_USAGE_ variable, HOME set to an empty directory so that no host install is found by default."""
    env = {key: value for key, value in os.environ.items() if not key.startswith(("GITHUB_", "CHILD_USAGE_"))}
    env.update({"GITHUB_ACTIONS": "true", "GITHUB_JOB": PROVISIONING_JOB, "HOME": str(home),
                "GITHUB_WORKFLOW_REF": f"owner/repo/.github/workflows/{PROVISIONING_WORKFLOW}@refs/pull/1/merge"})
    env.update(extra)
    for key in drop:
        env.pop(key, None)
    return env


def host_install():
    """The verified install on this host (CHILD_USAGE_SHELL_PARSER, else the pin's default directory under HOME), or None."""
    if not shutil.which("node"):
        return None
    candidate = Path(os.environ.get(ENV_NAME) or Path.home() / load_pin()["install"]["default_directory"])
    with tempfile.TemporaryDirectory() as home:
        return candidate if verified(loader_status(simulated_ci_env(home, **{ENV_NAME: str(candidate)}))) else None


class ShellParserInstalledInCI(unittest.TestCase):
    """The runtime tripwire. It skips outside GitHub Actions and in the recorded gaps, and fails everywhere else."""

    def test_a_github_actions_job_has_the_verified_parser(self):
        reason = stand_down(os.environ)
        if reason is not None:
            self.skipTest(reason)
        status = loader_status(dict(os.environ))
        if not verified(status):
            self.fail(f"this GitHub Actions job has no verified tree-sitter-bash install ({describe(status)}): the lane "
                      "tests would skip; a step that installs the pin must run before the suite, as validate.yml's "
                      "does, or the job must be a recorded gap")


class TripwireControls(unittest.TestCase):
    """Mutation controls: the tripwire is run in each environment a job can present (the validate job's, GITHUB_ACTIONS
    alone and an unlisted job over a clean host) and must fail on each way the install can be missing or wrong. A
    control that always failed would prove nothing, so the verified install, the recorded gaps and a local run are also
    run."""

    @classmethod
    def setUpClass(cls):
        cls.install = host_install()

    def run_tripwire(self, home, drop=(), **extra):
        return subprocess.run([sys.executable, "-m", "unittest", "-v", TRIPWIRE], cwd=ROOT, capture_output=True,
                              text=True, timeout=300, check=False, env=simulated_ci_env(home, drop, **extra))

    def assert_failed(self, done, reason):
        self.assertEqual(done.returncode, 1, f"the tripwire did not fail (exit {done.returncode})")
        self.assertTrue("FAILED (failures=1)" in done.stderr, "the tripwire run did not report exactly one failure")
        self.assertTrue(f"reason={reason}" in done.stderr, f"the tripwire run did not report reason={reason}")
        self.assertFalse("skipped" in done.stderr, "the tripwire run skipped instead of failing")

    def assert_skipped(self, done, why):
        self.assertEqual(done.returncode, 0, f"the tripwire run exited {done.returncode}, not 0")
        self.assertTrue("skipped" in done.stderr, "the tripwire run did not skip")
        self.assertTrue(why in done.stderr, f"the tripwire run did not give the reason '{why}' for skipping")

    def copy_install(self, scratch):
        copy = Path(scratch) / "copy"
        for rel in [*load_pin()["files"], "package-lock.json"]:
            (copy / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.install / rel, copy / rel)
        return copy

    # GITHUB_ACTIONS=true and nothing else that names a job: the condition the brief gives for the tripwire.
    BARE = ("GITHUB_JOB", "GITHUB_WORKFLOW_REF")

    def flipped_wasm_fails(self, drop=()):
        if self.install is None:
            self.skipTest("no verified tree-sitter-bash install on this host to copy (CHILD_USAGE_SHELL_PARSER or the pin's default directory)")
        with tempfile.TemporaryDirectory() as scratch:
            copy = self.copy_install(scratch)
            unflipped = self.run_tripwire(scratch, drop, **{ENV_NAME: str(copy)})
            self.assertEqual(unflipped.returncode, 0, "the unflipped scratch copy must pass, or the flip proves nothing")
            self.assertFalse("skipped" in unflipped.stderr, "the unflipped scratch copy skipped, or the flip proves nothing")
            wasm = copy / "node_modules/tree-sitter-bash/tree-sitter-bash.wasm"
            data = bytearray(wasm.read_bytes())
            data[len(data) >> 1] ^= 1  # bit 0 of the middle byte: the same length, so only the hash can tell
            wasm.write_bytes(bytes(data))
            self.assert_failed(self.run_tripwire(scratch, drop, **{ENV_NAME: str(copy)}), "hash_mismatch")

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_no_install_anywhere_fails_the_tripwire(self):
        # CI before the provisioning step: no environment variable, and no install under HOME.
        with tempfile.TemporaryDirectory() as home:
            self.assert_failed(self.run_tripwire(home), "not_installed")

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_a_nonexistent_directory_fails_the_tripwire(self):
        with tempfile.TemporaryDirectory() as home:
            self.assert_failed(self.run_tripwire(home, **{ENV_NAME: str(Path(home) / "absent")}), "not_installed")

    def test_a_one_bit_flipped_wasm_fails_the_tripwire(self):
        self.flipped_wasm_fails()

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_actions_alone_with_no_install_fails_the_tripwire(self):
        with tempfile.TemporaryDirectory() as home:
            self.assert_failed(self.run_tripwire(home, self.BARE), "not_installed")

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_actions_alone_with_a_nonexistent_directory_fails_the_tripwire(self):
        with tempfile.TemporaryDirectory() as home:
            self.assert_failed(self.run_tripwire(home, self.BARE, **{ENV_NAME: str(Path(home) / "absent")}), "not_installed")

    def test_actions_alone_with_a_one_bit_flipped_wasm_fails_the_tripwire(self):
        self.flipped_wasm_fails(self.BARE)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_an_unlisted_job_fails_the_tripwire(self):
        # Fail closed: only a recorded gap is exempt, so a job that is not one of them needs the install even when its
        # name is a gap's name in another workflow, or its workflow reference is missing.
        unlisted = {"another job of the validate workflow": {"GITHUB_JOB": "another-job"},
                    "the validate job's name in another workflow": {"GITHUB_WORKFLOW_REF": "owner/repo/.github/workflows/other.yml@refs/heads/main"},
                    "a gap's job name in the validate workflow": {"GITHUB_JOB": "validate-macos"},
                    "a gap's job name with no workflow reference": {"GITHUB_JOB": "validate-macos", "GITHUB_WORKFLOW_REF": ""}}
        for label, extra in unlisted.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as home:
                self.assert_failed(self.run_tripwire(home, **extra), "not_installed")

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_a_recorded_gap_skips_and_says_so(self):
        for key in sorted(KNOWN_UNPROVISIONED):
            workflow, _, job = key.partition(":")
            extra = {"GITHUB_JOB": job, "GITHUB_WORKFLOW_REF": f"owner/repo/.github/workflows/{workflow}@refs/heads/main"}
            with self.subTest(key), tempfile.TemporaryDirectory() as home:
                self.assert_skipped(self.run_tripwire(home, **extra), "a recorded gap")

    def test_the_verified_install_passes_the_tripwire_without_skipping(self):
        if self.install is None:
            self.skipTest("no verified tree-sitter-bash install on this host (CHILD_USAGE_SHELL_PARSER or the pin's default directory)")
        with tempfile.TemporaryDirectory() as home:
            done = self.run_tripwire(home, **{ENV_NAME: str(self.install)})
        self.assertEqual(done.returncode, 0, f"the tripwire failed (exit {done.returncode})")
        self.assertTrue("OK" in done.stderr, "the tripwire run did not report OK")
        self.assertFalse("skipped" in done.stderr, "the tripwire run skipped instead of running")

    def test_runs_outside_actions_skip_with_a_message(self):
        outside = {"GITHUB_ACTIONS is false": ((), {"GITHUB_ACTIONS": "false"}),
                   "GITHUB_ACTIONS is not 'true'": ((), {"GITHUB_ACTIONS": "1"}),
                   "GITHUB_ACTIONS is unset": (("GITHUB_ACTIONS",), {})}
        for label, (drop, extra) in outside.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as home:
                self.assert_skipped(self.run_tripwire(home, drop, **extra), "not in GitHub Actions")


def step_blocks(job_text):
    """A job's steps as text blocks: a step starts at a line indented six spaces that begins with '- '."""
    steps, current = [], None
    for line in job_text.split("\n    steps:\n", 1)[-1].splitlines():
        if line.startswith("      - "):
            current = [line]
            steps.append(current)
        elif current is not None:
            current.append(line)
    return ["\n".join(step) for step in steps]


def runs_suite(step):
    return any(runs_whole_suite(args) for args in unittest_invocations(uncommented(step)))


def provisioning_indexes(steps):
    return [index for index, step in enumerate(steps) if PIN_PATH in uncommented(step)]


def mentions(step, key):
    return f'"{key}"' in step or f"'{key}'" in step


CATEGORIES = ("missing", "order", "derived", "export", "enforced")


def provisioning_problems(text):
    """(category, message) for each way the validate job's provisioning departs from what this module requires. With
    no single provisioning step to inspect, every category is reported: nothing passes by having nothing to check."""
    job = jobs(text).get(PROVISIONING_JOB)
    found = provisioning_indexes(step_blocks(job)) if job is not None else []
    if len(found) != 1:
        reason = f"no {PROVISIONING_JOB} job" if job is None else f"expected one step that reads the pin file, found {len(found)}"
        return [(category, reason) for category in CATEGORIES]
    steps = step_blocks(job)
    step = uncommented(steps[found[0]])
    problems = []
    suite = [index for index, other in enumerate(steps) if runs_suite(other)]
    if not suite:
        problems.append(("order", "no step runs the whole suite"))
    elif found[0] >= suite[0]:
        problems.append(("order", "the provisioning step does not come before the step that runs the whole suite"))
    pin = load_pin()
    for key in ("install", "command", "default_directory"):
        if not mentions(step, key):
            problems.append(("derived", f"the step does not read {key} from the pin"))
    retyped = [f"{name}@{package['version']}" for name, package in pin["packages"].items()]
    retyped += [package["version"] for package in pin["packages"].values()] + ["--ignore-scripts", "--save-exact"]
    problems += [("derived", "the step retypes part of the pinned command") for token in retyped if token in step][:1]
    if ENV_NAME not in step or "GITHUB_ENV" not in step:
        problems.append(("export", f"the step does not write {ENV_NAME} to the GITHUB_ENV file"))
    lines = step.splitlines()
    if "continue-on-error" in step:
        problems.append(("enforced", "the step continues on error"))
    if any(line.startswith(("        if:", "      - if:")) for line in lines):
        problems.append(("enforced", "the step has a condition, so some events would skip the install"))
    if "${{" in step:
        problems.append(("enforced", "the step expands an expression inside its script"))
    return problems


def categories(text):
    return {category for category, _ in provisioning_problems(text)}


def step_span(lines, index):
    """The [start, end) line range of the step that contains line `index`."""
    start = next(i for i in range(index, -1, -1) if lines[i].startswith("      - "))
    end = next((i for i in range(index + 1, len(lines)) if lines[i].startswith("      - ")), len(lines))
    return start, end


def provisioning_span(lines):
    index = next((i for i, line in enumerate(lines) if PIN_PATH in line and not line.lstrip().startswith("#")), None)
    if index is None:
        raise AssertionError("no step of the workflow reads the pin file: there is no provisioning step to inspect")
    return step_span(lines, index)


def run_script(step):
    """The `run: |` script of a step, dedented as YAML does (the runner writes it to a file and runs it)."""
    lines = step.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("        run: |"))
    body = []
    for line in lines[start + 1:]:
        if line.strip() and not line.startswith("          "):
            break
        body.append(line[10:])
    return "\n".join(body).rstrip("\n") + "\n"


class ProvisioningStepTests(unittest.TestCase):
    text = VALIDATE_YML.read_text(encoding="utf-8")

    def assertClean(self, category):
        self.assertEqual([message for found, message in provisioning_problems(self.text) if found == category], [])

    def test_provisioning_step_exists_in_the_validate_job(self):
        self.assertClean("missing")

    def test_provisioning_step_precedes_the_unittest_step(self):
        self.assertClean("order")

    def test_step_command_is_derived_from_the_pin_file(self):
        self.assertClean("derived")

    def test_step_exports_the_directory_through_github_env(self):
        self.assertClean("export")

    def test_step_cannot_be_skipped_or_ignored(self):
        self.assertClean("enforced")

    def test_the_provisioning_job_is_the_job_that_runs_the_suite(self):
        # The structure checks inspect this job by name: renaming it must not leave them with nothing to inspect.
        job = jobs(self.text).get(PROVISIONING_JOB)
        self.assertTrue(job is not None, "validate.yml has no job named as the tripwire expects")
        self.assertTrue(any(runs_suite(step) for step in step_blocks(job)), "that job does not run the whole suite")

    def test_every_whole_suite_job_provisions_the_parser_or_is_a_recorded_gap(self):
        provisioning, without = set(), set()
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for job_id, job_text in jobs(path.read_text(encoding="utf-8")).items():
                if any(runs_whole_suite(args) for args in unittest_invocations(job_text)):
                    steps = step_blocks(job_text)
                    (provisioning if provisioning_indexes(steps) else without).add(f"{path.name}:{job_id}")
        self.assertEqual(provisioning, {f"{PROVISIONING_WORKFLOW}:{PROVISIONING_JOB}"},
                         "the jobs that provision the parser: a job renamed or a second one added needs the tripwire's keys updated")
        self.assertEqual(without, KNOWN_UNPROVISIONED,
                         "whole-suite jobs without the parser: provision a new one, or delete the entry of a job that now does")


class ProvisioningControls(unittest.TestCase):
    """Mutation controls for the structure checks: each mutant is the real workflow with one defect, and must be
    reported in its category (and the real workflow in none of them)."""

    text = VALIDATE_YML.read_text(encoding="utf-8")

    def mutants(self):
        lines = self.text.split("\n")
        start, end = provisioning_span(lines)
        step = lines[start:end]
        pin = load_pin()
        package = next(iter(pin["packages"]))
        pinned = f"{package}@{pin['packages'][package]['version']}"
        run_index = next(i for i, line in enumerate(step) if line.startswith("        run: |"))
        suite_end = step_span(lines, next(i for i, line in enumerate(lines) if line.strip() == "run: python3 -m unittest"))[1]
        return {
            "removed step": ("missing", "\n".join(lines[:start] + lines[end:])),
            "step after the suite": ("order", "\n".join(lines[:start] + lines[end:suite_end] + step + lines[suite_end:])),
            "command retyped": ("derived", "\n".join(lines[:start + run_index + 1] + [f'          echo "{pinned}"'] + lines[start + run_index + 1:])),
            "export dropped": ("export", "\n".join(lines[:start] + [line.replace(ENV_NAME, "SHELL_PARSER_DIR") for line in step] + lines[end:])),
            "continues on error": ("enforced", "\n".join(lines[:start + 1] + ["        continue-on-error: true"] + lines[start + 1:])),
            "conditional": ("enforced", "\n".join(lines[:start + 1] + ["        if: github.event_name == 'push'"] + lines[start + 1:])),
            "expression in the script": ("enforced", "\n".join(lines[:start + run_index + 1] + ["          echo ${{ github.sha }}"] + lines[start + run_index + 1:])),
        }

    def test_each_mutant_is_reported_in_its_category(self):
        self.assertEqual(provisioning_problems(self.text), [])
        for label, (category, mutant) in self.mutants().items():
            with self.subTest(label):
                self.assertTrue(mutant != self.text, "the mutation must apply")
                self.assertIn(category, categories(mutant))

    def test_a_scratch_copy_of_the_workflow_without_the_step_fails_the_structure_tests(self):
        with tempfile.TemporaryDirectory() as scratch:
            copy = Path(scratch) / "validate.yml"
            copy.write_text(self.mutants()["removed step"][1], encoding="utf-8")
            problems = provisioning_problems(copy.read_text(encoding="utf-8"))
        self.assertEqual({category for category, _ in problems}, set(CATEGORIES))


SUITE_STEP = "      - name: Run the suite\n        run: python3 -m unittest\n"
PIN_STEP = f"      - name: Install the parser\n        run: cat {PIN_PATH}\n"
OTHER_STEP = "      - name: Something else\n        run: echo done\n"


def synthetic_workflow(**steps_by_job):
    """A minimal workflow with one job per keyword, each holding the given step text."""
    return "name: synthetic\n\njobs:\n" + "".join(
        f"  {job}:\n    runs-on: ubuntu-24.04\n    steps:\n{steps}" for job, steps in steps_by_job.items())


def with_step(text, job_id, step_lines):
    """`text` with the given step inserted before the first step of job `job_id` that runs the whole suite."""
    lines = text.split("\n")
    for index in range(next(i for i, line in enumerate(lines) if line == f"  {job_id}:"), len(lines)):
        if lines[index].startswith("      - "):
            start, end = step_span(lines, index)
            if runs_suite("\n".join(lines[start:end])):
                return "\n".join(lines[:start] + step_lines + lines[start:])
    raise AssertionError("the job has no step that runs the whole suite")


class RatchetControls(unittest.TestCase):
    """The ratchet over whole-suite jobs on synthetic workflows: each way a job can lack the parser is reported in its
    own category, and deleting a recorded gap that now provisions is all it takes to clear it."""

    PROVISIONED = {PROVISIONING_WORKFLOW: synthetic_workflow(**{PROVISIONING_JOB: PIN_STEP + SUITE_STEP})}

    def categories(self, texts, gaps):
        return [category for category, _ in ratchet_problems(texts, gaps)]

    def test_a_provisioned_job_and_a_recorded_gap_pass(self):
        texts = {**self.PROVISIONED, "gap.yml": synthetic_workflow(build=SUITE_STEP)}
        self.assertEqual(ratchet_problems(texts, {"gap.yml:build"}), [])

    def test_an_unlisted_whole_suite_job_without_the_parser_is_reported_by_name(self):
        texts = {**self.PROVISIONED, "new.yml": synthetic_workflow(build=SUITE_STEP)}
        problems = ratchet_problems(texts, set())
        self.assertEqual([category for category, _ in problems], ["unlisted"])
        self.assertTrue("new.yml:build" in problems[0][1], "the report does not name the job")

    def test_a_recorded_gap_that_now_provisions_is_stale_and_deleting_it_clears_the_ratchet(self):
        texts = {**self.PROVISIONED, "gap.yml": synthetic_workflow(build=PIN_STEP + SUITE_STEP)}
        problems = ratchet_problems(texts, {"gap.yml:build"})
        self.assertEqual([category for category, _ in problems], ["stale"])
        self.assertTrue("gap.yml:build" in problems[0][1], "the report does not name the entry")
        self.assertEqual(ratchet_problems(texts, set()), [])

    def test_a_recorded_gap_that_no_longer_runs_the_suite_or_is_gone_is_stale(self):
        quiet = {**self.PROVISIONED, "gap.yml": synthetic_workflow(build=OTHER_STEP)}
        self.assertEqual(self.categories(quiet, {"gap.yml:build"}), ["stale"])
        self.assertEqual(self.categories(self.PROVISIONED, {"gone.yml:build"}), ["stale"])

    def test_the_validate_job_must_provision_and_cannot_be_listed_as_a_gap(self):
        bare = {PROVISIONING_WORKFLOW: synthetic_workflow(**{PROVISIONING_JOB: SUITE_STEP})}
        self.assertEqual(self.categories(bare, set()), ["unlisted", "required"])
        self.assertEqual(self.categories(bare, {PROVISIONING_KEY}), ["required"])
        self.assertEqual(self.categories({}, set()), ["required"])


class RealRatchetControls(unittest.TestCase):
    """The same ratchet on this repository's workflows with one defect each, including the remediation the comment above
    KNOWN_UNPROVISIONED gives: provision a recorded-gap job, then delete its entry."""

    @classmethod
    def setUpClass(cls):
        cls.texts = workflow_texts()
        lines = cls.texts[PROVISIONING_WORKFLOW].split("\n")
        start, end = provisioning_span(lines)
        cls.step = lines[start:end]

    def test_the_real_workflows_pass(self):
        self.assertEqual(ratchet_problems(self.texts), [])

    def test_a_new_whole_suite_job_in_a_real_workflow_is_reported(self):
        gap_files = {key.partition(":")[0] for key in KNOWN_UNPROVISIONED}
        name = next(file for file in sorted(self.texts) if file != PROVISIONING_WORKFLOW and file not in gap_files)
        added = self.texts[name].rstrip("\n") + "\n\n  extra-suite:\n    runs-on: ubuntu-24.04\n    steps:\n" + SUITE_STEP
        self.assertEqual([category for category, _ in ratchet_problems({**self.texts, name: added})], ["unlisted"])

    def test_provisioning_a_recorded_gap_job_is_cleared_by_deleting_its_entry(self):
        self.assertTrue(KNOWN_UNPROVISIONED, "no recorded gap is left to provision")
        for key in sorted(KNOWN_UNPROVISIONED):
            name, _, job = key.partition(":")
            with self.subTest(key):
                mutant = {**self.texts, name: with_step(self.texts[name], job, self.step)}
                self.assertEqual([category for category, _ in ratchet_problems(mutant)], ["stale"])
                self.assertEqual(ratchet_problems(mutant, KNOWN_UNPROVISIONED - {key}), [])
                self.assertEqual(provisioning_problems(mutant[name], job), [], "the transplanted step is judged like validate.yml's")
                self.assertTrue(key in provisioning_targets(mutant), "the structure checks do not inspect the newly provisioned job")

    def test_a_step_that_only_names_the_pin_file_is_judged_by_the_structure_checks(self):
        fake = ["      - name: Pretend to provision", f"        run: echo {PIN_PATH}"]
        for key in sorted(KNOWN_UNPROVISIONED):
            name, _, job = key.partition(":")
            with self.subTest(key):
                mutant = {**self.texts, name: with_step(self.texts[name], job, fake)}
                self.assertEqual(ratchet_problems(mutant, KNOWN_UNPROVISIONED - {key}), [])
                self.assertTrue({"derived", "export"} <= categories(mutant[name], job), "the structure checks accept a step that installs nothing")


@unittest.skipUnless(shutil.which("bash") and shutil.which("python3"), "the step runs under bash and calls python3, as on the runner")
class ProvisioningStepRuns(unittest.TestCase):
    """Runs the step's script as the runner does (bash -e over the script file) in a scratch workspace, with a
    stand-in npm that records its arguments, so nothing is installed and nothing leaves the machine."""

    text = VALIDATE_YML.read_text(encoding="utf-8")
    # What the promotion gate step wrote to GITHUB_ENV before this one: the file is appended to by every step of the
    # job, so a step that rewrote it would drop these variables.
    PRIOR = "PROMOTION_GATE_PYTHON=stub\nREQUIRE_PROMOTION_GATE_VENV=1\n"

    def run_step(self, pin=None, npm_exit=0):
        lines = self.text.split("\n")
        start, end = provisioning_span(lines)
        script = run_script("\n".join(lines[start:end]))
        with tempfile.TemporaryDirectory() as scratch:
            scratch = Path(scratch)
            workspace, temp, stub = scratch / "workspace", scratch / "runner-temp", scratch / "bin"
            (workspace / PIN_PATH).parent.mkdir(parents=True)
            (workspace / PIN_PATH).write_text(json.dumps(pin if pin is not None else load_pin()), encoding="utf-8")
            temp.mkdir()
            stub.mkdir()
            (stub / "npm").write_text('#!/bin/sh\nprintf \'%s\\n\' "$@" > "$NPM_ARGV_FILE"\nexit "$NPM_EXIT"\n', encoding="utf-8")
            (stub / "npm").chmod(0o755)
            (scratch / "github-env").write_text(self.PRIOR, encoding="utf-8")
            (scratch / "step.sh").write_text(script, encoding="utf-8")
            env = {"PATH": f"{stub}{os.pathsep}{os.environ['PATH']}", "HOME": str(scratch), "RUNNER_TEMP": str(temp),
                   "GITHUB_ENV": str(scratch / "github-env"), "NPM_ARGV_FILE": str(scratch / "argv"), "NPM_EXIT": str(npm_exit)}
            done = subprocess.run(["bash", "--noprofile", "--norc", "-e", str(scratch / "step.sh")], cwd=workspace, env=env,
                                  capture_output=True, text=True, timeout=60, check=False)
            argv = (scratch / "argv").read_text(encoding="utf-8").splitlines() if (scratch / "argv").exists() else None
            name = os.path.basename((pin if pin is not None else load_pin())["install"]["default_directory"])
            return SimpleNamespace(code=done.returncode, argv=argv, exported=(scratch / "github-env").read_text(encoding="utf-8"),
                                   temp=str(temp), made=(temp / name).is_dir())

    def test_it_runs_the_pin_command_into_runner_temp_and_exports_the_directory(self):
        pin = load_pin()
        words = shlex.split(pin["install"]["command"])
        result = self.run_step()
        directory = os.path.join(result.temp, os.path.basename(pin["install"]["default_directory"]))
        self.assertEqual(result.code, 0)
        self.assertTrue(result.argv == [directory if word == "<directory>" else word for word in words[1:]],
                        "npm did not receive the pin's command with the directory filled in")
        self.assertTrue(result.made, "the step creates the directory before npm runs")
        self.assertTrue(result.exported == self.PRIOR + f"{ENV_NAME}={directory}\n", "the step did not append exactly one export line")

    def test_it_refuses_a_command_without_exactly_one_directory_placeholder(self):
        for label, command in (("none", "npm install --ignore-scripts pkg@1"), ("two", "npm install --prefix <directory> <directory> pkg@1")):
            with self.subTest(label):
                pin = load_pin()
                pin["install"]["command"] = command
                result = self.run_step(pin)
                self.assertNotEqual(result.code, 0)
                self.assertTrue(result.argv is None, "npm must not run")
                self.assertTrue(result.exported == self.PRIOR, "the step changed the GITHUB_ENV file")

    def test_it_refuses_a_command_that_is_not_an_npm_install(self):
        # `true` succeeds whatever it is given, so only the check can make this step fail.
        pin = load_pin()
        pin["install"]["command"] = "true --prefix <directory>"
        result = self.run_step(pin)
        self.assertNotEqual(result.code, 0)
        self.assertTrue(result.argv is None, "nothing may run")
        self.assertTrue(result.exported == self.PRIOR, "the step changed the GITHUB_ENV file")

    def test_it_refuses_an_install_directory_name_that_could_inject_a_variable_or_leave_runner_temp(self):
        for label, name in (("newline", "tools/x\nNODE_OPTIONS=--require=evil"), ("dot dot", "tools/.."), ("space", "tools/a b"),
                            ("leading dot", "tools/.hidden")):
            with self.subTest(label):
                pin = load_pin()
                pin["install"]["default_directory"] = name
                result = self.run_step(pin)
                self.assertNotEqual(result.code, 0)
                self.assertTrue(result.argv is None, "npm must not run")
                self.assertTrue(result.exported == self.PRIOR, "the step changed the GITHUB_ENV file")

    def test_a_failing_npm_fails_the_step_and_exports_nothing(self):
        result = self.run_step(npm_exit=1)
        self.assertNotEqual(result.code, 0)
        self.assertTrue(result.exported == self.PRIOR, "the step changed the GITHUB_ENV file")


class HostInstallLineTests(unittest.TestCase):
    """The handbook's install line and read-only check for a new host, derived from the pin and run for real."""

    def handbook(self):
        return HANDBOOK.read_text(encoding="utf-8")

    def check_line(self):
        return next((line.strip() for line in self.handbook().splitlines() if line.startswith(CHECK_PREFIX)), None)

    def test_the_handbook_gives_the_pin_command_with_the_default_directory(self):
        pin = load_pin()
        command = pin["install"]["command"].replace("<directory>", f'"$HOME/{pin["install"]["default_directory"]}"')
        text = self.handbook()
        self.assertTrue(command in text, "the handbook does not give the pin's install command with its default directory")
        self.assertTrue(ENV_NAME in text, "the handbook does not name the directory override")

    @unittest.skipUnless(shutil.which("node") and shutil.which("bash"), "node and bash are not installed")
    def test_the_documented_check_reports_not_installed_on_a_clean_host(self):
        line = self.check_line()
        self.assertIsNotNone(line, "the handbook has no line that starts with the node check")
        with tempfile.TemporaryDirectory() as home:
            env = simulated_ci_env(home, drop=("GITHUB_ACTIONS", "GITHUB_JOB", "GITHUB_WORKFLOW_REF"))
            done = subprocess.run(["bash", "-c", line], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120, check=False)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(json.loads(done.stdout), {"ok": False, "reason": "not_installed"})

    @unittest.skipUnless(shutil.which("node") and shutil.which("bash"), "node and bash are not installed")
    def test_the_documented_check_reports_the_pinned_record_for_a_verified_install(self):
        line = self.check_line()
        self.assertIsNotNone(line, "the handbook has no line that starts with the node check")
        install = host_install()
        if install is None:
            self.skipTest("no verified tree-sitter-bash install on this host (CHILD_USAGE_SHELL_PARSER or the pin's default directory)")
        with tempfile.TemporaryDirectory() as home:
            env = simulated_ci_env(home, drop=("GITHUB_ACTIONS", "GITHUB_JOB", "GITHUB_WORKFLOW_REF"), **{ENV_NAME: str(install)})
            done = subprocess.run(["bash", "-c", line], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120, check=False)
        self.assertEqual(done.returncode, 0)
        self.assertTrue(verified(json.loads(done.stdout)))


if __name__ == "__main__":
    unittest.main()
