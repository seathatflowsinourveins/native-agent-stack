"""Turn the incentive board into the engine's mover trial scan (protocol incentive-board-forward-v1-20260924).

  python board_scan.py --env-file ENV --board DIR/board.json --at-et 13:30 --out engine-scan.json --record selection.json

The filters are the frozen protocol's (forward-protocol-v1.json). A fresh SIP snapshot of the whole market at the
decision time supplies each candidate's price, day dollar volume, spread and last-trade age, and the pool for the
untraded controls. GET only; it never places an order.
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
import monitor as M  # noqa: E402

PROTOCOL = json.loads((HERE / "forward-protocol-v1.json").read_text())
ENGINE_PROTOCOL = "mover-early-entry-v1-20260924"


def fmt(x):
    """Decimal text with at most 9 places (the engine's scan limit)."""
    text = f"{x:.9f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def eligible(feat: dict | None, now: datetime, p: dict) -> str | None:
    """None when a snapshot row passes the protocol's price, spread, dollar-volume, gain and liveness filters."""
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


def select(board: list[dict], features: dict, now: datetime, p: dict = PROTOCOL["selection"]):
    chosen, rejected = [], {}
    for row in board:
        parts = row.get("parts") or {}
        if row.get("score", 0) < p["min_score"]:
            reason = "score"
        elif not set(parts) & set(p["required_any_component"]):
            reason = "no_non_price_component"
        elif set(parts) & set(p["excluded_components"]):
            reason = "excluded_component"
        else:
            feat = features.get(row["symbol"])
            reason = eligible(feat, now, p)  # the fresh snapshot, not the board's stage, decides the gain range
        if reason:
            rejected[row["symbol"]] = reason
        else:
            chosen.append(row)
    chosen.sort(key=lambda r: (-r["score"], -(r.get("relvol") or -1), r["symbol"]))
    return chosen[: p["max_symbols"]], rejected


def controls(features: dict, board_symbols: set, now: datetime, session: str, at_et: str, count: int, p: dict = PROTOCOL["selection"]) -> list[str]:
    pool = [s for s, f in features.items() if s not in board_symbols and eligible(f, now, p) is None]
    key = lambda s: hashlib.sha256(f"{PROTOCOL['id']}|{session}|{at_et}|{s}".encode()).hexdigest()
    return sorted(pool, key=key)[:count]


def engine_scan(chosen: list[dict], features: dict, now: datetime, at_et: str) -> dict:
    rule = PROTOCOL["execution"]["rule_template"].replace("HH:MM", at_et)
    return {"schema_version": 1, "kind": "mover_scan", "protocol": ENGINE_PROTOCOL, "rule": rule,
            "scan_time": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": PROTOCOL["id"],
            "symbols": [{"symbol": r["symbol"], "rank": i + 1, "price_at_t": fmt(features[r["symbol"]]["p"]),
                         "dollar_volume_at_t": fmt(features[r["symbol"]]["v"] * features[r["symbol"]]["p"]),
                         "entry_bar_dollar_volume": None, "gain_pct_at_t": fmt(features[r["symbol"]]["chg"] * 100)}
                        for i, r in enumerate(chosen)]}


def write_private(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(payload, f, indent=1, sort_keys=True)
        f.write("\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env-file", type=Path, required=True)
    ap.add_argument("--board", type=Path, required=True)
    ap.add_argument("--at-et", required=True, choices=PROTOCOL["decision_times_et"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--record", type=Path, required=True)
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    local = now.astimezone(M.ET)
    if local.strftime("%H:%M") < a.at_et:
        raise SystemExit("before the decision time")
    raw = a.board.read_bytes()
    board = json.loads(raw)
    age = (now - datetime.fromisoformat(board["at"])).total_seconds()
    if age > PROTOCOL["selection"]["board_max_age_seconds"]:
        raise SystemExit(f"board stale: {age:.0f} s")
    key, secret = M.credentials(a.env_file)
    http = M.Http({"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}, None)
    state = M.State()
    M.sweep_snapshots(http, M.load_universe(http), state, _NullSink(), now)
    chosen, rejected = select(board["board"], state.features, now)
    session = local.date().isoformat()
    ctrl = controls(state.features, {r["symbol"] for r in board["board"]}, now, session, a.at_et, PROTOCOL["controls"]["count"])
    scan = engine_scan(chosen, state.features, now, a.at_et)
    write_private(a.out, scan)
    write_private(a.record, {"protocol": PROTOCOL["id"], "protocol_sha256": hashlib.sha256((HERE / "forward-protocol-v1.json").read_bytes()).hexdigest(),
                             "session": session, "decision_et": a.at_et, "decided_at": now.isoformat(), "board_sha256": hashlib.sha256(raw).hexdigest(),
                             "board_age_seconds": round(age, 1), "selected": [{**r, "snapshot": state.features[r["symbol"]]} for r in chosen],
                             "rejected": rejected, "controls": [{"symbol": s, "snapshot": state.features[s]} for s in ctrl],
                             "calls": dict(http.calls)})
    print(json.dumps({"selected": [r["symbol"] for r in chosen], "rejected": len(rejected), "controls": len(ctrl)}))
    return 0 if chosen else 3


class _NullSink:
    def replace(self, name, payload):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
