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
        for phrase in ("B = 100,000", "Block length is 10 sessions for every item", "0.20 - 1e-9",
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

    def test_amendment_format_is_the_protocols_and_versioned(self):
        """Review round 15, amendment-format item: data-pins.json left the line format to the freeze PR and the
        parsers implied one that did not match the base files. The protocol now holds the versioned schema
        (run_discipline.amendment_format) and the code validates exactly that object."""
        from core import amendments
        self.assertEqual(PROTOCOL["run_discipline"]["amendment_format"], amendments.FORMAT)
        self.assertEqual(amendments.FORMAT["schema_version"], 1)
        bad = json.loads(json.dumps(PROTOCOL))
        bad["run_discipline"]["amendment_format"]["schema_version"] = 2
        with self.assertRaises(guards.Refused):
            guards.check_parameters(bad)
        pins = json.loads((Path(__file__).resolve().parents[2] / "data-pins.json").read_text())
        self.assertIn("run_discipline.amendment_format", pins["amendment_rule"])
        self.assertNotIn("left to the freeze pull request", pins["amendment_rule"])

    def test_freeze_acceptance_lists_every_precondition_without_claiming_completion(self):
        """Review round 15, F15: one status per freeze precondition, only 'open' or 'done in draft' in the draft, each
        'done' naming its evidence; the protocol stays a draft that is not frozen before outcomes."""
        fa = PROTOCOL["study_code_status"]["freeze_acceptance"]
        self.assertEqual([e["index"] for e in fa["entries"]], list(range(len(PROTOCOL["freeze_preconditions"]))))
        self.assertTrue(all(e["status"] in ("open", "done in draft") for e in fa["entries"]))
        self.assertTrue(all(e["evidence"] for e in fa["entries"] if e["status"] != "open"))
        self.assertIn("never by the presence of code", fa["rule"])
        self.assertIs(PROTOCOL["frozen_before_outcomes"], False)
        self.assertNotEqual(PROTOCOL["status"], "frozen")

    def test_the_readme_states_the_governing_coverage_and_deviation_rules(self):
        """Review round 15, N08: the overview names the minute-bar threshold and does not describe results from a
        deviated tree, which the guards refuse."""
        text = " ".join((Path(__file__).resolve().parents[2] / "README.md").read_text().split())
        self.assertIn("90% minute-bar coverage", text)
        self.assertNotIn("reported beside the governing ones", text)
        self.assertIn("A code change after the freeze cannot run", text)

    def test_amendment_lines_follow_the_format(self):
        from core import amendments
        from tests import synth
        self.assertEqual(amendments.fee_line_problems(synth.fee_line("sec_section31", "2027-01-04", None,
                                                                     usd_per_million=21.0)), [])
        self.assertEqual(amendments.calendar_line_problems(synth.calendar_line("2027-01-04")), [])
        good = synth.fee_line("finra_taf_covered_equity", "2027-01-04", "2027-12-31", usd_per_share=0.0002,
                              max_usd_per_trade=10.0)
        for broken in ({**good, "rate": 1.0}, {k: v for k, v in good.items() if k != "reason"},
                       {**good, "to": "2026-12-31"}, {**good, "usd_per_share": -1.0},
                       {**good, "source": {**good["source"], "url": "https://example.com/x"}},
                       {**good, "schema_version": 2}, {**good, "kind": "finra_taf"}):
            self.assertTrue(amendments.fee_line_problems(broken), broken)


if __name__ == "__main__":
    unittest.main()
