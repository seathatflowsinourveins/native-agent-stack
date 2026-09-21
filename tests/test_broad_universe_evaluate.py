"""Local integration checks for the broad-universe chronological evaluator.

Synthetic fixtures only: no network, no credentials, no real dataset, no broker.
Nothing here is upstream or broker acceptance; it proves the leakage, calendar,
execution, cost, label and selection arithmetic of evaluate.py against hand-computed
numbers. The frozen protocol.json is read read-only for its predeclared constants.
"""
from datetime import date, timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

import duckdb
import numpy as np

REPO = Path(__file__).resolve().parents[1]
BLUEPRINT = REPO / "blueprints/us-equities/broad-universe"
SPEC = importlib.util.spec_from_file_location("evaluate", BLUEPRINT / "evaluate.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

PROTOCOL_PATH = str(BLUEPRINT / "protocol.json")
PROTOCOL, SETTINGS = m.load_protocol(PROTOCOL_PATH)

# A synthetic calendar of weekly Mondays. Session order is what the protocol counts, so a
# weekly spacing keeps fixtures small while still landing decisions in each named segment.
EPOCH = date(2016, 1, 4)
CAL = [EPOCH + timedelta(days=7 * i) for i in range(400)]

# A second calendar whose first 70 sessions are daily inside the warmup year, so that a
# decision (which needs 60 prior bars) can land on each named chronology boundary.
SEG_CAL = ([EPOCH + timedelta(days=i) for i in range(70)] +
           [date(2017, 1, 2), date(2021, 12, 31), date(2022, 1, 3), date(2023, 12, 29),
            date(2024, 1, 2), date(2026, 8, 14), date(2026, 8, 17)])
SEG_EXPECTED = {60: "warmup", 69: "warmup", 70: "development", 71: "development",
                72: "validation", 73: "validation", 74: "reserved", 75: "reserved",
                76: "out_of_scope"}

COLUMNS = ("symbol", "session_date", "raw_o", "raw_h", "raw_l", "raw_c", "raw_v", "raw_n", "raw_vw",
           "all_o", "all_h", "all_l", "all_c", "in_raw", "in_all")
DDL = ("CREATE TABLE d (symbol VARCHAR, session_date DATE, raw_o DOUBLE, raw_h DOUBLE, raw_l DOUBLE,"
       " raw_c DOUBLE, raw_v DOUBLE, raw_n BIGINT, raw_vw DOUBLE, all_o DOUBLE, all_h DOUBLE,"
       " all_l DOUBLE, all_c DOUBLE, in_raw BOOLEAN, in_all BOOLEAN)")


def bar(symbol, idx, c=100.0, v=1_000_000.0, o=None, h=None, low=None,
        ac=None, ao=None, ah=None, al=None, in_raw=True, in_all=True, cal=None):
    """One contract row. Defaults keep raw == adjusted and high == low (clv 0.5)."""
    o = c if o is None else o
    h = max(o, c) if h is None else h
    low = min(o, c) if low is None else low
    ac = c if ac is None else ac
    ao = o if ao is None else ao
    ah = h if ah is None else ah
    al = low if al is None else al
    return (symbol, (CAL if cal is None else cal)[idx], o, h, low, c, v, 1000, c,
            ao, ah, al, ac, in_raw, in_all)


def spy(count, start=0, v=1000.0, cal=None):
    """SPY defines the calendar; a tiny dollar volume keeps it out of every decision set."""
    return [bar("SPY", i, c=100.0, v=v, cal=cal) for i in range(start, count)]


def write_daily(path, rows):
    con = duckdb.connect()
    con.execute(DDL)
    con.executemany("INSERT INTO d VALUES (" + ", ".join("?" * len(COLUMNS)) + ")", rows)
    con.execute(f"COPY d TO {m.sql_literal(path)} (FORMAT PARQUET)")
    con.close()


class Fixture:
    """A built evaluator state over synthetic rows; caller closes it."""

    def __init__(self, rows, names=(), stats=False):
        self.dir = tempfile.mkdtemp(prefix="bue-test-")
        self.daily = os.path.join(self.dir, "daily.parquet")
        write_daily(self.daily, rows)
        self.con = m.connect(os.path.join(self.dir, "duckdb-temp"), "2GB", 2)
        self.dataset = m.build_calendar(self.con, self.daily)
        m.build_features(self.con)
        self.gates = m.build_decisions(self.con, SETTINGS, list(names))
        self.events = m.build_events(self.con, SETTINGS)
        if stats:
            m.build_selections(self.con)
            m.build_stats(self.con)

    def rows(self, sql, *params):
        return self.con.execute(sql, list(params)).fetchall()

    def one(self, sql, *params):
        return self.con.execute(sql, list(params)).fetchone()

    def dicts(self, sql, *params):
        rows = self.con.execute(sql, list(params)).fetchall()
        columns = [d[0] for d in self.con.description]
        return [dict(zip(columns, row)) for row in rows]

    def close(self):
        self.con.close()
        shutil.rmtree(self.dir, ignore_errors=True)


class EvaluatorCase(unittest.TestCase):
    def build(self, rows, names=(), stats=False):
        fixture = Fixture(rows, names=names, stats=stats)
        self.addCleanup(fixture.close)
        return fixture


# --------------------------------------------------------------------- (1) no look-ahead

T_LOOK = 150
N_LOOK = 200


def lookahead_rows(scale=1.0):
    """AAA: flat prices, a ramped 20-session dollar-volume window before t, one old high.

    `scale` multiplies every AAA and SPY value on sessions strictly after t; nothing at or
    before t may move when it changes.
    """
    rows = []
    for i in range(N_LOOK):
        factor = scale if i > T_LOOK else 1.0
        volume = 1_000_000.0
        if T_LOOK - 20 <= i <= T_LOOK - 1:
            volume = (i - (T_LOOK - 20) + 1) * 1_000_000.0
        elif i == T_LOOK:
            volume = 21_000_000.0
        ah = 150.0 if i == T_LOOK - 30 else (10_000.0 if i == T_LOOK else 100.0)
        rows.append(bar("AAA", i, c=100.0 * factor, v=volume * factor, ah=ah * factor))
        rows.append(bar("SPY", i, c=100.0 * factor, v=1000.0))
    return rows


class NoLookAhead(EvaluatorCase):
    def features(self, fixture):
        return fixture.dicts(
            "SELECT c.dv, c.med20, c.r1, c.r5, c.high60, c.high20, c.clv, c.gap, c.range10,"
            " c.range10_p20, c.span60, c.span130, d.c1, d.s1, d.s2, d.s3, d.s4, d.s5,"
            " d.segment, d.cost_bps, d.dv_ratio"
            " FROM decisions d JOIN candidates c USING (symbol, cal_idx)"
            " WHERE d.symbol = 'AAA' AND d.universe = 'main' AND d.session_date = ?",
            CAL[T_LOOK])[0]

    def test_windows_exclude_t_and_match_hand_computed_values(self):
        got = self.features(self.build(lookahead_rows()))
        # dv uses session t itself; med20 is the median of the 20 sessions strictly before t.
        self.assertAlmostEqual(got["dv"], 21e8)
        self.assertAlmostEqual(got["med20"], 10.5e8)  # median(1e8..20e8); 11e8 if t leaked in
        self.assertAlmostEqual(got["dv_ratio"], 2.0)
        # high60/high20 read t-60..t-1 and t-20..t-1; the 10,000 high on t must not appear.
        self.assertAlmostEqual(got["high60"], 150.0)
        self.assertAlmostEqual(got["high20"], 100.0)
        # range10 is evaluated at u = t-1, so t's 10,000 high cannot enter it.
        self.assertAlmostEqual(got["range10"], 0.0)
        self.assertAlmostEqual(got["range10_p20"], 0.0)
        self.assertAlmostEqual(got["r1"], 0.0)
        self.assertAlmostEqual(got["r5"], 0.0)
        self.assertAlmostEqual(got["gap"], 0.0)
        self.assertAlmostEqual(got["clv"], 0.5)
        self.assertEqual((got["span60"], got["span130"]), (60, 130))
        self.assertEqual(got["segment"], "development")
        self.assertEqual([got["s1"], got["s2"], got["s3"], got["s4"], got["s5"]], [False] * 5)

    def test_mutating_every_bar_after_t_changes_nothing_at_t(self):
        base = self.features(self.build(lookahead_rows(scale=1.0)))
        moved = self.features(self.build(lookahead_rows(scale=3.7)))
        self.assertEqual(base, moved)

    def test_eligibility_needs_sixty_prior_bars(self):
        fixture = self.build(lookahead_rows())
        first = fixture.one("SELECT min(cal_idx) FROM decisions WHERE symbol = 'AAA'")[0]
        self.assertEqual(first, 60)
        self.assertEqual(fixture.one(
            "SELECT count(*) FROM candidates WHERE symbol = 'AAA' AND insufficient_history")[0], 60)


# ------------------------------------------------------- (2) entry and exit calendar align

T_EXIT = 150


def exit_rows(count=200):
    rows = spy(count)
    for i in range(count):
        rows.append(bar("BBB", i, c=100.0, v=1_000_000.0,
                        ao=1000.0 + i, ac=2000.0 + i, ah=3000.0 + i, al=500.0 + i))
    return rows


class EntryAndExit(EvaluatorCase):
    def test_entry_is_the_next_session_open_and_exits_land_on_t_plus_h(self):
        fixture = self.build(exit_rows())
        rows = {r["horizon"]: r for r in fixture.dicts(
            "SELECT horizon, entry_date, entry_px, exit_date, exit_bar_date, exit_px, outcome,"
            " exit_stale, terminated_early FROM ev"
            " WHERE symbol = 'BBB' AND universe = 'main' AND session_date = ?", CAL[T_EXIT])}
        for horizon, step in m.HORIZONS:
            got = rows[horizon]
            self.assertEqual(got["outcome"], "scored")
            self.assertEqual(got["entry_date"], CAL[T_EXIT + 1])
            self.assertAlmostEqual(got["entry_px"], 1000.0 + T_EXIT + 1)
            self.assertEqual(got["exit_date"], CAL[T_EXIT + step])
            self.assertEqual(got["exit_bar_date"], CAL[T_EXIT + step])
            self.assertAlmostEqual(got["exit_px"], 2000.0 + T_EXIT + step)
            self.assertFalse(got["exit_stale"])
            self.assertFalse(got["terminated_early"])


# ----------------------------------------- (3) no_entry, exit_stale, terminated_early, gap

T_OUT = 150
N_OUT = 175
T_INC = 171


def outcome_rows():
    rows = spy(N_OUT)
    for i in range(N_OUT):
        if i != T_OUT + 1:  # no bar on the entry session
            rows.append(bar("NOE", i))
        if i != T_OUT + 5:  # bar missing on the H5 exit session, series continues
            rows.append(bar("STL", i, ac=300.0 if i == T_OUT + 4 else 100.0))
        if i <= T_OUT + 3:  # series terminates three sessions after the decision
            rows.append(bar("TRM", i, ac=80.0 if i == T_OUT + 3 else 100.0))
        rows.append(bar("INC", i))
    return rows


class Outcomes(EvaluatorCase):
    def setUp(self):
        self.fixture = self.build(outcome_rows())

    def events(self, symbol, decision):
        return {r["horizon"]: r for r in self.fixture.dicts(
            "SELECT horizon, outcome, entry_px, exit_px, exit_bar_date, exit_stale,"
            " terminated_early, net, stress_net, cost_bps FROM ev"
            " WHERE symbol = ? AND universe = 'main' AND session_date = ?", symbol, CAL[decision])}

    def test_missing_entry_bar_is_no_entry_and_never_scored(self):
        for horizon, got in self.events("NOE", T_OUT).items():
            self.assertEqual(got["outcome"], "no_entry", horizon)
            self.assertIsNone(got["net"])
            self.assertIsNone(got["stress_net"])

    def test_missing_exit_bar_with_a_later_bar_is_exit_stale(self):
        got = self.events("STL", T_OUT)
        self.assertEqual(got["H5"]["outcome"], "scored")
        self.assertTrue(got["H5"]["exit_stale"])
        self.assertFalse(got["H5"]["terminated_early"])
        self.assertEqual(got["H5"]["exit_bar_date"], CAL[T_OUT + 4])
        self.assertAlmostEqual(got["H5"]["exit_px"], 300.0)
        self.assertFalse(got["H1"]["exit_stale"])

    def test_series_ending_early_is_terminated_early_and_stress_halves_the_exit(self):
        got = self.events("TRM", T_OUT)
        self.assertFalse(got["H1"]["terminated_early"])
        for horizon in ("H5", "H20"):
            row = got[horizon]
            self.assertEqual(row["outcome"], "scored")
            self.assertTrue(row["terminated_early"])
            self.assertEqual(row["exit_bar_date"], CAL[T_OUT + 3])
            self.assertAlmostEqual(row["exit_px"], 80.0)
            c = row["cost_bps"] / 10000.0
            self.assertAlmostEqual(row["net"], 80.0 / 100.0 * (1 - c) / (1 + c) - 1)
            self.assertAlmostEqual(row["stress_net"],
                                   40.0 / 100.0 * (1 - 3 * c) / (1 + 3 * c) - 1)

    def test_horizon_beyond_the_calendar_is_incomplete_and_never_zero(self):
        got = self.events("INC", T_INC)
        self.assertEqual(got["H1"]["outcome"], "scored")
        for horizon in ("H5", "H20"):
            self.assertEqual(got[horizon]["outcome"], "horizon_incomplete")
            self.assertIsNone(got[horizon]["net"])
            self.assertIsNone(got[horizon]["stress_net"])


# -------------------------------------------------- (4) cost tiers and net return formula

T_COST = 150
TIERS = (("HIG", 1_500_000.0, 5.0), ("MID", 700_000.0, 10.0), ("LOW", 300_000.0, 20.0))


def cost_rows(count=200):
    rows = spy(count)
    for symbol, volume, _bps in TIERS:
        for i in range(count):
            rows.append(bar(symbol, i, c=100.0, v=volume,
                            ac=110.0 if i == T_COST + 1 else 100.0, ao=100.0))
    for i in range(count):  # microcap-only name: $2 close, $3M dollar volume
        rows.append(bar("MIC", i, c=2.0, v=1_500_000.0,
                        ac=2.2 if i == T_COST + 1 else 2.0, ao=2.0))
    return rows


class CostsAndReturns(EvaluatorCase):
    def setUp(self):
        self.fixture = self.build(cost_rows())

    def test_cost_tier_comes_from_med20_and_the_net_formula_is_exact(self):
        for symbol, _volume, bps in TIERS:
            got = self.fixture.dicts(
                "SELECT cost_bps, entry_px, exit_px, net, stress_net FROM ev"
                " WHERE universe = 'main' AND horizon = 'H1' AND symbol = ? AND session_date = ?",
                symbol, CAL[T_COST])[0]
            self.assertAlmostEqual(got["cost_bps"], bps, msg=symbol)
            c = bps / 10000.0
            self.assertAlmostEqual(got["entry_px"], 100.0)
            self.assertAlmostEqual(got["exit_px"], 110.0)
            self.assertAlmostEqual(got["net"], 1.1 * (1 - c) / (1 + c) - 1)
            self.assertAlmostEqual(got["stress_net"], 1.1 * (1 - 3 * c) / (1 + 3 * c) - 1)

    def test_microcap_lane_uses_its_own_floors_and_fifty_basis_points(self):
        rows = self.fixture.dicts(
            "SELECT universe, cost_bps, net FROM ev"
            " WHERE horizon = 'H1' AND symbol = 'MIC' AND session_date = ?", CAL[T_COST])
        self.assertEqual([r["universe"] for r in rows], ["micro"])
        self.assertAlmostEqual(rows[0]["cost_bps"], 50.0)
        c = 0.005
        self.assertAlmostEqual(rows[0]["net"], 1.1 * (1 - c) / (1 + c) - 1)
        # A $2 close is below the $5 primary floor, so the name never reaches the main universe.
        self.assertEqual(self.fixture.one(
            "SELECT count(*) FROM decisions WHERE symbol = 'MIC' AND universe = 'main'")[0], 0)


# ------------------------------------------------------------------- (5) has_gap exclusion

T_GAP = 150
GAP_AT = 120


def gap_rows(count=200):
    rows = spy(count)
    rows += [bar("GAP", i) for i in range(count) if i != GAP_AT]
    return rows


class Contiguity(EvaluatorCase):
    def test_a_missing_session_blocks_decisions_until_the_window_clears(self):
        fixture = self.build(gap_rows())
        flagged = fixture.dicts(
            "SELECT cal_idx, has_gap, span60 FROM candidates WHERE symbol = 'GAP'"
            " AND has_gap ORDER BY cal_idx")
        # Exactly the 60 decisions whose 60-bar window still straddles the hole.
        self.assertEqual([r["cal_idx"] for r in flagged],
                         list(range(GAP_AT + 1, GAP_AT + 61)))
        self.assertTrue(all(r["span60"] == 61 for r in flagged))
        excluded = {r["cal_idx"] for r in flagged}
        present = {r[0] for r in fixture.rows(
            "SELECT cal_idx FROM decisions WHERE symbol = 'GAP' AND universe = 'main'")}
        self.assertFalse(excluded & present)
        self.assertEqual(fixture.gates["excluded_has_gap"], 60)
        self.assertIn(GAP_AT + 61, present)

    def test_s4_needs_its_own_longer_contiguous_window(self):
        fixture = self.build(gap_rows())
        rows = fixture.dicts(
            "SELECT cal_idx, s4_has_gap, s4_insufficient_history, has_gap_s4, s4 FROM decisions"
            " WHERE symbol = 'GAP' AND universe = 'main' ORDER BY cal_idx")
        by_idx = {r["cal_idx"]: r for r in rows}
        # A decision 61 bars after the hole is eligible but its 130-bar S4 window still spans it.
        self.assertTrue(by_idx[GAP_AT + 61]["s4_has_gap"])
        self.assertTrue(by_idx[GAP_AT + 61]["has_gap_s4"])
        self.assertFalse(by_idx[GAP_AT + 61]["s4"])
        self.assertFalse(by_idx[GAP_AT + 61]["s4_insufficient_history"])
        # Before the hole the window is short, not broken.
        self.assertTrue(by_idx[100]["s4_insufficient_history"])
        self.assertFalse(by_idx[100]["s4_has_gap"])


# -------------------------------------------------------------- (6) raw / all quarantine


def quarantine_rows(count=200):
    rows = spy(count)
    for i in range(count):
        rows.append(bar("QRA", i, in_all=(i != 120)))   # raw only on 120
        rows.append(bar("QAL", i, in_raw=(i != 121)))   # adjusted only on 121
        rows.append(bar("KEP", i))
    return rows


class Quarantine(EvaluatorCase):
    def test_rows_present_in_only_one_series_are_counted_and_never_used(self):
        fixture = self.build(quarantine_rows())
        self.assertEqual(fixture.dataset["quarantined_raw_only"], 1)
        self.assertEqual(fixture.dataset["quarantined_all_only"], 1)
        self.assertEqual(fixture.one(
            "SELECT count(*) FROM bars WHERE symbol IN ('QRA', 'QAL') AND cal_idx IN (120, 121)")[0], 2)
        self.assertEqual(fixture.one(
            "SELECT count(*) FROM bars WHERE symbol = 'QRA' AND cal_idx = 120")[0], 0)
        self.assertEqual(fixture.one(
            "SELECT count(*) FROM bars WHERE symbol = 'QAL' AND cal_idx = 121")[0], 0)
        # The quarantined session becomes a hole, so the contiguity rule takes over.
        self.assertTrue(fixture.one(
            "SELECT has_gap FROM candidates WHERE symbol = 'QRA' AND cal_idx = 121")[0])
        self.assertFalse(fixture.one(
            "SELECT has_gap FROM candidates WHERE symbol = 'KEP' AND cal_idx = 121")[0])


# --------------------------------------------------------------------- (7) split session

T_SPLIT = 150


def split_rows(count=200):
    """A 2:1 split between t and t+1: raw prices halve, the adjusted series is continuous."""
    rows = spy(count)
    for i in range(count):
        if i <= T_SPLIT:
            rows.append(bar("SPL", i, c=100.0, v=1_000_000.0, ac=50.0, ao=50.0, ah=50.0, al=50.0))
        else:
            rows.append(bar("SPL", i, c=50.0, v=2_000_000.0, ac=50.0, ao=50.0, ah=50.0, al=50.0))
    return rows


class SplitSession(EvaluatorCase):
    def test_a_two_for_one_split_creates_no_false_mover(self):
        fixture = self.build(split_rows())
        decision = fixture.dicts(
            "SELECT raw_c, all_c, s1, s2, s3, s4, s5, lab_up_mover_1d, lab_down_mover_1d,"
            " lab_extreme_up_1d FROM labelled"
            " WHERE symbol = 'SPL' AND universe = 'main' AND session_date = ?", CAL[T_SPLIT])[0]
        # Eligibility reads the raw series (as traded), returns read the adjusted series.
        self.assertAlmostEqual(decision["raw_c"], 100.0)
        self.assertAlmostEqual(decision["all_c"], 50.0)
        self.assertEqual([decision[f"s{i}"] for i in range(1, 6)], [False] * 5)
        self.assertFalse(decision["lab_down_mover_1d"])
        self.assertFalse(decision["lab_up_mover_1d"])
        self.assertFalse(decision["lab_extreme_up_1d"])
        event = fixture.dicts(
            "SELECT entry_px, exit_px, net, cost_bps FROM ev WHERE symbol = 'SPL'"
            " AND universe = 'main' AND horizon = 'H1' AND session_date = ?", CAL[T_SPLIT])[0]
        self.assertAlmostEqual(event["entry_px"], 50.0)
        self.assertAlmostEqual(event["exit_px"], 50.0)
        c = event["cost_bps"] / 10000.0
        self.assertAlmostEqual(event["net"], (1 - c) / (1 + c) - 1)
        self.assertGreater(event["net"], -0.01)  # a raw-series return would be about -50%
        # The next session's own r1 is also clean on the adjusted series.
        self.assertAlmostEqual(fixture.one(
            "SELECT r1 FROM feat2 WHERE symbol = 'SPL' AND cal_idx = ?", T_SPLIT + 1)[0], 0.0)


# ----------------------------------------------------------------- (8) C1 hash determinism


class HashControl(EvaluatorCase):
    def test_c1_matches_the_protocol_hash_rule_for_every_decision(self):
        fixture = self.build(exit_rows())
        rows = fixture.rows(
            "SELECT symbol, session_date, c1 FROM decisions WHERE universe = 'main'")
        self.assertGreater(len(rows), 100)
        hits = 0
        for symbol, session_date, flag in rows:
            key = f"{symbol}|{session_date.isoformat()}".encode()
            expected = int(hashlib.sha256(key).hexdigest()[:8], 16) % 20 == 0
            self.assertEqual(flag, expected, f"{symbol} {session_date}")
            hits += bool(flag)
        self.assertGreater(hits, 0)


# ------------------------------------------------------- (9) top_20 ranking and tie-break

T_TOP = 150
TOP_SYMBOLS = [f"S{k:02d}" for k in range(22)]
TOP_RATIO = {s: float(22 - k) for k, s in enumerate(TOP_SYMBOLS)}
TOP_RATIO["S20"] = TOP_RATIO["S19"]  # deliberate tie at the 20th place boundary


def top_rows(count=200):
    rows = spy(count)
    for symbol in TOP_SYMBOLS:
        for i in range(count):
            volume = TOP_RATIO[symbol] * 1_000_000.0 if i == T_TOP else 1_000_000.0
            rows.append(bar(symbol, i, c=100.0, v=volume))
    return rows


class TopSelection(EvaluatorCase):
    def test_top_20_ranks_by_dv_over_med20_then_symbol_ascending(self):
        fixture = self.build(top_rows(), stats=True)
        order = [r[0] for r in fixture.rows(
            "SELECT symbol FROM top_20 WHERE lane = ? AND selector = 'C0_all_eligible'"
            " AND cal_idx = ? ORDER BY rank_in_date", m.LANE_SECONDARY, T_TOP)]
        self.assertEqual(len(order), 20)               # 22 names competed, 20 were kept
        self.assertEqual(order[:19], TOP_SYMBOLS[:19])
        self.assertEqual(order[19], "S19")             # tie with S20, broken by symbol ascending
        self.assertNotIn("S20", order)
        self.assertNotIn("S21", order)
        selected_here = fixture.one(
            "SELECT count(*) FROM ev_sel WHERE lane = ? AND selector = 'C0_all_eligible'"
            " AND horizon = 'H1' AND entry_date = ? AND rank_in_date IS NOT NULL",
            m.LANE_SECONDARY, CAL[T_TOP + 1])[0]
        self.assertEqual(selected_here, 20)
        selected = fixture.one(
            "SELECT count(*) FROM group_stats WHERE lane = ? AND selection = 'top_20'"
            " AND selector = 'C0_all_eligible' AND horizon = 'H1'", m.LANE_SECONDARY)[0]
        self.assertGreater(selected, 0)
        events = fixture.one(
            "SELECT sum(events) FROM group_stats WHERE lane = ? AND selection = 'top_20'"
            " AND selector = 'C0_all_eligible' AND horizon = 'H1'", m.LANE_SECONDARY)[0]
        dates = fixture.one(
            "SELECT count(DISTINCT entry_cal) FROM ev_sel WHERE lane = ?"
            " AND selector = 'C0_all_eligible' AND horizon = 'H1'", m.LANE_SECONDARY)[0]
        self.assertEqual(events, 20 * dates)  # at most 20 per entry date, and 22 are available


# ------------------------------------------------- (10) segment assignment, warmup excluded


def segment_rows():
    count = len(SEG_CAL)
    rows = spy(count, cal=SEG_CAL)
    rows += [bar("SEG", i, cal=SEG_CAL) for i in range(count)]
    return rows


class Segments(EvaluatorCase):
    def test_segments_follow_the_decision_session_and_warmup_is_never_scored(self):
        fixture = self.build(segment_rows(), stats=True)
        got = dict(fixture.rows(
            "SELECT cal_idx, segment FROM decisions WHERE symbol = 'SEG' AND universe = 'main'"
            " AND cal_idx IN (" + ", ".join(str(k) for k in SEG_EXPECTED) + ")"))
        self.assertEqual(got, SEG_EXPECTED)
        self.assertGreater(fixture.one(
            "SELECT count(*) FROM decisions WHERE symbol = 'SEG' AND segment = 'warmup'")[0], 0)
        self.assertEqual(fixture.one(
            "SELECT count(*) FROM ev_sel WHERE segment NOT IN ('development','validation','reserved')")[0], 0)
        self.assertEqual(sorted({r[0] for r in fixture.rows(
            "SELECT DISTINCT segment FROM group_stats")}),
            ["development", "reserved", "validation"])


# --------------------------------- (11) label unknowns and precision / recall / base rate

T_LAB = 150


def label_rows(count=200):
    rows = spy(count)
    plan = {"LUP": 120.0, "LDN": 85.0, "LFL": 100.0}
    for symbol, nxt in plan.items():
        for i in range(count):
            fires = symbol in ("LUP", "LFL") and i == T_LAB
            close = 106.0 if i == T_LAB else 100.0
            rows.append(bar(symbol, i, c=close if fires else 100.0,
                            v=3_000_000.0 if fires else 1_000_000.0,
                            ac=nxt if i == T_LAB + 1 else (106.0 if fires else 100.0)))
    for i in range(count):
        if i != T_LAB + 1 and i != T_LAB + 5:  # both label sessions are missing
            rows.append(bar("LNA", i))
    return rows


class LabelArithmetic(EvaluatorCase):
    def setUp(self):
        self.fixture = self.build(label_rows(), stats=True)

    def test_labels_are_unknown_when_the_needed_bar_is_missing(self):
        rows = {r["symbol"]: r for r in self.fixture.dicts(
            "SELECT symbol, lab_up_mover_1d, lab_extreme_up_1d, lab_down_mover_1d, lab_up_mover_5d"
            " FROM labelled WHERE universe = 'main' AND session_date = ?", CAL[T_LAB])}
        self.assertTrue(rows["LUP"]["lab_up_mover_1d"])        # 120 / 106 - 1 = +13.2%
        self.assertFalse(rows["LUP"]["lab_extreme_up_1d"])     # below the +20% threshold
        self.assertIsNone(rows["LNA"]["lab_up_mover_1d"])      # no t+1 bar: unknown, never False
        self.assertIsNone(rows["LNA"]["lab_up_mover_5d"])
        self.assertTrue(rows["LDN"]["lab_down_mover_1d"])      # 85 / 100 - 1 = -15%
        self.assertFalse(rows["LFL"]["lab_up_mover_1d"])

    def test_labelled_and_hit_counts_on_one_entry_date_are_exact(self):
        counts = {r["selector"]: r for r in self.fixture.dicts(
            "SELECT selector, count(*) AS events,"
            " count(*) FILTER (WHERE lab_up_mover_1d IS NOT NULL) AS labelled,"
            " count(*) FILTER (WHERE lab_up_mover_1d) AS hits"
            " FROM ev_sel WHERE lane = ? AND horizon = 'H1' AND entry_date = ?"
            " GROUP BY selector", m.LANE_SECONDARY, CAL[T_LAB + 1])}
        signal = counts["S2_volume_shock_continuation"]
        control = counts["C0_all_eligible"]
        self.assertEqual((signal["events"], signal["labelled"], signal["hits"]), (2, 2, 1))
        self.assertEqual((control["events"], control["labelled"], control["hits"]), (4, 3, 1))
        self.assertAlmostEqual(signal["hits"] / signal["labelled"], 0.5)              # precision
        self.assertAlmostEqual(control["hits"] / control["labelled"], 1 / 3)          # C0 base rate
        self.assertAlmostEqual(signal["hits"] / control["hits"], 1.0)                 # recall


class LabelFormulas(unittest.TestCase):
    """Precision, base rate, lift and recall arithmetic on hand-written counts."""

    def test_the_four_label_statistics_are_computed_as_declared(self):
        con = duckdb.connect()
        self.addCleanup(con.close)
        columns = ", ".join(f"labelled_{label} BIGINT, hits_{label} BIGINT" for label in m.LABELS)
        con.execute("CREATE TABLE label_stats (lane VARCHAR, selection VARCHAR, selector VARCHAR,"
                    f" segment VARCHAR, decisions BIGINT, {columns})")
        zeros = [0, 0] * (len(m.LABELS) - 1)
        con.execute("INSERT INTO label_stats VALUES (?, ?, ?, ?, ?" + ", ?" * (2 * len(m.LABELS)) + ")",
                    ["L", "all_events", "C0_all_eligible", "validation", 500, 300, 30] + zeros)
        con.execute("INSERT INTO label_stats VALUES (?, ?, ?, ?, ?" + ", ?" * (2 * len(m.LABELS)) + ")",
                    ["L", "all_events", "S1_momentum_breakout", "validation", 50, 40, 12] + zeros)
        got = {(r["selector"], r["label"]): r for r in m.label_metrics(con)}
        signal = got[("S1_momentum_breakout", "up_mover_1d")]
        self.assertEqual(signal["unknown_label"], 10)
        self.assertAlmostEqual(signal["precision"], 0.30)
        self.assertAlmostEqual(signal["base_rate_c0"], 0.10)
        self.assertAlmostEqual(signal["lift"], 3.0)
        self.assertAlmostEqual(signal["recall"], 0.40)
        control = got[("C0_all_eligible", "up_mover_1d")]
        self.assertAlmostEqual(control["precision"], control["base_rate_c0"])
        self.assertAlmostEqual(control["recall"], 1.0)
        # An entirely unlabelled outcome is reported as absent, never as zero.
        unlabelled = got[("S1_momentum_breakout", "up_mover_5d")]
        self.assertEqual(unlabelled["labelled"], 0)
        self.assertIsNone(unlabelled["precision"])
        self.assertIsNone(unlabelled["recall"])
        self.assertIsNone(unlabelled["lift"])


# ------------------------------------------------------------- (12) bootstrap determinism


class Bootstrap(unittest.TestCase):
    def test_same_seed_and_key_give_identical_bounds(self):
        values = np.linspace(-0.02, 0.03, 120)
        first = m.bootstrap_group(values, 5, SETTINGS, "lane|all_events|S1|H1|validation")
        again = m.bootstrap_group(values, 5, SETTINGS, "lane|all_events|S1|H1|validation")
        self.assertEqual(first, again)
        self.assertEqual(first["resamples"], 2000)
        self.assertEqual(first["seed"], 20260921)
        self.assertEqual(first["block_entry_dates"], 5)
        self.assertAlmostEqual(first["bonferroni_level"], 1 - 0.05 / 15)
        self.assertLessEqual(first["ci_bonf_lo"], first["ci95_lo"])
        self.assertGreaterEqual(first["ci_bonf_hi"], first["ci95_hi"])

    def test_a_different_group_key_draws_a_different_resample(self):
        values = np.linspace(-0.02, 0.03, 120)
        first = m.bootstrap_group(values, 5, SETTINGS, "lane|all_events|S1|H1|validation")
        other = m.bootstrap_group(values, 5, SETTINGS, "lane|all_events|S2|H1|validation")
        self.assertNotEqual(first["ci95_lo"], other["ci95_lo"])

    def test_blocks_are_circular_and_cover_the_whole_series(self):
        values = np.arange(10.0)
        rng = np.random.default_rng(7)
        means = m.block_bootstrap_means(values, 20, 50, rng)
        self.assertEqual(means.shape, (50,))
        # A block longer than the series wraps to exactly one full circular pass.
        self.assertTrue(np.allclose(means, values.mean()))
        self.assertIsNone(m.block_bootstrap_means(np.array([]), 5, 10, rng))


# --------------------------------------------------- (13) promotion can never be all-pass


def perfect_groups():
    groups = []
    for lane in (m.LANE_PRIMARY, m.LANE_SECONDARY):
        for signal in m.SIGNALS:
            for horizon, _step in m.HORIZONS:
                for segment in m.SCORED_SEGMENTS:
                    groups.append({
                        "lane": lane, "selection": "all_events", "selector": signal,
                        "horizon": horizon, "segment": segment,
                        "events": 5000, "scored_entry_dates": 400,
                        "date_clustered_mean_excess": 0.02, "stress_mean_net": 0.01,
                        "bootstrap_excess": {"ci_bonf_lo": 0.005, "ci_bonf_hi": 0.03},
                    })
    return groups


class Promotion(unittest.TestCase):
    def test_the_identity_gate_stays_open_so_nothing_auto_promotes(self):
        report = m.evaluate_promotion(perfect_groups(), PROTOCOL)
        self.assertEqual(len(report), len(m.SIGNALS) * len(m.HORIZONS))
        for entry in report:
            statuses = [check["status"] for check in entry["checks"]]
            self.assertEqual(statuses[:4], ["pass"] * 4)
            self.assertEqual(statuses[4], "open")
            self.assertEqual(entry["open_requirements"], 1)
            self.assertEqual(entry["status"], "not_established")
            self.assertNotIn("fail", statuses)
            self.assertNotEqual(entry["mechanical_passes"], len(statuses))

    def test_missing_evidence_fails_rather_than_passing_silently(self):
        report = m.evaluate_promotion([], PROTOCOL)
        for entry in report:
            self.assertEqual([c["status"] for c in entry["checks"]],
                             ["fail", "fail", "fail", "fail", "open"])
            self.assertEqual(entry["status"], "not_established")


# --------------------------------------------------------- end-to-end CLI and artifacts


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="bue-e2e-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.daily = os.path.join(self.dir, "daily.parquet")
        write_daily(self.daily, label_rows() + top_rows()[200:])
        self.assets = os.path.join(self.dir, "active.json")
        self.inactive = os.path.join(self.dir, "inactive.json")
        with open(self.assets, "w", encoding="utf-8") as handle:
            json.dump([{"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust"},
                       {"symbol": "LUP", "name": "Lup Industries Inc"},
                       {"symbol": "S00", "name": "iShares Example Index Fund"}], handle)
        with open(self.inactive, "w", encoding="utf-8") as handle:
            json.dump([], handle)
        self.results = os.path.join(self.dir, "results.json")
        self.events = os.path.join(self.dir, "events.parquet")

    def run_cli(self, **extra):
        argv = ["run", "--daily", self.daily, "--assets", self.assets, self.inactive,
                "--protocol", PROTOCOL_PATH, "--out", self.results, "--events-out", self.events,
                "--commit", "0" * 40, "--ledger-sha256", "a" * 64,
                "--run-at", "2026-09-21T18:00:00Z", "--memory-limit", "2GB"]
        for key, value in extra.items():
            argv += [f"--{key.replace('_', '-')}", value]
        self.assertEqual(m.main(argv), 0)
        with open(self.results, encoding="utf-8") as handle:
            return json.load(handle)

    def test_results_carry_provenance_and_the_events_parquet_is_private(self):
        body = self.run_cli()
        self.assertEqual(body["protocol"]["id"], m.PROTOCOL_ID)
        self.assertEqual(body["protocol"]["sha256"], m.sha256_file(PROTOCOL_PATH))
        self.assertEqual(body["run"]["commit"], "0" * 40)
        self.assertEqual(body["run"]["ledger_sha256"], "a" * 64)
        self.assertEqual(body["run"]["evaluate_sha256"], m.sha256_file(str(BLUEPRINT / "evaluate.py")))
        self.assertEqual(body["dataset"]["first_session"], CAL[0].isoformat())
        self.assertIn("quarantined_raw_only", body["dataset"])
        self.assertEqual(len(body["inspection_log"]), 1)
        self.assertEqual(body["conventions"]["net_return_formula"], m.NET_RETURN_FORMULA)
        self.assertEqual(oct(os.stat(self.events).st_mode & 0o777), "0o600")
        # Fund-named symbols leave the primary lane but stay in the unrestricted one.
        lanes = {row["lane"] for row in body["metrics"]}
        self.assertEqual(lanes, set(m.LANES))
        con = duckdb.connect()
        primary = con.execute(
            f"SELECT count(*) FROM read_parquet({m.sql_literal(self.events)})"
            " WHERE symbol = 'S00' AND in_primary").fetchone()[0]
        self.assertEqual(primary, 0)
        unknown = con.execute(
            f"SELECT count(*) FROM read_parquet({m.sql_literal(self.events)})"
            " WHERE symbol = 'S01' AND universe = 'main' AND NOT in_primary").fetchone()[0]
        con.close()
        self.assertEqual(unknown, 0)  # no asset-master name: stays in both lanes

    def test_a_second_run_appends_to_the_inspection_log_and_refuses_to_clobber_events(self):
        self.run_cli()
        with self.assertRaises(SystemExit):
            self.run_cli()
        os.remove(self.events)
        body = self.run_cli()
        self.assertEqual(len(body["inspection_log"]), 2)
        self.assertNotEqual(body["inspection_log"][0]["results_sha256"], "")

    def test_selected_scope_writes_only_control_and_signal_events(self):
        body = self.run_cli(events_scope="selected")
        con = duckdb.connect()
        stray = con.execute(
            f"SELECT count(*) FROM read_parquet({m.sql_literal(self.events)})"
            " WHERE NOT (c1 OR s1 OR s2 OR s3 OR s4 OR s5)").fetchone()[0]
        con.close()
        self.assertEqual(stray, 0)
        self.assertEqual(body["run"]["events_scope"], "selected")
        self.assertLess(body["event_construction"]["events_written"],
                        body["event_construction"]["event_rows"])


if __name__ == "__main__":
    unittest.main()
