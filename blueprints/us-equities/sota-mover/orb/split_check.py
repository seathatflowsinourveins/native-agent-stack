"""Cross-check the D8 split detector against Alpaca corporate-action split records (pre-outcome).

  python split_check.py fetch --env-file ENV     # GET data.alpaca.markets/v1/corporate-actions (splits only)
  python split_check.py compare                  # flagged split windows vs recorded split ex-dates

Reads only candidates.csv.gz (the split ratio of each member symbol-day, derived from the
share-adjustment factor) and the provider's split records. No price after a decision time is read.
Every page is kept gzipped and hashed in a ledger. Stdlib only.
"""
from __future__ import annotations

import os as _os
import sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
if _HERE not in _sys.path:
    _sys.path.insert(0, _HERE)

import argparse  # noqa: E402
import csv  # noqa: E402
import gzip  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
import urllib.error  # noqa: E402
import urllib.parse  # noqa: E402
import urllib.request  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

import collect_quotes as Q  # noqa: E402
import orb_common as C  # noqa: E402

HOST = "https://data.alpaca.markets"
PATH = "/v1/corporate-actions"
START, END = "2016-12-01", "2026-08-14"
BATCH = 50
RATIO_TOLERANCE = 0.02


def member_rows():
    with gzip.open(C.PRIVATE / "candidates.csv.gz", "rt", newline="") as f:
        for r in csv.DictReader(f):
            yield r


def cmd_fetch(a) -> int:
    headers = Q.credentials(a.env_file)
    symbols = sorted(C.load_json(C.MINUTE_PLAN)["universe_a"]["union"])
    out = C.private_dir("splits")
    limiter = Q.Limiter(a.per_minute)
    ledger = open(out / "ledger.jsonl", "a")
    n = 0
    for i in range(0, len(symbols), BATCH):
        batch = symbols[i:i + BATCH]
        token = None
        for page in range(1000):
            params = {"symbols": ",".join(batch), "types": "forward_split,reverse_split", "start": START,
                      "end": END, "limit": 1000, "sort": "asc"}
            if token:
                params["page_token"] = token
            url = HOST + PATH + "?" + urllib.parse.urlencode(params)
            for attempt in range(5):
                limiter.wait()
                n += 1
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers=headers, method="GET"),
                                                timeout=60) as r:
                        raw, status = r.read(), r.status
                    break
                except urllib.error.HTTPError as exc:
                    raw, status = exc.read() or b"{}", exc.code
                    if exc.code in (429, 500, 502, 503, 504) and attempt < 4:
                        time.sleep(2 ** attempt)
                        continue
                    break
            name = f"b{i // BATCH:03d}-p{page:03d}.json.gz"
            with gzip.open(out / name, "wb", compresslevel=6) as f:
                f.write(raw)
            ledger.write(json.dumps({"file": name, "status": status, "sha256": hashlib.sha256(raw).hexdigest(),
                                     "batch": i // BATCH, "page": page,
                                     "at": datetime.now(timezone.utc).isoformat()}) + "\n")
            ledger.flush()
            if status != 200:
                raise SystemExit(f"HTTP {status} on batch {i // BATCH}")
            token = json.loads(raw).get("next_page_token")
            if not token:
                break
    print(json.dumps({"requests": n}))
    return 0


def cmd_compare(a) -> int:
    out = C.PRIVATE / "splits"
    records = {}
    statuses = {}
    for line in (out / "ledger.jsonl").read_text().splitlines():
        rec = json.loads(line)
        raw = gzip.decompress((out / rec["file"]).read_bytes())
        if hashlib.sha256(raw).hexdigest() != rec["sha256"]:
            raise SystemExit(f"page hash mismatch {rec['file']}")
        statuses[str(rec["status"])] = statuses.get(str(rec["status"]), 0) + 1
        ca = json.loads(raw).get("corporate_actions") or {}
        for kind in ("forward_splits", "reverse_splits"):
            for s in ca.get(kind) or []:
                records[(s["symbol"], s["ex_date"])] = s["new_rate"] / s["old_rate"]
    members, flagged = set(), {}
    for r in member_rows():
        members.add((r["symbol"], r["d"]))
        if float(r["split"]) != 1.0:
            flagged[(r["symbol"], r["d"])] = float(r["split"])
    confirmed = [k for k in flagged if k in records and abs(flagged[k] / records[k] - 1) <= RATIO_TOLERANCE]
    ratio_mismatch = sorted(k for k in flagged if k in records and k not in confirmed)
    unrecorded = sorted(k for k in flagged if k not in records)
    missed = sorted(k for k in records if k in members and k not in flagged)
    res = {"requests_by_status": statuses, "split_records": len(records), "flagged_windows": len(flagged),
           "confirmed": len(confirmed), "ratio_mismatch": [list(k) + [flagged[k], records[k]] for k in ratio_mismatch],
           "flagged_without_record": [list(k) + [flagged[k]] for k in unrecorded],
           "records_on_member_days_not_flagged": [list(k) + [records[k]] for k in missed],
           "label": "HIST", "ledger_sha256": C.sha256_file(out / "ledger.jsonl")}
    print(json.dumps(res, indent=1, sort_keys=True))
    C.write_private_json(C.PRIVATE / "split-check.json", res)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--env-file", type=Path, required=True)
    f.add_argument("--per-minute", type=int, default=300)
    sub.add_parser("compare")
    a = ap.parse_args(argv)
    return {"fetch": cmd_fetch, "compare": cmd_compare}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
