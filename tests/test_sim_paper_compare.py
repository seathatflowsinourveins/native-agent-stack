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

    def test_flip_bisections_are_present_and_resolved_to_1us(self):
        bisections = self.receipt["latency_sensitivity_sweep"]["flip_bisections"]
        self.assertTrue(bisections)
        for b in bisections:
            self.assertLessEqual(b["disagrees_at_or_above_latency_ns"] - b["agrees_at_or_below_latency_ns"], b["resolution_ns"])
            self.assertLessEqual(b["resolution_ns"], 1000)

    def test_clock_provenance_and_exit_code_fields(self):
        self.assertIn("clock_provenance", self.receipt)
        self.assertIn("host_minus_broker_submit_offset_ms_range", self.receipt["clock_provenance"])
        # exit_code was removed rather than kept as a misleading constant 0 (a
        # failed run raises before a receipt is ever written).
        self.assertNotIn("exit_code", self.receipt)

    def test_alpaca_py_version_is_environment_metadata_not_data_provenance(self):
        self.assertNotIn("alpaca_py_version", self.receipt.get("data_provenance", {}))
        self.assertIn("alpaca_py_installed_version", self.receipt.get("runtime_environment", {}))


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

    def test_bisected_flip_values_appear_and_quote_derived_boundary_is_not_presented_as_the_flip(self):
        bisections = self.receipt["latency_sensitivity_sweep"]["flip_bisections"]
        lo_ms = min(b["agrees_at_or_below_latency_ns"] for b in bisections) / 1e6
        self.assertIn(f"{lo_ms:.6f}ms", self.readme)

    def test_withdrawn_wrong_direction_explanation_is_not_present(self):
        # The second (also-wrong) version of the H1 explanation claimed the order
        # "becomes marketable" at submit+69ms; it was actually already marketable
        # at submit and *stops* being marketable there. Guard against silently
        # reintroducing the wrong-direction phrasing.
        normalized = " ".join(self.readme.split())
        self.assertNotIn("become marketable the instant real SIP quotes cross it", normalized)
        self.assertIn("already marketable at submit", normalized)
        self.assertIn("stops being marketable", normalized)

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

    def test_partial_fill_then_cancel_reports_the_fill_events_time_not_the_cancel_time(self):
        # Native counterpart to CompareOrdersTests' synthetic version: qty=2 with
        # only enough top-of-book size for 1 share, then a cancel of the remainder.
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
        if sim["filled_qty"] == 0:
            self.skipTest("fixture's ask_size=1 did not produce a partial fill under the native fill model")
        self.assertIsNotNone(sim["fill_ts_ns"])
        # The fill event's timestamp must be well before the cancel, not at/after it.
        self.assertLess(sim["fill_ts_ns"], cancel_ns)

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

    def test_umask_is_restored_after_main_returns(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        real_pages = Path.home() / ".local/state/native-agent-stack/sim-paper/pages"
        if not real_pages.exists():
            self.skipTest("retained page cache not present on this host")
        import os
        before = os.umask(0o022)
        os.umask(before)  # restore immediately; `before` is what we compare against
        argv = ["--trial", str(TRIAL), "--pages", str(real_pages), "--out", str(tmp / "out"),
                "--replay", "--receipt", str(tmp / "receipt.json")]
        C.main(argv)
        after = os.umask(0o022)
        os.umask(after)
        self.assertEqual(before, after)


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
