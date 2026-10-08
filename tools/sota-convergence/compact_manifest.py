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


def validate_row(row, index):
    closed(row, ROW_REQUIRED, ROW_OPTIONAL, "row")
    identity, slot, _ = decision_key(row)
    require(row["disposition"] in CLASSES and row["evidence_class"] in EVIDENCE, "unsupported disposition/evidence class")
    blockers = []
    if slot == "UNKNOWN":
        blockers.append("unknown-field-scope")
    if row["evidence_class"] == "UNKNOWN":
        blockers.append("unknown-evidence-class")
    validate_pin(row["pin"], "row", blockers)
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
    for i, source in enumerate(sources):
        closed(source, {"locator", "pin", "subject"}, {"capture_sha256", "archive_member", "pointer"}, "primary source")
        text(source["subject"], "primary source subject")
        validate_pin(source["pin"], f"primary[{i}]", blockers)
        validate_locator(source["locator"], source["pin"], f"primary[{i}].locator", blockers)
        require(("capture_sha256" in source) == ("archive_member" in source), "primary capture hash/member must be paired")
        if "archive_member" in source:
            match_capture(source["archive_member"], source["capture_sha256"], index)
        if "pointer" in source:
            require(isinstance(source["pointer"], str) and (source["pointer"] == "" or source["pointer"].startswith("/")), "primary pointer must be JSON Pointer")
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


def validate_coverage(coverage, rows, index, captures, cache):
    closed(coverage, {"schema_version", "status", "expected_keys", "starred_identities", "list_populations", "omissions"},
           {"source_inventory", "source_inventory_witness", "field_inventory_witness", "star_inventory_witness", "note"}, "coverage")
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
    if coverage["omissions"]:
        blockers.append({"code": "declared-omissions", "count": len(coverage["omissions"])})
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
    occurrence_keys, summary = set(), []
    retained_count = 0
    ref_map = {}
    for row in rows:
        for ref in row.get("source_refs", []):
            if "occurrence_id" in ref:
                require(ref["occurrence_id"] not in ref_map, "duplicate retained occurrence_id")
                ref_map[ref["occurrence_id"]] = (decision_key(row), ref)
    for population in populations:
        closed(population, {"source_repository", "pin", "path", "capture_sha256", "archive_member", "parser", "expected_occurrences"}, {"source_witness", "census_witness"}, "list population")
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
        if census is not None and (not isinstance(census, dict) or census.get("status") != "FROZEN" or census.get("expected_occurrences") != population["expected_occurrences"]):
            blockers.append({"code": "original-list-census-unfrozen-or-mismatched", "population": population["archive_member"]})
        for occurrence in population["expected_occurrences"]:
            closed(occurrence, {"occurrence_id", "repository_or_entry", "slot", "capture_sha256", "archive_member", "pointer"}, {"qualification"}, "list occurrence")
            occurrence_id = text(occurrence["occurrence_id"], "occurrence_id")
            require(occurrence_id not in occurrence_keys, "duplicate list occurrence census ID")
            occurrence_keys.add(occurrence_id)
            occurrence_key = decision_key(occurrence)
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
            actual_ref = ref_map.get(occurrence_id)
            if actual_ref is None or actual_ref[0] != occurrence_key or any(actual_ref[1].get(name) != occurrence[source] for name, source in
                    (("sha256", "capture_sha256"), ("archive_member", "archive_member"), ("pointer", "pointer"))):
                blockers.append({"code": "unretained-list-occurrence", "occurrence_id": occurrence_id})
            else:
                retained_count += 1
        summary.append({name: population[name] for name in ("source_repository", "pin", "path", "capture_sha256", "archive_member", "parser", "source_witness", "census_witness") if name in population} |
                       {"expected_occurrences": len(population["expected_occurrences"])})
    def population_fact(value):
        return {name: value[name] for name in ("source_repository", "pin", "path", "capture_sha256", "archive_member", "parser")}
    if inventory is not None:
        if (not isinstance(inventory, dict) or inventory.get("status") != "FROZEN" or not isinstance(inventory.get("list_populations"), list)
                or sorted((population_fact(p) for p in inventory["list_populations"]), key=lambda p: json.dumps(p, sort_keys=True))
                != sorted((population_fact(p) for p in populations), key=lambda p: json.dumps(p, sort_keys=True))):
            blockers.append({"code": "source-inventory-unfrozen-or-population-mismatch"})
    extra = set(ref_map) - occurrence_keys
    if extra:
        blockers.append({"code": "occurrences-outside-declared-union", "count": len(extra)})
    coverage_summary = {"status": coverage["status"], "omissions": coverage["omissions"], "list_populations": summary}
    coverage_summary.update({name: coverage[name] for name in ("source_inventory_witness", "field_inventory_witness", "star_inventory_witness") if name in coverage})
    return blockers, coverage_summary, {
        "expected_rows": len(expected), "starred_identities": len(stars), "represented_stars": len(stars) - len(missing_stars),
        "list_populations": len(populations), "expected_occurrences": len(occurrence_keys),
        "retained_occurrences": retained_count}


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


def build_manifest(asset, release_tag, witnesses=()):
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
                         "qualification": qualification(row.get("qualification", {}))} for code in validate_row(row, index))
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
    if isinstance(coverage_raw, dict):
        wanted |= {coverage_raw[name]["archive_member"] for name in ("source_inventory_witness", "field_inventory_witness", "star_inventory_witness") if isinstance(coverage_raw.get(name), dict) and "archive_member" in coverage_raw[name]}
        for population in coverage_raw.get("list_populations", []):
            wanted |= {o["archive_member"] for o in population.get("expected_occurrences", [])}
            wanted |= {population[name]["archive_member"] for name in ("source_witness", "census_witness") if isinstance(population.get(name), dict) and "archive_member" in population[name]}
    receipts = {}
    if wanted:
        second_sha, second_index, receipts = read_archive(asset, wanted)
        require(second_sha == asset_sha and second_index == index, "asset changed before acceptance-witness check")
        for row in rows:
            validate_acceptance(row, receipts)
    cache = {}
    validate_reference_pointers(rows, receipts, blockers, cache)
    for row in rows:
        validate_native_source_entry(row, index, receipts, cache, blockers)
        validate_native_skill_entry(row, index, receipts, cache, blockers)
    coverage_blockers, coverage, counts = validate_coverage(coverage_raw, rows, index, receipts, cache)
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
    manifest = {"schema_version": 1, "kind": "g5-compact-landscape", "release_tag": release_tag,
                "row_schema": {"path": "tools/sota-convergence/schemas/compact-decision.json", "sha256": hashlib.sha256(SCHEMA.read_bytes()).hexdigest()},
                "coverage_schema": {"path": "tools/sota-convergence/schemas/compact-coverage.json", "sha256": hashlib.sha256(COVERAGE_SCHEMA.read_bytes()).hexdigest()},
                "asset": {"name": asset.name, "format": "tar.zst", "sha256": asset_sha, "bytes": asset.stat().st_size,
                          "rows_member": ROWS_MEMBER, "rows_sha256": index[ROWS_MEMBER]["sha256"],
                          "coverage_member": COVERAGE_MEMBER, "coverage_sha256": index[COVERAGE_MEMBER]["sha256"]},
                "coverage": coverage, "counts": counts,
                "validation": {"status": "BLOCKED" if blockers else "PASS", "blockers": blockers,
                               "contract": "Byte integrity and declared census consistency only; parser names are provenance, not executed coverage research. Recorded execution receipts remain historical; no vendor/native test or install runs here. Open measured-case proposals remain open, not missing coverage."},
                "rows": rows}
    raw = json_text(sorted_tree(manifest), indent=2).encode("utf-8")
    require(len(raw) < MANIFEST_LIMIT, "compact manifest must remain below GitHub's 100 MiB regular-file limit")
    return manifest, raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", action="append", type=Path, default=[], help="optional equality witness; never used instead of asset-contained rows")
    parser.add_argument("--asset", required=True, type=Path)
    parser.add_argument("--release-tag", default="v2026.10.08")
    parser.add_argument("--manifest", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="atomically write rebuilt metadata, including explicit blocked/incomplete state")
    mode.add_argument("--check", action="store_true", help="compare existing metadata with an independent asset-only rebuild")
    args = parser.parse_args(argv)
    try:
        require(not args.manifest.is_symlink(), "manifest output must not be a symlink")
        require(args.manifest.resolve() != args.asset.resolve() and args.manifest.resolve() not in {p.resolve() for p in args.rows}, "manifest output overlaps immutable inputs")
        manifest, raw = build_manifest(args.asset, args.release_tag, args.rows)
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
