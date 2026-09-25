"""Positive-detection sensitivity check for gap ci-supply-chain[13].

The retained Grype receipt (blueprints/us-equities/supply-chain/scan-nautilus-
rc5-20260922/receipt.json) establishes a dated zero-match result against a
production dependency set. A zero-match result alone does not establish that
Grype would actually catch a real, published vulnerability if one were
present (positive-detection sensitivity), nor does it say anything about
absence of vulnerabilities in general (which no scanner can prove).

This test runs the installed grype (skipped if absent, matching the existing
zizmor tests' pattern) against a small, pinned fixture containing
urllib3==1.26.4, which has a long-published, well-known CVE (CVE-2021-33503,
a catastrophic-backtracking ReDoS in urllib3's URL-authority regex,
GHSA-q2q7-5pp4-w6pg), and asserts grype reports that exact match. This does
not establish vulnerability absence elsewhere; it only establishes that
grype's positive-detection path works end to end on this host with this
database.

The fixture is retained as ``requirements.txt.fixture`` (not
``requirements.txt``) so manifest/lockfile scanners (Dependabot, OSV-Scanner,
and Scorecard's own embedded OSV-Scanner/osv-scalibr vulnerabilities check,
none of which read GitHub's dependency graph here) never see it as a real,
scannable manifest. grype's underlying syft Python cataloger matches by
filename convention -- any ``*requirements*.txt`` name -- not by directory
content, which is exactly why this test copies the fixture into a fresh
temporary directory as ``requirements.txt`` immediately before invoking
grype, and never writes that copy into the repository tree.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GRYPE = shutil.which("grype")
FIXTURE_DIR = ROOT / "blueprints/gap-wave2-20260923/grype-known-cve-fixture"
FIXTURE_FILE = FIXTURE_DIR / "requirements.txt.fixture"
EXPECTED_GHSA = "GHSA-q2q7-5pp4-w6pg"
EXPECTED_CVE = "CVE-2021-33503"
EXPECTED_PACKAGE = "urllib3"
EXPECTED_VERSION = "1.26.4"
# The fixture's retained sha256 (manifests/evidence.json); a change here means the
# positive-control pin itself changed, which the content test below must catch even
# when grype is absent (e.g. in CI's validate job, which never installs grype).
EXPECTED_SHA256 = "d3b3b59405b2e7919cc5045aa238932c0e3cc593d1d6896f75a41c37b6f45bd6"


class GrypeKnownCveFixtureContentTests(unittest.TestCase):
    """Runs unconditionally (no grype dependency) so CI always checks the fixture
    itself, even though the detection test below is skipped wherever grype is
    absent -- including CI's validate job, which does not install grype."""

    def test_fixture_declares_the_expected_vulnerable_pin(self) -> None:
        text = FIXTURE_FILE.read_text(encoding="utf-8")
        self.assertIn(f"{EXPECTED_PACKAGE}=={EXPECTED_VERSION}", text)

    def test_fixture_bytes_match_the_registered_sha256(self) -> None:
        import hashlib

        digest = hashlib.sha256(FIXTURE_FILE.read_bytes()).hexdigest()
        self.assertEqual(digest, EXPECTED_SHA256)


@unittest.skipUnless(GRYPE, "native grype unavailable; CI installs the pinned scanner")
class GrypeKnownCveFixtureTests(unittest.TestCase):
    def test_grype_detects_the_published_cve_in_the_fixture(self) -> None:
        # Opt-in: default discovery never runs the scanner. When enabled it runs offline and
        # read-only (grype maps these GRYPE_* variables onto check-for-app-update,
        # db.auto-update and db.validate-age; `grype config --load` shows them applied) and skips
        # when no local database exists.
        if os.environ.get("NAS_RUN_GRYPE_FIXTURE") != "1":
            self.skipTest("set NAS_RUN_GRYPE_FIXTURE=1 to run the scanner (off by default: no network or cache use)")
        env = dict(os.environ, GRYPE_CHECK_FOR_APP_UPDATE="false", GRYPE_DB_AUTO_UPDATE="false",
                   GRYPE_DB_VALIDATE_AGE="false")
        status = subprocess.run([GRYPE, "db", "status"], capture_output=True, text=True,
                                timeout=60, check=False, env=env)
        if status.returncode != 0:
            self.skipTest("no local grype vulnerability database; this test never downloads one")
        # Copy into a fresh temp directory as requirements.txt: grype's manifest
        # extractor (syft's Python cataloger) matches any *requirements*.txt name,
        # and the copy must never land in the repository tree (see module
        # docstring). Fail loudly, rather than silently writing into the checkout,
        # if TMPDIR has been redirected inside the repository.
        with tempfile.TemporaryDirectory(prefix="grype-known-cve-fixture-") as raw_scan_dir:
            scan_dir = Path(raw_scan_dir).resolve()
            self.assertFalse(
                scan_dir.is_relative_to(ROOT),
                f"temp scan directory {scan_dir} is inside the repository root {ROOT}; "
                "refusing to copy the fixture there as requirements.txt",
            )
            shutil.copyfile(FIXTURE_FILE, scan_dir / "requirements.txt")
            result = subprocess.run(
                [GRYPE, f"dir:{scan_dir}", "-o", "json"],
                capture_output=True, text=True, timeout=120, check=False, env=env,
            )
        self.assertEqual(result.returncode, 0, result.stderr[:2000])
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(f"grype did not return JSON: {result.stderr[:2000]}")

        matches = payload.get("matches", [])
        self.assertTrue(matches, "expected at least one match against the fixture")

        target = None
        for match in matches:
            artifact = match.get("artifact", {})
            if artifact.get("name") != EXPECTED_PACKAGE:
                continue
            vuln_id = match.get("vulnerability", {}).get("id")
            related_ids = {
                r.get("id") for r in match.get("relatedVulnerabilities", [])
            }
            if vuln_id == EXPECTED_GHSA or EXPECTED_CVE in related_ids:
                target = match
                break

        self.assertIsNotNone(
            target,
            f"expected a match for {EXPECTED_GHSA} ({EXPECTED_CVE}) on "
            f"{EXPECTED_PACKAGE}=={EXPECTED_VERSION}; got "
            f"{[(m['vulnerability']['id'], m['artifact']['name'], m['artifact']['version']) for m in matches]}",
        )
        self.assertEqual(target["artifact"]["version"], EXPECTED_VERSION)


if __name__ == "__main__":
    unittest.main()
