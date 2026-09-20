#!/usr/bin/env python3
"""Validate FOUNDATION capability references offline, without replaying receipts.

Pins, original claims and lifecycle stage evidence stay in their canonical files.
This checks consistency of the selection, never the truth of a prose assertion.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.validate_catalogs import (
        InvalidCatalog, Validator, dated, enum, https, object_value, require,
        sequence, strings, text,
    )
except ModuleNotFoundError:
    from validate_catalogs import (
        InvalidCatalog, Validator, dated, enum, https, object_value, require,
        sequence, strings, text,
    )


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "catalogs/foundation/manifest.json"
DECISIONS = "catalogs/foundation/decisions.json"
SOURCES = {
    "components": "manifests/stack.json",
    "evidence": "manifests/evidence.json",
    "lifecycle": "blueprints/token-native-focus/saturation-audit.json",
    "shared_research_inventory": "catalogs/us-equities/decision-index.json",
}
LAYERS = {
    "native-clients", "instructions-skills", "workers", "isolation", "code-navigation",
    "document-retrieval", "semantic-rag", "durable-memory", "web-research",
    "token-efficiency", "quality-evaluation", "ci-supply-chain", "scheduling-supervision",
    "hosting-services", "recovery-portability", "observation-inference",
}
STAGES = {"install", "use", "persistence", "restart", "cleanup", "recovery"}
STATUSES = {
    "accepted_within_scope", "observed_installed", "partial_acceptance",
    "documented_not_replayed", "not_established", "not_applicable",
}
EXECUTION = {"native_model_e2e", "native_cli_e2e", "artifact_measurement"}


def fields(value, expected, label):
    object_value(value, label)
    require(not value.keys() - expected, label, f"unknown fields: {sorted(value.keys() - expected)}")
    require(not expected - value.keys(), label, f"missing fields: {sorted(expected - value.keys())}")


def indexed(rows, key, label):
    result = {}
    for row in sequence(rows, label):
        object_value(row, label)
        identifier = text(row.get(key), f"{label}.{key}")
        require(identifier not in result, label, f"duplicate ID {identifier}")
        result[identifier] = row
    return result


def source_paths(values, validator, label):
    for path in strings(values, label):
        validator.path(path, label)


def validate_foundation(root: Path) -> dict:
    validator = Validator(root)
    manifest = validator.load(MANIFEST)
    fields(manifest, {"schema_version", "catalog_id", "checked_at", "scope", "limitations",
                      "canonical_sources", "decisions_file", "layers", "domain_boundary", "top_gaps", "open_gates"}, MANIFEST)
    validator.header(manifest, MANIFEST)
    require(manifest["catalog_id"] == "foundation", MANIFEST, "catalog_id must be foundation")
    text(manifest["scope"], "manifest.scope")
    strings(manifest["limitations"], "manifest.limitations")
    require(manifest["canonical_sources"] == SOURCES, "canonical_sources", "use canonical sources without copying pins or receipts")
    require(manifest["decisions_file"] == DECISIONS, "decisions_file", "use the FOUNDATION decisions file")
    for path in SOURCES.values():
        validator.path(path, "canonical_sources")
    components = indexed(validator.load(SOURCES["components"]).get("components"), "id", "components")
    receipts = indexed(validator.load(SOURCES["evidence"]).get("receipts"), "id", "receipts")
    lifecycle = indexed(validator.load(SOURCES["lifecycle"]).get("components"), "component_id", "lifecycle")

    layers = indexed(manifest["layers"], "id", "layers")
    require(set(layers) == LAYERS, "layers", "must contain exactly the 16 required layers")
    for identifier, layer in layers.items():
        fields(layer, {"id", "title", "purpose", "selection", "activation", "lifecycle_scope", "next_gap"}, identifier)
        for key, value in layer.items():
            text(value, f"{identifier}.{key}")

    domain = {}
    for row in sequence(manifest["domain_boundary"], "domain_boundary", nonempty=False):
        fields(row, {"component_id", "catalog", "scope"}, "domain_boundary")
        identifier = text(row["component_id"], "domain_boundary.component_id")
        require(identifier in components, "domain_boundary", f"unknown component {identifier}")
        require(identifier not in domain, "domain_boundary", "duplicate component")
        validator.path(row["catalog"], "domain_boundary.catalog")
        text(row["scope"], "domain_boundary.scope")
        domain[identifier] = row

    gaps = indexed(manifest["top_gaps"], "id", "top_gaps")
    priorities = []
    for gap in gaps.values():
        fields(gap, {"id", "priority", "status", "scope", "next_action", "source_paths"}, "top_gaps")
        require(type(gap["priority"]) is int, "top_gaps.priority", "expected integer priority")
        priorities.append(gap["priority"])
        enum(gap["status"], {"open", "partial", "addressed_in_catalog"}, "top_gaps.status")
        text(gap["scope"], "top_gaps.scope")
        text(gap["next_action"], "top_gaps.next_action")
        source_paths(gap["source_paths"], validator, "top_gaps.source_paths")
    require(sorted(priorities) == [1, 2, 3], "top_gaps", "exactly three ranked gaps required")
    gate_ids, gap_ids = set(), set()
    for gate in sequence(manifest["open_gates"], "open_gates", nonempty=False):
        fields(gate, {"id", "gap_id"}, "open_gates")
        gate_id = text(gate["id"], "open_gates.id")
        gap_id = text(gate["gap_id"], "open_gates.gap_id")
        require(gate_id not in gate_ids and gap_id not in gap_ids, "open_gates", "duplicate gate or gap")
        require(gap_id in gaps, "open_gates", "unknown gap")
        gate_ids.add(gate_id)
        gap_ids.add(gap_id)
    require(gap_ids == {identifier for identifier, gap in gaps.items() if gap["status"] != "addressed_in_catalog"},
            "open_gates", "must reference exactly the unfinished gaps")

    document = validator.load(DECISIONS)
    fields(document, {"schema_version", "checked_at", "scope", "decisions"}, DECISIONS)
    validator.header(document, DECISIONS, manifest["checked_at"])
    text(document["scope"], "decisions.scope")
    decisions = indexed(document["decisions"], "id", "decisions")
    used_layers, used_components, used_receipts, candidates = set(), set(), set(), set()
    for identifier, row in decisions.items():
        fields(row, {"id", "capability", "capability_key", "checked_at", "layer_ids", "selection", "review_status",
                     "activation", "component_ids", "candidate", "evidence_ids", "evidence_scope", "limitations",
                     "source_paths", "next_gap", "lifecycle", "supersedes"}, identifier)
        for key in ("capability", "capability_key", "activation", "evidence_scope", "next_gap"):
            text(row[key], f"{identifier}.{key}")
        checked = dated(row["checked_at"], f"{identifier}.checked_at")
        require(checked <= dated(manifest["checked_at"], "manifest.checked_at"), identifier, "decision date exceeds manifest")
        layer_ids = strings(row["layer_ids"], f"{identifier}.layer_ids")
        require(set(layer_ids) <= LAYERS, identifier, "unknown layer")
        used_layers.update(layer_ids)
        enum(row["selection"], {"default", "conditional", "optional", "trial", "candidate"}, f"{identifier}.selection")
        enum(row["review_status"], {"accepted_within_scope", "partial_acceptance", "source_review", "discovery", "not_established"},
             f"{identifier}.review_status")
        component_ids = strings(row["component_ids"], f"{identifier}.component_ids", nonempty=False)
        require(set(component_ids) <= components.keys(), identifier, "unknown component")
        require(not set(component_ids) & domain.keys(), identifier, "component belongs to domain boundary")
        evidence_ids = strings(row["evidence_ids"], f"{identifier}.evidence_ids", nonempty=False)
        require(set(evidence_ids) <= receipts.keys(), identifier, "unknown evidence")
        strings(row["limitations"], f"{identifier}.limitations")
        source_paths(row["source_paths"], validator, f"{identifier}.source_paths")

        candidate = row["candidate"]
        if row["selection"] == "candidate":
            fields(candidate, {"id", "repository"}, f"{identifier}.candidate")
            candidate_id = text(candidate["id"], f"{identifier}.candidate.id")
            require(candidate_id not in candidates and candidate_id not in components, identifier, "candidate identity duplicates adopted component or candidate")
            https(candidate["repository"], f"{identifier}.candidate.repository")
            require(not component_ids and not evidence_ids and row["review_status"] in {"discovery", "source_review", "not_established"},
                    identifier, "candidate cannot assert adopted components or native acceptance")
            candidates.add(candidate_id)
        else:
            require(candidate is None and bool(component_ids), identifier, "selected capability needs component IDs, not a candidate")
            require(bool(evidence_ids), identifier, "selected capability needs evidence references")

        bound_components = set()
        for evidence_id in evidence_ids:
            receipt = receipts[evidence_id]
            validator.path(receipt.get("path"), f"{identifier}.evidence.{evidence_id}")
            receipt_components = set(strings(receipt.get("component_ids"), f"{evidence_id}.component_ids"))
            overlap = set(component_ids) & receipt_components
            require(bool(overlap), identifier, f"unrelated evidence {evidence_id}")
            bound_components.update(overlap)
            text(receipt.get("claim"), f"{evidence_id}.claim")
            strings(receipt.get("limitations"), f"{evidence_id}.limitations")
        require(set(component_ids) <= bound_components, identifier, "component without related evidence")
        if row["review_status"] == "accepted_within_scope":
            require(any(receipts[evidence_id].get("kind") in EXECUTION for evidence_id in evidence_ids),
                    identifier, "native acceptance requires execution evidence, not inventory alone")

        stages = row["lifecycle"]
        fields(stages, {"source_path", "scope", "unknown", "stage_refs"}, f"{identifier}.lifecycle")
        require(stages["source_path"] == SOURCES["lifecycle"], identifier, "use canonical lifecycle source")
        text(stages["scope"], f"{identifier}.lifecycle.scope")
        text(stages["unknown"], f"{identifier}.lifecycle.unknown")
        seen_stages = set()
        for stage in sequence(stages["stage_refs"], f"{identifier}.stage_refs", nonempty=bool(component_ids)):
            fields(stage, {"component_id", "stage", "status"}, f"{identifier}.stage_refs")
            require(stage["component_id"] in component_ids and stage["component_id"] in lifecycle,
                    identifier, "invalid lifecycle component")
            enum(stage["stage"], STAGES, f"{identifier}.lifecycle stage")
            enum(stage["status"], STATUSES, f"{identifier}.lifecycle status")
            key = (stage["component_id"], stage["stage"])
            require(key not in seen_stages, identifier, "duplicate lifecycle stage")
            seen_stages.add(key)
            canonical = object_value(lifecycle[stage["component_id"]].get("lifecycle_stages"), "canonical lifecycle")
            native_stage = object_value(canonical.get(stage["stage"]), "canonical lifecycle stage")
            require(stage["status"] == native_stage.get("status"), identifier, "lifecycle status differs from canonical scoped evidence")
            text(native_stage.get("scope"), "canonical lifecycle scope")
            for path in strings(native_stage.get("evidence_refs"), "canonical lifecycle evidence", nonempty=False):
                validator.path(path, "canonical lifecycle evidence")
        require(set(component_ids) <= {key[0] for key in seen_stages}, identifier, "component missing lifecycle reference")
        if row["review_status"] == "accepted_within_scope":
            accepted_components = {stage["component_id"] for stage in stages["stage_refs"]
                                   if stage["status"] == "accepted_within_scope"}
            require(set(component_ids) <= accepted_components, identifier,
                    "capability acceptance requires a canonical accepted stage for each component")
        if candidate is not None:
            require(not seen_stages, identifier, "candidate lifecycle must remain pending")
        used_components.update(component_ids)
        used_receipts.update(evidence_ids)

    require(used_layers == LAYERS, "decisions", "every required layer needs a capability or explicit pending decision")
    for identifier, row in decisions.items():
        targets = set()
        for supersession in sequence(row["supersedes"], f"{identifier}.supersedes", nonempty=False):
            fields(supersession, {"decision_id", "scope", "reason"}, f"{identifier}.supersedes")
            target = text(supersession["decision_id"], f"{identifier}.supersedes.decision_id")
            require(target in decisions, identifier, "unknown superseded decision")
            require(target != identifier and target not in targets, identifier, "self or duplicate supersession")
            targets.add(target)
            text(supersession["scope"], f"{identifier}.supersedes.scope")
            text(supersession["reason"], f"{identifier}.supersedes.reason")
            previous = decisions[target]
            require(previous["capability_key"] == row["capability_key"]
                    and set(previous["component_ids"]) == set(row["component_ids"])
                    and previous["candidate"] == row["candidate"], identifier, "supersession must retain the same capability and component scope")
            require(dated(previous["checked_at"], "superseded date") < dated(row["checked_at"], "decision date"),
                    identifier, "superseded decision must be earlier; cycles forbidden")

    return {"layers": len(layers), "decisions": len(decisions), "foundation_components": len(used_components),
            "domain_components": len(domain), "evidence_receipts": len(used_receipts), "candidates": len(candidates)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        counts = validate_foundation(args.root)
        report = {"ok": True, "counts": counts, "errors": []}
    except (InvalidCatalog, OSError, UnicodeError, ValueError) as error:
        report = {"ok": False, "counts": {}, "errors": [str(error)]}
    if args.as_json:
        print(json.dumps(report, indent=2))
    elif report["ok"]:
        print("FOUNDATION catalog valid: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    else:
        print("FOUNDATION catalog invalid: " + "; ".join(report["errors"]))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
