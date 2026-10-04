#!/usr/bin/env bash
# Workstation side of the Part B window (amendment 4). Stops the workstation's two model services by their literal
# unit names, checks the precondition of deviation 1 once before any load, loads the generation model on the
# measurement server and keeps it resident, then runs the named arms in order: for E3 and E4 gate F first, the run only
# if F passes; after every run the per-query metric and gate C; the generation model's residency is checked before
# every step and the window stops if it is gone. Starts the two services again whatever happens.
# usage: W-partb-window.sh <label> <arm> [<arm> ...]     arms: E1 E2 E3 E4
set -u
LABEL="${1:?label}"; shift
UNITS="native-stack-embeddings.service nativestack-generation.service"
W=/mnt/c/Windows/System32/wsl.exe
D="$HOME/.local/state/native-agent-stack/new-wsl-measure-20261002"
LOG="$D/raw/_gpu-window.txt"
GEN=swift-iq3s-s2o-64k
say() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" | tee -a "$LOG"; }
gpu() { nvidia-smi --query-gpu=memory.used --format=csv,noheader; }
clean() { tr -d '\r\000' | grep -v 'Failed to translate'; }
inside() { $W -d '<the throwaway distribution>' -- bash -s 2>&1 | clean; }
restore() {
  inside <<EOF > /dev/null
export PATH="\$HOME/.local/share/mise/shims:\$HOME/.local/bin:\$PATH" OLLAMA_HOST=127.0.0.1:21434
for m in \$(curl -fsS -m 10 http://127.0.0.1:21434/api/ps | python3 -c 'import json,sys; print(" ".join(m["name"] for m in json.load(sys.stdin).get("models", [])))'); do ollama stop "\$m"; done
EOF
  say "measurement server unloaded: $(echo 'curl -fsS -m 10 http://127.0.0.1:21434/api/ps' | inside | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("models", [])))' 2>/dev/null) model(s) resident"
  systemctl --user start $UNITS; say "workstation units started exit=$?"
  sleep 5; say "units now: $(systemctl --user is-active $UNITS | tr '\n' ' ')"
}
precheck() { inside < "$D/steps/M11p-precheck.sh" | tee -a "$LOG"; return "${PIPESTATUS[0]}"; }
gen_ok() {
  inside <<EOF | tee -a "$LOG" | tail -n 1 | grep -q '^generation fully on GPU$'
curl -fsS -m 10 http://127.0.0.1:21434/api/ps | python3 -c '
import json,sys
ms=[m for m in json.load(sys.stdin).get("models",[]) if m["name"].split(":")[0]=="$GEN"]
print("generation check:", [(m["name"], m.get("size"), m.get("size_vram")) for m in ms])
print("generation fully on GPU" if ms and all(m.get("size")==m.get("size_vram") for m in ms) else "generation NOT fully on GPU")'
EOF
}
for unit in $UNITS; do
  [ "$(systemctl --user is-active "$unit")" = "active" ] || { say "not opened: $unit is not active"; exit 1; }
done
precheck || { say "not opened: the measurement distribution holds GPU memory before any load"; exit 1; }
trap restore EXIT
say "Part B window $LABEL for $* : before stop $(gpu)"
systemctl --user stop $UNITS; say "workstation units stopped exit=$?"
sleep 6; say "GPU used after stop: $(gpu); units: $(systemctl --user is-active $UNITS | tr '\n' ' ')"
used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -n 1)
[ "${used:-99999}" -le 9000 ] || { say "window closed before any load: $used MiB in use"; exit 1; }
precheck || { say "window closed before any load: precondition failed after the units were stopped"; exit 1; }
inside <<EOF | tee -a "$LOG"
curl -fsS -m 900 http://127.0.0.1:21434/api/generate -d '{"model":"$GEN","prompt":"Reply with the word ready.","stream":false,"keep_alive":-1,"options":{"num_predict":16}}' | python3 -c 'import json,sys; d=json.load(sys.stdin); print("generation loaded:", d.get("done_reason"), "load_s", round(d.get("load_duration",0)/1e9,1))'
EOF
gen_ok || { say "the generation model is not resident and fully on the GPU after loading; window closed"; exit 1; }
say "generation model resident; GPU used $(gpu)"
for arm in "$@"; do
  gen_ok || { say "$arm not started: the generation model is no longer fully on the GPU; window closed"; break; }
  out="runs/$arm-$LABEL"
  if [ "$arm" = "E3" ] || [ "$arm" = "E4" ]; then
    say "fit:$arm start"
    rec="$D/raw/PB-fit-$arm-$LABEL.txt"; [ ! -e "$rec" ] || { say "fit:$arm not started: its record exists"; continue; }
    echo "cd \$HOME/measure/partb/harness && HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_OFFLINE=1 timeout 1800 ../venv/bin/python -B partb_fit.py $arm; echo \"fit exit \$?\"" | inside > "$rec"
    say "fit:$arm end; record sha256 $(sha256sum "$rec" | cut -c1-64); $(grep -E '^fit exit' "$rec")"
    if grep -q '^fit exit 1$' "$rec"; then say "$arm out: gate F says it does not fit beside the generation model"; continue; fi
    grep -q '^fit exit 0$' "$rec" || { say "$arm not run in this window: gate F stopped on an error that is not a fit result (amendment 4a, item 7)"; continue; }
    gen_ok || { say "$arm not run: the generation model left the GPU during gate F; window closed"; break; }
  fi
  rec="$D/raw/PB-run-$arm-$LABEL.txt"; [ ! -e "$rec" ] || { say "run:$arm not started: its record exists"; continue; }
  say "run:$arm start"
  echo "cd \$HOME/measure/partb/harness && HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_OFFLINE=1 timeout 5400 ../venv/bin/python -B partb_run.py $arm ../$out; echo \"run exit \$?\"; HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_OFFLINE=1 ../venv/bin/python -B partb_perquery.py ../$out; echo \"perquery exit \$?\"" | inside > "$rec"
  say "run:$arm end; record sha256 $(sha256sum "$rec" | cut -c1-64); $(grep -E '^(run|perquery) exit' "$rec" | tr '\n' ' ')"
  case "$arm" in
    E1) echo 'OLLAMA_HOST=127.0.0.1:21434 ~/.local/share/mise/shims/ollama stop qwen3-embedding-8k:latest; echo "unload E1 exit $?"' | inside | tee -a "$LOG" ;;
    E2) echo 'OLLAMA_HOST=127.0.0.1:21434 ~/.local/share/mise/shims/ollama stop embeddinggemma:latest; echo "unload E2 exit $?"' | inside | tee -a "$LOG" ;;
  esac
done
say "GPU used before restart: $(gpu)"
