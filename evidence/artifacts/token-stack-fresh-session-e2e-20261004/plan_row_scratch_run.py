#!/usr/bin/env python3
"""Run the install plan's `command-output` Codex hook steps in a scratch HOME and print what each returned (one JSON object).

    python3 plan_row_scratch_run.py [OUTFILE]    # default: ~/.local/state/native-agent-stack/e2e/plan-row-scratch-run.json

The program text of every step is read from evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json (the exact strings the plan runs),
not retyped here: the config install, `rtk init -g --codex`, the trust command, and the post_install acceptance program (run with bash -euo
pipefail, as accept.sh does). Around them: a `--check` before the hook exists (exit 4), one after `rtk init` and before the trust (exit 5), and the
execution-rule guard (Codex's own `codex execpolicy check` on a rule for `git push`, then the trust command refused beside a
rules file and accepted with --allow-exec-rules), the jq filter and test of the after_sign_in program against synthetic streams of `codex exec --json` in the shape recorded from a real session (one that
passes and five negative fixtures: a failed rewritten command, a non-zero exit, a declined command, no rtk prefix, no command item; the model call itself
needs the sign-in and is not run). Nothing leaves the scratch HOME: rtk and Codex write their files there, and the live ~/.codex and rtk
configuration are not read or written. The scratch ECO_ROOT links the installed rtk instead of running the plan's download and extract steps.
The trust command refuses while a codex process runs (the tool's own rule); when other codex processes run on the host, the scratch run appends
`--codex-process-name no-such-process-name` to it and says so, as codex_hook_qual.py does. One run, one host: local_integration evidence.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN_DIR = ROOT / "evidence" / "artifacts" / "new-wsl-install-plan-20261002"


def stream(command: str | None, exit_code: int | None, status: str) -> str:
    """A `codex exec --json` stream in the shape recorded from a real session (JSONL command item: command, aggregated_output, exit_code, status;
    codex-rs/exec/src/exec_events.rs L161-L166 at rust-v0.159.3 and rust-v0.160.0)."""
    lines = [{"type": "thread.started", "thread_id": "fixture"}]
    if command is not None:
        lines.append({"type": "item.completed", "item": {"id": "item_0", "type": "command_execution", "command": command,
                                                          "aggregated_output": "", "exit_code": exit_code, "status": status}})
    lines.append({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}})
    return "\n".join(json.dumps(line) for line in lines) + "\n"


RTK = "/bin/bash -lc 'rtk git status --short'"
# (label, stream, the exit status the plan's after_sign_in check must end with: 0 passes, 1 fails)
AFTER_SIGN_IN_FIXTURES = (
    ("the rewritten command ran and exited 0", stream(RTK, 0, "completed"), 0),
    ("the rewritten command failed (rtk not on the launcher's PATH: exit 127)", stream(RTK, 127, "failed"), 1),
    ("the rewritten command completed with a non-zero exit status", stream(RTK, 1, "completed"), 1),
    ("the rewritten command was declined", stream(RTK, None, "declined"), 1),
    ("the command ran without the rtk prefix (no hook)", stream("/bin/bash -lc 'git status --short'", 0, "completed"), 1),
    ("no command item at all", stream(None, None, "completed"), 1),
)


def main() -> int:
    for tool in ("rtk", "codex", "jq"):
        if not shutil.which(tool):
            print(f"needs {tool} on PATH", file=sys.stderr)
            return 2
    target = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else \
        Path.home() / ".local/state/native-agent-stack/e2e/plan-row-scratch-run.json"
    plan = json.loads((PLAN_DIR / "install-plan.json").read_text(encoding="utf-8"))
    row = next(r for r in plan["owners"] if r["slot"] == "command-output")
    config_cmd, init_cmd, trust_cmd = row["commands"][2], row["commands"][4], row["commands"][5]
    assert "rtk-config.toml" in config_cmd and "init -g --codex" in init_cmd and "codex_hook_trust.py" in trust_cmd and "--apply" in trust_cmd
    post_program = row["acceptance"]["post_install"]["command"]
    after_program = row["acceptance"]["after_sign_in"]["command"]
    check_cmd = 'python3 "$repo_root/tools/adoption/codex_hook_trust.py" --command "rtk hook codex" --check'
    busy = subprocess.run(["pgrep", "-x", "codex"], capture_output=True, text=True, check=False).stdout.split()
    steps = []
    with tempfile.TemporaryDirectory(prefix="plan-row-") as scratch:
        home = Path(scratch) / "fake-home"
        eco = Path(scratch) / "eco"
        (home / ".codex").mkdir(parents=True)
        (eco / "bin").mkdir(parents=True)
        os.symlink(shutil.which("rtk"), eco / "bin" / "rtk")
        (home / ".codex" / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "", "hooks": [
            {"type": "command", "command": "python3 /fixture/memory_hook.py"}]}]}}, indent=2) + "\n", encoding="utf-8")
        (home / ".codex" / "config.toml").write_text("# scratch user layer\n", encoding="utf-8")
        env = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(home / ".local/share"),
               "XDG_CACHE_HOME": str(home / ".cache"), "XDG_STATE_HOME": str(home / ".local/state"), "RTK_TELEMETRY_DISABLED": "1",
               "ECO_ROOT": str(eco), "plan_dir": str(PLAN_DIR), "repo_root": str(ROOT)}
        env.pop("CODEX_HOME", None)
        deviation = None
        execpolicy: list[dict] = []
        if busy:
            trust_cmd = trust_cmd + " --codex-process-name no-such-process-name"
            deviation = (f"{len(busy)} codex process(es) were running on the host, so the trust command carries "
                         f"--codex-process-name no-such-process-name (the tool would otherwise refuse, exit 2)")

        def run(label: str, program: str, expect: int | None = None, environment: dict | None = None) -> None:
            done = subprocess.run(["bash", "-euo", "pipefail", "-c", program], cwd=ROOT, env=environment or env, capture_output=True, text=True,
                                  timeout=300, check=False, stdin=subprocess.DEVNULL)
            clean = lambda text: [line.replace(scratch, "<scratch>")[:200] for line in text.splitlines() if line.strip()]  # noqa: E731
            steps.append({"step": label, "exit": done.returncode, "expected_exit": expect, "stdout_tail": clean(done.stdout)[-6:],
                          "stderr_tail": clean(done.stderr)[-3:]})

        run("--check before any rtk hook exists", check_cmd, 4)
        run("plan command 3: the exact five-entry exclusions config", config_cmd, 0)
        run("plan command 5: rtk init -g --codex", init_cmd, 0)
        run("--check after init, before the trust", check_cmd, 5)
        run("plan command 6: the trust", trust_cmd, 0)
        run("the plan's post_install acceptance program", post_program, 0)
        jq_line = next(line for line in after_program.splitlines() if line.startswith("ran=$(jq -rs "))
        jq_program = re.search(r"jq -rs ('.*?')", jq_line).group(1)
        assert after_program.splitlines()[-1] == '[[ "$ran" == "true" ]]', after_program.splitlines()[-1]
        for number, (label, fixture, expected) in enumerate(AFTER_SIGN_IN_FIXTURES):
            fixture_file = Path(scratch) / f"out-{number}.jsonl"
            fixture_file.write_text(fixture, encoding="utf-8")
            run(f"the after_sign_in filter and test on a synthetic stream: {label} (the model call is not run)",
                f'ran=$(jq -rs {jq_program} "{fixture_file}"); printf "%s\\n" "$ran"; [[ "$ran" == "true" ]]', expected)
        # Execution rules and the rewritten command. Codex matches rules against the command words after the hook's rewrite, so a rule on `git push`
        # does not match `rtk git push`: Codex's own evaluator, then the trust tool's refusal and its explicit acceptance, in a second scratch home.
        gate = Path(scratch) / "gate.rules"
        gate.write_text('prefix_rule(pattern = ["git", "push"], decision = "forbidden", justification = "pushes need the owner")\n'
                        'prefix_rule(pattern = ["git", "commit"], decision = "prompt", justification = "commits are reviewed")\n', encoding="utf-8")
        for command in ("git push origin main", "rtk git push origin main", "git commit -m x", "rtk git commit -m x", "git status", "rtk git status"):
            done = subprocess.run(["codex", "execpolicy", "check", "--rules", str(gate), "--", *command.split()], env=env, capture_output=True,
                                  text=True, timeout=120, check=False, stdin=subprocess.DEVNULL)
            verdict = json.loads(done.stdout) if done.returncode == 0 and done.stdout.strip() else {}
            execpolicy.append({"command": command, "exit": done.returncode, "decision": verdict.get("decision"),
                               "matched_prefixes": [m.get("prefixRuleMatch", {}).get("matchedPrefix") for m in verdict.get("matchedRules", [])]})
        home2 = Path(scratch) / "fake-home-2"
        (home2 / ".codex" / "rules").mkdir(parents=True)
        (home2 / ".codex" / "hooks.json").write_text((home / ".codex" / "hooks.json").read_text(encoding="utf-8")
                                                   .replace("rtk hook codex", "python3 /fixture/memory_hook.py"), encoding="utf-8")
        (home2 / ".codex" / "config.toml").write_text("# scratch user layer\n", encoding="utf-8")
        (home2 / ".codex" / "rules" / "default.rules").write_text(gate.read_text(encoding="utf-8"), encoding="utf-8")
        env2 = {**env, "HOME": str(home2), "XDG_CONFIG_HOME": str(home2 / ".config"), "XDG_DATA_HOME": str(home2 / ".local/share"),
                "XDG_CACHE_HOME": str(home2 / ".cache"), "XDG_STATE_HOME": str(home2 / ".local/state")}
        run("a second Codex home with an execution rules file: rtk init -g --codex", init_cmd, 0, env2)
        run("the plan's trust command is refused while the rules file is there", trust_cmd, 2, env2)
        run("--check still reports the hook untrusted", check_cmd, 5, env2)
        run("the explicit acceptance: the trust command with --allow-exec-rules", trust_cmd + " --allow-exec-rules", 0, env2)
        run("--check after the accepted trust", check_cmd, 0, env2)
    record = {"schema": "plan-row-scratch-run/1", "evidence_class": "local_integration: one run, one host, a scratch HOME (the stream is synthetic)",
              "rtk": subprocess.run(["rtk", "--version"], capture_output=True, text=True, check=False).stdout.strip(),
              "codex": subprocess.run(["codex", "--version"], capture_output=True, text=True, check=False).stdout.strip(),
              "deviation": deviation, "steps": steps, "execpolicy_check": execpolicy,
              "all_as_expected": all(step["exit"] == step["expected_exit"] for step in steps) and
              [e["decision"] for e in execpolicy] == ["forbidden", None, "prompt", None, None, None]}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target}: {len(steps)} steps, all as expected: {record['all_as_expected']}")
    return 0 if record["all_as_expected"] else 1


if __name__ == "__main__":
    sys.exit(main())
