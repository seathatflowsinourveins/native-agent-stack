#!/bin/zsh
# Resume C3 (aimem-qwen3) to its boundary after the 2026-09-25 01:19 reboot into macOS 27.0 (declared deviation, A15.2),
# then a platform-drift check (20 completed questions recomputed with no cache), then stop every benchmark service.
set -u
B=$HOME/.local/share/agent-ecosystem/bench; L=$B/longmemeval
OLL=$HOME/.local/share/agent-ecosystem/ollama/current/ollama
export PATH="$HOME/.local/bin:$PATH"
log() { print -r -- "$(date +%H:%M:%S) $*"; }
env -i HOME="$HOME/.local/share/agent-ecosystem/ollama/runtime-home" PATH=/usr/bin:/bin OLLAMA_HOST=127.0.0.1:11436 \
  OLLAMA_MODELS="$HOME/.local/share/agent-ecosystem/ollama/models" OLLAMA_NUM_PARALLEL=8 OLLAMA_KEEP_ALIVE=60m \
  OLLAMA_CONTEXT_LENGTH=4096 OLLAMA_NO_CLOUD=1 OLLAMA_NOHISTORY=1 OLLAMA_MAX_LOADED_MODELS=1 "$OLL" serve > $B/ollama-embed/serve-macos27.log 2>&1 &
EMB=$!; echo "embed ollama pid $EMB (macOS 27.0)" > $B/ollama-embed/pid
for i in {1..60}; do curl -sf http://127.0.0.1:11436/api/version >/dev/null && break; sleep 1; done
(cd $L && exec .venv-official/bin/python embed_cache_proxy.py http://127.0.0.1:11436 11439 "$L/cache/embed-proxy.sqlite") > $L/logs/proxy-macos27.log 2>&1 &
PRX=$!
for i in {1..30}; do curl -sf http://127.0.0.1:11439/api/version >/dev/null && break; sleep 1; done
log "embed server $EMB and cache proxy $PRX up; resuming C3"
(cd $L && LME_EMBED_URL=http://127.0.0.1:11439 .venv-official/bin/python lme_harness.py aimem-qwen3) >> $L/logs/queue-aimem-qwen3.log 2>&1
log "C3 exit=$? rows=$(wc -l < $L/results/aimem-qwen3.jsonl | tr -d ' ') errors=$(grep -c '"error": "' $L/results/aimem-qwen3.jsonl)"
IDS=$(cd $L && .venv-official/bin/python -c 'import json; print(" ".join(json.loads(l)["question_id"] for l in list(open("results/aimem-qwen3.jsonl"))[100:120]))')
(cd $L && LME_EMBED_URL=http://127.0.0.1:11436 .venv-official/bin/python lme_harness.py aimem-qwen3 --ids ${=IDS} --out results-drift-macos27) > $L/logs/drift-macos27.log 2>&1
(cd $L && .venv-official/bin/python - <<'PY'
import json
orig = {json.loads(l)["question_id"]: json.loads(l) for l in open("results/aimem-qwen3.jsonl")}
new = [json.loads(l) for l in open("results-drift-macos27/aimem-qwen3.jsonl")]
same = lambda m: sum(all(abs(orig[r["question_id"]]["metrics"][t][m] - r["metrics"][t][m]) < 1e-12 for t in ("full", "official")) for r in new)
print(f"drift check (macOS 26.5 rows vs macOS 27.0 recompute, no cache): {len(new)} questions, errors {sum(r['error'] is not None for r in new)}; "
      f"identical recall_all@5 {same('recall_all@5')}, ndcg_any@5 {same('ndcg_any@5')}, recall_all@10 {same('recall_all@10')}")
PY
)
kill $PRX 2>/dev/null; kill $EMB 2>/dev/null; sleep 3; pkill -f "llama-server --model .*sha256-2b0cf8f1" 2>/dev/null
log "benchmark services stopped; coordinator back to cockpit-only"
