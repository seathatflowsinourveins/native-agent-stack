#!/usr/bin/env python3
"""Nonmutating, value-free status check for the pinned skills manifest.

For every skill pinned in adoption/skills/manifest.json (schema `skills_trial_manifest`)
this checks, under a given home directory:

  * the canonical copy ``~/.agents/skills/<name>/SKILL.md`` exists and its sha256
    matches the manifest's ``skill_md_sha256``;
  * the global skills-CLI lock (``$XDG_STATE_HOME/skills/.skill-lock.json`` when
    ``XDG_STATE_HOME`` is set, else ``~/.agents/.skill-lock.json``) has an entry for
    the skill whose ``skillFolderHash`` equals the manifest's ``tree_sha``;
  * ``~/.claude/skills/<name>`` exists and resolves to that canonical folder (the
    link's own kind -- relative, absolute, or a plain directory copy instead of a
    link -- is reported, not just pass/fail);
  * ``~/.claude/settings.json`` ``skillOverrides[name]`` equals the manifest's
    ``claude_listing`` (a missing key defaults to ``"on"`` per Claude Code's own
    documented behaviour, so that default only satisfies a manifest of ``"on"``);
  * ``~/.codex/config.toml`` has, or lacks, a ``[[skills.config]]`` table naming the
    skill with ``enabled = false``, matching the manifest's ``codex_enabled``.

It also reports (informationally; these never affect the exit code): skills present
under ``~/.agents/skills`` or in the lock but absent from the manifest; canonical
folders with no lock entry at all; and the pinned Claude/Codex description-character
budget compared against a fresh sum over the manifest.

Nonmutating: it only ever reads (os.readlink/is_file/iterdir/read_bytes/read_text) and
never writes, installs, removes or touches a lock, a symlink or a client setting. It
opens no credential store. Output never includes a setting's value except the fixed
``skillOverrides`` state strings (on/name-only/user-invocable-only/off), and never a
file's raw content -- SKILL.md and the lock are read only to compute a digest or to
look up one field, and settings.json/config.toml are read only to pull the two fields
this checker needs; nothing else from those files is copied into the report.

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
import subprocess
import sys


DEFAULT_MANIFEST = Path("adoption/skills/manifest.json")
LOCK_BASENAME = ".skill-lock.json"
LOCK_VERSION = 3
SKILL_MD = "SKILL.md"
CLAUDE_LISTING_STATES = {"on", "name-only", "user-invocable-only", "off"}
# A skillOverrides key absent from settings.json defaults to "on" (Claude Code docs);
# only a manifest pin of "on" is satisfied by that default with no key present at all.
DEFAULT_CLAUDE_LISTING = "on"

NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
SHA1_RE = re.compile(r"[0-9a-f]{40}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED_SKILL_KEYS = {"name", "tree_sha", "skill_md_sha256", "skill_md_bytes",
                       "description_chars", "claude_listing", "codex_enabled"}


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


def resolve_lock_path(home: Path, env) -> tuple[Path, str]:
    """(path, source) where source is "xdg_state_home" or "default"."""
    xdg_state_home = env.get("XDG_STATE_HOME")
    if xdg_state_home:
        return Path(xdg_state_home) / "skills" / LOCK_BASENAME, "xdg_state_home"
    return home / ".agents" / LOCK_BASENAME, "default"


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
        except (OSError, RecursionError):
            return {"state": "cannot_resolve", "kind": kind}
        return {"state": "ok" if resolved == expected else "wrong_target", "kind": kind}
    return {"state": "not_a_symlink", "kind": "copy"}


def check_claude_listing(overrides: dict, overrides_state: str, skill: dict) -> dict:
    if overrides_state != "ok":
        return {"state": "settings_unreadable", "actual": None}
    actual = overrides.get(skill["name"], DEFAULT_CLAUDE_LISTING)
    return {"state": "ok" if actual == skill["claude_listing"] else "mismatch", "actual": actual}


def codex_disable_entries(config: dict | None) -> list[dict]:
    """The [[skills.config]] array-of-tables, or [] when absent or the wrong shape."""
    if not isinstance(config, dict):
        return []
    entries = config.get("skills", {})
    entries = entries.get("config") if isinstance(entries, dict) else None
    return [entry for entry in entries if isinstance(entry, dict)] if isinstance(entries, list) else []


def check_codex_disable(config: dict | None, config_state: str, skill: dict) -> dict:
    name, codex_enabled = skill["name"], skill["codex_enabled"]
    present = config_state == "ok" and any(
        entry.get("name") == name and entry.get("enabled") is False for entry in codex_disable_entries(config))
    if codex_enabled:
        return {"state": "unexpected_disable_entry" if present else "ok", "disable_entry_present": present}
    if config_state == "missing":
        return {"state": "config_missing", "disable_entry_present": False}
    if config_state != "ok":
        return {"state": "config_unreadable", "disable_entry_present": False}
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


def budget_report(manifest: dict) -> dict:
    skills = manifest["skills"]
    computed_claude_on = sum(s["description_chars"] for s in skills if s["claude_listing"] == "on")
    computed_codex_enabled = sum(s["description_chars"] for s in skills if s["codex_enabled"])
    declared = manifest.get("budget")
    declared = declared if isinstance(declared, dict) else {}
    claude_cap = declared.get("claude_on_cap")
    codex_cap = declared.get("codex_default_budget_chars")
    return {
        "claude_on_description_chars": {
            "manifest": declared.get("claude_on_description_chars"), "computed": computed_claude_on,
            "matches_manifest": declared.get("claude_on_description_chars") == computed_claude_on},
        "claude_on_cap": claude_cap,
        "claude_within_cap": not isinstance(claude_cap, int) or computed_claude_on <= claude_cap,
        "codex_enabled_description_chars": {
            "manifest": declared.get("codex_enabled_description_chars"), "computed": computed_codex_enabled,
            "matches_manifest": declared.get("codex_enabled_description_chars") == computed_codex_enabled},
        "codex_default_budget_chars": codex_cap,
        "codex_within_cap": not isinstance(codex_cap, int) or computed_codex_enabled <= codex_cap,
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
    agents_skills = home / ".agents" / "skills"
    claude_skills = home / ".claude" / "skills"

    lock_file, lock_source = resolve_lock_path(home, env)
    lock_data, lock_state = load_lock(lock_file)
    overrides, overrides_state = load_skill_overrides(home / ".claude" / "settings.json")
    codex_config, codex_config_state = load_codex_config(home / ".codex" / "config.toml")

    skills_report = []
    for skill in manifest["skills"]:
        name = skill["name"]
        checks = {
            "canonical": check_canonical(agents_skills, skill),
            "lock": check_lock_entry(lock_data, lock_state, skill),
            "claude_link": check_claude_link(claude_skills / name, agents_skills / name),
            "claude_listing": check_claude_listing(overrides, overrides_state, skill),
            "codex_disable": check_codex_disable(codex_config, codex_config_state, skill),
        }
        skills_report.append({"name": name, "pass": all(item["state"] == "ok" for item in checks.values()),
                              **checks})

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
        "budget": budget_report(manifest),
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
            f"codex={skill['codex_disable']['state']}")
    extra = report["extra_skills"]
    lines.append("extra skills not in manifest: " + (", ".join(
        f"{item['name']}(agents_dir={item['in_agents_dir']},lock={item['in_lock']})" for item in extra
    ) or "none"))
    lines.append("unlocked folders: " + (", ".join(report["unlocked_folders"]) or "none"))
    budget = report["budget"]
    claude_chars, codex_chars = budget["claude_on_description_chars"], budget["codex_enabled_description_chars"]
    lines.append(f"budget: claude_on computed={claude_chars['computed']} manifest={claude_chars['manifest']} "
                 f"cap={budget['claude_on_cap']} within_cap={budget['claude_within_cap']}")
    lines.append(f"budget: codex_enabled computed={codex_chars['computed']} manifest={codex_chars['manifest']} "
                 f"cap={budget['codex_default_budget_chars']} within_cap={budget['codex_within_cap']}")
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
                        help="Home directory to check (~/.agents, ~/.claude, ~/.codex)")
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


if __name__ == "__main__":
    raise SystemExit(main())
