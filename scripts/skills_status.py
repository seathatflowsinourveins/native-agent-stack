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

Two kinds of entry are checked differently. A skill whose ``status`` is ``held`` waits for the
measurement or gate its entry names and is not installed by tools/adoption/install_skills.py; it is
reported as ``held`` (with whether a canonical folder is present anyway) and never fails the run. An
entry with ``"agents": ["claude-code"]`` and ``"copy": true`` is a Claude-Code-only copy: its
SKILL.md, lock entry and folder tree are checked in Claude Code's own skills folder, which must be a
real folder (not a link), and no same-name folder may sit in the shared ``~/.agents/skills``, where
Codex loads skills (``shared_copy_present``); Codex receives no rule for it.

Each path is built as the program that writes or reads it builds it: the skills CLI's
folders, lock and links with Node's ``path.join`` (``node_path_join``), Claude Code's
settings and Codex's config with their own rules (``claude_settings_path``,
``codex_config_path``).

It also reports skills present
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
left out) from ``drift`` (pinned content itself differs). Folder drift stays informational because
normal use of such a skill recreates the artifacts and ``tools/adoption/install_skills.py``
does not reinstall a folder whose SKILL.md and lock entry still match.

S4 (2026-10-06): extra native user/project skills without a current S3 ledger identity fail metadata status.
Static manifest totals do not prove that either client's live catalog fits. Explicit retained native listing
inputs carry the actual bytesPerToken/truncation signals; missing inputs remain unknown. --metadata-only
skips client configuration, supporting-file tree scans and all subprocess calls, and never starts a model.
The vendor-generated hf-cli form has a pinned generator and file digest, no fabricated Git tree or Skills CLI lock.

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
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import math
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
TOOL_COUPLED_SKILLS = frozenset({"dagu", "worktrunk", "hf-cli", "agent-browser", "chrome-devtools", "edgartools"})
_POLICY_READER = None
METADATA_LIMIT = 1_048_576


def trusted_roots(roots) -> tuple[Path, ...]:
    """A source/root symlink does not register its destination as another trusted metadata root."""
    result = []
    for root in roots:
        absolute = Path(os.path.abspath(root))
        try:
            if absolute.resolve(strict=True) == absolute and absolute.is_dir():
                result.append(absolute)
        except (OSError, RuntimeError):
            pass
    return tuple(result)


@contextmanager
def regular_stream(path: Path):
    """S3's accepted FD contract: required flags, regular-file fstat before any I/O.

    Python os.open/fstat and Linux open(2) O_NOFOLLOW/O_NONBLOCK. Parent directories and
    writers are trusted/cooperating; this is not a latency or power-loss guarantee.
    """
    nofollow, nonblock = getattr(os, "O_NOFOLLOW", None), getattr(os, "O_NONBLOCK", None)
    if not isinstance(nofollow, int) or not nofollow or not isinstance(nonblock, int) or not nonblock:
        raise NotImplementedError("required_file_flags_unavailable")
    descriptor = os.open(path, os.O_RDONLY | nofollow | nonblock)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("not_regular_metadata")
        stream = os.fdopen(descriptor, "rb")
        descriptor = None
        try:
            yield stream
        finally:
            stream.close()
    finally:
        if descriptor is not None:
            os.close(descriptor)


def metadata_bytes(path: Path, roots, limit: int = METADATA_LIMIT) -> bytes:
    """Bounded public metadata read inside explicitly enumerated, nonredirected roots.

    Directory aliases into those roots are allowed; the final metadata file is never a symlink.
    Unknown external targets are rejected before opening/reading their contents.
    """
    allowed = trusted_roots(roots)
    if not allowed or stat.S_ISLNK(path.lstat().st_mode):
        raise ValueError("unregistered_metadata_target")
    resolved = path.resolve(strict=True)
    if not any(resolved.is_relative_to(root) for root in allowed):
        raise ValueError("unregistered_metadata_target")
    with regular_stream(resolved) as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("metadata_size_limit")
    return data


def native_generated(skill: dict) -> bool:
    """Only the vendor's locally generated hf-cli form; never a generic null-tree escape.

    huggingface/huggingface_hub@bd4a7603 src/huggingface_hub/cli/_skills.py:65-73 writes
    build_skill_md() and touches an empty managed marker. No Git skill tree or Skills CLI lock is produced.
    The separate mirror is comparison provenance, not the installed file's identity.
    """
    generator, mirror = skill.get("generator"), skill.get("mirror")
    return bool(
        skill.get("source_type") == "native_generated" and skill.get("name") == "hf-cli"
        and skill.get("source") == "huggingface/huggingface_hub"
        and skill.get("path") == "src/huggingface_hub/cli/skills.py"
        and skill.get("tree_sha") is None
        and SHA1_RE.fullmatch(str(skill.get("ref", "")))
        and skill.get("url") == f"https://github.com/{skill['source']}/blob/{skill['ref']}/{skill['path']}"
        and isinstance(generator, dict) and generator.get("package") == "huggingface_hub"
        and re.fullmatch(r"\d+\.\d+\.\d+", str(generator.get("version", "")))
        and generator.get("release_tag") == "v" + generator["version"]
        and generator.get("install") == ["hf", "skills", "add", "--global"]
        and generator.get("update") == ["hf", "skills", "update", "hf-cli", "--global"]
        and generator.get("preview") == ["hf", "skills", "preview"]
        and isinstance(mirror, dict) and mirror.get("source") == "huggingface/skills"
        and mirror.get("path") == "skills/hf-cli"
        and SHA1_RE.fullmatch(str(mirror.get("ref", "")))
        and SHA1_RE.fullmatch(str(mirror.get("tree_sha", "")))
        and SHA256_RE.fullmatch(str(mirror.get("skill_md_sha256", "")))
        and isinstance(mirror.get("skill_md_bytes"), int) and not isinstance(mirror["skill_md_bytes"], bool)
        and mirror["skill_md_bytes"] > 0
    )

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
        require(native_generated(skill) or (
                    skill.get("source_type") != "native_generated"
                    and isinstance(skill["tree_sha"], str) and bool(SHA1_RE.match(skill["tree_sha"]))),
                f"{label}: tree_sha must be a git tree SHA, or declared vendor-generated hf-cli")
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
        agents = skill.get("agents", ["claude-code", "codex"])
        require(isinstance(agents, list) and bool(agents) and len(set(agents)) == len(agents)
                and all(agent in ("claude-code", "codex") for agent in agents),
                f"{label}: agents names claude-code and/or codex, each once")
        require(isinstance(skill.get("copy", False), bool), f"{label}: copy must be a boolean")
        require(not skill.get("copy") or agents == ["claude-code"],
                f"{label}: copy is supported for a Claude-Code-only entry")
    cli = data.get("cli")
    require(isinstance(cli, dict) and isinstance(cli.get("version"), str) and bool(cli["version"]),
            "cli.version must be a nonempty string")
    return data


# ---------------------------------------------------------------------------
# Filesystem-facing helpers. Each reduces what it reads to the single field or
# digest a check needs; none returns a file's raw content to its caller.
# ---------------------------------------------------------------------------

def sha256_file(path: Path, roots=()) -> str | None:
    try:
        return hashlib.sha256(metadata_bytes(path, roots)).hexdigest()
    except (OSError, ValueError, RuntimeError, NotImplementedError):
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
        if name in skip or name == "__pycache__" or name.endswith(".pyc"):
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
        digest = sha256_file(path, (agents_skills,))
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
    allowed = trusted_roots((agents_skills,))
    try:
        if not allowed or not folder.resolve(strict=True).is_relative_to(allowed[0]):
            return {"state": "unreadable"}
    except (OSError, RuntimeError):
        return {"state": "unreadable"}
    if native_generated(skill):
        return {"state": "native_generated", "git_tree_required": False,
                "managed_marker_present": (folder / ".hf-skill-manifest.json").is_file(),
                "managed_marker_format": "empty-presence-marker"}
    try:
        if git_tree_sha(folder) == skill["tree_sha"]:
            return {"state": "ok"}
        if git_tree_sha(folder, RUNTIME_ARTIFACT_DIRS) == skill["tree_sha"]:
            return {"state": "runtime_artifacts"}
    except (OSError, RecursionError):
        return {"state": "unreadable"}
    return {"state": "drift"}


def folder_tree_summary(skills_report: list[dict]) -> dict:
    summary = {"ok": 0, "runtime_artifacts": [], "drift": [], "missing": [], "unreadable": [], "held": [],
               "native_generated": [], "not_checked": []}
    for skill in skills_report:
        state = skill["folder_tree"]["state"]
        if state == "ok":
            summary["ok"] += 1
        else:
            summary[state].append(skill["name"])
    return summary


def check_lock_entry(lock_data: dict | None, lock_state: str, skill: dict) -> dict:
    if native_generated(skill):
        return {"state": "ok", "kind": "native_generated", "skills_cli_lock_required": False}
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
# Metadata coverage and retained native catalog reporting.
# ---------------------------------------------------------------------------

def extra_skills(dir_names: set[str], lock_names: set[str], manifest_names: set[str]) -> list[dict]:
    names = sorted((dir_names | lock_names) - manifest_names)
    return [{"name": name, "in_agents_dir": name in dir_names, "in_lock": name in lock_names}
            for name in names]


def ledger_identities(path: Path) -> tuple[dict, str]:
    """S3 skill_state_change v1's latest state, never an audit verdict or a credential/config reader."""
    identities = {}
    try:
        data = metadata_bytes(path, (path.parent,), limit=16 * METADATA_LIMIT).decode("utf-8")
        for line in data.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or row.get("kind") != "skill_state_change" or row.get("schema_version") != 1:
                continue
            name, scope = row.get("skill_name"), row.get("scope")
            if not isinstance(name, str) or not NAME_RE.fullmatch(name) or not isinstance(scope, str):
                continue
            after = row.get("after")
            digest = after.get("skill_md_sha256") if isinstance(after, dict) else None
            state_key = row.get("state_key")
            if not isinstance(state_key, str) or not SHA256_RE.fullmatch(state_key):
                # Legacy unbound rows cannot attest one profile's physical root or remove another's identity.
                continue
            key = (scope, name, state_key)
            if row.get("action") == "remove" or row.get("event") == "removed":
                identities.pop(key, None)
            elif isinstance(digest, str) and SHA256_RE.fullmatch(digest):
                identities[key] = digest
        return identities, "ok"
    except FileNotFoundError:
        return {}, "missing"
    except (OSError, ValueError, TypeError, RuntimeError, NotImplementedError):
        return {}, "invalid"


def metadata_state_key(canonical_path: Path) -> str:
    """S3 v1 digest([canonical SKILL.md path]); caller has already verified the descriptor/root."""
    data = json.dumps([str(canonical_path)], sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def ledger_path(home: Path, env) -> Path:
    state = env.get("XDG_STATE_HOME") or str(home / ".local" / "state")
    return node_path_join(state, "native-agent-stack", "skills", "ledger.jsonl")


def metadata_root_specs(home: Path, env, project_dir: Path | None = None) -> list[tuple[str, Path]]:
    codex_home = env.get("CODEX_HOME") or str(home / ".codex")
    roots = [("home_agents", agents_skills_dir(home)), ("home_claude", claude_skills_dir(home, env)),
             ("home_codex", node_path_join(codex_home, "skills"))]
    if project_dir is not None:
        roots.extend([("project_agents", project_dir / ".agents" / "skills"),
                      ("project_claude", project_dir / ".claude" / "skills")])
    return roots


def installed_metadata(home: Path, env, project_dir: Path | None = None) -> list[dict]:
    """Native user skill roots; shared aliases collapse to one SKILL.md identity.

    vercel-labs/skills@7407f389 src/agents.ts and Codex rust-v0.159.2 host_roots.rs.
    Bundled/plugin caches are not canonical extras: cache presence alone does not establish activation.
    """
    roots = metadata_root_specs(home, env, project_dir)
    allowed = trusted_roots(root for _scope, root in roots)
    result, seen = [], set()
    for scope, root in roots:
        if Path(os.path.abspath(root)) not in allowed:
            continue
        for name in sorted(list_agent_skill_dirs(root)):
            if name.startswith(".") or not NAME_RE.fullmatch(name):
                continue
            path = root / name / SKILL_MD
            if not os.path.lexists(path):
                continue
            try:
                digest = sha256_file(path, allowed)
                if digest is None:
                    result.append({"name": name, "scope": scope, "skill_md_sha256": None,
                                   "state_key": None, "metadata_state": "unverified"})
                    continue
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                result.append({"name": name, "scope": scope, "skill_md_sha256": digest,
                               "state_key": metadata_state_key(resolved)})
            except (OSError, RuntimeError):
                continue
    return result


def recorded_extras(manifest: dict, home: Path, env, lock_names: set[str], identities: dict,
                    project_dir: Path | None = None) -> list[dict]:
    names = {s["name"] for s in manifest["skills"]}
    installed = installed_metadata(home, env, project_dir)
    result = []
    for item in installed:
        if item["name"] not in names:
            result.append({**item, "in_agents_dir": item["scope"] == "home_agents",
                           "in_lock": item["name"] in lock_names,
                           "recorded": isinstance(item["skill_md_sha256"], str)
                           and bool(SHA256_RE.fullmatch(item["skill_md_sha256"]))
                           and isinstance(item.get("state_key"), str)
                           and identities.get((item["scope"], item["name"], item["state_key"])) == item["skill_md_sha256"]})
    present = {s["name"] for s in installed}
    for name in sorted(lock_names - names - present):
        result.append({"name": name, "scope": "home_agents", "in_agents_dir": False, "in_lock": True,
                       "skill_md_sha256": None, "recorded": False})
    return result


def read_frontmatter(path: Path, roots=()) -> dict:
    """PyYAML safe_load, the manifest's documented description counter; no source body is returned."""
    import yaml
    text = metadata_bytes(path, roots).decode("utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.DOTALL)
    if not match:
        return {}
    try:
        value = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        raise ValueError("invalid public frontmatter") from None
    return value if isinstance(value, dict) else {}


def implicit_policy(path: Path, roots=()) -> bool:
    """Reuse the reviewed native serde_yaml policy reader, not PyYAML's broader bool coercion.

    source_reviews.py:448-464 at ecfa1127 distinguishes plain false from a string 'off',
    ignored invalid metadata, and unverified input. This reader runs no executable or model.
    """
    global _POLICY_READER
    if not path.is_file():
        return True
    if _POLICY_READER is None:
        source = Path(__file__).resolve().parents[1] / "tools/sota-convergence/landscape-sweep/source_reviews.py"
        spec = importlib.util.spec_from_file_location("native_skill_policy_reader", source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _POLICY_READER = module
    implicit, _written, _note = _POLICY_READER.openai_yaml_policy(metadata_bytes(path, roots))
    if implicit is None:
        raise ValueError("native implicit policy unverified")
    return implicit


def preload_report(workflow: dict | None, home: Path, env) -> dict:
    """Report known missing role preloads; never load a role or start a model.

    Claude's agent frontmatter skills field: https://code.claude.com/docs/en/sub-agents.
    S7 variant names are taken from the routing manifest, not a second maintained variant list.
    """
    roles = workflow.get("variants", []) if isinstance(workflow, dict) else []
    if not isinstance(roles, list):
        return {"state": "unknown", "missing": []}
    roles = list(roles)
    for row in workflow.get("rows", []) if isinstance(workflow, dict) else []:
        if not isinstance(row, dict) or not isinstance(row.get("lanes"), dict):
            continue
        stage = row["lanes"].get("ultracode_stage")
        pending = stage == "inert"
        if pending:
            measure = row.get("measure", {})
            stage = measure.get("planned_ultracode_stage") if isinstance(measure, dict) else None
        if isinstance(stage, dict) and isinstance(stage.get("preload"), list):
            roles.append({"name": stage.get("agentType"), "skills": stage["preload"], "pending": pending})
    repo = Path(__file__).resolve().parents[1]
    directories = [claude_skills_dir(home, env).parent / "agents"]
    if workflow is not None:
        directories.append(repo / ".claude" / "agents")
    unverified_roles = []
    for directory in directories:
        if directory.exists() and not trusted_roots((directory,)):
            unverified_roles.append("unregistered_role_root")
            continue
        for path in sorted(directory.glob("*.md")):
            try:
                role = read_frontmatter(path, (directory,))
            except (OSError, ValueError, RuntimeError, NotImplementedError, ImportError):
                unverified_roles.append(path.stem)
                continue
            if isinstance(role.get("skills"), list):
                roles.append({"name": role.get("name", path.stem), "skills": role["skills"]})
    known = {s["name"] for s in installed_metadata(home, env)}
    plugin_unknown = set()
    for client in (".claude", ".codex"):
        cache = home / client / "plugins" / "cache"
        if not trusted_roots((cache,)):
            continue
        for path in cache.glob("*/*/*/skills/*/SKILL.md"):
            try:
                skill = read_frontmatter(path, (cache,))
                name = skill.get("name")
                if isinstance(name, str):
                    known.add(name)
                    known.add(path.parts[-5] + ":" + name)
                    plugin_unknown.add(name)
            except (OSError, ValueError, RuntimeError, NotImplementedError, ImportError):
                continue
    missing, pending_missing = [], []
    for role in roles:
        if not isinstance(role, dict):
            continue
        name, skills = role.get("name"), role.get("skills")
        if not isinstance(name, str) or not isinstance(skills, list):
            continue
        for skill in skills:
            if (isinstance(skill, str) and all(NAME_RE.fullmatch(part) for part in skill.split(":"))
                    and skill not in known):
                destination = pending_missing if role.get("pending") else missing
                item = {"role": name, "skill": skill}
                if item not in destination:
                    destination.append(item)
    return {"state": "missing" if missing else "unknown" if unverified_roles else "ok", "missing": missing,
            "unverified_roles": unverified_roles,
            "pending_missing": pending_missing,
            "variant_registry": "available" if (repo / "tools/adoption/workflow_variants.py").is_file() else "not_integrated",
            "plugin_activation": "unknown" if plugin_unknown else "not_observed"}


def native_claude_budget(listing: dict | None) -> dict:
    """Retained native listing fields, including the client's truncation signal and bytesPerToken.

    Claude Code 2.1.291 tXe()/listing builder, documented skillListingBudgetFraction:
    https://code.claude.com/docs/en/settings-reference. Never launches claude -p.
    """
    if not isinstance(listing, dict):
        return {"state": "unknown", "within_budget": None, "reason": "native_listing_not_supplied"}
    text = listing.get("listing", listing.get("content"))
    truncated = listing.get("truncatedSkills")
    ratio, fraction, window = listing.get("bytesPerToken"), listing.get("skillListingBudgetFraction"), listing.get("contextWindow")
    numbers = (ratio, fraction, window)
    if (not isinstance(text, str) or not isinstance(truncated, (list, int)) or isinstance(truncated, bool)
            or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in numbers)
            or ratio <= 0 or not 0 < fraction <= 1 or window <= 0):
        return {"state": "unknown", "within_budget": None, "reason": "native_budget_signals_incomplete"}
    # Claude's JavaScript listing builder charges String.length, including two code units for an astral glyph.
    chars = len(text.encode("utf-16-le", errors="surrogatepass")) // 2
    count = len(truncated) if isinstance(truncated, list) else truncated
    cap = math.floor(window * ratio * fraction)
    return {"state": "ok" if count == 0 and chars <= cap else "fail",
            "within_budget": count == 0 and chars <= cap, "listing_chars": chars,
            "character_budget": cap, "bytes_per_token": ratio, "context_window": window,
            "listing_budget_fraction": fraction, "truncated_skills": count,
            "scenarios": {str(w): {"character_budget": math.floor(w * ratio * fraction),
                                    "within_budget": count == 0 and chars <= math.floor(w * ratio * fraction)}
                          for w in (1_000_000, 200_000)}}


def native_codex_budget(catalog: dict | None, configured_budget: int | None) -> dict:
    """Charge actual retained catalog lines at ceil(UTF-8 bytes/4), not manifest character sums.

    openai/codex@a956835d render.rs:19-29,126-160. The 1,024 character description
    limit and budget-removal warning must be retained alongside rendered text.
    """
    if isinstance(catalog, dict):
        known_truncation = catalog.get("truncated_descriptions")
        known_warnings = catalog.get("warnings")
        removed = isinstance(known_warnings, list) and any(
            isinstance(warning, str) and "Exceeded skills context budget" in warning for warning in known_warnings)
        if (isinstance(known_truncation, list) and bool(known_truncation)) or removed:
            return {"state": "fail", "within_budget": False,
                    "truncated_descriptions": len(known_truncation) if isinstance(known_truncation, list) else None,
                    "descriptions_removed": removed}
    if isinstance(catalog, dict) and not isinstance(catalog.get("catalog"), str):
        return codex_list_budget(catalog, configured_budget)
    if not isinstance(catalog, dict):
        return {"state": "unknown", "within_budget": None, "reason": "native_catalog_not_supplied"}
    truncated, warnings = catalog.get("truncated_descriptions"), catalog.get("warnings")
    budget = catalog.get("max_context_tokens", configured_budget)
    if (not isinstance(truncated, list) or not isinstance(warnings, list)
            or not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0):
        return {"state": "unknown", "within_budget": None, "reason": "native_budget_signals_incomplete"}
    candidates = [line for line in catalog["catalog"].splitlines() if line.startswith("- ")]
    # render.rs:210-267 emits all four authority kinds, including empty-description lines.
    lines = [line for line in candidates if re.fullmatch(
        r"- .+: (?:.* )?\((?:file|executor package|cloud package|custom resource): .+\)", line)]
    if len(lines) != len(candidates):
        return {"state": "unknown", "within_budget": None, "reason": "native_catalog_entry_unparsed"}
    if not lines:
        return {"state": "unknown", "within_budget": None, "reason": "native_catalog_lines_missing"}
    charge = sum((len((line + "\n").encode("utf-8")) + 3) // 4 for line in lines)
    cap = min(budget, 10_000)
    removed = any(isinstance(w, str) and "Exceeded skills context budget" in w for w in warnings)
    passed = not truncated and not removed and charge <= cap
    return {"state": "ok" if passed else "fail", "within_budget": passed,
            "catalog_skills": len(lines), "catalog_tokens": charge, "configured_budget_tokens": cap,
            "truncated_descriptions": len(truncated), "descriptions_removed": removed}


def codex_list_budget(response: dict, configured_budget: int | None) -> dict:
    """Native SkillsListResponse: an unaliased charge over enabled rows is an upper bound.

    openai/codex@a956835d app-server-protocol/schema/json/v2/SkillsListResponse.json exposes
    enabled/name/description/path, not implicit policy or renderer warnings. Including an
    explicit-only skill conservatively overcounts; it never understates the catalog charge.
    """
    payload = response.get("result", response)
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return {"state": "unknown", "within_budget": None, "reason": "native_catalog_not_supplied"}
    budget = response.get("max_context_tokens", configured_budget)
    if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
        return {"state": "unknown", "within_budget": None, "reason": "native_budget_not_supplied"}
    lines, clipped = [], 0
    seen = set()
    for group in payload["data"]:
        if not isinstance(group, dict) or group.get("errors") or not isinstance(group.get("skills"), list):
            return {"state": "unknown", "within_budget": None, "reason": "native_list_errors"}
        for skill in group["skills"]:
            if not isinstance(skill, dict) or not isinstance(skill.get("enabled"), bool):
                return {"state": "unknown", "within_budget": None, "reason": "native_skill_metadata_incomplete"}
            if not skill["enabled"]:
                continue
            name, description, locator = skill.get("name"), skill.get("description"), skill.get("path")
            if not all(isinstance(value, str) for value in (name, description, locator)):
                return {"state": "unknown", "within_budget": None, "reason": "native_skill_metadata_incomplete"}
            path = Path(locator)
            if not path.is_absolute() or path.name != SKILL_MD or not path.is_file():
                return {"state": "unknown", "within_budget": None, "reason": "current_native_skill_source_unavailable"}
            if (name, locator) in seen:
                continue
            seen.add((name, locator))
            if len(description) > CODEX_CATALOG_DESCRIPTION_CHARS:
                clipped += 1
                description = description[:CODEX_CATALOG_DESCRIPTION_CHARS - 3] + "..."
            lines.append(f"- {name}: {description} (file: {locator})")
    tokens = sum((len((line + "\n").encode("utf-8")) + 3) // 4 for line in lines)
    cap = min(budget, 10_000)
    certain = clipped == 0 and tokens <= cap
    return {"state": "ok" if certain else "unknown", "within_budget": True if certain else None,
            "catalog_skills": len(lines), "catalog_tokens_upper_bound": tokens,
            "configured_budget_tokens": cap, "possible_description_caps": clipped,
            "representation": "native_skills_list_unaliased_upper_bound", "renderer_warning_observed": False}


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


def budget_report(manifest: dict, skills_root: str | None = None, *, claude_listing: dict | None = None,
                  codex_catalog: dict | None = None, configured_budget: int | None = None) -> dict:
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
    claude_live = native_claude_budget(claude_listing)
    codex_live = native_codex_budget(codex_catalog, configured_budget)
    codex_budget = codex_live.get("configured_budget_tokens")
    return {
        "claude_on_description_chars": {
            "manifest": declared.get("claude_on_description_chars"), "computed": computed_claude_on,
            "matches_manifest": declared.get("claude_on_description_chars") == computed_claude_on},
        "claude_on_cap": None,
        "claude_within_cap": claude_live["within_budget"],
        "claude_live": claude_live,
        "codex_enabled_description_chars": {
            "manifest": declared.get("codex_enabled_description_chars"), "computed": computed_codex_enabled,
            "matches_manifest": declared.get("codex_enabled_description_chars") == computed_codex_enabled},
        "codex_catalog_skills": len(shown),
        "codex_catalog_description_chars": {
            "manifest": declared.get("codex_catalog_description_chars"), "computed": computed_codex_catalog,
            "matches_manifest": declared.get("codex_catalog_description_chars") == computed_codex_catalog},
        "codex_catalog_estimated_tokens": estimated_tokens,
        "codex_configured_budget_tokens": codex_budget,
        "codex_within_budget": codex_live["within_budget"],
        "codex_live": codex_live,
        "manifest_estimate_is_live_acceptance": False,
        # Only when no budget is configured and the context window is unknown (render.rs L138-151): metadata.
        "codex_fallback_budget_chars": declared.get("codex_fallback_budget_chars"),
    }


def tool_coupling_report(skills: list[dict], lock_data: dict | None, releases: dict | None) -> list[dict]:
    """An advisory comparison with retained binary-release metadata; no deny or automatic restore.

    A release input maps skill name to {version, tree_sha}; native-generated HF compares generator version.
    Unknown binary state stays unknown. Ordinary guidance rows have no tool-coupled policy.
    """
    result = []
    for skill in skills:
        policy = skill.get("pin_policy", {})
        if (not isinstance(policy, dict) or policy.get("kind") != "tool-coupled") and skill["name"] not in TOOL_COUPLED_SKILLS:
            continue
        release = releases.get(skill["name"]) if isinstance(releases, dict) else None
        release = release if isinstance(release, dict) else {}
        lock = (lock_data or {}).get("skills", {}).get(skill["name"], {})
        lock = lock if isinstance(lock, dict) else {}
        if native_generated(skill):
            expected, actual = skill["generator"]["version"], release.get("version")
        else:
            expected, actual = release.get("tree_sha"), lock.get("skillFolderHash")
        known = expected is not None and actual is not None
        restore_ref = release.get("ref")
        qualified = isinstance(restore_ref, str) and SHA1_RE.fullmatch(restore_ref)
        restore_url = f"https://github.com/{skill.get('source')}/tree/{restore_ref}/{skill.get('path')}" if qualified else skill.get("url")
        result.append({"name": skill["name"], "advisory": True,
                       "state": "aligned" if known and expected == actual else "mismatch" if known else "unknown",
                       "proposal_provenance": "native_generated_update" if native_generated(skill)
                       else "retained_binary_release" if qualified else "recorded_pin_release_unverified",
                       "restore_proposal": skill["generator"]["update"] if native_generated(skill)
                       else ["skills", "add", restore_url, "--skill", skill["name"], "-g", "-y",
                             "-a", "claude-code", "codex"] if isinstance(restore_url, str) else None})
    return result


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

def inspect(manifest: dict, home: Path, env=None, skills_bin: str | None = None, *,
            metadata_only: bool = False, ledger: Path | None = None, claude_listing: dict | None = None,
            codex_catalog: dict | None = None, workflow: dict | None = None, releases: dict | None = None,
            project_dir: Path | None = None) -> dict:
    env = os.environ if env is None else env
    agents_skills = agents_skills_dir(home)
    claude_skills = claude_skills_dir(home, env)

    lock_file, lock_source = resolve_lock_path(home, env)
    lock_data, lock_state = load_lock(lock_file)
    codex_config_file = codex_config_path(home, env)
    if metadata_only:
        overrides, overrides_state = {}, "not_checked"
        codex_config, codex_config_state = {}, "not_checked"
    else:
        overrides, overrides_state = load_skill_overrides(claude_settings_path(home, env))
        codex_config, codex_config_state = load_codex_config(codex_config_file)
    listing_skipped = {"state": "not_checked", "actual": None, "checked": False}

    def folder_check(root, skill):
        return {"state": "not_checked"} if metadata_only else check_folder_tree(root, skill)

    def checks_pass(checks):
        return all(item["state"] == "ok" or metadata_only and item["state"] == "not_checked"
                   for item in checks.values())

    skills_report = []
    for skill in manifest["skills"]:
        name = skill["name"]
        if skill.get("status") == "held":
            # Not installed while held (tools/adoption/install_skills.py skips it); a folder left from an earlier
            # install is reported, never failed.
            present = os.path.lexists(agents_skills / name) or os.path.lexists(claude_skills / name)
            held = {"state": "held"}
            skills_report.append({"name": name, "pass": True, "held": True, "present": present,
                                  "canonical": held, "lock": held, "claude_link": {"state": "held", "kind": "held"},
                                  "claude_listing": {"state": "held", "actual": None},
                                  "codex_disable": {"state": "held", "disable_entry_present": False},
                                  "folder_tree": held})
            continue
        if skill.get("copy"):
            # A Claude-Code-only copy: everything is in Claude Code's own folder, which must not be a link, and the
            # shared folder where Codex loads skills holds no same-name copy. Codex needs no rule for it.
            link = check_claude_link(claude_skills / name, claude_skills / name)
            if link["state"] == "not_a_symlink":
                link = {"state": "ok", "kind": "copy"}
            elif link["state"] == "ok":
                link = {"state": "is_a_symlink", "kind": link["kind"]}
            shared = os.path.lexists(agents_skills / name)
            checks = {
                "canonical": check_canonical(claude_skills, skill),
                "lock": check_lock_entry(lock_data, lock_state, skill),
                "claude_link": link,
                "claude_listing": listing_skipped if metadata_only else check_claude_listing(overrides, overrides_state, skill),
                "codex_disable": {"state": "shared_copy_present" if shared else "ok", "disable_entry_present": False},
            }
            skills_report.append({"name": name, "pass": checks_pass(checks),
                                  "scope": "claude-code copy", **checks,
                                  "folder_tree": folder_check(claude_skills, skill)})
            continue
        checks = {
            "canonical": check_canonical(agents_skills, skill),
            "lock": check_lock_entry(lock_data, lock_state, skill),
            "claude_link": check_claude_link(claude_skills / name, agents_skills / name),
            "claude_listing": listing_skipped if metadata_only else check_claude_listing(overrides, overrides_state, skill),
            # skills 1.7.0 installs a global Codex skill only at this canonical folder (src/installer.ts L392-402),
            # which Codex loads from its $HOME/.agents/skills root (ext/skills/src/host_roots.rs L103-108).
            "codex_disable": {"state": "not_checked", "disable_entry_present": None, "checked": False} if metadata_only else check_codex_disable(codex_config, codex_config_state, skill,
                                                 skill_md=agents_skills / name / SKILL_MD, home=home,
                                                 config_dir=codex_config_file.parent),
        }
        if native_generated(skill) and checks["claude_link"]["state"] == "not_a_symlink":
            # HF cli/skills.py:_create_symlink supports a copy when a symlink cannot be created.
            if sha256_file(claude_skills / name / SKILL_MD, (claude_skills, agents_skills)) == skill["skill_md_sha256"]:
                checks["claude_link"] = {"state": "ok", "kind": "native-generated copy"}
        skills_report.append({"name": name, "pass": checks_pass(checks),
                              **checks, "folder_tree": folder_check(agents_skills, skill)})

    dir_names = list_agent_skill_dirs(agents_skills)
    lock_names = set(lock_data["skills"]) if lock_state == "ok" else set()
    manifest_names = {skill["name"] for skill in manifest["skills"]}
    identities, ledger_state = ledger_identities(ledger or ledger_path(home, env))
    extras = recorded_extras(manifest, home, env, lock_names, identities, project_dir)
    unverified_roots = [scope for scope, root in metadata_root_specs(home, env, project_dir)
                        if os.path.lexists(root) and not trusted_roots((root,))]
    preloads = preload_report(workflow, home, env)
    native_skills = codex_config.get("skills", {}) if isinstance(codex_config, dict) else {}
    configured = native_skills.get("max_context_tokens") if isinstance(native_skills, dict) else None
    budget = budget_report(manifest, os.path.realpath(agents_skills), claude_listing=claude_listing,
                           codex_catalog=codex_catalog, configured_budget=configured)

    report = {
        "schema_version": 1,
        "metadata_only": metadata_only,
        "lock": {"source": lock_source, "state": lock_state,
                 "version": lock_data.get("version") if lock_state == "ok" else None,
                 "version_matches": lock_state == "ok" and lock_data.get("version") == LOCK_VERSION},
        "claude_settings": {"state": overrides_state},
        "codex_config": {"state": codex_config_state},
        "skills": skills_report,
        "extra_skills": extras,
        "ledger": {"state": ledger_state},
        "metadata_roots": {"state": "unknown" if unverified_roots else "ok", "unverified": unverified_roots},
        "unlocked_folders": unlocked_folders(dir_names, lock_names),
        "budget": budget,
        "preloads": preloads,
        "tool_coupling": tool_coupling_report(manifest["skills"], lock_data, releases),
        "folder_trees": folder_tree_summary(skills_report),
    }
    required_pass = (all(item["pass"] for item in skills_report) and all(item["recorded"] for item in extras)
                     and not unverified_roots
                     and preloads["state"] != "missing"
                     and budget["claude_live"]["state"] != "fail" and budget["codex_live"]["state"] != "fail")
    if skills_bin and not metadata_only:
        report["cli_version"] = check_cli_version(skills_bin, manifest["cli"]["version"])
        required_pass = required_pass and report["cli_version"]["matches_manifest"]
    report["result"] = "ok" if required_pass else "fail"
    return report


def render_text(report: dict) -> str:
    lines = ["scope: metadata only; client configuration and model discovery not checked"] if report.get("metadata_only") else []
    for skill in report["skills"]:
        link, listing = skill["claude_link"], skill["claude_listing"]
        lines.append(
            f"{'ok' if skill['pass'] else 'fail':<5} {skill['name']:<32} "
            f"canonical={skill['canonical']['state']} lock={skill['lock']['state']} "
            f"link={link['state']}({link['kind']}) listing={listing['state']}({listing['actual']}) "
            f"codex={skill['codex_disable']['state']} tree={skill['folder_tree']['state']}")
    extra = report["extra_skills"]
    lines.append("extra skills not in manifest: " + (", ".join(
        f"{item['name']}(agents_dir={item['in_agents_dir']},lock={item['in_lock']},recorded={item.get('recorded')})" for item in extra
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
    lines.append(f"native budget: claude={budget['claude_live']['state']} codex={budget['codex_live']['state']} "
                 "(manifest estimates are metadata; no fresh model job)")
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
    parser.add_argument("--project-dir", type=Path, help="Also report native project skill roots (metadata-only defaults to cwd)")
    parser.add_argument("--metadata-only", action="store_true", help="Filesystem and ledger only; no client settings or subprocess calls")
    parser.add_argument("--ledger", type=Path, help="S3 skill_state_change JSONL ledger (default under XDG state/home)")
    parser.add_argument("--claude-listing", type=Path, help="Retained native listing and bytesPerToken/truncatedSkills signals; never launches Claude")
    parser.add_argument("--codex-catalog", type=Path, help="Retained native rendered catalog with truncation/warning signals; never launches Codex")
    parser.add_argument("--workflow-manifest", type=Path, help="Routing manifest whose variant preloads to check")
    parser.add_argument("--tool-releases", type=Path, help="Retained binary release metadata for advisory skill coupling checks")
    parser.add_argument("--json", action="store_true", help="Print the machine-readable JSON report")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as error:
        print(f"invalid manifest: {error}", file=sys.stderr)
        return 2
    inputs = {}
    try:
        for key in ("claude_listing", "codex_catalog", "workflow_manifest", "tool_releases"):
            path = getattr(args, key)
            if path is not None and (not args.metadata_only or key == "workflow_manifest"):
                value = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(value, dict):
                    raise ValueError("expected a native metadata object")
                inputs[key] = value
    except (OSError, ValueError):
        print("invalid retained metadata input", file=sys.stderr)
        return 2
    report = inspect(manifest, args.home, skills_bin=args.skills_bin, metadata_only=args.metadata_only,
                     ledger=args.ledger, claude_listing=inputs.get("claude_listing"),
                     codex_catalog=inputs.get("codex_catalog"), workflow=inputs.get("workflow_manifest"),
                     releases=inputs.get("tool_releases"),
                     project_dir=args.project_dir or (Path.cwd() if args.metadata_only else None))
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
