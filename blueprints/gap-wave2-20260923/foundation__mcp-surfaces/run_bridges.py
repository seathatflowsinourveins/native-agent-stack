#!/usr/bin/env python3
"""Matched bridge run for gaps 0, 1, 3, 4, 6, 8 and 12 (foundation/mcp-surfaces, wave 2).

One owned fixture (iso.Fixture) hosts isolated instances of the retained servers. The same operation set
is then executed through each bridge:
  mcporter-installed-0.13.13  the host PATH binary (gap 0 recertification)
  mcporter-0.13.13 / 0.14.0   fresh npm prefixes under $HOME/.cache/gap-wave2-20260923 (gaps 1, 12)
  inspector                   the host's pinned MCP Inspector 2.7.0 CLI (gaps 0, 4, 8, 6 incumbent)
  wong2-mcp-cli-2.0.0         registry alternative from punkpeye/awesome-mcp-servers (gaps 6, 12)
Each mcporter bridge gets its own MCPORTER_DAEMON_DIR and its daemon is stopped afterwards.

Usage: run_bridges.py OUT_JSON [--reps N]
"""
import json
import pathlib
import re
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import iso  # noqa: E402

OUT = pathlib.Path(sys.argv[1])
REPS = int(sys.argv[sys.argv.index("--reps") + 1]) if "--reps" in sys.argv else 3

f = iso.Fixture("bridges")
record = {
    "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "fixture_root": iso.sanitize(str(f.root)),
    "shared_daemon_before": iso.shared_daemon_snapshot(),
    "enforcement_probe_start": iso.enforcement_probe(),  # fix round 1: meaningful when run under enforce.py
    "owned_socket_controls": {},
    "setup": [],
    "runs": [],
}


def text_of(r):
    return r["stdout"] + "\n" + r["stderr"]


# ---- operation checks (applied to stdout of every bridge) -----------------
def chk_list(r):
    return r["exit"] == 0 and len(re.findall(r"function |\"name\"|^\s*- ", r["stdout"], re.M)) > 0


def chk_42(r):
    return r["exit"] == 0 and re.search(r"(?<!\d)42(?!\d)", r["stdout"]) is not None


def chk_bytes(expected):
    return lambda r: r["exit"] == 0 and str(expected) in r["stdout"]


def chk_stats(r):
    return r["exit"] == 0 and "session_calls" in r["stdout"].replace('\\"', '"')


def chk_collect(r):
    return r["exit"] == 0 and "collect" in r["stdout"] and "linux-usage-report" in r["stdout"]


def chk_callees(r):
    return r["exit"] == 0 and "callees" in r["stdout"] and "runParser" in r["stdout"]


def chk_mem_status(r):
    return r["exit"] == 0 and "pages_latest" in r["stdout"].replace('\\"', '"')


def chk_socra(r):
    return r["exit"] == 0 and ("Project:" in r["stdout"] or "not indexed" in r["stdout"].lower() or "No index" in r["stdout"])


def ppid_of(r):
    m = re.search(r"PPID=(\d+)", r["stdout"])
    return int(m.group(1)) if m else None


try:
    f.start_ai_memory()
    f.start_qdrant()
    proj = f.project_fixture()
    cfg = f.write_mcporter_config(proj)
    mcpjson = f.write_mcp_json(proj, f.root / "state/mcp.json", ["context-mode", "socraticode", "codebase-memory", "jcodemunch", "ai-memory"])
    notes_bytes = len((proj / "notes.md").read_bytes())
    record["servers"] = {k: iso.sanitize(json.dumps({kk: vv for kk, vv in v.items() if kk != "env"})) for k, v in f.server_defs(proj).items()}
    record["ports"] = f.ports

    # setup: index the owned fixture project in the isolated codebase-memory cache (not a matched op)
    M0 = iso.BINS["mcporter-0.13.13"]
    setup_env = {"MCPORTER_DAEMON_DIR": str(f.short / "setup")}
    r = f.run([M0, "--config", str(cfg), "call", "codebase-memory.index_repository", "--args",
               json.dumps({"repo_path": str(proj), "mode": "full"}), "--output", "json", "--no-oauth"],
              cwd=proj, timeout=300, env_extra=setup_env)
    record["setup"].append(dict(r, op="cbm-index"))
    r = f.run([M0, "--config", str(cfg), "call", "codebase-memory.list_projects", "--args", '{"format":"json"}',
               "--output", "json", "--no-oauth"], cwd=proj, env_extra=setup_env)
    record["setup"].append(dict(r, op="cbm-list-projects"))
    m = re.search(r'"(?:name|project)"\s*:\s*"([^"]+)"', r["stdout"].replace('\\"', '"'))
    cbm_project = m.group(1) if m else "project"
    record["cbm_project"] = cbm_project
    f.run([M0, "daemon", "stop"], env_extra=setup_env)

    ARGS = {
        "ctx_execute_file": {"path": "notes.md", "language": "python", "code": "print('BYTES=%d' % len(FILE_CONTENT.encode()))"},
        "ppid": {"language": "javascript", "code": "console.log('PPID=' + process.ppid)"},
        "arith": {"language": "javascript", "code": "console.log(6*7)"},
        "stats": {"action": "get_session_stats", "args": {}},
        "graph": {"project": cbm_project, "name_pattern": "^collect$", "file_pattern": "tools/ecosystem/linux-usage-report.cjs", "format": "json", "limit": 10},
        "callees": {"project": cbm_project, "function_name": f"{cbm_project}.tools.ecosystem.linux-usage-report.collect", "direction": "outbound", "depth": 1, "format": "json", "limit": 20},
        "memstatus": {"workspace": "agent-lab", "project": "agent-lab"},
        "socra": {"projectPath": str(proj)},
    }
    # op id -> (server, tool, args key, check, retained id)
    OPS = [
        ("list-context-mode", "context-mode", None, None, chk_list, "retained list"),
        ("list-ai-memory", "ai-memory", None, None, chk_list, "retained list"),
        ("list-socraticode", "socraticode", None, None, chk_list, "retained list"),
        ("list-codebase-memory", "codebase-memory", None, None, chk_list, "retained list"),
        ("list-jcodemunch", "jcodemunch", None, None, chk_list, "retained list"),
        ("ctx-execute-file", "context-mode", "ctx_execute_file", "ctx_execute_file", chk_bytes(f"BYTES={notes_bytes}"), "current-session-observation op 2"),
        ("ctx-arith-42", "context-mode", "ctx_execute", "arith", chk_42, "fresh-inspector-context-call"),
        ("ctx-ppid", "context-mode", "ctx_execute", "ppid", lambda r: ppid_of(r) is not None, "lifecycle probe"),
        ("jcodemunch-session-stats", "jcodemunch", "order", "stats", chk_stats, "current-session-observation op 13"),
        ("fresh-static-graph", "codebase-memory", "search_graph", "graph", chk_collect, "fresh-static-graph"),
        ("fresh-static-callees", "codebase-memory", "trace_path", "callees", chk_callees, "fresh-static-callees"),
        ("fresh-memory-status", "ai-memory", "memory_status", "memstatus", chk_mem_status, "fresh-memory-status"),
        ("fresh-socraticode-status", "socraticode", "codebase_status", "socra", chk_socra, "fresh-socraticode-status"),
    ]
    record["ops"] = [{"op": o[0], "server": o[1], "tool": o[2], "args": ARGS.get(o[3]) if o[3] else None, "retained_ref": o[5]} for o in OPS]
    record["args"] = json.loads(iso.sanitize(json.dumps(ARGS)))

    def argv_for(bridge, op):
        oid, server, tool, akey, _, _ = op
        args = ARGS.get(akey) if akey else None
        if bridge.startswith("mcporter"):
            M = iso.BINS[bridge]
            if oid == "jcodemunch-session-stats":  # retained form: ad-hoc --stdio
                d = f.server_defs(proj)["jcodemunch"]
                return [M, "call", "--stdio", iso.JCODEMUNCH, "--env", f"CODE_INDEX_PATH={d['env']['CODE_INDEX_PATH']}",
                        "--env", "JCODEMUNCH_SHARE_SAVINGS=0", "--tool", "order", "--args", json.dumps(args), "--output", "json", "--no-oauth"]
            if tool is None:
                return [M, "--config", str(cfg), "list", server, "--brief", "--no-oauth"]
            return [M, "--config", str(cfg), "call", f"{server}.{tool}", "--args", json.dumps(args), "--output", "json", "--no-oauth"]
        if bridge == "inspector":
            base = [iso.BINS["inspector"], "--cli", "--config", str(mcpjson), "--server", server]
            if tool is None:
                return base + ["--method", "tools/list"]
            out = base + ["--method", "tools/call", "--tool-name", tool]
            for k, v in args.items():
                out += ["--tool-arg", f"{k}={v if isinstance(v, str) else json.dumps(v)}"]
            return out
        if bridge == "wong2-mcp-cli-2.0.0":
            W = iso.BINS[bridge]
            if tool is None:
                return None  # no non-interactive list in 2.0.0 (src/cli.js usage); recorded as unsupported
            # 2.0.0 non-interactive mode builds a StdioClientTransport for every config entry
            # (src/mcp.js runNonInteractive); the HTTP ai-memory entry is run anyway and its failure recorded.
            return [W, "-c", str(mcpjson), "call-tool", f"{server}:{tool}", "--args", json.dumps(args)]
        raise ValueError(bridge)

    BRIDGES = ["mcporter-installed-0.13.13", "mcporter-0.13.13", "mcporter-0.14.0", "inspector", "wong2-mcp-cli-2.0.0"]
    for bridge in BRIDGES:
        env_extra = {"MCPORTER_DAEMON_DIR": str(f.short / bridge.replace("mcporter-", "m").replace("installed-", "i")[:10])}
        for op in OPS:
            argv = argv_for(bridge, op)
            if argv is None:
                record["runs"].append({"bridge": bridge, "op": op[0], "rep": 0, "exit": "unsupported", "check": False,
                                       "note": "no non-interactive tools/list mode in this bridge"})
                continue
            for rep in range(REPS):
                r = f.run(argv, cwd=proj, timeout=240, env_extra=env_extra)
                r.update(bridge=bridge, op=op[0], rep=rep, check=bool(op[4](r)))
                if op[0] == "ctx-ppid":
                    r["server_pid"] = ppid_of(r)
                record["runs"].append(r)
        if bridge.startswith("mcporter"):
            # owned control: the same AF_UNIX probe connects to this bridge's own daemon socket
            record["owned_socket_controls"][bridge] = iso.socket_probe(pathlib.Path(env_extra["MCPORTER_DAEMON_DIR"]) / "daemon/user.sock")
            st = f.run([iso.BINS[bridge], "daemon", "status", "--json"], env_extra=env_extra)
            record["setup"].append(dict(st, op=f"daemon-status-{bridge}"))
            stop = f.run([iso.BINS[bridge], "daemon", "stop"], env_extra=env_extra)
            record["setup"].append(dict(stop, op=f"daemon-stop-{bridge}"))
finally:
    record["leftover_after_stop"] = f.stop()
    record["shared_daemon_after"] = iso.shared_daemon_snapshot()
    record["enforcement_probe_end"] = iso.enforcement_probe()
    record["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

# ---- summary ---------------------------------------------------------------
summary = {}
for r in record["runs"]:
    s = summary.setdefault(r["op"], {}).setdefault(r["bridge"], {"exits": [], "checks": [], "elapsed_ms": [], "server_pids": [], "stdout_sha256": []})
    s["exits"].append(r["exit"])
    s["checks"].append(r["check"])
    if "elapsed_ms" in r:
        s["elapsed_ms"].append(r["elapsed_ms"])
        s["stdout_sha256"].append(r["stdout_sha256"])
    if r.get("server_pid"):
        s["server_pids"].append(r["server_pid"])
for op, bridges in summary.items():
    for b, s in bridges.items():
        s["all_pass"] = all(s["checks"])
        s["median_ms"] = statistics.median(s["elapsed_ms"]) if s["elapsed_ms"] else None
        s["distinct_server_pids"] = len(set(s["server_pids"])) if s["server_pids"] else None
        s["distinct_outputs"] = len(set(s["stdout_sha256"]))
record["summary"] = summary
OUT.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n")
for op, bridges in summary.items():
    print(op.ljust(26), " ".join(f"{b.replace('mcporter-', 'm')[:14]}:{'P' if s['all_pass'] else 'F'}/{s['median_ms']}" +
                                  (f"/pids={s['distinct_server_pids']}" if s['distinct_server_pids'] else "") for b, s in bridges.items()))
print("enforcement:", record["enforcement_probe_start"], "owned controls:", record["owned_socket_controls"])
print("shared daemon unchanged:", record["shared_daemon_before"] == record["shared_daemon_after"], "leftover:", record["leftover_after_stop"])
