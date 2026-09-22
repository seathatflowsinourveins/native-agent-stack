#!/usr/bin/env python3
"""Deterministic, no-network extraction of the SOTA-convergence working files.

Reads the two maintained catalogs and writes the fixed set of intermediate
"working files" that ``github_freshness.py`` and ``build_manifest.py`` consume.
Nothing here calls a network API or reads a private host path; every input is
a repository-relative file already checked into ``catalogs/`` and
``manifests/``.

Inputs (repository-relative, overridable):
  catalogs/foundation/manifest.json    - the 16 foundation layer ids/titles + top_gaps
  catalogs/foundation/decisions.json   - per-decision layer_ids + component_ids
  manifests/stack.json                 - component id -> repository/version/license/profile/role
  catalogs/us-equities/foundation-memory.json
  catalogs/us-equities/agents-operations.json
  catalogs/us-equities/data-research.json
  catalogs/us-equities/engines-strategies.json
  catalogs/us-equities/models.json
  catalogs/us-equities/star-audit.json
  catalogs/us-equities/coverage.json
  catalogs/sota-convergence/manifest-20260922.json  - source of the 12-layer taxonomy only

Outputs (written under --out):
  foundation-layers.json  {checked_at, layers:[{layer_id,title,summary,decisions,components}], top_gaps}
  trading-catalog.json    {entries:[fine-grained entries + catalog_file], layer_index:{tag:[entry ids]}}
  trading-by-layer.json   {taxonomy:{layer_id:[tags]}, layers:{layer_id:[entries]}}
  star-candidates.json    {star_candidates, beyond_stars, star_count}
  models.json             {entries:[...]}

Every output is deterministic for a fixed set of inputs: components and
entries are sorted by id, and tag/layer indexes are sorted by key, so two
runs against unchanged inputs byte-for-byte match (module the ``checked_at``
stamps carried over verbatim from the source catalogs).
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Foundation: catalogs/foundation/{manifest,decisions}.json + manifests/stack.json
# ---------------------------------------------------------------------------

FOUNDATION_DECISION_FIELDS = (
    "id", "capability", "selection", "review_status", "component_ids",
    "activation", "candidate", "evidence_ids",
)
FOUNDATION_COMPONENT_FIELDS = ("id", "repository", "version", "license", "role", "profile")


def build_foundation_layers(manifest: dict, decisions_doc: dict, stack: dict) -> dict:
    layer_order = [layer["id"] for layer in manifest.get("layers", [])]
    titles = {layer["id"]: layer.get("title", layer["id"]) for layer in manifest.get("layers", [])}
    by_layer = {lid: {"layer_id": lid, "title": titles[lid], "summary": "", "decisions": [], "components": []}
                for lid in layer_order}
    stack_components = {c["id"]: c for c in stack.get("components", [])}

    for decision in decisions_doc.get("decisions", []):
        entry = {field: decision.get(field) for field in FOUNDATION_DECISION_FIELDS}
        for layer_id in decision.get("layer_ids") or []:
            if layer_id in by_layer:
                by_layer[layer_id]["decisions"].append(entry)

    for layer_id in layer_order:
        layer = by_layer[layer_id]
        referenced = set()
        for decision in layer["decisions"]:
            referenced.update(decision.get("component_ids") or [])
        for component_id in sorted(referenced):
            component = stack_components.get(component_id)
            if component is None:
                continue
            layer["components"].append({field: component.get(field) for field in FOUNDATION_COMPONENT_FIELDS})

    return {
        "checked_at": decisions_doc.get("checked_at"),
        "layers": [by_layer[lid] for lid in layer_order],
        "top_gaps": manifest.get("top_gaps", []),
    }


# ---------------------------------------------------------------------------
# Trading: catalogs/us-equities/{foundation-memory,agents-operations,data-research,engines-strategies}.json
# ---------------------------------------------------------------------------

TRADING_SOURCE_FILES = ("foundation-memory", "agents-operations", "data-research", "engines-strategies")


def build_trading_catalog(us_equities_dir: Path) -> dict:
    entries = []
    layer_index = defaultdict(list)
    for name in TRADING_SOURCE_FILES:
        path = us_equities_dir / f"{name}.json"
        if not path.exists():
            continue
        doc = load_json(path)
        for raw in doc.get("entries", []):
            entry = dict(raw)
            entry["catalog_file"] = name
            entries.append(entry)
            for tag in entry.get("layers") or []:
                layer_index[tag].append(entry["id"])
    entries.sort(key=lambda e: e.get("id") or "")
    return {
        "entries": entries,
        "layer_index": {tag: sorted(ids) for tag, ids in sorted(layer_index.items())},
    }


def load_taxonomy(taxonomy_source: Path) -> dict:
    """The 12-layer taxonomy is copied from manifest-20260922.json#/taxonomy;
    reading it live keeps this extraction in sync with that fixed record
    instead of duplicating a second stale copy in source."""
    doc = load_json(taxonomy_source)
    taxonomy = doc.get("taxonomy") if isinstance(doc, dict) else None
    if not isinstance(taxonomy, dict):
        raise ValueError(f"{taxonomy_source} has no #/taxonomy mapping")
    return taxonomy


def tag_to_layers_map(taxonomy: dict) -> dict:
    """Invert {layer_id: [tags]} into {tag: [layer_id, ...]}."""
    mapping: dict = defaultdict(list)
    for layer_id, tags in taxonomy.items():
        for tag in tags:
            mapping[tag].append(layer_id)
    return dict(mapping)


def unmapped_tags(entries, tag_map: dict) -> list:
    """Tags used by entries that the taxonomy does not place in any layer."""
    unmapped = set()
    for entry in entries:
        for tag in entry.get("layers") or []:
            if tag not in tag_map:
                unmapped.add(tag)
    return sorted(unmapped)


def build_trading_by_layer(trading_catalog: dict, taxonomy: dict) -> dict:
    tag_map = tag_to_layers_map(taxonomy)
    by_layer = defaultdict(list)
    for entry in trading_catalog["entries"]:
        matched = set()
        for tag in entry.get("layers") or []:
            matched.update(tag_map.get(tag, []))
        for layer_id in matched:
            by_layer[layer_id].append(entry)
    layers = {layer_id: sorted(entries, key=lambda e: e.get("id") or "")
              for layer_id, entries in by_layer.items()}
    # Every taxonomy layer appears even if no entry currently matches it.
    for layer_id in taxonomy:
        layers.setdefault(layer_id, [])
    return {"taxonomy": taxonomy, "layers": {lid: layers[lid] for lid in sorted(layers)}}


# ---------------------------------------------------------------------------
# Beyond the stars: catalogs/us-equities/{star-audit,coverage}.json
# ---------------------------------------------------------------------------

STAR_CANDIDATE_FIELDS = ("repository", "decision", "layers", "role", "rationale", "license")


def build_star_candidates(star_audit: dict, coverage: dict) -> dict:
    star_candidates = [
        {field: entry.get(field) for field in STAR_CANDIDATE_FIELDS}
        for entry in star_audit.get("entries", [])
    ]
    return {
        "star_candidates": star_candidates,
        "beyond_stars": coverage.get("beyond_stars", []),
        "star_count": (star_audit.get("counts") or {}).get("public_stars"),
    }


def build_models(models_doc: dict) -> dict:
    return {"entries": models_doc.get("entries", [])}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=Path, default=Path("."),
                         help="Repository root; all default input paths are relative to this.")
    parser.add_argument("--foundation-manifest", type=Path, default=None)
    parser.add_argument("--foundation-decisions", type=Path, default=None)
    parser.add_argument("--stack", type=Path, default=None)
    parser.add_argument("--us-equities-dir", type=Path, default=None)
    parser.add_argument("--taxonomy-source", type=Path, default=None,
                         help="JSON document with a top-level #/taxonomy mapping.")
    parser.add_argument("--out", type=Path, required=True, help="Output directory for the working files.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    root = args.repo_root
    foundation_manifest = args.foundation_manifest or root / "catalogs/foundation/manifest.json"
    foundation_decisions = args.foundation_decisions or root / "catalogs/foundation/decisions.json"
    stack_path = args.stack or root / "manifests/stack.json"
    us_equities_dir = args.us_equities_dir or root / "catalogs/us-equities"
    taxonomy_source = args.taxonomy_source or root / "catalogs/sota-convergence/manifest-20260922.json"

    manifest = load_json(foundation_manifest)
    decisions_doc = load_json(foundation_decisions)
    stack = load_json(stack_path)
    foundation_layers = build_foundation_layers(manifest, decisions_doc, stack)

    trading_catalog = build_trading_catalog(us_equities_dir)
    taxonomy = load_taxonomy(taxonomy_source)
    trading_by_layer = build_trading_by_layer(trading_catalog, taxonomy)
    unmapped = unmapped_tags(trading_catalog["entries"], tag_to_layers_map(taxonomy))

    star_audit = load_json(us_equities_dir / "star-audit.json")
    coverage = load_json(us_equities_dir / "coverage.json")
    star_candidates = build_star_candidates(star_audit, coverage)

    models_doc = load_json(us_equities_dir / "models.json")
    models_out = build_models(models_doc)

    out = args.out
    write_json(out / "foundation-layers.json", foundation_layers)
    write_json(out / "trading-catalog.json", trading_catalog)
    write_json(out / "trading-by-layer.json", trading_by_layer)
    write_json(out / "star-candidates.json", star_candidates)
    write_json(out / "models.json", models_out)

    print(json.dumps({
        "foundation_layers": len(foundation_layers["layers"]),
        "trading_entries": len(trading_catalog["entries"]),
        "trading_layers": len(trading_by_layer["layers"]),
        "unmapped_tags": unmapped,
        "star_candidates": len(star_candidates["star_candidates"]),
        "beyond_stars": len(star_candidates["beyond_stars"]),
        "models": len(models_out["entries"]),
    }))
    if unmapped:
        print(f"warning: {len(unmapped)} tag(s) have no taxonomy layer: {unmapped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
