"""Deterministic research policies; every order still passes broker/risk controls.

The default inline policy families (trend/breakout/mean-reversion/relative-
strength/defensive-cash) live verbatim in strategies_v1.py, the only shipped
member of registry.json (evidence_class "SYN"). `AdaptivePolicy` here
subclasses that implementation unchanged and, when constructed with a
non-empty `strategy_pool` and/or an explicit `selector`, consults the
selector (selector.py) before allowing new entries. With the default empty
pool and no selector -- i.e. every existing call site (`AdaptivePolicy(config)`)
-- behavior is byte-identical to the pre-selector implementation; see
blueprints/us-equities/adaptive-paper/receipts/adaptive_policy_v1.golden.json
and tests/test_adaptive_paper_strategies.py's golden-equivalence test.
"""
from __future__ import annotations

from decimal import Decimal

from strategies_v1 import (
    AdaptivePolicy as _AdaptivePolicyV1,
    Decision,
    Holding,
    PolicyConfig,
    QUOTE_FUTURE_TOLERANCE_SECONDS,
    Sample,
    Signal,
    limit_price,
)
from selector import (
    ACTIVE,
    DecisionInputs,
    OperationalStatus,
    RegimeSelector,
    SelectorConfig,
    StrategySpec,
)

__all__ = [
    "AdaptivePolicy", "AdaptivePolicyV1", "PolicyConfig", "Sample", "Signal",
    "Decision", "Holding", "limit_price", "Decimal", "QUOTE_FUTURE_TOLERANCE_SECONDS",
    "DecisionInputs", "OperationalStatus", "RegimeSelector", "SelectorConfig", "StrategySpec",
]

# Kept importable under this name too, for callers/tests that want the
# unwrapped v1 engine explicitly rather than relying on the default (empty
# pool) path of AdaptivePolicy below.
AdaptivePolicyV1 = _AdaptivePolicyV1


class AdaptivePolicy(_AdaptivePolicyV1):
    """AdaptivePolicyV1 plus an optional strategy-pool/selector gate.

    `strategy_pool` and `selector` default to values that reproduce the
    original, single-policy behavior exactly: no strategy pool and no
    selector means `decide()` is `AdaptivePolicyV1.decide()` unchanged. This
    class only adds a synthetic (evidence class SYN), not-yet-accepted
    rotation framework on top; see selector.py's module docstring and
    blueprints/us-equities/acceptance-wave/research-protocol.json's
    `regime_selector` field for what "accepted" would require.
    """

    def __init__(self, config: PolicyConfig, strategy_pool: tuple[StrategySpec, ...] = (),
                 selector: RegimeSelector | None = None):
        strategy_pool = tuple(strategy_pool)
        if selector is not None and not strategy_pool:
            # A selector with nothing to select would gate allow_entries on
            # NO_NEW_RISK/HOLD forever (no candidate_id is ever proposed),
            # silently blocking all entries. Fail loudly at construction
            # instead of producing a policy that never trades.
            raise ValueError("selector requires a non-empty strategy_pool")
        super().__init__(config)
        self.strategy_pool = strategy_pool
        self.selector = selector
        self.last_selector_decision = None
        self.quote_ns = {}
        self.quote_tombstones = {}

    def invalidate_quote(self, symbol: str, ts_ns: int):
        if ts_ns >= self.quote_ns.get(symbol, 0):
            self.quote_tombstones[symbol] = max(ts_ns, self.quote_tombstones.get(symbol, 0))
            self.latest.pop(symbol, None)

    def observe_native(self, symbol: str, bid: float, ask: float, ts_ns: int) -> bool:
        # Native data-engine ticks can already be queued at invalidation time.
        # Compare their exact integer event time before reducing it to seconds.
        if ts_ns <= max(self.quote_ns.get(symbol, 0), self.quote_tombstones.get(symbol, 0)):
            return False
        timestamp = ts_ns / 1_000_000_000
        old = self.latest.get(symbol)
        if old is not None and timestamp == old.timestamp:
            # A genuinely newer nanosecond can round to the same float second.
            # v1 history buckets stay unchanged; only latest authority advances.
            self.latest.pop(symbol)
        if not super().observe(symbol, bid, ask, timestamp):
            if old is not None:
                self.latest[symbol] = old
            return False
        self.quote_ns[symbol] = ts_ns
        return True

    def _evaluate_pool(self, regime: str, risk_off: bool, signals: tuple[Signal, ...]):
        """Synthetic, deterministic candidate scoring for the shipped
        single-member pool. This is framework plumbing, not a qualified
        multi-strategy ranking: with exactly one registered strategy there is
        nothing to rank against, so advantage_bps is always 0 (no incumbent
        to beat) and confidence is a coarse, documented placeholder derived
        from whether the regime is readable and non-defensive. A real
        confidence/advantage signal requires per-strategy HIST/paper receipts
        (see selector.py docstring) before it can gate live rotation.
        """
        if not self.strategy_pool or regime == "unavailable":
            return None, 0.0, 0.0
        candidate = self.strategy_pool[0]
        if risk_off:
            return candidate.id, 0.0, 0.0
        confidence = 1.0 if signals else 0.5
        return candidate.id, confidence, 0.0

    def decide(self, now: float, *, allow_entries: bool = True, force_exit: bool = False,
               operational: OperationalStatus | None = None) -> Decision | None:
        c = self.config
        if not self.strategy_pool and self.selector is None:
            # Exact original path: no wrapper computation, no extra reads.
            return super().decide(now, allow_entries=allow_entries, force_exit=force_exit)

        if now - self.last_decision < c.rebalance_seconds and not force_exit:
            return None
        self.last_decision = now

        features, complete, risk_off, regime, signals = self._regime_and_signals(now)
        candidate_id, confidence, advantage_bps = self._evaluate_pool(regime, risk_off, signals)

        entries_allowed = allow_entries
        # R6: capture the caller's own force_exit before the selector can
        # mutate it below. If the caller already requested a force exit this
        # tick (trial deadline/STOP/cleanup -- runner.py's force_exit), that
        # reason must win over a same-tick selector liquidation; only a
        # liquidation that itself turns force_exit on (caller had not
        # already asked for one) is genuinely selector-driven and gets the
        # distinct "rotation_flatten" reason.
        caller_force_exit = force_exit
        if self.selector is not None:
            inputs = DecisionInputs(
                timestamp=now, regime=regime, warmed_up=complete,
                operational=operational if operational is not None else OperationalStatus.clear(),
                candidate_id=candidate_id, confidence=confidence, advantage_bps=advantage_bps)
            self.last_selector_decision = self.selector.decide(inputs)
            # Invariant: a state change never liquidates existing positions
            # unless SelectorConfig.portfolio_transition_policy explicitly
            # says so (FLATTEN_BEFORE_SWITCH). That is the only source of
            # `liquidate=True`; when it fires, route through _decide_core's
            # existing force_exit path so exits are still emitted by the
            # unmodified stop/take-profit/trailing/time-exit chain (no new
            # order type is introduced here) -- only the recorded exit reason
            # differs ("rotation_flatten" instead of the generic "trial_end",
            # so the decision event and any order tag built from it can tell
            # a selector-driven flatten apart from an actual end-of-trial exit).
            entries_allowed = allow_entries and self.last_selector_decision.new_state == ACTIVE
            if self.last_selector_decision.liquidate:
                force_exit = True
                force_exit_reason = "trial_end" if caller_force_exit else "rotation_flatten"
                entries_allowed = False
            else:
                force_exit_reason = "trial_end"
        else:
            force_exit_reason = "trial_end"

        return self._decide_core(now, allow_entries=entries_allowed, force_exit=force_exit,
                                  force_exit_reason=force_exit_reason)
