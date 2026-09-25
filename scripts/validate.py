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
from pathlib import Path, PurePosixPath


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
    ("Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{20,}\b")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    ("Tavily token", re.compile(r"\btvly-(?:(?:prod|dev)-)?[A-Za-z0-9_-]{24,}\b")),
    ("API secret", re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}\b")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("bearer credential", re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{30,}", re.I)),
)


class InvalidPublication(ValueError):
    """One or more manifest, integrity, or publication hygiene failures."""


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


def scan_file_for_private_content(path: Path) -> list[str]:
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
        if pattern.search(content):
            # Never echo matched credentials or personal paths.
            findings.append(f"{path}: contains possible {description}")
    return findings


class Validator:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.errors: list[str] = []

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
                paths.update(os.fsdecode(item) for item in listing.stdout.split(b"\0") if item)
            except (OSError, subprocess.CalledProcessError, ValueError):
                # Do not fall back to a success on an incomplete or redirected
                # Git listing, and do not echo Git's possibly private stderr.
                self.error("Git publication enumeration failed at the exact root")
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
        self.check_credential_inventory()
        self.scan_publication(files)
        if self.errors:
            raise InvalidPublication("\n".join(self.errors))
        return {"components": len(components), "profiles": len(profiles), "receipts": len(receipts), "hashed_files": len(files)}


def validate_pins_v2(root: Path) -> tuple[list[str], list[str]]:
    """(errors, warnings) cross-checking adoption/pins-linux-x86_64.json's schema_version 2
    tools[] against manifests/stack.json components[].version and every
    catalogs/landscape/*.json winners[].pin, honouring a matching divergence[] entry (report-only)
    and never treating a pending candidate as a mismatch. Independent of Validator.validate(): a
    missing pins file, a pins file still at schema_version 1 (e.g. a macOS host not yet migrated),
    or a missing manifests/stack.json/catalogs/landscape all return no errors, because this check
    is a v2-specific parity rule, not a general publication-integrity rule (tests/test_pins_v2.py
    and tests/test_validate.py both exercise it; main() below is the only caller, so the exact
    dict validate() itself returns is unaffected)."""
    errors: list[str] = []
    warnings: list[str] = []
    pins_path = root / "adoption" / "pins-linux-x86_64.json"
    if not pins_path.is_file():
        return errors, warnings
    try:
        pins = json.loads(pins_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"adoption/pins-linux-x86_64.json: invalid JSON ({type(error).__name__})"], warnings
    if not isinstance(pins, dict) or pins.get("schema_version") != 2:
        return errors, warnings
    tools = pins.get("tools")
    if not isinstance(tools, list):
        return ["adoption/pins-linux-x86_64.json: schema_version 2 requires tools to be a list"], warnings

    divergence_by_id = {
        entry["id"]: entry for entry in pins.get("divergence") or []
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }

    stack_versions: dict[str, str] = {}
    stack_path = root / "manifests" / "stack.json"
    if stack_path.is_file():
        try:
            stack = json.loads(stack_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            errors.append("manifests/stack.json: invalid JSON; cannot cross-check pins v2")
        else:
            for component in (stack or {}).get("components") or []:
                if isinstance(component, dict) and isinstance(component.get("id"), str) and isinstance(component.get("version"), str):
                    stack_versions[component["id"]] = component["version"]

    # component_id -> [(pin, "<catalog>/<layer_id>"), ...]; a component can be a winner in more
    # than one layer (rare) so every citing layer is checked, not just the first found.
    landscape_pins: dict[str, list[tuple[str, str]]] = {}
    landscape_dir = root / "catalogs" / "landscape"
    if landscape_dir.is_dir():
        for landscape_file in sorted(landscape_dir.glob("*.json")):
            try:
                document = json.loads(landscape_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for layer in (document or {}).get("layers") or []:
                if not isinstance(layer, dict):
                    continue
                label = f"{landscape_file.stem}/{layer.get('layer_id')}"
                for winner in layer.get("winners") or []:
                    if (isinstance(winner, dict) and isinstance(winner.get("component_id"), str)
                            and isinstance(winner.get("pin"), str)):
                        landscape_pins.setdefault(winner["component_id"], []).append((winner["pin"], label))

    def check(tool_id: str, version, source_label: str, source_version: str) -> None:
        if source_version == version:
            return
        divergent = divergence_by_id.get(tool_id)
        message = (f"{tool_id}: pins v2 version {version!r} differs from {source_label} version "
                    f"{source_version!r}")
        if divergent is not None:
            warnings.append(f"{message} (declared divergence {divergent.get('kind')!r}; report-only)")
        else:
            errors.append(f"{message} (add a divergence[] entry if intentional, else make them agree)")

    for tool in tools:
        if not isinstance(tool, dict):
            errors.append("adoption/pins-linux-x86_64.json: every tools[] entry must be an object")
            continue
        tool_id, version = tool.get("id"), tool.get("version")
        if not isinstance(tool_id, str) or not tool_id or not isinstance(version, str) or not version:
            errors.append("adoption/pins-linux-x86_64.json: a tools[] entry is missing id or version")
            continue
        if tool_id in stack_versions:
            check(tool_id, version, "manifests/stack.json", stack_versions[tool_id])
        for pin, label in landscape_pins.get(tool_id, []):
            check(tool_id, version, label, pin)

    for divergence_id in divergence_by_id:
        if divergence_id not in {tool.get("id") for tool in tools if isinstance(tool, dict)}:
            errors.append(f"adoption/pins-linux-x86_64.json: divergence[] names {divergence_id!r}, which is not a tools[].id")

    for candidate in pins.get("candidates") or []:
        if isinstance(candidate, dict) and candidate.get("status") == "pending":
            warnings.append(f"candidate {candidate.get('id')!r} is pending (no installable pin yet); report-only")
        elif isinstance(candidate, dict):
            errors.append(f"candidate {candidate.get('id')!r}: candidates[] entries must currently be status \"pending\"")

    return errors, warnings


def validate(root: Path) -> dict[str, int]:
    return Validator(root).validate()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--scan-file", action="append", default=[], type=Path, metavar="PATH",
        help="Scan an arbitrary file (repeatable) for PRIVATE_CONTENT patterns and "
             "exit 1 on a match, independent of --root's git-tracked publication scan. "
             "Use this for a generated, gitignored artifact (e.g. a freshly built "
             "docs/ecosystem/index.html) that scan_publication() never walks.")
    args = parser.parse_args()
    if args.scan_file:
        findings = []
        for file_path in args.scan_file:
            findings.extend(scan_file_for_private_content(file_path))
        if findings:
            print("Private-content scan failed:\n" + "\n".join(findings))
            return 1
        print(json.dumps({"status": "passed", "scanned_files": len(args.scan_file)}, sort_keys=True))
        return 0
    try:
        summary = validate(args.root)
    except InvalidPublication as error:
        print(f"Publication validation failed:\n{error}")
        return 1
    pins_errors, pins_warnings = validate_pins_v2(args.root)
    for warning in pins_warnings:
        print(f"pins-v2 (report-only): {warning}")
    if pins_errors:
        print("Pins v2 parity check failed:\n" + "\n".join(pins_errors))
        return 1
    print(json.dumps({"status": "passed", **summary}, sort_keys=True))
    print("Integrity and scope checks only; no live provider or GPU execution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
