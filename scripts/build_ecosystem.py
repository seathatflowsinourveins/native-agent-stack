#!/usr/bin/env python3
"""Build/check the self-contained public explorer, without network or dependencies."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
import os
import subprocess
import sys
from urllib.parse import quote, urlsplit

try:
    from .catalog_decisions import InvalidDecisionIndex, canonical, load, pointer, safe_file
    from .component_matrix import (CONVERGENCE_FACTOR_VALUES, CONVERGENCE_FACTORS, CONVERGENCE_LAYER_STATES,
                                   OUTPUT_JSON as COMPONENT_MATRIX)
    from .landscape import build_landscape
except ImportError:
    from catalog_decisions import InvalidDecisionIndex, canonical, load, pointer, safe_file
    from component_matrix import (CONVERGENCE_FACTOR_VALUES, CONVERGENCE_FACTORS, CONVERGENCE_LAYER_STATES,
                                  OUTPUT_JSON as COMPONENT_MATRIX)
    from landscape import build_landscape


CONFIG = "docs/ecosystem/manifest.json"
TEMPLATE = "docs/ecosystem/template.html"
OUTPUT = "docs/ecosystem/index.html"
INDEX = "catalogs/us-equities/decision-index.json"
STACK = "manifests/stack.json"
EVIDENCE = "manifests/evidence.json"
STARS = "catalogs/convergence-practice/public-starred.json"
REVIEW = "catalogs/convergence-practice/source-review.json"
ADOPTION = "adoption/manifest.json"
SATURATION = "blueprints/token-native-focus/saturation-audit.json"
TOKEN_TOPIC = "docs/token-efficiency-stack.json"
# A dated topic edition gives every row a per-tool card or an explicit marker. Each
# card block keeps its own evidence class; pins always come from manifests/stack.json.
TOKEN_TOPIC_CARD_BLOCKS = ("upstream", "native_adaptation", "e2e_returned_results",
                           "adapted_performance", "invoke_rates", "gpt6_review")
TOKEN_TOPIC_NO_CARD = "no card in this edition"
FOUNDATION_SURFACES = "catalogs/foundation/surfaces.json"
SETUP_GUIDES = ("adoption/README.md", "adoption/update.md", "tools/token-report/README.md")
TOKEN_RECEIPTS = (
    "token-practice-native-counters-20260920", "native-jcodemunch-20260920",
    "native-headroom-mcp-20260920", "token-practice-catalog-toon-20260920",
    "native-token-focus-clients-20260920",
)
# Explicit publication families, with dates supplied by the evidence registry.
# A matching name alone never qualifies execution: native families also require
# an execution evidence kind and canonical selected component identities.
TOKEN_RECEIPT_FAMILIES = {
    "token-practice-confirmation", "native-token-clean-prefix",
    "current-session-observation", "native-token-stack-final", "foundation-native",
}
RETURNED_RECEIPT_FAMILIES = {
    "memory-lifecycle-probe",
    "claude-foundation-finalization",
    "native-returned-results", "native-memory-rag-alignment", "hf-memory-models",
    "native-dashboard-data", "native-dashboard-access", "full-stack-convergence",
    "dashboard-render-e2e", "dashboard-gap-resolution", "memory-landscape", "memory-landscape-lifecycle", "foundation-convergence",
    "foundation-rd",
    "claude-upstream-checks",
    "broad-universe-research", "adaptive-paper-practice",
    "claude-repository-evidence",
}
PUBLIC_ARTIFACT_LIMIT = 2 * 1024 * 1024
PUBLIC_BUNDLE_LIMIT = 16 * 1024 * 1024
NEW_PUBLIC_FILES = {"adoption/lifecycle.md", "evidence/receipts/token-practice-confirmation-20260920.json",
                    "docs/native-skill-practice-20260921.md",
                    "docs/hosting-container-practice.md", "docs/landscape-continuation.md",
                    "docs/token-native-saturation.md", "catalogs/us-equities/README.md",
                    "catalogs/us-equities/decision-index.json", "catalogs/us-equities/manifest.json",
                    "docs/claude-upstream-checks.md", "docs/ecosystem/claude-upstream-checks.html",
                    "evidence/artifacts/claude-upstream-checks-20260921/results.json",
                    "evidence/artifacts/claude-upstream-checks-20260921/provenance.json",
                    "evidence/artifacts/claude-upstream-checks-20260921/grand-dashboard-6h-20260921.png",
                    "evidence/artifacts/claude-upstream-checks-20260921/grand-dashboard-72h-20260921.png",
                    "evidence/artifacts/claude-upstream-checks-20260921/token-savings-manifest-page-20260921.png",
                    "docs/claude-repository-evidence.md",
                    "docs/ecosystem/claude-repository-evidence.html",
                    "evidence/artifacts/claude-repository-evidence-20260921/summary.json",
                    "evidence/artifacts/claude-repository-evidence-20260921/provenance.json",
                    "evidence/artifacts/claude-repository-evidence-20260921/shots/prometheus-targets.png",
                    "evidence/artifacts/claude-repository-evidence-20260921/shots/qdrant-collections.png",
                    "evidence/artifacts/claude-repository-evidence-20260921/shots/dagu-dag-latest-run.png",
                    "docs/claude-foundation-finalization-20260921.md", "examples/claude-native/workflows/README.md",
                    "docs/foundation-rd-readiness.md", "recipes/claude-codex-foreground-review.md",
                    "evidence/artifacts/foundation-rd-20260921/qmd-comparison.json",
                    "evidence/artifacts/foundation-rd-20260921/qmd-bench-output.txt",
                    "evidence/artifacts/foundation-rd-20260921/native-review.json",
                    "recipes/claude-native-ultracode.md", "examples/claude-native/ultracode.settings.json",
                    "docs/ultracode-token-routing-20260921.md", "recipes/claude-codex-cooperation-lanes.md", "examples/codex-native/README.md",
                    "blueprints/us-equities/broad-universe/README.md", "blueprints/us-equities/adaptive-paper/README.md",
                    "evidence/receipts/broad-universe-research-20260921.json", "evidence/receipts/adaptive-paper-practice-20260921.json",
                    "docs/harness-rules-convergence-20260922.md", "docs/new-workstation-runtime-profile-20260922.md",
                    "evidence/artifacts/harness-rules-convergence-20260922/runs.json",
                    "evidence/artifacts/harness-rules-convergence-20260922/official-doc-excerpts.json",
                    "evidence/artifacts/harness-rules-convergence-20260922/codex-agent-roles-source.json",
                    "evidence/receipts/ultracode-token-routing-20260921.json", "evidence/receipts/portable-claude-native-qualification-20260921.json",
                    "evidence/artifacts/native-claude-coop-20260921/persistent-profile.json",
                    "docs/memory-landscape-maintenance.md", "docs/native-memory-rag-lifecycle.md", "docs/foundation-convergence-20260921.md",
                    "docs/harness-defaults.md", "catalogs/README.md", STACK, ADOPTION,
                    "docs/full-stack-convergence.md", "recipes/native-upgrades-20260921.md",
                    "docs/token-practice.md", "tools/token-report/README.md", "recipes/README.md",
                    "catalogs/foundation/decisions.json", "catalogs/foundation/manifest.json",
                    "blueprints/token-native-focus/saturation-audit.json",
                    "blueprints/us-equities/north-star.md"}
EXECUTION_KINDS = {"native_cli_e2e", "native_model_e2e"}
# The convergence-by-layer fields the page shows; per-component detail stays in the linked matrix.
CONVERGENCE_LAYER_FIELDS = ("layer_state", "verdict_checked_at", "reopened_by", "in_use", "converged", "all_rows",
                            "recorded_winner_rows", "factors", "unresolved", "manifest_layer_found",
                            "winners_without_manifest_row", "invoke", "invoke_reason")
CONVERGENCE_SUMMARY_FIELDS = ("frozen_at", "definitions", "sources", "layer_states", "catalogs", "overall",
                              "newest_manifest", "newest_verdict_checked_at", "manifest_layers_without_matrix_row")
CONVERGENCE_SCOPE_COUNTS = ("layers", "in_use", "converged", "unresolved")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def public_url(value):
    """Only credential-free HTTPS links can become navigable source links."""
    if not isinstance(value, str) or any(ord(c) < 33 for c in value) or "\\" in value:
        return ""
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.port not in {None, 443}
                or parsed.hostname in {"localhost", "127.0.0.1", "::1"}):
            return ""
    except ValueError:
        return ""
    return value


def loopback_url(value):
    """A chosen browser link to this PC, never a background health request."""
    if not isinstance(value, str) or any(ord(c) < 33 for c in value) or "\\" in value:
        return ""
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"}
                or not re.fullmatch(r"(?:127\.0\.0\.1|\[::1\])(?::[0-9]+)?", parsed.netloc)
                or parsed.port == 0 or parsed.query or parsed.fragment):
            return ""
    except ValueError:
        return ""
    return value


def repository_key(value):
    require(public_url(value) == value and bool(re.fullmatch(
        r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value)),
        "repository must be a canonical public GitHub HTTPS URL")
    return value.removeprefix("https://github.com/").casefold()


def stamp(value):
    for key in ("retrieved_at", "checked_at", "recorded_at_utc", "recorded_at",
                "observed_at_utc", "observed_at", "executed_at", "recorded_date_utc", "date"):
        if isinstance(value.get(key), str):
            return value[key]
    return "Date not recorded in this source"


def text(value):
    return value if isinstance(value, str) else ""


def source_links(value):
    links = []
    for candidate in value if isinstance(value, list) else []:
        candidate = candidate.get("url", "") if isinstance(candidate, dict) else candidate
        if public_url(candidate) and candidate not in links:
            links.append(candidate)
    return links


def build_grand_catalogs(config, stack, receipts_by_id, read, track, file_url, root):
    """Join explicit capability decisions; repository execution flags are not acceptance."""
    paths = config.get("grand_catalogs")
    if paths is None:
        return None
    require(isinstance(paths, dict) and set(paths) == {
        "foundation_manifest", "foundation_decisions", "trading_target"},
        "grand catalogs need all three configured sources")
    manifest, decisions, target = (read(paths[key]) for key in (
        "foundation_manifest", "foundation_decisions", "trading_target"))
    require(all(row.get("schema_version") == 1 for row in (manifest, decisions, target)),
            "unsupported grand catalog schema")
    components = {row["id"]: row for row in stack["components"]}
    layers = manifest["layers"]
    layer_ids = [row["id"] for row in layers]
    require(len(set(layer_ids)) == len(layer_ids), "duplicate foundation layer")
    decision_ids = [row["id"] for row in decisions["decisions"]]
    require(len(set(decision_ids)) == len(decision_ids), "duplicate foundation decision")

    def sources(values):
        require(isinstance(values, list), "catalog source paths must be a list")
        result = []
        for path in values:
            track(path)
            result.append({"path": path, "url": file_url(path)})
        return result

    joined = []
    for row in decisions["decisions"]:
        require(set(row["layer_ids"]).issubset(layer_ids), "unknown foundation layer")
        require(set(row["component_ids"]).issubset(components), "catalog references an unknown component")
        require(set(row["evidence_ids"]).issubset(receipts_by_id), "catalog references an unknown receipt")
        supersessions = row.get("supersedes", [])
        require(isinstance(supersessions, list), "catalog supersedes must be a list")
        for supersession in supersessions:
            require(isinstance(supersession, dict)
                    and set(supersession) == {"decision_id", "scope", "reason"}
                    and all(isinstance(value, str) and value.strip() for value in supersession.values()),
                    "catalog supersession needs decision_id, scope and reason text")
            require(supersession["decision_id"] in decision_ids, "catalog supersedes an unknown decision")
        item = {**row, "sources": sources(row.get("source_paths", [])), "components": [], "receipts": []}
        item.pop("source_paths", None)
        for identifier in row["component_ids"]:
            component = components[identifier]
            item["components"].append({"id": identifier,
                "repository": public_url(component.get("repository")),
                "version": component.get("version", "Not recorded"),
                "source_pin": component.get("source_pin", ""),
                "source_commit": component.get("source_commit", ""),
                "license": component.get("license", "Not recorded"), "url": file_url(STACK)})
        for identifier in row["evidence_ids"]:
            receipt = receipts_by_id[identifier]
            detail = read(receipt["path"])
            item["receipts"].append({"id": identifier, "kind": receipt["kind"],
                "claim": receipt["claim"], "limitations": receipt["limitations"],
                "date": stamp(detail), "url": file_url(receipt["path"])})
        lifecycle = dict(row.get("lifecycle", {}))
        if lifecycle.get("source_path"):
            lifecycle["sources"] = sources([lifecycle.pop("source_path")])
        for stage in lifecycle.get("stage_refs", []):
            require(stage.get("component_id") in components, "lifecycle references an unknown component")
        item["lifecycle"] = lifecycle
        if row.get("candidate"):
            item["candidate"] = {**row["candidate"], "repository": public_url(row["candidate"].get("repository"))}
        joined.append(item)
    for boundary in manifest.get("domain_boundary", []):
        require(boundary.get("component_id") in components, "domain boundary references an unknown component")
    gaps = []
    for gap in manifest.get("top_gaps", []):
        item = {**gap, "sources": sources(gap.get("source_paths", []))}
        item.pop("source_paths", None)
        gaps.append(item)
    foundation = {**manifest, "decisions": joined, "top_gaps": gaps,
        "url": file_url(paths["foundation_manifest"]), "decisions_url": file_url(paths["foundation_decisions"]),
        "counts": {"layers": len(layers), "capabilities": len(joined),
                   "accepted": sum(row.get("review_status") == "accepted_within_scope" for row in joined),
                   "components": len({identifier for row in joined for identifier in row["component_ids"]})}}
    if safe_file(root, FOUNDATION_SURFACES).exists():
        surface_catalog = read(FOUNDATION_SURFACES)
        require(surface_catalog.get("schema_version") == 1, "unsupported foundation surface schema")
        for field in ("checked_at", "scope"):
            require(isinstance(surface_catalog.get(field), str) and surface_catalog[field].strip(),
                    "foundation surfaces need " + field)
        require(isinstance(surface_catalog.get("surfaces"), list)
                and isinstance(surface_catalog.get("layers"), list), "foundation surfaces need lists")

        def identities(values, label):
            require(isinstance(values, list) and all(isinstance(value, str) for value in values),
                    label + " must be a list of identities")
            require(len(values) == len(set(values)), "duplicate " + label)
            return set(values)

        surfaces = {}
        for surface in surface_catalog["surfaces"]:
            require(isinstance(surface, dict), "foundation surface must be an object")
            identifier = surface.get("id")
            require(isinstance(identifier, str) and re.fullmatch(r"[a-z][a-z0-9-]*", identifier),
                    "invalid foundation surface identity")
            require(identifier not in surfaces, "duplicate foundation surface")
            require(surface.get("kind") in {"native-tui", "local-web", "hosted-web", "cli"},
                    "unknown foundation surface kind")
            for field in ("title", "scope"):
                require(isinstance(surface.get(field), str) and surface[field].strip(),
                        "foundation surface needs " + field)
            component_ids = identities(surface.get("component_ids"), "surface components")
            require(component_ids and component_ids.issubset(components),
                    "foundation surface references an unknown component or has none")
            require(bool(public_url(surface.get("upstream_url"))),
                    "foundation surface needs a public HTTPS upstream URL")
            local = surface.get("local_url")
            require(local is None or (surface["kind"] == "local-web" and bool(loopback_url(local))),
                    "foundation surface local URL must be a literal loopback web URL")
            launch = surface.get("launch")
            require(launch is None or (isinstance(launch, str) and launch.strip()),
                    "foundation surface launch must be command text or null")
            item = {**surface, "sources": sources(surface.get("source_paths", []))}
            item.pop("source_paths", None)
            surfaces[identifier] = item
        joins = surface_catalog["layers"]
        require(all(isinstance(row, dict) for row in joins), "surface layer must be an object")
        joined_ids = identities([row.get("layer_id") for row in joins], "surface layer")
        require(joined_ids == set(layer_ids), "foundation surface layers must exactly match foundation layers")
        layer_surfaces = {}
        for row in joins:
            references = identities(row.get("surface_ids"), "layer surface references")
            require(references.issubset(surfaces), "foundation layer references an unknown surface")
            layer_surfaces[row["layer_id"]] = {
                "surfaces": [surfaces[identifier] for identifier in row["surface_ids"]],
                "runbooks": sources(row.get("runbook_paths", []))}
        foundation["layers"] = [{**layer, **layer_surfaces[layer["id"]]} for layer in layers]
        foundation["surface_catalog"] = {"checked_at": surface_catalog["checked_at"],
            "scope": surface_catalog["scope"], "url": file_url(FOUNDATION_SURFACES),
            "text": safe_file(root, FOUNDATION_SURFACES).read_text(encoding="utf-8")}
    engine = {**target["engine"], "repository": public_url(target["engine"].get("repository")),
              "sources": source_links(target["engine"].get("sources", []))}
    brokers = [{**row, "sources": source_links(row.get("sources", []))} for row in target["broker_boundaries"]]
    trading = {**target, "engine": engine, "broker_boundaries": brokers,
               "accepted_references": sources(target.get("accepted_reference_paths", [])),
               "url": file_url(paths["trading_target"])}
    trading.pop("accepted_reference_paths", None)
    for key in ("north_star", "foundation_catalog", "acceptance_plan"):
        if target.get(key):
            trading[key + "_source"] = sources([target[key]])[0]
    return {"foundation": foundation, "trading": trading}


def build_convergence(root, read, file_url):
    """The convergence-by-layer block of the generated component evidence matrix
    (scripts/component_matrix.py), or None without that matrix. The page renders only these counts,
    definitions and dates; a block that disagrees with its own layer rows fails the build."""
    if not safe_file(root, COMPONENT_MATRIX).is_file():
        return None
    matrix = read(COMPONENT_MATRIX)
    block = (matrix.get("summary") or {}).get("convergence") if isinstance(matrix, dict) else None
    require(isinstance(block, dict) and all(key in block for key in CONVERGENCE_SUMMARY_FIELDS),
            "the component matrix has no convergence block; run python3 scripts/component_matrix.py --write")
    rows = matrix.get("rows")
    require(isinstance(rows, list) and all(isinstance(row, dict) for row in rows),
            "component matrix rows must be a list of objects")

    def count(value):
        return type(value) is int and value >= 0

    layers, states, scopes = [], dict.fromkeys(CONVERGENCE_LAYER_STATES, 0), {}
    for row in rows:
        layer = row.get("convergence")
        require(isinstance(layer, dict), "every component matrix row needs a convergence object")
        require(isinstance(row.get("catalog"), str) and isinstance(row.get("layer_id"), str),
                "a convergence row needs its catalog and layer_id")
        require(layer.get("layer_state") in CONVERGENCE_LAYER_STATES, "unknown convergence layer_state")
        require(all(count(layer.get(key)) for key in ("in_use", "converged", "all_rows", "recorded_winner_rows")),
                "convergence counts must be nonnegative integers")
        factors = layer.get("factors")
        require(isinstance(factors, dict) and set(factors) == set(CONVERGENCE_FACTORS)
                and all(isinstance(values, dict) and set(values) == set(CONVERGENCE_FACTOR_VALUES)
                        and all(count(value) for value in values.values()) for values in factors.values()),
                "convergence factors need true/false/unknown integer counts")
        require(all(sum(values.values()) == layer["in_use"] for values in factors.values()),
                "convergence factor counts must add up to in_use")
        unresolved, reopened = layer.get("unresolved"), layer.get("reopened_by")
        require(isinstance(unresolved, list) and all(isinstance(item, dict) and isinstance(item.get("reason"), str)
                                                     for item in unresolved),
                "every unresolved convergence row needs its reason")
        require(isinstance(reopened, list) and all(isinstance(item, dict) and isinstance(item.get("date"), str)
                                                   for item in reopened),
                "convergence reopened_by needs dated sweeps")
        require(layer["converged"] <= min(values["true"] for values in factors.values())
                and layer["in_use"] + len(unresolved) <= layer["all_rows"]
                and layer["recorded_winner_rows"] <= layer["all_rows"], "convergence counts are inconsistent")
        require(layer["converged"] == 0 or layer["layer_state"] == "confirmed_current",
                "only a confirmed_current layer can have converged components")
        found, orphans = layer.get("manifest_layer_found"), layer.get("winners_without_manifest_row")
        require(isinstance(found, bool) and (found or layer["all_rows"] == 0),
                "convergence manifest_layer_found must be true or false, and false only for a layer without "
                "manifest rows")
        require(isinstance(orphans, list) and all(isinstance(item, str) and bool(item) for item in orphans),
                "convergence winners_without_manifest_row must list component ids")
        require(layer.get("invoke") is not None
                or (isinstance(layer.get("invoke_reason"), str) and bool(layer["invoke_reason"].strip())),
                "a null invoke needs its reason")
        states[layer["layer_state"]] += 1
        scope = scopes.setdefault(row["catalog"], dict.fromkeys(CONVERGENCE_SCOPE_COUNTS, 0))
        for key, value in (("layers", 1), ("in_use", layer["in_use"]), ("converged", layer["converged"]),
                           ("unresolved", len(unresolved))):
            scope[key] += value
        layers.append({"catalog": row["catalog"], "layer_id": row["layer_id"], "title": text(row.get("title")),
                       **{key: layer.get(key) for key in CONVERGENCE_LAYER_FIELDS}})
    overall = {key: sum(scope[key] for scope in scopes.values()) for key in CONVERGENCE_SCOPE_COUNTS}
    for scope in (*scopes.values(), overall):
        scope["share"] = round(scope["converged"] / scope["in_use"], 4) if scope["in_use"] else None
    catalogs = block["catalogs"]
    empty = {**dict.fromkeys(CONVERGENCE_SCOPE_COUNTS, 0), "share": None}
    require(block["layer_states"] == states and block["overall"] == overall and isinstance(catalogs, dict)
            and set(scopes) <= set(catalogs)
            and all(catalogs[catalog] == scopes.get(catalog, empty) for catalog in catalogs),
            "the convergence summary differs from its layer rows")
    definitions = block["definitions"]
    require(isinstance(definitions, list) and bool(definitions)
            and all(isinstance(item, dict) and all(isinstance(item.get(key), str) and item[key].strip()
                                                   for key in ("term", "definition")) for item in definitions),
            "convergence definitions must be a nonempty list of terms and definitions")
    unmatched = block["manifest_layers_without_matrix_row"]
    require(isinstance(unmatched, list)
            and all(isinstance(item, dict) and isinstance(item.get("catalog"), str)
                    and isinstance(item.get("layer_id"), str) for item in unmatched)
            and not ({(item["catalog"], item["layer_id"]) for item in unmatched}
                     & {(layer["catalog"], layer["layer_id"]) for layer in layers}),
            "convergence manifest_layers_without_matrix_row must list manifest layers that have no matrix row")
    manifest, sources = block["newest_manifest"], block["sources"]
    require(manifest is None or (isinstance(manifest, dict) and isinstance(manifest.get("path"), str)
                                 and isinstance(manifest.get("checked_at"), str)),
            "the newest convergence sweep manifest needs its path and checked_at")
    require(isinstance(sources, dict) and isinstance(sources.get("completed_sweeps"), list)
            and isinstance(sources.get("host_e2e_platform"), str)
            and isinstance(block["newest_verdict_checked_at"], dict) and isinstance(block["frozen_at"], str),
            "convergence sources need their sweeps, platform and dates")
    return {"url": file_url(COMPONENT_MATRIX), **{key: block[key] for key in CONVERGENCE_SUMMARY_FIELDS},
            "layers": layers}


def token_topic_card(card, edition_date, stack_version, root):
    """Validate one topic row's dated tool card. Returns (card, pin drift note, missing-card marker)."""
    require(edition_date is not None and isinstance(card, dict) and card.get("edition") == edition_date,
            "token topic row needs a card of this edition")
    if card.get("status") == TOKEN_TOPIC_NO_CARD:
        require(set(card) == {"status", "edition"}, "a row without a card carries only the edition marker")
        return dict(card), None, f"No card in this edition ({edition_date})"
    require(card.get("status") == "present", "unknown token topic card status")
    recorded = card.get("recorded_pin")
    require(isinstance(recorded, str) and bool(recorded.strip()), "token topic card needs its recorded pin")
    source = card.get("source")
    require(isinstance(source, dict) and isinstance(source.get("path"), str)
            and source["path"].startswith("evidence/artifacts/"),
            "token topic card source must be a public evidence artifact")
    raw = safe_file(root, source["path"]).read_bytes()
    require(type(source.get("bytes")) is int and source["bytes"] == len(raw) and source.get("sha256") == digest(raw),
            "token topic card source hash or size mismatch")
    for block in TOKEN_TOPIC_CARD_BLOCKS:
        value = card.get(block)
        require(isinstance(value, dict) and isinstance(value.get("evidence_class"), str)
                and bool(value["evidence_class"].strip()),
                "token topic card needs " + block + " with its evidence class")
    comparisons = card["adapted_performance"].get("per_payload_and_lane", [])
    require(isinstance(comparisons, list), "token topic card comparisons must be a list")
    for entry in comparisons:
        # Each figure stays in its own lane, payload and evidence class; nothing is summed across them.
        require(isinstance(entry, dict) and all(isinstance(entry.get(key), str) and entry[key].strip()
                                                for key in ("lane", "payload", "evidence_class")),
                "token topic card comparison needs its lane, payload and evidence class")
        before, after, change = (entry.get(key) for key in ("before_tokens", "after_tokens", "change_pct"))
        require(type(before) is int and type(after) is int and before > 0 and after >= 0
                and type(change) in (int, float) and abs((after - before) * 100 / before - change) <= 0.05 + 1e-9,
                "token topic card comparison counts are inconsistent")
    drift = None
    if recorded != stack_version:
        drift = (f"Pin drift: this card recorded {recorded}; {STACK} now pins {stack_version}. The card's "
                 f"upstream, E2E, performance and review facts describe {recorded} until a newer card edition "
                 "is recorded.")
    return dict(card), drift, None


def build_data(root):
    documents, inputs = {}, {}
    current_public_paths = set()

    def track(path):
        raw = safe_file(root, path).read_bytes()
        inputs[path] = {"path": path, "sha256": digest(raw), "bytes": len(raw), "scope": "whole file"}

    def read(path):
        if path not in documents:
            documents[path] = load(root, path)
            raw = safe_file(root, path).read_bytes()
            scope = "whole file"
            if path == EVIDENCE:
                raw = canonical_json(documents[path]["receipts"]).encode()
                scope = "/receipts; canonical sorted compact UTF-8 JSON (avoids generated-file self-reference)"
            inputs[path] = {"path": path, "sha256": digest(raw), "bytes": len(raw), "scope": scope}
        return documents[path]

    config = read(CONFIG)
    require(config.get("schema_version") == 1, "unsupported explorer manifest version")
    repository_key(config["repository_url"])
    require(bool(re.fullmatch(r"[a-f0-9]{40}", config["source_revision"])), "source revision must be a full commit")
    publication_ref = config.get("publication_ref", "main")
    require(isinstance(publication_ref, str) and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*", publication_ref))
            and ".." not in publication_ref, "unsafe publication ref")
    layers = config["layers"]
    layer_ids = [layer["id"] for layer in layers]
    require(len(set(layer_ids)) == len(layer_ids) and "beyond" in layer_ids,
            "layers need unique identities and a beyond fallback")
    require(all(re.fullmatch(r"[a-z][a-z0-9-]*", value) for value in layer_ids), "invalid layer identity")

    def file_url(path):
        safe_file(root, path)
        # This packet is newer than the immutable base; its own new pages resolve
        # at the public branch after publication, with exact input hashes retained.
        new_catalog = path.startswith(("catalogs/foundation/", "catalogs/landscape/", "docs/landscape-")) or path in config.get("grand_catalogs", {}).values()
        new_practice = path.startswith(("blueprints/native-skill-practice/", "examples/codex-native/agents/semantic-", "examples/claude-native/agents/semantic-"))
        # Artifact bundles that arrived with this packet do not exist at the immutable base.
        new_catalog = new_catalog or path.startswith(("evidence/artifacts/ultracode-token-routing-20260921/", "evidence/artifacts/portable-claude-native-qualification-20260921/", "evidence/artifacts/blind-catalog-convergence-20260921/", "blueprints/blind-catalog-convergence/", "blueprints/memory-lifecycle-probe/", "evidence/artifacts/memory-lifecycle-probe-20260921/", "evidence/receipts/memory-lifecycle-probe-"))
        revision = publication_ref if path.startswith("docs/ecosystem/") or path in NEW_PUBLIC_FILES or new_catalog or new_practice or path in current_public_paths else config["source_revision"]
        return f'{config["repository_url"]}/blob/{revision}/{quote(path, safe="/")}'

    index, stack, evidence, stars, review = (read(path) for path in (INDEX, STACK, EVIDENCE, STARS, REVIEW))
    star_map = {row["repository"].casefold(): row for row in stars["repositories"]}
    require(len(star_map) == stars["count"], "public-star count or duplicate identity mismatch")
    stars_observed_at = stars["retrieved_at"]
    if config.get("landscape_manifest"):
        landscape_manifest = read(config["landscape_manifest"])
        current_public_paths.update(guide["path"] for guide in landscape_manifest.get("handbook_guides", []))
        if landscape_manifest["sources"].get("quality_review"):
            quality_source = read(landscape_manifest["sources"]["quality_review"])
            current_public_paths.add(quality_source["source_snapshot"])
        current_stars = read(landscape_manifest["sources"]["freshness_snapshot"])["stars"]
        require(current_stars.get("status") == "checked", "current public-star snapshot must be checked")
        latest_map = {}
        for row in current_stars["repositories"]:
            key = canonical(repository_key(row["repository"]), index.get("aliases", {}))
            require(key not in latest_map, "duplicate current public-star identity")
            latest_map[key] = {**star_map.get(key, {}), **row}
        star_map = latest_map
        stars_observed_at = current_stars["repository_snapshot_checked_at"]
    receipts_by_id = {row["id"]: row for row in evidence["receipts"]}
    require(len(receipts_by_id) == len(evidence["receipts"]), "duplicate evidence receipt identity")
    receipt_ids = set(TOKEN_RECEIPTS)
    returned_receipt_ids = set()
    selected_ids = {component["id"] for component in stack["components"]}
    for identifier, receipt in receipts_by_id.items():
        family, _, date = identifier.rpartition("-")
        if not re.fullmatch(r"[0-9]{8}", date):
            continue
        if family in TOKEN_RECEIPT_FAMILIES:
            receipt_ids.add(identifier)
        if family in RETURNED_RECEIPT_FAMILIES and receipt.get("kind") in EXECUTION_KINDS:
            require(bool(receipt.get("component_ids")) and
                    set(receipt["component_ids"]).issubset(selected_ids),
                    "returned receipt needs canonical selected components")
            receipt_ids.add(identifier)
            returned_receipt_ids.add(identifier)
    current_public_paths.update(receipts_by_id[identifier]["path"] for identifier in receipt_ids
                                if identifier in receipts_by_id and identifier not in TOKEN_RECEIPTS)
    output, seen = [], set()
    for record in index["records"]:
        key = repository_key(record["repository"])
        require(key not in seen, "duplicate repository identity")
        seen.add(key)
        refs, components, receipts = [], [], []
        role, terms, pins, decisions = "", [], [], []
        reviewed = False
        for ref in record["references"]:
            document = read(ref["path"])
            entry = pointer(document, ref["pointer"])
            require(isinstance(entry, dict), "source pointer must address a record")
            fields = {name: text(entry.get(name) or ref.get(name)) for name in (
                "role", "decision", "disposition", "rationale", "evidence_kind", "evidence_level", "review_level",
                "review_depth", "evidence_depth", "version_or_commit", "source_commit",
                "version", "license", "acceptance_gate")}
            pin = (fields["source_commit"] or text(entry.get("reviewed_source", {}).get("commit"))
                   or fields["version_or_commit"] or fields["version"])
            depth = " ".join(fields[name] for name in (
                "evidence_kind", "evidence_level", "review_level", "review_depth", "evidence_depth"))
            reviewed = reviewed or "source_review" in depth or "primary_source" in depth
            if pin and pin not in pins:
                pins.append(pin)
            if fields["decision"] and fields["decision"] not in decisions:
                decisions.append(fields["decision"])
            if fields["disposition"] and fields["disposition"] not in decisions:
                decisions.append(fields["disposition"])
            role = role or fields["role"] or text(entry.get("description"))
            terms.extend([fields["role"], fields["rationale"], text(entry.get("name")), text(entry.get("layer"))])
            terms.extend(entry.get("layers", []))
            refs.append({"kind": ref["kind"], "path": ref["path"], "pointer": ref["pointer"],
                         "url": file_url(ref["path"]), "date": stamp(entry) if stamp(entry).startswith("20") else stamp(document),
                         "pin": pin, "fields": {k: v for k, v in fields.items() if v},
                         "limitations": entry.get("limitations", []),
                         "sources": source_links(entry.get("sources", entry.get("upstream_sources", [])))})
            if ref["kind"] == "component_record":
                components.append(entry["id"])
                for receipt_id in entry.get("evidence_ids", []):
                    require(receipt_id in receipts_by_id, "component references an unknown receipt")
                    receipt = receipts_by_id[receipt_id]
                    if any(row["id"] == receipt_id for row in receipts):
                        continue
                    detail = read(receipt["path"])
                    receipts.append({"id": receipt_id, "kind": receipt["kind"],
                                     "claim": receipt["claim"], "limitations": receipt["limitations"],
                                     "date": stamp(detail), "url": file_url(receipt["path"])})
        star = star_map.get(key, {})
        role = role or text(star.get("description")) or "Open the source records for this repository's scope."
        terms.extend([key, role, *star.get("topics", [])])
        haystack = " ".join(item for item in terms if isinstance(item, str)).casefold()
        assigned = [layer["id"] for layer in layers if layer["id"] != "beyond" and (
            key in [name.casefold() for name in layer["repositories"]]
            or any(word.casefold() in haystack for word in layer["keywords"]))]
        annotations = []
        for annotation in config.get("annotations", []):
            if annotation["repository"].casefold() == key:
                item = dict(annotation)
                if "path" in item:
                    track(item["path"])
                item["url"] = file_url(item.pop("path")) if "path" in item else public_url(item.get("url"))
                annotations.append(item)
        output.append({"repository_id": key, "name": record["repository"].removeprefix("https://github.com/"),
                       "url": record["repository"], "description": role, "layers": assigned or ["beyond"],
                       "starred": bool(star), "source_reviewed": bool(reviewed),
                       "executed": any(row["kind"] in EXECUTION_KINDS for row in receipts),
                       "live_status": "Unknown on this browser's host", "component_ids": components,
                       "pins": pins, "decisions": decisions, "references": refs,
                       "receipts": receipts, "annotations": annotations,
                       "search": " ".join([haystack, *decisions, *record.get("aliases", [])])})
    require(set(star_map).issubset(seen), "public-star inventory has repositories missing from the canonical index")
    curated = {}
    offline_guide_paths = set()
    for name in ("policies", "guides", "highlights"):
        curated[name] = []
        for value in config[name]:
            item = dict(value)
            if "path" in item:
                path = item.pop("path")
                require(safe_file(root, path).is_file(), "curated source file missing")
                track(path)
                item["url"] = file_url(path)
                if item.pop("offline", False):
                    require(path.endswith(".md"), "offline curated source must be Markdown")
                    item["recipe_path"] = path
                    offline_guide_paths.add(path)
            elif "url" in item:
                item["url"] = public_url(item["url"])
            curated[name].append(item)
    integrations, integration_ids = [], set()
    for entry in config.get("integrations", []):
        require(entry["id"] not in integration_ids, "duplicate integration identity")
        integration_ids.add(entry["id"])
        require(set(entry["layers"]).issubset(layer_ids), "integration uses an unknown layer")
        require(public_url(entry["url"]), "integration needs a public HTTPS source")
        item = {key: entry[key] for key in ("id", "name", "description", "layers", "status", "date", "pin", "url")}
        item["receipt"] = read(entry["receipt_path"])
        item["receipt_url"] = file_url(entry["receipt_path"])
        item["search"] = " ".join([entry["name"], entry["description"], *entry["layers"]]).casefold()
        integrations.append(item)
    awesome = [{"name": item["repository"], "pin": item["source_commit"],
                "date": item["retrieved_at"], "url": public_url(item["readme_url"]),
                "license": item["license_at_pin"]} for item in review["awesome_sources"]]

    # The selected stack drives coverage. A dated audit may lag an added component
    # or version; absence must remain visible instead of becoming acceptance.
    adoption, saturation = read(ADOPTION), read(SATURATION)
    component_ids = [component["id"] for component in stack["components"]]
    require(len(set(component_ids)) == len(component_ids), "duplicate selected component identity")
    require(set(adoption["recipe_map"]) == set(component_ids),
            "recipe map must cover exactly the selected stack")
    audited = {row["component_id"]: row for row in saturation["components"]}
    require(len(audited) == len(saturation["components"]), "duplicate saturation component identity")
    require(set(audited).issubset(component_ids), "saturation references an unknown component")
    profiles = adoption["profiles"]
    profile_ids = [profile["id"] for profile in profiles]
    require(len(set(profile_ids)) == len(profile_ids), "duplicate adoption profile identity")
    for profile in profiles:
        require(set(profile["component_ids"]).issubset(component_ids),
                "adoption profile references an unknown component")
    guide_paths = list(SETUP_GUIDES) + sorted(offline_guide_paths)
    for path in ("docs/claude-foundation-finalization-20260921.md", "examples/claude-native/workflows/README.md", "docs/foundation-convergence-20260921.md", "docs/native-memory-rag-lifecycle.md", "docs/memory-landscape-maintenance.md", "adoption/lifecycle.md", "docs/current-session-observation.md", "docs/token-efficiency-stack.md", "docs/foundation-stack.md", "docs/token-session-handbook.md",
                 "docs/harness-defaults.md", "catalogs/README.md", "catalogs/foundation/README.md",
                 "docs/community-native-practice.md", "examples/claude-native/CLAUDE.md",
                 "recipes/claude-native-ultracode.md", "docs/foundation-rd-readiness.md",
                 "recipes/claude-codex-foreground-review.md", "docs/claude-upstream-checks.md",
                 "docs/claude-repository-evidence.md", "docs/ultracode-token-routing-20260921.md",
                 "recipes/claude-codex-cooperation-lanes.md", "examples/codex-native/README.md",
                 "docs/harness-rules-convergence-20260922.md", "docs/new-workstation-runtime-profile-20260922.md"):
        if (root / path).exists():
            guide_paths.append(path)
    if config.get("landscape_manifest"):
        guide_paths.extend(guide["path"] for guide in landscape_manifest.get("handbook_guides", []))
        guide_paths.extend(["catalogs/landscape/README.md", "docs/landscape-foundation-notes.md",
                            "docs/landscape-domain-notes.md", "docs/landscape-freshness-notes.md"])
        if landscape_manifest["sources"].get("native_practice"):
            guide_paths.extend(["docs/native-skill-practice-20260921.md", "blueprints/native-skill-practice/README.md"])
        if landscape_manifest["sources"].get("research_state"):
            guide_paths.extend(["docs/landscape-continuation.md", "docs/hosting-container-practice.md"])
    documents_to_embed = sorted(set(adoption["recipe_map"].values()) | set(guide_paths))
    recipes = []
    for path in documents_to_embed:
        require(isinstance(path, str) and path.endswith(".md"), "recipe must be repository Markdown")
        track(path)
        recipes.append({"path": path, "url": file_url(path),
                        "text": safe_file(root, path).read_text(encoding="utf-8")})
    selected, comparisons = [], []
    comparison_ids = set()
    for component in stack["components"]:
        identifier = component["id"]
        repositories = [row for row in output if identifier in row["component_ids"]]
        require(len(repositories) == 1, "selected component must join exactly one catalog repository")
        repository = repositories[0]
        audit = audited.get(identifier)
        status = "missing" if audit is None else (
            "matched_version" if audit.get("version") == component.get("version") else "different_version")
        if audit:
            for receipt_ref in audit.get("functional_evidence", {}).get("public_receipts", []):
                registered = receipts_by_id.get(receipt_ref["id"])
                require(registered is not None and registered["path"] == receipt_ref["path"],
                        "saturation receipt must match registered evidence")
            for row in audit.get("artifact_baselines", []):
                require(row["id"] not in comparison_ids, "duplicate artifact comparison identity")
                comparison_ids.add(row["id"])
                before, after, removed = (row.get(key) for key in (
                    "baseline_tokens", "candidate_tokens", "tokens_removed"))
                require(all(type(value) is int for value in (before, after, removed))
                        and before >= 0 and after >= 0 and before - after == removed,
                        "artifact comparison counts are inconsistent")
                comparisons.append({**row, "component_id": identifier, "audit_status": status,
                                    "recorded_at": stamp(saturation), "source_url": file_url(SATURATION)})
        selected.append({"id": identifier, "repository": repository["url"],
                         "version": component.get("version", "Not recorded"),
                         "license": component.get("license", "Not recorded"),
                         "role": component.get("role", ""), "tier": component.get("profile", ""),
                         "commands": component.get("commands", []),
                         "command_scope": component.get("command_scope", "See the full native recipe and its recorded boundaries."),
                         "layers": repository["layers"],
                         "profiles": [p["id"] for p in profiles if identifier in p["component_ids"]],
                         "recipe_path": adoption["recipe_map"][identifier],
                         "audit_status": status, "audit": audit, "receipts": repository["receipts"],
                         "returned_receipt_ids": sorted(receipt_id for receipt_id in returned_receipt_ids
                             if identifier in receipts_by_id[receipt_id]["component_ids"]),
                         "current_host_acceptance": "Unknown on this browser's host"})
    token_receipts = []
    artifact_bytes = 0
    for receipt_id in sorted(receipt_ids):
        require(receipt_id in receipts_by_id, "required token receipt is unregistered")
        receipt = receipts_by_id[receipt_id]
        detail = read(receipt["path"])
        require(detail.get("id") == receipt_id, "token receipt identity differs from registration")
        artifacts = []
        # Only files explicitly designated public by a selected execution receipt
        # are embedded. References and raw/private log paths are never traversed.
        if receipt_id in returned_receipt_ids:
            for declaration in detail.get("public_artifacts", []):
                path = declaration.get("path", "")
                require(path.startswith("evidence/artifacts/"), "returned artifact must be in public evidence/artifacts")
                target = safe_file(root, path)
                require(target.stat().st_size <= PUBLIC_ARTIFACT_LIMIT, "returned artifact exceeds size limit")
                raw = target.read_bytes()
                require(type(declaration.get("bytes")) is int and declaration["bytes"] == len(raw)
                        and declaration.get("sha256") == digest(raw), "returned artifact hash or size mismatch")
                artifact_bytes += len(raw)
                require(artifact_bytes <= PUBLIC_BUNDLE_LIMIT, "returned artifact bundle exceeds size limit")
                require(target.suffix.lower() in {".json", ".md", ".txt", ".png"}, "unsupported public returned artifact type")
                artifact = {"path": path, "bytes": len(raw), "sha256": digest(raw)}
                if target.suffix.lower() == ".png":
                    require(raw.startswith(b"\x89PNG\r\n\x1a\n"), "returned screenshot must be PNG")
                    artifact.update(mime_type="image/png", content_base64=base64.b64encode(raw).decode("ascii"))
                else:
                    artifact.update(mime_type="text/plain", text=raw.decode("utf-8"))
                track(path)
                current_public_paths.add(path)
                artifact["url"] = file_url(path)
                artifacts.append(artifact)
        token_receipts.append({"id": receipt_id, "url": file_url(receipt["path"]), "record": detail,
                               "kind": receipt["kind"], "component_ids": receipt.get("component_ids", []),
                               "artifacts": artifacts, "returned_results": receipt_id in returned_receipt_ids})
    selection_policy = []
    for entry in config.get("selection_policy", []):
        item = dict(entry)
        item["sources"] = []
        for path in item.pop("source_paths", []):
            track(path)
            item["sources"].append({"path": path, "url": file_url(path)})
        selection_policy.append(item)
    token_topic = {"rows": [], "scope": "No topic-specific evidence packet is present."}
    if (root / TOKEN_TOPIC).exists():
        topic_source = read(TOKEN_TOPIC)
        require(topic_source.get("schema_version") == 1, "unsupported token topic schema")
        require(isinstance(topic_source.get("rows"), list), "token topic rows must be a list")
        edition = topic_source.get("edition")
        require(edition is None or (isinstance(edition, dict) and isinstance(edition.get("date_utc"), str)
                                    and bool(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", edition["date_utc"]))
                                    and isinstance(edition.get("source_paths", []), list)),
                "token topic edition needs its date and evidence paths")
        edition_date = edition["date_utc"] if edition else None
        if edition:
            # A dated edition and its card artifacts are newer than the immutable base:
            # resolve them at the publication ref, with exact input hashes retained.
            current_public_paths.add(TOKEN_TOPIC)
            current_public_paths.update(edition.get("source_paths", []))
            current_public_paths.update(row["card"]["source"]["path"] for row in topic_source["rows"]
                                        if isinstance(row.get("card"), dict)
                                        and isinstance(row["card"].get("source"), dict)
                                        and isinstance(row["card"]["source"].get("path"), str))
        selected_by_id = {row["id"]: row for row in selected}
        stack_by_id = {component["id"]: component for component in stack["components"]}
        topic_ids = set()
        topic_rows = []
        for row in topic_source["rows"]:
            identifier = row.get("component_id")
            require(identifier in selected_by_id and identifier not in topic_ids,
                    "token topic component must be selected and unique")
            require(not {"version", "pin", "repository"} & set(row),
                    "token topic pins come from manifests/stack.json, not the row")
            require(row.get("group") in {"core", "observation", "runtime"},
                    "unknown token topic group")
            require(isinstance(row.get("source_paths"), list) and row["source_paths"],
                    "token topic row needs evidence paths")
            for field in ("purpose", "returned_result_summary", "baseline_summary", "lifecycle_summary"):
                require(isinstance(row.get(field), str) and row[field].strip(),
                        "token topic row needs an explicit " + field)
            for field in ("session_statistics", "lifetime_statistics"):
                meter = row.get(field)
                require(isinstance(meter, dict) and isinstance(meter.get("summary"), str)
                        and meter["summary"].strip(), "token topic needs scoped " + field)
            require(isinstance(row.get("upstream_commands"), dict) and row["upstream_commands"].get("use"),
                    "token topic needs an upstream use command")
            topic_ids.add(identifier)
            component = selected_by_id[identifier]
            pinned = stack_by_id[identifier]
            item = dict(row)
            item.update(repository=component["repository"], version=component["version"],
                        recipe_path=component["recipe_path"], sources=[],
                        pin={"version": component["version"], "repository": pinned.get("repository", ""),
                             "source": STACK},
                        pin_drift=None, card_marker=None)
            for path in item.pop("source_paths"):
                track(path)
                item["sources"].append({"path": path, "url": file_url(path)})
            if edition or "card" in row:
                card, item["pin_drift"], item["card_marker"] = token_topic_card(
                    row.get("card"), edition_date, component["version"], root)
                if "source" in card:
                    track(card["source"]["path"])
                    card["source"] = {**card["source"], "url": file_url(card["source"]["path"])}
                item["card"] = card
            topic_rows.append(item)
        token_topic = {**topic_source, "rows": topic_rows, "url": file_url(TOKEN_TOPIC)}
        if edition:
            sources = []
            for path in edition.get("source_paths", []):
                require(isinstance(path, str), "token topic edition evidence path must be text")
                track(path)
                sources.append({"path": path, "url": file_url(path)})
            token_topic["edition"] = {**{key: value for key, value in edition.items() if key != "source_paths"},
                                      "sources": sources}
    grand_catalogs = build_grand_catalogs(config, stack, receipts_by_id, read, track, file_url, root)
    landscape = None
    if config.get("landscape_manifest"):
        landscape = build_landscape(root, config["landscape_manifest"], read=read,
                                    track=track, file_url=file_url)
    convergence = build_convergence(root, read, file_url)
    return {"schema_version": 1, "snapshot_date": config["snapshot_date"],
            "repository_url": config["repository_url"], "source_revision": config["source_revision"],
            "stars_observed_at": stars_observed_at, "historical_star_audit_count": stars["count"],
            "component_snapshot_at": stamp(stack),
            "counts": {"repositories": len(output), "stars": len(star_map),
                       "components": len(stack["components"]),
                       "source_reviewed": sum(row["source_reviewed"] for row in output),
                       "executed": sum(row["executed"] for row in output)},
            "layers": layers, "repositories": output, "integrations": integrations, "awesome": awesome,
            "grand_catalogs": grand_catalogs, "landscape": landscape, "convergence": convergence,
            "setup": {"components": selected, "profiles": profiles, "recipes": recipes,
                      "default_profile": adoption["default_profile"],
                      "supported_platforms": adoption.get("supported_platforms", []),
                      "acceptance_target": adoption.get("acceptance_target", {}),
                      "stack_scope": stack.get("scope", ""), "audit_scope": saturation.get("scope", ""),
                      "audit_date": stamp(saturation),
                      "missing_audit_count": sum(row["audit_status"] == "missing" for row in selected)},
            "efficiency": {"comparisons": comparisons, "receipts": token_receipts,
                           "counter_policy": saturation.get("counter_policy", {}),
                           "selection_policy": selection_policy, "topic": token_topic},
            "inputs": sorted(inputs.values(), key=lambda row: row["path"]), **curated}


class InlineScripts(HTMLParser):
    """Bodies of attribute-less <script> elements (tag case, end-tag whitespace and
    attributes handled like a browser). `opened` counts every script start tag so a
    caller can require it to match the raw "<script" count: html.parser hides a script
    inside a comment or a self-closing <script/> that a browser would still run."""

    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.bodies, self.body, self.opened, self.self_closed = [], None, 0, 0
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.opened += 1
            self.body = None if attrs else []

    def handle_startendtag(self, tag, attrs):
        if tag == "script":
            self.opened += 1
            self.self_closed += 1

    def handle_data(self, data):
        if self.body is not None:
            self.body.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.body is not None:
            self.bodies.append("".join(self.body))
            self.body = None


def render_from_data(data, root):
    template = safe_file(root, TEMPLATE).read_text(encoding="utf-8")
    require(template.count("@@DATA@@") == 1, "template must have one embedded data marker")
    encoded = canonical_json(data).replace("&", "\\u0026").replace("<", "\\u003c").replace(
        ">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    body = '<noscript><h2>JavaScript is disabled</h2><p>Enable JavaScript for local search and filters. '
    body += 'No data leaves this page. Public source repository: <a href="'
    body += html.escape(data["repository_url"], quote=True) + '">native-agent-stack</a>.</p></noscript>'
    result = template.replace("@@DATA@@", encoded).replace("<!--@@BODY@@-->", body)
    parsed = InlineScripts(result)
    scripts = parsed.bodies
    require(len(scripts) == 1 and not parsed.self_closed and parsed.opened == result.lower().count("<script"),
            "template must have one inline application script")
    script_hash = base64.b64encode(hashlib.sha256(scripts[0].encode()).digest()).decode()
    return result.replace("@@SCRIPT_HASH@@", script_hash).encode("utf-8")


def render(root):
    return render_from_data(build_data(root), root)


def input_digest(data, root):
    """sha256 over the sorted list of every input path this build actually read
    (path, sha256, bytes, scope) plus the HTML template render_from_data reads,
    so the report is tied to exact source content."""
    template = safe_file(root, TEMPLATE).read_bytes()
    return digest(canonical_json({"inputs": data["inputs"],
                                  "template": {"path": str(TEMPLATE), "sha256": digest(template)}}).encode())


def check(root):
    """Build twice, each time into its own temporary directory, and require
    byte-identical output. docs/ecosystem/index.html is no longer committed,
    so --check has nothing checked-in to compare against; this instead
    verifies the build is deterministic from the current repository state."""
    with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
        data = build_data(root)
        (Path(first) / "index.html").write_bytes(render_from_data(data, root))
        first_bytes = (Path(first) / "index.html").read_bytes()
        # The second build runs in a separate interpreter with a different hash seed, so
        # set/dict-order nondeterminism that one process would hide still fails the check.
        target = Path(second) / "index.html"
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--root", str(root), "--render-to", str(target)],
            env=dict(os.environ, PYTHONHASHSEED="1" if os.environ.get("PYTHONHASHSEED") != "1" else "2"),
            capture_output=True, text=True, check=False)
        require(proc.returncode == 0, f"second-process explorer build failed: {(proc.stdout + proc.stderr)[-400:]}")
        second_bytes = target.read_bytes()
    require(first_bytes == second_bytes,
            "explorer build is not deterministic across two independent builds (separate processes and hash seeds)")
    return first_bytes, input_digest(data, root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Rebuild the public HTML (writes it locally; not committed)")
    mode.add_argument("--check", action="store_true", help="Check deterministic rebuild (default)")
    mode.add_argument("--render-to", type=Path, help=argparse.SUPPRESS)  # used by --check for the second-process build
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        if args.render_to:
            args.render_to.write_bytes(render(root))
            return 0
        if args.write:
            result = render(root)
            safe_file(root, OUTPUT).write_bytes(result)
            report = {"status": "written", "bytes": len(result), "sha256": digest(result)}
        else:
            result, source_digest = check(root)
            report = {"status": "passed", "bytes": len(result), "output_sha256": digest(result),
                      "input_sha256": source_digest}
    except (InvalidDecisionIndex, OSError, ValueError, KeyError, TypeError) as error:
        print(f"Explorer validation failed: {error}")
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
