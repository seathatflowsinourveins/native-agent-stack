"""US-equity fee model: SEC Section 31 and FINRA TAF on sells only, FINRA CAT
on both buys and sells, and an optional Alpaca Elite Smart Router commission
(paper-parity uses no commission; elite-tier uses the all-in Elite rate by
default). Rates are cited from two primary sources:

  - SEC Section 31 and FINRA TAF: pinned, dated
    `blueprints/us-equities/mover-v3/data/fees-v3.json` (retrieved_at
    2026-09-24): $20.60 per $1,000,000 of covered-sale proceeds (effective
    2026-04-04, open-ended at retrieval; SEC Release No. 34-104909, corrected
    by 34-104909A; SEC Fee Rate Advisory for FY2026, 2026-02-27); FINRA TAF
    $0.000195/share sold, capped at $9.79/trade, in force 2026-01-01 through
    2026-09-30 (covers the 2026-09-24 session date).
  - FINRA CAT and the Elite Smart Router commission: Alpaca Securities LLC's
    own "Brokerage Fee Schedule" PDF, https://alpaca.markets/disclosures ->
    https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf,
    "Revised on September 17, 2026", retrieved 2026-09-25, sha256
    7bc75e3cd86f5c1950f8ce1292049965280340a3cebe727ca7aee4a7d2d71b12:
      * "FINRA Consolidated Audit Trail Fee (CAT) | When buys and sells |
        $0.000003 per executed equivalent share | *NMS Equities (1 share = 1
        executed equivalent share)".
      * "Equities - Elite Smart Router ... Monthly Shares Traded* | All-in
        (Fixed) | Cost Plus (Tiered) || Up to 200,000 | $0.0040 | $0.0025"
        (the All-in column bundles exchange fees/rebates into the flat rate;
        the Cost Plus column separately passes through "Exchange Fees or
        Rebates" on top of its lower per-share rate -- unmodeled here, see
        `commission_plan="cost_plus"`'s docstring note below).
      * "Fees are calculated on the exact executed quantity ... Each fee type
        is aggregated separately at the daily, per-account level. After
        aggregation, each fee total is rounded up to the nearest cent." This
        model instead rounds **per fill**, half-up, not per day, per-fee-type,
        rounded up -- a known, disclosed simplification. The difference is
        small at this run's fill counts (a handful of cents at most across a
        30-minute run) and is reported, not hidden (see
        `runner.summarize_run`'s `fee_rounding_note`).

FINRA CAT applies to every Alpaca equity trade (not Elite-specific); the Elite
Smart Router commission applies only when trading through the Elite offering
(the elite-tier profile here), never on paper-parity, matching "Commissions
apply to ... use of the Elite Smart Router under the Alpaca Elite offering."

UNVERIFIED: whether the FINRA TAF cap applies per *order* or per *execution*
(fill); the fee-schedule PDF's own footnote ("capped at 50,205 shares or
more") describes the cap in per-transaction terms consistent with either
reading. This model applies the cap per fill (the conservative, i.e. more
fee-generating, choice for a high-fill-rate capacity run) and exposes it as
`taf_cap` for anyone who wants the alternative. This is a cost-accounting
nuance in a synthetic capacity run, not a strategy claim.

UNVERIFIED (partial): the `cost_plus` commission plan's per-share rate
($0.0025/share at this run's volume tier) is exact, but its additional
"Exchange Fees or Rebates" pass-through component is not modeled (no
per-venue maker/taker schedule is available to this lane) -- `cost_plus`
therefore understates true cost and is not the default for elite-tier.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

SEC_SECTION31_RATE_USD_PER_DOLLAR = Decimal("20.60") / Decimal("1000000")  # $20.60 / $1,000,000
FINRA_TAF_USD_PER_SHARE = Decimal("0.000195")
FINRA_TAF_MAX_USD_PER_TRADE = Decimal("9.79")
FINRA_CAT_USD_PER_SHARE = Decimal("0.000003")  # buys and sells, NMS equities
ALPACA_COMMISSION_USD = Decimal("0")  # retail routing (paper-parity): no commission
ELITE_ALL_IN_USD_PER_SHARE = Decimal("0.0040")  # <=200,000 monthly shares tier
ELITE_COST_PLUS_USD_PER_SHARE = Decimal("0.0025")  # <=200,000 monthly shares tier; partial (see module docstring)
FEE_RATE_SOURCE = "blueprints/us-equities/mover-v3/data/fees-v3.json (retrieved_at 2026-09-24)"
BROKER_FEE_SCHEDULE_SOURCE = ("https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf "
                              "(Revised on September 17, 2026; retrieved 2026-09-25; sha256 "
                              "7bc75e3cd86f5c1950f8ce1292049965280340a3cebe727ca7aee4a7d2d71b12)")
COMMISSION_PLANS = ("none", "all_in", "cost_plus")
CENT = Decimal("0.01")


def sell_side_regulatory_fee(*, quantity: int, price: Decimal | str | float,
                              sec_rate: Decimal = SEC_SECTION31_RATE_USD_PER_DOLLAR,
                              taf_per_share: Decimal = FINRA_TAF_USD_PER_SHARE,
                              taf_cap: Decimal = FINRA_TAF_MAX_USD_PER_TRADE) -> Decimal:
    """SEC Section 31 fee plus FINRA TAF (capped), unrounded, on one sell fill's
    quantity/price -- the sells-only component of `commission_usd`. Returned
    unrounded (rounding happens once, in `commission_usd`, after CAT and any
    commission are added) so a caller combining components never double-rounds."""
    if quantity <= 0:
        return Decimal("0")
    notional = Decimal(str(price)) * quantity
    sec_fee = notional * sec_rate
    taf = min(Decimal(quantity) * taf_per_share, taf_cap)
    return sec_fee + taf


def cat_fee(*, quantity: int, rate: Decimal = FINRA_CAT_USD_PER_SHARE) -> Decimal:
    """FINRA CAT fee, unrounded, on buys AND sells alike."""
    if quantity <= 0:
        return Decimal("0")
    return Decimal(quantity) * rate


def elite_commission(*, quantity: int, plan: str) -> Decimal:
    """Elite Smart Router commission, unrounded, on buys AND sells alike (the
    fee schedule does not say sells-only for this component). `plan="none"`
    (paper-parity) is always $0; `"all_in"` is the flat, all-inclusive rate;
    `"cost_plus"` is the lower per-share rate but excludes the schedule's
    separate exchange-fee/rebate pass-through (see module docstring)."""
    if plan not in COMMISSION_PLANS:
        raise ValueError(f"unknown commission_plan:{plan!r}")
    if plan == "none" or quantity <= 0:
        return Decimal("0")
    per_share = ELITE_ALL_IN_USD_PER_SHARE if plan == "all_in" else ELITE_COST_PLUS_USD_PER_SHARE
    return Decimal(quantity) * per_share


def commission_usd(*, side: str, quantity: int, price, commission_plan: str = "none") -> Decimal:
    """Total per-fill cost: FINRA CAT (both sides) plus, on a SELL only, SEC
    Section 31 + FINRA TAF, plus an optional Elite Smart Router commission --
    summed unrounded and rounded once, half-up, to the cent. `commission_plan`
    defaults to `"none"` (paper-parity / retail: $0 commission) for backward
    compatibility with existing callers; pass `"all_in"` for the elite-tier
    profile."""
    total = cat_fee(quantity=quantity) + elite_commission(quantity=quantity, plan=commission_plan)
    if side.upper() == "SELL":
        total += sell_side_regulatory_fee(quantity=quantity, price=price)
    return (ALPACA_COMMISSION_USD + total).quantize(CENT, rounding=ROUND_HALF_UP)


def build_nautilus_fee_model(commission_plan: str = "none"):
    """Deferred import: returns a `nautilus_trader.execution.FeeModel` subclass
    instance wired to `commission_usd`, without importing nautilus_trader at
    module load (so `commission_usd`/`sell_side_regulatory_fee` stay unit
    testable on system Python with no nautilus_trader installed)."""
    from nautilus_trader.model import Currency, Money

    from nautilus_trader.execution import FeeModel

    class USEquityFeeModel(FeeModel):
        def get_commission(self, order, fill_quantity, fill_px, instrument):
            side = "SELL" if str(order.side).upper().endswith("SELL") else "BUY"
            fee = commission_usd(side=side, quantity=int(fill_quantity), price=str(fill_px),
                                  commission_plan=commission_plan)
            return Money(fee, Currency.from_str("USD"))

    return USEquityFeeModel()
