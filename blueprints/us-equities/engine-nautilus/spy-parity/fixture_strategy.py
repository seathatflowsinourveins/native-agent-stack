#!/usr/bin/env python3
"""Minimal native fixture strategy for the frozen ``one_zero`` SPY case.

Decision semantics reproduced from the frozen plan:

* the intent is formed on the completed 16:00 New York bar (the hourly row whose
  local start is 15:00), sized ``floor(equity * target * 0.98 / price)`` with the
  decision bar's close as the decision price and integer shares;
* the order is submitted on a strictly later bar - the first completed bar of the
  next session - so no fill can consume the decision bar;
* accounting is ``Decimal`` throughout; nothing is inferred from float reports.

Two mapping rows could not be expressed on the pinned engine and are recorded
here rather than approximated (see ``mapping-manifest.json``):

* ``market_on_open_proxy`` is **unsupported**. ``TimeInForce.AT_THE_OPEN`` is
  rejected by the pinned simulated exchange, and a market order pending before a
  bar still fills at that bar's close. The fixture therefore fills at the close
  of the next session's first hourly bar, which reproduces LEAN's fill *instant*
  (10:00 New York) but not LEAN's fill *price* (that bar's open). The resulting
  price difference is a declared deviation, never a tolerance.
* ``distributions_and_cash`` is **unsupported**. The pinned wheel exposes no
  dividend or cash-distribution mechanism, so no balancing cash entry is injected
  into the engine. Distribution cash is kept as a separate external ``Decimal``
  ledger and reported beside the native account, never merged into it silently.

Nautilus is imported inside ``build_strategy`` so the pure decision, causality
and ledger helpers stay importable without the engine.
"""
from __future__ import annotations

from decimal import Decimal

DECISION_LOCAL_START = "15:00"  # the hourly row that completes at 16:00 New York
MARKET_ON_OPEN_PROXY = "unsupported"
NATIVE_CASH_POSTING = "unsupported"


def decision_rows(rows, decision_dates) -> dict:
    """Locate the completed 16:00 New York bar for each frozen decision date."""
    found = {}
    for row in rows:
        if row["session_date"] in decision_dates and row["local_start"] == DECISION_LOCAL_START:
            if row["session_date"] in found:
                raise ValueError("duplicate_decision_bar:" + row["session_date"])
            found[row["session_date"]] = row
    missing = [d for d in decision_dates if d not in found]
    if missing:
        raise ValueError("missing_decision_bar:" + ",".join(missing))
    return found


def target_quantity(equity: Decimal, target: Decimal, buffer: Decimal, price: Decimal) -> int:
    """``floor(equity * target * buffer / price)`` in whole shares."""
    if price <= 0:
        raise ValueError("nonpositive_decision_price")
    return int((equity * target * buffer / price).to_integral_value(rounding="ROUND_FLOOR"))


def check_causality(intents, fills) -> None:
    """Look-ahead guard: every fill strictly follows its own decision instant.

    A fill at or before its decision bar's close means the decision bar was used
    to execute, which the acceptance plan forbids. Quantity is accumulated per
    order reference, so a sequence of partial fills that together exceed the
    intent is refused even when no single fill does.
    """
    by_order = {}
    for intent in intents:
        if intent["order_ref"] in by_order:
            raise ValueError("duplicate_intent_reference:" + str(intent["order_ref"]))
        by_order[intent["order_ref"]] = intent
    filled = {}
    for fill in fills:
        intent = by_order.get(fill["order_ref"])
        if intent is None:
            raise ValueError("unattributed_fill:" + str(fill["order_ref"]))
        if fill["utc_seconds"] <= intent["utc_seconds"]:
            raise ValueError("look_ahead_fill:" + str(fill["order_ref"]))
        if (fill["quantity"] > 0) != (intent["quantity"] > 0):
            raise ValueError("fill_side_mismatch:" + str(fill["order_ref"]))
        cumulative = filled.get(fill["order_ref"], Decimal(0)) + Decimal(fill["quantity"])
        filled[fill["order_ref"]] = cumulative
        if abs(cumulative) > abs(Decimal(intent["quantity"])):
            raise ValueError("fill_exceeds_intent:" + str(fill["order_ref"]))


def assert_commission(fee, expected, currency: str, expected_currency: str) -> None:
    """Read the native commission back and refuse anything but the frozen cost."""
    if str(currency) != str(expected_currency):
        raise ValueError("unexpected_commission_currency:" + str(currency))
    if Decimal(fee) != Decimal(expected):
        raise ValueError("unexpected_commission:" + str(fee))


def check_run_integrity(errors, bars_seen: int, expected_bars: int, iterations) -> None:
    """Surface a guard that fired inside a strategy callback.

    The pinned engine catches and logs an exception raised inside a strategy
    callback: a raise in ``on_bar`` does not stop ``engine.run()`` and does not
    reach the caller. Each callback therefore records its failure on the strategy
    before re-raising, and the runner refuses the run here. Without this the
    fixture's own guards would be silently ineffective.
    """
    if errors:
        raise ValueError("strategy_callback_failed:" + ";".join(str(e) for e in errors))
    if bars_seen != expected_bars:
        raise ValueError("bars_not_fully_processed:" + str(bars_seen) + "/" + str(expected_bars))
    if iterations is not None and int(iterations) != expected_bars:
        raise ValueError("engine_iterations_mismatch:" + str(iterations))


def check_final_state(pending, open_orders: int, open_positions: int, position) -> None:
    """Refuse a run that ended with unsubmitted intent or unresolved exposure."""
    if pending is not None:
        raise ValueError("unsubmitted_pending_intent:" + str(pending.get("order_ref")))
    if open_orders:
        raise ValueError("open_orders_at_end:" + str(open_orders))
    if open_positions:
        raise ValueError("open_positions_at_end:" + str(open_positions))
    if Decimal(position) != 0:
        raise ValueError("nonflat_final_position:" + str(position))


def distribution_ledger(distributions, fills) -> list[dict]:
    """Eligible holdings and cash per derived distribution.

    ``engine_posted`` stays false: the pinned engine has no cash-distribution
    mechanism, so this ledger is external evidence beside the native account.
    """
    ledger = []
    for distribution in distributions:
        held = sum((Decimal(f["quantity"]) for f in fills
                    if f["utc_seconds"] <= distribution["utc_seconds"]), Decimal(0))
        per_share = Decimal(distribution["per_share"])
        ledger.append({"ex_date": distribution["ex_date"],
                       "utc_seconds": distribution["utc_seconds"],
                       "per_share": str(per_share), "quantity": str(held),
                       "amount": str(held * per_share), "engine_posted": False})
    return ledger


def cash_ledger(initial_cash: Decimal, fills, distributions) -> list[dict]:
    """Independent ``Decimal`` cash at every economic event, in time order."""
    events = [{"kind": "fill", "utc_seconds": f["utc_seconds"],
               "delta": -Decimal(f["quantity"]) * Decimal(f["price"]) - Decimal(f["fee"]),
               "detail": f} for f in fills]
    events += [{"kind": "distribution", "utc_seconds": d["utc_seconds"],
                "delta": Decimal(d["amount"]), "detail": d} for d in distributions]
    events.sort(key=lambda e: (e["utc_seconds"], 0 if e["kind"] == "distribution" else 1))
    cash, ledger = Decimal(initial_cash), []
    for event in events:
        cash += event["delta"]
        ledger.append({"kind": event["kind"], "utc_seconds": event["utc_seconds"],
                       "delta": str(event["delta"]), "cash": str(cash)})
    return ledger


def build_strategy(equity_id, bar_type_str, rows, case):
    """Return the native Strategy class bound to this frozen case."""
    from nautilus_trader.config import StrategyConfig
    from nautilus_trader.model import BarType, OrderSide, Quantity
    from nautilus_trader.trading import Strategy

    bar_type = BarType.from_str(bar_type_str)
    decisions = decision_rows(rows, [case["entry_decision_date"], case["exit_decision_date"]])
    target = Decimal(case["target"])
    buffer = Decimal(case["sizing_buffer"])
    initial_cash = Decimal(case["initial_cash_usd"])

    class OneZeroFixture(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.intents = []
            self.fills = []
            self.errors = []
            self.order_events = []
            self.buying_power_events = []
            self.latch_events = []
            self.pending = None
            self.position = Decimal(0)
            self.cash = initial_cash
            self.order_ref = 0
            self.submitted = {}
            self.bars_seen = 0
            self.last_session = None

        def on_start(self):
            self.subscribe_bars(bar_type)

        def _record(self, callback, error):
            """The engine swallows callback exceptions; keep the evidence."""
            self.errors.append(callback + ":" + type(error).__name__ + ": " + str(error))

        def on_bar(self, bar):
            try:
                self._handle_bar(bar)
            except BaseException as error:
                self._record("on_bar", error)
                raise

        def on_order_event(self, event):
            try:
                self._handle_order_event(event)
            except BaseException as error:
                self._record("on_order_event", error)
                raise

        def _handle_bar(self, bar):
            self.bars_seen += 1
            row = rows[self.bars_seen - 1]
            if row["ts_event_ns"] != bar.ts_event:
                raise ValueError("bar_stream_desync:" + row["session_date"])
            # Submit a decision taken on an earlier session on the first bar of
            # the next session. This is strictly after the decision bar.
            if self.pending is not None and row["session_date"] != self.pending["session_date"]:
                self._submit(row)
            if row["local_start"] == DECISION_LOCAL_START and row["session_date"] in decisions:
                self._decide(row)
            self.last_session = row["session_date"]

        def _decide(self, row):
            price = Decimal(row["c"])
            equity = self.cash + self.position * price
            wanted = (target_quantity(equity, target, buffer, price)
                      if row["session_date"] == case["entry_decision_date"] else 0)
            delta = Decimal(wanted) - self.position
            if delta == 0:
                return
            self.order_ref += 1
            self.intents.append({
                "kind": "intent", "order_ref": self.order_ref, "utc_seconds": row["ts_event_ns"] // 10 ** 9,
                "ts_event_ns": row["ts_event_ns"], "session_date": row["session_date"],
                "quantity": int(delta), "target": str(target if wanted else Decimal(0)),
                "decision_price": str(price), "decision_equity": str(equity),
                "reason": "entry" if wanted else "exit"})
            self.pending = {"order_ref": self.order_ref, "quantity": int(delta),
                            "session_date": row["session_date"]}

        def _submit(self, row):
            pending = self.pending
            self.pending = None
            side = OrderSide.BUY if pending["quantity"] > 0 else OrderSide.SELL
            order = self.order_factory.market(equity_id, side, Quantity.from_int(abs(pending["quantity"])))
            self.submitted[order.client_order_id.value] = {
                "order_ref": pending["order_ref"], "submitted_session": row["session_date"],
                "submitted_ts_event_ns": row["ts_event_ns"]}
            self.submit_order(order)

        def _handle_order_event(self, event):
            name = type(event).__name__
            record = {"event": name, "ts_event_ns": event.ts_event,
                      "client_order_id": getattr(event, "client_order_id", None)}
            record["client_order_id"] = str(record["client_order_id"])
            self.order_events.append(record)
            reason = str(getattr(event, "reason", "") or "")
            if name in ("OrderDenied", "OrderRejected"):
                self.buying_power_events.append({**record, "reason": reason})
            if name != "OrderFilled":
                return
            mapped = self.submitted.get(str(event.client_order_id))
            if mapped is None:
                raise ValueError("unmapped_fill:" + str(event.client_order_id))
            signed = Decimal(str(event.last_qty)) * (1 if str(event.order_side) == "BUY" else -1)
            price = Decimal(str(event.last_px))
            commission = str(event.commission) if event.commission is not None else "0 " + case["currency"]
            fee = Decimal(commission.split()[0])
            assert_commission(fee, case["fee_usd"], commission.split()[-1], case["currency"])
            self.position += signed
            self.cash += -signed * price - fee
            self.fills.append({"order_ref": mapped["order_ref"], "utc_seconds": event.ts_event // 10 ** 9,
                               "ts_event_ns": event.ts_event, "quantity": int(signed), "price": str(price),
                               "fee": str(fee), "instrument_id": str(event.instrument_id),
                               "currency": str(event.currency), "side": str(event.order_side),
                               "venue_order_id": str(event.venue_order_id),
                               "submitted_session": mapped["submitted_session"],
                               "fill_source": "next_session_first_bar_close",
                               "market_on_open_proxy": MARKET_ON_OPEN_PROXY})

    return OneZeroFixture
