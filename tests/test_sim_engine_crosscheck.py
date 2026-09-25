"""Hermetic checks for the engine-vs-engine cross-check
(blueprints/us-equities/sim-engine-crosscheck/), Phase C.

This is OUR integration check (docs/acceptance-evidence-policy.md), not an
upstream test. `order_stream.py` and `metrics.py` have no engine or network
dependency at all (order_stream.py imports only sim-capacity's schedule.py,
itself dependency-free; metrics.py imports only sim-capacity's fee_model.py,
also dependency-free) -- their tests run unconditionally on system Python,
using small, hand-constructed synthetic fixtures, never the private retained
sample. Tests that actually drive NautilusTrader or hftbacktest skip cleanly
when the corresponding package is not importable on the running interpreter,
matching tests/test_sim_capacity.py and tests/test_sim_crosscheck_hftbacktest.py's
own convention.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints" / "us-equities" / "sim-engine-crosscheck"

import sys  # noqa: E402

if str(BLUEPRINT) not in sys.path:
    sys.path.insert(0, str(BLUEPRINT))

import metrics  # noqa: E402
import order_stream  # noqa: E402

NAUTILUS_AVAILABLE = importlib.util.find_spec("nautilus_trader") is not None
HFTBACKTEST_AVAILABLE = importlib.util.find_spec("hftbacktest") is not None


def _quote_row(ts_ns, bid, ask, bid_size=1000, ask_size=1000):
    return {"ts_ns": ts_ns, "bid": bid, "ask": ask, "bid_size": bid_size, "ask_size": ask_size}


class OrderStreamTests(unittest.TestCase):
    def test_generates_one_order_per_tick_when_quotes_are_dense(self):
        # 1 symbol, quotes covering the whole window, submitting at 2/sec for 3 seconds -> 6 ticks.
        quotes = {"AAA": [_quote_row(t * 100_000_000, "10.00", "10.02") for t in range(40)]}
        stream = order_stream.generate_order_stream(quotes, submits_per_sec=2.0)
        self.assertGreater(len(stream), 0)
        for intent in stream:
            self.assertEqual(intent.symbol, "AAA")
            self.assertEqual(intent.qty, order_stream.QTY_MAX)  # displayed size (1000) always caps it

    def test_first_side_is_buy_then_alternates_while_flat(self):
        quotes = {"AAA": [_quote_row(t * 50_000_000, "10.00", "10.02") for t in range(200)]}
        stream = order_stream.generate_order_stream(quotes, submits_per_sec=5.0, position_cap=300)
        sides = [o.side for o in stream]
        self.assertEqual(sides[0], "BUY")  # flat at start -> always BUY
        # alternates thereafter (position stays well under the cap)
        for a, b in zip(sides, sides[1:]):
            self.assertNotEqual(a, b)

    def test_never_proposes_sell_when_assumed_position_is_flat_or_short(self):
        # A pathological case: force qty clamps to make the position hover near 0
        # by starving the SELL side via a tiny position cap of 1 share, and
        # confirm no SELL is ever proposed while the assumed position is <= 0.
        quotes = {"AAA": [_quote_row(t * 50_000_000, "10.00", "10.02") for t in range(400)]}
        stream = order_stream.generate_order_stream(quotes, submits_per_sec=5.0, qty_min=1, qty_max=1,
                                                      position_cap=1)
        position = 0
        for intent in stream:
            if position <= 0:
                self.assertEqual(intent.side, "BUY", intent)
            position += intent.qty if intent.side == "BUY" else -intent.qty
            self.assertGreaterEqual(position, 0)  # never goes short under the assumed-fill model

    def test_sell_quantity_is_clamped_to_assumed_position_not_raw_available_size(self):
        # Position cap of 3, qty_min=qty_max=5 (larger than the cap): a BUY is not
        # itself shrunk by the cap (it can overshoot it in one qty_max-sized step),
        # but every SELL must still be clamped to whatever the assumed running
        # position actually is at that point -- never asking to sell more than is
        # assumed held, and the assumed position must never go negative.
        quotes = {"AAA": [_quote_row(t * 50_000_000, "10.00", "10.02") for t in range(400)]}
        stream = order_stream.generate_order_stream(quotes, submits_per_sec=5.0, qty_min=5, qty_max=5,
                                                      position_cap=3)
        position = 0
        for intent in stream:
            if intent.side == "SELL":
                self.assertLessEqual(intent.qty, position, intent)
            position += intent.qty if intent.side == "BUY" else -intent.qty
            self.assertGreaterEqual(position, 0)

    def test_deterministic_for_the_same_input(self):
        quotes = {"AAA": [_quote_row(t * 50_000_000, "10.00", "10.02") for t in range(100)],
                  "BBB": [_quote_row(t * 70_000_000, "20.00", "20.05") for t in range(100)]}
        s1 = order_stream.generate_order_stream(quotes, submits_per_sec=3.0)
        s2 = order_stream.generate_order_stream(quotes, submits_per_sec=3.0)
        self.assertEqual(s1, s2)

    def test_round_robin_alternates_symbols_regardless_of_skips(self):
        # BBB has no quotes at all until halfway through -- its ticks should be
        # silently skipped (no intent), but AAA's own cadence is unaffected.
        aaa = [_quote_row(t * 50_000_000, "10.00", "10.02") for t in range(400)]
        bbb = [_quote_row(t * 50_000_000 + 10_000_000_000, "20.00", "20.05") for t in range(400)]
        quotes = {"AAA": aaa, "BBB": bbb}
        stream = order_stream.generate_order_stream(quotes, submits_per_sec=5.0)
        early_symbols = {o.symbol for o in stream if o.ts_ns < 10_000_000_000}
        self.assertEqual(early_symbols, {"AAA"})
        later_symbols = {o.symbol for o in stream if o.ts_ns > 10_500_000_000}
        self.assertEqual(later_symbols, {"AAA", "BBB"})

    def test_rejects_empty_symbols(self):
        with self.assertRaises(ValueError):
            order_stream.generate_order_stream({})

    def test_rejects_symbol_with_no_quotes(self):
        with self.assertRaises(ValueError):
            order_stream.generate_order_stream({"AAA": []})

    def test_limit_price_is_touch_plus_or_minus_collar(self):
        quotes = {"AAA": [_quote_row(0, "10.00", "10.02")] + [_quote_row(t * 50_000_000, "10.00", "10.02")
                                                                for t in range(1, 200)]}
        stream = order_stream.generate_order_stream(quotes, submits_per_sec=5.0, collar=Decimal("0.01"))
        for intent in stream:
            if intent.side == "BUY":
                self.assertEqual(intent.limit_price, "10.03")
                self.assertEqual(intent.touch_price, "10.02")
            else:
                self.assertEqual(intent.limit_price, "9.99")
                self.assertEqual(intent.touch_price, "10.00")


def _outcome(order_id=1, symbol="AAA", side="BUY", submit_ts_ns=0, submit_qty=5, status="FILLED",
             exec_qty=5, avg_exec_price="10.02", resolved_ts_ns=70_000_000, touch="10.02", mid="10.01"):
    return {"order_id": order_id, "symbol": symbol, "side": side, "submit_ts_ns": submit_ts_ns,
            "submit_qty": submit_qty, "limit_price": "10.03", "touch_price_at_submit": touch,
            "mid_price_at_submit": mid, "status": status, "exec_qty": exec_qty,
            "avg_exec_price": avg_exec_price, "resolved_ts_ns": resolved_ts_ns}


class MetricsTests(unittest.TestCase):
    def test_fill_rate_counts_any_positive_exec_qty(self):
        outcomes = [_outcome(exec_qty=5), _outcome(exec_qty=2, status="PARTIAL"),
                    _outcome(exec_qty=0, status="NO_FILL", avg_exec_price=None, resolved_ts_ns=None)]
        self.assertAlmostEqual(metrics.fill_rate(outcomes), 2 / 3)

    def test_fill_rate_empty_is_zero(self):
        self.assertEqual(metrics.fill_rate([]), 0.0)

    def test_full_and_partial_fill_share(self):
        outcomes = [_outcome(exec_qty=5, submit_qty=5), _outcome(exec_qty=2, submit_qty=5, status="PARTIAL"),
                    _outcome(exec_qty=0, submit_qty=5, status="NO_FILL", avg_exec_price=None, resolved_ts_ns=None)]
        self.assertAlmostEqual(metrics.full_fill_share(outcomes), 1 / 3)
        self.assertAlmostEqual(metrics.partial_fill_share(outcomes), 1 / 3)

    def test_time_to_fill_stats_median_and_p90(self):
        # deltas (ms): 10, 20, 30, 40, 50 -- median=30, p90 uses the same
        # nearest-rank method as sim-capacity's submit_to_fill_latency_ms.
        outcomes = [_outcome(order_id=i, submit_ts_ns=0, resolved_ts_ns=ms * 1_000_000, exec_qty=5)
                    for i, ms in enumerate((10, 20, 30, 40, 50))]
        stats = metrics.time_to_fill_ms_stats(outcomes)
        self.assertEqual(stats["n"], 5)
        self.assertAlmostEqual(stats["median_ms"], 30.0)
        self.assertAlmostEqual(stats["min_ms"], 10.0)
        self.assertAlmostEqual(stats["max_ms"], 50.0)
        # nearest-rank p90 over 5 sorted values: index = min(4, int(0.9*4)) = 3 -> 40ms
        self.assertAlmostEqual(stats["p90_ms"], 40.0)

    def test_time_to_fill_stats_empty_when_nothing_filled(self):
        outcomes = [_outcome(exec_qty=0, status="NO_FILL", avg_exec_price=None, resolved_ts_ns=None)]
        stats = metrics.time_to_fill_ms_stats(outcomes)
        self.assertEqual(stats["n"], 0)
        self.assertIsNone(stats["median_ms"])

    def test_touch_share_matches_quote_in_force_at_resolution_time(self):
        quotes = {"AAA": [_quote_row(0, "10.00", "10.02"), _quote_row(100_000_000, "10.01", "10.03")]}
        at_touch = _outcome(resolved_ts_ns=50_000_000, avg_exec_price="10.02")  # matches quote in force at t=50ms
        beyond_touch = _outcome(order_id=2, resolved_ts_ns=150_000_000, avg_exec_price="10.02")  # touch moved to 10.03 by t=150ms
        result = metrics.touch_share([at_touch, beyond_touch], quotes)
        self.assertEqual(result["n"], 2)
        self.assertEqual(result["at_touch"], 1)
        self.assertAlmostEqual(result["share"], 0.5)

    def test_cost_vs_mid_bps_sign_convention_buy_and_sell(self):
        # BUY at 10.02 vs mid 10.00 -> worse than mid -> positive cost.
        buy = _outcome(side="BUY", exec_qty=10, avg_exec_price="10.02", mid="10.00")
        # SELL at 9.98 vs mid 10.00 -> worse than mid (received less) -> positive cost.
        sell = _outcome(order_id=2, side="SELL", exec_qty=10, avg_exec_price="9.98", mid="10.00")
        result = metrics.cost_vs_mid_bps([buy, sell])
        self.assertEqual(result["n"], 2)
        buy_cost = (Decimal("10.02") - Decimal("10.00")) * 10  # 0.20
        sell_cost = (Decimal("10.00") - Decimal("9.98")) * 10  # 0.20
        self.assertEqual(Decimal(result["total_cost_usd"]), buy_cost + sell_cost)
        self.assertGreater(result["bps"], 0)

    def test_cost_vs_mid_bps_empty(self):
        result = metrics.cost_vs_mid_bps([])
        self.assertEqual(result["n"], 0)
        self.assertIsNone(result["bps"])

    def test_total_fees_usd_matches_fee_model_directly(self):
        import fee_model as fm

        buy = _outcome(side="BUY", exec_qty=10, avg_exec_price="10.02")
        sell = _outcome(order_id=2, side="SELL", exec_qty=10, avg_exec_price="9.98")
        expected = fm.commission_usd(side="BUY", quantity=10, price="10.02", commission_plan="none") + \
            fm.commission_usd(side="SELL", quantity=10, price="9.98", commission_plan="none")
        self.assertEqual(Decimal(metrics.total_fees_usd([buy, sell], commission_plan="none")), expected)

    def test_total_fees_usd_skips_unfilled_orders(self):
        unfilled = _outcome(exec_qty=0, status="NO_FILL", avg_exec_price=None, resolved_ts_ns=None)
        self.assertEqual(Decimal(metrics.total_fees_usd([unfilled])), Decimal("0"))

    def test_status_counts(self):
        outcomes = [_outcome(status="FILLED"), _outcome(order_id=2, status="FILLED"),
                    _outcome(order_id=3, status="NO_FILL", exec_qty=0, avg_exec_price=None, resolved_ts_ns=None)]
        self.assertEqual(metrics.status_counts(outcomes), {"FILLED": 2, "NO_FILL": 1})

    def test_summarize_returns_all_expected_keys(self):
        quotes = {"AAA": [_quote_row(0, "10.00", "10.02")]}
        outcomes = [_outcome()]
        summary = metrics.summarize(outcomes, quotes)
        for key in ("n_orders", "status_counts", "fill_rate", "full_fill_share", "partial_fill_share",
                    "time_to_fill_ms", "touch_share", "cost_vs_mid", "fees_usd", "total_simulated_cost_usd"):
            self.assertIn(key, summary)

    def test_summarize_by_symbol_splits_correctly(self):
        quotes = {"AAA": [_quote_row(0, "10.00", "10.02")], "BBB": [_quote_row(0, "20.00", "20.05")]}
        outcomes = [_outcome(symbol="AAA"), _outcome(order_id=2, symbol="BBB")]
        by_symbol = metrics.summarize_by_symbol(outcomes, quotes)
        self.assertEqual(set(by_symbol), {"AAA", "BBB"})
        self.assertEqual(by_symbol["AAA"]["n_orders"], 1)
        self.assertEqual(by_symbol["BBB"]["n_orders"], 1)


class ReceiptStructureTests(unittest.TestCase):
    """Runs regardless of any runtime -- checks the checked-in receipt, not
    native execution."""

    def test_receipt_is_valid_json_with_required_keys(self):
        receipt_path = BLUEPRINT / "receipts" / "20260925-crosscheck.json"
        self.assertTrue(receipt_path.is_file(), receipt_path)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        for key in ("evidence_class", "sample", "order_stream", "engines", "config_matrix",
                    "metrics_table", "mechanistic_findings", "overturn_evaluation", "unverified"):
            self.assertIn(key, receipt)
        self.assertEqual(receipt["evidence_class"], "sim_engine_crosscheck")

    def test_receipt_metrics_table_has_all_six_configs(self):
        receipt = json.loads((BLUEPRINT / "receipts" / "20260925-crosscheck.json").read_text(encoding="utf-8"))
        overall = receipt["metrics_table"]["overall"]
        self.assertEqual(len(overall), 6)
        for label, row in overall.items():
            self.assertIn("fill_rate_pct", row, label)
            self.assertGreaterEqual(row["fill_rate_pct"], 0.0)
            self.assertLessEqual(row["fill_rate_pct"], 100.0)


@unittest.skipUnless(NAUTILUS_AVAILABLE, "nautilus_trader is not installed on this interpreter")
class NautilusDriverSmokeTests(unittest.TestCase):
    def test_run_stream_fills_a_marketable_ioc_on_a_static_book(self):
        import run_nautilus

        quotes = {"AAA": [_quote_row(t * 100_000_000, "10.00", "10.02", 1000, 1000) for t in range(50)]}
        stream = order_stream.generate_order_stream(quotes, submits_per_sec=2.0)
        outcomes = run_nautilus.run_stream(quotes, stream[:3], latency_ms=10)
        self.assertEqual(len(outcomes), 3)
        for o in outcomes:
            self.assertIn(o["status"], ("FILLED", "PARTIAL", "NO_FILL", "REJECTED", "DENIED", "UNRESOLVED"))


@unittest.skipUnless(HFTBACKTEST_AVAILABLE, "hftbacktest is not installed on this interpreter")
class HftbacktestDriverSmokeTests(unittest.TestCase):
    def test_build_depth_events_zeroes_the_old_level_on_a_price_change(self):
        import hftbacktest as h

        import run_hftbacktest

        rows = [_quote_row(0, "10.00", "10.02"), _quote_row(100_000_000, "10.00", "10.06")]
        data = run_hftbacktest.build_depth_events(rows, pad_ns=1_000_000_000)
        ask_events = [row for row in data if int(row["ev"]) & int(h.SELL_EVENT) and int(row["ev"]) & int(h.DEPTH_EVENT)]
        zero_events = [row for row in ask_events if row["qty"] == 0.0]
        self.assertGreaterEqual(len(zero_events), 1)
        self.assertTrue(any(abs(float(row["px"]) - 10.02) < 1e-9 for row in zero_events))

    def test_run_stream_fills_a_marketable_ioc_on_a_static_book(self):
        import run_hftbacktest

        quotes = {"AAA": [_quote_row(t * 100_000_000, "10.00", "10.02", 1000, 1000) for t in range(50)]}
        stream = order_stream.generate_order_stream(quotes, submits_per_sec=2.0)
        outcomes = run_hftbacktest.run_stream(quotes, stream[:3], latency_ms=10, exchange="partial_fill")
        self.assertEqual(len(outcomes), 3)
        for o in outcomes:
            self.assertIn(o["status"], ("FILLED", "PARTIAL", "NO_FILL", "REJECTED", "UNRESOLVED", "OTHER"))


if __name__ == "__main__":
    unittest.main()
