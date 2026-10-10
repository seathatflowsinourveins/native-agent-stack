"""Role-window ambiguity, count conservation and published-only tool counters."""

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "adoption_roles", Path(__file__).resolve().parents[1] / "tools/local-pages/adoption_roles.py"
)
roles = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(roles)


def row(conversations, calls):
    return {"conversations": conversations, "servers": {"context-mode": {"calls": calls, "conversations": conversations}}}


def document(labels=None):
    return {
        "schema": "adoption-now/1", "generated_utc": "2026-10-09T01:00:00Z", "window_hours": 24,
        "codex_by_lane": labels or {}, "claude_by_role": {}, "layers": {},
        "orchestration": {"claude_by_role": {}, "codex_by_lane": {}, "unmeasured": ["hcom launches and kills"]},
    }


class AdoptionRolesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name).resolve()
        self.base = self.state / "coordination/ns2604-coop"

    def write(self, relative, value):
        path = self.base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return path

    def test_unique_recorded_launch_projects_lane_and_preserves_input(self):
        self.write("lanes/hcom-lanes.json", {"lane-a": {"name": "tag-mahe", "launched": "2026-10-08T12:00:00Z", "thread": "fixture-thread"}})
        source = document({"mahe": row(4, 17)})
        before = copy.deepcopy(source)
        result = roles.project(source, self.state)
        self.assertEqual(result["instances"]["role_map"], {"mahe": "lane-a"})
        self.assertEqual(result["codex_roles"]["lane-a"]["conversations"], 4)
        self.assertEqual(result["codex_roles"]["lane-a"]["calls"], 17)
        self.assertEqual(result["document"]["codex_by_lane"]["lane-a"]["servers"]["context-mode"]["calls"], 17)
        self.assertEqual(source, before)
        self.assertEqual(len(result["sources"][0]["sha256"]), 64)

    def test_recurrent_alias_across_nonoverlapping_launches_in_window_is_unattributed(self):
        self.write("lanes/hcom-lanes.json", {
            "lane-a": {"name": "tag-mahe", "launched": "2026-10-08T03:00:00Z", "closed": "2026-10-08T10:00:00Z"},
            "lane-b": {"name": "other-mahe", "launched": "2026-10-08T12:00:00Z"},
        })
        result = roles.project(document({"mahe": row(7, 29)}), self.state)
        self.assertEqual(result["codex_roles"], {})
        self.assertEqual(result["instances"]["unattributed"]["mahe"]["candidate_roles"], ["lane-a", "lane-b"])
        self.assertEqual(result["document"]["codex_by_lane"]["unattributed instances"]["conversations"], 7)

    def test_outside_window_is_excluded_but_undated_history_cannot_rule_out_alias_collision(self):
        self.write("lanes/hcom-lanes.json", {
            "old-lane": {"name": "old-mahe", "launched": "2026-10-07T03:00:00Z", "closed": "2026-10-07T10:00:00Z"},
            "new-lane": {"name": "new-mahe", "launched": "2026-10-08T12:00:00Z"},
        })
        result = roles.project(document({"mahe": row(2, 5)}), self.state)
        self.assertEqual(result["instances"]["role_map"]["mahe"], "new-lane")
        self.write("lanes/threads.json", {"unknown-lane": {"name": "unknown-mahe"}})
        result = roles.project(document({"mahe": row(2, 5)}), self.state)
        self.assertIsNone(result["instances"]["role_map"]["mahe"])

    def test_unknown_or_future_launch_and_timestamp_free_alias_are_not_guessed(self):
        self.write("lanes/hcom-lanes.json", {
            "future-lane": {"name": "tag-mahe", "launched": "2026-10-09T02:00:00Z"},
            "undated-lane": {"name": "tag-luva"},
        })
        result = roles.project(document({"mahe": row(1, 1), "luva": row(2, 2), "unknown": row(3, 3)}), self.state)
        self.assertEqual(len(result["instances"]["unattributed"]), 3)
        self.assertEqual(result["codex_roles"], {})

    def test_duplicate_registry_and_receipts_do_not_double_count(self):
        record = {"lane-a": {"name": "tag-mahe", "launched": "2026-10-08T12:00:00Z"}}
        self.write("lanes/hcom-lanes.json", record)
        self.write("lanes/threads.json", record)
        self.write("notes/parking-20261008/park-apply-fixture.json", {
            "apply": True, "before": {"at": "2026-10-08T14:00:00Z"}, "after": {"at": "2026-10-08T14:01:00Z"},
            "plan": [{"lane": "lane-a", "name": "tag-mahe", "park": True, "kill_rc": 0}],
        })
        result = roles.project(document({"mahe": row(3, 13)}), self.state)
        self.assertEqual(result["codex_roles"]["lane-a"]["conversations"], 3)
        self.assertEqual(result["codex_roles"]["lane-a"]["calls"], 13)
        self.assertEqual(result["codex_roles"]["lane-a"]["instances"], 1)

    def test_old_parking_fields_do_not_close_a_relaunched_instance(self):
        self.write("lanes/hcom-lanes.json", {
            "lane-a": {
                "name": "tag-mahe", "launched": "2026-10-08T12:00:00Z",
                "parked": "2026-10-07T04:00:00Z", "parked_name": "tag-luva",
                "last_parked": "2026-10-07T05:00:00Z", "last_parked_name": "tag-luva",
            },
        })
        result = roles.project(document({"mahe": row(1, 1)}), self.state)
        self.assertEqual(result["instances"]["role_map"]["mahe"], "lane-a")

    def test_conservation_with_unattributed_and_server_populations_remain_scoped(self):
        self.write("lanes/hcom-lanes.json", {"lane-a": {"name": "tag-mahe", "launched": "2026-10-08T12:00:00Z", "previous_name": "tag-luva"}})
        source = document({"mahe": row(3, 13), "luva": row(2, 7), "unknown": row(4, 11)})
        source["codex_by_lane"]["mahe"]["servers"]["serena"] = {"calls": 5, "conversations": 3}
        result = roles.project(source, self.state)
        shown = result["document"]["codex_by_lane"]
        self.assertEqual(sum(r["conversations"] for r in shown.values()), 9)
        self.assertEqual(shown["lane-a"]["conversations"], 5)
        self.assertEqual(shown["lane-a"]["servers"]["serena"]["conversations"], 3)
        self.assertEqual(sum(r["calls"] for r in shown.values()), 36)

    def test_exact_orchestration_measures_are_aggregated_once(self):
        self.write("lanes/hcom-lanes.json", {"lane-a": {"name": "tag-mahe", "launched": "2026-10-08T12:00:00Z", "previous_name": "tag-luva"}})
        source = document({"mahe": row(1, 1), "luva": row(1, 1)})
        source["orchestration"]["claude_by_role"] = {roles.OWNER: {"Agent": 0, "SendMessage": 3}}
        source["orchestration"]["codex_by_lane"] = {"mahe": {"spawn_agent": 0, "send_message": 2}, "luva": {"spawn_agent": 4}, "unknown": {"spawn_agent": 5}}
        result = roles.project(source, self.state)
        counts = result["orchestration"]
        self.assertEqual(counts["codex_by_role"]["lane-a"], {"spawn_agent": 4, "send_message": 2})
        self.assertEqual(counts["codex_unattributed"]["unknown"]["spawn_agent"], 5)
        self.assertEqual(counts["claude_by_role"][roles.OWNER]["Agent"], 0)
        self.assertIn("hcom launches and kills", counts["unmeasured"])
        self.assertNotIn("wait_agent", counts["codex_by_role"]["lane-a"])

    def test_missing_sdk_is_unreported_and_explicit_sdk_rows_keep_zero_and_unknown(self):
        source = document()
        self.assertEqual(roles.project(source, self.state)["sdk"]["status"], "UNREPORTED")
        source["layers"] = {"client-native": {"servers": {"sdk:codex_sdk_ts": {"codex_calls": 0, "codex_conversations": None, "claude_calls": None}}}}
        sdk = roles.project(source, self.state)["sdk"]
        self.assertEqual(sdk["status"], "MEASURED")
        self.assertEqual(sdk["rows"][0]["client"], "sdk:codex_sdk_ts")
        self.assertEqual(sdk["rows"][0]["codex_calls"], 0)
        self.assertIsNone(sdk["rows"][0]["codex_conversations"])
        self.assertNotIn("claude_sessions", sdk["rows"][0])

    def test_missing_measurement_and_invalid_window_do_not_create_zero(self):
        source = document({"unknown": {"conversations": None, "servers": None}})
        del source["orchestration"]
        result = roles.project(source, self.state)
        self.assertIsNone(result["document"]["codex_by_lane"]["unattributed instances"]["conversations"])
        self.assertIn("codex_by_lane orchestration", result["orchestration"]["unmeasured"])
        source["generated_utc"] = "invalid"
        with self.assertRaises(ValueError):
            roles.project(source, self.state)

    def test_unrepresentable_registry_date_does_not_create_attribution(self):
        self.write("lanes/hcom-lanes.json", {
            "lane-a": {"name": "tag-mahe", "launched": "0001-01-01T00:00:00+01:00"},
        })
        result = roles.project(document({"mahe": row(2, 7)}), self.state)
        self.assertIsNone(result["instances"]["role_map"]["mahe"])
        self.assertEqual(result["document"]["codex_by_lane"]["unattributed instances"]["conversations"], 2)
        self.assertEqual(result["document"]["codex_by_lane"]["unattributed instances"]["calls"], 7)

    def test_nonobject_registry_remains_unreported(self):
        path = self.base / "lanes/hcom-lanes.json"
        path.parent.mkdir(parents=True)
        path.write_text('[{"synthetic": "not a registry object"}]', encoding="utf-8")
        result = roles.project(document({"mahe": row(2, 7)}), self.state)
        self.assertIsNone(result["instances"]["role_map"]["mahe"])
        self.assertEqual(result["document"]["codex_by_lane"]["unattributed instances"]["calls"], 7)
        self.assertTrue(any("UNREPORTED" in error["status"] for error in result["source_errors"]))

    def test_receipt_count_bound_applies_to_parking_and_capacity_together(self):
        for index in range(129):
            self.write(f"notes/parking-20261008/park-fixture-{index:03d}.json", {})
        self.write("notes/capacity-ruling-20261008/relay-receipt.json", {
            "at": "2026-10-08T12:00:00Z", "plan": [{"lane": "capacity-lane", "name": "tag-mahe"}],
        })
        result = roles.project(document({"mahe": row(2, 7)}), self.state)
        self.assertIsNone(result["instances"]["role_map"]["mahe"])
        self.assertEqual(result["sources"], [])
        self.assertTrue(any("receipt count exceeds bound" in error["status"] for error in result["source_errors"]))


if __name__ == "__main__":
    unittest.main()
