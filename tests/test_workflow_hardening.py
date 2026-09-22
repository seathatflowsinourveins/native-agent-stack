"""Regression tests for the 2026-09-22 Actions hardening (docs/decisions/2026-09-22-actions-hardening.md).

Text-level checks (no YAML dependency): every job that downloads or installs software starts with
step-security/harden-runner in audit mode; Scorecard is report-only with read-only permissions;
dependency review runs on pull requests only and never blocks; every third-party action is pinned
by a full commit SHA.
"""

from pathlib import Path
import hashlib
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
DOWNLOAD = re.compile(r"\b(curl|wget)\b|pip(3)? install|\buv (sync|pip|tool)|\bnpm (ci|install)|apt-get install")
HARDEN = "step-security/harden-runner@"
# Workflows whose exact bytes are pinned by retained evidence plans; editing them would invalidate
# that evidence (tests/test_active_recovery_plans.py), so they stay unhardened until re-run.
HASH_FROZEN = {
    "native-offhost-app-state.yml": "blueprints/convergence-practice/offhost-app-state/plan.json",
    "native-offhost-restore.yml": "blueprints/convergence-practice/offhost-restore/hosted-plan.json",
}


def jobs(text):
    """Return {job_id: job_text} for the top-level jobs mapping."""
    body = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"(?m)^  ([A-Za-z0-9_-]+):\s*$", body)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def first_step(job_text):
    steps = job_text.split("\n    steps:\n", 1)
    if len(steps) < 2:
        return ""
    match = re.search(r"(?ms)^      - (.*?)(?=^      - |\Z)", steps[1])
    return match.group(1) if match else ""


class HardenRunnerTests(unittest.TestCase):
    def test_every_downloading_job_starts_with_harden_runner_in_audit_mode(self):
        missing = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            if path.name in HASH_FROZEN:
                continue
            for job_id, job_text in jobs(path.read_text(encoding="utf-8")).items():
                if "runs-on: ubuntu" not in job_text or not DOWNLOAD.search(job_text):
                    continue
                step = first_step(job_text)
                if HARDEN not in step or "egress-policy: audit" not in step:
                    missing.append(f"{path.name}:{job_id}")
        self.assertEqual(missing, [], "downloading ubuntu jobs without a first-step harden-runner audit")

    def test_hash_frozen_exemptions_are_still_pinned(self):
        for name, plan in HASH_FROZEN.items():
            digest = hashlib.sha256((WORKFLOWS / name).read_bytes()).hexdigest()
            self.assertIn(digest, (ROOT / plan).read_text(encoding="utf-8"), f"{name} is no longer pinned by {plan}")

    def test_harden_runner_never_blocks_egress(self):
        for path in WORKFLOWS.glob("*.yml"):
            self.assertNotIn("egress-policy: block", path.read_text(encoding="utf-8"), path.name)


class ScorecardTests(unittest.TestCase):
    text = (WORKFLOWS / "scorecard.yml").read_text(encoding="utf-8")

    def test_results_are_not_published(self):
        self.assertIn("publish_results: false", self.text)
        self.assertNotIn("publish_results: true", self.text)

    def test_permissions_are_read_only(self):
        self.assertRegex(self.text, r"(?m)^permissions:\n  contents: read\s*$")
        for escalation in ("security-events: write", "id-token: write", "contents: write"):
            self.assertNotIn(escalation, self.text)


class DependencyReviewTests(unittest.TestCase):
    text = (WORKFLOWS / "dependency-review.yml").read_text(encoding="utf-8")

    def test_runs_on_pull_requests_only_and_never_blocks(self):
        trigger = self.text.split("\non:\n", 1)[1].split("\n\n", 1)[0]
        self.assertEqual([line.strip() for line in trigger.splitlines() if line.strip()], ["pull_request:"])
        self.assertIn("warn-only: true", self.text)
        self.assertNotIn("contents: write", self.text)


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
