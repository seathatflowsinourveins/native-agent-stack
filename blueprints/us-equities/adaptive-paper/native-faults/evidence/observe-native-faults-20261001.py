"""Read-only observation of one native-fault run's orders on account 2 (trading lane, 2026-10-01).

Independent of the harness's ledger and transport: it loads the key through the frozen engine's guarded credential
loader only (runner.credentials, paper_only=True) and asks the broker directly with alpaca-py's TradingClient
(paper=True), GET requests only. It prints no identifier, balance or credential: only order client-id suffixes
(c01, c04), symbol, side, quantity, type, limit price, time in force, extended hours, status, filled quantity,
counts and HTTP outcomes.

    python -B observe-20261001.py --engine ENGINE_CLONE --env-file "$PAPER_ENV_FILE_2" --prefix nf-...- --after ISO8601
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--engine", type=Path, required=True)
ap.add_argument("--env-file", type=Path, required=True)
ap.add_argument("--prefix", required=True)
ap.add_argument("--after", required=True)
a = ap.parse_args()
if not a.prefix.startswith("nf-") or not a.prefix.endswith("-"):
    sys.exit("prefix must look like nf-<stamp>-<hex>-")
sys.path.insert(0, str(a.engine / "blueprints/us-equities/adaptive-paper"))
from runner import credentials  # noqa: E402
from alpaca.common.exceptions import APIError  # noqa: E402
from alpaca.trading.client import TradingClient  # noqa: E402
from alpaca.trading.enums import ActivityType, QueryOrderStatus  # noqa: E402
from alpaca.trading.requests import GetOrdersRequest  # noqa: E402

key, secret = credentials(a.env_file, paper_only=True)
client = TradingClient(key, secret, paper=True)
del key, secret
after = datetime.fromisoformat(a.after.replace("Z", "+00:00"))
out = {"gets": 0}


def order_view(o):
    return {"client_suffix": str(o.client_order_id)[len(a.prefix):] if str(o.client_order_id).startswith(a.prefix) else "foreign",
            "symbol": o.symbol, "side": str(o.side.value), "qty": str(o.qty), "type": str(o.order_type.value),
            "limit_price": str(o.limit_price), "time_in_force": str(o.time_in_force.value),
            "extended_hours": o.extended_hours, "status": str(o.status.value), "filled_qty": str(o.filled_qty)}


account = client.get_account(); out["gets"] += 1
out["account_status"] = str(account.status.value) if hasattr(account.status, "value") else str(account.status)
out["position_count"] = len(client.get_all_positions()); out["gets"] += 1
out["open_order_count"] = len(client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=50))); out["gets"] += 1
window = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, after=after, limit=50, nested=False)); out["gets"] += 1
out["orders_since_start"] = [order_view(o) for o in window]
for case in ("c01", "c04"):
    try:
        o = client.get_order_by_client_id(a.prefix + case); out["gets"] += 1
        out[case] = order_view(o)
    except APIError as error:
        out["gets"] += 1
        out[case] = {"http_status": getattr(error, "status_code", None)}
fills = client.get(f"/account/activities/{ActivityType.FILL.value}", {"after": a.after}); out["gets"] += 1
out["fill_activities_since_start"] = len(fills) if isinstance(fills, list) else None
print(json.dumps(out, sort_keys=True))
