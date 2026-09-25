"""Post-freeze quote check of F1's bucketed half-spreads at actual stop exits and gap-through fills.

  python quote_check.py sample --protocol-sha256 SHA       # 1-in-10 of the checked post-publication F1 trades
  python quote_check.py fetch  --protocol-sha256 SHA --env-file ENV
  python quote_check.py apply  --protocol-sha256 SHA       # -> private quote-check.json (read by evaluate.py)

Population: post-publication F1 trades with a stop exit (including same-bar stops) or a gap-through entry.
Sample: sha256("d|symbol|dirn|protocol_sha256") first 8 bytes mod 10 == 0 (protocol quote_check). For each
checked execution the newest valid SIP quote before it is fetched: at the bar start for a gap-through fill
(the fill is the bar open), at the bar end otherwise (the fill lies inside the bar). Per sampled trade,
dR = -sum over its checked executions of (measured - bucket half-spread) x base price / R per share. The
leg's segment shift = (population size / all trades of the leg) x mean dR over the sample, added to F1's
mean net R. Every command runs the full freeze guard first. Stdlib only.
"""
from __future__ import annotations

import os as _os
import sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
if _HERE not in _sys.path:
    _sys.path.insert(0, _HERE)

import argparse  # noqa: E402
import gzip  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import threading  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402
from pathlib import Path  # noqa: E402

import collect_quotes as Q  # noqa: E402
import orb_common as C  # noqa: E402
import orb_signal as S  # noqa: E402

RATE = 10


def guard(sha):
    proto = C.require_frozen(C.PROTOCOL_PATH, sha)
    C.require_clean_tree()
    C.verify_pins(proto)
    C.check_trades("selected", sha)
    return proto


def in_check(d, symbol, dirn, sha) -> bool:
    key = f"{d}|{symbol}|{dirn}|{sha.strip().lower()}"
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") % RATE == 0


def executions(t):
    """[(kind, minute, base_price, side, at_bar_start)] of a trade's checked executions."""
    out = []
    if t["gap_entry"]:
        out.append(("entry_gap", t["entry_minute"], t["entry_base"], t["dirn"], True))
    if t["exit_reason"] in ("stop", "stop_same_bar"):
        gap = t["exit_reason"] == "stop" and abs(t["exit_base"] - t["stop"]) > 1e-12
        out.append(("stop_exit", t["exit_minute"], t["exit_base"], -t["dirn"], gap))
    return out


def trade_delta_r(execs, measured, bucket, r_ps) -> float:
    """dR for one trade: minus the extra half-spread cost (measured - bucket) of each execution, in R."""
    return -math.fsum((measured[i] - bucket[i]) * px / r_ps for i, (_, _, px, _, _) in enumerate(execs))


def segment_shift(delta_rs, population: int, total: int):
    if not delta_rs or total == 0:
        return 0.0 if population == 0 else None
    return population / total * (math.fsum(delta_rs) / len(delta_rs))


def cmd_sample(a) -> int:
    guard(a.protocol_sha256)
    import evaluate as E
    import simulate as SIM
    table = C.load_json(C.PRIVATE / "cost-table.json")
    liq = {(o[0], o[2]): o[8] for o in SIM.load_orders("selected")}
    close_of = dict(C.calendar())
    trades = [t for t in E.read_trades("selected") if t["model"] == "F1" and t["segment"] == "post_publication"]
    pop = {leg: 0 for leg in ("combined", "long")}
    total = {"combined": len(trades), "long": sum(1 for t in trades if t["dirn"] > 0)}
    picked = []
    for t in trades:
        ex = executions(t)
        if not ex:
            continue
        pop["combined"] += 1
        pop["long"] += t["dirn"] > 0
        if not in_check(t["d"], t["symbol"], t["dirn"], a.protocol_sha256):
            continue
        hs = SIM.cost_function(table, "post_publication", liq[(t["d"], t["symbol"])], close_of[t["d"]])
        picked.append({"d": t["d"], "symbol": t["symbol"], "dirn": t["dirn"], "r_ps": S.r_per_share(t["atr14"]),
                       "execs": [{"kind": k, "minute": m, "price": px, "side": sd,
                                  "ts": Q.et_epoch(t["d"], m if start else m + 1), "bucket_hs": hs(m, px)}
                                 for k, m, px, sd, start in ex]})
    out = {"protocol_sha256": a.protocol_sha256.strip().lower(), "rate": RATE, "population": pop, "total": total,
           "sampled": len(picked), "sample": picked}
    sha = C.write_private_json(C.private_dir("quote-check") / "sample.json", out)
    print(json.dumps({k: v for k, v in out.items() if k != "sample"} | {"sha256": sha}))
    return 0


def cmd_fetch(a) -> int:
    guard(a.protocol_sha256)
    qdir = C.PRIVATE / "quote-check"
    sample = json.loads((qdir / "sample.json").read_text())
    headers = Q.credentials(a.env_file)
    pages_dir = C.private_dir("quote-check", "pages")
    limiter, lock = Q.Limiter(a.per_minute), threading.Lock()
    ledger = open(qdir / "ledger.jsonl", "a")
    todo = [(f"{s['symbol']}|{s['d']}|{s['dirn']}|{e['kind']}", s["symbol"], e["ts"]) for s in sample["sample"]
            for e in s["execs"]]

    def work(item):
        k, sym, ts = item
        pages = Q.fetch_stamp(headers, limiter, sym, ts)
        name = hashlib.sha256(k.encode()).hexdigest()[:24]
        recs = []
        for i, (status, raw) in enumerate(pages):
            rec = {"event": "page", "key": k, "status": status, "sha256": hashlib.sha256(raw).hexdigest()}
            if status == 200:
                with gzip.open(pages_dir / f"{name}-{i:02d}.json.gz", "wb") as f:
                    f.write(raw)
                rec["file"] = f"{name}-{i:02d}.json.gz"
            recs.append(rec)
        ok = bool(recs) and recs[-1]["status"] == 200
        with lock:
            for r in recs + [{"event": "stamp_complete" if ok else "stamp_incomplete", "key": k, "ts": ts}]:
                ledger.write(json.dumps(r) + "\n")
            ledger.flush()

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, todo))
    print(json.dumps({"stamps": len(todo), "requests": limiter.count}))
    return 0


def cmd_apply(a) -> int:
    guard(a.protocol_sha256)
    qdir = C.PRIVATE / "quote-check"
    sample = json.loads((qdir / "sample.json").read_text())
    if sample["protocol_sha256"] != a.protocol_sha256.strip().lower():
        raise C.FreezeError("refused: quote-check sample belongs to another protocol")
    pages, status = {}, {}
    for line in (qdir / "ledger.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["event"] == "page" and r["status"] == 200:
            raw = gzip.decompress((qdir / "pages" / r["file"]).read_bytes())
            if hashlib.sha256(raw).hexdigest() != r["sha256"]:
                raise SystemExit(f"quote page hash mismatch {r['file']}")
            pages.setdefault(r["key"], []).append(raw)
        elif r["event"].startswith("stamp_"):
            status[r["key"]] = r["event"]
    deltas = {"combined": [], "long": []}
    missing = 0
    for s in sample["sample"]:
        measured, bucket = [], []
        for e in s["execs"]:
            k = f"{s['symbol']}|{s['d']}|{s['dirn']}|{e['kind']}"
            quotes = [q for raw in pages.get(k, []) for q in (json.loads(raw).get("quotes") or {}).get(s["symbol"]) or []]
            q = Q.valid_quote(quotes) if status.get(k) == "stamp_complete" else None
            if q is None:
                missing += 1
                measured.append(e["bucket_hs"])  # no quote: no shift for this execution (counted)
            else:
                measured.append((q["ap"] - q["bp"]) / (q["ap"] + q["bp"]))
            bucket.append(e["bucket_hs"])
        execs = [(e["kind"], e["minute"], e["price"], e["side"], None) for e in s["execs"]]
        d = trade_delta_r(execs, measured, bucket, s["r_ps"])
        deltas["combined"].append(d)
        if s["dirn"] > 0:
            deltas["long"].append(d)
    legs = {leg: {"sampled": len(v), "mean_delta_R": math.fsum(v) / len(v) if v else None,
                  "population": sample["population"][leg], "total": sample["total"][leg],
                  "segment_shift_R": segment_shift(v, sample["population"][leg], sample["total"][leg])}
            for leg, v in deltas.items()}
    out = {"protocol_sha256": a.protocol_sha256.strip().lower(), "label": "HIST", "legs": legs,
           "executions_without_valid_quote": missing}
    sha = C.write_private_json(C.PRIVATE / "quote-check.json", out)
    print(json.dumps(out | {"sha256": sha}, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("sample", "fetch", "apply"):
        p = sub.add_parser(name)
        p.add_argument("--protocol-sha256", default=None)
        if name == "fetch":
            p.add_argument("--env-file", type=Path, required=True)
            p.add_argument("--per-minute", type=int, default=500)
    a = ap.parse_args(argv)
    return {"sample": cmd_sample, "fetch": cmd_fetch, "apply": cmd_apply}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
