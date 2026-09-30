#!/usr/bin/env python3
"""Offline probes of a staged pi arm against the scripted stub: no gateway, no quota, no model.

Local integration checks (not upstream acceptance, not model behaviour). They observe what the arm's pi sends,
whether the RTK extension rewrites a bash call inside pi's real tool loop, and what survives SIGKILL.

    probes.py --state DIR [--arm stack|plain|all] [--only capture,loop,kill]

Each probe prints PASS/FAIL lines and the run exits 1 on any FAIL.
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUB = HERE / "pi_stub.py"
MODEL = "sharedgw/gpt-6.1-sol"
THINKING = "xhigh"  # what runs: the gateway has no 6.1 registry entry, so cx/ clamps max to xhigh
EXCLUDE = "ctx_upgrade,ctx_purge,ctx_doctor,ctx_insight"
PORT = 47850
RESULTS = []
MUTATION = {"agent_edit": None, "no_exclude": False, "quiet": False}


# Reproduced upstream defects the trial documents rather than fixes: (arm, probe key) -> evidence. A check listed here
# prints KNOWN-FAIL and does not fail the run; if it starts passing the line says so, which means the defect was fixed.
TOOL_SEARCH_NOTE = ("pi docs/cli.md ('tool_search'): matches are declared from the next call on, so the tools array grows and the cached "
                    "prefix breaks once per load (the transcript-anchored alternative needs compat.supportsToolSearch, which the ChatGPT-backed route does not offer)")
KNOWN = {("stack", "toolsearch-tools"): TOOL_SEARCH_NOTE, ("stack-ext", "toolsearch-tools"): TOOL_SEARCH_NOTE,
         ("stack-ext", "append-only"): "context-mode 1.0.169 pi extension, src/adapters/pi/extension.ts:740-753: the context hook pushes a "
                                        "user message at the end of the FIRST request of each prompt and later requests drop it"}


def report(ok, text, known=None):
    if known is not None:
        RESULTS.append((True, text))
        if not MUTATION["quiet"]:
            print(("PASS (known defect no longer reproduces) " if ok else "KNOWN-FAIL ") + text + ("" if ok else f" [{known}]"), flush=True)
        return
    RESULTS.append((ok, text))
    if not MUTATION["quiet"]:
        print(("PASS " if ok else "FAIL ") + text, flush=True)


class Stub:
    def __init__(self, work, name, steps):
        self.log = work / f"{name}.requests.jsonl"
        script = work / f"{name}.script.json"
        script.write_text(json.dumps(steps))
        self.proc = subprocess.Popen([sys.executable, str(STUB), str(PORT), str(self.log), str(script)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.8)

    def stop(self):
        self.proc.terminate()
        self.proc.wait(timeout=10)

    def requests(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []


def prepare(state, arm):
    """Copy the arm's agent dir and point its provider at the stub; nothing else changes."""
    src = state / "arms" / arm / "home" / ".pi" / "agent"
    dst = state / "arms" / arm / "agent-probe"
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst, symlinks=True)
    models = json.loads((dst / "models.json").read_text())
    models["providers"]["omni-fw"]["baseUrl"] = f"http://127.0.0.1:{PORT}/v1"
    (dst / "models.json").write_text(json.dumps(models, indent=2))
    settings = json.loads((dst / "settings.json").read_text())
    if settings.get("packages"):
        settings["packages"] = [str((src / p).resolve()) for p in settings["packages"]]
    (dst / "settings.json").write_text(json.dumps(settings, indent=2))
    if MUTATION["agent_edit"]:
        MUTATION["agent_edit"](dst)
    return dst


def ctx_prefix(arm):
    return "mcp__context-mode__" if arm == "stack" else ""


def pi_args(arm, extra):
    exclude = arm != "plain" and not MUTATION["no_exclude"]
    return ["--thinking", THINKING] + (["-xt", EXCLUDE] if exclude else []) + extra


def start_pi(state, arm, agent, run_id, cwd, args, out, err):
    env = {**os.environ, "PI_TRIAL_RUN_ID": run_id, "PI_CODING_AGENT_DIR": str(agent)}
    return subprocess.Popen([str(state / "bin" / f"pi-{arm}")] + args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                            stdout=open(out, "w"), stderr=open(err, "w"), start_new_session=True)


def repo(work):
    ws = work / "ws"
    if not ws.exists():
        ws.mkdir()
        for cmd in (["git", "init", "-q", "-b", "main"], ["git", "config", "user.email", "p@example.invalid"],
                    ["git", "config", "user.name", "probe"]):
            subprocess.run(cmd, cwd=ws, check=True)
        (ws / "a.txt").write_text("a\n")
        subprocess.run(["git", "add", "-A"], cwd=ws, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=ws, check=True)
    return ws


def probe_capture(state, arm, work):
    agent = prepare(state, arm)
    stub = Stub(work, f"capture-{arm}", [{"text": "STUB-OK"}])
    proc = start_pi(state, arm, agent, "probe-capture", repo(work), ["--print", "--no-session"] + pi_args(arm, ["Reply OK."]),
                    work / "capture.out", work / "capture.err")
    code = proc.wait(timeout=150)
    stub.stop()
    seen = stub.requests()
    report(code == 0 and "STUB-OK" in (work / "capture.out").read_text(), f"[{arm}] capture: pi exits 0 with the stub's answer")
    report(len(seen) == 1, f"[{arm}] capture: exactly one request (got {len(seen)})")
    if not seen:
        return
    r, h = seen[0], seen[0]["headers"]
    report(r["path"] == "/v1/responses" and r["model"] == MODEL, f"[{arm}] capture: /v1/responses, model {r['model']}")
    report((r["reasoning"] or {}).get("effort") == THINKING, f"[{arm}] capture: reasoning effort {r['reasoning']}")
    report(h.get("x-omniroute-no-cache") == "true", f"[{arm}] capture: x-omniroute-no-cache true (no replay of identical first turns)")
    report(h.get("x-omniroute-session-id") == "probe-capture" and h.get("x-correlation-id") == "probe-capture",
           f"[{arm}] capture: session and correlation ids interpolated from PI_TRIAL_RUN_ID")
    report(bool(r["prompt_cache_key"]), f"[{arm}] capture: prompt_cache_key present")
    names = r["tool_names"]
    if arm != "plain":
        configured = json.loads((state / "arms" / arm / "home" / ".pi" / "agent" / "models.json").read_text())["providers"]["omni-fw"]["headers"].get("x-omniroute-compression")
        report(h.get("x-omniroute-compression") == configured, f"[{arm}] capture: compression header matches the arm's configuration ({configured!r})")
        report("tool_search" in names and ctx_prefix(arm) + "ctx_execute" in names, f"[{arm}] capture: tool_search and {ctx_prefix(arm)}ctx_execute declared")
        report(not [n for n in names if n in [ctx_prefix(arm) + x for x in EXCLUDE.split(",")]], f"[{arm}] capture: excluded ctx tools absent")
        report(not [n for n in names if n.startswith(("mcp__serena__", "mcp__jcodemunch__", "mcp__qmd__", "mcp__headroom__"))],
               f"[{arm}] capture: deferred MCP tools not declared ({len(names)} tools, {r['tools_json_chars']} chars of tool JSON)")
    else:
        report(h.get("x-omniroute-compression") == "off", f"[{arm}] capture: compression header off")
        report(sorted(names) == ["bash", "edit", "read", "write"], f"[{arm}] capture: built-in tools only {names}")


def probe_prefix(state, arm, work):
    """Prompt-cache friendliness: across the requests of one run the prefix must only grow (GPT-5.6+ caches up to the end of the latest message)."""
    agent = prepare(state, arm)
    steps = [{"tool_call": {"name": "bash", "arguments": {"command": "echo A"}}},
             {"tool_call": {"name": "bash", "arguments": {"command": "echo B"}}}, {"text": "DONE"}]
    stub = Stub(work, f"prefix-{arm}", steps)
    proc = start_pi(state, arm, agent, "probe-prefix", repo(work),
                    ["--print", "--mode", "json", "--session-dir", str(work / "prefix-sessions")] + pi_args(arm, ["Run echo A, then echo B."]),
                    work / "prefix.out", work / "prefix.err")
    code = proc.wait(timeout=150)
    stub.stop()
    seen = stub.requests()
    report(code == 0 and len(seen) == 3, f"[{arm}] prefix: three requests in the scripted loop (got {len(seen)})")
    pairs = list(zip(seen, seen[1:]))
    report(bool(pairs) and all(a["tools_sha"] == b["tools_sha"] for a, b in pairs), f"[{arm}] prefix: declared tools identical across the loop")
    report(bool(pairs) and all(a["instructions_sha"] == b["instructions_sha"] for a, b in pairs), f"[{arm}] prefix: instructions identical across the loop")
    report(bool(pairs) and all(b["input_shas"][:len(a["input_shas"])] == a["input_shas"] and len(b["input_shas"]) > len(a["input_shas"]) for a, b in pairs),
           f"[{arm}] prefix: each request's input extends the previous one (append-only; item kinds per request {[s['input_kinds'] for s in seen]})",
           known=KNOWN.get((arm, "append-only")))
    report(bool(seen) and len({s["prompt_cache_key"] for s in seen}) == 1 and len({s["headers"].get("session_id") for s in seen}) == 1,
           f"[{arm}] prefix: prompt_cache_key and session_id stable across the loop")


def probe_toolsearch(state, arm, work):
    """What deferred-tool loading does to the request: pi's real tool_search over the real MCP servers, scripted model."""
    if arm == "plain":
        return
    agent = prepare(state, arm)
    steps = [{"tool_call": {"name": "tool_search", "arguments": {"query": "qmd document index status", "limit": 3}}}, {"text": "DONE"}]
    stub = Stub(work, f"toolsearch-{arm}", steps)
    proc = start_pi(state, arm, agent, "probe-toolsearch", repo(work),
                    ["--print", "--mode", "json", "--session-dir", str(work / "toolsearch-sessions")] + pi_args(arm, ["Find the qmd status tool."]),
                    work / "toolsearch.out", work / "toolsearch.err")
    code = proc.wait(timeout=150)
    stub.stop()
    seen = stub.requests()
    report(code == 0 and len(seen) == 2 and seen[1]["function_call_outputs"] == 1, f"[{arm}] toolsearch: tool_search ran and its result was returned")
    if len(seen) == 2:
        a, b = seen
        report(a["tools_sha"] == b["tools_sha"], f"[{arm}] toolsearch: declared tools unchanged after tool_search ({a['tool_count']} -> {b['tool_count']} tools)",
               known=KNOWN.get((arm, "toolsearch-tools")))
        report(b["input_shas"][:len(a["input_shas"])] == a["input_shas"], f"[{arm}] toolsearch: input still append-only after tool_search",
               known=KNOWN.get((arm, "append-only")))


def probe_loop(state, arm, work):
    agent = prepare(state, arm)
    home = state / "arms" / arm / "home"
    before = rtk_commands(home)
    stub = Stub(work, f"loop-{arm}", [{"tool_call": {"name": "bash", "arguments": {"command": "git status"}}}, {"text": "DONE"}])
    proc = start_pi(state, arm, agent, "probe-loop", repo(work),
                    ["--print", "--mode", "json", "--session-dir", str(work / "loop-sessions")] + pi_args(arm, ["Run git status."]),
                    work / "loop.out", work / "loop.err")
    code = proc.wait(timeout=150)
    stub.stop()
    seen = stub.requests()
    report(code == 0 and len(seen) == 2 and seen[1]["function_call_outputs"] == 1,
           f"[{arm}] loop: two requests, tool result returned to the model")
    delta = rtk_commands(home) - before
    if arm != "plain":
        report(delta == 1, f"[{arm}] loop: rtk's own tracker recorded the bash call as rtk git status (delta {delta})")
    else:
        report(delta == 0, f"[{arm}] loop: no rtk activity (delta {delta})")


def rtk_commands(home):
    out = subprocess.run(["rtk", "gain", "--format", "json"], capture_output=True, text=True,
                         env={**os.environ, "HOME": str(home)}, cwd=home).stdout
    try:
        data = json.loads(out)
        return int(data.get("summary", data).get("total_commands", 0))
    except Exception:
        return 0


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


def alive(pids):
    live = []
    for pid in pids:
        try:
            state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        except (FileNotFoundError, ProcessLookupError, IndexError):
            continue
        if state != "Z":
            live.append(pid)
    return live


def probe_kill(state, arm, work, case):
    agent = prepare(state, arm)
    steps = ([{"text": "NEVER-SEEN", "delay_s": 40}] if case == "K1" else
             [{"tool_call": {"name": "bash", "arguments": {"command": "echo first-tool-ran"}}}, {"text": "NEVER-SEEN", "delay_s": 40}])
    want = 1 if case == "K1" else 2
    sessions = work / f"{case}-sessions"
    stub = Stub(work, f"{case}-{arm}-1", steps)
    proc = start_pi(state, arm, agent, f"probe-{case}", repo(work),
                    ["--print", "--mode", "json", "--session-dir", str(sessions)] + pi_args(arm, ["Run echo first-tool-ran, then say done."]),
                    work / f"{case}.out", work / f"{case}.err")
    for _ in range(160):
        if len(stub.requests()) >= want:
            break
        time.sleep(0.5)
    time.sleep(1)
    kids = descendants(proc.pid)
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait()
    stub.stop()
    time.sleep(3)
    survivors = alive(kids)
    for pid in survivors:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    files = list(sessions.rglob("*.jsonl"))
    rows = [json.loads(line) for line in files[0].read_text().splitlines() if line.strip()] if files else []
    roles = [(r.get("message") or {}).get("role") for r in rows if r.get("type") == "message"]
    report(bool(files) and "user" in roles, f"[{arm}] {case}: session file kept the first user message after SIGKILL ({roles})")
    if case == "K2":
        report("toolResult" in roles, f"[{arm}] {case}: the tool result before the kill was saved")
    report((len(kids) >= 4) if arm != "plain" else (len(kids) == 0),
           f"[{arm}] {case}: pi had {len(kids)} descendant processes at the kill (stack: MCP servers and the context-mode bridge)")
    report(not survivors, f"[{arm}] {case}: none of those {len(kids)} descendants survived 3 s after SIGKILL ({len(survivors)} did)")
    stub2 = Stub(work, f"{case}-{arm}-2", [{"text": "RESUMED-OK"}])
    proc2 = start_pi(state, arm, agent, f"probe-{case}-resume", repo(work),
                     ["--print", "--mode", "json", "--session-dir", str(sessions), "--continue"] + pi_args(arm, ["Continue."]),
                     work / f"{case}.resume.out", work / f"{case}.resume.err")
    code = proc2.wait(timeout=150)
    stub2.stop()
    seen = stub2.requests()
    ok = code == 0 and bool(seen) and any("first-tool-ran" in t for t in seen[0]["user_texts"])
    report(ok, f"[{arm}] {case}: --continue resumes with the original prompt in context")
    if case == "K2":
        report(bool(seen) and seen[0]["function_call_outputs"] == 1, f"[{arm}] {case}: resumed request carries the saved tool result")


def probe_runner(state, arm, work):
    """run_task.py end to end against the stub: a scripted solver must pass the task check, a no-op must fail it."""
    solver = [{"tool_call": {"name": "bash", "arguments": {"command": "sed -i 's/a - b/a + b/' calc.py"}}},
              {"tool_call": {"name": "bash", "arguments": {"command": "python3 -m unittest -q"}}},
              {"text": "fixed"}]
    for label, steps, want in (("known-pass", solver, True), ("known-fail", [{"text": "no change"}], False)):
        stub = Stub(work, f"runner-{arm}-{label}", steps)
        proc = subprocess.run([sys.executable, str(HERE / "run_task.py"), "--state", str(state), "--arm", arm, "--task",
                               "calc-sign-bug", "--attempt", "1", "--tag", f"ctl-{label}", "--base-url",
                               f"http://127.0.0.1:{PORT}/v1", "--timeout", "150"], capture_output=True, text=True)
        stub.stop()
        try:
            info = json.loads(proc.stdout.strip().splitlines()[-1])
            run_dir = state / "runs" / info["run_id"]
            result = json.loads((run_dir / "result.json").read_text())
        except Exception:
            report(False, f"[{arm}] runner {label}: no result ({proc.stderr[-200:]})")
            continue
        report(result["check"]["passed"] is want and (proc.returncode == 0) is want,
               f"[{arm}] runner {label} control: task check {'passes' if want else 'fails'} and the exit code agrees")
        if want:
            seen = result["pi_reported"]
            report(seen["lanes"]["bash_calls"] == 2 and seen["assistant_messages"] == 3 and seen["usage"]["input"] == 303,
                   f"[{arm}] runner {label}: 2 bash calls, 3 assistant messages, summed input 303 = 100+101+102 "
                   f"(got {seen['lanes']['bash_calls']}, {seen['assistant_messages']}, {seen['usage']['input']})")
        shutil.rmtree(run_dir, ignore_errors=True)


def _drop_header(agent):
    models = json.loads((agent / "models.json").read_text())
    models["providers"]["omni-fw"]["headers"].pop("x-omniroute-compression", None)
    (agent / "models.json").write_text(json.dumps(models))


def _direct_exposure(agent):
    mcp = json.loads((agent / "mcp.json").read_text())
    mcp["mcpServers"]["serena"]["exposure"] = "direct"
    (agent / "mcp.json").write_text(json.dumps(mcp))


MUTANTS = [
    ("plain arm's compression off removed", "compression header off", _drop_header, False, "plain"),
    ("exclusion flag not passed", "excluded ctx tools absent", None, True, "stack-ext"),
    ("serena exposed directly", "deferred MCP tools not declared", _direct_exposure, False, "stack"),
]


def selftest(state):
    """Each mutant breaks one rule; the capture probe must fail that rule and only that rule."""
    verdicts = []
    for name, rule, edit, no_exclude, arm in MUTANTS:
        MUTATION.update(agent_edit=edit, no_exclude=no_exclude, quiet=True)
        RESULTS.clear()
        with tempfile.TemporaryDirectory(prefix="pi-mutant-") as tmp:
            probe_capture(state, arm, Path(tmp))
        failed = [text for ok, text in RESULTS if not ok]
        MUTATION.update(agent_edit=None, no_exclude=False, quiet=False)
        RESULTS.clear()
        ok = len(failed) == 1 and rule in failed[0]
        verdicts.append((ok, f"selftest mutant '{name}' fails exactly the rule '{rule}' (failed: {len(failed)})"))
    for ok, text in verdicts:  # reported after the loop: each mutant clears RESULTS, which used to drop the earlier verdicts from the tally
        report(ok, text)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--arm", choices=["stack", "stack-ext", "plain", "all"], default="all")
    parser.add_argument("--only", default="capture,loop,prefix,toolsearch,runner,kill,selftest")
    a = parser.parse_args()
    arms = ["stack", "stack-ext", "plain"] if a.arm == "all" else [a.arm]
    chosen = a.only.split(",")
    if "selftest" in chosen:
        selftest(a.state)
    for arm in arms:
        with tempfile.TemporaryDirectory(prefix=f"pi-probe-{arm}-") as tmp:
            work = Path(tmp)
            if "capture" in chosen:
                probe_capture(a.state, arm, work)
            if "loop" in chosen:
                probe_loop(a.state, arm, work)
            if "prefix" in chosen:
                probe_prefix(a.state, arm, work)
            if "toolsearch" in chosen:
                probe_toolsearch(a.state, arm, work)
            if "runner" in chosen:
                probe_runner(a.state, arm, work)
            if "kill" in chosen:
                for case in ("K1", "K2"):
                    probe_kill(a.state, arm, work, case)
    bad = sum(1 for ok, _ in RESULTS if not ok)
    print("result:", "FAIL" if bad else "ok", f"({bad} failed checks of {len(RESULTS)})")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
