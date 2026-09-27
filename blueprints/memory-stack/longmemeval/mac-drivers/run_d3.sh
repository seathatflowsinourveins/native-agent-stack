#!/bin/zsh
# Start D3 (am-qwen3, 4 isolated slots, benchmark embed server) once D2 has finished, gated on a
# slot smoke test: 4 keyless questions in parallel slots must reproduce D1's sequential rankings exactly.
set -u
cd "${0:A:h}"
export PATH="$HOME/.local/bin:$PATH"
PY=$PWD/.venv-official/bin/python
while kill -0 17380 2>/dev/null; do sleep 15; done
echo "$(date +%H:%M:%S) D2 finished; slot smoke test"
rm -rf results-smoke-slots
IDS=$($PY -c 'import json; print(" ".join(json.loads(l)["question_id"] for l in list(open("results/am-keyless.jsonl"))[:4]))')
$PY lme_harness.py am-keyless --ids ${=IDS} --workers 4 --out results-smoke-slots || exit 1
$PY - <<'EOF' || { echo "slot smoke test FAILED; D3 not started"; exit 1; }
import json, sys
seq = {json.loads(l)["question_id"]: json.loads(l) for l in open("results/am-keyless.jsonl")}
par = [json.loads(l) for l in open("results-smoke-slots/am-keyless.jsonl")]
ok = len(par) == 4 and all(r["error"] is None and r["ranking"] == seq[r["question_id"]]["ranking"] for r in par)
print("slots used:", sorted({r.get("slot") for r in par}), "| identical rankings:", ok)
sys.exit(0 if ok else 1)
EOF
echo "$(date +%H:%M:%S) smoke passed; starting D3"
LME_EMBED_URL=http://127.0.0.1:11436 $PY lme_harness.py am-qwen3
echo "$(date +%H:%M:%S) D3 finished"
