"""Offline synthetic controls for slot requirements; no candidate or host acceptance.

The twelve requirement IDs/texts come from the retained public carrier. Inventory
parents and the five crosswalk rows below are synthetic fixture declarations: the
complete projection proves the mechanism, not a canonical mapping for those five
IDs. Production inputs without an explicit crosswalk must retain that gap.

Native reference: native-agent-stack@8b844d37:scripts/build_new_wsl_handbook.py:459.
Retained requirements:
native-agent-stack@8b844d37:evidence/artifacts/new-wsl-final-architecture-20261002/added-slots/slots.json:6.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tools/sota-convergence/landscape-sweep/slot_requirements.py"
spec = importlib.util.spec_from_file_location("landscape_sweep_slot_requirements", MODULE)
slots = importlib.util.module_from_spec(spec)
spec.loader.exec_module(slots)

REQUIREMENTS = "evidence/artifacts/new-wsl-final-architecture-20261002/added-slots/slots.json"
EXPECTED_IDS = {
    "local-generation-model", "embedding-model", "reranker-model", "alerting-notification", "agents-in-ci",
    "session-analytics", "gpu-container-runtime", "web-search-provider", "structural-code-search",
    "agent-messaging", "secret-scanning", "llm-tracing",
}
DIRECT = {
    "local-generation-model": "observation-inference",
    "embedding-model": "semantic-rag",
    "reranker-model": "semantic-rag",
    "session-analytics": "observation-inference",
    "gpu-container-runtime": "hosting-services",
    "web-search-provider": "web-research",
    "agent-messaging": "workers",
}
# These mappings are intentionally declared by the synthetic fixture, not inferred
# from the historical default or copied into a production crosswalk.
FIXTURE_CROSSWALK = {
    "alerting-notification": ("fixture-alert-owner", "observation-inference"),
    "agents-in-ci": ("fixture-ci-owner", "git-github-automation"),
    "structural-code-search": ("fixture-structural-owner", "code-navigation"),
    "secret-scanning": ("fixture-secret-owner", "secrets-credentials"),
    "llm-tracing": ("fixture-trace-owner", "observation-inference"),
}


def fixture_source(name: str, value: dict | list) -> dict:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return {
        "path": f"fixtures/slot-inputs/{name}.json",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "citation": f"synthetic-fixture@fixture:fixtures/slot-inputs/{name}.json:1",
        "evidence_class": "synthetic_fixture",
    }


class SlotRequirementTests(unittest.TestCase):
    def setUp(self):
        raw = (ROOT / REQUIREMENTS).read_bytes()
        self.requirements = json.loads(raw)
        self.layer_keys = {
            (catalog, layer["layer_id"])
            for catalog in ("foundation", "us-equities")
            for layer in json.loads((ROOT / f"catalogs/landscape/{catalog}.json").read_text())["layers"]
        }
        self.inventory = {
            catalog: {"layers": [{"layer_id": layer_id, "slots": []}
                                 for owner, layer_id in sorted(self.layer_keys) if owner == catalog]}
            for catalog in ("foundation", "us-equities")
        }
        self.inventory["convergence"] = {
            "added_slots": [{"slot_id": identifier, "layer_id": parent} for identifier, parent in DIRECT.items()]
        }
        for target, parent in FIXTURE_CROSSWALK.values():
            layer = next(row for row in self.inventory["foundation"]["layers"] if row["layer_id"] == parent)
            layer["slots"].append({"slot_id": target})
        self.crosswalk = [
            {"slot_id": identifier, "parent_slot_ids": [target],
             "source": fixture_source(identifier, {"parent_slot_ids": [target]})}
            for identifier, (target, _) in FIXTURE_CROSSWALK.items()
        ]
        self.sources = {name: fixture_source(name, value) for name, value in self.inventory.items()}
        self.sources["requirements"] = {
            "path": REQUIREMENTS, "sha256": hashlib.sha256(raw).hexdigest(),
            "citation": f"native-agent-stack@8b844d37:{REQUIREMENTS}:6", "evidence_class": "source_review",
        }

    def project(self, crosswalk=True):
        return slots.project_slot_requirements(
            self.requirements, self.inventory, ("foundation", "us-equities"), self.layer_keys, self.sources,
            crosswalk=self.crosswalk if crosswalk else None,
        )

    def test_complete_twelve_with_explicit_fixture_crosswalk(self):
        result = self.project()
        records = [record for group in result.values() for record in group]
        self.assertEqual({record["slot_id"] for record in records}, EXPECTED_IDS)
        self.assertEqual(len(records), 12)
        self.assertTrue(set(result) <= self.layer_keys)
        self.assertFalse({record["slot_id"] for record in records} & {layer_id for _, layer_id in result})
        originals = {row["layer_id"]: row for row in self.requirements["slots"]}
        for record in records:
            self.assertEqual(record["requirement"], originals[record["slot_id"]]["requirement"])
            self.assertEqual(record["title"], originals[record["slot_id"]]["title"])
            self.assertEqual(record["requirement_status"], "declared")
            index = next(i for i, row in enumerate(self.requirements["slots"])
                         if row["layer_id"] == record["slot_id"])
            self.assertEqual(record["source"]["pointer"], f"/slots/{index}")
            self.assertEqual(record["source"]["sha256"], self.sources["requirements"]["sha256"])

    def test_retained_job_crosswalk_binds_all_twelve_without_component_verdicts(self):
        result = slots.load_slot_requirements(ROOT, self.layer_keys)
        records = {record["slot_id"]: record for group in result.values() for record in group}
        self.assertEqual(set(records), EXPECTED_IDS)
        originals = {row["layer_id"]: row for row in self.requirements["slots"]}
        for identifier, record in records.items():
            self.assertEqual(record["requirement"], originals[identifier]["requirement"])
            self.assertEqual(record["source"]["sha256"], self.sources["requirements"]["sha256"])
            self.assertFalse({"default", "outcome", "adoption_status", "installed"} & record.keys())
        for identifier, expected in slots.JOB_CROSSWALK.items():
            self.assertEqual(records[identifier]["parent"]["slot_ids"], list(expected))
            declarations = records[identifier]["parent_job_declarations"]
            self.assertEqual([row["slot_id"] for row in declarations], list(expected))
            self.assertTrue(all(row["job"] and row["source"]["pointer"] for row in declarations))
        self.assertEqual(records["secret-scanning"]["parent"]["layer_id"], "secrets-credentials")

    def test_seven_identity_mappings_need_no_crosswalk(self):
        self.requirements["slots"] = [row for row in self.requirements["slots"] if row["layer_id"] in DIRECT]
        result = self.project(crosswalk=False)
        for parent, records in result.items():
            for record in records:
                self.assertEqual(parent, ("foundation", DIRECT[record["slot_id"]]))
                self.assertEqual(record["parent"]["slot_ids"], [record["slot_id"]])
                self.assertNotIn("mapping_source", record)
        self.assertEqual(sum(map(len, result.values())), 7)

    def test_missing_crosswalk_cannot_silently_drop_a_requirement(self):
        with self.assertRaisesRegex(ValueError, "alerting-notification.*no inventory parent"):
            self.project(crosswalk=False)

    def test_crosswalk_missing_one_parent_fails(self):
        self.crosswalk[0]["parent_slot_ids"] = ["missing-native-slot"]
        with self.assertRaisesRegex(ValueError, "alerting-notification.*missing-native-slot"):
            self.project()

    def test_native_unknown_layer_guard_is_preserved(self):
        self.inventory["convergence"]["added_slots"][0]["layer_id"] = "new-unapproved-layer"
        with self.assertRaisesRegex(ValueError, "unknown layer: new-unapproved-layer"):
            self.project()

    def test_native_parent_must_exist_in_landscape_taxonomy(self):
        self.layer_keys.remove(("foundation", "observation-inference"))
        with self.assertRaisesRegex(ValueError, "unknown landscape parent"):
            self.project()

    def test_different_crosswalk_parents_are_ambiguous(self):
        self.crosswalk[0]["parent_slot_ids"] += ["fixture-ci-owner"]
        with self.assertRaisesRegex(ValueError, "alerting-notification.*ambiguous parents"):
            self.project()

    def test_two_slots_with_one_parent_preserve_both_references(self):
        self.crosswalk[0]["parent_slot_ids"] += ["fixture-trace-owner"]
        result = self.project()
        record = next(row for row in result[("foundation", "observation-inference")]
                      if row["slot_id"] == "alerting-notification")
        self.assertEqual(record["parent"]["slot_ids"], ["fixture-alert-owner", "fixture-trace-owner"])

    def test_crosswalk_cannot_override_native_parent(self):
        self.crosswalk.append({"slot_id": "embedding-model", "parent_slot_ids": ["fixture-ci-owner"],
                               "source": fixture_source("wrong-parent", {})})
        with self.assertRaisesRegex(ValueError, "disagrees with its native inventory parent"):
            self.project()

    def test_duplicate_requirement_id_fails(self):
        self.requirements["slots"].append(copy.deepcopy(self.requirements["slots"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate requirement slot: local-generation-model"):
            self.project()

    def test_duplicate_native_slot_id_fails(self):
        self.inventory["convergence"]["added_slots"].append(
            {"slot_id": "embedding-model", "layer_id": "workers"})
        with self.assertRaisesRegex(ValueError, "duplicate slot in catalog inventory: embedding-model"):
            self.project()

    def test_native_duplicate_parent_guard_is_preserved(self):
        self.inventory["us-equities"]["layers"].append({"layer_id": "workers", "slots": []})
        with self.assertRaisesRegex(ValueError, "duplicate layer in catalog inventory: workers"):
            self.project()

    def test_duplicate_crosswalk_or_parent_slot_fails(self):
        self.crosswalk.append(copy.deepcopy(self.crosswalk[0]))
        with self.assertRaisesRegex(ValueError, "duplicate crosswalk slot"):
            self.project()
        self.crosswalk.pop()
        self.crosswalk[0]["parent_slot_ids"] *= 2
        with self.assertRaisesRegex(ValueError, "repeats a parent slot"):
            self.project()

    def test_crosswalk_for_unknown_requirement_fails(self):
        self.crosswalk[0]["slot_id"] = "unknown-requirement"
        with self.assertRaisesRegex(ValueError, "unknown requirement slot"):
            self.project()

    def test_crosswalk_needs_its_source(self):
        del self.crosswalk[0]["source"]["citation"]
        with self.assertRaisesRegex(ValueError, "crosswalk source.*needs path, sha256 and citation"):
            self.project()

    def test_requirement_and_parent_sources_are_required(self):
        for missing in ("requirements", "foundation", "convergence"):
            with self.subTest(missing=missing):
                reference = self.sources.pop(missing)
                with self.assertRaisesRegex(ValueError, "needs path, sha256 and citation"):
                    self.project()
                self.sources[missing] = reference

    def test_native_source_hash_and_public_path_guards_are_preserved(self):
        self.sources["requirements"]["sha256"] = "unknown"
        with self.assertRaisesRegex(ValueError, "needs SHA-256"):
            self.project()
        self.sources["requirements"]["sha256"] = "a" * 64
        self.sources["requirements"]["path"] = "../escape.json"
        with self.assertRaisesRegex(ValueError, "public repository path"):
            self.project()

    def test_absent_null_or_blank_text_remains_unknown(self):
        for value in (None, "", " \t\n"):
            with self.subTest(value=value):
                self.requirements["slots"][0]["requirement"] = value
                self.requirements["slots"][0]["job"] = "This must never supply missing requirement text"
                self.requirements["slots"][0]["default"] = {"name": "Selected candidate"}
                self.requirements["slots"][0]["outcome"] = "final"
                record = self.project()[("foundation", "observation-inference")][0]
                self.assertEqual(record["requirement"], value)
                self.assertEqual(record["requirement_status"], "unknown")
                self.assertFalse({"job", "default", "outcome", "installed", "adoption_status"} & record.keys())
        del self.requirements["slots"][0]["requirement"]
        record = self.project()[("foundation", "observation-inference")][0]
        self.assertIsNone(record["requirement"])
        self.assertEqual(record["requirement_status"], "unknown")

    def test_non_text_requirement_fails(self):
        self.requirements["slots"][0]["requirement"] = ["not text"]
        with self.assertRaisesRegex(ValueError, "text must be a string or null"):
            self.project()

    def test_inputs_and_source_objects_are_not_mutated_or_shared(self):
        originals = copy.deepcopy((self.requirements, self.inventory, self.sources, self.crosswalk, self.layer_keys))
        result = self.project()
        record = next(row for row in result[("foundation", "observation-inference")]
                      if row["slot_id"] == "alerting-notification")
        record["source"]["path"] = "changed-output"
        record["parent"]["slot_ids"].append("changed-output")
        record["parent_sources"][0]["sha256"] = "changed-output"
        record["mapping_source"]["path"] = "changed-output"
        self.assertEqual((self.requirements, self.inventory, self.sources, self.crosswalk, self.layer_keys), originals)
        unchanged = result[("foundation", "observation-inference")][0]
        self.assertNotEqual(unchanged["source"]["path"], "changed-output")
        self.assertNotEqual(unchanged["parent_sources"][0]["sha256"], "changed-output")


if __name__ == "__main__":
    unittest.main()
