#!/usr/bin/env python3
"""Join the already-recorded landscape verdicts, lifecycle decisions, host
receipts and gap crosswalk into one per-component independent-review and
E2E-status view.

This never selects a winner, records a receipt or runs a lane; it only joins
what ``catalogs/landscape/{foundation,us-equities}.json``,
``catalogs/foundation/decisions.json``, ``scripts/host_receipts.py`` receipts
and ``catalogs/landscape/gap-crosswalk-92bb279.json`` (optional) already say,
and writes the result deterministically to
``catalogs/landscape/component-evidence-matrix.json`` and
``docs/component-evidence-matrix.md``.

Each row also carries the convergence-by-layer metric (``rows[].convergence``,
summarized in ``summary.convergence``), computed only from committed files: the
row's verdict and ``checked_at``, the completed sweeps of
``catalogs/saturation/ledger.json``, the newest
``catalogs/sota-convergence/manifest-YYYYMMDD.json``, ``manifests/stack.json``,
``tools/sota-convergence/receipt-component-aliases.json`` and the row's own
linux-wsl2-x86_64 winner entries. ``CONVERGENCE_DEFINITIONS`` is its single
source of definitions.

Modes: ``--check`` (default) recomputes both outputs in memory and exits 1 on
any difference from the checked-in files, or on a flip-rule violation (a
declared ``platform_status`` above what ``scripts/platform_status.py`` derives,
for the platforms in ``landscape.ENFORCED_PLATFORMS``); ``--write`` recomputes
and writes them.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re

try:
    from . import host_receipts
    from . import platform_status as platform_evidence
    from . import saturation_ledger
    from .catalog_decisions import InvalidDecisionIndex, load, safe_file, unique_json
    from .landscape import ENFORCED_PLATFORMS, PLATFORM_KEYS
    from .validate import PRIVATE_CONTENT
except ImportError:  # running as a plain script, not a package
    import host_receipts
    import platform_status as platform_evidence
    import saturation_ledger
    from catalog_decisions import InvalidDecisionIndex, load, safe_file, unique_json
    from landscape import ENFORCED_PLATFORMS, PLATFORM_KEYS
    from validate import PRIVATE_CONTENT


# The date the scope and the JSON schema below were last checked (the convergence-by-layer fields, 2026-09-27).
# It is never a build date: the generator reads no clock, and the page header derives its newest input date.
CHECKED_AT = "2026-09-27"
SCOPE = (
    "Per-component independent-review status and per-platform E2E state, joined from "
    "catalogs/landscape/{foundation,us-equities}.json winners/alternatives, "
    "catalogs/foundation/decisions.json lifecycle stage_refs, scripts/host_receipts.py receipts "
    "and the gap crosswalk (open executable_now gaps per layer, when present), with each layer's "
    "convergence by layer from the saturation ledger and the newest sweep manifest. It never selects "
    "a winner or records a receipt; it is a read-only join of evidence recorded elsewhere."
)
# The same two catalogs a receipt's layer_refs may name.
LANDSCAPE_FILES = host_receipts.LANDSCAPE_CATALOGS
DECISIONS_FILE = "catalogs/foundation/decisions.json"
GAP_CROSSWALK_FILE = "catalogs/landscape/gap-crosswalk-92bb279.json"
STACK_FILE = "manifests/stack.json"
ADJUDICATION_TEMPLATE = "evidence/artifacts/layer-verdicts-20260922/adjudication/{catalog}-{layer_id}-20260922.json"

OUTPUT_JSON = "catalogs/landscape/component-evidence-matrix.json"
OUTPUT_MD = "docs/component-evidence-matrix.md"

INDEPENDENT_REVIEW_STATES = {
    "dual_lane_same_winner", "dual_lane_adjudicated", "pending_lanes", "single_lane",
}

# Convergence by layer: the metric frozen on 2026-09-27, before any of its numbers were computed. Integers per
# layer, three independent factors (only pin_current and host_e2e can be unknown), no blended score and no sum
# across factors.
CONVERGENCE_FROZEN_AT = "2026-09-27"
SATURATION_LEDGER_FILE = saturation_ledger.LEDGER
SWEEP_MANIFEST_DIR = "catalogs/sota-convergence"
# Only the sweep manifests themselves; the directory also holds layer-verdicts-*, sdk-runtime-coverage-* and
# layer-verdict-waves.json.
SWEEP_MANIFEST_NAME = re.compile(r"manifest-\d{8}\.json")
RECEIPT_ALIASES_FILE = host_receipts.RECEIPT_ALIASES_RELATIVE_PATH
CONVERGENCE_PLATFORM = "linux-wsl2-x86_64"
# catalogs/saturation/README.md: a stopped sweep neither counts nor resets (saturation_ledger.STATUSES).
COMPLETED_SWEEP = "completed"
CONVERGENCE_LAYER_STATES = ("confirmed_current", "no_selection", "pending_lanes", "recorded_reopened")
CONVERGENCE_FACTORS = ("verdict_winner", "pin_current", "host_e2e")
CONVERGENCE_FACTOR_VALUES = ("true", "false", "unknown")
HOST_E2E_PASSING = ("accepted", "host_verified")
# tools/sota-convergence/build_manifest.py SELECTED_TRADING_DECISIONS: the decisions a sweep manifest's trading
# entry carries; only "default" is adopted.
TRADING_DECISIONS = ("default", "conditional")
IN_USE_TRADING_DECISION = "default"
# Strongest first: the winner a row *is* (for host_e2e) comes from the first method that matches.
WINNER_MATCH_METHODS = ("id", "alias", "repository")
INVOKE_REASON = "no post-fix invoke receipt yet"
CONVERGENCE_DEFINITIONS = (
    ("layer_state",
     "Exactly one of: pending_lanes (the verdict ledger row's verdict_status is pending_lanes); no_selection "
     "(verdict_status no_selection, or a recorded verdict with no winners; scripts/landscape.py allows no other "
     "status); recorded_reopened (a recorded verdict, and a completed sweep in " + SATURATION_LEDGER_FILE
     + " that covers the layer is dated after the row's checked_at); confirmed_current (a recorded verdict that "
     "no covering completed sweep is dated after). A sweep on the verdict's own date is not after it, a stopped "
     "sweep never counts, and a row without an ISO checked_at counts every covering completed sweep as after it."),
    ("in_use",
     "The layer's rows in the newest committed sweep manifest (" + SWEEP_MANIFEST_DIR + "/manifest-YYYYMMDD.json "
     "with the latest checked_at; foundation[].components for a foundation layer, trading[].entries for a "
     "us-equities layer) that resolve to an adopted component, the headline denominator. A foundation row "
     "resolves to manifests/stack.json components by its id, else by a " + RECEIPT_ALIASES_FILE + " alias, else "
     "by its repository (scripts/host_receipts.py normalize_repository), with no uniqueness condition: "
     "adopted_as_candidates lists the stack components matched that way, and adopted_as names the single one or "
     "is null when several share the alias or repository. A us-equities entry is in use when its decision is "
     "default; a conditional entry is not in use. The unit is the layer-component row: every resolving row "
     "counts, so a component in several layers counts once per layer and two rows of one layer that resolve to "
     "the same stack component both count; per-catalog and overall sums count these rows, not distinct "
     "components."),
    ("verdict_winner",
     "true when the row is a winner of the layer's recorded verdict by component id, by an alias in either "
     "direction, or by the same repository (scripts/host_receipts.py normalize_repository); false otherwise, "
     "including in a pending_lanes layer, which has no recorded verdict yet."),
    ("pin_current",
     "true when the newest sweep manifest row has pin_comparison compared and pin_behind_upstream false; false "
     "when it is compared and behind; unknown when it was not compared."),
    ("host_e2e",
     "true when this layer's own matrix winner entry for the component (the winner the row matches by the first "
     "of id, alias and repository) has e2e_state accepted or host_verified on " + CONVERGENCE_PLATFORM + "; false "
     "for any other e2e_state; unknown when the layer's matrix row has no winner entry for it."),
    ("converged",
     "layer_state is confirmed_current and verdict_winner, pin_current and host_e2e are all true; an unknown "
     "factor is not converged and stays counted as unknown. The summary gives converged / in_use per catalog and "
     "overall as integers, with a share (four decimal places) only where in_use > 0."),
    ("all_rows", "Every row of the layer in the newest sweep manifest, in use or not."),
    ("recorded_winner_rows",
     "The layer's manifest rows that match a winner of its recorded verdict, whether or not they are in use and "
     "whether or not a later sweep reopened the verdict. With all_rows it is the comparability column, not a "
     "score."),
    ("manifest_layer_found",
     "true when the newest sweep manifest has the layer in its catalog's section; false when it does not, or no "
     "sweep manifest is committed, and then all_rows is 0."),
    ("winners_without_manifest_row",
     "The winners of the layer's recorded verdict that no row of the layer in the newest sweep manifest matches "
     "(the verdict_winner match), listed and never counted. Row counts and winner counts differ because one "
     "winner can match several rows; winner_rows[].winner_ids gives the exact per-row mapping."),
    ("manifest_layers_without_matrix_row",
     "Summary list of the newest sweep manifest's layers, in either section, that have no row in this matrix; "
     "listed, never counted."),
    ("unresolved",
     "Manifest rows that could not be resolved (a row without a component id, a foundation row with no "
     "manifests/stack.json id, alias or repository match, or a trading entry without a default or conditional "
     "decision), counted and listed with the reason, never dropped."),
    ("invoke",
     "null until a post-fix invoke receipt exists; every null carries the reason '" + INVOKE_REASON + "'."),
)


# --------------------------------------------------------------------------- loading


def load_optional(root: Path, relative: str):
    """Return the parsed JSON document at ``relative``, or ``None`` if absent/unreadable."""
    try:
        path = safe_file(root, relative)
    except InvalidDecisionIndex:
        return None
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
    except (OSError, UnicodeError, ValueError):
        return None


def decisions_by_component(decisions_doc: dict | None) -> dict[str, list[dict]]:
    result: dict[str, set[tuple[str, str]]] = {}
    for decision in (decisions_doc or {}).get("decisions", []) or []:
        lifecycle = decision.get("lifecycle") if isinstance(decision, dict) else None
        for ref in (lifecycle or {}).get("stage_refs", []) or []:
            if not isinstance(ref, dict):
                continue
            component_id = ref.get("component_id")
            stage = ref.get("stage")
            status = ref.get("status")
            if not isinstance(component_id, str) or not isinstance(stage, str) or not isinstance(status, str):
                continue
            result.setdefault(component_id, set()).add((stage, status))
    return {
        component_id: [{"stage": stage, "status": status} for stage, status in sorted(pairs)]
        for component_id, pairs in result.items()
    }


def gap_counts_by_layer(gap_crosswalk_doc: dict | None) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for layer in (gap_crosswalk_doc or {}).get("layers", []) or []:
        if not isinstance(layer, dict):
            continue
        catalog = layer.get("catalog")
        layer_id = layer.get("layer_id")
        if not isinstance(catalog, str) or not isinstance(layer_id, str):
            continue
        open_executable_now = sum(
            1 for gap in layer.get("gaps", []) or []
            if isinstance(gap, dict) and gap.get("status") == "open" and gap.get("category") == "executable_now"
        )
        counts[(catalog, layer_id)] = open_executable_now
    return counts


def open_gap_counts_by_layer(gap_crosswalk_doc: dict | None) -> dict[tuple[str, str], int]:
    """Open gaps of any category (the crosswalk's status "open"), so a layer whose only open gap
    waits on a login, hardware or a user decision is not shown as having none."""
    counts: dict[tuple[str, str], int] = {}
    for layer in (gap_crosswalk_doc or {}).get("layers", []) or []:
        if isinstance(layer, dict) and isinstance(layer.get("catalog"), str) and isinstance(layer.get("layer_id"), str):
            counts[(layer["catalog"], layer["layer_id"])] = sum(
                1 for gap in layer.get("gaps", []) or [] if isinstance(gap, dict) and gap.get("status") == "open")
    return counts


def repository_to_component_id(stack_doc: dict | None) -> dict[str, str]:
    """Normalized repository (``host_receipts.normalize_repository``) -> the first
    ``manifests/stack.json`` id with that repository."""
    mapping: dict[str, str] = {}
    for component in (stack_doc or {}).get("components", []) or []:
        if not isinstance(component, dict):
            continue
        repository = host_receipts.normalize_repository(component.get("repository"))
        component_id = component.get("id")
        if repository is not None and isinstance(component_id, str):
            mapping.setdefault(repository, component_id)
    return mapping


def alias_ids_by_winner(stack_doc: dict | None, landscape_docs) -> dict[str, tuple[str, ...]]:
    """Winner component_id -> the ``manifests/stack.json`` ids that are aliases of it
    (``host_receipts.stack_aliases_of_winners``: same normalized repository, not itself a winner
    id), from the landscape documents this matrix joins."""
    winners = [winner for document in landscape_docs for layer in (document or {}).get("layers", []) or []
               if isinstance(layer, dict) for winner in layer.get("winners", []) or [] if isinstance(winner, dict)]
    components = [component for component in (stack_doc or {}).get("components", []) or []
                  if isinstance(component, dict)]
    by_winner: dict[str, set[str]] = {}
    for stack_id, winner_ids in host_receipts.stack_aliases_of_winners(components, winners).items():
        for winner_id in winner_ids:
            by_winner.setdefault(winner_id, set()).add(stack_id)
    return {winner_id: tuple(sorted(ids)) for winner_id, ids in sorted(by_winner.items())}


# ---------------------------------------------------------------------- classification


def classify_independent_review(layer: dict) -> str:
    if layer.get("verdict_status") == "pending_lanes":
        return "pending_lanes"
    agreement = (layer.get("lanes") or {}).get("agreement")
    if agreement == "same_winner":
        return "dual_lane_same_winner"
    if agreement == "disagree":
        return "dual_lane_adjudicated"
    return "single_lane"


def find_adjudication_ref(root: Path, catalog: str, layer_id: str, layer: dict) -> str | None:
    candidate = ADJUDICATION_TEMPLATE.format(catalog=catalog, layer_id=layer_id)
    if (root / candidate).is_file():
        return candidate
    for gap in layer.get("open_gaps", []) or []:
        if isinstance(gap, str) and candidate in gap:
            return candidate
    return None


# --------------------------------------------------------------------- receipts join


def platform_receipt_info(receipts_summary: dict, component_id: str, platform_key: str) -> dict:
    component_bucket = receipts_summary.get("components", {}).get(component_id, {})
    platform_bucket = component_bucket.get("platforms", {}).get(platform_key)
    if not platform_bucket:
        return {"pass": 0, "fail": 0, "independently_reviewed_pass": 0, "independently_reviewed_fail": 0,
                "dissented": 0, "latest": None}
    stages = platform_bucket.get("stages", {}) or {}
    total_pass = sum(counts.get("pass", 0) for counts in stages.values() if isinstance(counts, dict))
    total_fail = sum(counts.get("fail", 0) for counts in stages.values() if isinstance(counts, dict))
    return {
        "pass": total_pass,
        "fail": total_fail,
        "independently_reviewed_pass": platform_bucket.get("independently_reviewed_passes", 0),
        "independently_reviewed_fail": platform_bucket.get("independently_reviewed_fails", 0),
        "dissented": platform_bucket.get("dissented", 0),
        "latest": platform_bucket.get("latest_observed_at_utc"),
    }


def platform_qualified_models(receipts_summary: dict, component_id: str, platform_key: str) -> list[dict]:
    """Local model weights this component's (a runtime's) receipts on ``platform_key``
    declared qualified (``scripts/host_receipts.py record --qualified-model``), each with
    the recording receipt's host and path attached. Informational only: never read by the
    platform-status flip rule, and it never marks anything accepted on its own."""
    component_bucket = receipts_summary.get("components", {}).get(component_id, {})
    platform_bucket = component_bucket.get("platforms", {}).get(platform_key) or {}
    out = []
    for entry in platform_bucket.get("receipts", []) or []:
        if not isinstance(entry, dict):
            continue
        for qm in entry.get("qualified_models") or []:
            out.append({
                "model_id": qm.get("model_id"), "revision": qm.get("revision"), "runtime": qm.get("runtime"),
                "runtime_version": qm.get("runtime_version"), "bars": qm.get("bars"), "result": qm.get("result"),
                "host_id": entry.get("host_id"), "receipt_path": entry.get("path"),
            })
    out.sort(key=lambda qm: (qm.get("model_id") or "", qm.get("host_id") or "", qm.get("receipt_path") or ""))
    return out


def platform_alias_receipts(receipts_summary: dict, winner: dict, alias_ids, platform_key: str) -> list[dict]:
    """Receipts on ``platform_key`` recorded under a ``manifests/stack.json`` alias of ``winner``
    (``alias_ids``). Informational only: ``scripts/platform_status.py`` joins receipts by the
    winner's own component_id, so these never reach the counts, the derived status, the flip
    rule or e2e_state; they are listed so evidence recorded under the wrong id stays visible."""
    component_id, pin = winner.get("component_id"), winner.get("pin")
    out = []
    for alias_id in alias_ids:
        component_bucket = receipts_summary.get("components", {}).get(alias_id, {})
        platform_bucket = component_bucket.get("platforms", {}).get(platform_key) or {}
        for entry in platform_bucket.get("receipts", []) or []:
            if not isinstance(entry, dict):
                continue
            version = entry.get("component_version")
            version_matches = host_receipts.pin_matches(version, pin)
            out.append({
                "path": entry.get("path"),
                "host_id": entry.get("host_id"),
                "observed_at_utc": entry.get("observed_at_utc"),
                "recorded_component_id": alias_id,
                "recorded_version": version,
                "evidence_class": entry.get("evidence_class"),
                "stage": entry.get("stage"),
                "result": entry.get("result"),
                "binds": False,
                "version_matches_pin": version_matches,
                "reason": (f"recorded under manifests/stack.json id {alias_id!r}, an alias of winner "
                           f"{component_id!r}; receipts bind by the winner's own component_id"
                           + ("" if version_matches else f", and version {version!r} is not the winner pin in full")),
            })
    out.sort(key=lambda item: (item.get("path") or "", item.get("recorded_component_id") or ""))
    return out


def build_winner(winner: dict, decisions: dict[str, list[dict]], receipts_summary: dict,
                 status_context: platform_evidence.StatusContext, alias_ids: tuple[str, ...] = (), layer=None):
    """Per-platform catalog status, the status the evidence derives (scripts/platform_status.py),
    receipt counts and e2e_state. ``host_verified`` means the derived status is ``accepted``
    on the strength of a host receipt; otherwise e2e_state is the declared catalog status.
    ``alias_receipts`` lists receipts recorded under a stack alias of the winner; never counted.
    ``layer`` (``"<catalog>/<layer_id>"``) is the row, which a receipt with ``layer_refs`` must name."""
    component_id = winner.get("component_id")
    platforms: dict[str, dict] = {}
    violations: list[str] = []
    for platform_key in sorted(PLATFORM_KEYS):
        catalog_status = (winner.get("platform_status") or {}).get(platform_key, "untested")
        derived = platform_evidence.platform_status(platform_key, winner, status_context, layer=layer)
        host_verified = derived.status == "accepted" and any(
            ref.startswith("evidence/hosts/") for ref in derived.receipt_refs)
        platforms[platform_key] = {
            "catalog_status": catalog_status,
            "derived_status": derived.status,
            "derived_reason": derived.reason,
            "host_receipts": platform_receipt_info(receipts_summary, component_id, platform_key),
            "e2e_state": "host_verified" if host_verified else catalog_status,
            "qualified_models": platform_qualified_models(receipts_summary, component_id, platform_key),
            "alias_receipts": platform_alias_receipts(receipts_summary, winner, alias_ids, platform_key),
        }
        if platform_key in ENFORCED_PLATFORMS:
            error = platform_evidence.declared_status_error(platform_key, catalog_status, winner, status_context,
                                                            layer=layer)
            if error:
                violations.append(error)
    built = {
        "component_id": component_id,
        "repository": winner.get("repository"),
        "pin": winner.get("pin"),
        "evidence_class": winner.get("evidence_class"),
        "lifecycle_stages": decisions.get(component_id, []),
        "platforms": platforms,
    }
    return built, violations


def build_alternative(alternative: dict, repo_to_component: dict[str, str], receipts_summary: dict,
                      layer=None, catalogued_layers=()) -> dict:
    """An alternative is ``host_verified`` when a receipt of the component sharing its repository is an
    independently reviewed native_proven pass at a use stage that speaks for this row: current
    (platform_status.non_current_paths: not superseded at its version, not on a forked chain), and (platform_status.in_layer_scope) either naming ``layer`` in its
    ``layer_refs`` or unscoped while the repository is catalogued in at most one layer (``catalogued_layers``). A repository in
    several layers can play a different role in each (Codex: native-clients and agent-sdks winner, workers
    alternative), so an unscoped receipt there verifies none of its alternatives, and ``layer_scope_needed``
    marks a row that a receipt naming this layer would verify."""
    repository = alternative.get("repository")
    normalized = host_receipts.normalize_repository(repository)
    component_id = repo_to_component.get(normalized) if normalized is not None else None
    e2e_state = "not_run"
    scope_needed = False
    if isinstance(component_id, str):
        component_bucket = receipts_summary.get("components", {}).get(component_id)
        if component_bucket:
            # Only a reviewed use-stage pass verifies an alternative on a host, as it alone supports accepted for
            # a winner (platform_status.ACCEPTING_STAGES; #164 review, item 2); an install-only pass is recorded.
            unambiguous = len(set(catalogued_layers or ())) <= 1
            superseded = platform_evidence.non_current_paths(receipts_summary, component_id)
            reviewed_use = [entry for platform_bucket in component_bucket.get("platforms", {}).values()
                            for entry in (platform_bucket or {}).get("receipts") or []
                            if isinstance(entry, dict) and entry.get("independently_reviewed_native_proven_pass")
                            and entry.get("stage") in platform_evidence.ACCEPTING_STAGES
                            and entry.get("path") not in superseded]
            verified = any(platform_evidence.in_layer_scope(entry, layer, unscoped=unambiguous)
                           for entry in reviewed_use)
            scope_needed = not verified and any(platform_evidence.in_layer_scope(entry, layer, unscoped=True)
                                                for entry in reviewed_use)
            e2e_state = "host_verified" if verified else "receipts_recorded"
    built = {
        "name": alternative.get("name"),
        "repository": repository,
        "disposition": alternative.get("disposition"),
        "evidence_class": alternative.get("evidence_class"),
        "e2e_state": e2e_state,
    }
    if scope_needed:
        built["layer_scope_needed"] = True
    return built


def build_row(root: Path, catalog: str, layer: dict, decisions: dict[str, list[dict]],
              gap_counts: dict[tuple[str, str], int], receipts_summary: dict,
              repo_to_component: dict[str, str], open_gap_counts: dict[tuple[str, str], int] | None = None,
              status_context: platform_evidence.StatusContext | None = None,
              winner_aliases: dict[str, tuple[str, ...]] | None = None,
              repo_layers: dict[str, set[str]] | None = None):
    if status_context is None:
        status_context = platform_evidence.load_context(root)
    layer_id = layer.get("layer_id")
    layer_key = f"{catalog}/{layer_id}"
    independent_review = classify_independent_review(layer)
    adjudication_ref = find_adjudication_ref(root, catalog, layer_id, layer)

    winners = []
    flip_violations: list[str] = []
    for winner in layer.get("winners", []) or []:
        built, violations = build_winner(winner, decisions, receipts_summary, status_context,
                                         (winner_aliases or {}).get(winner.get("component_id"), ()), layer_key)
        winners.append(built)
        flip_violations.extend(f"{catalog}/{layer_id} winner {built['component_id']!r}: {violation}"
                               for violation in violations)

    alternatives = [
        build_alternative(alternative, repo_to_component, receipts_summary, layer_key,
                          (repo_layers or {}).get(host_receipts.normalize_repository(alternative.get("repository")), ()))
        for alternative in layer.get("alternatives", []) or []
    ]

    row = {
        "catalog": catalog,
        "layer_id": layer_id,
        "title": layer.get("title"),
        "verdict_status": layer.get("verdict_status"),
        "independent_review": independent_review,
        "adjudication_ref": adjudication_ref,
        "open_executable_now_gaps": gap_counts.get((catalog, layer_id)),
        "open_gaps": (open_gap_counts or {}).get((catalog, layer_id)),
        "winners": winners,
        "alternatives": alternatives,
    }
    return row, flip_violations


# --------------------------------------------------------------------- convergence by layer


def _dicts(value) -> list[dict]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def parse_iso_date(value) -> date | None:
    """The ``date`` of an ISO date string (the check scripts/landscape.py applies to ``checked_at``), else None."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def load_convergence_input(root: Path, relative: str, *, required: bool = False):
    """The parsed JSON document at ``relative`` for convergence by layer, or ``None`` when it is absent and not
    ``required``. A required input that is absent, or any input that is present but cannot be read (including a
    duplicate key), stops the build: read as empty, the saturation ledger would mean "no completed sweep" and
    confirm every recorded layer, and a skipped sweep manifest could be the newest one."""
    try:
        path = safe_file(root, relative)
    except InvalidDecisionIndex as error:
        raise SystemExit(f"component_matrix: {relative}: {error}") from error
    if not path.is_file():
        if required:
            raise SystemExit(f"component_matrix: {relative} is missing; convergence by layer cannot tell whether a "
                             "completed sweep reopened a recorded layer")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
    except (OSError, UnicodeError, ValueError) as error:
        raise SystemExit(f"component_matrix: {relative}: cannot read JSON ({error})") from error


def newest_sweep_manifest(root: Path) -> tuple[str | None, dict | None]:
    """(path, document) of the ``catalogs/sota-convergence/manifest-YYYYMMDD.json`` with the latest ISO
    ``checked_at`` (ties: the later file name), or (None, None) when none is committed. Chosen by ``checked_at``,
    never by file name or by ledger order (``saturation_ledger.latest_manifest_ref``). A manifest that cannot be
    read or dated stops the build, since it could be the newest one."""
    try:
        directory = safe_file(root, SWEEP_MANIFEST_DIR)
    except InvalidDecisionIndex:
        return None, None
    if not directory.is_dir():
        return None, None
    newest = None
    for name in sorted(path.name for path in directory.iterdir()):
        if not SWEEP_MANIFEST_NAME.fullmatch(name):
            continue
        relative = f"{SWEEP_MANIFEST_DIR}/{name}"
        document = load_convergence_input(root, relative)
        day = parse_iso_date(document.get("checked_at")) if isinstance(document, dict) else None
        if day is None:
            raise SystemExit(f"component_matrix: {relative}: a sweep manifest must be an object with an ISO checked_at")
        if newest is None or (day, name) > newest[0]:
            newest = ((day, name), relative, document)
    return (newest[1], newest[2]) if newest else (None, None)


def completed_sweeps(ledger_doc) -> list[dict]:
    """The completed sweeps of ``catalogs/saturation/ledger.json``, sorted by (date, sweep_id), each with the
    (catalog, layer_id) pairs its ``layers`` cover. A stopped sweep is left out (catalogs/saturation/README.md: it
    neither counts nor resets); a completed sweep's date equals its manifest's ``checked_at``
    (scripts/saturation_ledger.py checks that). A field the metric reads that is malformed stops the build, since
    skipping that sweep could confirm a layer it reopened."""
    sweeps_value = ledger_doc.get("sweeps") if isinstance(ledger_doc, dict) else None
    if not isinstance(sweeps_value, list):
        raise SystemExit(f"component_matrix: {SATURATION_LEDGER_FILE}: sweeps must be a list")
    sweeps = []
    for position, sweep in enumerate(sweeps_value):
        where = f"component_matrix: {SATURATION_LEDGER_FILE}: sweeps[{position}]"
        if not isinstance(sweep, dict) or sweep.get("status") not in saturation_ledger.STATUSES:
            raise SystemExit(where + " needs the status " + " or ".join(saturation_ledger.STATUSES))
        if sweep["status"] != COMPLETED_SWEEP:
            continue
        day = parse_iso_date(sweep.get("date"))
        layers = sweep.get("layers")
        if day is None or not isinstance(layers, list) or not all(
                isinstance(layer, dict) and isinstance(layer.get("catalog"), str)
                and isinstance(layer.get("layer_id"), str) for layer in layers):
            raise SystemExit(where + ": a completed sweep needs an ISO date and layers that name catalog and layer_id")
        sweeps.append({
            "sweep_id": sweep.get("sweep_id") if isinstance(sweep.get("sweep_id"), str) else None,
            "date": sweep["date"], "day": day, "covers": {(layer["catalog"], layer["layer_id"]) for layer in layers},
            "manifest_ref": sweep.get("manifest_ref") if isinstance(sweep.get("manifest_ref"), str) else None,
        })
    sweeps.sort(key=lambda sweep: (sweep["day"], sweep["sweep_id"] or ""))
    return sweeps


def receipt_aliases(document) -> dict[str, str]:
    """``tools/sota-convergence/receipt-component-aliases.json``: manifests/stack.json id -> sweep-manifest id, or
    {} when the file is absent. A present file whose aliases are not an object of ids stops the build, since
    dropping them would turn alias matches into misses."""
    if document is None:
        return {}
    aliases = document.get("aliases") if isinstance(document, dict) else None
    if not isinstance(aliases, dict) or not all(isinstance(sota_id, str) and sota_id for sota_id in aliases.values()):
        raise SystemExit(f"component_matrix: {RECEIPT_ALIASES_FILE}: aliases must map manifests/stack.json ids to "
                         "sweep-manifest ids")
    return dict(sorted(aliases.items()))


def manifest_layers(manifest_doc) -> list[tuple[str, str]]:
    """(catalog, layer_id) of every layer in both sections of a sweep manifest, sorted and unique."""
    catalog_of = {section: catalog for catalog, section in saturation_ledger.MANIFEST_SECTION.items()}
    return sorted({(catalog_of[section], layer["layer"]) for section in catalog_of
                   for layer in _dicts(manifest_doc.get(section) if isinstance(manifest_doc, dict) else None)
                   if isinstance(layer.get("layer"), str)})


def adoption_index(stack_doc, aliases: dict[str, str]) -> dict:
    """What a foundation manifest row resolves against: the manifests/stack.json ids, and those ids by
    normalized repository and by the sweep-manifest id their alias names."""
    stack_ids: set[str] = set()
    stack_ids_by_repository: dict[str, set[str]] = {}
    for component in _dicts((stack_doc or {}).get("components") if isinstance(stack_doc, dict) else None):
        if isinstance(component.get("id"), str):
            stack_ids.add(component["id"])
            repository = host_receipts.normalize_repository(component.get("repository"))
            if repository is not None:
                stack_ids_by_repository.setdefault(repository, set()).add(component["id"])
    stack_ids_by_alias: dict[str, set[str]] = {}
    for stack_id, sota_id in aliases.items():
        if stack_id in stack_ids:
            stack_ids_by_alias.setdefault(sota_id, set()).add(stack_id)
    return {"stack_ids": stack_ids, "stack_ids_by_repository": stack_ids_by_repository,
            "stack_ids_by_alias": stack_ids_by_alias}


def resolve_manifest_row(section: str, row: dict, index: dict) -> dict:
    """``{"status": "in_use" | "not_in_use" | "unresolved", ...}`` for one sweep-manifest row, by frozen rule 2:
    a trading entry by its decision; a foundation component by its manifests/stack.json id, else the stack ids
    whose alias names it, else the stack ids with its repository, with no uniqueness condition.
    ``adopted_as_candidates`` lists the stack ids so matched, and ``adopted_as`` names the single one (None when
    several share the alias or repository)."""
    row_id = row.get("id")
    if not isinstance(row_id, str) or not row_id:
        return {"status": "unresolved", "reason": "no component id"}
    if section == "trading":
        decision = row.get("decision")
        if decision == IN_USE_TRADING_DECISION:
            return {"status": "in_use", "resolved_by": "decision", "adopted_as": None, "adopted_as_candidates": []}
        if decision in TRADING_DECISIONS:
            return {"status": "not_in_use"}
        return {"status": "unresolved", "reason": "no default or conditional decision"}
    repository = host_receipts.normalize_repository(row.get("repository"))
    for method, candidates in (
            ("id", [row_id] if row_id in index["stack_ids"] else []),
            ("alias", sorted(index["stack_ids_by_alias"].get(row_id, ()))),
            ("repository", sorted(index["stack_ids_by_repository"].get(repository, ())) if repository else [])):
        if candidates:
            return {"status": "in_use", "resolved_by": method,
                    "adopted_as": candidates[0] if len(candidates) == 1 else None,
                    "adopted_as_candidates": candidates}
    return {"status": "unresolved", "reason": "no manifests/stack.json id, alias or repository match"}


def winner_match_method(row: dict, winner: dict, aliases: dict[str, str]) -> str | None:
    """How a sweep-manifest row matches one recorded winner, strongest first: the same component id, an alias in
    either direction, or the same normalized repository; None when it does not match."""
    row_id = row.get("id") if isinstance(row.get("id"), str) else None
    winner_id = winner.get("component_id")
    if not isinstance(winner_id, str):
        return None
    if row_id is not None and winner_id == row_id:
        return "id"
    if row_id is not None and (aliases.get(winner_id) == row_id or aliases.get(row_id) == winner_id):
        return "alias"
    repository = host_receipts.normalize_repository(row.get("repository"))
    if repository is not None and repository == host_receipts.normalize_repository(winner.get("repository")):
        return "repository"
    return None


def winner_match(row: dict, winners: list[dict], aliases: dict[str, str]) -> tuple[str | None, list[str]]:
    """(method, winner ids) for the strongest way the manifest row matches the layer's recorded winners
    (``winner_match_method``); (None, []) for no match."""
    matched: dict[str, set[str]] = {}
    for winner in winners:
        method = winner_match_method(row, winner, aliases)
        if method is not None:
            matched.setdefault(method, set()).add(winner["component_id"])
    for method in WINNER_MATCH_METHODS:
        if method in matched:
            return method, sorted(matched[method])
    return None, []


def pin_current_factor(row: dict) -> str:
    if row.get("pin_comparison") != "compared":
        return "unknown"
    behind = row.get("pin_behind_upstream")
    return "true" if behind is False else "false" if behind is True else "unknown"


def host_e2e_factor(winner_ids: list[str], e2e_states: dict[str, list[str]]) -> str:
    states = [state for winner_id in winner_ids for state in e2e_states.get(winner_id, [])]
    if not states:
        return "unknown"
    return "true" if all(state in HOST_E2E_PASSING for state in states) else "false"


def classify_layer_state(layer: dict, later_sweeps: list[dict]) -> str:
    status = layer.get("verdict_status")
    if status == "pending_lanes":
        return "pending_lanes"
    if status != "recorded" or not (layer.get("winners") or []):
        return "no_selection"
    return "recorded_reopened" if later_sweeps else "confirmed_current"


def load_convergence_context(root: Path, stack_doc) -> dict:
    manifest_path, manifest_doc = newest_sweep_manifest(root)
    aliases = receipt_aliases(load_convergence_input(root, RECEIPT_ALIASES_FILE))
    return {
        "manifest_path": manifest_path, "manifest": manifest_doc, "aliases": aliases,
        "sweeps": completed_sweeps(load_convergence_input(root, SATURATION_LEDGER_FILE, required=True)),
        "index": adoption_index(stack_doc, aliases),
    }


def build_layer_convergence(catalog: str, layer: dict, row: dict, context: dict) -> dict:
    """The convergence object of one matrix row (CONVERGENCE_DEFINITIONS), from its verdict ledger row
    ``layer``, the built matrix ``row`` (its linux-wsl2-x86_64 winner entries) and the loaded context."""
    verdict_day = parse_iso_date(layer.get("checked_at"))
    covered = (catalog, layer.get("layer_id"))
    later = [sweep for sweep in context["sweeps"]
             if covered in sweep["covers"] and (verdict_day is None or sweep["day"] > verdict_day)]
    state = classify_layer_state(layer, later)
    recorded_winners = row["winners"] if layer.get("verdict_status") == "recorded" else []
    e2e_states: dict[str, list[str]] = {}
    for winner in recorded_winners:
        entry = (winner.get("platforms") or {}).get(CONVERGENCE_PLATFORM)
        if isinstance(entry, dict) and isinstance(winner.get("component_id"), str):
            e2e_states.setdefault(winner["component_id"], []).append(entry.get("e2e_state"))

    section = saturation_ledger.MANIFEST_SECTION.get(catalog)
    found = (saturation_ledger.manifest_layer(context["manifest"], catalog, layer.get("layer_id"))
             if isinstance(context["manifest"], dict) else None)
    manifest_rows = []
    if found:
        selection_key = saturation_ledger.SELECTION_KEY[found[0]]
        manifest_rows = found[2].get(selection_key)
        where = f"component_matrix: {context['manifest_path']}: {catalog}/{layer.get('layer_id')}: {selection_key}"
        if not isinstance(manifest_rows, list):
            raise SystemExit(where + " must be a list")
        for position, item in enumerate(manifest_rows):
            if not isinstance(item, dict):
                raise SystemExit(f"{where}[{position}] must be an object")

    factors = {factor: dict.fromkeys(CONVERGENCE_FACTOR_VALUES, 0) for factor in CONVERGENCE_FACTORS}
    components, unresolved, winner_rows = [], [], []
    for manifest_row in manifest_rows:
        row_id = manifest_row.get("id") if isinstance(manifest_row.get("id"), str) else None
        method, winner_ids = winner_match(manifest_row, recorded_winners, context["aliases"])
        if method is not None:
            winner_rows.append({"id": row_id, "matched_by": method, "winner_ids": winner_ids})
        resolution = resolve_manifest_row(section, manifest_row, context["index"])
        if resolution["status"] == "unresolved":
            repository = manifest_row.get("repository")
            unresolved.append({"id": row_id, "repository": repository if isinstance(repository, str) else None,
                               "reason": resolution["reason"]})
            continue
        if resolution["status"] != "in_use":
            continue
        values = {
            "verdict_winner": "true" if method else "false",
            "pin_current": pin_current_factor(manifest_row),
            "host_e2e": host_e2e_factor(winner_ids, e2e_states),
        }
        for factor, value in values.items():
            factors[factor][value] += 1
        components.append({
            "id": row_id, "resolved_by": resolution["resolved_by"], "adopted_as": resolution["adopted_as"],
            "adopted_as_candidates": resolution["adopted_as_candidates"],
            "winner_match": method, "winner_ids": winner_ids, **values,
            "converged": state == "confirmed_current" and all(value == "true" for value in values.values()),
        })
    components.sort(key=lambda item: (item["id"], item["adopted_as"] or ""))
    unresolved.sort(key=lambda item: (item["id"] or "", item["repository"] or "", item["reason"]))
    winner_rows.sort(key=lambda item: (item["id"] or "", item["matched_by"]))
    # The other side of the verdict-to-manifest join: winners no manifest row of this layer matches.
    winners_without_row = sorted({winner["component_id"] for winner in recorded_winners
                                  if isinstance(winner.get("component_id"), str)
                                  and not any(winner_match_method(manifest_row, winner, context["aliases"])
                                              for manifest_row in manifest_rows)})
    return {
        "layer_state": state,
        "verdict_checked_at": layer["checked_at"] if verdict_day is not None else None,
        "reopened_by": ([{"sweep_id": sweep["sweep_id"], "date": sweep["date"]} for sweep in later]
                        if state == "recorded_reopened" else []),
        "in_use": len(components),
        "converged": sum(1 for component in components if component["converged"]),
        "factors": factors,
        "all_rows": len(manifest_rows),
        "recorded_winner_rows": len(winner_rows),
        "winner_rows": winner_rows,
        "manifest_layer_found": found is not None,
        "winners_without_manifest_row": winners_without_row,
        "unresolved": unresolved,
        "components": components,
        "invoke": None,
        "invoke_reason": INVOKE_REASON,
    }


def build_convergence_summary(rows: list[dict], context: dict) -> dict:
    """Layer counts by state; converged / in_use per catalog and overall (a share only where in_use > 0); the
    newest manifest id and checked_at; the newest verdict checked_at per catalog; the newest manifest's layers
    that have no matrix row; definitions and sources."""
    layer_states = dict.fromkeys(CONVERGENCE_LAYER_STATES, 0)
    counted = ("layers", "in_use", "converged", "unresolved")
    catalogs = {catalog: dict.fromkeys(counted, 0) for catalog in sorted(LANDSCAPE_FILES)}
    newest_verdict: dict[str, str | None] = {catalog: None for catalog in sorted(LANDSCAPE_FILES)}
    for row in rows:
        convergence = row["convergence"]
        layer_states[convergence["layer_state"]] += 1
        scope = catalogs.setdefault(row["catalog"], dict.fromkeys(counted, 0))
        scope["layers"] += 1
        scope["in_use"] += convergence["in_use"]
        scope["converged"] += convergence["converged"]
        scope["unresolved"] += len(convergence["unresolved"])
        day = parse_iso_date(convergence["verdict_checked_at"])
        current = parse_iso_date(newest_verdict.get(row["catalog"]))
        if day is not None and (current is None or day > current):
            newest_verdict[row["catalog"]] = convergence["verdict_checked_at"]
    overall = {key: sum(scope[key] for scope in catalogs.values()) for key in counted}
    for scope in (*catalogs.values(), overall):
        scope["share"] = round(scope["converged"] / scope["in_use"], 4) if scope["in_use"] else None
    matrix_layers = {(row["catalog"], row["layer_id"]) for row in rows}
    manifest = context["manifest"]
    return {
        "frozen_at": CONVERGENCE_FROZEN_AT,
        "definitions": [{"term": term, "definition": text} for term, text in CONVERGENCE_DEFINITIONS],
        "sources": {
            "verdict_ledgers": dict(sorted(LANDSCAPE_FILES.items())),
            "saturation_ledger": SATURATION_LEDGER_FILE,
            "completed_sweeps": [{"sweep_id": sweep["sweep_id"], "date": sweep["date"],
                                  "manifest_ref": sweep["manifest_ref"], "layers": len(sweep["covers"])}
                                 for sweep in context["sweeps"]],
            "stack": STACK_FILE,
            "aliases": RECEIPT_ALIASES_FILE,
            "host_e2e_platform": CONVERGENCE_PLATFORM,
        },
        "layer_states": layer_states,
        "catalogs": catalogs,
        "overall": overall,
        "newest_manifest": None if context["manifest_path"] is None else {
            "path": context["manifest_path"],
            "id": manifest.get("id") if isinstance(manifest.get("id"), str) else None,
            "checked_at": manifest["checked_at"],
        },
        "newest_verdict_checked_at": newest_verdict,
        "manifest_layers_without_matrix_row": [
            {"catalog": catalog, "layer_id": layer_id} for catalog, layer_id in manifest_layers(manifest)
            if (catalog, layer_id) not in matrix_layers],
    }


# --------------------------------------------------------------------------- document


def build_document(root: Path):
    decisions_doc = load_optional(root, DECISIONS_FILE)
    decisions = decisions_by_component(decisions_doc)
    gap_doc = load_optional(root, GAP_CROSSWALK_FILE)
    gap_counts = gap_counts_by_layer(gap_doc)
    open_gap_counts = open_gap_counts_by_layer(gap_doc)
    stack_doc = load_optional(root, STACK_FILE)
    repo_to_component = repository_to_component_id(stack_doc)
    status_context = platform_evidence.load_context(root)
    receipts_summary = status_context.summary

    landscape_docs = {catalog: load_optional(root, relative) for catalog, relative in LANDSCAPE_FILES.items()}
    winner_aliases = alias_ids_by_winner(stack_doc, landscape_docs.values())
    repo_layers = host_receipts.repository_layers({
        f"{catalog}/{layer['layer_id']}": layer for catalog, document in landscape_docs.items()
        for layer in (document or {}).get("layers", []) or []
        if isinstance(layer, dict) and isinstance(layer.get("layer_id"), str)})
    convergence_context = load_convergence_context(root, stack_doc)

    rows: list[dict] = []
    flip_violations: list[str] = []
    for catalog, landscape_doc in landscape_docs.items():
        if landscape_doc is None:
            continue
        for layer in landscape_doc.get("layers", []) or []:
            if not isinstance(layer, dict):
                continue
            row, row_flip_violations = build_row(
                root, catalog, layer, decisions, gap_counts, receipts_summary, repo_to_component, open_gap_counts,
                status_context, winner_aliases, repo_layers,
            )
            row["convergence"] = build_layer_convergence(catalog, layer, row, convergence_context)
            rows.append(row)
            flip_violations.extend(row_flip_violations)

    rows.sort(key=lambda row: (row["catalog"], row["layer_id"]))

    # Whether each alias receipt is exempt from validate's alias rejection (GRANDFATHERED_ALIAS_RECEIPTS,
    # path and recorded-claim digest); informational like the rest of the alias listing.
    grandfathered_paths = host_receipts.grandfathered_alias_paths(root)
    for row in rows:
        for winner in row["winners"]:
            for entry in winner["platforms"].values():
                for alias in entry.get("alias_receipts") or []:
                    alias["grandfathered"] = alias.get("path") in grandfathered_paths

    needs_host: dict[str, list[dict]] = {platform_key: [] for platform_key in sorted(PLATFORM_KEYS)}
    for row in rows:
        for winner in row["winners"]:
            for platform_key, entry in winner["platforms"].items():
                if entry["e2e_state"] not in ("accepted", "host_verified"):
                    needs_host[platform_key].append({
                        "catalog": row["catalog"],
                        "layer_id": row["layer_id"],
                        "component_id": winner["component_id"],
                        "e2e_state": entry["e2e_state"],
                    })
    for platform_key in needs_host:
        needs_host[platform_key].sort(key=lambda entry: (entry["catalog"], entry["layer_id"], entry["component_id"]))

    needs_independent_review = [
        {"catalog": row["catalog"], "layer_id": row["layer_id"], "independent_review": row["independent_review"]}
        for row in rows if row["independent_review"] in ("pending_lanes", "single_lane")
    ]

    totals = {
        "layers": len(rows),
        "winners": sum(len(row["winners"]) for row in rows),
        "alternatives": sum(len(row["alternatives"]) for row in rows),
        "dual_lane_same_winner": sum(1 for row in rows if row["independent_review"] == "dual_lane_same_winner"),
        "dual_lane_adjudicated": sum(1 for row in rows if row["independent_review"] == "dual_lane_adjudicated"),
        "pending_lanes": sum(1 for row in rows if row["independent_review"] == "pending_lanes"),
        "single_lane": sum(1 for row in rows if row["independent_review"] == "single_lane"),
    }

    document = {
        "schema_version": 1,
        "checked_at": CHECKED_AT,
        "scope": SCOPE,
        "rows": rows,
        "summary": {
            "totals": totals,
            "needs_host": needs_host,
            "needs_independent_review": needs_independent_review,
            "convergence": build_convergence_summary(rows, convergence_context),
        },
    }
    return document, flip_violations


# ------------------------------------------------------------------------- rendering


def serialize(document: dict) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def assert_no_private_content(text: str) -> None:
    for description, pattern in PRIVATE_CONTENT:
        if pattern.search(text):
            raise SystemExit(f"component_matrix: generated output contains possible {description}; aborting")


def alias_summary_sentence(aliases: list[dict]) -> str:
    """One sentence derived from the listed alias receipts (count, hosts, observation dates and how
    many are grandfathered), or ``""`` when there are none. ``aliases`` holds one entry per
    (row, winner, platform), so a winner selected in several layers repeats the same receipt;
    receipts are counted once each by ``path`` (an entry without a path counts on its own)."""
    unique: dict = {}
    for alias in aliases:
        unique.setdefault(alias.get("path") or id(alias), alias)
    aliases = list(unique.values())
    if not aliases:
        return ""
    hosts = sorted({alias.get("host_id") or "unknown host" for alias in aliases})
    dates = sorted({(alias.get("observed_at_utc") or "")[:10] or "unknown date" for alias in aliases})
    grandfathered = sum(1 for alias in aliases if alias.get("grandfathered"))
    return (f" Listed: {len(aliases)} alias receipt(s) from host(s) {', '.join(f'`{host}`' for host in hosts)}, "
            f"observed {', '.join(dates)}; {grandfathered} of {len(aliases)} grandfathered.")


def newest_source_date(block: dict) -> str | None:
    """The newest of the dates convergence by layer reads (each catalog's newest verdict checked_at, the newest
    sweep manifest's checked_at and the completed sweep dates), derived from the document and never typed."""
    dates = [*block["newest_verdict_checked_at"].values(), (block["newest_manifest"] or {}).get("checked_at"),
             *(sweep["date"] for sweep in block["sources"]["completed_sweeps"])]
    days = [day for day in (parse_iso_date(value) for value in dates) if day is not None]
    return max(days).isoformat() if days else None


def render_convergence_markdown(document: dict) -> list[str]:
    """The "Convergence by layer" section, every number, definition and date read from the document."""
    block = document["summary"]["convergence"]
    sources = block["sources"]
    manifest = block["newest_manifest"]
    newest = block["newest_verdict_checked_at"]
    ledgers = " and ".join(f"`{path}` (newest verdict checked_at {newest.get(catalog) or 'not recorded'})"
                           for catalog, path in sources["verdict_ledgers"].items())
    manifest_text = (f"`{manifest['path']}` (`{manifest['id']}`, checked_at {manifest['checked_at']})"
                     if manifest else "none committed")
    sweeps = ", ".join(f"`{sweep['sweep_id']}` ({sweep['date']})" for sweep in sources["completed_sweeps"])
    lines = [
        "## Convergence by layer",
        "",
        f"Definitions frozen {block['frozen_at']}, before any count was computed. Every count is an integer per "
        "layer computed only from committed files; the three factors stay independent, only pin_current and "
        "host_e2e can be unknown, and factors are never blended into one score or summed across factors.",
        "",
        *(f"- **{item['term']}**: {item['definition']}" for item in block["definitions"]),
        "",
        f"Sources: verdict ledgers {ledgers}; newest sweep manifest {manifest_text}; completed sweeps in "
        f"`{sources['saturation_ledger']}`: {sweeps or 'none recorded'}; adopted components from "
        f"`{sources['stack']}` and `{sources['aliases']}`; host_e2e reads `{sources['host_e2e_platform']}`.",
        "",
        "Layer states: " + ", ".join(f"{state} {count}" for state, count in block["layer_states"].items()) + ".",
        "",
        "in_use and converged count layer-component rows: a component in several layers counts once per layer, "
        "and two rows of one layer that resolve to the same stack component both count, so the catalog and overall "
        "sums below are not numbers of distinct components.",
        "",
        "| Scope | Layers | converged / in_use (layer-component rows) | Share | Unresolved rows |",
        "| --- | --- | --- | --- | --- |",
    ]
    for label, scope in (*block["catalogs"].items(), ("overall", block["overall"])):
        share = "-" if scope["share"] is None else scope["share"]
        lines.append(f"| {label} | {scope['layers']} | {scope['converged']} / {scope['in_use']} | {share} "
                     f"| {scope['unresolved']} |")
    lines += [
        "",
        "| Layer | layer_state | Verdict checked_at | Reopened by | in_use | converged "
        "| verdict_winner (true/false/unknown) | pin_current (true/false/unknown) | host_e2e (true/false/unknown) "
        "| all_rows | recorded_winner_rows | Unresolved | invoke |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in document["rows"]:
        convergence = row["convergence"]
        counts = {factor: "/".join(str(convergence["factors"][factor][value]) for value in CONVERGENCE_FACTOR_VALUES)
                  for factor in CONVERGENCE_FACTORS}
        reopened = ", ".join(f"`{sweep['sweep_id']}`" for sweep in convergence["reopened_by"]) or "-"
        unresolved = ", ".join(f"`{item['id'] or 'no id'}`" for item in convergence["unresolved"]) or "-"
        invoke = "null" if convergence["invoke"] is None else json.dumps(convergence["invoke"], sort_keys=True)
        lines.append(
            f"| `{row['catalog']}/{row['layer_id']}` | {convergence['layer_state']} "
            f"| {convergence['verdict_checked_at'] or '-'} | {reopened} | {convergence['in_use']} "
            f"| {convergence['converged']} | {counts['verdict_winner']} | {counts['pin_current']} "
            f"| {counts['host_e2e']} | {convergence['all_rows']} | {convergence['recorded_winner_rows']} "
            f"| {unresolved} | {invoke} |")
    lines += ["", "### Unresolved manifest rows", ""]
    lines += [f"- `{row['catalog']}/{row['layer_id']}` `{item['id'] or 'no id'}`: {item['reason']}"
              for row in document["rows"] for item in row["convergence"]["unresolved"]] or ["None."]
    # List join gaps; one winner can match several rows, so row counts and winner counts differ.
    # winner_rows[].winner_ids gives the exact per-row mapping.
    lines += ["", "### Recorded winners without a row in the newest sweep manifest", ""]
    lines += [f"- `{row['catalog']}/{row['layer_id']}`: "
              + ", ".join(f"`{winner_id}`" for winner_id in row["convergence"]["winners_without_manifest_row"])
              for row in document["rows"] if row["convergence"]["winners_without_manifest_row"]] or ["None."]
    lines += ["", "### Layers missing from the newest sweep manifest", ""]
    lines += [f"- `{row['catalog']}/{row['layer_id']}`" for row in document["rows"]
              if not row["convergence"]["manifest_layer_found"]] or ["None."]
    lines += ["", "### Newest sweep manifest layers without a matrix row", ""]
    lines += [f"- `{item['catalog']}/{item['layer_id']}`"
              for item in block["manifest_layers_without_matrix_row"]] or ["None."]
    return lines


def render_markdown(document: dict) -> str:
    newest = newest_source_date(document["summary"]["convergence"]) or "none recorded"
    lines = [
        "# Component evidence matrix",
        "",
        f"Scope and schema checked {document['checked_at']}; newest verdict, sweep-manifest or completed-sweep date "
        f"{newest}. Generated by `python3 scripts/component_matrix.py --write` from "
        "`catalogs/landscape/component-evidence-matrix.json`, which reads no clock, so neither date is a build "
        "date. " + document["scope"],
        "",
        "## Totals",
        "",
        "| Metric | Count |",
        "| --- | --- |",
    ]
    totals = document["summary"]["totals"]
    for key in (
        "layers", "winners", "alternatives",
        "dual_lane_same_winner", "dual_lane_adjudicated", "pending_lanes", "single_lane",
    ):
        lines.append(f"| {key} | {totals[key]} |")
    lines += [
        "",
        "## Per-layer",
        "",
        "Each winner shows, for linux-wsl2-x86_64 / macos-arm64, its `e2e_state` and host receipts as "
        "[pass/fail/independently reviewed pass/independently reviewed fail], plus `dissented N` when a "
        "reviewer's latest verdict is disagree or needs_changes. Receipt counts ignore pins; the derived "
        "status in the JSON binds receipts to the winner's current pin.",
        "",
        "| Layer | Independent review | Winners: e2e_state [receipts] (linux-wsl2-x86_64 / macos-arm64) |",
        "| --- | --- | --- |",
    ]

    def platform_cell(entry: dict) -> str:
        counts = entry.get("host_receipts") or {}
        cell = (f"{entry.get('e2e_state', '-')} [{counts.get('pass', 0)}/{counts.get('fail', 0)}/"
                f"{counts.get('independently_reviewed_pass', 0)}/{counts.get('independently_reviewed_fail', 0)}]")
        if counts.get("dissented"):
            cell += f" dissented {counts['dissented']}"
        if entry.get("alias_receipts"):
            cell += f" +{len(entry['alias_receipts'])} alias receipt(s), not counted"
        return cell

    for row in document["rows"]:
        winner_cells = []
        for winner in row["winners"]:
            linux_cell = platform_cell(winner["platforms"].get("linux-wsl2-x86_64", {}))
            macos_cell = platform_cell(winner["platforms"].get("macos-arm64", {}))
            winner_cells.append(f"{winner['component_id']} ({linux_cell} / {macos_cell})")
        adjudication = f" (adjudication: `{row['adjudication_ref']}`)" if row["adjudication_ref"] else ""
        lines.append(
            f"| `{row['catalog']}/{row['layer_id']}` | {row['independent_review']}{adjudication} "
            f"| {'; '.join(winner_cells) if winner_cells else '-'} |"
        )
    alias_entries = [(row, winner, platform_key, alias) for row in document["rows"] for winner in row["winners"]
                     for platform_key, entry in sorted(winner["platforms"].items())
                     for alias in entry.get("alias_receipts") or []]
    lines += ["", "## Alias receipts (listed, never counted)", "", (
        "Receipts recorded under a `manifests/stack.json` id whose repository is a winner's repository "
        "(`scripts/host_receipts.py` `winner_stack_aliases`). Receipts bind to a winner only by its own "
        "`component_id` and full pin, so these never enter the counts, the derived status, the flip rule or "
        "`e2e_state`. `scripts/host_receipts.py record` refuses such ids, and `validate` rejects such receipts "
        "except those grandfathered unchanged, by path and recorded-claim digest, in `GRANDFATHERED_ALIAS_RECEIPTS`; "
        "re-recording on the same host under the winner's `component_id` with its full pin is the path to "
        "binding." + alias_summary_sentence([alias for _row, _winner, _platform, alias in alias_entries])
    ), ""]
    alias_lines = []
    for row, winner, platform_key, alias in alias_entries:
        match = "matches" if alias.get("version_matches_pin") else "does not match"
        grandfathered = "; grandfathered" if alias.get("grandfathered") else ""
        alias_lines.append(
            f"- `{row['catalog']}/{row['layer_id']}` `{winner['component_id']}` {platform_key}: "
            f"`{alias['path']}` recorded as `{alias['recorded_component_id']}` "
            f"{alias.get('recorded_version')!r} ({alias.get('evidence_class')}, {alias.get('stage')}, "
            f"{alias.get('result')}); binds: no (id alias; version {match} the pin in full{grandfathered})")
    lines += alias_lines or ["None."]
    lines += ["", "## Needs host evidence", "", (
        "Winners whose per-platform `e2e_state` is neither `accepted` nor `host_verified`, grouped by "
        "platform. This is the list other WSL/macOS machines should work through with "
        "[`docs/contributing-evidence.md`](contributing-evidence.md). `macos-arm64` entries stay here "
        "until a Mac records receipts that `scripts/platform_status.py` accepts and the layer rows are "
        "re-recorded."
    ), ""]
    for platform_key in sorted(document["summary"]["needs_host"]):
        entries = document["summary"]["needs_host"][platform_key]
        lines.append(f"### {platform_key}")
        lines.append("")
        if not entries:
            lines.append("None.")
        else:
            for entry in entries:
                lines.append(
                    f"- `{entry['catalog']}/{entry['layer_id']}`: `{entry['component_id']}` "
                    f"(catalog/e2e state: {entry['e2e_state']})"
                )
        lines.append("")
    lines += ["## Needs independent review", "", (
        "Rows whose `independent_review` is `pending_lanes` (a dual-lane disagreement that the "
        "counterbalanced adjudication did not resolve) or `single_lane` (no second lane recorded)."
    ), ""]
    needs_review = document["summary"]["needs_independent_review"]
    if not needs_review:
        lines.append("None.")
    else:
        for entry in needs_review:
            lines.append(f"- `{entry['catalog']}/{entry['layer_id']}`: {entry['independent_review']}")
    lines += ["", *render_convergence_markdown(document)]
    lines += [
        "",
        "## How to update this page",
        "",
        "This page and `catalogs/landscape/component-evidence-matrix.json` are generated, not hand-edited. "
        "After adding host receipts, a decision, a gap-crosswalk regeneration or a landscape verdict update, "
        "run `python3 scripts/component_matrix.py --write` and commit both files. "
        f"Convergence by layer also reads `{SATURATION_LEDGER_FILE}`, the newest "
        f"`{SWEEP_MANIFEST_DIR}/manifest-YYYYMMDD.json`, `{STACK_FILE}` and `{RECEIPT_ALIASES_FILE}`, so run "
        "`--write` again after appending a sweep to the ledger or committing a sweep manifest. A missing ledger, "
        "or a ledger, sweep manifest or alias file that cannot be read, stops the build instead of reading as "
        "empty. "
        "`python3 scripts/component_matrix.py --check` (run in CI) recomputes both outputs and also enforces "
        "the flip rule, which `scripts/landscape.py` enforces too through the same function "
        "(`scripts/platform_status.py`): a declared `macos-arm64` `platform_status` may not claim more than "
        "the recorded evidence supports. `accepted` needs a host receipt for that platform at stage `use` "
        "(an `install` pass supports `conditional` at most) that is `result: pass` and "
        "`evidence_class: native_proven`, records the winner's current "
        "pin in `tool_versions`, declares `host.second_physical_machine: true`, has `host.os`/"
        "`host.architecture` consistent with `adoption/manifest.json`'s `platform_profiles[]` entry, and "
        "carries an `agree` review from a reviewer identity other than the recorder's with no standing "
        "`disagree`/`needs_changes` review. A `native_proven` `use`/`install` fail that is the latest receipt for "
        "its host and stage blocks `accepted` until that host records a later pass. `conditional` needs a "
        "pin-bound, non-`synthetic` pass from a declared second physical machine with no standing dissent. "
        "A receipt superseded at the same component version, or on a forked supersede chain, supports no "
        "status, though a superseded `native_proven` fail still blocks "
        "until a later current native pass at the same pin, platform, stage and layer; a receipt with "
        "`layer_refs` counts only in the layers it names; and a host receipt cited in a winner's "
        "`evidence_refs` counts only through this receipt route, never as a registered artifact. An alternative (JSON only) is `host_verified` on such a reviewed `use` "
        "pass of the component sharing its repository, which must name the alternative's layer in "
        "`layer_refs` when that repository is catalogued in more than one layer (`layer_scope_needed` marks "
        "an alternative an unscoped pass would otherwise verify). "
        "Never edit `platform_status` in the landscape files to make this page "
        "pass; add the underlying host receipt instead, following "
        "[`docs/contributing-evidence.md`](contributing-evidence.md).",
        "",
    ]
    return "\n".join(lines)


# -------------------------------------------------------------------------------- main


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--write", action="store_true", help="Write the generated outputs.")
    parser.add_argument("--check", action="store_true",
                         help="Recompute and compare against the checked-in outputs (default).")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    write_mode = bool(args.write) and not args.check

    document, flip_violations = build_document(root)
    json_text = serialize(document)
    md_text = render_markdown(document)
    assert_no_private_content(json_text)
    assert_no_private_content(md_text)

    json_path = root / OUTPUT_JSON
    md_path = root / OUTPUT_MD

    if write_mode:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json_text, encoding="utf-8")
        md_path.write_text(md_text, encoding="utf-8")
        # Keep manifests/evidence.json's registered hashes for these two generated
        # outputs current: otherwise any contributor who adds a receipt/review and
        # reruns --write leaves scripts/validate.py reporting a stale hash for them.
        host_receipts.register_file(root, OUTPUT_JSON)
        host_receipts.register_file(root, OUTPUT_MD)
        print(json.dumps({
            "status": "written", "rows": len(document["rows"]),
            "flip_rule_violations": len(flip_violations),
        }, sort_keys=True))
        return 0

    ok = True
    if not json_path.exists() or json_path.read_text(encoding="utf-8") != json_text:
        print(f"component-evidence-matrix JSON differs from the generated output: {json_path}")
        ok = False
    if not md_path.exists() or md_path.read_text(encoding="utf-8") != md_text:
        print(f"component-evidence-matrix markdown differs from the generated output: {md_path}")
        ok = False
    if flip_violations:
        print(f"flip-rule violation(s) ({len(flip_violations)}):")
        for violation in flip_violations:
            print(f"- {violation}")
        ok = False

    if not ok:
        return 1
    print(json.dumps({"status": "checked", "rows": len(document["rows"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
