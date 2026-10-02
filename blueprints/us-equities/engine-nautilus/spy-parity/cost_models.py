"""Native rc5 cost models for the frozen SPY stress fixture.

Source: nautilus_trader 1b0a49d2792a9432a3aca3fcb617ce7a630d905e,
docs/concepts/backtesting/fill-models.md (custom low-level FillModel protocol),
crates/execution/src/python/fill.rs and matching_engine/mod.rs:4455-4478.
The matching engine consumes the returned book before generating native fills;
no historical bar, fill export, or account balance is modified here.
"""
from decimal import Decimal, ROUND_HALF_EVEN


def adverse_price(price, side, slippage, precision):
    """One Decimal adjustment, rounded once to the declared fixture precision."""
    price, slippage = Decimal(str(price)), Decimal(str(slippage))
    if side not in ("BUY", "SELL"):
        raise ValueError("invalid_order_side:" + str(side))
    if not price.is_finite() or price <= 0 or not slippage.is_finite() or not 0 <= slippage < 1:
        raise ValueError("invalid_stress_price_or_slippage")
    multiplier = 1 + slippage if side == "BUY" else 1 - slippage
    return (price * multiplier).quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_EVEN)


def build_models(case, instrument):
    """Build fresh supported native models; never reuse fee state across runs."""
    from nautilus_trader.execution import FillModel, FixedFeeModel
    from nautilus_trader.model import BookOrder, BookType, Currency, Money, OrderBook, OrderSide, Price

    class TwentyBasisPointFillModel(FillModel):
        def __init__(self):
            super().__init__()
            self.calls = []

        def get_orderbook_for_fill_simulation(self, native_instrument, order, best_bid, best_ask):
            # Only the fixture's native OCO market-style legs are supported.
            if order.order_type.name not in ("STOP_MARKET", "MARKET_IF_TOUCHED"):
                raise ValueError("unsupported_stress_order_type:" + order.order_type.name)
            if native_instrument.price_precision != instrument["price_precision"]:
                raise ValueError("stress_instrument_precision_mismatch")
            side = order.side.name
            reference = best_ask if side == "BUY" else best_bid
            price = adverse_price(str(reference), side, case["slippage"], instrument["price_precision"])
            book = OrderBook(native_instrument.id, BookType.L2_MBP)
            resting_side = OrderSide.SELL if side == "BUY" else OrderSide.BUY
            book.add(BookOrder(resting_side, Price.from_str(format(price, ".6f")), order.quantity, 1),
                     0, 0, 0)
            self.calls.append({"client_order_id": str(order.client_order_id), "side": side,
                               "reference_price": str(reference), "fill_price": str(price),
                               "quantity": str(order.quantity)})
            return book

    fee = FixedFeeModel(Money(Decimal(case["fee_usd"]), Currency.from_str(case["currency"])),
                        charge_commission_once=True)
    return TwentyBasisPointFillModel(), fee
