"""Exact single-long-SPY LEAN fixture policy, independent of native execution.

LEAN 985ef30: DefaultMarginCallModel.cs:60-116,134-225 and
BuyingPowerModel.cs:333-354,421-518. Native orders/fills remain authoritative.
This is neither rc5 automatic maintenance nor a paper risk implementation.
"""
from decimal import Decimal, ROUND_FLOOR


def _number(value):
    value = Decimal(str(value))
    if not value.is_finite():
        raise ValueError('nonfinite_policy_state')
    return value


def margin_decision(quantity, price, equity, fee, exchange_open):
    """Fixed 50% current-value maintenance, 10% call buffer, fee-aware lots.

    For this single positive SPY position, delta buying power leaves equity as
    the target margin. LEAN GetAmountToOrder floors the long final holdings;
    its fee loop then reduces that target by the actual once-per-order fee.
    The execution stop condition is margin remaining >=0, independently of
    the strict >110% call predicate. ExchangeOpen gates execution, not warning.
    """
    q, price, equity, fee = map(_number, (quantity, price, equity, fee))
    if q < 0 or q != q.to_integral_value() or price <= 0 or fee < 0:
        raise ValueError('invalid_single_long_policy_state')
    maintenance = q * price * Decimal('0.5')
    remaining = equity - maintenance
    warning = maintenance > 0 and remaining <= equity * Decimal('0.05')
    call = maintenance > 0 and remaining <= 0 and maintenance > equity * Decimal('1.10')
    if remaining <= 0:
        warning = call  # DefaultMarginCallModel overwrites warning with count>0.
    reduction = 0
    if call and exchange_open:
        # LEAN's zero-target path returns all exposure directly. A negative
        # target cannot reverse this reduction-only single-long fixture.
        keep = (max(Decimal(0), equity - fee) / (price * Decimal('0.5')))
        keep = min(q, keep.to_integral_value(rounding=ROUND_FLOOR))
        reduction = int(keep - q)
    return {'quantity': reduction, 'warning': bool(warning and not reduction),
            'policy_maintenance': str(maintenance), 'policy_margin_remaining': str(remaining),
            'call_predicate': bool(call), 'exchange_open': bool(exchange_open)}


class AdaptiveState:
    """Hourly peak and completed-16:00 one-way 5% latch from the frozen plan."""
    def __init__(self, initial, enabled):
        self.peak = _number(initial)
        self.enabled = enabled
        self.latched = False

    def observe(self, equity, *, completed_close, invested, settled=True):
        if not settled:
            raise ValueError('unsettled_native_state')
        equity = _number(equity)
        self.peak = max(self.peak, equity)
        if self.peak <= 0:
            raise ValueError('nonpositive_policy_peak')
        drawdown = 1 - equity / self.peak
        reduce = (self.enabled and not self.latched and completed_close and invested
                  and drawdown >= Decimal('0.05'))
        if reduce:
            self.latched = True
        return {'peak': str(self.peak), 'drawdown': str(drawdown), 'reduce': bool(reduce)}


class SettlementHandshake:
    """A mark is admitted only at the retained +1ns native completion alert.

    Module acknowledgement precedes post-queue settlement in rc5. Each native
    liquidation must complete at the original economic timestamp. A separate
    alert reads settled native exposure before observing marks or making a
    discretionary decision. This contract still needs an actual native probe.
    """
    def __init__(self):
        self.pending = None
        self.last = None

    def begin(self, economic_ns, native_quantity):
        if self.pending is not None:
            raise ValueError('pending_observation')
        if self.last is not None and economic_ns <= self.last:
            raise ValueError('duplicate_economic_timestamp')
        self.pending = {'economic': int(economic_ns), 'quantity': int(native_quantity), 'fills': {}}
        return int(economic_ns) + 1

    def expect_fill(self, order_ref, quantity):
        if self.pending is None or order_ref in self.pending['fills'] or quantity >= 0:
            raise ValueError('invalid_or_duplicate_liquidation')
        if -quantity > self.pending['quantity']:
            raise ValueError('liquidation_reverses_exposure')
        self.pending['fills'][order_ref] = int(quantity)

    def fill(self, order_ref, quantity, native_ns):
        if self.pending is None or order_ref not in self.pending['fills']:
            raise ValueError('unattributed_liquidation_fill')
        if native_ns != self.pending['economic']:
            raise ValueError('liquidation_time')
        expected = self.pending['fills'][order_ref]
        if quantity >= 0 or quantity < expected:
            raise ValueError('liquidation_fill_exceeds_request')
        self.pending['fills'][order_ref] -= int(quantity)
        self.pending['quantity'] += int(quantity)

    def complete(self, native_ns, native_quantity):
        if self.pending is None:
            raise ValueError('duplicate_or_missing_observation')
        if native_ns != self.pending['economic'] + 1:
            raise ValueError('observation_time')
        if any(self.pending['fills'].values()):
            raise ValueError('pending_fill')
        if native_quantity != self.pending['quantity']:
            raise ValueError('native_quantity_not_settled')
        result = {'economic_ts_event_ns': self.pending['economic'],
                  'observation_ts_event_ns': int(native_ns)}
        self.last = self.pending['economic']
        self.pending = None
        return result

    def finish(self):
        if self.pending is not None:
            raise ValueError('pending_observation_at_end')
