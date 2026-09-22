#!/usr/bin/env python3
"""Build/check the self-contained public explorer, without network or dependencies."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import quote, urlsplit

try:
    from .catalog_decisions import InvalidDecisionIndex, load, pointer, safe_file
except ImportError:
    from catalog_decisions import InvalidDecisionIndex, load, pointer, safe_file


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
    "claude-foundation-finalization",
    "native-returned-results", "native-memory-rag-alignment", "hf-memory-models",
    "native-dashboard-data", "native-dashboard-access", "full-stack-convergence",
    "dashboard-render-e2e", "dashboard-gap-resolution", "memory-landscape", "memory-landscape-lifecycle", "foundation-convergence",
    "foundation-rd",
    "claude-upstream-checks",
}
PUBLIC_ARTIFACT_LIMIT = 2 * 1024 * 1024
PUBLIC_BUNDLE_LIMIT = 16 * 1024 * 1024
NEW_PUBLIC_FILES = {"adoption/lifecycle.md", "evidence/receipts/token-practice-confirmation-20260920.json",
                    "docs/claude-upstream-checks.md", "docs/ecosystem/claude-upstream-checks.html",
                    "evidence/artifacts/claude-upstream-checks-20260921/results.json",
                    "evidence/artifacts/claude-upstream-checks-20260921/provenance.json",
                    "evidence/artifacts/claude-upstream-checks-20260921/grand-dashboard-6h-20260921.png",
                    "evidence/artifacts/claude-upstream-checks-20260921/grand-dashboard-72h-20260921.png",
                    "evidence/artifacts/claude-upstream-checks-20260921/token-savings-manifest-page-20260921.png",
                    "docs/claude-foundation-finalization-20260921.md", "examples/claude-native/workflows/README.md",
                    "docs/foundation-rd-readiness.md", "recipes/claude-codex-foreground-review.md",
                    "evidence/artifacts/foundation-rd-20260921/qmd-comparison.json",
                    "evidence/artifacts/foundation-rd-20260921/qmd-bench-output.txt",
                    "evidence/artifacts/foundation-rd-20260921/native-review.json",
                    "recipes/claude-native-ultracode.md", "examples/claude-native/ultracode.settings.json",
                    "docs/ultracode-token-routing-20260921.md", "recipes/claude-codex-cooperation-lanes.md", "examples/codex-native/README.md",
                    "docs/harness-rules-convergence-20260922.md", "docs/new-workstation-runtime-profile-20260922.md",
                    "evidence/artifacts/harness-rules-convergence-20260922/runs.json",
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
    layers = config["layers"]
    layer_ids = [layer["id"] for layer in layers]
    require(len(set(layer_ids)) == len(layer_ids) and "beyond" in layer_ids,
            "layers need unique identities and a beyond fallback")
    require(all(re.fullmatch(r"[a-z][a-z0-9-]*", value) for value in layer_ids), "invalid layer identity")

    def file_url(path):
        safe_file(root, path)
        # This packet is newer than the immutable base; its own new pages resolve
        # at the public branch after publication, with exact input hashes retained.
        new_catalog = path.startswith("catalogs/foundation/") or path in config.get("grand_catalogs", {}).values()
        # Artifact bundles that arrived with this packet do not exist at the immutable base.
        new_catalog = new_catalog or path.startswith(("evidence/artifacts/ultracode-token-routing-20260921/", "evidence/artifacts/portable-claude-native-qualification-20260921/"))
        revision = "main" if path.startswith("docs/ecosystem/") or path in NEW_PUBLIC_FILES or new_catalog or path in current_public_paths else config["source_revision"]
        return f'{config["repository_url"]}/blob/{revision}/{quote(path, safe="/")}'

    index, stack, evidence, stars, review = (read(path) for path in (INDEX, STACK, EVIDENCE, STARS, REVIEW))
    star_map = {row["repository"].casefold(): row for row in stars["repositories"]}
    require(len(star_map) == stars["count"], "public-star count or duplicate identity mismatch")
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
                "role", "decision", "rationale", "evidence_level", "review_level",
                "review_depth", "evidence_depth", "version_or_commit", "source_commit",
                "version", "license", "acceptance_gate")}
            pin = (fields["source_commit"] or text(entry.get("reviewed_source", {}).get("commit"))
                   or fields["version_or_commit"] or fields["version"])
            depth = " ".join(fields[name] for name in (
                "evidence_level", "review_level", "review_depth", "evidence_depth"))
            reviewed = reviewed or "source_review" in depth or "primary_source" in depth
            if pin and pin not in pins:
                pins.append(pin)
            if fields["decision"] and fields["decision"] not in decisions:
                decisions.append(fields["decision"])
            role = role or fields["role"] or text(entry.get("description"))
            terms.extend([fields["role"], text(entry.get("layer"))])
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
    for name in ("policies", "guides", "highlights"):
        curated[name] = []
        for value in config[name]:
            item = dict(value)
            if "path" in item:
                path = item.pop("path")
                require(safe_file(root, path).is_file(), "curated source file missing")
                track(path)
                item["url"] = file_url(path)
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
    guide_paths = list(SETUP_GUIDES)
    for path in ("docs/claude-foundation-finalization-20260921.md", "examples/claude-native/workflows/README.md", "docs/foundation-convergence-20260921.md", "docs/native-memory-rag-lifecycle.md", "docs/memory-landscape-maintenance.md", "adoption/lifecycle.md", "docs/current-session-observation.md", "docs/token-efficiency-stack.md", "docs/foundation-stack.md", "docs/token-session-handbook.md",
                 "docs/harness-defaults.md", "catalogs/README.md", "catalogs/foundation/README.md",
                 "docs/community-native-practice.md", "examples/claude-native/CLAUDE.md",
                 "recipes/claude-native-ultracode.md", "docs/foundation-rd-readiness.md",
                 "recipes/claude-codex-foreground-review.md", "docs/claude-upstream-checks.md",
                 "docs/ultracode-token-routing-20260921.md", "recipes/claude-codex-cooperation-lanes.md", "examples/codex-native/README.md",
                 "docs/harness-rules-convergence-20260922.md", "docs/new-workstation-runtime-profile-20260922.md"):
        if (root / path).exists():
            guide_paths.append(path)
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
        selected_by_id = {row["id"]: row for row in selected}
        topic_ids = set()
        topic_rows = []
        for row in topic_source["rows"]:
            identifier = row.get("component_id")
            require(identifier in selected_by_id and identifier not in topic_ids,
                    "token topic component must be selected and unique")
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
            item = dict(row)
            item.update(repository=component["repository"], version=component["version"],
                        recipe_path=component["recipe_path"], sources=[])
            for path in item.pop("source_paths"):
                track(path)
                item["sources"].append({"path": path, "url": file_url(path)})
            topic_rows.append(item)
        token_topic = {**topic_source, "rows": topic_rows, "url": file_url(TOKEN_TOPIC)}
    grand_catalogs = build_grand_catalogs(config, stack, receipts_by_id, read, track, file_url, root)
    return {"schema_version": 1, "snapshot_date": config["snapshot_date"],
            "repository_url": config["repository_url"], "source_revision": config["source_revision"],
            "stars_observed_at": stars["retrieved_at"], "component_snapshot_at": stamp(stack),
            "counts": {"repositories": len(output), "stars": len(star_map),
                       "components": len(stack["components"]),
                       "source_reviewed": sum(row["source_reviewed"] for row in output),
                       "executed": sum(row["executed"] for row in output)},
            "layers": layers, "repositories": output, "integrations": integrations, "awesome": awesome,
            "grand_catalogs": grand_catalogs,
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


def render(root):
    data = build_data(root)
    template = safe_file(root, TEMPLATE).read_text(encoding="utf-8")
    require(template.count("@@DATA@@") == 1, "template must have one embedded data marker")
    encoded = canonical_json(data).replace("&", "\\u0026").replace("<", "\\u003c").replace(
        ">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    body = '<noscript><h2>JavaScript is disabled</h2><p>Enable JavaScript for local search and filters. '
    body += 'No data leaves this page. Public source repository: <a href="'
    body += html.escape(data["repository_url"], quote=True) + '">native-agent-stack</a>.</p></noscript>'
    result = template.replace("@@DATA@@", encoded).replace("@@BODY@@", body)
    scripts = re.findall(r"<script>(.*?)</script>", result, re.S)
    require(len(scripts) == 1, "template must have one inline application script")
    script_hash = base64.b64encode(hashlib.sha256(scripts[0].encode()).digest()).decode()
    return result.replace("@@SCRIPT_HASH@@", script_hash).encode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Rebuild the public HTML")
    mode.add_argument("--check", action="store_true", help="Check exact rebuild equality (default)")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        result = render(root)
        target = safe_file(root, OUTPUT)
        if args.write:
            target.write_bytes(result)
        else:
            require(target.is_file() and target.read_bytes() == result,
                    "generated HTML is stale or changed; rebuild with --write")
    except (InvalidDecisionIndex, OSError, ValueError, KeyError, TypeError) as error:
        print(f"Explorer validation failed: {error}")
        return 1
    print(json.dumps({"status": "written" if args.write else "passed", "bytes": len(result),
                      "sha256": digest(result)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
