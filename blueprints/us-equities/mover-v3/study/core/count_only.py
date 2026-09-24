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

from core import formulas as FM
from core import plan
from core.calendar import year_of
from core.coverage_rule import (checked_thresholds, fetch_margin, identity_limited, item_rule, probe_decision,
                                rule_sha256, year_decision)
from core.fills import fill_at
from core.params import FETCH, SAMPLING, T
from pinned.sessions_io_copy import official_price


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
    new_symbols = {r["new_symbol"] for r in actions if r.get("type") == "name_change" and r.get("new_symbol")}
    c = defaultdict(Counter)
    for s in sessions:
        y = year_of(s)
        picked = [x for x in symbols if sampled(x, s)]
        prev = cal.offset(s, -1)
        for batch in plan.batches(picked):
            reqs = {r["kind"]: r for r in plan.screen_requests(cal, s, batch)}
            dflt = {r["kind"]: r for r in part1_requests(cal, s, batch) if r["kind"].startswith("count_default")}
            if any(store.status(r["key"]) != "complete" for r in reqs.values()):
                c[y]["sampled_pairs_fetch_incomplete"] += len(batch)
                continue
            for r in reqs.values():
                c[y]["screen_requests"] += 1
                c[y]["screen_requests_empty"] += store.empty(r["key"])
            raw = store.parsed(reqs["screen_daily_raw"]["key"])
            split = store.parsed(reqs["screen_daily_split"]["key"])
            prints = store.parsed(reqs["screen_auctions"]["key"])
            draw = store.parsed(dflt["count_default_asof_daily_raw"]["key"]) \
                if store.status(dflt["count_default_asof_daily_raw"]["key"]) == "complete" else {}
            for x in batch:
                c[y]["sampled_pairs"] += 1
                b = raw.get(x, {}).get(s)
                pr = prints.get(x, {})
                ex = FM.listing_exchange(pr.get(s)) or "none"
                # identity diagnostic
                db = draw.get(x, {}).get(s)
                if db and db["c"] >= 1.0:
                    c[y]["default_asof_pairs_close_ge_1"] += 1
                    if (b is None or _ohlcv(db) != _ohlcv(b)) and x not in new_symbols:
                        c[y]["identity_unreached_pairs"] += 1
                        c[y]["_unreached:" + x] = 1
                if not b:
                    continue
                c[y]["with_daily_bar"] += 1
                c[y][f"with_daily_bar:{ex}"] += 1
                if b["c"] < 1.0:
                    continue
                c[y]["with_bar_close_ge_1"] += 1
                label_c = FM.close_label(pr.get(s))
                label_o = official_price(pr.get(s), "o")[1] or "no_print"
                c[y][f"close_label:{label_c}"] += 1
                c[y][f"open_label:{label_o}"] += 1
                if FM.official_close(pr.get(s)) is not None:
                    c[y]["accepted_official_close"] += 1
                f_t = FM.share_factor(raw.get(x, {}), split.get(x, {}), prev, s)
                prev_b = raw.get(x, {}).get(prev)
                if FM.suspected_unadjusted_split(b["c"], prev_b["c"] if prev_b else None, f_t):
                    c[y]["suspected_unadjusted_split"] += 1
                    continue
                close_t, prev_close = FM.official_close(pr.get(s)), FM.official_close(pr.get(prev))
                ref = prev_close / f_t if (prev_close is not None and f_t is not None) else None
                if (FM.gain_passes(close_t, ref) and close_t >= 1.0 and FM.listing_exchange(pr.get(s))
                        and not FM.exclusion2(x)):
                    c[y]["sampled_candidates"] += 1
    return c


def phase2_counts(store, cal, sessions: list, symbols: list, c: dict) -> None:
    for s in sessions:
        y = year_of(s)
        picked = [x for x in symbols if sampled(x, s)]
        for batch in plan.batches(picked):
            reqs = {r["kind"]: r for r in plan.screen_requests(cal, s, batch)}
            if store.status(reqs["screen_daily_raw"]["key"]) != "complete":
                continue
            raw = store.parsed(reqs["screen_daily_raw"]["key"])
            with_bar = [x for x in batch if (raw.get(x, {}).get(s) or {}).get("c", 0) >= 1.0]
            for req in part1_phase2(cal, s, with_bar):
                x = req["params"]["symbols"]
                st = store.status(req["key"])
                if req["kind"] == "count_coverage_quotes":
                    stamp = plan_stamp(req)
                    if st != "complete":
                        c[y]["coverage_stamps_fetch_incomplete"] += 1
                        continue
                    qs = store.parsed(req["key"]).get(x, [])
                    c[y]["coverage_stamps_with_eligible" if stamp_has_eligible(cal, qs, stamp)
                         else "coverage_stamps_without_eligible"] += 1
                else:
                    if (raw.get(x, {}).get(s) or {}).get("v", 0) <= 0:
                        continue
                    if st != "complete":
                        c[y]["minute_pairs_fetch_incomplete"] += 1
                        continue
                    rows = store.parsed(req["key"]).get(x, [])
                    have = any(cal.open(s) <= b["t"] < cal.close(s) for b in rows)
                    c[y]["minute_pairs_with_regular_bar" if have else "minute_pairs_without_regular_bar"] += 1


def plan_stamp(req) -> float:
    from core.records import ts_epoch
    return ts_epoch(req["params"]["start"]) + T["prevailing_max_age_s"]


def rates(cy: Counter) -> dict:
    def ratio(a, b):
        return (a / b) if b else None
    q_den = cy["coverage_stamps_with_eligible"] + cy["coverage_stamps_without_eligible"] + cy["coverage_stamps_fetch_incomplete"]
    m_den = cy["minute_pairs_with_regular_bar"] + cy["minute_pairs_without_regular_bar"] + cy["minute_pairs_fetch_incomplete"]
    return {"official_close_rate": ratio(cy["accepted_official_close"], cy["with_bar_close_ge_1"]),
            "eligible_quote_rate": ratio(cy["coverage_stamps_with_eligible"], q_den),
            "identity_unreached_rate": ratio(cy["identity_unreached_pairs"], cy["default_asof_pairs_close_ge_1"]),
            "minute_bar_rate": ratio(cy["minute_pairs_with_regular_bar"], m_den)}


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
                         "candidate_bound": candidate_bound(cy["sampled_candidates"])}
    return {"kind": "mover_v3_count_only_output", "coverage_rule_sha256": rule_sha256(protocol),
            "years": years, "item_rule": item_rule(decisions),
            "validation_identity_limited": identity_limited(years["2020"]["rates"]["identity_unreached_rate"], th),
            "identity_probe": probe_decision(probe, th), "part0": part0,
            "fetch_margin": fetch_margin(fetch_estimate_seconds, th)}


def probe_counts(store, cal, probes: dict) -> dict:
    out = Counter()
    k = SAMPLING["probe_offset_sessions"]
    for o, n, d in probes["renames"]:
        out["rename_probes"] += 1
        lo, hi = cal.offset(d, -k), cal.offset(d, k)
        got = {}
        for sym, asof in ((o, lo), (n, hi)):
            reqs = [r for r in probe_requests(cal, {"renames": [(o, n, d)], "reuse": []})
                    if r["params"]["symbols"] == sym]
            got[sym] = {r["kind"] + (r["params"].get("end") if r["kind"] == "probe_quotes" else ""): r for r in reqs}
        def data(sym, kind):
            r = got[sym][kind]
            return store.parsed(r["key"]).get(sym, {}) if store.status(r["key"]) == "complete" else None
        b_o, b_n = data(o, "probe_daily_raw"), data(n, "probe_daily_raw")
        common = sorted(set(b_o or {}) & set(b_n or {}))
        out["bars_match"] += bool(common) and all(_ohlcv(b_o[s]) == _ohlcv(b_n[s]) for s in common)
        a_o, a_n = data(o, "probe_auctions"), data(n, "probe_auctions")
        common = sorted(set(a_o or {}) & set(a_n or {}))
        out["auctions_match"] += bool(common) and all(a_o[s] == a_n[s] for s in common)
        qk = [kk for kk in got[o] if kk.startswith("probe_quotes")]
        out["quotes_match"] += all(bool(data(o, kk)) and bool(data(n, kk)) for kk in qk)
    for x, d1, d2 in probes["reuse"]:
        out["reuse_cases"] += 1
        reqs = [r for r in probe_requests(cal, {"renames": [], "reuse": [(x, d1, d2)]})]
        vals = [store.parsed(r["key"]).get(x, {}) if store.status(r["key"]) == "complete" else None for r in reqs]
        if vals[0] is not None and vals[1] is not None:
            s = cal.offset(d1, -k)
            out["reuse_differ"] += _ohlcv(vals[0].get(s)) != _ohlcv(vals[1].get(s))
    return {k: int(out[k]) for k in ("rename_probes", "bars_match", "auctions_match", "quotes_match",
                                      "reuse_cases", "reuse_differ")}


# ---------------------------------------------------------------- native dry run (freeze_preconditions, E4)

def dry_run_requests(cal, sessions: list, symbols: list) -> list:
    """The plumbing check on an already exposed window: the screen of each session, and for each (symbol, session)
    the per-event requests and the b_lane entry and first exit windows, with asof = the session."""
    out = []
    for s in sessions:
        out.extend(plan.screen_requests(cal, s, symbols))
        for x in symbols:
            end = cal.offset(s, 10)
            out.extend(plan.event_requests(cal, x, s, end))
            out.append(plan.entry_window(cal, x, s, "b_lane"))
            e, stamp, _ = plan.planned_exit(cal, s, "b_lane", end)
            w = plan.exit_windows(cal, e, stamp)[0]
            out.append(plan.quote_request("quote_exit", x, s, w[0], w[1]))
    return sorted({r["key"]: r for r in out}.values(), key=lambda r: r["key"])


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
