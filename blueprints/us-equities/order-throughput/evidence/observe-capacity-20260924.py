"""Independent observation of a capacity run via alpaca-py (separate from the harness code path).
Reads credentials from --env-file without printing them; prints only counts."""
import argparse, collections, json, sys
from datetime import datetime
import alpaca
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
ap = argparse.ArgumentParser(); ap.add_argument('--env-file', required=True); ap.add_argument('--receipt', required=True)
a = ap.parse_args()
env = dict(l.strip().split('=', 1) for l in open(a.env_file) if '=' in l)
rc = json.load(open(a.receipt))
prefix = (rc.get('probe_plan') or {}).get('client_order_id_prefix') or (rc.get('config') or {}).get('client_order_id_prefix')
c = TradingClient(env['APCA_API_KEY_ID'], env['APCA_API_SECRET_KEY'], paper=True)
start = datetime.fromisoformat(rc['started_at']); seen = {}; after = start
while True:
    batch = c.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, after=after, limit=500, direction='asc'))
    new = [o for o in batch if str(o.id) not in seen]
    for o in new: seen[str(o.id)] = o
    if len(batch) < 500 or not new: break
    after = max(o.submitted_at for o in batch)
mine = [o for o in seen.values() if str(o.client_order_id).startswith(prefix)]
out = {"method": "alpaca-py TradingClient.get_orders(status=all, after=receipt.started_at, asc, paged by submitted_at) filtered by the receipt's client_order_id prefix; then get_all_positions and open orders",
       "alpaca_py_version": alpaca.__version__, "python": sys.version.split()[0], "observed_at": datetime.now().astimezone().isoformat(),
       "receipt_started_at": rc['started_at'], "orders_listed_since_start": len(seen), "orders_with_run_prefix": len(mine),
       "status_counts": dict(collections.Counter(str(o.status.value) for o in mine)),
       "filled_qty_total": sum(float(o.filled_qty or 0) for o in mine),
       "positions_now": len(c.get_all_positions()), "open_orders_now": len(c.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN)))}
print(json.dumps(out, indent=1))
