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

# blueprints/us-equities/adaptive-paper/metrics.py shares the bare name "metrics": in a full
# `python3 -m unittest` run whichever was imported first would win sys.modules["metrics"]. Load
# this blueprint's copy under its own name so neither suite can see the other's module.
_METRICS_SPEC = importlib.util.spec_from_file_location("sim_engine_crosscheck_metrics", BLUEPRINT / "metrics.py")
metrics = importlib.util.module_from_spec(_METRICS_SPEC)
_METRICS_SPEC.loader.exec_module(metrics)
import oracle  # noqa: E402  (unique names repo-wide; OrderIntent must stay one class)
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
        for key in ("evidence_class", "repair_round", "superseded_first_attempt", "fix", "sample",
                    "order_stream", "engines", "config_matrix", "metrics_table", "oracle_agreement",
                    "better_than_touch_violations", "determinism_check", "release_timing_finding",
                    "overturn_evaluation", "unverified"):
            self.assertIn(key, receipt)
        self.assertEqual(receipt["evidence_class"], "sim_engine_crosscheck")

    def test_receipt_metrics_table_has_all_eight_configs(self):
        receipt = json.loads((BLUEPRINT / "receipts" / "20260925-crosscheck.json").read_text(encoding="utf-8"))
        table = receipt["metrics_table"]
        self.assertEqual(len(table), 8)
        for label, row in table.items():
            self.assertIn("fill_rate_pct", row, label)
            self.assertGreaterEqual(row["fill_rate_pct"], 0.0)
            self.assertLessEqual(row["fill_rate_pct"], 100.0)

    def test_superseded_receipt_is_preserved_and_matches_its_declared_hash(self):
        # The first (wrong) attempt is kept on record, not deleted -- and its
        # content must still match the hash the corrected receipt cites for
        # it in superseded_first_attempt.receipt_sha256.
        superseded_path = BLUEPRINT / "receipts" / "20260925-crosscheck-superseded.json"
        self.assertTrue(superseded_path.is_file(), superseded_path)
        receipt = json.loads((BLUEPRINT / "receipts" / "20260925-crosscheck.json").read_text(encoding="utf-8"))
        import hashlib

        actual = hashlib.sha256(superseded_path.read_bytes()).hexdigest()
        self.assertEqual(actual, receipt["superseded_first_attempt"]["receipt_sha256"])

    def test_overturn_condition_is_not_triggered_on_the_corrected_data(self):
        receipt = json.loads((BLUEPRINT / "receipts" / "20260925-crosscheck.json").read_text(encoding="utf-8"))
        ev = receipt["overturn_evaluation"]
        self.assertFalse(ev["fill_rate_divergence_gt_20pct"])
        self.assertFalse(ev["median_time_to_fill_divergence_gt_2x"])
        for pct in ev["fill_rate_relative_divergence_hftbacktest_vs_nautilus_primary"].values():
            self.assertLess(abs(pct), 20.0)
        for ratio in ev["median_time_to_fill_ratio_nautilus_primary_over_hftbacktest"].values():
            self.assertLess(ratio, 2.0)

    def test_oracle_agreement_at_least_99pct_for_every_engine_and_symbol(self):
        receipt = json.loads((BLUEPRINT / "receipts" / "20260925-crosscheck.json").read_text(encoding="utf-8"))
        table = receipt["oracle_agreement"]
        checked = 0
        for label, entry in table.items():
            if not isinstance(entry, dict) or "overall_pct" not in entry:
                continue  # skip the "method"/"interpretation" narrative keys
            # hftbacktest's constant-latency, last-NBBO model is the oracle's own definition: its measured
            # 100% is pinned so a regenerated receipt cannot drift below it unnoticed (independent re-check).
            floor = 100.0 if label.startswith("hftbacktest") else 99.0
            self.assertGreaterEqual(entry["overall_pct"], floor, label)
            for sym, pct in entry["by_symbol_pct"].items():
                self.assertGreaterEqual(pct, floor, f"{label}/{sym}")
                checked += 1
        self.assertGreater(checked, 0)

    def test_zero_better_than_touch_violations_for_every_run(self):
        receipt = json.loads((BLUEPRINT / "receipts" / "20260925-crosscheck.json").read_text(encoding="utf-8"))
        table = receipt["better_than_touch_violations"]
        checked = 0
        for label, count in table.items():
            if not isinstance(count, int):
                continue  # skip the "note" narrative key
            self.assertEqual(count, 0, label)
            checked += 1
        self.assertGreater(checked, 0)

    def test_determinism_check_recorded_as_matching(self):
        receipt = json.loads((BLUEPRINT / "receipts" / "20260925-crosscheck.json").read_text(encoding="utf-8"))
        self.assertTrue(receipt["determinism_check"]["match"])
        self.assertEqual(receipt["determinism_check"]["hash_1"], receipt["determinism_check"]["hash_2"])


class OracleTests(unittest.TestCase):
    """Hermetic, synthetic: oracle.py has no engine or network dependency."""

    def _intent(self, order_id=1, ts_ns=0, symbol="AAA", side="BUY", qty=5, limit_price="10.03"):
        return order_stream.OrderIntent(order_id=order_id, ts_ns=ts_ns, symbol=symbol, side=side, qty=qty,
                                         limit_price=limit_price, touch_price="10.02", mid_price="10.01")

    def test_predicts_fillable_when_crossing_and_size_sufficient(self):
        quotes = {"AAA": [_quote_row(0, "10.00", "10.02", bid_size=100, ask_size=100)]}
        intent = self._intent(side="BUY", qty=5, limit_price="10.03")
        result = oracle.predict(quotes, intent, latency_ms=10)
        self.assertTrue(result["fillable"])
        self.assertIsNone(result["reason"])

    def test_predicts_not_fillable_when_not_crossing(self):
        quotes = {"AAA": [_quote_row(0, "10.00", "10.02", bid_size=100, ask_size=100)]}
        intent = self._intent(side="BUY", qty=5, limit_price="10.01")  # below the ask -> does not cross
        result = oracle.predict(quotes, intent, latency_ms=10)
        self.assertFalse(result["fillable"])
        self.assertEqual(result["reason"], "not_crossing")

    def test_predicts_not_fillable_when_top_size_insufficient(self):
        quotes = {"AAA": [_quote_row(0, "10.00", "10.02", bid_size=100, ask_size=2)]}
        intent = self._intent(side="BUY", qty=5, limit_price="10.03")  # crosses, but only 2 shares shown
        result = oracle.predict(quotes, intent, latency_ms=10)
        self.assertFalse(result["fillable"])
        self.assertEqual(result["reason"], "insufficient_top_size")

    def test_predicts_not_fillable_before_any_quote_exists(self):
        quotes = {"AAA": [_quote_row(1_000_000_000, "10.00", "10.02")]}
        intent = self._intent(ts_ns=0, limit_price="10.03")  # arrival at 10ms, first quote is at 1s
        result = oracle.predict(quotes, intent, latency_ms=10)
        self.assertFalse(result["fillable"])
        self.assertEqual(result["reason"], "no_quote_at_or_before_arrival")

    def test_uses_the_last_quote_at_or_before_arrival_not_submit_time(self):
        # ask moves from 10.02 to 10.10 shortly after submit but before arrival (submit+latency).
        quotes = {"AAA": [_quote_row(0, "10.00", "10.02", ask_size=100),
                           _quote_row(5_000_000, "10.00", "10.10", ask_size=100)]}
        intent = self._intent(limit_price="10.03")  # only crosses the FIRST quote's ask, not the second
        result = oracle.predict(quotes, intent, latency_ms=10)  # arrival at 10ms, after the second quote
        self.assertFalse(result["fillable"])
        self.assertEqual(result["touch"], "10.10")

    def test_sell_side_uses_the_bid(self):
        quotes = {"AAA": [_quote_row(0, "10.00", "10.02", bid_size=100)]}
        intent = self._intent(side="SELL", qty=5, limit_price="9.99")  # crosses the bid
        result = oracle.predict(quotes, intent, latency_ms=10)
        self.assertTrue(result["fillable"])
        self.assertEqual(result["touch"], "10.00")

    def test_confusion_counts_are_correct(self):
        predictions = [{"fillable": True}, {"fillable": True}, {"fillable": False}, {"fillable": False}]
        outcomes = [{"exec_qty": 5}, {"exec_qty": 0}, {"exec_qty": 5}, {"exec_qty": 0}]
        result = oracle.confusion(predictions, outcomes)
        self.assertEqual(result, {"n": 4, "true_positive": 1, "false_positive": 1, "false_negative": 1,
                                   "true_negative": 1, "agreement": 0.5})

    def test_confusion_rejects_mismatched_lengths(self):
        with self.assertRaises(ValueError):
            oracle.confusion([{"fillable": True}], [])

    def test_confusion_by_symbol_splits_correctly(self):
        predictions = [{"fillable": True}, {"fillable": True}]
        outcomes = [{"symbol": "AAA", "exec_qty": 5}, {"symbol": "BBB", "exec_qty": 0}]
        result = oracle.confusion_by_symbol(predictions, outcomes)
        self.assertEqual(result["AAA"]["agreement"], 1.0)
        self.assertEqual(result["BBB"]["agreement"], 0.0)

    def test_predict_stream_preserves_order_and_length(self):
        quotes = {"AAA": [_quote_row(t * 1_000_000, "10.00", "10.02", ask_size=100) for t in range(20)]}
        stream = order_stream.generate_order_stream(quotes, submits_per_sec=5.0)
        predictions = oracle.predict_stream(quotes, stream, latency_ms=5)
        self.assertEqual(len(predictions), len(stream))
        self.assertEqual([p["order_id"] for p in predictions], [intent.order_id for intent in stream])


class BetterThanTouchViolationTests(unittest.TestCase):
    """Hermetic, synthetic: metrics.better_than_touch_violations has no
    engine or network dependency. Added in the 2026-09-25 repair round --
    the first attempt never ran this check against hftbacktest's own
    output at all; it would have caught the use-after-free directly."""

    def test_flags_a_buy_fill_strictly_better_than_the_ask(self):
        quotes = {"AAA": [_quote_row(0, "10.00", "10.02")]}
        outcomes = [_outcome(side="BUY", exec_qty=5, avg_exec_price="10.01", resolved_ts_ns=0)]
        violations = metrics.better_than_touch_violations(outcomes, quotes)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["avg_exec_price"], "10.01")

    def test_flags_a_sell_fill_strictly_better_than_the_bid(self):
        quotes = {"AAA": [_quote_row(0, "10.00", "10.02")]}
        outcomes = [_outcome(side="SELL", exec_qty=5, avg_exec_price="10.01", resolved_ts_ns=0)]
        violations = metrics.better_than_touch_violations(outcomes, quotes)
        self.assertEqual(len(violations), 1)

    def test_does_not_flag_a_fill_exactly_at_the_touch(self):
        quotes = {"AAA": [_quote_row(0, "10.00", "10.02")]}
        outcomes = [_outcome(side="BUY", exec_qty=5, avg_exec_price="10.02", resolved_ts_ns=0)]
        self.assertEqual(metrics.better_than_touch_violations(outcomes, quotes), [])

    def test_does_not_flag_a_fill_through_but_not_beating_the_touch(self):
        # A marketable IOC crossing the collar (worse than touch) is expected and fine.
        quotes = {"AAA": [_quote_row(0, "10.00", "10.02")]}
        outcomes = [_outcome(side="BUY", exec_qty=5, avg_exec_price="10.03", resolved_ts_ns=0)]
        self.assertEqual(metrics.better_than_touch_violations(outcomes, quotes), [])

    def test_empty_when_nothing_filled(self):
        quotes = {"AAA": [_quote_row(0, "10.00", "10.02")]}
        outcomes = [_outcome(exec_qty=0, status="NO_FILL", avg_exec_price=None, resolved_ts_ns=None)]
        self.assertEqual(metrics.better_than_touch_violations(outcomes, quotes), [])


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

    def test_exact_latency_resolves_every_fill_at_exactly_submit_plus_latency(self):
        import run_nautilus

        quotes = {"AAA": [_quote_row(t * 100_000_000, "10.00", "10.02", 1000, 1000) for t in range(50)]}
        stream = order_stream.generate_order_stream(quotes, submits_per_sec=2.0)
        latency_ms = 10
        outcomes = run_nautilus.run_stream(quotes, stream[:5], latency_ms=latency_ms, exact_latency=True)
        filled = [o for o in outcomes if o["exec_qty"] > 0]
        self.assertGreater(len(filled), 0)
        for o in filled:
            delta_ms = (o["resolved_ts_ns"] - o["submit_ts_ns"]) / 1e6 - latency_ms
            self.assertAlmostEqual(delta_ms, 0.0, places=6)


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

    @staticmethod
    def _outcomes_hash(outcomes):
        import hashlib

        return hashlib.sha256(json.dumps(outcomes, sort_keys=True, default=str).encode()).hexdigest()

    @staticmethod
    def _two_symbol_quotes():
        # Both symbols use the SAME tick spacing/count, so they span the
        # exact same time range -- an "AAA alone" run's feed (built only
        # from AAA's own rows) then comfortably covers every AAA order's
        # submit time, including ones generated near the tail of the full
        # combined stream (round-robin ticks keep using a symbol's LAST
        # known quote past its own data if the other symbol's range were
        # longer, which would otherwise submit an "alone" run's order past
        # its own feed's padded end).
        return {"AAA": [_quote_row(t * 50_000_000, "10.00", "10.02", 1000, 1000) for t in range(200)],
                "BBB": [_quote_row(t * 50_000_000, "20.00", "20.05", 1000, 1000) for t in range(200)]}

    def test_two_symbol_run_matches_each_symbols_own_single_symbol_run(self):
        """Regression test for the 2026-09-25 repair round's use-after-free
        fix (see run_hftbacktest.py's module docstring): a per-symbol numpy
        feed array must not lose its only Python reference while a LATER
        symbol's array is built in the same call, or hftbacktest reads
        freed memory for the earlier symbol for the rest of the run.

        Verified failing against the pre-fix driver (commit d5cc0c58,
        `git show d5cc0c58:.../run_hftbacktest.py`, run unmodified): the
        first symbol's outcomes extracted from a two-symbol run did NOT
        match its own standalone single-symbol run (differing outcome
        hashes) -- see receipts/20260925-crosscheck.json's
        superseded_first_attempt.independently_reproduced_this_round block
        for the exact hashes. This test passes against the fixed driver."""
        import run_hftbacktest

        # AAA built first (asset 0, the one the old driver's loop-reassigned
        # `data` variable would free); BBB built second (asset 1).
        quotes = self._two_symbol_quotes()
        stream = order_stream.generate_order_stream(quotes, submits_per_sec=5.0)
        self.assertGreater(len([o for o in stream if o.symbol == "AAA"]), 5)

        two_symbol = run_hftbacktest.run_stream(quotes, stream, latency_ms=10, exchange="partial_fill")
        two_symbol_aaa = [o for o in two_symbol if o["symbol"] == "AAA"]

        aaa_stream = [intent for intent in stream if intent.symbol == "AAA"]
        aaa_quotes = {"AAA": quotes["AAA"]}
        aaa_alone = run_hftbacktest.run_stream(aaa_quotes, aaa_stream, latency_ms=10, exchange="partial_fill")

        self.assertEqual(self._outcomes_hash(aaa_alone), self._outcomes_hash(two_symbol_aaa))

    def test_determinism_rerun_is_hash_identical(self):
        """Same regression coverage as the isolation test above, from the
        non-determinism angle: verified failing against the pre-fix driver
        (two identical calls gave DIFFERENT outcome hashes and different
        filled-order counts, commit d5cc0c58 -- see the same receipt block).
        Passes against the fixed driver."""
        import run_hftbacktest

        quotes = self._two_symbol_quotes()
        stream = order_stream.generate_order_stream(quotes, submits_per_sec=5.0)
        first = run_hftbacktest.run_stream(quotes, stream, latency_ms=10, exchange="partial_fill")
        second = run_hftbacktest.run_stream(quotes, stream, latency_ms=10, exchange="partial_fill")
        self.assertEqual(self._outcomes_hash(first), self._outcomes_hash(second))

    def test_exchange_models_agree_once_the_use_after_free_is_fixed(self):
        import run_hftbacktest

        quotes = self._two_symbol_quotes()
        stream = order_stream.generate_order_stream(quotes, submits_per_sec=5.0)
        partial = run_hftbacktest.run_stream(quotes, stream, latency_ms=10, exchange="partial_fill")
        no_partial = run_hftbacktest.run_stream(quotes, stream, latency_ms=10, exchange="no_partial_fill")
        self.assertEqual(self._outcomes_hash(partial), self._outcomes_hash(no_partial))


if __name__ == "__main__":
    unittest.main()
