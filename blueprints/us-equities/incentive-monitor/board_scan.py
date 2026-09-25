"""Turn the incentive board into the engine's mover trial scan (protocol incentive-board-forward-v1-20260924).

  python board_scan.py --env-file ENV --board DATA/YYYYMMDD/board.json --at-et 13:30 --config config-forward-1330.json \
      --engine-dir ADAPTIVE_PAPER_DIR --records LEDGER_DIR --out engine-scan.json

The filters are the frozen protocol's (forward-protocol-v1.json). A fresh SIP snapshot of the whole market after
the decision time supplies each candidate's price, day dollar volume, spread and last-trade age, and the pool for
the untraded, gain-matched controls; both are limited to operating companies (SEC company tickers, less registered
funds and fund-like asset names). The ledger holds one decision record per session and decision time, created
exclusively (a decision cannot be re-rolled) with the sha256 of the code, engine, protocol, config and scan, before
the scan is written; every refusal gets its own record. Controls already used by the session's other decision are
excluded. GET only; it never places an order. SEC_USER_AGENT must hold the declared SEC contact.
Exit codes: 0 scan written, 3 nothing selected (record written, no scan), 4 refused (refusal record written).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import monitor as M  # noqa: E402

PROTOCOL_PATH = HERE / "forward-protocol-v1.json"
PROTOCOL = json.loads(PROTOCOL_PATH.read_text())
ENGINE_PROTOCOL = "mover-early-entry-v1-20260924"
SYMBOL = re.compile(PROTOCOL["selection"]["symbol_pattern"])
GAIN_BUCKETS = ((0.0, 0.03), (0.03, 0.06), (0.06, 0.10))
ENGINE_FILES = ("mover.py", "mover_runner.py", "mover_strategy.py", "safety.py", "runner.py", "native_adapter.py", "transport.py",
                "../mover-early-entry/rules.py")
CONTROLS_PER_NAME = 4


def sha(path_or_bytes) -> str:
    data = path_or_bytes if isinstance(path_or_bytes, (bytes, bytearray)) else Path(path_or_bytes).read_bytes()
    return hashlib.sha256(data).hexdigest()


def fmt(x):
    """Decimal text with at most 9 places (the engine's scan limit)."""
    text = f"{x:.9f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def eligible(symbol: str, feat: dict | None, now: datetime, p: dict) -> str | None:
    """None when a snapshot row passes the protocol's symbol, price, spread, dollar-volume, gain and liveness filters."""
    if not SYMBOL.fullmatch(symbol):
        return "symbol"
    if not feat or feat.get("chg") is None:
        return "no_snapshot"
    if feat["p"] < p["min_price_usd"]:
        return "price"
    if feat.get("spr_bps") is None or feat["spr_bps"] > p["max_spread_bps"]:
        return "spread"
    if (feat.get("v") or 0) * feat["p"] < p["min_day_dollar_volume_usd"]:
        return "dollar_volume"
    if not p["min_gain"] <= feat["chg"] < p["max_gain_exclusive"]:
        return "gain"
    traded = datetime.fromisoformat(feat["tt"].replace("Z", "+00:00")) if feat.get("tt") else None
    if traded is None or (now - traded).total_seconds() > p["max_last_trade_age_seconds"]:
        return "stale_last_trade"
    return None


def select(board: list[dict], features: dict, now: datetime, operating: set | None = None, p: dict = PROTOCOL["selection"]):
    chosen, rejected = [], {}
    for row in board:
        parts = row.get("parts") or {}
        if operating is not None and row["symbol"] not in operating:
            reason = "not_operating_company"
        elif row.get("score", 0) < p["min_score"]:
            reason = "score"
        elif not set(parts) & set(p["required_any_component"]):
            reason = "no_non_price_component"
        elif set(parts) & set(p["excluded_components"]):
            reason = "excluded_component"
        else:
            reason = eligible(row["symbol"], features.get(row["symbol"]), now, p)
        if reason:
            rejected[row["symbol"]] = reason
        else:
            chosen.append(row)
    chosen.sort(key=lambda r: (-r["score"], -(r.get("relvol") or -1), r["symbol"]))
    return chosen[: p["max_symbols"]], rejected


def gain_bucket(chg: float) -> int | None:
    return next((i for i, (lo, hi) in enumerate(GAIN_BUCKETS) if lo <= chg < hi), None)


def controls(chosen: list[dict], features: dict, excluded: set, now: datetime, session: str, at_et: str,
             operating: set | None = None, p: dict = PROTOCOL["selection"]) -> dict:
    """Per selected symbol, CONTROLS_PER_NAME operating companies from its gain bucket with no non-price incentive and
    not used by the session's other decision (``excluded``), without replacement."""
    key = lambda s: hashlib.sha256(f"{PROTOCOL['id']}|{session}|{at_et}|{s}".encode()).hexdigest()
    pool = sorted((s for s, f in features.items() if s not in excluded and (operating is None or s in operating)
                   and eligible(s, f, now, p) is None), key=key)
    used, out = set(), {}
    for row in chosen:
        bucket = gain_bucket(features[row["symbol"]]["chg"])
        picks = [s for s in pool if s not in used and gain_bucket(features[s]["chg"]) == bucket][:CONTROLS_PER_NAME]
        used.update(picks)
        out[row["symbol"]] = picks
    return out


def engine_scan(chosen: list[dict], features: dict, now: datetime, at_et: str) -> dict:
    rule = PROTOCOL["execution"]["rule_template"].replace("HH:MM", at_et)
    return {"schema_version": 1, "kind": "mover_scan", "protocol": ENGINE_PROTOCOL, "rule": rule,
            "scan_time": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": PROTOCOL["id"],
            "symbols": [{"symbol": r["symbol"], "rank": i + 1, "price_at_t": fmt(features[r["symbol"]]["p"]),
                         "dollar_volume_at_t": fmt(features[r["symbol"]]["v"] * features[r["symbol"]]["p"]),
                         "entry_bar_dollar_volume": None, "gain_pct_at_t": fmt(features[r["symbol"]]["chg"] * 100)}
                        for i, r in enumerate(chosen)]}


def timing_refusal(now: datetime, at_et: str) -> str | None:
    local = now.astimezone(M.ET)
    decision = datetime.combine(local.date(), datetime.strptime(at_et, "%H:%M").time(), M.ET)
    if local < decision:
        return "before_decision_time"
    if local > decision + timedelta(seconds=PROTOCOL["late_guard_seconds"]):
        return "after_late_guard"
    return None


def write_exclusive(path: Path, payload: dict) -> bytes:
    """Create a ledger record; an existing file is never replaced (raises FileExistsError)."""
    data = (json.dumps(payload, indent=1, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return data


def session_used(records: Path, session: str, at_et: str) -> set:
    """Symbols selected or used as controls by the session's other decision records."""
    used = set()
    for path in records.glob(f"{session}-*.json"):
        if "-refused-" in path.name or path.name == f"{session}-{at_et.replace(':', '')}.json":
            continue
        rec = json.loads(path.read_text())
        used |= {r["symbol"] for r in rec.get("selected", [])}
        used |= {c["symbol"] for picks in (rec.get("controls") or {}).values() for c in picks}
    return used


class _NullSink:
    def replace(self, name, payload):
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env-file", type=Path, required=True)
    ap.add_argument("--board", type=Path, required=True)
    ap.add_argument("--at-et", required=True, choices=PROTOCOL["decision_times_et"])
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--engine-dir", type=Path, required=True)
    ap.add_argument("--records", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    local = now.astimezone(M.ET)
    session, stamp = local.date().isoformat(), a.at_et.replace(":", "")
    decision_path = a.records / f"{session}-{stamp}.json"
    if a.out.exists():
        a.out.unlink()  # never leave an earlier decision's scan where the engine could pick it up
    record = {"protocol": PROTOCOL["id"], "session": session, "decision_et": a.at_et, "decided_at": now.isoformat()}

    def file_sha(path):
        try:
            return sha(path)
        except OSError:
            return None
    record["hashes"] = {"protocol": sha(PROTOCOL_PATH), "board_scan.py": sha(HERE / "board_scan.py"), "monitor.py": sha(HERE / "monitor.py"),
                        "config": file_sha(a.config), "engine": {f: file_sha(a.engine_dir / f) for f in ENGINE_FILES}}

    def refuse(reason, **extra):
        path = a.records / f"{session}-{stamp}-refused-{datetime.now(timezone.utc).strftime('%H%M%S%f')}.json"
        write_exclusive(path, {**record, "status": "refused", "reason": reason, **extra})
        print(json.dumps({"refused": reason}))
        return 4

    if (reason := timing_refusal(now, a.at_et)):
        return refuse(reason)
    if decision_path.exists():
        return refuse("decision_already_recorded")
    pinned = PROTOCOL["execution"]["configs"][a.at_et]["sha256"]
    if record["hashes"]["config"] != pinned:
        return refuse("config_not_pinned", pinned=pinned)
    if any(v is None for v in record["hashes"]["engine"].values()):
        return refuse("engine_files_missing")
    try:
        raw = a.board.read_bytes()
        board = json.loads(raw)
        age = (now - datetime.fromisoformat(board["at"])).total_seconds()
        rows = board["board"]
    except Exception as exc:  # unreadable, naive timestamp, wrong shape
        return refuse("board_unreadable", error=type(exc).__name__)
    record.update({"board_sha256": sha(raw), "board_age_seconds": round(age, 1), "monitor": board.get("monitor")})
    if age > PROTOCOL["selection"]["board_max_age_seconds"]:
        return refuse("board_stale")
    if (board.get("monitor") or {}).get("code_sha256") != record["hashes"]["monitor.py"]:
        return refuse("monitor_code_mismatch")  # the board must come from the monitor code this record binds
    try:
        key, secret = M.credentials(a.env_file)
        http = M.Http({"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}, M.sec_identity())
        names = M.retry(lambda: M.load_assets(http), attempts=2)
        company = {t for tickers in M.retry(lambda: M.load_cik_tickers(http), attempts=2).values() for t in tickers}
        operating = M.operating_symbols(names, company, M.retry(lambda: M.load_fund_tickers(http), attempts=2))
        state = M.State()
        snapshot_started = datetime.now(timezone.utc)
        M.sweep_snapshots(http, sorted(names), state, _NullSink(), snapshot_started)
        snapshot_completed = datetime.now(timezone.utc)
    except BaseException as exc:  # SystemExit from the credential reader included: every failure leaves a record
        return refuse("snapshot_failed", error=f"{type(exc).__name__}: {str(exc)[:160]}")
    if (reason := timing_refusal(snapshot_completed, a.at_et)):
        return refuse(reason + "_after_snapshot")
    try:
        chosen, rejected = select(rows, state.features, snapshot_completed, operating)
        excluded = set(board.get("incentive_symbols") or []) | {r["symbol"] for r in rows} | session_used(a.records, session, a.at_et)
        matched = controls(chosen, state.features, excluded, snapshot_completed, session, a.at_et, operating)
        scan = engine_scan(chosen, state.features, snapshot_completed, a.at_et) if chosen else None
        scan_bytes = (json.dumps(scan, indent=1, sort_keys=True) + "\n").encode() if scan else None
        record.update({"status": "selected" if chosen else "nothing_selected", "snapshot_started_at": snapshot_started.isoformat(),
                       "snapshot_completed_at": snapshot_completed.isoformat(), "scan_sha256": sha(scan_bytes) if scan_bytes else None,
                       "operating_companies": len(operating), "selected": [{**r, "snapshot": state.features[r["symbol"]]} for r in chosen],
                       "rejected": rejected, "control_pool_excluded": len(excluded),
                       "controls": {s: [{"symbol": c, "snapshot": state.features[c]} for c in picks] for s, picks in matched.items()},
                       "calls": dict(http.calls)})
        write_exclusive(decision_path, record)  # bound before the scan exists
    except FileExistsError:
        return refuse("decision_already_recorded")
    except Exception as exc:
        return refuse("internal_error", error=f"{type(exc).__name__}: {str(exc)[:160]}")
    if scan_bytes:
        a.out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(a.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(scan_bytes)
    print(json.dumps({"selected": [r["symbol"] for r in chosen], "rejected": len(rejected), "controls": sum(map(len, matched.values()))}))
    return 0 if chosen else 3


if __name__ == "__main__":
    raise SystemExit(main())
