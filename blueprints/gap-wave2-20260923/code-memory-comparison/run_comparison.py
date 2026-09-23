import sys, json, time, os
sys.path.insert(0, os.path.dirname(__file__))
from cm_client import spawn_cm

PROJ = "~/codex-ecosystem/state/gap-wave2-20260923/rag-ops/scratch-project"
log = {}

t0 = time.time()
p = spawn_cm(PROJ)
t1 = time.time()
log["spawn_and_initialize_s"] = round(t1 - t0, 2)

# Cold index
t2 = time.time()
idx = p.call_tool("index_codebase", {"directory": PROJ}, timeout=300)
t3 = time.time()
log["index_codebase_call_s"] = round(t3 - t2, 2)
log["index_result"] = idx

# Stats
stats = p.call_tool("get_index_stats", {"directory": PROJ}, timeout=30)
log["stats_after_index"] = stats

# Search baseline
search1 = p.call_tool("search_code", {"query": "divide function ZQXJ99 marker", "directory": PROJ}, timeout=30)
log["search_before_edit"] = search1

# Edit a NEW marker into a file (freshness test)
target = os.path.join(PROJ, "beta.py")
with open(target, "a") as f:
    f.write("\n\ndef cmfresh(a, b):\n    \"\"\"code-memory freshness marker CMFRESH2026.\"\"\"\n    return a - b\n")
log["edited_file"] = target

# Re-index (freshness update) and time it
t4 = time.time()
idx2 = p.call_tool("index_codebase", {"directory": PROJ}, timeout=300)
t5 = time.time()
log["reindex_after_edit_call_s"] = round(t5 - t4, 2)
log["reindex_result"] = idx2

search2 = p.call_tool("search_code", {"query": "CMFRESH2026 freshness marker", "directory": PROJ}, timeout=30)
log["search_after_edit"] = search2

p.terminate_clean()

with open(os.path.join(os.path.dirname(__file__), "comparison_result.json"), "w") as f:
    json.dump(log, f, indent=2, default=str)

print(json.dumps({k: v for k, v in log.items() if not isinstance(v, dict)}, indent=2))
print("--- index_result ---")
print(json.dumps(log["index_result"])[:800])
print("--- stats ---")
print(json.dumps(log["stats_after_index"])[:500])
print("--- search_before_edit ---")
print(json.dumps(log["search_before_edit"])[:500])
print("--- reindex_result ---")
print(json.dumps(log["reindex_result"])[:800])
print("--- search_after_edit ---")
print(json.dumps(log["search_after_edit"])[:800])
