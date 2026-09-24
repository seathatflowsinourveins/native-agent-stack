"""Independent price audit of the extreme-gainer research package (plan.json).

Two phases, so the evidence can be reproduced and refreshed:

  fetch    reads the package's forward-returns and alias-map CSVs, requests Alpaca SIP
           auctions and daily bars (raw and split-adjusted) around every event, and writes
           the raw responses to a private snapshot (market data is not redistributed) plus
           its sha256 and a request log;
  compare  reads only the snapshot and the CSVs and writes per-event gains, differences
           and verdicts. It is deterministic: the same inputs give byte-identical output.

  python audit.py fetch   --env-file ENV --package-dir DIR --out-dir PRIVATE_DIR
  python audit.py compare --snapshot PRIVATE_DIR/snapshot.json --package-dir DIR --out results.json

Standard library only. No order, account or position endpoint is called.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / "plan.json").read_text())
DATA_URL = "https://data.alpaca.markets"
FORWARD_CSV = "datasets/forward-returns-2021-2026.csv"
ALIAS_CSV = "datasets/alias-map.csv"
HORIZONS = (1, 5, 20)


# ----------------------------------------------------------------------------- inputs

def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_inputs(package_dir: Path) -> None:
    """Refuse to run on inputs other than the ones the plan was frozen against."""
    for key, rel in (("forward_returns_csv", FORWARD_CSV), ("alias_map_csv", ALIAS_CSV)):
        want = PLAN["inputs"][key]["sha256"]
        got = sha256_file(package_dir / rel)
        if got != want:
            raise SystemExit(f"{rel}: sha256 {got} does not match the plan's {want}")


def load_events(package_dir: Path) -> list[dict]:
    rows = list(csv.DictReader((package_dir / FORWARD_CSV).open(newline="")))
    aliases = {}
    for r in csv.DictReader((package_dir / ALIAS_CSV).open(newline="")):
        if r.get("Alias_Symbol"):
            aliases[(r["Date"], r["Ticker"])] = r["Alias_Symbol"].strip()
    events = []
    for i, r in enumerate(rows):
        primary = (r.get("Ticker_Used") or r["Ticker"]).strip()
        symbols = [primary]
        alias = aliases.get((r["Date"], r["Ticker"]))
        if alias and alias not in symbols:
            symbols.append(alias)
        events.append({"id": f"{r['Date']}:{r['Ticker']}:{i}", "date": r["Date"], "ticker": r["Ticker"],
                       "symbols": symbols, "status": r["Status"], "computed_gain": num(r.get("Computed_Gain_Pct")),
                       "dataset_gain": num(r.get("Gain_Pct_Dataset")),
                       "fwd": {n: num(r.get(f"Ret_T{n}_Pct")) for n in HORIZONS}})
    return events


def num(text):
    try:
        return float(text) if text not in (None, "") else None
    except ValueError:
        return None


# ----------------------------------------------------------------------------- pure rules

def official_close(day_auction: dict | None, bar_close: float | None):
    """(price, source) for one trading day under plan.json official_close_rule."""
    if day_auction:
        closes = day_auction.get("c") or []
        prints = [c for c in closes if c.get("c") == "6"]
        if prints:
            return float(prints[0]["p"]), "closing_print"
        opens = day_auction.get("o") or []
        open_x = next((o.get("x") for o in opens if o.get("c") == "O"), None)
        official = [c for c in closes if c.get("c") == "M" and open_x and c.get("x") == open_x]
        if official:
            return float(official[0]["p"]), "official_close_listing_exchange"
    if bar_close is not None:
        return float(bar_close), "bar_close_fallback"
    return None, None


def by_date(items, key="t"):
    """Map YYYY-MM-DD to the item (daily bars carry an RFC-3339 timestamp; auctions a d field)."""
    out = {}
    for item in items or []:
        day = item.get("d") or str(item.get(key, ""))[:10]
        out[day] = item
    return out


def event_gain(event_date: str, auctions: dict, raw_bars: dict, split_bars: dict):
    """Returns a dict with gain, flags and the closes' sources, or a no-data reason."""
    event_bar = raw_bars.get(event_date)
    ev_close, ev_src = official_close(auctions.get(event_date), event_bar["c"] if event_bar else None)
    if ev_close is None:
        return {"reason": "no_source_data"}
    earlier = sorted(d for d in set(auctions) | set(raw_bars) if d < event_date)
    prev_date = prev_close = prev_src = None
    for d in reversed(earlier):
        bar = raw_bars.get(d)
        price, src = official_close(auctions.get(d), bar["c"] if bar else None)
        if price is not None:
            prev_date, prev_close, prev_src = d, price, src
            break
    if prev_close is None or prev_close <= 0:
        return {"reason": "no_prev_close"}
    out = {"prev_date": prev_date, "event_close_source": ev_src, "prev_close_source": prev_src, "split_between": False}
    f_ev, f_prev = split_factor(raw_bars.get(event_date), split_bars.get(event_date)), split_factor(raw_bars.get(prev_date), split_bars.get(prev_date))
    if f_ev and f_prev and abs(f_prev / f_ev - 1) > 1e-6:
        out["split_between"] = True
        gain = (ev_close / f_ev) / (prev_close / f_prev) - 1
    else:
        gain = ev_close / prev_close - 1
    out["gain_pct"] = round(gain * 100, 4)
    for name, bar, official in (("event", event_bar, ev_close), ("prev", raw_bars.get(prev_date), prev_close)):
        if bar and official:
            out[f"{name}_bar_vs_official_pct"] = round((bar["c"] / official - 1) * 100, 4)
    return out


def split_factor(raw_bar, split_bar):
    if raw_bar and split_bar and split_bar.get("c"):
        return raw_bar["c"] / split_bar["c"]
    return None


def forward_returns(event_date: str, split_bars: dict) -> dict:
    days = sorted(split_bars)
    if event_date not in split_bars:
        return {}
    i = days.index(event_date)
    base = split_bars[event_date]["c"]
    out = {}
    for n in HORIZONS:
        if i + n < len(days) and base:
            out[n] = {"date": days[i + n], "ret_pct": round((split_bars[days[i + n]]["c"] / base - 1) * 100, 4)}
    return out


def agrees(alpaca: float, package: float, tol: dict) -> bool:
    return abs(alpaca - package) <= max(tol["abs_pct_points"], tol["rel_fraction"] * abs(package))


def verdict_for(event: dict, result: dict) -> tuple[str, float | None, str]:
    """(verdict, package_reference, reference_field)."""
    if "reason" in result:
        return result["reason"], None, ""
    tol = PLAN["tolerance"]["event_gain"]
    if event["status"] == "OK" and event["computed_gain"] is not None:
        ref, field, prefix = event["computed_gain"], "Computed_Gain_Pct", ""
    elif event["dataset_gain"] is not None:
        ref, field, prefix = event["dataset_gain"], "Gain_Pct_Dataset", "recovered_"
    else:
        return "no_package_reference", None, ""
    return prefix + ("match" if agrees(result["gain_pct"], ref, tol) else "mismatch"), ref, field


# ----------------------------------------------------------------------------- fetch

def credentials(path: Path) -> tuple[str, str]:
    """Read the paper key pair from a 0600 env file owned by this user; values never printed."""
    info = path.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise SystemExit("credential file must be owned by this user with mode 0600")
    found = {}
    for line in path.read_text().splitlines():
        line = line.strip().removeprefix("export ")
        if "=" in line and not line.startswith("#"):
            name, value = line.split("=", 1)
            if name.strip() in ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY"):
                found[name.strip()] = value.strip().strip("'\"")
    if len(found) != 2:
        raise SystemExit("credential file lacks APCA_API_KEY_ID / APCA_API_SECRET_KEY")
    return found["APCA_API_KEY_ID"], found["APCA_API_SECRET_KEY"]


class Client:
    def __init__(self, key, secret, per_second=20.0):
        self.headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self.gap, self.last, self.log = 1.0 / per_second, 0.0, []

    def get(self, path: str, **params) -> dict:
        items, token = [], None
        while True:
            q = dict(params, **({"page_token": token} if token else {}))
            url = DATA_URL + path + "?" + urllib.parse.urlencode(q)
            for attempt in range(4):
                wait = self.last + self.gap - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                self.last = time.monotonic()
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers=self.headers), timeout=30) as r:
                        body = json.load(r)
                        self.log.append({"path": path, "params": q, "status": r.status})
                        break
                except urllib.error.HTTPError as exc:
                    self.log.append({"path": path, "params": q, "status": exc.code})
                    if exc.code == 429 and attempt < 3:
                        time.sleep(2 ** attempt)
                        continue
                    if exc.code in (400, 404, 422):
                        return {"error": exc.code}
                    raise
            key = "auctions" if path.endswith("/auctions") else "bars"
            items.extend(body.get(key) or [])
            token = body.get("next_page_token")
            if not token:
                return {key: items}


def fetch(args) -> int:
    check_inputs(args.package_dir)
    events = load_events(args.package_dir)
    client = Client(*credentials(args.env_file))
    snapshot = {"plan_sha256": sha256_file(HERE / "plan.json"), "fetched_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "feed": "sip", "events": {}}
    w = PLAN["source"]["window_calendar_days"]
    for n, ev in enumerate(events, 1):
        d = date.fromisoformat(ev["date"])
        start, end = (d - timedelta(days=w["before"])).isoformat(), (d + timedelta(days=w["after"])).isoformat()
        tried = []
        for sym in ev["symbols"]:
            base = {"start": start, "end": end, "feed": "sip", "asof": ev["date"]}
            path = f"/v2/stocks/{urllib.parse.quote(sym)}"
            # Auctions only up to the event date (official closes for the gain); bars through the
            # forward window (split-adjusted closes for T+1/T+5/T+20).
            resp = {"symbol": sym,
                    "auctions": client.get(path + "/auctions", start=start, end=ev["date"], feed="sip", asof=ev["date"]),
                    "bars_raw": client.get(path + "/bars", timeframe="1Day", adjustment="raw", **base),
                    "bars_split": client.get(path + "/bars", timeframe="1Day", adjustment="split", **base)}
            tried.append(resp)
            if ev["date"] in by_date(resp["bars_raw"].get("bars")) or ev["date"] in by_date(resp["auctions"].get("auctions")):
                break
        snapshot["events"][ev["id"]] = tried
        if n % 100 == 0:
            print(json.dumps({"progress": n, "of": len(events), "requests": len(client.log)}), flush=True)
    args.out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    snap_path = args.out_dir / "snapshot.json"
    snap_path.write_text(json.dumps(snapshot, sort_keys=True) + "\n")
    os.chmod(snap_path, 0o600)
    log = {"snapshot_sha256": sha256_file(snap_path), "requests": len(client.log),
           "status_counts": {str(s): sum(1 for e in client.log if e["status"] == s) for s in sorted({e["status"] for e in client.log})},
           "fetched_at_utc": snapshot["fetched_at_utc"]}
    (args.out_dir / "fetch-log.json").write_text(json.dumps(log, indent=2) + "\n")
    print(json.dumps(log))
    return 0


# ----------------------------------------------------------------------------- compare

def compare(args) -> int:
    check_inputs(args.package_dir)
    events = load_events(args.package_dir)
    snapshot = json.loads(args.snapshot.read_text())
    if snapshot["plan_sha256"] != sha256_file(HERE / "plan.json"):
        raise SystemExit("snapshot was fetched under a different plan.json")
    results, counts = [], {}
    fwd_counts = {n: {"match": 0, "mismatch": 0, "compared": 0} for n in HORIZONS}
    for ev in events:
        tried = snapshot["events"].get(ev["id"]) or []
        result, used = {"reason": "no_source_data"}, None
        for resp in tried:
            r = event_gain(ev["date"], by_date(resp["auctions"].get("auctions")),
                           by_date(resp["bars_raw"].get("bars")), by_date(resp["bars_split"].get("bars")))
            if "reason" not in r or r["reason"] == "no_prev_close":
                result, used = r, resp
                break
        verdict, ref, field = verdict_for(ev, result)
        counts[verdict] = counts.get(verdict, 0) + 1
        row = {"id": ev["id"], "date": ev["date"], "ticker": ev["ticker"], "symbol_used": used["symbol"] if used else None,
               "package_status": ev["status"], "package_reference_field": field, "package_gain_pct": ref,
               "alpaca_gain_pct": result.get("gain_pct"),
               "diff_pct_points": round(result["gain_pct"] - ref, 4) if ref is not None and "gain_pct" in result else None,
               "verdict": verdict}
        row.update({k: v for k, v in result.items() if k not in ("gain_pct", "reason")})
        if used and "gain_pct" in result:
            fr = forward_returns(ev["date"], by_date(used["bars_split"].get("bars")))
            row["forward"] = {}
            for n in HORIZONS:
                pkg = ev["fwd"][n]
                if n in fr and pkg is not None:
                    ok = agrees(fr[n]["ret_pct"], pkg, PLAN["tolerance"]["forward_returns"])
                    fwd_counts[n]["compared"] += 1
                    fwd_counts[n]["match" if ok else "mismatch"] += 1
                    row["forward"][f"T{n}"] = {"alpaca_pct": fr[n]["ret_pct"], "package_pct": pkg, "match": ok}
        results.append(row)
    both = counts.get("match", 0) + counts.get("mismatch", 0)
    rec = counts.get("recovered_match", 0) + counts.get("recovered_mismatch", 0)
    summary = {"events": len(events), "verdicts": dict(sorted(counts.items())),
               "mismatch_rate_where_both_have_prices": round(counts.get("mismatch", 0) / both, 4) if both else None,
               "recovered_rows": rec, "recovered_mismatch_rate": round(counts.get("recovered_mismatch", 0) / rec, 4) if rec else None,
               "split_between_rows": sum(1 for r in results if r.get("split_between")),
               "bar_close_fallback_rows": sum(1 for r in results if "bar_close_fallback" in (r.get("event_close_source"), r.get("prev_close_source"))),
               "forward_returns": {f"T{n}": fwd_counts[n] for n in HORIZONS},
               "overturn_triggered": bool(both and counts.get("mismatch", 0) / both > 0.05)}
    out = {"kind": "extreme_gainer_price_audit_results", "plan_sha256": sha256_file(HERE / "plan.json"),
           "inputs": {k: PLAN["inputs"][k]["sha256"] for k in ("forward_returns_csv", "alias_map_csv")},
           "snapshot_sha256": sha256_file(args.snapshot), "snapshot_fetched_at_utc": snapshot["fetched_at_utc"],
           "summary": summary, "events": results}
    args.out.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(summary))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--env-file", type=Path, required=True)
    f.add_argument("--package-dir", type=Path, required=True)
    f.add_argument("--out-dir", type=Path, required=True)
    c = sub.add_parser("compare")
    c.add_argument("--snapshot", type=Path, required=True)
    c.add_argument("--package-dir", type=Path, required=True)
    c.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    return fetch(a) if a.cmd == "fetch" else compare(a)


if __name__ == "__main__":
    sys.exit(main())
