# Retrieval quality v2: BM25 vs. hybrid -- measured comparison, September 25, 2026

QMD **2.8.3** evaluated all 30 preregistered held-out queries against both arms over the same frozen 33-document index. Arm A (BM25) scored nDCG@10=0.2228; Arm B (hybrid, CPU) scored nDCG@10=0.7139. **Hybrid (Arm B) selected over BM25** (gain=0.4912, threshold=0.05, 95% bootstrap CI=[0.3673, 0.6185]).

The [preregistration](PREREGISTRATION.md) and [30 held-out queries](queries.json) (sha256 `4d0a0eaf0f6fc48b899f6139e7e98a6c1edf4798b1f17ddfbf5ec3e1cc6c5c7a`) were sealed by an independent author before either arm ran; this script only re-verified that seal, it did not author or edit either file. All 33 corpus files were re-extracted from git commit `3e4054d02eac06ae8ac995c5e96fe8a75c0824c8` and every one verified against its pinned sha256 before indexing (see [results-20260925.json](results-20260925.json)'s `corpus_staging` array).

| Metric (mean over 30 queries) | Arm A -- BM25 (`search`) | Arm B -- hybrid (`query`, CPU) |
| --- | ---: | ---: |
| nDCG@10 | 0.2228 | 0.7139 |
| recall@5 (grade-2 files) | 0.2667 | 0.8500 |
| MRR | 0.2667 | 0.7283 |
| Queries erroring/timing out | 0/30 | 0/30 |

recall@5 and MRR are secondary, non-gating evidence per PREREGISTRATION.md's Decision rule; only nDCG@10's mean gain and bootstrap CI decide between arms.

## Decision

**Hybrid (Arm B) selected over BM25.** Both preregistered conditions held.

- Condition 1 (gain &ge; 0.05): True (gain=0.4912)
- Condition 2 (paired bootstrap 95% CI excludes 0): True (CI=[0.3673, 0.6185], 10000 resamples, seed=20260925)

## Model provenance (Arm B)

All three of QMD's default hybrid-mode models, pulled into the scratch HOME's own model cache:

| Role | HF repository | Revision (repo HEAD at pull time) | File | sha256 | Size |
| --- | --- | --- | --- | --- | ---: |
| embed | [ggml-org/embeddinggemma-300M-GGUF](https://huggingface.co/ggml-org/embeddinggemma-300M-GGUF) | `0f741b5a6585bd53aeb15cd1372c56f2a0f65e12` | `embeddinggemma-300M-Q8_0.gguf` | `b5ce9d77a3fc4b3b39ccb5643c36777911cc4eb46a66962eadfa3f5f60490d63` | 318.1 MB |
| generate | [tobil/qmd-query-expansion-1.7B-gguf](https://huggingface.co/tobil/qmd-query-expansion-1.7B-gguf) | `7816de0b72572c6c860ca1eddf97ba9e7fb8cc65` | `qmd-query-expansion-1.7B-q4_k_m.gguf` | `000dfb1c06efa6a049e9f64ba921c3740e2454f62abab6fa10e77bd30bb2bcc0` | 1.2 GB |
| rerank | [ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF](https://huggingface.co/ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF) | `a02f48bb4f057028298c21fa033da2b30d7742d5` | `qwen3-reranker-0.6b-q8_0.gguf` | `22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48` | 609.5 MB |

QMD adaptively skips the query-expansion (generate) model per-query when its own BM25 signal is already strong (observed directly in this run's stderr as "Strong BM25 signal (...) -- skipping expansion"); the table above lists every model `qmd pull` fetched up front, not a claim that all three ran on every one of the 30 queries.

## Known limitations

- **Arm A is QMD's lexical `search` command, not BM25 in general.** It returned no candidates
  at all for 22 of the 30 queries: every natural-language query, every paraphrased or indirect
  query, and 2 of the 10 keyword queries. Only the 8 keyword queries made of short literal
  technical tokens retrieved anything. The large nDCG@10 gain therefore measures QMD's hybrid
  `query` against QMD's lexical `search` as research workers would call them. It does not
  measure hybrid against a tuned BM25 with a disjunctive or relaxed query. The preregistered
  decision holds as stated. A fairer lexical baseline (for example an OR-query BM25 over the
  same index) is a named follow-up, not a result of this run.
- `run.py` runs its one `qmd --version` sanity check before the scratch HOME/XDG
  redirection, under the ambient environment. That call reads no index, cache or model. It is
  left as run so the code matches these results, and the next revision should pass the scratch
  environment to it.
- 30 queries against 33 short documents is a small-sample comparison; the paired bootstrap CI is the safeguard against reading noise as a real gain, not a substitute for a larger corpus.
- This protocol measures retrieval quality only (nDCG@10, recall@5, MRR); it does not measure end-to-end answer quality, latency at scale, or provider-token cost.
- The query author's relevance judgments reflect one reader's understanding of "directly answers" vs. "partially relevant", not adjudicated multi-rater agreement.
- Arm B's models were pulled and run once, forced onto CPU on a shared host; a GPU run or a different host's CPU could show different absolute latency (not accuracy, since the same GGUF weights and inference code drive both).
- QMD adaptively skips its query-expansion model per-query when BM25 signal is already strong; not every Arm B query necessarily exercised all three pulled models.

## Durations

| Phase | Duration |
| --- | ---: |
| seal_verify | 0.0s |
| corpus_staging | 0.1s |
| index_build | 1.1s |
| arm_a | 4.6s |
| arm_b_pull | 3.0s |
| arm_b_embed | 45.0s |
| arm_b | 1389.3s |
| total_wall_clock | 1443.3s |

## Exact commands

Run against a scratch `$SCRATCH_HOME` with `HOME`/`XDG_*` pointed into it and
`QMD_FORCE_CPU=1` set, never the host's shared `~/.cache/qmd`:

```sh
python3 blueprints/retrieval-quality-v2/run.py \
  --repo "$STACK_REPO" --scratch-home "$SCRATCH_HOME"

# what run.py runs under the hood, per query arm:
qmd --index retrieval-quality-v2 collection add "$STAGE/blueprints/us-equities" \
  --name rqv2-foundation --mask '**/*.md'
qmd --index retrieval-quality-v2 collection add "$STAGE/catalogs/us-equities" \
  --name rqv2-catalog --mask '**/*.md'
qmd --index retrieval-quality-v2 collection add "$STAGE/observability" \
  --name rqv2-observability --mask '**/*.md'
qmd --index retrieval-quality-v2 update
qmd --index retrieval-quality-v2 search "<query>" -n 10 --format json   # Arm A
qmd pull   # Arm B only: default embed/generate/rerank models, CPU-forced
qmd --index retrieval-quality-v2 embed                                   # Arm B only
qmd --index retrieval-quality-v2 query "<query>" -n 10 --format json    # Arm B
```

## Reviewed upstream implementation

QMD `qmd 2.8.3 (facd35e)`, installed from `@tobilu/qmd`. The `file` field's `qmd://<collection>/<relative-path>?index=<name>` shape and the `docid` = first 6 hex chars of the document's content sha256 were confirmed directly against this run's own built index (`dist/cli/formatter.js`'s `searchResultsToJson`, `dist/cli/formatter.js`'s `getDocid`), and the three default hybrid-mode model URIs against `dist/llm.js`'s `DEFAULT_EMBED_MODEL` / `DEFAULT_GENERATE_MODEL` / `DEFAULT_RERANK_MODEL` and this run's own `qmd pull` output, not asserted from memory.

This measures retrieval quality only (nDCG@10, recall@5, MRR) over 33 short documents and 30 queries. It does not measure end-to-end answer quality, general-corpus latency at scale, or provider-token cost; see PREREGISTRATION.md's own Known limitations for the full list, reproduced above.
