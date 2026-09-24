#!/usr/bin/env bash
# Gap 0 (held-out 30, vars-based assertion + control), gap 4 (same frozen cases
# through Promptfoo and Inspect) and gap 7 (upstream four-query assertion rerun
# with -o results.json; token usage). vLLM prompt_tokens_total is snapshotted
# around every run and over quiet control intervals.
# Usage: run_g0_g4_g7.sh WORKDIR OUT CASES_JSON UPSTREAM4_DIR VENV
set -u
WORK=$1; OUT=$2; CASES=$3; UP4=$4; VENV=$5; HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$WORK" "$OUT"
export PROMPTFOO_DISABLE_TELEMETRY=1 PROMPTFOO_CONFIG_DIR="$WORK/promptfoo-config" MLFLOW_DISABLE_AGENT_HINT=1
rc() { echo "$2" > "$OUT/$1.exit"; echo "$1 exit=$2"; }
snap() {  # label -> one line: label utc prompt_tokens_total success_stop
  local m; m=$(curl -s -m 5 http://127.0.0.1:8231/metrics)
  echo "$1 $(date -u +%FT%T.%3NZ) $(echo "$m" | awk '/^vllm:prompt_tokens_total\{/{print $2}') $(echo "$m" | awk '/^vllm:request_success_total\{.*finished_reason="stop"/{print $2}')" >> "$OUT/vllm-metrics.txt"
}
timed() {  # name cmd... ; wall-clock ms to $OUT/name.wall_ms
  local s e; s=$(date +%s%N); "${@:2}"; local r=$?; e=$(date +%s%N); echo $(( (e - s) / 1000000 )) > "$OUT/$1.wall_ms"; return $r
}
echo "# label utc vllm:prompt_tokens_total vllm:request_success_total{stop}" > "$OUT/vllm-metrics.txt"

cp "$CASES" "$WORK/cases.json"; sha256sum "$WORK/cases.json" | cut -d' ' -f1 > "$OUT/cases.sha256"
cp "$HERE"/heldout_common.py "$HERE"/pf_provider.py "$HERE"/pf_control_provider.py "$HERE"/inspect_heldout_task.py "$WORK/"
python3 "$HERE/gen_heldout_promptfoo.py" "$WORK/cases.json" "$WORK" > "$OUT/generator.stdout"
cp "$WORK/promptfooconfig.yaml" "$OUT/heldout-promptfooconfig.yaml"; cp "$WORK/control.yaml" "$OUT/heldout-control.yaml"; cp "$WORK/labels.json" "$OUT/labels.json"

snap quiet1-start; sleep 15; snap quiet1-end

# Gap 0 / 4 / 7: held-out run through Promptfoo (python provider reporting billed tokens)
snap pf-heldout-start
( cd "$WORK" && timed pf-heldout promptfoo eval -c promptfooconfig.yaml --no-cache -j 1 -o "$WORK/pf-heldout-results.json" ) > "$OUT/pf-heldout.stdout" 2> "$OUT/pf-heldout.stderr"
rc pf-heldout $?
snap pf-heldout-end

# Gap 0 control: constant provider, no model call
( cd "$WORK" && promptfoo eval -c control.yaml --no-cache -j 1 -o "$WORK/pf-control-results.json" ) > "$OUT/pf-control.stdout" 2> "$OUT/pf-control.stderr"
rc pf-control $?

# Gap 4: identical frozen cases through Inspect (JSON log format)
snap inspect-start
( cd "$WORK" && timed inspect-heldout "$VENV/bin/inspect" eval inspect_heldout_task.py --log-dir "$WORK/inspect-logs" --log-format json ) > "$OUT/inspect-heldout.stdout" 2> "$OUT/inspect-heldout.stderr"
rc inspect-heldout $?
snap inspect-end

# Gap 7: upstream four-query retrieval assertion, rerun with -o results.json
cp "$HERE/../../../examples/promptfoo-nemotron-upstream/promptfooconfig.yaml" "$UP4/promptfooconfig.yaml"
snap upstream4-start
( cd "$UP4" && PATH="$VENV/bin:$PATH" timed upstream4 promptfoo eval -c promptfooconfig.yaml --no-cache -j 1 -o "$UP4/results.json" ) > "$OUT/upstream4.stdout" 2> "$OUT/upstream4.stderr"
rc upstream4 $?
snap upstream4-end

snap quiet2-start; sleep 15; snap quiet2-end
