"""Regression coverage for .gitleaks.toml's allowlist context-restriction.

Runs the PATH `gitleaks` (the guarded, memory-capped launcher; never the
underlying binary directly) in no-git `dir` mode against small synthetic fixture
directories built under a temp dir, using the real repository `.gitleaks.toml`.
Skips the whole test module if gitleaks is not on PATH, and skips individual
cases if the guarded launcher reports its per-user scan lock is held by another
scan (a busy lock is not a passing or failing result here). A scan that does not
complete raises _ScannerError, which unittest records as an error, never as a
detection result (_scan_findings).

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

import ast
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".gitleaks.toml"
# The dated SOTA manifests whose catalog pin ids the allowlist pins by value (one exact path each).
REVIEWED_MANIFESTS = ("manifest-20260926.json", "manifest-20260929.json")

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


class _ScannerError(Exception):
    """A scan that did not complete. Deliberately not an AssertionError: unittest records an AssertionError
    as a failure and any other exception as an error (CPython Lib/unittest/case.py, _addError), and the
    betterleaks trial job's fixture step accepts failures only (.github/workflows/validate.yml,
    secret-scan-betterleaks), so a scanner error fails that step instead of passing as a detection difference."""


# The guarded launchers' busy-lock contract: exit status 75 with this message, and no scan started
# (adoption/tools/gitleaks-guarded lines 23-32; adoption/tools/gitleaks-guarded-macos lines 29 and 125-130).
# Any other status is an error, even one whose message contains "lock", such as the Go runtime's
# "all goroutines are asleep - deadlock!".
LOCK_BUSY_STATUS = 75
LOCK_BUSY_MESSAGE = "another scan holds the per-user lock"


def _findings(report_text: str) -> list:
    """The findings in a JSON report. gitleaks 8.30.1 writes an empty report as `[]` (its detector
    starts from make([]report.Finding, 0), detect/detect.go line 127); betterleaks 1.8.1 writes `null`
    (cmd/git.go line 74 and cmd/directory.go line 72 start from a nil slice, which report/json.go
    encodes as is). Both mean no findings, so the betterleaks trial job
    (evidence/artifacts/betterleaks-parity-20260927/) fails only on detection differences."""
    findings = json.loads(report_text)
    return [] if findings is None else findings


def _scan_findings(scan_args: list, report_path: Path, cwd=None) -> list:
    """Run `gitleaks <scan_args>` with --exit-code 0 and a JSON report at report_path; return its findings.

    With --exit-code 0 both pinned scanners exit 0 whether or not they find anything, and only after
    writing the report. In gitleaks v8.30.1 and betterleaks v1.8.1 (cmd/root.go), findingSummaryAndExit
    writes the report whenever --report-path is set (gitleaks lines 463-491, betterleaks 610-638), and a
    report it cannot write is fatal (lines 489 and 636). It then exits 1 on a scan error (lines 493-495
    and 640-642) and with --exit-code on findings (lines 497-499 and 644-646). A fatal log exits 1
    (zerolog v1.33.0 log.go, Logger.Fatal, line 396), an unknown flag exits 126 (lines 226-228 and
    325-327), and a Go runtime crash or a signal gives another status. Detector() creates and removes the
    report path before the scan starts (lines 352-356 and 485-489), so a scan that dies leaves no report.
    Any nonzero status, and a missing or empty report after status 0, therefore raise _ScannerError:
    findings are read only from a completed scan. Raises _LockBusy for the guarded launcher's busy lock,
    so the caller can skipTest instead.
    """
    argv = [GITLEAKS, *scan_args, "--redact", "--no-banner", "--exit-code", "0",
            "--report-format", "json", "--report-path", str(report_path)]
    proc = subprocess.run(argv, cwd=None if cwd is None else str(cwd), capture_output=True, text=True, check=False)
    if proc.returncode == LOCK_BUSY_STATUS and LOCK_BUSY_MESSAGE in proc.stderr:
        raise _LockBusy(proc.stderr.strip())
    stderr_tail = "\n".join(proc.stderr.strip().splitlines()[-20:])
    if proc.returncode != 0:
        raise _ScannerError(f"gitleaks {scan_args[0]} exited {proc.returncode} under --exit-code 0, so the scan "
                            f"did not complete: {stderr_tail}")
    report = report_path.read_text() if report_path.exists() else ""
    if not report.strip():
        raise _ScannerError(f"gitleaks {scan_args[0]} exited 0 without writing its report: {stderr_tail}")
    findings = _findings(report)
    for finding in findings:
        # A redacted finding's full line can still contain adjacent values.
        # Assertions need only the redacted match and location metadata.
        finding.pop("Line", None)
    return findings


def _finding_fields(findings):
    """Identify JSON keys from redacted matches without reading secret values."""
    fields = set()
    for finding in findings:
        match = re.search(r'([A-Za-z0-9_./-]+)"?\s*:\s*"?REDACTED', finding.get("Match", ""))
        if match:
            fields.add(match.group(1))
    return fields


def _pr_scan_range():
    """Use the actual main merge base; never expand into HEAD ancestry."""
    try:
        base = subprocess.run(["git", "merge-base", "HEAD", "refs/remotes/origin/main"],
                              cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise unittest.SkipTest("PR-range history check requires HEAD and origin/main; no history scanned") from exc
    if not re.fullmatch(r"[0-9a-f]{40}", base):
        raise _ScannerError("Cannot establish the PR merge base for the bounded scan")
    expected = f"{base}..HEAD"
    configured = os.environ.get("GITLEAKS_TEST_RANGE", expected)
    if configured != expected:
        raise _ScannerError("GITLEAKS_TEST_RANGE must equal the actual merge-base..HEAD range")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()
    if head == base:
        raise unittest.SkipTest("empty PR range on main; no history scanned")
    return expected


def _run_gitleaks(target_dir: Path) -> list:
    """Run `gitleaks dir .` (cwd = target_dir) with the real repo config.

    Returns the parsed JSON findings list. Raises _LockBusy if the guarded
    launcher reports its per-user scan lock is held by another scan, so the
    caller can skipTest instead of failing, and _ScannerError if the scan
    did not complete (_scan_findings).
    """
    return _scan_findings(["dir", ".", "--config", str(CONFIG_PATH)], target_dir / "gitleaks-report.json",
                          cwd=target_dir)


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
            fields = _finding_fields(findings)
            self.assertIn("api_key", fields, "64-hex api_key under a non-allowlisted path must be detected")
            self.assertIn("token", fields, "40-hex token under a non-allowlisted path must be detected")

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
            fields = _finding_fields(findings)
            self.assertIn(
                "disk_token", fields,
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
            self.assertTrue(
                any(f["RuleID"] == "github-pat" for f in findings),
                "a ghp_ token on a different line from the allowlisted cursor must still be detected",
            )
            self.assertNotIn(
                "next_page_token", _finding_fields(findings),
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
            fields = _finding_fields(findings)
            self.assertIn(
                "api_key", fields,
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
            fields = _finding_fields(findings)
            self.assertIn(
                "api_key", fields,
                "the same base64-shaped value under an unrelated 'api_key' field must be detected "
                "even though the identical value under 'next_page_token' is legitimately suppressed",
            )

    def test_population_receipt_hash_fields_are_not_credentials(self):
        for name in ("confirmed-four", "note-class"):
            for compact in (False, True):
                with self.subTest(receipt=name, compact=compact), tempfile.TemporaryDirectory() as tmp:
                    target = Path(tmp)
                    path = target / f"evidence/artifacts/g5-start-closure-1-20261009/{name}-population-receipt.json"
                    path.parent.mkdir(parents=True)
                    path.write_text(json.dumps({"before_population_key_sha256": HEX64,
                                                "after_population_key_sha256": HEX64[::-1]},
                                               indent=None if compact else 2) + "\n")
                    self.assertEqual(self._scan(target), [], "reviewed population digests are not credentials")

    def test_population_fragment_boundary_rejects_partial_matches_and_accepts_safe_separators(self):
        # gitleaks v8.30.1 sources/file.go:21,166-246 and sources/common.go:16,56-125:
        # a 100,000-byte read peeks up to 25,000 more bytes. Put the digest's
        # last byte in the next fragment, matching the hosted findings.
        # Retain the complete-digest allowlist and use the upstream reader's
        # double-newline boundary instead of suppressing truncated values.
        fragment_end = 125_001
        for name in ("confirmed-four", "note-class"):
            for field in ("before_population_key_sha256", "after_population_key_sha256"):
                with self.subTest(receipt=name, field=field), tempfile.TemporaryDirectory() as tmp:
                    target = Path(tmp)
                    path = target / f"evidence/artifacts/g5-start-closure-1-20261009/{name}-population-receipt.json"
                    path.parent.mkdir(parents=True)
                    prefix = '{"padding":"'
                    middle = f'","{field}":"'
                    padding = "x" * (fragment_end - len(prefix + middle + HEX64))
                    content = prefix + padding + middle + HEX64 + '"}\n'
                    path.write_text(content)
                    self.assertIn("generic-api-key", {f["RuleID"] for f in self._scan(target)},
                                  "an incomplete native match must not gain a broader digest exception")
                    path.write_text(json.dumps(json.loads(content), indent=2,
                                               separators=(",\n", ": ")) + "\n")
                    self.assertEqual(self._scan(target), [],
                                     "native safe separators preserve complete reviewed population digests")

    def test_population_receipts_scan_clean_with_native_file_fragments(self):
        # Byte-for-byte public receipt fixtures exercise the serialization
        # that the hosted working-tree scanner actually sees. The PR-range
        # history check alone missed this failure because its fragments differ.
        for name in ("confirmed-four", "note-class"):
            with self.subTest(receipt=name), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp)
                relative = f"evidence/artifacts/g5-start-closure-1-20261009/{name}-population-receipt.json"
                source = ROOT / relative
                if not source.is_file():
                    self.skipTest(f"repository population receipt absent from isolated fixture: {name}")
                path = target / relative
                path.parent.mkdir(parents=True)
                shutil.copyfile(source, path)
                self.assertEqual(self._scan(target), [],
                                 "the actual population receipt must scan clean in native file mode")

    def test_population_fragment_boundary_keeps_other_contexts_detectable(self):
        cases = [
            ("unreviewed", "after_population_key_sha256", HEX64, "generic-api-key"),
            ("note-class", "api_key", HEX64, "generic-api-key"),
            ("note-class", "after_population_key_sha256", HEX64.upper(), "generic-api-key"),
            ("note-class", "after_population_key_sha256", HEX64[:-1], "generic-api-key"),
            ("note-class", "after_population_key_sha256", HEX64 + "a", "generic-api-key"),
            ("note-class", "after_population_key_sha256", GH_PAT_SHAPED_VALUE, "github-pat"),
        ]
        for name, field, value, rule in cases:
            with self.subTest(receipt=name, field=field, length=len(value), rule=rule), \
                    tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp)
                path = target / f"evidence/artifacts/g5-start-closure-1-20261009/{name}-population-receipt.json"
                path.parent.mkdir(parents=True)
                prefix = '{"padding":"'
                middle = f'","{field}":"'
                # The PAT rule needs its terminating delimiter in the
                # fragment; keep that delimiter at the same boundary.
                end = 125_000 if rule == "github-pat" else 125_001
                padding = "x" * (end - len(prefix + middle + value))
                path.write_text(prefix + padding + middle + value + '"}\n')
                self.assertIn(rule, {f["RuleID"] for f in self._scan(target)})

    def test_population_fragment_boundary_same_line_api_key_still_fires(self):
        for name in ("confirmed-four", "note-class"):
            with self.subTest(receipt=name), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp)
                path = target / f"evidence/artifacts/g5-start-closure-1-20261009/{name}-population-receipt.json"
                path.parent.mkdir(parents=True)
                prefix = '{"padding":"'
                middle = '","after_population_key_sha256":"'
                padding = "x" * (125_001 - len(prefix + middle + HEX64))
                path.write_text(prefix + padding + middle + HEX64 + '","api_key":"' + HEX64 + '"}\n')
                self.assertIn("api_key", _finding_fields(self._scan(target)))

    def test_population_receipt_same_line_api_key_still_fires(self):
        for name in ("confirmed-four", "note-class"):
            with self.subTest(receipt=name), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp)
                path = target / f"evidence/artifacts/g5-start-closure-1-20261009/{name}-population-receipt.json"
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({"before_population_key_sha256": HEX64,
                                            "after_population_key_sha256": HEX64[::-1],
                                            "api_key": HEX64}) + "\n")
                findings = self._scan(target)
                self.assertIn("api_key", _finding_fields(findings))
                self.assertTrue(all(f["Secret"] == "REDACTED" for f in findings))

    def test_population_receipt_exception_is_path_field_shape_and_rule_scoped(self):
        cases = [
            ("unreviewed-population-receipt.json", {"before_population_key_sha256": HEX64}, "generic-api-key"),
            ("note-class-population-receipt.json", {"before_population_key_sha256": HEX64.upper()}, "generic-api-key"),
            ("note-class-population-receipt.json", {"after_population_key_sha256": GH_PAT_SHAPED_VALUE}, "github-pat"),
        ]
        for name, obj, rule in cases:
            with self.subTest(receipt=name, rule=rule), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp)
                path = target / "evidence/artifacts/g5-start-closure-1-20261009" / name
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(obj) + "\n")
                self.assertIn(rule, {f["RuleID"] for f in self._scan(target)})

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

    def test_d5_retained_sweep_input_pin_lines_only(self):
        """The retained code-navigation layer input: its "pin" lines are exempt, another 40-hex field in it
        is still detected, and so are the same pin lines in a sibling input file."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            base = "evidence/artifacts/landscape-sweep-20260926/inputs/"
            self._manifest_fixture(target, base + "code-navigation.json", {"token": HEX40})
            self._manifest_fixture(target, base + "semantic-rag.json", {})
            by_file = {}
            for f in self._scan(target):
                if f["RuleID"] == "sourcegraph-access-token":
                    by_file.setdefault(f["File"], []).append(f["StartLine"])
            self.assertEqual(len(by_file.get(base + "code-navigation.json", [])), 1,
                             f"only the non-pin token line may be detected in the retained input: {by_file}")
            self.assertEqual(len(by_file.get(base + "semantic-rag.json", [])), 2,
                             f"pin lines in any other input file must still be detected: {by_file}")

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
        for name in REVIEWED_MANIFESTS:
            with self.subTest(manifest=name), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp)
                self._free_form_manifest(target, f"catalogs/sota-convergence/{name}", ids, [])
                findings = [f for f in self._scan(target) if f["RuleID"] == "sourcegraph-access-token"]
                self.assertEqual(findings, [], "reviewed pin commit ids in the reviewed manifest must not be flagged")

    def test_d4_unreviewed_values_and_other_paths_stay_detected(self):
        """Only the reviewed ids in that exact file are exempt. An unreviewed 40-hex value (under another field, or
        as free text in a pin), the uppercase form of a reviewed id, an sgp_-prefixed token, and the reviewed ids in
        any other file are all still detected."""
        ids = self._reviewed_manifest_ids()
        extra = [{"token": HEX40}, {"pin": f"sourcegraph legacy access token {HEX40}"},
                 {"pin": ids[0].upper()}, {"pin": f"sgp_{ids[0]}"}]
        for name in REVIEWED_MANIFESTS:
            with self.subTest(manifest=name), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp)
                self._free_form_manifest(target, f"catalogs/sota-convergence/{name}", ids, extra)
                self._free_form_manifest(target, "catalogs/sota-convergence/manifest-20260925.json", ids, [])
                by_file = {}
                for f in self._scan(target):
                    if f["RuleID"] == "sourcegraph-access-token":
                        by_file.setdefault(f["File"], []).append(f["StartLine"])
                self.assertEqual(len(by_file.get(f"catalogs/sota-convergence/{name}", [])), len(extra),
                                 f"every unreviewed value in the reviewed manifest must be detected: {by_file}")
                self.assertEqual(len(by_file.get("catalogs/sota-convergence/manifest-20260925.json", [])), 4,
                                 f"reviewed ids outside the exact reviewed paths must be detected: {by_file}")

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

    RETURNED_REPORT_PATH = "observability/memory-scheduled-results-20260927.json"
    RETURNED_REPORT_FINGERPRINTS = REVIEWED_FINGERPRINTS + [
        "20d12bd285ea6bd2d67a2fa02a3880d58390fbc17b4fedc2d9862f7db89e9088",
        "a29791aae4200620764263b4e3fd1b4a383746fda9e82c30c7cb9ee59ed1a6e8",
        "d1349458a0797550dfac40c438d35e067f8d5277deabbba283695786c20d0555",
    ]

    def test_e3_returned_report_reviewed_fingerprints_are_not_detected(self):
        """The seven source-confirmed rejection digests are exempt in this exact report."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._fingerprint_fixture(target, self.RETURNED_REPORT_PATH, {},
                                      values=self.RETURNED_REPORT_FINGERPRINTS)
            findings = [f for f in self._scan(target) if f["RuleID"] == "generic-api-key"]
            self.assertEqual(findings, [], "reviewed rejection digests must not be flagged")

    def test_e4_returned_report_other_fields_values_and_paths_stay_detected(self):
        """The new exception does not extend the old path or suppress credential fields."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self._fingerprint_fixture(target, self.RETURNED_REPORT_PATH,
                                      {"api_key": HEX64, "token": HEX64},
                                      values=[self.RETURNED_REPORT_FINGERPRINTS[0], HEX64[::-1]])
            self._fingerprint_fixture(target, "observability/memory-scheduled-results-20260928.json",
                                      {}, values=self.RETURNED_REPORT_FINGERPRINTS)
            self._fingerprint_fixture(target, "observability/memory-scheduled-20260923.json",
                                      {}, values=self.RETURNED_REPORT_FINGERPRINTS[-3:])
            findings = [f for f in self._scan(target) if f["RuleID"] == "generic-api-key"]
            own = [f for f in findings if f["File"] == self.RETURNED_REPORT_PATH]
            self.assertEqual(len(own), 3, "unreviewed key, api_key and token must remain detected")
            self.assertEqual(_finding_fields(own), {"key", "api_key", "token"})
            self.assertEqual(sum(f["File"].endswith("results-20260928.json") for f in findings), 7)
            self.assertEqual(sum(f["File"].endswith("memory-scheduled-20260923.json") for f in findings), 3)

    def test_e5_returned_report_second_secret_on_same_line_stays_detected(self):
        """Whole-line matching must not hide an adjacent credential in compact JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            path = target / self.RETURNED_REPORT_PATH
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"key": self.RETURNED_REPORT_FINGERPRINTS[0],
                                        "api_key": HEX64}) + "\n")
            findings = self._scan(target)
            self.assertIn("api_key", _finding_fields(findings))

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
            fields = _finding_fields(findings)
            self.assertIn("credential.key", fields, "a credential.key value in the reviewed manifest must still be detected")
            self.assertIn("api_key", fields, "an api_key value in the reviewed manifest must still be detected")

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
            fields = _finding_fields(findings)
            self.assertEqual(len(findings), 2, "both dot-segment keys must still be detected")
            self.assertIn("credential_store.py", fields, "a '..' path key must not be exempted")
            self.assertIn("api_key.py", fields, "a '.' path key must not be exempted")

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
            self.assertIn("api_key", _finding_fields(findings),
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
        unnoticed: the scan runs through _scan_findings, which raises _ScannerError
        for any nonzero exit status, so a nonzero status here errors this test.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            nonallow = target / "some" / "other" / "path"
            nonallow.mkdir(parents=True)
            (nonallow / "data.json").write_text(json.dumps({"api_key": HEX64}))
            findings = self._scan(target)
            self.assertTrue(findings, "fixture must contain a detected leak for this test to be meaningful")


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
        # when run before these files are committed. Match the injected marker
        # by detector and exact location; all native scans remain redacted.
        try:
            findings = _scan_findings(["git", str(worktree), "--config", str(CONFIG_PATH),
                                       "--gitleaks-ignore-path", str(ROOT), f"--log-opts=-1 {sha}"], report_path)
        except _LockBusy as exc:
            self.skipTest(f"gitleaks per-user lock held by another scan: {exc}")
        matches = [
            f for f in findings
            if f.get("RuleID") == "github-pat" and f.get("File") == target_path
            and f.get("StartLine") == marker_idx + 1
        ]
        self.assertTrue(
            matches,
            f"a secret injected into the SAME JSON string as a fingerprint-ignored narrative "
            f"commit reference, on a NEW commit, must still be detected: {findings}",
        )


class GitleaksBranchAncestryHistoryTests(unittest.TestCase):
    """Real-history acceptance on the actual PR range, without a full-history scan.

    The historical test name is retained. The current scan is bounded to
    merge-base..HEAD; an explicit GITLEAKS_TEST_RANGE must name that same range.
    Main's empty range and checkouts without origin/main are explicit skips,
    with no history scanned. HEAD/--all remain rejected. Scanner errors remain
    errors, never an empty passing result.
    """

    def setUp(self):
        if GITLEAKS is None:
            self.skipTest("gitleaks not found on PATH")
        self.assertTrue(CONFIG_PATH.exists(), ".gitleaks.toml must exist at repo root")

    def test_head_ancestry_scoped_scan_has_zero_findings(self):
        scope = _pr_scan_range()
        report_path = Path(tempfile.mkstemp(suffix=".json")[1])
        try:
            # This scan reads the real history, and CI logs on this public repository are world-readable, so
            # it redacts like the secret-scan job (--redact: Finding.Redact masks Secret, Match and Line in
            # gitleaks v8.30.1 report/finding.go lines 78-86; betterleaks v1.8.1 cmd/root.go line 589), and
            # the failure message names only non-secret fields.
            try:
                findings = _scan_findings(["git", ".", "--config", str(CONFIG_PATH), "--max-target-megabytes", "2",
                                           f"--log-opts={scope}"], report_path, cwd=ROOT)
            except _LockBusy as exc:
                self.skipTest(f"gitleaks per-user lock held by another scan: {exc}")
            located = [(f.get("RuleID"), f.get("File"), f.get("StartLine"), f.get("Fingerprint")) for f in findings]
            self.assertEqual(
                located, [],
                "this branch's actual PR range must scan clean; a nonempty "
                f"result here is this unit's own regression, not a sibling branch: {located}",
            )
        finally:
            report_path.unlink(missing_ok=True)


class ScannerErrorTests(unittest.TestCase):
    """A scan that does not complete must reach unittest as an error, never as a detection result.
    Cross-family review of the betterleaks trial (2026-09-28, P2): _run_gitleaks turned an unexpected exit
    status into an AssertionError, which the trial job's fixture step accepts as a detection difference, and
    it read exit status 1 without a report as no findings. The scanner is replaced in memory, so these tests
    need no gitleaks and run none."""

    BUSY = "gitleaks: another scan holds the per-user lock; retry after it finishes\n"

    @staticmethod
    def _scanner(returncode, report=None, stderr=""):
        """A stand-in for subprocess.run: writes `report` to the --report-path when it is not None, then
        returns `returncode` and `stderr`."""
        def run(argv, **kwargs):
            if report is not None:
                Path(argv[argv.index("--report-path") + 1]).write_text(report)
            return subprocess.CompletedProcess(argv, returncode, "", stderr)
        return run

    def _scan_with(self, returncode, report=None, stderr=""):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(subprocess, "run", side_effect=self._scanner(returncode, report, stderr)):
            return _run_gitleaks(Path(tmp))

    def test_a_nonzero_exit_status_is_a_scanner_error_with_or_without_a_report(self):
        """--exit-code 0 makes findings exit 0, so any other status, a signal included, is a scan that did not
        complete, even when a report was written first (a partial scan exits 1 after writing it)."""
        self.assertFalse(issubclass(_ScannerError, AssertionError))
        for returncode in (-11, -9, 139, 1, 2, 126, 78):
            for report in (None, "null\n", "[]\n"):
                with self.subTest(returncode=returncode, report=report), self.assertRaises(_ScannerError):
                    self._scan_with(returncode, report)

    def test_b_exit_0_needs_a_written_report(self):
        for report in (None, "", "\n"):
            with self.subTest(report=report), self.assertRaises(_ScannerError):
                self._scan_with(0, report)
        self.assertEqual(self._scan_with(0, "null\n"), [])
        self.assertEqual(self._scan_with(0, "[]\n"), [])
        self.assertEqual(self._scan_with(0, '[{"RuleID": "rule-a"}]\n'), [{"RuleID": "rule-a"}])

    def test_c_only_the_guarded_launchers_busy_lock_skips(self):
        with self.assertRaises(_LockBusy):
            self._scan_with(75, stderr=self.BUSY)
        for returncode, stderr in ((2, "fatal error: all goroutines are asleep - deadlock!\n"), (75, ""),
                                   (1, "gitleaks: could not acquire the per-user lock; scan was not started\n")):
            with self.subTest(returncode=returncode, stderr=stderr), self.assertRaises(_ScannerError):
                self._scan_with(returncode, stderr=stderr)

    def test_d_a_detection_test_errors_when_its_scan_does_not_complete(self):
        """The review's probe as a test: a detection test shaped like test_a is a unittest error when its scan
        exits -11, 139 or 1 or writes no report, and still a failure when a completed scan misses the value."""
        class Detection(unittest.TestCase):
            def test_detected(inner):
                with tempfile.TemporaryDirectory() as tmp:
                    inner.assertIn("api_key", _finding_fields(_run_gitleaks(Path(tmp))))

        for returncode, report, status_line in ((-11, None, "FAILED (errors=1)"), (139, None, "FAILED (errors=1)"),
                                                (1, None, "FAILED (errors=1)"), (1, "null\n", "FAILED (errors=1)"),
                                                (0, None, "FAILED (errors=1)"), (0, "null\n", "FAILED (failures=1)")):
            with self.subTest(returncode=returncode, report=report):
                stream = io.StringIO()
                with mock.patch.object(subprocess, "run", side_effect=self._scanner(returncode, report)):
                    unittest.TextTestRunner(stream=stream, verbosity=0).run(Detection("test_detected"))
                self.assertEqual(stream.getvalue().strip().splitlines()[-1], status_line)

    def test_e_every_scan_in_this_module_goes_through_scan_findings(self):
        """Outside _scan_findings, every subprocess.run here runs git (an argument list that starts with
        "git"), so no scan can bypass the classification above."""
        def calls(node, function):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield from calls(child, child.name)
                    continue
                if (isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr == "run"
                        and isinstance(child.func.value, ast.Name) and child.func.value.id == "subprocess"):
                    first = child.args[0] if child.args else None
                    runs_git = (isinstance(first, ast.List) and bool(first.elts)
                                and isinstance(first.elts[0], ast.Constant) and first.elts[0].value == "git")
                    if not runs_git:
                        yield function, child.lineno
                yield from calls(child, function)

        module = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        others = list(calls(module, "<module>"))
        self.assertEqual([function for function, _ in others], ["_scan_findings"], others)

    def test_f_the_history_scan_redacts_and_its_failure_names_no_secret(self):
        """The branch-ancestry test scans the real history, and CI logs are public: it passes --redact, and a
        failure lists rule, file, line and fingerprint only. The stand-in report here is deliberately
        unredacted, so the message is checked on its own."""
        sentinel = "SENTINEL-" + HEX40
        finding = {"RuleID": "generic-api-key", "File": "a.json", "StartLine": 3, "Secret": sentinel,
                   "Match": f"token: {sentinel}", "Line": f'"token": "{sentinel}"',
                   "Fingerprint": "0123abcd:a.json:generic-api-key:3"}
        argvs = []

        def run(argv, **kwargs):
            argvs.append(argv)
            Path(argv[argv.index("--report-path") + 1]).write_text(json.dumps([finding]))
            return subprocess.CompletedProcess(argv, 0, "", "")

        stream = io.StringIO()
        with mock.patch.object(subprocess, "run", side_effect=run), \
                mock.patch(f"{__name__}.GITLEAKS", "gitleaks"), \
                mock.patch(f"{__name__}._pr_scan_range", return_value="a" * 40 + "..HEAD"):
            unittest.TextTestRunner(stream=stream, verbosity=0).run(
                GitleaksBranchAncestryHistoryTests("test_head_ancestry_scoped_scan_has_zero_findings"))
        output = stream.getvalue()
        self.assertEqual(len(argvs), 1, argvs)
        self.assertIn("--redact", argvs[0])
        self.assertIn("--log-opts=" + "a" * 40 + "..HEAD", argvs[0])
        self.assertEqual(output.strip().splitlines()[-1], "FAILED (failures=1)")
        self.assertIn(finding["Fingerprint"], output)
        self.assertNotIn(sentinel, output)

    def test_g_history_range_rejects_unbounded_or_unrelated_overrides(self):
        completed = subprocess.CompletedProcess([], 0, "b" * 40 + "\n", "")
        for scope in ("HEAD", "--all", "a" * 40 + "..HEAD"):
            with self.subTest(scope=scope), mock.patch.dict(os.environ, {"GITLEAKS_TEST_RANGE": scope}), \
                    mock.patch.object(subprocess, "run", return_value=completed):
                with self.assertRaisesRegex(_ScannerError, "actual merge-base"):
                    _pr_scan_range()

    def test_h_history_range_uses_the_actual_merge_base(self):
        completed = subprocess.CompletedProcess([], 0, "b" * 40 + "\n", "")
        head = subprocess.CompletedProcess([], 0, "c" * 40 + "\n", "")
        with mock.patch.dict(os.environ, {"GITLEAKS_TEST_RANGE": "b" * 40 + "..HEAD"}), \
                mock.patch.object(subprocess, "run", side_effect=[completed, head]) as run:
            self.assertEqual(_pr_scan_range(), "b" * 40 + "..HEAD")
        self.assertEqual([call.args[0] for call in run.call_args_list],
                         [["git", "merge-base", "HEAD", "refs/remotes/origin/main"],
                          ["git", "rev-parse", "HEAD"]])

    def test_i_history_range_skips_an_empty_main_range(self):
        completed = subprocess.CompletedProcess([], 0, "b" * 40 + "\n", "")
        with mock.patch.dict(os.environ, {"GITLEAKS_TEST_RANGE": "b" * 40 + "..HEAD"}), \
                mock.patch.object(subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(unittest.SkipTest, "empty PR range"):
                _pr_scan_range()

    def test_j_history_range_skips_a_checkout_without_origin_main(self):
        with mock.patch.object(subprocess, "run", side_effect=subprocess.CalledProcessError(128, ["git"])), \
                self.assertRaisesRegex(unittest.SkipTest, "origin/main"):
            _pr_scan_range()


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
