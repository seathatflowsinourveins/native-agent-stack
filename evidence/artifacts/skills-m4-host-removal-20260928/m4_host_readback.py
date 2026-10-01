#!/usr/bin/env python3
"""Read-only, value-free read-back of the 2026-09-28 M4 host removal of verification-before-completion.

Usage:
  python3 m4_host_readback.py <checkout> <base revision> <settings backup directory> \
      <upstream skills v1.7.0 src/agents.ts> > readback.json

Reads, never writes: the global skills folder and lock, the Claude and Codex skill folders, the two
installed profile files, the user settings' skillOverrides (key count, presence and equality with the
template at <base revision>, never a value), the labelled settings backup (existence, mode, key count
and presence), the checkout (tracked and on-disk project-scope copies, which an unscoped remove run
there would also clean) and the presence of the environment variables that relocate an agent's
folder (presence only). It also parses the pinned upstream agents.ts for the depth of every agent's
default global skill path below home. Prints counts, booleans, digests and one UTC stamp; records no path.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

NAME = "verification-before-completion"
BACKUP_LABEL = "settings.json.20260928T183120Z.pre-m4-override-drop"
INSTALLED = {"hooks/token-lanes-block.builder.md": "adoption/hooks/claude/token-lanes-block.builder.md",
             "agents/isolated-builder.md": "adoption/agents/claude/isolated-builder.md"}
RELOCATING_VARS = ("CODEX_HOME", "CLAUDE_CONFIG_DIR", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "SARVAM_HOME", "VIBE_HOME",
                   "HERMES_HOME", "AUTOHAND_HOME", "GROK_HOME", "APPDATA", "FLATPAK_XDG_CONFIG_HOME")
DEFAULT_HOMES = {"home": "~", "configHome": "~/.config", "codexHome": "~/.codex", "claudeHome": "~/.claude",
                 "sarvamHome": "~/.sarvam", "vibeHome": "~/.vibe", "hermesHome": "~/.hermes",
                 "autohandHome": "~/.autohand", "grokHome": "~/.grok"}


def git_show(checkout: Path, rev: str, path: str) -> bytes:
    return subprocess.run(["git", "-C", str(checkout), "show", f"{rev}:{path}"], capture_output=True,
                          check=True).stdout


def present(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def agent_global_depths(agents_ts: Path) -> dict:
    """Depth below home of <globalSkillsDir>/<name> for every agent, with every relocating variable unset."""
    lines = agents_ts.read_text().split("\n")
    starts = [(m.group(1), n) for n, line in enumerate(lines) for m in [re.match(r"^  '?([a-z0-9-]+)'?: \{$", line)] if m]
    depths, no_global, other = {}, [], []
    for index, (name, start) in enumerate(starts):
        end = starts[index + 1][1] if index + 1 < len(starts) else len(lines)
        found = re.search(r"globalSkillsDir: ([^\n]+),", "\n".join(lines[start:end]))
        expression = found.group(1).strip() if found else "undefined"
        joined = re.fullmatch(r"join\((\w+)((?:, '[^']*')*)\)", expression)
        if expression == "undefined":
            no_global.append(name)
        elif joined and joined.group(1) in DEFAULT_HOMES:
            parts = [DEFAULT_HOMES[joined.group(1)]] + [p.strip().strip("'") for p in joined.group(2).split(",") if p.strip()]
            depths[name] = len("/".join(parts).split("/"))  # '~' stands in for the <name> segment
        else:
            other.append(name)
    deepest = max(depths.values())
    return {"agents": len(starts), "max_depth_of_global_copy_below_home": deepest,
            "deepest_agents": sorted(n for n, d in depths.items() if d == deepest),
            "agents_without_global_dir": sorted(no_global), "agents_resolved_by_function": sorted(other)}


def main() -> int:
    checkout, rev, backups, agents_ts = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
    home = Path.home()
    env = {var: var in os.environ for var in RELOCATING_VARS}
    codex_home = Path(os.environ.get("CODEX_HOME") or home / ".codex")
    claude_home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or home / ".claude")
    state_home = os.environ.get("XDG_STATE_HOME")
    lock_path = Path(state_home) / "skills" / ".skill-lock.json" if state_home else home / ".agents" / ".skill-lock.json"
    lock = json.loads(lock_path.read_text())
    lock_names = set(lock.get("skills", {}))
    entries = {p.name for p in (home / ".agents" / "skills").iterdir()}
    manifest_names = {s["name"] for s in json.loads(git_show(checkout, rev, "adoption/skills/manifest.json"))["skills"]}

    installed = {}
    for relative, repo_path in INSTALLED.items():
        data = (claude_home / relative).read_bytes()
        installed[relative] = {"sha256": hashlib.sha256(data).hexdigest(),
                               "equals_repo_file_at_base": data == git_show(checkout, rev, repo_path),
                               "mentions_of_skill_name": data.decode("utf-8").count(NAME)}

    overrides = json.loads((claude_home / "settings.json").read_text()).get("skillOverrides", {})
    template = json.loads(git_show(checkout, rev, "adoption/templates/claude.settings.template.json")).get("skillOverrides", {})
    backup = backups / BACKUP_LABEL
    backup_record = {"exists": backup.is_file()}
    if backup.is_file():
        held = json.loads(backup.read_text()).get("skillOverrides", {})
        backup_record.update({"mode": oct(backup.stat().st_mode & 0o777), "skillOverrides_keys": len(held),
                              "skill_key_present": NAME in held})

    tracked = subprocess.run(["git", "-C", str(checkout), "ls-tree", "-r", "--name-only", rev], capture_output=True,
                             text=True, check=True).stdout.splitlines()
    project_copy = re.compile(r"(^|/)(\.agents/skills|agent/skills|agent/subagents/[^/]+/skills)/" + re.escape(NAME) + r"(/|$)")
    on_disk = [checkout / ".agents" / "skills" / NAME, checkout / "agent" / "skills" / NAME,
               *(checkout / "agent" / "subagents").glob(f"*/skills/{NAME}")]

    print(json.dumps({
        "readback_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_revision": subprocess.run(["git", "-C", str(checkout), "rev-parse", rev], capture_output=True, text=True,
                                        check=True).stdout.strip(),
        "relocating_env_vars_set": sorted(var for var, is_set in env.items() if is_set),
        "skill_copies": {"canonical_folder": present(home / ".agents" / "skills" / NAME),
                         "claude_link": present(claude_home / "skills" / NAME),
                         "codex_native_copy": present(codex_home / "skills" / NAME),
                         "home_agent_skills_copy": present(home / "agent" / "skills" / NAME)},
        "lock": {"version": lock.get("version"), "entries": len(lock_names), "skill_entry_present": NAME in lock_names},
        "agents_skills": {"entries": len(entries), "equal_to_lock_names": entries == lock_names,
                          "equal_to_manifest_skills_at_base": entries == manifest_names,
                          "manifest_skills_at_base": len(manifest_names),
                          "skill_in_manifest_skills_at_base": NAME in manifest_names},
        "installed_profile_files": installed,
        "settings_skillOverrides": {"keys": len(overrides), "skill_key_present": NAME in overrides,
                                    "template_keys_at_base": len(template), "key_sets_equal": set(overrides) == set(template),
                                    "values_equal": overrides == template},
        "settings_backup_by_label": backup_record,
        "checkout_project_scope_copies": {"tracked_at_base": sum(1 for path in tracked if project_copy.search(path)),
                                          "on_disk": sum(1 for path in on_disk if present(path))},
        "upstream_agent_paths": agent_global_depths(agents_ts),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
