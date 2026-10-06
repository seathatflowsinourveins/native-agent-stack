#!/usr/bin/env python3
"""Install the pinned skills trial manifest (adoption/skills/manifest.json)
through the upstream `skills` CLI, idempotently and without ever writing the
lock file or the canonical skill folders itself.

For every manifest skill, in order:

  (a) already installed and locked at the pinned revision (the canonical
      ~/.agents/skills/<name>/SKILL.md sha256 matches skill_md_sha256, and the
      global skill lock's skillFolderHash for <name> matches tree_sha) ->
      'ok': nothing is run.
  (b) a folder exists at that path but the lock has no entry for <name> (for
      example a skill installed by hand before this manifest existed) -> only
      proceed (treat like a fresh install) when its SKILL.md sha256 already
      equals the manifest's, so a local edit is never silently discarded;
      otherwise refuse with 'local-modified' unless --force.
  (c) otherwise, run `skills add <url> --skill <name> -g -y -a claude-code
      codex` (env DISABLE_TELEMETRY=1, so the run skips both telemetry and the
      add-time audit call) and re-check the same two conditions as (a). A
      mismatch after add (wrong tree, wrong bytes, or the CLI silently
      installing something else) runs `skills remove <name> -g -y -a
      claude-code codex`, then reads back the canonical folder, the lock
      entry and the claude-code link ($CLAUDE_CONFIG_DIR/skills when set, as
      the CLI resolves it), whatever that remove reported: 'rolled-back' when
      all three are gone, else 'error' with "rollback retained, in use by
      another agent" (only the remove's exit 0 with the canonical folder
      kept) or "rollback incomplete", naming what remains (see SKILL_AGENTS).
      A remove that cannot run is 'error' too, and so is a read-back that
      cannot observe them, such as an unreadable or malformed lock ("rollback
      could not be verified"). Nothing is
      deleted by hand; docs/decisions/2026-09-25-skills-trial-and-usage.md
      (Addendum 2026-09-28: M4 host removal and the scoped-remove correction)
      gives the manual procedure.

Exit status is 1 when any processed skill ends anywhere but 'ok' or
'installed' (or, under --dry-run, anywhere but 'ok' or 'planned' -- a
local-modified refusal is real even though --dry-run writes nothing).

Project verification invokes `gh api`; gh uses its own configured authentication.
The script itself never reads, prints or passes a token. Its only environment
overrides for the `skills` subprocess are HOME (so --home works for a non-default
target, e.g. in tests) and DISABLE_TELEMETRY.
It never writes ~/.agents/skills, ~/.claude/skills or
the skill lock file directly -- only the `skills` CLI does, exactly as it
would for a person running it by hand.

The global skill lock path honors $XDG_STATE_HOME exactly like the upstream CLI:
``$XDG_STATE_HOME/skills/.skill-lock.json`` when that variable is set, else ``~/.agents/.skill-lock.json``.
Only *that* lock path check reads the variable; the canonical skill folders and the claude-code symlink
stay under --home/.agents and --home/.claude regardless of $XDG_STATE_HOME. Every global path is joined as
the CLI's path.join joins it (node_path_join), so a ".." in --home or $XDG_STATE_HOME names what it wrote.

With --project-dir, the same pipeline invokes the CLI in that existing directory,
without -g, targeting --agent (default universal). The project lock is
skills-lock.json. Its computedHash is NOT a Git tree SHA: project verification
binds source/ref/skillPath to the manifest, resolves that pinned tree through
`gh api` before any add, and checks SKILL.md bytes. Every selected source/ref is
fetched first; unavailable verification is reported as unverified, not mismatch,
and a selected skill whose pinned tree differs from its manifest tree_sha refuses
the whole run before any add. A rollback cannot be relied on to undo such an add:
the native remove keeps the canonical folder and its lock entry while a detected
agent that is not a target reads that folder, as Codex does whenever $CODEX_HOME
(when unset, ~/.codex) or /etc/codex exists (src/remove.ts:293-331,
src/agents.ts:10,224-232, src/installer.ts:151-158).
Before any CLI or gh call, project containment is checked: .agents/skills,
.claude/skills and skills-lock.json, which the CLI recreates or writes
(src/installer.ts:128-131,193-200,388; src/agents.ts:158; src/local-lock.ts:65-66),
must not pass through a symlink; each selected skill's canonical and Claude paths
must resolve inside --project-dir; and --project-dir must not be --home, joined as the
CLI joins HOME and then resolved.
As with the global verifier, this attests
the source tree, not all installed support files. No lock or skill is hand-written.
Reference: vercel-labs/skills@7407f3893ad4dceab546ac002c3ef806e4000c73
src/local-lock.ts:15-37,65-66; src/add.ts:2086-2160; src/agents.ts:815-820.

A manifest marked "scope": "project" (the runtime-worker manifest) is refused
without --project-dir, and so is --print-codex-config for it, which only prints
but names each skill by its installed path in the project. A skill whose status
is pruned is never installed, in either mode, and neither is a skill whose status
is held: it waits for the measurement or gate its entry names (adoption/skills/lifecycle.md,
"Held"), and --only refuses it as held.

A global entry may name its own targets: "agents" (a subset of claude-code and codex, both by
default) and "copy": true, which installs a copy into the one target agent's own skills folder
instead of the shared canonical folder with links (skills@7407f389 README.md:91, :141-142). The
one form this manifest uses is a Claude-Code-only copy (skill-creator: Codex keeps the copy it
embeds, so no same-name folder may sit where Codex loads skills); the add and the rollback's remove
name only the entry's agents, the installed folder read back is the Claude skills folder, and
--print-codex-config prints no rule for an entry Codex never receives. Such a copy is 'ok' only as a
real folder in Claude Code's skills folder with no entry of its name in the shared canonical folder:
a link there, or a same-name entry in the shared folder, is 'misplaced', refused in every mode
(--check-only, --dry-run and --force included) with exit status 1 and nothing deleted.

--print-codex-config prints one `[[skills.config]]` table with `enabled = false` for
every codex_enabled: false skill, selecting the installed SKILL.md by `path`, never by
`name`: Codex applies a name rule to every loaded skill of that name, the bundled
.system skills it ships included (openai/codex rust-v0.159.2
codex-rs/config/src/skills_config.rs L109-119; codex-rs/skills/src/lib.rs L55-67), and
a path rule to the one skill whose canonical path_to_skills_md it names
(codex-rs/ext/skills/src/host_service.rs L366-371, host_outcome.rs L52-54). The path is
the canonical copy the CLI writes (canonical_skill_dir), which is where a global install
leaves a Codex skill (skills@7407f389 src/installer.ts:392-402) and which Codex loads
from its $HOME/.agents/skills root (codex-rs/ext/skills/src/host_roots.rs L103-108).

A manifest entry with `reuse_ref` ("adoption/skills/manifest.json") is resolved
when the manifest is read, against the one adoption skill of the same name: its pin
must equal that entry, and it takes that entry's codex_enabled and claude_listing.
An entry that restates either gate, whose pin drifted, or whose name the adoption
manifest does not carry exactly once is refused before any skill is touched. The
name, not an array index, is the key, so main may reorder or insert skills.
With --only, a name that the manifest marks pruned is reported as pruned, not unknown.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import functools
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "adoption" / "skills" / "manifest.json"
sys.path.insert(0, str(ROOT))
from scripts import skills_status as skill_state

# A manifest entry may reuse an adoption skill by naming that manifest instead of copying the
# entry (blueprints/runtime-workers/skills/manifest.json); the same-named adoption skill is the
# referenced one. load_manifest checks the pin against it and copies main's per-skill gates onto
# the entry as read, so a reused skill is never enabled where main disables it. An entry that
# restates a gate is refused.
REUSE_REF = "adoption/skills/manifest.json"
REUSE_PIN_KEYS = ("name", "source", "url", "ref", "path", "tree_sha", "skill_md_sha256")
REUSE_GATE_KEYS = ("codex_enabled", "claude_listing")
PROVENANCE_KEYS = ("source", "url", "path", "ref", "tree_sha", "skill_md_sha256")

# A manifest with "scope": "project" is only installed into a project (--project-dir).
PROJECT_SCOPE = "project"

# Paths the pinned CLI recreates or writes in a project (skills@7407f389): the canonical
# .agents/skills (src/installer.ts:128-131, rm and mkdir at 193-200 and 388), the Claude alias
# directory .claude/skills (src/agents.ts:158) and the project lock (src/local-lock.ts:65-66).
PROJECT_WRITE_PATHS = (".agents/skills", ".claude/skills", "skills-lock.json")

VERSION_CHECK_TIMEOUT = 30
ADD_TIMEOUT = 120
REMOVE_TIMEOUT = 30

# The only agents this installer writes for. `add` and the rollback `remove` both pass them, because skills
# v1.7.0's `remove` without -a selects every known agent (vercel-labs/skills src/remove.ts#L209) and would delete
# a same-named skill that another agent owns. -a stays last: the CLI reads trailing words as agent names.
# With -a, that `remove` uninstalls for the named agents only: it keeps the canonical ~/.agents/skills/<name> and
# its lock entry while any other detected agent resolves to that folder, as every universal agent (project skillsDir
# .agents/skills) does, and reports success either way. Codex reads the canonical folder while it exists, and the
# skills CLI still counts it as installed for every universal agent. So process_skill reads a rollback back from
# disk in both modes and reports what remains, or a read-back it cannot complete, as 'error'.
# Sources: skills v1.7.0 (commit 7407f389) src/remove.ts L293-340, src/agents.ts L910-912, src/installer.ts
# L157-159, and the skills@1.7.0 npm dist/cli.mjs L6834-6838, L6883-6914, isUniversalAgent L2180 and getAgentBaseDir
# L2214; Codex rust-v0.157.1 (commit 36650394) codex-rs/ext/skills/src/host_roots.rs L103-108.
SKILL_AGENTS = ("claude-code", "codex")
# Statuses the installer never installs: pruned (left by a dated decision) and held (waits for a named measurement or gate).
SKIPPED_STATUSES = ("pruned", "held")

# Real-run and --dry-run each have their own notion of "nothing left to fix":
# a dry run never executes `add`/`remove`, so 'planned' (not 'installed') is
# its success outcome, but a real local-modified refusal is still a refusal.
OK_STATUSES_REAL = {"ok", "installed"}
OK_STATUSES_DRY_RUN = {"ok", "planned"}


class InstallError(ValueError):
    """A skill could not be safely installed, verified or checked."""


def git_commit(source: str, ref: str = "HEAD") -> str:
    """Resolve a public GitHub commit before recording; never fill in a guessed ref.

    The commit endpoint and Trees oracle are the same upstream identity path used by
    vercel-labs/skills@7407f389 src/skill-lock.ts:168-171.
    """
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", source) or not re.fullmatch(r"[\w./-]+", ref):
        raise InstallError("unverified source or ref")
    try:
        done = subprocess.run(["gh", "api", f"repos/{source}/commits/{ref}"],
                              capture_output=True, text=True, stdin=subprocess.DEVNULL,
                              timeout=VERSION_CHECK_TIMEOUT, check=False)
        value = json.loads(done.stdout) if done.returncode == 0 else {}
        commit = value.get("sha")
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
        raise InstallError("public source commit could not be verified") from None
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise InstallError("public source commit could not be verified")
    return commit


def skill_metadata(folder: Path, name: str) -> dict:
    """Installed public metadata, using the manifest's PyYAML description-count contract."""
    path = folder / "SKILL.md"
    data = skill_state.read_frontmatter(path, (folder.parent,))
    description = data.get("description")
    if data.get("name") != name or not isinstance(description, str):
        raise InstallError("installed frontmatter name/description could not be verified")
    disabled = data.get("disable-model-invocation", False)
    disabled = disabled in (True, 1) or (isinstance(disabled, str) and disabled.lower() in ("true", "yes", "on", "1"))
    implicit = skill_state.implicit_policy(folder / "agents" / "openai.yaml", (folder.parent,))
    raw = skill_state.metadata_bytes(path, (folder.parent,))
    return {"skill_md_sha256": hashlib.sha256(raw).hexdigest(), "skill_md_bytes": len(raw),
            "description_chars": len(description.strip()), "upstream_disable_model_invocation": disabled,
            "upstream_allow_implicit_invocation": implicit}


def refresh_budget(manifest: dict) -> None:
    """Refresh static totals without changing repository policy or native client budgets."""
    budget = manifest.get("budget")
    if not isinstance(budget, dict):
        return
    skills = manifest["skills"]
    budget["claude_on_description_chars"] = sum(s["description_chars"] for s in skills if s["claude_listing"] == "on")
    budget["codex_enabled_description_chars"] = sum(s["description_chars"] for s in skills if s["codex_enabled"])
    budget["codex_catalog_description_chars"] = sum(s["description_chars"] for s in skill_state.codex_catalog_skills(skills))


def record_skills(manifest: dict, home: Path, only: list[str] | None = None) -> tuple[dict, dict]:
    """Tier B reconciliation: record installed identity only after an unchanged upstream tree matches it.

    Missing source identity is reported, not invented. This never installs, updates, changes settings,
    writes a host lock, or runs a model. Failed/unknown rows leave their earlier manifest entry intact.
    """
    entries = load_lock(home).get("skills", {})
    if not isinstance(entries, dict):
        entries = {}
    existing = {s["name"]: s for s in manifest["skills"]}
    folders = skill_state.installed_metadata(home, os.environ)
    names = list(dict.fromkeys(only or sorted({item["name"] for item in folders} | set(entries))))
    results = {}
    for name in names:
        if not skill_state.NAME_RE.fullmatch(name):
            results["invalid_name"] = "unverified"
            continue
        old = existing.get(name)
        if old and old.get("source_type") == "native_generated":
            folder = canonical_skill_dir(home, name)
            path = folder / "SKILL.md"
            try:
                results[name] = "recorded" if skill_state.native_generated(old) and path.is_file() and sha256_of(path) == old["skill_md_sha256"] else "unverified"
            except (InstallError, OSError, ValueError, RuntimeError, NotImplementedError):
                results[name] = "unverified"
            continue
        entry = entries.get(name, {})
        entry = entry if isinstance(entry, dict) else {}
        source = entry.get("source", old.get("source") if old else None)
        skill_path = entry.get("skillPath", old.get("path") if old else None)
        try:
            if not isinstance(source, str) or not re.fullmatch(r"[\w.-]+/[\w.-]+", source):
                raise InstallError("source identity unknown")
            if not isinstance(skill_path, str):
                raise InstallError("source skill path unknown")
            skill_path = skill_path.removesuffix("/SKILL.md")
            if "\\" in skill_path or any(part in ("", ".", "..") for part in skill_path.split("/")):
                raise InstallError("source skill path unverified")
            folder = installed_skill_dir(old, home) if old else canonical_skill_dir(home, name)
            if not folder.is_dir():
                folder = claude_skills_dir(home) / name
            metadata = skill_metadata(folder, name)
            tree = skill_state.git_tree_sha(folder, skill_state.RUNTIME_ARTIFACT_DIRS)
            lock_tree = entry.get("skillFolderHash")
            if lock_tree and lock_tree != tree:
                raise InstallError("installed content differs from public lock tree")
            ref = git_commit(source)
            if pinned_source_trees(source, ref).get(skill_path) != tree:
                # A previously recorded immutable pin remains a valid identity when HEAD has already moved.
                ref = old.get("ref") if old else None
                if not isinstance(ref, str) or not skill_state.SHA1_RE.fullmatch(ref) or pinned_source_trees(source, ref).get(skill_path) != tree:
                    raise InstallError("installed tree has no verified source commit")
            row = dict(old) if old else {"name": name, "status": "trial", "license": "Unknown", "official": False,
                                        "gap": "Recorded existing installation; task fit and audits remain unknown."}
            row.update({"source": source, "ref": ref, "path": skill_path, "tree_sha": tree,
                        "url": f"https://github.com/{source}/tree/{ref}/{skill_path}", **metadata})
            identity_changed = old is None or any(old.get(key) != row.get(key) for key in PROVENANCE_KEYS)
            if old and identity_changed:
                row["prior_pins"] = [*old.get("prior_pins", []),
                                     {key: old.get(key) for key in (*PROVENANCE_KEYS, "official", "license", "audits")}]
            if old is None or old.get("source") != source:
                # Identical bytes from a fork are not evidence that the fork is the earlier official origin.
                row["official"] = False
            row["claude_listing"] = "user-invocable-only" if metadata["upstream_disable_model_invocation"] else row.get("claude_listing", "on")
            row.setdefault("codex_enabled", True)
            if name in skill_state.TOOL_COUPLED_SKILLS:
                row.setdefault("pin_policy", {"kind": "tool-coupled", "advisory": True})
            if old is None and folder.parent == claude_skills_dir(home):
                row.update({"agents": ["claude-code"], "copy": True, "codex_enabled": False})
            if identity_changed:
                row["license"] = "Unknown"
                row["audits"] = {"gen_agent_trust_hub": "Unknown", "socket": "Unknown", "snyk": "Unknown",
                                 "url": f"https://skills.sh/{source}/{name}", "checked_at": datetime.now(timezone.utc).date().isoformat()}
            existing[name] = row
            results[name] = "recorded"
        except (InstallError, OSError, ValueError, TypeError, ImportError):
            results[name] = "unverified"
    manifest["skills"] = list(existing.values())
    refresh_budget(manifest)
    return manifest, results


def retire_skill(manifest: dict, home: Path, name: str, skills_bin: str, dry_run: bool) -> str:
    """Native remove, then observed read-back, then retained last pin. No locally authored remover.

    vercel-labs/skills@7407f389 src/remove.ts:209,293-340; a surviving universal-agent
    canonical entry is a retained removal limit, even when the CLI returns zero.
    """
    if not skill_state.NAME_RE.fullmatch(name):
        return "unknown"
    matches = [s for s in manifest["skills"] if s.get("name") == name]
    if len(matches) != 1:
        return "unknown"
    skill = matches[0]
    if skill.get("source_type") == "native_generated":
        return "unsupported-native-remove"
    if dry_run:
        return "planned"
    done = run_skills_bin(skills_bin, ["remove", name, "-g", "-y", "-a", *SKILL_AGENTS], home, REMOVE_TIMEOUT)
    if done.returncode:
        return "remove-failed"
    codex_root = skill_state.codex_config_path(home, os.environ).parent / "skills"
    if (canonical_skill_dir(home, name).exists() or canonical_skill_dir(home, name).is_symlink()
            or (claude_skills_dir(home) / name).exists() or (claude_skills_dir(home) / name).is_symlink()
            or (codex_root / name).exists() or (codex_root / name).is_symlink()
            or lock_retains(home, name)):
        return "remove-retained"
    manifest["skills"] = [s for s in manifest["skills"] if s["name"] != name]
    manifest.setdefault("excluded", []).append({"skills": name, "source": skill["source"],
        "retired": datetime.now(timezone.utc).date().isoformat(), "last_pin": dict(skill),
        "reason": "Retired through the native Skills CLI; last_pin retains the complete source for a re-add.",
        "overturn": "A later task decision re-adds the unchanged upstream last_pin through its native installer."})
    refresh_budget(manifest)
    return "retired"


def generated_skill(skill: dict, home: Path, binary: str, dry_run: bool, check_only: bool, force: bool) -> str:
    """Hugging Face's supported locally generated install; no Skills CLI tree URL or fabricated lock.

    huggingface_hub@bd4a7603 cli/skills.py:308,323-327,442-470. print(preview) adds
    one output delimiter; installation writes build_skill_md's exact bytes. HF 2.1.1 ships no remove in this contract.
    """
    if not skill_state.native_generated(skill):
        return "unsupported-native-generated"
    folder = canonical_skill_dir(home, skill["name"])
    md = folder / "SKILL.md"
    alias = claude_skills_dir(home) / skill["name"] / "SKILL.md"
    matches = md.is_file() and sha256_of(md) == skill["skill_md_sha256"]
    alias_roots = (folder.parent, alias.parent.parent)
    alias_matches = alias.is_file() and sha256_of(alias, alias_roots) == skill["skill_md_sha256"]
    if matches and alias_matches and (folder / ".hf-skill-manifest.json").is_file():
        return "ok"
    if check_only:
        return "missing-or-drifted"
    if folder.exists() and not matches and not force:
        return "local-modified"
    if dry_run:
        return "planned"
    environment = {**os.environ, "HOME": str(home), "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        version = subprocess.run([binary, "version", "--format", "json"], capture_output=True,
                                 text=True, stdin=subprocess.DEVNULL, env=environment, timeout=VERSION_CHECK_TIMEOUT)
        value = json.loads(version.stdout) if version.returncode == 0 else {}
        if not isinstance(value, dict) or value.get("version") != skill["generator"]["version"]:
            return "unverified-generator-version"
        preview = subprocess.run([binary, "skills", "preview"], capture_output=True, stdin=subprocess.DEVNULL,
                                 env=environment, timeout=VERSION_CHECK_TIMEOUT)
        raw = preview.stdout.removesuffix(b"\n")
        if preview.returncode or hashlib.sha256(raw).hexdigest() != skill["skill_md_sha256"]:
            return "unverified-generated-bytes"
        command = [binary, "skills", "add", "--global", *(["--force"] if force else [])]
        done = subprocess.run(command, capture_output=True, stdin=subprocess.DEVNULL, env=environment, timeout=ADD_TIMEOUT)
    except (OSError, subprocess.SubprocessError, ValueError):
        return "unverified-generator"
    if (done.returncode or not md.is_file() or sha256_of(md) != skill["skill_md_sha256"]
            or not alias.is_file() or sha256_of(alias, alias_roots) != skill["skill_md_sha256"]
            or not (folder / ".hf-skill-manifest.json").is_file()):
        return "install-failed"
    return "installed"


def load_manifest(path: Path, root: Path = ROOT) -> dict:
    """Read a manifest and resolve each `reuse_ref` entry against root's adoption manifest.

    The reused entry is matched there by name and must carry that pin unchanged; it then takes
    the adoption entry's current codex_enabled/claude_listing, so the two manifests cannot drift."""
    with open(path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    skills = manifest.get("skills") if isinstance(manifest, dict) else None
    reused = [s for s in skills if isinstance(s, dict) and "reuse_ref" in s] if isinstance(skills, list) else []
    if not reused:
        return manifest
    adoption_path = root / REUSE_REF
    try:
        with open(adoption_path, "r", encoding="utf-8") as handle:
            base = json.load(handle)["skills"]
        if not isinstance(base, list):
            raise TypeError("skills is not a list")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise InstallError(f"cannot resolve reuse_ref entries against {adoption_path}: {error}") from None
    for skill in reused:
        ref = skill["reuse_ref"]
        matches = [old for old in base if isinstance(old, dict) and old.get("name") == skill.get("name")]
        if ref != REUSE_REF or len(matches) != 1:
            raise InstallError(f"{skill.get('name')}: reuse_ref {ref!r} names no single {REUSE_REF} skill of that name")
        old = matches[0]
        if old.get("source_type") == "native_generated":
            raise InstallError("native-generated entries are not supported by the runtime-worker/project installer")
        drifted = [key for key in REUSE_PIN_KEYS if skill.get(key) != old.get(key)]
        if drifted:
            raise InstallError(f"{skill.get('name')}: reuse_ref differs from the adoption pin in {drifted}")
        restated = [key for key in REUSE_GATE_KEYS if key in skill]
        if restated:
            raise InstallError(f"{skill.get('name')}: reuse_ref entry restates main's {', '.join(restated)}")
        skill.update({key: old[key] for key in REUSE_GATE_KEYS if key in old})
    return manifest


def sha256_of(path: Path, roots=None) -> str:
    try:
        return hashlib.sha256(skill_state.metadata_bytes(path, roots or (path.parent.parent,))).hexdigest()
    except (OSError, ValueError, RuntimeError, NotImplementedError):
        raise InstallError("public skill metadata target could not be verified") from None


def canonical_skill_dir(home: Path, name: str, project_dir: Path | None = None) -> Path:
    """The upstream CLI's one canonical copy (src/installer.ts:128-131); Codex reads this directly and
    claude-code gets a relative symlink onto it (../../.agents/skills/<name>)."""
    return (project_dir / ".agents" / "skills" / name if project_dir is not None
            else node_path_join(str(home), ".agents", "skills", name))


def skill_agents(skill: dict) -> tuple:
    """The agents a global entry installs for: its "agents" (a subset of SKILL_AGENTS, each once) or both."""
    agents = skill.get("agents")
    if agents is None:
        return SKILL_AGENTS
    if (not isinstance(agents, list) or not agents or len(set(agents)) != len(agents)
            or any(agent not in SKILL_AGENTS for agent in agents)):
        raise InstallError(f"{skill.get('name')}: agents names claude-code and/or codex, each once")
    return tuple(agent for agent in SKILL_AGENTS if agent in agents)


def copy_mode(skill: dict) -> bool:
    """Whether a global entry installs a copy into its one agent's own skills folder instead of the canonical folder
    with links (skills@7407f389 README.md:91, :141-142). Only a Claude-Code-only copy is supported: Codex's own folder
    would hold a same-name copy beside the skills it embeds."""
    copy = skill.get("copy", False)
    if not isinstance(copy, bool):
        raise InstallError(f"{skill.get('name')}: copy is true or false")
    if copy and skill_agents(skill) != ("claude-code",):
        raise InstallError(f"{skill.get('name')}: copy installs only into Claude Code's own folder (agents [\"claude-code\"])")
    return copy


def installed_skill_dir(skill: dict, home: Path, project_dir: Path | None = None) -> Path:
    """Where an entry's installed SKILL.md lives: Claude Code's skills folder for a global copy, else the canonical folder."""
    if project_dir is None and copy_mode(skill):
        return claude_skills_dir(home) / skill["name"]
    return canonical_skill_dir(home, skill["name"], project_dir)


def copy_placement_problem(skill: dict, home: Path) -> str | None:
    """Why a global Claude-Code-only copy is not placed for Claude Code alone, else None. Its entry in Claude Code's skills
    folder must be a real folder, not a link (a link reads another folder), and the shared canonical folder, where Codex
    loads skills (codex-rs/ext/skills/src/host_roots.rs L103-108), must hold no entry of the same name, not even a
    dangling link (os.path.lexists), since Codex keeps the copy it embeds. scripts/skills_status.py fails both layouts
    the same way. Nothing here deletes either."""
    claude, shared = installed_skill_dir(skill, home), canonical_skill_dir(home, skill["name"])
    if claude.is_symlink():
        return f"{claude} is a link, not Claude Code's own copy"
    if os.path.lexists(shared):
        return f"{shared} exists, in the shared folder where Codex loads skills"
    return None


# What JavaScript's String.prototype.trim removes (ECMA-262 WhiteSpace and LineTerminator): the 25 code points
# node's trim() removed when run over every code point on 2026-09-28. str.strip() differs: it keeps U+FEFF and
# strips U+001C-U+001F and U+0085.
JS_TRIM_CHARS = ("\t\n\v\f\r              "
                 "    　﻿")


def claude_skills_dir(home: Path, project_dir: Path | None = None) -> Path:
    """Where the CLI links claude-code skills: <project>/.claude/skills, or globally
    $CLAUDE_CONFIG_DIR/skills when that is set and not blank, else home/.claude/skills
    (skills@1.7.0 npm dist/cli.mjs L1398 claudeHome, L1511 globalSkillsDir). The global
    path is trimmed as the CLI's trim() trims it (JS_TRIM_CHARS) and joined as its
    path.join joins it (node_path_join)."""
    if project_dir is not None:
        return project_dir / ".claude" / "skills"
    claude_config_dir = os.environ.get("CLAUDE_CONFIG_DIR", "").strip(JS_TRIM_CHARS)
    return node_path_join(claude_config_dir or str(home / ".claude"), "skills")


def project_containment_problem(project_dir: Path, home: Path, names: list[str]) -> str | None:
    """Why a project install could write outside the (resolved) project_dir, else None.

    skills@7407f389 recreates <project>/.agents/skills/<name> with rm and mkdir
    (src/installer.ts:193-200,388) and keeps it for another detected agent on remove
    (src/remove.ts:293-331). Through a symlink, or with --project-dir at --home, an add and its
    rollback would replace and then delete a global skill. No existing component of a path the
    CLI writes may be a symlink. A selected skill's own Claude entry may be the CLI's relative
    link onto the canonical copy, so for those paths only the resolved location is checked.
    --home is compared as the CLI's global home, path.join(HOME) (node_path_join), then resolved:
    pathlib keeps a ".." that follows a symlink or a missing folder, and names another directory."""
    if node_path_join(str(home)).resolve() == project_dir:
        return "--project-dir is --home, where the global skills and their lock live"
    for relative in PROJECT_WRITE_PATHS:
        path = project_dir
        for part in Path(relative).parts:
            path = path / part
            if path.is_symlink():
                return f"{relative} passes through the symlink {path.relative_to(project_dir)}"
    for name in names:
        for relative in (Path(".agents/skills") / name, Path(".claude/skills") / name):
            if not (project_dir / relative).resolve().is_relative_to(project_dir):
                return f"{relative} resolves outside --project-dir"
    return None


def lock_file_path(home: Path, project_dir: Path | None = None) -> Path:
    if project_dir is not None:
        return project_dir / "skills-lock.json"
    xdg_state_home = os.environ.get("XDG_STATE_HOME")  # dist/cli.mjs L3746-3750: untrimmed, any non-empty value
    if xdg_state_home:
        return node_path_join(xdg_state_home, "skills", ".skill-lock.json")
    return node_path_join(str(home), ".agents", ".skill-lock.json")


def load_lock(home: Path, project_dir: Path | None = None) -> dict:
    path = lock_file_path(home, project_dir)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def lock_retains(home: Path, name: str, project_dir: Path | None = None) -> bool:
    """A rollback's read-back of the lock. Unlike load_lock, only a missing lock file or a lock that
    parses without an entry for name confirms removal: an unreadable or malformed lock raises OSError
    or ValueError, since it may still hold the entry."""
    path = lock_file_path(home, project_dir)
    if not path.exists() and not path.is_symlink():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    skills = data.get("skills", {}) if isinstance(data, dict) else None
    if not isinstance(skills, dict):
        raise ValueError(f"{path} has no skills table")
    return name in skills


def read_lock_entry(home: Path, name: str, project_dir: Path | None = None) -> dict | None:
    skills = load_lock(home, project_dir).get("skills")
    if not isinstance(skills, dict):
        return None
    entry = skills.get(name)
    return entry if isinstance(entry, dict) else None


@functools.lru_cache(maxsize=None)
def pinned_source_trees(source: str, ref: str) -> dict[str, str]:
    """Read-only GitHub tree lookup; retain every preflight result for this run.

    Same source-tree oracle as upstream src/skill-lock.ts:168-171 (blob.ts).
    Project locks do not carry the global lock's skillFolderHash.
    """
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{source}/git/trees/{ref}?recursive=1"],
            capture_output=True, text=True, timeout=VERSION_CHECK_TIMEOUT,
            check=False, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise InstallError(f"unverified (gh unavailable): {source}@{ref}: {error}") from error
    if result.returncode:
        raise InstallError(f"unverified (gh unavailable): {source}@{ref} (gh exit {result.returncode})")
    try:
        data = json.loads(result.stdout)
        if not isinstance(data, dict) or data.get("truncated") or not isinstance(data.get("tree"), list):
            raise ValueError("incomplete pinned source tree")
        if not all(isinstance(entry, dict) for entry in data["tree"]):
            raise ValueError("malformed pinned source tree entry")
        return {entry["path"]: entry["sha"] for entry in data["tree"] if entry.get("type") == "tree"}
    except (ValueError, KeyError, TypeError) as error:
        raise InstallError(f"unverified (invalid gh response): {source}@{ref}: {error}") from error


def classify_skill(skill: dict, home: Path, project_dir: Path | None = None, agent: str = "universal") -> str:
    """'ok' (a)), 'local-modified' (b), refused), 'misplaced' (a global
    Claude-Code-only copy whose Claude entry is a link or whose name the shared
    canonical folder also holds, copy_placement_problem: refused, never 'ok'),
    or 'install' (needs an add: either a fresh install, a locked-but-mismatched
    entry, or an unlocked folder that already matches the manifest
    byte-for-byte)."""
    name = skill["name"]
    skill_dir = installed_skill_dir(skill, home, project_dir)
    if project_dir is None and copy_mode(skill) and copy_placement_problem(skill, home):
        return "misplaced"
    if project_dir is not None and agent == "claude-code":
        # skills@7407f389 src/installer.ts:254-264 replaces existing aliases,
        # including real directories. Protect them regardless of lock state.
        target = project_dir / ".claude" / "skills" / name
        if target.exists() or target.is_symlink():
            try:
                canonical_link = target.is_symlink() and target.resolve() == skill_dir.resolve()
            except (OSError, RuntimeError):
                canonical_link = False
            if not canonical_link:
                return "local-modified"
    skill_md = skill_dir / "SKILL.md"
    md_matches = skill_md.is_file() and sha256_of(skill_md) == skill["skill_md_sha256"]
    entry = read_lock_entry(home, name, project_dir)
    if entry is not None:
        if project_dir is not None:
            if agent == "claude-code":
                target_md = project_dir / ".claude" / "skills" / name / "SKILL.md"
                if not target_md.is_file() or sha256_of(target_md, (project_dir / ".agents/skills", project_dir / ".claude/skills")) != skill["skill_md_sha256"]:
                    return "install"
            identity_matches = (
                entry.get("sourceType") == "github" and entry.get("source") == skill["source"]
                and entry.get("ref") == skill["ref"]
                and entry.get("skillPath") == skill["path"] + "/SKILL.md"
                and re.fullmatch(r"[0-9a-f]{64}", str(entry.get("computedHash", ""))) is not None)
            if not (md_matches and identity_matches):
                return "install"
            tree = pinned_source_trees(skill["source"], skill["ref"]).get(skill["path"])
            return "ok" if tree == skill["tree_sha"] else "install"
        return "ok" if (md_matches and entry.get("skillFolderHash") == skill["tree_sha"]) else "install"
    # An unlocked folder counts as (b) -- local content to protect -- as soon as it
    # *exists*, not only once it happens to contain a SKILL.md: a folder with other
    # files and no SKILL.md can never satisfy md_matches, so checking is_file() here
    # instead of the folder itself would fall through to "install" and let `skills
    # add` (which recreates the target directory from scratch) silently discard it.
    if skill_dir.exists():
        return "install" if md_matches else "local-modified"
    return "install"


def run_skills_bin(skills_bin: str, args: list[str], home: Path, timeout: int,
                   project_dir: Path | None = None) -> subprocess.CompletedProcess:
    """Every skills-bin call: HOME pinned to --home (so a non-default target
    works, e.g. under test) and telemetry (and its add-time audit call) off.
    No token or credential is read or added; stdin is closed so a CLI that
    falls back to reading it gets EOF rather than the caller's terminal."""
    env = {**os.environ, "HOME": str(home), "DISABLE_TELEMETRY": "1"}
    return subprocess.run([skills_bin, *args], capture_output=True, text=True, timeout=timeout,
                          check=False, env=env, stdin=subprocess.DEVNULL, cwd=project_dir)


def verify_skills_bin(skills_bin: str, cli: dict, home: Path) -> None:
    """Refuse to run any pinned skill against an unpinned or missing binary."""
    expected = cli["version"]
    try:
        result = run_skills_bin(skills_bin, ["--version"], home, timeout=VERSION_CHECK_TIMEOUT)
    except FileNotFoundError:
        raise InstallError(f"{skills_bin} not found; install it: {cli['install']}") from None
    except (OSError, subprocess.TimeoutExpired) as error:
        raise InstallError(f"cannot run {skills_bin} --version ({error}); install it: {cli['install']}") from None
    output = (result.stdout or "") + (result.stderr or "")
    if expected not in output:
        raise InstallError(
            f"{skills_bin} --version does not report the pinned version {expected} "
            f"(got {output.strip()!r}); install it: {cli['install']}"
        )


def process_skill(skill: dict, home: Path, skills_bin: str, dry_run: bool, force: bool, quiet: bool,
                  project_dir: Path | None = None, agent: str = "universal", check_only: bool = False) -> str:
    name = skill["name"]

    def note(message: str) -> None:
        if not quiet:
            print(message)

    try:
        state = classify_skill(skill, home, project_dir, agent)
    except InstallError as error:
        print(f"{name}: {error}", file=sys.stderr)
        return "error"
    if state == "ok":
        note(f"{name}: ok (pinned ref already installed and locked)")
        return "ok"
    if state == "misplaced":
        # In every mode, --force included: an add would leave the shared entry where Codex loads it, and the rollback
        # after a failed verification would remove the Claude copy. Nothing is deleted; the person removes the entry.
        print(f"{name}: misplaced -- {copy_placement_problem(skill, home)}; a Claude-Code-only copy needs a real folder "
              f"at {installed_skill_dir(skill, home)} and no entry of its name at {canonical_skill_dir(home, name)}. "
              "Nothing was changed: remove the extra entry with the skills CLI (docs/decisions/"
              "2026-09-25-skills-trial-and-usage.md, Addendum 2026-09-28: M4 host removal and the scoped-remove "
              "correction), then run again", file=sys.stderr)
        return "misplaced"
    if check_only:
        status = "local-modified" if state == "local-modified" else "missing-or-drifted"
        note(f"{name}: {status}")
        return status
    if state == "local-modified" and not force:
        protected = ("local project content or an unmanaged Claude target" if project_dir is not None
                     else "an unlocked local SKILL.md that does not match the pinned manifest hash")
        print(f"{name}: local-modified -- refusing to overwrite {protected} "
              f"(pass --force to overwrite it)", file=sys.stderr)
        return "local-modified"

    # A global entry names its own agents (both by default) and may ask for a copy; --copy precedes -a, whose trailing
    # words the CLI reads as agent names.
    agents = skill_agents(skill)
    copy = project_dir is None and copy_mode(skill)
    add_args = ["add", skill["url"], "--skill", name, "-g", "-y", *(["--copy"] if copy else []), "-a", *agents]
    if project_dir is not None:
        # Keep the canonical folder even for a single non-universal agent.
        # src/add.ts:1775-1810 otherwise selects copy mode for one target dir.
        targets = ["universal"] if agent == "universal" else ["universal", agent]
        add_args = ["add", skill["url"], "--skill", name, "-y", "-a", *targets]
    if dry_run:
        note(f"{name}: would run: {shlex.join([skills_bin, *add_args])}")
        return "planned"

    try:
        result = run_skills_bin(skills_bin, add_args, home, timeout=ADD_TIMEOUT, project_dir=project_dir)
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"{name}: add failed to run ({error})", file=sys.stderr)
        return "error"
    if result.returncode != 0:
        print(f"{name}: add exited {result.returncode}: {result.stderr.strip()}", file=sys.stderr)
        return "error"

    try:
        verified = classify_skill(skill, home, project_dir, agent) == "ok"
    except InstallError as error:
        print(f"{name}: {error}", file=sys.stderr)
        if project_dir is not None:
            return "error"  # An unavailable oracle is not evidence of a mismatch.
        verified = False
    if verified:
        # classify_skill checks SKILL.md's sha256 and the lock's recorded tree (skills' skillFolderHash is the source
        # tree hash recorded at install, vercel-labs/skills v1.7.0 src/skill-lock.ts), not the installed support files.
        if project_dir is None:
            note(f"{name}: installed; SKILL.md sha256 matches the pin and the lock records tree {skill['tree_sha']}")
        else:
            note(f"{name}: installed; SKILL.md sha256 and project lock identity match pinned source tree {skill['tree_sha']}")
        return "installed"

    # Remove exactly the add targets. skills@7407f389 src/remove.ts:209-333
    # otherwise removes other agents' copies, and may retain shared canonical data.
    remove_args = (["remove", name, "-g", "-y", "-a", *agents] if project_dir is None
                   else ["remove", name, "-y", "-a", *targets])
    try:
        removed = run_skills_bin(skills_bin, remove_args, home, timeout=REMOVE_TIMEOUT, project_dir=project_dir)
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"{name}: verification failed and rollback could not run ({error})", file=sys.stderr)
        return "error"
    # Read back what the remove left in either mode, whatever it reported (see SKILL_AGENTS): the global
    # canonical folder, lock and Claude link (where the CLI puts it, claude_skills_dir), or the project's.
    # The CLI alone deletes them. A read-back that cannot observe them does not confirm the rollback.
    # For a Claude-Code-only copy the installed folder is the Claude one, so there is no separate link to read back.
    canonical = installed_skill_dir(skill, home, project_dir)
    claude_link = claude_skills_dir(home, project_dir) / name
    try:
        canonical_retained = canonical.exists() or canonical.is_symlink()
        lock_retained = lock_retains(home, name, project_dir)
        claude_retained = (not copy and ((project_dir is None and "claude-code" in agents) or agent == "claude-code")
                           and (claude_link.exists() or claude_link.is_symlink()))
    except (OSError, ValueError) as error:
        print(f"{name}: error: rollback could not be verified (exit {removed.returncode}; "
              f"read-back failed: {error})", file=sys.stderr)
        return "error"
    if removed.returncode or canonical_retained or lock_retained or claude_retained:
        reason = ("rollback retained, in use by another agent" if canonical_retained and not removed.returncode
                  else "rollback incomplete")
        left = [str(canonical)] if canonical_retained else []
        if lock_retained:
            left.append(f"its entry in {lock_file_path(home, project_dir)}")
        if claude_retained:
            left.append(str(claude_link))
        lock_label = "project-lock" if project_dir is not None else "lock"
        print(f"{name}: error: {reason} (exit {removed.returncode}; canonical={canonical_retained}, "
              f"{lock_label}={lock_retained}, claude-link={claude_retained})"
              + (f"; left: {', '.join(left)}" if left else ""), file=sys.stderr)
        return "error"
    print(f"{name}: installed content did not match the pinned manifest hash/tree; rolled back",
          file=sys.stderr)
    return "rolled-back"


def node_path_join(*parts: str) -> Path:
    """Node's POSIX path.join, with which the pinned CLI builds every global path it writes: the lock
    (skills@7407f389 src/skill-lock.ts:67-72, npm dist/cli.mjs L3746-3750), the canonical folder
    (src/installer.ts:128-131, dist/cli.mjs L2208-2210) and the claude-code link (dist/cli.mjs L1511).
    Node joins the non-empty parts with / and normalizes the result, so "." and ".." collapse lexically.
    os.homedir() is HOME verbatim, so only this join removes a ".." from --home; pathlib keeps it, and
    through a missing or symlinked folder it names another path than the CLI's. os.path.normpath
    normalizes as Node does, except that it keeps a leading // (POSIX leaves it implementation-defined),
    which Node collapses to /. No final part joined here ends in /, which Node would keep."""
    joined = os.path.normpath("/".join(part for part in parts if part))
    return Path("/" + joined.lstrip("/") if joined.startswith("//") else joined)


def toml_basic_string(value: str) -> str:
    """value as a TOML basic string: the quotation mark, the backslash and every control character but none other
    escaped (TOML 1.0.0, "String"). Raises InstallError for a value that is not valid Unicode text."""
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise InstallError("a skill path is not valid UTF-8 and cannot be written as a TOML string") from None
    escaped = "".join("\\" + char if char in '"\\' else
                      f"\\u{ord(char):04X}" if ord(char) < 0x20 or ord(char) == 0x7F else char for char in value)
    return f'"{escaped}"'


def print_codex_config(skills: list[dict], home: Path, project_dir: Path | None = None) -> None:
    """The `[[skills.config]]` tables that turn every codex_enabled: false manifest skill off in Codex's
    config.toml, each selecting its installed SKILL.md by path (see the module docstring), never by name."""
    blocks = []
    for skill in skills:
        if not isinstance(skill, dict) or skill.get("codex_enabled") is not False:
            continue
        if project_dir is None and "codex" not in skill_agents(skill):
            continue  # never installed where Codex loads skills (a Claude-Code-only entry): there is nothing to turn off
        name = skill.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", name):
            raise InstallError(f"codex_enabled: false skill {name!r} is not one path component")
        path = canonical_skill_dir(home, name, project_dir) / "SKILL.md"
        blocks.append(f"[[skills.config]]\npath = {toml_basic_string(str(path))}\nenabled = false")
    print("\n\n".join(blocks))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST),
                         help="Skills trial manifest to install from (default: adoption/skills/manifest.json)")
    parser.add_argument("--home", default=str(Path.home()),
                         help="Target $HOME (default: current user's; override for tests)")
    parser.add_argument("--project-dir", type=Path,
                         help="Existing project directory; uses its skills-lock.json and .agents/skills")
    parser.add_argument("--agent", choices=["universal", "claude-code", "codex"],
                         help="Project agent target (default universal); requires --project-dir")
    parser.add_argument("--skills-bin", default="skills",
                         help="Pinned 'skills' executable (default: 'skills' resolved on PATH)")
    parser.add_argument("--dry-run", action="store_true",
                         help="Report planned actions without add/remove; project source lookups still run")
    parser.add_argument("--check-only", action="store_true",
                         help="Read-only installed pin check; exit 1 for any missing/drifted skill or misplaced copy")
    recording = parser.add_mutually_exclusive_group()
    recording.add_argument("--record", action="store_true",
                           help="Reconcile verified installed source identities into the owned manifest; no install or host-lock writes")
    recording.add_argument("--retire", action="append", metavar="NAME",
                           help="Run the native global remove, observe removal, then retain last_pin in excluded[]")
    parser.add_argument("--hf-bin", default="hf", help="Native HF executable for vendor-generated hf-cli entries")
    parser.add_argument("--only", action="append", metavar="NAME",
                         help="Process only this manifest skill name; repeatable")
    parser.add_argument("--force", action="store_true",
                         help="Overwrite a local, unlocked skill folder whose SKILL.md does not "
                              "match the manifest, or an unmanaged project Claude target "
                              "(default: refuse it as local-modified)")
    parser.add_argument("--print-codex-config", action="store_true",
                         help="Print a [[skills.config]] path/enabled=false table for every "
                              "codex_enabled: false manifest skill (a reuse_ref entry takes the "
                              "adoption manifest's value), selecting its installed SKILL.md under "
                              "--home, or --project-dir for a project-scoped manifest, then exit")
    parser.add_argument("--json", action="store_true",
                         help="Print a compact, value-free {skill: status} summary instead of prose")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.agent and args.project_dir is None:
        parser.error("--agent requires --project-dir; default global targets are claude-code and codex")
    project_dir = args.project_dir.resolve() if args.project_dir is not None else None
    if project_dir is not None and not project_dir.is_dir():
        parser.error("--project-dir must be an existing directory")
    if project_dir is not None and os.path.dirname(args.skills_bin):
        args.skills_bin = str(Path(args.skills_bin).resolve())

    manifest_path = Path(args.manifest)
    try:
        manifest = load_manifest(manifest_path)
    except InstallError as error:
        print(f"install-skills failed: {error}", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError) as error:
        print(f"install-skills failed: cannot read manifest {manifest_path}: {error}", file=sys.stderr)
        return 1
    except (KeyError, TypeError) as error:
        print(f"install-skills failed: malformed reuse_ref entry ({error})", file=sys.stderr)
        return 1
    try:
        all_skills = manifest["skills"]
    except (KeyError, TypeError) as error:
        print(f"install-skills failed: manifest missing 'skills' ({error})", file=sys.stderr)
        return 1
    scope = manifest.get("scope")
    if scope not in (None, PROJECT_SCOPE):
        print(f"install-skills failed: unknown manifest scope {scope!r}", file=sys.stderr)
        return 1

    generated = [s for s in all_skills if isinstance(s, dict) and s.get("source_type") == "native_generated"]
    if generated and (project_dir is not None or manifest.get("kind") != "skills_trial_manifest"):
        print("install-skills failed: native-generated entries support only the global adoption manifest", file=sys.stderr)
        return 1
    if any(not skill_state.native_generated(s) for s in generated):
        print("install-skills failed: unverified vendor-generated provenance", file=sys.stderr)
        return 1

    if args.record or args.retire:
        if args.check_only or args.print_codex_config or args.force or project_dir is not None:
            parser.error("--record/--retire cannot be combined with check/config/force or project installation")
        try:
            before = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
            if args.record:
                manifest, results = record_skills(manifest, Path(args.home), args.only)
                ok = all(status == "recorded" for status in results.values())
            else:
                verify_skills_bin(args.skills_bin, manifest["cli"], Path(args.home))
                results = {name: retire_skill(manifest, Path(args.home), name, args.skills_bin, args.dry_run)
                           for name in dict.fromkeys(args.retire)}
                ok = all(status in ("retired", "planned") for status in results.values())
            after = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
            if not args.dry_run and after != before:
                temporary = manifest_path.with_name(manifest_path.name + ".record-tmp")
                temporary.write_text(after, encoding="utf-8")
                temporary.replace(manifest_path)
        except (InstallError, OSError, ValueError, TypeError, ImportError):
            print("install-skills failed: reconciliation or native removal could not be verified", file=sys.stderr)
            return 1
        print(json.dumps({"mode": "record" if args.record else "retire", "dry_run": args.dry_run,
                          "ok": ok, "skills": results}, sort_keys=True))
        return 0 if ok else 1

    if args.print_codex_config:
        if scope == PROJECT_SCOPE and project_dir is None:
            print(f'install-skills failed: this manifest is scoped to projects ("scope": "{PROJECT_SCOPE}"); '
                  f"pass --project-dir, whose installed SKILL.md paths the Codex tables name", file=sys.stderr)
            return 1
        try:
            print_codex_config(all_skills if isinstance(all_skills, list) else [], Path(args.home), project_dir)
        except InstallError as error:
            print(f"install-skills failed: {error}", file=sys.stderr)
            return 1
        return 0

    if scope == PROJECT_SCOPE and project_dir is None:
        print(f'install-skills failed: this manifest is scoped to projects ("scope": "{PROJECT_SCOPE}"); '
              f"pass --project-dir", file=sys.stderr)
        return 1

    home = Path(args.home)
    skills = [s for s in all_skills if not isinstance(s, dict) or s.get("status") not in SKIPPED_STATUSES]
    if args.only:
        wanted = list(dict.fromkeys(args.only))
        by_name = {s["name"]: s for s in skills if isinstance(s, dict) and "name" in s}
        # Look each name up in the whole manifest first: a pruned or held skill is known, not unknown.
        status_of = {s["name"]: s.get("status") for s in all_skills if isinstance(s, dict) and "name" in s}
        unknown = [name for name in wanted if name not in status_of]
        if unknown:
            print(f"install-skills failed: unknown --only name(s): {unknown}", file=sys.stderr)
            return 1
        pruned = [name for name in wanted if name not in by_name and status_of[name] == "pruned"]
        if pruned:
            print(f"install-skills failed: pruned --only name(s), never installed: {pruned}", file=sys.stderr)
            return 1
        held = [name for name in wanted if name not in by_name]
        if held:
            print(f"install-skills failed: held --only name(s), not installed while held: {held}", file=sys.stderr)
            return 1
        skills = [by_name[name] for name in wanted]
    if project_dir is None:
        # Each global entry's targets, checked before any add (skill_agents, copy_mode).
        try:
            for skill in skills:
                if isinstance(skill, dict):
                    skill_agents(skill)
                    copy_mode(skill)
        except InstallError as error:
            print(f"install-skills failed: {error}", file=sys.stderr)
            return 1

    if project_dir is not None:
        # Bound the API and filesystem arguments to the pinned GitHub manifest schema.
        for skill in skills:
            try:
                valid = (re.fullmatch(r"[a-z0-9][a-z0-9._-]*", skill["name"])
                         and re.fullmatch(r"[\w.-]+/[\w.-]+", skill["source"])
                         and re.fullmatch(r"[0-9a-f]{40}", skill["ref"])
                         and re.fullmatch(r"[0-9a-f]{40}", skill["tree_sha"])
                         and re.fullmatch(r"[0-9a-f]{64}", skill["skill_md_sha256"])
                         and all(part not in ("", ".", "..") for part in skill["path"].split("/"))
                         and "\\" not in skill["path"]
                         and skill["url"] == f"https://github.com/{skill['source']}/tree/{skill['ref']}/{skill['path']}")
            except (KeyError, TypeError):
                valid = False
            if not valid:
                print("install-skills failed: malformed pinned project skill", file=sys.stderr)
                return 1
        # After the schema check, so each name joined below is a single bounded path component.
        problem = project_containment_problem(project_dir, home, [skill["name"] for skill in skills])
        if problem:
            print(f"install-skills failed: project containment: {problem}; refusing before any add",
                  file=sys.stderr)
            return 1

    try:
        if not skills or any(s.get("source_type") != "native_generated" for s in skills):
            verify_skills_bin(args.skills_bin, manifest["cli"], home)
    except InstallError as error:
        print(f"install-skills failed: {error}", file=sys.stderr)
        return 1
    except (KeyError, TypeError) as error:
        print(f"install-skills failed: manifest missing 'cli' details ({error})", file=sys.stderr)
        return 1

    if project_dir is not None:
        # local-lock.ts:15-37 has computedHash, not a source tree SHA. Resolve
        # every selected source/ref before any add, using the same Trees API
        # oracle as skills@7407f389 src/skill-lock.ts:168-171. Cache all results
        # so post-add verification never depends on a second network lookup.
        try:
            for source, ref in dict.fromkeys((skill["source"], skill["ref"]) for skill in skills):
                pinned_source_trees(source, ref)
        except InstallError as error:
            print(f"install-skills failed: {error}", file=sys.stderr)
            return 1
        # Compare every selected pin before any add. A rollback after add cannot be relied on:
        # src/remove.ts:293-331 keeps the canonical folder and lock for a detected agent that reads
        # it (Codex from $CODEX_HOME, ~/.codex when unset, or /etc/codex, src/agents.ts:10 and 224-232;
        # universal agents, src/installer.ts:151-158).
        mismatched = [skill["name"] for skill in skills
                      if pinned_source_trees(skill["source"], skill["ref"]).get(skill["path"]) != skill["tree_sha"]]
        if mismatched:
            print(f"install-skills failed: pinned source tree differs from the manifest tree_sha before any add: "
                  f"{mismatched}", file=sys.stderr)
            return 1

    results: dict[str, str] = {}
    try:
        for skill in skills:
            if skill.get("source_type") == "native_generated":
                results[skill["name"]] = generated_skill(skill, home, args.hf_bin, args.dry_run, args.check_only, args.force)
                continue
            results[skill["name"]] = process_skill(skill, home, args.skills_bin, args.dry_run,
                                                    args.force, args.json, project_dir, args.agent or "universal",
                                                    args.check_only)
    except (KeyError, TypeError) as error:
        print(f"install-skills failed: malformed skill entry ({error})", file=sys.stderr)
        return 1

    ok_statuses = OK_STATUSES_DRY_RUN if args.dry_run else OK_STATUSES_REAL
    all_ok = all(status in ok_statuses for status in results.values())

    if args.json:
        print(json.dumps({"dry_run": args.dry_run, "ok": all_ok, "skills": results}, sort_keys=True))
    else:
        settled = sum(1 for status in results.values() if status in ok_statuses)
        print(f"install-skills: {settled}/{len(results)} ok")

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
