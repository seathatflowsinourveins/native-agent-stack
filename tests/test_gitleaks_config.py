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
        r'^(?:(?P<commit>[0-9a-f]{40}):)?(?P<path>[^:]+):(?P<rule>[^:]+):(?P<line>\d+)$'
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
            self.assertIn(
                match.group("path"), self.NARRATIVE_FILES,
                f"fingerprint path is not one of the two reviewed narrative files: {line!r}",
            )
            self.assertIn(
                match.group("rule"), self.NARRATIVE_RULES,
                f"fingerprint rule is not generic-api-key or sourcegraph-access-token: {line!r}",
            )

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

        Uses a real, tracked narrative line (not a synthetic fixture file),
        modified in a disposable detached worktree so the injected marker
        never touches this repository's actual history or working tree."""
        rev_parse = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT),
            capture_output=True, text=True, check=False,
        )
        if rev_parse.returncode != 0:
            self.skipTest(f"could not resolve HEAD: {rev_parse.stderr.strip()}")

        worktree = Path(tempfile.mkdtemp(prefix="gitleaksignore-fp-test-"))
        worktree.rmdir()  # `git worktree add` requires the target not already exist
        add = subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree), "HEAD"],
            cwd=str(ROOT), capture_output=True, text=True, check=False,
        )
        if add.returncode != 0:
            self.skipTest(f"could not create a detached worktree: {add.stderr.strip()}")
        self._worktree = worktree

        target_file = worktree / self.NARRATIVE_FILES[0]
        lines = target_file.read_text().splitlines()
        marker_idx = None
        for i, line in enumerate(lines):
            if (
                re.search(r'\b(?:pin|pinned|commit|tree|source_pin|source_commit|source)\b', line, re.IGNORECASE)
                and re.search(r'[0-9a-f]{8,}', line)
                and line.rstrip().rstrip(",").endswith('"')
            ):
                marker_idx = i
                break
        self.assertIsNotNone(marker_idx, "expected at least one real commit-reference narrative line")

        # Built at runtime from short chunks under a name with no
        # credential-like substring, never as one literal: this source file
        # is itself scanned by gitleaks, and the assembled value is
        # deliberately shaped like a real GitHub personal access token so
        # this test can prove it is still caught when injected into a
        # narrative line's SAME JSON string. The literal never sits in any
        # file committed to THIS repository's real history -- only inside the
        # disposable worktree removed in tearDown -- so GitHub push
        # protection is not a concern here.
        marker_parts = ("ghp_", "wT9kLp3", "Qr7xNb2", "Yv5cMz8", "Hj4sDf6A")
        injected_marker = "".join(marker_parts)

        original = lines[marker_idx].rstrip()
        trailing_comma = original.endswith(",")
        core = original[:-1] if trailing_comma else original
        self.assertTrue(core.endswith('"'), f"expected a JSON string on this line: {original!r}")
        modified = core[:-1] + f"; api_key={injected_marker}" + '"' + ("," if trailing_comma else "")
        lines[marker_idx] = modified
        target_file.write_text("\n".join(lines) + "\n")

        subprocess.run(["git", "add", "-A"], cwd=str(worktree), check=True, capture_output=True)
        commit = subprocess.run(
            ["git", "commit", "-m", "test: inject synthetic marker for gitleaksignore fingerprint test"],
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
