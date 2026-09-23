#!/usr/bin/env python3
"""Unmodified-configuration arm for gaps 0, 3, 4 and 8 (foundation/mcp-surfaces, wave 2).

Outer:  ns_exact.py OUT_JSON
        re-executes itself inside `unshare -rnm --fork --kill-child` (user + network + mount namespace).
Inner:  $HOME and /mnt/c are re-mounted read-only; only the run's temp root is writable; loopback is
        brought up empty. Owned ai-memory and Qdrant then listen on the CONFIGURED ports (49374, 16333) so the
        unmodified $HOME/codex-ecosystem/config/mcporter.json and agent-lab/.mcp.json can be used verbatim.
        The live services on those ports are in the host network namespace and are unreachable from here;
        a connect probe before the owned services start records that (it would detect a live listener).
        Fix round 1: an empty tmpfs over $HOME/.mcporter hides the shared daemon socket; an AF_UNIX probe of
        that path (ENOENT) plus the same probe against the owned daemon socket (connected) record it.
"""
import json
import os
import pathlib
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import iso  # noqa: E402

HOME = iso.REAL_HOME
HOST_CFG = f"{HOME}/codex-ecosystem/config/mcporter.json"
PROJECT = f"{HOME}/code/agent-lab"
MCPJSON = f"{PROJECT}/.mcp.json"
MCPORTER = iso.BINS["mcporter-installed-0.13.13"]
INSPECTOR_LAUNCHER = str(iso.ECO / "tools/mcp-inspector-2.7.0/node_modules/@modelcontextprotocol/inspector/clients/launcher/build/index.js")


def outer():
    out = pathlib.Path(sys.argv[1]).resolve()
    stamp = time.strftime("%H%M%S", time.gmtime())
    t = iso.CACHE / "d" / f"ns{stamp}"  # short: holds the daemon socket
    t.mkdir(parents=True, exist_ok=True)
    inner_out = t / "ns-result.json"  # the worktree is read-only inside the namespace
    cmd = ["unshare", "-rnm", "--fork", "--kill-child", sys.executable, __file__, "--inner", str(t), str(inner_out)]
    p = subprocess.run(cmd, timeout=1150)
    print("inner exit", p.returncode)
    out.write_text(inner_out.read_text())
    return p.returncode


def sh(*a):
    subprocess.run(list(a), check=True)


def probe(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return "connected"
    except OSError as e:
        return f"{type(e).__name__}: {e.strerror}"


def inner(t, out):
    t = pathlib.Path(t)
    sh("mount", "--rbind", HOME, HOME)
    sh("mount", "-o", "remount,bind,ro", HOME)
    # fix round 1: hide the shared per-user daemon directory (pathname sockets ignore network namespaces)
    sh("mount", "-t", "tmpfs", "-o", "size=1m,mode=0700", "tmpfs", f"{HOME}/.mcporter")
    sh("mount", "--rbind", "/mnt/c", "/mnt/c")  # Windows drive (context-mode plugin cache lives there)
    sh("mount", "-o", "remount,bind,ro", "/mnt/c")
    sh("mount", "--bind", str(t), str(t))
    sh("mount", "-o", "remount,bind,rw", str(t))
    sh("ip", "link", "set", "lo", "up")
    rec = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "temp_root": iso.sanitize(str(t)), "runs": []}
    # write probes: the project and the real config must be read-only here
    rec["enforcement_probe"] = iso.enforcement_probe()
    for p in (f"{PROJECT}/.ns-write-probe", f"{HOME}/.local/share/codex-ecosystem/ns-write-probe"):
        try:
            open(p, "w").close()
            rec.setdefault("write_probe", {})[iso.sanitize(p)] = "WRITABLE (isolation failure)"
            os.unlink(p)
        except OSError as e:
            rec.setdefault("write_probe", {})[iso.sanitize(p)] = f"{type(e).__name__}: {e.strerror}"
    rec["pre_start_probe"] = {"49374": probe(49374), "16333": probe(16333), "8231": probe(8231)}

    home = t / "home"
    for d in [".config", ".local/share", ".local/state", ".cache", ".codex"]:
        (home / d).mkdir(parents=True, exist_ok=True)
    env = {"HOME": str(home), "USER": os.environ.get("USER", "user"), "LANG": "C.UTF-8", "TERM": "dumb",
           "PATH": f"{iso.ECO}/bin:/usr/local/bin:/usr/bin:/bin", "MCPORTER_DAEMON_DIR": str(t / "dm"),
           "XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(home / ".local/share"),
           "XDG_STATE_HOME": str(home / ".local/state"), "XDG_CACHE_HOME": str(home / ".cache"),
           "MCP_AUTO_OPEN_ENABLED": "false", "NO_UPDATE_NOTIFIER": "1", "AI_MEMORY_SERVER_URL": "http://127.0.0.1:49374"}
    procs = []
    data = t / "ai-memory"
    data.mkdir(exist_ok=True)
    procs.append(subprocess.Popen([iso.AI_MEMORY, "serve", "--transport", "http", "--bind", "127.0.0.1:49374", "--data-dir", str(data),
                                   "--no-watcher", "--workspace", "agent-lab", "--project", "agent-lab"],
                                  env=env, stdout=open(t / "ai-memory.log", "wb"), stderr=subprocess.STDOUT))
    qd = t / "qdrant"
    qd.mkdir(exist_ok=True)
    procs.append(subprocess.Popen([iso.QDRANT], cwd=qd, env=dict(env, QDRANT__SERVICE__HOST="127.0.0.1", QDRANT__SERVICE__HTTP_PORT="16333",
                                  QDRANT__SERVICE__GRPC_PORT="16334", QDRANT__STORAGE__STORAGE_PATH=str(qd / "storage"),
                                  QDRANT__STORAGE__SNAPSHOTS_PATH=str(qd / "snapshots"), QDRANT__TELEMETRY_DISABLED="true"),
                                  stdout=open(t / "qdrant.log", "wb"), stderr=subprocess.STDOUT))
    for port in (49374, 16333):
        end = time.time() + 60
        while probe(port) != "connected" and time.time() < end:
            time.sleep(0.2)
    rec["post_start_probe"] = {"49374": probe(49374), "16333": probe(16333)}
    outside = t / "outside"
    outside.mkdir(exist_ok=True)

    def run(label, gap, argv, cwd, timeout=180):
        t0 = time.time()
        try:
            p = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=timeout)
            rc, so, se = p.returncode, p.stdout.decode(errors="replace"), p.stderr.decode(errors="replace")
        except subprocess.TimeoutExpired as e:
            rc, so, se = "timeout", (e.stdout or b"").decode(errors="replace"), (e.stderr or b"").decode(errors="replace")
        r = {"label": label, "gaps": gap, "argv": [iso.sanitize(str(a)) for a in argv], "cwd": iso.sanitize(str(cwd)), "exit": rc,
             "elapsed_ms": round((time.time() - t0) * 1000), "stdout": iso.sanitize(so)[:6000], "stderr": iso.sanitize(se)[:3000]}
        rec["runs"].append(r)
        print(label, rc, r["elapsed_ms"], flush=True)
        return r

    M = MCPORTER
    try:
        # ---- gap 0/3: unmodified host mcporter config -------------------------------------------
        for s in ("context-mode", "ai-memory", "socraticode"):
            run(f"host-cfg-list-{s}", [0], [M, "--config", HOST_CFG, "list", s, "--brief", "--no-oauth"], PROJECT)
        run("host-cfg-ctx-execute-file", [0], [M, "--config", HOST_CFG, "call", "context-mode.ctx_execute_file", "--args",
            json.dumps({"path": "README.md", "language": "python",
                        "code": "import hashlib; print('BYTES=%d SHA=%s' % (len(FILE_CONTENT.encode()), hashlib.sha256(FILE_CONTENT.encode()).hexdigest()))"}),
            "--output", "json", "--no-oauth"], PROJECT)
        run("host-cfg-fresh-memory-status", [0, 3], [M, "--config", HOST_CFG, "call", "ai-memory.memory_status", "--args",
            json.dumps({"workspace": "agent-lab", "project": "agent-lab"}), "--output", "json", "--no-oauth"], PROJECT)
        run("host-cfg-fresh-socraticode-status", [0, 3], [M, "--config", HOST_CFG, "call", "socraticode.codebase_status", "--args",
            json.dumps({"projectPath": PROJECT}), "--output", "json", "--no-oauth"], PROJECT)
        run("adhoc-jcodemunch-session-stats", [0], [M, "call", "--stdio", "jcodemunch-mcp", "--env", f"CODE_INDEX_PATH={t / 'code-index'}",
            "--env", "JCODEMUNCH_SHARE_SAVINGS=0", "--tool", "order", "--args", json.dumps({"action": "get_session_stats", "args": {}}),
            "--output", "json", "--no-oauth"], PROJECT)
        run("host-daemon-status", [0], [M, "daemon", "status", "--json"], PROJECT)
        rec["owned_socket_control"] = iso.socket_probe(t / "dm/daemon/user.sock")
        run("host-daemon-stop", [0], [M, "daemon", "stop"], PROJECT)
        run("inspector-context-mode-42", [0], ["node", INSPECTOR_LAUNCHER, "--cli", "node", iso.CONTEXT_MODE_NPM,
            "--method", "tools/call", "--tool-name", "ctx_execute", "--tool-arg", "language=javascript", "--tool-arg", "code=console.log(6*7)"], PROJECT)
        # ---- gap 4/8: Inspector with agent-lab's unmodified .mcp.json ----------------------------
        for s in ("serena", "ai-memory", "socraticode"):
            run(f"inspector-inside-list-{s}", [4, 8], ["node", INSPECTOR_LAUNCHER, "--cli", "--config", ".mcp.json", "--server", s,
                "--method", "tools/list"], PROJECT, timeout=120)
        run("inspector-inside-call-memory-status", [8], ["node", INSPECTOR_LAUNCHER, "--cli", "--config", ".mcp.json", "--server", "ai-memory",
            "--method", "tools/call", "--tool-name", "memory_status", "--tool-arg", "workspace=agent-lab", "--tool-arg", "project=agent-lab"], PROJECT)
        run("inspector-inside-call-codebase-status-cwd", [8], ["node", INSPECTOR_LAUNCHER, "--cli", "--config", ".mcp.json", "--server", "socraticode",
            "--method", "tools/call", "--tool-name", "codebase_status"], PROJECT)
        run("inspector-inside-no-config", [8], ["node", INSPECTOR_LAUNCHER, "--cli", "--server", "socraticode", "--method", "tools/list"], PROJECT)
        run("inspector-outside-relative-config", [8], ["node", INSPECTOR_LAUNCHER, "--cli", "--config", ".mcp.json", "--server", "socraticode",
            "--method", "tools/list"], outside)
        run("inspector-outside-absolute-list", [8], ["node", INSPECTOR_LAUNCHER, "--cli", "--config", MCPJSON, "--server", "socraticode",
            "--method", "tools/list"], outside)
        run("inspector-outside-absolute-call-codebase-status-cwd", [8], ["node", INSPECTOR_LAUNCHER, "--cli", "--config", MCPJSON,
            "--server", "socraticode", "--method", "tools/call", "--tool-name", "codebase_status"], outside)
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()
        rec["ai_memory_log_tail"] = iso.sanitize((t / "ai-memory.log").read_text(errors="replace")[-1500:])
        rec["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        pathlib.Path(out).write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--inner":
        inner(sys.argv[2], sys.argv[3])
    else:
        before = iso.shared_daemon_snapshot()
        rc = outer()
        after = iso.shared_daemon_snapshot()
        o = pathlib.Path(sys.argv[1])
        d = json.loads(o.read_text())
        d["shared_daemon_before"], d["shared_daemon_after"] = before, after
        d["shared_daemon_unchanged"] = before == after
        o.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")
        print("shared daemon unchanged:", before == after)
        sys.exit(rc)
