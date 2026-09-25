#!/usr/bin/env python3
"""Account binding and order submission for the news-forward paper runner.

Orders are possible only with the dedicated account in
~/.config/codex-ecosystem/secrets/alpaca-paper-3.env, through alpaca-py's paper
TradingClient, after:
  * the file exists and passes credential_guard.open_verified (0600, owner, no symlink,
    no Git worktree ancestor, ...);
  * its key id differs from alpaca-paper-2.env's (paper-2 belongs to other studies and
    is never used for orders);
  * the client's trading host is exactly https://paper-api.alpaca.markets;
  * at start, every open order and every position traces to a client_order_id with the
    nf1- prefix.
Every order passes planner.contract_envelope (order_contract.build_envelope) first.

In dry-run mode no trading client is constructed at all: intended orders are validated
and journaled, and nothing is sent.

CLI (read-only): ``executor.py check-account`` runs the same refusal checks against the
paper-3 account and prints a verdict; it never submits or cancels anything.
"""
import argparse
import json
import os
import sys
from datetime import timedelta
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402
import live_news  # noqa: E402
import planner  # noqa: E402

PAPER_TRADING_HOST = "https://paper-api.alpaca.markets"
TRADING_ENV_NAME = "alpaca-paper-3.env"


class AccountRefused(RuntimeError):
    """Orders refused for this account; the message is a fixed reason code."""


def _v(value):
    """Enum -> its value; everything else unchanged."""
    return getattr(value, "value", value)


def as_dict(obj, fields):
    if isinstance(obj, dict):
        return {f: _v(obj.get(f)) for f in fields}
    return {f: _v(getattr(obj, f, None)) for f in fields}


ORDER_FIELDS = ("id", "client_order_id", "symbol", "side", "qty", "filled_qty", "filled_avg_price", "status",
                "type", "time_in_force", "limit_price", "submitted_at", "filled_at", "extended_hours")
POSITION_FIELDS = ("symbol", "qty", "side", "avg_entry_price", "market_value", "unrealized_pl")
ACCOUNT_FIELDS = ("status", "equity", "last_equity", "cash", "buying_power", "multiplier", "trading_blocked",
                  "account_blocked", "shorting_enabled", "pattern_day_trader")


def trading_credentials(path=common.TRADING_ENV, paper2_env=common.PAPER2_ENV):
    """(key_id, secret) of the dedicated paper-3 account, or AccountRefused.

    paper2_env is read only to refuse a paper-3 file that carries the paper-2 key id.
    """
    name = os.path.basename(path)
    if name != TRADING_ENV_NAME or "paper-2" in path or "live" in name:
        raise AccountRefused("trading_env_not_paper_3")
    if not os.path.lexists(path):
        raise AccountRefused("trading_env_missing")
    try:
        key_id, secret = live_news.read_credentials(path)
    except live_news.CredentialError as error:
        raise AccountRefused(f"trading_env_guard:{error}") from None
    if os.path.lexists(paper2_env):
        try:
            other_key, _ = live_news.read_credentials(paper2_env)
        except live_news.CredentialError:
            other_key = None
        if other_key is not None and other_key == key_id:
            raise AccountRefused("trading_key_is_paper_2")
    return key_id, secret


def make_trading_client(key_id, secret):
    from alpaca.trading.client import TradingClient  # noqa: PLC0415 - adaptive-paper runtime only

    client = TradingClient(key_id, secret, paper=True)
    host = str(_v(getattr(client, "_base_url", ""))).rstrip("/")
    if host != PAPER_TRADING_HOST:
        raise AccountRefused("trading_host_not_paper")
    return client


class AlpacaBroker:
    """Thin normalizing wrapper around alpaca-py's TradingClient (or a test double)."""

    def __init__(self, client):
        host = str(_v(getattr(client, "_base_url", ""))).rstrip("/")
        if host != PAPER_TRADING_HOST:
            raise AccountRefused("trading_host_not_paper")
        self.client = client

    def account(self):
        return as_dict(self.client.get_account(), ACCOUNT_FIELDS)

    def positions(self):
        """Positions with a signed qty (negative for a short, whatever sign the API uses)."""
        out = []
        for p in self.client.get_all_positions():
            row = as_dict(p, POSITION_FIELDS)
            qty = abs(Decimal(str(row.get("qty") or 0)))
            row["qty"] = str(-qty if str(row.get("side")).lower() == "short" else qty)
            out.append(row)
        return out

    def orders(self, status="open", after=None, symbols=None, limit=500, direction=None):
        from alpaca.common.enums import Sort  # noqa: PLC0415
        from alpaca.trading.enums import QueryOrderStatus  # noqa: PLC0415
        from alpaca.trading.requests import GetOrdersRequest  # noqa: PLC0415

        request = GetOrdersRequest(status=QueryOrderStatus(status), after=after, symbols=symbols, limit=limit,
                                   direction=Sort(direction) if direction else None)
        return [as_dict(o, ORDER_FIELDS) for o in self.client.get_orders(filter=request)]

    def all_orders(self, after, page=500, max_pages=40):
        """Every order submitted after `after`, oldest first, across pages (m5).

        `after` is exclusive, so each next page starts one microsecond before the last
        page's newest submission time and ids remove the overlap. A page that adds
        nothing new, or more than max_pages pages, raises rather than truncating.
        """
        out, seen, cursor = [], set(), after
        for _ in range(max_pages):
            batch = self.orders("all", after=cursor, limit=page, direction="asc")
            fresh = [o for o in batch if o.get("id") not in seen]
            out.extend(fresh)
            seen.update(o.get("id") for o in fresh)
            if len(batch) < page:
                return out
            if not fresh:
                raise RuntimeError("order_history_pagination_stalled")
            stamps = [o["submitted_at"] for o in batch if o.get("submitted_at")]
            cursor = max(stamps) - timedelta(microseconds=1)
        raise RuntimeError("order_history_pagination_limit")

    def order_by_client_id(self, client_id):
        try:
            return as_dict(self.client.get_order_by_client_id(client_id), ORDER_FIELDS)
        except Exception:  # noqa: BLE001 - absent order
            return None

    def submit(self, intent):
        from alpaca.trading.enums import OrderSide, TimeInForce  # noqa: PLC0415
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest  # noqa: PLC0415

        common_args = {
            "symbol": intent["symbol"],
            "qty": float(Decimal(intent["qty"])),
            "side": OrderSide(intent["side"]),
            "time_in_force": TimeInForce(intent["time_in_force"]),
            "client_order_id": intent["client_order_id"],
            "extended_hours": bool(intent.get("extended_hours", False)),
        }
        if intent["type"] == "limit":
            request = LimitOrderRequest(limit_price=float(Decimal(intent["limit_price"])), **common_args)
        else:
            request = MarketOrderRequest(**common_args)
        try:
            return as_dict(self.client.submit_order(order_data=request), ORDER_FIELDS)
        except Exception as error:  # noqa: BLE001
            existing = self.order_by_client_id(intent["client_order_id"])
            if existing is not None:
                existing["idempotent_existing"] = True
                return existing
            raise RuntimeError(f"submit_failed:{type(error).__name__}:{str(error)[:200]}") from None

    def cancel(self, order_id):
        self.client.cancel_order_by_id(order_id)


def foreign_holdings(broker):
    """Open orders and positions that do not trace to an nf1- client_order_id."""
    problems = []
    for o in broker.orders("open"):
        if not planner.is_nf1(o.get("client_order_id")):
            problems.append({"kind": "open_order", "symbol": o.get("symbol")})
    for p in broker.positions():
        history = broker.orders("all", symbols=[p["symbol"]], limit=100)
        if not any(planner.is_nf1(o.get("client_order_id")) and Decimal(str(o.get("filled_qty") or 0)) > 0 for o in history):
            problems.append({"kind": "position", "symbol": p["symbol"]})
    return problems


def start_check(broker):
    """Refusal checks at start; returns the start-of-day account snapshot."""
    account = broker.account()
    if str(account.get("status")).upper() != "ACTIVE":
        raise AccountRefused("account_not_active")
    if account.get("trading_blocked") or account.get("account_blocked"):
        raise AccountRefused("account_blocked")
    foreign = foreign_holdings(broker)
    if foreign:
        raise AccountRefused("foreign_orders_or_positions")
    return account


class RiskGate:
    """Independent pre-submit check of every entry against the hard caps (M3).

    The gate keeps its own per-arm exposure: synced from the broker's fill-based state by
    the supervisor, then raised by each entry it passes. At 100% of each cap it checks the
    order's notional against the per-order and per-name cap (5% E), one symbol per arm and
    day, the names per leg, the arm's gross cap, the account's gross cap across arms and
    the window's net cap. Planners size below these caps; the gate is the second line.
    """

    def __init__(self, limits, account_cap):
        self.limits = dict(limits)
        self.account_cap = Decimal(str(account_cap))
        self.exposures = {arm: planner.Exposure() for arm in self.limits}

    def sync(self, exposures):
        self.exposures = {arm: planner.copy_exposure(x) for arm, x in exposures.items()}

    def check(self, arm, window, leg, symbol, notional):
        lim = self.limits.get(arm)
        if lim is None:
            return "no_limits_for_arm"
        x = self.exposures.setdefault(arm, planner.Exposure())
        notional = Decimal(str(notional))
        if notional <= 0:
            return "zero_notional"
        if notional > lim.per_order_cap:
            return "per_order_cap"
        if symbol in x.symbols:
            return "per_name_repeat"
        if x.names.get((window, leg), 0) >= planner.MAX_NAMES_PER_LEG:
            return "names_per_leg_cap"
        if x.gross + notional > lim.gross_cap:
            return "gross_cap"
        if sum((e.gross for e in self.exposures.values()), Decimal("0")) + notional > self.account_cap:
            return "account_gross_cap"
        net = planner.window_net(x, window) + (notional if leg == planner.LEG_LONG else -notional)
        if abs(net) > lim.net_cap:
            return "net_cap"
        return None

    def commit(self, arm, window, leg, symbol, notional):
        planner.commit_entry(self.exposures.setdefault(arm, planner.Exposure()), Decimal(str(notional)), window, leg, symbol)


class Executor:
    """Validates, caps and journals every order; submits only in paper mode.

    Entries (context purpose "entry") must carry arm, session_label (the window), leg and
    ref_price; they are refused while killed or in exit-only mode and must pass the
    RiskGate. Exits and kill flattens are never refused for the kill (B1); only the STOP
    file, the order contract, the first-order time and a passed deadline stop them.
    """

    def __init__(self, mode, journal, state_root, broker=None, clock=common.utc_now, not_before=None,
                 gate=None, exit_only=False):
        if mode not in ("dry-run", "paper"):
            raise ValueError("mode must be dry-run or paper")
        if mode == "paper" and broker is None:
            raise AccountRefused("paper_mode_without_verified_broker")
        self.mode = mode
        self.journal = journal
        self.state_root = state_root
        self.broker = broker if mode == "paper" else None
        self.clock = clock
        self.not_before = not_before  # no order is sent before this instant (UTC)
        self.gate = gate
        self.exit_only = exit_only
        self.killed = False
        self.submitted = {}   # client_order_id -> order dict (or dry-run record)
        self.ref_prices = {}  # client_order_id -> reference price of each entry (pending exposure, m4)

    def halted(self):
        return os.path.exists(os.path.join(self.state_root, "STOP")) or self.killed

    def _refuse(self, reason, intent, context):
        self.journal.write("order_refused", reason=reason, intent=intent, **context)
        return None

    def send(self, intent, context, dry_run=False, deadline=None):
        """Validate with the order contract, then submit (paper) or journal (dry-run).

        dry_run=True journals the validated intent without sending it, in any mode (an
        arm that is not yet enabled for orders). deadline: refuse if the clock has passed
        it at the moment of sending (m1).
        """
        cid = intent["client_order_id"]
        entry = context.get("purpose") == "entry"
        if not planner.is_nf1(cid):
            return self._refuse("client_order_id_prefix", intent, context)
        if os.path.exists(os.path.join(self.state_root, "STOP")):
            return self._refuse("stop_file", intent, context)
        if entry and self.killed:
            return self._refuse("kill_switch", intent, context)
        if entry and self.exit_only:
            return self._refuse("exit_only_mode", intent, context)
        if cid in self.submitted:
            return self.submitted[cid]
        try:
            envelope = planner.contract_envelope(intent)
        except ValueError as error:
            return self._refuse(f"contract:{error}", intent, context)
        mode = "dry-run" if dry_run else self.mode
        now = self.clock()
        if mode == "paper" and self.not_before is not None and now < self.not_before:
            return self._refuse("before_first_order_time", intent, {**context, "not_before": common.iso(self.not_before)})
        if deadline is not None and now > deadline:
            return self._refuse("deadline_passed", intent, {**context, "deadline": common.iso(deadline)})
        price = context.get("ref_price") or intent.get("limit_price")
        notional = Decimal(intent["qty"]) * Decimal(str(price)) if price else None
        if entry:
            if self.gate is None or notional is None:
                return self._refuse("executor_cap:no_gate_or_reference_price", intent, context)
            why = self.gate.check(context.get("arm"), context.get("session_label"), context.get("leg"), intent["symbol"], notional)
            if why:
                return self._refuse(f"executor_cap:{why}", intent, {**context, "notional": str(notional)})
        self.journal.write("order_intent", mode=mode, envelope=envelope, **context)
        if mode == "dry-run":
            record = {"id": f"dry-{cid}", "client_order_id": cid, "status": "filled", "simulated": True,
                      "symbol": intent["symbol"], "side": intent["side"], "qty": intent["qty"], "filled_qty": intent["qty"],
                      "filled_avg_price": str(price) if price else None, "limit_price": intent.get("limit_price"),
                      "submitted_at": now}
            self.submitted[cid] = record
            if entry:
                self.gate.commit(context.get("arm"), context.get("session_label"), context.get("leg"), intent["symbol"], notional)
                self.ref_prices[cid] = str(price)
            return record
        try:
            order = self.broker.submit(envelope["intent"])
        except Exception as error:  # noqa: BLE001
            return self._refuse(str(error)[:300], intent, context)
        self.submitted[cid] = order
        if entry:
            self.gate.commit(context.get("arm"), context.get("session_label"), context.get("leg"), intent["symbol"], notional)
            self.ref_prices[cid] = str(price)
        # m2: an order that already existed under this id is not a new submission
        self.journal.write("order_idempotent_existing" if order.get("idempotent_existing") else "order_submitted",
                           order=order, **context)
        return order


def check_account_main():
    """Read-only verdict for the paper-3 account (no order, cancel or position call)."""
    report = {"trading_env": common.TRADING_ENV, "host": None, "verdict": None}
    try:
        key_id, secret = trading_credentials()
        client = make_trading_client(key_id, secret)
        report["host"] = PAPER_TRADING_HOST
        broker = AlpacaBroker(client)
        account = start_check(broker)
        report["account"] = {k: account.get(k) for k in ("status", "equity", "cash", "multiplier", "shorting_enabled",
                                                           "trading_blocked", "account_blocked")}
        report["open_orders"] = len(broker.orders("open"))
        report["positions"] = len(broker.positions())
        report["verdict"] = "ready_for_paper"
    except AccountRefused as error:
        report["verdict"] = f"refused:{error}"
    print(json.dumps(report, indent=1, default=str))
    return 0 if report["verdict"] == "ready_for_paper" else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("check-account",))
    parser.parse_args(argv)
    return check_account_main()


if __name__ == "__main__":
    sys.exit(main())
