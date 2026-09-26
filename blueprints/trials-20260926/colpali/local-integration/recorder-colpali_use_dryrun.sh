#!/bin/sh
set -x
CMD1="<scratch>/trial-colpali/.venv-combined/bin/vidore-benchmark evaluate-retriever --model-class colpali --model-name vidore/colpali-v1.3 --dataset-name <scratch>/trial-colpali/local-tabfquad-subset --dataset-format qa --split test --batch-query 4 --batch-passage 4 --batch-score 4 --output-dir <scratch>/trial-colpali/outputs-small"
CMD2="<scratch>/trial-colpali/.venv-combined/bin/vidore-benchmark evaluate-retriever --model-class dummy_vision_retriever --dataset-name <scratch>/trial-colpali/local-tabfquad-subset --dataset-format qa --split test --batch-query 4 --batch-passage 4 --batch-score 4 --output-dir <scratch>/trial-colpali/outputs-control-small"
echo "=== START $(date -u +%FT%TZ) ==="
T0=$(date +%s)
sh -c "$CMD1"
EC1=$?
T1=$(date +%s)
echo "CMD1_EXIT=$EC1 CMD1_SECONDS=$((T1-T0))"
sh -c "$CMD2"
EC2=$?
T2=$(date +%s)
echo "CMD2_EXIT=$EC2 CMD2_SECONDS=$((T2-T1))"
echo "=== END $(date -u +%FT%TZ) ==="
exit $((EC1 == 0 && EC2 == 0 ? 0 : 1))
