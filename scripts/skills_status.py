#!/usr/bin/env python3
"""Nonmutating, value-free status check for the pinned skills manifest.

For every skill pinned in adoption/skills/manifest.json (schema `skills_trial_manifest`)
this checks, under a given home directory:

  * the canonical copy ``~/.agents/skills/<name>/SKILL.md`` exists and its sha256
    matches the manifest's ``skill_md_sha256``;
  * the global skills-CLI lock (``$XDG_STATE_HOME/skills/.skill-lock.json`` when
    ``XDG_STATE_HOME`` is set, else ``~/.agents/.skill-lock.json``) has an entry for
    the skill whose ``skillFolderHash`` equals the manifest's ``tree_sha``;
  * ``~/.claude/skills/<name>`` (``$CLAUDE_CONFIG_DIR/skills/<name>`` when that is set and
    not blank) exists and resolves to that canonical folder (the
    link's own kind -- relative, absolute, or a plain directory copy instead of a
    link -- is reported, not just pass/fail);
  * ``~/.claude/settings.json`` (under ``$CLAUDE_CONFIG_DIR`` when set) ``skillOverrides[name]``
    equals the manifest's
    ``claude_listing`` (a missing key defaults to ``"on"`` per Claude Code's own
    documented behaviour, so that default only satisfies a manifest of ``"on"``);
  * ``~/.codex/config.toml`` (``$CODEX_HOME/config.toml`` when set) has, or lacks, a
    ``[[skills.config]]`` table with ``enabled = false`` that selects the skill,
    matching the manifest's ``codex_enabled``. A ``path`` selector matches when it names the
    installed ``~/.agents/skills/<name>/SKILL.md``, resolved as Codex resolves both sides
    (``codex_rule_path``); a ``name`` selector matches the name, but for a name Codex's own
    bundled skills carry (``CODEX_BUNDLED_SKILL_NAMES``) it is a failure, because Codex
    applies a name rule to every loaded skill of that name and so hides its bundled copy too.

Each path is built as the program that writes or reads it builds it: the skills CLI's
folders, lock and links with Node's ``path.join`` (``node_path_join``), Claude Code's
settings and Codex's config with their own rules (``claude_settings_path``,
``codex_config_path``).

It also reports (informationally; these never affect the exit code): skills present
under ``~/.agents/skills`` or in the lock but absent from the manifest; canonical
folders with no lock entry at all; the pinned Claude/Codex description-character
sums compared against a fresh sum over the manifest; Codex's catalog of the skills it
shows the model, estimated in tokens as its renderer charges it (``codex_catalog_tokens``),
against the manifest's ``codex_configured_budget_tokens``; and, per skill, whether the
canonical folder's on-disk git tree SHA-1 still equals the manifest's ``tree_sha``.
The lock's ``skillFolderHash`` is written at install time and never recomputed, so it
cannot see a file changed after install (a skill whose own ``uv run`` creates
``scripts/.venv`` and rewrites ``scripts/uv.lock`` inside its installed folder, for
example); the folder check recomputes the tree from disk, and separates ``runtime_artifacts``
(the tree matches once ``__pycache__``, ``.venv``, ``node_modules`` and tool caches are
left out) from ``drift`` (pinned content itself differs). It stays informational because
normal use of such a skill recreates the artifacts and ``tools/adoption/install_skills.py``
does not reinstall a folder whose SKILL.md and lock entry still match.

Nonmutating: it only ever reads (os.readlink/lstat/listdir/is_file/iterdir/read_bytes/read_text/realpath) and
never writes, installs, removes or touches a lock, a symlink or a client setting. It
opens no credential store. Output never includes a setting's value except the fixed
``skillOverrides`` state strings (on/name-only/user-invocable-only/off) -- a value that
is not one of those four strings is reported as the fixed ``invalid_value`` placeholder
instead of being echoed -- and never a file's raw content -- SKILL.md and the lock are
read only to compute a digest or to look up one field, and settings.json/config.toml
are read only to pull the two fields this checker needs; nothing else from those files
is copied into the report.

Exit status: 0 when every required check above passes for every manifest skill (and,
if ``--skills-bin`` was given, its ``--version`` matches ``cli.version``); 1 when any
of them fails; 2 when the manifest itself cannot be read or does not match the
expected shape.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import unicodedata


DEFAULT_MANIFEST = Path("adoption/skills/manifest.json")
LOCK_BASENAME = ".skill-lock.json"
LOCK_VERSION = 3
SKILL_MD = "SKILL.md"
CLAUDE_LISTING_STATES = {"on", "name-only", "user-invocable-only", "off"}
# A skillOverrides key absent from settings.json defaults to "on" (Claude Code docs);
# only a manifest pin of "on" is satisfied by that default with no key present at all.
DEFAULT_CLAUDE_LISTING = "on"
# overrides.get(name) can be any JSON value (a secret-shaped string, a number, a list,
# a dict...) since settings.json is foreign input; a value that is not one of the four
# strings above is reported as this fixed placeholder, never echoed verbatim.
INVALID_CLAUDE_LISTING = "invalid_value"

# Directories a skill's own tooling creates inside its installed folder at run time
# (interpreter caches, a project virtualenv, package installs, tool caches). Upstream
# trees do not carry them; the folder check leaves them out for its runtime_artifacts state.
RUNTIME_ARTIFACT_DIRS = frozenset({"__pycache__", ".venv", "node_modules", ".pytest_cache",
                                   ".ruff_cache", ".mypy_cache"})

NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
SHA1_RE = re.compile(r"[0-9a-f]{40}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED_SKILL_KEYS = {"name", "tree_sha", "skill_md_sha256", "skill_md_bytes",
                       "description_chars", "claude_listing", "codex_enabled"}

# Codex's bundled system skills at openai/codex rust-v0.159.2: codex-rs/skills/src/assets/samples/*/SKILL.md, each
# frontmatter name equal to its folder, installed into CODEX_HOME/skills/.system (codex-rs/skills/src/lib.rs L55-67
# and L77-82). A [[skills.config]] name rule disables every loaded skill of that name (codex-rs/config/src/
# skills_config.rs L109-119), so a name rule for one of these names hides Codex's own copy as well.
CODEX_BUNDLED_SKILL_NAMES = frozenset({"imagegen", "openai-docs", "review-agent", "skill-creator", "skill-installer"})

# How Codex renders and charges a skill its catalog shows the model (openai/codex rust-v0.159.2
# codex-rs/ext/skills/src/render.rs): the line "- {name}: {description} (file: {path})" (L258-267, the path being the
# skill's canonical SKILL.md, ext/skills/src/provider/host.rs L129-140), a description over 1,024 characters cut to
# 1,021 plus "..." (L23-24, L1158-1174), and, under a token budget, each line with its newline charged
# ceil(bytes / 4) (L154-160 and L25; utils/string/src/truncate.rs L71-74).
CODEX_CATALOG_DESCRIPTION_CHARS = 1024
CODEX_CATALOG_BYTES_PER_TOKEN = 4

# What JavaScript's trim() removes, with which skills 1.7.0 trims $CLAUDE_CONFIG_DIR (npm dist/cli.mjs L1398):
# ECMA-262 WhiteSpace and LineTerminator. A copy of tools/adoption/install_skills.py JS_TRIM_CHARS (see
# node_path_join for why this checker keeps copies); tests/test_skills_status.py asserts that they agree.
JS_TRIM_CHARS = ("\t\n\v\f\r              "
                 "    　﻿")


class ManifestError(ValueError):
    """Unreadable or structurally invalid skills manifest; messages hold no host paths."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ManifestError(message)


def load_manifest(path: Path) -> dict:
    """Read and structurally validate the pinned skills manifest; never partially returns."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ManifestError(f"cannot read manifest: {type(error).__name__}") from error
    require(isinstance(data, dict), "manifest must be an object")
    skills = data.get("skills")
    require(isinstance(skills, list) and bool(skills), "skills must be a nonempty array")
    seen: set[str] = set()
    for index, skill in enumerate(skills):
        label = f"skills[{index}]"
        require(isinstance(skill, dict), f"{label}: expected object")
        missing = REQUIRED_SKILL_KEYS - set(skill)
        require(not missing, f"{label}: missing keys {sorted(missing)}")
        name = skill["name"]
        require(isinstance(name, str) and bool(NAME_RE.match(name)), f"{label}: invalid name")
        require(name not in seen, f"{label}: duplicate name {name}")
        seen.add(name)
        require(isinstance(skill["tree_sha"], str) and bool(SHA1_RE.match(skill["tree_sha"])),
                f"{label}: tree_sha must be a 40-hex git tree SHA")
        require(isinstance(skill["skill_md_sha256"], str) and bool(SHA256_RE.match(skill["skill_md_sha256"])),
                f"{label}: skill_md_sha256 must be a 64-hex sha256 digest")
        require(isinstance(skill["skill_md_bytes"], int) and not isinstance(skill["skill_md_bytes"], bool)
                and skill["skill_md_bytes"] >= 0, f"{label}: skill_md_bytes must be a non-negative integer")
        require(isinstance(skill["description_chars"], int) and not isinstance(skill["description_chars"], bool)
                and skill["description_chars"] >= 0, f"{label}: description_chars must be a non-negative integer")
        require(skill["claude_listing"] in CLAUDE_LISTING_STATES, f"{label}: unknown claude_listing")
        require(isinstance(skill["codex_enabled"], bool), f"{label}: codex_enabled must be a boolean")
        require(isinstance(skill.get("upstream_allow_implicit_invocation", True), bool),
                f"{label}: upstream_allow_implicit_invocation must be a boolean")
    cli = data.get("cli")
    require(isinstance(cli, dict) and isinstance(cli.get("version"), str) and bool(cli["version"]),
            "cli.version must be a nonempty string")
    return data


# ---------------------------------------------------------------------------
# Filesystem-facing helpers. Each reduces what it reads to the single field or
# digest a check needs; none returns a file's raw content to its caller.
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def git_tree_sha(folder: Path, skip: frozenset[str] = frozenset()) -> str | None:
    """The git tree SHA-1 of an on-disk folder, hashed the way git hashes a tree object.

    A regular file is a blob with mode 100755 when its owner-execute bit is set, else
    100644; a symlink is a blob of its target bytes with mode 120000 (never followed); a
    subdirectory is a 40000 tree; an empty directory is omitted, as git omits it. Entries
    sort by name bytes, a directory's name compared with a trailing "/". Names in ``skip``
    are left out at every level. Returns None for a folder with nothing to hash; raises
    OSError when an entry cannot be read. Only digests leave this function.
    """
    entries = []
    for name in os.listdir(folder):
        if name in skip:
            continue
        path = folder / name
        info = os.lstat(path)
        raw_name = os.fsencode(name)
        if stat.S_ISLNK(info.st_mode):
            entries.append((raw_name, b"120000", _git_blob_sha(os.readlink(os.fsencode(path))), False))
        elif stat.S_ISDIR(info.st_mode):
            subtree = git_tree_sha(path, skip)
            if subtree is not None:
                entries.append((raw_name, b"40000", bytes.fromhex(subtree), True))
        elif stat.S_ISREG(info.st_mode):
            mode = b"100755" if info.st_mode & stat.S_IXUSR else b"100644"
            entries.append((raw_name, mode, _git_blob_sha(path.read_bytes()), False))
    if not entries:
        return None
    entries.sort(key=lambda entry: entry[0] + b"/" if entry[3] else entry[0])
    body = b"".join(mode + b" " + raw_name + b"\0" + digest for raw_name, mode, digest, _ in entries)
    return hashlib.sha1(b"tree %d\0" % len(body) + body).hexdigest()


def _git_blob_sha(data: bytes) -> bytes:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).digest()


def resolve_lock_path(home: Path, env) -> tuple[Path, str]:
    """(path, source), source "xdg_state_home" or "default"; joined as the CLI joins it (node_path_join)."""
    xdg_state_home = env.get("XDG_STATE_HOME")
    if xdg_state_home:
        return node_path_join(xdg_state_home, "skills", LOCK_BASENAME), "xdg_state_home"
    return node_path_join(str(home), ".agents", LOCK_BASENAME), "default"


def agents_skills_dir(home: Path) -> Path:
    """The CLI's global canonical folder, path.join(os.homedir(), ".agents", "skills") (dist/cli.mjs L2208-2210)."""
    return node_path_join(str(home), ".agents", "skills")


def claude_skills_dir(home: Path, env) -> Path:
    """Where the CLI links claude-code skills globally: path.join(claudeHome, "skills"), claudeHome being
    $CLAUDE_CONFIG_DIR trimmed by JavaScript's trim() when that leaves it non-empty, else path.join(HOME, ".claude")
    (dist/cli.mjs L1398, L1511), as tools/adoption/install_skills.py claude_skills_dir reads it back."""
    config_dir = (env.get("CLAUDE_CONFIG_DIR") or "").strip(JS_TRIM_CHARS)
    return node_path_join(config_dir, "skills") if config_dir else node_path_join(str(home), ".claude", "skills")


def claude_settings_path(home: Path, env) -> Path:
    """Where Claude Code reads user settings: under $CLAUDE_CONFIG_DIR when set (code.claude.com/docs/en/env-vars and
    /settings). Its installed 2.1.284 bundle joins path.join(path.resolve(dir), "settings.json") with
    dir = (CLAUDE_CONFIG_DIR ?? path.join(os.homedir(), ".claude")).normalize("NFC"): unlike the skills CLI's link
    folder (claude_skills_dir), the variable is not trimmed, and a set but empty value still counts."""
    config_dir = env.get("CLAUDE_CONFIG_DIR")
    base = config_dir if config_dir is not None else str(node_path_join(str(home), ".claude"))
    return node_path_join(os.path.abspath(unicodedata.normalize("NFC", base)), "settings.json")


def codex_config_path(home: Path, env) -> Path:
    """Where Codex reads config.toml: under $CODEX_HOME, else ~/.codex (developers.openai.com/codex/config-advanced,
    "Config and state locations"). Codex rust-v0.157.1 (codex-rs/utils/home-dir/src/lib.rs find_codex_home) takes a
    non-empty CODEX_HOME untrimmed and canonicalizes it, so a ".." there is resolved on disk, through any symlink,
    which a pathlib join leaves to the operating system too; path.join would name another file. Without it, HOME/.codex
    is normalized lexically (utils/absolute-path/src/absolutize.rs normalize_path), as path.join does. The skills
    CLI's trimmed codexHome (dist/cli.mjs L1397, L1575-1577) names Codex's skills folder and detects Codex; it reads
    no config.toml."""
    codex_home = env.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home) / "config.toml"
    return node_path_join(str(home), ".codex", "config.toml")


def load_lock(path: Path) -> tuple[dict | None, str]:
    """(lock dict, state) where state is "ok", "missing" or "invalid"."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, "missing"
    except OSError:
        return None, "invalid"
    try:
        data = json.loads(text)
    except ValueError:
        return None, "invalid"
    if not isinstance(data, dict) or not isinstance(data.get("skills"), dict):
        return None, "invalid"
    return data, "ok"


def load_skill_overrides(path: Path) -> tuple[dict, str]:
    """(skillOverrides dict, state); a missing settings.json is "ok" with {} since Claude's
    own default then applies uniformly. Only the skillOverrides value ever leaves this
    function; every other settings.json field is discarded here, not merely unread."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, "ok"
    except OSError:
        return {}, "invalid"
    try:
        data = json.loads(text)
    except ValueError:
        return {}, "invalid"
    if not isinstance(data, dict):
        return {}, "invalid"
    overrides = data.get("skillOverrides", {})
    return (overrides if isinstance(overrides, dict) else {}), "ok"


def load_codex_config(path: Path) -> tuple[dict | None, str]:
    """(parsed config, state); state is "ok", "missing" or "invalid"."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, "missing"
    except OSError:
        return None, "invalid"
    try:
        import tomllib  # standard library from Python 3.11; older interpreters report it unreadable
        data = tomllib.loads(text)
    except (ImportError, ValueError):
        return None, "invalid"
    return (data, "ok") if isinstance(data, dict) else (None, "invalid")


def list_agent_skill_dirs(agents_skills: Path) -> set[str]:
    try:
        return {entry.name for entry in agents_skills.iterdir() if entry.is_dir()}
    except OSError:
        return set()


# ---------------------------------------------------------------------------
# Per-skill checks. Each takes already-loaded state and returns a small dict
# with a "state" of "ok" on pass, plus whatever extra field is documented.
# ---------------------------------------------------------------------------

def check_canonical(agents_skills: Path, skill: dict) -> dict:
    path = agents_skills / skill["name"] / SKILL_MD
    if path.is_file():
        digest = sha256_file(path)
        if digest is None:
            return {"state": "unreadable"}
        return {"state": "ok" if digest == skill["skill_md_sha256"] else "sha_mismatch"}
    if path.exists() or path.is_symlink():
        return {"state": "not_a_file"}
    return {"state": "missing"}


def check_folder_tree(agents_skills: Path, skill: dict) -> dict:
    """Informational: the canonical folder's on-disk git tree against the manifest tree_sha.

    ok -- the whole folder hashes to tree_sha; runtime_artifacts -- it does once
    RUNTIME_ARTIFACT_DIRS are left out; drift -- pinned content differs even then;
    missing / unreadable -- no folder, or an entry could not be read.
    """
    folder = agents_skills / skill["name"]
    if not folder.is_dir():
        return {"state": "missing"}
    try:
        if git_tree_sha(folder) == skill["tree_sha"]:
            return {"state": "ok"}
        if git_tree_sha(folder, RUNTIME_ARTIFACT_DIRS) == skill["tree_sha"]:
            return {"state": "runtime_artifacts"}
    except (OSError, RecursionError):
        return {"state": "unreadable"}
    return {"state": "drift"}


def folder_tree_summary(skills_report: list[dict]) -> dict:
    summary = {"ok": 0, "runtime_artifacts": [], "drift": [], "missing": [], "unreadable": []}
    for skill in skills_report:
        state = skill["folder_tree"]["state"]
        if state == "ok":
            summary["ok"] += 1
        else:
            summary[state].append(skill["name"])
    return summary


def check_lock_entry(lock_data: dict | None, lock_state: str, skill: dict) -> dict:
    if lock_state != "ok":
        return {"state": "lock_unreadable"}
    entry = lock_data["skills"].get(skill["name"])
    if not isinstance(entry, dict):
        return {"state": "missing_entry"}
    return {"state": "ok" if entry.get("skillFolderHash") == skill["tree_sha"] else "hash_mismatch"}


def check_claude_link(link: Path, canonical: Path) -> dict:
    if not os.path.lexists(link):
        return {"state": "missing", "kind": "missing"}
    if os.path.islink(link):
        kind = "absolute" if os.path.isabs(os.readlink(link)) else "relative"
        try:
            resolved, expected = link.resolve(), canonical.resolve()
        except (OSError, RecursionError, RuntimeError):
            # A symlink cycle raises RuntimeError("Symlink loop from ...") from Path.resolve()
            # on CPython 3.11/3.12 (verified empirically; 3.13+ tolerates it silently instead
            # in non-strict mode), not OSError/RecursionError -- caught here so one looping
            # skill is reported, not an uncaught crash of the whole status check.
            return {"state": "cannot_resolve", "kind": kind}
        return {"state": "ok" if resolved == expected else "wrong_target", "kind": kind}
    return {"state": "not_a_symlink", "kind": "copy"}


def check_claude_listing(overrides: dict, overrides_state: str, skill: dict) -> dict:
    if overrides_state != "ok":
        return {"state": "settings_unreadable", "actual": None}
    actual = overrides.get(skill["name"], DEFAULT_CLAUDE_LISTING)
    state = "ok" if actual == skill["claude_listing"] else "mismatch"
    # `actual` is foreign input and may be any JSON value, not necessarily one of the four
    # documented strings (or even a hashable type) -- never return it verbatim; only one of
    # the known states, or the fixed placeholder, ever reaches the report.
    reported = actual if isinstance(actual, str) and actual in CLAUDE_LISTING_STATES else INVALID_CLAUDE_LISTING
    return {"state": state, "actual": reported}


def codex_disable_entries(config: dict | None) -> list[dict]:
    """The [[skills.config]] array-of-tables, or [] when absent or the wrong shape."""
    if not isinstance(config, dict):
        return []
    entries = config.get("skills", {})
    entries = entries.get("config") if isinstance(entries, dict) else None
    return [entry for entry in entries if isinstance(entry, dict)] if isinstance(entries, list) else []


def codex_rule_selector(entry: dict) -> tuple[str, str] | None:
    """("path", value) or ("name", trimmed value) for an entry Codex turns into a rule, else None: an entry with
    both selectors or neither, or with a blank name, is ignored (openai/codex rust-v0.159.2
    codex-rs/config/src/skills_config.rs L188-210)."""
    path, name = entry.get("path"), entry.get("name")
    if isinstance(path, str) and name is None:
        return "path", path
    if isinstance(name, str) and path is None and name.strip():
        return "name", name.strip()
    return None


def codex_rule_path(value: str, home: Path, config_dir: Path) -> str:
    """The file a path selector names, resolved as Codex resolves it at openai/codex rust-v0.159.2: a leading "~" or
    "~/" expands against the home (codex-rs/utils/absolute-path/src/lib.rs L28-44); a relative path joins the folder
    config.toml is in (codex-rs/config/src/loader/mod.rs L573-582 and L1424-1431); the result is normalized
    lexically ("." dropped, ".." popping the previous component, absolutize.rs L22-45) and then canonicalized when it
    exists (skills_config.rs L188-192). realpath after that lexical step reads only what exists."""
    if value == "~" or value.startswith("~/"):
        value = str(home) + "/" + value[1:].lstrip("/")
    if not os.path.isabs(value):
        value = str(config_dir) + "/" + value
    return os.path.realpath(node_path_join(value))


def check_codex_disable(config: dict | None, config_state: str, skill: dict, skill_md: Path | None = None,
                        home: Path | None = None, config_dir: Path | None = None) -> dict:
    """Whether an `enabled = false` rule selects the skill's installed copy.

    A name rule selects every loaded skill of the name (skills_config.rs L109-119); for a name in
    CODEX_BUNDLED_SKILL_NAMES that includes Codex's own copy, reported as name_entry_hides_bundled_skill. A path rule
    selects the one skill whose canonical SKILL.md it names (host_service.rs L366-371, host_outcome.rs L52-54): with
    skill_md, home and config_dir known, the rule's path must resolve (codex_rule_path) to skill_md's; without them,
    its last two components must be the skill's folder name and SKILL.md. Presence only: a later enabling rule, which
    Codex applies in order (skills_config.rs L91-93), is not modelled."""
    name, codex_enabled = skill["name"], skill["codex_enabled"]
    expected = os.path.realpath(skill_md) if skill_md is not None and home is not None and config_dir is not None \
        else None
    selected = set()
    for entry in (codex_disable_entries(config) if config_state == "ok" else []):
        selector = codex_rule_selector(entry) if entry.get("enabled") is False else None
        if selector is None:
            continue
        kind, value = selector
        if kind == "name":
            matches = value == name
        elif expected is not None:
            try:
                matches = codex_rule_path(value, home, config_dir) == expected
            except (OSError, ValueError, RuntimeError):  # e.g. an escaped NUL, which no path can hold
                matches = False
        else:
            parts = Path(value).parts
            matches = parts[-2:] == (name, SKILL_MD)
        if matches:
            selected.add(kind)
    present = bool(selected)
    if codex_enabled:
        return {"state": "unexpected_disable_entry" if present else "ok", "disable_entry_present": present}
    if config_state == "missing":
        return {"state": "config_missing", "disable_entry_present": False}
    if config_state != "ok":
        return {"state": "config_unreadable", "disable_entry_present": False}
    if "name" in selected and name in CODEX_BUNDLED_SKILL_NAMES:
        return {"state": "name_entry_hides_bundled_skill", "disable_entry_present": True}
    return {"state": "ok" if present else "missing_disable_entry", "disable_entry_present": present}


# ---------------------------------------------------------------------------
# Informational-only reporting (never gates the exit code).
# ---------------------------------------------------------------------------

def extra_skills(dir_names: set[str], lock_names: set[str], manifest_names: set[str]) -> list[dict]:
    names = sorted((dir_names | lock_names) - manifest_names)
    return [{"name": name, "in_agents_dir": name in dir_names, "in_lock": name in lock_names}
            for name in names]


def unlocked_folders(dir_names: set[str], lock_names: set[str]) -> list[str]:
    return sorted(dir_names - lock_names)


def codex_catalog_skills(skills: list[dict]) -> list[dict]:
    """The manifest skills Codex's catalog shows the model: enabled, and not kept to an explicit $name by
    agents/openai.yaml allow_implicit_invocation: false (ext/skills/src/provider/host.rs L144-149, catalog.rs
    L261-263; the flag defaults to true, skills/src/model.rs L22-28), recorded as upstream_allow_implicit_invocation."""
    return [s for s in skills if s["codex_enabled"] and s.get("upstream_allow_implicit_invocation", True)]


def codex_catalog_tokens(skills: list[dict], skills_root: str) -> int:
    """Codex's token charge for the unaliased catalog lines of these skills (CODEX_CATALOG_*), each located at
    <skills_root>/<name>/SKILL.md. description_chars stands in for the description's UTF-8 bytes, which it
    undercounts by the extra bytes of any non-ASCII character. Codex prints root aliases instead only where they
    cost less (render.rs L535-556), and bundled and plugin skills share the same budget."""
    total = 0
    for skill in skills:
        chars = min(skill["description_chars"], CODEX_CATALOG_DESCRIPTION_CHARS)
        name = skill["name"]
        locator = f"(file: {skills_root}/{name}/{SKILL_MD})"
        line_bytes = len(f"- {name}: ".encode("utf-8")) + chars + (1 if chars else 0) + len(locator.encode("utf-8"))
        total += -(-(line_bytes + 1) // CODEX_CATALOG_BYTES_PER_TOKEN)
    return total


def budget_report(manifest: dict, skills_root: str | None = None) -> dict:
    """skills_root: the canonical skills folder as Codex renders it (default: the current user's)."""
    skills = manifest["skills"]
    computed_claude_on = sum(s["description_chars"] for s in skills if s["claude_listing"] == "on")
    computed_codex_enabled = sum(s["description_chars"] for s in skills if s["codex_enabled"])
    shown = codex_catalog_skills(skills)
    computed_codex_catalog = sum(s["description_chars"] for s in shown)
    if skills_root is None:
        skills_root = os.path.realpath(agents_skills_dir(Path.home()))
    estimated_tokens = codex_catalog_tokens(shown, skills_root)
    declared = manifest.get("budget")
    declared = declared if isinstance(declared, dict) else {}
    claude_cap = declared.get("claude_on_cap")
    codex_budget = declared.get("codex_configured_budget_tokens")
    return {
        "claude_on_description_chars": {
            "manifest": declared.get("claude_on_description_chars"), "computed": computed_claude_on,
            "matches_manifest": declared.get("claude_on_description_chars") == computed_claude_on},
        "claude_on_cap": claude_cap,
        "claude_within_cap": not isinstance(claude_cap, int) or computed_claude_on <= claude_cap,
        "codex_enabled_description_chars": {
            "manifest": declared.get("codex_enabled_description_chars"), "computed": computed_codex_enabled,
            "matches_manifest": declared.get("codex_enabled_description_chars") == computed_codex_enabled},
        "codex_catalog_skills": len(shown),
        "codex_catalog_description_chars": {
            "manifest": declared.get("codex_catalog_description_chars"), "computed": computed_codex_catalog,
            "matches_manifest": declared.get("codex_catalog_description_chars") == computed_codex_catalog},
        "codex_catalog_estimated_tokens": estimated_tokens,
        "codex_configured_budget_tokens": codex_budget,
        "codex_within_budget": not isinstance(codex_budget, int) or estimated_tokens <= codex_budget,
        # Only when no budget is configured and the context window is unknown (render.rs L138-151): metadata.
        "codex_fallback_budget_chars": declared.get("codex_fallback_budget_chars"),
    }


def check_cli_version(binary: str, manifest_version: str) -> dict:
    """Runs "<binary> --version" (never the skills CLI's mutating subcommands)."""
    try:
        result = subprocess.run([binary, "--version"], stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {"invoked": False, "exit_code": None, "output": None, "matches_manifest": False}
    output = (result.stdout or result.stderr or "").strip()
    return {"invoked": True, "exit_code": result.returncode, "output": output or None,
            "matches_manifest": manifest_version in output}


# ---------------------------------------------------------------------------
# Orchestration.
# ---------------------------------------------------------------------------

def inspect(manifest: dict, home: Path, env=None, skills_bin: str | None = None) -> dict:
    env = os.environ if env is None else env
    agents_skills = agents_skills_dir(home)
    claude_skills = claude_skills_dir(home, env)

    lock_file, lock_source = resolve_lock_path(home, env)
    lock_data, lock_state = load_lock(lock_file)
    overrides, overrides_state = load_skill_overrides(claude_settings_path(home, env))
    codex_config_file = codex_config_path(home, env)
    codex_config, codex_config_state = load_codex_config(codex_config_file)

    skills_report = []
    for skill in manifest["skills"]:
        name = skill["name"]
        checks = {
            "canonical": check_canonical(agents_skills, skill),
            "lock": check_lock_entry(lock_data, lock_state, skill),
            "claude_link": check_claude_link(claude_skills / name, agents_skills / name),
            "claude_listing": check_claude_listing(overrides, overrides_state, skill),
            # skills 1.7.0 installs a global Codex skill only at this canonical folder (src/installer.ts L392-402),
            # which Codex loads from its $HOME/.agents/skills root (ext/skills/src/host_roots.rs L103-108).
            "codex_disable": check_codex_disable(codex_config, codex_config_state, skill,
                                                 skill_md=agents_skills / name / SKILL_MD, home=home,
                                                 config_dir=codex_config_file.parent),
        }
        skills_report.append({"name": name, "pass": all(item["state"] == "ok" for item in checks.values()),
                              **checks, "folder_tree": check_folder_tree(agents_skills, skill)})

    dir_names = list_agent_skill_dirs(agents_skills)
    lock_names = set(lock_data["skills"]) if lock_state == "ok" else set()
    manifest_names = {skill["name"] for skill in manifest["skills"]}

    report = {
        "schema_version": 1,
        "lock": {"source": lock_source, "state": lock_state,
                 "version": lock_data.get("version") if lock_state == "ok" else None,
                 "version_matches": lock_state == "ok" and lock_data.get("version") == LOCK_VERSION},
        "claude_settings": {"state": overrides_state},
        "codex_config": {"state": codex_config_state},
        "skills": skills_report,
        "extra_skills": extra_skills(dir_names, lock_names, manifest_names),
        "unlocked_folders": unlocked_folders(dir_names, lock_names),
        "budget": budget_report(manifest, os.path.realpath(agents_skills)),
        "folder_trees": folder_tree_summary(skills_report),
    }
    required_pass = all(item["pass"] for item in skills_report)
    if skills_bin:
        report["cli_version"] = check_cli_version(skills_bin, manifest["cli"]["version"])
        required_pass = required_pass and report["cli_version"]["matches_manifest"]
    report["result"] = "ok" if required_pass else "fail"
    return report


def render_text(report: dict) -> str:
    lines = []
    for skill in report["skills"]:
        link, listing = skill["claude_link"], skill["claude_listing"]
        lines.append(
            f"{'ok' if skill['pass'] else 'fail':<5} {skill['name']:<32} "
            f"canonical={skill['canonical']['state']} lock={skill['lock']['state']} "
            f"link={link['state']}({link['kind']}) listing={listing['state']}({listing['actual']}) "
            f"codex={skill['codex_disable']['state']} tree={skill['folder_tree']['state']}")
    extra = report["extra_skills"]
    lines.append("extra skills not in manifest: " + (", ".join(
        f"{item['name']}(agents_dir={item['in_agents_dir']},lock={item['in_lock']})" for item in extra
    ) or "none"))
    lines.append("unlocked folders: " + (", ".join(report["unlocked_folders"]) or "none"))
    trees = report["folder_trees"]
    lines.append(f"folder trees (informational): ok={trees['ok']} "
                 + " ".join(f"{state}={','.join(trees[state]) or 'none'}"
                            for state in ("runtime_artifacts", "drift", "missing", "unreadable")))
    budget = report["budget"]
    claude_chars, codex_chars = budget["claude_on_description_chars"], budget["codex_enabled_description_chars"]
    lines.append(f"budget: claude_on computed={claude_chars['computed']} manifest={claude_chars['manifest']} "
                 f"cap={budget['claude_on_cap']} within_cap={budget['claude_within_cap']}")
    catalog_chars = budget["codex_catalog_description_chars"]
    lines.append(f"budget: codex_enabled computed={codex_chars['computed']} manifest={codex_chars['manifest']}")
    lines.append(f"budget: codex_catalog skills={budget['codex_catalog_skills']} "
                 f"description_chars computed={catalog_chars['computed']} manifest={catalog_chars['manifest']} "
                 f"estimated_tokens={budget['codex_catalog_estimated_tokens']} "
                 f"configured_budget_tokens={budget['codex_configured_budget_tokens']} "
                 f"within_budget={budget['codex_within_budget']} "
                 f"(fallback_chars={budget['codex_fallback_budget_chars']} when the window is unknown)")
    lock = report["lock"]
    lines.append(f"lock: source={lock['source']} state={lock['state']} version={lock['version']}")
    lines.append(f"claude settings: state={report['claude_settings']['state']}  "
                 f"codex config: state={report['codex_config']['state']}")
    if "cli_version" in report:
        cli_version = report["cli_version"]
        lines.append(f"cli --version: invoked={cli_version['invoked']} output={cli_version['output']} "
                     f"matches_manifest={cli_version['matches_manifest']}")
    lines.append(f"result: {report['result']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST,
                        help="Path to the pinned skills manifest")
    parser.add_argument("--home", type=Path, default=Path.home(),
                        help="Home directory to check (~/.agents, ~/.claude, ~/.codex); a set CLAUDE_CONFIG_DIR, "
                             "CODEX_HOME or XDG_STATE_HOME moves its folder as the CLI or client does")
    parser.add_argument("--skills-bin", help="Executable whose '--version' is compared to manifest cli.version")
    parser.add_argument("--json", action="store_true", help="Print the machine-readable JSON report")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as error:
        print(f"invalid manifest: {error}", file=sys.stderr)
        return 2
    report = inspect(manifest, args.home, skills_bin=args.skills_bin)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render_text(report))
    return 0 if report["result"] == "ok" else 1


def node_path_join(*parts: str) -> Path:
    """Node's POSIX path.join, with which skills 1.7.0 builds every global path it writes: the lock
    (vercel-labs/skills@7407f389 src/skill-lock.ts:67-72, npm dist/cli.mjs L3746-3750), the canonical folder
    (L2208-2210) and the claude-code link folder (L1511). The non-empty parts are joined with / and normalized,
    so "." and ".." collapse lexically and a leading // becomes / (os.path.normpath alone keeps it). pathlib
    keeps a "..", which through a missing or symlinked folder names another file than the CLI's.
    tools/adoption/install_skills.py applies the same join. This checker keeps its own copy because
    evidence/artifacts/skills-listing-restore-20260928/tree_drift_check.py executes it from its own bytes and
    records their sha256 (load_checker); tests/test_skills_status.py asserts that the paths both build agree."""
    joined = os.path.normpath("/".join(part for part in parts if part))
    return Path("/" + joined.lstrip("/") if joined.startswith("//") else joined)


if __name__ == "__main__":
    raise SystemExit(main())
