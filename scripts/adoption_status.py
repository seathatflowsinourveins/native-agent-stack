#!/usr/bin/env python3
"""Read-only adoption prerequisite report. No installation or runtime acceptance.

Checks command presence with shutil.which; it never invokes those commands. The
only subprocess is a bounded native Git revision query. It opens no credential store
(~/.claude.json, ~/.claude/.credentials.json, ~/.codex/auth.json) and reads no
service/process state, network endpoint or model API. Client configuration is read
only with the opt-in --client-wiring, which parses fixed native client files whole and
in-process and emits no value from them: fixed booleans and hook-event counts only,
never a value, command, path or environment value. The opt-in --pinned-versions execs
a profile's PATH-resolved commands with their platform pin's declared "exec"
version_probe only (never one declared "npm-metadata" or another method, since that
method exists exactly because running the tool starts a server or a UI), each in its
own process group that is killed once the probe exits, times out or is interrupted,
and emits booleans, counts and version strings from the checked-in pins file and the
output of a probe that exited 0.
"""

from __future__ import annotations

import argparse
import contextlib
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
    "--client-wiring parses the user Claude settings and plugin registry, the Codex config.toml, hooks.json and "
    "AGENTS.md, and this checkout's .claude/settings.json and .codex/config.toml whole and in-process, and emits no "
    "value from them: fixed booleans and hook-event counts only. It opens no credential store (~/.claude.json, "
    "~/.claude/.credentials.json, ~/.codex/auth.json), network endpoint or running process; environment variables "
    "only locate the client homes, and two opt-ins are checked by name.",
    "Configured wiring is not activation: managed, project or local Claude settings, and Codex profiles, project "
    "config.toml features and command-line overrides, can override the user scope read here; plugin revisions, hook "
    "and project trust, Claude MCP registrations, MCP server startup and a useful native call remain the clients' "
    "own checks (/mcp, /hooks, the plugin doctor).",
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
CLIENT_FILE_LIMIT = 1_048_576
CLIENT_WIRING_KEYS = {
    "claude": ("rtk_hook", "ai_memory_hook_events", "context_mode_plugin_enabled", "subagent_spawn_depth_1",
               "workflow_concurrency_set", "effort_level_env_unset", "agent_teams_off"),
    "project": ("settings_depth_and_concurrency", "codex_mcp_servers_present"),
    "codex": ("rtk_instructions", "context_mode_plugin_enabled", "mcp_servers_present", "hooks_feature_enabled",
              "ai_memory_hook_events"),
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


def codex_wiring(codex_dir: Path) -> dict:
    config = read_client_file(codex_dir / "config.toml", "toml")
    agents = read_client_file(codex_dir / "AGENTS.md", "text")
    hooks = read_client_file(codex_dir / "hooks.json", "json")
    entry = {} if config is None else table(table(config.get("plugins")).get(CONTEXT_MODE_PLUGIN))
    plugin = None if config is None else entry.get("enabled") is True
    if plugin:  # enabled in config.toml and present in the native plugin cache
        try:
            plugin = any(path.is_file() for path in
                         codex_dir.glob("plugins/cache/context-mode/context-mode/*/.codex-plugin/plugin.json"))
        except OSError:
            plugin = None
    engine = codex_hooks_enabled(config)
    return {
        "rtk_instructions": None if agents is None else "RTK.md" in agents and (codex_dir / "RTK.md").is_file(),
        "context_mode_plugin_enabled": plugin,
        "mcp_servers_present": mcp_servers_present(config),
        "hooks_feature_enabled": engine,
        "ai_memory_hook_events": None if hooks is None or engine is None else
                                 ai_memory_hook_events(hooks.get("hooks")) if engine else 0,
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
    true with each Codex server named in the user or the project config.toml, and both hook counts above zero."""
    if None in leaves(groups):
        return False
    claude, project, codex = groups["claude"], groups["project"], groups["codex"]
    servers = all(codex["mcp_servers_present"][name] or project["codex_mcp_servers_present"][name]
                  for name in WIRED_MCP_SERVERS)
    flags = all(value for group in groups.values() for value in group.values() if isinstance(value, bool))
    return servers and flags and claude["ai_memory_hook_events"] > 0 and codex["ai_memory_hook_events"] > 0


def client_wiring(root: Path, env=None) -> dict:
    """Opt-in check that the selected token practice is wired into the native clients.

    Reads the user Claude and Codex homes (CLAUDE_CONFIG_DIR and CODEX_HOME when set) and this
    checkout's project files. Fixed keys only; None marks a file that is unreadable or malformed,
    and "complete" applies the documented rule to the three groups."""
    env = os.environ if env is None else env
    home = env.get("HOME") or str(Path.home())
    groups = {"claude": claude_wiring(Path(env.get("CLAUDE_CONFIG_DIR") or f"{home}/.claude"), env),
              "project": project_wiring(root),
              "codex": codex_wiring(Path(env.get("CODEX_HOME") or f"{home}/.codex"))}
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
        result["profiles"].append(entry)
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
                             "pin (adoption/pins-<os>-<arch>.json) version_probe observed the pinned version "
                             "(booleans, counts and version strings only; never execs a probe whose declared "
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
            if "pinned_versions" in profile:
                matched = sum(1 for item in profile["pinned_versions"] if item["matches_pin"])
                mismatched = [item["id"] for item in profile["pinned_versions"]
                             if item["checked"] and not item["matches_pin"]]
                unchecked = [item["id"] for item in profile["pinned_versions"] if not item["checked"]]
                print(f"  pinned versions: {matched} matched"
                      + (f", mismatched: {', '.join(mismatched)}" if mismatched else "")
                      + (f", unchecked: {', '.join(unchecked)}" if unchecked else ""))
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
