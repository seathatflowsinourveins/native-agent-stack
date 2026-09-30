#!/usr/bin/env python3
"""R1: SIGKILL a real pi run after its Nth model response and resume it with --continue (local integration runner).

    run_r1.py --state DIR [--arm stack|stack-ext|plain] [--task TASK] [--kill-after N] [--tag TAG]

Segment 1 runs the arm's pi on the task exactly as run_task.py does, with the run id as the gateway session id. When the
Nth assistant message has ended, the whole process tree is killed with SIGKILL. Segment 2 runs `pi --continue "Continue."`
in the same session directory and workspace, with the run id plus "-resume" as the gateway session id, and the task is
checked at the end. r1.json records what the session file kept, whether any descendant survived 3 s, both segments' pi-reported
usage per request, and the task check. Gateway-side rows are joined afterwards with gateway_usage.py on the two run ids.
Nothing here judges the result: a run that finishes before the kill records killed=false.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import fixtures
import run_task as rt


def assistant_ends(path):
    n = 0
    try:
        for line in path.read_text().splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") == "message_end" and (e.get("message") or {}).get("role") == "assistant":
                n += 1
    except OSError:
        pass
    return n


def events_of(path):
    out = []
    for line in path.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--arm", choices=["stack", "stack-ext", "plain"], default="stack")
    parser.add_argument("--task", choices=fixtures.TASKS, default="multi-file-rename")
    parser.add_argument("--kill-after", type=int, default=2)
    parser.add_argument("--tag", default="r1")
    parser.add_argument("--timeout", type=int, default=900)
    a = parser.parse_args()
    stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    run_id = f"pi-trial-{a.arm}-{a.task}-r1-{stamp}-{a.tag}"
    run_dir = a.state / "runs" / run_id
    ws, sessions = run_dir / "ws", run_dir / "sessions"
    run_dir.mkdir(parents=True)
    head = fixtures.make(a.task, ws)
    home = a.state / "arms" / a.arm / "home"
    env = {**os.environ, "PI_TRIAL_RUN_ID": run_id, "PYTHONDONTWRITEBYTECODE": "1"}
    base = [str(a.state / "bin" / f"pi-{a.arm}"), "--print", "--mode", "json", "--session-dir", str(sessions), "--thinking", rt.THINKING]
    if a.arm != "plain":
        base += ["-xt", rt.EXCLUDE]
    ev1 = run_dir / "events-1.jsonl"
    state_before = rt.gateway_state(home / ".pi" / "agent" / "models.json")
    t0 = time.time()
    proc = subprocess.Popen(base + [fixtures.INSTRUCTIONS[a.task]], cwd=ws, env=env, stdin=subprocess.DEVNULL, stdout=open(ev1, "w"),
                            stderr=open(run_dir / "stderr-1.txt", "w"), start_new_session=True)
    killed, victims, seen = False, [], 0
    while proc.poll() is None and time.time() - t0 < a.timeout:
        time.sleep(0.4)
        seen = assistant_ends(ev1)
        if seen >= a.kill_after:
            victims = rt.descendants(proc.pid)
            rt.kill_tree(proc)
            killed = True
            break
    if not killed and proc.poll() is None:
        rt.kill_tree(proc)
    proc.wait()
    seg1_wall = round(time.time() - t0, 1)
    time.sleep(3.0)
    survivors = [pid for pid in victims if alive(pid)]
    files = sorted(sessions.glob("*.jsonl")) if sessions.exists() else []
    roles = []
    for f in files[:1]:
        for line in f.read_text().splitlines():
            try:
                m = json.loads(line)
            except ValueError:
                continue
            msg = m.get("message") if isinstance(m, dict) else None
            if isinstance(msg, dict) and msg.get("role"):
                roles.append(msg["role"])
    seg1 = rt.summarize(events_of(ev1), home)
    result = {"run_id": run_id, "resume_run_id": run_id + "-resume", "arm": a.arm, "task": a.task, "fixture_commit": head,
              "kill_after_responses": a.kill_after, "responses_seen_before_kill": seen, "killed": killed,
              "descendants_at_kill": len(victims), "survivors_after_3s": len(survivors), "session_files": len(files),
              "session_roles_kept": roles, "gateway_state_before": state_before, "segment1_wall_s": seg1_wall, "segment1": seg1}
    if killed:
        env2 = {**env, "PI_TRIAL_RUN_ID": run_id + "-resume"}
        ev2 = run_dir / "events-2.jsonl"
        t1 = time.time()
        p2 = subprocess.Popen(base + ["--continue", "Continue."], cwd=ws, env=env2, stdin=subprocess.DEVNULL, stdout=open(ev2, "w"),
                              stderr=open(run_dir / "stderr-2.txt", "w"), start_new_session=True)
        try:
            code2 = p2.wait(timeout=a.timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            rt.kill_tree(p2)
            p2.wait()
            code2, timed_out = None, True
        result["segment2"] = {"exit_code": code2, "timed_out": timed_out, "wall_s": round(time.time() - t1, 1),
                              "pi_reported": rt.summarize(events_of(ev2), home)}
    result["check"] = fixtures.check(a.task, ws)
    (run_dir / "r1.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({k: result[k] for k in ("run_id", "resume_run_id", "killed", "responses_seen_before_kill", "survivors_after_3s")} |
                     {"passed": result["check"]["passed"]}))
    sys.exit(0 if result["check"]["passed"] and killed else 1)


if __name__ == "__main__":
    main()
