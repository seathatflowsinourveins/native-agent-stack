#!/usr/bin/env python3
"""Rebuild compact G5 metadata from immutable release-asset captures.

References: native-agent-stack@3e5, scripts/catalog_decisions.py (safe_file,
unique_json), landscape-sweep/sweep_common.py (canon/json_text), Python 3.12
stdlib tarfile stream mode, and upstream Zstandard's supported zstd -dc CLI.
This checks artifact integrity and declared coverage; it runs no acceptance
tests, executes no producer/parser code, and performs no network request.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools/sota-convergence/landscape-sweep"))
from catalog_decisions import InvalidDecisionIndex, identity as github_identity, safe_file, unique_json
from sweep_common import canon, json_text

SCHEMA = Path(__file__).parent / "schemas/compact-decision.json"
COVERAGE_SCHEMA = SCHEMA.with_name("compact-coverage.json")
START_CLOSURE_PROFILE = "start-closure/1"
START_ROW_SCHEMA = SCHEMA.with_name("compact-decision-start-closure-1.json")
START_COVERAGE_SCHEMA = SCHEMA.with_name("compact-coverage-start-closure-1.json")
ACTION_CLASSES = {"ADOPT-NOW", "TRIAL"}
PIN_REASONS = {"no-body", "no-match", "not-a-repository-file"}
LOCATOR_REASONS = {"unsupported-transport", "unestablished-pinned-locator", "source-disagreement"}
OMISSION_FOLLOW_UPS = {"complete-typed-list-populations-not-frozen": "G5-F1",
                     "source-primary-qualification-unresolved": "G5-F2", "missing-list-capture": "G5-F1"}
POPULATION_FACTS = ("source_repository", "pin", "path", "capture_sha256", "archive_member", "parser")
COUNT_UNITS = {"physical_entries": "physical entries in the frozen source list before deduplication",
               "typed_source_ids": "distinct typed source ids already present in the retained mining input",
               "groups": "distinct groups in the retained mining input",
               "duplicates_removed": "physical entries removed by the declared deduplication rule",
               "overlap_stars": "physical entries whose identities overlap retained star rows",
               "overlap_fields": "physical entries whose identities overlap retained field rows",
               "promoted_entries": "physical entries retained in expected_occurrences by the promotion rule",
               "unpromoted_entries": "physical entries counted only, bound by their unpromoted id-list witness"}
ROWS_MEMBER = "compact/rows.json"
COVERAGE_MEMBER = "compact/coverage.json"
ASSET_LIMIT = 2 * 1024**3
MANIFEST_LIMIT = 100 * 1024**2
UNPACKED_LIMIT = 8 * 1024**3
RECEIPT_LIMIT = 16 * 1024**2
POINTER_LIMIT = 100 * 1024**2
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
VERSION = re.compile(r"[A-Za-z0-9._+-]*[0-9][A-Za-z0-9._+-]*\Z")
SLOT = re.compile(r"(?:UNKNOWN|[a-z0-9][a-z0-9._-]*)\Z")
CLASSES = {"ADOPT-NOW", "TRIAL", "WATCH", "REJECT", "NO-GAP", "OUT-OF-SCOPE", "PENDING"}
RECORDED = {"RECORDED-UPSTREAM-TEST", "RECORDED-INTEGRATION-CHECK", "RECORDED-LIVE-ACCEPTANCE"}
EVIDENCE = RECORDED | {"SOURCE-REVIEW", "DOCUMENTARY", "UNKNOWN"}
ROW_REQUIRED = {"repository_or_entry", "slot", "disposition", "evidence_class", "pin", "primary_sources",
                "capture_sha256", "archive_member", "owner_lane", "refresh_date"}
ROW_OPTIONAL = {"qualification", "pending", "choices", "source_refs", "source_pointer", "acceptance_witness",
                "searched", "reopen_when", "note", "decision_scope", "candidate_implementation_status", "source_entry_witness"}
REF_KEYS = {"sha256", "pointer", "archive_member", "source_id", "owner_lane", "occurrence_id"}
NATIVE_LIST_HEADER = (
    "input_id", "source_kind", "source_repository", "source_pin", "source_path", "source_line",
    "source_content_sha256", "source_heading", "entry_kind", "canonical_english", "entry_label",
    "linked_repository", "linked_targets_json", "layer_fit", "relevant_slot", "disposition", "reason",
    "verification_status", "searched_evidence", "evidence_json",
)
# Exact entry syntax from discover-skills.json@6aa61da9; the containing
# repository is validated separately with catalog_decisions.identity.
NATIVE_SKILL_REF = re.compile(r"([A-Za-z0-9-]+/[A-Za-z0-9._-]+)@([a-z0-9-]+)\Z")
NATIVE_SKILLS_SCHEMA = REPO / "tools/sota-convergence/landscape-sweep/schemas/discover-skills.json"


class CompactError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise CompactError(message)


def text(value, label):
    require(isinstance(value, str) and bool(value.strip()) and value == value.strip(), label + " must be nonempty canonical text")
    require(not any(ord(c) < 32 or ord(c) == 127 for c in value), label + " contains a control character")
    return value


def sha(value, label):
    require(isinstance(value, str) and SHA256.fullmatch(value), label + " must be a lowercase SHA256")
    return value


def load(raw):
    try:
        return json.loads(raw, object_pairs_hook=unique_json)
    except (ValueError, UnicodeError, InvalidDecisionIndex) as error:
        raise CompactError("invalid JSON: " + str(error)) from error


def closed(value, required, optional, label):
    require(isinstance(value, dict) and required <= value.keys() and value.keys() <= required | optional,
            label + " has missing or unsupported keys")


def canonical(value):
    value = text(value, "repository_or_entry")
    skill = NATIVE_SKILL_REF.fullmatch(value)
    if skill:
        try:
            return github_identity(skill[1]) + "@" + skill[2]
        except InvalidDecisionIndex as error:
            raise CompactError("native skill entry has an invalid containing repository") from error
    result = canon(value)
    require(not result.startswith(("/", "file:", "~")), "identity must not be a private local path")
    return result


def qualification(value):
    closed(value, set(), {"catalog", "role", "slot"}, "qualification")
    return {key: text(value[key], "qualification." + key) for key in sorted(value)}


def key(row):
    closed(row, {"repository_or_entry", "slot"}, {"qualification"}, "coverage key")
    slot = text(row["slot"], "slot")
    require(SLOT.fullmatch(slot), "slot must be an explicit canonical selector")
    return canonical(row["repository_or_entry"]), slot, json.dumps(qualification(row.get("qualification", {})), sort_keys=True, ensure_ascii=False)


def decision_key(row):
    return key({name: row[name] for name in ("repository_or_entry", "slot", "qualification") if name in row})


def member_name(name):
    text(name, "archive member")
    try:
        # Reuse the maintained confinement contract, without extracting data.
        safe_file(Path(tempfile.gettempdir()) / "g5-archive-member-contract", name)
    except InvalidDecisionIndex as error:
        raise CompactError("unsafe archive member: " + str(error)) from error
    require(PurePosixPath(name).as_posix() == name and name != ".", "archive member must be canonical")
    return name


def digest_stream(stream, keep=False):
    h = hashlib.sha256()
    chunks = []
    while chunk := stream.read(1024 * 1024):
        h.update(chunk)
        if keep:
            chunks.append(chunk)
    return h.hexdigest(), b"".join(chunks) if keep else None


class BoundedReader:
    """Count decoded bytes, including extension headers/padding, before tarfile."""

    def __init__(self, stream):
        self.stream = stream
        self.read_bytes = 0

    def read(self, size):
        require(0 <= size <= UNPACKED_LIMIT - self.read_bytes, "archive exceeds 8 GiB decoded byte bound")
        raw = self.stream.read(size)
        self.read_bytes += len(raw)
        return raw


class BoundedTarInfo(tarfile.TarInfo):
    @classmethod
    def frombuf(cls, buf, encoding, errors):
        info = super().frombuf(buf, encoding, errors)
        if info.type in {tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK, tarfile.XHDTYPE,
                         tarfile.XGLTYPE, tarfile.SOLARIS_XHDTYPE}:
            require(info.size <= 1024**2, "TAR extension metadata exceeds its 1 MiB bound")
        require(info.type != tarfile.GNUTYPE_SPARSE, "sparse archive members are forbidden")
        return info


def read_archive(asset, wanted=None):
    """Stream/hash all original bytes; retain only requested small JSON witnesses."""
    require(shutil.which("zstd") is not None, "native zstd CLI is required; install the supported upstream package")
    require(asset.is_file() and not asset.is_symlink(), "asset must be a regular TAR.ZST file")
    require(asset.name.endswith(".tar.zst"), "asset suffix must be .tar.zst")
    require(0 < asset.stat().st_size < ASSET_LIMIT, "release asset must be smaller than 2 GiB")
    wanted = wanted or {ROWS_MEMBER, COVERAGE_MEMBER}
    index, retained, seen = {}, {}, set()
    total = 0
    with asset.open("rb") as source, tempfile.TemporaryFile() as errors:
        asset_sha, _ = digest_stream(source)
        source.seek(0)
        process = subprocess.Popen(["zstd", "--decompress", "--stdout", "--quiet"], stdin=source,
                                   stdout=subprocess.PIPE, stderr=errors)
        decoded = BoundedReader(process.stdout)
        try:
            with tarfile.open(fileobj=decoded, mode="r|", ignore_zeros=True, tarinfo=BoundedTarInfo) as archive:
                for member in archive:
                    name = member_name(member.name.rstrip("/") if member.isdir() else member.name)
                    require(name not in seen, "duplicate archive member: " + name)
                    seen.add(name)
                    require(member.isdir() or member.isfile(), "archive links/devices/special members are forbidden")
                    require(not member.issparse(), "sparse archive members are forbidden")
                    require(len(seen) <= 200000, "archive member count exceeds the bounded publication contract")
                    require(type(member.size) is int and member.size >= 0, "invalid member size")
                    total += member.size
                    require(total <= UNPACKED_LIMIT, "archive exceeds 8 GiB uncompressed bound")
                    if member.isdir():
                        require(member.size == 0, "directory must have no payload")
                        continue
                    keep = name in wanted
                    if keep:
                        limit = MANIFEST_LIMIT if name == ROWS_MEMBER or name == COVERAGE_MEMBER else POINTER_LIMIT
                        if member.size >= limit and name not in {ROWS_MEMBER, COVERAGE_MEMBER}:
                            keep = False  # Unsupported large pointer sources remain blocked, not copied into memory.
                        else:
                            require(member.size < limit, "retained JSON member exceeds its publication bound")
                    with archive.extractfile(member) as payload:
                        file_sha, raw = digest_stream(payload, keep)
                    index[name] = {"sha256": file_sha, "bytes": member.size}
                    if keep:
                        retained[name] = raw
            while decoded.read(1024 * 1024):
                pass  # Drain chunks through the same decoded-byte budget.
            require(process.wait(timeout=10) == 0, "native zstd rejected the release asset")
        except (tarfile.TarError, OSError, subprocess.TimeoutExpired) as error:
            raise CompactError("invalid release archive: " + type(error).__name__) from error
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            process.stdout.close()
        source.seek(0)
        final_sha, _ = digest_stream(source)
        require(final_sha == asset_sha, "asset changed while being inspected")
    return asset_sha, index, retained


def match_capture(member, expected, index):
    member_name(member)
    sha(expected, "capture hash")
    require(not member.startswith("compact/"), "decision/coverage metadata is not an original capture")
    require(member in index and index[member]["sha256"] == expected, "capture is missing or hash-mismatched: " + member)


def validate_pin(value, label, blockers):
    if value is None:
        blockers.append(label + ":unknown-pin")
        return
    closed(value, {"kind", "version_or_commit", "repository_or_source", "subject"}, set(), label)
    require(value["kind"] in {"commit", "version"}, label + ": invalid pin kind")
    require(value["subject"] in {"implementation", "source-entry", "reference"}, label + ": invalid pin subject")
    version = text(value["version_or_commit"], label + ".version_or_commit")
    if value["kind"] == "commit":
        require(COMMIT.fullmatch(version), label + ": commit must be its full 40-hex Git object ID, never a capture SHA")
    else:
        require(VERSION.fullmatch(version) and not any(word in version.lower() for word in ("latest", "main", "master", "head")),
                label + ": version must be an exact, nonfloating release")
    canonical(value["repository_or_source"])


def validate_locator(locator, pin, label, blockers):
    locator = text(locator, label)
    if locator.upper() in {"UNKNOWN", "UNVERIFIED", "PENDING", "NONE", "N/A"}:
        blockers.append(label + ":unknown-primary-locator")
        return
    require(not locator.startswith(("/", "~", "file:")), "primary locator must not be a host path")
    require(not re.search(r"/(?:blob|tree|raw)/(?:main|master|HEAD|latest)(?:/|$)|raw\.githubusercontent\.com/[^/]+/[^/]+/(?:main|master|HEAD|latest)(?:/|$)", locator, re.I),
            "primary locator uses a floating ref")
    require(locator.startswith("https://") or re.search(r"@[^:]+:", locator), "primary locator must name an upstream HTTPS source or repo@pin:file")
    if pin is None:
        return
    source = canonical(pin["repository_or_source"])
    version = pin["version_or_commit"]
    at_pin = re.fullmatch(r"(.+)@([^:]+):(.+)", locator)
    if at_pin:
        require(canonical(at_pin[1]) == source and at_pin[2] == version, "primary repo@pin locator does not match its declared source/pin")
        return
    url = urlsplit(locator)
    require(url.scheme == "https" and not url.username and not url.password, "primary URL must be HTTPS and credential-free")
    parts = url.path.strip("/").split("/")
    ref, located_source = None, None
    if url.hostname == "raw.githubusercontent.com" and len(parts) >= 4:
        located_source, ref = canon("/".join(parts[:2])), parts[2]
    elif url.hostname in {"github.com", "www.github.com"} and len(parts) >= 4:
        located_source = canon("/".join(parts[:2]))
        if parts[2] in {"blob", "tree", "commit", "raw"}:
            ref = parts[3]
        elif parts[2:4] == ["releases", "tag"] and len(parts) >= 5:
            ref = parts[4]
    elif url.hostname == "api.github.com" and len(parts) >= 5 and parts[0] == "repos":
        located_source = canon("/".join(parts[1:3]))
        if parts[3] == "commits":
            ref = parts[4]
        elif parts[3:5] == ["git", "commits"] and len(parts) >= 6:
            ref = parts[5]
    if located_source is not None:
        require(located_source == source, "primary locator names a different source repository")
        if ref is not None:
            require(ref == version, "primary locator ref does not match its declared pin")
            return
    elif locator.startswith(source.rstrip("/") + "/") and version in parts:
        return  # Explicitly versioned official docs, or another host's immutable commit path.
    blockers.append(label + ":unestablished-pinned-primary-locator")


def validate_ref(ref, index):
    closed(ref, {"sha256", "pointer"}, REF_KEYS - {"sha256", "pointer"}, "source_ref")
    sha(ref["sha256"], "source_ref hash")
    text(ref["pointer"], "source_ref pointer")
    for name in ("source_id", "owner_lane", "occurrence_id"):
        if name in ref:
            text(ref[name], "source_ref." + name)
    if "archive_member" in ref:
        match_capture(ref["archive_member"], ref["sha256"], index)


def validation_profile(profile):
    require(profile in {None, START_CLOSURE_PROFILE}, "unsupported validation profile")
    return profile == START_CLOSURE_PROFILE


def closure_metadata(row, index):
    """Validate explicit residue declarations; none is evidence or a source pin."""
    closure = row.get("closure", {})
    closed(closure, set(), {"pending_pin", "pending_locator", "pending_conflict", "disagreements"}, "closure")
    for name, reasons in (("pending_pin", PIN_REASONS), ("pending_locator", LOCATOR_REASONS)):
        if name in closure:
            residue = closure[name]
            closed(residue, {"reason_code", "measurement"}, set(), "closure." + name)
            require(residue["reason_code"] in reasons, "unsupported " + name + " reason code")
            text(residue["measurement"], "closure." + name + ".measurement")
            require(row["disposition"] == "PENDING", name + " residue must be PENDING and can never be an action row")
    if "pending_conflict" in closure:
        conflict = closure["pending_conflict"]
        closed(conflict, {"provisional_disposition", "measurement", "action_side_row_ids"}, set(), "closure.pending_conflict")
        require(row["disposition"] == "PENDING", "PENDING-CONFLICT must retain PENDING and can never be a final action row")
        require(conflict["provisional_disposition"] in CLASSES - ACTION_CLASSES - {"PENDING"}, "PENDING-CONFLICT requires a conservative non-action provisional")
        text(conflict["measurement"], "pending_conflict.measurement")
        pending = row.get("pending")
        require(isinstance(pending, dict) and all(pending.get(name) == conflict[name] for name in ("provisional_disposition", "measurement")), "PENDING-CONFLICT must retain the existing pending provisional and settling measurement")
        action_ids = conflict["action_side_row_ids"]
        require(isinstance(action_ids, list) and bool(action_ids), "PENDING-CONFLICT must retain its original action-side row ids")
        for action_id in action_ids:
            text(action_id, "pending_conflict.action_side_row_id")
        require(len(action_ids) == len(set(action_ids)), "duplicate PENDING-CONFLICT action-side row id")
        choices = row.get("choices", [])
        require(isinstance(choices, list) and all(isinstance(choice, dict) for choice in choices), "PENDING-CONFLICT choices must be an array of original choices")
        dispositions = {choice.get("disposition") for choice in choices}
        require(len(dispositions) >= 2 and bool(dispositions & ACTION_CLASSES), "PENDING-CONFLICT requires contradictory same-slot choices including an action decision")
        for choice in choices:
            if isinstance(choice.get("qualification"), dict) and "slot" in choice["qualification"]:
                require(choice["qualification"]["slot"] == row["slot"], "different native slots are a scope split, not PENDING-CONFLICT")
    null_pins = row["pin"] is None or any(source["pin"] is None for source in row["primary_sources"])
    require("pending_pin" not in closure or null_pins, "pending_pin requires an actual null row or primary pin")
    disagreements = closure.get("disagreements", [])
    require(isinstance(disagreements, list), "closure.disagreements must be an array")
    for item in disagreements:
        closed(item, {"id", "kind", "status", "recorded_locator", "recorded_repository", "resolution", "explanation", "measurement", "evidence_refs"},
               {"recorded_pin"}, "closure disagreement")
        for name in ("id", "recorded_locator", "recorded_repository", "resolution", "explanation"):
            text(item[name], "disagreement." + name)
        canonical(item["recorded_repository"])
        require(item["kind"] in {"source-repository", "repo-pin"}, "unsupported disagreement kind")
        require(item["status"] in {"RESOLVED", "PENDING"}, "unsupported disagreement status")
        require(isinstance(item["measurement"], str), "disagreement.measurement must be a string")
        require(isinstance(item["evidence_refs"], list), "disagreement evidence_refs must be an array")
        for ref in item["evidence_refs"]:
            validate_ref(ref, index)
        if "recorded_pin" in item:
            defects = []
            validate_pin(item["recorded_pin"], "disagreement.recorded_pin", defects)
            require(not defects, "disagreement recorded pin must be established")
            require(canonical(item["recorded_pin"]["repository_or_source"]) == canonical(item["recorded_repository"]),
                    "disagreement recorded repository differs from its recorded pin")
        require(item["kind"] != "repo-pin" or "recorded_pin" in item, "repo-pin disagreement must retain its original pin")
        recorded_pin = item.get("recorded_pin")
        if recorded_pin is None:
            recorded_pin = next((source["pin"] for source in row["primary_sources"] if source["pin"] is not None
                                 and canonical(source["pin"]["repository_or_source"]) == canonical(item["recorded_repository"])), None)
        require(recorded_pin is not None, "disagreement must retain its original pin when the source pin is corrected")
        original_defect = None
        try:
            validate_locator(item["recorded_locator"], recorded_pin, "recorded disagreement", [])
        except CompactError as error:
            original_defect = str(error)
        require(original_defect in {"primary locator names a different source repository", "primary repo@pin locator does not match its declared source/pin",
                                    "primary locator ref does not match its declared pin"}, "declared disagreement is not detected in its retained original locator/pin claims")
        at_pin = re.fullmatch(r"(.+)@([^:]+):(.+)", item["recorded_locator"])
        source_defect = original_defect == "primary locator names a different source repository" or (at_pin is not None and canonical(at_pin[1]) != canonical(recorded_pin["repository_or_source"]))
        require(item["kind"] == ("source-repository" if source_defect else "repo-pin"), "declared disagreement kind differs from its detected original defect")
        if item["status"] == "PENDING":
            require(row["disposition"] == "PENDING", "an action or non-PENDING row cannot retain an unresolved disagreement")
            text(item["measurement"], "disagreement.measurement")
            require(closure.get("pending_locator", {}).get("reason_code") == "source-disagreement", "unresolved disagreement requires PENDING-LOCATOR residue")
        else:
            require(bool(item["evidence_refs"]), "resolved disagreement requires primary evidence references")
    if "provenance" in row:
        provenance = row["provenance"]
        closed(provenance, {"pin_resolution"}, set(), "provenance")
        require(isinstance(provenance["pin_resolution"], list) and bool(provenance["pin_resolution"]), "pin resolution provenance must be a nonempty array")
        seen_targets = set()
        for resolution in provenance["pin_resolution"]:
            closed(resolution, {"target", "method", "resolved_at", "blob_id", "commit", "repository", "path"}, set(), "pin resolution")
            target = text(resolution["target"], "pin resolution target")
            require(target not in seen_targets, "duplicate pin resolution target")
            seen_targets.add(target)
            require(resolution["method"] in {"git-blob-default-tree", "git-blob-path-history"}, "unsupported pin resolution method")
            require(COMMIT.fullmatch(text(resolution["blob_id"], "pin resolution blob id")) and COMMIT.fullmatch(text(resolution["commit"], "pin resolution commit")), "pin resolution uses full Git object ids")
            require(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text(resolution["resolved_at"], "pin resolution time")), "pin resolution time must be UTC RFC3339")
            canonical(resolution["repository"])
            member_name(resolution["path"])
            match = re.fullmatch(r"primary\[([0-9]+)\]", target)
            require(target == "row" or match is not None, "pin resolution target must name row or primary[N]")
            if target == "row":
                resolved_pin = row["pin"]
            else:
                require(int(match[1]) < len(row["primary_sources"]), "pin resolution target is out of range")
                resolved_pin = row["primary_sources"][int(match[1])]["pin"]
            require(resolved_pin is not None and resolved_pin["kind"] == "commit" and resolved_pin["version_or_commit"] == resolution["commit"]
                    and canonical(resolved_pin["repository_or_source"]) == canonical(resolution["repository"]), "pin resolution provenance differs from its final pin")
    return closure


def closure_locator(source, label, closure, blockers):
    """Keep unsafe locators fatal and detect every explicitly deferred disagreement."""
    locator = text(source["locator"], label)
    unknown = locator.upper() in {"UNKNOWN", "UNVERIFIED", "PENDING", "NONE", "N/A"}
    at_pin = re.fullmatch(r"(.+)@([^:]+):(.+)", locator)
    if not unknown and at_pin is not None:
        canonical(at_pin[1])
        require(at_pin[1].startswith("https://") or ":" not in at_pin[1], "primary repo@pin source must not name an unsafe transport")
        if at_pin[1].startswith("https://"):
            repo_url = urlsplit(at_pin[1])
            require(bool(repo_url.hostname) and not repo_url.username and not repo_url.password, "primary URL must be HTTPS and credential-free")
        require(COMMIT.fullmatch(at_pin[2]) or VERSION.fullmatch(at_pin[2]) and not any(word in at_pin[2].lower() for word in ("latest", "main", "master", "head")),
                "primary repo@pin locator must retain an exact commit or version")
        member_name(re.sub(r":[1-9][0-9]*$", "", at_pin[3]))
    elif not unknown:
        require(locator.startswith("https://"), "primary locator must name an upstream HTTPS source or repo@pin:file")
        url = urlsplit(locator)
        require(url.scheme == "https" and bool(url.hostname) and not url.username and not url.password, "primary URL must be HTTPS and credential-free")
    if not unknown:
        require(not re.search(r"[\x00-\x20\x7f]", locator), "primary locator must not contain controls or whitespace")
    failures = []
    try:
        validate_locator(locator, source["pin"], label, failures)
    except CompactError as error:
        message = str(error)
        permitted = {"primary locator names a different source repository", "primary repo@pin locator does not match its declared source/pin",
                     "primary locator ref does not match its declared pin"}
        require(message in permitted, message)
        matching = [item for item in closure.get("disagreements", []) if item["status"] == "PENDING"
                    and item["recorded_locator"] == locator and source["pin"] is not None
                    and canonical(item["recorded_repository"]) == canonical(source["pin"]["repository_or_source"])
                    and (item["kind"] == "source-repository" if message == "primary locator names a different source repository" else item.get("recorded_pin") == source["pin"])]
        require(bool(matching) and closure.get("pending_locator", {}).get("reason_code") == "source-disagreement", message)
        return True
    if "pending_locator" in closure:
        allowed = {label + ":unknown-primary-locator", label + ":unestablished-pinned-primary-locator"}
        blockers.extend(code for code in failures if code not in allowed)
        return bool(set(failures) & allowed)
    blockers.extend(failures)
    return False


def validate_row(row, index, profile=None):
    start_closure = validation_profile(profile)
    closed(row, ROW_REQUIRED, ROW_OPTIONAL | ({"closure", "provenance", "origin_pointer", "origin_claim_ids"} if start_closure else set()), "row")
    identity, slot, _ = decision_key(row)
    require(row["disposition"] in CLASSES and row["evidence_class"] in EVIDENCE, "unsupported disposition/evidence class")
    blockers = []
    if slot == "UNKNOWN":
        blockers.append("unknown-field-scope")
    if row["evidence_class"] == "UNKNOWN":
        blockers.append("unknown-evidence-class")
    closure = closure_metadata(row, index) if start_closure else {}
    if "origin_pointer" in row:
        origin = row["origin_pointer"]
        if isinstance(origin, str):
            require(origin == "unresolved", "unbound origin pointer must be recorded exactly as unresolved")
        else:
            closed(origin, {"archive_member", "sha256", "pointer"}, REF_KEYS - {"archive_member", "sha256", "pointer"}, "origin pointer")
            validate_ref(origin, index)
    if "origin_claim_ids" in row:
        require(row.get("origin_pointer") == "unresolved", "origin claim ids require a literal unresolved origin pointer")
        claim_ids = row["origin_claim_ids"]
        require(isinstance(claim_ids, list) and bool(claim_ids), "origin_claim_ids must be a nonempty array")
        for claim_id in claim_ids:
            text(claim_id, "origin claim id")
        require(len(claim_ids) == len(set(claim_ids)), "duplicate origin claim id on row")
    pin_blockers = []
    validate_pin(row["pin"], "row", pin_blockers)
    if "pending_pin" not in closure:
        blockers.extend(pin_blockers)
    if "decision_scope" in row:
        require(row["decision_scope"] in {"source-entry-screen", "implementation-merit", "reference-artifact"}, "unsupported decision scope")
    if "candidate_implementation_status" in row:
        require(row["candidate_implementation_status"] == "UNESTABLISHED", "unsupported candidate implementation status")
    if row["pin"]:
        skill = NATIVE_SKILL_REF.fullmatch(row["repository_or_entry"])
        parent_identity = canonical(skill[1]) if skill else identity
        foreign = canonical(row["pin"]["repository_or_source"]) != parent_identity
        if foreign:
            require(row["pin"]["subject"] in {"source-entry", "reference"}, "foreign source pin is not an implementation pin")
            require(row["evidence_class"] in {"SOURCE-REVIEW", "DOCUMENTARY"}, "foreign primary source pin cannot establish recorded execution")
            if row.get("decision_scope") != "source-entry-screen" or row.get("candidate_implementation_status") != "UNESTABLISHED" or not {"source_pointer", "source_entry_witness"} & row.keys():
                blockers.append("foreign-primary-pin-scope-unqualified")
        if skill:
            if (row["evidence_class"] not in {"SOURCE-REVIEW", "DOCUMENTARY"} or row["disposition"] != "PENDING"
                    or row["pin"]["kind"] != "commit" or row["pin"]["subject"] != "implementation" or "source_pointer" not in row):
                blockers.append("skill-entry-source-scope-unqualified")
    if "source_entry_witness" in row:
        witness = row["source_entry_witness"]
        closed(witness, {"archive_member", "sha256", "pointer"}, set(), "source entry witness")
        match_capture(witness["archive_member"], witness["sha256"], index)
        require(isinstance(witness["pointer"], str) and re.fullmatch(r"(?:line:|#L)[1-9][0-9]*", witness["pointer"]), "native TSV witness requires a one-based physical line locator")
        if (row["evidence_class"] not in {"SOURCE-REVIEW", "DOCUMENTARY"} or row.get("decision_scope") != "source-entry-screen"
                or row.get("candidate_implementation_status") != "UNESTABLISHED" or row["pin"] is None
                or row["pin"]["subject"] != "source-entry"):
            blockers.append("native-source-entry-witness-scope-unqualified")
    match_capture(row["archive_member"], row["capture_sha256"], index)
    text(row["owner_lane"], "owner_lane")
    value = text(row["refresh_date"], "refresh_date")
    try:
        require(date.fromisoformat(value).isoformat() == value, "refresh_date must be YYYY-MM-DD")
    except ValueError as error:
        raise CompactError("invalid refresh date") from error
    sources = row["primary_sources"]
    require(isinstance(sources, list) and bool(sources), "every row must retain a primary source")
    pending_locator_detected = False
    for i, source in enumerate(sources):
        closed(source, {"locator", "pin", "subject"}, {"capture_sha256", "archive_member", "pointer"}, "primary source")
        text(source["subject"], "primary source subject")
        pin_blockers = []
        validate_pin(source["pin"], f"primary[{i}]", pin_blockers)
        if "pending_pin" not in closure:
            blockers.extend(pin_blockers)
        if start_closure:
            pending_locator_detected |= closure_locator(source, f"primary[{i}].locator", closure, blockers)
        else:
            validate_locator(source["locator"], source["pin"], f"primary[{i}].locator", blockers)
        require(("capture_sha256" in source) == ("archive_member" in source), "primary capture hash/member must be paired")
        if "archive_member" in source:
            match_capture(source["archive_member"], source["capture_sha256"], index)
        if "pointer" in source:
            require(isinstance(source["pointer"], str) and (source["pointer"] == "" or source["pointer"].startswith("/")), "primary pointer must be JSON Pointer")
    require("pending_locator" not in closure or pending_locator_detected or any(item["status"] == "PENDING" for item in closure.get("disagreements", [])),
            "pending_locator requires an actual unknown locator or recorded disagreement")
    if row["pin"] is not None:
        require(any(source["pin"] == row["pin"] for source in sources), "no primary source binds the row's exact subject and implementation/source pin")
    for name in ("source_pointer",):
        if name in row:
            require(isinstance(row[name], str) and (row[name] == "" or row[name].startswith("/")), name + " must be JSON Pointer")
    for name in ("searched", "reopen_when", "note"):
        if name in row:
            text(row[name], name)
    require(row["disposition"] != "REJECT" or bool(row.get("searched")), "REJECT must name its searched source/surface")
    require((row["disposition"] == "PENDING") == ("pending" in row), "PENDING must retain its measurement; other rows must not carry pending")
    if "pending" in row:
        p = row["pending"]
        closed(p, {"provisional_disposition", "measurement", "owner"}, {"status"}, "pending")
        require(p["provisional_disposition"] in CLASSES - {"ADOPT-NOW", "PENDING"}, "provisional choice must never be ADOPT-NOW")
        text(p["measurement"], "pending.measurement")
        text(p["owner"], "pending.owner")
        if "status" in p:
            require(p["status"] in {"PROPOSED", "NOT-RUN", "SOURCE-AUDIT-ONLY", "EXECUTED-PENDING-RULING"}, "invalid pending status")
    refs = row.get("source_refs", [])
    require(isinstance(refs, list), "source_refs must be an array")
    for ref in refs:
        validate_ref(ref, index)
    choices = row.get("choices", [])
    require(isinstance(choices, list), "choices must be an array")
    for choice in choices:
        closed(choice, {"disposition", "source_refs"}, {"qualification"}, "choice")
        require(choice["disposition"] in CLASSES - {"PENDING"}, "invalid choice disposition")
        require(isinstance(choice["source_refs"], list) and bool(choice["source_refs"]), "choice needs original sources")
        if "qualification" in choice:
            qualification(choice["qualification"])
        for ref in choice["source_refs"]:
            validate_ref(ref, index)
    require((row["evidence_class"] in RECORDED) == ("acceptance_witness" in row), "recorded execution requires an original witness; source review cannot carry execution")
    if "acceptance_witness" in row:
        witness = row["acceptance_witness"]
        closed(witness, {"archive_member", "sha256", "pointer"}, set(), "acceptance witness")
        match_capture(witness["archive_member"], witness["sha256"], index)
        require(isinstance(witness["pointer"], str) and (witness["pointer"] == "" or witness["pointer"].startswith("/")), "acceptance witness needs a JSON Pointer")
    require(row["disposition"] != "ADOPT-NOW" or row["evidence_class"] == "RECORDED-LIVE-ACCEPTANCE", "source-only or test-only evidence cannot establish ADOPT-NOW")
    require(row["disposition"] != "ADOPT-NOW" or (row["pin"] is not None and row["pin"]["subject"] == "implementation"), "ADOPT-NOW requires an implementation pin, not a reference/source-entry pin")
    return blockers


def pointer(document, value):
    result = document
    for part in value.split("/")[1:]:
        token = part.replace("~1", "/").replace("~0", "~")
        try:
            if isinstance(result, list):
                require(token == "0" or (token.isdecimal() and not token.startswith("0")), "noncanonical pointer array index")
                result = result[int(token)]
            else:
                result = result[token]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise CompactError("capture pointer does not resolve") from error
    return result


def selected_capture(member, locator, captures, cache, blockers, label):
    if member not in captures:
        blockers.append({"code": "unsupported-large-pointer-capture", "source": label})
        return None
    raw = captures[member]
    if locator == "" or locator.startswith("/"):
        if member not in cache:
            try:
                cache[member] = load(raw)
            except CompactError:
                blockers.append({"code": "unsupported-json-pointer-capture", "source": label})
                return None
        try:
            selected = pointer(cache[member], locator)
            if selected is None:
                blockers.append({"code": "null-capture-selection", "source": label})
            return selected
        except CompactError:
            blockers.append({"code": "unresolved-capture-pointer", "source": label})
            return None
    match = re.fullmatch(r"(?:line:|#L)([1-9][0-9]*)", locator)
    if match:
        try:
            lines = raw.decode("utf-8").splitlines()
            return lines[int(match[1]) - 1]
        except (UnicodeError, IndexError):
            blockers.append({"code": "unresolved-capture-line", "source": label})
            return None
    blockers.append({"code": "unsupported-capture-locator", "source": label})
    return None


def declared_witness(value, index, captures, cache, blockers, label):
    if value is None:
        blockers.append({"code": label + "-missing"})
        return None
    closed(value, {"archive_member", "sha256", "pointer"}, set(), label)
    match_capture(value["archive_member"], value["sha256"], index)
    require(isinstance(value["pointer"], str) and (value["pointer"] == "" or value["pointer"].startswith("/")), label + " must use a JSON Pointer")
    return selected_capture(value["archive_member"], value["pointer"], captures, cache, blockers, label)


def native_list_record(member, locator, captures, cache):
    """Read the retained 20-column TSV using stdlib csv, not a mining replay.

    csv.reader(strict=True), newline='' and line_num follow Python's supported
    csv interface (https://docs.python.org/3/library/csv.html). Each record
    must consume exactly one physical line; generated JSON and multiline CSV
    are outside this single native-format contract.
    """
    require(member in captures, "native TSV capture is unavailable or exceeds the pointer bound")
    cache_key = ("native-list-tsv", member)
    if cache_key not in cache:
        decoded = captures[member].decode("utf-8")
        reader = csv.reader(io.StringIO(decoded, newline=""), delimiter="\t", strict=True)
        header = next(reader, None)
        require(header == list(NATIVE_LIST_HEADER) and reader.line_num == 1, "native TSV header must match the exact 20-column retained format")
        records = {}
        previous = reader.line_num
        for values in reader:
            require(reader.line_num == previous + 1, "native TSV embedded multiline records are unsupported")
            require(len(values) == len(NATIVE_LIST_HEADER), "native TSV physical record width is not 20")
            records[reader.line_num] = dict(zip(NATIVE_LIST_HEADER, values))
            previous = reader.line_num
        cache[cache_key] = records
    line = int(re.fullmatch(r"(?:line:|#L)([1-9][0-9]*)", locator)[1])
    require(line in cache[cache_key], "native TSV physical line is absent or selects its header")
    return cache[cache_key][line]


def github_repository_href(value):
    """An exact Markdown repository href; never guess from another domain/path."""
    require(isinstance(value, str) and re.fullmatch(r"https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9._-]+/?", value, re.I),
            "native source entry requires an exact GitHub repository href without query/fragment/subpath")
    try:
        return "https://github.com/" + github_identity(value)
    except InvalidDecisionIndex as error:
        raise CompactError("native source entry href does not identify a valid GitHub owner/repository") from error


def markdown_source_locator(locator):
    at_pin = re.fullmatch(r"(.+)@([0-9a-f]{40}):([^:\r\n]+):([1-9][0-9]*)", locator)
    if at_pin:
        source, pin, path, line = at_pin.groups()
        return canonical(source), pin, path, int(line)
    url = urlsplit(locator)
    require(url.scheme == "https" and not url.query and not url.username and not url.password and url.port is None,
            "native Markdown source locator is not an exact upstream HTTPS file")
    fragment = re.fullmatch(r"L([1-9][0-9]*)", url.fragment)
    require(fragment, "native Markdown source locator requires one exact source line")
    parts = url.path.strip("/").split("/")
    if url.hostname in {"github.com", "www.github.com"} and len(parts) >= 5 and parts[2] in {"blob", "raw"}:
        return canonical("/".join(parts[:2])), parts[3], "/".join(parts[4:]), int(fragment[1])
    if url.hostname == "raw.githubusercontent.com" and len(parts) >= 4:
        return canonical("/".join(parts[:2])), parts[2], "/".join(parts[3:]), int(fragment[1])
    raise CompactError("native Markdown locator format is unsupported")


def validate_native_source_entry(row, index, captures, cache, blockers):
    if "source_entry_witness" not in row:
        return
    witness = row["source_entry_witness"]
    label = canonical(row["repository_or_entry"]) + ":" + row["slot"]
    try:
        require(row["evidence_class"] in {"SOURCE-REVIEW", "DOCUMENTARY"} and row.get("decision_scope") == "source-entry-screen"
                and row.get("candidate_implementation_status") == "UNESTABLISHED", "native TSV proves only documentary source-entry screening")
        p = row["pin"]
        require(p is not None and p["kind"] == "commit" and p["subject"] == "source-entry", "native TSV requires its source-entry Git commit pin")
        record = native_list_record(witness["archive_member"], witness["pointer"], captures, cache)
        candidate = canonical(row["repository_or_entry"])
        require(canonical(record["linked_repository"]) == candidate, "native TSV linked_repository differs from row identity")
        require(record["layer_fit"] == row["slot"] and record["layer_fit"] != "UNKNOWN", "native TSV literal layer_fit differs from row slot")
        if "slot" in row.get("qualification", {}):
            require(row["qualification"]["slot"] == record["layer_fit"], "native TSV literal slot differs from qualification.slot")
        require(record["relevant_slot"] == "true", "native TSV entry does not declare relevant slot")
        require(canonical(record["source_repository"]) == canonical(p["repository_or_source"])
                and record["source_pin"] == p["version_or_commit"], "native TSV source repository/pin differs from primary source pin")
        member_name(record["source_path"])
        require(Path(record["source_path"]).suffix.lower() in {".md", ".markdown"}, "native TSV adapter requires an upstream Markdown file")
        require(re.fullmatch(r"[1-9][0-9]*", record["source_line"]), "native TSV source line is not one-based canonical text")
        line_number = int(record["source_line"])
        require(record["input_id"] == record["source_repository"] + ":" + record["source_path"] + ":" + record["source_line"],
                "native TSV input_id differs from its exact source repository/path/line")
        require(record["source_content_sha256"] == row["capture_sha256"], "native TSV source hash differs from retained primary capture")
        match_capture(row["archive_member"], record["source_content_sha256"], index)
        require(row["archive_member"] in captures, "pinned primary Markdown capture is unavailable or exceeds the pointer bound")
        source_binding = (canonical(record["source_repository"]), record["source_pin"], record["source_path"], line_number)
        bound = False
        for source in row["primary_sources"]:
            if source["pin"] != p:
                continue
            try:
                bound |= markdown_source_locator(source["locator"]) == source_binding
            except (CompactError, ValueError):
                continue
        require(bound, "primary locator differs from the original TSV source repository/pin/file/line")
        # The retained mining source numbers physical LF/CRLF lines; Unicode
        # separators or embedded control characters must not create new lines.
        primary_lines = captures[row["archive_member"]].decode("utf-8").split("\n")
        require(line_number <= len(primary_lines), "native TSV source line is absent from the pinned Markdown")
        primary_line = primary_lines[line_number - 1]
        links = set()
        for match in re.finditer(r"(?<!!)\[[^\]\r\n]*\]\((https://github\.com/[^\s)]+)\)", primary_line, re.I):
            try:
                links.add(github_repository_href(match[1]))
            except CompactError:
                continue
        require(candidate in links, "pinned Markdown line does not contain the exact candidate repository link")
        targets = load(record["linked_targets_json"])
        require(isinstance(targets, list), "native TSV linked_targets_json must be its original array")
        require(any(isinstance(target, dict) and isinstance(target.get("repository"), str)
                    and canonical(target["repository"]) == candidate and github_repository_href(target.get("url")) == candidate
                    for target in targets), "native TSV linked-target URL/identity does not match the pinned Markdown repository link")
        cache[("native-entry-bound", decision_key(row), witness["archive_member"], witness["sha256"], witness["pointer"])] = record
        return True
    except (CompactError, csv.Error, UnicodeError, ValueError, TypeError) as error:
        blockers.append({"code": "native-source-entry-witness-unverified", "source": label, "reason": str(error)})
        return False


def skill_source_path(locator):
    """Only an immutable GitHub SKILL.md file URL, not a tree or file guess."""
    url = urlsplit(locator)
    if url.scheme != "https" or url.query or url.username or url.password or url.port is not None:
        return None
    parts = url.path.strip("/").split("/")
    if url.hostname in {"github.com", "www.github.com"} and len(parts) >= 5 and parts[2] in {"blob", "raw"}:
        parent, ref, path = canonical("/".join(parts[:2])), parts[3], "/".join(parts[4:])
    elif url.hostname == "raw.githubusercontent.com" and len(parts) >= 4:
        parent, ref, path = canonical("/".join(parts[:2])), parts[2], "/".join(parts[3:])
    else:
        return None
    if not COMMIT.fullmatch(ref) or PurePosixPath(path).name != "SKILL.md":
        return None
    member_name(path)
    return parent, ref, path


def validate_native_skill_entry(row, index, captures, cache, blockers):
    """Bind the documented native skills entry without turning claims into bytes."""
    skill = NATIVE_SKILL_REF.fullmatch(row["repository_or_entry"])
    if not skill:
        return
    label = canonical(row["repository_or_entry"]) + ":" + row["slot"]
    try:
        require(row["evidence_class"] in {"SOURCE-REVIEW", "DOCUMENTARY"} and row["disposition"] == "PENDING",
                "native skill entry remains documentary and PENDING")
        p = row["pin"]
        require(p is not None and p["subject"] == "implementation" and p["kind"] == "commit"
                and canonical(p["repository_or_source"]) == canonical(skill[1]), "native skill entry pin must bind its actual containing repository")
        require(re.fullmatch(r"/proposed/(?:0|[1-9][0-9]*)", row.get("source_pointer", "")), "native skill entry requires its original proposal pointer")
        original = selected_capture(row["archive_member"], "", captures, cache, blockers, label)
        require(isinstance(original, dict), "native skills original must be its discovery object")
        schema = load(NATIVE_SKILLS_SCHEMA.read_bytes())
        require(set(original) == set(schema["required"]), "native skills original must retain its exact five-key discovery shape")
        require(isinstance(original["proposed"], list), "native skills proposed must be an original array")
        proposal = pointer(original, row["source_pointer"])
        proposal_schema = schema["properties"]["proposed"]["items"]
        require(isinstance(proposal, dict) and set(proposal) == set(proposal_schema["required"]), "native skills proposal shape is unsupported")
        require(isinstance(proposal["skill_ref"], str) and NATIVE_SKILL_REF.fullmatch(proposal["skill_ref"]), "native original skill_ref has unsupported syntax")
        require(canonical(proposal["skill_ref"]) == canonical(row["repository_or_entry"])
                and proposal["pin"] == p["version_or_commit"], "native original skill_ref/pin does not bind the entry")
        task = proposal["lifecycle_task"]
        require(task in proposal_schema["properties"]["lifecycle_task"]["enum"] and original["layer_id"] == row["slot"] == "skills-" + task,
                "native skills original task/layer_id differs from the literal row slot")
        require(isinstance(proposal["evidence"], list) and all(isinstance(item, str) for item in proposal["evidence"]), "native skill evidence must retain original locator strings")
        skill_hash = proposal["skill_md_sha256"]
        if skill_hash is None:
            blockers.append({"code": "skill-entry-primary-bytes-unestablished", "source": label})
            return
        sha(skill_hash, "native SKILL.md SHA256")
        original_paths = set()
        for evidence in proposal["evidence"]:
            for match in re.finditer(r"https://[^\s)\]>]+", evidence):
                path = skill_source_path(match[0])
                if path is not None:
                    original_paths.add(path)
        established = False
        for source in row["primary_sources"]:
            if source["pin"] != p or "archive_member" not in source or source.get("capture_sha256") != skill_hash:
                continue
            path = skill_source_path(source["locator"])
            if path is None or path not in original_paths or path[:2] != (canonical(skill[1]), p["version_or_commit"]):
                continue
            match_capture(source["archive_member"], skill_hash, index)
            if source["archive_member"] not in captures or not captures[source["archive_member"]]:
                continue
            require(source["archive_member"] != row["archive_member"], "native discovery JSON is not primary SKILL.md bytes")
            try:
                body = captures[source["archive_member"]].decode("utf-8")
            except UnicodeError:
                continue
            inspection = re.sub(r"^[\s\ufeff]*", "", body)
            if inspection.startswith(("{", "[")):
                continue  # A metadata JSON/receipt hash is not retained SKILL.md body bytes.
            try:
                json.loads(inspection)
            except ValueError:
                pass
            else:
                continue  # JSON scalars and BOM-prefixed receipts are metadata too.
            established = True
        if not established:
            blockers.append({"code": "skill-entry-primary-bytes-unestablished", "source": label})
    except (CompactError, ValueError, KeyError, TypeError) as error:
        blockers.append({"code": "native-skill-entry-witness-unverified", "source": label, "reason": str(error)})


def validate_reference_pointers(rows, captures, blockers, cache):
    for row in rows:
        label = canonical(row["repository_or_entry"]) + ":" + row["slot"]
        if "source_pointer" in row:
            original_entry = selected_capture(row["archive_member"], row["source_pointer"], captures, cache, blockers, label)
            if not NATIVE_SKILL_REF.fullmatch(row["repository_or_entry"]) and row["pin"] is not None and canonical(row["pin"]["repository_or_source"]) != canonical(row["repository_or_entry"]):
                entry_identity = None
                if isinstance(original_entry, dict):
                    entry_identity = next((original_entry[name] for name in ("repository_or_entry", "repository", "full_name", "repo", "html_url", "url") if isinstance(original_entry.get(name), str)), None)
                elif isinstance(original_entry, str):
                    entry_identity = original_entry
                if entry_identity is None or canonical(entry_identity) != canonical(row["repository_or_entry"]):
                    blockers.append({"code": "original-source-entry-identity-unbound", "source": label})
        refs = list(row.get("source_refs", []))
        refs += [ref for choice in row.get("choices", []) for ref in choice["source_refs"]]
        for ref in refs:
            if "archive_member" not in ref:
                blockers.append({"code": "unbound-source-reference", "source": label, "sha256": ref["sha256"], "pointer": ref["pointer"]})
            else:
                selected_capture(ref["archive_member"], ref["pointer"], captures, cache, blockers, label)
        for source in row["primary_sources"]:
            if "pointer" in source:
                if "archive_member" not in source:
                    blockers.append({"code": "unbound-primary-pointer", "source": label})
                else:
                    selected_capture(source["archive_member"], source["pointer"], captures, cache, blockers, label)


def validate_origin_pointer(row, captures, cache, blockers):
    origin = row.get("origin_pointer")
    if not isinstance(origin, dict):
        return
    label = canonical(row["repository_or_entry"]) + ":" + row["slot"]
    original = selected_capture(origin["archive_member"], origin["pointer"], captures, cache, blockers, "origin:" + label)
    identity, slot = None, None
    if isinstance(original, dict):
        identity = next((original[name] for name in ("repository_or_entry", "repository", "full_name", "repo", "html_url", "url", "entry", "linked_repository") if isinstance(original.get(name), str)), None)
        slot = next((original[name] for name in ("slot", "layer_fit", "layer_id", "field") if isinstance(original.get(name), str)), None)
    if identity is None or slot != row["slot"] or canonical(identity) != canonical(row["repository_or_entry"]):
        blockers.append({"code": "origin-pointer-repository-slot-unbound", "source": label})


def validate_origin_claims(row, captures, cache, blockers):
    claim_ids = row.get("origin_claim_ids", [])
    if not claim_ids:
        return
    expected = set(claim_ids)
    matched = set()
    label = canonical(row["repository_or_entry"]) + ":" + row["slot"]
    for ref in row.get("source_refs", []):
        if "archive_member" not in ref:
            continue
        original = selected_capture(ref["archive_member"], ref["pointer"], captures, cache, blockers, "origin-claim:" + label)
        if not isinstance(original, dict) or original.get("row_id") not in expected:
            continue
        identity = next((original[name] for name in ("repository_or_entry", "repository", "entry") if isinstance(original.get(name), str)), None)
        metadata = original.get("metadata", {})
        slots = original.get("slots")
        if slots is None and isinstance(metadata, dict):
            slots = metadata.get("slots")
        if identity is not None and canonical(identity) == canonical(row["repository_or_entry"]) and isinstance(slots, list) and row["slot"] in slots:
            matched.add(original["row_id"])
    for claim_id in sorted(expected - matched):
        blockers.append({"code": "origin-claim-id-repository-slot-unbound", "source": label, "row_id": claim_id})


def validate_acceptance(row, captures):
    if "acceptance_witness" not in row:
        return
    witness = row["acceptance_witness"]
    require(witness["archive_member"] in captures and len(captures[witness["archive_member"]]) < RECEIPT_LIMIT, "native acceptance receipt exceeds supported 16 MiB bound")
    receipt = pointer(load(captures[witness["archive_member"]]), witness["pointer"])
    require(isinstance(receipt, dict), "acceptance witness must select an original receipt object")
    require(receipt.get("executed") is True and receipt.get("status") == "PASS" and type(receipt.get("exit_code")) is int and receipt["exit_code"] == 0,
            "original acceptance receipt does not record a successful executed command")
    text(receipt.get("command"), "receipt.command")
    text(receipt.get("evidence_scope"), "receipt.evidence_scope")
    require(decision_key(receipt) == decision_key(row) and receipt.get("pin") == row["pin"] and receipt.get("evidence_class") == row["evidence_class"],
            "acceptance receipt has a different identity, slot, qualification, pin or evidence class")
    if row["disposition"] == "ADOPT-NOW":
        for name in ("vendor_install", "check"):
            fact = receipt.get(name, {})
            require(isinstance(fact, dict) and fact.get("executed") is True and fact.get("status") == "PASS", "ADOPT-NOW lacks executed " + name)
            text(fact.get("command"), "receipt." + name + ".command")
        text(receipt.get("inverse", {}).get("command"), "receipt.inverse.command")
        clients = receipt.get("native_clients", [])
        require(isinstance(clients, list) and {c.get("client") for c in clients if isinstance(c, dict) and c.get("executed") is True and c.get("status") == "PASS"} >= {"claude", "codex"},
                "ADOPT-NOW lacks passing native routing in both clients")


def closure_omissions(omissions, index):
    approved, unresolved = [], []
    for omission in omissions:
        if not isinstance(omission, dict):
            unresolved.append(omission)
            continue
        closed(omission, {"code", "count", "cc_disposition_id", "follow_up_id", "resolution"}, set(POPULATION_FACTS), "closure omission")
        require(type(omission["count"]) is int and omission["count"] >= 0, "omission count must be a measured nonnegative integer")
        text(omission["resolution"], "omission resolution")
        code = text(omission["code"], "omission code")
        if (not isinstance(omission["cc_disposition_id"], str) or not omission["cc_disposition_id"].strip()
                or OMISSION_FOLLOW_UPS.get(code) != omission["follow_up_id"]):
            unresolved.append(omission)
            continue
        if code == "missing-list-capture":
            require(set(POPULATION_FACTS) <= omission.keys(), "missing list capture omission must retain its source reference")
            canonical(omission["source_repository"])
            failures = []
            validate_pin(omission["pin"], "missing population", failures)
            require(not failures and canonical(omission["pin"]["repository_or_source"]) == canonical(omission["source_repository"]), "missing list capture must retain its snapshot pin")
            text(omission["path"], "missing list path")
            text(omission["parser"], "missing list parser")
            sha(omission["capture_sha256"], "missing list capture hash")
            member_name(omission["archive_member"])
            require(omission["archive_member"] not in index, "missing-list-capture omission must identify an absent capture")
        approved.append(omission)
    return approved, unresolved


def counted_population(population, index, captures, cache, blockers):
    counted = population["counted"]
    closed(counted, set(COUNT_UNITS) - {"unpromoted_entries"} | {"promotion_rule", "unpromoted_ids"}, {"alias_witness"}, "counted population")
    for name in set(COUNT_UNITS) - {"unpromoted_entries"}:
        require(type(counted[name]) is int and counted[name] >= 0, "counted " + name + " must be a nonnegative integer")
    text(counted["promotion_rule"], "promotion rule")
    require(counted["promoted_entries"] == len({item.get("physical_occurrence_id", item["occurrence_id"]) for item in population["expected_occurrences"]}), "promoted count differs from physical promoted occurrence census")
    for name in ("duplicates_removed", "overlap_stars", "overlap_fields", "promoted_entries"):
        require(counted[name] <= counted["physical_entries"], "counted " + name + " exceeds physical entries")
    ids = declared_witness(counted["unpromoted_ids"], index, captures, cache, blockers, "unpromoted-list-id-witness")
    if ids is not None:
        require(isinstance(ids, list) and all(isinstance(value, str) and value.strip() for value in ids), "unpromoted list ids must be an untyped string array")
        require(len(ids) == len(set(ids)), "duplicate unpromoted list ids")
        require(counted["physical_entries"] == counted["promoted_entries"] + len(ids), "physical entries do not reconcile promoted and unpromoted ids")
    return ids


def counted_aliases(population, index, captures, cache, blockers):
    """Bind literal aliases to a physical source line through both original receipts."""
    witness = population["counted"].get("alias_witness")
    if witness is None:
        return {}
    original = declared_witness(witness, index, captures, cache, blockers, "physical-list-alias-witness")
    require(isinstance(original, dict) and original.get("status") == "FROZEN" and isinstance(original.get("aliases"), list), "alias witness must select a frozen alias array")
    result = {}
    for alias in original["aliases"]:
        closed(alias, {"occurrence_id", "physical_occurrence_id", "source_repository", "path", "line", "original_id", "archive_member", "capture_sha256", "pointer",
                       "physical_witness", "alias_collection_witness", "alias_occurrence_witness"}, set(), "physical list alias")
        for name in ("occurrence_id", "physical_occurrence_id", "source_repository", "path", "original_id", "pointer"):
            text(alias[name], "alias." + name)
        require(type(alias["line"]) is int and alias["line"] > 0, "alias source line must be a positive physical line number")
        match_capture(alias["archive_member"], alias["capture_sha256"], index)
        require(alias["physical_occurrence_id"] == alias["original_id"], "physical alias id must retain the exact original source id")
        parts = alias["original_id"].rsplit(":", 2)
        require(len(parts) == 3 and canonical(parts[0]) == canonical(population["source_repository"]) == canonical(alias["source_repository"])
                and parts[1] == population["path"] == alias["path"] and parts[2] == str(alias["line"]), "physical alias id differs from its source repository/path/line")
        physical = declared_witness(alias["physical_witness"], index, captures, cache, blockers, "original-physical-occurrence-witness")
        collection = declared_witness(alias["alias_collection_witness"], index, captures, cache, blockers, "original-alias-collection-witness")
        record = declared_witness(alias["alias_occurrence_witness"], index, captures, cache, blockers, "original-alias-occurrence-witness")
        require(isinstance(physical, dict) and isinstance(collection, dict) and isinstance(record, dict), "physical alias original receipts must select original objects")
        require(physical.get("occurrence_id") == alias["original_id"] and physical.get("original_ledger_input_id") == alias["original_id"]
                and canonical(physical.get("source_repository")) == canonical(alias["source_repository"])
                and physical.get("source_path") == alias["path"] and physical.get("source_line") == alias["line"]
                and physical.get("source_pin") == population["pin"]["version_or_commit"]
                and physical.get("source_content_sha256") == population["capture_sha256"], "original physical occurrence differs from its declared source identity/pin/capture")
        match_capture(physical.get("archive_member"), physical["source_content_sha256"], index)
        collection_pin = collection.get("pin")
        if isinstance(collection_pin, dict):
            require(canonical(collection_pin["repository_or_source"]) == canonical(alias["source_repository"]), "alias collection pin names a different source repository")
            collection_pin = collection_pin["version_or_commit"]
        require(canonical(collection.get("source_repository")) == canonical(alias["source_repository"])
                and collection.get("file") == alias["path"] and collection_pin == population["pin"]["version_or_commit"], "original alias collection differs from its source repository/path/pin")
        collection_ref, occurrence_ref = alias["alias_collection_witness"], alias["alias_occurrence_witness"]
        require(collection_ref["archive_member"] == occurrence_ref["archive_member"] and collection_ref["sha256"] == occurrence_ref["sha256"], "alias collection and occurrence must come from the same original receipt")
        relative_pointer = occurrence_ref["pointer"].removeprefix(collection_ref["pointer"])
        require(occurrence_ref["pointer"].startswith(collection_ref["pointer"] + "/occurrences/") and re.fullmatch(r"/occurrences/(?:0|[1-9][0-9]*)", relative_pointer)
                and pointer(collection, relative_pointer) == record, "alias occurrence is not the selected original collection member")
        require(record.get("occurrence_id") == alias["occurrence_id"] and record.get("source_line") == alias["line"]
                and all(record.get(name) == alias[name] for name in ("archive_member", "capture_sha256", "pointer")), "original alias occurrence differs from its literal id/source line/captured representation")
        candidate, slot = canonical(record.get("entry")), text(record.get("slot"), "original alias slot")
        targets = physical.get("linked_targets")
        require(isinstance(targets, list) and any(isinstance(target, dict) and isinstance(target.get("repository"), str)
                and canonical(target["repository"]) == candidate and github_repository_href(target.get("url")) == candidate for target in targets), "alias candidate is not an exact original physical source link")
        require(population["archive_member"] in captures, "physical alias source Markdown bytes are unavailable")
        try:
            primary_lines = captures[population["archive_member"]].decode("utf-8").split("\n")
        except UnicodeError as error:
            raise CompactError("physical alias source Markdown is not UTF-8") from error
        require(alias["line"] <= len(primary_lines), "physical alias source line is absent from its original Markdown")
        links = set()
        for match in re.finditer(r"(?<!!)\[[^\]\r\n]*\]\((https://github\.com/[^\s)]+)\)", primary_lines[alias["line"] - 1], re.I):
            try:
                links.add(github_repository_href(match[1]))
            except CompactError:
                continue
        require(candidate in links, "physical alias original Markdown line does not contain the exact candidate repository link")
        alias_key = (alias["occurrence_id"], alias["physical_occurrence_id"], alias["archive_member"], alias["capture_sha256"], alias["pointer"])
        require(alias_key not in result, "duplicate physical alias captured representation")
        result[alias_key] = {"linked_repository": candidate, "layer_fit": slot}
    return result


def validate_coverage(coverage, rows, index, captures, cache, profile=None):
    start_closure = validation_profile(profile)
    closed(coverage, {"schema_version", "status", "expected_keys", "starred_identities", "list_populations", "omissions"},
           {"source_inventory", "source_inventory_witness", "field_inventory_witness", "star_inventory_witness", "note"}
           | ({"document_inventory_witness"} if start_closure else set()), "coverage")
    require(type(coverage["schema_version"]) is int and coverage["schema_version"] == 1, "invalid coverage schema version")
    require(coverage["status"] in {"FROZEN", "INCOMPLETE"}, "coverage status must explicitly name frozen or incomplete union")
    require(isinstance(coverage["expected_keys"], list) and isinstance(coverage["omissions"], list), "coverage census/omissions must be arrays")
    expected = [key(value) for value in coverage["expected_keys"]]
    require(len(set(expected)) == len(expected), "coverage expected keys contain duplicates")
    actual = {decision_key(row): row for row in rows}
    blockers = []
    if set(expected) != set(actual):
        blockers.append({"code": "row-census-mismatch", "missing": len(set(expected) - set(actual)), "unexpected": len(set(actual) - set(expected))})
    if coverage["status"] != "FROZEN":
        blockers.append({"code": "complete-list-union-not-frozen"})
    approved_omissions = []
    unresolved_omissions = coverage["omissions"]
    if start_closure:
        approved_omissions, unresolved_omissions = closure_omissions(coverage["omissions"], index)
    if unresolved_omissions:
        blockers.append({"code": "declared-omissions", "count": len(unresolved_omissions)})
    inventory = declared_witness(coverage.get("source_inventory_witness"), index, captures, cache, blockers, "frozen-source-inventory-witness")
    field_inventory = declared_witness(coverage.get("field_inventory_witness"), index, captures, cache, blockers, "frozen-field-inventory-witness")
    allowed_fields = set()
    if isinstance(field_inventory, dict) and field_inventory.get("status") == "FROZEN" and isinstance(field_inventory.get("fields"), list):
        for field in field_inventory["fields"]:
            closed(field, {"slot", "catalog"}, set(), "field selector")
            require(SLOT.fullmatch(text(field["slot"], "field slot")) and field["slot"] != "UNKNOWN", "field inventory contains unknown selector")
            allowed_fields.add((field["slot"], text(field["catalog"], "field catalog")))
        if len(allowed_fields) != 45 or len(field_inventory["fields"]) != 45:
            blockers.append({"code": "field-inventory-not-45"})
        for row in rows:
            if row["slot"] == "out-of-scope" and row["disposition"] == "OUT-OF-SCOPE":
                continue
            catalog = row.get("qualification", {}).get("catalog")
            if not any(slot == row["slot"] and (catalog is None or catalog == cat) for slot, cat in allowed_fields):
                blockers.append({"code": "unbound-field-selector", "repository_or_entry": canonical(row["repository_or_entry"]), "slot": row["slot"]})
    elif field_inventory is not None:
        blockers.append({"code": "field-inventory-unfrozen-or-unsupported"})
    document_count = 0
    if start_closure and "document_inventory_witness" in coverage:
        documents = declared_witness(coverage["document_inventory_witness"], index, captures, cache, blockers, "frozen-document-inventory-witness")
        if isinstance(documents, dict) and documents.get("status") == "FROZEN" and isinstance(documents.get("documents"), list):
            paths, members = set(), set()
            document_count = len(documents["documents"])
            for document in documents["documents"]:
                closed(document, {"path", "archive_member", "sha256"}, {"source_reference"}, "document inventory item")
                member_name(document["path"])
                match_capture(document["archive_member"], document["sha256"], index)
                paths.add(document["path"])
                members.add(document["archive_member"])
                if "source_reference" in document:
                    text(document["source_reference"], "document source reference")
            if document_count != 2 or len(paths) != 2 or len(members) != 2:
                blockers.append({"code": "document-inventory-not-2-or-unretained"})
        elif documents is not None:
            blockers.append({"code": "document-inventory-unfrozen-or-unsupported"})
    require(isinstance(coverage["starred_identities"], list), "starred identity census must be an array")
    stars = [canonical(value) for value in coverage["starred_identities"]]
    require(all(value.startswith("https://github.com/") for value in stars) and len(set(stars)) == len(stars), "starred census must contain unique GitHub identities")
    original_stars = declared_witness(coverage.get("star_inventory_witness"), index, captures, cache, blockers, "original-star-inventory-witness")
    if isinstance(original_stars, dict):
        original_stars = next((original_stars[name] for name in ("starred_identities", "repositories", "identities", "rows") if isinstance(original_stars.get(name), list)), None)
        if original_stars is None:
            blockers.append({"code": "unsupported-original-star-inventory"})
    if isinstance(original_stars, list):
        original_identities = []
        for item in original_stars:
            if isinstance(item, dict):
                item = next((item[name] for name in ("full_name", "repository", "repository_or_entry", "html_url", "url", "name") if isinstance(item.get(name), str)), None)
            if not isinstance(item, str):
                blockers.append({"code": "unsupported-original-star-identity"})
                continue
            original_identities.append(canonical(item))
        if len(original_identities) != 368 or len(set(original_identities)) != 368 or set(original_identities) != set(stars):
            blockers.append({"code": "original-star-census-unbound-or-mismatched"})
    elif original_stars is not None:
        blockers.append({"code": "unsupported-original-star-inventory"})
    if len(stars) != 368:
        blockers.append({"code": "star-census-not-368", "count": len(stars)})
    missing_stars = set(stars) - {decision_key(row)[0] for row in rows}
    if missing_stars:
        blockers.append({"code": "undispositioned-stars", "count": len(missing_stars)})
    populations = coverage["list_populations"]
    require(isinstance(populations, list), "list_populations must be an array")
    if not populations:
        blockers.append({"code": "no-mined-list-population-census"})
    occurrence_keys, physical_occurrence_keys, occurrence_mappings, unpromoted_keys, summary = set(), set(), set(), set(), []
    occurrence_bindings = {}
    occurrence_physical_ids, physical_population_bindings, verified_alias_ids = {}, {}, set()
    physical_alias_count = 0
    retained_ids = set()
    counted_lists = counted_census_witnesses = 0
    retained_count = 0
    ref_map = {}
    for row in rows:
        for ref in row.get("source_refs", []):
            if "occurrence_id" in ref:
                ref_key = (ref["occurrence_id"], decision_key(row)) if start_closure else ref["occurrence_id"]
                require(ref_key not in ref_map, "duplicate retained occurrence_id" + (" and decision mapping" if start_closure else ""))
                ref_map[ref_key] = (decision_key(row), ref)
    for population in populations:
        closed(population, {"source_repository", "pin", "path", "capture_sha256", "archive_member", "parser", "expected_occurrences"},
               {"source_witness", "census_witness"} | ({"counted"} if start_closure else set()), "list population")
        canonical(population["source_repository"])
        pin_blockers = []
        validate_pin(population["pin"], "population", pin_blockers)
        blockers.extend({"code": code, "population": population["archive_member"]} for code in pin_blockers)
        if population["pin"] is not None:
            require(canonical(population["pin"]["repository_or_source"]) == canonical(population["source_repository"]), "list population pin names a different source repository")
        text(population["path"], "population.path")
        text(population["parser"], "population.parser")
        match_capture(population["archive_member"], population["capture_sha256"], index)
        require(isinstance(population["expected_occurrences"], list), "expected_occurrences must retain physical entry witnesses")
        source_witness = declared_witness(population.get("source_witness"), index, captures, cache, blockers, "pinned-list-source-witness")
        if source_witness is not None and (not isinstance(source_witness, dict) or any(source_witness.get(name) != population[name] for name in ("source_repository", "pin", "path", "capture_sha256"))):
            blockers.append({"code": "pinned-list-source-witness-mismatch", "population": population["archive_member"]})
        census = declared_witness(population.get("census_witness"), index, captures, cache, blockers, "original-list-census-witness")
        counted = start_closure and "counted" in population
        if census is not None and (not isinstance(census, dict) or census.get("status") not in ({"FROZEN", "COUNTED"} if counted else {"FROZEN"})
                                   or census.get("expected_occurrences") != population["expected_occurrences"]
                                   or counted and census.get("counted") != population["counted"]):
            blockers.append({"code": "original-list-census-unfrozen-or-mismatched", "population": population["archive_member"]})
        aliases = {}
        if counted:
            counted_lists += 1
            counted_census_witnesses += isinstance(census, dict) and census.get("status") == "COUNTED"
            ids = counted_population(population, index, captures, cache, blockers)
            aliases = counted_aliases(population, index, captures, cache, blockers)
            physical_alias_count += len(aliases)
            if ids is not None:
                require(not set(ids) & unpromoted_keys, "duplicate unpromoted occurrence id across populations")
                unpromoted_keys.update(ids)
        for occurrence in population["expected_occurrences"]:
            closed(occurrence, {"occurrence_id", "repository_or_entry", "slot", "capture_sha256", "archive_member", "pointer"},
                   {"qualification"} | ({"physical_occurrence_id"} if start_closure else set()), "list occurrence")
            occurrence_id = text(occurrence["occurrence_id"], "occurrence_id")
            physical_id = text(occurrence.get("physical_occurrence_id", occurrence_id), "physical_occurrence_id")
            require(counted or physical_id == occurrence_id, "physical occurrence aliases require a counted population")
            occurrence_key = decision_key(occurrence)
            occurrence_mapping = (occurrence_id, occurrence_key)
            if start_closure:
                require(occurrence_mapping not in occurrence_mappings, "duplicate promoted occurrence decision mapping")
            source_binding = tuple(json.dumps(population[name], sort_keys=True) for name in POPULATION_FACTS)
            binding = source_binding + tuple(occurrence[name] for name in ("archive_member", "capture_sha256", "pointer"))
            alias_key = (occurrence_id, physical_id, occurrence["archive_member"], occurrence["capture_sha256"], occurrence["pointer"])
            if physical_id != occurrence_id:
                proof = aliases.get(alias_key)
                require(proof is not None, "physical occurrence alias lacks its exact original receipt proof")
                require(canonical(proof["linked_repository"]) == occurrence_key[0] and proof["layer_fit"] == occurrence_key[1], "physical alias original candidate/slot differs from its retained decision key")
                cache[("native-entry-bound", occurrence_key, occurrence["archive_member"], occurrence["capture_sha256"], occurrence["pointer"])] = proof
                verified_alias_ids.add(occurrence_id)
            if occurrence_id in occurrence_keys:
                require(counted and occurrence_physical_ids[occurrence_id] == physical_id
                        and (occurrence_bindings[occurrence_id] == binding or physical_id != occurrence_id and occurrence_id in verified_alias_ids), "duplicate list occurrence census ID")
            if physical_id in physical_occurrence_keys:
                require(counted and physical_population_bindings[physical_id] == source_binding, "physical occurrence belongs to conflicting source populations")
            occurrence_keys.add(occurrence_id)
            physical_occurrence_keys.add(physical_id)
            occurrence_mappings.add(occurrence_mapping)
            occurrence_bindings[occurrence_id] = binding
            occurrence_physical_ids[occurrence_id] = physical_id
            physical_population_bindings[physical_id] = source_binding
            match_capture(occurrence["archive_member"], occurrence["capture_sha256"], index)
            text(occurrence["pointer"], "occurrence.pointer")
            original = selected_capture(occurrence["archive_member"], occurrence["pointer"], captures, cache, blockers, occurrence_id)
            if original is not None:
                if isinstance(original, dict) and {"repository_or_entry", "slot"} <= original.keys():
                    if decision_key(original) != occurrence_key:
                        blockers.append({"code": "original-list-occurrence-identity-scope-mismatch", "occurrence_id": occurrence_id})
                elif ("native-entry-bound", occurrence_key, occurrence["archive_member"], occurrence["capture_sha256"], occurrence["pointer"]) in cache:
                    # An exact native TSV record already bound against its pinned Markdown;
                    # qualification still comes from the separate frozen field inventory.
                    native = cache[("native-entry-bound", occurrence_key, occurrence["archive_member"], occurrence["capture_sha256"], occurrence["pointer"])]
                    if canonical(native["linked_repository"]) != occurrence_key[0] or native["layer_fit"] != occurrence_key[1]:
                        blockers.append({"code": "original-list-occurrence-identity-scope-mismatch", "occurrence_id": occurrence_id})
                else:
                    blockers.append({"code": "original-list-occurrence-scope-unverified", "occurrence_id": occurrence_id})
            actual_ref = ref_map.get(occurrence_mapping if start_closure else occurrence_id)
            if actual_ref is None or actual_ref[0] != occurrence_key or any(actual_ref[1].get(name) != occurrence[source] for name, source in
                    (("sha256", "capture_sha256"), ("archive_member", "archive_member"), ("pointer", "pointer"))):
                blockers.append({"code": "unretained-list-occurrence", "occurrence_id": occurrence_id})
            else:
                retained_count += 1
                retained_ids.add(physical_id)
        summary.append({name: population[name] for name in ("source_repository", "pin", "path", "capture_sha256", "archive_member", "parser", "source_witness", "census_witness") if name in population} |
                       {"expected_occurrences": len(population["expected_occurrences"])})
        if counted:
            summary[-1]["counted"] = population["counted"] | {"unpromoted_entries": population["counted"]["physical_entries"] - population["counted"]["promoted_entries"]}
            summary[-1]["promoted_mappings"] = len(population["expected_occurrences"])
            summary[-1]["expected_occurrences"] = population["counted"]["promoted_entries"]
    def population_fact(value):
        return {name: value[name] for name in ("source_repository", "pin", "path", "capture_sha256", "archive_member", "parser")}
    if inventory is not None:
        inventory_populations = populations + [omission for omission in approved_omissions if omission["code"] == "missing-list-capture"]
        if (not isinstance(inventory, dict) or inventory.get("status") != "FROZEN" or not isinstance(inventory.get("list_populations"), list)
                 or sorted((population_fact(p) for p in inventory["list_populations"]), key=lambda p: json.dumps(p, sort_keys=True))
                 != sorted((population_fact(p) for p in inventory_populations), key=lambda p: json.dumps(p, sort_keys=True))):
            blockers.append({"code": "source-inventory-unfrozen-or-population-mismatch"})
    extra = set(ref_map) - (occurrence_mappings if start_closure else occurrence_keys)
    if extra:
        blockers.append({"code": "occurrences-outside-declared-union", "count": len(extra)})
    require(not physical_occurrence_keys & unpromoted_keys, "an occurrence cannot be both promoted and unpromoted")
    coverage_summary = {"status": coverage["status"], "omissions": coverage["omissions"], "list_populations": summary}
    coverage_summary.update({name: coverage[name] for name in ("source_inventory_witness", "field_inventory_witness", "star_inventory_witness") if name in coverage})
    counts = {
        "expected_rows": len(expected), "starred_identities": len(stars), "represented_stars": len(stars) - len(missing_stars),
        "list_populations": len(populations), "expected_occurrences": len(occurrence_keys),
        "retained_occurrences": retained_count}
    if start_closure:
        counts["expected_occurrences"] = len(physical_occurrence_keys)
        counts["literal_promoted_occurrences"] = len(occurrence_keys)
        counts["physical_aliases"] = physical_alias_count
        counts["promoted_mappings"] = len(occurrence_mappings)
        counts["retained_mappings"] = retained_count
        counts["retained_occurrences"] = len(retained_ids)
        coverage_summary["count_units"] = COUNT_UNITS | {"promoted_mappings": "distinct literal occurrence id to retained decision key mappings; one physical entry may have several mappings",
                                                        "physical_aliases": "exact literal id/captured representation aliases verified against both original receipts"}
        if "document_inventory_witness" in coverage:
            coverage_summary["document_inventory_witness"] = coverage["document_inventory_witness"]
            counts["documents"] = document_count
        counts.update({"counted_list_populations": counted_lists, "counted_census_witnesses": counted_census_witnesses,
                       "unpromoted_list_occurrences": len(unpromoted_keys),
                       "approved_omissions": len(approved_omissions), "approved_omissions_by_follow_up": dict(sorted(Counter(o["follow_up_id"] for o in approved_omissions).items())),
                       "missing_list_captures": sum(o["code"] == "missing-list-capture" for o in approved_omissions),
                       "missing_list_capture_entries": sum(o["count"] for o in approved_omissions if o["code"] == "missing-list-capture")})
    return blockers, coverage_summary, counts


def row_list(raw):
    data = load(raw)
    if isinstance(data, dict):
        closed(data, {"rows"}, set(), "rows envelope")
        data = data["rows"]
    require(isinstance(data, list) and bool(data), "asset must retain a nonempty rows array")
    return data


def normalized_rows(rows):
    # Sorting is explicit: native json_text intentionally preserves insertion order.
    return sorted([{**row, "repository_or_entry": canonical(row["repository_or_entry"]),
                    "qualification": qualification(row.get("qualification", {}))} for row in rows], key=decision_key)


def sorted_tree(value):
    if isinstance(value, dict):
        return {key: sorted_tree(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [sorted_tree(item) for item in value]
    return value


def build_manifest(asset, release_tag, witnesses=(), profile=None):
    start_closure = validation_profile(profile)
    require(release_tag == "v2026.10.08", "G5 release tag must be v2026.10.08; this binds a planned release without claiming publication")
    asset = Path(asset)
    asset_sha, index, captured = read_archive(asset)
    require(ROWS_MEMBER in captured and COVERAGE_MEMBER in captured, "asset requires compact/rows.json and compact/coverage.json")
    rows = row_list(captured[ROWS_MEMBER])
    all_keys = [decision_key(row) for row in rows]
    require(len(set(all_keys)) == len(all_keys), "duplicate canonical identity+slot+qualification decision key")
    blockers = []
    for row in rows:
        blockers.extend({"code": code, "repository_or_entry": decision_key(row)[0], "slot": row["slot"],
                         "qualification": qualification(row.get("qualification", {}))} for code in validate_row(row, index, profile))
    rows = normalized_rows(rows)
    if witnesses:
        witness_rows = [row for witness in witnesses for row in row_list(Path(witness).read_bytes())]
        require(normalized_rows(witness_rows) == rows, "local --rows witness union differs from retained asset rows")
    coverage_raw = load(captured[COVERAGE_MEMBER])
    wanted = {row["acceptance_witness"]["archive_member"] for row in rows if "acceptance_witness" in row}
    wanted |= {row["archive_member"] for row in rows if "source_pointer" in row or "source_entry_witness" in row}
    wanted |= {row["source_entry_witness"]["archive_member"] for row in rows if "source_entry_witness" in row}
    wanted |= {ref["archive_member"] for row in rows for ref in row.get("source_refs", []) if "archive_member" in ref}
    wanted |= {ref["archive_member"] for row in rows for choice in row.get("choices", []) for ref in choice["source_refs"] if "archive_member" in ref}
    wanted |= {source["archive_member"] for row in rows for source in row["primary_sources"] if "pointer" in source and "archive_member" in source}
    wanted |= {source["archive_member"] for row in rows if NATIVE_SKILL_REF.fullmatch(row["repository_or_entry"]) for source in row["primary_sources"] if "archive_member" in source}
    if start_closure:
        wanted |= {ref["archive_member"] for row in rows for item in row.get("closure", {}).get("disagreements", []) for ref in item["evidence_refs"] if "archive_member" in ref}
        wanted |= {row["origin_pointer"]["archive_member"] for row in rows if isinstance(row.get("origin_pointer"), dict)}
    if isinstance(coverage_raw, dict):
        wanted |= {coverage_raw[name]["archive_member"] for name in ("source_inventory_witness", "field_inventory_witness", "star_inventory_witness") if isinstance(coverage_raw.get(name), dict) and "archive_member" in coverage_raw[name]}
        if start_closure and isinstance(coverage_raw.get("document_inventory_witness"), dict):
            wanted.add(coverage_raw["document_inventory_witness"]["archive_member"])
        for population in coverage_raw.get("list_populations", []):
            wanted |= {o["archive_member"] for o in population.get("expected_occurrences", [])}
            wanted |= {population[name]["archive_member"] for name in ("source_witness", "census_witness") if isinstance(population.get(name), dict) and "archive_member" in population[name]}
            if start_closure and isinstance(population.get("counted", {}).get("unpromoted_ids"), dict):
                wanted.add(population["counted"]["unpromoted_ids"]["archive_member"])
            if start_closure and isinstance(population.get("counted", {}).get("alias_witness"), dict):
                wanted.add(population["counted"]["alias_witness"]["archive_member"])
                wanted.add(population["archive_member"])
    receipts = {}
    if wanted:
        second_sha, second_index, receipts = read_archive(asset, wanted)
        require(second_sha == asset_sha and second_index == index, "asset changed before acceptance-witness check")
        for row in rows:
            validate_acceptance(row, receipts)
    if start_closure:
        alias_members, alias_cache = set(), {}
        for population in coverage_raw.get("list_populations", []):
            alias_ref = population.get("counted", {}).get("alias_witness")
            if alias_ref is None:
                continue
            alias_body = declared_witness(alias_ref, index, receipts, alias_cache, blockers, "physical-list-alias-witness")
            require(isinstance(alias_body, dict) and isinstance(alias_body.get("aliases"), list), "alias witness must select an alias array")
            for alias in alias_body["aliases"]:
                for name in ("physical_witness", "alias_collection_witness", "alias_occurrence_witness"):
                    ref = alias.get(name)
                    closed(ref, {"archive_member", "sha256", "pointer"}, set(), "alias original receipt reference")
                    match_capture(ref["archive_member"], ref["sha256"], index)
                    alias_members.add(ref["archive_member"])
        if alias_members - receipts.keys():
            alias_sha, alias_index, alias_captures = read_archive(asset, alias_members)
            require(alias_sha == asset_sha and alias_index == index, "asset changed before original alias receipt check")
            receipts.update(alias_captures)
    cache = {}
    validate_reference_pointers(rows, receipts, blockers, cache)
    if start_closure:
        for row in rows:
            validate_origin_pointer(row, receipts, cache, blockers)
            validate_origin_claims(row, receipts, cache, blockers)
    for row in rows:
        validate_native_source_entry(row, index, receipts, cache, blockers)
        validate_native_skill_entry(row, index, receipts, cache, blockers)
    coverage_blockers, coverage, counts = validate_coverage(coverage_raw, rows, index, receipts, cache, profile)
    blockers.extend(coverage_blockers)
    counts.update({"rows": len(rows), "identities": len({decision_key(row)[0] for row in rows}),
                   "pending_measurements": sum(row["disposition"] == "PENDING" for row in rows),
                   "by_disposition": dict(sorted(Counter(row["disposition"] for row in rows).items())),
                   "by_evidence_class": dict(sorted(Counter(row["evidence_class"] for row in rows).items())),
                   "by_pin_subject": dict(sorted(Counter(row["pin"]["subject"] if row["pin"] else "UNKNOWN" for row in rows).items())),
                   "candidate_implementation_unestablished": sum(row.get("candidate_implementation_status") == "UNESTABLISHED" for row in rows),
                   "by_slot": dict(sorted(Counter(row["slot"] for row in rows).items())),
                   "by_qualification": dict(sorted(Counter(decision_key(row)[2] for row in rows).items())),
                   "by_owner_lane": dict(sorted(Counter(row["owner_lane"] for row in rows).items()))})
    row_schema = START_ROW_SCHEMA if start_closure else SCHEMA
    coverage_schema = START_COVERAGE_SCHEMA if start_closure else COVERAGE_SCHEMA
    manifest = {"schema_version": 1, "kind": "g5-compact-landscape", "release_tag": release_tag,
                "row_schema": {"path": str(row_schema.relative_to(REPO)), "sha256": hashlib.sha256(row_schema.read_bytes()).hexdigest()},
                "coverage_schema": {"path": str(coverage_schema.relative_to(REPO)), "sha256": hashlib.sha256(coverage_schema.read_bytes()).hexdigest()},
                "asset": {"name": asset.name, "format": "tar.zst", "sha256": asset_sha, "bytes": asset.stat().st_size,
                          "rows_member": ROWS_MEMBER, "rows_sha256": index[ROWS_MEMBER]["sha256"],
                          "coverage_member": COVERAGE_MEMBER, "coverage_sha256": index[COVERAGE_MEMBER]["sha256"]},
                "coverage": coverage, "counts": counts,
                "validation": {"status": "BLOCKED" if blockers else "PASS", "blockers": blockers,
                               "contract": "Byte integrity and declared census consistency only; parser names are provenance, not executed coverage research. Recorded execution receipts remain historical; no vendor/native test or install runs here. Open measured-case proposals remain open, not missing coverage."},
                "rows": rows}
    if start_closure:
        disagreements = [item | {"repository_or_entry": row["repository_or_entry"], "slot": row["slot"]}
                         for row in rows for item in row.get("closure", {}).get("disagreements", [])]
        require(len({item["id"] for item in disagreements}) == len(disagreements), "duplicate declared disagreement id")
        for row in rows:
            for item in row.get("closure", {}).get("disagreements", []):
                for ref in item["evidence_refs"]:
                    if "archive_member" in ref:
                        selected_capture(ref["archive_member"], ref["pointer"], receipts, cache, blockers, item["id"])
        residue_counts = {}
        for name in ("pending_pin", "pending_locator"):
            residue_counts[name + "_rows"] = sum(name in row.get("closure", {}) for row in rows)
            residue_counts[name + "_by_reason"] = dict(sorted(Counter(row["closure"][name]["reason_code"] for row in rows if name in row.get("closure", {})).items()))
        pin_items = Counter()
        for row in rows:
            if "pending_pin" in row.get("closure", {}):
                pin_items[row["closure"]["pending_pin"]["reason_code"]] += (row["pin"] is None) + sum(source["pin"] is None for source in row["primary_sources"])
        residue_counts["pending_pin_items_by_reason"] = dict(sorted(pin_items.items()))
        residue_counts["pending_pin_items"] = sum(pin_items.values())
        locator_items = Counter()
        for row in rows:
            if "pending_locator" in row.get("closure", {}):
                for i, source in enumerate(row["primary_sources"]):
                    if closure_locator(source, f"primary[{i}].locator", row["closure"], []):
                        locator_items[row["closure"]["pending_locator"]["reason_code"]] += 1
        residue_counts["pending_locator_items_by_reason"] = dict(sorted(locator_items.items()))
        residue_counts["pending_locator_items"] = sum(locator_items.values())
        residue_counts.update({name: counts[name] for name in ("counted_list_populations", "counted_census_witnesses", "unpromoted_list_occurrences", "approved_omissions", "approved_omissions_by_follow_up", "missing_list_captures", "missing_list_capture_entries")})
        residue_counts["pending_disagreements"] = sum(item["status"] == "PENDING" for item in disagreements)
        residue_counts["pending_conflict_rows"] = sum("pending_conflict" in row.get("closure", {}) for row in rows)
        residue_counts["origin_pointer_unresolved_rows"] = sum(row.get("origin_pointer") == "unresolved" for row in rows)
        residue_counts["origin_pointer_unresolved_action_rows"] = sum(row.get("origin_pointer") == "unresolved" and row["disposition"] in ACTION_CLASSES for row in rows)
        unresolved_claims = {claim_id for row in rows for claim_id in row.get("origin_claim_ids", [])}
        unresolved_legacy_rows = sum(row.get("origin_pointer") == "unresolved" and not row.get("origin_claim_ids") for row in rows)
        residue_counts["origin_pointer_unresolved_claims"] = len(unresolved_claims)
        residue_counts["origin_pointer_unresolved_legacy_rows"] = unresolved_legacy_rows
        residue_counts["origin_pointer_unresolved"] = len(unresolved_claims) + unresolved_legacy_rows
        counts.update({"action_rows": sum(row["disposition"] in ACTION_CLASSES for row in rows),
                       "pending_conflict": residue_counts["pending_conflict_rows"],
                       "action_read_rows": sum(row["disposition"] in ACTION_CLASSES for row in rows) + residue_counts["pending_conflict_rows"],
                       "origin_pointer_unresolved": residue_counts["origin_pointer_unresolved"],
                       "origin_pointer_unresolved_rows": residue_counts["origin_pointer_unresolved_rows"],
                       "origin_pointer_unresolved_claims": len(unresolved_claims),
                       "origin_pointer_bound": sum(isinstance(row.get("origin_pointer"), dict) for row in rows),
                       "pinned_rows": sum(row["pin"] is not None for row in rows),
                       "pending_pin": residue_counts["pending_pin_rows"], "pending_locator": residue_counts["pending_locator_rows"],
                       "disagreements_resolved": sum(item["status"] == "RESOLVED" for item in disagreements), "disagreements_total": len(disagreements)})
        manifest["validation"].update({"profile": START_CLOSURE_PROFILE, "nonblocking_counts": residue_counts, "disagreements": disagreements,
                                       "status": "BLOCKED" if blockers else "PASS"})
        coverage["count_units"].update({"origin_pointer_unresolved": "distinct hash-bound original origin_claim_ids plus one legacy unit per unresolved row without declared claim ids",
                                        "origin_pointer_unresolved_rows": "retained decision rows with literal origin_pointer unresolved, including qualified keys sharing one original claim"})
    raw = json_text(sorted_tree(manifest), indent=2).encode("utf-8")
    require(len(raw) < MANIFEST_LIMIT, "compact manifest must remain below GitHub's 100 MiB regular-file limit")
    return manifest, raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", action="append", type=Path, default=[], help="optional equality witness; never used instead of asset-contained rows")
    parser.add_argument("--asset", required=True, type=Path)
    parser.add_argument("--release-tag", default="v2026.10.08")
    parser.add_argument("--profile", choices=[START_CLOSURE_PROFILE], default=None,
                        help="explicit versioned START closure contract; omission keeps the strict default unchanged")
    parser.add_argument("--manifest", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="atomically write rebuilt metadata, including explicit blocked/incomplete state")
    mode.add_argument("--check", action="store_true", help="compare existing metadata with an independent asset-only rebuild")
    args = parser.parse_args(argv)
    try:
        require(not args.manifest.is_symlink(), "manifest output must not be a symlink")
        require(args.manifest.resolve() != args.asset.resolve() and args.manifest.resolve() not in {p.resolve() for p in args.rows}, "manifest output overlaps immutable inputs")
        manifest, raw = build_manifest(args.asset, args.release_tag, args.rows, args.profile)
        if args.write:
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=args.manifest.parent, prefix=".compact-manifest-", delete=False) as output:
                    temporary = Path(output.name)
                    output.write(raw)
                temporary.replace(args.manifest)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        else:
            require(args.manifest.is_file() and args.manifest.read_bytes() == raw, "compact manifest differs from asset-only rebuild")
        print(json.dumps({"status": manifest["validation"]["status"], "counts": manifest["counts"],
                          "blockers": len(manifest["validation"]["blockers"]), "manifest_sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True))
        return 0 if manifest["validation"]["status"] == "PASS" else 1
    except (CompactError, OSError, KeyError, TypeError) as error:
        print("compact-manifest: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
