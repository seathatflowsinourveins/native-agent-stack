"""Contract checks for the portable, scoped lifecycle matrix."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StackLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = json.loads((ROOT / "blueprints/token-native-focus/saturation-audit.json").read_text())
        cls.stack = json.loads((ROOT / "manifests/stack.json").read_text())
        cls.adoption = json.loads((ROOT / "adoption/manifest.json").read_text())
        cls.index = json.loads((ROOT / "catalogs/us-equities/decision-index.json").read_text())
        cls.receipts = {r["id"]: r for r in json.loads((ROOT / "manifests/evidence.json").read_text())["receipts"]}
        cls.rows = {r["component_id"]: r for r in cls.audit["components"]}

    def test_every_selected_component_has_current_identity_and_receipts(self):
        self.assertEqual(len(self.rows), len(self.audit["components"]))
        self.assertEqual(set(self.rows), {c["id"] for c in self.stack["components"]})
        for component in self.stack["components"]:
            with self.subTest(component=component["id"]):
                row = self.rows[component["id"]]
                for key in ("repository", "version", "profile", "role"):
                    self.assertEqual(row[key], component[key])
                refs = row["functional_evidence"]["public_receipts"]
                self.assertEqual({r["id"] for r in refs}, set(component["evidence_ids"]))
                for receipt in refs:
                    self.assertEqual(receipt["path"], self.receipts[receipt["id"]]["path"])
                self.assertEqual(row["native_integration"]["recipe_document"], self.adoption["recipe_map"][component["id"]])

    def test_catalog_partition_matches_canonical_union(self):
        counts = self.audit["counts"]
        self.assertEqual(counts["selected_components"], len(self.rows))
        self.assertEqual(counts["catalog_identities"], len(self.index["records"]))
        self.assertEqual(sum(counts["exclusive_identity_groups"].values()), counts["catalog_identities"])
        self.assertEqual(counts["selected_components"] + counts["nonselected_catalog_identities"], counts["catalog_identities"])

    def test_stage_states_require_scope_and_supported_local_references(self):
        stages = set(self.audit["stage_policy"]["stages"])
        statuses = set(self.audit["stage_policy"]["statuses"])
        for cid, row in self.rows.items():
            self.assertEqual(set(row["lifecycle_stages"]), stages, cid)
            self.assertIsNone(row["exact_causal_lifetime_provider_tokens_saved"], cid)
            self.assertFalse(row["current_host_recertified_by_this_audit"], cid)
            for name, stage in row["lifecycle_stages"].items():
                with self.subTest(component=cid, stage=name):
                    self.assertIn(stage["status"], statuses)
                    self.assertTrue(stage["scope"].strip())
                    if stage["status"] in {"accepted_within_scope", "observed_installed", "partial_acceptance"}:
                        self.assertTrue(stage["evidence_refs"])
                    for reference in stage["evidence_refs"]:
                        target = (ROOT / reference.split("#", 1)[0]).resolve()
                        self.assertTrue(target.is_relative_to(ROOT))
                        self.assertTrue(target.is_file(), reference)
            self.assertTrue((ROOT / row["native_integration"]["recipe_document"]).is_file())

    def test_baselines_and_remaining_boundaries_are_not_promoted_to_passes(self):
        for row in self.rows.values():
            baseline = row["baseline_applicability"]
            self.assertIn(baseline["category"], {"guidance", "direct_context", "supporting_workflow"})
            self.assertEqual(baseline["retained_artifact_comparisons"], len(row["artifact_baselines"]))
            self.assertEqual(baseline["matched_lifetime_provider_baseline"], "not_established")
        hud = self.rows["claude-hud"]["lifecycle_stages"]
        self.assertEqual(hud["use"]["status"], "accepted_within_scope")
        self.assertIn("evidence/receipts/foundation-closure-20260921.json", hud["use"]["evidence_refs"])
        self.assertEqual(hud["recovery"]["status"], "not_established")
        self.assertEqual(self.rows["codex-for-claude"]["lifecycle_stages"]["use"]["status"], "partial_acceptance")
        self.assertEqual(self.rows["postgresql"]["lifecycle_stages"]["recovery"]["status"], "not_established")
        self.assertIn("macOS", self.rows["apple-container"]["installation_assessment"])


if __name__ == "__main__":
    unittest.main()
