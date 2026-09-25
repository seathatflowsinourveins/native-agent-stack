"""SYN: news-reversal/analyze.py - group-sequential numerics, futility, counted sessions, cost
measurement, harm stops, the refusal guard and a full guarded look in a scratch git repository.

Synthetic inputs only: no journal of the running service is read and no network is used. The
O'Brien-Fleming numerics are checked against published constants (Jennison & Turnbull 2000,
Table 2.3) and, independently, against a seeded Monte Carlo of the canonical joint distribution.
"""

import copy
import importlib.util
import io
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests import hermetic_git_environment

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "blueprints/us-equities/sota-mover/news-reversal"
FORWARD = ROOT / "blueprints/us-equities/sota-mover/news-forward"
STUDY_REL = "blueprints/us-equities/sota-mover/news-reversal"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


an = load("news_reversal_analyze_under_test", STUDY / "analyze.py")
sig = an.sig
DRAFT = json.loads((STUDY / "forward-protocol.json").read_text())
FEES = json.loads((ROOT / an.REFERENCE["fees-v3.json"]).read_text())
COSTS = DRAFT["estimands"]["net_cost_model"]
CAL = an.load_calendar(ROOT)


def monte_carlo(fractions, upper, lower, theta, n, seed):
    """(P(stop above), P(stop below)) by simulating the Brownian score at the looks."""
    rng = random.Random(seed)
    up = lo = 0
    for _ in range(n):
        s, t_prev = 0.0, 0.0
        for k, t in enumerate(fractions):
            s += rng.gauss(theta * (t - t_prev), math.sqrt(t - t_prev))
            t_prev = t
            z = s / math.sqrt(t)
            if z >= upper[k]:
                up += 1
                break
            if lower is not None and k < len(fractions) - 1 and z <= lower[k]:
                lo += 1
                break
    return up / n, lo / n


class ObrienFleming(unittest.TestCase):
    # Jennison & Turnbull (2000), Table 2.3: C_B(K, alpha) for two-sided O'Brien-Fleming tests. A one-sided
    # upper-only test at alpha/2 has the same constant to 3 decimals (crossing one boundary and then the
    # other has negligible probability).
    TABLE_2_3 = {0.05: {2: 1.977, 3: 2.004, 4: 2.024, 5: 2.040}, 0.10: {2: 1.678, 3: 1.710, 4: 1.733, 5: 1.751}}

    def test_constants_match_the_published_table(self):
        for two_sided, row in self.TABLE_2_3.items():
            for k, ref in row.items():
                c, _ = an.obf_boundaries([(i + 1) / k for i in range(k)], two_sided / 2)
                self.assertAlmostEqual(c, ref, delta=0.0006, msg=(two_sided, k))

    def test_k4_boundaries_and_the_fixed_sample_limit(self):
        _, b = an.obf_boundaries([0.25, 0.5, 0.75, 1.0], 0.025)
        for got, ref in zip(b, (4.049, 2.863, 2.337, 2.024)):
            self.assertAlmostEqual(got, ref, delta=0.0006)
        c, b = an.obf_boundaries([1.0], 0.05)
        self.assertAlmostEqual(c, 1.6448536, places=5)

    def test_grid_integrates_the_normal_density(self):
        z, w = an.grid(32, 0.3, -math.inf, math.inf)
        self.assertAlmostEqual(sum(wi * an.norm_pdf(zi - 0.3) for zi, wi in zip(z, w)), 1.0, places=7)
        z, w = an.grid(32, 0.0, -math.inf, 1.0)
        self.assertAlmostEqual(sum(wi * an.norm_pdf(zi) for zi, wi in zip(z, w)), an.norm_cdf(1.0), places=7)

    def test_the_design_against_an_independent_monte_carlo(self):
        d = an.design(DRAFT)
        fr, up, fut = d["information_fractions"], d["efficacy_z"], [-math.inf if f is None else f for f in d["futility_z"]]
        alpha, _ = monte_carlo(fr, up, None, 0.0, 60000, 20260925)
        self.assertAlmostEqual(alpha, 0.05, delta=0.004)
        theta = d["scenarios"]["in_sample_11bps_spread_ignored"]["drift_theta"]
        power, stop_low = monte_carlo(fr, up, fut, theta, 60000, 20260926)
        self.assertAlmostEqual(power, d["scenarios"]["in_sample_11bps_spread_ignored"]["power_if_futility_followed"], delta=0.008)
        self.assertAlmostEqual(stop_low, d["scenarios"]["in_sample_11bps_spread_ignored"]["futility_stop_probability"], delta=0.006)

    def test_fixed_sample_sessions(self):
        # the brief: sd ~79 bps, +11 bps/day gross, 80% power one-sided 0.05 -> about 320 sessions
        self.assertEqual(math.ceil(an.fixed_sample_sessions(11.0, 79.0)), 319)
        self.assertEqual(math.ceil(an.fixed_sample_sessions(11.0083, 78.67)), 316)
        self.assertGreater(an.fixed_sample_sessions(2.6, 78.67), 5600)  # the net effect: over 22 years of sessions
        self.assertIsNone(an.fixed_sample_sessions(0.0, 78.67))


class FutilityAndDecisions(unittest.TestCase):
    EFF = [4.27407, 2.96116, 2.09386, 1.70963]
    FUT = [None, 0.0, 0.0, None]

    def test_look_decisions(self):
        dec = lambda k, z: an.look_decision(k, z, self.EFF, self.FUT, 4)  # noqa: E731
        self.assertEqual(dec(1, -3.0), "continue")  # no futility stop at look 1
        self.assertEqual(dec(1, 4.28), "efficacy")
        self.assertEqual(dec(2, 0.0), "futility")  # t <= 0 at looks 2 and 3
        self.assertEqual(dec(2, 0.01), "continue")
        self.assertEqual(dec(3, -1.0), "futility")
        self.assertEqual(dec(3, 2.1), "efficacy")
        self.assertEqual(dec(4, -1.0), "final_not_rejected")  # the final look has no futility stop, only a verdict
        self.assertEqual(dec(4, 1.70), "final_not_rejected")
        self.assertEqual(dec(4, 1.71), "efficacy")

    def test_futility_is_non_binding(self):
        d = an.design(DRAFT)
        self.assertAlmostEqual(d["type_i_error"]["without_futility"], 0.05, places=6)
        self.assertLess(d["type_i_error"]["if_futility_followed"], 0.05)
        s = d["scenarios"]["in_sample_11bps_spread_ignored"]
        self.assertLess(s["power_if_futility_followed"], s["power_without_futility"])
        self.assertEqual(d["futility_z"], [None, 0.0, 0.0, None])


class CountedSessions(unittest.TestCase):
    PINS = {"runner_code": {n: "a" * 64 for n in an.RUNNER_CODE},
            "study_code": {"news_signal.py": "b" * 64, "score.py": "c" * 64}}
    SHA = "d" * 64

    def start(self, **over):
        row = {"kind": "lifecycle", "event": "start", "evidence_label": an.RUN_LABEL, "mode": "paper",
               "rth_reversal_active": True, "reversal_protocol_sha256": self.SHA, "code_sha256": dict(self.PINS["runner_code"]),
               "news_signal_sha256": "b" * 64, "score_py_sha256": "c" * 64}
        row.update(over)
        return row

    def test_start_is_the_first_session_after_freeze_and_deployment(self):
        self.assertEqual(an.counted_start(CAL, "2026-09-26T12:00:00Z", "2026-09-25T20:30:00Z"), date(2026, 9, 28))
        # deployed on the Monday before the open: that Monday counts; after the open: Tuesday
        self.assertEqual(an.counted_start(CAL, "2026-09-26T12:00:00Z", "2026-09-28T13:00:00Z"), date(2026, 9, 28))
        self.assertEqual(an.counted_start(CAL, "2026-09-26T12:00:00Z", "2026-09-28T13:31:00Z"), date(2026, 9, 29))
        self.assertEqual(an.counted_start(CAL, "2026-11-25T22:00:00Z", "2026-11-25T22:00:00Z"), date(2026, 11, 27))  # Thanksgiving

    def test_qualification_needs_every_pinned_condition(self):
        self.assertEqual(an.session_qualifies(self.start(), self.SHA, self.PINS), (True, []))
        cases = {"run_label:pilot": {"evidence_label": "pilot"}, "mode:dry-run": {"mode": "dry-run"},
                 "rth_reversal_inactive": {"rth_reversal_active": False}, "protocol_sha256_mismatch": {"reversal_protocol_sha256": "e" * 64},
                 "runner_code_pin:planner.py": {"code_sha256": {**self.PINS["runner_code"], "planner.py": "f" * 64}},
                 "study_code_pin:news_signal.py": {"news_signal_sha256": "0" * 64}}
        for reason, over in cases.items():
            ok, reasons = an.session_qualifies(self.start(**over), self.SHA, self.PINS)
            self.assertFalse(ok)
            self.assertIn(reason, reasons)
        self.assertEqual(an.session_qualifies(None, self.SHA, self.PINS), (False, ["no_start_record"]))
        extra = {**self.PINS["runner_code"], "new_module.py": "1" * 64}
        self.assertIn("runner_code_pin:new_module.py", an.session_qualifies(self.start(code_sha256=extra), self.SHA, self.PINS)[1])

    def test_information_sessions_need_two_filled_names_per_leg_and_a_resolved_reconciled_day(self):
        days = [date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1)]
        rec = {"kind": "reconciliation", "mode": "paper"}
        fills = []
        for d, legs in zip(days, ((2, 2), (2, 1), (3, 2), (2, 2))):
            for leg, n in zip(("long", "short"), legs):
                for i in range(n):
                    fills += fill_pair(d, f"{leg[0].upper()}{i}", leg, 100.0, 100.0, 10)
        holdings = an.fills_by_holding(fills)
        sessions = [(d, [rec], True, []) for d in days]
        self.assertEqual(an.information_sessions(sessions, holdings), [days[0], days[2], days[3]])
        sessions[1] = (days[1], [rec], False, ["mode:dry-run"])  # an excluded session is skipped, not a stop
        self.assertEqual(an.information_sessions(sessions, holdings), [days[0], days[2], days[3]])
        sessions[2] = (days[2], [], True, [])  # no reconciliation record yet: the sequence stops there
        self.assertEqual(an.information_sessions(sessions, holdings), [days[0]])
        open_fill = [f for f in fill_pair(days[0], "OPEN", "long", 100.0, 100.0, 10) if "-rth-" in f["client_order_id"]]
        holdings = an.fills_by_holding(fills + open_fill)  # an unresolved position on the first day
        self.assertEqual(an.information_sessions([(d, [rec], True, []) for d in days], holdings), [])

    def test_fill_rows_are_deduplicated_by_order_id(self):
        pair = fill_pair(date(2026, 9, 28), "DUP", "short", 50.0, 49.0, 20)
        holdings = an.fills_by_holding(pair + [dict(pair[0])])  # a second reconciliation after a restart
        self.assertEqual(an.vwap(holdings[(date(2026, 9, 28), "DUP", "short")]["entry"])[0], 20.0)
        self.assertEqual(an.fills_by_holding([{**pair[0], "client_order_id": "nf1-20260928-rth-DUP-short"}]), {})


def fill_pair(day, sym, leg, entry, exit_, qty, stage="cls1"):
    ymd = day.strftime("%Y%m%d")
    ins, outs = ("buy", "sell") if leg == "long" else ("sell", "buy")
    return [{"kind": "fill", "id": f"{ymd}-{sym}-in", "client_order_id": f"nf1r-{ymd}-rth-{sym}-{leg}", "side": ins,
             "filled_qty": str(qty), "filled_avg_price": str(entry)},
            {"kind": "fill", "id": f"{ymd}-{sym}-out", "client_order_id": f"nf1r-{ymd}-{stage}-{sym}-{leg}", "side": outs,
             "filled_qty": str(qty), "filled_avg_price": str(exit_)}]


class CostMeasurement(unittest.TestCase):
    def test_round_trip_components(self):
        c = an.position_costs(1, 100.05, 101.0, {"bid": "99.95", "ask": "100.05"}, 101.0, 0.0, 10000.0, COSTS)
        self.assertAlmostEqual(c["half_spread_bps"], 5.0)
        self.assertAlmostEqual(c["entry_vs_mid_bps"], 5.0)
        self.assertAlmostEqual(c["entry_vs_touch_bps"], 0.0)  # a paper fill at the ask
        self.assertAlmostEqual(c["exit_vs_close_bps"], 0.0)
        self.assertAlmostEqual(c["measured_vs_mid_bps"], 5.0)
        self.assertAlmostEqual(c["assumed_vs_mid_bps"], 9.0)  # half-spread + 2 + 2 bps (+ fees, 0 here)
        self.assertAlmostEqual(c["measured_beyond_touch_bps"], 0.0)
        self.assertAlmostEqual(c["assumed_beyond_touch_bps"], 4.0)
        # a short filled a nickel below the bid and bought back a dime above the official close
        c = an.position_costs(-1, 99.90, 99.00, {"bid": "99.95", "ask": "100.05"}, 98.90, 1.0, 10000.0, COSTS)
        self.assertAlmostEqual(c["entry_vs_mid_bps"], 10.0)
        self.assertAlmostEqual(c["entry_vs_touch_bps"], 5.0)
        self.assertAlmostEqual(c["exit_vs_close_bps"], 0.1 / 98.90 * 1e4)
        self.assertAlmostEqual(c["fees_bps"], 1.0)
        self.assertAlmostEqual(c["measured_vs_mid_bps"], 10.0 + 0.1 / 98.90 * 1e4 + 1.0)
        no_close = an.position_costs(1, 100.05, 101.0, {"bid": "99.95", "ask": "100.05"}, None, 0.0, 10000.0, COSTS)
        self.assertIsNone(no_close["measured_vs_mid_bps"])

    def test_positions_returns_and_the_per_day_comparison_with_8_4_bps(self):
        day = date(2026, 9, 28)
        rows, fills = [], []
        for sym, leg, entry, exit_ in (("L1", "long", 50.05, 50.55), ("L2", "long", 20.02, 20.12),
                                       ("S1", "short", 49.95, 49.45), ("S2", "short", 30.00, 30.30)):
            cid = f"nf1r-20260928-rth-{sym}-{leg}"
            bid, ask = (entry - 0.1, entry) if leg == "long" else (entry, entry + 0.1)
            rows.append({"kind": "decision", "arm": "rev", "action": "enter", "client_order_id": cid, "symbol": sym,
                         "event_id": f"1:{sym}", "label": "UNFAVORABLE" if leg == "long" else "FAVORABLE",
                         "quote_bid": str(bid), "quote_ask": str(ask)})
            rows.append({"kind": "close_mark", "symbol": sym, "official_close": exit_})
            fills += fill_pair(day, sym, leg, entry, exit_, 100)
        positions, unresolved = an.session_positions(day, rows, an.fills_by_holding(fills), FEES, COSTS)
        self.assertEqual((len(positions), unresolved), (4, []))
        by = {p["symbol"]: p for p in positions}
        self.assertAlmostEqual(by["L1"]["gross"], 50.55 / 50.05 - 1)
        self.assertAlmostEqual(by["S2"]["gross"], -(30.30 / 30.00 - 1))
        self.assertLess(by["L1"]["net"], by["L1"]["gross"])
        self.assertEqual(by["S1"]["label"], "FAVORABLE")
        daily = an.daily_values(positions, "gross")["2026-09-28"]
        self.assertAlmostEqual(daily["long_short"], (by["L1"]["gross"] + by["L2"]["gross"]) / 2 + (by["S1"]["gross"] + by["S2"]["gross"]) / 2)
        summary = an.cost_summary(positions, {"2026-09-28"})
        self.assertEqual((summary["round_trips"], summary["long_short_days_with_costs"]), (4, 1))
        self.assertEqual(summary["historical_assumption_bps_per_long_short_day"], 8.4)
        # fills at the touch and exits at the close: the measured beyond-touch cost is the fees alone
        self.assertAlmostEqual(summary["mean_entry_vs_touch_bps"], 0.0)
        fees = [p["cost"]["fees_bps"] for p in positions]
        long_fees, short_fees = (fees[0] + fees[1]) / 2, (fees[2] + fees[3]) / 2
        self.assertAlmostEqual(summary["mean_measured_beyond_touch_bps_per_long_short_day"], long_fees + short_fees)

    def test_unresolved_positions_are_not_priced(self):
        day = date(2026, 9, 28)
        fills = fill_pair(day, "HALF", "long", 10.0, 10.5, 100)
        fills[1]["filled_qty"] = "60"  # 40 shares still open (e.g. an exit that fills tomorrow)
        positions, unresolved = an.session_positions(day, [], an.fills_by_holding(fills), FEES, COSTS)
        self.assertEqual((positions, [(u["symbol"], u["entry_qty"], u["exit_qty"]) for u in unresolved]), ([], [("HALF", 100.0, 60.0)]))


class HarmStops(unittest.TestCase):
    HARM = DRAFT["harm_stops"]

    def pos(self, net, notional=100000.0, measured=5.0, assumed=9.0):
        return {"net": net, "notional": notional, "cost": {"measured_vs_mid_bps": measured, "assumed_vs_mid_bps": assumed}}

    def test_drawdown_against_ten_percent_of_average_gross(self):
        # 200k gross a day; a 10% threshold is 20k: +10k, -15k, -6k -> peak 10k, trough -11k, drawdown 21k
        days = [(d, [self.pos(x), self.pos(x)]) for d, x in ((1, 0.05), (2, -0.075), (3, -0.03))]
        r = an.harm_check(days, self.HARM)
        self.assertAlmostEqual(r["max_net_drawdown_usd"], 21000.0)
        self.assertAlmostEqual(r["drawdown_threshold_usd"], 20000.0)
        self.assertEqual(r["reasons"], ["cumulative_net_drawdown"])
        r = an.harm_check(days[:2], self.HARM)  # 15k so far: below the stop
        self.assertFalse(r["harm_stop"])

    def test_cost_stop_only_from_the_60th_session(self):
        days = [(i, [self.pos(0.0, measured=20.0, assumed=9.0)]) for i in range(59)]
        self.assertFalse(an.harm_check(days, self.HARM)["cost_checked"])
        r = an.harm_check(days + [(59, [self.pos(0.0, measured=20.0, assumed=9.0)])], self.HARM)
        self.assertEqual((r["cost_checked"], r["reasons"]), (True, ["execution_cost_above_twice_assumed"]))
        r = an.harm_check([(i, [self.pos(0.0, measured=18.0, assumed=9.0)]) for i in range(60)], self.HARM)
        self.assertFalse(r["harm_stop"])  # exactly twice the assumption: not above it


class ProtocolDraft(unittest.TestCase):
    def test_draft_status_and_consistency_with_code(self):
        p = DRAFT
        self.assertEqual((p["status"], p["frozen_before_outcomes"], p["frozen_at"]),
                         ("draft_pending_independent_pre_outcome_review", False, None))
        self.assertEqual(p["frozen_status_value"], an.FROZEN_STATUS)
        self.assertEqual(p["sequential_plan"]["looks_sessions"], [60, 125, 250, 375])
        self.assertEqual(p["sequential_plan"]["alpha_one_sided"], 0.05)
        self.assertEqual(p["sequential_plan"]["futility"], {**p["sequential_plan"]["futility"], "looks": [2, 3], "z_at_or_below": 0.0})
        self.assertEqual((p["harm_stops"]["drawdown_fraction_of_average_gross"], p["harm_stops"]["cost_check_after_sessions"],
                          p["harm_stops"]["cost_multiple"]), (0.10, 60, 2.0))
        self.assertEqual((COSTS["rth_entry_allowance_bps"], COSTS["exit_allowance_bps"]), (2.0, 2.0))

    def test_design_numbers_are_reproduced(self):
        d, pd = an.design(DRAFT), DRAFT["design_numbers"]
        self.assertAlmostEqual(d["obf_constant"], pd["obf_constant"], places=4)
        for got, want in zip(d["efficacy_z"], pd["efficacy_z"]):
            self.assertAlmostEqual(got, want, places=4)
        self.assertEqual(d["futility_z"], pd["futility_z"])
        for name, s in pd["power_at_375_max"].items():
            for key in ("power_without_futility", "power_if_futility_followed", "futility_stop_probability"):
                self.assertAlmostEqual(d["scenarios"][name][key], s[key], delta=0.0006, msg=(name, key))
            self.assertEqual(round(d["scenarios"][name]["expected_sessions_if_futility_followed"]),
                             s["expected_sessions_if_futility_followed"])
        self.assertAlmostEqual(d["type_i_error"]["if_futility_followed"], pd["type_i_error"]["if_futility_followed"], places=4)

    def test_origin_matches_the_frozen_study_receipt(self):
        summary = json.loads((ROOT / "blueprints/us-equities/sota-mover/news-llm/receipts/evaluation-summary.json").read_text())
        n3, o = summary["items"]["NEWS-3"], DRAFT["origin"]["in_sample_estimate"]
        self.assertEqual(summary["protocol_sha256"][:8], "bba1b157")
        self.assertEqual(o["days"], n3["gross"]["n_days"])
        self.assertAlmostEqual(o["gross_mean_bps_per_day"], n3["gross"]["mean"] * 1e4, places=3)
        self.assertAlmostEqual(o["net_mean_bps_per_day"], n3["net"]["mean"] * 1e4, places=3)
        self.assertAlmostEqual(o["gross_sd_bps_nw_effective"], n3["gross"]["se_nw"] * math.sqrt(n3["gross"]["n_days"]) * 1e4, places=1)
        self.assertAlmostEqual(o["modelled_cost_bps_per_day"], (n3["gross"]["mean"] - n3["net"]["mean"]) * 1e4, places=3)

    def test_runner_constants_match_the_rule(self):
        sys.path.insert(0, str(FORWARD))
        import common  # noqa: PLC0415
        import planner  # noqa: PLC0415
        import supervisor  # noqa: PLC0415
        self.assertEqual(planner.ARM_PREFIX[planner.REV], an.REV_PREFIX)
        self.assertEqual(common.REVERSAL_RUN_LABEL, an.RUN_LABEL)
        self.assertEqual(supervisor.HALT_REVERSAL, an.HALT_FILE)
        self.assertEqual((planner.REV_QUOTE_WINDOW, planner.REV_ENTRY_TTL), (timedelta(seconds=60), timedelta(seconds=60)))
        self.assertEqual((planner.MAX_SPREAD_BPS, planner.MAX_NAMES_PER_LEG, str(planner.NET_CAP_FRACTION)), (50, 12, "0.10"))
        self.assertEqual(set(an.RUNNER_CODE), {n.name for n in FORWARD.glob("*.py")})  # the start record hashes exactly these

    def test_pins_match_the_files(self):
        pins = DRAFT["pins"]
        self.assertIsNotNone(pins, "run `python analyze.py pins` and copy the result into forward-protocol.json#/pins")
        current = an.compute_pins(STUDY, ROOT)
        self.assertEqual({g: pins[g] for g in current}, current, "re-pin: python analyze.py pins")

    def test_the_runner_executes_the_frozen_study_code(self):
        study = json.loads((ROOT / "blueprints/us-equities/sota-mover/news-llm/protocol.json").read_text())["pins"]
        pins = DRAFT["pins"]
        self.assertEqual(pins["study_code"], {n: study["code"][n] for n in an.STUDY_CODE})
        self.assertEqual(pins["reference"], study["reference"])


class GuardRefusals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, obj):
        path = self.dir / name
        path.write_text(obj if isinstance(obj, str) else json.dumps(obj))
        return path

    def test_freeze_and_deployment_records_are_required_and_complete(self):
        with self.assertRaises(an.Refusal):
            an.read_freeze_record(self.dir / "missing.json")
        with self.assertRaises(an.Refusal):
            an.read_freeze_record(self.write("bad.json", "{not json"))
        with self.assertRaises(an.Refusal):
            an.read_freeze_record(self.write("f.json", {"protocol_sha256": "a" * 64, "protocol_commit": "abc"}))
        self.assertEqual(an.read_freeze_record(self.write("g.json", {"protocol_sha256": "A" * 64, "protocol_commit": "b" * 40})),
                         ("a" * 64, "b" * 40))
        with self.assertRaises(an.Refusal):
            an.read_deployment_record(self.dir / "missing.json")
        with self.assertRaises(an.Refusal):
            an.read_deployment_record(self.write("d1.json", {"deployed_at": None, "deployed_commit": "c" * 40}))
        with self.assertRaises(an.Refusal):
            an.read_deployment_record(self.write("d2.json", {"deployed_at": "2026-09-25T20:30:00Z", "deployed_commit": "c" * 7}))
        at, commit = an.read_deployment_record(self.write("d3.json", {"deployed_at": "2026-09-25T20:30:00Z", "deployed_commit": "c" * 40}))
        self.assertEqual((at, commit), (datetime(2026, 9, 25, 20, 30, tzinfo=timezone.utc), "c" * 40))

    def test_templates_are_not_valid_records(self):
        with self.assertRaises(an.Refusal):
            an.read_freeze_record(STUDY / "receipts" / "freeze-record.template.json")
        with self.assertRaises(an.Refusal):
            an.read_deployment_record(STUDY / "receipts" / "deployment-record.template.json")

    def test_the_committed_draft_is_refused_even_with_its_own_sha(self):
        raw = (STUDY / "forward-protocol.json").read_bytes()
        with self.assertRaises(an.Refusal) as ctx:
            an.guard(STUDY / "forward-protocol.json", an.hashlib.sha256(raw).hexdigest())
        self.assertIn("not frozen", ctx.exception.reason)

    def test_guard_needs_the_sha_and_every_freeze_field(self):
        frozen = {**DRAFT, "status": "frozen_pre_outcome", "frozen_before_outcomes": True, "frozen_at": "2026-09-26T12:00:00Z"}
        path = self.write("forward-protocol.json", json.dumps(frozen))
        digest = an.sha256_file(path)
        self.assertIsInstance(an.guard(path, digest.upper()), an.FrozenProtocol)
        with self.assertRaises(an.Refusal):
            an.guard(path, "0" * 64)
        for field, value in (("frozen_before_outcomes", False), ("frozen_at", None), ("status", "frozen")):
            path = self.write("forward-protocol.json", json.dumps({**frozen, field: value}))
            with self.assertRaises(an.Refusal, msg=field):
                an.guard(path, an.sha256_file(path))

    def test_tokens_cannot_be_forged(self):
        frozen = {**DRAFT, "status": "frozen_pre_outcome", "frozen_before_outcomes": True, "frozen_at": "2026-09-26T12:00:00Z"}
        path = self.write("forward-protocol.json", json.dumps(frozen))
        fp = an.guard(path, an.sha256_file(path))
        with self.assertRaises(an.Refusal):
            an.FrozenProtocol({}, "a" * 64, "p", object())
        with self.assertRaises(an.Refusal):
            an.Authorization(fp, "0" * 40, "c" * 40, datetime.now(timezone.utc), "d" * 40, STUDY, self.dir, ROOT, object())
        fake = SimpleNamespace(frozen=fp, state_root=self.dir, repo_root=ROOT, _token=object())
        for call in (lambda t: an.load_sessions(t, CAL), lambda t: an.run_look(t), lambda t: an.run_monitor(t)):
            for bad in (None, fake, fp):
                with self.assertRaises(an.Refusal):
                    call(bad)

    def test_main_refuses_the_repository_draft(self):
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = an.main(["look", "--state", str(self.dir)])
        self.assertEqual(code, 2)
        self.assertIn("REFUSED", err.getvalue())


def git(cwd, *args):
    out = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args], cwd=cwd,
                         capture_output=True, text=True, env=hermetic_git_environment())
    if out.returncode != 0:
        raise AssertionError(out.stderr)
    return out.stdout.strip()


class GuardedRunInGit(unittest.TestCase):
    """authorize(), a look and the monitor in a scratch repository with synthetic journals."""

    FROZEN_AT = "2026-09-26T12:00:00Z"
    DEPLOYED_AT = "2026-09-26T20:00:00Z"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo = base / "repo"
        self.study = self.repo / STUDY_REL
        (self.study / "receipts").mkdir(parents=True)
        shutil.copy(STUDY / "analyze.py", self.study / "analyze.py")
        for group, files in an.pin_paths(STUDY, ROOT).items():
            for name, src in files.items():
                dst = an.pin_paths(self.study, self.repo)[group][name]
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, dst)
        self.state = base / "state"
        (self.state / "journal").mkdir(parents=True)
        git(self.repo, "init", "-q")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "code")
        protocol = copy.deepcopy(DRAFT)
        protocol.update(status="frozen_pre_outcome", frozen_before_outcomes=True, frozen_at=self.FROZEN_AT,
                        pins=an.compute_pins(self.study, self.repo))
        (self.study / "forward-protocol.json").write_text(json.dumps(protocol, indent=1))
        self.sha = an.sha256_file(self.study / "forward-protocol.json")
        self.pins = protocol["pins"]
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "freeze")
        self.freeze_commit = git(self.repo, "rev-parse", "HEAD")
        (self.study / "receipts" / "freeze-record.json").write_text(json.dumps(
            {"protocol_sha256": self.sha, "protocol_commit": self.freeze_commit}))
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "freeze record")
        (self.study / "receipts" / "deployment-record.json").write_text(json.dumps(
            {"deployed_at": self.DEPLOYED_AT, "deployed_commit": git(self.repo, "rev-parse", "HEAD")}))
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "deployment record")

    def tearDown(self):
        self.tmp.cleanup()

    def args(self, **kw):
        return SimpleNamespace(state=self.state, freeze_record=None, deployment_record=None, protocol_sha256=kw.get("sha"))

    def authorize(self):
        return an.authorize(self.args(), study_dir=self.study, repo_root=self.repo)

    def start_row(self, **over):
        row = {"kind": "lifecycle", "event": "start", "evidence_label": an.RUN_LABEL, "mode": "paper",
               "rth_reversal_active": True, "reversal_protocol_sha256": self.sha, "code_sha256": self.pins["runner_code"],
               "news_signal_sha256": self.pins["study_code"]["news_signal.py"], "score_py_sha256": self.pins["study_code"]["score.py"]}
        row.update(over)
        return row

    def write_day(self, day, gross_long, gross_short, start=None, reconciled=True):
        rows = [start or self.start_row()]
        for i, (leg, g) in enumerate((("long", gross_long), ("long", gross_long), ("short", gross_short), ("short", gross_short))):
            sym, entry = f"{leg[0].upper()}{i}", 50.0
            exit_ = entry * (1 + g) if leg == "long" else entry * (1 - g)
            cid = f"nf1r-{day.strftime('%Y%m%d')}-rth-{sym}-{leg}"
            rows.append({"kind": "decision", "arm": "rev", "action": "enter", "client_order_id": cid, "symbol": sym,
                         "event_id": f"{i}:{sym}", "quote_bid": "49.99" if leg == "long" else "50.0",
                         "quote_ask": "50.0" if leg == "long" else "50.01"})
            rows.append({"kind": "close_mark", "symbol": sym, "official_close": exit_})
            rows += fill_pair(day, sym, leg, entry, exit_, 100)
        if reconciled:
            rows.append({"kind": "reconciliation", "mode": "paper", "ok": True})
        with open(an.journal_path(self.state, day), "w", encoding="utf-8") as handle:
            for r in rows:
                handle.write(json.dumps(r) + "\n")

    def sessions_from(self, start, n):
        return [s.session for s in CAL.sessions if s.session >= start][:n]

    def test_authorize_and_a_look_that_never_opens_pilot_days(self):
        self.write_day(date(2026, 9, 25), 0.5, 0.5, start=self.start_row(evidence_label="pilot"))  # the pilot day
        days = self.sessions_from(date(2026, 9, 28), 62)
        rng = random.Random(11)
        legs = [0.004 + rng.gauss(0.0, 0.001) for _ in days]  # a strong synthetic reversal: each leg +0.4% +/- noise
        for d, g in zip(days, legs):
            self.write_day(d, g, g)
        auth = self.authorize()
        opened = []
        real = an.read_jsonl
        with mock.patch.object(an, "read_jsonl", side_effect=lambda p: opened.append(Path(p).name) or real(p)):
            receipt = an.run_look(auth, until=date(2027, 12, 31))
        self.assertNotIn("2026-09-25.jsonl", opened)
        self.assertEqual((receipt["look"], receipt["counted_start"], receipt["sessions_used"]["count"]), (1, "2026-09-28", 60))
        self.assertEqual(receipt["sessions_used"]["last"], days[59].isoformat())
        self.assertEqual(receipt["look_decision"], "efficacy")
        self.assertNotIn("decision", json.dumps(receipt).replace("look_decision", ""))  # no blueprint label key
        self.assertAlmostEqual(receipt["primary"]["mean_bps"], 2 * sum(legs[:60]) / 60 * 1e4, places=6)  # long + short leg
        self.assertAlmostEqual(receipt["primary"]["efficacy_boundary_z"], 4.27407, places=4)
        self.assertEqual(receipt["execution_cost"]["round_trips"], 240)
        written = self.study / "receipts" / "look-1.json"
        self.assertTrue(written.exists() and Path(str(written) + ".sha256").exists())
        with self.assertRaises(an.Refusal) as ctx:  # the receipt must be committed before anything else runs
            self.authorize()
        self.assertIn("uncommitted", ctx.exception.reason)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "look 1")
        with self.assertRaises(an.Refusal) as ctx:
            an.run_look(self.authorize(), until=date(2027, 12, 31))
        self.assertIn("stopped at look 1", ctx.exception.reason)

    def test_a_look_waits_for_its_sessions_and_excluded_days_do_not_count(self):
        days = self.sessions_from(date(2026, 9, 28), 61)
        rng = random.Random(5)
        for i, d in enumerate(days[:60]):
            g = rng.gauss(0.0, 0.002)
            start = self.start_row(mode="dry-run") if i == 3 else None  # one excluded session (known at its start)
            self.write_day(d, g, g, start=start)
        with self.assertRaises(an.Refusal) as ctx:
            an.run_look(self.authorize(), until=date(2027, 12, 31))
        self.assertIn("look 1 needs 60 counted long-short sessions; 59 are complete", ctx.exception.reason)
        self.write_day(days[60], 0.001, 0.001)
        receipt = an.run_look(self.authorize(), until=date(2027, 12, 31))
        self.assertEqual((receipt["look_decision"], receipt["excluded_sessions"]), ("continue", {"mode:dry-run": 1}))
        self.assertEqual(receipt["sessions_used"], {"first": days[0].isoformat(), "last": days[60].isoformat(), "count": 60})

    def test_monitor_reports_harm_only_and_writes_the_halt_file(self):
        days = self.sessions_from(date(2026, 9, 28), 5)
        # 4 positions of $5,000 a day: the stop is 10% of $20,000; days 2-4 lose about $1,000 each
        for d, g in zip(days, (0.01, -0.05, -0.05, -0.05, 0.0)):
            self.write_day(d, g, g)
        result = an.run_monitor(self.authorize(), apply=True, until=date(2027, 12, 31))
        self.assertTrue(result["harm_stop"])
        self.assertEqual(result["reasons"], ["cumulative_net_drawdown"])
        self.assertNotIn("t_nw", json.dumps(result))  # never the primary statistic
        self.assertTrue((self.state / an.HALT_FILE).exists())
        self.assertTrue(any((self.state / "reversal-monitor").iterdir()))

    def test_refusals_in_git(self):
        with self.assertRaises(an.Refusal):
            an.authorize(self.args(sha="0" * 64), study_dir=self.study, repo_root=self.repo)
        (self.study / "scratch.txt").write_text("x")
        with self.assertRaises(an.Refusal) as ctx:
            self.authorize()
        self.assertIn("uncommitted", ctx.exception.reason)
        (self.study / "scratch.txt").unlink()
        planner_copy = an.pin_paths(self.study, self.repo)["runner_code"]["planner.py"]
        original = planner_copy.read_bytes()
        planner_copy.write_bytes(original + b"\n# changed after the freeze\n")
        with self.assertRaises(an.Refusal) as ctx:
            self.authorize()
        self.assertIn("pin mismatch: runner_code/planner.py", ctx.exception.reason)
        planner_copy.write_bytes(original)
        # a deployment from a commit that does not descend from the freeze commit
        first = git(self.repo, "rev-list", "--max-parents=0", "HEAD")
        (self.study / "receipts" / "deployment-record.json").write_text(json.dumps(
            {"deployed_at": self.DEPLOYED_AT, "deployed_commit": first}))
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "deployment record from the code commit")
        with self.assertRaises(an.Refusal) as ctx:
            self.authorize()
        self.assertIn("does not descend from the freeze commit", ctx.exception.reason)
        git(self.repo, "checkout", "-q", "--orphan", "other")
        git(self.repo, "commit", "-q", "-m", "unrelated")
        with self.assertRaises(an.Refusal) as ctx:
            self.authorize()
        self.assertIn("not an ancestor", ctx.exception.reason)


if __name__ == "__main__":
    unittest.main()
