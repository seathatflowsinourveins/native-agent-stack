"""Synthetic broker port for mover trials; no networking, credentials or paper orders.

Quotes follow a scripted path; a limit order fills when marketable against the
current quote (a buy at the ask when ask <= limit, a sell at the bid when bid >=
limit), otherwise it rests until a later quote makes it marketable or it is
canceled. ``partial_fill`` leaves part of a symbol's buy resting forever, to
exercise entry timeouts. This fixture does not model queue priority, market
impact, fees, halts, auctions or broker latency, and it is not evidence of fills a
real venue would give. Each fill is one execution: the streamed row carries its
execution_id, qty and price as transport.py forwards a trade_updates fill, and
fill_activities() returns an order's executions as the transport does.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal, ROUND_FLOOR
import inspect
import itertools
import secrets
import time
import uuid

_ORDER_IDS = itertools.count(1)


async def _invoke(callback, value):
    result = callback(value)
    if inspect.isawaitable(result):
        return await result
    return result


class MoverSimulatedPort:
    def __init__(self, controller, symbols, *, path, interval=0.02, partial_fill=None, cash="100000",
                 extended_hours_allowed=False):
        """``path(symbol, elapsed_seconds)`` returns ``(bid, ask)`` as Decimals, or None for
        no quote at that instant (a quote gap). ``partial_fill`` maps a symbol to the
        fraction of each buy that fills; the remainder never fills. Setting
        ``fill_sells`` False leaves every sell resting (no liquidity), to exercise the
        forced-recovery path.

        Intents follow transport.AlpacaPaperTransport's contract: ``submit`` and
        ``adopt_intents`` apply transport.normalize_intent against this port's symbols
        (an intent for an unsubscribed symbol raises TransportError), and ``cancel``
        requires an intent this port submitted or adopted."""
        self.controller, self.symbols = controller, tuple(sorted(set(symbols)))
        self.extended_hours_allowed = bool(extended_hours_allowed)
        self.path, self.interval = path, interval
        self.partial_fill = {k: Decimal(str(v)) for k, v in (partial_fill or {}).items()}
        self.fill_sells = True
        # Seconds every snapshot after the native adapter's startup one awaits before
        # returning, like the transport's REST round trips.
        self.snapshot_latency = 0.0
        self.snapshots = 0
        self.ready = False
        self.health = {"ready": False, "simulation": True, "reasons": [], "fresh_quotes": True,
                       "dropped_quotes": {}, "dropped_quotes_by_symbol": {}}
        self.orders, self.positions = {}, {}
        self.executions = {}   # broker order id -> executions, oldest first
        self.cash = Decimal(cash)
        self.quotes = {}
        self.payloads = []
        self.adopted = {}
        self._intents = {}   # client id -> normalized intent, as the transport keeps them
        self.started = self.stopped = 0
        self.on_quote = self.on_order = None
        self.task = None
        self.t0 = None
        self.id_prefix = "sim-" + secrets.token_hex(4)  # broker ids are unique across ports, as a broker's are

    def successor(self, symbols=None, *, fill_sells=True):
        """A new, unstarted port on the same synthetic account (orders, positions, cash)
        and quote timeline, as mover_runner builds a fresh transport for recovery. Intents
        this port submitted or adopted do not carry over; recovery must adopt them."""
        port = MoverSimulatedPort(self.controller, self.symbols if symbols is None else symbols, path=self.path,
                                  interval=self.interval, cash=format(self.cash, "f"),
                                  extended_hours_allowed=self.extended_hours_allowed)
        port.partial_fill = dict(self.partial_fill)
        port.orders, port.positions, port.t0 = self.orders, self.positions, self.t0
        port.executions = self.executions
        port.fill_sells, port.snapshot_latency = fill_sells, self.snapshot_latency
        return port

    def _normalize(self, order):
        from transport import normalize_intent
        return normalize_intent(order, self.symbols, allow_extended_hours=self.extended_hours_allowed)

    def adopt_intents(self, intents):
        """recovery.recover hands a fresh port its durable intents. As the transport does,
        each must normalize against this port's symbols; the order book itself persists
        across a stop/start (and across ports sharing it), as the broker's would."""
        from transport import TransportError
        for order in intents:
            normalized = self._normalize(order)
            key = normalized["client_order_id"]
            if key in self._intents and self._intents[key] != normalized:
                raise TransportError("durable intent changed")
            self._intents[key] = self.adopted[key] = normalized

    async def start(self, on_quote, on_order):
        """Start (or, for recovery.recover, restart) the scripted feed; orders, positions
        and cash persist across a stop/start, as the broker's would."""
        self.on_quote, self.on_order = on_quote, on_order
        self.started += 1
        if self.t0 is None:
            self.t0 = time.monotonic()
        self.ready = self.health["ready"] = True
        self.health["reasons"] = []

        async def feed():
            while self.ready:
                elapsed = time.monotonic() - self.t0
                for symbol in self.symbols:
                    point = self.path(symbol, elapsed)
                    if point is None:
                        continue
                    bid, ask = (Decimal(str(x)) for x in point)
                    quote = {"symbol": symbol, "bid": format(bid, "f"), "ask": format(ask, "f"),
                             "bid_size": "1000", "ask_size": "1000", "ts_ns": time.time_ns()}
                    self.quotes[symbol] = (bid, ask)
                    await _invoke(self.on_quote, quote)
                    await self._match(symbol)
                await asyncio.sleep(self.interval)

        self.task = asyncio.create_task(feed())

    async def stop(self):
        if not self.ready:
            return
        self.stopped += 1
        self.ready = self.health["ready"] = False
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    def freeze_health(self, reason):
        self.health.setdefault("reasons", []).append(str(reason))
        self.ready = self.health["ready"] = False

    async def _emit(self, order, execution=None):
        order["updated_at_ns"] = time.time_ns()
        row = self._public(order)
        if execution is not None:
            row.update(execution)
        self.controller.observe(dict(row))
        await _invoke(self.on_order, dict(row))

    async def fill_activities(self, order_id):
        await self.controller.before_request("read")
        return [dict(row) for row in self.executions.get(order_id, [])]

    def _fill_quantity(self, order):
        remaining = Decimal(order["qty"]) - Decimal(order["filled_qty"])
        if order["side"] != "buy" or order["symbol"] not in self.partial_fill:
            return remaining
        if order.get("_partial_done"):
            return Decimal(0)
        order["_partial_done"] = True
        target = (Decimal(order["qty"]) * self.partial_fill[order["symbol"]]).to_integral_value(rounding=ROUND_FLOOR)
        return max(Decimal(0), min(remaining, target - Decimal(order["filled_qty"])))

    async def _try_fill(self, order):
        if order["status"] not in ("new", "partially_filled"):
            return
        quote = self.quotes.get(order["symbol"])
        if quote is None:
            return
        bid, ask = quote
        limit = Decimal(order["limit_price"])
        if order["side"] == "buy" and ask <= limit:
            price = ask
        elif order["side"] == "sell" and bid >= limit and self.fill_sells:
            price = bid
        else:
            return
        quantity = self._fill_quantity(order)
        if quantity <= 0:
            return
        held = self.positions.get(order["symbol"], Decimal(0))
        if order["side"] == "sell" and quantity > held:
            raise RuntimeError("simulation_oversell")
        filled_before = Decimal(order["filled_qty"])
        value_before = filled_before * Decimal(order["filled_avg_price"] or 0)
        filled = filled_before + quantity
        order["filled_avg_price"] = format((value_before + quantity * price) / filled, "f")
        order["filled_qty"] = format(filled, "f")
        order["status"] = "filled" if filled == Decimal(order["qty"]) else "partially_filled"
        self.positions[order["symbol"]] = held + (quantity if order["side"] == "buy" else -quantity)
        self.cash += (-quantity if order["side"] == "buy" else quantity) * price
        execution_id = str(uuid.uuid4())
        self.executions.setdefault(order["id"], []).append(
            {"trade_id": execution_id, "qty": format(quantity, "f"), "price": format(price, "f"),
             "cum_qty": format(filled, "f"), "symbol": order["symbol"], "side": order["side"],
             "transaction_time_ns": time.time_ns(), "source": "activity"})
        await self._emit(order, {"event": "partial_fill" if order["status"] == "partially_filled" else "fill",
                                 "execution_id": execution_id, "event_qty": format(quantity, "f"),
                                 "event_price": format(price, "f")})

    async def _match(self, symbol):
        for order in list(self.orders.values()):
            if order["symbol"] == symbol:
                await self._try_fill(order)

    async def submit(self, payload):
        intent = self._normalize(payload)
        self.controller.before_submit(payload)
        self._intents[intent["client_order_id"]] = intent
        await self.controller.before_request("submit", client_id=payload["client_order_id"])
        self.payloads.append(dict(payload))
        order = {key: payload[key] for key in ("client_order_id", "symbol", "side", "qty", "limit_price")}
        order.update(id=f"{self.id_prefix}-{next(_ORDER_IDS)}", status="new", filled_qty="0", filled_avg_price=None,
                     updated_at_ns=time.time_ns())
        self.orders[payload["client_order_id"]] = order
        await self._emit(order)
        await self._try_fill(order)
        return self._public(order)

    async def cancel(self, client_id):
        if client_id not in self._intents:
            from transport import TransportError
            raise TransportError("cancellation requires an owned durable intent")
        await self.controller.before_request("cancel")
        order = self.orders.get(client_id)
        if order is None:
            return None
        if order["status"] in ("new", "partially_filled"):
            order["status"] = "canceled"
            await self._emit(order)
        return self._public(order)

    @staticmethod
    def _public(order):
        return {key: value for key, value in order.items() if not key.startswith("_")}

    async def snapshot(self):
        """State is captured first and returned after ``snapshot_latency``, as the
        transport's REST reads collect account, positions and orders and only then return."""
        await self.controller.before_request("read")
        self.snapshots += 1
        result = {"account": {"cash": format(self.cash, "f"), "equity": format(self.cash, "f"),
                              "buying_power": format(self.cash, "f")},
                  "orders": [self._public(order) for order in self.orders.values()],
                  "positions": [{"symbol": symbol, "qty": format(qty, "f"), "avg_entry_price": "0"}
                                for symbol, qty in self.positions.items() if qty],
                  "complete": True}
        if self.snapshot_latency and self.snapshots > 1:
            await asyncio.sleep(self.snapshot_latency)
        return result


def piecewise_path(points):
    """A scripted mid path: ``points`` maps symbol -> [(elapsed_seconds, mid, spread), ...]
    (ascending). Between points the mid is linear; before the first and after the last
    the endpoint holds. Returns ``(bid, ask)`` on the price tick grid."""
    prepared = {symbol: [(float(t), Decimal(str(mid)), Decimal(str(spread))) for t, mid, spread in rows]
                for symbol, rows in points.items()}

    def path(symbol, elapsed):
        rows = prepared.get(symbol)
        if not rows:
            return None
        if elapsed <= rows[0][0]:
            _, mid, spread = rows[0]
        elif elapsed >= rows[-1][0]:
            _, mid, spread = rows[-1]
        else:
            for (t1, m1, s1), (t2, m2, s2) in zip(rows, rows[1:]):
                if t1 <= elapsed <= t2:
                    weight = Decimal(str((elapsed - t1) / (t2 - t1)))
                    mid, spread = m1 + (m2 - m1) * weight, s1
                    break
        tick = Decimal("0.01") if mid >= 1 else Decimal("0.0001")
        bid = ((mid - spread / 2) / tick).to_integral_value(rounding=ROUND_FLOOR) * tick
        ask = bid + max(tick, (spread / tick).to_integral_value(rounding=ROUND_FLOOR) * tick)
        return bid, ask

    return path
