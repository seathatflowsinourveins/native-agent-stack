#!/usr/bin/env bash
# Fix round 2, gap 0: the frozen easy set and the frozen Codex-authored hard-negative
# set through promptfoo eval, with Nemotron (model-card input types and, as a
# diagnostic, the round-1 untyped call), bge-small-en-v1.5 and a constant control.
# Usage: run_g0_fixround2.sh WORK OUT EASY_CASES HARD_CASES FE_VENV FE_CACHE_DIR
set -u
WORK=$1; OUT=$2; EASY=$3; HARD=$4; FEV=$5; export FE_CACHE_DIR=$6; HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$WORK" "$OUT"
export PROMPTFOO_DISABLE_TELEMETRY=1 PROMPTFOO_CONFIG_DIR="$WORK/promptfoo-config" PROMPTFOO_PYTHON="$FEV/bin/python" HF_HUB_OFFLINE=1
rc() { echo "$2" > "$OUT/$1.exit"; echo "$1 exit=$2"; }
for set in easy hard; do
  D="$WORK/$set"; mkdir -p "$D"
  src=$EASY; [ $set = hard ] && src=$HARD
  cp "$src" "$D/cases.json"; sha256sum "$D/cases.json" | cut -d' ' -f1 > "$OUT/$set-cases.sha256"
  cp "$HERE"/heldout_common.py "$HERE"/pf_provider.py "$HERE"/pf_provider_typed.py "$HERE"/pf_provider_bge.py "$HERE"/pf_control_provider.py "$D/"
  python3 "$HERE/gen_fixround2_configs.py" "$D/cases.json" "$D" > "$OUT/$set-generator.stdout"
  cp "$D/labels.json" "$OUT/$set-labels.json"
  arms="typed bge"; [ $set = hard ] && arms="typed untyped bge control"
  for arm in $arms; do
    cp "$D/$arm.yaml" "$OUT/$set-$arm.yaml"
    ( cd "$D" && promptfoo eval -c $arm.yaml --no-cache -j 1 -o "$D/$arm-results.json" ) > "$OUT/$set-$arm.stdout" 2> "$OUT/$set-$arm.stderr"
    rc $set-$arm $?
    cp "$D/$arm-results.json" "$OUT/$set-$arm-results.json"
  done
done
