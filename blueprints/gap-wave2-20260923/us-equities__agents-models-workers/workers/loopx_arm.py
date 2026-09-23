#!/usr/bin/env python3
"""LoopX 1.1.0 arm (non-adopted candidate, gap 16): one governed `loopx turn run-once`
through the built-in codex-cli adapter, isolated-headless, read-only sandbox, on the same
fact-extraction task, inputs and gold as the gap-0 arms. Fixture layout follows upstream
examples/loopx-turn-codex-cli-e2e-smoke.py at v1.1.0 (goal state file + registry).

The codex binary handed to LoopX is a wrapper that only adds `-c features.hooks=false
-c features.plugin_hooks=false --ephemeral` to `codex exec` (isolation rule) and tees the
native --json event stream to a log so turn usage can be read.
Usage: loopx_arm.py RUN_DIR   (run with the LoopX venv python; RUN_DIR must not exist)
"""
import json, os, shutil, stat, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve(); REPO = HERE.parents[4]
GOAL, AGENT, TODO = "g2amw-fact-extraction", "codex-turn-g2amw", "todo_g2amwfacts01"
REAL_CODEX = Path.home() / ".local/share/codex-ecosystem/bin/codex"
TASK = (HERE.parent / "task-prompt.md").read_text().replace("\n", " ")

def main():
    run = Path(sys.argv[1]).resolve(); run.mkdir(parents=False)
    project, runtime, ws, home = run / "project", run / "runtime", run / "workspace", run / "home"
    for p in (runtime, ws, home):
        p.mkdir(parents=True)
    shutil.copyfile(REPO / "blueprints/us-equities/workers/receipt.json", ws / "worker-receipt.json")
    shutil.copyfile(REPO / "blueprints/us-equities/deerflow/research-receipt.json", ws / "acp-research-receipt.json")
    state = project / ".codex/goals" / GOAL / "ACTIVE_GOAL_STATE.md"; state.parent.mkdir(parents=True)
    state.write_text("\n".join(["---", "status: active", "updated_at: 2026-09-23T00:00:00+00:00", "---", "",
        "# Gap-wave-2 fact extraction", "", "## Agent Todo", "",
        f"- [ ] [P0] {TASK} Put that JSON object, verbatim and alone, in the typed result's summary field.",
        f"  <!-- loopx:todo todo_id={TODO} status=open task_class=advancement_task action_kind=real_cli_e2e claimed_by={AGENT} priority=P0 -->", ""]))
    reg = project / ".loopx/registry.json"; reg.parent.mkdir(parents=True)
    reg.write_text(json.dumps({"schema_version": 1, "common_runtime_root": str(runtime), "goals": [{
        "id": GOAL, "domain": "gap-wave2-fixture", "status": "active", "repo": str(project),
        "state_file": str(state.relative_to(project)), "adapter": {"kind": "fixture_v0", "status": "connected-delivery"},
        "quota": {"compute": 1.0, "window_hours": 24},
        "coordination": {"agent_model": "peer_v1", "registered_agents": [AGENT],
                         "agent_profiles": {AGENT: {"schema_version": "agent_profile_v1", "profile_role": "fixture", "scope": "gap-wave2 comparison"}},
                         "write_scope": ["docs/**"]}}]}, indent=2) + "\n")
    events = run / "codex-events.jsonl"
    wrapper = run / "codex-wrapper.sh"
    wrapper.write_text(f"""#!/usr/bin/env bash
if [ "$1" = exec ]; then shift; set -- exec -c features.hooks=false -c features.plugin_hooks=false --ephemeral "$@"; fi
echo "ARGV: $*" >> {run}/codex-argv.log
CODEX_HOME={Path.home() / '.codex'} "{REAL_CODEX}" "$@" | tee -a "{events}"
exit ${{PIPESTATUS[0]}}
""")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    validator = [sys.executable, str(HERE.parent / "loopx_validator.py"), str(HERE.parent / "gold.json"), str(run / "validator-stdin.json")]
    argv = [str(Path(sys.executable).with_name("loopx")), "--registry", str(reg), "--runtime-root", str(runtime), "--format", "json",
            "turn", "run-once", "--goal-id", GOAL, "--agent-id", AGENT, "--turn-instance-id", "g2amw-turn-1",
            "--host", "codex-cli", "--execution-mode", "isolated-headless", "--project", str(ws),
            "--codex-bin", str(wrapper), "--codex-sandbox", "read-only", "--codex-model", "gpt-6-astra",
            "--validation-command-json", json.dumps(validator), "--scan-root", str(project.parent),
            "--no-global-sync", "--timeout-seconds", "300", "--execute"]
    env = dict(os.environ, HOME=str(home))
    t0 = time.monotonic()
    p = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=420)
    out = {"argv": argv, "exit": p.returncode, "elapsed_seconds": round(time.monotonic() - t0, 3),
           "stdout": p.stdout, "stderr_tail": p.stderr[-3000:]}
    usage = [json.loads(l)["usage"] for l in events.read_text().splitlines() if l.startswith("{") and '"turn.completed"' in l] if events.exists() else []
    out["codex_turn_completed_usage"] = usage
    (run / "arm-result.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({"exit": p.returncode, "elapsed": out["elapsed_seconds"], "usage": usage, "stdout_head": p.stdout[:600]}))

if __name__ == "__main__":
    main()
