"""Offline tests for the sim-vs-paper fill comparison logic (trading-lane audit
gap #7). No network, no credential file and no NautilusTrader runtime is used;
`run_replay` and the CLI's `main` are exercised only by the (separately gated)
native integration, not here. Fills are synthetic fixtures."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/sim-paper-compare/replay_compare.py"
SPEC = importlib.util.spec_from_file_location("sim_paper_compare", SOURCE)
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


TRIAL = ROOT / "blueprints/us-equities/adaptive-paper/trials/20260923g-main-passed"


class TimestampTests(unittest.TestCase):
    def test_round_trip(self):
        self.assertEqual(C.ns_to_iso(C.ts_ns("2026-09-23T16:47:36.955177Z")), "2026-09-23T16:47:36.955177000Z")
        self.assertEqual(C.ns_to_iso(C.ts_ns("2026-09-23T16:47:43Z")), "2026-09-23T16:47:43.000000000Z")
        self.assertEqual(C.ts_ns("1970-01-01T00:00:00.000000001Z"), 1)

    def test_ordering(self):
        self.assertLess(C.ts_ns("2026-09-23T16:47:36.000000Z"), C.ts_ns("2026-09-23T16:47:36.000001Z"))

    def test_rejects_malformed(self):
        for bad in ("2026-09-23 16:47:36Z", "not-a-timestamp", "2026-09-23T16:47:36"):
            with self.assertRaises(ValueError):
                C.ts_ns(bad)


class LoadPaperOrdersTests(unittest.TestCase):
    def setUp(self):
        self.broker_orders = json.loads((TRIAL / "broker-orders.json").read_text())

    def test_loads_the_five_recorded_orders_sorted_by_submission(self):
        orders = C.load_paper_orders(self.broker_orders)
        self.assertEqual(len(orders), 5)
        self.assertEqual([o["client_order_id"] for o in orders],
                         sorted([o["client_order_id"] for o in orders],
                                key=lambda cid: next(o["submitted_at_ns"] for o in orders if o["client_order_id"] == cid)))
        statuses = {o["client_order_id"]: o["status"] for o in orders}
        self.assertEqual(sum(1 for s in statuses.values() if s == "filled"), 4)
        self.assertEqual(sum(1 for s in statuses.values() if s == "canceled"), 1)

    def test_symbols_sides_and_qty(self):
        orders = C.load_paper_orders(self.broker_orders)
        by_id = {o["client_order_id"]: o for o in orders}
        first = by_id["adp-adaptive-20260923g-0000001"]
        self.assertEqual((first["symbol"], first["side"], first["qty"], first["limit_price"]), ("INTC", "BUY", 1, "120.6"))

    def test_rejects_unsupported_order_type(self):
        bad = json.loads(json.dumps(self.broker_orders))
        bad["orders"][0]["type"] = "market"
        with self.assertRaisesRegex(ValueError, "unsupported_order_type"):
            C.load_paper_orders(bad)


class BuildDecisionsTests(unittest.TestCase):
    def test_cancel_inserted_before_the_replacement_submit(self):
        orders = C.load_paper_orders(json.loads((TRIAL / "broker-orders.json").read_text()))
        decisions = C.build_decisions(orders)
        # Five submits plus one synthetic cancel for the canceled GOOGL sell.
        self.assertEqual(sum(1 for d in decisions if d["action"] == "submit"), 5)
        cancels = [d for d in decisions if d["action"] == "cancel"]
        self.assertEqual(len(cancels), 1)
        self.assertEqual(cancels[0]["order"]["client_order_id"], "adp-adaptive-20260923g-0000004")
        replacement = next(o for o in orders if o["client_order_id"] == "adp-adaptive-20260923g-0000005")
        self.assertLess(cancels[0]["ts_ns"], replacement["submitted_at_ns"])
        self.assertEqual(decisions, sorted(decisions, key=lambda d: (d["ts_ns"], 0 if d["action"] == "submit" else 1)))

    def test_no_cancel_decision_without_a_canceled_predecessor(self):
        orders = [{"symbol": "AAPL", "side": "BUY", "status": "filled", "submitted_at_ns": 1, "filled_at_ns": 2,
                   "client_order_id": "a", "qty": 1, "limit_price": "1", "time_in_force": "DAY", "filled_qty": 1,
                   "filled_avg_price": "1"}]
        self.assertEqual(C.build_decisions(orders), [{"ts_ns": 1, "action": "submit", "order": orders[0]}])


class FetchWindowTests(unittest.TestCase):
    def test_window_covers_all_submit_and_fill_timestamps_with_padding(self):
        orders = C.load_paper_orders(json.loads((TRIAL / "broker-orders.json").read_text()))
        start, end = C.fetch_window(orders, pad_seconds=10)
        earliest_submit = min(o["submitted_at_ns"] for o in orders)
        latest_event = max(o["filled_at_ns"] or o["submitted_at_ns"] for o in orders)
        self.assertEqual(start, earliest_submit - 10 * 10**9)
        self.assertEqual(end, latest_event + 10 * 10**9)


class NormalizeQuoteRowsTests(unittest.TestCase):
    def test_drops_one_sided_and_nonpositive_quotes_and_sorts(self):
        raw = {"INTC": [
            {"t": "2026-09-23T16:47:37.000000Z", "bp": 120.50, "ap": 120.60, "bs": 1, "as": 1},
            {"t": "2026-09-23T16:47:36.000000Z", "bp": 0, "ap": 120.60, "bs": 1, "as": 1},
            {"t": "2026-09-23T16:47:38.000000Z", "bp": 120.55, "ap": 0, "bs": 1, "as": 1},
            {"t": "2026-09-23T16:47:35.000000Z", "bp": 120.40, "ap": 120.45, "bs": 2, "as": 3},
        ]}
        out = C.normalize_quote_rows(raw)
        self.assertEqual(len(out["INTC"]), 2)
        self.assertEqual([q["ts_ns"] for q in out["INTC"]], sorted(q["ts_ns"] for q in out["INTC"]))
        self.assertEqual(out["INTC"][0]["bid"], "120.40")
        self.assertEqual(out["INTC"][0]["ask"], "120.45")


class BpsTests(unittest.TestCase):
    def test_bps_direction_and_none_propagation(self):
        self.assertAlmostEqual(C.bps("101", "100"), 100.0)
        self.assertAlmostEqual(C.bps("99", "100"), -100.0)
        self.assertIsNone(C.bps(None, "100"))
        self.assertIsNone(C.bps("100", None))
        self.assertIsNone(C.bps("100", 0))


class CompareOrdersTests(unittest.TestCase):
    def paper(self, **over):
        base = {"client_order_id": "x", "symbol": "INTC", "side": "BUY", "qty": 1, "limit_price": "120.60",
                "status": "filled", "filled_qty": 1, "filled_avg_price": "120.57",
                "submitted_at_ns": 0, "filled_at_ns": 10**9}
        base.update(over)
        return base

    def test_both_filled_agreement_with_price_and_time_deltas(self):
        paper = [self.paper()]
        sim = {"x": {"filled": True, "avg_px": "120.58", "ts_last": 2 * 10**9}}
        out = C.compare_orders(paper, sim)
        row = out["rows"][0]
        self.assertTrue(row["fill_agreement"])
        self.assertAlmostEqual(row["fill_price_delta_bps"], (120.58 / 120.57 - 1) * 1e4, places=4)
        self.assertAlmostEqual(row["fill_time_delta_s"], 1.0)
        self.assertEqual(out["aggregates"]["fill_agreement_rate"], 1.0)
        self.assertEqual(out["aggregates"]["both_filled"], 1)

    def test_paper_filled_sim_no_fill_is_a_disagreement(self):
        paper = [self.paper()]
        sim = {"x": {"filled": False, "avg_px": None, "ts_last": None}}
        out = C.compare_orders(paper, sim)
        self.assertFalse(out["rows"][0]["fill_agreement"])
        self.assertIsNone(out["rows"][0]["fill_price_delta_bps"])
        self.assertEqual(out["aggregates"]["fill_agreement_rate"], 0.0)
        self.assertEqual(out["aggregates"]["both_filled"], 0)

    def test_paper_canceled_and_sim_no_fill_agree(self):
        paper = [self.paper(status="canceled", filled_qty=0, filled_avg_price=None, filled_at_ns=None)]
        sim = {"x": {"filled": False, "avg_px": None, "ts_last": None}}
        out = C.compare_orders(paper, sim)
        self.assertTrue(out["rows"][0]["fill_agreement"])
        self.assertEqual(out["aggregates"]["fill_agreement_rate"], 1.0)

    def test_missing_sim_order_counts_as_no_fill_not_a_crash(self):
        paper = [self.paper()]
        out = C.compare_orders(paper, {})
        self.assertFalse(out["rows"][0]["sim_present"])
        self.assertFalse(out["rows"][0]["fill_agreement"])

    def test_aggregates_over_mixed_synthetic_orders(self):
        paper = [self.paper(client_order_id="a"), self.paper(client_order_id="b", limit_price="120.62"),
                 self.paper(client_order_id="c", status="canceled", filled_qty=0, filled_avg_price=None, filled_at_ns=None)]
        sim = {"a": {"filled": True, "avg_px": "120.57", "ts_last": 10**9},   # exact agreement
               "b": {"filled": False, "avg_px": None, "ts_last": None},       # disagreement (paper filled)
               "c": {"filled": False, "avg_px": None, "ts_last": None}}       # agreement (both no-fill)
        out = C.compare_orders(paper, sim)
        agg = out["aggregates"]
        self.assertEqual(agg["orders"], 3)
        self.assertEqual(agg["fill_agreements"], 2)
        self.assertAlmostEqual(agg["fill_agreement_rate"], 2 / 3)
        self.assertEqual(agg["both_filled"], 1)
        self.assertAlmostEqual(agg["abs_fill_price_delta_bps_mean"], 0.0)


class RetainedTrialFixtureTests(unittest.TestCase):
    """The retained trial fixture used by the native integration must keep
    parsing under this module's contract; this is a local check on that fixture,
    not a claim of unchanged upstream acceptance."""

    def test_broker_orders_fixture_still_matches_documented_shape(self):
        broker_orders = json.loads((TRIAL / "broker-orders.json").read_text())
        orders = C.load_paper_orders(broker_orders)
        self.assertEqual(len(orders), 5)
        symbols = {o["symbol"] for o in orders}
        self.assertEqual(symbols, {"INTC", "GOOGL"})
        decisions = C.build_decisions(orders)
        self.assertEqual(len(decisions), 6)


if __name__ == "__main__":
    unittest.main()
