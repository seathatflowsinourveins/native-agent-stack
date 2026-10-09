"""Shared invocation normalization is idempotent and preserves measured scope."""

import copy
import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "architecture_builder_roles", Path(__file__).resolve().parents[1] / "tools/local-pages/architecture_builder.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def role(instance, calls, conversations=1, server="context-mode"):
    return {"role": instance, "client": "Codex", "server": server, "calls": calls, "conversations": conversations, "window_hours": 24}


class ArchitectureRoleTests(unittest.TestCase):
    def test_shared_inventory_component_and_repeat_keep_role_and_source_identity(self):
        raw = {"calls": 7, "roles": [role("mahe", 7)], "sha256": "fixture-source"}
        source = copy.deepcopy(raw)
        inventory = {"invoke": raw}
        component = {"invoke": raw}
        owners = {"mahe": "g5-stars-gap"}
        builder._normalize_invocation_roles([inventory, component, inventory], owners)
        normalized = copy.deepcopy(inventory["invoke"])
        self.assertEqual(raw, source)
        self.assertIs(inventory["invoke"], component["invoke"])
        row = inventory["invoke"]["roles"][0]
        self.assertEqual(row["role"], "g5-stars-gap")
        self.assertEqual(row["source_instances"], ["mahe"])
        self.assertEqual(row["instance_observations"][0]["role"], "mahe")
        self.assertEqual(row["instance_observations"][0]["source_instance"], "mahe")
        builder._normalize_invocation_roles([inventory, component], owners)
        self.assertEqual(inventory["invoke"], normalized)
        self.assertEqual(component["invoke"], normalized)
        self.assertEqual(inventory["invoke"]["sha256"], "fixture-source")

    def test_group_by_owner_and_server_preserves_totals_and_unattributed_instances(self):
        raw = {"calls": 23, "roles": [
            role("mahe", 4, 2), role("vame", 6, 3),
            role("unknown", 3, 4), role("missing", 0, 0),
            role("mahe", 5, 2, "serena"),
            {"role": "owner", "client": "Claude", "server": "context-mode", "calls": 5, "sessions": 1, "window_hours": 24},
        ]}
        component = {"invoke": raw}
        builder._normalize_invocation_roles([component], {"mahe": "lane-a", "vame": "lane-a"})
        rows = component["invoke"]["roles"]
        codex = {(row["role"], row["server"]): row for row in rows if row["client"] == "Codex"}
        combined = codex[("lane-a", "context-mode")]
        self.assertEqual(combined["calls"], 10)
        self.assertEqual(combined["conversations"], 5)
        self.assertEqual(combined["source_instances"], ["mahe", "vame"])
        unknown = codex[("unattributed instances", "context-mode")]
        self.assertEqual(unknown["calls"], 3)
        self.assertEqual(unknown["source_instances"], ["unknown", "missing"])
        self.assertEqual(sum(row["calls"] for row in rows), raw["calls"])
        self.assertEqual(sum(row["conversations"] for row in rows if row["client"] == "Codex"), 11)
        self.assertEqual(next(row for row in rows if row["client"] == "Claude"), raw["roles"][-1])
        self.assertIn("distinct cross-instance conversations unverified", combined["aggregation_scope"])

    def test_missing_counts_stay_unmeasured_zero_remains_measured_and_windows_stay_separate(self):
        rows = [role("mahe", None, None), role("vame", 4, 2), role("zero", 0, 0)]
        other_window = role("mahe", 2, 1)
        other_window["window_hours"] = 48
        rows.append(other_window)
        component = {"invoke": {"calls": None, "roles": rows}}
        builder._normalize_invocation_roles([component], {"mahe": "lane-a", "vame": "lane-a", "zero": "lane-zero"})
        grouped = {(row["role"], row["window_hours"]): row for row in component["invoke"]["roles"]}
        self.assertIsNone(grouped[("lane-a", 24)]["calls"])
        self.assertIsNone(grouped[("lane-a", 24)]["conversations"])
        self.assertEqual(grouped[("lane-zero", 24)]["calls"], 0)
        self.assertEqual(grouped[("lane-zero", 24)]["conversations"], 0)
        self.assertEqual(grouped[("lane-a", 48)]["calls"], 2)
        self.assertIsNone(component["invoke"]["calls"])

    def test_reprojection_uses_retained_source_instance_not_previous_owner(self):
        component = {"invoke": {"calls": 7, "roles": [role("mahe", 7)]}}
        builder._normalize_invocation_roles([component], {"mahe": "lane-old"})
        builder._normalize_invocation_roles([component], {"mahe": "lane-new"})
        row = component["invoke"]["roles"][0]
        self.assertEqual(row["role"], "lane-new")
        self.assertEqual(row["source_instances"], ["mahe"])
        self.assertEqual(row["calls"], 7)


if __name__ == "__main__":
    unittest.main()
