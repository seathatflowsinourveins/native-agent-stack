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
DEFAULT_MANIFEST_RUN_ID = "20260922"


def default_sota_manifest_path(run_id: str) -> str:
    return f"catalogs/sota-convergence/manifest-{run_id}.json"


# Kept as a module-level constant for existing callers/tests; default_sota_manifest_path(DEFAULT_MANIFEST_RUN_ID)
# reproduces the same path. build_all_packets/main take an explicit --manifest override so a later run can join
# a differently-dated manifest without editing this default.
SOTA_MANIFEST_PATH = default_sota_manifest_path(DEFAULT_MANIFEST_RUN_ID)
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
# --trading-candidates manifest: the four domain catalog cards that every trading entry of the
# sota manifest comes from (read in this order; first card holding an id wins).
TRADING_CARD_FILES = (
    "catalogs/us-equities/agents-operations.json", "catalogs/us-equities/data-research.json",
    "catalogs/us-equities/engines-strategies.json", "catalogs/us-equities/foundation-memory.json",
)
CARD_DECISION_ADOPTED = {"default", "conditional"}
# Manifest review labels are not carried in manifest mode: every label value, including
# not_individually_reviewed and unmaintained_signal, correlates with the withheld card
# decision (measured over the 112 2026-09-22 trading entries). pin_behind_upstream stays
# as its own boolean field and the upstream metadata stays.
LAYER_REQUIREMENT_NOTE = ("The requirement, limitations and existing_overturn_when text is shared by this layer's "
                          "group; judge fit against the layer title and layer_scope_terms.")
MANIFEST_CANDIDATE_SOURCE = "sota_manifest_layer_entries"
# --withhold-labels: fields whose values track the withheld v1 disposition (measured over the
# 2026-09-22 foundation packets: candidate review_status confirmed_default and decision selection
# default occur only on selected candidates; decision review_status accepted_within_scope on 105
# selected against 6 others). Evidence prose (evidence_scope, limitations, next_gap) stays.
WITHHELD_DECISION_FIELDS = ("selection", "review_status")
# --withhold-labels also strips popularity and recency signals (2026-09-23 peer audit: the upstream
# record was copied verbatim, so every judge saw GitHub stars and push/release dates, which rank
# candidates by attention rather than by the retained evidence). The explicit keys are the ones
# build_manifest.upstream_record() and the GitHub API emit; any other key naming a count of stars,
# forks, watchers or downloads, or a timestamp (``*_at``), is stripped the same way.
POPULARITY_RECENCY_FIELDS = ("stars", "forks", "watchers", "pushed_at", "released_at")
_POPULARITY_TOKENS = ("star", "fork", "watcher", "subscriber", "download", "popular", "trending")
# Kept only when the packet's requirement text names them (a requirement about licensing or
# maintenance status makes them evidence rather than a popularity proxy).
REQUIREMENT_GATED_FIELDS = {"archived": ("archiv", "maintained", "maintenance"), "license": ("licen",)}
# The packet copies of upstream metadata: each candidate's and each unclaimed sota component's.
UPSTREAM_COPIES = ("candidates", "sota_components_not_in_candidates")


def is_popularity_or_recency_key(key: str) -> bool:
    lowered = key.lower()
    return (lowered in POPULARITY_RECENCY_FIELDS or lowered.endswith("_at")
            or any(token in lowered for token in _POPULARITY_TOKENS))


def requirement_names(field: str, requirement) -> bool:
    text = requirement.lower() if isinstance(requirement, str) else ""
    return any(token in text for token in REQUIREMENT_GATED_FIELDS[field])


def withhold_popularity(packet: dict) -> dict:
    """Strip popularity and recency fields (and archived/license unless the requirement names
    them) from every candidate and sota-component copy in a built packet, and list each stripped
    field in ``withheld``. The canonical fields are always listed, so a reader can tell the
    packet was built under this policy even when no copy carried upstream metadata."""
    requirement = packet.get("requirement")
    gated = [field for field in REQUIREMENT_GATED_FIELDS if not requirement_names(field, requirement)]
    # Labels are relative to one copy: "upstream.<key>" inside the upstream record, "<key>" on the copy itself.
    policy = {f"upstream.{field}" for field in list(POPULARITY_RECENCY_FIELDS) + gated}
    stripped = {collection: set(policy) for collection in UPSTREAM_COPIES}
    for collection in UPSTREAM_COPIES:
        for item in packet.get(collection) or []:
            if not isinstance(item, dict):
                continue
            for key in [key for key in item if key != "upstream" and is_popularity_or_recency_key(key)]:
                del item[key]
                stripped[collection].add(key)
            upstream = item.get("upstream")
            if isinstance(upstream, dict):
                for key in [key for key in upstream if is_popularity_or_recency_key(key) or key in gated]:
                    del upstream[key]
                    stripped[collection].add(f"upstream.{key}")
    withheld = list(packet.get("withheld", []))
    for collection in UPSTREAM_COPIES:
        for label in sorted(f"{collection}[].{key}" for key in stripped[collection]):
            if label not in withheld:
                withheld.append(label)
    packet["withheld"] = withheld
    return packet


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


def trading_cards_by_id(root: Path) -> dict:
    cards = {}
    for relative in TRADING_CARD_FILES:
        for entry in load_json(root / relative).get("entries", []):
            if isinstance(entry, dict) and entry.get("id") and entry["id"] not in cards:
                cards[entry["id"]] = entry
    return cards


def manifest_layer_candidates(layer: dict, cards: dict, ledger_names_by_slug: dict,
                              recipe_map: dict, root: Path) -> list:
    """Layer-specific trading candidates: the sota manifest's own entries for this
    layer (adopted when their card decision is default or conditional), then its
    newcomer candidates and keep-but-compare entries (never adopted). Evidence paths,
    role and limitations come from the entry's domain catalog card; the card's
    rationale and decision are withheld like the ledger's. The manifest id is the
    component id directly, because two entries can share one repository."""
    candidates = []
    for entry in layer.get("entries", []):
        card = cards.get(entry["id"])
        if card is None:
            # A missing card would silently turn an incumbent into a non-adopted candidate.
            raise ValueError(f"manifest trading entry {entry['id']!r} has no domain catalog card")
        repository = entry.get("repository") or card.get("repository")
        evidence_refs = list(card.get("evidence_refs") or [])
        candidates.append({
            "name": ledger_names_by_slug.get(github_repo_slug(repository) if repository else None) or entry["id"],
            "repository": repository,
            "adopted": card.get("decision", entry.get("decision")) in CARD_DECISION_ADOPTED,
            "evidence_kind": card.get("evidence_level"),
            "evidence_refs": evidence_refs,
            "role": card.get("role"),
            "card_limitations": list(card.get("limitations") or []),
            "component_id": entry["id"],
            "pin": entry.get("pin"),
            "upstream": entry.get("upstream"),
            "review_status": None,
            "pin_behind_upstream": entry.get("pin_behind_upstream"),
            "recipe_ref": resolve_recipe_ref(entry["id"], recipe_map, evidence_refs, root),
            "decisions": [],
        })
    seen = {github_repo_slug(c["repository"]) for c in candidates if c["repository"]}
    for item in list(layer.get("candidates", [])) + list(layer.get("alternatives_keep_but_compare", [])):
        repository = item.get("repository")
        slug = github_repo_slug(repository) if repository else None
        if not slug or slug in seen:
            continue
        seen.add(slug)
        candidates.append({
            "name": item.get("name") or item.get("id") or slug, "repository": repository, "adopted": False,
            "evidence_kind": None, "evidence_refs": [], "role": None,
            "card_limitations": [], "component_id": None, "pin": None, "upstream": None,
            "review_status": None, "pin_behind_upstream": None, "newcomer": True,
            "recipe_ref": None, "decisions": [],
            "note": item.get("demonstrated_gap") or item.get("comparison_that_would_overturn"),
        })
    return candidates


def build_packet(row: dict, *, catalog: str, sota_components: list, recipe_map: dict,
                  decisions_by_component: dict, seed: str, checked_at: str, root: Path, rules: list,
                  catalog_components: list = None, layer_candidates: list = None,
                  layer_scope_terms: list = None) -> dict:
    """``sota_components`` is the manifest slice for this ledger layer (it feeds
    ``sota_components_not_in_candidates``); the candidate join runs by repository
    slug against the layer slice first and then the whole catalog
    (``catalog_components``), because the 2026-09-22 manifest still carries the
    16-layer foundation taxonomy while the ledger is frozen at 20 layers, so a
    candidate's manifest component can sit under another layer id. The other
    catalog is never consulted."""
    layer_id = row["layer_id"]
    if layer_candidates is not None:
        # --trading-candidates manifest: candidates were built from the manifest's own
        # layer entries; keys follow the same seeded order as the ledger path.
        ordered = list(layer_candidates)
        make_rng(seed, catalog, layer_id).shuffle(ordered)
        candidates = [{"key": f"c{index}", **candidate} for index, candidate in enumerate(ordered, start=1)]
    else:
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
    packet = {
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
    if layer_candidates is not None:
        # Only added in manifest mode, so ledger-mode packets stay byte-identical.
        packet["candidate_source"] = MANIFEST_CANDIDATE_SOURCE
        packet["layer_scope_terms"] = list(layer_scope_terms or [])
        packet["requirement_note"] = LAYER_REQUIREMENT_NOTE
        packet["withheld"] = list(WITHHELD) + ["candidates[].card_rationale", "candidates[].card_decision",
                                              "candidates[].review_status"]
    return packet


def serialize(document: dict) -> str:
    sanitized = sanitize_value(document)
    text = json.dumps(sanitized, indent=1, sort_keys=True)
    json.loads(text)  # prove the sanitized result is still valid JSON before the leak check
    assert_no_leak(text)
    return text + "\n"


def packet_filename(catalog: str, layer_id: str) -> str:
    return f"{catalog}__{layer_id}.json"


def withhold_labels(packet: dict) -> dict:
    """Drop decision-bearing labels from a built packet (candidate review_status and the
    attached decisions' selection and review_status) and record what was withheld."""
    for candidate in packet.get("candidates", []):
        candidate["review_status"] = None
        candidate["decisions"] = [{key: value for key, value in decision.items() if key not in WITHHELD_DECISION_FIELDS}
                                  for decision in candidate.get("decisions") or []]
    for component in packet.get("sota_components_not_in_candidates", []):
        component["review_status"] = None
    withheld = list(packet.get("withheld", []))
    for label in ("candidates[].review_status", "candidates[].decisions[].selection",
                  "candidates[].decisions[].review_status", "sota_components_not_in_candidates[].review_status"):
        if label not in withheld:
            withheld.append(label)
    packet["withheld"] = withheld
    return packet


def build_all_packets(root: Path, *, catalogs: list, seed: str, checked_at: str,
                      trading_candidates: str = "ledger", withhold: bool = False,
                      manifest: str = None) -> dict:
    """Returns {filename: serialized packet text}, fully built and leak-
    checked in memory before any file is written. ``manifest`` overrides the
    dated sota manifest joined in (default reproduces the 2026-09-22
    packets); pass the same value used for build_verdicts.py's --manifest so
    the packets and the verdict catalog agree on the pins."""
    rules = load_rules()
    sota_doc = load_json(root / (manifest or SOTA_MANIFEST_PATH))
    sota_index = sota_layer_index(sota_doc)
    recipe_map = load_json(root / ADOPTION_MANIFEST_PATH).get("recipe_map", {})
    decisions_doc = load_json(root / FOUNDATION_DECISIONS_PATH)
    decisions_by_component = foundation_decisions_by_component(decisions_doc)
    manifest_mode = trading_candidates == "manifest"
    cards = trading_cards_by_id(root) if manifest_mode else {}
    trading_layers = {layer["layer"]: layer for layer in sota_doc.get("trading", [])}

    packets = {}
    for catalog in catalogs:
        ledger = load_json(root / LEDGER_FILES[catalog])
        for row in ledger.get("layers", []):
            layer_candidates = None
            if manifest_mode and catalog == "us-equities":
                names = {github_repo_slug(c["repository"]): c.get("name")
                         for c in row.get("candidates") or [] if c.get("repository")}
                layer_candidates = manifest_layer_candidates(
                    trading_layers.get(row["layer_id"], {}), cards, names, recipe_map, root)
            packet = build_packet(
                row, catalog=catalog, sota_components=sota_index.get((catalog, row["layer_id"]), []),
                catalog_components=catalog_components(sota_index, catalog),
                recipe_map=recipe_map, decisions_by_component=decisions_by_component,
                seed=seed, checked_at=checked_at, root=root, rules=rules, layer_candidates=layer_candidates,
                layer_scope_terms=(sota_doc.get("taxonomy") or {}).get(row["layer_id"]) if layer_candidates is not None
                else None,
            )
            if withhold and layer_candidates is None:
                # Manifest-mode trading packets already carry no decision labels.
                packet = withhold_labels(packet)
            if withhold:
                # Every packet, manifest-mode trading packets included, loses popularity and
                # recency signals; the default (no --withhold-labels) build is unchanged.
                packet = withhold_popularity(packet)
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
    parser.add_argument("--manifest", type=Path, default=None,
                        help="Override the dated sota manifest joined in (default "
                             "catalogs/sota-convergence/manifest-20260922.json, reproducing the 2026-09-22 "
                             "packets). Pass the same --manifest given to build_verdicts.py for the same run "
                             "so packets and verdicts agree on the pins.")
    parser.add_argument("--withhold-labels", action="store_true",
                        help="Drop decision-bearing labels (candidate and SOTA-component review_status, decision "
                             "selection and review_status) from every ledger-built packet, and popularity/recency "
                             "fields (stars, forks, watchers, pushed_at, released_at, any *_at; archived and "
                             "license unless the requirement names them) from every candidate and component copy "
                             "of every packet; each stripped field is listed in the packet's withheld list. Off by "
                             "default so the 2026-09-22 packets reproduce.")
    parser.add_argument("--trading-candidates", choices=("ledger", "manifest"), default="ledger",
                        help="Candidate source for us-equities packets: the ledger row's group-wide list "
                             "(default; reproduces the 2026-09-22 packets) or the sota manifest's own entries "
                             "for the layer, with evidence from their domain catalog cards.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    catalogs = [args.catalog] if args.catalog else sorted(LEDGER_FILES)

    packets = build_all_packets(root, catalogs=catalogs, seed=str(args.seed), checked_at=args.checked_at,
                                trading_candidates=args.trading_candidates, withhold=args.withhold_labels,
                                manifest=str(args.manifest) if args.manifest else None)

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
