#!/usr/bin/env python3
"""Render the shared Codex config template for the example host and load it with the installed Codex under --strict-config.

Arms: the rendered template as it is (it must load: the run may stop at authentication, never at configuration); a negative control with a
wrong type for `notifications` (strict config must refuse it, which shows the key is known to Codex's typed schema); a negative control with an
unknown top-level key (must be refused); and a probe with an unknown key inside `[tui]`, which strict config does NOT refuse (measured), so the
repository's test pins the `[tui]` setting names itself. Uses a throwaway CODEX_HOME inside a private temporary directory; nothing outside it is
written. Prints exit codes, booleans and the last output line of each run only.

Revised 2026-09-30 after a cross-family review: 'accepted' used to mean only that no configuration-error text appeared, which a Codex that failed BEFORE reading any configuration also satisfies. Codex prints
its session banner (`OpenAI Codex v<version>`, `workdir:`, `model:`, ...) once the configuration is accepted, so a run counts as loaded only with that banner and no configuration error; a negative control counts
as refused only with a configuration error and no banner. `judge` holds that rule and `--selftest` runs it on made-up output (a banner with a 401, a config error, a run that never started).
usage: python3 -B codex_tui_strict_check.py <worktree> | --selftest
"""
import json, os, re, shutil, subprocess, sys, tempfile, tomllib
from pathlib import Path

CONFIG_ERROR = re.compile(r"unknown field|unknown key|invalid type|config(uration)? (error|invalid)|failed to (load|parse) config|Error loading config", re.I)
BANNER = re.compile(r"OpenAI Codex v\d[^\n]*\n-+\nworkdir: [^\n]*\nmodel: [^\n]*\n")


def judge(blob):
    """(loaded, config_error): loaded only when the session banner was printed and no configuration error was; a run that never started has neither."""
    banner = bool(BANNER.search(blob))
    error = bool(CONFIG_ERROR.search(blob))
    return banner and not error, error and not banner


def selftest():
    banner = "OpenAI Codex v0.159.2\n--------\nworkdir: /w\nmodel: gpt-6-astra\nprovider: openai\n--------\nuser\nhi\nERROR: unexpected status 401 Unauthorized\n"
    checks = [("a banner then a 401 is loaded", judge(banner), (True, False)),
              ("a configuration error with no banner is refused", judge("Error loading config.toml: unknown field `zzz`\n"), (False, True)),
              ("a run that never started (no binary, nothing printed) is neither loaded nor refused", judge(""), (False, False)),
              ("a shell error is neither loaded nor refused", judge("bash: codex: command not found\n"), (False, False)),
              ("a banner together with a configuration error is not loaded and not refused", judge(banner + "invalid type\n"), (False, False))]
    problems = [label for label, got, expected in checks if got != expected]
    print(json.dumps({"selftest_checks": len(checks), "problems": problems}))
    return 1 if problems else 0


if "--selftest" in sys.argv[1:]:
    sys.exit(selftest())
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
        loaded, config_error = judge(blob)
        first = re.sub(r"\s+", " ", (blob.strip().splitlines() or [""])[-1])[:150]
        print(f"strict {label}: exit {out.returncode}, loaded (banner, no config error): {loaded}, refused (config error, no banner): {config_error}, mentions notifications: {'notifications' in blob} | last line: {first}")
        return out.returncode, loaded, config_error

    ok = strict("rendered-template", config)
    wrong_type = strict("negative-control-wrong-type", config.replace('notifications = ["approval-requested", "plan-mode-prompt", "async-question"]', "notifications = 5", 1))
    unknown_key = strict("negative-control-unknown-top-level-key", "zzz_unknown_key = true\n" + config)
    unknown_tui_key = strict("unknown-key-inside-tui", config.replace('notifications = [', 'notificationz = [', 1))
    print("template accepted:", ok[1])
    print("wrong-type control refused:", wrong_type[2], "| unknown top-level key refused:", unknown_key[2], "| unknown key inside [tui] refused:", unknown_tui_key[2],
          "| unknown key inside [tui] loaded:", unknown_tui_key[1])
    accepted = ok[1] and wrong_type[2] and unknown_key[2]
    print("acceptance (template loaded, both controls refused):", accepted)
finally:
    shutil.rmtree(work, ignore_errors=True)
    print("scratch removed:", not work.exists())
sys.exit(0 if accepted else 1)
