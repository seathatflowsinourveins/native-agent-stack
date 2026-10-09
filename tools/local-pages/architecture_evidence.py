"""Source-bound E2E metadata and recorded invocation observations.

This helper does not execute a harness or infer adoption from an installation.
"""

from datetime import datetime, timezone
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import re
import sys


_LIMIT = 2 * 1024 * 1024
_LABEL = re.compile(r"[A-Za-z0-9 ._:/()+-]{1,120}\Z")
_SENSITIVE = re.compile(r"@|\bBearer\s|\bsk-|\bgh[pousr]_|\bgithub_pat_|[A-Za-z0-9]{24,}", re.I)
_ALIASES = {"plugin_context-mode_context-mode": "context-mode", "plugin_socraticode_socraticode": "socraticode"}
_SOURCE_SPEC = importlib.util.spec_from_file_location("architecture_evidence_sources", Path(__file__).with_name("evidence_sources.py"))
_receipt_sources = importlib.util.module_from_spec(_SOURCE_SPEC)
_SOURCE_SPEC.loader.exec_module(_receipt_sources)
_POLICY_SPEC = importlib.util.spec_from_file_location("architecture_evidence_policy", Path(__file__).with_name("source_policy.py"))
_policy = importlib.util.module_from_spec(_POLICY_SPEC)
_POLICY_SPEC.loader.exec_module(_policy)
SOURCE_POLICY_PATH = Path(__file__).with_name("source_policy.json")


def architecture_reads(root, state_root=None):
    """Use independently reviewed paths before opening any evidence bytes."""
    return _policy.ArchitectureReads(Path(root), Path(state_root) if state_root is not None else Path(root), policy_path=SOURCE_POLICY_PATH)


def _label(value):
    if value == "native-agent-stack-1a":
        return "owner session (reports to CC)"
    return value if isinstance(value, str) and _LABEL.fullmatch(value) and not _SENSITIVE.search(value) else "withheld label"


def _read(path, reads, role="architecture_static"):
    try:
        raw, _ = reads.read(role, path, max_bytes=_LIMIT)
    except FileNotFoundError:
        return None
    value = json.loads(raw)
    return value if isinstance(value, dict) else None


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def host_receipts_index(state_root, reads=None):
    """Return the CC's local metadata projection without accessing raw receipts."""
    reads = reads or architecture_reads(Path(__file__).resolve().parents[2], state_root)
    return _receipt_sources.host_receipts_index(state_root, reads=reads)


def invocation_source(state_root, reads=None):
    """Select the newest hash-verified published snapshot by observation time."""
    directory = state_root / "coordination/ns2604-coop/notes/adoption-evidence-20261008"
    reads = reads or architecture_reads(Path(__file__).resolve().parents[2], state_root)
    valid = []
    for path in directory.glob("adoption-now-*.json"):
        if not re.fullmatch(r"adoption-now-[a-f0-9]{16}\.json", path.name):
            continue
        raw, metadata = reads.read("architecture_adoption_snapshot", path, max_bytes=_LIMIT)
        digest = metadata["sha256"]
        if path.name != f"adoption-now-{digest[:16]}.json":
            continue
        try:
            document = json.loads(raw)
            timestamp = datetime.fromisoformat(document["generated_utc"].replace("Z", "+00:00"))
            hours = document.get("window_hours")
            if document.get("schema") != "adoption-now/1" or timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0 or _count(hours) in (None, 0):
                continue
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
        valid.append((timestamp, path, digest, document))
    if not valid:
        return {"status": "not reported", "verified": False, "path": None, "sha256": None, "generated_utc": None, "window_hours": None, "roles": []}
    _, path, digest, document = max(valid, key=lambda item: (item[0], item[2]))
    roles = []
    for category, client, population in (("claude_by_role", "Claude", "sessions"), ("codex_by_lane", "Codex", "conversations")):
        published = document.get(category)
        if not isinstance(published, dict):
            continue
        for name, row in published.items():
            if not isinstance(row, dict):
                continue
            servers = row.get("servers")
            safe_servers = {server: {"calls": _count(record.get("calls")), population: _count(record.get(population))} for server, record in servers.items() if isinstance(servers, dict) and isinstance(record, dict) and _label(server) != "withheld label"} if isinstance(servers, dict) else None
            roles.append({"name": _label(name), "client": client, population: _count(row.get(population)), "servers": safe_servers})
    orchestration = document.get("orchestration") if isinstance(document.get("orchestration"), dict) else {}
    safe_orchestration = {}
    for category in ("claude_by_role", "codex_by_lane"):
        group = orchestration.get(category)
        if not isinstance(group, dict):
            continue
        allowed = {"Agent", "ListAgents", "SendMessage", "TaskStop", "followup_task", "list_agents", "send_message", "spawn_agent", "wait_agent"}
        safe_orchestration[category] = {_label(name): {key: _count(value) for key, value in row.items() if key in allowed} for name, row in group.items() if isinstance(row, dict)}
    return {"status": "recorded", "verified": True, "path": str(path), "sha256": digest, "generated_utc": document["generated_utc"], "window_hours": document["window_hours"], "roles": roles, "orchestration": safe_orchestration, "orchestration_published": bool(orchestration)}


def _identity(row):
    result = set()
    for key in ("component_id", "name", "repository"):
        value = row.get(key)
        if isinstance(value, str) and value:
            result.add(value.lower().removeprefix("https://github.com/").removesuffix(".git").rstrip("/"))
    for value in row.get("component_ids", []) if isinstance(row.get("component_ids"), list) else []:
        if isinstance(value, str) and value:
            result.add(value.lower())
    return result


def _invoke(component, observation):
    names = {_ALIASES.get(value, value) for value in (component.get("component_id"), component.get("name")) if isinstance(value, str)}
    rows = []
    client = "Claude" if "claude-code" in names else "Codex" if "codex" in names else None
    for role in observation.get("roles", []):
        if client and role.get("client") == client:
            population = "sessions" if client == "Claude" else "conversations"
            rows.append({"role": role["name"], "client": client, "calls": role.get(population), population: role.get(population), "window_hours": observation.get("window_hours")})
            continue
        if client:
            continue
        for server, record in (role.get("servers") or {}).items():
            if _ALIASES.get(server, server) in names:
                population = "sessions" if role["client"] == "Claude" else "conversations"
                rows.append({"role": role["name"], "client": role["client"], "server": server, "calls": record["calls"], population: record.get(population), "window_hours": observation.get("window_hours")})
    values = [row["calls"] for row in rows]
    total = sum(values) if rows and all(value is not None for value in values) else None
    if total is not None:
        reason = None
    elif observation.get("status") == "not reported":
        reason = "retained observation snapshot is unavailable or failed verification"
    elif client:
        reason = "client session population is absent or incomplete in the retained observation producer"
    elif rows:
        reason = "an attributed MCP server row exists, but its published call count is absent or invalid"
    else:
        reason = "retained producer attributes MCP server calls; Bash-run CLIs, skills and workflows have no component attribution in this producer"
    return {"status": "recorded" if total is not None else "component attribution not reported", "measure": "sessions" if client else "calls", "calls": total, "sessions": total if client else None, "reason": reason, "count_class": "observational", "roles": rows, "path": observation.get("path"), "sha256": observation.get("sha256"), "generated_utc": observation.get("generated_utc"), "window_hours": observation.get("window_hours")}


def _native_receipts(root):
    """Reuse the repository's supported read-only registry/pin interfaces."""
    if not (root / "scripts/host_receipts.py").is_file():
        return None
    original = list(sys.path)
    try:
        sys.path.insert(0, str(root))
        return importlib.import_module("scripts.host_receipts")
    except ImportError:
        return None
    finally:
        sys.path[:] = original


def _safe_path(relative, registered=False):
    return isinstance(relative, str) and relative.endswith(".json") and not relative.startswith(("/", "http")) and ".." not in Path(relative).parts and (registered or relative.startswith(("evidence/hosts/", "evidence/receipts/", "evidence/artifacts/", "blueprints/"))) and not re.search(r"credential|secrets?|client.secret|(?:^|/)env(?:ironment)?[./]|\.env|/private/|/logs?/|/raw/|rollout|prompt", relative, re.I)


def _safe_command(value):
    if not isinstance(value, str) or not value or len(value) > 1500:
        return None
    # Commit hashes are legitimate harness arguments; credential forms are not.
    if re.search(r"[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}|\bBearer\s|\bsk-|\bgh[pousr]_|\bgithub_pat_|(?:api[_-]?key|authorization|access_token)\s*[=:]|--?(?:api[-_]?key|authorization|access[-_]?token|password|secret)\b", value, re.I):
        return None
    return value


class _EvidenceSources:
    """Load registered metadata once and cache only explicitly linked receipts."""

    def __init__(self, root, state_root=None, reads=None):
        self.root, self.cache, self.registered, self.fresh, self.sources = root, {}, [], {}, []
        self.projections = {}
        self.readability = {}
        self.reads = reads or architecture_reads(root, state_root)
        self.native = _native_receipts(root)
        index_path = root / "manifests/evidence.json"
        try:
            index_raw, index_metadata = self.reads.read("architecture_registry", index_path)
        except FileNotFoundError:
            index_raw, index_metadata = b"{}", None
        doc = json.loads(index_raw)
        if not isinstance(doc, dict):
            raise ValueError("Architecture evidence registry must be an object")
        records = {row["path"]: row for row in doc.get("files", []) if isinstance(row, dict) and isinstance(row.get("path"), str)}
        self.receipts = {row["path"]: row for row in doc.get("receipts", []) if isinstance(row, dict) and isinstance(row.get("path"), str)}
        for relative in self.receipts:
            self.reads.authorize("architecture_receipt", root / relative)
        for relative in records:
            if relative.endswith(".json") and relative.startswith(("evidence/hosts/", "evidence/receipts/")):
                self.reads.authorize("architecture_receipt", root / relative)
        self.explicit_native_paths = {path for path, row in self.receipts.items() if row.get("kind") in _receipt_sources.NATIVE_KINDS and _safe_path(path, registered=True)}
        self.explicit_receipt_paths = {path for path in self.receipts if _safe_path(path, registered=True)}
        paths = [(path, record) for path, record in records.items() if _safe_path(path, registered=path in self.explicit_receipt_paths) and (path.startswith(("evidence/hosts/", "evidence/receipts/")) or path in self.explicit_receipt_paths)]
        self.registry_expected = {path: record.get("sha256") for path, record in records.items() if _safe_path(path, registered=path in self.explicit_receipt_paths)}
        scope_bytes = sum(record.get("bytes", 0) for _, record in paths if isinstance(record.get("bytes"), int) and not isinstance(record.get("bytes"), bool) and record["bytes"] >= 0)
        self.stats = {"registered_metadata_paths": len(paths), "registered_metadata_bytes": scope_bytes, "registered_native_receipts": len(self.explicit_native_paths), "native_registry_verified": 0, "registry_verified": 0, "registry_digest_mismatch": 0, "registry_unreadable_or_nonobject": 0, "registry_read_limit": 0, "readiness_tools": 0}
        if scope_bytes > 64 * 1024 * 1024:
            raise ValueError("registered receipt metadata exceeds the bounded read scope")
        if index_metadata is not None:
            self.sources.append({"path": "manifests/evidence.json", "sha256": index_metadata["sha256"], "bytes": index_metadata["bytes"]})
        actual_bytes = 0
        for relative, record in paths:
            loaded = self.load(relative, record.get("sha256"))
            actual_bytes += loaded["bytes"] if loaded else 0
            if actual_bytes > 64 * 1024 * 1024:
                raise ValueError("registered receipt metadata exceeds the bounded read scope")
            if loaded and loaded["digest_verified"]:
                loaded["registry"] = self.receipts.get(relative, {})
                self.registered.append(loaded)
                self.stats["registry_verified"] += 1
                self.stats["native_registry_verified"] += int(loaded["registry"].get("kind") in _receipt_sources.NATIVE_KINDS)
            elif loaded:
                self.stats["registry_digest_mismatch"] += 1
            else:
                self.stats["registry_unreadable_or_nonobject"] += 1
        self.stats["registered_metadata_bytes"] = actual_bytes
        readiness_path = root / "catalogs/north-star/readiness.json"
        try:
            raw, metadata = self.reads.read("architecture_readiness", readiness_path, max_bytes=_LIMIT)
            doc = json.loads(raw)
            if not isinstance(doc, dict):
                raise ValueError("Architecture readiness metadata must be an object")
            self.sources.append({"path": "catalogs/north-star/readiness.json", "sha256": metadata["sha256"], "bytes": metadata["bytes"]})
        except FileNotFoundError:
            doc = {}
        for layer_index, layer in enumerate(doc.get("layers", []) if isinstance(doc.get("layers"), list) else []):
            for tool_index, tool in enumerate(layer.get("selected_tools", []) if isinstance(layer, dict) and isinstance(layer.get("selected_tools"), list) else []):
                fields = tool.get("fields") if isinstance(tool, dict) and isinstance(tool.get("fields"), dict) else {}
                identity = {key: fields[key].get("value") for key in ("component_id", "repository") if isinstance(fields.get(key), dict)}
                fresh = fields.get("fresh_session_invoke") if isinstance(fields.get("fresh_session_invoke"), dict) else {}
                receipt = fresh.get("receipt") if isinstance(fresh.get("receipt"), dict) else {}
                status = fresh.get("status") if isinstance(fresh.get("status"), str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,59}", fresh["status"]) else "UNREPORTED"
                value = fresh.get("value")
                safe = {"status": status, "value": value if value is None or isinstance(value, (bool, int)) else "reported source value", "source": f"catalogs/north-star/readiness.json#/layers/{layer_index}/selected_tools/{tool_index}/fields/fresh_session_invoke", "receipt": {key: receipt.get(key) for key in ("root", "path", "sha256", "locator") if isinstance(receipt.get(key), str) and not re.search(r"@|Bearer|github_pat_", receipt[key])}}
                for key in _identity(identity):
                    self.fresh.setdefault(key, []).append(safe)
                self.stats["readiness_tools"] += 1

    def load(self, relative, expected=None):
        if not _safe_path(relative, registered=relative in self.explicit_receipt_paths):
            return None
        if relative not in self.cache:
            path = self.root / relative
            try:
                raw, metadata = self.reads.read("architecture_receipt", path, max_bytes=_LIMIT)
            except self.reads.limit_error:
                self.cache[relative] = None
                self.readability[relative] = "approved receipt exceeds the metadata read bound; body unmeasured"
                self.stats["registry_read_limit"] += 1
            except OSError:
                self.cache[relative] = None
            else:
                # Reader policy errors remain outside the parse-error fallback,
                # including readers imported through another module instance.
                try:
                    document = json.loads(raw)
                except (ValueError, UnicodeError):
                    document = None
                if isinstance(document, list):
                    document = {"commands": document}
                elif not isinstance(document, dict):
                    document = None
                if not document:
                    self.cache[relative] = None
                else:
                    digest = metadata["sha256"]
                    self.cache[relative] = {"path": relative, "sha256": digest, "bytes": len(raw), "document": document}
        value = self.cache[relative]
        expected = expected if expected is not None else self.registry_expected.get(relative)
        return {**value, "digest_verified": isinstance(expected, str) and expected == value["sha256"], "digest_required": expected is not None} if value else None

    def fresh_for(self, component):
        return [row for identity in sorted(_identity(component)) for row in self.fresh.get(identity, [])]

    def project(self, loaded, component):
        identity = component.get("component_id")
        key = (loaded["path"], identity)
        if key not in self.projections:
            registry = self.receipts.get(loaded["path"], {})
            projection = _receipt_sources.receipt_projection(loaded["document"], registry, identity, _safe_command)
            linked = []
            for relative in _receipt_sources.linked_receipt_paths(loaded["document"]):
                if relative not in self.registry_expected:
                    continue
                extra = self.load(relative)
                if not extra or not extra["digest_verified"]:
                    continue
                detail = _receipt_sources.receipt_projection(extra["document"], registry, identity, _safe_command)
                for field in ("command", "result", "observed_pin"):
                    if projection.get(field) is None and detail.get(field) is not None:
                        projection[field] = detail[field]
                        projection["metadata_locators"][field] = relative + "#" + extra["sha256"]
                        if field == "command":
                            projection["command_count"] = detail["command_count"]
                            projection["command_programs"] = detail["command_programs"]
                linked.append({"path": relative, "sha256": extra["sha256"]})
            projection["linked_receipts"] = linked
            projection["missing_metadata"] = [f"receipt does not publish {label}" for field, label in (("date", "a parseable UTC observation date"), ("command", "a safe execution command"), ("result", "a machine result or exit code")) if not projection.get(field)]
            self.projections[key] = projection
        return self.projections[key]


def _e2e(root, component, matrix, matrix_source, sources=None):
    identity = _identity(component)
    matches = [row for row in matrix if identity.intersection(_identity(row))]
    evidence_class = next((row.get("evidence_class") for row in matches if isinstance(row.get("evidence_class"), str)), component.get("evidence_class"))
    selected_pin = component.get("pin")
    if isinstance(selected_pin, dict):
        selected_pin = selected_pin.get("version_or_commit")
    base = {"status": "no upstream E2E evidence", "verified": False, "receipt_verified": False, "reason": "no hash-verified native E2E receipt or qualifying vendor test-suite receipt names this component", "date": None, "path": None, "sha256": None, "command": None, "result": None, "kind": None, "evidence_scope": None, "selected_pin": selected_pin, "observed_pin": None, "pin_matches": None, "evidence_class": evidence_class, "class_status": "RECORDED" if evidence_class in ("native_proven", "local_integration", "source_review", "synthetic") else "UNVERIFIED", "class_source": matrix_source if matches else component.get("source")}
    # Only explicit receipt pointers are followed, never directories or logs.
    def references(rows):
        refs = []
        for row in rows:
            refs.extend(value for value in row.get("evidence_refs", []) if isinstance(value, str)) if isinstance(row.get("evidence_refs"), list) else None
            refs.extend(row[key] for key in ("receipt", "receipt_ref", "receipt_path") if isinstance(row.get(key), str))
        return list(dict.fromkeys(refs))
    ordered = [("component matrix", ref, None) for ref in references(matches)]
    if sources:
        for entry in sources.registered:
            if identity.intersection(_identity(entry["document"]) | _identity(entry.get("registry", {}))):
                ordered.append(("host registry" if entry["path"].startswith("evidence/hosts/") else "registered receipt", entry["path"], entry["sha256"]))
        for field in sources.fresh_for(component):
            receipt = field.get("receipt", {})
            if field.get("status") in ("RECORDED", "VERIFIED", "PASS", "recorded", "documented-as-done") and receipt.get("root") == "repo":
                ordered.append(("readiness Fresh invocation", receipt.get("path"), receipt.get("sha256")))
    ordered.extend(("native_proven source record", ref, None) for ref in references([component]))
    proofs, qualifying, other, seen = [], [], [], set()
    for tier, relative, expected in ordered:
        if relative in seen or not _safe_path(relative, registered=bool(sources and relative in sources.explicit_receipt_paths)):
            continue
        seen.add(relative)
        path = root / relative
        if sources:
            loaded = sources.load(relative, expected)
            if not loaded or loaded["digest_required"] and not loaded["digest_verified"]:
                continue
            receipt, digest = loaded["document"], loaded["sha256"]
        else:
            try:
                reads = architecture_reads(root)
                raw, metadata = reads.read("architecture_receipt", path, max_bytes=_LIMIT)
                receipt = json.loads(raw)
            except _policy.SourcePolicyError:
                raise
            except (ValueError, OSError):
                continue
            if not receipt:
                continue
            digest = metadata["sha256"]
        registry = sources.receipts.get(relative, {}) if sources else {}
        kind = receipt.get("kind") or registry.get("kind")
        native_kind = kind in _receipt_sources.NATIVE_KINDS
        if native_kind and sources and not loaded["digest_verified"]:
            continue
        cls = receipt.get("evidence_class") or registry.get("evidence_class") or (kind if registry or native_kind else evidence_class)
        vendor_declared = cls == "RECORDED-UPSTREAM-TEST"
        result = receipt.get("result", receipt.get("status"))
        date = receipt.get("observed_at_utc", receipt.get("recorded_at_utc", receipt.get("observed_at")))
        command = _safe_command(receipt.get("harness", receipt.get("command")))
        commands = receipt.get("commands")
        safe_commands = [{"cmd": cmd, "exit": row.get("exit"), "output_sha256": row.get("output_sha256") if isinstance(row.get("output_sha256"), str) and re.fullmatch(r"[a-fA-F0-9]{64}", row["output_sha256"]) else None} for row in commands if isinstance(row, dict) and (cmd := _safe_command(row.get("cmd")))] if isinstance(commands, list) else []
        if command is None and safe_commands and all(isinstance(row["exit"], int) and row["output_sha256"] for row in safe_commands):
            command = "\n".join(row["cmd"] for row in safe_commands)
        receipt_identity = _identity(receipt) | _identity(registry)
        if not identity.intersection(receipt_identity):
            continue
        receipt_pin = sources.native.recorded_version(receipt) if sources and sources.native else receipt.get("pin")
        receipt_pin = receipt_pin or receipt.get("pin")
        projection = sources.project(loaded, component) if sources and (registry or vendor_declared) else None
        if projection:
            date, command, result = (projection[field] for field in ("date", "command", "result"))
            receipt_pin = projection.get("observed_pin")
        pin_matches = None
        if isinstance(selected_pin, str) and isinstance(receipt_pin, str) and selected_pin and receipt_pin:
            pin_matches = sources.native.pin_matches(receipt_pin, selected_pin) if sources and sources.native else receipt_pin == selected_pin
        scope = "vendor_test_suite" if vendor_declared else "native_host" if native_kind else "measurement" if kind == "artifact_measurement" else "source_provenance" if kind == "upstream_provenance" else "historical_inventory" if kind == "historical_inventory" else "compatibility_attempt" if kind == "compatibility_attempt" else "host_acceptance" if kind == "host_acceptance" else "vendor_test_suite" if isinstance(kind, str) and "e2e" in kind.lower() else "registered_receipt"
        proof = {"date": date if isinstance(date, str) and len(date) <= 40 else None, "path": relative, "sha256": digest, "command": command, "result": result if isinstance(result, str) else None, "kind": kind, "evidence_scope": scope, "evidence_class": cls if isinstance(cls, str) and len(cls) < 100 else None, "class_source": relative if receipt.get("evidence_class") or native_kind else base["class_source"], "source_tier": tier, "stage": receipt.get("stage") if receipt.get("stage") in ("install", "use", "upgrade", "recover", "remove") else None, "selected_pin": selected_pin, "observed_pin": receipt_pin, "pin_matches": pin_matches}
        if registry or native_kind or isinstance(date, str) and isinstance(result, str):
            proofs.append(proof)
        declared_e2e = isinstance(kind, str) and "e2e" in kind.lower() or receipt.get("e2e_state") in ("pass", "passed", "verified") or vendor_declared
        if registry and not declared_e2e:
            other.append({**base, **proof, "status": "recorded " + str(kind or "receipt"), "receipt_verified": loaded["digest_verified"], "reason": "; ".join(projection.get("missing_metadata", [])) or "receipt kind does not declare E2E", "result": result or "result field absent", "command_count": projection.get("command_count", 0), "command_programs": projection.get("command_programs", []), "metadata_locators": projection.get("metadata_locators", {}), "class_status": "RECORDED"})
        if not declared_e2e or not native_kind and not vendor_declared and cls not in ("native_proven", "local_integration"):
            continue
        observed = _receipt_sources.observation_time(date)
        success = isinstance(result, str) and result.lower() in ("pass", "passed", "success", "succeeded", "verified")
        complete = observed is not None and isinstance(command, str) and bool(command) and isinstance(result, str)
        # Legacy vendor claims still require their exact selected pin. Native host
        # receipts remain visible for their observed pin, including later failures.
        if not native_kind and not vendor_declared and (not complete or pin_matches is not True or not success):
            continue
        reasons = list(projection.get("missing_metadata", [])) if projection else []
        if isinstance(result, str) and not success:
            reasons.append(f"latest recorded result is {result}")
        if pin_matches is False:
            reasons.append("observed pin differs from the selected component pin")
        elif not receipt_pin:
            reasons.append("receipt does not report a component pin; selected-pin acceptance is unmeasured")
        item = {**base, **proof, "status": "recorded vendor test-suite receipt" if vendor_declared else "native host E2E receipt" if native_kind else "verified upstream E2E receipt", "verified": complete and success, "receipt_verified": bool(sources and loaded["digest_verified"]), "reason": "; ".join(reasons) or None, "result": result or "result field absent", "class_status": "RECORDED", "pin": receipt_pin, "date_precision": projection.get("date_precision") if projection else "timestamp", "date_original": projection.get("date_original") if projection else date, "date_timezone": projection.get("date_timezone") if projection else None, "command_count": projection.get("command_count", 0) if projection else len(safe_commands) or int(bool(command)), "command_programs": projection.get("command_programs", []) if projection else [], "metadata_locators": projection.get("metadata_locators", {}) if projection else {}, "linked_receipts": projection.get("linked_receipts", []) if projection else []}
        qualifying.append((observed or datetime.min.replace(tzinfo=timezone.utc), -len(qualifying), item))
    if qualifying:
        chosen = max(qualifying, key=lambda row: (row[0], row[1]))[2]
        proofs.sort(key=lambda row: _receipt_sources.observation_time(row.get("date")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return {**chosen, "source_proofs": proofs[:32], "other_evidence": other[:16], "source_proof_count": len(proofs), "selection": "newest recorded observation including failures; missing dates sort last; source priority breaks ties"}
    if other:
        latest = max(other, key=lambda row: _receipt_sources.observation_time(row.get("date")) or datetime.min.replace(tzinfo=timezone.utc))
        return {**latest, "source_proofs": proofs[:32], "other_evidence": other[:16], "source_proof_count": len(proofs)}
    return {**base, "source_proofs": proofs, "other_evidence": other}


def enrich(root, state_root, layers, reads=None):
    """Attach evidence to source candidates; keep missing observations explicit."""
    reads = reads or architecture_reads(root, state_root)
    observation = invocation_source(state_root, reads=reads)
    sources = _EvidenceSources(root, state_root, reads=reads)
    observation["evidence_sources"] = sources.sources
    matrix_path = root / "catalogs/landscape/component-evidence-matrix.json"
    document = _read(matrix_path, reads) or {}
    matrix_rows = document.get("rows") if isinstance(document.get("rows"), list) else []
    by_layer = {f"{row.get('catalog')}:{row.get('layer_id')}": row for row in matrix_rows if isinstance(row, dict)}
    for layer in layers:
        row = by_layer.get(layer["key"], {})
        matrix = [item for kind in ("winners", "alternatives") for item in row.get(kind, []) if isinstance(item, dict)]
        positive, verified, native_verified, vendor_verified, complete = False, False, False, False, False
        for category in ("winners", "candidates", "alternatives", "source_quality", "g5_candidates"):
            for component in layer.get(category, []):
                component["e2e"] = _e2e(root, component, matrix, "catalogs/landscape/component-evidence-matrix.json", sources)
                component["fresh_invocation"] = sources.fresh_for(component)
                component["invoke"] = _invoke(component, observation)
                positive |= component["invoke"]["calls"] is not None and component["invoke"]["calls"] > 0
                verified |= component["e2e"]["verified"]
                native_verified |= component["e2e"]["verified"] and component["e2e"].get("evidence_scope") == "native_host"
                vendor_verified |= component["e2e"]["verified"] and component["e2e"].get("evidence_scope") == "vendor_test_suite"
                component["evidence_complete"] = component["invoke"]["calls"] is not None and component["invoke"]["calls"] > 0 and component["e2e"]["verified"] and component["e2e"].get("pin_matches") is True
                complete |= component["evidence_complete"]
        layer["organic_invocation_positive"] = positive
        layer["verified_upstream_e2e"] = vendor_verified
        layer["verified_native_host_e2e"] = native_verified
        layer["recorded_e2e_success"] = verified
        layer["evidence_complete"] = complete
    sources.stats["linked_receipt_metadata_read"] = sum(value is not None for value in sources.cache.values())
    observation["evidence_source_stats"] = sources.stats
    return observation


def evidence_index(layers):
    """Index the already-built safe metadata; this function performs no I/O."""
    result = {}
    for layer in layers:
        for category in ("winners", "candidates", "alternatives", "source_quality", "g5_candidates"):
            for component in layer.get(category, []):
                value = {"e2e": component.get("e2e"), "invoke": component.get("invoke"), "fresh_invocation": component.get("fresh_invocation"), "source": component.get("source"), "layer": layer["key"]}
                for identity in _identity(component):
                    if value not in result.setdefault(identity, []):
                        result[identity].append(value)
    return result


def attach_inventory(items, index, *, root=None, state_root=None, sources=None, observation=None, reads=None):
    """Join source identities; registry fallback covers non-catalog components."""
    if root is not None and sources is None:
        reads = reads or architecture_reads(root, state_root)
        sources = _EvidenceSources(root, state_root, reads=reads)
    if state_root is not None and observation is None:
        observation = invocation_source(state_root, reads=reads)
    for item in items:
        if item.get("status") == "UNAPPROVED":
            reason = "Inventory identity has no independent approval; names-only discovery does not establish a source or MCP association"
            item["e2e"] = {"status": "UNREPORTED", "verified": False, "reason": reason}
            item["invoke"] = {"status": "unmeasured", "calls": None, "roles": [], "reason": reason, "count_class": "observational"}
            item["fresh_invocation"] = []
            item["evidence_complete"] = False
            continue
        matches = []
        for identity in sorted(_identity(item)):
            matches.extend(index.get(identity, []))
        available = [row["e2e"] for row in matches if row.get("e2e")]
        if root is not None and sources is not None:
            available.append(_e2e(root, item, [], item.get("source"), sources))
        item["e2e"] = max(available, key=lambda row: (bool(row.get("path")), _receipt_sources.observation_time(row.get("date")) or datetime.min.replace(tzinfo=timezone.utc))) if available else {"status": "no upstream E2E evidence", "verified": False, "reason": "no exact source identity joins this inventory item to a registered receipt"}
        item["invoke"] = _invoke(item, observation) if observation is not None else next((row.get("invoke") for row in matches if (row.get("invoke") or {}).get("calls") is not None), next((row.get("invoke") for row in matches if row.get("invoke")), {"status": "component attribution not reported", "calls": None, "roles": [], "reason": "no exact source identity joins this inventory item to retained observation producer attribution", "count_class": "observational"}))
        item["fresh_invocation"] = next((row["fresh_invocation"] for row in matches if row.get("fresh_invocation")), [])
        item["evidence_complete"] = bool(item["e2e"].get("verified") and item["e2e"].get("pin_matches") is True and item["invoke"].get("calls") is not None and item["invoke"]["calls"] > 0)
    return items
