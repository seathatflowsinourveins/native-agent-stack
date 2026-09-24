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
# The withheld-key policy is shared with scripts/landscape.py, which re-checks every packet a new
# wave retains (evidence/artifacts/layer-verdicts-<run-id>/packets/) against it in CI.
from scripts.landscape import (  # noqa: E402
    COPY_WITHHELD_FIELDS, PACKET_KEYS_SCHEMA_VERSION, POPULARITY_TOKENS, REQUIREMENT_GATED_FIELDS,
    SEALED_CANDIDATE_FIELDS, is_withheld_packet_key, requirement_names, sealed_candidate_labels,
    withhold_policy_labels,
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
# adoption/receipt.json) repeats the incumbent label the blind packet withholds.
LABEL_BEARING_RECEIPT = re.compile(r"default|adopt|select|winner|incumbent|chosen|retain", re.I)


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
        label = "registered_receipts[] whose id or path names a selection role (default, adopt, select, winner)"
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
                                "stack", "local", "cloud", "native", "model", "models", "store", "check", "checks"})


def candidate_terms(packet: dict) -> list:
    """Words that identify a packet candidate: its name and repository name (four characters or longer), and their
    distinctive parts ("NautilusTrader" and "nautilus_trader" give "nautilus")."""
    terms = set()
    for candidate in packet.get("candidates") or []:
        for value in (candidate.get("name"), (candidate.get("repository") or "").rstrip("/").split("/")[-1]):
            if not isinstance(value, str) or len(value.strip()) < 4:
                continue
            terms.add(value.strip().lower())
            for part in re.split(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])", value):
                if len(part) >= 5 and part.lower() not in GENERIC_NAME_PARTS:
                    terms.add(part.lower())
    return sorted(terms, key=len, reverse=True)


def neutral_sentences(text: str, terms: list) -> str:
    kept = []
    for sentence in re.split(r"(?<=[.!?;])\s+", text.strip()):
        lowered = sentence.lower()
        if not sentence or SELECTION_WORD.search(sentence) or any(
                re.search(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", lowered) for term in terms):
            continue
        kept.append(sentence)
    return " ".join(kept)


def withhold_prose(packet: dict) -> dict:
    terms = candidate_terms(packet)
    reduced = []
    for field in PROSE_FIELDS:
        value = packet.get(field)
        if isinstance(value, str):
            kept = neutral_sentences(value, terms)
        elif isinstance(value, list):
            kept = [item for item in (neutral_sentences(str(entry), terms) for entry in value) if item]
        else:
            continue
        if kept != value:
            reduced.append(field)
        packet[field] = kept
    if not packet.get("requirement"):
        packet["requirement"] = NEUTRAL_REQUIREMENT
    if reduced:
        withheld = list(packet.get("withheld", []))
        label = ("sentences of requirement, limitations and existing_overturn_when that name a candidate or use a "
                 "selection word")
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


def seal_candidate_fields(packet: dict) -> tuple:
    """(packet, {candidate key: {field: value}}): every candidate's SEALED_CANDIDATE_FIELDS moved out of a
    --withhold-labels packet and listed in its withheld list. Their presence alone marks a sota-manifest
    component, which singled out the catalog's current choice among the adopted candidates (review of #145;
    scripts/landscape.py SEALED_CANDIDATE_FIELDS has the measurement); record_verdicts.py and adjudicate.py
    restore them from --keys-out."""
    sealed = {}
    for candidate in packet.get("candidates") or []:
        sealed[candidate["key"]] = {field: candidate.pop(field) for field in SEALED_CANDIDATE_FIELDS if field in candidate}
    withheld = list(packet.get("withheld", []))
    withheld.extend(label for label in sealed_candidate_labels() if label not in withheld)
    packet["withheld"] = withheld
    return packet, sealed


def build_all_packets(root: Path, *, catalogs: list, seed: str, checked_at: str,
                      trading_candidates: str = "ledger", withhold: bool = False,
                      manifest: str = None, registered_receipts: bool = False,
                      gap_receipts: bool = False, sealed_keys: dict = None, removed_refs: dict = None) -> dict:
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
                packet = withhold_prose(packet)
            if gap_index is not None:
                packet["gap_receipts"] = gap_index.get((catalog, row["layer_id"]), [])
                packet["gap_receipts_note"] = GAP_RECEIPTS_NOTE
            if receipts_index is not None:
                packet = attach_registered_receipts(packet, receipts_index, withhold)
            name = packet_filename(catalog, row["layer_id"])
            sealed = None
            if withhold:
                packet, dropped = withhold_removed_refs(packet)
                if removed_refs is not None and dropped:
                    removed_refs[name] = dropped
                # Last, after receipts were matched by component id.
                packet, sealed = seal_candidate_fields(packet)
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
    sealed_keys, removed_refs = {}, {}
    packets = build_all_packets(root, catalogs=catalogs, seed=str(args.seed), checked_at=args.checked_at,
                                trading_candidates=args.trading_candidates, withhold=args.withhold_labels,
                                manifest=str(args.manifest) if args.manifest else None,
                                registered_receipts=args.registered_receipts, gap_receipts=args.gap_receipts,
                                sealed_keys=sealed_keys, removed_refs=removed_refs)

    out_dir = args.out / "packets"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in packets.items():
        (out_dir / name).write_text(text, encoding="utf-8")
    (out_dir / "SHA256SUMS").write_text(sha256sums(packets), encoding="utf-8")
    if args.keys_out is not None:
        args.keys_out.parent.mkdir(parents=True, exist_ok=True)
        args.keys_out.write_text(serialize({"schema_version": PACKET_KEYS_SCHEMA_VERSION, "packets": sealed_keys}),
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
