"""Read one trial's orders back from the adaptive-paper durable ledger (read-only, stdlib).

Opens ``ledger.sqlite3`` with ``mode=ro`` (as metrics.py does), never talks to the
broker and never reads credentials. It selects the intents whose client id starts
with ``adp-<trial>-``, their observed order lifecycle (``order_observed`` events),
the trial's submit/cancel request reservations, and pairs filled 1-share buys and
sells per symbol in order into round trips. Broker order ids, the ledger path, the
account fingerprint and every cash balance are left out of the output.

    python ledger_readback.py --ledger "$STATE_ROOT/<account-fingerprint>/adaptive/ledger.sqlite3" \
        --trial mac-20260924a --out ledger-readback.json
"""
import argparse
import json
import sqlite3
import urllib.parse
from collections import defaultdict, deque
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


def iso(ts):
    return None if ts is None else datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="milliseconds")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--trial", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    db = sqlite3.connect("file:" + urllib.parse.quote(str(args.ledger.resolve(strict=True))) + "?mode=ro", uri=True)
    trials = sorted(db.execute("SELECT started_at, trial_id FROM trials"))
    starts = [s for s, t in trials if t == args.trial]
    if not starts:
        raise SystemExit("unknown trial")
    start = starts[0]
    later = [s for s, _ in trials if s > start]
    end = later[0] if later else float("inf")
    prefix = "adp-%s-" % args.trial
    reserved, lifecycle = {}, defaultdict(list)
    for kind, client_id, payload in db.execute(
            "SELECT kind, client_id, payload FROM events WHERE client_id LIKE ? ORDER BY id", (prefix + "%",)):
        event = json.loads(payload)
        if kind == "intent_reserved":
            reserved[client_id] = event["at"]
        elif kind == "order_observed":
            lifecycle[client_id].append({"at": iso(event["at"]), "status": event["status"],
                                         "filled_qty": event["filled_qty"], "average_price": event["average_price"]})
    intents = []
    for row in db.execute("SELECT client_id, symbol, side, qty, limit_price, status, filled_qty, average_price, "
                          "submit_attempted FROM intents WHERE client_id LIKE ? ORDER BY client_id", (prefix + "%",)):
        client_id, symbol, side, qty, limit_price, status, filled_qty, average_price, attempted = row
        intents.append({"client_id": client_id, "symbol": symbol, "side": side, "qty": qty,
                        "limit_price": limit_price, "status": status, "filled_qty": filled_qty,
                        "average_price": average_price, "submit_attempted": bool(attempted),
                        "reserved_at": iso(reserved.get(client_id)), "observed": lifecycle[client_id]})
    # Only order writes are attributed: submits carry this trial's client id, and the
    # ledger records cancels without one, so cancels are taken from this trial's window
    # (its start to the next trial's start). Reads are not attributed here: the window
    # also holds the next trial's preflight reads; paper-output.json lists the run's own.
    requests = defaultdict(list)
    for at, kind, client_id in db.execute(
            "SELECT at, kind, client_id FROM requests WHERE at >= ? AND at < ? AND kind IN ('submit', 'cancel') "
            "ORDER BY at", (start, end)):
        if client_id is None or client_id.startswith(prefix):
            requests[kind].append(iso(at))
    open_buys, round_trips = defaultdict(deque), []
    for intent in intents:
        if intent["status"] != "filled" or Decimal(intent["filled_qty"]) != 1:
            continue
        if intent["side"] == "buy":
            open_buys[intent["symbol"]].append(intent)
        elif open_buys[intent["symbol"]]:
            buy = open_buys[intent["symbol"]].popleft()
            round_trips.append({"symbol": intent["symbol"], "buy": buy["client_id"], "sell": intent["client_id"],
                                "buy_price": buy["average_price"], "sell_price": intent["average_price"],
                                "pnl_usd": str(Decimal(intent["average_price"]) - Decimal(buy["average_price"]))})
    result = {
        "kind": "adaptive_paper_ledger_readback",
        "source": "durable ledger.sqlite3 opened read-only (mode=ro); no broker request",
        "trial_id": args.trial, "trial_started_at": iso(start),
        "next_trial_started_at": None if end == float("inf") else iso(end),
        "intents": intents,
        "request_reservations": {kind: {"count": len(times), "at": times} for kind, times in sorted(requests.items())},
        "round_trips": round_trips,
        "totals": {
            "intents": len(intents),
            "by_status": {s: sum(1 for i in intents if i["status"] == s) for s in sorted({i["status"] for i in intents})},
            "filled_buys": sum(1 for i in intents if i["side"] == "buy" and i["status"] == "filled"),
            "filled_sells": sum(1 for i in intents if i["side"] == "sell" and i["status"] == "filled"),
            "round_trips": len(round_trips),
            "unpaired_filled_buys": sum(len(q) for q in open_buys.values()),
            "round_trip_pnl_usd": str(sum((Decimal(r["pnl_usd"]) for r in round_trips), Decimal("0"))),
        },
    }
    args.out.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result["totals"]))


if __name__ == "__main__":
    main()
