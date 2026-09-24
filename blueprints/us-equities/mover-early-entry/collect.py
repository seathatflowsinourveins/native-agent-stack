"""Collect intraday evidence for every US mover candidate day (research only; GET requests only).

Candidates are symbol-days whose fully adjusted daily-bar high reached at least +20% over the
previous adjusted close (``candidates.py`` builds the list from the broad-universe dataset). Every
early-entry rule tested at a +20% or higher threshold is therefore evaluated on all days that met
it, winners and faders alike. Days are processed one session at a time, with ``asof`` set to that
session so each symbol resolves to the entity that traded that day. For each session this writes
one gzip page set:

  bars      1-minute SIP bars 04:00-20:00 ET, raw prices (every page kept)
  auctions  official opening/closing auction prints for the session and the previous session
  news      headline timestamps and symbols from the previous 16:00 ET to the session's 20:00 ET

Every page is hashed into ledger.jsonl. The run resumes from the ledger and never re-requests a
completed session. Output stays in a private directory (SIP redistribution terms).

  python collect.py --env-file ENV --candidates candidates.csv --out PRIVATE_DIR [--max-sessions N]
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
DATA = "https://data.alpaca.markets"
BATCH = 100  # symbols per request


def credentials(path: Path):
    info = path.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise SystemExit("credential file must be owned by this user with mode 0600")
    found = {}
    for line in path.read_text().splitlines():
        line = line.strip().removeprefix("export ")
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if k.strip() in ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY"):
                found[k.strip()] = v.strip().strip("'\"")
    if len(found) != 2:
        raise SystemExit("credential file lacks the paper key pair")
    return found["APCA_API_KEY_ID"], found["APCA_API_SECRET_KEY"]


def et_iso(day: date, hh: int, mm: int = 0) -> str:
    return datetime.combine(day, dtime(hh, mm), ET).isoformat()


class Client:
    def __init__(self, key, secret, per_second):
        self.h = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self.gap, self.last, self.requests = 1.0 / per_second, 0.0, 0

    def pages(self, path, params):
        token = None
        while True:
            q = dict(params, **({"page_token": token} if token else {}))
            url = DATA + path + "?" + urllib.parse.urlencode(q)
            for attempt in range(5):
                wait = self.last + self.gap - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                self.last = time.monotonic()
                self.requests += 1
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers=self.h), timeout=60) as r:
                        raw = r.read()
                        status = r.status
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code in (429, 500, 502, 503, 504) and attempt < 4:
                        time.sleep(2 ** attempt)
                        continue
                    raw, status = exc.read() or b"{}", exc.code
                    break
            yield status, q, raw
            if status != 200:
                return
            token = json.loads(raw).get("next_page_token")
            if not token:
                return


def load_candidates(path: Path):
    by_day = defaultdict(set)
    prev = {}
    for r in csv.DictReader(path.open(newline="")):
        by_day[r["session_date"]].add(r["symbol"])
        prev[r["session_date"]] = min(prev.get(r["session_date"], r["prev_date"]), r["prev_date"])
    return by_day, prev


def done_sessions(ledger: Path):
    done = set()
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            rec = json.loads(line)
            if rec.get("event") == "session_complete":
                done.add(rec["session"])
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env-file", type=Path, required=True)
    ap.add_argument("--candidates", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--per-second", type=float, default=20.0)
    ap.add_argument("--max-sessions", type=int, default=0)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True, mode=0o700)
    ledger_path = a.out / "ledger.jsonl"
    by_day, prev = load_candidates(a.candidates)
    done = done_sessions(ledger_path)
    client = Client(*credentials(a.env_file), a.per_second)
    todo = [d for d in sorted(by_day) if d not in done]
    if a.max_sessions:
        todo = todo[: a.max_sessions]
    with ledger_path.open("a") as ledger:
        ledger.write(json.dumps({"event": "run_start", "at": datetime.now(ET).isoformat(),
                                 "candidates_sha256": hashlib.sha256(a.candidates.read_bytes()).hexdigest(),
                                 "sessions_todo": len(todo)}) + "\n")
        for n, day_s in enumerate(todo, 1):
            day = date.fromisoformat(day_s)
            syms = sorted(by_day[day_s])
            sdir = a.out / "sessions" / day_s
            sdir.mkdir(parents=True, exist_ok=True)
            specs = []
            for i in range(0, len(syms), BATCH):
                chunk = ",".join(syms[i:i + BATCH])
                specs.append(("bars", i, "/v2/stocks/bars", {"symbols": chunk, "timeframe": "1Min", "start": et_iso(day, 4),
                              "end": et_iso(day, 20), "feed": "sip", "adjustment": "raw", "asof": day_s, "limit": 10000, "sort": "asc"}))
                specs.append(("auctions", i, "/v2/stocks/auctions", {"symbols": chunk, "start": prev[day_s], "end": day_s,
                              "feed": "sip", "asof": day_s, "limit": 10000}))
                specs.append(("news", i, "/v1beta1/news", {"symbols": chunk, "start": et_iso(date.fromisoformat(prev[day_s]), 16),
                              "end": et_iso(day, 20), "limit": 50, "sort": "asc", "include_content": "false"}))
            ok = True
            for kind, i, path, params in specs:
                for page, (status, q, raw) in enumerate(client.pages(path, params)):
                    name = sdir / f"{kind}-{i:04d}-{page:04d}.json.gz"
                    with gzip.open(name, "wb", compresslevel=6) as f:
                        f.write(raw)
                    ledger.write(json.dumps({"event": "page", "session": day_s, "kind": kind, "batch": i, "page": page,
                                             "status": status, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}) + "\n")
                    if status != 200:
                        ok = False
            ledger.write(json.dumps({"event": "session_complete" if ok else "session_incomplete", "session": day_s,
                                     "symbols": len(syms), "requests_so_far": client.requests}) + "\n")
            ledger.flush()
            if n % 25 == 0:
                print(json.dumps({"sessions_done": n, "of": len(todo), "requests": client.requests}), flush=True)
    print(json.dumps({"sessions_done": len(todo), "requests": client.requests}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
