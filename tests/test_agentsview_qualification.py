"""Guard the scope and sanitization of the dated AgentsView qualification.

Sources: kenn-io/agentsview v0.44.0 (413a87f7bfbd67b2815b1119ac51abc1efbeeaba),
internal/mcp/tools.go:705-726, cmd/agentsview/usage.go:163-168,
cmd/agentsview/serve_runtime.go:57-65; ccusage/ccusage v20.0.24
(ecb676cce27cb5dd0090c7804a5cecc35e8ba805), rust/adapters/codex/src/parser.rs.
Structural checks follow docs/acceptance-evidence-policy.md:31-69 and the
negative-control pattern in Python's unittest.TestCase.assertRaises:
https://docs.python.org/3.13/library/unittest.html#unittest.TestCase.assertRaises
The re-pin location registry follows the tracked-file inventory pattern of
tests/test_osv_lockfile_coverage.py (tracked_files and
test_every_tracked_lockfile_and_manifest_is_listed) and runs the recorded search
itself with git grep -z -n -I (https://git-scm.com/docs/git-grep; git 2.43.0
prints path NUL line NUL text).
These check artifact consistency, not upstream execution or provider runs.
"""

import copy
import itertools
import json
import os
from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "evidence/artifacts/agentsview-044-qualification-20260927"
DATED_PATH = re.compile(r"20\d{6}|20\d{2}-\d{2}-\d{2}")


def version_hits(pattern):
    """{path: [(line, text), ...]} for tracked working-tree files matching pattern (the recorded git grep)."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    found = subprocess.run(
        ["git", "-C", str(ROOT), "grep", "-z", "-n", "-I", "--no-color", "-E", "-e", pattern],
        env=environment, capture_output=True, check=False,
    )
    if found.returncode not in (0, 1):  # 1 means no match
        raise subprocess.CalledProcessError(found.returncode, found.args, found.stdout, found.stderr)
    hits = {}
    for record in found.stdout.split(b"\n"):
        if record:
            path, line, text = record.split(b"\0", 2)
            hits.setdefault(os.fsdecode(path), []).append((int(line), text.decode("utf-8", "replace")))
    return hits


def unclassified(registry, hits):
    """Matching files outside the dated prefixes that neither registry list classifies."""
    prefixes = tuple(registry["search"]["excluded_dated_prefixes"])
    classified = {entry["path"] for key in ("repin_targets", "not_repin_targets") for entry in registry[key]}
    return sorted(path for path in hits if not path.startswith(prefixes) and path not in classified)


def location_mismatches(registry, hits):
    """Re-pin files whose matching lines do not pair one-to-one with their recorded locations.

    A re-pin file may also carry dated record lines that name the pinned version and keep it after a
    re-pin (the topic JSON's per-tool cards). The entry's dated_record_lines.count says how many; they
    are the matching lines that contain no recorded match, and a count that differs fails the check.
    """
    problems = []
    for entry in registry["repin_targets"]:
        matches = [location["match"] for location in entry["locations"]]
        dated = entry.get("dated_record_lines", {}).get("count", 0)
        texts = [text for _, text in hits.get(entry["path"], [])]
        recorded = [text for text in texts if any(match in text for match in matches)]
        counts_fit = len(recorded) == len(matches) and len(texts) - len(recorded) == dated
        paired = counts_fit and any(
            all(match in text for match, text in zip(order, recorded)) for order in itertools.permutations(matches))
        if not paired:
            detail = " that do not pair by text" if counts_fit else ""
            extra = f" and {dated} dated record lines" if dated else ""
            problems.append(f"{entry['path']}: {len(texts)} matching lines, {len(matches)} recorded locations{extra}{detail}")
    return problems


class AgentsviewQualificationTests(unittest.TestCase):
    def read(self, name):
        return json.loads((ARTIFACT / name).read_text())

    def test_incomplete_gates_cannot_be_presented_as_a_qualified_repin(self):
        receipt = self.read("qualification.json")
        self.assertFalse(receipt["qualified"])
        self.assertFalse(receipt["pin_change_prepared"])
        self.assertFalse(receipt["host_switch_performed"])
        self.assertEqual(receipt["verdict"], "hold")
        self.assertEqual(receipt["gates"]["upstream_broad_tests"], "passed_outside_codex_sandbox")
        self.assertEqual(receipt["gates"]["fresh_four_native_lanes"], "blocked")
        self.assertEqual(receipt["gates"]["independent_gpt6_review"], "not_completed")
        self.assertEqual(receipt["gates"]["independent_claude_review"], "incomplete")
        self.assertEqual(receipt["gates"]["unchanged_full_save_runner"], "not_run")
        self.assertEqual(receipt["evidence_class"], "multi_class_summary")
        self.assertEqual(receipt["repository_tests"]["evidence_class"], "structural_validation")
        self.assertTrue(receipt["residuals"])
        self.assertTrue(receipt["errata"])

    def test_review_attempts_cannot_be_promoted_to_completed_reviews(self):
        reviews = self.read("qualification.json")["reviews"]
        self.assertEqual(reviews["gpt6"]["status"], "not_completed")
        self.assertNotIn("verdict", reviews["gpt6"])
        self.assertNotIn("independently_checked", reviews["gpt6"])
        self.assertFalse(reviews["gpt6"]["returned_report_retained"])
        self.assertEqual(len(reviews["native_codex_attempts"]), 2)
        for attempt in reviews["native_codex_attempts"]:
            self.assertEqual(attempt["exit_code"], 1)
            self.assertEqual(attempt["jsonl_bytes"], 0)
            self.assertFalse(attempt["last_message_exists"])
            self.assertTrue(attempt["stderr_ref"].endswith(".stderr"))
        claude = reviews["claude"]
        self.assertEqual(claude["stopped_by"], "build_session")
        self.assertEqual(claude["signal"], "SIGINT")
        self.assertEqual(claude["exit_code"], 130)
        self.assertEqual(claude["tools"], ["Read", "Agent"])
        self.assertEqual(claude["launch_context"], "inside_builder_codex_sandbox")
        self.assertEqual(claude["requalification_context"], "outside_codex_sandbox")

    def test_prior_verdict_and_future_pin_locations_are_reconciled(self):
        receipt = self.read("qualification.json")
        prior = receipt["prior_records"][0]
        self.assertEqual(prior["path"], "evidence/artifacts/sota-refresh-20260923/pins-tools/agentsview.json")
        self.assertEqual(prior["verdict"], "qualified")
        self.assertEqual(prior["governing_repin_record"], "qualification.json")
        self.assertFalse(prior["satisfies_full_qualification"])
        self.assertIn("limits[0]", prior["scope_basis"])
        locations = receipt["repository_pin_locations"]
        targets = {entry["path"]: entry for entry in locations["repin_targets"]}
        required = {"manifests/stack.json", "scripts/native_token_ci.py", "recipes/README.md",
                    "docs/token-efficiency-stack.json", "blueprints/token-native-focus/saturation-audit.json",
                    "catalogs/landscape/upstream-snapshot.json"}
        self.assertTrue(required.issubset(targets))
        # Mirrors that existing checks compare with manifests/stack.json name those checks.
        self.assertTrue(targets["blueprints/token-native-focus/saturation-audit.json"]["enforced_by"]
                        .startswith("tests/test_stack_lifecycle.py:28-32"))
        self.assertTrue(targets["catalogs/landscape/upstream-snapshot.json"]["enforced_by"]
                        .startswith("scripts/landscape.py:1373-1381"))
        self.assertEqual([location["kind"] for location in targets["recipes/README.md"]["locations"]],
                         ["install_reference", "version_specific_guidance"])
        kept = {entry["path"]: entry for entry in locations["not_repin_targets"]}
        self.assertEqual(kept["docs/stack.md"]["class"], "dated_record")
        rewire = receipt["required_future_recipe_rewire"]["files"]
        self.assertTrue({"recipes/README.md", "docs/token-efficiency-stack.json"}.issubset(rewire))
        self.assertNotIn("docs/stack.md", rewire)
        self.assertEqual(rewire["docs/token-efficiency-stack.json"]["fields"],
                         ["install", "install_note", "use"])

    def test_errata_do_not_name_an_unretained_reviewer(self):
        for erratum in self.read("qualification.json")["errata"]:
            with self.subTest(date=erratum["date"]):
                self.assertNotRegex(erratum["reason"], r"(?i)\bindependent")
                self.assertIn("reviewer identity and returned report not retained", erratum["reason"])

    def test_copied_archive_parity_counts_cached_input_once(self):
        observed = self.read("native-checks.json")["copied_archive"]
        expected = {"inputTokens": 20965, "cacheReadTokens": 58752,
                    "cacheCreationTokens": 0, "outputTokens": 556}
        for version in ("0.43.0", "0.44.0"):
            self.assertEqual(observed["versions"][version]["cli_tokens"], expected)
            self.assertEqual(observed["versions"][version]["inclusive_sessions"], 2)
        ccusage = observed["ccusage"]
        self.assertEqual({k: ccusage[k] for k in expected}, expected)
        self.assertEqual(ccusage["totalTokens"], sum(expected.values()))
        self.assertEqual(ccusage["reasoningOutputTokens"], 64)
        self.assertTrue(observed["session_keys_preserved"])
        self.assertTrue(observed["source_copies_byte_identical"])
        self.assertEqual(observed["fresh_provider_executions"], 0)

    def test_mcp_gap_port_change_and_failed_fixture_are_retained(self):
        checks = self.read("native-checks.json")
        archive = checks["copied_archive"]["versions"]
        self.assertEqual(archive["0.44.0"]["mcp_tokens"]["outputTokens"], 0)
        self.assertEqual(archive["0.43.0"]["mcp_tokens"]["outputTokens"], 556)
        self.assertEqual(checks["occupied_port"]["0.43.0"]["exit_code"], 0)
        self.assertEqual(checks["occupied_port"]["0.44.0"]["exit_code"], 1)
        self.assertEqual(checks["synthetic_fixture"]["ccusage_parity"], "failed")
        self.assertEqual(checks["synthetic_fixture"]["expected_sessions"], 5)
        fixture = checks["synthetic_fixture"]
        self.assertEqual(fixture["expected_automated_sessions"], {"0.43.0": 0, "0.44.0": 2})
        frozen = fixture["frozen_inputs"]
        self.assertEqual(frozen["capture_stage"], "repair_after_original_trial")
        self.assertEqual(len(frozen["files"]), 23)
        self.assertEqual(sum(f["kind"] == "session_log" for f in frozen["files"]), 5)
        self.assertEqual(len({f["label"] for f in frozen["files"]}), 23)
        for entry in frozen["files"]:
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(entry["bytes"], 0)
        for version in ("0.43.0", "0.44.0"):
            self.assertEqual(fixture["versions"][version]["inclusive_sessions"], 5)
            self.assertEqual(fixture["versions"][version]["automated_sessions"],
                             fixture["expected_automated_sessions"][version])

    def test_upstream_failures_stay_distinct_from_targeted_success(self):
        upstream = self.read("upstream-tests.json")
        self.assertEqual(upstream["evidence_class"], "unchanged_upstream_tests")
        self.assertTrue(upstream["tracked_source_unchanged"])
        self.assertEqual(upstream["targeted_classification"]["top_level_tests_passed"], 4)
        self.assertEqual(upstream["targeted_classification"]["test_events_passed"], 13)
        self.assertEqual(upstream["broad_attempt"]["exit_code"], 1)
        self.assertEqual(upstream["broad_attempt"]["top_level_counts"]["failed"], 21)
        self.assertEqual(upstream["broad_attempt"]["test_event_counts"]["failed"], 25)
        self.assertEqual(len(upstream["broad_attempt"]["failed_test_events"]), 25)
        self.assertEqual(upstream["broad_attempt"]["failure_class"], "environmental")
        self.assertFalse(upstream["confirming_subprocess_rerun"]["raw_bytes_retained"])
        self.assertIn("gpt6-build-events.jsonl", upstream["confirming_subprocess_rerun"]["summary_ref"])
        controls = upstream["coordinator_runs"]
        self.assertEqual(controls["execution_context"], "outside_codex_sandbox")
        self.assertTrue(controls["environment"]["TMPDIR"].startswith("/var/tmp/"))
        self.assertTrue(controls["tracked_source_clean_before_and_after"])
        expected = {
            "v0.44.0": (4575, "8529d7daa9b6c60ec2730066330f2e347adbc17a4af64ae2d906708221bb7190"),
            "v0.43.0": (4387, "ace5a04c6183b31924856f9f36ba79cbbe812317ef9d5d813262e6aa892e4ec4"),
        }
        for run in controls["broad"]:
            count, digest = expected[run["tag"]]
            self.assertEqual(run["exit_code"], 0)
            self.assertEqual(run["top_level_counts"], {"passed": count, "failed": 0, "skipped": 32})
            self.assertEqual(run["stdout_sha256"], digest)
            self.assertTrue(run["stdout_ref"].endswith(".jsonl"))
        self.assertEqual({r["tag"] for r in controls["broad"]}, set(expected))
        serve = controls["serve_runtime"]
        self.assertEqual(serve["exit_code"], 0)
        self.assertEqual(serve["top_level_counts"], {"passed": 5, "failed": 0, "skipped": 0})
        self.assertEqual(serve["stdout_sha256"], "533a163412c06f37a6155d0cc18f4b776d7a4854d4784ae8b3f130553ebbd485")
        self.assertIn("TestPrepareRunServeRuntimeConfigRestartPreservesConfiguredURLRewrite", serve["test_names"])
        self.assertEqual(upstream["diagnosis"]["status"], "environmental_failure_discriminated")

    def test_published_artifacts_use_whitelisted_aggregates(self):
        forbidden_keys = {
            "session_id", "sessionId", "parent_session_id", "connection_id",
            "machineName", "machine_name", "account_id", "email", "uuid",
            "request_body", "requestBody", "messages", "inclusive_rows",
            "project", "project_id", "content", "prompt", "api_key",
        }

        def visit(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden_keys.intersection(value))
                for item in value.values():
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)

        def check(text, is_json):
            self.assertNotRegex(text, r"/(?:home|Users)/[^/\s]+")
            self.assertNotRegex(text, r"/tmp/claude-\d+")
            self.assertNotRegex(text, r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b")
            self.assertNotRegex(text, r"(?i)bearer\s+[a-z0-9._~+/=-]+")
            if is_json:
                visit(json.loads(text))

        # Generated violations exercise the very same checks as published files.
        # Source: unittest.TestCase.assertRaises; no real private value is used.
        planted = {
            "home_path": {"nested": ["/".join(("", "home", "planted", "receipt"))]},
            "uuid": {"nested": ["-".join("0" * n for n in (8, 4, 4, 4, 12))]},
            "forbidden_key": {"nested": [{"request_body": "planted"}]},
        }
        for label, value in planted.items():
            with self.subTest(planted=label), self.assertRaises(AssertionError):
                check(json.dumps(value), True)

        paths = list(ARTIFACT.iterdir())
        self.assertGreaterEqual(len(paths), 5)
        for path in paths:
            with self.subTest(path=path.name):
                check(path.read_text(), path.suffix == ".json")


class RepinLocationRegistryTests(unittest.TestCase):
    """While the pin holds, every tracked file outside the dated evidence paths that names the pinned version
    is a recorded re-pin file or a classified record."""

    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ARTIFACT / "qualification.json").read_text())["repository_pin_locations"]
        components = json.loads((ROOT / "manifests/stack.json").read_text())["components"]
        cls.pinned = next(component["version"] for component in components if component["id"] == "agentsview")

    def hits(self):
        try:
            return version_hits(self.registry["search"]["pattern"])
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a Git checkout; the recorded search cannot run")

    def require_pin_held(self):
        if self.pinned != self.registry["current_version"]:
            self.skipTest("manifests/stack.json was re-pinned; this dated list describes the hold")

    def test_every_matching_file_outside_dated_prefixes_is_classified(self):
        self.require_pin_held()
        search = self.registry["search"]
        self.assertIn(search["pattern"], search["command"])
        self.assertRegex(self.registry["current_version"], search["pattern"])
        hits = self.hits()
        self.assertEqual(unclassified(self.registry, hits), [],
                         "classify these in qualification.json repository_pin_locations")
        prefixes = tuple(search["excluded_dated_prefixes"])
        for path in hits:
            if path.startswith(prefixes):
                self.assertRegex(path, DATED_PATH, f"{path} is excluded as dated but its path has no date")
        for entry in self.registry["not_repin_targets"]:
            with self.subTest(path=entry["path"]):
                self.assertIn(entry["path"], hits, "a kept record must still match the recorded search")
                if entry["class"] == "dated_record":
                    text = (ROOT / entry["path"]).read_text(encoding="utf-8")
                    self.assertTrue(entry["basis"] in entry["path"] or entry["basis"] in text)
                else:
                    self.assertEqual(entry["class"], "unrelated_package")
                    for _, line in hits[entry["path"]]:
                        self.assertIn(entry["basis"], line)
                        self.assertNotIn("agentsview", line.lower())

    def test_recorded_repin_locations_match_the_tree_while_the_pin_holds(self):
        self.require_pin_held()
        self.assertEqual(location_mismatches(self.registry, self.hits()), [])

    def test_the_dated_record_line_count_is_exact(self):
        self.require_pin_held()
        hits = self.hits()
        topic = next(index for index, entry in enumerate(self.registry["repin_targets"])
                     if entry["path"] == "docs/token-efficiency-stack.json")
        count = self.registry["repin_targets"][topic]["dated_record_lines"]["count"]
        self.assertGreater(count, 0)
        for wrong in (count - 1, count + 1):
            with self.subTest(count=wrong):
                changed = copy.deepcopy(self.registry)
                changed["repin_targets"][topic]["dated_record_lines"]["count"] = wrong
                self.assertEqual(len(location_mismatches(changed, hits)), 1)

    def test_a_list_missing_any_entry_or_location_is_detected(self):
        self.require_pin_held()
        hits = self.hits()
        self.assertEqual(unclassified(self.registry, hits) + location_mismatches(self.registry, hits), [])
        for key in ("repin_targets", "not_repin_targets"):
            for index, entry in enumerate(self.registry[key]):
                with self.subTest(removed=entry["path"]):
                    reduced = copy.deepcopy(self.registry)
                    del reduced[key][index]
                    self.assertEqual(unclassified(reduced, hits), [entry["path"]])
        for index, entry in enumerate(self.registry["repin_targets"]):
            for position, location in enumerate(entry["locations"]):
                with self.subTest(removed=f"{entry['path']}:{location['line_at_record']}"):
                    reduced = copy.deepcopy(self.registry)
                    del reduced["repin_targets"][index]["locations"][position]
                    self.assertEqual(len(location_mismatches(reduced, hits)), 1)


if __name__ == "__main__":
    unittest.main()
