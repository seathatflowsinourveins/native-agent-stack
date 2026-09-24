#!/usr/bin/env python3
"""Validate and join the dated landscape choices; never infer benchmark wins."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit

try:
    from .catalog_decisions import canonical, identity, load, safe_file
    from . import platform_status as platform_evidence
except ImportError:
    from catalog_decisions import canonical, identity, load, safe_file
    import platform_status as platform_evidence

MANIFEST = "catalogs/landscape/manifest.json"
DISPOSITIONS = {
    "selected", "observed_failure", "measured_tradeoff", "overlap",
    "out_of_scope", "unqualified", "conditional",
}
EVIDENCE_KINDS = {
    "source_review", "native_execution", "measured_comparison", "requirement_fit", "mixed",
}
DECISIONS = {"retain", "adjust", "keep_but_compare"}

# Layer-verdict schema v2 (catalogs/landscape/{foundation,us-equities}.json).
VERDICT_STATUSES = {"pending_lanes", "recorded", "no_selection"}
WINNER_EVIDENCE_CLASSES = {
    "native_proven", "local_integration", "synthetic", "source_review", "measured_comparison",
}
ALTERNATIVE_SOURCES = {"star", "awesome", "discovery_index", "lane:claude", "lane:codex"}
LANE_AGREEMENTS = {"same_winner", "disagree", "codex_absent", "pending"}
PLATFORM_KEYS = {"linux-wsl2-x86_64", "macos-arm64"}
PLATFORM_STATUSES = {"accepted", "conditional", "not_established", "untested"}
PLATFORM_ALLOWED = {
    "linux-wsl2-x86_64": {"accepted", "conditional", "not_established"},
    "macos-arm64": {"accepted", "conditional", "not_established", "untested"},
}
# Platforms whose declared status may not outrank what scripts/platform_status.py derives
# from the host receipts and registered evidence, on every row. tools/sota-convergence/
# record_verdicts.py now derives every platform of a new wave through that same function, and
# validate_verdict_row enforces every platform on a non-grandfathered row; Linux joins this set
# for the grandfathered rows when they are re-recorded (13 Linux "accepted" rows at 38847e5 cite
# no registered evidence/ file and would derive "conditional"); that re-record widens it.
ENFORCED_PLATFORMS = {"macos-arm64"}
OVERTURN_MARKERS = ("fixtures/", "blueprints/", "tests/", "python3 ", "node ")

# --- Layer-verdict integrity rules (2026-09-23 peer audit) ---------------------------------------
# Shared by tools/sota-convergence/record_verdicts.py (record time) and this validator (CI re-check).
SEALED_BASE_PREFIX = "evidence/artifacts/layer-verdicts-"
DEFAULT_SEALED_BASE = SEALED_BASE_PREFIX + "20260922"
# Grandfathered wave: the 32 rows sealed on 2026-09-22 predate these rules. Their lane returns
# declare no model family or provenance, their adjudications are Opus-only (both presentation
# orders, no judge identity), they have no run manifest (their packets/ and SHA256SUMS are
# retained under the sealed base instead), and their Linux platform_status came from the lane's
# evidence class alone (13 "accepted" winners cite no registered evidence/ file, so
# scripts/platform_status.py would derive "conditional"). The exemption covers only the committed wave,
# which is frozen independently of whether a later wave exists yet:
# - record_verdicts.py has no default --run-id and its --write refuses a grandfathered id once
#   --root holds that wave (its sealed directory or a registered wave document), so it never
#   re-records a row or adds a run manifest there;
# - build_verdicts.py --write refuses to regenerate or re-register a registered grandfathered
#   wave, and --check compares every row still naming it with the hash-registered
#   layer-verdicts-20260922.json;
# - tests/test_layer_verdicts.py GrandfatheredWavePinTests (run by CI's python3 -m unittest) pins
#   the bytes of that document, its registry entry and every file under the sealed 20260922
#   directory, and asserts it holds no run-manifest.json.
# Every other run id gets every rule.
GRANDFATHERED_RUN_IDS = frozenset({"20260922"})
LANES = ("claude", "codex")
LANE_FAMILIES = {"claude": "anthropic", "codex": "openai"}
FAMILY_MODEL_PATTERNS = {
    "anthropic": re.compile(r"claude-[A-Za-z0-9._\[\]-]+|opus|sonnet|fable|haiku"),
    "openai": re.compile(r"gpt-[A-Za-z0-9._-]+|codex"),
}
SHA256_TEXT = re.compile(r"[a-f0-9]{64}")
GIT_COMMIT_TEXT = re.compile(r"[a-f0-9]{40}")
LANE_PROVENANCE_FIELDS = {
    "claude": ("workflow_path", "workflow_sha256", "agentlab_commit", "agent_sha256", "prompt_sha256",
               "repo_tree_sha256"),
    "codex": ("codex_lane_py_sha256", "prompt_sha256", "repo_tree_sha256"),
}
RUN_MANIFEST_NAME = "run-manifest.json"
# "failed": the lane ran for the layer but returned nothing sealable (a Claude layer whose final was
# refuted or unknown, a Codex layer that failed after its retry); the reason comes from the lane
# runner's <work-dir>/<lane>/failures.json (2026-09-23 review of #122, finding 7).
LANE_OUTCOMES = {"sealed", "rejected", "failed", "missing"}
# A single-lane decision record must be dated in its file name (YYYY-MM-DD or YYYYMMDD), sit under
# docs/decisions/ and carry, for each layer it authorizes, the exact line
# "single-lane-authorization: <catalog>/<layer_id>"; its sha256 is stored on the row
# (lanes.single_lane_decision_sha256). A wave document or run manifest that merely mentions a layer
# id authorizes nothing (2026-09-23 review of #122, finding 2).
DATED_NAME = re.compile(r"(?<![0-9])20[0-9]{2}-?(?:0[1-9]|1[0-2])-?(?:0[1-9]|[12][0-9]|3[01])(?![0-9])")
SINGLE_LANE_DECISION_DIR = "docs/decisions/"
SINGLE_LANE_AUTHORIZATION = "single-lane-authorization: {catalog}/{layer_id}"
# A new wave retains the packets both lanes judged under <sealed_base>/packets/ with their
# SHA256SUMS, listed in the run manifest's retained_packets (2026-09-23 review of #122, finding 6).
RETAINED_PACKETS_DIR = "packets"
# Keys a new-wave (--withhold-labels) packet never carries on a candidate or unclaimed-component
# copy: popularity and recency signals, the latest upstream release and what is derived from it,
# the newcomer flag and the candidate-only note (tools/sota-convergence/lane_packets.py
# withhold_popularity, which imports these).
POPULARITY_RECENCY_FIELDS = ("stars", "forks", "watchers", "pushed_at", "released_at")
POPULARITY_TOKENS = ("star", "fork", "watcher", "subscriber", "download", "popular", "trending")
UPSTREAM_RELEASE_FIELDS = ("latest", "prerelease", "latest_flag")
COPY_WITHHELD_FIELDS = ("pin_behind_upstream", "newcomer", "note")
PACKET_UPSTREAM_COPIES = ("candidates", "sota_components_not_in_candidates")
# Review of the #122 fix round (2026-09-23): the withheld-key check walks every depth of the packet,
# not only the two positions withhold_popularity stripped. At any depth a key is withheld when it is
# a popularity/recency key, one of COPY_WITHHELD_FIELDS, or names the latest version, any release,
# a newcomer or a pin-behind comparison (for example upstream.latest_release, upstream.release,
# upstream.latest_flag, whose tag-listing fallback can be date-shaped, or a top-level newcomers
# list). archived/license are kept only where the requirement names them (REQUIREMENT_GATED_FIELDS).
# The packet's own checked_at is its build date, not a candidate signal. On a candidate or component
# copy the disposition labels are withheld at any depth too: selection, disposition, rationale and
# current_choice never appear and review_status is null (lane_packets.withhold_labels); at the top
# level current_choice, decision and rationale never appear (lane_packets.WITHHELD). A packet whose
# withheld[] lacks a policy label was not built with --withhold-labels.
WITHHELD_KEY_TOKENS = ("latest", "release", "newcomer", "pin_behind")
REQUIREMENT_GATED_FIELDS = {"archived": ("archiv", "maintained", "maintenance"), "license": ("licen",)}
PACKET_OWN_KEYS = ("checked_at", "sealed_candidates_sha256")
COPY_DISPOSITION_KEYS = ("selection", "disposition", "rationale", "current_choice")
COPY_NULL_ONLY_KEYS = ("review_status",)
# gap_receipts (lane_packets.py --gap-receipts) is the set of checks run against each layer's previous
# winner, and many of those receipts repeat the gap text or name the winner, so a blind wave's retained
# packets never carry it (round-2 review). The grandfathered 2026-09-22 packets are not re-checked.
TOP_LEVEL_WITHHELD_KEYS = ("current_choice", "decision", "rationale", "gap_receipts", "gap_receipts_note")
# The Claude lane's refutation summary (layer-verdict-lane.js): both lens votes are required on the
# object it seals (2026-09-23 review of #122, finding 5).
REFUTATION_LENSES = ("evidence", "challenger")
REFUTATION_ROUNDS = ("proposal", "revision")
REFUTATION_STATUSES = ("unrefuted", "refuted", "unknown")
# Append-only list of the lane code a new-wave return may name in its provenance: the Claude
# lane's (workflow_path, workflow_sha256) and the Codex lane's (codex_lane_py_sha256,
# prompt_sha256). tests/test_verdict_lane_vendoring.py keeps it covering the current
# codex_lane.py, lane-prompt.md and vendored workflow bytes.
LANE_PROVENANCE_REGISTRY = "tools/sota-convergence/lane-provenance.json"
LANE_PROVENANCE_KEYS = {"claude": ("workflow_path", "workflow_sha256", "agent_sha256", "prompt_sha256"),
                        "codex": ("codex_lane_py_sha256", "prompt_sha256")}


def run_id_of(sealed_base):
    return sealed_base[len(SEALED_BASE_PREFIX):] if isinstance(sealed_base, str) else None


def is_grandfathered_run(run_id):
    return run_id in GRANDFATHERED_RUN_IDS


def model_family_issue(model, expected_family, label):
    """None when ``model`` declares ``expected_family`` and a name matching that family's pattern."""
    if not isinstance(model, dict):
        return label + " must be an object"
    family, name = model.get("family"), model.get("name")
    if family != expected_family:
        return f"{label}.family must be {expected_family!r} (got {family!r})"
    if not (isinstance(name, str) and FAMILY_MODEL_PATTERNS[expected_family].fullmatch(name)):
        return (f"{label}.name {name!r} does not match the {expected_family} pattern "
                f"{FAMILY_MODEL_PATTERNS[expected_family].pattern}")
    return None


def lane_model_issue(lane, model):
    return model_family_issue(model, LANE_FAMILIES[lane], "model")


def is_popularity_or_recency_key(key):
    lowered = key.lower()
    return (lowered in POPULARITY_RECENCY_FIELDS or lowered.endswith("_at")
            or any(token in lowered for token in POPULARITY_TOKENS))


def requirement_names(field, requirement):
    """True when the packet requirement names a REQUIREMENT_GATED_FIELDS field (licensing or
    maintenance status), which makes it evidence rather than a popularity proxy."""
    text = requirement.lower() if isinstance(requirement, str) else ""
    return any(token in text for token in REQUIREMENT_GATED_FIELDS[field])


def is_withheld_packet_key(key, kept_gated=()):
    """Whether a --withhold-labels packet may carry ``key`` at any depth (the shared policy of
    lane_packets.withhold_popularity and withheld_packet_keys); ``kept_gated`` are the
    REQUIREMENT_GATED_FIELDS the packet's requirement names."""
    lowered = key.lower()
    if lowered in REQUIREMENT_GATED_FIELDS:
        return lowered not in kept_gated
    return (is_popularity_or_recency_key(key) or lowered in COPY_WITHHELD_FIELDS or lowered == "notes"
            or any(token in lowered for token in WITHHELD_KEY_TOKENS))


def withhold_policy_labels(requirement=None):
    """The withheld[] labels lane_packets.withhold_popularity always lists for each copy
    collection; a packet lacking one was not built with --withhold-labels."""
    gated = [field for field in REQUIREMENT_GATED_FIELDS if not requirement_names(field, requirement)]
    return sorted(f"{collection}[].{label}" for collection in PACKET_UPSTREAM_COPIES
                  for label in [f"upstream.{field}" for field in
                                list(POPULARITY_RECENCY_FIELDS) + list(UPSTREAM_RELEASE_FIELDS) + gated]
                  + list(COPY_WITHHELD_FIELDS))


# Candidate fields only a sota-manifest-matched candidate carries (its manifest id, pin, upstream record, adoption
# recipe and decision records): their presence alone marks manifest membership, which singled out the catalog's
# current choice among a layer's adopted candidates in the 2026-09-23 packets (review of #145, measured
# 2026-09-24: 8 of 32 layers against the v1 selected/default candidates, 6 against the recorded 20260922 winners
# by export_isolation_check.packet_field_hits, 0 once sealed). A --withhold-labels packet carries none of them: lane_packets.py --keys-out seals them by candidate
# key into a packet-keys document outside the lanes' reach, record_verdicts.py and adjudicate.py restore them to
# resolve winner component ids, and a new wave retains the document as <sealed_base>/packet-keys.json, bound by
# the run manifest's packet_keys_sha256. A registered receipt's matched_by (component_id or alias) names the
# same membership and is dropped from a blind packet.
SEALED_CANDIDATE_FIELDS = ("component_id", "pin", "upstream", "recipe_ref", "decisions")
PACKET_KEYS_NAME = "packet-keys.json"
SEALED_COMMITMENT_KEY = "sealed_candidates_sha256"
PACKET_KEYS_SCHEMA_VERSION = 1


# Candidate labels a blind packet drops outright (round 5, N5): a selected candidate must carry a strong evidence_kind,
# so the kind marks the winners.
WITHHELD_CANDIDATE_LABELS = ("evidence_kind",)


def withheld_candidate_label_labels():
    return [f"candidates[].{field}" for field in WITHHELD_CANDIDATE_LABELS]


def sealed_candidate_labels():
    return [f"candidates[].{field}" for field in SEALED_CANDIDATE_FIELDS]


def packet_seals_candidates(packet):
    """Whether a packet's withheld list says its candidates' SEALED_CANDIDATE_FIELDS are sealed out of it."""
    listed = packet.get("withheld") if isinstance(packet, dict) else None
    return isinstance(listed, list) and all(label in listed for label in sealed_candidate_labels())


def packet_keys_issue(keys_doc, name, packet_sha256, packet):
    """None when ``keys_doc`` (a packet-keys document) seals exactly the candidates of ``packet`` (file ``name``
    with ``packet_sha256``), each with SEALED_CANDIDATE_FIELDS only."""
    if not (isinstance(keys_doc, dict) and keys_doc.get("schema_version") == PACKET_KEYS_SCHEMA_VERSION
            and isinstance(keys_doc.get("packets"), dict)):
        return "the packet-keys document is malformed"
    entry = keys_doc["packets"].get(name)
    if not isinstance(entry, dict):
        return f"the packet-keys document has no entry for {name}"
    if entry.get("packet_sha256") != packet_sha256:
        return (f"the packet-keys entry for {name} names packet_sha256 {entry.get('packet_sha256')!r}, "
                f"not {packet_sha256}")
    sealed = entry.get("candidates")
    keys = [candidate.get("key") for candidate in (packet.get("candidates") or []) if isinstance(candidate, dict)]
    if not isinstance(sealed, dict) or set(sealed) != set(keys):
        return f"the packet-keys entry for {name} must seal exactly the packet's candidate keys"
    for key, fields in sealed.items():
        if not isinstance(fields, dict) or set(fields) - set(SEALED_CANDIDATE_FIELDS):
            return f"the packet-keys entry for {name} seals fields other than {list(SEALED_CANDIDATE_FIELDS)} for {key}"
    ids = [fields.get("component_id") for fields in sealed.values() if fields.get("component_id")]
    if len(ids) != len(set(ids)):
        # Two candidates restored to one component would record a false same_winner (round 6, INT-R6-2).
        return f"the packet-keys entry for {name} seals one component_id for two candidates"
    if packet.get(SEALED_COMMITMENT_KEY) != sealed_candidates_sha256(sealed):
        return (f"the packet-keys entry for {name} is not the sealed values the packet commits to "
                f"({SEALED_COMMITMENT_KEY}); rebuild the document with lane_packets.py --keys-out for these packets")
    return None


def sealed_candidates_sha256(sealed) -> str:
    """The commitment a --withhold-labels packet carries (sealed_candidates_sha256) to its candidates' sealed values:
    the packet-keys entry that restores them must hash to it, so a stale, edited or other run's document cannot
    restore other component ids or pins, and every lane return, bound to the packet's sha256, is bound to the
    values too (Codex review of #145 at a516c477; round 5, INT-R5-1)."""
    return hashlib.sha256(json.dumps(sealed, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def unseal_packet(packet, keys_doc, name):
    """A copy of ``packet`` whose candidates carry their sealed fields again (packet_keys_issue must be None)."""
    sealed = keys_doc["packets"][name]["candidates"]
    return dict(packet, candidates=[dict(candidate, **sealed.get(candidate.get("key"), {}))
                                    if isinstance(candidate, dict) else candidate
                                    for candidate in packet.get("candidates") or []])


def withheld_packet_keys(packet):
    """Labels ("candidates[].upstream.stars", "newcomers", ...) of every withheld key a packet still
    carries at any depth, plus "withheld[] lacks <label>" for each policy label missing from its
    withheld list; empty only for a --withhold-labels packet."""
    if not isinstance(packet, dict):
        return ["<packet is not a JSON object>"]
    requirement = packet.get("requirement")
    kept_gated = {field for field in REQUIREMENT_GATED_FIELDS if requirement_names(field, requirement)}
    found = set()

    def walk(value, label, in_copy):
        if isinstance(value, dict):
            for key, item in value.items():
                path = f"{label}.{key}" if label else key
                lowered = key.lower() if isinstance(key, str) else ""
                if not label and lowered in PACKET_OWN_KEYS:
                    continue
                if (is_withheld_packet_key(key, kept_gated)
                        or (not label and lowered in TOP_LEVEL_WITHHELD_KEYS)
                        or (in_copy and (lowered in COPY_DISPOSITION_KEYS
                                         or (lowered in COPY_NULL_ONLY_KEYS and item is not None)))):
                    found.add(path)
                    continue
                walk(item, path, in_copy or (not label and key in PACKET_UPSTREAM_COPIES))
        elif isinstance(value, list):
            for item in value:
                walk(item, f"{label}[]", in_copy)

    walk(packet, "", False)
    for collection in PACKET_UPSTREAM_COPIES:
        for item in packet.get(collection) or []:
            if not isinstance(item, dict):
                continue
            if collection == "candidates":
                found |= {f"candidates[].{field}" for field in SEALED_CANDIDATE_FIELDS + WITHHELD_CANDIDATE_LABELS
                          if field in item}
            if any(isinstance(receipt, dict) and "matched_by" in receipt for receipt in item.get("registered_receipts") or []):
                found.add(f"{collection}[].registered_receipts[].matched_by")
    listed = packet.get("withheld")
    listed = set(listed) if isinstance(listed, list) and all(isinstance(item, str) for item in listed) else set()
    found |= {f"withheld[] lacks {label}" for label in withhold_policy_labels(requirement) + sealed_candidate_labels()
              + withheld_candidate_label_labels() if label not in listed}
    return sorted(found)


def packet_component_id(candidate):
    """A packet candidate's winner component id: its component_id, else candidate:<owner-repo>
    (the id record_verdicts.py writes on the row)."""
    component_id = candidate.get("component_id") if isinstance(candidate, dict) else None
    if component_id:
        return component_id
    try:
        slug = identity(candidate.get("repository"))
    except (ValueError, TypeError, AttributeError):
        slug = None
    return f"candidate:{(slug or 'unknown').replace('/', '-')}"


def lane_winner_components(sealed_return, packet):
    """(issue, {(component_id, repository)}) of a sealed return's winner_keys resolved against the
    retained packet it names."""
    keys = sealed_return.get("winner_keys") if isinstance(sealed_return, dict) else None
    if not (isinstance(keys, list) and 1 <= len(keys) <= 3 and all(isinstance(key, str) for key in keys)
            and len(set(keys)) == len(keys)):
        return "winner_keys must be 1-3 unique packet candidate keys", None
    candidates = {candidate.get("key"): candidate for candidate in packet.get("candidates") or []
                  if isinstance(candidate, dict)}
    unknown = [key for key in keys if key not in candidates]
    if unknown:
        return f"winner_keys {unknown} are not candidates of the retained packet", None
    not_adopted = [key for key in keys if candidates[key].get("adopted") is not True]
    if not_adopted:
        # The lane contract forbids a non-adopted winner (record_verdicts.validate_lane_return).
        return f"winner_keys {not_adopted} are not adopted candidates of the retained packet", None
    return None, {(packet_component_id(candidates[key]), candidates[key].get("repository")) for key in keys}


def claude_refutation_issue(refutation):
    """None when the Claude lane's refutation summary shows its final object sealed unrefuted: status
    unrefuted, and both lens votes of the round that produced the final returned refuted == false."""
    if not isinstance(refutation, dict):
        return ("a claude lane return needs the refutation summary layer-verdict-lane.js returns "
                "(refutation {status, final_source, proposal_status, revision_status, votes})")
    status, source = refutation.get("status"), refutation.get("final_source")
    if status != "unrefuted":
        return f"refutation.status is {status!r}: a refuted or unknown final is never sealed"
    if source not in REFUTATION_ROUNDS or refutation.get(f"{source}_status") != "unrefuted":
        return "refutation.final_source must name a round (proposal|revision) whose status is unrefuted"
    votes = refutation.get("votes")
    if not isinstance(votes, list) or not all(
            isinstance(vote, dict) and vote.get("lens") in REFUTATION_LENSES and vote.get("round") in REFUTATION_ROUNDS
            and vote.get("refuted") in (True, False, None) and isinstance(vote.get("reason"), str)
            for vote in votes):
        return "refutation.votes must be a list of {lens, round, refuted true|false|null, reason}"
    final_votes = [vote for vote in votes if vote["round"] == source]
    if (sorted(vote["lens"] for vote in final_votes) != sorted(REFUTATION_LENSES)
            or any(vote["refuted"] is not False for vote in final_votes)):
        return (f"both lens votes ({', '.join(REFUTATION_LENSES)}) on the sealed {source} must be present "
                "and unrefuted")
    return None


def lane_provenance_issue(lane, provenance):
    """A new-wave sealed return names what produced it: the Claude lane its workflow file, hash, agent-lab
    commit and the hash of the role definition its stages ran as; the Codex lane the hashes of codex_lane.py
    and the prompt it filled. Both name the digest of the evidence tree they read (repo_tree_sha256)."""
    fields = LANE_PROVENANCE_FIELDS[lane]
    if not isinstance(provenance, dict) or set(provenance) != set(fields):
        return f"provenance must be an object with exactly {', '.join(fields)} for the {lane} lane"
    for field in fields:
        value = provenance[field]
        if field.endswith("sha256"):
            ok = isinstance(value, str) and bool(SHA256_TEXT.fullmatch(value))
        elif field == "agentlab_commit":
            ok = isinstance(value, str) and bool(GIT_COMMIT_TEXT.fullmatch(value))
        else:  # workflow_path: a repository-relative .js path
            ok = (isinstance(value, str) and value.endswith(".js") and not value.startswith("/")
                  and ".." not in value.split("/"))
        if not ok:
            return f"provenance.{field} is malformed for the {lane} lane"
    return None


def load_lane_provenance_registry(root):
    """lane -> list of registered provenance entries (empty when the registry is absent); the "adjudication"
    key holds the registered adjudication code (independent review of #145, M2)."""
    path = Path(root) / LANE_PROVENANCE_REGISTRY
    if not path.is_file():
        return {lane: [] for lane in (*LANES, "adjudication")}
    document = json.loads(path.read_text(encoding="utf-8"))
    return {lane: [entry for entry in document.get(lane) or [] if isinstance(entry, dict)]
            for lane in (*LANES, "adjudication")}


# What produced an adjudication (tools/sota-convergence/adjudicate.py adjudication_provenance, less the evidence tree,
# which varies per run): a new-wave adjudication must name code, prompt, schemas, workflow and role that
# lane-provenance.json registers (independent review of #145, M2).
ADJUDICATION_PROVENANCE_KEYS = ("adjudicate_py_sha256", "codex_lane_py_sha256", "prompt_sha256", "judge_schema_sha256",
                                "refute_schema_sha256", "workflow_sha256", "adjudicator_role_sha256")


def adjudication_provenance_issue(provenance, registry):
    """None when ``provenance`` names registered adjudication code and carries an evidence-tree digest."""
    if not isinstance(provenance, dict) or not all(isinstance(provenance.get(key), str) and SHA256_TEXT.fullmatch(
            provenance[key]) for key in (*ADJUDICATION_PROVENANCE_KEYS, "repo_tree_sha256")):
        return ("adjudication provenance must carry " + ", ".join((*ADJUDICATION_PROVENANCE_KEYS, "repo_tree_sha256"))
                + " as sha256 text")
    for entry in registry.get("adjudication") or []:
        if all(entry.get(key) == provenance.get(key) for key in ADJUDICATION_PROVENANCE_KEYS):
            return None
    return f"adjudication provenance names adjudication code not listed in {LANE_PROVENANCE_REGISTRY}"


def adjudication_binding_issue(raw, sealed_sha256, lane_trees, registry):
    """None when a new-wave adjudication compared exactly the sealed lane returns (``sealed_sha256``: lane ->
    the row's lanes.<lane>.sealed_sha256), read the lanes' one evidence tree (``lane_trees``) and names
    registered adjudication code (independent review of #145, M2)."""
    if not isinstance(raw, dict):
        return "adjudication must be a JSON object"
    if raw.get("lane_returns_sha256") != sealed_sha256:
        return "its lane_returns_sha256 does not name the sealed lane returns"
    trees = set(lane_trees.values())
    provenance = raw.get("provenance") if isinstance(raw.get("provenance"), dict) else {}
    if len(trees) != 1 or provenance.get("repo_tree_sha256") not in trees:
        return (f"it read evidence tree {provenance.get('repo_tree_sha256')!r}, not the lanes' one tree "
                f"({sorted(str(tree) for tree in trees)})")
    return adjudication_provenance_issue(provenance, registry)


def registered_provenance_entry(lane, provenance, registry):
    """The registry entry naming this return's lane code, or None."""
    if not isinstance(provenance, dict):
        return None
    fields = LANE_PROVENANCE_KEYS[lane]
    for entry in registry.get(lane) or []:
        if all(entry.get(field) == provenance.get(field) for field in fields):
            return entry
    return None


def lane_provenance_registry_issue(lane, provenance, registry):
    if registered_provenance_entry(lane, provenance, registry) is None:
        fields = ", ".join(f"{field}={(provenance or {}).get(field)!r}" for field in LANE_PROVENANCE_KEYS[lane])
        return f"provenance ({fields}) names {lane} lane code not listed in {LANE_PROVENANCE_REGISTRY}"
    return None


def judge_adjudication(raw, *, grandfathered, packet_sha256=None):
    """Validate an adjudication record. Returns ``(issue, result)``; ``issue`` is a rejection
    reason or None. ``result['winner_lane']`` is the lane the adjudication establishes, or None
    for a split. A new wave establishes a winner only when judgments from BOTH lane families
    are present, each family covers both presentation orders, all pick the same lane and none
    is refuted; otherwise it is a split with ``split_reason``. Each new-wave judgment's
    ``stripped_packet_sha256`` must be ``packet_sha256``, the layer's sealed lane packet (the
    --withhold-labels packet both lanes judged, listed in packets/SHA256SUMS): the judge is shown
    that packet, not a private reduction of it. The grandfathered 2026-09-22 rule is the older
    one: both orders, all the same lane, none refuted, no judge identity."""
    if not isinstance(raw, dict):
        return "adjudication must be a JSON object", None
    winner_lane = raw.get("winner_lane")
    if "winner_lane" not in raw or winner_lane not in ("claude", "codex", None) or not (
            isinstance(raw.get("why"), str) and raw["why"].strip()):
        return "adjudication needs winner_lane claude|codex|null and a nonempty why", None
    evidence_refs = raw.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not all(isinstance(item, str) for item in evidence_refs):
        return "adjudication evidence_refs must be a list of text", None
    judgments = raw.get("judgments")
    if not isinstance(judgments, list) or not judgments:
        return "adjudication needs its judgments from both presentation orders", None
    for judgment in judgments:
        if (not isinstance(judgment, dict) or judgment.get("claude_position") not in ("A", "B")
                or judgment.get("preferred_position") not in ("A", "B")
                or type(judgment.get("refuting_votes")) is not int or judgment["refuting_votes"] < 0):
            return ("each judgment needs claude_position A|B, preferred_position A|B "
                    "and a nonnegative integer refuting_votes"), None
        lane = "claude" if judgment["preferred_position"] == judgment["claude_position"] else "codex"
        if judgment.get("preferred_lane") != lane:
            return "a judgment's preferred_lane contradicts its presentation positions", None
        if not grandfathered:
            judge = judgment.get("judge")
            family = judge.get("family") if isinstance(judge, dict) else None
            if family not in FAMILY_MODEL_PATTERNS or model_family_issue(
                    {"family": family, "name": judge.get("model")}, family, "judge") is not None:
                return ("each judgment needs judge {model, family} with family anthropic|openai and a model "
                        "matching that family"), None
            if not (isinstance(judgment.get("stripped_packet_sha256"), str)
                    and SHA256_TEXT.fullmatch(judgment["stripped_packet_sha256"])):
                return "each judgment needs the stripped_packet_sha256 of the packet its judge saw", None
            if not (isinstance(packet_sha256, str) and SHA256_TEXT.fullmatch(packet_sha256)):
                return "the layer's sealed packet sha256 is unknown, so no judgment can be bound to it", None
            if judgment["stripped_packet_sha256"] != packet_sha256:
                return ("a judgment's stripped_packet_sha256 is not the layer's sealed packet sha256 "
                        f"({packet_sha256}): its judge saw a packet this wave did not seal"), None
    if {judgment["claude_position"] for judgment in judgments} != {"A", "B"}:
        return "adjudication judgments must cover both presentation orders", None
    lanes = {judgment["preferred_lane"] for judgment in judgments}
    unrefuted = all(judgment["refuting_votes"] == 0 for judgment in judgments)
    unanimous = next(iter(lanes)) if len(lanes) == 1 and unrefuted else None
    agreed, split_reason = unanimous, None
    if agreed is not None and not grandfathered:
        orders = defaultdict(set)
        for judgment in judgments:
            orders[judgment["judge"]["family"]].add(judgment["claude_position"])
        missing = [family for family in sorted(set(LANE_FAMILIES.values())) if orders.get(family) != {"A", "B"}]
        if missing:
            split_reason = ("the adjudication needs unanimous judgments from both lane families in both "
                            "presentation orders; missing: " + ", ".join(missing))
            agreed = None
    # winner_lane is checked after the two-family rule: when that rule alone makes the result a
    # split, null (the documented split value) and the lane the single family chose are both
    # accepted, and either way the result is a split, never a malformed record.
    allowed = {agreed} | ({unanimous} if split_reason else set())
    if winner_lane not in allowed:
        return (f"winner_lane {winner_lane!r} must equal the lane every unrefuted judgment chose "
                f"({agreed!r}; null when the judgments split, any was refuted or a lane family is missing)"), None
    tally = {lane: sum(judgment["preferred_lane"] == lane for judgment in judgments) for lane in LANES}
    return None, {"winner_lane": agreed, "tally": tally, "split_reason": split_reason,
                  "refuted": sum(judgment["refuting_votes"] > 0 for judgment in judgments)}


def single_lane_authorizes(text, catalog, layer_id):
    """True when ``text`` carries the exact line ``single-lane-authorization: <catalog>/<layer_id>``
    (surrounding whitespace ignored). Mentioning the layer id anywhere else authorizes nothing."""
    expected = SINGLE_LANE_AUTHORIZATION.format(catalog=catalog, layer_id=layer_id)
    return isinstance(text, str) and any(line.strip() == expected for line in text.splitlines())


def single_lane_decision_path_issue(root, path, label="single-lane decision"):
    """None when ``path`` is a confined, existing, dated file under docs/decisions/."""
    if not isinstance(path, str) or not path.strip():
        return "a single-lane recorded verdict needs lanes.single_lane_decision naming a dated decision record"
    if not path.startswith(SINGLE_LANE_DECISION_DIR) or ".." in path.split("/"):
        return f"{label} {path!r} must be a decision record under {SINGLE_LANE_DECISION_DIR}"
    if not DATED_NAME.search(path.rsplit("/", 1)[-1]):
        return f"{label} {path!r} must be dated (YYYY-MM-DD or YYYYMMDD in its file name)"
    try:
        record = safe_file(Path(root), path)
    except ValueError:
        return f"{label} {path!r} is not a confined repository path"
    if not record.is_file():
        return f"{label} {path!r} does not exist"
    return None


def single_lane_decision_issue(root, path, catalog, layer_id, sha256=None):
    """A single-lane (codex_absent) recorded row names a dated docs/decisions/ record carrying the
    line ``single-lane-authorization: <catalog>/<layer_id>``, and stores that record's sha256."""
    issue = single_lane_decision_path_issue(root, path, "lanes.single_lane_decision")
    if issue is not None:
        return issue
    data = safe_file(Path(root), path).read_bytes()
    expected = SINGLE_LANE_AUTHORIZATION.format(catalog=catalog, layer_id=layer_id)
    if not single_lane_authorizes(data.decode("utf-8", errors="replace"), catalog, layer_id):
        return f"lanes.single_lane_decision {path!r} must carry the line {expected!r}"
    if sha256 != hashlib.sha256(data).hexdigest():
        return (f"lanes.single_lane_decision_sha256 must be the sha256 of {path} "
                "(the record changed after it authorized this row, or the hash is missing)")
    return None


def run_manifest_row_issue(manifest, run_id, catalog, layer_id, lanes_field):
    """A new-wave row must appear exactly once in its wave's run manifest with both lanes
    accounted for: sealed (matching the row's run id and hash) or rejected/missing (the row's
    lane then carries no sealed hash), and its packet hash listed in packets_sha256sums."""
    if not isinstance(manifest, dict) or manifest.get("run_id") != run_id or not isinstance(
            manifest.get("packets"), list):
        return f"the run manifest for wave {run_id} is malformed"
    entries = [entry for entry in manifest["packets"]
               if isinstance(entry, dict) and entry.get("catalog") == catalog and entry.get("layer_id") == layer_id]
    if len(entries) != 1:
        return f"{catalog}/{layer_id} must appear exactly once in the run manifest of wave {run_id}"
    entry = entries[0]
    packet_sha256 = entry.get("packet_sha256")
    sums = manifest.get("packets_sha256sums")
    if not (isinstance(packet_sha256, str) and SHA256_TEXT.fullmatch(packet_sha256) and isinstance(sums, str)
            and f"{packet_sha256}  {catalog}__{layer_id}.json" in sums.splitlines()):
        return f"{catalog}/{layer_id} packet hash is not listed in the run manifest's packets_sha256sums"
    for lane in LANES:
        outcome = (entry.get("lanes") or {}).get(lane)
        row_lane = lanes_field.get(lane) or {}
        if not isinstance(outcome, dict) or outcome.get("outcome") not in LANE_OUTCOMES:
            return f"the run manifest does not account for the {lane} lane of {catalog}/{layer_id}"
        if outcome["outcome"] == "sealed":
            if (outcome.get("sealed_sha256") != row_lane.get("sealed_sha256")
                    or outcome.get("run_id") != row_lane.get("run_id") or not row_lane.get("sealed_sha256")):
                return f"the run manifest's sealed {lane} lane of {catalog}/{layer_id} differs from the row"
        else:
            if row_lane.get("sealed_sha256"):
                return f"the row seals a {lane} lane the run manifest records as {outcome['outcome']}"
            if outcome["outcome"] in ("rejected", "failed") and not (
                    isinstance(outcome.get("reasons"), list) and outcome["reasons"]
                    and all(isinstance(reason, str) and reason for reason in outcome["reasons"])):
                return (f"the run manifest's {outcome['outcome']} {lane} lane of {catalog}/{layer_id} "
                        "needs its reasons")
    # A sealed adjudication is bound by the manifest as well as by the row (review of the #122 fix
    # round), so rewriting one means rewriting the manifest and every row's run_manifest_sha256.
    adjudication = entry.get("adjudication")
    manifest_sha256 = (adjudication.get("sha256") if isinstance(adjudication, dict)
                       and adjudication.get("outcome") == "sealed" else None)
    if manifest_sha256 != lanes_field.get("adjudication_sha256"):
        return (f"the run manifest's sealed adjudication of {catalog}/{layer_id} ({manifest_sha256!r}) differs from "
                f"the row's lanes.adjudication_sha256 ({lanes_field.get('adjudication_sha256')!r})")
    return None


def sha256_of(root, relative):
    path = safe_file(Path(root), relative)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def parse_retained_sha256sums(text):
    """(issue, {packet name: sha256}) of a retained packets/SHA256SUMS text in sha256sum format
    ("<hash>  <name>", keyed by the bare file name after an optional leading "*", as
    record_verdicts.parse_sha256sums reads it). A malformed or duplicated line is an issue, not skipped."""
    if not isinstance(text, str):
        return "is not text", {}
    listed = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.strip().split(None, 1)
        digest = parts[0].lower() if parts else ""
        if len(parts) != 2 or not SHA256_TEXT.fullmatch(digest):
            return f"has a malformed line {line!r}", {}
        name = PurePosixPath(parts[1].strip().lstrip("*")).name
        if name in listed:
            return f"lists {name} twice", {}
        listed[name] = digest
    return None, listed


def verify_sealed_waves(root, wave_refs):
    """Wave-level checks of every non-grandfathered sealed folder (evidence/artifacts/
    layer-verdicts-<run-id>/) under ``root``: its run manifest lists the retained packets and their
    SHA256SUMS; each retained packet matches its hash and carries no withheld key; every sealed
    return the manifest names matches its hash; and every file in the folder is referenced by a row
    (``wave_refs``: wave -> relative paths validate_verdict_row resolved) or by the run manifest."""
    artifacts = Path(root) / "evidence" / "artifacts"
    waves = set(wave_refs)
    if artifacts.is_dir():
        waves |= {path.name[len("layer-verdicts-"):] for path in artifacts.glob("layer-verdicts-*") if path.is_dir()}
    for wave in sorted(waves):
        if is_grandfathered_run(wave):
            continue
        # A folder whose id no row can name (the sealed_base pattern) is rejected, not skipped, so
        # no sealed-looking file sits in evidence/artifacts unchecked (review of the #122 fix round).
        require(re.fullmatch(r"[0-9A-Za-z]+", wave),
                f"{SEALED_BASE_PREFIX}{wave} is not a sealed wave folder: a wave id is alphanumeric "
                "(record_verdicts.py --run-id); move or remove it")
        base = SEALED_BASE_PREFIX + wave
        folder = safe_file(Path(root), base)
        if not folder.is_dir():
            continue
        manifest_file = folder / RUN_MANIFEST_NAME
        require(manifest_file.is_file(), f"sealed wave {base} has no {RUN_MANIFEST_NAME}")
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        require(isinstance(manifest, dict) and manifest.get("run_id") == wave,
                f"the run manifest of wave {wave} is malformed")
        referenced = {RUN_MANIFEST_NAME} | set(wave_refs.get(wave, ()))
        retained = manifest.get("retained_packets")
        require(isinstance(retained, list) and all(
            isinstance(item, dict) and isinstance(item.get("name"), str)
            and re.fullmatch(r"[a-z-]+__[0-9A-Za-z._-]+\.json", item["name"])
            and isinstance(item.get("sha256"), str) and SHA256_TEXT.fullmatch(item["sha256"]) for item in retained),
            f"the run manifest of wave {wave} needs retained_packets [{{name, sha256}}]")
        retained_sha = {item["name"]: item["sha256"] for item in retained}
        sums_relative = f"{RETAINED_PACKETS_DIR}/SHA256SUMS"
        sums_file = folder / sums_relative
        require(sums_file.is_file() and sums_file.read_text(encoding="utf-8") == manifest.get("packets_sha256sums"),
                f"wave {wave}: {sums_relative} must be retained and equal the run manifest's packets_sha256sums")
        # The retained SHA256SUMS must list exactly the retained packets with their actual hashes,
        # including packets no lane returned for (review of catalog #124).
        sums_issue, sums_listed = parse_retained_sha256sums(manifest.get("packets_sha256sums"))
        require(sums_issue is None, f"wave {wave}: {sums_relative} {sums_issue}")
        require(sums_listed == retained_sha,
                f"wave {wave}: {sums_relative} must list exactly the retained packets and their sha256 "
                f"(differs for {sorted(name for name in set(sums_listed) | set(retained_sha) if sums_listed.get(name) != retained_sha.get(name))})")
        referenced.add(sums_relative)
        # Every retained packet is a --withhold-labels packet, so its candidates' manifest fields are sealed in
        # the wave's packet-keys document, bound by the run manifest (review of #145).
        keys_file = folder / PACKET_KEYS_NAME
        require(keys_file.is_file() and hashlib.sha256(keys_file.read_bytes()).hexdigest()
                == manifest.get("packet_keys_sha256"),
                f"wave {wave}: {PACKET_KEYS_NAME} must be retained with the run manifest's packet_keys_sha256")
        keys_doc = json.loads(keys_file.read_text(encoding="utf-8"))
        keys_packets = keys_doc.get("packets") if isinstance(keys_doc, dict) else None
        require(isinstance(keys_packets, dict) and set(keys_packets) == set(retained_sha),
                f"wave {wave}: {PACKET_KEYS_NAME} must seal exactly the retained packets")
        referenced.add(PACKET_KEYS_NAME)
        for name, digest in retained_sha.items():
            relative = f"{RETAINED_PACKETS_DIR}/{name}"
            packet_file = folder / relative
            require(packet_file.is_file() and hashlib.sha256(packet_file.read_bytes()).hexdigest() == digest,
                    f"wave {wave}: retained packet {relative} is missing or differs from its run-manifest sha256")
            found = withheld_packet_keys(json.loads(packet_file.read_text(encoding="utf-8")))
            require(not found, f"wave {wave}: retained packet {relative} carries withheld keys {found}; "
                               "a new wave's lanes judge --withhold-labels packets")
            issue = packet_keys_issue(keys_doc, name, digest, json.loads(packet_file.read_text(encoding="utf-8")))
            require(issue is None, f"wave {wave}: {issue}")
            referenced.add(relative)
        for entry in manifest.get("packets") or []:
            if not isinstance(entry, dict):
                continue
            name = f"{entry.get('catalog')}__{entry.get('layer_id')}.json"
            if entry.get("packet_sha256") is not None:
                require(retained_sha.get(name) == entry["packet_sha256"],
                        f"wave {wave}: packet {name} of the run manifest is not retained with its sha256")
            for lane in LANES:
                outcome = (entry.get("lanes") or {}).get(lane)
                if isinstance(outcome, dict) and outcome.get("outcome") == "sealed":
                    relative = f"{lane}/{outcome.get('run_id')}.json"
                    require(sha256_of(root, f"{base}/{relative}") == outcome.get("sealed_sha256"),
                            f"wave {wave}: sealed return {relative} differs from its run-manifest sha256")
                    referenced.add(relative)
            adjudication = entry.get("adjudication")
            if isinstance(adjudication, dict) and adjudication.get("outcome") == "sealed":
                # The manifest lists each sealed adjudication's sha256 as it lists each sealed return's.
                relative = f"adjudication/{entry.get('catalog')}-{entry.get('layer_id')}-{wave}.json"
                require(sha256_of(root, f"{base}/{relative}") == adjudication.get("sha256"),
                        f"wave {wave}: sealed adjudication {relative} differs from its run-manifest sha256")
                referenced.add(relative)
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                relative = path.relative_to(folder).as_posix()
                require(relative in referenced,
                        f"wave {wave}: {base}/{relative} is referenced by no ledger row and not by the run "
                        "manifest; a sealed wave is never rewritten or extended outside record_verdicts.py")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value, label):
    require(isinstance(value, str) and bool(value.strip()), label + " must be nonempty text")
    return value


def strings(value, label):
    require(isinstance(value, list) and bool(value), label + " must be a nonempty list")
    for item in value:
        nonempty(item, label)
    require(len(value) == len(set(value)), label + " contains duplicates")
    return value


def https_url(value):
    if not isinstance(value, str) or any(ord(c) < 33 for c in value) or "\\" in value:
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and bool(parsed.hostname)
                and not parsed.username and not parsed.password
                and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                and parsed.port in {None, 443})
    except ValueError:
        return False


def validate_verdict_row(row, key, *, root, identities, aliases, evidence, recipe_map, sota_pins,
                          status_context, lane_registry=None, wave_refs=None):
    """Layer-verdict schema v2 checks for a single landscape row. ``evidence``
    is the confined evidence()/track() helper already bound to this run; a
    winner/alternative's ``evidence_refs`` may be an empty list (schema v2
    allows empty containers while ``verdict_status`` is ``pending_lanes``)."""

    def evidence_maybe_empty(values, label):
        require(isinstance(values, list), label + " must be a list")
        return evidence(values, label) if values else []

    require(row.get("verdict_status") in VERDICT_STATUSES, str(key) + ".verdict_status is unknown")
    require(isinstance(row.get("checked_at"), str) and bool(row["checked_at"]),
            str(key) + ".checked_at must be nonempty text")
    try:
        date.fromisoformat(row["checked_at"])
    except ValueError as error:
        raise ValueError(str(key) + ".checked_at must be an ISO date") from error

    protocol = row.get("overturn_protocol")
    require(isinstance(protocol, dict), str(key) + ".overturn_protocol must be an object")
    require(isinstance(protocol.get("fixture_paths"), list)
            and all(isinstance(item, str) for item in protocol["fixture_paths"]),
            str(key) + ".overturn_protocol.fixture_paths must be a list of text")
    require(isinstance(protocol.get("metric"), str), str(key) + ".overturn_protocol.metric must be text")
    require(isinstance(protocol.get("arms"), list), str(key) + ".overturn_protocol.arms must be a list")

    lanes_field = row.get("lanes")
    require(isinstance(lanes_field, dict), str(key) + ".lanes must be an object")
    # The sealed directory a row's lanes point at is recorded on the row itself
    # (tools/sota-convergence/record_verdicts.py's "sealed_base"), not read from
    # a global constant here, so a later run's rows can point at a later sealed
    # wave (evidence/artifacts/layer-verdicts-<run-id>/) while an older sealed
    # run stays intact and verifiable. A row recorded before this field existed
    # (or one recorded with the default run id) omits it and falls back to the
    # sealed 2026-09-22 wave, keeping every already-checked-in row valid.
    sealed_base = lanes_field.get("sealed_base") or DEFAULT_SEALED_BASE
    require(isinstance(sealed_base, str) and re.fullmatch(r"evidence/artifacts/layer-verdicts-[0-9A-Za-z]+",
                                                           sealed_base),
            str(key) + ".lanes.sealed_base must be evidence/artifacts/layer-verdicts-<run-id>")
    wave = run_id_of(sealed_base)
    for lane_name in LANES:
        lane = lanes_field.get(lane_name)
        require(isinstance(lane, dict), str(key) + f".lanes.{lane_name} must be an object")
        require(isinstance(lane.get("run_id"), str), str(key) + f".lanes.{lane_name}.run_id must be text")
        require(isinstance(lane.get("sealed_sha256"), str), str(key) + f".lanes.{lane_name}.sealed_sha256 must be text")
    # A row gets every new-wave rule when its sealed_base OR any lane run id (the recorder's
    # <catalog>-<layer_id>-<run-id>) names a non-grandfathered wave, whether or not a lane carries a
    # run id: a hand edit cannot drop the rules by emptying a run id or omitting sealed_base.
    run_prefix = f"{key[0]}-{key[1]}-"
    named_waves = {wave} | {lanes_field[lane]["run_id"][len(run_prefix):] for lane in LANES
                            if lanes_field[lane]["run_id"].startswith(run_prefix)}
    grandfathered = all(is_grandfathered_run(named) for named in named_waves)
    if not grandfathered:
        require(not is_grandfathered_run(wave),
                str(key) + ".lanes run ids name wave(s) " + ", ".join(sorted(named_waves - {wave}))
                + " but lanes.sealed_base names the grandfathered wave " + str(wave))
        for lane_name in LANES:
            lane = lanes_field[lane_name]
            require(lane["run_id"] in ("", run_prefix + wave),
                    str(key) + f".lanes.{lane_name}.run_id must be {run_prefix + wave!r} in wave {wave}")
            require(bool(lane["run_id"]) == bool(lane["sealed_sha256"]),
                    str(key) + f".lanes.{lane_name} must carry a run_id exactly when it carries a sealed_sha256")
    sealed_returns = {}
    for lane_name in LANES:
        lane = lanes_field[lane_name]
        sealed = lane["sealed_sha256"]
        if sealed:
            require(bool(re.fullmatch(r"[a-f0-9]{64}", sealed)),
                    str(key) + f".lanes.{lane_name}.sealed_sha256 must be a lowercase 64-digit hash")
            sealed_path = f"{sealed_base}/{lane_name}/{lane['run_id']}.json"
            sealed_file = safe_file(root, sealed_path)
            require(sealed_file.is_file(),
                    str(key) + f".lanes.{lane_name}.sealed_sha256 needs a sealed file: {sealed_path}")
            sealed_bytes = sealed_file.read_bytes()
            require(hashlib.sha256(sealed_bytes).hexdigest() == sealed,
                    str(key) + f".lanes.{lane_name}.sealed_sha256 does not match {sealed_path}")
            sealed_returns[lane_name] = sealed_bytes
    require(lanes_field.get("agreement") in LANE_AGREEMENTS, str(key) + ".lanes.agreement is unknown")
    parsed_returns = {}
    if not grandfathered:
        # Lane identity, family and provenance are re-checked from the sealed returns themselves.
        families = []
        for lane_name, sealed_bytes in sealed_returns.items():
            try:
                sealed_return = json.loads(sealed_bytes)
            except ValueError as error:
                raise ValueError(str(key) + f".lanes.{lane_name} sealed return is not JSON") from error
            require(isinstance(sealed_return, dict), str(key) + f".lanes.{lane_name} sealed return must be an object")
            issue = lane_model_issue(lane_name, sealed_return.get("model"))
            require(issue is None, str(key) + f".lanes.{lane_name}: {issue}")
            issue = lane_provenance_issue(lane_name, sealed_return.get("provenance"))
            require(issue is None, str(key) + f".lanes.{lane_name}: {issue}")
            issue = lane_provenance_registry_issue(lane_name, sealed_return["provenance"],
                                                   lane_registry if lane_registry is not None
                                                   else load_lane_provenance_registry(root))
            require(issue is None, str(key) + f".lanes.{lane_name}: {issue}")
            if lane_name == "claude":
                issue = claude_refutation_issue(sealed_return.get("refutation"))
                require(issue is None, str(key) + f".lanes.claude: {issue}")
            families.append(sealed_return["model"]["family"])
            parsed_returns[lane_name] = sealed_return
        require(len(families) == len(set(families)), str(key) + ".lanes must come from two different model families")
        # Survivorship: the row must be accounted for in its wave's run manifest.
        manifest_path = f"{sealed_base}/{RUN_MANIFEST_NAME}"
        manifest_file = safe_file(root, manifest_path)
        require(manifest_file.is_file(), str(key) + f" was recorded in wave {wave} but its run manifest "
                                                  f"{manifest_path} is missing")
        manifest_bytes = manifest_file.read_bytes()
        run_manifest = json.loads(manifest_bytes)
        issue = run_manifest_row_issue(run_manifest, wave, key[0], key[1], lanes_field)
        require(issue is None, str(key) + ": " + str(issue))
        # The row is bound to the exact run manifest it was recorded with (finding 3).
        require(lanes_field.get("run_manifest_sha256") == hashlib.sha256(manifest_bytes).hexdigest(),
                str(key) + f".lanes.run_manifest_sha256 must be the sha256 of its run manifest {manifest_path}")
        packet_sha256 = next(entry["packet_sha256"] for entry in run_manifest["packets"]
                             if isinstance(entry, dict) and (entry.get("catalog"), entry.get("layer_id")) == (key[0], key[1]))
        # The packet both lanes judged is retained under the sealed folder (finding 6).
        packet_relative = f"{RETAINED_PACKETS_DIR}/{key[0]}__{key[1]}.json"
        packet_file = safe_file(root, f"{sealed_base}/{packet_relative}")
        require(packet_file.is_file() and hashlib.sha256(packet_file.read_bytes()).hexdigest() == packet_sha256,
                str(key) + f" needs its retained packet {sealed_base}/{packet_relative} with the run manifest's "
                           "packet_sha256")
        retained_packet = json.loads(packet_file.read_text(encoding="utf-8"))
        if packet_seals_candidates(retained_packet):
            # Winner component ids resolve against the candidates' sealed manifest fields (review of #145).
            keys_file = safe_file(root, f"{sealed_base}/{PACKET_KEYS_NAME}")
            require(keys_file.is_file() and hashlib.sha256(keys_file.read_bytes()).hexdigest()
                    == run_manifest.get("packet_keys_sha256"),
                    str(key) + f" needs {sealed_base}/{PACKET_KEYS_NAME} with the run manifest's packet_keys_sha256")
            keys_doc = json.loads(keys_file.read_text(encoding="utf-8"))
            packet_name = f"{key[0]}__{key[1]}.json"
            issue = packet_keys_issue(keys_doc, packet_name, packet_sha256, retained_packet)
            require(issue is None, str(key) + f": {issue}")
            retained_packet = unseal_packet(retained_packet, keys_doc, packet_name)
        if wave_refs is not None:
            wave_refs.setdefault(wave, set()).update(
                f"{lane}/{lanes_field[lane]['run_id']}.json" for lane in sealed_returns)
    else:
        packet_sha256 = None

    open_gaps = row.get("open_gaps")
    require(isinstance(open_gaps, list) and all(isinstance(gap, str) and gap.strip() for gap in open_gaps),
            str(key) + ".open_gaps must be a list of nonempty text")

    winners = row.get("winners")
    require(isinstance(winners, list), str(key) + ".winners must be a list")
    winner_component_ids = set()
    for winner in winners:
        require(isinstance(winner, dict), str(key) + ".winner must be an object")
        component_id = nonempty(winner.get("component_id"), str(key) + ".winner.component_id")
        require(component_id not in winner_component_ids, str(key) + " has a duplicate winner component_id")
        winner_component_ids.add(component_id)
        repository = winner.get("repository")
        if repository is not None:
            require(https_url(repository), str(key) + ".winner.repository must be an https URL or null")
            repo_id = canonical(identity(repository), aliases)
            require(repo_id in identities, str(key) + ".winner.repository absent from canonical index")
        require(isinstance(winner.get("pin"), str), str(key) + ".winner.pin must be text")
        if component_id in sota_pins:
            require(winner["pin"] == sota_pins[component_id],
                    str(key) + ".winner.pin differs from the sota manifest pin for " + component_id)
        require(winner.get("evidence_class") in WINNER_EVIDENCE_CLASSES,
                str(key) + ".winner.evidence_class is unknown")
        nonempty(winner.get("why_selected"), str(key) + ".winner.why_selected")
        evidence_maybe_empty(winner.get("evidence_refs"), str(key) + ".winner.evidence_refs")
        recipe_ref = winner.get("recipe_ref")
        nonempty(recipe_ref, str(key) + ".winner.recipe_ref")
        require(recipe_ref in recipe_map or safe_file(root, recipe_ref).exists(),
                str(key) + ".winner.recipe_ref must resolve to a recipe_map key or an existing path")
        platform_status = winner.get("platform_status")
        require(isinstance(platform_status, dict) and set(platform_status) == PLATFORM_KEYS,
                str(key) + ".winner.platform_status must cover exactly " + ", ".join(sorted(PLATFORM_KEYS)))
        for platform, value in platform_status.items():
            require(value in PLATFORM_ALLOWED[platform],
                    str(key) + ".winner.platform_status." + platform + " must be one of "
                    + ", ".join(sorted(PLATFORM_ALLOWED[platform])))
            # A new wave's rows were derived through scripts/platform_status.py for every platform
            # (tools/sota-convergence/record_verdicts.py), so none may claim more than it derives;
            # grandfathered rows are held to it for ENFORCED_PLATFORMS only.
            if platform in ENFORCED_PLATFORMS or not grandfathered:
                error = platform_evidence.declared_status_error(platform, value, winner, status_context)
                require(error is None, str(key) + ".winner " + str(winner.get("component_id")) + ": " + str(error))

    alternatives = row.get("alternatives")
    require(isinstance(alternatives, list), str(key) + ".alternatives must be a list")
    why_not_defaults = set()
    for alternative in alternatives:
        require(isinstance(alternative, dict), str(key) + ".alternative must be an object")
        nonempty(alternative.get("name"), str(key) + ".alternative.name")
        repository = alternative.get("repository")
        require(https_url(repository), str(key) + ".alternative.repository must be an https URL")
        repo_id = canonical(identity(repository), aliases)
        require(repo_id in identities, str(key) + ".alternative.repository absent from canonical index")
        require(alternative.get("disposition") in DISPOSITIONS, str(key) + ".alternative.disposition is unknown")
        why_not = nonempty(alternative.get("why_not_default"), str(key) + ".alternative.why_not_default")
        why_not_defaults.add(why_not)
        require(alternative.get("evidence_class") in WINNER_EVIDENCE_CLASSES,
                str(key) + ".alternative.evidence_class is unknown")
        evidence_maybe_empty(alternative.get("evidence_refs"), str(key) + ".alternative.evidence_refs")
        require(alternative.get("source") in ALTERNATIVE_SOURCES, str(key) + ".alternative.source is unknown")

    verdict_overturn_when = row.get("verdict_overturn_when", "")
    require(isinstance(verdict_overturn_when, str), str(key) + ".verdict_overturn_when must be text")
    status = row["verdict_status"]
    chosen_lane = None
    if status == "recorded":
        require(bool(winners), str(key) + " recorded verdict needs at least one winner")
        require(bool(alternatives), str(key) + " recorded verdict needs at least one alternative")
        for winner in winners:
            require(winner.get("why_selected") not in why_not_defaults,
                    str(key) + ".winner.why_selected must differ from every alternative's why_not_default")
        # The v1 ``overturn_when`` belongs to the dated review that the quality
        # comparison mirrors; a recorded verdict carries its own condition.
        winner_ids = {canonical(identity(w["repository"]), aliases) for w in winners if w.get("repository")}
        require(not any(canonical(identity(a["repository"]), aliases) in winner_ids for a in alternatives),
                str(key) + " lists a winner repository among its alternatives")
        require(any(marker in verdict_overturn_when for marker in OVERTURN_MARKERS),
                str(key) + ".verdict_overturn_when must name a fixture/blueprint/test path or a runnable command "
                           "for a recorded verdict")
        agreement = lanes_field.get("agreement")
        require(agreement in {"same_winner", "disagree", "codex_absent"},
                str(key) + " recorded verdict needs lanes.agreement same_winner, disagree or codex_absent")
        # The lanes each agreement implies must be sealed (a recorded row always seals the claude lane).
        sealed_lanes = {lane for lane in LANES if lanes_field[lane].get("sealed_sha256")}
        if agreement == "codex_absent":
            require(sealed_lanes == {"claude"},
                    str(key) + " codex_absent verdict needs the claude lane sealed and the codex lane unsealed")
            issue = single_lane_decision_issue(root, lanes_field.get("single_lane_decision"), key[0], key[1],
                                               lanes_field.get("single_lane_decision_sha256"))
            require(issue is None, str(key) + ": " + str(issue))
            chosen_lane = "claude"
        elif agreement == "same_winner":
            require(sealed_lanes == set(LANES), str(key) + " same_winner verdict needs both lanes sealed")
            chosen_lane = "claude"
        else:
            require(sealed_lanes == set(LANES), str(key) + " disagree verdict needs both lanes sealed")
            adjudication_path = f"{sealed_base}/adjudication/{lanes_field['claude'].get('run_id')}.json"
            adjudication_file = safe_file(root, adjudication_path)
            require(adjudication_file.is_file(),
                    str(key) + f" disagree verdict needs its sealed adjudication {adjudication_path}")
            issue, result = judge_adjudication(json.loads(adjudication_file.read_text(encoding="utf-8")),
                                               grandfathered=grandfathered, packet_sha256=packet_sha256)
            require(issue is None, str(key) + f" adjudication {adjudication_path}: {issue}")
            require(result["winner_lane"] is not None,
                    str(key) + f" adjudication {adjudication_path} is a split and cannot record a winner"
                    + (f" ({result['split_reason']})" if result["split_reason"] else ""))
            if not grandfathered:
                require(lanes_field.get("adjudication_sha256") is not None,
                        str(key) + f".lanes.adjudication_sha256 must bind the sealed adjudication {adjudication_path}")
            chosen_lane = result["winner_lane"]
    elif status == "no_selection":
        require(bool(open_gaps), str(key) + " no_selection verdict needs open_gaps")
    if lanes_field.get("single_lane_decision") is not None:
        require(lanes_field.get("agreement") == "codex_absent",
                str(key) + ".lanes.single_lane_decision is only meaningful on a codex_absent row")
    if not grandfathered:
        verify_new_wave_row(row, key, root=root, sealed_base=sealed_base, wave=wave, lanes_field=lanes_field,
                            parsed_returns=parsed_returns, retained_packet=retained_packet,
                            packet_sha256=packet_sha256, winners=winners,
                            chosen_lane=chosen_lane if status == "recorded" else None, wave_refs=wave_refs)


def verify_new_wave_row(row, key, *, root, sealed_base, wave, lanes_field, parsed_returns, retained_packet,
                        packet_sha256, winners, chosen_lane, wave_refs):
    """The new-wave row is what its sealed returns establish (2026-09-23 review of #122, finding 1):
    every sealed return names the retained packet; the agreement is recomputed from both returns'
    winner component ids; a recorded row's winners are exactly the chosen lane's (same_winner or
    codex_absent: the claude lane, disagree: the adjudication's winner_lane); an unrecorded row has
    none. A sealed adjudication (a recorded disagreement or a sealed split) is bound by
    lanes.adjudication_sha256 (finding 3)."""
    lane_sets = {}
    for lane, sealed_return in parsed_returns.items():
        require(sealed_return.get("packet_sha256") == packet_sha256,
                str(key) + f".lanes.{lane} sealed return names packet_sha256 {sealed_return.get('packet_sha256')!r}, "
                           f"not the retained packet {packet_sha256}")
        issue, components = lane_winner_components(sealed_return, retained_packet)
        require(issue is None, str(key) + f".lanes.{lane} sealed return: {issue}")
        lane_sets[lane] = components
    if set(parsed_returns) == set(LANES):
        trees = {lane: (sealed_return.get("provenance") or {}).get("repo_tree_sha256")
                 for lane, sealed_return in parsed_returns.items()}
        require(trees["claude"] == trees["codex"],
                str(key) + f" the sealed lane returns read different evidence trees ({trees})")
    if set(lane_sets) == set(LANES):
        computed = "same_winner" if lane_sets["claude"] == lane_sets["codex"] else "disagree"
    elif "claude" in lane_sets:
        computed = "codex_absent"
    else:
        computed = "pending"
    require(lanes_field.get("agreement") == computed,
            str(key) + f".lanes.agreement {lanes_field.get('agreement')!r} is not what its sealed returns establish "
                       f"({computed!r}: claude={sorted(c for c, _ in lane_sets.get('claude', ()))}, "
                       f"codex={sorted(c for c, _ in lane_sets.get('codex', ()))})")
    row_winners = {(winner.get("component_id"), winner.get("repository")) for winner in winners}
    if chosen_lane is None:
        require(not winners, str(key) + " a new-wave row that is not recorded carries no winners")
    else:
        require(row_winners == lane_sets.get(chosen_lane) and len(row_winners) == len(winners),
                str(key) + f" winners {sorted(c for c, _ in row_winners)} are not the {chosen_lane} lane's sealed "
                           f"winner set {sorted(c for c, _ in lane_sets.get(chosen_lane, ()))}")
    adjudication_sha256 = lanes_field.get("adjudication_sha256")
    if adjudication_sha256 is not None:
        require(lanes_field.get("agreement") == "disagree",
                str(key) + ".lanes.adjudication_sha256 is only meaningful on a disagree row")
        relative = f"adjudication/{lanes_field['claude'].get('run_id')}.json"
        adjudication_file = safe_file(root, f"{sealed_base}/{relative}")
        require(adjudication_file.is_file()
                and hashlib.sha256(adjudication_file.read_bytes()).hexdigest() == adjudication_sha256,
                str(key) + f".lanes.adjudication_sha256 does not match {sealed_base}/{relative}")
        raw = json.loads(adjudication_file.read_text(encoding="utf-8"))
        issue, _ = judge_adjudication(raw, grandfathered=False, packet_sha256=packet_sha256)
        require(issue is None, str(key) + f" adjudication {sealed_base}/{relative}: {issue}")
        issue = adjudication_binding_issue(
            raw, {lane: lanes_field[lane].get("sealed_sha256") for lane in LANES},
            {lane: (parsed_returns.get(lane, {}).get("provenance") or {}).get("repo_tree_sha256") for lane in LANES},
            load_lane_provenance_registry(root))
        require(issue is None, str(key) + f" adjudication {sealed_base}/{relative}: {issue}")
        if wave_refs is not None:
            wave_refs.setdefault(wave, set()).add(relative)


def build_landscape(root, manifest_path=MANIFEST, *, read=None, track=None, file_url=None):
    """Resolve references using the explorer's existing confined loader/hash registry."""
    root = Path(root).resolve()
    read = read or (lambda path: load(root, path))
    track = track or (lambda path: safe_file(root, path).read_bytes())
    file_url = file_url or (lambda path: path)
    manifest = read(manifest_path)
    require(manifest.get("schema_version") == 1, "unsupported landscape schema")
    date.fromisoformat(manifest["checked_at"])
    require(bool(re.fullmatch(r"[a-f0-9]{40}", manifest["source_base"])), "landscape needs a full source base")
    for field in ("scope", "status", "new_pc_scope"):
        nonempty(manifest.get(field), "landscape." + field)
    strings(manifest.get("rules"), "landscape.rules")
    require(manifest.get("universal_superiority") == "not_established",
            "landscape must preserve the unestablished universal-superiority boundary")
    sources = manifest["sources"]
    foundation = read(sources["foundation_manifest"])
    domain = read(sources["domain_manifest"])
    index = read(sources["repository_index"])
    aliases = index.get("aliases", {})
    identities = {identity(row["repository"]) for row in index["records"]}
    stack = read(sources["selected_manifest"])
    expected = {("foundation", row["id"]) for row in foundation["layers"]}
    domain_documents = {path: read(path) for path in domain["catalog_files"]}
    domain_group_ids = {document["layer"] for document in domain_documents.values()}
    # The 12-layer US-equities taxonomy is sourced live from the dated SOTA-
    # convergence manifest's trading[].layer ids, never hardcoded here.
    trading_taxonomy_doc = read(sources["trading_taxonomy"])
    trading_layer_ids = sorted({row["layer"] for row in trading_taxonomy_doc.get("trading", [])})
    require(bool(trading_layer_ids), "trading taxonomy needs at least one layer")
    expected.update(("us-equities", layer_id) for layer_id in trading_layer_ids)
    recipe_map = read("adoption/manifest.json").get("recipe_map", {})
    lane_registry = load_lane_provenance_registry(root)
    wave_refs = {}
    # Per-layer, not a single flattened map: a component id can recur across
    # layers with a different pin in each (tools/sota-convergence/build_verdicts.py's
    # sota_layer_index keeps the same per-layer scope for its own join, so the
    # generator and this validator agree on which pin governs a given winner).
    sota_pins_by_layer = defaultdict(dict)
    for row in trading_taxonomy_doc.get("foundation", []):
        for component in row.get("components", []):
            sota_pins_by_layer[row["layer"]][component["id"]] = component.get("pin")
    for row in trading_taxonomy_doc.get("trading", []):
        for entry in row.get("entries", []):
            sota_pins_by_layer[row["layer"]][entry["id"]] = entry.get("pin")

    def evidence(values, label):
        result = []
        for value in strings(values, label):
            if value.startswith("https://"):
                require(https_url(value), label + " has an unsafe source URL")
                result.append({"path": value, "url": value})
            else:
                require(safe_file(root, value).is_file(), label + " evidence file missing: " + value)
                track(value)
                result.append({"path": value, "url": file_url(value)})
        return result

    status_context = platform_evidence.load_context(root)

    documents = manifest["catalogs"]
    require(set(documents) == {"foundation", "us-equities"}, "landscape must cover both catalogs")
    layers, seen, decision_pointers = [], set(), {}
    for catalog, path in documents.items():
        document = read(path)
        require(document.get("schema_version") == 2, "unsupported layer comparison schema")
        require(document.get("checked_at") == manifest["checked_at"], "layer review date differs from manifest")
        nonempty(document.get("scope"), path + ".scope")
        require(isinstance(document.get("layers"), list), path + " needs layers")
        for position, row in enumerate(document["layers"]):
            key = (row["catalog"], row["layer_id"])
            require(key[0] == catalog and key in expected, "unknown comparison layer: " + str(key))
            require(key not in seen, "duplicate comparison layer: " + str(key))
            seen.add(key)
            decision_pointers[key] = path + "#/layers/" + str(position)
            for field in ("title", "requirement", "current_choice", "rationale", "overturn_when"):
                nonempty(row.get(field), str(key) + "." + field)
            require(row.get("decision") in DECISIONS, "unknown layer decision")
            strings(row.get("limitations"), str(key) + ".limitations")
            group = row.get("group")
            if catalog == "us-equities":
                require(group in domain_group_ids, str(key) + ".group must be a domain document id")
            else:
                require(group is None, str(key) + ".group is only used for trading rows")
            validate_verdict_row(row, key, root=root, identities=identities, aliases=aliases,
                                  evidence=evidence, recipe_map=recipe_map,
                                  sota_pins=sota_pins_by_layer.get(key[1], {}),
                                  status_context=status_context, lane_registry=lane_registry,
                                  wave_refs=wave_refs)
            source_links = evidence(row.get("evidence_refs"), str(key))
            candidates, candidate_ids = [], set()
            require(isinstance(row.get("candidates"), list) and row["candidates"], "layer needs candidates")
            for candidate in row["candidates"]:
                for field in ("name", "rationale"):
                    nonempty(candidate.get(field), "candidate." + field)
                repository = candidate.get("repository")
                require(https_url(repository) and bool(re.fullmatch(
                    r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)),
                    "candidate needs a canonical public repository URL")
                repo_id = canonical(identity(repository), aliases)
                require(repo_id in identities, "comparison repository absent from canonical index: " + repo_id)
                require(repo_id not in candidate_ids, "duplicate candidate repository in layer: " + repo_id)
                candidate_ids.add(repo_id)
                require(candidate.get("disposition") in DISPOSITIONS, "unknown candidate disposition")
                require(candidate.get("evidence_kind") in EVIDENCE_KINDS, "unknown candidate evidence kind")
                candidate_sources = evidence(candidate.get("evidence_refs"), candidate["name"])
                if candidate["disposition"] == "observed_failure":
                    require(candidate["evidence_kind"] in {"native_execution", "measured_comparison", "mixed"},
                            "observed failure needs execution evidence, not source screening")
                    require(any(not ref.startswith("https://") and ref.endswith((".json", ".txt", ".log"))
                                for ref in candidate["evidence_refs"]),
                            "observed failure needs a retained local result")
                candidates.append({**candidate, "repository_id": repo_id, "sources": candidate_sources})
            require(any(row["disposition"] == "selected" for row in candidates), "layer needs a selected candidate")
            require(any(row["disposition"] != "selected" for row in candidates), "layer needs a named alternative")
            layers.append({**row, "id": ":".join(key), "candidates": candidates,
                           "sources": source_links, "url": file_url(path), "catalog_candidates": []})
    require(seen == expected, "comparison coverage must exactly match all foundation and domain layers")
    verify_sealed_waves(root, wave_refs)

    component_coverage = []
    for component in stack["components"]:
        repo_id = canonical(identity(component["repository"]), aliases)
        matched = [layer["id"] for layer in layers
                   if any(candidate["repository_id"] == repo_id for candidate in layer["candidates"])]
        require(bool(matched), "selected component lacks a current role explanation: " + component["id"])
        component_coverage.append({"component_id": component["id"], "repository_id": repo_id,
                                   "profile": component.get("profile"), "layer_ids": matched})

    research = None
    if sources.get("research_state"):
        research = read(sources["research_state"])
        require(research.get("schema_version") == 1 and research.get("checked_at") == manifest["checked_at"],
                "research state schema or date differs from landscape")
        for field in ("scope",):
            nonempty(research.get(field), "research." + field)
        strings(research.get("resume_order"), "research.resume_order")
        saturation = research.get("saturation", {})
        require(saturation.get("status") in {"not_established", "bounded_review_complete"},
                "unknown research saturation status")
        strings(saturation.get("close_only_when"), "research closure criteria")
        strings(saturation.get("reopen_on"), "research reopening criteria")
        research["sources"] = evidence(research.get("source_inventory_refs"), "research inventories")
        research["guide_url"] = evidence([research.get("guide")], "research guide")[0]["url"]
        queue_keys = set()
        require(isinstance(research.get("layers"), list), "research queue needs layers")
        for item in research["layers"]:
            key = (item.get("catalog"), item.get("layer_id"))
            require(key in expected and key not in queue_keys, "unknown or duplicate research layer")
            queue_keys.add(key)
            require(item.get("status") in {"on_requirement_change", "comparison_required", "new_host_required", "bounded_review_complete"},
                    "unknown research queue status")
            if item["status"] == "bounded_review_complete":
                require(item.get("saturation") == "bounded_review_complete", "inconsistent layer closure")
                item["closure_sources"] = evidence(item.get("closure_refs"), "layer closure")
                require(any(not row["path"].startswith("https://") for row in item["closure_sources"]),
                        "layer closure requires a retained local record")
            else:
                require(item.get("saturation") == "not_established", "open layer cannot claim closure")
            nonempty(item.get("next_action"), "research next action")
            require(item.get("decision_ref") == documents[key[0]], "research decision reference differs from catalog")
            item["sources"] = evidence(item.get("evidence_refs"), "research layer")
            next(layer for layer in layers if layer["id"] == ":".join(key))["research"] = item
        require(queue_keys == expected, "research queue must cover every layer exactly once")
        if saturation["status"] == "bounded_review_complete":
            require(all(item["status"] == "bounded_review_complete" for item in research["layers"]),
                    "overall closure requires every layer's bounded closure")
            saturation["sources"] = evidence(saturation.get("closure_refs"), "overall closure")
            require(any(not row["path"].startswith("https://") for row in saturation["sources"]),
                    "overall closure requires a retained local record")
        research["url"] = file_url(sources["research_state"])

    # All historical candidate cards remain visible with their original date and
    # role. They do not override the explicitly dated current comparison above.
    # Schema v2: a domain document (foundation-memory/agents-operations/
    # data-research/engines-strategies) no longer binds 1:1 to a us-equities
    # layer_id; it binds through every row whose "group" equals the document's
    # own "layer" id, since the 12-layer trading taxonomy consolidates several
    # taxonomy layers under one domain document's primary contribution.
    by_key = {(row["catalog"], row["layer_id"]): row for row in layers}
    group_rows = defaultdict(list)
    for row in layers:
        if row["catalog"] == "us-equities":
            group_rows[row.get("group")].append(row)
    for path, document in domain_documents.items():
        matched_rows = group_rows.get(document["layer"], [])
        require(matched_rows, "domain document maps to no landscape row group: " + document["layer"])
        for position, row in enumerate(document["entries"]):
            candidate_entry = {
                "id": row["id"], "name": row["repository"].removeprefix("https://github.com/"),
                "repository": row["repository"], "role": row["role"], "decision": row["decision"],
                "rationale": row["rationale"], "evidence_kind": row["evidence_level"],
                "pin": row["version_or_commit"], "limitations": row["limitations"],
                "checked_at": document["checked_at"], "url": file_url(path) + "#L1",
                "pointer": "/entries/" + str(position),
                "sources": evidence(row["evidence_refs"], row["id"]),
            }
            for matched in matched_rows:
                matched["catalog_candidates"].append(dict(candidate_entry))

    freshness = read(sources["freshness_snapshot"])
    require(freshness.get("schema_version") == 1, "unsupported upstream snapshot schema")
    checked = freshness.get("components")
    require(isinstance(checked, list), "freshness snapshot needs component records")
    checked_ids = [row.get("component_id") for row in checked]
    selected_by_id = {row["id"]: row for row in stack["components"]}
    require(len(checked_ids) == len(set(checked_ids)) and set(checked_ids) == set(selected_by_id),
            "freshness snapshot must cover every selected component exactly once")
    for row in checked:
        selected = selected_by_id[row["component_id"]]
        require(row.get("selected_version") == selected.get("version"),
                "freshness selected version differs from current manifest")
        require(row.get("selected_source_pin") == selected.get("source_pin"),
                "freshness selected source pin differs from current manifest")
        require(canonical(identity(row.get("selected_repository_url")), aliases)
                == canonical(identity(selected.get("repository")), aliases),
                "freshness selected repository differs from current manifest")
    stars = freshness.get("stars", {})
    require(stars.get("status") == "checked", "current public-star snapshot is not checked")
    observed = stars.get("repositories")
    require(isinstance(observed, list), "current public-star identities missing")
    star_urls = [row["repository"].lower() for row in observed]
    require(len(star_urls) == len(set(star_urls)) == stars.get("repository_snapshot_count"),
            "current public-star count or identity duplication mismatch")
    require(all(https_url(url) and canonical(identity(url), aliases) in identities for url in star_urls),
            "current public-star identity absent from canonical index")
    require(hashlib.sha256("\n".join(sorted(star_urls)).encode()).hexdigest()
            == stars.get("observed_identity_set_sha256"), "current public-star identity hash mismatch")
    review_status = Counter(row["review_status"] for row in read(sources["foundation_decisions"])["decisions"])
    counts = {"layers": len(layers), "foundation_layers": len(foundation["layers"]),
              "domain_layers": len(domain_documents), "selected_components": len(stack["components"]),
              "research_repositories": len(identities), "foundation_decisions": sum(review_status.values()),
              "current_public_stars": len(star_urls),
              "explained_components": len(component_coverage),
              "foundation_statuses": dict(sorted(review_status.items())),
              "comparison_candidates": sum(len(row["candidates"]) for row in layers),
              "comparison_repositories": len({candidate["repository_id"] for row in layers
                                               for candidate in row["candidates"]}),
              # Distinct cards, not the sum across every matched row: schema v2
              # fans the same domain-document entry out onto every row in its
              # group (rows sharing one "group" all show the same historical
              # cards), so summing catalog_candidates per row would multiply
              # each card by the number of rows in its group.
              "historical_candidate_cards": sum(len(document["entries"])
                                                 for document in domain_documents.values()),
              "dispositions": dict(sorted(Counter(candidate["disposition"] for row in layers
                                                    for candidate in row["candidates"]).items()))}
    practice = None
    if sources.get("native_practice"):
        practice = read(sources["native_practice"])
        require(practice.get("schema_version") == 1 and practice.get("checked_at") == manifest["checked_at"],
                "native practice schema or date differs from landscape")
        require(isinstance(practice.get("skills"), list) and practice["skills"], "native practice needs selected skills")
        names = set()
        for skill in practice["skills"]:
            name = nonempty(skill.get("name"), "skill.name")
            require(name not in names, "duplicate selected skill")
            names.add(name)
            require(canonical(identity(skill.get("repository")), aliases) in identities,
                    "selected skill repository absent from index")
            require(isinstance(skill.get("source_pin"), str) and re.fullmatch(r"[0-9a-f]{40}", skill["source_pin"]),
                    "selected skill needs a full source commit")
            require(isinstance(skill.get("skill_sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", skill["skill_sha256"]),
                    "selected skill needs its exact content hash")
            nonempty(skill.get("rationale"), "skill.rationale")
            require(isinstance(skill.get("limits"), list) and skill["limits"], "selected skill needs limits")
            skill["sources"] = evidence(skill.get("evidence_refs"), name)
        practice = {**practice, "url": file_url(sources["native_practice"])}
        counts["applied_skills"] = len(names)
    if research:
        counts["research_queue_layers"] = len(research["layers"])
    quality = None
    if sources.get("quality_review"):
        quality = read(sources["quality_review"])
        require(quality.get("schema_version") == 1 and quality.get("checked_at") == manifest["checked_at"],
                "quality review schema or date differs from landscape")
        require(quality.get("no_universal_ranking") is True,
                "quality review must preserve the unestablished universal ranking")
        nonempty(quality.get("scope"), "quality review scope")
        strings(quality.get("claim_limits"), "quality review limits")
        quality["snapshot_sources"] = evidence([quality.get("source_snapshot")], "quality source snapshot")
        snapshot = read(quality["source_snapshot"])
        snapshot_rows = snapshot.get("repositories")
        require(isinstance(snapshot_rows, list) and snapshot_rows, "quality snapshot needs repositories")
        pinned_sources = {}
        for row in snapshot_rows:
            require(isinstance(row, dict), "quality snapshot repository must be an object")
            repo_id = canonical(identity(row.get("repository")), aliases)
            require(repo_id not in pinned_sources, "duplicate quality snapshot repository")
            revision = row.get("revision")
            require(isinstance(revision, str) and bool(re.fullmatch(r"[a-f0-9]{40}", revision)),
                    "quality snapshot needs a full revision")
            files = row.get("source_files")
            require(isinstance(files, list) and bool(files), "quality snapshot needs source files")
            urls = set()
            for source in files:
                require(isinstance(source, dict), "quality source file must be an object")
                url = source.get("url")
                require(https_url(url), "unsafe quality snapshot source")
                parts = urlsplit(url)
                path_parts = parts.path.strip("/").split("/")
                require(parts.hostname == "raw.githubusercontent.com" and len(path_parts) >= 4
                        and canonical(identity("https://github.com/" + "/".join(path_parts[:2])), aliases) == repo_id
                        and path_parts[2] == revision,
                        "quality snapshot source differs from pinned repository")
                require(isinstance(source.get("sha256"), str)
                        and bool(re.fullmatch(r"[a-f0-9]{64}", source["sha256"]))
                        and isinstance(source.get("bytes"), int) and source["bytes"] > 0,
                        "quality snapshot source needs content hash and byte count")
                require(url not in urls, "duplicate quality snapshot source")
                urls.add(url)
            pinned_sources[repo_id] = (revision, urls)
        criteria = quality.get("criteria")
        require(isinstance(criteria, list) and bool(criteria), "quality review needs criteria")
        criterion_ids = set()
        for criterion in criteria:
            require(isinstance(criterion, dict), "quality criterion must be an object")
            key = nonempty(criterion.get("id"), "quality criterion id")
            require(key not in criterion_ids, "duplicate quality criterion")
            criterion_ids.add(key)
            nonempty(criterion.get("question"), "quality criterion question")
        candidates = quality.get("candidates")
        require(isinstance(candidates, list) and bool(candidates), "quality review needs candidates")
        quality_by_repo = {}
        compared_ids = {candidate["repository_id"] for layer in layers for candidate in layer["candidates"]}
        for candidate in candidates:
            require(isinstance(candidate, dict), "quality candidate must be an object")
            repo_id = canonical(identity(candidate.get("repository")), aliases)
            require(repo_id in compared_ids, "quality candidate lacks a current layer comparison")
            require(repo_id not in quality_by_repo, "duplicate quality repository identity")
            quality_by_repo[repo_id] = candidate
            require(bool(re.fullmatch(r"[a-f0-9]{40}", candidate.get("revision", ""))),
                    "quality source needs a full revision")
            require(repo_id in pinned_sources and candidate["revision"] == pinned_sources[repo_id][0],
                    "quality candidate revision differs from source snapshot")
            require(candidate.get("evidence_kind") == "source_review",
                    "repository quality source review cannot certify execution")
            require(candidate.get("disposition") in DISPOSITIONS - {"observed_failure"},
                    "quality source review cannot declare an observed failure")
            for field in ("name", "requirement_fit", "qualification_gap", "overturn_when"):
                nonempty(candidate.get(field), "quality candidate " + field)
            strings(candidate.get("source_findings"), "quality source findings")
            candidate["sources"] = evidence(candidate.get("evidence_refs"), "quality candidate")
            assessments = candidate.get("criteria")
            require(isinstance(assessments, dict) and set(assessments) == criterion_ids,
                    "quality candidate must address each declared criterion")
            for key, assessment in assessments.items():
                require(isinstance(assessment, dict), "quality assessment must be an object")
                nonempty(assessment.get("finding"), "quality finding " + key)
                refs = assessment.get("evidence_refs")
                require(isinstance(refs, list), "quality finding needs explicit evidence references")
                assessment["sources"] = evidence(refs, "quality criterion") if refs else []
            all_refs = candidate["evidence_refs"] + [ref for a in assessments.values() for ref in a["evidence_refs"]]
            raw_refs = {ref for ref in all_refs if urlsplit(ref).hostname == "raw.githubusercontent.com"}
            require(bool(raw_refs) and raw_refs.issubset(pinned_sources[repo_id][1]),
                    "quality candidate pinned sources differ from source snapshot")
        coverage = quality.get("layer_coverage")
        require(isinstance(coverage, list), "quality review needs layer coverage")
        quality_layers = set()
        for item in coverage:
            require(isinstance(item, dict), "quality layer must be an object")
            key = (item.get("catalog"), item.get("layer_id"))
            require(key in expected and key not in quality_layers, "unknown or duplicate quality layer")
            quality_layers.add(key)
            layer = by_key[key]
            require(item.get("decision_ref") == decision_pointers[key] and item.get("decision") == layer["decision"],
                    "quality layer decision differs from current comparison")
            for field in ("requirement", "current_choice", "evidence_gap", "overturn_when"):
                nonempty(item.get(field), "quality layer " + field)
            for field in ("requirement", "current_choice", "overturn_when"):
                require(item[field] == layer[field], "quality layer " + field + " differs from current comparison")
            challengers = strings(item.get("challenger_repositories"), "quality challengers")
            layer_ids = {candidate["repository_id"] for candidate in layer["candidates"]}
            require(all(canonical(identity(repo), aliases) in layer_ids for repo in challengers),
                    "quality challenger absent from its layer")
            if "evidence_refs" in item:
                item["sources"] = evidence(item["evidence_refs"], "quality layer")
        require(quality_layers == expected, "quality review must cover every layer exactly once")
        for layer in layers:
            for candidate in layer["candidates"]:
                if candidate["repository_id"] in quality_by_repo:
                    candidate["quality_review"] = quality_by_repo[candidate["repository_id"]]
        quality["url"] = file_url(sources["quality_review"])
        counts["quality_review_repositories"] = len(quality_by_repo)
    guides = manifest.get("handbook_guides", [])
    require(isinstance(guides, list), "handbook guides must be a list")
    for guide in guides:
        require(isinstance(guide, dict), "handbook guide must be an object")
        nonempty(guide.get("label"), "handbook guide label")
        require(isinstance(guide.get("path"), str) and guide["path"].endswith(".md"),
                "handbook guide must be Markdown")
        evidence([guide["path"]], "handbook guide")
    return {**manifest, "layers": layers, "counts": counts, "freshness": freshness, "native_practice": practice,
            "research_state": research, "component_coverage": component_coverage, "quality_review": quality,
            "url": file_url(manifest_path), "freshness_url": file_url(sources["freshness_snapshot"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        data = build_landscape(args.root)
        print(json.dumps({"status": "passed", "counts": data["counts"],
                          "scope": "Coverage and reference integrity; no new runtime or ranking acceptance."}, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("Landscape validation failed: " + str(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
