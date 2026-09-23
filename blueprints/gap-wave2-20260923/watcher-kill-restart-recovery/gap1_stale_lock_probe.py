import sys, json, time, os
sys.path.insert(0, os.path.dirname(__file__))
from mcp_client import spawn

QDRANT="http://127.0.0.1:26333"
HOME_DIR=os.path.join(os.path.dirname(__file__), "mcp-home")
PROJ=os.path.join(os.path.dirname(__file__), "scratch-project")

p = spawn(QDRANT, HOME_DIR, PROJ, watcher="off")
print("--- codebase_stop ---")
print(json.dumps(p.call_tool("codebase_stop", {"projectPath": PROJ}, timeout=30)))
print("--- status after stop ---")
print(json.dumps(p.call_tool("codebase_status", {"projectPath": PROJ}, timeout=30)))
print("--- codebase_index (fresh attempt after stop) ---")
print(json.dumps(p.call_tool("codebase_index", {"projectPath": PROJ}, timeout=30)))
time.sleep(3)
print("--- status after re-index attempt ---")
print(json.dumps(p.call_tool("codebase_status", {"projectPath": PROJ}, timeout=30)))
p.terminate_clean()
