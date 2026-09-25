"""Pinned alpaca-py transport for one externally locked, paper-only owner.

This module never discovers credentials, resets an account, or retries an order.
The caller owns durable intent/risk accounting and the shared request limiter.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import inspect
from pathlib import Path
import queue
import re
import threading
import time
from urllib.parse import urlsplit
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from feeds import DATA_FEEDS, is_qualified_feed

SDK_VERSION = "0.44.0"
SDK_COMMIT = "cc4cb3b7ba50ae250e621983c2779047fb16bb28"
PAPER_URL = "https://paper-api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets"
PAPER_WS = "wss://paper-api.alpaca.markets/stream"
DATA_WS_BASE = "wss://stream.data.alpaca.markets/v2"
TERMINAL = {"filled", "canceled", "expired", "rejected", "replaced"}
SYMBOL = re.compile(r"[A-Z][A-Z0-9.\-]{0,14}\Z")
CLIENT_ID = re.compile(r"[A-Za-z0-9_\-]{1,48}\Z")
UUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\Z")
# GET /v2/account/activities/{activity_type} with activity_type FILL, filtered by the
# documented order_id query parameter (https://docs.alpaca.markets/us/reference/
# getaccountactivitiesbyactivitytype-1.md). An activity id is "<timestamp>::<uuid>"
# (https://docs.alpaca.markets/us/docs/account-activities.md, TradeActivity.id).
ACTIVITY_FILL_PATH = "/v2/account/activities/FILL"
ACTIVITY_ID = re.compile(r"[0-9]{1,32}::([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})\Z")
ACTIVITY_PAGE_SIZE = 100
# trade_updates events that carry one execution's own qty, price and execution_id.
EXECUTION_EVENTS = frozenset({"fill", "partial_fill"})
EXECUTION_FIELDS = ("event", "execution_id", "event_qty", "event_price")
# The pre-submission boundary (blueprints/us-equities/order-contract). Loaded by
# path at import, so a missing or broken contract fails transport import closed.
ORDER_CONTRACT_PATH = Path(__file__).resolve().parent.parent / "order-contract" / "order_contract.py"


def _load_order_contract():
    spec = importlib.util.spec_from_file_location("adaptive_paper_order_contract", ORDER_CONTRACT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


order_contract = _load_order_contract()


class TransportError(RuntimeError):
    """Sanitized transport failure; never includes provider response bodies."""


class InvalidQuote(TransportError):
    """A streamed quote that is a legitimate but untradable market state (a crossed
    book or a one-sided zero price). It is dropped and counted, never fatal."""

    def __init__(self, reason):
        super().__init__("invalid quote: " + reason)
        self.reason = reason


class AmbiguousSubmission(TransportError):
    pass


class RejectedSubmission(TransportError):
    def __init__(self, status_code, refusal=None):
        self.status_code = status_code
        self.refusal = refusal
        self.definitive_rejection = True
        super().__init__("broker definitively rejected submission (HTTP %d%s)"
                         % (status_code, "" if refusal is None else ": " + refusal))


# Documented definitive refusals for POST /v2/orders. 401/403/404 as before. A 422 is
# ambiguous (it also carries "client_order_id must be unique", which proves an order
# exists) except the one Alpaca documents as a rejection: a limit price in excess of
# the minimum price variance, body code 42210000 with the message below
# (https://docs.alpaca.markets/us/docs/orders-at-alpaca.md, "Sub-penny increments").
# That page documents the body, not the HTTP status; 422 is inferred from the code
# prefix and POST /v2/orders 422 "Input parameters are not recognized"
# (https://docs.alpaca.markets/us/reference/postorder.md), pending native
# confirmation, so any other status stays ambiguous. The message is the
# discriminator; the code alone is not sufficient. The body is only compared with
# these constants; it is never retained or raised.
SUB_PENNY_REFUSAL = "sub_penny_minimum_price_variance"
SUB_PENNY_CODE = 42210000
SUB_PENNY_MESSAGE = "sub-penny increment does not fulfill minimum pricing criteria"


def violates_minimum_price_variance(limit_price):
    price = Decimal(str(limit_price))
    return price != price.quantize(Decimal("0.01") if price >= 1 else Decimal("0.0001"))


def documented_refusal(exc, status, intent):
    """Classify a failed POST as a documented definitive 422, or return None."""
    if status != 422 or not violates_minimum_price_variance(intent["limit_price"]):
        return None
    try:
        code, message = exc.code, exc.message
    except Exception:
        return None
    if type(code) is not int or code != SUB_PENNY_CODE or not isinstance(message, str):
        return None
    return SUB_PENNY_REFUSAL if SUB_PENNY_MESSAGE in message else None


class SubmissionNotSent(TransportError):
    definitive_rejection = True
    not_sent = True


class OrderContractRefused(SubmissionNotSent):
    """Local refusal by the order-contract boundary before any HTTP request.

    No broker answered, so it is never a RejectedSubmission (a broker's definitive
    HTTP refusal). ``refusal`` is the contract's value-free reason; a controller
    records the intent as ``not_sent`` with ``not_sent_reason``.
    """
    local_refusal = "order_contract"
    not_sent_reason = "order_contract_refused"

    def __init__(self, reason):
        self.refusal = str(reason)
        super().__init__("order contract refused submission before HTTP: " + self.refusal)


def order_envelope(intent, *, extended_hours_allowed=False):
    """Validate the exact SDK-bound projection of a normalized intent.

    Only the fields the SDK request receives are validated (attribution metadata
    never reaches the wire). Fractional sells keep the engine's exact residual
    exits; every other rule is the contract's own. Raises OrderContractRefused.
    """
    try:
        fields = {key: intent[key] for key in ("symbol", "qty", "side", "client_order_id", "limit_price")}
        fields.update(type="limit", time_in_force="day", extended_hours=intent.get("extended_hours", False))
        return order_contract.build_envelope(fields, fractional_sell_qty=True,
                                             extended_hours_allowed=bool(extended_hours_allowed))
    except order_contract.ContractError as exc:
        raise OrderContractRefused(str(exc)) from None
    except (KeyError, TypeError, AttributeError):
        raise OrderContractRefused("intent: missing required field") from None


def limit_order_request(envelope):
    """The alpaca-py request built only from a validated envelope's intent."""
    from alpaca.trading.requests import LimitOrderRequest
    intent = envelope["intent"]
    try:
        return LimitOrderRequest(symbol=intent["symbol"], qty=intent["qty"], side=intent["side"],
                                 type="limit", time_in_force="day", limit_price=intent["limit_price"],
                                 client_order_id=intent["client_order_id"],
                                 extended_hours=intent["extended_hours"])
    except Exception:
        raise OrderContractRefused("sdk request model refused the envelope") from None


_WIRE_TEXT = ("symbol", "side", "type", "time_in_force", "client_order_id")
_WIRE_KEYS = frozenset(_WIRE_TEXT + ("qty", "limit_price", "extended_hours"))


def wire_matches_envelope(body, envelope):
    """True only when the serialized POST body carries exactly the validated intent.

    alpaca-py serializes qty/limit_price as floats; a value whose float text no
    longer equals the exact envelope decimal, a dropped or added field, or any
    changed value is silent field loss and is refused before the request.
    """
    intent = envelope["intent"]
    if not isinstance(body, dict) or set(body) - {"order_class"} != _WIRE_KEYS:
        return False
    if "order_class" in body and body["order_class"] != "simple":
        return False
    if any(not isinstance(body[key], str) or body[key] != intent[key] for key in _WIRE_TEXT):
        return False
    if type(body["extended_hours"]) is not bool or body["extended_hours"] is not intent["extended_hours"]:
        return False
    for key in ("qty", "limit_price"):
        value = body[key]
        if type(value) not in (int, float, str):
            return False
        try:
            if Decimal(str(value)) != Decimal(intent[key]):
                return False
        except (InvalidOperation, ValueError):
            return False
    return True


def check_wire_submission(envelopes, body):
    """GuardedSession's POST gate: every order body needs its validated envelope."""
    client_id = body.get("client_order_id") if isinstance(body, dict) else None
    envelope = envelopes.get(client_id) if isinstance(client_id, str) else None
    if envelope is None:
        raise OrderContractRefused("no validated envelope for this submission")
    if not wire_matches_envelope(body, envelope):
        raise OrderContractRefused("serialized request differs from the validated envelope")
    return envelope


def submit_enveloped(client, envelope, request):
    """Submit one validated request; its envelope is admitted only for this call."""
    session = client._session
    client_id = envelope["intent"]["client_order_id"]
    session.expect_submission(envelope)
    try:
        return client.submit_order(request)
    finally:
        session.withdraw_submission(client_id)


def order_contract_status(symbols=()):
    """SDK-free, network-free proof that the pre-submission boundary is active.

    Checks the pinned contract path, one accepted and several refused sentinels,
    the POST gate's envelope requirement, and that every configured symbol is
    admissible. Raises TransportError naming the first failed check.
    """
    def fail(reason):
        raise TransportError("order_contract_boundary_inactive:" + reason)
    if (Path(getattr(order_contract, "__file__", "") or "").resolve() != ORDER_CONTRACT_PATH
            or not callable(getattr(order_contract, "build_envelope", None))):
        fail("contract_module_not_loaded")
    sentinel = {"client_order_id": "contract-selftest-1", "symbol": "SPY", "side": "buy", "qty": "1",
                "limit_price": "100.01", "extended_hours": False}
    try:
        envelope = order_envelope(sentinel)
    except OrderContractRefused:
        fail("valid_sentinel_refused")
    refused = 0
    for change in ({"limit_price": "100.001"}, {"qty": "0.5"}, {"client_order_id": "_leading"},
                   {"extended_hours": True}, {"symbol": "SPY1"}, {"side": "sell", "qty": "0.0000000001"}):
        try:
            order_envelope(dict(sentinel, **change))
        except OrderContractRefused:
            refused += 1
        else:
            fail("invalid_sentinel_accepted")
    wire = {"symbol": "SPY", "qty": 1.0, "side": "buy", "type": "limit", "time_in_force": "day",
            "extended_hours": False, "client_order_id": "contract-selftest-1", "limit_price": 100.01}
    try:
        check_wire_submission({"contract-selftest-1": envelope}, wire)
    except OrderContractRefused:
        fail("valid_wire_refused")
    for envelopes, body in (({}, wire), ({"contract-selftest-1": envelope}, dict(wire, limit_price=100.0)),
                            ({"contract-selftest-1": envelope}, {k: v for k, v in wire.items() if k != "qty"})):
        try:
            check_wire_submission(envelopes, body)
        except OrderContractRefused:
            refused += 1
        else:
            fail("unvalidated_wire_admitted")
    checked = 0
    for symbol in symbols:
        try:
            order_envelope(dict(sentinel, symbol=symbol))
        except OrderContractRefused:
            fail("configured_symbol_outside_contract")
        checked += 1
    return {"active": True, "contract_sha256": hashlib.sha256(ORDER_CONTRACT_PATH.read_bytes()).hexdigest(),
            "sentinels_accepted": 2, "sentinels_refused": refused, "symbols_checked": checked}


class UnsupportedDataFeed(TransportError):
    """Refusal for any market data feed outside the qualified set."""


def data_feed(value):
    """Return the one configured feed name. Entitlement is not checked here.

    Only a plain ``str`` is accepted; a ``DataFeed`` enum member is refused
    because it formats as ``DataFeed.IEX`` and would build a malformed endpoint.
    """
    if not is_qualified_feed(value):
        raise UnsupportedDataFeed("unqualified_data_feed")
    return value


def data_stream_url(feed):
    """Derive the quote stream endpoint from the single configured feed."""
    return "%s/%s" % (DATA_WS_BASE, data_feed(feed))


def halt_statuses_supported(feed):
    """E4: trading statuses and LULD bands ride the quote connection on the SIP feed only
    (the convergence record's scope; observed natively on v2/sip on 2026-09-24). Their
    availability on v2/iex is unverified, and a refused channel would keep the stream from
    becoming ready, so on any other feed the engine subscribes neither and seeds no halt
    (a seeded halt could only be cleared by a streamed resume)."""
    return feed == "sip"


def decimal_string(value, *, positive=False):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise TransportError("invalid decimal") from None
    if not number.is_finite() or (positive and number <= 0):
        raise TransportError("invalid decimal")
    if number.adjusted() > 18 or number.as_tuple().exponent < -18:
        raise TransportError("decimal precision out of bounds")
    fixed = format(number, "f")
    return fixed.rstrip("0").rstrip(".") if "." in fixed else fixed


def timestamp_ns(value):
    if value is None:
        return 0
    if hasattr(value, "to_unix_nano"):
        return int(value.to_unix_nano())
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise TransportError("timestamp lacks timezone")
        return int(value.timestamp()) * 1_000_000_000 + value.microsecond * 1000
    if isinstance(value, str):
        match = re.fullmatch(r"(.+?)(?:\.(\d{1,9}))?(Z|[+-]\d\d:\d\d)", value)
        if not match:
            raise TransportError("invalid timestamp")
        base = datetime.fromisoformat(match[1] + match[3].replace("Z", "+00:00"))
        return int(base.timestamp()) * 1_000_000_000 + int((match[2] or "").ljust(9, "0"))
    raise TransportError("unsupported timestamp")


def normalize_order(raw):
    result = {name: str(raw.get(name) or "") for name in
              ("client_order_id", "id", "symbol", "side", "status")}
    for name in ("qty", "filled_qty"):
        result[name] = decimal_string(raw.get(name, "0"))
    for name in ("filled_avg_price", "limit_price"):
        value = raw.get(name)
        result[name] = None if value is None else decimal_string(value)
    result["updated_at_ns"] = timestamp_ns(raw.get("updated_at") or raw.get("created_at"))
    if result["side"] not in {"buy", "sell"} or not result["client_order_id"] or not result["id"]:
        raise TransportError("invalid order identity")
    if not Decimal("0") <= Decimal(result["filled_qty"]) <= Decimal(result["qty"]):
        raise TransportError("invalid cumulative filled quantity")
    return result


def activity_trade_id(activity_id):
    """The native TradeId text for one FILL activity: the UUID after "::" (36 characters,
    NautilusTrader's TradeId limit). The activity id itself (a timestamp, "::" and that
    UUID) is longer than 36 characters and never used directly."""
    match = ACTIVITY_ID.fullmatch(str(activity_id))
    if not match:
        raise TransportError("invalid activity id")
    return match[1]


def normalize_fill_activity(raw, order_id):
    """One documented TradeActivity of ``order_id`` (activity_type FILL): one execution,
    its own qty and price, and the order's cumulative quantity after it. Raises
    TransportError for any other shape; provider text is never retained."""
    try:
        activity_id = str(raw["id"])
        if (raw.get("activity_type") != "FILL" or str(raw.get("order_id")) != order_id
                or raw.get("type") not in EXECUTION_EVENTS or raw.get("side") not in ("buy", "sell")):
            raise TransportError("invalid fill activity")
        symbol = str(raw["symbol"])
        result = {"activity_id": activity_id, "trade_id": activity_trade_id(activity_id), "order_id": order_id,
                  "symbol": symbol, "side": raw["side"], "type": raw["type"],
                  "qty": decimal_string(raw["qty"], positive=True),
                  "price": decimal_string(raw["price"], positive=True),
                  "cum_qty": decimal_string(raw["cum_qty"], positive=True),
                  "leaves_qty": decimal_string(raw.get("leaves_qty", "0")),
                  "transaction_time_ns": timestamp_ns(raw.get("transaction_time")), "source": "activity"}
    except TransportError:
        raise
    except (KeyError, TypeError, AttributeError, ValueError):
        raise TransportError("invalid fill activity") from None
    if (not SYMBOL.fullmatch(symbol) or result["transaction_time_ns"] <= 0
            or Decimal(result["qty"]) > Decimal(result["cum_qty"])):
        raise TransportError("invalid fill activity")
    return result


def tiled_executions(executions):
    """Executions of one order sorted by cumulative quantity. Each must start where the
    previous one ended (the first at zero), on one symbol and side, with distinct ids,
    or the list is not a complete execution record of the order."""
    ordered = sorted(executions, key=lambda row: Decimal(row["cum_qty"]))
    previous, ids = Decimal(0), set()
    for row in ordered:
        if (Decimal(row["cum_qty"]) - Decimal(row["qty"]) != previous or row["trade_id"] in ids
                or (row["symbol"], row["side"]) != (ordered[0]["symbol"], ordered[0]["side"])):
            raise TransportError("fill activities do not tile the order")
        previous = Decimal(row["cum_qty"])
        ids.add(row["trade_id"])
    return ordered


def _activity_params(params):
    """Only the documented FILL filter by one broker order: order_id (UUID), ascending,
    page_size 1-100 and an activity-id page_token."""
    if not isinstance(params, dict) or not set(params) <= {"order_id", "direction", "page_size", "page_token"}:
        return False
    size, token = params.get("page_size", ACTIVITY_PAGE_SIZE), params.get("page_token")
    return (isinstance(params.get("order_id"), str) and bool(UUID.fullmatch(params["order_id"]))
            and params.get("direction", "asc") == "asc" and type(size) is int and 1 <= size <= ACTIVITY_PAGE_SIZE
            and (token is None or (isinstance(token, str) and bool(ACTIVITY_ID.fullmatch(token)))))


# Best-effort CTA/UTP quote-condition code that can mark an individual NBBO
# quote update as halted ("H"). Alpaca's primary halt signal is the separate
# trading status stream message parsed by normalize_trading_status below, not
# a field on ordinary quote updates; this remains a defensive fallback.
QUOTE_HALT_CONDITION_CODES = frozenset({"H"})


def normalize_quote(raw, symbol=None):
    conditions = raw.get("c") or raw.get("cond") or raw.get("conditions") or []
    halted = bool(raw.get("halted")) or bool(QUOTE_HALT_CONDITION_CODES & set(conditions))
    bid = decimal_string(raw.get("bp", raw.get("bid")))
    ask = decimal_string(raw.get("ap", raw.get("ask")))
    result = {"symbol": symbol or raw.get("S") or raw.get("symbol"), "bid": bid, "ask": ask,
              "bid_size": decimal_string(raw.get("bs", raw.get("bid_size", 0))),
              "ask_size": decimal_string(raw.get("as", raw.get("ask_size", 0))),
              "ts_ns": timestamp_ns(raw.get("t", raw.get("timestamp"))), "halted": halted}
    if (not result["symbol"] or result["ts_ns"] <= 0 or min(Decimal(bid), Decimal(ask)) < 0
            or min(Decimal(result["bid_size"]), Decimal(result["ask_size"])) < 0):
        raise TransportError("invalid quote")
    # Well-formed but untradable market states: a one-sided zero price or a crossed book
    # (SIP publishes brief crossed books; see adaptive-paper/trials/20260923b-needs-attention).
    # A halt-flagged quote is never dropped, so its halt signal cannot be lost: fail closed.
    zero = Decimal(bid) == 0 or Decimal(ask) == 0
    if zero or Decimal(bid) > Decimal(ask):
        if halted:
            raise TransportError("invalid halted quote")
        raise InvalidQuote("one_sided" if zero else "crossed")
    return result


# Trading status messages (T "s": S, sc, sm, rc, rm, t, z), with the status codes
# Alpaca documents per tape (https://docs.alpaca.markets/us/docs/
# real-time-stock-pricing-data.md, "Trading Status"). Each code maps to its effect on
# the symbol's halt state: True halts (no entries, no exit re-pricing), False resumes,
# None leaves the state unchanged. The two tables share no code. The CTA meanings follow
# the CTA's own feed specification (CTS Pillar Multicast Output Binary Specification
# v2.11b, 2026-01-29, glossary and Security Status field): a Price Indication "will be
# when trading resumes after a Trading Halt" (the symbol is halted until a Resume), while
# a Trading Range Indication describes "a security that is not Trading Halted" before or
# after the opening, so it never halts and never resumes a symbol.
CTA_STATUS_CODES = {
    "2": ("halted", True),                       # Trading Halt (reason M: LULD trading pause)
    "3": ("trading", False),                     # Resume
    "5": ("price_indication", True),             # reopening indication, only while halted
    "6": ("trading_range_indication", None),     # a symbol that is not halted: no change
    "7": ("imbalance_buy", None), "8": ("imbalance_sell", None),
    "9": ("on_close_imbalance_buy", None), "A": ("on_close_imbalance_sell", None),
    "C": ("no_imbalance", None), "D": ("no_on_close_imbalance", None),
    "E": ("short_sale_restriction", None),       # never clears a halt
    "F": ("luld_limit_state", None),             # a LULD limit state is not a halt; never clears one
}
UTP_STATUS_CODES = {
    "H": ("halted", True),                       # Trading Halt
    "Q": ("quotation_only", True),               # quotes resumed, trading still halted
    "P": ("volatility_pause", True),             # LULD volatility trading pause
    "T": ("trading", False),                     # Trading Resumption
}
STATUS_CODES = {**CTA_STATUS_CODES, **UTP_STATUS_CODES}
CTA_TAPES, UTP_TAPES = frozenset({"A", "B"}), frozenset({"C", "O"})
CTA_LULD_PAUSE_REASON = "M"                      # CTA reason: Limit Up-Limit Down (LULD) Trading Pause
MARKET_WIDE_REASONS = frozenset({"1", "2", "3", "MWC0", "MWC1", "MWC2", "MWC3"})


def normalize_trading_status(raw):
    """Parse one documented trading status message into ``{"symbol", "ts_ns",
    "status_code", "reason_code", "tape", "state", "halted"}``.

    ``halted`` is True (halt, pause, quotation-only period, or a CTA price indication,
    which is only sent while a symbol is halted), False (CTA 3, UTP T), or None for a
    code that must never change the halt state (CTA 6 trading range indication, CTA E
    short-sale restriction, CTA F LULD limit state, CTA imbalance indicators 7-D). A
    code outside both documented tables, or a code of the other tape's table, is
    ``unknown_status`` and halts (fails closed) until a documented resume. A missing or
    unrecognized tape (anything but A, B, C or O) reads the code from both tables (they
    share no code), so a documented resume still resumes the symbol. CTA 2 with reason M
    is a LULD pause. Raises TransportError for a malformed message.
    """
    symbol = raw.get("S")
    status_code = raw.get("sc")
    if (not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol) or not isinstance(status_code, str)
            or not status_code):
        raise TransportError("invalid trading status")
    try:
        ts_ns = timestamp_ns(raw.get("t"))
    except (ValueError, OverflowError):
        raise TransportError("invalid trading status") from None
    if ts_ns <= 0:
        raise TransportError("invalid trading status")
    tape = raw.get("z")
    reason = raw.get("rc")
    reason = reason if isinstance(reason, str) else ""
    named = tape if isinstance(tape, str) else None
    table = (CTA_STATUS_CODES if named in CTA_TAPES else UTP_STATUS_CODES if named in UTP_TAPES
             else STATUS_CODES)
    state, halted = table.get(status_code, ("unknown_status", True))
    if halted and status_code == "2" and reason == CTA_LULD_PAUSE_REASON:
        state = "luld_pause"
    if halted and reason in MARKET_WIDE_REASONS:
        state = "market_wide_circuit_breaker"
    return {"symbol": symbol, "ts_ns": ts_ns, "status_code": status_code, "reason_code": reason,
            "tape": tape if isinstance(tape, str) else None, "state": state, "halted": halted}


def normalize_luld(raw):
    """One LULD price band message (T "l": S, u limit up, d limit down, i indicator, t,
    z). Recorded for receipts only; it never changes the halt state (a limit state or a
    pause arrives as a trading status message). Raises TransportError when malformed."""
    symbol = raw.get("S")
    if not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol):
        raise TransportError("invalid luld band")
    try:
        ts_ns = timestamp_ns(raw.get("t"))
    except (ValueError, OverflowError):
        raise TransportError("invalid luld band") from None
    up, down = decimal_string(raw.get("u")), decimal_string(raw.get("d"))
    if ts_ns <= 0 or min(Decimal(up), Decimal(down)) < 0:
        raise TransportError("invalid luld band")
    indicator, tape = raw.get("i"), raw.get("z")
    return {"symbol": symbol, "ts_ns": ts_ns, "limit_up": up, "limit_down": down,
            "indicator": indicator if isinstance(indicator, str) else None,
            "tape": tape if isinstance(tape, str) else None}


# E4 startup state: the status stream sends no snapshot at subscribe time, so a symbol
# already halted when the engine subscribes is seeded from Nasdaq Trader's trade halts
# RSS (all US listing markets), one request per engine start (the feed's own <ttl> is one
# minute). Items carry ndaq:IssueSymbol, HaltDate (MM/DD/YYYY), HaltTime (HH:MM:SS[.fff],
# Eastern), ReasonCode, Market, ResumptionDate and ResumptionTradeTime (empty until a
# resumption is set); the incentive monitor records the same fields.
NASDAQ_HALTS_RSS = "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"
HALT_ROW_FIELDS = ("HaltDate", "HaltTime", "IssueSymbol", "Market", "ReasonCode", "ResumptionDate",
                   "ResumptionQuoteTime", "ResumptionTradeTime")
HALT_FEED_MAX_BYTES = 4_000_000
HALT_FEED_SECONDS = 5.0
HALT_FEED_READ_BYTES = 65536   # the most one read may return; each read is one socket read
EASTERN = ZoneInfo("America/New_York")
_HALT_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_HALT_TIME = re.compile(r"(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?")


def parse_nasdaq_halts(payload):
    """Every item of one trade halts RSS document as a row of HALT_ROW_FIELDS (None for an
    empty field). Raises TransportError for anything that is not that RSS document."""
    try:
        root = ElementTree.fromstring(payload)
    except (ElementTree.ParseError, TypeError, ValueError):
        raise TransportError("invalid halts feed") from None
    if root.tag != "rss" or root.find("channel") is None:
        raise TransportError("invalid halts feed")
    rows = []
    for item in root.iter("item"):
        row = dict.fromkeys(HALT_ROW_FIELDS)
        for child in item:
            tag = child.tag.rsplit("}", 1)[-1]
            if tag in row:
                row[tag] = (child.text or "").strip() or None
        rows.append(row)
    return rows


def eastern_ns(date_text, time_text):
    """Epoch nanoseconds of a halt feed date (MM/DD/YYYY) and Eastern time."""
    date, clock = _HALT_DATE.fullmatch(date_text or ""), _HALT_TIME.fullmatch(time_text or "")
    if not date or not clock:
        raise TransportError("invalid halt time")
    try:
        at = datetime(int(date[3]), int(date[1]), int(date[2]), int(clock[1]), int(clock[2]), int(clock[3]),
                      int((clock[4] or "").ljust(6, "0")), tzinfo=EASTERN)
    except ValueError:
        raise TransportError("invalid halt time") from None
    return int(at.timestamp()) * 1_000_000_000 + at.microsecond * 1000


def active_halts(rows, symbols, now_ns):
    """The symbols among ``symbols`` halted at ``now_ns`` according to halt rows: each
    symbol's latest halt (by halt time) counts while its resumption trade time is absent
    or still ahead. Returns {symbol: {"halted_at_ns", "resumption_trade_ns", "reason_code",
    "market"}}. Rows of other symbols are ignored; a malformed row of a wanted symbol
    raises TransportError (the seed is then unavailable, never guessed)."""
    wanted, latest = set(symbols), {}
    for row in rows:
        symbol = row.get("IssueSymbol")
        if symbol not in wanted:
            continue
        halted_at = eastern_ns(row.get("HaltDate"), row.get("HaltTime"))
        if symbol in latest and latest[symbol]["halted_at_ns"] >= halted_at:
            continue
        resumes = row.get("ResumptionTradeTime")
        latest[symbol] = {"halted_at_ns": halted_at,
                          "resumption_trade_ns": (eastern_ns(row.get("ResumptionDate") or row.get("HaltDate"), resumes)
                                                  if resumes else None),
                          "reason_code": row.get("ReasonCode"), "market": row.get("Market")}
    return {symbol: halt for symbol, halt in sorted(latest.items())
            if halt["resumption_trade_ns"] is None or halt["resumption_trade_ns"] > now_ns}


def fetch_nasdaq_halts(*, get=None, seconds=HALT_FEED_SECONDS, max_bytes=HALT_FEED_MAX_BYTES):
    """One GET of the trade halts RSS: that one https URL, no redirects, an uncompressed
    and bounded body, and a total deadline on the body. requests' timeout bounds each
    socket read, not the body, and one iter_content chunk may span many reads of a
    slowly dripping server; so the body is read with urllib3's read1 (at most one socket
    read per call) and the deadline is checked before every read: reading ends at most
    one read timeout (``seconds``) after the deadline. Returns the body bytes; raises
    TransportError otherwise."""
    if get is None:
        import requests
        get = requests.get
    deadline = time.monotonic() + seconds
    try:
        response = get(NASDAQ_HALTS_RSS, timeout=(seconds, seconds), allow_redirects=False, stream=True,
                       headers={"User-Agent": "Mozilla/5.0 (compatible; adaptive-paper)",
                                "Accept": "application/rss+xml, application/xml",
                                "Accept-Encoding": "identity"})
    except Exception:
        raise TransportError("halts feed unavailable") from None
    try:
        if response.status_code != 200:
            raise TransportError("halts feed unavailable")
        if str(response.headers.get("Content-Encoding") or "identity").strip().lower() != "identity":
            raise TransportError("halts feed unavailable")   # decoding could chain reads past the deadline
        body = bytearray()
        while True:
            if time.monotonic() > deadline:
                raise TransportError("halts feed unavailable")
            chunk = response.raw.read1(HALT_FEED_READ_BYTES, decode_content=False)
            if not chunk:
                return bytes(body)
            body += chunk
            if len(body) > max_bytes:
                raise TransportError("halts feed too large")
    except TransportError:
        raise
    except Exception:
        raise TransportError("halts feed unavailable") from None
    finally:
        response.close()


def nasdaq_halt_seed(symbols, *, now_ns=None, fetch=None):
    """The startup halt seed for ``symbols``: one trade halts RSS read, its digest and the
    symbols it shows halted now (active_halts). Blocking; runner.Controller runs it in a
    worker thread and applies the result on the owner loop."""
    payload = (fetch or fetch_nasdaq_halts)()
    rows = parse_nasdaq_halts(payload)
    now_ns = time.time_ns() if now_ns is None else now_ns
    return {"source": "nasdaq_trade_halts_rss", "url": NASDAQ_HALTS_RSS, "fetched_at_ns": now_ns,
            "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload), "items": len(rows),
            "halts": active_halts(rows, symbols, now_ns)}


def normalize_account(raw, *, include_margin=False):
    result = {key: decimal_string(raw[key]) for key in ("cash", "equity", "buying_power")}
    for key in ("status", "currency", "trading_blocked", "account_blocked", "trade_suspended_by_user",
                "shorting_enabled", "pattern_day_trader"):
        if key in raw:
            result[key] = raw[key]
    # G-e: only read for a leverage-policy preflight/reconciliation call
    # (runner.py sets include_margin=True exactly when config has a
    # validated _leverage_policy). False (every default call site) keeps
    # this function's return keys byte-identical to before G-e.
    if include_margin:
        for key in ("multiplier", "daytrading_buying_power", "regt_buying_power", "maintenance_margin", "initial_margin"):
            if key in raw:
                result[key] = decimal_string(raw[key])
        if "daytrade_count" in raw:
            result["daytrade_count"] = raw["daytrade_count"]
    return result


def normalize_intent(order, symbols, *, allow_extended_hours=False):
    allowed = {"client_order_id", "symbol", "side", "qty", "limit_price", "type", "time_in_force",
               "extended_hours", "tags", "strategy", "reason"}
    if set(order) - allowed:
        raise TransportError("unsupported order fields")
    result = {key: str(order.get(key, "")) for key in
              ("client_order_id", "symbol", "side", "qty", "limit_price")}
    qty = Decimal(decimal_string(result["qty"], positive=True))
    result["qty"] = format(qty, "f")
    result["limit_price"] = decimal_string(result["limit_price"], positive=True)
    extended_hours = order.get("extended_hours", False)
    if type(extended_hours) is not bool or (extended_hours and not allow_extended_hours):
        raise TransportError("only owned DAY limits with whole-share entries are supported")
    if ((result["side"] == "buy" and qty != qty.to_integral_value())
            or qty.as_tuple().exponent < -9 or result["symbol"] not in symbols
            or result["side"] not in {"buy", "sell"}
            or not CLIENT_ID.fullmatch(result["client_order_id"])
            or order.get("type", "limit") != "limit"
            or order.get("time_in_force", "day") != "day"):
        raise TransportError("only owned DAY limits with whole-share entries are supported")
    result["extended_hours"] = extended_hours
    for key in ("strategy", "reason"):
        if key in order:
            if not isinstance(order[key], str) or len(order[key]) > 256:
                raise TransportError("invalid attribution metadata")
            result[key] = order[key]
    if "tags" in order:
        tags = order["tags"]
        if (not isinstance(tags, list) or len(tags) > 20
                or any(not isinstance(tag, str) or len(tag) > 128 for tag in tags)):
            raise TransportError("invalid attribution tags")
        result["tags"] = list(tags)
    return result


class GuardedSession:
    """The SDK's sole HTTP boundary, including budget and response observation."""

    def __init__(self, *, origin, before_request, observer=None, read_only=False, lock=None, before_send=None):
        import requests
        self._session = requests.Session()
        self._session.trust_env = False
        self.trust_env = False
        for adapter in self._session.adapters.values():
            adapter.max_retries = requests.adapters.Retry(total=0, connect=0, read=0, redirect=0)
        self.origin = origin
        self.before_request = before_request
        self.observer = observer
        self.read_only = read_only
        self.lock = lock or threading.Lock()
        self.before_send = before_send
        # Every order POST must carry a body equal to an envelope registered by
        # submit_enveloped for that client id (order-contract boundary).
        self._envelopes = {}
        # (broker order id, client order id) of the DELETE the owner is about to send, so
        # the budget hook can record which order a cancel request was for.
        self.cancel_expectation = None

    def expect_submission(self, envelope):
        self._envelopes[envelope["intent"]["client_order_id"]] = envelope

    def withdraw_submission(self, client_id):
        self._envelopes.pop(client_id, None)

    def request(self, method, url, **kwargs):
        method = method.upper()
        parsed = urlsplit(url)
        if (f"{parsed.scheme}://{parsed.netloc}" != self.origin or parsed.query
                or parsed.fragment or parsed.username or parsed.password):
            raise TransportError("HTTP origin or URL rejected")
        path = parsed.path
        if self.origin == DATA_URL:
            allowed = method == "GET" and path == "/v2/stocks/quotes/latest"
            kind = "data_read"
        else:
            reads = {"/v2/account", "/v2/clock", "/v2/positions", "/v2/orders",
                     "/v2/orders:by_client_order_id"}
            asset = path.startswith("/v2/assets/") and SYMBOL.fullmatch(path[len("/v2/assets/"):])
            order_id = path.startswith("/v2/orders/") and UUID.fullmatch(path[len("/v2/orders/"):])
            # FILL activities only, and only filtered by one broker order (fill gap-fill).
            activities = path == ACTIVITY_FILL_PATH and _activity_params(kwargs.get("params"))
            allowed = ((method == "GET" and (path in reads or asset or order_id or activities))
                       or (not self.read_only and method == "POST" and path == "/v2/orders")
                       or (not self.read_only and method == "DELETE" and order_id))
            kind = "submit" if method == "POST" else "cancel" if method == "DELETE" else "read"
        if not allowed:
            raise TransportError("HTTP method/path rejected")
        if kind == "submit":
            # Before the budget or the lock: an unvalidated body is refused locally.
            check_wire_submission(self._envelopes, kwargs.get("json"))
        with self.lock:
            if kind == "submit":
                try:
                    reservation = self.before_request(kind, client_id=kwargs.get("json", {}).get("client_order_id"))
                    # The POST hook is an atomic admission check, never a wait.
                    # A positive delay leaves management calls free to proceed.
                    if reservation not in (None, 0):
                        raise SubmissionNotSent("submission budget deferred")
                    if self.before_send:
                        self.before_send(kwargs.get("json", {}))
                except Exception:
                    raise SubmissionNotSent("submission prevented before HTTP request") from None
            elif kind == "cancel" and (expected := self.cancel_expectation) and \
                    path[len("/v2/orders/"):].lower() == str(expected[0]).lower():
                # Only the DELETE for the announced broker order carries its client id.
                self.before_request(kind, client_id=expected[1])
            else:
                self.before_request(kind)
            kwargs.update(timeout=(5, 5), allow_redirects=False, verify=True, proxies={})
            response = self._session.request(method, url, **kwargs)
            if self.observer:
                headers = {key.lower(): value for key, value in response.headers.items()
                           if key.lower() in {"x-ratelimit-limit", "x-ratelimit-remaining",
                                              "x-ratelimit-reset", "retry-after"}}
                self.observer({"kind": kind, "status": response.status_code, "headers": headers})
            if 300 <= response.status_code < 400:
                raise TransportError("HTTP redirect rejected")
            return response

    def close(self):
        self._session.close()


def _sdk_client(api_key, secret_key, before_request, observer=None, *, data=False, read_only=False, lock=None):
    from importlib.metadata import version
    if version("alpaca-py") != SDK_VERSION:
        raise TransportError("alpaca-py version differs from reviewed pin")
    if not api_key or not secret_key:
        raise TransportError("explicit credentials required")
    if data:
        from alpaca.data.historical import StockHistoricalDataClient
        client = StockHistoricalDataClient(api_key, secret_key, raw_data=True, url_override=DATA_URL)
    else:
        from alpaca.trading.client import TradingClient
        client = TradingClient(api_key, secret_key, paper=True, raw_data=True, url_override=PAPER_URL)
    # The reviewed SDK constructor does not accept zero as a retry override.
    client._retry = 0
    client._session.close()
    client._session = GuardedSession(origin=DATA_URL if data else PAPER_URL,
                                    before_request=before_request, observer=observer,
                                    read_only=read_only, lock=lock)
    return client


def preflight(api_key, secret_key, symbols, *, feed="iex", before_request, request_observer=None,
              include_margin=False):
    """Read-only native SDK preflight; callback is synchronous in this helper."""
    from alpaca.data.enums import DataFeed
    from alpaca.data.requests import StockLatestQuoteRequest
    symbols = _symbols(symbols)
    feed = data_feed(feed)
    lock = threading.Lock()
    trading = _sdk_client(api_key, secret_key, before_request, request_observer, read_only=True, lock=lock)
    data = _sdk_client(api_key, secret_key, before_request, request_observer, data=True, read_only=True, lock=lock)
    try:
        raw_account = trading.get_account()
        account = normalize_account(raw_account, include_margin=include_margin)
        import hashlib
        identity = hashlib.sha256(str(raw_account["id"]).encode()).hexdigest()
        clock = trading.get_clock()
        clock_received_at_ns = time.time_ns()
        positions = [{"symbol": p["symbol"], "qty": decimal_string(p["qty"]),
                      "avg_entry_price": decimal_string(p["avg_entry_price"])}
                     for p in trading.get_all_positions()]
        # Preflight admits only a flat account with no open orders. A full page is
        # explicitly incomplete and therefore cannot establish that condition.
        raw_orders = trading.get("/orders", {"status": "open", "limit": 500, "nested": False})
        orders = [normalize_order(raw) for raw in raw_orders]
        assets = []
        for symbol in symbols:
            asset = trading.get_asset(symbol)
            assets.append({key: asset.get(key) for key in
                           ("symbol", "status", "tradable", "fractionable", "marginable", "shortable")})
        quotes = data.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=list(symbols), feed=DataFeed(feed)))
        normalized_quotes, quote_errors = [], {}
        for symbol in symbols:
            if symbol not in quotes:
                quote_errors[symbol] = "missing_quote"
                continue
            try:
                normalized_quotes.append(normalize_quote(quotes[symbol], symbol))
            except (TransportError, TypeError, ValueError, AttributeError, KeyError):
                quote_errors[symbol] = "invalid_quote"
        return {"account": account, "account_identity_sha256": identity,
                "clock": {"is_open": bool(clock["is_open"]),
                "received_at_ns": clock_received_at_ns,
                "timestamp_ns": timestamp_ns(clock["timestamp"]), "next_close_ns": timestamp_ns(clock["next_close"]),
                "next_open_ns": timestamp_ns(clock["next_open"])},
                "positions": positions, "orders": orders, "open_orders_complete": len(raw_orders) < 500,
                "assets": assets, "quotes": normalized_quotes, "quote_errors": quote_errors}
    finally:
        trading._session.close()
        data._session.close()


def _symbols(symbols):
    result = tuple(sorted(set(symbols)))
    if not result or len(result) > 30 or any(not isinstance(s, str) or not SYMBOL.fullmatch(s) for s in result):
        raise TransportError("one to thirty explicit symbols required")
    return result


def _protocol_factory(endpoint):
    """Reject WebSocket redirects before the SDK can send authentication frames."""
    from websockets.legacy.client import WebSocketClientProtocol
    from websockets.exceptions import RedirectHandshake
    parsed = urlsplit(endpoint)

    class FixedEndpointProtocol(WebSocketClientProtocol):
        async def handshake(self, wsuri, *args, **kwargs):
            if (not wsuri.secure or wsuri.host != parsed.hostname or wsuri.port != 443
                    or wsuri.resource_name != parsed.path or wsuri.user_info is not None):
                raise TransportError("websocket endpoint rejected")
            try:
                return await super().handshake(wsuri, *args, **kwargs)
            except RedirectHandshake:
                raise TransportError("websocket redirect rejected before authentication") from None

    return FixedEndpointProtocol


def _stream_classes(data_ws):
    from alpaca.trading.stream import TradingStream
    from alpaca.data.live.stock import StockDataStream

    class Orders(TradingStream):
        async def _connect(self):
            self.owner._connection("orders", False)
            if str(self._endpoint) != PAPER_WS:
                raise TransportError("paper websocket endpoint rejected")
            await super()._connect()

        async def _auth(self):
            await super()._auth()
            self.owner._authorized("orders")

        async def _dispatch(self, msg):
            if msg.get("stream") == "listening":
                self.owner._ack("orders", "trade_updates" in msg.get("data", {}).get("streams", []))
            elif msg.get("stream") in {"error", "authorization"}:
                self.owner.freeze_health("orders_control_error")
            await super()._dispatch(msg)

        async def close(self):
            self.owner._connection("orders", False)
            await super().close()

    class Quotes(StockDataStream):
        async def _connect(self):
            self.owner._connection("quotes", False)
            if str(self._endpoint) != data_ws:
                raise TransportError("quote websocket endpoint rejected")
            await super()._connect()

        async def _auth(self):
            await super()._auth()
            self.owner._authorized("quotes")

        async def _dispatch(self, msg):
            if msg.get("T") == "subscription":
                # On SIP, quotes, trading statuses and LULD bands share this one
                # connection; every subscribed channel must cover every symbol or the
                # stream is not ready.
                symbols = set(self.owner.symbols)
                quotes = symbols.issubset(msg.get("quotes") or [])
                halts = not self.owner.halt_statuses or all(
                    symbols.issubset(msg.get(channel) or []) for channel in ("statuses", "lulds"))
                if quotes and not halts:
                    self.owner.freeze_health("halt_status_subscription_rejected")
                self.owner._ack("quotes", quotes and halts)
            elif msg.get("T") == "error":
                self.owner.freeze_health("quotes_control_error")
            await super()._dispatch(msg)

        async def close(self):
            self.owner._connection("quotes", False)
            await super().close()

    return Orders, Quotes


class AlpacaPaperTransport:
    def __init__(self, api_key, secret_key, symbols, *, before_request, before_submit,
                 sink_observation, queue_size=1024, quote_timeout=5.0, start_timeout=15.0,
                 order_update_timeout=10.0, request_observer=None, history_start=None,
                 max_snapshot_pages=20, required_quote_symbols=None, feed="iex",
                 extended_hours_allowed=False, include_margin=False, sink_status=None):
        # sink_status receives every normalized trading status message of a subscribed
        # symbol (normalize_trading_status) on the owning loop, like sink_observation.
        self.sink_status = sink_status
        self.extended_hours_allowed = bool(extended_hours_allowed)
        # G-e: forwarded to normalize_account on every snapshot() call.
        # False (every default construction) keeps snapshot()'s account
        # keys byte-identical to before G-e.
        self.include_margin = bool(include_margin)
        self.feed = data_feed(feed)
        self.data_ws = data_stream_url(self.feed)
        self.halt_statuses = halt_statuses_supported(self.feed)
        self.symbols = _symbols(symbols)
        self.required_quote_symbols = (self.symbols if required_quote_symbols is None
                                       else _symbols(required_quote_symbols))
        if not set(self.required_quote_symbols).issubset(self.symbols):
            raise TransportError("required quote symbols must be subscribed")
        if min(quote_timeout, start_timeout, order_update_timeout) <= 0 or queue_size < 1:
            raise TransportError("positive finite timeouts and queue size required")
        if any(not __import__("math").isfinite(x) for x in (quote_timeout, start_timeout, order_update_timeout)):
            raise TransportError("finite timeout required")
        self.before_request, self.before_submit = before_request, before_submit
        self.sink_observation, self.request_observer = sink_observation, request_observer
        self.quote_timeout, self.start_timeout = quote_timeout, start_timeout
        self.order_update_timeout = order_update_timeout
        self.history_start = history_start or datetime.now(timezone.utc)
        if self.history_start.tzinfo is None or not 1 <= max_snapshot_pages <= 100:
            raise TransportError("bounded snapshot with timezone-aware history start required")
        self.max_snapshot_pages = max_snapshot_pages
        self._events = queue.Queue(maxsize=queue_size)
        self._state_lock = threading.RLock()
        self._reasons = set()
        self._dropped_quotes = {}
        self._dropped_by_symbol = {}
        self._auth = {"orders": False, "quotes": False}
        self._acks = dict(self._auth)
        self._ever_acks = dict(self._auth)
        self._quote_seen = {}
        self._quote_values = {}
        self._pending_stream = {}
        self._stream_seen = set()
        self._executions = {}      # client order id -> execution ids already forwarded
        self._status_counts = {}   # trading status messages by resulting state
        self._luld = {}            # symbol -> latest LULD band (receipts only)
        self._luld_invalid = 0
        self._intents = {}
        self._not_sent = set()
        self._rejected = {}
        self._observed = {}
        self._loop = None
        self._stopping = False
        self._started = False
        self._ever_ready = False
        self._threads = []
        self._tasks = []
        self._operation_lock = asyncio.Lock()
        self._observation_lock = asyncio.Lock()
        self._http_lock = threading.Lock()
        self._client = _sdk_client(api_key, secret_key, self._budget_sync,
                                   self._response_sync, lock=self._http_lock)
        self._client._session.before_send = self._wire_guard
        Orders, Quotes = _stream_classes(self.data_ws)
        from alpaca.data.enums import DataFeed
        parameters = {"ping_interval": 10, "ping_timeout": 10, "max_queue": queue_size,
                      "open_timeout": 5, "close_timeout": 2}
        self._orders_stream = Orders(api_key, secret_key, paper=True, raw_data=True,
                                     url_override=PAPER_WS, websocket_params=dict(parameters,
                                     create_protocol=_protocol_factory(PAPER_WS)))
        self._quotes_stream = Quotes(api_key, secret_key, feed=DataFeed(self.feed), raw_data=True,
                                     url_override=self.data_ws, websocket_params=dict(parameters,
                                     create_protocol=_protocol_factory(self.data_ws)),
                                     data_timeout=quote_timeout)
        self._orders_stream.owner = self
        self._quotes_stream.owner = self

    @property
    def health(self):
        with self._state_lock:
            fresh = all(time.monotonic() - self._quote_seen.get(s, float("-inf")) <= self.quote_timeout
                        for s in self.required_quote_symbols)
            return {"ready": self._started and not self._stopping and not self._reasons
                    and all(self._auth.values()) and all(self._acks.values()) and fresh,
                    "frozen": bool(self._reasons), "reasons": sorted(self._reasons),
                    "authenticated": dict(self._auth), "subscriptions": dict(self._acks),
                    "fresh_quotes": fresh, "required_quote_symbols": list(self.required_quote_symbols),
                    "queue_size": self._events.qsize(), "dropped_quotes": dict(self._dropped_quotes),
                    "dropped_quotes_by_symbol": dict(self._dropped_by_symbol),
                    "halt_status_channels": ["statuses", "lulds"] if self.halt_statuses else [],
                    "trading_status_messages": dict(self._status_counts),
                    "luld_bands": {symbol: dict(band) for symbol, band in self._luld.items()},
                    "luld_invalid": self._luld_invalid}

    @property
    def ready(self):
        return self.health["ready"]

    def freeze_health(self, reason):
        with self._state_lock:
            self._reasons.add(str(reason))

    def mark_reconciled(self):
        """Caller must first validate positions, owned fills and a fresh snapshot."""
        with self._state_lock:
            if (not all(self._auth.values()) or not all(self._acks.values())
                    or not self.health["fresh_quotes"] or self._order_events_pending()):
                raise TransportError("streams are not ready for reconciliation acknowledgement")
            if "queue_overflow" in self._reasons or "callback_failure" in self._reasons:
                raise TransportError("event loss requires a new transport and durable recovery")
            # Pending order-update timers survive a routine acknowledgement; they are
            # cleared only when the orders stream actually dropped, since only then can
            # those stream events never arrive (the REST snapshot then stands in for them).
            if any(str(reason).startswith("orders_") for reason in self._reasons):
                self._pending_stream.clear()
            self._reasons.clear()

    def _order_events_pending(self):
        """True while an order event is still queued. Queued quotes, trading statuses and
        LULD bands do not block a reconciliation acknowledgement: on SIP the quote queue
        is rarely empty."""
        with self._events.mutex:
            return any(kind == "order" for kind, _ in self._events.queue)

    def _connection(self, channel, connected):
        with self._state_lock:
            if not connected:
                self._auth[channel] = self._acks[channel] = False
                if self._ever_acks[channel] and not self._stopping:
                    self.freeze_health(channel + "_disconnected")

    def _authorized(self, channel):
        with self._state_lock:
            self._auth[channel] = True

    def _ack(self, channel, accepted):
        with self._state_lock:
            self._acks[channel] = bool(accepted and self._auth[channel])
            self._ever_acks[channel] |= self._acks[channel]
            if not self._acks[channel]:
                self.freeze_health(channel + "_subscription_rejected")

    async def _invoke(self, callback, *args, **kwargs):
        result = callback(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    def _on_owner(self, callback, *args, _owner_timeout=65, _freeze_timeout=True, **kwargs):
        if self._loop is None or not self._loop.is_running():
            raise TransportError("owner loop unavailable")
        # Invoked only in a REST worker thread. Never block the owner loop.
        future = asyncio.run_coroutine_threadsafe(self._invoke(callback, *args, **kwargs), self._loop)
        try:
            return future.result(timeout=_owner_timeout)
        except FutureTimeout:
            future.cancel()
            if _freeze_timeout:
                self.freeze_health("owner_callback_timeout")
            raise TransportError("owner callback exceeded bounded deadline") from None

    def _budget_sync(self, kind, client_id=None):
        if kind == "submit" and client_id is not None:
            # Never park a submission for an entire rolling window while it
            # holds locks needed by cancels. The supported hook reserves or
            # refuses immediately; this deadline also cancels accidental sleeps.
            return self._on_owner(self.before_request, kind, client_id=client_id,
                                  _owner_timeout=0.25, _freeze_timeout=False)
        if client_id is not None:
            # A cancel that names its order keeps the ordinary (waiting) budget path.
            return self._on_owner(self.before_request, kind, client_id=client_id)
        return self._on_owner(self.before_request, kind)

    def _wire_guard(self, order):
        # Runs after a possibly delayed budget reservation, immediately before POST.
        quote = self._quote_values.get(order.get("symbol"))
        if (self._stopping or not self._started or quote is None
                or not -0.25 <= (time.time_ns() - quote["ts_ns"]) / 1e9 <= self.quote_timeout
                or (order.get("side") == "buy" and not self.ready)):
            raise SubmissionNotSent("quote or stream readiness changed before submission")

    def _response_sync(self, observation):
        if observation["status"] == 429:
            self.freeze_health("rate_limited")
        if self.request_observer:
            return self._on_owner(self.request_observer, observation)

    def _enqueue(self, kind, raw):
        if self._stopping:
            return
        try:
            self._events.put_nowait((kind, raw))
        except queue.Full:
            self.freeze_health("queue_overflow")

    async def _quote_callback(self, raw):
        self._enqueue("quote", raw)

    async def _order_callback(self, raw):
        self._enqueue("order", raw)

    async def _status_callback(self, raw):
        self._enqueue("status", raw)

    async def _luld_callback(self, raw):
        self._enqueue("luld", raw)

    async def _observe(self, order):
        async with self._observation_lock:
            return await self._observe_locked(order)

    async def _observe_locked(self, order):
        """Forward one order observation to the sink unless it is stale. A stream fill
        carrying an execution id not yet forwarded for this order is always forwarded,
        with its own qty and price, even when a REST read already advanced the cumulative
        quantity past it; the stored cumulative state never moves backward."""
        cid = order["client_order_id"]
        previous = self._observed.get(cid)
        execution = order.get("execution_id") if order.get("event") in EXECUTION_EVENTS else None
        new_execution = execution is not None and execution not in self._executions.get(cid, ())
        stale = False
        if previous:
            if order["id"] != previous["id"]:
                self.freeze_health("client_id_collision")
                raise TransportError("client ID resolves to multiple orders")
            stale = (Decimal(order["filled_qty"]) < Decimal(previous["filled_qty"])
                     or (Decimal(order["filled_qty"]) == Decimal(previous["filled_qty"])
                         and (order["updated_at_ns"] < previous["updated_at_ns"]
                              or (previous["status"] in TERMINAL and order["status"] not in TERMINAL))))
            if stale and not new_execution:
                return previous
        await self._invoke(self.sink_observation, dict(order))
        if new_execution:
            self._executions.setdefault(cid, set()).add(execution)
        if not stale:
            self._observed[cid] = {key: value for key, value in order.items() if key not in EXECUTION_FIELDS}
        return order

    async def _consume_events(self):
        while not self._stopping:
            try:
                kind, raw = self._events.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.01)
                continue
            try:
                if kind == "quote":
                    try:
                        quote = normalize_quote(raw)
                    except InvalidQuote as exc:
                        # Untradable, not corrupt: drop it without touching the stored quote or
                        # its freshness, so the last valid quote only ages toward quote_stale.
                        # Malformed data and unsubscribed symbols still fail the transport.
                        dropped = raw.get("S") or raw.get("symbol")
                        if dropped not in self.symbols:
                            raise TransportError("unexpected quote symbol") from None
                        with self._state_lock:
                            self._dropped_quotes[exc.reason] = self._dropped_quotes.get(exc.reason, 0) + 1
                            self._dropped_by_symbol[dropped] = self._dropped_by_symbol.get(dropped, 0) + 1
                        continue
                    if quote["symbol"] not in self.symbols:
                        raise TransportError("unexpected quote symbol")
                    age = (time.time_ns() - quote["ts_ns"]) / 1e9
                    if not -0.25 <= age <= self.quote_timeout:
                        if quote["symbol"] in self.required_quote_symbols:
                            self.freeze_health("quote_timestamp_stale")
                        continue
                    self._quote_seen[quote["symbol"]] = time.monotonic()
                    self._quote_values[quote["symbol"]] = quote
                    await self._invoke(self._on_quote, quote)
                elif kind == "status":
                    status = normalize_trading_status(raw)
                    if status["symbol"] not in self.symbols:
                        raise TransportError("unexpected status symbol")
                    with self._state_lock:
                        self._status_counts[status["state"]] = self._status_counts.get(status["state"], 0) + 1
                    if self.sink_status is not None:
                        await self._invoke(self.sink_status, status)
                elif kind == "luld":
                    try:
                        band = normalize_luld(raw)
                    except TransportError:
                        band = None
                    with self._state_lock:
                        if band is None or band["symbol"] not in self.symbols:
                            self._luld_invalid += 1  # receipts only; never a trading input
                        elif band["ts_ns"] >= self._luld.get(band["symbol"], {}).get("ts_ns", 0):
                            self._luld[band["symbol"]] = band
                elif kind == "order":
                    payload = raw.get("data", raw)
                    order = normalize_order(payload["order"])
                    for key, source in (("event", "event"), ("execution_id", "execution_id"),
                                        ("event_qty", "qty"), ("event_price", "price")):
                        if payload.get(source) is not None:
                            order[key] = str(payload[source])
                    self._stream_seen.add(order["client_order_id"])
                    self._pending_stream.pop(order["client_order_id"], None)
                    order = await self._observe(order)
                    await self._invoke(self._on_order, order)
                else:
                    raise TransportError("unknown stream event kind")
            except Exception:
                self.freeze_health("callback_failure")

    async def _watchdog(self):
        while not self._stopping:
            now = time.monotonic()
            if self.ready:
                self._ever_ready = True
            if self._ever_ready and not self.health["fresh_quotes"]:
                self.freeze_health("quote_stale")
            if any(now - started > self.order_update_timeout for started in self._pending_stream.values()):
                self.freeze_health("order_update_missing")
            await asyncio.sleep(min(0.1, self.quote_timeout / 2))

    def _run_stream(self, stream, channel):
        try:
            stream.run()
        except Exception:
            self.freeze_health(channel + "_thread_failed")
        finally:
            if not self._stopping:
                self.freeze_health(channel + "_thread_stopped")

    async def start(self, on_quote, on_order):
        if self._started or self._stopping:
            raise TransportError("transport instances start only once")
        self._loop = asyncio.get_running_loop()
        self._on_quote, self._on_order = on_quote, on_order
        self._orders_stream.subscribe_trade_updates(self._order_callback)
        self._quotes_stream.subscribe_quotes(self._quote_callback, *self.symbols)
        if self.halt_statuses:
            # Halts and LULD bands ride the same data connection as the quotes (one
            # stream per endpoint). alpaca-py 0.44.0 has subscribe_trading_statuses and a
            # "lulds" handler slot without a public subscribe method; the SDK sends every
            # non-empty channel in the one subscribe message of each (re)connect
            # (DataStream._send_subscribe_msg).
            self._quotes_stream.subscribe_trading_statuses(self._status_callback, *self.symbols)
            self._quotes_stream._subscribe(self._luld_callback, self.symbols,
                                           self._quotes_stream._handlers["lulds"])
        self._started = True
        self._tasks = [asyncio.create_task(self._consume_events()), asyncio.create_task(self._watchdog())]
        for stream, channel in ((self._orders_stream, "orders"), (self._quotes_stream, "quotes")):
            thread = threading.Thread(target=self._run_stream, args=(stream, channel),
                                      name="alpaca-paper-" + channel, daemon=False)
            self._threads.append(thread)
            thread.start()
        deadline = time.monotonic() + self.start_timeout
        while not self.ready:
            if time.monotonic() >= deadline or self.health["frozen"]:
                self.freeze_health("start_not_ready")
                await self.stop()
                raise TransportError("stream authentication/subscription/quote readiness failed")
            await asyncio.sleep(0.02)
        self._ever_ready = True

    def adopt_intents(self, intents):
        for order in intents:
            normalized = normalize_intent(order, self.symbols, allow_extended_hours=self.extended_hours_allowed)
            key = normalized["client_order_id"]
            if key in self._intents and self._intents[key] != normalized:
                raise TransportError("durable intent changed")
            self._intents[key] = normalized

    def _assert_matches(self, order, intent):
        for key in ("client_order_id", "symbol", "side"):
            if order[key] != intent[key]:
                self.freeze_health("client_id_collision")
                raise TransportError("returned order differs from frozen intent")
        for key in ("qty", "limit_price"):
            if order[key] is None or Decimal(order[key]) != Decimal(intent[key]):
                self.freeze_health("client_id_collision")
                raise TransportError("returned order differs from frozen intent")

    async def _lookup(self, client_id):
        try:
            raw = await asyncio.to_thread(self._client.get_order_by_client_id, client_id)
        except Exception as exc:
            if getattr(exc, "status_code", None) == 404:
                return None
            raise TransportError("order lookup failed") from None
        return await self._observe(normalize_order(raw))

    def _validated_request(self, intent):
        """The pre-submission boundary: an envelope and the SDK request built from it.

        Overridable only by the native-fault harness (its single C04 client id).
        Raises OrderContractRefused before any network call.
        """
        envelope = order_envelope(intent, extended_hours_allowed=self.extended_hours_allowed)
        return envelope, limit_order_request(envelope)

    async def submit(self, order):
        intent = normalize_intent(order, self.symbols, allow_extended_hours=self.extended_hours_allowed)
        key = intent["client_order_id"]
        async with self._operation_lock:
            if key in self._intents:
                if self._intents[key] != intent:
                    raise TransportError("durable intent changed")
                if key in self._not_sent:
                    raise SubmissionNotSent("this frozen intent was already prevented before HTTP")
                if key in self._rejected:
                    raise RejectedSubmission(*self._rejected[key])
                found = await self._lookup(key)
                if found is None:
                    self.freeze_health("replay_unresolved")
                    raise AmbiguousSubmission("existing intent not yet visible; no resubmit")
                self._assert_matches(found, intent)
                return found
            if not self._started or self._stopping or (intent["side"] == "buy" and not self.ready):
                raise SubmissionNotSent("transport not ready for exposure")
            result = await self._invoke(self.before_submit, dict(intent))
            if result is False:
                raise SubmissionNotSent("intent was not authorized by risk callback")
            self._intents[key] = dict(intent)
            try:
                envelope, request = self._validated_request(intent)
            except OrderContractRefused:
                self._not_sent.add(key)
                raise
            try:
                raw = await asyncio.to_thread(submit_enveloped, self._client, envelope, request)
                observed = normalize_order(raw)
            except SubmissionNotSent:
                self._not_sent.add(key)
                raise
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                try:
                    observed = await self._lookup(key)
                except Exception:
                    self.freeze_health("submission_ambiguous")
                    raise AmbiguousSubmission("submission lookup unavailable; no automatic retry") from None
                if observed is None:
                    # A 422/400 may report a duplicate client ID whose prior order
                    # is not visible yet. Neither is proof that the intent failed,
                    # except the documented sub-penny 422 for a price that really
                    # violates the minimum price variance (this was the first POST
                    # of this client ID; SDK retries are disabled).
                    refusal = documented_refusal(exc, status, intent)
                    if status in {401, 403, 404} or refusal is not None:
                        self._rejected[key] = (status, refusal)
                        raise RejectedSubmission(status, refusal) from None
                    self.freeze_health("submission_ambiguous")
                    raise AmbiguousSubmission("submission unresolved; no automatic retry") from None
                self.freeze_health("submission_ambiguous")
            self._assert_matches(observed, intent)
            if key not in self._stream_seen:
                self._pending_stream[key] = time.monotonic()
            return await self._observe(observed)

    async def cancel(self, client_order_id):
        """Send the broker DELETE for an owned order and return its queried final state.

        The caller asks to cancel an order it believes open or whose state is
        ambiguous; the transport does not overrule that with a cached or freshly
        read status. The DELETE goes to the known broker ID (the transport's own
        observation, or a client-ID lookup when it has none). The broker's answer is
        data: 204 is only an acknowledgement; 422 ("The order status is not
        cancelable", https://docs.alpaca.markets/us/reference/deleteorderbyorderid-1.md)
        or 404 is accepted without freezing only when the follow-up lookup shows the
        order terminal. Any other failure (timeout, 429, 5xx) freezes admissions as
        before. The follow-up observation is idempotent, so a second cancel of an
        already-canceled order changes no ledger state.
        """
        async with self._operation_lock:
            if client_order_id not in self._intents:
                raise TransportError("cancellation requires an owned durable intent")
            order = self._observed.get(client_order_id)
            if order is None:
                order = await self._lookup(client_order_id)
                if order is None:
                    self.freeze_health("cancel_identity_unobserved")
                    return None
            self._assert_matches(order, self._intents[client_order_id])
            answer = 204
            # The request log records which owned order this DELETE was for (exact
            # sim-to-paper cancel pairing); the operation lock keeps it to one DELETE.
            self._client._session.cancel_expectation = (order["id"], client_order_id)
            try:
                await asyncio.to_thread(self._client.cancel_order_by_id, order["id"])
            except Exception as exc:
                answer = getattr(exc, "status_code", None)
                if answer not in (404, 422):
                    self.freeze_health("cancellation_unresolved")
            finally:
                self._client._session.cancel_expectation = None
            # A successful DELETE is only an acknowledgement; query cumulative state.
            final = await self._lookup(client_order_id)
            if final is None:
                self.freeze_health("cancel_finality_unobserved")
            elif answer in (404, 422) and final["status"] not in TERMINAL:
                # A refusal for an order that is still working is not resolved data.
                self.freeze_health("cancellation_unresolved")
            return final

    def _pages(self, status, *, after=None):
        params = {"status": status, "direction": "asc", "limit": 500, "nested": False}
        if after is not None:
            params["after"] = after.isoformat()
        result = []
        seen = set()
        for _ in range(self.max_snapshot_pages):
            page = self._client.get("/orders", params)
            if not isinstance(page, list) or len(page) > 500:
                raise TransportError("invalid order page")
            if any(str(order["id"]) in seen for order in page):
                raise TransportError("order pagination did not advance")
            result.extend(page)
            seen.update(str(order["id"]) for order in page)
            if len(page) < 500:
                return result
            params.pop("after", None)  # Timestamp and ID cursors are mutually exclusive.
            params["after_order_id"] = str(page[-1]["id"])
        raise TransportError("snapshot page bound reached; completeness unproven")

    async def fill_activities(self, order_id):
        """Every execution of one broker order from its FILL activities (GET
        /v2/account/activities/FILL, order_id filter, oldest first): each execution's own
        qty and price and the order's cumulative quantity after it. Read-only, one
        budgeted GET per 100 executions, bounded by max_snapshot_pages. The executions
        must tile the order's filled quantity from zero (tiled_executions). Joined to the
        stream by (order, cumulative quantity): that an activity id's UUID equals the
        stream's execution_id is not documented, so neither side relies on it."""
        if self._stopping:
            raise TransportError("transport stopping")
        if not isinstance(order_id, str) or not UUID.fullmatch(order_id):
            raise TransportError("fill activities require a broker order id")

        def collect():
            rows, token = [], None
            for _ in range(self.max_snapshot_pages):
                params = {"order_id": order_id, "direction": "asc", "page_size": ACTIVITY_PAGE_SIZE}
                if token is not None:
                    params["page_token"] = token
                page = self._client.get("/account/activities/FILL", params)
                if not isinstance(page, list) or len(page) > ACTIVITY_PAGE_SIZE:
                    raise TransportError("invalid activity page")
                rows.extend(page)
                if len(page) < ACTIVITY_PAGE_SIZE:
                    return rows
                token = str(page[-1].get("id") if isinstance(page[-1], dict) else "")
            raise TransportError("activity page bound reached; completeness unproven")

        try:
            raw = await asyncio.to_thread(collect)
            return tiled_executions([normalize_fill_activity(row, order_id) for row in raw])
        except TransportError:
            raise
        except Exception:
            raise TransportError("fill activity lookup failed") from None

    async def snapshot(self):
        async with self._operation_lock:
            def collect():
                account = normalize_account(self._client.get_account(), include_margin=self.include_margin)
                positions = [{"symbol": p["symbol"], "qty": decimal_string(p["qty"]),
                              "avg_entry_price": decimal_string(p["avg_entry_price"])}
                             for p in self._client.get_all_positions()]
                orders = self._pages("open") + self._pages("all", after=self.history_start)
                return account, positions, orders
            try:
                account, positions, raw_orders = await asyncio.to_thread(collect)
                orders = {}
                for raw in raw_orders:
                    order = await self._observe(normalize_order(raw))
                    orders[order["client_order_id"]] = order
                # Adopted intents predating the history window must be resolved explicitly.
                for key in self._intents:
                    if key not in orders and key not in self._not_sent and key not in self._rejected:
                        found = await self._lookup(key)
                        if found is None:
                            raise TransportError("owned intent absent from complete snapshot")
                        orders[key] = found
                return {"account": account, "orders": list(orders.values()), "positions": positions,
                        "complete": True, "history_start": self.history_start.isoformat(),
                        "scope": "all_open_and_recent_plus_owned", "health": self.health}
            except Exception:
                self.freeze_health("snapshot_incomplete")
                raise TransportError("snapshot incomplete; admissions remain frozen") from None

    async def stop(self):
        self._stopping = True
        futures = []
        for stream in (self._orders_stream, self._quotes_stream):
            loop = getattr(stream, "_loop", None)
            if loop and loop.is_running():
                async def close_stream(s=stream):
                    await s.stop_ws()
                    await s.close()
                futures.append(asyncio.wrap_future(asyncio.run_coroutine_threadsafe(close_stream(), loop)))
        if futures:
            try:
                await asyncio.wait_for(asyncio.gather(*futures, return_exceptions=True), 7)
            except asyncio.TimeoutError:
                self.freeze_health("stream_stop_timeout")
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        for thread in self._threads:
            await asyncio.to_thread(thread.join, 7)
        if any(thread.is_alive() for thread in self._threads):
            self.freeze_health("stream_thread_leak")
            raise TransportError("stream thread failed to terminate")
        self._client._session.close()
        self._started = False
