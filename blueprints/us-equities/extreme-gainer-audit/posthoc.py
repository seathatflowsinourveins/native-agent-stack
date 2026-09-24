"""Post-hoc decomposition of the price audit's mismatches (not preregistered; plan.json verdicts stand).

Reads the private snapshot, the package's forward-returns CSV and the compare results, and
writes, deterministically:

- for rows the package priced itself (Status OK, no package discrepancy flag), how many gains
  agree with the official-close gain and how many with a gain from Alpaca's split-adjusted
  daily-bar closes (last trade, extended hours included), under the plan's event-gain tolerance;
- the size of the daily-bar close vs official close gap on event and previous days;
- for each preregistered mismatch, which price leg differs from Alpaca's bar closes.

  python posthoc.py --snapshot PRIVATE/snapshot.json --package-dir PKG --results results.json --out posthoc.json
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import statistics
import sys
from pathlib import Path

import audit as A


def leg(pkg, alp):
    if pkg is None or alp is None:
        return "missing"
    return "same" if abs(pkg - alp) <= max(0.011, 0.005 * alp) else "differs"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--package-dir", type=Path, required=True)
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--supplement", type=Path, default=None)
    a = ap.parse_args(argv)
    A.check_inputs(a.package_dir)
    snap = json.loads(a.snapshot.read_text())
    results = json.loads(a.results.read_text())
    if results["snapshot_sha256"] != A.sha256_file(a.snapshot):
        raise SystemExit("results were computed from a different snapshot")
    if a.supplement:
        sup = json.loads(a.supplement.read_text())
        if results.get("supplement_sha256") != A.sha256_file(a.supplement):
            raise SystemExit("results were computed without this supplement")
        for eid, tried in sup["events"].items():
            snap["events"][eid] = list(snap["events"].get(eid) or []) + tried
    rows = list(csv.DictReader((a.package_dir / A.FORWARD_CSV).open(newline="")))
    res = {e["id"]: e for e in results["events"]}
    tol = A.PLAN["tolerance"]["event_gain"]
    basis = collections.Counter()
    gaps, legs, leg_examples = [], collections.Counter(), collections.defaultdict(list)
    for i, r in enumerate(rows):
        eid = f"{r['Date']}:{r['Ticker']}:{i}"
        e = res[eid]
        if e["verdict"] not in ("match", "mismatch"):
            continue
        resp = next(x for x in snap["events"][eid] if x["symbol"] == e["symbol_used"])
        sb = A.by_date(resp["bars_split"].get("bars"))
        for k in ("event_bar_vs_official_pct", "prev_bar_vs_official_pct"):
            if e.get(k) is not None:
                gaps.append(abs(e[k]))
        if r["Discrepancy_Flag"]:
            if e["verdict"] == "mismatch":
                legs["package_flagged"] += 1
                leg_examples["package_flagged"].append(f"{r['Date']} {r['Ticker']}: {r['Discrepancy_Flag'][:60]}")
            continue
        pkg = A.num(r["Computed_Gain_Pct"])
        if e["date"] in sb and e["prev_date"] in sb:
            bar_gain = (sb[e["date"]]["c"] / sb[e["prev_date"]]["c"] - 1) * 100
            basis[(A.agrees(e["alpaca_gain_pct"], pkg, tol), A.agrees(bar_gain, pkg, tol))] += 1
        if e["verdict"] == "mismatch":
            lp = leg(A.num(r["Prev_Close"]), sb.get(e["prev_date"], {}).get("c"))
            le = leg(A.num(r["Ev_Close"]), sb.get(e["date"], {}).get("c"))
            cat = ("split_between" if e.get("split_between") else
                   "closes_match_bar_not_official" if (lp, le) == ("same", "same") else
                   "both_closes_differ" if (lp, le) == ("differs", "differs") else
                   "prev_close_differs" if lp == "differs" else "event_close_differs" if le == "differs" else "missing_leg")
            legs[cat] += 1
            leg_examples[cat].append(f"{r['Date']} {r['Ticker']}")
    n = sum(basis.values())
    q = statistics.quantiles(gaps, n=20) if len(gaps) > 20 else []
    out = {"kind": "extreme_gainer_price_audit_posthoc", "preregistered": False,
           **({"rules": results["rules"]} if "rules" in results else {}),
           "note": ("Explains the preregistered (v1) mismatches; the plan.json verdicts and overturn stand." if results.get("rules", "v1") == "v1"
                    else "Explains the v2 (deviations.json) mismatches; the preregistered v1 verdicts and overturn stand."),
           "snapshot_sha256": results["snapshot_sha256"], "results_sha256": A.sha256_file(a.results),
           "unflagged_ok_rows_compared": n,
           "agree_official_close_gain": sum(v for (o, _), v in basis.items() if o),
           "agree_bar_close_gain": sum(v for (_, b), v in basis.items() if b),
           "agree_bar_only": basis[(False, True)], "agree_neither": basis[(False, False)],
           "bar_vs_official_abs_pct": {"days": len(gaps), "median": round(statistics.median(gaps), 4) if gaps else None,
                                       "p90": round(q[17], 4) if q else None, "p95": round(q[18], 4) if q else None,
                                       "share_over_0_5": round(sum(x > 0.5 for x in gaps) / len(gaps), 4) if gaps else None},
           "mismatch_leg_classes": dict(legs.most_common()),
           "mismatch_leg_examples": {k: v[:12] for k, v in sorted(leg_examples.items())}}
    a.out.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    import os
    os.chmod(a.out, 0o600)
    print(json.dumps({k: out[k] for k in ("unflagged_ok_rows_compared", "agree_official_close_gain", "agree_bar_close_gain",
                                          "agree_bar_only", "agree_neither", "mismatch_leg_classes")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
