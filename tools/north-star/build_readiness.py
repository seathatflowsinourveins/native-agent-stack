#!/usr/bin/env python3
"""Join retained receipt facts without invoking tools or adjudicating their gates.

Reference adapter: scripts/component_matrix.py (--check/--write), and Python 3.13
json/hashlib/pathlib. Provenance semantics: in-toto Statement v1 and SLSA v1.2.
This local view is neither a signed attestation nor RFC 8785 canonical JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path("catalogs/north-star/readiness.json")
SPEC = Path("tools/north-star/sources.json")
MAX_SOURCE_BYTES = 8 * 1024 * 1024


def unique_json(raw: bytes) -> Any:
    """Reject duplicate names and non-JSON constants, as upstream json supports."""
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value: str) -> Any:
        raise ValueError(f"non-JSON constant: {value}")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def pointer(document: Any, path: str) -> Any:
    if path == "":
        return document
    if not path.startswith("/"):
        raise ValueError("JSON Pointer must start with /")
    for part in path[1:].split("/"):
        if re.search(r"~(?![01])", part):
            raise ValueError("invalid JSON Pointer escape")
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(document, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", part):
                raise ValueError("invalid JSON Pointer array index")
            document = document[int(part)]
        else:
            document = document[part]
    return document


class Receipts:
    """Read only named, confined sources and retain identity before parsing."""
    def __init__(self, root: Path, state_root: Path, sources: dict[str, Any]):
        self.roots = {"repo": root.resolve(), "state": state_root.resolve()}
        self.sources = sources
        self.records: dict[str, dict[str, Any]] = {}
        self.raw: dict[str, bytes | None] = {}
        self.parsed: dict[str, Any] = {}

    def get(self, name: str) -> dict[str, Any]:
        if name in self.records:
            return self.records[name]
        source = self.sources[name]
        base = self.roots[source["root"]]
        relative = Path(source["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"source must be a relative confined path: {name}")
        path = base / relative
        if not path.resolve().is_relative_to(base):
            raise ValueError(f"source escapes its root: {name}")
        record: dict[str, Any] = {
            "root": source["root"], "path": relative.as_posix(),
            "sha256": None, "bytes": None, "status": "UNVERIFIED",
        }
        raw = None
        try:
            with path.open("rb") as handle:
                raw = handle.read(MAX_SOURCE_BYTES + 1)
            if len(raw) > MAX_SOURCE_BYTES:
                raise ValueError("source exceeds 8 MiB bound")
            record.update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
            expected = source.get("expected_sha256")
            if expected is not None:
                record["expected_sha256"] = expected
            if expected is not None and record["sha256"] != expected:
                record["reason"] = "receipt bytes differ from the declared binding"
            else:
                record["status"] = "RECORDED"
        except (OSError, ValueError) as error:
            record["reason"] = (f"{type(error).__name__}: receipt is missing or unreadable"
                                if isinstance(error, OSError) else str(error))
            raw = None
        self.records[name], self.raw[name] = record, raw
        return record

    def document(self, name: str) -> Any:
        record = self.get(name)
        if record["status"] != "RECORDED":
            return None
        if name not in self.parsed:
            try:
                self.parsed[name] = unique_json(self.raw[name])
            except (ValueError, UnicodeError) as error:
                record.update(status="UNVERIFIED", reason=f"invalid JSON: {error}")
                self.parsed[name] = None
        return self.parsed[name]

    def reference(self, name: str, locator: str) -> dict[str, Any]:
        record = self.get(name)
        return {key: record[key] for key in ("root", "path", "sha256")} | {
            "locator": locator,
        }

    def unknown(self, name: str, locator: str, reason: str) -> dict[str, Any]:
        return {"value": None, "status": "UNVERIFIED", "reason": reason,
                "receipt": self.reference(name, locator)}

    def fact(self, name: str, locator: str, value: Any) -> dict[str, Any]:
        record = self.get(name)
        if record["status"] != "RECORDED":
            return self.unknown(name, locator, record.get("reason", "unavailable receipt"))
        if value is None:
            return self.unknown(name, locator, "receipt does not establish this field")
        return {"value": value, "status": "RECORDED",
                "receipt": self.reference(name, locator)}

    def claim(self, selector: dict[str, Any]) -> dict[str, Any]:
        name = selector["source"]
        if "pointer" in selector:
            location = selector["pointer"]
            document = self.document(name)
            try:
                value = pointer(document, location)
            except (KeyError, IndexError, TypeError, ValueError):
                return self.unknown(name, location, "JSON Pointer is absent or invalid")
            return self.fact(name, location, value)
        expression = selector["regex"]
        record = self.get(name)
        if record["status"] != "RECORDED":
            return self.unknown(name, "regex:" + expression, record.get("reason", "unavailable receipt"))
        try:
            text = self.raw[name].decode("utf-8")
            matches = list(re.finditer(expression, text, re.MULTILINE))
            if len(matches) != 1:
                return self.unknown(name, "regex:" + expression,
                                    f"selector matched {len(matches)} times; exactly one required")
            match = matches[0]
            line = text.count("\n", 0, match.start()) + 1
            value = match.group("value")
        except (UnicodeError, re.error, IndexError) as error:
            return self.unknown(name, "regex:" + expression, f"invalid text selector: {error}")
        return self.fact(name, f"line:{line};regex:{expression}", value)

    def linked(self, root: str, path: str, expected: str | None = None) -> str:
        name = f"{root}:{path}" + (f"@{expected}" if expected else "")
        if name not in self.sources:
            self.sources[name] = {"root": root, "path": path}
            if expected:
                self.sources[name]["expected_sha256"] = expected
        self.get(name)
        return name


def records(spec: dict[str, Any], section: str, receipts: Receipts) -> list[dict[str, Any]]:
    return [
        {"id": row["id"], "title": row.get("title", row["id"]),
         "fields": {key: receipts.claim(value) for key, value in sorted(row["fields"].items())}}
        for row in spec.get(section, [])
    ]


def build_layers(receipts: Receipts) -> list[dict[str, Any]]:
    foundation = receipts.document("foundation") or {}
    stack = receipts.document("stack") or {}
    evidence = receipts.document("evidence") or {}
    profile = receipts.document("profile") or {}
    components = {row["id"]: (index, row) for index, row in enumerate(stack.get("components", []))}
    registered = {row["id"]: row for row in evidence.get("receipts", [])}
    hashes = {row["path"]: row["sha256"] for row in evidence.get("files", [])}
    layers = []
    for index, layer in enumerate(foundation.get("layers", [])):
        prefix = f"/layers/{index}"
        tools = []
        for winner_index, winner in enumerate(layer.get("winners", [])):
            path = f"{prefix}/winners/{winner_index}"
            component_id = winner.get("component_id")
            fields = {key: receipts.fact("foundation", f"{path}/{key}", winner.get(key))
                      for key in ("component_id", "repository", "pin", "evidence_class", "recipe_ref")}
            component_index, component = components.get(component_id, (None, {}))
            component_path = f"/components/{component_index}"
            fields["recorded_stack_pin"] = receipts.fact("stack", component_path + "/version", component.get("version"))
            fields["documented_commands"] = receipts.fact("stack", component_path + "/commands", component.get("commands"))
            fields["fresh_session_invoke"] = receipts.unknown(
                "foundation", path, "selection and command records do not bind a fresh-session invocation")
            fields["install_receipt"] = receipts.unknown(
                "stack", component_path + "/evidence_ids", "registered support is not a current pin-bound install receipt")
            fields["pin_agreement"] = receipts.fact(
                "stack", component_path + "/version", component.get("version") == winner.get("pin")) if component else receipts.unknown(
                    "stack", "/components", "selected component is absent from the stack ledger")
            fields["pin_agreement"]["inputs"] = [fields["pin"]["receipt"], fields["recorded_stack_pin"]["receipt"]]
            fields["pin_agreement"]["derivation"] = "selection pin equals recorded stack version"
            examples = []
            for entry_index, entry in enumerate(profile.get("entries", [])):
                if component_id is not None and entry.get("component_id") == component_id:
                    examples.append({key: receipts.fact("profile", f"/entries/{entry_index}/{key}", entry.get(key))
                                     for key in ("pin", "install", "acceptance", "provisioning_status")})
            support = []
            for receipt_id in component.get("evidence_ids", []):
                declaration = registered.get(receipt_id)
                if not declaration or not isinstance(declaration.get("path"), str):
                    continue
                receipt_path = declaration["path"]
                source = receipts.linked("repo", receipt_path, hashes.get(receipt_path))
                document = receipts.document(source)
                support.append({"id": receipt_id, "receipt": receipts.reference(source, ""),
                                "binding": receipts.get(source)["status"],
                                "kind": receipts.fact(source, "/kind", document.get("kind") if isinstance(document, dict) else None)})
            tools.append({"id": component_id or f"winner-{winner_index}", "fields": fields,
                          "documented_examples": examples, "supporting_receipts": support})
        layers.append({"id": layer["layer_id"], "title": receipts.fact("foundation", prefix + "/title", layer.get("title")),
                       "selected_tools": tools,
                       "inventory_date": receipts.fact("foundation", "/checked_at", foundation.get("checked_at"))})
    return sorted(layers, key=lambda row: row["id"])


def build_sdks(spec: dict[str, Any], receipts: Receipts) -> dict[str, Any]:
    contract = receipts.document("sdk_contract")
    index = receipts.document("sdk_rows")
    output: dict[str, Any] = {"contract": receipts.reference("sdk_contract", ""),
                              "index": receipts.reference("sdk_rows", ""), "items": []}
    seen = set()
    if isinstance(index, dict):
        for position, item in enumerate(index.get("items", [])):
            identity = item["id"]
            if identity in seen:
                raise ValueError(f"duplicate SDK item identity: {identity}")
            seen.add(identity)
            absolute = Path(item["receipt_path"])
            if not absolute.is_absolute():
                raise ValueError(f"SDK receipt_path must be absolute: {identity}")
            state_root = receipts.roots["state"]
            if not absolute.resolve().is_relative_to(state_root):
                raise ValueError(f"SDK receipt escapes state root: {identity}")
            source = receipts.linked("state", absolute.relative_to(state_root).as_posix(), item.get("receipt_sha256"))
            declaration = f"/items/{position}"
            fields = {}
            required_hash = item.get("receipt_sha256")
            valid_binding = isinstance(required_hash, str) and re.fullmatch(r"[0-9a-f]{64}", required_hash)
            payload = receipts.document(source)
            bound = bool(valid_binding and receipts.get(source)["status"] == "RECORDED"
                         and isinstance(payload, dict) and payload.get("id") == identity)
            raw_reference = None
            raw_binding = "UNVERIFIED"
            if bound and isinstance(payload.get("raw_receipt"), dict):
                raw_receipt = payload["raw_receipt"]
                raw_path = Path(raw_receipt["path"])
                raw_hash = raw_receipt.get("sha256")
                if not raw_path.is_absolute() or not raw_path.resolve().is_relative_to(state_root):
                    raise ValueError(f"raw SDK receipt escapes state root: {identity}")
                raw_source = receipts.linked("state", raw_path.relative_to(state_root).as_posix(), raw_hash)
                raw_reference = receipts.reference(raw_source, "")
                if isinstance(raw_hash, str) and re.fullmatch(r"[0-9a-f]{64}", raw_hash) and receipts.get(raw_source)["status"] == "RECORDED":
                    raw_binding = "MATCH"
                else:
                    bound = False
            for key in ("title", "repository", "pin", "install", "native", "fresh_session", "evidence_class",
                        "designated_reader", "limitations", "primary_sources"):
                # The normalized producer contract copies item fields exactly.
                # A matching file hash alone cannot justify differing index facts.
                value = item.get(key)
                if bound and contract is not None and key in payload and payload[key] == value:
                    fields[key] = receipts.fact(source, "/" + key, value)
                    fields[key]["index_receipt"] = receipts.reference("sdk_rows", declaration + "/" + key)
                else:
                    fields[key] = receipts.unknown(
                        source, "/" + key, "contract, receipt digest, identity or index value is unavailable/mismatched")
            proof_fields = list(fields.values())
            fields["owner"] = receipts.fact("sdk_rows", "/owner_lane", index.get("owner_lane"))
            output["items"].append({"id": identity, "fields": fields,
                                    "item_receipt": receipts.reference(source, ""),
                                    "raw_receipt": raw_reference, "raw_receipt_binding": raw_binding,
                                    "raw_json_pointer_map": receipts.fact(source, "/raw_json_pointer_map", payload.get("raw_json_pointer_map") if isinstance(payload, dict) else None),
                                    "prior_fresh_session_smoke": receipts.fact(source, "/prior_fresh_session_smoke", payload.get("prior_fresh_session_smoke") if isinstance(payload, dict) else None),
                                    "receipt_binding": "MATCH" if bound and all(field["status"] == "RECORDED" for field in proof_fields) else "UNVERIFIED"})
    for identity in spec.get("sdk", {}).get("expected_ids", []):
        if identity not in seen:
            output["items"].append({"id": identity, "fields": {
                "evidence_class": receipts.unknown("sdk_rows", "/items", "no item receipt posted for this declared scope"),
                "owner": receipts.claim(spec["sdk"].get("owner", {
                    "source": "sdk_contract", "pointer": "/index/owner_lane"})),
            }, "receipt_binding": "UNVERIFIED"})
    output["items"].sort(key=lambda row: row["id"])
    return output


def build(root: Path = ROOT, state_root: Path | None = None, spec_path: Path = SPEC) -> dict[str, Any]:
    state_root = state_root or Path.home() / ".local/state/native-agent-stack"
    root = root.resolve()
    spec_path = (spec_path if spec_path.is_absolute() else root / spec_path).resolve()
    if not spec_path.is_relative_to(root):
        raise ValueError("source index escapes the repository root")
    spec_raw = spec_path.read_bytes()
    spec = unique_json(spec_raw)
    if spec.get("schema_version") != 1:
        raise ValueError("unsupported source-index schema")
    receipts = Receipts(root, state_root, dict(spec["sources"]))
    manifest: dict[str, Any] = {
        "schema_version": 1, "kind": "north_star_retained_receipt_readiness",
        "source_index": {"root": "repo", "path": spec_path.relative_to(root).as_posix(),
                         "sha256": hashlib.sha256(spec_raw).hexdigest()},
        "claim_status_meaning": {
            "RECORDED": "Value extracted from the named bytes; no new execution or reader approval.",
            "UNVERIFIED": "Missing, changed, ambiguous, malformed or insufficient retained evidence.",
        },
        "path_representation": "Exported values replace personal home prefixes and local session/task identifiers with explicit placeholders; source digests and locators bind the original retained bytes.",
        "limitations": [
            "This builder performs local receipt reads only; it does not install, invoke, adjudicate or publish tools.",
            "A digest identifies bytes; it does not establish signature trust, current SOTA or acceptance.",
            "Selection pins, documented installation, native behavior, fresh invocation and designated readers are separate claims.",
            "Gate-source anchors are changed only to an accepted replacement receipt; source changes alone confer no closure.",
            "Host-state receipts remain local; a checkout without them renders their claims UNVERIFIED.",
        ],
    }
    for section in ("gates", "data", "paper", "rnd_inputs", "open_items", "observations", "monitoring"):
        manifest[section] = records(spec, section, receipts)
    manifest["layers"] = build_layers(receipts)
    manifest["sdk_frameworks"] = build_sdks(spec, receipts)
    manifest["sdk_frameworks"]["qualifications"] = records(spec, "sdk_qualifications", receipts)
    # Force all declared inputs into provenance, including unavailable inputs.
    for name in list(receipts.sources):
        receipts.get(name)
    manifest["receipts"] = dict(sorted(receipts.records.items()))

    def statuses(value: Any) -> list[str]:
        if isinstance(value, dict):
            if "value" in value and "receipt" in value:
                return [value["status"]]
            return [status for child in value.values() for status in statuses(child)]
        if isinstance(value, list):
            return [status for child in value for status in statuses(child)]
        return []

    claims = statuses(manifest)
    manifest["summary"] = {"gates": len(manifest["gates"]), "layers": len(manifest["layers"]),
                           "sdk_items": len(manifest["sdk_frameworks"]["items"]),
                           "recorded_claims": claims.count("RECORDED"),
                           "unverified_claims": claims.count("UNVERIFIED"),
                           "unverified_sources": sum(row["status"] == "UNVERIFIED" for row in receipts.records.values())}
    return manifest


def render(manifest: dict[str, Any]) -> bytes:
    def portable(value: Any) -> Any:
        if isinstance(value, str):
            value = re.sub(r"/home/[^/\s\"'<>]+|/Users/[^/\s\"'<>]+", "${USER_HOME}", value)
            value = re.sub(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", "${LOCAL_SESSION_ID}", value, flags=re.IGNORECASE)
            return re.sub(r"task-[a-z0-9]{8}-[a-z0-9]{6}", "${LOCAL_TASK_HANDLE}", value, flags=re.IGNORECASE)
        if isinstance(value, dict):
            return {key: portable(child) for key, child in value.items()}
        if isinstance(value, list):
            return [portable(child) for child in value]
        return value

    return (json.dumps(portable(manifest), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def render_fragment(manifest: dict[str, Any]) -> str:
    """Render a reviewable fragment for the existing durable readiness page."""
    def cell(value: Any) -> str:
        if isinstance(value, dict) and "value" in value:
            value = value["value"] if value["status"] == "RECORDED" else "UNVERIFIED"
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return html.escape(str(value if value is not None else "UNVERIFIED"))

    lines = ['<section id="receipt-readiness" aria-labelledby="receipt-readiness-title">',
             '<h2 id="receipt-readiness-title">Readiness receipt manifest</h2>',
             '<p>Retained receipt values; installation, invocation and reader approval remain separate.</p>',
             '<table><thead><tr><th>Gate</th><th>Recorded state</th><th>Owner</th></tr></thead><tbody>']
    for row in manifest["gates"]:
        fields = row["fields"]
        lines.append(f'<tr><td>{cell(row["id"])}</td><td>{cell(fields.get("state"))}</td><td>{cell(fields.get("owner"))}</td></tr>')
    lines.append('</tbody></table><table><thead><tr><th>Layer</th><th>Selected tool / pin</th><th>Fresh invocation</th></tr></thead><tbody>')
    for row in manifest["layers"]:
        tools = row["selected_tools"]
        names = "; ".join(cell(tool["id"]) + " / " + cell(tool["fields"]["pin"]) for tool in tools)
        invokes = "; ".join(cell(tool["fields"]["fresh_session_invoke"]) for tool in tools)
        lines.append(f'<tr><td>{cell(row["id"])}</td><td>{names}</td><td>{invokes or "UNVERIFIED"}</td></tr>')
    lines.append('</tbody></table><table><thead><tr><th>SDK / harness</th><th>Receipt binding</th></tr></thead><tbody>')
    for row in manifest["sdk_frameworks"]["items"]:
        lines.append(f'<tr><td>{cell(row["id"])}</td><td>{cell(row["receipt_binding"])}</td></tr>')
    lines.append('</tbody></table>')
    for row in manifest["sdk_frameworks"].get("qualifications", []):
        lines.append(f'<p>{cell(row["title"])}: {cell(row["fields"].get("state"))}</p>')
    for section, title in (("data", "Data"), ("paper", "Paper"), ("rnd_inputs", "R&amp;D inputs"),
                           ("open_items", "Open items"), ("monitoring", "Monitoring")):
        rows = manifest.get(section, [])
        if not rows:
            continue
        lines.append(f'<h3>{title}</h3><table><thead><tr><th>Item</th><th>Recorded state</th><th>Owner</th></tr></thead><tbody>')
        for row in rows:
            fields = row["fields"]
            lines.append(f'<tr><td>{cell(row["title"])}</td><td>{cell(fields.get("state"))}</td><td>{cell(fields.get("owner"))}</td></tr>')
        lines.append('</tbody></table>')
    lines.append('</section>')
    return "\n".join(lines) + "\n"


def publish_page(manifest: dict[str, Any], page: Path, expected_sha256: str,
                 dry_run: bool = False) -> dict[str, Any]:
    """Publish one managed fragment only against the custodian's expected bytes."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("expected page SHA-256 must be 64 lowercase hex characters")
    if page.is_symlink():
        raise ValueError("page target must be a regular file, not a symlink")
    original = page.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    if original_hash != expected_sha256:
        raise ValueError("page bytes differ from the custodian's expected SHA-256")
    text = original.decode("utf-8")
    start, end = "<!-- north-star-readiness:start -->", "<!-- north-star-readiness:end -->"
    counts = text.count(start), text.count(end)
    block = start + "\n" + render_fragment(manifest) + end
    if counts == (1, 1):
        first, last = text.index(start), text.index(end)
        if last < first:
            raise ValueError("page managed markers are reversed")
        updated = text[:first] + block + text[last + len(end):]
    elif counts != (0, 0):
        raise ValueError("page managed markers are missing, nested or duplicated")
    else:
        # The CC's retained HTML fragment omits body/main closing tags and
        # ends with one named links section; full HTML documents use their
        # ordinary closing container. Unknown layouts fail rather than append.
        if text.count("</main>") == 1:
            anchor = "</main>"
        elif text.count("</body>") == 1:
            anchor = "</body>"
        else:
            anchor = '<section aria-labelledby="l" class="foot">'
        if text.count(anchor) != 1:
            raise ValueError("page requires one unambiguous insertion anchor")
        updated = text.replace(anchor, block + "\n" + anchor)
    output = updated.encode("utf-8")
    result = {"original_sha256": original_hash, "output_sha256": hashlib.sha256(output).hexdigest(),
              "output_bytes": len(output), "dry_run": dry_run}
    if dry_run:
        return result
    if output == original:
        return result | {"unchanged": True}
    backup = page.with_name(page.name + ".receipt-backup-" + original_hash[:16])
    if backup.exists() and backup.read_bytes() != original:
        raise ValueError("existing page backup does not match the original bytes")
    if not backup.exists():
        backup.write_bytes(original)
    if hashlib.sha256(page.read_bytes()).hexdigest() != original_hash:
        raise ValueError("page changed while preparing the publication")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=page.parent, prefix=f".{page.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(output)
        os.chmod(temporary, page.stat().st_mode & 0o777)
        temporary.replace(page)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    result["backup"] = str(backup)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--sources", type=Path, default=SPEC)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    parser.add_argument("--html-fragment", type=Path, help="write a local fragment; never alters the durable page")
    parser.add_argument("--publish-page", type=Path, help="finite managed-fragment publication for the page custodian")
    parser.add_argument("--expected-page-sha256", help="required digest of the custodian-approved page input")
    parser.add_argument("--dry-run", action="store_true", help="report page publication hashes without changing the page")
    args = parser.parse_args(argv)
    try:
        manifest = build(args.root, args.state_root, args.sources)
        expected = render(manifest)
        output = args.output if args.output.is_absolute() else args.root / args.output
        if args.write:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(expected)
        elif not output.exists() or output.read_bytes() != expected:
            print(f"STALE {output}; run with --write after accepting any replacement gate receipt")
            return 1
        if args.html_fragment:
            args.html_fragment.parent.mkdir(parents=True, exist_ok=True)
            args.html_fragment.write_text(render_fragment(manifest), encoding="utf-8")
        result = {"path": str(output), "sha256": hashlib.sha256(expected).hexdigest(),
                  "bytes": len(expected), "summary": manifest["summary"]}
        if args.publish_page:
            if not args.expected_page_sha256:
                raise ValueError("--publish-page requires --expected-page-sha256")
            result["page_publication"] = publish_page(manifest, args.publish_page, args.expected_page_sha256, args.dry_run)
        elif args.dry_run or args.expected_page_sha256:
            raise ValueError("page publication options require --publish-page")
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"UNVERIFIED: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
