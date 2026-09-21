#!/usr/bin/env python3
"""One bounded Alpaca paper round trip; native transport, deterministic risk."""
from __future__ import annotations

import argparse
from collections import deque
from contextlib import contextmanager
from decimal import Decimal, ROUND_CEILING
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

PAPER_URL = "https://paper-api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets"
DEFAULT = {
    "schema_version": 1, "strategy": "operational-smoke-round-trip",
    "symbol": "SPY", "qty": "1", "paper_capital_usd": "1000", "minimum_account_equity_usd": "25000",
    "max_order_notional_usd": "1000", "max_gross_exposure_usd": "1000",
    "max_realized_loss_usd": "5", "max_spread_usd": "0.50",
    "limit_offset_usd": "0.05", "max_quote_age_seconds": 15,
    "max_clock_offset_seconds": 5, "position_observation_seconds": 3,
    "max_write_attempts": 4, "max_requests_per_minute": 120,
    "http_timeout_seconds": 5, "order_wait_seconds": 20,
    "cancel_wait_seconds": 15, "trial_timeout_seconds": 180,
    "minimum_session_remaining_seconds": 300, "feed": "iex", "paper": True,
}
TERMINAL = {"filled", "canceled", "expired", "rejected"}
PENDING = {"new", "accepted", "pending_new", "partially_filled", "pending_cancel",
           "accepted_for_bidding", "held", "calculated"}


class SafetyError(RuntimeError):
    """A bounded reason code, never arbitrary broker text or credentials."""


class BrokerError(RuntimeError):
    def __init__(self, status=None):
        self.status = status if type(status) is int else None
        super().__init__("broker_request_failed")


def number(value, *, zero=False, maximum=Decimal("10000000")):
    text = str(value) if type(value) in (str, int, Decimal) else ""
    if not re.fullmatch(r"[0-9]{1,10}(?:\.[0-9]{1,8})?", text):
        raise SafetyError("invalid_decimal")
    result = Decimal(text)
    if not result.is_finite() or result < 0 or (not zero and result == 0) or result > maximum:
        raise SafetyError("decimal_out_of_bounds")
    return result


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SafetyError("duplicate_json_field")
        result[key] = value
    return result


def parse_json(text):
    try:
        return json.loads(text, object_pairs_hook=unique_json,
                          parse_constant=lambda _: (_ for _ in ()).throw(SafetyError("nonfinite_json")))
    except (ValueError, RecursionError):
        raise SafetyError("invalid_json") from None


def load_config(path):
    if path.stat().st_size > 8192:
        raise SafetyError("config_too_large")
    config = parse_json(path.read_text())
    # Exact types prevent true==1 and 1.0==1 accepting malformed config.
    if (type(config) is not dict or set(config) != set(DEFAULT)
            or any(type(config[k]) is not type(v) or config[k] != v for k, v in DEFAULT.items())):
        raise SafetyError("config_is_not_frozen_smoke_trial")
    return config


class Journal:
    """Private append-only records, synced before each possibly mutating request."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        self.file = os.fdopen(fd, "r+", encoding="utf-8")
        text = self.file.read(4_000_001)
        if len(text) > 4_000_000 or (text and not text.endswith("\n")):
            self.file.close()
            raise SafetyError("journal_incomplete_or_oversized")
        self.events = []
        try:
            for line in text.splitlines():
                event = parse_json(line)
                if type(event) is not dict or type(event.get("event")) is not str:
                    raise SafetyError("journal_invalid")
                self.events.append(event)
        except BaseException:
            self.file.close()
            raise
        # Persist directory entry as well as journal bytes.
        directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def add(self, event, **data):
        record = {"event": event, **data}
        self.file.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
        self.file.flush()
        os.fsync(self.file.fileno())
        self.events.append(record)
        return record

    def first(self, event):
        return next((e for e in self.events if e["event"] == event), None)

    def close(self):
        self.file.close()


@contextmanager
def account_lock(account_id, lock_root=None):
    """All CLI runs use this single fixed lock namespace, independent of trial."""
    if type(account_id) is not str or not account_id or len(account_id) > 128:
        raise SafetyError("invalid_account_identity")
    root = lock_root or Path.home() / ".local/state/native-agent-stack/alpaca-paper/locks"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    fingerprint = hashlib.sha256(account_id.encode()).hexdigest()
    fd = os.open(root / (fingerprint + ".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SafetyError("account_writer_already_running") from None
        yield fingerprint
    finally:
        os.close(fd)


class Gate:
    """Counts every HTTP attempt, including GETs; shares history across restart."""
    def __init__(self, config, journal=None, now=time.time, sleep=time.sleep):
        self.config, self.journal, self.now, self.sleep = config, journal, now, sleep
        self.started = now()
        self.deadline = self.started + config["trial_timeout_seconds"]
        self.recent = deque()
        self.submit_guard = None

    def attach(self, journal):
        self.journal = journal
        saved = [e["at"] for e in journal.events if e["event"] == "request"]
        self.recent = deque(sorted(saved + list(self.recent)))

    def before(self, method):
        write = method.upper() != "GET"
        count = sum(e["event"] == "request" and e.get("write", False)
                    for e in self.journal.events) if self.journal else 0
        if write and (self.journal is None or count >= self.config["max_write_attempts"]):
            raise SafetyError("write_budget_exhausted")
        now = self.now()
        if self.recent and self.recent[-1] > now:
            raise SafetyError("clock_moved_backward")
        while self.recent and now - self.recent[0] >= 60:
            self.recent.popleft()
        delay = max(0, (self.recent[-1] + 0.51 - now) if self.recent else 0)
        if len(self.recent) >= self.config["max_requests_per_minute"]:
            delay = max(delay, self.recent[0] + 60.01 - now)
        if now + delay + 2 * self.config["http_timeout_seconds"] >= self.deadline:
            raise SafetyError("trial_deadline_reached")
        if delay:
            self.sleep(delay)
        if method.upper() == "POST" and self.submit_guard:
            self.submit_guard()
        at = self.now()
        if self.journal:
            self.journal.add("request", at=at, write=write)
        self.recent.append(at)


def enum(value):
    return getattr(value, "value", value)


def timestamp(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise SafetyError("invalid_timestamp")
    return value


def allowed_request(base, method, url):
    parsed = urlsplit(url)
    if parsed.scheme + "://" + parsed.netloc != base or parsed.fragment or parsed.query:
        return False
    if base == DATA_URL:
        return method == "GET" and parsed.path == "/v2/stocks/quotes/latest"
    if method == "GET":
        return parsed.path in {"/v2/account", "/v2/clock", "/v2/assets/SPY", "/v2/positions",
                               "/v2/orders", "/v2/orders:by_client_order_id"}
    return ((method == "POST" and parsed.path == "/v2/orders") or
            (method == "DELETE" and re.fullmatch(r"/v2/orders/[a-fA-F0-9-]{36}", parsed.path) is not None))


class Alpaca:
    """Pinned alpaca-py transport; only private seam is finite timeout/no retry."""
    evidence_kind = "native_alpaca_paper"

    def __init__(self, key, secret, gate):
        from importlib.metadata import version
        from alpaca.trading.client import TradingClient
        from alpaca.data.historical import StockHistoricalDataClient
        if version("alpaca-py") != "0.44.0":
            raise SafetyError("unqualified_sdk_version")
        self.gate = gate
        self.trading = TradingClient(key, secret, paper=True)
        self.data = StockHistoricalDataClient(key, secret)
        if enum(self.trading._base_url) != PAPER_URL or enum(self.data._base_url) != DATA_URL:
            raise SafetyError("endpoint_boundary_failed")
        for client, base in ((self.trading, PAPER_URL), (self.data, DATA_URL)):
            client._retry = 0
            client._session.trust_env = False
            native_request = client._session.request

            def bounded(method, url, _native=native_request, _base=base, **kwargs):
                if not allowed_request(_base, method.upper(), url):
                    raise SafetyError("endpoint_boundary_failed")
                gate.before(method)
                timeout = gate.config["http_timeout_seconds"]
                kwargs.update(timeout=(timeout, timeout), allow_redirects=False)
                response = _native(method, url, **kwargs)
                if 300 <= response.status_code < 400:
                    raise SafetyError("redirect_forbidden")
                return response

            client._session.request = bounded

    def _call(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except SafetyError:
            raise
        except Exception as error:
            raise BrokerError(getattr(error, "status_code", None)) from None

    def account(self):
        account = self._call(self.trading.get_account)
        return {"id": str(account.id), "status": enum(account.status),
                "currency": account.currency, "blocked": account.trading_blocked,
                "account_blocked": account.account_blocked, "transfers_blocked": account.transfers_blocked,
                "trade_suspended_by_user": account.trade_suspended_by_user,
                "buying_power": account.buying_power, "equity": account.equity}

    def clock(self):
        clock = self._call(self.trading.get_clock)
        return {"open": clock.is_open, "at": clock.timestamp.timestamp(), "close": clock.next_close.timestamp()}

    def asset(self):
        asset = self._call(self.trading.get_asset, "SPY")
        return {"symbol": asset.symbol, "status": enum(asset.status), "tradable": asset.tradable}

    def quote(self):
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockLatestQuoteRequest
        quotes = self._call(self.data.get_stock_latest_quote,
                            StockLatestQuoteRequest(symbol_or_symbols=["SPY"], feed=DataFeed.IEX))
        quote = quotes["SPY"]
        return {"bid": str(quote.bid_price), "ask": str(quote.ask_price), "at": quote.timestamp.timestamp()}

    def positions(self):
        return [{"symbol": p.symbol, "qty": p.qty} for p in self._call(self.trading.get_all_positions)]

    @staticmethod
    def order(order):
        return {"id": str(order.id), "client_order_id": order.client_order_id,
                "symbol": order.symbol, "side": enum(order.side), "status": enum(order.status),
                "qty": order.qty, "filled_qty": order.filled_qty,
                "filled_avg_price": order.filled_avg_price}

    def open_orders(self):
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        return [self.order(o) for o in self._call(self.trading.get_orders,
                GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=500))]

    def lookup(self, client_id):
        try:
            return self.order(self._call(self.trading.get_order_by_client_id, client_id))
        except BrokerError as error:
            if error.status == 404:
                return None
            raise

    def submit(self, intent):
        from alpaca.trading.requests import LimitOrderRequest
        return self.order(self._call(self.trading.submit_order, LimitOrderRequest(**intent)))

    def cancel(self, order_id):
        self._call(self.trading.cancel_order_by_id, order_id)


class Runner:
    def __init__(self, broker, config, journal, gate, kill_file):
        self.broker, self.config, self.journal, self.gate = broker, config, journal, gate
        self.kill_file = Path(kill_file)
        self.orders = {}
        self.quote_observations = []
        self.last_quote = None

    def clock(self, entry=False):
        clock = self.broker.clock()
        offset = timestamp(clock["at"]) - self.gate.now()
        if (abs(offset) > self.config["max_clock_offset_seconds"] or clock["open"] is not True
                or timestamp(clock["close"]) - clock["at"] <
                   (self.config["minimum_session_remaining_seconds"] if entry else 60)):
            raise SafetyError("regular_session_clock_required")
        return offset

    def quote(self):
        offset = self.clock()
        quote = self.broker.quote()
        bid, ask = number(quote["bid"]), number(quote["ask"])
        age = self.gate.now() + offset - timestamp(quote["at"])
        if not -1 <= age <= self.config["max_quote_age_seconds"]:
            raise SafetyError("quote_not_fresh")
        if ask < bid or ask - bid > number(self.config["max_spread_usd"]):
            raise SafetyError("quote_spread_invalid")
        self.quote_observations.append({"bid": str(bid), "ask": str(ask), "age_seconds": round(age, 3)})
        self.last_quote = (quote["at"], offset)
        return bid, ask

    def preflight(self, account):
        if (account["status"] != "ACTIVE" or account["currency"] != "USD"
                or any(account.get(k) is not False for k in
                       ("blocked", "account_blocked", "trade_suspended_by_user"))):
            raise SafetyError("account_not_ready")
        if number(account["buying_power"]) < number(self.config["paper_capital_usd"]):
            raise SafetyError("insufficient_paper_buying_power")
        if number(account["equity"]) < number(self.config["minimum_account_equity_usd"]):
            raise SafetyError("account_equity_below_frozen_pdt_buffer")
        self.clock(entry=True)
        asset = self.broker.asset()
        if asset != {"symbol": "SPY", "status": "active", "tradable": True}:
            raise SafetyError("asset_not_ready")
        if self.broker.positions() or self.broker.open_orders():
            raise SafetyError("initial_account_not_flat_and_idle")
        _, ask = self.quote()
        if ask + number(self.config["limit_offset_usd"]) > number(self.config["max_order_notional_usd"]):
            raise SafetyError("entry_notional_exceeds_cap")
        if self.kill_file.exists():
            raise SafetyError("kill_switch_blocks_entry")

    def validate_order(self, order, intent):
        if (not isinstance(order, dict) or order.get("client_order_id") != intent["client_order_id"]
                or order.get("symbol") != "SPY" or order.get("side") != intent["side"]
                or type(order.get("id")) is not str or not order["id"]
                or order.get("status") not in TERMINAL | PENDING):
            raise SafetyError("unexpected_order_identity_or_state")
        qty = number(order["qty"], maximum=Decimal(1))
        filled = number(order["filled_qty"], zero=True, maximum=qty)
        if qty != number(intent["qty"]) or (order["status"] == "filled" and filled != qty):
            raise SafetyError("unexpected_order_quantity")
        if filled:
            average = number(order["filled_avg_price"])
            limit = number(intent["limit_price"])
            if (intent["side"] == "buy" and average > limit) or (intent["side"] == "sell" and average < limit):
                raise SafetyError("fill_violates_limit")
        prior = self.orders.get(intent["side"])
        if prior is None:
            prior = next((e["order"] for e in reversed(self.journal.events)
                          if e["event"] == "order_observation" and e["order"]["side"] == intent["side"]), None)
        if prior and filled < number(prior["filled_qty"], zero=True):
            raise SafetyError("filled_quantity_decreased")
        self.orders[intent["side"]] = order
        self.journal.add("order_observation", order=order)
        return order

    def find(self, intent):
        order = self.broker.lookup(intent["client_order_id"])
        return self.validate_order(order, intent) if order is not None else None

    def submit_once(self, intent):
        # No blind retries, including when a timeout/429 may hide acceptance.
        self.journal.add("submit_intent", intent=intent)
        def guard():
            if intent["side"] == "buy" and self.kill_file.exists():
                raise SafetyError("kill_switch_blocks_entry")
            if self.last_quote is None:
                raise SafetyError("quote_not_fresh_at_submit")
            at, offset = self.last_quote
            if not -1 <= self.gate.now() + offset - at <= self.config["max_quote_age_seconds"]:
                raise SafetyError("quote_not_fresh_at_submit")
        self.gate.submit_guard = guard
        try:
            return self.validate_order(self.broker.submit(intent), intent)
        except BrokerError as error:
            self.journal.add("ambiguous_submit", side=intent["side"], status=error.status)
            return None
        finally:
            self.gate.submit_guard = None

    def settle(self, intent, initial=None):
        end = self.gate.now() + self.config["order_wait_seconds"]
        order = initial
        if order is not None and order["status"] in TERMINAL:
            return order
        if order is None:
            order = next((e["order"] for e in reversed(self.journal.events)
                          if e["event"] == "order_observation" and
                          e["order"]["client_order_id"] == intent["client_order_id"]), None)
        while self.gate.now() < end:
            observed = self.find(intent)
            if observed is not None:
                order = observed
                if order["status"] in TERMINAL:
                    return order
            if order is not None and self.kill_file.exists():
                break
            self.gate.sleep(1)
        if order is None:
            raise SafetyError("ambiguous_order_not_found_no_resubmit")
        canceled = any(e["event"] == "cancel_intent" and e["client_order_id"] == intent["client_order_id"]
                       for e in self.journal.events)
        if not canceled and order["status"] not in TERMINAL:
            self.journal.add("cancel_intent", client_order_id=intent["client_order_id"])
            try:
                self.broker.cancel(order["id"])
            except BrokerError as error:
                self.journal.add("ambiguous_cancel", status=error.status)
        # Cancel acknowledgement is not finality: observe terminal filled quantity.
        end = self.gate.now() + self.config["cancel_wait_seconds"]
        while self.gate.now() < end:
            order = self.find(intent)
            if order is not None and order["status"] in TERMINAL:
                return order
            self.gate.sleep(1)
        raise SafetyError("cancel_finality_unobserved")

    def intent(self, side, trial, qty, price):
        qty = number(qty, maximum=Decimal(1))
        price = number(price)
        if qty * price > number(self.config["max_order_notional_usd"]):
            raise SafetyError("order_notional_exceeds_cap")
        intent = {"symbol": "SPY", "side": side, "qty": str(qty), "type": "limit",
                  "time_in_force": "day", "extended_hours": False,
                  "client_order_id": "nas-" + trial + "-" + side, "limit_price": str(price)}
        # Reuse original basic-equity contract for whole-share intents. Partial
        # exits retain exact observed quantity, independently bounded above.
        if qty == qty.to_integral_value():
            path = Path(__file__).resolve().parents[1] / "order-contract/order_contract.py"
            spec = importlib.util.spec_from_file_location("basic_order_contract", path)
            contract = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(contract)
            intent = contract.canonicalize(intent)["intent"]
        return intent

    def lifecycle(self, trial, recover):
        frozen = self.journal.first("trial")
        if frozen:
            if not recover or frozen["trial"] != trial or frozen["config"] != self.config:
                raise SafetyError("existing_trial_requires_matching_recovery")
        else:
            if recover:
                raise SafetyError("no_trial_to_recover")
            self.journal.add("trial", trial=trial, config=self.config, started_at=self.gate.now())
        entries = [e["intent"] for e in self.journal.events if e["event"] == "submit_intent"]
        if len(entries) > 2 or len({i["side"] for i in entries}) != len(entries):
            raise SafetyError("journal_duplicate_intents")
        for stored in entries:
            if (stored.get("side") not in ("buy", "sell") or
                    stored != self.intent(stored["side"], trial, stored.get("qty"), stored.get("limit_price"))):
                raise SafetyError("journal_intent_does_not_match_frozen_trial")
        entry = next((i for i in entries if i["side"] == "buy"), None)
        if entry is None:
            if recover:
                raise SafetyError("recovery_cannot_create_entry")
            self.clock(entry=True)
            if self.kill_file.exists() or self.broker.positions() or self.broker.open_orders():
                raise SafetyError("entry_boundary_not_ready")
            if self.gate.now() + 120 >= self.gate.deadline:
                raise SafetyError("insufficient_cleanup_time_reserve")
            _, ask = self.quote()
            if self.kill_file.exists():
                raise SafetyError("kill_switch_blocks_entry")
            price = (ask + number(self.config["limit_offset_usd"])).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
            entry = self.intent("buy", trial, "1", price)
            initial = self.submit_once(entry)
        else:
            initial = self.find(entry)
        filled_entry = self.settle(entry, initial)
        bought = number(filled_entry["filled_qty"], zero=True, maximum=Decimal(1))
        if bought:
            average = number(filled_entry["filled_avg_price"])
            if bought * average > number(self.config["max_gross_exposure_usd"]):
                raise SafetyError("gross_exposure_exceeded")
            exit_intent = next((i for i in entries if i["side"] == "sell"), None)
            if exit_intent is None:
                self.clock()
                positions = self.broker.positions()
                if (len(positions) != 1 or positions[0]["symbol"] != "SPY"
                        or number(positions[0]["qty"], maximum=Decimal(1)) != bought
                        or self.broker.open_orders()):
                    raise SafetyError("unexplained_position_or_order_difference")
                if not recover:
                    for _ in range(self.config["position_observation_seconds"]):
                        bid, _ = self.quote()
                        marked = bought * (bid - average)
                        self.journal.add("position_observation", gross_unrealized_pnl_usd=str(marked))
                        if self.kill_file.exists() or marked <= -number(self.config["max_realized_loss_usd"]):
                            break
                        self.gate.sleep(1)
                bid, _ = self.quote()
                floor = average - number(self.config["max_realized_loss_usd"]) / bought
                price = max(bid - number(self.config["limit_offset_usd"]), floor)
                price = price.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
                exit_intent = self.intent("sell", trial, bought, price)
                initial = self.submit_once(exit_intent)
            else:
                initial = self.find(exit_intent)
            filled_exit = self.settle(exit_intent, initial)
            if number(filled_exit["filled_qty"], zero=True) != bought:
                raise SafetyError("exit_incomplete_position_requires_attention")
        if self.broker.positions() or self.broker.open_orders():
            raise SafetyError("final_account_not_flat_and_idle")
        pnl = Decimal(0)
        if bought:
            pnl = bought * (number(self.orders["sell"]["filled_avg_price"]) - number(filled_entry["filled_avg_price"]))
            if pnl < -number(self.config["max_realized_loss_usd"]):
                raise SafetyError("realized_gross_loss_cap_exceeded")
        result = "passed" if bought == 1 else "inconclusive_no_full_round_trip"
        self.journal.add("completed", result=result, realized_gross_pnl_usd=str(pnl), finished_at=self.gate.now())
        return result

    def receipt(self, result, reason=None):
        writes = sum(e["event"] == "request" and e.get("write", False) for e in self.journal.events)
        completed = [e for e in self.journal.events if e["event"] == "completed"]
        return {"schema_version": 1, "evidence_kind": self.broker.evidence_kind,
                "paper_endpoint": PAPER_URL, "result": result, "reason": reason,
                "config": self.config, "write_attempts": writes,
                "orders": [{k: v for k, v in order.items() if k != "id"} for order in self.orders.values()],
                "quote_observations": self.quote_observations,
                "position_observations": [e for e in self.journal.events if e["event"] == "position_observation"],
                "final_flat_and_idle_observed": result in ("passed", "inconclusive_no_full_round_trip"),
                "realized_gross_pnl_usd": completed[-1]["realized_gross_pnl_usd"] if completed else None,
                "limitations": ["Operational trial, not strategy or profitability acceptance.",
                    "Gross realized loss bound excludes fees and unrealized gap loss.",
                    "Limit exits may remain unfilled; failure requires reconciliation, never blind retry.",
                    "Synthetic tests do not establish native broker failure behavior.",
                    "1000 trades/minute is not configured or qualified."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--recover", action="store_true")
    parser.add_argument("--trial", default="smoke-20260921")
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"[a-z0-9-]{1,30}", args.trial):
            raise SafetyError("invalid_trial_identity")
        config = load_config(args.config)
        key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
        if not key or not secret:
            raise SafetyError("paper_credentials_missing")
        gate = Gate(config)
        broker = Alpaca(key, secret, gate)
        account = broker.account()  # Read-only identity lookup before writer lock.
        with account_lock(account["id"]) as fingerprint:
            root = Path.home() / ".local/state/native-agent-stack/alpaca-paper"
            journal = Journal(root / fingerprint / "journal.jsonl")
            try:
                gate.attach(journal)
                runner = Runner(broker, config, journal, gate, root / "STOP")
                try:
                    if not args.recover:
                        runner.preflight(account)
                    if args.execute or args.recover:
                        result = runner.lifecycle(args.trial, args.recover)
                    else:
                        result = "preflight_passed_no_orders"
                    receipt = runner.receipt(result)
                except Exception as error:
                    reason = str(error) if isinstance(error, SafetyError) else "broker_or_schema_failure"
                    journal.add("failed", reason=reason, at=gate.now())
                    receipt = runner.receipt("needs_attention", reason)
                print(json.dumps(receipt, sort_keys=True, allow_nan=False))
                return 0 if receipt["result"] in ("passed", "preflight_passed_no_orders") else 2
            finally:
                journal.close()
    except Exception as error:
        reason = str(error) if isinstance(error, SafetyError) else "broker_or_schema_failure"
        print(json.dumps({"result": "needs_attention", "reason": reason}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
