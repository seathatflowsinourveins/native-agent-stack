#!/usr/bin/env python3
"""Read-only adoption prerequisite report. No installation or runtime acceptance.

Checks command presence with shutil.which; it never invokes those commands. The
only subprocess is a bounded native Git revision query. No credentials, client
configuration, service/process state, network endpoints, or model APIs are read.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit


SHA = re.compile(r"[0-9a-f]{40}\Z")
NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*\Z")
LIMITATIONS = [
    "Executable presence does not verify its version, installation integrity, activation, or E2E behavior.",
    "Historical acceptance remains historical; no provider, service, GPU, hook, or broker acceptance runs here.",
    "Git comparison reports source identity only; changed worktree files are not inspected.",
    "No credentials, client configuration, environment values, network endpoints, or running processes are inspected.",
]


class InvalidManifest(ValueError):
    """Invalid or unsafe adoption manifest; messages contain no host paths."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidManifest(message)


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def names(value, field: str) -> list[str]:
    require(isinstance(value, list), f"{field} must be an array")
    require(all(isinstance(item, str) and NAME.fullmatch(item) for item in value),
            f"{field} must contain plain identifiers, not paths or command arguments")
    require(len(value) == len(set(value)), f"{field} contains duplicate identifiers")
    return value


def recipe_path(root: Path, value) -> Path:
    require(isinstance(value, str) and bool(value), "recipe reference must be nonempty text")
    relative = PurePosixPath(value)
    require(bool(relative.parts) and not relative.is_absolute() and str(relative) == value
            and all(part not in {".", ".."} for part in relative.parts)
            and not any(ord(char) < 32 or char in "\\:?#" for char in value),
            "recipe path must be canonical, relative, and confined to the repository")
    path = root
    for part in relative.parts:
        path /= part
        require(not path.is_symlink(), "recipe symlinks are forbidden")
    require(path.resolve().is_relative_to(root), "recipe path escapes the repository")
    return path


def validate_manifest(data, root: Path) -> dict:
    require(isinstance(data, dict), "manifest must be an object")
    require(type(data.get("schema_version")) is int and data["schema_version"] == 1,
            "schema_version must be 1")
    supported = data.get("supported_platforms")
    require(isinstance(supported, list) and bool(supported), "supported_platforms must be a nonempty array")
    for item in supported:
        require(isinstance(item, dict), "platform entry must be an object")
        require(all(isinstance(item.get(key), str) and NAME.fullmatch(item[key])
                    for key in ("os", "architecture")), "platform identifiers are invalid")
        require(isinstance(item.get("python"), str) and re.fullmatch(r"[0-9]+\.[0-9]+", item["python"]),
                "platform python must be a major.minor version")
    source = data.get("source")
    require(isinstance(source, dict), "source must be an object")
    require(isinstance(source.get("baseline_commit"), str) and SHA.fullmatch(source["baseline_commit"]),
            "source baseline_commit must be a full commit SHA")
    url = source.get("repository")
    require(isinstance(url, str), "source repository must be an HTTPS URL without credentials")
    try:
        parsed = urlsplit(url)
        valid_url = (parsed.scheme == "https" and bool(parsed.hostname)
                     and parsed.username is None and parsed.password is None
                     and not parsed.query and not parsed.fragment
                     and not any(char.isspace() for char in url) and "\\" not in url)
        parsed.port
    except ValueError:
        valid_url = False
    require(valid_url, "source repository must be an HTTPS URL without credentials")
    profiles = data.get("profiles")
    require(isinstance(profiles, list) and bool(profiles), "profiles must be a nonempty array")
    ids = set()
    for profile in profiles:
        require(isinstance(profile, dict), "profile must be an object")
        identifier = profile.get("id")
        require(isinstance(identifier, str) and NAME.fullmatch(identifier), "profile id is invalid")
        require(identifier not in ids, "profile ids must be unique")
        ids.add(identifier)
        label = profile.get("label")
        require(isinstance(label, str) and bool(label.strip()) and len(label) <= 160
                and not any(ord(char) < 32 for char in label), "profile label is invalid")
        names(profile.get("required_commands"), "required_commands")
        components = profile.get("component_ids")
        require(isinstance(components, list)
                and all(isinstance(item, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*", item)
                        for item in components), "component_ids must contain component identifiers")
        require(len(components) == len(set(components)), "component_ids contains duplicate identifiers")
        references = profile.get("recipe_paths")
        require(isinstance(references, list), "recipe_paths must be an array")
        for reference in references:
            recipe_path(root, reference)
        require(len(references) == len(set(references)), "recipe_paths contains duplicate references")
    require(isinstance(data.get("default_profile"), str) and data["default_profile"] in ids,
            "default_profile must identify a profile")
    return data


def git_revision(root: Path) -> str | None:
    """Return only a native Git SHA from this root; suppress arbitrary Git errors."""
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), "rev-parse", "--show-toplevel", "HEAD"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5,
            check=False,
        )
        lines = result.stdout.splitlines()
        if result.returncode == 0 and len(lines) == 2 and Path(lines[0]).resolve() == root and SHA.fullmatch(lines[1]):
            return lines[1]
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
        pass
    return None


def inspect_adoption(manifest: Path, root: Path | None = None, profiles: list[str] | None = None) -> dict:
    manifest = manifest.absolute()
    root = (root or manifest.parent.parent).resolve()
    host = {"os": platform.system().lower(), "architecture": platform.machine().lower(),
            "python": ".".join(str(part) for part in sys.version_info[:3]), "supported": False}
    result = {"schema_version": 1, "status": "prerequisites_missing", "platform": host,
              "manifest": {"status": "invalid"}, "profiles": [], "errors": [],
              "runtime_acceptance_verified": False, "limitations": LIMITATIONS.copy()}
    try:
        require(manifest.resolve().is_relative_to(root), "manifest must be inside the repository root")
        require(manifest.is_file(), "manifest must be a regular file")
        require(manifest.stat().st_size <= 1_048_576, "manifest exceeds the one MiB size limit")
        data = validate_manifest(json.loads(manifest.read_text(encoding="utf-8"), object_pairs_hook=unique_json), root)
        selected = list(dict.fromkeys(profiles or [data["default_profile"]]))
        by_id = {profile["id"]: profile for profile in data["profiles"]}
        require(all(identifier in by_id for identifier in selected), "unknown profile requested")
    except (OSError, UnicodeError, json.JSONDecodeError):
        result["errors"].append("manifest is unavailable or not valid UTF-8 JSON")
        return result
    except (InvalidManifest, ValueError, RecursionError) as error:
        result["errors"].append(str(error) if isinstance(error, InvalidManifest) else "invalid manifest structure")
        return result
    result["manifest"] = {"status": "valid", "schema_version": data["schema_version"]}
    host["supported"] = any(item["os"] == host["os"] and item["architecture"] == host["architecture"]
                            and item["python"] == ".".join(str(part) for part in sys.version_info[:2])
                            for item in data["supported_platforms"])
    for identifier in selected:
        profile = by_id[identifier]
        commands = [{"name": name, "present": shutil.which(name) is not None}
                    for name in profile["required_commands"]]
        recipes = [{"path": reference, "present": recipe_path(root, reference).is_file()}
                   for reference in profile["recipe_paths"]]
        ready = all(item["present"] for item in commands + recipes)
        result["profiles"].append({"id": identifier, "commands": commands, "recipes": recipes,
            "status": "prerequisites_present" if ready else "prerequisites_missing"})
    revision = git_revision(root)
    baseline = data["source"]["baseline_commit"]
    result["git"] = {"baseline_commit": baseline, "current_commit": revision,
                     "comparison": "unavailable" if revision is None else
                     "baseline_matches" if revision == baseline else "baseline_differs"}
    if host["supported"] and all(profile["status"] == "prerequisites_present" for profile in result["profiles"]):
        result["status"] = "prerequisites_present"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("adoption/manifest.json"))
    parser.add_argument("--repo-root", type=Path, help="Defaults to the manifest's grandparent directory")
    parser.add_argument("--profile", action="append", help="Profile ID; repeat to check multiple profiles")
    parser.add_argument("--json", action="store_true", help="Emit the bounded report as JSON")
    args = parser.parse_args(argv)
    report = inspect_adoption(args.manifest, args.repo_root, args.profile)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report["status"])
        print(f"Manifest: {report['manifest']['status']}; platform supported: {report['platform']['supported']}")
        for profile in report["profiles"]:
            missing = [item["name"] for item in profile["commands"] if not item["present"]]
            missing += [item["path"] for item in profile["recipes"] if not item["present"]]
            print(f"{profile['id']}: {profile['status']}" + (f" (missing: {', '.join(missing)})" if missing else ""))
        for error in report["errors"]:
            print(f"Error: {error}")
        for limitation in report["limitations"]:
            print(limitation)
    return 0 if report["status"] == "prerequisites_present" else 2


if __name__ == "__main__":
    raise SystemExit(main())
