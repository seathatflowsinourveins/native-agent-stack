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
import os
import posixpath
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
# The withheld-key policy is shared with scripts/landscape.py, which re-checks every packet a new
# wave retains (evidence/artifacts/layer-verdicts-<run-id>/packets/) against it in CI.
from scripts.landscape import (  # noqa: E402
    COPY_WITHHELD_FIELDS, PACKET_KEYS_SCHEMA_VERSION, POPULARITY_TOKENS, REQUIREMENT_GATED_FIELDS,
    SEALED_CANDIDATE_FIELDS, SEALED_COMMITMENT_KEY, WITHHELD_CANDIDATE_LABELS, is_withheld_packet_key,
    requirement_names, sealed_candidates_sha256,
    sealed_candidate_labels, withheld_candidate_label_labels, withheld_packet_keys, withhold_policy_labels,
)
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
EVIDENCE_MANIFEST_PATH = "manifests/evidence.json"
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
# decision (measured over the 112 2026-09-22 trading entries). Outside --withhold-labels,
# pin_behind_upstream stays as its own boolean field and the upstream metadata stays.
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
# The latest upstream release is withheld entirely (re-review 2026-09-23): a date-based tag such as
# inspect_ai's "release/2025-11-28" carries a release date. Withholding it always is the stricter
# of the two options considered (the other stripped it only when date-shaped) and no packet
# requirement names releases, versions or maintenance. prerelease describes that same release, and
# pin_behind_upstream is derived by comparing the pin with it, so both go with it.
# newcomer marks a candidate as recently discovered, a recency signal of the same kind (final
# verification, 2026-09-23), so it is withheld with them. The candidate-only note (a newcomer's
# demonstrated_gap or a keep-but-compare entry's overturn comparison) exists only on non-adopted
# candidates, so it hints at their status too and is withheld as well (review of #122, finding 9).
COPY_RELEASE_FIELDS = COPY_WITHHELD_FIELDS
_POPULARITY_TOKENS = POPULARITY_TOKENS
# archived/license are kept only when the packet's requirement text names them (a requirement about
# licensing or maintenance status makes them evidence rather than a popularity proxy):
# scripts/landscape.py REQUIREMENT_GATED_FIELDS and requirement_names.
# The review of the #122 fix round made the strip recursive, sharing scripts/landscape.py
# is_withheld_packet_key with the CI check: a withheld key is removed at any depth of a copy (for
# example upstream.latest_flag, whose tag-listing fallback can be date-shaped such as
# "release/2025-11-28", or a nested evidence.stars), not only on the copy and its upstream record.
# The packet copies of upstream metadata: each candidate's and each unclaimed sota component's.
UPSTREAM_COPIES = ("candidates", "sota_components_not_in_candidates")


def withhold_popularity(packet: dict) -> dict:
    """Strip popularity and recency fields, the latest upstream release and what is derived from it
    (and archived/license unless the requirement names them) at any depth of every candidate and
    sota-component copy in a built packet, and list each stripped field in ``withheld``. The
    canonical fields are always listed, so a reader can tell the packet was built under this policy
    even when no copy carried upstream metadata."""
    requirement = packet.get("requirement")
    kept_gated = {field for field in REQUIREMENT_GATED_FIELDS if requirement_names(field, requirement)}
    labels = set(withhold_policy_labels(requirement))

    def strip(value, label):
        # Rebuild rather than delete in place: build_candidate and the unclaimed list share the loaded
        # manifest's upstream record across packets, so an earlier packet must not remove a field a
        # later packet's requirement keeps.
        if isinstance(value, dict):
            kept = {}
            for key, item in value.items():
                if is_withheld_packet_key(key, kept_gated):
                    labels.add(f"{label}.{key}")
                else:
                    kept[key] = strip(item, f"{label}.{key}")
            return kept
        if isinstance(value, list):
            return [strip(item, label) for item in value]
        return value

    for collection in UPSTREAM_COPIES:
        if isinstance(packet.get(collection), list):
            packet[collection] = [strip(item, f"{collection}[]") if isinstance(item, dict) else item
                                  for item in packet[collection]]
    withheld = list(packet.get("withheld", []))
    for label in sorted(labels):
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
                              recipe_map: dict, root: Path, evidence_files: dict = None,
                              withhold: bool = False) -> list:
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
    for newcomer in manifest_newcomers(layer, seen, evidence_files, root, withhold):
        candidates.append({**newcomer, "role": None, "card_limitations": []})
    return candidates


# --manifest-newcomers (2026-09-23 landscape sweep): a manifest candidate whose discovery was refuted is not
# carried, and a newcomer's evidence_refs are the repository-relative evidence/ paths its manifest evidence[]
# lists that manifests/evidence.json registers in files[] with the file's current sha256.
REFUTED_DISPOSITION_PREFIX = "refuted_"


def registered_evidence_files(root: Path) -> dict:
    """Repository-relative path -> sha256 for every file manifests/evidence.json lists in files[]."""
    return {entry["path"]: entry.get("sha256") for entry in load_json(root / EVIDENCE_MANIFEST_PATH).get("files") or []
            if isinstance(entry, dict) and isinstance(entry.get("path"), str)}


def newcomer_evidence_refs(item: dict, evidence_files: dict, root: Path, withhold: bool) -> list:
    """The evidence[] strings that are exactly a registered, unchanged evidence/ file. Command/result prose,
    a path with a suffix such as "(lines 1-9)", an unregistered or edited file, and (under ``withhold``) a
    path naming a selection role are left out."""
    refs = []
    for value in item.get("evidence") or []:
        if (not isinstance(value, str) or not value.startswith("evidence/") or posixpath.normpath(value) != value
                or value in refs or value not in evidence_files):
            continue
        path = root / value
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != evidence_files[value]:
            continue
        if withhold and LABEL_BEARING_RECEIPT.search(value):
            continue
        refs.append(value)
    return refs


def manifest_newcomers(layer: dict, seen: set, evidence_files: dict = None, root: Path = None,
                       withhold: bool = False) -> list:
    """Candidate records for a manifest layer's candidates and keep-but-compare alternatives whose repository
    slug is not in ``seen`` (updated; first seen wins). Without ``evidence_files`` (the default build) every
    such item is carried with no evidence_refs, as the 2026-09-22 packets were; with it (--manifest-newcomers),
    a refuted discovery is left out and the registered evidence files are attached."""
    newcomers = []
    items = list(layer.get("candidates", [])) + list(layer.get("alternatives_keep_but_compare", []))
    # A refuted_* disposition is the outcome of a discovery proposal, not a judgment of the repository: the
    # 2026-09-23 refutations of ledger candidates say "not new to the catalog" or "already conditional"
    # (anthropics/skills, inspect_ai, mise, claude-agent-sdk-python). So it only withholds a newcomer
    # addition; a ledger candidate (``seen``) keeps its place and its own evidence (Codex review of #151).
    # A repository refuted in any of its entries is left out entirely, even where another list repeats it
    # without a disposition.
    refuted = {github_repo_slug(item["repository"]) for item in items if item.get("repository")
               and str(item.get("disposition") or "").startswith(REFUTED_DISPOSITION_PREFIX)}
    for item in items:
        repository = item.get("repository")
        slug = github_repo_slug(repository) if repository else None
        if not slug or slug in seen or (evidence_files is not None and slug in refuted):
            continue
        seen.add(slug)
        newcomers.append({
            "name": item.get("name") or item.get("id") or slug, "repository": repository, "adopted": False,
            "evidence_kind": None,
            "evidence_refs": newcomer_evidence_refs(item, evidence_files, root, withhold)
            if evidence_files is not None else [],
            "component_id": None, "pin": None, "upstream": None,
            "review_status": None, "pin_behind_upstream": None, "newcomer": True,
            "recipe_ref": None, "decisions": [],
            "note": item.get("demonstrated_gap") or item.get("comparison_that_would_overturn"),
        })
    return newcomers


# Marks a newcomer record inside build_packet's shuffled list (a ledger candidate never has this key).
NEWCOMER_SLOT = "__manifest_newcomer__"


def build_packet(row: dict, *, catalog: str, sota_components: list, recipe_map: dict,
                  decisions_by_component: dict, seed: str, checked_at: str, root: Path, rules: list,
                  catalog_components: list = None, layer_candidates: list = None,
                  layer_scope_terms: list = None, newcomers: list = None) -> dict:
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
        # --manifest-newcomers: newcomers are shuffled together with the ledger candidates, so a key's
        # position does not tell them apart. Without newcomers the order is the 2026-09-22 one.
        ordered = list(row.get("candidates") or []) + [{NEWCOMER_SLOT: newcomer} for newcomer in newcomers or []]
        make_rng(seed, catalog, layer_id).shuffle(ordered)
        candidates = [
            {"key": f"c{index}", **candidate[NEWCOMER_SLOT]} if NEWCOMER_SLOT in candidate else
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


STACK_MANIFEST_PATH = "manifests/stack.json"
RECEIPT_ALIASES_PATH = "tools/sota-convergence/receipt-component-aliases.json"


def registered_receipts_index(root: Path, sota_doc: dict) -> dict:
    """The receipts manifests/evidence.json registers (the list scripts/platform_status.py and
    component_matrix.py read), indexed two ways for ``receipts_for``:

    - ``by_id``: receipt component id -> [{id, kind, path}].
    - ``by_repository``: repository slug -> {"stack_id", "entries"}, only for a slug exactly one
      manifests/stack.json component uses; ``entries`` are that component's receipts.
    - ``sota_ids_by_repository``: repository slug -> the sota manifest component ids (both catalogs) using it.

    Receipts name components in the manifests/stack.json id space, which differs from the sota manifest's
    for some components (``nautilus-trader`` there, ``nautilustrader`` here; ``duckdb``/``data-duckdb``), so a
    repository match can reach a receipt an id match misses. It must not reach another component that
    shares the repository (PR #142 re-review): ``nautilus-ibkr-adapter`` shares NautilusTrader's repository
    and ``codex-native-sdk`` shares the Codex CLI's."""
    stack_ids_by_slug: dict = {}
    for component in load_json(root / STACK_MANIFEST_PATH).get("components") or []:
        slug = github_repo_slug(component.get("repository") or "")
        if slug:
            stack_ids_by_slug.setdefault(slug, set()).add(component["id"])
    unique_stack = {slug: next(iter(ids)) for slug, ids in stack_ids_by_slug.items() if len(ids) == 1}
    sota_ids_by_slug: dict = {}
    for components in sota_layer_index(sota_doc).values():
        for component in components:
            slug = github_repo_slug(component.get("repository") or "")
            if slug:
                sota_ids_by_slug.setdefault(slug, set()).add(component["id"])
    stack_slug = {stack_id: slug for slug, ids in stack_ids_by_slug.items() for stack_id in ids}
    sota_slug = {sota_id: slug for slug, ids in sota_ids_by_slug.items() for sota_id in ids}
    aliases_path = root / RECEIPT_ALIASES_PATH
    aliases = (load_json(aliases_path).get("aliases") or {}) if aliases_path.is_file() else {}
    for stack_id, sota_id in aliases.items():
        # An alias is only a respelling: both ids must name one repository, or it would move a receipt to
        # a different component.
        if stack_slug.get(stack_id) is None or stack_slug.get(stack_id) != sota_slug.get(sota_id):
            raise ValueError(f"{RECEIPT_ALIASES_PATH}: {stack_id} -> {sota_id} do not share one repository")
    by_id: dict = {}
    by_alias: dict = {}
    for receipt in load_json(root / EVIDENCE_MANIFEST_PATH).get("receipts") or []:
        entry = {"id": receipt["id"], "kind": receipt["kind"], "path": receipt["path"]}
        for component_id in receipt.get("component_ids") or []:
            by_id.setdefault(component_id, []).append(entry)
            if component_id in aliases:
                by_alias.setdefault(aliases[component_id], []).append(entry)
    by_repository = {slug: {"stack_id": stack_id, "entries": by_id[stack_id]}
                     for slug, stack_id in unique_stack.items() if stack_id in by_id}
    return {"by_id": by_id, "by_alias": by_alias, "by_repository": by_repository,
            "sota_ids_by_repository": sota_ids_by_slug}


def receipts_for(item: dict, component_id, index: dict, withhold: bool = False) -> list:
    """Receipts for one candidate or component, sorted by path, each marked ``matched_by``.

    ``component_id``: every receipt that names the component's own id. ``alias``: every receipt naming the
    manifests/stack.json id that receipt-component-aliases.json maps to this id. ``repository``: used only when
    (a) the own id matches no receipt, (b) exactly one manifests/stack.json component uses the item's
    repository slug and the receipt names that component, and (c) no other sota manifest component id, in
    either catalog, uses that slug. Otherwise nothing is attached by repository. Under ``withhold`` the
    receipt id is dropped: ids such as ``native-session-defaults-20260920`` can name the incumbent's role."""
    own = index["by_id"].get(component_id, []) if component_id else []
    matched = [(entry, "component_id") for entry in own]
    seen = {entry["path"] for entry in own}
    aliased = [entry for entry in index.get("by_alias", {}).get(component_id, []) if entry["path"] not in seen]
    matched += [(entry, "alias") for entry in aliased]
    own = own + aliased
    slug = github_repo_slug(item.get("repository") or "")
    if not own and slug and slug in index["by_repository"]:
        other_ids = index["sota_ids_by_repository"].get(slug, set()) - {component_id}
        if not other_ids:
            matched = [(entry, "repository") for entry in index["by_repository"][slug]["entries"]]
    result = []
    for entry, matched_by in sorted(matched, key=lambda pair: pair[0]["path"]):
        if withhold and label_bearing_receipt(entry):
            # The path would carry what the withheld id carried (Codex review of #145): left out of a blind
            # packet; attach_registered_receipts counts it in the packet's withheld list.
            continue
        # matched_by component_id or alias exists only for a manifest component, so a blind packet drops it
        # with the other membership fields (review of #145; scripts/landscape.py SEALED_CANDIDATE_FIELDS).
        result.append({"kind": entry["kind"], "path": entry["path"]} if withhold
                      else {**entry, "matched_by": matched_by})
    return result


# A receipt id or file name that names a selection role (for example native-session-defaults-20260920,
# adoption/receipt.json) repeats the incumbent label the blind packet withholds. The manifest disposition
# vocabulary counts too (Codex review of #151): a path such as keep-but-compare.json or
# refuted-targeted-candidate.json names the label as plainly. "candidate" alone is not a label: every packet
# entry is one. None of the 142 receipts registered on 2026-09-23 matches the added terms.
LABEL_BEARING_RECEIPT = re.compile(r"default|adopt|select|winner|incumbent|chosen|retain|refut"
                                   r"|keep[-_ ]?but[-_ ]?compare|targeted[-_ ]?candidate|newcomer|discovered"
                                   r"|reject|demot|disposition", re.I)


def label_bearing_receipt(entry: dict) -> bool:
    return bool(LABEL_BEARING_RECEIPT.search(entry.get("id") or "")
                or LABEL_BEARING_RECEIPT.search(entry.get("path") or ""))


REGISTERED_RECEIPTS_NOTE = ("registered_receipts lists the receipts manifests/evidence.json registers for a "
                            "candidate's component: matched_by component_id when the receipt names its id, alias when it names "
                            "the same component under its manifests/stack.json spelling, "
                            "repository when the receipt names the only registered component with its repository "
                            "and no other manifest component shares that repository. A receipt may name several "
                            "components, and its kind is the registrant's label, not a checked evidence class: "
                            "open it and judge what it actually ran for this component, as for evidence_refs.")
BLIND_REGISTERED_RECEIPTS_NOTE = ("registered_receipts lists the receipts manifests/evidence.json registers for a "
                                  "candidate. A receipt may name several components, and its kind is the "
                                  "registrant's label, not a checked evidence class: open it and judge what it "
                                  "actually ran for this candidate, as for evidence_refs.")
# Listed in a packet's withheld list when --withhold-labels drops the receipt ids and match routes.
WITHHELD_RECEIPT_ID_LABELS = ("candidates[].registered_receipts[].id",
                              "sota_components_not_in_candidates[].registered_receipts[].id",
                              "candidates[].registered_receipts[].matched_by",
                              "sota_components_not_in_candidates[].registered_receipts[].matched_by")


def attach_registered_receipts(packet: dict, index: dict, withhold: bool = False) -> dict:
    for item in packet.get("candidates") or []:
        item["registered_receipts"] = receipts_for(item, item.get("component_id"), index, withhold)
    for item in packet.get("sota_components_not_in_candidates") or []:
        item["registered_receipts"] = receipts_for(item, item.get("id"), index, withhold)
    packet["registered_receipts_note"] = BLIND_REGISTERED_RECEIPTS_NOTE if withhold else REGISTERED_RECEIPTS_NOTE
    if withhold:
        withheld = list(packet.get("withheld", []))
        withheld.extend(label for label in WITHHELD_RECEIPT_ID_LABELS if label not in withheld)
        label = ("registered_receipts[] whose id or path names a selection role or disposition (default, adopt, "
                 "select, winner, refuted, keep_but_compare, targeted_candidate)")
        if label not in withheld:
            withheld.append(label)
        packet["withheld"] = withheld
    return packet


GAP_LEDGER_GLOB = "catalogs/landscape/gap-wave*--*.json"
# Not blind (round-2 review): the list is the set of checks run against the layer's previous winner; 111 of
# 249 joined receipt files repeat the ledger gap text word for word, 13 name the winner, and file names such
# as 7-winner-readiness-today.json name it too. Only non-blind runs pass --gap-receipts; scripts/landscape.py
# TOP_LEVEL_WITHHELD_KEYS refuses gap_receipts/gap_receipts_note in a new wave's retained packets.
GAP_RECEIPTS_NOTE = ("gap_receipts lists receipts from the gap-resolution waves for this layer: checks run against "
                     "the layer's previous winner, recorded after its previous verdict. They are not blind: many "
                     "repeat the previous gap text and some name the previous winner, in their content or file "
                     "name. Open and judge them like evidence_refs; a receipt's content, not its presence, decides "
                     "what it establishes. A blind wave never carries this list.")


def gap_receipts_index(root: Path) -> dict:
    """(catalog, layer_id) -> sorted receipt paths from every gap-wave owner ledger
    (catalogs/landscape/gap-wave*--*.json). Only paths are carried: a gap's text and status derive from the
    previous verdict rows' open_gaps, which can name the incumbent (2026-09-23 re-record)."""
    index: dict = {}
    for ledger in sorted(root.glob(GAP_LEDGER_GLOB)):
        for layer in load_json(ledger).get("layers") or []:
            key = (layer.get("catalog"), layer.get("layer_id"))
            for gap in layer.get("gaps") or []:
                for receipt in gap.get("receipts") or []:
                    path = receipt.get("path")
                    if isinstance(path, str) and (root / path).is_file():
                        index.setdefault(key, set()).add(path)
    return {key: sorted(paths) for key, paths in index.items()}


def serialize(document: dict) -> str:
    sanitized = sanitize_value(document)
    text = json.dumps(sanitized, indent=1, sort_keys=True)
    json.loads(text)  # prove the sanitized result is still valid JSON before the leak check
    assert_no_leak(text)
    return text + "\n"


def packet_filename(catalog: str, layer_id: str) -> str:
    return f"{catalog}__{layer_id}.json"


# Under --withhold-labels, the ledger's shared prose (requirement, limitations, existing_overturn_when) keeps only
# sentences that name no packet candidate and use no selection word (Codex review of #145): "Use the selected
# NautilusTrader destination..." names the incumbent before the lane reads any evidence.
PROSE_FIELDS = ("requirement", "limitations", "existing_overturn_when")
SELECTION_WORD = re.compile(r"\b(selected|select|default|defaults|retain(?:ed|s)?|incumbents?|chosen|choose|winners?"
                            r"|adopt(?:ed|s)?|keep|kept|current (?:choice|selection|destination))\b", re.I)
NEUTRAL_REQUIREMENT = "Judge fit against the layer title and layer_scope_terms; the ledger's requirement text is withheld."


# Parts of a candidate name too generic to identify it on their own.
GENERIC_NAME_PARTS = frozenset({"python", "server", "client", "engine", "trader", "tools", "agent", "agents",
                                "stack", "local", "cloud", "native", "model", "models", "store", "check", "checks",
                                # Ordinary technical nouns (round 5): as terms they would redact prose that names no
                                # candidate ("retrieval context", "research adapter").
                                "research", "context", "adapter", "retrieval", "memory", "search", "browser",
                                "workflow", "workflows", "runner", "index", "cache", "proxy", "gateway", "bridge",
                                "monitor", "trading", "market", "data", "service", "services", "runtime", "worker",
                                "workers", "review", "reviews", "skills", "plugin", "plugins", "config", "manager"})


# A phrase that states the catalog's own choice without naming a candidate (round 5, N1: a bare "keep", "retain",
# "select" or "default" verb is not one; "selected pages" or "Keep the receipt" name no choice).
CHOICE_PHRASE = re.compile(r"\b(?:incumbents?|winners?|current (?:choice|selection|destination|default)|"
                           r"(?:selected|chosen|retained|adopted) (?:destination|choice|stack|engine|runtime|path|"
                           r"component|candidate|default|layer)|implementation choice|"
                           r"prior (?:\S+ )?(?:oracle|choice|default|selection|engine|winner)|"
                           # Adoption lifecycle status ("use stage is partial_acceptance", "not a newly qualified
                           # component").
                           r"use stage|lifecycle stage|partial_acceptance|qualified component|adoption (?:stage|status)|"
                           # Catalog membership status (Codex review of #145 at a516c477: "gh CLI has no separate
                           # manifests/stack.json inventory entry").
                           r"stack\.json|inventory entry|stack (?:entry|inventory|membership)|"
                           # A broker path's status (round 7, BL7-5: "IBKR is this catalog's selected live-primary
                           # broker path").
                           r"live-primary)", re.I)
CANDIDATE_PLACEHOLDER = "<candidate>"
CHOICE_WINDOW = 25
# Short names that are ordinary words are never terms ("one" as a component id is not the word "one").
COMMON_SHORT_WORDS = frozenset({"one", "two", "six", "ten", "all", "any", "and", "the", "for", "new", "run", "use",
                                "set", "get", "not", "yes", "off", "on", "in", "at", "to", "by", "of", "is", "it",
                                "as", "or", "an", "be", "do", "no", "up", "so", "we", "us", "if", "id", "ok"})
# Ordinary words that are also another layer's candidate name or name part ("Temporal", "LangGraph", "adaptive-paper",
# "OpenTelemetry"): as catalog-wide terms they matched plain prose and dropped a requirement clause ("retain scoped
# telemetry ...") (independent review of #145, round 7, BL7-3). Such a catalog name matches only as written.
ORDINARY_WORDS = frozenset({"graph", "exact", "paper", "inference", "actions", "action", "security", "token", "tokens",
                            "temporal", "telemetry", "optional", "foundation", "lineage", "official", "registry",
                            "exchange", "route", "testing", "financial", "basic", "software", "semantic", "modal",
                            "containers", "container", "subagent", "reference", "contrib", "practice", "support",
                            "companion", "sandbox", "inspect", "efficient", "awesome", "calendars", "calendar",
                            "attest", "servers", "collector", "timestamp", "pandas", "tracing", "evaluation"})
NEUTRAL_REQUIREMENT_NO_SCOPE = "Judge fit against the layer title; the ledger's requirement text is withheld."
# Candidate prose a lane reads besides the shared fields (round 5, N2).
CANDIDATE_PROSE_FIELDS = ("role", "card_limitations")


class CandidateMatcher:
    """Finds the candidates a text names: full names, repository names, component ids and owners and name parts
    unique to one candidate (four characters or longer, case-insensitive, with -/_/space variants), shorter names
    such as gh, uv or RTK as whole case-sensitive tokens (round 5, N2; review of 52344da8), and ``exact_terms`` (other
    layers' name parts and ordinary-word names) only as written and never inside a path (round 7, BL7-3)."""

    def __init__(self, long_terms, short_terms, exact_terms=()):
        # A selection word is never a name term, even when a candidate's name holds it (round 5, N2).
        long_terms = {term for term in long_terms if not SELECTION_WORD.fullmatch(term.strip())}
        short_terms = {term for term in short_terms if not SELECTION_WORD.fullmatch(term.strip())}
        exact_terms = {term for term in exact_terms if not SELECTION_WORD.fullmatch(term.strip())}
        self.long = re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(re.escape(t) for t in sorted(long_terms, key=len, reverse=True))
                               + r")(?![A-Za-z0-9])", re.I) if long_terms else None
        self.short = re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(re.escape(t) for t in sorted(short_terms, key=len, reverse=True))
                                + r")(?![A-Za-z0-9])") if short_terms else None
        # '-' and '/' join words ("Nautilus-native", "Codex/Claude"), so they bound a term too; only a match inside
        # a path token is skipped (round 8, REG8-4).
        self.exact = re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(re.escape(t) for t in sorted(exact_terms, key=len, reverse=True))
                                + r")(?![A-Za-z0-9])") if exact_terms else None

    def patterns(self):
        return [pattern for pattern in (self.long, self.short, self.exact) if pattern is not None]

    def _matches(self, text: str):
        for pattern in self.patterns():
            for match in pattern.finditer(text):
                if pattern is self.exact and _inside_path(text, match.start(), match.end()):
                    continue
                yield match

    def search(self, text: str) -> bool:
        return any(True for _ in self._matches(text))

    def spans(self, text: str) -> list:
        return [match.span() for match in self._matches(text)]

    def sub(self, replacement: str, text: str) -> str:
        for pattern in self.patterns():
            skip_paths = pattern is self.exact
            text = pattern.sub(lambda match: match.group(0) if skip_paths and _inside_path(
                match.string, match.start(), match.end()) else replacement, text)
        return text


_PATH_TOKEN = re.compile(r"[^\s]*/[^\s]*\.[A-Za-z0-9]+")


def _inside_path(text: str, start: int, end: int) -> bool:
    """Whether text[start:end] sits inside a whitespace-free token that names a file path (a '/' and an extension)."""
    left = text.rfind(" ", 0, start) + 1
    right = text.find(" ", end)
    token = text[left:right if right != -1 else len(text)].strip("()[]{}<>'\",;:")
    return bool(_PATH_TOKEN.fullmatch(token.rstrip(".")))


def _variants(value: str) -> set:
    lowered = value.strip().lower()
    return {lowered, re.sub(r"[-_ ]", "-", lowered), re.sub(r"[-_ ]", "_", lowered), re.sub(r"[-_ ]", " ", lowered)}


def _name_terms(candidate: dict, long_terms: set, short_terms: set) -> None:
    """Add a candidate's whole-name terms: name, repository name, component id, and each parenthesized alias of the
    name ("GitHub CLI (gh)" gives gh; Codex review of #145 at a516c477)."""
    repository = (candidate.get("repository") or "").rstrip("/")
    name = candidate.get("name") if isinstance(candidate.get("name"), str) else ""
    component = re.sub(r"^(?:candidate:|foundation-|data-)", "", str(candidate.get("component_id") or ""))
    aliases = re.findall(r"\(([^()]+)\)", name)
    for value in (re.sub(r"\s*\([^()]*\)", "", name), name, repository.split("/")[-1], component, *aliases):
        if not isinstance(value, str) or not value.strip():
            continue
        if len(value.strip()) >= 4:
            long_terms |= _variants(value)
        elif len(value.strip()) >= 2 and value.strip().lower() not in COMMON_SHORT_WORDS:
            short_terms.add(value.strip())


def candidate_matcher(candidates, layer_words=(), catalog_candidates=()) -> CandidateMatcher:
    """The CandidateMatcher of ``candidates`` (name, repository and component_id each); a name part or owner counts
    only when one candidate has it and the layer's own title and scope words (``layer_words``) do not.
    ``catalog_candidates`` (every layer's) add their whole names, so a packet does not name another layer's incumbent
    either (Codex review of #145 at a516c477: a factor layer's prose named Nautilus, LEAN and Alpaca)."""
    long_terms, short_terms, exact_terms = set(), set(), set()
    owned_parts: dict = {}
    layer = {word.lower() for word in layer_words}
    for candidate in catalog_candidates or ():
        if isinstance(candidate, dict):
            # Other layers' candidates: their whole names, except that a single ordinary word ("Temporal") matches
            # only as written; their name parts only capitalized, as a proper noun ("Nautilus", "Alpaca"), never as
            # the ordinary word ("telemetry", "graph", "exact") or a path segment (round 7, BL7-3).
            catalog_long, catalog_short = set(), set()
            _name_terms(candidate, catalog_long, catalog_short)
            short_terms |= catalog_short
            for term in catalog_long:
                if term in ORDINARY_WORDS:
                    exact_terms.update(value for value in (candidate.get("name"), candidate.get("component_id"))
                                       if isinstance(value, str) and value.lower() == term and not value.islower())
                else:
                    long_terms.add(term)
            for value in (candidate.get("name"), (candidate.get("repository") or "").rstrip("/").split("/")[-1]):
                for part in re.split(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])", value or ""):
                    if (len(part) >= 5 and part.lower() not in GENERIC_NAME_PARTS | ORDINARY_WORDS
                            and part.lower() not in layer):
                        exact_terms.add(part[:1].upper() + part[1:].lower())
    for index, candidate in enumerate(candidates or []):
        if not isinstance(candidate, dict):
            continue
        repository = (candidate.get("repository") or "").rstrip("/")
        pieces = repository.split("/")
        basename, owner = pieces[-1], (pieces[-2] if len(pieces) >= 2 else "")
        _name_terms(candidate, long_terms, short_terms)
        for value in (candidate.get("name"), basename):
            for part in re.split(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])", value or ""):
                if len(part) >= 5 and part.lower() not in GENERIC_NAME_PARTS | ORDINARY_WORDS:
                    owned_parts.setdefault(part.lower(), set()).add(index)
        if len(owner) >= 4:
            owned_parts.setdefault(owner.lower(), set()).add(index)
    long_terms |= {part for part, owners in owned_parts.items() if len(owners) == 1 and part not in layer}
    return CandidateMatcher(long_terms, short_terms, exact_terms)


def states_choice(sentence: str, matcher: CandidateMatcher, own: CandidateMatcher = None) -> bool:
    """Whether a sentence states the catalog's choice: a choice phrase, or a selection word next to a candidate name
    (within CHOICE_WINDOW characters: "the selected NautilusTrader destination", "Nautilus stays the default").
    A selection verb elsewhere in the sentence ("Keep ... across Claude and Codex sessions") is not one (round 5,
    N1).

    ``own`` (a candidate's own names, for its role and limitations): a selection word next to the candidate's own name
    describes it ("Brokerage model defaults include NullSlippageModel"), and a sentence carrying a result marker is
    evidence, so neither drops a sentence by proximity; a choice phrase always does (round 7, BL7-4)."""
    if CHOICE_PHRASE.search(sentence):
        return True
    selections = [match.span() for match in SELECTION_WORD.finditer(sentence)]
    if not selections:
        return False
    names = matcher.spans(sentence)
    if own is not None:
        if RESULT_MARKER.search(sentence):
            return False
        own_spans = set(own.spans(sentence))
        names = [span for span in names if not any(o_start <= span[0] and span[1] <= o_end
                                                   for o_start, o_end in own_spans)]
    return any(max(0, max(s_start, n_start) - min(s_end, n_end)) <= CHOICE_WINDOW
               for s_start, s_end in selections for n_start, n_end in names)


# A sentence of a candidate's own role or limitations that states its status (round 6, B6-5; round 7, BL7-4/BL7-5):
# - a copula naming the status: "is the selected ...", "remains default", "is this catalog's selected live-primary
#   broker path" ("retained" and "adopted" need a determiner, since "usage is retained" states behaviour);
# - or an opening selection adjective that labels: after "the" ("The selected GitHub CLI."), before a role noun
#   ("Selected north-star engine", "Default backend") or as a short label of at most four words ("Selected GitHub
#   CLI"), but not "Default examples use model API credentials", "Selected-file handoff bundles" or "Retained local
#   sanitized operational logs and LogQL queries".
# A choice phrase or a copula is status whatever else the sentence says; an opening adjective is not when the sentence
# carries a result marker.
_STATUS_ROLE = (r"(?:engine|runtime|stack|choice|destination|path|backend|broker|option|candidate|component|tool|"
                r"implementation|provider|store|layer|winner|solution|lane|adapter|framework|service|default|primary)s?")
STATUS_COPULA = re.compile(
    r"\b(?:is|was|are|remains?|stays?|kept as|serves as)\s+(?:(?:the|this|a|an|our|its|this catalog's|the catalog's)"
    r"\s+(?:[\w'-]+\s+){0,2}?(?:current\s+)?(?:selected|default|chosen|retained|adopted|incumbent|preferred)|"
    r"(?:current\s+)?(?:selected|default|chosen|incumbent|preferred))\b", re.I)
_STATUS_ADJECTIVE = r"(?:selected|default|chosen|retained|adopted|incumbent|preferred)(?![\w-])"
STATUS_OPENING = re.compile(r"^\W*(?:the\s+" + _STATUS_ADJECTIVE + r"|" + _STATUS_ADJECTIVE + r"\s+(?:[\w'/-]+\s+){0,3}?"
                            + _STATUS_ROLE + r"\b)", re.I)
STATUS_LABEL = re.compile(r"^\W*" + _STATUS_ADJECTIVE + r"(?:\s+[\w'/()-]+){0,3}\W*$", re.I)


def opens_with_status(sentence: str) -> bool:
    """Whether a sentence opens with a selection adjective that labels its subject (STATUS_OPENING, STATUS_LABEL)."""
    return bool(STATUS_OPENING.search(sentence) or STATUS_LABEL.search(sentence))
# Evidence in a sentence: a pass/fail/blocked result (also inside an underscore-joined status token such as
# reported_execution_blocked_review_incomplete), an exit code, a count such as 4/6, a repository path or a bare
# evidence file name (round 7, BL7-4: the marker was case-sensitive and needed a slash path).
RESULT_MARKER = re.compile(r"(?<![A-Za-z])(?:pass(?:ed|es)?|fail(?:ed|s|ure)?|blocked)(?![A-Za-z])|"
                           r"\bexit(?: code)? \d+\b|\b\d+/\d+\b|"
                           r"(?<![\w.])[\w.-]+/[\w./-]+\.\w+|"
                           r"\b[\w.-]+\.(?:json|jsonl|md|txt|ya?ml|py|csv|log|sha256|SHA256SUMS)\b", re.I)


def states_candidate_status(sentence: str) -> bool:
    return bool(CHOICE_PHRASE.search(sentence) or STATUS_COPULA.search(sentence)
                or (opens_with_status(sentence) and not RESULT_MARKER.search(sentence)))


def reduce_prose(text: str, matcher: CandidateMatcher, about_candidate: bool = False,
                 own: CandidateMatcher = None) -> str:
    """``text`` without the sentences that state the choice, and with every other candidate name replaced by
    <candidate> (round 5, N1: redact the name rather than empty the sentence). A candidate's own role or
    limitations (``about_candidate``, with its own names ``own``) also lose a sentence that states that candidate's
    status, and keep one whose selection word only describes the candidate itself or sits beside a result marker
    (round 7, BL7-4)."""
    kept = []
    for sentence in re.split(r"(?<=[.!?;])\s+", text.strip()):
        if (not sentence or states_choice(sentence, matcher, own if about_candidate else None)
                or (about_candidate and states_candidate_status(sentence))):
            continue
        kept.append(matcher.sub(CANDIDATE_PLACEHOLDER, sentence))
    return " ".join(kept)


def withhold_prose(packet: dict, catalog_candidates=()) -> dict:
    layer_words = re.findall(r"[A-Za-z0-9]+", str(packet.get("title") or "")) + [
        word for term in packet.get("layer_scope_terms") or [] for word in re.findall(r"[A-Za-z0-9]+", str(term))]
    matcher = candidate_matcher(packet.get("candidates") or [], layer_words, catalog_candidates)
    reduced = []
    for field in PROSE_FIELDS:
        value = packet.get(field)
        if isinstance(value, str):
            kept = reduce_prose(value, matcher)
        elif isinstance(value, list):
            kept = [item for item in (reduce_prose(str(entry), matcher) for entry in value) if item]
        else:
            continue
        if kept != value:
            reduced.append(field)
        packet[field] = kept
    for candidate in packet.get("candidates") or []:
        own = candidate_matcher([candidate], layer_words)
        for field in CANDIDATE_PROSE_FIELDS:
            value = candidate.get(field)
            if isinstance(value, str):
                candidate[field] = reduce_prose(value, matcher, about_candidate=True, own=own) or None
            elif isinstance(value, list):
                candidate[field] = [item for item in (reduce_prose(str(entry), matcher, about_candidate=True, own=own)
                                                      for entry in value) if item]
    if not packet.get("requirement"):
        # Only a packet that carries layer_scope_terms is pointed at them (round 5, N1/N4).
        packet["requirement"] = NEUTRAL_REQUIREMENT if packet.get("layer_scope_terms") else NEUTRAL_REQUIREMENT_NO_SCOPE
    withheld = list(packet.get("withheld", []))
    label = ("sentences of requirement, limitations, existing_overturn_when and candidates' role and card_limitations "
             "that state the current choice; other candidate names there are written <candidate>")
    if label not in withheld:
        withheld.append(label)
    packet["withheld"] = withheld
    return packet


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


# Packet references to files blind_checkout.py removes from every blind export (membership lists, selection
# records and earlier verdicts): a lane pointed at one finds nothing (independent review of #145, F4/OPS-1: 5 such
# references on the 2026-09-23 packets). The label is listed on every blind packet, dropped reference or not.
REMOVED_REFS_LABEL = ("candidates[].evidence_refs[] and registered_receipts[] naming a file the blind export removes "
                      "(membership, selection or earlier-verdict records)")


def removed_reference(reference) -> bool:
    from blind_checkout import bare_reference, removed_from_blind_export
    bare = bare_reference(reference)
    return bare is not None and removed_from_blind_export(bare)


def withhold_removed_refs(packet: dict) -> tuple:
    """(packet, dropped count): every candidate's evidence_refs and every registered receipt that names a file the
    blind export removes are dropped, and REMOVED_REFS_LABEL is listed in the packet's withheld list."""
    dropped = 0
    for collection in ("candidates", "sota_components_not_in_candidates"):
        for item in packet.get(collection) or []:
            if not isinstance(item, dict):
                continue
            if collection == "candidates" and item.get("evidence_refs"):
                kept = [reference for reference in item["evidence_refs"] if not removed_reference(reference)]
                dropped += len(item["evidence_refs"]) - len(kept)
                item["evidence_refs"] = kept
            if item.get("registered_receipts"):
                kept = [receipt for receipt in item["registered_receipts"]
                        if not (isinstance(receipt, dict) and removed_reference(receipt.get("path")))]
                dropped += len(item["registered_receipts"]) - len(kept)
                item["registered_receipts"] = kept
    withheld = list(packet.get("withheld", []))
    if REMOVED_REFS_LABEL not in withheld:
        withheld.append(REMOVED_REFS_LABEL)
    packet["withheld"] = withheld
    return packet, dropped


def withhold_candidate_labels(packet: dict) -> dict:
    """Drop WITHHELD_CANDIDATE_LABELS from every candidate and list them in withheld: a selected candidate must carry
    a strong evidence_kind (scripts/landscape.py), so the kind held exactly the winners in 7 of the 2026-09-23 layers
    (round 5, N5). The lane judges the evidence it opens instead."""
    for candidate in packet.get("candidates") or []:
        for field in WITHHELD_CANDIDATE_LABELS:
            candidate.pop(field, None)
    withheld = list(packet.get("withheld", []))
    withheld.extend(label for label in withheld_candidate_label_labels() if label not in withheld)
    packet["withheld"] = withheld
    return packet


def seal_candidate_fields(packet: dict) -> tuple:
    """(packet, {candidate key: {field: value}}): every candidate's SEALED_CANDIDATE_FIELDS moved out of a
    --withhold-labels packet and listed in its withheld list. Their presence alone marks a sota-manifest
    component, which singled out the catalog's current choice among the adopted candidates (review of #145;
    scripts/landscape.py SEALED_CANDIDATE_FIELDS has the measurement); record_verdicts.py and adjudicate.py
    restore them from --keys-out."""
    sealed = {}
    for candidate in packet.get("candidates") or []:
        sealed[candidate["key"]] = {field: candidate.pop(field) for field in SEALED_CANDIDATE_FIELDS if field in candidate}
        # A selection word in a candidate's own name labels it (round 6, B6-6).
        if isinstance(candidate.get("name"), str):
            bare = re.sub(r"[(\[]\s*[)\]]", "", SELECTION_WORD.sub("", candidate["name"]))  # "Tool (selected)"
            candidate["name"] = re.sub(r"\s{2,}", " ", bare).strip() or candidate["name"]
    # The commitment covers the values as the document stores them (sanitized, as serialize and record_verdicts'
    # sealed_text write them; round 6, INT-R6-1).
    sealed = sanitize_value(sealed)
    # The packet commits to the sealed values (scripts/landscape.py sealed_candidates_sha256), so only this
    # build's document restores them and every return, bound to the packet's bytes, is bound to them too.
    packet[SEALED_COMMITMENT_KEY] = sealed_candidates_sha256(sealed)
    withheld = list(packet.get("withheld", []))
    withheld.extend(label for label in sealed_candidate_labels() if label not in withheld)
    packet["withheld"] = withheld
    return packet, sealed


def build_all_packets(root: Path, *, catalogs: list, seed: str, checked_at: str,
                      trading_candidates: str = "ledger", withhold: bool = False,
                      manifest: str = None, registered_receipts: bool = False,
                      gap_receipts: bool = False, manifest_newcomers_on: bool = False,
                      sealed_keys: dict = None, removed_refs: dict = None) -> dict:
    """Returns {filename: serialized packet text}, fully built and leak-
    checked in memory before any file is written. ``manifest`` overrides the
    dated sota manifest joined in (default reproduces the 2026-09-22
    packets); pass the same value used for build_verdicts.py's --manifest so
    the packets and the verdict catalog agree on the pins. Under ``withhold``,
    each packet's sealed candidate fields (seal_candidate_fields) go to
    ``sealed_keys`` ({filename: {packet_sha256, candidates}}) when it is given, and the number of references to
    files the blind export removes that each packet dropped (withhold_removed_refs) to ``removed_refs``."""
    rules = load_rules()
    sota_doc = load_json(root / (manifest or SOTA_MANIFEST_PATH))
    sota_index = sota_layer_index(sota_doc)
    recipe_map = load_json(root / ADOPTION_MANIFEST_PATH).get("recipe_map", {})
    decisions_doc = load_json(root / FOUNDATION_DECISIONS_PATH)
    decisions_by_component = foundation_decisions_by_component(decisions_doc)
    manifest_mode = trading_candidates == "manifest"
    cards = trading_cards_by_id(root) if manifest_mode else {}
    trading_layers = {layer["layer"]: layer for layer in sota_doc.get("trading", [])}
    receipts_index = registered_receipts_index(root, sota_doc) if registered_receipts else None
    if gap_receipts and withhold:
        # Gap receipts are checks run against the previous winner; a blind (label-withheld) build must not carry
        # them, and refusing here stops lanes from ever opening them (Codex review of #145).
        raise ValueError("--gap-receipts cannot be combined with --withhold-labels: gap receipts name the "
                         "previous winner")
    gap_index = gap_receipts_index(root) if gap_receipts else None
    evidence_files = registered_evidence_files(root) if manifest_newcomers_on else None
    manifest_rows = {"foundation": {layer["layer"]: layer for layer in sota_doc.get("foundation", [])},
                     "us-equities": trading_layers}

    # Every catalog candidate's name, so no packet's prose names another layer's incumbent.
    catalog_candidates = [candidate for relative in LEDGER_FILES.values()
                          for row in load_json(root / relative).get("layers", [])
                          for candidate in row.get("candidates") or [] if isinstance(candidate, dict)]
    catalog_candidates += [{"name": entry.get("id"), "repository": entry.get("repository"), "component_id": entry.get("id")}
                           for layer in trading_layers.values() for entry in layer.get("entries", [])
                           if isinstance(entry, dict)]
    catalog_candidates += [{"repository": item.get("repository"), "component_id": item.get("id")}
                           for rows in (sota_doc.get("foundation") or [],) for row in rows if isinstance(row, dict)
                           for item in row.get("components") or [] if isinstance(item, dict)]
    packets = {}
    for catalog in catalogs:
        ledger = load_json(root / LEDGER_FILES[catalog])
        for row in ledger.get("layers", []):
            layer_candidates = None
            if manifest_mode and catalog == "us-equities":
                names = {github_repo_slug(c["repository"]): c.get("name")
                         for c in row.get("candidates") or [] if c.get("repository")}
                layer_candidates = manifest_layer_candidates(
                    trading_layers.get(row["layer_id"], {}), cards, names, recipe_map, root, evidence_files,
                    withhold)
            newcomers = None
            if evidence_files is not None and layer_candidates is None:
                # --manifest-newcomers on a ledger-built packet: the manifest row's surviving newcomers.
                seen = {github_repo_slug(c["repository"]) for c in row.get("candidates") or [] if c.get("repository")}
                newcomers = manifest_newcomers(manifest_rows[catalog].get(row["layer_id"], {}), seen,
                                               evidence_files, root, withhold)
            packet = build_packet(
                row, catalog=catalog, sota_components=sota_index.get((catalog, row["layer_id"]), []),
                catalog_components=catalog_components(sota_index, catalog),
                recipe_map=recipe_map, decisions_by_component=decisions_by_component,
                seed=seed, checked_at=checked_at, root=root, rules=rules, layer_candidates=layer_candidates,
                layer_scope_terms=(sota_doc.get("taxonomy") or {}).get(row["layer_id"]) if layer_candidates is not None
                else None, newcomers=newcomers,
            )
            if withhold and layer_candidates is None:
                # Manifest-mode trading packets already carry no decision labels.
                packet = withhold_labels(packet)
            if withhold:
                # Every packet, manifest-mode trading packets included, loses popularity and
                # recency signals; the default (no --withhold-labels) build is unchanged. Prose first, so
                # the archived/license gating reads the requirement the lanes see (round 5, N4).
                packet = withhold_prose(packet, catalog_candidates)
                packet = withhold_popularity(packet)
            if gap_index is not None:
                packet["gap_receipts"] = gap_index.get((catalog, row["layer_id"]), [])
                packet["gap_receipts_note"] = GAP_RECEIPTS_NOTE
            if receipts_index is not None:
                packet = attach_registered_receipts(packet, receipts_index, withhold)
            name = packet_filename(catalog, row["layer_id"])
            sealed = None
            if withhold:
                packet = withhold_candidate_labels(packet)
                packet, dropped = withhold_removed_refs(packet)
                if removed_refs is not None and dropped:
                    removed_refs[name] = dropped
                # Last, after receipts were matched by component id.
                packet, sealed = seal_candidate_fields(packet)
                found = withheld_packet_keys(packet)
                if found:
                    # CI and record_verdicts.py refuse such a packet once both lanes ran on it (round 5, N4).
                    raise ValueError(f"{name} would carry withheld keys {found}")
            packets[name] = serialize(packet)
            if sealed is not None and sealed_keys is not None:
                sealed_keys[name] = {"packet_sha256": hashlib.sha256(packets[name].encode("utf-8")).hexdigest(),
                                     "candidates": sealed}
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
                             "license unless the requirement names them; always upstream.latest, upstream.prerelease, "
                             "upstream.latest_flag, pin_behind_upstream, the newcomer flag, the candidate-only note "
                             "and any key naming a release) at any depth of every candidate and component copy "
                             "of every packet; each stripped field is listed in the packet's withheld list. Off by "
                             "default so the 2026-09-22 packets reproduce.")
    parser.add_argument("--keys-out", type=Path, default=None,
                        help="With --withhold-labels (required there): write the candidates' sealed manifest fields "
                             "(component_id, pin, upstream, recipe_ref, decisions) to this packet-keys JSON file, "
                             "outside --out so no lane reads it; record_verdicts.py --packet-keys and adjudicate.py "
                             "inputs --packet-keys restore them.")
    parser.add_argument("--registered-receipts", action="store_true",
                        help="Attach to every candidate and component the receipts registered in "
                             "manifests/evidence.json for it (kind, path and matched_by; id too unless "
                             "--withhold-labels), matched by component id, or by repository only when no other "
                             "component shares it, so a lane can open and cite them. Off by default so the "
                             "2026-09-22 packets reproduce.")
    parser.add_argument("--gap-receipts", action="store_true",
                        help="Attach to every packet the receipt paths the gap-wave owner ledgers "
                             "(catalogs/landscape/gap-wave*--*.json) list for its layer; paths only, no gap text. "
                             "Not blind: the receipts are checks of the previous winner and many name it, so a "
                             "blind wave must not pass this (a new wave's retained packets refuse it). Off by "
                             "default: the default build path is unchanged.")
    parser.add_argument("--manifest-newcomers", action="store_true",
                        help="Carry the dated manifest's newcomer candidates and keep-but-compare alternatives in "
                             "every packet (foundation included, shuffled with the ledger candidates), leave out "
                             "any whose discovery was refuted (disposition refuted_*), and attach as a newcomer's "
                             "evidence_refs each evidence[] entry that is exactly an evidence/ path registered in "
                             "manifests/evidence.json files[] with its current sha256. Off by default so the "
                             "2026-09-22 packets reproduce.")
    parser.add_argument("--trading-candidates", choices=("ledger", "manifest"), default="ledger",
                        help="Candidate source for us-equities packets: the ledger row's group-wide list "
                             "(default; reproduces the 2026-09-22 packets) or the sota manifest's own entries "
                             "for the layer, with evidence from their domain catalog cards.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    catalogs = [args.catalog] if args.catalog else sorted(LEDGER_FILES)

    if args.gap_receipts and args.withhold_labels:
        print("lane_packets: --gap-receipts cannot be combined with --withhold-labels: gap receipts name the "
              "previous winner", file=sys.stderr)
        return 2
    if args.withhold_labels != (args.keys_out is not None):
        print("lane_packets: --keys-out is required with --withhold-labels and only meaningful there: the sealed "
              "candidate fields are needed to record verdicts", file=sys.stderr)
        return 2
    if args.keys_out is not None:
        keys_out, out = args.keys_out.resolve(), args.out.resolve()
        if keys_out == out or out in keys_out.parents:
            print("lane_packets: --keys-out must be outside --out, where lanes read packets", file=sys.stderr)
            return 2
    manifest_relative = str(args.manifest) if args.manifest else None
    if args.withhold_labels:
        # A blind build never overwrites a wave's packets or keys (independent review of #145, round 6, OPR6-3): a
        # re-check goes to new directories.
        for existing in (args.out / "packets", args.keys_out):
            if existing is not None and existing.exists():
                print(f"lane_packets: {existing} already exists; write a blind build to new directories",
                      file=sys.stderr)
                return 2
        # Lanes read --out, and --keys-out names the winners: neither may sit in a repository, whose history or
        # siblings a worker can read (round 7, OPR7-5).
        for flag, place in (("--out", args.out), ("--keys-out", args.keys_out)):
            # Both spellings: a symlink can lead into a checkout (round 8, REG8-5).
            spellings = {Path(os.path.abspath(place)), Path(place).resolve()}
            repository = next((str(path) for spelling in spellings for path in (spelling, *spelling.parents)
                               if (path / ".git").exists()), None)
            absolute = Path(os.path.abspath(place))
            if repository:
                print(f"lane_packets: {flag} {absolute} is inside the git repository {repository}; place a blind "
                      "build outside every repository", file=sys.stderr)
                return 2
        if args.manifest:
            # The keys document records the manifest relative to --root, where record_verdicts finds it (round 7,
            # REG7-4: an absolute path was sanitized to <host-path> and refused only at step 6).
            manifest_path = Path(args.manifest)
            resolved = (manifest_path if manifest_path.is_absolute() else root / manifest_path).resolve()
            if root not in resolved.parents or not resolved.is_file():
                print(f"lane_packets: --manifest {args.manifest} is not a file under --root {root}", file=sys.stderr)
                return 2
            manifest_relative = resolved.relative_to(root).as_posix()
    sealed_keys, removed_refs = {}, {}
    packets = build_all_packets(root, catalogs=catalogs, seed=str(args.seed), checked_at=args.checked_at,
                                trading_candidates=args.trading_candidates, withhold=args.withhold_labels,
                                manifest=manifest_relative,
                                registered_receipts=args.registered_receipts, gap_receipts=args.gap_receipts,
                                manifest_newcomers_on=args.manifest_newcomers, sealed_keys=sealed_keys,
                                removed_refs=removed_refs)

    out_dir = args.out / "packets"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in packets.items():
        (out_dir / name).write_text(text, encoding="utf-8")
    (out_dir / "SHA256SUMS").write_text(sha256sums(packets), encoding="utf-8")
    if args.keys_out is not None:
        args.keys_out.parent.mkdir(parents=True, exist_ok=True)
        # The manifest the sealed component ids come from, by path and sha256: record_verdicts.py checks every
        # sealed id against it (round 6, INT-R6-2).
        manifest_relative = manifest_relative or SOTA_MANIFEST_PATH
        manifest_bytes = (root / manifest_relative).read_bytes()
        args.keys_out.write_text(serialize({"schema_version": PACKET_KEYS_SCHEMA_VERSION, "packets": sealed_keys,
                                            "manifest": {"path": manifest_relative,
                                                         "sha256": hashlib.sha256(manifest_bytes).hexdigest()}}),
                                 encoding="utf-8")

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
        "unmatched_sota_components": unmatched_counts, "dropped_removed_file_refs": removed_refs,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
