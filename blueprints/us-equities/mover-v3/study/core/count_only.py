"""The pre-freeze count-only code (exposure_registry.pre_freeze_access_path). It is the only code that opens
snapshot parts 0, 1 and 3, and it emits only counts, rates and the coverage_rule decisions: no price, spread,
return, covariate value, event list or symbol-level row.

Part 2 (the 2024-11-01 .. 2025-12-31 screen) is not fetched before the freeze (review round 8, R8-3 and E2): the
holdout breakpoint screen is fetched after the freeze under the first granted 'count' entry, sealed before use.
Minute-bar coverage (review round 8, E3): for the pairs the coverage selection picks, the regular-session minute
bars of s are requested with asof = s, and the share of those with daily volume > 0 that have at least one
regular-session minute bar is a year_rule rate.
"""
from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from pathlib import Path

from core import driver
from core import formulas as FM
from core import identity, plan
from core.calendar import year_of
from core.canon import dumps, sha256_bytes
from core.coverage_rule import (checked_thresholds, fetch_margin, identity_limited, item_rule, probe_decision,
                                rule_sha256, year_decision)
from core.fills import fill_at
from core.params import FETCH, SAMPLING, T
from core.records import MERGER_TYPES
from core.store import Store
from pinned.sessions_io_copy import official_price

PART1_RANGE = ("2016-01-04", "2020-12-31")


def _hmod(prefix: str, *parts) -> int:
    return int.from_bytes(hashlib.sha256("|".join((prefix,) + parts).encode("utf-8")).digest()[:8], "big")


def sampled(symbol: str, s: str) -> bool:
    return _hmod("mover-v3-sample", symbol, s) % SAMPLING["sample_modulus"] == 0


def coverage_selected(symbol: str, s: str) -> bool:
    return _hmod("mover-v3-coverage", symbol, s) % SAMPLING["coverage_modulus"] == 0


def coverage_stamps(cal, s: str) -> list:
    hhmm = SAMPLING["coverage_stamps_early_close_hhmm"] if cal.is_early_close(s) else SAMPLING["coverage_stamps_hhmm"]
    return [cal.at(s, h) for h in hhmm]


def stamp_has_eligible(cal, quotes: list, stamp: float) -> bool:
    """Eligible NBBO prevailing at the stamp and at most 1000 ms old, or the first eligible update within 60 s."""
    return fill_at(cal, quotes, stamp, stamp + SAMPLING["coverage_forward_s"]) is not None


# ---------------------------------------------------------------- plan

def part1_requests(cal, s: str, symbols: list) -> list:
    """Sampled pairs of session s: asof = s daily bars (raw, split, all) and auctions of s-1 and s, the same daily
    bars at the provider default asof (identity_diagnostic only), and for coverage-selected pairs with a bar the
    coverage-stamp quotes and the regular-session minute bars (second phase, see part1_phase2)."""
    picked = [x for x in symbols if sampled(x, s)]
    out = plan.screen_requests(cal, s, picked) if picked else []
    prev = cal.offset(s, -1)
    for batch in plan.batches(picked):
        for adj in plan.ADJ:
            out.append(plan.make(f"count_default_asof_daily_{adj}", plan.DATA, "/v2/stocks/bars",
                                 {"symbols": ",".join(batch), "timeframe": "1Day", "start": prev, "end": s,
                                  "adjustment": adj, "feed": FETCH["feed"], "limit": FETCH["page_limit"]},
                                 None, "daily_bars"))
    return out


def part1_phase2(cal, s: str, pairs_with_bar: list) -> list:
    out = []
    for x in pairs_with_bar:
        if not coverage_selected(x, s):
            continue
        for st in coverage_stamps(cal, s):
            out.append(plan.quote_request("count_coverage_quotes", x, s, st - T["prevailing_max_age_s"],
                                          st + SAMPLING["coverage_forward_s"]))
        out.append(plan.make("count_minute", plan.DATA, "/v2/stocks/bars",
                             {"symbols": x, "timeframe": "1Min", "start": plan.t_floor(cal.open(s)),
                              "end": plan.t_ceil(cal.close(s)), "adjustment": "raw", "asof": s, "feed": FETCH["feed"],
                              "limit": FETCH["page_limit"]}, s, "minute_bars"))
    return out


def probe_list(cal, actions: list) -> dict:
    """The fixed identity-probe list: renames effective on a 2016-01-04 .. 2020-12-31 session (sha256 order, first
    100) and ticker reuses (old symbol of one record, new symbol of a later one; same order, first 50)."""
    renames = []
    for r in actions:
        if r.get("type") == "name_change" and r.get("old_symbol") and r.get("new_symbol") and r.get("date"):
            if "2016-01-04" <= r["date"] <= "2020-12-31" and cal.is_session(r["date"]):
                renames.append((r["old_symbol"], r["new_symbol"], r["date"]))
    renames = sorted(set(renames), key=lambda x: hashlib.sha256(f"mover-v3-probe|{x[0]}|{x[1]}|{x[2]}".encode()).hexdigest())
    reuse = []
    for o, n, d in renames:
        later = [(o2, n2, d2) for o2, n2, d2 in renames if n2 == o and d2 > d]
        if later:
            reuse.append((o, d, min(later, key=lambda x: x[2])[2]))
    reuse = sorted(set(reuse), key=lambda x: hashlib.sha256(f"mover-v3-probe|{x[0]}|{x[1]}|{x[2]}".encode()).hexdigest())
    return {"renames": renames[: SAMPLING["probe_rename_cap"]], "reuse": reuse[: SAMPLING["probe_reuse_cap"]]}


def probe_requests(cal, probes: dict) -> list:
    k = SAMPLING["probe_offset_sessions"]
    out = []
    for o, n, d in probes["renames"]:
        lo, hi = cal.offset(d, -k), cal.offset(d, k)
        for sym, asof in ((o, lo), (n, hi)):
            out.append(plan.make("probe_daily_raw", plan.DATA, "/v2/stocks/bars",
                                 {"symbols": sym, "timeframe": "1Day", "start": lo, "end": hi, "adjustment": "raw",
                                  "asof": asof, "feed": FETCH["feed"], "limit": FETCH["page_limit"]}, asof, "daily_bars"))
            out.append(plan.make("probe_auctions", plan.DATA, "/v2/stocks/auctions",
                                 {"symbols": sym, "start": lo, "end": hi, "asof": asof, "feed": FETCH["feed"],
                                  "limit": FETCH["page_limit"]}, asof, "auctions"))
            for q in (cal.offset(d, -1), cal.offset(d, 1)):
                end = cal.at(q, SAMPLING["probe_quote_window_end_hhmm"])
                out.append(plan.quote_request("probe_quotes", sym, asof, end - SAMPLING["probe_quote_window_s"], end))
    for x, d1, d2 in probes["reuse"]:
        s = cal.offset(d1, -k)
        for asof in (cal.offset(d1, -k), cal.offset(d2, k)):
            out.append(plan.make("probe_reuse_daily_raw", plan.DATA, "/v2/stocks/bars",
                                 {"symbols": x, "timeframe": "1Day", "start": s, "end": s, "adjustment": "raw",
                                  "asof": asof, "feed": FETCH["feed"], "limit": FETCH["page_limit"]}, asof, "daily_bars"))
    return out


# ---------------------------------------------------------------- outputs

def _ohlcv(b):
    return None if not b else (b["o"], b["h"], b["l"], b["c"], b["v"])


def part1_counts(store, cal, sessions: list, symbols: list, actions: list) -> dict:
    """The part-1 counts per year (and per listing exchange). Review round 15, N03: a fetch-incomplete request no
    longer drops its batch from every rate. Each rate keeps its own cohort, defined by the requests that decide
    membership in it, and a pair whose membership or outcome is unknown counts against coverage (fail closed):
      official close   cohort: asof = s raw close >= $1. An incomplete raw request puts every sampled pair of the
                       batch in the denominator with no accepted close (raw_fetch_incomplete_pairs); a known member
                       whose auctions request is incomplete stays in the denominator (official_close_fetch_incomplete).
      identity         cohort: default-asof raw close >= $1. An incomplete default-asof request counts every pair of
                       the batch as unreached (default_asof_pairs_unknown); a member whose asof = s raw request is
                       incomplete is unreached (identity_unreached_pairs_fetch_incomplete).
      stamps, minutes  phase2_counts: an incomplete raw request counts each coverage-selected pair's stamps and its
                       minute pair as fetch-incomplete.
    The candidate count for the fetch estimate adds every pair whose candidacy is unknown (sampled_candidates_unknown;
    fetch_estimate counts them as candidates)."""
    new_symbols = {r["new_symbol"] for r in actions if r.get("type") == "name_change" and r.get("new_symbol")}
    c = defaultdict(Counter)
    for s in sessions:
        y = year_of(s)
        picked = [x for x in symbols if sampled(x, s)]
        prev = cal.offset(s, -1)
        for batch in plan.batches(picked):
            reqs = {r["kind"]: r for r in plan.screen_requests(cal, s, batch)}
            dflt = {r["kind"]: r for r in part1_requests(cal, s, batch) if r["kind"].startswith("count_default")}
            ok = {k: store.status(r["key"]) == "complete" for k, r in reqs.items()}
            dflt_key = dflt["count_default_asof_daily_raw"]["key"]
            dflt_ok = store.status(dflt_key) == "complete"
            if not all(ok.values()):
                c[y]["sampled_pairs_fetch_incomplete"] += len(batch)
            for k, r in reqs.items():
                c[y]["screen_requests"] += 1
                if ok[k]:
                    c[y]["screen_requests_empty"] += store.empty(r["key"])
                else:
                    c[y][f"screen_requests_fetch_incomplete:{k}"] += 1
            raw = store.parsed(reqs["screen_daily_raw"]["key"]) if ok["screen_daily_raw"] else None
            split = store.parsed(reqs["screen_daily_split"]["key"]) if ok["screen_daily_split"] else None
            prints = store.parsed(reqs["screen_auctions"]["key"]) if ok["screen_auctions"] else None
            draw = store.parsed(dflt_key) if dflt_ok else None
            for x in batch:
                c[y]["sampled_pairs"] += 1
                b = raw.get(x, {}).get(s) if raw is not None else None
                pr = prints.get(x, {}) if prints is not None else {}
                ex = (FM.listing_exchange(pr.get(s)) or "none") if prints is not None else "unknown"
                # identity diagnostic, per year and per listing exchange (review round 11, C5)
                if draw is None:
                    c[y]["default_asof_pairs_unknown"] += 1
                    c[y][f"default_asof_pairs_unknown:{ex}"] += 1
                else:
                    db = draw.get(x, {}).get(s)
                    if db and db["c"] >= 1.0:
                        c[y]["default_asof_pairs_close_ge_1"] += 1
                        c[y][f"default_asof_pairs_close_ge_1:{ex}"] += 1
                        if raw is None:
                            c[y]["identity_unreached_pairs_fetch_incomplete"] += 1
                            c[y][f"identity_unreached_pairs_fetch_incomplete:{ex}"] += 1
                        elif (b is None or _ohlcv(db) != _ohlcv(b)) and x not in new_symbols:
                            c[y]["identity_unreached_pairs"] += 1
                            c[y][f"identity_unreached_pairs:{ex}"] += 1
                            c[y]["_unreached:" + x] = 1
                if raw is None:
                    # membership in the official-close cohort is unknown: counted against it (fail closed)
                    c[y]["raw_fetch_incomplete_pairs"] += 1
                    c[y]["sampled_candidates_unknown"] += 1
                    continue
                if not b:
                    continue
                # every part-1 output is counted per year and, as '<name>:<listing exchange>', per exchange
                # (pre_freeze_access_path.outputs; review round 10, F9)

                def tally(name, ex=ex, y=y):
                    c[y][name] += 1
                    c[y][f"{name}:{ex}"] += 1
                tally("with_daily_bar")
                f_t = FM.share_factor(raw.get(x, {}), split.get(x, {}), prev, s) if split is not None else None
                prev_b = raw.get(x, {}).get(prev)
                suspected = FM.suspected_unadjusted_split(b["c"], prev_b["c"] if prev_b else None, f_t)
                # the candidate count applies D's floor to the accepted official close only, never to the raw daily
                # close, so a pair with raw close < $1 and official close >= $1 still counts (review round 9, L-3)
                if split is None or prints is None:
                    tally("sampled_candidates_unknown")
                elif not suspected and _sampled_candidate(x, s, prev, pr, f_t):
                    tally("sampled_candidates")
                if b["c"] < 1.0:
                    continue
                tally("with_bar_close_ge_1")
                if prints is None:
                    # a known member of the official-close cohort whose prints are unknown counts against it
                    tally("official_close_fetch_incomplete")
                    continue
                label_c = FM.close_label(pr.get(s))
                label_o = official_price(pr.get(s), "o")[1] or "no_print"
                tally(f"close_label:{label_c}")
                tally(f"open_label:{label_o}")
                if FM.official_close(pr.get(s)) is not None:
                    tally("accepted_official_close")
                if suspected:
                    tally("suspected_unadjusted_split")
    return c


def _sampled_candidate(x: str, s: str, prev: str, pr: dict, f_t) -> bool:
    """The gain condition, D's $1 floor on the accepted official close, and exclusions 1 and 2 (a count only)."""
    if FM.listing_exchange(pr.get(s)) is None or FM.exclusion2(x):
        return False
    close_t, prev_close = FM.official_close(pr.get(s)), FM.official_close(pr.get(prev))
    ref = prev_close / f_t if (prev_close is not None and f_t is not None) else None
    return FM.gain_passes(close_t, ref) and close_t >= FM.M["min_official_close"]


def phase2_counts(store, cal, sessions: list, symbols: list, c: dict) -> None:
    """Coverage stamps and minute pairs. Review round 15, N03: a batch whose asof = s raw request is incomplete has
    an unknown stamp and minute cohort, so each coverage-selected pair of it counts its stamps as fetch-incomplete and
    its minute pair as fetch-incomplete (fail closed), instead of leaving both denominators."""
    for s in sessions:
        y = year_of(s)
        picked = [x for x in symbols if sampled(x, s)]
        for batch in plan.batches(picked):
            reqs = {r["kind"]: r for r in plan.screen_requests(cal, s, batch)}
            if store.status(reqs["screen_daily_raw"]["key"]) != "complete":
                for x in batch:
                    if coverage_selected(x, s):
                        n = len(coverage_stamps(cal, s))
                        c[y]["coverage_stamps_fetch_incomplete"] += n
                        c[y]["coverage_stamps_fetch_incomplete:unknown"] += n
                        c[y]["minute_pairs_fetch_incomplete"] += 1
                        c[y]["minute_pairs_fetch_incomplete:unknown"] += 1
                        c[y]["coverage_pairs_raw_unknown"] += 1
                continue
            raw = store.parsed(reqs["screen_daily_raw"]["key"])
            auctions_ok = store.status(reqs["screen_auctions"]["key"]) == "complete"
            prints = store.parsed(reqs["screen_auctions"]["key"]) if auctions_ok else {}
            with_bar = [x for x in batch if (raw.get(x, {}).get(s) or {}).get("c", 0) >= 1.0]
            for req in part1_phase2(cal, s, with_bar):
                x = req["params"]["symbols"]
                st = store.status(req["key"])
                ex = (FM.listing_exchange(prints.get(x, {}).get(s)) or "none") if auctions_ok else "unknown"

                def tally(name, ex=ex, y=y):       # per year and per listing exchange (review round 11, C5)
                    c[y][name] += 1
                    c[y][f"{name}:{ex}"] += 1
                if req["kind"] == "count_coverage_quotes":
                    stamp = plan_stamp(req)
                    if st != "complete":
                        tally("coverage_stamps_fetch_incomplete")
                        continue
                    qs = store.parsed(req["key"]).get(x, [])
                    tally("coverage_stamps_with_eligible" if stamp_has_eligible(cal, qs, stamp)
                          else "coverage_stamps_without_eligible")
                else:
                    if (raw.get(x, {}).get(s) or {}).get("v", 0) <= 0:
                        continue
                    if st != "complete":
                        tally("minute_pairs_fetch_incomplete")
                        continue
                    rows = store.parsed(req["key"]).get(x, [])
                    have = any(cal.open(s) <= b["t"] < cal.close(s) for b in rows)
                    tally("minute_pairs_with_regular_bar" if have else "minute_pairs_without_regular_bar")


def plan_stamp(req) -> float:
    from core.records import ts_epoch
    return ts_epoch(req["params"]["start"]) + T["prevailing_max_age_s"]


def rates(cy: Counter) -> dict:
    """coverage_rule.year_rule's four rates, each over its own cohort, with every fetch-incomplete member or unknown
    candidate member counted against coverage (review round 15, N03; part1_counts, phase2_counts)."""
    def ratio(a, b):
        return (a / b) if b else None
    q_den = cy["coverage_stamps_with_eligible"] + cy["coverage_stamps_without_eligible"] + cy["coverage_stamps_fetch_incomplete"]
    m_den = cy["minute_pairs_with_regular_bar"] + cy["minute_pairs_without_regular_bar"] + cy["minute_pairs_fetch_incomplete"]
    oc_den = cy["with_bar_close_ge_1"] + cy["raw_fetch_incomplete_pairs"]
    id_num = cy["identity_unreached_pairs"] + cy["identity_unreached_pairs_fetch_incomplete"] + \
        cy["default_asof_pairs_unknown"]
    id_den = cy["default_asof_pairs_close_ge_1"] + cy["default_asof_pairs_unknown"]
    return {"official_close_rate": ratio(cy["accepted_official_close"], oc_den),
            "eligible_quote_rate": ratio(cy["coverage_stamps_with_eligible"], q_den),
            "identity_unreached_rate": ratio(id_num, id_den),
            "minute_bar_rate": ratio(cy["minute_pairs_with_regular_bar"], m_den)}


def candidates_for_bound(cy: Counter) -> int:
    """k of candidate_bound: the sampled candidates plus every sampled pair whose candidacy is unknown because a
    screen request it needs is fetch-incomplete (review round 15, N03: an unknown counts against the margin)."""
    return cy["sampled_candidates"] + cy["sampled_candidates_unknown"]


def candidate_bound(k: int) -> int:
    """20 x (k + 3 sqrt(k) + 3): the per-year candidate bound of the fetch-time margin test."""
    return int(math.ceil(20 * (k + 3 * math.sqrt(k) + 3)))


def outputs(protocol: dict, c: dict, probe: dict, part0: dict, fetch_estimate_seconds: float) -> dict:
    """The committed count-only output: counts, rates and decisions only."""
    th = checked_thresholds(protocol)
    years = {}
    decisions = {}
    for y in range(2016, 2021):
        cy = c.get(y, Counter())
        r = rates(cy)
        decisions[y] = year_decision(r, th)
        public = {k: v for k, v in sorted(cy.items()) if not k.startswith("_")}
        public["distinct_unreached_symbols"] = sum(1 for k in cy if k.startswith("_unreached:"))
        years[str(y)] = {"counts": public, "rates": r, "decision": decisions[y],
                         "candidate_bound": candidate_bound(candidates_for_bound(cy))}
    return {"kind": "mover_v3_count_only_output", "coverage_rule_sha256": rule_sha256(protocol),
            "years": years, "item_rule": item_rule(decisions),
            "validation_identity_limited": identity_limited(years["2020"]["rates"]["identity_unreached_rate"], th),
            "identity_probe": probe_decision(probe, th), "part0": part0,
            "fetch_margin": fetch_margin(fetch_estimate_seconds, th)}


def _spans_the_rename(by_session, other, d: str, same) -> bool:
    """Review round 15, F09: a rename probe matches on a daily endpoint only when both responses are complete, hold
    exactly the same sessions, with at least one before the rename session d and one on or after it (so the history
    is reached across the rename from both tickers), and every session's record is identical (same())."""
    if by_session is None or other is None or set(by_session) != set(other):
        return False
    days = sorted(by_session)
    return any(s < d for s in days) and any(s >= d for s in days) and all(same(by_session[s], other[s]) for s in days)


def _quote_rows(rows) -> list:
    return [(q["ns"], q["bp"], q["ap"], q["bs"], q["as"]) for q in rows]


PROBE_KEYS = ("rename_probes", "bars_match", "auctions_match", "quotes_match", "reuse_cases", "reuse_differ",
              "reuse_failed", "reuse_inconclusive")


def probe_counts(store, cal, probes: dict) -> dict:
    """exposure_registry.pre_freeze_access_path.identity_probe. Review round 15, F09: a daily or auction endpoint
    matches only over the same sessions on both sides, spanning the rename (_spans_the_rename), and the quote endpoint
    only when both windows are complete, non-empty and identical update for update; at e7529b47 one common session and
    two merely non-empty quote responses were a match. N07: each ticker-reuse case is 'reuse_differ' (verified: the
    old issuer's bar at s is there under the early asof and absent or different under the late one), 'reuse_failed'
    (observed failure: the late asof returns the old issuer's identical bar) or 'reuse_inconclusive' (a request is
    fetch-incomplete or the old issuer has no bar at s)."""
    out = Counter()
    k = SAMPLING["probe_offset_sessions"]
    for o, n, d in probes["renames"]:
        out["rename_probes"] += 1
        got = {}
        for sym in (o, n):
            reqs = [r for r in probe_requests(cal, {"renames": [(o, n, d)], "reuse": []})
                    if r["params"]["symbols"] == sym]
            got[sym] = {r["kind"] + (r["params"].get("end") if r["kind"] == "probe_quotes" else ""): r for r in reqs}

        def data(sym, kind):
            r = got[sym][kind]
            return store.parsed(r["key"]).get(sym, [] if kind.startswith("probe_quotes") else {}) \
                if store.status(r["key"]) == "complete" else None
        out["bars_match"] += _spans_the_rename(data(o, "probe_daily_raw"), data(n, "probe_daily_raw"), d,
                                               lambda a, b: _ohlcv(a) == _ohlcv(b))
        out["auctions_match"] += _spans_the_rename(data(o, "probe_auctions"), data(n, "probe_auctions"), d,
                                                   lambda a, b: a == b)
        qk = sorted(kk for kk in got[o] if kk.startswith("probe_quotes"))
        qo = {kk: data(o, kk) for kk in qk}
        qn = {kk: data(n, kk) for kk in qk}
        out["quotes_match"] += bool(qk) and all(qo[kk] and qn[kk] and _quote_rows(qo[kk]) == _quote_rows(qn[kk])
                                                for kk in qk)
    for x, d1, d2 in probes["reuse"]:
        out["reuse_cases"] += 1
        reqs = [r for r in probe_requests(cal, {"renames": [], "reuse": [(x, d1, d2)]})]
        vals = [store.parsed(r["key"]).get(x, {}) if store.status(r["key"]) == "complete" else None for r in reqs]
        s = cal.offset(d1, -k)
        if vals[0] is None or vals[1] is None or vals[0].get(s) is None:
            out["reuse_inconclusive"] += 1
        elif vals[1].get(s) is not None and _ohlcv(vals[0][s]) == _ohlcv(vals[1][s]):
            out["reuse_failed"] += 1
        else:
            out["reuse_differ"] += 1
    return {key: int(out[key]) for key in PROBE_KEYS}


# ---------------------------------------------------------------- native dry run (freeze_preconditions, E4)

DRY_RUN_WINDOW = ("2021-01-04", "2024-10-31")   # after validation, before the holdout breakpoint screen


def check_dry_run_window(sessions: list) -> None:
    """A first, calendar-free bound on the sessions: 2021-01-04 .. 2024-10-17 (the holdout breakpoint screen starts
    2024-11-01, and E+5 of the last session must end before it). It is necessary, not sufficient: the lookbacks of
    a session reach further back (review round 11, C1), so check_dry_run_reach bounds every planned request."""
    bad = [s for s in sessions if not DRY_RUN_WINDOW[0] <= s <= "2024-10-17"]
    if not sessions or bad:
        raise ValueError(f"dry-run sessions must lie in {DRY_RUN_WINDOW[0]} .. 2024-10-17 (so every window ends "
                         f"before {DRY_RUN_WINDOW[1]}): {bad[:5]}")


def check_dry_run_reach(reqs: list) -> None:
    """Review round 11, C1: every planned dry-run request, not only its session, lies inside the already exposed
    window: its start (a date, or the UTC date of a timestamp: a minute-bar start at 04:00 ET or a quote-window
    start) is on or after 2021-01-04 and its end on or before 2024-10-31. The per-event daily bars reach t-60, the
    auctions t-22, the minute bars 04:00 ET of t-19 and the screen s-1, so a session earlier than about
    cal.offset('2021-01-04', 60) is refused. Any earlier request would read v3 validation data before the freeze,
    which exposure_registry.update_rule forbids."""
    bad = []
    for r in reqs:
        p = r.get("params") or {}
        start, end = p.get("start"), p.get("end")
        if not isinstance(start, str) or not isinstance(end, str) or start[:10] < DRY_RUN_WINDOW[0] \
                or end[:10] > DRY_RUN_WINDOW[1]:
            bad.append((r["kind"], start, end))
    if not reqs or bad:
        raise ValueError(f"dry-run requests must reach only {DRY_RUN_WINDOW[0]} .. {DRY_RUN_WINDOW[1]}; "
                         f"{len(bad)} do not, for example {sorted(bad)[:3]}")


def dry_run_requests(cal, sessions: list, symbols: list) -> list:
    """The plumbing check on an already exposed window: the screen of each session, and for each (symbol, session)
    the per-event requests, the b_lane entry window and every forward exit window (W0 with the prevailing-quote
    lookback, W1 and the search windows E+1 .. E+5; review round 10, F6), with asof = the session. It refuses a plan
    with any request outside the exposed window (check_dry_run_reach; review round 11, C1)."""
    check_dry_run_window(sessions)
    out = []
    for s in sessions:
        out.extend(plan.screen_requests(cal, s, symbols))
        for x in symbols:
            end = cal.offset(s, 10)
            out.extend(plan.event_requests(cal, x, s, end))
            out.append(plan.entry_window(cal, x, s, "b_lane"))
            e, stamp, _ = plan.planned_exit(cal, s, "b_lane", end)
            for w in plan.exit_windows(cal, e, stamp):
                out.append(plan.quote_request("quote_exit", x, s, w[0], w[1]))
    out = sorted({r["key"]: r for r in out}.values(), key=lambda r: r["key"])
    check_dry_run_reach(out)
    return out


def dry_run(cal, sessions: list, symbols: list, transports: dict, snapshot_root, fetch_date: str,
            clock=driver.utc_now, progress: dict | None = None) -> dict:
    """freeze_preconditions: the native dry run through core/driver.py and the transport, sealed, re-read from the
    seal and counted (counts only; run.py dry-run writes the output with its run-log line). progress, when given,
    receives the snapshot sha256 as soon as it is sealed, so a run that fails afterwards still logs it (review round
    12, F3)."""
    dry_run_requests(cal, sessions, symbols)            # refuses before any fetch (review round 11, C1)
    store = Store()
    root = Path(snapshot_root) / "dry-run"
    driver.stage_fetch(lambda st: dry_run_requests(cal, sessions, symbols), transports, store, fetch_date,
                       clock=clock)
    sha = store.write(root)
    if progress is not None:
        progress["dry-run"] = sha
    return dry_run_output(snapshot_root, sha, sessions, symbols)


def dry_run_output(snapshot_root, sha: str, sessions: list, symbols: list) -> dict:
    """The dry-run output from its sealed snapshot alone (review round 15, N02 / R14-open-2: run.py dry-run
    recomputes it to adopt an output that a hard kill left with no run-log line)."""
    sealed = Store.read(Path(snapshot_root) / "dry-run", sha)
    return {"kind": "mover_v3_dry_run_output", "snapshot_sha256": sha, "sessions": list(sessions),
            "symbols_count": len(symbols), "counts": dry_run_counts(sealed),
            "incomplete_by_kind": sealed.incomplete_by_kind()}


def dry_run_counts(store) -> dict:
    """Counts only: requests, pages, empty responses and fetch-incomplete requests by kind, and the number of
    normalized records each parser produced. No price, spread, return or event list."""
    out = {}
    for key, req in sorted(store.req.items()):
        row = out.setdefault(req["kind"], Counter())
        row["requests"] += 1
        row["pages"] += len(store.state[key]["pages"])
        if store.status(key) != "complete":
            row["fetch_incomplete"] += 1
            continue
        if store.empty(key):
            row["empty"] += 1
        parsed = store.parsed(key)
        row["records"] += len(parsed) if isinstance(parsed, list) else sum(len(v) for v in parsed.values())
    return {k: dict(v) for k, v in out.items()}


# ---------------------------------------------------------------- the committed count-only run (review round 9, M-2)

def part0_requests(fetch_date: str) -> list:
    """Part 0: the asset master (trading API) and every corporate action from 2016-01-01 to the fetch date."""
    return plan.assets_requests() + [plan.corporate_actions_request("2016-01-01", fetch_date)]


def enumeration_from(store) -> dict:
    """The sealed symbol list from part 0's responses (every request complete, or the run stops)."""
    assets, actions = [], []
    for key, req in sorted(store.req.items()):
        if store.status(key) != "complete":
            raise RuntimeError(f"enumeration request {key} is incomplete")
        if req["kind"] == "assets":
            assets.extend(store.parsed(key))
        elif req["kind"] == "corporate_actions":
            actions.extend(store.parsed(key))
    enum = identity.enumerate_symbols(assets, actions)
    return {"symbols": enum["symbols"], "counts": enum["counts"], "actions": actions,
            "active": sorted(x["symbol"] for x in assets if x.get("status") == "active")}


def part0_counts(enum: dict) -> dict:
    """Per year, split, reverse-split, cash-dividend, merger and name-change records, and enumerated symbols per
    source (exposure_registry.pre_freeze_access_path.outputs)."""
    by = defaultdict(Counter)
    for r in enum["actions"]:
        typ = "merger" if r.get("type") in MERGER_TYPES else r.get("type")
        if typ in ("forward_split", "reverse_split", "cash_dividend", "merger", "name_change") and r.get("date"):
            by[r["date"][:4]][typ] += 1
    return {"enumerated_symbols": dict(enum["counts"]), "actions_by_year": {y: dict(v) for y, v in sorted(by.items())}}


def part1_planner(cal, sessions: list, symbols: list):
    def requests(store) -> list:
        reqs = [r for s in sessions for r in part1_requests(cal, s, symbols)]
        if any(not store.has(r["key"]) for r in reqs):
            return reqs
        for s in sessions:
            for batch in plan.batches([x for x in symbols if sampled(x, s)]):
                key = next(r["key"] for r in plan.screen_requests(cal, s, batch) if r["kind"] == "screen_daily_raw")
                if store.status(key) != "complete":
                    continue
                raw = store.parsed(key)
                reqs += part1_phase2(cal, s, [x for x in batch if (raw.get(x, {}).get(s) or {}).get("c", 0) >= 1.0])
        return reqs
    return requests


def pinned_rate_limit(protocol: dict) -> dict:
    """exposure_registry.pre_freeze_access_path.rate_limit: the provider's documented rate limit and its source,
    committed in the protocol before the count-only run (review round 10, L1). It decides fetch_margin, so it is not a
    command-line input."""
    rl = ((protocol.get("exposure_registry") or {}).get("pre_freeze_access_path") or {}).get("rate_limit") or {}
    per, src = rl.get("per_minute"), rl.get("source")
    if isinstance(per, bool) or not isinstance(per, (int, float)) or per <= 0 or not isinstance(src, str) or not src:
        raise ValueError("pre_freeze_access_path.rate_limit needs a positive per_minute and its source before the "
                         "count-only run")
    return {"per_minute": float(per), "source": src}


def fetch_estimate(cal, n_symbols: int, k_by_year: dict, rate_per_minute: float) -> dict:
    """coverage_rule.thresholds.fetch_estimate.rule: the full 2016-2020 screen requests plus, per year,
    candidate_bound(k) candidates times the per-event request count (core.plan.per_event_requests_max), at the
    documented rate limit."""
    screen = len(cal.range(*PART1_RANGE)) * 4 * math.ceil(n_symbols / FETCH["screen_symbols_per_request"])
    per_event = plan.per_event_requests_max()
    bounds = {str(y): candidate_bound(k) for y, k in sorted(k_by_year.items())}
    requests = screen + per_event * sum(bounds.values())
    return {"screen_requests": screen, "per_event_requests": per_event, "candidate_bounds": bounds,
            "requests": requests, "rate_per_minute": rate_per_minute,
            "estimate_seconds": requests / rate_per_minute * 60.0}


def run(protocol: dict, cal, transports: dict, snapshot_root, fetch_date: str, rate_per_minute: float,
        clock=driver.utc_now, sessions: list | None = None, progress: dict | None = None) -> dict:
    """Parts 0, 1 (with its second phase) and 3, each fetched through core.driver.stage_fetch, sealed, re-read from
    the seal and counted. coverage_rule's hash is checked before any fetch or read (coverage_rule.decided_by_code;
    review round 9, L-3). Returns the output (counts, rates and decisions only) and the sealed snapshot hashes.
    progress, when given, receives each part's sha256 as soon as the part is sealed, so a run that fails after a seal
    still logs every sealed part on its failed end line (pre_freeze_access_path.runs; review round 12, F3)."""
    checked_thresholds(protocol)
    root = Path(snapshot_root)

    def sealed(name, planner):
        store = Store()
        driver.stage_fetch(planner, transports, store, fetch_date, clock=clock)
        sha = store.write(root / name)
        if progress is not None:
            progress[name] = sha
        return Store.read(root / name, sha), sha

    s0, sha0 = sealed("part0", lambda st: part0_requests(fetch_date))
    enum = enumeration_from(s0)
    enum_bytes = (dumps(enum) + "\n").encode("utf-8")
    (root / "enumeration.json").write_bytes(enum_bytes)
    sessions = sessions or cal.range(*PART1_RANGE)
    _, sha1 = sealed("part1", part1_planner(cal, sessions, enum["symbols"]))
    probes = probe_list(cal, enum["actions"])
    _, sha3 = sealed("part3", lambda st: probe_requests(cal, probes))
    return output_from_sealed(protocol, cal, root, {"part0": sha0, "part1": sha1, "part3": sha3},
                              rate_per_minute, sessions)


def output_from_sealed(protocol: dict, cal, snapshot_root, shas: dict, rate_per_minute: float,
                       sessions: list | None = None) -> dict:
    """The count-only output (counts, rates and decisions only) from the sealed parts alone, each read back from
    <root>/<part> and checked against its sha256 (review round 15, N02 / R14-open-2): run() computes it this way after
    sealing, and run.py count-only recomputes it from the same seals to adopt an output that a hard kill left with no
    run-log line (the enumeration file must also be the one part 0 yields). No provider is called."""
    checked_thresholds(protocol)
    root = Path(snapshot_root)
    s0, s1, s3 = (Store.read(root / name, shas[name]) for name in ("part0", "part1", "part3"))
    enum = enumeration_from(s0)
    enum_bytes = (dumps(enum) + "\n").encode("utf-8")
    on_disk = root / "enumeration.json"
    if not on_disk.exists() or on_disk.read_bytes() != enum_bytes:
        raise ValueError("enumeration.json is not the enumeration that sealed part 0 yields")
    sessions = sessions or cal.range(*PART1_RANGE)
    probes = probe_list(cal, enum["actions"])
    c = part1_counts(s1, cal, sessions, enum["symbols"], enum["actions"])
    phase2_counts(s1, cal, sessions, enum["symbols"], c)
    part0 = {**part0_counts(enum), "enumeration_sha256": sha256_bytes(enum_bytes)}
    est = fetch_estimate(cal, len(enum["symbols"]), {y: candidates_for_bound(c.get(y, Counter()))
                                                     for y in range(2016, 2021)}, rate_per_minute)
    out = outputs(protocol, c, probe_counts(s3, cal, probes), part0, est["estimate_seconds"])
    out["fetch_estimate"] = est
    out["snapshots"] = {name: shas[name] for name in ("part0", "part1", "part3")}
    return out
