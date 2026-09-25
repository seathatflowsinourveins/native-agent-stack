"""Independent observation of a native-fault run via alpaca-py (separate from harness.py and the engine transport).
Reads credentials from --env-file without printing them; prints only statuses and counts."""
import argparse, collections, json, sys
from datetime import datetime
import alpaca
from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
ap = argparse.ArgumentParser(); ap.add_argument('--env-file', required=True); ap.add_argument('--receipt', required=True)
a = ap.parse_args()
env = dict(l.strip().split('=', 1) for l in open(a.env_file) if '=' in l)
rc = json.load(open(a.receipt)); prefix = rc['client_id_prefix']; start = datetime.fromisoformat(rc['started_at'])
c = TradingClient(env['APCA_API_KEY_ID'], env['APCA_API_SECRET_KEY'], paper=True)
orders = c.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, after=start, limit=500, direction='asc'))
mine = [o for o in orders if str(o.client_order_id).startswith(prefix)]
by_id = {str(o.client_order_id)[len(prefix):]: {"status": str(o.status.value), "filled_qty": str(o.filled_qty)} for o in mine}
def lookup(cid):
    try:
        o = c.get_order_by_client_id(cid); return {"found": True, "status": str(o.status.value), "filled_qty": str(o.filled_qty)}
    except APIError as e:
        return {"found": False, "http_status": getattr(e, "status_code", None)}
out = {"method": "alpaca-py TradingClient.get_orders(status=all, after=receipt.started_at) filtered by the receipt's client_id_prefix; get_order_by_client_id for c01 and c04; get_all_positions; open orders",
       "alpaca_py_version": alpaca.__version__, "python": sys.version.split()[0], "observed_at": datetime.now().astimezone().isoformat(),
       "receipt_started_at": rc['started_at'], "orders_listed_since_start": len(orders), "orders_with_prefix": len(mine),
       "by_suffix": by_id, "lookup_c01": lookup(prefix + "c01"), "lookup_c04": lookup(prefix + "c04"),
       "status_counts": dict(collections.Counter(v["status"] for v in by_id.values())),
       "positions_now": len(c.get_all_positions()), "open_orders_now": len(c.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN)))}
print(json.dumps(out, indent=1))
