#!/usr/bin/env python3
"""Held-out, stateless skill-name hints; fail open, with no native/model calls.

Sources: https://code.claude.com/docs/en/hooks ; openai/codex@a956835d020762cb2b570053af06f643a11c0ecc:
codex-rs/hooks/schema/generated/{user-prompt-submit,post-tool-use,subagent-start}.command.output.schema.json
native-agent-stack@ecfa1127:adoption/hooks/claude/token-lanes-subagent-start.py:35-45.
Bounded regex design reference (not copied/forked): alex-macra/claude-codex-skills-assembly@
aba8bedadd83998cd2004838683ee41eaa449c1f:hooks/skill-activation.py:23-32,432-460.
The unchanged upstream prompt-only hook remains a separate B13 comparator.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import signal
import stat
import sys
import time
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

EVENTS = {"UserPromptSubmit": "hook_prompt", "PostToolUse": "hook_tool_event", "SubagentStart": "hook_subagent_start"}
CLIENTS = {"claude", "codex"}
CHANNELS = {"description", "preload", "skill_grant_packet", "path_rule", "hook_prompt",
            "hook_tool_event", "hook_subagent_start", "pointer", "native_verify",
            "codex_role_text", "sdk_native_arg"}
MAX_INPUT_BYTES = 64 * 1024
MAX_FILE_BYTES = 256 * 1024
MAX_TEXT_CHARS = 8192
MAX_PATTERN_CHARS = 512
MAX_ROWS = 64
MAX_REFS = 4
MAX_CONTEXT_CHARS = 512
MAX_REGEX_SECONDS = 0.02
MAX_MATCH_SECONDS = 0.1
MAX_TRIGGER_ITEMS = 16
MAX_ROW_REFS = 64
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
READ_TOOLS = {"Read", "read_file", "read_text_file", "Glob", "Grep", "list_files"}
EDIT_TOOLS = {"Write", "Edit", "write_file", "edit_file", "apply_patch"}
FETCH_GH = re.compile(r"\bgh\s+(?:pr\s+(?:view|list|status|checks)|run\s+(?:view|list)|api)\b")


def lexical_path(path: Path) -> Path:
    """Normalize a locator without resolving a symlink or reading its target."""
    if not path.is_absolute() or len(str(path)) > 2048 or ".." in path.parts:
        raise ValueError("absolute_bounded_path_required")
    return Path(os.path.abspath(path))


def directory_chain(path: Path, *, allow_missing: bool = False) -> None:
    """Reject redirected directories before an owned-file open.

    Native os.lstat observes the link itself rather than following its target:
    https://docs.python.org/3/library/os.html#os.lstat. The parent/root checks
    assume cooperating processes; this is not a race-proof sandbox boundary.
    """
    path = lexical_path(path)
    directories = (*reversed(path.parents), path)
    if len(directories) > 64:
        raise ValueError("path_depth_limit")
    for directory in directories:
        try:
            mode = directory.lstat().st_mode
        except FileNotFoundError:
            if allow_missing:
                return
            raise
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise ValueError("nonredirected_directory_required")


def owned_path(path: Path, root: Path, *, allow_missing_parents: bool = False) -> Path:
    root = lexical_path(root)
    path = lexical_path(path)
    path.relative_to(root)  # Reject an outside locator before inspecting it.
    directory_chain(root)
    directory_chain(path.parent, allow_missing=allow_missing_parents)
    return path


def safe_read(path: Path, *, root: Path) -> bytes:
    """Read a regular file under an explicit nonredirected owned root."""
    path = owned_path(path, root)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    nonblock = getattr(os, "O_NONBLOCK", None)
    if not nofollow or not nonblock:
        raise ValueError("required_file_flags_missing")
    descriptor = os.open(path, os.O_RDONLY | nofollow | nonblock)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("regular_file_required")
        stream = os.fdopen(descriptor, "rb")
        descriptor = None
        try:
            data = stream.read(MAX_FILE_BYTES + 1)
        finally:
            stream.close()
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("file_limit")
    return data


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def read_json(path: Path, *, root: Path) -> dict:
    value = json.loads(safe_read(path, root=root), object_pairs_hook=unique_object)
    if not isinstance(value, dict):
        raise ValueError("object_required")
    return value


def project_root(cwd: Path) -> Path:
    current = lexical_path(cwd)
    directory_chain(current)
    for directory in (current, *current.parents):
        if (directory / ".git").exists():
            return directory
    return current


def root_from_manifest(path: Path) -> Path:
    path = lexical_path(path)
    if path.name != "manifest.json" or path.parent.name != "workflow" or path.parent.parent.name != "adoption":
        raise ValueError("canonical_manifest_location_required")
    root = path.parent.parent.parent
    owned_path(path, root)
    return root


def text(value: Any) -> str:
    return value[:MAX_TEXT_CHARS] if isinstance(value, str) else ""


@contextmanager
def regex_deadline(deadline: float | None = None) -> Iterator[None]:
    if not hasattr(signal, "setitimer") or not hasattr(signal, "ITIMER_REAL"):
        raise ValueError("bounded_regex_unavailable")

    def expired(_number, _frame):
        raise TimeoutError("regex_limit")

    remaining = MAX_REGEX_SECONDS if deadline is None else min(MAX_REGEX_SECONDS, deadline - time.monotonic())
    if remaining <= 0:
        raise TimeoutError("match_budget_exhausted")
    previous = signal.signal(signal.SIGALRM, expired)
    timer = signal.setitimer(signal.ITIMER_REAL, remaining)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *timer)
        signal.signal(signal.SIGALRM, previous)


def matches(pattern: Any, value: str, *, deadline: float | None = None) -> bool:
    if not isinstance(pattern, str) or not pattern or len(pattern) > MAX_PATTERN_CHARS:
        return False
    try:
        with regex_deadline(deadline):
            return re.search(pattern, value[:MAX_TEXT_CHARS], flags=re.IGNORECASE) is not None
    except (ValueError, re.error, TimeoutError):
        return False


def paths_from_edit(payload: dict, root: Path) -> list[str]:
    tool = payload.get("tool_name")
    if tool not in EDIT_TOOLS:
        return []
    arguments = payload.get("tool_input", {})
    candidates = []
    if isinstance(arguments, dict):
        for key in ("file_path", "path", "filename"):
            if isinstance(arguments.get(key), str):
                candidates.append(arguments[key])
        if tool == "apply_patch":
            # Native Codex wraps its freeform raw patch in tool_input.command:
            # openai/codex@a956835d:codex-rs/core/src/tools/handlers/apply_patch.rs:290-295,437-450.
            patch = text(arguments.get("command"))
            candidates.extend(re.findall(r"(?m)^\*\*\* (?:Update|Add|Delete) File: (.+)$", patch))
    result = []
    for candidate in candidates[:32]:
        if len(candidate) > 2048 or "\n" in candidate or "\r" in candidate:
            continue
        path = Path(candidate)
        try:
            if not path.is_absolute():
                cwd_value = payload.get("cwd")
                if not isinstance(cwd_value, str):
                    continue  # A relative native target needs its actual event cwd.
                cwd = owned_path(lexical_path(Path(cwd_value)), root)
                directory_chain(cwd)
                path = cwd / path
            path = owned_path(path, root, allow_missing_parents=True)
            if path.is_symlink():
                continue
            result.append(path.relative_to(root).as_posix())
        except (ValueError, OSError):
            pass
    return result


def glob_matches(pattern: Any, path: str, *, deadline: float | None = None) -> bool:
    """Match the documented relative POSIX subset with Python 3.13's native API.

    https://docs.python.org/3.13/library/glob.html#glob.translate preserves
    separators and makes a complete ** segment match zero or more directories.
    Native brace/extglob expansion is outside this held prototype's subset.
    """
    translate = getattr(glob, "translate", None)
    if (not callable(translate) or not isinstance(pattern, str) or not pattern
            or len(pattern) > MAX_PATTERN_CHARS or not isinstance(path, str)
            or len(path) > 2048 or pattern.startswith("/")
            or any(character in pattern for character in "{}[]?\\()")
            or ".." in PurePosixPath(pattern).parts
            or any("**" in part and part != "**" for part in pattern.split("/"))):
        return False
    try:
        with regex_deadline(deadline):
            return re.match(translate(pattern, recursive=True, include_hidden=True, seps="/"), path) is not None
    except (ValueError, re.error, TimeoutError):
        return False


def active_lane(row: dict, lane: str, *, child: bool, role: Any) -> bool:
    """An opt-in hint still needs an executable lane in the actual workflow row."""
    lanes = row.get("lanes")
    if not isinstance(lanes, dict):
        return False
    if child:
        stage = lanes.get("ultracode_stage")
        return lane == "ultracode_stage" and isinstance(stage, dict) and stage.get("agentType") == role
    if lane == "ultracode_stage":
        return False  # An active stage is a child route, never a main-session list.
    channels = lanes.get(lane)
    return bool(channels) and isinstance(channels, list) and all(
        isinstance(channel, str) and channel in CHANNELS for channel in channels)


def ambiguous_fetch(payload: dict) -> bool:
    if payload.get("tool_name") in READ_TOOLS:
        return True
    arguments = payload.get("tool_input")
    command = text(arguments.get("command")) if isinstance(arguments, dict) else ""
    # The native event lacks original user intent. Fetch-only reads, including
    # --log-failed, cannot establish permission or intent to repair/address.
    return payload.get("tool_name") == "Bash" and bool(FETCH_GH.search(command))


def role_metadata(root: Path, manifest: dict, role: str, client: str) -> dict | None:
    if not SAFE_NAME.fullmatch(role) or role.startswith("blind-") or client == "codex":
        return None  # S10 must supply a native Codex child capability contract.
    registered = set()
    for row in manifest.get("rows", []):
        for reference in row.get("uses", []):
            if isinstance(reference, str) and reference.startswith("agents:"):
                registered.add(reference[7:])
        stage = row.get("lanes", {}).get("ultracode_stage")
        if isinstance(stage, dict) and isinstance(stage.get("agentType"), str):
            registered.add(stage["agentType"])
    if role not in registered:
        return None
    base = manifest.get("pin_sources", {}).get("agents")
    if base != "adoption/agents":
        return None
    # Same maintained parser as S1's canonical agent_frontmatter. No role body,
    # inherited wildcard or payload-supplied grant is treated as capability.
    import yaml

    def metadata_at(path: Path, owned_root: Path) -> dict | None:
        parts = safe_read(path, root=owned_root).split(b"---", 2)
        if len(parts) != 3 or parts[0].strip() or len(parts[1]) > 8192:
            return None
        value = yaml.safe_load(parts[1])
        return value if isinstance(value, dict) else None

    canonical = metadata_at(root / base / "claude" / (role + ".md"), root)
    project_role = root / ".claude/agents" / (role + ".md")
    native = (project_role, root) if project_role.exists() else None
    if native is None:
        # A custom native profile cannot borrow a default-global role grant.
        # https://code.claude.com/docs/en/env-vars (CLAUDE_CONFIG_DIR), and
        # https://code.claude.com/docs/en/sub-agents (user-level agent definitions).
        configured = os.environ.get("CLAUDE_CONFIG_DIR")
        try:
            config_root = lexical_path(Path(configured) if configured else Path.home() / ".claude")
            directory_chain(config_root)
        except (ValueError, OSError):
            return None
        user_root = config_root / "agents"
        user_role = user_root / (role + ".md")
        native = (user_role, user_root) if user_role.exists() else None
    if canonical is None or native is None:
        return None
    metadata = metadata_at(*native)
    if metadata is None or any(metadata.get(key) != canonical.get(key) for key in ("name", "tools", "skills")):
        return None
    if not isinstance(metadata, dict) or metadata.get("name") != role:
        return None
    tools = metadata.get("tools")
    tools = [item.strip() for item in tools.split(",")] if isinstance(tools, str) else tools
    if not isinstance(tools, list) or "Skill" not in tools:
        return None
    preloads = metadata.get("skills", [])
    if not isinstance(preloads, list) or any(not isinstance(item, str) for item in preloads):
        return None
    return {"tools": tools, "preloads": preloads}


def skill_registry(root: Path, manifest: dict, client: str) -> dict[str, dict]:
    if manifest.get("pin_sources", {}).get("skills") != "adoption/skills/manifest.json":
        return {}
    central = read_json(root / "adoption/skills/manifest.json", root=root)
    if not isinstance(central.get("skills"), list):
        return {}
    result = {}
    for skill in central.get("skills", []):
        if not isinstance(skill, dict):
            continue
        name = skill.get("name")
        if not isinstance(name, str) or not SAFE_NAME.fullmatch(name) or skill.get("status") not in {"kept", "trial"}:
            continue
        targets = skill.get("agents", ["claude-code", "codex"])
        if not strings(targets, max_items=MAX_ROW_REFS):
            continue
        if client == "claude":
            eligible = "claude-code" in targets and skill.get("claude_listing") in {"on", "name-only"} and not skill.get("upstream_disable_model_invocation", False)
        else:
            eligible = "codex" in targets and skill.get("codex_enabled") is True and skill.get("upstream_allow_implicit_invocation", True) is True
        if eligible:
            if name in result:
                raise ValueError("ambiguous_skill_identity")
            result[name] = skill
    return result


def strings(value: Any, *, max_items: int = MAX_TRIGGER_ITEMS) -> bool:
    return (isinstance(value, list) and len(value) <= max_items and all(
        isinstance(item, str) and 0 < len(item) <= MAX_PATTERN_CHARS for item in value))


def valid_row(row: dict) -> bool:
    """Reject malformed routing containers before treating their members as hints."""
    uses = row.get("uses")
    measure = row.get("measure", {})
    triggers = row.get("triggers", {})
    if not strings(uses, max_items=MAX_ROW_REFS) or not isinstance(measure, dict) or not isinstance(triggers, dict):
        return False
    if not strings(measure.get("pending_skills", [])) or not strings(measure.get("coordinator_only_skills", [])):
        return False
    dependencies = measure.get("pending_lane_dependencies", {})
    if not isinstance(dependencies, dict) or any(
            not isinstance(lane, str) or not isinstance(dependency, dict)
            or not strings(dependency.get("skills", []))
            for lane, dependency in dependencies.items()):
        return False
    if set(triggers) - {"intent", "paths", "tool_events", "agent_types", "skill_intents"}:
        return False
    if any(not strings(triggers.get(key, [])) for key in ("intent", "paths", "agent_types")):
        return False
    events = triggers.get("tool_events", [])
    if not isinstance(events, list) or len(events) > MAX_TRIGGER_ITEMS:
        return False
    for event in events:
        if (not isinstance(event, dict) or set(event) - {"tool", "regex", "path_glob"}
                or not isinstance(event.get("tool"), str) or not 0 < len(event["tool"]) <= 128
                or ("regex" in event) == ("path_glob" in event)):
            return False
        pattern = event.get("regex", event.get("path_glob"))
        if not isinstance(pattern, str) or not 0 < len(pattern) <= MAX_PATTERN_CHARS:
            return False
    skill_intents = triggers.get("skill_intents", {})
    canonical_skills = {reference[7:] for reference in uses if reference.startswith("skills:")}
    return (isinstance(skill_intents, dict) and len(skill_intents) <= MAX_ROW_REFS
            and all(isinstance(name, str) and name in canonical_skills and strings(patterns)
                    for name, patterns in skill_intents.items()))


def any_regex(patterns: list[str], value: str, deadline: float) -> bool:
    for pattern in patterns:
        if time.monotonic() >= deadline:
            break
        if matches(pattern, value, deadline=deadline):
            return True
    return False


def any_glob(patterns: list[str], paths: list[str], deadline: float) -> bool:
    for pattern in patterns:
        for path in paths:
            if time.monotonic() >= deadline:
                return False
            if glob_matches(pattern, path, deadline=deadline):
                return True
    return False


def row_matches(row: dict, payload: dict, event: str, edit_paths: list[str], *, deadline: float) -> bool:
    triggers = row.get("triggers", {})
    if event == "UserPromptSubmit":
        prompt = text(payload.get("prompt"))
        return any_regex(triggers.get("intent", []), prompt, deadline)
    if event == "SubagentStart":
        return payload.get("agent_type") in triggers.get("agent_types", [])
    tool = payload.get("tool_name")
    arguments = payload.get("tool_input")
    command = text(arguments.get("command")) if isinstance(arguments, dict) else ""
    for trigger in triggers.get("tool_events", []):
        if time.monotonic() >= deadline:
            return False
        if not isinstance(trigger, dict) or trigger.get("tool") != tool:
            continue
        if "regex" in trigger and matches(trigger["regex"], command, deadline=deadline):
            return True
        if "path_glob" in trigger and any_glob([trigger["path_glob"]], edit_paths, deadline):
            return True
    return any_glob(triggers.get("paths", []), edit_paths, deadline)


def suggest(root: Path, manifest: dict, payload: dict, *, client: str, lane: str, benchmark_hints: bool) -> list[str]:
    event = payload.get("hook_event_name")
    role = payload.get("agent_type")
    if not benchmark_hints or lane == "blind" or event not in EVENTS or client not in CLIENTS:
        return []
    if not strings(manifest.get("lanes")) or lane not in manifest["lanes"]:
        return []
    if manifest.get("schema_version") != 1 or manifest.get("kind") != "sota_workflow_manifest" or manifest.get("trigger_syntax") != "python_regex":
        return []
    if isinstance(role, str) and role.startswith("blind-"):
        return []
    child = event == "SubagentStart" or bool(role) or bool(payload.get("agent_id"))
    metadata = None
    if child:
        if not isinstance(role, str):
            return []
        metadata = role_metadata(root, manifest, role, client)
        if metadata is None:
            return []
    if event == "PostToolUse" and ambiguous_fetch(payload):
        return []
    registry = skill_registry(root, manifest, client)
    edit_paths = paths_from_edit(payload, root) if event == "PostToolUse" else []
    rows = manifest.get("rows")
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        return []
    deadline = time.monotonic() + MAX_MATCH_SECONDS
    matched = []
    for row in rows:
        if time.monotonic() > deadline:
            break
        if not isinstance(row, dict) or row.get("status") not in {"kept", "trial"} or not valid_row(row):
            continue
        if not active_lane(row, lane, child=child, role=role):
            continue
        measure = row.get("measure", {})
        if measure.get("pending_skills") or lane in measure.get("pending_lane_dependencies", {}):
            continue
        if not row_matches(row, payload, event, edit_paths, deadline=deadline):
            continue
        forbidden = set(measure.get("coordinator_only_skills", [])) if child else set()
        preloads = set(metadata["preloads"]) if metadata else set()
        for reference in row.get("uses", []):
            if time.monotonic() >= deadline:
                return matched
            if not isinstance(reference, str) or not reference.startswith("skills:"):
                continue
            name = reference[7:]
            skill_intents = row.get("triggers", {}).get("skill_intents", {})
            if event == "UserPromptSubmit" and "skill_intents" in row.get("triggers", {}) and (
                    name not in skill_intents or not any_regex(skill_intents[name], text(payload.get("prompt")), deadline)):
                continue
            if name in registry and name not in forbidden and name not in preloads and name not in matched:
                matched.append(name)
                if len(matched) >= MAX_REFS:
                    return matched
    return matched


def serialize(event: str, names: list[str]) -> dict | None:
    safe = [name for name in names[:MAX_REFS] if isinstance(name, str) and SAFE_NAME.fullmatch(name)]
    if event not in EVENTS or not safe:
        return None
    context = "Apply the relevant task skill: " + ", ".join(safe) + "."
    if len(context) > MAX_CONTEXT_CHARS:
        return None
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}


class QuietParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("invalid_arguments")


def main(argv: list[str] | None = None) -> int:
    try:
        parser = QuietParser(description=__doc__)
        parser.add_argument("--client", choices=sorted(CLIENTS), required=True)
        parser.add_argument("--lane")
        parser.add_argument("--manifest", type=Path)
        parser.add_argument("--benchmark-hints", action="store_true")
        args = parser.parse_args(argv)
        if not args.benchmark_hints:
            return 0
        data = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(data) > MAX_INPUT_BYTES:
            return 0
        payload = json.loads(data, object_pairs_hook=unique_object)
        if not isinstance(payload, dict):
            return 0
        cwd = Path(payload.get("cwd", os.getcwd()))
        root = root_from_manifest(args.manifest) if args.manifest else project_root(cwd)
        path = args.manifest or root / "adoption/workflow/manifest.json"
        manifest = read_json(path, root=root)
        lane = args.lane or ("ultracode_stage" if payload.get("hook_event_name") == "SubagentStart" and args.client == "claude" else "codex_lane" if args.client == "codex" else "cc")
        if lane not in manifest.get("lanes", {}):
            return 0
        names = suggest(root, manifest, payload, client=args.client, lane=lane, benchmark_hints=args.benchmark_hints)
        output = serialize(payload.get("hook_event_name"), names)
        if output:
            sys.stdout.write(json.dumps(output, separators=(",", ":")) + "\n")
    except (Exception, SystemExit):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
