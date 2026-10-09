"""Native gitleaks 8.30.1 checks of synthetic sweep-record commit contexts.

These tiny local Git repositories contain replacement identifiers, never vendor captures or credentials.
The scanner retains its native default decoding depth (5), uses --redact, and contacts no remote.
The report is reduced to rule/file/line/column metadata before assertions, following the completed-scan
contract in test_gitleaks_config.py. No real repository history is scanned here.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".gitleaks.toml"
GITLEAKS = os.environ.get("GITLEAKS_TEST_BINARY") or shutil.which("gitleaks")
REQUIRED = bool(os.environ.get("GITLEAKS_TESTS_REQUIRED"))
RULE = "sourcegraph-access-token"
MANIFEST = "catalogs/sota-convergence/manifest-20261009-synthetic-policy.json"
RETURNS = "evidence/artifacts/landscape-sweep-20261009-synthetic-policy/returns.json"
# A contiguous literal identifier in this test source would itself trigger the native rule.
IDENTIFIER = "".join(("d71ec4b20f889a10", "65ec3a1826fdda80", "9b73165c"))
LOW_ENTROPY_COMMIT = "0" * 40
MODERN = "".join(("sg", "p_", IDENTIFIER))


def manifest_row(owner_repo="fixture-owner/fixture-main-one", commit=IDENTIFIER, branch="main",
                 dated="2026-10-08T02:02:46Z", api_clause=False):
    row = (f"https://github.com/{owner_repo}/commit/{commit} — the newest default-branch ({branch}) "
           f"commit since 2026-07-11, dated {dated}")
    if api_clause:
        return row + (" (gh api commits?since=2026-07-11T00:00:00Z&per_page=1). "
                      "It meets the 90-day maintenance rule; repository archived=false.")
    return row + ". It meets the 90-day rule; archived=false."


def manifest(rows, *, escaped_dash=False):
    return json.dumps({"context": "sourcegraph", "evidence": rows}, ensure_ascii=escaped_dash, indent=2) + "\n"


def returns(commit=IDENTIFIER, prefix="Decision: synthetic sourcegraph review."):
    note = (prefix + " [The required commit check](https://api.github.com/repos/fixture-owner/fixture-client/"
            f"commits?since=2026-07-11T00%3A00%3A00Z&per_page=1) returned {commit} dated 2026-10-08."
            "\n\nSynthetic second paragraph retained in the JSON string.")
    return json.dumps({"notes": note}, ensure_ascii=False, indent=2) + "\n"


def unicode_escape(value):
    return "".join(f"\\u{ord(char):04x}" for char in value)


def percent_escape(value):
    return "".join(f"%{ord(char):02X}" for char in value)


def safe_locations(findings):
    return [(item["rule"], item["file"], item["line"], item["start"], item["end"]) for item in findings]


def priority_prefix():
    prefix = [shutil.which("nice"), "-n", "19"] if shutil.which("nice") else []
    if shutil.which("ionice"):
        prefix += [shutil.which("ionice"), "-c", "3"]
    return prefix


class GitleaksRecordBinaryPresenceTests(unittest.TestCase):
    def test_required_native_binary_is_available(self):
        if REQUIRED:
            self.assertTrue(GITLEAKS and os.access(GITLEAKS, os.X_OK),
                            "GITLEAKS_TESTS_REQUIRED requires an executable native gitleaks binary")


class GitleaksRecordCommitContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not GITLEAKS or not os.access(GITLEAKS, os.X_OK):
            if REQUIRED:
                raise AssertionError("GITLEAKS_TESTS_REQUIRED requires native gitleaks 8.30.1")
            raise unittest.SkipTest("native gitleaks is unavailable")
        version = subprocess.run([GITLEAKS, "version"], capture_output=True, text=True, timeout=15, check=False)
        if version.returncode != 0:
            raise RuntimeError(f"native gitleaks version probe exited {version.returncode}")
        if version.stdout.strip() != "8.30.1":
            if REQUIRED:
                raise AssertionError("GITLEAKS_TESTS_REQUIRED requires the pinned native gitleaks 8.30.1")
            raise unittest.SkipTest("these native integration cases require gitleaks 8.30.1")

    def scan(self, files, *, upstream_default=False):
        """Scan one synthetic commit; never return Secret, Match, Line, or commit identifiers."""
        with tempfile.TemporaryDirectory(prefix="gitleaks-record-context-") as tmp:
            work = Path(tmp)
            repo = work / "repo"
            repo.mkdir()
            for relative, text in files.items():
                path = repo / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            git_env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
            git_env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
            for command in (("init", "-q"), ("add", "--", "."),
                            ("commit", "-q", "-m", "synthetic commit-context fixture")):
                done = subprocess.run(["git", "-c", f"core.hooksPath={os.devnull}",
                                       "-c", "user.name=Synthetic Fixture", "-c", "user.email=fixture@example.invalid",
                                       *command], cwd=repo, env=git_env, capture_output=True, text=True,
                                      timeout=30, check=False)
                if done.returncode:
                    raise RuntimeError(f"synthetic git {command[0]} exited {done.returncode}")
            config = CONFIG
            if upstream_default:
                config = work / "default.toml"
                config.write_text("[extend]\nuseDefault = true\n", encoding="utf-8")
            report = work / "report.json"
            # Omit --max-decode-depth: the installed client's default 5 is the acceptance boundary.
            done = subprocess.run([*priority_prefix(), GITLEAKS, "git", ".", "--config", str(config),
                                   "--log-opts=HEAD", "--redact", "--exit-code", "0", "--no-banner",
                                   "--report-format", "json", "--report-path", str(report)],
                                  cwd=repo, env=git_env, capture_output=True, text=True, timeout=60, check=False)
            if done.returncode or not report.is_file():
                raise RuntimeError(f"native synthetic scan did not complete (exit {done.returncode})")
            try:
                raw = json.loads(report.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise RuntimeError("native synthetic scan did not write a readable JSON report") from None
            if not isinstance(raw, list):
                raise RuntimeError("native synthetic scan report is not a findings list")
            return [{"rule": item["RuleID"], "file": item["File"], "line": item["StartLine"],
                     "start": item["StartColumn"], "end": item["EndColumn"],
                     "decoded": any("decode" in tag.lower() for tag in item.get("Tags", []))} for item in raw]

    def test_five_real_record_shapes_trigger_upstream_and_are_scoped_out_by_policy(self):
        rows = [manifest_row(),
                manifest_row("vendor-owner/fixture-main-two", dated="2026-10-01T22:55:00Z", api_clause=True),
                manifest_row("FixtureOwner/FixtureMaster", branch="master", dated="2026-10-07T10:15:37Z"),
                manifest_row("fixture-owner/fixture-main-four", dated="2026-10-01T16:03:06Z")]
        files = {MANIFEST: manifest(rows, escaped_dash=True), RETURNS: returns()}
        expected = {(relative, index) for relative, text in files.items()
                    for index, line in enumerate(text.splitlines(), 1) if IDENTIFIER in line}
        self.assertEqual(len(expected), 5)
        baseline = [item for item in self.scan(files, upstream_default=True) if item["rule"] == RULE]
        self.assertEqual({(item["file"], item["line"]) for item in baseline}, expected,
                         f"upstream rule must actually detect all five synthetic contexts: {safe_locations(baseline)}")
        scoped = [item for item in self.scan(files) if item["rule"] == RULE]
        self.assertEqual(safe_locations(scoped), [], "reviewed sweep commit contexts should be exempt")

    def test_path_and_commit_context_must_both_match(self):
        bare = json.dumps({"observation": f"sourcegraph {IDENTIFIER}"}, indent=2) + "\n"
        files = {MANIFEST: bare, RETURNS: bare,
                 "unreviewed/commit-context.json": manifest([manifest_row()]),
                 "unreviewed/notes.json": returns()}
        findings = [item for item in self.scan(files) if item["rule"] == RULE]
        self.assertEqual({item["file"] for item in findings}, set(files),
                         f"both allowlist conditions are required: {safe_locations(findings)}")

    def test_modern_candidates_survive_plaintext_and_decoded_same_line_contexts(self):
        manifest_modern = manifest([manifest_row(commit=LOW_ENTROPY_COMMIT)])
        commit_line = next(line for line in manifest_modern.splitlines() if "/commit/" in line)
        manifest_modern = manifest_modern.replace(commit_line, commit_line + ", " + json.dumps(MODERN))
        notes_modern = returns(LOW_ENTROPY_COMMIT, prefix=f"Decision: synthetic sourcegraph {MODERN} retained.")
        files = {"unreviewed/modern.txt": MODERN + "\n", MANIFEST: manifest_modern, RETURNS: notes_modern}
        encoded_files = []
        for label, encode in (("unicode", unicode_escape), ("percent", percent_escape)):
            for form, value in (("prefix", encode(MODERN[:4]) + MODERN[4:]), ("full", encode(MODERN))):
                relative = f"evidence/artifacts/landscape-sweep-20261009-{label}-{form}/returns.json"
                files[relative] = notes_modern.replace(MODERN, value)
                encoded_files.append(relative)
        findings = [item for item in self.scan(files) if item["rule"] == RULE]
        self.assertEqual({item["file"] for item in findings}, set(files),
                         f"modern candidates must survive in every fixture: {safe_locations(findings)}")
        for relative in (MANIFEST, RETURNS, "unreviewed/modern.txt"):
            text = files[relative]
            line_number, line = next((index, line) for index, line in enumerate(text.splitlines(), 1)
                                     if MODERN in line)
            # detect/location.go at v8.30.1 counts UTF-8 bytes and includes the preceding newline in columns
            # after line 1 (prevNewLine = pair[0]). Match that native location convention exactly.
            start = len(line[:line.index(MODERN)].encode("utf-8")) + 1 + int(line_number > 1)
            end = start + len(MODERN.encode("utf-8")) - 1
            self.assertTrue(any(item["file"] == relative and item["line"] == line_number
                                and item["start"] <= start and item["end"] >= end for item in findings),
                            f"finding must cover modern candidate columns in {relative}:{line_number}: "
                            f"{safe_locations(findings)}")
        for relative in encoded_files:
            self.assertTrue(any(item["file"] == relative and item["decoded"] for item in findings),
                            f"native default decoding must preserve the modern candidate in {relative}")

    def test_escaped_sourcegraph_keywords_still_activate_the_native_class(self):
        candidate = f"sourcegraph {IDENTIFIER}"
        text = json.dumps({"observation": candidate}, indent=2) + "\n"
        # The upstream detector reports decoded-pass matches only when their span overlaps an encoded segment.
        # Encode the keyword and candidate together, rather than expecting an unrelated decoded keyword alone
        # to retroactively report an entirely plaintext candidate elsewhere in the file.
        files = {f"catalogs/sota-convergence/manifest-20261009-{label}-keyword.json":
                 text.replace(candidate, encode(candidate))
                 for label, encode in (("unicode", unicode_escape), ("percent", percent_escape))}
        findings = [item for item in self.scan(files) if item["rule"] == RULE]
        self.assertEqual({item["file"] for item in findings}, set(files),
                         f"escaped keywords must retain class activation: {safe_locations(findings)}")
        for relative in files:
            self.assertTrue(any(item["file"] == relative and item["decoded"] for item in findings),
                            f"native default decoding must activate the class in {relative}")


if __name__ == "__main__":
    unittest.main()
