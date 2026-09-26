"""Tests for tools/skill-usage/skill_usage.py. Fixtures are synthetic (tests/fixtures/skill_usage/):
no real host paths, cwd or session ids, and skill names drawn from the real pinned skills manifest."""
from __future__ import annotations

import contextlib
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "skill-usage"))
import skill_usage as S  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "skill_usage"
NOW = "2026-10-30T00:00:00Z"


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

    def test_refuses_json_that_is_not_an_event_array(self):
        parsed = S.parse_claude_output(json.dumps({"not": "a list"}))
        self.assertIn("error", parsed)

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

    def test_skill_lock_path_relative_xdg_state_home_is_ignored(self):
        path = S.skill_lock_path(home="/home/example", environment={"XDG_STATE_HOME": "relative/dir"})
        self.assertEqual(path, Path("/home/example/.agents/.skill-lock.json"))

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

    def run_main(self, extra_args, out=None):
        args = ["--manifest", str(self.manifest_path), "--now", NOW, "--home", str(self.home),
                "--claude-skill-doctor", str(self.claude_file)]
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


class CodexLanes(unittest.TestCase):
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
        self.assertEqual(scan["sessions_excluded_user_config_ignored"], 0)
        self.assertEqual(scan["counts"]["tdd"][30]["skill_md_reads"], 1)

    def test_files_not_modified_since_the_window_start_are_skipped_unread(self):
        stale = next(self.root.glob("rollout-*-lanes-isolated.jsonl"))
        old = S.parse_iso("2026-10-01T00:00:00Z").timestamp()
        os.utime(stale, (old, old))
        scan = self.scan()
        self.assertEqual(scan["files_skipped_unmodified"], 1)
        self.assertEqual(scan["user_config"]["ignored"], 0)

    def test_invoke_rate_counts_leave_out_sessions_that_ignored_the_user_config(self):
        now = S.parse_iso(NOW)
        scan = S.scan_codex_roots([self.root], self.names, now=now, windows=(30,), codex_off=self.codex_off)
        self.assertEqual(scan["sessions_excluded_user_config_ignored"], 1)
        self.assertEqual(scan["counts"]["tdd"][30]["skill_md_reads"], 1)  # the worker's read
        self.assertEqual(scan["excluded_counts"]["tdd"][30]["skill_md_reads"], 1)  # the isolated one
        report = S.build_report(self.manifest, claude=None, codex_scan=scan, lock_installed_at={},
                                now=now, windows=(30,))
        self.assertEqual(report["codex"]["sessions_excluded_user_config_ignored"], 1)
        tdd = next(entry for entry in report["skills"] if entry["name"] == "tdd")
        self.assertEqual(tdd["codex"]["counts"]["30"]["skill_md_reads"], 1)
        self.assertEqual(tdd["codex"]["excluded_user_config_ignored"]["30"]["skill_md_reads"], 1)
        # Without a codex_off list nothing can be classified, so nothing is left out.
        legacy = S.scan_codex_roots([self.root], self.names, now=now, windows=(30,))
        self.assertEqual((legacy["counts"]["tdd"][30]["skill_md_reads"],
                          legacy["sessions_excluded_user_config_ignored"]), (2, 0))

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
        self.assertEqual(S.shell_script(["bash", "-lc", "rtk ls"]), "rtk ls")
        self.assertEqual(S.shell_script(["ls", "-la"]), "ls -la")
        self.assertEqual(S.shell_script(None), "")

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


if __name__ == "__main__":
    unittest.main()
