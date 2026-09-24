"""Independent broker-side readback of one adaptive paper trial via alpaca-py.

Separate from the engine transport and ledger: lists the trial's orders by client-id
prefix, the broker's own FILL activities for those orders, positions and open orders.
Reads credentials from --env-file without printing them; prints no account id, order id
or activity id. Read-only: GET requests only.

    python observe_ladder_trial.py --env-file PAPER_ENV --prefix adp-<trial>- --after ISO8601
"""
import argparse
import collections
import json
import sys
from datetime import datetime

import alpaca
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest

ap = argparse.ArgumentParser()
ap.add_argument("--env-file", required=True)
ap.add_argument("--prefix", required=True)
ap.add_argument("--after", required=True, help="ISO-8601 time before the trial's first order")
a = ap.parse_args()

env = {}
for line in open(a.env_file):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        name, value = line.split("=", 1)
        env[name.removeprefix("export ").strip()] = value.strip().strip('"')
client = TradingClient(env["APCA_API_KEY_ID"], env["APCA_API_SECRET_KEY"], paper=True)
del env

after = datetime.fromisoformat(a.after)
orders = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, after=after, limit=500, direction="asc"))
mine = [o for o in orders if str(o.client_order_id).startswith(a.prefix)]
suffix_of = {str(o.id): str(o.client_order_id)[len(a.prefix):] for o in mine}

activities = client.get("/account/activities/FILL", {"after": after.isoformat(), "direction": "asc", "page_size": 100})
fills = []
for act in activities or []:
    suffix = suffix_of.get(str(act.get("order_id")))
    if suffix is None:
        continue
    fills.append({"order": suffix, "symbol": act.get("symbol"), "side": act.get("side"), "qty": act.get("qty"),
                  "price": act.get("price"), "cum_qty": act.get("cum_qty"), "leaves_qty": act.get("leaves_qty"),
                  "type": act.get("type"), "transaction_time": act.get("transaction_time")})

out = {
    "method": "alpaca-py TradingClient.get_orders(status=all, after) filtered by client-id prefix; "
              "GET /v2/account/activities/FILL (after) joined to those orders; get_all_positions; open orders",
    "alpaca_py_version": alpaca.__version__,
    "python": sys.version.split()[0],
    "observed_at": datetime.now().astimezone().isoformat(),
    "prefix": a.prefix,
    "listing_after": a.after,
    "orders_listed_since_after": len(orders),
    "orders_with_prefix": len(mine),
    "orders": [{"order": str(o.client_order_id)[len(a.prefix):], "symbol": o.symbol, "side": str(o.side.value),
                "qty": str(o.qty), "limit_price": str(o.limit_price), "status": str(o.status.value),
                "filled_qty": str(o.filled_qty), "filled_avg_price": str(o.filled_avg_price)} for o in mine],
    "fill_activities": fills,
    "status_counts": dict(collections.Counter(str(o.status.value) for o in mine)),
    "positions_now": len(client.get_all_positions()),
    "open_orders_now": len(client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))),
}
print(json.dumps(out, indent=1))
