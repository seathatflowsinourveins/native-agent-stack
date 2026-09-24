"""Synthetic tests for the extreme-gainer price audit: made-up tickers, dates and prices; no network, credentials or package rows."""
import csv
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("gainer_audit", ROOT / "blueprints/us-equities/extreme-gainer-audit/audit.py")
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)


def bar(day, close):
    return {"t": f"{day}T05:00:00Z", "o": close, "h": close, "l": close, "c": close, "v": 1}


def auction(day, closes, opens=({"c": "O", "p": 1, "x": "Q"},)):
    return {"d": day, "c": list(closes), "o": list(opens)}


class OfficialClose(unittest.TestCase):
    def test_closing_print_wins_over_other_venues_official_close(self):
        day = auction("2020-02-03", [{"c": "M", "p": 4.12, "x": "P"}, {"c": "6", "p": 4.10, "x": "Q"}, {"c": "M", "p": 4.10, "x": "Q"}])
        self.assertEqual(A.official_close(day, 4.2), (4.10, "closing_print"))

    def test_listing_exchange_official_close_then_bar_fallback(self):
        day = auction("2020-02-03", [{"c": "M", "p": 4.12, "x": "P"}, {"c": "M", "p": 4.10, "x": "Q"}])
        self.assertEqual(A.official_close(day, 4.2), (4.10, "official_close_listing_exchange"))
        self.assertEqual(A.official_close({"d": "x", "c": None, "o": []}, 0.7702), (0.7702, "bar_close_fallback"))
        self.assertEqual(A.official_close(None, None), (None, None))


class OfficialCloseV2(unittest.TestCase):
    def test_listing_exchange_print_and_largest_size_win(self):
        day = {"d": "2020-02-03", "o": [{"c": "O", "p": 3.0, "x": "T"}],
               "c": [{"c": "6", "p": 3.90, "x": "P", "s": 400}, {"c": "6", "p": 3.97, "x": "T", "s": 17000}, {"c": "6", "p": 3.99, "x": "T", "s": 300}]}
        self.assertEqual(A.official_close(day, 3.95), (3.90, "closing_print"))  # v1: first print, any exchange
        self.assertEqual(A.official_close(day, 3.95, "v2"), (3.97, "closing_print_listing_exchange"))

    def test_other_exchange_print_is_flagged_and_bar_is_last(self):
        day = {"d": "2020-02-03", "o": [{"c": "O", "p": 3.0, "x": "T"}], "c": [{"c": "6", "p": 3.90, "x": "P", "s": 400}]}
        self.assertEqual(A.official_close(day, 3.95, "v2"), (3.90, "closing_print_other_exchange"))
        self.assertEqual(A.official_close({"d": "x", "o": [], "c": None}, 3.95, "v2"), (3.95, "bar_close_fallback"))

    def test_split_tolerance_ignores_adjustment_rounding(self):
        raw = A.by_date([bar("2020-02-07", 2.0), bar("2020-02-10", 3.0)])
        split = A.by_date([bar("2020-02-07", 2.0008), bar("2020-02-10", 3.0)])  # 4e-4 rounding in the adjusted series
        self.assertTrue(A.event_gain("2020-02-10", {}, raw, split)["split_between"])
        self.assertFalse(A.event_gain("2020-02-10", {}, raw, split, "v2")["split_between"])

    def test_status_ok_without_computed_gain_is_not_recovered_under_v2(self):
        ev = {"status": "OK", "computed_gain": None, "dataset_gain": 50.0}
        self.assertEqual(A.verdict_for(ev, {"gain_pct": 50.1})[0], "recovered_match")
        self.assertEqual(A.verdict_for(ev, {"gain_pct": 50.1}, "v2")[0], "package_uncomputed_match")

    def test_original_ticker_is_tried_before_the_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp); (pkg / "datasets").mkdir()
            (pkg / A.FORWARD_CSV).write_text("Date,Ticker,Ticker_Used,Status,Computed_Gain_Pct,Gain_Pct_Dataset\n2020-03-02,DDDD,EEEE,NO_DATA,,90\n")
            (pkg / A.ALIAS_CSV).write_text("Date,Ticker,Outcome_Type,Alias_Symbol\n2020-03-02,DDDD,renamed,FFFF\n")
            self.assertEqual(A.load_events(pkg)[0]["symbols"], ["EEEE", "DDDD", "FFFF"])


class HardeningV2(unittest.TestCase):
    def test_forward_returns_use_the_market_calendar_and_report_a_missing_session(self):
        days = ["2020-03-02", "2020-03-03", "2020-03-04", "2020-03-05", "2020-03-06", "2020-03-09", "2020-03-10"]
        split = A.by_date([bar(d, 10 + i) for i, d in enumerate(days) if d != "2020-03-03"])  # halted on 03-03
        v1 = A.forward_returns("2020-03-02", split)
        self.assertEqual(v1[1]["date"], "2020-03-04")  # v1 shifts past the halt
        v2 = A.forward_returns("2020-03-02", split, days)
        self.assertEqual(v2[1], {"date": "2020-03-03", "missing_session_bar": True})
        self.assertEqual((v2[5]["date"], v2[5]["ret_pct"]), ("2020-03-09", 50.0))

    def test_private_outputs_are_created_owner_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.json"
            path.write_text("old")
            path.chmod(0o644)
            A.write_private(path, "new")
            self.assertEqual((path.read_text(), path.stat().st_mode & 0o777), ("new", 0o600))

    def test_repeated_page_token_is_refused(self):
        client = A.Client("k", "s", per_second=1000)
        pages = iter([{"bars": [1], "next_page_token": "t1"}, {"bars": [2], "next_page_token": "t1"}])

        class Resp:
            status = 200
            def __init__(self, body): self.body = body
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps(self.body).encode()

        original = A.urllib.request.urlopen
        A.urllib.request.urlopen = lambda req, timeout=30: Resp(next(pages))
        original_load = A.json.load
        A.json.load = lambda r: json.loads(r.read())
        try:
            with self.assertRaises(RuntimeError):
                client.get("/v2/stocks/AAAA/bars")
        finally:
            A.urllib.request.urlopen, A.json.load = original, original_load


class EventGain(unittest.TestCase):
    def test_gain_from_official_closes_and_previous_trading_day(self):
        auctions = A.by_date([auction("2020-02-07", [{"c": "6", "p": 2.00, "x": "T"}]), auction("2020-02-10", [{"c": "6", "p": 6.40, "x": "T"}])])
        raw = A.by_date([bar("2020-02-07", 2.00), bar("2020-02-10", 6.40)])
        r = A.event_gain("2020-02-10", auctions, raw, raw)
        self.assertEqual((r["gain_pct"], r["prev_date"], r["split_between"]), (220.0, "2020-02-07", False))
        self.assertEqual(r["event_bar_vs_official_pct"], 0.0)

    def test_reverse_split_between_the_two_closes_uses_adjusted_prices(self):
        # A 1-for-10 reverse split effective on the event date: raw 0.50 -> 7.50 is +1400%,
        # but split-adjusted it is 5.00 -> 7.50, +50%.
        raw = A.by_date([bar("2024-03-01", 0.50), bar("2024-03-04", 7.50)])
        split = A.by_date([bar("2024-03-01", 5.00), bar("2024-03-04", 7.50)])
        r = A.event_gain("2024-03-04", {}, raw, split)
        self.assertTrue(r["split_between"])
        self.assertAlmostEqual(r["gain_pct"], 50.0)

    def test_no_event_close_or_no_previous_close(self):
        self.assertEqual(A.event_gain("2024-03-04", {}, {}, {}), {"reason": "no_source_data"})
        raw = A.by_date([bar("2024-03-04", 7.5)])
        self.assertEqual(A.event_gain("2024-03-04", {}, raw, raw), {"reason": "no_prev_close"})


class ForwardAndVerdicts(unittest.TestCase):
    def test_forward_returns_count_trading_days(self):
        days = [f"2024-03-{d:02d}" for d in (4, 5, 6, 7, 8, 11, 12)]
        split = A.by_date([bar(d, 10 + i) for i, d in enumerate(days)])
        fr = A.forward_returns("2024-03-04", split)
        self.assertEqual((fr[1]["date"], fr[1]["ret_pct"]), ("2024-03-05", 10.0))
        self.assertEqual((fr[5]["date"], fr[5]["ret_pct"]), ("2024-03-11", 50.0))
        self.assertNotIn(20, fr)

    def test_tolerance_and_verdict_fields(self):
        tol = {"abs_pct_points": 0.5, "rel_fraction": 0.005}
        self.assertTrue(A.agrees(220.49, 220.0, tol))  # 0.49 pp
        self.assertTrue(A.agrees(1204.0, 1200.0, tol))  # 4 pp but within 0.5% of 1200
        self.assertFalse(A.agrees(221.2, 220.0, tol))
        ok = {"status": "OK", "computed_gain": 180.5, "dataset_gain": 180.5}
        self.assertEqual(A.verdict_for(ok, {"gain_pct": 180.4611})[0], "match")
        nodata = {"status": "NO_DATA", "computed_gain": None, "dataset_gain": 140.0}
        self.assertEqual(A.verdict_for(nodata, {"gain_pct": 140.0312}), ("recovered_match", 140.0, "Gain_Pct_Dataset"))
        self.assertEqual(A.verdict_for(nodata, {"gain_pct": 100.0})[0], "recovered_mismatch")
        self.assertEqual(A.verdict_for(ok, {"reason": "no_prev_close"})[0], "no_prev_close")


class CompareEndToEnd(unittest.TestCase):
    """compare() on a synthetic package and snapshot (made-up tickers and prices); the plan's
    input-hash check is patched so the rule logic, alias fallback and determinism are exercised."""

    def _package(self, tmp):
        pkg = Path(tmp) / "pkg"; (pkg / "datasets").mkdir(parents=True)
        fields = ["Date", "Ticker", "Ticker_Used", "Status", "Computed_Gain_Pct", "Gain_Pct_Dataset", "Ret_T1_Pct", "Ret_T5_Pct", "Ret_T20_Pct"]
        with (pkg / A.FORWARD_CSV).open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
            w.writerow({"Date": "2020-02-10", "Ticker": "AAAA", "Ticker_Used": "AAAA", "Status": "OK", "Computed_Gain_Pct": "220.0", "Gain_Pct_Dataset": "220.0", "Ret_T1_Pct": "-5.0"})
            w.writerow({"Date": "2020-03-02", "Ticker": "BBBB", "Ticker_Used": "", "Status": "NO_DATA", "Gain_Pct_Dataset": "150.0"})
        with (pkg / A.ALIAS_CSV).open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["Date", "Ticker", "Outcome_Type", "Alias_Symbol"]); w.writeheader()
            w.writerow({"Date": "2020-03-02", "Ticker": "BBBB", "Outcome_Type": "renamed", "Alias_Symbol": "CCCC"})
        return pkg

    def _snapshot(self, tmp, events):
        empty = {"auctions": {"auctions": []}, "bars_raw": {"bars": []}, "bars_split": {"bars": []}}
        aaaa = {"symbol": "AAAA", "auctions": {"auctions": [auction("2020-02-07", [{"c": "6", "p": 2.00, "x": "T"}]), auction("2020-02-10", [{"c": "6", "p": 6.40, "x": "T"}])]},
                "bars_raw": {"bars": [bar("2020-02-07", 2.00), bar("2020-02-10", 6.40), bar("2020-02-11", 6.08)]},
                "bars_split": {"bars": [bar("2020-02-07", 2.00), bar("2020-02-10", 6.40), bar("2020-02-11", 6.08)]}}
        cccc = {"symbol": "CCCC", "auctions": {"auctions": [auction("2020-03-02", [{"c": "6", "p": 2.50, "x": "A"}])]},
                "bars_raw": {"bars": [bar("2020-02-28", 1.00), bar("2020-03-02", 2.50)]},
                "bars_split": {"bars": [bar("2020-02-28", 1.00), bar("2020-03-02", 2.50)]}}
        snap = Path(tmp) / "snapshot.json"
        snap.write_text(json.dumps({"plan_sha256": A.sha256_file(A.HERE / "plan.json"), "fetched_at_utc": "2026-09-24T03:10:00Z",
                                    "events": {events[0]["id"]: [aaaa], events[1]["id"]: [dict(empty, symbol="BBBB"), cccc]}}))
        return snap

    def test_compare_is_deterministic_and_uses_the_alias_when_the_ticker_has_no_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = self._package(tmp)
            events = A.load_events(pkg)
            self.assertEqual(events[1]["symbols"], ["BBBB", "CCCC"])
            snap = self._snapshot(tmp, events)
            original = A.check_inputs
            A.check_inputs = lambda d: None
            try:
                outs = []
                for name in ("a.json", "b.json"):
                    A.compare(SimpleNamespace(snapshot=snap, package_dir=pkg, out=Path(tmp) / name))
                    outs.append((Path(tmp) / name).read_bytes())
                A.compare(SimpleNamespace(snapshot=snap, package_dir=pkg, out=Path(tmp) / "v2.json", rules="v2", supplement=None))
            finally:
                A.check_inputs = original
            self.assertEqual(hashlib.sha256(outs[0]).hexdigest(), hashlib.sha256(outs[1]).hexdigest())
            r = json.loads(outs[0])
            self.assertEqual(r["summary"]["verdicts"], {"match": 1, "recovered_match": 1})
            self.assertEqual([e["symbol_used"] for e in r["events"]], ["AAAA", "CCCC"])
            self.assertEqual(r["events"][0]["forward"]["T1"]["match"], True)
            self.assertNotIn("rules", r)  # v1 output keeps the preregistered run's exact shape
            self.assertEqual(json.loads((Path(tmp) / "v2.json").read_text())["rules"], "v2")
            self.assertNotIn("6.4", json.dumps(r["events"]))  # no raw prices in the results

    def test_posthoc_separates_basis_difference_from_real_mismatch(self):
        sys_path = str(A.HERE)
        import sys
        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)
        spec = importlib.util.spec_from_file_location("gainer_posthoc", A.HERE / "posthoc.py")
        sys.modules["audit"] = A
        P = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(P)
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"; (pkg / "datasets").mkdir(parents=True)
            fields = ["Date", "Ticker", "Ticker_Used", "Status", "Prev_Close", "Ev_Close", "Computed_Gain_Pct", "Gain_Pct_Dataset",
                      "Ret_T1_Pct", "Ret_T5_Pct", "Ret_T20_Pct", "Discrepancy_Flag"]
            with (pkg / A.FORWARD_CSV).open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
                # Package close 2.10 is the after-hours last trade; the official close is 2.00.
                w.writerow({"Date": "2024-05-02", "Ticker": "AAA", "Ticker_Used": "AAA", "Status": "OK", "Prev_Close": "1.00",
                            "Ev_Close": "2.10", "Computed_Gain_Pct": "110.0", "Gain_Pct_Dataset": "110.0"})
            (pkg / A.ALIAS_CSV).write_text("Date,Ticker,Outcome_Type,Alias_Symbol\n")
            ev = A.load_events(pkg)[0]
            resp = {"symbol": "AAA", "auctions": {"auctions": [auction("2024-05-01", [{"c": "6", "p": 1.00, "x": "Q"}]),
                                                               auction("2024-05-02", [{"c": "6", "p": 2.00, "x": "Q"}])]},
                    "bars_raw": {"bars": [bar("2024-05-01", 1.00), bar("2024-05-02", 2.10)]},
                    "bars_split": {"bars": [bar("2024-05-01", 1.00), bar("2024-05-02", 2.10)]}}
            snap = Path(tmp) / "snapshot.json"
            snap.write_text(json.dumps({"plan_sha256": A.sha256_file(A.HERE / "plan.json"), "fetched_at_utc": "x",
                                        "events": {ev["id"]: [resp]}}))
            original = A.check_inputs
            A.check_inputs = lambda d: None
            try:
                A.compare(SimpleNamespace(snapshot=snap, package_dir=pkg, out=Path(tmp) / "r.json"))
                P.main(["--snapshot", str(snap), "--package-dir", str(pkg), "--results", str(Path(tmp) / "r.json"),
                        "--out", str(Path(tmp) / "p.json")])
            finally:
                A.check_inputs = original
            r = json.loads((Path(tmp) / "r.json").read_text()); p = json.loads((Path(tmp) / "p.json").read_text())
            self.assertEqual(r["summary"]["verdicts"], {"mismatch": 1})  # official close says +100%
            self.assertEqual((p["agree_official_close_gain"], p["agree_bar_close_gain"], p["agree_bar_only"]), (0, 1, 1))
            self.assertEqual(p["mismatch_leg_classes"], {"closes_match_bar_not_official": 1})
            self.assertFalse(p["preregistered"])

    def test_inputs_are_checked_against_the_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp); (pkg / "datasets").mkdir()
            (pkg / A.FORWARD_CSV).write_text("Date\n"); (pkg / A.ALIAS_CSV).write_text("Date\n")
            with self.assertRaises(SystemExit):
                A.check_inputs(pkg)


if __name__ == "__main__":
    unittest.main()
