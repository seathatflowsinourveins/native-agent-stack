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

    def test_c4_narrative_commit_id_and_unrelated_api_key_sharing_one_line_the_api_key_is_still_detected(self):
        r"""Second-round Codex cross-family review finding (codex-review-72,
        .gitleaks.toml prose-narrative allowlist, duplicated under both
        rules that match it -- see .gitleaks.toml's "[[rules]] id" lines):
        whole-line anchoring (test_c2 above) is not enough for this
        allowlist, because its `.*?`/
        `.*` (any char, including `"`) can cross the closing quote of the
        JSON string holding the commit reference and reach a SECOND
        key:value pair later on the same physical line -- e.g.
        `{"detail": "pinned commit <hex>", "api_key": "<value>"}` on one
        compact line. The allowlist regex now uses `(?:[^\"\\\\]|\\\\.)*`
        instead of `.*`, so it cannot leave the JSON string holding the
        commit reference; a second key:value pair on the same line is
        outside that string and the line no longer matches the allowlist as
        a whole, so gitleaks's own finding for the unrelated key is not
        exempted. Uses `api_key`/HEX64 rather than the ghp_-shaped value: the
        GitHub PAT shape is caught by gitleaks's own dedicated `github-pat`
        rule, which never had this allowlist attached and so would pass
        regardless of this fix; HEX64 under `api_key` is caught by the same
        `generic-api-key` rule this narrative allowlist is scoped under
        (matching test_c2's technique above), so this only passes for the
        right reason. The two fields must NOT be compacted onto a line that
        also holds the JSON object's opening `{`: gitleaks's `regexTarget =
        "line"` allowlist match is against the exact physical line, and this
        allowlist's own `^\s*"..."` anchor already fails to match a line
        starting with `{` regardless of the crossing-quote bug being tested
        here -- that would make the assertion pass for the wrong reason (a
        pre-existing brace-anchoring mismatch, not this fix). Mirrors how
        the real files actually look (pretty-printed, each JSON object's
        `{`/`}` on its own line, fields following on later lines)."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            allow_dir = target / "evidence" / "artifacts" / "blind-catalog-convergence-20260921"
            allow_dir.mkdir(parents=True)
            (allow_dir / "claude-coverage-review.json").write_text(
                "{\n"
                f'  "detail": "pinned commit {HEX40}", "api_key": "{HEX64}"\n'
                "}\n"
            )
            findings = self._scan(target)
            secrets = {f["Secret"] for f in findings}
            self.assertIn(
                HEX64, secrets,
                f"the api_key finding co-located with an allowlisted commit-narrative field on "
                f"the same line must still be detected, got: {findings}",
            )

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


class GitleaksNarrativeAllowlistRegexTests(unittest.TestCase):
    """Pure-regex regression coverage for the prose-narrative commit-id
    allowlist (codex-review-72), independent of the installed gitleaks
    binary or its per-user lock -- gitleaks's own `generic-api-key` rule
    never fires on these two files' CURRENT content in the first place (no
    field name here matches its own access/auth/api/credential/creds/key/
    password/secret/token keyword list), so an end-to-end `dir`-mode
    positive control using only real file content would be vacuous; this
    tests the allowlist regex itself directly against real lines plus a
    constructed mixed line, complementing test_c4's end-to-end proof above
    (which uses a fixture line engineered to also satisfy the base rule)."""

    NARRATIVE_FILES = (
        ROOT / "evidence/artifacts/blind-catalog-convergence-20260921/claude-coverage-review.json",
        ROOT / "evidence/artifacts/blind-catalog-convergence-20260921/screening-ledger.json",
    )
    # The allowlist regex exactly as it read before the codex-review-72 fix,
    # frozen here for comparison; .gitleaks.toml no longer contains this form.
    PRE_FIX_REGEX = (
        r'''(?i)^\s*"[A-Za-z0-9_]+":\s*".*?(?:@\s*|\b(?:pin|pinned|commit|tree|'''
        r'''source_pin|source_commit|source)\b[\sa-zA-Z0-9_./:,\-]{0,25})[0-9a-f]{40}\b.*"\s*,?\s*$'''
    )

    def _current_allowlist_regexes(self):
        import tomllib
        with open(CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
        found = []
        for rule in data.get("rules", []):
            for allowlist in rule.get("allowlists", []):
                if any("blind-catalog-convergence" in p for p in allowlist.get("paths", [])):
                    found.extend(allowlist.get("regexes", []))
        return found

    def test_config_no_longer_contains_the_crossing_quote_regex(self):
        raw = CONFIG_PATH.read_text()
        self.assertNotIn(
            self.PRE_FIX_REGEX, raw,
            "the pre-fix `.*?`/`.*` form of the prose-narrative allowlist regex "
            "(which can cross a JSON string's closing quote) is still present",
        )

    def test_fixed_regex_rejects_mixed_line_but_keeps_every_real_narrative_match(self):
        regexes = self._current_allowlist_regexes()
        self.assertEqual(
            len(regexes), 2,
            "expected one copy of the narrative allowlist under generic-api-key "
            "and an identical copy under the other matching rule",
        )
        self.assertEqual(regexes[0], regexes[1], "the two rule-scoped copies must stay identical")
        current = re.compile(regexes[0])
        pre_fix = re.compile(self.PRE_FIX_REGEX)

        hexid = "1bf6df330b056ef93ab283083afdcce642387949"
        mixed_line = f'  "detail": "pinned commit {hexid}", "api_key": "{hexid}deadbeefdeadbeef"'
        self.assertTrue(
            pre_fix.match(mixed_line),
            "sanity check: the pre-fix regex must match this mixed line (it is the reported bug)",
        )
        self.assertFalse(
            current.match(mixed_line),
            "the fixed regex must not exempt a second key:value pair on the same physical line",
        )

        real_matches_before = 0
        for path in self.NARRATIVE_FILES:
            for line in path.read_text().splitlines():
                if pre_fix.match(line):
                    real_matches_before += 1
                    self.assertTrue(
                        current.match(line),
                        f"fixed regex regressed a real, previously-allowlisted narrative line: {line[:160]}",
                    )
        self.assertGreater(
            real_matches_before, 0,
            "the two narrative files must contain at least one real line the pre-fix regex "
            "matched, or this comparison is not exercising real content",
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
