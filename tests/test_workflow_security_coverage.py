"""Regression coverage for workflows not analyzed by test_workflow_security.py.

That module hard-codes only validate.yml (kept as a separate, hash-frozen
evidence input for blueprints/convergence-practice/ci-security/experiment.json,
so it is intentionally not extended here). This module gives
catalog-freshness.yml and supply-chain.yml -- and, for completeness, every
other published workflow -- the same offline zizmor pass/fail assertion in
`python3 -m unittest`, not only in the validate job's directory-wide CI step.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ZIZMOR = shutil.which("zizmor")
WORKFLOWS_DIR = ROOT / ".github/workflows"


def _analyze(workflow, directory):
    environment = {
        key: value for key, value in os.environ.items()
        if key not in {"GH_TOKEN", "GITHUB_TOKEN", "ZIZMOR_GITHUB_TOKEN"}
    }
    result = subprocess.run(
        [ZIZMOR, "--offline", "--no-config", "--no-ignores", "--no-progress",
         "--persona", "regular", "--strict-collection", "--format", "json",
         "--cache-dir", str(directory / "cache"), str(workflow)],
        cwd=directory, env=environment, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=30, check=False,
    )
    return result


@unittest.skipUnless(ZIZMOR, "native zizmor unavailable; CI installs the pinned analyzer")
class NewWorkflowSecurityCoverageTests(unittest.TestCase):
    def test_all_published_workflows_are_listed_and_covered(self):
        actual = {path.name for path in WORKFLOWS_DIR.glob("*.yml")}
        expected = {
            "validate.yml",
            "token-report.yml",
            "catalog-freshness.yml",
            "supply-chain.yml",
            "native-service-reboot.yml",
            "native-foundation-e2e.yml",
            "native-offhost-restore.yml",
            "native-offhost-app-state.yml",
            "native-token-e2e.yml",
            "action-compatibility.yml",
            "publish-catalog.yml",
            "adoption-bootstrap.yml",
            "scorecard.yml",
            "security-scan.yml",
            "dependency-review.yml",
            "hardware-profile-smoke.yml",
            "receipt-staleness.yml",
            "saturation-tracking.yml",
        }
        self.assertEqual(
            actual, expected,
            "workflows/*.yml changed; update this test's coverage set to match",
        )

    def test_catalog_freshness_workflow_has_no_offline_findings(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = _analyze(WORKFLOWS_DIR / "catalog-freshness.yml", Path(temporary))
        try:
            findings = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(f"zizmor did not return JSON (exit {result.returncode}): "
                      f"{result.stderr[:2000]}")
        self.assertEqual(result.returncode, 0, result.stderr[:2000])
        self.assertEqual(findings, [])

    def test_supply_chain_workflow_has_no_offline_findings(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = _analyze(WORKFLOWS_DIR / "supply-chain.yml", Path(temporary))
        try:
            findings = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(f"zizmor did not return JSON (exit {result.returncode}): "
                      f"{result.stderr[:2000]}")
        self.assertEqual(result.returncode, 0, result.stderr[:2000])
        self.assertEqual(findings, [])

    def test_hardware_profile_smoke_workflow_has_no_offline_findings(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = _analyze(WORKFLOWS_DIR / "hardware-profile-smoke.yml", Path(temporary))
        try:
            findings = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(f"zizmor did not return JSON (exit {result.returncode}): "
                      f"{result.stderr[:2000]}")
        self.assertEqual(result.returncode, 0, result.stderr[:2000])
        self.assertEqual(findings, [])

    def test_saturation_tracking_workflow_has_no_offline_findings(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = _analyze(WORKFLOWS_DIR / "saturation-tracking.yml", Path(temporary))
        try:
            findings = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(f"zizmor did not return JSON (exit {result.returncode}): "
                      f"{result.stderr[:2000]}")
        self.assertEqual(result.returncode, 0, result.stderr[:2000])
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
