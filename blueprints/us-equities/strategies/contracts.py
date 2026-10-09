"""Dated, immutable inputs; no acquisition, ranking, credentials or broker clients.

Nautilus rc5's Python custom-data wrapper reads ``ts_event`` and ``ts_init``.
The latter is availability, so the engine delivers a snapshot only when it is
known. Source: nautilus_trader@1b0a49d2, crates/model/src/data/custom.rs.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
DEVELOPMENT_CUTOFF_NS = 1791936000000000000  # 2026-10-14T00:00:00Z, exclusive


def decimal(value: str | int | Decimal) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise TypeError("exact_decimal_required")
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("exact_decimal_required") from error
    if not result.is_finite() or abs(result) > Decimal("1e18"):
        raise ValueError("finite_bounded_decimal_required")
    return result


def nanos(value: int) -> int:
    if type(value) is not int or not 0 <= value < 2**63:
        raise ValueError("nonnegative_integer_timestamp_required")
    return value


def digest(payload) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class FactorSnapshot:
    """One symbol's explicit C_t membership and originally available factors.

    Values use registered coordinates documented in registry.json; unavailable
    fields stay missing. ``source_sha256`` binds the supplying artifact, not a
    claim that its historical provenance has passed Layer 1.5. A synthetic
    snapshot is usable only by an explicitly synthetic strategy specification.
    """

    instrument_id: str
    cohort_sha256: str
    source_sha256: str
    ts_event: int
    ts_init: int
    valid_until_ns: int
    values: tuple[tuple[str, str], ...]
    evidence_class: str = "synthetic"
    cohort_member: bool = True
    halted: bool = False
    expiry_ns: int | None = None

    def __post_init__(self):
        for value in (self.cohort_sha256, self.source_sha256):
            if not SHA256.fullmatch(value):
                raise ValueError("source_and_cohort_hashes_required")
        if not isinstance(self.instrument_id, str) or "." not in self.instrument_id:
            raise ValueError("instrument_id_required")
        for value in (self.ts_event, self.ts_init, self.valid_until_ns):
            nanos(value)
        if not self.ts_event <= self.ts_init <= self.valid_until_ns:
            raise ValueError("snapshot_availability_order_invalid")
        if self.evidence_class not in {"synthetic", "development"}:
            raise ValueError("development_or_synthetic_only")
        if (
            self.evidence_class == "development"
            and self.ts_init >= DEVELOPMENT_CUTOFF_NS
        ):
            raise ValueError("development_cutoff_exceeded")
        if type(self.cohort_member) is not bool or type(self.halted) is not bool:
            raise ValueError("explicit_boolean_state_required")
        if type(self.values) is not tuple or any(
            type(pair) is not tuple or len(pair) != 2 for pair in self.values
        ):
            raise ValueError("immutable_factor_pairs_required")
        keys = [pair[0] for pair in self.values]
        if any(
            not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", key)
            for key in keys
        ):
            raise ValueError("factor_key_invalid")
        if len(keys) != len(set(keys)) or keys != sorted(keys):
            raise ValueError("unique_sorted_factors_required")
        for _, value in self.values:
            if not isinstance(value, str):
                raise TypeError("serialized_decimal_string_required")
            decimal(value)
        if self.expiry_ns is not None:
            nanos(self.expiry_ns)

    def value(self, key: str) -> Decimal | None:
        raw = dict(self.values).get(key)
        return None if raw is None else decimal(raw)

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))

    def as_dict(self) -> dict:
        return {
            "instrument_id": self.instrument_id,
            "cohort_sha256": self.cohort_sha256,
            "source_sha256": self.source_sha256,
            "ts_event": self.ts_event,
            "ts_init": self.ts_init,
            "valid_until_ns": self.valid_until_ns,
            "values": dict(self.values),
            "evidence_class": self.evidence_class,
            "cohort_member": self.cohort_member,
            "halted": self.halted,
            "expiry_ns": self.expiry_ns,
        }

    @classmethod
    def from_json(cls, data: dict) -> FactorSnapshot:
        data = dict(data)
        data["values"] = tuple(sorted(data["values"].items()))
        return cls(**data)


@dataclass(frozen=True)
class StrategySpec:
    """Frozen local budgets; native risk and the paper governor stay independent.

    This specification deliberately offers no forward-data mode. Development
    inputs require external release/horizon qualification as well as this date
    fence. Synthetic fixtures prove mechanics only.
    """

    instrument_id: str
    cohort_sha256: str
    preset: str = "conservative-v1"
    evidence_class: str = "synthetic"
    execution_profile: str = "code-managed-limit-v1"
    position_cap_usd: str = "1000"
    loss_cap_usd: str = "10"
    cash_cap_usd: str = "1000"
    max_quantity: int = 100
    quote_max_age_ns: int = 3_000_000_000
    future_tolerance_ns: int = 250_000_000
    limit_collar_bps: str = "20"
    entry_timeout_ns: int = 10_000_000_000
    exit_timeout_ns: int = 10_000_000_000
    max_exit_orders: int = 20
    entry_deadline_ns: int | None = None
    exit_deadline_ns: int | None = None
    catalyst_kind: str = "concrete"
    qualified_data: tuple[str, ...] = ()
    instance_id: str = "default"

    def __post_init__(self):
        if not isinstance(self.instance_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_]{1,64}", self.instance_id
        ):
            raise ValueError("stable_instance_id_required")
        if not SHA256.fullmatch(self.cohort_sha256):
            raise ValueError("cohort_hash_required")
        if self.evidence_class not in {"synthetic", "development"}:
            raise ValueError("development_or_synthetic_only")
        if self.execution_profile not in {"code-managed-limit-v1", "native-target-v1"}:
            raise ValueError("unregistered_execution_profile")
        if self.catalyst_kind not in {"concrete", "narrative"}:
            raise ValueError("catalyst_kind_invalid")
        for field in (self.position_cap_usd, self.loss_cap_usd, self.cash_cap_usd):
            if decimal(field) <= 0:
                raise ValueError("positive_frozen_cap_required")
        if not 0 < decimal(self.limit_collar_bps) <= 100:
            raise ValueError("limit_collar_invalid")
        for value in (self.max_quantity, self.max_exit_orders):
            if type(value) is not int or not 1 <= value <= 100:
                raise ValueError("bounded_integer_cap_required")
        if type(self.qualified_data) is not tuple or any(
            not isinstance(x, str) for x in self.qualified_data
        ):
            raise ValueError("immutable_data_qualification_required")
        for value in (
            self.quote_max_age_ns,
            self.future_tolerance_ns,
            self.entry_timeout_ns,
            self.exit_timeout_ns,
        ):
            nanos(value)
        if (
            not 0 < self.quote_max_age_ns <= 3_000_000_000
            or self.future_tolerance_ns > 250_000_000
        ):
            raise ValueError("quote_freshness_may_not_be_relaxed")
        if (
            not 0 < self.entry_timeout_ns <= 60_000_000_000
            or not 0 < self.exit_timeout_ns <= 60_000_000_000
        ):
            raise ValueError("bounded_order_timeout_required")
        for value in (self.entry_deadline_ns, self.exit_deadline_ns):
            if value is not None:
                nanos(value)
        if self.evidence_class == "development":
            if (
                "released_development" not in self.qualified_data
                or "horizon_qualified" not in self.qualified_data
            ):
                raise ValueError(
                    "development_release_and_horizon_qualification_required"
                )
            if (
                self.exit_deadline_ns is None
                or self.exit_deadline_ns >= DEVELOPMENT_CUTOFF_NS
            ):
                raise ValueError("development_exit_deadline_required")
