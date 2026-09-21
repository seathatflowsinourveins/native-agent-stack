#!/usr/bin/env python3
"""Validate and join the dated landscape choices; never infer benchmark wins."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
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
    expected.update(("us-equities", document["layer"]) for document in domain_documents.values())

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
    layers, seen = [], set()
    for catalog, path in documents.items():
        document = read(path)
        require(document.get("schema_version") == 1, "unsupported layer comparison schema")
        require(document.get("checked_at") == manifest["checked_at"], "layer review date differs from manifest")
        nonempty(document.get("scope"), path + ".scope")
        require(isinstance(document.get("layers"), list), path + " needs layers")
        for row in document["layers"]:
            key = (row["catalog"], row["layer_id"])
            require(key[0] == catalog and key in expected, "unknown comparison layer: " + str(key))
            require(key not in seen, "duplicate comparison layer: " + str(key))
            seen.add(key)
            for field in ("title", "requirement", "current_choice", "rationale", "overturn_when"):
                nonempty(row.get(field), str(key) + "." + field)
            require(row.get("decision") in DECISIONS, "unknown layer decision")
            strings(row.get("limitations"), str(key) + ".limitations")
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

    # All historical candidate cards remain visible with their original date and
    # role. They do not override the explicitly dated current comparison above.
    by_key = {(row["catalog"], row["layer_id"]): row for row in layers}
    for path, document in domain_documents.items():
        layer = by_key[("us-equities", document["layer"])]
        for position, row in enumerate(document["entries"]):
            layer["catalog_candidates"].append({
                "id": row["id"], "name": row["repository"].removeprefix("https://github.com/"),
                "repository": row["repository"], "role": row["role"], "decision": row["decision"],
                "rationale": row["rationale"], "evidence_kind": row["evidence_level"],
                "pin": row["version_or_commit"], "limitations": row["limitations"],
                "checked_at": document["checked_at"], "url": file_url(path) + "#L1",
                "pointer": "/entries/" + str(position),
                "sources": evidence(row["evidence_refs"], row["id"]),
            })

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
              "foundation_statuses": dict(sorted(review_status.items())),
              "comparison_candidates": sum(len(row["candidates"]) for row in layers),
              "historical_candidate_cards": sum(len(row["catalog_candidates"]) for row in layers),
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
    return {**manifest, "layers": layers, "counts": counts, "freshness": freshness, "native_practice": practice,
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
