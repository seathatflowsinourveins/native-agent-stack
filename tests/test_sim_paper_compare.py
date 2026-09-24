"""Offline tests for the sim-vs-paper fill comparison logic. Most classes here use
no network, no credential file and no NautilusTrader runtime; `run_replay` and the
CLI's `main` are exercised only by the separately gated `PinnedRuntimeTests` and
`MainReplayNoCredentialTests` classes below, which skip themselves when the active
interpreter is not the pinned nautilus_trader==2.0.0rc5 runtime. Fills are synthetic
fixtures unless noted."""
import gzip
import hashlib
import importlib.metadata
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/sim-paper-compare/replay_compare.py"
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
        # This is the runner's own recorded cancel-request instant, not the
        # withdrawn heuristic's "1ns before the next order's submit" (a distinct
        # value ~159ms earlier than the next order's actual submit time).
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
        # Can't actually happen for a marketable-through fill vs. its own limit, but
        # the function is side-agnostic arithmetic; verify the sign convention directly.
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

    def test_both_filled_agreement_with_price_and_time_deltas(self):
        paper = [self.paper()]
        sim = {"x": {"status": "FILLED", "filled_qty": 1, "avg_px": "120.58", "ts_last": 2 * 10**9, "reject_reason": None}}
        out = C.compare_orders(paper, sim)
        row = out["rows"][0]
        self.assertTrue(row["fill_agreement"])
        self.assertAlmostEqual(row["fill_price_delta_bps"], (120.58 / 120.57 - 1) * 1e4, places=4)
        self.assertAlmostEqual(row["fill_time_delta_s"], 1.0)
        self.assertEqual(out["aggregates"]["fill_agreement_rate"], 1.0)
        self.assertEqual(out["aggregates"]["both_filled"], 1)

    def test_paper_filled_sim_no_fill_is_a_disagreement(self):
        paper = [self.paper()]
        sim = {"x": {"status": "REJECTED", "filled_qty": 0, "avg_px": None, "ts_last": None,
                      "reject_reason": "Short selling not permitted on a CASH account"}}
        out = C.compare_orders(paper, sim)
        self.assertFalse(out["rows"][0]["fill_agreement"])
        self.assertIsNone(out["rows"][0]["fill_price_delta_bps"])
        self.assertEqual(out["rows"][0]["sim_reject_reason"], "Short selling not permitted on a CASH account")
        self.assertEqual(out["aggregates"]["fill_agreement_rate"], 0.0)
        self.assertEqual(out["aggregates"]["both_filled"], 0)

    def test_paper_canceled_and_sim_no_fill_agree(self):
        paper = [self.paper(status="canceled", filled_qty=0, filled_avg_price=None, filled_at_ns=None)]
        sim = {"x": {"status": "CANCELED", "filled_qty": 0, "avg_px": None, "ts_last": None, "reject_reason": None}}
        out = C.compare_orders(paper, sim)
        self.assertTrue(out["rows"][0]["fill_agreement"])
        self.assertEqual(out["aggregates"]["fill_agreement_rate"], 1.0)

    def test_missing_sim_order_counts_as_no_fill_not_a_crash(self):
        paper = [self.paper()]
        out = C.compare_orders(paper, {})
        self.assertFalse(out["rows"][0]["sim_present"])
        self.assertFalse(out["rows"][0]["fill_agreement"])

    def test_partial_fill_is_scored_by_quantity_not_a_boolean(self):
        # Paper order for qty=3, only 1 filled before cancellation; sim fully fills 3.
        paper = [self.paper(qty=3, filled_qty=1, status="partially_filled")]
        sim = {"x": {"status": "FILLED", "filled_qty": 3, "avg_px": "120.58", "ts_last": 2 * 10**9, "reject_reason": None}}
        out = C.compare_orders(paper, sim)
        row = out["rows"][0]
        self.assertFalse(row["fill_agreement"])  # 1 != 3, correctly scored as a disagreement
        self.assertEqual(row["paper_filled_qty"], 1)
        self.assertEqual(row["sim_filled_qty"], 3)

    def test_matching_partial_fills_agree(self):
        paper = [self.paper(qty=3, filled_qty=1, status="partially_filled")]
        sim = {"x": {"status": "PARTIALLY_FILLED", "filled_qty": 1, "avg_px": "120.58", "ts_last": 2 * 10**9, "reject_reason": None}}
        out = C.compare_orders(paper, sim)
        self.assertTrue(out["rows"][0]["fill_agreement"])

    def test_aggregates_over_mixed_synthetic_orders(self):
        paper = [self.paper(client_order_id="a"), self.paper(client_order_id="b", limit_price="120.62"),
                 self.paper(client_order_id="c", status="canceled", filled_qty=0, filled_avg_price=None, filled_at_ns=None)]
        sim = {"a": {"status": "FILLED", "filled_qty": 1, "avg_px": "120.57", "ts_last": 10**9, "reject_reason": None},
               "b": {"status": "REJECTED", "filled_qty": 0, "avg_px": None, "ts_last": None, "reject_reason": None},
               "c": {"status": "CANCELED", "filled_qty": 0, "avg_px": None, "ts_last": None, "reject_reason": None}}
        out = C.compare_orders(paper, sim)
        agg = out["aggregates"]
        self.assertEqual(agg["orders"], 3)
        self.assertEqual(agg["fill_agreements"], 2)
        self.assertAlmostEqual(agg["fill_agreement_rate"], 2 / 3)
        self.assertEqual(agg["both_filled"], 1)
        self.assertAlmostEqual(agg["abs_fill_price_delta_bps_mean"], 0.0)


class RedactArgvTests(unittest.TestCase):
    def test_redacts_private_path_values_but_keeps_other_args(self):
        argv = ["--trial", "t", "--env-file", "/private/creds.env", "--out", "/tmp/out",
                "--env-file-from-file=/private/pointer.txt", "--pages", "/private/pages", "--replay"]
        redacted = C.redact_argv(argv)
        self.assertEqual(redacted, ["--trial", "t", "--env-file", "<redacted>", "--out", "<redacted>",
                                     "--env-file-from-file=<redacted>", "--pages", "<redacted>", "--replay"])


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
        # Corrupt the retained page after seeding the (now-stale) ledger hash.
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
        # A second fetcher can open the same ledger file for append immediately
        # (would fail on some platforms if the first fetcher held an exclusive lock).
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
            "ts_last": C.ts_ns(r["sim_fill_ts"]) if r["sim_fill_ts"] else None, "reject_reason": r["sim_reject_reason"],
        } for r in rows if r["sim_present"]}
        recomputed = C.compare_orders(paper_orders, sim_by_id)
        self.assertEqual(recomputed["aggregates"]["fill_agreements"], self.receipt["results"]["aggregates"]["fill_agreements"])
        self.assertEqual(recomputed["aggregates"]["orders"], self.receipt["results"]["aggregates"]["orders"])
        self.assertEqual(recomputed["aggregates"]["both_filled"], self.receipt["results"]["aggregates"]["both_filled"])

    def test_the_headline_disagreement_is_not_attributed_to_cancel_timing(self):
        # H1 regression guard: the receipt/README must not re-introduce the
        # withdrawn "cancel timestamp gap" explanation for orders 4/5.
        blob = json.dumps(self.receipt)
        self.assertIn("recorded_cancel_request", blob)
        self.assertEqual(self.receipt["cancel_timestamp_resolution"]["by_client_order_id"]
                          ["adp-adaptive-20260923g-0000004"]["source"], "recorded_cancel_request")

    def test_latency_sweep_is_present_and_covers_the_declared_points(self):
        sweep = self.receipt["latency_sensitivity_sweep"]["points"]
        self.assertEqual([p["latency_ms"] for p in sweep], list(C.LATENCY_SWEEP_MS))
        zero = sweep[0]
        seventy = next(p for p in sweep if p["latency_ms"] == 70)
        self.assertEqual(zero["fill_agreements"], 3)
        self.assertEqual(seventy["fill_agreements"], 5)


@unittest.skipUnless(_pinned_runtime_active(), "requires the pinned nautilus_trader==2.0.0rc5 runtime")
class PinnedRuntimeTests(unittest.TestCase):
    """Exercises run_replay end to end on a tiny synthetic fixture where an order
    is marketable only briefly -- this is the shape of case that would have caught
    H1 (wrong disagreement attribution) and M1 (decision timing tied to quote
    arrival instead of the exact recorded instant)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _order(self, coid, side, submitted_at_ns, limit_price, status="filled", filled_qty=1, filled_avg_price=None):
        return {"client_order_id": coid, "symbol": "ZZZZ", "side": side, "qty": 1, "limit_price": limit_price,
                "time_in_force": "DAY", "status": status, "filled_qty": filled_qty,
                "filled_avg_price": filled_avg_price, "submitted_at_ns": submitted_at_ns, "filled_at_ns": None}

    def test_order_marketable_only_briefly_fills_at_zero_latency(self):
        t0 = 1_000_000_000_000
        # Quotes: ask starts above the limit, crosses briefly at t0+50ms for one
        # tick, then moves back above -- a synthetic version of order 4's ~69ms
        # marketable window in the real trial.
        quotes = {"ZZZZ": [
            {"symbol": "ZZZZ", "ts_ns": t0, "bid": "9.90", "ask": "10.10", "bid_size": 100, "ask_size": 100},
            {"symbol": "ZZZZ", "ts_ns": t0 + 50_000_000, "bid": "9.95", "ask": "9.99", "bid_size": 100, "ask_size": 100},
            {"symbol": "ZZZZ", "ts_ns": t0 + 200_000_000, "bid": "9.90", "ask": "10.10", "bid_size": 100, "ask_size": 100},
        ]}
        paper_orders = [self._order("t-0000001", "BUY", t0, "10.00")]
        result = C.run_replay(paper_orders, quotes, out_dir=self.tmp / "zero")
        sim = result["sim_by_id"]["t-0000001"]
        self.assertEqual(sim["status"], "FILLED")
        self.assertEqual(sim["filled_qty"], 1)

    def test_higher_latency_can_change_the_fill_outcome(self):
        # Same brief-cross window, but the order is only submitted at t0 and the
        # crossing tick is at t0+50ms; with enough added latency the order isn't
        # accepted by the venue until after the brief cross has passed.
        t0 = 2_000_000_000_000
        quotes = {"ZZZZ": [
            {"symbol": "ZZZZ", "ts_ns": t0, "bid": "9.90", "ask": "10.10", "bid_size": 100, "ask_size": 100},
            {"symbol": "ZZZZ", "ts_ns": t0 + 50_000_000, "bid": "9.95", "ask": "9.99", "bid_size": 100, "ask_size": 100},
            {"symbol": "ZZZZ", "ts_ns": t0 + 90_000_000, "bid": "9.90", "ask": "10.10", "bid_size": 100, "ask_size": 100},
            {"symbol": "ZZZZ", "ts_ns": t0 + 500_000_000, "bid": "9.90", "ask": "10.10", "bid_size": 100, "ask_size": 100},
        ]}
        paper_orders = [self._order("t-0000002", "BUY", t0, "10.00")]
        zero_latency = C.run_replay(paper_orders, quotes, out_dir=self.tmp / "zero2")
        high_latency = C.run_replay(paper_orders, quotes, out_dir=self.tmp / "high2", latency_ns=100_000_000)
        self.assertEqual(zero_latency["sim_by_id"]["t-0000002"]["status"], "FILLED")
        self.assertNotEqual(zero_latency["sim_by_id"]["t-0000002"]["status"],
                             high_latency["sim_by_id"]["t-0000002"]["status"])


@unittest.skipUnless(_pinned_runtime_active(), "requires the pinned nautilus_trader==2.0.0rc5 runtime")
class MainReplayNoCredentialTests(unittest.TestCase):
    """--replay must never open or require a credential file (M3)."""

    def test_main_replay_runs_with_no_env_file_argument_at_all(self):
        pages = ROOT / "blueprints/us-equities/sim-paper-compare"  # any dir; unused because --replay needs no fetch
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        real_pages = Path.home() / ".local/state/native-agent-stack/sim-paper/pages"
        if not real_pages.exists():
            self.skipTest("retained page cache not present on this host")
        argv = ["--trial", str(TRIAL), "--pages", str(real_pages), "--out", str(tmp / "out"),
                "--replay", "--receipt", str(tmp / "receipt.json")]
        # No --env-file / --env-file-from-file anywhere in argv, and no PAPER_ENV_FILE
        # env var read by this call: if main() tried to open a credential file it
        # would raise SystemExit before writing the receipt.
        rc = C.main(argv)
        self.assertEqual(rc, 0)
        self.assertTrue((tmp / "receipt.json").exists())


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
