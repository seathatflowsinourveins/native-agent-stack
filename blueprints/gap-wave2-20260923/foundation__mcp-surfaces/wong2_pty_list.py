#!/usr/bin/env python3
"""Gap 6: drive @wong2/mcp-cli 2.0.0's INTERACTIVE mode through a pseudo-terminal to observe its listing.

2.0.0 has no non-interactive list command (src/cli.js usage); listing happens inside an autocomplete prompt
after connect (src/mcp.js connectServer -> listPrimitives). This script answers the server prompt (Enter),
captures the rendered primitive list, then cancels (Ctrl-C). Servers: context-mode (stdio, via -c config)
and the owned ai-memory (HTTP, via --url); fix round 1 runs all 5 retained servers x3. Owned fixture state only.

Usage: wong2_pty_list.py OUT_JSON
"""
import json
import os
import pathlib
import pty
import re
import select
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import iso  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[78]")


def drive(argv, env, cwd, answer_server, wait=25, presses=45):
    """Fix round 2: after the connect line, press Down `presses` times so the autocomplete scrolls through
    every choice; all rendered tool(name) entries across the scroll are collected. ready_ms = spawn until
    the 'Connected, server capabilities' line (listing readiness), separate from the harness duration."""
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(cwd)
        os.execve(argv[0], argv, env)
    buf = b""
    t0 = time.time()
    sent_enter = not answer_server
    ready_ms = None

    def pump(timeout):
        nonlocal buf
        r, _, _ = select.select([fd], [], [], timeout)
        if r:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                return False
            if not chunk:
                return False
            buf += chunk
        return True

    alive = True
    while time.time() - t0 < wait and alive:
        alive = pump(0.2)
        text = buf.decode(errors="replace")
        if not sent_enter and "Pick a server" in text:
            os.write(fd, b"\r")
            sent_enter = True
        if "Connected, server capabilities" in text:
            ready_ms = round((time.time() - t0) * 1000)
            break
    if ready_ms is not None:
        for _ in range(presses):
            os.write(fd, b"\x1b[B")  # Down arrow
            end = time.time() + 0.12
            while time.time() < end and pump(0.03):
                pass
    else:  # not connected: drain whatever the client printed (e.g. a crash trace)
        end = time.time() + 1.0
        while time.time() < end and pump(0.1):
            pass
    try:
        os.write(fd, b"\x03")
    except OSError:
        pass
    time.sleep(0.5)
    try:
        os.kill(pid, 9)
    except ProcessLookupError:
        pass
    os.waitpid(pid, 0)
    clean = ANSI.sub("", buf.decode(errors="replace"))
    return {"harness_ms": round((time.time() - t0) * 1000), "ready_ms": ready_ms, "connected": ready_ms is not None,
            "down_presses": presses if ready_ms is not None else 0,
            "tools_rendered": sorted(set(re.findall(r"tool\(([A-Za-z0-9_\-]+)\)", clean))),
            "screen_excerpt": iso.sanitize(clean[-3000:])}


REPS = 3
f = iso.Fixture("wong2pty")
out = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "enforcement_probe": iso.enforcement_probe(), "runs": {}}
try:
    f.start_ai_memory()
    f.start_qdrant()
    proj = f.project_fixture()
    env = dict(f.env, TERM="xterm", COLUMNS="200", LINES="60")
    W = iso.BINS["wong2-mcp-cli-2.0.0"]
    for server in ("context-mode", "socraticode", "codebase-memory", "jcodemunch", "ai-memory"):
        for rep in range(REPS):
            if server == "ai-memory":
                url = f"http://127.0.0.1:{f.ports['ai-memory']}/mcp"
                r = drive([iso.NODE, W, "--url", url], env, proj, False)
                r["argv"] = [iso.sanitize(W), "--url", "http://127.0.0.1:<owned port>/mcp"]
            else:
                cfg = f.write_mcp_json(proj, f.root / f"state/mcp-{server}.json", [server])
                r = drive([iso.NODE, W, "-c", str(cfg)], env, proj, True, wait=40)
                r["argv"] = [iso.sanitize(a) for a in [W, "-c", str(cfg)]]
            out["runs"][f"{server}#{rep}"] = r
finally:
    out["leftover"] = f.stop()
    out["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
pathlib.Path(sys.argv[1]).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
for k, v in out["runs"].items():
    print(k, v["connected"], len(v["tools_rendered"]), v["ready_ms"], v["harness_ms"])
