#!/usr/bin/env python3
"""Append-only saturation ledger for landscape sweeps (catalogs/saturation/ledger.json).

Each landscape sweep appends one record: which layers it covered, what was proposed, which
proposals survived both refuters (facts and fit) and which were refuted, and what reopened a
layer. Records form a hash chain: every sweep carries ``prev_sha256``, the sha256 of the
canonical JSON of the record before it (the first one chains to the policy), and the file keeps
``head_sha256`` for the last record. Editing, reordering or deleting a record breaks the chain.

Derived per layer, never stored:

- a completed sweep is **clean** for a layer when that layer's per-vote returns were retained
  (``votes: retained``), nothing survived and nothing reopened it;
- ``saturation_candidate`` means ``policy.K`` consecutive clean completed sweeps, each at least
  ``policy.min_gap_days`` after the last one counted, under an unchanged requirement hash and
  platform-profile hash;
- a stopped sweep neither counts nor resets; a survivor, a reopen entry, a changed requirement or
  platform-profile hash, a sweep without retained votes, or a current ``pin_moved``/``stale``
  receipt flag or archived/renamed/relicensed selection resets the count to 0.

A saturation candidate is only an input to closure. Closing a layer still goes through
``catalogs/landscape/research-state.json`` ``closure_refs``, owned by the landscape owners; this
script never writes that file or anything under ``catalogs/landscape/`` or
``catalogs/sota-convergence/``.

  python3 scripts/saturation_ledger.py --check                  # schema, chain and bindings
  python3 scripts/saturation_ledger.py --check --base origin/main  # also: base ledger is a prefix
  python3 scripts/saturation_ledger.py --report [--json] \\
      [--staleness receipt-staleness.json] [--freshness-manifest manifest-YYYYMMDD.json]
  python3 scripts/saturation_ledger.py --append RESULT.json     # append one sweep (see README)
  python3 scripts/saturation_ledger.py --derive-seed            # print the 2026-09-23 seed results

It makes no network or model calls. See catalogs/saturation/README.md.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = "catalogs/saturation/ledger.json"
RESEARCH_STATE = "catalogs/landscape/research-state.json"
ADOPTION = "adoption/manifest.json"
EVIDENCE = "manifests/evidence.json"
# Paths this script must never write (the landscape owners' files and the verdict data).
PROTECTED_PREFIXES = ("catalogs/landscape/", "catalogs/sota-convergence/", "adoption/", "manifests/")
SCHEMA_VERSION = 1
MANIFEST_SECTION = {"foundation": "foundation", "us-equities": "trading"}
SELECTION_KEY = {"foundation": "components", "trading": "entries"}
STATUSES = ("completed", "stopped")
VOTES = ("retained", "not_retained", "not_returned")
VOTE_VALUES = ("refuted", "not_refuted")
ROLES = ("facts", "fit")
REOPEN_TRIGGERS = ("requirement_changed", "platform_profile_changed", "retained_failure",
                   "missing_capability", "comparison_changed", "pin_moved", "stale_receipt",
                   "selection_changed")
RESETTING_RECEIPT_FLAGS = {"pin_moved": "pin_moved", "stale": "stale_receipt"}
HEX64 = re.compile(r"[0-9a-f]{64}")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
COMPUTED_FIELDS = ("prev_sha256", "manifest_sha256", "usage_sha256", "record_sha256")
COMPUTED_LAYER_FIELDS = ("requirement_sha256", "platform_profiles_sha256", "known", "new")

# The 2026-09-23 seed: every value --derive-seed emits is read from these files.
SEED = {
    "manifest_ref": "catalogs/sota-convergence/manifest-20260923.json",
    "lane": "landscape-sweep-20260923",
    "attempt_ref": "evidence/artifacts/landscape-sweep-20260923-attempts/wf_28d47bbc-1b5.json",
}


class LedgerError(Exception):
    pass


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def safe_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or relative.startswith("/") or "\\" in relative:
        raise LedgerError(f"not a repository-relative path: {relative!r}")
    path = (root / relative).resolve()
    if path != root.resolve() and root.resolve() not in path.parents:
        raise LedgerError(f"path escapes the checkout: {relative!r}")
    return path


def load_json(root: Path, relative: str):
    path = safe_path(root, relative)
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique)
    except (OSError, UnicodeError, ValueError) as error:
        raise LedgerError(f"{relative}: cannot read JSON ({error})") from error


def file_sha256(root: Path, relative: str) -> str | None:
    try:
        return sha256_bytes(safe_path(root, relative).read_bytes())
    except (OSError, LedgerError):
        return None


def norm_repo(repository: str) -> str:
    return repository.strip().rstrip("/").lower()


def genesis_sha256(ledger: dict) -> str:
    return sha256_bytes(canonical({"schema_version": ledger.get("schema_version"), "policy": ledger.get("policy")}))


def record_sha256(record: dict) -> str:
    return sha256_bytes(canonical(record))


def requirement_sha256(row: dict) -> str:
    """The layer's frozen requirement: its research-state next_action and decision_ref."""
    return sha256_bytes(canonical({"next_action": row.get("next_action"), "decision_ref": row.get("decision_ref")}))


def platform_profiles_sha256(adoption: dict) -> str:
    return sha256_bytes(canonical(adoption.get("platform_profiles")))


def resolve_pointer(document, pointer: str):
    """RFC 6901 JSON pointer (``/a/0/b``); raises LedgerError when it does not resolve."""
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise LedgerError(f"JSON pointer must start with '/': {pointer!r}")
    current = document
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if not token.isdigit() or int(token) >= len(current):
                raise LedgerError(f"JSON pointer {pointer!r} does not resolve")
            current = current[int(token)]
        elif isinstance(current, dict) and token in current:
            current = current[token]
        else:
            raise LedgerError(f"JSON pointer {pointer!r} does not resolve")
    return current


def research_rows(root: Path) -> dict:
    state = load_json(root, RESEARCH_STATE)
    rows = {}
    for row in state.get("layers") or []:
        if isinstance(row, dict):
            rows[(row.get("catalog"), row.get("layer_id"))] = row
    return rows


def registered_files(root: Path) -> dict:
    evidence = load_json(root, EVIDENCE)
    return {record["path"]: record for record in evidence.get("files") or []
            if isinstance(record, dict) and isinstance(record.get("path"), str)}


def manifest_layer(manifest: dict, catalog: str, layer_id: str):
    """(section, index, row) of a layer in a SOTA-convergence manifest, or None."""
    section = MANIFEST_SECTION.get(catalog)
    if section is None:
        return None
    for index, row in enumerate(manifest.get(section) or []):
        if isinstance(row, dict) and row.get("layer") == layer_id:
            return section, index, row
    return None


def lane_rows(layer_row: dict, lane: str) -> dict:
    """{normalized repository: (candidate index, candidate)} for the lane's candidate rows."""
    rows = {}
    for index, candidate in enumerate(layer_row.get("candidates") or []):
        if isinstance(candidate, dict) and candidate.get("lane") == lane and isinstance(candidate.get("repository"), str):
            rows[norm_repo(candidate["repository"])] = (index, candidate)
    return rows


def baseline_repositories(section: str, layer_row: dict, lane: str) -> set:
    """Repositories the manifest layer already names outside this lane (selections, named
    alternatives, candidates from other lanes)."""
    repos = set()
    for item in layer_row.get(SELECTION_KEY[section]) or []:
        if isinstance(item, dict) and isinstance(item.get("repository"), str):
            repos.add(norm_repo(item["repository"]))
    for item in layer_row.get("alternatives_keep_but_compare") or []:
        if isinstance(item, dict) and isinstance(item.get("repository"), str):
            repos.add(norm_repo(item["repository"]))
    for item in layer_row.get("candidates") or []:
        if isinstance(item, dict) and item.get("lane") != lane and isinstance(item.get("repository"), str):
            repos.add(norm_repo(item["repository"]))
    return repos


def adjudicated_repos(layer: dict) -> set:
    """Repositories an earlier sweep already put through both refuters for this layer."""
    return {norm_repo(entry["repo"]) for field in ("survived", "refuted") for entry in layer.get(field) or []
            if isinstance(entry, dict) and isinstance(entry.get("repo"), str)}


def split_known(proposed: list, baseline: set, earlier: set) -> tuple[list, list]:
    """known: already named by the manifest layer outside this lane, or adjudicated by an earlier
    sweep for this layer; new: the rest. A proposal a stopped sweep never adjudicated stays new."""
    known = [repo for repo in proposed if norm_repo(repo) in baseline or norm_repo(repo) in earlier]
    new = [repo for repo in proposed if repo not in known]
    return known, new


def entry_votes(entry: dict) -> list:
    """The two votes of a survived/refuted entry as [(label, vote, ref)]."""
    if "lens_votes" in entry:
        return [(f"lens {vote.get('lens')}", vote.get("vote"), vote.get("ref")) for vote in entry.get("lens_votes") or []
                if isinstance(vote, dict)]
    return [(role, (entry.get(role) or {}).get("vote"), (entry.get(role) or {}).get("ref"))
            for role in ROLES if isinstance(entry.get(role), dict)]


def entry_survives(entry: dict) -> bool:
    """The survival rule: survives only when neither vote refutes it."""
    votes = entry_votes(entry)
    return len(votes) == 2 and all(vote == "not_refuted" for _, vote, _ in votes)


def empty_ledger(K: int = 3, min_gap_days: int = 7) -> dict:
    ledger = {"schema_version": SCHEMA_VERSION, "policy": {"K": K, "min_gap_days": min_gap_days}, "sweeps": []}
    ledger["head_sha256"] = genesis_sha256(ledger)
    return ledger


# --------------------------------------------------------------------------- check


class Checker:
    def __init__(self, root: Path):
        self.root = root
        self.errors: list[str] = []
        self._files = None
        self._json_cache: dict = {}

    def error(self, message: str) -> None:
        self.errors.append(message)

    @property
    def files(self) -> dict:
        if self._files is None:
            self._files = registered_files(self.root)
        return self._files

    def document(self, relative: str):
        if relative not in self._json_cache:
            self._json_cache[relative] = load_json(self.root, relative)
        return self._json_cache[relative]

    def registered(self, relative, label: str, expected_sha: str | None = None) -> bool:
        """The file exists, is registered in manifests/evidence.json and matches its registration."""
        if not isinstance(relative, str) or not relative:
            self.error(f"{label}: missing path")
            return False
        record = self.files.get(relative)
        actual = file_sha256(self.root, relative)
        if actual is None:
            self.error(f"{label}: {relative} does not exist")
            return False
        if record is None:
            self.error(f"{label}: {relative} is not registered in {EVIDENCE}")
            return False
        if record.get("sha256") != actual:
            self.error(f"{label}: {relative} differs from its {EVIDENCE} registration")
            return False
        if expected_sha is not None and expected_sha != actual:
            self.error(f"{label}: recorded sha256 of {relative} does not match the file")
            return False
        return True

    def check_ref(self, ref, label: str, expected_vote: str | None):
        """A vote reference: a registered file, optionally with a #/json/pointer to an object
        whose boolean ``refuted`` must agree with the recorded vote."""
        if not isinstance(ref, str) or not ref:
            self.error(f"{label}: missing ref")
            return
        path, _, pointer = ref.partition("#")
        if not self.registered(path, label):
            return
        if not pointer:
            return
        try:
            target = resolve_pointer(self.document(path), pointer)
        except LedgerError as error:
            self.error(f"{label}: {error}")
            return
        if expected_vote is not None:
            refuted = target.get("refuted") if isinstance(target, dict) else None
            if not isinstance(refuted, bool):
                self.error(f"{label}: {ref} has no boolean refuted")
            elif ("refuted" if refuted else "not_refuted") != expected_vote:
                self.error(f"{label}: vote {expected_vote} disagrees with {ref}")

    def check(self, ledger) -> list[str]:
        if not isinstance(ledger, dict):
            return ["ledger: expected an object"]
        extra = set(ledger) - {"schema_version", "policy", "sweeps", "head_sha256"}
        if extra:
            self.error(f"ledger: unknown keys {sorted(extra)}")
        if ledger.get("schema_version") != SCHEMA_VERSION:
            self.error(f"ledger: schema_version must be {SCHEMA_VERSION}")
        policy = ledger.get("policy")
        if not (isinstance(policy, dict) and set(policy) == {"K", "min_gap_days"}
                and all(isinstance(policy[k], int) and not isinstance(policy[k], bool) for k in policy)
                and policy["K"] >= 1 and policy["min_gap_days"] >= 0):
            self.error("ledger: policy must be {K: int >= 1, min_gap_days: int >= 0}")
        sweeps = ledger.get("sweeps")
        if not isinstance(sweeps, list):
            self.error("ledger: sweeps must be a list")
            return self.errors
        previous = genesis_sha256(ledger)
        seen_ids, last_date = set(), None
        proposals_so_far: dict = {}
        for index, sweep in enumerate(sweeps):
            label = f"sweeps[{index}]"
            if not isinstance(sweep, dict):
                self.error(f"{label}: expected an object")
                previous = None
                continue
            if sweep.get("prev_sha256") != previous:
                self.error(f"{label}: prev_sha256 breaks the hash chain (an earlier record was edited, "
                           "reordered or removed)")
            previous = record_sha256(sweep)
            sweep_id = sweep.get("sweep_id")
            if not isinstance(sweep_id, str) or not sweep_id:
                self.error(f"{label}: sweep_id required")
            elif sweep_id in seen_ids:
                self.error(f"{label}: duplicate sweep_id {sweep_id}")
            seen_ids.add(sweep_id)
            sweep_date = sweep.get("date")
            if not isinstance(sweep_date, str) or not DATE.fullmatch(sweep_date):
                self.error(f"{label}: date must be YYYY-MM-DD")
            else:
                if last_date is not None and sweep_date < last_date:
                    self.error(f"{label}: dates must not go backwards")
                last_date = sweep_date
            self.check_sweep(sweep, label, proposals_so_far)
        if ledger.get("head_sha256") != previous:
            self.error("ledger: head_sha256 does not match the last record (a record was removed or edited)")
        return self.errors

    def check_sweep(self, sweep: dict, label: str, proposals_so_far: dict) -> None:
        allowed = {"sweep_id", "date", "workflow_run", "status", "manifest_ref", "manifest_sha256", "lane",
                   "prompts_sha256", "usage_ref", "usage_sha256", "lower_bound_usage", "record_ref",
                   "lane_calls", "not_retained", "notes", "prev_sha256", "layers"}
        extra = set(sweep) - allowed
        if extra:
            self.error(f"{label}: unknown keys {sorted(extra)}")
        status = sweep.get("status")
        if status not in STATUSES:
            self.error(f"{label}: status must be one of {STATUSES}")
        if not isinstance(sweep.get("workflow_run"), str) or not sweep.get("workflow_run"):
            self.error(f"{label}: workflow_run required")
        not_retained = sweep.get("not_retained") or []
        if not isinstance(not_retained, list) or not all(isinstance(item, str) for item in not_retained):
            self.error(f"{label}: not_retained must be a list of field names")
            not_retained = []
        prompts = sweep.get("prompts_sha256")
        if prompts is None:
            if "prompts_sha256" not in not_retained:
                self.error(f"{label}: prompts_sha256 is null but not listed in not_retained")
        elif not (isinstance(prompts, str) and HEX64.fullmatch(prompts)):
            self.error(f"{label}: prompts_sha256 must be 64 lowercase hex or null")
        # Usage: a completed sweep has complete registered usage; a stopped one is a lower bound.
        lower = sweep.get("lower_bound_usage")
        if not isinstance(lower, bool):
            self.error(f"{label}: lower_bound_usage must be a boolean")
        if self.registered(sweep.get("usage_ref"), f"{label}.usage_ref", sweep.get("usage_sha256")):
            usage = self.document(sweep["usage_ref"])
            usage_status = ((usage.get("child_usage") or {}).get("status") if isinstance(usage, dict) else None)
            if status == "completed":
                if lower is not False:
                    self.error(f"{label}: a completed sweep's usage must not be a lower bound")
                if usage_status != "complete":
                    self.error(f"{label}: a completed sweep needs complete usage (child_usage.status is {usage_status!r})")
        if not isinstance(sweep.get("usage_sha256"), str):
            self.error(f"{label}: usage_sha256 required")
        if status == "stopped" and lower is not True:
            self.error(f"{label}: a stopped sweep's usage must be marked lower_bound_usage")
        if sweep.get("record_ref") is not None:
            self.registered(sweep.get("record_ref"), f"{label}.record_ref")
        manifest = None
        manifest_ref = sweep.get("manifest_ref")
        if manifest_ref is not None:
            if not isinstance(sweep.get("manifest_sha256"), str):
                self.error(f"{label}: manifest_sha256 required with manifest_ref")
            elif self.registered(manifest_ref, f"{label}.manifest_ref", sweep["manifest_sha256"]):
                manifest = self.document(manifest_ref)
        elif status == "completed":
            self.error(f"{label}: a completed sweep needs a manifest_ref")
        lane = sweep.get("lane")
        if not isinstance(lane, str) or not lane:
            self.error(f"{label}: lane required")
        layers = sweep.get("layers")
        if not isinstance(layers, list):
            self.error(f"{label}: layers must be a list")
            return
        seen = set()
        for position, layer in enumerate(layers):
            layer_label = f"{label}.layers[{position}]"
            if not isinstance(layer, dict):
                self.error(f"{layer_label}: expected an object")
                continue
            key = (layer.get("catalog"), layer.get("layer_id"))
            if key in seen:
                self.error(f"{layer_label}: duplicate layer {key}")
            seen.add(key)
            self.check_layer(sweep, layer, layer_label, manifest, lane, proposals_so_far.get(key, set()))
            proposals_so_far.setdefault(key, set()).update(adjudicated_repos(layer))

    def check_layer(self, sweep, layer, label, manifest, lane, earlier) -> None:
        allowed = {"catalog", "layer_id", "requirement_sha256", "platform_profiles_sha256", "votes", "votes_note",
                   "calls", "proposed", "known", "new", "survived", "refuted", "reopen"}
        extra = set(layer) - allowed
        if extra:
            self.error(f"{label}: unknown keys {sorted(extra)}")
        catalog, layer_id = layer.get("catalog"), layer.get("layer_id")
        if catalog not in MANIFEST_SECTION or not isinstance(layer_id, str):
            self.error(f"{label}: catalog must be one of {sorted(MANIFEST_SECTION)} with a layer_id")
            return
        for field in ("requirement_sha256", "platform_profiles_sha256"):
            if not (isinstance(layer.get(field), str) and HEX64.fullmatch(layer[field])):
                self.error(f"{label}: {field} must be 64 lowercase hex")
        votes = layer.get("votes")
        if votes not in VOTES:
            self.error(f"{label}: votes must be one of {VOTES}")
        if votes != "retained" and not (isinstance(layer.get("votes_note"), str) and layer["votes_note"].strip()):
            self.error(f"{label}: votes {votes} needs a votes_note saying what was not retained")
        calls = layer.get("calls")
        if calls is not None and not (isinstance(calls, dict) and all(
                isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in calls.values())):
            self.error(f"{label}: calls must be null or a map of non-negative integers")
        lists = {}
        for field in ("proposed", "known", "new", "survived", "refuted", "reopen"):
            value = layer.get(field)
            if not isinstance(value, list):
                self.error(f"{label}: {field} must be a list")
                value = []
            lists[field] = value
        proposed = lists["proposed"]
        if not all(isinstance(repo, str) for repo in proposed) or len({norm_repo(r) for r in proposed if isinstance(r, str)}) != len(proposed):
            self.error(f"{label}: proposed must be unique repository strings")
            return
        # known/new partition proposed, recomputed from the manifest baseline and earlier sweeps.
        located = manifest_layer(manifest, catalog, layer_id) if manifest is not None else None
        if manifest is not None and located is None:
            self.error(f"{label}: layer {catalog}/{layer_id} is not in {sweep.get('manifest_ref')}")
        baseline = baseline_repositories(located[0], located[2], lane) if located else set()
        known, new = split_known(proposed, baseline, earlier)
        if lists["known"] != known or lists["new"] != new:
            self.error(f"{label}: known/new do not match the manifest baseline and earlier adjudications "
                       f"(expected known={known}, new={new})")
        # Outcomes: both votes required, survival recomputed from them.
        adjudicated = {}
        for field, survives in (("survived", True), ("refuted", False)):
            for position, entry in enumerate(lists[field]):
                entry_label = f"{label}.{field}[{position}]"
                if not isinstance(entry, dict) or not isinstance(entry.get("repo"), str):
                    self.error(f"{entry_label}: expected {{repo, ...}}")
                    continue
                repo = norm_repo(entry["repo"])
                if repo in adjudicated:
                    self.error(f"{entry_label}: {entry['repo']} adjudicated twice")
                adjudicated[repo] = survives
                if repo not in {norm_repo(r) for r in proposed}:
                    self.error(f"{entry_label}: {entry['repo']} was not proposed")
                self.check_votes(layer, entry, entry_label, located, lane, sweep)
                if entry_survives(entry) != survives:
                    self.error(f"{entry_label}: listed as {field} but its votes give "
                               f"{'survived' if entry_survives(entry) else 'refuted'}")
                if survives:
                    self.check_survivor(entry, entry_label, layer_id, located, lane)
        if sweep.get("status") == "completed":
            missing = [repo for repo in proposed if norm_repo(repo) not in adjudicated]
            if missing:
                self.error(f"{label}: a completed sweep must adjudicate every proposal (missing {missing})")
            if located is not None and isinstance(lane, str):
                rows = lane_rows(located[2], lane)
                if set(rows) != {norm_repo(repo) for repo in proposed}:
                    self.error(f"{label}: proposed does not equal the manifest's {lane} rows for this layer")
                for repo, (index, candidate) in rows.items():
                    recorded = (candidate.get("adversarial_verification") or {}).get("survives")
                    if repo in adjudicated and recorded is not adjudicated[repo]:
                        self.error(f"{label}: {candidate['repository']} survival disagrees with the manifest")
        for position, entry in enumerate(lists["reopen"]):
            if not (isinstance(entry, dict) and entry.get("trigger") in REOPEN_TRIGGERS
                    and isinstance(entry.get("ref"), str) and entry["ref"].strip()):
                self.error(f"{label}.reopen[{position}]: needs a trigger in {REOPEN_TRIGGERS} and a ref")

    def check_votes(self, layer, entry, label, located, lane, sweep) -> None:
        votes = layer.get("votes")
        if votes == "retained":
            if "lens_votes" in entry:
                self.error(f"{label}: a layer with retained votes names facts and fit, not lens_votes")
            for role in ROLES:
                vote = entry.get(role)
                if not (isinstance(vote, dict) and vote.get("vote") in VOTE_VALUES):
                    self.error(f"{label}: {role} vote required ({'/'.join(VOTE_VALUES)} with a ref)")
                    continue
                self.check_ref(vote.get("ref"), f"{label}.{role}", vote.get("vote"))
            return
        lens_votes = entry.get("lens_votes")
        if not (isinstance(lens_votes, list) and len(lens_votes) == 2
                and sorted(v.get("lens") for v in lens_votes if isinstance(v, dict)) == [0, 1]
                and all(isinstance(v, dict) and v.get("vote") in VOTE_VALUES for v in lens_votes)):
            self.error(f"{label}: both lens votes (0 and 1) are required")
            return
        for vote in lens_votes:
            ref = vote.get("ref")
            self.check_ref(ref, f"{label}.lens {vote.get('lens')}", vote.get("vote"))
            if isinstance(ref, str) and ref.partition("#")[0] != sweep.get("manifest_ref"):
                self.error(f"{label}: lens votes must cite the sweep's manifest_ref")

    def check_survivor(self, entry, label, layer_id, located, lane) -> None:
        if located is None:
            self.error(f"{label}: a survivor needs a manifest layer to bind to")
        else:
            rows = lane_rows(located[2], lane)
            match = rows.get(norm_repo(entry["repo"]))
            if match is None:
                self.error(f"{label}: survivor {entry['repo']} has no {lane} row in the manifest layer")
            elif (match[1].get("adversarial_verification") or {}).get("survives") is not True:
                self.error(f"{label}: survivor {entry['repo']} is not a surviving manifest row")
        source_review = entry.get("source_review")
        if self.registered(source_review, f"{label}.source_review"):
            review = self.document(source_review)
            if not isinstance(review, dict) or norm_repo(str(review.get("repository", ""))) != norm_repo(entry["repo"]):
                self.error(f"{label}: {source_review} reviews a different repository")
            elif isinstance(review.get("layers"), list) and layer_id not in review["layers"]:
                self.error(f"{label}: {source_review} does not name layer {layer_id}")


def check_ledger(root: Path, ledger) -> list[str]:
    try:
        return Checker(root).check(ledger)
    except LedgerError as error:
        return [str(error)]


def check_append_only(root: Path, ledger: dict, base: str) -> list[str]:
    """The ledger at ``base`` must be a prefix of this one (same policy, same records)."""
    result = subprocess.run(["git", "-C", str(root), "show", f"{base}:{LEDGER}"],
                            capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return []  # no ledger at the base yet
    try:
        old = json.loads(result.stdout, object_pairs_hook=_unique)
    except ValueError as error:
        return [f"{base}:{LEDGER}: unreadable ({error})"]
    errors = []
    if old.get("policy") != ledger.get("policy") or old.get("schema_version") != ledger.get("schema_version"):
        errors.append(f"append-only: policy or schema_version changed since {base}")
    old_sweeps, new_sweeps = old.get("sweeps") or [], ledger.get("sweeps") or []
    if len(new_sweeps) < len(old_sweeps) or any(
            canonical(a) != canonical(b) for a, b in zip(old_sweeps, new_sweeps)):
        errors.append(f"append-only: the records at {base} are not an unchanged prefix of this ledger")
    return errors


# --------------------------------------------------------------------------- derive


def derive(ledger: dict, current: dict | None = None) -> dict:
    """Per-layer consecutive-clean count. ``current`` optionally carries today's inputs:
    {"requirements": {(catalog, layer_id): sha}, "platform_profiles_sha256": sha,
     "triggers": {(catalog, layer_id): [{"trigger", "ref"}]}}."""
    policy = ledger.get("policy") or {}
    K, gap = policy.get("K", 3), policy.get("min_gap_days", 7)
    state: dict = {}
    for sweep in ledger.get("sweeps") or []:
        if sweep.get("status") != "completed":
            continue  # a stopped sweep neither counts nor resets
        sweep_date = date.fromisoformat(sweep["date"])
        for layer in sweep.get("layers") or []:
            key = (layer.get("catalog"), layer.get("layer_id"))
            entry = state.setdefault(key, {"count": 0, "last_counted": None, "requirement_sha256": None,
                                           "platform_profiles_sha256": None, "counted_sweeps": [],
                                           "reset": [], "last_sweep": None})
            reasons = []
            if entry["requirement_sha256"] not in (None, layer.get("requirement_sha256")):
                reasons.append({"trigger": "requirement_changed", "ref": sweep["sweep_id"]})
            if entry["platform_profiles_sha256"] not in (None, layer.get("platform_profiles_sha256")):
                reasons.append({"trigger": "platform_profile_changed", "ref": sweep["sweep_id"]})
            entry["requirement_sha256"] = layer.get("requirement_sha256")
            entry["platform_profiles_sha256"] = layer.get("platform_profiles_sha256")
            entry["last_sweep"] = sweep["sweep_id"]
            if reasons:
                entry.update(count=0, last_counted=None, counted_sweeps=[])
            not_clean = [dict(item) for item in layer.get("reopen") or []]
            not_clean += [{"trigger": "survivor", "ref": f"{sweep['sweep_id']}:{item.get('repo')}"}
                          for item in layer.get("survived") or []]
            if layer.get("votes") != "retained":
                not_clean.append({"trigger": f"votes_{layer.get('votes')}", "ref": sweep["sweep_id"]})
            if not_clean:
                entry.update(count=0, last_counted=None, counted_sweeps=[])
                entry["reset"] = reasons + not_clean
                continue
            if reasons:
                entry["reset"] = reasons
            if entry["last_counted"] is None or (sweep_date - entry["last_counted"]).days >= gap:
                entry["count"] += 1
                entry["last_counted"] = sweep_date
                entry["counted_sweeps"].append(sweep["sweep_id"])
    current = current or {}
    for key in set(current.get("requirements") or {}) | set(current.get("triggers") or {}):
        state.setdefault(key, {"count": 0, "last_counted": None, "requirement_sha256": None,
                               "platform_profiles_sha256": None, "counted_sweeps": [], "reset": [],
                               "last_sweep": None})
    for key, entry in state.items():
        reasons = []
        wanted = (current.get("requirements") or {}).get(key)
        if wanted is not None and entry["requirement_sha256"] not in (None, wanted):
            reasons.append({"trigger": "requirement_changed", "ref": RESEARCH_STATE})
        profiles = current.get("platform_profiles_sha256")
        if profiles is not None and entry["platform_profiles_sha256"] not in (None, profiles):
            reasons.append({"trigger": "platform_profile_changed", "ref": f"{ADOPTION}#/platform_profiles"})
        reasons += list((current.get("triggers") or {}).get(key) or [])
        if reasons:
            entry.update(count=0, last_counted=None, counted_sweeps=[])
            entry["reset"] = entry["reset"] + reasons if entry["reset"] else reasons
            entry["current_triggers"] = reasons
        entry["saturation_candidate"] = entry["count"] >= K
        entry["last_counted"] = entry["last_counted"].isoformat() if entry["last_counted"] else None
    return state


# --------------------------------------------------------------------------- report


def latest_manifest_ref(ledger: dict) -> str | None:
    for sweep in reversed(ledger.get("sweeps") or []):
        if sweep.get("status") == "completed" and sweep.get("manifest_ref"):
            return sweep["manifest_ref"]
    return None


def component_layers(manifest: dict) -> dict:
    """{component id: [(catalog, layer_id)]} and {component id: selection row} from a manifest."""
    catalog_of = {section: catalog for catalog, section in MANIFEST_SECTION.items()}
    mapping: dict = {}
    for section, key in SELECTION_KEY.items():
        for row in manifest.get(section) or []:
            if not isinstance(row, dict):
                continue
            for item in row.get(key) or []:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    mapping.setdefault(item["id"], []).append(((catalog_of[section], row.get("layer")), item))
    return mapping


def external_triggers(baseline: dict | None, staleness: dict | None, freshness: dict | None) -> tuple[dict, list]:
    triggers: dict = {}
    notes = []
    mapping = component_layers(baseline) if baseline else {}
    if staleness is not None:
        for row in staleness.get("rows") or []:
            for flag in row.get("flags") or []:
                trigger = RESETTING_RECEIPT_FLAGS.get(flag)
                if trigger is None:
                    continue
                layers = mapping.get(row.get("component_id")) or []
                if not layers:
                    notes.append(f"receipt flag {flag} on {row.get('component_id')} maps to no layer")
                for key, _ in layers:
                    triggers.setdefault(key, []).append(
                        {"trigger": trigger, "ref": f"receipt_staleness:{row.get('platform_id')}/{row.get('component_id')}"})
    if freshness is not None and baseline is not None:
        fresh = component_layers(freshness)
        for component_id, placements in fresh.items():
            before = {key: item for key, item in mapping.get(component_id, [])}
            for key, item in placements:
                upstream = item.get("upstream") or {}
                old = (before.get(key) or {}).get("upstream") or {}
                changes = []  # only a change since the baseline manifest, not a standing state
                if upstream.get("archived") is True and old.get("archived") is not True:
                    changes.append("archived")
                if upstream.get("renamed_to") and upstream.get("renamed_to") != old.get("renamed_to"):
                    changes.append(f"renamed to {upstream['renamed_to']}")
                if key in before and upstream.get("license") != old.get("license") and upstream.get("license") is not None:
                    changes.append(f"license {old.get('license')} -> {upstream.get('license')}")
                if changes:
                    triggers.setdefault(key, []).append(
                        {"trigger": "selection_changed", "ref": f"catalog-freshness:{component_id} ({', '.join(changes)})"})
    return triggers, notes


def build_report(root: Path, ledger: dict, staleness=None, freshness=None) -> dict:
    rows = research_rows(root)
    adoption = load_json(root, ADOPTION)
    manifest_ref = latest_manifest_ref(ledger)
    baseline = load_json(root, manifest_ref) if manifest_ref else None
    triggers, notes = external_triggers(baseline, staleness, freshness)
    current = {"requirements": {key: requirement_sha256(row) for key, row in rows.items()},
               "platform_profiles_sha256": platform_profiles_sha256(adoption), "triggers": triggers}
    state = derive(ledger, current)
    layers = []
    for key in rows:
        entry = state.get(key) or {"count": 0, "saturation_candidate": False, "reset": [], "last_sweep": None,
                                   "last_counted": None}
        layers.append({
            "catalog": key[0], "layer_id": key[1], "research_status": rows[key].get("status"),
            "clean_count": entry["count"], "saturation_candidate": entry["saturation_candidate"],
            "due": not entry["saturation_candidate"], "last_sweep": entry.get("last_sweep"),
            "last_counted": entry.get("last_counted"), "reset": entry.get("reset") or [],
            "current_triggers": entry.get("current_triggers") or [],
        })
    completed = [s for s in ledger.get("sweeps") or [] if s.get("status") == "completed"]
    return {
        "policy": ledger.get("policy"),
        "sweeps": len(ledger.get("sweeps") or []),
        "completed_sweeps": len(completed),
        "last_completed": {"sweep_id": completed[-1]["sweep_id"], "date": completed[-1]["date"]} if completed else None,
        "inputs": {"staleness": staleness is not None, "freshness": freshness is not None,
                   "baseline_manifest": manifest_ref},
        "notes": notes,
        "due": [f"{l['catalog']}/{l['layer_id']}" for l in layers if l["due"]],
        "saturation_candidates": [f"{l['catalog']}/{l['layer_id']}" for l in layers if l["saturation_candidate"]],
        "current_reopen_triggers": {f"{l['catalog']}/{l['layer_id']}": l["current_triggers"]
                                    for l in layers if l["current_triggers"]},
        "layers": layers,
    }


def render_markdown(report: dict) -> str:
    policy = report["policy"] or {}
    last = report["last_completed"]
    lines = [
        "## Saturation tracking",
        "",
        f"Policy: a layer is a saturation candidate after {policy.get('K')} consecutive clean completed sweeps "
        f"at least {policy.get('min_gap_days')} days apart. A candidate is only an input to closure; closing a "
        "layer goes through `catalogs/landscape/research-state.json` `closure_refs` (landscape owners).",
        "",
        f"Ledger: {report['sweeps']} sweep record(s), {report['completed_sweeps']} completed; last completed: "
        + (f"`{last['sweep_id']}` ({last['date']})" if last else "none") + ".",
        f"Inputs: receipt staleness {'read' if report['inputs']['staleness'] else 'not available'}; "
        f"catalog-freshness manifest {'read' if report['inputs']['freshness'] else 'not available'}.",
        "",
        f"**Due layers: {len(report['due'])}** · saturation candidates: {len(report['saturation_candidates'])} · "
        f"layers with current reopen triggers: {len(report['current_reopen_triggers'])}",
        "",
        "A sweep is started by a person in an agent-lab coordinator session (recipes/saturation-sweep.md); "
        "this report makes no model calls.",
        "",
        "| Layer | Research status | Clean count | Candidate | Last sweep | Reset / reopen |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for layer in report["layers"]:
        reasons = "; ".join(f"{r.get('trigger')} ({r.get('ref')})" for r in (layer["reset"] or [])[:4]) or "-"
        if len(layer["reset"] or []) > 4:
            reasons += f"; +{len(layer['reset']) - 4} more"
        lines.append(f"| {layer['catalog']}/{layer['layer_id']} | {layer['research_status']} | {layer['clean_count']} | "
                     f"{'yes' if layer['saturation_candidate'] else 'no'} | {layer['last_sweep'] or '-'} | {reasons} |")
    for note in report["notes"]:
        lines.append(f"\nNote: {note}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- append


def complete_result(root: Path, ledger: dict, result: dict) -> dict:
    """Turn a sweep result into a ledger record: add the computed hashes and known/new."""
    if not isinstance(result, dict):
        raise LedgerError("result must be a JSON object")
    for field in COMPUTED_FIELDS:
        if field in result:
            raise LedgerError(f"result must not set computed field {field}")
    record = copy.deepcopy(result)
    rows = research_rows(root)
    profiles = platform_profiles_sha256(load_json(root, ADOPTION))
    if record.get("manifest_ref") is not None:
        record["manifest_sha256"] = file_sha256(root, record["manifest_ref"])
        if record["manifest_sha256"] is None:
            raise LedgerError(f"manifest_ref {record['manifest_ref']} does not exist")
    usage_sha = file_sha256(root, record.get("usage_ref")) if isinstance(record.get("usage_ref"), str) else None
    if usage_sha is None:
        raise LedgerError("usage_ref must name an existing, registered usage file")
    record["usage_sha256"] = usage_sha
    manifest = load_json(root, record["manifest_ref"]) if record.get("manifest_ref") else None
    earlier: dict = {}
    for sweep in ledger.get("sweeps") or []:
        for layer in sweep.get("layers") or []:
            earlier.setdefault((layer.get("catalog"), layer.get("layer_id")), set()).update(adjudicated_repos(layer))
    layers = []
    for layer in record.get("layers") or []:
        for field in COMPUTED_LAYER_FIELDS:
            if field in layer:
                raise LedgerError(f"result layer must not set computed field {field}")
        key = (layer.get("catalog"), layer.get("layer_id"))
        if key not in rows:
            raise LedgerError(f"{key[0]}/{key[1]} is not a layer in {RESEARCH_STATE}")
        located = manifest_layer(manifest, *key) if manifest is not None else None
        baseline = baseline_repositories(located[0], located[2], record.get("lane")) if located else set()
        known, new = split_known(layer.get("proposed") or [], baseline, earlier.get(key, set()))
        ordered = {"catalog": key[0], "layer_id": key[1],
                   "requirement_sha256": requirement_sha256(rows[key]),
                   "platform_profiles_sha256": profiles}
        for field in ("votes", "votes_note", "calls", "proposed"):
            if field in layer:
                ordered[field] = layer[field]
        ordered["known"], ordered["new"] = known, new
        for field in ("survived", "refuted", "reopen"):
            ordered[field] = layer.get(field, [])
        extra = set(layer) - set(ordered)
        if extra:
            raise LedgerError(f"result layer has unknown keys {sorted(extra)}")
        layers.append(ordered)
    record["layers"] = layers
    record["prev_sha256"] = ledger.get("head_sha256")
    order = ["sweep_id", "date", "workflow_run", "status", "manifest_ref", "manifest_sha256", "lane",
             "prompts_sha256", "usage_ref", "usage_sha256", "lower_bound_usage", "record_ref", "lane_calls",
             "not_retained", "notes", "prev_sha256", "layers"]
    return {field: record[field] for field in order if field in record} | {
        field: value for field, value in record.items() if field not in order}


def append(root: Path, ledger: dict, result: dict) -> dict:
    """Return a new ledger with ``result`` appended; refuses a broken existing ledger, a reused
    sweep_id or a record that does not check."""
    errors = check_ledger(root, ledger)
    if errors:
        raise LedgerError("the existing ledger does not check; refusing to append:\n  " + "\n  ".join(errors))
    if any(sweep.get("sweep_id") == result.get("sweep_id") for sweep in ledger.get("sweeps") or []):
        raise LedgerError(f"sweep_id {result.get('sweep_id')} is already recorded; the ledger is append-only")
    record = complete_result(root, ledger, result)
    updated = copy.deepcopy(ledger)
    updated["sweeps"].append(record)
    updated["head_sha256"] = record_sha256(record)
    errors = check_ledger(root, updated)
    if errors:
        raise LedgerError("the new record does not check:\n  " + "\n  ".join(errors))
    return updated


def dump(ledger: dict) -> str:
    return json.dumps(ledger, indent=1, ensure_ascii=False) + "\n"


def write_ledger(root: Path, path: Path, ledger: dict) -> None:
    resolved = path.resolve()
    for prefix in PROTECTED_PREFIXES:
        protected = (root / prefix).resolve()
        if resolved == protected or protected in resolved.parents:
            raise LedgerError(f"refusing to write {path}: {prefix} is not owned by the saturation ledger")
    if resolved.name != "ledger.json":
        raise LedgerError(f"refusing to write {path}: the ledger file is named ledger.json")
    mode = resolved.stat().st_mode & 0o777 if resolved.exists() else 0o644
    handle, temporary = tempfile.mkstemp(dir=resolved.parent, prefix=".ledger-", suffix=".json")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(dump(ledger))
        os.chmod(temporary, mode)
        os.replace(temporary, resolved)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


# --------------------------------------------------------------------------- seed


def derive_seed(root: Path) -> list[dict]:
    """The two 2026-09-23 sweep results, read from the lane manifest, the retained attempt record
    and the child-usage outputs. The raw lane returns (per-vote returns and prompts) were not
    retained, so every layer is ``votes: not_retained`` (completed run) or ``not_returned``
    (stopped run, no refuter returned) and none counts as clean."""
    manifest_ref, lane, attempt_ref = SEED["manifest_ref"], SEED["lane"], SEED["attempt_ref"]
    manifest = load_json(root, manifest_ref)
    attempt = load_json(root, attempt_ref)
    rows = research_rows(root)
    catalog_of = {layer_id: catalog for catalog, layer_id in rows}
    attempts_dir = attempt_ref.rsplit("/", 1)[0]
    completed_run = attempt["superseded_by"]
    completed_usage_ref = f"{attempts_dir}/child-usage-{completed_run}.json"
    completed_usage = load_json(root, completed_usage_ref)
    usage_status = completed_usage["child_usage"]["status"]
    discovered = [child["label"].split(":", 1)[1] for child in completed_usage["child_usage"]["children"]
                  if child.get("label", "").startswith("discover:")]
    review_dir = f"evidence/artifacts/{lane}"
    reviews = {}
    for path in sorted(safe_path(root, review_dir).glob("*.json")):
        relative = f"{review_dir}/{path.name}"
        reviews[norm_repo(load_json(root, relative)["repository"])] = relative

    stopped = {
        "sweep_id": attempt["id"],
        "date": manifest["checked_at"],
        "workflow_run": attempt["workflow_run"],
        "status": attempt["status"],
        "manifest_ref": manifest_ref,
        "lane": lane,
        "prompts_sha256": None,
        "usage_ref": attempt["provider_usage"]["retained_output"],
        "lower_bound_usage": attempt["provider_usage"]["lower_bound"],
        "record_ref": attempt_ref,
        "not_retained": ["prompts_sha256", "lane_returns"],
        "notes": [attempt["stop_reason"], *attempt.get("limitations", [])],
        "layers": [],
    }
    for layer in attempt["layers"]:
        stopped["layers"].append({
            "catalog": catalog_of[layer["layer_id"]], "layer_id": layer["layer_id"],
            "votes": "not_returned",
            "votes_note": f"stopped after {attempt['discovery_returns']} discovery returns and "
                          f"{attempt['refuter_returns']} refuter returns ({attempt_ref})",
            "calls": layer["calls"],
            "proposed": [item["repository"] for item in layer["repositories"]],
            "survived": [], "refuted": [], "reopen": [],
        })

    completed = {
        "sweep_id": lane,
        "date": manifest["checked_at"],
        "workflow_run": completed_run,
        "status": "completed" if usage_status == "complete" else "stopped",
        "manifest_ref": manifest_ref,
        "lane": lane,
        "prompts_sha256": None,
        "usage_ref": completed_usage_ref,
        "lower_bound_usage": usage_status != "complete",
        "lane_calls": manifest["lane_calls"][lane],
        "not_retained": ["prompts_sha256", "lane_returns", "per_layer_calls"],
        "notes": [f"Lane limits: {manifest_ref}#/lane_limits/{lane}.",
                  "Per-vote returns were not retained; the manifest keeps each vote's refuted flag and a "
                  "400-character reasoning excerpt by lens index, without naming which lens was the facts "
                  "or fit refuter, so no layer of this sweep counts as clean."],
        "layers": [],
    }
    for layer_id in discovered:
        catalog = catalog_of[layer_id]
        section, layer_index, layer_row = manifest_layer(manifest, catalog, layer_id)
        entries = {"survived": [], "refuted": []}
        proposed = []
        for repo, (index, candidate) in lane_rows(layer_row, lane).items():
            proposed.append(candidate["repository"])
            base = f"{manifest_ref}#/{section}/{layer_index}/candidates/{index}/adversarial_verification/votes"
            entry = {"repo": candidate["repository"], "lens_votes": [
                {"lens": vote["lens"], "vote": "refuted" if vote["refuted"] else "not_refuted", "ref": f"{base}/{k}"}
                for k, vote in enumerate(candidate["adversarial_verification"]["votes"])]}
            if entry_survives(entry):
                entries["survived"].append({"repo": entry["repo"], "source_review": reviews.get(repo),
                                            "lens_votes": entry["lens_votes"]})
            else:
                entries["refuted"].append(entry)
        completed["layers"].append({
            "catalog": catalog, "layer_id": layer_id, "votes": "not_retained",
            "votes_note": ("per-vote returns not retained; votes are the manifest's per-lens refuted flags"
                           if proposed else
                           "discovery return not retained; the manifest has no lane rows for this layer, so an "
                           "empty proposal set cannot be verified"),
            "calls": None, "proposed": proposed,
            "survived": entries["survived"], "refuted": entries["refuted"], "reopen": [],
        })
    return [stopped, completed]


# --------------------------------------------------------------------------- main


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--ledger", type=Path, help=f"ledger file (default: <root>/{LEDGER})")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--report", action="store_true")
    mode.add_argument("--append", type=Path, metavar="RESULT.json")
    mode.add_argument("--derive-seed", action="store_true")
    parser.add_argument("--base", help="with --check: the ledger at this git ref must be an unchanged prefix")
    parser.add_argument("--json", action="store_true", help="with --report: print JSON")
    parser.add_argument("--staleness", type=Path, help="with --report: scripts/receipt_staleness.py --json output")
    parser.add_argument("--freshness-manifest", type=Path,
                        help="with --report: the rebuilt manifest from a catalog-freshness artifact")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    ledger_path = args.ledger or root / LEDGER
    try:
        if args.derive_seed:
            print(json.dumps(derive_seed(root), indent=1, ensure_ascii=False))
            return 0
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"), object_pairs_hook=_unique)
        if args.check:
            errors = check_ledger(root, ledger)
            if args.base:
                errors += check_append_only(root, ledger, args.base)
            for error in errors:
                print(f"error: {error}", file=sys.stderr)
            if not errors:
                print(f"ok: {len(ledger['sweeps'])} sweep record(s), chain intact, bindings verified")
            return 1 if errors else 0
        if args.report:
            staleness = json.loads(args.staleness.read_text(encoding="utf-8")) if args.staleness else None
            freshness = (json.loads(args.freshness_manifest.read_text(encoding="utf-8"))
                         if args.freshness_manifest else None)
            report = build_report(root, ledger, staleness, freshness)
            print(json.dumps(report, indent=1) if args.json else render_markdown(report), end="" if not args.json else "\n")
            return 0
        result = json.loads(args.append.read_text(encoding="utf-8"), object_pairs_hook=_unique)
        write_ledger(root, ledger_path, append(root, ledger, result))
        print(f"appended {result.get('sweep_id')} to {ledger_path}")
        return 0
    except (LedgerError, OSError, ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
