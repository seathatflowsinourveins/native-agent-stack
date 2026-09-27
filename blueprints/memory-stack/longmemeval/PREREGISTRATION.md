# Preregistration: durable-memory retrieval on LongMemEval-S (cleaned)

Frozen 2026-09-24, before any system arm runs. Changes after this point are
recorded as dated amendments below, never edited in place.

## Question

Does any memory system retrieve the evidence sessions of a question better than
the installed ai-memory configuration? This is the owed comparison of the
native-agent-stack `durable-memory` layer (verdict "keep but compare"; open gap:
"No matched semantic-recall or usefulness benchmark between ai-memory and any
alternative exists").

## Benchmark and code (pinned)

- Dataset: `longmemeval_s_cleaned.json` from `xiaowu0162/longmemeval-cleaned`,
  sha256 `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`
  (500 questions, ~115K tokens of history each).
- Official code: `xiaowu0162/LongMemEval` at `9e0b455f4ef0e2ab8f2e582289761153549043fc`.
  Metrics come from its `src/retrieval/eval_utils.py::evaluate_retrieval`; corpus
  ids and gold labels from `run_retrieval.py::process_item_flat_index` at
  session granularity; the summary uses `run_retrieval.py`'s exclusions
  (abstention `_abs` questions and questions without user-side evidence) and the
  official `src/evaluation/print_retrieval_metrics.py`.
- Environment deviation: Python 3.11 instead of 3.9; the pinned package versions
  otherwise follow `requirements-full.txt` (CPU torch 2.3.1 on macOS arm64).

## Metrics

- Primary: session-level `recall_all@5` (the official "Recall@5": every evidence
  session in the top 5).
- Secondary: `ndcg_any@5`, `recall_all@10`, `ndcg_any@10`, and `recall_any@5`
  (the "hit@5" / "R@5" that vendors publish, reported only for comparability).
- Also recorded: per-question query latency, ingestion wall time, failures.

## Arms

| ID | Arm | Notes |
|---|---|---|
| A0 | Official `flat-bm25`, session granularity | Official runner, user-turn corpus |
| A1 | Official `oracle` | Sanity check; must score 1.0 |
| B1 | BM25 over full sessions (user and assistant) | Same tokenizer as A0 |
| B2 | Dense: Qwen3-Embedding-4B (Ollama), user-turn corpus | Qwen3 query instruction |
| C1 | ai-memory 2.5-pre `19b6429`, zero-LLM (FTS + entity + graph) | Production hook ingest |
| C2 | ai-memory, local all-MiniLM-L6-v2 (its 2.x default) | Production hook ingest |
| C3 | ai-memory, Qwen3-Embedding-4B + production query prefix | **Incumbent (production config)** |
| C4 | C3 plus the LLM reranker (qwen3.5-9b-64k, concurrency 1) | Run if time allows |
| D1 | agentmemory v0.9.29, keyless (BM25) | `remember` + `smart-search`, as its own harness |
| D2 | agentmemory v0.9.29, local all-MiniLM-L6-v2 hybrid | Its documented free mode |

Hindsight needs an LLM for every ingested session; it moves to the QA tier
(sampled) and is not part of this retrieval tier.

## Protocol

1. Every question gets a fresh store in its own server process (fresh data
   directory, empty-store check before ingest, destroyed afterwards).
2. Each system receives every haystack session in chronological order with its
   date. Session identifiers are replaced by `sha256(question_id + session_id)[:16]`,
   so no identifier contains "answer". Gold fields (`answer`,
   `answer_session_ids`, `has_answer`) are never passed to a system.
3. ai-memory ingests through its production hook path (`POST /hook/batch`:
   session-start, user-prompt-submit, stop with the assistant excerpt,
   session-end), exactly as its own harness does, including the dated turn
   prefix and the 2 KB excerpt cap. agentmemory ingests each full session through
   `remember`, as its own harness does.
4. The query is the question text. Each system's results are mapped to distinct
   sessions in rank order; results that map to no session are skipped; the
   ranking is truncated at 50.
5. Metrics are computed by the official functions on the official corpus ids.

## Statistics and decision rule

- Paired comparisons against C3 (incumbent) and against A0 (official baseline).
- Exact McNemar test on per-question `recall_all@5`, Holm-corrected across all
  pairs tested against C3.
- Paired bootstrap 95% CIs (10,000 resamples, seed 20260924) for the mean
  difference in `recall_all@5` and `ndcg_any@5`.
- An alternative **beats** the incumbent only if its Holm-adjusted McNemar
  p < 0.05, the bootstrap CI of the `recall_all@5` difference excludes 0, and the
  point estimate is at least +5 percentage points. Otherwise the incumbent stays.
- A configuration of ai-memory that beats C3 changes the production configuration,
  not the layer winner.

## Known limits (stated before results)

- Retrieval is not answer quality; the QA tier (sampled, local or Codex judge,
  labelled as non-official) is a separate record.
- LongMemEval is chat-assistant memory, not coding-agent sessions. Independent
  work (VibeMemBench, 2026-09-20) found automatic memory at or below "memory off"
  on repository tasks; no result here addresses that question.
- Systems ingest differently by design (ai-memory caps captured excerpts at 2 KB
  and embeds session pages; agentmemory stores whole sessions). The benchmark
  measures each system as shipped, not an idealised retriever.

## Amendments

### 2026-09-24 A1–A7 (before any system arm ran)

Source: an independent GPT-6 Astra review of this document against the
official code and data (`prereg-review-codex.md`), plus a data check. All
findings were verified against the code and the dataset and accepted.

- **A1. One frozen denominator.** `eligible-manifest.json` (sha256
  `871f5da108b2901204aa01315b87d91cdee8d4e61dea96f4499916cbc19a05b7`) fixes the
  question sets. The official track has 419 questions (non-abstention, with
  user-side evidence), matching `run_retrieval.py`'s summary. The official
  `print_retrieval_metrics.py` averages 470, including 51 questions whose
  official gold set is empty and which therefore score `recall_all = 1` for any
  ranking. It is reported for reference only. Every summary, paired test and
  interval uses the manifest.
- **A2. Two tracks.**
  - **Official track (419):** the official labels. Assistant-side evidence is
    relabelled `noans`, exactly as in the official corpus builder.
  - **Full-session track (470):** gold is `answer_session_ids`, including
    assistant-side evidence, scored with the same official `evaluate_retrieval`
    function on the raw session ids.
  - **Decision rule, now two-track.** An alternative beats the incumbent only if
    it meets the rule on the full-session track and is not worse than the
    incumbent on the official track (point estimate ≥ −2 pp). A split result
    keeps the incumbent.
- **A3. Dates for every competitive arm.** Every competitive arm gets
  `[session date: <haystack_date>]` in its session text: B1, B2 and D* as a
  leading line, and C* through ai-memory's own per-turn prefix. A0 stays the
  untouched official reference.
- **A4. Failures.**
  - Limits per question: 30 min to ingest and 120 s per query.
  - Up to two retries with a fresh store, for infrastructure errors only (the
    server fails to start, or the connection is refused or reset).
  - A question that still fails scores as an empty ranking for that arm.
  - Every arm must cover every manifest question. An environment-wide fault (for
    example, the embedding server down) triggers a full rerun of the arm, never a
    selective one.
- **A5. Clustered statistics.**
  - Questions are clustered by shared evidence-session content (union-find over
    sha256 of evidence sessions). On the official track, 12 pairs share
    byte-identical evidence.
  - Confidence intervals: cluster bootstrap, 10,000 resamples, seed 20260924.
  - Significance: a cluster-level paired sign-flip randomization test (100,000
    draws, seed 20260924) replaces the per-question McNemar test, with Holm
    correction over the comparisons against C3.
- **A6. Oracle ceilings.** No top-five ranking can hold six evidence sessions,
  so the oracle's `recall_all@5` ceiling is 416/419 (0.99284) on the official
  track and 467/470 on the full-session track. The A1 oracle must reach these
  ceilings, and must reach 1.0 on `recall_any@k` for every k.
- **A7. Repeated sessions.** Thirteen questions repeat a distractor session
  (identical content, a different date, never gold). Each occurrence is ingested
  as its own session. Hashed ids include the occurrence index, and results map
  back to the haystack position.

### 2026-09-24 A8 (added before these arms ran)

- **C5** is ai-memory with Qwen3-Embedding-8B (4096 dimensions). **C6** is ai-memory with
  Qwen3-Embedding-0.6B (1024 dimensions).
- Both keep C3's production query prefix.
- They are configuration alternatives to C3, not layer candidates. They are analyzed only as
  paired comparisons with C3 under the same decision rule, and can change the production embedder,
  not the layer winner.

### 2026-09-24 A9 (added before this arm ran)

- **D3** is agentmemory v0.9.29 with Qwen3-Embedding-4B through its OpenAI-compatible embedding
  provider (Ollama, 2560 dimensions).
- It matches C3's embedder, so the D3-versus-C3 comparison isolates system design from the choice
  of embedding model.
- agentmemory has no query-instruction prefix, so D3 runs without one, as shipped.
- It is analyzed as a layer candidate under the A2 rule.

### 2026-09-24 A10: harness corrections from an independent code review

Before any C arm with vectors ran, a GPT-6 Astra review of `lme_harness.py` and `lme_summarize.py`
found 8 defects (`harness-review-codex.md`). All were verified and fixed. `lme_harness.v1.py`
keeps the first version.

- **Retrieval depth.** Every ai-memory arm now queries with limit 50, the registered depth; the
  first version used ai-memory's harness default of 10. The completed C1 run at limit 10 moves to
  `results-sensitivity/aimem-fts-limit10.jsonl` as a sensitivity record, and C1 reruns at limit 50.
- **Failure classes.** Embedding failures and degraded retrieval are now env errors: ai-memory's
  degradation warnings and missing vectors, and agentmemory's `embed failed` log lines plus an
  embedding-service probe before and after each question. An env error invalidates the arm until
  it is rerun. Ingest (30 min) and query (120 s) now have monotonic budgets. HTTP 5xx now triggers
  a fresh-store retry of the whole question; the in-place retry is removed.
- **agentmemory isolation.** agentmemory arms hold a cross-process lock and refuse more than one
  worker.
- **Analysis.**
  - Clusters hash only conversation role and content, not gold annotations.
  - The Holm family is fixed: C4 joins only when complete, and a missing required arm counts as
    p = 1.
  - No decision is given until every required arm is complete, free of env errors, and both
    oracle checks pass.
  - The official oracle is scored only on the official track. A separate full-session oracle is
    built from `answer_session_ids`.
- **Arms that stay on the first version.** B2 (dense-qwen3) and D1 (am-keyless) were in progress
  on it. They differ only on failure paths: the query timeout, and the removed in-place retry. That
  retry is harmless if it never fired. Both arms are kept if they finish with zero errors, and
  D1's supersession events are explained by repeated sessions alone.

### 2026-09-24 A11: throughput changes for arms not yet started (user asked for full speed)

Nothing here changes a question's inputs, isolation, scoring or decision rule; it only changes
how fast arms that have not started yet can run.

- **Embedding server.** C3, C5, C6, D3 and C4 use a dedicated benchmark Ollama instance on
  port 11436 (`lme_harness.py` through `LME_EMBED_URL`). It runs the same Ollama 0.34.4 binary
  and model store with the same `qwen3-embedding` digests. It uses `OLLAMA_NUM_PARALLEL=8` and
  keeps production's `OLLAMA_CONTEXT_LENGTH=4096`, the guard against ollama#17878. Batched
  requests can change embeddings only at float-rounding level. B2 (dense-qwen3) finishes on the
  production instance it started on.
- **Parallel agentmemory.** D arms started from now on (D3; any D rerun) run up to 4 questions
  at once, each in its own slot. A slot follows agentmemory's documented multi-instance port
  scheme: REST anchor 3611 + 100·slot, streams +1, viewer +2, engine +46023, set through
  `III_REST_PORT`, `III_STREAM_PORT`, `III_ENGINE_URL` / `III_URL` and iii's
  `iii-worker-manager` port. Teardown kills only the slot's engine, its descendants and the
  holders of its ports. Every question still gets a fresh store. D1 and D2 ran one at a time on
  the default ports, and D2 finishes that way.
- **Worker counts.** The ai-memory Qwen3 arms run 6 questions at a time, each with its own
  server.
- **Unchanged.** C4 (the reranker) still runs last, alone on the LLM, because its hard 20 s
  rerank timeout is sensitive to load.

### 2026-09-24 A12: C4 reranker run (before C4 started)

- **Where it runs.** C4's reranker LLM (qwen3.5-9b-64k, reasoning effort low, production
  settings) runs on a dedicated parallel benchmark instance (`LME_LLM_URL`), with 3 questions at a
  time, each on its own ai-memory server. It starts only after every other GPU arm and the quant
  runs have finished.
- **Counted fallbacks.** ai-memory keeps the pre-rerank order when a rerank times out (hard 20 s
  limit), fails, or returns invalid scores, and logs each at WARN. The harness counts these per
  question (`rerank_timeouts`, `rerank_failures`, `rerank_invalid`). They are reported, not
  scored as errors: falling back is ai-memory's designed behaviour.
- **Rule.** If more than 5% of C4's queries fell back, C4 is reported as inconclusive for the
  reranker on/off decision rather than as a reranker effect. C4 stays an optional family member,
  and joins the Holm family only if complete.

### 2026-09-24 A13: one GPU workload at a time, and a byte-exact embedding cache (before C4, C5 and C6 started)

Nothing here changes a question's inputs, isolation, scoring, families or decision rule.

- **Measured bottleneck.** From 22:17 to 22:28 the benchmark embed server ran at 99% GPU device
  utilization and processed 700–1,470 prompt tokens/s. Its log shows one slot (`n_slots = 1`):
  Ollama ignored A11's `OLLAMA_NUM_PARALLEL=8` for the embedding model, so requests were embedded
  one at a time and A11's float-rounding caveat never applied. Sharing that server, C3 and D3
  finished 0.7 and 0.4 questions per minute. At those rates the remaining GPU arms needed more
  than a day.
- **Queue.** From 22:38, one GPU workload runs at a time: C3 → C4 → C6 → D3 → the quant runs
  (resumed) → the AIPerf matrix → C5. C3 goes first because every preregistered comparison is
  against it. C4 still runs alone on an otherwise idle GPU, as A12 requires; only its position
  moves.
- **Stop and resume.** C3 (31 of 470 rows) and D3 (12 of 470) were stopped at 22:38 and resume
  from their rows. The questions in flight (6 in C3, 4 in D3) had written nothing. They rerun
  from the start on fresh stores and do not count as infra retries. Both row files were
  validated: no duplicate or truncated rows, and 0 errors. Four orphaned ai-memory servers from
  an earlier run were stopped. They started at 19:18 and had no connections.
- **Byte-exact embedding cache.** From 22:38, all benchmark embedding traffic goes through
  `embed_cache_proxy.py` (port 11439, upstream 11436), set through `LME_EMBED_URL`.
  - The key is the SHA-256 of the method, path and raw request body.
  - A hit returns the upstream's stored 200 response bytes.
  - Other paths and non-200 responses pass through uncached.
  - The start-up self-test found a hit byte-identical to the stored response, and a direct
    recomputation identical to the proxied vector.

  The server reuses a slot's cached prompt prefix from the previous request (`cached n_tokens`
  in its log). A recomputation can therefore differ at float-rounding level, depending on what
  ran before. The cache fixes each request's vector at its first computation.

  C4 sends exactly C3's embedding requests (same binary, same ingestion and same embedder; only
  the reranker differs), so C4's embeddings come from C3's. An infra retry of a question reuses
  that question's embeddings. The proxy counts hits, misses and tokens in
  `cache/embed-proxy.sqlite.stats.json`.
- **Cache warm-up for C4.** C3's first 31 rows were written before the cache existed. Those 31
  questions rerun through the proxy, alongside C3, into `results-cachewarm/`, so C4 finds every
  embedding cached and runs on an idle GPU as A12 requires. The warm-up rows are never analysed.
  They serve only as a reproducibility check against the original 31 rows (same rankings
  expected, up to the float-rounding effect above).
- **Reporting before the family is complete.** Holm adjusted p-values never decrease when
  another member's p-value increases: Holm is closed testing with Bonferroni local tests, and
  each local test is monotone. So once C3 is complete, a candidate that passes the rule with
  unfinished members held at p = 1 passes whatever those members later show, and it is reported
  as final. A candidate that does not pass stays provisional until the family is complete.
- **What the summarizer does.** `lme_summarize.py` (v2; v1 kept) implements this as follows.
  These changes were made before any comparison against C3 existed.
  - Until the queue finishes (`--final`), the family is its largest form, C4 included, with
    unfinished members held at p = 1.
  - An arm with env errors counts as unfinished.
  - Each comparison draws its bootstrap and sign-flip samples from its own generator, seeded
    with the preregistered seed and (track, arm, metric). An arm's CI and p-value therefore do
    not depend on which other arms have finished.

### 2026-09-24 A14: production is C4, not C3 (a correction written at 23:26 EDT, before any comparison against C3 or C4 existed)

When A14 was written, C3 had 121 of 470 rows and C4 had not started. No C3 or C4 score had been
computed or read.

- **Fact.** Production ai-memory reranks project `memory_query` results with its LLM.
  - The LaunchAgent sets `AI_MEMORY_RERANKER=llm`, with qwen3.5-9b-64k on local Ollama at
    reasoning effort low.
  - The running server's startup log (17:53:48 EDT) records "memory_query reranking enabled".

  The Arms table's "C3 … Incumbent (production config)" is therefore wrong. C3 is production
  with the reranker off, and C4 is the production configuration.
- **Layer decision.** A layer candidate (A0, B1, B2, D1, D2, D3) replaces ai-memory only if it
  beats both C3 and C4 under the unchanged rule.
  - Each comparison is Holm-corrected within its own family: the preregistered family against
    C3, and the six layer candidates against C4.
  - Requiring both is an intersection–union test, so no further correction is needed.
  - The change can only make a switch harder.
- **Reranker decision.** Production is the status quo, so it keeps the reranker unless C3 beats
  C4 under the rule. That comparison uses the C4-versus-C3 comparison's p-value from the
  family against C3, with the sign reversed. A12's fallback rule still applies: more than 5%
  fallbacks makes the decision inconclusive.
- **Embedder decisions.** C5 and C6 against C3 are unchanged. They measure embedder size with
  the reranker off, and that limit is stated with the result.
- **Unchanged.** Metrics, tracks, statistics and the A13 early-final logic. Layer decisions now
  wait for both C3 and C4 to finish.
- **Implementation.** `lme_summarize.py` v3 (v2 kept) implements A14. Every decision path was
  exercised on stand-in data in a scratch copy (an A14 pass, the reranker's status-quo rule,
  and A12's inconclusive branch at 10% fallbacks) before C3 or C4 finished.

### 2026-09-25 A15: the rerun on VelaNext, plus current-generation models (written before any VelaNext run)

- **Why.**
  - User decisions (2026-09-25): the coordinator Mac is control-only; heavy evaluations run on
    VelaNext (Threadripper, RTX 4090, WSL2 Ubuntu 24.04), as native Claude Code sessions
    started there; results return as Git pull requests; there is no SSH between the hosts.
  - The user also asked why the stack runs stale models. The model re-screen (two blind lanes,
    `bench/lanes/sota-models-*.md`, convergence record included) found current-generation
    models in every role.
- **One platform per comparison.** Every arm used in a VelaNext decision is rerun on VelaNext.
  - It uses the same harness logic (v3; only paths and endpoints are configured) and the same
    pins:
    - dataset sha256 and `eligible-manifest.json`;
    - official LongMemEval 9e0b455, run natively on CUDA (the Mac's device-count shim is not
      needed);
    - ai-memory 19b6429 (`release/2.5`) built for Linux;
    - agentmemory 0.9.29 with iii 0.11.2 for linux-x64, checksum-verified;
    - Ollama 0.34.4 for the GGUF models, with the Mac digests (qwen3-embedding 0.6b
      `ac6da0dfba84`, 4b `df5bd2e3c74c`, 8b `64b933495768`).
  - The Mac results (A0, A1, B1, B2, C1, C2, C3, D1, D2) are kept as a cross-platform
    replication, reported per arm and never mixed into a VelaNext comparison.
  - **Platform deviation.** Production's reranker LLM is qwen3.5-9b in NVFP4 through Apple MLX.
    The RTX 4090 has no native FP4, so C4 and the H arms use the official GGUF build of the same
    model. This is stated with every reranker result.
- **New arms: the A15 family.**
  - **Embedders.** Nemotron-3-Embed-8B and Nemotron-3-Embed-1B (NVIDIA, 2026-07-16), and
    harrier-oss-v1-0.6b (Microsoft, 2026-03-30).
    - Each runs from its developer's reference implementation (official weights,
      transformers/sentence-transformers, BF16, CUDA), behind an OpenAI-compatible
      `/v1/embeddings` server with the A13 byte-exact cache in front.
    - Gate: before any arm, the server must reproduce the model card's published example
      similarities to 2 decimal places.
    - Every embedder, old and new, is capped at 4,096 input tokens. This matches the production
      guard and NVIDIA's own evaluation length.
    - Query and document prompts follow each model card where the system accepts prefixes
      (ai-memory, dense). agentmemory's OpenAI provider sends no prefix, as shipped.
    - E1–E3: agentmemory with each new embedder. F1–F3: ai-memory with each. G1–G3: the dense
      baseline with each.
  - **Reranker LLM.** H1–H3 swap ai-memory's reranker LLM, reusing C3's embeddings through the
    cache.
    - H1: Qwen3.6-35B-A3B, thinking off.
    - H2: Nemotron 3.5 Lightning 30B-A3B, reasoning off where supported.
    - H3: LFM2.5-2.6B. Its LFM1.0 licence needs review before any production use.
    - Each uses an official GGUF on Ollama 0.34.4. A12's 20 s limit and fallback rule apply.
  - **Diagnostic, no decision.** G0 is the dense baseline with Qwen3-Embedding-4B at BF16 from
    its reference implementation. It separates the effect of quantization and runtime from the
    effect of the model generation.
  - **Exploratory, no decision.** X is a cross-encoder stage over the top 50 of the best
    system: ettin-reranker-400m-v1, MemReranker-4B, Qwen3-Reranker-4B and
    KaLM-Reranker-V1-Small. It is excluded from Holm, because no system accepts these models
    as shipped. Jina Reranker v3.5 is excluded (CC-BY-NC).
- **Decisions.** The A2 rule is unchanged. The A15 family (E, F, G, H) is Holm-corrected on its
  own:
  - F and H are compared against production C4;
  - E and G, the layer candidates, are compared against both C3 and C4 (A14);
  - A13's early-final logic applies.
  - Among candidates that pass, choose by point estimate, and report the paired CIs between
    them.
  - The original family is decided unchanged from the VelaNext reruns.
- **Order on VelaNext, one GPU workload at a time.**
  1. Gates: the oracle ceilings, the slot smoke test, and the reference-output check.
  2. C3, then C4.
  3. E1–E3, then F1–F3.
  4. The rest of the original family.
  5. H1–H3.
  6. G0–G3.
  7. X.
- **Return path.** The workstation session opens one pull request with:
  - the rows (`results-velanext/`);
  - the report;
  - an environment receipt: GPU, driver, CUDA, versions, model revisions and digests;
  - the cache statistics.
  All of it is sanitized to pass `validate.py`. This amendment is committed in Git before any
  VelaNext run.

### 2026-09-25 A15.1: GPU throughput on VelaNext (written before any VelaNext run)

- **Measured limit on the Mac.** The embed server ran at 99% GPU device utilization with one
  slot and one sequence at a time, about 1,920 tokens/s (00:00–00:25). Ollama runs embedding
  models single-slot: A11's `OLLAMA_NUM_PARALLEL` was ignored.
- **VelaNext embedding servers batch.**
  - GGUF embedders (the Qwen3 controls) are served by a pinned llama.cpp CUDA `llama-server`
    over the same GGUF blobs (digests as in A15), with `--embeddings`, `--pooling last`,
    16 parallel slots and a large ubatch, instead of single-slot Ollama. Ollama remains the
    server for the GGUF chat LLMs (C4 and the H arms).
  - The BF16 reference server batches concurrent requests dynamically, sorting by length
    under a token budget per batch.
- **Batch-invariance gate, run with the reference-output gate.** For every served embedder,
  the gate texts are embedded one at a time and inside a mixed batch. Each pair must agree to
  a cosine of at least 0.9999. The maximum deviation goes into the environment receipt. A model
  that fails runs single-sequence and says so.
- **Concurrency.**
  - ai-memory arms run 16 questions at a time and agentmemory arms 8 slots, each still with a
    fresh store.
  - The dense baseline sends batches of 64.
  - CPU-only arms (A0, A1, B1, C1, D1, and the MiniLM arms C2 and D2) run alongside GPU arms,
    because they place no load on the GPU. There is still only one GPU workload at a time.
- **Evidence.** GPU utilization is sampled every 5 s during each arm (`nvidia-smi dmon`), and
  the per-arm mean goes into the report.

### 2026-09-25 A15.2: corrections from the adversarial review (written before any VelaNext run and before C3 finished)

The review ran 5 dimensions with 3 skeptics per finding and confirmed 37 findings. The JSON is
in the coordinator's session scratchpad, and it will be sealed with the evidence. This amendment
applies every statistics, design and records finding. The code and infrastructure findings are
implemented in the package's harness v4 and summarizer v4.

- **Families and error control.**
  - There is one family per reference arm, each fixed now at its largest membership:
    - the **C3 family**: the original members (A0, B1, B2, C1, C2, C4, C5, C6, D1, D2, D3) plus
      E1–E3 and G1–G3, all against C3;
    - the **C4 family**: the layer candidates (A0, B1, B2, D1–D3, E1–E3, G1–G3) plus F1–F3 and
      H1–H3, all against C4.
  - Holm runs within each family at α = 0.0333. A layer candidate must pass both families (the
    A14 intersection–union test).
  - α = 0.0167 is reserved for A16. A16's arms are named in A16 before any A16 run.
  - An arm not named before its first run makes no decision.
  - A13's p = 1 treatment applies over these fixed families.
- **Precedence for each production setting.**
  1. **The reranker.** C3 against C4 is decided first, with production as the status quo. The H
     arms are compared only if the reranker stays on.
  2. **The embedder.** F1–F3 run ai-memory with the reranker ON, which is the production
     configuration with only the embedder changed, and they are decided against C4. C5 and C6,
     which run with the reranker off, stay C3-family size diagnostics.
  3. **The layer.** A0, B, D, E and G must pass both families.

  Among passing candidates for one setting, the choice is by point estimate, and the paired CIs
  between them are reported. The winner's estimate is labelled as selected, so it is biased
  upward.
- **Matched-embedder system comparison.** E against F, with the same embedder in both, is
  reported as a paired, descriptive result. It is required before any claim that a system beats
  ai-memory "at equal embedder".
- **C4 fallbacks.** A12's 5% rule applies to every decision whose reference arm is C4, and to
  the H arms. Above 5%, those decisions are inconclusive.
- **Reranker pins.** C4 and H use the production Modelfile parameters: `num_ctx` 65536, the same
  sampling and reasoning settings, and the official GGUF quant pinned by digest. The effective
  context is recorded in the receipt.
- **agentmemory's shipped path.** A new arm, D2h, is required before any layer switch to
  agentmemory. It runs agentmemory 0.9.29 with MiniLM fed through its shipped Claude Code hook
  sequence (observe on each prompt, then session end), not the REST `remember` path. D1–D3 and
  E1–E3 keep the REST path and are labelled "benchmark API path".
- **Deployable artifact.** A production switch to a new embedder also requires the artifact that
  would be deployed, the same reference implementation on the target host (MPS on the Mac) or a
  verified conversion, to meet two conditions. It must reproduce the reference embeddings on the
  gate texts (cosine ≥ 0.999), and it must stay within 1 pp of the reference on a 100-question
  subsample.
- **Mac and VelaNext.** The Mac results (A0, A1, B1, B2, C1, C2, C3) are descriptive and serve as
  the cross-platform replication. Confirmatory decisions come only from VelaNext, so there is one
  confirmatory look per family.
- **macOS 27.0 deviation.** The Mac rebooted into macOS 27.0 at about 01:19, with C3 at 348 of
  470 rows. Rows 349 onward are computed on 27.0, with the same Ollama binary and model digest.
  A drift check recomputes 20 completed questions on 27.0 with no cache and reports how many are
  identical at @5.
- **Record corrections.**
  - **A14.** Per-question metrics were stored in every row, and every 25th question's
    recall_all@5 was printed to `logs/queue-aimem-qwen3.log`. The coordinator never opened that
    log and computed no aggregate before A14. "No score read" should have said "no aggregate
    computed or read".
  - **A13.** The 22:17–22:28 window was contended: the quant run froze at 22:19 and B2 finished
    at 22:26. The exclusive-GPU rate was measured from 22:44 to 22:54.
  - **A13's queue.** It was superseded at 00:00 by the control-only decision. C4, C6, D3, C5,
    the quant runs and AIPerf never ran on the Mac. D3's 12 Mac rows are excluded from every
    analysis.
  - **Reproducibility.** It is reported as counts only, with no causal attribution.
  - **Model-lane record.** The lanes made 15 Codex web_search calls, not 30. The LM Studio
    dimension bug comes from the Codex lane only.
- **Harness equivalence.** v4 is v3 logic plus the fixes listed in the package README. Before any
  confirmatory arm, v4 must reproduce v3's rankings exactly for 20 questions of C1 and 20 of B1,
  both CPU-deterministic.

### 2026-09-25 A16: memory-system trial arms (named before any A16 run; α = 0.0167 as reserved in A15.2)

Source: the blind cross-family convergence of 2026-09-25 (`lanes/adjudication-20260925/`). Nine
GPT-6 Sol judgments in three presentation orders trialled agentmemory, MemPalace and Hindsight, and
retained ai-memory as the production control.

- **Decision-capable arms (the A16 family).** Each is a layer candidate, so it must pass against
  both C3 and C4 (A14's intersection–union test), with Holm inside the family at α = 0.0167.
  - **D2h:** agentmemory 0.9.29 with MiniLM, fed through its shipped Claude Code hook sequence
    (A15.2).
  - **M2:** MemPalace 3.10.0 (MIT) in palace (production) mode.
    - Ingest: the question's dated transcripts through its shipped miner and hook path.
    - Query: its MCP search.
    - Rank sessions by first hit.
    - Install: the official release only.
  - **K1:** Hindsight 0.10.1 (MIT) with one local LLM, Qwen3.6-35B-A3B from the H1 build.
    - One memory bank per question.
    - Ingest: `retain(transcript, timestamp, document_id=session_id)` for each session.
    - Query: `recall(query_timestamp=question_date)`.
    - Rank sessions by first-seen `document_id`.
    - Cost: an LLM extracts facts on every retain, so K1 runs on a preregistered stratified
      subset of 100 questions (seed 20260925, stratified by question type). C3, C4 and D2 are
      scored on the same subset for the paired comparison.
- **Diagnostics (no decision).**
  - **M1:** MemPalace raw mode through its upstream `longmemeval_bench.py`, run unmodified. It
    reproduces the vendor figure and gets rescored with the official evaluator.
  - **Vendor harness reproductions,** each run unmodified with its own metric recorded next to
    ours: agentmemory `benchmark/`, ai-memory `evals/src/retrieval`, and Hindsight's
    agent-memory-benchmark.
  - **Pooled-store stress run:** all eligible sessions pooled into one store, for the top two
    systems only. Descriptive.
- **Deferred (no arm).**
  - Attemory: its gate is a source and licence check of the prebuilt core.
  - GBrain and Mem0 OSS.
- **Rejected for this role:** Honcho, OpenViking, Basic Memory, and the retired Letta server.
- **Production rule (unchanged).** ai-memory stays in production until an A16 or A15 candidate
  passes. A candidate that passes then needs the catalog's memory-lane acceptance before
  adoption: an explicit durable decision retrievable in its intended scope, cross-scope
  negatives, and recovery.
