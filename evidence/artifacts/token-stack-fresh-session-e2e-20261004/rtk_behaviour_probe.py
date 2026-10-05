#!/usr/bin/env python3
"""Reproduce the rtk behaviours that the README of this directory states from a measurement: what `rtk rewrite` rewrites with
rtk's upstream defaults and with this repository's hook exclusions, and how rtk's compact forms differ from the shell's (the log
cap and its notice, dropped merge commits, a dropped trailing newline, an error text, exit codes).

    python3 rtk_behaviour_probe.py [OUTFILE]    # default: ~/.local/state/native-agent-stack/e2e/rtk-behaviour-probe.json

Needs rtk and git on PATH. No model, no network and no host file: it builds a scratch repository and two scratch homes in a
temporary directory and removes them, so rtk runs with no configuration of the host's and the host's `rtk gain` counter is not
touched. One scratch home has no rtk configuration (upstream defaults); the other holds fixtures/rtk-hook-exclusions.toml, the
five `exclude_commands` that the bootstrap installs, as `$XDG_CONFIG_HOME/rtk/config.toml`. Every command runs through
subprocess, so the host's own command rewriting does not touch the shell side of a comparison. One run on one host with the
installed rtk and git; the file records what each command returned (exit status, line counts, the first stderr lines), with the
temporary path replaced. It is local_integration evidence, not an upstream test.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXCLUSIONS = Path(__file__).resolve().parents[3] / "fixtures" / "rtk-hook-exclusions.toml"

# `rtk rewrite "<command>"`: what the PreToolUse hook would turn the command into (exit 0 or 3 and the new command), or nothing.
REWRITE_CASES = (
    "git status", "git status --short", "git log", "git log --oneline -3", "git log --stat", "git diff --exit-code",
    "ls /nonexistent", "cat a/x/util.py", "grep -rl needle .", "find /nonexistent -name x",
    "git status --short && echo done", "git log --oneline -3 | cat",
    "git show HEAD:a/x/util.py", "diff /nonexistent a/x/util.py", "jq . data.json", "git branch", "echo hi", "bash -c 'git status'",
)

# Commands run in the fixture repository, once as the shell runs them and once with the `rtk` prefix (rtk's own compact forms;
# the hook's exclusions do not apply to a command typed with the prefix).
COMPARE_CASES = (
    "git status --short", "git log", "git log --stat", "git log --oneline", "git log --format=%s", "git log --graph --oneline",
    "git log -n 16", "git log --oneline -n 66", "git log --stat -n 16", "ls /nonexistent", "find /nonexistent -name x", "grep -rl needle .",
)


def scratch_env(home: Path) -> dict:
    """The environment of a command: a scratch HOME and XDG tree (rtk keeps its configuration and its usage database there)."""
    env = {**os.environ, "HOME": str(home), "RTK_TELEMETRY_DISABLED": "1", "GIT_PAGER": "cat", "LC_ALL": "C.UTF-8"}
    for name, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_DATA_HOME", ".local/share"), ("XDG_CACHE_HOME", ".cache"),
                      ("XDG_STATE_HOME", ".local/state")):
        env[name] = str(home / sub)
    return env


def run(args: list[str], cwd: Path, home: Path) -> dict:
    done = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=60, check=False, env=scratch_env(home))
    return {"exit": done.returncode, "stdout": done.stdout, "stderr": done.stderr}


def git(repo: Path, home: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=probe", "-c", "user.email=probe@example.invalid", *args], cwd=repo, check=True,
                   capture_output=True, text=True, timeout=60,
                   env={**scratch_env(home), "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"})


def fixture(repo: Path, home: Path) -> None:
    """Sixty-four linear commits, one feature commit merged with --no-ff (sixty-six commits, one merge: past rtk's default of 50 for
    compact log forms), a modified and an untracked file."""
    git(repo, home, "init", "-q", "-b", "main")
    (repo / "a" / "x").mkdir(parents=True)
    (repo / "a" / "x" / "util.py").write_text("needle\n", encoding="utf-8")
    (repo / "data.json").write_text("{}\n", encoding="utf-8")
    git(repo, home, "add", ".")
    git(repo, home, "commit", "-q", "-m", "commit 1")
    for number in range(2, 65):
        (repo / "a" / "x" / "util.py").write_text(f"needle {number}\n", encoding="utf-8")
        git(repo, home, "commit", "-q", "-am", f"commit {number}")
    git(repo, home, "checkout", "-q", "-b", "feature")
    (repo / "feature.txt").write_text("feature\n", encoding="utf-8")
    git(repo, home, "add", ".")
    git(repo, home, "commit", "-q", "-m", "feature work")
    git(repo, home, "checkout", "-q", "main")
    git(repo, home, "merge", "-q", "--no-ff", "-m", "Merge branch feature", "feature")
    (repo / "a" / "x" / "util.py").write_text("needle changed\n", encoding="utf-8")
    (repo / "untracked.txt").write_text("x\n", encoding="utf-8")


def summarize(result: dict, scratch: str) -> dict:
    out, err = result["stdout"], result["stderr"]
    return {
        "exit": result["exit"],
        "stdout_lines": len(out.splitlines()),
        "stdout_ends_with_newline": out.endswith("\n") if out else None,
        "commit_lines": sum(1 for line in out.splitlines() if line.startswith("commit ")),
        "merge_lines": sum(1 for line in out.splitlines() if "Merge branch" in line),
        "stderr_first_lines": [line.replace(scratch, "<scratch>") for line in err.splitlines()[:2]],
        "mentions_usr_bin_ls": "/usr/bin/ls" in err,
    }


def rewrites(repo: Path, home: Path) -> list[dict]:
    table = []
    for command in REWRITE_CASES:
        result = run(["rtk", "rewrite", command], repo, home)
        table.append({"command": command, "exit": result["exit"], "rewritten_to": result["stdout"].strip() or None})
    return table


def main() -> int:
    if not shutil.which("rtk") or not shutil.which("git"):
        print("needs rtk and git on PATH", file=sys.stderr)
        return 2
    if not EXCLUSIONS.is_file():
        print(f"missing {EXCLUSIONS}: run it from a checkout of the repository", file=sys.stderr)
        return 2
    target = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else \
        Path.home() / ".local/state/native-agent-stack/e2e/rtk-behaviour-probe.json"
    with tempfile.TemporaryDirectory(prefix="rtk-probe-") as scratch:
        repo, plain, excluding = (Path(scratch) / name for name in ("repo", "home-defaults", "home-exclusions"))
        for directory in (repo, plain, excluding):
            directory.mkdir()
        (excluding / ".config" / "rtk").mkdir(parents=True)
        shutil.copyfile(EXCLUSIONS, excluding / ".config" / "rtk" / "config.toml")
        fixture(repo, plain)
        versions = {"rtk": run(["rtk", "--version"], repo, plain)["stdout"].strip(),
                    "git": run(["git", "--version"], repo, plain)["stdout"].strip()}
        rewrite = {"upstream_defaults": rewrites(repo, plain), "repository_exclusions": rewrites(repo, excluding)}
        compared = []
        for command in COMPARE_CASES:
            argv = command.split()
            compared.append({"command": command, "shell": summarize(run(argv, repo, plain), scratch),
                             "rtk": summarize(run(["rtk", *argv], repo, plain), scratch)})
        commits = len(run(["git", "log", "--format=%H"], repo, plain)["stdout"].splitlines())
        merges = len(run(["git", "log", "--merges", "--format=%H"], repo, plain)["stdout"].splitlines())
    record = {"schema": "rtk-behaviour-probe/1", "evidence_class": "local_integration: one run, one host, a scratch repository",
              "versions": versions, "fixture": {"commits": commits, "merge_commits": merges},
              "exclusions_fixture_sha256": hashlib.sha256(EXCLUSIONS.read_bytes()).hexdigest(),
              "rewrite": rewrite, "compared": compared}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {target}: {len(REWRITE_CASES)} rewrite cases under two configurations, {len(compared)} compared commands")
    return 0


if __name__ == "__main__":
    sys.exit(main())
