import sys, json, time, os
sys.path.insert(0, os.path.dirname(__file__))
from mcp_client import spawn

QDRANT="http://127.0.0.1:26333"
HOME_DIR=os.path.join(os.path.dirname(__file__), "mcp-home")
PROJ=os.path.join(os.path.dirname(__file__), "scratch-project")

p = spawn(QDRANT, HOME_DIR, PROJ, watcher="off")
print(json.dumps(p.call_tool("codebase_index", {"projectPath": PROJ}, timeout=30)))
for i in range(15):
    time.sleep(2)
    st = p.call_tool("codebase_status", {"projectPath": PROJ}, timeout=30)
    txt = st["result"]["content"][0]["text"]
    print(f"--- t+{(i+1)*2}s ---")
    print(txt[:300])
p.terminate_clean()
