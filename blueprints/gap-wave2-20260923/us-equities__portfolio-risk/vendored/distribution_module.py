#!/usr/bin/env python3
"""Native cash-distribution ``SimulationModule`` for the v2 ``one_zero`` replay.

Implements ``distributions_and_cash.mechanism_rules`` of
``mapping-manifest-v2.json`` and nothing else:

* events are derived from the frozen factor file and the retained daily session
  list only. For consecutive factor rows ``(d0, pf0, ref0)`` and ``(d1, pf1, ...)``
  with ``pf0 != pf1`` and an unchanged split factor, the event is armed on
  ``d0``, which must be a retained session;
* the ex-date is the next retained session after ``d0`` (LEAN's next
  ``NewTradableDate``), never ``d0`` + 1 calendar day, and the ex-date instant is
  00:00 America/New_York on that date, as integer UTC nanoseconds;
* ``per_share = round_half_even(ref0 - ref0 * (pf0 / pf1), 2)`` in ``Decimal``;
* the eligible quantity is the sum of ``signed_qty`` over the engine's own
  ``ctx.positions`` for the instrument, read inside ``process()`` at the ex-date
  instant;
* the amount is ``quantity * per_share`` exactly, with no second rounding stage,
  and a zero quantity still posts ``Money(0.00, USD)``;
* the module only emits when ``ts_now`` equals an ex-date instant. An event whose
  instant has already passed is a late emission: it is never posted, it is
  recorded as a module error, and the runner refuses the run;
* every acknowledgement outcome must be ``applied`` with no error.

The cash reaches the account only through the value ``process()`` returns, which
the simulated exchange applies with ``try_adjust_account`` and reports as an
``AccountState``. Nothing here reads the LEAN oracle, and no amount is chosen to
reconcile a balance.

Nautilus is imported only inside ``build_module`` so the derivation and the
due/eligibility/amount helpers stay importable and testable without the engine.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
CENT = Decimal("0.01")
MODULE_CLASS_NAME = "DistributionModule"


def ex_date_instant_ns(ex_date: str) -> int:
    """00:00 America/New_York on ``ex_date`` as integer UTC nanoseconds."""
    stamp = datetime.combine(date.fromisoformat(ex_date), time(0), NEW_YORK)
    return int(stamp.timestamp()) * 10 ** 9


def next_session(sessions, day: str):
    """The first retained session strictly after ``day``, or ``None``."""
    for session in sessions:
        if session > day:
            return session
    return None


def per_share_distribution(ref0: Decimal, pf0: Decimal, pf1: Decimal) -> Decimal:
    """LEAN ``Dividend.ComputeDistribution``: cents, half-to-even, one rounding."""
    if pf1 == 0:
        raise ValueError("zero_price_factor")
    return (ref0 - ref0 * (pf0 / pf1)).quantize(CENT, rounding=ROUND_HALF_EVEN)


def derive_events(factor_rows, sessions, start: str, end: str) -> list[dict]:
    """Distribution events whose ex-date falls in ``[start, end]``.

    ``sessions`` is the whole retained daily session list (ISO dates), not only
    the replay window, so the session before the window is known. A factor row
    that could arm an in-window event but is not a retained session is refused,
    as is a split inside that range and a nonpositive distribution.
    """
    sessions = list(sessions)
    if sessions != sorted(set(sessions)):
        raise ValueError("sessions_not_sorted_unique")
    session_set = set(sessions)
    before = [s for s in sessions if s < start]
    # A row dated earlier than the last session before the window can only arm
    # an ex-date at or before that session, which is outside the window.
    floor = before[-1] if before else (sessions[0] if sessions else start)
    events = []
    for previous, current in zip(factor_rows, factor_rows[1:]):
        d0 = previous["date"]
        if d0 < floor or d0 >= end:
            continue
        if previous["split_factor"] != current["split_factor"]:
            raise ValueError("unexpected_split:" + d0)
        pf0, pf1 = Decimal(previous["price_factor"]), Decimal(current["price_factor"])
        if pf0 == pf1:
            continue
        if d0 not in session_set:
            raise ValueError("factor_row_not_a_session:" + d0)
        ex_date = next_session(sessions, d0)
        if ex_date is None:
            raise ValueError("no_session_after_factor_row:" + d0)
        if not start <= ex_date <= end:
            continue
        ref0 = Decimal(previous["reference_price"])
        per_share = per_share_distribution(ref0, pf0, pf1)
        if per_share <= 0:
            raise ValueError("nonpositive_distribution:" + d0)
        instant = ex_date_instant_ns(ex_date)
        events.append({
            "factor_row_date": d0, "ex_date": ex_date,
            "calendar_plus_one": (date.fromisoformat(d0) + timedelta(days=1)).isoformat(),
            "ex_instant_ns": instant, "ex_instant_utc_seconds": instant // 10 ** 9,
            "pf0": str(pf0), "pf1": str(pf1), "ref0": str(ref0), "per_share": str(per_share)})
    return events


def due_events(pending, ts_now: int) -> tuple[list, list]:
    """Split pending events into (on time at ``ts_now``, already late)."""
    on_time = [e for e in pending if e["ex_instant_ns"] == ts_now]
    late = [e for e in pending if e["ex_instant_ns"] < ts_now]
    return on_time, late


def eligible_quantity(positions, instrument_id: str) -> int:
    """Sum of ``signed_qty`` over the engine's positions for one instrument.

    The pinned binding exposes ``signed_qty`` as a float; it is read through its
    string form and must be a whole number of shares, otherwise it is refused.
    """
    total = Decimal(0)
    for position in positions:
        if str(position.instrument_id) == instrument_id:
            total += Decimal(str(position.signed_qty))
    if total != total.to_integral_value():
        raise ValueError("non_integral_eligible_quantity:" + str(total))
    return int(total)


def distribution_amount(quantity: int, per_share) -> Decimal:
    """Whole shares times a cent amount: exact, no further rounding stage."""
    return Decimal(int(quantity)) * Decimal(str(per_share))


def build_module(events, instrument_id: str, currency: str):
    """Return a fresh ``DistributionModule`` instance bound to ``events``."""
    from nautilus_trader.backtest import SimulationModule
    from nautilus_trader.model import Currency, Money

    money_currency = Currency.from_str(currency)
    frozen = [dict(event) for event in events]

    class DistributionModule(SimulationModule):
        def __init__(self, *args, **kwargs):
            self.events = [dict(event) for event in frozen]
            self.pending = [dict(event) for event in frozen]
            self.process_calls = 0
            self.resets = 0
            self.calls_at_event_instants = []
            self.emissions = []
            self.acknowledgements = []
            self.errors = []
            self._awaiting = []

        def pre_process(self, data):
            return None

        def process(self, ts_now, ctx):
            self.process_calls += 1
            try:
                return self._process(int(ts_now), ctx)
            except BaseException as error:  # the engine may swallow it; keep the evidence
                self.errors.append("process:" + type(error).__name__ + ": " + str(error))
                return None

        def _process(self, ts_now, ctx):
            if any(e["ex_instant_ns"] == ts_now for e in self.events):
                self.calls_at_event_instants.append(ts_now)
            on_time, late = due_events(self.pending, ts_now)
            for event in late:
                self.errors.append("late_module_emission:" + event["ex_date"] + "@" + str(ts_now))
            if late:
                self.pending = [e for e in self.pending if e not in late]
            if not on_time:
                return None
            quantity = eligible_quantity(ctx.positions, instrument_id)
            posted = []
            for event in on_time:
                amount = distribution_amount(quantity, event["per_share"])
                self.emissions.append({
                    "ex_date": event["ex_date"], "factor_row_date": event["factor_row_date"],
                    "ex_instant_ns": event["ex_instant_ns"], "ts_now_ns": ts_now,
                    "on_time": ts_now == event["ex_instant_ns"],
                    "eligible_quantity": quantity, "per_share": event["per_share"],
                    "amount": str(amount), "currency": currency,
                    "positions_seen": len(ctx.positions)})
                posted.append(Money(amount, money_currency))
            self.pending = [e for e in self.pending if e not in on_time]
            self._awaiting = [e["ex_date"] for e in on_time]
            return posted

        def acknowledge(self, outcomes):
            outcomes = list(outcomes or [])
            if not outcomes and not self._awaiting:
                return
            record = {"ex_dates": list(self._awaiting),
                      "outcomes": [{"applied": bool(o.applied),
                                    "error": None if o.error is None else str(o.error)}
                                   for o in outcomes]}
            self.acknowledgements.append(record)
            if len(outcomes) != len(self._awaiting):
                self.errors.append("acknowledgement_count:" + str(len(outcomes)) + "/" +
                                   str(len(self._awaiting)))
            for outcome in record["outcomes"]:
                if not outcome["applied"] or outcome["error"] is not None:
                    self.errors.append("adjustment_not_applied:" + ",".join(record["ex_dates"]) +
                                       ":" + str(outcome["error"]))
            self._awaiting = []

        def log_diagnostics(self):
            return None

        def reset(self):
            self.resets += 1
            self.pending = [dict(event) for event in self.events]

    DistributionModule.__name__ = MODULE_CLASS_NAME
    return DistributionModule()
