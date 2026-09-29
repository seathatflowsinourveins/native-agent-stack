"""Read-only broker reconciliation of the ext-20260928 extended-hours mover paper series.

Method adapted from ../ladder-1x-20260924a-needs-attention/observe_ladder_trial.py (alpaca-py TradingClient, the
same credential loading and class-only error reporting), with an explicit [after, until) window, page_token
pagination of FILL activities, and an in-memory join to the engine's mover ledger (sqlite, mode=ro). The ledger is
read first, so a wrong --ledger fails before any broker request. Pass --env-file and --ledger through shell
variables: the credential store and the ledger path (which contains the account-fingerprint directory) then never
appear on a recorded command line. GET requests only, paper endpoint only. Prints derived values only: no
credential, account id, order id, activity id or execution id. Any failure prints a fixed code plus the exception
class name to stderr and exits 2.

    python -B reconcile_ext_series.py --env-file "$PAPER_ENV_FILE_2" --ledger "$MOVER_LEDGER" \
        --prefix mvr-ext-20260928- --after 2026-09-28T20:00:00+00:00 --until 2026-09-29T00:30:00+00:00
"""
import argparse
import collections
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

PAGE_SIZE = 100
ORDER_LIMIT = 500
PAPER_HOST = "paper-api.alpaca.markets"


class Refused(Exception):
    pass


def load_env(path):
    names = ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "APCA_API_BASE_URL")
    found = {}
    with open(path, encoding="ascii") as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                name, value = line.split("=", 1)
                name = name.removeprefix("export ").strip()
                if name in names:
                    found[name] = value.strip().strip('"')
    return tuple(found.get(n, "") for n in names)


def text(value):
    return None if value is None else str(getattr(value, "value", value))


def dec(value):
    return None if value in (None, "") else D(str(value))


def ledger_rows(path, prefix):
    if not os.path.isfile(path):
        raise Refused("ledger_missing")
    con = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        intents = {r[0]: {"symbol": r[1], "side": r[2], "qty": D(r[3]), "limit_price": D(r[4]), "status": r[5],
                          "filled_qty": D(r[6]), "average_price": dec(r[7]), "broker_id": r[8]}
                   for r in con.execute("select client_id, symbol, side, qty, limit_price, status, filled_qty, "
                                        "average_price, broker_id from intents where client_id like ?",
                                        (prefix + "%",))}
        execs = collections.defaultdict(list)
        for r in con.execute("select client_id, cum_qty, qty, price, execution_id, at from executions "
                             "where client_id like ? order by at", (prefix + "%",)):
            execs[r[0]].append({"cum_qty": D(r[1]), "qty": D(r[2]), "price": D(r[3]), "execution_id": r[4],
                                "at": r[5]})
        positions = [(s, D(q)) for s, q in con.execute("select symbol, qty from positions")]
    finally:
        con.close()
    return intents, execs, positions


def observe(args):
    intents, execs, ledger_positions = ledger_rows(args.ledger, args.prefix)

    import alpaca
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    key_id, key_value, base_url = load_env(args.env_file)
    if not key_id or not key_value:
        raise Refused("credential_names_missing")
    if base_url and PAPER_HOST not in base_url:
        raise Refused("non_paper_endpoint")
    client = TradingClient(key_id, key_value, paper=True)
    del key_id, key_value, base_url

    after, until = datetime.fromisoformat(args.after), datetime.fromisoformat(args.until)
    orders = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, after=after, until=until,
                                                limit=ORDER_LIMIT, direction="asc"))
    if len(orders) >= ORDER_LIMIT:
        raise Refused("order_listing_may_be_truncated")
    mine = [o for o in orders if str(o.client_order_id).startswith(args.prefix)]
    coid_of = {str(o.id): str(o.client_order_id) for o in mine}

    activities, pages, token = [], 0, None
    while True:
        params = {"activity_types": "FILL", "after": after.isoformat(), "until": until.isoformat(),
                  "direction": "asc", "page_size": PAGE_SIZE}
        if token:
            params["page_token"] = token
        page = client.get("/account/activities", params) or []
        pages += 1
        activities.extend(page)
        if len(page) < PAGE_SIZE:
            break
        token = page[-1]["id"]
        if pages > 50:
            raise Refused("activity_pagination_runaway")

    by_coid, foreign_activities = collections.defaultdict(list), 0
    for act in activities:
        coid = coid_of.get(str(act.get("order_id")))
        if coid is None:
            foreign_activities += 1
            continue
        by_coid[coid].append(act)

    broker_ids = {str(o.id) for o in mine}

    rows, unconfirmed, matched_total, matched_exec_id, max_skew = [], [], 0, 0, 0.0
    trial_pnl = collections.defaultdict(D)
    for o in mine:
        coid = str(o.client_order_id)
        suffix = coid[len(args.prefix):]
        trial = suffix.split("-")[0]
        acts = sorted(by_coid.get(coid, []), key=lambda a: D(str(a["cum_qty"])))
        led = intents.get(coid)
        lex = execs.get(coid, [])
        act_keys = collections.Counter((D(str(a["cum_qty"])), D(str(a["qty"])), D(str(a["price"]))) for a in acts)
        act_uuid = {str(a["id"]).split("::")[-1] for a in acts}
        act_time = {(D(str(a["cum_qty"]))): datetime.fromisoformat(str(a["transaction_time"]).replace("Z", "+00:00"))
                    for a in acts}
        matched = 0
        for e in lex:
            key = (e["cum_qty"], e["qty"], e["price"])
            if act_keys.get(key, 0) > 0:
                act_keys[key] -= 1
                matched += 1
                if e["execution_id"] in act_uuid:
                    matched_exec_id += 1
                t = act_time.get(e["cum_qty"])
                if t is not None and e["at"] is not None:
                    max_skew = max(max_skew, abs(t.timestamp() - e["at"]))
            else:
                unconfirmed.append({"order": suffix, "cum_qty": str(e["cum_qty"]), "qty": str(e["qty"]),
                                    "price": str(e["price"])})
        matched_total += matched
        for a in acts:
            value = D(str(a["qty"])) * D(str(a["price"]))
            trial_pnl[trial] += value if str(a["side"]) == "sell" else -value
        rows.append({
            "order": suffix, "symbol": o.symbol, "side": text(o.side), "type": text(o.order_type),
            "time_in_force": text(o.time_in_force), "extended_hours": o.extended_hours,
            "qty": text(o.qty), "limit_price": text(o.limit_price), "broker_status": text(o.status),
            "filled_qty": text(o.filled_qty), "filled_avg_price": text(o.filled_avg_price),
            "submitted_at": o.submitted_at.astimezone(timezone.utc).isoformat() if o.submitted_at else None,
            "filled_at": o.filled_at.astimezone(timezone.utc).isoformat() if o.filled_at else None,
            "broker_fill_activities": len(acts),
            "broker_activity_qty_sum": str(sum((D(str(a["qty"])) for a in acts), D(0))),
            "activity_types": dict(collections.Counter(str(a.get("type")) for a in acts)),
            "ledger_status": led["status"] if led else None,
            "ledger_executions": len(lex),
            "ledger_executions_matched": matched,
            "ledger_broker_id_equals_order": (led is not None and led["broker_id"] == str(o.id)),
            "agree": bool(led) and led["symbol"] == o.symbol and led["side"] == text(o.side)
                     and led["qty"] == dec(o.qty) and led["limit_price"] == dec(o.limit_price)
                     and led["status"] == text(o.status) and led["filled_qty"] == dec(o.filled_qty)
                     and led["average_price"] == dec(o.filled_avg_price) and matched == len(lex) == len(acts),
        })

    ledger_only = sorted(c[len(args.prefix):] for c in intents if c not in {str(o.client_order_id) for o in mine})
    ledger_broker_ids_outside = sum(1 for i in intents.values() if i["broker_id"] and i["broker_id"] not in broker_ids)
    positions = client.get_all_positions()
    open_orders = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))
    return {
        "method": "alpaca-py TradingClient.get_orders(status=all, after, until, limit=500, asc); GET "
                  "/v2/account/activities?activity_types=FILL (after, until, asc, page_size=100, page_token); "
                  "get_all_positions; get_orders(status=open); joined in memory to the engine mover ledger "
                  "(sqlite mode=ro) on client order id and (cum_qty, qty, price)",
        "alpaca_py_version": alpaca.__version__,
        "python": sys.version.split()[0],
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": "paper",
        "prefix": args.prefix,
        "window": {"after": args.after, "until": args.until},
        "orders_listed_in_window": len(orders),
        "orders_with_prefix": len(mine),
        "orders_without_prefix_in_window": len(orders) - len(mine),
        "fill_activity_pages": pages,
        "fill_activities_in_window": len(activities),
        "fill_activities_without_prefix_order": foreign_activities,
        "ledger_intents_with_prefix": len(intents),
        "ledger_executions_with_prefix": sum(len(v) for v in execs.values()),
        "ledger_intents_not_listed_by_broker": ledger_only,
        "ledger_broker_ids_not_in_listing": ledger_broker_ids_outside,
        "executions_matched_on_cum_qty_qty_price": matched_total,
        "executions_matched_on_execution_id_too": matched_exec_id,
        "max_ledger_vs_activity_time_skew_seconds": round(max_skew, 3),
        "unconfirmed_executions": unconfirmed,
        "orders": rows,
        "status_counts": dict(collections.Counter(r["broker_status"] for r in rows)),
        "broker_recomputed_realized_pnl_usd_by_trial": {k: str(v) for k, v in sorted(trial_pnl.items())},
        "broker_recomputed_realized_pnl_usd_total": str(sum(trial_pnl.values(), D(0))),
        "positions_now": len(positions),
        "position_symbols_now": sorted(p.symbol for p in positions),
        "open_orders_now": len(open_orders),
        "ledger_positions_nonzero": [s for s, q in ledger_positions if q != 0],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--until", required=True)
    args = parser.parse_args(argv)
    try:
        out = observe(args)
    except Refused as error:
        print(f"reconcile_failed: {error.args[0]}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"reconcile_failed: file_unreadable ({type(error).__name__})", file=sys.stderr)
        return 2
    except Exception as error:  # noqa: BLE001 - report the class only, never the message
        print(f"reconcile_failed: {type(error).__name__}", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
