#!/usr/bin/env python3
"""Reproduce what `rtk init -g --codex` (rtk 0.51.0) changes in a Codex home, and how it is shown and undone, in scratch homes only.

    python3 rtk_init_codex_probe.py [OUTFILE]    # default: ~/.local/state/native-agent-stack/e2e/rtk-init-codex-probe.json

Needs rtk on PATH. No model, no network, no host file: every run uses a scratch HOME, XDG tree and CODEX_HOME in a temporary
directory that is removed, so the host's Codex home, rtk configuration and `rtk gain` counter are untouched. The file records, per
step, the exit status, the files created, changed and removed (with the changed lines of text files) and the `--show` lines, with the
temporary path replaced. One run, one host, the installed rtk: local_integration evidence, not an upstream test.
"""

from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MANAGED_AGENTS = "# Existing managed instructions\n\n<!-- managed block -->\nUse the stack's tools.\n<!-- /managed block -->\n"
MEMORY_HOOKS = {"hooks": {"PreToolUse": [{"matcher": "", "hooks": [{"type": "command", "command": "python3 /fixture/memory_hook.py"}]}]}}


def snapshot(root: Path) -> dict:
    return {str(path.relative_to(root)): path.read_text(encoding="utf-8", errors="replace")
            for path in sorted(root.rglob("*")) if path.is_file()}


def environment(home: Path, codex_home: Path) -> dict:
    return {**os.environ, "HOME": str(home), "CODEX_HOME": str(codex_home), "RTK_TELEMETRY_DISABLED": "1",
            "XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(home / ".local/share"),
            "XDG_CACHE_HOME": str(home / ".cache"), "XDG_STATE_HOME": str(home / ".local/state")}


def step(label: str, args: list[str], home: Path, codex_home: Path, scratch: str, state: dict) -> tuple[dict, dict]:
    done = subprocess.run(["rtk", *args], cwd=home, env=environment(home, codex_home), capture_output=True, text=True, timeout=60,
                          stdin=subprocess.DEVNULL, check=False)
    after = snapshot(Path(scratch))
    changes = []
    for name in sorted(set(state) | set(after)):
        if name not in state:
            changes.append({"file": name, "change": "created", "bytes": len(after[name])})
        elif name not in after:
            changes.append({"file": name, "change": "removed"})
        elif state[name] != after[name]:
            lines = [line[:160].replace(scratch, "<scratch>") for line in difflib.unified_diff(
                state[name].splitlines(), after[name].splitlines(), lineterm="", n=0) if not line.startswith(("---", "+++", "@@"))]
            changes.append({"file": name, "change": "changed", "lines": lines})
    clean = lambda text: [line.replace(scratch, "<scratch>")[:170] for line in text.splitlines()]  # noqa: E731
    record = {"step": label, "args": args, "exit": done.returncode, "files": [c for c in changes if not c["file"].endswith("history.db")],
              "history_db_created": any(c["file"].endswith("history.db") and c["change"] == "created" for c in changes)}
    if "--show" in args:
        record["show"] = [line for line in clean(done.stdout) if line.startswith(("[ok]", "[--]"))]
    else:
        record["stdout_first_lines"] = [line for line in clean(done.stdout) if line.strip()][:7]
        record["stderr"] = clean(done.stderr)[:2]
    return record, after


def scenario(label: str, with_agents: bool, steps: list[tuple[str, list[str]]], codex_elsewhere: bool = False) -> dict:
    """Each step's changes are listed relative to the scratch root, where the scratch HOME is `fake-home`."""
    with tempfile.TemporaryDirectory(prefix="rtk-init-") as scratch:
        home = Path(scratch) / "fake-home"
        codex_home = Path(scratch) / "codex-elsewhere" if codex_elsewhere else home / ".codex"
        home.mkdir(parents=True)
        codex_home.mkdir(parents=True, exist_ok=True)
        if with_agents:
            (codex_home / "AGENTS.md").write_text(MANAGED_AGENTS, encoding="utf-8")
        (codex_home / "hooks.json").write_text(json.dumps(MEMORY_HOOKS, indent=2) + "\n", encoding="utf-8")
        (codex_home / "config.toml").write_text("# scratch user layer\n", encoding="utf-8")
        state, records = snapshot(Path(scratch)), []
        for name, args in steps:
            record, state = step(name, args, home, codex_home, scratch, state)
            records.append(record)
        return {"scenario": label, "steps": records}


def main() -> int:
    if not shutil.which("rtk"):
        print("needs rtk on PATH", file=sys.stderr)
        return 2
    target = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else \
        Path.home() / ".local/state/native-agent-stack/e2e/rtk-init-codex-probe.json"
    full = [("show before", ["init", "--show", "--codex"]), ("dry run", ["init", "-g", "--codex", "--dry-run"]),
            ("init", ["init", "-g", "--codex"]), ("show after", ["init", "--show", "--codex"]),
            ("init again", ["init", "-g", "--codex"]), ("uninstall", ["init", "-g", "--codex", "--uninstall"]),
            ("show after uninstall", ["init", "--show", "--codex"])]
    scenarios = [
        scenario("a Codex home with its own AGENTS.md and a hooks.json", True, full),
        scenario("a Codex home with a hooks.json and no AGENTS.md", False, [("init", ["init", "-g", "--codex"]),
                                                                           ("uninstall", ["init", "-g", "--codex", "--uninstall"])]),
        scenario("flags combined with --codex", True, [(flag, ["init", "-g", "--codex", flag]) for flag in
                                                       ("--hook-only", "--no-patch", "--auto-patch")]),
        scenario("CODEX_HOME outside HOME", False, [("init", ["init", "-g", "--codex"])], codex_elsewhere=True),
    ]
    record = {"schema": "rtk-init-codex-probe/1", "evidence_class": "local_integration: one run, one host, scratch homes",
              "rtk": subprocess.run(["rtk", "--version"], capture_output=True, text=True, timeout=30, check=False).stdout.strip(),
              "scenarios": scenarios}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {target}: {sum(len(s['steps']) for s in scenarios)} steps in {len(scenarios)} scenarios")
    return 0


if __name__ == "__main__":
    sys.exit(main())
