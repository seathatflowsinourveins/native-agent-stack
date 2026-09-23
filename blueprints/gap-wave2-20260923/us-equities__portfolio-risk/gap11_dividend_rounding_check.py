#!/usr/bin/env python3
"""Gap 11 fix round 4: explain credited-minus-unmodelled dividend cash. Recompute the earlier unmodelled estimate
(unrounded per-share from nautilus_portfolio.dividends) and the same estimate with per-share rounded half-even to the
cent (the DistributionModule rule); the rounded estimate must equal the native credited cash exactly."""
import json
import sys
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from nautilus_episodes import episodes_for  # noqa: E402
from nautilus_portfolio import dividends, load_bars  # noqa: E402


def main(ledger_path, run_summary_path):
    ledger = json.loads(Path(ledger_path).read_text())
    run = json.loads(Path(run_summary_path).read_text())
    frozen = common.frozen_panel()
    assets = frozen["plan"]["assets"]
    observed = [r for r in ledger if r["phase"] == "evaluation" and r["status"] == "observed"]
    first, last = min(r["entry"] for r in observed), max(r["exit"] for r in observed)
    bars = load_bars(frozen["root"], assets, first, last)
    opens = {a: {b["date"]: b["open"] for b in bars[a]} for a in assets}
    dates = [b["date"] for b in bars[assets[0]]]
    divs = dividends(frozen["root"], assets, first, last)
    out = {}
    for cand, entry in run["candidates"].items():
        if "credited_dividend_cash_usd" not in entry:
            continue
        eps = episodes_for(ledger, cand, opens)
        unrounded, rounded = Decimal(0), Decimal(0)
        for d in divs:
            ex = dates[dates.index(d["last_cum_date"]) + 1] if d["last_cum_date"] in dates[:-1] else None
            cents = d["per_share"].quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            for e in eps:
                if ex and e["entry"] < ex <= e["exit"] and d["asset"] in e["legs"]:
                    unrounded += e["legs"][d["asset"]] * d["per_share"]
                    rounded += e["legs"][d["asset"]] * cents
        credited = Decimal(entry["credited_dividend_cash_usd"])
        out[cand] = {"unrounded_estimate": str(unrounded.quantize(Decimal("0.01"))), "cent_rounded_estimate": str(rounded),
                     "native_credited": str(credited), "cent_rounded_equals_native": rounded == credited}
    print(json.dumps(out, indent=1))
    return 0 if all(v["cent_rounded_equals_native"] for v in out.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
