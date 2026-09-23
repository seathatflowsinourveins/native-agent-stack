import sys, json, time, os
sys.path.insert(0, os.path.dirname(__file__))
from mcp_client import spawn
QDRANT="http://127.0.0.1:26333"
HOME_DIR=os.path.join(os.path.dirname(__file__), "mcp-home")
PROJ=os.path.join(os.path.dirname(__file__), "scratch-project")

p0 = spawn(QDRANT, HOME_DIR, PROJ, watcher="off")
print("--- remove ---")
print(json.dumps(p0.call_tool("codebase_remove", {"projectPath": PROJ}, timeout=30)))
p0.terminate_clean()
time.sleep(1.0)

p1 = spawn(QDRANT, HOME_DIR, PROJ, watcher="off")
print("--- fresh process index ---")
print(json.dumps(p1.call_tool("codebase_index", {"projectPath": PROJ}, timeout=30)))
deadline = time.time() + 60
last = None
while time.time() < deadline:
    st = p1.call_tool("codebase_status", {"projectPath": PROJ}, timeout=30)
    txt = st["result"]["content"][0]["text"]
    last = txt
    print(f"[{time.time():.1f}] {txt[:150].splitlines()[0] if txt else ''}")
    if "completed" in txt or "100%" in txt:
        break
    time.sleep(2)
print("--- final ---")
print(last)
p1.terminate_clean()
