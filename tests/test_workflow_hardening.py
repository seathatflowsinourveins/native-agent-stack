"""Regression tests for the 2026-09-22 Actions hardening (docs/decisions/2026-09-22-actions-hardening.md).

Text-level checks (no YAML dependency; when PyYAML is importable the job parser is cross-checked
against it): every ubuntu job starts with step-security/harden-runner in audit mode unless its
workflow's exact bytes are pinned by retained evidence; Scorecard is report-only with read-only
permissions; dependency review runs on pull requests only and never blocks; every third-party
action is pinned by a full commit SHA.
"""

from pathlib import Path
import hashlib
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
HARDEN = "step-security/harden-runner@"
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
# harden-runner supports Linux runners only.
UNSUPPORTED_RUNNER = re.compile(r"runs-on:\s*macos-")


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


def permission_blocks(text):
    """Every block-form permissions mapping in a workflow, as {scope: access} dicts."""
    blocks = []
    for match in re.finditer(r"(?m)^( *)permissions:[ \t]*\n((?:\1  [^\n]*\n)+)", text):
        entries = [line.strip().split(":", 1) for line in match.group(2).splitlines() if line.strip()]
        blocks.append({key.strip(): value.strip() for key, value in entries})
    return blocks


class HardenRunnerTests(unittest.TestCase):
    def test_every_ubuntu_job_starts_with_harden_runner_in_audit_mode(self):
        unclassified, missing = [], []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for job_id, job_text in jobs(path.read_text(encoding="utf-8")).items():
                name = f"{path.name}:{job_id}"
                if UNSUPPORTED_RUNNER.search(job_text):
                    continue
                if not re.search(r"runs-on:\s*ubuntu-\d", job_text):
                    unclassified.append(name)
                    continue
                if path.name in HASH_FROZEN:
                    continue
                step = first_step(job_text)
                if HARDEN not in step or "egress-policy: audit" not in step:
                    missing.append(name)
        self.assertEqual(unclassified, [], "jobs whose runner is neither a literal ubuntu nor macos label")
        self.assertEqual(missing, [], "ubuntu jobs without a first-step harden-runner audit")

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

    def test_every_permissions_block_is_exactly_contents_read(self):
        blocks = permission_blocks(self.text)
        self.assertGreaterEqual(len(blocks), 1)
        for block in blocks:
            self.assertEqual(block, {"contents": "read"})
        self.assertNotRegex(self.text, r"(?m)permissions:[ \t]*[^\s#]", "no inline read-all/write-all form")


class DependencyReviewTests(unittest.TestCase):
    text = (WORKFLOWS / "dependency-review.yml").read_text(encoding="utf-8")

    def test_runs_on_pull_requests_only_and_never_blocks(self):
        trigger = self.text.split("\non:\n", 1)[1].split("\n\n", 1)[0]
        self.assertEqual([line.strip() for line in trigger.splitlines() if line.strip()], ["pull_request:"])
        self.assertIn("warn-only: true", self.text)
        for block in permission_blocks(self.text):
            self.assertEqual(block, {"contents": "read"})


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
