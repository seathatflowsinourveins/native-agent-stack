"""The screen: session-s rows from asof = s requests, identity dedup, and the candidate conditions that the
screen data decide (exclusion 1, the accepted close, gain, $1 floor, suspected unadjusted split at t, exclusion 2).

Fetch failures (review round 8, R8-5 and E5): a screen batch whose daily-bar or auction request is incomplete
after the re-fetch makes every symbol-session of that batch membership-unknown: excluded and counted by kind.
"""
from __future__ import annotations

from collections import Counter

from core import formulas as FM
from core import identity, plan
from core.calendar import year_of


SCREEN_KINDS = ("screen_daily_raw", "screen_daily_split", "screen_daily_all", "screen_auctions")


def _default_view(store, cal, s, batch) -> dict:
    """One batch of session s from the stage's own screen requests (keys of plan.screen_requests)."""
    kinds = {r["kind"]: r for r in plan.screen_requests(cal, s, batch)}
    status = {k: store.status(r["key"]) for k, r in kinds.items()}
    if any(v is None for v in status.values()):
        raise KeyError(f"screen {s}: unsealed request (no outcome is computed from unsealed data)")
    bad = sorted(k for k, v in status.items() if v != "complete")
    return {"requests": len(kinds), "incomplete_kinds": bad, "unknown": set(batch) if bad else set(),
            "empty": [k for k, r in kinds.items() if status[k] == "complete" and store.empty(r["key"])],
            "data": {} if bad else {k: store.parsed(r["key"]) for k, r in kinds.items()}}


def view(store, cal, s, batch) -> dict:
    """The screen rows of one batch of session s: {"requests", "incomplete_kinds", "unknown" (symbols whose
    screen request is fetch-incomplete: membership-unknown), "empty" (kinds with no row), "data" {kind: {symbol:
    rows}}}. A holdout store merges its sealed collection batches per (symbol, session) (core.holdout_store)."""
    fn = getattr(store, "screen_view", None)
    return fn(cal, s, batch) if fn is not None else _default_view(store, cal, s, batch)


def screen_rows(store, cal, sessions: list, symbols: list):
    """Pass 1: the screen table for dedup, plus request, empty and failure counts."""
    rows, counts = [], Counter()
    unknown = set()
    for s in sessions:
        for batch in plan.batches(symbols):
            v = view(store, cal, s, batch)
            counts["screen_requests"] += v["requests"]
            for k in v["incomplete_kinds"]:
                counts[f"screen_incomplete:{k}"] += 1
            for k in v["empty"]:
                counts[f"screen_empty:{k}"] += 1
            if v["unknown"]:
                counts["membership_unknown_symbol_sessions"] += len(v["unknown"])
                unknown.update((sym, s) for sym in v["unknown"])
            raw = v["data"].get("screen_daily_raw", {})
            for sym in batch:
                if sym in v["unknown"]:
                    continue
                b = raw.get(sym, {}).get(s)
                if b:
                    rows.append({"symbol": sym, "session": s, "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"],
                                 "v": b["v"]})
    return rows, counts, unknown


def candidates(store, cal, sessions: list, symbols: list, renames: set, active: frozenset = frozenset()):
    """Pass 2, then identity dedup of the candidates as of each candidate's session, then the same-session guard.
    Returns (candidates, counts, dedupe report). Counts are per stage, by reason and year; the per-reason counts are
    over the screen rows before dedup."""
    rows, counts, unknown = screen_rows(store, cal, sessions, symbols)
    with_bar = {(r["symbol"], r["session"]) for r in rows}
    stage_symbols_with_bar = {r["symbol"] for r in rows}
    counts["enumerated_symbols_without_bar_in_stage"] = len(set(symbols) - stage_symbols_with_bar)
    found = []
    for s in sessions:
        y = year_of(s)
        prev = cal.offset(s, -1)
        for batch in plan.batches(symbols):
            v = view(store, cal, s, batch)
            raw = v["data"].get("screen_daily_raw", {})
            split = v["data"].get("screen_daily_split", {})
            prints = v["data"].get("screen_auctions", {})
            for sym in batch:
                if (sym, s) in unknown or (sym, s) not in with_bar:
                    continue
                pr = prints.get(sym, {})
                label = FM.close_label(pr.get(s))
                counts[f"close_label:{y}:{label}"] += 1
                # exclusion 1 comes first: without a listing-exchange opening print no close is accepted, so after
                # the accepted-close check this rule could never fire (review round 9, M-7)
                if FM.listing_exchange(pr.get(s)) is None:
                    counts["not_event:exclusion1_not_listed"] += 1
                    continue
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
                if FM.exclusion2(sym):
                    counts["gain_but:exclusion2_derivative"] += 1
                    continue
                b, bp = r_sym[s], r_sym.get(prev) or {}
                found.append({"symbol": sym, "session": s, "close_t": close_t, "prev_close": prev_close,
                              "ohlcv": (b["o"], b["h"], b["l"], b["c"], b["v"]),
                              "ohlcv_prev": (bp.get("o"), bp.get("h"), bp.get("l"), bp.get("c"), bp.get("v") or 0)})
    # identity dedup as of each candidate's own session: rows after t never decide membership at t (review round
    # 12, Codex P1; universe_and_identity.dedup)
    dd = identity.dedupe_asof(rows, renames, active, [(c["symbol"], c["session"]) for c in found])
    counts["dedupe_candidates_removed"] = len(dd["removed"])
    found = [c for c in found if (c["symbol"], c["session"]) not in dd["removed"]]
    kept, dropped = identity.same_session_guard(found, renames, active)
    counts["same_session_guard_removed"] = len(dropped)
    counts["candidates"] = len(kept)
    return [{"symbol": c["symbol"], "t": c["session"], "close_t": c["close_t"], "prev_close": c["prev_close"]}
            for c in kept], dict(counts), dd["report"]
