#!/usr/bin/env bash
# Two-arm run for gaps 0/2/3. Every arm runs inside `unshare -rn` (no network).
# Usage: run_two_arm.sh OUTDIR
set -uo pipefail
OUT=$1; mkdir -p "$OUT"
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
PR=$REPO/blueprints/native-skill-practice
TASK=$REPO/blueprints/gap-wave2-20260923/us-equities__evaluation-experiments/inspect-arm/catalog_task.py
C=${HOME}/.cache/gap-wave2-20260923/evaluation-experiments
INSPECT=$C/venv-inspect/bin/inspect
unset TYPESAFE_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY
export PROMPTFOO_DISABLE_TELEMETRY=1 PROMPTFOO_DISABLE_UPDATE_CHECK=1 INSPECT_DISPLAY=plain NO_COLOR=1
NS="unshare -rn"
# Background jobs in a non-interactive shell inherit SIGINT=ignored; restore the
# default disposition so the interrupt is a real Ctrl-C equivalent for both arms.
SIGDFL=(python3 -c 'import os,signal,sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execvp(sys.argv[1], sys.argv[1:])')
stamp() { date -u +%FT%T.%3NZ; }
log() { echo "$(stamp) $*" | tee -a "$OUT/timeline.txt"; }

pf() { # name, extra args...
  local name=$1; shift
  mkdir -p "$OUT/pf-$name"
  ( cd "$PR" && PROMPTFOO_CONFIG_DIR="${PF_HOME:-$OUT/pf-$name/home}" $NS promptfoo eval -c "${PF_CONFIG:-promptfooconfig.yaml}" \
      --filter-providers exact-text-baseline-v1 --no-cache --no-share --no-table -j 1 \
      -o "$OUT/pf-$name/results.json" "$@" ) > "$OUT/pf-$name/stdout.txt" 2> "$OUT/pf-$name/stderr.txt"
  echo $?
}
ins() { # name, extra args...
  local name=$1; shift
  mkdir -p "$OUT/in-$name/home"
  ( cd "$(dirname "$TASK")" && HOME="$OUT/in-$name/home" $NS "$INSPECT" eval catalog_task.py --max-samples 1 --max-connections 1 \
      --retry-on-error 1 --log-format json --log-dir "$OUT/in-$name/logs" "$@" \
      > "$OUT/in-$name/stdout.txt" 2> "$OUT/in-$name/stderr.txt" )
  echo $?
}

log "sha catalog-cases $(sha256sum "$PR/catalog-cases.json" | cut -c1-64)"
for r in 1 2; do
  log "pf-clean-$r exit=$(pf clean-$r)"
  log "in-clean-$r exit=$(ins clean-$r)"
done

# Fault injection (diagnostic, derived config/task args): one transient error on C3's first attempt.
C3_CLAIM_PREFIX=$(python3 -c "import json;print([c for c in json.load(open('$PR/catalog-cases.json')) if c['metadata']['case_id']=='C3'][0]['vars']['claim'][:40])")
export C3_CLAIM_PREFIX
FAULT=$OUT/pf-fault/promptfooconfig.fault.yaml; mkdir -p "$OUT/pf-fault"
python3 - "$PR/promptfooconfig.yaml" "$FAULT" <<'PY'
import sys, yaml
cfg = yaml.safe_load(open(sys.argv[1]))
for p in cfg['providers']:
    if p.get('label') == 'exact-text-baseline-v1':
        p['transform'] = ("(process.env.INJECT_FAIL === '1' && context.vars.claim.startsWith(process.env.C3_CLAIM_PREFIX)) ? "
                          "(() => { throw new Error('injected transient failure for C3 (first attempt)'); })() : (" + p['transform'] + ")")
cfg['prompts'] = cfg['prompts']
open(sys.argv[2], 'w').write(yaml.safe_dump(cfg, sort_keys=False))
PY
# promptfoo resolves file:// relative to the config; copy the fault config next to the originals.
cp "$FAULT" "$PR/.fault-promptfooconfig.yaml"
log "pf-fault first exit=$(PF_CONFIG=.fault-promptfooconfig.yaml INJECT_FAIL=1 pf fault)"
python3 "$(dirname "$0")/pf_db_snapshot.py" "$OUT/pf-fault/"home/promptfoo.db > "$OUT/pf-fault/db-after-first.json"
log "pf-fault retry-errors exit=$(PF_HOME=$OUT/pf-fault/home PF_CONFIG=.fault-promptfooconfig.yaml INJECT_FAIL=0 pf fault-retry --retry-errors)"
python3 "$(dirname "$0")/pf_db_snapshot.py" "$OUT/pf-fault/"home/promptfoo.db > "$OUT/pf-fault/db-after-retry.json"
rm -f "$PR/.fault-promptfooconfig.yaml"
mkdir -p "$OUT/in-fault/markers"
log "in-fault exit=$(ins fault -T fail_once_case=C3 -T marker_dir="$OUT/in-fault/markers")"
mkdir -p "$OUT/in-fault-noretry/markers"
log "in-fault-noretry exit=$(ins fault-noretry -T fail_once_case=C3 -T marker_dir="$OUT/in-fault-noretry/markers" --retry-on-error 0)"

# Interrupt and resume.
mkdir -p "$OUT/pf-int"
( cd "$PR" && PROMPTFOO_CONFIG_DIR="$OUT/pf-int/home" exec "${SIGDFL[@]}" $NS promptfoo eval -c promptfooconfig.yaml \
    --filter-providers exact-text-baseline-v1 --no-cache --no-share --no-table -j 1 --delay 1500 \
    -o "$OUT/pf-int/results-interrupted.json" ) > "$OUT/pf-int/stdout-1.txt" 2> "$OUT/pf-int/stderr-1.txt" &
PID=$!; sleep 5.5; log "pf-int SIGINT pid=$PID"; kill -INT $PID; wait $PID; log "pf-int first exit=$?"
python3 "$(dirname "$0")/pf_db_snapshot.py" "$OUT/pf-int/"home/promptfoo.db > "$OUT/pf-int/db-after-interrupt.json"
[ -f "$OUT/pf-int/results-interrupted.json" ] && cp "$OUT/pf-int/results-interrupted.json" "$OUT/pf-int/output-after-interrupt.json"
( cd "$PR" && PROMPTFOO_CONFIG_DIR="$OUT/pf-int/home" $NS promptfoo eval --resume --no-share --no-table \
    -o "$OUT/pf-int/results.json" ) > "$OUT/pf-int/stdout-2.txt" 2> "$OUT/pf-int/stderr-2.txt"
log "pf-int resume exit=$?"
python3 "$(dirname "$0")/pf_db_snapshot.py" "$OUT/pf-int/"home/promptfoo.db > "$OUT/pf-int/db-after-resume.json"
mkdir -p "$OUT/in-int/home"
( cd "$(dirname "$TASK")" && HOME="$OUT/in-int/home" exec "${SIGDFL[@]}" $NS "$INSPECT" eval catalog_task.py --max-samples 1 --max-connections 1 --retry-on-error 1 \
    --log-format json --log-dir "$OUT/in-int/logs" -T delay=1.5 ) > "$OUT/in-int/stdout-1.txt" 2> "$OUT/in-int/stderr-1.txt" &
PID=$!; sleep 7; log "in-int SIGINT pid=$PID"; kill -INT $PID; wait $PID; log "in-int first exit=$?"
FIRST=$(ls "$OUT"/in-int/logs/*.json | head -1); cp "$FIRST" "$OUT/in-int/interrupted-log.json"
( cd "$(dirname "$TASK")" && HOME="$OUT/in-int/home" $NS "$INSPECT" eval-retry "$FIRST" --max-samples 1 --max-connections 1 --retry-on-error 1 \
    --log-dir "$OUT/in-int/logs" ) > "$OUT/in-int/stdout-2.txt" 2> "$OUT/in-int/stderr-2.txt"
log "in-int resume exit=$?"
log "sha catalog-cases $(sha256sum "$PR/catalog-cases.json" | cut -c1-64)"
