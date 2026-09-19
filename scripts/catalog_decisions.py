#!/usr/bin/env python3
"""Build/check the canonical repository decision union, entirely offline.

Register a reviewed supplement explicitly after adding its public source file:
  python3 scripts/catalog_decisions.py --write --supplement PATH.json#/candidates

Collections must be arrays of records with a `repository` field. A supplement is
not discovered by crawling every URL in prose. References retain source-declared
decisions and review levels; inclusion never upgrades source review into E2E.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit


BASE = "catalogs/us-equities"
INDEX = f"{BASE}/decision-index.json"
MANIFEST = f"{BASE}/manifest.json"
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+\Z")
SOURCE_FIELDS = {"path", "collection", "repository_field", "kind"}
SCOPE = ("Canonical identity union with typed pointers to recorded decisions. "
         "Discovery, source review, component records and native acceptance remain distinct; "
         "consult the referenced source and its receipts for the actual execution scope.")


class InvalidDecisionIndex(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidDecisionIndex(message)


def source(path, collection, kind, repository_field="repository"):
    return {"path": path, "collection": collection,
            "repository_field": repository_field, "kind": kind}


BASE_SOURCES = [
    source(f"{BASE}/coverage.json", "/stars", "public_star"),
    source(f"{BASE}/star-audit.json", "/entries", "star_review"),
    *[source(f"{BASE}/{name}.json", "/entries", "catalog_card") for name in
      ("foundation-memory", "agents-operations", "data-research", "engines-strategies")],
    source("manifests/stack.json", "/components", "component_record"),
    source("manifests/candidates.json", "/candidates", "legacy_candidate", "url"),
    source("adoption/research.json", "/candidates", "research_supplement"),
]


def safe_file(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and bool(relative), "source path must be text")
    parts = PurePosixPath(relative)
    require(bool(parts.parts) and not parts.is_absolute() and str(parts) == relative
            and all(part not in {".", "..", ".git"} for part in parts.parts)
            and not any(ord(char) < 32 or char in "\\:?#" for char in relative),
            "source path must be canonical and confined to the repository")
    path = root
    for part in parts.parts:
        path /= part
        require(not path.is_symlink(), "source symlinks are forbidden")
    require(path.resolve().is_relative_to(root), "source path escapes the repository")
    return path


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def load(root, relative):
    path = safe_file(root, relative)
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
    except (OSError, UnicodeError, ValueError) as error:
        raise InvalidDecisionIndex(f"invalid source JSON: {relative}") from error


def pointer(document, value):
    require(isinstance(value, str) and value.startswith("/") and value != "/",
            "collection must be a nonempty JSON pointer")
    current = document
    for encoded in value[1:].split("/"):
        require(not re.search(r"~(?![01])", encoded), "malformed JSON pointer escape")
        key = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            require(bool(re.fullmatch(r"0|[1-9][0-9]*", key)), "invalid array pointer index")
            require(int(key) < len(current), "JSON pointer array index missing")
            current = current[int(key)]
        else:
            require(isinstance(current, dict) and key in current, "JSON pointer target missing")
            current = current[key]
    return current


def identity(value):
    require(isinstance(value, str), "repository must be text")
    require(not any(char.isspace() or ord(char) < 32 or 127 <= ord(char) <= 159
                    for char in value), "repository must not contain whitespace or control characters")
    if "://" in value:
        try:
            parsed = urlsplit(value)
        except ValueError as error:
            raise InvalidDecisionIndex("malformed repository URL") from error
        require(parsed.scheme == "https" and parsed.netloc.lower() == "github.com"
                and not parsed.query and not parsed.fragment,
                "repository URL must identify a public GitHub repository")
        parts = parsed.path.strip("/").split("/")
        require(len(parts) >= 2, "repository URL is incomplete")
        value = "/".join(parts[:2])
    value = value.removesuffix(".git").lower()
    require(bool(NAME.fullmatch(value)) and value.split("/")[1] not in {".", ".."},
            "repository identity must be owner/repository")
    return value


def aliases_for(root):
    data = load(root, f"{BASE}/coverage.json")
    require(isinstance(data, dict) and isinstance(data.get("aliases"), dict), "coverage aliases must be an object")
    aliases = {}
    for key, value in data["aliases"].items():
        origin, target = identity(key), identity(value)
        require(origin not in aliases and origin != target, "duplicate or self-referential alias")
        aliases[origin] = target
    for name in aliases:
        canonical(name, aliases)
    return dict(sorted(aliases.items()))


def canonical(name, aliases):
    seen = set()
    while name in aliases:
        require(name not in seen, "repository alias cycle")
        seen.add(name)
        name = aliases[name]
    return name


def source_key(spec):
    return spec["path"], spec["collection"]


def checked_sources(root, specs):
    require(isinstance(specs, list), "sources must be an array")
    seen = set()
    required = {source_key(item): item for item in BASE_SOURCES}
    for item in specs:
        require(isinstance(item, dict) and set(item) == SOURCE_FIELDS, "invalid source descriptor fields")
        require(all(isinstance(value, str) for value in item.values()), "source descriptor values must be text")
        safe_file(root, item["path"])
        require(item["repository_field"] == "repository" or item == BASE_SOURCES[7],
                "supplement records must declare repository")
        key = source_key(item)
        require(key not in seen, "duplicate source collection")
        seen.add(key)
        if key in required:
            require(item == required[key], "base source descriptor was changed")
        else:
            require(item["kind"] == "research_supplement", "additional sources must be research supplements")
    require(set(required) <= seen, "required base source collection is missing")
    return sorted(specs, key=source_key)


def build_index(root: Path, sources=None):
    root = root.resolve()
    sources = checked_sources(root, sources if sources is not None else BASE_SOURCES)
    aliases = aliases_for(root)
    records = {}
    documents = {}
    for spec in sources:
        path = spec["path"]
        if path not in documents:
            documents[path] = load(root, path)
        collection = pointer(documents[path], spec["collection"])
        require(isinstance(collection, list), "source collection must be an array")
        for number, entry in enumerate(collection):
            require(isinstance(entry, dict), "source entry must be an object")
            name = canonical(identity(entry.get(spec["repository_field"])), aliases)
            record = records.setdefault(name, {"repository": f"https://github.com/{name}",
                "aliases": [], "public_star": False, "record_types": [], "references": []})
            kind = spec["kind"]
            if kind not in record["record_types"]:
                record["record_types"].append(kind)
            record["public_star"] |= kind == "public_star"
            reference = {"kind": kind, "path": path, "pointer": f"{spec['collection']}/{number}"}
            for field in ("id", "decision", "disposition", "review_level", "review_depth", "evidence_depth", "evidence_level"):
                if isinstance(entry.get(field), str):
                    reference[field] = entry[field]
            record["references"].append(reference)
    for alias in aliases:
        target = canonical(alias, aliases)
        if target in records:
            records[target]["aliases"].append(alias)
    result = []
    for name, record in sorted(records.items()):
        record["record_types"].sort()
        record["aliases"].sort()
        record["references"].sort(key=lambda item: (item["path"], item["pointer"], item["kind"]))
        result.append(record)
    stars = sum(record["public_star"] for record in result)
    counts = {"repositories": len(result), "public_star_repositories": stars,
              "beyond_public_stars": len(result) - stars,
              "references": sum(len(record["references"]) for record in result),
              "repositories_by_record_type": dict(sorted(Counter(
                  kind for record in result for kind in record["record_types"]).items()))}
    return {"schema_version": 1, "scope": SCOPE, "sources": sources,
            "aliases": aliases, "counts": counts, "records": result}


def validate_index(root: Path, manifest=None):
    root = root.resolve()
    manifest = manifest if manifest is not None else load(root, MANIFEST)
    require(isinstance(manifest, dict), "catalog manifest must be an object")
    require(manifest.get("decision_index_file") == INDEX, "manifest decision_index_file is missing or incorrect")
    data = load(root, INDEX)
    require(isinstance(data, dict) and type(data.get("schema_version")) is int
            and data["schema_version"] == 1, "invalid decision index schema")
    expected = build_index(root, data.get("sources"))
    require(data.get("aliases") == expected["aliases"], "decision index aliases are stale")
    records = data.get("records")
    require(isinstance(records, list), "decision records must be an array")
    names = [identity(item.get("repository")) for item in records if isinstance(item, dict)]
    require(len(names) == len(records) and len(set(names)) == len(names), "duplicate or malformed decision record")
    require(data.get("counts") == expected["counts"], "decision index counts do not match source union")
    require(data == expected, "decision index records or source pointers are stale; regenerate the explicit union")
    require(manifest.get("grand_index_repositories") == expected["counts"]["repositories"], "manifest grand repository count is stale")
    require(manifest.get("grand_index_beyond_stars") == expected["counts"]["beyond_public_stars"], "manifest grand beyond-star count is stale")
    return expected["counts"]


def supplement(argument):
    path, separator, collection = argument.partition("#")
    require(bool(separator), "supplement must be PATH.json#/collection")
    return source(path, collection, "research_supplement")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Regenerate the decision index and its manifest counts")
    mode.add_argument("--check", action="store_true", help="Check the registered union without writing (default)")
    parser.add_argument("--supplement", action="append", default=[], metavar="PATH.json#/collection")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        require(not args.supplement or args.write, "registering supplements requires --write")
        if args.write:
            index_path = safe_file(root, INDEX)
            specs = load(root, INDEX).get("sources") if index_path.exists() else list(BASE_SOURCES)
            require(isinstance(specs, list), "sources must be an array")
            additions = [supplement(item) for item in args.supplement]
            for item in additions:
                if item not in specs:
                    specs.append(item)
            index = build_index(root, specs)
            manifest = load(root, MANIFEST)
            require(isinstance(manifest, dict), "catalog manifest must be an object")
            manifest.update(decision_index_file=INDEX,
                            grand_index_repositories=index["counts"]["repositories"],
                            grand_index_beyond_stars=index["counts"]["beyond_public_stars"])
            index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
            safe_file(root, MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        counts = validate_index(root)
    except (InvalidDecisionIndex, OSError) as error:
        print(f"Decision-index validation failed: {error}")
        return 1
    print(json.dumps(counts, sort_keys=True))
    print("Identity union and typed source pointers validated; no upstream source or native execution was rerun.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
