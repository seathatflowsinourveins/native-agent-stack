#!/usr/bin/env python3
"""Scratch-HOME reproduction of skills 1.7.0's agent-scoped `remove` (M4 correction, 2026-09-28).

Usage:
  TMPDIR=/var/tmp python3 m4_scoped_remove_repro.py <skills bin> <fixed install_skills.py> \
      <unfixed install_skills.py> > repro.json

Every CLI and installer run gets `env -i` with HOME set to a fresh directory under $TMPDIR, PATH set
to node's directory plus /usr/bin:/bin, DISABLE_TELEMETRY=1 and TMPDIR, and an empty working
directory. No CODEX_HOME, XDG_* or CLAUDE_CONFIG_DIR variable can therefore point the CLI at a
real home, and the cwd-relative paths an unscoped remove cleans are empty. The skill is a local
fixture. A local-source add writes no global lock entry, so arms A to C seed one in the scratch lock.
The output is value-free JSON: exit codes, whether the CLI printed its success line, the
scratch HOME's top-level dot-directories, and whether the canonical folder, the claude-code link,
a Codex-native copy and the lock entry exist. For each installer run it adds the reported state and
the first of the installer's rollback reasons that its stderr names. The scratch root is deleted
before exit.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NAME = "m4probe"
SKILL_MD = ("---\nname: m4probe\ndescription: Scratch fixture for the M4 scoped-remove reproduction.\n"
            "---\n\n# m4probe\n")
SCOPED = ["remove", NAME, "-g", "-y", "-a", "claude-code", "codex"]
UNSCOPED = ["remove", NAME, "-g", "-y"]
# install_skills.py's rollback messages, most specific first; none contains another.
STDERR_REASONS = ("rollback retained, in use by another agent", "rollback incomplete",
                  "rollback could not run", "rolled back")


def clean_env(home: Path, node_dir: Path) -> dict:
    return {"PATH": f"{node_dir}:/usr/bin:/bin", "HOME": str(home), "DISABLE_TELEMETRY": "1",
            "TMPDIR": os.environ.get("TMPDIR", "/var/tmp")}


def fresh(root: Path, arm: str, universal: bool) -> tuple[Path, Path]:
    home, cwd = root / arm / "home", root / arm / "cwd"
    home.mkdir(parents=True)
    cwd.mkdir()
    if universal:
        (home / ".cursor").mkdir()  # skills 1.7.0 detects Cursor by this folder alone
    return home, cwd


def run(argv: list[str], home: Path, cwd: Path, node_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, env=clean_env(home, node_dir), capture_output=True, text=True,
                          timeout=180, stdin=subprocess.DEVNULL, check=False)


def lock_path(home: Path) -> Path:
    return home / ".agents" / ".skill-lock.json"


def lock_entry(home: Path):
    path = lock_path(home)
    if not path.is_file():
        return False
    try:
        return NAME in json.loads(path.read_text()).get("skills", {})
    except ValueError:
        return "unreadable"


def state(home: Path) -> dict:
    canonical = home / ".agents" / "skills" / NAME
    link = home / ".claude" / "skills" / NAME
    return {"canonical_folder": canonical.exists() or canonical.is_symlink(),
            "claude_link": link.is_symlink() or link.exists(),
            "codex_native_copy": (home / ".codex" / "skills" / NAME).exists(),
            "lock_entry": lock_entry(home)}


def dot_dirs(home: Path) -> list[str]:
    return sorted(p.name for p in home.iterdir() if p.name.startswith(".") and p.is_dir())


def seed_lock(home: Path) -> int:
    path = lock_path(home)
    data = json.loads(path.read_text()) if path.is_file() else {}
    version = data.get("version") if isinstance(data.get("version"), int) else 3
    data = {"version": version, "skills": data.get("skills") or {}, **{k: v for k, v in data.items()
                                                                         if k not in ("version", "skills")}}
    data["skills"][NAME] = {"source": "example/m4probe", "sourceType": "github",
                            "sourceUrl": "https://github.com/example/m4probe.git", "skillPath": "m4probe/SKILL.md",
                            "skillFolderHash": "0" * 40, "installedAt": "2026-09-28T00:00:00.000Z",
                            "updatedAt": "2026-09-28T00:00:00.000Z"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return version


def cli_step(skills_bin: Path, args: list[str], home: Path, cwd: Path, node_dir: Path, shown: list[str]) -> dict:
    result = run([str(skills_bin), *args], home, cwd, node_dir)
    output = result.stdout + result.stderr
    return {"argv": "skills " + " ".join(shown), "exit": result.returncode,
            "printed_successfully_removed": "Successfully removed 1 skill(s)" in output,
            "state_after": state(home)}


def main() -> int:
    skills_bin, fixed, unfixed = (Path(arg).resolve() for arg in sys.argv[1:4])
    node_dir = Path(shutil.which("node")).resolve().parent
    root = Path(tempfile.mkdtemp(prefix="m4-repro-", dir=os.environ.get("TMPDIR", "/var/tmp")))
    report = {"version": None, "arms": {}, "installer": {}}
    try:
        src = root / "src" / NAME
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text(SKILL_MD)
        add = ["add", str(root / "src"), "--skill", NAME, "-g", "-y", "-a", "claude-code", "codex"]
        add_shown = ["add", "<local fixture>", "--skill", NAME, "-g", "-y", "-a", "claude-code", "codex"]
        report["version"] = run([str(skills_bin), "--version"], root, root, node_dir).stdout.strip()

        for arm, universal in (("A_scoped_with_cursor", True), ("B_scoped_control", False)):
            home, cwd = fresh(root, arm, universal)
            steps = [cli_step(skills_bin, add, home, cwd, node_dir, add_shown)]
            lock_version = seed_lock(home)
            record = {"seeded_lock_version": lock_version, "dot_dirs_before_remove": dot_dirs(home),
                      "state_before_remove": state(home)}
            steps.append(cli_step(skills_bin, SCOPED, home, cwd, node_dir, SCOPED))
            if universal:  # arm C continues in arm A's home
                report["arms"]["C_unscoped_after_A"] = {"dot_dirs_before_remove": dot_dirs(home),
                                                        "state_before_remove": state(home),
                                                        "steps": [cli_step(skills_bin, UNSCOPED, home, cwd,
                                                                           node_dir, UNSCOPED)]}
            report["arms"][arm] = {**record, "steps": steps}

        manifest = {"schema_version": 1, "cli": {"version": "1.7.0", "install": "the pinned skills 1.7.0 prefix"},
                    "skills": [{"name": NAME, "url": str(root / "src"), "tree_sha": "1" * 40,
                                "skill_md_sha256": __import__("hashlib").sha256(SKILL_MD.encode()).hexdigest()}]}
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        for label, script in (("unfixed", unfixed), ("fixed", fixed)):
            for arm, universal in (("with_cursor", True), ("control", False)):
                home, cwd = fresh(root, f"installer_{label}_{arm}", universal)
                result = run([sys.executable, str(script), "--manifest", str(manifest_path), "--home", str(home),
                              "--skills-bin", str(skills_bin), "--json"], home, cwd, node_dir)
                try:
                    payload = json.loads(result.stdout)
                except ValueError:
                    payload = None
                report["installer"][f"{label}_{arm}"] = {
                    "exit": result.returncode,
                    "reported_state": (payload or {}).get("skills", {}).get(NAME),
                    "stderr_reason": next((reason for reason in STDERR_REASONS if reason in result.stderr), None),
                    "dot_dirs_after": dot_dirs(home), "state_after": state(home)}
    finally:
        shutil.rmtree(root)
    report["scratch_root_removed"] = not root.exists()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
