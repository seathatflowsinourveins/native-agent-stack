"""Small synthetic contract checks, not a strategy, feature builder or backtester."""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
import re

_FIELDS = {
    "security_id", "source_hash", "feature_end_ns", "feature_available_ns",
    "universe_available_ns", "catalyst_available_ns", "is_listed",
    "is_common_share", "identity_proven", "catalyst_original_8k_item101",
    "catalyst_age_sessions", "full_session_minutes", "complete_prior_sessions",
    "basis_ids", "prior_close", "median_dollar_volume", "price_return",
    "relative_volume", "quote_age_ms", "spread_bps",
}
_SHA = re.compile(r"[a-f0-9]{64}\Z")

def integer(value, *, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError("expected exact integer in permitted range")
    return value

def decimal(value):
    if not isinstance(value, str):
        raise ValueError("decimal values must be source-preserving text")
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("invalid decimal") from error
    if not result.is_finite():
        raise ValueError("non-finite decimal")
    return result

def utc_ns(value):
    """Canonical UTC RFC3339 subset; no floats or fractional rounding."""
    if not isinstance(value, str):
        raise ValueError("timestamp must be text")
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z", value)
    if not match:
        raise ValueError("canonical UTC timestamp with at most9fractional digits required")
    date = datetime.strptime(match[1], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    delta = date - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return integer((delta.days * 86400 + delta.seconds) * 10**9
                   + int((match[2] or "").ljust(9, "0")), minimum=1)

def candidate(row, decision_ns, lane, protocol):
    """Validate a supplied synthetic feature row and return ALL rejection reasons.

    Upstream feature construction, actual session schedule, event deduplication and
    ranking are deliberately outside this helper's accepted implementation scope.
    No outcome fields can be passed in this strict feature shape.
    """
    if set(row) != _FIELDS or lane not in protocol["lanes"]:
        raise ValueError("wrong feature schema or lane")
    if not isinstance(row["security_id"], str) or not row["security_id"]:
        raise ValueError("security identity required")
    if not isinstance(row["source_hash"], str) or not _SHA.fullmatch(row["source_hash"]):
        raise ValueError("source hash required")
    cutoff = integer(decision_ns, minimum=1)
    end = integer(row["feature_end_ns"], minimum=1)
    available = integer(row["feature_available_ns"], minimum=1)
    source_times = [available, integer(row["universe_available_ns"], minimum=1),
                    integer(row["catalyst_available_ns"], minimum=1)]
    if available < end:
        raise ValueError("feature cannot be available before its interval completes")
    reasons = []
    if end > cutoff: reasons.append("incomplete_feature")
    if max(source_times) > cutoff: reasons.append("unavailable_at_decision")
    if any(row[x] is not True for x in ("is_listed", "is_common_share", "identity_proven")):
        reasons.append("unknown_or_ineligible_universe")
    if row["catalyst_original_8k_item101"] is not True:
        reasons.append("unknown_or_ineligible_catalyst")
    spec = protocol["lanes"][lane]
    age = integer(row["catalyst_age_sessions"])
    if not spec["catalyst_age_sessions_min"] <= age <= spec["catalyst_age_sessions_max"]:
        reasons.append("event_age")
    if integer(row["full_session_minutes"]) != 390:
        reasons.append("non_full_session")
    eligibility = protocol["eligibility"]
    if integer(row["complete_prior_sessions"]) < eligibility["required_complete_prior_sessions"]:
        reasons.append("incomplete_lookback")
    bases = row["basis_ids"]
    if not isinstance(bases, list) or len(bases) != 3 or any(not isinstance(x, str) or not x for x in bases):
        raise ValueError("three explicit price/volume/window basis IDs required")
    if len(set(bases)) != 1: reasons.append("split_basis_mismatch")
    price = decimal(row["prior_close"])
    if not decimal(eligibility["prior_close_min_usd"]) <= price <= decimal(eligibility["prior_close_max_usd"]):
        reasons.append("price_range")
    if decimal(row["median_dollar_volume"]) < decimal(eligibility["median_dollar_volume_min_usd"]):
        reasons.append("liquidity_threshold")
    if decimal(row["price_return"]) < decimal(spec["min_price_return"]):
        reasons.append("price_threshold")
    if decimal(row["relative_volume"]) < decimal(spec["min_relative_volume"]):
        reasons.append("volume_threshold")
    quote_age = integer(row["quote_age_ms"])
    spread = decimal(row["spread_bps"])
    if spread < 0: raise ValueError("negative spread")
    if lane == "intraday" and (quote_age > eligibility["max_quote_age_ms"] or
                              spread > decimal(eligibility["max_full_spread_bps"])):
        reasons.append("quote_gate")
    return reasons

def labels(prior_close, day_open, day_high, day_close, close_5d, entry, exit_price,
           *, basis_consistent):
    """Ex-post arithmetic only. Missing/action-ambiguous inputs must stay unscored."""
    if basis_consistent is not True:
        raise ValueError("unknown or inconsistent corporate-action basis")
    prior, opening, high, close, close5, entry_price, exit_value = map(
        decimal, (prior_close, day_open, day_high, day_close, close_5d, entry, exit_price))
    if min(prior, opening, high, close, close5, entry_price, exit_value) <= 0:
        raise ValueError("positive supported prices required")
    if high < max(opening, close):
        raise ValueError("invalid daily high")
    ratios = {
        "close_to_close_1d": (close, prior),
        "open_to_high_1d": (high, opening),
        "prior_close_to_high_1d": (high, prior),
        "close_to_close_5d": (close5, close),
        "entry_to_exit": (exit_value, entry_price),
    }
    # Display is rounded, but the decision boundary uses exact source rationals.
    with localcontext() as context:
        context.prec = 28
        values = {key: str(numerator / denominator - 1)
                  for key, (numerator, denominator) in ratios.items()}
    return {**values, "gte_200pct": {
        key: Fraction(numerator) >= 3 * Fraction(denominator)
        for key, (numerator, denominator) in ratios.items()}}

def entry_gate(decision_ns, quote_ns, latency_seconds):
    return integer(quote_ns, minimum=1) >= (
        integer(decision_ns, minimum=1) + integer(latency_seconds, minimum=1) * 10**9)

def assert_purged(training, first_evaluation_ns, evaluation_event_groups):
    cutoff = integer(first_evaluation_ns, minimum=1)
    for row in training:
        start = integer(row["decision_ns"], minimum=1)
        end = integer(row["label_end_ns"], minimum=1)
        if not start <= end < cutoff:
            raise ValueError("training label interval overlaps evaluation")
        if not row["event_group"] or row["event_group"] in evaluation_event_groups:
            raise ValueError("missing or shared issuer-event group")

def reserved_access(case_ids, inspection_registry):
    """Registry completeness is a supplied prerequisite, not inferred here."""
    if not case_ids or len(set(case_ids)) != len(case_ids):
        raise ValueError("nonempty unique exact case IDs required")
    for case in case_ids:
        record = inspection_registry.get(case, {})
        digest = record.get("registry_hash")
        if record.get("inspected") is not False or not isinstance(digest, str) or not _SHA.fullmatch(digest):
            raise ValueError("missing/inspected reserved case registry")
