"""Offline fixture: a fake clock, a fake Alpaca-like broker and a fake trade_updates stream.

Evidence class ``offline_fixture``. It models only what the harness depends on:
per-account fixed 60-second rate windows with x-ratelimit-* headers and 429 +
Retry-After when exceeded, order acceptance, lost submit responses for created
orders, individual cancels, cancel-all, paged order listings (one trading call
per page) and trade_updates events. It does not model Alpaca's real
latency, matching, price collars or websocket behavior; nothing here is broker
evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import math
import uuid

from capacity import Response

# 2026-09-24 14:00:00 UTC = 10:00 ET, inside the regular session.
DEFAULT_WALL_START = datetime(2026, 9, 24, 14, 0, tzinfo=timezone.utc).timestamp()


class FakeClock:
    def __init__(self, wall_start=DEFAULT_WALL_START):
        self.now = 1000.0
        self.offset = wall_start - self.now

    def monotonic(self):
        return self.now

    def time(self):
        return self.now + self.offset

    def sleep(self, seconds):
        self.now += max(float(seconds), 1e-4)

    def advance(self, seconds):
        self.now += float(seconds)


class FakeBroker:
    evidence_class = "offline_fixture"

    def __init__(self, clock, *, limit=200, symbol="SPY", bid="500.00", ask="500.02",
                 positions=(), foreign_open_orders=0, submit_latency=0.03, cancel_latency=0.02,
                 read_latency=0.02, limit_schedule=None, force_429_calls=(), retry_after="2",
                 reject_submit_seqs=None, fill_submit_seqs=(), drop_events=(), crash_on_submit_seq=None,
                 supports_cancel_all=True, hide_from_listing=(), listing_status_override=None,
                 ghost_order=False, open_orders_complete=True, stream_ready=True, data_limit=10000,
                 page_size=None, lost_response_seqs=None, silent_submit_seqs=(), quote_age=0.0,
                 market_data_available=True):
        self.clock = clock
        self.limit = limit
        self.limit_schedule = limit_schedule
        self.symbol = symbol
        self.bid, self.ask = bid, ask
        self.quote_age = quote_age
        self.market_data_available = market_data_available
        self._positions = [dict(p) for p in positions]
        self.submit_latency, self.cancel_latency, self.read_latency = submit_latency, cancel_latency, read_latency
        self.force_429_calls = set(force_429_calls)
        self.retry_after = retry_after
        self.reject_submit_seqs = dict(reject_submit_seqs or {})
        self.fill_submit_seqs = set(fill_submit_seqs)
        self.drop_events = set(drop_events)
        self.crash_on_submit_seq = crash_on_submit_seq
        self.supports_cancel_all = supports_cancel_all
        self.hide_from_listing = set(hide_from_listing)
        self.listing_status_override = dict(listing_status_override or {})
        self.ghost_order = ghost_order
        self.open_orders_complete = open_orders_complete
        self._stream_ready = stream_ready
        self.data_limit = data_limit
        self.page_size = page_size
        # seq -> status (None or 5xx): the order IS created but the REST response is lost.
        self.lost_response_seqs = dict(lost_response_seqs or {})
        # Orders created by these submits never appear on trade_updates.
        self.silent_submit_seqs = set(silent_submit_seqs)
        self._silent_cids = set()
        self.orders = {}
        self.callback = None
        self.trading_calls = []
        self.total_trading_calls = 0
        self.call_log = []
        self.submit_count = 0
        self.cancel_all_calls = 0
        self.extended_hours_flags = set()
        self.stream_stopped = False
        self._uuid_counter = 0
        for index in range(foreign_open_orders):
            self._create("strategy-foreign-%d" % index, symbol, "100.00", status="new")

    # -- server-side model -------------------------------------------------------
    def current_limit(self):
        return self.limit_schedule(self.clock.time()) if self.limit_schedule else self.limit

    def _admit(self, kind):
        """Fixed 60-second windows aligned to wall time, like an x-ratelimit-reset epoch."""
        wall = self.clock.time()
        window = math.floor(wall / 60.0) * 60
        self.total_trading_calls += 1
        index = self.total_trading_calls
        self.trading_calls = [t for t in self.trading_calls if t >= window]
        limit = self.current_limit()
        used = len(self.trading_calls)
        self.call_log.append({"t": self.clock.monotonic(), "kind": kind})
        if index in self.force_429_calls or used >= limit:
            self.force_429_calls.discard(index)
            headers = {"x-ratelimit-limit": str(limit), "x-ratelimit-remaining": "0",
                       "x-ratelimit-reset": str(int(window + 60))}
            if self.retry_after is not None:
                headers["retry-after"] = self.retry_after
            return False, headers
        self.trading_calls.append(wall)
        headers = {"x-ratelimit-limit": str(limit), "x-ratelimit-remaining": str(max(0, limit - used - 1)),
                   "x-ratelimit-reset": str(int(window + 60))}
        return True, headers

    def _next_uuid(self):
        self._uuid_counter += 1
        return str(uuid.UUID(int=(0xCA9 << 64) + self._uuid_counter))

    def _create(self, cid, symbol, limit_price, status="new"):
        order = {"id": self._next_uuid(), "client_order_id": cid, "symbol": symbol, "side": "buy",
                 "qty": "1", "filled_qty": "0", "limit_price": limit_price, "status": status,
                 "created_at_wall": self.clock.time()}
        self.orders[cid] = order
        return order

    def _emit(self, event, order):
        if self.callback is None or event in self.drop_events or (event, order["client_order_id"]) in self.drop_events:
            return
        if order["client_order_id"] in self._silent_cids:
            return
        self.callback({"stream": "trade_updates",
                       "data": {"event": event, "order": {k: v for k, v in order.items() if k != "created_at_wall"}}})

    def _by_id(self, order_id):
        for order in self.orders.values():
            if order["id"] == order_id:
                return order
        return None

    # -- port API -----------------------------------------------------------------
    def preflight(self):
        observations = []
        for _ in range(4):  # account, clock, positions, open orders
            _, headers = self._admit("read")
            observations.append({"origin": "trading", "kind": "read", "status": 200, "headers": headers})
        observations.append({"origin": "data", "kind": "data_read", "status": 200,
                             "headers": {"x-ratelimit-limit": str(self.data_limit),
                                         "x-ratelimit-remaining": str(self.data_limit - 1)}})
        if not self.market_data_available:
            raise RuntimeError("fixture market-data outage")
        open_orders = [dict(o) for o in self.orders.values() if o["status"] not in
                       {"filled", "canceled", "expired", "rejected", "replaced"}]
        return {"account_identity_sha256": hashlib.sha256(b"fixture-account").hexdigest(),
                "positions": [dict(p) for p in self._positions], "open_orders": open_orders,
                "open_orders_complete": self.open_orders_complete, "asset_tradable": True,
                "quote": self.latest_quote(), "observations": observations}

    def recovery_preflight(self):
        _, headers = self._admit("read")  # account only; never market data
        return {"account_identity_sha256": hashlib.sha256(b"fixture-account").hexdigest(),
                "observations": [{"origin": "trading", "kind": "read", "status": 200, "headers": headers}]}

    def latest_quote(self):
        if not self.market_data_available:
            raise RuntimeError("fixture market-data outage")
        return {"bid": self.bid, "ask": self.ask, "ts_ns": int((self.clock.time() - self.quote_age) * 1e9)}

    def start_stream(self, callback, timeout):
        self.callback = callback

    def stream_health(self):
        return {"ready": self._stream_ready and self.callback is not None and not self.stream_stopped}

    def stop_stream(self):
        self.stream_stopped = True
        self.callback = None

    def submit(self, cid, symbol, qty, limit_price, extended_hours):
        self.clock.advance(self.submit_latency)
        ok, headers = self._admit("submit")
        if not ok:
            return Response(429, headers)
        self.submit_count += 1
        seq = self.submit_count
        self.extended_hours_flags.add(bool(extended_hours))
        if seq in self.reject_submit_seqs:
            return Response(self.reject_submit_seqs[seq], headers)
        order = self._create(cid, symbol, limit_price)
        if seq in self.silent_submit_seqs:
            self._silent_cids.add(cid)
        self._emit("new", order)
        if seq in self.fill_submit_seqs:
            order.update(status="filled", filled_qty="1")
            self._emit("fill", order)
        if self.crash_on_submit_seq == seq:
            raise RuntimeError("fixture port defect")
        if self.ghost_order and seq == 1:
            self._create(cid[:-6] + "999999", symbol, limit_price, status="canceled")
        if seq in self.lost_response_seqs:
            return Response(self.lost_response_seqs[seq], {}, error="response_lost")
        return Response(200, headers, order=dict(order))

    def cancel(self, order_id):
        self.clock.advance(self.cancel_latency)
        ok, headers = self._admit("cancel")
        if not ok:
            return Response(429, headers)
        order = self._by_id(order_id)
        if order is None:
            return Response(404, headers)
        if order["status"] in {"filled", "canceled", "expired", "rejected"}:
            return Response(422, headers)
        order["status"] = "canceled"
        self._emit("canceled", order)
        return Response(204, headers)

    def cancel_all(self):
        self.clock.advance(self.cancel_latency)
        ok, headers = self._admit("cancel")
        if not ok:
            return Response(429, headers)
        self.cancel_all_calls += 1
        for order in self.orders.values():
            if order["status"] not in {"filled", "canceled", "expired", "rejected"}:
                order["status"] = "canceled"
                self._emit("canceled", order)
        return Response(207, headers)

    def list_orders(self, status, after_wall, admit=None):
        rows = []
        for cid, order in self.orders.items():
            if any(cid.endswith("%06d" % seq) for seq in self.hide_from_listing):
                continue
            row = {k: v for k, v in order.items() if k != "created_at_wall"}
            for seq, override in self.listing_status_override.items():
                if cid.endswith("%06d" % seq):
                    row["status"] = override
                    if override == "filled":
                        row["filled_qty"] = row["qty"]
            if status == "open" and row["status"] in {"filled", "canceled", "expired", "rejected", "replaced"}:
                continue
            if after_wall is not None and order["created_at_wall"] <= after_wall:
                continue
            rows.append(row)
        # Paged like the native port: every page is one trading call, and every
        # page after the first needs admit() first.
        size = self.page_size or max(1, len(rows))
        listed, responses = [], []
        for index, start in enumerate(range(0, max(1, len(rows)), size)):
            if index and admit is not None and not admit():
                return listed, False, responses
            self.clock.advance(self.read_latency)
            ok, headers = self._admit("read")
            responses.append(Response(200 if ok else 429, headers))
            if not ok:
                return listed, False, responses
            listed.extend(rows[start:start + size])
        return listed, True, responses

    def positions(self):
        self.clock.advance(self.read_latency)
        ok, headers = self._admit("read")
        if not ok:
            return [], [Response(429, headers)]
        held = [dict(p) for p in self._positions]
        filled = sum(Decimal(o["filled_qty"]) for o in self.orders.values() if o["symbol"] == self.symbol)
        if filled:
            for row in held:
                if row["symbol"] == self.symbol:
                    row["qty"] = str(Decimal(row["qty"]) + filled)
                    break
            else:
                held.append({"symbol": self.symbol, "qty": str(filled)})
        return held, [Response(200, headers)]

    # -- test helpers -----------------------------------------------------------
    def open_orders_with_prefix(self, prefix):
        return [o for cid, o in self.orders.items() if cid.startswith(prefix)
                and o["status"] not in {"filled", "canceled", "expired", "rejected", "replaced"}]
