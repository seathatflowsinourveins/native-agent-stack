"""Execution prices from Alpaca's cumulative order reports (stdlib only).

Alpaca reports an order's cumulative ``filled_avg_price`` rounded to six decimals: on
2026-09-24 a paper sell filled 11 shares at 15.00 and then 1 at 15.01, reported as 15.000833.
The transport normalizes the value, dropping trailing zeros, so the reported string's own
precision says nothing about the rounding. A reported average therefore differs from the true
one by strictly less than ``report_unit(avg)``, and ``filled * avg`` differs from the true
cumulative notional by strictly less than ``filled * report_unit(avg)``. Every execution price
lies on the instrument's price grid (``tick``), so the true notional of any set of whole-share
executions is a whole number of ticks.
"""
from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, localcontext

REPORT_UNIT = Decimal("0.000001")
DIGITS = 60  # this module's arithmetic precision, independent of the caller's decimal context
UNRESOLVED = "cumulative_fill_precision_requires_reconciliation"
CONTRADICTED = "fill_event_price_requires_reconciliation"


def report_unit(avg: Decimal) -> Decimal:
    """The six-decimal reporting unit, or the average's own last decimal when it is finer."""
    return min(REPORT_UNIT, Decimal(1).scaleb(avg.as_tuple().exponent))


def resolve_execution(prior_qty: Decimal, prior_notional: Decimal, filled: Decimal, avg: Decimal,
                      tick: Decimal, *, event_qty=None, event_price=None) -> tuple[Decimal, Decimal]:
    """The price of the shares filled since the prior observation, and the new exact notional.

    ``prior_notional`` is the exact notional of the ``prior_qty`` shares already resolved.

    - A trade-update event whose quantity is exactly the new shares carries their execution
      price. It must be on the grid and agree with the reported average, or the order needs
      reconciliation: an authoritative price is never replaced by a derived one.
    - Otherwise, the new shares' notional must be the only whole number of ticks strictly
      within the average's bound of ``filled * avg - prior_notional``, and it must divide into
      an on-grid price per share. When it does not, the shares filled at several prices and one
      native fill cannot represent them.

    Anything else raises ``cumulative_fill_precision_requires_reconciliation``.
    """
    with localcontext() as ctx:
        ctx.prec = DIGITS
        delta = filled - prior_qty
        if delta <= 0 or tick <= 0:
            raise ValueError(UNRESOLVED)
        bound = filled * report_unit(avg)
        reported = filled * avg

        def on_grid(price):
            return price > 0 and price == price.quantize(tick)

        if event_qty is not None and event_price is not None and Decimal(str(event_qty)) == delta:
            price = Decimal(str(event_price))
            if not on_grid(price) or abs(prior_notional + delta * price - reported) >= bound:
                raise ValueError(CONTRADICTED)
            return price.quantize(tick), prior_notional + delta * price
        estimate = reported - prior_notional
        first = ((estimate - bound) / tick).to_integral_value(ROUND_FLOOR) + 1    # least k: k * tick > estimate - bound
        last = ((estimate + bound) / tick).to_integral_value(ROUND_CEILING) - 1   # greatest k: k * tick < estimate + bound
        if first != last:
            raise ValueError(UNRESOLVED)
        notional = first * tick
        price = notional / delta
        if not on_grid(price):
            raise ValueError(UNRESOLVED)
        return price.quantize(tick), prior_notional + notional

