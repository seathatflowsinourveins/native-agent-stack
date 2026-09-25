#!/usr/bin/env python3
"""Pre-freeze receipts from pre-decision inputs only (no adjusted close, no return).

  python prefreeze.py survivorship --root ROOT --daily DAILY.parquet --out receipts/survivorship.json
  python prefreeze.py weights      --root ROOT --daily DAILY.parquet --out receipts/weights.json
  python prefreeze.py events       --root ROOT --daily DAILY.parquet --out receipts/event-counts.json

survivorship: per decision session D(t), common-like daily symbols that qualify for the main
lane (raw close and raw volume before D(t)) split by whether a current SEC CIK maps to them.
weights: per month, the capped and uncapped maximum weight and effective N of the long and
short legs (dollar-volume weights from pre-D(t) inputs; membership from filings before the
cutoff). events: firm-months by the number of known Item 2.02 events in t-12..t-1.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import eap_signal as S  # noqa: E402
import expected_dates as E  # noqa: E402


def context(a):
    con = S.duck(a.root)
    sessions = E.load_sessions(con, a.daily)
    months = E.study_months()
    decisions = [E.decision_session(sessions, t) for t in months]
    universe = json.loads((a.root / "universe.json").read_text())["ciks"]
    return con, sessions, months, decisions, universe


def rng(xs):
    xs = [x for x in xs if x is not None]
    return [min(xs), max(xs)] if xs else None


def cmd_survivorship(a) -> dict:
    con, sessions, months, decisions, universe = context(a)
    mapped = {s for v in universe.values() for s in v}
    all_syms = {r[0] for r in con.execute(f"SELECT DISTINCT symbol FROM read_parquet('{a.daily}')").fetchall()}
    lanes = S.lanes_from_inputs(S.load_lane_inputs(con, a.daily, sessions, decisions, all_syms))
    per = {}
    for d in decisions:
        main = {s for s, ln in lanes[d].items() if ln == "main"}
        with_cik, without = len(main & mapped), len(main - mapped)
        per[str(d)] = {"main_qualifying": len(main), "with_current_cik": with_cik, "without_current_cik": without,
                       "share_without": round(without / len(main), 4) if main else None}
    shares = [v["share_without"] for v in per.values()]
    return {"kind": "eap_survivorship_counts", "label": "HIST", "outcomes_computed": False,
            "inputs": "raw_c and raw_v on the 20 sessions before each D(t) plus a bar on D(t); symbol-pattern common-stock heuristic",
            "bias_sign": "unsigned: the missing names include delisted failures, acquired firms, renamed issuers, funds/ETFs and ADRs",
            "daily_symbols": len(all_syms), "decision_sessions": len(per),
            "without_current_cik_range": rng([v["without_current_cik"] for v in per.values()]),
            "share_without_range": rng(shares), "share_without_mean": round(sum(shares) / len(shares), 4),
            "per_decision_session": per}


def monthly_states(universe, events, sessions, t):
    cutoff = E.information_cutoff(sessions, t)
    return {cik: E.monthly_status(events[cik], t, cutoff) for cik in universe}


def load_events(a, universe, sessions):
    filings = E.load_filings(a.root)
    return {c: E.announcement_events(filings.get(c, []), sessions)[0] for c in universe}


def cmd_weights(a) -> dict:
    con, sessions, months, decisions, universe = context(a)
    events = load_events(a, universe, sessions)
    mapped = {s for v in universe.values() for s in v}
    inputs = S.load_lane_inputs(con, a.daily, sessions, decisions, mapped)
    per = {}
    for t, d in zip(months, decisions):
        st = monthly_states(universe, events, sessions, t)
        long, short = {}, {}
        for cik, syms in universe.items():
            if not st[cik]["eligible"]:
                continue
            for sym in syms:
                v = inputs[d].get(sym)
                if v and S.lane(sym, *v) == "main":
                    (long if st[cik]["expected"] else short)[sym] = v[1]
        row = {"n_long": len(long), "n_short": len(short)}
        for leg, raw in (("long", long), ("short", short)):
            capped, uncapped = S.capped_weights(raw), S.normalized(raw)
            row[f"{leg}_max_w_capped"] = round(max(capped.values()), 5) if capped else None
            row[f"{leg}_eff_n_capped"] = round(S.effective_n(capped), 1) if capped else None
            row[f"{leg}_max_w_uncapped"] = round(max(uncapped.values()), 5) if uncapped else None
            row[f"{leg}_eff_n_uncapped"] = round(S.effective_n(uncapped), 1) if uncapped else None
        per[f"{t[0]}-{t[1]:02d}"] = row
    summ = {k: rng([r[k] for r in per.values()]) for k in next(iter(per.values()))}
    return {"kind": "eap_weight_concentration", "label": "HIST", "outcomes_computed": False,
            "weight_rule": "prior-20 median dollar volume capped at max(2%, 1/n), renormalised", "ranges": summ, "per_month": per}


def cmd_events(a) -> dict:
    con, sessions, months, decisions, universe = context(a)
    events = load_events(a, universe, sessions)
    mapped = {s for v in universe.values() for s in v}
    inputs = S.load_lane_inputs(con, a.daily, sessions, decisions, mapped)
    dist = {"all_mapped": Counter(), "main": Counter()}
    for t, d in zip(months, decisions):
        st = monthly_states(universe, events, sessions, t)
        for cik, syms in universe.items():
            k = min(st[cik]["count"], 6)
            key = "6+" if k == 6 else str(k)
            dist["all_mapped"][key] += 1
            if any((v := inputs[d].get(s)) and S.lane(s, *v) == "main" for s in syms):
                dist["main"][key] += 1
    out = {"kind": "eap_item_202_event_counts", "label": "HIST", "outcomes_computed": False,
           "definition": "firm-months 2017-01..2026-08 by the number of known merged Item 2.02 events with effective months in t-12..t-1",
           "distribution": {k: dict(sorted(v.items())) for k, v in dist.items()}}
    for k, v in dist.items():
        ge5 = v["5"] + v["6+"]
        out[f"{k}_firm_months_ge5"] = ge5
        out[f"{k}_share_ge5"] = round(ge5 / sum(v.values()), 4)
    return out


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=("survivorship", "weights", "events"))
    p.add_argument("--root", type=Path, default=Path("~/.local/state/native-agent-stack/research/sota-mover/eap").expanduser())
    p.add_argument("--daily", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    res = {"survivorship": cmd_survivorship, "weights": cmd_weights, "events": cmd_events}[a.cmd](a)
    a.out.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k not in ("per_decision_session", "per_month")}, sort_keys=True))


if __name__ == "__main__":
    main()
