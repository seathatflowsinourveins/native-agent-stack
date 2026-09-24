"""Condense an evaluate.py results file into the public evidence summary (aggregates only).

  python summarize.py RESULTS.json OUT.json

Keeps, per rule-exit and split, trades, net and gross means, p, lower bound, the robustness means and
the break-even multiple; the selection record; gates; replication; the capture recall of the loosest
rule per time and tier; and the paper candidate's portfolio by rung. The full results file's sha256 is
recorded so the summary can be checked against a reproduction.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

KEEP = ("trades", "mean", "gross_mean", "median", "p", "lower_bound", "winsorised_mean", "mean_without_top5_sessions",
        "mean_of_session_means", "win_rate", "mean_stress", "mean_ibkr", "break_even_cost_multiple", "p_two_way_cluster",
        "without_premarket_supplement_rows", "without_fallback_rows", "placebo_t_plus_30", "excess_vs_iwm_open_to_close_proxy")


def main(argv=None) -> int:
    src, dst = map(Path, (argv or sys.argv[1:]))
    raw = src.read_bytes()
    d = json.loads(raw)
    out = {"schema_version": 1, "protocol": d["protocol"], "stage": d["stage"], "results_sha256": hashlib.sha256(raw).hexdigest(),
           "inputs": d["inputs"], "selection": d["selection"], "paper_candidate": d["paper_candidate"]}
    for k in ("coverage", "completeness", "regime_factor_share_1", "entries_fired_loosest", "replication_wave_h"):
        if k in d:
            out[k] = d[k]
    for split in ("development", "validation"):
        if split in d:
            out[split] = {r: {k: m.get(k) for k in KEEP if k in m} for r, m in sorted(d[split].items())}
    if "capture" in d:
        cap = d["capture"]["development_and_validation"]
        out["capture_loosest_rule_dev_and_val"] = {r: cells for r, cells in sorted(cap.items()) if "|G0.20|V250000|any" in r}
    cand = d["paper_candidate"]["rule_exit"]
    if "development" in d and cand in d["development"]:
        out["paper_candidate_portfolio"] = {s: d[s][cand].get("portfolio") for s in ("development", "validation") if s in d}
    dst.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"out": str(dst), "bytes": dst.stat().st_size, "results_sha256": out["results_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
