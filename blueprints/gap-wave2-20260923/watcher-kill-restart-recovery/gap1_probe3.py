import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
from mcp_client import spawn
QDRANT="http://127.0.0.1:26333"
HOME_DIR=os.path.join(os.path.dirname(__file__), "mcp-home")
PROJ=os.path.join(os.path.dirname(__file__), "scratch-project")
p = spawn(QDRANT, HOME_DIR, PROJ, watcher="off")
print("--- update (lock check) ---")
print(json.dumps(p.call_tool("codebase_update", {"projectPath": PROJ}, timeout=30)))
p.terminate_clean()
