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
      installing something else) runs `skills remove <name> -g -y` and is
      reported as 'rolled-back' rather than left half-installed.

Exit status is 1 when any processed skill ends anywhere but 'ok' or
'installed' (or, under --dry-run, anywhere but 'ok' or 'planned' -- a
local-modified refusal is real even though --dry-run writes nothing).

This script never reads a credential store or a `gh`/git token, and never
passes one to the `skills` CLI: the only environment override it adds to that
subprocess is HOME (so --home works for a non-default target, e.g. in tests)
and DISABLE_TELEMETRY. It never writes ~/.agents/skills, ~/.claude/skills or
the skill lock file directly -- only the `skills` CLI does, exactly as it
would for a person running it by hand.

The global skill lock path honors $XDG_STATE_HOME exactly like the upstream
CLI: ``$XDG_STATE_HOME/skills/.skill-lock.json`` when that variable is set,
else ``~/.agents/.skill-lock.json``. Only *that* lock path check reads the
variable; the canonical skill folders and the claude-code symlink stay under
--home/.agents and --home/.claude regardless of $XDG_STATE_HOME.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "adoption" / "skills" / "manifest.json"

VERSION_CHECK_TIMEOUT = 30
ADD_TIMEOUT = 120
REMOVE_TIMEOUT = 30

# Real-run and --dry-run each have their own notion of "nothing left to fix":
# a dry run never executes `add`/`remove`, so 'planned' (not 'installed') is
# its success outcome, but a real local-modified refusal is still a refusal.
OK_STATUSES_REAL = {"ok", "installed"}
OK_STATUSES_DRY_RUN = {"ok", "planned"}


class InstallError(ValueError):
    """A skill could not be safely installed, verified or checked."""


def load_manifest(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_skill_dir(home: Path, name: str) -> Path:
    """The upstream CLI's one canonical copy; Codex reads this directly and
    claude-code gets a relative symlink onto it (../../.agents/skills/<name>)."""
    return home / ".agents" / "skills" / name


def lock_file_path(home: Path) -> Path:
    xdg_state_home = os.environ.get("XDG_STATE_HOME")
    if xdg_state_home:
        return Path(xdg_state_home) / "skills" / ".skill-lock.json"
    return home / ".agents" / ".skill-lock.json"


def load_lock(home: Path) -> dict:
    path = lock_file_path(home)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def read_lock_entry(home: Path, name: str) -> dict | None:
    skills = load_lock(home).get("skills")
    if not isinstance(skills, dict):
        return None
    entry = skills.get(name)
    return entry if isinstance(entry, dict) else None


def classify_skill(skill: dict, home: Path) -> str:
    """'ok' (a)), 'local-modified' (b), refused), or 'install' (needs an add:
    either a fresh install, a locked-but-mismatched entry, or an unlocked
    folder that already matches the manifest byte-for-byte)."""
    name = skill["name"]
    skill_md = canonical_skill_dir(home, name) / "SKILL.md"
    md_matches = skill_md.is_file() and sha256_of(skill_md) == skill["skill_md_sha256"]
    entry = read_lock_entry(home, name)
    if entry is not None:
        return "ok" if (md_matches and entry.get("skillFolderHash") == skill["tree_sha"]) else "install"
    if skill_md.is_file():
        return "install" if md_matches else "local-modified"
    return "install"


def run_skills_bin(skills_bin: str, args: list[str], home: Path, timeout: int) -> subprocess.CompletedProcess:
    """Every skills-bin call: HOME pinned to --home (so a non-default target
    works, e.g. under test) and telemetry (and its add-time audit call) off.
    No token or credential is read or added; stdin is closed so a CLI that
    falls back to reading it gets EOF rather than the caller's terminal."""
    env = {**os.environ, "HOME": str(home), "DISABLE_TELEMETRY": "1"}
    return subprocess.run([skills_bin, *args], capture_output=True, text=True, timeout=timeout,
                          check=False, env=env, stdin=subprocess.DEVNULL)


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


def process_skill(skill: dict, home: Path, skills_bin: str, dry_run: bool, force: bool, quiet: bool) -> str:
    name = skill["name"]

    def note(message: str) -> None:
        if not quiet:
            print(message)

    state = classify_skill(skill, home)
    if state == "ok":
        note(f"{name}: ok (pinned ref already installed and locked)")
        return "ok"
    if state == "local-modified" and not force:
        print(f"{name}: local-modified -- refusing to overwrite an unlocked local SKILL.md that does "
              f"not match the pinned manifest hash (pass --force to overwrite it)", file=sys.stderr)
        return "local-modified"

    add_args = ["add", skill["url"], "--skill", name, "-g", "-y", "-a", "claude-code", "codex"]
    if dry_run:
        note(f"{name}: would run: {shlex.join([skills_bin, *add_args])}")
        return "planned"

    try:
        result = run_skills_bin(skills_bin, add_args, home, timeout=ADD_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"{name}: add failed to run ({error})", file=sys.stderr)
        return "error"
    if result.returncode != 0:
        print(f"{name}: add exited {result.returncode}: {result.stderr.strip()}", file=sys.stderr)
        return "error"

    if classify_skill(skill, home) == "ok":
        note(f"{name}: installed and verified at tree {skill['tree_sha']}")
        return "installed"

    run_skills_bin(skills_bin, ["remove", name, "-g", "-y"], home, timeout=REMOVE_TIMEOUT)
    print(f"{name}: installed content did not match the pinned manifest hash/tree; rolled back",
          file=sys.stderr)
    return "rolled-back"


def print_codex_config(skills: list[dict]) -> None:
    """The `[[skills.config]]` tables that turn every codex_enabled: false
    manifest skill off in Codex's ~/.codex/config.toml (no path needed)."""
    blocks = [
        f'[[skills.config]]\nname = "{skill["name"]}"\nenabled = false'
        for skill in skills if isinstance(skill, dict) and skill.get("codex_enabled") is False
    ]
    print("\n\n".join(blocks))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST),
                         help="Skills trial manifest to install from (default: adoption/skills/manifest.json)")
    parser.add_argument("--home", default=str(Path.home()),
                         help="Target $HOME (default: current user's; override for tests)")
    parser.add_argument("--skills-bin", default="skills",
                         help="Pinned 'skills' executable (default: 'skills' resolved on PATH)")
    parser.add_argument("--dry-run", action="store_true",
                         help="Report planned actions; add, remove and verify nothing")
    parser.add_argument("--only", action="append", metavar="NAME",
                         help="Process only this manifest skill name; repeatable")
    parser.add_argument("--force", action="store_true",
                         help="Overwrite a local, unlocked skill folder whose SKILL.md does not "
                              "match the manifest (default: refuse it as local-modified)")
    parser.add_argument("--print-codex-config", action="store_true",
                         help="Print [[skills.config]] name/enabled=false lines for every "
                              "codex_enabled: false manifest skill, then exit")
    parser.add_argument("--json", action="store_true",
                         help="Print a compact, value-free {skill: status} summary instead of prose")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest)
    try:
        manifest = load_manifest(manifest_path)
    except (OSError, json.JSONDecodeError) as error:
        print(f"install-skills failed: cannot read manifest {manifest_path}: {error}", file=sys.stderr)
        return 1
    try:
        all_skills = manifest["skills"]
    except (KeyError, TypeError) as error:
        print(f"install-skills failed: manifest missing 'skills' ({error})", file=sys.stderr)
        return 1

    if args.print_codex_config:
        print_codex_config(all_skills)
        return 0

    home = Path(args.home)
    skills = all_skills
    if args.only:
        wanted = list(dict.fromkeys(args.only))
        by_name = {s["name"]: s for s in all_skills if isinstance(s, dict) and "name" in s}
        unknown = [name for name in wanted if name not in by_name]
        if unknown:
            print(f"install-skills failed: unknown --only name(s): {unknown}", file=sys.stderr)
            return 1
        skills = [by_name[name] for name in wanted]

    try:
        verify_skills_bin(args.skills_bin, manifest["cli"], home)
    except InstallError as error:
        print(f"install-skills failed: {error}", file=sys.stderr)
        return 1
    except (KeyError, TypeError) as error:
        print(f"install-skills failed: manifest missing 'cli' details ({error})", file=sys.stderr)
        return 1

    results: dict[str, str] = {}
    try:
        for skill in skills:
            results[skill["name"]] = process_skill(skill, home, args.skills_bin, args.dry_run,
                                                    args.force, args.json)
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
