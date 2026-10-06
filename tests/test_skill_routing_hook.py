"""Focused local fixtures for the held S9 consumer, not native-client efficacy."""

from __future__ import annotations

import importlib.util
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "adoption/hooks/claude/skill-routing/hooks/skill-routing.py"
SPEC = importlib.util.spec_from_file_location("held_skill_routing", HOOK)
ROUTING = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROUTING)


class SkillRoutingFixtures(unittest.TestCase):
    def setUp(self):
        cache = Path(os.environ.get("NS_SKILL_ROUTING_TEST_CACHE", str(Path.home() / ".cache/ns2604-skills-r2-routing-tests")))
        cache.mkdir(parents=True, exist_ok=True)
        self.cache = cache
        self.temp = tempfile.TemporaryDirectory(dir=cache, prefix="fixture-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest_path = self.root / "adoption/workflow/manifest.json"
        self.manifest_path.parent.mkdir(parents=True)
        self.central = self.root / "adoption/skills/manifest.json"
        self.central.parent.mkdir()
        self.manifest = {
            "schema_version": 1, "kind": "sota_workflow_manifest", "trigger_syntax": "python_regex",
            "pin_sources": {"skills": "adoption/skills/manifest.json", "agents": "adoption/agents"},
            "lanes": ["cc", "coop", "codex_lane", "ultracode_stage", "blind"],
            "rows": [{
                "id": "skills-ci-pr", "status": "kept", "uses": ["skills:gh-fix-ci", "agents:eligible-worker"],
                "lanes": {"cc": ["description"], "codex_lane": ["description"], "ultracode_stage": {"agentType": "eligible-worker"}},
                "triggers": {"intent": [r"\b(?:fix|diagnose)\b.*\bCI\b"], "paths": ["**/AGENTS.md"],
                    "tool_events": [{"tool": "Bash", "regex": r"\bgh\s+run\s+(?:view|rerun)\b"}], "agent_types": ["eligible-worker"]},
                "measure": {},
            }],
        }
        self.skills = [{"name": "gh-fix-ci", "status": "kept", "claude_listing": "on", "codex_enabled": True}]
        self.save()

    def save(self):
        self.manifest_path.write_text(json.dumps(self.manifest))
        self.central.write_text(json.dumps({"skills": self.skills}))

    def role(self, *, name="eligible-worker", tools="Read, Skill", preloads=(), native=True):
        header = f"---\nname: {name}\ntools: {json.dumps(tools)}\nskills: {json.dumps(list(preloads))}\n---\nPublic fixture role.\n"
        canonical = self.root / "adoption/agents/claude" / (name + ".md")
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_text(header)
        if native:
            path = self.root / ".claude/agents" / (name + ".md")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(header)

    def suggest(self, payload, client="claude", lane="cc", optin=True):
        return ROUTING.suggest(self.root, self.manifest, payload, client=client, lane=lane, benchmark_hints=optin)

    def test_no_optin_is_silent_without_filesystem_read(self):
        with mock.patch.object(ROUTING, "read_json", side_effect=AssertionError("should not read")), mock.patch.object(ROUTING.sys, "stdin", io.TextIOWrapper(io.BytesIO(b"not JSON"))), mock.patch.object(ROUTING.sys, "stdout", io.StringIO()) as output:
            self.assertEqual(ROUTING.main(["--client", "claude"]), 0)
            self.assertEqual(output.getvalue(), "")

    def test_explicit_outcome_positive_matches_registered_skill(self):
        self.assertEqual(self.suggest({"hook_event_name": "UserPromptSubmit", "prompt": "Diagnose this CI failure"}), ["gh-fix-ci"])

    def test_list_and_status_intents_are_not_positive_outcomes(self):
        for prompt in ["List CI checks", "Summarize the CI log", "Check CI status"]:
            with self.subTest(prompt=prompt):
                self.assertEqual(self.suggest({"hook_event_name": "UserPromptSubmit", "prompt": prompt}), [])

    def test_fetch_only_tool_events_are_silent_even_if_regex_matches(self):
        for command in ["gh run view 42 --log-failed", "gh pr view 42 --json comments", "gh api repos/example/project/pulls/42/comments"]:
            with self.subTest(command=command):
                self.assertEqual(self.suggest({"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": command}}), [])

    def test_matched_action_event_can_hint(self):
        self.assertEqual(self.suggest({"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "gh run rerun 42"}}), ["gh-fix-ci"])

    @unittest.skipUnless(callable(getattr(ROUTING.glob, "translate", None)), "path hints require supported Python 3.13+")
    def test_clear_edit_path_and_native_codex_command_patch_shape_are_supported(self):
        # This authored fixture mirrors pinned upstream payload shape; it is not
        # a fresh native callback. apply_patch.rs:290-295,437-450 at a956835d.
        for payload in [
            {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {"file_path": str(self.root / "AGENTS.md")}},
            {"hook_event_name": "PostToolUse", "tool_name": "apply_patch", "cwd": str(self.root), "tool_input": {"command": "*** Begin Patch\n*** Update File: AGENTS.md\n@@\n-public\n+public\n*** End Patch\n"}},
        ]:
            self.assertEqual(self.suggest(payload, client="codex", lane="codex_lane"), ["gh-fix-ci"])

    def test_invented_codex_patch_input_and_patch_fields_are_not_native_paths(self):
        raw = "*** Begin Patch\n*** Update File: AGENTS.md\n@@\n-public\n+public\n*** End Patch\n"
        for arguments in ({"input": raw}, {"patch": raw}, raw):
            with self.subTest(arguments=arguments):
                self.assertEqual(ROUTING.paths_from_edit({"hook_event_name": "PostToolUse", "tool_name": "apply_patch", "tool_input": arguments}, self.root), [])

    @unittest.skipUnless(callable(getattr(ROUTING.glob, "translate", None)), "path hints require supported Python 3.13+")
    def test_native_patch_content_is_not_mistaken_for_a_fetch_command(self):
        payload = {"hook_event_name": "PostToolUse", "tool_name": "apply_patch", "cwd": str(self.root),
                   "tool_input": {"command": "*** Begin Patch\n*** Update File: AGENTS.md\n@@\n+Use gh pr view to read the supplied review record.\n*** End Patch\n"}}
        self.assertEqual(self.suggest(payload, client="codex", lane="codex_lane"), ["gh-fix-ci"])

    def test_relative_edit_paths_use_native_cwd_and_reject_unknown_or_outside_cwd(self):
        nested = self.root / "nested"
        nested.mkdir()
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Edit", "cwd": str(nested), "tool_input": {"file_path": "AGENTS.md"}}
        self.assertEqual(ROUTING.paths_from_edit(payload, self.root), ["nested/AGENTS.md"])
        for cwd in (None, "nested", str(self.root.parent)):
            payload["cwd"] = cwd
            with self.subTest(cwd=cwd):
                self.assertEqual(ROUTING.paths_from_edit(payload, self.root), [])
        payload["cwd"] = str(nested)
        payload["tool_input"]["file_path"] = "../../outside.md"
        self.assertEqual(ROUTING.paths_from_edit(payload, self.root), [])

    def test_read_file_is_not_an_edit_hint(self):
        self.assertEqual(self.suggest({"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_input": {"file_path": str(self.root / "AGENTS.md")}}), [])

    def test_candidate_held_retired_and_pending_rows_are_inert(self):
        payload = {"hook_event_name": "UserPromptSubmit", "prompt": "Fix CI now"}
        for status in ["candidate", "held", "retired"]:
            self.manifest["rows"][0]["status"] = status
            self.assertEqual(self.suggest(payload), [])
        self.manifest["rows"][0]["status"] = "kept"
        self.manifest["rows"][0]["measure"]["pending_skills"] = ["gh-fix-ci"]
        self.assertEqual(self.suggest(payload), [])
        self.manifest["rows"][0]["measure"] = {"pending_lane_dependencies": {"codex_lane": {"skills": []}}}
        self.assertEqual(self.suggest(payload, client="codex", lane="codex_lane"), [])

    def test_main_events_need_nonempty_native_lane_channels(self):
        payload = {"hook_event_name": "UserPromptSubmit", "prompt": "Fix CI now"}
        for channel in ([], "inert", {"agentType": "eligible-worker"}, ["unregistered-channel"]):
            self.manifest["rows"][0]["lanes"]["cc"] = channel
            with self.subTest(channel=channel):
                self.assertEqual(self.suggest(payload), [])
        self.manifest["rows"][0]["lanes"].pop("cc")
        self.assertEqual(self.suggest(payload), [])

    def test_main_event_cannot_use_an_active_or_inert_child_lane(self):
        payload = {"hook_event_name": "UserPromptSubmit", "prompt": "Fix CI now"}
        for stage in ({"agentType": "eligible-worker"}, "inert", None):
            self.manifest["rows"][0]["lanes"]["ultracode_stage"] = stage
            with self.subTest(stage=stage):
                self.assertEqual(self.suggest(payload, lane="ultracode_stage"), [])

    def test_child_event_cannot_substitute_main_channels_for_active_stage(self):
        self.role()
        payload = {"hook_event_name": "SubagentStart", "agent_type": "eligible-worker"}
        self.assertEqual(self.suggest(payload, lane="cc"), [])

    def test_client_and_implicit_invocation_policy_is_preserved(self):
        payload = {"hook_event_name": "UserPromptSubmit", "prompt": "Fix CI now"}
        for change in [{"status": "held"}, {"codex_enabled": False}, {"upstream_allow_implicit_invocation": False}]:
            old = dict(self.skills[0])
            self.skills[0].update(change)
            self.save()
            self.assertEqual(self.suggest(payload, client="codex", lane="codex_lane"), [])
            self.skills[0] = old
        self.skills[0]["claude_listing"] = "user-invocable-only"
        self.save()
        self.assertEqual(self.suggest(payload), [])

    def test_verified_native_skill_grant_is_required_for_child(self):
        payload = {"hook_event_name": "SubagentStart", "agent_type": "eligible-worker"}
        self.role(native=False)
        with mock.patch.object(ROUTING.Path, "home", return_value=self.root / "absent-home"):
            self.assertEqual(self.suggest(payload, lane="ultracode_stage"), [])
        self.role()
        self.assertEqual(self.suggest(payload, lane="ultracode_stage"), ["gh-fix-ci"])

    def test_custom_native_global_role_root_does_not_borrow_default_profile(self):
        self.role(native=False)
        header = (self.root / "adoption/agents/claude/eligible-worker.md").read_text()
        fake_home = self.root / "public-home"
        default_role = fake_home / ".claude/agents/eligible-worker.md"
        default_role.parent.mkdir(parents=True)
        default_role.write_text(header)
        custom = self.root / "public-custom-claude"
        custom.mkdir()
        payload = {"hook_event_name": "SubagentStart", "agent_type": "eligible-worker"}
        with mock.patch.object(ROUTING.Path, "home", return_value=fake_home), mock.patch.object(ROUTING.os, "environ", {"CLAUDE_CONFIG_DIR": str(custom)}):
            with mock.patch.object(ROUTING, "safe_read", wraps=ROUTING.safe_read) as reads:
                self.assertEqual(self.suggest(payload, lane="ultracode_stage"), [])
            self.assertNotIn(default_role, [call.args[0] for call in reads.call_args_list])
            custom_role = custom / "agents/eligible-worker.md"
            custom_role.parent.mkdir()
            custom_role.write_text(header)
            self.assertEqual(self.suggest(payload, lane="ultracode_stage"), ["gh-fix-ci"])
        self.role()
        with mock.patch.object(ROUTING.os, "environ", {"CLAUDE_CONFIG_DIR": "unsupported-relative-root"}):
            self.assertEqual(self.suggest(payload, lane="ultracode_stage"), ["gh-fix-ci"])

    def test_skillless_wildcard_unknown_blind_and_codex_children_silent(self):
        for tools in ["Read, Grep", "*"]:
            self.role(tools=tools)
            self.assertEqual(self.suggest({"hook_event_name": "SubagentStart", "agent_type": "eligible-worker"}, lane="ultracode_stage"), [])
        self.role()
        for role in ["blind-judge", "unknown-worker"]:
            self.assertEqual(self.suggest({"hook_event_name": "SubagentStart", "agent_type": role}, lane="ultracode_stage"), [])
        self.assertEqual(self.suggest({"hook_event_name": "SubagentStart", "agent_type": "eligible-worker"}, client="codex", lane="codex_lane"), [])
        self.assertEqual(self.suggest({"hook_event_name": "UserPromptSubmit", "prompt": "Fix CI now"}, lane="blind"), [])

    def test_native_role_drift_and_preloaded_duplicate_are_silent(self):
        self.role(preloads=["gh-fix-ci"])
        payload = {"hook_event_name": "SubagentStart", "agent_type": "eligible-worker"}
        self.assertEqual(self.suggest(payload, lane="ultracode_stage"), [])
        self.role()
        (self.root / ".claude/agents/eligible-worker.md").write_text("---\nname: eligible-worker\ntools: Read\nskills: []\n---\nFixture.\n")
        self.assertEqual(self.suggest(payload, lane="ultracode_stage"), [])

    def test_inert_grant_preview_is_not_an_active_caller(self):
        self.role()
        self.manifest["rows"][0]["lanes"]["ultracode_stage"] = "inert"
        self.manifest["rows"][0]["measure"]["planned_ultracode_stage"] = {"agentType": "eligible-worker", "skill_grant": True}
        self.assertEqual(self.suggest({"hook_event_name": "SubagentStart", "agent_type": "eligible-worker"}, lane="ultracode_stage"), [])

    def test_event_serialization_has_no_decision_or_data_echo(self):
        for event in ROUTING.EVENTS:
            value = ROUTING.serialize(event, ["gh-fix-ci"])
            self.assertEqual(value["hookSpecificOutput"]["hookEventName"], event)
            self.assertEqual(set(value), {"hookSpecificOutput"})
            self.assertEqual(set(value["hookSpecificOutput"]), {"hookEventName", "additionalContext"})
            self.assertNotIn("decision", json.dumps(value))
        self.assertIsNone(ROUTING.serialize("PostToolUse", ["$(UNRETAINED_FIXTURE)"]))

    @unittest.skipUnless(callable(getattr(ROUTING.glob, "translate", None)), "path hints require supported Python 3.13+")
    def test_native_glob_recursive_segment_matches_zero_and_multiple_directories(self):
        for path in ("adoption/skills/SKILL.md", "adoption/skills/example/SKILL.md", "adoption/skills/a/b/SKILL.md"):
            with self.subTest(path=path):
                self.assertTrue(ROUTING.glob_matches("adoption/skills/**/SKILL.md", path))
        self.assertTrue(ROUTING.glob_matches("**/AGENTS.md", "AGENTS.md"))
        self.assertTrue(ROUTING.glob_matches(".claude/agents/**/*.md", ".claude/agents/worker.md"))

    @unittest.skipUnless(callable(getattr(ROUTING.glob, "translate", None)), "path hints require supported Python 3.13+")
    def test_native_glob_single_star_does_not_cross_separator_or_fold_case(self):
        self.assertTrue(ROUTING.glob_matches("adoption/templates/*AGENTS*", "adoption/templates/codex.AGENTS.template.md"))
        self.assertFalse(ROUTING.glob_matches("adoption/templates/*AGENTS*", "adoption/templates/nested/codex.AGENTS.template.md"))
        self.assertFalse(ROUTING.glob_matches("**/AGENTS.md", "agents.md"))

    def test_unsupported_glob_features_and_runtime_stay_silent(self):
        for pattern in ("**/*.{md,txt}", "**/[A-Z]*", "**/AGENTS?.md", "**/@(AGENTS|CLAUDE).md", "../**", "**name.md"):
            with self.subTest(pattern=pattern):
                self.assertFalse(ROUTING.glob_matches(pattern, "AGENTS.md"))
        with mock.patch.object(ROUTING.glob, "translate", None, create=True):
            self.assertFalse(ROUTING.glob_matches("**/AGENTS.md", "AGENTS.md"))

    def test_malformed_trigger_member_and_measure_containers_are_silent(self):
        payload = {"hook_event_name": "UserPromptSubmit", "prompt": "Fix CI now"}
        original = copy.deepcopy(self.manifest["rows"][0])
        for change in ({"intent": "CI"}, {"intent": [True]}, {"intent": ["CI"] * (ROUTING.MAX_TRIGGER_ITEMS + 1)},
                       {"paths": "**/AGENTS.md"}, {"agent_types": {"eligible-worker": True}},
                       {"tool_events": "Bash"}, {"tool_events": [{"tool": "Bash", "regex": ["CI"]}]},
                       {"skill_intents": {"not-canonical": ["CI"]}}, {"skill_intents": {"gh-fix-ci": "CI"}}):
            self.manifest["rows"][0] = copy.deepcopy(original)
            self.manifest["rows"][0]["triggers"].update(change)
            with self.subTest(change=change):
                self.assertEqual(self.suggest(payload), [])
        for measure in ("pending", {"pending_skills": "gh-fix-ci"}, {"coordinator_only_skills": "gh-fix-ci"},
                        {"pending_lane_dependencies": ["cc"]}):
            self.manifest["rows"][0] = copy.deepcopy(original)
            self.manifest["rows"][0]["measure"] = measure
            with self.subTest(measure=measure):
                self.assertEqual(self.suggest(payload), [])

    def test_one_rows_regex_attempts_share_the_global_match_deadline(self):
        now = [10.0]
        attempted = []
        def bounded_nonmatch(pattern, value, *, deadline):
            attempted.append((pattern, deadline))
            now[0] += 0.021
            return False
        with mock.patch.object(ROUTING.time, "monotonic", side_effect=lambda: now[0]), mock.patch.object(ROUTING, "matches", side_effect=bounded_nonmatch):
            self.assertFalse(ROUTING.any_regex(["unmatched"] * ROUTING.MAX_TRIGGER_ITEMS, "CI", 10.1))
        self.assertEqual(len(attempted), 5)
        self.assertEqual({deadline for _, deadline in attempted}, {10.1})

    def test_regex_timer_uses_remaining_global_budget_and_skips_exhausted_search(self):
        with mock.patch.object(ROUTING.time, "monotonic", return_value=10.09), mock.patch.object(ROUTING.signal, "signal", return_value=0), mock.patch.object(ROUTING.signal, "setitimer", return_value=(0, 0)) as timer:
            with ROUTING.regex_deadline(10.1):
                pass
            self.assertAlmostEqual(timer.call_args_list[0].args[1], 0.01)
        with mock.patch.object(ROUTING.time, "monotonic", return_value=10.1), mock.patch.object(ROUTING.re, "search") as search:
            self.assertFalse(ROUTING.matches("CI", "CI", deadline=10.1))
            search.assert_not_called()

    def test_optional_per_skill_intents_discriminate_ci_from_review_requests(self):
        self.skills.append({"name": "gh-address-comments", "status": "kept", "claude_listing": "on", "codex_enabled": True})
        row = self.manifest["rows"][0]
        row["uses"].append("skills:gh-address-comments")
        row["triggers"]["intent"] = [r"\bfix\b.*\bCI\b", r"\baddress\b.*\breview requests\b"]
        row["triggers"]["skill_intents"] = {"gh-fix-ci": [r"\bfix\b.*\bCI\b"], "gh-address-comments": [r"\baddress\b.*\breview requests\b"]}
        self.save()
        self.assertEqual(self.suggest({"hook_event_name": "UserPromptSubmit", "prompt": "Fix CI now"}), ["gh-fix-ci"])
        self.assertEqual(self.suggest({"hook_event_name": "UserPromptSubmit", "prompt": "Address these review requests"}), ["gh-address-comments"])
        row["triggers"]["skill_intents"] = {}
        self.assertEqual(self.suggest({"hook_event_name": "UserPromptSubmit", "prompt": "Fix CI now"}), [])

    def test_parent_and_root_symlinks_are_rejected_before_file_open(self):
        extra = tempfile.TemporaryDirectory(dir=self.cache, prefix="harmless-public-")
        self.addCleanup(extra.cleanup)
        public = Path(extra.name)
        (public / "manifest.json").write_text('{"public_fixture": true}')
        for redirect in (self.root / "adoption/workflow", self.root / "adoption/skills"):
            saved = redirect.with_name(redirect.name + "-saved")
            redirect.rename(saved)
            redirect.symlink_to(public, target_is_directory=True)
            try:
                with mock.patch.object(ROUTING.os, "open", side_effect=AssertionError("must reject before opener")):
                    with self.assertRaises(ValueError):
                        ROUTING.read_json(redirect / "manifest.json", root=self.root)
            finally:
                redirect.unlink()
                saved.rename(redirect)
        alias = self.root / "redirected-root"
        alias.symlink_to(public, target_is_directory=True)
        with mock.patch.object(ROUTING.os, "open", side_effect=AssertionError("must reject before opener")):
            with self.assertRaises(ValueError):
                ROUTING.safe_read(alias / "manifest.json", root=alias)

    def test_explicit_manifest_never_accepts_redirected_canonical_parent(self):
        public = self.root / "public-fixture"
        public.mkdir()
        workflow = self.root / "adoption/workflow"
        saved = workflow.with_name("workflow-saved")
        workflow.rename(saved)
        workflow.symlink_to(public, target_is_directory=True)
        with self.assertRaises(ValueError):
            ROUTING.root_from_manifest(workflow / "manifest.json")

    def test_bad_contract_oversize_and_malformed_inputs_fail_open(self):
        self.manifest.pop("trigger_syntax")
        self.assertEqual(self.suggest({"hook_event_name": "UserPromptSubmit", "prompt": "Fix CI now"}), [])
        for raw in [b"malformed fixture", b"x" * (ROUTING.MAX_INPUT_BYTES + 1)]:
            with mock.patch.object(ROUTING.sys, "stdin", io.TextIOWrapper(io.BytesIO(raw))), mock.patch.object(ROUTING.sys, "stdout", io.StringIO()) as output:
                self.assertEqual(ROUTING.main(["--client", "claude", "--benchmark-hints", "--manifest", str(self.manifest_path)]), 0)
                self.assertEqual(output.getvalue(), "")

    def test_canonical_manifest_fifo_does_not_block_read(self):
        self.manifest_path.unlink()
        os.mkfifo(self.manifest_path)
        with self.assertRaises(ValueError):
            ROUTING.read_json(self.manifest_path, root=self.root)

    def test_source_names_only_leave_prompt_and_paths_outside_context(self):
        payload = {"hook_event_name": "UserPromptSubmit", "prompt": "Fix CI now: UNRETAINED_PROMPT_FIXTURE"}
        value = ROUTING.serialize("UserPromptSubmit", self.suggest(payload))
        self.assertNotIn("UNRETAINED_PROMPT_FIXTURE", json.dumps(value))
        self.assertNotIn(str(self.root), json.dumps(value))


if __name__ == "__main__":
    unittest.main()
