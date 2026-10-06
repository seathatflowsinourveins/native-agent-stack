"""Synthetic controls over the copied candidate's existing strict comparator.

No native engine, broker, provider or candidate main() is invoked.
"""
import copy
import hashlib
import json
import unittest

from tests import test_spy_parity as baseline

SOURCE = baseline.SOURCE
COMPARE = baseline._load("spy_rc6_compare_fixture", SOURCE / "compare-rc6.py")
MANIFEST = json.loads((SOURCE / "mapping-manifest-rc6.json").read_text())
EFFECTIVE = COMPARE.effective_manifest(MANIFEST, baseline.MANIFEST)


def candidate_fixture():
    """Reuse the established fixture, changing only candidate identity metadata."""
    receipt = baseline._v2_receipt()
    receipt["engine"] = copy.deepcopy(MANIFEST["engine"])
    receipt["case_configuration"]["fee_model"] = copy.deepcopy(MANIFEST["case_configuration"]["fee_model"])
    receipt["mapping_manifest"]["sha256"] = COMPARE.SEALED_V2_MANIFEST_SHA256
    receipt["local_source_sha256"] = {name: "a" * 64 for name in COMPARE.REVIEWED_HARNESS_FILES}
    context = baseline._context()
    context["review_record"]["content"]["reviewed_local_source_sha256"] = dict(receipt["local_source_sha256"])
    context["deviation_acceptance"]["content"]["reviewed_harness_local_source_sha256"] = dict(receipt["local_source_sha256"])
    receipt["preconditions"]["deviation_acceptance"]["path"] = (
        "blueprints/us-equities/engine-nautilus/spy-parity/" + COMPARE.DEVIATION_ACCEPTANCE)
    return receipt, context


class Rc6CandidateTests(unittest.TestCase):
    def verdict(self, receipt, context):
        return COMPARE.compare(receipt, baseline.ORACLE, baseline.TOLERANCES,
                               EFFECTIVE, baseline.V2_BARS, context)

    def test_candidate_manifest_is_sealed_and_fee_descriptor_matches_the_runner(self):
        self.assertEqual(hashlib.sha256((SOURCE / "mapping-manifest-rc6.json").read_bytes()).hexdigest(),
                         COMPARE.SEALED_V2_MANIFEST_SHA256)
        self.assertEqual(MANIFEST["engine"]["version"], "2.0.0rc6")
        self.assertEqual(MANIFEST["case_configuration"]["fee_model"],
                         {"class": "MakerTakerFeeModel", "maker_rate": "0", "taker_rate": "0"})
        self.assertEqual(MANIFEST["rc5_historical_engine_provenance"], baseline.MANIFEST_V2["engine"])
        self.assertEqual(COMPARE.REVIEWED_HARNESS_FILES[-3:],
                         ("compare-rc6.py", "mapping-manifest-rc6.json",
                          "PREREGISTRATION-ADDENDUM-rc6-20261006.md"))

    def test_frozen_mapping_method_is_unchanged_outside_identity_and_fee_model(self):
        allowed = {"id", "drafted_utc_date", "run_status_note", "engine", "case_configuration"}
        for key, value in baseline.MANIFEST_V2.items():
            if key not in allowed:
                self.assertEqual(MANIFEST[key], value, key)
        old, new = copy.deepcopy(baseline.MANIFEST_V2["case_configuration"]), copy.deepcopy(MANIFEST["case_configuration"])
        old.pop("fee_model")
        new.pop("fee_model")
        self.assertEqual(old, new)
        original = SOURCE / "replay-history-v2.json"
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),
                         "ca08721fe7f197151cb2f061794a2064809b8a88e9b865d1c62c2279a4af740c")
        old_history = json.loads(original.read_text())
        new_history = json.loads((SOURCE / "replay-history-rc6.json").read_text())
        self.assertEqual(new_history["replays"][:len(old_history["replays"])], old_history["replays"])
        appended = {row["id"]: row for row in new_history["replays"][len(old_history["replays"]):]}
        self.assertEqual(appended["j2-rc5-runtime-env-20261006"]["engine_version"], "2.0.0rc5")
        self.assertEqual(appended["j2-rc5-documented-env-20261006"]["engine_version"], "2.0.0rc5")

    def test_existing_synthetic_full_method_passes_with_candidate_identity(self):
        receipt, context = candidate_fixture()
        result = self.verdict(receipt, context)
        self.assertEqual(result["verdict"], "PASS", baseline._failing_fields(result))

    def test_wrong_extension_and_old_review_cannot_pass_the_candidate(self):
        for change in ("extension", "review", "acceptance"):
            with self.subTest(change=change):
                receipt, context = candidate_fixture()
                if change == "extension":
                    receipt["engine"]["extension_sha256"] = baseline.MANIFEST_V2["engine"]["extension_sha256"]
                elif change == "review":
                    context["review_record"]["content"]["reviewed_local_source_sha256"] = dict(baseline.SYNTHETIC_REVIEW["reviewed_local_source_sha256"])
                else:
                    context["deviation_acceptance"]["content"]["reviewed_harness_local_source_sha256"] = dict(baseline.SYNTHETIC_ACCEPTANCE["reviewed_harness_local_source_sha256"])
                result = self.verdict(receipt, context)
                self.assertEqual(result["verdict"], "FAIL")
                self.assertTrue(baseline._failing_fields(result))

    def test_wrong_price_fee_and_cash_still_fail_without_new_allowances(self):
        for field in ("price", "fees", "cash"):
            with self.subTest(field=field):
                receipt, context = candidate_fixture()
                if field == "price":
                    receipt["fills"][0]["price"] = "323.5900"
                elif field == "fees":
                    receipt["fills"][0]["fee"] = "1.00"
                else:
                    receipt["native_end_cash_usd"] = "90735.08"
                self.assertEqual(self.verdict(receipt, context)["verdict"], "FAIL")

    def test_receipt_binding_rejects_old_manifest_and_untruthful_fee_metadata(self):
        receipt = baseline._rebound_to_current_harness(json.loads(baseline.RECEIPT_V2.read_text()))
        receipt["engine"]["version"] = "2.0.0rc6"
        receipt["mapping_manifest"] = {"path": "mapping-manifest-rc6.json", "sha256": COMPARE.SEALED_V2_MANIFEST_SHA256}
        receipt["case_configuration"]["fee_model"] = copy.deepcopy(MANIFEST["case_configuration"]["fee_model"])
        receipt["local_source_sha256"] = {
            name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() for name in COMPARE.V2_SOURCES}
        args = (receipt, SOURCE / "tolerances.json", SOURCE / "mapping-manifest-rc6.json")
        plan = SOURCE.parent.parent / "historical-simulation/plan.json"
        COMPARE.bind(*args, plan_path=plan)
        receipt["case_configuration"]["fee_model"] = None
        with self.assertRaisesRegex(ValueError, "case_configuration.*fee_model"):
            COMPARE.bind(*args, plan_path=plan)
        receipt["mapping_manifest"]["sha256"] = baseline.COMPARE.SEALED_V2_MANIFEST_SHA256
        with self.assertRaisesRegex(ValueError, "sealed_manifest"):
            COMPARE.bind(receipt, SOURCE / "tolerances.json", SOURCE / "mapping-manifest-v2.json")


if __name__ == "__main__":
    unittest.main()
