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
import os
import re
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
# Assembled at runtime: a literal 40-hex value in this file matches the sourcegraph-access-token
# rule in `gitleaks dir` (the file names that rule, which satisfies its keyword check).
HEX40 = "".join(("1bf6df330b056ef9", "3ab283083afdcce6", "42387949"))
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


class GitleaksPresenceTests(unittest.TestCase):
    def test_gitleaks_is_on_path_when_the_ci_step_requires_it(self):
        """The secret-scan job sets GITLEAKS_TESTS_REQUIRED and puts the pinned binary on PATH; without
        it the allowlist tests below would silently skip there, as they do in the validate job."""
        if os.environ.get("GITLEAKS_TESTS_REQUIRED"):
            self.assertIsNotNone(GITLEAKS, "GITLEAKS_TESTS_REQUIRED is set but gitleaks is not on PATH")


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

    def test_c_ghp_token_on_a_different_line_from_the_allowlisted_cursor_is_still_detected(self):
        """A synthetic ghp_ token on a DIFFERENT line from a legitimate, alone-on-its-
        own-line `next_page_token` cursor under the allowlisted receipt path is still
        caught; the cursor itself (its own whole line, keyed on "next_page_token") is
        suppressed. Regression fixture for `codex-review-64`: an earlier revision used
        `regexTarget = "secret"` (the cursor's base64 shape, unkeyed, matched anywhere
        on the line) instead of a keyed, line-anchored regex; see test_c2/test_c3 below
        for the two scenarios that revision got wrong (a same-line pair, and an
        unrelated key sharing the cursor's shape)."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            allow_dir = target / "blueprints" / "us-equities" / "broad-universe"
            allow_dir.mkdir(parents=True)
            (allow_dir / "receipt.json").write_text(
                json.dumps({"next_page_token": CURSOR, "leaked_token": GH_PAT_SHAPED_VALUE}, indent=2) + "\n"
            )
            findings = self._scan(target)
            secrets = {f["Secret"] for f in findings}
            self.assertIn(
                GH_PAT_SHAPED_VALUE, secrets,
                "a ghp_ token on a different line from the allowlisted cursor must still be detected",
            )
            self.assertNotIn(
                CURSOR, secrets,
                "the legitimate opaque pagination cursor, alone on its own line, must remain suppressed",
            )

    def test_c2_sha256_and_api_key_sharing_one_line_the_api_key_is_still_detected(self):
        """Codex cross-family review finding (codex-review-64, .gitleaks.toml:134):
        a line holding BOTH an allowlisted digest field ("sha256") AND an unrelated
        secret ("api_key") -- e.g. compact (non-pretty-printed) JSON that puts two
        key/value pairs on one physical line -- must not have the api_key swept up
        as exempted merely because the same line ALSO contains the allowlisted
        "sha256" field/value pair. The base gitleaks generic-api-key rule does not
        independently flag a bare "sha256"-labeled hex value on its own (unlike
        "api_key"/"token"/"disk_token"; see test_b's docstring), so this scenario is
        a real regression check on the ALLOWLIST's suppression of the api_key
        finding, not on whether "sha256" itself is ever flagged: with the prior
        unanchored regex, the allowlist regex matched the "sha256" substring
        anywhere on the line and exempted the WHOLE line (including the unrelated
        api_key finding on it); the whole-line anchor now requires the line to be
        EXACTLY one "sha256": "<hex>" pair with nothing else, so this two-field line
        never matches the allowlist and the api_key finding surfaces normally."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            allow_dir = target / "evidence" / "artifacts" / "native-service-reboot-20260920"
            allow_dir.mkdir(parents=True)
            # Deliberately compact (no indent): both fields on one physical line.
            line = json.dumps({"sha256": HEX64, "api_key": HEX64})
            (allow_dir / "guest-after.json").write_text(line + "\n")
            findings = self._scan(target)
            secrets = {f["Secret"] for f in findings}
            self.assertIn(
                HEX64, secrets,
                f"the api_key finding co-located with an allowlisted sha256 field on the "
                f"same line must still be detected, got: {findings}",
            )

    def test_c3_unrelated_key_sharing_the_cursors_base64_shape_is_detected(self):
        """Codex cross-family review finding (codex-review-64, .gitleaks.toml:192): the
        next_page_token exemption must be keyed on the literal "next_page_token" field
        name, not merely the cursor's base64-with-padding shape. An unrelated key
        (e.g. "api_key") holding a same-shaped value, even under the SAME allowlisted
        receipt path, must still be detected."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            allow_dir = target / "blueprints" / "us-equities" / "broad-universe"
            allow_dir.mkdir(parents=True)
            (allow_dir / "receipt.json").write_text(
                json.dumps({"next_page_token": CURSOR, "api_key": CURSOR}, indent=2) + "\n"
            )
            findings = self._scan(target)
            secrets = {f["Secret"] for f in findings}
            self.assertIn(
                CURSOR, secrets,
                "the same base64-shaped value under an unrelated 'api_key' field must be detected "
                "even though the identical value under 'next_page_token' is legitimately suppressed",
            )

    def _manifest_fixture(self, target: Path, relative: str, extra: dict) -> None:
        """A manifest-shaped file whose text names Sourcegraph, so the sourcegraph-access-token
        rule's keyword is present and its 40-hex pattern is live for every value in the file."""
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [{"id": "a", "pin": HEX40}, {"id": "b", "pin": f"1.0.6 @ {HEX40}"},
                {"evidence": ["https://sourcegraph.com/blog/announcing-scip"]}, extra]
        path.write_text(json.dumps({"foundation": rows}, indent=1))

    def test_d_manifest_pin_commit_ids_are_not_detected(self):
        """The dated SOTA manifest's "pin" git commit ids (plain or "<version> @ <id>") are exempt."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._manifest_fixture(target, "catalogs/sota-convergence/manifest-20260923.json", {})
            findings = self._scan(target)
            self.assertEqual([f for f in findings if f["RuleID"] == "sourcegraph-access-token"], [],
                             "pin commit ids in the reviewed manifest must not be flagged")

    def test_d2_other_fields_and_other_paths_stay_detected(self):
        """Only "pin" lines of that exact file are exempt: the same 40-hex under another field in the
        file, and the same pin lines in any other file, are still sourcegraph-access-token findings."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._manifest_fixture(target, "catalogs/sota-convergence/manifest-20260923.json", {"token": HEX40})
            self._manifest_fixture(target, "catalogs/sota-convergence/manifest-20260924.json", {})
            findings = [f for f in self._scan(target) if f["RuleID"] == "sourcegraph-access-token"]
            by_file = {}
            for f in findings:
                by_file.setdefault(f["File"], []).append(f["StartLine"])
            self.assertEqual(len(by_file.get("catalogs/sota-convergence/manifest-20260923.json", [])), 1,
                             f"the non-pin token line in the reviewed manifest must still be detected: {by_file}")
            self.assertEqual(len(by_file.get("catalogs/sota-convergence/manifest-20260924.json", [])), 2,
                             f"pin lines outside the exact reviewed path must still be detected: {by_file}")

    @staticmethod
    def _reviewed_manifest_ids() -> list:
        """The git commit ids that the 2026-09-26 manifest allowlist pins by value, read from .gitleaks.toml. This
        file names the rule, so a 40-hex literal written here would itself be a finding."""
        text = CONFIG_PATH.read_text(encoding="utf-8")
        block = text[text.index("manifest-20260926\\.json"):]
        return re.findall(r"[0-9a-f]{40}", block[:block.index("[[")])

    def _free_form_manifest(self, target: Path, relative: str, ids: list, extra_rows: list) -> None:
        """The 2026-09-26 manifest's shape: free-form catalog pins holding a git commit id, in a file whose lane
        text names the rule id sourcegraph-access-token (the keyword that makes every 40-hex value a candidate)."""
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        pins = [f"v0.44.0; source {ids[0]}", f"{ids[1]} (blueprints/us-equities/adaptive-paper)",
                f"Apache Iceberg 1.11.0; PyIceberg 0.12.0; source {ids[2]}", ids[3]]
        rows = [{"id": f"c{i}", "pin": pin} for i, pin in enumerate(pins)]
        rows += [{"reasoning": "the repository's gitleaks config has generic-api-key and sourcegraph-access-token"},
                 *extra_rows]
        path.write_text(json.dumps({"trading": rows}, indent=1))

    def test_d3_reviewed_manifest_pin_ids_are_not_detected(self):
        """The reviewed git commit ids in the 2026-09-26 manifest's free-form "pin" values are exempt."""
        ids = self._reviewed_manifest_ids()
        self.assertGreaterEqual(len(ids), 4, "the allowlist must pin the reviewed ids by value")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._free_form_manifest(target, "catalogs/sota-convergence/manifest-20260926.json", ids, [])
            findings = [f for f in self._scan(target) if f["RuleID"] == "sourcegraph-access-token"]
            self.assertEqual(findings, [], "reviewed pin commit ids in the reviewed manifest must not be flagged")

    def test_d4_unreviewed_values_and_other_paths_stay_detected(self):
        """Only the reviewed ids in that exact file are exempt. An unreviewed 40-hex value (under another field, or
        as free text in a pin), the uppercase form of a reviewed id, an sgp_-prefixed token, and the reviewed ids in
        any other file are all still detected."""
        ids = self._reviewed_manifest_ids()
        extra = [{"token": HEX40}, {"pin": f"sourcegraph legacy access token {HEX40}"},
                 {"pin": ids[0].upper()}, {"pin": f"sgp_{ids[0]}"}]
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._free_form_manifest(target, "catalogs/sota-convergence/manifest-20260926.json", ids, extra)
            self._free_form_manifest(target, "catalogs/sota-convergence/manifest-20260925.json", ids, [])
            by_file = {}
            for f in self._scan(target):
                if f["RuleID"] == "sourcegraph-access-token":
                    by_file.setdefault(f["File"], []).append(f["StartLine"])
            self.assertEqual(len(by_file.get("catalogs/sota-convergence/manifest-20260926.json", [])), len(extra),
                             f"every unreviewed value in the reviewed manifest must be detected: {by_file}")
            self.assertEqual(len(by_file.get("catalogs/sota-convergence/manifest-20260925.json", [])), 4,
                             f"reviewed ids outside the exact reviewed path must be detected: {by_file}")

    # The 4 reviewed ai-memory rejection fingerprints (SHA-256 digests, not credentials) the
    # .gitleaks.toml entry pins by value.
    REVIEWED_FINGERPRINTS = ["ab60ca6b319cd1ae67edf7153a82dfe740358d9fe839f8e52366edfa88cf38db", "ad141246c92c80672c10dba83896fe6744fc0ef5ef3a4d3ca07b27fce89aa9b0", "125b939f93f32338ee87c4fe362dbc1e10237865266014573628ca6ab7d811a1", "683cc56662967628cbce607d2a76a95e81eab811bf0033a167885cc243e399b9"]

    def _fingerprint_fixture(self, target: Path, relative: str, extra: dict, values=None) -> None:
        """The shape of ai-memory's scheduled-learning report: 64-hex rejection fingerprints under "key"."""
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [{"key": value, "count": 10 - i} for i, value in enumerate(values or self.REVIEWED_FINGERPRINTS[:2])]
        report = {"learning": {"report": {"aggregate": {"repeated_rejection_fingerprints": rows}, **extra}}}
        path.write_text(json.dumps(report, indent=2))

    def test_e_memory_rejection_fingerprints_are_not_detected(self):
        """ai-memory's SHA-256 rejection fingerprints in the reviewed evidence file are exempt."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._fingerprint_fixture(target, "observability/memory-scheduled-20260923.json", {})
            findings = [f for f in self._scan(target) if f["RuleID"] == "generic-api-key"]
            self.assertEqual(findings, [], "rejection fingerprints in the reviewed file must not be flagged")

    def test_e2_other_fields_and_other_paths_stay_detected(self):
        """Only the reviewed digests on whole "key" lines of that exact file are exempt: an unreviewed 64-hex
        "key" value and an api_key in the same file, and the same lines in another file, are still findings."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            # The reviewed file: one exempt digest, one unreviewed 64-hex "key" value, and an api_key.
            self._fingerprint_fixture(target, "observability/memory-scheduled-20260923.json", {"api_key": HEX64},
                                      values=[self.REVIEWED_FINGERPRINTS[0], HEX64[::-1]])
            self._fingerprint_fixture(target, "observability/memory-scheduled-20260924.json", {})
            by_file = {}
            for f in self._scan(target):
                if f["RuleID"] == "generic-api-key":
                    by_file.setdefault(f["File"], []).append(f["StartLine"])
            self.assertEqual(len(by_file.get("observability/memory-scheduled-20260923.json", [])), 2,
                             f"the unreviewed key value and the api_key in the reviewed file must be detected: {by_file}")
            self.assertEqual(len(by_file.get("observability/memory-scheduled-20260924.json", [])), 2,
                             f"fingerprint lines outside the exact reviewed path must still be detected: {by_file}")

    SOURCE_HASHES_PATH = "blueprints/us-equities/adaptive-paper/source-hashes.json"

    def _source_hashes_fixture(self, target: Path, relative: str, obj: dict, *, compact: bool = False) -> None:
        """The shape of blueprints/us-equities/adaptive-paper/source-hashes.json: a flat
        map of repo file paths (several containing the word "credential",
        e.g. credential_guard.py) to their sha256."""
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((json.dumps(obj) if compact else json.dumps(obj, indent=2)) + "\n")

    def test_f_path_keyed_digest_in_the_reviewed_manifest_is_not_detected(self):
        """A real-shaped `"blueprints/us-equities/adaptive-paper/<name>.py": "<64hex>"` entry
        in the reviewed manifest -- including a path containing "credential" -- is exempt."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._source_hashes_fixture(target, self.SOURCE_HASHES_PATH, {
                "blueprints/us-equities/adaptive-paper/credential_guard.py": HEX64,
                "tests/test_adaptive_paper_credential_race.py": HEX64[::-1],
            })
            findings = [f for f in self._scan(target) if f["RuleID"] == "generic-api-key"]
            self.assertEqual(findings, [], f"path-keyed digests in the reviewed manifest must not be flagged: {findings}")

    def test_f2_credential_shaped_key_in_the_same_file_is_detected(self):
        """The dedicated allowlist requires the ENTIRE key to be a real adaptive-paper/tests
        repo path: a credential-shaped key such as "credential.key" or "api_key" holding a
        64-hex value, in the SAME reviewed file, is not a path and must still be detected."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._source_hashes_fixture(target, self.SOURCE_HASHES_PATH, {
                "blueprints/us-equities/adaptive-paper/credential_guard.py": HEX64,
                "credential.key": HEX64[::-1],
                "api_key": HEX64,
            })
            findings = [f for f in self._scan(target) if f["RuleID"] == "generic-api-key"]
            secrets = {f["Secret"] for f in findings}
            self.assertIn(HEX64[::-1], secrets, f"a 'credential.key' value in the reviewed manifest must still be detected: {findings}")
            self.assertIn(HEX64, secrets, f"an 'api_key' value in the reviewed manifest must still be detected: {findings}")

    def test_f2b_dot_segment_path_key_holding_a_digest_is_detected(self):
        """The dedicated allowlist refuses path segments starting with ".", so a key that only
        looks like an adaptive-paper/tests path through "." or ".." (and names a credential)
        is not exempted and its 64-hex value is still detected in the reviewed manifest."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._source_hashes_fixture(target, self.SOURCE_HASHES_PATH, {
                "tests/../credential_store.py": HEX64,
                "blueprints/us-equities/adaptive-paper/./api_key.py": HEX64[::-1],
            })
            findings = [f for f in self._scan(target) if f["RuleID"] == "generic-api-key"]
            secrets = {f["Secret"] for f in findings}
            self.assertIn(HEX64, secrets, f"a '..' path key must not be exempted: {findings}")
            self.assertIn(HEX64[::-1], secrets, f"a '.' path key must not be exempted: {findings}")

    def test_f3_non_hex_value_under_a_path_shaped_key_is_detected(self):
        """The allowlist's value alternative is exactly `[0-9a-f]{64}`: a same-length value that is
        not lowercase hex (upper-case letters here) under an otherwise real path key does not match
        the allowlist regex and must still be detected as a candidate secret."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._source_hashes_fixture(target, self.SOURCE_HASHES_PATH, {
                "blueprints/us-equities/adaptive-paper/credential_guard.py": HEX64.upper(),
            })
            findings = [f for f in self._scan(target) if f["RuleID"] == "generic-api-key"]
            self.assertNotEqual(findings, [], "a non-lowercase-hex value under a path-shaped key must still be flagged")

    def test_f4_second_secret_on_the_same_line_is_detected(self):
        """Same whole-line-anchor requirement as test_c2/test_e2: a compact (single-line) JSON
        object holding both a legitimate path-keyed digest AND an unrelated api_key means the
        line no longer matches the allowlist's single-entry-per-line shape at all, so the
        api_key finding on that line must still surface."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._source_hashes_fixture(
                target, self.SOURCE_HASHES_PATH,
                {"blueprints/us-equities/adaptive-paper/credential_guard.py": HEX64, "api_key": HEX64[::-1]},
                compact=True)
            findings = [f for f in self._scan(target) if f["RuleID"] == "generic-api-key"]
            secrets = {f["Secret"] for f in findings}
            self.assertIn(HEX64[::-1], secrets,
                          f"an api_key sharing a line with an allowlisted path digest must still be detected: {findings}")

    def test_f5_same_path_keyed_line_in_a_different_file_is_detected(self):
        """The allowlist is scoped to the exact source-hashes.json path: the identical
        path-keyed digest line in any other file must still be detected."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._source_hashes_fixture(target, self.SOURCE_HASHES_PATH, {
                "blueprints/us-equities/adaptive-paper/credential_guard.py": HEX64,
            })
            other_path = "blueprints/us-equities/adaptive-paper/not-source-hashes.json"
            self._source_hashes_fixture(target, other_path, {
                "blueprints/us-equities/adaptive-paper/credential_guard.py": HEX64,
            })
            by_file = {}
            for f in self._scan(target):
                if f["RuleID"] == "generic-api-key":
                    by_file.setdefault(f["File"], []).append(f["StartLine"])
            self.assertEqual(by_file.get(self.SOURCE_HASHES_PATH, []), [],
                             f"the reviewed manifest's own path-keyed line must stay exempt: {by_file}")
            self.assertEqual(len(by_file.get(other_path, [])), 1,
                             f"the identical path-keyed line in a different file must still be detected: {by_file}")

    def test_exit_code_zero_flag_always_returns_zero_even_with_findings(self):
        """`--exit-code 0` must return process exit code 0 even when real leaks are found.

        Regression for a disclosed review finding: a prior recorded acceptance run
        used `--exit-code 0` but recorded process exit code 1 for a run that *did*
        find a leak, which is inconsistent with gitleaks's own `--exit-code N`
        semantics (N is the exit code used when leaks ARE found; 0 means "always
        exit 0"). Pass/fail must be read from the report/log output, never from the
        process exit code, whenever this flag is used. This pins that behavior
        against the installed binary so a similar mis-recorded result cannot recur
        unnoticed.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            nonallow = target / "some" / "other" / "path"
            nonallow.mkdir(parents=True)
            (nonallow / "data.json").write_text(json.dumps({"api_key": HEX64}))
            report_path = target / "gitleaks-report.json"
            proc = subprocess.run(
                [
                    GITLEAKS, "dir", ".",
                    "--config", str(CONFIG_PATH),
                    "--no-banner", "--exit-code", "0",
                    "--report-format", "json", "--report-path", str(report_path),
                ],
                cwd=str(target),
                capture_output=True, text=True, check=False,
            )
            if "lock" in proc.stderr.lower():
                self.skipTest(f"gitleaks per-user lock held by another scan: {proc.stderr.strip()}")
            findings = json.loads(report_path.read_text()) if report_path.exists() else []
            self.assertTrue(findings, "fixture must contain a detected leak for this test to be meaningful")
            self.assertEqual(
                proc.returncode, 0,
                "`--exit-code 0` must yield process exit code 0 even though a leak was found "
                f"(got {proc.returncode}); a nonzero code here means the earlier mis-recorded "
                "exit-code finding could recur",
            )


class GitleaksIgnoreFingerprintTests(unittest.TestCase):
    """Regression coverage for the root .gitleaksignore file that replaced the
    prose-narrative commit-id regex allowlist (codex-review-83b fix round):
    exact `commit:path:rule:line` fingerprints, gitleaks' own mechanism for
    known historical false positives (read from this file by default), in
    place of the four-round-leaky regex allowlist previously duplicated under
    generic-api-key and sourcegraph-access-token in .gitleaks.toml. See
    .gitleaksignore's own header comment for the full rationale."""

    GITLEAKSIGNORE_PATH = ROOT / ".gitleaksignore"
    NARRATIVE_FILES = (
        "evidence/artifacts/blind-catalog-convergence-20260921/claude-coverage-review.json",
        "evidence/artifacts/blind-catalog-convergence-20260921/screening-ledger.json",
    )
    NARRATIVE_RULES = ("generic-api-key", "sourcegraph-access-token")
    # gitleaks' own git-mode fingerprint format: `commit:path:rule:line`, or
    # `path:rule:line` for a working-tree (non-git) finding.
    FINGERPRINT_RE = re.compile(
        r'^(?P<commit>[0-9a-f]{40}):(?P<path>[^:]+):(?P<rule>[^:]+):(?P<line>\d+)$'  # commit required: a commit-less entry would suppress every commit and dir mode
    )

    def setUp(self):
        self.assertTrue(self.GITLEAKSIGNORE_PATH.exists(), ".gitleaksignore must exist at repo root")

    def tearDown(self):
        worktree = getattr(self, "_worktree", None)
        if worktree is not None:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=str(ROOT), capture_output=True, text=True, check=False,
            )
            shutil.rmtree(worktree, ignore_errors=True)

    def _ignore_lines(self):
        return [
            line.strip()
            for line in self.GITLEAKSIGNORE_PATH.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    def test_a_every_line_is_a_fingerprint_naming_a_narrative_file_and_rule(self):
        """Every non-comment, non-blank line must be a well-formed gitleaks
        fingerprint naming one of the two review-narrative files and one of
        the two rules that matched them -- not a stray line, a literal
        secret, or an entry for some other file this fix round did not
        review."""
        lines = self._ignore_lines()
        self.assertGreater(len(lines), 0, ".gitleaksignore must contain at least one fingerprint")
        for line in lines:
            match = self.FINGERPRINT_RE.match(line)
            self.assertIsNotNone(
                match,
                f"not a gitleaks fingerprint (commit:path:rule:line or path:rule:line): {line!r}",
            )
            if line in self.REVIEWED_OUT_OF_ANCESTRY:
                continue  # checked separately in test_a2
            self.assertIn(
                match.group("path"), self.NARRATIVE_FILES,
                f"fingerprint path is not one of the two reviewed narrative files: {line!r}",
            )
            self.assertIn(
                match.group("rule"), self.NARRATIVE_RULES,
                f"fingerprint rule is not generic-api-key or sourcegraph-access-token: {line!r}",
            )

    # Reviewed findings on sibling branches that are NOT ancestors of main: synthetic test data
    # the default all-refs local scan reports. Each entry needs a review note in .gitleaksignore,
    # and test_a2 fails if its commit ever enters HEAD's ancestry.
    REVIEWED_OUT_OF_ANCESTRY = {
        "34fc51beaf24114fe266f73b2e36ae8176c8a521:tests/test_lane_packets.py:generic-api-key:255",
    }

    def test_a2_out_of_ancestry_exceptions_stay_out_of_head_history(self):
        lines = set(self._ignore_lines())
        for entry in self.REVIEWED_OUT_OF_ANCESTRY:
            self.assertIn(entry, lines, f"reviewed exception is no longer in .gitleaksignore; drop it here: {entry}")
            commit = entry.split(":", 1)[0]
            if subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{commit}^{{commit}}"],
                              capture_output=True).returncode:
                continue  # object absent (shallow clone): nothing to check
            ancestry = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", commit, "HEAD"],
                                      capture_output=True)
            self.assertNotEqual(ancestry.returncode, 0,
                                f"{commit} is now an ancestor of HEAD; review the finding instead of ignoring it")

    def test_b_gitleaks_toml_has_no_allowlist_naming_the_narrative_files(self):
        """.gitleaks.toml must no longer contain an allowlist whose `paths`
        name either narrative file: that suppression now lives exclusively
        in .gitleaksignore, as exact per-commit fingerprints rather than a
        shape/context regex that (per four review rounds) could not fully
        distinguish a real commit reference from an adjacent secret."""
        import tomllib
        with open(CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
        for rule in data.get("rules", []):
            for allowlist in rule.get("allowlists", []):
                for path_regex in allowlist.get("paths", []):
                    for narrative_file in self.NARRATIVE_FILES:
                        self.assertIsNone(
                            re.search(path_regex, narrative_file),
                            f"rule {rule.get('id')!r} allowlist {allowlist.get('description')!r} "
                            f"still names a narrative file via path regex {path_regex!r}",
                        )

    @unittest.skipUnless(GITLEAKS, "gitleaks not found on PATH")
    def test_c_a_later_commit_sharing_a_narrative_line_with_an_injected_secret_is_detected(self):
        """A LATER commit that appends an unrelated secret to the SAME line
        (inside the SAME JSON string) as a real, fingerprint-ignored
        narrative commit reference is still detected: the fingerprint is
        `commit:path:rule:line`, so a different commit touching that line
        number gets a different fingerprint and is not suppressed. This is
        the exact class of gap all four regex-allowlist review rounds found
        (an unrelated secret sharing a marker-preceded narrative line/string)
        -- unlike that regex, which matched by shape/context on ANY commit,
        this mechanism cannot be defeated by a same-line, same-string
        adversarial addition on a commit the fingerprint does not name.

        The modified line is selected by PARSING .gitleaksignore itself and
        taking one of its own fingerprinted `path:...:line` entries for
        NARRATIVE_FILES[0] (the lowest fingerprinted line number, currently
        line 338) -- not by independently re-deriving a "looks like a commit
        reference" line via a marker-word/hex regex, which previously
        selected an unfingerprinted line (line 98, a short "source_commit
        5f3ec40b" abbreviated hash with no 40-hex id and no corresponding
        .gitleaksignore entry) and so passed regardless of whether
        .gitleaksignore ignored anything at all. Selecting an actual
        fingerprinted line makes the test's result genuinely depend on
        .gitleaksignore's content: an empty or overly broad .gitleaksignore
        would fail this test differently than the correct one.

        Uses a real, tracked narrative line (not a synthetic fixture file),
        modified in a disposable detached worktree so the injected marker
        never touches this repository's actual history or working tree."""
        rev_parse = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT),
            capture_output=True, text=True, check=False,
        )
        if rev_parse.returncode != 0:
            self.skipTest(f"could not resolve HEAD: {rev_parse.stderr.strip()}")

        target_path = self.NARRATIVE_FILES[0]
        fingerprinted_lines = []
        for raw in self._ignore_lines():
            match = self.FINGERPRINT_RE.match(raw)
            if match and match.group("path") == target_path:
                fingerprinted_lines.append(int(match.group("line")))
        self.assertTrue(
            fingerprinted_lines,
            f".gitleaksignore has no fingerprint for {target_path!r}; "
            "this test requires a real fingerprinted line to inject into",
        )
        target_line_no = min(fingerprinted_lines)
        marker_idx = target_line_no - 1  # fingerprint line numbers are 1-based

        worktree = Path(tempfile.mkdtemp(prefix="gitleaksignore-fp-test-"))
        worktree.rmdir()  # `git worktree add` requires the target not already exist
        add = subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree), "HEAD"],
            cwd=str(ROOT), capture_output=True, text=True, check=False,
        )
        if add.returncode != 0:
            self.skipTest(f"could not create a detached worktree: {add.stderr.strip()}")
        self._worktree = worktree

        target_file = worktree / target_path
        lines = target_file.read_text().splitlines()
        self.assertLess(
            marker_idx, len(lines),
            f".gitleaksignore fingerprints line {target_line_no} for {target_path!r}, "
            f"but that file only has {len(lines)} lines",
        )
        selected_line = lines[marker_idx]
        self.assertTrue(
            re.search(r'\b(?:pin|pinned|commit|tree|source_pin|source_commit|source)\b', selected_line, re.IGNORECASE)
            and re.search(r'[0-9a-f]{8,}', selected_line),
            f"fingerprinted line {target_line_no} does not look like a real commit-reference "
            f"narrative line: {selected_line!r}",
        )
        self.assertTrue(
            selected_line.rstrip().rstrip(",").endswith('"'),
            f"expected a JSON string on the fingerprinted line: {selected_line!r}",
        )

        # Built at runtime from short chunks under a name with no
        # credential-like substring, never as one literal: this source file
        # is itself scanned by gitleaks, and the assembled value is
        # deliberately shaped like a real GitHub personal access token
        # ("ghp_" followed by 36 characters) so this test can prove it is
        # still caught when injected into a narrative line's SAME JSON
        # string. The literal never sits in any file committed to THIS
        # repository's real history -- only inside the disposable worktree
        # removed in tearDown -- so GitHub push protection is not a concern
        # here.
        marker_parts = ("ghp_", "wT9kLp3", "Qr7xNb2", "Yv5cMz8", "Hj4sDf6A", "Zn2Jf9K")
        injected_marker = "".join(marker_parts)
        self.assertEqual(len(injected_marker), 40, "expected a ghp_ + 36-char GitHub PAT shape")

        original = lines[marker_idx].rstrip()
        trailing_comma = original.endswith(",")
        core = original[:-1] if trailing_comma else original
        self.assertTrue(core.endswith('"'), f"expected a JSON string on this line: {original!r}")
        modified = core[:-1] + f"; api_key={injected_marker}" + '"' + ("," if trailing_comma else "")
        lines[marker_idx] = modified
        target_file.write_text("\n".join(lines) + "\n")

        subprocess.run(["git", "add", "-A"], cwd=str(worktree), check=True, capture_output=True)
        commit = subprocess.run(
            ["git", "-c", "user.name=gitleaks-test", "-c", "user.email=gitleaks-test@example.invalid", "commit", "--no-verify", "-m", "test: inject synthetic marker for gitleaksignore fingerprint test"],
            cwd=str(worktree), capture_output=True, text=True, check=False,
        )
        self.assertEqual(commit.returncode, 0, f"worktree commit failed: {commit.stderr}")
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(worktree),
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        report_path = worktree / "gitleaks-report.json"
        # --config and --gitleaks-ignore-path point at THIS repository's real,
        # live files (not whatever the worktree's checked-out HEAD happens to
        # contain), so the test reflects the actual working-tree config even
        # when run before these files are committed. No --redact: the test
        # needs to find the injected marker in the report.
        proc = subprocess.run(
            [
                GITLEAKS, "git", str(worktree),
                "--config", str(CONFIG_PATH),
                "--gitleaks-ignore-path", str(ROOT),
                f"--log-opts=-1 {sha}",
                "--no-banner", "--exit-code", "0",
                "--report-format", "json", "--report-path", str(report_path),
            ],
            capture_output=True, text=True, check=False,
        )
        if "lock" in proc.stderr.lower():
            self.skipTest(f"gitleaks per-user lock held by another scan: {proc.stderr.strip()}")
        findings = json.loads(report_path.read_text()) if report_path.exists() and report_path.stat().st_size else []
        matches = [
            f for f in findings
            if injected_marker in (f.get("Match") or "") or injected_marker in (f.get("Secret") or "")
        ]
        self.assertTrue(
            matches,
            f"a secret injected into the SAME JSON string as a fingerprint-ignored narrative "
            f"commit reference, on a NEW commit, must still be detected: {findings}",
        )


class GitleaksBranchAncestryHistoryTests(unittest.TestCase):
    """Regression coverage for the branch-ancestry acceptance result recorded in
    .gitleaks.toml's header comment: PR-3-codexfix-major-2.

    A prior review round found that the published acceptance command (default
    log-opts, i.e. all refs reachable in this shared repository) does not reach
    zero findings because a concurrently active sibling branch contains an
    unrelated synthetic-fixture leak that is not an ancestor of this branch.
    `--log-opts="HEAD"` scopes the scan to commits this branch actually owns
    (its own ancestry) and is this unit's real acceptance-relevant result; this
    test asserts that scoped scan stays at zero findings for the real repository
    history, independent of what other branches in the shared repo contain.

    This is a local integration check against the real git history in this
    worktree (not a synthetic fixture): it is slower (full-history scan, ~30s)
    than the synthetic-fixture tests above, and it is skipped, not failed, if
    gitleaks is absent or its per-user scan lock is held by another scan.
    """

    def setUp(self):
        if GITLEAKS is None:
            self.skipTest("gitleaks not found on PATH")
        self.assertTrue(CONFIG_PATH.exists(), ".gitleaks.toml must exist at repo root")

    def test_head_ancestry_scoped_scan_has_zero_findings(self):
        report_path = Path(tempfile.mkstemp(suffix=".json")[1])
        try:
            proc = subprocess.run(
                [
                    GITLEAKS, "git", ".",
                    "--config", str(CONFIG_PATH),
                    "--max-target-megabytes", "2",
                    "--no-banner", "--exit-code", "0",
                    "--log-opts=HEAD",
                    "--report-format", "json", "--report-path", str(report_path),
                ],
                cwd=str(ROOT),
                capture_output=True, text=True, check=False,
            )
            if "lock" in proc.stderr.lower():
                self.skipTest(f"gitleaks per-user lock held by another scan: {proc.stderr.strip()}")
            findings = json.loads(report_path.read_text()) if report_path.exists() and report_path.stat().st_size else []
            self.assertEqual(
                findings, [],
                "this branch's own ancestry (--log-opts=HEAD) must scan clean; a nonempty "
                f"result here is this unit's own regression, not a sibling branch: {findings}",
            )
        finally:
            report_path.unlink(missing_ok=True)


class GithubAutomationDocConsistencyTests(unittest.TestCase):
    """Regression coverage for PR-3-codexfix-major-1: docs/github-automation.md
    must not restate the dated full-history scan counts that .gitleaks.toml's
    header comment owns, so the two files cannot drift back into contradicting
    each other about the same facts ("one canonical statement per fact")."""

    DOC_PATH = ROOT / "docs" / "github-automation.md"
    # Exact stale figures from the pre-fix allowlist regime that were previously
    # duplicated (and went stale) in docs/github-automation.md. These must live
    # only in .gitleaks.toml's header comment now.
    STALE_STRINGS = ("251 matches", "522 commits", "777 MB", "224 64-hex")

    def test_doc_does_not_restate_gitleaks_toml_owned_counts(self):
        text = self.DOC_PATH.read_text()
        for needle in self.STALE_STRINGS:
            self.assertNotIn(
                needle, text,
                f"docs/github-automation.md must not restate the dated count {needle!r}; "
                ".gitleaks.toml's header comment is the single canonical source",
            )

    def test_doc_does_not_claim_unqualified_zero_findings(self):
        text = self.DOC_PATH.read_text()
        section_start = text.index("### Secret-scan coverage boundary")
        section = text[section_start:section_start + 2000]
        self.assertNotIn(
            "the same scan and the working-tree scan report zero findings",
            section,
            "the doc must not claim an unqualified zero-findings result for the "
            "default (all-refs) scan; only the branch-ancestry-scoped scan is zero",
        )


if __name__ == "__main__":
    unittest.main()
