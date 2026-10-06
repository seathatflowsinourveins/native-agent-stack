"""Synthetic input-projection regressions; no files, network, models, installs or sweep execution.

The retained-vote fixture is interpreted by saturation_ledger's native resolver. These tests check the local input
projection and cannot establish current candidate merit, native acceptance or adoption.
"""

from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools/sota-convergence/landscape-sweep"


def load_module(name, path):
    # Import pattern: tests/test_landscape_sweep_harness.py at e28d0eec, load().
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_inputs = load_module("history_build_inputs", HARNESS / "build_inputs.py")
ledger_rules = load_module("history_saturation_ledger", ROOT / "scripts/saturation_ledger.py")
REQ, PLAT = "a" * 64, "b" * 64


def outcome(repo, index, vote="refuted"):
    return {"repo": f"https://github.com/o/{repo}",
            "facts": {"vote": "not_refuted", "ref": f"evidence/returns.json#/votes/{index}/facts"},
            "fit": {"vote": vote, "ref": f"evidence/returns.json#/votes/{index}/fit"}}


def sweep(number, catalog="foundation", layer_id="alpha", status="completed", requirement=REQ, platform=PLAT):
    return {"sweep_id": f"sw-{number}", "date": f"2026-09-{number:02d}", "status": status,
            "record_ref": f"evidence/sw-{number}/RESULT.json", "manifest_ref": f"catalogs/m{number}.json",
            "returns_ref": f"evidence/sw-{number}/returns.json", "layers": [
                {"catalog": catalog, "layer_id": layer_id, "requirement_sha256": requirement,
                 "platform_profiles_sha256": platform, "discovery_ref": f"evidence/sw-{number}/returns.json#/discovery",
                 "proposed": [f"https://github.com/o/s{number}", f"https://github.com/o/r{number}"],
                 "survived": [outcome(f"s{number}", number * 2, "not_refuted")],
                 "refuted": [outcome(f"r{number}", number * 2 + 1)]}]}


class DiscoveryHistoryTests(unittest.TestCase):
    def setUp(self):
        self.catalogs = {
            "foundation": {"layers": [{"layer_id": "alpha", "title": "Alpha", "requirement": "Frozen task."}]},
            "us-equities": {"layers": [{"layer_id": "beta", "title": "Beta", "requirement": "Frozen task."}]},
        }
        self.scope = {"requirement_sha256": {"foundation/alpha": REQ, "us-equities/beta": REQ},
                      "platform_profiles_sha256": PLAT}
        self.freshness = {"id": "fresh", "checked_at": "2026-10-06", "foundation": [], "trading": []}

    def build(self, ledger, baseline=None, **kwargs):
        return build_inputs.build_layer_inputs(self.catalogs, {}, self.scope, self.freshness, baseline, ledger,
                                               **kwargs)[0]

    def test_layer_history_survives_its_absence_from_latest_global_sweep(self):
        first, latest = sweep(1), sweep(2, catalog="us-equities", layer_id="beta")
        ledger = {"sweeps": [first, latest]}
        alpha = self.build(ledger)
        # Compatibility carrier and default-baseline selector keep their global-last-sweep semantics.
        self.assertEqual(alpha["previous_sweep"], {})
        self.assertIs(build_inputs.last_completed(ledger, build_inputs.REPOSITORY), latest)
        self.assertEqual(alpha["known_repositories"], ["o/r1", "o/s1"])
        self.assertEqual([row["sweep_id"] for row in alpha["discovery_history"]["sweeps"]], ["sw-1"])
        self.assertEqual(alpha["discovery_history"]["policy_K"], 3)

    def test_policy_window_is_per_layer_and_preserves_original_order_and_refs(self):
        # Ledger order is authoritative even when dates differ from that order.
        sweeps = [sweep(i) for i in (2, 1, 3, 5, 4)]
        ledger = {"policy": {"K": 2}, "sweeps": sweeps}
        history = self.build(ledger)["discovery_history"]["sweeps"]
        self.assertEqual([row["sweep_id"] for row in history], ["sw-5", "sw-4"])
        self.assertEqual(history[0]["date"], "2026-09-05")
        self.assertEqual(history[0]["sweep_ref"], "catalogs/saturation/ledger.json#/sweeps/3")
        self.assertEqual(history[0]["ledger_ref"], "catalogs/saturation/ledger.json#/sweeps/3/layers/0")
        self.assertEqual(history[0]["survived"][0]["ledger_ref"],
                         "catalogs/saturation/ledger.json#/sweeps/3/layers/0/survived/0")
        self.assertEqual(history[0]["refuted"][0]["fit"], sweeps[3]["layers"][0]["refuted"][0]["fit"])
        for field in ("record_ref", "manifest_ref", "returns_ref"):
            self.assertEqual(history[0][field], sweeps[3][field])
        self.assertEqual(history[0]["discovery_ref"], sweeps[3]["layers"][0]["discovery_ref"])
        self.assertEqual(self.build(ledger)["known_repositories"], ["o/r4", "o/r5", "o/s4", "o/s5"])
        # An older fixture without policy.K uses the native default, rather than a single-sweep memory.
        self.assertEqual([row["sweep_id"] for row in self.build({"sweeps": sweeps})["discovery_history"]["sweeps"]],
                         ["sw-3", "sw-5", "sw-4"])
        self.assertEqual(build_inputs.history_policy_k({"policy": {"min_gap_days": 7}}), 3)

    def test_invalid_present_policy_k_is_rejected_instead_of_slicing_arbitrarily(self):
        for value in (True, False, 0, -1, 1.0, "3", None, [], {}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, r"policy\.K"):
                self.build({"policy": {"K": value}, "sweeps": [sweep(1)]})
        with self.assertRaisesRegex(ValueError, "policy must be an object"):
            self.build({"policy": None, "sweeps": []})
        self.assertEqual(build_inputs.history_policy_k({"policy": {"K": 1}}), 1)

    def test_stopped_skills_mixed_and_unrelated_layers_do_not_consume_window(self):
        mixed = sweep(5)
        mixed["layers"].append(sweep(5, catalog="skills", layer_id="skills-discovery")["layers"][0])
        sweeps = [sweep(1), sweep(2, status="stopped"), sweep(3, catalog="skills", layer_id="skills-discovery"),
                  sweep(4, layer_id="another-layer"), mixed, sweep(6),
                  sweep(7, catalog="us-equities", layer_id="beta")]
        alpha = self.build({"policy": {"K": 2}, "sweeps": sweeps})
        self.assertEqual([row["sweep_id"] for row in alpha["discovery_history"]["sweeps"]], ["sw-1", "sw-6"])
        self.assertEqual(alpha["known_repositories"], ["o/r1", "o/r6", "o/s1", "o/s6"])
        self.assertEqual(alpha["discovery_history"]["sweeps"][1]["ledger_ref"],
                         "catalogs/saturation/ledger.json#/sweeps/5/layers/0")

    def test_native_missing_vote_outcome_is_not_merit_or_known(self):
        retained = {"votes": [
            {"facts": {"refuted": False},
             "fit": {"refuted": True, "claude": {"refuted": False}, "gpt6": {"missing": True}}},
            {"facts": {"refuted": False}, "fit": {"refuted": True, "claude": {"refuted": True}}},
        ]}
        target_of = ledger_rules.ref_resolver(lambda path: retained)
        absent = lambda entry: ledger_rules.refuted_by_absence(entry, target_of)
        prior = sweep(1)
        layer = prior["layers"][0]
        layer["survived"] = []
        layer["refuted"] = [outcome("missing", 0), outcome("returned", 1), outcome("unreadable", 99)]
        layer["proposed"] += ["https://github.com/o/discovery-only"]
        alpha = self.build({"sweeps": [prior]}, absent=absent)
        old = alpha["discovery_history"]["sweeps"][0]
        self.assertEqual([entry["repo"] for entry in old["not_adjudicated"]], ["https://github.com/o/missing"])
        self.assertEqual([entry["repo"] for entry in old["refuted"]],
                         ["https://github.com/o/returned", "https://github.com/o/unreadable"])
        self.assertTrue(old["not_adjudicated"][0]["refuted_by_absence"])
        self.assertEqual(alpha["known_repositories"], ["o/returned", "o/unreadable"])
        # The native resolver's false result for the unresolved pointer is not promoted into a merit verdict.
        self.assertFalse(old["refuted"][1]["refuted_by_absence"])
        self.assertEqual(old["refuted"][1]["reference_verification"], "unknown")
        self.assertNotIn("merit_refuted", old["refuted"][1])
        self.assertEqual(alpha["previous_sweep"]["not_adjudicated"], ["https://github.com/o/missing"])
        baseline = {"foundation": [{"layer": "alpha", "candidates": [
            {"repository": "https://github.com/o/missing"}]}]}
        self.assertIn("o/missing", self.build({"sweeps": [prior]}, baseline=baseline, absent=absent)["known_repositories"])

    def test_absence_callback_failure_remains_unknown_and_keeps_recovery_ref(self):
        def unavailable(entry):
            raise FileNotFoundError("private path must not be copied")

        alpha = self.build({"sweeps": [sweep(1)]}, absent=unavailable)
        entry = alpha["discovery_history"]["sweeps"][0]["refuted"][0]
        self.assertIsNone(entry["refuted_by_absence"])
        self.assertEqual(entry["absence_check_error"], "FileNotFoundError")
        self.assertEqual(entry["reference_verification"], "unknown")
        self.assertEqual(entry["fit"]["ref"], "evidence/returns.json#/votes/3/fit")
        self.assertEqual(alpha["previous_sweep"]["refuted"], ["https://github.com/o/r1"])
        self.assertNotIn("private path", str(entry))

    def test_scope_drift_is_retained_context_and_never_a_current_exclusion(self):
        ledger = {"sweeps": [sweep(1, requirement="c" * 64), sweep(2, platform="d" * 64), sweep(3)]}
        alpha = self.build(ledger)
        history = alpha["discovery_history"]["sweeps"]
        self.assertEqual([row["matches_current_scope"] for row in history], [False, False, True])
        self.assertEqual(history[0]["requirement_sha256"], "c" * 64)
        self.assertEqual(history[1]["platform_profiles_sha256"], "d" * 64)
        self.assertEqual((alpha["requirement_sha256"], alpha["platform_profiles_sha256"]), (REQ, PLAT))
        self.assertNotIn("excluded_repositories", alpha)
        self.assertIn("context only", alpha["discovery_history"]["note"])
        unknown = sweep(4)
        del unknown["layers"][0]["requirement_sha256"]
        row = self.build({"sweeps": [unknown]})["discovery_history"]["sweeps"][0]
        self.assertIsNone(row["matches_current_scope"])
        self.assertIsNone(row["requirement_sha256"])

    def test_exact_dispositions_and_conflicts_keep_manifest_and_pointer_provenance(self):
        candidate = {"repository": "https://github.com/o/c", "proposed_label": "keep_but_compare",
                     "review_status": "source_review", "decision": None, "extra": {"refs": ["evidence/c.json"]}}
        reconciliation = {"catalog": "foundation", "layer_id": "alpha", "repository": "https://github.com/o/c",
                          "kind": "later_owner_note", "note": "EXCLUDED is only a recorded observation here",
                          "details": {"overturn_when": ["new primary source"]}}
        baseline = {"id": "baseline", "checked_at": "2026-10-05", "foundation": [
            {"layer": "alpha", "candidates": [candidate, {"repository": "https://github.com/o/no-status"}]}],
            "reconciliations": [reconciliation]}
        fresh_observation = {"layer": "alpha", "repository": "https://github.com/o/c", "kind": "owner_note",
                             "note": "A conflicting observation, not a computed winner"}
        self.freshness["reconciliations"] = [fresh_observation,
            {"catalog": "us-equities", "layer_id": "alpha", "note": "wrong catalog"},
            {"catalog": "foundation", "layer_id": "other", "note": "wrong layer"},
            {"note": "no layer"}, {"layer": ["alpha"], "note": "non-scalar scope"},
            {"layer_id": "alpha", "layer": "beta", "note": "conflicting scope"}]
        self.freshness["trading"] = [{"layer": "beta", "entries": [
            {"repository": "https://github.com/o/trading", "decision": "recorded_default"}]}]
        original_baseline, original_freshness = copy.deepcopy(baseline), copy.deepcopy(self.freshness)
        alpha = self.build({"sweeps": []}, baseline=baseline)
        observations = alpha["current_dispositions"]
        self.assertEqual([row["observation"] for row in observations], [candidate, reconciliation, fresh_observation])
        self.assertEqual([row["ref"] for row in observations], [
            "baseline_manifest#/foundation/0/candidates/0", "baseline_manifest#/reconciliations/0",
            "freshness_manifest#/reconciliations/0"])
        self.assertEqual(observations[0]["source_document_id"], "baseline")
        self.assertEqual(observations[0]["source_checked_at"], "2026-10-05")
        self.assertEqual(observations[0]["source_document_sha256"], observations[1]["source_document_sha256"])
        self.assertNotEqual(observations[1]["source_document_sha256"], observations[2]["source_document_sha256"])
        self.assertIn("not raw file bytes", alpha["current_dispositions_note"])
        self.assertNotIn("excluded_repositories", alpha)
        observations[0]["observation"]["extra"]["refs"].append("changed-output-only")
        self.assertEqual(baseline, original_baseline)
        self.assertEqual(self.freshness, original_freshness)
        projected = build_inputs.current_dispositions_by_layer(baseline, self.freshness,
                                                                {"alpha": "foundation", "beta": "us-equities"})
        self.assertEqual(set(projected), {("foundation", "alpha"), ("us-equities", "beta")})
        self.assertEqual(projected[("us-equities", "beta")][0]["ref"],
                         "freshness_manifest#/trading/0/entries/0")

    def test_history_window_and_dispositions_do_not_leak_into_v2_field_hash_or_blind_fit(self):
        history = [sweep(1), sweep(2)]
        ledger = {"policy": {"K": 1}, "sweeps": history}
        baseline = {"foundation": [{"layer": "alpha", "candidates": [
            {"repository": "https://github.com/o/c", "disposition": "owner_observation"}]}],
            "reconciliations": [{"catalog": "foundation", "layer_id": "alpha", "note": "PRIVATE SELECTION NOTE"}]}
        options = {"contract_version": 2,
                   "platform_requirements": [{"id": "host", "os": "linux", "architecture": "x86_64"}]}
        before = self.build(ledger, baseline=baseline, **options)
        ledger["policy"]["K"] = 3
        baseline["reconciliations"][0]["note"] = "CHANGED PRIVATE SELECTION NOTE"
        after = self.build(ledger, baseline=baseline, **options)
        self.assertNotEqual(before["discovery_history"], after["discovery_history"])
        self.assertNotEqual(before["current_dispositions"], after["current_dispositions"])
        for field in ("eligible_field", "field_sha256", "known_repositories", "fit_projection"):
            self.assertEqual(before[field], after[field], field)
        self.assertEqual(before["known_repositories"], ["o/c", "o/r1", "o/r2", "o/s1", "o/s2"])
        self.assertTrue(all(row["disposition"] == "admit_pending" for row in before["eligible_field"]))
        self.assertNotIn("PRIVATE SELECTION NOTE", str(before["fit_projection"]))
        self.assertNotIn("discovery_history", before["fit_projection"])
        self.assertNotIn("current_dispositions", before["fit_projection"])


if __name__ == "__main__":
    unittest.main()
