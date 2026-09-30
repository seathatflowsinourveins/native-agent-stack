#!/usr/bin/env python3
"""Run one S2 task attempt through one staged arm and write a per-run result (local integration runner).

    run_task.py --state DIR --arm stack|stack-ext|plain --task TASK --attempt N [--timeout S] [--tag TAG] [--base-url URL]

Creates a fresh workspace from the frozen fixture, runs the arm's pi in JSON mode with a unique run id (sent to the
gateway as X-OmniRoute-Session-Id and X-Correlation-Id), checks the task, and writes RUN/result.json with the
pi-reported usage, tool calls by lane and the RTK tracker delta. Gateway-side usage is joined afterwards on the run id
by gateway_usage.py. --base-url points the provider elsewhere (used with pi_stub.py for the runner's controls).
Both arms run with PYTHONDONTWRITEBYTECODE=1 so a same-second edit cannot hit a stale .pyc.
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fixtures  # noqa: E402

EXCLUDE = "ctx_upgrade,ctx_purge,ctx_doctor,ctx_insight"
THINKING = "xhigh"  # the 6.1 Sol registry entry does not exist at the gateway, so cx/ clamps max to xhigh; ask for what runs
BUILTIN = ["read", "bash", "edit", "write"]


def descendants(pid):
    rows = subprocess.run(["ps", "-eo", "pid=,ppid="], capture_output=True, text=True).stdout.splitlines()
    children = {}
    for line in rows:
        child, parent = (int(x) for x in line.split())
        children.setdefault(parent, []).append(child)
    found, todo = [], [pid]
    while todo:
        for child in children.get(todo.pop(), []):
            found.append(child)
            todo.append(child)
    return found


def kill_tree(proc):
    victims = descendants(proc.pid) + [proc.pid]
    for pid in victims:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def rtk_commands(home):
    out = subprocess.run(["rtk", "gain", "--format", "json"], capture_output=True, text=True,
                         env={**os.environ, "HOME": str(home)}, cwd=home).stdout
    try:
        return int(json.loads(out)["summary"]["total_commands"])
    except Exception:
        return None


def rtk_eligible(home, command):
    result = subprocess.run(["rtk", "rewrite", command], capture_output=True, text=True, env={**os.environ, "HOME": str(home)})
    return result.returncode in (0, 3)


def gateway_state(models_json):
    """Read-only snapshot of the entry gateway's compression settings (no credentials in it)."""
    try:
        base = json.loads(Path(models_json).read_text())["providers"]["omni-fw"]["baseUrl"]
        origin = base.rsplit("/v1", 1)[0]
        with urllib.request.urlopen(origin + "/api/settings/compression", timeout=10) as response:
            data = json.loads(response.read())
        engines = data.get("engines") or {}
        on = sorted(k for k, v in engines.items() if (v.get("enabled") if isinstance(v, dict) else v) is True)
        return {"origin": origin, "compression_enabled": data.get("enabled"), "defaultMode": data.get("defaultMode"), "engines_on": on}
    except Exception as error:
        return {"error": repr(error)[:120]}


def headerless_uncompressed(state):
    """True when a request without the compression header passes through untouched at this gateway."""
    if "error" in state or state.get("compression_enabled") is None:
        return None
    return state["compression_enabled"] is not True or (state["defaultMode"] == "off" and not state["engines_on"])


def parse_error(text):
    """Structured fields of a provider error such as `omni-fw API error (429): {json}`; no free text beyond `message`."""
    head, _, tail = text.partition("): ")
    out = {"http": head.rsplit("(", 1)[-1] if head else None}
    try:
        body = json.loads(tail)
        out.update({k: body[k] for k in ("message", "type", "code", "model", "reset_seconds", "retry_after", "credentials_cooling") if k in body})
    except ValueError:
        out["message"] = tail[:160]
    return out


def summarize(events, home):
    usage = {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "reasoning": 0}
    tools, bash_commands, assistant, stop, tool_errors = {}, [], 0, None, {}
    retries, first_error, per_request = 0, None, []
    for event in events:
        kind = event.get("type")
        if kind == "message_end":
            message = event.get("message") or {}
            if message.get("role") == "assistant":
                assistant += 1
                stop = message.get("stopReason")
                if stop == "error" and first_error is None:
                    first_error = parse_error(str(message.get("errorMessage") or ""))
                for key in usage:
                    usage[key] += int((message.get("usage") or {}).get(key) or 0)
                per_request.append({key: int((message.get("usage") or {}).get(key) or 0) for key in usage} | {"stop": message.get("stopReason")})
        elif kind == "auto_retry_start":
            retries += 1
        elif kind == "tool_execution_end":
            if event.get("isError"):
                name = event.get("toolName") or "?"
                tool_errors[name] = tool_errors.get(name, 0) + 1
        elif kind == "tool_execution_start":
            name = event.get("toolName") or "?"
            tools[name] = tools.get(name, 0) + 1
            if name == "bash":
                bash_commands.append(str((event.get("args") or {}).get("command", "")))
    lanes = {
        "builtin": sum(n for t, n in tools.items() if t in BUILTIN),
        "context_mode": sum(n for t, n in tools.items() if t.startswith(("ctx_", "mcp__context-mode__"))),
        "tool_search": tools.get("tool_search", 0),
        "mcp": sum(n for t, n in tools.items() if t.startswith("mcp__") and not t.startswith("mcp__context-mode__")),
        "bash_calls": len(bash_commands),
        "bash_rtk_eligible": sum(1 for c in bash_commands if c.strip() and rtk_eligible(home, c)),
    }
    return {"assistant_messages": assistant, "last_stop_reason": stop, "auto_retries": retries, "first_error": first_error, "per_request": per_request,
            "usage": usage, "tools": tools, "tool_errors": tool_errors, "lanes": lanes}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--arm", choices=["stack", "stack-ext", "plain"], required=True)
    parser.add_argument("--task", choices=fixtures.TASKS, required=True)
    parser.add_argument("--attempt", type=int, required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--tag", default="")
    parser.add_argument("--base-url", default="")
    a = parser.parse_args()
    stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    run_id = f"pi-trial-{a.arm}-{a.task}-a{a.attempt}-{stamp}" + (f"-{a.tag}" if a.tag else "")
    run_dir = a.state / "runs" / run_id
    ws = run_dir / "ws"
    run_dir.mkdir(parents=True)
    head = fixtures.make(a.task, ws)
    home = a.state / "arms" / a.arm / "home"
    agent = home / ".pi" / "agent"
    env = {**os.environ, "PI_TRIAL_RUN_ID": run_id, "PYTHONDONTWRITEBYTECODE": "1"}
    if a.base_url:
        agent = run_dir / "agent"
        shutil.copytree(home / ".pi" / "agent", agent, symlinks=True)
        models = json.loads((agent / "models.json").read_text())
        models["providers"]["omni-fw"]["baseUrl"] = a.base_url
        (agent / "models.json").write_text(json.dumps(models, indent=2))
        settings = json.loads((agent / "settings.json").read_text())
        settings["packages"] = [str((home / ".pi" / "agent" / p).resolve()) for p in settings.get("packages", [])]
        (agent / "settings.json").write_text(json.dumps(settings, indent=2))
        env["PI_CODING_AGENT_DIR"] = str(agent)
    cmd = [str(a.state / "bin" / f"pi-{a.arm}"), "--print", "--mode", "json", "--session-dir", str(run_dir / "sessions"),
           "--thinking", THINKING] + (["-xt", EXCLUDE] if a.arm != "plain" else []) + [fixtures.INSTRUCTIONS[a.task]]
    state_before = gateway_state(agent / "models.json")
    before = rtk_commands(home) if a.arm != "plain" else None
    started = time.time()
    proc = subprocess.Popen(cmd, cwd=ws, env=env, stdin=subprocess.DEVNULL, stdout=open(run_dir / "events.jsonl", "w"),
                            stderr=open(run_dir / "stderr.txt", "w"), start_new_session=True)
    timed_out = False
    try:
        code = proc.wait(timeout=a.timeout)
    except subprocess.TimeoutExpired:
        timed_out, code = True, None
        kill_tree(proc)
        proc.wait()
    wall = round(time.time() - started, 1)
    events = []
    for line in (run_dir / "events.jsonl").read_text().splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    after = rtk_commands(home) if a.arm != "plain" else None
    result = {
        "run_id": run_id, "arm": a.arm, "task": a.task, "attempt": a.attempt, "fixture_commit": head,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)), "wall_seconds": wall,
        "exit_code": code, "timed_out": timed_out, "gateway_base": a.base_url or "models.json",
        "gateway_state_before": state_before, "headerless_uncompressed": headerless_uncompressed(state_before),
        "arm_headers": {k.lower(): v for k, v in json.loads((agent / "models.json").read_text())["providers"]["omni-fw"]["headers"].items()
                        if k.lower().startswith("x-omniroute-") and k.lower() not in ("x-omniroute-session-id",)},
        "check": fixtures.check(a.task, ws), "pi_reported": summarize(events, home),
        "rtk_tracker_delta": (after - before) if before is not None and after is not None else None,
    }
    (run_dir / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({k: result[k] for k in ("run_id", "exit_code", "timed_out", "wall_seconds")} | {"passed": result["check"]["passed"]}))
    sys.exit(0 if result["check"]["passed"] else 1)


if __name__ == "__main__":
    main()
