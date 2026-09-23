import sys, json, os
sys.path.insert(0, "~/codex-ecosystem/state/gap-wave2-20260923/rag-ops")
from mcp_client import spawn
QDRANT="http://127.0.0.1:36333"  # the RESTORED disposable Qdrant (from the snapshot)
HOME_DIR="~/codex-ecosystem/state/gap-wave2-20260923/rag-ops/gap10/mcp-home-restored"
os.makedirs(HOME_DIR, exist_ok=True)
PROJ="~/code/agent-lab"  # a project path present in the restored socraticode_metadata
p = spawn(QDRANT, HOME_DIR, PROJ, watcher="off")
st = p.call_tool("codebase_status", {"projectPath": PROJ}, timeout=30)
print(json.dumps(st, indent=2))
p.terminate_clean()
