"""Offline tests for the sim-vs-paper fill comparison logic. Most classes here use
no network, no credential file and no NautilusTrader runtime; `run_replay` and the
CLI's `main` are exercised only by the separately gated classes below (PinnedRuntimeTests,
MainReplayNoCredentialTests), which skip themselves when the active interpreter is
not the pinned nautilus_trader==2.0.0rc5 runtime. Fills are synthetic fixtures unless
noted."""
import gzip
import hashlib
import importlib.metadata
import importlib.util
import json
import re
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/sim-paper-compare/replay_compare.py"
README_PATH = ROOT / "blueprints/us-equities/sim-paper-compare/README.md"
SPEC = importlib.util.spec_from_file_location("sim_paper_compare", SOURCE)
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


TRIAL = ROOT / "blueprints/us-equities/adaptive-paper/trials/20260923g-main-passed"
RECEIPT_PATH = ROOT / "blueprints/us-equities/sim-paper-compare/receipts/20260923g-main-passed.json"


def _pinned_runtime_active() -> bool:
    try:
        return importlib.metadata.version("nautilus_trader") == "2.0.0rc5"
    except importlib.metadata.PackageNotFoundError:
        return False


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

    def test_epoch_seconds_to_ns_matches_the_recorded_cancel_example(self):
        # paper-output.json's requests[] cancel entry for this trial.
        self.assertEqual(C.epoch_seconds_to_ns(1790182276.7766664), 1790182276776666000)
        self.assertEqual(C.ns_to_iso(C.epoch_seconds_to_ns(1790182276.7766664)), "2026-09-23T16:51:16.776666000Z")


class LoadPaperOrdersTests(unittest.TestCase):
    def setUp(self):
        self.broker_orders = json.loads((TRIAL / "broker-orders.json").read_text())

    def test_loads_the_five_recorded_orders_sorted_by_submission(self):
        orders = C.load_paper_orders(self.broker_orders)
        self.assertEqual(len(orders), 5)
        submitted = [o["submitted_at_ns"] for o in orders]
        self.assertEqual(submitted, sorted(submitted))
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

    def test_rejects_non_day_time_in_force(self):
        bad = json.loads(json.dumps(self.broker_orders))
        bad["orders"][0]["time_in_force"] = "gtc"
        with self.assertRaisesRegex(ValueError, "unsupported_time_in_force:GTC"):
            C.load_paper_orders(bad)

    def test_rejects_fractional_qty_instead_of_truncating(self):
        bad = json.loads(json.dumps(self.broker_orders))
        bad["orders"][0]["qty"] = "1.5"
        with self.assertRaisesRegex(ValueError, "fractional_qty_not_supported"):
            C.load_paper_orders(bad)

    def test_rejects_fractional_filled_qty(self):
        bad = json.loads(json.dumps(self.broker_orders))
        bad["orders"][0]["filled_qty"] = "0.5"
        with self.assertRaisesRegex(ValueError, "fractional_filled_qty_not_supported"):
            C.load_paper_orders(bad)


class ClockProvenanceTests(unittest.TestCase):
    def test_host_minus_broker_offset_matches_the_measured_range_for_this_trial(self):
        orders = C.load_paper_orders(json.loads((TRIAL / "broker-orders.json").read_text()))
        paper_output = json.loads((TRIAL / "paper-output.json").read_text())
        prov = C.clock_provenance(orders, paper_output)
        self.assertEqual(len(prov["host_minus_broker_submit_offset_ms"]), 5)
        lo, hi = prov["host_minus_broker_submit_offset_ms_range"]
        self.assertAlmostEqual(lo, 27.994, places=2)
        self.assertAlmostEqual(hi, 40.769, places=2)
        self.assertTrue(all(v > 0 for v in prov["host_minus_broker_submit_offset_ms"]))

    def test_reports_null_offsets_with_a_reason_when_counts_do_not_match(self):
        # Regression for the truncated-zip bug: dropping one host submit entry must
        # not silently produce misaligned "offsets" (a constructed case with this
        # trial's data reached ~195,441ms from exactly this mistake). Kills a
        # mutation that forces counts_match=True regardless of the actual counts.
        orders = C.load_paper_orders(json.loads((TRIAL / "broker-orders.json").read_text()))
        paper_output = json.loads((TRIAL / "paper-output.json").read_text())
        truncated = json.loads(json.dumps(paper_output))
        # Drop the first submit request so the lists no longer correspond 1:1.
        first_submit_index = next(i for i, r in enumerate(truncated["requests"]) if r["kind"] == "submit")
        del truncated["requests"][first_submit_index]
        prov = C.clock_provenance(orders, truncated)
        self.assertFalse(prov["counts_match"])
        self.assertIsNone(prov["host_minus_broker_submit_offset_ms"])
        self.assertIsNone(prov["host_minus_broker_submit_offset_ms_range"])
        self.assertIsNone(prov["host_minus_broker_submit_offset_is_lower_bound"])
        self.assertIsNotNone(prov["host_minus_broker_submit_offset_unavailable_reason"])
        self.assertIn("correspondence", prov["host_minus_broker_submit_offset_unavailable_reason"])
        # And confirm the *real* (untruncated) case is nowhere near the bogus
        # magnitude a naive truncated zip would have produced here.
        with_all_requests = C.clock_provenance(orders, paper_output)
        self.assertLess(max(v for v in with_all_requests["host_minus_broker_submit_offset_ms"]), 1000)


class CancelTimestampResolutionTests(unittest.TestCase):
    def setUp(self):
        self.broker_orders = json.loads((TRIAL / "broker-orders.json").read_text())
        self.paper_output = json.loads((TRIAL / "paper-output.json").read_text())
        self.ingest_receipt = json.loads((TRIAL / "ingest-receipt.json").read_text())
        self.orders = C.load_paper_orders(self.broker_orders)

    def test_order_timeout_seconds_resolved_from_the_matching_config_file(self):
        timeout, source = C.resolve_order_timeout_seconds(self.ingest_receipt)
        self.assertEqual(timeout, 10)
        self.assertEqual(source, "matched_config:config-sip.json")

    def test_order_timeout_seconds_falls_back_when_no_config_matches(self):
        timeout, source = C.resolve_order_timeout_seconds({"config_sha256": "not_a_real_hash"})
        self.assertEqual(timeout, C.DEFAULT_ORDER_TIMEOUT_SECONDS)
        self.assertEqual(source, "default_fallback_no_config_match")

    def test_parse_cancel_request_ns_reads_the_real_recorded_cancel(self):
        cancel_ns = C.parse_cancel_request_ns(self.paper_output)
        self.assertEqual(cancel_ns, [1790182276776666000])

    def test_resolve_cancel_timestamps_uses_the_recorded_request_not_a_successor_order(self):
        resolved = C.resolve_cancel_timestamps(self.orders, self.paper_output, 10)
        self.assertEqual(set(resolved), {"adp-adaptive-20260923g-0000004"})
        entry = resolved["adp-adaptive-20260923g-0000004"]
        self.assertEqual(entry["cancel_ts_ns"], 1790182276776666000)
        self.assertEqual(entry["source"], "recorded_cancel_request")
        next_submit = next(o["submitted_at_ns"] for o in self.orders
                            if o["client_order_id"] == "adp-adaptive-20260923g-0000005")
        self.assertNotEqual(entry["cancel_ts_ns"], next_submit - 1)
        self.assertLess(entry["cancel_ts_ns"], next_submit)

    def test_resolve_cancel_timestamps_falls_back_to_timeout_when_counts_disagree(self):
        paper_output_no_cancels = {"requests": []}
        resolved = C.resolve_cancel_timestamps(self.orders, paper_output_no_cancels, 10)
        entry = resolved["adp-adaptive-20260923g-0000004"]
        self.assertEqual(entry["source"], "submit_plus_order_timeout_seconds")
        canceled = next(o for o in self.orders if o["status"] == "canceled")
        self.assertEqual(entry["cancel_ts_ns"], canceled["submitted_at_ns"] + 10 * 10**9)

    def test_two_cancels_matched_by_validated_chronological_order(self):
        base = {"symbol": "AAPL", "side": "BUY", "qty": 1, "limit_price": "1", "time_in_force": "DAY",
                "filled_qty": 0, "filled_avg_price": None, "filled_at_ns": None}
        orders = [
            dict(base, client_order_id="a", status="canceled", submitted_at_ns=1_000_000_000),
            dict(base, client_order_id="b", status="canceled", submitted_at_ns=5_000_000_000),
        ]
        paper_output = {"requests": [{"kind": "cancel", "timestamp": 1.5}, {"kind": "cancel", "timestamp": 5.5}]}
        resolved = C.resolve_cancel_timestamps(orders, paper_output, 10)
        self.assertEqual(resolved["a"]["source"], "recorded_cancel_request")
        self.assertEqual(resolved["a"]["cancel_ts_ns"], 1_500_000_000)
        self.assertEqual(resolved["b"]["cancel_ts_ns"], 5_500_000_000)

    def test_two_requests_matching_the_same_order_leave_another_order_unmatched_and_are_refused(self):
        # X (submitted 1s) is open at the first request (2s) and uniquely matches
        # it; Y is not submitted until 10s. Once X is resolved by that first match,
        # X is terminal for the *second* request (3s) too -- and Y still isn't
        # open yet -- so the second request actually finds *zero* open orders and
        # is refused by the primary per-request uniqueness check, not by the
        # accumulated-pairing check (count(canceled)=2 never even gets compared
        # against a completed pairing here, since the loop breaks on the second
        # request). Must refuse (and must not raise).
        base = {"symbol": "AAPL", "side": "BUY", "qty": 1, "limit_price": "1", "time_in_force": "DAY",
                "filled_qty": 0, "filled_avg_price": None, "filled_at_ns": None}
        orders = [
            dict(base, client_order_id="X", status="canceled", submitted_at_ns=1_000_000_000),
            dict(base, client_order_id="Y", status="canceled", submitted_at_ns=10_000_000_000),
        ]
        paper_output = {"requests": [{"kind": "cancel", "timestamp": 2.0}, {"kind": "cancel", "timestamp": 3.0}]}
        resolved = C.resolve_cancel_timestamps(orders, paper_output, 10)
        self.assertEqual(resolved["X"]["source"], "submit_plus_order_timeout_seconds_ambiguous_recorded_match_refused")
        self.assertEqual(resolved["Y"]["source"], "submit_plus_order_timeout_seconds_ambiguous_recorded_match_refused")

    def test_a_filled_order_stealing_one_pairing_slot_leaves_a_canceled_order_unmatched_and_is_refused(self):
        # Y (filled, open only in [0s, 2s)) is the unique open order at the first
        # request (1s); X (canceled, open from 3s) is the unique open order at the
        # second request (4s); Z (canceled, not submitted until 10s) never
        # coincides with either request. If a per-request uniqueness match were
        # ever trusted without checking that the *accumulated* result actually
        # covers every canceled order (and only canceled orders), Y would
        # incorrectly take a pairing slot and Z would be left with none --
        # which, if unguarded, raises a KeyError while building `resolved`
        # instead of gracefully refusing. Must refuse without raising.
        y = {"client_order_id": "Y", "symbol": "AAPL", "side": "BUY", "qty": 1, "limit_price": "1",
             "time_in_force": "DAY", "status": "filled", "filled_qty": 1, "filled_avg_price": "1",
             "submitted_at_ns": 0, "filled_at_ns": 2_000_000_000}
        x = {"client_order_id": "X", "symbol": "AAPL", "side": "BUY", "qty": 1, "limit_price": "1",
             "time_in_force": "DAY", "status": "canceled", "filled_qty": 0, "filled_avg_price": None,
             "submitted_at_ns": 3_000_000_000, "filled_at_ns": None}
        z = {"client_order_id": "Z", "symbol": "AAPL", "side": "BUY", "qty": 1, "limit_price": "1",
             "time_in_force": "DAY", "status": "canceled", "filled_qty": 0, "filled_avg_price": None,
             "submitted_at_ns": 10_000_000_000, "filled_at_ns": None}
        paper_output = {"requests": [{"kind": "cancel", "timestamp": 1.0}, {"kind": "cancel", "timestamp": 4.0}]}
        resolved = C.resolve_cancel_timestamps([x, y, z], paper_output, 10)
        self.assertEqual(resolved["X"]["source"], "submit_plus_order_timeout_seconds_ambiguous_recorded_match_refused")
        self.assertEqual(resolved["Z"]["source"], "submit_plus_order_timeout_seconds_ambiguous_recorded_match_refused")
        self.assertNotIn("Y", resolved)  # Y was never a canceled order; never in the output at all

    def test_ambiguous_match_is_refused_and_falls_back_for_all_canceled_orders(self):
        base = {"symbol": "AAPL", "side": "BUY", "qty": 1, "limit_price": "1", "time_in_force": "DAY",
                "filled_qty": 0, "filled_avg_price": None, "filled_at_ns": None}
        orders = [
            dict(base, client_order_id="a", status="canceled", submitted_at_ns=1_000_000_000),
            dict(base, client_order_id="b", status="canceled", submitted_at_ns=5_000_000_000),
        ]
        # A "cancel request" timed *before* order a's own submit: chronological
        # pairing would still count-match (2 cancels, 2 canceled orders), but the
        # pairing is nonsensical, so it must be refused rather than accepted.
        paper_output = {"requests": [{"kind": "cancel", "timestamp": 0.5}, {"kind": "cancel", "timestamp": 5.5}]}
        resolved = C.resolve_cancel_timestamps(orders, paper_output, 10)
        self.assertEqual(resolved["a"]["source"], "submit_plus_order_timeout_seconds_ambiguous_recorded_match_refused")
        self.assertEqual(resolved["b"]["source"], "submit_plus_order_timeout_seconds_ambiguous_recorded_match_refused")
        self.assertEqual(resolved["a"]["cancel_ts_ns"], 1_000_000_000 + 10 * 10**9)
        self.assertEqual(resolved["b"]["cancel_ts_ns"], 5_000_000_000 + 10 * 10**9)

    def test_cancel_after_the_next_orders_submit_is_refused_as_ambiguous(self):
        base = {"symbol": "AAPL", "side": "BUY", "qty": 1, "limit_price": "1", "time_in_force": "DAY",
                "filled_qty": 0, "filled_avg_price": None, "filled_at_ns": None}
        orders = [
            dict(base, client_order_id="a", status="canceled", submitted_at_ns=1_000_000_000),
            dict(base, client_order_id="b", status="canceled", submitted_at_ns=2_000_000_000),
        ]
        # Order a's paired cancel request lands after order b's own submit -- not a
        # sane pairing even though the counts match.
        paper_output = {"requests": [{"kind": "cancel", "timestamp": 2.5}, {"kind": "cancel", "timestamp": 6.0}]}
        resolved = C.resolve_cancel_timestamps(orders, paper_output, 10)
        self.assertEqual(resolved["a"]["source"], "submit_plus_order_timeout_seconds_ambiguous_recorded_match_refused")

    def test_accepts_a_valid_timeout_cancel_despite_an_unrelated_later_order_of_another_symbol(self):
        # The earlier "most-recently-submitted order overall" heuristic wrongly
        # refused this: order A (INTC) submitted at 0s and canceled by a genuine
        # timeout request at 10s; order B (GOOGL, a different symbol) submitted at
        # 5s and filled, entirely unrelated to A's cancel. B being the most
        # recently submitted order overall at cancel time must not make A's
        # unambiguous same-symbol pairing ambiguous. Kills a mutation that removes
        # the open-order-uniqueness check (accepting or rejecting by count alone).
        a = {"client_order_id": "A", "symbol": "INTC", "side": "BUY", "qty": 1, "limit_price": "1",
             "time_in_force": "DAY", "status": "canceled", "filled_qty": 0, "filled_avg_price": None,
             "submitted_at_ns": 0, "filled_at_ns": None}
        b = {"client_order_id": "B", "symbol": "GOOGL", "side": "BUY", "qty": 1, "limit_price": "1",
             "time_in_force": "DAY", "status": "filled", "filled_qty": 1, "filled_avg_price": "1",
             "submitted_at_ns": 5_000_000_000, "filled_at_ns": 5_500_000_000}
        paper_output = {"requests": [{"kind": "cancel", "timestamp": 10.0}]}
        resolved = C.resolve_cancel_timestamps([a, b], paper_output, 10)
        self.assertEqual(resolved["A"]["source"], "recorded_cancel_request")
        self.assertEqual(resolved["A"]["cancel_ts_ns"], 10_000_000_000)

    def test_refuses_a_race_lost_cancel_that_could_belong_to_a_still_open_unrelated_order(self):
        # Order B (GOOGL) submitted at 1s and eventually filled, but its fill time
        # (3s) is *after* the cancel request at 2.5s -- so B was genuinely still
        # open (a plausible target) when the cancel request fired. Order K (AAPL)
        # submitted at 1s is canceled. Both are open at 2.5s: this must be refused
        # as ambiguous regardless of which order is listed first (kills a mutation
        # that breaks ties by input/sort order instead of refusing them).
        base_ts = 1_000_000_000
        f = {"client_order_id": "F", "symbol": "GOOGL", "side": "BUY", "qty": 1, "limit_price": "1",
             "time_in_force": "DAY", "status": "filled", "filled_qty": 1, "filled_avg_price": "1",
             "submitted_at_ns": base_ts, "filled_at_ns": 3_000_000_000}
        k = {"client_order_id": "K", "symbol": "AAPL", "side": "BUY", "qty": 1, "limit_price": "1",
             "time_in_force": "DAY", "status": "canceled", "filled_qty": 0, "filled_avg_price": None,
             "submitted_at_ns": base_ts, "filled_at_ns": None}
        paper_output = {"requests": [{"kind": "cancel", "timestamp": 2.5}]}
        forward = C.resolve_cancel_timestamps([f, k], paper_output, 10)
        reversed_ = C.resolve_cancel_timestamps([k, f], paper_output, 10)
        self.assertEqual(forward["K"]["source"], "submit_plus_order_timeout_seconds_ambiguous_recorded_match_refused")
        self.assertEqual(reversed_["K"]["source"], "submit_plus_order_timeout_seconds_ambiguous_recorded_match_refused")
        self.assertEqual(forward["K"], reversed_["K"])


class BuildDecisionsTests(unittest.TestCase):
    def test_cancel_uses_the_resolved_timestamp(self):
        orders = C.load_paper_orders(json.loads((TRIAL / "broker-orders.json").read_text()))
        paper_output = json.loads((TRIAL / "paper-output.json").read_text())
        cancel_resolution = C.resolve_cancel_timestamps(orders, paper_output, 10)
        decisions = C.build_decisions(orders, cancel_resolution)
        self.assertEqual(sum(1 for d in decisions if d["action"] == "submit"), 5)
        cancels = [d for d in decisions if d["action"] == "cancel"]
        self.assertEqual(len(cancels), 1)
        self.assertEqual(cancels[0]["order"]["client_order_id"], "adp-adaptive-20260923g-0000004")
        self.assertEqual(cancels[0]["ts_ns"], 1790182276776666000)
        self.assertEqual(decisions, sorted(decisions, key=lambda d: (d["ts_ns"], 0 if d["action"] == "submit" else 1)))

    def test_no_cancel_decision_without_a_resolution_entry(self):
        orders = [{"symbol": "AAPL", "side": "BUY", "status": "canceled", "submitted_at_ns": 1, "filled_at_ns": None,
                   "client_order_id": "a", "qty": 1, "limit_price": "1", "time_in_force": "DAY", "filled_qty": 0,
                   "filled_avg_price": None}]
        self.assertEqual(C.build_decisions(orders), [{"ts_ns": 1, "action": "submit", "order": orders[0]}])

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
        out, drops = C.normalize_quote_rows(raw)
        self.assertEqual(len(out["INTC"]), 2)
        self.assertEqual([q["ts_ns"] for q in out["INTC"]], sorted(q["ts_ns"] for q in out["INTC"]))
        self.assertEqual(out["INTC"][0]["bid"], "120.40")
        self.assertEqual(out["INTC"][0]["ask"], "120.45")
        self.assertEqual(drops["INTC"]["one_sided_or_nonpositive"], 2)
        self.assertEqual(drops["INTC"]["crossed"], 0)

    def test_drops_crossed_quotes_and_counts_them(self):
        raw = {"GOOGL": [
            {"t": "2026-09-23T16:47:35.000000Z", "bp": 338.50, "ap": 338.40, "bs": 1, "as": 1},  # crossed: bid > ask
            {"t": "2026-09-23T16:47:36.000000Z", "bp": 338.40, "ap": 338.45, "bs": 1, "as": 1},  # valid
        ]}
        out, drops = C.normalize_quote_rows(raw)
        self.assertEqual(len(out["GOOGL"]), 1)
        self.assertEqual(out["GOOGL"][0]["bid"], "338.40")
        self.assertEqual(drops["GOOGL"]["crossed"], 1)

    def test_keeps_locked_quotes(self):
        raw = {"GOOGL": [{"t": "2026-09-23T16:47:35.000000Z", "bp": 338.40, "ap": 338.40, "bs": 1, "as": 1}]}
        out, drops = C.normalize_quote_rows(raw)
        self.assertEqual(len(out["GOOGL"]), 1)
        self.assertEqual(out["GOOGL"][0]["bid"], out["GOOGL"][0]["ask"])
        self.assertEqual(drops["GOOGL"]["crossed"], 0)

    def test_quantizes_short_decimal_strings_to_two_places(self):
        raw = {"GOOGL": [{"t": "2026-09-23T16:47:35.000000Z", "bp": 120.5, "ap": 120.50, "bs": 1, "as": 1}]}
        out, _ = C.normalize_quote_rows(raw)
        self.assertEqual(out["GOOGL"][0]["bid"], "120.50")
        self.assertEqual(out["GOOGL"][0]["ask"], "120.50")


class BpsTests(unittest.TestCase):
    def test_bps_direction_and_none_propagation(self):
        self.assertAlmostEqual(C.bps("101", "100"), 100.0)
        self.assertAlmostEqual(C.bps("99", "100"), -100.0)
        self.assertIsNone(C.bps(None, "100"))
        self.assertIsNone(C.bps("100", None))
        self.assertIsNone(C.bps("100", 0))


class SignedSlippageTests(unittest.TestCase):
    def test_buy_paying_more_than_limit_is_positive(self):
        self.assertAlmostEqual(C.signed_slippage_bps("BUY", "101", "100"), 100.0)

    def test_sell_receiving_less_than_limit_is_positive(self):
        self.assertAlmostEqual(C.signed_slippage_bps("SELL", "99", "100"), 100.0)

    def test_sell_receiving_more_than_limit_is_negative(self):
        self.assertAlmostEqual(C.signed_slippage_bps("SELL", "101", "100"), -100.0)

    def test_none_propagation(self):
        self.assertIsNone(C.signed_slippage_bps("BUY", None, "100"))
        self.assertIsNone(C.signed_slippage_bps("BUY", "100", None))


class CompareOrdersTests(unittest.TestCase):
    def paper(self, **over):
        base = {"client_order_id": "x", "symbol": "INTC", "side": "BUY", "qty": 1, "limit_price": "120.60",
                "status": "filled", "filled_qty": 1, "filled_avg_price": "120.57",
                "submitted_at_ns": 0, "filled_at_ns": 10**9}
        base.update(over)
        return base

    def sim(self, **over):
        base = {"status": "FILLED", "filled_qty": 1, "avg_px": "120.58", "fill_ts_ns": 2 * 10**9, "reject_reason": None}
        base.update(over)
        return base

    def test_both_filled_agreement_with_price_and_time_deltas(self):
        paper = [self.paper()]
        sim = {"x": self.sim()}
        out = C.compare_orders(paper, sim)
        row = out["rows"][0]
        self.assertTrue(row["fill_agreement"])
        self.assertAlmostEqual(row["fill_price_delta_bps"], (120.58 / 120.57 - 1) * 1e4, places=4)
        self.assertAlmostEqual(row["fill_time_delta_s"], 1.0)
        self.assertEqual(out["aggregates"]["fill_agreement_rate"], 1.0)
        self.assertEqual(out["aggregates"]["both_filled"], 1)

    def test_paper_filled_sim_no_fill_is_a_disagreement(self):
        paper = [self.paper()]
        sim = {"x": self.sim(status="REJECTED", filled_qty=0, avg_px=None, fill_ts_ns=None,
                              reject_reason="Short selling not permitted on a CASH account")}
        out = C.compare_orders(paper, sim)
        self.assertFalse(out["rows"][0]["fill_agreement"])
        self.assertIsNone(out["rows"][0]["fill_price_delta_bps"])
        self.assertEqual(out["rows"][0]["sim_reject_reason"], "Short selling not permitted on a CASH account")
        self.assertEqual(out["aggregates"]["fill_agreement_rate"], 0.0)
        self.assertEqual(out["aggregates"]["both_filled"], 0)

    def test_paper_canceled_and_sim_no_fill_agree(self):
        paper = [self.paper(status="canceled", filled_qty=0, filled_avg_price=None, filled_at_ns=None)]
        sim = {"x": self.sim(status="CANCELED", filled_qty=0, avg_px=None, fill_ts_ns=None)}
        out = C.compare_orders(paper, sim)
        self.assertTrue(out["rows"][0]["fill_agreement"])
        self.assertEqual(out["aggregates"]["fill_agreement_rate"], 1.0)

    def test_missing_sim_order_counts_as_no_fill_not_a_crash(self):
        paper = [self.paper()]
        out = C.compare_orders(paper, {})
        self.assertFalse(out["rows"][0]["sim_present"])
        self.assertFalse(out["rows"][0]["fill_agreement"])

    def test_partial_fill_is_scored_by_quantity_not_a_boolean(self):
        paper = [self.paper(qty=3, filled_qty=1, status="partially_filled")]
        sim = {"x": self.sim(status="FILLED", filled_qty=3)}
        out = C.compare_orders(paper, sim)
        row = out["rows"][0]
        self.assertFalse(row["fill_agreement"])  # 1 != 3, correctly scored as a disagreement
        self.assertEqual(row["paper_filled_qty"], 1)
        self.assertEqual(row["sim_filled_qty"], 3)

    def test_matching_partial_fills_agree(self):
        paper = [self.paper(qty=3, filled_qty=1, status="partially_filled")]
        sim = {"x": self.sim(status="PARTIALLY_FILLED", filled_qty=1)}
        out = C.compare_orders(paper, sim)
        self.assertTrue(out["rows"][0]["fill_agreement"])

    def test_a_partial_fill_followed_by_a_later_cancel_does_not_report_the_cancel_time_as_the_fill_time(self):
        # Regression for the ts_last-vs-fill_ts_ns bug: order.ts_last would be the
        # *last event of any kind*, so a 1-share fill at t=1s followed by a cancel
        # of the remainder at t=10s must not surface t=10s as the fill time.
        paper = [self.paper(qty=3, filled_qty=1, status="partially_filled", filled_at_ns=1 * 10**9)]
        sim = {"x": self.sim(status="CANCELED", filled_qty=1, avg_px="120.58", fill_ts_ns=1_100_000_000)}
        out = C.compare_orders(paper, sim)
        row = out["rows"][0]
        self.assertEqual(row["sim_fill_ts"], C.ns_to_iso(1_100_000_000))
        self.assertAlmostEqual(row["fill_time_delta_s"], 0.1, places=6)

    def test_slippage_fields_on_a_buy_row(self):
        paper = [self.paper(side="BUY", limit_price="100.00", filled_avg_price="100.00")]
        sim = {"x": self.sim(avg_px="100.02")}
        out = C.compare_orders(paper, sim)
        row = out["rows"][0]
        self.assertAlmostEqual(row["paper_slippage_vs_limit_bps"], 0.0, places=6)
        self.assertAlmostEqual(row["sim_slippage_vs_limit_bps"], 2.0, places=1)  # BUY paying more than limit: positive

    def test_slippage_fields_on_a_sell_row(self):
        paper = [self.paper(side="SELL", limit_price="100.00", filled_avg_price="100.00")]
        sim = {"x": self.sim(avg_px="99.98")}
        out = C.compare_orders(paper, sim)
        row = out["rows"][0]
        self.assertAlmostEqual(row["paper_slippage_vs_limit_bps"], 0.0, places=6)
        self.assertAlmostEqual(row["sim_slippage_vs_limit_bps"], 2.0, places=1)  # SELL receiving less than limit: positive

    def test_paper_side_slippage_sign_for_buy_and_sell(self):
        # Both prior BUY/SELL slippage tests used a paper fixture whose fill price
        # equals its own limit price, so paper_slippage_vs_limit_bps was always 0.0
        # regardless of which side was passed to signed_slippage_bps -- reversing
        # the side at the paper_slippage_vs_limit_bps call site specifically (not
        # the shared signed_slippage_bps function) would not have been caught.
        # Use a paper fill price that actually differs from the limit on both sides.
        paper_buy = [self.paper(side="BUY", limit_price="100.00", filled_avg_price="100.02")]
        out = C.compare_orders(paper_buy, {})
        self.assertAlmostEqual(out["rows"][0]["paper_slippage_vs_limit_bps"], 2.0, places=1)  # BUY paying more: positive

        paper_sell = [self.paper(side="SELL", limit_price="100.00", filled_avg_price="99.98")]
        out = C.compare_orders(paper_sell, {})
        self.assertAlmostEqual(out["rows"][0]["paper_slippage_vs_limit_bps"], 2.0, places=1)  # SELL receiving less: positive

    def test_aggregates_over_mixed_synthetic_orders(self):
        paper = [self.paper(client_order_id="a"), self.paper(client_order_id="b", limit_price="120.62"),
                 self.paper(client_order_id="c", status="canceled", filled_qty=0, filled_avg_price=None, filled_at_ns=None)]
        sim = {"a": self.sim(avg_px="120.57", fill_ts_ns=10**9),
               "b": self.sim(status="REJECTED", filled_qty=0, avg_px=None, fill_ts_ns=None),
               "c": self.sim(status="CANCELED", filled_qty=0, avg_px=None, fill_ts_ns=None)}
        out = C.compare_orders(paper, sim)
        agg = out["aggregates"]
        self.assertEqual(agg["orders"], 3)
        self.assertEqual(agg["fill_agreements"], 2)
        self.assertAlmostEqual(agg["fill_agreement_rate"], 2 / 3)
        self.assertEqual(agg["both_filled"], 1)
        self.assertAlmostEqual(agg["abs_fill_price_delta_bps_mean"], 0.0)


# Module-level (not nested) so type(ev).__name__ is exactly "OrderFilled" etc.,
# matching the real NautilusTrader event class names that summarize_sim_order
# dispatches on -- a nested or aliased class would report a different __name__.
class OrderFilled:
    def __init__(self, ts_event):
        self.ts_event = ts_event


class OrderCanceled:
    def __init__(self, ts_event):
        self.ts_event = ts_event


class OrderRejected:
    def __init__(self, ts_event, reason):
        self.ts_event = ts_event
        self.reason = reason


class _FakeOrder:
    def __init__(self, status, filled_qty, avg_px, ts_last, events):
        self.client_order_id = "fake-01"
        self.status = status
        self.filled_qty = filled_qty
        self.avg_px = avg_px
        self.ts_last = ts_last
        self._events = events

    def events(self):
        return self._events


class SummarizeSimOrderTests(unittest.TestCase):
    """Direct, native-runtime-independent tests of summarize_sim_order's event
    extraction, using minimal fake order/event objects (matched by class name, the
    same way summarize_sim_order itself dispatches on `type(ev).__name__`). This is
    the authoritative test for the fill_ts_ns-vs-ts_last distinction: the current
    engine configuration cannot produce a native partial-fill-then-cancel case (see
    PinnedRuntimeTests.test_current_no_partial_fill_configuration_ignores_quoted_size),
    so this test exercises the same extraction function directly instead, and runs
    on system python3 (no pinned runtime needed)."""

    def test_partial_fill_then_later_cancel_uses_the_fill_events_timestamp_not_ts_last(self):
        fill_ns, cancel_ns = 1_000_000_000, 10_000_000_000
        order = _FakeOrder(status="CANCELED", filled_qty=1, avg_px="10.00", ts_last=cancel_ns,
                            events=[OrderFilled(fill_ns), OrderCanceled(cancel_ns)])
        summary = C.summarize_sim_order(order)
        self.assertEqual(summary["status"], "CANCELED")
        self.assertEqual(summary["filled_qty"], 1)
        self.assertEqual(summary["ts_last"], cancel_ns)
        # The actual assertion this test exists for: fill_ts_ns must be the fill
        # event's own timestamp, not ts_last (which is the cancel's timestamp
        # here). A revert to `fill_ts_ns = int(order.ts_last)` fails this directly.
        self.assertEqual(summary["fill_ts_ns"], fill_ns)
        self.assertNotEqual(summary["fill_ts_ns"], summary["ts_last"])

    def test_full_fill_with_no_later_event(self):
        order = _FakeOrder(status="FILLED", filled_qty=1, avg_px="10.00", ts_last=5_000_000_000,
                            events=[OrderFilled(5_000_000_000)])
        summary = C.summarize_sim_order(order)
        self.assertEqual(summary["fill_ts_ns"], 5_000_000_000)

    def test_rejected_order_captures_reason_and_has_no_fill_timestamp(self):
        order = _FakeOrder(status="REJECTED", filled_qty=0, avg_px=None, ts_last=2_000_000_000,
                            events=[OrderRejected(2_000_000_000, "Short selling not permitted")])
        summary = C.summarize_sim_order(order)
        self.assertIsNone(summary["fill_ts_ns"])
        self.assertEqual(summary["reject_reason"], "Short selling not permitted")

    def test_two_partial_fills_use_the_last_fill_events_timestamp(self):
        order = _FakeOrder(status="FILLED", filled_qty=2, avg_px="10.01", ts_last=3_000_000_000,
                            events=[OrderFilled(1_000_000_000), OrderFilled(3_000_000_000)])
        summary = C.summarize_sim_order(order)
        self.assertEqual(summary["fill_ts_ns"], 3_000_000_000)


class ClassifyFlipDependenceTests(unittest.TestCase):
    """Pure-Python (no native runtime) tests of classify_flip_dependence's
    orchestration logic, via monkeypatching the module-level `_order_agrees_at_latency`
    it calls -- this is legitimate for testing the *scanning* logic itself,
    independent of whether a real BacktestEngine fixture can be built to reproduce
    a shifted boundary precisely."""

    def test_a_flip_that_shifts_elsewhere_in_the_declared_sweep_is_still_independent(self):
        # Regression for probing only the original bisection endpoints: order "A"'s
        # own boundary (independent of "B") is at 10ms when B is removed, but at
        # 30ms when B is present. The original bracket was [20, 50]ms. Probing only
        # those two endpoints with B removed would see A agreeing at *both* (since
        # its shifted 10ms boundary means it already agrees by 20ms), wrongly
        # concluding "no flip -> dependent". Scanning the full declared sweep finds
        # the real (shifted) flip and correctly reports independent_flip=True.
        def fake_agrees(paper_orders, quotes_by_symbol, cancel_resolution, out_dir, client_order_id, latency_ns):
            ms = latency_ns // 10**6
            has_b = any(o["client_order_id"] == "B" for o in paper_orders)
            if client_order_id == "A":
                return ms >= (30 if has_b else 10)
            if client_order_id == "B":
                return ms >= 30
            raise AssertionError(f"unexpected client_order_id {client_order_id}")

        real_fn = C._order_agrees_at_latency
        C._order_agrees_at_latency = fake_agrees
        try:
            paper_orders = [{"client_order_id": "A"}, {"client_order_id": "B"}]
            flip_bisections = [
                {"client_order_id": "A", "bracket_ms": [20, 50],
                 "lo": {"latency_ns": 20_000_000, "agrees": False}, "hi": {"latency_ns": 50_000_000, "agrees": True},
                 "resolution_ns": 1000},
                {"client_order_id": "B", "bracket_ms": [20, 50],
                 "lo": {"latency_ns": 20_000_000, "agrees": False}, "hi": {"latency_ns": 50_000_000, "agrees": True},
                 "resolution_ns": 1000},
            ]
            C.classify_flip_dependence(paper_orders, {}, {}, Path("/unused"), flip_bisections)
        finally:
            C._order_agrees_at_latency = real_fn

        entry_a = next(b for b in flip_bisections if b["client_order_id"] == "A")
        self.assertTrue(entry_a["independent_flip"])
        self.assertEqual(entry_a["depends_on_client_order_ids"], [])
        self.assertIsNotNone(entry_a["counterfactual_sweep"])
        self.assertEqual({p["latency_ms"] for p in entry_a["counterfactual_sweep"]}, set(C.LATENCY_SWEEP_MS))
        # And confirm the flip really is invisible if only the original two
        # endpoints (20ms, 50ms) are inspected -- both are True once B is removed,
        # which is exactly what makes probing only the endpoints unsound here.
        endpoints_only = {p["agrees"] for p in entry_a["counterfactual_sweep"] if p["latency_ms"] in (20, 50)}
        self.assertEqual(endpoints_only, {True})

    def test_a_flip_that_truly_disappears_is_reported_dependent(self):
        def fake_agrees(paper_orders, quotes_by_symbol, cancel_resolution, out_dir, client_order_id, latency_ns):
            has_b = any(o["client_order_id"] == "B" for o in paper_orders)
            has_a = any(o["client_order_id"] == "A" for o in paper_orders)
            ms = latency_ns // 10**6
            if client_order_id == "A":
                return True if not has_b else ms >= 30
            if client_order_id == "B":
                return True if not has_a else ms >= 30
            raise AssertionError(f"unexpected client_order_id {client_order_id}")

        real_fn = C._order_agrees_at_latency
        C._order_agrees_at_latency = fake_agrees
        try:
            paper_orders = [{"client_order_id": "A"}, {"client_order_id": "B"}]
            flip_bisections = [
                {"client_order_id": "A", "bracket_ms": [20, 50],
                 "lo": {"latency_ns": 20_000_000, "agrees": False}, "hi": {"latency_ns": 50_000_000, "agrees": True},
                 "resolution_ns": 1000},
                {"client_order_id": "B", "bracket_ms": [20, 50],
                 "lo": {"latency_ns": 20_000_000, "agrees": False}, "hi": {"latency_ns": 50_000_000, "agrees": True},
                 "resolution_ns": 1000},
            ]
            C.classify_flip_dependence(paper_orders, {}, {}, Path("/unused"), flip_bisections)
        finally:
            C._order_agrees_at_latency = real_fn
        entry_a = next(b for b in flip_bisections if b["client_order_id"] == "A")
        self.assertFalse(entry_a["independent_flip"])
        self.assertEqual(entry_a["depends_on_client_order_ids"], ["B"])


class RedactArgsTests(unittest.TestCase):
    def test_redacts_sensitive_paths_from_a_parsed_namespace(self):
        ap = C.argparse.ArgumentParser(allow_abbrev=False)
        ap.add_argument("--trial", type=C.Path)
        ap.add_argument("--env-file", type=C.Path)
        ap.add_argument("--env-file-from-file", type=C.Path)
        ap.add_argument("--pages", type=C.Path)
        ap.add_argument("--out", type=C.Path)
        ap.add_argument("--replay", action="store_true")
        ap.add_argument("--receipt", type=C.Path)
        args = ap.parse_args(["--trial", "t", "--env-file", "/private/creds.env", "--out", "/tmp/out",
                               "--pages", "/private/pages", "--replay", "--receipt", "r.json"])
        redacted = C.redact_args(args)
        self.assertEqual(redacted, ["--trial", "t", "--env-file", "<redacted>", "--pages", "<redacted>",
                                     "--out", "<redacted>", "--replay", "--receipt", "r.json"])

    def test_allow_abbrev_false_rejects_abbreviated_flags_at_the_parser_level(self):
        # This is the actual fix for the abbreviation bypass: --pag/--ou/--rec must
        # be rejected outright by argparse, never silently accepted and then leaked
        # into the receipt's argv (the prior raw-argv-text redaction only matched
        # exact flag spellings and missed accepted abbreviations).
        with self.assertRaises(SystemExit):
            C.main(["--tri", "t", "--pag", "/private/pages", "--ou", "/tmp/out", "--rep", "--rec", "r.json"])

    def test_flag_equals_value_form_is_also_redacted(self):
        ap = C.argparse.ArgumentParser(allow_abbrev=False)
        ap.add_argument("--pages", type=C.Path)
        args = ap.parse_args(["--pages=/private/pages"])
        self.assertEqual(C.redact_args(args), ["--pages", "<redacted>"])

    def test_trial_and_receipt_paths_are_trimmed_not_recorded_verbatim(self):
        # --trial/--receipt are not secret, but an absolute path for either still
        # carries the invoking user's home directory (e.g. /home/example/...); trim
        # to repo-relative (inside the repo) or basename (outside it).
        ap = C.argparse.ArgumentParser(allow_abbrev=False)
        ap.add_argument("--trial", type=C.Path)
        ap.add_argument("--receipt", type=C.Path)
        args = ap.parse_args([
            "--trial", str(TRIAL),
            "--receipt", "/some/private/prefix/scratch/receipt.json",
        ])
        redacted = C.redact_args(args)
        trial_value = redacted[redacted.index("--trial") + 1]
        receipt_value = redacted[redacted.index("--receipt") + 1]
        self.assertFalse(Path(trial_value).is_absolute())
        self.assertNotIn(str(Path.home()), trial_value)
        self.assertEqual(receipt_value, "receipt.json")  # outside the repo -> basename only
        self.assertNotIn("private", receipt_value)
        self.assertNotIn("prefix", receipt_value)


class PageFetcherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _seed_page(self, pages: Path, base, path, params, body: dict, status=200):
        raw = json.dumps(body).encode()
        key = C.req_key(base + path, params)
        name = f"{key}.json.gz"
        pages.mkdir(parents=True, exist_ok=True)
        with gzip.open(pages / name, "wb") as f:
            f.write(raw)
        rec = {"key": key, "file": name, "path": path, "status": status,
               "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        with (pages / "ledger.jsonl").open("a") as lf:
            lf.write(json.dumps(rec) + "\n")
        return key

    def test_replay_serves_from_cache_with_no_network_and_records_the_source(self):
        pages = self.tmp / "pages"
        self._seed_page(pages, "https://x", "/p", {"a": 1}, {"ok": True})
        fetcher = C.PageFetcher(pages, headers=None, replay=True)
        bodies = list(fetcher.get("https://x", "/p", {"a": 1}))
        self.assertEqual(bodies, [{"ok": True}])
        self.assertEqual(fetcher.from_cache, 1)
        self.assertEqual(fetcher.from_network, 0)
        self.assertEqual(fetcher.page_events, [{"key": fetcher.page_events[0]["key"], "source": "cache"}])

    def test_replay_with_no_retained_page_refuses_rather_than_network_fetching(self):
        pages = self.tmp / "pages"
        pages.mkdir()
        fetcher = C.PageFetcher(pages, headers=None, replay=True)
        with self.assertRaisesRegex(SystemExit, "no retained page"):
            list(fetcher.get("https://x", "/p", {"a": 1}))

    def test_hash_mismatch_is_refused(self):
        pages = self.tmp / "pages"
        key = self._seed_page(pages, "https://x", "/p", {"a": 1}, {"ok": True})
        with gzip.open(pages / f"{key}.json.gz", "wb") as f:
            f.write(b'{"ok": false}')
        fetcher = C.PageFetcher(pages, headers=None, replay=True)
        with self.assertRaisesRegex(SystemExit, "page hash mismatch"):
            list(fetcher.get("https://x", "/p", {"a": 1}))

    def test_pagination_follows_next_page_token_through_the_cache(self):
        pages = self.tmp / "pages"
        self._seed_page(pages, "https://x", "/p", {"a": 1}, {"rows": [1], "next_page_token": "tok2"})
        self._seed_page(pages, "https://x", "/p", {"a": 1, "page_token": "tok2"}, {"rows": [2]})
        fetcher = C.PageFetcher(pages, headers=None, replay=True)
        bodies = list(fetcher.get("https://x", "/p", {"a": 1}))
        self.assertEqual(bodies, [{"rows": [1], "next_page_token": "tok2"}, {"rows": [2]}])
        self.assertEqual(fetcher.from_cache, 2)

    def test_ledger_is_reloaded_from_an_existing_file_without_holding_it_open(self):
        pages = self.tmp / "pages"
        self._seed_page(pages, "https://x", "/p", {"a": 1}, {"ok": True})
        fetcher = C.PageFetcher(pages, headers=None, replay=False)
        self.assertIn(next(iter(fetcher.ledger)), fetcher.ledger)
        fetcher2 = C.PageFetcher(pages, headers=None, replay=False)
        self.assertEqual(len(fetcher2.ledger), 1)


class ReceiptConsistencyTests(unittest.TestCase):
    """Recomputes the retained receipt's aggregates and hashes from the same
    inputs it claims to describe, independent of whatever produced it."""

    def setUp(self):
        if not RECEIPT_PATH.exists():
            self.skipTest("no retained receipt committed yet")
        self.receipt = json.loads(RECEIPT_PATH.read_text())

    def test_inputs_sha256_matches_the_retained_trial_files_on_disk(self):
        expected = self.receipt["inputs_sha256"]
        self.assertEqual(expected["broker_orders_json"], C.digest_path(TRIAL / "broker-orders.json"))
        self.assertEqual(expected["paper_output_json"], C.digest_path(TRIAL / "paper-output.json"))
        self.assertEqual(expected["ingest_receipt_json"], C.digest_path(TRIAL / "ingest-receipt.json"))

    def test_runner_sha256_matches_the_committed_replay_compare_source(self):
        self.assertEqual(self.receipt["runner_sha256"], C.digest_path(SOURCE))

    def test_results_rows_recompute_to_the_same_aggregates_from_the_receipt_rows_alone(self):
        rows = self.receipt["results"]["rows"]
        paper_orders = [{
            "client_order_id": r["client_order_id"], "symbol": r["symbol"], "side": r["side"],
            "qty": r["qty"], "limit_price": r["limit_price"], "status": r["paper_status"],
            "filled_qty": r["paper_filled_qty"], "filled_avg_price": r["paper_fill_price"],
            "submitted_at_ns": 0,
            "filled_at_ns": C.ts_ns(r["paper_fill_ts"]) if r["paper_fill_ts"] else None,
        } for r in rows]
        sim_by_id = {r["client_order_id"]: {
            "status": r["sim_status"], "filled_qty": r["sim_filled_qty"], "avg_px": r["sim_fill_price"],
            "fill_ts_ns": C.ts_ns(r["sim_fill_ts"]) if r["sim_fill_ts"] else None, "reject_reason": r["sim_reject_reason"],
        } for r in rows if r["sim_present"]}
        recomputed = C.compare_orders(paper_orders, sim_by_id)
        self.assertEqual(recomputed["aggregates"]["fill_agreements"], self.receipt["results"]["aggregates"]["fill_agreements"])
        self.assertEqual(recomputed["aggregates"]["orders"], self.receipt["results"]["aggregates"]["orders"])
        self.assertEqual(recomputed["aggregates"]["both_filled"], self.receipt["results"]["aggregates"]["both_filled"])

    def test_the_headline_disagreement_is_not_attributed_to_cancel_timing(self):
        blob = json.dumps(self.receipt)
        self.assertIn("recorded_cancel_request", blob)
        self.assertEqual(self.receipt["cancel_timestamp_resolution"]["by_client_order_id"]
                          ["adp-adaptive-20260923g-0000004"]["source"], "recorded_cancel_request")
        # The receipt's own scope text must call the timing explanation a
        # hypothesis (it lives primarily in the README, but the receipt should
        # not contradict that framing either).
        self.assertIn("hypothesis", self.receipt["scope"].lower())

    def test_latency_sweep_is_present_and_covers_the_declared_points(self):
        sweep = self.receipt["latency_sensitivity_sweep"]["points"]
        self.assertEqual([p["latency_ms"] for p in sweep], list(C.LATENCY_SWEEP_MS))
        zero = sweep[0]
        seventy = next(p for p in sweep if p["latency_ms"] == 70)
        self.assertEqual(zero["fill_agreements"], 3)
        self.assertEqual(seventy["fill_agreements"], 5)

    def test_sweep_points_carry_full_per_order_rows_not_only_aggregates(self):
        # Every per-order figure cited in the README's "Latency model semantics"
        # prose (e.g. order 3's lag from its modeled arrival, order 2's price delta
        # at 100ms) must be traceable to data actually stored in the receipt.
        sweep = self.receipt["latency_sensitivity_sweep"]["points"]
        five_ms = next(p for p in sweep if p["latency_ms"] == 5)
        self.assertIn("rows", five_ms)
        row3 = next(r for r in five_ms["rows"] if r["client_order_id"].endswith("0000003"))
        self.assertIsNotNone(row3["sim_fill_ts"])
        self.assertIsNotNone(row3["fill_time_delta_s"])
        seventy_ms = next(p for p in sweep if p["latency_ms"] == 70)
        hundred_ms = next(p for p in sweep if p["latency_ms"] == 100)
        two_fifty_ms = next(p for p in sweep if p["latency_ms"] == 250)
        row1_100 = next(r for r in hundred_ms["rows"] if r["client_order_id"].endswith("0000001"))
        row2_70 = next(r for r in seventy_ms["rows"] if r["client_order_id"].endswith("0000002"))
        row2_100 = next(r for r in hundred_ms["rows"] if r["client_order_id"].endswith("0000002"))
        row2_250 = next(r for r in two_fifty_ms["rows"] if r["client_order_id"].endswith("0000002"))
        # Order 1 is unchanged across 50-650ms (+0.829bps at every point, including
        # 70ms and 250ms, not just 100ms) -- it is not what makes 100ms an outlier
        # relative to its neighbors. Order 2 changes specifically at 100ms
        # (-0.8295bps) relative to its own value at the neighboring 70ms/250ms
        # points (0.0bps at both) -- order 2's move is what accounts for the
        # 100ms sweep point's 0.489bps mean, not order 1.
        self.assertAlmostEqual(row1_100["fill_price_delta_bps"], 0.829, places=2)
        self.assertAlmostEqual(row2_70["fill_price_delta_bps"], 0.0, places=6)
        self.assertAlmostEqual(row2_100["fill_price_delta_bps"], -0.8295, places=3)
        self.assertAlmostEqual(row2_250["fill_price_delta_bps"], 0.0, places=6)

    def test_flip_bisections_record_the_actual_agreement_direction_not_an_assumed_one(self):
        # Bisection-direction regression guard: for this trial, agreement is FALSE
        # at the lower latency endpoint and TRUE at the higher one (a lower-latency
        # sim fills an order paper did not) -- the opposite of "agrees below,
        # disagrees above." This must be readable from explicit per-endpoint fields,
        # not assumed from key names, and must match what the sweep points
        # themselves say about the same orders at the bracket's endpoints.
        bisections = self.receipt["latency_sensitivity_sweep"]["flip_bisections"]
        self.assertTrue(bisections)
        sweep_by_ms = {p["latency_ms"]: p for p in self.receipt["latency_sensitivity_sweep"]["points"]}
        for b in bisections:
            self.assertIn("lo", b)
            self.assertIn("hi", b)
            self.assertLessEqual(b["hi"]["latency_ns"] - b["lo"]["latency_ns"], b["resolution_ns"])
            self.assertLessEqual(b["resolution_ns"], 1000)
            self.assertNotEqual(b["lo"]["agrees"], b["hi"]["agrees"])
            # Cross-check against the coarse sweep points bracketing this bisection:
            # the sweep point at the lower bracket latency must show this order
            # disagreeing exactly when the bisection says lo["agrees"] is False.
            lo_bracket_point = sweep_by_ms[b["bracket_ms"][0]]
            hi_bracket_point = sweep_by_ms[b["bracket_ms"][1]]
            lo_disagrees_in_sweep = b["client_order_id"] in lo_bracket_point["disagreeing_client_order_ids"]
            hi_disagrees_in_sweep = b["client_order_id"] in hi_bracket_point["disagreeing_client_order_ids"]
            self.assertEqual(b["lo"]["agrees"], not lo_disagrees_in_sweep)
            self.assertEqual(b["hi"]["agrees"], not hi_disagrees_in_sweep)
        # For this specific trial: disagrees at the lower endpoint, agrees at the
        # higher one, for every recorded bisection.
        self.assertTrue(all(b["lo"]["agrees"] is False and b["hi"]["agrees"] is True for b in bisections))

    def test_order_5s_flip_is_dependent_on_order_4_not_independent(self):
        bisections = {b["client_order_id"][-7:]: b for b in self.receipt["latency_sensitivity_sweep"]["flip_bisections"]}
        self.assertIn("0000004", bisections)
        self.assertIn("0000005", bisections)
        self.assertTrue(bisections["0000004"]["independent_flip"])
        self.assertEqual(bisections["0000004"]["depends_on_client_order_ids"], [])
        self.assertFalse(bisections["0000005"]["independent_flip"])
        self.assertTrue(any(c.endswith("0000004") for c in bisections["0000005"]["depends_on_client_order_ids"]))

    def test_clock_provenance_and_exit_code_fields(self):
        self.assertIn("clock_provenance", self.receipt)
        prov = self.receipt["clock_provenance"]
        self.assertIn("host_minus_broker_submit_offset_ms_range", prov)
        self.assertTrue(prov.get("counts_match"))
        self.assertTrue(prov.get("host_minus_broker_submit_offset_is_lower_bound"))
        # exit_code was removed rather than kept as a misleading constant 0 (a
        # failed run raises before a receipt is ever written).
        self.assertNotIn("exit_code", self.receipt)

    def test_alpaca_py_version_is_environment_metadata_not_data_provenance(self):
        self.assertNotIn("alpaca_py_version", self.receipt.get("data_provenance", {}))
        self.assertIn("alpaca_py_installed_version", self.receipt.get("runtime_environment", {}))

    def test_argv_trims_trial_and_receipt_paths(self):
        argv = self.receipt["argv"]
        for value in argv:
            self.assertNotIn(str(Path.home()), value)
        # --trial's value (whatever immediately follows it) must not be an absolute
        # path outside the repo; for this receipt it is repo-relative.
        trial_value = argv[argv.index("--trial") + 1]
        self.assertFalse(Path(trial_value).is_absolute())


class ReadmeReceiptConsistencyTests(unittest.TestCase):
    """Parses the README's per-order results table and cross-checks it against the
    committed receipt, so the table cannot silently go stale again."""

    def setUp(self):
        if not (RECEIPT_PATH.exists() and README_PATH.exists()):
            self.skipTest("receipt or README not present")
        self.receipt = json.loads(RECEIPT_PATH.read_text())
        self.readme = README_PATH.read_text()

    def test_results_table_matches_the_receipt(self):
        rows_by_suffix = {r["client_order_id"][-7:]: r for r in self.receipt["results"]["rows"]}
        table_row_re = re.compile(
            r"\|\s*`…(\d{7})`\s*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|")
        found = 0
        for m in table_row_re.finditer(self.readme):
            suffix, dpx_text, dt_text = m.groups()
            if suffix not in rows_by_suffix:
                continue
            found += 1
            row = rows_by_suffix[suffix]
            if row["fill_price_delta_bps"] is None:
                self.assertEqual(dpx_text.strip(), "n/a")
                self.assertEqual(dt_text.strip(), "n/a")
            else:
                self.assertAlmostEqual(float(dpx_text), row["fill_price_delta_bps"], places=2)
                self.assertAlmostEqual(float(dt_text), row["fill_time_delta_s"], places=2)
        self.assertEqual(found, 5)

    def test_headline_aggregates_in_prose_match_the_receipt(self):
        agg = self.receipt["results"]["aggregates"]
        self.assertIn(f"max {agg['abs_fill_time_delta_s_max']:.2f} s", self.readme)
        self.assertIn(f"{agg['fill_agreements']}/{agg['orders']}", self.readme)

    def test_four_fill_range_includes_order_5_not_just_0_68(self):
        # README:103 previously said "0.68-1.09s" excluding order 5's 0.648s.
        rows = self.receipt["results"]["aggregates"]
        both_filled_deltas = [abs(r["fill_time_delta_s"]) for r in self.receipt["results"]["rows"]
                               if r["fill_time_delta_s"] is not None]
        lo = min(both_filled_deltas)
        self.assertLess(lo, 0.68)  # order 5's 0.648s must be the low end, not order 1's 0.68s
        self.assertIn("0.65-1.09s", " ".join(self.readme.split()))

    def test_bisected_flip_values_appear_with_explicit_direction_not_just_the_number(self):
        bisections = self.receipt["latency_sensitivity_sweep"]["flip_bisections"]
        lo_ns = min(b["lo"]["latency_ns"] for b in bisections)
        hi_ns = min(b["hi"]["latency_ns"] for b in bisections)
        self.assertTrue(all(b["lo"]["agrees"] is False for b in bisections))
        self.assertTrue(all(b["hi"]["agrees"] is True for b in bisections))
        lo_ms_str = f"{lo_ns / 1e6:.6f}ms"
        hi_ms_str = f"{hi_ns / 1e6:.6f}ms"
        self.assertIn(lo_ms_str, self.readme)
        self.assertIn(hi_ms_str, self.readme)
        # The direction must be stated explicitly in prose near the numbers, not
        # left to be inferred from key names alone (the bug this round's finding
        # was about): searching only for the bare number, as the previous version
        # of this test did, would not have caught the labels being reversed.
        normalized = " ".join(self.readme.split())
        self.assertIn("disagreeing at 69.216918ms to agreeing at 69.217529ms", normalized)

    def test_order_5_is_documented_as_dependent_on_order_4_not_an_independent_flip(self):
        normalized = " ".join(self.readme.split())
        self.assertIn("not an independent second flip", normalized)
        self.assertIn("exactly one flip in this trial", normalized)
        self.assertIn("independent_flip: false", normalized)

    def test_withdrawn_wrong_direction_explanation_is_not_present(self):
        # The second (also-wrong) version of the H1 explanation claimed the order
        # "becomes marketable" at submit+69ms; it was actually already marketable
        # at submit and *stops* being marketable there. Guard against silently
        # reintroducing the wrong-direction phrasing.
        normalized = " ".join(self.readme.split())
        self.assertNotIn("become marketable the instant real SIP quotes cross it", normalized)
        self.assertIn("already marketable at submit", normalized)
        self.assertIn("stops being marketable", normalized)

    def test_no_unmeasured_cancel_before_fill_claim(self):
        # README previously said Alpaca "processed the cancel before a fill" as if
        # measured; the cancel came 10.09s after submit and no fill-vs-cancel race
        # for order 4 was directly measured. The corrected wording must say so.
        normalized = " ".join(self.readme.split())
        self.assertNotIn("enough real latency for Alpaca to have processed the cancel before a fill", normalized)
        self.assertIn("no fill-vs-cancel race for order 4 was directly measured", normalized)

    def test_decision_to_fill_wording_replaced_with_broker_submission_to_fill(self):
        normalized = " ".join(self.readme.split())
        self.assertNotIn("decision-to-fill latency", normalized)
        self.assertIn("broker submission-to-fill interval", normalized)

    def test_clock_offset_stated_as_a_lower_bound_not_an_upper_one(self):
        normalized = " ".join(self.readme.split())
        self.assertNotIn("up to ~41ms", normalized)
        self.assertIn("at least +27.994 to +40.769ms", normalized)
        self.assertIn("lower bound", normalized.lower())

    def test_cancel_pairing_validated_against_every_order_not_only_canceled_ones(self):
        normalized = " ".join(self.readme.split())
        self.assertNotIn("validated, not positional.", normalized)
        self.assertNotIn("chronological order is the only available signal, and it is validated", normalized)
        self.assertIn("open-order uniqueness across the whole trial, not positional", normalized)

    def test_hypothesis_framing_and_clock_provenance_section_present(self):
        self.assertIn("hypothesis", self.readme.lower())
        self.assertIn("Clock sources and provenance", self.readme)
        self.assertIn("27.994", self.readme)
        self.assertIn("40.769", self.readme)

    def test_reproduce_snippet_does_not_interpolate_env_var_inside_a_quoted_heredoc(self):
        # The old snippet embedded $PRIVATE_CACHE_DIR inside `<<'PY' ... PY` (quoted
        # heredoc -> no shell expansion) and read it with plain Python string
        # literal -> FileNotFoundError. The fixed snippet must pass it as argv.
        self.assertIn("sys.argv[1]", self.readme)
        self.assertNotIn('open("$PRIVATE_CACHE_DIR', self.readme)


@unittest.skipUnless(_pinned_runtime_active(), "requires the pinned nautilus_trader==2.0.0rc5 runtime")
class PinnedRuntimeTests(unittest.TestCase):
    """Exercises run_replay end to end on tiny synthetic fixtures."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _order(self, coid, side, submitted_at_ns, limit_price, status="filled", filled_qty=1, filled_avg_price=None,
               qty=1):
        return {"client_order_id": coid, "symbol": "ZZZZ", "side": side, "qty": qty, "limit_price": limit_price,
                "time_in_force": "DAY", "status": status, "filled_qty": filled_qty,
                "filled_avg_price": filled_avg_price, "submitted_at_ns": submitted_at_ns, "filled_at_ns": None}

    def test_order_marketable_only_briefly_fills_at_zero_latency(self):
        # Submit time (t0 + 1_234_567 ns) deliberately does NOT coincide with any
        # quote timestamp below: if decision timing silently fell back to "next
        # quote of any symbol" instead of the exact clock.set_time_alert_ns instant
        # (the withdrawn behavior this fixture is designed to catch -- an earlier
        # version of this fixture submitted exactly on a quote timestamp and could
        # not have told the two apart), the fill would happen at the wrong instant
        # relative to this marketable window and this test would need adjustment.
        t0 = 1_000_000_000_000
        submit_ns = t0 + 1_234_567  # off-quote
        quotes = {"ZZZZ": [
            {"symbol": "ZZZZ", "ts_ns": t0, "bid": "9.90", "ask": "10.10", "bid_size": 100, "ask_size": 100},
            {"symbol": "ZZZZ", "ts_ns": t0 + 50_000_000, "bid": "9.95", "ask": "9.99", "bid_size": 100, "ask_size": 100},
            {"symbol": "ZZZZ", "ts_ns": t0 + 200_000_000, "bid": "9.90", "ask": "10.10", "bid_size": 100, "ask_size": 100},
        ]}
        paper_orders = [self._order("t-0000001", "BUY", submit_ns, "10.00")]
        out_dir = self.tmp / "zero"
        result = C.run_replay(paper_orders, quotes, out_dir=out_dir)
        sim = result["sim_by_id"]["t-0000001"]
        self.assertEqual(sim["status"], "FILLED")
        self.assertEqual(sim["filled_qty"], 1)
        # The decision was *applied* (order_factory.limit + submit_order) at
        # exactly the off-quote submit instant -- clock.timestamp_ns() at
        # application time equals the scheduled ts_ns exactly, not "whenever the
        # next quote of any symbol arrives" (t0+50ms here, ~49ms later). This is
        # the M1 assertion: it only distinguishes the two behaviors because the
        # submit instant does not coincide with any quote timestamp.
        applied = json.loads((out_dir / "reports.json").read_text())["applied_decisions"]
        submit_decision = next(d for d in applied if d["client_order_id"] == "t-0000001" and d["action"] == "submit")
        self.assertEqual(submit_decision["clock_ts_ns"], submit_ns)
        self.assertEqual(submit_decision["ts_ns"], submit_ns)
        # The fill itself can only happen once a marketable quote is fed (t0+50ms
        # in this fixture); that is a data-availability fact, not a decision-timing
        # one, and is asserted separately from the M1 (exact-instant) check above.
        self.assertEqual(sim["fill_ts_ns"], t0 + 50_000_000)

    def test_higher_latency_can_change_the_fill_outcome(self):
        t0 = 2_000_000_000_000
        submit_ns = t0 + 987_654  # off-quote
        quotes = {"ZZZZ": [
            {"symbol": "ZZZZ", "ts_ns": t0, "bid": "9.90", "ask": "10.10", "bid_size": 100, "ask_size": 100},
            {"symbol": "ZZZZ", "ts_ns": t0 + 50_000_000, "bid": "9.95", "ask": "9.99", "bid_size": 100, "ask_size": 100},
            {"symbol": "ZZZZ", "ts_ns": t0 + 90_000_000, "bid": "9.90", "ask": "10.10", "bid_size": 100, "ask_size": 100},
            {"symbol": "ZZZZ", "ts_ns": t0 + 500_000_000, "bid": "9.90", "ask": "10.10", "bid_size": 100, "ask_size": 100},
        ]}
        paper_orders = [self._order("t-0000002", "BUY", submit_ns, "10.00")]
        zero_latency = C.run_replay(paper_orders, quotes, out_dir=self.tmp / "zero2")
        high_latency = C.run_replay(paper_orders, quotes, out_dir=self.tmp / "high2", latency_ns=100_000_000)
        self.assertEqual(zero_latency["sim_by_id"]["t-0000002"]["status"], "FILLED")
        self.assertNotEqual(zero_latency["sim_by_id"]["t-0000002"]["status"],
                             high_latency["sim_by_id"]["t-0000002"]["status"])

    def test_a_canceled_order_does_not_fill_on_a_later_marketable_quote(self):
        # Cancel-boundary test: submit an order that is NOT marketable at submit,
        # cancel it before a later marketable quote arrives, and confirm the sim
        # never fills it -- catching an "omitted cancellation" defect that would
        # otherwise leave the order open into that later marketable quote.
        t0 = 3_000_000_000_000
        submit_ns = t0 + 111_111
        cancel_ns = t0 + 40_000_000
        quotes = {"ZZZZ": [
            {"symbol": "ZZZZ", "ts_ns": t0, "bid": "9.80", "ask": "10.20", "bid_size": 100, "ask_size": 100},
            {"symbol": "ZZZZ", "ts_ns": t0 + 20_000_000, "bid": "9.80", "ask": "10.20", "bid_size": 100, "ask_size": 100},
            # First marketable quote is *after* the cancel.
            {"symbol": "ZZZZ", "ts_ns": t0 + 60_000_000, "bid": "9.95", "ask": "10.00", "bid_size": 100, "ask_size": 100},
            {"symbol": "ZZZZ", "ts_ns": t0 + 100_000_000, "bid": "9.95", "ask": "10.00", "bid_size": 100, "ask_size": 100},
        ]}
        paper_orders = [self._order("t-cancel-01", "BUY", submit_ns, "10.00", status="canceled", filled_qty=0)]
        cancel_resolution = {"t-cancel-01": {"cancel_ts_ns": cancel_ns, "source": "recorded_cancel_request"}}
        result = C.run_replay(paper_orders, quotes, out_dir=self.tmp / "cancel-boundary", cancel_resolution=cancel_resolution)
        sim = result["sim_by_id"]["t-cancel-01"]
        self.assertEqual(sim["status"], "CANCELED")
        self.assertEqual(sim["filled_qty"], 0)

    def test_current_no_partial_fill_configuration_ignores_quoted_size(self):
        # This documents, rather than assumes, a real boundary of the declared
        # baseline configuration (module docstring / README "Reuse and
        # methodology": no synthetic slippage or partial-fill draw,
        # liquidity_consumption=False): matching disregards quoted size entirely,
        # so a quote with ask_size smaller than the order quantity still fills the
        # order in full, immediately -- it does NOT produce a partial fill followed
        # by a cancel of the remainder. Verified directly (not assumed) so this test
        # fails loudly if a future engine/config change makes partial fills
        # possible here, at which point this test (and the module's "no
        # partial-fill draw" claim) need revisiting together.
        #
        # Because this configuration cannot produce a native partial-fill-then-
        # cancel case, the extraction logic that matters for that case
        # (summarize_sim_order's fill_ts_ns, which must come from the actual
        # OrderFilled event rather than order.ts_last) is instead tested directly
        # against constructed events in SummarizeSimOrderTests below, independent
        # of this native boundary.
        t0 = 4_000_000_000_000
        submit_ns = t0 + 222_222
        cancel_ns = t0 + 30_000_000
        quotes = {"ZZZZ": [
            {"symbol": "ZZZZ", "ts_ns": t0, "bid": "9.90", "ask": "10.00", "bid_size": 100, "ask_size": 1},
            {"symbol": "ZZZZ", "ts_ns": t0 + 10_000_000, "bid": "9.90", "ask": "10.00", "bid_size": 100, "ask_size": 1},
        ]}
        paper_orders = [self._order("t-partial-01", "BUY", submit_ns, "10.00", status="canceled", filled_qty=1, qty=2)]
        cancel_resolution = {"t-partial-01": {"cancel_ts_ns": cancel_ns, "source": "recorded_cancel_request"}}
        result = C.run_replay(paper_orders, quotes, out_dir=self.tmp / "partial-cancel", cancel_resolution=cancel_resolution)
        sim = result["sim_by_id"]["t-partial-01"]
        self.assertEqual(sim["status"], "FILLED")
        self.assertEqual(sim["filled_qty"], 2)  # full quantity despite ask_size=1

    def test_a_pending_orders_deferred_command_settles_on_another_orders_decision_timer(self):
        # Reproduces the reviewer-reported scenario exactly: order A (quotes at
        # 0ms/100ms) submitted at 10ms with 20ms latency (modeled arrival 30ms)
        # fills at 50ms -- against its existing book -- when order B (a different
        # instrument) is submitted at 50ms. B's own decision timer is a settlement
        # event that processes A's already-due deferred command well before A's own
        # next quote at 100ms and without any A-specific event anywhere near 30ms.
        # This is the `advance_time_impl` behavior the module docstring describes:
        # eligible settlement events are not limited to "the next event for that
        # instrument."
        t0 = 7_000_000_000_000
        quotes = {
            "AAAA": [
                {"symbol": "AAAA", "ts_ns": t0, "bid": "9.90", "ask": "10.00", "bid_size": 100, "ask_size": 100},
                {"symbol": "AAAA", "ts_ns": t0 + 100_000_000, "bid": "9.90", "ask": "10.00", "bid_size": 100, "ask_size": 100},
            ],
            "BBBB": [
                {"symbol": "BBBB", "ts_ns": t0, "bid": "19.90", "ask": "20.00", "bid_size": 100, "ask_size": 100},
                {"symbol": "BBBB", "ts_ns": t0 + 50_000_000, "bid": "19.90", "ask": "20.00", "bid_size": 100, "ask_size": 100},
            ],
        }
        order_a = {"client_order_id": "a-01", "symbol": "AAAA", "side": "BUY", "qty": 1, "limit_price": "10.00",
                   "time_in_force": "DAY", "status": "filled", "filled_qty": 1, "filled_avg_price": None,
                   "submitted_at_ns": t0 + 10_000_000, "filled_at_ns": None}
        order_b = {"client_order_id": "b-01", "symbol": "BBBB", "side": "BUY", "qty": 1, "limit_price": "20.00",
                   "time_in_force": "DAY", "status": "filled", "filled_qty": 1, "filled_avg_price": None,
                   "submitted_at_ns": t0 + 50_000_000, "filled_at_ns": None}
        result = C.run_replay([order_a, order_b], quotes, out_dir=self.tmp / "ab-settlement", latency_ns=20_000_000)
        sim_a = result["sim_by_id"]["a-01"]
        self.assertEqual(sim_a["status"], "FILLED")
        self.assertEqual(sim_a["fill_ts_ns"], t0 + 50_000_000)  # B's timer, not A's own 30ms modeled arrival or 100ms quote

    def test_a_foreign_instruments_quote_alone_does_not_settle_a_pending_order(self):
        # Quote-only control for the timer test above: same A (quotes 0ms/100ms,
        # submitted at 10ms, 20ms latency, modeled arrival 30ms), but BBBB has a
        # quote at 50ms with NO order of its own submitted at all. A market-data
        # quote for another instrument is not a timer and must not trigger
        # cross-instrument settlement -- A must fill at its own next quote (100ms),
        # not at 50ms.
        t0 = 7_500_000_000_000
        quotes = {
            "AAAA": [
                {"symbol": "AAAA", "ts_ns": t0, "bid": "9.90", "ask": "10.00", "bid_size": 100, "ask_size": 100},
                {"symbol": "AAAA", "ts_ns": t0 + 100_000_000, "bid": "9.90", "ask": "10.00", "bid_size": 100, "ask_size": 100},
            ],
            "BBBB": [
                {"symbol": "BBBB", "ts_ns": t0, "bid": "19.90", "ask": "20.00", "bid_size": 100, "ask_size": 100},
                {"symbol": "BBBB", "ts_ns": t0 + 50_000_000, "bid": "19.90", "ask": "20.00", "bid_size": 100, "ask_size": 100},
            ],
        }
        order_a = {"client_order_id": "a-02", "symbol": "AAAA", "side": "BUY", "qty": 1, "limit_price": "10.00",
                   "time_in_force": "DAY", "status": "filled", "filled_qty": 1, "filled_avg_price": None,
                   "submitted_at_ns": t0 + 10_000_000, "filled_at_ns": None}
        result = C.run_replay([order_a], quotes, out_dir=self.tmp / "quote-only-control", latency_ns=20_000_000)
        sim_a = result["sim_by_id"]["a-02"]
        self.assertEqual(sim_a["status"], "FILLED")
        self.assertEqual(sim_a["fill_ts_ns"], t0 + 100_000_000)  # A's own next quote, not BBBB's 50ms quote

    def test_a_bare_no_op_timer_alone_settles_a_pending_order(self):
        # Same A as the two tests above (quotes 0ms/100ms, submitted at 10ms, 20ms
        # latency, modeled arrival 30ms; fills at 100ms with no other trigger), but
        # with no order B at all -- just a bare no-op clock timer scheduled at
        # 50ms via run_replay's extra_timers_ns test hook, with no order effect
        # whatsoever. This confirms trigger (b) in the module docstring is
        # genuinely "any due timer the engine processes," not specifically an
        # order-command timer: A's fill moves from 100ms to 50ms purely because
        # the engine collected and processed the no-op timer.
        t0 = 7_600_000_000_000
        quotes = {"AAAA": [
            {"symbol": "AAAA", "ts_ns": t0, "bid": "9.90", "ask": "10.00", "bid_size": 100, "ask_size": 100},
            {"symbol": "AAAA", "ts_ns": t0 + 100_000_000, "bid": "9.90", "ask": "10.00", "bid_size": 100, "ask_size": 100},
        ]}
        order_a = {"client_order_id": "a-03", "symbol": "AAAA", "side": "BUY", "qty": 1, "limit_price": "10.00",
                   "time_in_force": "DAY", "status": "filled", "filled_qty": 1, "filled_avg_price": None,
                   "submitted_at_ns": t0 + 10_000_000, "filled_at_ns": None}
        result = C.run_replay([order_a], quotes, out_dir=self.tmp / "noop-timer", latency_ns=20_000_000,
                               extra_timers_ns=(t0 + 50_000_000,))
        sim_a = result["sim_by_id"]["a-03"]
        self.assertEqual(sim_a["status"], "FILLED")
        self.assertEqual(sim_a["fill_ts_ns"], t0 + 50_000_000)  # the no-op timer, not A's own 100ms quote

    def test_latency_lower_bounds_the_fill_time_and_settles_at_the_first_eligible_event(self):
        # Magnitude test: a fill must not happen before submit + configured latency,
        # and (with no other order's timer to bring settlement forward) must happen
        # at the first quote event at or after that instant -- and specifically NOT
        # at whatever quote a smaller (e.g. halved) latency would have picked. Two
        # marketable quotes (15ms, 30ms) straddle the candidate arrival instants for
        # the full (20ms) and halved (10ms) latency: submit+20ms=22ms lands between
        # them (first eligible settlement is the 30ms quote); submit+10ms=12ms lands
        # before the 15ms quote (first eligible settlement would be the 15ms quote
        # instead). A mutation that halves the configured latency therefore changes
        # both the fill instant and the fill price, which this test asserts exactly.
        t0 = 6_000_000_000_000
        submit_ns = t0 + 2_000_000  # +2ms
        latency_ns = 20_000_000  # 20ms -> arrival at submit+20ms = t0+22ms
        quotes = {"ZZZZ": [
            {"symbol": "ZZZZ", "ts_ns": t0, "bid": "9.90", "ask": "10.10", "bid_size": 100, "ask_size": 100},
            {"symbol": "ZZZZ", "ts_ns": t0 + 15_000_000, "bid": "9.94", "ask": "9.97", "bid_size": 100, "ask_size": 100},
            {"symbol": "ZZZZ", "ts_ns": t0 + 30_000_000, "bid": "9.92", "ask": "9.95", "bid_size": 100, "ask_size": 100},
            {"symbol": "ZZZZ", "ts_ns": t0 + 90_000_000, "bid": "9.90", "ask": "10.10", "bid_size": 100, "ask_size": 100},
        ]}
        order = self._order("t-mag-01", "BUY", submit_ns, "10.00")
        result = C.run_replay([order], quotes, out_dir=self.tmp / "magnitude", latency_ns=latency_ns)
        sim = result["sim_by_id"]["t-mag-01"]
        self.assertEqual(sim["status"], "FILLED")
        self.assertGreaterEqual(sim["fill_ts_ns"], submit_ns + latency_ns)
        # Must settle at the 30ms quote (@9.95), not the 15ms one (@9.97) that a
        # halved latency would incorrectly reach.
        self.assertEqual(sim["fill_ts_ns"], t0 + 30_000_000)
        self.assertEqual(sim["avg_px"], "9.95")

    def test_report_hashes_reproduce_across_independent_reruns_from_the_same_pages(self):
        if not RECEIPT_PATH.exists():
            self.skipTest("no retained receipt committed yet")
        pages = Path.home() / ".local/state/native-agent-stack/sim-paper/pages"
        if not pages.exists():
            self.skipTest("retained page cache not present on this host")
        receipt = json.loads(RECEIPT_PATH.read_text())
        paper = C.load_paper_orders(json.loads((TRIAL / "broker-orders.json").read_text()))
        paper_output = json.loads((TRIAL / "paper-output.json").read_text())
        ingest_receipt = json.loads((TRIAL / "ingest-receipt.json").read_text())
        timeout, _ = C.resolve_order_timeout_seconds(ingest_receipt)
        cancel_resolution = C.resolve_cancel_timestamps(paper, paper_output, timeout)
        fetcher = C.PageFetcher(pages, headers=None, replay=True)
        start_ns, end_ns = C.fetch_window(paper)
        quotes, _ = C.normalize_quote_rows(C.fetch_quotes(fetcher, sorted({o["symbol"] for o in paper}), start_ns,
                                                            end_ns, C.ns_to_iso(paper[0]["submitted_at_ns"])[:10]))
        result = C.run_replay(paper, quotes, out_dir=self.tmp / "reproduce", cancel_resolution=cancel_resolution)
        self.assertEqual(result["reports"]["fills"]["sha256_excluding_init_id"],
                          receipt["engine"]["reports"]["fills"]["sha256_excluding_init_id"])
        self.assertEqual(result["reports"]["orders"]["sha256_excluding_init_id"],
                          receipt["engine"]["reports"]["orders"]["sha256_excluding_init_id"])

    def test_bisection_direction_computed_live_matches_the_known_direction_for_order_4(self):
        # Unlike the receipt-based bisection-direction tests (which read the
        # committed, already-generated JSON and so cannot detect a mutation in
        # bisect_fill_agreement_flip itself), this test calls the function live
        # against the retained trial and checks the actual returned lo/hi agree
        # values -- this is what actually exercises, and can fail on, the bisection
        # code path. For this trial's order 4: disagrees at 50ms, agrees at 70ms.
        pages = Path.home() / ".local/state/native-agent-stack/sim-paper/pages"
        if not pages.exists():
            self.skipTest("retained page cache not present on this host")
        paper = C.load_paper_orders(json.loads((TRIAL / "broker-orders.json").read_text()))
        paper_output = json.loads((TRIAL / "paper-output.json").read_text())
        ingest_receipt = json.loads((TRIAL / "ingest-receipt.json").read_text())
        timeout, _ = C.resolve_order_timeout_seconds(ingest_receipt)
        cancel_resolution = C.resolve_cancel_timestamps(paper, paper_output, timeout)
        fetcher = C.PageFetcher(pages, headers=None, replay=True)
        start_ns, end_ns = C.fetch_window(paper)
        quotes, _ = C.normalize_quote_rows(C.fetch_quotes(fetcher, sorted({o["symbol"] for o in paper}), start_ns,
                                                            end_ns, C.ns_to_iso(paper[0]["submitted_at_ns"])[:10]))
        bisection = C.bisect_fill_agreement_flip(paper, quotes, cancel_resolution, self.tmp / "bisect-live",
                                                   "adp-adaptive-20260923g-0000004", 50 * 10**6, 70 * 10**6)
        self.assertIsNotNone(bisection)
        self.assertFalse(bisection["lo"]["agrees"])
        self.assertTrue(bisection["hi"]["agrees"])
        self.assertLess(bisection["lo"]["latency_ns"], bisection["hi"]["latency_ns"])

    def test_live_sweep_carries_per_order_rows_and_respects_the_latency_lower_bound(self):
        # Unlike the receipt-based sweep tests (which read the committed,
        # already-generated JSON and so cannot detect a mutation in
        # run_latency_sweep itself -- e.g. dropping the "rows" field, or halving
        # the latency actually passed to run_replay inside the sweep loop), this
        # test calls run_latency_sweep live against the retained trial.
        pages = Path.home() / ".local/state/native-agent-stack/sim-paper/pages"
        if not pages.exists():
            self.skipTest("retained page cache not present on this host")
        paper = C.load_paper_orders(json.loads((TRIAL / "broker-orders.json").read_text()))
        paper_output = json.loads((TRIAL / "paper-output.json").read_text())
        ingest_receipt = json.loads((TRIAL / "ingest-receipt.json").read_text())
        timeout, _ = C.resolve_order_timeout_seconds(ingest_receipt)
        cancel_resolution = C.resolve_cancel_timestamps(paper, paper_output, timeout)
        fetcher = C.PageFetcher(pages, headers=None, replay=True)
        start_ns, end_ns = C.fetch_window(paper)
        quotes, _ = C.normalize_quote_rows(C.fetch_quotes(fetcher, sorted({o["symbol"] for o in paper}), start_ns,
                                                            end_ns, C.ns_to_iso(paper[0]["submitted_at_ns"])[:10]))
        submit_ns_by_id = {o["client_order_id"]: o["submitted_at_ns"] for o in paper}
        baseline_result = C.run_replay(paper, quotes, out_dir=self.tmp / "live-sweep-base", cancel_resolution=cancel_resolution)
        baseline = C.compare_orders(paper, baseline_result["sim_by_id"])
        sweep = C.run_latency_sweep(paper, quotes, cancel_resolution=cancel_resolution,
                                     out_dir=self.tmp / "live-sweep", baseline_comparison=baseline)
        for point in sweep["points"]:
            self.assertIn("rows", point)
            self.assertEqual(len(point["rows"]), len(paper))
            for row in point["rows"]:
                if row["sim_fill_ts"] is None:
                    continue
                fill_ns = C.ts_ns(row["sim_fill_ts"])
                submit_ns = submit_ns_by_id[row["client_order_id"]]
                # A fill can never happen before submit + this point's configured
                # latency -- a mutation that halves (or otherwise shrinks) the
                # latency actually passed to run_replay inside the sweep loop would
                # violate this for at least one row at a nonzero latency point.
                self.assertGreaterEqual(fill_ns, submit_ns + point["latency_ms"] * 10**6,
                                         f"order {row['client_order_id']} at {point['latency_ms']}ms")

    def test_live_sweep_has_a_fill_time_that_actually_differs_by_configured_latency_magnitude(self):
        # Complements the lower-bound check above with a magnitude check: order 3's
        # own fill offset from submit must scale with the configured latency (not,
        # e.g., a constant or halved value) across at least two widely-separated
        # sweep points where order 3's settlement is driven by its own sparse
        # quotes (see README "Latency model semantics" -- 266.9ms/466.4ms lag at
        # 5ms/650ms respectively in the retained receipt).
        pages = Path.home() / ".local/state/native-agent-stack/sim-paper/pages"
        if not pages.exists():
            self.skipTest("retained page cache not present on this host")
        paper = C.load_paper_orders(json.loads((TRIAL / "broker-orders.json").read_text()))
        paper_output = json.loads((TRIAL / "paper-output.json").read_text())
        ingest_receipt = json.loads((TRIAL / "ingest-receipt.json").read_text())
        timeout, _ = C.resolve_order_timeout_seconds(ingest_receipt)
        cancel_resolution = C.resolve_cancel_timestamps(paper, paper_output, timeout)
        fetcher = C.PageFetcher(pages, headers=None, replay=True)
        start_ns, end_ns = C.fetch_window(paper)
        quotes, _ = C.normalize_quote_rows(C.fetch_quotes(fetcher, sorted({o["symbol"] for o in paper}), start_ns,
                                                            end_ns, C.ns_to_iso(paper[0]["submitted_at_ns"])[:10]))
        submit_ns = next(o["submitted_at_ns"] for o in paper if o["client_order_id"].endswith("0000003"))
        offsets_ms = {}
        for ms in (5, 650):
            result = C.run_replay(paper, quotes, out_dir=self.tmp / f"live-mag-{ms}", cancel_resolution=cancel_resolution,
                                   latency_ns=ms * 10**6)
            fill_ns = result["sim_by_id"]["adp-adaptive-20260923g-0000003"]["fill_ts_ns"]
            offsets_ms[ms] = (fill_ns - submit_ns) / 1e6
        # A halved-latency mutation would compress both offsets (and their
        # difference); assert the real, order-of-magnitude-larger separation.
        self.assertGreater(offsets_ms[650] - offsets_ms[5], 200)


@unittest.skipUnless(_pinned_runtime_active(), "requires the pinned nautilus_trader==2.0.0rc5 runtime")
class MainReplayNoCredentialTests(unittest.TestCase):
    """--replay must never open or require a credential file (M3)."""

    def test_main_replay_runs_with_no_env_file_argument_at_all(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        real_pages = Path.home() / ".local/state/native-agent-stack/sim-paper/pages"
        if not real_pages.exists():
            self.skipTest("retained page cache not present on this host")
        argv = ["--trial", str(TRIAL), "--pages", str(real_pages), "--out", str(tmp / "out"),
                "--replay", "--receipt", str(tmp / "receipt.json")]
        rc = C.main(argv)
        self.assertEqual(rc, 0)
        self.assertTrue((tmp / "receipt.json").exists())

    def test_the_credential_loader_module_is_never_imported_in_replay_mode(self):
        # Pre-seed sys.modules with a fake "runner" whose credentials() raises; if
        # main() ever reaches `import runner; runner.credentials(...)` in --replay
        # mode, this fake is what Python's import system would find (sys.modules
        # is checked before sys.path), and the call would raise and propagate.
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        real_pages = Path.home() / ".local/state/native-agent-stack/sim-paper/pages"
        if not real_pages.exists():
            self.skipTest("retained page cache not present on this host")
        fake = types.ModuleType("runner")

        def boom(*a, **k):
            raise AssertionError("runner.credentials() must not be called in --replay mode")

        fake.credentials = boom
        had_real = "runner" in sys.modules
        previous = sys.modules.get("runner")
        sys.modules["runner"] = fake
        try:
            argv = ["--trial", str(TRIAL), "--pages", str(real_pages), "--out", str(tmp / "out"),
                    "--replay", "--receipt", str(tmp / "receipt.json")]
            rc = C.main(argv)
            self.assertEqual(rc, 0)
        finally:
            if had_real:
                sys.modules["runner"] = previous
            else:
                del sys.modules["runner"]

    def test_stdout_write_works_when_stdout_has_no_buffer_attribute(self):
        # unittest's -b flag (output capture) replaces sys.stdout with an io.StringIO,
        # which has no `.buffer` attribute; `sys.stdout.buffer.write(...)` raises
        # AttributeError there, *after* the receipt has already been saved. Confirm
        # main() writes via plain text-mode `.write()` instead and completes cleanly
        # under a StringIO stdout, and that the written text hashes to the receipt's
        # own stdout_sha256 (i.e. the hash is still of the exact bytes written).
        import hashlib
        import io
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        real_pages = Path.home() / ".local/state/native-agent-stack/sim-paper/pages"
        if not real_pages.exists():
            self.skipTest("retained page cache not present on this host")
        argv = ["--trial", str(TRIAL), "--pages", str(real_pages), "--out", str(tmp / "out"),
                "--replay", "--receipt", str(tmp / "receipt.json")]
        fake_stdout = io.StringIO()  # no .buffer attribute, like unittest -b's capture
        real_stdout = sys.stdout
        sys.stdout = fake_stdout
        try:
            rc = C.main(argv)
        finally:
            sys.stdout = real_stdout
        self.assertEqual(rc, 0)
        receipt = json.loads((tmp / "receipt.json").read_text())
        written = fake_stdout.getvalue().encode()
        self.assertEqual(hashlib.sha256(written).hexdigest(), receipt["stdout_sha256"])
        self.assertTrue(written.endswith(b"\n"))
        self.assertEqual(receipt["stdout_sha256_basis"], "utf8_lf_normalized_text")

    def test_stdout_sha256_hashes_the_exact_bytes_written_to_a_binary_buffer_when_one_exists(self):
        # When sys.stdout has a `.buffer` (the normal case for a real process),
        # main() must write to it directly and hash exactly those bytes -- not go
        # through a text-mode `.write()` that could apply newline translation
        # (e.g. a stream opened with `newline="\r\n"`). This fake stdout's
        # `.write()` deliberately mangles newlines to CRLF; if main() ever called
        # it instead of writing to `.buffer` directly, the captured bytes would
        # contain "\r\n" and this test would catch that.
        import hashlib
        import io

        class FakeStdoutWithBuffer:
            def __init__(self):
                self.buffer = io.BytesIO()

            def write(self, s):
                self.buffer.write(s.replace("\n", "\r\n").encode())

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        real_pages = Path.home() / ".local/state/native-agent-stack/sim-paper/pages"
        if not real_pages.exists():
            self.skipTest("retained page cache not present on this host")
        argv = ["--trial", str(TRIAL), "--pages", str(real_pages), "--out", str(tmp / "out"),
                "--replay", "--receipt", str(tmp / "receipt.json")]
        fake_stdout = FakeStdoutWithBuffer()
        real_stdout = sys.stdout
        sys.stdout = fake_stdout
        try:
            rc = C.main(argv)
        finally:
            sys.stdout = real_stdout
        self.assertEqual(rc, 0)
        receipt = json.loads((tmp / "receipt.json").read_text())
        written = fake_stdout.buffer.getvalue()
        self.assertEqual(hashlib.sha256(written).hexdigest(), receipt["stdout_sha256"])
        self.assertEqual(receipt["stdout_sha256_basis"], "exact_bytes_written")
        self.assertNotIn(b"\r\n", written)  # proves .buffer.write() was used, not the mangling .write()

    def test_stdout_sha256_basis_is_text_when_buffer_attribute_exists_but_is_none(self):
        # Regression for `hasattr(sys.stdout, "buffer")` alone: a wrapper can have
        # a `.buffer` attribute that is present but set to None (unlike a real
        # stdout or io.StringIO, which either has a working buffer or lacks the
        # attribute entirely). `hasattr(...)` would wrongly report True here and
        # claim "exact_bytes_written" while main() actually falls through to
        # text-mode `.write()` -- the recorded basis and the actual write path
        # must agree.
        import hashlib

        class FakeStdoutBufferIsNone:
            buffer = None

            def __init__(self):
                self.written = []

            def write(self, s):
                self.written.append(s)

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        real_pages = Path.home() / ".local/state/native-agent-stack/sim-paper/pages"
        if not real_pages.exists():
            self.skipTest("retained page cache not present on this host")
        argv = ["--trial", str(TRIAL), "--pages", str(real_pages), "--out", str(tmp / "out"),
                "--replay", "--receipt", str(tmp / "receipt.json")]
        fake_stdout = FakeStdoutBufferIsNone()
        self.assertTrue(hasattr(fake_stdout, "buffer"))  # the misleading check this test guards against
        real_stdout = sys.stdout
        sys.stdout = fake_stdout
        try:
            rc = C.main(argv)
        finally:
            sys.stdout = real_stdout
        self.assertEqual(rc, 0)
        receipt = json.loads((tmp / "receipt.json").read_text())
        written = "".join(fake_stdout.written).encode()
        self.assertEqual(hashlib.sha256(written).hexdigest(), receipt["stdout_sha256"])
        self.assertEqual(receipt["stdout_sha256_basis"], "utf8_lf_normalized_text")

    def test_umask_is_restored_after_main_returns(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        real_pages = Path.home() / ".local/state/native-agent-stack/sim-paper/pages"
        if not real_pages.exists():
            self.skipTest("retained page cache not present on this host")
        import os
        # A *known, distinctive* umask set immediately before calling main(), not
        # "whatever the ambient process umask happens to be": main() internally sets
        # 0o077, so if an earlier test's main() call left the process umask at
        # 0o077 without restoring it (the bug this test exists to catch), and this
        # test instead compared against the ambient (already-0o077) value, the
        # comparison would trivially pass regardless of whether *this* main() call
        # restores correctly -- a real test-order-dependence failure mode. Using an
        # explicit, deliberately-different value (0o007) for both "before" and the
        # expected "after" makes the assertion depend only on this call's own
        # restore behavior, not on what ran earlier in the suite.
        KNOWN_UMASK = 0o007
        assert KNOWN_UMASK != 0o077
        original = os.umask(KNOWN_UMASK)
        try:
            argv = ["--trial", str(TRIAL), "--pages", str(real_pages), "--out", str(tmp / "out"),
                    "--replay", "--receipt", str(tmp / "receipt.json")]
            C.main(argv)
            after = os.umask(KNOWN_UMASK)
            self.assertEqual(after, KNOWN_UMASK)
        finally:
            os.umask(original)


class RetainedTrialFixtureTests(unittest.TestCase):
    """The retained trial fixture used by the native integration must keep
    parsing under this module's contract; this is a local check on that fixture,
    not a claim of unchanged upstream acceptance."""

    def test_broker_orders_fixture_still_matches_documented_shape(self):
        broker_orders = json.loads((TRIAL / "broker-orders.json").read_text())
        paper_output = json.loads((TRIAL / "paper-output.json").read_text())
        orders = C.load_paper_orders(broker_orders)
        self.assertEqual(len(orders), 5)
        symbols = {o["symbol"] for o in orders}
        self.assertEqual(symbols, {"INTC", "GOOGL"})
        cancel_resolution = C.resolve_cancel_timestamps(orders, paper_output, 10)
        decisions = C.build_decisions(orders, cancel_resolution)
        self.assertEqual(len(decisions), 6)


if __name__ == "__main__":
    unittest.main()
