#!/usr/bin/env python3
"""Reproduce equity-replay's economic_repeat_sha256 from a run's raw CSVs.

Checked in during the round-3 fix for the finding that equity-replay.json's
`repository_checks` described the wrong (reports.json-based) computation and
then, after that was corrected, claimed the CSV-based method could not be
independently re-derived ("several plausible reconstructions ... did not
reproduce"). Round 3 found the correct field selection on the first try and
checks it in here so the claim is reproducible by anyone, not just asserted.

Method (matches blueprints/us-equities/engine-nautilus/equity-replay/receipt.json's
own `independent_observations.economic_repeat_fields` /
`economic_hash_encoding`, and this receipt's `reoccurrence_verification.
economic_hash_encoding`):

  sha256(json.dumps({
      "fills": [<FIELDS subset of each fills.csv row, csv.DictReader raw
                 strings>, ...],
      "cash": [<account.csv "total" column, in file order>, ...],
      "position_pnl": [<positions.csv "realized_pnl" column, in file
                        order>, ...],
  }, sort_keys=True, separators=(",", ":")))

This is a regression check, not a repository test-suite member (this track's
brief allows writing only under evidence/artifacts/native-rollout-20260925/sim/
and docs/native-rollout-20260925-sim.md, not tests/): run it again after any
future re-run of the equity-replay backtest and it will raise if the recorded
oracle hash stops reproducing.
"""
import csv
import hashlib
import json
import sys

FIELDS = [
    "instrument_id", "side", "quantity", "filled_qty", "avg_px",
    "commissions", "status", "ts_init", "ts_last",
]

# From blueprints/us-equities/engine-nautilus/equity-replay/receipt.json
# results_per_run[].economic_repeat_sha256 (the frozen oracle, 2026-09-21).
ORACLE = {
    "baseline": "8f81042abf13c444d7148c723bd6c82d323bd2e30297d4eba358d20988505e57",
    "fee_slippage_stress": "2b97563442ef6d12235a85f09e78db960f8a10afb739777e7ab219ebc03e0a04",
}


def economic_hash(case_dir):
    with open(f"{case_dir}/fills.csv", newline="") as f:
        fills = [{k: row[k] for k in FIELDS} for row in csv.DictReader(f)]
    with open(f"{case_dir}/account.csv", newline="") as f:
        cash = [row["total"] for row in csv.DictReader(f)]
    with open(f"{case_dir}/positions.csv", newline="") as f:
        position_pnl = [row["realized_pnl"] for row in csv.DictReader(f)]
    payload = {"fills": fills, "cash": cash, "position_pnl": position_pnl}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def main(argv):
    if len(argv) < 2:
        print("usage: economic_hash_recompute.py <native_out_dir> [native_out_dir ...]",
              file=sys.stderr)
        print("  each <native_out_dir> is a launch.py --out .../native directory "
              "containing baseline/ and fee_slippage_stress/ subdirectories.",
              file=sys.stderr)
        return 2
    overall_ok = True
    for base in argv[1:]:
        for case, expected in ORACLE.items():
            got = economic_hash(f"{base}/{case}")
            ok = got == expected
            overall_ok &= ok
            print(f"{base}/{case}: computed={got} expected={expected} "
                  f"{'MATCH' if ok else 'MISMATCH'}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
