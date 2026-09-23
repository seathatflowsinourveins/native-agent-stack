#!/usr/bin/env python3
"""Minimal native fixture strategy for the frozen ``one_zero`` SPY case.

Decision semantics reproduced from the frozen plan:

* the intent is formed on the completed 16:00 New York bar (the hourly row whose
  local start is 15:00), sized ``floor(equity * target * 0.98 / price)`` with the
  decision bar's close as the decision price and integer shares;
* no fill may consume the decision bar (``check_causality``);
* accounting is ``Decimal`` throughout; nothing is inferred from float reports.

Mapping manifest v2 (``mapping-manifest-v2.json``) preregisters the two rows v1
declared unsupported, and this fixture implements them exactly as specified:

* ``market_on_open_proxy`` (**preregistered**): from the decision bar's own
  ``on_bar`` the fixture submits one native OCO pair (``ContingencyType.OCO``,
  one ``order_list_id``, reciprocal ``linked_order_ids``) of a STOP_MARKET and a
  MARKET_IF_TOUCHED order in the intent's direction, each for the full intent
  quantity, ``GTC``, ``TriggerType.DEFAULT``, not reduce-only, with triggers at
  the decision close +/- one tick (0.0001). The matching engine's gap-open trade
  tick fills whichever leg the next session's first-bar open crosses, at that
  open, and the engine's OCO contingency cancels the sibling. No order is
  submitted on a later bar, no tick or bar is injected, and no strategy-level
  cancel stands in for the native OCO. The proxy is only faithful when the open
  differs from the decision close by at least one tick; ``compare.py`` checks
  that per event.
* ``distributions_and_cash`` (**preregistered**): cash is posted by the venue's
  ``DistributionModule`` (``distribution_module.py``), never by this strategy.
  The strategy only registers one no-op time alert at each ex-date instant so the
  engine has a timestamp at which to run its venue modules there.

Nautilus is imported inside ``build_strategy`` so the pure decision, causality
and ledger helpers stay importable without the engine.
"""
from __future__ import annotations

from decimal import Decimal

DECISION_LOCAL_START = "15:00"  # the hourly row that completes at 16:00 New York
MARKET_ON_OPEN_PROXY = "preregistered"
NATIVE_CASH_POSTING = "preregistered"
TICK = Decimal("0.0001")  # the instrument's declared price_increment
STOP_MARKET = "STOP_MARKET"
MARKET_IF_TOUCHED = "MARKET_IF_TOUCHED"


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


def oco_triggers(quantity: int, close: Decimal, tick: Decimal = TICK) -> dict:
    """Trigger prices of the market_on_open_proxy pair from the decision close.

    BUY: stop at C + tick, MIT at C - tick. SELL: stop at C - tick, MIT at C + tick.
    Both lie strictly outside the engine's last price C, so neither leg can fill
    on the decision bar, and they depend on nothing later than that close.
    """
    if quantity == 0:
        raise ValueError("zero_intent_quantity")
    close, tick = Decimal(close), Decimal(tick)
    if quantity > 0:
        return {STOP_MARKET: close + tick, MARKET_IF_TOUCHED: close - tick}
    return {STOP_MARKET: close - tick, MARKET_IF_TOUCHED: close + tick}


ENGINE_ORDER_FIELDS = ("client_order_id", "type", "side", "quantity", "status", "trigger_price",
                       "trigger_type", "time_in_force", "is_reduce_only", "contingency_type",
                       "order_list_id", "linked_order_ids", "filled_qty")


def engine_order_view(snapshot: dict) -> dict:
    """The structural fields of an order as the engine's cache serializes it.

    ``snapshot`` is ``order.to_dict()`` of the order read back from the engine's
    cache, never the harness's own submission record. A missing field refuses.
    """
    missing = [field for field in ENGINE_ORDER_FIELDS if field not in snapshot]
    if missing:
        raise ValueError("engine_order_view_missing:" + ",".join(missing))
    view = {field: snapshot[field] for field in ENGINE_ORDER_FIELDS}
    view["linked_order_ids"] = [str(i) for i in (view["linked_order_ids"] or [])]
    return view


def attach_engine_views(oco_pairs, at_accept: dict, final: dict) -> list:
    """Each OCO leg with the engine's cache view at OrderAccepted and at run end.

    The leg's other fields are the harness's submission record; ``compare.py``
    judges the native OCO structure only from these engine views.
    """
    attached = []
    for pair in oco_pairs:
        legs = [{**leg, "engine_at_accept": at_accept.get(leg["client_order_id"]),
                 "engine_final": final.get(leg["client_order_id"])} for leg in pair["legs"]]
        attached.append({**pair, "legs": legs})
    return attached


def check_decision_bar_is_session_final(rows, index: int) -> None:
    """The pair must rest when the next session's first bar is processed."""
    row = rows[index]
    if index + 1 >= len(rows):
        raise ValueError("decision_bar_is_last_row:" + row["session_date"])
    if rows[index + 1]["session_date"] == row["session_date"]:
        raise ValueError("decision_bar_not_session_final:" + row["session_date"])


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
    """External cross-check: holdings implied by the fixture's own fills.

    Never used to post or size a distribution. v2 posts through the venue's
    ``DistributionModule``, whose eligible quantity is the engine's own position
    (see ``posted_distribution_ledger``); this ledger only lets the receipt show
    that the two agree.
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


def posted_distribution_ledger(emissions, acknowledgements) -> list[dict]:
    """The distribution ledger as the engine posted it through the module.

    ``engine_posted`` is true only when the emission was on time and every
    acknowledgement outcome for its ex-date reports ``applied`` with no error.
    """
    applied = {}
    for record in acknowledgements:
        ok = bool(record["outcomes"]) and all(o["applied"] and o["error"] is None
                                              for o in record["outcomes"])
        for ex_date in record["ex_dates"]:
            applied[ex_date] = ok
    return [{"ex_date": e["ex_date"], "utc_seconds": e["ts_now_ns"] // 10 ** 9,
             "ts_event_ns": e["ts_now_ns"], "per_share": e["per_share"],
             "quantity": str(e["eligible_quantity"]), "amount": e["amount"],
             "engine_posted": bool(e["on_time"] and applied.get(e["ex_date"], False)),
             "source": "DistributionModule.process"} for e in emissions]


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


def build_strategy(equity_id, bar_type_str, rows, case, ex_instants_ns=()):
    """Return the native Strategy class bound to this frozen case.

    ``ex_instants_ns`` are the DistributionModule's ex-date instants; the
    strategy registers one no-op time alert at each and does nothing else there.
    """
    from nautilus_trader.config import StrategyConfig
    from nautilus_trader.core import UUID4
    from nautilus_trader.model import (BarType, ClientOrderId, ContingencyType, MarketIfTouchedOrder,
                                       OrderListId, OrderSide, Price, Quantity, StopMarketOrder,
                                       TimeInForce, TriggerType)
    from nautilus_trader.trading import Strategy

    bar_type = BarType.from_str(bar_type_str)
    decisions = decision_rows(rows, [case["entry_decision_date"], case["exit_decision_date"]])
    target = Decimal(case["target"])
    buffer = Decimal(case["sizing_buffer"])
    initial_cash = Decimal(case["initial_cash_usd"])
    alerts = [int(ns) for ns in ex_instants_ns]
    price_format = "." + str(-TICK.as_tuple().exponent) + "f"

    class OneZeroFixture(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.intents = []
            self.fills = []
            self.errors = []
            self.order_events = []
            self.buying_power_events = []
            self.latch_events = []
            self.oco_pairs = []
            self.alerts_registered = []
            self.alerts_fired = []
            self.pending = None
            self.position = Decimal(0)
            self.cash = initial_cash
            self.order_ref = 0
            self.submitted = {}
            self.accepted_orders = {}
            self.bars_seen = 0
            self.last_session = None

        def on_start(self):
            try:
                self.subscribe_bars(bar_type)
                for instant in alerts:
                    name = "ex_date_" + str(instant)
                    self.clock.set_time_alert_ns(name, instant, self._on_ex_date_alert, allow_past=False)
                    self.alerts_registered.append({"name": name, "alert_time_ns": instant})
            except BaseException as error:
                self._record("on_start", error)
                raise

        def _on_ex_date_alert(self, event):
            # No-op by design: the alert only gives the engine a timestamp at
            # which run_venue_modules executes. No cash, order or state change.
            self.alerts_fired.append({"name": str(event.name), "ts_event_ns": int(event.ts_event)})

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
            index = self.bars_seen - 1
            row = rows[index]
            if row["ts_event_ns"] != bar.ts_event:
                raise ValueError("bar_stream_desync:" + row["session_date"])
            if row["local_start"] == DECISION_LOCAL_START and row["session_date"] in decisions:
                check_decision_bar_is_session_final(rows, index)
                if Decimal(str(bar.close)) != Decimal(row["c"]):
                    raise ValueError("decision_close_mismatch:" + row["session_date"])
                self._decide(row)
            self.last_session = row["session_date"]

        def _decide(self, row):
            price = Decimal(row["c"])
            # The unchanged v1 sizing rule. self.cash moves only on fills, so it
            # leaves out cash the DistributionModule posts: one_zero's exit
            # decision_equity is 428.64 below LEAN's portfolio value. The exit
            # target is 0 and the entry precedes any distribution, so one_zero
            # is unaffected; a case that sizes after an ex-date would not be.
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
            self._submit_oco(self.order_ref, int(delta), price, row)

        def _submit_oco(self, order_ref, quantity, close, row):
            """Submit the preregistered native OCO pair from the decision bar."""
            triggers = oco_triggers(quantity, close)
            side = OrderSide.BUY if quantity > 0 else OrderSide.SELL
            list_id = OrderListId("OL-" + str(order_ref))
            ids = {STOP_MARKET: ClientOrderId("O-" + str(order_ref) + "-STOP"),
                   MARKET_IF_TOUCHED: ClientOrderId("O-" + str(order_ref) + "-MIT")}
            ts_init = self.clock.timestamp_ns()
            common = dict(trader_id=self.trader_id, strategy_id=self.strategy_id,
                          instrument_id=equity_id, order_side=side,
                          quantity=Quantity.from_int(abs(quantity)),
                          trigger_type=TriggerType.DEFAULT, time_in_force=TimeInForce.GTC,
                          reduce_only=False, quote_quantity=False, ts_init=ts_init,
                          contingency_type=ContingencyType.OCO, order_list_id=list_id)
            stop = StopMarketOrder(
                client_order_id=ids[STOP_MARKET],
                trigger_price=Price.from_str(format(triggers[STOP_MARKET], price_format)),
                init_id=UUID4(), linked_order_ids=[ids[MARKET_IF_TOUCHED]], **common)
            touched = MarketIfTouchedOrder(
                client_order_id=ids[MARKET_IF_TOUCHED],
                trigger_price=Price.from_str(format(triggers[MARKET_IF_TOUCHED], price_format)),
                init_id=UUID4(), linked_order_ids=[ids[STOP_MARKET]], **common)
            legs = []
            for leg_type, order in ((STOP_MARKET, stop), (MARKET_IF_TOUCHED, touched)):
                sibling = MARKET_IF_TOUCHED if leg_type == STOP_MARKET else STOP_MARKET
                self.submitted[order.client_order_id.value] = {
                    "order_ref": order_ref, "leg": leg_type, "order_list_id": list_id.value,
                    "trigger_price": str(order.trigger_price), "submitted_session": row["session_date"],
                    "submitted_ts_event_ns": row["ts_event_ns"]}
                legs.append({"client_order_id": order.client_order_id.value, "order_type": leg_type,
                             "side": "BUY" if quantity > 0 else "SELL", "quantity": abs(quantity),
                             "trigger_price": str(order.trigger_price),
                             "expected_trigger_price": format(triggers[leg_type], price_format),
                             "trigger_type": "DEFAULT", "time_in_force": "GTC", "reduce_only": False,
                             "contingency_type": "OCO", "order_list_id": list_id.value,
                             "linked_order_ids": [ids[sibling].value]})
            self.oco_pairs.append({"order_ref": order_ref, "order_list_id": list_id.value,
                                   "reference_close": str(close),
                                   "decision_session": row["session_date"],
                                   "submitted_ts_event_ns": row["ts_event_ns"],
                                   "submitted_clock_ns": ts_init, "legs": legs})
            self.submit_order(stop)
            self.submit_order(touched)

        def _handle_order_event(self, event):
            name = type(event).__name__
            client_order_id = str(getattr(event, "client_order_id", None))
            mapped = self.submitted.get(client_order_id)
            record = {"event": name, "ts_event_ns": event.ts_event, "client_order_id": client_order_id,
                      "order_ref": mapped["order_ref"] if mapped else None,
                      "leg": mapped["leg"] if mapped else None,
                      "order_list_id": mapped["order_list_id"] if mapped else None}
            reason = str(getattr(event, "reason", "") or "")
            if name in ("OrderDenied", "OrderRejected", "OrderCanceled", "OrderModifyRejected",
                        "OrderCancelRejected", "OrderExpired"):
                record["reason"] = reason
            if name == "OrderFilled":
                record["last_qty"] = str(event.last_qty)
                record["last_px"] = str(event.last_px)
            self.order_events.append(record)
            if name == "OrderAccepted":
                # Read the accepted order back from the engine's cache so the
                # OCO structure is judged from the engine's record, not from
                # the strings this strategy wrote when it built the order.
                order = self.cache.order(event.client_order_id)
                if order is None:
                    raise ValueError("accepted_order_not_in_cache:" + client_order_id)
                self.accepted_orders[client_order_id] = engine_order_view(order.to_dict())
            if name in ("OrderDenied", "OrderRejected"):
                self.buying_power_events.append({**record, "reason": reason})
            if name != "OrderFilled":
                return
            if mapped is None:
                raise ValueError("unmapped_fill:" + client_order_id)
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
                               "client_order_id": client_order_id, "leg": mapped["leg"],
                               "order_list_id": mapped["order_list_id"],
                               "trigger_price": mapped["trigger_price"],
                               "submitted_session": mapped["submitted_session"],
                               "fill_source": "native_oco_leg",
                               "market_on_open_proxy": MARKET_ON_OPEN_PROXY})

    return OneZeroFixture
