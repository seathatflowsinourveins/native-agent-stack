"""The reusable sota-sources gate and the check it shares with validate.yml.

.github/workflows/sota-sources-gate.yml is validate.yml's required sota-sources job made callable (`on:
workflow_call`), so a repository scaffolded by tools/adoption/scaffold_repo.py enforces the same pull-request rule by
calling it at a pinned commit. These tests keep the two copies one check:

- from the job's `if:` line to its end the gate's job is validate.yml's byte for byte (only the leading comment may
  differ), and a one-character drift is caught;
- the gate is only a reusable workflow, with a read-only token, and validate.yml keeps the job the main ruleset
  requires;
- run the way actions/github-script runs a script (an AsyncFunction over the named arguments,
  src/async-function.ts at the pinned v9.0.0 commit 3a2844b7), both copies pass and fail the same descriptions, and
  both pull-request templates fail until their SOTA sources section is filled in;
- zizmor finds nothing in the gate or in the scaffold's rendered caller, while the caller's unrendered `<sha>`
  placeholder is an unpinned-uses finding. zizmor 1.30.1 collects nested .github/workflows directories, so the
  scaffold keeps that file under a `.template` name that validate.yml's repository-wide zizmor gate does not collect.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
VALIDATE = WORKFLOWS / "validate.yml"
GATE = WORKFLOWS / "sota-sources-gate.yml"
RULESET = ROOT / ".github/main-ruleset.json"
SCAFFOLD = ROOT / "adoption/scaffold"
CALLER_TEMPLATE = SCAFFOLD / ".github/workflows/sota-sources.yml.template"
PR_TEMPLATES = {"scaffold": SCAFFOLD / ".github/pull_request_template.md",
                "repository": ROOT / ".github/pull_request_template.md"}
JOB_ID = "sota-sources"
GATE_REFERENCE = "seathatflowsinourveins/native-agent-stack/.github/workflows/sota-sources-gate.yml"
NODE = shutil.which("node")
ZIZMOR = shutil.which("zizmor")
A_COMMIT = "0123456789abcdef0123456789abcdef01234567"

sys.path.insert(0, str(ROOT / "tools" / "adoption"))


def jobs(text: str) -> dict:
    """{job_id: job_text} of the top-level jobs mapping, split as tests/test_workflow_hardening.py splits it."""
    body = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"(?m)^  ([A-Za-z0-9_-]+):[ \t]*(?:#.*)?$", body)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def check_body(job_text: str) -> str:
    """The job from its `if:` line to its end, trailing blank lines dropped: everything the runner evaluates. Only
    comment lines may come before it."""
    lines = job_text.rstrip("\n").split("\n")
    start = next((index for index, line in enumerate(lines) if line.startswith("    if: ")), None)
    if start is None:
        raise ValueError("the job has no `if:` line")
    if any(line.strip() and not line.lstrip().startswith("#") for line in lines[:start]):
        raise ValueError("something other than a comment comes before the job's `if:` line")
    return "\n".join(lines[start:]) + "\n"


def inline_script(job_text: str) -> str:
    """The job's github-script `script: |` block, dedented."""
    match = re.search(r"(?m)^( +)script: \|\n((?:\1  [^\n]*\n?|[ \t]*\n)+)", job_text)
    if match is None:
        raise ValueError("the job has no `script: |` block")
    return textwrap.dedent(match.group(2))


def sota_job(path: Path) -> str:
    return jobs(path.read_text(encoding="utf-8"))[JOB_ID]


# actions/github-script v9.0.0 (3a2844b7e9c422d3c10d287c895573f7108da1b3) src/async-function.ts: the script is the
# body of `new AsyncFunction(...Object.keys(args), source)`, called with the argument values. This script reads only
# `context` and `core`, so the harness passes those two.
HARNESS = r"""
const fs = require('fs');
const AsyncFunction = Object.getPrototypeOf(async () => null).constructor;
const {script, payloads} = JSON.parse(fs.readFileSync(0, 'utf8'));
(async () => {
  const results = [];
  for (const payload of payloads) {
    const outcome = {failed: null, info: null};
    const core = {setFailed: (message) => { outcome.failed = String(message); },
                  info: (message) => { outcome.info = String(message); }};
    await new AsyncFunction('context', 'core', script)({payload}, core);
    results.push(outcome);
  }
  process.stdout.write(JSON.stringify(results));
})().catch((error) => { process.stderr.write(String((error && error.stack) || error)); process.exit(1); });
"""


def run_check(script: str, payloads: list) -> list:
    result = subprocess.run([NODE, "-e", HARNESS], input=json.dumps({"script": script, "payloads": payloads}),
                            capture_output=True, text=True, timeout=60, check=False)
    if result.returncode != 0:
        raise AssertionError(f"node exited {result.returncode}: {result.stderr[:2000]}")
    return json.loads(result.stdout)


def body(text) -> dict:
    return {"pull_request": {"body": text}}


# (case, pull_request payload, whether the check passes)
CASES = [
    ("a ## section naming a source", body("## Summary\n\nx\n\n## SOTA sources\n\n- https://github.com/o/r at v1.2.3, "
                                          "src/x.py\n\n## Evidence\n\ny\n"), True),
    ("a ### section last in the body", body("### SOTA sources\n- https://example.org/paper\n"), True),
    ("CRLF line endings", body("## Summary\r\n\r\nx\r\n\r\n## SOTA sources\r\n\r\n- https://example.org/r\r\n"), True),
    ("only a comment in the section", body("## SOTA sources\n\n<!-- fill in -->\n\n## Evidence\n\ny\n"), False),
    ("no section", body("## Summary\n\nx\n"), False),
    ("a lower-case heading", body("## sota sources\n- https://example.org/r\n"), False),
    ("a level-4 heading", body("#### SOTA sources\n- https://example.org/r\n"), False),
    ("the next heading right after it", body("## SOTA sources\n## Evidence\ny\n"), False),
    ("an empty body", body(""), False),
    ("a null body", body(None), False),
    ("no pull_request in the payload", {}, False),
]


class GateIdentityTests(unittest.TestCase):
    def test_the_gate_is_only_a_reusable_workflow_with_a_read_only_token(self):
        text = GATE.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^on:\n  workflow_call:\n\n")
        self.assertEqual(re.findall(r"(?m)^on:.*$", text), ["on:"])
        self.assertEqual(re.findall(r"(?m)^  [a-z_]+:", text.split("\non:\n", 1)[1].split("\n\n", 1)[0]),
                         ["  workflow_call:"])
        # No token scope and no cache access (docs/decisions/2026-10-04-ci-least-privilege.md); the job adds none.
        self.assertIn("\npermissions: {}\ncache-mode: none\n\n", text)
        self.assertNotRegex(text, r"(?m)^    permissions:")
        self.assertNotRegex(text, r"(?m)^[ \t]*[\w-]+:[ \t]*write(?:-all)?[ \t]*(?:#.*)?$")
        self.assertEqual(list(jobs(text)), [JOB_ID])

    def test_the_gate_runs_validate_ymls_check_byte_for_byte(self):
        self.assertEqual(check_body(sota_job(GATE)), check_body(sota_job(VALIDATE)))
        self.assertEqual(inline_script(sota_job(GATE)), inline_script(sota_job(VALIDATE)))
        self.assertIn("core.setFailed(", inline_script(sota_job(GATE)))

    def test_a_one_character_drift_in_either_copy_is_caught(self):
        original = sota_job(GATE)
        for old, new in (("#{2,3}[ \\t]+SOTA sources", "#{2,4}[ \\t]+SOTA sources"), ("timeout-minutes: 2", "timeout-minutes: 3"),
                         ("egress-policy: audit", "egress-policy: block")):
            with self.subTest(drift=new):
                self.assertEqual(original.count(old), 1, old)
                self.assertNotEqual(check_body(original.replace(old, new)), check_body(sota_job(VALIDATE)))
        with self.assertRaises(ValueError):
            check_body(original.replace("    if: ", "    name: x\n    if: ", 1))

    def test_validate_yml_keeps_the_job_the_main_ruleset_requires(self):
        contexts = [check["context"] for rule in json.loads(RULESET.read_text(encoding="utf-8"))["rules"]
                    if rule.get("type") == "required_status_checks"
                    for check in rule["parameters"]["required_status_checks"]]
        self.assertIn(JOB_ID, contexts)
        self.assertIn(JOB_ID, jobs(VALIDATE.read_text(encoding="utf-8")))


@unittest.skipUnless(NODE, "node unavailable; CI's runner images carry it")
class GateBehaviourTests(unittest.TestCase):
    def test_both_copies_pass_and_fail_the_same_descriptions(self):
        payloads = [payload for _, payload, _ in CASES]
        outcomes = {name: run_check(inline_script(sota_job(path)), payloads)
                    for name, path in (("validate.yml", VALIDATE), ("sota-sources-gate.yml", GATE))}
        self.assertEqual(outcomes["validate.yml"], outcomes["sota-sources-gate.yml"])
        for (case, _, passes), outcome in zip(CASES, outcomes["sota-sources-gate.yml"]):
            with self.subTest(case=case):
                self.assertIs(outcome["failed"] is None, passes, outcome)
                if passes:
                    self.assertRegex(outcome["info"], r"^SOTA sources section present \(\d+ characters\)\.$")
                else:
                    self.assertIn('non-empty "SOTA sources" section', outcome["failed"])

    def test_both_pull_request_templates_fail_until_the_section_is_filled_in(self):
        script = inline_script(sota_job(GATE))
        for name, path in PR_TEMPLATES.items():
            with self.subTest(template=name):
                text = path.read_text(encoding="utf-8")
                headings = re.findall(r"(?m)^#{2,3} SOTA sources$", text)
                self.assertEqual(len(headings), 1, "exactly one SOTA sources heading the check can find")
                filled = text.replace(headings[0] + "\n", headings[0] + "\n\n- https://github.com/o/r at v1.2.3, "
                                      "src/x.py\n", 1)
                empty, done = run_check(script, [body(text), body(filled)])
                self.assertIsNotNone(empty["failed"])
                self.assertIsNone(done["failed"], done)


def zizmor(path: Path, directory: Path) -> tuple:
    """zizmor offline, as tests/test_workflow_security_coverage.py runs it: (exit status, finding idents)."""
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"GH_TOKEN", "GITHUB_TOKEN", "ZIZMOR_GITHUB_TOKEN"}}
    result = subprocess.run(
        [ZIZMOR, "--offline", "--no-config", "--no-ignores", "--no-progress", "--persona", "regular",
         "--strict-collection", "--format", "json", "--cache-dir", str(directory / "cache"), str(path)],
        cwd=directory, env=environment, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
        check=False)
    try:
        findings = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise AssertionError(f"zizmor did not return JSON (exit {result.returncode}): {result.stderr[:2000]}")
    return result.returncode, {finding["ident"] for finding in findings}


@unittest.skipUnless(ZIZMOR, "native zizmor unavailable; CI installs the pinned analyzer")
class GateZizmorTests(unittest.TestCase):
    def test_the_gate_has_no_offline_findings(self):
        with tempfile.TemporaryDirectory() as temporary:
            status, idents = zizmor(GATE, Path(temporary))
        self.assertEqual((status, idents), (0, set()))


class ScaffoldCallerTests(unittest.TestCase):
    def test_the_caller_calls_the_gate_at_a_placeholder_commit(self):
        text = CALLER_TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"(?m)^    uses: (\S+)$", text), [f"{GATE_REFERENCE}@<sha>"])
        self.assertIn("\npermissions:\n  contents: read\n", text)
        self.assertRegex(text, r"(?m)^  pull_request:\n    # [^\n]*\n    types: \[opened, synchronize, reopened, edited\]$")

    def test_no_scaffold_file_is_collected_as_a_workflow(self):
        # validate.yml's zizmor gate audits the repository root with --strict-collection, and zizmor 1.30.1 collects
        # a nested .github/workflows/*.yml, so a scaffold workflow holding its placeholder must not carry that name.
        collected = [path.relative_to(ROOT).as_posix() for path in SCAFFOLD.rglob("*")
                     if path.suffix in {".yml", ".yaml"}]
        self.assertEqual(collected, [])

    def test_the_rendered_caller_pins_a_commit_and_the_placeholder_does_not(self):
        import scaffold_repo
        rendered = scaffold_repo.render_caller(CALLER_TEMPLATE.read_text(encoding="utf-8"), A_COMMIT)
        self.assertIn(f"    uses: {GATE_REFERENCE}@{A_COMMIT}\n", rendered)
        self.assertNotIn("<sha>", rendered)
        for bad in ("", "main", "0123456", A_COMMIT.upper(), A_COMMIT + "0"):
            with self.subTest(sha=bad), self.assertRaises(ValueError):
                scaffold_repo.render_caller(CALLER_TEMPLATE.read_text(encoding="utf-8"), bad)

    @unittest.skipUnless(ZIZMOR, "native zizmor unavailable; CI installs the pinned analyzer")
    def test_zizmor_finds_nothing_in_the_rendered_caller_and_flags_the_raw_placeholder(self):
        import scaffold_repo
        text = CALLER_TEMPLATE.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            workflow = directory / "sota-sources.yml"
            workflow.write_text(scaffold_repo.render_caller(text, A_COMMIT), encoding="utf-8")
            self.assertEqual(zizmor(workflow, directory), (0, set()))
            workflow.write_text(text, encoding="utf-8")
            status, idents = zizmor(workflow, directory)
        self.assertNotEqual(status, 0)
        self.assertIn("unpinned-uses", idents)


if __name__ == "__main__":
    unittest.main()
