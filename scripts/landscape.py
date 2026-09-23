#!/usr/bin/env python3
"""Validate and join the dated landscape choices; never infer benchmark wins."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import NamedTuple
import re
from urllib.parse import urlsplit

try:
    from .catalog_decisions import canonical, identity, load, safe_file
except ImportError:
    from catalog_decisions import canonical, identity, load, safe_file

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
    "macos-arm64": {"untested"},
}
OVERTURN_MARKERS = ("fixtures/", "blueprints/", "tests/", "python3 ", "node ")

# --- Layer-verdict integrity rules (2026-09-23 peer audit) ---------------------------------------
# Shared by tools/sota-convergence/record_verdicts.py (record time) and this validator (CI re-check).
SEALED_BASE_PREFIX = "evidence/artifacts/layer-verdicts-"
DEFAULT_SEALED_BASE = SEALED_BASE_PREFIX + "20260922"
# Grandfathered wave: the 32 rows sealed on 2026-09-22 predate these rules. Their lane returns
# declare no model family or provenance, their adjudications are Opus-only (both presentation
# orders, no judge identity), they have no run manifest (their packets/ and SHA256SUMS are
# retained under the sealed base instead), and ci-supply-chain and hosting-services carry linux
# "accepted" without citing a registered receipt. That wave is frozen: build_verdicts.py --check
# compares every row naming it with its hash-registered layer-verdicts-20260922.json, so a row
# cannot be re-recorded under this run id without failing CI. Every other run id gets every rule.
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
    "claude": ("workflow_path", "workflow_sha256", "agentlab_commit"),
    "codex": ("codex_lane_py_sha256", "prompt_sha256"),
}
RUN_MANIFEST_NAME = "run-manifest.json"
LANE_OUTCOMES = {"sealed", "rejected", "missing"}
# A single-lane decision record must be dated in its file name (YYYY-MM-DD or YYYYMMDD).
DATED_NAME = re.compile(r"(?<![0-9])20[0-9]{2}-?(?:0[1-9]|1[0-2])-?(?:0[1-9]|[12][0-9]|3[01])(?![0-9])")
ACCEPTED_EVIDENCE_CLASSES = {"native_proven", "measured_comparison"}
EVIDENCE_MANIFEST = "manifests/evidence.json"


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


def lane_provenance_issue(lane, provenance):
    """A new-wave sealed return names what produced it: the Claude lane its workflow file, hash and
    agent-lab commit; the Codex lane the hashes of codex_lane.py and the prompt it filled."""
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


def judge_adjudication(raw, *, grandfathered):
    """Validate an adjudication record. Returns ``(issue, result)``; ``issue`` is a rejection
    reason or None. ``result['winner_lane']`` is the lane the adjudication establishes, or None
    for a split. A new wave establishes a winner only when judgments from BOTH lane families
    are present, each family covers both presentation orders, all pick the same lane and none
    is refuted; otherwise it is a split with ``split_reason``. The grandfathered 2026-09-22
    rule is the older one: both orders, all the same lane, none refuted, no judge identity."""
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
    if {judgment["claude_position"] for judgment in judgments} != {"A", "B"}:
        return "adjudication judgments must cover both presentation orders", None
    lanes = {judgment["preferred_lane"] for judgment in judgments}
    unrefuted = all(judgment["refuting_votes"] == 0 for judgment in judgments)
    agreed = next(iter(lanes)) if len(lanes) == 1 and unrefuted else None
    if winner_lane != agreed:
        return (f"winner_lane {winner_lane!r} must equal the lane every unrefuted judgment chose "
                f"({agreed!r}; null when the judgments split or any was refuted)"), None
    split_reason = None
    if agreed is not None and not grandfathered:
        orders = defaultdict(set)
        for judgment in judgments:
            orders[judgment["judge"]["family"]].add(judgment["claude_position"])
        missing = [family for family in sorted(set(LANE_FAMILIES.values())) if orders.get(family) != {"A", "B"}]
        if missing:
            split_reason = ("the adjudication needs unanimous judgments from both lane families in both "
                            "presentation orders; missing: " + ", ".join(missing))
            agreed = None
    tally = {lane: sum(judgment["preferred_lane"] == lane for judgment in judgments) for lane in LANES}
    return None, {"winner_lane": agreed, "tally": tally, "split_reason": split_reason,
                  "refuted": sum(judgment["refuting_votes"] > 0 for judgment in judgments)}


def registered_evidence_paths(evidence_document):
    """Repository paths a linux "accepted" winner may cite: every receipt listed in
    manifests/evidence.json receipts[], and every hash-registered files[] artifact under
    evidence/ (receipts, artifacts, host receipts). Docs and catalogs are not receipts."""
    paths = set()
    if not isinstance(evidence_document, dict):
        return paths
    for receipt in evidence_document.get("receipts") or []:
        if isinstance(receipt, dict) and isinstance(receipt.get("path"), str):
            paths.add(receipt["path"])
    for entry in evidence_document.get("files") or []:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str) and entry["path"].startswith("evidence/"):
            paths.add(entry["path"])
    return paths


def cited_registered_refs(evidence_refs, registered):
    """The evidence refs (a ``#fragment`` ignored) that name a registered receipt or artifact."""
    return tuple(ref for ref in evidence_refs or []
                 if isinstance(ref, str) and ref.split("#", 1)[0] in registered)


def linux_platform_status(evidence_class, evidence_refs, registered):
    """accepted only for a native/measured winner citing at least one registered receipt or artifact."""
    if evidence_class in ACCEPTED_EVIDENCE_CLASSES:
        return "accepted" if cited_registered_refs(evidence_refs, registered) else "conditional"
    if evidence_class in {"local_integration", "synthetic"}:
        return "conditional"
    return "not_established"


# Platform-status adapter (2026-09-23 peer audit, item 6). Catalog PR #117
# (claude/host-evidence-hardening-20260923) owns the shared scripts/platform_status.py with
# load_context(root) and platform_status(platform_id, winner, context) -> PlatformStatus. Until it
# is on main, these two functions carry the same call shape with the Linux rule only (macos-arm64
# stays "untested"), so tools/sota-convergence/record_verdicts.py switches to the shared module by
# changing its single adapter import line. The shared module is stricter for Linux (it counts only
# registered evidence/ files, not receipts[] entries outside evidence/).
PLATFORM_IDS = ("linux-wsl2-x86_64", "macos-arm64")


class PlatformStatus(NamedTuple):
    status: str
    reason: str
    receipt_refs: tuple


def load_platform_context(root):
    """The registered receipt/artifact paths, read once per run (the adapter's context)."""
    path = Path(root) / EVIDENCE_MANIFEST
    if not path.is_file():
        return frozenset()
    return frozenset(registered_evidence_paths(json.loads(path.read_text(encoding="utf-8"))))


def linux_rule_platform_status(platform_id, winner, context):
    """``winner`` is {component_id, pin, evidence_class, evidence_refs}; ``context`` is
    load_platform_context(root). Linux: linux_platform_status; macos-arm64: untested."""
    if platform_id not in PLATFORM_IDS:
        raise ValueError(f"unknown platform {platform_id!r}")
    if platform_id == "macos-arm64":
        return PlatformStatus("untested", "no host-receipt rule in this adapter", ())
    refs = cited_registered_refs(winner.get("evidence_refs"), context)
    status = linux_platform_status(winner.get("evidence_class"), winner.get("evidence_refs"), context)
    reason = {"accepted": "native/measured winner citing a registered receipt or evidence/ artifact",
              "conditional": "no registered receipt or evidence/ artifact cited, or a local/synthetic class",
              "not_established": "source-review evidence only"}[status]
    return PlatformStatus(status, reason, refs if status == "accepted" else ())


def single_lane_decision_issue(root, path, layer_id):
    """A single-lane (codex_absent) recorded row names a dated decision record that names its layer."""
    if not isinstance(path, str) or not path.strip():
        return "a single-lane recorded verdict needs lanes.single_lane_decision naming a dated decision record"
    if not DATED_NAME.search(path.rsplit("/", 1)[-1]):
        return f"lanes.single_lane_decision {path!r} must be dated (YYYY-MM-DD or YYYYMMDD in its file name)"
    try:
        record = safe_file(Path(root), path)
    except ValueError:
        return f"lanes.single_lane_decision {path!r} is not a confined repository path"
    if not record.is_file():
        return f"lanes.single_lane_decision {path!r} does not exist"
    if layer_id not in record.read_text(encoding="utf-8", errors="replace"):
        return f"lanes.single_lane_decision {path!r} must name the layer id {layer_id!r}"
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
            if outcome["outcome"] == "rejected" and not (
                    isinstance(outcome.get("reasons"), list) and outcome["reasons"]
                    and all(isinstance(reason, str) and reason for reason in outcome["reasons"])):
                return f"the run manifest's rejected {lane} lane of {catalog}/{layer_id} needs its reasons"
    return None


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
                         registered=frozenset()):
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
    grandfathered = is_grandfathered_run(wave)
    sealed_returns = {}
    for lane_name in ("claude", "codex"):
        lane = lanes_field.get(lane_name)
        require(isinstance(lane, dict), str(key) + f".lanes.{lane_name} must be an object")
        require(isinstance(lane.get("run_id"), str), str(key) + f".lanes.{lane_name}.run_id must be text")
        sealed = lane.get("sealed_sha256")
        require(isinstance(sealed, str), str(key) + f".lanes.{lane_name}.sealed_sha256 must be text")
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
    if not grandfathered and any(lanes_field[lane].get("run_id") for lane in LANES):
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
            families.append(sealed_return["model"]["family"])
        require(len(families) == len(set(families)), str(key) + ".lanes must come from two different model families")
        # Survivorship: the row must be accounted for in its wave's run manifest.
        manifest_path = f"{sealed_base}/{RUN_MANIFEST_NAME}"
        manifest_file = safe_file(root, manifest_path)
        require(manifest_file.is_file(), str(key) + f" was recorded in wave {wave} but its run manifest "
                                                  f"{manifest_path} is missing")
        issue = run_manifest_row_issue(json.loads(manifest_file.read_text(encoding="utf-8")), wave,
                                       key[0], key[1], lanes_field)
        require(issue is None, str(key) + ": " + str(issue))

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
        if not grandfathered and platform_status.get("linux-wsl2-x86_64") == "accepted":
            require(linux_platform_status(winner.get("evidence_class"), winner.get("evidence_refs"),
                                          registered) == "accepted",
                    str(key) + ".winner.platform_status.linux-wsl2-x86_64 accepted needs a native_proven or "
                               "measured_comparison winner citing a registered receipt or evidence/ artifact "
                               "(" + EVIDENCE_MANIFEST + ")")

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
        if agreement == "codex_absent":
            issue = single_lane_decision_issue(root, lanes_field.get("single_lane_decision"), key[1])
            require(issue is None, str(key) + ": " + str(issue))
        elif agreement == "same_winner":
            require(all(lanes_field[lane].get("sealed_sha256") for lane in LANES),
                    str(key) + " same_winner verdict needs both lanes sealed")
        else:
            adjudication_path = f"{sealed_base}/adjudication/{lanes_field['claude'].get('run_id')}.json"
            adjudication_file = safe_file(root, adjudication_path)
            require(adjudication_file.is_file(),
                    str(key) + f" disagree verdict needs its sealed adjudication {adjudication_path}")
            issue, result = judge_adjudication(json.loads(adjudication_file.read_text(encoding="utf-8")),
                                               grandfathered=grandfathered)
            require(issue is None, str(key) + f" adjudication {adjudication_path}: {issue}")
            require(result["winner_lane"] is not None,
                    str(key) + f" adjudication {adjudication_path} is a split and cannot record a winner"
                    + (f" ({result['split_reason']})" if result["split_reason"] else ""))
    elif status == "no_selection":
        require(bool(open_gaps), str(key) + " no_selection verdict needs open_gaps")
    if lanes_field.get("single_lane_decision") is not None:
        require(lanes_field.get("agreement") == "codex_absent",
                str(key) + ".lanes.single_lane_decision is only meaningful on a codex_absent row")


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
    registered = (registered_evidence_paths(read(EVIDENCE_MANIFEST))
                  if safe_file(root, EVIDENCE_MANIFEST).is_file() else set())
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
                                  sota_pins=sota_pins_by_layer.get(key[1], {}), registered=registered)
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
