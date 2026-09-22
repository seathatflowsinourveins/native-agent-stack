"""Deterministic research policies; every order still passes broker/risk controls.

These are transparent baseline implementations, not qualified trading alpha.
Quotes are observed in event time. No future bar, pasted price, or LLM judgment
can trigger an order. A single allocator coordinates all policy families.

This module is the default (and only shipped) member of the strategy registry
(see registry.json, evidence_class "SYN"). It is imported by strategies.py,
whose AdaptivePolicy subclasses AdaptivePolicyV1 unchanged and only adds the
optional selector/strategy_pool gate on top. decide() is split into a thin
rate-limiting wrapper plus two internal, side-effect-free/side-effecting
pieces (_regime_and_signals / _decide_core) purely so that wrapper code can
observe the regime without double-mutating counters; behavior for a given
sequence of calls is unchanged from the pre-split implementation (see
blueprints/us-equities/adaptive-paper/receipts/adaptive_policy_v1.golden.json,
captured before this refactor).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
import math
import statistics

from exits import DEFAULT_PLAN, ExitContext

# Quotes may arrive up to this far ahead of the caller's `now` (clock skew
# across processes/threads) and still count as fresh; anything further ahead
# is rejected as a future/reordered quote. Shared with native_strategy.py's
# OperationalStatus freshness check and its own quote_age_seconds staleness
# check, via import -- do not duplicate this literal elsewhere.
QUOTE_FUTURE_TOLERANCE_SECONDS = .25


@dataclass(frozen=True)
class PolicyConfig:
    symbols: tuple[str, ...]
    benchmarks: tuple[str, ...] = ("SPY", "QQQ", "IWM", "DIA")
    history: int = 120
    warmup_samples: int = 32
    warmup_seconds: float = 30
    sample_seconds: float = 1
    rebalance_seconds: float = 2
    max_positions: int = 10
    capital: float = 10000
    gross_cap: float = 5000
    max_leverage: float = 1
    max_shares: int = 1
    minimum_price: float = 5
    maximum_price: float = 1000
    max_order_notional: float = 1000
    limit_offset_usd: float = .02
    max_spread_bps: float = 15
    quote_age_seconds: float = 3
    minimum_edge_bps: float = 4
    volatility_halt_bps: float = 80
    min_hold_seconds: float = 5
    max_hold_seconds: float = 90
    stop_bps: float = 25
    take_profit_bps: float = 40
    trailing_bps: float = 15
    cooldown_seconds: float = 3
    # G-f exit-plan knobs (exits.py). Every default below reproduces the
    # pre-G-f inline chain exactly: vol_stop_multiplier=1.0 and a
    # zero-width [stop_min_bps, stop_max_bps]/[trailing_min_bps,
    # trailing_max_bps] clamp (None resolves to stop_bps/trailing_bps in
    # __post_init__ below) together pin the effective stop/trailing
    # threshold to stop_bps/trailing_bps regardless of realised volatility;
    # take_profit_fraction=1.0 is a full (non-partial) take-profit;
    # time_decay_start_seconds=None disables time-decay tightening. See
    # exits.py's module docstring for exact rule ordering and
    # receipts/adaptive_policy_v1.golden.json for the byte-identity proof.
    vol_stop_multiplier: float = 1.0
    vol_reference_bps: float = 20.0
    stop_min_bps: float | None = None
    stop_max_bps: float | None = None
    trailing_min_bps: float | None = None
    trailing_max_bps: float | None = None
    take_profit_fraction: float = 1.0
    time_decay_start_seconds: float | None = None
    time_decay_min_multiplier: float = 1.0
    # Cancel-then-replace attempts per symbol per session before
    # native_strategy.AdaptiveStrategy.replace_exit gives up and the exit
    # goes to the recovery path (see native_strategy.py's module docstring).
    exit_replace_max_attempts: int = 3
    # D1 (round 2): replace_exit only cancels+resubmits a resting exit order
    # when its recomputed limit price has moved by more than this many bps
    # from the resting order's own price, OR the reason's price_rule
    # changed. 0 (the default) means "any nonzero price change" -- a
    # trailing-stop ratchet that recomputes the same price_rule ("trailing")
    # every tick but a strictly tighter limit price each time (the exact
    # case replace_exit exists for) must still trigger a replace; gating on
    # price_rule alone never fires for it. Excluded from the generic
    # positive-value check below (0 is the valid, intentional default).
    exit_replace_tolerance_bps: float = 0
    # D1 (round 2): minimum wall-clock seconds between two replace_exit
    # cancel-then-submits for the same symbol, 0 (default) = no minimum.
    # Bounds excessive cancel/resubmit churn on a fast-ratcheting trail
    # without silently dropping the eventual replacement (the next tick
    # past the interval still replaces at whatever price is then current).
    exit_replace_min_interval_seconds: float = 0
    # D4 (round 4): the D5 gap-risk stop (native_strategy._gap_risk_stop_symbols)
    # used to arm regardless of whether an actual adverse gap occurred --
    # safety.evaluate_gap_risk's own gap_bps was computed and discarded.
    # None (the default) resolves to stop_bps below: the gap stop only
    # arms when the adverse (downward) gap magnitude is at least as large
    # as the ordinary stop distance -- i.e. only when the overnight move
    # alone would already have breached where a normal intraday stop
    # would have. The shipped config ships overnight_holds=false, so no
    # position ever survives to a gap-risk arming tick in the default
    # path regardless of this threshold (see runner.py's session policy
    # validation) -- this field changes nothing in the shipped default's
    # actual behavior.
    gap_stop_trigger_bps: float | None = None
    # G-f round 5: the entire gap-risk hook (native_strategy.
    # _gap_risk_stop_symbols -- arming, triggering, and the prior-close
    # capture/persist it also performs) is opt-in, gated on this flag.
    # False (both shipped configs' effective default, via runner.py's
    # "sessions.gap_stop.enabled" read) means _gap_risk_stop_symbols
    # returns immediately without ever touching self._prior_rth_close,
    # self.ledger, or any quote -- a stricter, simpler guarantee than
    # overnight_holds=false alone (which already made the hook practically
    # unreachable in the shipped default, but did not prevent its code
    # from running).
    gap_stop_enabled: bool = False
    # G-f round 8: cancel-then-replace itself (native_strategy.
    # AdaptiveStrategy.replace_exit, invoked from rebalance()'s
    # busy-symbol branch) is opt-in, gated on this flag, following the
    # same pattern as gap_stop_enabled above. False (both shipped
    # configs' effective default, via runner.py's "exits.replace_enabled"
    # read) means rebalance() never calls replace_exit at all -- a
    # symbol whose resting exit needs a different price/price_rule this
    # tick is simply left as-is (the pre-G-f behavior: skip, no
    # cancel/resubmit), relying entirely on that resting order's own
    # eventual fill/expire/recovery path.
    exit_replace_enabled: bool = False

    def __post_init__(self):
        if (not self.symbols or len(set(self.symbols)) != len(self.symbols)
                or not set(self.benchmarks).issubset(self.symbols)):
            raise ValueError("invalid_universe")
        # Resolve the clamp sentinels before any numeric validation below so
        # the resolved (always-float) values are checked like every other
        # bound -- frozen dataclass, so object.__setattr__ is required here.
        if self.stop_min_bps is None:
            object.__setattr__(self, "stop_min_bps", self.stop_bps)
        if self.stop_max_bps is None:
            object.__setattr__(self, "stop_max_bps", self.stop_bps)
        if self.trailing_min_bps is None:
            object.__setattr__(self, "trailing_min_bps", self.trailing_bps)
        if self.trailing_max_bps is None:
            object.__setattr__(self, "trailing_max_bps", self.trailing_bps)
        if self.gap_stop_trigger_bps is None:
            object.__setattr__(self, "gap_stop_trigger_bps", self.stop_bps)
        # exit_replace_tolerance_bps/exit_replace_min_interval_seconds may
        # legitimately be 0 (their documented defaults); excluded from the
        # generic strictly-positive check and validated separately below.
        _zero_allowed = {"exit_replace_tolerance_bps", "exit_replace_min_interval_seconds"}
        values = [v for k, v in self.__dict__.items()
                 if isinstance(v, (float, int)) and not isinstance(v, bool) and k not in _zero_allowed]
        if any(not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError("invalid_policy_number")
        if self.time_decay_start_seconds is not None and not math.isfinite(self.time_decay_start_seconds):
            raise ValueError("invalid_policy_number")
        if (not math.isfinite(self.exit_replace_tolerance_bps) or self.exit_replace_tolerance_bps < 0
                or self.exit_replace_tolerance_bps > 10000
                or not math.isfinite(self.exit_replace_min_interval_seconds)
                or self.exit_replace_min_interval_seconds < 0
                or self.exit_replace_min_interval_seconds > 3600):
            raise ValueError("invalid_policy_number")
        if (self.warmup_samples < 4 or self.history < self.warmup_samples
                or self.max_leverage > 2 or self.gross_cap > self.capital * self.max_leverage
                or self.max_positions > len(self.symbols) or self.max_shares > 10
                or self.minimum_price >= self.maximum_price
                or self.min_hold_seconds >= self.max_hold_seconds
                or self.stop_min_bps > self.stop_max_bps or self.trailing_min_bps > self.trailing_max_bps
                or not 0 < self.take_profit_fraction <= 1
                or not 0 < self.time_decay_min_multiplier <= 1
                or not 1 <= self.exit_replace_max_attempts <= 20
                or (self.time_decay_start_seconds is not None
                    and self.time_decay_start_seconds >= self.max_hold_seconds)):
            raise ValueError("invalid_policy_bounds")


@dataclass(frozen=True)
class Sample:
    timestamp: float
    bid: float
    ask: float

    @property
    def mid(self):
        return (self.bid + self.ask) / 2


@dataclass(frozen=True)
class Signal:
    symbol: str
    family: str
    score: float
    edge_bps: float
    volatility_bps: float
    reason: str


@dataclass(frozen=True)
class Decision:
    timestamp: float
    regime: str
    targets: dict[str, int]
    signals: tuple[Signal, ...]
    exits: dict[str, str]
    effective_leverage: float
    reason: str


@dataclass
class Holding:
    quantity: Decimal
    average_price: float
    entered_at: float
    high_bid: float


class AdaptivePolicy:
    """Trend, breakout, mean reversion, relative strength and defensive rotation.

    The router may choose cash. Throughput is never a signal objective. Catalyst
    and predictive pre-positioning need an independently qualified event source;
    neither is inferred from a high percentage change on a pasted market list.
    """
    families = ("trend_momentum", "range_breakout", "mean_reversion",
                "relative_strength", "defensive_cash")

    def __init__(self, config: PolicyConfig):
        self.config = config
        self.history = {s: deque(maxlen=config.history) for s in config.symbols}
        self.latest: dict[str, Sample] = {}
        self.holdings: dict[str, Holding] = {}
        self.cooldown: dict[str, float] = {}
        self.last_decision = float("-inf")
        self.counts = {family: 0 for family in self.families}
        # G-f: fraction of the current holding the most recent decide() call
        # asked to exit for each symbol present in that call's `exits` dict
        # (1.0 unless a partial take-profit rule fired -- see exits.py).
        # Consumed by native_strategy.AdaptiveStrategy to size the sell
        # order; not part of Decision itself so the golden fixture (which
        # only ever serializes Decision) is unaffected by this field.
        self.last_exit_fractions: dict[str, float] = {}

    def observe(self, symbol: str, bid: float, ask: float, timestamp: float) -> bool:
        if symbol not in self.history:
            return False
        if (any(not math.isfinite(v) for v in (bid, ask, timestamp))
                or bid <= 0 or ask < bid or timestamp <= 0):
            return False
        old = self.latest.get(symbol)
        if old and timestamp <= old.timestamp:
            return False
        sample = Sample(timestamp, bid, ask)
        self.latest[symbol] = sample
        values = self.history[symbol]
        if (not values or int(timestamp / self.config.sample_seconds)
                > int(values[-1].timestamp / self.config.sample_seconds)):
            values.append(sample)
        else:
            values[-1] = sample
        return True

    def sync_positions(self, positions: dict, now: float):
        """Call only with monotonic, reconciled cumulative broker positions."""
        present = set()
        for symbol, position in positions.items():
            qty = Decimal(str(position["qty"]))
            price = float(position.get("avg_entry_price", position.get("average_price", 0)))
            if symbol not in self.history or not qty.is_finite() or qty < 0 or not math.isfinite(price) or (qty and price <= 0):
                raise ValueError("unmanaged_position")
            if qty:
                present.add(symbol)
                holding = self.holdings.get(symbol)
                if holding:
                    holding.quantity, holding.average_price = qty, price
                else:
                    self.holdings[symbol] = Holding(qty, price, now, 0)
        for symbol in set(self.holdings) - present:
            del self.holdings[symbol]
            self.cooldown[symbol] = now + self.config.cooldown_seconds

    def _features(self, symbol: str, now: float):
        values = self.history[symbol]
        last = self.latest.get(symbol)
        c = self.config
        if (not last or now - last.timestamp > c.quote_age_seconds or now < last.timestamp - QUOTE_FUTURE_TOLERANCE_SECONDS
                or len(values) < c.warmup_samples
                or values[-1].timestamp - values[0].timestamp < c.warmup_seconds
                or not c.minimum_price <= last.mid <= c.maximum_price):
            return None
        spread = (last.ask - last.bid) / last.mid * 10000
        if spread > c.max_spread_bps:
            return None
        # Comparable event-time horizon across symbols; discard older samples
        # and require the first retained sample near the common start boundary.
        horizon = max(c.warmup_seconds, (c.warmup_samples - 1) * c.sample_seconds)
        cutoff = now - horizon
        selected = [s for s in values if s.timestamp >= cutoff - c.sample_seconds]
        if len(selected) < c.warmup_samples or selected[0].timestamp > cutoff + c.sample_seconds:
            return None
        prices = [s.mid for s in selected]
        returns = [(b / a - 1) * 10000 for a, b in zip(prices, prices[1:])]
        vol = statistics.pstdev(returns) if len(returns) > 1 else 0
        slow = statistics.mean(prices)
        fast = statistics.mean(prices[-max(2, min(8, len(prices) // 4)):])
        deviation = statistics.pstdev(prices)
        return {"mid": last.mid, "spread": spread, "vol": vol,
                "momentum": (fast / slow - 1) * 10000,
                "return": (prices[-1] / prices[0] - 1) * 10000,
                "z": (last.mid - slow) / deviation if deviation else 0,
                "turn": (prices[-1] / prices[-3] - 1) * 10000,
                "breakout": (last.mid / max(prices[:-1]) - 1) * 10000}

    def _signals(self, features: dict, regime: str, benchmark_return: float):
        signals = []
        for symbol, f in features.items():
            if f["vol"] > self.config.volatility_halt_bps:
                continue
            hurdle = max(self.config.minimum_edge_bps,
                         f["spread"] + 2 * self.config.limit_offset_usd / f["mid"] * 10000)
            choices = []
            if regime == "trend" and f["momentum"] > hurdle and f["turn"] > 0:
                choices.append(("trend_momentum", f["momentum"], "fast mean above slow mean"))
            if regime != "risk_off" and f["breakout"] > hurdle:
                choices.append(("range_breakout", f["breakout"], "fresh rolling range breakout"))
            if regime == "range" and f["z"] < -1.5 and f["turn"] > hurdle / 2:
                choices.append(("mean_reversion", abs(f["momentum"]), "below range mean with observed turn"))
            relative = f["return"] - benchmark_return
            if regime != "risk_off" and relative > hurdle and f["momentum"] > hurdle / 2:
                choices.append(("relative_strength", relative, "positive momentum above benchmark basket"))
            for family, edge, reason in choices:
                if edge > hurdle:
                    signals.append(Signal(symbol, family, edge / max(1, f["vol"]),
                                          edge, f["vol"], reason))
        return sorted(signals, key=lambda s: (-s.score, s.symbol, s.family))

    def _regime_and_signals(self, now: float):
        """Pure/read-only: derive regime and candidate signals for `now`.

        Reads only self.history/self.latest; never mutates holdings, cooldown
        or counts, so it is safe to call more than once for the same `now`
        (a caller such as strategies.AdaptivePolicy consults the regime before
        deciding whether to gate entries, then _decide_core recomputes the
        same values internally -- deterministic given unchanged inputs).
        """
        c = self.config
        features = {s: f for s in c.symbols if (f := self._features(s, now)) is not None}
        benchmarks = [features[s] for s in c.benchmarks if s in features]
        complete = len(benchmarks) == len(c.benchmarks)
        benchmark_return = statistics.mean(f["return"] for f in benchmarks) if benchmarks else 0
        benchmark_momentum = statistics.mean(f["momentum"] for f in benchmarks) if benchmarks else 0
        risk_off = complete and (benchmark_return < -25
                    or any(f["vol"] > c.volatility_halt_bps for f in benchmarks))
        regime = "unavailable" if not complete else "risk_off" if risk_off else "trend" if benchmark_momentum > c.minimum_edge_bps else "range"
        signals = self._signals(features, regime, benchmark_return) if complete else []
        return features, complete, risk_off, regime, signals

    def _decide_core(self, now: float, *, allow_entries: bool, force_exit: bool,
                      force_exit_reason: str = "trial_end") -> Decision:
        c = self.config
        features, complete, risk_off, regime, signals = self._regime_and_signals(now)
        targets, exits = {}, {}
        self.last_exit_fractions = {}
        for symbol, holding in self.holdings.items():
            latest = self.latest.get(symbol)
            quote_fresh = bool(latest and now - latest.timestamp <= c.quote_age_seconds)
            if quote_fresh:
                holding.high_bid = max(holding.high_bid, latest.bid)
                pnl_bps = (latest.bid / holding.average_price - 1) * 10000
                trail_bps = (latest.bid / holding.high_bid - 1) * 10000
            else:
                pnl_bps, trail_bps = 0, 0
            ctx = ExitContext(now=now, entered_at=holding.entered_at, pnl_bps=pnl_bps,
                              trail_bps=trail_bps, quote_fresh=quote_fresh, risk_off=risk_off,
                              force_exit=force_exit, force_exit_reason=force_exit_reason,
                              volatility_bps=(features.get(symbol) or {}).get("vol"))
            decision = DEFAULT_PLAN.evaluate(ctx, c)
            if decision is not None:
                exits[symbol] = decision.reason
                self.last_exit_fractions[symbol] = decision.fraction
            elif not allow_entries or not complete or now - holding.entered_at < c.min_hold_seconds:
                targets[symbol] = holding.quantity
        # Leverage is an exposure ceiling, not permission to multiply an order.
        # Only a fully warmed trending basket can use the configured ceiling;
        # other regimes reduce it. The independent ledger remains authoritative.
        leverage = min(c.max_leverage, 1 if regime == "range" else c.max_leverage) if regime not in ("risk_off", "unavailable") else 0
        budget = max(0, min(c.gross_cap, c.capital * leverage) - c.max_order_notional)
        used = sum(self.latest[s].ask * float(qty) for s, qty in targets.items() if s in self.latest)
        if allow_entries and complete and not force_exit and not risk_off:
            for signal in signals:
                s = signal.symbol
                if (s in targets or s in exits or self.cooldown.get(s, 0) > now
                        or len(targets) >= c.max_positions):
                    continue
                price = self.latest[s].ask
                # Inverse-volatility allocation is capped by per-order shares;
                # uncertainty can reduce size but cannot override numeric caps.
                allocation = max(price, budget / max(1, c.max_positions) / max(1, signal.volatility_bps / 5))
                allocation = min(allocation, c.max_order_notional)
                qty = min(c.max_shares, int(allocation / price), int((budget - used) / price))
                if qty > 0:
                    targets[s] = qty
                    used += qty * price
                    self.counts[signal.family] += 1
        for symbol in self.holdings:
            if symbol not in targets:
                exits.setdefault(symbol, "portfolio_rotation")
        if regime == "risk_off":
            self.counts["defensive_cash"] += 1
        return Decision(now, regime, targets, tuple(signals), exits, used / c.capital,
                        "benchmark_unavailable" if not complete else "benchmark_risk" if risk_off else "ranked_cost_hurdle_allocation")

    def decide(self, now: float, *, allow_entries: bool = True, force_exit: bool = False) -> Decision | None:
        c = self.config
        if now - self.last_decision < c.rebalance_seconds and not force_exit:
            return None
        self.last_decision = now
        return self._decide_core(now, allow_entries=allow_entries, force_exit=force_exit)


def limit_price(bid: str | float, ask: str | float, side: str, offset: str = "0.02") -> str:
    """Bounded marketable limit; the broker may leave it unfilled."""
    b, a, o = Decimal(str(bid)), Decimal(str(ask)), Decimal(offset)
    if any(not x.is_finite() for x in (b, a, o)) or b <= 0 or a < b or o < 0 or side not in ("buy", "sell"):
        raise ValueError("invalid_limit_input")
    price = a + o if side == "buy" else max(Decimal("0.01"), b - o)
    return str(price.quantize(Decimal("0.01")))
