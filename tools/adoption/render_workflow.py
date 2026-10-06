#!/usr/bin/env python3
"""Render native routing artifacts without installing or registering them.

References: Claude sub-agent YAML and path-specific rules:
https://code.claude.com/docs/en/sub-agents
https://code.claude.com/docs/en/memory#path-specific-rules
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

try:
    from .workflow_manifest import WorkflowError, load_json, validate_manifest
except ImportError:  # Supported direct script execution.
    from workflow_manifest import WorkflowError, load_json, validate_manifest


def render_foundation_rules(manifest: dict) -> dict[str, bytes]:
    outputs = {}
    for row in manifest["rows"]:
        if row["id"] not in {"skills-agent-docs", "skills-hosting"}:
            continue
        paths = row.get("triggers", {}).get("paths", [])
        if not isinstance(paths, list) or not paths or any(not isinstance(path, str) for path in paths):
            raise WorkflowError(f"{row['id']}: foundation path rule needs explicit paths")
        if any("us-equities" in path or path.startswith("/") or ".." in Path(path).parts for path in paths):
            raise WorkflowError(f"{row['id']}: path rule exceeds foundation ownership")
        allowed = ("adoption/", ".claude/agents/", "examples/claude-native/agents/",
                   "tools/adoption/", "blueprints/runtime-workers/skills/",
                   "blueprints/gap-wave2-20260923/foundation__scheduling-supervision/")
        if any(not path.startswith(allowed) for path in paths):
            raise WorkflowError(f"{row['id']}: broad glob exceeds foundation ownership")
        skills = [ref.split(":", 1)[1] for ref in row["uses"] if ref.startswith("skills:")]
        pending = row.get("measure", {}).get("pending_skills", [])
        names = list(dict.fromkeys(skills + pending))
        if not names:
            raise WorkflowError(f"{row['id']}: path rule has no named skill")
        lines = ["---", "paths:", *[f"  - {json.dumps(path)}" for path in paths], "---", ""]
        if row["id"] == "skills-agent-docs":
            lines.extend(["For agent instructions and skill documents, read writing-for-agents before editing.",
                          "Apply the repository's canonical policies and use the workflow manifest's",
                          "agent-docs route. Verify commands against the target project's actual files."])
            name = "agent-docs"
        else:
            lines.extend(["For Dagu DAG or hosting changes, read the installed dagu skill and the owning",
                          "hosting recipe. Check the skill's availability and its binary-coupled version",
                          "before following its commands; report a missing trial rather than claiming a load."])
            name = "hosting"
        lines.extend(["", "Routing source: adoption/workflow/manifest.json.", ""])
        active = any(isinstance(channels, list) and "path_rule" in channels
                     for channels in row["lanes"].values())
        directory = ".claude/rules" if active else "adoption/workflow/pending-rules"
        outputs[f"{directory}/{name}.md"] = "\n".join(lines).encode("utf-8")
    return outputs


def render_routes(manifest: dict) -> bytes:
    lines = ["# Native workflow routing", "", "Generated from manifest.json; pins remain in the referenced stores.",
             "Hook channels stay held until the upstream A/B and the command-center ACK.", "",
             "| Task | Status | References | Native lanes |", "| --- | --- | --- | --- |"]
    for row in manifest["rows"]:
        lanes = []
        for name, value in row["lanes"].items():
            if name == "blind":
                continue
            if name == "ultracode_stage":
                label = "inert" if value == "inert" else value["agentType"]
                lanes.append(f"{name}: {label}")
            elif value:
                lanes.append(f"{name}: {', '.join(value)}")
        lines.append(f"| {row['id']} | {row['status']} | {', '.join(row['uses'])} | {'; '.join(lanes)} |")
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def render_all(root: Path, manifest: dict) -> dict[str, bytes]:
    outputs = render_foundation_rules(manifest)
    outputs["adoption/workflow/routing.md"] = render_routes(manifest)
    if any((isinstance(row.get("lanes", {}).get("ultracode_stage"), dict)
            and row["lanes"]["ultracode_stage"].get("base"))
           or row.get("measure", {}).get("planned_ultracode_stage")
           for row in manifest["rows"]):
        try:
            from .workflow_variants import render_variants
        except ImportError:
            from workflow_variants import render_variants
        for path, content in render_variants(root, manifest).items():
            if path in outputs:
                raise WorkflowError(f"duplicate generated artifact: {path}")
            outputs[path] = content
    return outputs


def check_rendered(root: Path, manifest: dict) -> list[str]:
    errors = []
    outputs = render_all(root, manifest)
    errors.extend(stale_outputs(root, outputs))
    for path, content in outputs.items():
        target = root / path
        if not target.is_file() or target.read_bytes() != content:
            errors.append(f"{path}: differs from the native workflow render")
    return errors


def owned_outputs() -> set[str]:
    """Finite reviewed names; never infer ownership from a directory or glob."""
    try:
        from .workflow_variants import OWNED_VARIANT_NAMES, AGENT_DIRS, PENDING_DIRS
    except ImportError:
        from workflow_variants import OWNED_VARIANT_NAMES, AGENT_DIRS, PENDING_DIRS
    paths = {f"{directory}/{name}.md" for name in OWNED_VARIANT_NAMES
             for directory in (*AGENT_DIRS, *PENDING_DIRS)}
    paths.update(f"{directory}/{name}.md" for name in ("agent-docs", "hosting")
                 for directory in (".claude/rules", "adoption/workflow/pending-rules"))
    paths.add("adoption/workflow/routing.md")
    return paths


def stale_outputs(root: Path, outputs: dict[str, bytes]) -> list[str]:
    return [f"{path}: obsolete renderer-owned artifact; remove in the reviewed lifecycle change"
            for path in sorted(owned_outputs() - outputs.keys())
            if (root / path).exists() or (root / path).is_symlink()]


def publish_outputs(root: Path, outputs: dict[str, bytes]) -> None:
    """Stage every file, then replace individually; rerender recovers a partial batch.

    No multi-file atomicity is claimed. A later publication failure may leave a
    mix of complete old/new files; --check detects it. Unknown/stale files are
    never deleted. os.replace is the native atomic per-file operation:
    https://docs.python.org/3/library/os.html#os.replace.
    """
    stale = stale_outputs(root, outputs)
    if stale:
        raise WorkflowError("\n".join(stale))
    staged = []
    try:
        for path, content in outputs.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                raise WorkflowError(f"{path}: refusing a symlink destination")
            with tempfile.NamedTemporaryFile(prefix=".workflow-render-", dir=target.parent,
                                             delete=False) as stream:
                temporary = Path(stream.name)
                staged.append((temporary, target))
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.chmod(0o644)
        for temporary, target in staged:
            os.replace(temporary, target)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--check", action="store_true", help="Verify tracked artifacts, writing nothing")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    manifest_path = args.manifest or root / "adoption/workflow/manifest.json"
    try:
        manifest = load_json(manifest_path)
        if args.check:
            validate_manifest(root, manifest)
            errors = check_rendered(root, manifest)
            if errors:
                raise WorkflowError("\n".join(errors))
        else:
            # Resolve prospective native artifacts before modifying any file.
            # An invalid reference or inert route cannot overwrite a role.
            outputs = render_all(root, manifest)
            validate_manifest(root, manifest, outputs)
            publish_outputs(root, outputs)
    except (WorkflowError, OSError, KeyError, TypeError) as error:
        print(f"Workflow render failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "mode": "check" if args.check else "render"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
