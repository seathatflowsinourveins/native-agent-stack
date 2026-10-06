#!/usr/bin/env python3
"""Resolve native workflow routes against the repository's existing stores.

Source contract: docs/decisions/2026-10-06-sota-workflow-manifest.md.
Native delivery formats: https://code.claude.com/docs/en/sub-agents and
https://code.claude.com/docs/en/memory. This module installs nothing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


LANES = frozenset({"cc", "coop", "codex_lane", "sdk_worker", "ultracode_stage",
                   "agent_team", "scheduled_headless", "blind"})
CHANNELS = frozenset({"description", "preload", "skill_grant_packet", "path_rule",
                      "hook_prompt", "hook_tool_event", "hook_subagent_start",
                      "pointer", "native_verify", "codex_role_text", "sdk_native_arg"})
STATUSES = frozenset({"kept", "trial", "candidate", "held", "retired"})
STORE_PATHS = {
    "skills": "adoption/skills/manifest.json",
    "stack": "manifests/stack.json",
    "agents": "adoption/agents",
    "workflow": "examples/claude-native/workflows",
}
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
_PIN_KEYS = frozenset({"pin", "tree_sha", "skill_md_sha256", "source_pin"})
# Native qualified plugin name, already used by the pinned builder definition.
# mksglu/context-mode@6f0cc684:skills/context-mode/SKILL.md and plugin.json.
_PLUGIN_SKILLS = {"context-mode:context-mode": "stack:context-mode"}
_FIELDS = {
    "manifest": {"schema_version", "kind", "trigger_syntax", "checked_at", "decision_record",
                 "clients", "client_snapshot_note", "pin_sources", "native_skill_aliases",
                 "lanes", "channels", "rows"},
    "clients": {"claude_code", "codex_cli"},
    "row": {"id", "uses", "status", "lanes", "triggers", "sdk", "challenger", "measure",
            "overturn", "inert_reason"},
    "stage": {"agentType", "base", "description", "effort", "model", "preload",
              "required_skills", "skill_grant", "packet_imperative"},
    "triggers": {"agent_types", "intent", "skill_intents", "paths", "tool_events"},
    "event": {"tool", "regex", "path_glob"},
    "measure": {"coordinator_only_skills", "deliverable", "delivery_evidence", "readiness",
                "pending_lane_dependencies", "pending_skills", "planned_ultracode_stage"},
    "dependency": {"reason", "skills"},
    "reference": {"ref", "reason"},
}


class WorkflowError(ValueError):
    """The declared route cannot be resolved or delivered."""


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise WorkflowError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique)
    except (OSError, json.JSONDecodeError) as error:
        raise WorkflowError(f"cannot read {path.name}: {error}") from error
    if not isinstance(value, dict):
        raise WorkflowError(f"{path.name}: expected an object")
    return value


def agent_frontmatter(raw: bytes) -> dict:
    """Read native YAML with the maintained loader used by the role tests.

    Source: tests/test_install_claude_profile.py:1019-1027 and PyYAML's
    https://pyyaml.org/wiki/PyYAMLDocumentation#loading-yaml. No role body
    or native frontmatter is rewritten while resolving a route.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise WorkflowError("agent file is not UTF-8") from error
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise WorkflowError("agent file lacks native YAML frontmatter")
    try:
        import yaml
    except ImportError as error:
        raise WorkflowError("PyYAML is required to verify native agent frontmatter") from error
    try:
        value = yaml.safe_load(parts[1])
    except yaml.YAMLError as error:
        raise WorkflowError("invalid native YAML frontmatter") from error
    if not isinstance(value, dict):
        raise WorkflowError("native agent frontmatter must be a mapping")
    return value


def _list(value, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise WorkflowError(f"{label}: expected nonempty strings")
    if len(value) != len(set(value)):
        raise WorkflowError(f"{label}: duplicate values")
    return value


def _fields(value, kind: str, label: str) -> None:
    if not isinstance(value, dict):
        raise WorkflowError(f"{label}: expected an object")
    unknown = set(value) - _FIELDS[kind]
    if unknown:
        raise WorkflowError(f"{label}: unsupported routing fields {sorted(unknown)}; pins belong in the existing stores")


def _strings(value: dict, keys: set[str], label: str) -> None:
    for key in keys & value.keys():
        if not isinstance(value[key], str) or not value[key].strip():
            raise WorkflowError(f"{label}.{key}: expected a nonempty routing string")


def _schema(manifest: dict) -> None:
    """Close the routing schema; unknown nested fields cannot become pin stores."""
    _fields(manifest, "manifest", "manifest")
    _strings(manifest, {"kind", "trigger_syntax", "checked_at", "decision_record",
                        "client_snapshot_note"}, "manifest")
    if manifest.get("trigger_syntax") != "python_regex":
        raise WorkflowError("trigger_syntax: expected python_regex")
    _fields(manifest.get("clients", {}), "clients", "clients")
    for value in manifest.get("clients", {}).values():
        if not isinstance(value, str) or not re.fullmatch(r"\d+\.\d+\.\d+", value):
            raise WorkflowError("clients: expected a client-version snapshot, not a source pin")
    if not isinstance(manifest.get("rows"), list):
        raise WorkflowError("workflow rows must be a nonempty list")
    for row in manifest.get("rows", []):
        _fields(row, "row", "row")
        _strings(row, {"id", "status", "overturn", "inert_reason"}, "row")
        _fields(row.get("triggers", {}), "triggers", "triggers")
        _fields(row.get("measure", {}), "measure", "measure")
        _strings(row.get("measure", {}), {"delivery_evidence", "readiness"}, "measure")
        for key in ("pending_skills", "coordinator_only_skills"):
            _list(row.get("measure", {}).get(key, []), "measure." + key)
        if not isinstance(row.get("lanes"), dict):
            raise WorkflowError("row: invalid native lane")
        _list(row.get("triggers", {}).get("intent", []), "intent triggers")
        _list(row.get("triggers", {}).get("paths", []), "path triggers")
        _list(row.get("triggers", {}).get("agent_types", []), "agent-type triggers")
        skill_intents = row.get("triggers", {}).get("skill_intents", {})
        if not isinstance(skill_intents, dict):
            raise WorkflowError("skill_intents: expected canonical skill names and regex lists")
        routed = {ref.split(":", 1)[1] for ref in _list(row.get("uses", []), "uses")
                  if ref.startswith("skills:")}
        if set(skill_intents) - routed:
            raise WorkflowError("skill_intents: name is outside canonical row uses")
        for name, patterns in skill_intents.items():
            _list(patterns, "skill_intents." + name)
            if not patterns:
                raise WorkflowError("skill_intents: an explicit predicate cannot be empty")
        if not isinstance(row.get("triggers", {}).get("tool_events", []), list):
            raise WorkflowError("tool_events: expected a list")
        dependencies = row.get("measure", {}).get("pending_lane_dependencies", {})
        if not isinstance(dependencies, dict):
            raise WorkflowError("pending_lane_dependencies: expected a mapping")
        if "deliverable" in row.get("measure", {}) and not isinstance(row["measure"]["deliverable"], bool):
            raise WorkflowError("deliverable: expected a boolean")
        for key in ("sdk", "challenger"):
            _fields(row.get(key, {}), "reference", key)
            _strings(row.get(key, {}), {"ref", "reason"}, key)
        for event in row.get("triggers", {}).get("tool_events", []):
            _fields(event, "event", "tool event")
            _strings(event, {"tool", "regex", "path_glob"}, "tool event")
        stages = [row.get("lanes", {}).get("ultracode_stage"),
                  row.get("measure", {}).get("planned_ultracode_stage")]
        for stage in stages:
            if isinstance(stage, dict):
                _fields(stage, "stage", "stage")
                _strings(stage, {"agentType", "base", "description", "effort", "model",
                                  "packet_imperative"}, "stage")
                for key in ("preload", "required_skills"):
                    _list(stage.get(key, []), "stage." + key)
                if "skill_grant" in stage and not isinstance(stage["skill_grant"], bool):
                    raise WorkflowError("stage.skill_grant: expected a boolean")
        for dependency in dependencies.values():
            _fields(dependency, "dependency", "pending lane")
            _strings(dependency, {"reason"}, "pending lane")
            _list(dependency.get("skills", []), "pending lane skills")


def _skill_record(root: Path, name: str) -> dict:
    matches = [item for item in load_json(root / STORE_PATHS["skills"]).get("skills", [])
               if isinstance(item, dict) and item.get("name") == name]
    if len(matches) != 1:
        raise WorkflowError(f"unresolved or ambiguous skill: {name}")
    return matches[0]


def _eligible(record: dict, client: str, label: str) -> None:
    if record.get("status") not in {"kept", "trial"}:
        raise WorkflowError(f"{label}: held or retired source cannot execute")
    agents = record.get("agents")
    if agents is not None and (not isinstance(agents, list) or
                               any(not isinstance(agent, str) for agent in agents)):
        raise WorkflowError(f"{label}: malformed client eligibility")
    if client == "codex" and (record.get("codex_enabled") is not True or
                              (agents is not None and "codex" not in agents)):
        raise WorkflowError(f"{label}: source is not Codex eligible")
    if client == "claude" and (record.get("claude_listing") != "on" or
                               (agents is not None and "claude-code" not in agents)):
        raise WorkflowError(f"{label}: source is not Claude eligible")


def _preload(root: Path, name: str, aliases: dict) -> None:
    if name in aliases:
        ref = aliases[name]
        if _PLUGIN_SKILLS.get(name) != ref:
            raise WorkflowError(f"{name}: plugin alias differs from its verified native source")
        resolve_ref(root, ref)
    else:
        _eligible(_skill_record(root, name), "claude", name)


def _no_pins(value, label: str = "manifest", root: Path | None = None,
             generated: dict[str, bytes] | None = None) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _PIN_KEYS:
                raise WorkflowError(f"{label}.{key}: pins belong in the existing stores")
            if key in {"ref", "base"} and root is not None:
                resolve_ref(root, item, generated)
            _no_pins(item, f"{label}.{key}", root, generated)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _no_pins(item, f"{label}[{index}]", root, generated)


def resolve_ref(root: Path, ref: str, generated: dict[str, bytes] | None = None) -> Path:
    if not isinstance(ref, str) or ":" not in ref:
        raise WorkflowError(f"invalid reference: {ref!r}")
    namespace, name = ref.split(":", 1)
    if namespace not in STORE_PATHS or not _NAME.fullmatch(name):
        raise WorkflowError(f"invalid reference: {ref!r}")
    path = root / STORE_PATHS[namespace]
    if namespace in {"skills", "stack"}:
        data = load_json(path)
        key, identity = ("skills", "name") if namespace == "skills" else ("components", "id")
        matches = [item for item in data.get(key, []) if isinstance(item, dict) and item.get(identity) == name]
        if len(matches) != 1:
            raise WorkflowError(f"unresolved or ambiguous reference: {ref}")
        if namespace == "skills" and matches[0].get("status") in {"pruned", "retired"}:
            raise WorkflowError(f"retired reference: {ref}")
        return path
    if namespace == "agents":
        matches = [candidate for candidate in (path / "claude" / f"{name}.md",
                                               path / "codex" / f"{name}.toml")
                   if candidate.is_file() or str(candidate.relative_to(root)) in (generated or {})]
        if not matches:
            raise WorkflowError(f"unresolved reference: {ref}")
        return matches[0]
    path = path / f"{name}.js"
    if not path.is_file():
        raise WorkflowError(f"unresolved reference: {ref}")
    return path


def _agent_values(root: Path, name: str, generated: dict[str, bytes] | None = None,
                  prepared: bool = False) -> dict:
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise WorkflowError("invalid native agentType")
    path = root / "adoption/agents/claude" / f"{name}.md"
    relative = str(path.relative_to(root))
    if prepared:
        path = root / "adoption/workflow/pending-agents" / f"{name}.md"
        relative = str(path.relative_to(root))
    if relative in (generated or {}):
        return agent_frontmatter(generated[relative])
    if not path.is_file():
        raise WorkflowError(f"missing native agentType: {name}")
    return agent_frontmatter(path.read_bytes())


def validate_stage(root: Path, row: dict, generated: dict[str, bytes] | None = None,
                   aliases: dict | None = None, prepared: bool = False) -> None:
    stage = row.get("lanes", {}).get("ultracode_stage")
    if stage is None:
        return
    if stage == "inert":
        if not isinstance(row.get("inert_reason"), str) or not row["inert_reason"].strip():
            raise WorkflowError(f"{row['id']}: inert route requires its reason")
        if row.get("measure", {}).get("deliverable"):
            raise WorkflowError(f"{row['id']}: inert route marked deliverable")
        plan = row.get("measure", {}).get("planned_ultracode_stage", {})
        if isinstance(plan, dict) and plan.get("skill_grant"):
            preview = dict(row, lanes=dict(row["lanes"], ultracode_stage=plan))
            validate_stage(root, preview, generated, aliases, prepared=True)
        return
    if not isinstance(stage, dict):
        raise WorkflowError(f"{row['id']}: invalid ultracode route")
    agent = _agent_values(root, stage.get("agentType"), generated, prepared)
    if stage.get("effort") != "max" or not isinstance(stage.get("model"), str):
        raise WorkflowError(f"{row['id']}: native stage requires explicit model and max effort")
    preload = _list(stage.get("preload", []), f"{row['id']}.preload")
    actual = agent.get("skills", [])
    if isinstance(actual, str):
        actual = [item.strip() for item in actual.split(",") if item.strip()]
    if set(preload) != set(actual):
        raise WorkflowError(f"{row['id']}: route differs from native agent preloads")
    for name in preload:
        _preload(root, name, aliases or {})
    routed = [ref.split(":", 1)[1] for ref in row.get("uses", []) if ref.startswith("skills:")]
    targets = _list(stage.get("required_skills", routed), f"{row['id']}.required_skills")
    coordinator = _list(row.get("measure", {}).get("coordinator_only_skills", []),
                        f"{row['id']}.coordinator_only_skills")
    if set(targets) & set(coordinator) or set(targets) | set(coordinator) != set(routed):
        raise WorkflowError(f"{row['id']}: required/coordinator skills must partition canonical uses")
    for name in targets:
        _eligible(_skill_record(root, name), "claude", name)
    if stage.get("skill_grant") and not prepared:
        raise WorkflowError(f"{row['id']}: Skill-grant route is pending native caller acceptance")
    if set(targets).issubset(preload):
        return
    tools = agent.get("tools", [])
    if isinstance(tools, str):
        tools = [item.strip() for item in tools.split(",")]
    imperative = stage.get("packet_imperative", "")
    if not stage.get("skill_grant") or "Skill" not in tools or not isinstance(imperative, str):
        raise WorkflowError(f"{row['id']}: inert skill route declared deliverable")
    if "invoke" not in imperative.lower() or "skill" not in imperative.lower() or any(
            name not in imperative for name in targets if name not in preload):
        raise WorkflowError(f"{row['id']}: packet does not imperatively name its routed skills")
    if not prepared:
        raise WorkflowError(f"{row['id']}: Skill-grant route is pending native caller acceptance")


def validate_manifest(root: Path, manifest: dict, generated: dict[str, bytes] | None = None) -> None:
    if type(manifest.get("schema_version")) is not int or manifest.get("schema_version") != 1 or manifest.get("kind") != "sota_workflow_manifest":
        raise WorkflowError("unsupported workflow manifest")
    _schema(manifest)
    _no_pins(manifest, root=root, generated=generated)
    aliases = manifest.get("native_skill_aliases", {})
    if not isinstance(aliases, dict):
        raise WorkflowError("native_skill_aliases: expected explicit alias references")
    for name in aliases:
        if not isinstance(name, str) or ":" not in name:
            raise WorkflowError("native_skill_aliases: use the qualified native plugin skill name")
        _preload(root, name, aliases)
    if set(_list(manifest.get("lanes"), "lanes")) != LANES:
        raise WorkflowError("workflow lanes differ from the native routing contract")
    if set(_list(manifest.get("channels"), "channels")) != CHANNELS:
        raise WorkflowError("workflow channels differ from the native routing contract")
    if manifest.get("pin_sources") != STORE_PATHS:
        raise WorkflowError("pin_sources must name the existing stores only")
    record = manifest.get("decision_record")
    if not isinstance(record, str) or not record.startswith("docs/decisions/") or ".." in Path(record).parts or not (root / record).is_file():
        raise WorkflowError("missing canonical workflow decision record")
    rows = manifest.get("rows")
    if not isinstance(rows, list) or not rows:
        raise WorkflowError("workflow rows must be a nonempty list")
    catalog_path = root / "catalogs/landscape/skills-lifecycle.json"
    catalog_ids = None
    if catalog_path.is_file():
        catalog_ids = {item.get("layer_id") for item in load_json(catalog_path).get("tasks", [])}
    ids = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not _NAME.fullmatch(row["id"]):
            raise WorkflowError("invalid workflow task id")
        ids.append(row["id"])
        if catalog_ids is not None and row["id"] not in catalog_ids:
            raise WorkflowError(f"{row['id']}: task is not in the skills lifecycle catalog")
        if row.get("status") not in STATUSES:
            raise WorkflowError(f"{row['id']}: invalid workflow status")
        for ref in _list(row.get("uses"), f"{row['id']}.uses"):
            resolve_ref(root, ref, generated)
        lanes = row.get("lanes")
        if not isinstance(lanes, dict) or set(lanes) - LANES:
            raise WorkflowError(f"{row['id']}: invalid native lane")
        if row["status"] not in {"kept", "trial"} and any(
                (value != "inert") if lane == "ultracode_stage" else bool(value)
                for lane, value in lanes.items()):
            raise WorkflowError(f"{row['id']}: held, candidate or retired row cannot execute")
        pending = row.get("measure", {}).get("pending_skills", [])
        if pending:
            _list(pending, f"{row['id']}.pending_skills")
            if row.get("status") not in {"candidate", "held"}:
                raise WorkflowError(f"{row['id']}: pending dependencies require a held or candidate row")
            if row.get("measure", {}).get("deliverable"):
                raise WorkflowError(f"{row['id']}: pending route marked deliverable")
            if any((value != "inert") if lane == "ultracode_stage" else bool(value)
                   for lane, value in lanes.items()):
                raise WorkflowError(f"{row['id']}: pending dependency routed before Tier B recording")
        for lane, dependency in row.get("measure", {}).get("pending_lane_dependencies", {}).items():
            if lane not in LANES or not isinstance(dependency, dict):
                raise WorkflowError(f"{row['id']}: invalid pending lane dependency")
            _list(dependency.get("skills"), f"{row['id']}.{lane}.pending_skills")
            if not isinstance(dependency.get("reason"), str) or not dependency["reason"].strip():
                raise WorkflowError(f"{row['id']}: pending lane needs its reason")
            actual = lanes.get(lane)
            routed = (actual != "inert") if lane == "ultracode_stage" else bool(actual)
            if routed:
                raise WorkflowError(f"{row['id']}: pending lane routed before Tier B recording")
        if lanes.get("blind"):
            raise WorkflowError(f"{row['id']}: blind lane must remain skill-free")
        for lane, channels in lanes.items():
            if lane == "ultracode_stage":
                continue
            if set(_list(channels, f"{row['id']}.{lane}")) - CHANNELS:
                raise WorkflowError(f"{row['id']}: unknown channel")
            if any(channel.startswith("hook_") for channel in channels):
                raise WorkflowError(f"{row['id']}: held-out routing hooks cannot be deployed channels")
            if channels:
                client = "codex" if lane == "codex_lane" else "claude"
                for ref in row["uses"]:
                    if ref.startswith("skills:"):
                        _eligible(_skill_record(root, ref.split(":", 1)[1]), client, f"{row['id']}.{lane}")
        triggers = row.get("triggers", {})
        if not isinstance(triggers, dict):
            raise WorkflowError(f"{row['id']}: invalid triggers")
        if manifest.get("trigger_syntax") == "python_regex":
            patterns = triggers.get("intent", []) + [pattern
                       for predicates in triggers.get("skill_intents", {}).values()
                       for pattern in predicates]
            for pattern in patterns:
                try:
                    re.compile(pattern, re.IGNORECASE)
                except (re.error, TypeError) as error:
                    raise WorkflowError(f"{row['id']}: invalid intent regex") from error
        for event in triggers.get("tool_events", []):
            if not isinstance(event, dict) or not isinstance(event.get("tool"), str):
                raise WorkflowError(f"{row['id']}: invalid tool event")
            if ("regex" in event) == ("path_glob" in event):
                raise WorkflowError(f"{row['id']}: tool event requires regex or path_glob")
            if "regex" in event:
                try:
                    re.compile(event["regex"])
                except (re.error, TypeError) as error:
                    raise WorkflowError(f"{row['id']}: invalid tool-event regex") from error
        validate_stage(root, row, generated, aliases)
    if len(ids) != len(set(ids)):
        raise WorkflowError("duplicate workflow task id")
