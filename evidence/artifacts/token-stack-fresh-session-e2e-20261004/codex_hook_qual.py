#!/usr/bin/env python3
"""Qualify RTK's Codex PreToolUse hook (`rtk init -g --codex`, rtk 0.51.0) against the installed Codex, in scratch Codex homes.

Upstream commands only: `rtk init -g --codex`, `rtk init --show --codex`, Codex's own `hooks/list`, the repository's
tools/adoption/codex_hook_trust.py (the /hooks review's persisted edit: config/batchWrite of hooks.state, trusted_hash),
`codex exec --json --ephemeral` through the loopback OmniRoute gateway the packaged worker uses (no credential needed, none
copied), and `rtk gain`.
Nothing under the live ~/.codex is written; the scratch homes and the fixture repository live under one directory that this
script deletes at the end. The two hooks of the scratch homes are a probe (it logs the PreToolUse payload Codex sends, then
allows) at group 0, standing for the host's ai-memory hook, and rtk's own group at 1, as `rtk init` appends it.

    python3 evidence/artifacts/token-stack-fresh-session-e2e-20261004/codex_hook_qual.py [outdir [arm ...]]

Arms: R0 probe only (no rtk hook); R1 probe + rtk hook, trusted, no AGENTS instruction; R1u the same but not trusted;
R2 the same as R1 with the RTK awareness instruction present; B2 R1 over a second battery (pipe, quotes, rtk's known exit-code
exceptions: find on a missing path, diff on a missing file, cat); R2b the awareness instruction present and the prompt not
forbidding a prefix, so the model prefixes `rtk` itself and the hook must leave it alone (no `rtk rtk`).
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))
import apply_codex_lane as lane  # noqa: E402

TRUST_TOOL = ROOT / "tools" / "adoption" / "codex_hook_trust.py"

OUT = Path(sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else os.environ.get("E2E_OUT") or
           Path.home() / ".local/state/native-agent-stack/e2e") / f"codex-hook-qual-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
WORK = Path.home() / ".cache/native-agent-stack-e2e/rtk-codex-dyn"
ONLY = set(sys.argv[2:])  # run only these arm labels when given
CODEX = shutil.which("codex")
GATEWAY = ["model_provider=\"omniroute_runtime\"", "model=\"cx/gpt-6.1-sol-max\"", "model_reasoning_effort=\"low\"",
           "features.plugins=false", "approval_policy=\"never\"", "sandbox_mode=\"danger-full-access\"",
           "model_providers.omniroute_runtime.name=\"OmniRoute runtime workers\"",
           "model_providers.omniroute_runtime.base_url=\"http://127.0.0.1:20128/v1\"",
           "model_providers.omniroute_runtime.wire_api=\"responses\"",
           "model_providers.omniroute_runtime.requires_openai_auth=false",
           "model_providers.omniroute_runtime.supports_websockets=false"]
COMMANDS = ["git status --short", "ls /nonexistent", "grep -rl nomatch .", "grep -rl needle .", "git diff --exit-code",
            "git status --short && echo done"]
COMMANDS2 = ["git log --oneline -3 | cat", "grep -rn \"needle two\" a", "find /nonexistent -name x",
             "diff /nonexistent a/x/util.py", "cat a/x/util.py"]


def prompt(commands, strict=True):
    """strict: the commands exactly as written, no prefix (the model then runs them unprefixed, so the hook has work to do);
    not strict: the model is left to its instructions (a Codex home with the RTK awareness text prefixes `rtk` itself)."""
    lead = ("Run each of the following commands as its own separate shell tool call, exactly as written, with no prefix and no "
            "extra flags." if strict else "Run each of the following commands as its own separate shell tool call.")
    return (lead + " After all of them, reply with one line per command: \"<n> exit=<exit status>\".\n" +
            "\n".join(f"{n}. {c}" for n, c in enumerate(commands, 1)))


AWARENESS = ("# RTK\n\nPrefix every shell command with `rtk`: `rtk git status`, `rtk cargo test`, `rtk npm run build`, `rtk ls src/`."
             " Keep the prefix inside chains: `rtk git add . && rtk git commit -m \"msg\"`. Commands RTK has no filter for run "
             "as-is, so the prefix is always safe.\n")


def sh(*argv, cwd=None, env=None, timeout=120, check=True):
    done = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    if check and done.returncode != 0:
        raise SystemExit(f"{argv[:3]} failed ({done.returncode}): {done.stderr[:300]}")
    return done


def fixture() -> Path:
    project = WORK / "project"
    for rel in ("a/x/util.py", "b/x/util.py", "c/util.py"):
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        (project / rel).write_text("needle\n", encoding="utf-8")
    (project / "c/other.py").write_text("nothing\n", encoding="utf-8")
    env = dict(os.environ, GIT_AUTHOR_NAME="e2e", GIT_AUTHOR_EMAIL="e2e@local", GIT_COMMITTER_NAME="e2e",
               GIT_COMMITTER_EMAIL="e2e@local")
    sh("git", "init", "-q", cwd=project)
    sh("git", "add", ".", cwd=project)
    sh("git", "commit", "-q", "-m", "fixture", cwd=project, env=env)
    (project / "a/x/util.py").write_text("needle\nneedle two\n", encoding="utf-8")  # so that `git diff --exit-code` exits 1
    return project


def ground_truth(project: Path, commands) -> list[dict]:
    rows = []
    for command in commands:
        done = sh("bash", "-c", command, cwd=project, check=False)
        rows.append({"command": command, "exit": done.returncode, "output": (done.stdout + done.stderr)[:200]})
    return rows


def make_home(name: str, project: Path, rtk_hook: bool, agents: bool) -> Path:
    home = WORK / name
    codex_home = home / ".codex"
    codex_home.mkdir(parents=True)
    probe = home / "probe_hook.py"
    probe.write_text("import json, sys\nopen(%r, 'a').write(sys.stdin.read().replace('\\n', ' ') + '\\n')\n" % str(home / "probe.log"),
                     encoding="utf-8")
    (codex_home / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "", "hooks": [{"type": "command", "command": f"python3 {probe}"}]}]}}, indent=2) + "\n", encoding="utf-8")
    (codex_home / "config.toml").write_text("# scratch user layer\n", encoding="utf-8")
    env = dict(os.environ, HOME=str(home), CODEX_HOME=str(codex_home))
    if rtk_hook:
        sh("rtk", "init", "-g", "--codex", cwd=home, env=env)
    if not agents:
        for leftover in ("AGENTS.md", "RTK.md"):
            (codex_home / leftover).unlink(missing_ok=True)
    else:
        (codex_home / "AGENTS.md").write_text(AWARENESS, encoding="utf-8")
    return codex_home


def hooks_state(codex_home: Path, project: Path) -> list[dict]:
    with lane.AppServer(CODEX, lane.codex_env(codex_home), project) as server:
        return server.request("hooks/list", {"cwds": [str(project)]})["data"][0]["hooks"]


def trust_all(codex_home: Path, project: Path) -> None:
    """The repository's own tool, as a plan row runs it, for the two hooks of the scratch home: the probe and rtk's. The process
    name is one no process has, because other codex sessions may run on the host and this home is scratch."""
    probe = codex_home.parent / "probe_hook.py"
    sh(sys.executable, str(TRUST_TOOL), "--codex-home", str(codex_home), "--cwd", str(project), "--command", "rtk hook codex",
       "--command", f"python3 {probe}", "--codex-process-name", "no-such-codex-process", "--apply")


def run_arm(label: str, codex_home: Path, project: Path, commands, strict: bool, path: str | None = None) -> dict:
    log = codex_home.parent / "probe.log"
    log.unlink(missing_ok=True)
    argv = [CODEX, "exec", "--json", "--ephemeral", "--skip-git-repo-check", "-C", str(project)]
    for override in GATEWAY:
        argv += ["-c", override]
    argv.append(prompt(commands, strict))
    env = dict(os.environ, CODEX_HOME=str(codex_home))
    if path is not None:
        env["PATH"] = path  # a launcher whose PATH lacks rtk: the hook command is the bare `rtk hook codex`
    started = time.time()
    done = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=900, stdin=subprocess.DEVNULL)
    (OUT / f"{label}.jsonl").write_text(done.stdout, encoding="utf-8")
    (OUT / f"{label}.err").write_text(done.stderr[-2000:], encoding="utf-8")
    events = [json.loads(line) for line in done.stdout.splitlines() if line.startswith("{")]
    commands = [e["item"] for e in events if e.get("type") == "item.completed" and e["item"].get("type") == "command_execution"]
    payloads = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    (OUT / f"{label}.probe.jsonl").write_text("".join(json.dumps(p) + "\n" for p in payloads), encoding="utf-8")
    usage = [e["usage"] for e in events if e.get("type") == "turn.completed"]
    return {"label": label, "rc": done.returncode, "seconds": round(time.time() - started), "commands": commands,
            "asked": [p.get("tool_input", {}).get("command") for p in payloads], "usage": usage[-1] if usage else None,
            "stderr_head": done.stderr[:300]}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, mode=0o700)
    live = Path.home() / ".codex/hooks.json"
    live_before = live.read_bytes() if live.exists() else None
    project = fixture()
    truth = ground_truth(project, COMMANDS)
    truth2 = ground_truth(project, COMMANDS2)
    gain_before = json.loads(sh("rtk", "gain", "-f", "json").stdout)["summary"]
    arms = {}
    for label, rtk_hook, agents, trusted, commands, strict in (
            ("R0-probe-only", False, False, True, COMMANDS, True), ("R1-hook-trusted", True, False, True, COMMANDS, True),
            ("R1u-hook-untrusted", True, False, False, COMMANDS, True), ("R2-hook-and-prefix", True, True, True, COMMANDS, True),
            ("B2-hook-battery2", True, False, True, COMMANDS2, True),
            ("R2b-prefix-instruction-and-hook", True, True, True, COMMANDS, False),
            ("R1p-hook-trusted-rtk-not-on-path", True, False, True, COMMANDS, True)):
        if ONLY and label not in ONLY:
            continue
        codex_home = make_home(label, project, rtk_hook, agents)
        listing = [{k: h.get(k) for k in ("key", "eventName", "matcher", "command", "trustStatus", "enabled")}
                   for h in hooks_state(codex_home, project)]
        if trusted:
            trust_all(codex_home, project)
        after = [{k: h.get(k) for k in ("key", "trustStatus")} for h in hooks_state(codex_home, project)]
        arms[label] = run_arm(label, codex_home, project, commands, strict,
                              "/usr/bin:/bin" if label.startswith("R1p") else None)
        arms[label]["hooks_before_trust"] = listing
        arms[label]["trust_after"] = after
    gain_after = json.loads(sh("rtk", "gain", "-f", "json").stdout)["summary"]
    live_after = live.read_bytes() if live.exists() else None
    result = {"ground_truth": truth, "ground_truth_battery2": truth2, "arms": arms, "live_hooks_json_unchanged": live_before == live_after,
              "gain": {"commands": [gain_before["total_commands"], gain_after["total_commands"]],
                       "saved": [gain_before["total_saved"], gain_after["total_saved"]]}}
    (OUT / "result.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    shutil.rmtree(WORK, ignore_errors=True)
    print(OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
