"""Deterministic strategy-rotation selector (evidence class SYN; synthetic).

No broker connection is made by this module. Every transition is a pure
function of an explicit `timestamp` and the other fields on `DecisionInputs`
-- there is no wall-clock read inside `RegimeSelector`. Operational safety
(kill switch STOP file, risk halt, transport freeze, unreconciled/stale
state) always wins over regime/confidence: any block collapses the state to
NO_NEW_RISK. A state transition never liquidates existing positions unless
`SelectorConfig.portfolio_transition_policy` explicitly requests it; the
default policy holds the incumbent and leaves exit management to the caller's
existing exit chain (e.g. strategies_v1.AdaptivePolicy's stop/take-profit/
trailing/time exits), which keeps running regardless of selector state.

See docs: blueprints/us-equities/acceptance-wave/factors-regimes.md
(states table, "Versioned automatic selection contract") and
blueprints/us-equities/acceptance-wave/research-protocol.json
(`regime_selector`, status "implemented_synthetic_not_accepted"). Promotion
of a strategy pool member beyond this synthetic framework requires HIST
receipts per strategy, then independently qualified paper receipts -- never
automatic acceptance from this module alone.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol, runtime_checkable

WARMING = "WARMING"
NO_NEW_RISK = "NO_NEW_RISK"
HOLD = "HOLD"
ACTIVE = "ACTIVE"
STATES = (WARMING, NO_NEW_RISK, HOLD, ACTIVE)

HOLD_AND_MANAGE_EXITS = "hold_and_manage_exits"
FLATTEN_BEFORE_SWITCH = "flatten_before_switch"
TRANSITION_POLICIES = (HOLD_AND_MANAGE_EXITS, FLATTEN_BEFORE_SWITCH)


@runtime_checkable
class StrategySpec(Protocol):
    """A pre-registered, receipt-pinned strategy pool member.

    `propose` must be a pure function of `decision_inputs` (plus the spec's
    own internal, already-observed state) -- no wall clock, no I/O. It
    returns candidate orders/targets in whatever shape the caller's engine
    (e.g. strategies.AdaptivePolicy) understands; the selector itself never
    interprets the payload, only the spec's id/sessions/regime_affinity and
    the confidence/advantage figures the caller derives from it.
    """

    id: str
    receipt_sha256: str
    sessions: tuple[str, ...]
    regime_affinity: tuple[str, ...]

    def propose(self, decision_inputs: "DecisionInputs"):
        ...


@dataclass(frozen=True)
class SelectorConfig:
    confidence_threshold: float = 0.6
    minimum_advantage_bps: float = 5.0
    entry_hysteresis: float = 2.0
    exit_hysteresis: float = 0.1
    persistence_bars: int = 3
    minimum_residence_s: float = 60.0
    cooldown_s: float = 30.0
    portfolio_transition_policy: str = HOLD_AND_MANAGE_EXITS

    def __post_init__(self):
        numbers = (self.confidence_threshold, self.minimum_advantage_bps, self.entry_hysteresis,
                   self.exit_hysteresis, self.persistence_bars, self.minimum_residence_s, self.cooldown_s)
        if any(not math.isfinite(v) or v < 0 for v in numbers):
            raise ValueError("invalid_selector_config_number")
        if not 0 <= self.confidence_threshold <= 1:
            raise ValueError("invalid_confidence_threshold")
        if not 0 <= self.exit_hysteresis <= self.confidence_threshold:
            raise ValueError("invalid_exit_hysteresis")
        if self.persistence_bars < 1 or int(self.persistence_bars) != self.persistence_bars:
            raise ValueError("invalid_persistence_bars")
        if self.portfolio_transition_policy not in TRANSITION_POLICIES:
            raise ValueError("invalid_portfolio_transition_policy")


@dataclass(frozen=True)
class OperationalStatus:
    """Inputs are observed elsewhere (safety.py/transport.py); this module
    never reads a STOP file, ledger or transport connection itself -- it only
    combines pre-observed booleans so the selector stays pure/testable."""
    kill_switch: bool = False
    risk_halted: bool = False
    transport_frozen: bool = False
    reconciled: bool = True
    state_fresh: bool = True

    @classmethod
    def clear(cls) -> "OperationalStatus":
        return cls()

    def blocked_reasons(self) -> tuple[str, ...]:
        reasons = []
        if self.kill_switch:
            reasons.append("kill_switch")
        if self.risk_halted:
            reasons.append("risk_halted")
        if self.transport_frozen:
            reasons.append("transport_frozen")
        if not self.reconciled:
            reasons.append("unreconciled_state")
        if not self.state_fresh:
            reasons.append("stale_state")
        return tuple(reasons)


@dataclass(frozen=True)
class DecisionInputs:
    """Time is an input, never read from the wall clock inside the selector."""
    timestamp: float
    regime: str
    warmed_up: bool
    operational: OperationalStatus
    candidate_id: str | None
    confidence: float = 0.0
    advantage_bps: float = 0.0

    def __post_init__(self):
        if not math.isfinite(self.timestamp):
            raise ValueError("invalid_timestamp")
        if not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("invalid_confidence")
        if not math.isfinite(self.advantage_bps):
            raise ValueError("invalid_advantage_bps")


@dataclass(frozen=True)
class SelectionDecision:
    timestamp: float
    prior_state: str
    new_state: str
    regime: str
    confidence: float
    advantage_bps: float
    incumbent_id: str | None
    candidate_id: str | None
    reason_codes: tuple[str, ...]
    blocked_by: tuple[str, ...]
    liquidate: bool = False


class RegimeSelector:
    """Deterministic given identical (state, DecisionInputs) sequences.

    Construct fresh (or restore explicit `_state`/counters out of band) per
    trial; there is no hidden global or wall-clock dependency.
    """

    def __init__(self, config: SelectorConfig):
        self.config = config
        self._state = WARMING
        self._incumbent_id: str | None = None
        self._incumbent_since: float = float("-inf")
        self._last_switch_at: float = float("-inf")
        self._persistence_candidate: str | None = None
        self._persistence_count: int = 0

    @property
    def state(self) -> str:
        return self._state

    @property
    def incumbent_id(self) -> str | None:
        return self._incumbent_id

    def _record(self, inputs: DecisionInputs, prior: str, new_state: str,
                reason_codes: tuple[str, ...], blocked_by: tuple[str, ...],
                candidate_id: str | None, liquidate: bool = False) -> SelectionDecision:
        self._state = new_state
        return SelectionDecision(
            timestamp=inputs.timestamp, prior_state=prior, new_state=new_state,
            regime=inputs.regime, confidence=inputs.confidence, advantage_bps=inputs.advantage_bps,
            incumbent_id=self._incumbent_id, candidate_id=candidate_id,
            reason_codes=reason_codes, blocked_by=blocked_by, liquidate=liquidate)

    def _reset_persistence(self) -> None:
        self._persistence_candidate = None
        self._persistence_count = 0

    def decide(self, inputs: DecisionInputs) -> SelectionDecision:
        c = self.config
        prior = self._state

        # Invariant: an operational block always yields NO_NEW_RISK, no
        # matter how favorable the regime/confidence look.
        blocked = inputs.operational.blocked_reasons()
        if blocked:
            self._reset_persistence()
            return self._record(inputs, prior, NO_NEW_RISK,
                                 ("operational_block",), blocked, inputs.candidate_id)

        if not inputs.warmed_up:
            self._reset_persistence()
            return self._record(inputs, prior, WARMING, ("indicators_not_ready",), (), inputs.candidate_id)

        candidate = inputs.candidate_id
        meets_confidence = candidate is not None and inputs.confidence >= c.confidence_threshold

        if self._incumbent_id is None:
            # First activation: no incumbent to beat, so only the confidence
            # gate (plus persistence) applies.
            if not meets_confidence:
                self._reset_persistence()
                reason = ("no_candidate",) if candidate is None else ("confidence_below_threshold",)
                return self._record(inputs, prior, NO_NEW_RISK, reason, (), candidate)
            if self._persistence_candidate == candidate:
                self._persistence_count += 1
            else:
                self._persistence_candidate, self._persistence_count = candidate, 1
            if self._persistence_count < c.persistence_bars:
                return self._record(inputs, prior, HOLD, ("persistence_pending",), (), candidate)
            self._incumbent_id = candidate
            self._incumbent_since = inputs.timestamp
            self._last_switch_at = inputs.timestamp
            self._reset_persistence()
            return self._record(inputs, prior, ACTIVE, ("activated",), (), candidate)

        if candidate == self._incumbent_id:
            self._reset_persistence()
            if inputs.confidence >= c.confidence_threshold - c.exit_hysteresis:
                return self._record(inputs, prior, ACTIVE, ("incumbent_confirmed",), (), candidate)
            return self._record(inputs, prior, HOLD, ("incumbent_confidence_degraded",), (), candidate)

        # A different candidate is proposed: require confidence, an
        # advantage over the incumbent beyond entry hysteresis, sustained
        # persistence, minimum incumbent residence, and cooldown since the
        # last switch -- all five gates -- before switching away.
        residence_ok = (inputs.timestamp - self._incumbent_since) >= c.minimum_residence_s
        cooldown_ok = (inputs.timestamp - self._last_switch_at) >= c.cooldown_s
        advantage_ok = inputs.advantage_bps >= (c.minimum_advantage_bps + c.entry_hysteresis)
        gate_ok = meets_confidence and advantage_ok

        if gate_ok and self._persistence_candidate == candidate:
            self._persistence_count += 1
        elif gate_ok:
            self._persistence_candidate, self._persistence_count = candidate, 1
        else:
            self._reset_persistence()

        persistence_ok = gate_ok and self._persistence_count >= c.persistence_bars

        if gate_ok and persistence_ok and residence_ok and cooldown_ok:
            liquidate = c.portfolio_transition_policy == FLATTEN_BEFORE_SWITCH
            self._incumbent_id = candidate
            self._incumbent_since = inputs.timestamp
            self._last_switch_at = inputs.timestamp
            self._reset_persistence()
            return self._record(inputs, prior, ACTIVE, ("switched",), (), candidate, liquidate=liquidate)

        if candidate is None:
            reasons = ["no_candidate"]
        else:
            reasons = []
            if not meets_confidence:
                reasons.append("confidence_below_threshold")
            if not advantage_ok:
                reasons.append("advantage_below_hysteresis")
            if gate_ok and not persistence_ok:
                reasons.append("persistence_pending")
            if gate_ok and not residence_ok:
                reasons.append("incumbent_residence_not_satisfied")
            if gate_ok and not cooldown_ok:
                reasons.append("cooldown_not_elapsed")
            if not reasons:
                reasons.append("switch_conditions_not_met")
        return self._record(inputs, prior, HOLD, tuple(reasons), (), candidate)
