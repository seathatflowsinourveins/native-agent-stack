"""Synthetic integration controls for the independent frozen OSV report.

These execute the checked-in shell with recording doubles and exercise its
summary parser. They are local integration evidence, never native OSV acceptance
or evidence that the archived application cannot be consumed.
"""

from datetime import datetime, timedelta
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

from tests.test_osv_lockfile_coverage import FROZEN_CONFIG, FROZEN_LOCKS, INVENTORY, ROOT


WORKFLOW = ROOT / ".github/workflows/frozen-evidence-risk.yml"
TRUSTED_MAIN_GUARD = (
    "${{ !cancelled() && github.event_name != 'pull_request' && github.ref == 'refs/heads/main' && "
    "(github.event_name == 'push' || github.event_name == 'schedule' || "
    "github.event_name == 'workflow_dispatch') }}"
)


def step_script(name):
    text = WORKFLOW.read_text(encoding="utf-8")
    section = text.split("      - name: " + name, 1)[1]
    return textwrap.dedent(section.split("        run: |\n", 1)[1].split("      - name:", 1)[0])


def fixture_environment(scratch):
    runner = scratch / "runner"
    report = runner / "frozen-evidence-risk"
    report.mkdir(parents=True)
    summary = scratch / "summary.md"
    return dict(os.environ, RUNNER_TEMP=str(runner), GITHUB_RUN_ID="synthetic-run",
                GITHUB_RUN_ATTEMPT="1", GITHUB_SHA="synthetic-head", GITHUB_EVENT_NAME="pull_request",
                GITHUB_STEP_SUMMARY=str(summary), REPORT_OWNER="github-ci-finalize",
                ATTEMPT_OUTCOME="success", PREFLIGHT_OUTCOME="success",
                INSTALL_OUTCOME="success", SCAN_OUTCOME="success")


class FrozenReportWorkflowTests(unittest.TestCase):
    """Configuration/permission checks and native-shell recording doubles."""

    def run_scan(self, inventory=None, json_code=0, sarif_code=0):
        inventory = json.loads(INVENTORY.read_text(encoding="utf-8")) if inventory is None else inventory
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            environment = fixture_environment(scratch)
            config_dir = scratch / ".github"
            config_dir.mkdir()
            (config_dir / "osv-scanner-lockfiles.json").write_text(json.dumps(inventory), encoding="utf-8")
            tool = scratch / "runner/osv-scanner/osv-scanner"
            tool.parent.mkdir()
            tool.write_text("#!" + sys.executable + "\n" + textwrap.dedent("""\
                from pathlib import Path
                import json
                import os
                import sys

                args = sys.argv[1:]
                mode = args[args.index("--format") + 1]
                with Path(os.environ["SYNTHETIC_CALLS"]).open("a", encoding="utf-8") as output:
                    output.write(json.dumps(args) + "\\n")
                code = int(os.environ["SYNTHETIC_" + mode.upper() + "_CODE"])
                if mode == "json":
                    data = {"synthetic_fixture": True, "results": [
                        {"packages": [{"vulnerabilities": [{"id": "GHSA-synthetic"}]}]}
                    ] if code == 1 else []}
                else:
                    data = {"synthetic_fixture": True, "version": "2.1.0", "runs": [
                        {"tool": {"driver": {"name": "synthetic"}}, "results": [
                            {"ruleId": "GHSA-synthetic"}
                        ] if code == 1 else []}
                    ]}
                Path(args[args.index("--output-file") + 1]).write_text(json.dumps(data), encoding="utf-8")
                print("synthetic " + mode + " scanner exit " + str(code))
                raise SystemExit(code)
                """), encoding="utf-8")
            tool.chmod(0o700)
            environment.update(SYNTHETIC_CALLS=str(scratch / "calls.jsonl"),
                               SYNTHETIC_JSON_CODE=str(json_code), SYNTHETIC_SARIF_CODE=str(sarif_code))
            result = subprocess.run(["bash", "-c", step_script("Scan only frozen evidence without suppression")],
                                    cwd=scratch, env=environment, text=True, capture_output=True, check=False)
            calls_path = scratch / "calls.jsonl"
            calls = [json.loads(line) for line in calls_path.read_text().splitlines()] if calls_path.exists() else []
            output_dir = scratch / "runner/frozen-evidence-risk"
            artifacts = {path.name: path.read_text() for path in output_dir.iterdir()}
        return result, calls, artifacts

    def test_frozen_report_is_independent_and_scan_has_only_read_permission(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        scan, remainder = text.split("  frozen-osv-sarif-upload:", 1)
        upload = remainder.split("  frozen-risk-review:", 1)[0]
        self.assertIn("  frozen-evidence-risk:", scan)
        self.assertNotIn("  osv-scanner:", text)
        self.assertIn("      contents: read", scan)
        self.assertNotIn("security-events: write", scan)
        self.assertNotIn("issues: write", scan)
        self.assertNotIn("continue-on-error", text)
        self.assertIn("if: " + TRUSTED_MAIN_GUARD, upload)
        self.assertIn("      security-events: write", upload)
        self.assertNotIn("        run:", upload)
        self.assertIn("category: osv-scanner-frozen-macos", upload)
        self.assertIn('if: ${{ always() }}', text.split("      - name: Retain the frozen native reports", 1)[1])
        self.assertIn("if-no-files-found: error", text)

    def test_exact_frozen_group_and_parser_flags_reach_both_native_formats(self):
        result, calls, artifacts = self.run_scan()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 2)
        inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
        expected = ["--lockfile=" + entry.get("parser", "") + ":" + entry["path"]
                    for entry in inventory["lockfiles"] if entry.get("config") == FROZEN_CONFIG]
        self.assertTrue(expected)
        ordinary = {entry["path"] for entry in inventory["lockfiles"] if "config" not in entry}
        for args in calls:
            self.assertEqual(args[:2], ["scan", "source"])
            self.assertEqual(args[args.index("--config") + 1], FROZEN_CONFIG)
            self.assertIn("--no-resolve", args)
            self.assertEqual([arg for arg in args if arg.startswith("--lockfile=")], expected)
            self.assertFalse(any(arg.split(":", 1)[-1] in ordinary
                                 for arg in args if arg.startswith("--lockfile=")))
        self.assertEqual({args[args.index("--format") + 1] for args in calls}, {"json", "sarif"})
        self.assertIn("osv-scanner-frozen-macos.json", artifacts)
        self.assertIn("osv-scanner-frozen-macos.sarif", artifacts)

    def test_native_findings_errors_and_both_logs_are_retained(self):
        for json_code, sarif_code in ((0, 0), (1, 0), (0, 1), (1, 1),
                                      (2, 0), (0, 7), (1, 2), (2, 1),
                                      (128, 1), (1, 129)):
            with self.subTest(json=json_code, sarif=sarif_code):
                result, calls, artifacts = self.run_scan(json_code=json_code, sarif_code=sarif_code)
                # Reported findings do not make the advisory job fail; native
                # operational errors still do, including mixed-format outcomes.
                expected = 0 if max(json_code, sarif_code) <= 1 else max(json_code, sarif_code)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(len(calls), 2)
                self.assertEqual(artifacts["json.exit_code"].strip(), str(json_code))
                self.assertEqual(artifacts["sarif.exit_code"].strip(), str(sarif_code))
                self.assertIn("synthetic json scanner", artifacts["json.log"])
                self.assertIn("synthetic sarif scanner", artifacts["sarif.log"])

    def test_empty_duplicate_unknown_and_wrong_frozen_assignments_never_scan(self):
        original = json.loads(INVENTORY.read_text(encoding="utf-8"))
        for mutation in ("empty", "duplicate", "unknown", "wrong"):
            with self.subTest(mutation=mutation):
                inventory = json.loads(json.dumps(original))
                entries = inventory["lockfiles"]
                frozen = next(entry for entry in entries if entry.get("config") == FROZEN_CONFIG)
                if mutation == "empty":
                    inventory["lockfiles"] = [entry for entry in entries if entry is not frozen]
                elif mutation == "duplicate":
                    entries.append(dict(frozen))
                elif mutation == "unknown":
                    entries[0]["config"] = ".github/unsupported-report.toml"
                else:
                    frozen["path"] = "synthetic-live-project/pnpm-lock.yaml"
                result, calls, artifacts = self.run_scan(inventory=inventory)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])
                self.assertNotIn("osv-scanner-frozen-macos.json", artifacts)


class FrozenReportSummaryTests(unittest.TestCase):
    """Exercise the actual bootstrap/summary shell; missing execution is not zero findings."""

    def run_summary(self, json_code=0, sarif_code=0, missing=None, malformed=None,
                    preflight="success", missing_record=False):
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            environment = fixture_environment(scratch)
            environment["PREFLIGHT_OUTCOME"] = preflight
            bootstrap = subprocess.run(["bash", "-c", step_script("Record the frozen report attempt")],
                                       cwd=scratch, env=environment, text=True, capture_output=True, check=False)
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)
            report_dir = scratch / "runner/frozen-evidence-risk"
            report_path = report_dir / "report.json"
            initial = json.loads(report_path.read_text())
            if preflight == "success":
                initial["inputs"] = [{"path": next(iter(FROZEN_LOCKS)), "synthetic_fixture": True}]
                initial["eligibility"] = "validated"
                report_path.write_text(json.dumps(initial), encoding="utf-8")
            if missing_record:
                # Separate the original native clock from recovery's current clock without sleeping.
                started = datetime.fromisoformat(initial["report_attempt_started_at"].replace("Z", "+00:00"))
                expected_started = (started - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
                (report_dir / "report_attempt_started_at").write_text(expected_started, encoding="utf-8")
                report_path.unlink()
            for mode, code, name, data in (
                    ("json", json_code, "osv-scanner-frozen-macos.json", {"results": []}),
                    ("sarif", sarif_code, "osv-scanner-frozen-macos.sarif", {"runs": []})):
                if code is not None:
                    (report_dir / (mode + ".exit_code")).write_text(str(code), encoding="utf-8")
                if mode != missing:
                    (report_dir / name).write_text("{" if mode == malformed else json.dumps(data), encoding="utf-8")
            result = subprocess.run(["bash", "-c", step_script("Summarize native report and unavailable evidence")],
                                    cwd=scratch, env=environment, text=True, capture_output=True, check=False)
            report = json.loads(report_path.read_text())
            if missing_record:
                report["_synthetic_expected_started_at"] = expected_started
            summary = (scratch / "summary.md").read_text()
        return result, report, summary

    def test_incomplete_bootstrap_recovers_the_first_attempt_clock(self):
        result, report, _ = self.run_summary(missing_record=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(report["status"], "unknown")
        self.assertEqual(report["report_attempt_started_at"], report["_synthetic_expected_started_at"])
        started = datetime.fromisoformat(report["report_attempt_started_at"].replace("Z", "+00:00"))
        due = datetime.fromisoformat(report["review_due"].replace("Z", "+00:00"))
        self.assertEqual(due - started, timedelta(hours=24))
        self.assertEqual(report["owner"], "github-ci-finalize")

    def test_actual_attempt_clock_assigns_owner_and_review_due_in_twenty_four_hours(self):
        result, report, summary = self.run_summary()
        self.assertEqual(result.returncode, 0, result.stderr)
        started = datetime.fromisoformat(report["report_attempt_started_at"].replace("Z", "+00:00"))
        due = datetime.fromisoformat(report["review_due"].replace("Z", "+00:00"))
        self.assertEqual(due - started, timedelta(hours=24))
        self.assertEqual(report["owner"], "github-ci-finalize")
        self.assertEqual(report["status"], "clear")
        self.assertIn("github-ci-finalize", summary)

    def test_known_native_errors_stay_distinct_from_missing_execution(self):
        for code, expected in ((1, "findings"), (2, "error"), (127, "error")):
            with self.subTest(code=code):
                result, report, _ = self.run_summary(json_code=code, missing="json" if code > 1 else None)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(report["status"], expected)
                self.assertEqual(report["native_exit_codes"]["json"], code)
                if code > 1:
                    self.assertEqual(report["finding_state"], "unknown")
        result, report, _ = self.run_summary(json_code=None, sarif_code=None, missing="json", preflight="failure")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(report["status"], "unknown")
        self.assertIsNone(report["inputs"])
        self.assertIsNone(report["native_exit_codes"]["json"])
        self.assertEqual(report["owner"], "github-ci-finalize")
        self.assertIn("review_due", report)

    def test_missing_or_malformed_output_cannot_become_a_clean_result(self):
        for kind in ("missing", "malformed"):
            with self.subTest(kind=kind):
                result, report, _ = self.run_summary(**{kind: "json"})
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(report["status"], "unknown")
                self.assertEqual(report["finding_state"], "unknown")
                self.assertTrue(report["errors"])


class FrozenReportIssueTests(unittest.TestCase):
    """Native gh glue with a recording double; no GitHub issue or credential is created here."""

    def run_issue(self, numbers=(), missing_report=False, listing_error=0, interval_seconds=None):
        if sys.platform == "darwin":
            self.skipTest("Ubuntu issue-writer integration parses timestamps with GNU date --date; BSD date lacks it")
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            environment = fixture_environment(scratch)
            if not missing_report:
                bootstrap = subprocess.run(["bash", "-c", step_script("Record the frozen report attempt")],
                                           cwd=scratch, env=environment, text=True, capture_output=True, check=False)
                self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)
                report_path = scratch / "runner/frozen-evidence-risk/report.json"
                report = json.loads(report_path.read_text())
                report["errors"] = ["synthetic raw diagnostic; must never be copied into the issue"]
                report["raw_finding"] = "synthetic finding body; must never be copied into the issue"
                if interval_seconds is not None:
                    started = datetime.fromisoformat(report["report_attempt_started_at"].replace("Z", "+00:00"))
                    report["review_due"] = (started + timedelta(seconds=interval_seconds)).isoformat().replace("+00:00", "Z")
                report_path.write_text(json.dumps(report), encoding="utf-8")
            binaries = scratch / "bin"
            binaries.mkdir()
            gh = binaries / "gh"
            gh.write_text("#!" + sys.executable + "\n" + textwrap.dedent("""\
                from pathlib import Path
                import json
                import os
                import sys

                args = sys.argv[1:]
                with Path(os.environ["SYNTHETIC_GH_CALLS"]).open("a", encoding="utf-8") as output:
                    output.write(json.dumps(args) + "\\n")
                if args[:2] == ["issue", "list"]:
                    code = int(os.environ["SYNTHETIC_LIST_ERROR"])
                    if code:
                        raise SystemExit(code)
                    for number in sorted(json.loads(os.environ["SYNTHETIC_ISSUES"])):
                        print(number)
                """), encoding="utf-8")
            gh.chmod(0o700)
            environment.update(PATH=str(binaries) + os.pathsep + os.environ["PATH"],
                               GH_TOKEN="synthetic-not-a-real-token", GH_REPO="synthetic/repository",
                               RUN_URL="https://github.invalid/synthetic/run",
                               ALERTS_URL="https://github.invalid/synthetic/security/code-scanning?query=is%3Aopen",
                               ASSIGNEE="seathatflowsinourveins", REVIEWER="command center",
                               SYNTHETIC_GH_CALLS=str(scratch / "calls.jsonl"),
                               SYNTHETIC_ISSUES=json.dumps(numbers), SYNTHETIC_LIST_ERROR=str(listing_error))
            result = subprocess.run(["bash", "-c", step_script("Create or edit the single frozen review issue")],
                                    cwd=scratch, env=environment, text=True, capture_output=True, check=False)
            calls_path = scratch / "calls.jsonl"
            calls = [json.loads(line) for line in calls_path.read_text().splitlines()] if calls_path.exists() else []
            body_path = scratch / "runner/frozen-review-issue-body.md"
            body = body_path.read_text() if body_path.exists() else ""
        return result, calls, body

    def test_only_explicit_main_events_reach_the_scoped_writer_and_sarif_upload(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for job in ("frozen-osv-sarif-upload", "frozen-risk-review"):
            section = text.split("  " + job + ":\n", 1)[1]
            guard = section.split("    if: ", 1)[1].splitlines()[0]
            self.assertEqual(guard, TRUSTED_MAIN_GUARD)
            # A bounded fixture evaluates only the documented boolean/string atoms in this exact guard.
            # It is a local condition control, not hosted GitHub event acceptance.
            for event, ref, cancelled, expected in (
                    ("push", "refs/heads/main", False, True),
                    ("schedule", "refs/heads/main", False, True),
                    ("workflow_dispatch", "refs/heads/main", False, True),
                    ("workflow_dispatch", "refs/heads/off-main", False, False),
                    ("workflow_dispatch", "refs/tags/main", False, False),
                    ("pull_request", "refs/heads/main", False, False),
                    ("push", "refs/heads/off-main", False, False),
                    ("repository_dispatch", "refs/heads/main", False, False),
                    ("schedule", "refs/heads/main", True, False)):
                with self.subTest(job=job, event=event, ref=ref, cancelled=cancelled):
                    expression = guard.removeprefix("${{").removesuffix("}}").strip()
                    expression = expression.replace("!cancelled()", repr(not cancelled))
                    expression = expression.replace("github.ref", repr(ref)).replace("github.event_name", repr(event))
                    expression = expression.replace("&&", "and").replace("||", "or")
                    self.assertEqual(eval(expression, {"__builtins__": {}}, {}), expected)
        writer = text.split("  frozen-risk-review:\n", 1)[1]
        self.assertIn("      issues: write", writer)
        self.assertNotIn("contents:", writer)
        self.assertNotIn("security-events:", writer)
        self.assertNotIn("actions/checkout@", writer)
        self.assertNotIn("python3", writer)
        self.assertIn("GH_TOKEN: ${{ github.token }}", writer)
        self.assertIn("group: frozen-risk-review-${{ github.repository }}", writer)
        self.assertIn("cancel-in-progress: false", writer)

    def test_create_assigns_owner_and_links_alerts_without_copying_payloads(self):
        result, calls, body = self.run_issue()
        self.assertEqual(result.returncode, 0, result.stderr)
        create = [args for args in calls if args[:2] == ["issue", "create"]]
        self.assertEqual(len(create), 1)
        self.assertEqual(create[0][create[0].index("--assignee") + 1], "seathatflowsinourveins")
        self.assertIn("Reviewer: command center", body)
        self.assertIn("Review due:", body)
        self.assertIn("osv-scanner-frozen-macos", body)
        self.assertIn("?query=is%3Aopen", body)
        self.assertNotIn("query=category", body)
        self.assertNotIn("category%3A", body)
        self.assertNotIn("synthetic raw diagnostic", body)
        self.assertNotIn("synthetic finding body", body)
        self.assertNotIn("synthetic-not-a-real-token", body + json.dumps(calls))

    def test_existing_issue_is_edited_and_duplicate_open_issues_are_closed(self):
        result, calls, _ = self.run_issue(numbers=(9, 3))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([args[2] for args in calls if args[:2] == ["issue", "edit"]], ["3"])
        self.assertEqual([args[2] for args in calls if args[:2] == ["issue", "close"]], ["9"])
        self.assertEqual([args for args in calls if args[:2] == ["issue", "create"]], [])

    def test_missing_report_or_failed_listing_never_creates_an_issue(self):
        result, calls, _ = self.run_issue(missing_report=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])
        result, calls, _ = self.run_issue(listing_error=7)
        self.assertEqual(result.returncode, 7)
        self.assertEqual([args for args in calls if args[:2] in (["issue", "create"], ["issue", "edit"])], [])

    def test_nonpositive_or_late_review_interval_never_reaches_gh(self):
        for interval in (0, -1, 86401):
            with self.subTest(interval=interval):
                result, calls, _ = self.run_issue(interval_seconds=interval)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])
