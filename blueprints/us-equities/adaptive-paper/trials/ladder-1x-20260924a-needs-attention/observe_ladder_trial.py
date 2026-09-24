"""Independent broker-side readback of one adaptive paper trial via alpaca-py.

Separate from the engine transport and ledger: lists the trial's orders by client-id
prefix, the broker's own FILL activities for those orders, positions and open orders.
Reads credentials from --env-file without printing them; prints no account id, order id
or activity id. Read-only: GET requests only. Any failure prints only a fixed error
code and the exception class name to stderr (never a path, a value or a traceback) and
exits 2.

    python observe_ladder_trial.py --env-file PAPER_ENV --prefix adp-<trial>- --after ISO8601
"""
import argparse
import collections
import json
import sys
from datetime import datetime


def load_keys(path):
    names = ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY")
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


def observe(args):
    import alpaca
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    key_id, key_value = load_keys(args.env_file)
    client = TradingClient(key_id, key_value, paper=True)
    del key_id, key_value

    after = datetime.fromisoformat(args.after)
    orders = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, after=after, limit=500, direction="asc"))
    mine = [o for o in orders if str(o.client_order_id).startswith(args.prefix)]
    suffix_of = {str(o.id): str(o.client_order_id)[len(args.prefix):] for o in mine}

    activities = client.get("/account/activities/FILL", {"after": after.isoformat(), "direction": "asc", "page_size": 100})
    fills = []
    for act in activities or []:
        suffix = suffix_of.get(str(act.get("order_id")))
        if suffix is None:
            continue
        fills.append({"order": suffix, "symbol": act.get("symbol"), "side": act.get("side"), "qty": act.get("qty"),
                      "price": act.get("price"), "cum_qty": act.get("cum_qty"), "leaves_qty": act.get("leaves_qty"),
                      "type": act.get("type"), "transaction_time": act.get("transaction_time")})

    return {
        "method": "alpaca-py TradingClient.get_orders(status=all, after) filtered by client-id prefix; "
                  "GET /v2/account/activities/FILL (after) joined to those orders; get_all_positions; open orders",
        "alpaca_py_version": alpaca.__version__,
        "python": sys.version.split()[0],
        "observed_at": datetime.now().astimezone().isoformat(),
        "prefix": args.prefix,
        "listing_after": args.after,
        "orders_listed_since_after": len(orders),
        "orders_with_prefix": len(mine),
        "orders": [{"order": str(o.client_order_id)[len(args.prefix):], "symbol": o.symbol, "side": str(o.side.value),
                    "qty": str(o.qty), "limit_price": str(o.limit_price), "status": str(o.status.value),
                    "filled_qty": str(o.filled_qty), "filled_avg_price": str(o.filled_avg_price)} for o in mine],
        "fill_activities": fills,
        "status_counts": dict(collections.Counter(str(o.status.value) for o in mine)),
        "positions_now": len(client.get_all_positions()),
        "open_orders_now": len(client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--after", required=True, help="ISO-8601 time before the trial's first order")
    args = parser.parse_args(argv)
    try:
        out = observe(args)
    except OSError as error:
        print(f"observe_failed: credential_file_unreadable ({type(error).__name__})", file=sys.stderr)
        return 2
    except Exception as error:  # noqa: BLE001 - report the class only, never the message
        print(f"observe_failed: {type(error).__name__}", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
