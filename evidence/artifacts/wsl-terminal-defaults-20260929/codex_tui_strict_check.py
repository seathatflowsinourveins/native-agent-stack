#!/usr/bin/env python3
"""Render the shared Codex config template for the example host and load it with the installed Codex under --strict-config.

Arms: the rendered template as it is (it must load: the run may stop at authentication, never at configuration); a negative control with a
wrong type for `notifications` (strict config must refuse it, which shows the key is known to Codex's typed schema); a negative control with an
unknown top-level key (must be refused); and a probe with an unknown key inside `[tui]`, which strict config does NOT refuse (measured), so the
repository's test pins the `[tui]` setting names itself. Uses a throwaway CODEX_HOME inside a private temporary directory; nothing outside it is
written. Prints exit codes, booleans and the last output line of each run only.
usage: python3 -B codex_tui_strict_check.py <worktree>
"""
import json, os, re, shutil, subprocess, sys, tempfile, tomllib
from pathlib import Path

worktree = Path(sys.argv[1]).resolve()
codex = shutil.which("codex")
work = Path(tempfile.mkdtemp(prefix="codex-tui-strict-"))
try:
    rendered = work / "rendered"
    run = subprocess.run([sys.executable, "-B", str(worktree / "tools/adoption/render_config.py"), "--host", "example", "--out", str(rendered)],
                         capture_output=True, text=True, cwd=worktree, timeout=120)
    print("render exit:", run.returncode, "|", (run.stderr.strip().splitlines() or [""])[-1][:160])
    config = (rendered / "codex.config.toml").read_text(encoding="utf-8")
    table = tomllib.loads(config).get("tui", {})
    print("[tui] parsed:", table)

    def strict(label, text):
        home = work / ("home-" + label)
        home.mkdir()
        (home / "config.toml").write_text(text, encoding="utf-8")
        env = {"PATH": os.environ["PATH"], "HOME": str(work), "CODEX_HOME": str(home)}
        out = subprocess.run([codex, "--strict-config", "exec", "--skip-git-repo-check", "-s", "read-only", "Reply with exactly: ok"], cwd=work, env=env,
                             stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
        blob = (out.stdout + out.stderr)
        config_error = bool(re.search(r"unknown field|unknown key|invalid type|config(uration)? (error|invalid)|failed to (load|parse) config|Error loading config", blob, re.I))
        first = re.sub(r"\s+", " ", (blob.strip().splitlines() or [""])[-1])[:150]
        print(f"strict {label}: exit {out.returncode}, config error reported: {config_error}, mentions notifications: {'notifications' in blob} | last line: {first}")
        return out.returncode, config_error

    ok = strict("rendered-template", config)
    wrong_type = strict("negative-control-wrong-type", config.replace('notifications = ["approval-requested", "plan-mode-prompt", "async-question"]', "notifications = 5", 1))
    unknown_key = strict("negative-control-unknown-top-level-key", "zzz_unknown_key = true\n" + config)
    unknown_tui_key = strict("unknown-key-inside-tui", config.replace('notifications = [', 'notificationz = [', 1))
    print("template accepted:", not ok[1] and ok[0] != 0 or not ok[1])
    print("wrong-type control refused:", wrong_type[1], "| unknown top-level key refused:", unknown_key[1], "| unknown key inside [tui] refused:", unknown_tui_key[1])
finally:
    shutil.rmtree(work, ignore_errors=True)
    print("scratch removed:", not work.exists())
