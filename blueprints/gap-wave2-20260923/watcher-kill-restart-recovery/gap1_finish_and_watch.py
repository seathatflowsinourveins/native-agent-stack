import sys, json, time, os, urllib.request
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

# Watcher=auto process, wait for the in-flight index (started by prior script) to complete.
p = spawn(QDRANT, HOME_DIR, PROJ, watcher="auto")
deadline = time.time() + 60
last = None
while time.time() < deadline:
    st = p.call_tool("codebase_status", {"projectPath": PROJ}, timeout=30)
    txt = st["result"]["content"][0]["text"]
    last = txt
    if "completed" in txt:
        break
    time.sleep(2)
print("--- index completion status ---")
print(last)
print("--- qdrant counts after full recovery index ---")
print(json.dumps(qcounts(), indent=2))

# Start the watcher explicitly and edit a file, confirm live pick-up without manual codebase_update.
wstart = p.call_tool("codebase_watch", {"projectPath": PROJ, "action": "start"}, timeout=30)
print("--- watcher start ---")
print(json.dumps(wstart))

target = os.path.join(PROJ, "alpha.py")
with open(target, "a") as f:
    f.write("\n\ndef modulo(a, b):\n    \"\"\"Modulo op, watcher freshness marker WATCHFRESH42.\"\"\"\n    return a % b\n")
print("edited file for watcher test")

# Give the watcher time to detect+reindex the change automatically (no codebase_update call).
found = False
q_result = None
for i in range(20):
    time.sleep(1.5)
    q = p.call_tool("codebase_search", {"query": "WATCHFRESH42 modulo watcher marker", "projectPath": PROJ, "limit": 3}, timeout=30)
    q_result = q
    txt = q["result"]["content"][0]["text"]
    if "WATCHFRESH42" in txt:
        found = True
        break
print(f"--- watcher-driven freshness found={found} after {(i+1)*1.5:.1f}s ---")
print(json.dumps(q_result)[:1200])

wstatus = p.call_tool("codebase_watch", {"projectPath": PROJ, "action": "status"}, timeout=30)
print("--- watcher status ---")
print(json.dumps(wstatus))

print("--- final qdrant counts ---")
print(json.dumps(qcounts(), indent=2))

p.terminate_clean()
