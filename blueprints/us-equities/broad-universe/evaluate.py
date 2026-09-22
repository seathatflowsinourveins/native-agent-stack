#!/usr/bin/env python3
"""Chronological evaluator for the frozen protocol broad-universe-mover-v1-20260921.

Reads the materialized daily contract (one row per symbol and session, raw and
adjusted series side by side), rebuilds the predeclared features with DuckDB window
functions over each symbol's *own consecutive bars*, applies the five predeclared
signals and the two controls, prices every event from the next calendar session's
adjusted open, and reports every failed signal beside every success.

Leakage discipline: every feature window is a PRECEDING (or PRECEDING..CURRENT ROW)
frame, so no value at a session later than the decision session t can reach a feature
at t. Realized outcomes are never used to select candidates.

No network, no credentials, no orders. This module reads one parquet file and two
asset-master JSON files and writes one public results JSON plus one private events
parquet.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

import duckdb
import numpy as np

HERE = Path(__file__).resolve().parent
_COLLECT = importlib.util.spec_from_file_location("collect_daily", HERE / "collect_daily.py")
collect_daily = importlib.util.module_from_spec(_COLLECT)
_COLLECT.loader.exec_module(collect_daily)

PROTOCOL_ID = "broad-universe-mover-v1-20260921"
SCHEMA = "broad-universe-evaluation/1"

HORIZONS = (("H1", 1), ("H5", 5), ("H20", 20))
SIGNALS = ("S1_momentum_breakout", "S2_volume_shock_continuation", "S3_oversold_reversal",
           "S4_contraction_breakout", "S5_gap_and_hold")
CONTROLS = ("C0_all_eligible", "C1_hash_sample")
SELECTORS = CONTROLS + SIGNALS
SELECTIONS = ("all_events", "top_20")
LANE_PRIMARY = "primary_operating_company"
LANE_SECONDARY = "secondary_all_instruments"
LANE_MICRO = "descriptive_microcap"
LANES = (LANE_PRIMARY, LANE_SECONDARY, LANE_MICRO)
SCORED_SEGMENTS = ("development", "validation", "reserved")
LABELS = ("up_mover_1d", "extreme_up_1d", "up_mover_5d", "extreme_up_5d", "down_mover_1d")

# protocol eligibility.symbol_exclusion_pattern
EXCLUDED_DOT_SUFFIXES = ("WS", "W", "U", "R", "RT")
AMBIGUOUS_TAIL = ("W", "R", "U")
# protocol eligibility.instrument_lanes.primary_operating_company_heuristic
FUND_NAME = re.compile(r"ETF|ETN|Fund|Trust|Shares|ProShares|Direxion|iShares|SPDR|Index|Portfolio",
                       re.IGNORECASE)
# protocol execution_assumptions.per_side_cost_bps keys name these two thresholds
TIER_HIGH_USD = 100_000_000.0
TIER_MID_USD = 50_000_000.0

# Longest feature window, counted in the symbol's own consecutive bars.
#   eligibility: high60 = max(all_high[t-60..t-1]) and min_prior_sessions_with_bars = 60
ELIGIBILITY_LOOKBACK_BARS = 60
#   S4: range10_p20 is the 20th percentile of range10 over u in [t-121, t-2]; range10 at u
#   reads all_high/all_low[u-9..u], so the deepest bar S4 touches is u=t-121 -> t-130.
S4_LOOKBACK_BARS = 130
RANGE10_BARS = 10
RANGE10_P20_OBS = 120
NET_RETURN_FORMULA = "net = exit_price / entry_price * (1 - c) / (1 + c) - 1, c = per-side cost in decimal"
STRESS_RETURN_FORMULA = ("stress_net = (exit_price * (0.5 if terminated_early else 1)) / entry_price"
                         " * (1 - 3c) / (1 + 3c) - 1")
TRIALS = 15  # 5 signals x 3 horizons; Bonferroni family size for the adjusted bootstrap bound


# ----------------------------------------------------------------------------- helpers


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def write_private(path, payload):
    """Exclusive-create a private 0600 JSON artifact; never silently overwrite evidence."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    handle = os.open(path, flags, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        json.dump(payload, out, indent=1, sort_keys=True)


def number(value):
    """JSON-safe float: NaN and infinity are absences, not values."""
    if value is None:
        return None
    value = float(value)
    return value if np.isfinite(value) else None


def load_protocol(path):
    with open(path, encoding="utf-8") as handle:
        protocol = json.load(handle)
    if protocol.get("id") != PROTOCOL_ID:
        raise SystemExit(f"protocol id is {protocol.get('id')!r}, expected {PROTOCOL_ID!r}")
    eligibility = protocol["eligibility"]
    micro = eligibility["descriptive_microcap_lane"]
    costs = protocol["execution_assumptions"]["per_side_cost_bps"]
    bootstrap = protocol["metrics"]["bootstrap"]
    chronology = protocol["chronology"]
    settings = {
        "min_raw_close_usd": float(eligibility["min_raw_close_usd"]),
        "max_raw_close_usd": eligibility["max_raw_close_usd"],
        "med20_lookback": int(eligibility["median_dollar_volume_lookback_sessions"]),
        "med20_min_usd": float(eligibility["median_dollar_volume_min_usd"]),
        "min_prior_sessions_with_bars": int(eligibility["min_prior_sessions_with_bars"]),
        "micro_min_raw_close_usd": float(micro["min_raw_close_usd"]),
        "micro_med20_min_usd": float(micro["median_dollar_volume_min_usd"]),
        "micro_cost_bps": float(micro["per_side_cost_bps"]),
        "cost_bps_high": float(costs["med20_ge_100m"]),
        "cost_bps_mid": float(costs["med20_ge_50m"]),
        "cost_bps_low": float(costs["otherwise"]),
        "stress_multiplier": float(protocol["execution_assumptions"]["stress_cost_multiplier"]),
        "resamples": int(bootstrap["resamples"]),
        "seed": int(bootstrap["seed"]),
        "block_sessions": {k: int(v) for k, v in bootstrap["block_sessions"].items()},
        "segments": [(name, chronology[name][0], chronology[name][1])
                     for name in ("warmup", "development", "validation", "reserved")],
    }
    if settings["max_raw_close_usd"] is not None:
        raise SystemExit("protocol declares a price cap; this evaluator implements the no-cap protocol")
    if settings["med20_lookback"] != 20 or settings["min_prior_sessions_with_bars"] != ELIGIBILITY_LOOKBACK_BARS:
        raise SystemExit("protocol window constants do not match this evaluator's frozen SQL")
    return protocol, settings


def load_asset_names(paths):
    """Current asset-master names only. Disagreeing duplicates degrade to 'unknown', never merge."""
    by_symbol = {}
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            for asset in json.load(handle):
                symbol = asset.get("symbol")
                if not symbol:
                    continue
                name = asset.get("name")
                if not name:
                    continue
                by_symbol.setdefault(symbol, set()).add(bool(FUND_NAME.search(name)))
    rows = []
    stats = {"symbols_with_name": 0, "fund_named": 0, "operating_named": 0, "name_conflict": 0}
    for symbol, flags in by_symbol.items():
        stats["symbols_with_name"] += 1
        if len(flags) > 1:
            stats["name_conflict"] += 1
            rows.append((symbol, None))
            continue
        is_fund = next(iter(flags))
        stats["fund_named" if is_fund else "operating_named"] += 1
        rows.append((symbol, is_fund))
    return rows, stats


def sql_literal(value):
    """Single-quoted SQL literal; DuckDB DDL cannot take prepared parameters."""
    return "'" + str(value).replace("'", "''") + "'"


def segment_case(segments, column):
    branches = " ".join(
        f"WHEN {column} BETWEEN DATE '{lo}' AND DATE '{hi}' THEN '{name}'" for name, lo, hi in segments)
    return f"CASE {branches} ELSE 'out_of_scope' END"


# ------------------------------------------------------------------------- duckdb build


def connect(temp_dir, memory_limit, threads):
    os.makedirs(temp_dir, mode=0o700, exist_ok=True)
    config = {"temp_directory": temp_dir, "memory_limit": memory_limit,
              "preserve_insertion_order": False}
    if threads:
        config["threads"] = threads
    return duckdb.connect(database=":memory:", config=config)


def build_calendar(con, daily_path):
    con.execute(f"CREATE OR REPLACE VIEW src AS SELECT * FROM read_parquet({sql_literal(daily_path)})")
    quarantine = con.execute("""
        SELECT count(*) FILTER (WHERE in_raw AND NOT in_all) AS raw_only,
               count(*) FILTER (WHERE in_all AND NOT in_raw) AS all_only,
               count(*) AS rows_total
        FROM src""").fetchone()
    con.execute("""
        CREATE OR REPLACE TABLE calendar AS
        SELECT session_date, (row_number() OVER (ORDER BY session_date) - 1)::BIGINT AS cal_idx
        FROM (SELECT DISTINCT session_date FROM src WHERE symbol = 'SPY' AND in_raw)""")
    sessions = con.execute("SELECT count(*) FROM calendar").fetchone()[0]
    if sessions == 0:
        raise SystemExit("calendar is empty: no SPY raw sessions in the daily contract")
    con.execute("""
        CREATE OR REPLACE TABLE bars AS
        SELECT s.symbol, s.session_date, c.cal_idx,
               s.raw_o::DOUBLE AS raw_o, s.raw_h::DOUBLE AS raw_h, s.raw_l::DOUBLE AS raw_l,
               s.raw_c::DOUBLE AS raw_c, s.raw_v::DOUBLE AS raw_v,
               s.all_o::DOUBLE AS all_o, s.all_h::DOUBLE AS all_h, s.all_l::DOUBLE AS all_l,
               s.all_c::DOUBLE AS all_c
        FROM src s JOIN calendar c USING (session_date)
        WHERE s.in_raw AND s.in_all
          AND s.raw_c IS NOT NULL AND s.raw_v IS NOT NULL AND s.raw_o IS NOT NULL
          AND s.raw_h IS NOT NULL AND s.raw_l IS NOT NULL
          AND s.all_c IS NOT NULL AND s.all_o IS NOT NULL
          AND s.all_h IS NOT NULL AND s.all_l IS NOT NULL
          -- Every one of these feeds a division: all_o is the entry price, all_c the exit and
          -- the return denominators, raw_c the dollar-volume and the price floor, all_h/all_l
          -- the range10 numerator. A zero here yields inf (DuckDB does not null x/0.0 here),
          -- and one inf poisons avg() for every group containing the row, so such a row is
          -- quarantined into unusable_field_rows instead.
          AND s.raw_c > 0 AND s.all_c > 0 AND s.raw_o > 0 AND s.all_o > 0
          AND s.all_h > 0 AND s.all_l > 0""")
    paired = con.execute("SELECT count(*) FROM src WHERE in_raw AND in_all").fetchone()[0]
    kept = con.execute("SELECT count(*) FROM bars").fetchone()[0]
    off_calendar = con.execute("""
        SELECT count(*) FROM src s
        WHERE s.in_raw AND s.in_all
          AND NOT EXISTS (SELECT 1 FROM calendar c WHERE c.session_date = s.session_date)""").fetchone()[0]
    con.execute("""
        CREATE OR REPLACE TABLE sym_last AS
        SELECT symbol, max(cal_idx) AS last_cal_idx FROM bars GROUP BY symbol""")
    first_session, last_session = con.execute(
        "SELECT min(session_date), max(session_date) FROM calendar").fetchone()
    return {
        "rows_in_contract": int(quarantine[2]),
        "quarantined_raw_only": int(quarantine[0]),
        "quarantined_all_only": int(quarantine[1]),
        "paired_rows": int(paired),
        "off_calendar_rows": int(off_calendar),
        "unusable_field_rows": int(paired - off_calendar - kept),
        "bars_used": int(kept),
        "calendar_sessions": int(sessions),
        "first_session": first_session.isoformat(),
        "last_session": last_session.isoformat(),
    }


FEATURES_SQL = f"""
CREATE OR REPLACE VIEW feat AS
SELECT symbol, session_date, cal_idx, raw_o, raw_h, raw_l, raw_c, raw_v, all_o, all_h, all_l, all_c,
       raw_c * raw_v AS dv,
       median(raw_c * raw_v) OVER w20 AS med20,
       count(*) OVER w20 AS n20,
       all_c / lag(all_c, 1) OVER w - 1 AS r1,
       all_c / lag(all_c, 5) OVER w - 1 AS r5,
       max(all_h) OVER w60 AS high60,
       max(all_h) OVER w20 AS high20,
       CASE WHEN raw_h = raw_l THEN 0.5 ELSE (raw_c - raw_l) / (raw_h - raw_l) END AS clv,
       all_o / lag(all_c, 1) OVER w - 1 AS gap,
       CASE WHEN count(*) OVER w10 = {RANGE10_BARS}
            THEN (max(all_h) OVER w10 - min(all_l) OVER w10) / all_c END AS range10_u,
       cal_idx - lag(cal_idx, {ELIGIBILITY_LOOKBACK_BARS}) OVER w AS span60,
       cal_idx - lag(cal_idx, {S4_LOOKBACK_BARS}) OVER w AS span130
FROM bars
WINDOW w   AS (PARTITION BY symbol ORDER BY session_date),
       w20 AS (PARTITION BY symbol ORDER BY session_date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING),
       w60 AS (PARTITION BY symbol ORDER BY session_date
               ROWS BETWEEN {ELIGIBILITY_LOOKBACK_BARS} PRECEDING AND 1 PRECEDING),
       w10 AS (PARTITION BY symbol ORDER BY session_date
               ROWS BETWEEN {RANGE10_BARS - 1} PRECEDING AND CURRENT ROW)
"""

FEATURES2_SQL = f"""
CREATE OR REPLACE VIEW feat2 AS
SELECT *,
       lag(range10_u, 1) OVER w AS range10,
       CASE WHEN count(range10_u) OVER wp = {RANGE10_P20_OBS}
            THEN quantile_cont(range10_u, 0.2) OVER wp END AS range10_p20
FROM feat
WINDOW w  AS (PARTITION BY symbol ORDER BY session_date),
       wp AS (PARTITION BY symbol ORDER BY session_date
              ROWS BETWEEN {RANGE10_P20_OBS + 1} PRECEDING AND 2 PRECEDING)
"""


def build_features(con):
    con.execute(FEATURES_SQL)
    con.execute(FEATURES2_SQL)


def build_decisions(con, settings, asset_rows):
    con.execute("CREATE OR REPLACE TABLE asset_names (symbol VARCHAR, is_fund BOOLEAN)")
    if asset_rows:
        con.executemany("INSERT INTO asset_names VALUES (?, ?)", asset_rows)

    excluded = ", ".join(f"'{s}'" for s in EXCLUDED_DOT_SUFFIXES)
    ambiguous = ", ".join(f"'{s}'" for s in AMBIGUOUS_TAIL)
    segment = segment_case(settings["segments"], "f.session_date")
    # feat/feat2 stay views and only `candidates` is materialised: the bar table is scanned
    # once for the window pass instead of being copied at every stage.
    con.execute(f"""
        CREATE OR REPLACE TABLE candidates AS
        SELECT f.*,
               (contains(f.symbol, '.') AND split_part(f.symbol, '.', 2) IN ({excluded})) AS excluded_suffix,
               (length(f.symbol) = 5 AND NOT contains(f.symbol, '.')
                AND right(f.symbol, 1) IN ({ambiguous})) AS ambiguous_suffix_flag,
               a.is_fund AS is_fund,
               (a.symbol IS NULL OR a.is_fund IS NULL) AS name_unknown,
               {segment} AS segment,
               (f.span60 IS NOT NULL AND f.span60 <> {ELIGIBILITY_LOOKBACK_BARS}) AS has_gap,
               (f.span60 IS NULL) AS insufficient_history,
               (f.span130 IS NULL) AS s4_insufficient_history,
               (f.span130 IS NOT NULL AND f.span130 <> {S4_LOOKBACK_BARS}) AS s4_has_gap,
               (f.span130 IS NULL OR f.span130 <> {S4_LOOKBACK_BARS}) AS has_gap_s4
        FROM feat2 f LEFT JOIN asset_names a ON a.symbol = f.symbol""")

    gates = con.execute("""
        SELECT count(*) AS candidate_rows,
               count(*) FILTER (WHERE insufficient_history) AS insufficient_history,
               count(*) FILTER (WHERE has_gap) AS has_gap,
               count(*) FILTER (WHERE excluded_suffix) AS excluded_suffix,
               count(*) FILTER (WHERE ambiguous_suffix_flag) AS ambiguous_suffix_flagged,
               count(*) FILTER (WHERE name_unknown) AS name_unknown_rows
        FROM candidates""").fetchall()[0]

    # The counters above are independent filters over the same rows and therefore overlap, so
    # they cannot be subtracted from candidate_rows. This second pass applies the same gates in
    # a fixed precedence and counts each row exactly once, so that
    #   candidate_rows - sum(excluded_stepwise) = eligible_base_rows
    # reconciles exactly.
    valid_med20 = "n20 = 20 AND med20 IS NOT NULL AND med20 > 0"
    stepwise = con.execute(f"""
        SELECT count(*) FILTER (WHERE excluded_suffix) AS g1,
               count(*) FILTER (WHERE NOT excluded_suffix AND insufficient_history) AS g2,
               count(*) FILTER (WHERE NOT excluded_suffix AND NOT insufficient_history
                                AND has_gap) AS g3,
               count(*) FILTER (WHERE NOT excluded_suffix AND NOT insufficient_history
                                AND NOT has_gap AND NOT ({valid_med20})) AS g4
        FROM candidates""").fetchall()[0]

    con.execute(f"""
        CREATE OR REPLACE VIEW eligible_base AS
        SELECT * FROM candidates
        WHERE NOT excluded_suffix AND NOT insufficient_history AND NOT has_gap
          AND {valid_med20}""")
    eligible_base_rows = int(con.execute("SELECT count(*) FROM eligible_base").fetchone()[0])

    signals = f"""
        (all_c > high60 AND dv >= 2 * med20 AND clv >= 0.75) AS s1,
        (r1 >= 0.05 AND dv >= 3 * med20 AND clv >= 0.5) AS s2,
        (r5 <= -0.15 AND raw_c > raw_o AND dv >= med20) AS s3,
        (NOT has_gap_s4 AND range10 IS NOT NULL AND range10_p20 IS NOT NULL
         AND range10 <= range10_p20 AND all_c > high20) AS s4,
        (gap >= 0.04 AND all_c >= all_o AND dv >= 2 * med20) AS s5"""
    c1 = ("(('0x' || substr(sha256(symbol || '|' || strftime(session_date, '%Y-%m-%d')), 1, 8))::UBIGINT"
          " % 20 = 0) AS c1")
    tier = (f"(CASE WHEN med20 >= {TIER_HIGH_USD} THEN {settings['cost_bps_high']}"
            f" WHEN med20 >= {TIER_MID_USD} THEN {settings['cost_bps_mid']}"
            f" ELSE {settings['cost_bps_low']} END)::DOUBLE")
    common = f"""
        symbol, session_date, cal_idx, segment, dv, med20, dv / med20 AS dv_ratio,
        raw_c, all_c, is_fund, name_unknown, ambiguous_suffix_flag,
        has_gap_s4, s4_has_gap, s4_insufficient_history,
        {c1}, {signals}"""
    con.execute(f"""
        CREATE OR REPLACE TABLE decisions AS
        SELECT 'main' AS universe,
               (is_fund IS NULL OR NOT is_fund) AS in_primary,
               {tier} AS cost_bps, {common}
        FROM eligible_base
        WHERE raw_c >= {settings['min_raw_close_usd']} AND med20 >= {settings['med20_min_usd']}
        UNION ALL
        SELECT 'micro' AS universe, FALSE AS in_primary,
               {settings['micro_cost_bps']}::DOUBLE AS cost_bps, {common}
        FROM eligible_base
        WHERE raw_c >= {settings['micro_min_raw_close_usd']}
          AND med20 >= {settings['micro_med20_min_usd']}""")
    # The two liquidity/price floors are the largest drop in the run; counted per universe so
    # eligible_base_rows - below_price_floor - below_med20_floor = that universe's decisions.
    floors = []
    universes = (("main", settings["min_raw_close_usd"], settings["med20_min_usd"]),
                 ("micro", settings["micro_min_raw_close_usd"], settings["micro_med20_min_usd"]))
    for universe, price_floor, med_floor in universes:
        row = con.execute(f"""
            SELECT count(*) FILTER (WHERE raw_c < {price_floor}) AS below_price,
                   count(*) FILTER (WHERE raw_c >= {price_floor} AND med20 < {med_floor})
                       AS below_med20,
                   count(*) FILTER (WHERE raw_c >= {price_floor} AND med20 >= {med_floor})
                       AS kept
            FROM eligible_base""").fetchall()[0]
        floors.append({"universe": universe, "eligible_base_rows": eligible_base_rows,
                       "min_raw_close_usd": price_floor, "median_dollar_volume_min_usd": med_floor,
                       "excluded_below_price_floor": int(row[0]),
                       "excluded_below_med20_floor": int(row[1]),
                       "decisions": int(row[2])})

    # micro is a pure minimum-floor lane, so every main decision is also a micro decision. The
    # overlap is reported per segment so a reader can deflate the lane's descriptive figures.
    also_main = (f"(universe = 'micro' AND raw_c >= {settings['min_raw_close_usd']}"
                 f" AND med20 >= {settings['med20_min_usd']})")
    counts = con.execute(f"""
        SELECT universe, segment, count(*) AS decisions,
               count(*) FILTER (WHERE s4_has_gap) AS s4_non_contiguous,
               count(*) FILTER (WHERE s4_insufficient_history) AS s4_insufficient_history,
               count(*) FILTER (WHERE name_unknown) AS name_unknown,
               count(*) FILTER (WHERE ambiguous_suffix_flag) AS ambiguous_suffix_flagged,
               count(*) FILTER (WHERE {also_main}) AS micro_also_in_main
        FROM decisions GROUP BY ALL ORDER BY universe, segment""").fetchall()
    return {
        "candidate_rows": int(gates[0]),
        "excluded_insufficient_history": int(gates[1]),
        "excluded_has_gap": int(gates[2]),
        "excluded_symbol_suffix": int(gates[3]),
        "ambiguous_suffix_flagged_rows": int(gates[4]),
        "name_unknown_rows": int(gates[5]),
        "excluded_stepwise": [
            {"gate": "symbol_suffix", "rows": int(stepwise[0])},
            {"gate": "insufficient_history", "rows": int(stepwise[1])},
            {"gate": "non_contiguous_60_bar_window", "rows": int(stepwise[2])},
            {"gate": "med20_window_incomplete_or_zero", "rows": int(stepwise[3])},
        ],
        "eligible_base_rows": eligible_base_rows,
        "universe_floors": floors,
        "decisions_by_universe_segment": [
            {"universe": r[0], "segment": r[1], "decisions": int(r[2]),
             "s4_non_contiguous": int(r[3]), "s4_insufficient_history": int(r[4]),
             "name_unknown": int(r[5]), "ambiguous_suffix_flagged": int(r[6]),
             "micro_also_in_main": int(r[7])} for r in counts],
    }


LABEL_SQL = """
        CASE WHEN b1.all_c IS NULL THEN NULL ELSE (b1.all_c / d.all_c - 1) >= 0.10 END AS lab_up_mover_1d,
        CASE WHEN b1.all_c IS NULL THEN NULL ELSE (b1.all_c / d.all_c - 1) >= 0.20 END AS lab_extreme_up_1d,
        CASE WHEN b5.all_c IS NULL THEN NULL ELSE (b5.all_c / d.all_c - 1) >= 0.20 END AS lab_up_mover_5d,
        CASE WHEN b5.all_c IS NULL THEN NULL ELSE (b5.all_c / d.all_c - 1) >= 0.50 END AS lab_extreme_up_5d,
        CASE WHEN b1.all_c IS NULL THEN NULL ELSE (b1.all_c / d.all_c - 1) <= -0.10 END AS lab_down_mover_1d
"""


def build_events(con, settings):
    horizons = ", ".join(f"('{name}', {step})" for name, step in HORIZONS)
    con.execute(f"CREATE OR REPLACE TABLE horizons AS SELECT * FROM (VALUES {horizons}) t(horizon, hstep)")
    con.execute(f"""
        CREATE OR REPLACE VIEW labelled AS
        SELECT d.*, {LABEL_SQL}
        FROM decisions d
        LEFT JOIN bars b1 ON b1.symbol = d.symbol AND b1.cal_idx = d.cal_idx + 1
        LEFT JOIN bars b5 ON b5.symbol = d.symbol AND b5.cal_idx = d.cal_idx + 5""")
    con.execute("""
        CREATE OR REPLACE VIEW ev_base AS
        SELECT d.*, h.horizon, h.hstep,
               d.cal_idx + 1 AS entry_cal, d.cal_idx + h.hstep AS exit_cal,
               ce.session_date AS entry_date, cx.session_date AS exit_date,
               be.all_o AS entry_px
        FROM labelled d CROSS JOIN horizons h
        LEFT JOIN calendar ce ON ce.cal_idx = d.cal_idx + 1
        LEFT JOIN calendar cx ON cx.cal_idx = d.cal_idx + h.hstep
        LEFT JOIN bars be ON be.symbol = d.symbol AND be.cal_idx = d.cal_idx + 1""")
    stress = settings["stress_multiplier"]
    con.execute(f"""
        CREATE OR REPLACE TABLE ev AS
        WITH joined AS (
            SELECT e.*, sl.last_cal_idx, bx.session_date AS exit_bar_date,
                   bx.cal_idx AS exit_bar_cal, bx.all_c AS exit_px
            FROM ev_base e
            LEFT JOIN sym_last sl ON sl.symbol = e.symbol
            ASOF LEFT JOIN bars bx ON bx.symbol = e.symbol AND e.exit_date >= bx.session_date
        ), flagged AS (
            SELECT *,
                   -- Protocol outcome precedence: no_entry first. Whether the symbol had a bar
                   -- on session t+1 is a fact about t+1 alone, so the same decision must not be
                   -- labelled no_entry at H1 and horizon_incomplete at H5/H20.
                   -- A decision on the dataset's last session has no observed t+1 at all: that is
                   -- an incomplete horizon, not a symbol that failed to trade.
                   CASE WHEN entry_date IS NULL THEN 'horizon_incomplete'
                        WHEN entry_px IS NULL THEN 'no_entry'
                        WHEN exit_date IS NULL THEN 'horizon_incomplete'
                        WHEN exit_px IS NULL THEN 'no_exit_bar'
                        ELSE 'scored' END AS outcome,
                   cost_bps / 10000.0 AS c
            FROM joined
        )
        SELECT *,
               (outcome = 'scored' AND exit_bar_cal < exit_cal AND last_cal_idx >= exit_cal) AS exit_stale,
               (outcome = 'scored' AND exit_bar_cal < exit_cal AND last_cal_idx < exit_cal) AS terminated_early,
               CASE WHEN outcome = 'scored'
                    THEN exit_px / entry_px * (1 - c) / (1 + c) - 1 END AS net,
               CASE WHEN outcome = 'scored'
                    THEN (exit_px * CASE WHEN exit_bar_cal < exit_cal AND last_cal_idx < exit_cal
                                         THEN 0.5 ELSE 1.0 END) / entry_px
                         * (1 - {stress} * c) / (1 + {stress} * c) - 1 END AS stress_net
        FROM flagged""")
    con.execute("""
        CREATE OR REPLACE TABLE spy_ref AS
        SELECT h.horizon, ce.session_date AS entry_date, bx.all_c / be.all_o - 1 AS spy_ret
        FROM calendar ce CROSS JOIN horizons h
        JOIN bars be ON be.symbol = 'SPY' AND be.cal_idx = ce.cal_idx
        LEFT JOIN bars bx ON bx.symbol = 'SPY' AND bx.cal_idx = ce.cal_idx + h.hstep - 1""")
    outcomes = con.execute("""
        SELECT universe, horizon, outcome, count(*) FROM ev GROUP BY ALL ORDER BY 1, 2, 3""").fetchall()
    return {"event_rows": int(con.execute("SELECT count(*) FROM ev").fetchone()[0]),
            "outcomes": [{"universe": r[0], "horizon": r[1], "outcome": r[2], "events": int(r[3])}
                         for r in outcomes]}


def build_selections(con):
    """Lane and selector expansion, then the per-date top_20 rank. Warmup is never scored."""
    lane_list = (f"CASE WHEN universe = 'micro' THEN ['{LANE_MICRO}']"
                 f" WHEN in_primary THEN ['{LANE_SECONDARY}', '{LANE_PRIMARY}']"
                 f" ELSE ['{LANE_SECONDARY}'] END")
    sel_list = ", ".join(["'C0_all_eligible'",
                          "CASE WHEN c1 THEN 'C1_hash_sample' END"] +
                         [f"CASE WHEN s{i} THEN '{SIGNALS[i - 1]}' END" for i in range(1, 6)])
    scored = ", ".join(f"'{s}'" for s in SCORED_SEGMENTS)
    # The top_20 rank is a property of the decision, not of the horizon, so it is ranked once
    # over decisions and joined in. Ranking the horizon-expanded event table would sort three
    # times as many rows for the same answer.
    con.execute(f"""
        CREATE OR REPLACE VIEW dec_lane AS
        SELECT d.*, unnest({lane_list}) AS lane FROM decisions d WHERE d.segment IN ({scored})""")
    con.execute(f"""
        CREATE OR REPLACE VIEW dec_sel AS
        SELECT l.*, unnest(list_filter([{sel_list}], x -> x IS NOT NULL)) AS selector FROM dec_lane l""")
    con.execute("""
        CREATE OR REPLACE TABLE top_20 AS
        SELECT lane, selector, universe, symbol, cal_idx, rank_in_date FROM (
            SELECT lane, selector, universe, symbol, cal_idx,
                   row_number() OVER (PARTITION BY lane, selector, cal_idx
                                      ORDER BY dv_ratio DESC, symbol ASC) AS rank_in_date
            FROM dec_sel)
        WHERE rank_in_date <= 20""")
    con.execute(f"""
        CREATE OR REPLACE VIEW ev_lane AS
        SELECT e.*, unnest({lane_list}) AS lane FROM ev e WHERE e.segment IN ({scored})""")
    con.execute(f"""
        CREATE OR REPLACE VIEW ev_sel_raw AS
        SELECT l.*, unnest(list_filter([{sel_list}], x -> x IS NOT NULL)) AS selector FROM ev_lane l""")
    con.execute("""
        CREATE OR REPLACE TABLE ev_sel AS
        SELECT s.lane, s.selector, s.horizon, s.segment, s.symbol, s.entry_cal, s.entry_date,
               s.outcome, s.exit_stale, s.terminated_early, s.net, s.stress_net,
               s.lab_up_mover_1d, s.lab_extreme_up_1d, s.lab_up_mover_5d, s.lab_extreme_up_5d,
               s.lab_down_mover_1d, t.rank_in_date
        FROM ev_sel_raw s
        LEFT JOIN top_20 t ON t.lane = s.lane AND t.selector = s.selector
             AND t.universe = s.universe AND t.symbol = s.symbol AND t.cal_idx = s.cal_idx""")


SELECTION_EXPANSION = ("SELECT s.*, unnest(CASE WHEN rank_in_date IS NOT NULL"
                       " THEN ['all_events', 'top_20'] ELSE ['all_events'] END) AS selection"
                       " FROM ev_sel s")


def build_stats(con):
    con.execute(f"""
        CREATE OR REPLACE TABLE group_stats AS
        SELECT lane, selection, selector, horizon, segment,
               count(*) AS events,
               count(DISTINCT symbol) AS distinct_symbols,
               count(DISTINCT entry_date) AS distinct_entry_dates,
               count(*) FILTER (WHERE outcome = 'no_entry') AS no_entry,
               count(*) FILTER (WHERE outcome = 'horizon_incomplete') AS horizon_incomplete,
               count(*) FILTER (WHERE outcome = 'no_exit_bar') AS no_exit_bar,
               count(*) FILTER (WHERE terminated_early) AS terminated_early,
               count(*) FILTER (WHERE exit_stale) AS exit_stale,
               count(net) AS scored,
               avg(net) AS mean_net,
               -- one aggregate state for all three reported quantiles keeps the exact
               -- (non-spilling) quantile operator from holding three copies of net
               quantile_cont(net, [0.05, 0.5, 0.95]) AS net_quantiles,
               count(*) FILTER (WHERE net <= 0) AS failed_events,
               avg(net) FILTER (WHERE net <= 0) AS failed_mean_net,
               avg(stress_net) AS stress_mean_net
        FROM ({SELECTION_EXPANSION}) GROUP BY ALL""")
    con.execute(f"""
        CREATE OR REPLACE TABLE date_stats AS
        SELECT lane, selection, selector, horizon, segment, entry_date,
               count(net) AS n, avg(net) AS mean_net
        FROM ({SELECTION_EXPANSION}) WHERE net IS NOT NULL GROUP BY ALL""")
    con.execute(f"""
        CREATE OR REPLACE TABLE label_stats AS
        SELECT lane, selection, selector, segment, count(*) AS decisions,
               {", ".join(f"count(*) FILTER (WHERE lab_{lab} IS NOT NULL) AS labelled_{lab},"
                          f" count(*) FILTER (WHERE lab_{lab}) AS hits_{lab}" for lab in LABELS)}
        FROM ({SELECTION_EXPANSION}) WHERE horizon = 'H1' GROUP BY ALL""")
    con.execute("""
        CREATE OR REPLACE TABLE spy_group AS
        SELECT d.lane, d.selection, d.selector, d.horizon, d.segment, avg(s.spy_ret) AS spy_reference_mean
        FROM date_stats d LEFT JOIN spy_ref s ON s.horizon = d.horizon AND s.entry_date = d.entry_date
        GROUP BY ALL""")


# ------------------------------------------------------------------------ numpy metrics


def block_bootstrap_means(values, block, resamples, rng):
    """Circular moving-block bootstrap of the mean over the ordered entry-date series."""
    n = values.shape[0]
    if n == 0:
        return None
    block = int(min(block, n))
    blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n, size=(resamples, blocks))
    offsets = np.arange(block)
    index = (starts[:, :, None] + offsets[None, None, :]).reshape(resamples, blocks * block) % n
    return values[index[:, :n]].mean(axis=1)


def bootstrap_group(values, block, settings, key):
    seed = np.random.SeedSequence([settings["seed"], int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)])
    rng = np.random.default_rng(seed)
    means = block_bootstrap_means(values, block, settings["resamples"], rng)
    if means is None:
        return None
    alpha_b = 0.05 / TRIALS
    lo95, hi95 = np.quantile(means, [0.025, 0.975])
    lob, hib = np.quantile(means, [alpha_b / 2, 1 - alpha_b / 2])
    dates = int(values.shape[0])
    # With at most `block` entry dates every circular resample is one full pass over the series,
    # so all resampled means equal the sample mean and the interval collapses to a point. That
    # is an artefact of the block length, not a measured bound, so it is flagged and the bounds
    # are withheld rather than published as a zero-width confidence interval.
    degenerate = dates <= block
    interval = {"ci95_lo": number(lo95), "ci95_hi": number(hi95),
                "ci_bonf_lo": number(lob), "ci_bonf_hi": number(hib)}
    if degenerate:
        interval = dict.fromkeys(interval)
    return {"resamples": settings["resamples"], "block_entry_dates": block, "seed": settings["seed"],
            "seed_key": key, "dates": dates, "degenerate": degenerate,
            "point_estimate": number(values.mean()),
            "bonferroni_level": 1 - alpha_b, **interval}


def date_series(con, settings):
    """Per group: the ordered entry-date series of mean net and of mean net excess over C0."""
    rows = con.execute("""
        SELECT d.lane, d.selection, d.selector, d.horizon, d.segment, d.entry_date,
               d.mean_net, b.mean_net AS c0_mean_net
        FROM date_stats d
        LEFT JOIN date_stats b ON b.lane = d.lane AND b.horizon = d.horizon
             AND b.entry_date = d.entry_date AND b.selector = 'C0_all_eligible'
             AND b.selection = 'all_events'
        ORDER BY d.lane, d.selection, d.selector, d.horizon, d.segment, d.entry_date""").fetchall()
    grouped = {}
    for lane, selection, selector, horizon, segment, _date, mean_net, c0 in rows:
        entry = grouped.setdefault((lane, selection, selector, horizon, segment),
                                   {"net": [], "excess": [], "missing_c0_dates": 0})
        entry["net"].append(float(mean_net))
        if c0 is None:
            entry["missing_c0_dates"] += 1
        else:
            entry["excess"].append(float(mean_net) - float(c0))
    out = {}
    for key, entry in grouped.items():
        block = settings["block_sessions"][key[3]]
        excess = np.asarray(entry["excess"], dtype=float)
        out[key] = {
            "scored_entry_dates": len(entry["net"]),
            "date_clustered_mean_net": number(float(np.mean(entry["net"])) if entry["net"] else None),
            "date_clustered_mean_excess": number(float(excess.mean()) if excess.size else None),
            "excess_dates": int(excess.size),
            "missing_c0_dates": entry["missing_c0_dates"],
            "bootstrap_excess": bootstrap_group(excess, block, settings, "|".join(key)),
        }
    return out


def label_metrics(con):
    rows = con.execute("SELECT * FROM label_stats").fetchall()
    columns = [d[0] for d in con.description]
    records = [dict(zip(columns, row)) for row in rows]
    # The control population is the whole eligible universe of the lane and segment: C0 with
    # selection='all_events', for every selection. Keying the reference on the record's own
    # selection would measure a top_20 signal against C0's independently ranked 20 names, which
    # is not a superset of the signal's own top 20 and lets recall exceed 1. This matches the
    # excess convention in date_series, which pins the same C0 all_events reference.
    base = {(r["lane"], r["segment"]): r for r in records
            if r["selector"] == "C0_all_eligible" and r["selection"] == "all_events"}
    out = []
    for record in records:
        reference = base.get((record["lane"], record["segment"]))
        for label in LABELS:
            labelled = int(record[f"labelled_{label}"])
            hits = int(record[f"hits_{label}"])
            ref_labelled = int(reference[f"labelled_{label}"]) if reference else 0
            ref_hits = int(reference[f"hits_{label}"]) if reference else 0
            precision = hits / labelled if labelled else None
            base_rate = ref_hits / ref_labelled if ref_labelled else None
            out.append({
                "lane": record["lane"], "selection": record["selection"], "selector": record["selector"],
                "segment": record["segment"], "label": label,
                "decisions": int(record["decisions"]), "labelled": labelled, "hits": hits,
                "unknown_label": int(record["decisions"]) - labelled,
                "precision": number(precision),
                "c0_labelled": ref_labelled, "c0_hits": ref_hits,
                "base_rate_c0": number(base_rate),
                "lift": number(precision / base_rate) if precision is not None and base_rate else None,
                "recall": number(hits / ref_hits) if ref_hits else None,
            })
    return out


def assemble_groups(con, settings):
    rows = con.execute("""
        SELECT g.*, s.spy_reference_mean
        FROM group_stats g
        LEFT JOIN spy_group s ON s.lane = g.lane AND s.selection = g.selection
             AND s.selector = g.selector AND s.horizon = g.horizon AND s.segment = g.segment
        ORDER BY g.lane, g.selection, g.selector, g.horizon, g.segment""").fetchall()
    columns = [d[0] for d in con.description]
    series = date_series(con, settings)
    out = []
    for row in rows:
        record = dict(zip(columns, row))
        key = (record["lane"], record["selection"], record["selector"], record["horizon"],
               record["segment"])
        extra = series.get(key, {})
        scored = int(record["scored"])
        failed = int(record["failed_events"])
        quantiles = record["net_quantiles"] or [None, None, None]
        out.append({
            "lane": record["lane"], "selection": record["selection"], "selector": record["selector"],
            "horizon": record["horizon"], "segment": record["segment"],
            "events": int(record["events"]),
            "distinct_symbols": int(record["distinct_symbols"]),
            "distinct_entry_dates": int(record["distinct_entry_dates"]),
            "scored": scored,
            "no_entry": int(record["no_entry"]),
            "horizon_incomplete": int(record["horizon_incomplete"]),
            "no_exit_bar": int(record["no_exit_bar"]),
            "terminated_early": int(record["terminated_early"]),
            "exit_stale": int(record["exit_stale"]),
            "mean_net": number(record["mean_net"]),
            "p05_net": number(quantiles[0]),
            "median_net": number(quantiles[1]),
            "p95_net": number(quantiles[2]),
            "failed_events": failed,
            "failed_share": number(failed / scored) if scored else None,
            "failed_mean_net": number(record["failed_mean_net"]),
            "stress_mean_net": number(record["stress_mean_net"]),
            "spy_reference_mean": number(record["spy_reference_mean"]),
            "scored_entry_dates": extra.get("scored_entry_dates", 0),
            "date_clustered_mean_net": extra.get("date_clustered_mean_net"),
            "date_clustered_mean_excess": extra.get("date_clustered_mean_excess"),
            "excess_dates": extra.get("excess_dates", 0),
            "missing_c0_dates": extra.get("missing_c0_dates", 0),
            "bootstrap_excess": extra.get("bootstrap_excess"),
        })
    return out


# ---------------------------------------------------------------------------- promotion


def evaluate_promotion(groups, protocol):
    """Mechanical pass/fail per requirement. The identity gate stays open, so nothing promotes."""
    index = {(g["lane"], g["selection"], g["selector"], g["horizon"], g["segment"]): g for g in groups}
    requirements = protocol["promotion"]["requirements"]
    out = []
    for signal in SIGNALS:
        for horizon, _step in HORIZONS:
            primary = {seg: index.get((LANE_PRIMARY, "all_events", signal, horizon, seg))
                       for seg in SCORED_SEGMENTS}
            secondary = {seg: index.get((LANE_SECONDARY, "all_events", signal, horizon, seg))
                         for seg in SCORED_SEGMENTS}

            def value(source, segment, field):
                group = source.get(segment)
                return None if group is None else group.get(field)

            size_ok = all((value(primary, seg, "events") or 0) >= 250
                          and (value(primary, seg, "scored_entry_dates") or 0) >= 100
                          for seg in SCORED_SEGMENTS)
            excess = {seg: value(primary, seg, "date_clustered_mean_excess") for seg in SCORED_SEGMENTS}
            positive = all(e is not None and e > 0 for e in excess.values())
            bounds = {}
            degenerate = {}
            for seg in ("validation", "reserved"):
                boot = value(primary, seg, "bootstrap_excess")
                # A group with no more entry dates than the block length has no resampling
                # variation at all, so its bound is not evidence and can never satisfy this
                # requirement.
                short = bool(boot is not None
                             and (boot.get("degenerate")
                                  or (boot.get("dates") is not None
                                      and boot.get("block_entry_dates") is not None
                                      and boot["dates"] <= boot["block_entry_dates"])))
                degenerate[seg] = short
                bounds[seg] = None if boot is None or short else boot["ci_bonf_lo"]
            excess_ok = positive and all(b is not None and b > 0 for b in bounds.values())
            stress = {seg: value(primary, seg, "stress_mean_net") for seg in ("validation", "reserved")}
            stress_ok = all(s is not None and s >= 0 for s in stress.values())
            signs = []
            for seg in SCORED_SEGMENTS:
                a = value(primary, seg, "date_clustered_mean_excess")
                b = value(secondary, seg, "date_clustered_mean_excess")
                signs.append(bool(a is not None and b is not None
                                  and (a > 0) == (b > 0) and (a < 0) == (b < 0)))
            lane_ok = all(signs)
            checks = [
                {"requirement": requirements[0], "status": "pass" if size_ok else "fail",
                 "observed": {seg: {"events": value(primary, seg, "events"),
                                    "entry_dates": value(primary, seg, "scored_entry_dates")}
                              for seg in SCORED_SEGMENTS}},
                {"requirement": requirements[1], "status": "pass" if excess_ok else "fail",
                 "observed": {"date_clustered_mean_excess": excess, "bonferroni_lower_bound": bounds,
                              "degenerate_excess_bootstrap": degenerate}},
                {"requirement": requirements[2], "status": "pass" if stress_ok else "fail",
                 "observed": {"stress_mean_net": stress}},
                {"requirement": requirements[3], "status": "pass" if lane_ok else "fail",
                 "observed": {"sign_match_by_segment": dict(zip(SCORED_SEGMENTS, signs))}},
                {"requirement": requirements[4], "status": "open",
                 "observed": {"note": "identity, availability and delisting gates are unresolved in v1;"
                                      " reported open so no result can auto-promote"}},
            ]
            out.append({
                "signal": signal, "horizon": horizon,
                "basis": {"lane": LANE_PRIMARY, "selection": "all_events",
                          "lane_sign_comparison": LANE_SECONDARY},
                "checks": checks,
                "mechanical_passes": sum(1 for c in checks if c["status"] == "pass"),
                "open_requirements": sum(1 for c in checks if c["status"] == "open"),
                "status": "not_established",
                "reason": "at least one requirement is open; automatic promotion is impossible by design",
            })
    return out


def requested_names(con, names=("META", "AMD")):
    placeholders = ", ".join(f"'{n}'" for n in names)
    rows = con.execute(f"""
        SELECT symbol, universe, segment, count(*) AS eligible_decisions,
               count(*) FILTER (WHERE c1) AS c1,
               {", ".join(f"count(*) FILTER (WHERE s{i}) AS s{i}" for i in range(1, 6))},
               count(*) FILTER (WHERE has_gap_s4) AS s4_non_contiguous,
               min(session_date) AS first_decision, max(session_date) AS last_decision
        FROM decisions WHERE symbol IN ({placeholders})
        GROUP BY ALL ORDER BY symbol, universe, segment""").fetchall()
    out = []
    for row in rows:
        out.append({
            "symbol": row[0], "universe": row[1], "segment": row[2],
            "eligible_decisions": int(row[3]),
            "C1_hash_sample": int(row[4]),
            **{SIGNALS[i - 1]: int(row[4 + i]) for i in range(1, 6)},
            "s4_non_contiguous_decisions": int(row[10]),
            "first_decision": row[11].isoformat(), "last_decision": row[12].isoformat(),
        })
    return out


# --------------------------------------------------------------------------------- run


def export_events(con, path, scope):
    if os.path.exists(path):
        raise SystemExit(f"refusing to overwrite existing events parquet: {path}")
    where = "" if scope == "all" else "WHERE c1 OR s1 OR s2 OR s3 OR s4 OR s5"
    con.execute(f"""
        COPY (SELECT universe, symbol, session_date, cal_idx, segment, in_primary, cost_bps,
                     med20, dv, dv_ratio, raw_c, all_c, has_gap_s4,
                     c1, s1, s2, s3, s4, s5,
                     lab_up_mover_1d, lab_extreme_up_1d, lab_up_mover_5d, lab_extreme_up_5d,
                     lab_down_mover_1d,
                     horizon, hstep, entry_cal, entry_date, entry_px,
                     exit_cal, exit_date, exit_bar_date, exit_bar_cal, exit_px, last_cal_idx,
                     outcome, exit_stale, terminated_early, net, stress_net
              FROM ev {where}) TO {sql_literal(path)} (FORMAT PARQUET, COMPRESSION ZSTD)""")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    return int(con.execute("SELECT count(*) FROM ev" + (f" {where}" if where else "")).fetchone()[0])


def prior_inspection_log(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        previous = json.load(handle)
    log = previous.get("inspection_log")
    return log if isinstance(log, list) else []


def run(args):
    started = time.time()
    if os.path.exists(args.events_out):  # fail before the work, not after it
        raise SystemExit(f"refusing to overwrite existing events parquet: {args.events_out}")
    protocol, settings = load_protocol(args.protocol)
    asset_rows, name_stats = load_asset_names(args.assets)
    temp_dir = args.temp_dir or os.path.join(os.path.dirname(os.path.abspath(args.events_out)),
                                             "duckdb-temp")
    ledger = collect_daily.Ledger(args.run_ledger) if args.run_ledger else None
    if ledger:
        ledger.write(event="evaluate_start", protocol=PROTOCOL_ID, commit=args.commit,
                     ledger_sha256=args.ledger_sha256, run_at=args.run_at, daily=args.daily)

    con = connect(temp_dir, args.memory_limit, args.threads)
    try:
        dataset = build_calendar(con, args.daily)
        build_features(con)
        gates = build_decisions(con, settings, asset_rows)
        events = build_events(con, settings)
        build_selections(con)
        build_stats(con)
        groups = assemble_groups(con, settings)
        labels = label_metrics(con)
        names = requested_names(con)
        con.execute("DROP TABLE IF EXISTS ev_sel")  # free the selection table before the export
        events["events_written"] = export_events(con, args.events_out, args.events_scope)
    finally:
        con.close()

    body = {
        "schema": SCHEMA,
        "protocol": {"id": protocol["id"], "status": protocol["status"],
                     "sha256": sha256_file(args.protocol),
                     "base_commit": protocol.get("base_commit")},
        "run": {
            "commit": args.commit,
            "ledger_sha256": args.ledger_sha256,
            "run_at": args.run_at,
            "evaluate_sha256": sha256_file(__file__),
            "duckdb_version": duckdb.__version__,
            "numpy_version": np.__version__,
            "elapsed_s": round(time.time() - started, 3),
            # Identity of the private artifact without its location: the absolute path names the
            # host account and directory layout and this JSON is the publishable half of the run.
            "events_parquet": {
                "basename": os.path.basename(args.events_out),
                "sha256": sha256_file(args.events_out),
                "rows": events["events_written"],
            },
            "events_scope": args.events_scope,
        },
        "dataset": dataset,
        "asset_master": name_stats,
        "eligibility_gates": gates,
        "event_construction": events,
        "conventions": {
            "net_return_formula": NET_RETURN_FORMULA,
            "stress_return_formula": STRESS_RETURN_FORMULA,
            "cost_tiers_bps": {"med20_ge_100m": settings["cost_bps_high"],
                               "med20_ge_50m": settings["cost_bps_mid"],
                               "otherwise": settings["cost_bps_low"],
                               LANE_MICRO: settings["micro_cost_bps"]},
            "entry": "all_open on the calendar session immediately after the decision session t",
            "exit": "all_close on calendar session t+h; most recent close at or before it when the"
                    " symbol has no bar there (exit_stale) or its series ended (terminated_early)",
            "calendar": "sorted distinct session_date of SPY with in_raw; horizons count these sessions",
            "contiguity": {"eligibility_bars": ELIGIBILITY_LOOKBACK_BARS,
                           "s4_bars": S4_LOOKBACK_BARS,
                           "rule": "cal_idx[t] - cal_idx[t - k bars] must equal k",
                           "s4_derivation": "range10_p20 reads range10 at u in [t-121, t-2] and"
                                            " range10 at u reads bars u-9..u, so S4's deepest bar"
                                            " is t-130"},
            "descriptive_microcap_lane": protocol["eligibility"]["descriptive_microcap_lane"]["promotion"],
            "descriptive_microcap_scope":
                "this lane applies only the minimum floors (raw close >= "
                f"{settings['micro_min_raw_close_usd']:,.0f} USD, med20 >= "
                f"{settings['micro_med20_min_usd']:,.0f} USD) with no upper bound, so it is the"
                " unrestricted $1/$2M universe and a strict superset of the main universe, not a"
                " microcap subset: every main decision also appears here at a flat"
                f" {settings['micro_cost_bps']:g} bps per side. eligibility_gates"
                ".decisions_by_universe_segment.micro_also_in_main reports, per segment, how many"
                " of this lane's decisions are also main-universe decisions; read its base rates"
                " and lifts as describing that whole universe",
            "outcome_precedence":
                "no_entry (no bar on session t+1) is decided before horizon_incomplete (t+h beyond"
                " the calendar), so one decision carries the same outcome at H1, H5 and H20;"
                " then no_exit_bar, then scored with the exit_stale / terminated_early flags",
            "eligibility_reconciliation":
                "eligibility_gates.excluded_* are independent, overlapping counts over the same"
                " candidate rows; excluded_stepwise applies the same gates in a fixed precedence"
                " so candidate_rows minus its rows equals eligible_base_rows, and"
                " universe_floors gives each universe's price and med20 rejections so"
                " eligible_base_rows minus them equals that universe's decisions",
            "unusable_rows":
                "a contract row is quarantined into dataset.unusable_field_rows when any of"
                " raw_o/raw_h/raw_l/raw_c/raw_v or all_o/all_h/all_l/all_c is null, or when any"
                " of raw_o/raw_c/all_o/all_h/all_l/all_c is not strictly positive: each feeds a"
                " division, and a zero would yield inf rather than null",
            "label_reference":
                "precision is within the selected group; base_rate_c0, lift and recall are always"
                " measured against C0_all_eligible with selection='all_events' on the same lane"
                " and segment - the all-eligible control population - for every selection,"
                " including top_20, so recall is a share of that population's hits and cannot"
                " exceed 1",
            "lane_membership": "a symbol with no current asset-master name stays in both instrument"
                               " lanes and is counted as name_unknown; disagreeing duplicate names"
                               " are counted as name_conflict and treated the same way",
            "quantile": "quantile_cont (linear interpolation) for med20, range10_p20 and the reported"
                        " median/p05/p95",
            "excess": "date-level mean net minus the C0_all_eligible all_events mean net on the same"
                      " lane, horizon and entry date",
            "bootstrap": "circular moving-block bootstrap over the ordered entry dates that carry at"
                         " least one scored event; block length from the protocol",
            "bootstrap_blocks":
                "a block is that many CONSECUTIVE ENTRY DATES OF THE GROUP'S OWN SERIES, not"
                " consecutive calendar sessions: the series holds only the dates on which that"
                " selector had at least one scored event, so for a sparse signal one block spans"
                " more calendar sessions than its length and the clustering it removes is"
                " correspondingly wider. A group whose series is no longer than the block is"
                " reported with degenerate=true and no interval, because every resample is then"
                " one full circular pass over the same values",
            "bootstrap_monte_carlo":
                f"ci_bonf_lo is the {(0.05 / TRIALS) / 2:.6f} empirical quantile of"
                f" {settings['resamples']} resampled means, so it is interpolated from about"
                f" {settings['resamples'] * (0.05 / TRIALS) / 2:.1f} draws in that tail. The bound"
                " therefore carries high Monte-Carlo variance - a different seed can move it"
                " materially at the same data - and is a coarse screen, not a precise threshold",
            "bonferroni_family": TRIALS,
            "spy_reference": "gross SPY all_open[t+1] to all_close[t+h], no cost applied",
            "warmup": "decisions in the warmup segment are counted but never scored",
        },
        "metrics": groups,
        "label_metrics": labels,
        "promotion": evaluate_promotion(groups, protocol),
        "requested_names": names,
    }
    body_hash = sha256_json(body)
    log = prior_inspection_log(args.out)
    log.append({"run_at": args.run_at, "commit": args.commit, "ledger_sha256": args.ledger_sha256,
                "protocol_sha256": body["protocol"]["sha256"],
                "evaluate_sha256": body["run"]["evaluate_sha256"],
                "results_sha256": body_hash})
    body["inspection_log"] = log
    temporary = args.out + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(body, handle, indent=1, sort_keys=True)
    os.replace(temporary, args.out)
    if ledger:
        # The private ledger keeps the absolute location the public results deliberately omit.
        ledger.write(event="evaluate_complete", results_sha256=body_hash,
                     metrics=len(groups), events_written=events["events_written"],
                     events_parquet=os.path.abspath(args.events_out),
                     events_parquet_sha256=body["run"]["events_parquet"]["sha256"],
                     elapsed_s=body["run"]["elapsed_s"])
    print(f"metrics={len(groups)} events={events['event_rows']} written={events['events_written']} "
          f"sessions={dataset['calendar_sessions']} elapsed_s={body['run']['elapsed_s']}", flush=True)
    return 0


# ------------------------------------------------------------------- synthetic fixture


def synth(args):
    """Generate a random-walk daily contract. A fixture for timing, never market evidence."""
    rng = np.random.default_rng(args.seed)
    symbols = [f"SY{i:05d}" for i in range(args.symbols - 1)] + ["SPY"]
    start = np.datetime64("2016-01-04")
    dates = np.busday_offset(start, np.arange(args.sessions), roll="forward")
    con = duckdb.connect()
    con.execute("""CREATE TABLE stage (symbol VARCHAR, session_date DATE, raw_o DOUBLE, raw_h DOUBLE,
                   raw_l DOUBLE, raw_c DOUBLE, raw_v DOUBLE, raw_n BIGINT, raw_vw DOUBLE,
                   all_o DOUBLE, all_h DOUBLE, all_l DOUBLE, all_c DOUBLE,
                   in_raw BOOLEAN, in_all BOOLEAN)""")
    import pandas  # local: only the fixture generator needs a dataframe
    session_dates = np.array([str(d) for d in dates], dtype="datetime64[D]")
    for start in range(0, len(symbols), 50):
        chunk = symbols[start:start + 50]
        size = len(chunk) * args.sessions
        steps = rng.normal(0.0004, 0.02, size=(len(chunk), args.sessions))
        close = (50.0 * np.exp(np.cumsum(steps, axis=1))).reshape(size)
        open_ = close * (1 + rng.normal(0, 0.004, size=size))
        high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, size=size)))
        low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, size=size)))
        # Heavy-tailed per-symbol liquidity so only a minority of the fixture universe clears
        # the protocol's dollar-volume floors, as in a real listed universe.
        level = rng.lognormal(args.liquidity_mu, args.liquidity_sigma, size=(len(chunk), 1))
        volume = (level * rng.lognormal(0, 0.5, size=(len(chunk), args.sessions))).reshape(size)
        frame = pandas.DataFrame({
            "symbol": np.repeat(np.array(chunk, dtype=object), args.sessions),
            "session_date": np.tile(session_dates, len(chunk)),
            "raw_o": open_, "raw_h": high, "raw_l": low, "raw_c": close, "raw_v": volume,
            "raw_n": np.full(size, 1000, dtype="int64"), "raw_vw": close,
            "all_o": open_, "all_h": high, "all_l": low, "all_c": close,
            "in_raw": np.ones(size, dtype=bool), "in_all": np.ones(size, dtype=bool)})
        con.execute("INSERT INTO stage SELECT * FROM frame")
    con.execute(f"COPY stage TO {sql_literal(args.out)} (FORMAT PARQUET, COMPRESSION ZSTD)")
    active = [{"symbol": s, "name": f"{s} Incorporated", "exchange": "NASDAQ", "status": "active",
               "class": "us_equity", "tradable": True} for s in symbols]
    for path, payload in ((args.assets_out[0], active), (args.assets_out[1], [])):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
    print(f"symbols={len(symbols)} sessions={args.sessions} rows={len(symbols) * args.sessions} "
          f"out={args.out}", flush=True)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    runner = sub.add_parser("run", help="evaluate the frozen protocol over a materialized daily contract")
    runner.add_argument("--daily", required=True, help="daily.parquet written by coverage.py materialize")
    runner.add_argument("--assets", nargs="+", required=True, help="asset-master JSON files")
    runner.add_argument("--protocol", required=True)
    runner.add_argument("--out", required=True, help="public results JSON (counts, dates, flags, stats)")
    runner.add_argument("--events-out", required=True, help="private per-event parquet (0600)")
    runner.add_argument("--commit", required=True)
    runner.add_argument("--ledger-sha256", required=True)
    runner.add_argument("--run-at", required=True, help="ISO-8601 UTC")
    runner.add_argument("--events-scope", choices=("all", "selected"), default="all",
                        help="'selected' keeps only C1 and signal events to bound private disk use")
    runner.add_argument("--temp-dir", default=None, help="DuckDB spill directory; default beside --events-out")
    runner.add_argument("--memory-limit", default="6GB")
    runner.add_argument("--threads", type=int, default=0)
    runner.add_argument("--run-ledger", default=None, help="optional append-only private run ledger")
    runner.set_defaults(func=run)

    fixture = sub.add_parser("synth", help="write a synthetic daily contract for timing (not evidence)")
    fixture.add_argument("--out", required=True)
    fixture.add_argument("--assets-out", nargs=2, required=True)
    fixture.add_argument("--symbols", type=int, default=2000)
    fixture.add_argument("--sessions", type=int, default=1500)
    fixture.add_argument("--seed", type=int, default=20260921)
    fixture.add_argument("--liquidity-mu", type=float, default=11.0)
    fixture.add_argument("--liquidity-sigma", type=float, default=2.2)
    fixture.set_defaults(func=synth)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
