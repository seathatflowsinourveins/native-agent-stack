"""Bounded IBKR paper order acceptance on NautilusTrader 1.231.0's own IB execution engine.

Subcommands:
  check  Official-ibapi read-only check: paper port, every managed account starts
         with "DU", zero positions, zero open orders. The account id stays in memory.
  run    The predeclared order run (plan.json cases C1-C4) through a Nautilus
         TradingNode with the Python InteractiveBrokers data/execution clients,
         bracketed by an in-process 'check' before and an independent flat proof after.

Heavy modules (nautilus_trader, ibapi) are imported lazily inside functions so the
pure logic (plan validation, prices, budget, session window, redaction, status)
imports and tests with a plain interpreter. Nothing here connects at import time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import signal
import threading
import time
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
PLAN_PATH = HERE / "plan.json"
# Predeclared plans only: the regular-session plan and its after-hours variant.
PLAN_NAMES = ("plan.json", "plan-post.json")
SESSIONS = {("09:30", "16:00"): "regular", ("16:00", "20:00"): "after_hours"}
HARNESS_PATH = Path(__file__).resolve()
# The gate's flip receipt; this harness never writes there.
GATE_RECEIPT = HERE.parent / "ibkr-acceptance" / "receipt.json"
RECEIPT_KIND = "ibkr_paper_orders_nautilus_1_231"
SCHEMA_VERSION = 1
CASE_IDS = ("C1", "C2", "C3", "C4")
CASE_NAMES = {"C1": "accept_resting", "C2": "cancel_resting", "C3": "fill_buy", "C4": "flatten"}
CASE_EXPECT = {"C1": "OrderAccepted", "C2": "OrderCanceled", "C3": "OrderFilled", "C4": "OrderFilled+flat"}
CENT = Decimal("0.01")

# IBKR account ids: paper DU/DF, live U/F, and I for some institutional forms.
ACCOUNT_ID = re.compile(r"\b(?:D?[UF]|I)\d{5,}\b")
IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b")
ABS_PATH = re.compile(r"(?:[A-Za-z]:\\|/)(?:[\w.-]+[/\\])+[\w.-]*")
HOME_PATH = re.compile(r"/(?:home|Users)/[^\s\"']+")
# Account values in IB rejection text, e.g. "EQUITY WITH LOAN VALUE [1234.56 USD]" or
# "Available Funds: 1,234.56". Applied to free text only (never to recorded prices).
_NUM = r"[-+]?\d[\d,]*(?:\.\d+)?"
_CCY = r"(?:USD|EUR|GBP|CHF|JPY|CAD|AUD|HKD)"
BRACKETED_AMOUNT = re.compile(rf"\[\s*{_NUM}\s*(?:{_CCY})?\s*\]")
CURRENCY_AMOUNT = re.compile(rf"(?:\b{_CCY}\s*{_NUM}|(?<![\w.]){_NUM}\s*{_CCY}\b)")
LABELLED_AMOUNT = re.compile(
    r"(?i)(\b(?:equity|loan value|margin|funds|cash|balance|buying power|net ?liq\w*|excess liquidity|"
    r"available|commission|value)\b[^\d\[\n]{0,40}?)" + _NUM)
# Informational IB codes (farm status, market-data notices); not failures.
INFO_CODES = {2100, 2104, 2106, 2107, 2108, 2119, 2158, 10089, 10167}

EXIT_BY_STATUS = {"passed": 0, "failed": 1, "incomplete": 1, "not_connected": 2, "cleanup_required": 3}


class PlanError(ValueError):
    pass


class BudgetError(RuntimeError):
    pass


# --------------------------------------------------------------------------- redaction


def redact_amounts(text: str) -> str:
    """Remove account values (balances, equity, margin, funds) from free text."""
    text = BRACKETED_AMOUNT.sub("[<amount>]", text)
    text = CURRENCY_AMOUNT.sub("<amount>", text)
    return LABELLED_AMOUNT.sub(lambda m: m.group(1) + "<amount>", text)


def redact(text) -> str:
    """Strip account ids, IPv4 endpoints, absolute paths and account amounts from free text."""
    text = str(text if text is not None else "")
    text = ABS_PATH.sub("<path>", IPV4.sub("<ip>", ACCOUNT_ID.sub("<account-id>", text)))
    return redact_amounts(text)


def scrub_serialized(text: str, secret_values=()) -> str:
    """Final pass over the whole serialized receipt: remove any in-memory secret
    (the account id), id-shaped tokens and home paths. Relative repository paths
    are kept, so the absolute-path rule is applied to error text only (redact)."""
    for value in secret_values:
        if value:
            text = text.replace(str(value), "<account-id>")
    return HOME_PATH.sub("<path>", ACCOUNT_ID.sub("<account-id>", text))


def exit_code_for(status: str) -> int:
    if status.startswith("refused_"):
        return 3
    return EXIT_BY_STATUS.get(status, 1)


def is_gate_receipt(path) -> bool:
    return Path(path).resolve() == GATE_RECEIPT.resolve()


# --------------------------------------------------------------------------- plan


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_plan(path=PLAN_PATH) -> dict:
    return json.loads(Path(path).read_text())


def validate_plan(plan: dict) -> list[str]:
    """Return every violation of the frozen bounds; empty means valid."""
    errors: list[str] = []

    def need(cond, msg):
        if not cond:
            errors.append(msg)

    try:
        need(plan.get("schema_version") == 1, "schema_version must be 1")
        need(plan.get("host") == "127.0.0.1", "host must be 127.0.0.1")
        ports = plan.get("paper_ports") or []
        need(bool(ports) and set(ports) <= {4002, 7497}, "paper_ports must be a non-empty subset of {4002, 7497}")
        need(plan.get("account_prefix") == "DU", "account_prefix must be DU")
        ids = plan["client_ids"]
        node, check = ids["node"], ids["check"]
        need(node == 91 and check == 92, "client ids must be node 91 and check 92")
        need(node != check, "node and check client ids must differ")
        need(not {node, check} & set(ids.get("reserved_elsewhere", [])), "client ids collide with reserved ids")
        inst = plan["instrument"]
        need((inst["symbol"], inst["sec_type"], inst["exchange"], inst["primary_exchange"], inst["currency"])
             == ("SPY", "STK", "SMART", "ARCA", "USD"), "instrument must be SPY STK SMART/ARCA USD")
        b = plan["bounds"]
        need(isinstance(b["max_orders"], int) and 3 <= b["max_orders"] <= 6, "max_orders must be 3..6")
        need(b["max_quantity_per_order"] == 1, "max_quantity_per_order must be 1")
        need(0 < b["max_notional_per_order_usd"] <= 1000, "max_notional_per_order_usd must be in (0, 1000]")
        need(0 < b["max_roundtrip_loss_usd"] <= 5, "max_roundtrip_loss_usd must be in (0, 5]")
        need(0 < b["marketable_offset_usd"] <= 0.10, "marketable_offset_usd must be in (0, 0.10]")
        need(0 < b["resting_fraction_of_bid"] <= 0.5, "resting_fraction_of_bid must be in (0, 0.5]")
        need(b["resting_price_floor_usd"] >= 0.01, "resting_price_floor_usd must be >= 0.01")
        need(b["commission_allowance_per_order_usd"] >= 0, "commission allowance must be >= 0")
        need(2 * b["commission_allowance_per_order_usd"] + 2 * b["marketable_offset_usd"] < b["max_roundtrip_loss_usd"],
             "commission allowance and offsets leave no round-trip loss budget")
        need(b.get("time_in_force") == "DAY" and b.get("order_type") == "LIMIT", "orders must be DAY LIMIT")
        rate_n, rate_iv = submit_rate_parts(b["max_order_submit_rate"])
        spacing = b["min_submit_spacing_seconds"]
        need(spacing >= 1.2, "min_submit_spacing_seconds must be >= 1.2")
        # The risk-engine throttle must never bind at the harness's own spacing.
        need(rate_n / rate_iv >= 2.0 / spacing and rate_n >= 2, "max_order_submit_rate would throttle the harness's spacing")
        need(isinstance(b["max_cancel_attempts_per_order"], int) and 2 <= b["max_cancel_attempts_per_order"] <= 5,
             "max_cancel_attempts_per_order must be 2..5")
        s = plan["session"]
        need(s["timezone"] == "America/New_York", "session timezone must be America/New_York")
        kind = SESSIONS.get((s["open"], s["close"]))
        need(kind is not None, "session must be 09:30-16:00 (regular) or 16:00-20:00 (after hours)")
        # IB rejects or holds an order outside regular hours unless it carries outsideRth.
        need(s.get("outside_rth", False) is (kind == "after_hours"),
             "outside_rth must be true exactly for the after-hours session")
        need(s.get("contract_hours_field", "liquidHours") == ("tradingHours" if kind == "after_hours" else "liquidHours"),
             "the after-hours session reads the contract's tradingHours; the regular session its liquidHours")
        need(kind != "after_hours" or s.get("use_contract_liquid_hours") is True,
             "the after-hours session must check today's contract hours")
        need(s["close_buffer_minutes"] >= 10, "close_buffer_minutes must be >= 10")
        d = plan["data"]
        need(0 < d["quote_max_age_seconds"] <= 10, "quote_max_age_seconds must be in (0, 10]")
        need(0 <= d["clock_resolution_tolerance_seconds"] <= 2, "clock tolerance must be in [0, 2]")
        t = plan["timeouts"]
        need(t["node_start_seconds"] == 60, "node_start_seconds must be 60")
        need(t["per_step_seconds"] == 45, "per_step_seconds must be 45")
        need(t["overall_deadline_seconds"] == 420, "overall_deadline_seconds must be 420")
        need(t["post_check_attempts"] >= 1, "post_check_attempts must be >= 1")
        need(t["check_seconds"] + t["node_start_seconds"] + t["per_step_seconds"] + t["cleanup_seconds"]
             + t["node_stop_allowance_seconds"] + t["post_check_reserve_seconds"] <= t["overall_deadline_seconds"],
             "timeouts do not fit inside overall_deadline_seconds")
        need(t["post_check_reserve_seconds"] >= t["check_seconds"], "post-check reserve must cover one full check")
        need(t["flatten_retry_delay_seconds"] >= 1.5, "flatten_retry_delay_seconds must be >= 1.5")
        need(0 < t["recancel_interval_seconds"] <= t["cleanup_seconds"] / 3, "recancel_interval_seconds must fit 3x in cleanup")
        need(3 <= t["post_stop_cancel_grace_seconds"] and t["post_stop_cancel_grace_seconds"] + 10
             <= t["node_stop_allowance_seconds"], "post_stop_cancel_grace_seconds + 10 s disconnect must fit the stop allowance")
        x = plan["exec_engine"]
        need(x["inflight_check_threshold_ms"] * x["inflight_check_retries"] / 1000 > t["overall_deadline_seconds"],
             "exec_engine in-flight resolution (threshold x retries) must lie beyond overall_deadline_seconds")
        need(x["inflight_check_interval_ms"] > 0, "inflight_check_interval_ms must stay > 0 (venue queries still run)")
        need([c["id"] for c in plan["cases"]] == list(CASE_IDS), "cases must be exactly C1..C4 in order")
        need([c["name"] for c in plan["cases"]] == [CASE_NAMES[c] for c in CASE_IDS], "case names do not match")
        e = plan["end_disposition"]
        need(e["positions"] == 0 and e["open_orders"] == 0, "end disposition must be flat with zero open orders")
        need(plan["receipt"]["kind"] == RECEIPT_KIND, "receipt kind mismatch")
        need(plan.get("evidence_class") == "native_paper", "evidence_class must be native_paper")
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"plan field missing or malformed: {exc!r}")
    return errors


# --------------------------------------------------------------------------- prices


def _dec(x) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def floor_cent(x) -> Decimal:
    return _dec(x).quantize(CENT, rounding=ROUND_FLOOR)


def ceil_cent(x) -> Decimal:
    return _dec(x).quantize(CENT, rounding=ROUND_CEILING)


def resting_buy_price(bid, fraction=0.5, floor=1.0) -> Decimal:
    """C1: non-marketable BUY at max(floor, floor_to_cent(fraction * bid))."""
    if _dec(bid) <= 0:
        raise ValueError("bid must be positive")
    return max(_dec(floor).quantize(CENT), floor_cent(_dec(bid) * _dec(fraction)))


def marketable_buy_price(ask, qty, max_notional, offset=0.05) -> Decimal | None:
    """C3: ceil_to_cent(ask + offset), capped so price * qty <= max_notional.
    Returns None when the cap falls below the ask (the order would not be marketable)."""
    ask, qty = _dec(ask), _dec(qty)
    if ask <= 0 or qty <= 0:
        raise ValueError("ask and qty must be positive")
    price = min(ceil_cent(ask + _dec(offset)), floor_cent(_dec(max_notional) / qty))
    return None if price < ask else price


def marketable_sell_price(bid, offset=0.05) -> Decimal:
    """C4 and cleanup flatten: max(0.01, floor_to_cent(bid - offset))."""
    if _dec(bid) <= 0:
        raise ValueError("bid must be positive")
    return max(CENT, floor_cent(_dec(bid) - _dec(offset)))


def worst_case_roundtrip_loss(buy_price, bid, qty, offset, commission_allowance) -> Decimal:
    """Upper estimate before C3: buy at the limit, sell at the flatten limit from the
    current bid, plus two commission allowances."""
    sell = marketable_sell_price(bid, offset)
    return (_dec(buy_price) - sell) * _dec(qty) + 2 * _dec(commission_allowance)


def quote_age_seconds(local_now_s: float, server_minus_local_s: float, ts_event_s: float) -> float:
    return round(local_now_s + (server_minus_local_s or 0.0) - ts_event_s, 3)


def quote_is_fresh(age_s, max_age_s, tolerance_s) -> bool:
    return age_s is not None and -tolerance_s <= age_s <= max_age_s


def quote_is_valid(bid, ask) -> bool:
    return bid is not None and ask is not None and _dec(bid) > 0 and _dec(ask) > 0 and _dec(ask) >= _dec(bid)


class OrderBudget:
    """Hard cap on orders created by this run, checked before every factory call."""

    def __init__(self, max_orders: int, max_quantity: int, max_notional=None):
        self.max_orders = int(max_orders)
        self.max_quantity = _dec(max_quantity)
        self.max_notional = None if max_notional is None else _dec(max_notional)
        self.used = 0
        self.reservations: list[dict] = []

    @property
    def remaining(self) -> int:
        return self.max_orders - self.used

    def reserve(self, case: str, qty, price=None) -> int:
        """Reserve one order. Every order path (entries, the flatten and cleanup sells)
        passes its limit price, so max_notional_per_order_usd binds all of them."""
        qty = _dec(qty)
        if qty <= 0 or qty > self.max_quantity:
            raise BudgetError(f"quantity {qty} outside (0, {self.max_quantity}]")
        if self.max_notional is not None:
            if price is None:
                raise BudgetError("limit price required to check max_notional_per_order_usd")
            if _dec(price) * qty > self.max_notional:
                raise BudgetError(f"notional {_dec(price) * qty} above max_notional_per_order_usd {self.max_notional}")
        if self.used >= self.max_orders:
            raise BudgetError(f"max_orders {self.max_orders} reached")
        self.used += 1
        self.reservations.append({"n": self.used, "case": case, "qty": str(qty)})
        return self.used


def submit_rate_parts(rate: str) -> tuple[int, float]:
    """Parse a Nautilus rate 'N/HH:MM:SS' into (N, interval seconds)."""
    n, iv = rate.split("/")
    h, m, sec = iv.split(":")
    seconds = int(h) * 3600 + int(m) * 60 + float(sec)
    if int(n) <= 0 or seconds <= 0:
        raise ValueError(f"bad rate {rate!r}")
    return int(n), seconds


def spacing_ok(now_ns: int, last_submit_ns, spacing_s: float) -> bool:
    return last_submit_ns is None or now_ns - last_submit_ns >= int(spacing_s * 1e9)


def cancel_decision(pending_cancel: bool, attempts: int, last_sent_ns, now_ns: int, interval_s: float,
                    max_attempts: int, force: bool = False) -> str:
    """What to do for one open order of this run: 'cancel' (Strategy.cancel_order),
    'cancel_all' (Strategy.cancel_all_orders; the only path that re-sends a cancel for
    an order stuck in PENDING_CANCEL, since cancel_order refuses those), 'wait' or
    'exhausted'. ``force`` (finish and on_stop) always sends, whatever the count."""
    action = "cancel_all" if pending_cancel else "cancel"
    if force or attempts <= 0:
        return action
    if attempts >= max_attempts:
        return "exhausted"
    if last_sent_ns is not None and now_ns - last_sent_ns < int(interval_s * 1e9):
        return "wait"
    return action


# --------------------------------------------------------------------------- session window


def _hm(text: str) -> tuple[int, int]:
    h, m = text.split(":")
    return int(h), int(m)


# IB reports legacy zone names; some hosts ship them only in a separate legacy tzdata package.
TZ_ALIASES = {"US/Eastern": "America/New_York", "EST5EDT": "America/New_York", "EST": "America/New_York",
              "US/Central": "America/Chicago", "US/Pacific": "America/Los_Angeles"}


def resolve_zone(tz_name: str, fallback: str = "America/New_York") -> ZoneInfo:
    for name in (TZ_ALIASES.get(tz_name, tz_name), fallback):
        try:
            return ZoneInfo(name)
        except Exception:  # noqa: BLE001
            continue
    raise ValueError(f"no usable time zone for {tz_name!r}")


LIQUID_STAMP = re.compile(r"\d{8}:\d{4}")


def parse_liquid_hours(text: str, tz_name: str, day: date):
    """Parse IB ContractDetails.liquidHours for ``day``.

    Returns a list of (start, end) aware datetimes (empty when IB marks the day
    CLOSED) or None when the day is absent or any segment naming the day is
    unparseable. Segments for other days that do not parse are skipped, so one
    malformed future day cannot hide today's hours. Format examples:
    "20260923:0930-20260923:1600;20260926:CLOSED" and the older same-day form
    "20260923:0930-1600"."""
    if not text:
        return None
    try:
        tz = resolve_zone(tz_name)
    except ValueError:
        return None
    key = day.strftime("%Y%m%d")
    sessions, seen = [], False
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        if part.endswith(":CLOSED"):
            if part.split(":")[0] == key:
                seen = True
            continue
        try:
            start_s, end_s = part.split("-")
            if ":" not in end_s:  # older form: the end time shares the start date
                end_s = f"{start_s.split(':')[0]}:{end_s}"
            # strptime alone accepts truncated fields ("20260923:16" parses as 01:06).
            if not (LIQUID_STAMP.fullmatch(start_s) and LIQUID_STAMP.fullmatch(end_s)):
                raise ValueError(part)
            start = datetime.strptime(start_s, "%Y%m%d:%H%M").replace(tzinfo=tz)
            end = datetime.strptime(end_s, "%Y%m%d:%H%M").replace(tzinfo=tz)
        except ValueError:
            if key in part:
                return None  # today's segment is broken: unknown hours, never assume the fixed window
            continue
        if start.date() == day or end.date() == day:
            seen = True
            sessions.append((start, end))
    return sessions if seen else None


def session_window(now_utc: datetime, plan: dict, liquid_sessions=None):
    """Return (open_utc, last_end_utc) for today's run window, or None when closed.
    last_end is close minus the buffer; liquid sessions (when known) narrow it."""
    s = plan["session"]
    tz = ZoneInfo(s["timezone"])
    local = now_utc.astimezone(tz)
    if s.get("weekdays_only", True) and local.weekday() >= 5:
        return None
    oh, om = _hm(s["open"])
    ch, cm = _hm(s["close"])
    open_l = local.replace(hour=oh, minute=om, second=0, microsecond=0)
    close_l = local.replace(hour=ch, minute=cm, second=0, microsecond=0)
    if liquid_sessions is not None:
        if not liquid_sessions:
            return None
        covering = [(a, b) for a, b in liquid_sessions if a <= now_utc <= b] or liquid_sessions
        a, b = covering[0]
        open_l, close_l = max(open_l, a.astimezone(tz)), min(close_l, b.astimezone(tz))
    last_end = close_l - timedelta(minutes=s["close_buffer_minutes"])
    if last_end <= open_l:
        return None
    return open_l.astimezone(timezone.utc), last_end.astimezone(timezone.utc)


def rth_check(now_utc: datetime, plan: dict, liquid_sessions=None, horizon_s=None) -> tuple[bool, str]:
    """The whole run [now, now + horizon] must sit inside [open, close - buffer]."""
    horizon = plan["timeouts"]["overall_deadline_seconds"] if horizon_s is None else horizon_s
    window = session_window(now_utc, plan, liquid_sessions)
    if window is None:
        return False, "market_closed_today"
    open_utc, last_end = window
    if now_utc < open_utc:
        return False, "before_open"
    if now_utc + timedelta(seconds=horizon) > last_end:
        return False, "too_close_to_close"
    return True, "inside_window"


# --------------------------------------------------------------------------- official ibapi check


CHECK_REQUESTS = ("accounts", "time", "positions", "orders", "contract")


class CheckState:
    """ibapi callback handlers kept free of ibapi so they test offline; mixed into
    EWrapper/EClient by ``build_check_client``. Read-only: no order method exists here."""

    def __init__(self):
        self.done = {k: threading.Event() for k in CHECK_REQUESTS}
        self._accounts: list[str] = []  # memory only; never serialized
        self._order_keys: set = set()
        self.r = {"account_count": 0, "paper_accounts": None, "server_time_epoch": None, "positions": 0,
                  "spy_position": False, "open_orders": 0, "open_order_statuses": [], "contract": None,
                  "errors": [], "info": []}
        self._liquid_hours = ""
        self._trading_hours = ""
        self._time_zone_id = ""

    def managedAccounts(self, accountsList):
        ids = [a.strip() for a in (accountsList or "").split(",") if a.strip()]
        for a in ids:
            if a not in self._accounts:
                self._accounts.append(a)
        paper = bool(ids) and all(a.startswith("DU") for a in ids)
        self.r["account_count"] = len(self._accounts)
        # Latched: once any callback reports a non-paper account the check stays refused.
        self.r["paper_accounts"] = paper and self.r["paper_accounts"] is not False
        self.done["accounts"].set()

    def currentTime(self, t):
        self.r["server_time_epoch"] = t
        self.done["time"].set()

    def position(self, account, contract, pos, avgCost):
        if pos:
            self.r["positions"] += 1
            if getattr(contract, "symbol", None) == "SPY":
                self.r["spy_position"] = True

    def positionEnd(self):
        self.done["positions"].set()

    def openOrder(self, orderId, contract, order, orderState):
        key = getattr(order, "permId", 0) or ("order", orderId)
        if key in self._order_keys:
            return
        self._order_keys.add(key)
        self.r["open_orders"] += 1
        self.r["open_order_statuses"].append(str(getattr(orderState, "status", "")))

    def openOrderEnd(self):
        self.done["orders"].set()

    def contractDetails(self, reqId, d):
        c = d.contract
        self._liquid_hours = d.liquidHours or ""
        self._trading_hours = getattr(d, "tradingHours", "") or ""
        self._time_zone_id = d.timeZoneId or ""
        self.r["contract"] = {"secType": c.secType, "currency": c.currency, "exchange": c.exchange,
                              "primaryExchange": c.primaryExchange, "minTick": d.minTick,
                              "timeZoneId": self._time_zone_id}

    def contractDetailsEnd(self, reqId):
        self.done["contract"].set()

    def error(self, reqId, errorTime, errorCode, errorString, advancedOrderRejectJson=""):
        # ibapi 10.45 signature: (reqId, errorTime, errorCode, errorString, advancedOrderRejectJson)
        entry = {"reqId": reqId, "code": errorCode, "text": redact(errorString)[:160]}
        (self.r["info"] if errorCode in INFO_CODES else self.r["errors"]).append(entry)

    def completed(self) -> dict:
        return {k: v.is_set() for k, v in self.done.items()}

    def single_account(self) -> str | None:
        return self._accounts[0] if len(self._accounts) == 1 else None


def check_verdict(r: dict, completed: dict, required=CHECK_REQUESTS, require_single=True) -> str:
    if r["paper_accounts"] is not True:
        return "refused_not_paper_account"
    if require_single and r["account_count"] != 1:
        return "refused_account_scope"
    if not all(completed.get(k) for k in required):
        return "incomplete"
    if r["positions"] or r["open_orders"]:
        return "refused_existing_state"
    return "passed"


def build_check_client():
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper

    class CheckClient(CheckState, EWrapper, EClient):
        def __init__(self):
            CheckState.__init__(self)
            EClient.__init__(self, self)

    return CheckClient()


def spy_contract():
    from ibapi.contract import Contract

    c = Contract()
    c.symbol, c.secType, c.exchange, c.primaryExchange, c.currency = "SPY", "STK", "SMART", "ARCA", "USD"
    return c


def run_check(plan: dict, port: int, *, with_session: bool, client_factory=None, contract_factory=None,
              deadline_s: float | None = None):
    """Official-ibapi read-only check. Returns (result, account_id); the account id
    is returned in memory only and only when the verdict is passed."""
    t = plan["timeouts"]
    budget_s = t["check_seconds"] if deadline_s is None else min(deadline_s, t["check_seconds"])
    host, client_id = plan["host"], plan["client_ids"]["check"]
    result = {"client": "ibapi", "client_id": client_id, "port": port, "status": None}
    if port not in plan["paper_ports"]:
        result["status"] = "refused_not_paper_port"
        return result, None
    p = (client_factory or build_check_client)()
    deadline = time.monotonic() + budget_s

    def wait(key, seconds):
        return p.done[key].wait(max(0.0, min(seconds, deadline - time.monotonic())))

    try:
        try:
            p.connect(host, port, client_id)
        except OSError as exc:
            p.r["errors"].append({"reqId": -1, "code": None, "text": redact(f"{type(exc).__name__}: {exc}")[:160]})
        if p.isConnected():
            threading.Thread(target=p.run, daemon=True).start()
        if not p.isConnected() or not wait("accounts", 10):
            result.update(status="not_connected", observed=p.r)
            return result, None
        steps = [("time", 5, p.reqCurrentTime, None),
                 ("positions", 10, p.reqPositions, p.cancelPositions),
                 ("orders", 10, p.reqAllOpenOrders, None)]
        if with_session:
            steps.append(("contract", 10, lambda: p.reqContractDetails(9201, (contract_factory or spy_contract)()), None))
        for key, seconds, request, after in steps:
            if p.r["paper_accounts"] is not True:  # checked before every request
                break
            started = time.time()
            request()
            wait(key, seconds)
            if after:
                after()
            if key == "time" and p.r["server_time_epoch"]:
                p.r["server_minus_local_s"] = round(p.r["server_time_epoch"] - (started + time.time()) / 2, 3)
        required = tuple(k for k, *_ in [("accounts",)] + steps)
        status = check_verdict(p.r, p.completed(), required=required)
        result.update(status=status, observed=p.r, requests_completed=p.completed())
        if with_session and (p._liquid_hours or p._trading_hours):
            # Kept whole (IB lists about a month of days); never written to a receipt.
            result["liquid_hours"] = p._liquid_hours
            result["trading_hours"] = p._trading_hours
            result["time_zone_id"] = p._time_zone_id
        return result, (p.single_account() if status == "passed" else None)
    finally:
        try:
            p.disconnect()
        except Exception:
            pass


# --------------------------------------------------------------------------- run bookkeeping (pure)


def ns_to_iso(ns) -> str | None:
    if not ns:
        return None
    return datetime.fromtimestamp(int(ns) / 1e9, tz=timezone.utc).isoformat()


def new_run_prefix(now_utc: datetime) -> str:
    return f"NTP-{now_utc:%m%d-%H%M%S}-{secrets.token_hex(3)}"


class RunContext:
    """Case state, events, fills and budget for one run. Pure Python; the Nautilus
    strategy calls into it and the receipt is built from it."""

    def __init__(self, plan: dict, prefix: str, server_minus_local_s: float = 0.0):
        self.plan = plan
        self.prefix = prefix
        self.server_minus_local_s = server_minus_local_s or 0.0
        b = plan["bounds"]
        self.budget = OrderBudget(b["max_orders"], b["max_quantity_per_order"], b["max_notional_per_order_usd"])
        # Set by cmd_run once the provisional receipt exists: rewrites it after every state
        # change, so a kill mid-run leaves the orders, events and fills on disk.
        self.on_change = None
        self.cases = {cid: {"id": cid, "name": CASE_NAMES[cid], "expect": CASE_EXPECT[cid], "outcome": "not_run",
                            "reason": None, "started_at": None, "ended_at": None, "orders": [], "events": []}
                      for cid in CASE_IDS}
        self.order_case: dict[str, str] = {}
        self.fills: list[dict] = []
        self.net_qty = Decimal(0)
        self.current: str | None = None
        self.started = False
        self.finished = False
        self.cleanup: dict | None = None
        self.cleanup_orders: list[dict] = []
        self.cleanup_events: list[dict] = []
        self.position_opened: dict | None = None
        self.position_closed: dict | None = None
        self.roundtrip: dict | None = None
        self.notes: list[str] = []
        self.errors: list[str] = []
        # Terminal events the execution engine produced itself (reconciliation=True), not IB.
        self.unconfirmed: list[dict] = []
        self.duplicates: list[dict] = []
        self.cancel_requests: list[dict] = []
        self.node: dict = {"built": False, "strategy_started": False, "stop_requested_by": None}

    # -- cases
    def changed(self):
        """Persist the current state through on_change; a write failure is recorded, never raised."""
        if self.on_change is None:
            return
        try:
            self.on_change()
        except Exception as exc:  # noqa: BLE001 - persistence must never interrupt trading
            if len(self.errors) < 20:
                self.errors.append(redact(f"provisional receipt write failed: {type(exc).__name__}")[:200])

    def begin(self, cid: str, now_ns: int):
        self.current = cid
        c = self.cases[cid]
        c["outcome"], c["started_at"] = "running", ns_to_iso(now_ns)
        self.changed()

    def pass_case(self, cid: str, now_ns: int, **fields):
        c = self.cases[cid]
        c.update(fields)
        c["outcome"], c["ended_at"] = "passed", ns_to_iso(now_ns)
        self.changed()

    def end_case(self, cid: str, outcome: str, reason: str, now_ns: int):
        c = self.cases[cid]
        if c["outcome"] in ("passed", "failed", "incomplete"):
            return
        c["outcome"], c["reason"], c["ended_at"] = outcome, redact(reason)[:200], ns_to_iso(now_ns)
        self.changed()

    def all_passed(self) -> bool:
        return all(self.cases[c]["outcome"] == "passed" for c in CASE_IDS)

    # -- orders and events
    def client_order_id(self, suffix: str) -> str:
        return f"{self.prefix}-{suffix}"

    def register_order(self, client_order_id: str, case: str, side: str, qty, price, submit_n: int, now_ns: int):
        self.order_case[client_order_id] = case
        rec = {"client_order_id": client_order_id, "side": side, "quantity": str(qty), "limit_price": str(price),
               "notional_usd": str(_dec(price) * _dec(qty)), "time_in_force": "DAY", "order_number": submit_n,
               "created_at": ns_to_iso(now_ns)}
        (self.cleanup_orders if case == "cleanup" else self.cases[case]["orders"]).append(rec)
        self.changed()
        return rec

    def case_for(self, client_order_id: str) -> str | None:
        return self.order_case.get(client_order_id)

    def record_event(self, client_order_id: str, event_type: str, ts_event_ns, ts_init_ns=None, **extra):
        case = self.case_for(client_order_id)
        if case is None:
            return None
        # Events of the C1 order after C1 passed (pending cancel, canceled, a duplicate
        # cancel report) are C2's evidence.
        c1_after = self.current == "C2" or self.cases["C2"]["outcome"] != "not_run"
        target = "C2" if case == "C1" and c1_after else case
        entry = {"type": event_type, "client_order_id": client_order_id, "ts_event": ns_to_iso(ts_event_ns),
                 "ts_init": ns_to_iso(ts_init_ns)}
        entry.update({k: (redact(v)[:200] if isinstance(v, str) else v) for k, v in extra.items()})
        (self.cleanup_events if case == "cleanup" else self.cases[target]["events"]).append(entry)
        self.changed()
        return case

    def add_fill(self, case: str, client_order_id: str, side: str, price, qty, commission, currency, ts_event_ns):
        signed = _dec(qty) if side == "BUY" else -_dec(qty)
        self.net_qty += signed
        fill = {"case": case, "client_order_id": client_order_id, "side": side, "price": str(price),
                "quantity": str(qty), "commission": None if commission is None else str(commission),
                "commission_currency": currency, "ts_event": ns_to_iso(ts_event_ns)}
        if commission is not None and _dec(commission) == 0:
            # The 1.231.0 adapter maps an unset/-1 IB commission to 0 before OrderFilled.
            fill["commission_zero_note"] = "zero may mean IB had not reported the commission"
        self.fills.append(fill)
        self.changed()
        return fill

    def commission_unresolved(self) -> bool:
        """A fill without a commission, or with the zero the 1.231.0 adapter substitutes for
        an unreported IB commission, leaves the net P&L and the loss bound unproven."""
        return any(f["commission"] is None or "commission_zero_note" in f for f in self.fills)

    def compute_roundtrip(self, nautilus_realized=None, nautilus_currency=None) -> dict:
        buys = [f for f in self.fills if f["side"] == "BUY"]
        sells = [f for f in self.fills if f["side"] == "SELL"]
        bought = sum((_dec(f["price"]) * _dec(f["quantity"]) for f in buys), Decimal(0))
        sold = sum((_dec(f["price"]) * _dec(f["quantity"]) for f in sells), Decimal(0))
        commissions = sum((_dec(f["commission"]) for f in self.fills if f["commission"] is not None), Decimal(0))
        gross = sold - bought
        net = gross - commissions
        limit = _dec(self.plan["bounds"]["max_roundtrip_loss_usd"])
        self.roundtrip = {"gross_pnl_usd": str(gross), "commissions_usd": str(commissions), "net_pnl_usd": str(net),
                          "max_roundtrip_loss_usd": str(limit), "loss_bound_breached": -net > limit,
                          "commission_unresolved": self.commission_unresolved(),
                          "nautilus_realized_pnl": None if nautilus_realized is None else str(nautilus_realized),
                          "nautilus_realized_pnl_currency": nautilus_currency}
        return self.roundtrip

    def start_cleanup(self, reason: str, kind: str, now_ns: int):
        # A setup failure before C1 began is attributed to C1 (the first case not reached).
        self.end_case(self.current or CASE_IDS[0], kind, reason, now_ns)
        deadline = now_ns + int(self.plan["timeouts"]["cleanup_seconds"] * 1e9)
        self.cleanup = {"triggered": True, "reason": redact(reason)[:200], "kind": kind,
                        "started_at": ns_to_iso(now_ns), "deadline_ns": deadline, "cancels_requested": 0,
                        "flatten_orders": 0, "ended_at": None, "end_reason": None}
        self.changed()

    def summary(self) -> dict:
        cleanup = dict(self.cleanup) if self.cleanup else {"triggered": False}
        cleanup.pop("deadline_ns", None)
        if self.cleanup:
            cleanup.update(orders=self.cleanup_orders, events=self.cleanup_events)
        return {"run_prefix": self.prefix, "cases": [self.cases[c] for c in CASE_IDS], "fills": self.fills,
                "position": {"opened": self.position_opened, "closed": self.position_closed},
                "roundtrip": self.roundtrip, "orders_created": self.budget.used,
                "max_orders": self.budget.max_orders, "net_quantity_from_fills": str(self.net_qty),
                "cleanup": cleanup, "unconfirmed_events": self.unconfirmed, "duplicate_events": self.duplicates,
                "cancel_requests": self.cancel_requests,
                "node": self.node, "notes": self.notes, "errors": self.errors}


def final_status(ctx: RunContext | None, flat_proof: dict | None) -> str:
    if flat_proof is None or flat_proof.get("status") != "passed":
        return "cleanup_required"
    if (ctx is not None and ctx.all_passed() and not (ctx.roundtrip or {}).get("loss_bound_breached")
            and not ctx.commission_unresolved()):
        return "passed"
    if ctx is not None and any(ctx.cases[c]["outcome"] == "failed" for c in CASE_IDS):
        return "failed"
    return "incomplete"


# --------------------------------------------------------------------------- Nautilus strategy (lazy)


def build_strategy_class():
    """Define the order strategy against the installed NautilusTrader 1.231.0 API."""
    from nautilus_trader.model.enums import OrderSide, OrderStatus, TimeInForce, position_side_to_str
    from nautilus_trader.model.events import (OrderAccepted, OrderCanceled, OrderCancelRejected, OrderDenied,
                                              OrderExpired, OrderFilled, OrderRejected)
    from nautilus_trader.model.identifiers import ClientOrderId, InstrumentId
    from nautilus_trader.model.objects import Price
    from nautilus_trader.trading.strategy import Strategy
    from nautilus_trader.adapters.interactive_brokers.common import IBOrderTags

    TERMINAL_EVENTS = (OrderCanceled, OrderRejected, OrderDenied, OrderExpired)

    class PaperOrderStrategy(Strategy):
        def __init__(self, config, ctx: RunContext, request_stop):
            super().__init__(config)
            self.ctx = ctx
            self._request_stop = request_stop
            self._iid = InstrumentId.from_str(ctx.plan["instrument"]["nautilus_instrument_id"])
            self._quote = None  # (bid Decimal, ask Decimal, ts_event_ns)
            self._waiting_quote = False
            self._step_deadline_ns = 0
            self._orders = {}
            self._cancels = {}  # client_order_id -> {"attempts": int, "last_ns": int | None}
            self._exhausted = set()
            self._terminal = {}  # client_order_id -> first terminal event type processed
            self._unconfirmed = set()  # closed only by an engine-generated (reconciliation) event
            self._flatten_active = None  # (client_order_id str, submitted_ns)
            self._flatten_n = 0
            self._last_submit_ns = None
            self._last_sell_close_ns = None
            self._window_end = None
            self._in_cleanup = False

        # ---------------------------------------------------------- lifecycle
        def on_start(self):
            ctx = self.ctx
            if ctx.finished or ctx.cleanup:
                ctx.notes.append("strategy started after the run was stopped; no case started")
                return
            ctx.started = True
            ctx.node["strategy_started"] = True
            ctx.node["strategy_started_at"] = ns_to_iso(self.clock.timestamp_ns())
            try:
                instrument = self.cache.instrument(self._iid)
                if instrument is None:
                    self.abort("instrument_not_loaded", kind="failed")
                    return
                ctx.node["instrument"] = {"id": str(instrument.id), "price_increment": str(instrument.price_increment),
                                          "size_increment": str(instrument.size_increment),
                                          "quote_currency": str(instrument.quote_currency)}
                if instrument.price_increment != Price.from_str(ctx.plan["instrument"]["expected_price_increment"]):
                    self.abort("unexpected_price_increment", kind="failed")
                    return
                self.subscribe_quote_ticks(self._iid, params={"batch_quotes": False})
                self.clock.set_timer("ibpo-watchdog", timedelta(seconds=1), callback=self._on_watchdog)
                self._begin("C1")
            except Exception as exc:  # noqa: BLE001
                self._fault(exc)

        def on_stop(self):
            # Runs from Trader.stop() before the kernel waits timeout_post_stop and only then
            # disconnects the clients (system/kernel.py stop_async), so these cancels still
            # reach the adapter. Always swept, whatever ctx.finished says.
            ctx = self.ctx
            if not ctx.finished:
                ctx.notes.append("strategy stopped before the run finished")
            try:
                sent = self._sweep_cancels("on_stop", force=True)
                if sent:
                    ctx.notes.append(f"on_stop sent a final cancel for {sent} open order(s) of this run")
            except Exception as exc:  # noqa: BLE001
                ctx.errors.append(redact(f"on_stop cancel sweep: {type(exc).__name__}: {exc}")[:200])

        # ---------------------------------------------------------- helpers
        def _now(self) -> int:
            return self.clock.timestamp_ns()

        def _fault(self, exc):
            self.ctx.errors.append(redact(f"{type(exc).__name__}: {exc}")[:200])
            self.abort(f"exception_{type(exc).__name__}", kind="failed")

        def _fresh_quote(self):
            if self._quote is None:
                return None
            bid, ask, ts = self._quote
            d = self.ctx.plan["data"]
            # LiveClock is wall-clock time in a live node; the offset aligns it to the IB server clock.
            age = quote_age_seconds(self._now() / 1e9, self.ctx.server_minus_local_s, ts / 1e9)
            if not quote_is_valid(bid, ask) or not quote_is_fresh(age, d["quote_max_age_seconds"],
                                                                  d["clock_resolution_tolerance_seconds"]):
                return None
            return bid, ask, age

        def _inside_window(self) -> bool:
            return self._window_end is None or self.clock.utc_now() <= self._window_end

        def _begin(self, cid: str):
            self.ctx.begin(cid, self._now())
            self._step_deadline_ns = self._now() + int(self.ctx.plan["timeouts"]["per_step_seconds"] * 1e9)
            if cid == "C2":
                self._cancel_c1()
            else:
                self._waiting_quote = True
                self._try_step()

        # ---------------------------------------------------------- order creation (the only factory calls)
        def _order_tags(self):
            """IB order fields for every order: outsideRth exactly when the plan is the
            after-hours session (the execution client parses IBOrderTags:<json>)."""
            return [IBOrderTags(outsideRth=True).value] if self.ctx.plan["session"].get("outside_rth") else None

        def _new_c1_order(self, price, qty):
            return self.order_factory.limit(
                instrument_id=self._iid, order_side=OrderSide.BUY, quantity=qty, price=price,
                time_in_force=TimeInForce.DAY, client_order_id=ClientOrderId(self.ctx.client_order_id("C1")),
                tags=self._order_tags())

        def _new_c3_order(self, price, qty):
            return self.order_factory.limit(
                instrument_id=self._iid, order_side=OrderSide.BUY, quantity=qty, price=price,
                time_in_force=TimeInForce.DAY, client_order_id=ClientOrderId(self.ctx.client_order_id("C3")),
                tags=self._order_tags())

        def _new_flatten_order(self, price, qty, suffix):
            return self.order_factory.limit(
                instrument_id=self._iid, order_side=OrderSide.SELL, quantity=qty, price=price,
                time_in_force=TimeInForce.DAY, client_order_id=ClientOrderId(self.ctx.client_order_id(suffix)),
                tags=self._order_tags())

        def _submit(self, case, suffix, side, price_dec, qty_int):
            """Check spacing, reserve budget, create the order with its case's builder, then submit."""
            now = self._now()
            if not spacing_ok(now, self._last_submit_ns, self.ctx.plan["bounds"]["min_submit_spacing_seconds"]):
                raise BudgetError("min_submit_spacing_seconds not elapsed")  # callers wait; hard backstop only
            n = self.ctx.budget.reserve(case, qty_int, price_dec)  # raises BudgetError before any order exists
            instrument = self.cache.instrument(self._iid)
            price = instrument.make_price(float(price_dec))
            qty = instrument.make_qty(qty_int)
            if suffix == "C1":
                order = self._new_c1_order(price, qty)
            elif suffix == "C3":
                order = self._new_c3_order(price, qty)
            else:
                order = self._new_flatten_order(price, qty, suffix)
            cid = order.client_order_id.value
            self.ctx.register_order(cid, case, side, qty_int, price_dec, n, self._now())
            self._orders[cid] = order
            self._last_submit_ns = now
            self.submit_order(order)
            return cid

        def _spacing_ok(self) -> bool:
            return spacing_ok(self._now(), self._last_submit_ns, self.ctx.plan["bounds"]["min_submit_spacing_seconds"])

        # ---------------------------------------------------------- cancels (the only cancel call sites)
        def _send_cancel(self, order, where: str, action: str = "cancel"):
            """Record one cancel attempt; 'cancel' sends Strategy.cancel_order here, while
            'cancel_all' is sent once per sweep by _sweep_cancels."""
            key = order.client_order_id.value
            st = self._cancels.setdefault(key, {"attempts": 0, "last_ns": None})
            st["attempts"] += 1
            st["last_ns"] = self._now()
            self.ctx.cancel_requests.append({"client_order_id": key, "where": where, "action": action,
                                             "attempt": st["attempts"], "status": order.status_string(),
                                             "at": ns_to_iso(st["last_ns"])})
            if self.ctx.cleanup and where != "C2":
                self.ctx.cleanup["cancels_requested"] += 1
            self.ctx.changed()
            if action == "cancel":
                self.cancel_order(order)

        def _sweep_cancels(self, where: str, force: bool = False) -> int:
            """Cancel every open order of this run that IB has acknowledged. Re-sends are
            bounded (max_cancel_attempts_per_order, recancel_interval_seconds apart); an order
            stuck in PENDING_CANCEL is re-cancelled through cancel_all_orders, because
            Strategy.cancel_order refuses pending-cancel orders. ``force`` (finish, on_stop)
            sends one more cancel for every open order, including a flatten in its fill window."""
            ctx = self.ctx
            b, t = ctx.plan["bounds"], ctx.plan["timeouts"]
            now = self._now()
            flatten_wait_ns = int(t["flatten_fill_wait_seconds"] * 1e9)
            sent, need_all = 0, False
            for o in self._outstanding_orders():
                key = o.client_order_id.value
                if o.venue_order_id is None:
                    continue  # not yet acknowledged by IB: the adapter cannot resolve an IB order id
                in_window = self._flatten_active and key == self._flatten_active[0] \
                    and now - self._flatten_active[1] < flatten_wait_ns
                if in_window and not force:
                    continue  # give the flatten order its fill window
                st = self._cancels.get(key, {"attempts": 0, "last_ns": None})
                action = cancel_decision(o.is_pending_cancel, st["attempts"], st["last_ns"], now,
                                         t["recancel_interval_seconds"], b["max_cancel_attempts_per_order"], force=force)
                if action == "exhausted":
                    if key not in self._exhausted:
                        self._exhausted.add(key)
                        ctx.notes.append(f"cancel attempts exhausted for {key}; final cancel at finish")
                    continue
                if action == "wait":
                    continue
                self._send_cancel(o, where, action)
                sent += 1
                need_all = need_all or action == "cancel_all"
            if need_all:
                # The adapter's _cancel_all_orders cancels every open SPY.ARCA order in the cache.
                # Cleanup submits a flatten only once no other order of this run is outstanding,
                # so outside finish/on_stop this can only hit orders that are meant to be cancelled.
                self.cancel_all_orders(self._iid)
            return sent

        def _cancel_c1(self):
            order = self.cache.order(ClientOrderId(self.ctx.client_order_id("C1")))
            if order is None or not order.is_open:
                self.abort("c1_order_not_open_for_cancel", kind="failed")
                return
            self._send_cancel(order, "C2")

        # ---------------------------------------------------------- case steps
        def _try_step(self):
            ctx = self.ctx
            if ctx.cleanup or ctx.finished or not self._waiting_quote:
                return
            q = self._fresh_quote()
            if q is None:
                return
            if not self._inside_window():
                self.abort("session_window_closed", kind="incomplete")
                return
            if not self._spacing_ok():
                return  # min_submit_spacing_seconds; the watchdog and quote ticks retry
            bid, ask, age = q
            b = ctx.plan["bounds"]
            cid = ctx.current
            quote = {"bid": str(bid), "ask": str(ask), "age_s": age}
            try:
                if cid == "C1":
                    price = resting_buy_price(bid, b["resting_fraction_of_bid"], b["resting_price_floor_usd"])
                    if price * 1 > _dec(b["max_notional_per_order_usd"]) or price >= bid:
                        self.abort("c1_price_not_resting_within_notional", kind="failed")
                        return
                    self._waiting_quote = False
                    ctx.cases["C1"]["quote"] = quote
                    self._submit("C1", "C1", "BUY", price, 1)
                elif cid == "C3":
                    price = marketable_buy_price(ask, 1, b["max_notional_per_order_usd"], b["marketable_offset_usd"])
                    if price is None:
                        self.abort("c3_notional_cap_below_ask", kind="failed")
                        return
                    loss = worst_case_roundtrip_loss(price, bid, 1, b["marketable_offset_usd"],
                                                     b["commission_allowance_per_order_usd"])
                    quote["worst_case_roundtrip_loss_usd"] = str(loss)
                    if loss > _dec(b["max_roundtrip_loss_usd"]):
                        self.abort("c3_worst_case_roundtrip_loss_exceeds_bound", kind="failed")
                        return
                    self._waiting_quote = False
                    ctx.cases["C3"]["quote"] = quote
                    self._submit("C3", "C3", "BUY", price, 1)
                elif cid == "C4":
                    if not self.cache.positions_open(instrument_id=self._iid, strategy_id=self.id):
                        return  # wait for the C3 position to register
                    qty = int(ctx.net_qty)
                    if qty <= 0:
                        self.abort("c4_no_quantity_to_flatten", kind="failed")
                        return
                    price = marketable_sell_price(bid, b["marketable_offset_usd"])
                    self._waiting_quote = False
                    ctx.cases["C4"]["quote"] = quote
                    self._submit("C4", "C4", "SELL", price, qty)
            except BudgetError as exc:
                self.abort(f"budget: {exc}", kind="failed")

        def on_quote_tick(self, tick):
            try:
                self._quote = (Decimal(str(tick.bid_price)), Decimal(str(tick.ask_price)), tick.ts_event)
                if self._waiting_quote:
                    self._try_step()
                elif self.ctx.cleanup and not self.ctx.finished:
                    self._cleanup_tick()
            except Exception as exc:  # noqa: BLE001
                self._fault(exc)

        def on_order_event(self, event):
            try:
                self._handle_order_event(event)
            except Exception as exc:  # noqa: BLE001
                self._fault(exc)

        def _handle_order_event(self, event):
            ctx = self.ctx
            cid = event.client_order_id.value
            if ctx.case_for(cid) is None:
                return
            etype = type(event).__name__
            terminal = isinstance(event, TERMINAL_EVENTS)
            extra = {}
            if isinstance(event, (OrderRejected, OrderDenied, OrderCancelRejected)):
                extra["reason"] = str(event.reason)
            if isinstance(event, OrderAccepted):
                extra["venue_order_id_present"] = event.venue_order_id is not None
            if bool(getattr(event, "reconciliation", False)):
                extra["reconciliation"] = True
            # Engine-generated closes (live/execution_engine.py _resolve_inflight_order and the
            # reconciliation paths set reconciliation=True) are not an IB status callback.
            unconfirmed = terminal and not isinstance(event, OrderDenied) and extra.get("reconciliation", False)
            if unconfirmed:
                extra["unconfirmed"] = True
            # IB reports one cancel as error 202 and orderStatus Cancelled; the second report
            # can pass the adapter's cached-status guard and still reach the strategy.
            duplicate = terminal and cid in self._terminal
            if duplicate:
                extra["duplicate_ignored"] = True
            case = ctx.record_event(cid, etype, event.ts_event, event.ts_init, **extra)
            now = self._now()
            if duplicate:
                ctx.duplicates.append({"client_order_id": cid, "type": etype, "first": self._terminal[cid],
                                       "ts_event": ns_to_iso(event.ts_event), "ts_init": ns_to_iso(event.ts_init)})
                if ctx.cleanup and not ctx.finished:
                    self._cleanup_tick()
                return
            if terminal:
                self._terminal[cid] = etype
                if self._orders[cid].side == OrderSide.SELL:
                    self._last_sell_close_ns = now  # flatten_retry_delay_seconds runs from here
            if unconfirmed:
                self._unconfirmed.add(cid)
                ctx.unconfirmed.append({"client_order_id": cid, "case": case, "type": etype,
                                        "reason": redact(extra.get("reason", ""))[:200] or None,
                                        "ts_event": ns_to_iso(event.ts_event)})
            if isinstance(event, OrderFilled):
                commission = event.commission
                ctx.add_fill(case, cid, "BUY" if event.order_side == OrderSide.BUY else "SELL",
                             Decimal(str(event.last_px)), Decimal(str(event.last_qty)),
                             None if commission is None else Decimal(str(commission.as_decimal())),
                             None if commission is None else commission.currency.code, event.ts_event)
            if ctx.cleanup or ctx.finished:
                # is_closed, not "not is_open": a SUBMITTED flatten is neither open nor closed.
                if self._flatten_active and cid == self._flatten_active[0] and self.cache.order(event.client_order_id).is_closed:
                    self._flatten_active = None
                if not ctx.finished:
                    self._cleanup_tick()
                return
            if unconfirmed:
                # Never pass a case on an engine-generated close; the order may still be live at IB.
                self.abort(f"{case}_unconfirmed_{etype}", kind="incomplete")
                return
            if isinstance(event, (OrderRejected, OrderDenied, OrderExpired)):
                self.abort(f"{case}_{etype}: {extra.get('reason', '')}", kind="failed")
                return
            if case == "C1":
                if isinstance(event, OrderAccepted) and ctx.current == "C1":
                    ctx.pass_case("C1", now, venue_order_id_present=event.venue_order_id is not None)
                    self._begin("C2")
                elif isinstance(event, OrderFilled):
                    self.abort("c1_resting_order_filled", kind="failed")
                elif isinstance(event, OrderCanceled) and ctx.current == "C2":
                    ctx.pass_case("C2", now)
                    self._begin("C3")
                elif isinstance(event, OrderCancelRejected) and ctx.current == "C2":
                    self.abort(f"c2_cancel_rejected: {extra.get('reason', '')}", kind="failed")
                elif isinstance(event, OrderCanceled):
                    self.abort("c1_canceled_unexpectedly", kind="failed")
            elif case == "C3":
                order = self.cache.order(event.client_order_id)
                if isinstance(event, OrderFilled) and order.status == OrderStatus.FILLED:
                    ctx.pass_case("C3", now, filled_qty=str(order.filled_qty), avg_px=str(order.avg_px))
                    self._begin("C4")
                elif isinstance(event, OrderCanceled):
                    self.abort("c3_canceled_before_fill", kind="failed")
            elif case == "C4":
                if isinstance(event, OrderFilled):
                    self._evaluate_c4()
                elif isinstance(event, OrderCanceled):
                    self.abort("c4_canceled_before_fill", kind="failed")

        def on_position_opened(self, event):
            try:
                opened = {"side": position_side_to_str(event.side), "quantity": str(event.quantity),
                          "avg_px_open": str(event.avg_px_open), "ts_event": ns_to_iso(event.ts_event)}
                if self.ctx.position_opened is None:
                    self.ctx.position_opened = opened
                else:
                    self.ctx.notes.append(f"another position opened: {opened['side']} {opened['quantity']}")
                if self.ctx.current == "C4" and self._waiting_quote:
                    self._try_step()
            except Exception as exc:  # noqa: BLE001
                self._fault(exc)

        def on_position_closed(self, event):
            try:
                pnl = event.realized_pnl
                self.ctx.position_closed = {"realized_pnl": None if pnl is None else str(pnl.as_decimal()),
                                            "currency": None if pnl is None else pnl.currency.code,
                                            "ts_event": ns_to_iso(event.ts_event)}
                if self.ctx.current == "C4" and not self.ctx.cleanup:
                    self._evaluate_c4()
                elif self.ctx.cleanup and not self.ctx.finished:
                    self._cleanup_tick()
            except Exception as exc:  # noqa: BLE001
                self._fault(exc)

        def _evaluate_c4(self):
            ctx = self.ctx
            if ctx.finished or ctx.cleanup or ctx.cases["C4"]["outcome"] != "running":
                return
            order = self.cache.order(ClientOrderId(ctx.client_order_id("C4")))
            if order is None or order.status != OrderStatus.FILLED:
                return
            if self.cache.positions_open(instrument_id=self._iid, strategy_id=self.id) or ctx.net_qty != 0:
                return  # wait for the position to close
            if ctx.position_closed is None:
                # The position can close in the cache before OrderFilled reaches the strategy.
                done = self.cache.positions_closed(instrument_id=self._iid, strategy_id=self.id)
                if done:
                    pnl = done[-1].realized_pnl
                    ctx.position_closed = {"realized_pnl": None if pnl is None else str(pnl.as_decimal()),
                                           "currency": None if pnl is None else pnl.currency.code,
                                           "ts_event": ns_to_iso(done[-1].ts_closed), "source": "cache"}
            closed = ctx.position_closed or {}
            rt = ctx.compute_roundtrip(closed.get("realized_pnl"), closed.get("currency"))
            now = self._now()
            if rt["loss_bound_breached"]:
                ctx.end_case("C4", "failed", "roundtrip_loss_bound_exceeded", now)
            else:
                ctx.pass_case("C4", now, filled_qty=str(order.filled_qty), avg_px=str(order.avg_px), flat=True)
            self._finish("cases_complete")

        # ---------------------------------------------------------- watchdog, abort and cleanup
        def _on_watchdog(self, _event):
            try:
                ctx = self.ctx
                if ctx.finished:
                    return
                if ctx.cleanup:
                    self._cleanup_tick()
                    return
                if ctx.current == "C4":
                    self._evaluate_c4()
                if self._waiting_quote:
                    self._try_step()
                if not ctx.finished and not ctx.cleanup and self._now() > self._step_deadline_ns:
                    self.abort(f"{ctx.current}_step_timeout", kind="incomplete")
            except Exception as exc:  # noqa: BLE001
                self.ctx.errors.append(redact(f"watchdog {type(exc).__name__}: {exc}")[:200])
                if not self.ctx.cleanup:
                    self.abort("watchdog_exception", kind="failed")

        def abort(self, reason: str, kind: str = "incomplete"):
            """Stop the case sequence; cancel this run's orders and flatten, then stop the node."""
            ctx = self.ctx
            if ctx.finished or ctx.cleanup:
                return
            self._waiting_quote = False
            ctx.start_cleanup(reason, kind, self._now())
            if not ctx.started:
                self._finish("aborted_before_start")
                return
            self._cleanup_tick()

        def _outstanding_orders(self):
            """Every order this run created that is not closed, including INITIALIZED and
            SUBMITTED ones (which orders_open/orders_inflight would miss)."""
            out = []
            for cid, order in self._orders.items():
                current = self.cache.order(order.client_order_id) or order
                if not current.is_closed:
                    out.append(current)
            return out

        def _cleanup_tick(self):
            # Order events are delivered synchronously from submit/cancel calls (at least
            # OrderInitialized in a live node); never re-enter or a flatten could be doubled.
            if self._in_cleanup or self.ctx.finished:
                return
            self._in_cleanup = True
            try:
                self._cleanup_step()
            finally:
                self._in_cleanup = False

        def _cleanup_step(self):
            ctx = self.ctx
            now = self._now()
            if now > ctx.cleanup["deadline_ns"]:
                self._finish("cleanup_deadline")  # _finish sends the final cancel for every open order
                return
            self._sweep_cancels("cleanup")
            if self._outstanding_orders():
                return
            self._flatten_active = None
            if self._unconfirmed:
                ctx.notes.append("an order of this run closed only by an engine-generated event; no further "
                                 "orders are sent and the independent check decides")
                self._finish("cleanup_unconfirmed_order_state")
                return
            if ctx.net_qty == 0:
                self._finish("cleanup_flat")
                return
            if ctx.net_qty < 0:
                ctx.notes.append("net quantity negative after cleanup; left for the independent check")
                self._finish("cleanup_negative_quantity")
                return
            retry_ns = int(ctx.plan["timeouts"]["flatten_retry_delay_seconds"] * 1e9)
            if self._last_sell_close_ns is not None and now - self._last_sell_close_ns < retry_ns:
                return  # a SELL of this run just closed (denied, rejected, canceled): wait before re-submitting
            if not self._spacing_ok():
                return
            q = self._fresh_quote()
            if q is None:
                return  # wait for a fresh quote (watchdog and quote ticks retry)
            if ctx.budget.remaining <= 0:
                self._finish("cleanup_budget_exhausted")
                return
            qty = int(ctx.net_qty)
            if qty <= 0 or qty > ctx.plan["bounds"]["max_quantity_per_order"]:
                self._finish("cleanup_quantity_out_of_bounds")
                return
            self._flatten_n += 1
            price = marketable_sell_price(q[0], ctx.plan["bounds"]["marketable_offset_usd"])
            try:
                cid = self._submit("cleanup", f"X{self._flatten_n}", "SELL", price, qty)
            except BudgetError as exc:
                ctx.errors.append(f"cleanup budget: {exc}")
                # A notional refusal leaves the position for a manual flatten; name it apart
                # from running out of the order budget.
                self._finish("cleanup_notional_refused" if "notional" in str(exc) else "cleanup_budget_exhausted")
                return
            ctx.cleanup["flatten_orders"] += 1
            if self._orders[cid].is_closed:
                # Denied synchronously inside submit_order (before _flatten_active is set).
                self._last_sell_close_ns = self._now()
            else:
                self._flatten_active = (cid, now)

        def _finish(self, reason: str):
            ctx = self.ctx
            if ctx.finished:
                return
            ctx.finished = True
            try:
                sent = self._sweep_cancels(f"finish:{reason}", force=True)
                if sent:
                    ctx.notes.append(f"finish ({reason}) sent a final cancel for {sent} open order(s) of this run")
            except Exception as exc:  # noqa: BLE001
                ctx.errors.append(redact(f"finish cancel sweep: {type(exc).__name__}: {exc}")[:200])
            if ctx.cleanup:
                ctx.cleanup["ended_at"] = ns_to_iso(self._now())
                ctx.cleanup["end_reason"] = reason
            ctx.node["finish_reason"] = reason
            ctx.changed()
            try:
                self.clock.cancel_timer("ibpo-watchdog")
            except Exception:  # noqa: BLE001
                pass
            self._request_stop(f"strategy:{reason}")

    return PaperOrderStrategy


# --------------------------------------------------------------------------- node phase


def build_node_config(plan: dict, account_id: str, port: int, log_level: str = "WARNING"):
    """TradingNodeConfig for the 1.231.0 Python IB clients (pure config; connects nothing)."""
    from nautilus_trader.adapters.interactive_brokers.common import IB, IBContract
    from nautilus_trader.adapters.interactive_brokers.config import (IBMarketDataTypeEnum,
                                                                     InteractiveBrokersDataClientConfig,
                                                                     InteractiveBrokersExecClientConfig,
                                                                     InteractiveBrokersInstrumentProviderConfig,
                                                                     SymbologyMethod)
    from nautilus_trader.config import (LiveExecEngineConfig, LiveRiskEngineConfig, LoggingConfig, RoutingConfig,
                                        TradingNodeConfig)

    t, inst, node_id, x = plan["timeouts"], plan["instrument"], plan["client_ids"]["node"], plan["exec_engine"]
    provider = InteractiveBrokersInstrumentProviderConfig(
        symbology_method=SymbologyMethod.IB_SIMPLIFIED,
        load_contracts=frozenset([IBContract(secType=inst["sec_type"], symbol=inst["symbol"], exchange=inst["exchange"],
                                             primaryExchange=inst["primary_exchange"], currency=inst["currency"])]),
    )
    data_cfg = InteractiveBrokersDataClientConfig(
        ibg_host=plan["host"], ibg_port=port, ibg_client_id=node_id,
        use_regular_trading_hours=not plan["session"].get("outside_rth", False),
        market_data_type=IBMarketDataTypeEnum.REALTIME, instrument_provider=provider,
        connection_timeout=t["node_start_seconds"], request_timeout_secs=t["per_step_seconds"])
    exec_cfg = InteractiveBrokersExecClientConfig(
        ibg_host=plan["host"], ibg_port=port, ibg_client_id=node_id, account_id=account_id,
        instrument_provider=provider, routing=RoutingConfig(default=True),
        connection_timeout=t["node_start_seconds"], request_timeout_secs=t["per_step_seconds"])
    return TradingNodeConfig(
        trader_id="IBPAPER-001",
        logging=LoggingConfig(log_level=log_level),
        data_clients={IB: data_cfg},
        exec_clients={IB: exec_cfg},
        risk_engine=LiveRiskEngineConfig(max_order_submit_rate=plan["bounds"]["max_order_submit_rate"]),
        # Push the engine's in-flight resolution (fabricated OrderRejected/OrderCanceled after
        # threshold x retries without a venue answer) beyond the run; venue queries still run.
        exec_engine=LiveExecEngineConfig(inflight_check_interval_ms=x["inflight_check_interval_ms"],
                                         inflight_check_threshold_ms=x["inflight_check_threshold_ms"],
                                         inflight_check_retries=x["inflight_check_retries"]),
        timeout_connection=float(t["node_start_seconds"]),
        timeout_reconciliation=15.0,
        timeout_portfolio=10.0,
        timeout_disconnection=10.0,
        timeout_post_stop=float(t["post_stop_cancel_grace_seconds"]),  # on_stop cancels reach the adapter first
    )


RUN_SIGNALS = tuple(getattr(signal, n) for n in ("SIGINT", "SIGTERM", "SIGHUP") if hasattr(signal, n))


class NodeStopControl:
    """Deadlines, signals and stop escalation for one TradingNode run. The node, its
    event loop and the strategy's abort are injected, so this runs offline.

    A requested stop is the graceful node.stop() (Trader.stop -> on_stop cancel sweep,
    timeout_post_stop, disconnect). If node.run() has not returned node_stop_allowance_seconds
    later, or on a further signal once a stop was requested, the stop is forced: the
    kernel's remaining tasks are cancelled and the loop is stopped, so node.run() returns
    and the independent flat proof still runs. The hard stop never cuts a graceful stop
    short; it only guarantees the forced stop by hard stop + allowance."""

    def __init__(self, ctx: RunContext, plan: dict, node=None, loop=None, abort=None, monotonic=time.monotonic):
        self.ctx, self.node, self.loop, self.abort = ctx, node, loop, abort
        self.allowance_s = float(plan["timeouts"]["node_stop_allowance_seconds"])
        self.monotonic = monotonic
        self.requested = False
        self.forced = False
        self.force_at: float | None = None
        self._force_handle = None
        self.signals: list[str] = []

    def request_stop(self, by: str):
        if self.requested:
            return
        self.requested = True
        self.ctx.node["stop_requested_by"] = by
        self._arm_force(self.monotonic() + self.allowance_s, "stop_allowance_exceeded")
        self.node.stop()

    def _arm_force(self, at: float, by: str):
        """Schedule the forced stop at ``at`` unless one is already due no later."""
        if self.forced or self.loop is None or (self.force_at is not None and self.force_at <= at):
            return
        if self._force_handle is not None:
            self._force_handle.cancel()
        self.force_at = at
        self._force_handle = self.loop.call_later(max(0.0, at - self.monotonic()), self.force_stop, by)

    def force_stop(self, by: str):
        if self.forced:
            return
        self.forced = True
        ctx = self.ctx
        ctx.node["forced_stop_by"] = by
        ctx.notes.append(f"forced node stop ({by}): remaining kernel tasks cancelled and the event loop stopped")
        try:
            self.node.kernel.cancel_all_tasks()
        except Exception as exc:  # noqa: BLE001
            ctx.errors.append(redact(f"forced stop cancel_all_tasks: {type(exc).__name__}: {exc}")[:200])
        # call_soon, not an immediate stop: the cancelled tasks get one loop step to unwind.
        # node.run() then returns (run_until_complete finishes or raises the RuntimeError
        # TradingNode.run catches).
        self.loop.call_soon(self.loop.stop)

    def _stop_before_start(self, reason: str):
        """The strategy has not started: mark the run finished so a late on_start submits nothing."""
        ctx = self.ctx
        if ctx.started:
            return
        if not ctx.cleanup:
            ctx.start_cleanup(reason, "incomplete", time.time_ns())
        ctx.finished = True

    def on_node_start_deadline(self):
        if self.ctx.started:
            return
        self.ctx.notes.append("node did not start the strategy within node_start_seconds")
        self._stop_before_start("node_start_timeout")
        self.request_stop("node_start_timeout")

    def on_abort_deadline(self):
        if self.ctx.started and not self.ctx.finished:
            self.abort("overall_deadline")
        elif not self.ctx.started:
            self.on_node_start_deadline()

    def on_hard_stop(self):
        self.ctx.notes.append("hard stop reached")
        self._stop_before_start("hard_stop")
        if self.requested:
            self._arm_force(self.monotonic() + self.allowance_s, "hard_stop")
        else:
            self.request_stop("hard_stop")

    def on_signal(self, sig):
        name = getattr(sig, "name", str(sig))
        self.signals.append(name)
        ctx = self.ctx
        ctx.notes.append(f"received {name}")
        self._stop_before_start(f"signal_{name}")
        if len(self.signals) == 1 and ctx.started and not ctx.finished:
            self.abort(f"signal_{name}")
        elif not self.requested:
            self.request_stop(f"signal_{name}")
        elif len(self.signals) >= 2:
            self.force_stop(f"signal_{name}")
        # else: a first signal during a graceful stop; the armed allowance bounds it.


def run_node(plan: dict, account_id: str, port: int, ctx: RunContext, *, abort_at: float, hard_stop_at: float,
             window_end: datetime | None, log_level: str = "WARNING") -> None:
    """Build and run a TradingNode with the 1.231.0 Python IB clients; returns when the node stops."""
    from nautilus_trader.adapters.interactive_brokers.common import IB
    from nautilus_trader.adapters.interactive_brokers.factories import (InteractiveBrokersLiveDataClientFactory,
                                                                        InteractiveBrokersLiveExecClientFactory)
    from nautilus_trader.config import StrategyConfig
    from nautilus_trader.live.node import TradingNode

    t = plan["timeouts"]
    node_cfg = build_node_config(plan, account_id, port, log_level)
    node = TradingNode(config=node_cfg)
    control = NodeStopControl(ctx, plan, node=node)
    strategy = build_strategy_class()(StrategyConfig(order_id_tag="001"), ctx, control.request_stop)
    strategy._window_end = window_end
    control.abort = lambda reason: strategy.abort(reason, kind="incomplete")
    node.trader.add_strategy(strategy)
    node.add_data_client_factory(IB, InteractiveBrokersLiveDataClientFactory)
    node.add_exec_client_factory(IB, InteractiveBrokersLiveExecClientFactory)
    node.build()
    ctx.node["built"] = True
    loop = node.get_event_loop()
    control.loop = loop

    # Replace the kernel's stop-on-signal handlers so a signal first runs cleanup.
    for sig in RUN_SIGNALS:
        loop.add_signal_handler(sig, control.on_signal, sig)
    now = time.monotonic()
    loop.call_later(t["node_start_seconds"], control.on_node_start_deadline)
    loop.call_later(max(0.0, abort_at - now), control.on_abort_deadline)
    loop.call_later(max(0.0, hard_stop_at - now), control.on_hard_stop)
    try:
        node.run()
    finally:
        try:
            node.dispose()
        finally:
            # Closing the loop drops its handlers; restore interruptible signals for the flat proof.
            install_signal_handlers()


# --------------------------------------------------------------------------- receipts and CLI


def _raise_interrupt(signum, frame):
    raise KeyboardInterrupt(f"signal {signum}")


def install_signal_handlers():
    """Outside the node phase SIGINT, SIGTERM and SIGHUP raise KeyboardInterrupt so a
    receipt is still written (SIGHUP would otherwise end the process silently)."""
    signal.signal(signal.SIGINT, signal.default_int_handler)
    for sig in RUN_SIGNALS:
        if sig != signal.SIGINT:
            signal.signal(sig, _raise_interrupt)


def versions() -> dict:
    out = {"nautilus_trader": None, "ibapi": None}
    try:
        import nautilus_trader

        out["nautilus_trader"] = nautilus_trader.__version__
    except Exception:  # noqa: BLE001
        pass
    try:
        import ibapi

        out["ibapi"] = ibapi.get_version_string()
    except Exception:  # noqa: BLE001
        pass
    return out


def base_receipt(plan_path=PLAN_PATH) -> dict:
    v = versions()
    return {"schema_version": SCHEMA_VERSION, "kind": RECEIPT_KIND,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "nautilus_trader_version": v["nautilus_trader"], "ibapi_version": v["ibapi"],
            "plan_sha256": sha256_file(plan_path) if Path(plan_path).exists() else None,
            "harness_sha256": sha256_file(HARNESS_PATH), "evidence_class": "none"}


def _write_receipt_file(path, receipt: dict, secret_values=()) -> int:
    """Serialize, scrub and atomically replace ``path`` (a kill mid-write leaves the old file)."""
    code = exit_code_for(receipt["status"])
    receipt["exit_code"] = code
    text = scrub_serialized(json.dumps(receipt, indent=2, default=str), secret_values)
    target = Path(path)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text + "\n")
        os.replace(tmp, target)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    return code


def write_receipt(path, receipt: dict, secret_values=()) -> int:
    code = _write_receipt_file(path, receipt, secret_values)
    print(json.dumps({k: receipt.get(k) for k in ("status", "evidence_class", "exit_code")}))
    return code


PROVISIONAL_NOTE = ("provisional receipt written before the node started; if it is still here the run ended "
                    "without its final receipt (killed, hung up or the final write failed) and orders with "
                    "this run_prefix may remain at IB: run 'check', cancel them and flatten by hand")


def provisional_receipt(receipt: dict, ctx: RunContext) -> dict:
    """The cleanup_required receipt that stands until the final receipt replaces it."""
    out = dict(receipt)
    out.update(status="cleanup_required", evidence_class="native_paper", provisional=True, note=PROVISIONAL_NOTE,
               run=ctx.summary(), flat_proof={"status": "not_attempted"})
    return out


def flat_proof(plan: dict, port: int, check_fn, sleep_fn, overall_end: float) -> dict:
    """Independent official-ibapi flat proof after the node has stopped. Never raises: a
    failed attempt is recorded as 'error'; an interrupt ends it as 'interrupted'."""
    t = plan["timeouts"]
    attempts = []
    try:
        for i in range(t["post_check_attempts"]):
            remaining = overall_end - time.monotonic()
            if i:
                # Retries only inside the overall deadline; the first attempt always runs.
                if remaining < t["post_check_retry_delay_seconds"] + 10:
                    break
                sleep_fn(t["post_check_retry_delay_seconds"])
                remaining -= t["post_check_retry_delay_seconds"]
            try:
                post, _ = check_fn(plan, port, with_session=False, deadline_s=max(15.0, remaining))
            except Exception as exc:  # noqa: BLE001
                attempts.append({"status": "error", "error": redact(f"{type(exc).__name__}: {exc}")[:200]})
                continue
            attempts.append(_sanitized_check(post))
            if post["status"] == "passed":
                break
    except BaseException as exc:  # noqa: BLE001 - KeyboardInterrupt from a signal, SystemExit
        return {"status": "interrupted", "positions": None, "open_orders": None, "attempts": attempts,
                "error": redact(type(exc).__name__)[:200]}
    last = attempts[-1] if attempts else None
    if last is None:
        return {"status": "not_attempted", "positions": None, "open_orders": None, "attempts": attempts}
    return {"status": "passed" if last["status"] == "passed" else last["status"],
            "positions": (last.get("observed") or {}).get("positions"),
            "open_orders": (last.get("observed") or {}).get("open_orders"),
            "attempts": attempts}


def _sanitized_check(result: dict | None) -> dict | None:
    if result is None:
        return None
    return {k: v for k, v in result.items() if k not in ("liquid_hours", "trading_hours")}


def cmd_check(a, check_fn=run_check) -> int:
    if a.receipt and is_gate_receipt(a.receipt):
        print(json.dumps({"status": "refused_gate_receipt_path", "exit_code": 3}))
        return 3
    plan = load_plan()
    errors = validate_plan(plan)
    if errors:
        print(json.dumps({"status": "refused_plan_invalid", "errors": errors, "exit_code": 3}))
        return 3
    result, account = check_fn(plan, a.port, with_session=False)
    status = result["status"]
    code = exit_code_for(status)
    summary = {"status": status, "exit_code": code, "account_count": (result.get("observed") or {}).get("account_count"),
               "positions": (result.get("observed") or {}).get("positions"),
               "open_orders": (result.get("observed") or {}).get("open_orders")}
    if a.receipt:
        receipt = base_receipt()
        receipt.update(kind="ibkr_paper_orders_check", status=status, check=_sanitized_check(result),
                       evidence_class="native_paper_readonly" if status != "not_connected" else "not_connected")
        return write_receipt(a.receipt, receipt, [account])
    print(scrub_serialized(json.dumps(summary), [account]))
    return code


def pinned_runtime(plan: dict, observed: dict) -> bool:
    """True only when the imported NautilusTrader and ibapi are the plan's exact versions: the
    harness relies on version-specific adapter behaviour (order tags, commission mapping)."""
    engine = plan["engine"]
    return observed.get("nautilus_trader") == engine["version"] and observed.get("ibapi") == engine["ibapi_version"]


def cmd_run(a, check_fn=run_check, node_fn=run_node, now_fn=None, sleep_fn=time.sleep, versions_fn=None) -> int:
    t0 = time.monotonic()
    if is_gate_receipt(a.receipt):
        print(json.dumps({"status": "refused_gate_receipt_path", "exit_code": 3}))
        return 3
    plan_path = HERE / getattr(a, "plan", "plan.json")
    receipt = base_receipt(plan_path)
    receipt.update(port=a.port, status=None)
    account = None
    ctx = None
    plan = None
    node_entered = False
    overall_end = t0
    flat = {"status": "not_attempted", "positions": None, "open_orders": None, "attempts": []}
    try:
        try:
            plan = load_plan(plan_path)
            errors = validate_plan(plan)
            if errors:
                receipt.update(status="refused_plan_invalid", plan_errors=errors)
                return write_receipt(a.receipt, receipt)
            receipt["plan_bounds"] = plan["bounds"]
            if a.port not in plan["paper_ports"]:
                receipt.update(status="refused_not_paper_port")
                return write_receipt(a.receipt, receipt)
            observed = (versions_fn or versions)()
            if not pinned_runtime(plan, observed):
                receipt.update(status="refused_unpinned_runtime", runtime=observed)
                return write_receipt(a.receipt, receipt)
            now = (now_fn or (lambda: datetime.now(timezone.utc)))()
            ok, why = rth_check(now, plan)
            receipt["session_check"] = {"fixed_window": why}
            if not ok:
                receipt.update(status="refused_outside_rth")
                return write_receipt(a.receipt, receipt)
            # 'check' in-process immediately before the node; its account id stays in memory.
            pre, account = check_fn(plan, a.port, with_session=True)
            receipt["pre_check"] = _sanitized_check(pre)
            if pre["status"] == "not_connected":
                receipt.update(status="not_connected", evidence_class="not_connected")
                return write_receipt(a.receipt, receipt)
            if pre["status"] != "passed" or not account or not account.startswith(plan["account_prefix"]):
                status = pre["status"] if pre["status"].startswith("refused_") else "refused_check_not_passed"
                receipt.update(status=status)
                return write_receipt(a.receipt, receipt, [account])
            now = (now_fn or (lambda: datetime.now(timezone.utc)))()
            sessions = None
            if plan["session"].get("use_contract_liquid_hours"):
                # Fail closed: without today's contract hours a holiday or early close is invisible.
                # The after-hours plan reads tradingHours (04:00-20:00 segments), the regular
                # plan liquidHours; both use the same IB segment format.
                field = plan["session"].get("contract_hours_field", "liquidHours")
                hours = pre.get("trading_hours" if field == "tradingHours" else "liquid_hours") or ""
                tz_name = pre.get("time_zone_id") or plan["session"]["timezone"]
                local_day = now.astimezone(ZoneInfo(plan["session"]["timezone"])).date()
                sessions = parse_liquid_hours(hours, tz_name, local_day)
                receipt["session_check"].update(contract_hours_field=field, liquid_hours_present=bool(hours),
                                                liquid_hours_parsed=sessions is not None)
                if sessions is None:
                    receipt["session_check"]["with_liquid_hours"] = "today_missing_or_unparseable"
                    receipt.update(status="refused_liquid_hours_unavailable")
                    return write_receipt(a.receipt, receipt, [account])
            remaining = plan["timeouts"]["overall_deadline_seconds"] - (time.monotonic() - t0)
            ok, why = rth_check(now, plan, sessions, horizon_s=remaining)
            receipt["session_check"]["with_liquid_hours"] = why
            if not ok:
                receipt.update(status="refused_outside_rth")
                return write_receipt(a.receipt, receipt, [account])
            window = session_window(now, plan, sessions)
            t = plan["timeouts"]
            overall_end = t0 + t["overall_deadline_seconds"]
            hard_stop_at = overall_end - t["post_check_reserve_seconds"] - t["node_stop_allowance_seconds"]
            abort_at = hard_stop_at - t["cleanup_seconds"]
            ctx = RunContext(plan, new_run_prefix(now), (pre.get("observed") or {}).get("server_minus_local_s") or 0.0)
            receipt["evidence_class"] = "native_paper"
            # A cleanup_required receipt stands at the receipt path before the node can connect,
            # so SIGKILL, SIGHUP or a failed final write never leaves orders without one.
            try:
                _write_receipt_file(a.receipt, provisional_receipt(receipt, ctx), [account])
            except OSError as exc:
                ctx = None
                print(json.dumps({"status": "refused_receipt_unwritable", "exit_code": 3,
                                  "error": redact(f"{type(exc).__name__}: {exc}")[:200]}))
                return 3
            ctx.on_change = lambda: _write_receipt_file(a.receipt, provisional_receipt(receipt, ctx), [account])
            node_entered = True
            try:
                node_fn(plan, account, a.port, ctx, abort_at=abort_at, hard_stop_at=hard_stop_at,
                        window_end=window[1] if window else None, log_level=a.log_level)
            except BaseException as exc:  # noqa: BLE001 - the flat proof must still run
                ctx.errors.append(redact(f"node: {type(exc).__name__}: {exc}")[:200])
                if isinstance(exc, Exception):
                    receipt["error"] = redact(f"node: {type(exc).__name__}: {exc}")[:200]  # never a pass
                else:
                    receipt["interrupted"] = True
            ctx.changed()  # the node phase is over: persist its end state before the flat proof
        finally:
            # Whenever orders may have been submitted, the independent official-ibapi flat
            # proof runs, whatever ended the node phase.
            if node_entered or (ctx is not None and ctx.budget.used > 0):
                flat = flat_proof(plan, a.port, check_fn, sleep_fn, overall_end)
    except KeyboardInterrupt:
        receipt["interrupted"] = True
    except Exception as exc:  # noqa: BLE001
        receipt["error"] = redact(f"{type(exc).__name__}: {exc}")[:200]
    if ctx is not None:
        ctx.on_change = None  # the final receipt replaces the provisional one from here
    receipt["run"] = ctx.summary() if ctx else None
    receipt["flat_proof"] = flat
    if node_entered or (ctx is not None and ctx.budget.used > 0):
        status = final_status(ctx, flat)
        if status == "passed" and (receipt.get("interrupted") or receipt.get("error")):
            status = "incomplete"
    else:
        status = "incomplete"  # ended before the node phase: no order of this run exists
    receipt["status"] = status
    receipt["elapsed_seconds"] = round(time.monotonic() - t0, 3)
    try:
        return write_receipt(a.receipt, receipt, [account])
    except OSError as exc:
        # The provisional cleanup_required receipt (if any) stays in place.
        print(json.dumps({"status": status, "final_receipt_written": False, "exit_code": 3,
                          "error": redact(f"{type(exc).__name__}: {exc}")[:200]}))
        return 3


def main(argv=None, **hooks) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="official-ibapi read-only check")
    c.add_argument("--port", type=int, default=4002)
    c.add_argument("--receipt")
    r = sub.add_parser("run", help="bounded paper order run")
    r.add_argument("--port", type=int, default=4002)
    r.add_argument("--receipt", required=True)
    r.add_argument("--plan", choices=PLAN_NAMES, default="plan.json",
                   help="predeclared plan next to this file: plan.json (09:30-16:00) or plan-post.json (16:00-20:00, outsideRth)")
    r.add_argument("--log-level", default="WARNING", help="Nautilus console log level (console output is not redacted)")
    a = ap.parse_args(argv)
    install_signal_handlers()
    if a.cmd == "check":
        return cmd_check(a, **{k: v for k, v in hooks.items() if k == "check_fn"})
    return cmd_run(a, **hooks)


if __name__ == "__main__":
    raise SystemExit(main())
