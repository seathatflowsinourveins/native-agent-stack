"""Source/metadata distinctions in the Architecture presentation."""
import importlib.util
import copy
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("architecture_view", ROOT / "tools/local-pages/architecture_view.py")
VIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VIEW)


class ArchitectureViewTests(unittest.TestCase):
    def setUp(self):
        self.tool = {"name": "measured-tool", "repository": "https://github.com/org/tool", "rationale": "A dated source choice", "invoke": {"status": "measured", "calls": 4, "roles": [{"role": "fixture", "calls": 4, "conversations": 1}], "window_hours": 24}, "e2e": {"verified": True, "date": "2026-01-01T00:00:00Z", "path": "evidence/receipt.json", "sha256": "a" * 64, "command": "vendor test", "result": "PASS", "evidence_class": "native_proven"}}
        self.layer = {"key": "foundation:fixture", "catalog": "foundation", "layer_id": "fixture", "title": "Fixture layer", "current_choice": "measured-tool", "candidates": [self.tool], "winners": [self.tool], "alternatives": [], "rejected": [], "source_quality": [], "g5_candidates": [], "source_refs": ["catalogs/landscape/fixture.json"]}
        self.model = {"layers": [self.layer], "layer_count": 1, "g5": {"status": "candidate, PENDING G5"}, "adoption_observation": {"generated_utc": "2026-01-02T00:00:00Z", "sha256": "b" * 64, "window_hours": 24}, "sources": [], "design": {}, "adoption_program": {"global_stages": ["1 source quality", "2 clean installation", "3 fresh session", "4 observed use"]}}

    def test_stage_labels_follow_source_projection_without_completing_tools(self):
        html = VIEW._tool_progress([self.tool], self.model)
        self.assertEqual(html.count('<li>'), 4)
        for label in self.model["adoption_program"]["global_stages"]:
            self.assertIn(label, html)
        self.assertIn("UNREPORTED per tool; no completed stage inferred", html)
        self.model["adoption_program"] = {}
        html = VIEW._tool_progress([self.tool], self.model)
        self.assertNotIn('<li>', html)
        self.assertIn("Stage labels are UNREPORTED in the CC source", html)

    def test_all_layers_count_and_hashed_role_evidence_columns(self):
        html, receipt = VIEW.render(self.model, {"items": []})
        self.assertEqual(receipt["rendered_layer_count"], self.model["layer_count"])
        self.assertIn("Invoke rate per owning role", html)
        self.assertIn("Latest upstream E2E evidence", html)
        self.assertIn("b" * 64, html)
        self.assertIn("vendor test", html)
        self.assertIn("native_proven", html)
        self.assertIn("1 of 1", html)

    def test_unmeasured_is_not_zero_and_install_is_not_e2e(self):
        self.tool.update(invoke={"status": "unmeasured", "calls": None}, e2e={"verified": False, "path": "install-receipt.json", "sha256": "c" * 64, "result": "installed"})
        html, _ = VIEW.render(self.model, {"items": []})
        self.assertIn("unmeasured", html)
        self.assertIn("no upstream E2E evidence", html)
        self.assertNotIn("0 recorded calls", html)
        self.assertIn("0 of 1", html)

    def test_inventory_exact_identity_and_explicit_unmapped_items(self):
        inventory = {"items": [{"name": "exact", "repository": "org/tool", "kind": "skill"}, {"name": "similar", "repository": "org/tool-other", "kind": "agent"}]}
        mapped, unknown = VIEW.join_inventory(self.model, inventory)
        self.assertEqual([row["name"] for row in mapped[self.layer["key"]]], ["exact"])
        self.assertEqual([row["name"] for row in unknown], ["similar"])
        html, receipt = VIEW.render(self.model, inventory)
        self.assertIn("Unmapped inventory", html)
        self.assertEqual(receipt["unmapped_inventory_items"], 1)

    def test_first_layer_alias_is_a_subset_not_a_new_canonical_layer(self):
        html, receipt = VIEW.render(self.model, {"items": []}, "foundation/fixture")
        self.assertEqual(receipt["rendered_layer_count"], 1)
        self.assertEqual(receipt["canonical_layer_count"], 1)
        self.assertIn('data-layer="foundation:fixture"', html)

    def test_source_text_is_escaped_and_cannot_create_external_resources(self):
        self.tool["rationale"] = '<img src="https://example.org/x" onerror="alert(1)">'
        html, _ = VIEW.render(self.model, {"items": []})
        self.assertNotIn('<img src=', html)
        self.assertIn('&lt;img', html)

    def test_progress_uses_attached_owning_role_and_e2e_without_raw_instance_metadata(self):
        self.tool["invoke"]["roles"] = [{
            "client": "Codex", "role": "g5-stars-gap", "server": "measured-tool",
            "calls": 10, "conversations": 5, "window_hours": 24,
            "source_instances": ["mahe", "vame"],
            "instance_observations": [{"role": "mahe", "calls": 4}, {"role": "vame", "calls": 6}],
            "aggregation_scope": "sum of published instance counts; distinct cross-instance conversations unverified",
        }]
        self.tool["invoke"]["calls"] = 10
        self.tool["adoption_stage"] = "fresh-session evidence pending"
        self.model["adoption_observation"]["codex_by_lane"] = {
            "raw-fixture": {"conversations": 9, "servers": {"measured-tool": {"calls": 999}}},
        }
        before = copy.deepcopy(self.tool)
        html = VIEW._tool_progress([self.tool], self.model)
        self.assertIn("Invoke rate per owning role", html)
        self.assertIn("Latest upstream E2E evidence", html)
        self.assertIn("Codex g5-stars-gap (measured-tool): 10 recorded calls", html)
        self.assertIn("0.417 calls/hour", html)
        self.assertIn("published conversation count: 5", html)
        self.assertIn("distinct cross-instance conversations unverified", html)
        self.assertIn("vendor test", html)
        self.assertIn("fresh-session evidence pending", html)
        for raw in ("raw-fixture", "999", "instance_observations", "source_instances", "mahe", "vame"):
            self.assertNotIn(raw, html)
        self.assertEqual(self.tool, before)

    def test_all_per_tool_tables_have_both_contract_columns(self):
        self.layer.update(alternatives=[copy.deepcopy(self.tool)], rejected=[copy.deepcopy(self.tool)], source_quality=[copy.deepcopy(self.tool)], g5_candidates=[copy.deepcopy(self.tool)])
        inventory = {"items": [dict(self.tool, kind="skill", layer_id="fixture"), {"name": "unbound", "kind": "agent"}]}
        html, _ = VIEW.render(self.model, inventory)
        tables = [table for table in re.findall(r"<table>.*?</table>", html, re.S)
                  if any(f'<th scope="col">{header}</th>' in table for header in ("Tool / repository", "Name", "Candidate"))]
        self.assertGreaterEqual(len(tables), 8)
        for table in tables:
            self.assertIn("Invoke rate per owning role", table)
            self.assertIn("Latest upstream E2E evidence", table)

    def test_progress_unknown_and_recorded_zero_stay_distinct(self):
        measured = copy.deepcopy(self.tool)
        measured["name"] = "zero-tool"
        measured["invoke"].update(calls=0, roles=[{"client": "Codex", "role": "recorded-lane", "calls": 0, "conversations": 0}], window_hours=24)
        unknown = {"name": "unknown-tool", "invoke": {"calls": None, "status": "unmeasured"}}
        html = VIEW._tool_progress([measured, unknown], self.model)
        self.assertIn("recorded-lane: 0 recorded calls; 0.000 calls/hour", html)
        self.assertIn("published conversation count: 0", html)
        self.assertIn("<td>unmeasured</td>", html)
        self.assertIn("no upstream E2E evidence", html)
        self.assertEqual(html.count("0 recorded calls"), 1)

    def test_unattached_raw_instance_observations_do_not_imply_owning_role_use(self):
        raw = {"name": "measured-tool"}
        self.model["adoption_observation"]["codex_by_lane"] = {
            "raw-fixture": {"conversations": 1, "servers": {"measured-tool": {"calls": 24}}},
        }
        self.assertEqual(VIEW._invoke_text(raw, self.model), "unmeasured")
        html = VIEW._tool_progress([raw], self.model)
        self.assertNotIn("raw-fixture", html)
        self.assertIn("<td>unmeasured</td>", html)

    def test_role_counts_remain_visible_when_rate_window_is_unknown(self):
        self.tool["invoke"].update(window_hours=None, roles=[{"client": "Claude", "role": "native-agent-stack-1a", "calls": 4, "sessions": 1}])
        text = VIEW._invoke_text(self.tool, self.model)
        self.assertIn("owner session (reports to CC): 4 recorded calls; rate unmeasured", text)
        self.assertIn("published session count: 1", text)


if __name__ == "__main__":
    unittest.main()
