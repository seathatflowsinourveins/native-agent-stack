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


def repository_key(value):
    require(public_url(value) == value and bool(re.fullmatch(
        r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value)),
        "repository must be a canonical public GitHub HTTPS URL")
    return value.removeprefix("https://github.com/").casefold()


def stamp(value):
    for key in ("retrieved_at", "checked_at", "recorded_at_utc", "recorded_at",
                "observed_at_utc", "observed_at", "executed_at", "date"):
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


def build_data(root):
    documents, inputs = {}, {}

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
        revision = "main" if path.startswith("docs/ecosystem/") else config["source_revision"]
        return f'{config["repository_url"]}/blob/{revision}/{quote(path, safe="/")}'

    index, stack, evidence, stars, review = (read(path) for path in (INDEX, STACK, EVIDENCE, STARS, REVIEW))
    star_map = {row["repository"].casefold(): row for row in stars["repositories"]}
    require(len(star_map) == stars["count"], "public-star count or duplicate identity mismatch")
    receipts_by_id = {row["id"]: row for row in evidence["receipts"]}
    require(len(receipts_by_id) == len(evidence["receipts"]), "duplicate evidence receipt identity")
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
    return {"schema_version": 1, "snapshot_date": config["snapshot_date"],
            "repository_url": config["repository_url"], "source_revision": config["source_revision"],
            "stars_observed_at": stars["retrieved_at"], "component_snapshot_at": stamp(stack),
            "counts": {"repositories": len(output), "stars": len(star_map),
                       "components": len(stack["components"]),
                       "source_reviewed": sum(row["source_reviewed"] for row in output),
                       "executed": sum(row["executed"] for row in output)},
            "layers": layers, "repositories": output, "integrations": integrations, "awesome": awesome,
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
