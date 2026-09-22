"""Regression coverage for .gitleaks.toml's allowlist context-restriction.

Runs the PATH `gitleaks` (the guarded, memory-capped launcher; never the
underlying binary directly) in no-git `dir` mode against small synthetic fixture
directories built under a temp dir, using the real repository `.gitleaks.toml`.
Skips the whole test module if gitleaks is not on PATH, and skips individual
cases if the guarded launcher reports its per-user scan lock is held by another
scan (a busy lock is not a passing or failing result here).

`gitleaks dir` is invoked with the fixture directory as the *current working
directory* and "." as the source argument, matching how validate.yml's
secret-scan job and the manually recorded full-history scans in .gitleaks.toml's
header comment invoke it. Passing an absolute path instead makes gitleaks report
absolute `File` values, which never match this config's `^relative/path$`
allowlist anchors - a distinct, previously-observed failure mode of this test
file itself, not of the config.

These are local integration checks against the installed gitleaks binary and
synthetic fixture content; they do not assert anything about the repository's
real git history (see .gitleaks.toml's header comment for the dated
full-history scan counts, which are a separate, manually recorded evidence
class).
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".gitleaks.toml"

# A 64-hex and a 40-hex synthetic digest-shaped value, plus a synthetic GitHub
# personal-access-token-shaped value. None of these are real credentials.
HEX64 = "e1d0b0d7d8fa3617cc6410b02e8767ca242cd3f4882f5792b27ccdb1ea2b34e8"
HEX40 = "1bf6df330b056ef93ab283083afdcce642387949"
# Assembled from short chunks under a name with no credential-like substring
# (not "*token*"/"*key*"/"*secret*"/"*api*"), not as one literal assigned to a
# credential-named variable: written either way, this file is itself scanned
# by gitleaks, and the assembled value is deliberately shaped like a real
# GitHub personal access token so test_c can prove it is still caught when
# planted in a fixture file elsewhere.
_GH_PAT_SHAPE_PARTS = ("ghp_u8jzPde0Igx", "Ld6GncfBAepfJBd0", "Kh8oOOL8d")
GH_PAT_SHAPED_VALUE = "".join(_GH_PAT_SHAPE_PARTS)
CURSOR = "QU1EfER8MTU5NTkwODgwMDAwMDAwMDAwMA=="

GITLEAKS = shutil.which("gitleaks")


class _LockBusy(Exception):
    pass


def _run_gitleaks(target_dir: Path) -> list:
    """Run `gitleaks dir .` (cwd = target_dir) with the real repo config.

    Returns the parsed JSON findings list. Raises _LockBusy if the guarded
    launcher reports its per-user scan lock is held by another scan, so the
    caller can skipTest instead of failing.
    """
    report_path = target_dir / "gitleaks-report.json"
    proc = subprocess.run(
        [
            GITLEAKS, "dir", ".",
            "--config", str(CONFIG_PATH),
            "--no-banner", "--exit-code", "0",
            "--report-format", "json", "--report-path", str(report_path),
        ],
        cwd=str(target_dir),
        capture_output=True, text=True, check=False,
    )
    if "lock" in proc.stderr.lower():
        raise _LockBusy(proc.stderr.strip())
    if proc.returncode not in (0, 1):
        raise AssertionError(f"gitleaks failed unexpectedly: {proc.returncode} {proc.stderr}")
    if not report_path.exists():
        return []
    return json.loads(report_path.read_text())


@unittest.skipUnless(GITLEAKS, "gitleaks not found on PATH")
class GitleaksConfigContextRestrictionTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CONFIG_PATH.exists(), ".gitleaks.toml must exist at repo root")

    def _scan(self, target_dir: Path) -> list:
        try:
            return _run_gitleaks(target_dir)
        except _LockBusy as exc:
            self.skipTest(f"gitleaks per-user lock held by another scan: {exc}")

    def test_a_non_allowlisted_path_hex_secrets_are_detected(self):
        """A synthetic api_key/token pair under a non-allowlisted path is still caught."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            nonallow = target / "some" / "other" / "path"
            nonallow.mkdir(parents=True)
            (nonallow / "data.json").write_text(
                json.dumps({"api_key": HEX64, "token": HEX40}, indent=2)
            )
            findings = self._scan(target)
            secrets = {f["Secret"] for f in findings}
            self.assertIn(HEX64, secrets, "64-hex api_key under a non-allowlisted path must be detected")
            self.assertIn(HEX40, secrets, "40-hex token under a non-allowlisted path must be detected")

    def test_b_allowlisted_path_named_digest_field_is_not_detected(self):
        """A `"disk_token": "<64hex>"` line under an allowlisted evidence path is suppressed.

        disk_token is one of this config's exact allowlisted field names, and (unlike
        a bare "sha256" key) the default generic-api-key rule reliably matches it on
        its own with no other credential-context needed, which keeps this a real
        regression check rather than a vacuous pass because the base rule never fired.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            allow_dir = target / "evidence" / "artifacts" / "native-service-reboot-20260920"
            allow_dir.mkdir(parents=True)
            (allow_dir / "guest-after.json").write_text(
                json.dumps({"disk_token": HEX64}, indent=2)
            )
            findings = self._scan(target)
            self.assertEqual(
                findings, [],
                "disk_token field under the allowlisted evidence path must not be flagged",
            )

    def test_b2_non_allowlisted_directory_same_field_name_is_still_detected(self):
        """The same `"disk_token": "<64hex>"` shape outside the allowlisted paths is caught.

        This is the context-restriction half of the fix: the allowlist must not
        become a blanket hex-secret suppressor merely because a key is named
        "disk_token" - it must also match one of the exact reviewed file paths.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            other_dir = target / "some" / "unrelated" / "path"
            other_dir.mkdir(parents=True)
            (other_dir / "not-a-reviewed-receipt.json").write_text(
                json.dumps({"disk_token": HEX64}, indent=2)
            )
            findings = self._scan(target)
            secrets = {f["Secret"] for f in findings}
            self.assertIn(
                HEX64, secrets,
                "disk_token field outside the allowlisted paths must still be detected",
            )

    def test_c_ghp_token_beside_allowlisted_cursor_is_still_detected(self):
        """A synthetic ghp_ token on the same line as a legitimate next_page_token cursor
        under the allowlisted receipt path is still caught; only the cursor itself
        is suppressed (regexTarget = "secret", not the whole line)."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            allow_dir = target / "blueprints" / "us-equities" / "broad-universe"
            allow_dir.mkdir(parents=True)
            line = json.dumps({"next_page_token": CURSOR, "leaked_token": GH_PAT_SHAPED_VALUE})
            (allow_dir / "receipt.json").write_text(line + "\n")
            findings = self._scan(target)
            secrets = {f["Secret"] for f in findings}
            self.assertIn(
                GH_PAT_SHAPED_VALUE, secrets,
                "a ghp_ token on the same line as an allowlisted cursor must still be detected",
            )
            self.assertNotIn(
                CURSOR, secrets,
                "the legitimate opaque pagination cursor itself must remain suppressed",
            )


if __name__ == "__main__":
    unittest.main()
