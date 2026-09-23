import sys, json, time, os
sys.path.insert(0, os.path.dirname(__file__))
from mcp_client import spawn
QDRANT="http://127.0.0.1:26333"
HOME_DIR=os.path.join(os.path.dirname(__file__), "mcp-home")
PROJ=os.path.join(os.path.dirname(__file__), "scratch-project")
p = spawn(QDRANT, HOME_DIR, PROJ, watcher="off")
print("--- codebase_remove (clears stale lock) ---")
print(json.dumps(p.call_tool("codebase_remove", {"projectPath": PROJ}, timeout=30)))
print("--- codebase_index (fresh full index) ---")
print(json.dumps(p.call_tool("codebase_index", {"projectPath": PROJ}, timeout=30)))
deadline = time.time() + 60
while time.time() < deadline:
    st = p.call_tool("codebase_status", {"projectPath": PROJ}, timeout=30)
    txt = st["result"]["content"][0]["text"]
    if "completed" in txt or "100%" in txt:
        print("--- status: recovered ---")
        print(txt[:400])
        break
    time.sleep(2)
else:
    print("--- status: TIMEOUT, last ---")
    print(txt[:400])
p.terminate_clean()
