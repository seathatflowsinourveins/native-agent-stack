"""Compare a mover paper trial's fills with the study's historical fill model (protocol paper_e2e).

  python paper_compare.py --env-file ENV --scan scan.json --fills fills.json --exit X2 --out compare.json

fills.json lists, per symbol, {"symbol", "entry_price", "entry_ts", "exit_price", "exit_ts", "exit_reason", "qty"}
(epoch seconds, UTC), as extracted from the trial receipt. After the session this fetches the same SIP
1-minute bars (04:00-20:00 ET, raw, asof 2026-09-21 naming) and the session's auction prints, then applies
rules.entry_for and rules.exits_for exactly as the study does, and reports per symbol the model entry and exit,
the actual fills, and the differences in basis points. GET only; pages are kept with hashes under --pages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rules as R  # noqa: E402
from mover_scan import DATA, Fetcher, et_iso, parse_rule  # noqa: E402
from sessions_io import official_price  # noqa: E402


def bps(a, b):
    return None if (a is None or b is None) else round((a / b - 1) * 1e4, 2)


def compare(f: Fetcher, scan: dict, fills: list, exit_rule: str):
    t, _, _, _ = parse_rule(scan["rule"])
    day = scan["session"]
    syms = sorted({x["symbol"] for x in fills})
    bars = {s: [] for s in syms}
    # asof = the trade session: the tickers the scanner traded that day (a later rename or reuse cannot change them)
    for body in f.get(DATA, "/v2/stocks/bars", {"symbols": ",".join(syms), "timeframe": "1Min", "start": et_iso(day, "04:00"),
                                                 "end": et_iso(day, "20:00"), "feed": "sip", "adjustment": "raw", "asof": day,
                                                 "limit": 10000, "sort": "asc"}):
        for s, items in (body.get("bars") or {}).items():
            bars[s].extend(items)
    auctions = {}
    for body in f.get(DATA, "/v2/stocks/auctions", {"symbols": ",".join(syms), "start": day, "end": day, "feed": "sip", "asof": day, "limit": 10000}):
        for s, days in (body.get("auctions") or {}).items():
            for d in days or []:
                auctions[s] = {"o": d.get("o") or [], "c": d.get("c") or []}
    daily_close = {}
    for body in f.get(DATA, "/v2/stocks/bars", {"symbols": ",".join(syms), "timeframe": "1Day", "start": day, "end": day, "feed": "sip",
                                                 "adjustment": "raw", "asof": day, "limit": 10000}):
        for s, items in (body.get("bars") or {}).items():
            if items:
                daily_close[s] = items[-1]["c"]
    rows = []
    for x in fills:
        s = x["symbol"]
        b = R.Bars.from_rows([{"t": datetime.fromisoformat(r["t"].replace("Z", "+00:00")).timestamp(), **{k: r[k] for k in "ohlcv"},
                               "vw": r.get("vw") or r["c"]} for r in bars[s]], R.et_epoch(day, "04:00"))
        oo, _ = official_price(auctions.get(s), "o")
        oc, _ = official_price(auctions.get(s), "c")
        m_entry, m_ts, m_src, _ = R.entry_for(day, t, b, oo)
        row = {"symbol": s, "actual_entry": x.get("entry_price"), "actual_entry_ts": x.get("entry_ts"), "model_entry": m_entry,
               "model_entry_ts": m_ts, "model_entry_source": m_src, "entry_diff_bps": bps(x.get("entry_price"), m_entry),
               "actual_exit": x.get("exit_price"), "actual_exit_ts": x.get("exit_ts"), "actual_exit_reason": x.get("exit_reason")}
        if m_entry is not None:
            ex, high, halt, close_src = R.exits_for(m_entry, m_ts, b, day, oc, daily_close.get(s))  # C22 fallback order
            px, ts, fb = ex[exit_rule]
            row.update({"model_exit": px, "model_exit_ts": ts, "model_exit_close_fallback": fb, "exit_diff_bps": bps(x.get("exit_price"), px),
                        "model_gross": px / m_entry - 1,
                        "actual_gross": (x["exit_price"] / x["entry_price"] - 1) if (x.get("exit_price") and x.get("entry_price")) else None,
                        "halt_flag": halt})
        rows.append(row)
    return {"schema_version": 1, "protocol": "mover-early-entry-v1-20260924", "rule": scan["rule"], "exit": exit_rule, "session": day,
            "scan_sha256": None, "rows": rows,
            "note": "The model uses 1-minute bars (entry at the first bar open at or after t; exits per rules.exits_for); a paper fill is a quote-driven limit order, so differences mix the bar model's granularity with fill quality."}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env-file", type=Path, required=True)
    ap.add_argument("--scan", type=Path, required=True)
    ap.add_argument("--fills", type=Path, required=True)
    ap.add_argument("--exit", choices=R.EXITS, required=True)
    ap.add_argument("--pages", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    import collect
    key, secret = collect.credentials(a.env_file)
    f = Fetcher(a.pages, {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})
    scan_bytes = a.scan.read_bytes()
    out = compare(f, json.loads(scan_bytes), json.loads(a.fills.read_text()), a.exit)
    out["scan_sha256"] = hashlib.sha256(scan_bytes).hexdigest()
    out["compared_at_utc"] = datetime.now(timezone.utc).isoformat()
    a.out.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    os.chmod(a.out, 0o600)
    print(json.dumps({"rows": len(out["rows"]), "entry_diff_bps": [r.get("entry_diff_bps") for r in out["rows"]],
                      "exit_diff_bps": [r.get("exit_diff_bps") for r in out["rows"]]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
