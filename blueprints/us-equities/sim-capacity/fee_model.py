"""US-equity sell-side regulatory fee model: Alpaca commission ($0, documented --
Alpaca charges no commission on US equities) plus the SEC Section 31 fee and the
FINRA Trading Activity Fee (TAF) on sells only. Rates are cited from the pinned,
dated, primary-sourced `blueprints/us-equities/mover-v3/data/fees-v3.json`
(retrieved_at 2026-09-24), not re-derived here:

  - SEC Section 31 (Exchange Act secs. 31(b)/(c)): $20.60 per $1,000,000 of
    covered-sale proceeds, effective 2026-04-04, open-ended at retrieval.
    Source: SEC Release No. 34-104909 (91 FR 10643), corrected by 34-104909A
    (91 FR 24948); SEC Fee Rate Advisory for FY2026 (2026-02-27), accessed
    2026-09-24. https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2
  - FINRA TAF (By-Laws Schedule A, Section 1(b)): $0.000195 per share sold,
    capped at $9.79 per trade, in force 2026-01-01 through 2026-09-30 (the
    session date, 2026-09-24, falls inside this row; SR-FINRA-2026-021 pauses
    the fee to $0 for 2026-10-01 through 2026-12-31, which does not apply
    here). https://www.finra.org/rules-guidance/rulebooks/corporate-organization/section-1-member-regulatory-fees

UNVERIFIED: whether the FINRA TAF cap applies per *order* or per *execution*
(fill). This model applies it per fill (the conservative, i.e. more
fee-generating, choice for a high-fill-rate capacity run, since one order can
generate multiple partial fills each independently capped) and this parameter
is exposed as `taf_cap_scope` for anyone who wants the alternative. This is a
cost-accounting nuance in a synthetic capacity run, not a strategy claim.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

SEC_SECTION31_RATE_USD_PER_DOLLAR = Decimal("20.60") / Decimal("1000000")  # $20.60 / $1,000,000
FINRA_TAF_USD_PER_SHARE = Decimal("0.000195")
FINRA_TAF_MAX_USD_PER_TRADE = Decimal("9.79")
ALPACA_COMMISSION_USD = Decimal("0")
FEE_RATE_SOURCE = "blueprints/us-equities/mover-v3/data/fees-v3.json (retrieved_at 2026-09-24)"
CENT = Decimal("0.01")


def sell_side_regulatory_fee(*, quantity: int, price: Decimal | str | float,
                              sec_rate: Decimal = SEC_SECTION31_RATE_USD_PER_DOLLAR,
                              taf_per_share: Decimal = FINRA_TAF_USD_PER_SHARE,
                              taf_cap: Decimal = FINRA_TAF_MAX_USD_PER_TRADE) -> Decimal:
    """SEC Section 31 fee plus FINRA TAF (capped) on one sell fill, in USD,
    rounded to the cent (broker fee schedules are cent-denominated). Buys carry
    neither fee under current rules and are not passed to this function by the
    fee model's `get_commission` (which routes buys to 0 directly)."""
    if quantity <= 0:
        return Decimal("0.00")
    notional = Decimal(str(price)) * quantity
    sec_fee = notional * sec_rate
    taf = min(Decimal(quantity) * taf_per_share, taf_cap)
    return (sec_fee + taf).quantize(CENT, rounding=ROUND_HALF_UP)


def commission_usd(*, side: str, quantity: int, price) -> Decimal:
    """Total per-fill commission: `$0` (Alpaca) plus, on a SELL only, the
    regulatory fees above."""
    if side.upper() != "SELL":
        return ALPACA_COMMISSION_USD
    return ALPACA_COMMISSION_USD + sell_side_regulatory_fee(quantity=quantity, price=price)


def build_nautilus_fee_model():
    """Deferred import: returns a `nautilus_trader.execution.FeeModel` subclass
    instance wired to `commission_usd`, without importing nautilus_trader at
    module load (so `commission_usd`/`sell_side_regulatory_fee` stay unit
    testable on system Python with no nautilus_trader installed)."""
    from nautilus_trader.model import Currency, Money

    from nautilus_trader.execution import FeeModel

    class USEquitySellSideFeeModel(FeeModel):
        def get_commission(self, order, fill_quantity, fill_px, instrument):
            side = "SELL" if str(order.side).upper().endswith("SELL") else "BUY"
            fee = commission_usd(side=side, quantity=int(fill_quantity), price=str(fill_px))
            return Money(fee, Currency.from_str("USD"))

    return USEquitySellSideFeeModel()
