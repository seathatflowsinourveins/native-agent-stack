"""The three arms and H3-c's legs: entries, exits, terminal exits, corporate actions and the net return.

trade(ev, arm, ctx, store) walks one trade through the rules in order and returns either
{"needs": [requests]} (the next quote windows the plan must fetch, from sealed inputs only) or the trade record.
With ctx.mode == "count" it stops after the entry-presence and in-hold split-record checks and computes no mid,
spread, exit value or return (chronology.holdout.count_unit).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from core import costs, fills, plan
from core import formulas as FM
from core.chronology import embargoed, segment_of
from core.params import C, T
from core.records import MERGER_TYPES, SPLIT_TYPES, et_date

MULTI_SESSION_ARMS = ("b_lane", "b_overnight")


@dataclass
class Ctx:
    cal: object
    stage: str
    segs: list
    dropped_years: frozenset = frozenset()
    actions: list = field(default_factory=list)
    fees: object = None
    cells: dict | None = None
    mode: str = "read"          # "read" (full evaluation), "count" (count_unit only) or "plan" (windows only)
    trace: list | None = None   # when a list, every quote request the walk consults is appended (the plan)
    paper_exposed: frozenset = frozenset()   # (symbol, session) pairs with a logged paper order (holdout only)
    late_sessions: frozenset = frozenset()   # late-collected holdout sessions

    def records(self, typ_set, **match):
        for r in self.actions:
            if r.get("type") in typ_set and all(r.get(k) == v for k, v in match.items()):
                yield r


def _quotes(ctx, store, req, symbol):
    if ctx.trace is not None:
        ctx.trace.append(req)
    st = store.status(req["key"])
    if st is None:
        return "missing", None
    if st != "complete":
        return "incomplete", None
    return "ok", store.parsed(req["key"]).get(symbol, [])


def _window_req(kind, symbol, asof, w):
    return plan.quote_request(kind, symbol, asof, w[0], w[1])


def _forward(ctx, store, kind, symbol, asof, windows, x, deadline_of_last, empties=None):
    """Walk exit windows in order: ('needs', req) | ('incomplete', None) | ('fill', (ts, q)) | ('none', None).
    empties, when a list, receives every consulted window answered with no row (review round 11, C6)."""
    got = []
    for i, w in enumerate(windows):
        req = _window_req(kind, symbol, asof, w)
        st, qs = _quotes(ctx, store, req, symbol)
        if st == "missing":
            return "needs", req
        if st == "incomplete":
            return "incomplete", None
        if empties is not None and store.empty(req["key"], symbol):
            empties.append(w)
        got.extend(qs)
        got.sort(key=lambda q: q["t"])
        hit = fills.fill_at(ctx.cal, got, x, w[1])
        if hit is not None:
            return "fill", hit
    return "none", None


def _backward(ctx, store, symbol, asof, windows, after, x):
    for w in windows:
        req = _window_req("quote_backward", symbol, asof, w)
        st, qs = _quotes(ctx, store, req, symbol)
        if st == "missing":
            return "needs", req
        if st == "incomplete":
            return "incomplete", None
        hit = fills.last_eligible_bid(ctx.cal, sorted(qs, key=lambda q: q["t"]), after, x)
        if hit is not None:
            return "bid", hit
    return "none", None


def _has_entry(cal, quotes, x) -> bool:
    """Presence of an entry fill quote inside the timeout, from eligibility only (the count path)."""
    return fills.fill_at(cal, quotes, x, plan.entry_deadline(x)) is not None


def _factor(ev, e, x):
    if e == x:
        return 1.0
    return FM.share_factor(ev["raw"], ev["split"], e, x)


def _cash(cal, ev, e, x, F):
    """populations.corporate_actions (review round 14, Codex P2): the dividend cash of the ex-dates in (e, x], each
    at the close of the session immediately before it, so nothing after the exit session's ex-date moves it; None
    when that close is missing. F is booked on the shares."""
    if e == x:
        return 0.0
    if not (ev["raw"].get(x) or {}).get("c"):
        return None
    return costs.cash_term(cal, ev["raw"], ev["split"], ev["all"], e, x)


def trade(ev: dict, arm: str, ctx: Ctx, store) -> dict:
    cal, sym, t = ctx.cal, ev["symbol"], ev["t"]
    d1 = cal.offset(t, 1)
    out = {"symbol": sym, "t": t, "arm": arm, "entry_session": d1, "least_exposed": ev.get("least_exposed")}
    seg = segment_of(ctx.segs, d1) if d1 else None
    if seg is None:
        return {**out, "status": "dropped_no_segment"}
    seg_last = ctx.segs[seg][1]
    if arm in MULTI_SESSION_ARMS and embargoed(cal, ctx.stage, ctx.segs, d1, ctx.dropped_years):
        return {**out, "status": "embargoed"}
    if arm == "b_overnight" and d1 == seg_last:
        return {**out, "status": "no_entry_segment_last"}
    if ev["incomplete"]:
        return {**out, "status": "fetch_incomplete", "incomplete": ev["incomplete"]}
    x_in = plan.entry_stamp(cal, t, arm)
    bar_dv = FM.entry_bar_dv(cal, ev["minute"], d1, x_in)
    notional = costs.filled_notional(ev["med20"], bar_dv)
    if costs.is_no_fill(notional) or ev["sigma_d"] is None:
        return {**out, "status": "no_fill"}
    req_in = plan.entry_window(cal, sym, t, arm)
    st, q_in = _quotes(ctx, store, req_in, sym)
    if st == "missing":
        return {"needs": [req_in]}
    if st == "incomplete":
        return {**out, "status": "fetch_incomplete", "incomplete": ["quote_entry"]}
    if store.empty(req_in["key"], sym):
        out["entry_window_empty"] = True
    e_session, x_stamp, censored = plan.planned_exit(cal, t, arm, seg_last)
    split_hit = [r for r in ctx.records(SPLIT_TYPES, symbol=sym) if r.get("date") and d1 < r["date"] <= e_session]
    if split_hit and _factor(ev, d1, e_session) == 1.0:
        return {**out, "status": "split_record_excluded"}
    if ctx.mode == "count":
        return {**out, "status": "counted" if _has_entry(cal, q_in, x_in) else "no_entry", "notional_ok": True}
    fill_in = fills.fill_at(cal, q_in, x_in, plan.entry_deadline(x_in))
    if fill_in is None:
        return {**out, "status": "no_entry"}
    ts_in, quote_in, _ = fill_in
    out.update({"censored": censored, "planned_exit_session": e_session, "entry_fill_t": ts_in})
    windows = plan.exit_windows(cal, e_session, x_stamp)
    empties = []
    kind, hit = _forward(ctx, store, "quote_exit", sym, t, windows, x_stamp, None, empties)
    if kind == "needs":
        return {"needs": [hit]}
    # universe_and_identity.empty_responses, per item: empty exit windows (on the planned exit session) and empty
    # search windows (E+1 .. E+5), each a terminal-exit consequence (review round 11, C6)
    out["exit_windows_empty"] = sum(1 for w in empties if w[1] <= cal.close(e_session))
    out["search_windows_empty"] = len(empties) - out["exit_windows_empty"]
    if kind == "incomplete":
        return {**out, "status": "fetch_incomplete", "incomplete": ["quote_exit"]}
    search_last = cal.offset(e_session, T["search_sessions"])
    back = None
    if kind == "none":
        bw = plan.backward_windows(cal, d1, ts_in, e_session, x_stamp)
        bkind, bhit = _backward(ctx, store, sym, t, bw, ts_in, x_stamp)
        if bkind == "needs":
            return {"needs": [bhit]}
        back = (bkind, bhit)
    rename_hits = []
    if kind == "none":
        rename_hits = [r for r in ctx.records(("name_change",), old_symbol=sym)
                       if r.get("date") and d1 < r["date"] <= (search_last or r["date"]) and r.get("new_symbol")]
        for r in rename_hits[:1]:
            asof = cal.next_on_or_after(r["date"])
            rk, rhit = _forward(ctx, store, "quote_rename", r["new_symbol"], asof, windows, x_stamp, None)
            if rk == "needs":
                return {"needs": [rhit]}
            out["rename_sensitivity"] = {"new_symbol": r["new_symbol"], "status": rk,
                                         "fill_mid": fills.mid(rhit[1]) if rk == "fill" else None,
                                         "fill_session": et_date(rhit[0]) if rk == "fill" else None}
    if ctx.mode == "plan":
        return {**out, "status": "planned"}
    # ---------------------------------------------------------- booking (read mode)
    entry_mid, h_in = fills.mid(quote_in), fills.half_spread(quote_in)
    cum_in = FM.cum_dv_at(cal, ev["minute"], d1, ts_in)
    hs_in = ctx.cells[costs.cell_key(d1, ts_in, entry_mid, cum_in)]
    imp = {c: costs.impact(c, ev["sigma_d"], notional, ev["med20"]) for c in (C["impact_c"], *C["impact_c_sensitivities"])}
    out.update({"notional": notional, "entry_mid": entry_mid})

    def book(exit_price, x_session, c_out_by_mode):
        F = _factor(ev, d1, x_session)
        if F is None:
            return None
        cash = _cash(cal, ev, d1, x_session, F)
        if cash is None:
            return None
        res, parts = {}, None
        for mode, c in (("primary", C["impact_c"]), ("c0.5", 0.5), ("c2.0", 2.0), ("table_only", C["impact_c"]),
                        ("stress", C["stress_impact_c"])):
            cost_mode = mode if mode in ("table_only", "stress") else "primary"
            c_in = costs.per_side(hs_in, h_in, imp[c], cost_mode)
            c_out = c_out_by_mode(cost_mode, imp[c])
            res[mode] = costs.trade_net_return(notional, entry_mid, exit_price, F, cash, c_in, c_out, ctx.fees, x_session)
            if mode == "primary":
                parts = (notional, entry_mid, exit_price, F, cash, c_in, c_out, x_session)
        return {"nets": res, "F": F, "cash": cash, "exit_session": x_session, "primary_parts": parts}

    if kind == "fill":
        ts_out, quote_out, _ = hit
        x_session = et_date(ts_out)
        exit_mid, h_out = fills.mid(quote_out), fills.half_spread(quote_out)
        hs_out = ctx.cells[costs.cell_key(x_session, ts_out, exit_mid, FM.cum_dv_at(cal, ev["minute"], x_session, ts_out))]
        booked = book(exit_mid, x_session, lambda mode, im: costs.per_side(hs_out, h_out, im, mode))
        if booked is None:
            return {**out, "status": "undefined_factor"}
        delayed = x_session > e_session
        exit_kind = ("censored_delayed" if delayed else "censored") if censored else ("delayed" if delayed else "normal")
        res = {**out, "status": "filled", "exit": exit_kind, **booked}
    else:
        merger = [r for r in ctx.records(MERGER_TYPES, acquiree_symbol=sym)
                  if r.get("date") and d1 <= r["date"] <= (search_last or r["date"])]
        bkind, bhit = back
        last_bid = bhit if bkind == "bid" else None
        if merger:
            if bkind == "incomplete":
                return {**out, "status": "fetch_incomplete", "incomplete": ["quote_backward"]}
            if last_bid is None:
                res = {**out, "status": "filled", "exit": "censored_terminal" if censored else "terminal_zero",
                       "merger_without_bid": True, "nets": {m: costs.TERMINAL_ZERO_NET for m in
                                                             ("primary", "c0.5", "c2.0", "table_only", "stress")}}
            else:
                booked = book(last_bid[0], et_date(last_bid[1]), lambda mode, im: 0.0)
                if booked is None:
                    return {**out, "status": "undefined_factor"}
                res = {**out, "status": "filled", "exit": "censored_terminal" if censored else "terminal_merger",
                       "terminal_booking": "merger", **booked}
        else:
            res = {**out, "status": "filled", "exit": "censored_terminal" if censored else "terminal_zero",
                   "nets": {m: costs.TERMINAL_ZERO_NET for m in ("primary", "c0.5", "c2.0", "table_only", "stress")},
                   "no_merger_record": not any(ctx.records(MERGER_TYPES, acquiree_symbol=sym)),
                   "rename_record_in_window": bool(rename_hits)}
            if last_bid is not None:
                rebook = book(last_bid[0], et_date(last_bid[1]), lambda mode, im: 0.0)
                res["terminal_rebooked_at_last_bid"] = None if rebook is None else rebook["nets"]["primary"]
            elif bkind == "incomplete":
                # populations.fetch_failures: without a merger record, an incomplete backward window removes the
                # trade from the terminal-zero rebooking sensitivity only (review round 9, L-1)
                res["backward_incomplete"] = True
    res["ratio_rule_in_hold"] = _ratio_rule_in_hold(cal, ev, d1, res.get("exit_session") or e_session)
    res["paper_exposed"] = _paper_exposed(ctx, sym, t, res.get("exit_session") or search_last or e_session)
    return res


def _ratio_rule_in_hold(cal, ev, e, x) -> bool:
    d = cal.offset(e, 1)
    while d is not None and d <= x:
        if FM.suspected_at(cal, ev["raw"], ev["split"], d):
            return True
        d = cal.offset(d, 1)
    return False


def _paper_exposed(ctx, sym, t, last) -> bool:
    if ctx.stage != "holdout":
        return False
    d = t
    while d is not None and d <= last:
        if (sym, d) in ctx.paper_exposed or d in ctx.late_sessions:
            return True
        d = ctx.cal.offset(d, 1)
    return False


# ---------------------------------------------------------------- H3-c

def h3c_event(ev: dict, ctx: Ctx) -> dict:
    """The 8 official-print legs over t+1 .. t+5: overnight k = 1..4 (close t+k to open t+k+1, with F and cash),
    intraday k = 2..5 (open to close of t+k). Missing any leg excludes the event (counted)."""
    cal, t = ctx.cal, ev["t"]
    d = [cal.offset(t, k) for k in range(0, 6)]
    out = {"symbol": ev["symbol"], "t": t, "entry_session": d[1], "least_exposed": ev.get("least_exposed")}
    seg = segment_of(ctx.segs, d[1]) if d[1] else None
    if seg is None:
        return {**out, "status": "dropped_no_segment"}
    if d[5] is None or d[5] > ctx.segs[seg][1]:
        return {**out, "status": "legs_cross_segment_end"}
    if embargoed(cal, ctx.stage, ctx.segs, d[1], ctx.dropped_years):
        return {**out, "status": "embargoed"}
    if ev["incomplete"]:
        return {**out, "status": "fetch_incomplete"}
    opens = {k: FM.official_open(ev["prints"].get(d[k])) for k in range(1, 6)}
    closes = {k: FM.official_close(ev["prints"].get(d[k])) for k in range(1, 6)}
    need_open, need_close = range(2, 6), range(1, 6)
    missing = [k for k in need_open if opens[k] is None] + [k for k in need_close if closes[k] is None]
    if missing:
        later = [k for k in range(min(missing) + 1, 6) if opens.get(k) is not None or closes.get(k) is not None]
        return {**out, "status": "terminal" if not later else "missing_leg"}
    if ctx.mode == "count":
        return {**out, "status": "counted"}
    overnight, intraday = [], []
    for k in range(1, 5):
        e, x = d[k], d[k + 1]
        F = FM.share_factor(ev["raw"], ev["split"], e, x)
        cash = _cash(ctx.cal, ev, e, x, F) if F is not None else None
        if F is None or cash is None:
            return {**out, "status": "undefined_factor"}
        num = opens[k + 1] * F + cash
        if num <= 0:
            return {**out, "status": "undefined_factor"}
        overnight.append(math.log(num / closes[k]))
    for k in range(2, 6):
        intraday.append(math.log(closes[k] / opens[k]))
    # chronology.holdout.accrual_exposure: an H3-c event is paper-exposed if a session t .. t+5 is (review round 9,
    # L-2)
    return {**out, "status": "complete", "value": sum(overnight) / 4.0 - sum(intraday) / 4.0,
            "paper_exposed": _paper_exposed(ctx, ev["symbol"], t, d[5])}
