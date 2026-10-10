"""Native scanner coverage for large synthetic targets using the current CI options.

Only throwaway fixtures are scanned; git scans use a two-commit PR-shaped range.
The canary is fabricated, all scanner reports are redacted, and GNU time measures
the Linux subprocess without imposing a resource cap.
"""

import json
import io
import os
import platform
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

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
        if not line.lstrip().startswith(('"$RUNNER_TEMP/', '/usr/bin/time ')):
            continue
        words = shlex.split(line)
        binary = next((i for i, word in enumerate(words) if word in (
            "$RUNNER_TEMP/gitleaks/gitleaks", "$RUNNER_TEMP/betterleaks/betterleaks")), None)
        if binary is not None and words[binary + 1:binary + 3] == [mode, "."]:
            end = words.index("||") if "||" in words else len(words)
            return words[binary + 3:end]
    raise AssertionError(f"No native {job} {mode} command in the workflow")


def gnu_time_on_linux():
    # GNU time's --version contract; BSD time does not support -f/-o.
    timer = Path("/usr/bin/time")
    if platform.system() != "Linux" or not timer.is_file():
        return None
    probe = subprocess.run([str(timer), "--version"], capture_output=True, text=True)
    return str(timer) if probe.returncode == 0 and "(GNU Time)" in probe.stdout else None


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
        timer = gnu_time_on_linux()
        command = ([timer, "-f", "%e %M", "-o", str(metrics_file)] if timer else []) + args
        result = subprocess.run(command, cwd=target, env=env, capture_output=True, text=True)
        if result.returncode not in (0, 1):
            raise AssertionError(f"Scanner error, rc={result.returncode}; raw output withheld")
        findings = json.loads(report.read_text()) or []
        located = [f for f in findings if f.get("File") == path]
        metrics = {"scanner": Path(binary).name, "mode": mode, "size_bytes": size,
                   "findings": len(located), "rc": result.returncode, "host": platform.system(),
                   "measurement": "gnu_time" if timer else "unmeasured"}
        if timer:
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


@unittest.skipUnless(GITLEAKS, "native gitleaks is needed for timer fallback controls")
class ScannerTimerTests(unittest.TestCase):
    def exercise(self, host, gnu):
        native_run = subprocess.run
        native_file = Path.is_file
        scanner_calls = []
        timer_calls = []
        console = io.StringIO()

        def is_file(path):
            return True if str(path) == "/usr/bin/time" else native_file(path)

        def run(command, *args, **kwargs):
            if command[0] == "/usr/bin/time":
                timer_calls.append(command)
                if "--version" in command:
                    return subprocess.CompletedProcess(command, 0 if gnu else 1,
                        stdout="time (GNU Time) 1.9" if gnu else "", stderr="")
                if not gnu:
                    # BSD time refuses these options before launching the scanner.
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="unsupported option")
            if command[0] == GITLEAKS or GITLEAKS in command:
                scanner_calls.append(command)
            return native_run(command, *args, **kwargs)

        with patch("platform.system", return_value=host), patch.object(Path, "is_file", is_file), \
                patch.object(subprocess, "run", run), redirect_stdout(console):
            try:
                findings = scan_fixture(GITLEAKS, "secret-scan", "dir", 256)
            except (AssertionError, FileNotFoundError):
                self.fail("Existing non-GNU timer prevented the scanner's detection")
        self.assertTrue(findings)
        self.assertEqual(len(scanner_calls), 1)
        metrics = json.loads(console.getvalue().split("large-file-scan-metrics: ", 1)[1])
        self.assertEqual(metrics["host"], host)
        return metrics, timer_calls

    def test_darwin_existing_bsd_time_does_not_prevent_scanner_detection(self):
        metrics, calls = self.exercise("Darwin", False)
        self.assertFalse(calls)
        self.assertNotIn("elapsed_seconds", metrics)
        self.assertNotIn("peak_rss_kib", metrics)

    def test_linux_existing_non_gnu_timer_falls_back_to_direct_detection(self):
        metrics, calls = self.exercise("Linux", False)
        self.assertEqual(len(calls), 1)
        self.assertIn("--version", calls[0])
        self.assertNotIn("elapsed_seconds", metrics)
        self.assertNotIn("peak_rss_kib", metrics)

    @unittest.skipUnless(platform.system() == "Linux" and Path("/usr/bin/time").is_file(),
                         "native GNU time needed on Linux")
    def test_linux_confirmed_gnu_time_retains_measured_detection(self):
        metrics, calls = self.exercise("Linux", True)
        self.assertEqual(len(calls), 2)
        self.assertIn("--version", calls[0])
        self.assertGreaterEqual(metrics["elapsed_seconds"], 0)
        self.assertGreater(metrics["peak_rss_kib"], 0)


class TimedWorkflowArgumentsTests(unittest.TestCase):
    def test_verified_gitleaks_job_runs_timer_portability_regressions(self):
        native_job = jobs(WORKFLOW.read_text())["secret-scan"]
        self.assertIn("tests.test_secret_scan_size.ScannerTimerTests", native_job,
                      "Timer portability controls must run with CI's verified gitleaks")

    def test_timing_prefix_keeps_all_four_production_scanner_options(self):
        source = WORKFLOW.read_text()
        timed = re.sub(r'(?m)^(\s*)("\$RUNNER_TEMP/(?:gitleaks/gitleaks|betterleaks/betterleaks)" (?:git|dir) \.)',
                       r'\1/usr/bin/time --quiet --format "%e %M" --output "$RUNNER_TEMP/time.txt" \2', source)
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / "validate.yml"
            file.write_text(timed)
            with patch(__name__ + ".WORKFLOW", file):
                for job in ("secret-scan", "secret-scan-betterleaks"):
                    for mode in ("git", "dir"):
                        with self.subTest(job=job, mode=mode):
                            try:
                                args = workflow_scanner_arguments(job, mode)
                            except AssertionError:
                                self.fail("Canary parser lost production scanner options behind GNU time")
                            self.assertEqual(args[:2], ["--config", ".gitleaks.toml"])
                            self.assertIn("--redact", args)
                            if mode == "git":
                                self.assertIn("--log-opts=HEAD", args)
                            if job == "secret-scan-betterleaks":
                                self.assertIn("--exit-code", args)
                                self.assertIn(".gitleaksignore", args)


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
