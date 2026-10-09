"""Read the canonical landscape and retained G5 candidate metadata.

This is a source projection, not a landscape generator or acceptance engine.
Only compact/rows.json is read from the named asset; other member bodies are
skipped. Individual JSON records are bounded, and no archive is extracted.
"""

from __future__ import annotations

from datetime import datetime, timezone
import codecs
import importlib.util
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
from typing import Any
from urllib.parse import urlsplit


_FINAL_ASSET = "research/coverage-gap-20261008/grand-catalog/start-closure-1-20261008T2140Z/class-ruling-20261009T0031Z/g5-landscape-evidence-2026-10-08.tar.zst"
_ROWS_MEMBER = "compact/rows.json"
_RECORD_LIMIT = 64 * 1024
_DOC_LIMIT = 16 * 1024 * 1024
_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/()+ -]{0,199}\Z")
_EMAIL = re.compile(r"\b[^\s<>]+@[^\s<>]+\.[A-Za-z]{2,}\b")
_SECRET = re.compile(r"(?:\bBearer\s+\S+|\bsk-[A-Za-z0-9_-]{12,}|\bgh[pousr]_[A-Za-z0-9_]+|\bgithub_pat_[A-Za-z0-9_]+)", re.I)
_HASH = re.compile(r"[a-fA-F0-9]{40}(?:[a-fA-F0-9]{24})?\Z")
_COMPONENT_FIELDS = (
    "name", "component_id", "repository", "pin", "revision", "source_head_pin",
    "disposition", "decision", "rationale", "why_selected", "why_not_default",
    "evidence_class", "evidence_kind", "evidence_depth", "requirement_fit",
    "qualification_gap", "overturn_when", "canonical_repository",
    "selected_repository_url", "selected_version", "selected_source_pin",
    "pushed_at", "license_spdx", "status", "release_relationship",
    "source_pin_kind", "primary_repository", "adoption_recommendation",
)
_QUALITY_FIELDS = {
    "capability", "test_evidence", "maintenance_provenance", "licensing_deployment",
    "portability_lifecycle", "measured_cost", "status", "finding", "findings",
    "rationale", "evidence", "evidence_kind", "evidence_class", "evidence_refs",
    "source", "sources", "url", "repository", "pin", "revision", "name", "tag",
    "tag_name", "published_at", "pushed_at", "archived", "disabled", "draft",
    "prerelease", "license_spdx", "version", "result", "measured", "scope",
    "limit", "limits", "qualification_gap", "benchmark", "benchmarks",
    "type", "value", "selected", "upstream", "maintenance", "releases",
    "relationship", "checked_at", "observed_at", "documented", "source_findings",
}


def _text(value: Any, limit: int = 1400) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if _EMAIL.search(value) or _SECRET.search(value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        return "withheld source text"
    for link in re.findall(r"https?://[^\s<>\"']+", value):
        parsed = urlsplit(link)
        if parsed.username or parsed.password or parsed.query:
            return "withheld source text"
    return value if len(value) <= limit else value[:limit] + " [source text continues]"


def _label(value: Any) -> str | None:
    return value if isinstance(value, str) and _LABEL.fullmatch(value) and not _EMAIL.search(value) and not _SECRET.search(value) else None


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _receipt(path: Path, source: str) -> dict[str, Any]:
    return {"path": source, "sha256": _sha(path), "bytes": path.stat().st_size, "file_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")}


def _json(path: Path) -> dict[str, Any]:
    if path.stat().st_size > _DOC_LIMIT:
        raise ValueError("source document exceeds the bounded read limit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("source document must be an object")
    return value


def _repo(value: Any) -> str | None:
    if not isinstance(value, str) or _EMAIL.search(value) or _SECRET.search(value):
        return None
    if value.startswith(("https://github.com/", "http://github.com/")):
        parsed = urlsplit(value)
        if parsed.username or parsed.password:
            return None
        parts = parsed.path.strip("/").split("/")
        text = "/".join(parts[:2])
    else:
        text = value.split("@", 1)[0]
    text = text.removesuffix(".git")
    return text.lower() if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", text) else None


def _ref(value: Any) -> str | None:
    text = _text(value, 500)
    if not text or text == "withheld source text":
        return None
    if text.startswith(("https://", "http://")):
        parsed = urlsplit(text)
        if parsed.username or parsed.password or parsed.query:
            return None
    return text


def _refs(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [text for value in values[:100] if (text := _ref(value))]


def _quality(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return None
    if isinstance(value, dict):
        return {key: _quality(item, depth + 1) for key, item in value.items() if key in _QUALITY_FIELDS}
    if isinstance(value, list):
        return [_quality(item, depth + 1) for item in value[:40]]
    if isinstance(value, str):
        return _text(value, 600)
    if value is None or isinstance(value, (bool, int)):
        return value
    return None


def _component(row: Any, source: str, role: str) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    result = {key: _text(row[key]) for key in _COMPONENT_FIELDS if key in row and isinstance(row[key], str)}
    if not result:
        return None
    result.update({"source": source, "source_role": role, "evidence_refs": _refs(row.get("evidence_refs"))})
    for key in ("criteria", "checks", "latest_stable_release", "selected_pin_source", "latest_release_source", "source_findings"):
        if key in row:
            result[key] = _quality(row[key])
    for key in ("archived", "disabled"):
        if isinstance(row.get(key), bool):
            result[key] = row[key]
    return result


def _components(rows: Any, source: str, role: str) -> list[dict[str, Any]]:
    return [safe for row in rows if (safe := _component(row, source, role))] if isinstance(rows, list) else []


class _ArrayRecords:
    """Incremental reader for the producer's compact JSON array."""

    def __init__(self, stream):
        self.stream, self.buffer, self.eof = stream, "", False
        self.decoder = json.JSONDecoder()

    def _fill(self):
        block = self.stream.read(8192)
        if block:
            self.buffer += block
        else:
            self.eof = True

    def _char(self):
        self.buffer = self.buffer.lstrip()
        while not self.buffer and not self.eof:
            self._fill()
            self.buffer = self.buffer.lstrip()
        return self.buffer[:1]

    def __iter__(self):
        if self._char() != "[":
            raise ValueError("compact rows must be a JSON array")
        self.buffer = self.buffer[1:]
        while True:
            char = self._char()
            if char == "]":
                self.buffer = self.buffer[1:]
                while not self.eof:
                    self._fill()
                if self.buffer.strip():
                    raise ValueError("trailing compact source content")
                return
            while True:
                try:
                    row, end = self.decoder.raw_decode(self.buffer)
                    if len(self.buffer[:end].encode("utf-8")) > _RECORD_LIMIT:
                        raise ValueError("compact record exceeds read limit")
                    self.buffer = self.buffer[end:]
                    break
                except json.JSONDecodeError:
                    if self.eof or len(self.buffer) > _RECORD_LIMIT:
                        raise ValueError("invalid or oversized compact source record") from None
                    self._fill()
            if not isinstance(row, dict):
                raise ValueError("compact source record must be an object")
            yield row
            char = self._char()
            if char == ",":
                self.buffer = self.buffer[1:]
            elif char != "]":
                raise ValueError("compact source array separator missing")


def _g5_quality(row: dict[str, Any]) -> dict[str, Any]:
    """Project named quality metadata; absence is not a favorable result."""
    categories = {
        "maintenance": ("maintenance", "maintenance_provenance", "archived", "disabled", "pushed_at"),
        "releases": ("releases", "latest_stable_release", "latest_release", "release_relationship"),
        "tests": ("tests", "test_evidence"),
        "benchmarks": ("benchmarks", "benchmark", "measured_cost"),
    }
    result = {}
    for category, names in categories.items():
        fields = {name: _quality(row[name]) for name in names if name in row}
        observed = any(value is not None and value != {} and value != [] for value in fields.values())
        result[category] = {"status": "recorded source metadata" if observed else "UNREPORTED", "fields": fields}
    qualification = row.get("qualification") if isinstance(row.get("qualification"), dict) else {}
    result["qualification"] = {key: _label(qualification.get(key)) for key in ("catalog", "role", "slot")}
    result["evidence_class"] = _text(row.get("evidence_class"), 100)
    result["scope"] = "compact source metadata; qualification labels do not establish measurement or acceptance"
    return result


def _g5_row(row: dict[str, Any], source: str, gate_met: bool) -> dict[str, Any]:
    pin = row.get("pin") if isinstance(row.get("pin"), dict) else {}
    pending = row.get("pending") if isinstance(row.get("pending"), dict) else {}
    sources = row.get("primary_sources") if isinstance(row.get("primary_sources"), list) else []
    primary = [{key: (_ref(item.get(key)) if key in ("locator", "repository", "archive_member", "pointer") else item[key] if key == "capture_sha256" and re.fullmatch(r"[a-fA-F0-9]{64}", item[key]) else None if key == "capture_sha256" else _text(item.get(key), 500)) for key in ("locator", "refresh_date", "repository", "pin", "evidence_class", "archive_member", "capture_sha256", "pointer", "subject") if isinstance(item.get(key), str)} for item in sources if isinstance(item, dict)]
    witness = row.get("source_entry_witness") if isinstance(row.get("source_entry_witness"), dict) else {}
    return {
        "name": _text(row.get("repository_or_entry"), 240),
        "repository_or_entry": _text(row.get("repository_or_entry"), 240),
        "repository": _repo(row.get("repository_or_entry")) or _repo(pin.get("repository_or_source")),
        "status": "candidate; G5 MET in current view" if gate_met else "candidate, PENDING G5",
        "accepted": False, "recorded_disposition": _text(row.get("disposition"), 100),
        "evidence_class": _text(row.get("evidence_class"), 100),
        "candidate_implementation_status": _text(row.get("candidate_implementation_status"), 240),
        "pin": {key: _text(pin.get(key), 300) for key in ("kind", "repository_or_source", "subject", "version_or_commit")},
        "pending": {key: _text(pending.get(key), 300) for key in ("measurement", "status", "provisional_disposition")},
        "primary_sources": primary, "refresh_date": _text(row.get("refresh_date"), 100),
        "quality_evidence": _g5_quality(row),
        "source_entry_witness": {"archive_member": _ref(witness.get("archive_member")), "pointer": _ref(witness.get("pointer")), "sha256": witness.get("sha256") if isinstance(witness.get("sha256"), str) and re.fullmatch(r"[a-fA-F0-9]{64}", witness["sha256"]) else None},
        "decision_scope": _text(row.get("decision_scope"), 600),
        "source": source, "slot": _label(row.get("slot")),
        "source_pointer": _ref(row.get("source_pointer")),
        "capture_sha256": row.get("capture_sha256") if isinstance(row.get("capture_sha256"), str) and _HASH.fullmatch(row["capture_sha256"]) else None,
    }


def _g5(asset: Path, layers: list[dict[str, Any]], gate_met: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt = _receipt(asset, str(asset))
    meta = {"status": "candidate, PENDING G5" if not gate_met else "G5 MET in current view", "accepted": False, "rows": 0, "matched_rows": 0, "unmatched_rows": 0, "matched_associations": 0, "member": _ROWS_MEMBER}
    by_key = {row["key"]: row for row in layers}
    by_repo: dict[str, set[str]] = {}
    for layer in layers:
        for candidate in layer["winners"] + layer["candidates"] + layer["alternatives"]:
            if repository := _repo(candidate.get("repository")):
                by_repo.setdefault(repository, set()).add(layer["key"])
    member_digest = hashlib.sha256()
    process = subprocess.Popen(["/usr/bin/zstd", "-dc", str(asset)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    found = False
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                if member.name != _ROWS_MEMBER or not member.isfile():
                    continue
                found = True
                meta["member_bytes"] = member.size
                handle = archive.extractfile(member)
                # TextIOWrapper would hide the exact bytes used by the member receipt.
                class TextChunks:
                    decoder = codecs.getincrementaldecoder("utf-8")()
                    def read(self, size):
                        block = handle.read(size)
                        member_digest.update(block)
                        return self.decoder.decode(block, final=not block)
                for record in _ArrayRecords(TextChunks()):
                    meta["rows"] += 1
                    qualification = record.get("qualification") if isinstance(record.get("qualification"), dict) else {}
                    catalog, slot = qualification.get("catalog"), qualification.get("slot")
                    explicit = f"{catalog}:{slot}" if isinstance(catalog, str) and isinstance(slot, str) else None
                    matches = {explicit} if explicit in by_key else set()
                    pin = record.get("pin") if isinstance(record.get("pin"), dict) else {}
                    for value in (record.get("repository_or_entry"), pin.get("repository_or_source")):
                        if repository := _repo(value):
                            matches.update(by_repo.get(repository, set()))
                    if matches:
                        meta["matched_rows"] += 1
                        safe = _g5_row(record, str(asset) + "#/" + _ROWS_MEMBER, gate_met)
                        for key in sorted(matches):
                            by_key[key]["g5_candidates"].append(safe)
                            meta["matched_associations"] += 1
                    else:
                        meta["unmatched_rows"] += 1
        if process.wait(timeout=30) != 0 or not found:
            raise ValueError("retained G5 asset could not supply compact rows")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()
    receipt.update({"member": _ROWS_MEMBER, "member_sha256": member_digest.hexdigest(), "member_bytes": meta.get("member_bytes")})
    return meta, receipt


def build(root: Path, state_root: Path, asset: Path | None = None) -> dict[str, Any]:
    """Build one dated source section for every manifest-declared layer."""
    manifest_path = root / "catalogs/landscape/manifest.json"
    manifest = _json(manifest_path)
    catalogs = manifest.get("catalogs")
    if not isinstance(catalogs, dict) or not catalogs:
        raise ValueError("landscape manifest requires a catalogs map")
    sources = [_receipt(manifest_path, "catalogs/landscape/manifest.json")]
    layers, documents = [], {}
    for catalog, relative in catalogs.items():
        if not _label(catalog) or not isinstance(relative, str) or not relative.startswith("catalogs/landscape/") or ".." in Path(relative).parts:
            raise ValueError("canonical catalog path is outside its source root")
        path = root / relative
        doc = _json(path)
        documents[relative] = doc
        sources.append(_receipt(path, relative))
        if not isinstance(doc.get("layers"), list):
            raise ValueError("canonical catalog requires layers")
        for index, row in enumerate(doc["layers"]):
            if not isinstance(row, dict) or not _label(row.get("layer_id")):
                raise ValueError("canonical layer requires a bounded layer_id")
            pointer = relative + f"#/layers/{index}"
            winners = _components(row.get("winners"), pointer, "dated winner")
            candidates = _components(row.get("candidates"), pointer, "dated candidate")
            alternatives = _components(row.get("alternatives"), pointer, "dated alternative")
            layer = {
                "key": f"{catalog}:{row['layer_id']}", "catalog": catalog, "layer_id": row["layer_id"],
                **{key: _text(row.get(key)) for key in ("title", "requirement", "current_choice", "decision", "verdict_status", "rationale", "checked_at")},
                "evidence_refs": _refs(row.get("evidence_refs")), "limitations": [_text(value, 700) for value in row.get("limitations", []) if isinstance(value, str)],
                "winners": winners, "candidates": candidates, "alternatives": alternatives,
                "rejected": [candidate for candidate in candidates + alternatives if (candidate.get("disposition") or "").lower() in {"reject", "rejected"}],
                "source_quality": [], "dated_views": [], "g5_candidates": [],
                "adoption_stage": "UNREPORTED", "source_refs": [pointer],
            }
            layer["source_choice"] = {key: layer[key] for key in ("current_choice", "decision", "verdict_status", "checked_at", "source_refs")}
            layers.append(layer)
    by_key = {row["key"]: row for row in layers}
    if len(by_key) != len(layers):
        raise ValueError("duplicate canonical landscape layer")
    # Existing landscape catalogs remain dated source views; no later view is
    # silently substituted for the canonical selected values.
    id_keys: dict[str, list[str]] = {}
    for row in layers:
        id_keys.setdefault(row["layer_id"], []).append(row["key"])
    by_id = {layer_id: keys[0] for layer_id, keys in id_keys.items() if len(keys) == 1}
    by_repo: dict[str, set[str]] = {}
    for row in layers:
        for component in row["winners"] + row["candidates"] + row["alternatives"]:
            if repository := _repo(component.get("repository")):
                by_repo.setdefault(repository, set()).add(row["key"])
    for path in sorted((root / "catalogs/landscape").glob("*.json")):
        relative = path.relative_to(root).as_posix()
        if relative in documents or path == manifest_path:
            continue
        doc = _json(path)
        sources.append(_receipt(path, relative))
        for collection in ("layers", "rows", "candidates", "components"):
            for index, record in enumerate(doc.get(collection, []) if isinstance(doc.get(collection), list) else []):
                if not isinstance(record, dict):
                    continue
                pointer = relative + f"#/{collection}/{index}"
                matches = set()
                if record.get("catalog") and record.get("layer_id"):
                    key = f"{record['catalog']}:{record['layer_id']}"
                    if key in by_key:
                        matches.add(key)
                elif record.get("layer_id") in by_id:
                    matches.add(by_id[record["layer_id"]])
                explicit_layers = record.get("layers") if isinstance(record.get("layers"), list) else []
                for layer_id in explicit_layers:
                    if isinstance(layer_id, str) and layer_id in by_id:
                        matches.add(by_id[layer_id])
                if repository := _repo(record.get("repository")):
                    matches.update(by_repo.get(repository, set()))
                safe = _component(record, pointer, "dated supplementary source")
                for key in sorted(matches):
                    if safe and collection in ("components", "candidates"):
                        by_key[key]["source_quality"].append(safe)
                    elif safe:
                        by_key[key]["dated_views"].append(safe)
    cc_path = state_root / "coordination/command-center/pages/cc-now.json"
    cc = _json(cc_path) if cc_path.exists() else {}
    if cc_path.exists():
        sources.append(_receipt(cc_path, str(cc_path)))
    gates = cc.get("gates") if isinstance(cc.get("gates"), list) else []
    g5_gate = next((gate for gate in gates if isinstance(gate, dict) and gate.get("id") == "G5"), {})
    gate_met = g5_gate.get("state") == "MET"
    chosen_asset = asset or state_root / _FINAL_ASSET
    notes = ["Dated source choices are retained; candidate metadata does not establish installation or acceptance.", "Per-tool adoption stages are not reported by the current source."]
    if chosen_asset.exists():
        g5, receipt = _g5(chosen_asset, layers, gate_met)
        sources.append(receipt)
    else:
        g5 = {"status": "not reported", "accepted": False, "rows": None, "matched_rows": None, "unmatched_rows": None}
    g5["gate_state"] = _text(g5_gate.get("state"), 40)
    g5["current_view_utc"] = _text(cc.get("updated_utc"), 40)
    program = cc.get("adoption_program") if isinstance(cc.get("adoption_program"), dict) else {}
    adoption_program = {"global_stages": [_text(stage, 240) for stage in program.get("stages", []) if isinstance(stage, str)], "layers": [{"layer": _text(row.get("layer"), 120), "state": _text(row.get("state"), 800)} for row in program.get("layers", []) if isinstance(row, dict)], "source": str(cc_path) + "#/adoption_program", "per_tool_stage": "UNREPORTED"}
    adoption_path = state_root / "coordination/command-center/pages/adoption-now.json"
    observation = {}
    if adoption_path.exists():
        adoption = _json(adoption_path)
        sources.append(_receipt(adoption_path, str(adoption_path)))
        orchestration = adoption.get("orchestration") if isinstance(adoption.get("orchestration"), dict) else {}
        observation = {"schema": _text(adoption.get("schema"), 100), "generated_utc": _text(adoption.get("generated_utc"), 40), "window_hours": adoption.get("window_hours") if isinstance(adoption.get("window_hours"), int) else None, "orchestration_published": bool(orchestration), "unmeasured": [_text(item, 200) for item in orchestration.get("unmeasured", []) if isinstance(item, str)]}
    skill_manifest = root / "adoption/skills/manifest.json"
    design = {"status": "not reported"}
    if skill_manifest.exists():
        skills = _json(skill_manifest)
        sources.append(_receipt(skill_manifest, "adoption/skills/manifest.json"))
        frontend = next((row for row in skills.get("skills", []) if isinstance(row, dict) and row.get("name") == "frontend-design"), {})
        design = {key: _text(frontend.get(key), 500) for key in ("name", "source", "url", "ref", "path", "tree_sha", "skill_md_sha256", "status")}
        skill_path = Path.home() / ".agents/skills/frontend-design/SKILL.md"
        if skill_path.is_file():
            design["installed"] = _receipt(skill_path, str(skill_path))
        design["source_manifest"] = "adoption/skills/manifest.json"
    helper_path = Path(__file__).with_name("architecture_evidence.py")
    evidence_index = {}
    if helper_path.exists():
        spec = importlib.util.spec_from_file_location("local_architecture_evidence", helper_path)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        immutable = helper.enrich(root, state_root, layers)
        evidence_index = helper.evidence_index(layers)
        observation = immutable
        sources.extend(immutable.get("evidence_sources", []))
        if immutable.get("verified"):
            sources.append(_receipt(Path(immutable["path"]), immutable["path"]))
    return {"schema": "local-architecture-sources/1", "layers": layers, "layer_count": len(layers), "sources": sources, "design": design, "g5": g5, "adoption_program": adoption_program, "adoption_observation": observation, "evidence_index": evidence_index, "notes": notes}
