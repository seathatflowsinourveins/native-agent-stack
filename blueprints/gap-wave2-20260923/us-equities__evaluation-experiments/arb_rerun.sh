#!/usr/bin/env bash
# Gap 4: rerun ARB v0.2.1 trace2code lexical/BM25 on this host (recipe from
# blueprints/convergence-practice/arb-trace2code/README.md). Usage: arb_rerun.sh ARB_DIR OUT
set -uo pipefail
A=$1; OUT=$2; mkdir -p "$OUT"
C=${HOME}/.cache/gap-wave2-20260923/evaluation-experiments
export UV_CACHE_DIR=$C/uv-cache UV_PYTHON_INSTALL_DIR=$C/pythons UV_NO_CONFIG=1
cd "$A"
test "$(git -C upstream rev-parse HEAD)" = b487f3866cc13dd971819cb902517a6a50282404 || exit 2
git -C upstream status --porcelain > "$OUT/upstream-status.txt"
[ -x runtime/bin/python ] || uv venv -q --python 3.14.7 --no-seed runtime
runtime/bin/python -c 'import sys,platform;print(sys.version.split()[0], platform.system(), platform.machine())' > "$OUT/runtime.txt"
rm -rf data results; mkdir data results
runtime/bin/python - <<'PY' > "$OUT/extract.txt" 2>&1
import hashlib
import tarfile
from pathlib import Path, PurePosixPath

path = Path("agent_retrieval_bench_v2_trace2code.tar.zst")
with path.open("rb") as handle:
    actual = hashlib.file_digest(handle, "sha256").hexdigest()
if actual != "19b252e8cfff42107fedc74005dbb6972f2970af33651ce0c1571546819e41c4":
    raise ValueError("Archive checksum mismatch")
with tarfile.open(path, "r:zst") as archive:
    members = archive.getmembers()
    if len(members) != 120 or sum(item.size for item in members) != 300175960:
        raise ValueError("Archive size/member inventory mismatch")
    for item in members:
        name = PurePosixPath(item.name)
        if name.is_absolute() or ".." in name.parts or not (item.isfile() or item.isdir()):
            raise ValueError("Unsupported archive member")
    archive.extractall("data", members=members, filter="data")
print("archive ok", actual, len(members))
PY
echo "extract exit=$?" >> "$OUT/extract.txt"
PYTHONPATH=upstream/src runtime/bin/python -m agent_retrieval_bench.cli validate data/benchmark/v2_trace2code/samples.jsonl > "$OUT/validate.json" 2> "$OUT/validate.stderr.txt"
echo "validate exit=$?" > "$OUT/exit-codes.txt"
for ranker in lexical bm25; do
  s=$(date +%s.%N)
  PYTHONPATH=upstream/src runtime/bin/python -m agent_retrieval_bench.cli \
    eval-baseline data/benchmark/v2_trace2code/samples.jsonl \
    --corpus data/corpus/v2_trace2code --ranker "$ranker" \
    --candidate-filter all_files --no-keep-list --no-progress \
    --out "results/$ranker-summary.json" \
    --details "results/$ranker-details.jsonl" > "$OUT/$ranker-stdout.txt" 2> "$OUT/$ranker-stderr.txt"
  echo "$ranker exit=$? wall=$(echo "$(date +%s.%N) - $s" | bc)" >> "$OUT/exit-codes.txt"
done
[ -x pytest-venv/bin/python ] || { uv venv -q --python 3.14.7 pytest-venv && uv pip install -q --python pytest-venv/bin/python 'pytest==9.1.1'; }
( cd upstream && PYTHONPATH=src ../pytest-venv/bin/python -m pytest -q tests/test_corpus_baseline.py ) > "$OUT/upstream-tests.txt" 2>&1
echo "pytest exit=$?" >> "$OUT/exit-codes.txt"
sha256sum results/* > "$OUT/result-hashes.txt"
cp results/*-summary.json "$OUT/"
