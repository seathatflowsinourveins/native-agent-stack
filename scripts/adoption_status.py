#!/usr/bin/env python3
"""Read-only adoption prerequisite report. No installation or runtime acceptance.

Checks command presence with shutil.which; it never invokes those commands. The
only subprocess is a bounded native Git revision query. It opens no credential store
(~/.claude.json, ~/.claude/.credentials.json, ~/.codex/auth.json) and reads no
service/process state, network endpoint or model API. Client configuration is read
only with the opt-in --client-wiring, which parses fixed native client files whole and
in-process and emits no value from them: fixed booleans and hook-event counts only,
never a value, command, path or environment value (Codex hook trust is compared as a
SHA-256 inside this process, as Codex computes it). The opt-in --pinned-versions execs
a profile's PATH-resolved commands with their platform pin's declared "exec"
version_probe only (never one declared "npm-metadata" or another method, since that
method exists exactly because running the tool starts a server or a UI), each in its
own process group that is killed once the probe exits, times out or is interrupted,
and emits booleans, counts, component ids and version strings from the checked-in
manifest and pins file and the output of a probe that exited 0.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from urllib.parse import urlsplit
import warnings


SHA = re.compile(r"[0-9a-f]{40}\Z")
NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*\Z")
# Grafana's Linux x86-64 archive keeps this basename after extraction:
# https://grafana.com/docs/loki/latest/setup/install/local/
COMMAND_ALIASES = {("loki", "linux", "x86_64"): ("loki-linux-amd64",)}
NO_CLIENT_STATE = ("No credentials, client configuration, environment values, network endpoints, or running "
                   "processes are inspected.")
# --pinned-versions replaces this statement with PINNED_VERSION_LIMITATIONS.
NO_PINNED_VERSION = "Executable presence does not verify its version, installation integrity, activation, or E2E behavior."
LIMITATIONS = [
    NO_PINNED_VERSION,
    "Historical acceptance remains historical; no provider, service, GPU, hook, or broker acceptance runs here.",
    "Git comparison reports source identity only; changed worktree files are not inspected.",
    NO_CLIENT_STATE,
]
# --client-wiring replaces NO_CLIENT_STATE with these two statements.
CLIENT_WIRING_LIMITATIONS = [
    "--client-wiring parses the user Claude settings and plugin registry, the Codex config.toml, hooks.json, "
    "AGENTS.override.md, AGENTS.md and RTK.md, and this checkout's .claude/settings.json and .codex/config.toml whole "
    "and in-process, and emits no value from them: fixed booleans and hook-event counts only. It opens no credential "
    "store (~/.claude.json, ~/.claude/.credentials.json, ~/.codex/auth.json), network endpoint or running process; "
    "environment variables only locate the client homes, and two opt-ins are checked by name.",
    "Configured wiring is not activation: managed, project or local Claude settings, and Codex profiles, project "
    "config.toml features and command-line overrides, can override the user scope read here. Codex hook trust is "
    "computed for the ai-memory hooks.json entries only, the way Codex rust-v0.155.1 to rust-v0.157.1 computes it "
    "(a user config.toml [hooks.state] trusted_hash equal to the hook's current hash); a later Codex that hashes "
    "differently reads as untrusted here until this check follows it. hooks.json is read as Codex's serde parse "
    "reads it, and both Codex hook counts are null for a file that parse rejects, since Codex then loads none of "
    "its hooks; the trusted count is also null when a matcher on an ai-memory hook uses regex syntax this check "
    "cannot evaluate as Rust's regex crate does. Plugin revisions and bundled plugin hooks, project trust, Claude "
    "MCP registrations, MCP server startup and a useful native call remain the clients' own checks (/mcp, /hooks, "
    "the app-server hooks/list, the plugin doctor).",
]
PINNED_VERSION_TIMEOUT_SECONDS = 30
# adoption/bootstrap-linux.sh run_version_probe: TERM to the probe's process group when its bound expires, KILL
# this many seconds later.
PINNED_VERSION_KILL_GRACE_SECONDS = 2
# A pin's version_probe.method this script ever execs. "npm-metadata" (context-mode: no version flag, any
# other argument starts its MCP stdio server) and any future undeclared method are reported unchecked instead;
# see adoption/bootstrap-linux.sh's write_version_report, which this reuses the pins file's schema from (#251).
SUPPORTED_VERSION_PROBE_METHODS = ("exec",)
# --pinned-versions replaces NO_PINNED_VERSION with this statement.
PINNED_VERSION_LIMITATIONS = [
    "--pinned-versions execs a selected profile's component_ids that have an \"exec\" version_probe in this "
    "platform's pins file (adoption/pins-<os>-<arch>.json): the declared command, located on PATH only, run with "
    "stdin from /dev/null in its own process group. That group is killed once the probe exits, on interruption "
    "(SIGINT, SIGTERM or SIGHUP; a signal this check started with ignored, as under nohup, stays ignored), "
    f"and after its pin's timeout_seconds or {PINNED_VERSION_TIMEOUT_SECONDS}s (TERM, then KILL "
    f"{PINNED_VERSION_KILL_GRACE_SECONDS}s later); a descendant that leaves the group, for example by starting its "
    "own session, is not reached. Only a probe that exits 0 has its stdout and stderr text compared against the "
    "pinned version; a nonzero exit is reported as not matching. A component with no pins entry for this "
    "platform, or whose declared method is not \"exec\" (for example context-mode's \"npm-metadata\", declared "
    "because any other argument starts its MCP stdio server), is reported unchecked; this never execs a probe "
    "whose declared method is not \"exec\".",
]
# The selected token practice's client wiring (docs/token-efficiency-stack.md, "Coverage check").
CONTEXT_MODE_PLUGIN = "context-mode@context-mode"
WIRED_MCP_SERVERS = ("serena", "socraticode", "ai-memory")
# This catalog's pins-<os>-<arch>.json naming (adoption/pins-macos-arm64.json) vs. platform.system().lower().
PIN_OS_ALIASES = {"darwin": "macos"}
DEPTH_VARIABLE = "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"
CONCURRENCY_VARIABLE = "CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS"
EFFORT_VARIABLE = "CLAUDE_CODE_EFFORT_LEVEL"  # any value overrides every child's effort
AGENT_TEAMS_VARIABLE = "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"  # the agent-teams opt-in
# Codex 0.155.1's lifecycle-hook feature keys (codex-rs/features: the legacy alias, then the key), in the sorted
# order Codex applies them, so "hooks" wins when both are set.
CODEX_HOOK_FEATURES = ("codex_hooks", "hooks")
# The global instruction files Codex reads from its home, first non-blank one wins, passed to the model verbatim:
# no "@path" reference is expanded (codex-rs/codex-home/src/instructions/mod.rs at rust-v0.155.1 and rust-v0.157.1).
CODEX_INSTRUCTION_FILES = ("AGENTS.override.md", "AGENTS.md")
# rtk 0.50.0 (src/hooks/init.rs RTK_MD_OWNED_MARKER) heads the RTK.md it writes with this comment line; it is RTK's
# ownership record, not an instruction, so an inline copy may leave it out.
RTK_OWNED_MARKER = "<!-- rtk-owned:"
# Codex hook trust, read from codex-rs/hooks/src/engine/discovery.rs, config_rules.rs, lib.rs, events/common.rs and
# codex-rs/config/src/hook_config.rs and fingerprint.rs (byte-identical where used at rust-v0.155.1 and
# rust-v0.157.1). A hooks.json handler runs only when it is enabled and trusted: the user config.toml's
# [hooks.state."<hooks.json path>:<event key>:<group>:<handler>"] trusted_hash equals the SHA-256 of the handler's
# normalized identity. Event name -> the key label Codex uses in both.
CODEX_HOOK_EVENTS = {"PreToolUse": "pre_tool_use", "PermissionRequest": "permission_request",
                     "PostToolUse": "post_tool_use", "PreCompact": "pre_compact", "PostCompact": "post_compact",
                     "SessionStart": "session_start", "SessionEnd": "session_end",
                     "UserPromptSubmit": "user_prompt_submit", "SubagentStart": "subagent_start",
                     "SubagentStop": "subagent_stop", "Stop": "stop", "Interrupt": "interrupt"}
CODEX_EVENTS_WITHOUT_MATCHER = frozenset({"UserPromptSubmit", "Stop", "Interrupt"})  # matcher_pattern_for_event
CODEX_CONTEXT_LIMIT_EVENTS = frozenset({"PreToolUse", "PostToolUse", "SessionStart", "UserPromptSubmit",
                                        "SubagentStart"})  # the events that may emit additionalContext
CODEX_DEFAULT_CONTEXT_LIMIT = 2_500  # DEFAULT_HOOK_OUTPUT_TOKEN_LIMIT, dropped from the identity when configured
# Codex reads hooks.json with serde_json::from_str::<HooksFile> (discovery.rs load_hooks_json) and loads no hook at
# all from a file that fails it. The fields of each serde struct in hook_config.rs, in declaration order (a JSON
# array fills them in that order); HookHandlerConfig is internally tagged by "type", with these variants.
CODEX_HOOKS_FILE_FIELDS = ("description", "hooks")
CODEX_GROUP_FIELDS = ("matcher", "hooks")
CODEX_HANDLER_FIELDS = {"command": ("command", "commandWindows", "timeout", "async", "statusMessage",
                                    "additionalContextLimit"),
                        "mcp_tool": ("server", "tool", "input", "timeout", "statusMessage"),
                        "prompt": (), "agent": ()}
# serde_json 1.0.149 (Codex 0.157.1's Cargo.lock): the 128th array or object nested along a path it parses fails
# ("recursion limit exceeded"); a skipped unknown field's value is scanned without that limit.
SERDE_JSON_RECURSION_LIMIT = 128
U64_MAX = 2 ** 64 - 1
I64_MAX = 2 ** 63 - 1  # a TOML integer: the widest number Codex's hook hash can hold
RUST_WHITESPACE = ("\t\n\x0b\x0c\r \x85\xa0           "
                   "     　")  # char::is_whitespace, which Rust's str::trim strips
# The regex constructs that Python's re and Rust's regex crate (regex-syntax 0.8.8 in Codex 0.157.1) parse alike;
# see shared_regex_subset.
REGEX_META = frozenset("\\.+*?()|[]{}^$#&-~")  # regex-syntax's escapable meta characters; Python escapes them too
REGEX_CLASS_ESCAPES = frozenset("dDwWsS")
REGEX_CONTROL_ESCAPES = frozenset("aftnrv")
REGEX_ASSERTION_ESCAPES = frozenset("bBA")
REGEX_SUBSET_MAX_LENGTH = 1_000
REGEX_SUBSET_MAX_CLASSES = 20  # Unicode classes compile large in Rust; a few stay far below its 10 MiB size limit
REGEX_SUBSET_MAX_DEPTH = 64
CLIENT_FILE_LIMIT = 1_048_576
CLIENT_WIRING_KEYS = {
    "claude": ("rtk_hook", "ai_memory_hook_events", "context_mode_plugin_enabled", "subagent_spawn_depth_1",
               "workflow_concurrency_set", "effort_level_env_unset", "agent_teams_off"),
    "project": ("settings_depth_and_concurrency", "codex_mcp_servers_present"),
    "codex": ("rtk_instructions", "context_mode_plugin_enabled", "mcp_servers_present", "hooks_feature_enabled",
              "ai_memory_hook_events", "ai_memory_hook_events_trusted"),
}


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
    """Return only a native Git SHA from this root; suppress arbitrary Git errors.

    ``root`` is resolved before comparison so this holds regardless of
    whether the caller already resolved it: macOS routes its default
    tempdir through ``/var`` -> ``/private/var`` (and any project checkout
    can sit behind another symlink), so comparing an unresolved caller path
    against git's own resolved --show-toplevel answer would wrongly return
    None even for the real repository. inspect_adoption already resolves
    root first, so this is a no-op there; a direct caller no longer needs to
    resolve it itself first.
    """
    try:
        root = root.resolve()
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), "rev-parse", "--show-toplevel", "HEAD"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5,
            check=False,
        )
        lines = result.stdout.splitlines()
        if result.returncode == 0 and len(lines) == 2 and Path(lines[0]).resolve() == root and SHA.fullmatch(lines[1]):
            return lines[1]
    # RuntimeError: Path.resolve() on Python before 3.13 raises it for a
    # symlink loop (3.13+ instead returns the unresolved remainder); either
    # way this is a Git-adjacent environment condition to suppress, not a
    # reason to propagate an uncaught exception out of a "return None on any
    # failure" helper.
    except (OSError, ValueError, UnicodeError, RuntimeError, subprocess.TimeoutExpired):
        pass
    return None


def command_present(name: str, host: dict) -> bool:
    """Check PATH only, preferring the conventional name; never run candidates."""
    if shutil.which(name) is not None:
        return True
    aliases = COMMAND_ALIASES.get((name, host["os"], host["architecture"]), ())
    return any(shutil.which(alias) is not None for alias in aliases)


def read_client_file(path: Path, kind: str):
    """A client file parsed as "json", "toml" or "text": {} or "" when absent, None when unreadable,
    oversized or malformed. Parsed content stays in this module; callers reduce it to booleans and counts."""
    try:
        if not os.path.lexists(path):
            return "" if kind == "text" else {}
        if not path.is_file() or path.stat().st_size > CLIENT_FILE_LIMIT:
            return None
        text = path.read_text(encoding="utf-8")
        if kind == "text":
            return text
        if kind == "json":
            data = json.loads(text)
        else:
            import tomllib  # standard library from Python 3.11; older interpreters report the file unreadable
            data = tomllib.loads(text)
    except (ImportError, OSError, UnicodeError, ValueError, RecursionError):
        return None
    return data if isinstance(data, dict) else None


def table(value) -> dict:
    return value if isinstance(value, dict) else {}


def hook_argvs(groups, tool: str | None = None):
    """argv of each command hook in one event's matcher groups; with ``tool``, only groups whose
    matcher covers it (absent, "" and "*" match every tool, anything else must match the whole name)."""
    for group in groups if isinstance(groups, list) else []:
        if not isinstance(group, dict):
            continue
        matcher = group.get("matcher")
        if tool is not None and matcher not in (None, "", "*"):
            try:
                if not isinstance(matcher, str) or re.fullmatch(matcher, tool) is None:
                    continue
            except re.error:
                continue
        hooks = group.get("hooks")
        for hook in hooks if isinstance(hooks, list) else []:
            if isinstance(hook, dict) and hook.get("type") == "command" and isinstance(hook.get("command"), str):
                try:
                    yield shlex.split(hook["command"])
                except ValueError:
                    continue


def runs(argv: list[str], program: str) -> bool:
    return bool(argv) and PurePosixPath(argv[0]).name == program


def ai_memory_hook_events(hooks) -> int:
    """How many hook events run an ``ai-memory ... hook`` command (the command is never returned)."""
    return sum(any(runs(argv, "ai-memory") and "hook" in argv[1:] for argv in hook_argvs(groups))
               for groups in table(hooks).values())


def settings_env_text(settings: dict, name: str) -> str | None:
    """A settings ``env`` entry as text, compared inside this module and never returned by it."""
    value = table(settings.get("env")).get(name)
    return str(value).strip() if isinstance(value, (str, int)) and not isinstance(value, bool) else None


def depth_and_concurrency(settings: dict) -> tuple[bool, bool]:
    """Subagent spawn depth exactly 1; a workflow concurrency cap within the client's accepted 1-256."""
    concurrency = settings_env_text(settings, CONCURRENCY_VARIABLE) or ""
    return (settings_env_text(settings, DEPTH_VARIABLE) == "1",
            re.fullmatch(r"[0-9]{1,3}", concurrency) is not None and 1 <= int(concurrency) <= 256)


def mcp_servers_present(config) -> dict:
    """Codex ``mcp_servers`` table names only (a table with ``enabled = false`` is not present)."""
    if config is None:
        return dict.fromkeys(WIRED_MCP_SERVERS)
    servers = table(config.get("mcp_servers"))
    return {name: isinstance(servers.get(name), dict) and servers[name].get("enabled") is not False
            for name in WIRED_MCP_SERVERS}


def claude_wiring(claude_dir: Path, env) -> dict:
    settings = read_client_file(claude_dir / "settings.json", "json")
    if settings is None:
        return dict.fromkeys(CLIENT_WIRING_KEYS["claude"])
    hooks = {} if settings.get("disableAllHooks") is True else table(settings.get("hooks"))
    names = table(settings.get("env"))
    plugin = table(settings.get("enabledPlugins")).get(CONTEXT_MODE_PLUGIN) is True
    if plugin:  # enabled in settings and recorded in the native plugin registry
        registry = read_client_file(claude_dir / "plugins" / "installed_plugins.json", "json")
        installs = None if registry is None else table(registry.get("plugins")).get(CONTEXT_MODE_PLUGIN)
        plugin = None if registry is None else isinstance(installs, list) and bool(installs)
    depth, concurrency = depth_and_concurrency(settings)
    return {
        "rtk_hook": any(runs(argv, "rtk") and argv[1:3] == ["hook", "claude"]
                        for argv in hook_argvs(hooks.get("PreToolUse"), "Bash")),
        "ai_memory_hook_events": ai_memory_hook_events(hooks),
        "context_mode_plugin_enabled": plugin,
        "subagent_spawn_depth_1": depth,
        "workflow_concurrency_set": concurrency,
        "effort_level_env_unset": EFFORT_VARIABLE not in names and EFFORT_VARIABLE not in env,
        "agent_teams_off": AGENT_TEAMS_VARIABLE not in names and AGENT_TEAMS_VARIABLE not in env,
    }


def codex_hooks_enabled(config) -> bool | None:
    """Codex's lifecycle-hook feature, stable and on by default in 0.155.1. False turns off hooks.json and
    plugin-bundled hooks alike, as disableAllHooks does for Claude; a non-boolean fails Codex's own parse."""
    if config is None:
        return None
    features = config.get("features", {})
    if not isinstance(features, dict):
        return False
    enabled = True
    for key in CODEX_HOOK_FEATURES:
        if key in features:
            if not isinstance(features[key], bool):
                return False
            enabled = features[key]
    return enabled


def instruction_text(text: str) -> str:
    """Instruction text compared by content: whitespace runs collapsed, RTK's ownership comment line dropped."""
    lines = [line for line in text.splitlines() if not line.lstrip().startswith(RTK_OWNED_MARKER)]
    return " ".join(" ".join(lines).split())


def codex_instructions(codex_dir: Path) -> str | None:
    """The global instructions Codex gives the model: AGENTS.override.md when it has non-blank text, else AGENTS.md
    ("" when neither has any). None when either file is unreadable here, since Codex may still read it. Blank is
    decided as Codex decides it, with Rust's str::trim (codex-home/src/instructions/mod.rs at rust-v0.157.1):
    U+001C to U+001F, which Python's str.strip() also removes, make an override Codex sends."""
    for name in CODEX_INSTRUCTION_FILES:
        text = read_client_file(codex_dir / name, "text")
        if text is None or text.strip(RUST_WHITESPACE):
            return text
    return ""


def rtk_instructions_inline(codex_dir: Path) -> bool | None:
    """RTK.md's text appears inline in the instructions Codex loads. A bare "@RTK.md" reference, which is what
    `rtk init -g --codex` writes, is not enough: Codex expands no reference, so the model sees only the path."""
    instructions, rtk = codex_instructions(codex_dir), read_client_file(codex_dir / "RTK.md", "text")
    if instructions is None or rtk is None:
        return None
    body = instruction_text(rtk)
    return bool(body) and body in instruction_text(instructions)


def shared_regex_subset(pattern: str) -> bool:
    """Whether ``pattern`` uses only constructs that Python's re and Rust's regex crate (regex-syntax 0.8.8, which
    Codex 0.157.1 locks) accept and reject alike, so that Python's re.compile decides it as Rust would: literals,
    ".", "^", "$", "|", "(" and "(?:" groups, one "*", "+" or "?" after an atom (then an optional lazy "?"),
    escaped meta characters, \\d \\D \\w \\W \\s \\S, \\a \\f \\t \\n \\r \\v, \\b \\B \\A outside classes, and
    classes of literals, ASCII letter and digit ranges and those escapes. Counted repetition, inline flags, named
    groups, lookaround, backreferences, \\z \\Z \\p \\x \\0, nested classes and a repetition of an assertion or of
    a repetition are not in it: there the engines differ (evidence/artifacts/adoption-status-truth-20260926)."""
    if len(pattern) > REGEX_SUBSET_MAX_LENGTH:
        return False
    index, depth, classes, previous = 0, 0, 0, "start"  # previous: start, atom, assertion, repeat or lazy
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            if index + 1 == len(pattern):
                return True  # a trailing backslash: both engines reject the pattern
            escaped = pattern[index + 1]
            if escaped in REGEX_ASSERTION_ESCAPES:
                previous = "assertion"
            elif escaped in REGEX_META or escaped in REGEX_CONTROL_ESCAPES or escaped in REGEX_CLASS_ESCAPES:
                classes += escaped in REGEX_CLASS_ESCAPES
                previous = "atom"
            else:
                return False
            index += 2
        elif char == "[":
            index += 1 + pattern.startswith("^", index + 1)
            start, letter = index, False  # letter: the previous member is an ASCII letter or digit
            while True:
                if index == len(pattern):
                    return True  # an unclosed class: both engines reject the pattern
                member = pattern[index]
                if member == "]" and index > start:
                    break
                if member in "[]&~" or pattern.startswith("--", index):
                    return False  # nested classes and Rust's set operators && -- ~~
                if member == "\\":
                    escaped = pattern[index + 1:index + 2]
                    if not escaped:
                        return True
                    if not (escaped in REGEX_META or escaped in REGEX_CONTROL_ESCAPES
                            or escaped in REGEX_CLASS_ESCAPES):
                        return False
                    classes += escaped in REGEX_CLASS_ESCAPES
                    index, letter = index + 2, False
                elif member == "-" and index > start and pattern[index + 1:index + 2] != "]":
                    end = pattern[index + 1:index + 2]
                    if not (letter and end.isascii() and end.isalnum()):
                        return False
                    index, letter = index + 2, False  # a range such as a-z
                else:
                    index, letter = index + 1, member.isascii() and member.isalnum()
            index += 1
            classes += 1
            previous = "atom"
        elif char == "(":
            if pattern.startswith("(?", index) and not pattern.startswith("(?:", index):
                return False
            index += 3 if pattern.startswith("(?:", index) else 1
            depth += 1
            if depth > REGEX_SUBSET_MAX_DEPTH:
                return False
            previous = "start"
        elif char in "*+?":
            if char == "?" and previous == "repeat":
                previous = "lazy"
            elif previous in ("atom", "start"):
                previous = "repeat"  # after nothing, both engines reject: "nothing to repeat"
            else:
                return False
            index += 1
        elif char in "{}]":
            return False
        else:
            previous = ("start" if char == "|" else "assertion" if char in "^$" else "atom")
            depth -= char == ")"
            index += 1
    return classes <= REGEX_SUBSET_MAX_CLASSES


def codex_matcher_loads(matcher: str) -> bool | None:
    """validate_matcher_pattern (codex-rs/hooks/src/events/common.rs): "" and "*" match all, a name or a | list of
    ASCII letters, digits and "_" is exact, anything else must compile in Rust's regex crate. None when the matcher
    is outside shared_regex_subset, where Python's re cannot stand in for Rust's."""
    if matcher in ("", "*") or re.fullmatch(r"[A-Za-z0-9_|]*", matcher):
        return True
    if not shared_regex_subset(matcher):
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # FutureWarning on a possible nested set
            re.compile(matcher)
    except (re.error, RecursionError, OverflowError, ValueError):
        return False
    return True


class CodexRejects(ValueError):
    """Codex's own parse of hooks.json fails (or cannot finish), so Codex loads no hook from that file."""


class JsonObject(dict):
    """A JSON object as Codex's serde_json reads it: the dict keeps each key's last value, as serde_json's own maps
    do, and ``pairs`` keeps every pair in order, repeats included, for serde's field checks."""

    def __init__(self, pairs):
        super().__init__(pairs)
        self.pairs = pairs


def reject_constant(_name):
    raise CodexRejects("NaN and Infinity are not JSON")


def parsed_text(value) -> str:
    """A string serde_json parses into Rust text (a field, a key, anything buffered): a lone surrogate fails."""
    if not isinstance(value, str):
        raise CodexRejects("expected text")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise CodexRejects("lone surrogate") from None
    return value


def optional_text(value) -> str | None:
    return None if value is None else parsed_text(value)


def unsigned(value) -> int | None:
    """Option<u64> or Option<usize>: null or a plain JSON integer from 0 to 2^64-1. serde_json's arbitrary_precision
    feature, enabled in Codex's build, keeps any other number as text, which the field refuses."""
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= U64_MAX:
        raise CodexRejects("expected u64")
    return value


def buffered(value, depth: int) -> None:
    """One internally tagged handler, which serde buffers whole before reading its tag: every key and string in it
    is parsed as text, and each array or object in it counts toward serde_json's recursion limit (numbers stay
    arbitrary-precision text, so none is out of range)."""
    if isinstance(value, (list, dict)):
        if depth >= SERDE_JSON_RECURSION_LIMIT:
            raise CodexRejects("recursion limit exceeded")
        for key, item in value.pairs if isinstance(value, JsonObject) else ((None, item) for item in value):
            if key is not None:
                parsed_text(key)
            buffered(item, depth + 1)
    elif isinstance(value, str):
        parsed_text(value)


def serde_struct(value, fields: tuple, *, deny_unknown: bool = False, aliases: dict | None = None) -> dict:
    """A serde-derived struct read from a JSON object, where each key is parsed as text, a repeated field fails and
    an unknown key fails under deny_unknown_fields or is otherwise skipped with its value unparsed; or read from a
    JSON array, which holds the fields in declaration order and may be shorter, but not longer."""
    if isinstance(value, list):
        if len(value) > len(fields):
            raise CodexRejects("trailing characters")
        return dict(zip(fields, value))
    if not isinstance(value, JsonObject):
        raise CodexRejects("expected a struct")
    found = {}
    for key, item in value.pairs:
        name = (aliases or {}).get(parsed_text(key), key)
        if name in fields:
            if name in found:
                raise CodexRejects(f"duplicate field {name}")
            found[name] = item
        elif deny_unknown:
            raise CodexRejects("unknown field")
    return found


def toml_representable(value) -> bool:
    """An MCP hook's input must convert to TOML (deserialize_mcp_tool_input): no null anywhere. Numbers always
    convert, as arbitrary-precision text."""
    if isinstance(value, dict):
        return all(toml_representable(item) for item in value.values())
    if isinstance(value, list):
        return all(toml_representable(item) for item in value)
    return value is not None


def codex_handler(value) -> dict | None:
    """One HookHandlerConfig, tagged by "type" (buffered, then read as its variant), as a dict with its "type" and
    the fields append_matcher_groups uses; None for prompt and agent, which Codex skips."""
    buffered(value, 6)  # file, "hooks", event array, group, its "hooks" array, then this handler
    if isinstance(value, list):  # an array: the tag, then the variant's fields in order
        if not value:
            raise CodexRejects("missing field type")
        tag, fields = value[0], value[1:]
    elif isinstance(value, JsonObject):
        tags = [item for key, item in value.pairs if key == "type"]
        if len(tags) != 1:
            raise CodexRejects("missing or duplicate field type")
        tag, fields = tags[0], JsonObject([(key, item) for key, item in value.pairs if key != "type"])
    else:
        raise CodexRejects("expected a handler")
    if not isinstance(tag, str) or tag not in CODEX_HANDLER_FIELDS:
        raise CodexRejects("expected variant identifier")
    fields = serde_struct(fields, CODEX_HANDLER_FIELDS[tag],
                          aliases={"command_windows": "commandWindows"} if tag == "command" else None)
    if tag == "command":
        handler = {"type": tag, "command": parsed_text(fields.get("command")),
                   "timeout": unsigned(fields.get("timeout")), "async": fields.get("async", False),
                   "statusMessage": optional_text(fields.get("statusMessage")),
                   "additionalContextLimit": unsigned(fields.get("additionalContextLimit"))}
        optional_text(fields.get("commandWindows"))
        if not isinstance(handler["async"], bool):
            raise CodexRejects("expected a boolean")
        return handler
    if tag == "mcp_tool":
        server, tool = parsed_text(fields.get("server")), parsed_text(fields.get("tool"))
        mcp_input = fields.get("input", JsonObject([]))
        if not isinstance(mcp_input, dict) or not toml_representable(mcp_input):
            raise CodexRejects("MCP hook input must be representable as TOML")
        return {"type": tag, "server": server, "tool": tool, "timeout": unsigned(fields.get("timeout")),
                "statusMessage": optional_text(fields.get("statusMessage"))}
    return None


def codex_hook_events(data) -> dict:
    """A hooks.json as Codex parses it (HooksFile, HookEventsToml, MatcherGroup and HookHandlerConfig in
    codex-rs/config/src/hook_config.rs, read by serde_json::from_str), as {event: [(matcher, [handler])]} with
    codex_handler's handlers. Raises CodexRejects where that parse fails, and Codex then loads no hook from it."""
    top = serde_struct(data, CODEX_HOOKS_FILE_FIELDS, deny_unknown=True)
    optional_text(top.get("description"))
    events = {}
    for event, groups in serde_struct(top.get("hooks", JsonObject([])), tuple(CODEX_HOOK_EVENTS)).items():
        if not isinstance(groups, list):
            raise CodexRejects("expected a sequence")
        events[event] = []
        for group in groups:
            fields = serde_struct(group, CODEX_GROUP_FIELDS)
            handlers = fields.get("hooks", [])
            if not isinstance(handlers, list):
                raise CodexRejects("expected a sequence")
            events[event].append((optional_text(fields.get("matcher")), [codex_handler(item) for item in handlers]))
    return events


def codex_hooks_json(text: str) -> dict:
    """Parse hooks.json text as Codex's serde_json does: codex_hook_events of it, or CodexRejects. JSON objects keep
    repeated keys, NaN and Infinity fail, and a skipped value keeps any number."""
    try:
        return codex_hook_events(json.loads(text, object_pairs_hook=JsonObject, parse_constant=reject_constant))
    except CodexRejects:
        raise
    except (ValueError, RecursionError) as error:  # not JSON, or nested deeper than Python parses
        raise CodexRejects(str(error)) from None


def normalized_timeout(event: str, timeout: int | None) -> int:
    """normalize_command_hook: SessionEnd and Interrupt default to 1 s and are clamped to 1-3 s, others default to
    600 s and are at least 1 s."""
    if event in ("SessionEnd", "Interrupt"):
        return min(max(1 if timeout is None else timeout, 1), 3)
    return max(600 if timeout is None else timeout, 1)


def runs_ai_memory_hook(command: str) -> bool:
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    return runs(argv, "ai-memory") and "hook" in argv[1:]


def codex_hook_hashes(source: str, events: dict) -> dict:
    """{key: (event, loads, current hash, runs ai-memory's hook)} for each command handler of one hooks.json whose
    path is ``source``, following discovery.rs append_matcher_groups: a group whose matcher does not compile is
    skipped (loads False; None when codex_matcher_loads cannot tell), as is a blank command. The hash is hook_hash
    through fingerprint.rs version_for_toml: SHA-256 of the normalized identity as compact JSON with sorted keys.
    Raises CodexRejects for a hook Codex cannot hash (a number beyond a TOML integer), on which Codex's hook
    discovery panics and its app-server stops answering."""
    result = {}
    for event, groups in events.items():
        label = CODEX_HOOK_EVENTS[event]
        for group_index, (matcher, handlers) in enumerate(groups):
            matcher = None if event in CODEX_EVENTS_WITHOUT_MATCHER else matcher
            loads = True if matcher is None else codex_matcher_loads(matcher)
            if loads is False:
                continue  # Codex skips the whole group with a warning
            for handler_index, handler in enumerate(handlers):
                if handler is None:
                    continue  # prompt and agent hooks: skipped as unsupported
                if handler["type"] == "mcp_tool":
                    if not (event == "SessionEnd" or not handler["server"].strip(RUST_WHITESPACE)
                            or not handler["tool"].strip(RUST_WHITESPACE)) \
                            and normalized_timeout(event, handler["timeout"]) > I64_MAX:
                        raise CodexRejects("hook identity is not TOML")
                    continue  # an MCP hook runs no command
                if not handler["command"].strip(RUST_WHITESPACE):
                    continue  # skipped before it is normalized or hashed
                timeout = normalized_timeout(event, handler["timeout"])
                limit = handler["additionalContextLimit"] if event in CODEX_CONTEXT_LIMIT_EVENTS else None
                if max(timeout, limit or 0) > I64_MAX:
                    raise CodexRejects("hook identity is not TOML")
                config = {"type": "command", "command": handler["command"], "timeout": timeout,
                          "async": handler["async"]}
                if handler["statusMessage"] is not None:
                    config["statusMessage"] = handler["statusMessage"]
                if limit is not None and limit != CODEX_DEFAULT_CONTEXT_LIMIT:
                    config["additionalContextLimit"] = limit
                identity = {"event_name": label, "hooks": [config]}
                if matcher is not None:
                    identity["matcher"] = matcher
                canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                result[f"{source}:{label}:{group_index}:{handler_index}"] = (
                    event, loads, "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                    runs_ai_memory_hook(handler["command"]))
    return result


def codex_hook_states(config) -> dict:
    """The user config.toml's [hooks.state] as config_rules.rs hook_states_from_stack reads it: keys trimmed as
    Rust's str::trim does, an entry with a wrongly typed field skipped, and "enabled" and "trusted_hash" merged
    field by field."""
    states = {}
    for key, value in table(table(table(config).get("hooks")).get("state")).items():
        key = key.strip(RUST_WHITESPACE)
        if not isinstance(value, dict) or not key:
            continue
        fields = {"enabled": value.get("enabled"), "trusted_hash": value.get("trusted_hash")}
        if not (isinstance(fields["enabled"], (bool, type(None)))
                and isinstance(fields["trusted_hash"], (str, type(None)))):
            continue
        states.setdefault(key, {}).update({name: item for name, item in fields.items() if item is not None})
    return states


def codex_ai_memory_hook_counts(events: dict, config, key_root: str) -> tuple[int, int | None]:
    """(events with an ai-memory hook in hooks.json, events with one Codex runs): enabled, and its [hooks.state]
    trusted_hash equal to its current hash, exactly as discovery.rs hook_enabled and hook_trust_status decide for a
    user (not managed) hook. The second is None when a matcher on an ai-memory hook leaves loading undecided.
    Hashes are compared here and never returned."""
    configured = sum(any(handler is not None and handler["type"] == "command"
                         and runs_ai_memory_hook(handler["command"]) for _, handlers in groups for handler in handlers)
                     for groups in events.values())
    hooks = codex_hook_hashes(f"{key_root}/hooks.json", events)
    if any(loads is None for _, loads, _, ai_memory in hooks.values() if ai_memory):
        return configured, None
    states = codex_hook_states(config)
    return configured, len({event for key, (event, loads, digest, ai_memory) in hooks.items()
                            if ai_memory and loads and states.get(key, {}).get("enabled") is not False
                            and states.get(key, {}).get("trusted_hash") == digest})


def codex_wiring(codex_dir: Path, key_root: str | None = None) -> dict:
    """``key_root`` is the Codex home as Codex spells it in hook keys (client_wiring passes it)."""
    config = read_client_file(codex_dir / "config.toml", "toml")
    engine = codex_hooks_enabled(config)
    hooks_path = codex_dir / "hooks.json"
    text = read_client_file(hooks_path, "text")
    try:  # hooks off: none runs; an absent hooks.json: no hooks; unreadable, or failing Codex's own parse: unknown
        counts = ((None, None) if text is None or engine is None else (0, 0) if not engine else
                  codex_ai_memory_hook_counts(codex_hooks_json(text) if os.path.lexists(hooks_path) else {},
                                              config, key_root or str(codex_dir)))
    except CodexRejects:
        counts = (None, None)
    entry = {} if config is None else table(table(config.get("plugins")).get(CONTEXT_MODE_PLUGIN))
    plugin = None if config is None else entry.get("enabled") is True
    if plugin:  # enabled in config.toml and present in the native plugin cache
        try:
            plugin = any(path.is_file() for path in
                         codex_dir.glob("plugins/cache/context-mode/context-mode/*/.codex-plugin/plugin.json"))
        except OSError:
            plugin = None
    configured, trusted = counts
    return {
        "rtk_instructions": rtk_instructions_inline(codex_dir),
        "context_mode_plugin_enabled": plugin,
        "mcp_servers_present": mcp_servers_present(config),
        "hooks_feature_enabled": engine,
        "ai_memory_hook_events": configured,
        "ai_memory_hook_events_trusted": trusted,
    }


def project_wiring(root: Path) -> dict:
    settings = read_client_file(root / ".claude" / "settings.json", "json")
    return {"settings_depth_and_concurrency": None if settings is None else all(depth_and_concurrency(settings)),
            "codex_mcp_servers_present": mcp_servers_present(read_client_file(root / ".codex" / "config.toml", "toml"))}


def only_flags(value) -> bool:
    """Booleans, counts, None (unreadable) and objects of them: never text read from a file."""
    if value is None or isinstance(value, bool) or (isinstance(value, int) and value >= 0):
        return True
    return isinstance(value, dict) and all(isinstance(key, str) and only_flags(item) for key, item in value.items())


def fixed_wiring(result) -> bool:
    """The exact CLIENT_WIRING_KEYS shape, each server map naming WIRED_MCP_SERVERS, and only flags."""
    if not isinstance(result, dict) or set(result) != set(CLIENT_WIRING_KEYS):
        return False
    if any(not isinstance(result[group], dict) or set(result[group]) != set(keys)
           for group, keys in CLIENT_WIRING_KEYS.items()):
        return False
    servers = (result["project"]["codex_mcp_servers_present"], result["codex"]["mcp_servers_present"])
    return (all(isinstance(item, dict) and set(item) == set(WIRED_MCP_SERVERS) for item in servers)
            and only_flags(result))


def leaves(value) -> list:
    return [leaf for item in value.values() for leaf in leaves(item)] if isinstance(value, dict) else [value]


def wiring_complete(groups: dict) -> bool:
    """The documented rule (docs/token-efficiency-stack.md, "Coverage check"): every file parsed, every boolean
    true with each Codex server named in the user or the project config.toml, both hook counts above zero, and
    every Codex event that runs ai-memory trusted, so Codex actually runs its hook."""
    if None in leaves(groups):
        return False
    claude, project, codex = groups["claude"], groups["project"], groups["codex"]
    servers = all(codex["mcp_servers_present"][name] or project["codex_mcp_servers_present"][name]
                  for name in WIRED_MCP_SERVERS)
    flags = all(value for group in groups.values() for value in group.values() if isinstance(value, bool))
    return (servers and flags and claude["ai_memory_hook_events"] > 0 and codex["ai_memory_hook_events"] > 0
            and codex["ai_memory_hook_events_trusted"] == codex["ai_memory_hook_events"])


def client_wiring(root: Path, env=None) -> dict:
    """Opt-in check that the selected token practice is wired into the native clients.

    Reads the user Claude and Codex homes (CLAUDE_CONFIG_DIR and CODEX_HOME when set) and this
    checkout's project files. Fixed keys only; None marks a file that is unreadable or malformed,
    and "complete" applies the documented rule to the three groups."""
    env = os.environ if env is None else env
    home = env.get("HOME") or str(Path.home())
    codex_home = env.get("CODEX_HOME")
    # Codex's own spelling of its home in hook keys: a set CODEX_HOME canonicalized, else $HOME/.codex as is
    # (codex-rs/utils/home-dir find_codex_home).
    key_root = os.path.realpath(codex_home) if codex_home else os.path.normpath(f"{home}/.codex")
    groups = {"claude": claude_wiring(Path(env.get("CLAUDE_CONFIG_DIR") or f"{home}/.claude"), env),
              "project": project_wiring(root),
              "codex": codex_wiring(Path(codex_home or f"{home}/.codex"), key_root)}
    if not fixed_wiring(groups):
        raise AssertionError("client wiring must be the fixed keys with boolean or count values")
    return {**groups, "complete": wiring_complete(groups)}


def pins_file_path(root: Path, host: dict) -> Path:
    """This catalog's platform pins file (adoption/pins-<os>-<arch>.json), matching each pin's own
    version_probe (#251) against a profile's component_ids. PIN_OS_ALIASES covers a platform.system()
    name this catalog's own pins files spell differently (only "darwin" -> "macos" today)."""
    osname = PIN_OS_ALIASES.get(host["os"], host["os"])
    return root / "adoption" / f"pins-{osname}-{host['architecture']}.json"


def read_pins(path: Path) -> dict:
    """Pin entries by id from a platform pins file; {} when absent, unreadable, oversized or malformed --
    every component is then reported unchecked, the same as one simply missing from a readable file."""
    data = read_client_file(path, "json")
    tools = data.get("tools") if isinstance(data, dict) else None
    if not isinstance(tools, list):
        return {}
    return {entry["id"]: entry for entry in tools
            if isinstance(entry, dict) and isinstance(entry.get("id"), str) and isinstance(entry.get("version"), str)}


def version_at_least(observed: str, floor: str) -> bool:
    """adoption/bootstrap-linux.sh version_at_least: compare dotted parts numerically, padding the
    shorter with 0; any non-numeric part (e.g. "dev0") is not a match rather than an error."""
    observed_parts, floor_parts = observed.split("."), floor.split(".")
    for index in range(max(len(observed_parts), len(floor_parts))):
        observed_part = observed_parts[index] if index < len(observed_parts) else "0"
        floor_part = floor_parts[index] if index < len(floor_parts) else "0"
        if not (observed_part.isdigit() and floor_part.isdigit()):
            return False
        if int(observed_part) != int(floor_part):
            return int(observed_part) > int(floor_part)
    return True


def version_output_matches(expected: str, match: str, output: str) -> bool:
    """The bootstrap scripts' own two match rules (adoption/bootstrap-linux.sh version_output_matches):
    "exact" is the expected text bounded by no adjacent digit or dot (so "2.10" does not match
    "12.10.0"), "minimum" the first dotted number in the output against a numeric floor (a later
    version also passes). Any other rule is not a match."""
    if match == "exact":
        return re.search(r"(^|[^0-9.])" + re.escape(expected) + r"([^0-9.]|$)", output, re.MULTILINE) is not None
    if match == "minimum":
        found = re.search(r"[0-9]+(?:\.[0-9]+)+", output)
        return found is not None and version_at_least(found.group(), expected)
    return False


def signal_group(group: int, signum: int) -> None:
    """Signal a probe's whole process group; a group with nothing left in it is not an error."""
    try:
        os.killpg(group, signum)
    except OSError:  # ProcessLookupError: the group is empty; PermissionError: macOS, zombies only
        pass


def run_version_probe(argv: list[str], seconds: float) -> tuple[int, str] | None:
    """adoption/bootstrap-linux.sh run_version_probe: run ``argv`` with stdin from /dev/null in its own process
    group (a new session), its output going to temporary files, so a descendant that keeps them open cannot
    delay the result. When ``seconds`` pass, TERM goes to the whole group and KILL follows
    PINNED_VERSION_KILL_GRACE_SECONDS later. Whatever is left in the group is killed once the probe exits, and on
    any interruption before it propagates (main() turns SIGINT, SIGTERM and SIGHUP into one unless they are
    ignored, as the bootstrap's EXIT trap stops its probe's group when that script is interrupted). Interruptions
    are held back (held_interrupts) from before the process is created until its group has been killed and
    reaped, except while the probe is waited for (interrupts_released), inside the block whose cleanup kills the
    group. One held back, such as one that arrives between the probe's fork and subprocess.Popen returning it, or
    during the kill, is raised once the group is gone. Returns the exit status and the stdout and stderr text, or
    None on timeout."""
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        with held_interrupts():
            process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                       start_new_session=True)
            try:
                with interrupts_released():
                    try:
                        status = process.wait(timeout=seconds)
                    except subprocess.TimeoutExpired:
                        signal_group(process.pid, signal.SIGTERM)
                        with contextlib.suppress(subprocess.TimeoutExpired):
                            process.wait(timeout=PINNED_VERSION_KILL_GRACE_SECONDS)
                        status = None
            finally:
                signal_group(process.pid, signal.SIGKILL)
                process.wait()
        if status is None:
            return None
        stdout.seek(0)
        stderr.seek(0)
        # Joined by a newline, so the two streams are searched as the bootstrap's grep searches two files.
        return status, "\n".join(stream.read().decode("utf-8", "replace") for stream in (stdout, stderr))


# The interrupt held back by held_interrupts: whether a hold is on, and the first signal that arrived during it.
# Python runs signal handlers in the main thread only, and only the main thread holds, so nothing else reads or
# changes this.
HELD_INTERRUPTS: dict = {"holding": False, "pending": None}


def raise_interrupt(signum: int) -> None:
    """A probe interruption: KeyboardInterrupt for SIGINT, as CPython's own handler raises, else SystemExit with
    status 128 + the signal."""
    if signum == signal.SIGINT:
        raise KeyboardInterrupt
    raise SystemExit(128 + signum)


def interrupt_probe(signum: int, _frame) -> None:
    """The handler signals_interrupt_probes installs: interrupt now, or, during a hold, keep the first signal for
    the hold's end."""
    if HELD_INTERRUPTS["holding"]:
        if HELD_INTERRUPTS["pending"] is None:
            HELD_INTERRUPTS["pending"] = signum
        return
    raise_interrupt(signum)


@contextlib.contextmanager
def held_interrupts():
    """Hold back the interruptions signals_interrupt_probes turns signals into until the block ends, then raise
    the first one that arrived. Outside the main thread, or inside another hold, this changes nothing."""
    if threading.current_thread() is not threading.main_thread() or HELD_INTERRUPTS["holding"]:
        yield
        return
    HELD_INTERRUPTS["pending"] = None  # one left by an earlier hold that was itself interrupted does not carry over
    HELD_INTERRUPTS["holding"] = True
    try:
        yield
    finally:
        HELD_INTERRUPTS["holding"] = False
        signum, HELD_INTERRUPTS["pending"] = HELD_INTERRUPTS["pending"], None
        if signum is not None:
            raise_interrupt(signum)


@contextlib.contextmanager
def interrupts_released():
    """Inside a hold, let interruptions through for the block: one held back so far is raised as the block
    starts, and the hold resumes when the block ends, however it ends. Outside a hold, or outside the main
    thread, this changes nothing."""
    if threading.current_thread() is not threading.main_thread() or not HELD_INTERRUPTS["holding"]:
        yield
        return
    try:
        HELD_INTERRUPTS["holding"] = False
        signum, HELD_INTERRUPTS["pending"] = HELD_INTERRUPTS["pending"], None
        if signum is not None:
            raise_interrupt(signum)
        yield
    finally:
        HELD_INTERRUPTS["holding"] = True


@contextlib.contextmanager
def signals_interrupt_probes():
    """While probes run, SIGINT, SIGTERM and SIGHUP interrupt the check through interrupt_probe: SIGINT still
    raises KeyboardInterrupt, SIGTERM and SIGHUP raise SystemExit (status 128 + the signal), so
    run_version_probe kills the running probe's group on the way out; it holds an interruption back everywhere
    but while it waits for the probe, inside the block whose cleanup kills the group. As CPython installs its
    SIGINT handler only when SIGINT starts at its default action, a signal is changed only while it is at its
    default action (SIG_DFL, or for SIGINT also CPython's default_int_handler), and put back afterwards: one the
    check started with ignored (nohup, or a background job) stays ignored, as bash cannot trap a signal ignored
    on entry, and a handler installed by someone else stays in place. Python accepts signal handlers in the main
    thread only; elsewhere this changes nothing."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    installed = []
    for name in ("SIGINT", "SIGTERM", "SIGHUP"):
        signum = getattr(signal, name, None)
        if signum is None:
            continue
        previous = signal.getsignal(signum)
        if previous == signal.SIG_DFL or (name == "SIGINT" and previous is signal.default_int_handler):
            signal.signal(signum, interrupt_probe)
            installed.append((signum, previous))
    try:
        yield
    finally:
        for signum, previous in installed:
            signal.signal(signum, previous)


def probe_pinned_version(entry: dict) -> dict:
    """One component's pinned-version result. Never execs a probe whose declared method is not "exec": a
    "npm-metadata" method (context-mode) is declared exactly because any other argument starts its MCP
    stdio server, and any future undeclared method is left unchecked the same way."""
    pinned = entry.get("version")
    result = {"pinned_version": pinned if isinstance(pinned, str) else None, "checked": False, "matches_pin": None}
    probe = table(entry.get("version_probe"))
    if probe.get("method") not in SUPPORTED_VERSION_PROBE_METHODS:
        return result
    command, args = probe.get("command"), probe.get("args")
    if not isinstance(command, str) or NAME.fullmatch(command) is None or not isinstance(args, list) \
            or not all(isinstance(item, str) for item in args):
        return result
    resolved = shutil.which(command)
    if resolved is None:
        return result
    expect = probe.get("expect")
    expected = expect if isinstance(expect, str) else pinned
    match = probe.get("match") if probe.get("match") in ("exact", "minimum") else "exact"
    declared_seconds = probe.get("timeout_seconds")
    seconds = declared_seconds if isinstance(declared_seconds, (int, float)) and 0 < declared_seconds <= 300 \
        else PINNED_VERSION_TIMEOUT_SECONDS
    try:
        outcome = run_version_probe([resolved, *args], seconds)
    except (OSError, ValueError):
        return result
    if outcome is None:  # timed out: its process group was killed
        return result
    status, output = outcome
    result["checked"] = True
    # As the bootstrap's "FAILED (exit N)": a failing probe never matches, even if its diagnostics name the pin.
    result["matches_pin"] = status == 0 and isinstance(expected, str) and version_output_matches(expected, match,
                                                                                               output)
    return result


def pinned_versions(component_ids: list[str], pins: dict) -> list[dict]:
    """Opt-in per-component pinned-version result for one profile's component_ids; {} pins (no platform
    file for this host) reports every component unchecked, same as one simply absent from it."""
    return [{"id": identifier, **(probe_pinned_version(pins[identifier]) if identifier in pins else
             {"pinned_version": None, "checked": False, "matches_pin": None})}
            for identifier in component_ids]


def pinned_versions_summary(results: list[dict]) -> dict:
    """One profile's component ids by outcome: matched, mismatched (checked, not the pin) and unchecked."""
    return {"matched": [item["id"] for item in results if item["checked"] and item["matches_pin"]],
            "mismatched": [item["id"] for item in results if item["checked"] and not item["matches_pin"]],
            "unchecked": [item["id"] for item in results if not item["checked"]]}


def pinned_versions_match(profiles: list[dict]) -> bool | None:
    """False when any selected profile has a checked component that differs from its pin, True when at least one
    was checked and none differs, None when nothing could be checked. Unchecked components do not count."""
    summaries = [profile["pinned_versions_summary"] for profile in profiles]
    if any(summary["mismatched"] for summary in summaries):
        return False
    return True if any(summary["matched"] for summary in summaries) else None


def inspect_adoption(manifest: Path, root: Path | None = None, profiles: list[str] | None = None,
                     *, with_client_wiring: bool = False, with_pinned_versions: bool = False, env=None) -> dict:
    manifest = manifest.absolute()
    root = (root or manifest.parent.parent).resolve()
    host = {"os": platform.system().lower(), "architecture": platform.machine().lower(),
            "python": ".".join(str(part) for part in sys.version_info[:3]), "supported": False}
    result = {"schema_version": 1, "status": "prerequisites_missing", "platform": host,
              "manifest": {"status": "invalid"}, "profiles": [], "errors": [],
              "runtime_acceptance_verified": False, "limitations": LIMITATIONS.copy()}
    if with_client_wiring:
        result["client_wiring"] = client_wiring(root, env)
        result["limitations"] = [item for item in result["limitations"]
                                 if item != NO_CLIENT_STATE] + CLIENT_WIRING_LIMITATIONS
    pins = read_pins(pins_file_path(root, host)) if with_pinned_versions else {}
    if with_pinned_versions:
        result["limitations"] = [item for item in result["limitations"]
                                 if item != NO_PINNED_VERSION] + PINNED_VERSION_LIMITATIONS
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
        commands = [{"name": name, "present": command_present(name, host)}
                    for name in profile["required_commands"]]
        recipes = [{"path": reference, "present": recipe_path(root, reference).is_file()}
                   for reference in profile["recipe_paths"]]
        ready = all(item["present"] for item in commands + recipes)
        entry = {"id": identifier, "commands": commands, "recipes": recipes,
                 "status": "prerequisites_present" if ready else "prerequisites_missing"}
        if with_pinned_versions:
            entry["pinned_versions"] = pinned_versions(profile["component_ids"], pins)
            entry["pinned_versions_summary"] = pinned_versions_summary(entry["pinned_versions"])
        result["profiles"].append(entry)
    if with_pinned_versions:
        # Surfaced at the top: a mismatch leaves the prerequisite status and the exit code unchanged.
        result["pinned_versions_match"] = pinned_versions_match(result["profiles"])
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
    parser.add_argument("--client-wiring", action="store_true",
                        help="Also report whether the selected token practice is wired into the native Claude Code "
                             "and Codex clients (fixed booleans, hook-event counts and a computed 'complete' only; "
                             "the exit code is unchanged)")
    parser.add_argument("--pinned-versions", action="store_true",
                        help="Also report, per selected profile, whether each component_id's declared platform "
                             "pin (adoption/pins-<os>-<arch>.json) version_probe observed the pinned version, "
                             "each profile's matched, mismatched and unchecked ids, and a top-level "
                             "pinned_versions_match that is false when any checked component differs from its pin "
                             "(booleans, ids and version strings only; never execs a probe whose declared "
                             "method is not \"exec\", and the exit code is unchanged)")
    args = parser.parse_args(argv)
    with signals_interrupt_probes() if args.pinned_versions else contextlib.nullcontext():
        report = inspect_adoption(args.manifest, args.repo_root, args.profile,
                                  with_client_wiring=args.client_wiring, with_pinned_versions=args.pinned_versions)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report["status"])
        print(f"Manifest: {report['manifest']['status']}; platform supported: {report['platform']['supported']}")
        for profile in report["profiles"]:
            missing = [item["name"] for item in profile["commands"] if not item["present"]]
            missing += [item["path"] for item in profile["recipes"] if not item["present"]]
            print(f"{profile['id']}: {profile['status']}" + (f" (missing: {', '.join(missing)})" if missing else ""))
            if "pinned_versions_summary" in profile:
                summary = profile["pinned_versions_summary"]
                print(f"  pinned versions: {len(summary['matched'])} matched"
                      + (f", mismatched: {', '.join(summary['mismatched'])}" if summary["mismatched"] else "")
                      + (f", unchecked: {', '.join(summary['unchecked'])}" if summary["unchecked"] else ""))
        if "pinned_versions_match" in report:
            print(f"Pinned versions match: {json.dumps(report['pinned_versions_match'])}")
        if "client_wiring" in report:
            wiring = dict(report["client_wiring"])
            print(f"Client wiring complete: {json.dumps(wiring.pop('complete', None))}")
            print("Client wiring: " + json.dumps(wiring, sort_keys=True))
        for error in report["errors"]:
            print(f"Error: {error}")
        for limitation in report["limitations"]:
            print(limitation)
    return 0 if report["status"] == "prerequisites_present" else 2


if __name__ == "__main__":
    raise SystemExit(main())
