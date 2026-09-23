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
import re
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
        for context in ("validate", "token-report", "secret-scan", "dependency-review", "osv-scanner"):
            self.assertEqual(contexts.get(context), 15368, context)
        self.assertEqual(len(self.rule("code_scanning")), 1)


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
