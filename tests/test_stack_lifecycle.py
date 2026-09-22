"""Contract checks for the portable, scoped lifecycle matrix."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

# Components selected in manifests/stack.json whose row in
# blueprints/token-native-focus/saturation-audit.json is not yet recorded. That
# audit file is generated/owned outside this change's scope; a separate,
# coordinator-owned edit must add the matching row before these components can
# be dropped from this explicit, reviewed allowlist. Do not add an id here
# without a concrete reason recorded in the same commit.
PENDING_LIFECYCLE_AUDIT_COMPONENTS = {
    # Added directly to manifests/stack.json (pr4-stack unit); the lifecycle
    # audit row is out of that unit's owned paths and is a follow-up.
    "exchange-calendars",
}


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
        stack_ids = {c["id"] for c in self.stack["components"]}
        audited_ids = set(self.rows)
        # Every stack component is either audited, or explicitly and narrowly
        # allowlisted as pending audit (see PENDING_LIFECYCLE_AUDIT_COMPONENTS).
        # No unexpected/undocumented drift between the two files is tolerated.
        self.assertEqual(audited_ids | PENDING_LIFECYCLE_AUDIT_COMPONENTS, stack_ids)
        self.assertTrue(PENDING_LIFECYCLE_AUDIT_COMPONENTS <= (stack_ids - audited_ids))
        for component in self.stack["components"]:
            if component["id"] in PENDING_LIFECYCLE_AUDIT_COMPONENTS:
                continue
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

    def test_exchange_calendars_pending_component_has_a_real_pinned_evidence_target(self):
        """exchange-calendars is new in manifests/stack.json (pr4-stack unit).

        It is intentionally exempted above from the audit cross-check (see
        PENDING_LIFECYCLE_AUDIT_COMPONENTS) because its lifecycle-audit row is
        out of this unit's owned paths. This test still holds the component's
        own identity, evidence reference and pin to a concrete standard: the
        cited receipt id must be real and hash-listed, even though
        scripts/validate.py separately reports that the receipt's own
        component_ids field does not yet name this component (a known,
        reported gap for the coordinator to close in manifests/evidence.json).
        """
        components = {c["id"]: c for c in self.stack["components"]}
        self.assertIn("exchange-calendars", components)
        component = components["exchange-calendars"]
        self.assertEqual(component["repository"], "https://github.com/gerrymanoim/exchange_calendars")
        self.assertEqual(component["version"], "4.13.2")
        self.assertEqual(component["profile"], "supporting")
        self.assertTrue(component["evidence_ids"])
        for receipt_id in component["evidence_ids"]:
            self.assertIn(receipt_id, self.receipts, f"{receipt_id} must be a real receipt id in manifests/evidence.json")
            self.assertTrue(self.receipts[receipt_id].get("path"))
        supporting_profile = next(p for p in self.stack["profiles"] if p["id"] == "supporting")
        self.assertIn("exchange-calendars", supporting_profile["component_ids"])


if __name__ == "__main__":
    unittest.main()
