"""Tests for tools/skill-usage/skill_usage.py. Fixtures are synthetic (tests/fixtures/skill_usage/):
no real host paths, cwd or session ids, and skill names drawn from the real pinned skills manifest."""
from __future__ import annotations

import collections
import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "skill-usage"))
import skill_usage as S  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "skill_usage"
NOW = "2026-10-30T00:00:00Z"
# The tree-sitter-bash install the kernel's lane layer loads (child-usage.mjs loadShellParser): CHILD_USAGE_SHELL_PARSER,
# else the ecosystem tools directory. Tests that count lanes skip, with this message, on a host without it.
PARSER_DIR = Path(os.environ.get("CHILD_USAGE_SHELL_PARSER") or Path.home() / ".local/share/codex-ecosystem/tools/tree-sitter-bash-0.25.1")
PARSER_INSTALLED = (PARSER_DIR / "package-lock.json").is_file()
# The kernel's RTK replay prerequisite, as tests/test_token_measurement.py checks it: Linux and a binary on PATH self-reporting
# rtk 0.50.0 (the kernel also probes the five exclusions; neither check pins a build).
RTK_REPLAY_SUPPORTED = (sys.platform == "linux" and shutil.which("rtk") is not None and bool(re.fullmatch(
    r"rtk 0\.50\.0\s*", subprocess.run(["rtk", "--version"], text=True, capture_output=True, check=False).stdout)))


def load_fixture_manifest() -> dict:
    return S.load_manifest(FIXTURES / "manifest.json")


def fixture_names() -> list[str]:
    return [skill["name"] for skill in load_fixture_manifest()["skills"]]


def materialize_codex_roots(dest: Path) -> list[Path]:
    """Copy tests/fixtures/skill_usage/codex_root_{a,b} into `dest`, restoring each rollout
    line's real 'rollout-*.jsonl' name. They are committed as '*.jsonl.fixture' because the
    repository .gitignore has a blanket '*.jsonl' rule that would otherwise silently drop them;
    this is test-local materialization, never a change to that shared, unowned file. Preserves
    root_a's nested subdirectory so recursive-scan coverage is unaffected."""
    roots = []
    for root_name in ("codex_root_a", "codex_root_b"):
        source_root = FIXTURES / root_name
        dest_root = dest / root_name
        dest_root.mkdir(parents=True, exist_ok=True)
        for fixture_path in source_root.rglob("*.jsonl.fixture"):
            target = dest_root / fixture_path.relative_to(source_root).with_suffix("")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fixture_path, target)
        roots.append(dest_root)
    return roots


class ParsingHelpers(unittest.TestCase):
    def test_parse_approx_count(self):
        self.assertEqual(S.parse_approx_count("~110"), 110)
        self.assertEqual(S.parse_approx_count("-"), None)
        self.assertEqual(S.parse_approx_count("1.2k"), 1200)
        self.assertEqual(S.parse_approx_count("340"), 340)
        self.assertEqual(S.parse_approx_count("garbage"), None)

    def test_parse_iso_accepts_z_and_offset(self):
        a = S.parse_iso("2026-10-30T00:00:00Z")
        b = S.parse_iso("2026-10-30T00:00:00+00:00")
        self.assertEqual(a, b)
        self.assertIsNotNone(a.tzinfo)

    def test_parse_iso_rejects_garbage(self):
        with self.assertRaises(ValueError):
            S.parse_iso("not-a-timestamp")

    def test_evaluate_cost(self):
        self.assertTrue(S.evaluate_cost(0, 0))
        self.assertFalse(S.evaluate_cost(0.004, 0))
        self.assertFalse(S.evaluate_cost(0, 1))
        self.assertFalse(S.evaluate_cost(None, 0))

    def test_find_result_event_scans_from_the_end(self):
        events = [{"type": "system"}, {"type": "assistant"}, {"type": "result", "id": 1}]
        self.assertEqual(S.find_result_event(events)["id"], 1)
        self.assertIsNone(S.find_result_event([{"type": "system"}, {"type": "assistant"}]))


class SkillDoctorParsing(unittest.TestCase):
    def test_parse_text_fixture_rows(self):
        text = (FIXTURES / "skill-doctor-sample.txt").read_text()
        rows = S.parse_skill_doctor_text(text)
        self.assertEqual(set(rows), {"gh-fix-ci", "typesafe-ai", "tdd", "diagnosing-bugs",
                                      "grill-me", "codeql"})
        self.assertEqual(rows["gh-fix-ci"], {"source": "userSettings", "context_tokens": 110,
                                              "tokens_7d": 340, "uses": 6, "last_used": "2 days ago"})
        self.assertEqual(rows["typesafe-ai"]["uses"], 0)
        self.assertEqual(rows["typesafe-ai"]["last_used"], "never")
        self.assertIsNone(rows["grill-me"]["context_tokens"])  # "-" = not in the current listing

    def test_header_and_footnote_lines_never_match_a_row(self):
        text = ("  skill                           source          context  7d tokens   uses  last used\n"
                "  context = this skill's one-line listing in the system prompt\n"
                "5 skills loaded but never invoked.\n")
        self.assertEqual(S.parse_skill_doctor_text(text), {})

    def test_less_than_listing_cost_is_a_bound_not_part_of_the_source(self):
        # Claude Code 2.1.283 prints a name-only listing's cost as "< 20".
        rows = S.parse_skill_doctor_text(
            "  typesafe-ai                        userSettings       < 20          -     0×  never\n"
            "  search-first                       userSettings       < 20       <20    36×  today\n")
        self.assertEqual(rows["typesafe-ai"]["source"], "userSettings")
        self.assertEqual(rows["typesafe-ai"]["context_tokens"], 20)
        self.assertEqual((rows["search-first"]["tokens_7d"], rows["search-first"]["uses"]), (20, 36))
        self.assertEqual(S.parse_approx_count("< 20"), 20)

    def test_source_column_may_contain_a_space(self):
        rows = S.parse_skill_doctor_text(
            "  anthropic-skills:docs           claude.ai sync     ~330          -     0×  never")
        self.assertEqual(rows["anthropic-skills:docs"]["source"], "claude.ai sync")

    def test_parse_claude_output_json_matches_text(self):
        text_rows = S.parse_skill_doctor_text((FIXTURES / "skill-doctor-sample.txt").read_text())
        parsed = S.parse_claude_output((FIXTURES / "skill-doctor-sample.json").read_text())
        self.assertNotIn("error", parsed)
        self.assertEqual(parsed["format"], "json")
        self.assertEqual((parsed["total_cost_usd"], parsed["num_turns"]), (0, 0))
        self.assertEqual(parsed["rows"], text_rows)

    def test_parse_claude_output_plain_text_has_no_cost_signal(self):
        parsed = S.parse_claude_output((FIXTURES / "skill-doctor-sample.txt").read_text())
        self.assertEqual(parsed["format"], "text")
        self.assertIsNone(parsed["total_cost_usd"])
        self.assertIsNone(parsed["num_turns"])
        self.assertNotIn("error", parsed)

    def test_refuses_nonzero_cost_result(self):
        parsed = S.parse_claude_output((FIXTURES / "skill-doctor-nonzero-cost.json").read_text())
        self.assertIn("error", parsed)
        self.assertEqual(parsed["rows"], {})
        self.assertEqual(parsed["total_cost_usd"], 0.004)
        self.assertEqual(parsed["num_turns"], 1)

    def test_refuses_a_nonzero_cost_result_object(self):
        # The zero-cost check holds for the single result object `claude -p --output-format json` prints
        # (`claude --help` 2.1.283: "json" (single result)) as it does for the message array printed when verbose is
        # on (a 2.1.283 binary read, not a live reproduction; see S.parse_claude_output).
        messages = json.loads((FIXTURES / "skill-doctor-nonzero-cost.json").read_text())
        parsed = S.parse_claude_output(json.dumps(S.find_result_event(messages)))
        self.assertIn("refusing a nonzero-cost result", parsed.get("error", ""))
        self.assertEqual(parsed["rows"], {})
        self.assertEqual((parsed["total_cost_usd"], parsed["num_turns"]), (0.004, 1))

    def test_refuses_json_that_is_neither_a_result_object_nor_an_event_array(self):
        # An object that is no result message, even one carrying zero-cost fields and a table, and a JSON scalar.
        row = "  gh-fix-ci                       userSettings       ~110         340    6×  2 days ago"
        for raw in (json.dumps({"not": "a list"}),
                    json.dumps({"type": "assistant", "total_cost_usd": 0, "num_turns": 0, "result": row}),
                    "42", "null", json.dumps(row)):
            with self.subTest(raw=raw):
                parsed = S.parse_claude_output(raw)
                self.assertIn("error", parsed)
                self.assertEqual(parsed["rows"], {})

    def test_refuses_an_error_result_in_either_shape(self):
        # is_error can be true with subtype "success" (an API error; claude-agent-sdk-python types.py:1358-1360),
        # and a zero-cost error result must not be read as a measured /skill-doctor table.
        messages = json.loads((FIXTURES / "skill-doctor-sample.json").read_text())
        result = S.find_result_event(messages)
        for change in ({"is_error": True}, {"subtype": "error_during_execution", "is_error": True},
                       {"subtype": "error_max_turns"}, {"is_error": None}):
            for shape in ("object", "array"):
                with self.subTest(change=change, shape=shape):
                    event = {**result, **change}
                    raw = json.dumps(event if shape == "object" else
                                     [m if m is not result else event for m in messages])
                    parsed = S.parse_claude_output(raw)
                    self.assertIn("refusing an error result", parsed.get("error", ""))
                    self.assertEqual(parsed["rows"], {})
        missing = {k: v for k, v in result.items() if k != "is_error"}
        self.assertIn("refusing an error result", S.parse_claude_output(json.dumps(missing)).get("error", ""))

    def test_refuses_array_with_no_result_event(self):
        parsed = S.parse_claude_output(json.dumps([{"type": "system"}, {"type": "assistant"}]))
        self.assertIn("error", parsed)


class RunSkillDoctor(unittest.TestCase):
    def test_runs_exact_argv_with_devnull_stdin_and_timeout(self):
        captured = {}

        def fake_runner(argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            return subprocess.CompletedProcess(argv, 0, "[]", "")

        S.run_skill_doctor(timeout=17, runner=fake_runner)
        self.assertEqual(captured["argv"], ["claude", "-p", "/skill-doctor", "--output-format", "json"])
        self.assertIs(captured["kwargs"]["stdin"], subprocess.DEVNULL)
        self.assertEqual(captured["kwargs"]["timeout"], 17)
        self.assertTrue(captured["kwargs"]["text"])
        self.assertTrue(captured["kwargs"]["capture_output"])

    def test_uses_the_sample_fixture_stdout(self):
        sample = (FIXTURES / "skill-doctor-sample.json").read_text()
        runner = lambda argv, **kw: subprocess.CompletedProcess(argv, 0, sample, "")
        result = S.run_skill_doctor(runner=runner)
        self.assertNotIn("error", result)
        self.assertEqual(result["rows"]["gh-fix-ci"]["uses"], 6)

    def test_run_reads_either_json_output_shape(self):
        # `claude -p --output-format json` prints one result object (`claude --help` 2.1.283: "json" (single result))
        # or, when verbose is on, the message array (a 2.1.283 binary read, not a live reproduction; see
        # S.parse_claude_output). find_result_event takes the last element of type "result" from either, this
        # repository's selection; anthropics/claude-agent-sdk-python@36f95486ee9f
        # src/claude_agent_sdk/_internal/message_parser.py:308 parses a message of that type as the ResultMessage.
        sample = (FIXTURES / "skill-doctor-sample.json").read_text()
        stdouts = {"array": sample, "object": json.dumps(S.find_result_event(json.loads(sample)))}
        results = {}
        for shape, stdout in stdouts.items():
            with self.subTest(shape=shape):
                runner = lambda argv, stdout=stdout, **kw: subprocess.CompletedProcess(argv, 0, stdout, "")
                results[shape] = S.run_skill_doctor(runner=runner)
                self.assertNotIn("error", results[shape])
                self.assertEqual(results[shape]["rows"]["gh-fix-ci"]["uses"], 6)
        self.assertEqual(results["object"], results["array"])

    def test_refuses_nonzero_cost_from_a_run(self):
        sample = (FIXTURES / "skill-doctor-nonzero-cost.json").read_text()
        runner = lambda argv, **kw: subprocess.CompletedProcess(argv, 0, sample, "")
        result = S.run_skill_doctor(runner=runner)
        self.assertIn("error", result)
        self.assertEqual(result["total_cost_usd"], 0.004)

    def test_nonzero_exit_is_an_error(self):
        runner = lambda argv, **kw: subprocess.CompletedProcess(argv, 1, "", "boom")
        result = S.run_skill_doctor(runner=runner)
        self.assertIn("error", result)

    def test_timeout_is_an_error(self):
        def raising_runner(argv, **kw):
            raise subprocess.TimeoutExpired(cmd=argv, timeout=kw.get("timeout", 30))
        result = S.run_skill_doctor(runner=raising_runner)
        self.assertIn("error", result)
        self.assertIn("TimeoutExpired", result["error"])


class CodexRolloutScan(unittest.TestCase):
    def setUp(self):
        self.manifest = load_fixture_manifest()
        self.names = fixture_names()
        self.now = S.parse_iso(NOW)
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.roots = materialize_codex_roots(tmp)

    def scan(self, windows=(7, 30)):
        return S.scan_codex_roots(self.roots, self.names, now=self.now, windows=windows)

    def test_roots_and_files_counted_without_paths_in_the_result(self):
        scan = self.scan()
        self.assertEqual(scan["roots_count"], 2)
        self.assertEqual(scan["files_scanned"], 3)  # two files under root_a (one nested), one under root_b
        dumped = json.dumps(scan)
        self.assertNotIn(str(FIXTURES), dumped)
        self.assertNotIn("SKILL.md", dumped)  # counts only, never the paths that were matched

    def test_malformed_line_counts_as_a_parse_error_not_a_crash(self):
        scan = self.scan()
        self.assertEqual(scan["parse_errors"], 1)

    def test_skill_md_read_and_mention_counted_for_gh_fix_ci(self):
        scan = self.scan()
        counts = scan["counts"]["gh-fix-ci"]
        self.assertEqual(counts[7], {"skill_md_reads": 2, "name_mentions": 1})
        self.assertEqual(counts[30], {"skill_md_reads": 2, "name_mentions": 1})

    def test_out_of_manifest_skill_reference_is_ignored(self):
        scan = self.scan()
        self.assertNotIn("not-a-real-skill", scan["counts"])

    def test_out_of_window_mention_excluded_from_every_window(self):
        # The $tdd mention in the fixture is 59 days before `now`: outside both 7d and 30d.
        scan = self.scan()
        self.assertEqual(scan["counts"]["tdd"][7]["name_mentions"], 0)
        self.assertEqual(scan["counts"]["tdd"][30]["name_mentions"], 0)

    def test_window_boundary_between_7_and_30_days(self):
        # grill-me's local_shell_call SKILL.md read is 20 days old: in the 30d window, not the 7d.
        scan = self.scan()
        self.assertEqual(scan["counts"]["grill-me"][7]["skill_md_reads"], 0)
        self.assertEqual(scan["counts"]["grill-me"][30]["skill_md_reads"], 1)

    def test_no_roots_scans_nothing(self):
        scan = S.scan_codex_roots([], self.names, now=self.now, windows=(7, 30))
        self.assertEqual((scan["roots_count"], scan["files_scanned"]), (0, 0))
        self.assertEqual(scan["counts"]["gh-fix-ci"][7], {"skill_md_reads": 0, "name_mentions": 0})

    def test_scan_records_which_windows_it_actually_computed(self):
        scan = S.scan_codex_roots(self.roots, self.names, now=self.now, windows=[7])
        self.assertEqual(scan["windows"], [7])

    def test_iter_rollout_files_dedupes_overlapping_roots(self):
        overlapping = [self.roots[0], self.roots[0] / "nested"]
        files = S.iter_rollout_files(overlapping)
        self.assertEqual(len(files), 2)  # not double-counted despite the nested root also being a root

    def test_iter_rollout_files_no_default_search(self):
        self.assertEqual(S.iter_rollout_files([]), [])
        self.assertEqual(S.iter_rollout_files(None), [])


class GenericStringScanning(unittest.TestCase):
    """FunctionCall.arguments is a JSON-encoded *string*; ToolSearchCall.arguments is already a
    JSON *object* (codex-rs/protocol/src/models.rs). skillmd_hits must find a SKILL.md path either
    way without special-casing the variant."""

    def test_skillmd_hits_through_a_json_encoded_string_field(self):
        payload = {"type": "function_call", "name": "Read",
                   "arguments": json.dumps({"file_path": "/home/example/.agents/skills/gh-fix-ci/SKILL.md"})}
        self.assertEqual(S.skillmd_hits(payload, ["gh-fix-ci", "tdd"]), {"gh-fix-ci"})

    def test_skillmd_hits_through_an_already_nested_object_field(self):
        payload = {"type": "tool_search_call", "execution": "search",
                   "arguments": {"query": "read /home/example/.agents/skills/tdd/SKILL.md"}}
        self.assertEqual(S.skillmd_hits(payload, ["gh-fix-ci", "tdd"]), {"tdd"})

    def test_skillmd_hits_through_a_command_argv_array(self):
        payload = {"type": "local_shell_call", "action": {
            "type": "exec", "command": ["cat", "/home/example/.agents/skills/tdd/SKILL.md"]}}
        self.assertEqual(S.skillmd_hits(payload, ["gh-fix-ci", "tdd"]), {"tdd"})

    def test_skillmd_hits_requires_the_slash_delimited_suffix(self):
        # "other-tdd-extra/SKILL.md" must not match the manifest skill "tdd".
        payload = {"type": "function_call", "arguments": json.dumps(
            {"file_path": "/home/example/.agents/skills/other-tdd-extra/SKILL.md"})}
        self.assertEqual(S.skillmd_hits(payload, ["tdd"]), set())

    def test_mention_hits_word_boundary(self):
        patterns = {"ai": re.compile(r"\$ai\b")}
        self.assertEqual(S.mention_hits("please use $ai now", patterns), {"ai"})
        self.assertEqual(S.mention_hits("please use $ai2 now", patterns), set())
        self.assertEqual(S.mention_hits("$typesafe-ai is unrelated", patterns), set())


class ManifestAndLock(unittest.TestCase):
    def test_load_manifest_fixture(self):
        manifest = load_fixture_manifest()
        self.assertEqual(manifest["trial"]["window_days"], 30)
        self.assertEqual(len(manifest["skills"]), 7)

    def test_load_manifest_rejects_missing_skills_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "manifest.json"
            bad.write_text(json.dumps({"schema_version": 1}))
            with self.assertRaises(ValueError):
                S.load_manifest(bad)

    def test_skill_lock_path_xdg_state_home_takes_precedence(self):
        path = S.skill_lock_path(home="/home/example", environment={"XDG_STATE_HOME": "/xdg-state"})
        self.assertEqual(path, Path("/xdg-state/skills/.skill-lock.json"))

    def test_skill_lock_path_takes_any_non_empty_xdg_state_home_as_the_cli_does(self):
        # skills 1.7.0 (npm dist/cli.mjs L3746-3750) uses any non-empty XDG_STATE_HOME, untrimmed, relative or not,
        # through path.join; it does not apply the XDG Base Directory spec's absolute-path rule. Empty is unset.
        for value, expected in (("relative/dir", "relative/dir/skills/.skill-lock.json"),
                                (" ", " /skills/.skill-lock.json"),
                                ("", "/users/example/.agents/.skill-lock.json")):
            with self.subTest(xdg_state_home=value):
                path = S.skill_lock_path(home="/users/example", environment={"XDG_STATE_HOME": value})
                self.assertEqual(path, Path(expected))

    def test_skill_lock_path_is_joined_as_the_cli_path_join_joins_it(self):
        # path.join collapses "." and ".." lexically and a leading // to /; pathlib keeps the "..", which through a
        # missing or symlinked folder names another file than the one the CLI wrote.
        cases = (({"XDG_STATE_HOME": "/x/missing/../state"}, None, "/x/state/skills/.skill-lock.json"),
                 ({"XDG_STATE_HOME": "//x/./state"}, None, "/x/state/skills/.skill-lock.json"),
                 ({}, "/users/missing/../example", "/users/example/.agents/.skill-lock.json"),
                 ({"HOME": "//users/missing/../example"}, None, "/users/example/.agents/.skill-lock.json"))
        for environment, home, expected in cases:
            with self.subTest(environment=environment, home=home):
                self.assertEqual(S.skill_lock_path(home=home, environment=environment), Path(expected))

    def test_skill_lock_path_agrees_with_install_skills(self):
        # One join serves both tools: skill_usage.node_path_join is install_skills.py's.
        spec = importlib.util.spec_from_file_location("install_skills_for_usage_tests",
                                                      ROOT / "tools" / "adoption" / "install_skills.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        home = "/users/missing/../example"
        for environment in ({}, {"XDG_STATE_HOME": "rel/../state"}, {"XDG_STATE_HOME": "//x/missing/../state"}):
            with self.subTest(environment=environment), mock.patch.dict(os.environ, environment):
                if not environment:
                    os.environ.pop("XDG_STATE_HOME", None)
                self.assertEqual(S.skill_lock_path(home=home, environment=environment),
                                 installer.lock_file_path(Path(home)))

    def test_skill_lock_path_home_fallback(self):
        path = S.skill_lock_path(home="/home/example", environment={})
        self.assertEqual(path, Path("/home/example/.agents/.skill-lock.json"))

    def test_load_lock_installed_at_from_fixture(self):
        installed = S.load_lock_installed_at(FIXTURES / "fake-home" / ".agents" / ".skill-lock.json")
        self.assertEqual(installed["gh-fix-ci"], "2026-10-25T00:00:00.000Z")
        self.assertNotIn("codeql", installed)  # deliberately absent from the fixture lock

    def test_load_lock_installed_at_missing_file_is_empty(self):
        self.assertEqual(S.load_lock_installed_at(Path("/no/such/lock.json")), {})

    def test_load_lock_installed_at_malformed_json_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / ".skill-lock.json"
            bad.write_text("not json")
            self.assertEqual(S.load_lock_installed_at(bad), {})


class BuildReportPruneLogic(unittest.TestCase):
    """The master join test: exercises every prune_rule branch named in the manifest's own
    trial.prune_rule ("kept skills are flagged 'verdict re-record required' instead of demoted")
    against one fixed, fully-measured scenario."""

    def setUp(self):
        self.manifest = load_fixture_manifest()
        self.names = fixture_names()
        self.now = S.parse_iso(NOW)
        self.windows = S.effective_windows([7, 30], self.manifest)
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.roots = materialize_codex_roots(tmp)
        self.scan = S.scan_codex_roots(self.roots, self.names, now=self.now, windows=self.windows)
        self.claude = S.parse_claude_output((FIXTURES / "skill-doctor-sample.json").read_text())
        self.claude["origin"] = "file"

    def build(self, **overrides):
        lock = overrides.pop("lock_installed_at",
                              S.load_lock_installed_at(FIXTURES / "fake-home" / ".agents" / ".skill-lock.json"))
        kwargs = dict(claude=self.claude, codex_scan=self.scan, lock_installed_at=lock,
                      now=self.now, windows=[7, 30])
        kwargs.update(overrides)
        return S.build_report(self.manifest, **kwargs)

    def entry(self, report, name):
        return next(e for e in report["skills"] if e["name"] == name)

    def test_actively_used_skill_is_never_a_candidate(self):
        report = self.build()
        gh = self.entry(report, "gh-fix-ci")
        self.assertFalse(gh["prune_eligible"])
        self.assertEqual(gh["claude"]["uses"], 6)
        self.assertEqual(gh["codex"]["counts"]["7"], {"skill_md_reads": 2, "name_mentions": 1})

    def test_kept_skill_zero_everywhere_old_enough_is_flagged_not_demoted(self):
        report = self.build()
        names_in_prune = {c["name"] for c in report["prune_candidates"]}
        self.assertNotIn("typesafe-ai", names_in_prune)  # never demoted through this list
        recheck = next(c for c in report["verdict_recheck"] if c["name"] == "typesafe-ai")
        self.assertEqual(recheck["flag"], "verdict re-record required")
        entry = self.entry(report, "typesafe-ai")
        self.assertTrue(entry["prune_eligible"])
        self.assertEqual(set(entry["evaluated_clients"]), {"claude", "codex"})

    def test_trial_skill_zero_everywhere_old_enough_is_a_prune_candidate(self):
        report = self.build()
        self.assertIn("tdd", {c["name"] for c in report["prune_candidates"]})
        self.assertNotIn("tdd", {c["name"] for c in report["verdict_recheck"]})

    def test_recently_installed_skill_is_never_eligible_despite_zero_usage(self):
        report = self.build()
        entry = self.entry(report, "diagnosing-bugs")
        self.assertEqual(entry["evaluated_clients"], ["claude", "codex"])
        self.assertTrue(entry["zero_on_evaluated_clients"])
        self.assertFalse(entry["prune_eligible"])  # age_days ~= 1, below trial.window_days

    def test_client_not_enabled_is_excluded_but_its_raw_counts_still_show(self):
        report = self.build()
        entry = self.entry(report, "grill-me")
        self.assertEqual(entry["evaluated_clients"], ["claude"])  # codex_enabled is false
        self.assertTrue(entry["prune_eligible"])
        # Transparency: the raw Codex count is still reported even though Codex isn't evaluated.
        self.assertEqual(entry["codex"]["counts"]["30"], {"skill_md_reads": 1, "name_mentions": 0})

    def test_skill_disabled_everywhere_has_no_evaluated_client_and_is_never_eligible(self):
        report = self.build()
        entry = self.entry(report, "semgrep")
        self.assertEqual(entry["evaluated_clients"], [])
        self.assertIsNone(entry["zero_on_evaluated_clients"])
        self.assertFalse(entry["prune_eligible"])
        self.assertNotIn("semgrep", {c["name"] for c in report["prune_candidates"]})
        self.assertNotIn("semgrep", {c["name"] for c in report["verdict_recheck"]})

    def test_unknown_age_is_never_eligible_even_if_zero_everywhere(self):
        report = self.build()
        entry = self.entry(report, "codeql")
        self.assertIsNone(entry["age_days"])
        self.assertTrue(entry["zero_on_evaluated_clients"])
        self.assertFalse(entry["prune_eligible"])

    def test_claude_not_measured_removes_claude_from_evaluation(self):
        report = self.build(claude=None)
        self.assertEqual(report["claude"], {"measured": False, "origin": None, "format": None,
                                             "total_cost_usd": None, "num_turns": None})
        for entry in report["skills"]:
            self.assertEqual(entry["claude"], "not-measured")
            self.assertNotIn("claude", entry["evaluated_clients"])
        # grill-me now has no evaluated client at all (it was claude-only).
        self.assertFalse(self.entry(report, "grill-me")["prune_eligible"])
        # tdd is still a candidate through Codex alone.
        self.assertIn("tdd", {c["name"] for c in report["prune_candidates"]})

    def test_codex_not_measured_removes_codex_from_evaluation(self):
        empty_scan = S.scan_codex_roots([], self.names, now=self.now, windows=self.windows)
        report = self.build(codex_scan=empty_scan)
        self.assertFalse(report["codex"]["measured"])
        for entry in report["skills"]:
            self.assertEqual(entry["codex"], "not-measured")
            self.assertNotIn("codex", entry["evaluated_clients"])
        # typesafe-ai is still flagged through Claude alone.
        self.assertIn("typesafe-ai", {c["name"] for c in report["verdict_recheck"]})

    def test_refused_claude_capture_is_treated_as_not_measured(self):
        refused = S.parse_claude_output((FIXTURES / "skill-doctor-nonzero-cost.json").read_text())
        refused["origin"] = "run"
        report = self.build(claude=refused)
        self.assertEqual(report["claude"]["measured"], False)
        self.assertTrue(report["claude"]["refused"])
        self.assertEqual(report["claude"]["total_cost_usd"], 0.004)

    def test_windows_always_include_trial_window_days(self):
        report = self.build()
        self.assertEqual(report["windows_days"], [7, 30])
        report_narrow = self.build(windows=[14])
        self.assertIn(30, report_narrow["windows_days"])  # unioned in even though only 14 was asked for

    def test_a_window_never_scanned_reads_as_unmeasured_not_a_fake_zero(self):
        partial_scan = S.scan_codex_roots(self.roots, self.names, now=self.now, windows=[7])
        report = self.build(codex_scan=partial_scan, windows=[7, 14])
        entry = self.entry(report, "gh-fix-ci")
        self.assertIsNone(entry["codex"]["counts"]["14"])
        self.assertIsNone(entry["codex"]["counts"]["30"])
        self.assertEqual(entry["codex"]["counts"]["7"], {"skill_md_reads": 2, "name_mentions": 1})
        # tdd's zero-check at the (unscanned) trial window can no longer use Codex.
        tdd = self.entry(report, "tdd")
        self.assertNotIn("codex", tdd["evaluated_clients"])
        self.assertIn("claude", tdd["evaluated_clients"])
        self.assertTrue(tdd["prune_eligible"])  # still eligible through Claude alone

    def test_a_listed_skill_missing_from_the_table_reads_as_unmeasured_not_a_fake_zero(self):
        # Same principle as the Codex window case above, on the Claude side: a manifest skill
        # that IS listed (claude_listing != "off") but has no row in this particular captured
        # table (e.g. it scrolled out of a truncated capture) must never be reported as an
        # observed 0 -- that would claim a measurement that was never taken.
        empty_claude = {"rows": {}, "format": "json", "total_cost_usd": 0, "num_turns": 0}
        report = self.build(claude=empty_claude)
        gh = self.entry(report, "gh-fix-ci")  # claude_listing == "on" in the fixture manifest
        self.assertFalse(gh["claude"]["in_table"])
        self.assertIsNone(gh["claude"]["uses"])
        self.assertNotIn("claude", gh["evaluated_clients"])
        # tdd, also listed "on", falls back to Codex alone for its zero-check.
        tdd = self.entry(report, "tdd")
        self.assertIsNone(tdd["claude"]["uses"])
        self.assertNotIn("claude", tdd["evaluated_clients"])
        self.assertIn("codex", tdd["evaluated_clients"])

    def test_report_contains_no_transcript_or_path_text(self):
        report = self.build()
        dumped = json.dumps(report)
        self.assertNotIn("SKILL.md", dumped)
        self.assertNotIn(str(FIXTURES), dumped)
        self.assertNotIn("REDACTED", dumped)


class RenderTextAndCli(unittest.TestCase):
    def setUp(self):
        self.manifest_path = FIXTURES / "manifest.json"
        self.home = FIXTURES / "fake-home"
        self.claude_file = FIXTURES / "skill-doctor-sample.json"
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.roots = [str(root) for root in materialize_codex_roots(tmp)]

    def run_main(self, extra_args, out=None, claude_file=None):
        args = ["--manifest", str(self.manifest_path), "--now", NOW, "--home", str(self.home),
                "--claude-skill-doctor", str(claude_file or self.claude_file)]
        for root in self.roots:
            args += ["--codex-root", root]
        if out is not None:
            args += ["--out", str(out)]
        args += extra_args
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = S.main(args)
        return code, stdout.getvalue()

    def test_json_output_round_trips_through_main(self):
        code, output = self.run_main(["--json"])
        self.assertEqual(code, 0)
        report = json.loads(output)
        self.assertEqual(report["kind"], "skill_invoke_rate_report")
        self.assertIn("tdd", {c["name"] for c in report["prune_candidates"]})

    def test_main_measures_either_json_output_shape(self):
        # A capture of `claude -p "/skill-doctor" --output-format json` is one result object (`claude --help` 2.1.283:
        # "json" (single result)) or, when verbose is on, the message array (a 2.1.283 binary read, not a live
        # reproduction; see S.parse_claude_output); both yield the same report.
        messages = json.loads(self.claude_file.read_text())
        object_file = Path(self.enterContext(tempfile.TemporaryDirectory())) / "skill-doctor-object.json"
        object_file.write_text(json.dumps(S.find_result_event(messages)), encoding="utf-8")
        reports = {}
        for shape, claude_file in (("array", self.claude_file), ("object", object_file)):
            with self.subTest(shape=shape):
                code, output = self.run_main(["--json"], claude_file=claude_file)
                self.assertEqual(code, 0)
                reports[shape] = json.loads(output)
                self.assertEqual({key: reports[shape]["claude"].get(key) for key in
                                  ("measured", "format", "total_cost_usd", "num_turns")},
                                 {"measured": True, "format": "json", "total_cost_usd": 0, "num_turns": 0})
        self.assertEqual(reports["object"], reports["array"])

    def test_render_text_default_output(self):
        code, output = self.run_main([])
        self.assertEqual(code, 0)
        self.assertIn("PRUNE-CANDIDATE", output)
        self.assertIn("VERDICT-RE-RECORD", output)
        self.assertIn("gh-fix-ci", output)
        self.assertNotIn("SKILL.md", output)

    def test_out_writes_report_outside_the_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "nested" / "report.json"
            # Keep the checkout and output as siblings even when TMPDIR is inside
            # the real worktree. Source: docs.python.org/3/library/unittest.mock.html#patch-object.
            checkout = Path(tmp) / "checkout"
            checkout.mkdir()
            with mock.patch.object(S, "ROOT", checkout):
                code, _ = self.run_main(["--json"], out=out_path)
            self.assertEqual(code, 0)
            written = json.loads(out_path.read_text())
            self.assertEqual(written["kind"], "skill_invoke_rate_report")

    def test_out_inside_the_repository_is_refused(self):
        refused_path = ROOT / "tools" / "skill-usage" / "_should_never_be_written.json"
        try:
            code, _ = self.run_main([], out=refused_path)
            self.assertEqual(code, 2)
            self.assertFalse(refused_path.exists())
        finally:
            if refused_path.exists():
                refused_path.unlink()

    def test_no_codex_root_reports_not_measured(self):
        args = ["--manifest", str(self.manifest_path), "--now", NOW, "--home", str(self.home),
                "--claude-skill-doctor", str(self.claude_file), "--json"]
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = S.main(args)
        self.assertEqual(code, 0)
        report = json.loads(stdout.getvalue())
        self.assertFalse(report["codex"]["measured"])
        for entry in report["skills"]:
            self.assertEqual(entry["codex"], "not-measured")

    def test_invalid_manifest_path_returns_2(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = S.main(["--manifest", "/no/such/manifest.json"])
        self.assertEqual(code, 2)

    def test_invalid_now_returns_2(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = S.main(["--manifest", str(self.manifest_path), "--now", "not-a-timestamp"])
        self.assertEqual(code, 2)

    def test_conflicting_claude_sources_are_rejected_by_argparse(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as ctx:
                S.main(["--manifest", str(self.manifest_path), "--claude-skill-doctor",
                        str(self.claude_file), "--run-skill-doctor"])
        self.assertEqual(ctx.exception.code, 2)

    def test_refusal_on_nonzero_cost_is_visible_in_the_report_not_a_crash(self):
        args = ["--manifest", str(self.manifest_path), "--now", NOW,
                "--claude-skill-doctor", str(FIXTURES / "skill-doctor-nonzero-cost.json"), "--json"]
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = S.main(args)
        self.assertEqual(code, 0)
        report = json.loads(stdout.getvalue())
        self.assertFalse(report["claude"]["measured"])
        self.assertTrue(report["claude"]["refused"])
        self.assertIn("skill_usage:", stderr.getvalue())


LANES_SINCE = "2026-10-20T00:00:00Z"
LANES_UNTIL = "2026-10-21T00:00:00Z"


def materialize_lanes_root(dest: Path) -> Path:
    """tests/fixtures/skill_usage/codex_lanes/*.jsonl.fixture -> dest/codex_lanes/*.jsonl. The rollouts
    are synthetic, shaped from codex-cli 0.157.1 rollout records (session_meta, response_item,
    world_state, event_msg token_count / item_completed), with cwd REDACTED and made-up ids. Each
    copy's mtime is set after the fixture window, as a real rollout's is after its own records, so
    the scan's skip of files not modified since the window start does not depend on today's date."""
    root = dest / "codex_lanes"
    root.mkdir(parents=True, exist_ok=True)
    written = S.parse_iso("2026-10-22T00:00:00Z").timestamp()
    for fixture_path in (FIXTURES / "codex_lanes").glob("*.jsonl.fixture"):
        target = root / fixture_path.with_suffix("").name
        shutil.copyfile(fixture_path, target)
        os.utime(target, (written, written))
    return root


# Codex shell calls in the kernel's measurement.cli_lanes and measurement.proxy (U1 design 6). The record shapes
# follow openai/codex rust-v0.157.1 (36650394): CommandExecutionItem with its snake_case status and exit_code
# (codex-rs/protocol/src/items.rs:199-285), exec end states (core/src/tools/events.rs:529-573: exit 0 is completed,
# any other exit failed, a rejection declined with exit -1) and the unified exec response text, a header of
# sections up to the line `Output:` and then the output (core/src/tools/context.rs:524-575).
CLI_CARRIERS = ("bash", "rtk_proxy", "ctx", "nested")
DECLINED_TEXT = "exec command rejected by user"  # core/src/tools/events.rs:456-458
STACK_280 = ('mcporter --config "${MCPORTER_CONFIG}" call codebase-memory.search_graph'
             ' --args "${GRAPH_QUERY_ARGS}" --output json --no-oauth')  # manifests/stack.json:280


def cli_lane_row(carrier="bash", **counts):
    """One cli_lanes.lanes entry: one call with one invocation on `carrier`, other counters zero."""
    row = {"calls": 1, "invocations": 1, "succeeded": 0, "failed": 0, "not_executed": 0, "unfinished": 0,
           "unknown": 0, "interrupted": 0, "background": 0, "ambiguous": 0, "via_mcporter": 0,
           "by_carrier": {c: int(c == carrier) for c in CLI_CARRIERS}}
    row.update(counts)
    return row


def cli_proxy_row(nested=0):
    """measurement.proxy for one unreviewed rtk proxy call with one invocation (no prefix-rule match)."""
    return {"calls": 1, "acceptance": 0, "exception": 0, "unclassified": 1, "invocations": 1, "nested": nested,
            "in_ctx_code": 0, "prefix_rule_calls": 0, "rule": "command_position", "acceptance_or_exception_share": 0}


def codex_row(kind, payload):
    return {"type": kind, "timestamp": "2026-10-20T02:00:00Z", "payload": payload}


def command_item(key, argv, status, exit_code, output):
    return codex_row("event_msg", {"type": "item_completed", "item": {
        "type": "CommandExecution", "id": key, "command": argv, "source": "unified_exec_startup",
        "status": status, "exit_code": exit_code, "aggregated_output": output}})


def code_mode_command(key, argv, status, exit_code, output):
    """A paginated code-mode `exec` call and the CommandExecution item its JavaScript ran (sandbox-nested)."""
    return [codex_row("response_item", {"type": "custom_tool_call", "call_id": key + "_exec", "name": "exec",
                                        "input": "const r = await tools.exec_command({cmd}); text(r.output)"}),
            command_item(key, argv, status, exit_code, output),
            codex_row("response_item", {"type": "custom_tool_call_output", "call_id": key + "_exec", "output": "done"})]


def exec_command_call(key, cmd, output):
    """A direct exec_command call and its model-visible output; legacy history mode persists no item for it."""
    return [codex_row("response_item", {"type": "function_call", "call_id": key, "name": "exec_command",
                                        "arguments": json.dumps({"cmd": cmd})}),
            codex_row("response_item", {"type": "function_call_output", "call_id": key, "output": output})]


def exec_response(status_line, body):
    """A unified exec response text (context.rs:524-575) with one status section, or none."""
    return "\n".join(["Chunk ID: 4f2a1c", "Wall time: 1.2034 seconds", *([status_line] if status_line else []),
                      "Original token count: 9", "Output:", body])


# PR-A U3, Codex-side measures (items 10a, 10b, 10g, 10e and the Codex normalization; design research-u3.design.md with its
# review). Record shapes follow openai/codex rust-v0.157.1 (36650394c5b38c2990ccf2a3457165ca3e9d9726): SessionMeta
# (codex-rs/protocol/src/protocol.rs:3116-3191) and SubAgentSource::ThreadSpawn (:2901-2916), whose agent_role also reads
# agent_type; a hook's additionalContext as a developer message whose internal_chat_message_metadata_passthrough
# .content_item_kinds is ["hooks.additional_context"] (core/src/context/hook_additional_context.rs:15-22,
# context-fragments/src/fragment.rs:35-53, protocol/src/models.rs:958-993; a kind is a transparent string,
# protocol/src/models/item_metadata.rs:5-7); TurnContextItem (protocol.rs:3293-3350); ThreadSettingsApplied (:1410,
# :2192-2231); SubAgentActivityItem (protocol/src/items.rs:364-370, kind in snake_case at protocol.rs:4382-4390).
HOOK_KIND = "hooks.additional_context"
MARKER = S.DEFAULT_LANES_MARKER
CATALOG = "<skills_instructions>\n- tdd (file: /home/example/.agents/skills/tdd/SKILL.md)\n</skills_instructions>"
SPLIT = ("marker", "marker_inherited", "marker_injected", "marker_injected_kinds")
NO_HOOKS = {"inserted": 0, "with_marker": 0, "inherited": 0, "inherited_with_marker": 0}
TOKENS = {"type": "token_count", "info": {"last_token_usage": {"input_tokens": 100}}}


def pending(commit):
    """A U3 failing-first test that a later design commit makes pass; that commit removes the marker. unittest reports an
    unexpected success as a failure, so a marker cannot outlive its fix. The assertions read through .get() so that a
    missing field fails as an assertion, not as an error that expectedFailure would also absorb."""
    del commit  # documentation only: the design commit that lifts the marker
    return unittest.expectedFailure


def u3_row(kind, payload, at="2026-10-20T02:00:00Z", ordinal=None):
    row = {"timestamp": at, "type": kind, "payload": payload}
    if ordinal is not None:
        row["ordinal"] = ordinal
    return row


def developer(*texts, kinds=None):
    """A developer message with one input_text item per text; kinds, when given, is its content_item_kinds metadata."""
    payload = {"type": "message", "role": "developer",
               "content": [{"type": "input_text", "text": text} for text in texts]}
    if kinds is not None:
        payload["internal_chat_message_metadata_passthrough"] = {"content_item_kinds": kinds}
    return payload


def write_rollouts(root: Path, rollouts: dict) -> Path:
    """{file name: records} -> rollout files under root, each with an mtime after the lanes window, as
    materialize_lanes_root sets it, so the scan's skip of files not modified since the window start keeps them."""
    root.mkdir(parents=True, exist_ok=True)
    written = S.parse_iso("2026-10-22T00:00:00Z").timestamp()
    for name, records in rollouts.items():
        path = root / name
        path.write_text("".join(json.dumps(record) + "\n" for record in records))
        os.utime(path, (written, written))
    return root


def published_keys(value):
    """Every dict key of a published report, recursively."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from published_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from published_keys(item)


def assert_id_free_report(case, published, secrets):
    """No private join key (a key starting with an underscore) and no secret value (a thread id, call id, nickname, agent
    path, spawn or follow-up message, the fixture root) anywhere in a published report."""
    case.assertEqual([key for key in published_keys(published) if str(key).startswith("_")], [])
    text = json.dumps(published)
    case.assertEqual([secret for secret in secrets if secret in text], [])


class CodexLanes(unittest.TestCase):
    def test_measurement_uses_own_outputs_and_differences_cumulative_usage(self):
        def record(kind, payload, ordinal):
            return {"type": kind, "timestamp": "2026-10-20T02:01:00Z", "payload": payload, "ordinal": ordinal}
        def tokens(total, out=0):
            return {"type": "token_count", "info": {"total_token_usage": {
                "input_tokens": total, "cached_input_tokens": 20, "output_tokens": out,
                "reasoning_output_tokens": 0, "total_tokens": total + out}}}
        rows = [record("session_meta", {"source": {"subagent": {}}, "subagent_history_start_ordinal": 5}, 0),
                record("event_msg", tokens(100), 2),
                record("response_item", {"type": "function_call", "call_id": "parent", "name": "exec_command", "arguments": '{"cmd":"ls"}'}, 3),
                record("response_item", {"type": "function_call_output", "call_id": "parent", "output": "p" * 9000}, 4),
                record("event_msg", {"type": "task_started", "turn_id": "turn"}, 5),
                record("response_item", {"type": "function_call", "call_id": "child", "name": "exec_command", "arguments": '{"cmd":"rtk proxy cat a"}'}, 6),
                record("response_item", {"type": "function_call_output", "call_id": "child", "output": "c" * 6000}, 7),
                record("event_msg", tokens(110, 3), 8), record("event_msg", tokens(110, 3), 9),
                record("event_msg", {"type": "turn_aborted"}, 10)]
        got = S.measure_codex_records(rows, since=self.since, until=self.until)
        self.assertEqual(got["m3"]["results"], 1)
        self.assertEqual(got["by_carrier"]["rtk_proxy"]["bytes"], 6000)
        self.assertEqual(got["provider_usage"]["totals"]["input_tokens"], 10)
        self.assertEqual(got["provider_usage"]["totals"]["output_tokens"], 3)
        self.assertEqual(got["provider_usage"]["attempts"][0]["state"], "interrupted")
        self.assertFalse(got["provider_usage"]["complete"])
        self.assertEqual(got["provider_usage"]["duplicate_snapshots"], 1)
        self.assertNotIn("turn_id", json.dumps(got))

    def test_measurement_includes_ctx_nested_fetches_from_item_arguments(self):
        rows = []
        for i in range(20):
            tool = "ctx_fetch_and_index" if i == 0 else "ctx_execute"
            args = {"url": "https://example.org"} if i == 0 else {"language": "shell", "code": "curl https://example.org"}
            rows.append({"type": "event_msg", "timestamp": "2026-10-20T02:00:00Z", "payload": {
                "type": "item_completed", "item": {"id": str(i), "type": "McpToolCall", "server": "context-mode",
                    "tool": tool, "arguments": args, "result": {"content": [{"type": "text", "text": "ok"}]}}}})
        got = S.measure_codex_records(rows, since=self.since, until=self.until)
        self.assertEqual(got["m4"]["remote_fetches"], 20)
        self.assertEqual(got["m4"]["routed_share"], .05)
        self.assertEqual(got["m5"]["results"], 20)

    def test_lane_report_exposes_sanitized_per_actor_metrics(self):
        report = self.scan()
        self.assertEqual(len(report["actors"]), report["sessions_in_window"])
        self.assertIn("m3", report["actors"][0]["measurement"])
        self.assertIn("provider_usage", report["groups"]["workers"]["measurement"])
        for actor in report["actors"]:
            self.assertNotIn("usage", actor["measurement"])
        self.assertNotIn(str(self.root), json.dumps(report))

    def test_code_mode_fixture_keeps_nested_operations_out_of_context_bytes(self):
        path = next(self.root.glob("rollout-*-lanes-worker.jsonl"))
        rows = []
        for line in path.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass  # Fixture intentionally includes one malformed row.
        got = S.measure_codex_records(rows, since=self.since, until=self.until)
        self.assertEqual(got["orphan_results"], 0)
        self.assertEqual(got["mcp_states"]["context-mode"],
                         {"attempted": 3, "succeeded": 2, "failed": 1, "unfinished": 0})
        self.assertEqual(got["mcp_states"]["qmd"]["succeeded"], 1)
        self.assertEqual(got["calls_without_result"], 3)  # exec, spawn_agent, direct shell
        self.assertEqual(got["sandbox_operations"], 10)
        self.assertEqual(got["m4"]["ctx_sandbox_fetch"], 1)
        # The retained fixture has no exec output; add one synthetic model-visible
        # return and large sandbox results to exercise the actual byte boundary.
        exec_key = next(r["payload"]["call_id"] for r in rows
                        if r.get("payload", {}).get("type") == "custom_tool_call")
        boundary = next(i for i, r in enumerate(rows)
                        if r.get("payload", {}).get("name") == "spawn_agent")
        rows.insert(boundary, {"type": "response_item", "timestamp": "2026-10-20T01:05:10Z",
                               "payload": {"type": "custom_tool_call_output", "call_id": exec_key,
                                           "output": "visible summary"}})
        for row in rows[:boundary]:
            item = row.get("payload", {}).get("item", {})
            if item.get("type") == "CommandExecution":
                item["aggregated_output"] = "x" * 6000
            if item.get("type") == "McpToolCall":
                item["result"] = {"content": [{"type": "text", "text": "x" * 6000}]}
        got = S.measure_codex_records(rows, since=self.since, until=self.until)
        self.assertEqual(got["orphan_results"], 0)
        self.assertEqual(got["m3"]["bytes"], len("visible summary"))
        self.assertEqual(got["m3"]["results"], 1)
        self.assertEqual(got["m5"]["results"], 0)
        self.assertEqual(got["calls_without_result"], 2)

    def test_local_shell_and_custom_calls_pair_with_native_outputs(self):
        def row(payload):
            return {"type": "response_item", "timestamp": "2026-10-20T02:00:00Z", "payload": payload}
        rows = [row({"type": "local_shell_call", "call_id": "shell", "action": {
                    "type": "exec", "command": ["bash", "-lc", "curl https://example.org"]}}),
                row({"type": "function_call_output", "call_id": "shell", "output": "done"}),
                row({"type": "custom_tool_call", "call_id": "custom", "name": "apply_patch", "input": "patch"}),
                row({"type": "custom_tool_call_output", "call_id": "custom", "output": "ok"})]
        got = S.measure_codex_records(rows)
        self.assertEqual(got["orphan_results"], 0)
        self.assertEqual(got["calls_without_result"], 0)
        self.assertTrue(got["bytes_complete"])
        self.assertEqual(got["m3"]["bytes"], 6)
        self.assertEqual(got["by_carrier"]["bash"]["bytes"], 4)
        self.assertEqual(got["m4"]["shell_fetch"], 1)

    def test_sidecar_binding_counts_distinguish_changed_rollouts(self):
        import hashlib
        path = next(self.root.glob("rollout-*-lanes-worker.jsonl"))
        records = [{"transcript_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "tool_use_id": "reviewed", "proxy_purpose": "acceptance", "witness": "check"},
                   {"transcript_sha256": "0" * 64, "tool_use_id": "stale",
                    "proxy_purpose": "acceptance", "witness": "check"}]
        def scan():
            return S.scan_codex_lanes([self.root], self.manifest, since=self.since, until=self.until,
                                     marker=S.DEFAULT_LANES_MARKER, exception_records=records)
        self.assertEqual(scan()["sidecar_records"], {"bound": 1, "unbound": 1})
        path.write_text(path.read_text() + "\n")
        self.assertEqual(scan()["sidecar_records"], {"bound": 0, "unbound": 2})

    def test_measurement_namespace_and_failed_terminal_event(self):
        def row(kind, payload):
            return {"type": kind, "timestamp": "2026-10-20T02:00:00Z", "payload": payload}
        rows = [row("response_item", {"type": "function_call", "call_id": "c", "namespace": "mcp__context_mode",
                "name": "ctx_execute", "arguments": json.dumps({"language": "shell", "code": "curl https://example.org"})}),
                row("response_item", {"type": "function_call_output", "call_id": "c", "output": "x" * 6000}),
                row("event_msg", {"type": "item_completed", "item": {"type": "McpToolCall", "id": "c",
                    "server": "context_mode", "tool": "ctx_execute", "arguments": {"language": "shell", "code": "curl https://example.org"}}}),
                row("event_msg", {"type": "task_started"}),
                row("event_msg", {"type": "token_count", "info": {"total_token_usage": dict.fromkeys(S.CODEX_COUNTERS, 10)}}),
                row("event_msg", {"type": "task_complete", "error": {"message": "failed"}})]
        got = S.measure_codex_records(rows, since=self.since, until=self.until)
        self.assertEqual(got["m5"]["large_results"], 1)
        self.assertEqual(got["m4"]["ctx_sandbox_fetch"], 1)
        self.assertFalse(got["provider_usage"]["complete"])
        self.assertEqual(got["provider_usage"]["attempts"][0]["state"], "failed")

    def test_usage_missing_parent_baseline_and_counter_regression_stay_unknown(self):
        def row(kind, payload, ordinal=10):
            return {"type": kind, "timestamp": "2026-10-20T02:00:00Z", "payload": payload, "ordinal": ordinal}
        def snapshot(value):
            return row("event_msg", {"type": "token_count", "info": {"total_token_usage": dict.fromkeys(S.CODEX_COUNTERS, value)}})
        rows = [row("session_meta", {"subagent_history_start_ordinal": 5}, 0),
                row("event_msg", {"type": "task_started"}), snapshot(100),
                row("event_msg", {"type": "task_complete"})]
        got = S.measure_codex_records(rows)["provider_usage"]
        self.assertIsNone(got["totals"]["input_tokens"])
        self.assertFalse(got["complete"])
        regressed = S.measure_codex_records([row("event_msg", {"type": "task_started"}), snapshot(100), snapshot(90),
                                            row("event_msg", {"type": "task_complete"})])["provider_usage"]
        self.assertIsNone(regressed["totals"]["input_tokens"])
        self.assertFalse(regressed["complete"])

    def test_codex_mcp_failure_uses_native_item_state_with_response_bytes(self):
        rows = [{"type": "response_item", "timestamp": "2026-10-20T02:00:00Z", "payload": {
                    "type": "function_call", "call_id": "c", "namespace": "mcp__qmd", "name": "search", "arguments": "{}"}},
                {"type": "response_item", "timestamp": "2026-10-20T02:00:01Z", "payload": {
                    "type": "function_call_output", "call_id": "c", "output": "failed"}},
                {"type": "event_msg", "timestamp": "2026-10-20T02:00:01Z", "payload": {
                    "type": "item_completed", "item": {"id": "c", "type": "McpToolCall", "server": "qmd", "tool": "search", "status": "failed"}}}]
        got = S.measure_codex_records(rows)
        self.assertEqual(got["mcp_states"]["qmd"]["failed"], 1)
        self.assertEqual(got["m3"]["bytes"], 6)

    def test_native_mcp_status_without_result_payload(self):
        rows = [{"type": "event_msg", "timestamp": "2026-10-20T02:00:00Z", "payload": {
                    "type": "item_completed", "item": {"type": "McpToolCall", "id": str(i),
                        "server": "qmd", "tool": "query", "status": state, "result": None}}}
                for i, state in enumerate(["completed", "failed", "inProgress"])]
        got = S.measure_codex_records(rows)
        self.assertEqual(got["mcp_states"]["qmd"],
                         {"attempted": 3, "succeeded": 1, "failed": 1, "unfinished": 1})
        self.assertEqual(got["unknown_result_bytes"], 0)
        self.assertEqual(got["calls_without_result"], 3)
        self.assertFalse(got["bytes_complete"])

    def assert_id_free(self, measured):
        text = json.dumps(measured)
        for secret in ("call_priv", DECLINED_TEXT, "pytest", "search_graph", "GRAPH_QUERY_ARGS", "notes.md"):
            self.assertNotIn(secret, text)

    @unittest.skipUnless(PARSER_INSTALLED, "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
    def test_codex_shell_call_states_reach_cli_lanes(self):
        # U1 design 6 (i)-(vii). A call's state comes from its persisted CommandExecution status when there is one:
        # declined is failed and not executed (events.rs:562-573). With no item state, a Bash-mapped call's output
        # is read by its unified exec header (context.rs:534-540): an exit code of 0 is success, another failure,
        # and a running process or a missing header leaves the state unknown, since a rollout output never
        # carries the success flag (protocol/src/models.rs:2173-2182).
        declined_direct = exec_command_call("call_priv_iii_direct", "qmd search x", DECLINED_TEXT)
        declined_direct.insert(1, command_item("call_priv_iii_direct", ["bash", "-lc", "qmd search x"],
                                               "declined", -1, DECLINED_TEXT))
        local_shell = [codex_row("response_item", {"type": "local_shell_call", "call_id": "call_priv_vii",
                                                   "status": "completed", "action": {
                                                       "type": "exec", "command": ["bash", "-lc", STACK_280]}}),
                       codex_row("response_item", {"type": "function_call_output", "call_id": "call_priv_vii",
                                                   "output": "[]"})]
        cases = {
            "(i) code mode, completed": (
                code_mode_command("call_priv_i", ["bash", "-lc", "cd repo && rtk proxy pytest -q"], "completed", 0,
                                  "4 passed"),
                {"rtk_proxy": cli_lane_row("nested", succeeded=1, ambiguous=1)}, {}, cli_proxy_row(nested=1)),
            "(ii) code mode, failed": (
                code_mode_command("call_priv_ii", ["bash", "-c", "qmd search x"], "failed", 1, "no index"),
                {"qmd": cli_lane_row("nested", failed=1)}, {}, None),
            "(iii) code mode, declined": (
                code_mode_command("call_priv_iii", ["bash", "-lc", "qmd search x"], "declined", -1, DECLINED_TEXT),
                {"qmd": cli_lane_row("nested", failed=1, not_executed=1)}, {}, None),
            "(iii) direct call, declined item": (
                declined_direct, {"qmd": cli_lane_row(failed=1, not_executed=1)}, {}, None),
            "(iv) legacy exec_command, exit header": (
                exec_command_call("call_priv_iv", "FOO=1 rtk proxy pytest",
                                  exec_response("Process exited with code 1", "1 failed, 3 passed")),
                {"rtk_proxy": cli_lane_row("rtk_proxy", failed=1)}, {}, cli_proxy_row()),
            "(v) legacy exec_command, running header": (
                exec_command_call("call_priv_v", "qmd search x",
                                  exec_response("Process running with session ID 3", "searching")),
                {"qmd": cli_lane_row(unknown=1)}, {}, None),
            "(vi) no header and no item": (
                exec_command_call("call_priv_vi", "qmd search x", "notes.md:3: qmd search x"),
                {"qmd": cli_lane_row(unknown=1)}, {}, None),
            "(vii) local shell call, stack.json:280": (
                local_shell, {"codebase-memory-mcp": cli_lane_row(unknown=1, via_mcporter=1)},
                {"codebase-memory": {"calls": 1, "succeeded": 0, "failed": 0, "not_executed": 0, "unfinished": 0,
                                     "unknown": 1, "interrupted": 0}}, None),
        }
        for name, (rows, lanes, downstream, proxy) in cases.items():
            with self.subTest(case=name):
                got = S.measure_codex_records(rows, since=self.since, until=self.until)
                self.assertEqual(got["cli_lanes"]["lanes"], lanes)
                self.assertEqual(got["cli_lanes"]["mcporter_downstream"], downstream)
                if proxy:
                    self.assertEqual(got["proxy"], proxy)
                self.assert_id_free(got)

    @unittest.skipUnless(PARSER_INSTALLED, "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
    def test_codex_shell_state_controls(self):
        # Must-stay controls: an exit 0 header succeeds; only the header before `Output:` is read, never the output;
        # a persisted item state wins over the output text, as a paginated item arrives when the command ends.
        cases = {
            "exit 0 header": (
                exec_command_call("call_priv_c1", "qmd search x",
                                  exec_response("Process exited with code 0", "notes.md")),
                cli_lane_row(succeeded=1)),
            "exit line in the output": (
                exec_command_call("call_priv_c2", "qmd search x",
                                  exec_response("Process exited with code 0", "Process exited with code 1")),
                cli_lane_row(succeeded=1)),
            "completed item beats a running header": (
                exec_command_call("call_priv_c3", "qmd search x",
                                  exec_response("Process running with session ID 3", "searching"))
                + [command_item("call_priv_c3", ["bash", "-lc", "qmd search x"], "completed", 0, "notes.md")],
                cli_lane_row(succeeded=1)),
            "failed item with its exit header": (
                exec_command_call("call_priv_c4", "qmd search x",
                                  exec_response("Process exited with code 1", "no index"))
                + [command_item("call_priv_c4", ["bash", "-lc", "qmd search x"], "failed", 1, "no index")],
                cli_lane_row(failed=1)),
        }
        for name, (rows, row) in cases.items():
            with self.subTest(case=name):
                got = S.measure_codex_records(rows, since=self.since, until=self.until)
                self.assertEqual(got["cli_lanes"]["lanes"], {"qmd": row})
                self.assert_id_free(got)

    def test_exec_header_state_reads_only_the_pinned_header(self):
        # context.rs:524-548 sections before "Output:"; the exit code is an i32 written in decimal. A running line
        # wins over an exit line (write_stdin can report both, unified_exec/process_manager.rs:1066-1071).
        unknown, ok, failed = (False, "unknown"), (False, None), (True, None)
        cases = {
            "exit 0": (exec_response("Process exited with code 0", "x"), ok),
            "exit 1": (exec_response("Process exited with code 1", "x"), failed),
            "exit -1": (exec_response("Process exited with code -1", "x"), failed),
            "no chunk id": ("Wall time: 0.0100 seconds\nProcess exited with code 0\nOutput:\nx", ok),
            "running": (exec_response("Process running with session ID 3", "x"), unknown),
            "running and exit": ("Chunk ID: a\nWall time: 1.0 seconds\nProcess exited with code 0\n"
                                 "Process running with session ID 3\nOutput:\nx", unknown),
            "neither line": (exec_response(None, "x"), unknown),
            "exit only in the output": (exec_response(None, "Process exited with code 0"), unknown),
            "underscore digits": (exec_response("Process exited with code 1_0", "x"), unknown),
            "plus sign": (exec_response("Process exited with code +1", "x"), unknown),
            "padded": (exec_response("Process exited with code  1", "x"), unknown),
            "non-ASCII digit": (exec_response("Process exited with code ²", "x"), unknown),
            "no Output line within the sections": ("Wall time: 1 seconds\n" + "Original token count: 1\n" * 5
                                                   + "Process exited with code 0\nOutput:\nx", unknown),
            "no header": ("Process exited with code 0\nOutput:\nx", unknown),
            "content items": ([{"type": "input_text", "text": exec_response("Process exited with code 2", "x")}],
                              failed),
            "no output": (None, unknown),
        }
        for name, (output, expected) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(S.exec_header_state(output), expected)

    def test_exec_header_state_bounds_the_exit_code_digits(self):
        # D6 (GPT-6 #12): int() of a digit string over CPython's conversion limit (4,300 digits) raised ValueError, so one
        # malformed header stopped the whole scan. The code is an i32 written in decimal (context.rs:534-540), up to 10
        # digits with its sign; the brief's nine-digit bound (D6) makes a header with more than 9 digits read unknown,
        # never succeeded and without raising (a valid ten-digit i32 code also reads unknown: a documented limit).
        unknown = (False, "unknown")
        self.assertEqual(S.exec_header_state("Wall time: 0.01 seconds\nProcess exited with code " + "9" * 5000 + "\nOutput:\n"),
                         unknown)  # GPT-6 #12, verbatim
        cases = {
            "9 digits": (exec_response("Process exited with code 999999999", "x"), (True, None)),
            "negative, 9 digits": (exec_response("Process exited with code -999999999", "x"), (True, None)),
            "10 digits": (exec_response("Process exited with code 1000000000", "x"), unknown),
            "negative, 10 digits": (exec_response("Process exited with code -1000000000", "x"), unknown),
            "zero padded to 10 digits": (exec_response("Process exited with code 0000000000", "x"), unknown),
            "4,301 digits": (exec_response("Process exited with code " + "1" * 4301, "x"), unknown),
            "5,000 digits, negative": (exec_response("Process exited with code -" + "1" * 5000, "x"), unknown),
        }
        for name, (output, expected) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(S.exec_header_state(output), expected)

    def test_shell_script_quotes_argv_elements(self):
        # D6 (GPT-6 #11): an argv array is one command, so each element is quoted (shlex.join) and a metacharacter inside
        # one element stays data. Only a shell's `-c`/`-lc` script argument is shell text (openai/codex rust-v0.157.1
        # codex-rs/core/src/shell.rs: [shell, -lc, script]); `-c` of any other program is one of its arguments.
        self.assertEqual(S.shell_script(["echo", "qmd; rtk proxy qmd status"]), "echo 'qmd; rtk proxy qmd status'")
        self.assertEqual(S.shell_script(["echo", "-c", "qmd; rtk proxy qmd status"]), "echo -c 'qmd; rtk proxy qmd status'")
        self.assertEqual(S.shell_script(["grep", "-n", "a b", "notes.md"]), "grep -n 'a b' notes.md")
        self.assertEqual(S.shell_script(["ls", "-la"]), "ls -la")
        self.assertEqual(S.shell_script(["bash", "-lc", "qmd search x; ls"]), "qmd search x; ls")
        self.assertEqual(S.shell_script(["/usr/bin/zsh", "-c", "rtk proxy pytest"]), "rtk proxy pytest")
        self.assertEqual(S.shell_script("qmd search x"), "qmd search x")
        self.assertEqual(S.shell_script([]), "")

    @unittest.skipUnless(PARSER_INSTALLED, "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
    def test_argv_metacharacters_stay_data_in_the_codex_bridge(self):
        # D6 (GPT-6 #11, verbatim first case): the bridge flattened argv with spaces, so ["echo", "qmd; rtk proxy qmd status"]
        # read as two commands and counted one qmd call and one rtk proxy call that never ran.
        cases = {
            "local shell call": [
                codex_row("response_item", {"type": "local_shell_call", "call_id": "call_priv_argv", "status": "completed",
                                            "action": {"type": "exec", "command": ["echo", "qmd; rtk proxy qmd status"]}}),
                codex_row("response_item", {"type": "function_call_output", "call_id": "call_priv_argv", "output": "ok"})],
            "code mode item": code_mode_command("call_priv_argv2", ["echo", "qmd; rtk proxy qmd status"], "completed", 0, "ok"),
            "-c of a program that is not a shell": code_mode_command(
                "call_priv_argv3", ["echo", "-c", "qmd; rtk proxy qmd status"], "completed", 0, "ok"),
        }
        for name, rows in cases.items():
            with self.subTest(case=name):
                got = S.measure_codex_records(rows, since=self.since, until=self.until)
                self.assertEqual(got["proxy"]["calls"], 0)
                self.assertEqual(got["cli_lanes"]["lanes"], {})

    @unittest.skipUnless(PARSER_INSTALLED, "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
    def test_bridge_loads_the_shell_parser_and_records_it(self):
        # D1: the Node bridge awaits loadShellParser, as the kernel's CLI does, so its measurement counts lanes and records
        # the parser (versions and the two wasm sha256 values, no path).
        got = S.measure_codex_records(code_mode_command("call_priv_p", ["bash", "-lc", "qmd search x"], "completed", 0, "ok"),
                                      since=self.since, until=self.until)
        self.assertEqual(got["cli_lanes"]["status"], "measured")
        self.assertEqual(got["cli_lanes"]["parser"]["versions"], {"tree_sitter_bash": "0.25.1", "web_tree_sitter": "0.27.0"})
        self.assertEqual(sorted(got["cli_lanes"]["parser"]["wasm_sha256"]), ["tree_sitter_bash", "web_tree_sitter"])
        self.assertEqual(got["proxy"]["rule"], "command_position")
        self.assertEqual(got["cli_lanes"]["lanes"]["qmd"]["calls"], 1)
        self.assertNotIn(str(PARSER_DIR), json.dumps(got))

    def test_bridge_fails_closed_when_the_shell_parser_is_not_installed(self):
        # D1: with no parser the bridge's measurement says so and keeps the prefix rule for rtk proxy; it never falls back to
        # the text scanners for lane counting (M4 stays text-based and unchanged).
        rows = (code_mode_command("call_priv_q", ["bash", "-lc", "qmd search x"], "completed", 0, "ok")
                + exec_command_call("call_priv_r", "rtk proxy pytest", exec_response("Process exited with code 0", "ok"))
                + exec_command_call("call_priv_s", "curl https://example.org", exec_response("Process exited with code 0", "ok")))
        with mock.patch.dict(os.environ, {"CHILD_USAGE_SHELL_PARSER": str(self.root / "no-such-install")}):
            got = S.measure_codex_records(rows, since=self.since, until=self.until)
        self.assertEqual(got["cli_lanes"], {"status": "parser_unavailable", "reason": "not_installed"})
        self.assertEqual((got["proxy"]["rule"], got["proxy"]["calls"], got["proxy"]["invocations"]), ("prefix_fallback", 1, None))
        self.assertEqual(got["m4"]["shell_fetch"], 1)
        self.assert_id_free(got)

    @unittest.skipUnless(PARSER_INSTALLED, "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
    def test_codex_aggregate_passes_cli_lanes_and_proxy_through(self):
        # aggregate_codex_lanes hands the per-actor measurements to the kernel's aggregateMeasurements, which sums
        # cli_lanes and proxy and adds actors_with_success per lane.
        sessions = []
        for rows in (code_mode_command("call_priv_a", ["bash", "-lc", "cd repo && rtk proxy pytest -q"],
                                       "completed", 0, "4 passed"),
                     code_mode_command("call_priv_b", ["bash", "-c", "qmd search x"], "failed", 1, "no index")):
            session = S._new_lanes_session()
            session["measurement"] = S.measure_codex_records(rows, since=self.since, until=self.until)
            sessions.append(session)
        got = S.aggregate_codex_lanes(sessions)["measurement"]
        self.assertEqual(got["cli_lanes"]["lanes"], {
            "rtk_proxy": {**cli_lane_row("nested", succeeded=1, ambiguous=1), "actors_with_success": 1},
            "qmd": {**cli_lane_row("nested", failed=1), "actors_with_success": 0}})
        self.assertEqual(got["proxy"], cli_proxy_row(nested=1))
        self.assertIn("provider_usage", got)
        self.assert_id_free(got)

    def setUp(self):
        self.manifest = load_fixture_manifest()
        self.names = fixture_names()
        self.codex_off = [s["name"] for s in self.manifest["skills"] if s["codex_enabled"] is False]
        self.codex_on = [s["name"] for s in self.manifest["skills"] if s["codex_enabled"] is True]
        self.since, self.until = S.parse_iso(LANES_SINCE), S.parse_iso(LANES_UNTIL)
        self.root = materialize_lanes_root(Path(self.enterContext(tempfile.TemporaryDirectory())))

    def session(self, stem: str) -> tuple[dict, int, int]:
        path = next(self.root.glob(f"rollout-*-lanes-{stem}.jsonl"))
        return S.scan_lanes_file(path, self.names, since=self.since, until=self.until,
                                 marker=S.DEFAULT_LANES_MARKER, codex_off=self.codex_off,
                                 codex_on=self.codex_on)

    def scan(self) -> dict:
        return S.scan_codex_lanes([self.root], self.manifest, since=self.since, until=self.until,
                                  marker=S.DEFAULT_LANES_MARKER)

    def test_worker_session_counts_each_lane(self):
        session, parse_errors, untimed = self.session("worker")
        self.assertEqual((session["kind"], session["originator"]), ("exec", "codex_exec"))
        self.assertEqual(session["mcp_calls"], {"context-mode": 3, "qmd": 1})
        self.assertEqual(session["mcp_failed"], {"context-mode": 1})
        self.assertEqual((session["shell_calls"], session["rtk_prefixed"]), (5, 1))
        # The quoted `echo 'curl ...'` command is not a fetch.
        self.assertEqual(session["fetch"], {"web_open_page": 1, "web_search": 1, "web_other": 0,
                                            "ctx_fetch_and_index": 1, "shell_curl_wget": 1,
                                            "shell_curl_wget_loopback": 1})
        # 5 shell + 4 MCP + 3 extensions (clock.sleep included) + 1 file change + 1 spawn_agent; the
        # exec_command function_call shares its call_id with a CommandExecution item: one call.
        self.assertEqual(session["tool_calls"], 14)
        self.assertEqual(session["function_calls"], {"exec_command": 1, "spawn_agent": 1})
        self.assertEqual(session["skill_md_reads"], {"tdd": 1})  # the call payload, not the item
        self.assertTrue(session["marker"])
        self.assertEqual(S.user_config_state(session), "applied")
        self.assertEqual(session["first_prompt_tokens"], 19000)  # first token_count with usage
        self.assertTrue(session["ran_past_window_end"])  # the serena call at until is not counted
        self.assertEqual((parse_errors, untimed), (1, 1))

    def test_subagent_rollout_takes_its_own_meta_not_the_repeated_parent_meta(self):
        session, _, _ = self.session("subagent")
        self.assertEqual(session["kind"], "subagent")
        self.assertTrue(session["marker"])  # inherited developer context is part of its prompt
        # PR-A 10a: that marker is inherited (ordinal 2, below the start ordinal 4), never injected by this child.
        self.assertEqual({key: session.get(key) for key in SPLIT},
                         {"marker": True, "marker_inherited": True, "marker_injected": False, "marker_injected_kinds": {}})
        self.assertEqual(S.user_config_state(session), "applied")
        self.assertEqual(session["first_prompt_tokens"], 21000)

    def test_records_copied_from_the_parent_are_not_the_subagents_calls(self):
        # Ordinals below subagent_history_start_ordinal (4) hold the parent's exec_command read.
        session, _, _ = self.session("subagent")
        self.assertEqual(session["skill_md_reads"], {})
        self.assertEqual(session["function_calls"], {})
        self.assertEqual(session["tool_calls"], 2)  # its own MCP call and shell command

    def test_user_config_is_ignored_when_a_codex_disabled_skill_is_in_the_catalog(self):
        isolated, _, _ = self.session("isolated")
        self.assertEqual(S.user_config_state(isolated), "ignored")
        self.assertFalse(isolated["marker"])
        self.assertEqual(S.user_config_state(self.session("nocatalog")[0]), "unknown")

    def test_window_counts_only_records_inside_and_keeps_session_properties(self):
        straddle, _, _ = self.session("straddle")
        self.assertTrue(straddle["started_before_window"])
        self.assertEqual(straddle["mcp_calls"], {"serena": 1})  # the 23:30 call is before since
        self.assertIsNone(straddle["first_prompt_tokens"])  # its first request is before since
        self.assertEqual(S.user_config_state(straddle), "applied")  # catalog read before since
        self.assertFalse(self.session("before")[0]["in_window"])

    def lanes_between(self, stem: str, since, until) -> dict:
        path = next(self.root.glob(f"rollout-*-lanes-{stem}.jsonl"))
        return S.scan_lanes_file(path, self.names, since=since, until=until, marker=S.DEFAULT_LANES_MARKER,
                                 codex_off=self.codex_off, codex_on=self.codex_on)[0]

    def test_a_call_split_between_request_and_completion_counts_in_one_window(self):
        # Review finding (GPT-6, 2026-09-26): exec_command call item_16 is requested at 01:05:40 and
        # completes at 01:05:41. Split between the two, it counted in both windows (14 + 1) but once
        # in the whole window. It counts in the window of its first record, the request; its shell
        # lane comes from the item, in the item's window.
        split = S.parse_iso("2026-10-20T01:05:40.500Z")
        whole = self.lanes_between("worker", self.since, self.until)
        early = self.lanes_between("worker", self.since, split)
        late = self.lanes_between("worker", split, self.until)
        self.assertEqual((whole["tool_calls"], early["tool_calls"], late["tool_calls"]), (14, 14, 0))
        self.assertEqual((whole["shell_calls"], early["shell_calls"], late["shell_calls"]), (5, 4, 1))

    def test_adjacent_windows_add_up_at_every_split(self):
        # Each additive counter over [since, until) is the sum of the same counter over
        # [since, split) and [split, until), for a split between any two record times.
        additive = ("tool_calls", "shell_calls", "rtk_prefixed", "file_changes")
        keyed = ("mcp_calls", "mcp_failed", "fetch", "function_calls", "skill_md_reads")
        for path in sorted(self.root.glob("rollout-*-lanes-*.jsonl")):
            stem = path.name.split("-lanes-")[1].removesuffix(".jsonl")
            times = set()
            for line in path.read_text().splitlines():
                try:
                    times.add(S.parse_iso(json.loads(line)["timestamp"]))
                except (ValueError, KeyError, TypeError, AttributeError):
                    continue
            edges = [self.since, *sorted(t for t in times if self.since < t < self.until), self.until]
            whole = self.lanes_between(stem, self.since, self.until)
            for split in (a + (b - a) / 2 for a, b in zip(edges, edges[1:])):
                early = self.lanes_between(stem, self.since, split)
                late = self.lanes_between(stem, split, self.until)
                for key in additive:
                    self.assertEqual(early[key] + late[key], whole[key], (stem, split.isoformat(), key))
                for key in keyed:
                    self.assertEqual(collections.Counter(early[key]) + collections.Counter(late[key]),
                                     +collections.Counter(whole[key]), (stem, split.isoformat(), key))

    def test_report_keeps_negative_controls_out_of_workers(self):
        scan = self.scan()
        self.assertEqual(scan["sessions_in_window"], 5)
        self.assertEqual({k: scan["user_config"][k] for k in ("applied", "ignored", "unknown")},
                         {"applied": 3, "ignored": 1, "unknown": 1})
        groups = scan["groups"]
        self.assertEqual(groups["workers"]["sessions"], 3)
        self.assertNotIn("codex", groups["workers"]["mcp_calls"])
        self.assertEqual(groups["negative_controls"]["mcp_calls"], {"codex": 1})
        self.assertEqual(groups["negative_controls"]["marker_sessions"], 0)
        self.assertEqual(groups["unclassified"]["rtk_prefixed_shell_calls"], 1)
        self.assertEqual({kind: g["sessions"] for kind, g in groups["workers_by_kind"].items()},
                         {"exec": 2, "subagent": 1})
        self.assertEqual((scan["sessions_started_before_window"], scan["sessions_ran_past_window_end"]),
                         (1, 1))
        self.assertEqual((scan["parse_errors"], scan["records_without_timestamp"]), (1, 1))

    def test_worker_aggregate_shares_and_first_prompt_stats(self):
        workers = self.scan()["groups"]["workers"]
        self.assertEqual((workers["shell_calls"], workers["rtk_prefixed_shell_calls"]), (6, 1))
        self.assertEqual(workers["rtk_prefix_share"], 0.1667)
        # ctx_fetch_and_index / (web_open_page + ctx_fetch_and_index + remote curl/wget); loopback apart.
        self.assertEqual(workers["fetch"]["ctx_fetch_and_index_share"], 0.3333)
        self.assertEqual(workers["marker_sessions"], 2)
        self.assertEqual(workers["sessions_using_mcp_server"], {"context-mode": 2, "qmd": 1, "serena": 1})
        self.assertEqual(workers["first_prompt_tokens"],
                         {"n": 2, "min": 19000, "p10": 19000, "median": 19000, "p90": 21000, "max": 21000})

    def test_report_contains_no_ids_paths_or_text(self):
        scan = self.scan()
        dumped = json.dumps(scan)
        for leaked in ("lanes-worker", "lanes-subagent", "REDACTED", "/home/example", "Synthetic worker",
                       "synthetic routing", str(self.root), "rollout-", "/private/host", "item_16"):
            self.assertNotIn(leaked, dumped)
        # An originator that is not name-shaped is counted, never printed.
        self.assertEqual(scan["sessions_by_originator"], {"(other)": 1, "codex_exec": 4})

    def test_invoke_rate_classification_ignores_catalogs_after_now(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory())) / "later"
        root.mkdir()
        records = [
            {"timestamp": "2026-10-20T05:00:00Z", "type": "session_meta", "payload": {"id": "s", "source": "exec"}},
            {"timestamp": "2026-10-20T05:01:00Z", "type": "response_item", "payload": {
                "type": "function_call", "name": "exec_command", "call_id": "c1",
                "arguments": "{\"cmd\": \"cat /home/example/.agents/skills/tdd/SKILL.md\"}"}},
            {"timestamp": "2026-11-05T00:00:00Z", "type": "response_item", "payload": {
                "type": "message", "role": "developer", "content": [{"type": "input_text", "text":
                "<skills_instructions>- grill-me (file: /home/example/.agents/skills/grill-me/SKILL.md)"
                "</skills_instructions>"}]}},
        ]
        (root / "rollout-2026-10-20T05-00-00-later.jsonl").write_text(
            "\n".join(json.dumps(record) for record in records) + "\n")
        scan = S.scan_codex_roots([root], self.names, now=S.parse_iso(NOW), windows=(30,),
                                  codex_off=self.codex_off)
        self.assertEqual(scan["sessions_user_config_ignored"], 0)
        self.assertEqual(scan["counts"]["tdd"][30]["skill_md_reads"], 1)
        self.assertEqual(scan["of_which_user_config_ignored"]["tdd"][30]["skill_md_reads"], 0)

    def test_files_not_modified_since_the_window_start_are_skipped_unread(self):
        stale = next(self.root.glob("rollout-*-lanes-isolated.jsonl"))
        old = S.parse_iso("2026-10-01T00:00:00Z").timestamp()
        os.utime(stale, (old, old))
        scan = self.scan()
        self.assertEqual(scan["files_skipped_unmodified"], 1)
        self.assertEqual(scan["user_config"]["ignored"], 0)

    # Review findings 4 and 5 (2026-09-26): the trial pins `counts` as every session's records, so `counts`
    # stays that measurement and the two parts a within-listing-state comparison would leave out are
    # broken out beside it, never subtracted from it: own records of sessions that ignored the user
    # config, and records a spawned sub-agent's rollout copied from its parent.
    def test_invoke_rate_counts_keep_every_session_and_break_out_two_parts(self):
        now = S.parse_iso(NOW)
        scan = S.scan_codex_roots([self.root], self.names, now=now, windows=(30,), codex_off=self.codex_off)
        self.assertEqual(scan["sessions_user_config_ignored"], 1)
        # tdd SKILL.md reads: the worker's own, the isolated session's own and the one the sub-agent copied.
        self.assertEqual(scan["counts"]["tdd"][30]["skill_md_reads"], 3)
        self.assertEqual(scan["of_which_user_config_ignored"]["tdd"][30]["skill_md_reads"], 1)
        self.assertEqual(scan["of_which_copied_from_parent"]["tdd"][30]["skill_md_reads"], 1)
        report = S.build_report(self.manifest, claude=None, codex_scan=scan, lock_installed_at={},
                                now=now, windows=(30,))
        self.assertEqual(report["codex"]["sessions_user_config_ignored"], 1)
        tdd = next(entry for entry in report["skills"] if entry["name"] == "tdd")
        self.assertEqual(tdd["codex"]["counts"]["30"]["skill_md_reads"], 3)
        self.assertEqual(tdd["codex"]["of_which_user_config_ignored"]["30"]["skill_md_reads"], 1)
        self.assertEqual(tdd["codex"]["of_which_copied_from_parent"]["30"]["skill_md_reads"], 1)
        # Without a codex_off list no session is classified; counts are the same either way.
        legacy = S.scan_codex_roots([self.root], self.names, now=now, windows=(30,))
        self.assertEqual((legacy["counts"]["tdd"][30]["skill_md_reads"], legacy["sessions_user_config_ignored"]),
                         (3, 0))

    def breakout_root(self) -> Path:
        """A sub-agent rollout that copied a $tdd mention from its parent and adds its own, and a session
        that ignored the user config (its catalog lists codex_enabled=false grill-me) and is the only
        reader of codeql's SKILL.md."""
        root = Path(self.enterContext(tempfile.TemporaryDirectory())) / "breakout"
        root.mkdir()
        user = lambda text: {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}
        rollouts = {
            "rollout-2026-10-25T06-00-00-sub.jsonl": [
                {"timestamp": "2026-10-25T06:00:00Z", "type": "session_meta", "ordinal": 0, "payload": {
                    "id": "sub", "source": {"subagent": {"thread_spawn": {"parent_thread_id": "p", "depth": 1}}},
                    "subagent_history_start_ordinal": 2}},
                {"timestamp": "2026-10-25T06:00:01Z", "type": "response_item", "ordinal": 1,
                 "payload": user("parent: use $tdd here")},
                {"timestamp": "2026-10-25T06:00:02Z", "type": "response_item", "ordinal": 2,
                 "payload": user("own: and $tdd again")}],
            "rollout-2026-10-25T07-00-00-iso.jsonl": [
                {"timestamp": "2026-10-25T07:00:00Z", "type": "session_meta", "payload": {"id": "iso", "source": "exec"}},
                {"timestamp": "2026-10-25T07:00:01Z", "type": "response_item", "payload": {
                    "type": "message", "role": "developer", "content": [{"type": "input_text", "text":
                    "<skills_instructions>- grill-me (file: /home/example/.agents/skills/grill-me/SKILL.md)"
                    "</skills_instructions>"}]}},
                {"timestamp": "2026-10-25T07:01:00Z", "type": "response_item", "payload": {
                    "type": "function_call", "name": "exec_command", "call_id": "c1",
                    "arguments": "{\"cmd\": \"cat /home/example/.agents/skills/codeql/SKILL.md\"}"}}],
        }
        for name, records in rollouts.items():
            (root / name).write_text("\n".join(json.dumps(record) for record in records) + "\n")
        return root

    def test_a_copied_mention_is_counted_and_broken_out_so_the_parts_add_up(self):
        scan = S.scan_codex_roots([self.breakout_root()], self.names, now=S.parse_iso(NOW), windows=(7, 30),
                                  codex_off=self.codex_off)
        for window in (7, 30):
            self.assertEqual(scan["counts"]["tdd"][window]["name_mentions"], 2)
            self.assertEqual(scan["of_which_copied_from_parent"]["tdd"][window]["name_mentions"], 1)
            self.assertEqual(scan["of_which_user_config_ignored"]["tdd"][window]["name_mentions"], 0)
        for name in self.names:  # each part is inside counts, and the two parts never overlap
            for window in (7, 30):
                for metric in ("skill_md_reads", "name_mentions"):
                    parts = (scan["of_which_user_config_ignored"][name][window][metric]
                             + scan["of_which_copied_from_parent"][name][window][metric])
                    self.assertLessEqual(parts, scan["counts"][name][window][metric])

    def test_the_breakout_changes_no_trial_flag(self):
        # codeql is codex-enabled and read only in the session that ignored the user config: the trial's
        # measurement counts that read, so codeql is not zero on Codex.
        now = S.parse_iso(NOW)
        scan = S.scan_codex_roots([self.breakout_root()], self.names, now=now, windows=(30,), codex_off=self.codex_off)
        report = S.build_report(self.manifest, claude=None, codex_scan=scan, lock_installed_at={},
                                now=now, windows=(30,))
        codeql = next(entry for entry in report["skills"] if entry["name"] == "codeql")
        self.assertEqual(codeql["codex"]["counts"]["30"]["skill_md_reads"], 1)
        self.assertEqual(codeql["codex"]["of_which_user_config_ignored"]["30"]["skill_md_reads"], 1)
        self.assertIs(codeql["zero_on_evaluated_clients"], False)
        self.assertEqual(report["codex"]["sessions_user_config_ignored"], 1)

    # Review finding 10 (2026-09-26): shell, MCP and fetch lanes come from item_completed events, whose
    # persistence depends on the rollout's history mode; a session with calls but no such events is shown.
    def test_history_mode_and_sessions_with_calls_but_no_item_events_are_reported(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory())) / "modes"
        root.mkdir()
        records = [
            {"timestamp": "2026-10-20T05:00:00Z", "type": "session_meta",
             "payload": {"id": "m", "source": "exec", "originator": "codex_exec", "history_mode": "other-mode"}},
            {"timestamp": "2026-10-20T05:01:00Z", "type": "response_item", "payload": {
                "type": "function_call", "name": "exec_command", "call_id": "c1", "arguments": "{\"cmd\": \"ls\"}"}},
        ]
        rollout = root / "rollout-2026-10-20T05-00-00-modes.jsonl"
        rollout.write_text("\n".join(json.dumps(record) for record in records) + "\n")
        written = S.parse_iso("2026-10-22T00:00:00Z").timestamp()
        os.utime(rollout, (written, written))
        scan = S.scan_codex_lanes([root, self.root], self.manifest, since=self.since, until=self.until,
                                  marker=S.DEFAULT_LANES_MARKER)
        self.assertEqual(scan["sessions_by_history_mode"], {"(none)": 5, "other-mode": 1})
        self.assertEqual(scan["sessions_with_tool_calls_but_no_item_events"], 1)
        fixtures_only = self.scan()
        self.assertEqual(fixtures_only["sessions_with_tool_calls_but_no_item_events"], 0)

    def test_fetch_kind_and_shell_script(self):
        self.assertEqual([S.fetch_kind(c) for c in (
            "curl -s https://x.org", "rtk curl https://x.org", "timeout 5 wget http://localhost:8080/",
            'curl "$URL"', "echo curl", "grep curl f", "x=$(curl -s http://[::1]:9/)",
            "curl http://127.0.0.1/ https://example.org", "ls\ncurl -I https://x.org")],
            ["fetch", "fetch", "loopback", "fetch", None, None, "loopback", "fetch", "fetch"])
        # The same cases child-usage.mjs pins: quoted strings and heredoc bodies are data unless a
        # shell runs them (sh -c, eval, ssh, a heredoc fed to a shell).
        self.assertEqual([S.fetch_kind(c) for c in (
            "echo 'hello; curl https://example.com'", 'printf "%s" "curl https://x.org"',
            "bash -c 'curl -s https://x.org'", 'sh -lc "wget http://localhost/"',
            "ssh host 'curl https://x.org'", "cat > s.sh <<'EOF'\ncurl https://x.org\nEOF\nls",
            "bash <<'EOF'\ncurl https://x.org\nEOF", 'x="$(curl -s https://x.org)"',
            'cat <<< "curl https://x.org"', 'curl "http://127.0.0.1:9090/api"',
            "python3 - <<'PY'\nos.system('curl https://x.org')\nPY",
            'grep -c "curl" notes.txt; curl -s https://x.org')],
            [None, None, "fetch", "loopback", "fetch", None, "fetch", "fetch", None, "loopback", None, "fetch"])
        self.assertEqual((S.safe_key("codex:codex-cli-runtime"), S.safe_key("/private/x"),
                          S.safe_key("user@example.com")), ("codex:codex-cli-runtime", "(other)", "(other)"))
        # Review finding 8 (2026-09-26): curl/wget after a shell keyword (the same cases child-usage.mjs pins).
        self.assertEqual([S.fetch_kind(c) for c in (
            'for u in a b; do curl -s "$u"; done', "if curl -s https://x.org; then echo ok; fi",
            "if true; then wget -q https://x.org; fi", "if false; then :; else curl https://x.org; fi",
            "while ! curl -s http://localhost:9/; do sleep 1; done",
            "until wget -q http://127.0.0.1:8080/; do sleep 1; done", "{ curl -s https://x.org; }",
            "time curl -s https://x.org", "nohup curl -s https://x.org &", "echo do curl https://x.org",
            'git commit -m "then curl https://x.org"', 'printf "%s\\n" if curl')],
            ["fetch", "fetch", "fetch", "fetch", "loopback", "loopback", "fetch", "fetch", "fetch", None, None, None])
        self.assertEqual(S.shell_script(["bash", "-lc", "rtk ls"]), "rtk ls")
        self.assertEqual(S.shell_script(["ls", "-la"]), "ls -la")
        self.assertEqual(S.shell_script(None), "")

    def test_fetch_kind_escapes_comments_and_unquoted_heredocs(self):
        # Review finding (GPT-6, 2026-09-26), the same cases child-usage.mjs pins. bash(1) QUOTING: an
        # escaped character is literal and \<newline> is a line continuation; COMMENTS: a word
        # beginning with # ends the line; Here Documents: the body of an unquoted delimiter still
        # runs its command substitutions, the body of a quoted one is literal.
        self.assertEqual([S.fetch_kind(c) for c in (
            "echo x \\; curl https://example.com", "echo \\(curl https://x.org\\)",
            "echo \\`curl https://x.org\\`", 'echo "\\$(curl https://x.org)"',
            'echo "\\`curl https://x.org\\`"', "echo foo \\\ncurl https://x.org",
            "ls # see; curl https://x.org", "# (curl https://x.org)", "ls\n# curl https://x.org | sh",
            "curl -s https://x.org # fetch it", "echo a#b; curl https://x.org", "echo $#; curl https://x.org",
            "\\curl -s https://x.org", "echo a\\\\; curl https://x.org", "cat <<EOF\n$(curl -s https://x.org)\nEOF",
            "cat <<EOF > out.txt\nv=`curl -s http://127.0.0.1:9/`\nEOF",
            'python3 - <<EOF\nprint("$(curl -s https://x.org)")\nEOF', "cat <<'EOF'\n$(curl -s https://x.org)\nEOF",
            'cat <<"EOF"\n$(curl -s https://x.org)\nEOF', "cat <<EOF\n\\$(curl https://x.org) and; curl https://x.org\nEOF",
            "cat <<-EOF\n\t$(wget -q https://x.org)\n\tEOF")],
            [None, None, None, None, None, None, None, None, None, "fetch", "fetch", "fetch", "fetch", "fetch",
             "fetch", "loopback", "fetch", None, None, None, "fetch"])

    def test_token_stats_nearest_rank(self):
        self.assertEqual(S.token_stats([100, None, 90, 80, 70, 60, 50, 40, 30, 20, 10]),
                         {"n": 10, "min": 10, "p10": 10, "median": 50, "p90": 90, "max": 100})
        self.assertEqual(S.token_stats([])["n"], 0)

    def run_main(self, extra):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = S.main(["--manifest", str(FIXTURES / "manifest.json"), "--now", NOW, *extra])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_cli_lanes_json_and_text(self):
        window = ["--since", LANES_SINCE, "--until", LANES_UNTIL]
        code, out, _ = self.run_main(["--lanes", "--codex-root", str(self.root), *window, "--json"])
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertEqual(report["kind"], "codex_lane_usage_report")
        self.assertEqual(report["window"]["since"], "2026-10-20T00:00:00+00:00")
        self.assertEqual(report["groups"]["workers"]["sessions"], 3)
        code, out, _ = self.run_main(["--lanes", "--codex-root", str(self.root), *window])
        self.assertEqual(code, 0)
        self.assertIn("user_config: applied=3 ignored=1 unknown=1", out)

    def test_both_cli_sidecars_accept_and_validate_log_find_review(self):
        review = self.root / "review.json"
        record = {"transcript_sha256": "0" * 64, "tool_use_id": "c", "witness": "independent check",
                  "rtk_log_find": [{"part": 1, "disposition": "permitted"}]}
        for adjudications, expected in [([{ "part": 1, "disposition": "permitted"}], 0),
                                       ([{ "part": 0, "disposition": "permitted"}], 2),
                                       ([{ "part": 1, "disposition": "guess"}], 2),
                                       ([{ "part": 1, "disposition": "permitted"}] * 2, 2)]:
            with self.subTest(adjudications=adjudications):
                record["rtk_log_find"] = adjudications
                review.write_text(json.dumps([record]))
                code, _, _ = self.run_main(["--lanes", "--codex-root", str(self.root),
                                             "--exceptions", str(review), "--json"])
                self.assertEqual(code, expected)
                p = subprocess.run(["node", str(S.MEASUREMENT_MODULE), "--lanes-sweep",
                                    "--root", str(self.root), "--exceptions", str(review)],
                                   capture_output=True, text=True)
                self.assertEqual(p.returncode == 0, expected == 0)

    def test_both_cli_sidecars_reject_malformed_classes_in_mixed_records(self):
        review = self.root / "mixed-review.json"
        good = {"transcript_sha256": "0" * 64, "tool_use_id": "c", "witness": "independent check",
                "exception": "exact_bytes_required_by_frozen_check", "proxy_purpose": "acceptance",
                "rtk_log_find": [{"part": 1, "disposition": "permitted"}]}
        variants = [({}, True), ({"exception": "typo"}, False), ({"exception": None}, False),
                    ({"proxy_purpose": "acceptence"}, False), ({"proxy_purpose": None}, False),
                    ({"rtk_log_find": None}, False), ({"rtk_log_find": []}, False),
                    ({"rtk_log_find": [{"part": 0, "disposition": "permitted"}]}, False),
                    ({"rtk_log_find": [{"part": 1, "disposition": "guess"}]}, False),
                    ({"rtk_log_find": good["rtk_log_find"] * 2}, False)]
        for override, valid in variants:
            review.write_text(json.dumps([{**good, **override}]))
            with self.subTest(override=override, cli="skill_usage"):
                code, _, _ = self.run_main(["--lanes", "--codex-root", str(self.root),
                                           "--exceptions", str(review), "--json"])
                self.assertEqual(code, 0 if valid else 2)
            with self.subTest(override=override, cli="child_usage"):
                p = subprocess.run(["node", str(S.MEASUREMENT_MODULE), "--lanes-sweep",
                                    "--root", str(self.root), "--exceptions", str(review)],
                                   capture_output=True, text=True)
                self.assertEqual(p.returncode == 0, valid)

    def test_cli_lanes_refusals(self):
        root = ["--codex-root", str(self.root)]
        for args in (["--lanes"],
                     ["--lanes", *root, "--claude-skill-doctor", str(FIXTURES / "skill-doctor-sample.json")],
                     ["--lanes", *root, "--since", LANES_UNTIL, "--until", LANES_SINCE],
                     ["--lanes", *root, "--since", "yesterday"],
                     ["--lanes", *root, "--marker", " "],
                     [*root, "--since", LANES_SINCE]):
            with self.subTest(args=args):
                self.assertEqual(self.run_main(args)[0], 2)

    def test_cli_lanes_out_inside_the_repository_is_refused(self):
        refused = ROOT / "tools" / "skill-usage" / "_lanes_should_never_be_written.json"
        try:
            code, _, _ = self.run_main(["--lanes", "--codex-root", str(self.root), "--out", str(refused)])
            self.assertEqual(code, 2)
            self.assertFalse(refused.exists())
        finally:
            if refused.exists():
                refused.unlink()


def u3_forked_child(*own):
    """A1: a spawned sub-agent (start ordinal 4) that inherited its parent's hook context at ordinal 2, then its own
    records (kind, payload, time) from ordinal 4 on."""
    rows = [u3_row("session_meta", {"id": "child-10a", "source": {"subagent": {"thread_spawn": {
                "parent_thread_id": "parent-10a", "depth": 1}}}, "history_mode": "paginated",
                "subagent_history_start_ordinal": 4}, "2026-10-20T02:00:00Z", 0),
            u3_row("session_meta", {"id": "parent-10a", "source": "exec", "history_mode": "paginated"},
                   "2026-10-20T02:00:00Z", 1),
            u3_row("response_item", developer(MARKER + "inherited routing block", kinds=[HOOK_KIND]),
                   "2026-10-20T02:00:01Z", 2),
            u3_row("response_item", developer(CATALOG), "2026-10-20T02:00:02Z", 3)]
    return rows + [u3_row(kind, payload, at, 4 + index) for index, (kind, payload, at) in enumerate(own)]


def u3_root(*own):
    """A root exec session with a catalog, then its own records (kind, payload, time)."""
    rows = [u3_row("session_meta", {"id": "root-10a", "source": "exec", "history_mode": "paginated"},
                   "2026-10-20T03:00:00Z", 0),
            u3_row("response_item", developer(CATALOG), "2026-10-20T03:00:01Z", 1)]
    return rows + [u3_row(kind, payload, at, 2 + index) for index, (kind, payload, at) in enumerate(own)]


OWN_TOKENS = ("event_msg", TOKENS, "2026-10-20T02:00:05Z")
OWN_HOOK = ("response_item", developer(MARKER + "own hook block", kinds=[HOOK_KIND]), "2026-10-20T02:00:06Z")
OWN_HOOK_WITHOUT_MARKER = ("response_item", developer("hook text without the block", kinds=[HOOK_KIND]),
                           "2026-10-20T02:03:00Z")
OWN_COMMAND = ("event_msg", {"type": "item_completed", "item": {
    "type": "CommandExecution", "id": "item_1", "command": ["bash", "-lc", "ls"], "source": "unified_exec_startup",
    "status": "completed", "exit_code": 0}}, "2026-10-20T02:04:00Z")
ROOT_HOOK = (("response_item", developer(MARKER + "routing block", kinds=[HOOK_KIND]), "2026-10-20T03:00:02Z"),
             ("event_msg", TOKENS, "2026-10-20T03:00:05Z"))
GROUP_MARKER_KEYS = ("marker_sessions", "marker_inherited_sessions", "marker_injected_sessions",
                     "marker_inherited_only_sessions", "marker_injected_by_kind")


class CodexMarkerSplit(unittest.TestCase):
    """PR-A item 10a (design section 1, with the review's kinds and window findings). A developer message is inherited when
    its record's ordinal is below session_meta.subagent_history_start_ordinal (protocol.rs:3180-3185) and the session's own
    otherwise. A spawned sub-agent runs SubagentStart and a root SessionStart (core/src/hook_runtime.rs:128-154); both record
    a hook's additionalContext as a developer fragment of kind hooks.additional_context (hook_runtime.rs:848-872). The legacy
    `marker` keeps its meaning (the marker in any developer message before until); marker_inherited and marker_injected split
    it by content item, and marker_injected_kinds counts the injected items by kind. measurement.codex_hook_context counts
    developer content items of kind hooks.additional_context: own items in the window of their own record, inherited items
    once, in the window of the child's first own record, so adjacent windows add up. A kinds list that does not align with
    the content items, or a kind that is not a string, leaves the item's kind unknown: (none) in marker_injected_kinds and
    no hook context. The kernel's measurement.hook_context stays Claude-attachment-only."""

    def setUp(self):
        self.manifest = load_fixture_manifest()
        self.names = fixture_names()
        self.codex_off = [s["name"] for s in self.manifest["skills"] if s["codex_enabled"] is False]
        self.codex_on = [s["name"] for s in self.manifest["skills"] if s["codex_enabled"] is True]
        self.since, self.until = S.parse_iso(LANES_SINCE), S.parse_iso(LANES_UNTIL)
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def rollout(self, records) -> Path:
        name = "rollout-2026-10-20T02-00-00-u3-marker.jsonl"
        return write_rollouts(self.tmp / f"case-{len(list(self.tmp.iterdir()))}", {name: records}) / name

    def lanes(self, path, since=None, until=None) -> dict:
        return S.scan_lanes_file(path, self.names, since=self.since if since is None else since,
                                 until=self.until if until is None else until, marker=MARKER,
                                 codex_off=self.codex_off, codex_on=self.codex_on)[0]

    def split_and_hooks(self, records):
        session = self.lanes(self.rollout(records))
        return {key: session.get(key) for key in SPLIT}, session.get("measurement", {}).get("codex_hook_context")

    def scan(self, root) -> dict:
        return S.scan_codex_lanes([root], self.manifest, since=self.since, until=self.until, marker=MARKER)

    def test_an_inherited_hook_marker_is_inherited_not_injected(self):
        # A1, whose inherited developer message carries content_item_kinds (the review's A1 finding).
        split, hooks = self.split_and_hooks(u3_forked_child(OWN_TOKENS, OWN_COMMAND))
        self.assertEqual(split, {"marker": True, "marker_inherited": True, "marker_injected": False,
                                 "marker_injected_kinds": {}})
        self.assertEqual(hooks, {"inserted": 0, "with_marker": 0, "inherited": 1, "inherited_with_marker": 1})

    def test_an_own_hook_marker_is_injected_beside_the_inherited_one(self):
        # A2: the child's own hook context (ordinal 5) carries the marker; a second own hook item has none.
        split, hooks = self.split_and_hooks(u3_forked_child(OWN_TOKENS, OWN_HOOK, OWN_HOOK_WITHOUT_MARKER, OWN_COMMAND))
        self.assertEqual(split, {"marker": True, "marker_inherited": True, "marker_injected": True,
                                 "marker_injected_kinds": {HOOK_KIND: 1}})
        self.assertEqual(hooks, {"inserted": 2, "with_marker": 1, "inherited": 1, "inherited_with_marker": 1})

    def test_a_root_marker_is_injected(self):
        split, hooks = self.split_and_hooks(u3_root(*ROOT_HOOK))
        self.assertEqual(split, {"marker": True, "marker_inherited": False, "marker_injected": True,
                                 "marker_injected_kinds": {HOOK_KIND: 1}})
        self.assertEqual(hooks, {"inserted": 1, "with_marker": 1, "inherited": 0, "inherited_with_marker": 0})

    def test_a_fresh_child_without_a_marker_has_neither(self):
        # fork_turns none gives no start ordinal (spawn.rs:280-282), so nothing is inherited; its own hook item has no marker.
        split, hooks = self.split_and_hooks([
            u3_row("session_meta", {"id": "child-none", "source": {"subagent": {"thread_spawn": {
                "parent_thread_id": "parent-none", "depth": 1}}}, "history_mode": "paginated"}, "2026-10-20T04:00:00Z", 0),
            u3_row("response_item", developer(CATALOG), "2026-10-20T04:00:01Z", 1),
            u3_row("response_item", developer("hook text without the block", kinds=[HOOK_KIND]),
                   "2026-10-20T04:00:02Z", 2),
            u3_row("event_msg", TOKENS, "2026-10-20T04:00:05Z", 3)])
        self.assertEqual(split, {"marker": False, "marker_inherited": False, "marker_injected": False,
                                 "marker_injected_kinds": {}})
        self.assertEqual(hooks, {"inserted": 1, "with_marker": 0, "inherited": 0, "inherited_with_marker": 0})

    def test_a_marker_outside_developer_messages_changes_nothing(self):
        # The marker is looked for in developer messages only: a user message and a tool output do not count.
        split, hooks = self.split_and_hooks(u3_root(
            ("response_item", {"type": "message", "role": "user",
                               "content": [{"type": "input_text", "text": MARKER}]}, "2026-10-20T03:00:02Z"),
            ("response_item", {"type": "function_call", "call_id": "c", "name": "exec_command",
                               "arguments": json.dumps({"cmd": "cat notes.md"})}, "2026-10-20T03:00:03Z"),
            ("response_item", {"type": "function_call_output", "call_id": "c", "output": MARKER},
             "2026-10-20T03:00:04Z"),
            ("event_msg", TOKENS, "2026-10-20T03:00:05Z")))
        self.assertEqual(split, {"marker": False, "marker_inherited": False, "marker_injected": False,
                                 "marker_injected_kinds": {}})
        self.assertEqual(hooks, NO_HOOKS)

    def test_kinds_that_do_not_align_or_are_not_strings_read_as_none(self):
        # content_item_kinds is aligned with the item's content entries (models.rs:968-973). A list of another length, a
        # value that is not a list and a kind that is not a string leave the kind unknown; a kind that is not name-shaped
        # is counted as (other) and never printed.
        split, hooks = self.split_and_hooks(u3_root(
            ("response_item", developer(MARKER + " a", "second item", kinds=[HOOK_KIND]), "2026-10-20T03:00:02Z"),
            ("response_item", developer(MARKER + " b", kinds=[7]), "2026-10-20T03:00:03Z"),
            ("response_item", developer(MARKER + " c", kinds=HOOK_KIND), "2026-10-20T03:00:04Z"),
            ("response_item", developer(MARKER + " d", kinds=["/private/kind-path"]), "2026-10-20T03:00:05Z"),
            ("response_item", developer("no marker here", MARKER + " e", kinds=["other.kind", HOOK_KIND]),
             "2026-10-20T03:00:06Z"),
            ("event_msg", TOKENS, "2026-10-20T03:00:07Z")))
        self.assertEqual(split, {"marker": True, "marker_inherited": False, "marker_injected": True,
                                 "marker_injected_kinds": {"(none)": 3, "(other)": 1, HOOK_KIND: 1}})
        self.assertEqual(hooks, {"inserted": 1, "with_marker": 1, "inherited": 0, "inherited_with_marker": 0})
        self.assertNotIn("/private/kind-path", json.dumps(split))

    def test_the_retained_fixtures_carry_no_kinds(self):
        # The review's A1 control: the retained sub-agent inherited its marker from a developer message without
        # content_item_kinds, so its marker is inherited while no hook context is counted; the worker's own marker is
        # injected with an unknown kind.
        root = materialize_lanes_root(self.tmp)
        subagent = self.lanes(next(root.glob("rollout-*-lanes-subagent.jsonl")))
        worker = self.lanes(next(root.glob("rollout-*-lanes-worker.jsonl")))
        self.assertEqual({key: subagent.get(key) for key in SPLIT},
                         {"marker": True, "marker_inherited": True, "marker_injected": False, "marker_injected_kinds": {}})
        self.assertEqual(subagent.get("measurement", {}).get("codex_hook_context"), NO_HOOKS)
        self.assertEqual({key: worker.get(key) for key in SPLIT},
                         {"marker": True, "marker_inherited": False, "marker_injected": True,
                          "marker_injected_kinds": {"(none)": 1}})
        self.assertEqual(worker.get("measurement", {}).get("codex_hook_context"), NO_HOOKS)

    def test_groups_split_the_marker_sessions(self):
        groups = self.scan(materialize_lanes_root(self.tmp))["groups"]
        self.assertEqual({key: groups["workers"].get(key) for key in GROUP_MARKER_KEYS},
                         {"marker_sessions": 2, "marker_inherited_sessions": 1, "marker_injected_sessions": 1,
                          "marker_inherited_only_sessions": 1, "marker_injected_by_kind": {"(none)": 1}})
        self.assertEqual({key: groups["negative_controls"].get(key) for key in GROUP_MARKER_KEYS},
                         {"marker_sessions": 0, "marker_inherited_sessions": 0, "marker_injected_sessions": 0,
                          "marker_inherited_only_sessions": 0, "marker_injected_by_kind": {}})
        self.assertEqual(groups["workers"]["measurement"].get("codex_hook_context"), NO_HOOKS)

    def test_a_group_sums_its_actors_hook_context(self):
        root = write_rollouts(self.tmp / "sum", {
            "rollout-2026-10-20T02-00-00-u3-child.jsonl": u3_forked_child(
                OWN_TOKENS, OWN_HOOK, OWN_HOOK_WITHOUT_MARKER, OWN_COMMAND),
            "rollout-2026-10-20T03-00-00-u3-root.jsonl": u3_root(*ROOT_HOOK)})
        workers = self.scan(root)["groups"]["workers"]
        self.assertEqual(workers["sessions"], 2)
        self.assertEqual({key: workers.get(key) for key in GROUP_MARKER_KEYS},
                         {"marker_sessions": 2, "marker_inherited_sessions": 1, "marker_injected_sessions": 2,
                          "marker_inherited_only_sessions": 0, "marker_injected_by_kind": {HOOK_KIND: 2}})
        self.assertEqual(workers["measurement"].get("codex_hook_context"),
                         {"inserted": 3, "with_marker": 2, "inherited": 1, "inherited_with_marker": 1})

    def test_hook_context_adds_up_across_adjacent_windows(self):
        # The review's window finding: own items count in the window of their record and inherited items once, in the
        # window of the child's first own record (ordinal 4, 02:00:05), so every split adds up to the whole window. A
        # window that holds only inherited records measures nothing (scan_lanes_file measures a session with a counted
        # record), which is why inherited items do not follow their own records.
        records = u3_forked_child(OWN_TOKENS, OWN_HOOK, OWN_HOOK_WITHOUT_MARKER, OWN_COMMAND)
        path = self.rollout(records)

        def hooks(since, until):
            session = self.lanes(path, since, until)
            return collections.Counter(session.get("measurement", {}).get("codex_hook_context") or {})
        whole = self.lanes(path).get("measurement", {}).get("codex_hook_context")
        self.assertEqual(whole, {"inserted": 2, "with_marker": 1, "inherited": 1, "inherited_with_marker": 1})
        times = sorted({S.parse_iso(record["timestamp"]) for record in records})
        edges = [self.since, *(t for t in times if self.since < t < self.until), self.until]
        for split in (a + (b - a) / 2 for a, b in zip(edges, edges[1:])):
            with self.subTest(split=split.isoformat()):
                self.assertEqual(hooks(self.since, split) + hooks(split, self.until), +collections.Counter(whole))


ROLE_CASES = (  # (file stem, session_meta role fields, thread_spawn role fields or None for a root, actors[].role)
    ("a-root", {}, None, "(root)"),
    ("b-meta-role", {"agent_role": "stack-researcher"}, {}, "stack-researcher"),
    ("c-meta-alias", {"agent_type": "stack-researcher"}, {}, "stack-researcher"),
    ("d-spawn-role", {}, {"agent_role": "stack-researcher"}, "stack-researcher"),
    ("e-spawn-alias", {}, {"agent_type": "stack-researcher"}, "stack-researcher"),
    ("f-path", {"agent_role": "/home/example/.codex/agents/researcher.toml"}, {}, "(other)"),
    ("g-blank", {"agent_role": " \t"}, {}, "(none)"),
    ("h-trimmed", {"agent_role": " stack-researcher\n"}, {}, "stack-researcher"),
    ("i-not-white-space", {"agent_role": "\x1cstack-researcher"}, {}, "(other)"),  # U+001C: Python strips, Rust keeps
    ("j-not-a-string", {"agent_role": 7}, {}, "(none)"),
    ("k-no-role", {}, {}, "(none)"),
    ("l-meta-first", {"agent_role": "meta-role"}, {"agent_role": "spawn-role"}, "meta-role"),
)


def role_rollout(stem, meta_fields, spawn_fields):
    source = "exec" if spawn_fields is None else {"subagent": {"thread_spawn": {
        "parent_thread_id": "role-parent", "depth": 1, **spawn_fields}}}
    return [u3_row("session_meta", {"id": f"role-{stem}", "source": source, "history_mode": "paginated", **meta_fields},
                   "2026-10-20T05:00:00Z", 0),
            u3_row("response_item", developer(CATALOG), "2026-10-20T05:00:01Z", 1),
            u3_row("event_msg", TOKENS, "2026-10-20T05:00:05Z", 2)]


class CodexRoleGroups(unittest.TestCase):
    """PR-A item 10b (design section 2). A session's role is session_meta.agent_role, which also deserializes from
    agent_type (protocol.rs:3153-3155), else source.subagent.thread_spawn.agent_role, also read from agent_type
    (:2904-2913), from the session's first session_meta (a sub-agent rollout repeats its parent's meta second). As the spawn
    handler does (core/src/tools/handlers/multi_agents_v2/spawn.rs:126-130), the role is trimmed of Unicode White_Space (Rust
    str::trim) and an empty one is none; a value that is not a string is none; a role that is not name-shaped is (other). A
    sub-agent without a role is (none) and every other session (root). actors[].role, sessions_by_role and
    groups.workers_by_role publish it."""

    def setUp(self):
        self.manifest = load_fixture_manifest()
        self.since, self.until = S.parse_iso(LANES_SINCE), S.parse_iso(LANES_UNTIL)
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def scan(self, root) -> dict:
        return S.scan_codex_lanes([root], self.manifest, since=self.since, until=self.until, marker=MARKER)

    def test_the_role_comes_from_the_meta_then_the_spawn_source(self):
        # B (a worker: its catalog lists an enabled manifest skill) and its controls.
        root = write_rollouts(self.tmp / "roles", {
            f"rollout-2026-10-20T05-00-00-u3-role-{stem}.jsonl": role_rollout(stem, meta, spawn)
            for stem, meta, spawn, _ in ROLE_CASES})
        scan = self.scan(root)
        self.assertEqual([actor.get("role") for actor in scan["actors"]], [role for *_, role in ROLE_CASES])
        expected = dict(collections.Counter(role for *_, role in ROLE_CASES))
        self.assertEqual(scan.get("sessions_by_role"), expected)
        self.assertEqual({role: group["sessions"] for role, group in scan["groups"].get("workers_by_role", {}).items()},
                         expected)
        self.assertNotIn("researcher.toml", json.dumps(scan))

    def test_the_retained_fixtures_are_roots_and_one_child_without_a_role(self):
        scan = self.scan(materialize_lanes_root(self.tmp))
        self.assertEqual([(actor["kind"], actor.get("role")) for actor in scan["actors"]],
                         [("exec", "(root)"), ("exec", "(root)"), ("subagent", "(none)"), ("exec", "(root)"),
                          ("exec", "(root)")])
        self.assertEqual(scan.get("sessions_by_role"), {"(none)": 1, "(root)": 4})
        by_role = scan["groups"].get("workers_by_role", {})
        self.assertEqual({role: group["sessions"] for role, group in by_role.items()}, {"(none)": 1, "(root)": 2})
        # The role groups partition the workers group.
        self.assertEqual(sum(group["tool_calls"] for group in by_role.values()), scan["groups"]["workers"]["tool_calls"])


class CodexRouteValues(unittest.TestCase):
    """PR-A item 10g, route values (design section 3, commit 4). provider_usage.attempts[] take configured_model and effort
    from the turn's TurnContextItem (protocol.rs:3328, :3344-3345). ReasoningEffort at rust-v0.157.1 is none, minimal, low,
    medium, high, xhigh, max, ultra, persistent or a custom string (protocol/src/openai_models.rs:59-72), so any name-shaped
    effort is kept; a model keeps at most one provider segment (cx/gpt-6-astra); a path-shaped, '..' or multi-segment value
    is (other), and a missing or non-string value is null."""

    def routes(self, contexts):
        rows, total = [], 0
        for index, context in enumerate(contexts):
            total += 10
            rows += [u3_row("turn_context", context, f"2026-10-20T06:{index:02d}:00Z"),
                     u3_row("event_msg", {"type": "task_started"}, f"2026-10-20T06:{index:02d}:01Z"),
                     u3_row("event_msg", {"type": "token_count", "info": {
                         "total_token_usage": dict.fromkeys(S.CODEX_COUNTERS, total)}}, f"2026-10-20T06:{index:02d}:02Z"),
                     u3_row("event_msg", {"type": "task_complete"}, f"2026-10-20T06:{index:02d}:03Z")]
        got = S.measure_codex_records(rows, since=S.parse_iso(LANES_SINCE), until=S.parse_iso(LANES_UNTIL))
        return [(a.get("configured_model"), a.get("effort")) for a in got["provider_usage"]["attempts"]], got

    def test_configured_model_and_effort_come_from_the_turn_context(self):
        # Must stay: the delivered per-attempt route had no test (scope.md, item 10g verifier); effort, else reasoning_effort.
        routes, _ = self.routes([{"model": "gpt-6-astra", "effort": "max"},
                                 {"model": "gpt-6-astra", "reasoning_effort": "high"},
                                 {"model": "gpt-6-sol", "effort": "low"}])
        self.assertEqual(routes, [("gpt-6-astra", "max"), ("gpt-6-astra", "high"), ("gpt-6-sol", "low")])

    def test_route_values_keep_provider_models_and_every_effort(self):
        # C and its controls.
        routes, got = self.routes([{"model": "cx/gpt-6-astra", "effort": "ultra"}, {"model": "gpt-6-sol", "effort": "none"},
                                   {"model": "gpt-6-sol", "effort": "minimal"}, {"model": "/home/example/m", "effort": ""},
                                   {"model": "a/b/c", "effort": "/x"}, {"model": "cx/../m", "effort": 5},
                                   {"model": "cx/", "effort": "custom-level"}, {"model": 7, "effort": "max"}])
        self.assertEqual(routes, [("cx/gpt-6-astra", "ultra"), ("gpt-6-sol", "none"), ("gpt-6-sol", "minimal"),
                                  ("(other)", None), ("(other)", "(other)"), ("(other)", None),
                                  ("(other)", "custom-level"), (None, "max")])
        self.assertNotIn("/home/example", json.dumps(got))

    def test_route_values_that_are_not_strings_are_null(self):
        # TurnContextItem.model is a String and effort a ReasoningEffortConfig string (protocol.rs:3328, :3344-3345), so a value of
        # another JSON type is no route: a bool is an int in Python and str(True) is name-shaped, so the type decides, not the text.
        routes, _ = self.routes([{"model": True, "effort": True}, {"model": ["gpt-6-sol"], "effort": {"x": 1}},
                                 {"model": None, "effort": None}])
        self.assertEqual(routes, [(None, None), (None, None), (None, None)])


def usage_turn(minute, usage, last_input=None, repeat=None, ordinal=None):
    """One turn: task_started, a token_count snapshot of cumulative usage (with the request's own input tokens when given, and
    once more with the same totals when repeat names a second request size), task_complete."""
    def snapshot(last):
        info = {"total_token_usage": usage, **({"last_token_usage": {"input_tokens": last}} if last is not None else {})}
        return u3_row("event_msg", {"type": "token_count", "info": info}, f"2026-10-20T07:{minute:02d}:01Z", ordinal)
    return [u3_row("event_msg", {"type": "task_started"}, f"2026-10-20T07:{minute:02d}:00Z", ordinal), snapshot(last_input),
            *([snapshot(repeat)] if repeat is not None else []),
            u3_row("event_msg", {"type": "task_complete"}, f"2026-10-20T07:{minute:02d}:02Z", ordinal)]


def usage_of(total, cache_write=None):
    """A TokenUsage total with every pre-0.157.1 counter at total, and cache_write_input_tokens only when given."""
    usage = dict.fromkeys(("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens"), total)
    return usage if cache_write is None else {**usage, "cache_write_input_tokens": cache_write}


class CodexUsageCounters(unittest.TestCase):
    """Binding correction 4 of the U3 build (u3-corrections.md, gap G3 of the U11 design), with design commit 4 because it changes the
    delivered provider_usage.attempts[]. TokenUsage carries cache_write_input_tokens at rust-v0.157.1 (protocol/src/protocol.rs:2239-2241)
    with serde(default), so a rollout of an older client can lack it: it is differenced like the other cumulative counters, a rollout
    without it reports null for it (never 0), and its absence is no usage gap, so provider_usage.complete keeps its meaning. The request's
    own last_token_usage.input_tokens (TokenUsageInfo, :2269-2275) is kept as a per-attempt maximum, max_request_input_tokens, over the
    attempt's counted snapshots; a snapshot that repeats the totals is no new request."""

    def measure(self, rows):
        return S.measure_codex_records(rows, since=S.parse_iso(LANES_SINCE), until=S.parse_iso(LANES_UNTIL))["provider_usage"]

    def test_cache_writes_are_differenced(self):
        got = self.measure(usage_turn(0, usage_of(100, 30)) + usage_turn(1, usage_of(200, 75)))
        self.assertEqual([attempt["usage"].get("cache_write_input_tokens", "missing") for attempt in got["attempts"]], [30, 45])
        self.assertEqual((got["totals"].get("cache_write_input_tokens", "missing"), got["totals"]["input_tokens"]), (75, 200))
        self.assertTrue(got["complete"])

    def test_a_rollout_without_cache_writes_reports_them_as_unknown(self):
        got = self.measure(usage_turn(0, usage_of(100)) + usage_turn(1, usage_of(200)))
        self.assertEqual([attempt["usage"].get("cache_write_input_tokens", "missing") for attempt in got["attempts"]], [None, None])
        self.assertEqual((got["totals"].get("cache_write_input_tokens", "missing"), got["totals"]["input_tokens"]), (None, 200))
        self.assertEqual((got["complete"], got["gaps"]), (True, 0))
        # A snapshot without the field and a later one with it: that difference is unknown too.
        mixed = self.measure(usage_turn(0, usage_of(100)) + usage_turn(1, usage_of(200, 75)))
        self.assertEqual([attempt["usage"].get("cache_write_input_tokens", "missing") for attempt in mixed["attempts"]], [None, None])
        self.assertEqual((mixed["complete"], mixed["gaps"]), (True, 0))

    def test_a_child_differences_cache_writes_from_its_copied_baseline(self):
        # The parent's copied snapshot (below subagent_history_start_ordinal) is the child's baseline, as for every counter.
        meta = u3_row("session_meta", {"id": "u3-child", "source": {"subagent": {}}, "subagent_history_start_ordinal": 3},
                      "2026-10-20T06:59:00Z", 0)
        copied = u3_row("event_msg", {"type": "token_count", "info": {"total_token_usage": usage_of(100, 30)}},
                        "2026-10-20T06:59:01Z", 1)
        got = self.measure([meta, copied, *usage_turn(0, usage_of(150, 50), ordinal=4)])
        self.assertEqual([attempt["usage"].get("cache_write_input_tokens", "missing") for attempt in got["attempts"]], [20])
        self.assertEqual(got["totals"]["input_tokens"], 50)

    def test_a_group_total_is_unknown_when_an_actor_lacks_cache_writes(self):
        root = write_rollouts(Path(self.enterContext(tempfile.TemporaryDirectory())), {
            f"rollout-2026-10-20T07-00-0{index}-u3-usage.jsonl": [
                u3_row("session_meta", {"id": f"u3-usage-{index}", "source": "exec"}, "2026-10-20T06:59:00Z"),
                *usage_turn(index, usage)] for index, usage in enumerate((usage_of(100, 30), usage_of(200)))})
        group = S.scan_codex_lanes([root], load_fixture_manifest(), since=S.parse_iso(LANES_SINCE), until=S.parse_iso(LANES_UNTIL),
                                   marker=MARKER)["groups"]["unclassified"]["measurement"]["provider_usage"]
        self.assertEqual((group["totals"].get("cache_write_input_tokens", "missing"), group["totals"]["input_tokens"]), (None, 300))

    def test_each_attempt_keeps_its_largest_request(self):
        # The second snapshot of the first turn repeats the totals, so its request size is not read.
        before = u3_row("event_msg", {"type": "token_count", "info": {"total_token_usage": usage_of(50),
                                                                      "last_token_usage": {"input_tokens": 9000}}},
                        "2026-10-19T23:59:00Z")  # before since: the baseline only
        got = self.measure([before, *usage_turn(0, usage_of(100), last_input=90), *usage_turn(1, usage_of(250), last_input=140,
                                                                                               repeat=999),
                            *usage_turn(2, usage_of(300))])
        self.assertEqual([attempt.get("max_request_input_tokens", "missing") for attempt in got["attempts"]], [90, 140, None])


SPAWN_ROUTE = ("gpt-6-astra", "max")


def spawn_ids(case):
    """The distinctive private values of one spawn case; none may appear in a published report."""
    return {"parent": f"thread-parent-PRIV-{case}", "child": f"thread-child-PRIV-{case}", "call": f"call-spawn-PRIV-{case}",
            "nested": f"call-nested-PRIV-{case}", "followup_call": f"call-followup-PRIV-{case}",
            "path": f"/root/PRIV_task_{case}", "nick": f"PRIV-Nick-{case}", "message": f"PRIV spawn message {case}",
            "followup": f"PRIV follow-up message {case}", "turn": f"turn-PRIV-{case}", "other": f"thread-other-PRIV-{case}"}


def spawn_case(case, *, args=None, parent_route=SPAWN_ROUTE, child_routes=(SPAWN_ROUTE,), role=None, start=True,
               parent=True, spawn_call=True, other_parent=False, followups=(), legacy_parent=False, namespace="collaboration"):
    """One parent rollout that spawns one child through a direct spawn_agent function_call (spawn.rs:253-263) and records
    a SubAgentActivity started item whose id is that call_id (spawn.rs:216-226), then the child's rollout: its meta with the
    ThreadSpawn source, the parent's records below subagent_history_start_ordinal when it is forked, its own
    ThreadSettingsApplied (thread_id is its own id) and one turn per child route. followups are followup_task calls whose
    target is the child's thread id ("thread") or its task path ("path") (multi_agents_spec.rs:217-241), or a V1
    resume_agent call with the child's id ("resume", :246-266). A legacy_parent persists no started item, only a completed
    one (rollout/src/policy.rs:94-112); namespace multi_agent_v1 is a V1 spawn, whose history comes from fork_context
    (multi_agents_spec.rs:591-628)."""
    ids, hour = spawn_ids(case), int(case[1:])

    def at(minute, second):
        return f"2026-10-20T{hour:02d}:{minute:02d}:{second:02d}Z"
    parent_meta = {"id": ids["parent"], "source": "exec", "originator": "codex_exec", "cli_version": "0.157.1",
                   "history_mode": "legacy" if legacy_parent else "paginated"}
    parent_rows = [("session_meta", parent_meta, at(0, 0)), ("response_item", developer(CATALOG), at(0, 1)),
                   ("event_msg", {"type": "task_started", "turn_id": ids["turn"]}, at(0, 2)),
                   ("turn_context", {"turn_id": ids["turn"], "model": parent_route[0], "effort": parent_route[1]},
                    at(0, 3))]
    if spawn_call:
        arguments = {"message": ids["message"], "task_name": ids["path"].rsplit("/", 1)[-1], **(args or {})}
        parent_rows.append(("response_item", {"type": "function_call", "name": "spawn_agent", "namespace": namespace,
                                              "arguments": json.dumps(arguments), "call_id": ids["call"]}, at(0, 4)))
    if not legacy_parent:
        parent_rows.append(("event_msg", {"type": "item_completed", "item": {
            "type": "SubAgentActivity", "id": ids["call"] if spawn_call else ids["nested"], "kind": "started",
            "agent_thread_id": ids["child"], "agent_path": ids["path"]}}, at(0, 5)))
    if spawn_call:
        parent_rows.append(("response_item", {"type": "function_call_output", "call_id": ids["call"],
                                              "output": json.dumps({"task_name": ids["path"], "nickname": ids["nick"]})},
                            at(0, 6)))
    for index, target in enumerate(followups):
        key = f"{ids['followup_call']}-{index}"
        call = ({"name": "resume_agent", "namespace": "multi_agent_v1", "arguments": json.dumps({"id": ids["child"]})}
                if target == "resume" else
                {"name": "followup_task", "namespace": "collaboration",
                 "arguments": json.dumps({"target": ids["child"] if target == "thread" else ids["path"],
                                          "message": ids["followup"]})})
        parent_rows += [("response_item", {"type": "function_call", **call, "call_id": key}, at(0, 7 + 2 * index)),
                        ("response_item", {"type": "function_call_output", "call_id": key, "output": "{}"},
                         at(0, 8 + 2 * index))]
    if legacy_parent:
        parent_rows.append(("event_msg", {"type": "item_completed", "item": {
            "type": "SubAgentActivity", "id": ids["call"], "kind": "completed", "agent_thread_id": ids["child"],
            "agent_path": ids["path"]}}, at(0, 29)))
    parent_rows.append(("event_msg", {"type": "task_complete", "turn_id": ids["turn"]}, at(0, 30)))
    spawn_role = {"agent_role": role} if role else {}
    child_meta = {"id": ids["child"], "source": {"subagent": {"thread_spawn": {
                      "parent_thread_id": ids["other"] if other_parent else ids["parent"], "depth": 1,
                      "agent_path": ids["path"], "agent_nickname": ids["nick"], **spawn_role}}},
                  "agent_nickname": ids["nick"], "agent_path": ids["path"], **spawn_role, "originator": "codex_exec",
                  "cli_version": "0.157.1", "history_mode": "paginated", "multi_agent_version": "v2",
                  **({"subagent_history_start_ordinal": 3} if start else {})}
    child_rows = [("session_meta", child_meta, at(1, 0))]
    if start:  # the parent's history, copied below the start ordinal
        child_rows.append(("session_meta", parent_meta, at(1, 0)))
    child_rows.append(("response_item", developer(CATALOG), at(1, 1)))
    child_rows.append(("event_msg", {"type": "thread_settings_applied", "thread_id": ids["child"], "thread_settings": {
        "model": child_routes[0][0], "model_provider_id": "openai", "reasoning_effort": child_routes[0][1]}}, at(1, 2)))
    for index, (model, effort) in enumerate(child_routes):
        turn = f"{ids['turn']}-child-{index}"
        child_rows += [("event_msg", {"type": "task_started", "turn_id": turn}, at(2 + index, 0)),
                       ("turn_context", {"turn_id": turn, "model": model, "effort": effort}, at(2 + index, 1)),
                       ("event_msg", {"type": "token_count", "info": {"total_token_usage": dict.fromkeys(
                           S.CODEX_COUNTERS, 10 * (index + 1))}}, at(2 + index, 2)),
                       ("event_msg", {"type": "task_complete", "turn_id": turn}, at(2 + index, 3))]
    stem = f"rollout-2026-10-20T{hour:02d}-00-00-u3-spawn-{case}"
    rollouts = {f"{stem}-child.jsonl": [u3_row(kind, payload, t, i) for i, (kind, payload, t) in enumerate(child_rows)]}
    if parent:
        rollouts[f"{stem}-parent.jsonl"] = [u3_row(kind, payload, t, i)
                                            for i, (kind, payload, t) in enumerate(parent_rows)]
    return rollouts


class CodexSpawnJoin(unittest.TestCase):
    """PR-A item 10g, spawn metadata and route states (design section 4, commit 5, with the review's fork_turns, route-basis,
    resume and privacy findings). A sub-agent joins its spawn through its parent's SubAgentActivity started item, whose
    agent_thread_id is the child's thread id and whose id is the spawn_agent call_id (spawn.rs:216-226; items.rs:364-370).
    SpawnAgentArgs are {message, task_name, agent_type, model, reasoning_effort, fork_turns, fork_context}; fork_turns is
    trimmed, absent or empty means all, none and all match ASCII case-insensitively, and otherwise it is a positive integer
    (spawn.rs:253-299). fork_turns is a string at rust-v0.157.1, so a JSON integer fails the call there and yields no child;
    the frozen launch matrix writes `fork_turns: 2` (preregistration.json seed-binding-2), so a positive integer reads as
    last_n as well (the review). The child's route starts from the invoking step, then a spawn value or the [agents] default
    applies (a spawn model or effort, else agent_default_subagent_model or _reasoning_effort, child_config.rs:204-206), a model
    chosen without an effort takes the [agents] default effort, else that model's default effort (:229-238), and a role file
    overrides both (core/src/agent/child_config.rs:109-121, :196-253, :283-299): expected_route_basis is per field. Reroutes are
    not persisted in rollouts (rollout/src/policy.rs:141-204). A resumed child is a followup_task whose target is the child's
    thread id or task path (multi_agents_spec.rs:217-241), or a V1 resume_agent with its id (:246-266). A legacy rollout
    persists no started item (policy.rs:94-112), so its children read parent_without_started_item; a V1 spawn
    (namespace multi_agent_v1) forks when fork_context is true (:607-613). Join keys stay in memory; only states are published."""

    CASES = {
        "c01": {"args": {"fork_turns": "2"}},                                      # C1
        "c02": {"args": {"fork_turns": 2}},                                        # the launch matrix's integer form
        "c03": {},                                                                 # C2: no fork_turns, all by default
        "c04": {"args": {"fork_turns": "none"}, "start": False},                   # C3
        "c05": {"args": {"fork_turns": "none"}},                                   # C3b: a start ordinal despite none
        "c06": {"args": {"fork_turns": " NONE "}, "start": False},                 # trimmed, ASCII case-insensitive
        "c07": {"args": {"fork_turns": "0"}},                                      # invalid: not a positive integer
        "c08": {"args": {"fork_turns": "resume"}},                                 # invalid: resume is no spawn argument
        "c09": {"args": {"agent_type": "stack-researcher"}, "role": "stack-researcher"},                      # C4
        "c10": {"args": {"model": "gpt-6-astra", "reasoning_effort": "high"}, "child_routes": (("gpt-6-astra", "high"),)},
        "c11": {"args": {"model": "gpt-6-sol"}, "child_routes": (("gpt-6-sol", "medium"),)},  # a model-only override
        "c12": {"parent_route": ("gpt-6-astra", "medium")},                        # C6
        "c13": {"parent": False},                                                  # C7
        "c14": {"spawn_call": False},                                              # C8: a nested code-mode spawn
        "c15": {"args": {"model": "cx/gpt-6-astra"}, "child_routes": (("cx/gpt-6-sol", "max"),)},            # C9
        "c16": {"child_routes": (SPAWN_ROUTE, SPAWN_ROUTE)},                       # C10
        "c17": {"child_routes": (SPAWN_ROUTE, ("gpt-6-astra", "high"))},           # a route change within the child
        "c18": {"child_routes": (SPAWN_ROUTE, SPAWN_ROUTE), "followups": ("thread", "path")},                 # a resume
        "c19": {"other_parent": True},                                             # parent_mismatch
        "c20": {"args": {"agent_type": "stack-researcher"}, "role": "other-role"},  # a role mismatch
        "c21": {"role": "default"},                                                # a configured default role
        "c22": {"legacy_parent": True},                                            # no started item persisted
        "c23": {"namespace": "multi_agent_v1", "args": {"fork_context": False}, "start": False,
                "followups": ("resume",)},                                          # a V1 spawn, resumed by id
    }

    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name) / "spawn"
        rollouts = {}
        for case, options in cls.CASES.items():
            rollouts.update(spawn_case(case, **options))
        write_rollouts(cls.root, rollouts)
        cls.since, cls.until = S.parse_iso(LANES_SINCE), S.parse_iso(LANES_UNTIL)
        cls.scan = S.scan_codex_lanes([cls.root], load_fixture_manifest(), since=cls.since, until=cls.until, marker=MARKER)
        cls.children = [actor for actor in cls.scan["actors"] if actor["kind"] == "subagent"]
        cls.by_case = dict(zip(cls.CASES, cls.children))
        cls.secrets = [str(cls.root)] + [value for case in cls.CASES for value in spawn_ids(case).values()]

    def field(self, case, *path):
        value = self.by_case[case].get("spawn")
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        return value

    def report(self) -> dict:
        return S.build_lanes_report(self.scan, since=self.since, until=self.until, marker=MARKER, now=S.parse_iso(NOW))

    def test_every_spawn_case_is_an_actor(self):
        # Must stay: one child per case (in file order) and one parent per case but C7's.
        self.assertEqual(len(self.children), len(self.CASES))
        self.assertEqual(sum(actor["kind"] == "exec" for actor in self.scan["actors"]), len(self.CASES) - 1)

    def test_the_id_free_check_catches_a_leak(self):
        # The review's privacy finding: the check passes on the published report, and fails when the report carries a private
        # join key or a private value (negative controls), so a leak from the join would be caught.
        report = self.report()
        assert_id_free_report(self, report, self.secrets)
        leaked = json.loads(json.dumps(report))
        leaked["actors"][0]["_thread_id"] = "x"
        with self.assertRaises(AssertionError):
            assert_id_free_report(self, leaked, self.secrets)
        leaked = json.loads(json.dumps(report))
        leaked["actors"][0]["spawn_note"] = spawn_ids("c01")["child"]
        with self.assertRaises(AssertionError):
            assert_id_free_report(self, leaked, self.secrets)

    def test_the_join_publishes_states_only(self):
        self.assertEqual([case for case in self.CASES if not self.field(case)], [])
        assert_id_free_report(self, self.report(), self.secrets)

    def test_join_states(self):
        expected = {**dict.fromkeys(self.CASES, "joined"), "c13": "parent_not_scanned",
                    "c14": "activity_without_spawn_call", "c19": "parent_mismatch", "c22": "parent_without_started_item"}
        self.assertEqual({case: self.field(case, "join") for case in self.CASES}, expected)
        self.assertEqual({case: self.field(case, "reroute_evidence") for case in self.CASES},
                         dict.fromkeys(self.CASES, "not_persisted_in_rollout"))
        self.assertEqual(self.scan.get("subagent_spawns", {}).get("join"),
                         {"joined": 19, "parent_not_scanned": 1, "activity_without_spawn_call": 1, "parent_mismatch": 1,
                          "parent_without_started_item": 1})

    def test_requested_fork_turns_and_fork_consistency(self):
        got = {case: (self.field(case, "requested", "fork_turns"), self.field(case, "requested", "fork_n"),
                      self.field(case, "effective", "history"), self.field(case, "fork_consistent"))
               for case in ("c01", "c02", "c03", "c04", "c05", "c06", "c07", "c08", "c13")}
        self.assertEqual(got, {"c01": ("last_n", 2, "forked", True), "c02": ("last_n", 2, "forked", True),
                               "c03": ("default_all", None, "forked", True), "c04": ("none", None, "fresh", True),
                               "c05": ("none", None, "forked", False), "c06": ("none", None, "fresh", True),
                               "c07": ("invalid", None, "forked", None), "c08": ("invalid", None, "forked", None),
                               "c13": ("unknown", None, "forked", None)})

    def test_role_state_and_route_basis(self):
        parent_turn = {"model": "agents_default_or_parent_turn", "effort": "agents_default_or_parent_turn"}
        role_file = {"model": "role_file", "effort": "role_file"}
        got = {case: (self.field(case, "requested", "role"), self.field(case, "effective", "role"),
                      self.field(case, "role_state"), self.field(case, "expected_route_basis"))
               for case in ("c01", "c09", "c10", "c11", "c20", "c21")}
        self.assertEqual(got, {
            "c01": (None, "(none)", "not_requested", parent_turn),
            "c09": ("stack-researcher", "stack-researcher", "match", role_file),
            "c10": (None, "(none)", "not_requested", {"model": "spawn_request", "effort": "spawn_request"}),
            # A model without an effort takes the [agents] default effort, else the model's (child_config.rs:204-206, :229-238).
            "c11": (None, "(none)", "not_requested", {"model": "spawn_request", "effort": "agents_default_or_model_default"}),
            "c20": ("stack-researcher", "other-role", "mismatch", role_file),
            "c21": (None, "default", "not_requested", role_file)})
        self.assertEqual((self.field("c13", "requested", "role"), self.field("c13", "role_state")), ("unknown", "unknown"))

    def test_route_versus_request_and_parent_turn(self):
        def states(model, effort):
            return {"model": model, "effort": effort}
        got = {case: (self.field(case, "requested", "model"), self.field(case, "requested", "effort"),
                      self.field(case, "route_vs_request"), self.field(case, "route_vs_parent_turn"))
               for case in ("c01", "c10", "c11", "c12", "c13", "c15")}
        self.assertEqual(got, {
            "c01": (None, None, states("not_requested", "not_requested"), states("match", "match")),
            "c10": ("gpt-6-astra", "high", states("match", "match"), states("match", "mismatch")),
            "c11": ("gpt-6-sol", None, states("match", "not_requested"), states("mismatch", "mismatch")),
            "c12": (None, None, states("not_requested", "not_requested"), states("match", "mismatch")),
            "c13": ("unknown", "unknown", states("unknown", "unknown"), states("unknown", "unknown")),
            # C9: raw values differ (safe_key would have read both as (other) and matched them).
            "c15": ("cx/gpt-6-astra", None, states("mismatch", "not_requested"), states("mismatch", "match"))})

    def test_effective_route_turns_and_followups(self):
        self.assertEqual(self.field("c01", "effective"),
                         {"role": "(none)", "history": "forked", "turns": 1, "models": ["gpt-6-astra"], "efforts": ["max"],
                          "settings": {"model": "gpt-6-astra", "effort": "max"}})
        self.assertEqual((self.field("c01", "route_changes_within_child"), self.field("c01", "followups")), (False, 0))
        self.assertEqual(self.field("c15", "effective", "models"), ["cx/gpt-6-sol"])
        got = {case: (self.field(case, "effective", "turns"), self.field(case, "route_changes_within_child"),
                      sorted(self.field(case, "effective", "efforts") or []), self.field(case, "followups"))
               for case in ("c16", "c17", "c18")}
        self.assertEqual(got, {"c16": (2, False, ["max"], 0), "c17": (2, True, ["high", "max"], 0),
                               "c18": (2, False, ["max"], 2)})

    def test_legacy_parents_v1_spawns_and_unscanned_parents(self):
        got = {case: (self.field(case, "join"), self.field(case, "requested", "fork_turns"), self.field(case, "effective", "history"),
                      self.field(case, "fork_consistent"), self.field(case, "followups"))
               for case in ("c13", "c19", "c22", "c23")}
        self.assertEqual(got, {"c13": ("parent_not_scanned", "unknown", "forked", None, None),
                               "c19": ("parent_mismatch", "unknown", "forked", None, None),
                               "c22": ("parent_without_started_item", "unknown", "forked", None, 0),
                               "c23": ("joined", "none", "fresh", True, 1)})

    def test_subagent_spawns_count_each_state(self):
        spawns = self.scan.get("subagent_spawns", {})
        self.assertEqual(spawns.get("requested.fork_turns"),
                         {"default_all": 11, "invalid": 2, "last_n": 2, "none": 4, "unknown": 4})
        self.assertEqual(spawns.get("fork_consistent"), {"false": 1, "null": 6, "true": 16})
        self.assertEqual(sum(spawns.get("reroute_evidence", {}).values()), len(self.CASES))

    def test_frozen_launch_matrix_forms_join(self):
        # Control for the U3 binding correction: the five child cases of the frozen launch matrix (preregistration.json tasks
        # 64-68: fork_turns none, 2 and all with agent_type stack-researcher, all with agent_type null, and resume) joined end
        # to end, not only through requested_fork_turns. "resume" is no spawn argument (c08 reads it invalid, and upstream
        # fails such a call), so the resumed finished researcher child is its own spawn plus a followup_task to its thread and
        # a second own turn (multi_agents_spec.rs:217-241).
        researcher = "stack-researcher"
        cases = {"m01": {"args": {"fork_turns": "none", "agent_type": researcher}, "role": researcher, "start": False},
                 "m02": {"args": {"fork_turns": 2, "agent_type": researcher}, "role": researcher},
                 "m03": {"args": {"fork_turns": "all", "agent_type": researcher}, "role": researcher},
                 "m04": {"args": {"fork_turns": "all", "agent_type": None}},
                 "m05": {"args": {"agent_type": researcher}, "role": researcher, "followups": ("thread",),
                         "child_routes": (SPAWN_ROUTE, SPAWN_ROUTE)}}
        rollouts = {}
        for case, options in cases.items():
            rollouts.update(spawn_case(case, **options))
        root = write_rollouts(Path(self.enterContext(tempfile.TemporaryDirectory())) / "frozen", rollouts)
        scan = S.scan_codex_lanes([root], load_fixture_manifest(), since=self.since, until=self.until, marker=MARKER)
        assert_id_free_report(self, scan, [str(root)] + [value for case in cases for value in spawn_ids(case).values()])
        spawns = [actor.get("spawn") or {} for actor in scan["actors"] if actor["kind"] == "subagent"]
        got = [(spawn.get("join"), spawn.get("requested", {}).get("fork_turns"), spawn.get("requested", {}).get("fork_n"),
                spawn.get("requested", {}).get("role"), spawn.get("effective", {}).get("history"),
                spawn.get("effective", {}).get("turns"), spawn.get("fork_consistent"), spawn.get("role_state"),
                spawn.get("followups")) for spawn in spawns]
        self.assertEqual(got, [("joined", "none", None, researcher, "fresh", 1, True, "match", 0),
                               ("joined", "last_n", 2, researcher, "forked", 1, True, "match", 0),
                               ("joined", "all", None, researcher, "forked", 1, True, "match", 0),
                               ("joined", "all", None, None, "forked", 1, True, "not_requested", 0),
                               ("joined", "default_all", None, researcher, "forked", 2, True, "match", 1)])

    def test_fork_turns_follow_the_spawn_handler(self):
        # SpawnAgentArgs.fork_turns (spawn.rs:265-299): trimmed with str::trim (Unicode White_Space, not Python's strip), absent,
        # null or empty is all, none and all match ASCII case-insensitively, else usize::from_str (an optional '+' and ASCII
        # digits, within u64) and nonzero. The review's integer form reads as a positive integer string would.
        classify = getattr(S, "requested_fork_turns", None)
        self.assertTrue(callable(classify))
        cases = [(None, ("default_all", None)), ("", ("default_all", None)), (" 　", ("default_all", None)),
                 ("all", ("all", None)), (" ALL ", ("all", None)), ("NoNe", ("none", None)), ("2", ("last_n", 2)),
                 ("+2", ("last_n", 2)), (" 02　", ("last_n", 2)), (2, ("last_n", 2)),
                 ("18446744073709551615", ("last_n", 18446744073709551615)), ("18446744073709551616", ("invalid", None)),
                 ("0", ("invalid", None)), (0, ("invalid", None)), (-1, ("invalid", None)), ("-1", ("invalid", None)),
                 ("2_000", ("invalid", None)), ("٣", ("invalid", None)), ("1e3", ("invalid", None)),
                 ("\x1c2", ("invalid", None)), ("+", ("invalid", None)), ("resume", ("invalid", None)),
                 (True, ("invalid", None)), (2.0, ("invalid", None)), (["2"], ("invalid", None)),
                 ("Kll", ("invalid", None))]
        self.assertEqual([(value, classify(value)) for value, _ in cases], cases)

    def test_copied_spawn_records_stay_the_parents(self):
        # A forked child copies its parent's history below subagent_history_start_ordinal: here an earlier spawn_agent call and
        # the sibling's started item, the parent's turn context and its settings. They are the parent's records. The sibling
        # joins the parent, never the forked child: with the parent outside the roots it reads parent_not_scanned, not
        # parent_mismatch. The forked child's route, turns and settings are its own.
        def rows(*records):
            return [u3_row(kind, payload, f"2026-10-20T08:{i // 60:02d}:{i % 60:02d}Z", i) for i, (kind, payload) in enumerate(records)]
        parent_meta = {"id": "thread-P-PRIV", "source": "exec", "history_mode": "paginated"}

        def spawn(call, child, path, args):
            return [("response_item", {"type": "function_call", "name": "spawn_agent", "namespace": "collaboration",
                                       "call_id": call, "arguments": json.dumps({"message": "PRIV m", "task_name": path[6:], **args})}),
                    ("event_msg", {"type": "item_completed", "item": {"type": "SubAgentActivity", "id": call, "kind": "started",
                                                                      "agent_thread_id": child, "agent_path": path}}),
                    ("response_item", {"type": "function_call_output", "call_id": call, "output": "{}"})]
        parent = [("session_meta", parent_meta), ("response_item", developer(CATALOG)), ("event_msg", {"type": "task_started"}),
                  ("turn_context", {"model": "gpt-6-sol", "effort": "low"}),
                  ("event_msg", {"type": "thread_settings_applied", "thread_id": "thread-P-PRIV",
                                 "thread_settings": {"model": "gpt-6-sol", "reasoning_effort": "low"}}),
                  *spawn("call-A-PRIV", "thread-A-PRIV", "/root/PRIV_a", {"fork_turns": "none"}),
                  *spawn("call-B-PRIV", "thread-B-PRIV", "/root/PRIV_b", {}), ("event_msg", {"type": "task_complete"})]

        def child(thread, path, copied):
            meta = {"id": thread, "source": {"subagent": {"thread_spawn": {"parent_thread_id": "thread-P-PRIV", "depth": 1,
                                                                             "agent_path": path}}},
                    "agent_path": path, "history_mode": "paginated", "multi_agent_version": "v2",
                    **({"subagent_history_start_ordinal": len(copied) + 1} if copied else {})}
            return rows(("session_meta", meta), *copied, ("response_item", developer(CATALOG)),
                        ("event_msg", {"type": "thread_settings_applied", "thread_id": thread,
                                       "thread_settings": {"model": "gpt-6-astra", "reasoning_effort": "max"}}),
                        ("event_msg", {"type": "task_started"}), ("turn_context", {"model": "gpt-6-astra", "effort": "max"}),
                        ("event_msg", {"type": "task_complete"}))
        rollouts = {"rollout-2026-10-20T08-00-01-u3-copied-a.jsonl": child("thread-A-PRIV", "/root/PRIV_a", ()),
                    # B forks after its own spawn call: it copies the parent's records up to that call, sibling A's included.
                    "rollout-2026-10-20T08-00-02-u3-copied-b.jsonl": child("thread-B-PRIV", "/root/PRIV_b", parent[:9])}
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

        def scan(with_parent):
            files = {**rollouts, **({"rollout-2026-10-20T08-00-00-u3-copied-p.jsonl": rows(*parent)} if with_parent else {})}
            got = S.scan_codex_lanes([write_rollouts(tmp / str(with_parent), files)], load_fixture_manifest(),
                                     since=self.since, until=self.until, marker=MARKER)
            assert_id_free_report(self, got, ["PRIV", str(tmp)])
            return [actor.get("spawn") or {} for actor in got["actors"] if actor["kind"] == "subagent"]
        a, b = scan(True)
        self.assertEqual((a.get("join"), a.get("requested", {}).get("fork_turns"), a.get("effective", {}).get("history"),
                          a.get("fork_consistent")), ("joined", "none", "fresh", True))
        self.assertEqual((b.get("join"), b.get("requested", {}).get("fork_turns"), b.get("fork_consistent")),
                         ("joined", "default_all", True))
        self.assertEqual(b.get("effective"), {"role": "(none)", "history": "forked", "turns": 1, "models": ["gpt-6-astra"],
                                              "efforts": ["max"], "settings": {"model": "gpt-6-astra", "effort": "max"}})
        self.assertEqual((b.get("route_changes_within_child"), b.get("route_vs_parent_turn")),
                         (False, {"model": "mismatch", "effort": "mismatch"}))
        self.assertEqual([spawn.get("join") for spawn in scan(False)], ["parent_not_scanned", "parent_not_scanned"])


# The client version is one whose code-mode isolate was read (the 10e outer-JS decision, commit 8).
PAGINATED_META = u3_row("session_meta", {"id": "u3-session", "source": "exec", "history_mode": "paginated",
                                         "cli_version": "0.157.1"})
LEGACY_META = u3_row("session_meta", {"id": "u3-session", "source": "exec",  # legacy by default (protocol.rs:772-779)
                                      "cli_version": "0.157.1"})
EXPLICIT_LEGACY_META = u3_row("session_meta", {"id": "u3-session", "source": "exec", "history_mode": "legacy",
                                               "cli_version": "0.157.1"})
EXEC_FETCH_JS = "const r = await tools.exec_command({cmd: 'curl https://example.org'}); text(r.output)"


def sourced_command(key, argv, source, output="ok"):
    """A CommandExecution item with its ExecCommandSource (protocol.rs:3534-3544)."""
    return codex_row("event_msg", {"type": "item_completed", "item": {
        "type": "CommandExecution", "id": key, "command": argv, "source": source, "status": "completed", "exit_code": 0,
        "aggregated_output": output}})


def exec_call(key, code):
    return codex_row("response_item", {"type": "custom_tool_call", "call_id": key, "name": "exec", "input": code})


def exec_output(key, output="done"):
    return codex_row("response_item", {"type": "custom_tool_call_output", "call_id": key, "output": output})


def shell_function_call(key, arguments, output):
    return [codex_row("response_item", {"type": "function_call", "call_id": key, "name": "exec_command",
                                        "arguments": json.dumps(arguments)}),
            codex_row("response_item", {"type": "function_call_output", "call_id": key, "output": output})]


def u3_measure(*rows):
    return S.measure_codex_records(list(rows), since=S.parse_iso(LANES_SINCE), until=S.parse_iso(LANES_UNTIL))


class CodexCommandNormalization(unittest.TestCase):
    """The Codex normalization for U1's commandInvocations (design section 6, commit 6, with the review's shell_script
    finding: shell_script keeps returning the text and use() gets a separate resolver). exec_command takes cmd and an
    optional shell (core/src/tools/handlers/shell_spec.rs:15-110): a shell that is not a POSIX shell leaves the command
    unresolved, counted in codex_commands.non_posix_shell, with no lane and M4 incomplete (the review: its fetches cannot be
    seen). A CommandExecution's source is agent, user_shell, unified_exec_startup or unified_exec_interaction
    (protocol.rs:3534-3544). A user_shell command is the user's own (core/src/tasks/user_shell.rs:199) and its output is
    recorded as a conversation item, not a tool result (:453-480), so it is no model call (codex_commands.user_shell); an
    interaction item is not an invocation (codex_commands.exec_interactions; no core code sets that source at
    rust-v0.157.1, so this is conservative). The legacy lane counters keep counting every CommandExecution."""

    @unittest.skipUnless(PARSER_INSTALLED, "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
    def test_non_posix_shells_are_unresolved(self):
        got = u3_measure(PAGINATED_META,
                         *shell_function_call("call_priv_n1", {"cmd": "qmd search x", "shell": "/usr/bin/pwsh"},
                                              exec_response("Process exited with code 0", "ok")),
                         sourced_command("item_n2", ["pwsh", "-Command", "qmd search x"], "unified_exec_startup"),
                         sourced_command("item_n3", ["cmd.exe", "/c", "qmd search x"], "unified_exec_startup"))
        self.assertEqual(got["cli_lanes"].get("lanes"), {})
        self.assertEqual(got.get("codex_commands", {}).get("non_posix_shell"), 3)
        self.assertEqual(got["m4"]["status"], "incomplete")

    def test_user_shell_commands_are_not_model_calls(self):
        # E3.
        got = u3_measure(PAGINATED_META,
                         sourced_command("item_u1", ["bash", "-lc", "curl https://example.org"], "user_shell"))
        self.assertEqual((got["m4"]["remote_fetches"], got["m3"]["results"], got["sandbox_operations"]), (0, 0, 0))
        self.assertEqual(got.get("codex_commands", {}).get("user_shell"), 1)

    @unittest.skipUnless(PARSER_INSTALLED, "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
    def test_exec_interactions_are_not_invocations(self):
        got = u3_measure(PAGINATED_META,
                         sourced_command("item_i1", ["bash", "-lc", "qmd search x"], "unified_exec_interaction"))
        self.assertEqual(got["cli_lanes"].get("lanes"), {})
        self.assertEqual(got.get("codex_commands", {}).get("exec_interactions"), 1)

    @unittest.skipUnless(PARSER_INSTALLED, "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
    def test_posix_shells_and_argv_arrays_keep_their_lanes(self):
        # Must stay: a POSIX shell argument changes nothing, and E1 (an mcporter argv array) already reads as one command
        # after U1's per-element quoting (pivot D6), so its downstream is (stdio).
        for shell in ("/bin/zsh", "bash"):
            with self.subTest(shell=shell):
                got = u3_measure(PAGINATED_META, *shell_function_call(
                    "call_priv_z1", {"cmd": "qmd search x", "shell": shell}, exec_response("Process exited with code 0", "ok")))
                self.assertEqual(got["cli_lanes"]["lanes"].get("qmd", {}).get("calls"), 1)
        argv = ["mcporter", "call", "npx -y chrome-devtools-mcp@latest", "list_pages"]
        self.assertEqual(S.shell_script(argv), "mcporter call 'npx -y chrome-devtools-mcp@latest' list_pages")
        got = u3_measure(PAGINATED_META, *code_mode_command("call_priv_e1", argv, "completed", 0, "[]"))
        self.assertEqual(got["cli_lanes"]["mcporter_downstream"].get("(stdio)", {}).get("calls"), 1)

    def test_a_python_c_body_is_a_possible_fetch_not_a_command(self):
        # Must stay: E4 at the rebased parent fe9f511b (the review asked for its unconfirmed count and status). The quoted
        # body is interpreter code, so a `curl = 2` line is no command, only a raw possible fetch.
        got = u3_measure(PAGINATED_META,
                         codex_row("response_item", {"type": "local_shell_call", "call_id": "call_priv_e4", "status": "completed",
                                                     "action": {"type": "exec",
                                                                "command": ["python3", "-c", "import os\ncurl = 2\nprint(curl)"]}}),
                         codex_row("response_item", {"type": "function_call_output", "call_id": "call_priv_e4", "output": "2"}))
        self.assertEqual({key: got["m4"][key] for key in ("remote_fetches", "unclassifiable", "fetch_mentions_unconfirmed", "status")},
                         {"remote_fetches": 0, "unclassifiable": 0, "fetch_mentions_unconfirmed": 1, "status": "incomplete"})

    def test_legacy_lane_counters_keep_every_command_execution(self):
        # Must stay (the review's shell_script finding): the legacy shell, rtk-prefix and fetch counters are historical
        # comparison fields, so user_shell, interaction and non-POSIX commands keep counting there.
        manifest = load_fixture_manifest()
        root = write_rollouts(Path(self.enterContext(tempfile.TemporaryDirectory())), {
            "rollout-2026-10-20T02-00-00-u3-legacy-lanes.jsonl": [
                PAGINATED_META, codex_row("response_item", developer(CATALOG)),
                sourced_command("item_l1", ["bash", "-lc", "curl https://example.org"], "user_shell"),
                sourced_command("item_l2", ["bash", "-lc", "rtk ls"], "unified_exec_interaction"),
                sourced_command("item_l3", ["pwsh", "-Command", "qmd search x"], "unified_exec_startup")]})
        session = S.scan_lanes_file(next(root.glob("rollout-*.jsonl")), fixture_names(), since=S.parse_iso(LANES_SINCE),
                                    until=S.parse_iso(LANES_UNTIL), marker=MARKER,
                                    codex_off=[s["name"] for s in manifest["skills"] if s["codex_enabled"] is False],
                                    codex_on=[s["name"] for s in manifest["skills"] if s["codex_enabled"] is True])[0]
        self.assertEqual((session["shell_calls"], session["rtk_prefixed"], session["fetch"]["shell_curl_wget"]), (3, 1, 1))

    @unittest.skipUnless(PARSER_INSTALLED, "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
    def test_a_shell_is_typed_by_its_name_or_file_stem(self):
        # exec_command's shell only selects a ShellType, by the value or else its file stem, case-sensitively
        # (shell-command/src/shell_detect.rs:39-59, :329-334): pwsh, powershell and cmd are not POSIX (a Windows path included),
        # zsh, bash and sh are. A name Codex does not know (dash) runs its fallback shell, /bin/sh on Unix and cmd.exe on Windows
        # (:315-327), which the rollout does not record, so it is unresolved too (unknown_shell). Without --rtk-check nothing
        # is replayed, so no unknown call is added.
        ok = exec_response("Process exited with code 0", "ok")
        got = u3_measure(PAGINATED_META,
                         *shell_function_call("call_priv_s1", {"cmd": "qmd search x", "shell": "dash"}, ok),
                         *shell_function_call("call_priv_s2", {"cmd": "qmd search x",
                                                               "shell": "C:\\Program Files\\PowerShell\\7\\pwsh.exe"}, ok),
                         sourced_command("item_s3", ["C:\\Windows\\System32\\cmd.exe", "/c", "qmd search x"], "unified_exec_startup"),
                         sourced_command("item_s4", ["powershell.exe", "-NoProfile", "-Command", "qmd search x"], "agent"),
                         *shell_function_call("call_priv_s5", {"cmd": "qmd search x", "shell": "/usr/bin/sh"}, ok))
        self.assertEqual(got.get("codex_commands"), {"non_posix_shell": 3, "unknown_shell": 1, "user_shell": 0,
                                                     "exec_interactions": 0})
        self.assertEqual({lane: row["calls"] for lane, row in got["cli_lanes"]["lanes"].items()}, {"qmd": 1})
        self.assertEqual(got["m4"]["status"], "incomplete")
        self.assertEqual((got["rtk_parts"]["status"], got["rtk_parts"]["unknown_calls"]), ("not_measured", 0))

    def test_a_command_counts_once_in_the_window_of_its_first_record(self):
        # As the kernel keeps a call's first tool_use: a function_call and its own CommandExecution item are one call, counted
        # where the first record is, in [since, until); an item's own counters likewise, so adjacent windows add up.
        def at(hour, minute, row):
            return {**row, "timestamp": f"2026-10-20T{hour:02d}:{minute:02d}:00Z"}
        pwsh = ["pwsh", "-Command", "qmd search x"]
        call, output = shell_function_call("call_priv_w1", {"cmd": "qmd search x", "shell": "pwsh"},
                                           exec_response("Process exited with code 0", "ok"))
        rows = [at(0, 30, PAGINATED_META), at(1, 0, call), at(1, 0, output),
                at(1, 1, sourced_command("call_priv_w1", pwsh, "unified_exec_startup")),
                at(1, 30, sourced_command("item_w3", ["bash", "-lc", "ls"], "user_shell")),
                at(2, 30, sourced_command("item_w5", ["bash", "-lc", "ls"], "unified_exec_interaction")),
                at(3, 0, sourced_command("item_w2", pwsh, "unified_exec_startup")),
                at(3, 30, sourced_command("item_w4", ["bash", "-lc", "ls"], "user_shell"))]

        def commands(since, until):
            got = S.measure_codex_records(rows, since=S.parse_iso(f"2026-10-20T{since:02d}:00:00Z"),
                                          until=S.parse_iso(f"2026-10-20T{until:02d}:00:00Z"))
            return got.get("codex_commands", {})
        whole, first, second = commands(0, 4), commands(0, 2), commands(2, 4)
        self.assertEqual(whole, {"non_posix_shell": 2, "unknown_shell": 0, "user_shell": 2, "exec_interactions": 1})
        self.assertEqual(first, {"non_posix_shell": 1, "unknown_shell": 0, "user_shell": 1, "exec_interactions": 0})
        self.assertEqual({key: first.get(key, 0) + second.get(key, 0) for key in whole}, whole)

    def test_skipped_items_leave_no_result_and_groups_stay_incomplete(self):
        # A user_shell or interaction item is no call: neither a tool_use nor a result (no orphan, nothing in M3). The kernel
        # recomputes a group's M4 status from its counts, so an unresolved command is forced incomplete there as well.
        got = u3_measure(PAGINATED_META, sourced_command("item_k1", ["bash", "-lc", "ls"], "user_shell", "z" * 6000),
                         sourced_command("item_k2", ["bash", "-lc", "ls"], "unified_exec_interaction", "z" * 6000))
        self.assertEqual((got["m3"]["results"], got["orphan_results"], got["calls_without_result"], got["sandbox_operations"]),
                         (0, 0, 0, 0))
        root = write_rollouts(Path(self.enterContext(tempfile.TemporaryDirectory())), {
            "rollout-2026-10-20T02-00-00-u3-unresolved.jsonl": [
                PAGINATED_META, codex_row("response_item", developer(CATALOG)),
                sourced_command("item_k3", ["pwsh", "-Command", "curl https://example.org"], "unified_exec_startup")]})
        scan = S.scan_codex_lanes([root], load_fixture_manifest(), since=S.parse_iso(LANES_SINCE), until=S.parse_iso(LANES_UNTIL),
                                  marker=MARKER)
        for measurement in (scan["actors"][0]["measurement"], scan["groups"]["workers"]["measurement"]):
            self.assertEqual((measurement["m4"]["status"], measurement.get("codex_commands", {}).get("non_posix_shell")),
                             ("incomplete", 1))

    @unittest.skipUnless(RTK_REPLAY_SUPPORTED, "RTK replay needs Linux and rtk 0.50.0 on PATH")
    def test_rtk_replay_reports_an_unresolved_command_as_unknown(self):
        # The review: an unresolved command reaches replay as an empty Bash command (rtk 0.50.0 answers "No rewrite for:", no
        # parts), so it is reported as an explicit unknown call instead of a measured call without parts.
        got = S.measure_codex_records([PAGINATED_META, sourced_command("item_r1", ["pwsh", "-Command", "git status"], "agent"),
                                       sourced_command("item_r2", ["bash", "-lc", "git status"], "agent")],
                                      since=S.parse_iso(LANES_SINCE), until=S.parse_iso(LANES_UNTIL), rtk_check=True)
        rtk = got["rtk_parts"]
        self.assertEqual((rtk["calls"], rtk["unknown_calls"], rtk["eligible_parts"], rtk["status"]), (2, 1, 1, "incomplete"))

    @unittest.skipUnless(PARSER_INSTALLED, "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
    def test_argv_programs_and_shell_values_are_typed_by_their_stems(self):
        # An argv runs its program directly, so the program's file stem types it, with / and \ as separators: a Windows Git
        # Bash path is a POSIX shell, and CMD.EXE is cmd (Windows resolves program names ASCII case-insensitively).
        # exec_command's shell goes through detect_shell_type (shell-command/src/shell_detect.rs:39-59): the file stem again
        # and again (pwsh.exe.bak is pwsh), case-sensitively (PWSH is no name Codex knows, so the unrecorded fallback shell
        # ran). A shell that is not a string fails ExecCommandArgs (Option<String>, core/src/tools/handlers/unified_exec.rs:
        # 27-33), so what ran is unknown; null reads as None, the session shell (:117-121).
        ok = exec_response("Process exited with code 0", "ok")
        got = u3_measure(PAGINATED_META,
                         sourced_command("item_t1", ["C:\\Program Files\\Git\\bin\\bash.exe", "-lc", "qmd search x"], "agent"),
                         sourced_command("item_t2", ["CMD.EXE", "/c", "qmd search x"], "agent"),
                         *shell_function_call("call_priv_t3", {"cmd": "qmd search x", "shell": "pwsh.exe.bak"}, ok),
                         *shell_function_call("call_priv_t4", {"cmd": "qmd search x", "shell": "PWSH"}, ok),
                         *shell_function_call("call_priv_t5", {"cmd": "qmd search x", "shell": 7}, ok),
                         *shell_function_call("call_priv_t6", {"cmd": "qmd search x", "shell": None}, ok))
        self.assertEqual(got.get("codex_commands"), {"non_posix_shell": 2, "unknown_shell": 2, "user_shell": 0,
                                                     "exec_interactions": 0})
        self.assertEqual({lane: row["calls"] for lane, row in got["cli_lanes"]["lanes"].items()}, {"qmd": 2})

    def test_a_c_option_among_short_options_names_the_script(self):
        # bash(1) INVOCATION: with -c among the options, commands are read from the first non-option argument, so -cl and
        # -e -c name the script as -lc does, and -o takes the next word (pipefail) as its option name. The PR-A reading took
        # only -lc and -c and joined any other argv, and the kernel then read a -cl script, or one after -o pipefail, as data
        # and missed its fetch. The legacy counters keep shell_script's reading (must stay).
        self.assertEqual(S.shell_script(["bash", "-cl", "curl https://example.org"]), "bash -cl 'curl https://example.org'")
        got = u3_measure(PAGINATED_META,
                         sourced_command("item_c1", ["bash", "-cl", "curl https://example.org"], "agent"),
                         sourced_command("item_c2", ["bash", "-o", "pipefail", "-c", "curl https://example.net"], "agent"),
                         sourced_command("item_c3", ["zsh", "-e", "-c", "curl https://example.com"], "agent"))
        self.assertEqual((got["m4"]["shell_fetch"], got["m4"]["status"]), (3, "measured"))
        self.assertEqual(got.get("codex_commands"), {"non_posix_shell": 0, "unknown_shell": 0, "user_shell": 0,
                                                     "exec_interactions": 0})

    @unittest.skipUnless(RTK_REPLAY_SUPPORTED, "RTK replay needs Linux and rtk 0.50.0 on PATH")
    def test_rtk_replay_reads_the_script_of_a_c_option_cluster(self):
        # -ec runs its script as -lc does, so replay reads `git status` (one eligible part), not the joined argv, which rtk
        # 0.50.0 does not rewrite (one ineligible part).
        got = S.measure_codex_records([PAGINATED_META, sourced_command("item_r3", ["bash", "-ec", "git status"], "agent")],
                                      since=S.parse_iso(LANES_SINCE), until=S.parse_iso(LANES_UNTIL), rtk_check=True)
        rtk = got["rtk_parts"]
        self.assertEqual((rtk["calls"], rtk["eligible_parts"], rtk["ineligible_parts"], rtk["unknown_calls"]), (1, 1, 0, 0))


class CodexCodeModeAttribution(unittest.TestCase):
    """PR-A item 10e (design section 7, commits 7 and 8, with the review's position, per-exec, item-kind and outer-JS
    findings). Code mode runs raw JavaScript in a V8 isolate with "no Node, no file system, no network access, no console"
    (code-mode-protocol/src/description.rs:19-24) whose only globals are tools, ALL_TOOLS, clearTimeout, setTimeout, text,
    image, audio, generatedImage, store, load, notify, yield_control and exit (code-mode-runtime/src/runtime/globals.rs:36-48),
    so a network operation is a nested tool call and the outer JavaScript is never scanned for fetches. A cell can outlive
    its exec return through the code-mode `wait` tool (code-mode-protocol/src/lib.rs:51-52; the multi-agent wait is
    wait_agent, core/src/tools/handlers/multi_agents_v2/wait.rs:23-24). Commit 7: an emitted item (CommandExecution,
    McpToolCall or a web.search Extension) whose id is no model call id is nested when it follows an exec call of the same
    turn; otherwise it is direct and counted in code_mode.unattributed_items; a `wait` call without a namespace after an exec
    is code mode. Commit 8: a paginated rollout persists every ItemCompleted and a legacy one none of these items
    (rollout/src/policy.rs:94-112), and a meta without history_mode is legacy (protocol.rs:772-779); a legacy exec with a
    static fetch-capable site (tools.exec_command, tools.web__run, tools.mcp__*__ctx_execute, ctx_execute_file,
    ctx_batch_execute or ctx_fetch_and_index) and no item of its own (after it and before the next exec call or turn
    boundary) is an unobservable span that makes M4 incomplete."""

    def retained_rows(self, stem):
        root = materialize_lanes_root(Path(self.enterContext(tempfile.TemporaryDirectory())))
        rows = []
        for line in next(root.glob(f"rollout-*-lanes-{stem}.jsonl")).read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass  # the worker fixture includes one malformed row
        return rows

    def test_items_after_the_exec_return_and_wait_outputs_are_code_mode(self):
        # D: a nested curl that completes after the exec returned, and a code-mode wait with its output.
        got = u3_measure(PAGINATED_META, exec_call("call_priv_x", EXEC_FETCH_JS), exec_output("call_priv_x", "started"),
                         sourced_command("item_y", ["bash", "-lc", "curl https://example.org"], "unified_exec_startup",
                                         "z" * 6000),
                         codex_row("response_item", {"type": "function_call", "call_id": "call_priv_w", "name": "wait",
                                                     "arguments": json.dumps({"cell_id": "1"})}),
                         codex_row("response_item", {"type": "function_call_output", "call_id": "call_priv_w",
                                                     "output": "w" * 100}))
        self.assertEqual({key: got["m4"][key] for key in ("shell_fetch", "ctx_sandbox_fetch")},
                         {"shell_fetch": 0, "ctx_sandbox_fetch": 1})
        self.assertEqual((got["m3"]["results"], got["m3"]["large_results"]), (2, 0))
        self.assertEqual({carrier: sizes["results"] for carrier, sizes in got["by_carrier"].items()}, {"code_mode": 2})
        self.assertEqual(got["sandbox_operations"], 1)
        self.assertEqual({key: got.get("code_mode", {}).get(key)
                          for key in ("exec_calls", "wait_calls", "nested_items", "unattributed_items")},
                         {"exec_calls": 1, "wait_calls": 1, "nested_items": 1, "unattributed_items": 0})

    def test_nesting_is_bounded_by_the_exec_position_and_the_turn(self):
        # The review's position finding: an item before the turn's first exec, or in a later turn without one, is direct.
        got = u3_measure(PAGINATED_META, codex_row("event_msg", {"type": "task_started"}),
                         sourced_command("item_before", ["bash", "-lc", "curl https://example.org/a"], "unified_exec_startup"),
                         exec_call("call_priv_x", EXEC_FETCH_JS), exec_output("call_priv_x"),
                         sourced_command("item_after", ["bash", "-lc", "curl https://example.org/b"], "unified_exec_startup"),
                         codex_row("event_msg", {"type": "task_complete"}), codex_row("event_msg", {"type": "task_started"}),
                         sourced_command("item_next", ["bash", "-lc", "curl https://example.org/c"], "unified_exec_startup"),
                         codex_row("event_msg", {"type": "task_complete"}))
        self.assertEqual(got["sandbox_operations"], 1)
        self.assertEqual({key: got["m4"][key] for key in ("shell_fetch", "ctx_sandbox_fetch")},
                         {"shell_fetch": 2, "ctx_sandbox_fetch": 1})
        self.assertEqual({key: got.get("code_mode", {}).get(key) for key in ("nested_items", "unattributed_items")},
                         {"nested_items": 1, "unattributed_items": 2})

    @unittest.skipUnless(PARSER_INSTALLED, "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
    def test_a_nested_rtk_proxy_after_the_exec_return_counts_as_nested(self):
        # U1's nested counters move with the attribution (the design's list of changed meanings).
        got = u3_measure(PAGINATED_META, exec_call("call_priv_x", "await tools.exec_command({cmd: 'rtk proxy pytest -q'})"),
                         exec_output("call_priv_x"),
                         sourced_command("item_p", ["bash", "-lc", "rtk proxy pytest -q"], "unified_exec_startup", "4 passed"))
        self.assertEqual(got["proxy"]["nested"], 1)
        self.assertEqual(got["cli_lanes"]["lanes"].get("rtk_proxy", {}).get("by_carrier", {}).get("nested"), 1)

    def test_model_calls_after_an_exec_stay_direct(self):
        # Must stay: the model-call-id test comes first (the review), so a direct exec_command after an exec is direct.
        got = u3_measure(PAGINATED_META, exec_call("call_priv_x", EXEC_FETCH_JS),
                         codex_row("response_item", {"type": "function_call", "call_id": "call_priv_z", "name": "exec_command",
                                                     "arguments": json.dumps({"cmd": "curl https://example.org"})}),
                         sourced_command("call_priv_z", ["bash", "-lc", "curl https://example.org"], "unified_exec_startup"),
                         codex_row("response_item", {"type": "function_call_output", "call_id": "call_priv_z",
                                                     "output": exec_response("Process exited with code 0", "ok")}))
        self.assertEqual((got["sandbox_operations"], got["m4"]["shell_fetch"]), (0, 1))

    def test_a_wait_without_an_exec_and_wait_agent_are_not_code_mode(self):
        # Must stay: only a code-mode wait after an exec continues a cell; wait_agent is the multi-agent wait.
        def wait(name, **extra):
            return [codex_row("response_item", {"type": "function_call", "call_id": "call_priv_" + name, "name": name,
                                                "arguments": "{}", **extra}),
                    codex_row("response_item", {"type": "function_call_output", "call_id": "call_priv_" + name,
                                                "output": "w" * 50})]
        got = u3_measure(PAGINATED_META, *wait("wait"))
        self.assertEqual({carrier: sizes["results"] for carrier, sizes in got["by_carrier"].items()}, {"other": 1})
        got = u3_measure(PAGINATED_META, exec_call("call_priv_x", "text('hi')"), exec_output("call_priv_x"),
                         *wait("wait_agent", namespace="collaboration"))
        self.assertEqual({carrier: sizes["results"] for carrier, sizes in got["by_carrier"].items()},
                         {"code_mode": 1, "other": 1})

    def test_the_outer_exec_code_is_never_scanned(self):
        # Must stay (F2): a fetch() in the outer JavaScript cannot reach the network in the pinned isolate (above), so it is
        # neither a fetch nor a possible fetch, in either history mode; this rebuts the review's outer-JS finding.
        for meta in (PAGINATED_META, LEGACY_META):
            with self.subTest(history_mode=meta["payload"].get("history_mode", "(none)")):
                got = u3_measure(meta, exec_call("call_priv_f2", "const r = await fetch('https://example.org/api'); "
                                                 "text(await r.text())"), exec_output("call_priv_f2"))
                self.assertEqual({key: got["m4"][key]
                                  for key in ("remote_fetches", "unclassifiable", "fetch_mentions_unconfirmed", "status")},
                                 {"remote_fetches": 0, "unclassifiable": 0, "fetch_mentions_unconfirmed": 0,
                                  "status": "not_applicable"})

    def test_the_retained_isolated_fixture_keeps_its_direct_items(self):
        # Must stay (the review's position finding): its three items come before its exec, so they stay direct.
        got = S.measure_codex_records(self.retained_rows("isolated"), since=S.parse_iso(LANES_SINCE),
                                      until=S.parse_iso(LANES_UNTIL))
        self.assertEqual((got["sandbox_operations"], got["calls_without_result"]), (0, 4))

    def test_a_web_search_call_id_is_a_model_call_id(self):
        # The review's web_search_call finding: a hosted web search is a model call (ResponseItem::WebSearchCall, protocol/src/
        # models.rs:1182-1203, persisted by rollout/src/policy.rs:56), so an item carrying its id is direct, even inside an
        # open exec span. The hosted search's own item is TurnItem::WebSearch (protocol/src/items.rs:57-61), which the adapter
        # does not emit at all, as the Claude kernel counts no server tool; this host's store holds no web_search_call record
        # (the U3 census, evidence/artifacts/pra-u3-differential-20260929). The item here is the review's Extension shape.
        got = u3_measure(PAGINATED_META, exec_call("call_priv_x", EXEC_FETCH_JS),
                         codex_row("response_item", {"type": "web_search_call", "id": "ws_priv_1", "status": "completed",
                                                     "action": {"type": "open_page", "url": "https://example.org/w"}}),
                         codex_row("event_msg", {"type": "item_completed", "item": {
                             "type": "Extension", "id": "ws_priv_1", "kind": "web.search",
                             "action": {"type": "openPage", "url": "https://example.org/w"}}}),
                         exec_output("call_priv_x"))
        self.assertEqual(got["sandbox_operations"], 0)
        self.assertEqual({key: got.get("code_mode", {}).get(key) for key in ("exec_calls", "nested_items", "unattributed_items")},
                         {"exec_calls": 1, "nested_items": 0, "unattributed_items": 0})

    def test_only_emitted_items_count_as_nested_or_unattributed(self):
        # The review's item-kind finding: item_completed also carries Reasoning, AgentMessage, a clock.sleep Extension and
        # FileChange items, and a user_shell command is no call at all (commit 6); the adapter emits none of them as a tool
        # call, so none is a nested or an unattributed item, before the exec or after it.
        def item(key, item_type, **extra):
            return codex_row("event_msg", {"type": "item_completed", "item": {"type": item_type, "id": key, **extra}})
        got = u3_measure(PAGINATED_META, item("item_r0", "Reasoning"), exec_call("call_priv_x", "text('hi')"),
                         item("item_r1", "Reasoning"), item("item_a1", "AgentMessage"),
                         item("item_s1", "Extension", kind="clock.sleep"), item("item_f1", "FileChange", status="completed"),
                         sourced_command("item_u1", ["bash", "-lc", "ls"], "user_shell"), exec_output("call_priv_x"))
        self.assertEqual({key: got.get("code_mode", {}).get(key) for key in ("exec_calls", "nested_items", "unattributed_items")},
                         {"exec_calls": 1, "nested_items": 0, "unattributed_items": 0})
        self.assertEqual(got["sandbox_operations"], 0)

    def test_turn_aliases_end_nesting_and_other_direct_calls_do_not(self):
        # A cell keeps running after exec returns (description.rs: yield_control, and the wait tool resumes it), so another
        # direct call between an exec and an item no longer ends the exec's nesting; only the turn bounds it. The turn events
        # are every name this module reads: task_started (alias turn_started) and task_complete (alias turn_complete)
        # (protocol.rs:1403-1415), turn_aborted, and the attempt ends task_completed, turn_completed and turn_failed.
        def curl(key, path):
            return sourced_command(key, ["bash", "-lc", "curl https://example.org/" + path], "unified_exec_startup")
        got = u3_measure(PAGINATED_META, exec_call("call_priv_x", EXEC_FETCH_JS),
                         codex_row("response_item", {"type": "function_call", "call_id": "call_priv_p", "name": "update_plan",
                                                     "arguments": "{}"}),
                         codex_row("response_item", {"type": "function_call_output", "call_id": "call_priv_p", "output": "ok"}),
                         curl("item_n1", "a"), curl("item_n2", "b"), codex_row("event_msg", {"type": "turn_complete"}),
                         curl("item_d1", "c"), codex_row("event_msg", {"type": "turn_started"}),
                         exec_call("call_priv_y", EXEC_FETCH_JS), codex_row("event_msg", {"type": "turn_failed"}),
                         curl("item_d2", "d"))
        self.assertEqual(got["sandbox_operations"], 2)
        self.assertEqual({key: got["m4"][key] for key in ("shell_fetch", "ctx_sandbox_fetch")},
                         {"shell_fetch": 2, "ctx_sandbox_fetch": 2})
        self.assertEqual({key: got.get("code_mode", {}).get(key) for key in ("exec_calls", "nested_items", "unattributed_items")},
                         {"exec_calls": 2, "nested_items": 2, "unattributed_items": 2})

    def test_code_mode_counters_count_once_in_the_window_of_their_first_record(self):
        # As codex_commands (commit 6): an exec or wait call, and a nested or unattributed item, counts once, in the window of
        # its first record, so adjacent windows add up; nesting reads every own record before until, so an item after since
        # whose exec came before it is still nested, and a wait in that window is still the exec's.
        def at(hour, minute, row):
            return {**row, "timestamp": f"2026-10-20T{hour:02d}:{minute:02d}:00Z"}
        rows = [at(0, 30, PAGINATED_META), at(0, 40, codex_row("event_msg", {"type": "task_started"})),
                at(1, 0, exec_call("call_priv_x", EXEC_FETCH_JS)),
                at(1, 1, exec_output("call_priv_x", "Script running with cell ID 1")),
                at(1, 30, sourced_command("item_n1", ["bash", "-lc", "ls"], "unified_exec_startup")),
                at(2, 30, sourced_command("item_n2", ["bash", "-lc", "ls"], "unified_exec_startup")),
                at(2, 40, codex_row("response_item", {"type": "function_call", "call_id": "call_priv_w", "name": "wait",
                                                      "arguments": json.dumps({"cell_id": "1"})})),
                at(2, 41, codex_row("response_item", {"type": "function_call_output", "call_id": "call_priv_w",
                                                      "output": "w" * 100})),
                at(3, 0, codex_row("event_msg", {"type": "task_complete"})),
                at(3, 10, codex_row("event_msg", {"type": "task_started"})),
                at(3, 20, sourced_command("item_d1", ["bash", "-lc", "ls"], "unified_exec_startup")),
                at(3, 30, codex_row("event_msg", {"type": "task_complete"}))]
        keys = ("exec_calls", "wait_calls", "nested_items", "unattributed_items")

        def measure(since, until):
            return S.measure_codex_records(rows, since=S.parse_iso(f"2026-10-20T{since:02d}:00:00Z"),
                                           until=S.parse_iso(f"2026-10-20T{until:02d}:00:00Z"))
        whole, first, second = measure(0, 4), measure(0, 2), measure(2, 4)
        counts = [{key: got.get("code_mode", {}).get(key) for key in keys} for got in (whole, first, second)]
        self.assertEqual(counts[0], {"exec_calls": 1, "wait_calls": 1, "nested_items": 2, "unattributed_items": 1})
        self.assertEqual(counts[2], {"exec_calls": 0, "wait_calls": 1, "nested_items": 1, "unattributed_items": 1})
        self.assertEqual({key: (counts[1][key] or 0) + (counts[2][key] or 0) for key in keys}, counts[0])
        # The window's wait output is code mode; the unattributed item's own output is a direct Bash result.
        self.assertEqual({carrier: sizes["results"] for carrier, sizes in second["by_carrier"].items()},
                         {"code_mode": 1, "bash": 1})
        self.assertEqual(second["sandbox_operations"], 1)

    def test_groups_sum_the_code_mode_counters(self):
        # aggregate_codex_lanes sums measurement.code_mode over the group's actors, as it sums codex_commands.
        def rollout(key):
            return [{**PAGINATED_META, "payload": {**PAGINATED_META["payload"], "id": "u3-session-" + key}},
                    codex_row("response_item", developer(CATALOG)), exec_call("call_priv_" + key, EXEC_FETCH_JS),
                    sourced_command("item_" + key, ["bash", "-lc", "ls"], "unified_exec_startup"),
                    exec_output("call_priv_" + key)]
        root = write_rollouts(Path(self.enterContext(tempfile.TemporaryDirectory())), {
            "rollout-2026-10-20T02-00-00-u3-cm-a.jsonl": rollout("a"), "rollout-2026-10-20T02-10-00-u3-cm-b.jsonl": rollout("b")})
        scan = S.scan_codex_lanes([root], load_fixture_manifest(), since=S.parse_iso(LANES_SINCE), until=S.parse_iso(LANES_UNTIL),
                                  marker=MARKER)
        group = scan["groups"]["workers"]["measurement"].get("code_mode", {})
        self.assertEqual({key: group.get(key) for key in ("exec_calls", "wait_calls", "nested_items", "unattributed_items")},
                         {"exec_calls": 2, "wait_calls": 0, "nested_items": 2, "unattributed_items": 0})

    @pending("commit 8: legacy-mode spans")
    def test_a_legacy_exec_with_fetch_sites_and_no_items_is_unobservable(self):
        # F1 and its controls.
        four_sites = ("await tools.exec_command({cmd: 'a'}); await tools.exec_command({cmd: 'b'}); "
                      "await tools.mcp__context_mode__ctx_execute({language: 'shell', code: 'c'}); await tools.web__run({})")
        cases = {"no history_mode": (LEGACY_META, EXEC_FETCH_JS, (1, 1), "incomplete"),
                 "history_mode legacy": (EXPLICIT_LEGACY_META, EXEC_FETCH_JS, (1, 1), "incomplete"),
                 "four sites": (LEGACY_META, four_sites, (1, 4), "incomplete"),
                 "paginated": (PAGINATED_META, EXEC_FETCH_JS, (0, 0), "not_applicable"),
                 "no fetch-capable site": (LEGACY_META, "text('hello')", (0, 0), "not_applicable")}
        for name, (meta, code, spans, status) in cases.items():
            with self.subTest(case=name):
                got = u3_measure(meta, exec_call("call_priv_f", code), exec_output("call_priv_f"))
                code_mode = got.get("code_mode", {})
                self.assertEqual((code_mode.get("legacy_unobservable_exec_calls"), code_mode.get("legacy_unobservable_sites")),
                                 spans)
                self.assertEqual((got["m4"]["status"], got["m4"]["remote_fetches"], got["m4"]["fetch_mentions_unconfirmed"]),
                                 (status, 0, 0))
        # A legacy exec with a persisted item of its own is observable.
        got = u3_measure(LEGACY_META, exec_call("call_priv_g", EXEC_FETCH_JS),
                         sourced_command("item_g", ["bash", "-lc", "curl https://example.org"], "unified_exec_startup"),
                         exec_output("call_priv_g"))
        self.assertEqual((got.get("code_mode", {}).get("legacy_unobservable_exec_calls"), got["m4"]["status"]), (0, "measured"))

    @pending("commit 8: legacy-mode spans")
    def test_legacy_spans_make_the_actor_and_group_incomplete(self):
        # The retained isolated fixture is legacy (no history_mode) and its exec, with a tools.exec_command site, has no item
        # of its own; the retained worker's exec has twelve. The kernel's aggregate recomputes M4 status from counts, so the
        # group's status is forced as well.
        isolated = S.measure_codex_records(self.retained_rows("isolated"), since=S.parse_iso(LANES_SINCE),
                                           until=S.parse_iso(LANES_UNTIL))
        worker = S.measure_codex_records(self.retained_rows("worker"), since=S.parse_iso(LANES_SINCE),
                                         until=S.parse_iso(LANES_UNTIL))
        self.assertEqual((isolated.get("code_mode", {}).get("legacy_unobservable_exec_calls"),
                          isolated.get("code_mode", {}).get("legacy_unobservable_sites"), isolated["m4"]["status"]),
                         (1, 1, "incomplete"))
        self.assertEqual(worker.get("code_mode", {}).get("legacy_unobservable_exec_calls"), 0)
        scan = S.scan_codex_lanes([materialize_lanes_root(Path(self.enterContext(tempfile.TemporaryDirectory())))],
                                  load_fixture_manifest(), since=S.parse_iso(LANES_SINCE), until=S.parse_iso(LANES_UNTIL),
                                  marker=MARKER)
        controls = scan["groups"]["negative_controls"]["measurement"]
        self.assertEqual((controls["m4"]["status"], controls.get("code_mode", {}).get("legacy_unobservable_exec_calls")),
                         ("incomplete", 1))

    def test_a_rollout_without_a_paginated_meta_reads_as_legacy(self):
        # The no-meta rule, pinned: a SessionMeta without history_mode deserializes as legacy (protocol.rs:772-779), and only
        # a paginated rollout is known to persist every ItemCompleted (rollout/src/policy.rs:94-112), so rows with no
        # session_meta at all, and a history_mode other than paginated, get the legacy-span reading.
        other = u3_row("session_meta", {"id": "u3-session", "source": "exec", "history_mode": "archived",
                                        "cli_version": "0.157.1"})
        for name, rows in {"no session_meta": [], "history_mode legacy": [EXPLICIT_LEGACY_META],
                           "unknown history_mode": [other]}.items():
            with self.subTest(case=name):
                got = u3_measure(*rows, exec_call("call_priv_f", EXEC_FETCH_JS), exec_output("call_priv_f"))
                code_mode = got.get("code_mode", {})
                self.assertEqual((code_mode.get("legacy_unobservable_exec_calls"), code_mode.get("legacy_unobservable_sites"),
                                  got["m4"]["status"]), (1, 1, "incomplete"))

    def test_static_sites_include_bracket_access_and_skip_other_names(self):
        # A site is the global `tools` (not part of a longer name, not a property such as x.tools) with a fetch-capable name
        # after a dot (blanks and ?. allowed): exec_command, web__run and mcp__<server>__ctx_execute, ctx_execute_file,
        # ctx_batch_execute or ctx_fetch_and_index; any bracket access tools[...] can name any tool, so it counts as well
        # (conservative). ALL_TOOLS, other nested tools and longer names are no sites.
        code = ("await tools['exec_command']({cmd: 'a'}); await tools[name]('b'); await tools . exec_command ({cmd: 'c'}); "
                "await tools?.web__run({}); await tools.mcp__context_mode__ctx_fetch_and_index({url: 'u'}); "
                "await mytools.exec_command({}); await x.tools.exec_command({}); await tools.exec_commander({}); "
                "await tools.mcp__context_mode__ctx_search({}); const all = ALL_TOOLS; await tools_list.exec_command({})")
        got = u3_measure(LEGACY_META, exec_call("call_priv_s", code), exec_output("call_priv_s"))
        code_mode = got.get("code_mode", {})
        self.assertEqual((code_mode.get("legacy_unobservable_exec_calls"), code_mode.get("legacy_unobservable_sites")), (1, 5))

    def test_legacy_spans_count_once_in_the_window_of_the_exec(self):
        # As the other code_mode counters: an unobservable exec counts in the window of its call record, so adjacent
        # windows add up.
        def at(hour, row):
            return {**row, "timestamp": f"2026-10-20T{hour:02d}:00:00Z"}
        rows = [at(0, LEGACY_META), at(1, exec_call("call_priv_a", EXEC_FETCH_JS)), at(1, exec_output("call_priv_a")),
                at(3, exec_call("call_priv_b", EXEC_FETCH_JS)), at(3, exec_output("call_priv_b"))]

        def spans(since, until):
            got = S.measure_codex_records(rows, since=S.parse_iso(f"2026-10-20T{since:02d}:00:00Z"),
                                          until=S.parse_iso(f"2026-10-20T{until:02d}:00:00Z"))
            return got.get("code_mode", {}).get("legacy_unobservable_exec_calls"), got["m4"]["status"]
        self.assertEqual([spans(0, 4), spans(0, 2), spans(2, 4)], [(2, "incomplete"), (1, "incomplete"), (1, "incomplete")])

    def test_outer_http_mentions_are_scoped_to_verified_isolates(self):
        # The 10e outer-JS decision (2026-09-29, tools/skill-usage/README.md): the code-mode isolate of the clients read at
        # their tags has no network access (code-mode-protocol/src/description.rs:24 at rust-v0.157.1 and :20 at rust-v0.155.1,
        # and globals.rs:36-48, byte-identical at both, installs no fetch), so an HTTP-shaped mention (the kernel's HTTP_SCRIPT
        # pattern) in the outer code is no fetch there: it is only counted, in code_mode.outer_http_mentions. A client whose
        # isolate was not read, or a rollout naming none, is the decision's overturn trigger: its exec with a mention counts
        # in outer_http_unverified_exec_calls and M4 is incomplete; the fetch counts keep their meaning.
        code = ("const r = await fetch('https://example.org/api'); const s = await axios . get('https://example.org/b'); "
                "text(await r.text())")
        cases = {"0.157.1": (2, 0, "not_applicable"), "0.155.1": (2, 0, "not_applicable"),
                 "0.158.0": (2, 1, "incomplete"), None: (2, 1, "incomplete")}
        for version, expected in cases.items():
            with self.subTest(cli_version=version):
                meta = {"id": "u3-session", "source": "exec", "history_mode": "paginated",
                        **({"cli_version": version} if version else {})}
                got = u3_measure(u3_row("session_meta", meta), exec_call("call_priv_h", code), exec_output("call_priv_h"))
                code_mode = got.get("code_mode", {})
                self.assertEqual((code_mode.get("outer_http_mentions"), code_mode.get("outer_http_unverified_exec_calls"),
                                  got["m4"]["status"]), expected)
                self.assertEqual((got["m4"]["remote_fetches"], got["m4"]["unclassifiable"],
                                  got["m4"]["fetch_mentions_unconfirmed"]), (0, 0, 0))
        unverified = u3_row("session_meta", {"id": "u3-session", "source": "exec", "history_mode": "paginated",
                                             "cli_version": "0.158.0"})
        got = u3_measure(unverified, exec_call("call_priv_t", "text('hi')"), exec_output("call_priv_t"))
        self.assertEqual((got.get("code_mode", {}).get("outer_http_unverified_exec_calls"), got["m4"]["status"]),
                         (0, "not_applicable"))
        # Groups force it as well, since the kernel's aggregate recomputes M4 status from the counts.
        root = write_rollouts(Path(self.enterContext(tempfile.TemporaryDirectory())), {
            "rollout-2026-10-20T02-00-00-u3-unverified.jsonl": [
                unverified, codex_row("response_item", developer(CATALOG)), exec_call("call_priv_g", code),
                exec_output("call_priv_g")]})
        scan = S.scan_codex_lanes([root], load_fixture_manifest(), since=S.parse_iso(LANES_SINCE), until=S.parse_iso(LANES_UNTIL),
                                  marker=MARKER)
        group = scan["groups"]["workers"]["measurement"]
        self.assertEqual((group["m4"]["status"], group.get("code_mode", {}).get("outer_http_unverified_exec_calls")),
                         ("incomplete", 1))


if __name__ == "__main__":
    unittest.main()
