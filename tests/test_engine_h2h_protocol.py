"""Local unit tests for the Alpaca engine head-to-head protocol (no engine, no network).

Covers the frozen order script's structure and deterministic prices, the shared step
machine against a fake engine, the preregistered metrics and decision rule, and the
consistency of protocol.json and the offline receipt with the files they bind. These
are our integration checks, not upstream engine tests.
"""
from decimal import Decimal
import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
H2H = ROOT / "blueprints" / "us-equities" / "engine-h2h"
_spec = importlib.util.spec_from_file_location("h2h_common_under_test", H2H / "h2h_common.py")
common = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = common
_spec.loader.exec_module(common)

BRIEF_MATRIX = {"resting_limit", "marketable_limit", "market", "stop", "stop_limit", "trailing_stop", "bracket",
                "oto", "oco", "moo", "moc", "extended_hours_limit", "cancel", "replace", "partial_fill",
                "subpenny_rejection", "kill_mid_order", "stream_drop", "restart_with_open_orders"}


class OrderScript(unittest.TestCase):
    def setUp(self):
        self.script = common.load_script()

    def test_structure(self):
        cases = self.script["cases"]
        self.assertEqual(len([c for c in cases if c != "E01"]), 21)
        for phase in self.script["phases"].values():
            self.assertTrue(set(phase["cases"]) <= set(cases))
        self.assertEqual({c for c, v in cases.items() if v.get("paper_only")}, {"F01", "F02", "F03"})
        # Every phase that trades ends flat through E01, except the pre-open/regular/close
        # phases whose day ends in the reconcile phase.
        self.assertEqual(self.script["phases"]["reconcile"]["cases"], ["E01"])
        for window in ("extended_pre", "extended_post"):
            self.assertEqual(self.script["phases"][window]["cases"][-1], "E01")

    def test_rejects_malformed_scripts(self):
        broken = json.loads(json.dumps(self.script))
        broken["cases"]["R01"]["steps"][0]["order"]["type"] = "iceberg"
        with self.assertRaisesRegex(ValueError, "script:order_R01"):
            common.validate_script(broken)
        broken = json.loads(json.dumps(self.script))
        broken["cases"]["R02"]["steps"].append({"do": "kill"})
        with self.assertRaisesRegex(ValueError, "script:paper_only_step_R02"):
            common.validate_script(broken)
        broken = json.loads(json.dumps(self.script))
        broken["phases"]["regular"]["cases"].append("Z99")
        with self.assertRaisesRegex(ValueError, "script:phase_case_Z99"):
            common.validate_script(broken)

    def test_prices_are_deterministic_decimals(self):
        bid, ask = Decimal("500.01"), Decimal("500.03")
        expected = {"resting_buy": "475.00", "resting_buy_replace": "470.00", "ext_resting_buy": "485.00",
                    "marketable_buy": "502.54", "marketable_sell": "497.50", "far_buy_stop": "550.04",
                    "far_buy_stop_limit": "555.04", "take_profit": "550.04", "stop_loss": "450.00",
                    "subpenny_buy": "475.005"}
        for rule, value in expected.items():
            with self.subTest(rule=rule):
                self.assertEqual(common.price(rule, bid, ask, self.script), Decimal(value))
                self.assertEqual(common.price(rule, bid, ask, self.script), common.price(rule, bid, ask, self.script))
        with self.assertRaisesRegex(ValueError, "invalid_reference_quote"):
            common.price("resting_buy", Decimal(0), ask, self.script)

    def test_resolved_orders_use_constants(self):
        bid, ask = Decimal("100"), Decimal("100.02")
        steps = {(c, s): step for c, _, s, step in common.phase_steps(self.script, "regular", offline=True)}
        self.assertEqual(common.resolve_order(steps[("R10", 0)]["order"], bid, ask, self.script)["qty"], 10)
        self.assertEqual(common.resolve_order(steps[("R12", 0)]["order"], bid, ask, self.script)["qty"], 100000)
        self.assertEqual(common.resolve_order(steps[("R06", 0)]["order"], bid, ask, self.script)["trail_percent"],
                         Decimal("10"))
        bracket = common.resolve_order(steps[("R07", 0)]["order"], bid, ask, self.script)
        self.assertEqual((bracket["class"], bracket["take_profit"], bracket["stop_loss"]),
                         ("bracket", Decimal("110.03"), Decimal("90.00")))

    def test_offline_skips_paper_only_cases(self):
        offline = {c for c, *_ in common.phase_steps(self.script, "faults", offline=True)}
        paper = {c for c, *_ in common.phase_steps(self.script, "faults", offline=False)}
        self.assertEqual(offline, set())
        self.assertEqual(paper, {"F01", "F02", "F03"})
        repeats = [r for c, r, s, _ in common.phase_steps(self.script, "regular", offline=True) if c == "R10" and s == 0]
        self.assertEqual(repeats, [0, 1, 2, 3, 4])


class Evaluate(unittest.TestCase):
    def test_expectations(self):
        cases = [
            ("open", {"state": "open"}, (True, True, None, None)),
            ("open", {"state": "filled", "filled_qty": 1}, (False, True, None, "unintended_execution")),
            ("open", {"state": "submitted"}, (False, False, None, None)),
            ("filled", {"state": "refused"}, (False, True, None, None)),
            ("refused", {"state": "refused"}, (True, True, None, None)),
            ("refused", {"state": "open"}, (False, False, None, None)),
            ("canceled", {"state": "canceled"}, (True, True, None, None)),
            ("flat", {"state": "unknown", "position": 0, "open_orders": 0}, (True, False, None, None)),
        ]
        for expect, observed, result in cases:
            with self.subTest(expect=expect, observed=observed):
                self.assertEqual(common.evaluate(expect, observed), result)

    def test_subpenny_outcomes(self):
        requested = Decimal("475.005")
        self.assertEqual(common.evaluate("refused_or_rounded", {"state": "refused"}, requested_price=requested),
                         (True, True, None, None))
        self.assertEqual(common.evaluate("refused_or_rounded", {"state": "open", "accepted_price": "475.00"},
                                         requested_price=requested), (True, True, "rounded_in_engine_state", None))
        # Accepted at the sub-penny price itself: not satisfied (the step times out as failed).
        self.assertEqual(common.evaluate("refused_or_rounded", {"state": "open", "accepted_price": "475.005"},
                                         requested_price=requested), (False, False, None, None))

    def test_unknown_state_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "unknown_normalized_state"):
            common.evaluate("open", {"state": "working"})


class FakeOps:
    """A deterministic in-memory engine: limits below the ask rest, marketable ones fill,
    market orders are refused, and one order class is unsupported."""

    def __init__(self, script):
        self.script, self.clock = script, dt.datetime(2026, 9, 25, 10, tzinfo=dt.timezone.utc)
        self.orders, self.pos, self.cleanups, self.next_id = {}, Decimal(0), 0, 0

    def now(self):
        return self.clock

    def tick(self, seconds=1):
        self.clock += dt.timedelta(seconds=seconds)

    def quote(self):
        return Decimal("100.00"), Decimal("100.02")

    def position(self):
        return self.pos

    def open_orders(self):
        return sum(1 for o in self.orders.values() if o["state"] == "open")

    def submit(self, tag, order):
        if order["class"] != "simple":
            raise common.Unsupported("no_contingent_orders")
        self.next_id += 1
        state = "refused" if order["type"] == "market" else "open"
        row = {"state": state, "price": order.get("limit"), "qty": order["qty"], "side": order["side"], "filled": 0}
        if state == "open" and order["type"] == "limit" and (
                (order["side"] == "buy" and order["limit"] >= Decimal("100.02"))
                or (order["side"] == "sell" and order["limit"] <= Decimal("100.00"))):
            row.update(state="filled", filled=order["qty"])
            self.pos += order["qty"] if order["side"] == "buy" else -order["qty"]
        self.orders[self.next_id] = row
        return self.next_id

    def replace(self, handle, price):
        self.orders[handle]["price"] = price

    def cancel(self, handle):
        if self.orders[handle]["state"] == "open":
            self.orders[handle]["state"] = "canceled"

    def is_open(self, handle):
        return self.orders[handle]["state"] == "open"

    def flatten(self, session):
        for row in self.orders.values():
            if row["state"] == "open":
                row["state"] = "canceled"
        self.pos = Decimal(0)

    def cleanup(self, session):
        self.cleanups += 1
        self.flatten(session)

    def observe(self, handle):
        row = self.orders[handle]
        return {"state": row["state"], "filled_qty": row["filled"], "accepted_price": row["price"]}

    def fault_point(self, kind, tag):
        raise AssertionError("offline runs never reach fault steps")


class Journal:
    def __init__(self):
        self.rows = []

    def event(self, kind, **fields):
        self.rows.append({"kind": kind, **fields})


class StepMachineWithFakeEngine(unittest.TestCase):
    def run_phase(self, phase):
        script = common.load_script()
        ops, journal = FakeOps(script), Journal()
        machine = common.StepMachine(script, ops, journal, offline=True)
        machine.enqueue_phase(phase)
        for _ in range(20000):
            machine.advance()
            if machine.idle():
                break
            ops.tick()
        self.assertTrue(machine.idle())
        return machine.results, ops, journal

    def test_regular_phase_outcomes(self):
        results, ops, _ = self.run_phase("regular")
        status = {case: value["status"] for case, value in results.items()}
        self.assertEqual(status["R01"], common.PASSED)          # rest, replace to a live new price, cancel
        self.assertEqual(status["R02"], common.PASSED)
        self.assertEqual(status["R03"], common.REFUSED)         # market refused explicitly
        self.assertEqual(status["R07"], common.UNSUPPORTED)
        self.assertEqual(status["R11"], common.FAILED)          # accepted at a sub-penny price: timeout
        self.assertEqual(results["R11"]["detail"], "timeout:open")
        self.assertEqual(status["R12"], common.FAILED)          # a 100000-share fill is an unintended execution
        self.assertEqual(results["R12"]["detail"], "unintended_execution")
        self.assertEqual(ops.pos, 0)
        self.assertGreater(ops.cleanups, 0)

    def test_precondition_blocks_a_short_sale(self):
        script = common.load_script()
        ops, journal = FakeOps(script), Journal()
        machine = common.StepMachine(script, ops, journal, offline=True)
        machine.queue = [w for w in self._works(machine, script, "regular") if w.case == "R03"]
        machine.advance()
        self.assertEqual(machine.results["R03"], {"status": common.FAILED, "detail": "precondition_position:0"})
        self.assertEqual(ops.orders, {})

    @staticmethod
    def _works(machine, script, phase):
        machine.enqueue_phase(phase)
        works, machine.queue = machine.queue, []
        return works

    def test_paper_only_cases_are_recorded_offline(self):
        results, _, _ = self.run_phase("faults")
        self.assertEqual({c: v["status"] for c, v in results.items()},
                         {c: common.NOT_RUN_OFFLINE for c in ("F01", "F02", "F03")})

    def test_replace_must_take_effect(self):
        script = common.load_script()
        ops, journal = FakeOps(script), Journal()
        ops.replace = lambda handle, price: None   # an engine that silently ignores the replace
        machine = common.StepMachine(script, ops, journal, offline=True)
        machine.queue = [w for w in self._works(machine, script, "regular") if w.case == "R01"]
        for _ in range(200):
            machine.advance()
            if machine.idle():
                break
            ops.tick()
        self.assertEqual(machine.results["R01"]["status"], common.FAILED)
        self.assertTrue(machine.results["R01"]["detail"].startswith("timeout"))


class Metrics(unittest.TestCase):
    def test_percentile_nearest_rank(self):
        values = [5, 1, 4, 2, 3]
        self.assertEqual(common.percentile(values, 50), 3)
        self.assertEqual(common.percentile(values, 95), 5)
        self.assertEqual(common.percentile(list(range(1, 101)), 95), 95)
        self.assertIsNone(common.percentile([], 95))

    def test_reconcile_counts(self):
        broker = {"a": {"status": "filled", "filled_qty": "1", "intent": "R02"},
                  "b": {"status": "canceled", "filled_qty": "0", "intent": "R01"},
                  "c": {"status": "canceled", "filled_qty": "0", "intent": "R01"},
                  "d": {"status": "new", "filled_qty": "0", "intent": "F01"}}
        engine = {"a": {"status": "filled", "filled_qty": "1"}, "b": {"status": "canceled", "filled_qty": "0"},
                  "c": {"status": "new", "filled_qty": "0"}}
        self.assertEqual(common.reconcile(engine, broker, engine_position=0, broker_position=0),
                         {"reconciliation_mismatch": 1, "duplicate_order": 1, "orphan_order": 1})
        self.assertEqual(common.reconcile({}, {}, engine_position=1, broker_position=0)["reconciliation_mismatch"], 1)

    def test_finalize_offline_results(self):
        script = common.load_script()
        results = common.finalize_offline_results({"R10": {"status": common.PASSED}}, script, partial_fills_seen=False)
        self.assertEqual(results["R10"]["status"], common.NOT_OBSERVABLE)
        self.assertEqual(results["F02"]["status"], common.NOT_RUN_OFFLINE)
        kept = common.finalize_offline_results({"R10": {"status": common.PASSED}}, script, partial_fills_seen=True)
        self.assertEqual(kept["R10"]["status"], common.PASSED)


class DecisionRule(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads((H2H / "protocol.json").read_text())

    @staticmethod
    def summary(covered, ack, fill, failures=0, complete=True):
        return {"complete": complete, "covered": covered, "correctness_failures": {"duplicate_order": failures},
                "latency": {"submit_to_ack_ms_p95": ack, "fill_to_engine_ms_p95": fill}}

    def decide(self, **challengers):
        summaries = {"nautilus": self.summary(10, 100, 200), **challengers}
        return common.decide(summaries, self.protocol)

    def test_win_needs_all_three_conditions(self):
        self.assertEqual(self.decide(lean=self.summary(10, 125, 250))["verdict"], "challenger_wins:lean")
        loses = {"correctness_failures": self.summary(12, 90, 90, failures=1),
                 "coverage_below_incumbent": self.summary(9, 90, 90),
                 "submit_to_ack_ms_p95:over_ratio": self.summary(12, 126, 90),
                 "fill_to_engine_ms_p95:over_ratio": self.summary(12, 90, 251),
                 "fill_to_engine_ms_p95:missing": self.summary(12, 90, None),
                 "incomplete": self.summary(12, 90, 90, complete=False)}
        for reason, summary in loses.items():
            with self.subTest(reason=reason):
                decision = self.decide(lean=summary)
                self.assertEqual(decision["verdict"], "incumbent_retained")
                self.assertIn(reason, decision["challengers"]["lean"]["reasons"])

    def test_ordering_and_ties(self):
        self.assertEqual(self.decide(lean=self.summary(11, 120, 200), lumibot=self.summary(12, 124, 200))["verdict"],
                         "challenger_wins:lumibot")
        self.assertEqual(self.decide(lean=self.summary(12, 110, 200), lumibot=self.summary(12, 120, 200))["verdict"],
                         "challenger_wins:lean")
        self.assertEqual(self.decide(lean=self.summary(12, 110, 200), lumibot=self.summary(12, 110, 150))["verdict"],
                         "tie_requires_decision_record")

    def test_incomplete_incumbent_is_inconclusive(self):
        summaries = {"nautilus": self.summary(10, 100, 200, complete=False), "lean": self.summary(20, 1, 1)}
        self.assertEqual(common.decide(summaries, self.protocol)["verdict"], "inconclusive")


class ProtocolBindings(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads((H2H / "protocol.json").read_text())

    def test_matrix_covers_the_brief(self):
        matrix = self.protocol["order_script"]["matrix"]
        self.assertTrue(BRIEF_MATRIX <= set(matrix))
        cases = common.load_script()["cases"]
        for item, ids in matrix.items():
            with self.subTest(item=item):
                self.assertTrue(ids and set(ids) <= set(cases))

    def test_accounts_and_rule(self):
        accounts = self.protocol["accounts"]
        self.assertEqual(accounts["required"], 3)
        self.assertEqual(accounts["env_files"], {e: common.env_file_name(e) for e in common.ENGINES})
        self.assertEqual(self.protocol["decision_rule"]["max_p95_ratio"], "1.25")
        self.assertEqual(self.protocol["decision_rule"]["incumbent"], common.INCUMBENT)
        self.assertEqual(self.protocol["sessions"]["regular"]["count"], 5)
        self.assertEqual(len(self.protocol["sessions"]["extended"]["windows"]), 2)

    def test_frozen_files_match(self):
        frozen = self.protocol["preregistration"]["frozen_files"]
        self.assertIn("order_script.json", frozen)
        for relative, digest in frozen.items():
            with self.subTest(file=relative):
                self.assertEqual(common.file_sha256(H2H / relative), digest)

    def test_offline_receipt_binds_the_current_script(self):
        receipt = json.loads((H2H / "receipts" / "offline-20260925.json").read_text())
        self.assertEqual(receipt["script_sha256"], common.file_sha256(common.SCRIPT_PATH))
        for engine in common.ENGINES:
            with self.subTest(engine=engine):
                run = receipt["engines"][engine]
                self.assertEqual(run["script_sha256"], receipt["script_sha256"])
                statuses = {case: value["status"] for case, value in run["results"].items()}
                self.assertEqual(run["summary"]["covered"],
                                 sum(1 for c, s in statuses.items() if c != "E01" and s in common.COVERED))
                self.assertEqual(run["final_quantity"], "0")
                self.assertEqual(run["open_orders"], 0)


if __name__ == "__main__":
    unittest.main()
