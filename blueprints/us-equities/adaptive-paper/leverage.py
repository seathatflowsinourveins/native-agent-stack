"""G-e: the opt-in leverage-schedule policy layer (`leverage-schedule-v1-20260922`).

Pure and side-effect free: no I/O, no broker/transport calls, no mutation of
caller state. Every function here is a deterministic mapping from validated
config/inputs to a bounded decision. This module is only ever consulted when
a config's optional top-level `leverage_policy` block is present and has
already passed `validate_leverage_policy` below; with that block absent
(every shipped config as of `bdd04ca`), nothing in this module is imported
into the decision path at all -- see runner.py's `load_config` and
strategies.py's `AdaptivePolicy.decide` for the opt-in gate.

No optimiser, learned leverage or per-trade discretion lives here: the
session/regime schedule and the drawdown ladder are constants frozen in
config (see `CANONICAL_V1_BLOCK`), identical across every leverage rung.
This module only evaluates the frozen policy against the caller's already-
observed session/regime/drawdown/kill-switch/account-multiplier inputs.

See agent-lab's `docs/decisions/2026-09-22-leverage-schedule-and-entitlement.md`
(referenced by `decision_record` below; that record lives in the agent-lab
repository, not this one) for the design rationale, and
`blueprints/us-equities/adaptive-paper/README-safety.md` for the enforcement
points this policy layer sits in front of (safety.py's independent ledger
ceiling is authoritative regardless of what this module returns).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from itertools import pairwise

D = Decimal
ZERO = D(0)

LEVERAGE_POLICY_VERSION = "leverage-schedule-v1-20260922"
INTRADAY_MAX = D("4")
OVERNIGHT_MAX = D("2")  # Reg T
SESSIONS = ("PRE", "RTH", "POST", "CLOSED")
REGIMES = ("trend", "range", "risk_off", "unavailable")
ZERO_REGIMES = ("risk_off", "unavailable")
# strategies_v1._decide_core caps a "range" regime's leverage at 1
# regardless of the configured max_leverage; a schedule cell above that for
# "range" would authorize an entry budget the engine can never actually use,
# so it is refused at validation time rather than silently ignored.
ENGINE_RANGE_CAP = D("1")

# The single schedule/ladder every rung config must use verbatim (see
# blueprints/us-equities/adaptive-paper/config-leverage-{1,2,4}x.json).
# DP-2: enforced by `validate_leverage_policy` itself -- a shape-valid but
# non-canonical block (e.g. a hand-edited schedule/ladder that still passes
# every generic bound) must not reach the pre-registered >1x lane; the
# equality check below is the actual gate, not merely a config-authoring
# invariant. tests/test_adaptive_paper_runner.py additionally asserts every
# shipped rung config's block equals this constant byte-for-byte.
CANONICAL_V1_BLOCK = {
    "version": LEVERAGE_POLICY_VERSION,
    "decision_record": "agent-lab/docs/decisions/2026-09-22-leverage-schedule-and-entitlement.md",
    "schedule": {
        "RTH":    {"trend": "4", "range": "1", "risk_off": "0", "unavailable": "0"},
        "PRE":    {"trend": "1", "range": "1", "risk_off": "0", "unavailable": "0"},
        "POST":   {"trend": "1", "range": "1", "risk_off": "0", "unavailable": "0"},
        "CLOSED": {"trend": "0", "range": "0", "risk_off": "0", "unavailable": "0"},
    },
    "overnight_max_leverage": "2",
    "drawdown_ladder": [
        {"from_drawdown_fraction": "0",    "max_leverage": "4"},
        {"from_drawdown_fraction": "0.25", "max_leverage": "2"},
        {"from_drawdown_fraction": "0.5",  "max_leverage": "1"},
        {"from_drawdown_fraction": "0.75", "max_leverage": "0"},
    ],
}


# The discrete leverage rungs this schedule ships pre-registered configs for
# (config-leverage-1x/2x/4x.json). Pure/static; used only by the runner's
# achieved-leverage receipt (F2, 2026-09-22 residual review finding:
# reachability) -- this receipt exists so a rung's gate row's flip to
# established can eventually be checked against evidence that achieved
# exposure actually exceeded the next-lower rung's own ceiling, since
# strategies_v1._decide_core's budget/allocation math means a higher
# max_leverage does not by itself force higher achieved exposure. As of
# 2026-09-22 leverage fix round 2 (N1-1) no gate row in
# catalogs/us-equities/gates-20260922.json reads this receipt yet, so a
# rung's gate row can still flip on a receipt that never showed it -- see
# README-safety.md's Leverage schedule section. Not consulted by
# ceiling()/envelope() and does not change the schedule/ladder
# CANONICAL_V1_BLOCK enforces.
RUNGS = (D("1"), D("2"), D("4"))


def next_lower_rung_ceiling(max_leverage: Decimal) -> Decimal | None:
    """The largest pre-registered rung strictly below `max_leverage`, or
    None when there is none (the 1x rung itself, or any value <= the lowest
    rung). Used to compute how long a run spent with achieved (gross
    exposure / equity) leverage above the ceiling the next rung down would
    have imposed -- evidence the run actually needed this rung's higher
    ceiling rather than merely staying inside a lower one's proportional
    room the whole time."""
    lower = [r for r in RUNGS if r < max_leverage]
    return max(lower) if lower else None


class LeveragePolicyError(ValueError):
    """Bounded reason code; safe to retain, mirrors safety.SafetyError."""


def _require(condition, reason):
    if not condition:
        raise LeveragePolicyError(reason)


def _dec_str(value):
    """A finite, non-negative Decimal parsed strictly from `str`, at most 2
    decimal places -- the contract every leverage-policy number (config
    max_leverage, schedule cells, ladder fractions/steps, overnight cap)
    shares. Rejects float/int/bool (a bool is not `str`), NaN/Infinity,
    negative values and anything with more than 2 fractional digits."""
    if type(value) is not str:
        raise LeveragePolicyError("leverage_value_invalid")
    try:
        result = D(value)
    except InvalidOperation:
        raise LeveragePolicyError("leverage_value_invalid") from None
    if not result.is_finite() or result < 0:
        raise LeveragePolicyError("leverage_value_invalid")
    exponent = result.as_tuple().exponent
    if isinstance(exponent, str) or exponent < -2:
        raise LeveragePolicyError("leverage_value_invalid")
    return result


def _dec_config(value):
    """A finite Decimal parsed from an existing config number (already
    validated elsewhere as a `str` by safety.RiskLimits/sessions.py); no
    2dp restriction, matching that wider existing contract."""
    try:
        result = D(str(value))
    except InvalidOperation:
        raise LeveragePolicyError("leverage_value_invalid") from None
    if not result.is_finite():
        raise LeveragePolicyError("leverage_value_invalid")
    return result


@dataclass(frozen=True)
class LeverageInputs:
    """Per-tick, caller-observed inputs the policy layer's `ceiling()`
    consults. `session` is a `sessions.SessionKind` value (or None when the
    current wall-clock time is outside the frozen session calendar --
    unclassifiable, so `ceiling()`/`envelope()` fail closed to 0).

    `pending_buy_notional_usd` (LEV-RI-A, 2026-09-22 leverage fix round 1):
    the ledger's own `AccountState.pending_buy_notional_usd` -- the notional
    of every not-yet-filled buy intent (reserved/submitted/partially filled)
    -- so strategies_v1._decide_core's leveraged-rung budget can net out
    capital already committed to a resting order the policy layer's own
    `self.holdings` (filled positions only) cannot see. Defaults to 0 so a
    caller that does not observe the ledger (e.g. a direct unit-test
    construction) reproduces the pre-fix behavior exactly."""
    session: str | None
    drawdown_fraction: Decimal
    kill_switch: bool
    account_multiplier: Decimal | None = None
    pending_buy_notional_usd: Decimal = D("0")


@dataclass(frozen=True)
class LeveragePolicy:
    version: str
    max_leverage: Decimal
    # ((session, ((regime, value), ...)), ...) -- hashable/asdict-able,
    # ordered by SESSIONS/REGIMES for a deterministic, comparable value.
    schedule: tuple[tuple[str, tuple[tuple[str, Decimal], ...]], ...]
    overnight_max_leverage: Decimal
    ladder: tuple[tuple[Decimal, Decimal], ...]  # (from_fraction, max_leverage), ascending fraction
    apply_overnight_cap: bool

    def _cell(self, session: str, regime: str) -> Decimal:
        for s, row in self.schedule:
            if s == session:
                for r, v in row:
                    if r == regime:
                        return v
        # Unreachable once constructed only via validate_leverage_policy
        # (which requires every SESSIONS x REGIMES cell to be present).
        raise LeveragePolicyError("leverage_schedule_shape")

    def ladder_step(self, fraction: Decimal) -> Decimal:
        """Fail closed (0) for a non-finite or negative fraction; otherwise
        the ladder's last step whose threshold `fraction` has reached or
        passed. Monotone non-increasing in `fraction` by construction
        (validate_leverage_policy refuses a non-monotone ladder)."""
        if not fraction.is_finite() or fraction < 0:
            return ZERO
        step = ZERO
        for start, lev in self.ladder:
            if fraction >= start:
                step = lev
        return step

    def ceiling(self, *, session, regime, drawdown_fraction, kill_switch, account_multiplier=None) -> Decimal:
        """Policy-layer ceiling: the full session x regime x drawdown key,
        plus the kill switch, the overnight cap (when applicable) and the
        broker-proven account multiplier. Invariant: `ceiling(...) <=
        envelope(session=..., drawdown_fraction=...)` for every regime."""
        if kill_switch or session not in SESSIONS or regime not in REGIMES:
            return ZERO
        c = min(self.max_leverage, self._cell(session, regime), self.ladder_step(drawdown_fraction))
        if self.apply_overnight_cap:
            c = min(c, self.overnight_max_leverage)
        if account_multiplier is not None:
            c = min(c, account_multiplier)
        return max(c, ZERO)

    def envelope(self, *, session, drawdown_fraction) -> Decimal:
        """Ledger-layer ceiling: a regime-independent upper bound (the max
        over every regime's cell), since the ledger (safety.py) has no
        regime input of its own -- the policy layer (`ceiling()` above)
        enforces the regime-specific part independently, and every entry
        must pass both."""
        if session not in SESSIONS:
            return ZERO
        cell = max(self._cell(session, r) for r in REGIMES)
        c = min(self.max_leverage, cell, self.ladder_step(drawdown_fraction))
        if self.apply_overnight_cap:
            c = min(c, self.overnight_max_leverage)
        return c


def validate_leverage_policy(config: dict, session_policy: dict) -> LeveragePolicy:
    """Validate `config["leverage_policy"]` (already known to be present by
    the caller) against `config["max_leverage"]`/`capital_usd`/
    `max_gross_exposure_usd` and the already-validated `session_policy`
    (`sessions.validate_session_policy`'s return value). Raises
    `LeveragePolicyError` with a bounded reason code on any defect."""
    block = config.get("leverage_policy")
    _require(isinstance(block, dict), "leverage_policy_keys")
    allowed_keys = {"version", "decision_record", "schedule", "overnight_max_leverage", "drawdown_ladder"}
    required_keys = {"version", "schedule", "overnight_max_leverage", "drawdown_ladder"}
    _require(set(block) <= allowed_keys and required_keys <= set(block), "leverage_policy_keys")
    _require(block["version"] == LEVERAGE_POLICY_VERSION, "leverage_policy_version_mismatch")
    if "decision_record" in block:
        _require(isinstance(block["decision_record"], str) and block["decision_record"], "leverage_policy_keys")

    L = _dec_str(config["max_leverage"])
    _require(D("1") <= L <= INTRADAY_MAX, "leverage_requested_out_of_bounds")

    schedule_raw = block["schedule"]
    _require(isinstance(schedule_raw, dict) and set(schedule_raw) == set(SESSIONS), "leverage_schedule_shape")
    cells = {}
    for session in SESSIONS:
        row = schedule_raw[session]
        _require(isinstance(row, dict) and set(row) == set(REGIMES), "leverage_schedule_shape")
        for regime in REGIMES:
            value = _dec_str(row[regime])
            _require(value <= INTRADAY_MAX, "leverage_value_invalid")
            cells[(session, regime)] = value
    _require(all(cells[(s, r)] == ZERO for s in SESSIONS for r in ZERO_REGIMES), "leverage_nonzero_in_risk_off")
    _require(all(cells[("CLOSED", r)] == ZERO for r in REGIMES), "leverage_nonzero_when_closed")
    _require(all(cells[(s, "range")] <= ENGINE_RANGE_CAP for s in SESSIONS), "leverage_range_exceeds_engine_cap")

    O = _dec_str(block["overnight_max_leverage"])
    _require(ZERO < O <= OVERNIGHT_MAX, "leverage_overnight_out_of_bounds")

    ladder_raw = block["drawdown_ladder"]
    _require(isinstance(ladder_raw, list), "leverage_ladder_thresholds")
    steps = []
    for item in ladder_raw:
        _require(isinstance(item, dict) and set(item) == {"from_drawdown_fraction", "max_leverage"},
                 "leverage_ladder_thresholds")
        fraction = _dec_str(item["from_drawdown_fraction"])
        level = _dec_str(item["max_leverage"])
        _require(level <= INTRADAY_MAX, "leverage_value_invalid")
        steps.append((fraction, level))
    _require(len(steps) >= 2 and steps[0][0] == ZERO, "leverage_ladder_must_start_at_zero")
    _require(all(a[0] < b[0] for a, b in pairwise(steps)) and steps[-1][0] < D("1"), "leverage_ladder_thresholds")
    _require(all(a[1] >= b[1] for a, b in pairwise(steps)), "leverage_ladder_not_monotone")
    _require(steps[-1][1] == ZERO, "leverage_ladder_must_end_at_zero")
    _require(steps[0][1] <= INTRADAY_MAX, "leverage_value_invalid")

    cap = _dec_config(config["capital_usd"])
    gross = _dec_config(config["max_gross_exposure_usd"])
    _require(gross <= cap * L, "leverage_gross_cap_exceeds_capital_times_leverage")
    if session_policy["overnight_holds"]:
        multiple = D(str(session_policy["overnight_gross_multiple"]))
        _require(gross * multiple <= cap * O, "leverage_overnight_gross_exceeds_regt")

    # DP-2: the block is identical in every rung config and is compared to
    # this canonical constant. Every field-level check above already refuses
    # a malformed/out-of-bounds block with its own specific reason code; a
    # block that instead passes every one of those checks but still differs
    # from CANONICAL_V1_BLOCK (e.g. a hand-edited schedule/ladder within
    # bounds) must not reach the pre-registered >1x lane, so it is refused
    # here as the last check.
    canonical = CANONICAL_V1_BLOCK if "decision_record" in block else {
        k: v for k, v in CANONICAL_V1_BLOCK.items() if k != "decision_record"}
    _require(block == canonical, "leverage_policy_block_not_canonical")

    schedule = tuple((s, tuple((r, cells[(s, r)]) for r in REGIMES)) for s in SESSIONS)
    return LeveragePolicy(version=block["version"], max_leverage=L, schedule=schedule,
                          overnight_max_leverage=O, ladder=tuple(steps),
                          apply_overnight_cap=bool(session_policy["overnight_holds"]))
