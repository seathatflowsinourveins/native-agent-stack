"""Negative control for gap ci-supply-chain[0].

Every other zizmor test in this repository asserts a *clean* result on
published workflows, plus template-injection/unpinned-uses findings on an
inert unsafe fixture. None of that retained evidence exercises zizmor's
excessive-permissions audit, so the scoped-permissions axis rested on
configuration and source review rather than on native analyzer execution
(docs/catalog-provenance.md lines 20-24; automation.json line 254).

This test runs the installed zizmor offline against a fixture that declares
workflow-level `permissions: write-all` and a needless job-level
`contents: write`, and asserts the excessive-permissions finding actually
fires with High severity. The fixture is never executed; it is kept outside
.github/workflows (as a .yml.txt file, matching the existing
tests/fixtures/workflow-security/unsafe.yml.txt convention).

FIX ROUND CORRECTION (2026-09-23): the original module docstring claimed
excessive-permissions "does not fire under the default 'regular' persona
used elsewhere in this repository" as a general property of the audit. That
is only true for this specific fixture shape, where the fixture's single job
declares its own (narrower) permissions block -- zizmor appears to downgrade
the workflow-level excessive-permissions finding to pedantic persona in that
case. A second fixture (multi-job-no-job-permissions.yml.txt: two jobs,
neither declaring job-level permissions) shows excessive-permissions DOES
fire under --persona regular when no job overrides workflow-level
permissions; see test_multi_job_fixture_triggers_under_regular_persona
below. So --persona pedantic is required specifically for fixtures shaped
like this repository's negative-control.yml.txt (a job that declares its
own permissions), not for excessive-permissions in general.
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
FIXTURE = (
    ROOT
    / "blueprints/gap-wave2-20260923/zizmor-negative-control/negative-control.yml.txt"
)
MULTI_JOB_FIXTURE = (
    ROOT
    / "blueprints/gap-wave2-20260923/zizmor-negative-control/multi-job-no-job-permissions.yml.txt"
)


@unittest.skipUnless(ZIZMOR, "native zizmor unavailable; CI installs the pinned analyzer")
class ZizmorNegativeControlTests(unittest.TestCase):
    def analyze(self, workflow, directory, persona="pedantic"):
        environment = {
            key: value for key, value in os.environ.items()
            if key not in {"GH_TOKEN", "GITHUB_TOKEN", "ZIZMOR_GITHUB_TOKEN"}
        }
        result = subprocess.run(
            [ZIZMOR, "--offline", "--no-config", "--no-ignores", "--no-progress",
             "--persona", persona, "--strict-collection", "--format", "json",
             "--cache-dir", str(directory / "cache"), str(workflow)],
            cwd=directory, env=environment, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=30, check=False,
        )
        try:
            findings = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(
                f"zizmor did not return JSON (exit {result.returncode}): "
                f"{result.stderr[:2000]}"
            )
        self.assertIsInstance(findings, list)
        return result, findings

    def test_fixture_declares_write_all_and_a_needless_job_level_grant(self) -> None:
        text = FIXTURE.read_text(encoding="utf-8")
        self.assertIn("permissions: write-all", text)
        self.assertIn("contents: write", text)

    def test_negative_control_triggers_excessive_permissions_finding(self) -> None:
        original = FIXTURE.read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            workflow = directory / "negative-control.yml"
            workflow.write_bytes(original)
            result, findings = self.analyze(workflow, directory, persona="pedantic")
            self.assertEqual(workflow.read_bytes(), original, "fixture must not be mutated")

        # zizmor exits 13 when only unignored findings below the strictest
        # threshold are present; either a nonzero exit or a populated finding
        # list is acceptable evidence, but the excessive-permissions ident
        # must be present with High severity to settle the gap.
        self.assertNotEqual(result.returncode, 0, result.stderr[:2000])
        by_ident = {finding["ident"]: finding for finding in findings}
        self.assertIn(
            "excessive-permissions", by_ident,
            f"expected excessive-permissions finding, got idents={sorted(by_ident)}",
        )
        finding = by_ident["excessive-permissions"]
        self.assertEqual(finding["determinations"]["severity"], "High")
        annotations = {
            location["symbolic"]["annotation"]
            for location in finding["locations"]
            if "symbolic" in location and "annotation" in location["symbolic"]
        }
        self.assertTrue(
            any("write-all" in annotation for annotation in annotations),
            f"expected an annotation referencing write-all, got {annotations}",
        )

    def test_regular_persona_does_not_surface_excessive_permissions(self) -> None:
        # Documents why --persona pedantic is required: the default persona
        # used elsewhere in this repository's zizmor tests does not run the
        # excessive-permissions audit, so this negative control would be a
        # false negative under the regular persona.
        original = FIXTURE.read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            workflow = directory / "negative-control.yml"
            workflow.write_bytes(original)
            _, findings = self.analyze(workflow, directory, persona="regular")
        idents = {finding["ident"] for finding in findings}
        self.assertNotIn("excessive-permissions", idents)

    def test_multi_job_fixture_triggers_under_regular_persona(self) -> None:
        # Corrected/narrowed claim: excessive-permissions is not pedantic-only
        # in general. When no job in the workflow declares its own
        # permissions block, the workflow-level write-all grant is reported
        # under --persona regular (the persona this repository's actual CI
        # zizmor invocations use).
        original = MULTI_JOB_FIXTURE.read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            workflow = directory / "multi-job-no-job-permissions.yml"
            workflow.write_bytes(original)
            result, findings = self.analyze(workflow, directory, persona="regular")
            self.assertEqual(workflow.read_bytes(), original, "fixture must not be mutated")

        self.assertNotEqual(result.returncode, 0, result.stderr[:2000])
        by_ident = {finding["ident"]: finding for finding in findings}
        self.assertIn(
            "excessive-permissions", by_ident,
            f"expected excessive-permissions finding under regular persona for a "
            f"multi-job fixture with no job-level permissions, got idents="
            f"{sorted(by_ident)}",
        )
        self.assertEqual(by_ident["excessive-permissions"]["determinations"]["severity"], "High")


if __name__ == "__main__":
    unittest.main()
