"""Bounded filename/hash inventory; no settings, credentials or instruction bodies.

Provenance comes from recorded manifests and hash lists. File presence or a
matching hash does not establish client wiring or a fresh-session acceptance.
"""

import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
from pathlib import Path

USER_ROOT = Path.home()
MAX_HASH_BYTES = 1_000_000_000
MAX_METADATA_BYTES = 1_048_576
MAX_ENTRIES = 2048
BLOCKED_NAMES = {
    "auth.json", "settings.json", "config.toml", "credentials.json",
    "credentials.toml", "client_secrets.json", "secrets.json", ".env",
}
SKIP_DIRS = {".trash", ".git", "__pycache__", "node_modules"}
SCRIPT_SUFFIXES = {".py", ".sh", ".js", ".mjs", ".cjs", ".ts"}
MAPPING_PATH = Path(__file__).with_name("architecture_mapping.json")
_POLICY = None


def _policy():
    global _POLICY
    if _POLICY is None:
        spec = importlib.util.spec_from_file_location("inventory_source_policy", Path(__file__).with_name("source_policy.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _POLICY = module
    return _POLICY


def _blocked(path):
    if any(part.lower().startswith("e2e-truth-") for part in path.parts):
        raise _policy().SourcePolicyError("protected inventory component rejected before access")
    return any(part in SKIP_DIRS for part in path.parts) or (
        path.name.lower() in BLOCKED_NAMES or path.name.startswith(".env.")
        or (path.suffix.lower() in {".json", ".toml", ".yaml", ".yml"} and any(word in path.name.lower() for word in ("credential", "secret", "auth")))
    ) or _policy().protected_path(path.as_posix())


def _inside(path, root):
    return path == root or root in path.parents


def _approved_target(path, reads, role="architecture_inventory"):
    """Check a lexical grant or frozen alias before inspecting the target."""
    if _blocked(path):
        raise _policy().SourcePolicyError("protected inventory path rejected before access")
    try:
        reads.authorize(role, path)
        return path
    except ValueError:
        pass
    aliases = reads.policy.document.get("architecture_inventory_aliases", [])
    for record in aliases:
        if not isinstance(record, dict) or record.get("root") not in reads.roots or record.get("target_root") not in reads.roots:
            raise _policy().SourcePolicyError("invalid inventory alias record")
        relative = _policy()._relative(record.get("path"))
        target_relative = _policy()._relative(record.get("target_path"))
        if reads.roots[record["root"]] / relative == path:
            target = reads.roots[record["target_root"]] / target_relative
            reads.authorize(role, target)
            return target
    return None


def _safe_path(path, reads, role="architecture_inventory"):
    approved = _approved_target(path, reads, role)
    if approved is None:
        return None
    if approved == path:
        # Direct canonical grants do not authorize a new symlink target.
        # Only the separately reviewed alias branch may resolve a lexical link.
        _policy()._check_target(path, allow_missing=True)
        return path
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError):
        raise _policy().SourcePolicyError("inventory canonical target unavailable")
    if _blocked(resolved):
        raise _policy().SourcePolicyError("protected inventory canonical target rejected before access")
    if path.name == "SKILL.md" and resolved.name != "SKILL.md":
        raise _policy().SourcePolicyError("skill alias does not name an approved instruction asset")
    reads.authorize(role, resolved)
    if resolved != approved:
        raise _policy().SourcePolicyError("inventory alias differs from its independently approved target")
    return resolved


def _entries(root):
    """List names through native no-follow directory descriptors, without leaf stat."""
    if _blocked(root):
        return []
    try:
        with _policy()._directory(root) as directory:
            entries = sorted(os.listdir(directory))
    except OSError:
        return []
    if len(entries) > MAX_ENTRIES:
        raise ValueError("inventory directory entry limit exceeded")
    return [root / name for name in entries]


def _known_container(path, reads):
    return any(_inside(reads.roots[root_name] / relative, path)
               for role in ("architecture_inventory", "architecture_inventory_metadata")
               for root_name, relative in reads.allowed.get(role, set()))


def _files(root, depth=0, metadata_suffixes=(), *, reads=None, unknown_entries=None):
    found = []
    for path in _entries(root):
        if _blocked(path):
            continue
        if path.suffix in metadata_suffixes or path.name == "SHA256SUMS" or path.name.endswith("manifest.json"):
            found.append(path)
            continue
        if depth and not path.suffix:
            if reads is not None and _known_container(path, reads):
                found.extend(_files(path, depth - 1, metadata_suffixes, reads=reads, unknown_entries=unknown_entries))
            elif unknown_entries is not None:
                unknown_entries.add(path)
        else:
            found.append(path)
    return found


def _skills(root, reads):
    found, unknown = [], []
    for path in _entries(root):
        if _blocked(path):
            continue
        candidate = path / "SKILL.md"
        if _approved_target(candidate, reads) is not None:
            found.append(candidate)
        else:
            # A reviewed container such as .system can enumerate its names;
            # an unknown entry grants no authority to enter or stat it.
            if _known_container(path, reads):
                for child in _entries(path):
                    if _blocked(child):
                        continue
                    candidate = child / "SKILL.md"
                    if _approved_target(candidate, reads) is not None:
                        found.append(candidate)
                    else:
                        unknown.append(child)
            else:
                unknown.append(path)
    return found, unknown


def _hash(path, *, reads, max_bytes=MAX_HASH_BYTES):
    return reads.read("architecture_inventory", path, max_bytes=max_bytes)


def _json(raw):
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (ValueError, UnicodeError, TypeError):
        return {}


def _repository(record):
    value = record.get("repository") or record.get("source")
    if isinstance(value, dict):
        value = value.get("repository")
    if not isinstance(value, str):
        return None
    if re.fullmatch(r"[\w.-]+/[\w.-]+", value):
        return "https://github.com/" + value
    return value if value.startswith("https://") else None


def _record(item, record, source_ref, expected_hash=None):
    item["repository"] = _repository(record)
    item["pin"] = record.get("ref") or record.get("source_pin") or record.get("pin")
    item["source_refs"] = [source_ref]
    if isinstance(record.get("url"), str):
        item["source_refs"].append(record["url"])
    for key in ("catalog", "layer_id", "component_id", "tree_sha"):
        if record.get(key) is not None:
            item[key] = record[key]
    if record.get("status") is not None:
        item["recorded_status"] = record["status"]
    immutable = bool(re.fullmatch(r"[0-9a-f]{40}", str(item["pin"] or record.get("tree_sha", ""))))
    if expected_hash and item["sha256"] is not None:
        item["hash_match"] = item["sha256"] == expected_hash
        item["provenance"] = "recorded hash matches" if item["hash_match"] else "recorded hash mismatch"
        if item["hash_match"] and item["repository"] and immutable:
            item["status"] = "SOURCE_MATCHED"
    elif expected_hash:
        item["hash_match"] = None
        item["provenance"] = "independently approved metadata only; expected content hash not checked"


def _timers():
    """Return only names and timing keys; never service commands or environment."""
    try:
        help_result = subprocess.run(["systemctl", "--help"], capture_output=True, text=True, timeout=5)
        if "list-timers" not in help_result.stdout or "--output=" not in help_result.stdout:
            return [], "UNREPORTED: timer JSON interface not advertised"
        result = subprocess.run(
            ["systemctl", "--user", "list-timers", "--all", "--output=json", "--no-pager"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode:
            return [], "UNREPORTED: timer JSON command failed"
        rows = json.loads(result.stdout)
        if not isinstance(rows, list):
            return [], "UNREPORTED: timer JSON shape unsupported"
        safe = []
        for row in rows[:MAX_ENTRIES]:
            name = row.get("unit") or row.get("timer")
            if not isinstance(name, str) or not re.fullmatch(r"[\w.@:-]+\.timer", name):
                continue
            safe.append({key: value for key, value in row.items() if key in {"unit", "timer", "next", "last", "left", "passed", "next_elapse", "last_trigger"}})
        return safe, "names and timing only; wiring unverified"
    except (OSError, ValueError, subprocess.TimeoutExpired, AttributeError):
        return [], "UNREPORTED: timer query unavailable"


def _repo_key(value):
    """Use the repository identity, including manifests with release/tree URLs."""
    if not isinstance(value, str):
        return None
    match = re.match(r"https://github\.com/([\w.-]+/[\w.-]+)(?:/|$)", value, re.I)
    if match:
        return "github.com/" + match[1].lower().removesuffix(".git")
    return value.lower().rstrip("/") if value.startswith("https://") else None


def _catalog_paths(root, snapshot):
    manifest = root / "catalogs/landscape/manifest.json"
    paths = []
    for catalog, relative in _json(snapshot(manifest, metadata=True)).get("catalogs", {}).items():
        if (isinstance(catalog, str) and re.fullmatch(r"[\w.-]+", catalog) and isinstance(relative, str)
                and relative.startswith("catalogs/landscape/") and ".." not in Path(relative).parts):
            paths.append((catalog, root / relative))
    return manifest, paths


def _layer_links(catalogs):
    components, repositories, keys = {}, {}, set()
    for catalog, path, document in catalogs:
        for index, layer in enumerate(document.get("layers", [])):
            if not isinstance(layer, dict) or not isinstance(layer.get("layer_id"), str):
                continue
            key = catalog + "/" + layer["layer_id"]
            keys.add(key)
            for collection in ("winners", "candidates"):
                for number, record in enumerate(layer.get(collection, [])):
                    if not isinstance(record, dict):
                        continue
                    source = str(path) + f"#/layers/{index}/{collection}/{number}"
                    component = record.get("component_id")
                    if isinstance(component, str):
                        components.setdefault(component, []).append((key, source, "canonical " + collection + ".component_id join"))
                    repository = _repo_key(_repository(record))
                    if repository:
                        repositories.setdefault(repository, []).append((key, source, "canonical " + collection + " repository identity join"))
    return components, repositories, keys


def _catalog_mapping(item, links):
    components, repositories, keys = links
    matches = list(components.get(item.get("component_id"), []))
    matches.extend(repositories.get(_repo_key(item.get("repository")), []))
    explicit = item.get("layer_id")
    if isinstance(explicit, str):
        for key in keys:
            if key == item.get("catalog", "") + "/" + explicit or (not item.get("catalog") and key.split("/", 1)[1] == explicit):
                matches.append((key, item["source_refs"][0], "explicit manifest layer_id"))
    if matches:
        item["layer_keys"] = sorted({match[0] for match in matches})
        item["mapping_source"] = "; ".join(dict.fromkeys(match[1] for match in matches))
        item["mapping_reason"] = "; ".join(dict.fromkeys(match[2] for match in matches))


def _projection_items(path, projection, digest):
    """Read only the CC's sanitized registration fields, without source lookup."""
    if projection.get("schema") != "automation-projection/1":
        return []
    items = []
    for kind, collection, fields in (
        ("hook", "hooks", ("client", "scope", "event", "matcher", "program", "timeout_s")),
        ("cron", "cron", ("schedule", "program")),
    ):
        rows = projection.get(collection, [])
        if not isinstance(rows, list) or len(rows) > MAX_ENTRIES:
            raise ValueError("automation projection entry limit or shape invalid")
        for index, row in enumerate(rows):
            if not isinstance(row, dict) or not isinstance(row.get("program"), str):
                continue
            if not re.fullmatch(r"[\w.@:+-]{1,120}", row["program"]):
                continue
            source = str(path) + f"#/{collection}/{index}"
            item = {"kind": kind, "name": row["program"], "path": source,
                    "sha256": digest, "repository": None, "pin": None,
                    "source_refs": [source], "status": "UNREPORTED",
                    "recorded_status": "registered", "local": True,
                    "provenance": "local sanitized registration; execution unverified"}
            for key in fields:
                value = row.get(key)
                if isinstance(value, str):
                    item[key] = value[:1024]
                elif key == "timeout_s" and (value is None or isinstance(value, (int, float))):
                    item[key] = value
            items.append(item)
    return items


def _explicit_mapping(item, mapping, known_keys, mapping_path):
    if mapping.get("schema") != "local-architecture-mapping/1":
        return
    for index, record in enumerate(mapping.get("mappings", [])):
        if not isinstance(record, dict):
            continue
        if item["kind"] not in record.get("kinds", []) or item["name"] not in record.get("names", []):
            continue
        if isinstance(record.get("unmapped_reason"), str):
            item["unmapped_reason"] = record["unmapped_reason"]
        targets = record.get("layer_keys", [])
        if not isinstance(targets, list) or not all(isinstance(key, str) for key in targets):
            item["unmapped_reason"] = "committed mapping has an invalid layer_keys list"
            continue
        unknown = sorted(set(targets) - known_keys)
        if unknown:
            item["unmapped_reason"] = "committed mapping names an unknown canonical layer: " + ", ".join(unknown)
            continue
        if targets and isinstance(record.get("reason"), str) and record["reason"].strip():
            item["layer_keys"] = sorted(set(item.get("layer_keys", [])) | set(targets))
            source = str(mapping_path) + f"#/mappings/{index}"
            item["mapping_source"] = "; ".join(filter(None, (item.get("mapping_source"), source)))
            item["mapping_reason"] = "; ".join(filter(None, (item.get("mapping_reason"), record["reason"])))
            item.setdefault("mapping_evidence_refs", []).extend(record.get("source_refs", []))


def _capture(root, state_root, skill_roots, reads):
    """Capture exact approved bytes once; aliases supply no content authority."""
    root = Path(root)
    state_root = Path(state_root)
    snapshots, captured, resolutions = {}, {}, {}
    def snapshot(path, metadata=False):
        path = Path(path).absolute()
        resolved = _safe_path(path, reads)
        if resolved is None or (not resolved.exists() and not resolved.is_symlink()):
            return None
        resolutions[str(path)] = resolved
        key = str(resolved)
        if key not in snapshots:
            remaining = MAX_HASH_BYTES - sum(source["bytes"] for source in captured.values())
            size = resolved.stat().st_size
            if size > remaining:
                raise ValueError("LARGE-READ actual inventory payload exceeds aggregate budget")
            bound = MAX_METADATA_BYTES if metadata else MAX_HASH_BYTES
            bound = min(bound, max(1, size), max(1, remaining))
            raw, receipt = _hash(resolved, reads=reads, max_bytes=bound)
            snapshots[key], captured[key] = raw, receipt
        return snapshots[key]
    skill_roots = [Path(path) for path in skill_roots] if skill_roots is not None else [
        root / ".claude/skills", USER_ROOT / ".claude/skills",
        USER_ROOT / ".agents/skills", USER_ROOT / ".codex/skills",
    ]
    groups = []
    unknown_entries = set()
    for directory in skill_roots:
        skills, unknown_skills = _skills(directory, reads)
        groups.extend(("skill", path) for path in skills)
        groups.extend(("skill-directory", path) for path in unknown_skills)
    for directory in (root / "adoption/agents", USER_ROOT / ".claude/agents", USER_ROOT / ".codex/agents"):
        suffixes = {".md", ".toml"}
        groups.extend(("role" if path.suffix == ".toml" else "agent", path) for path in _files(directory, 2, suffixes, reads=reads, unknown_entries=unknown_entries) if path.suffix in {".md", ".toml"} and path.name != "AGENTS.md")
    groups.extend(("agent-entry", path) for path in sorted(unknown_entries))
    groups.extend(("workflow", path) for path in _files(root / ".github/workflows", metadata_suffixes={".yml", ".yaml"}) if path.suffix in {".yml", ".yaml"})
    groups.extend(("script", path) for path in _files(root / "scripts", metadata_suffixes=SCRIPT_SUFFIXES) if path.suffix in SCRIPT_SUFFIXES)
    unit_root = USER_ROOT / ".config/systemd/user"
    groups.extend(("timer" if path.suffix == ".timer" else "unit", path) for path in _files(unit_root, metadata_suffixes={".timer", ".service", ".path"}) if path.suffix in {".timer", ".service", ".path"})
    metadata_paths = [root / "adoption/skills/manifest.json", root / "adoption/manifest.json", root / "manifests/stack.json"]
    metadata_paths += [path for path in _files(root / "adoption/agents", 2, reads=reads) if path.name.endswith("manifest.json") or path.name == "SHA256SUMS"]
    catalog_manifest, catalog_paths = _catalog_paths(root, snapshot)
    metadata_paths += [catalog_manifest] + [path for _, path in catalog_paths]
    projection_path = state_root / "coordination/command-center/pages/automation-projection.json"
    mapping_path = root / "tools/local-pages/architecture_mapping.json" if MAPPING_PATH == Path(__file__).with_name("architecture_mapping.json") else MAPPING_PATH
    metadata_paths += [projection_path, mapping_path]
    candidates = {}
    input_paths, input_types, symlink_paths = {}, {}, {}
    metadata_only, unknown = {}, {}
    for kind, path in groups + [("metadata", path) for path in metadata_paths]:
        path = path.absolute()
        user_metadata = kind in {"agent", "role", "timer", "unit"} and not _inside(path, root.absolute())
        role = "architecture_inventory_metadata" if user_metadata else "architecture_inventory"
        if kind in {"skill-directory", "agent-entry"} or _approved_target(path, reads, role) is None:
            unknown[str(path)] = {
                "path": str(path), "resolved_path": None, "input_paths": [str(path)],
                "sha256": None, "sha256_kind": "unreported", "bytes": None,
                "mtime_ns": None, "type": kind, "types": [kind], "status": "UNAPPROVED",
                "reason": "No independent exact inventory grant; name only; metadata and content unread",
            }
            if kind == "skill-directory":
                unknown[str(path)]["reason"] = "Unapproved skill entry; name only; asset presence unmeasured"
            continue
        resolved = _safe_path(path, reads, role)
        if not user_metadata and not resolved.exists() and not resolved.is_symlink():
            continue
        resolutions[str(path)] = resolved
        info = None
        if user_metadata:
            # Reuse native no-follow traversal for metadata too. An approved
            # canonical path cannot stat a replacement symlink's target.
            with _policy()._directory(resolved.parent) as directory:
                info = os.stat(resolved.name, dir_fd=directory, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                raise _policy().SourcePolicyError("inventory metadata target is not a regular file")
        if user_metadata or resolved.is_file():
            key = str(resolved)
            if user_metadata:
                metadata_only[key] = {"path": key, "bytes": info.st_size, "mtime_ns": info.st_mtime_ns,
                                      "sha256": None, "sha256_kind": "unreported",
                                      "status": "independently approved metadata only; body unread"}
            else:
                candidates[key] = resolved
            input_paths.setdefault(key, set()).add(str(path))
            input_types.setdefault(key, set()).add(kind)
            if resolved != path.absolute():
                symlink_paths.setdefault(key, set()).add(str(path))
    input_bytes = {key: path.stat().st_size for key, path in candidates.items()}
    total_bytes = sum(input_bytes.values())
    if total_bytes > MAX_HASH_BYTES:
        raise ValueError("LARGE-READ bytes=" + str(total_bytes) + "; notify coordinator before hashing")
    for key, path in candidates.items():
        snapshot(path, metadata="metadata" in input_types[key] or "workflow" in input_types[key])
    hashes = {key: receipt["sha256"] for key, receipt in captured.items()}
    input_bytes = {key: receipt["bytes"] for key, receipt in captured.items()}
    total_bytes = sum(input_bytes.values())
    if total_bytes > MAX_HASH_BYTES:
        raise ValueError("LARGE-READ captured inventory payload exceeds aggregate budget")
    sources = [{
        "path": key, "resolved_path": key, "input_paths": sorted(input_paths[key]),
        "symlink_paths": sorted(symlink_paths.get(key, set())),
        "sha256": hashes[key], "sha256_kind": "computed", "bytes": input_bytes[key],
        "role": "architecture_inventory",
        "type": "metadata" if "metadata" in input_types[key] else "/".join(sorted(input_types[key])),
        "types": sorted(input_types[key]),
        "status": "recorded metadata" if "metadata" in input_types[key] else "hashed inventory input; runtime and wiring unverified",
    } for key in sorted(candidates)]
    for key, record in sorted(metadata_only.items()):
        sources.append({**record, "resolved_path": key, "input_paths": sorted(input_paths[key]),
                        "role": "architecture_inventory_metadata",
                        "symlink_paths": sorted(symlink_paths.get(key, set())),
                        "type": "/".join(sorted(input_types[key])), "types": sorted(input_types[key])})
    sources.extend(unknown[key] for key in sorted(unknown))
    return groups, metadata_paths, catalog_paths, snapshots, hashes, sources, total_bytes, resolutions, unknown


def input_signature(root, state_root, *, reads):
    _, _, _, _, _, sources, _, _, _ = _capture(root, state_root, None, reads)
    return sources


def build(root, state_root, skill_roots=None, *, reads=None):
    """Use exact independent inventory grants before hashing or metadata parsing."""
    root, state_root = Path(root), Path(state_root)
    reads = reads or _policy().ArchitectureReads(root, state_root, user_root=USER_ROOT)
    groups, metadata_paths, catalog_paths, snapshots, hashes, sources, total_bytes, resolutions, unknown = _capture(root, state_root, skill_roots, reads)
    projection_path = metadata_paths[-2]
    def data(path):
        return _json(snapshots.get(str(resolutions.get(str(path.absolute())))))
    def captured_key(path):
        return str(resolutions.get(str(path.absolute())))
    def content(path):
        return snapshots.get(str(resolutions.get(str(path.absolute()))), b"").decode("utf-8")
    skill_manifest, adoption, stack = [
        data(path)
        for path in metadata_paths[:3]
    ]
    links = _layer_links([(catalog, path, data(path)) for catalog, path in catalog_paths])
    projection_digest = hashes.get(captured_key(projection_path))
    projection = data(projection_path) if projection_digest else {}
    projection_present = projection.get("schema") == "automation-projection/1"
    mapping = data(metadata_paths[-1])
    for source in sources:
        if source["path"] == captured_key(metadata_paths[1]):
            source["reference_paths"] = [
                {"key": key, "path": value}
                for key, value in adoption.get("sources", {}).items()
                if isinstance(value, str)
            ]
            source["sdk_reference_paths"] = [
                {"key": key, "path": value}
                for key, value in adoption.get("toolchain", {}).items()
                if key in {"sdk_lock", "sdk_direct_requirements", "sdk_accepted_constraints"} and isinstance(value, str)
            ]
    skills = {record["name"]: record for record in skill_manifest.get("skills", []) if isinstance(record, dict) and isinstance(record.get("name"), str)}
    role_records = {}
    checksums = {}
    for path in metadata_paths[3:]:
        if path.name == "SHA256SUMS" and captured_key(path) in hashes:
            for line in content(path).splitlines():
                match = re.fullmatch(r"([0-9a-f]{64})\s+\*?([^/\\]+)", line)
                if match:
                    checksums.setdefault(match[2], []).append((match[1], str(path)))
        elif path.suffix == ".json" and captured_key(path) in hashes:
            document = data(path)
            for record in document.get("agents", []) + document.get("roles", []):
                if isinstance(record, dict) and record.get("name"):
                    role_records[record["name"]] = (record, str(path))
    items = []
    for kind, path in sorted(set(groups), key=lambda group: (group[0], str(group[1]))):
        if str(path.absolute()) in unknown:
            source = unknown[str(path.absolute())]
            items.append({**source, "kind": kind, "name": path.parent.name if kind == "skill" else path.name if kind == "skill-directory" else path.stem,
                          "repository": None, "pin": None, "source_refs": [],
                          "unmapped_reason": source["reason"]})
            continue
        resolved = resolutions.get(str(path.absolute()))
        digest = hashes.get(str(resolved)) if resolved else None
        item = {"kind": kind, "name": path.parent.name if kind == "skill" else path.stem, "path": str(path), "sha256": digest, "repository": None, "pin": None, "source_refs": [], "status": "UNREPORTED"}
        if resolved and resolved != path.absolute():
            item["resolved_path"] = str(resolved)
        if not resolved:
            item["provenance"] = "target outside approved roots or excluded"
        elif digest is None:
            item["provenance"] = "independently approved metadata only; body unread and content hash UNREPORTED"
        if kind == "skill" and item["name"] in skills:
            record = skills[item["name"]]
            _record(item, record, str(metadata_paths[0]) + "#skills/" + item["name"], record.get("skill_md_sha256"))
        elif kind in {"agent", "role"}:
            if item["name"] in role_records:
                record, source_ref = role_records[item["name"]]
                _record(item, record, source_ref, record.get("sha256"))
            elif path.name in checksums:
                records = checksums[path.name]
                item["source_refs"] = [source_ref for _, source_ref in records]
                item["hash_match"] = any(expected == digest for expected, _ in records) if digest is not None else None
                item["provenance"] = ("recorded hash matches; source pin unreported" if item["hash_match"] else "recorded hash mismatch") if digest is not None else "independently approved metadata only; expected content hash not checked"
        elif kind == "workflow" and resolved:
            item["action_refs"] = []
            if len(snapshots[str(resolved)]) <= MAX_METADATA_BYTES:
                for line in content(path).splitlines():
                    match = re.search(r"\buses:\s*['\"]?([\w.-]+/[\w./-]+)@([0-9a-f]{40})(?:['\"]|\s|$)", line)
                    if match:
                        item["action_refs"].append({"repository": "https://github.com/" + "/".join(match[1].split("/")[:2]), "pin": match[2]})
            item["source_refs"] = [str(path) + "#uses"]
        items.append(item)
    for component in stack.get("components", []):
        if not isinstance(component, dict) or not component.get("id"):
            continue
        item = {"kind": "component", "name": component["id"], "component_id": component["id"], "path": str(metadata_paths[2]), "sha256": hashes.get(captured_key(metadata_paths[2])), "repository": None, "pin": None, "source_refs": [], "status": "UNREPORTED"}
        _record(item, component, str(metadata_paths[2]) + "#components/" + str(component["id"]))
        recipe = adoption.get("recipe_map", {}).get(component["id"])
        if isinstance(recipe, str):
            item["source_refs"].append(str(root / recipe))
        item["recorded_version"] = component.get("version")
        item["provenance"] = "manifest reference; installed runtime and wiring unverified"
        items.append(item)
    items.extend(_projection_items(projection_path, projection, projection_digest))
    grouped = {str(path.absolute()) for _, path in groups}
    for key, source in unknown.items():
        if key not in grouped:
            items.append({**source, "kind": "metadata", "name": Path(key).name,
                          "repository": None, "pin": None, "source_refs": [],
                          "unmapped_reason": source["reason"]})
    if projection_present:
        source = next(source for source in sources if source["path"] == captured_key(projection_path))
        source.update({"status": "local sanitized automation projection", "local": True,
                       "generated_utc": projection.get("generated_utc"), "method": projection.get("method")})
    for item in items:
        if item.get("status") == "UNAPPROVED":
            continue
        _catalog_mapping(item, links)
        _explicit_mapping(item, mapping, links[2], metadata_paths[-1])
        for action in item.get("action_refs", []):
            identity = _repo_key(action.get("repository"))
            if not identity:
                continue
            projected = {"kind": "action", "name": identity.removeprefix("github.com/"),
                         "repository": action["repository"], "source_refs": item["source_refs"]}
            _catalog_mapping(projected, links)
            _explicit_mapping(projected, mapping, links[2], metadata_paths[-1])
            for key in ("layer_keys", "mapping_source", "mapping_reason"):
                if projected.get(key):
                    action[key] = projected[key]
        if not item.get("layer_keys") and not item.get("layer_id"):
            item.setdefault("unmapped_reason", "no canonical component ID or repository join, and no committed mapping for " + item["kind"] + ":" + item["name"])
    timer_rows, timer_status = _timers()
    coverage = {
        "hash_bytes": total_bytes,
        "canonical_skill_records": len(skills),
        "unmapped": [{"kind": item["kind"], "name": item["name"], "path": item["path"], "reason": item["unmapped_reason"]} for item in items if not item.get("layer_keys") and not item.get("layer_id")],
        "excluded_skills": [{"skills": entry.get("skills"), "repository": _repository(entry), "source_ref": str(metadata_paths[0]) + "#excluded"} for entry in skill_manifest.get("excluded", []) if isinstance(entry, dict)],
        "timer_rows": timer_rows, "timer_status": timer_status,
        "cron_status": ("local sanitized projection: " + str(len(projection.get("cron", []))) + " registrations; execution unverified") if projection_present else "UNREPORTED: sanitized projection absent or unsupported; installed crontab unread",
        "client_hook_wiring": ("local sanitized projection: " + str(len(projection.get("hooks", []))) + " registrations; execution unverified") if projection_present else "UNREPORTED: sanitized projection absent or unsupported; hook sources and client settings unread",
        "projected_hook_registrations": len(projection.get("hooks", [])) if projection_present else None,
        "projected_cron_registrations": len(projection.get("cron", [])) if projection_present else None,
        "projection_limits": projection.get("limits", []) if projection_present else [],
        "automation_limits": projection.get("limits", []) if projection_present else [],
        "state_root": str(state_root),
        "acceptance": "file inventory does not establish installation, wiring or fresh-session acceptance",
    }
    return {"items": items, "sources": sources, "coverage": coverage}
