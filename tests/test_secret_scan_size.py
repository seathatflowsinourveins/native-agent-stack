"""Native scanner coverage for large synthetic targets using the current CI options.

Only throwaway fixtures are scanned; git scans use a two-commit PR-shaped range.
The canary is fabricated, all scanner reports are redacted, and GNU time measures
the Linux subprocess without imposing a resource cap.
"""

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

from tests.test_workflow_hardening import jobs
from tests.test_gitleaks_config import GH_PAT_SHAPED_VALUE


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/validate.yml"
CANARY = GH_PAT_SHAPED_VALUE
SIZES = (2_000_001, 3_000_000)
GITLEAKS = shutil.which("gitleaks")
BETTERLEAKS = os.environ.get("BETTERLEAKS_TEST_BINARY")


def workflow_scanner_arguments(job, mode):
    # Existing stdlib job parser: the native scanner jobs install no YAML dependency.
    source = re.sub(r"\\\n\s*", " ", jobs(WORKFLOW.read_text())[job])
    for line in source.splitlines():
        if not line.lstrip().startswith('"$RUNNER_TEMP/'):
            continue
        words = shlex.split(line)
        if len(words) > 2 and words[1:3] == [mode, "."]:
            end = words.index("||") if "||" in words else len(words)
            return words[3:end]
    raise AssertionError(f"No native {job} {mode} command in the workflow")


def scan_fixture(binary, job, mode, size, path="manifests/large-shape.json"):
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        target = base / "tree"
        target.mkdir()
        raw = ('github_pat_fixture = "' + CANARY + '"\n').encode()
        raw += (b"padding\n" * ((size - len(raw)) // 8 + 1))[:size - len(raw)]
        env = {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(base),
               "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
               "LANG": "C.UTF-8"}
        range_arg = None
        if mode == "git":
            for args in (["init", "-q"], ["config", "user.name", "Fixture"],
                         ["config", "user.email", "fixture@example.invalid"],
                         ["commit", "--allow-empty", "-qm", "fixture base"]):
                subprocess.run(["git", *args], cwd=target, env=env, check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            range_arg = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=target, env=env,
                                                text=True).strip() + "..HEAD"
        file = target / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(raw)
        if mode == "git":
            for args in (["add", "--", path], ["commit", "-qm", "fixture target"]):
                subprocess.run(["git", *args], cwd=target, env=env, check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        report = base / "report.json"
        metrics_file = base / "metrics.txt"
        words = workflow_scanner_arguments(job, mode)
        args = [binary, mode, "."]
        for word in words:
            if word == ".gitleaks.toml":
                word = str(ROOT / ".gitleaks.toml")
            elif word == ".gitleaksignore":
                word = str(ROOT / ".gitleaksignore")
            elif word.startswith("--log-opts="):
                word = "--log-opts=" + range_arg
            elif word in ("$report", "$RUNNER_TEMP/gitleaks/gitleaks.json"):
                word = str(report)
            args.append(word)
        if "--report-path" not in args:
            args.extend(["--report-format", "json", "--report-path", str(report)])
        measured = Path("/usr/bin/time").is_file()
        command = (["/usr/bin/time", "-f", "%e %M", "-o", str(metrics_file)] if measured else []) + args
        result = subprocess.run(command, cwd=target, env=env, capture_output=True, text=True)
        if result.returncode not in (0, 1):
            raise AssertionError(f"Scanner error, rc={result.returncode}; raw output withheld")
        findings = json.loads(report.read_text()) or []
        located = [f for f in findings if f.get("File") == path]
        metrics = {"scanner": Path(binary).name, "mode": mode, "size_bytes": size,
                   "findings": len(located), "rc": result.returncode, "host": "Linux" if measured else "unmeasured"}
        if measured:
            seconds, rss = metrics_file.read_text().splitlines()[-1].split()
            metrics.update(elapsed_seconds=float(seconds), peak_rss_kib=int(rss))
        print("large-file-scan-metrics: " + json.dumps(metrics, sort_keys=True))
        return located


class ScannerMechanismSourcesTests(unittest.TestCase):
    def test_decision_cites_betterleaks_native_path_prefilter_and_source_callback(self):
        # betterleaks v1.8.1: translation96-108 -> SkipFunc436-451 -> source callbacks.
        decision = (ROOT / "docs/decisions/2026-10-10-secret-scan-large-targets.md").read_text()
        prefix = "https://github.com/betterleaks/betterleaks/blob/5eab48332cc48565864514e3bc6de89df091a7c4/"
        for locator in ("config/translate_filters.go#L96", "detect/detect.go#L436",
                        "sources/common.go#L55", "sources/files.go#L117"):
            with self.subTest(locator=locator):
                self.assertTrue(prefix + locator in decision, f"Missing pinned betterleaks mechanism: {locator}")
        self.assertTrue("prefilter" in decision, "Decision must identify the native prefilter")
        self.assertFalse("Both implementations use" in decision, "The two scanners have different path mechanisms")

    def test_decision_pins_the_gitleaks_path_allowlist_definition(self):
        # gitleaks v8.30.1 defines PathAllowed at136, after the comment at135.
        decision = (ROOT / "docs/decisions/2026-10-10-secret-scan-large-targets.md").read_text()
        self.assertTrue("https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/config/allowlist.go#L136" in decision,
                        "Gitleaks PathAllowed starts at136;135 is its comment")


@unittest.skipUnless(GITLEAKS, "gitleaks is installed in its native secret-scan job")
class GitleaksLargeFileTests(unittest.TestCase):
    def test_git_and_dir_find_canaries_above_both_old_skip_boundaries(self):
        for mode in ("git", "dir"):
            for size in SIZES:
                with self.subTest(mode=mode, size=size):
                    self.assertTrue(scan_fixture(GITLEAKS, "secret-scan", mode, size),
                                    "Native workflow arguments silently skip this large canary target")

    def test_only_the_exact_generated_explorer_path_is_excluded(self):
        for mode in ("git", "dir"):
            with self.subTest(mode=mode):
                self.assertEqual(scan_fixture(GITLEAKS, "secret-scan", mode, 256,
                                              path="docs/ecosystem/index.html"), [])
                self.assertTrue(scan_fixture(GITLEAKS, "secret-scan", mode, 256,
                                             path="docs/ecosystem/index.html.extra"))
                self.assertTrue(scan_fixture(GITLEAKS, "secret-scan", mode, 256,
                                             path="other/docs/ecosystem/index.html"))


@unittest.skipUnless(BETTERLEAKS, "verified CI betterleaks binary is supplied explicitly")
class BetterleaksLargeFileTests(unittest.TestCase):
    def test_dir_finds_canaries_above_both_old_skip_boundaries(self):
        self.assertEqual(subprocess.check_output([BETTERLEAKS, "version"], text=True).strip(), "1.8.1")
        for size in SIZES:
            with self.subTest(size=size):
                self.assertTrue(scan_fixture(BETTERLEAKS, "secret-scan-betterleaks", "dir", size),
                                "Native betterleaks workflow arguments silently skip this large canary target")

    def test_only_the_exact_generated_explorer_path_is_excluded(self):
        self.assertEqual(scan_fixture(BETTERLEAKS, "secret-scan-betterleaks", "dir", 256,
                                      path="docs/ecosystem/index.html"), [])
        self.assertTrue(scan_fixture(BETTERLEAKS, "secret-scan-betterleaks", "dir", 256,
                                     path="docs/ecosystem/index.html.extra"))


if __name__ == "__main__":
    unittest.main()
