"""The screen: session-s rows from asof = s requests, identity dedup, and the candidate conditions that the
screen data decide (gain, $1 floor, suspected unadjusted split at t, exclusions 1 and 2).

Fetch failures (review round 8, R8-5 and E5): a screen batch whose daily-bar or auction request is incomplete
after the re-fetch makes every symbol-session of that batch membership-unknown: excluded and counted by kind.
"""
from __future__ import annotations

from collections import Counter

from core import formulas as FM
from core import identity, plan
from core.calendar import year_of


def _batch_data(store, cal, s, batch):
    reqs = plan.screen_requests(cal, s, batch)
    kinds = {r["kind"]: r for r in reqs}
    status = {k: store.status(r["key"]) for k, r in kinds.items()}
    if any(v is None for v in status.values()):
        raise KeyError(f"screen {s}: unsealed request (no outcome is computed from unsealed data)")
    return kinds, status


def screen_rows(store, cal, sessions: list, symbols: list):
    """Pass 1: the screen table for dedup, plus request, empty and failure counts."""
    rows, counts = [], Counter()
    unknown = set()
    for s in sessions:
        for batch in plan.batches(symbols):
            kinds, status = _batch_data(store, cal, s, batch)
            counts["screen_requests"] += len(kinds)
            bad = [k for k, v in status.items() if v != "complete"]
            if bad:
                for k in bad:
                    counts[f"screen_incomplete:{k}"] += 1
                counts["membership_unknown_symbol_sessions"] += len(batch)
                unknown.update((sym, s) for sym in batch)
                continue
            for k, r in kinds.items():
                if store.empty(r["key"]):
                    counts[f"screen_empty:{k}"] += 1
            raw = store.parsed(kinds["screen_daily_raw"]["key"])
            for sym in batch:
                b = raw.get(sym, {}).get(s)
                if b:
                    rows.append({"symbol": sym, "session": s, "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"],
                                 "v": b["v"]})
    return rows, counts, unknown


def candidates(store, cal, sessions: list, symbols: list, renames: set, active: frozenset = frozenset()):
    """Pass 2 after dedup. Returns (candidates, counts, dedupe report). Counts are per stage, by reason and year."""
    rows, counts, unknown = screen_rows(store, cal, sessions, symbols)
    with_bar = {(r["symbol"], r["session"]) for r in rows}
    stage_symbols_with_bar = {r["symbol"] for r in rows}
    counts["enumerated_symbols_without_bar_in_stage"] = len(set(symbols) - stage_symbols_with_bar)
    dd = identity.dedupe_screen(rows, renames, active)
    counts["dedupe_rows_removed"] = len(dd["removed"])
    removed = dd["removed"]
    found = []
    for s in sessions:
        y = year_of(s)
        prev = cal.offset(s, -1)
        for batch in plan.batches(symbols):
            if (batch[0], s) in unknown:
                continue
            kinds, _ = _batch_data(store, cal, s, batch)
            raw = store.parsed(kinds["screen_daily_raw"]["key"])
            split = store.parsed(kinds["screen_daily_split"]["key"])
            prints = store.parsed(kinds["screen_auctions"]["key"])
            for sym in batch:
                if (sym, s) not in with_bar or (sym, s) in removed:
                    continue
                pr = prints.get(sym, {})
                label = FM.close_label(pr.get(s))
                counts[f"close_label:{y}:{label}"] += 1
                close_t = FM.official_close(pr.get(s))
                if close_t is None:
                    counts["not_event:no_accepted_official_close"] += 1
                    continue
                r_sym, s_sym = raw.get(sym, {}), split.get(sym, {})
                prev_close = FM.official_close(pr.get(prev))
                f_t = FM.share_factor(r_sym, s_sym, prev, s) if prev else None
                if prev_close is None or f_t is None:
                    counts["not_event:ref_undefined"] += 1
                    continue
                ref_t = prev_close / f_t
                if not FM.gain_passes(close_t, ref_t):
                    continue
                if close_t < FM.M["min_official_close"]:
                    counts["gain_but:below_1_dollar"] += 1
                    continue
                if FM.suspected_unadjusted_split(r_sym[s]["c"], (r_sym.get(prev) or {}).get("c"), f_t):
                    counts["gain_but:suspected_unadjusted_split"] += 1
                    continue
                if FM.listing_exchange(pr.get(s)) is None:
                    counts["gain_but:exclusion1_not_listed"] += 1
                    continue
                if FM.exclusion2(sym):
                    counts["gain_but:exclusion2_derivative"] += 1
                    continue
                b, bp = r_sym[s], r_sym.get(prev) or {}
                found.append({"symbol": sym, "session": s, "close_t": close_t, "prev_close": prev_close,
                              "ohlcv": (b["o"], b["h"], b["l"], b["c"], b["v"]),
                              "ohlcv_prev": (bp.get("o"), bp.get("h"), bp.get("l"), bp.get("c"), bp.get("v") or 0)})
    kept, dropped = identity.same_session_guard(found, renames, active)
    counts["same_session_guard_removed"] = len(dropped)
    counts["candidates"] = len(kept)
    return [{"symbol": c["symbol"], "t": c["session"], "close_t": c["close_t"], "prev_close": c["prev_close"]}
            for c in kept], dict(counts), dd["report"]
