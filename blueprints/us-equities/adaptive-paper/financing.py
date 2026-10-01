"""Modeled overnight margin-interest (financing) cost for the adaptive-paper
engine's opt-in overnight-holds lane.

Pure and side-effect free, in the style of leverage.py: no I/O, no
broker/transport calls, no mutation of caller state, no wall-clock read.
Every function here is a deterministic mapping from explicit Decimal/date
inputs to a bounded projection or schedule.

This module is only ever consulted from runner.py's ``run_native`` when a
run ends ``"held_overnight"`` under ``session_policy["overnight_holds"]``
(every shipped config as of this module's introduction leaves
``overnight_holds`` False, so nothing here is on the decision path for any
shipped config -- see runner.py's ``load_config`` for the optional
``"financing_plan"`` key and ``run_native``'s ``_modeled_financing_block``).

Sources (fetched 2026-09-25):

* Alpaca, "Margin and Short Selling"
  (https://docs.alpaca.markets/docs/margin-and-short-selling):

  - Annual margin interest rate: 5.00% for Elite users, 6.50% for
    non-Elite ("standard" here); the page says to check the "Alpaca
    Securities Brokerage Fee Schedule" for the current rate -- MARGIN_RATES
    below is a frozen snapshot of the page as read on the date above, not a
    live read of that fee schedule.
  - The rate is charged only on the end-of-day (overnight) SETTLEMENT-DATE
    debit balance: ``daily_margin_interest_charge =
    settlement_date_debit_balance * rate / 360`` (``DAY_COUNT`` below).
  - Interest accrues daily and posts at the end of each month. A
    settlement-date debit balance at the end of day Friday incurs 3 days of
    interest (Fri, Sat, Sun) -- no trade settles over the weekend, so the
    same balance is carried through both non-trading days.
  - Worked example: deposit $10,000, buy $15,000, hold at end of day. That
    borrows $5,000 overnight, and ``5000 * 0.065 / 360 = $0.90`` per day
    (see ``tests/test_adaptive_paper_financing.py`` for the same example
    run through this module, unrounded and rounded).

* Alpaca, "Paper Trading" (https://docs.alpaca.markets/docs/paper-trading):

  - Paper does NOT simulate regulatory fees or dividends.
  - Its "Paper vs Live" table marks "Borrow Fees (Coming Soon!)" for paper.
  - It does not say whether paper posts margin interest at all. Treated as
    unverified here: every value this module returns is a MODELED
    projection, never reconciled against a paper account -- see runner.py's
    ``"modeled_financing"`` outcome block (``"evidence_class": "modeled"``)
    and ``blueprints/us-equities/adaptive-paper/README.md``'s "Financing
    costs (modeled)" section.

Not modelled: borrow/short-locate fees, dividends, and (see
``settlement_date``'s docstring) a bank holiday on which NYSE is open but
securities do not actually settle (e.g. Columbus Day, Veterans Day).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sessions import next_trading_day

D = Decimal
ZERO = D("0")

# Alpaca "Margin and Short Selling" (fetched 2026-09-25): annual margin
# interest rate by account tier. A frozen snapshot, not a live fee-schedule
# read -- see the module docstring.
MARGIN_RATES = {"standard": D("0.0650"), "elite": D("0.0500")}

# Alpaca's stated day-count convention for the daily charge formula
# (``debit * rate / DAY_COUNT``), same source.
DAY_COUNT = 360

# Where MARGIN_RATES came from and when it was read; embedded in every
# overnight_financing_projection() result so a receipt is traceable back to
# its source without a second lookup.
RATE_SOURCE = {"url": "https://docs.alpaca.markets/docs/margin-and-short-selling",
               "retrieved": "2026-09-25"}

CENTS = D("0.01")


class FinancingError(ValueError):
    """Bounded reason code; mirrors leverage.LeveragePolicyError."""


def _dec(value):
    return value if isinstance(value, Decimal) else D(str(value))


def _resolve_rate(plan, rate):
    if plan not in MARGIN_RATES:
        raise FinancingError(f"unknown_margin_plan:{plan}")
    return _dec(rate) if rate is not None else MARGIN_RATES[plan]


def quantize_cents(value: Decimal) -> Decimal:
    """Round a Decimal USD amount to whole cents (ROUND_HALF_UP).

    Never applied automatically by ``margin_interest`` or
    ``overnight_financing_projection`` -- both keep full Decimal precision
    unless a caller explicitly asks for this.
    """
    return _dec(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def settlement_date(trade_date: date) -> date:
    """T+1: the next NYSE trading day after ``trade_date``, via
    ``sessions.next_trading_day``.

    Simplification (documented, not modelled): this follows the NYSE
    *trading* calendar, not the separate SIFMA bank/securities-settlement
    calendar -- a bank holiday on which NYSE is open (e.g. Columbus Day,
    Veterans Day) is treated as a normal settlement day here, though real
    DTCC settlement does not occur on those days. Every 2026 NYSE
    full-closure holiday in ``sessions.HOLIDAYS_2026`` is also a SIFMA bank
    holiday, so this simplification never changes a 2026 result; it would
    only matter for a trade/settlement window spanning Columbus Day or
    Veterans Day, which this module does not exercise.
    """
    return next_trading_day(trade_date)


def settled_debit_schedule(opening_settled_cash, cash_flows, start: date, end: date):
    """The settlement-date cash balance and debit for every calendar day
    from ``start`` to ``end`` (inclusive).

    ``cash_flows`` is an iterable of ``(trade_date, amount_usd)`` pairs --
    buys negative, sells positive, fees included -- each counted from its
    own settlement date (``settlement_date(trade_date)``), never its trade
    date: a flow dated ``trade_date`` first affects the balance on
    ``settlement_date(trade_date)`` and every day after (in particular, the
    trade-date night itself carries no charge from that flow). ``
    opening_settled_cash`` is the settled balance immediately before the
    earliest date this function considers (``start``, or any flow's
    settlement date, whichever is earlier) -- a flow need not settle on or
    after ``start``; one that settles earlier is simply already reflected
    in every day of the returned schedule.

    Returns a list of ``{"date": D, "balance_usd": Decimal, "debit_usd":
    Decimal}`` for each calendar day ``D``, ascending, where ``debit_usd =
    max(0, -balance_usd)``. A non-trading day is never a flow's settlement
    date (``settlement_date`` always returns a trading day), so it
    necessarily carries the prior day's balance forward unchanged -- no
    separate handling is needed for that rule.
    """
    if end < start:
        raise FinancingError("end_before_start")
    settled: dict[date, Decimal] = {}
    for trade_date, amount in cash_flows:
        settle_on = settlement_date(trade_date)
        settled[settle_on] = settled.get(settle_on, ZERO) + _dec(amount)
    running = _dec(opening_settled_cash)
    for settle_on in sorted(k for k in settled if k < start):
        running += settled[settle_on]
    schedule = []
    day = start
    while day <= end:
        running += settled.get(day, ZERO)
        schedule.append({"date": day, "balance_usd": running, "debit_usd": max(ZERO, -running)})
        day += timedelta(days=1)
    return schedule


def margin_interest(schedule, plan="standard", rate=None):
    """The margin interest due over ``schedule`` (as returned by
    ``settled_debit_schedule``): the sum of ``debit_usd * rate / DAY_COUNT``
    over every entry, at full Decimal precision -- never rounded here; call
    ``quantize_cents`` on a value explicitly to round it.

    ``rate`` overrides ``MARGIN_RATES[plan]`` when given (e.g. to project a
    fee-schedule change without editing ``MARGIN_RATES``); ``plan`` is still
    validated either way, since it also labels the result. Raises
    ``FinancingError`` (a ``ValueError``) for a plan not in
    ``MARGIN_RATES``.

    Returns ``{"plan", "rate", "total_usd", "daily": [{"date", "debit_usd",
    "charge_usd"}, ...]}``.
    """
    effective_rate = _resolve_rate(plan, rate)
    daily = []
    total = ZERO
    for day in schedule:
        charge = day["debit_usd"] * effective_rate / DAY_COUNT
        daily.append({"date": day["date"], "debit_usd": day["debit_usd"], "charge_usd": charge})
        total += charge
    return {"plan": plan, "rate": effective_rate, "total_usd": total, "daily": daily}


def overnight_financing_projection(positions_cost_usd, settled_cash_usd, trade_date: date, plan="standard"):
    """The projected margin-interest charge for holding the current book
    (bought on ``trade_date``) until it is sold at the next trading
    session -- the run just ended ``"held_overnight"``; this projects the
    cost of the hold it is currently in, not a historical schedule.

    Models that future sale explicitly rather than guessing a hold length:
    the buys settle at ``settlement_date(trade_date)`` (T+1); the book is
    then modelled as sold at the next session
    (``sessions.next_trading_day(trade_date)``), which itself settles at
    ``settlement_date`` of that next session (T+2 from ``trade_date``). The
    financed days are the calendar days from the buy's settlement date up
    to (not including) the sale's settlement date -- once the sale settles,
    the debit is gone. This reproduces the documented Friday case exactly
    when ``trade_date`` is an ordinary Thursday before a holiday-free
    weekend (3 days: Fri, Sat, Sun) and extends it by any holiday the
    weekend also carries (see ``tests/test_adaptive_paper_financing.py``).

    Simplifying assumption (kept deliberately simple; documented rather
    than reconstructed): ``settled_cash_usd`` is the settled cash available
    BEFORE buying the current book (e.g. the trial's starting capital) --
    not a post-buy running-cash figure, which already nets out the
    position's cost and would double-count it against
    ``positions_cost_usd``. ``positions_cost_usd`` is the cost basis of the
    book currently held. ``debit_usd = max(0, positions_cost_usd -
    settled_cash_usd)``, held flat for every financed day -- a projection of
    the CURRENT book, not a reconstructed intraday settled-cash trajectory.

    Returns a dict: ``plan``, ``rate``, ``source`` (a copy of
    ``RATE_SOURCE``), ``trade_date``, ``next_session_date``,
    ``buy_settlement_date``, ``sell_settlement_date``, ``debit_usd``,
    ``daily_charge_usd``, ``charge_days``, ``total_charge_usd``. Raises
    ``FinancingError`` (a ``ValueError``) for a plan not in
    ``MARGIN_RATES``.
    """
    effective_rate = _resolve_rate(plan, None)
    debit = max(ZERO, _dec(positions_cost_usd) - _dec(settled_cash_usd))
    buy_settlement = settlement_date(trade_date)
    next_session = next_trading_day(trade_date)
    sell_settlement = settlement_date(next_session)
    charge_days = (sell_settlement - buy_settlement).days
    daily_charge = debit * effective_rate / DAY_COUNT
    return {"plan": plan, "rate": effective_rate, "source": dict(RATE_SOURCE),
            "trade_date": trade_date, "next_session_date": next_session,
            "buy_settlement_date": buy_settlement, "sell_settlement_date": sell_settlement,
            "debit_usd": debit, "daily_charge_usd": daily_charge,
            "charge_days": charge_days, "total_charge_usd": daily_charge * charge_days}
