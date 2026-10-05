#!/usr/bin/env python3
"""Run the install plan's `command-output` Codex hook steps in a scratch HOME and print what each returned (one JSON object).

    python3 plan_row_scratch_run.py [OUTFILE]    # default: ~/.local/state/native-agent-stack/e2e/plan-row-scratch-run.json

The program text of every step is read from evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json (the exact strings the plan runs),
not retyped here: the config install, `rtk init -g --codex`, the trust command, and the post_install acceptance program (run with bash -euo
pipefail, as accept.sh does); the `--check` line is the last line of that program. Around them: a `--check` before the hook exists (exit 4), one
after `rtk init` and before the trust (exit 5), the jq filter and test of the after_sign_in program against synthetic streams of `codex exec
--json` in the shape recorded from a real session (one that passes and five negative fixtures: a failed rewritten command, a non-zero exit, a
declined command, no rtk prefix, no command item; the model call itself needs the sign-in and is not run), and the execution-rule review of the
trust tool in four more scratch homes, each with the real rtk and the real codex: the hcom rules of #713 (fixtures/hcom-deny.rules; rtk rewrites
none of them: the trust proceeds, and a `git push` rule added after the grant makes `--check` exit 6 and the trust refuse), a `git push`
forbid rule without an `rtk git push` twin (the trust is refused before anything is written; --allow-exec-rules accepts it), the same rule with
its twin (the trust proceeds), and an unreadable rules directory (the trust is refused: the review fails closed). Codex's own `codex execpolicy
check` is run on the rule for `git push` and `git commit`, and each answer must be an exit 0 with a valid response before its decision counts.
Nothing leaves the scratch HOME: rtk and Codex write their files there, and the live ~/.codex and rtk
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN_DIR = ROOT / "evidence" / "artifacts" / "new-wsl-install-plan-20261002"
HCOM_RULES = (HERE / "fixtures" / "hcom-deny.rules").read_text(encoding="utf-8")
GIT_PUSH = 'prefix_rule(pattern = ["git", "push"], decision = "forbidden", justification = "pushes need the owner")\n'
GIT_PUSH_TWIN = 'prefix_rule(pattern = ["rtk", "git", "push"], decision = "forbidden", justification = "pushes need the owner")\n'


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


def evaluator_answer(done: subprocess.CompletedProcess) -> tuple[bool, dict]:
    """A `codex execpolicy check` answer counts only with exit 0 and a JSON object whose matchedRules is a list (and a decision exactly when a rule
    matched); anything else is invalid, not an unmatched command."""
    try:
        verdict = json.loads(done.stdout)
    except ValueError:
        return False, {}
    valid = (done.returncode == 0 and isinstance(verdict, dict) and isinstance(verdict.get("matchedRules"), list)
             and (verdict.get("decision") is None) == (not verdict["matchedRules"]))
    return valid, verdict if valid else {}


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
    check_line = post_program.splitlines()[-1]
    assert "codex_hook_trust.py" in check_line and check_line.endswith("--check"), check_line
    check_cmd = 'e="${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}"; ' + check_line
    busy = subprocess.run(["pgrep", "-x", "codex"], capture_output=True, text=True, check=False).stdout.split()
    steps = []
    with tempfile.TemporaryDirectory(prefix="plan-row-") as scratch:
        eco = Path(scratch) / "eco"
        (eco / "bin").mkdir(parents=True)
        os.symlink(shutil.which("rtk"), eco / "bin" / "rtk")
        hooks = json.dumps({"hooks": {"PreToolUse": [{"matcher": "", "hooks": [
            {"type": "command", "command": "python3 /fixture/memory_hook.py"}]}]}}, indent=2) + "\n"

        def make_home(name: str, rules: dict[str, str] | None = None) -> dict:
            """A scratch HOME with a user-layer hooks.json (a memory hook), an empty config.toml and, when given, rules files; the environment for it."""
            home = Path(scratch) / name
            (home / ".codex").mkdir(parents=True)
            (home / ".codex" / "hooks.json").write_text(hooks, encoding="utf-8")
            (home / ".codex" / "config.toml").write_text("# scratch user layer\n", encoding="utf-8")
            if rules is not None:
                (home / ".codex" / "rules").mkdir()
                for fname, body in rules.items():
                    (home / ".codex" / "rules" / fname).write_text(body, encoding="utf-8")
            settings = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(home / ".local/share"),
                        "XDG_CACHE_HOME": str(home / ".cache"), "XDG_STATE_HOME": str(home / ".local/state"), "RTK_TELEMETRY_DISABLED": "1",
                        "ECO_ROOT": str(eco), "plan_dir": str(PLAN_DIR), "repo_root": str(ROOT)}
            settings.pop("CODEX_HOME", None)
            return settings

        env = make_home("fake-home")
        deviation = None
        execpolicy: list[dict] = []
        if busy:
            trust_cmd = trust_cmd + " --codex-process-name no-such-process-name"
            deviation = (f"{len(busy)} codex process(es) were running on the host, so the trust command carries "
                         f"--codex-process-name no-such-process-name (the tool would otherwise refuse, exit 2)")

        def run(label: str, program: str, expect: int | None = None, environment: dict | None = None) -> None:
            done = subprocess.run(["bash", "-euo", "pipefail", "-c", program], cwd=ROOT, env=environment or env, capture_output=True, text=True,
                                  timeout=300, check=False, stdin=subprocess.DEVNULL)
            clean = lambda text: [line.replace(scratch, "<scratch>")[:260] for line in text.splitlines() if line.strip()]  # noqa: E731
            steps.append({"step": label, "exit": done.returncode, "expected_exit": expect, "stdout_tail": clean(done.stdout)[-12:],
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
        # does not match `rtk git push`: Codex's own evaluator first, then the trust tool's review in scratch homes with the real rtk and codex.
        gate = Path(scratch) / "gate.rules"
        gate.write_text(GIT_PUSH + 'prefix_rule(pattern = ["git", "commit"], decision = "prompt", justification = "commits are reviewed")\n', encoding="utf-8")
        for command in ("git push origin main", "rtk git push origin main", "git commit -m x", "rtk git commit -m x", "git status", "rtk git status"):
            done = subprocess.run(["codex", "execpolicy", "check", "--rules", str(gate), "--", *command.split()], env=env, capture_output=True,
                                  text=True, timeout=120, check=False, stdin=subprocess.DEVNULL)
            valid, verdict = evaluator_answer(done)
            execpolicy.append({"command": command, "exit": done.returncode, "valid": valid, "decision": verdict.get("decision"),
                               "matched_prefixes": [m.get("prefixRuleMatch", {}).get("matchedPrefix") for m in verdict.get("matchedRules", [])]})

        def home_with_hook(name: str, rules: dict[str, str]) -> dict:
            settings = make_home(name, rules)
            run(f"{name}: plan command 3 (the exclusions config)", config_cmd, 0, settings)
            run(f"{name}: plan command 5 (rtk init -g --codex)", init_cmd, 0, settings)
            return settings

        hcom = home_with_hook("rules-hcom", {"hcom-deny.rules": HCOM_RULES})
        run("rules-hcom (#713's four hcom rules; rtk rewrites none of them): --check before the trust", check_cmd, 5, hcom)
        run("rules-hcom: the plan's trust command proceeds", trust_cmd, 0, hcom)
        run("rules-hcom: --check", check_cmd, 0, hcom)
        (Path(hcom["HOME"]) / ".codex" / "rules" / "default.rules").write_text(GIT_PUSH, encoding="utf-8")
        run("rules-hcom: a git push forbid rule is added after the grant: --check exits 6", check_cmd, 6, hcom)
        run("rules-hcom: the trust command now refuses although the hook is already trusted", trust_cmd, 2, hcom)

        exposed = home_with_hook("rules-exposed", {"default.rules": GIT_PUSH})
        run("rules-exposed (a git push forbid rule, no rtk twin): the trust command is refused before anything is written", trust_cmd, 2, exposed)
        run("rules-exposed: --check says the hook is not trusted (nothing was written)", check_cmd, 5, exposed)
        run("rules-exposed: --allow-exec-rules accepts the exposure", trust_cmd + " --allow-exec-rules", 0, exposed)
        run("rules-exposed: --check after the accepted trust exits 6", check_cmd, 6, exposed)
        run("rules-exposed: --check --allow-exec-rules", check_cmd + " --allow-exec-rules", 0, exposed)

        twin = home_with_hook("rules-twin", {"default.rules": GIT_PUSH + GIT_PUSH_TWIN})
        run("rules-twin (the git push rule and its rtk git push twin): the trust command proceeds", trust_cmd, 0, twin)
        run("rules-twin: --check", check_cmd, 0, twin)

        unreadable = home_with_hook("rules-unreadable", {"default.rules": GIT_PUSH})
        rules_dir = Path(unreadable["HOME"]) / ".codex" / "rules"
        if os.geteuid() == 0:
            steps.append({"step": "rules-unreadable: skipped (running as root, so a mode 000 directory is still listable)", "exit": 2,
                          "expected_exit": 2, "stdout_tail": [], "stderr_tail": []})
        else:
            rules_dir.chmod(0)
            try:
                run("rules-unreadable (the rules directory cannot be listed): the trust command fails closed", trust_cmd, 2, unreadable)
            finally:
                rules_dir.chmod(0o755)
    record = {"schema": "plan-row-scratch-run/2", "evidence_class": "local_integration: one run, one host, scratch HOMEs, the real rtk and codex (the stream is synthetic)",
              "rtk": subprocess.run(["rtk", "--version"], capture_output=True, text=True, check=False).stdout.strip(),
              "codex": subprocess.run(["codex", "--version"], capture_output=True, text=True, check=False).stdout.strip(),
              "deviation": deviation, "steps": steps, "execpolicy_check": execpolicy,
              "all_as_expected": all(step["exit"] == step["expected_exit"] for step in steps) and all(e["valid"] for e in execpolicy) and
              [e["decision"] for e in execpolicy] == ["forbidden", None, "prompt", None, None, None]}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target}: {len(steps)} steps, all as expected: {record['all_as_expected']}")
    return 0 if record["all_as_expected"] else 1


if __name__ == "__main__":
    sys.exit(main())
