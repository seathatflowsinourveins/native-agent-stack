#!/usr/bin/env python3
"""Check catalog structure, coverage joins and evidence classes, entirely offline.

This is not a source-fact checker or a rerun of the cited commands. A receipt's
presence and declared class cannot establish that it supports every prose claim.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit


BASE = "catalogs/us-equities"
CATALOG_FILES = tuple(f"{BASE}/{name}.json" for name in (
    "foundation-memory", "agents-operations", "data-research", "engines-strategies",
))
DECISIONS = {"default", "conditional", "alternative", "watch", "excluded"}
EVIDENCE_LEVELS = {"source_review", "native_proven", "metadata_only"}
DISPOSITIONS = {"catalog_reviewed", "baseline_record", "metadata_only_unassessed"}
NATIVE_RECEIPT_KINDS = {
    "native_model_e2e", "native_cli_e2e", "artifact_measurement", "historical_inventory",
}
REPO_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
ISO_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\Z"
)


class InvalidCatalog(ValueError):
    """The publication is incomplete or internally inconsistent."""


def require(condition, label: str, message: str) -> None:
    if not condition:
        raise InvalidCatalog(f"{label}: {message}")


def text(value, label: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), label, "expected nonempty text")
    return value


def object_value(value, label: str) -> dict:
    require(isinstance(value, dict), label, "expected object")
    return value


def sequence(value, label: str, *, nonempty: bool = True) -> list:
    require(isinstance(value, list) and (bool(value) or not nonempty), label,
            "expected nonempty array" if nonempty else "expected array")
    return value


def strings(value, label: str, *, nonempty: bool = True) -> list[str]:
    result = sequence(value, label, nonempty=nonempty)
    for index, item in enumerate(result):
        text(item, f"{label}[{index}]")
    require(len(result) == len(set(result)), label, "duplicate values")
    return result


def enum(value, choices: set[str], label: str) -> str:
    require(isinstance(value, str) and value in choices, label,
            f"expected one of {', '.join(sorted(choices))}")
    return value


def dated(value, label: str, *, nullable: bool = False, timestamp: bool = False):
    if value is None and nullable:
        return None
    text(value, label)
    try:
        if ISO_DATE.fullmatch(value):
            return date.fromisoformat(value)
        if timestamp and ISO_TIMESTAMP.fullmatch(value):
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    raise InvalidCatalog(f"{label}: invalid ISO {'date or timezone timestamp' if timestamp else 'date'}")


def https(value, label: str) -> str:
    text(value, label)
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == "https" and bool(parsed.hostname)
                 and parsed.username is None and parsed.password is None
                 and not any(character.isspace() for character in value)
                 and "\\" not in value)
        parsed.port  # Reject malformed ports, even when a caller does not use them.
    except ValueError:
        valid = False
    require(valid, label, "expected HTTPS URL without credentials")
    return value


def repository(value, label: str) -> str:
    https(value, label)
    parsed = urlsplit(value)
    name = parsed.path.removeprefix("/")
    require(parsed.netloc == "github.com" and not parsed.query and not parsed.fragment
            and bool(REPO_NAME.fullmatch(name))
            and name.split("/")[-1] not in {".", ".."}
            and not name.endswith(".git"), label,
            "expected canonical https://github.com/owner/repo URL")
    return name.lower()


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "JSON", f"duplicate key {key}")
        result[key] = value
    return result


class Validator:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.ids: set[str] = set()
        self.aliases: dict[str, str] = {}
        self.receipts: dict[str, dict] = {}

    def path(self, value, label: str) -> Path:
        text(value, label)
        relative = PurePosixPath(value)
        require(not relative.is_absolute() and str(relative) == value
                and all(part not in {".", ".."} for part in relative.parts)
                and "\\" not in value and ":" not in value
                and "?" not in value and "#" not in value,
                label, "path must be canonical, relative and confined to the repository")
        path = self.root
        for part in relative.parts:
            path = path / part
            require(not path.is_symlink(), label, "symlinks are forbidden")
        require(path.is_file(), label, f"file missing: {value}")
        require(path.resolve().is_relative_to(self.root), label, "path escapes repository")
        return path

    def load(self, relative: str) -> dict:
        path = self.path(relative, relative)
        try:
            result = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
        except (OSError, UnicodeError, ValueError) as error:
            raise InvalidCatalog(f"{relative}: invalid JSON: {error}") from error
        return object_value(result, relative)

    def header(self, data: dict, label: str, checked_at: str | None = None) -> None:
        require(type(data.get("schema_version")) is int and data["schema_version"] == 1,
                label, "schema_version must be 1")
        dated(data.get("checked_at"), f"{label}.checked_at")
        if checked_at is not None:
            require(data["checked_at"] == checked_at, label, "checked_at differs from manifest")

    def canonical(self, name: str) -> str:
        seen = set()
        while name in self.aliases:
            require(name not in seen, "coverage.aliases", f"alias cycle involving {name}")
            seen.add(name)
            name = self.aliases[name]
        return name

    def read_aliases(self, coverage: dict) -> None:
        self.aliases = object_value(coverage.get("aliases"), "coverage.aliases")
        for old, new in self.aliases.items():
            for name in (old, new):
                require(isinstance(name, str) and name == name.lower()
                        and bool(REPO_NAME.fullmatch(name))
                        and name.split("/")[-1] not in {".", ".."}
                        and not name.endswith(".git"), "coverage.aliases",
                        "aliases must be lowercase owner/repo names")
        for old in self.aliases:
            self.canonical(old)

    def evidence(self, refs, label: str) -> list[dict]:
        local_json = []
        for ref in strings(refs, label):
            if ref.startswith("https://"):
                https(ref, label)
            else:
                path = self.path(ref, label)
                if path.suffix == ".json":
                    if ref not in self.receipts:
                        self.receipts[ref] = self.load(ref)
                    local_json.append(self.receipts[ref])
        return local_json

    @staticmethod
    def is_receipt(data: dict, *, model: bool) -> bool:
        """Recognize evidence classes, not arbitrary local JSON or prose policies."""
        allowed = {"native_model_e2e"} if model else NATIVE_RECEIPT_KINDS
        if isinstance(data.get("kind"), str) and data["kind"] in allowed:
            result_scope = data.get("result", {}).get("scope") if isinstance(data.get("result"), dict) else None
            return (type(data.get("schema_version")) is int and data["schema_version"] == 1
                    and (any(data.get(key) for key in ("claim", "scope", "task")) or bool(result_scope))
                    and any(isinstance(data.get(key), (dict, list)) and data[key]
                            for key in ("data", "results", "result", "run", "commands")))
        # Older router receipts predate the kind field. These prove only anonymous
        # native health observations, never model execution or provider readiness.
        if not model and "kind" not in data and isinstance(data.get("routes"), list):
            try:
                dated(data.get("checked_at_utc"), "health receipt timestamp", timestamp=True)
                text(data.get("scope"), "health receipt scope")
                strings(data.get("limits"), "health receipt limits")
            except InvalidCatalog:
                return False
            return bool(data["routes"]) and all(
                isinstance(route, dict) and route.get("method") == "GET"
                and route.get("authentication_supplied") is False
                and type(route.get("attempts")) is int and route["attempts"] > 0
                and type(route.get("http_status")) is int and 100 <= route["http_status"] <= 599
                and isinstance(route.get("url"), str)
                for route in data["routes"]
            )
        return False

    def common_entry(self, item, label: str, *, model: bool = False) -> dict:
        item = object_value(item, label)
        identifier = text(item.get("id"), f"{label}.id")
        require(identifier not in self.ids, label, f"duplicate global id {identifier}")
        self.ids.add(identifier)
        decision = enum(item.get("decision"), DECISIONS, f"{label}.decision")
        level = enum(item.get("evidence_level"), EVIDENCE_LEVELS, f"{label}.evidence_level")
        text(item.get("role"), f"{label}.role")
        require("license" in item, label, "missing license (use null for unknown)")
        if item["license"] is not None:
            text(item["license"], f"{label}.license")
        strings(item.get("limitations"), f"{label}.limitations")
        strings(item.get("native_workflow"), f"{label}.native_workflow", nonempty=decision != "excluded")
        for source in strings(item.get("sources"), f"{label}.sources"):
            https(source, f"{label}.sources")
        receipts = self.evidence(item.get("evidence_refs"), f"{label}.evidence_refs")
        if level == "native_proven":
            require(any(self.is_receipt(receipt, model=model) for receipt in receipts), label,
                    "native_proven requires a local native_model_e2e receipt JSON; metadata is not inference proof"
                    if model else "native_proven requires a local execution receipt JSON, not policy or metadata alone")
        return item

    def catalog(self, relative: str, checked_at: str) -> dict[str, set[str]]:
        data = self.load(relative)
        self.header(data, relative, checked_at)
        require(data.get("layer") == PurePosixPath(relative).stem, relative, "layer differs from filename")
        repositories: dict[str, set[str]] = {}
        for index, value in enumerate(sequence(data.get("entries"), f"{relative}.entries")):
            label = f"{relative}.entries[{index}]"
            item = self.common_entry(value, label)
            for key in ("rationale", "version_or_commit", "us_equities_fit", "alpaca_fit"):
                text(item.get(key), f"{label}.{key}")
            for key in ("layers", "requirements"):
                strings(item.get(key), f"{label}.{key}")
            require("release_date" in item, label, "missing release_date (use null for unknown)")
            dated(item["release_date"], f"{label}.release_date", nullable=True, timestamp=True)
            if "source_commit" in item:
                require(isinstance(item["source_commit"], str) and bool(SHA.fullmatch(item["source_commit"])),
                        label, "source_commit must be a lowercase 40-character Git SHA")
            name = self.canonical(repository(item.get("repository"), f"{label}.repository"))
            repositories.setdefault(name, set()).add(item["id"])
        return repositories

    def models(self, relative: str, checked_at: str) -> int:
        data = self.load(relative)
        self.header(data, relative, checked_at)
        require(data.get("layer") == "models", relative, "layer must be models")
        text(data.get("scope"), f"{relative}.scope")
        window = sequence(data.get("recent_window"), f"{relative}.recent_window")
        require(len(window) == 2, relative, "recent_window must contain two dates")
        start, end = (dated(value, f"{relative}.recent_window") for value in window)
        require(start <= end <= date.fromisoformat(checked_at), relative, "invalid recent_window ordering")
        entries = sequence(data.get("entries"), f"{relative}.entries")
        for index, value in enumerate(entries):
            label = f"{relative}.entries[{index}]"
            item = self.common_entry(value, label, model=True)
            for key in ("provider", "release_evidence_kind", "task_fit", "workflow_scope"):
                text(item.get(key), f"{label}.{key}")
            require("revision" in item, label, "missing revision (use null for unknown/hosted)")
            if item["revision"] is not None:
                require(isinstance(item["revision"], str) and bool(SHA.fullmatch(item["revision"])),
                        label, "revision must be null or a lowercase 40-character SHA")
            require("release_evidence_date" in item, label, "missing release_evidence_date")
            dated(item["release_evidence_date"], f"{label}.release_evidence_date", nullable=True)
            for key in ("repository_created_at", "last_modified"):
                if key in item:
                    dated(item[key], f"{label}.{key}", nullable=True, timestamp=True)
            if item.get("inference_recipe") is not None:
                text(item["inference_recipe"], f"{label}.inference_recipe")
        return len(entries)

    def baseline_repositories(self) -> set[str]:
        data = self.load("manifests/stack.json")
        result = set()
        for item in sequence(data.get("components"), "stack.components"):
            item = object_value(item, "stack.components[]")
            value = item.get("repository")
            if isinstance(value, str) and value.startswith("https://github.com/"):
                parts = urlsplit(value).path.strip("/").split("/")
                if len(parts) >= 2:
                    name = repository("https://github.com/" + "/".join(parts[:2]), "stack repository")
                    result.add(self.canonical(name))
        return result

    def coverage(self, data: dict, catalog_repos: dict[str, set[str]]) -> dict[str, int]:
        stars, beyond = set(), set()
        baseline = None
        for section in ("stars", "beyond_stars"):
            records = sequence(data.get(section), f"coverage.{section}", nonempty=False)
            seen = stars if section == "stars" else beyond
            for index, value in enumerate(records):
                label = f"coverage.{section}[{index}]"
                item = object_value(value, label)
                name = self.canonical(repository(item.get("repository"), f"{label}.repository"))
                require(name not in seen, label, f"duplicate canonical repository {name}")
                seen.add(name)
                ids = set(strings(item.get("catalog_entry_ids"), f"{label}.catalog_entry_ids", nonempty=False))
                expected = catalog_repos.get(name, set())
                require(ids == expected, label, f"catalog_entry_ids do not match repository {name}")
                if section == "stars":
                    disposition = enum(item.get("disposition"), DISPOSITIONS, f"{label}.disposition")
                    require((disposition == "catalog_reviewed") == bool(expected), label,
                            "catalog_reviewed disposition must match catalog membership")
                    if disposition == "baseline_record":
                        if baseline is None:
                            baseline = self.baseline_repositories()
                        require(name in baseline, label, "baseline_record is absent from manifests/stack.json")
                else:
                    require(bool(expected), label, "beyond_stars must refer to a catalog repository")
        require(not stars & beyond, "coverage", "starred and beyond-star repositories overlap")
        require(set(catalog_repos) <= stars | beyond, "coverage", "catalog repositories missing from coverage")
        return {
            "public_stars": len(stars),
            "starred_catalog_repositories": len(stars & catalog_repos.keys()),
            "beyond_star_catalog_repositories": len(beyond),
        }

    def run(self) -> dict[str, int]:
        manifest = self.load(f"{BASE}/manifest.json")
        self.header(manifest, "manifest")
        checked_at = manifest["checked_at"]
        catalogs = strings(manifest.get("catalog_files"), "manifest.catalog_files")
        require(set(catalogs) == set(CATALOG_FILES), "manifest.catalog_files", "expected all four repository catalogs")
        for key, expected in (("model_file", f"{BASE}/models.json"), ("coverage_file", f"{BASE}/coverage.json")):
            require(manifest.get(key) == expected, f"manifest.{key}", f"expected {expected}")
        coverage = self.load(manifest["coverage_file"])
        self.header(coverage, "coverage", checked_at)
        self.read_aliases(coverage)
        repositories: dict[str, set[str]] = {}
        for relative in catalogs:
            for name, ids in self.catalog(relative, checked_at).items():
                repositories.setdefault(name, set()).update(ids)
        counts = {
            "repository_entries": sum(map(len, repositories.values())),
            "unique_catalog_repositories": len(repositories),
            "models": self.models(manifest["model_file"], checked_at),
            **self.coverage(coverage, repositories),
        }
        declared = object_value(manifest.get("counts"), "manifest.counts")
        require(set(declared) == set(counts), "manifest.counts", "missing or unknown count fields")
        for key, actual in counts.items():
            require(type(declared[key]) is int and declared[key] >= 0, f"manifest.counts.{key}", "expected nonnegative integer")
            require(declared[key] == actual, f"manifest.counts.{key}", f"declared {declared[key]}, computed {actual}")
        return counts


def validate(root: Path) -> dict[str, int]:
    return Validator(root).run()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        counts = validate(args.root)
    except InvalidCatalog as error:
        print(f"Catalog validation failed: {error}")
        return 1
    print(json.dumps(counts, sort_keys=True))
    print("Catalog structure and evidence classes validated; source claims and native executions were not rerun.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
