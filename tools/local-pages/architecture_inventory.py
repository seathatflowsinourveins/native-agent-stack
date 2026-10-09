"""Bounded filename/hash inventory; no settings, credentials or instruction bodies.

Provenance comes from recorded manifests and hash lists. File presence or a
matching hash does not establish client wiring or a fresh-session acceptance.
"""

import hashlib
import json
import re
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


def _blocked(path):
    return any(part in SKIP_DIRS for part in path.parts) or (
        path.name.lower() in BLOCKED_NAMES or path.name.startswith(".env.")
        or (path.suffix.lower() in {".json", ".toml", ".yaml", ".yml"} and any(word in path.name.lower() for word in ("credential", "secret", "auth")))
    )


def _inside(path, root):
    return path == root or root in path.parents


def _safe_path(path, approved):
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError):
        return None
    if _blocked(path) or _blocked(resolved):
        return None
    if path.name == "SKILL.md" and resolved.name != "SKILL.md":
        return None
    if any(_inside(resolved, root.absolute()) for root in approved):
        return resolved
    # Follow only an explicitly named SKILL target in an installed bundle.
    bundle = USER_ROOT / ".codex/plugins/cache"
    if resolved.name == "SKILL.md" and _inside(resolved, bundle) and "skills" in resolved.relative_to(bundle).parts:
        return resolved
    return None


def _files(root, depth=0):
    if not root.is_dir() or root.is_symlink():
        return []
    entries = sorted(root.iterdir(), key=lambda path: path.name)
    if len(entries) > MAX_ENTRIES:
        raise ValueError("inventory directory entry limit exceeded")
    found = []
    for path in entries:
        if _blocked(path):
            continue
        if path.is_dir() and not path.is_symlink() and depth:
            found.extend(_files(path, depth - 1))
        elif path.is_file() or path.is_symlink():
            found.append(path)
    return found


def _skills(root):
    if not root.is_dir():
        return []
    entries = sorted(root.iterdir(), key=lambda path: path.name)
    if len(entries) > MAX_ENTRIES:
        raise ValueError("skill directory entry limit exceeded")
    found = []
    for path in entries:
        if _blocked(path):
            continue
        candidate = path / "SKILL.md"
        if candidate.is_file():
            found.append(candidate)
        elif path.is_dir() and not path.is_symlink():
            children = sorted(path.iterdir(), key=lambda child: child.name)
            if len(children) > MAX_ENTRIES:
                raise ValueError("nested skill directory entry limit exceeded")
            found.extend(child / "SKILL.md" for child in children if not _blocked(child) and (child / "SKILL.md").is_file())
    return found


def _hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path):
    if not path.is_file() or _blocked(path):
        return {}
    if path.stat().st_size > MAX_METADATA_BYTES:
        raise ValueError("metadata size limit exceeded")
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
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
    for key in ("layer_id", "component_id", "tree_sha"):
        if record.get(key) is not None:
            item[key] = record[key]
    if record.get("status") is not None:
        item["recorded_status"] = record["status"]
    immutable = bool(re.fullmatch(r"[0-9a-f]{40}", str(item["pin"] or record.get("tree_sha", ""))))
    if expected_hash:
        item["hash_match"] = item["sha256"] == expected_hash
        item["provenance"] = "recorded hash matches" if item["hash_match"] else "recorded hash mismatch"
        if item["hash_match"] and item["repository"] and immutable:
            item["status"] = "SOURCE_MATCHED"


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


def build(root, state_root, skill_roots=None):
    """Inventory approved paths and canonical metadata without guessing layers."""
    root = Path(root)
    state_root = Path(state_root)
    skill_roots = [Path(path) for path in skill_roots] if skill_roots is not None else [
        root / ".claude/skills", USER_ROOT / ".claude/skills",
        USER_ROOT / ".agents/skills", USER_ROOT / ".codex/skills",
    ]
    groups = [("skill", path) for directory in skill_roots for path in _skills(directory)]
    for directory in (root / "adoption/agents", USER_ROOT / ".claude/agents", USER_ROOT / ".codex/agents"):
        groups.extend(("role" if path.suffix == ".toml" else "agent", path) for path in _files(directory, 2) if path.suffix in {".md", ".toml"} and path.name != "AGENTS.md")
    hook_roots = [root / "hooks", root / "scripts/hooks", root / "scripts/git-hooks", root / "adoption/hooks", USER_ROOT / ".claude/hooks"]
    for directory in hook_roots:
        groups.extend(("hook", path) for path in _files(directory, 2) if path.suffix in SCRIPT_SUFFIXES or not path.suffix)
    groups.extend(("workflow", path) for path in _files(root / ".github/workflows") if path.suffix in {".yml", ".yaml"})
    groups.extend(("script", path) for path in _files(root / "scripts") if path.suffix in SCRIPT_SUFFIXES)
    unit_root = USER_ROOT / ".config/systemd/user"
    groups.extend(("timer" if path.suffix == ".timer" else "unit", path) for path in _files(unit_root) if path.suffix in {".timer", ".service", ".path"})
    metadata_paths = [root / "adoption/skills/manifest.json", root / "adoption/manifest.json", root / "manifests/stack.json"]
    metadata_paths += [path for path in _files(root / "adoption/agents", 2) if path.name.endswith("manifest.json") or path.name == "SHA256SUMS"]
    approved = [root / ".claude/skills", root / "adoption/agents", root / ".github/workflows", root / "scripts", root / "adoption/hooks", root / "hooks", root / "adoption/skills", root / "manifests", root / "adoption/manifest.json", unit_root, USER_ROOT / ".claude/agents", USER_ROOT / ".codex/agents", USER_ROOT / ".claude/hooks"] + skill_roots
    candidates = {}
    for path in [path for _, path in groups] + metadata_paths:
        resolved = _safe_path(path, approved)
        if resolved is not None and resolved.is_file():
            candidates[str(resolved)] = resolved
    total_bytes = sum(path.stat().st_size for path in candidates.values())
    if total_bytes > MAX_HASH_BYTES:
        raise ValueError("LARGE-READ bytes=" + str(total_bytes) + "; notify coordinator before hashing")
    hashes = {key: _hash(path) for key, path in candidates.items()}
    sources = [{"path": str(path), "sha256": hashes.get(str(path.resolve())), "status": "recorded metadata"} for path in metadata_paths if str(path.resolve()) in hashes]
    skill_manifest, adoption, stack = [
        _json(path) if str(path.resolve()) in hashes else {}
        for path in metadata_paths[:3]
    ]
    for source in sources:
        if source["path"] == str(metadata_paths[1]):
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
        if path.name == "SHA256SUMS" and str(path.resolve()) in hashes:
            if path.stat().st_size > MAX_METADATA_BYTES:
                continue
            for line in path.read_text().splitlines():
                match = re.fullmatch(r"([0-9a-f]{64})\s+\*?([^/\\]+)", line)
                if match:
                    checksums.setdefault(match[2], []).append((match[1], str(path)))
        elif path.suffix == ".json" and str(path.resolve()) in hashes:
            data = _json(path)
            for record in data.get("agents", []) + data.get("roles", []):
                if isinstance(record, dict) and record.get("name"):
                    role_records[record["name"]] = (record, str(path))
    items = []
    for kind, path in sorted(set(groups), key=lambda group: (group[0], str(group[1]))):
        resolved = _safe_path(path, approved)
        digest = hashes.get(str(resolved)) if resolved else None
        item = {"kind": kind, "name": path.parent.name if kind == "skill" else path.stem, "path": str(path), "sha256": digest, "repository": None, "pin": None, "source_refs": [], "status": "UNREPORTED"}
        if resolved and resolved != path.absolute():
            item["resolved_path"] = str(resolved)
        if not resolved:
            item["provenance"] = "target outside approved roots or excluded"
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
                item["hash_match"] = any(expected == digest for expected, _ in records)
                item["provenance"] = "recorded hash matches; source pin unreported" if item["hash_match"] else "recorded hash mismatch"
        elif kind == "workflow" and resolved:
            item["action_refs"] = []
            if path.stat().st_size <= MAX_METADATA_BYTES:
                for line in path.read_text().splitlines():
                    match = re.search(r"\buses:\s*['\"]?([\w.-]+/[\w./-]+)@([0-9a-f]{40})(?:['\"]|\s|$)", line)
                    if match:
                        item["action_refs"].append({"repository": "https://github.com/" + "/".join(match[1].split("/")[:2]), "pin": match[2]})
            item["source_refs"] = [str(path) + "#uses"]
        items.append(item)
    for component in stack.get("components", []):
        if not isinstance(component, dict) or not component.get("id"):
            continue
        item = {"kind": "component", "name": component["id"], "component_id": component["id"], "path": str(metadata_paths[2]), "sha256": hashes.get(str(metadata_paths[2].resolve())), "repository": None, "pin": None, "source_refs": [], "status": "UNREPORTED"}
        _record(item, component, str(metadata_paths[2]) + "#components/" + str(component["id"]))
        recipe = adoption.get("recipe_map", {}).get(component["id"])
        if isinstance(recipe, str):
            item["source_refs"].append(str(root / recipe))
        item["recorded_version"] = component.get("version")
        item["provenance"] = "manifest reference; installed runtime and wiring unverified"
        items.append(item)
    timer_rows, timer_status = _timers()
    coverage = {
        "hash_bytes": total_bytes,
        "canonical_skill_records": len(skills),
        "unmapped": [{"kind": item["kind"], "name": item["name"], "path": item["path"], "reason": "no explicit layer_id"} for item in items if not item.get("layer_id")],
        "excluded_skills": [{"skills": entry.get("skills"), "repository": _repository(entry), "source_ref": str(metadata_paths[0]) + "#excluded"} for entry in skill_manifest.get("excluded", []) if isinstance(entry, dict)],
        "timer_rows": timer_rows, "timer_status": timer_status,
        "cron_status": "UNREPORTED: installed crontab intentionally unread",
        "client_hook_wiring": "UNREPORTED: credential-bearing client configuration intentionally unread",
        "state_root": str(state_root),
        "acceptance": "file inventory does not establish installation, wiring or fresh-session acceptance",
    }
    return {"items": items, "sources": sources, "coverage": coverage}
