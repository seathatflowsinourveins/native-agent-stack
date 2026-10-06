"""Render native Claude role variants without changing the pinned role bodies.

Sources: https://code.claude.com/docs/en/sub-agents#preload-skills-into-subagents
(native skills/tools frontmatter), and native-agent-stack@ecfa1127
adoption/agents/claude/{isolated-builder,stack-researcher}.md plus
tests/test_install_claude_profile.py:1289-1346. This fills the workflow's lack of
a per-call skills field; it is PR-time format glue, not a dispatch or eval runner.
Definitions and task descriptions come from adoption/workflow/manifest.json.
A14 (2026-10-06) adds the working token-tool allowlist; canonical Claude tool IDs
are in docs/token-session-handbook.md:245 and the connected upstream MCP schemas.
This module returns repository artifacts and never installs or writes them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


# These bodies remain held by the token-E2E owner. A variant inherits the same
# classification, not an amendment to the base's instructions or evidence.
VARIANTS = {
    "isolated-builder-ci-pr": "isolated-builder",
    "isolated-builder-agent-docs": "isolated-builder",
    "isolated-builder-hosting": "isolated-builder",
    "isolated-builder-broker-adapter": "isolated-builder",
    "stack-researcher-data-quant": "stack-researcher",
    "isolated-builder-skills": "isolated-builder",
    "evidence-reviewer-token-tools": "evidence-reviewer",
    "stack-verifier-token-tools": "stack-verifier",
    "security-reviewer-token-tools": "security-reviewer",
}
AGENT_DIRS = (
    "adoption/agents/claude",
    "examples/claude-native/agents",
    ".claude/agents",
)
PENDING_DIRS = ("adoption/workflow/pending-agents", "examples/claude-native/agents/pending")
TOKEN_TOOLS = (
    "mcp__semble__search", "mcp__semble__find_related",
    "mcp__headroom__headroom_compress", "mcp__headroom__headroom_retrieve",
    "mcp__codebase-memory__search_graph", "mcp__codebase-memory__trace_path",
    "mcp__codebase-memory__get_code_snippet",
    "mcp__plugin_context-mode_context-mode__ctx_execute",
    "mcp__plugin_context-mode_context-mode__ctx_execute_file",
    "mcp__plugin_context-mode_context-mode__ctx_batch_execute",
    "mcp__plugin_context-mode_context-mode__ctx_search",
    "mcp__serena__find_symbol", "mcp__serena__find_referencing_symbols",
    "mcp__serena__get_symbols_overview",
    "mcp__jcodemunch__route", "mcp__jcodemunch__menu", "mcp__jcodemunch__order",
)
FIELD = re.compile(rb"(?m)^([A-Za-z_][A-Za-z0-9_-]*):")


def _parts(source: bytes) -> tuple[bytes, bytes]:
    """Split the reviewed native frontmatter boundary, preserving every body byte."""
    if not source.startswith(b"---\n"):
        raise ValueError("base role must start with native YAML frontmatter")
    closing = source.find(b"\n---\n", 4)
    if closing < 0:
        raise ValueError("base role has no closing native frontmatter delimiter")
    return source[4:closing], source[closing + len(b"\n---\n"):]


def _fields(front: bytes) -> dict[str, bytes]:
    """Keep native field blocks verbatim; this does not implement a YAML parser."""
    matches = list(FIELD.finditer(front))
    fields: dict[str, bytes] = {}
    for index, match in enumerate(matches):
        name = match.group(1).decode("ascii")
        if name in fields:
            raise ValueError(f"base role has duplicate frontmatter field {name}")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(front)
        fields[name] = front[match.start():end].rstrip(b"\n")
    if not {"name", "description", "tools"} <= fields.keys():
        raise ValueError("base role lacks name, description or tools")
    return fields


def _render(source: bytes, stage: dict) -> bytes:
    front, body = _parts(source)
    fields = _fields(front)
    name = stage["agentType"]
    description = stage.get("description")
    if not isinstance(description, str) or not description.strip() or "\n" in description or "\r" in description:
        raise ValueError(f"{name}: provide one task-specific description line")
    preload = stage.get("preload")
    if not isinstance(preload, list) or not all(isinstance(skill, str) and skill and "\n" not in skill
                                                and "\r" not in skill for skill in preload):
        raise ValueError(f"{name}: preload must be a list of native skill names")
    if len(set(preload)) != len(preload):
        raise ValueError(f"{name}: duplicate preload")
    grant = stage.get("skill_grant", False)
    if not isinstance(grant, bool) or grant != (name == "isolated-builder-skills"):
        raise ValueError(f"{name}: only isolated-builder-skills may gain Skill")
    if grant and preload != ["context-mode:context-mode"]:
        raise ValueError(f"{name}: keep the base context-mode preload")
    fields["name"] = f"name: {name}".encode()
    fields["description"] = ("description: " + json.dumps(description, ensure_ascii=False)).encode("utf-8")
    fields["skills"] = ("skills:\n" + "\n".join("  - " + json.dumps(skill, ensure_ascii=False)
                                                     for skill in preload)).encode("utf-8") if preload else b"skills: []"
    tools = fields["tools"].decode("utf-8").removeprefix("tools: ").split(", ")
    tools = [tool for tool in tools if not tool.startswith("mcp__socraticode__")]
    if grant:
        if "Skill" in tools:
            raise ValueError("pinned builder already grants Skill; review the base change first")
        tools.append("Skill")
    fields["tools"] = ("tools: " + ", ".join(dict.fromkeys(tools + list(TOKEN_TOOLS)))).encode("utf-8")
    return b"---\n" + b"\n".join(fields.values()) + b"\n---\n" + body


def render_variants(repo_root: Path, manifest: dict) -> dict[str, bytes]:
    """Return byte-identical repository copies for each manifest-declared variant.

    A stage supplies agentType, base (agents:<base-name>), description and preload;
    isolated-builder-skills also supplies skill_grant=true. Other routes are left
    to the main renderer/validator. Conflicting definitions of one registry name
    refuse instead of silently choosing a row or overwriting another route.
    """
    rows = manifest.get("rows")
    if not isinstance(rows, list):
        raise ValueError("workflow manifest rows must be a list")
    rendered: dict[str, bytes] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("lanes"), dict):
            raise ValueError("workflow row must declare lanes")
        stage = row["lanes"].get("ultracode_stage")
        pending = stage == "inert"
        if pending:
            # Passive definitions are preparation, never an active dispatch route.
            measure = row.get("measure", {})
            stage = measure.get("planned_ultracode_stage") if isinstance(measure, dict) else None
        if not isinstance(stage, dict) or stage.get("agentType") not in VARIANTS:
            continue
        name = stage["agentType"]
        base = VARIANTS[name]
        if stage.get("base") != f"agents:{base}":
            raise ValueError(f"{name}: base must be agents:{base}")
        source = (repo_root / "adoption/agents/claude" / f"{base}.md").read_bytes()
        content = _render(source, stage)
        for directory in PENDING_DIRS if pending else AGENT_DIRS:
            path = f"{directory}/{name}.md"
            if path in rendered and rendered[path] != content:
                raise ValueError(f"{name}: conflicting definitions for one native registry name")
            rendered[path] = content
    return rendered
