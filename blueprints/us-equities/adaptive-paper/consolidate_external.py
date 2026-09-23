"""Consolidate same-account paper fills made outside the durable ledger into it.

A trial run in a separate state root trades the same broker account but books its fills
in its own ledger, so the account's durable ledger (default state root) no longer
reconciles with broker cash and its limits never saw those trades. This command, under
the account-writer lock:

1. proves the broker account flat with no open order (read-only preflight);
2. opens the durable ledger with its own frozen limits (``--config`` must be the config
   that ledger was frozen with, or the Ledger refuses);
3. lists broker orders submitted since the ledger's baseline (``trial.json`` ``started_at``,
   when ``baseline_cash`` was observed) whose client ids the ledger does not know, and
   requires that their net fill cash equals the gap between broker cash and
   ``baseline_cash + ledger cash_delta`` within 0.01 USD;
4. only with ``--apply``, books them with ``Ledger.record_external_fills`` (append-only
   event, realized loss counted against the ledger's limits) and re-checks that cash now
   reconciles.

Read-only unless ``--apply``. The receipt records counts, totals and the reconciliation
gap, never account ids or balances. Run with the adaptive-paper interpreter.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

TOLERANCE_USD = D("0.01")


TERMINAL = ("filled", "canceled", "expired", "rejected", "replaced")


def external_fills(orders, known_ids):
    """Every broker order the ledger does not know, filled or not, as record_external_fills
    input; the unfilled ones are booked too so later broker history recognises them."""
    fills = []
    for o in orders:
        if o["client_order_id"] in known_ids:
            continue
        if o["status"] not in TERMINAL:
            raise SystemExit("an external order is not terminal; the account is not settled")
        qty = D(str(o["filled_qty"] or 0))
        fills.append({"client_order_id": o["client_order_id"], "broker_id": o["id"], "symbol": o["symbol"], "side": o["side"],
                      "qty": str(qty), "price": str(o["filled_avg_price"]) if qty else None,
                      "filled_at": str(o["filled_at"] or o["updated_at"])})
    return fills


def fills_cash(fills):
    return sum((D(f["qty"]) * D(f["price"]) * (1 if f["side"] == "sell" else -1) for f in fills if D(f["qty"])), D(0))


def prefix_counts(fills):
    return dict(collections.Counter("-".join(f["client_order_id"].split("-")[:2]) for f in fills))


def reconciles(broker_cash, baseline_cash, ledger_cash_delta, external_cash):
    gap = D(broker_cash) - (D(baseline_cash) + D(ledger_cash_delta))
    return gap, abs(gap - D(external_cash)) <= TOLERANCE_USD


def _broker_orders(key, secret, since):
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    client = TradingClient(key, secret, paper=True)
    rows = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, after=since, limit=500))
    if len(rows) >= 500:
        raise SystemExit("more than 500 orders since --since: narrow the window")
    return [{"client_order_id": o.client_order_id, "id": str(o.id), "symbol": o.symbol, "side": o.side.value,
             "status": o.status.value, "filled_qty": o.filled_qty, "filled_avg_price": o.filled_avg_price,
             "filled_at": o.filled_at.isoformat() if o.filled_at else None,
             "updated_at": o.updated_at.isoformat() if o.updated_at else None} for o in rows]


def main(argv=None):
    from runner import credentials, load_config
    from safety import DEFAULT_STOP, Ledger, SafetyError, account_lock_fingerprint
    from transport import preflight

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env-file", type=Path, required=True)
    ap.add_argument("--config", type=Path, required=True, help="the config the durable ledger was frozen with")
    ap.add_argument("--state-root", type=Path, default=DEFAULT_STOP.parent)
    ap.add_argument("--reference", required=True, help="short text naming why these fills are external")
    ap.add_argument("--receipt", type=Path, required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    config, risk, _ = load_config(a.config)
    config_sha256 = hashlib.sha256(a.config.read_bytes()).hexdigest()
    key, secret = credentials(a.env_file)
    observation = preflight(key, secret, config["symbols"], feed=config["feed"], before_request=lambda *x, **y: None)
    receipt = {"kind": "external_fills_consolidation", "endpoint": "paper", "applied": False,
               "generated_at": datetime.now(timezone.utc).isoformat(), "reference": a.reference,
               "config_sha256": config_sha256}
    # preflight lists open orders only; a full page cannot prove there are none.
    receipt["broker_flat"] = (not observation["positions"] and not observation["orders"]
                              and observation["open_orders_complete"])
    fingerprint = observation["account_identity_sha256"]
    with account_lock_fingerprint(fingerprint):
        state_dir = a.state_root / fingerprint / "adaptive"
        meta = json.loads((state_dir / "trial.json").read_text())
        if meta.get("config_sha256") != config_sha256:
            raise SystemExit("--config is not the config this ledger was frozen with")
        if meta.get("phase") != "finished":
            raise SystemExit("the ledger's last trial is not finished; recover it first")
        since = datetime.fromtimestamp(meta["started_at"], timezone.utc)
        receipt["since"] = since.isoformat()
        if not (state_dir / "ledger.sqlite3").is_file():
            raise SystemExit("no durable ledger at the state root")
        ledger = Ledger(state_dir / "ledger.sqlite3", risk)
        try:
            known = ledger.known_client_ids()
            fills = external_fills(_broker_orders(key, secret, since), known)
            cash = fills_cash(fills)
            before = ledger.accounting()
            gap, ok = reconciles(observation["account"]["cash"], meta["baseline_cash"], before.cash_delta_usd, cash)
            receipt.update(external_orders=len(fills), external_fills=sum(1 for f in fills if D(f["qty"])),
                           external_prefixes=prefix_counts(fills), external_cash_usd=str(cash),
                           cash_gap_before_usd=str(gap), reconciles_with_external=ok and receipt["broker_flat"],
                           ledger_trial_phase=meta.get("phase"), ledger_realized_loss_before=str(before.cumulative_realized_loss_usd))
            code = 0 if receipt["reconciles_with_external"] else 3
            if a.apply:
                if code:
                    receipt["refused"] = "broker_not_flat_or_gap_mismatch"
                elif not fills:
                    receipt["refused"] = "nothing_to_apply"
                else:
                    try:
                        result = ledger.record_external_fills(fills, time.time(), a.reference)
                    except SafetyError as exc:
                        receipt["refused"] = str(exc)
                        result = None
                        code = 3
                if receipt.get("refused") is None:
                    after = ledger.accounting()
                    gap_after, ok_after = reconciles(observation["account"]["cash"], meta["baseline_cash"],
                                                     after.cash_delta_usd, D(0))
                    receipt.update(applied=True, booked=result, cash_gap_after_usd=str(gap_after),
                                   reconciled_after=ok_after, ledger_realized_loss_after=str(after.cumulative_realized_loss_usd),
                                   limits={"max_gross_loss_usd": str(risk.max_gross_loss_usd),
                                           "max_drawdown_usd": str(risk.max_drawdown_usd)})
                    code = 0 if ok_after else 3
        finally:
            ledger.close()
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    a.receipt.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
    print(json.dumps({k: receipt.get(k) for k in ("applied", "external_fills", "external_cash_usd",
                                                    "cash_gap_before_usd", "reconciles_with_external",
                                                    "reconciled_after")}, default=str))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
