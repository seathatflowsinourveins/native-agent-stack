#!/usr/bin/env python3
"""Derive a layer winner's per-platform status from recorded evidence: one rule for every caller.

``scripts/landscape.py`` (the ceiling a declared ``platform_status`` may claim),
``scripts/component_matrix.py`` (the matrix's e2e state and flip rule) and
``tools/sota-convergence/record_verdicts.py`` (the status a re-record writes) all call
``platform_status()``, so the rule cannot drift between the recorder, the validator and the
report. The inputs are the host receipts under ``evidence/hosts/`` (via
``host_receipts.build_summary``) and the winner's own ``evidence_class`` and
``evidence_refs``; nothing here reads a lane's prose.

A *qualifying* receipt is schema-valid, bound to the winner's current pin
(``tool_versions[component_id]`` equals ``pin`` after normalization), ``native_proven``,
at stage ``install`` or ``use``, on a declared second physical machine whose
``host.os``/``host.architecture`` match the platform profile, and independently reviewed
(``host_receipts.review_state`` is ``agree``: at least one reviewer identity other than the
recorder's agrees, and no reviewer's latest verdict dissents). The latest qualifying
receipt decides: a later qualifying ``fail`` supersedes an earlier ``pass``.

``macos-arm64``: ``accepted`` needs a qualifying pass; ``conditional`` any pin-bound,
schema-valid pass that no reviewer dissents from; ``not_established`` pin-bound receipts
none of which is such a pass; otherwise ``untested``.

``linux-wsl2-x86_64``: ``accepted`` needs a qualifying pass, or a ``native_proven`` /
``measured_comparison`` winner citing at least one ``evidence/`` file registered in
``manifests/evidence.json`` (and no superseding qualifying fail); ``conditional`` covers
the same classes without such a reference, ``local_integration``, ``synthetic`` and any
pin-bound pass; otherwise ``not_established``.

Every input is self-declared by whoever recorded or reviewed it (host identity, second
machine, reviewer identity); the rule makes an unsupported claim fail loudly, it does not
authenticate the claimant. See ``docs/contributing-evidence.md``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

try:
    from . import host_receipts
except ImportError:  # running as a plain script, not a package
    import host_receipts


PLATFORMS = ("linux-wsl2-x86_64", "macos-arm64")
STATUS_RANK = {"untested": 0, "not_established": 0, "conditional": 1, "accepted": 2}
QUALIFYING_STAGES = frozenset({"install", "use"})
NATIVE_CLASSES = frozenset({"native_proven", "measured_comparison"})
CONDITIONAL_CLASSES = frozenset({"local_integration", "synthetic"})
HEX_PREFIX_MIN = 7


class PlatformStatus(NamedTuple):
    status: str
    reason: str
    receipt_refs: tuple[str, ...]


@dataclass(frozen=True)
class StatusContext:
    summary: dict
    registered_paths: frozenset


def load_context(root: Path) -> StatusContext:
    """Read the host receipts and the registered evidence paths once; pass the result to
    every ``platform_status``/``declared_status_error`` call of one run."""
    root = Path(root)
    return StatusContext(
        summary=host_receipts.build_summary(root),
        registered_paths=frozenset(host_receipts.evidence_files(root)),
    )


def normalize_pin(value) -> str | None:
    """Comparable form of a pin or recorded version: the first token before ';' or
    whitespace, lower-cased, with a leading 'v' dropped before a digit ('v1.52.0' ->
    '1.52.0'; '985ef30 with remediation' -> '985ef30'). ``None`` when nothing usable."""
    if not isinstance(value, str):
        return None
    token = re.split(r"[;\s]", value.strip(), maxsplit=1)[0].lower()
    if re.fullmatch(r"v[0-9].*", token):
        token = token[1:]
    return token or None


def pin_matches(recorded, pin) -> bool:
    """True when a receipt's recorded component version is the winner's current pin. An
    unpinned winner ('unpinned' or empty) never matches: pin it before a receipt can bind."""
    left, right = normalize_pin(recorded), normalize_pin(pin)
    if not left or not right or right == "unpinned":
        return False
    if left == right:
        return True
    hexy = re.compile(r"[0-9a-f]+")
    shorter, longer = sorted((left, right), key=len)
    return (len(shorter) >= HEX_PREFIX_MIN and hexy.fullmatch(left) is not None
            and hexy.fullmatch(right) is not None and longer.startswith(shorter))


def registered_evidence_refs(winner: dict, registered_paths) -> tuple[str, ...]:
    refs = winner.get("evidence_refs") or []
    return tuple(ref for ref in refs if isinstance(ref, str)
                 and ref.split("#", 1)[0].startswith("evidence/") and ref.split("#", 1)[0] in registered_paths)


def _platform_receipts(summary: dict, component_id, platform_id: str) -> list[dict]:
    component = (summary.get("components") or {}).get(component_id) or {}
    bucket = (component.get("platforms") or {}).get(platform_id) or {}
    return [entry for entry in bucket.get("receipts", []) or [] if isinstance(entry, dict)]


def platform_status(platform_id: str, winner: dict, context: StatusContext) -> PlatformStatus:
    """The strongest status the recorded evidence supports for ``winner`` on ``platform_id``.
    ``winner`` needs ``component_id``, ``pin``, ``evidence_class`` and ``evidence_refs``."""
    if platform_id not in PLATFORMS:
        raise ValueError(f"unknown platform {platform_id!r}")
    component_id = winner.get("component_id")
    pin = winner.get("pin")
    entries = _platform_receipts(context.summary, component_id, platform_id)
    bound = [entry for entry in entries
             if entry.get("shape_ok") and entry.get("platform_identity_ok")
             and pin_matches(entry.get("component_version"), pin)]
    qualifying = [entry for entry in bound
                  if entry.get("evidence_class") == "native_proven"
                  and entry.get("stage") in QUALIFYING_STAGES
                  and entry.get("second_physical_machine") is True
                  and entry.get("review_state") == "agree"
                  and entry.get("result") in ("pass", "fail")]
    latest = max(qualifying, key=lambda entry: (entry.get("observed_at_utc") or "", entry.get("path") or ""),
                 default=None)
    superseded_by_fail = latest is not None and latest.get("result") == "fail"
    passes = [entry for entry in bound if entry.get("result") == "pass" and entry.get("review_state") != "dissent"]
    pass_refs = tuple(sorted(entry["path"] for entry in passes))
    fail_note = f"; latest qualifying receipt {latest['path']} failed" if superseded_by_fail else ""

    if latest is not None and not superseded_by_fail:
        return PlatformStatus("accepted", "independently reviewed native_proven pass at the current pin",
                              (latest["path"],))

    if platform_id == "macos-arm64":
        if passes:
            return PlatformStatus("conditional", "pin-bound passing host receipt(s) without the full "
                                  "acceptance conditions" + fail_note, pass_refs)
        if bound:
            return PlatformStatus("not_established", f"host receipts at pin {pin!r} but none passes without "
                                  "a standing dissent" + fail_note, tuple(sorted(entry["path"] for entry in bound)))
        return PlatformStatus("untested", f"no schema-valid host receipt bound to pin {pin!r}", ())

    evidence_class = winner.get("evidence_class")
    registered = registered_evidence_refs(winner, context.registered_paths)
    if evidence_class in NATIVE_CLASSES and registered and not superseded_by_fail:
        return PlatformStatus("accepted", f"{evidence_class} winner citing registered evidence", registered)
    if evidence_class in NATIVE_CLASSES:
        reason = (f"{evidence_class} winner" + fail_note if superseded_by_fail
                  else f"{evidence_class} winner without a registered evidence/ reference")
        return PlatformStatus("conditional", reason, registered + pass_refs)
    if evidence_class in CONDITIONAL_CLASSES:
        return PlatformStatus("conditional", f"{evidence_class} winner" + fail_note, registered + pass_refs)
    if passes:
        return PlatformStatus("conditional", "pin-bound passing host receipt(s)" + fail_note, pass_refs)
    return PlatformStatus("not_established", f"{evidence_class or 'unknown'} winner with no passing host receipt",
                          registered)


def declared_status_error(platform_id: str, declared, winner: dict, context: StatusContext) -> str | None:
    """A message when ``declared`` claims more than ``platform_status`` derives, else ``None``.
    A weaker declaration is stale but conservative and allowed, so a new receipt never breaks
    CI before the row is re-recorded."""
    derived = platform_status(platform_id, winner, context)
    if STATUS_RANK.get(declared, len(STATUS_RANK)) <= STATUS_RANK[derived.status]:
        return None
    return (f"platform_status.{platform_id} declares {declared!r} but the recorded evidence supports at most "
            f"{derived.status!r} ({derived.reason}); add the host receipt described in "
            "docs/contributing-evidence.md instead of editing the status")
