"""Versioned §6 hypotheses, never tuned or changed by a model.

Source: us-equities-trading #25@b0994749ca6c52ad07cb3bb70e8b5b6cd4fac910 §6;
measured-exit scope: #47@2e0860ccd1d485593d1bd31b8a97c12198ca6b3d D1/D2.
CTS@eab8d5cb position-sizer and breakout-trade-planner references. The explicit
code-managed-limit execution variant is separate from the target native plans.
"""

from dataclasses import dataclass, replace
from decimal import Decimal
from types import MappingProxyType


@dataclass(frozen=True)
class ExitPolicy:
    version: str
    boundary: str
    next_trading_day: bool
    margin_seconds: int = 120


# These are candidate timing parameters, not historically selected policies or
# broker permissions. OVERNIGHT remains admitted to research while unsupported
# execution sessions hold and flag through the shared T15 boundary.
EXIT_POLICIES = MappingProxyType(
    {
        "regular-close-v1": ExitPolicy("regular-close-v1", "RTH_CLOSE", False),
        "after-hours-v1": ExitPolicy("after-hours-v1", "POST_CLOSE", False),
        "overnight-v1": ExitPolicy("overnight-v1", "PRE_OPEN", True),
        "next-premarket-v1": ExitPolicy("next-premarket-v1", "RTH_OPEN", True),
    }
)


@dataclass(frozen=True)
class Preset:
    version: str
    cap_fraction: Decimal
    stop_atr: Decimal
    trail_atr: Decimal
    trail_from_r: Decimal
    take_profit_r: Decimal | None
    take_profit_fraction: Decimal
    max_sessions: int
    confirmation_seconds: int
    spread_stop_fraction: Decimal
    overnight: bool
    native_entry: str
    stop_limit_offset_atr: Decimal
    max_hold_seconds: int | None = None
    exit_policy: ExitPolicy | None = None


D = Decimal
PRESETS = MappingProxyType(
    {
        "conservative-v1": Preset(
            "conservative-v1",
            D("0.25"),
            D("1.5"),
            D("1.5"),
            D("1"),
            D("2"),
            D("1"),
            1,
            300,
            D("0.25"),
            False,
            "limit",
            D("0.25"),
        ),
        "standard-v1": Preset(
            "standard-v1",
            D("0.5"),
            D("2"),
            D("2"),
            D("1"),
            D("2"),
            D("0.5"),
            5,
            0,
            D("1") / D("3"),
            True,
            "stop_limit",
            D("0.5"),
        ),
        "aggressive-v1": Preset(
            "aggressive-v1",
            D("1"),
            D("3"),
            D("3"),
            D("0"),
            None,
            D("1"),
            5,
            0,
            D("0.5"),
            True,
            "limit",
            D("0.5"),
        ),
    }
)


def preset_for(
    version: str,
    family: str,
    catalyst_kind: str = "concrete",
    *,
    exit_policy: str | None = None,
) -> Preset:
    try:
        preset = PRESETS[version]
    except KeyError as error:
        raise ValueError("unregistered_preset") from error
    if (
        family == "squeeze_borrow"
        or family == "catalyst"
        and catalyst_kind == "narrative"
    ):
        preset = replace(preset, trail_atr=D("1.5"), trail_from_r=D("1"))
    if family == "halt_reopen":
        preset = replace(preset, max_hold_seconds=3600)
    if family in {"post_earnings_drift", "trend_new_highs"}:
        # "Weeks" is resolved to 20 sessions in this version; still a hypothesis.
        preset = replace(preset, max_sessions=20 if preset.overnight else 1)
    if family == "trend_new_highs":
        preset = replace(preset, take_profit_r=None)
    if exit_policy is not None:
        try:
            policy = EXIT_POLICIES[exit_policy]
        except (KeyError, TypeError) as error:
            raise ValueError("unregistered_exit_policy") from error
        # Override the old multi-session horizon only for an explicit measured
        # candidate. None preserves the retained v1 synthetic control behaviour.
        preset = replace(
            preset,
            exit_policy=policy,
            overnight=policy.next_trading_day,
            max_sessions=2 if policy.next_trading_day else 1,
        )
    return preset


FAMILY_FACTORS = MappingProxyType(
    {
        "catalyst": (
            "fda_decision",
            "clinical_trial",
            "government_award",
            "policy_beneficiary",
            "ma_status",
            "earnings",
            "commercial_contract",
            "ipo_lockup",
            "halt_event",
            "legal_regulatory",
            "commodity_crypto_exposure",
            "catalyst_confirmation",
        ),
        "gap_premarket": ("overnight_gap", "premarket_return", "premarket_activity"),
        "volume_float": ("relative_volume", "float_turnover", "float_flip_clock"),
        "squeeze_borrow": (
            "short_interest",
            "days_to_cover",
            "fails_to_deliver",
            "borrow_fee",
        ),
        "momentum_breakout": ("momentum_20", "range_breakout", "tight_range_state"),
        "options_flow_stock": (
            "option_volume_surge",
            "gamma_exposure_proxy",
            "expiry_concentration",
        ),
        "halt_reopen": ("halt_reopen_liquidity", "halt_event", "halt_pause_density"),
        "post_earnings_drift": ("earnings", "overnight_gap", "relative_volume"),
        "trend_new_highs": ("trend_state", "relative_strength"),
        "short_term_reversal": ("momentum_20", "momentum_5"),
    }
)

REQUIRED_QUALIFICATIONS = MappingProxyType(
    {
        "volume_float": ("OD6_float",),
        "squeeze_borrow": ("OD4_borrow", "OD6_float"),
        "options_flow_stock": ("OD3_option_history",),
    }
)

NATIVE_EXIT_PLANS = MappingProxyType(
    {
        "catalyst": "bracket_then_trail",
        "gap_premarket": "oco_from_open",
        "volume_float": "oto_then_trail",
        "squeeze_borrow": "oto_then_tight_trail",
        "momentum_breakout": "stop_limit_bracket_then_atr_trail",
        "options_flow_stock": "bracket_flat_before_expiry",
        "halt_reopen": "oco_60_minutes",
        "post_earnings_drift": "bracket",
        "trend_new_highs": "standalone_trailing_stop",
        "short_term_reversal": "bracket",
    }
)
