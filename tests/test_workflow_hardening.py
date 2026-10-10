"""Regression tests for the 2026-09-22 Actions hardening (docs/decisions/2026-09-22-actions-hardening.md).

Text-level checks (no YAML dependency; when PyYAML is importable the job parser is cross-checked
against it): every ubuntu job starts with step-security/harden-runner in audit mode unless its
workflow's exact bytes are pinned by retained evidence; Scorecard is unpublished and only its job
may write code-scanning results; dependency review runs on pull requests only and fails on high
advisories; security-scan.yml and publish-catalog.yml's release job keep write scopes job-local
(docs/decisions/2026-09-22-github-automation-closure.md); every third-party action is pinned by
a full commit SHA.
"""

from datetime import date
from pathlib import Path
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

import tests

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
HARDEN = "step-security/harden-runner@"
UPLOAD_SARIF = "github/codeql-action/upload-sarif@"
# Workflows whose exact bytes are pinned by retained evidence; editing them would detach that
# evidence from the file, so their jobs stay unhardened until the evidence is re-run. Each maps
# to a file that records the workflow's current SHA-256.
HASH_FROZEN = {}
# Empty since 2026-09-26 (docs/decisions/2026-09-26-token-workflow-hardening.md); the filters that read
# it stay for a future named exemption. native-token-e2e.yml left it when local --install runs
# re-recorded its harness receipts against the new workflow bytes (evidence/artifacts/
# token-workflow-hardening-20260926/); those runs call scripts/native_token_ci.py directly, so the
# pull request's hosted run is the step's first execution and completes the overturn named in
# docs/decisions/2026-09-22-actions-hardening-fix-round.md. The two off-host workflows gained the step
# with a refresh of only their recovery plans' prospective bindings (plan.json, hosted-plan.json, still
# enforced by tests/test_active_recovery_plans.py), as on 2026-09-20; their next dispatch is the first
# run with it. Putting one of the three back here also means dropping it from FORMERLY_HASH_FROZEN.
FORMERLY_HASH_FROZEN = ("native-offhost-app-state.yml", "native-offhost-restore.yml", "native-token-e2e.yml")
# An exact release in a pin's comment, such as `# v7.0.1`. A major-only `# v7` names a tag that
# moves: zizmor's online ref-version-mismatch audit (a Medium finding at the regular persona, which
# fails the validate job) reports it as soon as upstream moves that tag off the pinned commit.
EXACT_RELEASE_COMMENT = re.compile(r"#\s*v\d+\.\d+\.\d+\s*$")
# step-security/harden-runner's pinned version supports macOS runners too,
# in audit mode -- its README, read at this exact pinned commit
# (e14015d583714f6e62063499dc959a02595150a1) on 2026-09-23: "GitHub-hosted
# runners (Windows, macOS): Audit mode only", which is the only mode this
# project ever uses (test_harden_runner_never_blocks_egress below). A macOS
# job is therefore held to the same requirement as an ubuntu job, except for
# a job whose macOS job is owned by a different, concurrent task and must
# not be edited from this file's own change: adding it here is a narrow,
# named ownership exemption, never a platform-support one. Keyed per
# "file.yml:job_id", not per file, so a ubuntu job sharing that same file
# (hardware-profile-smoke.yml's own linux-profile) stays checked.
MACOS_JOBS_OWNED_ELSEWHERE = {"hardware-profile-smoke.yml:macos-profile"}


def jobs(text):
    """Return {job_id: job_text} for the top-level jobs mapping."""
    body = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"(?m)^  ([A-Za-z0-9_-]+):[ \t]*(?:#.*)?$", body)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def first_step(job_text):
    steps = job_text.split("\n    steps:\n", 1)
    if len(steps) < 2:
        return ""
    match = re.search(r"(?ms)^      - (.*?)(?=^      - |\Z)", steps[1])
    return match.group(1) if match else ""


def step_block(job_text, name_fragment):
    """The whole text of the step whose ``name:`` line contains ``name_fragment``: from
    that step's ``      - `` list-item line (so keys written before ``name:``, such as a
    leading ``- if:``, are included) through the next step boundary or the end of the job."""
    lines = job_text.splitlines()
    hit = next(i for i, line in enumerate(lines) if name_fragment in line and re.search(r"\bname:", line))
    start = next(i for i in range(hit, -1, -1) if re.match(r"^      - ", lines[i]))
    end = next((i for i in range(hit + 1, len(lines)) if re.match(r"^      - ", lines[i])), len(lines))
    return "\n".join(lines[start:end])


def block_if(block_text):
    """A step's or job's own ``if:`` value, found anywhere in ``block_text`` (not tied
    to a fixed line offset, so reordering keys within the block does not defeat the
    search) and resolved however it is written: a plain one-line scalar, or a ``>``/``|``
    folded or literal block scalar whose value spans the following more-indented lines.
    Returns ``None`` if the block has no ``if:`` key of its own."""
    match = re.search(r"(?m)^([ \t]*(?:- )?)if:[ \t]*(.*)$", block_text)
    if not match:
        return None
    indent, value = len(match.group(1)), match.group(2).strip()
    folded = not value or value[0] in ">|"
    parts = [] if folded else [value]
    # Plain scalars can continue on more-indented lines too, so always collect them.
    for line in block_text[match.end():].splitlines():
        if not line.strip():
            continue
        if len(line) - len(line.lstrip(" \t")) <= indent or re.match(r"^\s*[\w-]+:(\s|$)", line):
            break
        parts.append(line.strip())
    return " ".join(parts)


# The top-level `permissions: {}` that grants no scope (docs/decisions/2026-10-04-ci-least-privilege.md), and an
# inline permissions form other than that empty mapping (a read-all/write-all string or a flow mapping).
NO_SCOPE = r"(?m)^permissions: \{\}[ \t]*$"
INLINE_GRANT = r"(?m)permissions:[ \t]*(?!\{\}[ \t]*$)[^\s#]"


def permission_blocks(text):
    """Every block-form permissions mapping in a workflow, as {scope: access} dicts."""
    blocks = []
    for match in re.finditer(r"(?m)^( *)permissions:[ \t]*\n((?:\1  [^\n]*\n)+)", text):
        entries = [line.strip().split(":", 1) for line in match.group(2).splitlines() if line.strip()]
        blocks.append({key.strip(): value.strip() for key, value in entries})
    return blocks


class HardenRunnerTests(unittest.TestCase):
    def test_every_ubuntu_and_macos_job_starts_with_harden_runner_in_audit_mode(self):
        unclassified, missing = [], []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for job_id, job_text in jobs(path.read_text(encoding="utf-8")).items():
                name = f"{path.name}:{job_id}"
                if name in MACOS_JOBS_OWNED_ELSEWHERE:
                    continue
                if not re.search(r"runs-on:\s*(?:ubuntu|macos)-\d", job_text):
                    unclassified.append(name)
                    continue
                if path.name in HASH_FROZEN:
                    continue
                step = first_step(job_text)
                if HARDEN not in step or "egress-policy: audit" not in step:
                    missing.append(name)
        self.assertEqual(unclassified, [], "jobs whose runner is neither a literal ubuntu nor macos label")
        self.assertEqual(missing, [], "ubuntu/macos jobs without a first-step harden-runner audit")


    def test_hardware_profile_smoke_linux_job_stays_checked_despite_the_macos_job_exemption(self):
        # Regression guard for the exemption's own precision: it is keyed
        # per "file.yml:job_id" specifically so this file's ubuntu job is
        # never accidentally exempted alongside its macOS one.
        self.assertNotIn("hardware-profile-smoke.yml:linux-profile", MACOS_JOBS_OWNED_ELSEWHERE)
        text = (WORKFLOWS / "hardware-profile-smoke.yml").read_text(encoding="utf-8")
        job_map = jobs(text)
        self.assertIn("linux-profile", job_map)
        step = first_step(job_map["linux-profile"])
        self.assertIn(HARDEN, step)
        self.assertIn("egress-policy: audit", step)

    def test_hash_frozen_exemptions_are_still_pinned(self):
        if not HASH_FROZEN:
            # Reported as skipped rather than passed: with no exemption there is nothing to check.
            self.skipTest("no workflow is hash-frozen (empty since 2026-09-26)")
        for name, pin in HASH_FROZEN.items():
            digest = hashlib.sha256((WORKFLOWS / name).read_bytes()).hexdigest()
            self.assertIn(digest, (ROOT / pin).read_text(encoding="utf-8"), f"{name} is no longer pinned by {pin}")

    def test_formerly_exempt_workflows_stay_hardened(self):
        # Regression guard: none of the three returns to HASH_FROZEN, and each of their four jobs
        # starts with the audit step.
        found = []
        for name in FORMERLY_HASH_FROZEN:
            self.assertNotIn(name, HASH_FROZEN)
            for job_id, job_text in jobs((WORKFLOWS / name).read_text(encoding="utf-8")).items():
                step = first_step(job_text)
                self.assertIn(HARDEN, step, f"{name}:{job_id}")
                self.assertIn("egress-policy: audit", step, f"{name}:{job_id}")
                found.append(f"{name}:{job_id}")
        self.assertEqual(sorted(found), ["native-offhost-app-state.yml:destination", "native-offhost-app-state.yml:source",
                                         "native-offhost-restore.yml:synthetic-restore", "native-token-e2e.yml:native-token-tools"])

    def test_github_automation_cites_only_existing_tests(self):
        # docs/github-automation.md cites tests as the proof of its hardening claims. After the
        # ubuntu-only test was renamed for macOS coverage, the page kept citing the old name for a
        # test that no longer existed (2026-09-26 review).
        cited = set(re.findall(r"`(test_\w+)`", (ROOT / "docs/github-automation.md").read_text(encoding="utf-8")))
        defined = {name for path in (ROOT / "tests").glob("test_*.py")
                   for name in re.findall(r"(?m)^\s*(?:async\s+)?def (test_\w+)\(", path.read_text(encoding="utf-8"))}
        self.assertIn("test_every_ubuntu_and_macos_job_starts_with_harden_runner_in_audit_mode", defined)
        self.assertTrue(cited, "the page cites no test by name")
        self.assertEqual(sorted(cited - defined), [], "tests cited in docs/github-automation.md but not defined")

    def test_job_parser_matches_yaml_when_available(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed; the text parser is the only job source")
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(sorted(jobs(text)), sorted(yaml.safe_load(text)["jobs"]), path.name)

    def test_harden_runner_never_blocks_egress(self):
        for path in WORKFLOWS.glob("*.yml"):
            self.assertNotIn("egress-policy: block", path.read_text(encoding="utf-8"), path.name)


class ScorecardTests(unittest.TestCase):
    text = (WORKFLOWS / "scorecard.yml").read_text(encoding="utf-8")

    def test_results_are_not_published(self):
        self.assertIn("publish_results: false", self.text)
        self.assertNotIn("publish_results: true", self.text)

    def test_only_the_analysis_job_may_write_code_scanning_results(self):
        # The workflow grants no scope; the analysis job grants its own.
        top_level = self.text.split("\njobs:\n", 1)[0]
        self.assertEqual(scopes(top_level), [])
        self.assertRegex(top_level, NO_SCOPE)
        job = jobs(self.text)["analysis"]
        self.assertEqual(scopes(job), [{"contents": "read", "security-events": "write"}])
        self.assertNotRegex(self.text, INLINE_GRANT, "no inline read-all/write-all form")

    def test_sarif_goes_to_code_scanning_and_stays_an_artifact(self):
        job = jobs(self.text)["analysis"]
        self.assertIn(UPLOAD_SARIF, job)
        self.assertIn("sarif_file: results.sarif", job)
        self.assertIn("actions/upload-artifact@", job)


class DependencyReviewTests(unittest.TestCase):
    text = (WORKFLOWS / "dependency-review.yml").read_text(encoding="utf-8")

    def test_runs_on_pull_requests_only_and_fails_on_high(self):
        trigger = self.text.split("\non:\n", 1)[1].split("\n\n", 1)[0]
        self.assertEqual([line.strip() for line in trigger.splitlines() if line.strip()], ["pull_request:"])
        self.assertIn("fail-on-severity: high", self.text)
        self.assertNotIn("warn-only:", self.text)
        self.assertRegex(self.text.split("\njobs:\n", 1)[0], NO_SCOPE)
        blocks = permission_blocks(self.text)
        self.assertGreaterEqual(len(blocks), 1)
        for block in blocks:
            self.assertEqual(block, {"contents": "read"})
        self.assertNotRegex(self.text, INLINE_GRANT, "no inline read-all/write-all form")


def scopes(text):
    """permission_blocks() with trailing `# reason` comments removed from each access value."""
    return [{key: value.split("#", 1)[0].strip() for key, value in block.items()} for block in permission_blocks(text)]


class SecurityScanTests(unittest.TestCase):
    text = (WORKFLOWS / "security-scan.yml").read_text(encoding="utf-8")

    def test_triggers_include_every_pull_request_without_a_path_filter(self):
        trigger = self.text.split("\non:\n", 1)[1].split("\n\n", 1)[0]
        self.assertRegex(trigger, r"(?m)^  pull_request:[ \t]*$")
        self.assertNotIn("paths", trigger)
        for event in ("push:", "schedule:", "workflow_dispatch:"):
            self.assertIn(event, trigger)

    def test_write_scope_is_job_local_and_limited_to_security_events(self):
        top_level = self.text.split("\njobs:\n", 1)[0]
        self.assertEqual(scopes(top_level), [])
        self.assertRegex(top_level, NO_SCOPE)
        expected = {"osv-scanner": [{"contents": "read"}],
                    "osv-sarif-upload": [{"contents": "read", "security-events": "write"}],
                    "zizmor-online": [{"contents": "read"}],
                    "zizmor-sarif-upload": [{"contents": "read", "security-events": "write"}]}
        self.assertEqual({job_id: scopes(job) for job_id, job in jobs(self.text).items()}, expected)
        self.assertNotRegex(self.text, INLINE_GRANT, "no inline read-all/write-all form")

    def test_the_write_token_never_reaches_an_installed_tool(self):
        self.assertIn("GH_TOKEN: ${{ github.token }}", jobs(self.text)["zizmor-online"])
        # Frozen SARIF moves to its separate report-only workflow; the required
        # ordinary scan retains its own upload and installed tools stay read-only.
        for tool_job, upload_job, uploads in (("osv-scanner", "osv-sarif-upload", 1), ("zizmor-online", "zizmor-sarif-upload", 1)):
            upload = jobs(self.text)[upload_job]
            self.assertIn(f"needs: {tool_job}", upload, upload_job)
            self.assertNotRegex(upload, r"(?m)^\s+(- )?run:", f"{upload_job} (write scope) runs no shell step")
            actions = re.findall(r"uses: ([\w.-]+/[\w./-]+)@", upload)
            self.assertEqual(actions, ["step-security/harden-runner", "actions/checkout", "actions/download-artifact"]
                             + ["github/codeql-action/upload-sarif"] * uploads, upload_job)

    def test_osv_scanner_fails_on_findings_and_uploads_sarif_off_pull_requests(self):
        job = jobs(self.text)["osv-scanner"]
        self.assertNotIn("\n    if:", job, "the required PR check must run on every event")
        # `shell: bash` implies -e; without `set +e` a findings exit stops the step before the SARIF run.
        self.assertIn("set +e -u -o pipefail", job)
        self.assertIn('exit "$status"', job)
        self.assertNotIn("continue-on-error", job)
        keep = step_block(job, "Keep the OSV-Scanner SARIF for the upload job")
        self.assertIn("github.event_name != 'pull_request'", block_if(keep))
        self.assertIn("if-no-files-found: error", keep)
        upload = jobs(self.text)["osv-sarif-upload"]
        self.assertIn("github.event_name != 'pull_request'", block_if(upload))
        self.assertIn(UPLOAD_SARIF, upload)
        self.assertIn("category: osv-scanner\n", upload)
        self.assertNotIn("category: osv-scanner-frozen-macos", upload)
        # Native ordinary scan and SARIF outcomes both gate the required job.
        self.assertIn("osv-scanner.sarif", job)
        self.assertIn("osv-scanner.sarif", upload)
        self.assertIn('statuses=("$status")', job)
        self.assertIn('statuses+=("$sarif_status")', job)
        self.assertIn('for code in "${statuses[@]}"', job)
        self.assertNotIn("frozen_status", job)
        self.assertNotIn("scan_frozen", job)
        # Required artifact eligibility guards remain, even though advisories
        # now report in a separately named, non-required context.
        self.assertIn("tests.test_osv_lockfile_coverage.FrozenScanTests", job)
        frozen = (ROOT / ".github/workflows/frozen-evidence-risk.yml").read_text(encoding="utf-8")
        self.assertIn("category: osv-scanner-frozen-macos", frozen)
        self.assertIn("osv-scanner-frozen-macos.sarif", frozen)
        self.assertNotIn("continue-on-error", frozen)
        # The retired WSL group's scan and upload went with its lock's rename out of discovery (2026-10-04).
        self.assertNotIn("frozen-wsl", self.text)
        self.assertNotIn("frozen_wsl", self.text)

    def test_zizmor_online_skips_pull_requests_and_reports_without_failing(self):
        job = jobs(self.text)["zizmor-online"]
        self.assertIn("if: github.event_name != 'pull_request'", job)
        self.assertIn("-r .github/requirements-ci.txt", job)
        self.assertIn("--require-hashes", job)
        self.assertIn("GH_TOKEN: ${{ github.token }}", job)
        self.assertIn("--no-exit-codes", job)
        self.assertIn("--format sarif", job)
        self.assertNotIn("--offline", job)
        self.assertIn("if-no-files-found: error", job)
        self.assertIn("category: zizmor", jobs(self.text)["zizmor-sarif-upload"])

    def test_jobs_check_out_without_persisted_credentials(self):
        for job_id, job in jobs(self.text).items():
            self.assertIn("persist-credentials: false", job, job_id)
            self.assertRegex(job, r"timeout-minutes: \d+", job_id)

    def test_failure_path_semantics_keep_findings_uploadable(self):
        # (a) The OSV SARIF upload step must still run when the scan step failed
        # (a findings exit) so code scanning still receives the report; only a
        # cancelled run should skip it. block_if() searches the whole step block
        # rather than a fixed line offset, so this still catches a missing/weakened
        # guard even if `uses:` were reordered ahead of `if:`.
        # The artifact step and the downstream upload job both need it.
        osv_job = jobs(self.text)["osv-scanner"]
        frozen_jobs = jobs((ROOT / ".github/workflows/frozen-evidence-risk.yml").read_text(encoding="utf-8"))
        for label, block in (("OSV SARIF artifact step", step_block(osv_job, "Keep the OSV-Scanner SARIF for the upload job")),
                             ("osv-sarif-upload job", jobs(self.text)["osv-sarif-upload"]),
                             ("frozen report artifact step", step_block(frozen_jobs["frozen-evidence-risk"],
                                                                       "Retain the frozen native reports and diagnostics")),
                             ("frozen SARIF upload job", frozen_jobs["frozen-osv-sarif-upload"])):
            guard = block_if(block)
            self.assertIsNotNone(guard, f"the {label} must have its own if: guard")
            self.assertRegex(guard, r"!\s*cancelled\(\)|always\(\)",
                              f"the {label}'s if: must keep !cancelled() or always() so a findings "
                              "exit (the scan step failing) does not skip the upload")

        # (b) The zizmor analyzer step must not have continue-on-error: true, and the
        # artifact-upload step must have no if: that would let it (and, downstream,
        # the upload job) run after the analyzer step failed. Without both guards, a
        # crashed analyzer could still upload a partial or empty SARIF.
        zizmor_online = jobs(self.text)["zizmor-online"]
        analyzer_step = step_block(zizmor_online, "Audit GitHub workflows with zizmor's online audits")
        self.assertNotIn("continue-on-error", analyzer_step,
                          "the zizmor analyzer step must not continue past a crash "
                          "(continue-on-error would let a partial/empty SARIF reach the upload)")
        keep_step = step_block(zizmor_online, "Keep the zizmor SARIF for the upload job")
        keep_if = block_if(keep_step)  # resolves folded/literal block-scalar if: too
        self.assertFalse(keep_if and re.search(r"\b(always|cancelled|failure)\s*\(\)", keep_if),
                         "the artifact-upload step must not force a run after the analyzer "
                         "step failed; its default (skip-on-failure) behavior is required")

        # (c) The zizmor-sarif-upload job's own if: must not force it to run after a
        # cancelled or failed zizmor-online run either (it only skips on pull_request).
        # block_if() also resolves a folded/literal (`>`/`|`) block-scalar if:, which a
        # fixed single-line slice would read as the literal folding marker and pass
        # vacuously.
        upload_job = jobs(self.text)["zizmor-sarif-upload"]
        job_if = block_if(upload_job)
        self.assertIsNotNone(job_if, "zizmor-sarif-upload must have its own if: guard")
        self.assertNotRegex(job_if, r"\b(always|cancelled)\s*\(\)",
                             "zizmor-sarif-upload's if: must not add always()/!cancelled(); it "
                             "should only run after zizmor-online actually produced an artifact")


def zizmor_step(job_text):
    """The one step of a job whose ``run:`` invokes zizmor."""
    lines = job_text.splitlines()
    hits = [i for i, line in enumerate(lines) if re.search(r"(^|\s)zizmor\s+--", line) and not line.lstrip().startswith("#")]
    if len(hits) != 1:
        raise AssertionError(f"expected one zizmor invocation, found {len(hits)}")
    start = next(i for i in range(hits[0], -1, -1) if re.match(r"^      - ", lines[i]))
    end = next((i for i in range(hits[0] + 1, len(lines)) if re.match(r"^      - ", lines[i])), len(lines))
    return "\n".join(lines[start:end])


def uncommented(text):
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def zizmor_inputs(step):
    """The positional inputs of a step's zizmor invocation (backslash continuations joined,
    option values and any shell redirection dropped)."""
    command = re.sub(r"\\\n\s*", " ", uncommented(step))
    invocation = re.search(r"(?:^|\s)zizmor\s+([^\n>|;&]*)", command).group(1).split()
    inputs, skip = [], False
    for token in invocation:
        if skip:
            skip = False
        elif token in {"--persona", "--format", "--cache-dir", "--min-severity", "--min-confidence", "--config"}:
            skip = True
        elif not token.startswith("-"):
            inputs.append(token)
    return inputs


class ValidateZizmorGateTests(unittest.TestCase):
    """The required validate check runs zizmor's online audits and fails on findings
    (docs/decisions/2026-09-22-github-automation-closure.md, "GitHub hardening follow-up
    (2026-09-25)"). zizmor 1.30.1 with no token silently falls back to offline mode and
    exits 0, so the token line is what keeps the online audits in the gate."""

    step = zizmor_step(jobs((WORKFLOWS / "validate.yml").read_text(encoding="utf-8"))["validate"])

    def test_online_audits_get_the_read_only_job_token(self):
        self.assertIn("GH_TOKEN: ${{ github.token }}", self.step)
        text = (WORKFLOWS / "validate.yml").read_text(encoding="utf-8")
        # The workflow grants no scope (docs/decisions/2026-10-04-ci-least-privilege.md); the token the online
        # audits use is the validate job's own read-only grant.
        self.assertEqual(scopes(text.split("\njobs:\n", 1)[0]), [])
        self.assertRegex(text.split("\njobs:\n", 1)[0], NO_SCOPE)
        self.assertEqual(scopes(jobs(text)["validate"]), [{"contents": "read"}])

    def test_findings_fail_the_required_check(self):
        command = uncommented(self.step)
        for forbidden in ("--offline", "--no-exit-codes", "--format sarif", "--format=sarif", "continue-on-error"):
            self.assertNotIn(forbidden, command)
        self.assertIn("--persona regular", command)
        self.assertIn("--no-config --no-ignores", command)
        self.assertIn("--strict-collection", command)

    def test_both_ci_runs_audit_the_repository_root_so_dependabot_yml_is_collected(self):
        online = zizmor_step(jobs((WORKFLOWS / "security-scan.yml").read_text(encoding="utf-8"))["zizmor-online"])
        for label, step in (("validate", self.step), ("zizmor-online", online)):
            self.assertEqual(zizmor_inputs(step), ["."], label)


class PublishReleaseTests(unittest.TestCase):
    text = (WORKFLOWS / "publish-catalog.yml").read_text(encoding="utf-8")

    def test_release_job_is_tag_only_after_publish_with_contents_write_only(self):
        job = jobs(self.text)["release"]
        self.assertIn("needs: publish", job)
        self.assertIn("startsWith(github.ref, 'refs/tags/v')", job.split("\n    if:", 1)[1].split("\n", 1)[0])
        self.assertEqual(scopes(job), [{"contents": "write"}])
        self.assertEqual(scopes(self.text.split("\njobs:\n", 1)[0]), [])
        self.assertRegex(self.text.split("\njobs:\n", 1)[0], NO_SCOPE)
        self.assertNotIn("contents: write", jobs(self.text)["publish"])

    def test_release_rechecks_attested_digests_and_attaches_files_at_creation(self):
        job = jobs(self.text)["release"]
        self.assertIn("needs.publish.outputs.archive-sha256", job)
        self.assertIn("needs.publish.outputs.sbom-sha256", job)
        self.assertIn("sha256sum --check --strict", job)
        create = job.split("gh release create", 1)[1].split("\n      - name:", 1)[0]
        self.assertIn('"$archive" "$sbom"', create)
        self.assertIn("--verify-tag", create)
        self.assertNotIn("--draft", create)
        self.assertNotIn("gh release upload", job, "immutable releases reject assets added after publish")
        self.assertIn("gh attestation verify", job)
        self.assertIn(".isImmutable == true", job)


    def test_publish_outputs_name_existing_step_ids(self):
        job = jobs(self.text)["publish"]
        ids = set(re.findall(r"(?m)^        id: ([A-Za-z0-9_-]+)$", job))
        outputs = re.findall(r"\$\{\{ steps\.([A-Za-z0-9_-]+)\.outputs\.[A-Za-z0-9_-]+ \}\}",
                             job.split("\n    outputs:\n", 1)[1].split("\n    steps:\n", 1)[0])
        self.assertEqual(len(outputs), 4)
        self.assertEqual(sorted(set(outputs) - ids), [])
        for step in ("archive-digest", "sbom-digest"):
            body = job.split(f"id: {step}\n", 1)[1].split("\n      - name:", 1)[0]
            self.assertIn('>> "$GITHUB_OUTPUT"', body, step)


class TargetRulesetTests(unittest.TestCase):
    """The committed target main ruleset (docs/decisions/2026-09-22-github-automation-closure.md, section 10)."""

    ruleset = __import__("json").loads((ROOT / ".github/main-ruleset.json").read_text(encoding="utf-8"))

    def rule(self, kind):
        return [rule for rule in self.ruleset["rules"] if rule["type"] == kind]

    def test_strict_up_to_date_checks_stay_off_and_required_signatures_stays_out(self):
        (checks,) = self.rule("required_status_checks")
        self.assertIs(checks["parameters"]["strict_required_status_checks_policy"], False)
        self.assertEqual(self.rule("required_signatures"), [])

    def test_target_requires_the_security_gates_from_github_actions(self):
        (checks,) = self.rule("required_status_checks")
        contexts = {check["context"]: check.get("integration_id") for check in checks["parameters"]["required_status_checks"]}
        required = ("validate", "token-report", "secret-scan", "dependency-review", "osv-scanner",
                    "verdict-review-gate", "sota-sources")
        self.assertEqual(contexts, {context: 15368 for context in required})
        self.assertEqual(len(self.rule("code_scanning")), 1)


class AgentBranchRulesetTests(unittest.TestCase):
    """The committed agent-branch ruleset, applied as 24132241 (docs/github-automation.md, "Agent branch ruleset").

    The resolver driver pushes with the owner's login, so an admin-role or owner bypass would free it too: only a
    no-bypass rule binds it. Deletion stays allowed because delete_branch_on_merge is on.
    """

    PATH = ROOT / ".github/agent-branch-ruleset.json"

    def ruleset(self):
        return json.loads(self.PATH.read_text(encoding="utf-8"))

    def test_blocks_history_rewrite_on_both_agent_prefix_patterns_without_bypass(self):
        ruleset = self.ruleset()
        self.assertEqual((ruleset["target"], ruleset["enforcement"]), ("branch", "active"))
        self.assertEqual(ruleset["bypass_actors"], [])
        self.assertEqual(ruleset["conditions"]["ref_name"],
                         {"include": ["refs/heads/openhands/*", "refs/heads/openhands/**/*"], "exclude": []})
        self.assertEqual(ruleset["rules"], [{"type": "non_fast_forward"}])

    def test_never_targets_main_or_blocks_post_merge_branch_deletion(self):
        ruleset = self.ruleset()
        for pattern in ruleset["conditions"]["ref_name"]["include"]:
            self.assertTrue(pattern.startswith("refs/heads/openhands/"), pattern)
        self.assertNotIn("deletion", {rule["type"] for rule in ruleset["rules"]})


class VerdictReviewGateTests(unittest.TestCase):
    """The required verdict-review-gate job (docs/decisions/2026-09-22-github-automation-closure.md,
    "verdict-review-gate (2026-09-23)")."""

    text = (WORKFLOWS / "pr-metadata.yml").read_text(encoding="utf-8")
    job = jobs(text)["verdict-review-gate"]

    def test_runs_on_every_pull_request_without_a_path_filter(self):
        trigger = self.text.split("\non:\n", 1)[1].split("\n\n", 1)[0]
        self.assertRegex(trigger, r"(?m)^  pull_request:[ \t]*$")
        self.assertNotIn("paths", trigger)
        self.assertNotIn("branches", trigger.split("pull_request:", 1)[1].split("workflow_dispatch:", 1)[0])
        self.assertIn("push:", trigger)
        self.assertIsNone(block_if(self.job.split("\n    steps:\n", 1)[0]), "a required check must run on every event")

    def test_read_only_hardened_and_without_persisted_credentials(self):
        self.assertEqual(scopes(self.job), [{"contents": "read", "pull-requests": "read"}])
        step = first_step(self.job)
        self.assertIn(HARDEN, step)
        self.assertIn("egress-policy: audit", step)
        checkout = step_block(self.job, "Check out repository")
        self.assertIn("persist-credentials: false", checkout)
        self.assertIn("fetch-depth: 0", checkout)
        self.assertRegex(self.job, r"timeout-minutes: \d+")

    def test_pull_request_re_runs_when_its_base_branch_changes(self):
        # Review of #135, H1: without the edited type a retargeted PR kept its earlier green run.
        trigger = self.text.split("\non:\n", 1)[1].split("\n\n", 1)[0]
        pull_request = trigger.split("pull_request:", 1)[1].split("workflow_dispatch:", 1)[0]
        (types,) = re.findall(r"(?m)^    types: \[([^\]]*)\]$", pull_request)
        self.assertEqual([item.strip() for item in types.split(",")], ["opened", "synchronize", "reopened", "edited"])

    def test_validate_does_not_run_for_metadata_edits_or_duplicate_the_metadata_jobs(self):
        text = (WORKFLOWS / "validate.yml").read_text(encoding="utf-8")
        trigger = text.split("\non:\n", 1)[1].split("\n\n", 1)[0]
        pull_request = trigger.split("pull_request:", 1)[1].split("workflow_dispatch:", 1)[0]
        (types,) = re.findall(r"(?m)^    types: \[([^\]]*)\]$", pull_request)
        self.assertEqual([item.strip() for item in types.split(",")], ["opened", "synchronize", "reopened"])
        self.assertNotIn("edited", types)
        self.assertTrue({"sota-sources", "verdict-review-gate"}.isdisjoint(jobs(text)))
        self.assertEqual(set(jobs(self.text)), {"sota-sources", "verdict-review-gate"})

    def test_metadata_edits_queue_without_cancelling_and_without_default_permissions_or_cache(self):
        self.assertIn("\npermissions: {}\ncache-mode: none\n", self.text)
        self.assertIn("  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}\n",
                      self.text)
        self.assertIn("\n  queue: max\n", self.text)
        self.assertNotIn("cancel-in-progress:", self.text)

    @unittest.skipUnless(shutil.which("node"), "node unavailable; CI's runner images carry it")
    def test_the_current_base_check_allows_sha_drift_and_fails_on_retarget_or_retrieval_error(self):
        from tests.test_sota_sources_gate import inline_script, run_check
        step = step_block(self.job, "Require the current PR base")
        self.assertEqual(block_if(step), "github.event_name == 'pull_request'")
        self.assertIn("actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3 # v9.0.0", step)
        self.assertNotIn("continue-on-error", step)
        self.assertLess(self.job.index("Require the current PR base"), self.job.index("Require sealed cross-family"))
        event_base = {"ref": "main", "sha": "a" * 40}
        payload = {"pull_request": {"number": 42, "base": event_base}}
        same, retargeted, advanced, unavailable = run_check(inline_script(step), [
            payload,
            {**payload, "current_pull_request": {"base": {**event_base, "ref": "develop"}}},
            {**payload, "current_pull_request": {"base": {**event_base, "sha": "b" * 40}}},
            {**payload, "retrieval_error": "request denied"},
        ])
        self.assertIsNone(same["failed"], same)
        self.assertIsNone(advanced["failed"], advanced)
        self.assertIn("current PR base differs from the event base; failing closed", retargeted["failed"])
        self.assertIn("request denied", unavailable["failed"])
        for outcome in (same, retargeted, advanced, unavailable):
            self.assertEqual(outcome["requests"], [{"owner": "fixture-owner", "repo": "fixture-repo",
                                                  "pull_number": 42}])

    def run_script(self):
        return step_block(self.job, "Require sealed cross-family review").split("run: |", 1)[1]

    def test_event_values_reach_the_gate_through_env_only(self):
        gate = step_block(self.job, "Require sealed cross-family review")
        self.assertIn("EVENT_NAME: ${{ github.event_name }}", gate)
        self.assertIn("PR_BASE_SHA: ${{ github.event.pull_request.base.sha }}", gate)
        self.assertIn("PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}", gate)
        self.assertIn("PUSH_BEFORE_SHA: ${{ github.event.before }}", gate)
        self.assertIn("PR_BASE_REF: ${{ github.base_ref }}", gate)
        self.assertNotIn("${{", self.run_script(), "no expression is interpolated into the shell script")
        self.assertNotIn("continue-on-error", gate)

    def test_pull_request_base_is_the_merge_commits_first_parent_cross_checked(self):
        # Review of #123, finding 5: the base is HEAD^1 of the checked-out merge commit; the payload's
        # base.sha must be its ancestor; with neither available the job fails closed.
        run = self.run_script()
        pull_request = run.split("pull_request)", 1)[1].split(";;", 1)[0]
        self.assertIn("first_parent=\"$(git rev-parse --verify --quiet 'HEAD^1^{commit}' || true)\"", pull_request)
        self.assertIn('git merge-base --is-ancestor "$payload" "$first_parent"', pull_request)
        self.assertIn('base="$first_parent"', pull_request)
        self.assertRegex(pull_request, r"\n +else\n +echo \"::error::verdict-review-gate: neither the merge commit's "
                                       r"first parent nor the payload base is available\"\n +exit 1\n +fi")
        self.assertRegex(pull_request, r"is not an ancestor of the merge commit's first parent \$first_parent\"\n"
                                       r" +exit 1\n")

    def test_pull_request_head_must_be_the_merge_commit_of_the_payload_head(self):
        # Fourth review, G4: HEAD^1 is the base only when HEAD is the PR merge commit; assert it.
        pull_request = self.run_script().split("pull_request)", 1)[1].split(";;", 1)[0]
        assertion = pull_request.split("first_parent=", 1)[0]
        self.assertIn("second_parent=\"$(git rev-parse --verify --quiet 'HEAD^2^{commit}' || true)\"", assertion)
        self.assertIn('[ "$second_parent" != "$PR_HEAD_SHA" ]', assertion)
        self.assertIn("git rev-parse --verify --quiet 'HEAD^3^{commit}'", assertion)
        self.assertRegex(assertion, r"failing closed\"\n +exit 1\n +fi")

    def run_gate_step(self, repository, head, pr_head, event="pull_request", base_ref="main"):
        """Execute the step's script in ``repository`` checked out at ``head``, with a stub python3
        that records the gate invocation instead of running it."""
        subprocess.run(["git", "-C", str(repository), "checkout", "--quiet", "--detach", head], check=True)
        scratch = Path(tempfile.mkdtemp())
        self.addCleanup(subprocess.run, ["rm", "-rf", str(scratch)])
        (scratch / "bin").mkdir()
        stub = scratch / "bin" / "python3"
        stub.write_text('#!/bin/sh\necho "gate-invoked $*"\n')
        stub.chmod(0o755)
        # Drops inherited GIT_* but keeps the package's hermetic config (no global hooks or auto maintenance).
        environment = tests.hermetic_git_environment()
        environment.update(PATH=f"{scratch / 'bin'}:{environment['PATH']}", EVENT_NAME=event,
                           PR_BASE_SHA=self.commits["base"], PR_HEAD_SHA=pr_head, PUSH_BEFORE_SHA="",
                           PR_BASE_REF=base_ref,
                           RUNNER_TEMP=str(scratch), GITHUB_WORKSPACE=str(repository),
                           GITHUB_STEP_SUMMARY=str(scratch / "summary.md"))
        return subprocess.run(["bash", "-c", self.run_script()], cwd=repository, env=environment,
                              capture_output=True, text=True)

    def make_pull_request_repository(self, gate="added"):
        """base -> pr1 -> pr2 on branch pr, and the merge of pr2 into base. ``gate`` places
        scripts/verdict_review_gate.py: "added" by pr1 (the PR that adds the gate), "base" already at
        the base, None nowhere."""
        repository = Path(tempfile.mkdtemp())
        self.addCleanup(subprocess.run, ["rm", "-rf", str(repository)])

        def git(*args):
            return subprocess.run(["git", "-C", str(repository), "-c", "user.name=fixture",
                                   "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", *args],
                                  check=True, capture_output=True, text=True).stdout.strip()

        git("init", "--quiet", "--initial-branch=main")
        commits = {}
        for name, branch in (("base", None), ("pr1", "pr"), ("pr2", None)):
            if branch:
                git("checkout", "--quiet", "-b", branch)
            (repository / f"{name}.txt").write_text(name)
            if (gate, name) in (("added", "pr1"), ("base", "base")):
                (repository / "scripts").mkdir()
                (repository / "scripts" / "verdict_review_gate.py").write_text("# gate\n")
            git("add", "-A")
            git("commit", "--quiet", "-m", name)
            commits[name] = git("rev-parse", "HEAD")
        git("checkout", "--quiet", "--detach", commits["base"])
        git("merge", "--quiet", "--no-ff", "-m", "merge", commits["pr2"])
        commits["merge"] = git("rev-parse", "HEAD")
        # actions/checkout with fetch-depth: 0 fetches +refs/heads/*:refs/remotes/origin/*.
        git("update-ref", "refs/remotes/origin/main", commits["base"])
        # A stacked branch on main's tip and a merge of the PR head into it: a merge commit left
        # built against the branch a retargeted PR came from.
        git("checkout", "--quiet", "-b", "stack", commits["base"])
        (repository / "stack.txt").write_text("stack")
        git("add", "-A")
        git("commit", "--quiet", "-m", "stack")
        git("merge", "--quiet", "--no-ff", "-m", "merge into stack", commits["pr2"])
        commits["stack_merge"] = git("rev-parse", "HEAD")
        git("checkout", "--quiet", "--detach", commits["merge"])
        self.commits = commits
        return repository

    def test_the_merge_commit_assertion_executes(self):
        repository = self.make_pull_request_repository()
        merge, pr1, pr2, base = (self.commits[name] for name in ("merge", "pr1", "pr2", "base"))
        passed = self.run_gate_step(repository, merge, pr2)
        self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
        self.assertIn(f"gate-invoked scripts/verdict_review_gate.py --root {repository} --base {base}", passed.stdout)
        for head, pr_head, case in ((pr2, pr2, "the PR head checked out instead of the merge commit"),
                                    (merge, pr1, "a merge commit of another PR head"),
                                    (merge, "", "no PR head in the payload")):
            with self.subTest(case):
                failed = self.run_gate_step(repository, head, pr_head)
                self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
                self.assertIn("HEAD is not the merge commit of the PR head", failed.stdout)
                self.assertNotIn("gate-invoked", failed.stdout)

    def test_a_pull_request_into_another_branch_fails_closed(self):
        # Review of #135, H1: a PR judged against another branch and then retargeted to main must not
        # carry a green gate; the edited run fails closed until the base is main.
        repository = self.make_pull_request_repository()
        merge, pr2 = self.commits["merge"], self.commits["pr2"]
        for base_ref in ("develop", "main-copy", ""):
            with self.subTest(base_ref=base_ref):
                failed = self.run_gate_step(repository, merge, pr2, base_ref=base_ref)
                self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
                self.assertIn(f"the pull request's base branch is '{base_ref}', not main", failed.stdout)
                self.assertNotIn("gate-invoked", failed.stdout)
        passed = self.run_gate_step(repository, merge, pr2, base_ref="main")
        self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
        self.assertIn("gate-invoked", passed.stdout)

    def test_a_merge_commit_built_on_another_branch_fails_closed(self):
        # Review of #135, round 2: the payload base.sha being an ancestor of HEAD^1 is not enough; a
        # merge commit whose first parent is a stacked branch containing main's tip would be judged
        # against that branch. HEAD^1 must be a commit on origin/main.
        repository = self.make_pull_request_repository()
        failed = self.run_gate_step(repository, self.commits["stack_merge"], self.commits["pr2"])
        self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
        self.assertIn("is not a commit on origin/main; failing closed", failed.stdout)
        self.assertNotIn("gate-invoked", failed.stdout)
        passed = self.run_gate_step(repository, self.commits["merge"], self.commits["pr2"])
        self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
        run = self.run_script()
        pull_request = run.split("pull_request)", 1)[1].split(";;", 1)[0]
        self.assertIn('git merge-base --is-ancestor "$base" "refs/remotes/origin/$PR_BASE_REF"', pull_request)

    def test_the_base_gate_runs_when_the_base_has_one(self):
        repository = self.make_pull_request_repository(gate="base")
        passed = self.run_gate_step(repository, self.commits["merge"], self.commits["pr2"])
        self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
        self.assertRegex(passed.stdout, r"gate-invoked \S+/gate-base/scripts/verdict_review_gate\.py --root ")
        self.assertNotIn("bootstrap", passed.stdout)

    def test_the_bootstrap_copy_runs_only_for_the_change_that_adds_the_gate(self):
        # Review of #135, L4: the head's own copy runs only when base...HEAD adds the file (A).
        repository = self.make_pull_request_repository(gate="added")
        passed = self.run_gate_step(repository, self.commits["merge"], self.commits["pr2"])
        self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
        self.assertIn("this change adds the gate; running this checkout's copy (bootstrap)", passed.stdout)
        self.assertIn(f"gate-invoked scripts/verdict_review_gate.py --root {repository}", passed.stdout)
        repository = self.make_pull_request_repository(gate=None)
        failed = self.run_gate_step(repository, self.commits["merge"], self.commits["pr2"])
        self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
        self.assertIn("has no scripts/verdict_review_gate.py and this change does not add it; failing closed",
                      failed.stdout)
        self.assertNotIn("gate-invoked", failed.stdout)

    def test_push_to_main_executes_the_gate_and_fails_closed_without_a_previous_commit(self):
        # Review of #123, finding 2 (accepted residual): the push-to-main run re-checks after merge.
        trigger = self.text.split("\non:\n", 1)[1].split("\n\n", 1)[0]
        self.assertRegex(trigger, r"(?m)^  push:\n    branches: \[main\]$")
        self.assertIsNone(block_if(self.job.split("\n    steps:\n", 1)[0]))
        self.assertIsNone(block_if(step_block(self.job, "Require sealed cross-family review")))
        run = self.run_script()
        push = run.split("push)", 1)[1].split(";;", 1)[0]
        self.assertIn('base="${PUSH_BEFORE_SHA:-}"', push)
        self.assertIn('if [ -z "$base" ] || [ -z "${base//0/}" ]; then', push)
        self.assertIn("exit 1", push)
        # Every event reaches the gate invocation: no branch of the case exits 0 or skips it.
        self.assertNotIn("exit 0", run)
        self.assertTrue(run.rstrip().endswith('python3 "$gate" --root "$GITHUB_WORKSPACE" --base "$base" '
                                              '| tee -a "$GITHUB_STEP_SUMMARY"'))

    def test_the_gate_that_runs_is_the_base_commits_copy(self):
        # Review of #123, finding 2: a pull request must not be judged by a gate it edited.
        run = self.run_script()
        self.assertIn('git worktree add --quiet --detach "$RUNNER_TEMP/gate-base" "$base"', run)
        self.assertIn('gate="$RUNNER_TEMP/gate-base/$gate"', run)
        self.assertIn('if git cat-file -e "$base:$gate"', run)
        self.assertIn('python3 "$gate" --root "$GITHUB_WORKSPACE" --base "$base"', run)
        self.assertIn("set -euo pipefail", run.split('python3 "$gate"', 1)[0])

    def test_no_dangerous_trigger_is_added_for_the_residual(self):
        # The accepted residual (the PR's own pr-metadata.yml can disable the job) is not closed with a
        # privileged trigger: zizmor's dangerous-triggers audit runs with --no-config --no-ignores.
        for workflow in WORKFLOWS.glob("*.yml"):
            text = workflow.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"(?m)^\s*(pull_request_target|workflow_run):", workflow.name)


class SupplyChainGateTests(unittest.TestCase):
    text = (WORKFLOWS / "supply-chain.yml").read_text(encoding="utf-8")

    def test_grype_policy_changes_trigger_the_gate_on_push_and_pull_request(self):
        self.assertIn("--config .grype.yaml --fail-on high", self.text)
        trigger = "\n" + self.text.split("\non:\n", 1)[1].split("\n\n", 1)[0]
        for event in ("push", "pull_request"):
            block = trigger.split(f"\n  {event}:\n", 1)[1].split("\n  schedule:", 1)[0].split("\n  pull_request:", 1)[0]
            self.assertIn("- '.grype.yaml'", block, event)

    def test_every_grype_ignore_names_a_review_date_that_has_not_passed(self):
        # grype ignore rules have no expiry field, so the reason carries `review-by: YYYY-MM-DD`.
        body = (ROOT / ".grype.yaml").read_text(encoding="utf-8").split("\nignore:", 1)[1]
        if body.strip() == "[]":
            return
        rules = re.split(r"(?m)^  - ", body)[1:]
        self.assertTrue(rules, "ignore must be [] or a list of rules")
        for rule in rules:
            match = re.search(r"reason:.*review-by: (\d{4}-\d{2}-\d{2})", rule)
            self.assertIsNotNone(match, rule)
            self.assertGreaterEqual(date.fromisoformat(match.group(1)), date.today(), rule)


class PinningTests(unittest.TestCase):
    def test_every_third_party_action_is_pinned_by_full_sha(self):
        unpinned = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                match = re.search(r"uses:\s*([^\s#]+)", line)
                # GitHub's $/ syntax resolves this action at the workflow's
                # exact running commit (2026-07-30 native rollout).
                if not match or match.group(1).startswith(("./", "$/")):
                    continue
                if not re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", match.group(1)):
                    unpinned.append(f"{path.name}:{line_number}: {match.group(1)}")
        self.assertEqual(unpinned, [])

    @staticmethod
    def imprecise_comments(name, text):
        """SHA-pinned `uses:` lines whose comment does not name an exact release."""
        return [f"{name}:{number}: {line.strip()}" for number, line in enumerate(text.splitlines(), 1)
                if re.search(r"uses:\s*[\w.-]+/[\w./-]+@[0-9a-f]{40}", line) and not EXACT_RELEASE_COMMENT.search(line)]

    def test_pin_comments_name_an_exact_release_outside_hash_frozen_workflows(self):
        # Offline guard for zizmor's online ref-version-mismatch audit. A HASH_FROZEN workflow would keep
        # its recorded bytes until its own evidence is re-run; none is frozen since 2026-09-26.
        found = [error for path in sorted(WORKFLOWS.glob("*.yml")) if path.name not in HASH_FROZEN
                 for error in self.imprecise_comments(path.name, path.read_text(encoding="utf-8"))]
        self.assertEqual(found, [])

    def test_the_comment_check_rejects_a_major_only_or_missing_comment(self):
        sha = "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
        text = "\n".join(f"      - uses: actions/upload-artifact@{sha}{comment}"
                         for comment in (" # v7.0.1", " # v7", "", " # latest"))
        self.assertEqual([error.split(":", 2)[1] for error in self.imprecise_comments("x.yml", text)], ["2", "3", "4"])


SHELL_BREAK = {"|", "||", "&&", ";", ">", ">>", "2>&1", "&>", "2>", "<"}
QUIET_FLAGS = {"-v", "-q", "-b", "-f", "-c", "--verbose", "--quiet", "--buffer", "--failfast", "--catch", "--locals"}
# Report options that take a value and select no test: `--durations N`, also spelled `--durations=N` (Python 3.12+,
# https://docs.python.org/3/library/unittest.html#cmdoption-unittest-durations).
VALUE_FLAGS = {"--durations"}


def unittest_invocations(job_text):
    """The argument lists of every ``python3 -m unittest`` command in a job's text."""
    found = []
    for match in re.finditer(r"python3? -m unittest\b([^\n]*)", job_text):
        args = []
        for token in match.group(1).split():
            if token in SHELL_BREAK or token.startswith((">", "2>", "|")):
                break
            args.append(token)
        found.append(args)
    return found


def runs_whole_suite(args):
    """True for the whole project suite: no module or pattern arguments, or ``discover``
    without ``-p`` over the default or ``tests`` start directory. Report options select no
    test, so QUIET_FLAGS and ``--durations N`` are left out before deciding."""
    rest, value_next = [], False
    for arg in args:
        if value_next:
            value_next = False
        elif arg in VALUE_FLAGS:
            value_next = True
        elif arg not in QUIET_FLAGS and arg.partition("=")[0] not in VALUE_FLAGS:
            rest.append(arg)
    if not rest:
        return True
    if rest[0] != "discover" or any(a in ("-p", "--pattern") for a in rest):
        return False
    start = next((rest[i + 1] for i, a in enumerate(rest[:-1]) if a in ("-s", "--start-directory")), ".")
    return start.rstrip("/") in (".", "tests")


def validate_shard_invocations(job_text):
    """Actual shard-run arguments, distinct from a serial ``-m unittest`` command.

    Kind-3 supersession: docs/decisions/2026-10-07-validate-module-shards.md.
    Planning and aggregation do not execute a shard and require no test provisioning.
    """
    text = re.sub(r"[ \t]*\\\n\s*", " ", uncommented(job_text))
    found = []
    for match in re.finditer(r"python3? scripts/validate_shards\.py run\b([^\n]*)", text):
        args = []
        for token in shlex.split(match.group(1)):
            if token in SHELL_BREAK or token.startswith((">", "2>", "|")):
                break
            args.append(token)
        found.append(args)
    return found


def runs_project_tests(job_text):
    """A serial whole-suite run or a module shard; both need the suite environment."""
    return (any(runs_whole_suite(args) for args in unittest_invocations(job_text))
            or bool(validate_shard_invocations(job_text)))


def checkout_steps(job_text):
    return [m.group(0) for m in re.finditer(r"(?ms)^      - [^\n]*\n(?:(?!^      - ).*\n?)*", job_text)
            if "actions/checkout@" in m.group(0)]


class WholeSuiteJobsCheckOutFullHistory(unittest.TestCase):
    """tests/test_release_pin_contents.py resolves the pinned release commit and tag, which a
    depth-1 clone of a main that has moved past the release does not contain (catalog-freshness
    run 35931645459), so serial suite jobs and each module shard must fetch full history."""

    def test_whole_suite_jobs_set_fetch_depth_zero(self):
        suite_jobs = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for job_id, job_text in jobs(path.read_text(encoding="utf-8")).items():
                if runs_project_tests(job_text):
                    suite_jobs.append(f"{path.name}:{job_id}")
                    checkouts = checkout_steps(job_text)
                    with self.subTest(job=f"{path.name}:{job_id}"):
                        self.assertTrue(checkouts, "runs the suite without a checkout step")
                        for step in checkouts:
                            self.assertRegex(step, r"(?m)^\s+fetch-depth:\s*0\s*(#.*)?$")
        self.assertIn("catalog-freshness.yml:freshness", suite_jobs)
        self.assertIn("validate.yml:validate", suite_jobs)

    def test_whole_suite_classification(self):
        cases = {(): True, ("-v",): True, ("discover",): True, ("discover", "-s", "tests"): True,
                 ("tests.test_x", "-v"): False, ("discover", "-s", "tools/token-report", "-p", "t.py", "-q"): False,
                 ("discover", "-s", "tools/token-report"): False, ("discover", "-p", "test_a*.py"): False,
                 ("--durations", "50"): True, ("-v", "--durations", "50"): True, ("--durations=50",): True,
                 ("--durations", "50", "tests.test_x"): False, ("discover", "-s", "tests", "--durations", "50"): True,
                 ("discover", "--durations", "50", "-p", "test_a*.py"): False}
        for args, whole in cases.items():
            with self.subTest(args=args):
                self.assertIs(runs_whole_suite(list(args)), whole)
        self.assertEqual(unittest_invocations("run: python3 -m unittest 2>&1 | tee log\n"), [[]])
        self.assertEqual(unittest_invocations("run: python3 -m unittest -v >full.log 2>&1\n"), [["-v"]])
        wrapped = 'timeout --signal=ABRT --kill-after=60s 55m \\\n  python3 -m unittest -v --durations 50 2>&1 | tee "$log"\n'
        self.assertEqual(unittest_invocations(wrapped), [["-v", "--durations", "50"]])


class SessionCalendarTestPrerequisites(unittest.TestCase):
    """The additional serial-suite interpreter installs the pinned calendar before testing."""

    def test_calendar_install_precedes_tests_in_every_mode(self):
        install_name = "Install the hash-locked session calendar"
        install_command = ("python3 -m pip install --require-hashes --only-binary=:all: "
                           "-r .github/requirements-calendar.txt")
        for workflow, job_id, test_steps in (
                ("catalog-freshness.yml", "freshness", ("Run project test suite",)),):
            with self.subTest(workflow=workflow):
                job = jobs((WORKFLOWS / workflow).read_text(encoding="utf-8"))[job_id]
                step = step_block(job, install_name)
                self.assertEqual(uncommented(run_block(step)).strip(), install_command)
                self.assertIsNone(block_if(step), "the dependency is required in every test mode")
                for test_step in test_steps:
                    self.assertLess(job.index(step), job.index(step_block(job, test_step)))


class WholeSuiteHeadroomAndDiagnostics(unittest.TestCase):
    """Linux suites keep duration diagnostics, faulthandler and bounded timeout headroom.
    The validate job also uploads its verbose log when a shard fails."""

    SUITE_STEPS = {
        "catalog-freshness.yml:freshness": "Run project test suite",
        "validate.yml:validate": "Test validation failure modes",
    }
    VALIDATE = "validate.yml:validate"
    UPLOAD_STEP = "Upload the verbose test suite log"

    @classmethod
    def setUpClass(cls):
        cls.jobs = {f"{path.name}:{job_id}": job_text for path in sorted(WORKFLOWS.glob("*.yml"))
                    for job_id, job_text in jobs(path.read_text(encoding="utf-8")).items()}

    def suite_step(self, key):
        return uncommented(step_block(self.jobs[key], self.SUITE_STEPS[key]))

    def suite_invocation(self, key):
        step = self.suite_step(key)
        if key == self.VALIDATE:
            self.assertEqual(unittest_invocations(step), [], "a shard is not a serial whole-suite command")
            found = validate_shard_invocations(step)
        else:
            found = [args for args in unittest_invocations(step) if runs_whole_suite(args)]
        self.assertEqual(len(found), 1, f"{key}: the named step has exactly one native suite/shard invocation")
        return found[0]

    def test_every_whole_suite_job_names_its_suite_step(self):
        found = {key for key, job_text in self.jobs.items()
                 if runs_project_tests(job_text)}
        self.assertEqual(found, set(self.SUITE_STEPS))

    def test_each_suite_lists_its_50_slowest_tests_with_faulthandler_on(self):
        for key in sorted(self.SUITE_STEPS):
            with self.subTest(key):
                args = self.suite_invocation(key)
                self.assertIn("--durations", args)
                self.assertEqual(args[args.index("--durations") + 1], "50")
                self.assertRegex(self.suite_step(key), r"(?m)^          PYTHONFAULTHANDLER: '1'$")

    def test_linux_suites_abort_five_minutes_before_the_job_limit(self):
        for key in sorted(self.SUITE_STEPS):
            with self.subTest(key):
                limit = int(re.search(r"(?m)^    timeout-minutes: (\d+)$", self.jobs[key]).group(1))
                script = re.sub(r"[ \t]*\\\n\s*", " ", self.suite_step(key))
                command = "scripts/validate_shards.py run" if key == self.VALIDATE else "-m unittest"
                self.assertIn(f"timeout --signal=ABRT --kill-after=60s {limit - 5}m python3 {command} ", script)
                self.assertIn("set -o pipefail", script, "tee would otherwise hide the exit status of timeout and unittest")


    def test_validate_uploads_its_verbose_log_even_when_the_suite_fails(self):
        from tests.test_workflow_policy import load_workflow

        self.assertIn("-v", self.suite_invocation(self.VALIDATE))
        log = re.search(r'\| tee "\$RUNNER_TEMP/([^"]+)"', self.suite_step(self.VALIDATE)).group(1)
        job = self.jobs[self.VALIDATE]
        upload = step_block(job, self.UPLOAD_STEP)
        self.assertEqual(block_if(upload), "always()")
        self.assertIn("uses: actions/upload-artifact@", upload)
        document = load_workflow("on: push\njobs:\n  validate:" + job)
        selected = [step for step in document["jobs"]["validate"]["steps"]
                    if self.UPLOAD_STEP in step.get("name", "")]
        self.assertEqual(len(selected), 1, "the selected diagnostic uploader is unique")
        inputs = selected[0].get("with")
        self.assertIsInstance(inputs, dict, "the uploader must declare its actual inputs")
        path = inputs.get("path")
        self.assertIsInstance(path, str, "the uploader must bind its diagnostic files to with.path")
        paths = [line.strip() for line in path.splitlines() if line.strip()]
        self.assertIn("${{ runner.temp }}/" + log, paths)
        self.assertIn("${{ runner.temp }}/suite/report.json", paths)
        name = inputs.get("name")
        self.assertIsInstance(name, str, "the uploader must declare its artifact name")
        self.assertIn("${{ matrix.shard }}", name, "each matrix cell must retain a distinct log and report")
        self.assertLess(job.index(self.SUITE_STEPS[self.VALIDATE]), job.index(self.UPLOAD_STEP))

    def test_validate_reports_native_counts_after_the_suite_without_changing_its_result(self):
        job = self.jobs[self.VALIDATE]
        summary = step_block(job, "Report unittest counts")
        self.assertEqual(block_if(summary), "always()")
        self.assertNotIn("continue-on-error", summary)
        self.assertLess(job.index(self.SUITE_STEPS[self.VALIDATE]), job.index("Report unittest counts"))
        self.assertLess(job.index("Report unittest counts"), job.index(self.UPLOAD_STEP))
        cases = [
            ("Ran 12 tests in 0.123s\n\nOK (skipped=2)\n", "ran 12 tests; skipped 2"),
            ("Ran 1 test in 0.123s\n\nFAILED (failures=1, skipped=1)\n", "ran 1 tests; skipped 1"),
            ("Ran 4 tests in 0.123s\n\nOK\n", "ran 4 tests; skipped 0"),
            ("Ran 4 tests in 0.123s\n\nFAILED (errors=1)\n", "ran 4 tests; skipped 0"),
            ("Ran 0 tests in 0.123s\n\nNO TESTS RAN\n", "ran 0 tests; skipped 0"),
            ("Ran 4 tests in 0.123s\n", "ran 4 tests; skipped unknown"),
            ("interrupted before unittest's summary\n", "ran unknown tests; skipped unknown"),
            (None, "ran unknown tests; skipped unknown"),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            log = directory / "suite/unittest-verbose.log"
            log.parent.mkdir()
            environment = {**os.environ, "RUNNER_TEMP": str(directory),
                           "GITHUB_STEP_SUMMARY": str(directory / "summary.md")}
            for contents, expected in cases:
                with self.subTest(log=contents):
                    if contents is None:
                        log.unlink(missing_ok=True)
                    else:
                        log.write_text(contents, encoding="utf-8")
                    result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", run_block(summary)],
                                            env=environment, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn(expected, (directory / "summary.md").read_text().splitlines()[-1])
            # An unwritable summary destination cannot turn a passing suite into a failing job.
            environment["GITHUB_STEP_SUMMARY"] = str(directory)
            result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", run_block(summary)],
                                    env=environment, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_validate_uploader_guard_rejects_renamed_or_missing_path_input(self):
        """Exercise the real guard with valid YAML mutations, not a duplicate path predicate."""
        target = "test_validate_uploads_its_verbose_log_even_when_the_suite_fails"
        job = self.jobs[self.VALIDATE]
        upload = step_block(job, self.UPLOAD_STEP)
        path_block = re.search(r"(?m)^          path: \|\n(?:            [^\n]*(?:\n|$))+", upload)
        self.assertIsNotNone(path_block, "the current uploader has a block-scalar path input")

        def guarded_result(candidate):
            case = type(self)(target)
            case.jobs = {**self.jobs, self.VALIDATE: candidate}
            result = unittest.TestResult()
            case.run(result)
            return result

        original = guarded_result(job)
        self.assertTrue(original.wasSuccessful(), original.failures + original.errors)
        for label, changed in (
                ("renamed with.path", upload.replace("          path: |", "          description: |", 1)),
                ("missing with.path", upload[:path_block.start()] + upload[path_block.end():])):
            with self.subTest(mutation=label):
                result = guarded_result(job.replace(upload, changed, 1))
                self.assertEqual(result.errors, [], result.errors)
                self.assertTrue(result.failures, f"the real uploader guard accepted {label}")


class ValidateShardWorkflowContract(unittest.TestCase):
    """The retained required name aggregates every matrix cell, including failed or cancelled cells.

    https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#needs-context
    https://docs.github.com/en/actions/using-jobs/using-a-matrix-for-your-jobs
    Contract supersession: docs/decisions/2026-10-07-validate-module-shards.md.
    """

    @classmethod
    def setUpClass(cls):
        cls.workflow = (WORKFLOWS / "validate.yml").read_text(encoding="utf-8")
        cls.jobs = jobs(cls.workflow)
        cls.shards = cls.jobs["validate"]
        cls.final = cls.jobs["validate-result"]

    def test_eight_distinct_native_shards_keep_every_cell_running(self):
        self.assertRegex(self.shards, r"(?m)^    name: validate-shard-\$\{\{ matrix\.shard \}\}$")
        self.assertRegex(self.shards, r"(?m)^      fail-fast: false$")
        matrix = re.search(r"(?m)^        shard: (\[[^\n]+\])$", self.shards)
        self.assertIsNotNone(matrix)
        self.assertEqual(json.loads(matrix.group(1)), list(range(8)))
        step = step_block(self.shards, "Test validation failure modes")
        self.assertIsNone(block_if(step), "every matrix cell must execute its assigned modules")
        self.assertNotIn("continue-on-error", uncommented(self.shards))
        self.assertEqual(unittest_invocations(step), [])
        (args,) = validate_shard_invocations(step)
        self.assertEqual(args[args.index("--shards") + 1], "8")
        self.assertEqual(args[args.index("--shard") + 1], "$VALIDATE_SHARD")
        self.assertIn("VALIDATE_SHARD: ${{ matrix.shard }}", step)

    def test_final_required_name_runs_after_failed_cancelled_or_skipped_dependencies(self):
        self.assertRegex(self.final, r"(?m)^    name: validate$")
        self.assertEqual(block_if(self.final), "always()")
        self.assertRegex(self.final, r"(?m)^    needs: validate$")
        self.assertNotIn("continue-on-error", uncommented(self.final))
        self.assertEqual(sum(bool(re.search(r"(?m)^    name: validate$", job))
                             for job in self.jobs.values()), 1)

    def test_validate_guard_rejects_failure_suppression_in_every_step(self):
        from tests.test_workflow_policy import load_workflow

        def guarded_result(candidate):
            case = type(self)("test_eight_distinct_native_shards_keep_every_cell_running")
            case.shards = candidate
            result = unittest.TestResult()
            case.run(result)
            return result

        original = guarded_result(self.shards)
        self.assertTrue(original.wasSuccessful(), original.failures + original.errors)
        steps = load_workflow(self.workflow)["jobs"]["validate"]["steps"]
        for index, step in enumerate(steps):
            with self.subTest(step=step["name"]):
                block = step_block(self.shards, step["name"])
                lines = [line for line in block.splitlines()
                         if not re.match(r"^        continue-on-error:", line)]
                lines.insert(1, "        continue-on-error: true")
                candidate = self.shards.replace(block, "\n".join(lines), 1)
                mutated = load_workflow("on: push\njobs:\n  validate:" + candidate)
                self.assertEqual(mutated["jobs"]["validate"]["steps"][index]["continue-on-error"], "true")
                result = guarded_result(candidate)
                self.assertEqual(result.errors, [], result.errors)
                self.assertTrue(result.failures, f"the real shard guard accepted suppression in {step['name']}")

    def test_final_step_passes_the_real_needs_result_and_attempt_scoped_reports(self):
        step = step_block(self.final, "Require complete discovery coverage and success from every shard")
        self.assertEqual(block_if(step), "always()")
        self.assertIn("VALIDATE_SHARDS_RESULT: ${{ needs.validate.result }}", step)
        script = re.sub(r"[ \t]*\\\n\s*", " ", run_block(step))
        self.assertIn("python3 scripts/validate_shards.py aggregate ", script)
        for argument in ('--reports "$RUNNER_TEMP/shards"', "--shards 8",
                         '--job-result "$VALIDATE_SHARDS_RESULT"', '--summary "$GITHUB_STEP_SUMMARY"'):
            self.assertIn(argument, script)
        self.assertNotRegex(script, r"\|\||continue-on-error|\bexit 0\b")
        download = step_block(self.final, "Download this attempt's shard reports and native logs")
        self.assertIn("pattern: validate-shard-${{ github.run_id }}-${{ github.run_attempt }}-*", download)
        self.assertIn("merge-multiple: false", download)
        self.assertIn("digest-mismatch: error", download)


@unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "the real final step uses bash and Git-bound reports")
class ValidateShardFinalStepRuns(unittest.TestCase):
    """Execute the workflow's actual aggregate command over reports from tiny native shards.

    The two fixture tests give an independent oracle for the final ran/skipped totals;
    the shard helper remains the supported TestLoader/TextTestRunner integration.
    No repository test suite or provisioner runs in this fixture.

    Native APIs: https://github.com/python/cpython/blob/v3.12.3/Lib/unittest/loader.py
    and https://github.com/python/cpython/blob/v3.12.3/Lib/unittest/runner.py.
    """

    @classmethod
    def setUpClass(cls):
        cls.scratch = Path(tempfile.mkdtemp(prefix="validate-shard-gate-"))
        cls.addClassCleanup(shutil.rmtree, cls.scratch, ignore_errors=True)
        cls.checkout = cls.scratch / "checkout"
        (cls.checkout / "tests").mkdir(parents=True)
        (cls.checkout / "scripts").mkdir()
        (cls.checkout / "tests/__init__.py").write_text("", encoding="utf-8")
        (cls.checkout / "tests/test_gate_fixture.py").write_text(
            "import unittest\n\nclass GateFixture(unittest.TestCase):\n"
            "    def test_passes(self):\n        self.assertEqual(2 + 2, 4)\n"
            "    @unittest.skip('synthetic gate control')\n"
            "    def test_skips(self):\n        self.fail('the skip must remain visible')\n", encoding="utf-8")
        for name in ("validate_shards.py", "validate_shard_weights.json"):
            shutil.copyfile(ROOT / "scripts" / name, cls.checkout / "scripts" / name)
        cls.environment = {key: value for key, value in os.environ.items()
                           if not key.startswith(("GITHUB_", "GIT_", "PYTHON"))}
        cls.environment.update(PATH=f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}",
                               PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        for args in (("init", "-q"), ("add", "."),
                     ("-c", "user.name=Shard fixture", "-c", "user.email=fixture@example.invalid",
                      "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", "commit", "-qm", "gate fixture")):
            subprocess.run(["git", *args], cwd=cls.checkout, env=cls.environment, check=True, capture_output=True)
        cls.reports = cls.scratch / "native-reports"
        for shard in range(8):
            report = cls.reports / f"validate-shard-fixture-{shard}" / "report.json"
            report.parent.mkdir(parents=True)
            proc = subprocess.run(
                [sys.executable, "scripts/validate_shards.py", "run", "--shard", str(shard),
                 "--shards", "8", "--report", str(report), "-v", "--durations", "50"],
                cwd=cls.checkout, env=cls.environment, capture_output=True, text=True, timeout=30)
            if proc.returncode:
                raise AssertionError(f"native fixture shard {shard} failed: {proc.stdout}\n{proc.stderr}")
        final = jobs((WORKFLOWS / "validate.yml").read_text(encoding="utf-8"))["validate-result"]
        cls.script = run_block(step_block(final, "Require complete discovery coverage and success from every shard"))

    def run_final(self, job_result="success", mutate=None):
        runner = Path(tempfile.mkdtemp(dir=self.scratch, prefix="attempt-"))
        shutil.copytree(self.reports, runner / "shards")
        if mutate is not None:
            mutate(runner / "shards")
        script = runner / "aggregate.sh"
        script.write_text(self.script, encoding="utf-8")
        environment = dict(self.environment, RUNNER_TEMP=str(runner),
                           GITHUB_STEP_SUMMARY=str(runner / "summary.md"), VALIDATE_SHARDS_RESULT=job_result)
        proc = subprocess.run(["bash", "-e", str(script)], cwd=self.checkout, env=environment,
                              capture_output=True, text=True, timeout=30)
        receipt = runner / "shards/aggregate.json"
        return proc, json.loads(receipt.read_text(encoding="utf-8")) if receipt.exists() else None, runner

    def test_final_step_reports_the_native_fixture_counts_and_complete_module_coverage(self):
        proc, receipt, _ = self.run_final()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIsNotNone(receipt, "the required check must retain its aggregate receipt")
        self.assertIs(receipt["success"], True)
        self.assertEqual(receipt["counts"], {"ran": 2, "failures": 0, "errors": 0, "skipped": 1,
                                           "expected_failures": 0, "unexpected_successes": 0})
        self.assertEqual(set(receipt["executed_modules"]), {"tests", "tests.test_gate_fixture"})

    def test_final_step_rejects_every_non_success_dependency_result(self):
        for state in ("failure", "cancelled", "skipped", ""):
            with self.subTest(state=state):
                proc, _, _ = self.run_final(job_result=state)
                self.assertNotEqual(proc.returncode, 0, "the required validate check accepted incomplete dependencies")

    def test_final_step_rejects_a_missing_shard_report(self):
        def remove_report(directory):
            next(directory.glob("*/report.json")).unlink()
        proc, _, _ = self.run_final(mutate=remove_report)
        self.assertNotEqual(proc.returncode, 0, "the workflow's aggregate command accepted seven of eight reports")

    def test_final_step_rejects_a_report_without_the_discovery_inventory(self):
        def remove_inventory(directory):
            report = next(directory.glob("*/report.json"))
            payload = json.loads(report.read_text(encoding="utf-8"))
            del payload["inventory"]
            report.write_text(json.dumps(payload), encoding="utf-8")
        proc, _, _ = self.run_final(mutate=remove_inventory)
        self.assertNotEqual(proc.returncode, 0, "the required check accepted a report with no discovery inventory")

    def test_final_step_rejects_an_assigned_module_missing_from_execution(self):
        def remove_executed_module(directory):
            for report in directory.glob("*/report.json"):
                payload = json.loads(report.read_text(encoding="utf-8"))
                if "tests.test_gate_fixture" in payload["assigned_modules"]:
                    payload["executed_modules"] = []
                    report.write_text(json.dumps(payload), encoding="utf-8")
                    return
            self.fail("native fixture reports contain no assignment for their test module")
        proc, _, _ = self.run_final(mutate=remove_executed_module)
        self.assertNotEqual(proc.returncode, 0, "the required check accepted an assigned module with no execution")

    def test_final_step_rejects_a_zero_count_with_native_test_starts(self):
        def erase_ran_count(directory):
            for report in directory.glob("*/report.json"):
                payload = json.loads(report.read_text(encoding="utf-8"))
                if payload["counts"]["ran"]:
                    payload["counts"]["ran"] = 0
                    report.write_text(json.dumps(payload), encoding="utf-8")
                    return
            self.fail("the native fixture did not report any started tests")
        proc, _, _ = self.run_final(mutate=erase_ran_count)
        self.assertNotEqual(proc.returncode, 0, "the required check accepted counters that omit native test starts")


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("bash") and shutil.which("timeout")
                     and shutil.which("git"),
                     "the Linux shard step uses bash, GNU timeout and a Git-bound report, as on ubuntu-24.04")
class ValidateSuiteStepTracesAHang(unittest.TestCase):
    """validate.yml's suite script run as the runner runs a step without `shell:` (`bash -e` over the script file), in
    a scratch checkout whose one test hangs, with the step's limit cut from minutes to 3 s. With the step's
    PYTHONFAULTHANDLER the log that the artifact uploads holds the hung test's traceback and the step fails with
    timeout's status 124; the control without the variable fails the same way and holds no traceback."""

    HANG = "import time\nimport unittest\n\n\nclass T(unittest.TestCase):\n    def test_hangs(self):\n        time.sleep(600)\n"

    def run_step(self, faulthandler):
        job = jobs((WORKFLOWS / "validate.yml").read_text(encoding="utf-8"))["validate"]
        step = step_block(job, WholeSuiteHeadroomAndDiagnostics.SUITE_STEPS["validate.yml:validate"])
        self.assertIn("PYTHONFAULTHANDLER: '1'", step)
        script, cut = re.subn(r"--kill-after=60s \d+m ", "--kill-after=5s 3s ", run_block(step))
        self.assertEqual(cut, 1, "the step has one limit to cut")
        scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        (scratch / "tests").mkdir()
        (scratch / "tests/__init__.py").write_text("", encoding="utf-8")
        (scratch / "tests/test_hang.py").write_text(self.HANG, encoding="utf-8")
        (scratch / "scripts").mkdir()
        for name in ("validate_shards.py", "validate_shard_weights.json"):
            shutil.copyfile(ROOT / "scripts" / name, scratch / "scripts" / name)
        # The real shard report binds its native Git HEAD. This fixture changes the
        # selected command, not the hang, signal, exit-code or traceback oracle.
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("GITHUB_", "GIT_", "PYTHON"))}
        environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        for args in (("init", "-q"), ("add", "."),
                     ("-c", "user.name=Shard fixture", "-c", "user.email=fixture@example.invalid",
                      "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", "commit", "-qm", "hang fixture")):
            subprocess.run(["git", *args], cwd=scratch, env=environment, check=True, capture_output=True)
        tools = scratch / "bin"
        tools.mkdir()
        (tools / "python3").write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n', encoding="utf-8")
        (tools / "python3").chmod(0o755)
        (scratch / "step.sh").write_text(script, encoding="utf-8")
        environment.update(PATH=f"{tools}{os.pathsep}{os.environ.get('PATH', '')}", PYTHONDONTWRITEBYTECODE="1",
                           RUNNER_TEMP=str(scratch / "runner-temp"), VALIDATE_SHARD="0")
        if faulthandler:
            environment["PYTHONFAULTHANDLER"] = "1"
        proc = subprocess.run(["bash", "-e", str(scratch / "step.sh")], cwd=scratch, env=environment,
                              capture_output=True, text=True, timeout=120)
        log = re.search(r'\| tee "\$RUNNER_TEMP/([^"]+)"', script).group(1)
        path = scratch / "runner-temp" / log
        return proc.returncode, path.read_text(encoding="utf-8") if path.exists() else None

    def test_a_hang_prints_the_hung_test_traceback_and_fails_the_step(self):
        code, log = self.run_step(faulthandler=True)
        self.assertEqual(code, 124, log)
        self.assertIn("Fatal Python error: Aborted", log)
        self.assertRegex(log, r'File "[^"]*test_hang\.py", line 7 in test_hangs')

    def test_control_without_faulthandler_the_hang_leaves_no_traceback(self):
        code, log = self.run_step(faulthandler=False)
        self.assertEqual(code, 124, log)
        self.assertIn("test_hangs (tests.test_hang.T", log, "the hung test started, so its traceback could have printed")
        self.assertNotIn("Fatal Python error", log)


class GitleaksConfigTestsRunInCI(unittest.TestCase):
    """The allowlist regression tests need a gitleaks binary, which only the secret-scan job installs
    (Codex review of #155): pin that the job runs them with the pinned binary and fails if it is absent."""

    def test_secret_scan_job_runs_the_gitleaks_config_tests_with_the_pinned_binary(self):
        job = jobs((WORKFLOWS / "validate.yml").read_text(encoding="utf-8"))["secret-scan"]
        step = step_block(job, "gitleaks allowlist regression tests")
        self.assertIn("GITLEAKS_TESTS_REQUIRED: '1'", step)
        self.assertIn('export PATH="$RUNNER_TEMP/gitleaks:$PATH"', step)
        self.assertRegex(step, r"python3 -m unittest tests\.test_gitleaks_config\b")
        install = job.index("Install checksum-verified pinned gitleaks")
        self.assertLess(install, job.index("gitleaks allowlist regression tests"),
                        "the tests must run after the pinned binary is installed")


class BetterleaksTrialJobTests(unittest.TestCase):
    """The non-required betterleaks trial beside secret-scan (plan move M3; receipt
    evidence/artifacts/betterleaks-parity-20260927/): it stays out of the required contexts and cannot be
    forced green past a verification, scanner or test-run error, reads only, runs bash with pipefail, runs
    cosign only after its digest check and betterleaks only after the signed checksums and the pinned digest
    verify, redacts both scans with gitleaks's archive and ignore-file behaviour, uploads nothing and never
    turns on live --validation requests. It is report-only through betterleaks's own --exit-code option
    and unittest's split of failures from errors, a scan that does not complete in the real fixture module
    is an error that fails the fixture step, and its step summary holds counts, never values. The
    repository carries none of the suppression channels that only betterleaks reads."""

    JOB = "secret-scan-betterleaks"
    job = jobs((WORKFLOWS / "validate.yml").read_text(encoding="utf-8"))[JOB]
    FIXTURE_CLASSES = ("GitleaksPresenceTests", "GitleaksConfigContextRestrictionTests",
                       "GitleaksIgnoreFingerprintTests")
    SCAN_STEPS = ("Scan git history", "Scan working tree")
    FIXTURE_STEP = "fixture tests with betterleaks"
    # Stands in for betterleaks 1.8.1's exit status (cmd/root.go at the v1.8.1 tag): --exit-code (line 82,
    # default 1) is the status for findings (lines 644-645), a scan error exits 1 whatever it says (lines
    # 640-641), and the report is written before either. STUB_MODE is clean, findings or scan-error.
    SCAN_STUB = textwrap.dedent("""\
        #!/usr/bin/env bash
        report="" exit_code=1
        while [ "$#" -gt 0 ]; do
          case "$1" in
            --report-path) report="$2"; shift ;;
            --report-path=*) report="${1#*=}" ;;
            --exit-code) exit_code="$2"; shift ;;
            --exit-code=*) exit_code="${1#*=}" ;;
          esac
          shift
        done
        case "$STUB_MODE" in
          clean) echo null > "$report"; exit 0 ;;
          findings) cp "$STUB_REPORT" "$report"; exit "$exit_code" ;;
          scan-error) cp "$STUB_REPORT" "$report"; exit 1 ;;
        esac
        exit 99
        """)
    VERSION_STUB = '#!/bin/sh\n[ "$1" = version ] && echo "${STUB_VERSION:-1.8.1}" && exit 0\nexit 99\n'
    # Stands in for tests/test_gitleaks_config.py: FIXTURE_OUTCOME names the outcomes to produce.
    FIXTURE_MODULE = textwrap.dedent('''\
        import atexit
        import os
        import unittest

        FLAGS = set(os.environ["FIXTURE_OUTCOME"].split("+"))


        class GitleaksPresenceTests(unittest.TestCase):
            pass


        class GitleaksConfigContextRestrictionTests(unittest.TestCase):
            pass


        class GitleaksIgnoreFingerprintTests(unittest.TestCase):
            pass


        def fails(self):
            self.fail("a detection difference")


        def errors(self):
            raise RuntimeError("not an assertion")


        if "ok" in FLAGS:
            GitleaksPresenceTests.test_ok = lambda self: None
        if "fail" in FLAGS:
            GitleaksConfigContextRestrictionTests.test_fail = fails
        if "error" in FLAGS:
            GitleaksConfigContextRestrictionTests.test_error = errors
        if "skip" in FLAGS:
            GitleaksIgnoreFingerprintTests.test_skip = lambda self: self.skipTest("lock busy")
        if "crash" in FLAGS:
            atexit.register(os._exit, 3)
        ''')
    # Stands in for betterleaks under the real fixture module; STUB_MODE is how each scan ends. Under
    # --exit-code 0 a completed scan exits 0 after writing its report (cmd/root.go at v1.8.1, lines 610-646),
    # so every mode but detections-missing is a scan that did not complete. SIGKILL stands for a signal: a
    # SIGSEGV would start the host's crash reporter.
    SCAN_END_STUB = textwrap.dedent("""\
        #!/usr/bin/env bash
        [ "$1" = version ] && echo 1.8.1 && exit 0
        report=""
        while [ "$#" -gt 0 ]; do
          [ "$1" = --report-path ] && report="$2"
          shift
        done
        case "$STUB_MODE" in
          detections-missing) echo null > "$report"; exit 0 ;;
          partial-scan) echo null > "$report"; exit 1 ;;
          scan-error) exit 1 ;;
          no-report) exit 0 ;;
          exit-139) exit 139 ;;
          killed) kill -KILL "$$" ;;
          deadlock) echo 'fatal error: all goroutines are asleep - deadlock!' >&2; exit 2 ;;
        esac
        exit 99
        """)

    def run_script(self, name):
        """A step's `run: |` script, as the file GitHub writes and runs."""
        block = step_block(self.job, name)
        return "\n".join(line[10:] for line in block.split("\n        run: |\n", 1)[1].splitlines()) + "\n"

    def run_step(self, name, stub, environment, cwd=None):
        """Run step ``name`` as GitHub runs the job's `shell: bash`: `bash --noprofile --norc -eo pipefail {0}`
        (workflow syntax, jobs.<job_id>.steps[*].shell). RUNNER_TEMP and GITHUB_STEP_SUMMARY are in scratch,
        ``stub`` is the betterleaks binary and `python3` is this interpreter. Returns the exit status, the
        output and the step summary."""
        scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        runner_temp = scratch / "runner-temp"
        (runner_temp / "betterleaks").mkdir(parents=True)
        tools = scratch / "bin"
        tools.mkdir()
        for path, text in ((runner_temp / "betterleaks" / "betterleaks", stub),
                           (tools / "python3", f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n')):
            path.write_text(text, encoding="utf-8")
            path.chmod(0o755)
        script = scratch / "step.sh"
        script.write_text(self.run_script(name), encoding="utf-8")
        summary = scratch / "summary.md"
        env = {"PATH": f"{tools}{os.pathsep}{os.environ.get('PATH', '')}", "HOME": str(scratch), "LC_ALL": "C",
               "PYTHONDONTWRITEBYTECODE": "1", "RUNNER_TEMP": str(runner_temp),
               "GITHUB_STEP_SUMMARY": str(summary), **environment}
        proc = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", str(script)], cwd=cwd or scratch,
                              env=env, capture_output=True, text=True, timeout=120)
        return (proc.returncode, proc.stdout + proc.stderr,
                summary.read_text(encoding="utf-8") if summary.exists() else "")

    def scans(self):
        """Each betterleaks scan command, with its backslash continuation lines joined."""
        lines, found = self.job.splitlines(), []
        for index, line in enumerate(lines):
            if re.search(r'/betterleaks" (?:git|dir) ', line):
                command = line.strip()
                while command.endswith("\\"):
                    index += 1
                    command = command[:-1] + " " + lines[index].strip()
                found.append(command)
        return found

    def test_is_not_a_required_context_and_cannot_be_forced_green(self):
        ruleset = __import__("json").loads((ROOT / ".github/main-ruleset.json").read_text(encoding="utf-8"))
        contexts = {check["context"] for rule in ruleset["rules"] if rule["type"] == "required_status_checks"
                    for check in rule["parameters"]["required_status_checks"]}
        self.assertIn("secret-scan", contexts)
        self.assertNotIn(self.JOB, contexts)
        self.assertNotRegex(self.job, r"(?m)^    name:", "a job name would become its check context")
        self.assertNotIn("continue-on-error", self.job)

    def test_read_only_hardened_and_uploads_nothing(self):
        self.assertEqual(scopes(self.job), [{"contents": "read"}])
        step = first_step(self.job)
        self.assertIn(HARDEN, step)
        self.assertIn("egress-policy: audit", step)
        self.assertIn("persist-credentials: false", step_block(self.job, "Check out repository"))
        self.assertNotIn("upload-artifact", self.job)
        self.assertNotIn("GH_TOKEN", self.job)

    def test_runs_bash_with_pipefail(self):
        """GitHub runs an unspecified shell as `bash -e {0}` and `shell: bash` as
        `bash --noprofile --norc -eo pipefail {0}` (workflow syntax, jobs.<job_id>.steps[*].shell), so only
        an explicit bash makes a check that fails inside a pipeline fail its step."""
        head, steps = self.job.split("\n    steps:\n", 1)
        self.assertRegex(head, r"(?m)^    defaults:\n      run:\n(?:        #.*\n)*        shell: bash[ \t]*$")
        self.assertNotRegex(steps, r"(?m)^\s+shell:", "a step must not override the job's bash default")

    def test_binaries_run_only_after_verification(self):
        cosign = step_block(self.job, "Install cosign")
        self.assertRegex(cosign, r"(?m)^          COSIGN_SHA256: [0-9a-f]{64}$")
        order = [cosign.index(marker) for marker in ('"$COSIGN_SHA256" "$RUNNER_TEMP/cosign/cosign" | sha256sum --check',
                                                     'chmod +x "$RUNNER_TEMP/cosign/cosign"',
                                                     '"$RUNNER_TEMP/cosign/cosign" version')]
        self.assertEqual(order, sorted(order))
        install = step_block(self.job, "Install betterleaks")
        order = [install.index(marker) for marker in ('cosign" verify-blob',
                                                      "sha256sum --check --ignore-missing --strict checksums.txt",
                                                      '"$BETTERLEAKS_SHA256" "$archive" | sha256sum --check',
                                                      "tar -xzf", "./betterleaks version")]
        self.assertEqual(order, sorted(order))
        verify_blob = install[order[0]:order[1]]
        for constraint in ("--bundle checksums.txt.sigstore.json",
                           '--certificate-identity-regexp "$SIGNER_IDENTITY_REGEXP"',
                           "--certificate-oidc-issuer https://token.actions.githubusercontent.com",
                           "--certificate-github-workflow-repository betterleaks/betterleaks",
                           '--certificate-github-workflow-ref "refs/tags/v${BETTERLEAKS_VERSION}"',
                           '--certificate-github-workflow-sha "$SIGNER_COMMIT"',
                           "--certificate-github-workflow-trigger push"):
            self.assertIn(constraint, verify_blob)
        self.assertIn(r"SIGNER_IDENTITY_REGEXP: '^https://github\.com/betterleaks/betterleaks/\.github/workflows/"
                      r"release\.yml@refs/tags/v1\.8\.1$'", install)
        self.assertRegex(install, r"(?m)^          SIGNER_COMMIT: [0-9a-f]{40}$")
        self.assertRegex(install, r"(?m)^          BETTERLEAKS_SHA256: [0-9a-f]{64}$")

    def test_later_steps_need_the_verified_install_and_both_scans_redact(self):
        self.assertIn("id: install", step_block(self.job, "Install betterleaks"))
        for name in ("fixture tests with betterleaks", "Scan git history", "Scan working tree"):
            self.assertEqual(block_if(step_block(self.job, name)),
                             "${{ !cancelled() && steps.install.outcome == 'success' }}", name)
        scans = self.scans()
        self.assertEqual([re.search(r'" (git|dir) ', scan).group(1) for scan in scans], ["git", "dir"])
        for scan in scans:
            # A bare --redact redacts 100%; --redact=0 would print values (cmd/root.go lines 94-95).
            self.assertRegex(scan, r"(?:^|\s)--redact(?:=100)?(?:\s|$)")
            self.assertIn("--config .gitleaks.toml", scan)
            # gitleaks 8.30.1 opens no archives by default (its cmd/root.go line 92) and betterleaks
            # 1.8.1 opens them to depth 8 (cmd/root.go line 103); an ignore-file path always loads the
            # reviewed fingerprints (cmd/root.go lines 450-455).
            self.assertIn("--max-archive-depth 0", scan)
            self.assertIn("--gitleaks-ignore-path .gitleaksignore", scan)
        self.assertNotIn("--validation", self.job)
        self.assertNotIn("--experiments", self.job)

    def test_findings_exit_0_through_the_scanners_own_option(self):
        """Report-only through betterleaks's own option: each scan passes --exit-code 0 (cmd/root.go line 82,
        default 1), which sets the exit status for findings only (lines 644-645). A scan error exits 1 before
        it is used (lines 640-641) and a report that cannot be written is fatal (line 636). Each scan step keeps
        that status and exits with it, at its end and nowhere else."""
        scans = self.scans()
        self.assertEqual(len(scans), 2)
        for scan in scans:
            self.assertEqual(re.findall(r"--exit-code(?:=|\s+)(\S+)", scan), ["0"], scan)
            self.assertTrue(scan.endswith(" || status=$?"), scan)
        for name in self.SCAN_STEPS:
            script = uncommented(self.run_script(name))
            self.assertEqual(re.findall(r"\bstatus=\S*", script), ["status=0", "status=$?"], name)
            self.assertEqual(re.findall(r"(?m)^\s*exit\b.*$", script), ['exit "$status"'], name)
            self.assertEqual(script.rstrip().splitlines()[-1], 'exit "$status"', name)

    @unittest.skipUnless(shutil.which("bash") and shutil.which("jq"), "the scan steps need bash and jq, as the runner has")
    def test_scan_steps_fail_only_on_a_scan_error_and_count_findings_by_rule(self):
        """With a stand-in scanner, each scan step exits 0 with findings or none and 1 on a scan error, and its
        step summary counts findings by rule without a value or a path."""
        sentinel = "-".join(("never", "in", "the", "summary"))
        scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        report = scratch / "report.json"
        report.write_text(json.dumps([{"RuleID": rule, "File": path, "StartLine": line, "Secret": sentinel,
                                       "Match": sentinel}
                                      for rule, path, line in (("rule-alpha", "one/first.txt", 3),
                                                               ("rule-alpha", "two/second.txt", 5),
                                                               ("rule-beta", "one/first.txt", 9))]),
                          encoding="utf-8")
        for name in self.SCAN_STEPS:
            for mode, expected in (("findings", 0), ("clean", 0), ("scan-error", 1)):
                with self.subTest(step=name, mode=mode):
                    rc, output, summary = self.run_step(name, self.SCAN_STUB,
                                                        {"STUB_MODE": mode, "STUB_REPORT": str(report)})
                    self.assertEqual(rc, expected, output)
                    self.assertNotIn(sentinel, output + summary)
                    self.assertNotIn("first.txt", summary)
                    counts = re.findall(r"(?m)^(Findings: \d+|- [\w-]+: \d+)$", summary)
                    self.assertEqual(counts, ["Findings: 0"] if mode == "clean"
                                     else ["Findings: 3", "- rule-alpha: 2", "- rule-beta: 1"], summary)
                    self.assertIn(f"betterleaks exit status: {expected}", summary)

    @unittest.skipUnless(shutil.which("bash"), "the fixture step needs bash, as the runner has")
    def test_fixture_step_reports_assertion_failures_and_fails_on_anything_else(self):
        """Over a stand-in test module, the fixture step exits 0 when every problem is an assertion failure.
        It fails on an error, on no test run (unittest exits 5 since Python 3.12), on any other unittest exit
        status and on a betterleaks version other than the pinned one. Its step summary holds unittest's
        counts and never a failure message."""
        checkout = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, checkout, ignore_errors=True)
        (checkout / "tests").mkdir()
        (checkout / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (checkout / "tests" / "test_gitleaks_config.py").write_text(self.FIXTURE_MODULE, encoding="utf-8")
        no_test_run = (5, "NO TESTS RAN") if sys.version_info >= (3, 12) else (0, "OK")
        for outcome, version, expected, status_line in (("ok", "1.8.1", 0, "OK"),
                                                        ("ok+fail", "1.8.1", 0, "FAILED (failures=1)"),
                                                        ("ok+fail+skip", "1.8.1", 0, "FAILED (failures=1, skipped=1)"),
                                                        ("ok+error", "1.8.1", 1, "FAILED (errors=1)"),
                                                        ("ok+fail+error", "1.8.1", 1, "FAILED (failures=1, errors=1)"),
                                                        ("ok+fail+crash", "1.8.1", 3, "FAILED (failures=1)"),
                                                        ("none", "1.8.1", *no_test_run),
                                                        ("ok", "1.8.0", 1, None)):
            with self.subTest(outcome=outcome, version=version):
                rc, output, summary = self.run_step(self.FIXTURE_STEP, self.VERSION_STUB,
                                                    {"FIXTURE_OUTCOME": outcome, "STUB_VERSION": version,
                                                     "GITLEAKS_TESTS_REQUIRED": "1"}, cwd=checkout)
                # Indented, so the stand-in's own FAIL:/ERROR: headers do not read as this test's.
                self.assertEqual(rc, expected, textwrap.indent(output, "    | "))
                if status_line is None:
                    self.assertEqual(summary, "", "the version check comes before the tests")
                    continue
                self.assertRegex(summary, r"(?m)^Ran \d+ tests? in [\d.]+s; ")
                self.assertIn(f"; {status_line}; unittest exit status ", summary)
                self.assertNotIn("a detection difference", summary)
                self.assertNotIn("not an assertion", summary)

    @unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "the fixture step needs bash and git, as the runner has")
    def test_fixture_step_fails_when_a_scan_does_not_complete_in_the_real_fixture_module(self):
        """Cross-family review (2026-09-28, P2): a scanner error must not pass the fixture step as a detection
        difference. The step runs over the real tests/test_gitleaks_config.py, copied with .gitleaks.toml and
        .gitleaksignore into a checkout outside any repository (the fingerprint test that commits in a worktree
        of HEAD skips there), and a stand-in scanner. A scan that does not complete (exit 1 with or without a
        report, 139, a signal, a Go runtime error whose message names a lock, exit 0 without a report) is a
        unittest error in every scanning test, so the step fails. A completed scan that misses the detections
        is a failure, which the step reports without failing."""
        checkout = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, checkout, ignore_errors=True)
        (checkout / "tests").mkdir()
        (checkout / "tests" / "__init__.py").write_text("", encoding="utf-8")
        for name in ("tests/test_gitleaks_config.py", ".gitleaks.toml", ".gitleaksignore"):
            shutil.copyfile(ROOT / name, checkout / name)
        environment = {"GITLEAKS_TESTS_REQUIRED": "1", "GIT_CEILING_DIRECTORIES": str(checkout.parent)}
        for mode in ("detections-missing", "partial-scan", "scan-error", "no-report", "exit-139", "killed", "deadlock"):
            with self.subTest(mode=mode):
                rc, output, summary = self.run_step(self.FIXTURE_STEP, self.SCAN_END_STUB,
                                                    {**environment, "STUB_MODE": mode}, cwd=checkout)
                # Indented, so the real module's own FAIL:/ERROR: headers do not read as this test's.
                quoted = textwrap.indent(output, "    | ")
                status = re.search(r"(?m)^Ran \d+ tests? in [\d.]+s; (.+); unittest exit status (\d+)$", summary)
                self.assertIsNotNone(status, quoted)
                if mode == "detections-missing":
                    self.assertEqual((rc, status.group(2)), (0, "1"), quoted)
                    self.assertRegex(status.group(1), r"^FAILED \(failures=[1-9]\d*(?:, skipped=\d+)?\)$", quoted)
                else:
                    self.assertEqual((rc, status.group(2)), (1, "1"), quoted)
                    self.assertRegex(status.group(1), r"^FAILED \(errors=[1-9]\d*(?:, skipped=\d+)?\)$", quoted)

    def test_fixture_tests_leave_out_the_unredacted_history_class(self):
        """Exactly the three fixture classes run. GitleaksBranchAncestryHistoryTests is left out: the job's
        redacted history scan covers that ground. Until 2026-09-28 that class also scanned without --redact
        and quoted its findings; it now redacts (tests/test_gitleaks_config.py ScannerErrorTests.test_f)."""
        step = step_block(self.job, "fixture tests with betterleaks")
        self.assertIn("GITLEAKS_TESTS_REQUIRED: '1'", step)
        self.assertEqual(len(unittest_invocations(self.job)), 1, "the fixture step is the job's only unittest run")
        (args,) = unittest_invocations(step)
        (module,) = re.findall(r"(?m)^\s*m=(\S+)\s*$", step)
        named = [arg.strip('"').replace("$m", module) for arg in args if arg not in QUIET_FLAGS]
        self.assertEqual(named, [f"tests.test_gitleaks_config.{name}" for name in self.FIXTURE_CLASSES])

    def test_no_suppression_channel_that_only_betterleaks_reads(self):
        """betterleaks 1.8.1 reads three suppression channels that gitleaks does not: a .betterleaksignore
        in the scanned directory (cmd/root.go lines 281-291 and 465-469), a .betterleaks.toml wherever a run
        gives no --config (lines 269-279), and an inline allow comment that names betterleaks
        (detect/detect.go lines 57 and 962). None of them gets the review that .gitleaksignore and
        .gitleaks.toml get, so none may exist."""
        tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True,
                                 check=True).stdout.decode("utf-8", "replace").split("\0")
        for name in (".betterleaksignore", ".betterleaks.toml"):
            self.assertFalse((ROOT / name).exists(), f"{name} at the repository root")
            self.assertEqual([path for path in tracked if path.rsplit("/", 1)[-1] == name], [], name)
        marker = "betterleaks" + ":allow"  # assembled, so this file does not carry the marker itself
        grep = subprocess.run(["git", "-C", str(ROOT), "grep", "-l", "-I", "-F", "-e", marker],
                              capture_output=True, text=True)
        self.assertEqual(grep.returncode, 1, f"{marker!r} in tracked files: {grep.stdout.split()} {grep.stderr}")


ADOPTION_BOOTSTRAP = WORKFLOWS / "adoption-bootstrap.yml"
CHANGES_STEP = "Detect which bootstrap-relevant paths changed"


def run_block(step_text):
    """A step's literal-block ``run: |`` script, dedented, with a trailing newline."""
    body = step_text.split("run: |\n", 1)[1].splitlines()
    indent = min(len(line) - len(line.lstrip(" ")) for line in body if line.strip())
    return "\n".join(line[indent:] for line in body) + "\n"


def changes_script(text=None):
    """The ``changes`` job's path-detection script from adoption-bootstrap.yml (or from ``text``)."""
    text = ADOPTION_BOOTSTRAP.read_text(encoding="utf-8") if text is None else text
    return run_block(step_block(jobs(text)["changes"], CHANGES_STEP))


class AdoptionBootstrapLinuxPolicyTests(unittest.TestCase):
    """Linux bootstrap stays path-gated on PRs and reachable on push, schedule and dispatch."""

    text = ADOPTION_BOOTSTRAP.read_text(encoding="utf-8")
    job_map = jobs(text)

    def test_pull_request_trigger_has_no_path_filter(self):
        trigger = self.text.split("\non:\n", 1)[1].split("\n\njobs:", 1)[0]
        pull_request = trigger.split("\n  pull_request:", 1)[1].split("\n  schedule:", 1)[0]
        self.assertNotIn("paths", pull_request)


    def test_nightly_schedule_is_daily_off_the_hour_and_half_hour(self):
        trigger = self.text.split("\non:\n", 1)[1].split("\njobs:\n", 1)[0]
        schedule = trigger.split("\n  schedule:\n", 1)[1].split("\n  workflow_dispatch:", 1)[0]
        self.assertEqual(re.findall(r"(?m)^    - cron: '([^']+)'", schedule), ["47 6 * * *"])
        self.assertRegex(trigger, r"(?m)^  push:\n    branches: \[main\]$")
        self.assertRegex(trigger, r"(?m)^  workflow_dispatch:\s*$")

    def test_bootstrap_linux_stays_path_gated_on_pull_request_and_still_runs_off_it(self):
        # Regression for "bootstrap jobs are skipped on push, schedule and dispatch"
        # (independent review of this branch, 2026-09-25): `needs: changes` alone applies
        # an implicit `success()`, and `changes` itself only runs `if:
        # github.event_name == 'pull_request'`, so on push/schedule/workflow_dispatch
        # `changes` is skipped and a bare `if: github.event_name != 'pull_request' ||
        # needs.changes.outputs.bootstrap == 'true'` (no status function) is never even
        # evaluated -- the implicit success() check fails first and the job is skipped
        # too. Confirmed live: dispatch run 36085789483 showed `changes` skipped and all
        # three bootstrap-* jobs completing as skipped (docs/decisions/
        # 2026-09-22-github-automation-closure.md, "validate-macos required
        # (2026-09-25)", "Measured (before the fix)"). The fix needs both a status
        # function (`!cancelled()` or `always()`) so the `if:` is evaluated at all when
        # `changes` was skipped, and `!= 'false'` rather than `== 'true'` so a `changes`
        # job that itself failed or was cancelled (empty output, not the string
        # `'false'`) still runs these jobs (`changes`' own fail-safe default is
        # `bootstrap=true`, never a skip).
        for job_id in ("bootstrap-linux",):
            job = self.job_map[job_id]
            self.assertIn("needs: changes", job, job_id)
            condition = block_if(job)
            self.assertIsNotNone(condition, job_id)
            self.assertRegex(condition, r"!cancelled\(\)|always\(\)",
                              f"{job_id}: if: needs a status function (!cancelled() or always()) "
                              f"or an implicit success() from `needs: changes` skips it whenever "
                              f"changes itself is skipped (every push/schedule/dispatch run); got: {condition!r}")
            self.assertIn("needs.changes.outputs.bootstrap != 'false'", condition, job_id)
            self.assertNotIn("needs.changes.outputs.bootstrap == 'true'", condition,
                              f"{job_id}: '== ' true would keep the fail-open behaviour a "
                              f"missing/empty output (changes skipped, failed or cancelled) needs "
                              f"'!= \\'false\\'' to avoid")
            self.assertIn("github.event_name != 'pull_request'", condition, job_id)

    def test_the_pre_fix_condition_text_fails_this_tests_own_assertions(self):
        # Proof the strengthened assertions above are not vacuous: the exact `if:` text
        # this branch shipped before the fix round (a bare `if:`, no status function, and
        # `== 'true'`) must fail them.
        pre_fix_condition = "github.event_name != 'pull_request' || needs.changes.outputs.bootstrap == 'true'"
        with self.assertRaises(AssertionError):
            self.assertRegex(pre_fix_condition, r"!cancelled\(\)|always\(\)")
        with self.assertRaises(AssertionError):
            self.assertIn("needs.changes.outputs.bootstrap != 'false'", pre_fix_condition)

    def test_changes_job_runs_only_on_pull_request_and_diffs_paths_matching_push(self):
        job = self.job_map["changes"]
        self.assertEqual(block_if(job), "github.event_name == 'pull_request'")
        # The push trigger's `paths:` list stays the source of truth this job's own
        # PATTERNS array must match once both are normalized to the same glob spelling;
        # this is a textual comparison of the two lists, not a re-derivation of GitHub's
        # own `paths:` matching semantics (a case pattern's single `*` matches `/`, so it
        # is a strictly wider match than `paths:`'s `**` -- always in the safe,
        # over-matching direction; see the job's own in-file comment).
        trigger = self.text.split("\non:\n", 1)[1].split("\n\njobs:", 1)[0]
        push = trigger.split("push:", 1)[1].split("pull_request:", 1)[0]
        push_paths = re.findall(r"(?m)^      - '([^']+)'$", push)
        self.assertTrue(push_paths)

        def normalize(path):
            # PATTERNS uses bash case-glob syntax ('adoption/*'); push uses
            # gitignore-style globs ('adoption/**'). Both mean "everything under".
            return path.replace("/**", "/*")

        # Extract only the detector's PATTERNS array.
        patterns_block = re.search(r"(?ms)^[ \t]+PATTERNS=\(\n(.*?)^[ \t]+\)$", job)
        self.assertIsNotNone(patterns_block, "the changes script's PATTERNS array")
        job_patterns = re.findall(r"(?m)^            '([^']+)'$", patterns_block.group(1))
        self.assertTrue(job_patterns)
        self.assertEqual(sorted(normalize(path) for path in push_paths), sorted(job_patterns))

    def test_changes_job_fails_safe_on_missing_shas_and_git_diff_errors(self):
        # Item 2/3 of the independent review: a missing payload SHA or a failed `git
        # diff` must still write bootstrap=true (never leave the job to fail and skip
        # the three bootstrap-* jobs through `needs:`), and the diff must be NUL-delimited
        # so a non-ASCII quoted filename still matches a PATTERNS glob. Since 2026-10-03 every
        # failure path calls fail_safe, which also writes macos=true for the historical full-mode classifier.
        job = self.job_map["changes"]
        script = step_block(job, CHANGES_STEP)
        (set_flags,) = re.findall(r"(?m)^\s+set (-\S+)(?: |$)", script)
        self.assertNotIn("e", set_flags, "set -e would abort before a failure path's own bootstrap=true write")
        # `shell: bash` runs as `bash -eo pipefail`, so errexit must be turned off explicitly.
        self.assertRegex(script, r"(?m)^\s+set \+e\s*$", "errexit is on under shell: bash unless the script runs set +e")
        self.assertIn('diff_file="$(mktemp)" || { fail_safe; exit 0; }', script)
        # Since 2026-10-03 the writes are grouped, `{ ...; } >> "$GITHUB_OUTPUT"` (shellcheck SC2129, which the
        # validate job's actionlint step runs). The executable detector controls pin the fail-safe value.
        self.assertIn('echo "bootstrap=true"', script)
        self.assertIn('} >> "$GITHUB_OUTPUT"', script)

        def if_block(needle):
            # A same-indentation-anchored match (not a naive string split on "fi", which
            # false-positives inside "$diff_file"): captures from the matched "if" line
            # through the "fi" at the same leading whitespace.
            match = re.search(rf"(?ms)^([ \t]*)if\b[^\n]*{re.escape(needle)}.*?\n(.*?)\n\1fi\b", script)
            self.assertIsNotNone(match, needle)
            return match.group(0)

        missing_sha_block = if_block('-z "${BASE_SHA:-}"')
        self.assertIn("fail_safe", missing_sha_block)
        self.assertIn("exit 0", missing_sha_block)
        self.assertIn("git diff -z --no-renames --name-only", script)
        diff_failure_block = if_block("git diff -z")
        self.assertIn("fail_safe", diff_failure_block)
        self.assertIn("exit 0", diff_failure_block)
        self.assertIn("read -r -d ''", script)


def write_tree(root, files):
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


class LinuxBootstrapChangesTests(unittest.TestCase):
    """Run the actual PR detector against scratch Git history, including failure controls."""

    BASE = {"README.md": "base\n", "docs/a.md": "a\n",
            "adoption/bootstrap-linux.sh": "#!/bin/bash\n", "tests/__init__.py": ""}

    @classmethod
    def setUpClass(cls):
        cls.script = changes_script()
        cls.repository = Path(tempfile.mkdtemp())
        cls.addClassCleanup(shutil.rmtree, cls.repository, ignore_errors=True)
        cls.git("init", "--quiet", "--initial-branch=main")
        write_tree(cls.repository, cls.BASE)
        cls.git("add", "-A")
        cls.git("commit", "--quiet", "-m", "base")
        cls.base = cls.git("rev-parse", "HEAD")

    @classmethod
    def git(cls, *args):
        return subprocess.run(["git", "-C", str(cls.repository), "-c", "user.name=fixture",
                               "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", *args],
                              check=True, capture_output=True, text=True, env=tests.hermetic_git_environment()
                              ).stdout.strip()

    def run_changes(self, changes=None, deletions=(), base=None, head=None, script=None):
        """Commit ``changes`` (path to text) and ``deletions`` on top of the base commit, check the result out,
        and run the script there with BASE_SHA and HEAD_SHA (``base``/``head`` override them). Returns the
        outputs as {key: value} (each key at most once) and the step summary."""
        self.git("checkout", "--quiet", "--force", "--detach", self.base)
        self.git("clean", "-dfxq")
        write_tree(self.repository, changes or {})
        for path in deletions:
            self.git("rm", "--quiet", path)
        self.git("add", "-A")
        self.git("commit", "--quiet", "--allow-empty", "-m", "pull request")
        head_sha = self.git("rev-parse", "HEAD")
        scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        step = scratch / "step.sh"
        step.write_text(self.script if script is None else script, encoding="utf-8")
        output, summary = scratch / "output", scratch / "summary.md"
        environment = tests.hermetic_git_environment()
        environment.update(BASE_SHA=self.base if base is None else base, HEAD_SHA=head_sha if head is None else head,
                           GITHUB_OUTPUT=str(output), GITHUB_STEP_SUMMARY=str(summary))
        proc = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", str(step)], cwd=self.repository,
                              env=environment, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        pairs = [line.partition("=")[::2] for line in output.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(sorted(key for key, _ in pairs), ["bootstrap"], pairs)
        return dict(pairs), summary.read_text(encoding="utf-8") if summary.exists() else ""

    def test_bootstrap_inputs_select_the_linux_job(self):
        for path in ("adoption/bootstrap-linux.sh", ".github/workflows/adoption-bootstrap.yml",
                     "manifests/evidence.json", "tests/test_adoption_example.py",
                     "adoption/naïve.md", "adoption/line\nbreak.md"):
            with self.subTest(path=path):
                outputs, _ = self.run_changes({path: "changed\n"})
                self.assertEqual(outputs["bootstrap"], "true")

    def test_unrelated_paths_skip_the_linux_job(self):
        for path in ("docs/a.md", "tests/test_unrelated.py"):
            with self.subTest(path=path):
                outputs, _ = self.run_changes({path: "changed\n"})
                self.assertEqual(outputs["bootstrap"], "false")

    def test_a_deleted_bootstrap_input_still_selects_the_job(self):
        outputs, _ = self.run_changes(deletions=("adoption/bootstrap-linux.sh",))
        self.assertEqual(outputs["bootstrap"], "true")

    def test_detector_errors_fail_open(self):
        for label, override in (("missing base", {"base": ""}), ("missing head", {"head": ""}),
                                ("diff error", {"base": "0" * 40})):
            with self.subTest(label=label):
                outputs, summary = self.run_changes({"docs/a.md": "changed\n"}, **override)
                self.assertEqual(outputs["bootstrap"], "true")
                self.assertIn("failed safe", summary)

    def test_the_fail_open_control_detects_a_closed_detector(self):
        self.assertEqual(self.script.count('echo "bootstrap=true"'), 1)
        broken = self.script.replace('echo "bootstrap=true"', 'echo "bootstrap=false"')
        outputs, _ = self.run_changes(base="")
        self.assertEqual(outputs["bootstrap"], "true")
        weak, _ = self.run_changes(base="", script=broken)
        with self.assertRaises(AssertionError):
            self.assertEqual(weak["bootstrap"], "true")


class NoWorkflowApprovesPullRequestsTests(unittest.TestCase):
    """`can_approve_pull_request_reviews` stays on because one toggle also lets GITHUB_TOKEN
    create the catalog-freshness `propose` PR (docs/decisions/2026-09-23-bot-pr-dispatch.md,
    "Approval guard (2026-09-25)"). Since the setting also lets any workflow approve a PR, these
    cross-workflow checks keep the approve capability unused: `pull-requests: write` only on
    `catalog-freshness.yml:propose` (whose exact scopes tests/test_catalog_freshness_propose.py
    pins), no `actions: write` (the scope `POST /actions/runs/{run_id}/approve` needs), and no
    review/approve call anywhere."""

    texts = {path.name: path.read_text(encoding="utf-8") for path in sorted(WORKFLOWS.glob("*.y*ml"))}

    def test_every_permissions_key_is_a_parsed_block(self):
        # permission_blocks() only parses block-form mappings; any other form would slip past the
        # scope checks below, so every non-comment `permissions:` key must be one it parsed, or the
        # empty mapping `{}`, which grants nothing.
        for name, text in self.texts.items():
            body = uncommented(text)
            self.assertNotIn("write-all", body, name)
            self.assertNotRegex(body, r"(?m)^\s*permissions:[ \t]*(?!\{\}[ \t]*$)[^\s#]", f"{name}: inline permissions form")
            keys = len(re.findall(r"(?m)^\s*permissions:", body))
            empty = len(re.findall(r"(?m)^\s*permissions:[ \t]*\{\}[ \t]*$", body))
            self.assertEqual(keys, len(permission_blocks(body)) + empty, f"{name}: unparsed permissions key")

    def test_pull_requests_write_is_granted_only_to_the_propose_job(self):
        grants = set()
        for name, text in self.texts.items():
            sections = {"<top-level>": text.split("\njobs:\n", 1)[0], **jobs(text)}
            for section, section_text in sections.items():
                if any(block.get("pull-requests") == "write" for block in scopes(section_text)):
                    grants.add(f"{name}:{section}")
        self.assertEqual(grants, {"catalog-freshness.yml:propose"})

    def test_no_workflow_holds_actions_write(self):
        for name, text in self.texts.items():
            for block in scopes(text):
                self.assertNotEqual(block.get("actions"), "write", name)

    def test_no_workflow_reviews_or_approves_a_pull_request(self):
        patterns = (r"gh\s+pr\s+review", r"--approve\b", r"pulls/[^/\s]+/reviews", r"\bAPPROVE\b",
                    r"(?mi)^\s*(?:- )?uses:\s*\S*approve")
        for name, text in self.texts.items():
            body = uncommented(text)
            for pattern in patterns:
                self.assertNotRegex(body, pattern, name)


class ActionsAllowListTests(unittest.TestCase):
    """The Actions allow-list target (docs/decisions/2026-09-22-github-automation-closure.md,
    "2026-09-25 re-check against current practice"): every `uses:` in every workflow is either
    GitHub-owned or matches .github/actions-permissions.json's own patterns_allowed, so moving
    the live allowed_actions setting from "all" to "selected" with that file's
    github_owned_allowed/patterns_allowed would not block anything this repository already runs."""

    permissions = __import__("json").loads((ROOT / ".github/actions-permissions.json").read_text(encoding="utf-8"))

    def test_settings_target_selected_actions_with_sha_pinning_required(self):
        self.assertEqual(self.permissions["allowed_actions"], "selected")
        self.assertIs(self.permissions["sha_pinning_required"], True)

    def test_every_uses_is_github_owned_or_in_the_pattern_allow_list(self):
        # Reuses PinningTests' own `uses:` extraction (the same regex, the same
        # per-line walk over every workflow file), skipping a local `./` or `$/` action and
        # a `docker://` one exactly as that scan does, then checks ownership instead
        # of the pin format.
        patterns = self.permissions["patterns_allowed"]
        not_allowed = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                match = re.search(r"uses:\s*([^\s#]+)", line)
                if not match:
                    continue
                target = match.group(1)
                if target.startswith(("./", "$/", "docker://")):
                    continue
                owner = target.split("/", 1)[0]
                if owner in {"actions", "github"}:
                    continue
                if any(fnmatch.fnmatch(target, pattern) for pattern in patterns):
                    continue
                not_allowed.append(f"{path.name}:{line_number}: {target}")
        self.assertEqual(not_allowed, [])


if __name__ == "__main__":
    unittest.main()
