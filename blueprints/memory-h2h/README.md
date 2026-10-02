# Memory systems head to head

This source harness compares what each memory system stores and retrieves on
the official **cleaned LongMemEval S** questions. BM25 ranks whole sessions;
`none` supplies an empty history. System installation and live acceptance belong
to the coordinator. The core uses Python 3.13's standard library; adapters may
use `httpx` or a documented upstream client.

For each question, reset an isolated namespace, ingest both conversation roles
in timestamp order, recall the top k native results, feed their text to one common
answerer, and grade with the official LongMemEval judge. Dates stay unchanged.
Gold `has_answer` annotations are removed. Evidence-marked dataset session IDs
are replaced with opaque IDs before ingestion and mapped back only for scoring.

Every arm shares the subset, ingestion order, k, answer/judge routes, direct-reader
prompt, output limits, context budget and judge prompts/parser. The memory system's
store, ingestion/recall LLM calls, retrieval format and documented defaults differ.
There is no per-arm tuning or extra context extraction. Upstream CoN reading is
an upstream benchmark setting, not applied. BM25 includes both roles and uses
lowercase whitespace tokens; the official retrieval baseline indexes users only.

From the worktree root, with the caller's local dataset and existing model routes:

```sh
PYTHONPATH=blueprints/memory-h2h python3 -B -m h2h.run --list-arms
PYTHONPATH=blueprints/memory-h2h python3 -B -m h2h.run --arm bm25 --data /path/longmemeval_s_cleaned.json --n 60 --seed 20261002 --k 10 --answer-model ANSWER_ID --judge-model JUDGE_ID --base-url https://MODEL_ENDPOINT/v1 --out /path/results
PYTHONPATH=blueprints/memory-h2h python3 -B -m unittest discover -s blueprints/memory-h2h/tests -p 'test_core.py'
```

The key is read from `H2H_API_KEY` at request time; `--api-key-env` selects another
variable. No key is written to disk. `--memory-model` defaults to the answer model;
`--embed-model` supplies the embedding route. Each has optional `--*-base-url` and
`--*-api-key-env` flags; the judge also supports those overrides. Use models that
accept LongMemEval's `temperature=0`, `n=1`, and legacy `max_tokens` parameters.

The runner checks the dataset SHA256 in `pins.json`; `--allow-custom-data` explicitly
marks a custom fixture. n must divide evenly across the six question types, and
every type must have enough questions. Sampling is seeded, input-order independent,
and interleaved across types. `--limit N` completes at most N new questions per call.

`--out/ARM/` holds `run.json`, `records.jsonl`, `hypotheses.jsonl`, `summary.json`,
`pending.json`, and the adapter's private `system/` directory. Completed IDs are
skipped. An answer is checkpointed before judging and a judgment before appending;
resume also checks that dataset, routes, settings and adapter version match.
A torn final JSONL fragment is preserved as `records.partial`. Run one writer per
arm/output directory. The hypothesis JSONL is accepted by the official evaluator.

The prompt budget uses UTF-8 bytes plus 32 framing units as a conservative bound
for byte-BPE models, truncating only retrieved text. This is not an exact tokenizer
for arbitrary model servers; reported prompt usage exceeding the cap stops scoring.
All returned answer/judge usage, including nested counters, stays in the records;
failed attempts and pending paid calls remain in partial summaries. Missing usage stays unknown.
The fixed adapter interface exposes ingestion call counts, but no model-token usage.

Recall uses only reported IDs, deduplicated across the first k results. Nonempty
results without IDs and abstentions are unscored; mixed provenance gives a labeled
lower bound. Accuracy and paired differences use 95% percentile bootstrap intervals
with 10,000 resamples and seed 20261002. Pairing requires identical question IDs;
Holm adjusts supplied p-values without manufacturing tests from intervals.

Add `h2h/adapters/NAME.py` exposing `build() -> MemoryAdapter`, its source-cited
`NAME.md`, and offline `tests/test_adapter_NAME.py`. Keep imports free of network
effects and all state private to the instance/workdir. `start` uses the documented
launch route and `H2H_PORT`; `reset` must make earlier namespaces unreachable.
Document pins, ingestion/recall parameters, defaults, route support and limitations.

Sources: [cleaned dataset/schema](https://github.com/xiaowu0162/LongMemEval/blob/9e0b455f4ef0e2ab8f2e582289761153549043fc/README.md#L36), [answer prompt/request](https://github.com/xiaowu0162/LongMemEval/blob/9e0b455f4ef0e2ab8f2e582289761153549043fc/src/generation/run_generation.py#L53), [official judge](https://github.com/xiaowu0162/LongMemEval/blob/9e0b455f4ef0e2ab8f2e582289761153549043fc/src/evaluation/evaluate_qa.py#L24).
[Vectorize reference](https://github.com/vectorize-io/agent-memory-benchmark/blob/f618ed7b1f0eb9cad7b42e876f91a42f0eadb150/src/memory_bench/memory/bm25.py#L17), [BM25 0.2.2 scoring](https://github.com/dorianbrown/rank_bm25/blob/2550648efdbdcc5ebadbc8e5c8b26f5eb94b2b36/rank_bm25.py#L78), [paired bootstrap](https://github.com/scipy/scipy/blob/e4e854eaa8f18d807cd3496028e257e36caa93cc/scipy/stats/_resampling.py#L363), [Holm](https://github.com/statsmodels/statsmodels/blob/278ff9950636cdd4939b4055e339a8e681d79cab/statsmodels/stats/multitest.py#L233).
`pins.json` contains exact commits, line citations, immutable download/hash metadata,
and adaptations. Tests are authored synthetic integration checks; no dataset was
downloaded, memory system installed, service queried, or live model evaluated.
