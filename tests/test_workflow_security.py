"""Use native offline analysis; the unsafe workflow is never executed."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ZIZMOR = shutil.which("zizmor")


@unittest.skipUnless(ZIZMOR, "native zizmor unavailable; CI installs the pinned analyzer")
class WorkflowSecurityTests(unittest.TestCase):
    def analyze(self, workflow, directory):
        # No credential is needed for offline, local static analysis.
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
        try:
            findings = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(f"zizmor did not return JSON (exit {result.returncode}): "
                      f"{result.stderr[:2000]}")
        self.assertIsInstance(findings, list)
        return result, findings

    def test_published_workflow_has_no_offline_findings(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, findings = self.analyze(
                ROOT / ".github/workflows/validate.yml", Path(temporary),
            )
        self.assertEqual(result.returncode, 0, result.stderr[:2000])
        self.assertEqual(findings, [])

    def test_unsafe_fixture_reports_injection_and_unpinned_action(self):
        fixture = ROOT / "tests/fixtures/workflow-security/unsafe.yml.txt"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            workflow = directory / "unsafe.yml"
            original = fixture.read_bytes()
            workflow.write_bytes(original)
            result, findings = self.analyze(workflow, directory)
            self.assertEqual(workflow.read_bytes(), original)
        self.assertEqual(result.returncode, 14, result.stderr[:2000])
        identifiers = {finding["ident"] for finding in findings}
        self.assertTrue({"template-injection", "unpinned-uses"} <= identifiers,
                        identifiers)


if __name__ == "__main__":
    unittest.main()
