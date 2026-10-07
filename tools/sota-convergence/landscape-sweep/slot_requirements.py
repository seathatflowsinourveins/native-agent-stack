"""Project retained slot requirements onto existing landscape parents, offline.

The parent inventory is reused directly from
native-agent-stack@8b844d37:scripts/build_new_wsl_handbook.py:459, whose
rows_of/apply_convergence reference is assemble_manifest.py@675bdd51c96af28aa98012d9e4ff772a77a38f3d.
The retained requirement carrier is
native-agent-stack@8b844d37:evidence/artifacts/new-wsl-final-architecture-20261002/added-slots/slots.json:6.

Requirement IDs and inventory slot IDs can differ. Such a join needs an explicit,
source-cited crosswalk; this projection never infers it from selected components,
installed status, a final verdict or similar requirement text. Source references
are supplied by the caller, which must bind them to its frozen input bytes.
"""

from __future__ import annotations

import copy
import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
from scripts.build_new_wsl_handbook import (  # noqa: E402
    DEFAULTS_MANIFEST, Inputs, default_slot_inventory, manifest_source_path, read_manifest_sources,
)

REQUIREMENTS_PATH = "evidence/artifacts/new-wsl-final-architecture-20261002/added-slots/slots.json"
# New requirement-to-job annotations. They use the explicit job and parent
# declarations, never the manifest's component selections or execution verdicts.
# native-agent-stack@8b844d37:DEFAULTS_MANIFEST:1220,2539,2611,3210,3433.
JOB_CROSSWALK = {
    "structural-code-search": ("structural-search",),
    "llm-tracing": ("phoenix",),
    "alerting-notification": ("alerting",),
    "secret-scanning": ("betterleaks", "trufflehog"),
    "agents-in-ci": ("claude-code-action",),
}


def load_slot_requirements(root: Path, canonical_layer_keys) -> dict:
    """Bind retained requirement bytes and native parent sources before projection.

    Reduced fixture repositories may omit both historical sources. A partial
    source set is an error, rather than silently dropping declared requirements.
    This annotation changes neither historical carriers nor legacy ledger hashes.
    """
    present = [(root / path).is_file() for path in (REQUIREMENTS_PATH, DEFAULTS_MANIFEST)]
    if not any(present):
        return {}
    if not all(present):
        raise ValueError("slot requirements need both retained requirements and native parent manifest")
    inputs = Inputs(root)
    requirements = inputs.read(REQUIREMENTS_PATH)
    manifest = inputs.read(DEFAULTS_MANIFEST)
    catalogs = sorted({row["catalog"] for row in manifest["layers"]})
    selected_sources = {name: source for name, source in manifest["sources"].items()
                        if name in {*catalogs, "convergence", "consensus"}}
    inventory_data = read_manifest_sources(inputs, selected_sources, set(catalogs))

    def source(path, pointer=None):
        result = {**inputs.sources[path], "citation": f"native-agent-stack@8b844d37:{path}:1",
                  "evidence_class": "source_review"}
        if pointer is not None:
            result["pointer"] = pointer
        return result

    source_refs = {name: source(manifest_source_path(reference))
                   for name, reference in selected_sources.items()}
    source_refs["requirements"] = source(REQUIREMENTS_PATH)
    declared_jobs = {row["slot_id"]: (index, row) for index, row in enumerate(manifest["slots"])}
    crosswalk = []
    for identifier, targets in JOB_CROSSWALK.items():
        declarations = []
        for target in targets:
            if target not in declared_jobs:
                raise ValueError(f"slot crosswalk {identifier} lacks declared job {target}")
            index, row = declared_jobs[target]
            if not isinstance(row.get("job"), str) or not row["job"].strip():
                raise ValueError(f"slot crosswalk {identifier} lacks job text for {target}")
            declarations.append({"slot_id": target, "layer_id": row["layer_id"], "job": row["job"],
                                 "source": source(DEFAULTS_MANIFEST, f"/slots/{index}")})
        crosswalk.append({"slot_id": identifier, "parent_slot_ids": list(targets),
                          "source": source(DEFAULTS_MANIFEST), "job_declarations": declarations})
    projected = project_slot_requirements(requirements, inventory_data, catalogs, canonical_layer_keys,
                                          source_refs, crosswalk=crosswalk)
    annotations = {row["slot_id"]: row["job_declarations"] for row in crosswalk}
    for records in projected.values():
        for record in records:
            if record["slot_id"] in annotations:
                record["parent_job_declarations"] = copy.deepcopy(annotations[record["slot_id"]])
    return projected


def _source(reference: dict[str, str] | None, description: str, pointer: str | None = None) -> dict[str, str]:
    if not isinstance(reference, dict) or any(
        not isinstance(reference.get(field), str) or not reference[field].strip()
        for field in ("path", "sha256", "citation")
    ):
        raise ValueError(f"{description} needs path, sha256 and citation")
    # Native source-path/hash structure, not a claim that supplied bytes were verified.
    # native-agent-stack@8b844d37:scripts/build_new_wsl_handbook.py:428.
    manifest_source_path({"path": reference["path"], "sha256": reference["sha256"]})
    result = copy.deepcopy(reference)
    if pointer is not None:
        result["pointer"] = pointer
    return result


def project_slot_requirements(
    requirement_document: dict,
    inventory_data: dict[str, dict | None],
    catalog_names: Iterable[str],
    canonical_layer_keys: Iterable[tuple[str, str]],
    source_refs: dict[str, dict[str, str]],
    *,
    crosswalk: list[dict] | None = None,
) -> dict[tuple[str, str], list[dict]]:
    """Return (catalog, layer_id) -> requirements with their retained provenance.

    ``inventory_data`` and ``catalog_names`` are the handbook inventory's native
    arguments. ``canonical_layer_keys`` are the existing landscape identities,
    not new IDs taken from the requirement carrier. ``source_refs`` names the
    requirements document and every inventory document the native function reads.
    An optional crosswalk row has ``slot_id``, ``parent_slot_ids`` and ``source``
    (path, sha256, citation). Multiple target slots must have the same parent.

    The output carries declared requirement text only. A missing, null or blank
    requirement remains unknown; no decision or execution status is projected.
    This function performs no file write, hash migration, network or model call.
    """
    if not isinstance(requirement_document, dict) or not isinstance(requirement_document.get("slots"), list):
        raise ValueError("slot requirement source needs a slots list")
    if not isinstance(inventory_data, dict) or not isinstance(source_refs, dict):
        raise ValueError("slot inventory data and source references must be objects")
    slots = requirement_document["slots"]
    identifiers = []
    for row in slots:
        if not isinstance(row, dict) or not isinstance(row.get("layer_id"), str) or not row["layer_id"].strip():
            raise ValueError("slot requirement needs its retained layer_id identifier")
        if row["layer_id"] in identifiers:
            raise ValueError(f"duplicate requirement slot: {row['layer_id']}")
        identifiers.append(row["layer_id"])

    catalogs = tuple(catalog_names)
    inventory = default_slot_inventory(inventory_data, catalogs)
    parent_sources = [
        _source(source_refs.get(name), f"inventory source {name}")
        for name in (*catalogs, *(name for name in ("convergence", "consensus") if name in inventory_data))
    ]
    requirement_source = _source(source_refs.get("requirements"), "requirement source")
    canonical = set(canonical_layer_keys)
    mappings = {}
    if crosswalk is not None and not isinstance(crosswalk, list):
        raise ValueError("slot requirement crosswalk must be a list")
    for row in crosswalk or []:
        if not isinstance(row, dict) or row.get("slot_id") not in identifiers:
            raise ValueError("crosswalk names an unknown requirement slot")
        identifier = row["slot_id"]
        if identifier in mappings:
            raise ValueError(f"duplicate crosswalk slot: {identifier}")
        targets = row.get("parent_slot_ids")
        if not isinstance(targets, list) or not targets or any(
            not isinstance(target, str) or not target.strip() for target in targets
        ):
            raise ValueError(f"crosswalk slot {identifier} needs parent_slot_ids")
        if len(set(targets)) != len(targets):
            raise ValueError(f"crosswalk slot {identifier} repeats a parent slot")
        mappings[identifier] = (list(targets), _source(row.get("source"), f"crosswalk source {identifier}"))

    projected = {}
    for index, row in enumerate(slots):
        identifier = row["layer_id"]
        targets, mapping_source = mappings.get(identifier, ([identifier], None))
        missing = [target for target in targets if target not in inventory]
        if missing:
            raise ValueError(f"requirement slot {identifier} has no inventory parent for {missing}; "
                             "supply a source-cited crosswalk")
        parents = {inventory[target] for target in targets}
        if len(parents) != 1:
            raise ValueError(f"requirement slot {identifier} has ambiguous parents: {sorted(parents)}")
        parent, = parents
        if identifier in inventory and inventory[identifier] != parent:
            raise ValueError(f"crosswalk slot {identifier} disagrees with its native inventory parent")
        if parent not in canonical:
            raise ValueError(f"requirement slot {identifier} names an unknown landscape parent: {parent}")
        requirement = row.get("requirement")
        if requirement is not None and not isinstance(requirement, str):
            raise ValueError(f"requirement slot {identifier} text must be a string or null")
        record = {
            "slot_id": identifier,
            "title": copy.deepcopy(row.get("title")),
            "requirement": requirement,
            "requirement_status": "declared" if isinstance(requirement, str) and requirement.strip() else "unknown",
            "source": _source(requirement_source, "requirement source", f"/slots/{index}"),
            "parent": {"catalog": parent[0], "layer_id": parent[1], "slot_ids": list(targets)},
            "parent_sources": copy.deepcopy(parent_sources),
        }
        if mapping_source is not None:
            record["mapping_source"] = copy.deepcopy(mapping_source)
        projected.setdefault(parent, []).append(record)
    return projected
