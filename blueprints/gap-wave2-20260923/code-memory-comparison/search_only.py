import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
from cm_client import spawn_cm
PROJ = "~/codex-ecosystem/state/gap-wave2-20260923/rag-ops/scratch-project"
p = spawn_cm(PROJ)
r1 = p.call_tool("search_code", {"query": "cmfresh code-memory freshness marker", "search_type": "topic_discovery", "directory": PROJ}, timeout=30)
print("--- topic_discovery search (post-edit already applied earlier) ---")
print(r1["result"]["content"][0]["text"][:1200])
r2 = p.call_tool("search_code", {"query": "cmfresh", "search_type": "definition", "directory": PROJ}, timeout=30)
print("--- definition search for cmfresh ---")
print(r2["result"]["content"][0]["text"][:1200])
p.terminate_clean()
