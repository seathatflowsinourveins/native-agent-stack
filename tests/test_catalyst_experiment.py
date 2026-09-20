"""Negative checks for the bounded synthetic catalyst contract."""
import importlib.util
from pathlib import Path
import copy
import json
import sys
import unittest

BASE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/catalyst-experiment"
spec = importlib.util.spec_from_file_location("catalyst_contract", BASE / "contract.py")
c = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = c
spec.loader.exec_module(c)
P = json.loads((BASE / "protocol.json").read_text())

def row():
    return {
        "security_id": "SYNTH-A", "source_hash": "a" * 64,
        "feature_end_ns": 100, "feature_available_ns": 110,
        "universe_available_ns": 90, "catalyst_available_ns": 80,
        "is_listed": True, "is_common_share": True, "identity_proven": True,
        "catalyst_original_8k_item101": True,
        "catalyst_age_sessions": 0, "full_session_minutes": 390,
        "complete_prior_sessions": 20, "basis_ids": ["S0", "S0", "S0"],
        "prior_close": "10", "median_dollar_volume": "5000000",
        "price_return": "0.05", "relative_volume": "3",
        "quote_age_ms": 100, "spread_bps": "30",
    }

class CatalystContractTests(unittest.TestCase):
    def test_daily_and_intraday_threshold_boundaries(self):
        self.assertEqual(c.candidate(row(), 120, "daily", P), [])
        self.assertEqual(c.candidate(row(), 120, "intraday", P), [])
        r = row(); r["price_return"] = "0.0499"
        self.assertIn("price_threshold", c.candidate(r, 120, "intraday", P))

    def test_late_revision_or_universe_is_not_backdated(self):
        for field in ["feature_available_ns", "universe_available_ns", "catalyst_available_ns"]:
            r = row(); r[field] = 121
            self.assertIn("unavailable_at_decision", c.candidate(r, 120, "daily", P))

    def test_bar_start_cannot_replace_completion(self):
        r = row(); r["feature_end_ns"] = 121; r["feature_available_ns"] = 122
        self.assertIn("incomplete_feature", c.candidate(r, 120, "daily", P))
        r["feature_available_ns"] = 110
        with self.assertRaises(ValueError): c.candidate(r, 120, "daily", P)

    def test_nanosecond_precision_and_invalid_clock_types(self):
        a = c.utc_ns("2026-09-21T13:35:00.000000001Z")
        self.assertEqual(a-c.utc_ns("2026-09-21T13:35:00Z"), 1)
        for value in ["2026-09-21T13:35:00", "2026-09-21T13:35:00.0000000001Z"]:
            with self.assertRaises(ValueError): c.utc_ns(value)
        for value in [True, 120.0, -1]:
            with self.assertRaises(ValueError): c.candidate(row(), value, "daily", P)

    def test_units_amendment_halfday_and_missing_window_fail(self):
        changes = [("basis_ids", ["S0","S1","S0"], "split_basis_mismatch"),
                   ("catalyst_original_8k_item101",False,"unknown_or_ineligible_catalyst"),
                   ("full_session_minutes",210,"non_full_session"),
                   ("complete_prior_sessions",19,"incomplete_lookback")]
        for key,value,reason in changes:
            r=row();r[key]=value
            self.assertIn(reason,c.candidate(r,120,"daily",P))

    def test_unknown_or_truthy_string_metadata_fails_closed(self):
        for field in ["identity_proven","is_listed","is_common_share"]:
            r=row();r[field]="true"
            self.assertIn("unknown_or_ineligible_universe",c.candidate(r,120,"daily",P))
        r=row();r["source_hash"]="broken"
        with self.assertRaises(ValueError):c.candidate(r,120,"daily",P)

    def test_outcomes_cannot_enter_candidate_input(self):
        r=row();r["future_high"]="500"
        with self.assertRaises(ValueError):c.candidate(r,120,"intraday",P)

    def test_age_quote_and_liquidity_boundaries(self):
        r=row();r["catalyst_age_sessions"]=4
        self.assertIn("event_age",c.candidate(r,120,"intraday",P))
        r=row();r["quote_age_ms"]=1001;r["spread_bps"]="101"
        self.assertIn("quote_gate",c.candidate(r,120,"intraday",P))
        self.assertEqual(c.candidate(r,120,"daily",P),[])  # No16:15 RTH quote requirement.
        r=row();r["median_dollar_volume"]="4999999"
        self.assertIn("liquidity_threshold",c.candidate(r,120,"daily",P))

    def test_named_200pct_labels_are_distinct(self):
        result=c.labels("10","12","36","15","45","13","14",basis_consistent=True)
        self.assertEqual(result["open_to_high_1d"],"2")
        self.assertEqual(result["prior_close_to_high_1d"],"2.6")
        self.assertEqual(result["close_to_close_1d"],"0.5")
        self.assertEqual(result["close_to_close_5d"],"2")
        self.assertFalse(result["gte_200pct"]["entry_to_exit"])
        with self.assertRaises(ValueError):c.labels("10","12","36","15","45","13","14",basis_consistent=False)
        with self.assertRaises(ValueError):c.labels("0","12","36","15","45","13","14",basis_consistent=True)

    def test_latency_and_entry_timing(self):
        self.assertEqual(c.entry_gate(100,100+60*10**9,60),True)
        self.assertFalse(c.entry_gate(100,100+60*10**9-1,60))
        self.assertFalse(c.entry_gate(100,100,60))

    def test_200pct_boundary_is_exact_beyond_display_precision(self):
        for high, expected in [("2.99999999999999999999999999999999999999", False),
                               ("3", True),
                               ("3.00000000000000000000000000000000000001", True)]:
            result = c.labels("1", "1", high, "1", "1", "1", "1", basis_consistent=True)
            self.assertIs(result["gte_200pct"]["open_to_high_1d"], expected)
            self.assertIs(result["gte_200pct"]["prior_close_to_high_1d"], expected)

    def test_interval_purge_and_shared_event_group(self):
        training=[{"decision_ns":10,"label_end_ns":90,"event_group":"A"}]
        c.assert_purged(training,100,{"B"})
        for end in [100,101]:
            r=copy.deepcopy(training);r[0]["label_end_ns"]=end
            with self.assertRaises(ValueError):c.assert_purged(r,100,{"B"})
        with self.assertRaises(ValueError):c.assert_purged(training,100,{"A"})

    def test_reserved_access_requires_exact_uninspected_registry(self):
        c.reserved_access(["A"],{"A":{"inspected":False,"registry_hash":"a"*64}})
        for registry in [{},{"A":{"inspected":True,"registry_hash":"a"*64}},{"A":{"inspected":False,"registry_hash":""}}]:
            with self.assertRaises(ValueError):c.reserved_access(["A"],registry)

if __name__ == "__main__":
    unittest.main()
