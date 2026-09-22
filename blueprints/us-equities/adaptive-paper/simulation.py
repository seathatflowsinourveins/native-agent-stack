"""Synthetic broker port for native integration/throughput checks; no networking.

This fixture does not model queue priority, market impact, fees, corporate
actions, fills missed during disconnect, or profitable strategy performance.
"""
from __future__ import annotations
import asyncio
from decimal import Decimal
import inspect
import time


async def invoke(fn, value):
    result = fn(value)
    if inspect.isawaitable(result):
        return await result
    return result


class SimulatedPort:
    def __init__(self, controller, symbols, *, interval=.02, price=None):
        self.controller, self.symbols = controller, symbols
        self.interval, self.price = interval, price or (lambda symbol, tick: Decimal("100"))
        self.ready = False
        self.health = {"ready": False, "simulation": True}
        self.orders, self.positions = {}, {}
        self.cash = Decimal("100000")
        self.started = self.stopped = 0
        self.ticks = 0
        self.submitted_at = []
        self.on_quote = self.on_order = None
        self.task = None

    async def start(self, on_quote, on_order):
        self.on_quote, self.on_order = on_quote, on_order
        self.started += 1
        self.ready = self.health["ready"] = True
        async def feed():
            while self.ready:
                for symbol in self.symbols:
                    mid = self.price(symbol, self.ticks)
                    quote = {"symbol": symbol, "bid": str(mid - Decimal(".01")),
                             "ask": str(mid + Decimal(".01")), "bid_size": "1000",
                             "ask_size": "1000", "ts_ns": time.time_ns()}
                    self.controller.quote(quote)
                    await invoke(self.on_quote, quote)
                self.ticks += 1
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
        self.health["reason"] = reason
        self.ready = False

    async def submit(self, payload):
        self.controller.before_submit(payload)
        await self.controller.before_request("submit", client_id=payload["client_order_id"])
        self.submitted_at.append(time.time())
        qty, price = Decimal(payload["qty"]), Decimal(payload["limit_price"])
        symbol, side = payload["symbol"], payload["side"]
        order = dict(payload, id=f"sim-{len(self.orders)+1}", status="filled", filled_qty=str(qty),
                     filled_avg_price=str(price), updated_at_ns=time.time_ns())
        old_qty = self.positions.get(symbol, {}).get("qty", Decimal(0))
        new_qty = old_qty + (qty if side == "buy" else -qty)
        if new_qty < 0:
            raise RuntimeError("simulation_oversell")
        self.positions[symbol] = {"symbol": symbol, "qty": new_qty, "avg_entry_price": str(price)}
        self.cash += (-qty if side == "buy" else qty) * price
        self.orders[payload["client_order_id"]] = order
        self.controller.observe(order)
        await invoke(self.on_order, dict(order))
        return dict(order)

    async def cancel(self, client_id):
        await self.controller.before_request("cancel")
        return self.orders.get(client_id)

    async def snapshot(self):
        await self.controller.before_request("read")
        return {"account": {"cash": str(self.cash), "equity": str(self.cash), "buying_power": str(self.cash)},
                "orders": list(self.orders.values()),
                "positions": [{**p, "qty": str(p["qty"])} for p in self.positions.values() if p["qty"]],
                "complete": True}
