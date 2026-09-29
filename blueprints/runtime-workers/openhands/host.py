"""Owned lifecycle for the upstream SDK-in-image recipe; no work on import.

Host actions: frozen task checkout/patch transport, supported upstream grader
installation, owned Docker supervision and read-only gateway receipts. Candidate
code executes in worker/grader containers. No installation or execution on import.
"""

from __future__ import annotations

import argparse
import contextlib
import fnmatch
import hashlib
from datetime import datetime, timezone
import json
import io
import ipaddress
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import urllib.request
import uuid

from recipe import (COMPRESSION_COMBOS, HERE, arm_config, digest, environment_selection, llm_config, read_json,
                    render_mcp)
from e2e import netprobe
from e2e.task import load_task, worker_instruction
from receipt import PROBE_MECHANISM, create_receipt, gateway_database, read_bounded, time_value


DOCKER = ["docker", "--context", "rootless"]
# SWE-bench worker default; the resolver mode uses 3740 (README "Workflow dispatch").
DEFAULT_PORT = 3730
# Resolver mode (RESOLVER.md "Stage 2"): its repository, the runtime-worker manifest that pins
# tdd and search-first, and this recipe's resolver skill, which together are its skill set.
RESOLVER_PORT = 3740
RESOLVER_REPOSITORY = "seathatflowsinourveins/native-agent-stack"
RESOLVER_ORIGIN = f"https://github.com/{RESOLVER_REPOSITORY}.git"
RUNTIME_SKILLS_MANIFEST = "blueprints/runtime-workers/skills/manifest.json"
RESOLVER_SKILLS = ("resolver", "search-first", "tdd")
RESOLVER_SKILL_PATH = "blueprints/runtime-workers/openhands/skills/resolver"
# Agent limits whose partial patch is still graded: SDK@fcc102a
# conversation/impl/local_conversation.py:753-755 (STUCK) and :2021-2043,
# :2339-2360 (ERROR with ConversationErrorEvent code "MaxIterationsReached").
AGENT_LIMITS = frozenset({"stuck", "max_iterations_reached"})
# SDK@fcc102a openhands-agent-server/openhands/agent_server/config.py:24 and
# dependencies.py:19 (the header the server checks).
SESSION_KEY_NAME = "OH_SESSION_API_KEYS_0"
SESSION_HEADER = "X-Session-API-Key"
OWNER_KEY, OWNER_VALUE = "com.native-agent-stack.owner", "gpt6-omniroute-framework-integration"
OWNER_LABEL = OWNER_KEY + "=" + OWNER_VALUE
# Every Docker resource of one attempt is named from S = <run-id>-<arm>
# (O1 topology, README "Security posture").
RUN_ID = re.compile(r"rw-openhands-[a-z0-9-]{1,64}")
STEM = re.compile(RUN_ID.pattern + r"-(?:control|engines-on)")
# docker/docs@4e9a5751 content/manuals/engine/network/port-publishing.md:121-131,186-192.
ISOLATED_OPTION = "com.docker.network.bridge.gateway_mode_ipv4"
# Selected fields only. The Docker CLI inspector falls back to the raw JSON
# field names when the typed template fails; checked read-only against this
# host's default bridge network on 2026-09-28 (evidence/phase2-commands.json).
NETWORK_FORMAT = ('{"id":{{json .Id}},"name":{{json .Name}},"driver":{{json .Driver}},'
                  '"internal":{{json .Internal}},"ipv6":{{json .EnableIPv6}},"options":{{json .Options}},'
                  '"labels":{{json .Labels}},"ipam":{{json .IPAM.Config}}}')
# Never a full container inspect: the server's Config.Env holds the session key.
CONTAINER_FORMAT = ('{"id":{{json .Id}},"name":{{json .Name}},"running":{{json .State.Running}},'
                    '"labels":{{json .Config.Labels}},"networks":{{json .NetworkSettings.Networks}}}')
PROXY_TEMPLATE = HERE / "config/proxy-nginx.conf"
PLACEHOLDER = re.compile(r"@[A-Z]+@")
# Plan section 1 and E1: a P0-P2 receipt gates dispatch start for at most 900 s
# and only for the topology whose network and container IDs it records.
PROBE_MAX_AGE_SECONDS = 900
# Plan G7's P3 half, G2 (both image digests scanned and triaged) and G5, as the
# coordinator records them live in <state>/stage-gates.json (repair R6). This
# recipe never writes that file. The engines-on arm also waits for P4 and P5
# (README "P3-P5").
STAGE_GATES = "stage-gates.json"
STAGE_GATES_SCHEMA = "openhands-stage-gates-v1"
STAGE_PROBES = {"control": ("p3",), "engines-on": ("p3", "p4", "p5")}
# Plan G5 (repair R3). OmniRoute@045aa81f3 (20128) and @dd6e9607e (20129),
# whose provider constants and settings helpers are identical: these
# providers are served with a synthetic credential and no provider_connections
# row. No-auth ones (src/shared/constants/providers/noauth.ts, noAuth: true at
# :14,32,51,67,86,100,120,138,162,181) are refused only when
# settings.blockedProviders names their id or alias
# (src/sse/services/auth.ts:1193-1201 at 045aa81f3; noAuthProviderSettings.ts:5-18;
# src/shared/utils/noAuthProviders.ts:19-31). Anonymous-fallback ones
# (anonymousFallback: true at apikey/gateways.ts:741,756,
# apikey/specialty-media.ts:56 and oauth.ts:243) are refused only when
# settings.noAuthFallbackDisabledProviders names them (auth.ts:739-800).
# devin-cli-agentic, auggie and zcode have subprocess executors
# (open-sse/executors/devin-cli-agentic.ts:1, auggie.ts:26, zcodeProtocol.ts:1).
NO_AUTH_PROVIDERS = {"devin-cli-agentic": "dva", "opencode": "oc", "duckduckgo-web": "ddgw",
                     "cloudflare-playground": "cfp", "veoaifree-web": "veo-free", "auggie": "aug", "zcode": "zc",
                     "codex-app-server": "cxa", "uncloseai": "unc", "aihorde": "horde"}
ANONYMOUS_FALLBACK_PROVIDERS = {"opencode-zen": "opencode-zen", "opencode-go": "opencode-go",
                                "pollinations": "pol", "kilocode": "kc"}
# The stores each arm's requests can reach, with the allowlist that applies to
# each: the engines-on gateway forwards to 20128 (README "P3-P5", P4).
GATEWAY_CHAIN = {"control": ("control",), "engines-on": ("engines-on", "control")}
ALLOWLIST_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\*?")


def owned_port(value):
    """Mirror PR #428 crawl4ai host.py:44-45: an exact int (bool refused) in 3730..3799."""
    if type(value) is not int or not 3730 <= value <= 3799:
        raise ValueError("owned_port_3730_3799_required")
    return value


def cli_port(text):
    # Non-decimal text reaches run() unchanged, so preflight refuses it with a receipt.
    return int(text) if re.fullmatch(r"[0-9]{1,5}", text) else text


def private_file(path):
    path = Path(path).absolute()
    info = path.stat()
    if (path.resolve() != path or not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600 or path.is_relative_to(HERE.parents[2])):
        raise ValueError("owned_mode_0600_file_outside_checkout_required")
    return path


def check_server_env(path):
    """Require the session-key variable NAME in the server env file.

    Reads the file and compares only the variable name; the value is never
    logged or returned.

    SDK@fcc102a agent_server/__main__.py:282-285 binds all interfaces only with a
    session API key (config.py:24 names OH_SESSION_API_KEYS_0). Without one the
    server listens on container loopback, which the proxy cannot reach.
    docker/cli@v29.8.1 pkg/kvfile/kvfile.go:92-124 is the --env-file format:
    newline-delimited lines, a BOM dropped on line one, leading whitespace
    trimmed, "#" comments, and the name ends at the first "=". A bare name copies
    the Docker CLI's own environment, so only the NAME= form is accepted.
    """
    path = private_file(path)
    try:
        text = read_bounded(path, limit=64 * 1024)
    except UnicodeDecodeError:
        raise ValueError("server_env_must_be_utf8") from None
    for number, line in enumerate(text.split("\n")):
        if number == 0:
            line = line.removeprefix("\N{BYTE ORDER MARK}")
        # Go unicode.IsSpace: str.isspace() without U+001C..U+001F.
        line = re.sub(r"^[^\S\x1c-\x1f]+", "", line)
        separator = line.find("=")
        if not line.startswith("#") and separator > 0 and line[:separator] == SESSION_KEY_NAME:
            return path
    raise ValueError("server_env_session_key_name_required")


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def write_private_json(path, value):
    """Owner-only (0600) whatever the umask: mkstemp beside the target, then an atomic replace."""
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(json.dumps(value, indent=2) + "\n")
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)
        raise


def private_directory(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError("owned_directory_is_symlink")
    path.chmod(0o700)


def mount(source, target, readonly=True):
    if any(char in str(source) + str(target) for char in (",", "\n", "\r")):
        raise ValueError("unsupported_mount_path")
    return ["--mount", f"type=bind,src={source},dst={target}" + (",readonly" if readonly else "")]


def check_rootless():
    result = subprocess.run(DOCKER + ["info", "--format", "{{json .SecurityOptions}}"],
                            capture_output=True, text=True, check=True, timeout=30)
    if "name=rootless" not in json.loads(result.stdout):
        raise ValueError("rootless_docker_required")


def checked_mount(source, allowed):
    """Resolve before checking; only selected tool/collection roots may be bound."""
    candidate = Path(source)
    if not candidate.is_absolute() or not candidate.is_dir():
        raise ValueError("existing_absolute_directory_required")
    candidate = candidate.resolve()
    home = Path.home().resolve()
    protected = [home / part for part in (".config", ".ssh", ".codex", ".claude", ".aws", ".gnupg",
                                         ".local/share/omniroute", ".local/share/omniroute-fw")]
    protected.append(Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))).resolve())
    if (candidate == home or candidate in home.parents
            or any(candidate == p or candidate.is_relative_to(p) or p.is_relative_to(candidate) for p in protected)
            or any(part in {"credentials", ".ssh", ".codex", ".claude", ".aws", ".gnupg"} for part in candidate.parts)):
        raise ValueError("broad_or_authentication_mount_refused")
    if candidate not in {Path(path).resolve() for path in allowed}:
        raise ValueError("mount_outside_selected_roots")
    return candidate


def selected_mcp_roots(eco):
    # adoption/bootstrap-linux.sh:240,439,457 and pins-linux-x86_64.json.
    return [eco / name for name in (
        "bin", "tools/context-mode-1.0.169", "tools/qmd-2.8.3", "tools/node-24.21.0",
        "python-tools/serena", "python-tools/jcodemunch-mcp",
    )]


def read_host_file():
    """The private OPENHANDS_HOST_FILE: owned, mode 0600, outside the checkout, placeholders filled."""
    private_name = os.environ.get("OPENHANDS_HOST_FILE")
    if not private_name:
        raise ValueError("OPENHANDS_HOST_FILE_required")
    path = Path(private_name).expanduser()
    if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid():
        raise ValueError("private_host_file_must_be_owned_regular_file")
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError("private_host_file_requires_mode_0600")
    if path.resolve().is_relative_to(HERE.parents[2].resolve()):
        raise ValueError("private_host_file_must_be_outside_checkout")
    host = read_json(path)
    if "<" in json.dumps(host):
        raise ValueError("host_file_has_unfilled_placeholders")
    return host


def gateway_allowlists(host):
    """Plan G5: the provider ids each arm's gateway may serve (host file gateway_providers).

    Exactly the two arms, each a non-empty list of lowercase ids, of which only
    a trailing "*" may be a wildcard, so no pattern can match every provider.
    """
    lists = host.get("gateway_providers") if isinstance(host, dict) else None
    if (not isinstance(lists, dict) or set(lists) != {"control", "engines-on"}
            or any(not isinstance(patterns, list) or not patterns
                   or any(not isinstance(pattern, str) or not ALLOWLIST_PATTERN.fullmatch(pattern)
                          for pattern in patterns)
                   for patterns in lists.values())):
        raise ValueError("gateway_provider_allowlists_required")
    return {arm: tuple(patterns) for arm, patterns in lists.items()}


def gateway_surface(database):
    """Plan G5 inputs from one OmniRoute store, read-only (sqlite URI mode=ro and query_only).

    Four statements: the provider column of provider_connections and never a
    credential column (OmniRoute src/lib/db/core.ts:220), the row count of
    the routing combos table (:291-298), and the values of the two named
    settings keys that disable row-less providers. OmniRoute keeps each
    setting as JSON under key_value namespace "settings" (src/lib/db/settings.ts:
    154,283-293). That namespace also holds secrets, so no other key is read.
    A value that is not a JSON list of strings reads as empty, which refuses.
    """
    database = Path(database)
    if not database.is_file() or database.is_symlink():
        raise ValueError("gateway_database_must_be_existing_regular_file")
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=3)
    try:
        connection.execute("PRAGMA query_only = ON")
        providers = sorted({row[0] for row in connection.execute("SELECT provider FROM provider_connections")})
        combos = connection.execute("SELECT count(*) FROM combos").fetchone()[0]
        settings = {}
        for key in ("blockedProviders", "noAuthFallbackDisabledProviders"):
            row = connection.execute("SELECT value FROM key_value WHERE namespace = 'settings' AND key = ?",
                                     (key,)).fetchone()
            try:
                value = json.loads(row[0]) if row else []
            except (TypeError, ValueError):
                value = []
            settings[key] = sorted({item for item in value if isinstance(item, str)}) if isinstance(value, list) else []
    finally:
        connection.close()
    return {"providers": providers, "combos": combos, **settings}


def check_gateway_surface(surface, allowed):
    """Refuse unless every provider this store can serve is in the arm's allowlist.

    Served means a provider_connections row, or a no-auth or anonymous-fallback
    provider that the settings do not disable. Any routing combo is refused:
    its targets are not read. Returns counts only.
    """
    def permitted(provider):
        return isinstance(provider, str) and any(fnmatch.fnmatchcase(provider, pattern) for pattern in allowed)
    if not all(permitted(provider) for provider in surface["providers"]):
        raise ValueError("gateway_provider_outside_allowlist")
    if surface["combos"] != 0:
        raise ValueError("gateway_routing_combo_refused")
    for providers, key, reason in (
            (NO_AUTH_PROVIDERS, "blockedProviders", "gateway_no_auth_provider_not_blocked"),
            (ANONYMOUS_FALLBACK_PROVIDERS, "noAuthFallbackDisabledProviders", "gateway_anonymous_fallback_not_disabled")):
        named = set(surface[key])
        if any(not permitted(provider) and not {provider, alias} & named for provider, alias in providers.items()):
            raise ValueError(reason)
    return {"providers": len(surface["providers"]), "combos": 0}


def verify_gateway_providers(arm, allowlists):
    """Plan G5 at dispatch start: every store the arm's requests can reach (GATEWAY_CHAIN)."""
    for store in GATEWAY_CHAIN[arm_config(arm)["arm"]]:
        check_gateway_surface(gateway_surface(gateway_database(store)), allowlists[store])


def preflight(prefix, state, *, resolver=False):
    pins = read_json(HERE / "pins.json")
    if digest(HERE / "requirements.lock") != pins["requirements_sha256"]:
        raise ValueError("runtime_lock_hash_mismatch")
    if digest(HERE / "build-requirements.lock") != pins["build_requirements_sha256"]:
        raise ValueError("build_lock_hash_mismatch")
    expected_prefix = Path.home() / ".local/share/codex-ecosystem/tools" / ("openhands-" + pins["version"])
    expected_state = Path.home() / ".local/state/native-agent-stack/runtime-workers/openhands"
    if prefix != expected_prefix or state != expected_state:
        raise ValueError("unexpected_owned_prefix")
    for path in (prefix, state):
        if path.resolve() != path:
            raise ValueError("owned_path_must_not_follow_symlinks")
    host = read_host_file()
    gateway_allowlists(host)
    variables = host["variables"]
    if resolver:
        # Resolver mode mounts no MCP server or QMD collection and reaches no memory or
        # embedding service (plan section 5, E4), so none of those entries is read. The
        # request and server containers still take their PATH from HOST_PATH.
        if not isinstance(variables, dict) or not isinstance(variables.get("HOST_PATH"), str) \
                or not variables["HOST_PATH"]:
            raise ValueError("host_path_required")
        check_rootless()
        return pins, host, {}
    # These endpoints belong to the disabled ai-memory and socraticode entries
    # (config/mcp-policy.json). Under O1 they are unreachable by design from
    # the internal run network; the values only keep the template renderable.
    if variables["AI_MEMORY_URL"] != "10.0.2.2:49474":
        raise ValueError("ai_memory_container_endpoint_required")
    if variables["EMBED_URL"] != "10.0.2.2:18232":
        raise ValueError("local_embedder_required")
    if variables["CODE_INDEX_PATH"] != "/state/mcp/jcodemunch":
        raise ValueError("owned_jcodemunch_store_required")
    mcp = render_mcp(variables)
    required = set(read_json(HERE / "config/mcp-policy.json")["qmd"]["collections"])
    if set(host["qmd_collections"]) != required:
        raise ValueError("exact_qmd_collections_required")
    eco = Path(variables["ECO_ROOT"])
    for value in host["mcp_readonly_mounts"]:
        checked_mount(value, selected_mcp_roots(eco))
    stack = Path(os.environ.get("OPENHANDS_STACK_ROOT", str(HERE.parents[2]))).resolve()
    documents = [stack / name for name in ("docs", "adoption", "blueprints/us-equities", "catalogs/us-equities")]
    for value in host["qmd_collections"].values():
        checked_mount(value, documents)
    check_rootless()
    return pins, host, mcp


def install_workspace_skills(stack_root, workspace, manifest=RUNTIME_SKILLS_MANIFEST):
    """Pending shared skills PR: no copy/symlink/global-install fallback.

    Resolver mode passes its own project-scope manifest (install_resolver_skills).
    """
    # Vercel skills 1.7.0 add.ts:2130-2160 also creates a root local lock.
    # A task's existing paths must never become installer-owned or ignored.
    if any(os.path.lexists(workspace / name) for name in (".agents", "skills-lock.json")):
        raise ValueError("task_conflicts_with_skill_installer_paths")
    subprocess.run([
        sys.executable, str(stack_root / "tools/adoption/install_skills.py"),
        "--manifest", str(manifest),
        "--project-dir", str(workspace), "--agent", "universal",
    ], cwd=stack_root, check=True, timeout=600)
    with (workspace / ".git/info/exclude").open("a") as stream:
        stream.write("\n/.agents/\n/skills-lock.json\n")


def workspace_skills(stack_root, workspace):
    manifest = stack_root / "blueprints/runtime-workers/skills/manifest.json"
    entries = read_json(manifest)["skills"]
    installed = workspace / ".agents/skills"
    names = [entry["name"] for entry in entries]
    # verification-before-completion is excluded: the runtime manifest lists it under
    # "excluded" (#429, bdf25d28), and the resolver plan's 2026-09-28 update keeps it out
    # of every container skill set. Requiring it stopped every live prepare here.
    if (len(names) != len(set(names)) or "tdd" not in names
            or "verification-before-completion" in names):
        raise ValueError("runtime_skills_manifest_contract")
    for entry in entries:
        path = installed / entry["name"] / "SKILL.md"
        if not re.fullmatch(r"[a-z0-9-]+", entry["name"]):
            raise ValueError("invalid_skill_name")
        if not path.resolve().is_relative_to(installed.resolve()):
            raise ValueError("skills_must_be_project_local")
        if digest(path) != entry["skill_md_sha256"]:
            raise ValueError("installed_project_skill_pin_mismatch")
    return {"names": sorted(names), "manifest_sha256": digest(manifest)}


SHA1 = re.compile(r"[0-9a-f]{40}")


def resolver_git_env(home):
    """Neutral, anonymous git for the resolver's clones (RESOLVER.md "Stage 2").

    git(1): GIT_CONFIG_GLOBAL and GIT_CONFIG_NOSYSTEM drop the global and system files,
    so no credential helper, hook path or filter can come from them, and
    GIT_TERMINAL_PROMPT=0 fails instead of prompting. HOME is an empty private
    directory, so no per-user file under it applies: no ~/.netrc, and not the XDG git
    ignore and attributes files that tests/__init__.py names. Nothing is inherited.
    """
    return {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(home), "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_NO_REPLACE_OBJECTS": "1"}


def resolver_clone(result, base):
    """Plan section 2 step 2: an anonymous clone of main, pinned to the base, remote removed.

    EXT (OpenHands/extensions@bea7a20 skills/github-issue-to-pr/scripts/main.py:558-592)
    clones one branch over plain HTTPS. History is isolated as run()'s SWE-bench path
    does it: the remote removed, the reflog expired and unreachable objects pruned, so
    the workspace holds main's history up to the base and nothing later. No tag is
    fetched, the credential helper list is empty, and git-clone(1) --template with an
    empty value copies no hook (on git 2.43.0 no .git/hooks is created).
    """
    if not isinstance(base, str) or not SHA1.fullmatch(base):
        raise ValueError("resolver_base_sha_required")
    result = Path(result)
    home = result / "git-home"
    private_directory(home)
    env = resolver_git_env(home)
    workspace = result / "workspace"
    git = ["git", "-c", "credential.helper=", "-c", "core.hooksPath=/dev/null"]
    steps = (("clone", git + ["clone", "--template=", "--no-checkout", "--single-branch", "--branch", "main",
                              "--no-tags", "--", RESOLVER_ORIGIN, str(workspace)]),
             ("checkout", git + ["-C", str(workspace), "reset", "--hard", base]),
             ("remove-remote", git + ["-C", str(workspace), "remote", "remove", "origin"]),
             ("reflog", git + ["-C", str(workspace), "reflog", "expire", "--expire=now", "--all"]),
             ("gc", git + ["-C", str(workspace), "gc", "--prune=now"]))
    for step, argv in steps:
        if logged_command(argv, result / f"resolver-{step}.log", cwd=result, timeout=900, env=env):
            raise RuntimeError("resolver_" + step.replace("-", "_") + "_failed")
    refs = subprocess.check_output(["git", "-C", str(workspace), "for-each-ref", "--format=%(objectname) %(refname)"],
                                   text=True, timeout=30, env=env).splitlines()
    head = subprocess.check_output(["git", "-C", str(workspace), "rev-parse", "HEAD"], text=True, timeout=30,
                                   env=env).strip()
    if refs != [f"{base} refs/heads/main"] or head != base:
        raise ValueError("unexpected_resolver_reference")
    return workspace


def write_agents_md(workspace, base, target):
    """`git show <base>:AGENTS.md` into the read-only input mount (plan section 2 step 4).

    The worker loads it as the always-on "agents" skill. Neutral git, as the clone.
    """
    if not isinstance(base, str) or not SHA1.fullmatch(base):
        raise ValueError("resolver_base_sha_required")
    env = resolver_git_env(Path(workspace).parent / "git-home")
    try:
        text = subprocess.check_output(["git", "-C", str(workspace), "--no-pager", "show", f"{base}:AGENTS.md"],
                                       stderr=subprocess.DEVNULL, timeout=30, env=env)
    except (OSError, subprocess.SubprocessError):
        raise ValueError("agents_md_unreadable") from None
    if len(text) > 1024 * 1024:
        raise ValueError("agents_md_too_large")
    Path(target).write_bytes(text)


def resolver_skill_pin(stack_root):
    """The resolver skill at the driver checkout's commit, pinned as install_skills.py pins every skill.

    The skill states the driver's bounds, so it comes from the commit the driver runs
    from. Its tree and SKILL.md bytes are read from local git at HEAD, never from the
    working tree; install_skills.py then checks the tree against GitHub's Trees API
    before any add, so that commit must be on GitHub (a pushed branch or main).
    """
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

    def git(*args):
        return subprocess.run(["git", "-C", str(stack_root), *args], capture_output=True, env=env, timeout=30,
                              check=True).stdout

    try:
        ref = git("rev-parse", "--verify", "--end-of-options", "HEAD^{commit}").decode("ascii").strip()
        tree = git("rev-parse", "--verify", "--end-of-options", f"{ref}:{RESOLVER_SKILL_PATH}").decode("ascii").strip()
        data = git("cat-file", "blob", f"{ref}:{RESOLVER_SKILL_PATH}/SKILL.md")
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        raise ValueError("resolver_skill_pin_unavailable") from None
    if not SHA1.fullmatch(ref) or not SHA1.fullmatch(tree):
        raise ValueError("resolver_skill_pin_unavailable")
    return {"ref": ref, "tree_sha": tree, "skill_md_sha256": hashlib.sha256(data).hexdigest()}


def resolver_skills_manifest(stack_root, pin):
    """The resolver's project-scope manifest for install_skills.py.

    tdd and search-first are the runtime-worker manifest's entries, unchanged, so the
    installer resolves their reuse_ref against the adoption pins. The resolver entry
    uses the installer's url form (tools/adoption/install_skills.py main's schema check).
    """
    runtime = read_json(Path(stack_root) / RUNTIME_SKILLS_MANIFEST)
    entries = {entry.get("name"): entry for entry in runtime.get("skills", []) if isinstance(entry, dict)}
    if any(name not in entries for name in ("tdd", "search-first")):
        raise ValueError("resolver_skills_missing_from_runtime_manifest")
    resolver = {"name": "resolver", "source": RESOLVER_REPOSITORY,
                "url": f"https://github.com/{RESOLVER_REPOSITORY}/tree/{pin['ref']}/{RESOLVER_SKILL_PATH}",
                "ref": pin["ref"], "path": RESOLVER_SKILL_PATH, "tree_sha": pin["tree_sha"],
                "skill_md_sha256": pin["skill_md_sha256"], "status": "trial"}
    return {"schema_version": runtime["schema_version"], "kind": runtime["kind"], "scope": "project",
            "cli": runtime["cli"], "skills": [entries["tdd"], entries["search-first"], resolver]}


def resolver_workspace_skills(workspace, manifest_path):
    """Exactly the resolver set installed, each SKILL.md at its manifest hash (workspace_skills' checks)."""
    manifest_path = Path(manifest_path)
    entries = read_json(manifest_path)["skills"]
    names = sorted(entry["name"] for entry in entries)
    if tuple(names) != RESOLVER_SKILLS:
        raise ValueError("resolver_skill_set_mismatch")
    installed = Path(workspace) / ".agents/skills"
    if sorted(path.name for path in installed.iterdir()) != names:
        raise ValueError("resolver_installed_skills_mismatch")
    for entry in entries:
        path = installed / entry["name"] / "SKILL.md"
        if not path.resolve().is_relative_to(installed.resolve()):
            raise ValueError("skills_must_be_project_local")
        if digest(path) != entry["skill_md_sha256"]:
            raise ValueError("installed_project_skill_pin_mismatch")
    return {"names": names, "manifest_sha256": digest(manifest_path)}


def check_resolver_skills(stack_root, pin, workdir):
    """install_skills.py --dry-run with the resolver manifest against an empty project directory.

    tools/adoption/install_skills.py main: --dry-run still checks the pinned skills
    binary (verify_skills_bin) and looks up every selected source tree through
    `gh api` before any add, and it adds nothing. resolver.plan_run calls this before
    the attempt exists, so a missing binary or an unpublished pin refuses before the
    run id is spent. Returns the installer's per-skill statuses.
    """
    workdir = Path(workdir)
    manifest, project = workdir / "resolver-skills.json", workdir / "project"
    project.mkdir(mode=0o700)
    write_json(manifest, resolver_skills_manifest(stack_root, pin))
    checked = subprocess.run([sys.executable, str(Path(stack_root) / "tools/adoption/install_skills.py"),
                              "--manifest", str(manifest), "--project-dir", str(project), "--agent", "universal",
                              "--dry-run", "--json"], cwd=stack_root, capture_output=True, text=True, timeout=600,
                             check=False)
    try:
        summary = json.loads(checked.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        summary = {}
    if (checked.returncode != 0 or not isinstance(summary, dict) or summary.get("ok") is not True
            or summary.get("dry_run") is not True or not isinstance(summary.get("skills"), dict)):
        raise ValueError("resolver_skills_unverified")
    return summary["skills"]


def install_resolver_skills(stack_root, workspace, result):
    """tdd, search-first and the resolver skill through install_skills.py in project mode.

    The same path as the SWE-bench mode's set (install_workspace_skills), with the
    manifest written beside the attempt, outside every model mount.
    """
    manifest = Path(result) / "resolver-skills.json"
    write_json(manifest, resolver_skills_manifest(stack_root, resolver_skill_pin(stack_root)))
    install_workspace_skills(stack_root, workspace, manifest=str(manifest))
    return resolver_workspace_skills(workspace, manifest)


def optional_digest(path):
    try:
        return digest(path)
    except OSError:
        return None


def attempt_stem(run_id, arm):
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id) or arm not in {"control", "engines-on"}:
        raise ValueError("owned_attempt_identity_required")
    return run_id + "-" + arm


def network_names(stem):
    if not STEM.fullmatch(stem):
        raise ValueError("owned_attempt_identity_required")
    return {"int": stem + "-int", "gw": stem + "-gw"}


def network_allowed(name, network, installer):
    """Allow no network, the installer's bridge, or the attempt's own network per role.

    Only the agent-server and the P1/P2 probe join <stem>-int; only the P0
    probe joins <stem>-gw. The proxy is created by proxy_commands, not here.
    """
    if network == "none":
        return True
    if installer:
        return network == "bridge" and "-install-" in name
    for kind, roles in (("-int", ("-server", "-probe-int")), ("-gw", ("-probe-gw",))):
        stem = network.removesuffix(kind)
        if network.endswith(kind) and STEM.fullmatch(stem):
            return name in {stem + role for role in roles}
    return False


def docker_args(pins, name, *, network="none", installer=False):
    if not re.fullmatch(r"rw-openhands-[a-z0-9-]+", name):
        raise ValueError("owned_container_name_required")
    limits = read_json(HERE / "config/worker.json")["runtime"]
    if network is False:
        network = "none"
    if not isinstance(network, str) or not network_allowed(name, network, installer):
        raise ValueError("attempt_scoped_network_required")
    args = DOCKER + [
        "run", "--rm", "--pull=never", "--name", name, "--platform", pins["image"]["platform"],
        "--label", OWNER_LABEL,
        "--user", "0:0" if installer else "10001:10001", "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,mode=1777",
        "--tmpfs", "/state/home:rw,nosuid,nodev,mode=0700," + ("uid=0,gid=0" if installer else "uid=10001,gid=10001"),
        "--env", "HOME=/state/home",
        "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "UV_PYTHON_DOWNLOADS=never",
        "--cpus", limits["cpus"], "--memory", limits["memory"], "--pids-limit", str(limits["pids_limit"]),
    ]
    args += ["--network=" + network]
    # Launches built here publish nothing; only the proxy publishes loopback ingress.
    return args


def execute_container(args, name, logfile, timeout):
    """Bound the Docker client and remove exactly its container on every exit."""
    try:
        with logfile.open("w") as log:
            result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=timeout, check=False)
            return result.returncode
    except subprocess.TimeoutExpired:
        return 124
    except OSError:
        return 127
    finally:
        cleanup_container(name, logfile)


def cleanup_container(name, logfile):
    cleanup = {"confirmed_removed": False, "error_type": None}
    try:
        removed = subprocess.run(DOCKER + ["rm", "-f", name], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, check=False, timeout=30)
        if removed.returncode == 0:
            cleanup["confirmed_removed"] = True
        else:
            remaining = subprocess.run(DOCKER + ["ps", "-aq", "--filter", "name=^/" + re.escape(name) + "$"],
                                       capture_output=True, text=True, check=False, timeout=30)
            cleanup["confirmed_removed"] = remaining.returncode == 0 and not remaining.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        cleanup["error_type"] = type(exc).__name__
    write_json(logfile.with_suffix(logfile.suffix + ".cleanup.json"), cleanup)


def logged_command(argv, logfile, *, cwd, timeout, env=None):
    """Private command/exit capture; no claim that exit zero is task success."""
    record = {"argv": list(map(str, argv)), "started_at": utc_now(), "exit_code": None}
    try:
        with logfile.open("w") as log:
            completed = subprocess.run(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT,
                                       timeout=timeout, check=False)
            record["exit_code"] = completed.returncode
    except subprocess.TimeoutExpired:
        record["exit_code"] = 124
    except OSError:
        record["exit_code"] = 127
    finally:
        record["finished_at"] = utc_now()
        write_json(logfile.with_suffix(".command.json"), record)
    return record["exit_code"]


def prepare_grader_image(result, instance_id):
    """Bind the upstream instance tag to a coordinator-frozen registry digest.

    SWE-bench@v4.1.0 test_spec/test_spec.py:106-115 defines this tag. Docker
    SDK@7.1.0 models/resource.py:28-33 provides the independently checked Id.
    The coordinator pre-pulls the digest; grading cannot pull mutable tags.
    """
    raw = read_bounded(os.environ["OPENHANDS_GRADER_IMAGE_FILE"], limit=1024 * 1024)
    expected = os.environ["OPENHANDS_GRADER_IMAGE_SHA256"]
    if hashlib.sha256(raw.encode()).hexdigest() != expected:
        raise ValueError("frozen_grader_image_pin_hash_mismatch")
    pin = json.loads(raw)
    tag = ("swebench/sweb.eval.x86_64." + instance_id.lower() + ":latest").replace("__", "_1776_")
    ref = pin.get("ref", "")
    canonical = ref.removeprefix("docker.io/")
    if (pin.get("instance_id") != instance_id or pin.get("tag") != tag or not pin.get("source")
            or not re.fullmatch(re.escape(tag.removesuffix(":latest")) + r"@sha256:[a-f0-9]{64}", canonical)):
        raise ValueError("frozen_instance_image_required")
    images = json.loads(subprocess.check_output(DOCKER + ["image", "inspect", ref], text=True, timeout=30))
    if len(images) != 1:
        raise ValueError("one_prepulled_image_required")
    info = images[0]
    if (canonical not in [v.removeprefix("docker.io/") for v in info.get("RepoDigests", [])]
            or info.get("Architecture") != "amd64" or info.get("Os") != "linux"
            or not re.fullmatch(r"sha256:[a-f0-9]{64}", info.get("Id", ""))):
        raise ValueError("prepulled_image_identity_mismatch")
    subprocess.run(DOCKER + ["tag", ref, tag], check=True, timeout=30)
    selected = {"ref": ref, "tag": tag, "image_id": info["Id"], "pin_sha256": expected}
    write_json(result / "grader-image.json", selected)
    return selected


def grade(prefix, result, dataset, instance_id, run_id):
    """Upstream conversion, then its unchanged official Docker grading CLI."""
    from e2e.check import check_input, read_report
    grader = prefix / "benchmarks"
    pin = read_json(HERE / "pins.json")["grader"]
    for checkout, expected in ((grader, pin["commit"]),
                               (grader / "vendor/software-agent-sdk", pin["sdk_submodule_commit"])):
        actual = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True, timeout=30).strip()
        if actual != expected:
            raise ValueError("grader_checkout_pin_mismatch")
        if subprocess.check_output(["git", "-C", str(checkout), "status", "--porcelain",
                                    "--untracked-files=no"], text=True, timeout=30).strip():
            raise ValueError("grader_checkout_modified")
    source = result / "output.jsonl"
    check_input(source, instance_id)
    image = prepare_grader_image(result, instance_id)
    # The SDK Docker API uses DOCKER_HOST, not the CLI's --context option.
    endpoint = subprocess.check_output(DOCKER + ["context", "inspect", "rootless", "--format",
                                                 "{{.Endpoints.docker.Host}}"], text=True, timeout=30).strip()
    if not endpoint.startswith("unix://"):
        raise ValueError("rootless_local_docker_endpoint_required")
    environment = {**os.environ, "DOCKER_HOST": endpoint, "PYTHONDONTWRITEBYTECODE": "1",
                   "HF_HOME": str(result / "grader-cache"), "OPENHANDS_GRADER_IMAGE_ID": image["image_id"]}
    convert = [str(grader / ".venv/bin/swebench-eval"), str(source),
               "--dataset", str(dataset), "--run-id", run_id, "--workers", "1",
               "--no-modal", "--skip-evaluation"]
    code = logged_command(convert, result / "convert.log", cwd=result, env=environment, timeout=180)
    if code:
        return {"upstream_resolved": None, "grader_exit_code": None, "conversion_exit_code": code}
    predictions = result / "output.swebench.jsonl"
    converted = [json.loads(line) for line in predictions.read_text().splitlines() if line]
    if (len(converted) != 1 or converted[0].get("instance_id") != instance_id
            or converted[0].get("model_name_or_path") != "OpenHands"
            or not isinstance(converted[0].get("model_patch"), str)):
        raise ValueError("upstream_conversion_scope_mismatch")
    command = [
        str(grader / ".venv/bin/python"), str(HERE / "e2e/docker_grader.py"),
        "--dataset_name", str(dataset), "--predictions_path", str(predictions),
        "--instance_ids", instance_id, "--run_id", run_id, "--max_workers", "1",
        "--split", "test", "--timeout", "1800", "--namespace", "swebench",
        "--cache_level", "instance", "--clean", "false", "--modal", "false",
    ]
    # swebench TestSpec.get_instance_container_name, with our prefix only.
    name = "rw-openhands-sweb.eval." + instance_id.lower() + "." + run_id
    try:
        code = logged_command(command, result / "grader.log", cwd=result, env=environment, timeout=2400)
    finally:
        cleanup_container(name, result / "grader.log")
    report = result / ("OpenHands." + run_id + ".json")
    try:
        relayed = read_report(report, instance_id)
    except (OSError, ValueError, TypeError):
        relayed = {"upstream_resolved": None, "transport_error": "missing_or_malformed_output"}
    return {**relayed, "grader_exit_code": code, "conversion_exit_code": 0,
            "raw_prediction_sha256": digest(source), "converted_prediction_sha256": digest(predictions)}


def download_verified(artifact, target):
    if target.exists():
        if digest(target) != artifact["sha256"]:
            raise ValueError("cached_artifact_hash_mismatch")
        return
    temporary = target.with_suffix(target.suffix + ".partial")
    with urllib.request.urlopen(artifact["url"], timeout=120) as response, temporary.open("wb") as out:
        shutil.copyfileobj(response, out)
    if digest(temporary) != artifact["sha256"]:
        raise ValueError("downloaded_artifact_hash_mismatch")
    temporary.replace(target)


def pinned_image_identity(image):
    """Check the pulled image on the containerd or the classic image store.

    moby docker-v29.8.1 (464cd50c). containerd store: daemon/containerd/
    image_inspect.go:28,71-73,95,97 report the pulled index as Id and
    Descriptor, or the platform manifest when --platform is given. Classic
    store: daemon/images/image_inspect.go:59 reports the config digest
    (daemon/internal/image/store.go:152,160; fs.go:120) and no Descriptor
    (api/swagger.yaml:1839-1850); its pull by index digest verifies the
    platform manifest and records the index reference in RepoDigests
    (daemon/internal/distribution/pull_v2.go:431-434,705-747,845-867). The
    containerd store reports no config digest; there the content-addressed
    platform manifest binds it.
    """
    ref, platform = image["ref"], image["platform"]
    index = "sha256:" + ref.rsplit("@sha256:", 1)[1]
    manifest, config = "sha256:" + image["manifest_sha256"], "sha256:" + image["config_sha256"]
    views = []
    for extra in ([], ["--platform", platform]):
        found = json.loads(subprocess.check_output(DOCKER + ["image", "inspect", *extra, ref], text=True, timeout=30))
        if not isinstance(found, list) or len(found) != 1 or not isinstance(found[0], dict):
            raise ValueError("image_configuration_hash_mismatch")
        views.append(found[0])
    plain, selected = views
    # Primary check: the daemon recorded the exact pinned repository digest.
    if any(ref not in (view.get("RepoDigests") or []) for view in views):
        raise ValueError("image_repo_digest_mismatch")
    image_id = plain.get("Id")
    store = "containerd" if image_id == index else "classic" if image_id == config else None
    if store is None:
        raise ValueError("image_configuration_hash_mismatch")
    if f"{selected.get('Os')}/{selected.get('Architecture')}" != platform:
        raise ValueError("image_platform_manifest_mismatch")
    descriptor = selected.get("Descriptor")
    if store == "containerd":
        if (selected.get("Id") != manifest or not isinstance(descriptor, dict)
                or descriptor.get("digest") != manifest):
            raise ValueError("image_platform_manifest_mismatch")
    elif selected.get("Id") != config:
        raise ValueError("image_configuration_hash_mismatch")
    elif descriptor is not None:
        raise ValueError("image_platform_manifest_mismatch")
    return store


def install(prefix, state):
    pins, _, _ = preflight(prefix, state)
    for directory in (prefix, prefix / "venv", state, state / "cache"):
        private_directory(directory)
    # Source bytes are retained for reproducibility, not executed or patched.
    download_verified(pins["source_archive"], state / "cache/upstream.tar.gz")
    download_verified(pins["uv_lock"], state / "cache/upstream.uv.lock")
    stores = {}
    # The agent-server image, then the pinned gateway proxy image; each is
    # checked before anything else is pulled or any container runs.
    for key in ("image", "gateway_proxy"):
        subprocess.run(DOCKER + ["pull", "--platform", pins[key]["platform"], pins[key]["ref"]], check=True)
        stores[key] = pinned_image_identity(pins[key])
    image_store = stores["image"]
    # A reviewable snapshot, with no repository metadata or host configuration.
    if HERE.resolve() != (prefix / "recipe").resolve():
        shutil.copytree(HERE, prefix / "recipe", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    name = "rw-openhands-install-" + uuid.uuid4().hex[:12]
    args = docker_args(pins, name, installer=True, network="bridge")
    args += install_mounts(prefix, state)
    args += ["--entrypoint", "/bin/bash", pins["image"]["ref"], "/recipe/install-container.sh", str(prefix)]
    private_directory(state / "install-attempts")
    attempt = Path(tempfile.mkdtemp(prefix="attempt-", dir=state / "install-attempts"))
    code = execute_container(args, name, attempt / "install.log", 900)
    write_json(state / "installation.json", {"version": pins["version"], "image": pins["image"]["ref"],
                                            "image_store": image_store,
                                            "gateway_proxy": pins["gateway_proxy"]["ref"],
                                            "gateway_proxy_store": stores["gateway_proxy"],
                                            "requirements_sha256": pins["requirements_sha256"], "exit_code": code})
    if code:
        raise RuntimeError("container_install_failed_see_private_install_log")
    model_visible(prefix / "venv", writable=False)
    subprocess.run(["bash", str(HERE / "install-grader.sh"), str(prefix / "benchmarks"),
                    str(state / "cache")], check=True, timeout=1200)
    print("Installed SDK and pinned upstream grader; model/MCP/E2E acceptance remains pending.")


def runtime_mounts(host):
    args = []
    for source in host["mcp_readonly_mounts"]:
        args += mount(Path(source).resolve(), source)
    for name, source in host["qmd_collections"].items():
        args += mount(Path(source).resolve(), "/documents/" + name)
    return args


def install_mounts(prefix, state):
    return (mount(prefix / "venv", prefix / "venv", False) + mount(state / "cache", "/state/cache", False)
            + mount(prefix / "recipe", "/recipe"))


def inspect_selected(kind, template, name):
    """One `docker <kind> inspect --format` read of selected fields, as JSON."""
    value = json.loads(subprocess.check_output(DOCKER + [kind, "inspect", "--format", template, name],
                                               text=True, timeout=30))
    if not isinstance(value, dict):
        raise ValueError("unexpected_inspect_shape")
    return value


def checked_network(name, kind):
    """Read one attempt network back and require its contract (plan E1)."""
    info = inspect_selected("network", NETWORK_FORMAT, name)
    internal = kind == "int"
    if (info.get("name") != name or info.get("driver") != "bridge" or info.get("internal") is not internal
            or info.get("ipv6") is not False or (info.get("labels") or {}).get(OWNER_KEY) != OWNER_VALUE
            or not re.fullmatch(r"[a-f0-9]{64}", str(info.get("id")))
            or (internal and (info.get("options") or {}).get(ISOLATED_OPTION) != "isolated")):
        raise ValueError(f"attempt_{kind}_network_contract_mismatch")
    return info


def create_topology(result, stem):
    """Create the attempt's internal and gateway networks; fail closed.

    docker/docs@4e9a5751 content/manuals/engine/network/port-publishing.md:
    186-192: containers on an internal network can reach host services through
    the bridge address, including services listening on all host addresses;
    no address is assigned to the bridge with gateway mode isolated (options
    :121-131). A rejected option is never retried without it.
    """
    names = network_names(stem)
    commands = {
        "int": ["network", "create", "--internal", "--ipv6=false", "-o", ISOLATED_OPTION + "=isolated",
                "--label", OWNER_LABEL, names["int"]],
        "gw": ["network", "create", "--ipv6=false", "--label", OWNER_LABEL, names["gw"]],
    }
    for kind in ("int", "gw"):
        if logged_command(DOCKER + commands[kind], result / f"network-{kind}-create.log", cwd=result, timeout=60):
            raise RuntimeError(f"attempt_{kind}_network_create_failed")
    return {kind: checked_network(names[kind], kind) for kind in ("int", "gw")}


def session_files(state, run_id, arm):
    """The attempt's key files under the state root, derived from its identity only."""
    stem = attempt_stem(run_id, arm)
    directory = Path(state) / "secrets"
    return directory / (stem + ".server.env"), directory / (stem + ".headers")


def generate_session_files(state, run_id, arm, *, sink=None):
    """Generate this attempt's agent-server key; return the two paths, never the value.

    One value from Python's secrets module goes into <stem>.server.env in
    docker env-file syntax (NAME=value, docs.docker.com container run
    --env-file) and into <stem>.headers for curl -H @file. Each file is created
    with O_CREAT|O_EXCL|O_NOFOLLOW at 0600, so an existing file or a planted
    symlink is refused. teardown_attempt deletes both after confirmed removal.
    Resolver mode passes `sink`, which receives the value in memory once both
    files exist: the outgoing-text guard's session key (RESOLVER.md "Stage 2").
    """
    paths = session_files(state, run_id, arm)
    private_directory(paths[0].parent)
    value = secrets.token_urlsafe(32)
    for path, line in zip(paths, (f"{SESSION_KEY_NAME}={value}\n", f"{SESSION_HEADER}: {value}\n")):
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(line)
    if sink is not None:
        sink(value)
    return paths


def render_proxy_config(selection, run_id):
    """Fill config/proxy-nginx.conf for one attempt; refuse anything unexpected.

    The selection must equal what arm_config returns for its own fields, so a
    cross-arm pairing or an unrecorded compression combo cannot be rendered,
    and every value must match its own pattern before substitution.
    """
    checked = arm_config(selection.get("arm"), selection.get("requested_model"), selection.get("base_url"),
                         selection.get("compression_combo"))
    if checked != selection:
        raise ValueError("proxy_selection_mismatch")
    stem = attempt_stem(run_id, checked["arm"])
    values = {"@PORT@": str(checked["gateway_port"]), "@SERVER@": stem + "-server", "@RUN@": run_id,
              "@COMPRESSION@": checked["compression_combo"] or ""}
    patterns = {"@PORT@": r"2012[89]", "@SERVER@": STEM.pattern + "-server", "@RUN@": RUN_ID.pattern,
                "@COMPRESSION@": "|".join(map(re.escape, sorted(COMPRESSION_COMBOS))) + "|"}
    text = PROXY_TEMPLATE.read_text()
    found = PLACEHOLDER.findall(text)
    if set(found) != set(values) or text.count("@") != 2 * len(found):
        raise ValueError("proxy_template_placeholders_changed")
    for key, value in values.items():
        if not re.fullmatch(patterns[key], value):
            raise ValueError("proxy_value_outside_pattern")
        text = text.replace(key, value)
    return text


def write_proxy_config(result, text):
    """Host-owned 0644 file outside every model mount: <result>/proxy/nginx.conf."""
    directory = result / "proxy"
    private_directory(directory)
    path = directory / "nginx.conf"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(descriptor, "w") as stream:
        # umask 077 would leave 0600; the image's non-root user reads the bind mount.
        os.fchmod(stream.fileno(), 0o644)
        stream.write(text)
    return path, digest(path)


def proxy_commands(pins, stem, config, port):
    """Create on <stem>-gw with loopback ingress, join <stem>-int as "gw", start.

    A created container joins its configured networks when it runs, and
    network connect --alias adds a network-scoped name (docs.docker.com
    container run and network connect, fetched 2026-09-28). Starting after the
    connect lets nginx resolve <stem>-server when it loads. --entrypoint nginx
    bypasses the image's entrypoint scripts, unprobed under --read-only.
    """
    image, names = pins["gateway_proxy"], network_names(stem)
    name = stem + "-proxy"
    create = DOCKER + [
        "create", "--pull=never", "--name", name, "--platform", image["platform"], "--label", OWNER_LABEL,
        "--network=" + names["gw"], "--publish", f"127.0.0.1:{owned_port(port)}:8080",
        "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,mode=1777", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--pids-limit", "64", "--memory", "256m",
        *mount(config, "/etc/nginx/nginx.conf"), "--entrypoint", "nginx", image["ref"], "-g", "daemon off;",
    ]
    return create, DOCKER + ["network", "connect", "--alias", "gw", names["int"], name], DOCKER + ["start", name]


def launch_proxy(result, pins, stem, config, port):
    for step, argv in zip(("create", "connect", "start"), proxy_commands(pins, stem, config, port)):
        if logged_command(argv, result / f"proxy-{step}.log", cwd=result, timeout=60):
            raise RuntimeError(f"proxy_{step}_failed")


def cleanup_network(name, record):
    """Remove one network by exact name; confirm by exact membership in network ls."""
    cleanup = {"confirmed_removed": False, "error_type": None}
    try:
        subprocess.run(DOCKER + ["network", "rm", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=False, timeout=30)
        listed = subprocess.run(DOCKER + ["network", "ls", "--format", "{{.Name}}"], capture_output=True,
                                text=True, check=False, timeout=30)
        cleanup["confirmed_removed"] = listed.returncode == 0 and name not in listed.stdout.splitlines()
    except (OSError, subprocess.TimeoutExpired) as exc:
        cleanup["error_type"] = type(exc).__name__
    write_json(record, cleanup)
    return cleanup["confirmed_removed"]


def teardown_attempt(state, run_id, arm):
    """Remove the attempt's proxy, server and networks by exact name; never prune.

    Container logs go to private files first (the proxy access log is the
    denied-path evidence). The key files are deleted only after both
    containers are confirmed removed. True only if all four are confirmed.
    """
    stem = attempt_stem(run_id, arm)
    result = Path(state) / "runs" / run_id / arm
    containers = []
    for role in ("proxy", "server"):
        name, logfile = f"{stem}-{role}", result / f"{role}.log"
        try:
            logged_command(DOCKER + ["logs", name], logfile, cwd=result, timeout=30)
        finally:
            cleanup_container(name, logfile)
        record = read_json(logfile.with_suffix(logfile.suffix + ".cleanup.json"))
        containers.append(record.get("confirmed_removed") is True)
    networks = [cleanup_network(name, result / f"network-{kind}.cleanup.json")
                for kind, name in network_names(stem).items()]
    if all(containers):
        for path in session_files(state, run_id, arm):
            path.unlink(missing_ok=True)
    return all(containers) and all(networks)


def listener_ports(text):
    """TCP listener ports from `ss -ltnH` (iproute2); the fourth column is Local-Address:Port."""
    ports = set()
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        port = fields[3].rsplit(":", 1)[-1] if len(fields) >= 5 and fields[0] == "LISTEN" else ""
        if not re.fullmatch(r"[0-9]{1,5}", port) or not 0 < int(port) < 65536:
            raise ValueError("unexpected_ss_output")
        ports.add(int(port))
    return sorted(ports)


def host_ipv4_addresses(text):
    """Host IPv4 addresses from `ip -4 -o addr`, loopback excluded by address.

    127.0.0.0/8 inside the probe is the container's own loopback, not the
    host's. Other addresses on lo (WSL's 10.255.255.254) stay.
    """
    found = set()
    for line in text.splitlines():
        fields = line.split()
        if "inet" not in fields:
            continue
        position = fields.index("inet") + 1
        if position >= len(fields):
            raise ValueError("unexpected_ip_output")
        address = ipaddress.IPv4Interface(fields[position]).ip
        if not address.is_loopback:
            found.add(address)
    return [str(address) for address in sorted(found)]


ATTEMPT_ROLES = ("server_int", "proxy_int", "proxy_gw")


def ipv4_entries(network):
    entries = [entry for entry in network.get("ipam") or []
               if isinstance(entry, dict) and ":" not in str(entry.get("Subnet", ""))]
    if not entries:
        raise ValueError("attempt_network_ipam_required")
    return entries


def ipv4_subnets(network):
    """The network's IPv4 subnets as strict CIDR strings, from its selected-field IPAM view."""
    return [str(ipaddress.IPv4Network(entry["Subnet"])) for entry in ipv4_entries(network)]


def probe_targets(networks, listeners, interfaces, attempt_addresses):
    """P2 targets (plan section 1): addresses times ports, both sorted and deduplicated.

    Addresses: netprobe.FIXED_ADDRESSES, every non-loopback host IPv4 address
    and each gateway the attempt networks' IPAM actually records. The isolated
    $S-int records none: moby@464cd50c (docker-v29.8.1) skips gateway
    allocation in isolated mode (daemon/libnetwork/drivers/bridge/
    bridge_linux.go:700-713, network.go:1594-1602), so its first endpoint, the
    server, holds the subnet's .1. The attempt containers' own addresses are
    removed: a connect there reaches the attempt, not the host. The roles
    removed are returned so the receipt can record them; they never cause a
    refusal. Ports: every host TCP listener at probe time plus
    netprobe.EXTRA_PORTS (53).
    """
    if set(attempt_addresses) != set(ATTEMPT_ROLES):
        raise ValueError("attempt_container_addresses_required")
    own = {role: ipaddress.IPv4Address(attempt_addresses[role]) for role in ATTEMPT_ROLES}
    addresses = {ipaddress.IPv4Address(value) for value in netprobe.FIXED_ADDRESSES}
    addresses |= {ipaddress.IPv4Address(value) for value in host_ipv4_addresses(interfaces)}
    for kind in ("int", "gw"):
        for entry in ipv4_entries(networks[kind]):
            ipaddress.IPv4Network(entry["Subnet"])
            if entry.get("Gateway"):
                addresses.add(ipaddress.IPv4Address(entry["Gateway"]))
    excluded = [role for role in ATTEMPT_ROLES if own[role] in addresses]
    addresses -= set(own.values())
    ports = sorted(set(listener_ports(listeners)) | set(netprobe.EXTRA_PORTS))
    return [str(address) for address in sorted(addresses)], ports, excluded


def checked_container(name, networks, aliases=None):
    """Read one attempt container through CONTAINER_FORMAT and require its attachments.

    moby@464cd50c api/swagger.yaml: the name "may be prefixed with a
    forward-slash" (:5637-5643); EndpointSettings.Aliases holds the
    network-scoped aliases (:3369-3375) and NetworkID binds each attachment
    to its network (:3400). Never a full inspect: the server's Config.Env
    holds the session key.
    """
    info = inspect_selected("container", CONTAINER_FORMAT, name)
    attached = info.get("networks") if isinstance(info.get("networks"), dict) else {}
    labels = info.get("labels") if isinstance(info.get("labels"), dict) else {}
    if (info.get("name") not in (name, "/" + name) or info.get("running") is not True
            or labels.get(OWNER_KEY) != OWNER_VALUE or not re.fullmatch(r"[a-f0-9]{64}", str(info.get("id")))
            or set(attached) != set(networks)
            or any(not isinstance(attached[network], dict) or attached[network].get("NetworkID") != identity
                   for network, identity in networks.items())
            or any(alias not in (attached[network].get("Aliases") or [])
                   for network, alias in (aliases or {}).items())):
        raise ValueError("attempt_container_contract_mismatch")
    return info


def attempt_bindings(stem):
    """Live selected-field reads of the attempt's two networks and two containers."""
    names = network_names(stem)
    networks = {kind: checked_network(names[kind], kind) for kind in ("int", "gw")}
    server = checked_container(stem + "-server", {names["int"]: networks["int"]["id"]})
    proxy = checked_container(stem + "-proxy", {names["gw"]: networks["gw"]["id"], names["int"]: networks["int"]["id"]},
                              aliases={names["int"]: "gw"})
    return networks, server, proxy


def probe_command(pins, prefix, stem, role, output, arguments):
    """e2e/netprobe.py in the pinned agent image, with docker_args hardening and three mounts only.

    The venv, /recipe read-only and this container's own output directory:
    no workspace, server state, key file or published port.
    """
    if role not in ("gw", "int"):
        raise ValueError("probe_role_required")
    name = f"{stem}-probe-{role}"
    args = docker_args(pins, name, network=network_names(stem)[role])
    args += (mount(Path(prefix) / "venv", Path(prefix) / "venv") + mount(HERE, "/recipe")
             + mount(output, "/probe-output", False))
    args += ["--entrypoint", str(Path(prefix) / "venv/bin/python"), pins["image"]["ref"],
             "/recipe/e2e/netprobe.py", role, "--out", "/probe-output/observations.json", *arguments]
    return name, args


def run_probe(state, run_id, arm, prefix, pins):
    """Run P0 on <stem>-gw, then P1 and P2 on <stem>-int; True only if everything passes.

    The attempt must be prepared, its rendered proxy config unchanged, and
    its networks and containers must pass the live contract reads. P0 is the
    negative control: if it fails, P1 and P2 do not run. The verdict is
    re-derived from the observation files with netprobe.evaluate and also
    needs both exit codes to be 0. <result>/isolation-probe.json is written
    at 0600 whether or not the probe passes; it holds counts and IDs, never
    host addresses.
    """
    stem = attempt_stem(run_id, arm)
    result = Path(state) / "runs" / run_id / arm
    status = json.loads(read_bounded(result / "status.json"))
    if (not isinstance(status, dict) or status.get("status") != "prepared" or status.get("run_id") != run_id
            or status.get("arm") != arm):
        raise ValueError("prepared_attempt_required")
    port = owned_port(status.get("port"))
    upstream = arm_config(arm)["gateway_port"]
    config = digest(result / "proxy/nginx.conf")
    if status.get("proxy_config_sha256") != config:
        raise ValueError("proxy_config_changed_since_prepare")
    networks, server, proxy = attempt_bindings(stem)
    internal, gateway = networks["int"]["name"], networks["gw"]["name"]
    own = {"server_int": server["networks"][internal].get("IPAddress"),
           "proxy_int": proxy["networks"][internal].get("IPAddress"),
           "proxy_gw": proxy["networks"][gateway].get("IPAddress")}
    listeners = subprocess.check_output(["ss", "-ltnH"], text=True, timeout=30)
    interfaces = subprocess.check_output(["ip", "-4", "-o", "addr"], text=True, timeout=30)
    # An attempt container's own address is no host target; it is excluded and
    # recorded by role (repair R2), never a reason to refuse.
    addresses, ports, excluded = probe_targets(networks, listeners, interfaces, own)
    subnets = ipv4_subnets(networks["int"])
    private_directory(result / "probes")
    directory = Path(tempfile.mkdtemp(prefix="probe-", dir=result / "probes"))
    arguments = {"gw": ["--upstream-port", str(upstream)],
                 "int": ["--server", stem + "-server", "--addresses", ",".join(addresses),
                         "--ports", ",".join(map(str, ports)), "--subnets", ",".join(subnets)]}
    observed, codes = {"gw": None, "int": None}, {"gw": None, "int": None}
    for role in ("gw", "int"):
        output = directory / role
        output.mkdir(mode=0o700)
        model_visible(output, writable=True)
        name, argv = probe_command(pins, prefix, stem, role, output, arguments[role])
        codes[role] = execute_container(argv, name, directory / (role + ".log"), 300)
        with contextlib.suppress(OSError, ValueError):
            observed[role] = json.loads(read_bounded(output / "observations.json"))
        if role == "gw" and (codes["gw"] != 0 or not netprobe.evaluate_http(
                observed["gw"].get("p0") if isinstance(observed["gw"], dict) else None,
                netprobe.p0_expected(upstream))["passed"]):
            break
    verdict = netprobe.evaluate(observed["gw"], observed["int"], upstream, addresses, ports, stem + "-server",
                                subnets)
    passed = verdict["passed"] and codes == {"gw": 0, "int": 0}
    write_private_json(result / "isolation-probe.json", {
        "mechanism": PROBE_MECHANISM, "run_id": run_id, "arm": arm,
        "run_network_id": networks["int"]["id"], "gw_network_id": networks["gw"]["id"],
        "server_container_id": server["id"], "proxy_container_id": proxy["id"],
        "proxy_image": pins["gateway_proxy"]["ref"], "proxy_config_sha256": config,
        "probe_script_sha256": digest(HERE / "e2e/netprobe.py"),
        "upstream": f"{netprobe.GATEWAY_HOST}:{upstream}", "host_ingress": f"127.0.0.1:{port}",
        "verified_at": utc_now(), "exit_codes": codes,
        "targets": {"addresses": len(addresses), "ports": ports, "pairs": len(addresses) * len(ports),
                    "excluded": {role: 1 for role in excluded}},
        "p0": verdict["p0"], "p1": verdict["p1"], "p2": verdict["p2"], "passed": passed,
    })
    return passed


def checked_probe_counts(receipt, upstream_port):
    """Re-derive the probe verdict from the recorded counts; a passed flag alone is not evidence.

    Requires both probe exit codes 0, fully observed and matched P0 and P1,
    a non-empty target set whose pair count is addresses times ports, and a
    P2 in which every pair was observed and failed with a named error, every
    off-subnet pair failed for want of a route, the positive control
    connected, the DNS datagram got no answer, every expected name matched,
    and no IPv6 address, default route or gateway route was found. Any
    contradiction refuses.
    """
    section = {name: receipt.get(name) if isinstance(receipt.get(name), dict) else {}
               for name in ("p0", "p1", "p2", "targets")}
    p2, targets = section["p2"], section["targets"]
    addresses, ports, pairs = targets.get("addresses"), targets.get("ports"), targets.get("pairs")
    errors = p2.get("errors") if isinstance(p2.get("errors"), dict) else {}
    off_subnet = p2.get("off_subnet")
    consistent = (
        receipt.get("exit_codes") == {"gw": 0, "int": 0}
        and all(section[name].get("requests") == section[name].get("observed") == section[name].get("matched")
                == expected and section[name].get("passed") is True
                for name, expected in (("p0", len(netprobe.p0_expected(upstream_port))),
                                       ("p1", len(netprobe.P1_EXPECTED))))
        and type(addresses) is int and addresses > 0 and isinstance(ports, list) and bool(ports)
        and all(type(value) is int for value in ports) and pairs == addresses * len(ports)
        and p2.get("connects") == p2.get("observed") == pairs and p2.get("connected") == 0
        and all(type(value) is int for value in errors.values()) and sum(errors.values()) == pairs
        and type(off_subnet) is int and 0 < off_subnet <= pairs and p2.get("off_subnet_unreachable") == off_subnet
        and p2.get("control_connected") is True and p2.get("udp_answered") is False
        and p2.get("dns") == p2.get("dns_matched") == len(netprobe.UNRESOLVABLE) + 2
        and p2.get("ipv6_non_loopback") == 0 and p2.get("routes_available") is True
        and p2.get("default_routes") == 0 and p2.get("gateway_routes") == 0 and p2.get("passed") is True)
    if not consistent:
        raise ValueError("isolation_probe_contradiction")
    return receipt


def recorded(entry, now, **fields):
    """A stage-gate entry: passed, recorded no later than now, and carrying these exact fields."""
    if not isinstance(entry, dict) or entry.get("passed") is not True:
        return False
    if any(entry.get(key) != value for key, value in fields.items()):
        return False
    try:
        return time_value(entry.get("recorded_at")) <= now
    except (ValueError, TypeError, OverflowError, OSError):
        return False


def verify_stage_gates(state, arm, *, now):
    """The coordinator's live records that code cannot observe (repair R6).

    <state>/stage-gates.json must be an owner-only regular file outside the
    checkout. It must hold passed G2 scans of both pinned image references
    and each STAGE_PROBES entry for this arm, recorded under the pinned proxy
    image and the current proxy template, with the gateway build it ran on.
    It must also hold this arm's G5 record. Only the declared build is kept;
    this check cannot tell which build is running. The file stays absent
    until the gates are observed, so dispatch start refuses until then.
    """
    arm_config(arm)
    path = Path(state) / STAGE_GATES
    if not path.exists():
        raise ValueError("stage_gates_not_recorded")
    gates = json.loads(read_bounded(private_file(path), limit=1024 * 1024))
    if not isinstance(gates, dict) or gates.get("schema") != STAGE_GATES_SCHEMA:
        raise ValueError("stage_gates_schema")
    pins = read_json(HERE / "pins.json")
    scans = gates.get("g2") if isinstance(gates.get("g2"), dict) else {}
    if not all(recorded(scans.get(ref), now) for ref in (pins["image"]["ref"], pins["gateway_proxy"]["ref"])):
        raise ValueError("stage_gate_g2_not_recorded")
    probes = gates.get("probes") if isinstance(gates.get("probes"), dict) else {}
    template = digest(PROXY_TEMPLATE)
    if not all(recorded(probes.get(name), now, proxy_image=pins["gateway_proxy"]["ref"],
                        proxy_template_sha256=template)
               and re.fullmatch(r"[0-9a-f]{7,40}", str(probes[name].get("gateway_build")))
               for name in STAGE_PROBES[arm]):
        raise ValueError("stage_gate_probe_not_recorded")
    surfaces = gates.get("g5") if isinstance(gates.get("g5"), dict) else {}
    if not recorded(surfaces.get(arm), now):
        raise ValueError("stage_gate_g5_not_recorded")
    return gates


def verify_isolation(state, run_id, arm, port, *, now=None):
    """The dispatch-start gate (plan E1, G7): a fresh passed probe bound to the live attempt.

    Refuses unless <result>/isolation-probe.json is an owner-only regular file
    written at most PROBE_MAX_AGE_SECONDS ago, for this arm's upstream, this
    ingress port, the pinned proxy image, the rendered config and this probe
    script, whose counts re-derive a pass (checked_probe_counts); unless the
    coordinator's stage gates are recorded (verify_stage_gates); unless every
    provider the arm's gateway stores can serve is allowlisted in the host file
    (verify_gateway_providers, plan G5); and unless the live network and
    container IDs still match. File, time and read-only store checks come
    before any Docker read. A pure check: it changes nothing.
    """
    stem = attempt_stem(run_id, arm)
    now = now or datetime.now(timezone.utc)
    result = Path(state) / "runs" / run_id / arm
    receipt = json.loads(read_bounded(private_file(result / "isolation-probe.json"), limit=1024 * 1024))
    if not isinstance(receipt, dict):
        raise ValueError("isolation_probe_receipt_shape")
    age = (now - time_value(receipt.get("verified_at"))).total_seconds()
    if not 0 <= age <= PROBE_MAX_AGE_SECONDS:
        raise ValueError("isolation_probe_not_fresh")
    status = json.loads(read_bounded(result / "status.json"))
    config = digest(result / "proxy/nginx.conf")
    upstream = arm_config(arm)["gateway_port"]
    expected = {"mechanism": PROBE_MECHANISM, "run_id": run_id, "arm": arm,
                "upstream": f"{netprobe.GATEWAY_HOST}:{upstream}",
                "host_ingress": f"127.0.0.1:{owned_port(port)}",
                "proxy_image": read_json(HERE / "pins.json")["gateway_proxy"]["ref"],
                "proxy_config_sha256": config, "probe_script_sha256": digest(HERE / "e2e/netprobe.py"),
                "passed": True}
    if (any(receipt.get(key) != value for key, value in expected.items())
            or not isinstance(status, dict) or status.get("proxy_config_sha256") != config
            or any(not isinstance(receipt.get(section), dict) or receipt[section].get("passed") is not True
                   for section in ("p0", "p1", "p2"))):
        raise ValueError("isolation_probe_mismatch")
    checked_probe_counts(receipt, upstream)
    verify_stage_gates(state, arm, now=now)
    verify_gateway_providers(arm, gateway_allowlists(read_host_file()))
    networks, server, proxy = attempt_bindings(stem)
    live = {"run_network_id": networks["int"]["id"], "gw_network_id": networks["gw"]["id"],
            "server_container_id": server["id"], "proxy_container_id": proxy["id"]}
    if any(receipt.get(key) != value for key, value in live.items()):
        raise ValueError("isolation_probe_bound_to_other_resources")
    return receipt


def probe_action(prefix, state, run_id, arm):
    """`host.py probe`: re-run P0-P2 on a prepared attempt, e.g. to refresh its receipt.

    Needs an explicit run id and never mints one. A refusal before the probe
    runs changes nothing. A failed or crashed probe tears the attempt down
    and records failure_stage "probe" (exit 3), as run() does.
    """
    def refuse(stage, receipt=None):
        print(json.dumps({"run_id": run_id, "arm": arm, "receipt": receipt, "failure_stage": stage,
                          "task_passed": False, "evidence_complete": False}))
        return 3
    try:
        attempt_stem(run_id, arm)
    except ValueError:
        return refuse("preflight")
    result = Path(state) / "runs" / run_id / arm
    # Nothing has run before the probe starts; these refusals leave the attempt unchanged.
    try:
        status = json.loads(read_bounded(result / "status.json"))
        if not isinstance(status, dict) or status.get("status") != "prepared":
            raise ValueError("prepared_attempt_required")
    except (OSError, ValueError):
        return refuse("probe")
    try:
        pins, _, _ = preflight(prefix, state)
    except Exception:
        return refuse("preflight")
    failure_type = "RuntimeError"
    try:
        if run_probe(state, run_id, arm, prefix, pins):
            print(json.dumps({"run_id": run_id, "arm": arm, "isolation_probe": str(result / "isolation-probe.json"),
                              "passed": True}))
            return 0
    except (Exception, KeyboardInterrupt) as exc:
        failure_type = type(exc).__name__
    with contextlib.suppress(OSError, ValueError, subprocess.SubprocessError):
        teardown_attempt(state, run_id, arm)  # The cleanup records keep any uncertainty.
    try:
        window = json.loads(read_bounded(result / "window.json"))
    except (OSError, ValueError):
        window = {"run_id": run_id, "arm": arm, "started_at": utc_now()}
    window.update(failure_stage="probe", failure_type=failure_type, finished_at=window.get("finished_at") or utc_now())
    write_json(result / "window.json", window)
    if not (result / "check.json").is_file():
        write_json(result / "check.json", {"upstream_resolved": None, "grader_exit_code": None})
    write_json(result / "receipt.json", create_receipt(result))
    write_json(result / "status.json", {**status, "status": "failed", "failure_stage": "probe"})
    return refuse("probe", str(result / "receipt.json"))


def teardown_action(state, run_id, arm):
    """`host.py teardown`: remove an attempt that will not start a conversation now.

    For example after a probe-only acceptance run, or to retry an unconfirmed
    cleanup. It refuses, with no Docker call, while a conversation may be live
    or uncollected (status starting, running or terminal, whose teardown
    belongs to dispatch wait and result) or while the serial reservation names
    this attempt. teardown_attempt keeps the proxy and server logs first (the
    proxy access log holds the denied requests), removes the four resources by
    exact name and deletes the key files after confirmed container removal. A
    prepared status becomes "torn_down", which dispatch start and the probe
    refuse. Exit 0 only when all four removals are confirmed.
    """
    def report(outcome, code, **extra):
        print(json.dumps({"run_id": run_id, "arm": arm, "teardown": outcome, **extra}))
        return code
    try:
        attempt_stem(run_id, arm)
    except ValueError:
        return report("refused", 3, reason="owned_attempt_identity_required")
    result = Path(state) / "runs" / run_id / arm
    if not result.is_dir() or result.resolve() != result.absolute():
        return report("refused", 3, reason="owned_attempt_directory_required")
    try:
        status = json.loads(read_bounded(result / "status.json"))
    except FileNotFoundError:
        status = None
    except (OSError, ValueError):
        return report("refused", 3, reason="status_unreadable")
    if status is not None and (not isinstance(status, dict) or status.get("status") in {"starting", "running", "terminal"}):
        return report("refused", 3, reason="conversation_may_be_live")
    try:
        reservation = json.loads(read_bounded(Path(state) / "active-dispatch.json"))
    except FileNotFoundError:
        reservation = None
    except (OSError, ValueError):
        return report("refused", 3, reason="reservation_unreadable")
    if reservation == {"run_id": run_id, "arm": arm}:
        return report("refused", 3, reason="reservation_names_attempt")
    try:
        removed = teardown_attempt(state, run_id, arm) is True
    except (Exception, KeyboardInterrupt):
        removed = False  # The cleanup records keep the uncertainty.
    if status is not None and status.get("status") == "prepared":
        status = {**status, "status": "torn_down"}
        write_json(result / "status.json", status)
    return report("confirmed" if removed else "unconfirmed", 0 if removed else 3,
                  status=None if status is None else status.get("status"))


def clone_command(prefix, task, workspace):
    # SWE-bench@v4.1.0 test_spec/python.py:271-277, including branch exceptions.
    code = ("import json,sys; from importlib.metadata import version; "
            "assert version('swebench') == '4.1.0'; "
            "from swebench.harness.test_spec.python import REPO_BASE_COMMIT_BRANCH; "
            "print(json.dumps(REPO_BASE_COMMIT_BRANCH.get(sys.argv[1], {}).get(sys.argv[2], '')))")
    branch = json.loads(subprocess.check_output([
        str(prefix / "benchmarks/.venv/bin/python"), "-c", code, task["repo"], task["base_commit"]],
        text=True, timeout=30))
    if not isinstance(branch, str) or (branch and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch)):
        raise ValueError("invalid_upstream_branch_mapping")
    return ["git", "clone", "--no-checkout", "--single-branch", *(["--branch", branch] if branch else []),
            "--", "https://github.com/" + task["repo"] + ".git", str(workspace)]


def result_exit(receipt):
    if receipt.get("failure_stage"):
        return 3
    verdict = receipt.get("upstream_grader", {})
    if any(verdict.get(key) not in (None, 0) for key in ("grader_exit_code", "conversion_exit_code")):
        return 3
    if verdict.get("upstream_resolved") is False:
        return 1 if verdict.get("upstream_bucket") in {"unresolved_ids", "empty_patch_ids"} else 3
    if verdict.get("upstream_resolved") is True and receipt.get("agent_termination") in AGENT_LIMITS:
        return 1  # An officially graded partial patch after an agent limit is never a pass.
    if receipt.get("task_passed") and receipt.get("evidence_complete"):
        return 0
    return 2


def begin_attempt(state, run_id, arm, *, mcp=True):
    if not re.fullmatch(r"rw-openhands-[a-z0-9-]{1,64}", run_id):
        raise ValueError("owned_run_id_required")
    arm_config(arm)
    result = state / "runs" / run_id / arm
    if result.exists():
        raise ValueError("run_id_arm_already_exists")
    private_directory(result)
    # Resolver mode has no MCP server, so no MCP state directory (mcp=False).
    for directory in (result / "input", result / "worker", *([result / "mcp"] if mcp else [])):
        private_directory(directory)
    write_json(result / "status.json", {"run_id": run_id, "arm": arm, "status": "starting",
                                        "receipt": str(result / "receipt.json")})
    return result


def model_visible(root, *, writable):
    """Owned mount contents only; private mode-0700 attempt parent stays private.

    Rootless Docker's UID mapping is not host UID equality. The upstream image
    user is 10001 (Dockerfile@fcc102a:7-9,343). Never chmod symlink targets.
    """
    root = Path(root)
    for path in (root, *root.rglob("*")):
        if path.is_symlink():
            continue
        mode = path.stat().st_mode
        if stat.S_ISDIR(mode):
            path.chmod(0o777 if writable else 0o755)
        elif stat.S_ISREG(mode):
            path.chmod((0o666 if writable else 0o644) | (0o111 if mode & 0o111 else 0))
        else:
            raise ValueError("special_file_in_model_mount")


def prepare_native_dispatch(state, run_id, selection, prefix, pins, base, host, port=DEFAULT_PORT, *, resolver=False,
                            session_sink=None):
    """Serialize the request offline, then build the O1 topology around the server.

    Order: request render with no network; the two attempt networks; the
    per-attempt key; the agent-server on <stem>-int with no published port;
    the rendered proxy config; proxy create/connect/start; the native health
    and OpenAPI gate through the proxy's loopback ingress. The caller tears
    everything down on any failure (teardown_attempt). Resolver mode renders
    with `worker.py --request --resolver` and hands the key to `session_sink`.
    """
    from dispatch import check_server, server_command
    stem = attempt_stem(run_id, selection["arm"])
    result = Path(state) / "runs" / run_id / selection["arm"]
    port = owned_port(port)
    environment = ["--env", "OPENHANDS_OWNED_CONTAINER=1",
                   "--env", "OPENHANDS_RUN_ID=" + run_id, "--env", "OPENHANDS_ARM=" + selection["arm"],
                   "--env", "OPENHANDS_MODEL=" + selection["requested_model"],
                   "--env", "OPENHANDS_BASE_URL=" + selection["base_url"],
                   "--env", "OPENHANDS_COMPRESSION=" + (selection["compression_combo"] or ""),
                   "--env", f"PATH={prefix}/venv/bin:" + host["variables"]["HOST_PATH"]]
    render = docker_args(pins, stem + "-request") + base + mount(result / "worker", "/run-output", False)
    render += environment + ["--entrypoint", str(prefix / "venv/bin/python"), pins["image"]["ref"], "/recipe/worker.py", "--request"]
    render += ["--resolver"] if resolver else []
    if execute_container(render, stem + "-request", result / "request.log", 120):
        raise RuntimeError("native_request_serialization_failed")
    # Host copy made before a model can run; later worker edits cannot change it.
    body = json.loads(read_bounded(result / "worker/start.json"))
    write_json(result / "start.json", body)
    private_directory(result / "server")
    model_visible(result / "server", writable=True)
    networks = create_topology(result, stem)
    env_file, _ = generate_session_files(state, run_id, selection["arm"], sink=session_sink)
    check_server_env(env_file)
    mounts = base + environment + mount(result / "server", "/state/server", False) + mount(result / "worker", "/run-output", False)
    name = stem + "-server"
    if logged_command(server_command(pins, name, mounts, networks["int"]["name"], env_file),
                      result / "server-start.log", cwd=result, timeout=60):
        raise RuntimeError("native_server_launch_failed")
    config, config_sha256 = write_proxy_config(result, render_proxy_config(selection, run_id))
    launch_proxy(result, pins, stem, config, port)
    check_server(body, port=port)
    # Host-owned status is the dispatch commands' only port source.
    write_json(result / "status.json", {"run_id": run_id, "arm": selection["arm"], "status": "prepared",
                                        "server_name": name, "proxy_name": stem + "-proxy", "port": port,
                                        "proxy_config_sha256": config_sha256,
                                        "receipt": str(result / "receipt.json")})


def run(prefix, state, *, run_id=None, arm=None, prepare_only=False, port=DEFAULT_PORT, resolver=None):
    """One attempt: SWE-bench mode, or resolver mode when `resolver` is a resolver.ResolverAttempt.

    Resolver mode (RESOLVER.md "Stage 2") keeps the O1 topology, the P0-P2 probe and
    every dispatch gate. It also checks the stage gates and G5 before any clone or
    container, and it replaces the task clone, MCP, QMD and SWE-bench skills with an
    anonymous pinned clone of main, AGENTS.md and the resolver skill set.
    """
    run_id = run_id or os.environ.get("OPENHANDS_RUN_ID", "rw-openhands-e2e-" + uuid.uuid4().hex[:12])
    arm = arm or os.environ.get("OPENHANDS_ARM", "control")
    try:
        result = begin_attempt(state, run_id, arm, mcp=resolver is None)
    except (OSError, ValueError):
        print(json.dumps({"run_id": run_id, "arm": arm, "receipt": None, "failure_stage": "preflight",
                          "task_passed": False, "evidence_complete": False}))
        return 3
    window = {"started_at": utc_now(), "finished_at": None, "worker_exit_code": None, "arm": arm, "run_id": run_id}
    if resolver is not None:
        window["mode"] = "resolver"
    checked = {"upstream_resolved": None, "grader_exit_code": None}
    stem = run_id + "-" + arm
    stage = "preflight"
    prepared = False
    native_receipt = None
    try:
        port = owned_port(port)
        if resolver is not None:
            # First, so that every receipt of the attempt names its issue and base.
            write_json(result / "resolver-identity.json", resolver.identity())
        pins, host, mcp = preflight(prefix, state, resolver=resolver is not None)
        if resolver is not None:
            # The dispatch gate's stage-gate and G5 checks, before any clone or container.
            # verify_isolation repeats both at dispatch start, so this is stricter, never a bypass.
            stage = "gates"
            verify_stage_gates(state, arm, now=datetime.now(timezone.utc))
            verify_gateway_providers(arm, gateway_allowlists(host))
            window["stage_gates_sha256"] = optional_digest(Path(state) / STAGE_GATES)
            stage = "preflight"
        installed = read_json(state / "installation.json")
        if installed.get("exit_code") != 0 or installed.get("requirements_sha256") != pins["requirements_sha256"]:
            raise ValueError("matching_successful_installation_required")
        if not os.path.lexists(prefix / "venv/bin/python"):
            raise ValueError("owned_sdk_venv_missing")
        # Present locally by digest (install pulls it); proxy launches never pull.
        pinned_image_identity(pins["gateway_proxy"])
        cfg = read_json(HERE / "config/worker.json")
        selection = environment_selection(os.environ, arm)
        llm_config(cfg, selection["requested_model"], arm=arm, base_url=selection["base_url"],
                   compression=selection["compression_combo"])
        window.update({k: v for k, v in selection.items() if k != "headers"})
        window["header_names"] = sorted([*selection["headers"], "x-omniroute-session", "X-Correlation-Id", "Idempotency-Key"])
        stage = "prepare"
        if resolver is None:
            original = Path(os.environ["OPENHANDS_TASK_FILE"]).resolve()
            task_sha = os.environ["OPENHANDS_TASK_SHA256"]
            task = load_task(original, task_sha)
            window.update(instance_id=task["instance_id"])
            # Frozen oracle bytes are outside every worker mount.
            dataset = result / ("dataset" + original.suffix)
            shutil.copyfile(original, dataset)
            load_task(dataset, task_sha)
            write_json(result / "task-identity.json", {
                "instance_id": task["instance_id"], "repo": task["repo"],
                "base_commit": task["base_commit"], "dataset_sha256": task_sha,
            })
            workspace = result / "workspace"
            code = logged_command(clone_command(prefix, task, workspace), result / "clone.log", cwd=result, timeout=300)
            if code:
                raise RuntimeError("task_clone_failed")
            code = logged_command(["git", "-C", str(workspace), "reset", "--hard", task["base_commit"]],
                                  result / "checkout.log", cwd=result, timeout=120)
            if code:
                raise RuntimeError("task_checkout_failed")
            # SWE-bench 4.1.0 test_spec/python.py:274-292 removes future refs and
            # reflogs before exposing the checkout. This bare-checkout adaptation
            # drops every tag (not only newer tags) and checks surviving refs below.
            code = logged_command(["git", "-C", str(workspace), "remote", "remove", "origin"],
                                  result / "remove-remote.log", cwd=result, timeout=30)
            if code:
                raise RuntimeError("task_history_isolation_failed")
            tags = subprocess.check_output(["git", "-C", str(workspace), "tag", "--list"], text=True, timeout=30).splitlines()
            for tag in tags:
                subprocess.run(["git", "-C", str(workspace), "update-ref", "-d", "refs/tags/" + tag],
                               check=True, timeout=30, stdin=subprocess.DEVNULL)
            for phase, argv in (("reflog", ["reflog", "expire", "--expire=now", "--all"]),
                                ("gc", ["gc", "--prune=now"])):
                if logged_command(["git", "-C", str(workspace), *argv], result / (phase + ".log"),
                                  cwd=result, timeout=300):
                    raise RuntimeError("task_history_isolation_failed")
            refs = subprocess.check_output(["git", "-C", str(workspace), "for-each-ref", "--format=%(objectname)"],
                                           text=True, timeout=30).splitlines()
            if not refs or any(ref != task["base_commit"] for ref in refs):
                raise ValueError("unexpected_task_reference")
        else:
            workspace = resolver_clone(result, resolver.base_sha)
            write_agents_md(workspace, resolver.base_sha, result / "input/agents.md")
        stage = "skills"
        stack_root = Path(os.environ.get("OPENHANDS_STACK_ROOT", str(HERE.parents[2]))).resolve()
        if not (stack_root / "blueprints/runtime-workers/skills/manifest.json").is_file():
            raise ValueError("skills_program_pending_pr")
        if resolver is None:
            install_workspace_skills(stack_root, workspace)
            skills = workspace_skills(stack_root, workspace)
            write_json(result / "input/skills.json", skills)
            write_json(result / "input/mcp.json", mcp)
            (result / "input/task.txt").write_text(worker_instruction(task))
            for name in mcp:
                for child in ("cache", "config", "data", "state"):
                    private_directory(result / "mcp" / name / child)
            serena_home = result / "mcp/serena/home"
            private_directory(serena_home)
            shutil.copyfile(HERE / "config/serena_config.yml", serena_home / "serena_config.yml")
            for directory in (workspace, result / "mcp", result / "worker"):
                model_visible(directory, writable=True)
            model_visible(result / "input", writable=False)
            # Only the worker venv, not the grader checkout/environment, is mounted.
            base = mount(prefix / "venv", prefix / "venv") + mount(HERE, "/recipe")
            base += mount(result / "input", "/run-input") + mount(result / "mcp", "/state/mcp", False)
            base += mount(workspace, "/workspace", False) + mount(workspace / ".git", "/workspace/.git")
            base += mount(workspace / ".agents", "/workspace/.agents") + runtime_mounts(host)
            if (workspace / "skills-lock.json").is_file():
                base += mount(workspace / "skills-lock.json", "/workspace/skills-lock.json")
            stage = "qmd_setup"
            args = docker_args(pins, stem + "-qmd") + base
            args += ["--entrypoint", str(prefix / "venv/bin/python"), pins["image"]["ref"], "/recipe/qmd-setup.py"]
            if execute_container(args, stem + "-qmd", result / "qmd-setup.log", 900):
                raise RuntimeError("qmd_setup_failed")
        else:
            write_json(result / "input/skills.json", install_resolver_skills(stack_root, workspace, result))
            (result / "input/task.txt").write_text(resolver.instruction)
            for directory in (workspace, result / "worker"):
                model_visible(directory, writable=True)
            model_visible(result / "input", writable=False)
            # The SWE-bench mounts without /state/mcp, the MCP tool roots and the QMD
            # collections, and no QMD setup: resolver mode has no MCP server.
            base = mount(prefix / "venv", prefix / "venv") + mount(HERE, "/recipe")
            base += mount(result / "input", "/run-input")
            base += mount(workspace, "/workspace", False) + mount(workspace / ".git", "/workspace/.git")
            base += mount(workspace / ".agents", "/workspace/.agents")
            if (workspace / "skills-lock.json").is_file():
                base += mount(workspace / "skills-lock.json", "/workspace/skills-lock.json")
        stage = "start"
        prepare_native_dispatch(state, run_id, selection, prefix, pins, base, host, port=port,
                                resolver=resolver is not None, session_sink=getattr(resolver, "session_sink", None))
        # Plan E1/G7: P0-P2 before any conversation; dispatch start re-checks the receipt.
        stage = "probe"
        if not run_probe(state, run_id, arm, prefix, pins):
            raise RuntimeError("isolation_probe_failed")
        stage = "start"
        prepared = True
        write_json(result / "window.json", window)
        if not prepare_only:
            from dispatch import execute
            with contextlib.redirect_stdout(io.StringIO()):
                for action in ("start", "wait", "result"):
                    if execute(action, state, run_id, arm, resolver=resolver):
                        break
            native_receipt = read_json(result / "receipt.json")
    except (Exception, KeyboardInterrupt) as exc:
        window["failure_stage"] = stage
        window["failure_type"] = type(exc).__name__
        if stage in {"start", "probe"}:
            # Resources may exist from the first network onward; remove them by name.
            try:
                teardown_attempt(state, run_id, arm)
            except (OSError, ValueError, subprocess.SubprocessError):
                pass  # The cleanup records keep the uncertainty.
    finally:
        if native_receipt is not None:
            receipt = native_receipt
        else:
            window["finished_at"] = window["finished_at"] or utc_now()
            write_json(result / "window.json", window)
            write_json(result / "check.json", checked)
            receipt = create_receipt(result)
            write_json(result / "receipt.json", receipt)
    output = {"run_id": run_id, "arm": arm, "receipt": str(result / "receipt.json"),
              **{k: receipt[k] for k in ("failure_stage", "task_passed", "evidence_complete")}}
    if not prepared:
        write_json(result / "status.json", {**output, "status": "failed" if receipt["failure_stage"] else "finished"})
    print(json.dumps(output))
    if prepare_only and prepared:
        return 0
    return result_exit(receipt)


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("install", "run", "prepare", "probe", "teardown"))
    parser.add_argument("--prefix", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--arm", choices=("control", "engines-on"))
    parser.add_argument("--port", type=cli_port, default=DEFAULT_PORT,
                        help="published loopback port in 3730..3799 (default 3730; resolver mode 3740)")
    return parser


def main():
    args = build_parser().parse_args()
    os.umask(0o077)
    # SIGTERM goes through container cleanup and the failed-attempt receipt path.
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    if args.action == "install":
        install(args.prefix, args.state)
        return 0
    if args.action == "probe":
        # An existing attempt only: no run id is ever generated for a probe.
        return probe_action(args.prefix, args.state, args.run_id or os.environ.get("OPENHANDS_RUN_ID"),
                            args.arm or os.environ.get("OPENHANDS_ARM", "control"))
    if args.action == "teardown":
        # Likewise an existing attempt only; it needs no prefix or preflight.
        return teardown_action(args.state, args.run_id or os.environ.get("OPENHANDS_RUN_ID"),
                               args.arm or os.environ.get("OPENHANDS_ARM", "control"))
    return run(args.prefix, args.state, run_id=args.run_id, arm=args.arm,
               prepare_only=args.action == "prepare", port=args.port)


if __name__ == "__main__":
    raise SystemExit(main())
