#!/usr/bin/env python3
"""Scratch-HOME probe of where skills 1.7.0 links claude-code skills under CLAUDE_CONFIG_DIR, and of
install_skills.py's global rollback read-back there (PR #467 repair round, 2026-09-28).

Usage:
  TMPDIR=/var/tmp python3 m4_claude_config_dir_probe.py <skills bin> <repaired install_skills.py> \
      <install_skills.py before the repair> > probe.json

Same isolation as m4_scoped_remove_repro.py: every run gets `env -i` with HOME set to a fresh
directory under $TMPDIR, PATH set to node's directory plus /usr/bin:/bin, DISABLE_TELEMETRY=1, TMPDIR
and, per arm, CLAUDE_CONFIG_DIR, in an empty working directory. The skill is a local fixture and no
arm detects a universal agent other than the two the installer names.
- cli_config_dir and cli_blank_value: the pinned CLI's scoped add and remove, with CLAUDE_CONFIG_DIR
  set to a scratch folder or to two spaces, and where the claude-code link lands.
- installer_*: each installer's global install. The manifest pins a tree the local add never records,
  so the rollback runs. CLAUDE_CONFIG_DIR is set, and in the other_default_copy arms an unrelated
  SKILL.md folder already sits at ~/.claude/skills/<name>, where the CLI does not link while
  CLAUDE_CONFIG_DIR is set.
The output is value-free JSON: exit codes, reported states, the first rollback reason stderr names,
booleans and each installer's sha256. The scratch root is deleted before exit.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NAME = "m4probe"
SKILL_MD = ("---\nname: m4probe\ndescription: Scratch fixture for the M4 CLAUDE_CONFIG_DIR probe.\n"
            "---\n\n# m4probe\n")
# install_skills.py's rollback messages, most specific first; none contains another.
STDERR_REASONS = ("rollback retained, in use by another agent", "rollback incomplete",
                  "rollback could not be verified", "rollback could not run", "rolled back")


def run(argv: list[str], home: Path, cwd: Path, node_dir: Path, config_dir: str) -> subprocess.CompletedProcess:
    env = {"PATH": f"{node_dir}:/usr/bin:/bin", "HOME": str(home), "DISABLE_TELEMETRY": "1",
           "TMPDIR": os.environ.get("TMPDIR", "/var/tmp"), "CLAUDE_CONFIG_DIR": config_dir}
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=180,
                          stdin=subprocess.DEVNULL, check=False)


def fresh(root: Path, arm: str) -> tuple[Path, Path, Path]:
    home, cwd, config = root / arm / "home", root / arm / "cwd", root / arm / "claude-config"
    home.mkdir(parents=True)
    cwd.mkdir()
    return home, cwd, config


def linked(path: Path, canonical: Path) -> dict:
    return {"exists": path.is_symlink() or path.exists(),
            "is_symlink_to_canonical": path.is_symlink() and path.resolve() == canonical.resolve()}


def state(home: Path, config: Path) -> dict:
    canonical = home / ".agents" / "skills" / NAME
    lock = home / ".agents" / ".skill-lock.json"
    return {"canonical_folder": canonical.exists() or canonical.is_symlink(),
            "config_dir_link": linked(config / "skills" / NAME, canonical),
            "default_claude_entry": linked(home / ".claude" / "skills" / NAME, canonical),
            "lock_entry": lock.is_file() and NAME in json.loads(lock.read_text()).get("skills", {})}


def main() -> int:
    skills_bin, repaired, before = (Path(arg).resolve() for arg in sys.argv[1:4])
    node_dir = Path(shutil.which("node")).resolve().parent
    root = Path(tempfile.mkdtemp(prefix="m4-config-probe-", dir=os.environ.get("TMPDIR", "/var/tmp")))
    report = {"version": None, "cli": {}, "installer": {},
              "installer_sha256": {label: hashlib.sha256(path.read_bytes()).hexdigest()
                                   for label, path in (("repaired", repaired), ("before_repair", before))}}
    try:
        src = root / "src" / NAME
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text(SKILL_MD)
        report["version"] = run([str(skills_bin), "--version"], root, root, node_dir, "").stdout.strip()
        add = [str(skills_bin), "add", str(root / "src"), "--skill", NAME, "-g", "-y", "-a", "claude-code", "codex"]
        remove = [str(skills_bin), "remove", NAME, "-g", "-y", "-a", "claude-code", "codex"]
        for arm, blank in (("cli_config_dir", False), ("cli_blank_value", True)):
            home, cwd, config = fresh(root, arm)
            value = "  " if blank else str(config)
            steps = []
            for label, argv in (("add", add), ("scoped_remove", remove)):
                result = run(argv, home, cwd, node_dir, value)
                steps.append({"step": label, "exit": result.returncode, "state_after": state(home, config)})
            report["cli"][arm] = {"claude_config_dir": "two spaces" if blank else "<scratch>/claude-config",
                                  "steps": steps}

        manifest = {"schema_version": 1, "cli": {"version": "1.7.0", "install": "the pinned skills 1.7.0 prefix"},
                    "skills": [{"name": NAME, "url": str(root / "src"), "tree_sha": "1" * 40,
                                "skill_md_sha256": hashlib.sha256(SKILL_MD.encode()).hexdigest()}]}
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        for label, script in (("before_repair", before), ("repaired", repaired)):
            for arm, other_copy in (("other_default_copy", True), ("control", False)):
                home, cwd, config = fresh(root, f"installer_{label}_{arm}")
                other = home / ".claude" / "skills" / NAME / "SKILL.md"
                if other_copy:
                    other.parent.mkdir(parents=True)
                    other.write_text("unrelated\n")
                result = run([sys.executable, str(script), "--manifest", str(manifest_path), "--home", str(home),
                              "--skills-bin", str(skills_bin), "--json"], home, cwd, node_dir, str(config))
                try:
                    payload = json.loads(result.stdout)
                except ValueError:
                    payload = None
                report["installer"][f"{label}_{arm}"] = {
                    "exit": result.returncode,
                    "reported_state": (payload or {}).get("skills", {}).get(NAME),
                    "stderr_reason": next((reason for reason in STDERR_REASONS if reason in result.stderr), None),
                    "other_copy_intact": other.is_file() and other.read_text() == "unrelated\n" if other_copy else None,
                    "state_after": state(home, config)}
    finally:
        shutil.rmtree(root)
    report["scratch_root_removed"] = not root.exists()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
