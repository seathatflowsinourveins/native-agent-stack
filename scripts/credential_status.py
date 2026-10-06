#!/usr/bin/env python3
"""Report where this host's credentials live and whether each store is safe.

Nonmutating and value-free. For every entry in adoption/credential-inventory.json
it uses os.lstat only: existence, file type, mode, owner, parent-directory mode,
whether the path sits inside a Git worktree (and, if so, whether Git tracks it)
and mtime age. It never opens, reads, hashes or follows a credential file, and
it prints path templates, variable names and reason codes, never values or
expanded host paths. Environment checks report variable NAMES that are set,
never their values. That includes a native store's path override (such as
HF_TOKEN_PATH), which moves the store away from the path this checker inspects.
A kernel keyring entry (memory only, scripts/kernel_keyring.py) has no file:
it is validated and reported as `unchecked` with persistence `memory_only` and
the warning `memory_only_lost_on_restart`, and the keyring is never queried. A
required key must survive a restart, so a required kernel keyring entry is an
inventory error.

Two coverage lists account for keys that no entry declares, by name only: the
store root's own names (one scandir; no file is opened) and the kernel's live
user keys described native-agent-stack:<name>, by the whole <name> (/proc/keys,
which shows descriptions and payload lengths, never payloads; Linux only). Each
nonempty list is a warning.

Exit status is 1 when any credential file that exists is unsafe (whatever the
entry's status, since a stored optional or paid key leaks just as badly), and 2
for an invalid inventory. Missing entries and warnings are informational.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = "adoption/credential-inventory.json"
EXPECTED_HOOKS_PATH = "scripts/git-hooks"
AGE_WARNING_DAYS = 90
STORE_ROOT = "${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack"
REQUIRED_POINTERS = ("PAPER_ENV_FILE", "PAPER_ENV_FILE_2", "SEC_CONTACT_ENV", "PIT_ALPACA_ENV_PATH", "PIT_SEC_ENV_PATH",
                     "IBKR_PAPER_LOGIN_ENV", "IBKR_PAPER_TWS_FILE", "IBKR_PAPER_VNC_FILE")

LOCAL_KINDS = {"private_env_file", "private_file", "native_store"}
NONLOCAL_KINDS = {"interactive_login", "github_actions"}
# Held in memory by the Linux kernel, never in a file (scripts/kernel_keyring.py). The checker validates
# the entry and never queries the keyring; `kernel_keyring.py status <key_name>` is the presence check.
MEMORY_KINDS = {"kernel_keyring"}
KEYRING_KEY_NAME = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}")  # the names scripts/kernel_keyring.py accepts
# The kernel's list of the keys this process may view (keys(7)). Each line is formatted by proc_keys_show() in
# linux v6.18 security/keys/proc.c: serial, the seven flags I R D Q U N i (instantiated, revoked, dead, in quota,
# under construction, negative, invalidated), usage, expiry ("perm", "expd" or a time left), permissions, uid,
# gid, then "%-9.9s " for the type and the type's describe output. For a "user" key, user_describe() in
# security/keys/user_defined.c prints the whole description, which may hold "/", ":" or spaces, and then, for a
# positive key, ": <payload length>". Only that last suffix is removed; the description is kept whole.
PROC_KEYS = Path("/proc/keys")
PROC_KEYS_LINE = re.compile(
    r"[0-9a-f]+ (?P<flags>\S{7}) +\d+ +(?P<expiry>\S+) +[0-9a-f]+ +(?P<uid>\d+) +\d+ (?P<type>.{9}) (?P<describe>.*)")
USER_DESCRIBE = re.compile(r"(?P<description>.*): \d+")  # greedy: only the final ": <payload length>" is removed
KEYRING_PREFIX = "native-agent-stack:"  # scripts/kernel_keyring.py PREFIX
# test_only and test_canary label only the canary proof's synthetic key (tools/credentials/canary_proof.py writes and
# removes it per consumer attempt): a missing file is informational like every missing row, and the pair goes together.
STATUSES = {"required", "optional", "user_only_paid", "generated_local", "native",
            "interactive_only", "ci_only", "test_only"}
CLASSES = {"broker_api_key_pair", "contact_identity", "provider_api_key",
           "local_service_secret", "native_signin", "ci_secret", "test_canary"}
TEMPLATE_PREFIXES = ("${XDG_CONFIG_HOME:-$HOME/.config}/", "${CODEX_HOME:-$HOME/.codex}/",
                     "${HF_HOME:-${XDG_CACHE_HOME:-$HOME/.cache}/huggingface}/", "$HOME/")
NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
# ${NAME:-default}, where the default may hold one nested ${NAME:-default}: huggingface_hub's
# HF_HOME defaults to ${XDG_CACHE_HOME:-$HOME/.cache}/huggingface (constants.py).
DEFAULT_FORM = re.compile(r"\$\{([A-Z_][A-Z0-9_]*):-((?:[^{}]|\$\{[A-Z_][A-Z0-9_]*:-[^{}]*\})*)\}")
ENTRY_KEYS = {"id", "label", "class", "status", "lane", "store", "variables",
              "optional_variables", "pointer_variables", "loaders",
              "environment_only_consumers", "rotation", "notes"}

# Tracked basenames that should never exist in a checkout. Basename/extension
# matching keeps evidence folders such as .../secrets-credentials/ out of scope.
# Hugging Face's other file, the bare `token` basename, is deliberately not
# listed: it is too generic to flag repository-wide (.gitignore makes the same
# choice; docs/secret-storage.md "Threat model").
SENSITIVE_BASENAME = re.compile(
    r"^(?:\.env|\.env\..+|.+\.env|.+\.key|.+\.pem|credentials\.json|\.credentials\.json"
    r"|auth\.json|hosts\.yml|\.netrc|id_rsa|id_ecdsa|id_ed25519|stored_tokens)$")


def public_names(entry: dict) -> list[str]:
    """The entry's variables that tools/credentials/credential_run.py injects unmasked: only an optional variable that
    the entry classifies in public_variables and that is not also required (inventory_errors rejects such an entry;
    this keeps a required variable masked even for one that was not validated)."""
    required, optional = entry["variables"], entry["optional_variables"]
    return [name for name in entry.get("public_variables", []) if name in optional and name not in required]


def masked_names(entry: dict) -> list[str]:
    """Every declared variable of the entry except its public_variables."""
    public = set(public_names(entry))
    return [name for name in dict.fromkeys(entry["variables"] + entry["optional_variables"]) if name not in public]


def inventory_errors(inventory, root: Path | None = None) -> list[str]:
    """Structural check of the inventory; returns reason strings, never values."""
    errors: list[str] = []
    if not isinstance(inventory, dict) or inventory.get("schema_version") != 1:
        return ["inventory: expected object with schema_version 1"]
    entries = inventory.get("entries")
    if not isinstance(entries, list) or not entries:
        return ["inventory: entries must be a nonempty array"]
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        label = f"entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label}: expected object")
            continue
        missing = ENTRY_KEYS - set(entry)
        if missing:
            errors.append(f"{label}: missing keys {sorted(missing)}")
            continue
        identifier = entry["id"]
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-z0-9-]+", identifier):
            errors.append(f"{label}: invalid id")
        elif identifier in seen:
            errors.append(f"{label}: duplicate id {identifier}")
        else:
            seen.add(identifier)
        if entry["status"] not in STATUSES:
            errors.append(f"{label}: unknown status")
        if entry["class"] not in CLASSES:
            errors.append(f"{label}: unknown class")
        if (entry["status"] == "test_only") != (entry["class"] == "test_canary"):
            errors.append(f"{label}: status test_only and class test_canary go together (a synthetic canary only)")
        store = entry["store"]
        if not isinstance(store, dict) or store.get("kind") not in LOCAL_KINDS | NONLOCAL_KINDS | MEMORY_KINDS:
            errors.append(f"{label}: unknown store kind")
        else:
            template = store.get("path_template")
            if store["kind"] in LOCAL_KINDS:
                if not isinstance(template, str) or not template.startswith(TEMPLATE_PREFIXES) \
                        or ".." in template.split("/"):
                    errors.append(f"{label}: local store needs a home-anchored path template")
            elif template != "":
                errors.append(f"{label}: non-local store must have an empty path template")
            key_name = store.get("key_name")
            if store["kind"] in MEMORY_KINDS and not (isinstance(key_name, str) and KEYRING_KEY_NAME.fullmatch(key_name)):
                errors.append(f"{label}: kernel keyring store needs a key_name that scripts/kernel_keyring.py accepts")
            if store["kind"] in MEMORY_KINDS and entry["status"] == "required":
                errors.append(f"{label}: a required key cannot live only in the kernel keyring, which loses it "
                              "at every kernel restart; store it in a file")
        for key in ("variables", "optional_variables", "pointer_variables"):
            names = entry[key]
            if not isinstance(names, list) or not all(isinstance(n, str) and NAME.match(n) for n in names):
                errors.append(f"{label}: {key} must be uppercase variable names")
            elif len(set(names)) != len(names):
                errors.append(f"{label}: {key} must not repeat a name")
        required = [n for n in entry["variables"] if isinstance(n, str)] \
            if isinstance(entry["variables"], list) else []
        optional = [n for n in entry["optional_variables"] if isinstance(n, str)] \
            if isinstance(entry["optional_variables"], list) else []
        if set(required) & set(optional):  # else a required variable could be classified public below
            errors.append(f"{label}: variables and optional_variables must not share a name "
                          "(a required variable is never optional or public)")
        # Optional key: the optional variables that tools/credentials/credential_run.py injects unmasked (not secret,
        # such as a base URL); it masks every other variable it injects. An env-file entry with optional variables
        # classifies them explicitly, [] masking them all.
        if "public_variables" in entry:
            public = entry["public_variables"]
            if not isinstance(public, list) or not all(isinstance(n, str) and NAME.match(n) for n in public):
                errors.append(f"{label}: public_variables must be uppercase variable names")
            elif len(set(public)) != len(public) or not set(public) <= set(optional):
                errors.append(f"{label}: public_variables must name distinct optional_variables of the entry")
        elif isinstance(store, dict) and store.get("kind") == "private_env_file" and optional:
            errors.append(f"{label}: an env-file entry with optional_variables must classify them in "
                          "public_variables (the names injected unmasked; [] masks them all)")
        for key in ("loaders", "environment_only_consumers"):
            refs = entry[key]
            if not isinstance(refs, list) or not all(isinstance(r, str) for r in refs):
                errors.append(f"{label}: {key} must be strings")
                continue
            if root is not None:
                for ref in refs:
                    candidate = ref.split("#", 1)[0]
                    if "/" in candidate and " " not in candidate and not (root / candidate).is_file():
                        errors.append(f"{label}: {key} path not found: {candidate}")
    names = inventory.get("must_not_be_set")
    if not isinstance(names, list) or not all(isinstance(n, str) and NAME.match(n) for n in names):
        errors.append("must_not_be_set: expected uppercase variable names")
    if inventory.get("store_root_template") != STORE_ROOT:
        errors.append("store_root_template: must match the checker's store root")
    return errors


def expand_template(template: str, env) -> Path:
    home = env.get("HOME") or str(Path.home())

    def expand(text: str) -> str:
        def default(match: re.Match) -> str:
            value = env.get(match.group(1))
            return value if value else expand(match.group(2))  # only a default is expanded again

        return DEFAULT_FORM.sub(default, text).replace("$HOME", home)

    return Path(expand(template))


def git_worktree_of(directory: Path) -> Path | None:
    """Nearest ancestor holding a .git entry (directory or linked-worktree file)."""
    current = Path(os.path.realpath(directory))
    while True:
        if os.path.lexists(current / ".git"):
            return current
        if current.parent == current:
            return None
        current = current.parent


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          timeout=20, check=False)


def git_tracks(path: Path) -> bool:
    result = _git(["ls-files", "--error-unmatch", "--", path.name], path.parent)
    return result.returncode == 0


def native_store_overrides(entries, env) -> list[str]:
    """Names of set pointer variables of native stores (a path override such as HF_TOKEN_PATH).

    Our own stores are found through pointer variables on purpose; a native tool reads such a
    variable itself, so the store is no longer where its template says. Names only."""
    return sorted({name for entry in entries if entry["store"]["kind"] == "native_store"
                   for name in entry["pointer_variables"] if name in env})


def inspect_entry(entry: dict, env, uid: int, now: float) -> dict:
    store = entry["store"]
    names = entry["variables"] + entry["optional_variables"]
    report = {
        "id": entry["id"], "status": entry["status"], "class": entry["class"],
        "lane": entry["lane"], "store_kind": store["kind"], "path": store["path_template"],
        "findings": [], "warnings": [],
        "variables_in_environment": sorted(n for n in names if n in env),
    }
    if report["variables_in_environment"]:
        report["warnings"].append("store_variables_exported_in_environment")
    if store["kind"] == "native_store" and native_store_overrides([entry], env):
        # The tool then keeps its store where the variable points, not at the template.
        report["warnings"].append("store_path_overridden")
    if store["kind"] in NONLOCAL_KINDS:
        report["state"] = "not_local"
        return report
    if store["kind"] in MEMORY_KINDS:
        # No file to inspect, and the keyring is not queried: the state says so rather than guessing. The key
        # lives in kernel memory only, so the next kernel restart erases it.
        report["state"] = "unchecked"
        report["key_name"] = store["key_name"]
        report["persistence"] = "memory_only"
        report["warnings"].append("memory_only_lost_on_restart")
        return report
    path = expand_template(store["path_template"], env)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        report["state"] = "missing"
        return report
    except OSError:
        report["state"] = "unsafe"
        report["findings"].append("cannot_stat")
        return report
    report["mode"] = format(stat.S_IMODE(info.st_mode), "04o")
    findings = report["findings"]
    if stat.S_ISLNK(info.st_mode):
        findings.append("symlink_refused")
    elif not stat.S_ISREG(info.st_mode):
        findings.append("not_regular_file")
    mode = stat.S_IMODE(info.st_mode)
    if store["kind"] == "native_store":
        if mode & 0o077:
            findings.append("group_or_other_access")
    elif mode != 0o600:
        findings.append("mode_not_0600")
    if info.st_uid != uid:
        findings.append("foreign_owner")
    try:
        parent = os.lstat(path.parent)
        report["directory_mode"] = format(stat.S_IMODE(parent.st_mode), "04o")
        if store["path_template"].startswith(STORE_ROOT + "/") and stat.S_IMODE(parent.st_mode) & 0o077:
            findings.append("directory_group_or_other_access")
        elif stat.S_IMODE(parent.st_mode) & 0o002:
            findings.append("directory_world_writable")
    except OSError:
        findings.append("cannot_stat_directory")
    worktree = git_worktree_of(path.parent)
    report["inside_git_worktree"] = worktree is not None
    if worktree is not None:
        findings.append("inside_git_worktree")
        if git_tracks(path):
            findings.append("tracked_by_git")
    age_days = int(max(0.0, now - info.st_mtime) // 86400)
    report["age_days"] = age_days
    if age_days > AGE_WARNING_DAYS:
        report["warnings"].append(f"older_than_{AGE_WARNING_DAYS}_days")
    report["state"] = "unsafe" if findings else "ok"
    return report


def undeclared_store_files(entries, env) -> list[str] | None:
    """Names in the store root that no entry's file claims; directories are skipped.

    One scandir of the store root: names only, no file is opened or followed. [] when there is no store yet;
    None when the store root is not a real directory (a symbolic link is never listed through) or cannot be
    listed."""
    root = expand_template(STORE_ROOT, env)
    try:
        if not stat.S_ISDIR(os.lstat(root).st_mode):
            return None
        with os.scandir(root) as listing:
            present = {item.name for item in listing if not item.is_dir(follow_symlinks=False)}
    except FileNotFoundError:
        return []
    except OSError:
        return None
    claimed = set()
    for entry in entries:
        if entry["store"]["kind"] in LOCAL_KINDS:
            path = expand_template(entry["store"]["path_template"], env)
            if path.parent == root:
                claimed.add(path.name)
    return sorted(present - claimed)


def undeclared_keyring_keys(entries, uid: int, proc_keys: Path | None) -> list[str] | None:
    """Full names of this uid's live "user" keys described native-agent-stack:<name> that no entry declares.

    Read from the kernel's key list, which holds descriptions and payload lengths, never payloads. <name> is the
    whole rest of the description, "/" and ":" included, and a kernel_keyring entry declares a key only when its
    key_name equals that rest exactly. Revoked, dead, negative, invalidated and expired keys hold no usable value
    and are skipped. None when there is no list to read (not Linux, or proc_keys is None)."""
    if proc_keys is None:
        return None
    try:
        with open(proc_keys, encoding="utf-8", errors="backslashreplace") as handle:
            text = handle.read()
    except OSError:
        return None
    declared = {entry["store"]["key_name"] for entry in entries if entry["store"]["kind"] in MEMORY_KINDS}
    live = set()
    for line in text.splitlines():
        match = PROC_KEYS_LINE.fullmatch(line)
        if (not match or match["type"].rstrip() != "user" or int(match["uid"]) != uid
                or match["flags"][0] != "I" or set(match["flags"]) & set("RDNi") or match["expiry"] == "expd"):
            continue
        positive = USER_DESCRIBE.fullmatch(match["describe"])
        description = positive["description"] if positive else match["describe"]
        if description.startswith(KEYRING_PREFIX):
            live.add(description[len(KEYRING_PREFIX):])
    return sorted(live - declared)


def tracked_sensitive_names(root: Path) -> list[str] | None:
    result = _git(["ls-files", "-z"], root)
    if result.returncode != 0:
        return None
    hits = []
    for name in result.stdout.split("\0"):
        base = name.rsplit("/", 1)[-1]
        if name and not base.endswith(".example") and SENSITIVE_BASENAME.match(base):
            hits.append(name)
    return sorted(hits)


def hooks_path(root: Path) -> str | None:
    result = _git(["config", "--get", "core.hooksPath"], root)
    return result.stdout.strip() if result.returncode == 0 else None


TELEMETRY_CONTENT_FLAGS = ("OTEL_LOG_TOOL_CONTENT", "OTEL_LOG_TOOL_DETAILS", "OTEL_LOG_USER_PROMPTS",
                           "OTEL_LOG_ASSISTANT_RESPONSES", "OTEL_LOG_RAW_API_BODIES")
TELEMETRY_ENABLE_FLAG = "CLAUDE_CODE_ENABLE_TELEMETRY"
FALSY = {"", "0", "false", "no", "off"}
GUARD_HOOK_FILE = "secret_path_guard.py"
# What tools/adoption/install_claude_profile.py copies to <claude dir>/hooks/, and the pin file it checks it against.
GUARD_SOURCE = "scripts/hooks/secret_path_guard.py"
GUARD_PINS = "adoption/hooks/claude/SHA256SUMS"
CLIENT_GUARD_KEYS = ("claude_user_deny_rules", "claude_user_secret_guard_hook", "claude_sandbox_enabled",
                     "claude_telemetry_logs_content", "claude_telemetry_content_flags",
                     "codex_shell_environment_inherit_none", "claude_user_guard_matches_pin")


def truthy(value) -> bool:
    """Truthiness of a settings env entry. The value is compared, never returned or printed."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return isinstance(value, str) and value.strip().lower() not in FALSY


def enabled_names(settings_env) -> tuple[frozenset[str], frozenset[str]]:
    """Key names only: (names present, names whose entry is truthy).

    Each entry is reduced to its key and one boolean here; no entry value leaves
    this function, so everything downstream of it works on key names alone."""
    if not isinstance(settings_env, dict):
        return frozenset(), frozenset()
    present = frozenset(name for name in settings_env if isinstance(name, str))
    enabled = frozenset(name for name in present if truthy(settings_env[name]))
    return present, enabled


def telemetry_content_logging(settings_env) -> dict:
    """Booleans for Claude Code's OpenTelemetry content flags in settings `env`.

    Only key names and truthiness are used. OTEL_LOG_ASSISTANT_RESPONSES falls back
    to OTEL_LOG_USER_PROMPTS when unset (Claude Code monitoring docs)."""
    present, enabled = enabled_names(settings_env)
    flags = {name: name in enabled for name in TELEMETRY_CONTENT_FLAGS}
    if "OTEL_LOG_ASSISTANT_RESPONSES" not in present:
        flags["OTEL_LOG_ASSISTANT_RESPONSES"] = flags["OTEL_LOG_USER_PROMPTS"]
    telemetry_on = TELEMETRY_ENABLE_FLAG in enabled
    return {"telemetry_enabled": telemetry_on, "flags": flags,
            "logs_content": telemetry_on and any(flags.values())}


def guard_hook_installed(settings, claude_dir: Path) -> bool:
    """A user PreToolUse hook runs the path guard and the guard file exists (lstat only)."""
    groups = settings.get("hooks", {}).get("PreToolUse", [])
    registered = any(
        isinstance(hook, dict) and GUARD_HOOK_FILE in str(hook.get("command", ""))
        for group in groups if isinstance(group, dict)
        for hook in (group.get("hooks") if isinstance(group.get("hooks"), list) else []))
    return registered and os.path.lexists(claude_dir / "hooks" / GUARD_HOOK_FILE)


def guard_pin(root: Path) -> str | None:
    """The guard's sha256 on its line of the checkout's pin file, or None when there is no such line.

    Paths in the pin file are relative to its own directory, read as install_claude_profile.py's
    sha256sums_entries() reads them."""
    pins = root / GUARD_PINS
    try:
        lines = pins.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    source = (root / GUARD_SOURCE).resolve()
    for line in lines:
        parts = line.split()
        if len(parts) == 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0]) \
                and (pins.parent / parts[1].lstrip("*")).resolve() == source:
            return parts[0]
    return None


def guard_matches_pin(claude_dir: Path, root: Path) -> bool:
    """Whether the installed user-scope guard's bytes hash to the checkout's pin. One boolean; no digest leaves here.

    The guard is the only file read: it is opened without following a symbolic link and hashed only when it is a
    regular file, so a link planted in its place never makes this read another file, a store file included."""
    expected = guard_pin(root)
    if expected is None:
        return False
    try:
        handle = os.open(claude_dir / "hooks" / GUARD_HOOK_FILE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return False
    try:
        if not stat.S_ISREG(os.fstat(handle).st_mode):
            return False
        digest = hashlib.sha256()
        while chunk := os.read(handle, 1 << 16):
            digest.update(chunk)
    except OSError:
        return False
    finally:
        os.close(handle)
    return digest.hexdigest() == expected


def claude_guard_booleans(claude_dir: Path) -> dict | None:
    """Booleans derived from the user Claude settings, or None when unreadable.

    The parsed settings stay local to this function; only booleans are returned."""
    try:
        settings = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
        deny = settings.get("permissions", {}).get("deny", [])
        telemetry = telemetry_content_logging(settings.get("env"))
        return {
            "claude_user_deny_rules": any(isinstance(rule, str) and "native-agent-stack" in rule
                                          for rule in deny),
            "claude_user_secret_guard_hook": guard_hook_installed(settings, claude_dir),
            "claude_sandbox_enabled": bool(settings.get("sandbox", {}).get("enabled")),
            "claude_telemetry_logs_content": telemetry["logs_content"],
            "claude_telemetry_content_flags": telemetry["flags"],
        }
    except (OSError, ValueError, AttributeError, TypeError):
        # TypeError: well-formed JSON whose fields have the wrong type (e.g. deny = 3).
        return None


def codex_inherit_none(codex_dir: Path) -> bool | None:
    """Whether Codex shell_environment_policy.inherit is "none"; None when unreadable."""
    try:
        import tomllib
        config = tomllib.loads((codex_dir / "config.toml").read_text(encoding="utf-8"))
        # Only inherit = "none" is guarded: the repository's codex-cli 0.155.1 canary
        # measurement (gap-wave2 security-supply-chain receipt) removed every broker
        # variable only with "none"; "core" is unmeasured and exclude lists leaked names.
        return config.get("shell_environment_policy", {}).get("inherit") == "none"
    except (ImportError, OSError, ValueError, AttributeError):
        return None


def only_booleans(value) -> bool:
    return value is None or isinstance(value, bool) or (
        isinstance(value, dict) and all(isinstance(k, str) and only_booleans(v) for k, v in value.items()))


def claude_config_dir(env) -> Path:
    home = env.get("HOME") or str(Path.home())
    return Path(env.get("CLAUDE_CONFIG_DIR") or f"{home}/.claude")


def client_guards(env, root: Path = ROOT) -> dict:
    """Opt-in check of the user-level guard keys. Booleans only; no value is returned."""
    home = env.get("HOME") or str(Path.home())
    claude_dir = claude_config_dir(env)
    codex_dir = Path(env.get("CODEX_HOME") or f"{home}/.codex")
    result = dict.fromkeys(CLIENT_GUARD_KEYS)
    result.update(claude_guard_booleans(claude_dir) or {})
    result["codex_shell_environment_inherit_none"] = codex_inherit_none(codex_dir)
    result["claude_user_guard_matches_pin"] = guard_matches_pin(claude_dir, root)
    if set(result) != set(CLIENT_GUARD_KEYS) or not only_booleans(result):
        raise AssertionError("client guards must be the fixed keys with boolean values")
    return result


def pointer_status(inventory: dict, env) -> list[dict]:
    """Compare pointer metadata only: no target read, stat, resolution or expanded-path output.

    The canonical paths and aliases belong to credential-inventory.json; optional credential-file presence is separate.
    """
    rows = []
    for name in REQUIRED_POINTERS:
        entries = [entry for entry in inventory["entries"] if name in entry.get("pointer_variables", [])]
        declared = len(entries) == 1
        value = env.get(name)
        matches = bool(value) and declared and Path(value) == expand_template(entries[0]["store"]["path_template"], env)
        rows.append({"name": name, "inventory_id": entries[0]["id"] if declared else None,
                     "inventory_declared": declared, "set": bool(value), "matches_inventory": bool(matches)})
    return rows


def inspect(root: Path, inventory: dict, env=None, *, uid=None, now=None,
            with_client_guards=False, proc_keys: Path | None = None, require_pointers=False) -> dict:
    """The report. proc_keys is the kernel's key list to scan (the CLI passes PROC_KEYS); None skips it."""
    env = os.environ if env is None else env
    uid = os.getuid() if uid is None else uid
    now = time.time() if now is None else now
    entries = [inspect_entry(entry, env, uid, now) for entry in inventory["entries"]]
    exported = sorted(n for n in inventory["must_not_be_set"] if n in env)
    tracked = tracked_sensitive_names(root)
    coverage = {"undeclared_store_files": undeclared_store_files(inventory["entries"], env),
                "undeclared_keyring_keys": undeclared_keyring_keys(inventory["entries"], uid, proc_keys)}
    report = {
        "schema_version": 1,
        "entries": entries,
        "coverage": coverage,
        "warnings": [code for code, key in (("undeclared_store_file", "undeclared_store_files"),
                                            ("undeclared_keyring_key", "undeclared_keyring_keys"))
                     if coverage[key]],
        "environment": {"must_not_be_set_present": exported,
                        "native_store_path_overrides_present": native_store_overrides(inventory["entries"], env)},
        "repository": {
            "tracked_sensitive_names": tracked,
            "hooks_path_is_repo_gate": hooks_path(root) == EXPECTED_HOOKS_PATH,
            "gitleaks_on_path": shutil.which("gitleaks") is not None,
            "project_guard_settings_present": (root / ".claude/settings.json").is_file(),
        },
        "values_read": False,
    }
    if with_client_guards:
        report["client_guards"] = client_guards(env, root)
    unsafe_stored = [e["id"] for e in entries if e["state"] == "unsafe"]
    report["unsafe_required"] = [i for i in unsafe_stored
                                 if next(e for e in entries if e["id"] == i)["status"] == "required"]
    report["unsafe_stored"] = unsafe_stored
    report["result"] = "unsafe" if unsafe_stored else "ok"
    if require_pointers:
        report["pointers"] = pointer_status(inventory, env)
        report["pointer_failures"] = [row["name"] for row in report["pointers"] if not row["matches_inventory"]]
        if report["pointer_failures"] and not unsafe_stored:
            report["result"] = "pointer_mismatch"
    return report


def render_text(report: dict) -> str:
    lines = []
    for entry in report["entries"]:
        detail = ",".join(entry["findings"]) or "-"
        extra = ""
        if "mode" in entry:
            extra = f" mode={entry['mode']} dir={entry.get('directory_mode', '?')} age={entry.get('age_days', '?')}d"
        warn = f" warnings={','.join(entry['warnings'])}" if entry["warnings"] else ""
        exported = entry["variables_in_environment"]
        env_note = f" exported={','.join(exported)}" if exported else ""
        location = entry["path"] or (f"(kernel keyring {entry['key_name']}; check: kernel_keyring.py status)"
                                     if "key_name" in entry else "(not local)")
        lines.append(f"{entry['state']:<9} {entry['id']:<27} {entry['status']:<16} {location}"
                     f"{extra} findings={detail}{warn}{env_note}")
    stored, keys = report["coverage"]["undeclared_store_files"], report["coverage"]["undeclared_keyring_keys"]
    lines.append("undeclared store files (names only): "
                 + ("unknown (the store root is not a real directory)" if stored is None
                    else ",".join(stored) or "none"))
    lines.append("undeclared kernel keyring keys (names only): "
                 + ("not checked (no readable /proc/keys)" if keys is None
                    else (",".join(keys) + " (memory only; lost at the next kernel restart)" if keys else "none")))
    env_names = report["environment"]["must_not_be_set_present"]
    lines.append("environment must_not_be_set present: " + (",".join(env_names) or "none"))
    overrides = report["environment"]["native_store_path_overrides_present"]
    lines.append("environment native store path overrides present: " + (",".join(overrides) or "none"))
    for pointer in report.get("pointers", []):
        lines.append(f"pointer {pointer['name']}: set={pointer['set']} matches_inventory={pointer['matches_inventory']} "
                     f"inventory_declared={pointer['inventory_declared']} inventory_id={pointer['inventory_id']}")
    repo = report["repository"]
    tracked = repo["tracked_sensitive_names"]
    lines.append("tracked sensitive names: " + ("unknown (not a git checkout)" if tracked is None else (",".join(tracked) or "none")))
    lines.append(f"core.hooksPath={EXPECTED_HOOKS_PATH}: {repo['hooks_path_is_repo_gate']}  "
                 f"gitleaks on PATH: {repo['gitleaks_on_path']}  "
                 f"project guard settings: {repo['project_guard_settings_present']}")
    if "client_guards" in report:
        lines.append("client guards: " + json.dumps(report["client_guards"], sort_keys=True))
        if report["client_guards"].get("claude_telemetry_logs_content"):
            lines.append("claude telemetry logs content: true. Any value pasted into a prompt or passed through "
                         "a tool call is copied into the local telemetry store; rotate a pasted key "
                         "(docs/secret-storage.md)")
    lines.append(f"result: {report['result']} (lstat and names only; no credential file was opened)")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--json", action="store_true", help="print the JSON report")
    parser.add_argument("--require-pointers", action="store_true",
                        help="require all eight PAPER/SEC/PIT/IBKR path pointers to match the inventory (booleans only)")
    parser.add_argument("--client-guards", action="store_true",
                        help="also check user-level Claude/Codex settings for the guard keys, "
                             "Claude telemetry content logging and whether the installed guard matches "
                             "its pin (booleans only)")
    parser.add_argument("--proc-keys", type=Path, default=PROC_KEYS,
                        help="the kernel's key list to scan for undeclared native-agent-stack keys, names only "
                             f"(default {PROC_KEYS}; the tests pass a fixture)")
    args = parser.parse_args(argv)
    inventory_path = args.inventory or args.root / INVENTORY
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"invalid inventory: {type(error).__name__}", file=sys.stderr)
        return 2
    errors = inventory_errors(inventory, args.root)
    if errors:
        print("invalid inventory:\n" + "\n".join(errors), file=sys.stderr)
        return 2
    report = inspect(args.root, inventory, with_client_guards=args.client_guards, proc_keys=args.proc_keys,
                     require_pointers=args.require_pointers)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render_text(report))
    return 1 if report["unsafe_stored"] or report.get("pointer_failures") else 0


if __name__ == "__main__":
    raise SystemExit(main())
