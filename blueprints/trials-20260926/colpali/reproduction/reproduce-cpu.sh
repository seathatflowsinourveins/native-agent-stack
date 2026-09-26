#!/bin/sh
# Self-contained CPU reproduction of the ColPali trial's primary run and its random control.
#
# Usage: sh reproduce-cpu.sh <output-dir>
#
# Creates a fresh mktemp workspace (removed on exit), installs the exact environment that
# produced the original result (requirements-lock.txt: vidore-benchmark 5.0.0,
# colpali-engine 0.3.13, torch 2.8.0, transformers 4.53.1, ...), downloads the pinned model
# and dataset revisions into a private HF_HOME, rebuilds the 12-row slice (build_slice.py,
# checked against slice-expected.json), then runs the unchanged upstream
# `vidore-benchmark evaluate-retriever` CLI on CPU (CUDA_VISIBLE_DEVICES="") for
# vidore/colpali-v1.3 and for the built-in dummy_vision_retriever control, offline, under
# /usr/bin/time -v. Only <output-dir> receives files. Nothing is written to the shared
# Hugging Face cache. The script is local integration glue; the metrics are the CLI's own.
set -u

here=$(cd "$(dirname "$0")" && pwd)
out=${1:?usage: sh reproduce-cpu.sh <output-dir>}
mkdir -p "$out"
out=$(cd "$out" && pwd)
work=$(mktemp -d)
cleanup() { rm -rf "$work"; }
trap cleanup EXIT
trap 'exit 130' INT TERM

COLPALI_REVISION=b5c6dd62125326e6f0b540c1f7b36e901cdc0a11
BASE_REVISION=30ab955d073de4a91dc5a288e8c97226647e3e5a
DATASET_REVISION=16c8e633612fbda7400bfcbbc31d61a7534f580f

export HF_HOME="$work/hf" HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 TOKENIZERS_PARALLELISM=false
export CUDA_VISIBLE_DEVICES="" UV_NO_PROGRESS=1

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$out/steps.log"; }
fail() { log "FAIL: $*"; exit 1; }

log "start; workspace is a fresh mktemp directory; nproc=$(nproc)"
uv venv --python 3.11.16 "$work/venv" > "$out/venv.log" 2>&1 || fail "uv venv"
uv pip install --python "$work/venv/bin/python" -r "$here/requirements-lock.txt" > "$out/install.log" 2>&1 || fail "uv pip install"
uv pip freeze --python "$work/venv/bin/python" > "$out/installed-freeze.txt" 2>/dev/null || fail "uv pip freeze"
if cmp -s "$out/installed-freeze.txt" "$here/requirements-lock.txt"; then log "installed set equals requirements-lock.txt"; else fail "installed set differs from requirements-lock.txt"; fi

"$work/venv/bin/python" -c 'import torch; print("torch", torch.__version__, "cuda_available", torch.cuda.is_available(), "num_threads", torch.get_num_threads())' > "$out/device-check.txt" 2>&1 || fail "device check"
grep -q "cuda_available False" "$out/device-check.txt" || fail "CUDA is visible; refusing to run"

hf=$work/venv/bin/hf
"$hf" download vidore/colpali-v1.3 > "$out/hf-download-adapter.log" 2>&1 || fail "adapter download"
"$hf" download vidore/colpaligemma-3b-pt-448-base > "$out/hf-download-base.log" 2>&1 || fail "base download"
"$hf" download --repo-type dataset vidore/tabfquad_test_subsampled --revision "$DATASET_REVISION" > "$out/hf-download-dataset.log" 2>&1 || fail "dataset download"
adapter_main=$(cat "$HF_HOME/hub/models--vidore--colpali-v1.3/refs/main")
base_main=$(cat "$HF_HOME/hub/models--vidore--colpaligemma-3b-pt-448-base/refs/main")
log "resolved main: adapter=$adapter_main base=$base_main"
[ "$adapter_main" = "$COLPALI_REVISION" ] || fail "adapter main moved from the pinned revision"
[ "$base_main" = "$BASE_REVISION" ] || fail "base main moved from the pinned revision"

snapshot="$HF_HOME/hub/datasets--vidore--tabfquad_test_subsampled/snapshots/$DATASET_REVISION"
"$work/venv/bin/python" "$here/build_slice.py" "$snapshot" "$work/slice" "$here/slice-expected.json" > "$out/slice-summary.json" 2> "$out/slice-build.log" || fail "slice does not match the original run's input"

run_cli() {
  name=$1; shift
  log "$name: load before: $(cut -d' ' -f1-3 /proc/loadavg)"
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 /usr/bin/time -v -o "$out/$name.time.txt" \
    "$work/venv/bin/vidore-benchmark" --log info evaluate-retriever "$@" \
    --dataset-name "$work/slice" --dataset-format qa --split test \
    --batch-query 4 --batch-passage 4 --batch-score 4 --output-dir "$work/out-$name" > "$out/$name.log" 2>&1
  status=$?
  log "$name: exit=$status; load after: $(cut -d' ' -f1-3 /proc/loadavg)"
  cp "$work/out-$name"/*.json "$out/" 2>/dev/null
  return $status
}

run_cli colpali --model-class colpali --model-name vidore/colpali-v1.3
colpali_status=$?
run_cli dummy --model-class dummy_vision_retriever
dummy_status=$?
log "done: colpali_exit=$colpali_status dummy_exit=$dummy_status"
[ "$colpali_status" -eq 0 ] && [ "$dummy_status" -eq 0 ]
