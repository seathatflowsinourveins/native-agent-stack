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
  the source records named in TRADING_PIN_SOURCES (trading pins outside the cards)

Outputs (written under --out):
  foundation-layers.json  {checked_at, layers:[{layer_id,title,summary,decisions,components}], top_gaps}
  trading-catalog.json    {entries:[fine-grained entries + catalog_file], layer_index:{tag:[entry ids]}}
  trading-by-layer.json   {taxonomy:{layer_id:[tags]}, layers:{layer_id:[entries]}}
  trading-pins.json       {entries:[{id, layer, repository, pin, pin_source, repository_source}]}
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
# Trading pins that no selected catalog card carries
# ---------------------------------------------------------------------------

# Trading upstreams that a blueprint or runtime record pins but that no
# selected (default/conditional) catalogs/us-equities card carries. The
# card-based trading baseline never reaches them, so without this list
# github_freshness.py would not fetch them and the catalog-freshness report
# would not list them. Each pin (and the repository, where the record carries
# one) is read from its source record at extraction time, never copied here, so
# a pin bump in that record reaches the report without editing this list. A
# pointer that no longer resolves raises (resolve_trading_pins) instead of
# silently dropping the component; tests/test_catalog_freshness_trading.py
# resolves every entry against the checked-in repository.
TRADING_PIN_SOURCES = (
    {
        # Simulation-lane cross-check engine. Its only catalog mention is a
        # backtesting-engine alternative with disposition out_of_scope
        # (catalogs/landscape/us-equities.json); it has no us-equities card.
        "id": "hftbacktest",
        "layer": "backtesting-engine",
        "path": "blueprints/us-equities/sim-crosscheck-hftbacktest/receipt.json",
        "repository_pointer": "/upstream/source_url",
        "pin_pointer": "/upstream/pinned_version",
    },
    {
        # The PyPI TWS API client used by the accepted NautilusTrader IB paper run
        # (runtime-target.json broker_boundaries ibkr python_adapter_paper_evidence).
        # The PyPI project URL is IB's tws-api site, which is not on GitHub. The
        # GitHub source used here is the one named in
        # catalogs/landscape/claude-independent-discovery.json.
        "id": "nautilus-ibapi",
        "layer": "execution-broker",
        "path": "blueprints/us-equities/engine-nautilus/ibkr-paper-orders/evidence/receipt-20260923-passed.json",
        "repository": "https://github.com/nautechsystems/nautilus_ibapi",
        "pin_pointer": "/ibapi_version",
    },
    {
        # The Rust ibapi crate pinned by the selected NautilusTrader 2.0.0rc5 Rust IB
        # adapter. runtime-target.json upstream_ibapi_pin records the upstream
        # fix and pin-update dependency on this crate.
        "id": "rust-ibapi",
        "layer": "execution-broker",
        "path": "catalogs/us-equities/runtime-target.json",
        "repository": "https://github.com/wboayue/rust-ibapi",
        "pin_pointer": "/broker_boundaries/0/upstream_ibapi_pin/rc5_pin",
    },
)


def resolve_json_pointer(doc, pointer: str):
    """RFC 6901 lookup. Raises KeyError when any segment is absent."""
    if pointer == "":
        return doc
    if not pointer.startswith("/"):
        raise KeyError(f"not a JSON pointer: {pointer!r}")
    node = doc
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list) and token.isdigit() and int(token) < len(node):
            node = node[int(token)]
        elif isinstance(node, dict) and token in node:
            node = node[token]
        else:
            raise KeyError(f"{pointer!r} does not resolve at segment {token!r}")
    return node


def _source_file(repo_root: Path, relative: str) -> Path:
    parts = Path(relative).parts
    if Path(relative).is_absolute() or ".." in parts:
        raise ValueError(f"pin source path must be repository-relative: {relative!r}")
    return repo_root / relative


def resolve_trading_pins(repo_root: Path, sources=TRADING_PIN_SOURCES, taxonomy=None,
                         card_ids=()) -> dict:
    """Resolve each declared off-card trading pin against its source record.

    Raises ValueError naming the entry when a source file is missing, a pointer
    does not resolve to a non-empty string, a layer is not a taxonomy layer
    (when ``taxonomy`` is given), or an id collides with a catalog card id or
    another declared pin. Each of these would otherwise drop the component or
    make its report row ambiguous."""
    entries, seen = [], set(card_ids)
    for source in sources:
        entry_id = source["id"]
        if entry_id in seen:
            raise ValueError(f"trading pin id {entry_id!r} duplicates a catalog card or another pin")
        seen.add(entry_id)
        if taxonomy is not None and source["layer"] not in taxonomy:
            raise ValueError(f"trading pin {entry_id!r}: layer {source['layer']!r} is not a taxonomy layer")
        path = _source_file(repo_root, source["path"])
        try:
            doc = load_json(path)
            pin = resolve_json_pointer(doc, source["pin_pointer"])
            repository = (resolve_json_pointer(doc, source["repository_pointer"])
                          if source.get("repository_pointer") else source.get("repository"))
        except (OSError, ValueError, KeyError) as error:
            raise ValueError(f"trading pin {entry_id!r} does not resolve from {source['path']}: {error}") from error
        for field, value in (("pin", pin), ("repository", repository)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"trading pin {entry_id!r}: {field} is not a non-empty string")
        entries.append({
            "id": entry_id,
            "layer": source["layer"],
            "repository": repository,
            "pin": pin,
            "pin_source": {"path": source["path"], "pointer": source["pin_pointer"]},
            "repository_source": ({"path": source["path"], "pointer": source["repository_pointer"]}
                                  if source.get("repository_pointer") else None),
        })
    entries.sort(key=lambda e: e["id"])
    return {"entries": entries}


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
    trading_pins = resolve_trading_pins(
        root, taxonomy=taxonomy, card_ids={entry.get("id") for entry in trading_catalog["entries"]},
    )

    star_audit = load_json(us_equities_dir / "star-audit.json")
    coverage = load_json(us_equities_dir / "coverage.json")
    star_candidates = build_star_candidates(star_audit, coverage)

    models_doc = load_json(us_equities_dir / "models.json")
    models_out = build_models(models_doc)

    out = args.out
    write_json(out / "foundation-layers.json", foundation_layers)
    write_json(out / "trading-catalog.json", trading_catalog)
    write_json(out / "trading-by-layer.json", trading_by_layer)
    write_json(out / "trading-pins.json", trading_pins)
    write_json(out / "star-candidates.json", star_candidates)
    write_json(out / "models.json", models_out)

    print(json.dumps({
        "foundation_layers": len(foundation_layers["layers"]),
        "trading_entries": len(trading_catalog["entries"]),
        "trading_layers": len(trading_by_layer["layers"]),
        "unmapped_tags": unmapped,
        "trading_pins": [entry["id"] for entry in trading_pins["entries"]],
        "star_candidates": len(star_candidates["star_candidates"]),
        "beyond_stars": len(star_candidates["beyond_stars"]),
        "models": len(models_out["entries"]),
    }))
    if unmapped:
        print(f"warning: {len(unmapped)} tag(s) have no taxonomy layer: {unmapped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
