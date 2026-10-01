#!/bin/bash
set -x
SCRATCH=<scratch>/trial-colpali
export HF_HOME="$SCRATCH/hf-cache"
export HF_HUB_DISABLE_TELEMETRY=1
export DO_NOT_TRACK=1
export CUDA_VISIBLE_DEVICES=""
export MCP_AUTO_OPEN_ENABLED=false
cd "$SCRATCH"
time "$SCRATCH/.venv-combined/bin/vidore-benchmark" evaluate-retriever \
  --model-class dummy_vision_retriever \
  --dataset-name vidore/tabfquad_test_subsampled \
  --dataset-format qa \
  --split test \
  --batch-query 4 \
  --batch-passage 4 \
  --batch-score 4 \
  --output-dir "$SCRATCH/outputs-control"
echo "EVAL_EXIT=$?"
