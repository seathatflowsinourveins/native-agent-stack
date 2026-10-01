"""One stage's evaluation: terciles, trades per arm, the five items, labels and verdicts, in memory.

The caller (core.runner) writes the returned results once, atomically, after every item is computed
(run_discipline.once). Nothing here reads a file or the network.
"""
from __future__ import annotations

from collections import Counter

import numpy as np

from core import stats as ST
from core import terciles as TC
from core.params import ALTERNATIVE, BOOT, CHRONO, FETCH, ITEM_IDS, TRADABLE
from core.trades import h3c_event, trade

ARM_OF = {"H1-D": "b_lane", "H1-D-b_lane-low": "b_lane", "H3-a": "a_intraday", "H3-b": "b_overnight"}
ARMS = ("b_lane", "a_intraday", "b_overnight")
SENSITIVITY_MODES = ("c0.5", "c2.0", "table_only", "stress")
# review round 15, F08: what every result can claim (universe_and_identity.vintage_scope)
CLAIMS_SCOPE = ("retrospective reconstruction: every input is the provider's data as served at its fetch vintage, "
                "after the fact; decision-time availability and revisions between the decision and the fetch are "
                "neither enforced nor claimed (universe_and_identity.vintage_scope)")
# review round 15, F14: the units of an item's estimate, interval and MDE
MDE_UNITS = {"H1-D": "difference of mean net returns (fraction)", "H1-D-b_lane-low": "mean net return (fraction)",
             "H3-a": "mean net return (fraction)", "H3-b": "mean net return (fraction)",
             "H3-c": "difference of mean log returns (log units; x 100 = log points, not a percent return)"}
TERMINAL_KINDS = ("terminal_zero", "terminal_merger", "censored_terminal")


def arms_for(items) -> tuple:
    """The arms that the given items use (review round 9, M-1: at the holdout only the carried items' arms)."""
    return tuple(a for a in ARMS if any(ARM_OF.get(i) == a for i in items))


class Unsealed(Exception):
    pass


def void_rate(incomplete_by_kind: dict) -> dict:
    """Review round 8, R8-5: the per-stage fetch-incomplete rate over every required request, reported by kind."""
    req = sum(v["requests"] for v in incomplete_by_kind.values())
    inc = sum(v["incomplete"] for v in incomplete_by_kind.values())
    rate = inc / req if req else 0.0
    return {"requests": req, "incomplete": inc, "rate": rate, "void": rate > FETCH["void_incomplete_rate"],
            "by_kind": incomplete_by_kind}


def in_stage(ctx, ev, stage_sessions: set) -> bool:
    """Segments are assigned by entry session: an event belongs to the stage if t or its entry session t+1 is a
    kept stage session (a decision whose entry lies in no segment is then counted as dropped by trade())."""
    d1 = ctx.cal.offset(ev["t"], 1)
    return ev["t"] in stage_sessions or (d1 is not None and d1 in stage_sessions)


def assign_terciles(events: list, pool: list, members) -> dict:
    """{(symbol, t): tercile or None} for the stage's events, from trailing pool breakpoints at t."""
    by_session = {}
    for ev in events:
        if ev["max21"] is not None:
            by_session.setdefault(ev["t"], []).append(ev["max21"])
    out = {}
    for ev in events:
        if members(ev):
            out[(ev["symbol"], ev["t"])] = TC.assign(ev["max21"], TC.breakpoints(pool, by_session, ev["t"]))
    return out


def build_trades(events: list, ctx, store, stage_sessions: set, terc: dict, arms=ARMS, with_h3c: bool = True):
    trades, h3c, needs = [], [], []
    for ev in events:
        if not in_stage(ctx, ev, stage_sessions):
            continue
        for arm in arms:
            tr = trade(ev, arm, ctx, store)
            if "needs" in tr:
                needs.extend(tr["needs"])
                continue
            tr["tercile"] = terc.get((ev["symbol"], ev["t"]))
            trades.append(tr)
        if with_h3c:
            h3c.append(h3c_event(ev, ctx))
    return trades, h3c, needs


def item_trades(item: str, trades: list, h3c: list) -> list:
    if item == "H3-c":
        return [{"session": e["entry_session"], "value": e["value"], "rec": e} for e in h3c if e["status"] == "complete"]
    arm = ARM_OF[item]
    rows = [tr for tr in trades if tr["arm"] == arm and tr["status"] == "filled"]
    if item == "H1-D":
        rows = [tr for tr in rows if tr["tercile"] in ("high", "low")]
    elif item == "H1-D-b_lane-low":
        rows = [tr for tr in rows if tr["tercile"] == "low"]
    return [{"session": tr["entry_session"], "value": tr["nets"]["primary"], "group": tr.get("tercile"), "rec": tr}
            for tr in rows]


def _mean(xs):
    return float(np.mean(xs)) if len(xs) else None


def bh_diagnostics(item: str, rows: list) -> dict:
    """BH (q = 0.10) across year, entry price tier and tercile splits of one tradable cell (never gating)."""
    from pinned.rules_copy import price_tier
    splits = {}
    for r in rows:
        rec = r["rec"]
        for name, key in (("year", r["session"][:4]), ("price_tier", str(price_tier(rec["entry_mid"]))),
                          ("tercile", str(rec.get("tercile")))):
            splits.setdefault(f"{name}={key}", []).append((r["value"], r["session"]))
    pvals = {k: ST.split_p([v for v, _ in xs], [s for _, s in xs], ALTERNATIVE[item]) for k, xs in sorted(splits.items())}
    rejected = ST.benjamini_hochberg(pvals) if pvals else {}
    return {k: {"n": len(splits[k]), "sessions": len({s for _, s in splits[k]}),
                "mean": _mean([v for v, _ in splits[k]]), "p": pvals[k], "bh_rejected": rejected[k]} for k in pvals}


def statistic(item: str, rows: list, value=None):
    """The item's statistic on a subset of its rows: the high-minus-low difference of trade-level means for H1-D,
    the mean otherwise (the H3-c mean leg difference, or a cell's trade-level mean)."""
    value = value or (lambda r: r["value"])
    if item == "H1-D":
        hi = [value(r) for r in rows if r["group"] == "high"]
        lo = [value(r) for r in rows if r["group"] == "low"]
        return (_mean(hi) - _mean(lo)) if hi and lo else None
    return _mean([value(r) for r in rows])


def _rebook_undefined(r) -> bool:
    """A terminal-zero trade with an eligible last bid whose rebooking has an undefined share factor or cash term
    (terminal_rebooked_at_last_bid recorded as None). Like any undefined factor it is excluded from the
    sensitivity and counted, never booked at the primary -1 (review round 12, Codex P2)."""
    rec = r["rec"]
    return rec.get("exit") in ("terminal_zero", "censored_terminal") and "terminal_rebooked_at_last_bid" in rec \
        and rec["terminal_rebooked_at_last_bid"] is None


def _rebooked(r):
    rec = r["rec"]
    if rec.get("exit") in ("terminal_zero", "censored_terminal") and rec.get("terminal_rebooked_at_last_bid") is not None:
        return rec["terminal_rebooked_at_last_bid"]
    return r["value"]


def sensitivities(item: str, rows: list) -> dict:
    """statistics.sensitivities for one item, each the item's own statistic (review round 10, F3). Every item gets
    the least-exposed slice (exposure_registry.consequence) and the holdout without paper-exposed trades; the
    trade-based items (H1-D and the cells) also get the cost, terminal-rebooking, ratio-rule and censoring
    sensitivities. H3-c has no cost, no terminal booking and no censored leg (an event whose legs cross the segment
    end is excluded), so those do not apply to it."""
    out = {}
    if item != "H3-c":
        for m in SENSITIVITY_MODES:
            out[m] = statistic(item, rows, lambda r, m=m: r["rec"]["nets"][m])
        # a trade whose backward window is fetch-incomplete (and has no merger record) leaves this sensitivity only
        # (populations.fetch_failures; review round 9, L-1)
        out["terminal_zero_rebooked_at_last_bid"] = statistic(
            item, [r for r in rows if not r["rec"].get("backward_incomplete") and not _rebook_undefined(r)], _rebooked)
        out["terminal_zero_rebooked_undefined_factor_n"] = sum(1 for r in rows if _rebook_undefined(r))
        out["ratio_rule_holds_removed"] = statistic(item, [r for r in rows if not r["rec"].get("ratio_rule_in_hold")])
        out["censored_removed"] = statistic(item, [r for r in rows if not r["rec"].get("censored")])
    out["least_exposed_slice"] = statistic(item, [r for r in rows if r["rec"].get("least_exposed")])
    out["least_exposed_slice_n"] = sum(1 for r in rows if r["rec"].get("least_exposed"))
    out["without_paper_exposed"] = statistic(item, [r for r in rows if not r["rec"].get("paper_exposed")])
    return out


def item_result(item: str, stage: str, rows: list, sessions: list, protocol_id: str, B: int | None = None,
                fees=None) -> dict:
    alt = ALTERNATIVE[item]
    rng = ST.generator(protocol_id, stage, item)
    L = BOOT["block_sessions"][item]
    if item == "H1-D":
        hi = [r for r in rows if r["group"] == "high"]
        lo = [r for r in rows if r["group"] == "low"]
        n_hi, n_lo = len(hi), len(lo)
        est = (_mean([r["value"] for r in hi]) - _mean([r["value"] for r in lo])) if hi and lo else None
        groups = [ST.session_arrays(sessions, rows, "high"), ST.session_arrays(sessions, rows, "low")]
        n = n_hi + n_lo
        mde_v = ST.mde(item, n1=n_hi, n2=n_lo)
    else:
        n_hi = n_lo = None
        n = len(rows)
        est = _mean([r["value"] for r in rows])
        groups = [ST.session_arrays(sessions, rows)]
        mde_v = ST.mde(item, n=n)
    if not sessions or n == 0:
        boot = np.full(B or BOOT["B"], np.nan)
    else:
        boot = ST.bootstrap(sessions, groups, rng, L, B=B)
    p = ST.p_value(boot, alt)
    p_n = ST.normal_tail_p(est, boot, alt) if est is not None else 1.0
    # review round 15, F06 and F14: occupied entry sessions (per group for H1-D) and the bootstrap's validity, which
    # decides both a pass and an MDE exclusion (core.stats.inference_check); review round 16, F06: the same
    # occupied_sessions value also gates inference_check's fixed occupied-session floor
    if item == "H1-D":
        occupied = {g: len({r["session"] for r in rows if r["group"] == g}) for g in ("high", "low")}
    else:
        occupied = len({r["session"] for r in rows})
    res = {"item": item, "alternative": alt, "estimate": est, "n": n, "n_high": n_hi, "n_low": n_lo,
           "occupied_sessions": occupied, "units": MDE_UNITS[item],
           "median": float(np.median([r["value"] for r in rows])) if rows else None,
           "p": p, "p_normal_tail": p_n, "mde": mde_v,
           "mde_excluded": ST.mde_excluded(item, boot, mde_v, occupied),
           "inference": ST.inference_check(item, boot, occupied),
           "n_ok": ST.minimum_met(item, stage, n, n_hi, n_lo),
           "lineage_confirmed": ST.lineage_confirmed(p, p_n),
           # outcome_reporting.rule (review round 11, C12): the 95% percentile interval of the estimate, reported
           # with the opposite_direction flag set by evaluate(); over the draws that have a statistic
           "interval_95": [ST.bound(boot, 0.025), ST.bound(boot, 0.975)]}
    res["sensitivities"] = sensitivities(item, rows)
    if item == "H1-D":
        res["two_way_clustered"] = ST.two_way_cluster_difference(
            [r["value"] for r in rows], [r["group"] for r in rows], [r["session"] for r in rows],
            [r["rec"]["symbol"] for r in rows])
    else:
        res["two_way_clustered"] = ST.two_way_cluster([r["value"] for r in rows], [r["session"] for r in rows],
                                                      [r["rec"]["symbol"] for r in rows])
    if item in TRADABLE:
        rob = ST.robustness([{"session": r["session"], "value": r["value"]} for r in rows]) if rows else \
            {"all_positive": False}
        res["robustness"] = rob
        res["exits"] = dict(Counter(r["rec"]["exit"] for r in rows))
        res["break_even_cost_multiple"] = ST.break_even_multiple([r["rec"] for r in rows], fees) if rows and fees else None
        res["bh_diagnostics"] = bh_diagnostics(item, rows)
    if item == "H1-D":
        # terminal_exits.in_statistics: exit counts for every item; H1-D's are per group (review round 9, L-4)
        res["exits_by_group"] = {g: dict(Counter(r["rec"]["exit"] for r in rows if r["group"] == g))
                                 for g in ("high", "low")}
    res["paper_exposed_fraction"] = (sum(1 for r in rows if r["rec"].get("paper_exposed")) / len(rows)) if rows else 0.0
    return res


def opposite_direction(item: str, stage: str, estimate, validation_sign=None) -> bool:
    """outcome_reporting.rule (review round 11, C12): an estimate in the direction opposite to a one-sided
    alternative, or for H3-c at the holdout opposite to the validation sign, is reported descriptively with its
    estimate and interval_95 and supports no claim of an effect in that direction. Its label is unchanged: it never
    passes, and it may be 'not_supported_mde_excluded', because its interval then excludes the alternative's size."""
    if estimate is None or estimate == 0:
        return False
    alt = ALTERNATIVE[item]
    if alt == "greater":
        return estimate < 0
    if alt == "less":
        return estimate > 0
    return stage == "holdout" and validation_sign is not None and validation_sign != 0 and \
        np.sign(estimate) != np.sign(validation_sign)


def empty_by_item(computed: tuple, trades: list, h3c: list, events: list) -> dict:
    """universe_and_identity.empty_responses per item (review round 11, C6): over the item's trades of every status
    (H3-c: its events), the per-event requests answered with no row by kind, and the entry, exit and search quote
    windows answered with no row."""
    by_event = {(ev["symbol"], ev["t"]): ev for ev in events}
    out = {}
    for item in computed:
        if item == "H3-c":
            recs = h3c
        else:
            recs = [tr for tr in trades if tr["arm"] == ARM_OF[item]]
            if item == "H1-D":
                recs = [tr for tr in recs if tr.get("tercile") in ("high", "low")]
            elif item == "H1-D-b_lane-low":
                recs = [tr for tr in recs if tr.get("tercile") == "low"]
        row = Counter()
        for r in recs:
            ev = by_event.get((r.get("symbol"), r.get("t"))) or {}
            for k in (ev.get("data") or {}).get("empty", ()):
                row[f"event_request:{k}"] += 1
            if item != "H3-c":
                row["entry_window"] += bool(r.get("entry_window_empty"))
                row["exit_windows"] += r.get("exit_windows_empty", 0)
                row["search_windows"] += r.get("search_windows_empty", 0)
        out[item] = dict(sorted(row.items()))
    return out


def a_b_overlap(trades: list) -> dict:
    """Events whose H3-a (a_intraday) trade and b_lane trade were both filled, so they share the entry fill, out of
    the filled H3-a trades."""
    filled = {arm: {(t["symbol"], t["t"]) for t in trades if t["arm"] == arm and t.get("status") == "filled"}
              for arm in ("a_intraday", "b_lane")}
    return {"a_intraday_filled": len(filled["a_intraday"]),
            "also_b_lane_filled": len(filled["a_intraday"] & filled["b_lane"])}


def terminal_by_arm_year(trades: list) -> dict:
    """terminal_exits.booking: per arm and entry year, terminal-zero trades (with no merger record, and with a
    rename record in the window), terminal-merger trades and mergers without a bid (review round 9, L-4)."""
    out = {}
    for t in trades:
        if t.get("status") != "filled" or t.get("exit") not in TERMINAL_KINDS:
            continue
        row = out.setdefault(t["arm"], {}).setdefault(t["entry_session"][:4], Counter())
        row[t["exit"]] += 1
        for flag in ("no_merger_record", "rename_record_in_window", "merger_without_bid"):
            row[flag] += bool(t.get(flag))
    return {a: {y: dict(c) for y, c in ys.items()} for a, ys in out.items()}


def evaluate(stage: str, events: list, ctx, store, *, protocol_id: str, stage_sessions: list, pool: list,
             tested: bool = True, void: dict | None = None, carried: tuple = ITEM_IDS,
             validation_signs: dict | None = None, B: int | None = None, qualifiers: tuple = (),
             identity_limited: dict | None = None) -> dict:
    """Every item of one stage. stage_sessions: the stage's kept sessions (the bootstrap list and the decision
    sessions); pool: the tercile pool (warm-up included for development).

    At the holdout only the carried items are computed, from only the arms they use: holdout_gate.opens_only_for
    opens the read for validated items alone (review round 9, M-1). qualifiers are stage-level qualifiers
    ('transport-deviation'); identity_limited ({"rate": 2020's identity-unreached rate}), when given, labels every
    validation result identity-limited with the rate stated (chronology.labels.validation; M-8)."""
    sset = set(stage_sessions)
    computed = tuple(i for i in ITEM_IDS if stage != "holdout" or i in carried)
    arms = arms_for(computed)
    terc = assign_terciles(events, pool, lambda ev: in_stage(ctx, ev, sset))
    trades, h3c, needs = build_trades(events, ctx, store, sset, terc, arms=arms, with_h3c="H3-c" in computed)
    if needs:
        raise Unsealed(f"{len(needs)} planned requests are not sealed; no outcome is computed from unsealed data")
    counts = {"trades_by_arm_status": dict(Counter(f"{t['arm']}:{t['status']}" for t in trades)),
              "h3c_by_status": dict(Counter(e["status"] for e in h3c)),
              "terciles": dict(Counter(str(v) for v in terc.values())),
              "terminal_zero_without_merger_record": sum(1 for t in trades if t.get("no_merger_record")),
              "terminal_zero_with_rename_record": sum(1 for t in trades if t.get("rename_record_in_window")),
              "merger_without_bid": sum(1 for t in trades if t.get("merger_without_bid")),
              "terminal_by_arm_year": terminal_by_arm_year(trades),
              # terminal_exits.booking (E9): whether an eligible quote exists under the new symbol
              "rename_sensitivity": dict(Counter(f"{t['arm']}:{t['rename_sensitivity']['status']}"
                                                 for t in trades if t.get("rename_sensitivity"))),
              "backward_incomplete": sum(1 for t in trades if t.get("backward_incomplete")),
              # arms.a_intraday: H3-a's entries are the b_lane entries; the overlap is reported (review round 10, F13)
              "a_intraday_b_lane_entry_overlap": a_b_overlap(trades),
              "empty_by_item": empty_by_item(computed, trades, h3c, events)}
    is_void = bool(void and void.get("void"))
    items = {}
    for item in ITEM_IDS:
        if item not in computed:
            items[item] = {"item": item, "carried": False}
            continue
        rows = item_trades(item, trades, h3c)
        items[item] = item_result(item, stage, rows, stage_sessions, protocol_id, B=B, fees=ctx.fees)
    # descriptive H1 cells (at the holdout only when an H1 item is carried, so its b_lane trades were built)
    desc = {}
    if "b_lane" in arms:
        for terc_name in ("high", "middle"):
            vals = [t["nets"]["primary"] for t in trades if t["arm"] == "b_lane" and t["status"] == "filled"
                    and t["tercile"] == terc_name]
            desc[f"b_lane_{terc_name}"] = {"n": len(vals), "mean": _mean(vals)}
    # stage p-values
    p_raw = {i: (items[i]["p"] if (tested and not is_void and i in computed and i in carried) else 1.0)
             for i in ITEM_IDS}
    if stage == "development":
        p_stage = p_raw
    else:
        p_stage = ST.holm(p_raw, {i: items[i].get("p_normal_tail", 1.0) for i in ITEM_IDS})
    labels, stage_labels = {}, []
    if stage == "development":
        stage_labels.append("survivorship-limited")
    if stage == "validation" and identity_limited is not None:
        stage_labels.append(f"identity-limited (2020 identity-unreached rate {identity_limited.get('rate')})")
    for i in ITEM_IDS:
        r = items[i]
        if i not in computed:
            labels[i] = ST.item_label(stage, i, p_stage=1.0, n_ok=False, robust_ok=False, mde_ok=False, carried=False)
            r.update({"p_stage": 1.0, "label": labels[i], "qualifiers": []})
            continue
        sign_ok = True
        if stage == "holdout" and i == "H3-c":
            vs = (validation_signs or {}).get("H3-c")
            sign_ok = vs is not None and r["estimate"] is not None and np.sign(r["estimate"]) == np.sign(vs)
        contaminated = stage == "holdout" and r["paper_exposed_fraction"] > CHRONO["paper_exposed_max_fraction"]
        r["opposite_direction"] = opposite_direction(i, stage, r["estimate"], (validation_signs or {}).get("H3-c"))
        labels[i] = ST.item_label(stage, i, p_stage=p_stage[i], n_ok=r["n_ok"] and tested,
                                  robust_ok=bool(r.get("robustness", {}).get("all_positive", True)),
                                  mde_ok=r["mde_excluded"], void=is_void, sign_ok=sign_ok,
                                  contaminated=contaminated, carried=i in carried,
                                  opposite=r["opposite_direction"] and ALTERNATIVE[i] != "two-sided",
                                  inference_ok=r["inference"]["valid"])
        r["p_stage"] = p_stage[i]
        r["label"] = labels[i]
        r["qualifiers"] = ST.qualifiers(stage, labels[i], r["lineage_confirmed"], qualifiers)
    # multiple_testing.tie_breaks: the step-down order is reported beside the Holm-adjusted p (review round 12, F5)
    holm_order = None if stage == "development" else \
        ST.holm_order(p_raw, {i: items[i].get("p_normal_tail", 1.0) for i in ITEM_IDS})
    return {"stage": stage, "tested": tested, "void": void, "items": items, "labels": labels,
            "stage_labels": stage_labels, "claims_scope": CLAIMS_SCOPE, "holm_order": holm_order,
            "verdicts": ST.hypothesis_verdict(stage, labels, {i: items[i]["qualifiers"] for i in ITEM_IDS}),
            "profitability": ST.profitability(stage, labels, {i: items[i]["qualifiers"] for i in ITEM_IDS}),
            "descriptive": desc, "counts": counts}
