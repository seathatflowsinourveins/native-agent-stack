"""Offline tests for tools/sota-convergence/practice_references.py and its weekly workflow.

No network. Classification runs on fixture observations shaped like the checker's own
observe() output; the command line replays them with --observations; observe() itself runs
against a fake ``gh`` (subprocess.run patched, as tests/test_sota_convergence.py does for
github_freshness.py). The stale boundary follows ossf/scorecard@8788fc28
probes/hasRecentCommits/impl.go:52-57: a commit counts only when it is after now - 90 days.
"""
import copy
import importlib.util
import io
import json
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import tests  # noqa: F401 - hermetic git configuration for the whole suite

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "sota-convergence" / "practice_references.py"
CATALOG = ROOT / "catalogs" / "foundation" / "practice-references.json"
WORKFLOW = ROOT / ".github" / "workflows" / "practice-references-freshness.yml"
REFERENCE_WORKFLOW = ROOT / ".github" / "workflows" / "catalog-freshness.yml"

_spec = importlib.util.spec_from_file_location("practice_references", TOOL)
practice_references = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(practice_references)

NOW = datetime(2026, 9, 28, 3, 0, tzinfo=timezone.utc)
PIN = "8ca22dba9a94f28898bbce59f2537ff4d87c747d"
HEAD = "0f1e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c"
RECORD = "docs/decisions/2026-09-28-community-sweep.md"
DIMENSION = "harness-and-token-practice"


def iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def entry(repository, pin=PIN, pin_date="2026-09-25", role="community"):
    return {"repository": repository, "role": role, "pin": pin, "pin_date": pin_date, "stars_at_check": 10,
            "used_for": [{"dimension": DIMENSION, "use": "fixture"}], "record": RECORD}


def observed(full_name, head_sha=PIN, head_age=timedelta(days=2), archived=False,
             comparison=("identical", 0, 0), pin_committed="2026-09-25T18:06:27Z"):
    """Shaped like practice_references.observe(): github_freshness.fetch_repository()'s keys
    plus the pin comparison."""
    observation = {"error": None, "full_name": full_name, "archived": archived, "default_branch": "main",
                   "head": {"sha": head_sha, "date": iso(NOW - head_age)}, "latest_release": None,
                   "partial_errors": None}
    if comparison is not None:
        status, ahead, behind = comparison
        observation["compare"] = {"status": status, "ahead_by": ahead, "behind_by": behind,
                                  "base_sha": PIN, "base_date": pin_committed}
    return observation


# One fixture per reported case, keyed by repository.
FIXTURES = {
    "example/fresh": observed("example/fresh"),
    "example/drifted": observed("example/drifted", head_sha=HEAD, comparison=("ahead", 7, 0)),
    "example/stale": observed("example/stale", head_age=timedelta(days=91)),
    "example/archived": observed("example/archived", head_age=timedelta(days=5), archived=True),
    "example/renamed": observed("example-org/renamed-repo"),
    "example/missing": {"error": "gh: Not Found (HTTP 404)"},
}


def catalog(repositories=tuple(FIXTURES)):
    return {
        "schema_version": 1, "kind": "practice_references", "checked_at": "2026-09-28",
        "scope": "fixture", "dimensions": [{"id": DIMENSION, "description": "fixture", "topics": ["t"]}],
        "references": [entry(repository) for repository in repositories],
    }


def row_for(repository):
    return practice_references.classify(entry(repository), FIXTURES[repository], NOW)


class ClassificationTests(unittest.TestCase):
    def test_fresh_pin_at_the_default_branch_head_has_no_flags(self):
        row = row_for("example/fresh")
        self.assertEqual((row["status"], row["flags"]), ("fresh", []))
        self.assertEqual((row["commits_since_pin"], row["head_sha"], row["stale"]), (0, PIN, False))
        self.assertEqual(row["days_since_head_commit"], 2)
        self.assertEqual(row["pin_date_observed"], "2026-09-25")

    def test_drifted_pin_reports_commits_since_the_pin_and_the_head_sha(self):
        row = row_for("example/drifted")
        self.assertEqual((row["status"], row["flags"]), ("drifted", ["drifted"]))
        self.assertEqual((row["commits_since_pin"], row["compare_status"], row["head_sha"]), (7, "ahead", HEAD))
        self.assertFalse(row["stale"])

    def test_no_default_branch_commit_in_90_days_is_stale(self):
        row = row_for("example/stale")
        self.assertEqual((row["status"], row["flags"]), ("stale", ["stale"]))
        self.assertEqual(row["stale_reason"], "no default-branch commit in the last 90 days")
        # hasRecentCommits counts a commit only when it is after now - 90 days.
        for age, stale in ((timedelta(days=89, hours=23), False), (timedelta(days=90), True),
                           (timedelta(days=91), True)):
            with self.subTest(age=age):
                result = practice_references.classify(
                    entry("example/boundary"), observed("example/boundary", head_age=age), NOW)
                self.assertIs(result["stale"], stale)
                self.assertEqual("stale" in result["flags"], stale)

    def test_archived_repository_is_stale_whatever_its_last_commit(self):
        row = row_for("example/archived")
        self.assertEqual((row["status"], row["flags"]), ("archived", ["archived", "stale"]))
        self.assertEqual((row["archived"], row["stale"], row["stale_reason"]), (True, True, "archived"))
        self.assertEqual(row["days_since_head_commit"], 5)

    def test_renamed_repository_reports_its_new_name(self):
        row = row_for("example/renamed")
        self.assertEqual((row["status"], row["flags"]), ("renamed", ["renamed"]))
        self.assertEqual(row["renamed_to"], "example-org/renamed-repo")
        same_name_other_case = practice_references.classify(
            entry("Example/Fresh"), observed("example/fresh"), NOW)
        self.assertNotIn("renamed", same_name_other_case["flags"])

    def test_missing_repository_is_reported_and_a_transient_failure_is_not_missing(self):
        row = row_for("example/missing")
        self.assertEqual((row["status"], row["flags"]), ("missing", ["missing"]))
        self.assertIn("404", row["error"])
        for error in ("gh: Server Error (HTTP 503)", "gh: API rate limit exceeded (HTTP 429)", "timed out"):
            with self.subTest(error=error):
                result = practice_references.classify(entry("example/x"), {"error": error}, NOW)
                self.assertEqual(result["flags"], ["fetch_error"])
        self.assertEqual(practice_references.classify(entry("example/x"), None, NOW)["flags"], ["fetch_error"])

    def test_pin_that_no_longer_resolves_is_not_a_transient_error(self):
        cases = {"gh: Not Found (HTTP 404)": "pin_unresolved",
                 "gh: No commit found for SHA: 8ca22dba (HTTP 422)": "pin_unresolved",
                 "gh: Server Error (HTTP 502)": "fetch_error"}
        for error, flag in cases.items():
            with self.subTest(error=error):
                observation = observed("example/pin", comparison=None)
                observation["compare_error"] = error
                result = practice_references.classify(entry("example/pin"), observation, NOW)
                self.assertEqual(result["flags"], [flag])
                self.assertIsNone(result["commits_since_pin"])

    def test_diverged_pin_and_a_pin_date_mismatch_are_reported(self):
        observation = observed("example/diverged", head_sha=HEAD, comparison=("diverged", 3, 2),
                               pin_committed="2026-09-26T04:19:37Z")
        row = practice_references.classify(entry("example/diverged"), observation, NOW)
        self.assertEqual(row["flags"], ["drifted", "pin_date_mismatch"])
        self.assertEqual((row["commits_since_pin"], row["pin_commits_not_on_head"]), (3, 2))
        self.assertEqual(row["pin_date_observed"], "2026-09-26")


class CatalogValidationTests(unittest.TestCase):
    def test_committed_catalog_is_well_formed(self):
        loaded, errors = practice_references.load_catalog(CATALOG)
        self.assertEqual(errors, [])
        references = loaded["references"]
        roles = [reference["role"] for reference in references]
        self.assertEqual((len(references), roles.count("community"), roles.count("primary")), (25, 22, 3))
        self.assertEqual({reference["repository"] for reference in references if reference["role"] == "primary"},
                         {"anthropics/claude-code", "anthropics/claude-code-action",
                          "anthropics/claude-agent-sdk-python"})
        self.assertEqual({reference["record"] for reference in references}, {RECORD})

    def test_fixture_catalog_is_well_formed(self):
        self.assertEqual(practice_references.validate_catalog(catalog()), [])

    def test_malformed_catalogs_are_rejected(self):
        def mutate(change):
            document = copy.deepcopy(catalog())
            change(document)
            return document

        cases = {
            "not an object": ([], "expected a JSON object"),
            "string schema_version": (mutate(lambda d: d.update(schema_version="1")), "schema_version"),
            "wrong kind": (mutate(lambda d: d.update(kind="other")), "catalog.kind"),
            "unknown top-level key": (mutate(lambda d: d.update(extra=1)), "unknown key extra"),
            "empty references": (mutate(lambda d: d.update(references=[])), "catalog.references"),
            "abbreviated pin": (mutate(lambda d: d["references"][0].update(pin=PIN[:12])), ".pin:"),
            "invalid pin_date": (mutate(lambda d: d["references"][0].update(pin_date="2026-02-30")), ".pin_date:"),
            "pin_date after checked_at": (mutate(lambda d: d["references"][0].update(pin_date="2026-09-29")),
                                          "later than"),
            "stars as a boolean": (mutate(lambda d: d["references"][0].update(stars_at_check=True)),
                                   ".stars_at_check:"),
            "undeclared dimension": (mutate(lambda d: d["references"][0]["used_for"][0].update(dimension="x")),
                                     "not declared"),
            "missing record": (mutate(lambda d: d["references"][0].pop("record")), "missing record"),
            "record outside docs/decisions": (mutate(lambda d: d["references"][0].update(record="notes.md")),
                                              ".record:"),
            "invalid role": (mutate(lambda d: d["references"][0].update(role="winner")), ".role:"),
            "unknown entry key": (mutate(lambda d: d["references"][0].update(stars=1)), "unknown key stars"),
            "duplicate repository": (mutate(lambda d: d["references"].append(entry("EXAMPLE/fresh"))),
                                     "duplicate of references[0]"),
            "invalid repository": (mutate(lambda d: d["references"][0].update(repository="example")),
                                   ".repository:"),
        }
        for name, (document, fragment) in cases.items():
            with self.subTest(case=name):
                errors = practice_references.validate_catalog(document)
                self.assertTrue(errors, "accepted a malformed catalog")
                self.assertTrue(any(fragment in error for error in errors), errors)

    def test_duplicate_json_keys_are_malformed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.json"
            text = json.dumps(catalog(), indent=2)
            path.write_text(text.replace('"kind": "practice_references",',
                                         '"kind": "practice_references",\n  "kind": "practice_references",'),
                            encoding="utf-8")
            loaded, errors = practice_references.load_catalog(path)
        self.assertIsNone(loaded)
        self.assertTrue(errors)


class CommandLineTests(unittest.TestCase):
    def run_main(self, directory, document, observations):
        catalog_path, observations_path = directory / "catalog.json", directory / "observations.json"
        catalog_path.write_text(json.dumps(document), encoding="utf-8")
        observations_path.write_text(json.dumps(observations), encoding="utf-8")
        out, markdown = directory / "report.json", directory / "report.md"
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as stderr:
            status = practice_references.main([
                "--catalog", str(catalog_path), "--observations", str(observations_path),
                "--now", iso(NOW), "--out", str(out), "--markdown", str(markdown)])
        return status, out, markdown, stderr.getvalue()

    def test_drift_stale_archived_renamed_and_missing_are_report_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            status, out, markdown, _ = self.run_main(Path(temporary), catalog(), FIXTURES)
            self.assertEqual(status, 0)
            report = json.loads(out.read_text(encoding="utf-8"))
            table = markdown.read_text(encoding="utf-8")
        self.assertEqual(report["summary"], {
            "references": 6, "fresh": 1, "missing": 1, "fetch_error": 0, "archived": 1, "stale": 2,
            "renamed": 1, "pin_unresolved": 0, "drifted": 1, "pin_date_mismatch": 0})
        self.assertEqual({row["repository"]: row["status"] for row in report["references"]}, {
            "example/archived": "archived", "example/drifted": "drifted", "example/fresh": "fresh",
            "example/missing": "missing", "example/renamed": "renamed", "example/stale": "stale"})
        self.assertEqual((report["observed_at"], report["stale_after_days"]), ("2026-09-28T03:00:00Z", 90))
        rows = [line for line in table.splitlines() if line.startswith("| [")]
        self.assertEqual(len(rows), 6)
        self.assertIn("| Repository | Role | Pin | Flags | Commits since pin |", table)
        self.assertIn(f"[7](https://github.com/example/drifted/compare/{PIN[:12]}...{HEAD[:12]})", table)

    def test_output_is_deterministic_and_records_no_host_path(self):
        outputs = []
        for order in (list(FIXTURES), list(reversed(FIXTURES))):
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                status, out, markdown, _ = self.run_main(
                    directory, catalog(tuple(order)), {name: FIXTURES[name] for name in order})
                self.assertEqual(status, 0)
                outputs.append((out.read_bytes(), markdown.read_bytes()))
                self.assertNotIn(temporary.encode(), outputs[-1][0] + outputs[-1][1])
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(json.loads(outputs[0][0])["catalog"], "catalog.json")

    def test_malformed_catalog_exits_non_zero_without_a_report(self):
        documents = {"schema-invalid": json.dumps({**catalog(), "schema_version": 2}), "not JSON": "{"}
        for name, text in documents.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                (directory / "catalog.json").write_text(text, encoding="utf-8")
                (directory / "observations.json").write_text("{}", encoding="utf-8")
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as stderr:
                    status = practice_references.main([
                        "--catalog", str(directory / "catalog.json"),
                        "--observations", str(directory / "observations.json"),
                        "--out", str(directory / "report.json")])
                self.assertEqual(status, 2)
                self.assertIn("malformed catalog", stderr.getvalue())
                self.assertFalse((directory / "report.json").exists())


class _FakeProc:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


class ObserveTests(unittest.TestCase):
    """observe() through github_freshness.fetch_repository() and gh_api() with a fake gh."""

    def fake_gh(self, answers, calls):
        def run(cmd, capture_output=True, text=True, timeout=60):
            path = cmd[2]
            calls.append(path)
            answer = answers.get(path)
            if answer is None:
                return _FakeProc(1, stderr="gh: Not Found (HTTP 404)")
            return _FakeProc(0, stdout=json.dumps(answer))
        return run

    def observe(self, repository, answers):
        calls = []
        with mock.patch("subprocess.run", side_effect=self.fake_gh(answers, calls)):
            observation = practice_references.observe(entry(repository))
        return observation, calls

    def test_observation_compares_the_pin_with_the_observed_head(self):
        answers = {
            "repos/example/tool": {"full_name": "example/tool", "archived": False, "default_branch": "trunk"},
            "repos/example/tool/tags?per_page=1": [],
            "repos/example/tool/commits/trunk": {"sha": HEAD, "commit": {"committer": {"date": iso(NOW)}}},
            f"repos/example/tool/compare/{PIN}...{HEAD}?per_page=1": {
                "status": "ahead", "ahead_by": 4, "behind_by": 0,
                "base_commit": {"sha": PIN, "commit": {"committer": {"date": "2026-09-25T18:06:27Z"}}}},
        }
        observation, calls = self.observe("example/tool", answers)
        self.assertIn(f"repos/example/tool/compare/{PIN}...{HEAD}?per_page=1", calls)
        self.assertEqual(observation["compare"], {"status": "ahead", "ahead_by": 4, "behind_by": 0,
                                                  "base_sha": PIN, "base_date": "2026-09-25T18:06:27Z"})
        row = practice_references.classify(entry("example/tool"), observation, NOW)
        self.assertEqual((row["flags"], row["commits_since_pin"], row["default_branch"]), (["drifted"], 4, "trunk"))

    def test_missing_repository_is_not_compared(self):
        observation, calls = self.observe("example/gone", {})
        self.assertEqual(calls, ["repos/example/gone"])
        self.assertEqual(practice_references.classify(entry("example/gone"), observation, NOW)["flags"], ["missing"])

    def test_redirected_repository_is_reported_as_renamed(self):
        answers = {
            "repos/example/old": {"full_name": "example/new", "archived": False, "default_branch": "main"},
            "repos/example/old/tags?per_page=1": [],
            "repos/example/old/commits/main": {"sha": PIN, "commit": {"committer": {"date": iso(NOW)}}},
            f"repos/example/old/compare/{PIN}...{PIN}?per_page=1": {
                "status": "identical", "ahead_by": 0, "behind_by": 0,
                "base_commit": {"sha": PIN, "commit": {"committer": {"date": "2026-09-25T18:06:27Z"}}}},
        }
        observation, _ = self.observe("example/old", answers)
        row = practice_references.classify(entry("example/old"), observation, NOW)
        self.assertEqual((row["flags"], row["renamed_to"]), (["renamed"], "example/new"))


def uses_lines(text):
    return [line.strip().removeprefix("- ") for line in text.splitlines() if re.search(r"^\s*(?:- )?uses:", line)]


class WorkflowTests(unittest.TestCase):
    """The workflow mirrors catalog-freshness.yml's conventions (the task's stated reference)."""

    text = WORKFLOW.read_text(encoding="utf-8")

    def test_triggers_permissions_and_token_follow_catalog_freshness(self):
        self.assertRegex(self.text, r"(?m)^on:\n  schedule:\n(?:    #.*\n)*    - cron: '[0-9]+ [0-9]+ \* \* [0-6]'\n"
                                    r"  workflow_dispatch:\n")
        self.assertEqual(re.findall(r"(?m)^[ \t]*permissions:.*$", self.text), ["permissions:"])
        self.assertIn("\npermissions:\n  contents: read\n\njobs:\n", self.text)
        self.assertEqual(self.text.count("GH_TOKEN: ${{ github.token }}"), 1)
        self.assertEqual(self.text.count("persist-credentials: false"), 1)
        self.assertIn('>> "$GITHUB_STEP_SUMMARY"', self.text)

    def test_every_action_pin_is_copied_from_catalog_freshness(self):
        reference = set(uses_lines(REFERENCE_WORKFLOW.read_text(encoding="utf-8")))
        used = uses_lines(self.text)
        self.assertEqual(len(used), 4)
        self.assertEqual([line for line in used if line not in reference], [])
        self.assertTrue(any(line.startswith("uses: actions/upload-artifact@") for line in used))

    def test_the_report_runs_the_checker_on_the_catalog_and_uploads_its_json(self):
        self.assertIn("python3 -m unittest tests.test_practice_references", self.text)
        self.assertIn("python3 tools/sota-convergence/practice_references.py \\\n"
                      "            --catalog catalogs/foundation/practice-references.json", self.text)
        self.assertIn("${{ runner.temp }}/practice-references/practice-references-freshness.json", self.text)

    @unittest.skipUnless(shutil.which("zizmor"), "native zizmor unavailable; CI installs the pinned analyzer")
    def test_workflow_has_no_offline_zizmor_findings(self):
        # The same offline invocation as tests/test_workflow_security_coverage.py.
        from tests.test_workflow_security_coverage import _analyze
        with tempfile.TemporaryDirectory() as temporary:
            result = _analyze(WORKFLOW, Path(temporary))
        try:
            findings = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(f"zizmor did not return JSON (exit {result.returncode}): {result.stderr[:2000]}")
        self.assertEqual(result.returncode, 0, result.stderr[:2000])
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
