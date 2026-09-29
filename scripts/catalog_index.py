#!/usr/bin/env python3
"""Build/check the ranked catalog index, ``catalogs/landscape/catalog-index.json``: one generated, read-only join of
the recorded layer verdicts, the generated component evidence matrix, the repository decision index, the stack and
the evidence manifest, with the placements of every layer in evidence order under one frozen rule.

It never selects a winner, changes a verdict, records a receipt or infers a benchmark win. Order within a layer is
evidence order under the stated rule, not quality or superiority, and there is no order across layers. The rule
compares ordered keys -- recorded role, evidence tier, independent verification at the current pin on
linux-wsl2-x86_64, comparable measured rank -- lexicographically; nothing is blended into a score, and tied
placements share a position (competition ranking). Conflicts and stale entries become Backstage-style status items;
none is resolved. Decision record: ``docs/decisions/2026-09-29-catalog-index-ranking.md``.

Inputs are the committed files ``INPUTS`` names: the matrix is read as committed, as
``scripts/new_host_grand_list.py`` reads it, and from ``manifests/evidence.json`` only ``receipts[]`` and
``convergence_records[]`` are read, never ``files[]``, which ``host_receipts.register_file`` rewrites. A sorted
filesystem listing of ``catalogs/**/*.json`` and ``manifests/*.json`` (without this file's own path) gives the
coverage account, with no git call.

Modes: ``--check`` (default) rebuilds in memory, runs the fatal checks F2-F16 and byte-compares with the committed
file (F1); ``--write`` runs the same checks, writes the file and re-registers its hash in manifests/evidence.json.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import sys

try:
    from . import catalog_decisions
    from . import component_matrix
    from . import host_receipts
    from . import landscape
    from . import new_host_grand_list
    from . import platform_status
    from .validate import PRIVATE_CONTENT
except ImportError:  # running as a plain script, not a package
    import catalog_decisions
    import component_matrix
    import host_receipts
    import landscape
    import new_host_grand_list
    import platform_status
    from validate import PRIVATE_CONTENT


# The date the rule below was frozen. It is never a build date: the generator reads no clock.
FROZEN_AT = "2026-09-29"
OUTPUT_JSON = "catalogs/landscape/catalog-index.json"
MATRIX_FILE = component_matrix.OUTPUT_JSON
LEDGER_FILES = dict(sorted(host_receipts.LANDSCAPE_CATALOGS.items()))
DECISION_INDEX_FILE = catalog_decisions.INDEX
ALIASES_FILE = catalog_decisions.BASE + "/coverage.json"
STACK_FILE = component_matrix.STACK_FILE
EVIDENCE_FILE = "manifests/evidence.json"
LANDSCAPE_MANIFEST_FILE = landscape.MANIFEST
LISTING_INPUT = "catalogs/**/*.json + manifests/*.json"
LISTING_GLOBS = (("catalogs", "**/*.json"), ("manifests", "*.json"))
PLATFORM = component_matrix.CONVERGENCE_PLATFORM
MACOS_PLATFORM = "macos-arm64"
# F2: the user asked for each of the 32 layers; a layer added to or removed from a ledger updates this constant and
# the decision record together.
EXPECTED_LAYER_COUNT = 32
# gitleaks skips larger files (--max-target-megabytes 2 in .github/workflows/validate.yml); the smaller reading of
# "2 MB" (10**6 bytes per MB) is the cap, and --write warns from 1.5 million bytes.
SIZE_WARN_BYTES = 1_500_000
SIZE_LIMIT_BYTES = 2_000_000
ENTITY_PREFIX = "repo:"

INPUTS = (
    (MATRIX_FILE,
     "rows[]: catalog, layer_id, title, verdict_status, independent_review, open_gaps; winners[] component_id, "
     "repository, pin, evidence_class and per-platform catalog_status, derived_status, e2e_state, host_receipts; "
     "alternatives[] name, repository, disposition, evidence_class, e2e_state; convergence layer_state, "
     "verdict_checked_at, reopened_by and components[] winner_ids, pin_current; summary.convergence.newest_manifest"),
    (LEDGER_FILES["foundation"],
     "layers[]: layer_id, decision, verdict_status, overturn_protocol.metric; winners[], alternatives[] and "
     "candidates[] by array position (role_records); candidates[] repository, disposition, evidence_kind, "
     "evidence_refs"),
    (LEDGER_FILES["us-equities"],
     "layers[]: layer_id, decision, verdict_status, overturn_protocol.metric; winners[], alternatives[] and "
     "candidates[] by array position (role_records); candidates[] repository, disposition, evidence_kind, "
     "evidence_refs"),
    (DECISION_INDEX_FILE,
     "records[]: repository (the entity universe), aliases and references[] kind and decision; sources[].path"),
    (ALIASES_FILE, "/aliases, through catalog_decisions.aliases_for"),
    (STACK_FILE, "components[]: id, repository, profile"),
    (EVIDENCE_FILE,
     "receipts[]: id, kind, component_ids; convergence_records[]; never files[], which host_receipts.register_file "
     "rewrites"),
    (LANDSCAPE_MANIFEST_FILE, "/universal_superiority and /sources/trading_taxonomy"),
    (LISTING_INPUT,
     "sorted filesystem listing without this file's own path (coverage.catalog_files); each listed file is parsed "
     "only for a top-level non_repository_decisions array (coverage.unmodeled_collections), and "
     "component_matrix.newest_sweep_manifest reads the sweep manifests' checked_at to classify the matrix's inputs"),
)
DECLARED_INPUT_PATHS = frozenset(path for path, _scope in INPUTS if path != LISTING_INPUT)

ROLES = ("winner", "alternative", "candidate")
ROLE_RANK = {role: rank for rank, role in enumerate(ROLES)}
TIERS = ("A", "B", "C", "U")
TIER_RANK = {tier: rank for rank, tier in enumerate(TIERS)}
EVIDENCE_FIELDS = {"winner": "evidence_class", "alternative": "evidence_class", "candidate": "evidence_kind"}
# landscape.WINNER_EVIDENCE_CLASSES and landscape.EVIDENCE_KINDS; check_vocabularies() keeps them covered.
CLASS_TIERS = {"local_integration": "B", "measured_comparison": "A", "native_proven": "A", "source_review": "C",
               "synthetic": "B"}
KIND_TIERS = {"measured_comparison": "A", "native_execution": "A", "requirement_fit": "U", "source_review": "C"}
MIXED_KIND = "mixed"
RETAINED_RESULT_SUFFIXES = (".json", ".txt", ".log")
POLICY_ROWS = {"A": ["Upstream test", "Upstream example or native operation"],
               "local_integration": ["Local integration check"], "synthetic": ["Synthetic fixture"]}
VERIFICATION_LEVELS = {
    "winner": {"host_verified": 0, "accepted": 1, "conditional": 2, "not_established": 3, "untested": 3},
    "alternative": {"host_verified": 0, "receipts_recorded": 1, "not_run": 1},
    "candidate": {"not_applicable": 0},
}
ALTERNATIVE_E2E_STATES = ("host_verified", "not_run", "receipts_recorded")
PIN_CURRENT_VALUES = tuple(component_matrix.CONVERGENCE_FACTOR_VALUES)
# Only for counts.overturn_metrics: what a pin_current tiebreak (winners only, as K5) would change; never a sort key.
PIN_TIEBREAK = {"true": 0, "unknown": 1, "false": 2}
OUTSIDE_REASONS = ("out_of_scope", "observed_failure")
REACHED_AS = ("index_input", "matrix_input", "decision_index_source", "not_reached")
NON_REPOSITORY_KEY = "non_repository_decisions"
UNMODELED_FIXED = ((STACK_FILE, "/models"), ("catalogs/us-equities/models.json", "/entries"))
COMPARABILITY_FIELDS = ("layer", "metric", "benchmark", "benchmark_major_version", "fixture_sha256", "host_profile",
                        "pins", "direction")
DIRECTIONS = ("higher_is_better", "lower_is_better")
OUTCOMES = ("pass", "fail")
NO_MEASUREMENT = "no comparable measurement recorded"
BANNED_KEY_TOKENS = frozenset({"score", "scores", "weight", "weights", "weighted", "total", "totals", "composite"})
BLENDED_SCORE_POINTER = "/rule/blended_score"

PENDING_NOTE = ("No recorded verdict: every entry is a historical candidate card; the order is candidate-card "
                "evidence only, not a selection.")
REOPENED_NOTE = ("A completed sweep dated after this verdict covers the layer (reopened_by); the recorded roles stand "
                 "until the verdict is re-recorded.")
NO_SELECTION_NOTE = "No selection recorded: alternatives and candidate cards are ordered without a winner."
SCOPE = ("Read-only join of the recorded layer verdicts, component evidence matrix, decision index, stack and "
         "evidence manifest. It never selects a winner, changes a verdict, records a receipt or infers a benchmark "
         "win; order within a layer is evidence order under the stated rule, not quality or superiority; there is no "
         "order across layers.")
STALE_MESSAGE = ("stale or missing: " + OUTPUT_JSON + "; after re-adding your branch's receipts[] and "
                 "convergence_records[] entries to manifests/evidence.json, run python3 scripts/component_matrix.py "
                 "--write, python3 scripts/new_host_grand_list.py --write, python3 scripts/catalog_index.py --write, "
                 "then python3 scripts/validate.py")

STATUS_TYPES = {
    "coverage/not-reached": "info",
    "domain-card/default-never-winner": "info",
    "evidence/class-verification-inversion": "info",
    "evidence/mixed-kind": "info",
    "evidence/unmapped-kind": "info",
    "evidence/winner-tier-below-alternative": "info",
    "freshness/layer-reopened": "info",
    "freshness/pin-behind-upstream": "info",
    "identity/component-id-conflict": "error",
    "identity/multiple-component-ids": "info",
    "identity/unresolved": "warning",
    "role/selected-card-no-verdict": "info",
    "role/selected-card-not-winner": "warning",
    "role/winner-card-not-selected": "warning",
    "source/sweep-manifest-divergence": "info",
    "status/declared-above-derived": "warning",
    "verification/host-fail-recorded": "info",
    "verification/joined-by-repository": "info",
}
STATUS_LEVELS = ("info", "warning", "error")

DEFINITIONS = (
    ("recorded_role",
     "K1. 0 for a winner of the layer's recorded verdict, 1 for a verdict alternative, 2 for an entity that only a "
     "historical candidate card names. The current layer decision takes precedence over historical candidate-card "
     "recommendations (catalogs/landscape/manifest.json rules), so this index never selects a winner: a card that "
     "says selected never raises a role, and each conflict is a status item."),
    ("evidence_tier",
     "K2. A: evidence_class native_proven or measured_comparison, evidence_kind native_execution or "
     "measured_comparison, or evidence_kind mixed with a retained local result. B: local_integration or synthetic, "
     "tied as scripts/platform_status.py CONDITIONAL_CLASSES ties them. C: source_review, or mixed without a retained "
     "local result. U: requirement_fit, which no row of docs/acceptance-evidence-policy.md covers; it sorts after C "
     "and is flagged. Winners and alternatives use the verdict's evidence_class, card-only candidates the card's "
     "evidence_kind."),
    ("retained_local_result",
     "An evidence_refs item that does not start with https:// and ends with .json, .txt or .log: the predicate "
     "scripts/landscape.py applies to an observed_failure card."),
    ("verification_at_current_pin",
     "K3, on linux-wsl2-x86_64, from the generated component evidence matrix. Winners: 0 host_verified (derived "
     "accepted on an independently reviewed native_proven use-stage host receipt bound to the current pin and not "
     "superseded), 1 derived accepted by another route, 2 derived conditional, 3 derived not_established or "
     "untested. Level 1 includes the registered-evidence route of scripts/platform_status.py (a native_proven or "
     "measured_comparison winner citing a registered evidence/ file), which is not bound to the current pin; only "
     "level 0 is. The declared catalog_status never enters. Alternatives: 0 host_verified, 1 otherwise; "
     "receipts_recorded (a receipt of the stack component sharing the repository, possibly install-only or from "
     "another layer) is an annotation, not a level. Card-only candidates: the constant 0. Levels compare only "
     "within one role."),
    ("measured_rank",
     "K4. 0 unless every member of a K1-K3 tie class has a verified result in one comparability group: layer, the "
     "metric equal to the layer's overturn_protocol metric, benchmark or harness id and major version, fixture "
     "sha256 set, host profile, pins and direction. Inside the group: the approximate rank from non-overlapping "
     "intervals (the number of members whose interval lies entirely better); without intervals, an exact pass before "
     "an exact fail on the same frozen fixture; otherwise a tie. Unverified results never order anything. No layer "
     "records structured measurements in this version, so the key is 0 everywhere."),
    ("position",
     "Competition ranking within one layer: 1 plus the number of ranked placements of the layer with a strictly "
     "smaller sort_key (keys compared lexicographically, no arithmetic across keys). There is no order across "
     "layers."),
    ("shared",
     "True when another ranked placement of the layer has the same sort_key; the page shows =n and lists tied "
     "placements by entity reference, an order the position does not count."),
    ("outside_ranking",
     "Placements whose governing disposition is out_of_scope: listed with their records, never ranked."),
    ("caution",
     "Placements whose governing disposition is observed_failure, which scripts/landscape.py allows on a card only "
     "with execution evidence and a retained local result: listed, never ranked."),
    ("pin_current",
     "Upstream pin currency of a winner, from the matrix convergence components that match its component id: true "
     "when every matching in-use manifest row compared the pin as current, false when any compared it as behind, "
     "unknown otherwise (no matching row, or none compared). Display only, never a sort key: a current release does "
     "not supersede an accepted pin (catalogs/landscape/manifest.json rules), and metadata recency alone is "
     "insufficient."),
    ("entity",
     "repo:<owner>/<name> from catalog_decisions.canonical(catalog_decisions.identity(value)) over the coverage "
     "aliases. The universe is the decision-index records; the index adds no identity of its own, and a value that "
     "does not resolve is listed in unresolved with its reason."),
    ("placement",
     "One per (layer, entity), with every source record kept in role_records; role precedence winner, then "
     "alternative, then candidate. One entity can hold a different placement in each layer."),
    ("matrix_record",
     "For a winner or alternative, the pointer to its entry in the generated component evidence matrix, which keeps "
     "the winner's pin verbatim. The index does not repeat pins, so no bare 40-hex commit id appears in it: this "
     "file names Sourcegraph repositories, and the secret scan's Sourcegraph rule then reads such an id as a leak."),
    ("component_ids",
     "manifests/stack.json ids with the entity's repository plus matrix winner ids: a has-a list, never merged and "
     "never an identity. Status binding stays the matrix's, by each winner's own id."),
    ("receipts",
     "manifests/evidence.json receipts[] attach to an entity through a stack component id, else through a matrix "
     "winner id; a receipt that names neither is listed in evidence.receipts_unattached."),
    ("reached_as",
     "index_input (read for records), matrix_input (a file scripts/component_matrix.py reads), "
     "decision_index_source (a decision-index source) or not_reached (listed, and parsed only for a top-level "
     "non_repository_decisions array), in that precedence."),
    ("unmodeled_collections",
     "Every top-level non_repository_decisions array of a listed file, plus manifests/stack.json#/models and "
     "catalogs/us-equities/models.json#/entries: records that a repository identity cannot hold."),
    ("status_items",
     "Read-only status items (type, level, message, refs) in the Backstage descriptor pattern: conflicts and stale "
     "entries are flagged, never resolved, and never reorder anything."),
)

RULE = {
    "version": 1,
    "frozen_at": FROZEN_AT,
    "keys": ["recorded_role", "evidence_tier", "verification_at_current_pin", "measured_rank"],
    "blended_score": False,
    "tie": "competition",
    "verification_platform": PLATFORM,
    "tier_map": {
        "tiers": list(TIERS),
        "evidence_class": dict(sorted(CLASS_TIERS.items())),
        "evidence_kind": dict(sorted(KIND_TIERS.items())),
        "mixed": {"with_retained_local_result": "A", "without_retained_local_result": "C"},
        "policy_rows": {"A": list(POLICY_ROWS["A"]),
                        "B": POLICY_ROWS["local_integration"] + POLICY_ROWS["synthetic"], "C": [], "U": []},
    },
    "verification_levels": {role: dict(sorted(levels.items())) for role, levels in VERIFICATION_LEVELS.items()},
    "measured": {"comparability_fields": list(COMPARABILITY_FIELDS), "directions": list(DIRECTIONS),
                 "method": "approximate_rank", "requires_verified": True,
                 "without_intervals": "exact pass before exact fail on the same frozen fixture"},
    "never_sort_keys": ["stars", "pin_behind_upstream", "pin_current", "releases", "archived", "review_status",
                        "votes", "confidence", "latest", "catalog_status (declared)",
                        "e2e_state (its declared fallback)", "disposition within a role", "priority"],
    "definitions": [{"term": term, "definition": text} for term, text in DEFINITIONS],
}


class InvalidIndex(ValueError):
    """A fatal check failed; the message starts with the check's name (F1-F16)."""


def fail(check: str, message: str):
    raise InvalidIndex(f"{check}: {message}")


def require(condition, check: str, message: str) -> None:
    if not condition:
        fail(check, message)


# --------------------------------------------------------------------------------------------------- the rule


def has_retained_local_result(evidence_refs) -> bool:
    """scripts/landscape.py's observed_failure predicate: some ref is local and ends .json, .txt or .log."""
    return any(isinstance(ref, str) and not ref.startswith("https://") and ref.endswith(RETAINED_RESULT_SUFFIXES)
               for ref in evidence_refs or ())


def evidence_tier(field, recorded, retained_local_result=False) -> str:
    """K2 tier of a recorded evidence value; an unknown field or value fails closed (F13)."""
    if field == "evidence_class":
        require(recorded in CLASS_TIERS, "F13", f"unknown evidence_class {recorded!r}")
        return CLASS_TIERS[recorded]
    require(field == "evidence_kind", "F13", f"unknown evidence field {field!r}")
    if recorded == MIXED_KIND:
        return "A" if retained_local_result is True else "C"
    require(recorded in KIND_TIERS, "F13", f"unknown evidence_kind {recorded!r}")
    return KIND_TIERS[recorded]


def policy_rows(tier: str, recorded) -> list[str]:
    if tier == "A":
        return list(POLICY_ROWS["A"])
    return list(POLICY_ROWS.get(recorded, ()))


def verification_level(role, state) -> int:
    """K3 level of a verification state within its role; an unknown role or state fails closed (F13)."""
    levels = VERIFICATION_LEVELS.get(role)
    require(levels is not None, "F13", f"unknown role {role!r}")
    require(state in levels, "F13", f"unknown {role} verification state {state!r}")
    return levels[state]


def sort_key(placement: dict) -> list[int]:
    """[K1, K2, K3, K4], recomputed from the placement's recorded role, evidence and verification state. A stored
    tier or level that differs from the recomputed one fails (F5), so a reader re-derives the order itself."""
    role = placement.get("role")
    require(role in ROLE_RANK, "F13", f"unknown role {role!r}")
    entity = placement.get("entity")
    evidence = placement.get("evidence") if isinstance(placement.get("evidence"), dict) else {}
    require(evidence.get("field") == EVIDENCE_FIELDS[role], "F13",
            f"{entity}: a {role} reads {EVIDENCE_FIELDS[role]}, not {evidence.get('field')!r}")
    tier = evidence_tier(evidence.get("field"), evidence.get("recorded"), evidence.get("retained_local_result"))
    require(evidence.get("tier", tier) == tier, "F5",
            f"{entity}: stored evidence tier {evidence.get('tier')!r} differs from the rule's {tier!r}")
    verification = placement.get("verification") if isinstance(placement.get("verification"), dict) else {}
    level = verification_level(role, verification.get("state"))
    require(verification.get("level", level) == level, "F5",
            f"{entity}: stored verification level {verification.get('level')!r} differs from the rule's {level}")
    measured = placement.get("measured") if isinstance(placement.get("measured"), dict) else {}
    rank = measured.get("rank", 0)
    require(type(rank) is int and rank >= 0, "F8", f"{entity}: measured rank must be a nonnegative integer")
    return [ROLE_RANK[role], TIER_RANK[tier], level, rank]


def positions(keys) -> list[tuple[int, bool]]:
    """(position, shared) per key: competition ranking (1, 1, 3), 1 plus the number of strictly smaller keys."""
    keys = [tuple(key) for key in keys]
    return [(1 + sum(1 for other in keys if other < key), sum(1 for other in keys if other == key) > 1)
            for key in keys]


def comparability_key(measurement: dict) -> str:
    """The comparability group of a measurement, as canonical JSON of COMPARABILITY_FIELDS (fixture sha256 set
    sorted)."""
    values = {field: measurement.get(field) for field in COMPARABILITY_FIELDS}
    if isinstance(values["fixture_sha256"], list):
        values["fixture_sha256"] = sorted(values["fixture_sha256"], key=str)
    return json.dumps([values[field] for field in COMPARABILITY_FIELDS], sort_keys=True, separators=(",", ":"))


def _interval(measurement: dict):
    value = measurement.get("interval")
    if (isinstance(value, list) and len(value) == 2 and all(type(item) in (int, float) for item in value)
            and value[0] <= value[1]):
        return value[0], value[1]
    return None


def measured_split(members, measurements, *, layer, metric) -> dict:
    """K4 for one K1-K3 tie class: entity -> {group, rank, basis}. The class splits only when every member has
    exactly one verified result in one common comparability group; otherwise every member keeps rank 0."""
    members = sorted(set(members))

    def tie(basis, group=None):
        return {member: {"group": group, "rank": 0, "basis": basis} for member in members}

    relevant = [item for item in measurements or () if isinstance(item, dict) and item.get("layer") == layer
                and item.get("metric") == metric and item.get("entity") in members]
    if not relevant:
        return tie(NO_MEASUREMENT)
    if len(members) < 2:
        return tie("a placement without a tie: a measurement has nothing to split")
    groups: dict[str, dict[str, list]] = {member: {} for member in members}
    for item in relevant:
        if item.get("verified") is True:
            groups[item["entity"]].setdefault(comparability_key(item), []).append(item)
    common = set.intersection(*(set(found) for found in groups.values()))
    if len(common) != 1:
        return tie("not every tied placement has a verified result in one comparability group; unverified results "
                   "never order anything")
    group = common.pop()
    if any(len(groups[member][group]) != 1 for member in members):
        return tie("more than one verified result for a placement in the comparability group", group)
    results = {member: groups[member][group][0] for member in members}
    direction = results[members[0]].get("direction")
    intervals = {member: _interval(results[member]) for member in members}
    if direction in DIRECTIONS and all(value is not None for value in intervals.values()):
        def better(one, other):
            (one_low, one_high), (other_low, other_high) = intervals[one], intervals[other]
            return one_low > other_high if direction == "higher_is_better" else one_high < other_low

        ranks = {member: sum(1 for other in members if other != member and better(other, member))
                 for member in members}
        basis = "approximate rank from non-overlapping intervals in one comparability group"
    elif all(intervals[member] is None and results[member].get("outcome") in OUTCOMES for member in members):
        ranks = {member: 0 if results[member]["outcome"] == "pass" else 1 for member in members}
        basis = "exact pass or fail on the same frozen fixture"
    else:
        return tie("no intervals and no exact pass or fail on the same frozen fixture", group)
    return {member: {"group": group, "rank": ranks[member], "basis": basis} for member in members}


def rank_layer(placements, measurements, *, layer, metric) -> list[dict]:
    """Assign tier, level, measured rank, sort_key, position and shared to one layer's ranked placements, and return
    them in display order: position, then entity reference."""
    for placement in placements:
        evidence, verification = placement["evidence"], placement["verification"]
        evidence["tier"] = evidence_tier(evidence.get("field"), evidence.get("recorded"),
                                         evidence.get("retained_local_result"))
        verification["level"] = verification_level(placement.get("role"), verification.get("state"))
    classes: dict[tuple, list[dict]] = {}
    for placement in placements:
        key = (ROLE_RANK[placement["role"]], TIER_RANK[placement["evidence"]["tier"]],
               placement["verification"]["level"])
        classes.setdefault(key, []).append(placement)
    for key in sorted(classes):
        members = classes[key]
        split = measured_split([member["entity"] for member in members], measurements, layer=layer, metric=metric)
        for member in members:
            member["measured"] = dict(split[member["entity"]])
    keys = [sort_key(placement) for placement in placements]
    for placement, key, (position, shared) in zip(placements, keys, positions(keys)):
        placement.update(sort_key=key, position=position, shared=shared)
    return sorted(placements, key=lambda placement: (placement["position"], placement["entity"]))


# --------------------------------------------------------------------------------------------------- reading


class Reader:
    """Every JSON input is parsed here, once, with catalog_decisions.load, so duplicate keys and path escapes fail
    (F12). ``inputs`` and ``scanned`` record what was read, which F12 compares with INPUTS and the listing."""

    def __init__(self, root: Path):
        self.root = root
        self.documents: dict[str, object] = {}
        self.inputs: set[str] = set()
        self.scanned: set[str] = set()

    def parse(self, relative: str):
        if relative not in self.documents:
            try:
                self.documents[relative] = catalog_decisions.load(self.root, relative)
            except catalog_decisions.InvalidDecisionIndex as error:
                fail("F12", f"{relative}: {error}")
        return self.documents[relative]

    def input(self, relative: str):
        self.inputs.add(relative)
        return self.parse(relative)

    def scan(self, relative: str):
        self.scanned.add(relative)
        return self.parse(relative)


def catalog_listing(root: Path) -> list[str]:
    """Sorted repository-relative paths of catalogs/**/*.json and manifests/*.json, without OUTPUT_JSON."""
    paths = set()
    for base, pattern in LISTING_GLOBS:
        directory = root / base
        if directory.is_dir():
            paths.update(path.relative_to(root).as_posix() for path in directory.glob(pattern) if path.is_file())
    paths.discard(OUTPUT_JSON)
    return sorted(paths)


def load_measurements(reader: Reader) -> list[dict]:
    """Structured, comparable measurements. No committed source records them in this version, so this is empty;
    the later option feeds it from a validated comparability block in convergence records."""
    return []


def check_measurements(measurements, reader: Reader) -> list[dict]:
    """F8 for every listed measurement: all comparability fields, a JSON number that is the number at its source
    pointer in an already-read file, and a well-formed interval and outcome."""
    require(isinstance(measurements, list), "F8", "measurements must be a list")
    checked = []
    for number, item in enumerate(measurements):
        where = f"measurements[{number}]"
        require(isinstance(item, dict), "F8", where + " must be an object")
        missing = [field for field in (*COMPARABILITY_FIELDS, "entity", "verified", "value", "source")
                   if field not in item]
        require(not missing, "F8", f"{where} lacks {', '.join(missing)}")
        require(item["direction"] in DIRECTIONS, "F8", f"{where}: unknown direction {item['direction']!r}")
        require(isinstance(item["verified"], bool), "F8", f"{where}: verified must be true or false")
        require(isinstance(item["fixture_sha256"], list) and item["fixture_sha256"], "F8",
                f"{where}: fixture_sha256 must be a nonempty list")
        value, source = item["value"], item["source"]
        require(type(value) in (int, float), "F8", f"{where}: value must be a JSON number")
        require(isinstance(source, dict) and isinstance(source.get("path"), str)
                and isinstance(source.get("pointer"), str), "F8", f"{where}: source needs a path and a pointer")
        document = reader.documents.get(source["path"])
        require(document is not None, "F8", f"{where}: source {source['path']} is not in the read set")
        try:
            target = catalog_decisions.pointer(document, source["pointer"])
        except catalog_decisions.InvalidDecisionIndex as error:
            fail("F8", f"{where}: source pointer does not resolve ({error})")
        require(type(target) in (int, float) and target == value, "F8",
                f"{where}: value is not the JSON number at {source['path']}#{source['pointer']}")
        require(item.get("interval") is None or _interval(item) is not None, "F8",
                f"{where}: interval must be [low, high] numbers with low <= high")
        require(item.get("outcome") is None or item["outcome"] in OUTCOMES, "F8",
                f"{where}: outcome must be pass or fail")
        checked.append(copy.deepcopy(item))
    return sorted(checked, key=lambda item: (str(item["layer"]), str(item["entity"]), comparability_key(item),
                                             json.dumps(item, sort_keys=True)))


def check_vocabularies() -> None:
    """F13: this rule's tables still cover the vocabularies the validators enforce."""
    require(set(CLASS_TIERS) == set(landscape.WINNER_EVIDENCE_CLASSES), "F13",
            "landscape.WINNER_EVIDENCE_CLASSES changed; update CLASS_TIERS and the decision record")
    require(set(KIND_TIERS) | {MIXED_KIND} == set(landscape.EVIDENCE_KINDS), "F13",
            "landscape.EVIDENCE_KINDS changed; update KIND_TIERS and the decision record")
    require(set(VERIFICATION_LEVELS["winner"]) == set(platform_status.STATUS_RANK) | {"host_verified"}, "F13",
            "platform_status.STATUS_RANK changed; update VERIFICATION_LEVELS and the decision record")
    require(set(OUTSIDE_REASONS) <= set(landscape.DISPOSITIONS), "F13", "landscape.DISPOSITIONS changed")


def _pointer_key(pointer: str) -> tuple:
    return tuple((0, int(part), "") if part.isdigit() else (1, 0, part) for part in pointer.split("/"))


def _mapping(value, check: str, message: str) -> dict:
    require(isinstance(value, dict), check, message)
    return value


def _count(value, check: str, message: str) -> int:
    require(type(value) is int and value >= 0, check, message)
    return value


# --------------------------------------------------------------------------------------------------- building


class _Build:
    def __init__(self, root: Path, reader: Reader, aliases: dict, universe: dict, measurements: list[dict]):
        self.root, self.reader, self.aliases, self.universe = root, reader, aliases, universe
        self.measurements = measurements
        self.items: list[dict] = []
        self.unresolved: list[dict] = []
        self.flags: dict[tuple[str, str], set[str]] = {}

    def resolve(self, value):
        """(entity reference, None), or (None, the reason it does not resolve)."""
        try:
            name = catalog_decisions.canonical(catalog_decisions.identity(value), self.aliases)
        except catalog_decisions.InvalidDecisionIndex as error:
            return None, f"repository identity rejected ({error})"
        if name not in self.universe:
            return None, f"{name} is not a record of {DECISION_INDEX_FILE}"
        return ENTITY_PREFIX + name, None

    def item(self, item_type: str, message: str, refs, flagged=()) -> None:
        self.items.append({"type": item_type, "level": STATUS_TYPES[item_type], "message": message,
                           "refs": list(refs)})
        for layer_ref, entity in flagged:
            self.flags.setdefault((layer_ref, entity), set()).add(item_type)

    def unresolved_record(self, path: str, pointer: str, reason: str, layer_ref=None) -> None:
        self.unresolved.append({"path": path, "pointer": pointer, "reason": reason})
        refs = ([layer_ref] if layer_ref else []) + [f"{path}#{pointer}"]
        self.item("identity/unresolved", f"{path}#{pointer}: {reason}; listed in unresolved, never dropped", refs)

    def layer_records(self, catalog: str, path: str, layer_index: int, ledger_layer: dict, row_index: int,
                      row: dict, layer_ref: str) -> list[dict]:
        """Every source record of one layer: verdict winners and alternatives joined to their matrix entries by
        position, then the ledger's historical candidate cards. An unresolved record keeps entity None."""
        records = []
        for key, role in (("winners", "winner"), ("alternatives", "alternative")):
            ledger_entries, matrix_entries = ledger_layer.get(key), row.get(key)
            require(isinstance(ledger_entries, list) and isinstance(matrix_entries, list)
                    and len(ledger_entries) == len(matrix_entries), "F2",
                    f"{layer_ref}: the matrix {key} differ from the ledger; run python3 scripts/component_matrix.py "
                    "--write")
            for number, (ledger_entry, matrix_entry) in enumerate(zip(ledger_entries, matrix_entries)):
                require(isinstance(ledger_entry, dict) and isinstance(matrix_entry, dict), "F2",
                        f"{layer_ref}: {key} entries must be objects")
                disposition = None
                if role == "alternative":
                    for value in (matrix_entry.get("disposition"), ledger_entry.get("disposition")):
                        require(value in landscape.DISPOSITIONS, "F13",
                                f"{layer_ref}: unknown alternative disposition {value!r}")
                    disposition = ledger_entry.get("disposition")
                name_field = "component_id" if role == "winner" else "name"
                require(ledger_entry.get(name_field) == matrix_entry.get(name_field)
                        and ledger_entry.get("repository") == matrix_entry.get("repository")
                        and (role == "winner" or matrix_entry.get("disposition") == disposition), "F2",
                        f"{layer_ref}: {key}[{number}] differs between the matrix and the ledger; run python3 "
                        "scripts/component_matrix.py --write")
                pointer = f"/layers/{layer_index}/{key}/{number}"
                entity, reason = self.resolve(matrix_entry.get("repository"))
                if entity is None:
                    self.unresolved_record(path, pointer, reason, layer_ref)
                records.append({"entity": entity, "role": role, "path": path, "pointer": pointer,
                                "disposition": disposition, "matrix": matrix_entry, "ledger": ledger_entry,
                                "matrix_pointer": f"/rows/{row_index}/{key}/{number}"})
        cards = ledger_layer.get("candidates")
        require(isinstance(cards, list), "F2", f"{layer_ref}: candidates must be a list")
        for number, card in enumerate(cards):
            require(isinstance(card, dict), "F2", f"{layer_ref}: candidates[{number}] must be an object")
            require(card.get("disposition") in landscape.DISPOSITIONS, "F13",
                    f"{layer_ref}: unknown candidate disposition {card.get('disposition')!r}")
            require(card.get("evidence_kind") in landscape.EVIDENCE_KINDS, "F13",
                    f"{layer_ref}: unknown candidate evidence_kind {card.get('evidence_kind')!r}")
            pointer = f"/layers/{layer_index}/candidates/{number}"
            entity, reason = self.resolve(card.get("repository"))
            if entity is None:
                self.unresolved_record(path, pointer, reason, layer_ref)
            records.append({"entity": entity, "role": "candidate", "path": path, "pointer": pointer,
                            "disposition": card.get("disposition"), "matrix": None, "ledger": card,
                            "matrix_pointer": None})
        return records

    def winner_pin_current(self, component_id, components: list[dict]):
        values = [component["pin_current"] for component in components if component_id in component["winner_ids"]]
        if "false" in values:
            return "false"
        return "true" if values and all(value == "true" for value in values) else "unknown"

    def entry(self, entity: str, records: list[dict], layer_ref: str, pending: bool, components: list[dict]):
        """One placement (or outside/caution entry) of ``entity`` in the layer, from all of its records."""
        records.sort(key=lambda record: (ROLE_RANK[record["role"]], record["path"], _pointer_key(record["pointer"])))
        governing = records[0]
        role = governing["role"]
        require(not pending or role == "candidate", "F4",
                f"{layer_ref}: a pending_lanes layer has a {role} role for {entity}")
        entry = {
            "entity": entity, "role": role,
            "role_records": [{"path": record["path"], "pointer": record["pointer"], "role": record["role"],
                              "disposition": record["disposition"]} for record in records],
            "matrix_record": ({"path": MATRIX_FILE, "pointer": governing["matrix_pointer"]}
                              if governing["matrix_pointer"] else None),
        }
        cards = [record for record in records if record["role"] == "candidate"]
        if any(card["disposition"] == "selected" for card in cards):
            if pending:
                self.item("role/selected-card-no-verdict",
                          f"{entity}: a historical candidate card records disposition selected in {layer_ref}, which "
                          "has no recorded verdict (pending_lanes); the card orders nothing beyond its evidence tier",
                          [layer_ref, entity], [(layer_ref, entity)])
            elif role != "winner":
                self.item("role/selected-card-not-winner",
                          f"{entity}: a historical candidate card records disposition selected in {layer_ref}, but "
                          f"the recorded verdict role is {role}; the verdict governs and the card stays in "
                          "role_records", [layer_ref, entity], [(layer_ref, entity)])
        unselected = sorted({card["disposition"] for card in cards if card["disposition"] != "selected"})
        if role == "winner" and unselected:
            self.item("role/winner-card-not-selected",
                      f"{entity}: the recorded verdict winner of {layer_ref} has a historical candidate card with "
                      f"disposition {', '.join(unselected)}; the verdict governs", [layer_ref, entity],
                      [(layer_ref, entity)])
        if role != "winner" and governing["disposition"] in OUTSIDE_REASONS:
            entry["reason"] = governing["disposition"]
            return entry
        if role == "candidate":
            card = governing["ledger"]
            refs = card.get("evidence_refs") if isinstance(card.get("evidence_refs"), list) else []
            field, recorded, retained = "evidence_kind", card.get("evidence_kind"), has_retained_local_result(refs)
        else:
            field, recorded, retained = "evidence_class", governing["matrix"].get("evidence_class"), None
        tier = evidence_tier(field, recorded, retained)
        entry["evidence"] = {"field": field, "recorded": recorded, "tier": tier, "retained_local_result": retained,
                             "policy_rows": policy_rows(tier, recorded)}
        entry["component_id"] = None
        entry["freshness"] = {"pin_current": None}
        if role == "winner":
            winner = governing["matrix"]
            platforms = _mapping(winner.get("platforms"), "F13", f"{entity}: winner platforms must be an object")
            linux = _mapping(platforms.get(PLATFORM), "F13", f"{entity}: no {PLATFORM} entry")
            macos = _mapping(platforms.get(MACOS_PLATFORM), "F13", f"{entity}: no {MACOS_PLATFORM} entry")
            declared, derived, e2e = linux.get("catalog_status"), linux.get("derived_status"), linux.get("e2e_state")
            for label, value in (("catalog_status", declared), ("derived_status", derived),
                                 ("macOS derived_status", macos.get("derived_status"))):
                require(value in platform_status.STATUS_RANK, "F13", f"{entity}: unknown {label} {value!r}")
            require(e2e == "host_verified" or e2e in platform_status.STATUS_RANK, "F13",
                    f"{entity}: unknown e2e_state {e2e!r}")
            require(e2e != "host_verified" or derived == "accepted", "F13",
                    f"{entity}: e2e_state host_verified needs derived_status accepted")
            receipts = _mapping(linux.get("host_receipts"), "F13", f"{entity}: no {PLATFORM} host_receipts")
            state = "host_verified" if e2e == "host_verified" else derived
            entry["verification"] = {
                "state": state, "level": verification_level(role, state), "declared": declared,
                "macos": macos.get("derived_status"),
                "host_receipts": {key: _count(receipts.get(key, 0), "F13", f"{entity}: host_receipts.{key}")
                                  for key in ("pass", "fail", "independently_reviewed_pass")}}
            entry["component_id"] = winner.get("component_id")
            entry["freshness"]["pin_current"] = self.winner_pin_current(winner.get("component_id"), components)
        elif role == "alternative":
            state = governing["matrix"].get("e2e_state")
            require(state in ALTERNATIVE_E2E_STATES, "F13", f"{entity}: unknown alternative e2e_state {state!r}")
            entry["verification"] = {"state": state, "level": verification_level(role, state), "declared": None,
                                     "macos": None, "host_receipts": None}
        else:
            entry["verification"] = {"state": "not_applicable", "level": 0, "declared": None, "macos": None,
                                     "host_receipts": None}
        entry["measured"] = {"group": None, "rank": 0, "basis": NO_MEASUREMENT}
        return entry

    def placement_items(self, layer_ref: str, placements: list[dict], layer_state, reopened_by) -> dict:
        """Status items of one layer's ranked placements; returns the layer's overturn-metric counts."""
        for placement in placements:
            entity, evidence, verification = placement["entity"], placement["evidence"], placement["verification"]
            flagged = [(layer_ref, entity)]
            if evidence["recorded"] == MIXED_KIND:
                self.item("evidence/mixed-kind",
                          f"{entity}: evidence_kind mixed maps to tier {evidence['tier']} "
                          f"({'with' if evidence['retained_local_result'] else 'without'} a retained local result)",
                          [layer_ref, entity], flagged)
            if evidence["tier"] == "U":
                self.item("evidence/unmapped-kind",
                          f"{entity}: evidence_kind {evidence['recorded']} has no acceptance-policy row; tier U sorts "
                          "after source review", [layer_ref, entity], flagged)
            if placement["role"] == "winner":
                derived = "accepted" if verification["state"] == "host_verified" else verification["state"]
                if platform_status.STATUS_RANK[verification["declared"]] > platform_status.STATUS_RANK[derived]:
                    self.item("status/declared-above-derived",
                              f"{entity}: {PLATFORM} catalog_status declares {verification['declared']} but the "
                              f"recorded evidence derives {derived} (scripts/platform_status.py); the index orders on "
                              "the derived status", [layer_ref, entity], flagged)
                if verification["host_receipts"]["fail"] > 0:
                    self.item("verification/host-fail-recorded",
                              f"{entity}: {verification['host_receipts']['fail']} failing {PLATFORM} host receipt(s) "
                              f"recorded for component {placement['component_id']}", [layer_ref, entity], flagged)
                if placement["freshness"]["pin_current"] != "true":
                    self.item("freshness/pin-behind-upstream",
                              f"{entity}: pin_current is {placement['freshness']['pin_current']} for component "
                              f"{placement['component_id']} (display only, never a sort key)", [layer_ref, entity],
                              flagged)
            if placement["role"] == "alternative" and verification["state"] != "not_run":
                self.item("verification/joined-by-repository",
                          f"{entity}: alternative e2e_state {verification['state']} comes from the stack component "
                          "that shares its repository, not from a record of this layer", [layer_ref, entity], flagged)
        winners = [placement for placement in placements if placement["role"] == "winner"]
        alternatives = [placement for placement in placements if placement["role"] == "alternative"]
        pairs = [(winner, alternative) for winner in winners for alternative in alternatives
                 if TIER_RANK[winner["evidence"]["tier"]] > TIER_RANK[alternative["evidence"]["tier"]]]
        if pairs:
            below = sorted({winner["entity"] for winner, _alternative in pairs})
            above = sorted({alternative["entity"] for _winner, alternative in pairs})
            self.item("evidence/winner-tier-below-alternative",
                      f"{layer_ref}: winner(s) {', '.join(below)} record a lower evidence tier than alternative(s) "
                      f"{', '.join(above)}; the recorded role still orders first, and an overturn comparison may be "
                      "owed", [layer_ref, *below, *above], [(layer_ref, entity) for entity in below])
        flipped = winner_pairs = 0

        def class_first(key):
            return key[0], key[1], key[2]

        def verification_first(key):
            return key[0], key[2], key[1]

        for number, first in enumerate(placements):
            for second in placements[number + 1:]:
                one, other = first["sort_key"], second["sort_key"]
                if class_first(one) < class_first(other) and verification_first(other) < verification_first(one):
                    ahead, behind = first, second
                elif class_first(other) < class_first(one) and verification_first(one) < verification_first(other):
                    ahead, behind = second, first
                else:
                    continue
                flipped += 1
                winner_pairs += "winner" in (first["role"], second["role"])
                self.item("evidence/class-verification-inversion",
                          f"{layer_ref}: {ahead['entity']} precedes {behind['entity']} on evidence tier, while "
                          f"{behind['entity']} precedes it on verification at the current pin; evidence tier "
                          "orders first", [layer_ref, *sorted((ahead["entity"], behind["entity"]))],
                          [(layer_ref, ahead["entity"]), (layer_ref, behind["entity"])])
        if layer_state == "recorded_reopened":
            sweeps = ", ".join(str(sweep.get("sweep_id")) for sweep in reopened_by)
            self.item("freshness/layer-reopened",
                      f"{layer_ref}: a completed sweep dated after the verdict ({sweeps}) covers this layer; the "
                      "recorded roles stand until the verdict is re-recorded", [layer_ref])
        return {"flipped": flipped, "winner_pairs": winner_pairs}

    def layer(self, catalog: str, path: str, layer_index: int, ledger_layer: dict, row_index: int, row: dict):
        layer_id = ledger_layer["layer_id"]
        layer_ref = f"layer:{catalog}/{layer_id}"
        verdict_status = row.get("verdict_status")
        require(verdict_status in landscape.VERDICT_STATUSES, "F13",
                f"{layer_ref}: unknown verdict_status {verdict_status!r}")
        require(ledger_layer.get("verdict_status") == verdict_status, "F2",
                f"{layer_ref}: the matrix verdict_status differs from the ledger; run python3 "
                "scripts/component_matrix.py --write")
        review = row.get("independent_review")
        require(review in component_matrix.INDEPENDENT_REVIEW_STATES, "F13",
                f"{layer_ref}: unknown independent_review {review!r}")
        decision = ledger_layer.get("decision")
        require(decision in landscape.DECISIONS, "F13", f"{layer_ref}: unknown decision {decision!r}")
        convergence = _mapping(row.get("convergence"), "F13", f"{layer_ref}: the matrix row has no convergence object")
        layer_state = convergence.get("layer_state")
        require(layer_state in component_matrix.CONVERGENCE_LAYER_STATES, "F13",
                f"{layer_ref}: unknown layer_state {layer_state!r}")
        reopened_by = convergence.get("reopened_by")
        require(isinstance(reopened_by, list) and all(isinstance(sweep, dict) for sweep in reopened_by), "F13",
                f"{layer_ref}: reopened_by must be a list of sweeps")
        components = convergence.get("components")
        require(isinstance(components, list), "F13", f"{layer_ref}: convergence components must be a list")
        for component in components:
            require(isinstance(component, dict) and isinstance(component.get("winner_ids"), list)
                    and component.get("pin_current") in PIN_CURRENT_VALUES, "F13",
                    f"{layer_ref}: a convergence component needs winner_ids and a known pin_current")
        open_gaps = row.get("open_gaps")
        require(open_gaps is None or type(open_gaps) is int, "F13", f"{layer_ref}: open_gaps must be an integer")
        protocol = ledger_layer.get("overturn_protocol") if isinstance(ledger_layer.get("overturn_protocol"), dict) else {}
        metric = protocol.get("metric") if isinstance(protocol.get("metric"), str) else None
        pending = verdict_status == "pending_lanes"

        records = self.layer_records(catalog, path, layer_index, ledger_layer, row_index, row, layer_ref)
        by_entity: dict[str, list[dict]] = {}
        for record in records:
            if record["entity"] is not None:
                by_entity.setdefault(record["entity"], []).append(record)
        ranked, outside, caution = [], [], []
        for entity in sorted(by_entity):
            entry = self.entry(entity, by_entity[entity], layer_ref, pending, components)
            reason = entry.get("reason")
            (ranked if reason is None else outside if reason == "out_of_scope" else caution).append(entry)
        for record in records:
            if record["role"] == "winner" and record["entity"] is not None:
                require(any(entry["entity"] == record["entity"] and entry["role"] == "winner" for entry in ranked),
                        "F4", f"{layer_ref}: matrix winner {record['matrix'].get('component_id')} has no winner "
                        "placement")
        ranked = rank_layer(ranked, self.measurements, layer=layer_ref, metric=metric)
        metrics = self.placement_items(layer_ref, ranked, layer_state, reopened_by)
        for entry in ranked + outside + caution:
            entry["flags"] = sorted(self.flags.get((layer_ref, entry["entity"]), ()))
        note = (PENDING_NOTE if pending else REOPENED_NOTE if layer_state == "recorded_reopened"
                else NO_SELECTION_NOTE if layer_state == "no_selection" else "")
        resolved = sum(1 for record in records if record["entity"] is not None)
        layer = {
            "ref": layer_ref, "catalog": catalog, "layer_id": layer_id, "title": row.get("title"),
            "source": {"path": path, "pointer": f"/layers/{layer_index}"},
            "banner": {"decision": decision, "verdict_status": verdict_status, "independent_review": review,
                       "layer_state": layer_state, "verdict_checked_at": convergence.get("verdict_checked_at"),
                       "reopened_by": [{"sweep_id": sweep.get("sweep_id"), "date": sweep.get("date")}
                                       for sweep in reopened_by],
                       "open_gaps": open_gaps, "overturn_metric": metric, "note": note},
            "counts": {"records": len(records), "unresolved_records": len(records) - resolved,
                       "placements": len(by_entity), "ranked": len(ranked), "outside_ranking": len(outside),
                       "caution": len(caution)},
            "placements": ranked,
            "outside_ranking": sorted(outside, key=lambda entry: entry["entity"]),
            "caution": sorted(caution, key=lambda entry: entry["entity"]),
        }
        return layer, records, metrics


def entity_universe(decision_index, aliases: dict) -> dict[str, dict]:
    """Canonical owner/name -> decision-index record; every record must be canonical and unique (F12)."""
    records = decision_index.get("records") if isinstance(decision_index, dict) else None
    require(isinstance(records, list), "F12", f"{DECISION_INDEX_FILE}: records must be a list")
    universe: dict[str, dict] = {}
    for number, record in enumerate(records):
        where = f"{DECISION_INDEX_FILE}#/records/{number}"
        require(isinstance(record, dict), "F12", where + " must be an object")
        try:
            name = catalog_decisions.identity(record.get("repository"))
        except catalog_decisions.InvalidDecisionIndex as error:
            fail("F12", f"{where}: {error}")
        require(catalog_decisions.canonical(name, aliases) == name, "F12", f"{where}: {name} is an alias")
        require(name not in universe, "F12", f"{where}: duplicate record {name}")
        universe[name] = record
    return universe


def keyed_ledger_layers(ledgers: dict) -> dict:
    keyed = {}
    for catalog, path in LEDGER_FILES.items():
        layers = ledgers[catalog].get("layers") if isinstance(ledgers[catalog], dict) else None
        require(isinstance(layers, list), "F2", f"{path}: layers must be a list")
        for index, layer in enumerate(layers):
            require(isinstance(layer, dict) and isinstance(layer.get("layer_id"), str), "F2",
                    f"{path}: layers[{index}] needs a layer_id")
            key = (catalog, layer["layer_id"])
            require(key not in keyed, "F2", f"{path}: layer {layer['layer_id']} is listed twice")
            keyed[key] = (path, index, layer)
    return keyed


def keyed_matrix_rows(matrix) -> dict:
    rows = matrix.get("rows") if isinstance(matrix, dict) else None
    require(isinstance(rows, list), "F2", f"{MATRIX_FILE}: rows must be a list")
    keyed = {}
    for index, row in enumerate(rows):
        require(isinstance(row, dict), "F2", f"{MATRIX_FILE}: rows[{index}] must be an object")
        key = (row.get("catalog"), row.get("layer_id"))
        require(key not in keyed, "F2", f"{MATRIX_FILE}: layer {key} is listed twice")
        keyed[key] = (index, row)
    return keyed


def build_document(root) -> dict:
    """The index document for the tree at ``root``; every fatal check except F1 (staleness), F10 (size) and F11
    (private content), which main() applies to the serialized text, runs here."""
    root = Path(root).resolve()
    check_vocabularies()
    reader = Reader(root)
    matrix = reader.input(MATRIX_FILE)
    ledgers = {catalog: reader.input(path) for catalog, path in LEDGER_FILES.items()}
    decision_index = reader.input(DECISION_INDEX_FILE)
    reader.inputs.add(ALIASES_FILE)  # read by catalog_decisions.aliases_for, which validates the aliases
    try:
        aliases = catalog_decisions.aliases_for(root)
    except (catalog_decisions.InvalidDecisionIndex, OSError) as error:
        fail("F12", f"{ALIASES_FILE}: {error}")
    stack = reader.input(STACK_FILE)
    evidence = reader.input(EVIDENCE_FILE)
    landscape_manifest = reader.input(LANDSCAPE_MANIFEST_FILE)
    listing = catalog_listing(root)
    for relative in listing:
        reader.scan(relative)
    measurements = check_measurements(load_measurements(reader), reader)

    universal = landscape_manifest.get("universal_superiority") if isinstance(landscape_manifest, dict) else None
    require(universal == "not_established", "F7",
            f"{LANDSCAPE_MANIFEST_FILE}: universal_superiority must stay not_established")
    universe = entity_universe(decision_index, aliases)
    build = _Build(root, reader, aliases, universe, measurements)

    ledger_layers = keyed_ledger_layers(ledgers)
    matrix_rows = keyed_matrix_rows(matrix)
    require(set(ledger_layers) == set(matrix_rows), "F2",
            "the matrix layer set differs from the ledger layer set; run python3 scripts/component_matrix.py --write")
    require(len(matrix_rows) == EXPECTED_LAYER_COUNT, "F2",
            f"expected {EXPECTED_LAYER_COUNT} layers, found {len(matrix_rows)}; a layer added to or removed from a "
            "ledger updates EXPECTED_LAYER_COUNT and the decision record")
    layers, records_by_layer, flipped, winner_pairs = [], {}, 0, 0
    for catalog, layer_id in sorted(ledger_layers):
        path, layer_index, ledger_layer = ledger_layers[(catalog, layer_id)]
        row_index, row = matrix_rows[(catalog, layer_id)]
        layer, records, metrics = build.layer(catalog, path, layer_index, ledger_layer, row_index, row)
        layers.append(layer)
        records_by_layer[layer["ref"]] = records
        flipped += metrics["flipped"]
        winner_pairs += metrics["winner_pairs"]

    # Components: stack ids and matrix winner ids per entity, never merged.
    component_ids: dict[str, set[str]] = {}
    stack_profiles: dict[str, set[str]] = {}
    id_entities: dict[str, set[str]] = {}
    stack_entity: dict[str, str] = {}
    winner_entity: dict[str, str] = {}
    components = stack.get("components") if isinstance(stack, dict) else None
    require(isinstance(components, list), "F12", f"{STACK_FILE}: components must be a list")
    for number, component in enumerate(components):
        require(isinstance(component, dict) and isinstance(component.get("id"), str), "F12",
                f"{STACK_FILE}#/components/{number} needs an id")
        entity, reason = build.resolve(component.get("repository"))
        if entity is None:
            build.unresolved_record(STACK_FILE, f"/components/{number}", reason)
            continue
        component_ids.setdefault(entity, set()).add(component["id"])
        if isinstance(component.get("profile"), str):
            stack_profiles.setdefault(entity, set()).add(component["profile"])
        id_entities.setdefault(component["id"], set()).add(entity)
        stack_entity.setdefault(component["id"], entity)
    for records in records_by_layer.values():
        for record in records:
            if record["role"] == "winner" and record["entity"] is not None:
                component_id = record["matrix"].get("component_id")
                require(isinstance(component_id, str), "F13", f"{record['pointer']}: winner needs a component_id")
                component_ids.setdefault(record["entity"], set()).add(component_id)
                id_entities.setdefault(component_id, set()).add(record["entity"])
                winner_entity.setdefault(component_id, record["entity"])
    for entity in sorted(component_ids):
        if len(component_ids[entity]) > 1:
            ids = sorted(component_ids[entity])
            build.item("identity/multiple-component-ids",
                       f"{entity} carries component ids {', '.join(ids)}; they stay separate (never merged, never an "
                       "identity)", [entity, *("component:" + component_id for component_id in ids)])
    for component_id in sorted(id_entities):
        if len(id_entities[component_id]) > 1:
            build.item("identity/component-id-conflict",
                       f"component id {component_id} names more than one repository: "
                       f"{', '.join(sorted(id_entities[component_id]))}",
                       ["component:" + component_id, *sorted(id_entities[component_id])])

    # Receipts and experiments: receipts[] and convergence_records[] only.
    receipts = evidence.get("receipts") if isinstance(evidence, dict) else None
    require(isinstance(receipts, list), "F12", f"{EVIDENCE_FILE}: receipts must be a list")
    entity_receipts: dict[str, dict[str, str]] = {}
    unattached = []
    for number, receipt in enumerate(receipts):
        require(isinstance(receipt, dict) and isinstance(receipt.get("id"), str), "F12",
                f"{EVIDENCE_FILE}#/receipts/{number} needs an id")
        named = receipt.get("component_ids") if isinstance(receipt.get("component_ids"), list) else []
        targets = {stack_entity.get(component_id) or winner_entity.get(component_id) for component_id in named}
        targets.discard(None)
        for target in targets:
            entity_receipts.setdefault(target, {})[receipt["id"]] = str(receipt.get("kind"))
        if not targets:
            unattached.append({"id": receipt["id"],
                               "reason": "no component id names a manifests/stack.json component or a matrix winner"})
    convergence_records = evidence.get("convergence_records", []) if isinstance(evidence, dict) else None
    require(isinstance(convergence_records, list) and all(isinstance(item, str) for item in convergence_records),
            "F12", f"{EVIDENCE_FILE}: convergence_records must be a list of paths")
    experiments = [{"path": item, "joined": False, "reason": "no layer or component key"}
                   for item in sorted(convergence_records)]

    # Entities: the decision-index universe, each with its placements, components and receipts.
    entity_layers: dict[str, set[str]] = {}
    winner_entities = set()
    for layer in layers:
        for entry in layer["placements"] + layer["outside_ranking"] + layer["caution"]:
            entity_layers.setdefault(entry["entity"], set()).add(layer["ref"])
            if entry["role"] == "winner":
                winner_entities.add(entry["entity"])
    entities = []
    for name in sorted(universe):
        record = universe[name]
        ref = ENTITY_PREFIX + name
        references = [item for item in record.get("references") or [] if isinstance(item, dict)]
        kinds = Counter(item["kind"] for item in references if isinstance(item.get("kind"), str))
        attached = entity_receipts.get(ref, {})
        entities.append({
            "ref": ref, "aliases": sorted(item for item in record.get("aliases") or [] if isinstance(item, str)),
            "component_ids": sorted(component_ids.get(ref, ())), "stack_profiles": sorted(stack_profiles.get(ref, ())),
            "decision_index": {"repository": name, "reference_kinds": dict(sorted(kinds.items()))},
            "placements": sorted(entity_layers.get(ref, ())),
            "receipts": {"ids": sorted(attached), "kinds": dict(sorted(Counter(attached.values()).items()))},
        })
        defaults = [item for item in references if item.get("kind") == "catalog_card" and item.get("decision") == "default"]
        if defaults and ref not in winner_entities:
            build.item("domain-card/default-never-winner",
                       f"{ref}: a decision-index catalog_card records decision default, and no layer verdict names it "
                       "a winner", [ref, *sorted(f"{item.get('path')}#{item.get('pointer')}" for item in defaults)])

    # Coverage: every listed file with how the index reaches it, and the collections it cannot model.
    try:
        newest_manifest, _document = component_matrix.newest_sweep_manifest(root)
    except SystemExit as error:
        fail("F12", f"component_matrix.newest_sweep_manifest: {error}")
    matrix_inputs = {component_matrix.DECISIONS_FILE, component_matrix.GAP_CROSSWALK_FILE,
                     component_matrix.SATURATION_LEDGER_FILE, newest_manifest}
    sources = {item.get("path") for item in decision_index.get("sources") or [] if isinstance(item, dict)}
    catalog_files = []
    for relative in listing:
        reached = ("index_input" if relative in DECLARED_INPUT_PATHS else "matrix_input" if relative in matrix_inputs
                   else "decision_index_source" if relative in sources else "not_reached")
        catalog_files.append({"path": relative, "reached_as": reached})
        if reached == "not_reached":
            build.item("coverage/not-reached", f"{relative}: listed, but no record of it is joined into the index",
                       [relative])
    unmodeled = [{"path": relative, "pointer": "/" + NON_REPOSITORY_KEY} for relative in listing
                 if isinstance(reader.documents[relative], dict)
                 and isinstance(reader.documents[relative].get(NON_REPOSITORY_KEY), list)]
    for relative, pointer in UNMODELED_FIXED:
        if relative in reader.documents:
            try:
                target = catalog_decisions.pointer(reader.documents[relative], pointer)
            except catalog_decisions.InvalidDecisionIndex as error:
                fail("F12", f"unmodeled collection {relative}#{pointer} does not resolve ({error})")
            require(isinstance(target, list), "F12", f"unmodeled collection {relative}#{pointer} is not a list")
            unmodeled.append({"path": relative, "pointer": pointer})
    unmodeled.sort(key=lambda item: (item["path"], item["pointer"]))

    # One sweep manifest per consumer, flagged when they differ; the index follows the matrix.
    sweep_paths = {
        "catalogs/landscape/manifest.json sources.trading_taxonomy":
            (landscape_manifest.get("sources") or {}).get("trading_taxonomy"),
        "scripts/new_host_grand_list.py MANIFEST": new_host_grand_list.MANIFEST,
        "the component evidence matrix summary.convergence.newest_manifest":
            (((matrix.get("summary") or {}).get("convergence") or {}).get("newest_manifest") or {}).get("path"),
    }
    distinct = sorted({value for value in sweep_paths.values() if isinstance(value, str)})
    if len(distinct) > 1:
        build.item("source/sweep-manifest-divergence",
                   "sweep manifests in use differ: " + "; ".join(f"{label}: {value}" for label, value in
                                                                  sweep_paths.items())
                   + "; the index follows the matrix", distinct)

    items = sorted(build.items, key=lambda item: (item["type"], item["refs"], item["message"]))
    ranked = [placement for layer in layers for placement in layer["placements"]]
    winners = [placement for placement in ranked if placement["role"] == "winner"]
    shared_now = sum(1 for placement in ranked if placement["shared"])
    shared_with_pin = 0
    for layer in layers:
        keys = [tuple(placement["sort_key"]) + ((PIN_TIEBREAK[placement["freshness"]["pin_current"]],)
                                                if placement["role"] == "winner" else (0,))
                for placement in layer["placements"]]
        shared_with_pin += sum(1 for key in keys if keys.count(key) > 1)
    tie_sizes = [count for layer in layers
                 for count in Counter(tuple(placement["sort_key"]) for placement in layer["placements"]).values()]
    counts = {
        "placements": {
            "layers": len(layers),
            "pending_layers": sum(1 for layer in layers if layer["banner"]["verdict_status"] == "pending_lanes"),
            "source_records": sum(layer["counts"]["records"] for layer in layers),
            "unresolved_records": sum(layer["counts"]["unresolved_records"] for layer in layers),
            "placed": sum(layer["counts"]["placements"] for layer in layers),
            "ranked": len(ranked),
            "outside_ranking": sum(len(layer["outside_ranking"]) for layer in layers),
            "caution": sum(len(layer["caution"]) for layer in layers),
            "ranked_by_role": {role: sum(1 for placement in ranked if placement["role"] == role) for role in ROLES},
            "shared": shared_now,
            "distinct_positions": sum(len({placement["position"] for placement in layer["placements"]})
                                      for layer in layers),
            "largest_tie": max(tie_sizes, default=0),
            "ordered_by_measurement": sum(1 for placement in ranked if placement["sort_key"][3] > 0),
        },
        "conservation": {
            "entities": len(entities), "decision_index_records": len(universe),
            "receipts": {"listed": len(receipts),
                         "attached": len({receipt for attached in entity_receipts.values() for receipt in attached}),
                         "unattached": len(unattached)},
            "experiments": {"listed": len(experiments), "convergence_records": len(convergence_records)},
            "coverage": {"listed": len(listing), "classified": len(catalog_files)},
        },
        "status_items": {item_type: sum(1 for item in items if item["type"] == item_type)
                         for item_type in sorted(STATUS_TYPES)},
        "coverage": {**{reached: sum(1 for item in catalog_files if item["reached_as"] == reached)
                        for reached in REACHED_AS}, "unmodeled_collections": len(unmodeled)},
        "freshness": {"winner_pin_current": {value: sum(1 for placement in winners
                                                        if placement["freshness"]["pin_current"] == value)
                                             for value in PIN_CURRENT_VALUES}},
        "verification": {role: {state: sum(1 for placement in ranked if placement["role"] == role
                                           and placement["verification"]["state"] == state)
                                for state in sorted(VERIFICATION_LEVELS[role])} for role in ("winner", "alternative")},
        "overturn_metrics": {"class_vs_verification_flipped_pairs": flipped,
                             "class_vs_verification_flipped_winner_pairs": winner_pairs,
                             "pin_current_tiebreak_would_unshare": shared_now - shared_with_pin},
        "measurements": len(measurements),
    }
    document = {
        "schema_version": 1, "id": "catalog-index", "generated_by": "scripts/catalog_index.py", "scope": SCOPE,
        "universal_superiority": universal, "rule": copy.deepcopy(RULE),
        "inputs": [{"path": path, "scope": scope} for path, scope in sorted(INPUTS)],
        "counts": counts, "layers": layers, "entities": entities,
        "evidence": {"receipts_unattached": sorted(unattached, key=lambda item: item["id"]),
                     "experiments": experiments},
        "unresolved": sorted(build.unresolved, key=lambda item: (item["path"], _pointer_key(item["pointer"]))),
        "status_items": items,
        "coverage": {"catalog_files": catalog_files, "unmodeled_collections": unmodeled},
        "measurements": measurements,
    }
    check_document(document)
    check_build(document, reader, listing, records_by_layer, universe, aliases, receipts, convergence_records)
    return document


def check_build(document: dict, reader: Reader, listing: list[str], records_by_layer: dict, universe: dict,
                aliases: dict, receipts: list, convergence_records: list) -> None:
    """The fatal checks that need the inputs: conservation against the sources (F9) and integrity of the read set
    and of every pointer the document carries (F12)."""
    for layer in document["layers"]:
        records = records_by_layer[layer["ref"]]
        resolved = [record for record in records if record["entity"] is not None]
        counts = layer["counts"]
        require(counts["records"] == len(records) and counts["unresolved_records"] == len(records) - len(resolved),
                "F9", f"{layer['ref']}: record counts differ from the ledger and matrix records")
        require(len(layer["placements"]) + len(layer["outside_ranking"]) + len(layer["caution"])
                == counts["placements"] == len({record["entity"] for record in resolved}), "F9",
                f"{layer['ref']}: ranked + outside + caution differs from the placements")
    conservation = document["counts"]["conservation"]
    require(len(document["entities"]) == conservation["entities"] == len(universe), "F9",
            "the entities differ from the decision-index records")
    attached = {receipt for entity in document["entities"] for receipt in entity["receipts"]["ids"]}
    unattached = [item["id"] for item in document["evidence"]["receipts_unattached"]]
    require(len(attached) + len(unattached) == len(receipts) == conservation["receipts"]["listed"]
            and not (attached & set(unattached)), "F9", "attached + unattached receipts differ from receipts[]")
    require(len(document["evidence"]["experiments"]) == len(convergence_records), "F9",
            "the listed experiments differ from convergence_records[]")
    require([item["path"] for item in document["coverage"]["catalog_files"]] == listing, "F9",
            "coverage does not cover every listed file exactly once")

    require(reader.inputs == DECLARED_INPUT_PATHS, "F12",
            f"the read set differs from inputs[]: undeclared {sorted(reader.inputs - DECLARED_INPUT_PATHS)}, "
            f"unread {sorted(DECLARED_INPUT_PATHS - reader.inputs)}")
    require(reader.scanned == set(listing), "F12", "the listing scan differs from the listing")
    require(set(reader.documents) <= DECLARED_INPUT_PATHS | set(listing), "F12",
            f"parsed outside the read set: {sorted(set(reader.documents) - DECLARED_INPUT_PATHS - set(listing))}")
    for layer in document["layers"]:
        for entry in layer["placements"] + layer["outside_ranking"] + layer["caution"]:
            targets = [(record["path"], record["pointer"], record.get("disposition"), True)
                       for record in entry["role_records"]]
            if entry.get("matrix_record"):
                targets.append((entry["matrix_record"]["path"], entry["matrix_record"]["pointer"], None, False))
            for path, pointer, disposition, compare_disposition in targets:
                try:
                    target = catalog_decisions.pointer(reader.documents[path], pointer)
                    name = catalog_decisions.canonical(catalog_decisions.identity(target.get("repository")), aliases)
                except (catalog_decisions.InvalidDecisionIndex, KeyError, AttributeError) as error:
                    fail("F12", f"{layer['ref']} {entry['entity']}: {path}#{pointer} does not resolve ({error})")
                require(ENTITY_PREFIX + name == entry["entity"], "F12",
                        f"{layer['ref']}: {path}#{pointer} names {name}, not {entry['entity']}")
                require(not compare_disposition or target.get("disposition") == disposition, "F12",
                        f"{layer['ref']}: {path}#{pointer} disposition differs from its role record")
    for item in document["coverage"]["unmodeled_collections"]:
        try:
            catalog_decisions.pointer(reader.documents[item["path"]], item["pointer"])
        except (catalog_decisions.InvalidDecisionIndex, KeyError) as error:
            fail("F12", f"unmodeled collection {item['path']}#{item['pointer']} does not resolve ({error})")


# --------------------------------------------------------------------------------------------------- checking


def _keys(node, pointer=""):
    """Every (pointer, key) of the document's objects."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield pointer, key
            yield from _keys(value, f"{pointer}/{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _keys(value, f"{pointer}/{index}")


def check_document(document: dict) -> None:
    """The fatal checks a built document must pass on its own: F3-F8 and F13-F16, plus its internal counts (F9)."""
    require(isinstance(document, dict), "F7", "the index must be an object")
    require(document.get("universal_superiority") == "not_established", "F7",
            "universal_superiority must be not_established")
    require("never selects a winner" in str(document.get("scope")), "F7", "the scope must say it never selects a winner")
    rule = document.get("rule")
    require(isinstance(rule, dict) and rule.get("blended_score") is False, "F6", "rule.blended_score must be false")
    for pointer, key in _keys(document):
        require(key != "winners", "F14", f"{pointer}/winners: the index never carries a winners key "
                "(host_receipts.landscape_winners reads layers[].winners[] from catalogs/landscape/*.json)")
        require(not (set(key.lower().split("_")) & BANNED_KEY_TOKENS) or f"{pointer}/{key}" == BLENDED_SCORE_POINTER,
                "F6", f"{pointer}/{key}: no score, weight, total or composite key")
    items = document.get("status_items")
    require(isinstance(items, list), "F13", "status_items must be a list")
    for item in items:
        require(isinstance(item, dict) and item.get("type") in STATUS_TYPES
                and item.get("level") == STATUS_TYPES[item["type"]] and item.get("level") in STATUS_LEVELS
                and isinstance(item.get("message"), str) and isinstance(item.get("refs"), list), "F13",
                f"unknown status item {item!r:.200}")
    counts = document.get("counts") or {}
    require(counts.get("status_items") == {item_type: sum(1 for item in items if item["type"] == item_type)
                                           for item_type in sorted(STATUS_TYPES)}, "F9",
            "counts.status_items differ from status_items")
    coverage = document.get("coverage") or {}
    for item in coverage.get("catalog_files") or []:
        require(item.get("reached_as") in REACHED_AS, "F13", f"unknown reached_as {item.get('reached_as')!r}")
        require(item.get("path") != OUTPUT_JSON, "F15", "coverage lists the index's own path")
    groups = {}
    for measurement in document.get("measurements") or []:
        require(isinstance(measurement, dict) and all(field in measurement for field in COMPARABILITY_FIELDS), "F8",
                "a measurement lacks a comparability field")
        if measurement.get("verified") is True:
            groups.setdefault((measurement.get("layer"), measurement.get("entity")), set()).add(
                comparability_key(measurement))
    ranked = outside = caution = 0
    for layer in document.get("layers") or []:
        ref = layer.get("ref")
        banner = layer.get("banner") or {}
        pending = banner.get("verdict_status") == "pending_lanes"
        require(banner.get("layer_state") in component_matrix.CONVERGENCE_LAYER_STATES
                and banner.get("verdict_status") in landscape.VERDICT_STATUSES
                and banner.get("independent_review") in component_matrix.INDEPENDENT_REVIEW_STATES
                and banner.get("decision") in landscape.DECISIONS, "F13", f"{ref}: unknown banner value")
        placements = layer.get("placements") or []
        entries = placements + (layer.get("outside_ranking") or []) + (layer.get("caution") or [])
        entities = [entry.get("entity") for entry in entries]
        require(len(entities) == len(set(entities)), "F3", f"{ref}: a (layer, entity) pair appears twice")
        for entry in entries:
            require(entry.get("role") in ROLE_RANK, "F13", f"{ref}: unknown role {entry.get('role')!r}")
            require(not pending or entry["role"] == "candidate", "F4",
                    f"{ref}: a pending_lanes layer has a {entry['role']} role")
            for record in entry.get("role_records") or []:
                require(record.get("role") in ROLE_RANK and (record.get("disposition") is None
                                                              or record.get("disposition") in landscape.DISPOSITIONS),
                        "F13", f"{ref}: unknown role record {record!r:.200}")
        for entry in (layer.get("outside_ranking") or []) + (layer.get("caution") or []):
            require(entry.get("role") != "winner", "F4", f"{ref}: a winner is outside the ranking")
        for entry in layer.get("outside_ranking") or []:
            require(entry.get("reason") == "out_of_scope", "F13", f"{ref}: unknown outside reason")
        for entry in layer.get("caution") or []:
            require(entry.get("reason") == "observed_failure", "F13", f"{ref}: unknown caution reason")
        keys = [sort_key(placement) for placement in placements]
        require(keys == [placement.get("sort_key") for placement in placements], "F5",
                f"{ref}: a stored sort_key differs from the rule")
        expected = positions(keys)
        require([(placement.get("position"), placement.get("shared")) for placement in placements]
                == [tuple(item) for item in expected], "F5", f"{ref}: a stored position differs from the rule")
        require([(placement["position"], placement["entity"]) for placement in placements]
                == sorted((placement["position"], placement["entity"]) for placement in placements), "F5",
                f"{ref}: placements are not in position, then entity order")
        for placement in placements:
            require(placement.get("freshness", {}).get("pin_current") in (None, *PIN_CURRENT_VALUES), "F13",
                    f"{ref}: unknown pin_current")
            verification = placement.get("verification") or {}
            if placement["role"] == "winner":
                require(verification.get("declared") in platform_status.STATUS_RANK
                        and verification.get("macos") in platform_status.STATUS_RANK, "F13",
                        f"{ref}: unknown declared or macOS status")
                if verification.get("state") == "host_verified":
                    require((verification.get("host_receipts") or {}).get("independently_reviewed_pass", 0) >= 1,
                            "F16", f"{ref}: host_verified winner {placement['entity']} has no independently "
                            "reviewed passing receipt")
        classes: dict[tuple, list[dict]] = {}
        for placement in placements:
            classes.setdefault(tuple(placement["sort_key"][:3]), []).append(placement)
        for members in classes.values():
            if any(member["sort_key"][3] for member in members):
                group = members[0]["measured"].get("group")
                require(group is not None and all(member["measured"].get("group") == group for member in members)
                        and all(group in groups.get((ref, member["entity"]), ()) for member in members), "F8",
                        f"{ref}: a measured rank outside a whole-class verified comparability group")
        ranked += len(placements)
        outside += len(layer.get("outside_ranking") or [])
        caution += len(layer.get("caution") or [])
    placement_counts = counts.get("placements") or {}
    require((placement_counts.get("ranked"), placement_counts.get("outside_ranking"), placement_counts.get("caution"))
            == (ranked, outside, caution), "F9", "counts.placements differ from the layers")


def check_text(text: str) -> int:
    """F10 and F11 on the serialized index; returns its size in bytes."""
    size = len(text.encode("utf-8"))
    require(size < SIZE_LIMIT_BYTES, "F10",
            f"the index is {size} bytes; the secret scan skips files of {SIZE_LIMIT_BYTES} bytes or more "
            "(gitleaks --max-target-megabytes 2), so it is refused")
    for description, pattern in PRIVATE_CONTENT:
        require(not pattern.search(text), "F11",
                f"generated output contains possible {description}; aborting before writing")
    return size


def serialize(document: dict) -> str:
    return component_matrix.serialize(document)


# --------------------------------------------------------------------------------------------------- main


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="rebuild in memory and exit 1 if the committed index differs (default)")
    mode.add_argument("--write", action="store_true",
                      help="write the index and re-register its hash in manifests/evidence.json")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    try:
        document = build_document(root)
        text = serialize(document)
        size = check_text(text)
    except InvalidIndex as error:
        print(f"catalog_index: {error}", file=sys.stderr)
        return 1
    path = root / OUTPUT_JSON
    summary = {"bytes": size, "layers": len(document["layers"]),
               "ranked": document["counts"]["placements"]["ranked"]}
    if args.write:
        if size >= SIZE_WARN_BYTES:
            print(f"catalog_index: warning: the index is {size} bytes, at or above {SIZE_WARN_BYTES} of the "
                  f"{SIZE_LIMIT_BYTES}-byte secret-scan cap", file=sys.stderr)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        host_receipts.register_file(root, OUTPUT_JSON)
        print(json.dumps({"status": "written", **summary}, sort_keys=True))
        return 0
    if not path.is_file() or path.read_text(encoding="utf-8") != text:
        print(STALE_MESSAGE, file=sys.stderr)
        return 1
    print(json.dumps({"status": "checked", **summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
