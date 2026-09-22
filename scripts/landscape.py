#!/usr/bin/env python3
"""Validate and join the dated landscape choices; never infer benchmark wins."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
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


def validate_verdict_row(row, key, *, root, identities, aliases, evidence, recipe_map, sota_pins):
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
    for lane_name in ("claude", "codex"):
        lane = lanes_field.get(lane_name)
        require(isinstance(lane, dict), str(key) + f".lanes.{lane_name} must be an object")
        require(isinstance(lane.get("run_id"), str), str(key) + f".lanes.{lane_name}.run_id must be text")
        sealed = lane.get("sealed_sha256")
        require(isinstance(sealed, str), str(key) + f".lanes.{lane_name}.sealed_sha256 must be text")
        if sealed:
            require(bool(re.fullmatch(r"[a-f0-9]{64}", sealed)),
                    str(key) + f".lanes.{lane_name}.sealed_sha256 must be a lowercase 64-digit hash")
            sealed_path = f"evidence/artifacts/layer-verdicts-20260922/{lane_name}/{lane['run_id']}.json"
            require(safe_file(root, sealed_path).is_file(),
                    str(key) + f".lanes.{lane_name}.sealed_sha256 needs a sealed file: {sealed_path}")
    require(lanes_field.get("agreement") in LANE_AGREEMENTS, str(key) + ".lanes.agreement is unknown")

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
        require(any(marker in verdict_overturn_when for marker in OVERTURN_MARKERS),
                str(key) + ".verdict_overturn_when must name a fixture/blueprint/test path or a runnable command "
                           "for a recorded verdict")
    elif status == "no_selection":
        require(bool(open_gaps), str(key) + " no_selection verdict needs open_gaps")


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
                                  sota_pins=sota_pins_by_layer.get(key[1], {}))
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
