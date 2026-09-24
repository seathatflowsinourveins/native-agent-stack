"""holdout_gate: validated items, the access-log sequence (authorization then completion), count and read
retries, the evaluator refusals and the holdout-read classification."""
import unittest

from core import gate

FROZEN = "f" * 40


def auth(aid, purpose, decision="granted", retry_of=None, tree=FROZEN):
    return {"utc": "2027-01-01T00:00:00Z", "record_kind": "authorization", "authorization_id": aid,
            "actor_role": "committed automation", "protocol_id": "p", "protocol_sha256": "a" * 64, "code_revision": "c",
            "study_code_tree": tree, "runtime_lock_sha256": "r", "data_file_sha256s": {}, "validation_results_sha256": "v",
            "requested_items": ["H3-a"], "purpose": purpose, "decision": decision, "refusal": None, "retry_of": retry_of}


def done(aid, status="complete", results="x" * 64):
    return gate.completion(aid, "2027-01-02T00:00:00Z", status, "s" * 64 if status != "failed" else None, 10,
                           results if status == "complete" else None, [])


def ctx(**over):
    c = {"purpose": "read", "protocol_status": "frozen", "protocol_sha256": "a" * 64, "frozen_protocol_sha256": "a" * 64,
         "validation_present": True, "validation_sha256": "v", "validation_committed_sha256": "v",
         "validation_reachable_before_n0": True, "validation_run_tree": FROZEN, "validation_run_protocol_sha256": "a" * 64,
         "frozen_tree": FROZEN, "running_tree": FROZEN, "fetch_only_deviation_passed": False, "runtime_ok": True,
         "data_files_ok": True, "amendment_refusals": [], "validated_items": ["H3-a", "H3-c"], "requested_items": ["H3-a"],
         "access_log": [], "accrual_logs_complete": True, "count_due": True, "same_snapshot": True,
         "before_deadline": True, "retry_of": None, "study_code_tree": FROZEN, "validation_complete": True,
         "validation_void": False, "holdout_void": False}
    c.update(over)
    return c


class Gate(unittest.TestCase):
    def test_gate_opens_for_every_validated_item_without_a_cap(self):
        v = {"labels": {"H1-D": "underpowered", "H1-D-b_lane-low": "screened", "H3-a": "screened", "H3-b": "screened",
                        "H3-c": "not_supported_mde_excluded"}}
        self.assertEqual(gate.validated_items(v), ["H1-D-b_lane-low", "H3-a", "H3-b"])
        v["labels"]["H3-b"] = "underpowered"  # a tradable cell that failed a robustness statistic is not screened
        self.assertNotIn("H3-b", gate.validated_items(v))

    def test_validation_file_must_hold_every_item_p_value(self):
        # review round 10, F5: multiple_testing.procedure; the evaluator refuses an incomplete file
        from core.params import ITEM_IDS
        full = {"labels": {i: "underpowered" for i in ITEM_IDS}, "items": {i: {"p_stage": 1.0} for i in ITEM_IDS}}
        self.assertTrue(gate.validation_complete(full))
        for bad in ({**full, "items": {i: {"p_stage": 1.0} for i in ITEM_IDS[:4]}},
                    {**full, "items": {**full["items"], "H3-a": {"p_stage": None}}},
                    {**full, "items": {**full["items"], "H3-a": {"p_stage": True}}},
                    {**full, "items": {**full["items"], "H3-a": {"p_stage": 1.5}}},
                    {**full, "items": {**full["items"], "H9": {"p_stage": 0.1}}},
                    {"labels": full["labels"]}, None):
            self.assertFalse(gate.validation_complete(bad), bad)

    def test_read_classification(self):
        for k in ("collection", "batch_sha256", "paper_decision", "paper_order", "dashboard_metadata", "membership_only"):
            self.assertEqual(gate.classify_activity(k), "not a read")
        self.assertEqual(gate.classify_activity("net_return"), "read")
        with self.assertRaises(ValueError):
            gate.classify_activity("something else")


class AccessLog(unittest.TestCase):
    def test_complete_failed_and_partial_reads(self):
        for status in ("complete", "failed", "partial"):
            seq = gate.sequence([auth("a1", "read"), done("a1", status)])
            self.assertEqual(seq["problems"], [])
            self.assertIsNone(seq["open"])

    def test_granted_authorization_without_completion_blocks_the_next(self):
        seq = gate.sequence([auth("a1", "collect"), auth("a2", "read")])
        self.assertTrue(seq["problems"])
        refs = gate.evaluator_refusals(ctx(access_log=[auth("a1", "collect")]))
        self.assertTrue(any("no committed completion" in r for r in refs))

    def test_refused_authorization_needs_no_completion(self):
        seq = gate.sequence([auth("a1", "read", decision="refused"), auth("a2", "read")])
        self.assertEqual(seq["problems"], [])

    def test_completion_of_unknown_or_twice(self):
        self.assertTrue(gate.sequence([done("zz")])["problems"])
        self.assertTrue(gate.sequence([auth("a1", "read"), done("a1"), done("a1")])["problems"])

    def test_read_is_final_once_it_wrote_results(self):
        log = [auth("a1", "read"), done("a1", "complete")]
        refs = gate.evaluator_refusals(ctx(access_log=log, retry_of="a1"))
        self.assertTrue(any("previous granted 'read'" in r for r in refs))

    def test_failed_read_may_be_retried_from_the_same_tree_and_snapshot(self):
        log = [auth("a1", "read"), done("a1", "failed")]
        self.assertEqual(gate.evaluator_refusals(ctx(access_log=log, retry_of="a1")), [])
        self.assertTrue(gate.evaluator_refusals(ctx(access_log=log, retry_of=None)))
        self.assertTrue(gate.evaluator_refusals(ctx(access_log=log, retry_of="a1", same_snapshot=False)))
        self.assertTrue(gate.evaluator_refusals(ctx(access_log=log, retry_of="a1", before_deadline=False)))
        self.assertTrue(gate.evaluator_refusals(ctx(access_log=log, retry_of="a1", study_code_tree="e" * 40)))
        partial = [auth("a1", "read"), done("a1", "partial")]
        self.assertTrue(gate.evaluator_refusals(ctx(access_log=partial, retry_of="a1")))

    def test_count_schedule_and_count_retry(self):
        self.assertEqual(gate.evaluator_refusals(ctx(purpose="count")), [])
        self.assertTrue(gate.evaluator_refusals(ctx(purpose="count", count_due=False)))
        log = [auth("c1", "count"), done("c1", "failed")]
        # review round 8, R8-6: a failed count may be retried before the next scheduled action
        self.assertEqual(gate.evaluator_refusals(ctx(purpose="count", count_due=False, access_log=log, retry_of="c1")), [])
        self.assertTrue(gate.evaluator_refusals(ctx(purpose="count", count_due=False, access_log=log, retry_of="c1",
                                                    before_deadline=False)))
        ok = [auth("c1", "count"), done("c1", "complete")]
        self.assertTrue(gate.evaluator_refusals(ctx(purpose="count", count_due=False, access_log=ok, retry_of="c1")))
        self.assertTrue(gate.evaluator_refusals(ctx(purpose="count", count_outputs=["H3-a", "H3-a:mean"])))

    def test_authorization_record_is_granted_or_refused_by_rule(self):
        rec = gate.authorization(ctx(), "a9", "2027-01-01T00:00:00Z", {"protocol_id": "p"})
        self.assertEqual((rec["decision"], rec["refusal"]), ("granted", None))
        rec = gate.authorization(ctx(running_tree="e" * 40), "a9", "2027-01-01T00:00:00Z", {})
        self.assertEqual(rec["decision"], "refused")
        self.assertIn("study tree", rec["refusal"])


class Refusals(unittest.TestCase):
    def test_each_refusal(self):
        cases = {
            "protocol_status": ("draft", "not frozen"),
            "protocol_sha256": ("b" * 64, "not frozen"),
            "validation_present": (False, "validation results file is missing"),
            "validation_reachable_before_n0": (False, "before 09:30 ET on N0"),
            "validation_run_tree": ("e" * 40, "governing validation run"),
            "validation_run_protocol_sha256": ("b" * 64, "governing validation run"),
            "running_tree": ("e" * 40, "study tree"),
            "runtime_ok": (False, "runtime.lock"),
            "data_files_ok": (False, "data file"),
            "amendment_refusals": (["calendar amendment 0: not on origin/main"], "amendment"),
            "validated_items": ([], "validated items"),
            "requested_items": (["H1-D"], "validated items"),
            "accrual_logs_complete": (False, "accrual log"),
            # review round 10, F5 and F4
            "validation_complete": (False, "all 5 validation p-values"),
            "validation_void": (True, "validation is void"),
            "holdout_void": (True, "the holdout is void"),
        }
        self.assertEqual(gate.evaluator_refusals(ctx()), [])
        for key, (value, text) in cases.items():
            refs = gate.evaluator_refusals(ctx(**{key: value}))
            self.assertTrue(any(text in r for r in refs), (key, refs))

    def test_passing_transport_deviation_tree_is_accepted(self):
        self.assertEqual(gate.evaluator_refusals(ctx(running_tree="e" * 40, fetch_only_deviation_passed=True)), [])

    def test_collection_needs_only_a_frozen_protocol_and_a_closed_log(self):
        self.assertEqual(gate.evaluator_refusals(ctx(purpose="collect", validation_present=False)), [])
        self.assertTrue(gate.evaluator_refusals(ctx(purpose="collect", access_log=[auth("a1", "read")])))




class RunNeedsItsAuthorization(unittest.TestCase):
    def test_missing_refused_or_completed_authorization(self):
        with self.assertRaises(gate.NoAuthorization):
            gate.require_granted([], "a1", "read")
        with self.assertRaises(gate.NoAuthorization):
            gate.require_granted([auth("a1", "read", decision="refused")], "a1", "read")
        with self.assertRaises(gate.NoAuthorization):
            gate.require_granted([auth("a1", "count")], "a1", "read")
        with self.assertRaises(gate.NoAuthorization):
            gate.require_granted([auth("a1", "read"), done("a1")], "a1", "read")
        self.assertEqual(gate.require_granted([auth("a1", "read")], "a1", "read")["authorization_id"], "a1")


if __name__ == "__main__":
    unittest.main()
