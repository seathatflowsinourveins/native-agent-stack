"""Synthetic tests for the extreme-gainer price audit; no network, credentials or package files."""
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
        day = auction("2025-04-16", [{"c": "M", "p": 9.41, "x": "P"}, {"c": "6", "p": 9.39, "x": "Q"}, {"c": "M", "p": 9.39, "x": "Q"}])
        self.assertEqual(A.official_close(day, 9.5), (9.39, "closing_print"))

    def test_listing_exchange_official_close_then_bar_fallback(self):
        day = auction("2025-04-16", [{"c": "M", "p": 9.41, "x": "P"}, {"c": "M", "p": 9.39, "x": "Q"}])
        self.assertEqual(A.official_close(day, 9.5), (9.39, "official_close_listing_exchange"))
        self.assertEqual(A.official_close({"d": "x", "c": None, "o": []}, 0.5305), (0.5305, "bar_close_fallback"))
        self.assertEqual(A.official_close(None, None), (None, None))


class EventGain(unittest.TestCase):
    def test_gain_from_official_closes_and_previous_trading_day(self):
        auctions = A.by_date([auction("2021-01-15", [{"c": "6", "p": 5.88, "x": "T"}]), auction("2021-01-19", [{"c": "6", "p": 18.83, "x": "T"}])])
        raw = A.by_date([bar("2021-01-15", 5.88), bar("2021-01-19", 18.83)])
        r = A.event_gain("2021-01-19", auctions, raw, raw)
        self.assertEqual((r["gain_pct"], r["prev_date"], r["split_between"]), (220.2381, "2021-01-15", False))
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
        ok = {"status": "OK", "computed_gain": 220.24, "dataset_gain": 220.24}
        self.assertEqual(A.verdict_for(ok, {"gain_pct": 220.2381})[0], "match")
        nodata = {"status": "NO_DATA", "computed_gain": None, "dataset_gain": 167.67}
        self.assertEqual(A.verdict_for(nodata, {"gain_pct": 167.6719}), ("recovered_match", 167.67, "Gain_Pct_Dataset"))
        self.assertEqual(A.verdict_for(nodata, {"gain_pct": 120.0})[0], "recovered_mismatch")
        self.assertEqual(A.verdict_for(ok, {"reason": "no_prev_close"})[0], "no_prev_close")


class CompareEndToEnd(unittest.TestCase):
    """compare() on a synthetic package and snapshot; the plan's input-hash check is patched to
    the synthetic files so the rule logic, alias fallback and determinism are exercised."""

    def test_compare_is_deterministic_and_uses_the_alias_when_the_ticker_has_no_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"; (pkg / "datasets").mkdir(parents=True)
            fields = ["Date", "Ticker", "Ticker_Used", "Status", "Computed_Gain_Pct", "Gain_Pct_Dataset", "Ret_T1_Pct", "Ret_T5_Pct", "Ret_T20_Pct"]
            with (pkg / A.FORWARD_CSV).open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
                w.writerow({"Date": "2021-01-19", "Ticker": "ACRS", "Ticker_Used": "ACRS", "Status": "OK", "Computed_Gain_Pct": "220.24", "Gain_Pct_Dataset": "220.24", "Ret_T1_Pct": "-4.57"})
                w.writerow({"Date": "2021-01-06", "Ticker": "ISR", "Ticker_Used": "", "Status": "NO_DATA", "Gain_Pct_Dataset": "167.67"})
            with (pkg / A.ALIAS_CSV).open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["Date", "Ticker", "Outcome_Type", "Alias_Symbol"]); w.writeheader()
                w.writerow({"Date": "2021-01-06", "Ticker": "ISR", "Outcome_Type": "renamed", "Alias_Symbol": "CATX"})
            events = A.load_events(pkg)
            self.assertEqual(events[1]["symbols"], ["ISR", "CATX"])
            empty = {"auctions": {"auctions": []}, "bars_raw": {"bars": []}, "bars_split": {"bars": []}}
            acrs = {"symbol": "ACRS", "auctions": {"auctions": [auction("2021-01-15", [{"c": "6", "p": 5.88, "x": "T"}]), auction("2021-01-19", [{"c": "6", "p": 18.83, "x": "T"}])]},
                    "bars_raw": {"bars": [bar("2021-01-15", 5.88), bar("2021-01-19", 18.83), bar("2021-01-20", 17.97)]},
                    "bars_split": {"bars": [bar("2021-01-15", 5.88), bar("2021-01-19", 18.83), bar("2021-01-20", 17.97)]}}
            catx = {"symbol": "CATX", "auctions": {"auctions": [auction("2021-01-06", [{"c": "6", "p": 1.42, "x": "A"}])]},
                    "bars_raw": {"bars": [bar("2021-01-05", 0.5305), bar("2021-01-06", 1.42)]},
                    "bars_split": {"bars": [bar("2021-01-05", 0.5305), bar("2021-01-06", 1.42)]}}
            snap = Path(tmp) / "snapshot.json"
            snap.write_text(json.dumps({"plan_sha256": A.sha256_file(A.HERE / "plan.json"), "fetched_at_utc": "2026-09-24T03:10:00Z",
                                        "events": {events[0]["id"]: [acrs], events[1]["id"]: [dict(empty, symbol="ISR"), catx]}}))
            original = A.check_inputs
            A.check_inputs = lambda d: None
            try:
                outs = []
                for name in ("a.json", "b.json"):
                    A.compare(SimpleNamespace(snapshot=snap, package_dir=pkg, out=Path(tmp) / name))
                    outs.append((Path(tmp) / name).read_bytes())
            finally:
                A.check_inputs = original
            self.assertEqual(hashlib.sha256(outs[0]).hexdigest(), hashlib.sha256(outs[1]).hexdigest())
            r = json.loads(outs[0])
            self.assertEqual(r["summary"]["verdicts"], {"match": 1, "recovered_match": 1})
            self.assertEqual([e["symbol_used"] for e in r["events"]], ["ACRS", "CATX"])
            self.assertEqual(r["events"][0]["forward"]["T1"]["match"], True)
            self.assertFalse(r["summary"]["overturn_triggered"])
            self.assertNotIn("18.83", json.dumps(r["events"]))  # no raw prices in the committed results

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
