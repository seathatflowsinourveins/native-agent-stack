# ARB trace2code: exact-release replay

This is an actual offline replay of the complete **101-case `v2_trace2code`**
release using Agent Retrieval Bench's unmodified lexical and BM25 evaluators.
It is one positive-only failure-trace task, not an evaluation of installed
QMD, rg, SocratiCode, an embedding model, or an agent's repair success.

| Native ARB ranker | Samples | Skipped | Recall@5 | Recall@10 | Recall@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| Lexical | 101 | 0 | 0.343234 | 0.481848 | 0.696370 | 0.207453 |
| BM25 | 101 | 0 | 0.222772 | 0.321782 | 0.493399 | 0.163848 |

Recall is the arithmetic mean of each sample's fraction of gold file paths
retrieved by the cutoff. It is **not** the fraction of solved cases or hit@k.
MRR uses the first exact gold-file rank across the **full file ranking**, not
only its first twenty files. There are 80 cases with one gold file, 16 with two,
and five with three, for 127 gold-file references. File ranks deduplicate native
chunk rankings by first occurrence of each case-sensitive repository path.

The seven repository counts are caddy 7, clap 1, etcd 4, gin 56, click 26,
pytest 1 and tokio 6. Gin and Click together contribute 82/101 cases. No
repository balancing, confidence interval, significance test, parameter tuning,
or claim of general superiority is made. Per-repository raw means and paired
differences are retained in [metrics.json](metrics.json).

## Pins, algorithms and licensing

- Evaluator: [`v0.2.1`, commit `b487f3866cc13dd971819cb902517a6a50282404`](https://github.com/eyuansu62/agent-retrieval-bench/tree/b487f3866cc13dd971819cb902517a6a50282404).
- Dataset: [revision `5901e1ee3aff048290db72edf9c63bc498b79ea3`](https://huggingface.co/datasets/eyuansu71/agent_retrieval_bench/tree/5901e1ee3aff048290db72edf9c63bc498b79ea3), release `v2_trace2code`.
- Archive SHA-256: `19b252e8cfff42107fedc74005dbb6972f2970af33651ce0c1571546819e41c4`.
- The archive contains 98 frozen base-commit corpora, 24,883 snapshot file
  records and 356,074 snapshot chunk records. Repeated files across snapshots
  are counted repeatedly. Its compressed size is 39,295,446 bytes and its
  extracted file bytes total 300,175,960.
- The evaluator has no mandatory third-party runtime dependency. This run used
  a separate stdlib-only Python 3.14.7 environment on macOS arm64.

ARB lexical scoring combines token document frequency and query frequency with
full-path (+25), basename (+8) and symbol (+5) substring bonuses, then divides
by the square root of the number of unique chunk tokens. BM25 retains the
upstream `k1=1.5`, `b=0.75` and query-frequency weighting. Both tokenize camel-case
split, lowercase ASCII alphanumeric text containing path, symbol, kind and
content. Ties use path then chunk identifier. Neither implementation is an
rg or QMD baseline. [Pinned scoring source](https://github.com/eyuansu62/agent-retrieval-bench/blob/b487f3866cc13dd971819cb902517a6a50282404/src/agent_retrieval_bench/baseline.py).

The evaluator, benchmark metadata and reports are MIT licensed. Corpus content
retains the licenses of its original repositories; no corpus or query text is
redistributed here. See [upstream data licensing](https://github.com/eyuansu62/agent-retrieval-bench/blob/b487f3866cc13dd971819cb902517a6a50282404/DATA_LICENSE.md).

The first run used the catalog's retained source snapshot `07014c986f3deadb1548c62b32c0ffbe6a81465d`,
which declares version 0.2.1 but is not the release-tag commit. After verifying
the tag discrepancy, both rankers were rerun at the exact release commit.
The complete evaluator source tree is byte-identical at the two commits
(`0fd0466fb3e24c40c0bdf9468872bea9c9a61fa1`); the differences are documentation
and citation changes. Both executions have identical per-sample detail bytes
and metrics. The initial observation is preserved in the receipt's provenance,
not silently relabeled as an exact-tag run.

## Retained evidence and limits

[receipt.json](receipt.json) records source/data pins, parameters, environment,
exit codes, observations, checks and artifact hashes.
[input-files.json](input-files.json) hashes every extracted input file;
[source-files.json](source-files.json) hashes evaluator code and license sources.
[paired-samples.json](paired-samples.json) retains only public sample identifiers,
repository/base commits, gold paths and each ranker's exact gold ranks, allowing
independent Recall/MRR recomputation without republishing queries or code chunks.

The two `upstream-*-summary.json` files preserve native output unchanged.
**Their legacy `@8k` fields are not tokenizer-measured BCY or token savings.**
The pinned baseline uses Python `len(text)` characters, and accepts an oversized
first chunk, so it does not even enforce a strict 8,000-character cap in that
case. Those legacy fields are excluded from headline metrics. No abstention,
answer correctness, span quality, model inference, provider usage or billing
claim follows from this positive-only file-retrieval experiment.

The exact-release runs were sequential, single warm observations after the
earlier source-identical run. Timing is informational; it is not a controlled
latency benchmark. Both exact-release commands exit 0; schema validation finds
101 valid samples and zero invalid samples. Fifteen upstream corpus/baseline
tests pass. No runtime/default adoption is implied.

## Replay the upstream evaluator

Use a new empty directory and an existing Python 3.14.7 executable as
`ARB_PYTHON`. This recipe creates only that directory's environment/data; it
does not install a global tool, register a service or contact a model provider.

```sh
git clone https://github.com/eyuansu62/agent-retrieval-bench.git upstream
git -C upstream checkout --detach b487f3866cc13dd971819cb902517a6a50282404
"$ARB_PYTHON" -m venv --without-pip runtime
mkdir data results
curl --fail --location --max-time 120 \
  --output agent_retrieval_bench_v2_trace2code.tar.zst \
  https://huggingface.co/datasets/eyuansu71/agent_retrieval_bench/resolve/5901e1ee3aff048290db72edf9c63bc498b79ea3/releases/v2_trace2code/agent_retrieval_bench_v2_trace2code.tar.zst
runtime/bin/python - <<'PY'
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
PY
PYTHONPATH=upstream/src runtime/bin/python -m agent_retrieval_bench.cli \
  validate data/benchmark/v2_trace2code/samples.jsonl
for ranker in lexical bm25; do
  PYTHONPATH=upstream/src runtime/bin/python -m agent_retrieval_bench.cli \
    eval-baseline data/benchmark/v2_trace2code/samples.jsonl \
    --corpus data/corpus/v2_trace2code --ranker "$ranker" \
    --candidate-filter all_files --no-keep-list --no-progress \
    --out "results/$ranker-summary.json" \
    --details "results/$ranker-details.jsonl"
done
```

Run from the directory containing `data`: the released manifest's chunk paths
are relative to that directory. Compare metrics and detail hashes, not elapsed
time fields. Do not substitute `--dry-run`, an answer-only candidate list, or a
sample limit for this complete released-subset replay.
