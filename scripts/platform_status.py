#!/usr/bin/env python3
"""Derive a layer winner's per-platform status from recorded evidence: one rule for every caller.

``scripts/landscape.py`` (the ceiling a declared ``platform_status`` may claim),
``scripts/component_matrix.py`` (the matrix's e2e state and flip rule) and
``tools/sota-convergence/record_verdicts.py`` (the status a new-wave record writes, every
platform) call ``platform_status()``, so a Mac receipt raises the allowed ceiling and a row
reaches it on its next re-record. The inputs are the host receipts under ``evidence/hosts/`` (via
``host_receipts.build_summary``) and the winner's own ``evidence_class`` and
``evidence_refs``; nothing here reads a lane's prose.

A receipt is *bound* when it is schema-valid, its ``host.os``/``host.architecture`` match the
platform profile, and its ``tool_versions[component_id]`` equals the winner's current ``pin``
after ``normalize_pin`` (the whole string, so a multi-part pin must match in full). A
*qualifying* receipt is a bound ``native_proven`` pass at stage ``install`` or ``use``, on a
declared second physical machine, independently reviewed (``host_receipts.review_state`` is
``agree``: a reviewer identity other than the recorder's agrees and nothing dissents). A
*blocking* fail is a bound ``native_proven`` fail at ``install`` or ``use`` that is the latest
receipt for its host and stage, whatever its review; it withholds ``accepted`` until that host
records a later pass for that stage.

``macos-arm64``: ``accepted`` needs a qualifying pass and no blocking fail; ``conditional`` a
bound pass that is not ``synthetic``, comes from a declared second physical machine and has
no standing dissent; ``not_established`` bound receipts none of which is such a pass;
otherwise ``untested``.

``linux-wsl2-x86_64``: ``accepted`` needs a qualifying pass, or a ``native_proven`` /
``measured_comparison`` winner citing at least one ``evidence/`` file registered in
``manifests/evidence.json`` (not one the layer-verdict pipeline sealed under
``evidence/artifacts/layer-verdicts-<run-id>/``: packets, lane returns and adjudications are lane
inputs or opinions, not execution receipts), and in both cases no blocking fail; ``conditional`` covers the
same classes otherwise, ``local_integration``, ``synthetic`` and any bound non-``synthetic``
pass without a standing dissent; otherwise ``not_established``.

Every input is self-declared by whoever recorded or reviewed it (host identity, second
machine, reviewer identity); the rule makes an unsupported claim fail loudly, it does not
authenticate the claimant. See ``docs/contributing-evidence.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

try:
    from . import host_receipts
except ImportError:  # running as a plain script, not a package
    import host_receipts


PLATFORMS = ("linux-wsl2-x86_64", "macos-arm64")
STATUS_RANK = {"untested": 0, "not_established": 0, "conditional": 1, "accepted": 2}
# Stages whose latest native_proven fail blocks acceptance.
QUALIFYING_STAGES = frozenset({"install", "use"})
# Stages whose independently reviewed pass can make a winner accepted: a functional use only. An install pass (a
# version call proves the binary resolves, not that the component does its layer's job) supports conditional at
# most (docs/decisions/2026-09-24-accepted-needs-use-stage.md).
ACCEPTING_STAGES = frozenset({"use"})
NATIVE_CLASSES = frozenset({"native_proven", "measured_comparison"})
CONDITIONAL_CLASSES = frozenset({"local_integration", "synthetic"})


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


# One definition, shared with the recorder's --component-version check.
normalize_pin = host_receipts.normalize_pin
pin_matches = host_receipts.pin_matches


# What the layer-verdict pipeline itself seals (tools/sota-convergence/record_verdicts.py).
LAYER_VERDICT_ARTIFACTS = "evidence/artifacts/layer-verdicts-"


def registered_evidence_refs(winner: dict, registered_paths) -> tuple[str, ...]:
    """The winner's refs (a ``#fragment`` ignored) naming a registered ``evidence/`` file that is
    not a layer-verdict artifact."""
    refs = winner.get("evidence_refs") or []
    paths = [(ref, ref.split("#", 1)[0]) for ref in refs if isinstance(ref, str)]
    return tuple(ref for ref, path in paths if path.startswith("evidence/")
                 and not path.startswith(LAYER_VERDICT_ARTIFACTS) and path in registered_paths)


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
    native_stage = [entry for entry in bound
                    if entry.get("evidence_class") == "native_proven" and entry.get("stage") in QUALIFYING_STAGES]
    latest_per_host_stage: dict[tuple, tuple] = {}
    # Only pass and fail decide; a later partial or not_runnable receipt neither clears a fail nor
    # withdraws a pass.
    for entry in (item for item in native_stage if item.get("result") in ("pass", "fail")):
        key = (entry.get("host_id"), entry.get("stage"))
        # On an equal timestamp a fail sorts after a pass, so the tie blocks.
        rank = (entry.get("observed_at_utc") or "", entry.get("result") == "fail", entry.get("path") or "")
        current = latest_per_host_stage.get(key)
        if current is None or rank > current[0]:
            latest_per_host_stage[key] = (rank, entry)
    blocking = sorted(entry["path"] for _rank, entry in latest_per_host_stage.values()
                      if entry.get("result") == "fail")
    reviewed = [entry for entry in native_stage
                if entry.get("result") == "pass" and entry.get("second_physical_machine") is True
                and entry.get("review_state") == "agree"]
    qualifying = sorted(entry["path"] for entry in reviewed if entry.get("stage") in ACCEPTING_STAGES)
    install_only = sorted(entry["path"] for entry in reviewed if entry.get("stage") not in ACCEPTING_STAGES)
    passes = [entry for entry in bound if entry.get("result") == "pass"
              and entry.get("review_state") != "dissent" and entry.get("evidence_class") != "synthetic"]
    if platform_id == "macos-arm64":
        passes = [entry for entry in passes if entry.get("second_physical_machine") is True]
    pass_refs = tuple(sorted(entry["path"] for entry in passes))
    fail_note = f"; latest native_proven receipt failed: {', '.join(blocking)}" if blocking else ""

    if qualifying and not blocking:
        return PlatformStatus("accepted", "independently reviewed native_proven pass at the current pin",
                              tuple(qualifying))

    if install_only and not qualifying and not blocking:
        # A reviewed install pass alone supports conditional on either platform, never accepted.
        return PlatformStatus("conditional", "independently reviewed install-stage pass; accepted needs a reviewed "
                              "use-stage pass", tuple(install_only))

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
    if evidence_class in NATIVE_CLASSES and registered and not blocking:
        return PlatformStatus("accepted", f"{evidence_class} winner citing registered evidence", registered)
    if evidence_class in NATIVE_CLASSES:
        reason = (f"{evidence_class} winner" + fail_note if blocking
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
