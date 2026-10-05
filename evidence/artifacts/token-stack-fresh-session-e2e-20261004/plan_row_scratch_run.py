#!/usr/bin/env python3
"""Run the install plan's `command-output` Codex hook steps in a scratch HOME and print what each returned (one JSON object).

    python3 plan_row_scratch_run.py [OUTFILE]    # default: ~/.local/state/native-agent-stack/e2e/plan-row-scratch-run.json

The program text of every step is read from evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json (the exact strings the plan runs),
not retyped here: the config install, `rtk init -g --codex`, the trust command, and the post_install acceptance program (run with bash -euo
pipefail, as accept.sh does). Around them: a `--check` before the hook exists (exit 4), one after `rtk init` and before the trust (exit 5), and the
jq filter of the after_sign_in program against a synthetic stream of `codex exec --json` in the shape recorded from a real session (the model call
itself needs the sign-in and is not run). Nothing leaves the scratch HOME: rtk and Codex write their files there, and the live ~/.codex and rtk
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
FIXTURE_STREAM = "\n".join([
    json.dumps({"type": "thread.started", "thread_id": "fixture"}),
    json.dumps({"type": "item.completed", "item": {"id": "item_0", "type": "command_execution",
                                                   "command": "/bin/bash -lc 'rtk git status --short'", "aggregated_output": "",
                                                   "exit_code": 0, "status": "completed"}}),
    json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}),
]) + "\n"


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
        if busy:
            trust_cmd = trust_cmd + " --codex-process-name no-such-process-name"
            deviation = (f"{len(busy)} codex process(es) were running on the host, so the trust command carries "
                         f"--codex-process-name no-such-process-name (the tool would otherwise refuse, exit 2)")

        def run(label: str, program: str, expect: int | None = None) -> None:
            done = subprocess.run(["bash", "-euo", "pipefail", "-c", program], cwd=ROOT, env=env, capture_output=True, text=True,
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
        stream = Path(scratch) / "out.jsonl"
        stream.write_text(FIXTURE_STREAM, encoding="utf-8")
        jq_line = next(line for line in after_program.splitlines() if line.startswith("executed=$(jq -rs "))
        jq_program = re.search(r"jq -rs ('.*?')", jq_line).group(1)
        run("the after_sign_in jq filter on a synthetic codex exec stream (the model call is not run)",
            f'executed=$(jq -rs {jq_program} "{stream}"); printf "%s\\n" "$executed"; [[ "$executed" == *"rtk git status"* ]]', 0)
    record = {"schema": "plan-row-scratch-run/1", "evidence_class": "local_integration: one run, one host, a scratch HOME (the stream is synthetic)",
              "rtk": subprocess.run(["rtk", "--version"], capture_output=True, text=True, check=False).stdout.strip(),
              "codex": subprocess.run(["codex", "--version"], capture_output=True, text=True, check=False).stdout.strip(),
              "deviation": deviation, "steps": steps,
              "all_as_expected": all(step["exit"] == step["expected_exit"] for step in steps)}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target}: {len(steps)} steps, all as expected: {record['all_as_expected']}")
    return 0 if record["all_as_expected"] else 1


if __name__ == "__main__":
    sys.exit(main())
