import sys, json, time, os
sys.path.insert(0, os.path.dirname(__file__))
from mcp_client import spawn

QDRANT="http://127.0.0.1:26333"
HOME_DIR=os.path.join(os.path.dirname(__file__), "mcp-home")
PROJ=os.path.join(os.path.dirname(__file__), "scratch-project")

log = {"steps": []}

def step(name, data):
    log["steps"].append({"name": name, "at": time.time(), "data": data})
    print(f"=== {name} ===")
    print(json.dumps(data, indent=2)[:1500])

import urllib.request
def qdrant_point_counts():
    req = urllib.request.Request(QDRANT + "/collections")
    with urllib.request.urlopen(req, timeout=5) as r:
        cols = json.loads(r.read())["result"]["collections"]
    counts = {}
    for c in cols:
        name = c["name"]
        try:
            req2 = urllib.request.Request(QDRANT + f"/collections/{name}")
            with urllib.request.urlopen(req2, timeout=5) as r2:
                info = json.loads(r2.read())["result"]
            counts[name] = info.get("points_count")
        except Exception as e:
            counts[name] = f"ERR:{e}"
    return counts

# 1. Start a process, kick off indexing (background), let it run briefly, then kill -9 mid-index.
p1 = spawn(QDRANT, HOME_DIR, PROJ, watcher="off")
r = p1.call_tool("codebase_index", {"projectPath": PROJ})
step("index_start_call1", r)
time.sleep(0.6)  # let it get partway through embedding calls (402 files, expect multiple batches)
s = p1.call_tool("codebase_status", {"projectPath": PROJ})
step("status_before_kill", s)
counts_before_kill = qdrant_point_counts()
step("qdrant_counts_before_kill", counts_before_kill)
p1.kill(9)
time.sleep(0.5)
step("proc1_poll_after_kill9", {"returncode": p1.poll()})

counts_after_kill = qdrant_point_counts()
step("qdrant_counts_after_kill", counts_after_kill)

# 2. Restart fresh process, resume indexing via codebase_index again (checkpoint resume per docs).
p2 = spawn(QDRANT, HOME_DIR, PROJ, watcher="off")
r2 = p2.call_tool("codebase_index", {"projectPath": PROJ})
step("index_resume_call2", r2)
# Poll status until 100% or timeout
deadline = time.time() + 90
final_status = None
while time.time() < deadline:
    st = p2.call_tool("codebase_status", {"projectPath": PROJ})
    final_status = st
    txt = json.dumps(st)
    if '"progress":100' in txt or "100%" in txt or "complete" in txt.lower():
        break
    time.sleep(2)
step("status_after_resume_poll", final_status)

counts_after_resume = qdrant_point_counts()
step("qdrant_counts_after_resume", counts_after_resume)

# 3. Edit a file, then verify watcher/update-based reindex picks up the change.
target_file = os.path.join(PROJ, "alpha.py")
with open(target_file, "a") as f:
    f.write("\n\ndef divide(a, b):\n    \"\"\"Divide a by b, distinctive marker ZQXJ99.\"\"\"\n    return a / b\n")
step("edited_file", {"file": target_file})

upd = p2.call_tool("codebase_update", {"projectPath": PROJ})
step("codebase_update_after_edit", upd)

query = p2.call_tool("codebase_search", {"query": "ZQXJ99 divide function distinctive marker", "projectPath": PROJ, "limit": 3})
step("query_after_edit", query)

counts_final = qdrant_point_counts()
step("qdrant_counts_final", counts_final)

p2.terminate_clean()

with open(os.path.join(os.path.dirname(__file__), "gap1_result.json"), "w") as f:
    json.dump(log, f, indent=2, default=str)

print("DONE")
