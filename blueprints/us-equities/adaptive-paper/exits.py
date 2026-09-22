"""G-f: an ordered, data-driven exit rule chain for the per-holding exit
decision inside strategies_v1.AdaptivePolicy._decide_core.

This module only *restructures* the exit chain that used to be an inline
ternary in _decide_core into named, independently testable rules. With
every new PolicyConfig knob this module reads left at its shipped default
(vol_stop_multiplier=1.0, stop_min_bps==stop_max_bps==stop_bps,
trailing_min_bps==trailing_max_bps==trailing_bps, take_profit_fraction=1.0,
time_decay_start_seconds=None, time_decay_min_multiplier=1.0) every rule
below evaluates to exactly the same reason string, in exactly the same
order, as the pre-refactor inline chain -- see
receipts/adaptive_policy_v1.golden.json and
tests/test_adaptive_paper_exits.py's default-byte-identity test. Changing
any of those fields away from its default is a synthetic (evidence class
SYN), independently unqualified variant, same as every other threshold in
PolicyConfig.

Ordering (first matching rule wins, exactly mirrors the brief's precedence
list): trial/session end (force_exit) > regime_flip (risk_off) >
quote_stale > vol-scaled stop > partial take-profit > vol-scaled trailing >
time_exit (kept in its original chain position, immediately before the
portfolio_rotation fallback _decide_core applies afterward) -- vol-scaling
and time-decay tightening are folded into the *thresholds* rules 4 and 6
test against (computed once per holding by `effective_thresholds`, not
separate chain entries), since the original engine has no separate
"time-decay" or "vol-scale" *reason* string and inventing one would break
byte-identity by construction. gap-risk/overnight rules stay exactly where
they already lived -- native_strategy.py's `_gap_risk_stop_symbols` /
`evaluate_gap_risk`, applied at the order layer using inputs (the prior
session's captured RTH close) `_decide_core` does not have -- and
portfolio_rotation stays the existing post-loop fallback in
strategies_v1.AdaptivePolicy._decide_core. This module does not duplicate
either of those.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExitContext:
    """Everything one rule needs to decide whether *this* holding exits now.

    `pnl_bps`/`trail_bps` are 0 when the latest quote is missing or stale
    (matching _decide_core's pre-refactor computation) so a stale quote
    cannot itself trigger a stop/take-profit/trailing rule -- the
    quote_stale rule, evaluated first, already claims that case.
    """
    now: float
    entered_at: float
    pnl_bps: float
    trail_bps: float
    quote_fresh: bool
    risk_off: bool
    force_exit: bool
    force_exit_reason: str
    volatility_bps: float | None = None


@dataclass(frozen=True)
class ExitDecision:
    reason: str
    fraction: float = 1.0
    price_rule: str = "market"


# Reason -> the price_rule a resting sell order for that reason should use.
# Consulted by native_strategy.AdaptiveStrategy to decide whether a resting
# exit order needs cancel-then-replace (see replace_exit there): a reason
# whose price_rule differs from the resting order's recorded price_rule has
# had its price basis change (e.g. a trailing stop ratchet) and should be
# resubmitted at the new price, not left resting at the old one.
REASON_PRICE_RULE = {
    "stop_loss": "stop",
    "take_profit": "take_profit",
    "trailing_stop": "trailing",
}


def _clamp(value, lo, hi):
    return min(hi, max(lo, value))


def effective_thresholds(ctx: ExitContext, c) -> tuple[float, float]:
    """(effective_stop_bps, effective_trailing_bps) for this tick: the
    configured stop_bps/trailing_bps, scaled by a realised-volatility
    multiplier and clamped to [*_min_bps, *_max_bps], then further
    tightened linearly once the hold has run past
    time_decay_start_seconds (disabled by default). Every step is a no-op
    at the shipped defaults; see module docstring."""
    if ctx.volatility_bps is not None and c.vol_reference_bps:
        vol_factor = max(ctx.volatility_bps, 0.01) / c.vol_reference_bps
    else:
        vol_factor = 1.0
    stop_bps = _clamp(c.stop_bps * c.vol_stop_multiplier * vol_factor, c.stop_min_bps, c.stop_max_bps)
    trailing_bps = _clamp(c.trailing_bps * c.vol_stop_multiplier * vol_factor,
                          c.trailing_min_bps, c.trailing_max_bps)
    if c.time_decay_start_seconds is not None and c.max_hold_seconds > c.time_decay_start_seconds:
        elapsed = ctx.now - ctx.entered_at
        if elapsed >= c.time_decay_start_seconds:
            t = min(1.0, (elapsed - c.time_decay_start_seconds)
                    / (c.max_hold_seconds - c.time_decay_start_seconds))
            decay = 1.0 - t * (1.0 - c.time_decay_min_multiplier)
            stop_bps *= decay
            trailing_bps *= decay
    return stop_bps, trailing_bps


def _rule_force_exit(ctx, c, stop_bps, trailing_bps):
    if ctx.force_exit:
        return ExitDecision(ctx.force_exit_reason, 1.0, "market")
    return None


def _rule_risk_off(ctx, c, stop_bps, trailing_bps):
    if ctx.risk_off:
        return ExitDecision("risk_off", 1.0, "market")
    return None


def _rule_quote_stale(ctx, c, stop_bps, trailing_bps):
    if not ctx.quote_fresh:
        return ExitDecision("quote_stale", 1.0, "market")
    return None


def _rule_stop(ctx, c, stop_bps, trailing_bps):
    if ctx.pnl_bps <= -stop_bps:
        return ExitDecision("stop_loss", 1.0, "stop")
    return None


def _rule_take_profit(ctx, c, stop_bps, trailing_bps):
    if ctx.pnl_bps >= c.take_profit_bps:
        return ExitDecision("take_profit", c.take_profit_fraction, "take_profit")
    return None


def _rule_trailing(ctx, c, stop_bps, trailing_bps):
    if ctx.trail_bps <= -trailing_bps:
        return ExitDecision("trailing_stop", 1.0, "trailing")
    return None


def _rule_time_exit(ctx, c, stop_bps, trailing_bps):
    if ctx.now - ctx.entered_at >= c.max_hold_seconds:
        return ExitDecision("time_exit", 1.0, "market")
    return None


DEFAULT_RULES = (
    _rule_force_exit,
    _rule_risk_off,
    _rule_quote_stale,
    _rule_stop,
    _rule_take_profit,
    _rule_trailing,
    _rule_time_exit,
)


@dataclass(frozen=True)
class ExitPlan:
    """An ordered tuple of rule callables; first non-None result wins.

    Each rule is `(ctx, config, effective_stop_bps, effective_trailing_bps)
    -> ExitDecision | None`. The default plan (`ExitPlan()`) is exactly the
    original inline chain's ordering; a caller could construct a plan with
    a different rule order/subset for research, but strategies_v1.py never
    does -- only DEFAULT_RULES is wired into _decide_core.
    """
    rules: tuple = DEFAULT_RULES

    def evaluate(self, ctx: ExitContext, config) -> ExitDecision | None:
        stop_bps, trailing_bps = effective_thresholds(ctx, config)
        for rule in self.rules:
            decision = rule(ctx, config, stop_bps, trailing_bps)
            if decision is not None:
                return decision
        return None


DEFAULT_PLAN = ExitPlan()
