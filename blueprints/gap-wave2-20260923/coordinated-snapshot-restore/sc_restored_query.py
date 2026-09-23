import sys, json, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "watcher-kill-restart-recovery"))
from mcp_client import spawn
QDRANT="http://127.0.0.1:36333"
HOME_DIR=os.path.expanduser("~/codex-ecosystem/state/gap-wave2-20260923/rag-ops/gap10/mcp-home-restored")
PROJ=os.path.expanduser("~/code/agent-lab")
p = spawn(QDRANT, HOME_DIR, PROJ, watcher="off")
q = p.call_tool("codebase_search", {"query": "RTK Bash hook full-diff and network exclusions raw recovery", "projectPath": PROJ, "limit": 3}, timeout=30)
print(q["result"]["content"][0]["text"])
p.terminate_clean()
