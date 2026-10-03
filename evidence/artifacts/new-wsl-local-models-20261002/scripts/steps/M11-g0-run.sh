#!/usr/bin/env bash
# Measurement distribution only. Run gate G0 for one prepared arm: one unscored warm-up and three scored runs with
# the gate's own run script and scorer, unchanged. No run is repeated, excluded or re-scored: a label that exists is
# refused by the gate script itself. Prints each run's score and the server-log lines the gate's verdict rested on.
# usage: bash -s <S1|S1b|S2>
set -u
ARM="${1:?arm}"
export PATH="/usr/lib/wsl/lib:$PATH"
S="$HOME/measure/g0/$ARM"; export GATE_STATE="$S"
[ -x "$S/bin/codex" ] || { echo "arm $ARM is not prepared"; exit 2; }
echo "G0 $ARM start $(date -u +%Y-%m-%dT%H:%M:%SZ); GPU used before: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
( cd "$S" && sha256sum -c setup/hashes.txt 2>&1 | grep -vc ': OK$' | sed 's/^/prepared files changed since setup: /' )
for label in warmup 1 2 3; do
  bash "$S/gate/gate_run.sh" llama "$label" > "$S/runs/$label.out" 2>&1; rc=$?
  log="$S/runs/$label/server.log"
  echo "== $label gate_run exit $rc at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  grep -E '^(server_ready|codex_exit|server_alive_after_stop)' "$S/runs/$label/run-meta.txt" 2>/dev/null | tr '\n' ' '; echo
  python3 - "$S/runs/$label/score.json" <<'PY'
import json, sys
try:
    score = json.load(open(sys.argv[1]))
except Exception as error:
    print("no score:", type(error).__name__); raise SystemExit
keep = {k: score.get(k) for k in ("run_pass", "tool_call_completed", "last_message_contains_datetime", "exit", "turn_status", "failure") if k in score}
print("score:", keep if keep else {k: score[k] for k in list(score)[:8]})
PY
  if [ -f "$log" ]; then
    echo "server log: offload lines $(grep -ciE 'offloaded [0-9]+/[0-9]+ layers' "$log"): $(grep -iE 'offloaded [0-9]+/[0-9]+ layers' "$log" | tail -n 1 | cut -c1-110)"
    echo "server log: lines naming namespace $(grep -c 'namespace' "$log"); unsupported tool type $(grep -ci 'unsupported.*tool type' "$log"); HTTP 500 $(grep -c ' 500' "$log"); errors $(grep -ciE '\berror\b' "$log")"
    grep -iE 'unsupported.*tool type|failed to load|unknown (model )?architecture|error loading model' "$log" | sort | uniq -c | head -n 4 | cut -c1-200
  fi
  [ -s "$S/runs/$label/codex-stderr.txt" ] && tail -n 2 "$S/runs/$label/codex-stderr.txt" | cut -c1-200
done
python3 - "$S/runs" <<'PY'
import json, pathlib, sys
runs = pathlib.Path(sys.argv[1]); passed = []
for label in ("1", "2", "3"):
    try:
        passed.append(bool(json.load(open(runs / label / "score.json")).get("run_pass")))
    except Exception:
        passed.append(False)
print("scored runs passed:", sum(passed), "of 3 | arm passes G0:", all(passed))
PY
echo "G0 $ARM end $(date -u +%Y-%m-%dT%H:%M:%SZ); GPU used after: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
