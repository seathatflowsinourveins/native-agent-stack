"""Derive exact Architecture grants from pinned Git metadata, never input bodies.

Reference: native source_policy.ArchitectureReads at
ddb7a2a9419dac5047bb73df85b30c95bc0c98b8; installed Git ls-tree/show and
CPython3.13.16 cbc944f4bc59639a444dd971c737788ba2283a91 ast/json/pathlib.
This prints a proposal for review. It does not modify policy or discover a
runtime file into permission. User grants require a separate reviewed snapshot.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_SUFFIXES = {".py", ".sh", ".js", ".mjs", ".cjs", ".ts"}
FROZEN_RULE = "tests/test_frozen_macos_variant_no_use.py"


def receipt_paths(metadata: dict, frozen_prefixes: tuple[str, ...], protected) -> list[str]:
    """Use registered path metadata, excluding protected and frozen eligibility."""
    selected = set()
    for collection in ("files", "receipts"):
        rows = metadata.get(collection, [])
        if not isinstance(rows, list):
            raise ValueError("registered file metadata must be a list")
        for row in rows:
            relative = row.get("path") if isinstance(row, dict) else None
            if not isinstance(relative, str) or not relative.endswith(".json"):
                continue
            path = PurePosixPath(relative)
            if path.is_absolute() or ".." in path.parts or "\\" in relative or protected(relative):
                continue
            if any(path == PurePosixPath(prefix) or PurePosixPath(prefix) in path.parents for prefix in frozen_prefixes):
                continue
            selected.add(relative)
    return sorted(selected)


def inventory_paths(tracked: list[str], catalogs: dict) -> list[str]:
    """Only the reviewed selector's pinned paths become a proposed exact grant."""
    selected = {"adoption/skills/manifest.json", "adoption/manifest.json", "manifests/stack.json",
                "catalogs/landscape/manifest.json", "tools/local-pages/architecture_mapping.json"}
    for value in catalogs.values():
        if not isinstance(value, str) or not value.startswith("catalogs/landscape/") or ".." in PurePosixPath(value).parts or not value.endswith(".json"):
            raise ValueError("canonical catalog metadata path is not confined")
        selected.add(value)
    for relative in tracked:
        path = PurePosixPath(relative)
        if path.parent == PurePosixPath("scripts") and path.suffix in SCRIPT_SUFFIXES:
            selected.add(relative)
        elif path.parent == PurePosixPath(".github/workflows") and path.suffix in {".yml", ".yaml"}:
            selected.add(relative)
        elif relative.startswith("adoption/agents/") and len(path.parts) <= 5:
            if path.suffix in {".md", ".toml"} and path.name != "AGENTS.md" or path.name.endswith("manifest.json") or path.name == "SHA256SUMS":
                selected.add(relative)
        elif relative.startswith(".claude/skills/") and path.name == "SKILL.md":
            selected.add(relative)
    return sorted(selected)


def user_inventory_grants(snapshot: dict) -> dict:
    """Reproduce reviewed user grants from names-only observations and bindings.

    An extra discovered name is not a new binding or content permission.
    Binding targets are independently reviewed in the retained data file; no
    resolver, stat or content open is used by this derivation.
    """
    if snapshot.get("schema") != "architecture-user-names/1":
        raise ValueError("reviewed user inventory requires a names-only snapshot")
    observed = set()
    for row in snapshot.get("directories", []):
        directory = row.get("path") if isinstance(row, dict) else None
        if not isinstance(directory, str) or PurePosixPath(directory).is_absolute() or ".." in PurePosixPath(directory).parts:
            raise ValueError("user observation directory is not relative")
        for name in row.get("names", []):
            if not isinstance(name, str) or name in {".", ".."} or "/" in name or "\\" in name:
                raise ValueError("user observation name is not a leaf")
            observed.add(str(PurePosixPath(directory) / name))
    roles = {"architecture_inventory": set(), "architecture_inventory_metadata": set(), "architecture_design": set()}
    aliases = []
    for row in snapshot.get("reviewed_bindings", []):
        if not isinstance(row, dict) or row.get("role") not in roles:
            raise ValueError("user binding requires a reviewed role")
        source, target = row.get("source"), row.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            raise ValueError("user binding requires exact relative paths")
        for relative in (source, target):
            p = PurePosixPath(relative)
            if p.is_absolute() or ".." in p.parts or "\\" in relative:
                raise ValueError("user binding escapes its root")
        role = row["role"]
        source_key = str(PurePosixPath(source).parent) if role != "architecture_inventory_metadata" else source
        if source_key not in observed:
            continue
        if role != "architecture_inventory_metadata" and PurePosixPath(target).name != "SKILL.md":
            raise ValueError("user content binding must name an exact skill asset")
        roles[role].add(target)
        if source != target:
            aliases.append({"root": "user", "path": source, "target_root": "user", "target_path": target})
    return {**{role: [{"root": "user", "path": path} for path in sorted(paths)] for role, paths in roles.items()},
            "architecture_inventory_aliases": sorted(aliases, key=lambda row: (row["path"], row["target_path"]))}


def proposal(root: Path, pin: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{40}", pin):
        raise ValueError("grant derivation requires a full Git source SHA")
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True).stdout
    policy_spec = importlib.util.spec_from_file_location("policy_grant_reference", root / "tools/local-pages/source_policy.py")
    policy = importlib.util.module_from_spec(policy_spec)
    policy_spec.loader.exec_module(policy)
    # The tripwire's own pinned eligibility declaration is metadata. No frozen
    # artifact body is read and no descriptive-pin exception is created here.
    syntax = ast.parse(git("show", pin + ":" + FROZEN_RULE).decode("utf-8"))
    prefixes = [ast.literal_eval(node.value) for node in syntax.body
                if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "ARTIFACT" for target in node.targets)]
    if len(prefixes) != 1 or not isinstance(prefixes[0], str):
        raise ValueError("frozen eligibility metadata is not the reviewed declaration")
    metadata = json.loads(git("show", pin + ":manifests/evidence.json"))
    catalogs = json.loads(git("show", pin + ":catalogs/landscape/manifest.json"))["catalogs"]
    paths = git("ls-tree", "-r", "--name-only", pin).decode("utf-8").splitlines()
    receipts = receipt_paths(metadata, tuple(prefixes), policy.protected_path)
    inventory = [relative for relative in inventory_paths(paths, catalogs) if not policy.protected_path(relative)]
    return {"schema": "architecture-grant-proposal/1", "source_pin": pin,
            "frozen_rule_source": FROZEN_RULE, "receipt_count": len(receipts),
            "architecture_receipt": [{"root": "repo", "path": relative} for relative in receipts],
            "architecture_inventory": [{"root": "repo", "path": relative} for relative in inventory],
            "limits": ["Proposal only; runtime discovery never grants permission.",
                       "User targets require independent exact review; unit and agent configurations are metadata only.",
                       "Referenced registered receipt or frozen-artifact bodies are never read by derivation."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--pin", required=True)
    args = parser.parse_args()
    print(json.dumps(proposal(args.root, args.pin), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
