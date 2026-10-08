#!/usr/bin/env python3
"""Deterministically bind G5 data fragments; this is not a discovery/evaluation runner.

Reference: native-agent-stack@8ee8b3bd, landscape-sweep/sweep_common.py
(canon/json_text), scripts/host_receipts.py (register_file), and the supported
catalog_decisions.py writer. CC163050Z explicitly assigns this bounded glue.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "tools/sota-convergence/landscape-sweep"))
sys.path.insert(0, str(REPO / "scripts"))
from sweep_common import canon, json_text
from host_receipts import register_file, unique_json
import catalog_decisions as decisions
import compact_manifest as compact

CLASSES = {"ADOPT-NOW", "TRIAL", "WATCH", "REJECT", "NO-GAP", "OUT-OF-SCOPE"}
VERDICT_FIELDS = (
    "group", "verdict_status", "winners", "alternatives", "lanes", "current_choice",
    "decision", "checked_at", "open_gaps", "verdict_overturn_when", "overturn_protocol",
)
STAR_TARGET = "catalogs/convergence-practice/public-starred.json"
LIFECYCLE_TARGET = "blueprints/token-native-focus/saturation-audit.json"
CONSERVATIVE = ("REJECT", "OUT-OF-SCOPE", "NO-GAP", "WATCH", "TRIAL")


class FragmentError(ValueError):
    pass


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def checked_bytes(path: Path, expected: str) -> bytes:
    if not isinstance(expected, str) or len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise FragmentError("fragment SHA256 must be 64 lowercase hexadecimal characters")
    raw = path.read_bytes()
    if digest(raw) != expected:
        raise FragmentError(f"fragment hash mismatch: {path.name}")
    return raw


def target_path(root: Path, relative: str, lifecycle=False) -> Path:
    try:
        target = decisions.safe_file(root, relative)
    except decisions.InvalidDecisionIndex as error:
        raise FragmentError(str(error)) from error
    value = Path(relative)
    allowed = (
        relative == STAR_TARGET
        or (lifecycle and relative == LIFECYCLE_TARGET)
        or (relative.startswith("catalogs/landscape/") and value.suffix == ".json")
        or (relative.startswith("evidence/artifacts/g5-") and value.suffix in {".json", ".md", ".tsv", ".txt"})
        or (relative.startswith("docs/") and value.suffix == ".md")
    )
    if not allowed or value.name in {"AGENTS.md", "CLAUDE.md"}:
        raise FragmentError(f"target outside the assigned G5 data/doc paths: {relative}")
    return target


def repository_key(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FragmentError("star identity must be nonempty text")
    result = canon(value)
    if not isinstance(result, str) or not result.startswith("https://github.com/"):
        raise FragmentError("star identity must be a GitHub repository")
    return result.casefold()


def metadata_pages(path: Path, expected: str) -> list[dict]:
    text = checked_bytes(path, expected).decode("utf-8")
    decoder = json.JSONDecoder(object_pairs_hook=unique_json)
    cursor, rows = 0, []
    while cursor < len(text):
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor == len(text):
            break
        page, cursor = decoder.raw_decode(text, cursor)
        if not isinstance(page, list):
            raise FragmentError("native star metadata must contain JSON page arrays")
        rows.extend(page)
    if any(not isinstance(row, dict) for row in rows):
        raise FragmentError("native star rows must be objects")
    identities = [repository_key(row["repository"]) for row in rows]
    if len(rows) != 368 or len(set(identities)) != 368:
        raise FragmentError("native star inventory must contain 368 unique identities")
    return rows


def explicit_slots(entry):
    """Use declared source fields only; descriptive scope prose never supplies a slot."""
    if not isinstance(entry, dict):
        return []
    row, document = entry.get("row", {}), entry.get("document", {})
    if not isinstance(row, dict) or not isinstance(document, dict):
        raise FragmentError("scope overlay row/document must be objects")
    slots = []
    for source in (row, document):
        for field in ("layer_id", "layer_ids", "layers", "field"):
            value = source.get(field)
            values = value if isinstance(value, list) else value.split(";") if isinstance(value, str) else []
            for item in values:
                if isinstance(item, str) and item.strip() and item.strip().lower() not in {"none", "unspecified", "unknown"}:
                    slots.append(item.strip())
        if slots:
            break
    if not slots and isinstance(row.get("slot"), str) and row["slot"].strip():
        slots = ["slot:" + row["slot"].strip()]
    # Explicit role and catalog remain literal qualifications; they are not translated.
    qualifiers = {key: row.get(key, document.get(key)) for key in ("catalog", "role", "slot")
                  if row.get(key, document.get(key)) is not None}
    return [(slot, json.dumps(qualifiers, sort_keys=True, ensure_ascii=False)) for slot in sorted(set(slots))]


def conservative(dispositions):
    return next((value for value in CONSERVATIVE if value in dispositions), "WATCH")


def scope_record(overlay, source_id, pointer):
    if isinstance(overlay.get("records"), dict):
        source = overlay["records"].get(source_id, {})
        if not isinstance(source, dict):
            raise FragmentError("scope source map must be an object")
        return source.get(pointer)
    sources = overlay.get("sources")
    if not isinstance(sources, dict):
        raise FragmentError("scope overlay requires records{} or sources{}")
    source = sources.get(source_id, {})
    if not isinstance(source, dict) or not isinstance(source.get("selected_records", {}), dict):
        raise FragmentError("selected scope source must contain selected_records{}")
    selected = source.get("selected_records", {}).get(pointer)
    if selected is None:
        return None
    if not isinstance(selected, dict) or not isinstance(selected.get("explicit_scope", {}), dict):
        raise FragmentError("selected scope record requires explicit_scope{}")
    inherited = selected.get("inherited_explicit_scope", [])
    if isinstance(inherited, list) and inherited and all(isinstance(item, str) for item in inherited):
        ancestors = source.get("inherited_explicit_scope", {})
        if not isinstance(ancestors, dict) or any(pointer not in ancestors or not isinstance(ancestors[pointer], dict) for pointer in inherited):
            raise FragmentError("selected ancestor scope pointers must resolve to explicit source objects")
        inherited = [{"ancestor_pointer": pointer, "scope": ancestors[pointer]} for pointer in inherited]
    if not isinstance(inherited, list) or any(not isinstance(item, dict) or not isinstance(item.get("scope", {}), dict) for item in inherited):
        raise FragmentError("inherited scope must be an array of explicit ancestor objects")
    document = {}
    # Nearest declared ancestor wins; all original ancestors are retained as evidence.
    for item in sorted(inherited, key=lambda item: len(str(item.get("ancestor_pointer", "")))):
        document.update(item.get("scope", {}))
    return {"row": selected.get("explicit_scope", {}), "document": document,
            "evidence": [{"source_id": source_id, "original_pointer": pointer,
                          "original_input_sha256": source.get("original_input_sha256"),
                          "published_scope_records_sha256": source.get("published_scope_records_sha256"),
                          "inherited_explicit_scope": inherited}],
            "status": selected.get("scope_authority_status", selected.get("status", source.get("default_scope_authority_status")))}


def normalize_scopes(repository: str, groups: list, overlay: dict, committed_slots=None):
    """CC17:22: split scopes, merge pure duplicates, retain primary-only disagreements."""
    if not isinstance(overlay, dict):
        raise FragmentError("scope overlay must be an object")
    bins, unknown = {}, []
    for group in groups:
        disposition = group.get("disposition")
        if not isinstance(disposition, str) or disposition not in CLASSES:
            raise FragmentError("scope group requires a known disposition")
        # Nonbinding metadata screens remain in original claims, never vetoing another slot.
        if group.get("binding") is not True:
            continue
        refs = group.get("source_refs", [])
        if not isinstance(refs, list) or not refs:
            unknown.append({"disposition": disposition, "reason": "missing exact source references", "source_refs": refs})
        for ref in refs:
            if not isinstance(ref, dict) or not isinstance(ref.get("source_id"), str) or not isinstance(ref.get("pointer"), str):
                raise FragmentError("scope reference requires source_id and pointer text")
            entry = scope_record(overlay, ref["source_id"], ref["pointer"])
            scopes = explicit_slots(entry)
            if not scopes:
                unknown.append({"disposition": disposition, "reason": "explicit source scope unavailable", "source_refs": [ref]})
                continue
            observation = {"disposition": disposition, "lane": group.get("lane"), "pin": group.get("pin"),
                           "date": group.get("date"), "date_basis": group.get("date_basis"),
                           "source_ref": ref, "evidence": entry.get("evidence_refs", entry.get("evidence", [])),
                           "source_scope": {"row": entry.get("row", {}), "document": entry.get("document", {})},
                           "scope_authority_status": entry.get("status")}
            # project_scopes.py@4500a843:130-131 creates this *collector* deferral.
            # Resolve only its exact declared selector join, retaining the original annotation.
            binding = (entry.get("status") == "PENDING_EXPLICIT_FIELD_BINDING"
                       and committed_slots is not None and all(slot in committed_slots for slot, _ in scopes))
            observation["source_field_binding"] = "BOUND_TO_COMMITTED_SELECTORS" if binding else "UNRESOLVED"
            for scope in scopes:
                bins.setdefault(scope, []).append(observation)
    rows, remainder, duplicates, exact_duplicates = [], [], 0, 0
    for (slot, qualification), observations in sorted(bins.items()):
        labels = sorted({item["disposition"] for item in observations})
        choices = []
        for label in labels:
            candidates = [item for item in observations if item["disposition"] == label]
            unique = {json.dumps(item, sort_keys=True, ensure_ascii=False): item for item in candidates}
            duplicates += max(0, len(candidates) - 1)
            exact_duplicates += len(candidates) - len(unique)
            choices.append({"disposition": label, "observations": [unique[key] for key in sorted(unique)]})
        qualification_pending = any(item["source_field_binding"] != "BOUND_TO_COMMITTED_SELECTORS"
                                    and any(token in str(item.get("scope_authority_status", "")).upper()
                                            for token in ("PENDING", "UNKNOWN", "UNVERIFIED", "PROPOSED_NOT_LANDED"))
                                    for item in observations)
        pending = len(labels) > 1 or labels == ["ADOPT-NOW"] or qualification_pending
        record = {"repository": repository, "slot": slot, "qualification": json.loads(qualification),
                  "status": "PENDING" if pending else "SOURCE-REVIEW", "disposition": None if pending else labels[0],
                  "choices": choices, "source_observations": len(observations)}
        if pending:
            record.update(provisional_disposition=conservative(labels),
                          settling_measurement=f"Run the documented pinned native check for {slot} against the incumbent and candidate; retain the observed assertion, source references and inverse.",
                          measurement_owner="grand-catalog",
                          pending_reason="Same-slot primary evidence has not been independently adjudicated" if len(labels) > 1 else
                                         "Explicit source scope authority remains pending" if qualification_pending else
                                         "ADOPT-NOW native acceptance and designated readers are not bound")
            remainder.append(record)
        rows.append(record)
    if not bins and not unknown:
        unknown.append({"disposition": "WATCH", "reason": "No admitting explicitly scoped decision is bound; WATCH is only a provisional hold",
                        "source_refs": [ref for group in groups for ref in group.get("source_refs", [])]})
    if unknown:
        remainder.append({"repository": repository, "slot": "UNKNOWN", "qualification": {}, "status": "PENDING",
                          "choices": unknown, "provisional_disposition": conservative({item["disposition"] for item in unknown}),
                          "settling_measurement": "Read the exact pinned source records and bind their explicit slot/role fields; preserve every original locator.",
                          "measurement_owner": "grand-catalog", "pending_reason": "Source slot qualification is unavailable"})
    return {"rows": rows, "unknown_scope_claims": unknown, "remainder": remainder,
            "scope_split": len(rows) > 1, "pure_duplicates_merged": duplicates,
            "same_label_claims_coalesced": duplicates, "exact_duplicate_observations_removed": exact_duplicates}


def remainder_files(remainder):
    """One CC remainder table; qualification gaps are distinct from same-slot conflicts."""
    data = {"schema_version": 1, "rule": "CC17:22 primary evidence only", "rows": remainder,
            "same_slot_conflicts": sum(row["slot"] != "UNKNOWN" and len(row.get("choices", [])) > 1 for row in remainder),
            "scope_or_acceptance_pending": sum(row["slot"] == "UNKNOWN" or len(row.get("choices", [])) <= 1 for row in remainder)}
    lines = ["# G5 pending primary evidence and scope measurements", "",
             "Source qualifications and real same-slot disagreements are counted separately. No lane count, recency or popularity settles a row.", "",
             "| Repository | Slot and qualification | Dispositions and evidence | Provisional | Settling measurement | Owner |",
             "| --- | --- | --- | --- | --- | --- |"]
    def cell(value):
        return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    for index, row in enumerate(remainder):
        labels = sorted({choice["disposition"] for choice in row.get("choices", [])})
        evidence = ", ".join(labels) + f"; [all source locators](scope-conflicts.json#/rows/{index}/choices)"
        lines.append("| " + " | ".join(cell(value) for value in (
            row["repository"], row["slot"] + " " + json.dumps(row.get("qualification", {}), sort_keys=True, ensure_ascii=False),
            evidence, row["provisional_disposition"], row["settling_measurement"], row["measurement_owner"],
        )) + " |")
    # Fresh immutable snapshot when qualification changes; never overwrite a sealed table.
    suffix = digest(json_text(data, indent=2).encode("utf-8"))[:16]
    prefix = f"evidence/artifacts/g5-grand-catalog-20261008/scope-{suffix}/"
    return {prefix + "scope-conflicts.json": json_text(data, indent=2).encode("utf-8"),
            prefix + "scope-conflicts.md": ("\n".join(lines) + "\n").encode("utf-8")}


def committed_field_scope(root: Path):
    """Read exact field identities and bind their source documents; no semantic aliases."""
    slots, documents = set(), []
    for name, collection in (("foundation", "layers"), ("us-equities", "layers"), ("skills-lifecycle", "tasks")):
        relative = f"catalogs/landscape/{name}.json"
        path = decisions.safe_file(root, relative)
        packet = read_json(path)
        if not isinstance(packet, dict) or not isinstance(packet.get(collection), list):
            raise FragmentError("committed scope source requires its native collection")
        for row in packet[collection]:
            if not isinstance(row, dict) or not isinstance(row.get("layer_id"), str) or row["layer_id"] in slots:
                raise FragmentError("committed scope requires unique text layer identities")
            slots.add(row["layer_id"])
        documents.append({"path": relative, "sha256": digest(path.read_bytes()), "collection": collection})
    return slots, documents


def stars_document(root: Path, fragment: Path, sha: str, metadata: Path, metadata_sha: str, scope_overlay=None, committed_slots=None):
    packet = json.loads(checked_bytes(fragment, sha), object_pairs_hook=unique_json)
    if not isinstance(packet, dict):
        raise FragmentError("stars packet must be an object")
    claims = packet.get("repositories", packet.get("rows"))
    if not isinstance(claims, list):
        raise FragmentError("stars fragment requires repositories[] or rows[]")
    by_repo = {}
    for row in claims:
        if not isinstance(row, dict):
            raise FragmentError("star claims must be objects")
        key = repository_key(row.get("repository"))
        if key in by_repo:
            raise FragmentError("stars fragment repeats an identity")
        disposition = row.get("disposition")
        if disposition is not None and (not isinstance(disposition, str) or disposition not in CLASSES):
            raise FragmentError("unknown G5 disposition")
        by_repo[key] = row
    rows = metadata_pages(metadata, metadata_sha)
    if set(by_repo) != {repository_key(row["repository"]) for row in rows}:
        raise FragmentError("stars fragment and authoritative inventory differ")
    current = read_json(root / STAR_TARGET)
    output = {key: value for key, value in current.items() if key != "repositories"}
    bound, conflicts, scope_splits, duplicates, exact_duplicates = 0, 0, 0, 0, 0
    remainder = []
    for row in rows:
        claim = by_repo[repository_key(row["repository"])]
        status = str(claim.get("status", "PENDING"))
        if "conflicts" in claim and "conflict" in claim:
            raise FragmentError("star claim supplies both conflict representations")
        conflict = claim.get("conflicts", claim.get("conflict"))
        evidence = claim.get("evidence_refs", [])
        source_decisions = claim.get("source_decisions", claim.get("claims", []))
        if not isinstance(evidence, list) or any(not isinstance(x, str) or not x.strip() for x in evidence):
            raise FragmentError("star evidence_refs must be an array of nonempty strings")
        if not isinstance(source_decisions, list) or any(not isinstance(x, dict) for x in source_decisions):
            raise FragmentError("star source_decisions must be an array of objects")
        normalized = normalize_scopes(row["repository"], source_decisions, scope_overlay, committed_slots) if scope_overlay is not None else None
        if normalized is not None:
            scoped = normalized["rows"]
            unresolved = bool(normalized["remainder"]) or not scoped
            labels = {item["disposition"] for item in scoped if item["disposition"] is not None}
            conflict = normalized["remainder"]
            status = "PENDING" if unresolved else "SCOPE-SPLIT" if len(labels) > 1 else "SOURCE-MERGED"
            scope_splits += normalized["scope_split"]
            duplicates += normalized["pure_duplicates_merged"]
            exact_duplicates += normalized["exact_duplicate_observations_removed"]
            remainder.extend(normalized["remainder"])
            row["dispositions_by_slot"] = scoped
            row["unknown_scope_claims"] = normalized["unknown_scope_claims"]
        complete_status = status.upper() in {"SOURCE-MERGED", "SOURCE-REVIEW", "SOURCE-VERIFIED", "VERIFIED", "DISPOSITIONED"}
        pending = not complete_status or bool(conflict) or not evidence or not source_decisions
        if normalized is not None:
            pending = unresolved or not evidence or not source_decisions
        disposition = None if pending else (next(iter(labels)) if normalized is not None and len(labels) == 1 else claim.get("disposition") if normalized is None else None)
        if isinstance(row.get("license_metadata"), dict):
            row["license_metadata"] = row["license_metadata"].get("spdx_id")
        row.update(
            disposition=disposition,
            disposition_status=status if not pending or status.upper().startswith("PENDING") else "PENDING-EVIDENCE",
            disposition_evidence=evidence,
            source_decisions=source_decisions,
        )
        row["g5_source_fields"] = {key: value for key, value in claim.items() if key not in {
            "repository", "disposition", "status", "evidence_refs", "source_decisions", "claims", "conflicts", "conflict",
        }}
        if pending and claim.get("disposition") is not None:
            row["proposed_disposition"] = claim["disposition"]
        if conflict:
            row["disposition_conflicts"] = conflict
            conflicts += 1
        bound += not pending if normalized is not None else disposition is not None
    output.update(count=368, repositories=rows)
    output["g5"] = {
        **output.get("g5", {}),
        "status": "source_dispositions_bound" if bound == 368 and not conflicts else "assembling",
        "source_dispositions_bound": bound,
        "dispositions_pending": 368 - bound,
        "pending_repositories": conflicts,
        "conflicting_repositories": sum(any(record["slot"] != "UNKNOWN" and len(record.get("choices", [])) > 1
                                             for record in row.get("disposition_conflicts", []))
                                        for row in rows) if scope_overlay is not None else conflicts,
        "scope_splits": scope_splits,
        "pure_duplicates_merged": duplicates,
        "same_label_claims_coalesced": duplicates,
        "exact_duplicate_observations_removed": exact_duplicates,
        "duplicate_metric_boundary": "Same-slot same-class claims coalesced, with all distinct observations and source locators retained; exact duplicates counted separately.",
        "conflict_rule": "CC17:22: explicit scope splits; exact same-slot duplicates merged; primary-only unresolved choices pending",
        "conflict_remainder": remainder,
        "fragment_sha256": sha,
        "source_return_sha256": metadata_sha,
        "input_manifest": packet.get("input_manifest", {}),
        "acceptance_boundary": "Source data binding only; no family/native/install/START inference.",
    }
    return output, {"stars": bound, "stars_total": 368, "pending_repositories": 368-bound,
                    "same_slot_conflicting_repositories": output["g5"]["conflicting_repositories"], "scope_splits": scope_splits,
                    "pure_duplicates_merged": duplicates,
                    "same_label_claims_coalesced": duplicates, "exact_duplicate_observations_removed": exact_duplicates,
                    "same_slot_conflicts": sum(row["slot"] != "UNKNOWN" and len(row.get("choices", [])) > 1 for row in remainder),
                    "scope_or_acceptance_pending": sum(row["slot"] == "UNKNOWN" or len(row.get("choices", [])) <= 1 for row in remainder)}


def contains_prior(before, after):
    """Allow additive source observations, retaining every prior value and list item."""
    if isinstance(before, dict):
        return isinstance(after, dict) and all(key in after and contains_prior(value, after[key]) for key, value in before.items())
    if isinstance(before, list):
        return isinstance(after, list) and len(after) >= len(before) and all(
            contains_prior(value, after[index]) for index, value in enumerate(before)
        )
    return before == after


def layer_rows(document):
    if not isinstance(document, dict) or not isinstance(document.get("layers"), list):
        raise FragmentError("landscape document requires layers[]")
    rows = {}
    for row in document["layers"]:
        if not isinstance(row, dict) or not isinstance(row.get("layer_id"), str) or not row["layer_id"]:
            raise FragmentError("landscape rows require nonempty layer_id")
        if row["layer_id"] in rows:
            raise FragmentError("landscape repeats a layer identity")
        rows[row["layer_id"]] = row
    return rows


def preserve_verdicts(before, after, relative: str):
    if relative not in {"catalogs/landscape/foundation.json", "catalogs/landscape/us-equities.json"}:
        return
    old = layer_rows(before)
    new = layer_rows(after)
    if before.get("schema_version") != after.get("schema_version") or before.get("checked_at") != after.get("checked_at"):
        raise FragmentError("fragment changes the historical schema or checked_at")
    if list(old) != list(new):
        raise FragmentError("fragment changes the ordered committed layer identities")
    for key in old:
        for field in VERDICT_FIELDS:
            if old[key].get(field) != new[key].get(field):
                raise FragmentError(f"historical verdict changed: {key}/{field}")
        for field, value in old[key].items():
            if not contains_prior(value, new[key].get(field)):
                raise FragmentError(f"historical source/default removed or changed: {key}/{field}")


def committed_bytes(root: Path, relative: str):
    """Compare frozen evidence with immutable HEAD, even when working bytes are absent."""
    listed = subprocess.run(["git", "-C", str(root), "ls-tree", "-z", "HEAD", "--", relative], capture_output=True, check=True)
    if not listed.stdout:
        return None
    return subprocess.run(["git", "-C", str(root), "show", "HEAD:" + relative], capture_output=True, check=True).stdout


def public_bytes(raw: bytes):
    # Reject known personal host material rather than silently weakening provenance.
    if any(token in raw for token in (str(Path.home()).encode(), b"/mnt/v/evey", b"api_key\":", b"Bearer sk-")):
        raise FragmentError("public fragment contains personal host or credential material")


def manifest_files(root: Path, manifest: Path):
    packet = read_json(manifest)
    if not isinstance(packet, dict):
        raise FragmentError("fragment manifest must be an object")
    entries = packet.get("files")
    if not isinstance(entries, list):
        raise FragmentError("fragment manifest requires files[]")
    result = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("source"), str) or not entry["source"]:
            raise FragmentError("fragment files must be objects with source text")
        relative = entry["target"]
        target = target_path(root, relative)
        source = Path(entry["source"])
        if not source.is_absolute():
            source = manifest.parent / source
        raw = checked_bytes(source, entry["sha256"])
        baseline = entry.get("base_sha256")
        if baseline is not None:
            checked_bytes(target, baseline)
        if target.suffix == ".json":
            data = json.loads(raw, object_pairs_hook=unique_json)
            if target.is_file():
                before = read_json(target)
                preserve_verdicts(before, data, relative)
            raw = json_text(data, indent=2).encode("utf-8")
        if relative.startswith("evidence/artifacts/"):
            existing = committed_bytes(root, relative)
            if existing is not None and existing != raw:
                raise FragmentError("cannot rewrite a tracked frozen evidence input")
        public_bytes(raw)
        if relative in result:
            raise FragmentError("fragment repeats a target")
        result[relative] = raw
    return result


def preflight_supplements(root: Path, planned: dict, supplements: list[str]):
    if not supplements:
        return {}
    for relative in (decisions.INDEX, decisions.MANIFEST):
        decisions.safe_file(root, relative)
    manifest = decisions.load(root, decisions.MANIFEST)
    decisions.require(isinstance(manifest, dict), "catalog manifest must be an object")
    specs = decisions.load(root, decisions.INDEX).get("sources") if decisions.safe_file(root, decisions.INDEX).exists() else list(decisions.BASE_SOURCES)
    decisions.require(isinstance(specs, list), "sources must be an array")
    specs = list(specs)
    for value in supplements:
        addition = decisions.supplement(value)
        if addition not in specs:
            specs.append(addition)
    fingerprints = {}
    with tempfile.TemporaryDirectory(prefix="g5-supplement-") as directory:
        overlay = Path(directory).resolve()
        for spec in specs:
            decisions.require(isinstance(spec, dict) and isinstance(spec.get("path"), str), "source descriptors require path text")
            relative = spec["path"]
            original = decisions.safe_file(root, relative)
            raw = planned.get(relative)
            if raw is None:
                raw = original.read_bytes()
                fingerprints[relative] = digest(raw)
            destination = decisions.safe_file(overlay, relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
        decisions.build_index(overlay, specs)
    return fingerprints


def atomic_bytes(path: Path, raw: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="." + path.name + ".", delete=False) as output:
            temporary = Path(output.name)
            output.write(raw)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def lifecycle_union(root: Path, base_ref: str):
    """Reconcile catalog counters from native typed identities; retain every lifecycle fact."""
    if not base_ref or base_ref.startswith("-"):
        raise FragmentError("lifecycle reconciliation requires a committed base reference")
    base = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", base_ref + "^{commit}"],
                          capture_output=True, text=True, check=True).stdout.strip()
    def baseline(relative):
        raw = subprocess.run(["git", "-C", str(root), "show", base + ":" + relative], capture_output=True, check=True).stdout
        return json.loads(raw, object_pairs_hook=unique_json), digest(raw)
    before_index, index_sha = baseline(decisions.INDEX)
    before, audit_sha = baseline(LIFECYCLE_TARGET)
    current = read_json(decisions.safe_file(root, LIFECYCLE_TARGET))
    actual_index = decisions.load(root, decisions.INDEX)
    # A registered native index, not an arbitrary list length, supplies the subject universe.
    decisions.validate_index(root)
    old = {record["repository"]: record for record in before_index["records"]}
    new = {record["repository"]: record for record in actual_index["records"]}
    if len(old) != len(before_index["records"]) or len(new) != len(actual_index["records"]):
        raise FragmentError("lifecycle union repeats canonical repository identities")
    if not set(old).issubset(new):
        raise FragmentError("lifecycle reconciliation would remove historical catalog identities")
    added = sorted(set(new) - set(old))
    if any(new[repository]["record_types"] != ["research_supplement"] for repository in added):
        raise FragmentError("new lifecycle identities require a separately reviewed exclusive group")
    if before["counts"]["catalog_identities"] != len(old) or sum(before["counts"]["exclusive_identity_groups"].values()) != len(old):
        raise FragmentError("historical lifecycle counts do not match the pinned baseline union")
    if current.get("components") != before.get("components") or current.get("stage_policy") != before.get("stage_policy"):
        raise FragmentError("lifecycle facts changed after the catalog baseline")
    result = dict(current)
    counts = dict(before["counts"])
    groups = dict(counts["exclusive_identity_groups"])
    groups["research_supplement"] += len(added)
    counts.update(catalog_identities=len(new), nonselected_catalog_identities=len(new)-counts["selected_components"],
                  exclusive_identity_groups=groups,
                  exclusive_identity_group_scope=counts["exclusive_identity_group_scope"] +
                  f" G5 adds {len(added)} identities whose native registered record type is exclusively research_supplement. This changes source inventory counters only.")
    result["counts"] = counts
    record = {"schema_version": 1, "source": "scripts/catalog_decisions.py native typed identity union",
              "baseline_commit": base, "baseline_index_sha256": index_sha, "baseline_audit_sha256": audit_sha,
              "current_index_sha256": digest(decisions.safe_file(root, decisions.INDEX).read_bytes()),
              "baseline_counts": before["counts"], "current_counts": counts, "added_research_identities": added,
              "boundary": "Catalog inventory reconciliation only; selected component, lifecycle, receipt, install and host acceptance facts unchanged."}
    result["g5_catalog_reconciliation"] = record
    receipt = "evidence/artifacts/g5-grand-catalog-20261008/lifecycle-" + digest(json_text(record, indent=2).encode())[:16] + ".json"
    return {LIFECYCLE_TARGET: json_text(result, indent=2).encode("utf-8"), receipt: json_text(record, indent=2).encode("utf-8")}


def compact_primary_bundle(row):
    """A valid source bundle is serialization metadata, never a version/quality vote."""
    blockers = []
    try:
        compact.validate_pin(row.get("pin"), "fragment pin", blockers)
        if row.get("pin") is None:
            return False
        for primary in row.get("primary_sources", []):
            compact.validate_pin(primary.get("pin"), "fragment primary", blockers)
            compact.validate_locator(primary.get("locator"), primary.get("pin"), "fragment primary", blockers)
        return bool(row.get("primary_sources")) and not blockers
    except (compact.CompactError, KeyError, TypeError):
        return False


def merge_compact_groups(inputs):
    """CC scope rules over exact compact keys, preserving every immutable origin row."""
    groups = {}
    for rows, member, sha, fragment in inputs:
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise FragmentError("compact fragment rows must be objects")
            key = compact.decision_key(row)
            groups.setdefault(key, []).append((row, {"archive_member": member, "sha256": sha, "pointer": f"/{index}",
                                                   "source_id": fragment, "owner_lane": row.get("owner_lane", fragment)}))
    merged, origins, disagreements = [], [], []
    def stable(value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    def union(values):
        distinct = {stable(value): value for value in values}
        return [distinct[key] for key in sorted(distinct)]
    for key, candidates in sorted(groups.items()):
        candidates = sorted(candidates, key=lambda item: stable(item[0]))
        valid = [item for item in candidates if compact_primary_bundle(item[0])]
        base, _ = (valid or candidates)[0]
        output = dict(base)
        output["repository_or_entry"] = key[0]
        source_refs = union([ref for row, _ in candidates for ref in row.get("source_refs", [])] + [ref for _, ref in candidates])
        output["source_refs"] = source_refs
        primaries = union([primary for row, _ in valid for primary in row.get("primary_sources", [])])
        if primaries:
            output["primary_sources"] = primaries
        labels = {row["disposition"] for row, _ in candidates if row.get("disposition") in CLASSES}
        choices = []
        for row, ref in candidates:
            if row.get("disposition") in CLASSES:
                choices.append({"disposition": row["disposition"], "source_refs": [ref], "qualification": row.get("qualification", {})})
            for choice in row.get("choices", []):
                if choice.get("disposition") not in CLASSES:
                    raise FragmentError("pending compact choices must retain actual six-class source labels")
                labels.add(choice["disposition"])
                choices.append(choice)
        output["choices"] = union(choices)
        signatures = {stable({field: row.get(field) for field in ("disposition", "pin", "evidence_class", "decision_scope")}) for row, _ in candidates}
        pending = any(row.get("disposition") == "PENDING" for row, _ in candidates) or len(signatures) != 1 or len(labels) != 1 or len(valid) != len(candidates)
        if pending:
            output["disposition"] = "PENDING"
            # A conflicting execution assertion remains in its original receipt, not a synthetic new acceptance.
            output["evidence_class"] = "SOURCE-REVIEW"
            output.pop("acceptance_witness", None)
            output["pending"] = {"provisional_disposition": conservative(labels),
                                 "measurement": f"Verify every retained original source row's pinned primary claims and role qualification for {key[0]} in {key[1]}, including unresolved source bundles; run one supported same-task comparison only after its native fixture is bound.",
                                 "owner": "grand-catalog", "status": "PROPOSED"}
            disagreements.append({"repository_or_entry": key[0], "slot": key[1], "qualification": json.loads(key[2]),
                                  "labels": sorted(labels), "original_rows": [ref for _, ref in candidates], "pending": output["pending"]})
        else:
            output.pop("pending", None)
        if "REJECT" in labels:
            notes = sorted({row["searched"] for row, _ in candidates if isinstance(row.get("searched"), str) and row["searched"].strip()})
            if notes:
                output["searched"] = " | ".join(notes)
        output["note"] = "One deterministic source bundle represents serialization metadata; no primary pin is selected by recency, lane count or quality voting. Every original class, pin and literal role is retained in hash-bound source_refs. " + str(base.get("note", ""))
        merged.append(output)
        origins.append({"repository_or_entry": key[0], "slot": key[1], "qualification": json.loads(key[2]),
                        "fragments": sorted({ref["source_id"] for _, ref in candidates}), "source_refs": [ref for _, ref in candidates]})
    return merged, {"schema_version": 1, "key": "canonical entry + literal slot + canonical literal qualification",
                    "origins": origins, "pending": disagreements,
                    "boundary": "Source data integration only; candidate implementation, native execution, designated readers and complete corpus coverage are independently checked."}


def compact_intake(manifests: list[Path], stage: Path, root: Path, write: bool):
    stage = stage.resolve()
    if stage.is_relative_to(root.resolve()):
        raise FragmentError("the unpublished asset stage must be outside the repository")
    planned, inputs = {}, []
    for manifest in manifests:
        packet = read_json(manifest)
        if not isinstance(packet, dict):
            raise FragmentError("compact intake manifest must be an object")
        for kind, entries in (("captures", packet.get("captures", [])), ("fragments", packet.get("fragments", []))):
            if not isinstance(entries, list):
                raise FragmentError("compact intake entries must be arrays")
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("source"), str):
                    raise FragmentError("compact intake requires source text")
                member = compact.member_name(entry["archive_member"])
                if member in {"compact/rows.json", "provenance/compact-origin-map.json"}:
                    raise FragmentError("original capture cannot use a derived compact output member")
                destination = decisions.safe_file(stage, member)
                source = Path(entry["source"])
                if not source.is_absolute():
                    source = manifest.parent / source
                raw = checked_bytes(source, entry["sha256"])
                public_bytes(raw)
                if member in planned and planned[member] != raw:
                    raise FragmentError("compact intake aliases different capture bytes")
                if destination.exists() and destination.read_bytes() != raw:
                    raise FragmentError("compact intake cannot rewrite a retained source member")
                planned[member] = raw
                if kind == "fragments":
                    rows = json.loads(raw, object_pairs_hook=unique_json)
                    if not isinstance(rows, list):
                        raise FragmentError("compact fragment requires the original row array")
                    inputs.append((rows, member, entry["sha256"], entry["fragment_id"]))
    if not inputs:
        raise FragmentError("compact intake requires at least one fragment")
    rows, receipt = merge_compact_groups(inputs)
    planned["compact/rows.json"] = json_text(rows, indent=2).encode("utf-8")
    planned["provenance/compact-origin-map.json"] = json_text(receipt, indent=2).encode("utf-8")
    for member, raw in sorted(planned.items()):
        decisions.safe_file(stage, member)
        public_bytes(raw)
    for member, raw in sorted(planned.items()):
        if write:
            atomic_bytes(decisions.safe_file(stage, member), raw)
    return {"mode": "write" if write else "check", "compact_rows": len(rows), "pending": len(receipt["pending"]),
            "fragment_inputs": len(inputs), "captures": len(planned)-2, "row_sha256": digest(planned["compact/rows.json"]),
            "origin_map_sha256": digest(planned["provenance/compact-origin-map.json"]), "coverage": "Separate frozen original census and asset-only check required"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO)
    parser.add_argument("--manifest", type=Path, action="append", default=[])
    parser.add_argument("--stars", type=Path)
    parser.add_argument("--stars-sha256")
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--metadata-sha256")
    parser.add_argument("--scope-overlay", type=Path)
    parser.add_argument("--scope-overlay-sha256")
    parser.add_argument("--reconcile-lifecycle-base", help="Pinned pre-G5 union; reconcile source inventory counters only")
    parser.add_argument("--compact-intake", type=Path, action="append", default=[])
    parser.add_argument("--asset-stage", type=Path)
    parser.add_argument("--supplement", action="append", default=[])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.compact_intake:
            if args.asset_stage is None or args.manifest or args.stars or args.supplement or args.reconcile_lifecycle_base:
                raise FragmentError("compact asset intake needs --asset-stage and its own sequential call")
            print(json.dumps(compact_intake(args.compact_intake, args.asset_stage, root, args.write), sort_keys=True))
            return 0
        planned, summary = {}, {"stars": None, "stars_total": 368}
        for manifest in args.manifest:
            additions = manifest_files(root, manifest)
            if set(planned) & set(additions):
                raise FragmentError("multiple fragments target the same path")
            planned.update(additions)
        if args.stars:
            if not all((args.stars_sha256, args.metadata, args.metadata_sha256, args.scope_overlay, args.scope_overlay_sha256)):
                raise FragmentError("stars require exact fragment, metadata and explicit scope-overlay hash bindings")
            overlay = json.loads(checked_bytes(args.scope_overlay, args.scope_overlay_sha256), object_pairs_hook=unique_json)
            slots, scope_sources = committed_field_scope(root)
            data, summary = stars_document(root, args.stars, args.stars_sha256, args.metadata, args.metadata_sha256, overlay, slots)
            data["g5"]["field_scope_sources"] = scope_sources
            tables = remainder_files(data["g5"]["conflict_remainder"])
            data["g5"]["conflict_remainder_ref"] = next(key for key in tables if key.endswith(".json"))
            data["g5"]["scope_overlay_sha256"] = args.scope_overlay_sha256
            raw = json_text(data, indent=2).encode("utf-8")
            public_bytes(raw)
            if STAR_TARGET in planned:
                raise FragmentError("stars target supplied twice")
            planned[STAR_TARGET] = raw
            for relative, raw in tables.items():
                target_path(root, relative)
                public_bytes(raw)
                if relative in planned:
                    raise FragmentError("scope remainder target supplied twice")
                committed = committed_bytes(root, relative)
                if committed is not None and committed != raw:
                    raise FragmentError("cannot rewrite a frozen scope snapshot")
                planned[relative] = raw
        if args.reconcile_lifecycle_base:
            if args.supplement:
                raise FragmentError("reconcile lifecycle after the registered supplement writer completes")
            planned.update(lifecycle_union(root, args.reconcile_lifecycle_base))
        if not planned:
            raise FragmentError("no fragment supplied")
        if args.supplement and not args.write:
            raise FragmentError("supplement registration requires --write")
        fingerprints = preflight_supplements(root, planned, args.supplement)
        for relative, expected in fingerprints.items():
            checked_bytes(decisions.safe_file(root, relative), expected)
        # Every source/path/default and the native supplement union is checked before publication.
        for relative, raw in sorted(planned.items()):
            target = target_path(root, relative, lifecycle=bool(args.reconcile_lifecycle_base))
            if args.write:
                atomic_bytes(target, raw)
        if args.write:
            registered = set(planned)
            if args.supplement:
                command = [sys.executable, str(root / "scripts/catalog_decisions.py"), "--root", str(root), "--write"]
                for supplement in args.supplement:
                    command.extend(["--supplement", supplement])
                subprocess.run(command, cwd=root, check=True)
                registered.update((decisions.INDEX, decisions.MANIFEST))
            # The native writer owns its formats; evidence registration is the final step.
            for relative in sorted(registered):
                register_file(root, relative)
        print(json.dumps({**summary, "mode": "write" if args.write else "check",
                          "targets": sorted(planned), "sha256": {key: digest(value) for key, value in sorted(planned.items())}},
                         sort_keys=True))
        return 0
    except (FragmentError, OSError, ValueError, KeyError, compact.CompactError, decisions.InvalidDecisionIndex, subprocess.CalledProcessError) as error:
        print(f"merge_fragments: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
