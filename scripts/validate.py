#!/usr/bin/env python3
"""Validate published manifests and receipts without accounts or model calls.

This verifies evidence integrity and declared scope. It does not repeat the
historical native executions, prove arbitrary claims, or measure live savings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
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

    def scan_publication(self, hashed_paths=()) -> None:
        for path in sorted(self.root.rglob("*")):
            relative = path.relative_to(self.root)
            if ".git" in relative.parts or "__pycache__" in relative.parts:
                continue
            if path.is_symlink():
                self.error(f"{relative}: symlinks are forbidden")
                continue
            if not path.is_file():
                continue
            if path.name in {".env", ".credentials.json", "auth.json"}:
                self.error(f"{relative}: private authentication/environment file is forbidden")
            try:
                raw = path.read_bytes()
                if path.suffix.lower() == ".png":
                    if relative.parts[:2] != ("evidence", "artifacts") or relative.as_posix() not in hashed_paths:
                        self.error(f"{relative}: PNG must be a hash-listed evidence artifact")
                        continue
                    if not is_structural_png(raw):
                        self.error(f"{relative}: invalid PNG structure or checksum")
                        continue
                    # Still catch obvious uncompressed metadata; image content
                    # requires the separate visual review recorded by the author.
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

        for folder in ("evidence/receipts", "evidence/artifacts"):
            for path in (self.root / folder).rglob("*"):
                if path.is_file() and path.relative_to(self.root).as_posix() not in files:
                    self.error(f"{path.relative_to(self.root)}: evidence file is not hash-listed")
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
        self.scan_publication(files)
        if self.errors:
            raise InvalidPublication("\n".join(self.errors))
        return {"components": len(components), "profiles": len(profiles), "receipts": len(receipts), "hashed_files": len(files)}


def validate(root: Path) -> dict[str, int]:
    return Validator(root).validate()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        summary = validate(args.root)
    except InvalidPublication as error:
        print(f"Publication validation failed:\n{error}")
        return 1
    print(json.dumps({"status": "passed", **summary}, sort_keys=True))
    print("Integrity and scope checks only; no live provider or GPU execution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
