"""Routing contract mutants: references, native delivery and held dependencies.

These are repository integration fixtures, not native model acceptance.
"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.adoption.workflow_manifest import WorkflowError, validate_manifest
from tools.adoption.render_workflow import (check_rendered, publish_outputs, render_all,
                                          render_foundation_rules)


class WorkflowManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = {"name": "writing-for-agents", "status": "kept",
                      "claude_listing": "on", "codex_enabled": True}
        self.write("adoption/skills/manifest.json", {"skills": [self.skill]})
        self.write("manifests/stack.json", {"components": [{"id": "dagu"}]})
        self.text("docs/decisions/2026-10-06-test.md", "fixture decision\n")
        self.text("adoption/agents/claude/reader.md",
                  "---\nname: reader\ndescription: Read a supplied source\ntools: Read, Grep\n"
                  "model: opus\neffort: max\n---\nRead only.\n")
        self.text("adoption/agents/claude/loaded.md",
                  "---\nname: loaded\ndescription: Edit instructions\ntools: Read, Edit\n"
                  "skills:\n  - writing-for-agents\nmodel: opus\neffort: max\n---\nEdit instructions.\n")
        self.text("adoption/agents/claude/granted.md",
                  "---\nname: granted\ndescription: Invoke the supplied skill\ntools: Read, Skill\n"
                  "model: opus\neffort: max\n---\nRead the assigned packet.\n")
        self.text("adoption/workflow/pending-agents/granted.md",
                  (self.root / "adoption/agents/claude/granted.md").read_text())
        self.manifest = {
            "schema_version": 1, "kind": "sota_workflow_manifest", "trigger_syntax": "python_regex",
            "checked_at": "2026-10-06", "decision_record": "docs/decisions/2026-10-06-test.md",
            "clients": {"claude_code": "2.1.291", "codex_cli": "0.160.0"},
            "pin_sources": {"skills": "adoption/skills/manifest.json", "stack": "manifests/stack.json",
                            "agents": "adoption/agents", "workflow": "examples/claude-native/workflows"},
            "lanes": ["cc", "coop", "codex_lane", "sdk_worker", "ultracode_stage",
                      "agent_team", "scheduled_headless", "blind"],
            "channels": ["description", "preload", "skill_grant_packet", "path_rule", "hook_prompt",
                         "hook_tool_event", "hook_subagent_start", "pointer", "native_verify",
                         "codex_role_text", "sdk_native_arg"],
            "rows": [{"id": "skills-agent-docs", "uses": ["skills:writing-for-agents"],
                      "status": "kept", "lanes": {"cc": ["description", "path_rule"],
                        "blind": [], "ultracode_stage": {"agentType": "loaded", "model": "opus",
                          "effort": "max", "preload": ["writing-for-agents"]}},
                      "triggers": {"paths": ["adoption/templates/*AGENTS*"]}, "measure": {}}],
        }

    def write(self, relative, data):
        self.text(relative, json.dumps(data))

    def text(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")

    def changed(self):
        return copy.deepcopy(self.manifest)

    def test_resolved_native_preload_route_is_valid(self):
        validate_manifest(self.root, self.manifest)

    def test_dangling_reference_mutant_fails(self):
        data = self.changed()
        data["rows"][0]["uses"] = ["skills:unregistered-trial"]
        with self.assertRaisesRegex(WorkflowError, "unresolved"):
            validate_manifest(self.root, data)

    def test_inert_route_marked_deliverable_mutant_fails(self):
        data = self.changed()
        row = data["rows"][0]
        row["lanes"]["ultracode_stage"] = "inert"
        row["inert_reason"] = "No native skill delivery."
        row["measure"]["deliverable"] = True
        with self.assertRaisesRegex(WorkflowError, "inert route marked deliverable"):
            validate_manifest(self.root, data)

    def test_skill_less_actor_cannot_claim_delivery(self):
        data = self.changed()
        data["rows"][0]["lanes"]["ultracode_stage"] = {
            "agentType": "reader", "model": "opus", "effort": "max", "preload": []}
        with self.assertRaisesRegex(WorkflowError, "inert skill route"):
            validate_manifest(self.root, data)

    def test_native_skill_grant_needs_named_imperative(self):
        data = self.changed()
        stage = {"agentType": "granted", "model": "opus", "effort": "max", "preload": [],
                 "skill_grant": True, "packet_imperative": "Invoke writing-for-agents with Skill before editing."}
        row = data["rows"][0]
        row["lanes"]["ultracode_stage"] = "inert"
        row["inert_reason"] = "Native caller acceptance pending."
        row["measure"]["planned_ultracode_stage"] = stage
        validate_manifest(self.root, data)
        stage["packet_imperative"] = "Do useful work."
        with self.assertRaisesRegex(WorkflowError, "imperatively name"):
            validate_manifest(self.root, data)

    def test_pending_dependency_has_no_deployed_channel(self):
        data = self.changed()
        row = data["rows"][0]
        row["status"] = "held"
        row["measure"]["pending_skills"] = ["unregistered-trial"]
        row["inert_reason"] = "Await Tier B."
        row["lanes"] = {"cc": [], "blind": [], "ultracode_stage": "inert"}
        validate_manifest(self.root, data)
        row["lanes"]["cc"] = ["description"]
        with self.assertRaisesRegex(WorkflowError, "cannot execute"):
            validate_manifest(self.root, data)

    def test_pending_lane_does_not_disable_existing_other_lane(self):
        data = self.changed()
        row = data["rows"][0]
        row["lanes"]["sdk_worker"] = []
        row["measure"]["pending_lane_dependencies"] = {
            "sdk_worker": {"skills": ["unregistered-trial"], "reason": "S11 and Tier B pending."}}
        validate_manifest(self.root, data)
        row["lanes"]["sdk_worker"] = ["sdk_native_arg"]
        with self.assertRaisesRegex(WorkflowError, "pending lane routed"):
            validate_manifest(self.root, data)

    def test_blind_hint_mutant_fails(self):
        data = self.changed()
        data["rows"][0]["lanes"]["blind"] = ["description"]
        with self.assertRaisesRegex(WorkflowError, "blind lane"):
            validate_manifest(self.root, data)

    def test_held_hook_channel_cannot_become_deployed_by_metadata(self):
        data = self.changed()
        data["rows"][0]["lanes"]["cc"] = ["hook_prompt"]
        with self.assertRaisesRegex(WorkflowError, "held-out routing hooks"):
            validate_manifest(self.root, data)

    def test_challenger_reference_resolves_against_existing_store(self):
        data = self.changed()
        data["rows"][0]["challenger"] = {"ref": "stack:dagu"}
        validate_manifest(self.root, data)
        data["rows"][0]["challenger"]["ref"] = "stack:missing"
        with self.assertRaisesRegex(WorkflowError, "unresolved"):
            validate_manifest(self.root, data)

    def test_routing_layer_cannot_become_pin_store(self):
        data = self.changed()
        data["rows"][0]["tree_sha"] = "a" * 40
        with self.assertRaisesRegex(WorkflowError, "pins belong"):
            validate_manifest(self.root, data)

    def test_pending_foundation_rule_is_outside_active_registry(self):
        data = self.changed()
        data["rows"][0]["lanes"]["cc"] = []
        result = render_foundation_rules(data)
        self.assertIn("adoption/workflow/pending-rules/agent-docs.md", result)
        self.assertNotIn(".claude/rules/agent-docs.md", result)

    def test_trading_owned_rule_path_is_refused(self):
        data = self.changed()
        data["rows"][0]["triggers"]["paths"] = ["blueprints/us-equities/adapter.py"]
        with self.assertRaisesRegex(WorkflowError, "foundation ownership"):
            render_foundation_rules(data)

    def test_empty_required_skills_cannot_erase_routed_obligation(self):
        data = self.changed()
        data["rows"][0]["lanes"]["ultracode_stage"]["required_skills"] = []
        with self.assertRaisesRegex(WorkflowError, "partition"):
            validate_manifest(self.root, data)

    def test_coordinator_partition_excludes_only_explicit_canonical_skills(self):
        data = self.changed()
        row = data["rows"][0]
        row["lanes"]["ultracode_stage"] = {"agentType": "reader", "model": "opus",
            "effort": "max", "preload": [], "required_skills": []}
        row["measure"]["coordinator_only_skills"] = ["writing-for-agents"]
        validate_manifest(self.root, data)
        row["measure"]["coordinator_only_skills"] = ["unregistered"]
        with self.assertRaisesRegex(WorkflowError, "partition"):
            validate_manifest(self.root, data)

    def test_unregistered_native_preload_is_not_its_own_source(self):
        self.text("adoption/agents/claude/loaded.md",
                  (self.root / "adoption/agents/claude/loaded.md").read_text().replace(
                      "writing-for-agents", "absent"))
        data = self.changed()
        data["rows"][0]["lanes"]["ultracode_stage"]["preload"] = ["absent"]
        with self.assertRaisesRegex(WorkflowError, "unresolved"):
            validate_manifest(self.root, data)

    def test_held_source_cannot_enter_active_lane(self):
        self.skill["status"] = "held"
        self.write("adoption/skills/manifest.json", {"skills": [self.skill]})
        with self.assertRaisesRegex(WorkflowError, "held or retired"):
            validate_manifest(self.root, self.manifest)

    def test_client_disabled_source_cannot_alias_codex_builtin(self):
        self.skill.update(codex_enabled=False, agents=["claude-code"])
        self.write("adoption/skills/manifest.json", {"skills": [self.skill]})
        data = self.changed()
        data["rows"][0]["lanes"]["codex_lane"] = ["description"]
        with self.assertRaisesRegex(WorkflowError, "not Codex eligible"):
            validate_manifest(self.root, data)

    def test_codex_enablement_is_a_boolean_not_a_truthy_string(self):
        self.skill["codex_enabled"] = "false"
        self.write("adoption/skills/manifest.json", {"skills": [self.skill]})
        data = self.changed()
        data["rows"][0]["lanes"]["codex_lane"] = ["description"]
        with self.assertRaisesRegex(WorkflowError, "not Codex eligible"):
            validate_manifest(self.root, data)

    def test_held_or_retired_row_does_not_need_pending_metadata_to_be_inert(self):
        for status in ("held", "retired", "candidate"):
            data = self.changed()
            data["rows"][0]["status"] = status
            with self.subTest(status=status), self.assertRaisesRegex(WorkflowError, "cannot execute"):
                validate_manifest(self.root, data)

    def test_grant_cannot_be_activated_by_text_without_native_caller(self):
        data = self.changed()
        data["rows"][0]["lanes"]["ultracode_stage"] = {
            "agentType": "granted", "model": "opus", "effort": "max", "preload": [],
            "skill_grant": True, "packet_imperative": "Invoke writing-for-agents with Skill."}
        with self.assertRaisesRegex(WorkflowError, "pending native caller"):
            validate_manifest(self.root, data)

    def test_all_preloaded_or_coordinator_only_grant_still_needs_native_caller(self):
        data = self.changed()
        row = data["rows"][0]
        row["measure"]["coordinator_only_skills"] = ["writing-for-agents"]
        row["lanes"]["ultracode_stage"] = {"agentType": "granted", "model": "opus",
            "effort": "max", "preload": [], "required_skills": [], "skill_grant": True}
        with self.assertRaisesRegex(WorkflowError, "pending native caller"):
            validate_manifest(self.root, data)

    def test_unknown_nested_pin_or_reference_collection_is_refused(self):
        for value in ({"commit": "a" * 40}, {"references": ["skills:absent"]}):
            data = self.changed()
            data["rows"][0]["challenger"] = value
            with self.subTest(value=value), self.assertRaisesRegex(WorkflowError, "unsupported routing"):
                validate_manifest(self.root, data)

    def test_unverified_plugin_alias_cannot_activate_absent_skill(self):
        data = self.changed()
        data["native_skill_aliases"] = {"fake:skill": "stack:dagu"}
        with self.assertRaisesRegex(WorkflowError, "verified native source"):
            validate_manifest(self.root, data)

    def test_nominal_scalar_fields_cannot_hide_nested_pins(self):
        for where in ("challenger", "measure"):
            data = self.changed()
            key = "reason" if where == "challenger" else "readiness"
            data["rows"][0].setdefault(where, {})[key] = {"commit": "a" * 40, "references": ["skills:absent"]}
            with self.subTest(where=where), self.assertRaisesRegex(WorkflowError, "routing string"):
                validate_manifest(self.root, data)

    def test_trigger_syntax_is_required_and_cannot_change_silently(self):
        for syntax in (None, "unverified_syntax"):
            data = self.changed()
            if syntax is None:
                del data["trigger_syntax"]
            else:
                data["trigger_syntax"] = syntax
            with self.subTest(syntax=syntax), self.assertRaisesRegex(WorkflowError, "trigger_syntax"):
                validate_manifest(self.root, data)

    def test_per_skill_intents_resolve_only_canonical_routed_skills(self):
        data = self.changed()
        triggers = data["rows"][0]["triggers"]
        triggers["skill_intents"] = {"writing-for-agents": [r"\bedit\b"]}
        validate_manifest(self.root, data)
        triggers["skill_intents"] = {"absent": [r"\bedit\b"]}
        with self.assertRaisesRegex(WorkflowError, "canonical row uses"):
            validate_manifest(self.root, data)

    def test_per_skill_intents_cannot_bypass_regex_or_container_validation(self):
        for patterns in ("word", [], ["["]):
            data = self.changed()
            data["rows"][0]["triggers"]["skill_intents"] = {"writing-for-agents": patterns}
            with self.subTest(patterns=patterns), self.assertRaises(WorkflowError):
                validate_manifest(self.root, data)

    def test_broad_glob_does_not_reach_trading_owned_instructions(self):
        for path in ("**/AGENTS.md", "**/SKILL.md", "blueprints/**/SKILL.md"):
            data = self.changed()
            data["rows"][0]["triggers"]["paths"] = [path]
            with self.subTest(path=path), self.assertRaisesRegex(WorkflowError, "foundation ownership"):
                render_foundation_rules(data)

    def test_active_to_pending_transition_detects_stale_rule(self):
        publish_outputs(self.root, render_all(self.root, self.manifest))
        data = self.changed()
        data["rows"][0]["lanes"]["cc"] = []
        errors = check_rendered(self.root, data)
        self.assertTrue(any(".claude/rules/agent-docs.md: obsolete" in item for item in errors))
        with self.assertRaisesRegex(WorkflowError, "obsolete"):
            publish_outputs(self.root, render_all(self.root, data))
        self.assertTrue((self.root / ".claude/rules/agent-docs.md").is_file())

    def test_retired_variant_is_detected_but_unknown_agent_is_not_deleted(self):
        self.text(".claude/agents/isolated-builder-ci-pr.md", "obsolete owned fixture")
        self.text(".claude/agents/another-owner.md", "unrelated fixture")
        self.assertTrue(any("isolated-builder-ci-pr.md: obsolete" in item
                            for item in check_rendered(self.root, self.manifest)))
        with self.assertRaisesRegex(WorkflowError, "obsolete"):
            publish_outputs(self.root, render_all(self.root, self.manifest))
        self.assertEqual((self.root / ".claude/agents/another-owner.md").read_text(), "unrelated fixture")

    def test_later_replace_failure_keeps_complete_files_and_rerender_recovers(self):
        from tools.adoption import render_workflow as renderer
        outputs = {"adoption/workflow/a.md": b"new-a", "adoption/workflow/b.md": b"new-b"}
        self.text("adoption/workflow/a.md", "old-a")
        self.text("adoption/workflow/b.md", "old-b")
        replace = renderer.os.replace
        calls = 0
        def fail_second(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic later publication failure")
            replace(source, target)
        with patch.object(renderer.os, "replace", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "later publication"):
                publish_outputs(self.root, outputs)
        self.assertEqual((self.root / "adoption/workflow/a.md").read_bytes(), b"new-a")
        self.assertEqual((self.root / "adoption/workflow/b.md").read_bytes(), b"old-b")
        self.assertFalse(list(self.root.rglob(".workflow-render-*")))
        publish_outputs(self.root, outputs)
        publish_outputs(self.root, outputs)
        self.assertEqual({path: (self.root / path).read_bytes() for path in outputs}, outputs)


if __name__ == "__main__":
    unittest.main()
