"""Synthetic tests for the mover coverage as-of re-fetch (blueprints/us-equities/mover-coverage-asof).

Made-up tickers, dates and prices only: no network, credentials or private rows. Tests that need the
tiering in mover-early-entry rules.py (numpy) are skipped without numpy, like the other mover tests.
"""
import contextlib
import csv
import gzip
import hashlib
import importlib.util
import json
import os
import stat
import tempfile
import types
import unittest
import urllib.error
import urllib.parse
import zipfile
from datetime import datetime
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "blueprints/us-equities/mover-coverage-asof"
HAS_NUMPY = importlib.util.find_spec("numpy") is not None
SPEC = importlib.util.spec_from_file_location("mover_coverage_asof", HERE / "refetch.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
A = M.audit
ET = ZoneInfo("America/New_York")

D, L = "2023-03-15", "2023-03-14"  # a Wednesday session and the session before it


def bar(day, o, h, l, c, v=1000):  # noqa: E741
    return {"t": f"{day}T04:00:00Z", "o": o, "h": h, "l": l, "c": c, "v": v, "n": 7, "vw": c}


def page(key, rows, token=None, symbol="ZZQA"):
    return json.dumps({key: rows, "symbol": symbol, "next_page_token": token})


def ok(key, rows):
    return {"pages": [page(key, rows)]}


def auction(day, closes=(), opens=({"c": "O", "p": 1, "x": "Q", "s": 100},)):
    return {"d": day, "o": list(opens), "c": list(closes)}


def legs(all_rows=None, raw_rows=None, split_rows=None, auctions=None, **errors):
    """F1 legs; raw and split default to the all-adjusted rows (no split), auctions to none."""
    all_rows = all_rows if all_rows is not None else []
    out = {"bars_all": ok("bars", all_rows),
           "bars_raw": ok("bars", raw_rows if raw_rows is not None else all_rows),
           "bars_split": ok("bars", split_rows if split_rows is not None else all_rows),
           "auctions": ok("auctions", auctions or [])}
    for name, code in errors.items():
        out[name] = {"error": code}
    return out


def mover(prev_low=10.0, high=13.0):
    """A lag row and an event row whose all-adjusted high clears 1.2 x the lag low."""
    return [bar(L, 10.0, 10.5, prev_low, 10.2), bar(D, 10.5, high, 10.4, 12.9)]


class FakeResponse:
    def __init__(self, text, status=200):
        self.text, self.status = text, status

    def read(self, *args):
        return self.text.encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeHTTP:
    """Scripted urlopen: ("ok", text) returns a page, ("http", code) raises HTTPError, ("net", _) URLError."""

    def __init__(self, script):
        self.script, self.urls = list(script), []

    def __call__(self, req, timeout=30):
        self.urls.append(req.full_url)
        kind, payload = self.script.pop(0)
        if kind == "http":
            raise urllib.error.HTTPError(req.full_url, payload, "synthetic", {}, None)
        if kind == "net":
            raise urllib.error.URLError("synthetic outage")
        return FakeResponse(payload)


def forbid_network(*args, **kwargs):
    raise AssertionError("a request was sent")


def forbid_subprocess(*args, **kwargs):
    raise AssertionError("a child process was started")


class CredentialRead(Exception):
    """Raised by the patched audit.credentials: a credential file was about to be read."""


class PlanFreeze(unittest.TestCase):
    def test_runner_pins_the_plan_it_started_with(self):
        raw = (HERE / "plan.json").read_bytes()
        self.assertEqual(M.PLAN_SHA256, hashlib.sha256(raw).hexdigest())
        self.assertTrue(M.PLAN["frozen_before_first_fetch"])
        M.plan_guard()
        with mock.patch.object(M, "PLAN_SHA256", "0" * 64):
            with self.assertRaises(M.Refused):
                M.plan_guard()

    def test_constants_restate_the_plan_text(self):
        req = M.PLAN["requests"]
        self.assertIn("asof=2026-09-21", req["F2_today_symbol_leg"]["bars"])
        self.assertEqual(M.NAMING_ASOF, "2026-09-21")
        self.assertIn("60 sessions before d", req["F1_event_leg"]["bars"])
        self.assertIn("5 sessions after d and 2025-12-31", req["F1_event_leg"]["bars"])
        self.assertIn("22 sessions before d", req["F1_event_leg"]["auctions"])
        self.assertEqual((M.LOOKBACK, M.AUCTION_LOOKBACK, M.FORWARD), (60, 22, 5))
        self.assertIn("KOD and LFCR", req["positive_control"])
        self.assertEqual(M.CONTROL_SYMBOLS, ("KOD", "LFCR"))
        self.assertIn("2026-01-02..2026-09-18", M.PLAN["guards"]["holdout"])
        self.assertEqual(M.HOLDOUT, ("2026-01-02", "2026-09-18"))
        self.assertEqual([name for name, _ in M.RATIOS], M.PLAN["labels"]["ratios"])
        self.assertEqual([c["id"] for c in M.PLAN["reason_classes"]["order"]], list(M.CLASS_ORDER))


class Requests(unittest.TestCase):
    def setUp(self):
        self.cal = M.Calendar.load()

    def test_calendar_offsets_and_non_sessions(self):
        self.assertEqual(self.cal.offset(D, -1), L)
        self.assertEqual(self.cal.offset("2023-03-17", 1), "2023-03-20")
        with self.assertRaises(ValueError):
            self.cal.offset("2023-03-18", -1)  # a Saturday

    def test_f1_f2_and_control_parameters(self):
        specs = {s["leg"]: s for s in M.f1_specs("ZZQA", D, self.cal)}
        self.assertEqual(list(specs), ["bars_raw", "bars_split", "bars_all", "auctions"])
        start, end = self.cal.offset(D, -60), self.cal.offset(D, 5)
        for adj in ("raw", "split", "all"):
            s = specs[f"bars_{adj}"]
            self.assertEqual(s["path"], "/v2/stocks/ZZQA/bars")
            self.assertEqual(s["params"], {"timeframe": "1Day", "adjustment": adj, "asof": D, "feed": "sip",
                                           "start": start, "end": end, "limit": 10000})
        self.assertEqual(specs["auctions"]["path"], "/v2/stocks/ZZQA/auctions")
        self.assertEqual(specs["auctions"]["params"], {"asof": D, "feed": "sip", "start": self.cal.offset(D, -22), "end": D})
        f2 = M.f2_spec("ZZQA", D, self.cal)
        self.assertEqual(f2["params"], {"timeframe": "1Day", "adjustment": "raw", "asof": "2026-09-21", "feed": "sip",
                                        "start": L, "end": D})
        control = {s["leg"]: s["params"] for s in M.control_specs("KOD")}
        self.assertEqual(control["bars_all"]["start"], "2026-09-21")
        self.assertEqual(control["bars_all"]["end"], "2026-09-28")
        self.assertEqual(control["auctions"], {"asof": "2026-09-28", "feed": "sip", "start": "2026-09-21", "end": "2026-09-28"})

    def test_event_legs_stop_at_the_window_and_the_holdout_is_refused(self):
        late = {s["leg"]: s for s in M.f1_specs("ZZQA", "2025-12-26", self.cal)}
        self.assertEqual(late["bars_all"]["params"]["end"], "2025-12-31")  # d+5 is 2026-01-05
        M.check_holdout(M.f1_specs("ZZQA", "2025-12-26", self.cal) + [M.f2_spec("ZZQA", "2025-12-26", self.cal)])
        M.check_holdout(M.control_specs("LFCR"))
        crossing = dict(late["bars_all"], params=dict(late["bars_all"]["params"], end="2026-01-02"))
        with self.assertRaises(M.Refused):
            M.check_holdout([crossing])
        inside = dict(late["auctions"], params=dict(late["auctions"]["params"], start="2026-05-01", end="2026-05-01"))
        with self.assertRaises(M.Refused):
            M.check_holdout([inside])
        with self.assertRaises(M.Refused):
            M.check_holdout([{"leg": "x", "path": "/v2/account", "params": {"start": "2021-01-04", "end": "2021-01-05"}}])

    def test_control_is_not_sent_before_2000_et(self):
        self.assertFalse(M.control_time_ok(datetime(2026, 9, 28, 19, 59, tzinfo=ET)))
        self.assertTrue(M.control_time_ok(datetime(2026, 9, 28, 20, 0, tzinfo=ET)))


class Transport(unittest.TestCase):
    PATH = "/v2/stocks/ZZQA/bars"
    PARAMS = {"timeframe": "1Day", "adjustment": "raw", "asof": D, "feed": "sip", "start": L, "end": D, "limit": 10000}

    def run_client(self, cls, script):
        fake = FakeHTTP(script)
        with mock.patch("urllib.request.urlopen", fake), mock.patch("time.sleep") as sleep:
            client = cls("synthetic-key", "synthetic-secret")
            result = client.get(self.PATH, **self.PARAMS)
        return result, fake.urls, sleep, client

    def test_same_requests_as_audit_client_and_raw_text_kept(self):
        first = page("bars", [bar(L, 1.1, 1.2, 1.0, 1.15)], token="T1")
        second = '{"bars": [{"t": "2023-03-15T04:00:00Z", "o": 1.10, "h": 1.50, "l": 1.05, "c": 1.40, "v": 5}], "next_page_token": null}'
        script = [("http", 429), ("http", 429), ("ok", first), ("ok", second)]
        a_result, a_urls, a_sleep, _ = self.run_client(A.Client, script)
        t_result, t_urls, t_sleep, client = self.run_client(M.TextClient, script)
        self.assertEqual(a_urls, t_urls)
        self.assertEqual(t_result, {"pages": [first, second]})
        status, rows = M.leg_rows(t_result, "bars")
        self.assertEqual(status, "ok")
        self.assertEqual(rows[1]["o"], Decimal("1.10"))
        self.assertEqual(str(rows[1]["h"]), "1.50")  # the provider's decimal text survives
        self.assertEqual(M.as_float(rows), a_result["bars"])
        retry = lambda s: [c.args[0] for c in s.call_args_list if c.args and c.args[0] in (1, 2, 4)]  # noqa: E731
        self.assertEqual(retry(a_sleep), retry(t_sleep))
        self.assertEqual([e["status"] for e in client.log], [429, 429, 200, 200])

    def test_failures_become_error_records(self):
        cases = [([("http", 503)], {"error": 503}, 1), ([("http", 404)], {"error": 404}, 1),
                 ([("net", None)], {"error": "network:URLError"}, 1),
                 ([("http", 429)] * 4, {"error": 429}, 4)]
        for script, want, calls in cases:
            result, urls, _, _ = self.run_client(M.TextClient, script)
            self.assertEqual(result, want)
            self.assertEqual(len(urls), calls)
        with self.assertRaises(urllib.error.HTTPError):  # the audit client raises where the wrapper records
            self.run_client(A.Client, [("http", 503)])

    def test_repeated_page_token_is_an_error_not_a_loop(self):
        script = [("ok", page("bars", [], token="T")), ("ok", page("bars", [], token="T"))]
        result, urls, _, _ = self.run_client(M.TextClient, script)
        self.assertEqual(result, {"error": "pagination_not_terminated"})
        self.assertEqual(len(urls), 2)

    def test_unparseable_body_is_an_error(self):
        result, _, _, _ = self.run_client(M.TextClient, [("ok", "not json")])
        self.assertEqual(result, {"error": "invalid_json"})

    def test_leg_rows_status(self):
        self.assertEqual(M.leg_rows({"error": 503}, "bars"), ("error", []))
        self.assertEqual(M.leg_rows(None, "bars"), ("missing", []))
        self.assertEqual(M.leg_rows(ok("bars", []), "bars"), ("ok", []))


class CandidateRule(unittest.TestCase):
    def test_touch_is_ieee_double_like_the_sql(self):
        # 1.632 = 1.2 x 1.36 exactly in decimal, but the double product rounds above the double 1.632
        self.assertFalse(M.touch(Decimal("1.632"), Decimal("1.36")))
        self.assertTrue(M.touch(Decimal("1.6321"), Decimal("1.36")))
        self.assertTrue(M.touch(6, 5))
        self.assertFalse(M.touch(1, 0))

    def test_derivative_pattern(self):
        for sym in ("ZZQAW", "ZZQAU", "ZZQAR", "ZZQ.WS", "ZZQ.U", "ZZQ.R", "ZZQ.W"):
            self.assertTrue(M.derivative(sym), sym)
        for sym in ("ZZQA", "ZZQAB", "ZZQW", "BRK.B", "ZZQAWX"):
            self.assertFalse(M.derivative(sym), sym)


class ReasonTree(unittest.TestCase):
    def setUp(self):
        self.cal = M.Calendar.load()
        self.same_f2 = ok("bars", [bar(L, 10.0, 10.5, 10.0, 10.2), bar(D, 10.5, 13.0, 10.4, 12.9)])

    def assess(self, legs_, symbol="ZZQA", f2=None, **kw):
        return M.assess(symbol, D, legs_, self.same_f2 if f2 is None else f2, self.cal, **kw)

    def test_pre_touch_classes_in_order(self):
        self.assertEqual(self.assess(legs(mover(), bars_all=503))["failure_class"], "fetch_error")
        self.assertEqual(self.assess(legs([bar(L, 1, 1, 1, 1)]))["failure_class"], "no_asof_event_row")
        r = self.assess(legs([bar(D, 1, 2, 1, 2)]), symbol="ZZQAW")
        self.assertEqual(r["failure_class"], "derivative_pattern")  # before no_prior_row
        self.assertEqual(self.assess(legs([bar(D, 1, 2, 1, 2)]))["failure_class"], "no_prior_row")

    def test_below_touch_classes(self):
        flat = [bar(L, 10, 10.5, 10, 10.2), bar(D, 10.2, 11.0, 10.1, 10.8)]
        split_raw = [bar(L, 20, 21, 20, 20.4), bar(D, 10.2, 11.0, 10.1, 10.8)]
        r = self.assess(legs(flat, raw_rows=split_raw, split_rows=flat))
        self.assertEqual((r["touch"], r["failure_class"]), (False, "below_touch_split_basis"))
        outside = [auction(L, closes=[{"c": "6", "p": 9.5, "x": "Q", "s": 500}])]
        r = self.assess(legs(flat, auctions=outside))
        self.assertEqual(r["failure_class"], "below_touch_auction_outside_bar_range")
        inside = [auction(L, closes=[{"c": "6", "p": 10.2, "x": "Q", "s": 500}])]
        self.assertEqual(self.assess(legs(flat, auctions=inside))["failure_class"], "below_touch_other")
        r = self.assess(legs(flat, bars_raw=503))
        self.assertEqual(r["failure_class"], "below_touch_other")
        self.assertTrue(r["flags"]["leg_error"])

    def test_recovered_classes_in_order(self):
        renames = [("ZZQOLD", "ZZQA", D)]
        r = self.assess(legs(mover()), renames=renames, candidate_keys=set())
        self.assertEqual((r["touch"], r["recovered_class"]), (True, "recovered_rename_on_event_date"))
        chain = [("ZZQA", "ZZQB", "2024-01-10"), ("ZZQB", "ZZQC", "2025-06-02")]
        r = self.assess(legs(mover()), renames=chain, candidate_keys={("ZZQC", D)})
        self.assertEqual(r["recovered_class"], "recovered_keyed_under_successor")
        too_late = [("ZZQA", "ZZQB", "2026-09-22")]
        r = self.assess(legs(mover()), renames=too_late, candidate_keys={("ZZQB", D)})
        self.assertEqual(r["recovered_class"], "recovered_today_symbol_same_issuer")
        other = ok("bars", [bar(D, 55, 56, 54, 55.5, v=9)])
        self.assertEqual(self.assess(legs(mover()), f2=other)["recovered_class"], "recovered_today_symbol_other_issuer")
        self.assertEqual(self.assess(legs(mover()), f2=ok("bars", []))["recovered_class"], "recovered_today_symbol_no_row")
        r = self.assess(legs(mover()), f2={"error": 503})
        self.assertEqual(r["recovered_class"], "recovered_cause_unexplained")
        self.assertTrue(r["flags"]["leg_error"])
        self.assertIsNone(r["failure_class"])

    def test_event_class_by_role(self):
        passed = self.assess(legs(mover()))
        failed = self.assess(legs([bar(D, 1, 2, 1, 2)]))
        self.assertEqual(M.event_class(passed, "missed"), "recovered_today_symbol_same_issuer")
        self.assertIsNone(M.event_class(passed, "control"))
        self.assertEqual(M.event_class(failed, "control"), "no_prior_row")

    def test_flags(self):
        r = self.assess(legs(mover()))
        self.assertTrue(r["flags"]["otc_as_known"])  # no auction record at all on d
        opened = [auction(D, closes=[{"c": "6", "p": 12.9, "x": "Q", "s": 900}]),
                  auction(L, closes=[{"c": "6", "p": 10.2, "x": "Q", "s": 900}])]
        r = self.assess(legs(mover(), auctions=opened))
        self.assertFalse(r["flags"]["otc_as_known"])
        self.assertFalse(r["flags"]["prior_row_not_previous_session"])
        self.assertFalse(r["flags"]["basis_uncertain"])
        failed_auctions = dict(legs(mover()), auctions={"error": 503})
        r = self.assess(failed_auctions)
        self.assertIsNone(r["flags"]["otc_as_known"])
        self.assertTrue(r["flags"]["leg_error"])
        self.assertTrue(r["flags"]["not_verified_in_new_vintage"])  # no gain without the auction leg
        gap = [bar("2023-03-06", 10, 10.5, 10, 10.2), bar(D, 10.5, 13, 10.4, 12.9)]
        r = self.assess(legs(gap))
        self.assertTrue(r["flags"]["prior_row_not_previous_session"])
        self.assertTrue(r["flags"]["gap_over_7_days"])
        self.assertTrue(self.assess(legs(mover()))["flags"]["basis_uncertain"])  # closes from bar_close_fallback
        small = [bar(L, 10, 10.5, 10, 10.0), bar(D, 10.1, 12.5, 10.0, 11.0)]
        r = self.assess(legs(small))
        self.assertTrue(r["touch"])
        self.assertTrue(r["flags"]["not_verified_in_new_vintage"])  # +10% close to close


class Labels(unittest.TestCase):
    def setUp(self):
        self.cal = M.Calendar.load()

    def by(self, key, rows):
        return A.by_date(M.leg_rows(ok(key, rows), key)[1])

    def test_decimal_close_selector_matches_the_audit(self):
        days = [auction(D, closes=[{"c": "6", "p": 3.90, "x": "P", "s": 400}, {"c": "6", "p": 3.97, "x": "T", "s": 17000}],
                        opens=[{"c": "O", "p": 3.0, "x": "T", "s": 10}]),
                auction(D, closes=[{"c": "M", "p": 4.12, "x": "P"}, {"c": "M", "p": 4.10, "x": "Q"}]),
                auction(D, closes=[{"c": "6", "p": 2.5, "x": "Z", "s": 5}], opens=[]),
                auction(D, closes=[], opens=[])]
        for day in days:
            dec_day = self.by("auctions", [day])[D]
            got = M.official_close_dec(dec_day, Decimal("7.77"))
            want = A.official_close_v2(M.as_float(dec_day), 7.77)
            self.assertEqual((float(got[0]), got[1]), want)
        self.assertEqual(M.official_close_dec(None, None), (None, None))

    def test_ratio_flags_are_exact_rationals(self):
        flags = M.ratio_flags(Fraction(Decimal("3.00")), Fraction(Decimal("2.00")))
        self.assertEqual(flags, {"3/2": True, "2": False, "3": False})
        self.assertFalse(M.ratio_flags(Fraction(Decimal("2.9999")), Fraction(Decimal("2.00")))["3/2"])
        self.assertTrue(M.ratio_flags(Fraction(Decimal("6.00")), Fraction(Decimal("2")))["3"])

    def test_labels_with_split_correction_open_fallback_and_censoring(self):
        raw = [bar(L, 20, 21, 19.5, 20), bar(D, 12.5, 30, 12, 12)]
        split = [bar(L, 10, 10.5, 9.75, 10), bar(D, 12.5, 30, 12, 12)]
        raw_d, split_d, auc_d = self.by("bars", raw), self.by("bars", split), {}
        gain = A.event_gain(D, {}, M.as_float(raw_d), M.as_float(split_d), "v2")
        self.assertTrue(gain["split_between"])
        lab = M.labels(D, raw_d, split_d, auc_d, gain, self.cal)
        self.assertEqual(lab["close_to_close_1d"]["status"], "ok")
        self.assertEqual(Decimal(lab["close_to_close_1d"]["value"]), Decimal("0.2"))  # (12 x 2) / (20 x 1)
        self.assertEqual(lab["close_to_close_1d"]["flags"], {"3/2": False, "2": False, "3": False})
        self.assertEqual(lab["prior_close_to_high_1d"]["flags"], {"3/2": True, "2": True, "3": True})  # 30 x 2 / 20
        self.assertEqual(lab["open_to_high_1d"]["open_source"], "bar_open_fallback")
        self.assertEqual(lab["close_to_close_5d"]["status"], "censored_no_bar")
        self.assertEqual(lab["entry_to_exit"]["status"], "not_computed")
        opened = self.by("auctions", [auction(D, opens=[{"c": "O", "p": 10, "x": "Q", "s": 50}, {"c": "O", "p": 11, "x": "P", "s": 10}])])
        lab = M.labels(D, raw_d, split_d, opened, A.event_gain(D, M.as_float(opened), M.as_float(raw_d), M.as_float(split_d), "v2"), self.cal)
        self.assertEqual(lab["open_to_high_1d"]["open_source"], "opening_print_listing_exchange")
        self.assertEqual(lab["open_to_high_1d"]["flags"], {"3/2": True, "2": True, "3": True})  # 30 / 10

    def test_five_day_label_and_window_censoring(self):
        day5 = self.cal.offset(D, 5)
        split = [bar(L, 10, 10, 10, 10), bar(D, 10, 20, 10, 20), bar(day5, 30, 31, 29, 30)]
        split_d = self.by("bars", split)
        gain = A.event_gain(D, {}, M.as_float(split_d), M.as_float(split_d), "v2")
        lab = M.labels(D, split_d, split_d, {}, gain, self.cal)
        self.assertEqual(lab["close_to_close_5d"]["flags"], {"3/2": True, "2": False, "3": False})
        late = "2025-12-26"
        rows = self.by("bars", [bar("2025-12-24", 10, 10, 10, 10), bar(late, 10, 20, 10, 20)])
        gain = A.event_gain(late, {}, M.as_float(rows), M.as_float(rows), "v2")
        self.assertEqual(M.labels(late, rows, rows, {}, gain, self.cal)["close_to_close_5d"]["status"], "censored_after_window")


class Renames(unittest.TestCase):
    def test_name_change_pages_and_completeness(self):
        with tempfile.TemporaryDirectory() as tmp:
            ca = Path(tmp)
            (ca / "pages" / "2024").mkdir(parents=True)
            body = {"corporate_actions": {
                "name_change": [{"old_symbol": "ZZQA", "new_symbol": "ZZQB", "process_date": "2024-01-10"},
                                {"old_symbol": "ZZQX", "new_symbol": "ZZQX", "process_date": "2024-02-01"},
                                {"old_symbol": "ZZQY", "new_symbol": "ZZQZ"}],
                "name_changes": [{"old_symbol": "ZZQB", "new_symbol": "ZZQC", "process_date": "2025-06-02"}],
                "forward_split": [{"symbol": "ZZQD", "process_date": "2024-03-01"}]}, "next_page_token": None}
            with gzip.open(ca / "pages" / "2024" / "p0000.json.gz", "wb") as f:
                f.write(json.dumps(body).encode())
            self.assertEqual(M.name_changes(ca), [("ZZQA", "ZZQB", "2024-01-10"), ("ZZQB", "ZZQC", "2025-06-02")])
            (ca / "plan.json").write_text(json.dumps({"types_key": "k", "start": "2024-01-01", "end": "2025-12-31"}))
            lines = [{"event": "year_complete", "year": 2024, "types_key": "k"},
                     {"event": "run_complete", "types_key": "k", "failed": 0}]
            (ca / "ledger.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
            self.assertEqual(M.renames_complete(ca), (False, ["missing year_complete year=2025 types_key=k"]))
            lines.insert(1, {"event": "year_complete", "year": 2025, "types_key": "k"})
            (ca / "ledger.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
            self.assertEqual(M.renames_complete(ca), (True, []))

    def test_successor_chain_respects_dates(self):
        renames = [("ZZQA", "ZZQB", "2024-01-10"), ("ZZQB", "ZZQC", "2023-01-01"), ("ZZQB", "ZZQE", "2025-01-01")]
        self.assertEqual(M.successors(renames, "ZZQA", D), {"ZZQB", "ZZQE"})
        self.assertEqual(M.successors(renames, "ZZQA", "2024-01-10"), set())
        self.assertTrue(M.rename_on([("ZZQO", "ZZQA", D)], "ZZQA", D))
        self.assertFalse(M.rename_on([("ZZQA", "ZZQO", D)], "ZZQA", D))


def audit_row(i, date_, ticker, gain, verdict="match", symbol_used=None):
    return {"id": f"{date_}:{ticker}:{i}", "date": date_, "ticker": ticker, "symbol_used": symbol_used or ticker,
            "verdict": verdict, "alpaca_gain_pct": gain}


class GateSplit(unittest.TestCase):
    ROWS = [audit_row(0, "2021-02-01", "ZZQA", 35.0),                      # control, main
            audit_row(1, "2022-02-01", "ZZQB", 120.0, symbol_used="ZZQC"),  # control via ticker key, premarket
            audit_row(2, "2023-02-01", "ZZQD", 60.0, verdict="recovered_match"),  # missed
            audit_row(3, "2024-02-01", "ZZQE", 25.0, verdict="package_uncomputed_match"),  # excluded
            audit_row(4, "2025-02-03", "ZZQF", 19.99),                     # excluded: below 20
            audit_row(5, "2026-02-02", "ZZQG", 80.0),                      # excluded: holdout date
            audit_row(6, "2024-05-01", "ZZQH", 450.0)]                     # missed
    MAIN = {("ZZQA", "2021-02-01")}
    PREM = {("ZZQB", "2022-02-01"), ("ZZQA", "2021-02-01")}

    def test_missed_and_controls_follow_coverage_predicate(self):
        missed, controls = M.split_events({"events": self.ROWS}, self.MAIN, {("ZZQB", "2022-02-01")}, lambda g: "t")
        self.assertEqual([e["id"] for e in missed], [self.ROWS[2]["id"], self.ROWS[6]["id"]])
        self.assertEqual([(e["id"], e["held_by"]) for e in controls],
                         [(self.ROWS[0]["id"], "main"), (self.ROWS[1]["id"], "premarket")])
        self.assertEqual(controls[1]["symbol"], "ZZQC")
        _, both = M.split_events({"events": self.ROWS}, self.MAIN, self.PREM, lambda g: "t")
        self.assertEqual(both[0]["held_by"], "both")

    @unittest.skipUnless(HAS_NUMPY, "requires the pinned numpy runtime (mover-early-entry rules.py)")
    def test_split_agrees_with_evaluate_coverage(self):
        evaluate, rules = M.mover_modules()
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.json"
            audit_path.write_text(json.dumps({"events": self.ROWS}))
            paths = []
            for name, keys in (("main.csv", self.MAIN), ("prem.csv", self.PREM)):
                p = Path(tmp) / name
                with p.open("w", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["symbol", "session_date", "prev_date"])
                    for sym, day in sorted(keys):
                        w.writerow([sym, day, day])
                paths.append(p)
            cov = evaluate.coverage(audit_path, paths, *M.WINDOW)
            missed, controls = M.split_events({"events": self.ROWS}, self.MAIN, self.PREM, rules.degree_tier)
        self.assertEqual((cov["events"], cov["present"]), (len(missed) + len(controls), len(controls)))
        for tier, block in cov["by_tier"].items():
            self.assertEqual(block["present"], sum(1 for e in controls if e["tier"] == tier))
            self.assertEqual(block["events"] - block["present"], sum(1 for e in missed if e["tier"] == tier))


class GateRefusal(unittest.TestCase):
    def test_missing_inputs_refuse_without_a_request(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("urllib.request.urlopen", forbid_network):
            (Path(tmp) / "inputs").mkdir()
            code = M.main(["gate", "--inputs", str(Path(tmp) / "inputs"), "--out-dir", str(Path(tmp) / "run")])
            doc = json.loads((Path(tmp) / "run" / "gate.json").read_text())
            mode = stat.S_IMODE(os.stat(Path(tmp) / "run" / "gate.json").st_mode)
        self.assertEqual(code, 2)
        self.assertEqual((doc["status"], doc["reason"], doc["requests_sent"]), ("refused", "inputs_missing", 0))
        self.assertEqual(sorted(doc["missing"]), ["audit_results", "candidates_main", "candidates_premarket"])
        self.assertEqual(doc["plan_sha256"], M.PLAN_SHA256)
        self.assertEqual(mode, 0o600)

    def test_wrong_package_refuses_before_credentials(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("urllib.request.urlopen", forbid_network), \
                mock.patch.object(M, "code_revision", return_value={"head": "0" * 40, "clean": True}):
            z = Path(tmp) / "pkg.zip"
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("pkg/datasets/forward-returns-2021-2026.csv", "Date,Ticker\n")
            code = M.main(["e2", "--package-zip", str(z), "--env-file", str(Path(tmp) / "absent.env"),
                           "--out-dir", str(Path(tmp) / "run")])
            doc = json.loads((Path(tmp) / "run" / "fetch-status.json").read_text())
        self.assertEqual(code, 2)
        self.assertEqual((doc["status"], doc["reason"]), ("refused", "package_sha256_mismatch"))


class Package(unittest.TestCase):
    def test_extracts_only_the_two_audit_csvs(self):
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / "pkg.zip"
            fwd, alias = b"Date,Ticker\n2023-03-15,ZZQA\n", b"Date,Ticker,Alias_Symbol\n"
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("pkg/datasets/forward-returns-2021-2026.csv", fwd)
                zf.writestr("pkg/datasets/alias-map.csv", alias)
                zf.writestr("../evil.csv", b"x")
                zf.writestr("pkg/datasets/other.csv", b"y")
            dest = M.extract_package(z, Path(tmp) / "out" / "package")
            files = sorted(str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file())
            self.assertEqual(files, ["datasets/alias-map.csv", "datasets/forward-returns-2021-2026.csv"])
            self.assertEqual((dest / A.FORWARD_CSV).read_bytes(), fwd)
            self.assertEqual(stat.S_IMODE(os.stat(dest / A.FORWARD_CSV).st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o700)
            self.assertFalse((Path(tmp) / "evil.csv").exists())


class FakeData:
    """A synthetic market-data host keyed by (symbol, asof, path kind, adjustment)."""

    def __init__(self, table):
        self.table, self.urls = table, []

    def __call__(self, req, timeout=30):
        self.urls.append(req.full_url)
        parts = urllib.parse.urlsplit(req.full_url)
        q = dict(urllib.parse.parse_qsl(parts.query))
        segs = parts.path.split("/")
        sym, kind = urllib.parse.unquote(segs[3]), segs[4]
        key = (sym, q["asof"], kind, q.get("adjustment"))
        rows = self.table.get(key, [])
        rows = [r for r in rows if q["start"] <= (r.get("d") or r["t"][:10]) <= q["end"]]
        return FakeResponse(page(kind, rows, symbol=sym))


def package_event(i, day, ticker, status="OK", gain=None, used=""):
    return {"id": f"{day}:{ticker}:{i}", "date": day, "ticker": ticker, "symbols": [used or ticker] + ([ticker] if used else []),
            "status": status, "computed_gain": gain, "dataset_gain": None, "fwd": {1: None, 5: None, 20: None}}


@unittest.skipUnless(HAS_NUMPY, "requires the pinned numpy runtime (mover-early-entry rules.py)")
class E2Flow(unittest.TestCase):
    def setUp(self):
        self.cal = M.Calendar.load()

    def table(self):
        t = {}

        def put(sym, asof, rows, auctions=()):
            for adj in ("raw", "split", "all"):
                t[(sym, asof, "bars", adj)] = rows
            t[(sym, asof, "auctions", None)] = list(auctions)
        # ZZQA: +50% on D, touch passes, F2 (today's symbol) is another issuer
        put("ZZQA", D, [bar(L, 10, 10.2, 9.8, 10), bar(D, 11, 16, 10.9, 15)])
        put("ZZQA", "2026-09-21", [bar(D, 40, 41, 39, 40.5)])
        # ZZQB is found only under its second symbol; +30%, touch passes, F2 same issuer
        put("ZZQN", "2023-03-15", [])
        put("ZZQB", D, [bar(L, 20, 20.5, 19.9, 20), bar(D, 21, 26.5, 20.8, 26)])
        put("ZZQB", "2026-09-21", [bar(L, 20, 20.5, 19.9, 20), bar(D, 21, 26.5, 20.8, 26)])
        # ZZQC: package says +25% but the new vintage says +5%: not in N2
        put("ZZQC", D, [bar(L, 10, 10.1, 9.9, 10), bar(D, 10, 10.6, 9.9, 10.5)])
        for sym in ("KOD", "LFCR"):
            put(sym, "2026-09-28", [bar("2026-09-25", 5, 5.1, 4.9, 5), bar("2026-09-28", 5.2, 7.5, 5.1, 7)])
        return t

    def run_flow(self, tmp):
        events = [package_event(0, D, "ZZQA", gain=50.0), package_event(1, D, "ZZQB", gain=30.0, used="ZZQN"),
                  package_event(2, D, "ZZQC", gain=25.0), package_event(3, "2020-06-01", "ZZQD", gain=90.0)]
        fake = FakeData(self.table())
        out = Path(tmp) / "run"
        with mock.patch("urllib.request.urlopen", fake), mock.patch("time.sleep"):
            client = M.TextClient("synthetic-key", "synthetic-secret")
            M.run_e2(events, client, self.cal, out, fetched_at="2026-09-29T01:00:00Z", code={"head": "0" * 40, "clean": True})
        return out, fake, events

    def test_resolution_n2_touch_identity_and_control(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, fake, events = self.run_flow(tmp)
            self.assertTrue(all("/v2/stocks/" in u and u.startswith(A.DATA_URL) for u in fake.urls))
            self.assertFalse(any("2020-06-01" in u for u in fake.urls))  # outside 2021-01-04..2025-12-31
            with mock.patch.object(M, "load_package_events", return_value=events[:3]):
                self.assertEqual(M.main(["classify", "--out-dir", str(out)]), 0)
            summary = json.loads((out / "summary.json").read_text())
        e2 = summary["E2"]
        self.assertEqual(e2["package_events_in_window"], 3)
        self.assertEqual(e2["N2"], 2)
        self.assertEqual(e2["touch_passes_among_N2"], 2)
        self.assertEqual(e2["f2_identity_among_N2"], {"f1_raw_unavailable": 0, "f2_error": 0, "f2_not_fetched": 0,
                                                     "no_row": 0, "other_issuer": 1, "same_issuer": 1})
        self.assertEqual(e2["N2_minus_committed_events"], 2 - 594)
        outside = e2["f2_identity_outside_N2_post_hoc"]
        self.assertEqual((outside["no_row"], sum(outside.values())), (1, 1))  # the +5% event's symbol has no F2 row
        self.assertNotIn("classify_code_revision", summary)  # classify outputs depend on the snapshots alone
        self.assertEqual(summary["positive_control"], {"KOD": {"touch": True}, "LFCR": {"touch": True}, "passed": True})
        self.assertEqual(summary["exposure"]["price_rows_in_holdout"], 0)
        self.assertEqual(summary["E2"]["verdicts"]["mismatch"], 1)

    def test_classify_is_byte_identical_and_totals_hold_no_event_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, _, events = self.run_flow(tmp)
            rev = lambda h: mock.patch.object(M, "code_revision", return_value={"head": h * 40, "clean": True})  # noqa: E731
            with mock.patch.object(M, "load_package_events", return_value=events[:3]):
                with rev("1"):
                    self.assertEqual(M.main(["classify", "--out-dir", str(out)]), 0)
                first = {n: (out / n).read_bytes() for n in ("results.json", "labels.json", "summary.json")}
                with rev("2"):  # a verify at a later commit still compares the classify outputs byte for byte
                    self.assertEqual(M.main(["classify", "--out-dir", str(out), "--verify"]), 0)
            verify = json.loads((out / "verify.json").read_text())
            self.assertTrue(verify["byte_identical"])
            self.assertEqual(verify["classify_code_revision"]["head"], "2" * 40)
            self.assertEqual(first, {n: (out / n).read_bytes() for n in first})
            text = (out / "summary.json").read_text()
            modes = {p.name: stat.S_IMODE(os.stat(p).st_mode) for p in out.iterdir() if p.is_file()}
        for needle in ("ZZQA", "ZZQB", "ZZQN", "2023-03-15", "2023-03-14", "26.5", "16.0"):
            self.assertNotIn(needle, text)
        self.assertEqual(set(modes.values()), {0o600})

    def test_publish_scans_and_keeps_totals_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, _, events = self.run_flow(tmp)
            with mock.patch.object(M, "load_package_events", return_value=events[:3]):
                M.main(["classify", "--out-dir", str(out)])
                M.main(["classify", "--out-dir", str(out), "--verify"])
            run = Path(tmp) / "e1"
            run.mkdir()
            (run / "gate.json").write_text(json.dumps({"status": "refused", "reason": "inputs_missing", "requests_sent": 0,
                                                       "missing": {"audit_results": "a" * 64}, "plan_sha256": M.PLAN_SHA256}))
            dest = Path(tmp) / "summary.json"
            self.assertEqual(M.main(["publish", "--run-dir", str(run), "--e2-dir", str(out), "--to", str(dest)]), 0)
            doc = json.loads(dest.read_text())
            text = dest.read_text()
        self.assertEqual(doc["E1"]["status"], "not_run")
        self.assertIsNone(doc["E1"]["coverage_with_asof"])
        self.assertEqual(doc["E2"]["validity"]["stands"], True)
        self.assertIn("head", doc["E2"]["classify_code_revision"])  # carried over from verify.json
        self.assertNotIn(tmp, text)
        for needle in ("ZZQ", "2023-03-15"):
            self.assertNotIn(needle, text)


@unittest.skipUnless(HAS_NUMPY, "requires the pinned numpy runtime (mover-early-entry rules.py)")
class E1Flow(unittest.TestCase):
    """Gate outputs, F1/F2 from a synthetic data host, one name change, then classify, verify and publish."""

    def setUp(self):
        self.cal = M.Calendar.load()

    def build(self, tmp):
        out = Path(tmp) / "run"
        M.private_dir(out)
        ev = lambda i, sym, role, held, gain, tier: {"id": f"{D}:{sym}:{i}", "date": D, "ticker": sym, "symbol_used": sym,  # noqa: E731
                                                     "symbol": sym, "role": role, "held_by": held, "tier": tier,
                                                     "audit_gain_pct": gain}
        events = [ev(0, "ZZQA", "missed", None, 50.0, "0.50-1.00"), ev(1, "ZZQB", "missed", None, 30.0, "0.30-0.50"),
                  ev(2, "ZZQE", "missed", None, 30.0, "0.30-0.50"), ev(3, "ZZQC", "control", "main", 30.0, "0.30-0.50"),
                  ev(4, "ZZQD", "control", "premarket", 25.0, "-0.30")]
        sha = M.write_doc(out / "missed-events.json", {"plan_sha256": M.PLAN_SHA256, "events": events})
        M.write_doc(out / "gate.json", {"status": "passed", "plan_sha256": M.PLAN_SHA256, "events_sha256": sha,
                                        "coverage": M.PLAN["reproduction_gate"]["expected"], "missed": 3, "controls": 2,
                                        "controls_held_by": {"main": 1, "premarket": 1}, "requests_sent": 0})
        (out / "corporate-actions" / "pages" / "2024").mkdir(parents=True)
        with gzip.open(out / "corporate-actions" / "pages" / "2024" / "p0000.json.gz", "wb") as f:
            f.write(json.dumps({"corporate_actions": {"name_change": [
                {"old_symbol": "ZZQE", "new_symbol": "ZZQF", "process_date": "2024-01-10"}]}}).encode())
        t = {}

        def put(sym, asof, rows):
            for adj in ("raw", "split", "all"):
                t[(sym, asof, "bars", adj)] = rows
        put("ZZQA", D, [bar(L, 10, 10.2, 9.8, 10), bar(D, 11, 16, 10.9, 15)])
        put("ZZQA", "2026-09-21", [bar(D, 40, 41, 39, 40.5)])
        put("ZZQB", D, [bar(L, 10, 10.2, 9.8, 10)])
        put("ZZQE", D, [bar(L, 5, 5.1, 4.9, 5), bar(D, 5.5, 7, 5.4, 6.5)])
        put("ZZQC", D, [bar(L, 20, 20.5, 19.9, 20), bar(D, 21, 26.5, 20.8, 26)])
        put("ZZQC", "2026-09-21", [bar(L, 20, 20.5, 19.9, 20), bar(D, 21, 26.5, 20.8, 26)])
        put("ZZQD", D, [bar(L, 10, 10.5, 10, 10.2), bar(D, 10.2, 11, 10.1, 10.8)])
        for sym in ("KOD", "LFCR"):
            put(sym, "2026-09-28", [bar("2026-09-25", 5, 5.1, 4.9, 5), bar("2026-09-28", 5.2, 7.5, 5.1, 7)])
        with mock.patch("urllib.request.urlopen", FakeData(t)), mock.patch("time.sleep"):
            M.run_e1_fetch(events, M.TextClient("synthetic-key", "synthetic-secret"), self.cal, out,
                           fetched_at="2026-09-29T01:00:00Z", code={"head": "0" * 40, "clean": True})
        return out

    def test_classes_coverage_verify_and_publish(self):
        keys = {("ZZQF", D), ("ZZQC", D), ("ZZQD", D)}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(M, "load_candidate_keys", return_value=keys):
            out = self.build(tmp)
            self.assertEqual(M.main(["classify", "--out-dir", str(out)]), 0)
            self.assertEqual(M.main(["classify", "--out-dir", str(out), "--verify"]), 0)
            e1 = json.loads((out / "summary.json").read_text())["E1"]
            dest = Path(tmp) / "published.json"
            self.assertEqual(M.main(["publish", "--run-dir", str(out), "--to", str(dest)]), 0)
            published = json.loads(dest.read_text())
            text = dest.read_text()
        self.assertEqual(e1["recovered"], 2)
        self.assertEqual(e1["coverage_with_asof"], {"present": 500, "events": 594, "share": round(500 / 594, 8),
                                                    "meets_95_percent": False})
        self.assertEqual(e1["coverage_with_asof_without_otc_as_known"]["present"], 498)  # no auction prints at all
        self.assertEqual(e1["coverage_frozen_rekeyed"]["present"], 499)
        classes = e1["classes_of_missed"]
        self.assertEqual((classes["recovered_today_symbol_other_issuer"], classes["recovered_keyed_under_successor"],
                          classes["no_asof_event_row"]), (1, 1, 1))
        self.assertEqual(sum(classes.values()), 3)
        recount = e1["asof_recount"]
        self.assertEqual(recount["controls_by_candidate_file"]["main"]["touch_passes"], 1)
        self.assertEqual(recount["controls_by_candidate_file"]["premarket"]["failure_classes"]["below_touch_other"], 1)
        self.assertEqual(recount["control_f2_identity"]["same_issuer"], 1)
        self.assertEqual(e1["vendor_agreement"]["missed"], {"agree": 2, "disagree": 0, "not_verified_in_new_vintage": 1})
        self.assertEqual(e1["by_tier"]["0.50-1.00"]["recovered"], 1)
        self.assertEqual(e1["by_close_to_close_1d_ratio"]["3/2"]["recovered"], 1)  # +50%
        self.assertEqual(published["E1"]["validity"]["stands"], True)
        self.assertTrue(published["E1"]["validity"]["gate_reproduced"])
        self.assertNotIn("ZZQ", text)


TIER_KEYS = tuple(M.PLAN["reproduction_gate"]["expected"]["by_tier"])
DEGREE_TIERS = ((None, 0.30), (0.30, 0.50), (0.50, 1.00), (1.00, 3.00), (3.00, 10.00), (10.00, None))


def tier_label(i):
    lo, hi = DEGREE_TIERS[i]
    return f"{'' if lo is None else f'{lo:.2f}'}-{'' if hi is None else f'{hi:.2f}'}"


def degree_tier(gain):
    return next(tier_label(i) for i, (lo, hi) in enumerate(DEGREE_TIERS)
                if (lo is None or gain >= lo) and (hi is None or gain < hi))


# mover-early-entry rules.py's tier interface (rules.py:27 and 60-73), restated so these tests run without numpy
STUB_RULES = types.SimpleNamespace(DEGREE_TIERS=DEGREE_TIERS, tier_label=tier_label, degree_tier=degree_tier)


class StubRules(unittest.TestCase):
    def test_labels_are_the_plans_tiers(self):
        self.assertEqual(tuple(tier_label(i) for i in range(len(DEGREE_TIERS))), TIER_KEYS)

    @unittest.skipUnless(HAS_NUMPY, "requires the pinned numpy runtime (mover-early-entry rules.py)")
    def test_stub_restates_rules_py(self):
        _, rules = M.mover_modules()
        self.assertEqual(DEGREE_TIERS, rules.DEGREE_TIERS)
        for gain in (0.2, 0.3, 0.75, 1.0, 2.5, 3.0, 12.0):
            self.assertEqual(degree_tier(gain), rules.degree_tier(gain))


class E2LegCheck(unittest.TestCase):
    """Review finding 1: classify_e2 computes a gain only when the raw, split and auction legs all succeeded, as
    assess() does, so a partial failure never becomes a verdict inside N2."""

    BARS = [bar(L, 10, 10.2, 9.8, 10), bar(D, 11, 16, 10.9, 15)]  # +50% close to close; the touch passes
    CLOSES = [auction(L, closes=[{"c": "6", "p": 10, "x": "Q", "s": 100}]),
              auction(D, closes=[{"c": "6", "p": 15, "x": "Q", "s": 100}])]

    def setUp(self):
        self.cal = M.Calendar.load()

    def classify(self, tried):
        ev = package_event(0, D, "ZZQA", gain=50.0)
        f1doc = {"events": {ev["id"]: {"day": D, "tried": [{"symbol": s, "legs": got} for s, got in tried]}}}
        f2doc = {"events": {ev["id"]: {"symbol": "ZZQA", "leg": ok("bars", self.BARS)}}}
        with mock.patch.object(M, "load_package_events", return_value=[ev]):
            rows, _, body = M.classify_e2(Path("unused"), f1doc, f2doc, self.cal, STUB_RULES)
        return rows[0], body["E2"]

    def test_all_legs_ok_is_a_match_inside_n2(self):
        row, e2 = self.classify([("ZZQA", legs(self.BARS, auctions=self.CLOSES))])
        self.assertEqual((row["verdict"], row["in_n2"], row["symbol_used"], row["gain_pct"]), ("match", True, "ZZQA", 50.0))
        self.assertEqual((e2["N2"], e2["verdicts"]), (1, {"match": 1}))
        self.assertFalse(row["flags"]["not_verified_in_new_vintage"])
        self.assertFalse(row["flags"]["leg_error"])

    def test_a_failed_gain_leg_is_a_fetch_error_outside_n2(self):
        cases = {"auction 503 with valid bars": dict(legs(self.BARS), auctions={"error": 503}),
                 "split 503": legs(self.BARS, auctions=self.CLOSES, bars_split=503),
                 "raw 503 while the auctions hold both closes": legs(self.BARS, auctions=self.CLOSES, bars_raw=503)}
        for label, got in cases.items():
            with self.subTest(label):
                row, e2 = self.classify([("ZZQA", got)])
                self.assertEqual((row["verdict"], row["in_n2"], row["symbol_used"]), ("fetch_error", False, None))
                self.assertEqual((e2["N2"], e2["verdicts"]), (0, {"fetch_error": 1}))
                self.assertEqual(e2["flags_among_N2"]["not_verified_in_new_vintage"], {"true": 0, "false": 0, "unknown": 0})

    def test_a_failed_request_on_an_earlier_symbol_ends_the_walk(self):
        # The first symbol's raw bars failed, so whether it had a bar on d is unknown: a failed request is never
        # read as no data (audit deviation D7), and the walk does not move on to the next symbol.
        row, e2 = self.classify([("ZZQN", legs([], bars_raw=503)), ("ZZQA", legs(self.BARS, auctions=self.CLOSES))])
        self.assertEqual((row["verdict"], row["in_n2"], row["symbol_used"], e2["N2"]), ("fetch_error", False, None, 0))


class VerifyProvenance(unittest.TestCase):
    """Review finding 2: publish counts the second classify only from a verify.json of this plan and estimand that
    recorded the sha256 of the classify outputs now on disk, next to a summary.json that names the snapshots now
    on disk."""

    OUTPUTS = ("results.json", "labels.json", "summary.json")
    SNAPSHOTS = ("snapshot-f1.json", "snapshot-f2.json", "control.json", "request-log.json")

    def folder(self, tmp):
        out = M.private_dir(Path(tmp) / "e2")
        for name in self.SNAPSHOTS + ("results.json", "labels.json"):
            M.write_doc(out / name, {"kind": "synthetic", "name": name})
        M.write_doc(out / "summary.json", {
            "kind": "mover_coverage_asof_private_summary", "plan_sha256": M.PLAN_SHA256, "estimand": "E2",
            "E2": {"N2": 2, "package_events_in_window": 3},
            "positive_control": {"KOD": {"touch": True}, "LFCR": {"touch": True}, "passed": True},
            "exposure": {"price_rows_total": 9, "price_rows_before_2021_01_04": 0, "price_rows_in_holdout": 0},
            "requests": {"total": 12, "status_counts": {"200": 12}}, "responses": {"legs": {}, "error_codes": {}},
            "snapshots_sha256": {n: M.sha256_file(out / n) for n in self.SNAPSHOTS},
            "fetched_at_utc": "2026-09-29T01:00:00Z", "control_sent_at_utc": "2026-09-29T01:00:00Z",
            "finished_at_utc": "2026-09-29T01:05:00Z", "code_revision": {"head": "1" * 40, "clean": True}})
        self.write_verify(out)
        return out

    def write_verify(self, out, **changes):
        verify = {"kind": "mover_coverage_asof_verify", "plan_sha256": M.PLAN_SHA256, "estimand": "E2",
                  "byte_identical": True, "sha256": {n: M.sha256_file(out / n) for n in self.OUTPUTS},
                  "classify_code_revision": {"head": "2" * 40, "clean": True}}
        M.write_doc(out / "verify.json", dict(verify, **changes))

    def test_a_matching_verify_stands(self):
        with tempfile.TemporaryDirectory() as tmp:
            block = M.estimand_block(self.folder(tmp), "E2", False)
        self.assertEqual((block["validity"]["classify_rerun_byte_identical"], block["validity"]["stands"]), (True, True))
        self.assertEqual(block["classify_code_revision"], {"head": "2" * 40, "clean": True})

    def test_a_stale_or_unrelated_verify_does_not_stand(self):
        cases = {
            "another plan": lambda out: self.write_verify(out, plan_sha256="0" * 64),
            "another estimand": lambda out: self.write_verify(out, estimand="E1"),
            "another kind": lambda out: self.write_verify(out, kind="mover_coverage_asof_results"),
            "not byte-identical": lambda out: self.write_verify(out, byte_identical=False),
            "hashes of other outputs": lambda out: self.write_verify(out, sha256={n: "a" * 64 for n in self.OUTPUTS}),
            "no recorded hashes": lambda out: self.write_verify(out, sha256=None),
            "a classify output changed after the verify": lambda out: M.write_doc(out / "results.json", {"changed": 1}),
            "a snapshot changed after the classify": lambda out: M.write_doc(out / "snapshot-f1.json", {"changed": 1}),
            "the review probe: other plan and estimand, stale hashes": lambda out: (
                self.write_verify(out, plan_sha256="0" * 64, estimand="E1"), M.write_doc(out / "labels.json", {"stale": 1})),
            "no verify.json": lambda out: (out / "verify.json").unlink(),
        }
        for label, spoil in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                out = self.folder(tmp)
                spoil(out)
                validity = M.estimand_block(out, "E2", False)["validity"]
                self.assertEqual((validity["classify_rerun_byte_identical"], validity["stands"]), (False, False))

    def test_a_revision_is_carried_only_from_this_plan_and_estimand(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.folder(tmp)
            self.write_verify(out, plan_sha256="0" * 64)
            self.assertIsNone(M.estimand_block(out, "E2", False)["classify_code_revision"])

    def test_a_summary_of_another_plan_or_estimand_is_refused(self):
        for field, value in (("plan_sha256", "0" * 64), ("estimand", "E1"), ("kind", "mover_coverage_asof_results")):
            with self.subTest(field), tempfile.TemporaryDirectory() as tmp:
                out = self.folder(tmp)
                summary = json.loads((out / "summary.json").read_text())
                M.write_doc(out / "summary.json", dict(summary, **{field: value}))
                self.write_verify(out)  # a fresh verify of that summary: only the summary's own provenance is wrong
                with self.assertRaises(M.Refused) as caught:
                    M.estimand_block(out, "E2", False)
                self.assertEqual(caught.exception.reason, "summary_not_this_plan_or_estimand")

    def publish(self, tmp, out):
        run = Path(tmp) / "e1"
        run.mkdir()
        (run / "gate.json").write_text(json.dumps({"status": "refused", "reason": "inputs_missing", "requests_sent": 0,
                                                   "plan_sha256": M.PLAN_SHA256}))
        dest = Path(tmp) / "published.json"
        code = M.main(["publish", "--run-dir", str(run), "--e2-dir", str(out), "--to", str(dest)])
        return code, (json.loads(dest.read_text()) if dest.exists() else None)

    def test_publish_records_a_stale_verify_as_a_failed_condition(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.folder(tmp)
            M.write_doc(out / "summary.json", dict(json.loads((out / "summary.json").read_text()), E2={"N2": 3}))
            code, doc = self.publish(tmp, out)
        self.assertEqual(code, 0)
        self.assertEqual(doc["E2"]["N2"], 3)
        self.assertEqual((doc["E2"]["validity"]["classify_rerun_byte_identical"], doc["E2"]["validity"]["stands"]),
                         (False, False))

    def test_publish_refuses_a_summary_of_another_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.folder(tmp)
            M.write_doc(out / "summary.json", dict(json.loads((out / "summary.json").read_text()), plan_sha256="0" * 64))
            self.write_verify(out)
            code, doc = self.publish(tmp, out)
        self.assertEqual((code, doc), (2, None))


class PublicSchema(unittest.TestCase):
    """Review finding 3: publish's scan enforces an explicit totals-only schema, so a key it does not name, including
    a symbol-like key, is refused."""

    COMMITTED = HERE / "evidence" / "summary-asof-20260929.json"

    def committed(self):
        return json.loads(self.COMMITTED.read_text())

    def test_the_committed_summary_fits_the_schema(self):
        self.assertEqual(M.scan_public(self.committed()), [])

    def test_the_review_probe_is_refused(self):
        problems = M.scan_public({"labels": {"ZZQA": {"return": 0.5, "price": 10}}})
        self.assertIn("$.labels: unexpected key", problems)
        self.assertIn("$.labels.ZZQA: symbol-like key", problems)

    def test_keys_and_values_outside_the_schema_are_refused(self):
        cases = {
            ("$.E2.by_tier.ZZQA: unexpected key", "$.E2.by_tier.ZZQA: symbol-like key"):
                lambda d: d["E2"]["by_tier"].update(ZZQA={"N2": 1}),
            ("$.E2.events: unexpected key",): lambda d: d["E2"].update(events={"n": 1}),
            ("$.events: unexpected key",): lambda d: d.update(events=[{"return": 0.5}]),
            ("$.E2.verdicts.match: expected an integer",): lambda d: d["E2"]["verdicts"].update(match=[1, 2]),
            ("$.E2.private_files_sha256.ZZQA.json: unexpected key",):
                lambda d: d["E2"]["private_files_sha256"].update({"ZZQA.json": "a" * 64}),
            ("$.E2.requests.status_counts.ZZQA: unexpected key", "$.E2.requests.status_counts.ZZQA: symbol-like key"):
                lambda d: d["E2"]["requests"]["status_counts"].update(ZZQA=1),
            ("$.E2.validity.per_event: unexpected key",): lambda d: d["E2"]["validity"].update(per_event=True),
            ("$.E2.N2: expected an integer",): lambda d: d["E2"].update(N2=10.5),
            ("$.E2.N2: expected an integer", "$.E2.N2.ZZQA: symbol-like key"): lambda d: d["E2"].update(N2={"ZZQA": 1}),
            ("$.E2.touch_share_among_N2: expected a share",): lambda d: d["E2"].update(touch_share_among_N2=1.5),
            ("$.plan.sha256: expected a sha256",): lambda d: d["plan"].update(sha256="not-a-hash"),
            ("$.E2.fetched_at_utc: expected a timestamp",): lambda d: d["E2"].update(fetched_at_utc="soon"),
        }
        for wants, spoil in cases.items():
            doc = self.committed()
            spoil(doc)
            problems = M.scan_public(doc)
            for want in wants:
                with self.subTest(want):
                    self.assertIn(want, problems)


INPUT_NAMES = {"audit_results": "audit-results.json", "candidates_main": M.PLAN["inputs"]["candidates_main"]["file"],
               "candidates_premarket": M.PLAN["inputs"]["candidates_premarket"]["file"]}


class E1Refusals(unittest.TestCase):
    """Review finding 4: E1 stops at mismatched candidate files or an unreproduced coverage before any credential
    read, corporate-action collection or request. The real inputs are private, so the plan's sha256 is pointed at
    synthetic files for the inputs a case needs to pass."""

    def inputs(self, tmp):
        inputs = Path(tmp) / "inputs"
        inputs.mkdir()
        (inputs / INPUT_NAMES["audit_results"]).write_text(json.dumps({"events": GateSplit.ROWS}))
        for key, keys in (("candidates_main", GateSplit.MAIN), ("candidates_premarket", GateSplit.PREM)):
            with (inputs / INPUT_NAMES[key]).open("w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["symbol", "session_date", "prev_date"])
                for sym, day in sorted(keys):
                    writer.writerow([sym, day, day])
        return inputs

    def forbid_leaving_the_host(self, stack):
        credentials = mock.Mock(side_effect=CredentialRead)
        stack.enter_context(mock.patch("urllib.request.urlopen", forbid_network))
        stack.enter_context(mock.patch("subprocess.run", forbid_subprocess))
        stack.enter_context(mock.patch.object(M.audit, "credentials", credentials))
        stack.enter_context(mock.patch.object(M, "code_revision", return_value={"head": "0" * 40, "clean": True}))
        stack.enter_context(mock.patch.object(M, "control_time_ok", return_value=True))
        return credentials

    def gate_then_fetch(self, tmp, pinned, coverage=None):
        inputs, out = self.inputs(tmp), Path(tmp) / "run"
        with contextlib.ExitStack() as stack:
            for key in pinned:
                stack.enter_context(mock.patch.dict(M.PLAN["inputs"][key], {"sha256": M.sha256_file(inputs / INPUT_NAMES[key])}))
            if coverage is not None:
                evaluate = types.SimpleNamespace(coverage=lambda *args: coverage)
                stack.enter_context(mock.patch.object(M, "mover_modules", return_value=(evaluate, STUB_RULES)))
            credentials = self.forbid_leaving_the_host(stack)
            gate_code = M.main(["gate", "--inputs", str(inputs), "--out-dir", str(out)])
            fetch_code = M.main(["fetch", "--env-file", str(Path(tmp) / "paper.env"), "--out-dir", str(out)])
        return {"gate_code": gate_code, "gate": json.loads((out / "gate.json").read_text()), "fetch_code": fetch_code,
                "fetch": json.loads((out / "fetch-status.json").read_text()), "credentials": credentials,
                "events_written": (out / "missed-events.json").exists(),
                "renames_collected": (out / "corporate-actions").exists()}

    def assert_stopped_before_leaving_the_host(self, got, reason):
        self.assertEqual((got["gate_code"], got["gate"]["status"], got["gate"]["reason"], got["gate"]["requests_sent"]),
                         (2, "refused", reason, 0))
        self.assertFalse(got["events_written"])
        self.assertEqual((got["fetch_code"], got["fetch"]["status"], got["fetch"]["reason"], got["fetch"]["requests_sent"]),
                         (2, "refused", "gate_not_passed", 0))
        got["credentials"].assert_not_called()
        self.assertFalse(got["renames_collected"])

    def test_mismatched_candidate_files_stop_e1_before_credentials_and_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = self.gate_then_fetch(tmp, pinned=("audit_results",))  # found by sha256; the candidates differ
        self.assert_stopped_before_leaving_the_host(got, "input_sha256_mismatch")
        self.assertEqual(got["gate"]["mismatched"], ["candidates_main", "candidates_premarket"])

    def test_an_unreproduced_coverage_stops_e1_before_credentials_and_requests(self):
        wrong = dict(M.PLAN["reproduction_gate"]["expected"], present=497)
        with tempfile.TemporaryDirectory() as tmp:
            got = self.gate_then_fetch(tmp, pinned=tuple(INPUT_NAMES), coverage=wrong)
        self.assert_stopped_before_leaving_the_host(got, "coverage_not_reproduced")
        self.assertEqual(got["gate"]["coverage"]["present"], 497)

    def test_harness_control_a_passed_gate_does_reach_the_credentials(self):
        # Without a refusal, fetch reaches audit.credentials, so the not-called assertions above are not vacuous.
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            out = M.private_dir(Path(tmp) / "run")
            sha = M.write_doc(out / "missed-events.json", {"plan_sha256": M.PLAN_SHA256, "events": []})
            M.write_doc(out / "gate.json", {"status": "passed", "plan_sha256": M.PLAN_SHA256, "events_sha256": sha})
            credentials = self.forbid_leaving_the_host(stack)
            with self.assertRaises(CredentialRead):
                M.main(["fetch", "--env-file", str(Path(tmp) / "paper.env"), "--out-dir", str(out)])
        credentials.assert_called_once()

    def test_candidate_files_are_checked_again_at_classify(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = self.inputs(tmp)
            with self.assertRaises(M.Refused) as caught:
                M.load_candidate_keys(inputs)
        self.assertEqual((caught.exception.reason, caught.exception.detail), ("candidate_file_changed", {"file": "candidates_main"}))


if __name__ == "__main__":
    unittest.main()
