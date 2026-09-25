"""Native Alpaca paper port for the capacity harness (evidence class ``native_paper``).

Everything that touches the network is reused read-only from
``adaptive-paper/transport.py`` (pinned alpaca-py 0.44.0):

* ``_sdk_client`` builds a ``TradingClient(paper=True)`` whose HTTP session is
  ``GuardedSession``: origin pinned to https://paper-api.alpaca.markets, SDK
  retries set to zero, redirects rejected, and only GET reads, POST /v2/orders
  and DELETE /v2/orders/{uuid} admitted. DELETE /v2/orders (cancel-all) is not
  an admitted path, so ``supports_cancel_all`` is False here.
* ``GuardedSession``'s observer supplies status and the x-ratelimit-limit,
  x-ratelimit-remaining, x-ratelimit-reset and retry-after headers per call.
* ``preflight`` performs the read-only account/clock/positions/open-orders/
  asset/latest-quote preflight and hashes the account identity.
  ``recovery_preflight`` reads only GET /v2/account on the trading origin.
* ``_stream_classes`` / ``_protocol_factory`` provide the ``trade_updates``
  TradingStream pinned to wss://paper-api.alpaca.markets/stream with
  redirect rejection before authentication.

Each REST worker owns its own client (and lock) so calls can overlap; the
harness's RateGovernor admits every call before it reaches this module. The
host STOP file is re-checked at the final transport boundary before a POST.
This module has not been exercised against Alpaca in this change.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import queue
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ADAPTIVE = HERE.parent / "adaptive-paper"
for _path in (str(HERE), str(ADAPTIVE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from capacity import Response  # noqa: E402
from safety import DEFAULT_STOP, SafetyError  # noqa: E402
import transport  # noqa: E402

ORDER_FIELDS = ("client_order_id", "id", "status", "symbol", "side", "filled_qty")
MAX_PAGES = 20


def _order_view(raw):
    return {name: str(raw.get(name) or "") for name in ORDER_FIELDS}


class AlpacaCapacityPort:
    evidence_class = "native_paper"
    supports_cancel_all = False

    def __init__(self, api_key, secret_key, symbol, *, feed="iex", workers=4, stop_file=None):
        if not api_key or not secret_key:
            raise transport.TransportError("explicit credentials required")
        self._key, self._secret = api_key, secret_key
        self.symbol = symbol
        self.feed = transport.data_feed(feed)
        self.workers = int(workers)
        self.stop_file = Path(stop_file) if stop_file is not None else DEFAULT_STOP
        self._pool = None
        self._clients = []
        self._data = None
        self._local = threading.local()
        self._state_lock = threading.Lock()
        self._auth = self._acked = self._ever_acked = False
        self._reasons = set()
        self._stopping = False
        self._stream = None
        self._thread = None

    # -- REST ---------------------------------------------------------------------
    def _before_request(self, kind, client_id=None):
        # Final boundary: GuardedSession turns this refusal into SubmissionNotSent.
        if kind == "submit" and self.stop_file.exists():
            raise SafetyError("stop_blocks_entry")
        return None

    def _observe(self, observation):
        self._local.observation = observation

    def _ensure_pool(self):
        if self._pool is None:
            self._pool = queue.Queue()
            for _ in range(self.workers):
                client = transport._sdk_client(self._key, self._secret, self._before_request,
                                               self._observe, lock=threading.Lock())
                self._clients.append(client)
                self._pool.put(client)
        return self._pool

    def _call(self, fn):
        pool = self._ensure_pool()
        client = pool.get()
        self._local.observation = None
        value, error, status = None, None, None
        try:
            value = fn(client)
        except transport.OrderContractRefused:  # local boundary refusal, distinct from a broker answer
            return Response(None, not_sent=True, error="OrderContractRefused"), None
        except transport.SubmissionNotSent:
            return Response(None, not_sent=True, error="SubmissionNotSent"), None
        except Exception as exc:  # sanitized: only the class name and HTTP status survive
            error = type(exc).__name__
            status = getattr(exc, "status_code", None)
        finally:
            pool.put(client)
        observation = self._local.observation
        if observation is not None:
            status = observation["status"]
        headers = dict(observation["headers"]) if observation is not None else {}
        return Response(status, headers, error=error), value

    def preflight(self):
        observations, attempts = [], []

        def before(kind, **_):
            attempts.append(kind)
            if len(attempts) > 50:
                raise SafetyError("preflight_request_bound")

        def observer(observation):
            origin = "data" if observation["kind"] == "data_read" else "trading"
            observations.append(dict(observation, origin=origin))

        pre = transport.preflight(self._key, self._secret, [self.symbol], feed=self.feed,
                                  before_request=before, request_observer=observer)
        self._ensure_pool()  # SDK pin and credentials fail here, before any order
        asset = next((a for a in pre["assets"] if a.get("symbol") == self.symbol), {})
        quote = next((q for q in pre["quotes"] if q.get("symbol") == self.symbol), None)
        return {"account_identity_sha256": pre["account_identity_sha256"],
                "positions": pre["positions"], "open_orders": pre["orders"],
                "open_orders_complete": pre["open_orders_complete"],
                "asset_tradable": bool(asset.get("tradable")) and asset.get("status") == "active",
                "quote": None if quote is None else {"bid": quote["bid"], "ask": quote["ask"],
                                                     "ts_ns": quote["ts_ns"]},
                "observations": observations}

    def recovery_preflight(self):
        """Trading-origin only (GET /v2/account): the account identity, hashed as
        ``transport.preflight`` hashes it, and the trading rate-limit headers.
        No asset or market-data read, so crash recovery survives a data outage."""
        observations, attempts = [], []

        def before(kind, **_):
            attempts.append(kind)
            if len(attempts) > 5:
                raise SafetyError("preflight_request_bound")

        def observer(observation):
            observations.append(dict(observation, origin="trading"))

        client = transport._sdk_client(self._key, self._secret, before, observer, read_only=True,
                                       lock=threading.Lock())
        try:
            raw_account = client.get_account()
        finally:
            client._session.close()
        self._ensure_pool()
        return {"account_identity_sha256": hashlib.sha256(str(raw_account["id"]).encode()).hexdigest(),
                "observations": observations}

    def latest_quote(self):
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockLatestQuoteRequest
        if self._data is None:
            self._data = transport._sdk_client(self._key, self._secret, lambda kind, **_: None,
                                               None, data=True, read_only=True)
        quotes = self._data.get_stock_latest_quote(
            StockLatestQuoteRequest(symbol_or_symbols=[self.symbol], feed=DataFeed(self.feed)))
        quote = transport.normalize_quote(quotes[self.symbol], self.symbol)
        return {"bid": quote["bid"], "ask": quote["ask"], "ts_ns": quote["ts_ns"]}

    def submit(self, client_order_id, symbol, qty, limit_price, extended_hours):
        # The engine's pre-submission order-contract boundary: a refused envelope
        # never reaches a client, and GuardedSession admits only this envelope's body.
        try:
            envelope = transport.order_envelope(
                {"client_order_id": client_order_id, "symbol": symbol, "side": "buy", "qty": str(qty),
                 "limit_price": str(limit_price), "extended_hours": bool(extended_hours)},
                extended_hours_allowed=True)
            request = transport.limit_order_request(envelope)
        except transport.OrderContractRefused:
            return Response(None, not_sent=True, error="OrderContractRefused")
        response, raw = self._call(lambda client: transport.submit_enveloped(client, envelope, request))
        if raw is not None and response.status is not None and 200 <= response.status < 300:
            response.order = _order_view(raw)
        return response

    def cancel(self, order_id):
        if not transport.UUID.fullmatch(str(order_id)):
            return Response(None, error="invalid_order_id", not_sent=True)
        response, _ = self._call(lambda client: client.cancel_order_by_id(order_id))
        return response

    def cancel_all(self):
        raise transport.TransportError("cancel-all is not an admitted GuardedSession path")

    def list_orders(self, status, after_wall, admit=None):
        """Paged listing. The caller admitted the first page; ``admit()`` must
        return True before each further page, else the listing stops incomplete."""
        params = {"status": status, "direction": "asc", "limit": 500, "nested": False}
        if after_wall is not None:
            params["after"] = datetime.fromtimestamp(after_wall, timezone.utc).isoformat()
        orders, responses, seen = [], [], set()
        for index in range(MAX_PAGES):
            if index and admit is not None and not admit():
                return [_order_view(o) for o in orders], False, responses
            response, page = self._call(lambda client: client.get("/orders", dict(params)))
            responses.append(response)
            if response.error or not isinstance(page, list) or len(page) > 500:
                return [_order_view(o) for o in orders], False, responses
            if any(str(o.get("id")) in seen for o in page):
                return [_order_view(o) for o in orders], False, responses
            orders.extend(page)
            seen.update(str(o.get("id")) for o in page)
            if len(page) < 500:
                return [_order_view(o) for o in orders], True, responses
            params.pop("after", None)  # timestamp and ID cursors are mutually exclusive
            params["after_order_id"] = str(page[-1]["id"])
        return [_order_view(o) for o in orders], False, responses

    def positions(self):
        response, rows = self._call(lambda client: client.get_all_positions())
        if response.error or not isinstance(rows, list):
            raise transport.TransportError("positions unavailable")
        return [{"symbol": str(r["symbol"]), "qty": transport.decimal_string(r["qty"])} for r in rows], [response]

    # -- trade_updates stream (owner callbacks mirror AlpacaPaperTransport) ---------
    def _connection(self, channel, connected):
        with self._state_lock:
            if not connected:
                self._auth = self._acked = False
                if self._ever_acked and not self._stopping:
                    self._reasons.add("orders_disconnected")

    def _authorized(self, channel):
        with self._state_lock:
            self._auth = True

    def _ack(self, channel, accepted):
        with self._state_lock:
            self._acked = bool(accepted and self._auth)
            self._ever_acked |= self._acked
            if not self._acked:
                self._reasons.add("orders_subscription_rejected")

    def freeze_health(self, reason):
        with self._state_lock:
            self._reasons.add(str(reason))

    def stream_health(self):
        with self._state_lock:
            return {"ready": self._auth and self._acked and not self._reasons and not self._stopping,
                    "reasons": sorted(self._reasons)}

    def _run_stream(self):
        try:
            self._stream.run()
        except Exception:
            self.freeze_health("orders_thread_failed")
        finally:
            if not self._stopping:
                self.freeze_health("orders_thread_stopped")

    def start_stream(self, callback, timeout):
        Orders, _ = transport._stream_classes(transport.data_stream_url(self.feed))
        parameters = {"ping_interval": 10, "ping_timeout": 10, "max_queue": 4096,
                      "open_timeout": 5, "close_timeout": 2,
                      "create_protocol": transport._protocol_factory(transport.PAPER_WS)}
        self._stream = Orders(self._key, self._secret, paper=True, raw_data=True,
                              url_override=transport.PAPER_WS, websocket_params=parameters)
        self._stream.owner = self

        async def on_update(data):
            callback(data)

        self._stream.subscribe_trade_updates(on_update)
        self._thread = threading.Thread(target=self._run_stream, name="capacity-trade-updates", daemon=False)
        self._thread.start()
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            health = self.stream_health()
            if health["ready"] or health["reasons"]:
                return
            time.sleep(0.02)
        self.freeze_health("orders_start_timeout")

    def stop_stream(self):
        self._stopping = True
        try:
            stream = self._stream
            loop = getattr(stream, "_loop", None) if stream is not None else None
            if loop is not None and loop.is_running():
                async def close():
                    await stream.stop_ws()
                    await stream.close()
                try:
                    asyncio.run_coroutine_threadsafe(close(), loop).result(timeout=7)
                except Exception:
                    self.freeze_health("stream_stop_timeout")
            if self._thread is not None:
                self._thread.join(7)
                if self._thread.is_alive():
                    raise transport.TransportError("stream thread failed to terminate")
        finally:
            for client in self._clients + ([self._data] if self._data is not None else []):
                client._session.close()
