"""Read one mover trial's orders back from the mover durable ledger (read-only, stdlib).

Opens ``ledger.sqlite3`` with ``mode=ro``, never talks to the broker and never reads
credentials. It selects the intents whose client id starts with ``mvr-<trial>-`` or
``rec-<trial>-``, their observed order lifecycle (``order_observed`` events) and the
trial's submit/cancel request reservations. Per symbol it reports the entry and every exit
sell, the leg's realized P&L, and, with ``--events`` (the run's ``--live-dir`` events.jsonl),
each fill's distance from the quote the engine priced the order on: the ask for a buy, the
bid for a sell, in basis points (positive = paid more than the ask or received less than the
bid). Broker order ids, the ledger path, the account fingerprint and every cash balance are
left out of the output.

    python mover_ledger_readback.py --ledger "$STATE_ROOT/<account-fingerprint>/mover/ledger.sqlite3" \
        --trial mover-mac-20260924a --events live/events.jsonl --out ledger-readback.json
"""
import argparse
import json
import sqlite3
import urllib.parse
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


def iso(ts):
    return None if ts is None else datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="milliseconds")


def bps(fill, ref, side):
    if fill is None or ref is None or Decimal(ref) == 0:
        return None
    raw = (Decimal(fill) / Decimal(ref) - 1) * Decimal(10000)
    return str((raw if side == "buy" else -raw).quantize(Decimal("0.01")))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--trial", required=True)
    parser.add_argument("--events", type=Path, default=None)
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
    prefixes = ("mvr-%s-" % args.trial, "rec-%s-" % args.trial)

    def ours(client_id):
        return client_id is not None and client_id.startswith(prefixes)

    priced_on = {}
    if args.events is not None:
        for line in args.events.read_text().splitlines():
            event = json.loads(line)
            if event.get("type") == "mover_entry_submitted":
                priced_on[event["client_id"]] = ("ask", event.get("ask"))
            elif event.get("type") == "mover_exit_submitted":
                priced_on[event["client_id"]] = ("bid", event.get("bid"))
    reserved, lifecycle = {}, defaultdict(list)
    for kind, client_id, payload in db.execute("SELECT kind, client_id, payload FROM events ORDER BY id"):
        if not ours(client_id):
            continue
        event = json.loads(payload)
        if kind == "intent_reserved":
            reserved[client_id] = event["at"]
        elif kind == "order_observed":
            lifecycle[client_id].append({"at": iso(event["at"]), "status": event["status"],
                                         "filled_qty": event["filled_qty"], "average_price": event["average_price"]})
    intents = []
    for row in db.execute("SELECT client_id, symbol, side, qty, limit_price, status, filled_qty, average_price, "
                          "submit_attempted FROM intents ORDER BY client_id"):
        client_id, symbol, side, qty, limit_price, status, filled_qty, average_price, attempted = row
        if not ours(client_id):
            continue
        quote_kind, quote = priced_on.get(client_id, (None, None))
        intents.append({"client_id": client_id, "symbol": symbol, "side": side, "qty": qty,
                        "limit_price": limit_price, "status": status, "filled_qty": filled_qty,
                        "average_price": average_price, "submit_attempted": bool(attempted),
                        "reserved_at": iso(reserved.get(client_id)),
                        "priced_on": None if quote is None else {quote_kind: quote},
                        "fill_vs_quote_bps": bps(average_price if Decimal(filled_qty or "0") > 0 else None, quote, side),
                        "observed": lifecycle[client_id]})
    legs = defaultdict(lambda: {"bought_qty": Decimal(0), "cost": Decimal(0), "sold_qty": Decimal(0),
                                "proceeds": Decimal(0), "orders": []})
    for intent in intents:
        qty = Decimal(intent["filled_qty"] or "0")
        leg = legs[intent["symbol"]]
        leg["orders"].append(intent["client_id"])
        if qty == 0:
            continue
        notional = qty * Decimal(intent["average_price"])
        if intent["side"] == "buy":
            leg["bought_qty"] += qty
            leg["cost"] += notional
        else:
            leg["sold_qty"] += qty
            leg["proceeds"] += notional
    leg_rows = []
    for symbol, leg in sorted(legs.items()):
        flat = leg["bought_qty"] == leg["sold_qty"]
        leg_rows.append({"symbol": symbol, "bought_qty": str(leg["bought_qty"]), "sold_qty": str(leg["sold_qty"]),
                         "cost_usd": str(leg["cost"]), "proceeds_usd": str(leg["proceeds"]),
                         "realized_pnl_usd": str(leg["proceeds"] - leg["cost"]) if flat else None,
                         "flat": flat, "orders": leg["orders"]})
    requests = defaultdict(list)
    for at, kind, client_id in db.execute(
            "SELECT at, kind, client_id FROM requests WHERE at >= ? AND at < ? AND kind IN ('submit', 'cancel') "
            "ORDER BY at", (start, end)):
        if client_id is None or ours(client_id):
            requests[kind].append(iso(at))
    result = {"schema_version": 1, "kind": "mover_ledger_readback", "trial_id": args.trial,
              "trial_started_at": iso(start), "intents": intents, "legs": leg_rows,
              "requests": {kind: {"count": len(times), "at": times} for kind, times in sorted(requests.items())},
              "totals": {"intents": len(intents),
                         "filled_intents": sum(1 for i in intents if i["status"] == "filled"),
                         "realized_pnl_usd": str(sum((Decimal(r["realized_pnl_usd"]) for r in leg_rows
                                                     if r["realized_pnl_usd"] is not None), Decimal(0))),
                         "all_legs_flat": all(r["flat"] for r in leg_rows)},
              "excluded": ["broker order ids", "ledger path", "account fingerprint", "cash balances"]}
    args.out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps(result["totals"]))


if __name__ == "__main__":
    main()
