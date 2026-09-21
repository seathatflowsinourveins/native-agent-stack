"""Pinned alpaca-py transport for one externally locked, paper-only owner.

This module never discovers credentials, resets an account, or retries an order.
The caller owns durable intent/risk accounting and the shared request limiter.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import inspect
import queue
import re
import threading
import time
from urllib.parse import urlsplit

SDK_VERSION = "0.44.0"
SDK_COMMIT = "cc4cb3b7ba50ae250e621983c2779047fb16bb28"
PAPER_URL = "https://paper-api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets"
PAPER_WS = "wss://paper-api.alpaca.markets/stream"
DATA_WS = "wss://stream.data.alpaca.markets/v2/iex"
TERMINAL = {"filled", "canceled", "expired", "rejected", "replaced"}
SYMBOL = re.compile(r"[A-Z][A-Z0-9.\-]{0,14}\Z")
CLIENT_ID = re.compile(r"[A-Za-z0-9_\-]{1,48}\Z")
UUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\Z")


class TransportError(RuntimeError):
    """Sanitized transport failure; never includes provider response bodies."""


class AmbiguousSubmission(TransportError):
    pass


class RejectedSubmission(TransportError):
    def __init__(self, status_code):
        self.status_code = status_code
        self.definitive_rejection = True
        super().__init__("broker definitively rejected submission (HTTP %d)" % status_code)


class SubmissionNotSent(TransportError):
    definitive_rejection = True


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


def normalize_quote(raw, symbol=None):
    result = {"symbol": symbol or raw.get("S") or raw.get("symbol"),
              "bid": decimal_string(raw.get("bp", raw.get("bid")), positive=True),
              "ask": decimal_string(raw.get("ap", raw.get("ask")), positive=True),
              "bid_size": decimal_string(raw.get("bs", raw.get("bid_size", 0))),
              "ask_size": decimal_string(raw.get("as", raw.get("ask_size", 0))),
              "ts_ns": timestamp_ns(raw.get("t", raw.get("timestamp")))}
    if (Decimal(result["bid"]) > Decimal(result["ask"]) or result["ts_ns"] <= 0
            or min(Decimal(result["bid_size"]), Decimal(result["ask_size"])) < 0):
        raise TransportError("invalid quote")
    return result


def normalize_account(raw):
    result = {key: decimal_string(raw[key]) for key in ("cash", "equity", "buying_power")}
    for key in ("status", "trading_blocked", "account_blocked", "trade_suspended_by_user",
                "shorting_enabled", "pattern_day_trader"):
        if key in raw:
            result[key] = raw[key]
    return result


def normalize_intent(order, symbols):
    allowed = {"client_order_id", "symbol", "side", "qty", "limit_price", "type", "time_in_force",
               "extended_hours", "tags", "strategy", "reason"}
    if set(order) - allowed:
        raise TransportError("unsupported order fields")
    result = {key: str(order.get(key, "")) for key in
              ("client_order_id", "symbol", "side", "qty", "limit_price")}
    qty = Decimal(decimal_string(result["qty"], positive=True))
    result["qty"] = format(qty, "f")
    result["limit_price"] = decimal_string(result["limit_price"], positive=True)
    if ((result["side"] == "buy" and qty != qty.to_integral_value())
            or qty.as_tuple().exponent < -9 or result["symbol"] not in symbols
            or result["side"] not in {"buy", "sell"}
            or not CLIENT_ID.fullmatch(result["client_order_id"])
            or order.get("type", "limit") != "limit"
            or order.get("time_in_force", "day") != "day"
            or order.get("extended_hours", False) is not False):
        raise TransportError("only owned DAY limits with whole-share entries are supported")
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
            allowed = ((method == "GET" and (path in reads or asset or order_id))
                       or (not self.read_only and method == "POST" and path == "/v2/orders")
                       or (not self.read_only and method == "DELETE" and order_id))
            kind = "submit" if method == "POST" else "cancel" if method == "DELETE" else "read"
        if not allowed:
            raise TransportError("HTTP method/path rejected")
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


def preflight(api_key, secret_key, symbols, *, before_request, request_observer=None):
    """Read-only native SDK preflight; callback is synchronous in this helper."""
    from alpaca.data.enums import DataFeed
    from alpaca.data.requests import StockLatestQuoteRequest
    symbols = _symbols(symbols)
    lock = threading.Lock()
    trading = _sdk_client(api_key, secret_key, before_request, request_observer, read_only=True, lock=lock)
    data = _sdk_client(api_key, secret_key, before_request, request_observer, data=True, read_only=True, lock=lock)
    try:
        raw_account = trading.get_account()
        account = normalize_account(raw_account)
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
        quotes = data.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=list(symbols), feed=DataFeed.IEX))
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
        raise TransportError("one to thirty explicit IEX symbols required")
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


def _stream_classes():
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
            if str(self._endpoint) != DATA_WS:
                raise TransportError("IEX websocket endpoint rejected")
            await super()._connect()

        async def _auth(self):
            await super()._auth()
            self.owner._authorized("quotes")

        async def _dispatch(self, msg):
            if msg.get("T") == "subscription":
                self.owner._ack("quotes", set(self.owner.symbols).issubset(msg.get("quotes", [])))
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
                 max_snapshot_pages=20, required_quote_symbols=None):
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
        self._auth = {"orders": False, "quotes": False}
        self._acks = dict(self._auth)
        self._ever_acks = dict(self._auth)
        self._quote_seen = {}
        self._quote_values = {}
        self._pending_stream = {}
        self._stream_seen = set()
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
        Orders, Quotes = _stream_classes()
        from alpaca.data.enums import DataFeed
        parameters = {"ping_interval": 10, "ping_timeout": 10, "max_queue": queue_size,
                      "open_timeout": 5, "close_timeout": 2}
        self._orders_stream = Orders(api_key, secret_key, paper=True, raw_data=True,
                                     url_override=PAPER_WS, websocket_params=dict(parameters,
                                     create_protocol=_protocol_factory(PAPER_WS)))
        self._quotes_stream = Quotes(api_key, secret_key, feed=DataFeed.IEX, raw_data=True,
                                     url_override=DATA_WS, websocket_params=dict(parameters,
                                     create_protocol=_protocol_factory(DATA_WS)),
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
                    "queue_size": self._events.qsize()}

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
                    or not self.health["fresh_quotes"] or not self._events.empty()):
                raise TransportError("streams are not ready for reconciliation acknowledgement")
            if "queue_overflow" in self._reasons or "callback_failure" in self._reasons:
                raise TransportError("event loss requires a new transport and durable recovery")
            self._reasons.clear()
            self._pending_stream.clear()

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
        if client_id is not None:
            # Never park a submission for an entire rolling window while it
            # holds locks needed by cancels. The supported hook reserves or
            # refuses immediately; this deadline also cancels accidental sleeps.
            return self._on_owner(self.before_request, kind, client_id=client_id,
                                  _owner_timeout=0.25, _freeze_timeout=False)
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

    async def _observe(self, order):
        async with self._observation_lock:
            return await self._observe_locked(order)

    async def _observe_locked(self, order):
        previous = self._observed.get(order["client_order_id"])
        if previous:
            if order["id"] != previous["id"]:
                self.freeze_health("client_id_collision")
                raise TransportError("client ID resolves to multiple orders")
            if Decimal(order["filled_qty"]) < Decimal(previous["filled_qty"]):
                return previous
            if (Decimal(order["filled_qty"]) == Decimal(previous["filled_qty"])
                    and (order["updated_at_ns"] < previous["updated_at_ns"]
                         or (previous["status"] in TERMINAL and order["status"] not in TERMINAL))):
                return previous
        await self._invoke(self.sink_observation, dict(order))
        self._observed[order["client_order_id"]] = dict(order)
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
                    quote = normalize_quote(raw)
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
                else:
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
            normalized = normalize_intent(order, self.symbols)
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

    async def submit(self, order):
        from alpaca.trading.requests import LimitOrderRequest
        intent = normalize_intent(order, self.symbols)
        key = intent["client_order_id"]
        request = LimitOrderRequest(**{k: v for k, v in intent.items()
                                       if k not in {"tags", "strategy", "reason"}},
                                    time_in_force="day", extended_hours=False)
        async with self._operation_lock:
            if key in self._intents:
                if self._intents[key] != intent:
                    raise TransportError("durable intent changed")
                if key in self._not_sent:
                    raise SubmissionNotSent("this frozen intent was already prevented before HTTP")
                if key in self._rejected:
                    raise RejectedSubmission(self._rejected[key])
                found = await self._lookup(key)
                if found is None:
                    self.freeze_health("replay_unresolved")
                    raise AmbiguousSubmission("existing intent not yet visible; no resubmit")
                self._assert_matches(found, intent)
                return found
            if not self._started or self._stopping or (intent["side"] == "buy" and not self.ready):
                raise TransportError("transport not ready for exposure")
            result = await self._invoke(self.before_submit, dict(intent))
            if result is False:
                raise TransportError("intent was not authorized by risk callback")
            self._intents[key] = dict(intent)
            try:
                raw = await asyncio.to_thread(self._client.submit_order, request)
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
                    # is not visible yet. Neither is proof that the intent failed.
                    if status in {401, 403, 404}:
                        self._rejected[key] = status
                        raise RejectedSubmission(status) from None
                    self.freeze_health("submission_ambiguous")
                    raise AmbiguousSubmission("submission unresolved; no automatic retry") from None
                self.freeze_health("submission_ambiguous")
            self._assert_matches(observed, intent)
            if key not in self._stream_seen:
                self._pending_stream[key] = time.monotonic()
            return await self._observe(observed)

    async def cancel(self, client_order_id):
        async with self._operation_lock:
            if client_order_id not in self._intents:
                raise TransportError("cancellation requires an owned durable intent")
            order = await self._lookup(client_order_id)
            if order is None:
                order = self._observed.get(client_order_id)
                if order is None:
                    self.freeze_health("cancel_identity_unobserved")
                    return None
            if order["status"] in TERMINAL:
                return order
            self._assert_matches(order, self._intents[client_order_id])
            try:
                await asyncio.to_thread(self._client.cancel_order_by_id, order["id"])
            except Exception:
                self.freeze_health("cancellation_unresolved")
            # A successful DELETE is only an acknowledgement; query cumulative state.
            final = await self._lookup(client_order_id)
            if final is None:
                self.freeze_health("cancel_finality_unobserved")
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

    async def snapshot(self):
        async with self._operation_lock:
            def collect():
                account = normalize_account(self._client.get_account())
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
