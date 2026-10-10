"""Derive exact Architecture grants from pinned Git metadata, never input bodies.

Reference: native source_policy.ArchitectureReads at
ddb7a2a9419dac5047bb73df85b30c95bc0c98b8; installed Git ls-tree/show and
CPython3.13.16 cbc944f4bc59639a444dd971c737788ba2283a91 ast/json/pathlib.
This prints a proposal for review. It does not modify policy or discover a
runtime file into permission. User grants come only from reviewed bindings.
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
    """Reproduce grants directly from independently reviewed relative bindings.

    Binding targets are independently reviewed in the retained data file; no
    directory observation, resolver, stat or input body is used by derivation.
    """
    if not isinstance(snapshot, dict) or snapshot.get("schema") != "architecture-user-bindings/1":
        raise ValueError("user grant derivation requires reviewed bindings")
    if any(key in snapshot for key in ("directories", "names", "unapproved_names")):
        raise ValueError("user grant source must exclude directory observations and unapproved names")
    rows = snapshot.get("reviewed_bindings")
    if not isinstance(rows, list):
        raise ValueError("reviewed bindings must be an explicit list")
    policy_spec = importlib.util.spec_from_file_location("user_grant_policy_reference", ROOT / "tools/local-pages/source_policy.py")
    policy = importlib.util.module_from_spec(policy_spec)
    policy_spec.loader.exec_module(policy)
    roles = {"architecture_inventory": set(), "architecture_inventory_metadata": set(), "architecture_design": set()}
    aliases, seen, targets = {}, set(), {}
    for row in rows:
        if not isinstance(row, dict) or row.get("role") not in roles:
            raise ValueError("user binding requires a reviewed role")
        source, target = row.get("source"), row.get("target")
        for relative in (source, target):
            policy._relative(relative)
        role = row["role"]
        binding = (role, source, target)
        if binding in seen:
            raise ValueError("duplicate reviewed user binding")
        seen.add(binding)
        if source in targets and targets[source] != target:
            raise ValueError("reviewed user binding has conflicting targets")
        targets[source] = target
        if role != "architecture_inventory_metadata" and any(PurePosixPath(path).name != "SKILL.md" for path in (source, target)):
            raise ValueError("user content binding must name an exact skill asset")
        roles[role].add(target)
        if source != target:
            aliases[source] = {"root": "user", "path": source, "target_root": "user", "target_path": target}
    return {**{role: [{"root": "user", "path": path} for path in sorted(paths)] for role, paths in roles.items()},
            "architecture_inventory_aliases": sorted(aliases.values(), key=lambda row: (row["path"], row["target_path"]))}


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
