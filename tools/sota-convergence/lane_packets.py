#!/usr/bin/env python3
"""Build the per-layer lane packets for the 2026-09-22 layer-verdict
convergence (PR-5, "packets" unit): one JSON packet per
``(catalog, layer_id)`` row of the landscape ledger, written to
``<work_dir>/packets/<catalog>__<layer_id>.json``, plus a
``<work_dir>/packets/SHA256SUMS`` (``sha256sum`` format, filenames only).

No network access; every input is a repository-relative file already checked
into ``catalogs/`` and ``adoption/``. This tool never calls a model, never
picks a winner and never runs a lane -- it only assembles the retained
evidence a lane is allowed to see and withholds the incumbent's own verdict
(``current_choice``, ``decision``, the layer-level ``rationale`` and each
candidate's ``disposition``/``rationale``), so a lane argues from evidence
rather than copying the existing selection.

Candidate-to-manifest matching is by normalized GitHub slug (lowercase
``owner/repo``, ``.git``/``/tree/...``/``/releases/tag/...`` stripped --
``build_manifest.github_repo_slug``); a candidate without a ``repository`` or
whose repository is not a GitHub URL never matches. ``recipe_ref`` prefers
``adoption/manifest.json``'s ``recipe_map`` keyed by the matched
``component_id``, else the first of the candidate's own ``evidence_refs``
that resolves to a real path under ``--root`` (``scripts/catalog_decisions
.safe_file`` keeps that resolution confined to the repository), else
``null``.

Every packet is sanitized (``build_manifest.sanitize_value``) and leak-
checked (``build_manifest.assert_no_leak``) before anything is written; a
host path or a known secret-prefix marker surviving sanitization aborts the
whole run -- no packet is written, matching ``build_verdicts.py``'s
all-or-nothing write discipline.

Deterministic output: each packet is ``json.dumps(..., sort_keys=True,
indent=1)`` plus a trailing newline; the candidate order within a packet is
shuffled with ``random.Random`` seeded from
``sha256(f"{seed}{catalog}{layer_id}")`` (same seed material -> same order,
so both lanes see identical candidate positions and neither reads a
first-listed-wins signal from this generator).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
# assert_no_leak/sanitize_value/github_repo_slug are reused (not
# reimplemented) from build_manifest.py, which owns the host-path/secret-
# marker leak contract and the GitHub-slug normalization for every generator
# under tools/sota-convergence/.
from build_manifest import assert_no_leak, github_repo_slug, sanitize_value  # noqa: E402
# DISPOSITIONS/WINNER_EVIDENCE_CLASSES are reused (not reimplemented) from
# scripts/landscape.py, the single owner of these enums.
from scripts.landscape import DISPOSITIONS, WINNER_EVIDENCE_CLASSES  # noqa: E402
from scripts.catalog_decisions import InvalidDecisionIndex, safe_file  # noqa: E402

LEDGER_FILES = {
    "foundation": "catalogs/landscape/foundation.json",
    "us-equities": "catalogs/landscape/us-equities.json",
}
SOTA_MANIFEST_PATH = "catalogs/sota-convergence/manifest-20260922.json"
ADOPTION_MANIFEST_PATH = "adoption/manifest.json"
FOUNDATION_DECISIONS_PATH = "catalogs/foundation/decisions.json"
PACKET_SCHEMA_VERSION = 1
DEFAULT_SEED = "20260922"
DEFAULT_CHECKED_AT = "2026-09-22"
WITHHELD = ["current_choice", "decision", "rationale", "candidates[].disposition", "candidates[].rationale"]
# Fields republished verbatim from a matched sota-convergence manifest
# component/entry (or from an unmatched one, in
# sota_components_not_in_candidates).
MANIFEST_FIELDS = ("repository", "pin", "upstream", "review_status", "pin_behind_upstream")
DECISION_FIELDS = ("id", "capability", "selection", "review_status", "evidence_scope", "limitations", "next_gap")

RULE_ITEM_RE = re.compile(r"\n(?=\d+\.\s)")
RULE_PREFIX_RE = re.compile(r"^\d+\.\s*")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_rules(prompt_path: Path = HERE / "lane-prompt.md") -> list:
    """Parse the five numbered rules out of lane-prompt.md's own "Rules"
    section, de-wrapping each item's continuation lines into one string, so
    the packet's ``rules`` field is always exactly what the prompt file
    itself says -- never a second, independently maintained copy that could
    drift from it."""
    text = prompt_path.read_text(encoding="utf-8")
    match = re.search(r"\nRules\n(.*)\Z", text, re.S)
    if not match:
        raise ValueError(f"{prompt_path} has no 'Rules' section to parse")
    body = match.group(1).strip("\n")
    items = RULE_ITEM_RE.split(body)
    rules = []
    for item in items:
        item = RULE_PREFIX_RE.sub("", item)
        lines = [line.strip() for line in item.splitlines() if line.strip()]
        rules.append(" ".join(lines))
    if len(rules) != 5:
        raise ValueError(f"{prompt_path} must have exactly five numbered rules, found {len(rules)}")
    return rules


def sota_layer_index(sota_doc: dict) -> dict:
    """(catalog, layer_id) -> [{id, repository, pin, upstream, review_status,
    pin_behind_upstream}, ...], joined from the sota manifest's foundation[]
    .components and trading[].entries. Keyed by (catalog, layer_id) rather
    than layer_id alone: the manifest's two taxonomies (foundation[] and
    trading[], the latter feeding the "us-equities" ledger catalog) are
    independent namespaces, and a layer id that happened to appear in both
    must never let one catalog's components leak into the other's packet."""
    index = {}
    for row in sota_doc.get("foundation", []):
        index[("foundation", row["layer"])] = [
            {"id": component["id"], **{field: component.get(field) for field in MANIFEST_FIELDS}}
            for component in row.get("components", [])
        ]
    for row in sota_doc.get("trading", []):
        index[("us-equities", row["layer"])] = [
            {"id": entry["id"], **{field: entry.get(field) for field in MANIFEST_FIELDS}}
            for entry in row.get("entries", [])
        ]
    return index


def catalog_components(sota_index: dict, catalog: str) -> list:
    """Every manifest component of one catalog, all layers, in deterministic
    (layer id, manifest order) order; the other catalog is excluded."""
    return [component for (index_catalog, _layer), components in sorted(sota_index.items())
            if index_catalog == catalog for component in components]


def manifest_index_by_slug(components: list) -> dict:
    """repository-slug -> component record, first-seen wins (deterministic
    for a fixed input list). Components without a GitHub repository are
    simply absent -- they can still appear in
    sota_components_not_in_candidates, they just can never be the target of
    a candidate match."""
    index = {}
    for component in components:
        slug = github_repo_slug(component.get("repository"))
        if slug and slug not in index:
            index[slug] = component
    return index


def foundation_decisions_by_component(decisions_doc: dict) -> dict:
    """component_id -> [decision (DECISION_FIELDS only), ...], sorted by id
    for deterministic output. A decision touches a component whenever that
    component_id appears anywhere in its component_ids list."""
    by_component: dict = {}
    for decision in decisions_doc.get("decisions", []):
        trimmed = {field: decision.get(field) for field in DECISION_FIELDS}
        for component_id in decision.get("component_ids", []) or []:
            by_component.setdefault(component_id, []).append(trimmed)
    for component_id, rows in by_component.items():
        rows.sort(key=lambda row: row["id"])
    return by_component


def make_rng(seed: str, catalog: str, layer_id: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}{catalog}{layer_id}".encode("utf-8")).hexdigest()
    return random.Random(int(digest, 16))


def resolve_recipe_ref(component_id, recipe_map: dict, evidence_refs: list, root: Path):
    if component_id and component_id in recipe_map:
        return recipe_map[component_id]
    for ref in evidence_refs:
        try:
            path = safe_file(root, ref)
        except (InvalidDecisionIndex, ValueError):
            continue
        if path.exists():
            return ref
    return None


def build_candidate(key: str, v1_candidate: dict, *, slug_index: dict, recipe_map: dict,
                     decisions_by_component: dict, root: Path) -> dict:
    repository = v1_candidate.get("repository")
    slug = github_repo_slug(repository) if repository else None
    manifest_component = slug_index.get(slug) if slug else None
    component_id = manifest_component["id"] if manifest_component else None
    evidence_refs = list(v1_candidate.get("evidence_refs") or [])
    return {
        "key": key,
        "name": v1_candidate.get("name"),
        "repository": repository,
        "adopted": v1_candidate.get("disposition") in {"selected", "conditional"},
        "evidence_kind": v1_candidate.get("evidence_kind"),
        "evidence_refs": evidence_refs,
        "component_id": component_id,
        "pin": manifest_component.get("pin") if manifest_component else None,
        "upstream": manifest_component.get("upstream") if manifest_component else None,
        "review_status": manifest_component.get("review_status") if manifest_component else None,
        "pin_behind_upstream": manifest_component.get("pin_behind_upstream") if manifest_component else None,
        "recipe_ref": resolve_recipe_ref(component_id, recipe_map, evidence_refs, root),
        "decisions": decisions_by_component.get(component_id, []) if component_id else [],
    }


def build_packet(row: dict, *, catalog: str, sota_components: list, recipe_map: dict,
                  decisions_by_component: dict, seed: str, checked_at: str, root: Path, rules: list,
                  catalog_components: list = None) -> dict:
    """``sota_components`` is the manifest slice for this ledger layer (it feeds
    ``sota_components_not_in_candidates``); the candidate join runs by repository
    slug against the layer slice first and then the whole catalog
    (``catalog_components``), because the 2026-09-22 manifest still carries the
    16-layer foundation taxonomy while the ledger is frozen at 20 layers, so a
    candidate's manifest component can sit under another layer id. The other
    catalog is never consulted."""
    layer_id = row["layer_id"]
    slug_index = manifest_index_by_slug(list(sota_components) + list(catalog_components or []))
    ordered = list(row.get("candidates") or [])
    make_rng(seed, catalog, layer_id).shuffle(ordered)
    candidates = [
        build_candidate(f"c{index}", candidate, slug_index=slug_index, recipe_map=recipe_map,
                         decisions_by_component=decisions_by_component if catalog == "foundation" else {},
                         root=root)
        for index, candidate in enumerate(ordered, start=1)
    ]
    matched_ids = {candidate["component_id"] for candidate in candidates if candidate["component_id"]}
    unmatched = [
        {"id": component["id"], **{field: component.get(field) for field in MANIFEST_FIELDS}}
        for component in sota_components if component["id"] not in matched_ids
    ]
    return {
        "schema_version": PACKET_SCHEMA_VERSION,
        "catalog": catalog,
        "layer_id": layer_id,
        "title": row.get("title"),
        "group": row.get("group"),
        "checked_at": checked_at,
        "requirement": row.get("requirement"),
        "limitations": row.get("limitations"),
        "existing_overturn_when": row.get("overturn_when"),
        "candidates": candidates,
        "sota_components_not_in_candidates": unmatched,
        "enums": {"evidence_class": sorted(WINNER_EVIDENCE_CLASSES), "disposition": sorted(DISPOSITIONS)},
        "withheld": list(WITHHELD),
        "rules": rules,
    }


def serialize(document: dict) -> str:
    sanitized = sanitize_value(document)
    text = json.dumps(sanitized, indent=1, sort_keys=True)
    json.loads(text)  # prove the sanitized result is still valid JSON before the leak check
    assert_no_leak(text)
    return text + "\n"


def packet_filename(catalog: str, layer_id: str) -> str:
    return f"{catalog}__{layer_id}.json"


def build_all_packets(root: Path, *, catalogs: list, seed: str, checked_at: str) -> dict:
    """Returns {filename: serialized packet text}, fully built and leak-
    checked in memory before any file is written."""
    rules = load_rules()
    sota_doc = load_json(root / SOTA_MANIFEST_PATH)
    sota_index = sota_layer_index(sota_doc)
    recipe_map = load_json(root / ADOPTION_MANIFEST_PATH).get("recipe_map", {})
    decisions_doc = load_json(root / FOUNDATION_DECISIONS_PATH)
    decisions_by_component = foundation_decisions_by_component(decisions_doc)

    packets = {}
    for catalog in catalogs:
        ledger = load_json(root / LEDGER_FILES[catalog])
        for row in ledger.get("layers", []):
            packet = build_packet(
                row, catalog=catalog, sota_components=sota_index.get((catalog, row["layer_id"]), []),
                catalog_components=catalog_components(sota_index, catalog),
                recipe_map=recipe_map, decisions_by_component=decisions_by_component,
                seed=seed, checked_at=checked_at, root=root, rules=rules,
            )
            packets[packet_filename(catalog, row["layer_id"])] = serialize(packet)
    return packets


def sha256sums(packets: dict) -> str:
    lines = [f"{hashlib.sha256(text.encode('utf-8')).hexdigest()}  {name}\n"
              for name, text in sorted(packets.items())]
    return "".join(lines)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--catalog", choices=sorted(LEDGER_FILES), default=None,
                         help="Build packets for one catalog only; default builds both.")
    parser.add_argument("--checked-at", default=DEFAULT_CHECKED_AT)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    catalogs = [args.catalog] if args.catalog else sorted(LEDGER_FILES)

    packets = build_all_packets(root, catalogs=catalogs, seed=str(args.seed), checked_at=args.checked_at)

    out_dir = args.out / "packets"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in packets.items():
        (out_dir / name).write_text(text, encoding="utf-8")
    (out_dir / "SHA256SUMS").write_text(sha256sums(packets), encoding="utf-8")

    unmatched_counts = {}
    for name, text in packets.items():
        document = json.loads(text)
        count = len(document["sota_components_not_in_candidates"])
        if count:
            unmatched_counts[name] = count

    # The written packets are sanitized/leak-checked artifacts (serialize()),
    # but this status line is a run log, not a committed artifact -- redact
    # any host-path fragment in the reported --out path the same way, so a
    # leak marker never reaches stdout either.
    print(json.dumps({
        "status": "written", "packet_count": len(packets), "out_dir": sanitize_value(str(out_dir)),
        "unmatched_sota_components": unmatched_counts,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
