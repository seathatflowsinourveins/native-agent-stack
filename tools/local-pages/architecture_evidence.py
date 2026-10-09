"""Source-bound E2E metadata and recorded invocation observations.

This helper does not execute a harness or infer adoption from an installation.
"""

from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys


_LIMIT = 2 * 1024 * 1024
_LABEL = re.compile(r"[A-Za-z0-9 ._:/()+-]{1,120}\Z")
_SENSITIVE = re.compile(r"@|\bBearer\s|\bsk-|\bgh[pousr]_|\bgithub_pat_|[A-Za-z0-9]{24,}", re.I)
_ALIASES = {"plugin_context-mode_context-mode": "context-mode", "plugin_socraticode_socraticode": "socraticode"}


def _label(value):
    if value == "native-agent-stack-1a":
        return "owner session (reports to CC)"
    return value if isinstance(value, str) and _LABEL.fullmatch(value) and not _SENSITIVE.search(value) else "withheld label"


def _read(path):
    if not path.exists() or path.stat().st_size > _LIMIT:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else None


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def invocation_source(state_root):
    """Select the newest hash-verified published snapshot by observation time."""
    directory = state_root / "coordination/ns2604-coop/notes/adoption-evidence-20261008"
    valid = []
    for path in directory.glob("adoption-now-*.json"):
        if path.stat().st_size > _LIMIT:
            continue
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
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
    return result


def _invoke(component, observation):
    names = {_ALIASES.get(value, value) for value in (component.get("component_id"), component.get("name")) if isinstance(value, str)}
    rows = []
    for role in observation.get("roles", []):
        for server, record in (role.get("servers") or {}).items():
            if _ALIASES.get(server, server) in names:
                population = "sessions" if role["client"] == "Claude" else "conversations"
                rows.append({"role": role["name"], "client": role["client"], "server": server, "calls": record["calls"], population: record.get(population), "window_hours": observation.get("window_hours")})
    values = [row["calls"] for row in rows]
    total = sum(values) if rows and all(value is not None for value in values) else None
    return {"status": "recorded" if rows else "component attribution not reported", "calls": total, "roles": rows, "path": observation.get("path"), "sha256": observation.get("sha256"), "generated_utc": observation.get("generated_utc"), "window_hours": observation.get("window_hours")}


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


def _safe_path(relative):
    return isinstance(relative, str) and relative.endswith(".json") and not relative.startswith(("/", "http")) and ".." not in Path(relative).parts and relative.startswith(("evidence/hosts/", "evidence/receipts/", "evidence/artifacts/", "blueprints/")) and not re.search(r"credential|secrets|\.env|/private/|/logs?/|/raw/|rollout|prompt", relative, re.I)


def _safe_command(value):
    if not isinstance(value, str) or not value or len(value) > 1500:
        return None
    # Commit hashes are legitimate harness arguments; credential forms are not.
    if re.search(r"@|\bBearer\s|\bsk-|\bgh[pousr]_|\bgithub_pat_|(?:api[_-]?key|authorization|access_token)\s*[=:]", value, re.I):
        return None
    return value


class _EvidenceSources:
    """Load registered metadata once and cache only explicitly linked receipts."""

    def __init__(self, root):
        self.root, self.cache, self.registered, self.fresh, self.sources = root, {}, [], {}, []
        self.native = _native_receipts(root)
        index_path = root / "manifests/evidence.json"
        records = self.native.evidence_files(root) if self.native else {}
        if not records and index_path.is_file() and index_path.stat().st_size <= 8 * 1024 * 1024:
            doc = json.loads(index_path.read_text(encoding="utf-8"))
            records = {row["path"]: row for row in doc.get("files", []) if isinstance(row, dict) and isinstance(row.get("path"), str)}
        paths = [(path, record) for path, record in records.items() if _safe_path(path) and path.startswith(("evidence/hosts/", "evidence/receipts/"))]
        self.registry_expected = {path: record.get("sha256") for path, record in paths}
        scope_bytes = sum((root / path).stat().st_size for path, _ in paths if (root / path).is_file())
        self.stats = {"registered_metadata_paths": len(paths), "registered_metadata_bytes": scope_bytes, "registry_verified": 0, "registry_digest_mismatch": 0, "registry_unreadable_or_nonobject": 0, "readiness_tools": 0}
        if scope_bytes > 64 * 1024 * 1024:
            raise ValueError("registered receipt metadata exceeds the bounded read scope")
        if index_path.exists():
            self.sources.append({"path": "manifests/evidence.json", "sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(), "bytes": index_path.stat().st_size})
        for relative, record in paths:
            loaded = self.load(relative, record.get("sha256"))
            if loaded and loaded["digest_verified"]:
                self.registered.append(loaded)
                self.stats["registry_verified"] += 1
            elif loaded:
                self.stats["registry_digest_mismatch"] += 1
            else:
                self.stats["registry_unreadable_or_nonobject"] += 1
        readiness_path = root / "catalogs/north-star/readiness.json"
        doc = _read(readiness_path) or {}
        if readiness_path.exists():
            self.sources.append({"path": "catalogs/north-star/readiness.json", "sha256": hashlib.sha256(readiness_path.read_bytes()).hexdigest(), "bytes": readiness_path.stat().st_size})
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
        if not _safe_path(relative):
            return None
        if relative not in self.cache:
            path = self.root / relative
            try:
                document = _read(path)
                if not document:
                    self.cache[relative] = None
                else:
                    raw = path.read_bytes()
                    digest = hashlib.sha256(raw).hexdigest()
                    self.cache[relative] = {"path": relative, "sha256": digest, "bytes": len(raw), "document": document}
            except (OSError, ValueError):
                self.cache[relative] = None
        value = self.cache[relative]
        expected = expected if expected is not None else self.registry_expected.get(relative)
        return {**value, "digest_verified": isinstance(expected, str) and expected == value["sha256"], "digest_required": expected is not None} if value else None

    def fresh_for(self, component):
        return [row for identity in sorted(_identity(component)) for row in self.fresh.get(identity, [])]


def _e2e(root, component, matrix, matrix_source, sources=None):
    identity = _identity(component)
    matches = [row for row in matrix if identity.intersection(_identity(row))]
    evidence_class = next((row.get("evidence_class") for row in matches if isinstance(row.get("evidence_class"), str)), component.get("evidence_class"))
    base = {"status": "no upstream E2E evidence", "verified": False, "date": None, "path": None, "sha256": None, "command": None, "result": None, "evidence_class": evidence_class, "class_status": "RECORDED" if evidence_class in ("native_proven", "local_integration", "source_review", "synthetic") else "UNVERIFIED", "class_source": matrix_source if matches else component.get("source")}
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
            if identity.intersection(_identity(entry["document"])):
                ordered.append(("host registry" if entry["path"].startswith("evidence/hosts/") else "registered receipt", entry["path"], entry["sha256"]))
        for field in sources.fresh_for(component):
            receipt = field.get("receipt", {})
            if field.get("status") in ("RECORDED", "VERIFIED", "PASS", "recorded", "documented-as-done") and receipt.get("root") == "repo":
                ordered.append(("readiness Fresh invocation", receipt.get("path"), receipt.get("sha256")))
    ordered.extend(("native_proven source record", ref, None) for ref in references([component]))
    proofs, qualifying = [], []
    for tier, relative, expected in ordered:
        if not _safe_path(relative):
            continue
        path = root / relative
        if sources:
            loaded = sources.load(relative, expected)
            if not loaded or loaded["digest_required"] and not loaded["digest_verified"]:
                continue
            receipt, digest = loaded["document"], loaded["sha256"]
        else:
            try:
                receipt = _read(path)
            except (ValueError, OSError):
                continue
            if not receipt:
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        kind = receipt.get("kind")
        cls = receipt.get("evidence_class", evidence_class)
        result = receipt.get("result", receipt.get("status"))
        date = receipt.get("observed_at_utc", receipt.get("recorded_at_utc", receipt.get("observed_at")))
        command = _safe_command(receipt.get("harness", receipt.get("command")))
        commands = receipt.get("commands")
        safe_commands = [{"cmd": cmd, "exit": row.get("exit"), "output_sha256": row.get("output_sha256") if isinstance(row.get("output_sha256"), str) and re.fullmatch(r"[a-fA-F0-9]{64}", row["output_sha256"]) else None} for row in commands if isinstance(row, dict) and (cmd := _safe_command(row.get("cmd")))] if isinstance(commands, list) else []
        if command is None and safe_commands and all(row["exit"] == 0 and row["output_sha256"] for row in safe_commands):
            command = "\n".join(row["cmd"] for row in safe_commands)
        receipt_identity = _identity(receipt)
        for value in receipt.get("component_ids", []) if isinstance(receipt.get("component_ids"), list) else []:
            if isinstance(value, str):
                receipt_identity.add(value.lower())
        if not identity.intersection(receipt_identity):
            continue
        selected_pin = component.get("pin")
        if isinstance(selected_pin, dict):
            selected_pin = selected_pin.get("version_or_commit")
        receipt_pin = sources.native.recorded_version(receipt) if sources and sources.native else receipt.get("pin")
        receipt_pin = receipt_pin or receipt.get("pin")
        pin_matches = sources.native.pin_matches(receipt_pin, selected_pin) if sources and sources.native and isinstance(selected_pin, str) and isinstance(receipt_pin, str) else receipt_pin == selected_pin
        if not isinstance(selected_pin, str) or not isinstance(receipt_pin, str) or not selected_pin or not receipt_pin or not pin_matches:
            continue
        if isinstance(date, str) and result in ("pass", "passed", "success", "fail", "failure"):
            proofs.append({"date": date if len(date) <= 40 else None, "path": relative, "sha256": digest, "command": command, "result": result, "evidence_class": cls if isinstance(cls, str) and len(cls) < 100 else None, "class_source": relative if receipt.get("evidence_class") else base["class_source"], "source_tier": tier, "stage": receipt.get("stage") if receipt.get("stage") in ("install", "use", "upgrade", "recover", "remove") else None})
        declared_e2e = isinstance(kind, str) and "e2e" in kind.lower() or receipt.get("e2e_state") in ("pass", "passed", "verified")
        if not declared_e2e or cls not in ("native_proven", "local_integration") or result not in ("pass", "passed", "success") or not isinstance(date, str) or not isinstance(command, str) or not command:
            continue
        if "@" in date:
            continue
        try:
            observed = datetime.fromisoformat(date.replace("Z", "+00:00"))
        except ValueError:
            continue
        if observed.tzinfo is None:
            continue
        item = {**base, "status": "verified upstream E2E receipt", "verified": True, "date": date, "path": relative, "sha256": digest, "command": command[:1500], "result": result, "evidence_class": cls, "class_status": "RECORDED", "class_source": relative if receipt.get("evidence_class") else base["class_source"], "source_tier": tier, "pin": receipt_pin}
        qualifying.append((observed.astimezone(timezone.utc), -len(qualifying), item))
    if qualifying:
        chosen = max(qualifying, key=lambda row: (row[0], row[1]))[2]
        return {**chosen, "source_proofs": proofs, "selection": "newest qualifying recorded UTC observation; source priority breaks ties"}
    return {**base, "source_proofs": proofs}


def enrich(root, state_root, layers):
    """Attach evidence to source candidates; keep missing observations explicit."""
    observation = invocation_source(state_root)
    sources = _EvidenceSources(root)
    observation["evidence_sources"] = sources.sources
    matrix_path = root / "catalogs/landscape/component-evidence-matrix.json"
    document = _read(matrix_path) or {}
    matrix_rows = document.get("rows") if isinstance(document.get("rows"), list) else []
    by_layer = {f"{row.get('catalog')}:{row.get('layer_id')}": row for row in matrix_rows if isinstance(row, dict)}
    for layer in layers:
        row = by_layer.get(layer["key"], {})
        matrix = [item for kind in ("winners", "alternatives") for item in row.get(kind, []) if isinstance(item, dict)]
        positive, verified, complete = False, False, False
        for category in ("winners", "candidates", "alternatives", "source_quality", "g5_candidates"):
            for component in layer.get(category, []):
                component["e2e"] = _e2e(root, component, matrix, "catalogs/landscape/component-evidence-matrix.json", sources)
                component["fresh_invocation"] = sources.fresh_for(component)
                component["invoke"] = _invoke(component, observation)
                positive |= component["invoke"]["calls"] is not None and component["invoke"]["calls"] > 0
                verified |= component["e2e"]["verified"]
                component["evidence_complete"] = component["invoke"]["calls"] is not None and component["invoke"]["calls"] > 0 and component["e2e"]["verified"]
                complete |= component["evidence_complete"]
        layer["organic_invocation_positive"] = positive
        layer["verified_upstream_e2e"] = verified
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


def attach_inventory(items, index):
    """Attach exact-identity evidence from an existing index without rereads."""
    for item in items:
        matches = []
        for identity in sorted(_identity(item)):
            matches.extend(index.get(identity, []))
        positive = next((row.get("e2e") for row in matches if (row.get("e2e") or {}).get("verified")), None)
        item["e2e"] = positive or next((row.get("e2e") for row in matches if row.get("e2e")), {"status": "no upstream E2E evidence", "verified": False})
        item["invoke"] = next((row.get("invoke") for row in matches if (row.get("invoke") or {}).get("calls") is not None), next((row.get("invoke") for row in matches if row.get("invoke")), {"status": "component attribution not reported", "calls": None, "roles": []}))
        item["fresh_invocation"] = next((row["fresh_invocation"] for row in matches if row.get("fresh_invocation")), [])
        item["evidence_complete"] = bool(item["e2e"].get("verified") and item["invoke"].get("calls") is not None and item["invoke"]["calls"] > 0)
    return items
