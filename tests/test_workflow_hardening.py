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
import hashlib
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
HARDEN = "step-security/harden-runner@"
UPLOAD_SARIF = "github/codeql-action/upload-sarif@"
# Workflows whose exact bytes are pinned by retained evidence; editing them would detach that
# evidence from the file, so their jobs stay unhardened until the evidence is re-run. Each maps
# to a file that records the workflow's current SHA-256.
HASH_FROZEN = {
    # plan.json frozen_sources, enforced by tests/test_active_recovery_plans.py
    "native-offhost-app-state.yml": "blueprints/convergence-practice/offhost-app-state/plan.json",
    # hosted-plan.json, enforced by tests/test_active_recovery_plans.py
    "native-offhost-restore.yml": "blueprints/convergence-practice/offhost-restore/hosted-plan.json",
    # four dated execution receipts record it (docs/github-automation-evidence.json)
    "native-token-e2e.yml": "evidence/artifacts/portable-userspace-install-20260921/token-clean-install/receipt.json",
}
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

    def test_adoption_bootstrap_macos_jobs_are_not_exempt(self):
        # Regression guard: MACOS_JOBS_OWNED_ELSEWHERE must never grow to
        # cover this project's own macOS jobs (only a file owned by a
        # different, concurrent task belongs there); this enumerates them
        # explicitly so a future edit to the exemption set alone cannot
        # silently drop this coverage.
        for job_id in ("bootstrap-macos", "bootstrap-macos-brew", "validate-macos"):
            self.assertNotIn(f"adoption-bootstrap.yml:{job_id}", MACOS_JOBS_OWNED_ELSEWHERE)
        text = (WORKFLOWS / "adoption-bootstrap.yml").read_text(encoding="utf-8")
        job_map = jobs(text)
        for job_id in ("bootstrap-macos", "bootstrap-macos-brew", "validate-macos"):
            self.assertIn(job_id, job_map)
            step = first_step(job_map[job_id])
            self.assertIn(HARDEN, step, job_id)
            self.assertIn("egress-policy: audit", step, job_id)

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
        for name, pin in HASH_FROZEN.items():
            digest = hashlib.sha256((WORKFLOWS / name).read_bytes()).hexdigest()
            self.assertIn(digest, (ROOT / pin).read_text(encoding="utf-8"), f"{name} is no longer pinned by {pin}")

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
        self.assertEqual(scopes(self.text.split("\njobs:\n", 1)[0]), [{"contents": "read"}])
        job = jobs(self.text)["analysis"]
        self.assertEqual(scopes(job), [{"contents": "read", "security-events": "write"}])
        self.assertNotRegex(self.text, r"(?m)permissions:[ \t]*[^\s#]", "no inline read-all/write-all form")

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
        blocks = permission_blocks(self.text)
        self.assertGreaterEqual(len(blocks), 1)
        for block in blocks:
            self.assertEqual(block, {"contents": "read"})
        self.assertNotRegex(self.text, r"(?m)permissions:[ \t]*[^\s#]", "no inline read-all/write-all form")


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
        self.assertEqual(scopes(self.text.split("\njobs:\n", 1)[0]), [{"contents": "read"}])
        expected = {"osv-scanner": [{"contents": "read"}],
                    "osv-sarif-upload": [{"contents": "read", "security-events": "write"}],
                    "zizmor-online": [{"contents": "read"}],
                    "zizmor-sarif-upload": [{"contents": "read", "security-events": "write"}]}
        self.assertEqual({job_id: scopes(job) for job_id, job in jobs(self.text).items()}, expected)
        self.assertNotRegex(self.text, r"(?m)permissions:[ \t]*[^\s#]", "no inline read-all/write-all form")

    def test_the_write_token_never_reaches_an_installed_tool(self):
        self.assertIn("GH_TOKEN: ${{ github.token }}", jobs(self.text)["zizmor-online"])
        for tool_job, upload_job in (("osv-scanner", "osv-sarif-upload"), ("zizmor-online", "zizmor-sarif-upload")):
            upload = jobs(self.text)[upload_job]
            self.assertIn(f"needs: {tool_job}", upload, upload_job)
            self.assertNotRegex(upload, r"(?m)^\s+(- )?run:", f"{upload_job} (write scope) runs no shell step")
            actions = re.findall(r"uses: ([\w.-]+/[\w./-]+)@", upload)
            self.assertEqual(actions, ["step-security/harden-runner", "actions/checkout",
                                       "actions/download-artifact", "github/codeql-action/upload-sarif"], upload_job)

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
        self.assertIn("category: osv-scanner", upload)

    def test_zizmor_online_skips_pull_requests_and_reports_without_failing(self):
        job = jobs(self.text)["zizmor-online"]
        self.assertIn("if: github.event_name != 'pull_request'", job)
        self.assertIn("-r .github/requirements-ci.lock", job)
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
        for label, block in (("OSV SARIF artifact step", step_block(osv_job, "Keep the OSV-Scanner SARIF for the upload job")),
                             ("osv-sarif-upload job", jobs(self.text)["osv-sarif-upload"])):
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


class PublishReleaseTests(unittest.TestCase):
    text = (WORKFLOWS / "publish-catalog.yml").read_text(encoding="utf-8")

    def test_release_job_is_tag_only_after_publish_with_contents_write_only(self):
        job = jobs(self.text)["release"]
        self.assertIn("needs: publish", job)
        self.assertIn("startsWith(github.ref, 'refs/tags/v')", job.split("\n    if:", 1)[1].split("\n", 1)[0])
        self.assertEqual(scopes(job), [{"contents": "write"}])
        self.assertEqual(scopes(self.text.split("\njobs:\n", 1)[0]), [{"contents": "read"}])
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
        for context in ("validate", "token-report", "secret-scan", "dependency-review", "osv-scanner",
                        "verdict-review-gate"):
            self.assertEqual(contexts.get(context), 15368, context)
        self.assertEqual(len(self.rule("code_scanning")), 1)


class VerdictReviewGateTests(unittest.TestCase):
    """The required verdict-review-gate job (docs/decisions/2026-09-22-github-automation-closure.md,
    "verdict-review-gate (2026-09-23)")."""

    text = (WORKFLOWS / "validate.yml").read_text(encoding="utf-8")
    job = jobs(text)["verdict-review-gate"]

    def test_runs_on_every_pull_request_without_a_path_filter(self):
        trigger = self.text.split("\non:\n", 1)[1].split("\n\n", 1)[0]
        self.assertRegex(trigger, r"(?m)^  pull_request:[ \t]*$")
        self.assertNotIn("paths", trigger)
        self.assertNotIn("branches", trigger.split("pull_request:", 1)[1].split("workflow_dispatch:", 1)[0])
        self.assertIn("push:", trigger)
        self.assertIsNone(block_if(self.job), "a required check must run on every event")

    def test_read_only_hardened_and_without_persisted_credentials(self):
        self.assertEqual(scopes(self.job), [{"contents": "read"}])
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
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
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
        self.assertIsNone(block_if(self.job))
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
        # The accepted residual (the PR's own validate.yml can disable the job) is not closed with a
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
                if not match or match.group(1).startswith("./"):
                    continue
                if not re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", match.group(1)):
                    unpinned.append(f"{path.name}:{line_number}: {match.group(1)}")
        self.assertEqual(unpinned, [])


if __name__ == "__main__":
    unittest.main()
