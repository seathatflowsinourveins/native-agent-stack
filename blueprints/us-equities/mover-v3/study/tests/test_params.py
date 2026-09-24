"""Review round 8, R8-2: the parameters the code uses equal the protocol JSON."""
import json
import unittest
from pathlib import Path

from core import coverage_rule, guards
from core.params import COVERAGE_RULE_SHA256, PARAMETERS
from fetch import transport

PROTOCOL = json.loads((Path(__file__).resolve().parents[2] / "protocol-core-draft.json").read_text())


class Parameters(unittest.TestCase):
    def test_parameters_object_equals_protocol(self):
        self.assertEqual(PROTOCOL["run_discipline"]["study_code"]["parameters"], PARAMETERS)
        guards.check_parameters(PROTOCOL)

    def test_structured_protocol_fields_agree(self):
        self.assertEqual(PROTOCOL["multiple_testing"]["item_ids"], PARAMETERS["item_ids"])
        ms = PROTOCOL["minimum_sample"]
        self.assertEqual(ms["tradable_cell"], PARAMETERS["minimum_sample"]["tradable_cell"])
        self.assertEqual(ms["difference_test_per_group"], PARAMETERS["minimum_sample"]["difference_test_per_group"])
        mde = PROTOCOL["minimum_detectable_effect"]
        self.assertEqual(mde["z_sum_one_sided"], PARAMETERS["mde"]["z_sum_one_sided"])
        self.assertEqual(mde["z_sum_two_sided"], PARAMETERS["mde"]["z_sum_two_sided"])
        self.assertEqual(mde["design_effect_DEFF"], PARAMETERS["mde"]["design_effect_DEFF"])
        for item, v in PARAMETERS["mde"]["sigma_by_item"].items():
            self.assertEqual(mde["sigma_by_item"][item], v)
        for stage in ("warmup", "development", "validation"):
            key = stage
            self.assertEqual(PROTOCOL["chronology"][key], PARAMETERS["chronology"][stage])
        self.assertEqual(PROTOCOL["cost_model"]["base_table"]["sha256"], PARAMETERS["cost_table"]["sha256"])
        self.assertEqual(PROTOCOL["cost_model"]["base_table"]["path"], PARAMETERS["cost_table"]["path"])

    def test_prose_parameters_are_named_in_the_protocol(self):
        text = json.dumps(PROTOCOL)
        for phrase in ("B = 100,000", "Block length is 5 sessions for H3-a and 10 sessions", "0.20 - 1e-9",
                       "$1,000,000", "timeout of 300 s", "at most 1000 ms", "min($20,000; 1% of med20; 10%",
                       "filled notional under $1,000", "1.25 x max(hs'(cell), h_fill)", "c = 1.0",
                       "2e-3 x raw_c(e)", "252 kept sessions", "fewer than 60 prior D events",
                       "first 6 sessions of validation", "40th session after", "63-session blocks, at most 2",
                       "If it exceeds 1%", "waiting 1 s, 4 s and 16 s", "% 20 == 0", "% 25 == 0", "12:17 ET and 14:43 ET",
                       "capped at the first 100", "capped at 50", "0.05 / (1012 + 60 + 5)"):
            self.assertTrue(phrase in text, phrase)

    def test_transport_retry_waits(self):
        self.assertEqual(list(transport.RETRY_WAITS_S), PARAMETERS["fetch"]["retry_waits_s"])
        self.assertEqual(len(transport.RETRY_WAITS_S), PARAMETERS["fetch"]["retries"])

    def test_coverage_rule_hash_is_recorded(self):
        self.assertEqual(coverage_rule.rule_sha256(PROTOCOL), COVERAGE_RULE_SHA256)
        th = coverage_rule.checked_thresholds(PROTOCOL)
        self.assertEqual(th["official_close_rate_min"], 0.90)

    def test_parameter_mismatch_is_refused(self):
        bad = json.loads(json.dumps(PROTOCOL))
        bad["run_discipline"]["study_code"]["parameters"]["bootstrap"]["B"] = 1000
        with self.assertRaises(guards.Refused):
            guards.check_parameters(bad)


if __name__ == "__main__":
    unittest.main()
