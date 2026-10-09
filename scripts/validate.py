#!/usr/bin/env python3
"""Validate published manifests and receipts without accounts or model calls.

This verifies evidence integrity and declared scope. It does not repeat the
historical native executions, prove arbitrary claims, or measure live savings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import zlib
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit


RECEIPT_KINDS = {
    "native_model_e2e", "native_cli_e2e", "artifact_measurement",
    "historical_inventory", "upstream_provenance", "compatibility_attempt",
}
PRIVATE_CONTENT = (
    # Historical prose can glue a UUID to a word; word boundaries miss it.
    ("local session identifier", re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)),
    ("local companion task handle", re.compile(r"task-[a-z0-9]{8}-[a-z0-9]{6}", re.I)),
    ("personal home path", re.compile(r"/(?:home|Users)/(?!example(?:/|\b))[A-Za-z0-9_.-]+(?:/|\b)")),
    ("Windows user path", re.compile(r"(?:[A-Za-z]:[/\\]+|/mnt/[A-Za-z]/)Users[/\\]+(?!example(?:[/\\]|\b))[A-Za-z0-9_.-]+", re.I)),
    # Claude project and scratchpad directories encode path separators as dashes,
    # including bare homes and Windows profiles reached through WSL mounts. The Users
    # branches ignore case (Windows and default macOS filesystems are case-insensitive);
    # Linux's /home stays case-sensitive, like the plain home-path rule above.
    ("encoded home path", re.compile(
        r"(?<![\w-])(?:-home-|(?i:-Users-|[A-Za-z]--Users-|-mnt-[A-Za-z]-Users-))"
        r"(?!example(?:-|[/\\\"'\s`)\]]|$))[A-Za-z0-9_.]+(?:-|(?=[/\\\"'\s`)\]]|$))"
        # Graph project IDs omit the leading dash. Every punctuation wrapper,
        # including '_' and '-', is a boundary; Unicode alphanumerics are not.
        # '<user>', '%u' and the complete 'example' placeholder remain exempt.
        r"|(?<![^\W_])home-(?!example-code-)[\w.]+(?:-+[\w.]+)*-*-code-")),
    ("Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{20,}\b")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    ("Tavily token", re.compile(r"\btvly-(?:(?:prod|dev)-)?[A-Za-z0-9_-]{24,}\b")),
    ("API secret", re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}\b")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("bearer credential", re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{30,}", re.I)),
)


class InvalidPublication(ValueError):
    """One or more manifest, integrity, or publication hygiene failures."""


MODEL_CURRENCY_PATH = "catalogs/foundation/model-currency.json"
MODEL_MAX_RELEASE_AGE_DAYS = 42
MODEL_MAX_LANDSCAPE_AGE_DAYS = 7


def model_currency_problems(document, today: date | None = None, *, enforce_age=True) -> list[str]:
    """Check the dated model inventory offline; package bindings use the latest package date."""
    today = today if today is not None else datetime.now(timezone.utc).date()
    errors = []
    if type(today) is not date:
        return ["model currency: today must be a date"]
    if not isinstance(document, dict) or type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        return ["model currency: expected schema_version 1 object"]

    def allowed_keys(value, allowed, label):
        if isinstance(value, dict):
            unknown = sorted(str(key) for key in value if key not in allowed)
            if unknown:
                errors.append(f"{label}: unknown fields: {', '.join(unknown)}")

    allowed_keys(document, {"schema_version", "inventory_status", "policy", "packages", "models"}, "model currency")

    def text(value, label):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label}: expected nonempty string")
            return False
        return True

    def parsed_date(value, label):
        try:
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError
            result = date.fromisoformat(value)
        except ValueError:
            errors.append(f"{label}: expected valid YYYY-MM-DD date")
            return None
        if result > today:
            errors.append(f"{label}: future date")
        return result

    def source(value, label):
        try:
            clean = isinstance(value, str) and not any(char.isspace() or ord(char) < 32 or 127 <= ord(char) <= 159 for char in value)
            parts = urlsplit(value) if clean else None
            valid = parts is not None and parts.scheme == "https" and bool(parts.hostname) and not parts.username and not parts.password
            if parts is not None:
                parts.port  # urlsplit parses lazily; malformed/out-of-range ports raise ValueError here.
        except ValueError:
            valid = False
        if not valid:
            errors.append(f"{label}: expected primary HTTPS source URL")

    def records(key):
        result = {}
        values = document.get(key)
        if not isinstance(values, list):
            errors.append(f"model currency {key}: expected array")
            return result
        for i, row in enumerate(values):
            label = f"model currency {key}[{i}]"
            if not isinstance(row, dict):
                errors.append(f"{label}: expected object")
                continue
            identifier = row.get("id")
            if text(identifier, f"{label}.id"):
                if identifier in result:
                    errors.append(f"{label}: duplicate id {identifier}")
                result[identifier] = row
        return result

    def release_line(value, label):
        if not isinstance(value, dict):
            errors.append(f"{label}: expected release line object")
            return
        kind = value.get("kind")
        if kind == "huggingface":
            allowed_keys(value, {"kind", "repository", "ref"}, label)
            text(value.get("repository"), f"{label}.repository")
            if value.get("ref") != "main":
                errors.append(f"{label}.ref: latest-line checks require the Hub default main branch, not a pinned revision or tag")
        elif kind == "github_release":
            allowed_keys(value, {"kind", "repository"}, label)
            if not isinstance(value.get("repository"), str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value["repository"]):
                errors.append(f"{label}.repository: expected owner/repository")
        elif kind == "pypi":
            allowed_keys(value, {"kind", "package"}, label)
            text(value.get("package"), f"{label}.package")
        elif kind == "vendor_page":
            allowed_keys(value, {"kind", "url"}, label)
            source(value.get("url"), f"{label}.url")
        else:
            errors.append(f"{label}: unsupported release line kind")

    if not isinstance(document.get("inventory_status"), str) or document["inventory_status"] not in {"pending", "complete"}:
        errors.append("model currency: inventory_status must be pending or complete")
    expected_policy = {"max_release_age_days": 42, "max_landscape_age_days": 7, "refresh_lead_days": 2}
    allowed_keys(document.get("policy"), set(expected_policy), "model currency policy")
    if document.get("policy") != expected_policy:
        errors.append("model currency: policy must retain the 42-day/7-day limits and 2-day refresh lead")
    packages = records("packages")
    package_dates = {}
    for identifier, package in packages.items():
        label = f"model currency package {identifier}"
        allowed_keys(package, {"id", "latest_version", "release_date", "release_source", "checked_at", "release_line"}, label)
        text(package.get("latest_version"), f"{label}.latest_version")
        package_dates[identifier] = parsed_date(package.get("release_date"), f"{label}.release_date")
        source(package.get("release_source"), f"{label}.release_source")
        parsed_date(package.get("checked_at"), f"{label}.checked_at")
        release_line(package.get("release_line"), f"{label}.release_line")
    models = records("models")
    if document.get("inventory_status") == "complete" and not models:
        errors.append("model currency: a complete inventory needs model rows")
    for identifier, model in models.items():
        label = f"model currency model {identifier}"
        allowed_keys(model, {"id", "role", "consumer", "model_id", "revision", "release_date", "release_source", "checked_at", "status", "release_line", "package", "landscape_check", "overturn"}, label)
        for field in ("role", "consumer", "model_id", "revision"):
            text(model.get(field), f"{label}.{field}")
        released = parsed_date(model.get("release_date"), f"{label}.release_date")
        source(model.get("release_source"), f"{label}.release_source")
        parsed_date(model.get("checked_at"), f"{label}.checked_at")
        status = model.get("status")
        if not isinstance(status, str) or status not in {"in_use", "held", "package_bound"}:
            errors.append(f"{label}: unsupported status")
        # Model identity and its exact origin remain independent of the shipping
        # package used below for age/release-line checks.
        origin = model.get("release_line")
        release_line(origin, f"{label}.release_line")
        if isinstance(origin, dict) and origin.get("kind") == "huggingface":
            if not isinstance(model.get("revision"), str) or not re.fullmatch(r"[0-9a-f]{40}", model["revision"]):
                errors.append(f"{label}.revision: expected exact Hugging Face commit SHA")
        if "package" in model:
            binding = model["package"]
            if not isinstance(binding, dict):
                errors.append(f"{label}.package: expected object")
            else:
                allowed_keys(binding, {"id", "version"}, f"{label}.package")
                text(binding.get("id"), f"{label}.package.id")
                text(binding.get("version"), f"{label}.package.version")
        effective_release = released
        if status == "package_bound":
            binding = model.get("package")
            package_id = binding.get("id") if isinstance(binding, dict) else None
            package = packages.get(package_id) if isinstance(package_id, str) else None
            if package is None:
                errors.append(f"{label}: package binding must join a package record")
            else:
                if binding.get("version") != package.get("latest_version"):
                    errors.append(f"{label}: package version does not follow the recorded latest release")
                effective_release = package_dates.get(package_id)
        landscape = model.get("landscape_check")
        reviewed = None
        if landscape is not None:
            if not isinstance(landscape, dict):
                errors.append(f"{label}.landscape_check: expected object")
            else:
                allowed_keys(landscape, {"date", "sources", "newer_candidates", "reason"}, f"{label}.landscape_check")
                reviewed = parsed_date(landscape.get("date"), f"{label}.landscape_check.date")
                sources = landscape.get("sources")
                if not isinstance(sources, list) or not sources:
                    errors.append(f"{label}.landscape_check.sources: expected nonempty source array")
                else:
                    for i, url in enumerate(sources):
                        source(url, f"{label}.landscape_check.sources[{i}]")
                candidates = landscape.get("newer_candidates")
                if not isinstance(candidates, list):
                    errors.append(f"{label}.landscape_check.newer_candidates: expected array")
                else:
                    for i, candidate in enumerate(candidates):
                        candidate_label = f"{label}.landscape_check.newer_candidates[{i}]"
                        if not isinstance(candidate, dict):
                            errors.append(f"{candidate_label}: expected object")
                            continue
                        allowed_keys(candidate, {"model_id", "revision", "source", "reason"}, candidate_label)
                        for field in ("model_id", "revision", "reason"):
                            text(candidate.get(field), f"{candidate_label}.{field}")
                        source(candidate.get("source"), f"{candidate_label}.source")
                text(landscape.get("reason"), f"{label}.landscape_check.reason")
                text(model.get("overturn"), f"{label}.overturn")
        if enforce_age and effective_release is not None and (today - effective_release).days > MODEL_MAX_RELEASE_AGE_DAYS:
            if reviewed is None or not 0 <= (today - reviewed).days <= MODEL_MAX_LANDSCAPE_AGE_DAYS:
                errors.append(f"{label}: release older than 42 days needs a sourced landscape check within 7 days")
    return errors


def _json_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def is_structural_png(content: bytes) -> bool:
    """Check PNG framing and checksums, not visual content or pixel decoding."""
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    offset, seen_header, seen_data = 8, False, False
    while offset + 12 <= len(content):
        size = int.from_bytes(content[offset:offset + 4], "big")
        kind = content[offset + 4:offset + 8]
        end = offset + 12 + size
        if end > len(content) or not re.fullmatch(b"[A-Za-z]{4}", kind):
            return False
        payload = content[offset + 8:end - 4]
        checksum = int.from_bytes(content[end - 4:end], "big")
        if zlib.crc32(kind + payload) != checksum:
            return False
        if not seen_header:
            if kind != b"IHDR" or size != 13:
                return False
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            depths = {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8}, 4: {8, 16}, 6: {8, 16}}
            if (not 0 < width < 2**31 or not 0 < height < 2**31
                    or depth not in depths.get(color, set())
                    or compression != 0 or filtering != 0 or interlace not in {0, 1}):
                return False
            seen_header = True
        elif kind == b"IHDR":
            return False
        if kind == b"IDAT":
            seen_data = True
        if kind == b"IEND":
            return size == 0 and seen_data and end == len(content)
        offset = end
    return False


def is_supported_pdf_framing(content: bytes) -> bool:
    """Recognize bounded classic, single-revision PDF framing only.

    This is not a PDF parser: streams, encoded names, text, attachments and
    active content are not decoded or certified safe by this check.
    """
    if not re.match(rb"%PDF-(?:1\.[0-7]|2\.0)[\r\n]", content):
        return False
    ending = re.search(rb"startxref\s+([0-9]{1,20})\s+%%EOF\s*\Z", content)
    if ending is None or content.count(b"%%EOF") != 1:
        return False
    offset = int(ending[1])
    if offset >= ending.start() or not content[offset:].startswith(b"xref"):
        return False
    trailer = content[offset:ending.start()]
    return (re.search(rb"\btrailer\s*<<", trailer) is not None
            and re.search(rb"/Root\s+[0-9]+\s+[0-9]+\s+R\b", trailer) is not None
            and re.search(rb"/(?:Encrypt|Prev)\b", content) is None)


def scan_file_for_private_content(path: Path, *, locations: list[int] | None = None) -> list[str]:
    """Scan one file's bytes for PRIVATE_CONTENT patterns directly.

    `Validator.scan_publication()` only inspects paths returned by
    `publication_paths()`, which is git-tracked-and-listed paths (or a
    filesystem walk for a non-Git archive root). A generated, gitignored
    artifact -- e.g. `docs/ecosystem/index.html`, rebuilt fresh by
    `scripts/build_ecosystem.py --write` in CI right before it is uploaded
    and attested -- is neither, so it is invisible to that scan even when
    `--root` points at the repository. Callers that publish a built artifact
    must scan it explicitly with this function (or `--scan-file`) before
    attesting/uploading it.
    """
    findings: list[str] = []
    try:
        raw = path.read_bytes()
    except OSError as error:
        return [f"{path}: cannot read file ({type(error).__name__})"]
    try:
        content = raw.decode("utf-8")
    except UnicodeError:
        content = raw.decode("latin-1")
    for description, pattern in PRIVATE_CONTENT:
        match = pattern.search(content)
        if match:
            # Never echo matched credentials or personal paths.
            findings.append(f"{path}: contains possible {description}")
            if locations is not None:
                locations.append(content.count("\n", 0, match.start()) + 1)
    return findings


class Validator:
    def __init__(self, root: Path, *, today: date | None = None):
        self.root = root.resolve()
        self.errors: list[str] = []
        self.today = today

    def error(self, message: str) -> None:
        self.errors.append(message)

    def text(self, value, label: str) -> bool:
        valid = isinstance(value, str) and bool(value.strip())
        if not valid:
            self.error(f"{label}: expected nonempty string")
        return valid

    def sequence(self, value, label: str, *, nonempty=False) -> list:
        if not isinstance(value, list) or (nonempty and not value):
            self.error(f"{label}: expected {'nonempty ' if nonempty else ''}array")
            return []
        return value

    def identifiers(self, value, label: str, *, nonempty=False) -> list[str]:
        values = self.sequence(value, label, nonempty=nonempty)
        result = []
        for item in values:
            if self.text(item, label):
                if item in result:
                    self.error(f"{label}: duplicate identifier {item}")
                result.append(item)
        return result

    def records(self, value, label: str) -> dict[str, dict]:
        records = {}
        for index, record in enumerate(self.sequence(value, label, nonempty=True)):
            if not isinstance(record, dict):
                self.error(f"{label}[{index}]: expected object")
                continue
            identifier = record.get("id")
            if self.text(identifier, f"{label}[{index}].id"):
                if identifier in records:
                    self.error(f"{label}: duplicate id {identifier}")
                records[identifier] = record
        return records

    def path(self, value, label: str) -> Path | None:
        if not self.text(value, label):
            return None
        parts = PurePosixPath(value).parts
        if (value.startswith("/") or "\\" in value or ":" in value or "\x00" in value
                or any(part in {"", ".", ".."} for part in value.split("/"))
                or not parts or parts[0] == ".git"):
            self.error(f"{label}: path must be canonical, relative, and inside publication")
            return None
        current = self.root
        for part in parts:
            current = current / part
            if current.is_symlink():
                self.error(f"{label}: symlinks are forbidden")
                return None
        if not current.resolve().is_relative_to(self.root):
            self.error(f"{label}: path escapes publication")
            return None
        if not current.is_file():
            self.error(f"{label}: file missing")
            return None
        return current

    def load(self, relative_path: str) -> dict:
        path = self.path(relative_path, relative_path)
        if path is None:
            return {}
        try:
            result = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_json_without_duplicates)
        except (OSError, ValueError) as error:
            self.error(f"{relative_path}: invalid JSON ({type(error).__name__})")
            return {}
        if not isinstance(result, dict):
            self.error(f"{relative_path}: expected JSON object")
            return {}
        if result.get("schema_version") != 1 or isinstance(result.get("schema_version"), bool):
            self.error(f"{relative_path}: unsupported schema_version")
        return result

    def check_credential_inventory(self) -> None:
        """Names-only credential inventory (docs/secret-storage.md), when present."""
        path = self.root / "adoption/credential-inventory.json"
        if not path.is_file():
            return
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_credential_status", Path(__file__).resolve().with_name("credential_status.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        try:
            inventory = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.error("adoption/credential-inventory.json: invalid JSON")
            return
        for message in module.inventory_errors(inventory, self.root):
            self.error(f"adoption/credential-inventory.json: {message}")

    def publication_paths(self, hashed_paths) -> list[str]:
        """Use only this root's Git boundary; archives retain filesystem scanning."""
        paths = {"manifests/stack.json", "manifests/evidence.json", *hashed_paths}
        marker = self.root / ".git"
        if marker.exists() or marker.is_symlink():
            # Inherited Git routing/index variables must not select another
            # checkout or hide tracked files in an alternate index.
            environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
            try:
                top = subprocess.run(
                    ["git", "--no-optional-locks", "-C", str(self.root), "rev-parse", "--show-toplevel"],
                    env=environment, capture_output=True, check=True,
                )
                if Path(os.fsdecode(top.stdout).rstrip("\r\n")).resolve() != self.root:
                    raise ValueError("Git top level differs from publication root")
                listing = subprocess.run(
                    ["git", "--no-optional-locks", "-C", str(self.root), "ls-files", "--cached",
                     "--others", "--exclude-standard", "-z"],
                    env=environment, capture_output=True, check=True,
                )
                if listing.stdout and not listing.stdout.endswith(b"\0"):
                    raise ValueError("Git listing is not NUL terminated")
                listed = {os.fsdecode(item) for item in listing.stdout.split(b"\0") if item}
            except (OSError, subprocess.CalledProcessError, ValueError):
                # Do not fall back to a success on an incomplete or redirected
                # Git listing, and do not echo Git's possibly private stderr.
                self.error("Git publication enumeration failed at the exact root")
            else:
                # The listing holds every tracked file plus every untracked file Git
                # would add. A hash-listed file outside it is ignored and untracked:
                # it passes here only because it exists on this disk, and a commit of
                # this tree leaves it out, so a clean clone (CI) reports it missing.
                for name in sorted(paths - listed):
                    candidate = self.root / name
                    if candidate.is_file() or candidate.is_symlink():
                        self.error(f"{name}: hash-listed but ignored by Git and not tracked, so a commit "
                                   "would leave it out; rename it, add a narrow .gitignore exception, "
                                   "or force-add it")
                paths.update(listed)
        else:
            # A source archive can be inside some unrelated parent repository.
            # Never borrow that ancestor's ignores. Prune only Git metadata and
            # generated Python cache directories, without hiding cache symlinks.
            def walk_error(_error):
                self.error("Cannot enumerate publication archive")

            for directory, folders, filenames in os.walk(self.root, onerror=walk_error):
                parent = Path(directory)
                folders[:] = [name for name in folders if name != ".git"
                              and (name != "__pycache__" or (parent / name).is_symlink())]
                for name in filenames + [name for name in folders if (parent / name).is_symlink()]:
                    if name != ".git":
                        paths.add((parent / name).relative_to(self.root).as_posix())
        return sorted(paths)

    def pdf_review(self, relative: str, raw: bytes, files: dict) -> None:
        label = f"{relative}.publication_review"
        record = files[relative]
        review = record.get("publication_review")
        if not isinstance(review, dict):
            self.error(f"{label}: PDF requires recorded review and provenance")
            return
        for field in ("source", "license", "text_extraction_method"):
            self.text(review.get(field), f"{label}.{field}")
        if review.get("reviewed_for_private_content") is not True:
            self.error(f"{label}: reviewed_for_private_content must be true")
        if review.get("reviewed_sha256") != hashlib.sha256(raw).hexdigest():
            self.error(f"{label}: reviewed_sha256 must match PDF bytes")
        extraction = review.get("text_extraction_path")
        if (not isinstance(extraction, str) or extraction not in files
                or PurePosixPath(extraction).suffix.lower() not in {".txt", ".md"}):
            self.error(f"{label}: text_extraction_path must name hash-listed UTF-8 text")
        else:
            self.path(extraction, f"{label}.text_extraction_path")

    def scan_publication(self, files: dict) -> None:
        artifact_roots = {("evidence", "artifacts"), ("blueprints", "convergence-practice")}
        for name in self.publication_paths(files):
            relative = PurePosixPath(name)
            if relative.parts[:2] in {("evidence", "receipts"), ("evidence", "artifacts")} and name not in files:
                self.error(f"{relative}: evidence file is not hash-listed")
            path = self.path(name, name)
            if path is None:
                continue
            if path.name in {".env", ".credentials.json", "auth.json"}:
                self.error(f"{relative}: private authentication/environment file is forbidden")
            try:
                raw = path.read_bytes()
                if path.suffix.lower() in {".png", ".pdf"}:
                    kind = path.suffix[1:].upper()
                    if relative.parts[:2] not in artifact_roots or name not in files:
                        self.error(f"{relative}: {kind} must be a hash-listed evidence artifact or convergence-practice corpus artifact")
                        continue
                    if kind == "PNG" and not is_structural_png(raw):
                        self.error(f"{relative}: invalid PNG structure or checksum")
                        continue
                    if kind == "PDF":
                        if not is_supported_pdf_framing(raw):
                            self.error(f"{relative}: unsupported PDF framing (classic unencrypted single revision required)")
                        self.pdf_review(name, raw, files)
                    # Still catch obvious uncompressed metadata; image content
                    # and encoded/compressed PDF content require author review.
                    # Required PDF extraction text is independently hash-checked
                    # and scanned; stdlib byte scanning cannot extract it.
                    content = raw.decode("latin-1")
                else:
                    content = raw.decode("utf-8")
            except (OSError, UnicodeError):
                self.error(f"{relative}: cannot inspect as UTF-8 publication text")
                continue
            for description, pattern in PRIVATE_CONTENT:
                if pattern.search(content):
                    # Never echo matched credentials or personal paths.
                    self.error(f"{relative}: contains possible {description}")

    def validate(self) -> dict[str, int]:
        stack = self.load("manifests/stack.json")
        evidence = self.load("manifests/evidence.json")
        components = self.records(stack.get("components"), "components")
        profiles = self.records(stack.get("profiles"), "profiles")
        receipts = self.records(evidence.get("receipts"), "receipts")
        files = {}
        previous_path = None
        for index, record in enumerate(self.sequence(evidence.get("files"), "files", nonempty=True)):
            if not isinstance(record, dict):
                self.error(f"files[{index}]: expected object")
                continue
            label = f"files[{index}]"
            path_value = record.get("path")
            path = self.path(path_value, label)
            if not isinstance(path_value, str):
                continue
            if path_value in files:
                self.error(f"files: duplicate path {path_value}")
            if previous_path is not None and path_value < previous_path:
                self.error(f"{label}: files[] must be sorted by path (found {path_value!r} after "
                           f"{previous_path!r}); run `python3 scripts/evidence_manifest.py --write` to sort it")
            previous_path = path_value
            files[path_value] = record
            digest = record.get("sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                self.error(f"{label}: sha256 must be lowercase 64-digit hex")
            size = record.get("bytes")
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                self.error(f"{label}: bytes must be nonnegative integer")
            if path is not None:
                content = path.read_bytes()
                if hashlib.sha256(content).hexdigest() != digest:
                    self.error(f"{path_value}: SHA-256 mismatch")
                if len(content) != size:
                    self.error(f"{path_value}: byte count mismatch")

        memberships = {}
        for identifier, profile in profiles.items():
            for component_id in self.identifiers(profile.get("component_ids"), f"profile {identifier}.component_ids", nonempty=True):
                if component_id not in components:
                    self.error(f"profile {identifier}: unknown component {component_id}")
                if component_id in memberships:
                    self.error(f"component {component_id}: multiple profile memberships")
                memberships[component_id] = identifier

        for identifier, component in components.items():
            label = f"component {identifier}"
            self.text(component.get("version"), f"{label}.version")
            profile = component.get("profile")
            if not isinstance(profile, str) or profile not in profiles or memberships.get(identifier) != profile:
                self.error(f"{label}: profile membership mismatch")
            for command in self.sequence(component.get("commands"), f"{label}.commands", nonempty=True):
                if isinstance(command, str):
                    self.text(command, f"{label}.commands")
                elif isinstance(command, dict) and "skill_invocation" in command:
                    if not isinstance(command.get("source_only"), bool):
                        self.error(f"{label}: skill command requires source_only boolean")
                    if command.get("source_only") is not True or command["skill_invocation"] is not None:
                        self.identifiers(command["skill_invocation"], f"{label}.skill_invocation", nonempty=True)
                elif isinstance(command, dict) and "tool" in command:
                    self.text(command["tool"], f"{label}.tool")
                    if not isinstance(command.get("arguments"), dict):
                        self.error(f"{label}: native tool command requires arguments object")
                else:
                    self.error(f"{label}: unsupported command format")
            for receipt_id in self.identifiers(component.get("evidence_ids"), f"{label}.evidence_ids", nonempty=True):
                if receipt_id not in receipts:
                    self.error(f"{label}: unknown evidence {receipt_id}")
                elif not isinstance(receipts[receipt_id].get("component_ids"), list) or identifier not in receipts[receipt_id]["component_ids"]:
                    self.error(f"{label}: evidence {receipt_id} does not cover component")

        receipt_paths = set()
        for identifier, receipt in receipts.items():
            label = f"receipt {identifier}"
            kind = receipt.get("kind")
            if not isinstance(kind, str) or kind not in RECEIPT_KINDS:
                self.error(f"{label}: unknown evidence kind")
            self.text(receipt.get("claim"), f"{label}.claim")
            limitations = self.identifiers(receipt.get("limitations"), f"{label}.limitations", nonempty=True)
            component_ids = self.identifiers(receipt.get("component_ids"), f"{label}.component_ids", nonempty=True)
            for component_id in component_ids:
                if component_id not in components:
                    self.error(f"{label}: unknown component {component_id}")
            if kind == "historical_inventory":
                if not any("historical" in text.lower() and ("not" in text.lower() or "only" in text.lower()) for text in limitations):
                    self.error(f"{label}: historical inventory needs explicit non-live limitation")
                if receipt.get("live_verified") is True:
                    self.error(f"{label}: historical inventory cannot declare live_verified")
            path_value = receipt.get("path")
            path = self.path(path_value, f"{label}.path")
            if not isinstance(path_value, str):
                continue
            if path_value in receipt_paths:
                self.error(f"{label}: duplicate receipt path")
            receipt_paths.add(path_value)
            if path_value not in files:
                self.error(f"{label}: receipt is missing from hashed files")
            if path is not None:
                detail = self.load(path_value)
                for key in ("id", "kind", "component_ids", "claim", "limitations"):
                    if detail.get(key) != receipt.get(key):
                        self.error(f"{label}: payload {key} differs from manifest")

        model_ids = set()
        for model in self.sequence(stack.get("models", []), "models"):
            if not isinstance(model, dict):
                self.error("models: expected objects")
                continue
            if self.text(model.get("id"), "model.id"):
                if model["id"] in model_ids:
                    self.error("models: duplicate id")
                model_ids.add(model["id"])
            if "runtime" in model and (not isinstance(model["runtime"], str) or model["runtime"] not in components):
                self.error("model: unknown runtime component")
            for receipt_id in self.identifiers(model.get("evidence_ids", []), "model.evidence_ids"):
                if receipt_id not in receipts:
                    self.error(f"model: unknown evidence {receipt_id}")
        if (self.root / MODEL_CURRENCY_PATH).exists():
            self.errors.extend(model_currency_problems(self.load(MODEL_CURRENCY_PATH), self.today))
        self.check_credential_inventory()
        self.scan_publication(files)
        if self.errors:
            raise InvalidPublication("\n".join(self.errors))
        return {"components": len(components), "profiles": len(profiles), "receipts": len(receipts), "hashed_files": len(files)}


def validate(root: Path, *, today: date | None = None) -> dict[str, int]:
    return Validator(root, today=today).validate()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--today", type=date.fromisoformat, help="Model currency UTC date YYYY-MM-DD; default is today's UTC date")
    parser.add_argument(
        "--scan-file", action="append", default=[], type=Path, metavar="PATH",
        help="Scan an arbitrary file (repeatable) for PRIVATE_CONTENT patterns and "
             "runtime host-local names; report counts and file:line only. "
             "Exit 1 on a match or 2 on scanner error, independent of --root's "
             "git-tracked publication scan. "
             "Use this for a generated, gitignored artifact (e.g. a freshly built "
             "docs/ecosystem/index.html) that scan_publication() never walks.")
    parser.add_argument(
        "--scan-tracked", action="store_true",
        help="Scan tracked files for runtime host-local names with Betterleaks 1.9.0; "
             "report counts and file:line only. Hooks select an immutable checkout.")
    args = parser.parse_args()
    if args.scan_file or args.scan_tracked:
        try:
            try:
                from .host_name_scan import HostNameScanError, host_names, safe_locator, scan_paths
            except ImportError:
                from host_name_scan import HostNameScanError, host_names, safe_locator, scan_paths
        except ImportError:
            print(json.dumps({"status": "error", "scanned_files": len(args.scan_file)}, sort_keys=True))
            return 2
        paths = list(args.scan_file)
        try:
            if args.scan_tracked:
                tracked = subprocess.run(
                    ["git", "-C", str(args.root), "ls-files", "-z"],
                    capture_output=True, timeout=30, check=True)
                paths.extend(args.root / os.fsdecode(name) for name in tracked.stdout.split(b"\0") if name)
            paths = list(dict.fromkeys(paths))
            names = host_names(args.root)
            locators = {safe_locator(path, line, root=args.root, names=names)
                        for path, line in scan_paths(paths, root=args.root, names=names)}
            for path in dict.fromkeys(args.scan_file):
                private_lines: list[int] = []
                if scan_file_for_private_content(path, locations=private_lines) and not private_lines:
                    raise OSError  # A second read failed; no fabricated finding location.
                locators.update(safe_locator(path, line, root=args.root, names=names)
                                for line in private_lines)
        except (HostNameScanError, OSError, subprocess.SubprocessError):
            # Native diagnostic/config text and exception values are private.
            print(json.dumps({"status": "error", "scanned_files": len(paths)}, sort_keys=True))
            return 2
        print(json.dumps({"status": "failed" if locators else "passed",
                          "scanned_files": len(paths), "findings": len(locators)}, sort_keys=True))
        for locator in sorted(locators):
            print(locator)
        return 1 if locators else 0
    try:
        summary = validate(args.root, today=args.today)
    except InvalidPublication as error:
        print(f"Publication validation failed:\n{error}")
        return 1
    print(json.dumps({"status": "passed", **summary}, sort_keys=True))
    print("Integrity and scope checks only; no live provider or GPU execution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
