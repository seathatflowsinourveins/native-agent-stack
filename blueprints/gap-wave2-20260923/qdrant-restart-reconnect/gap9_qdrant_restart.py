import sys, json, time, os, subprocess, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from mcp_client import spawn
QDRANT="http://127.0.0.1:26333"
HOME_DIR=os.path.join(os.path.dirname(__file__), "mcp-home")
PROJ=os.path.join(os.path.dirname(__file__), "scratch-project")

def qcounts():
    req = urllib.request.Request(QDRANT + "/collections")
    with urllib.request.urlopen(req, timeout=5) as r:
        cols = json.loads(r.read())["result"]["collections"]
    out = {}
    for c in cols:
        name = c["name"]
        req2 = urllib.request.Request(QDRANT + f"/collections/{name}")
        with urllib.request.urlopen(req2, timeout=5) as r2:
            info = json.loads(r2.read())["result"]
        out[name] = info.get("points_count")
    return out

log = {}
p = spawn(QDRANT, HOME_DIR, PROJ, watcher="off")
before = p.call_tool("codebase_status", {"projectPath": PROJ}, timeout=30)
log["status_before_restart"] = before["result"]["content"][0]["text"]
log["qdrant_counts_before"] = qcounts()
print("BEFORE:", log["status_before_restart"][:200])

# Find and kill the disposable qdrant process, then restart it (same config/port).
out = subprocess.run(["pgrep", "-f", "qdrant-disposable.yaml"], capture_output=True, text=True).stdout.strip()
pids = [int(x) for x in out.splitlines() if x]
log["qdrant_pids_killed"] = pids
for pid in pids:
    os.kill(pid, 9)
time.sleep(1)
try:
    urllib.request.urlopen(QDRANT + "/collections", timeout=2)
    log["qdrant_reachable_immediately_after_kill"] = True
except Exception as e:
    log["qdrant_reachable_immediately_after_kill"] = False
    log["qdrant_kill_error"] = str(e)
print("qdrant down:", not log["qdrant_reachable_immediately_after_kill"])

# Restart qdrant with the SAME config (same port/data dir) -- no client reconfiguration.
RAGOPS_DIR = os.path.dirname(__file__)
qproc = subprocess.Popen(
    ["~/.local/share/codex-ecosystem/tools/qdrant-1.19.1/qdrant",
     "--config-path", os.path.join(RAGOPS_DIR, "qdrant-disposable.yaml")],
    cwd=RAGOPS_DIR,
    stdout=open(os.path.join(RAGOPS_DIR, "qdrant-disposable-restart.log"), "w"),
    stderr=subprocess.STDOUT,
)
log["qdrant_restart_pid"] = qproc.pid

# Wait for qdrant to come back up.
up = False
for i in range(30):
    time.sleep(1)
    try:
        urllib.request.urlopen(QDRANT + "/collections", timeout=2)
        up = True
        break
    except Exception:
        continue
log["qdrant_back_up_after_s"] = i + 1
log["qdrant_up"] = up
print("qdrant restarted, up:", up, "after", i+1, "s")

# WITHOUT restarting or reconfiguring the SocratiCode MCP process 'p', query it again.
after = p.call_tool("codebase_status", {"projectPath": PROJ}, timeout=30)
log["status_after_qdrant_restart_same_sc_process"] = after["result"]["content"][0]["text"]
print("AFTER (same SC process):", log["status_after_qdrant_restart_same_sc_process"][:300])

search_after = p.call_tool("codebase_search", {"query": "modulo watcher marker", "projectPath": PROJ, "limit": 2}, timeout=30)
log["search_after_qdrant_restart_same_sc_process"] = search_after["result"]["content"][0]["text"][:500]

log["qdrant_counts_after_restart"] = qcounts()
p.terminate_clean()

# Now test a FRESH SocratiCode process (as native clients would create) pointed at the same
# disposable QDRANT_URL env var (no different config) -- this is the "reconnect without manual
# reconfiguration" check since the client just uses the same env/config as before.
p2 = spawn(QDRANT, HOME_DIR, PROJ, watcher="off")
fresh = p2.call_tool("codebase_status", {"projectPath": PROJ}, timeout=30)
log["status_fresh_process_after_restart"] = fresh["result"]["content"][0]["text"]
print("FRESH PROCESS AFTER RESTART:", log["status_fresh_process_after_restart"][:300])
p2.terminate_clean()

with open(os.path.join(RAGOPS_DIR, "gap9_result.json"), "w") as f:
    json.dump(log, f, indent=2, default=str)
print("DONE")
