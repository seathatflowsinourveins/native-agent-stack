# Foundation research pass — 2026-09-19

Scope: token/context reduction, memory/RAG and evaluation. Existing 453-identity index and 152 scoped cards were checked first. Wave 1 revisited six adopted/cataloged projects at current stable or package identity and selected implementation paths; wave 2 searched beyond the index for lifecycle and retrieval-scoring gaps and source-reviewed three new candidates. This is a bounded two-wave review, not an exhaustive claim that no other SOTA repository exists. No new provider/model calls, installations or service changes. Only QMD's lexical snapshot benchmark actually ran; other commands below are prospective acceptance recipes.

## Decisions

1. Implement now: pinned QMD BM25 benchmark on an online-backup copy, frozen questions, unchanged upstream scores and separate exact-ID audit. Completed: 12 native/direct searches identical; exact recall@3 8/12, recall@1 5/12, recall@5 9/12, MRR 0.56875. Four misses retained. This is raw lexical retrieval, not complete agent query craft or robust RAG. See the new retrieval-evaluation artifact.
2. Best next bounded acceptance: ai-memory's own zero-LLM retrieval harness against a fresh temporary server. It still requires the pinned source build and separately fetched, checksum-checked LongMemEval dataset; do not run consolidation A/B or alter live memory. Cross-scope behavior should additionally use upstream multiuser tests, whose mirrored CLI authentication middleware limitation is documented in source.
3. Add MELT and ir_measures as source-reviewed alternatives, not installed defaults. MELT fills lifecycle/scope evaluation; ir_measures supplies conventional exact-ID IR metrics. Neither proves our live memory integration by testing its own fake adapter.
4. Keep the existing Nemotron/SocratiCode service. Fresh HF metadata matches current catalog pins; no measured benefit justifies replacing it now. Do not stack competing memory stores or trace backends without a concrete missing capability.

## Wave 1: existing stack, deeper source review

### mksglu/context-mode

- Stable: v1.0.169; released 2026-06-29T18:18:53Z; tag commit `589d8214d56740a28b5f7bf63167743d586b0b40`. Main separately observed at `5283a70780305994433cb65d6a0275386e797172` on September 19. Existing catalog's historical reviewed-main pin must not be presented as the release commit.
- License: **Elastic License 2.0**, verified from LICENSE; GitHub returns NOASSERTION. Relevant limitation: hosted/managed service access to substantial functionality is restricted. This does not make it a permissively licensed hosted foundation.
- Selected implementation: [real-byte stats tests](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/tests/session/real-bytes-stats.test.ts), [CLI doctor](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/cli.ts), [LICENSE](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/LICENSE).
- Concrete finding: tokens-saved estimates derive from bytes divided by four, with retrieval versus sandbox-output and worktree/session scope distinctions. They are not provider usage or a causal billing A/B. Existing restart evidence proves direct Desktop tools; old blanket 'not loaded' wording was stale and root has corrected it.
- Native acceptance: `context-mode doctor`; native MCP `ctx_stats` in the intended actual session. Existing scoped bridge recipe remains `mcporter --config "$MCPORTER_CONFIG" call context-mode.ctx_doctor --args '{}' --output text --no-oauth`.
- Duplication risk: installing another truncation proxy can double-count estimated reductions and hide raw error evidence; retain native hooks and raw artifacts.

### akitaonrails/ai-memory

- Stable v2.3.1; released 2026-09-17T18:26:44Z; tag commit `5b2426f73db69ee45a6805dabf74b061ed2c63dd`; MIT. Main independently advanced to `13eb7a20bb5f7da1ed3ee701b7bff8be75de7c52` at 18:42 September 19; no automatic upgrade recommended.
- Selected implementation: [retrieval CLI arguments and runner](https://github.com/akitaonrails/ai-memory/blob/5b2426f73db69ee45a6805dabf74b061ed2c63dd/evals/src/retrieval/mod.rs), [production-shaped multiuser scope test](https://github.com/akitaonrails/ai-memory/blob/5b2426f73db69ee45a6805dabf74b061ed2c63dd/crates/ai-memory-mcp/tests/suite/autoscope_multiuser.rs), [automatic-improvement eval gates](https://github.com/akitaonrails/ai-memory/blob/5b2426f73db69ee45a6805dabf74b061ed2c63dd/docs/auto-improve-eval-gates.md).
- Concrete finding: native retrieval evaluation is a workspace binary, not shipped in the installed CLI; default `--embeddings none` creates a fresh evaluation server. Its local alternative uses an older MiniLM model and is not evidence for the installed Nemotron RAG service. The scope test replicates a small part of CLI bearer middleware because the CLI crate is binary-only; do not claim whole auth-chain deployment acceptance from that test alone.
- Prospective native commands in pinned source: `cargo build --release -p ai-memory-cli`; then `cargo run --release -p ai-memory-eval -- retrieval --fetch --sample 10 --embeddings none --concurrency 2 --out "$NEW_PRIVATE_DIR"`. Dataset fetch is about 278 MB and separately checksum-verified. Full 500-question run and abstention handling would be required for a general benchmark claim; first ten is only a deterministic sample.
- Duplication risk: another memory store would split the system of record and lifecycle rules. Keep ai-memory durable scope; inspect consolidation gates without enabling new automatic inference.

### tobi/qmd

- Stable v2.8.3; released 2026-08-16T22:30:34Z; tag commit `facd35e01359e59d938bc9418e93fb9318addee3`; MIT. Main remains separately `04e4dbd8245c527a88f1a8f0bda547aef9ca81fb` (September 9).
- Selected implementation: [benchmark](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/bench/bench.ts), [scorer](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/bench/score.ts), [CLI dispatch](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/cli/qmd.ts#L4715), [store initialization](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/index.ts#L352).
- Concrete gap closed: measured retrieval quality on scoped existing content. Caveats found: CLI does not forward backend selector; default benchmark invokes all four backends, so there is no `--backends bm25` CLI flag. Internal shipped API supports that selector. Native matcher accepts path suffixes and the precision denominator is nonstandard; native catches backend exceptions as zeros. Wrapper preserves native values, exact-ID metrics and direct lexical error replay.
- Executed upstream call: `runBenchmark(fixturePath, {dbPath: snapshot, collection: 'us-equities-foundation', backends: ['bm25'], json: true})`. `CI=true` disables real operations in QMD's LlamaCpp layer. Online-backup copy is the only database passed to QMD; byte hash unchanged. Native stdout remains private because it has local fixture path.
- Upstream search workflow from installed `qmd skill show`: author strong domain keywords, scoped `qmd search`, `qmd get` complete source, one lexical reformulation if needed. Conceptual intent/lex/vec/hyde workflow requires a separately accepted model-backed lane. Do not tune frozen questions post hoc.
- Duplication risk: another Markdown index creates freshness/scope ambiguity; benchmark and improve the existing collection first.

### giancarloerra/SocratiCode

- Stable v1.14.0; released 2026-09-16T14:26:47Z; tag commit `2218f25153d0f3f4a76ee240a5643dbc873e80be`; AGPL-3.0 (catalog notes commercial alternative). Main `b67f1328ff52ca869f642bb6b068bb0d3f2c3646`, September 17, matches existing reviewed-main catalog pin.
- Selected implementation: [watcher](https://github.com/giancarloerra/SocratiCode/blob/2218f25153d0f3f4a76ee240a5643dbc873e80be/src/services/watcher.ts), [embedding configuration](https://github.com/giancarloerra/SocratiCode/blob/2218f25153d0f3f4a76ee240a5643dbc873e80be/src/services/embedding-config.ts), [watcher unit tests](https://github.com/giancarloerra/SocratiCode/blob/2218f25153d0f3f4a76ee240a5643dbc873e80be/tests/unit/watcher.test.ts).
- Concrete finding: incremental watcher has two-second debounce, active-watcher guards and native filesystem notifications. Embedding provider configuration explicitly requires model and dimensions for the OpenAI-compatible lmstudio profile. Query/document prefixes are asymmetric by design and must match the model; changing a model requires deliberate collection reindex and acceptance, not metadata-only switching.
- Native prospective acceptance: `mcporter --config "$MCPORTER_CONFIG" call socraticode.codebase_health --args '{}' --output text --no-oauth`; `mcporter --config "$MCPORTER_CONFIG" call socraticode.codebase_search --args "$SEARCH_ARGS" --output text --no-oauth`. Select an explicit project and relevant query, then inspect original code. Existing watcher receipts remain dated evidence; health alone is not retrieval quality.
- Duplication risk: a parallel code index needs independent scope/freshness guarantees; retain this accepted automatic code lane.

### promptfoo/promptfoo

- Stable 0.123.1; released 2026-09-18T01:07:54Z; tag commit `34f74d34e140b5e17d23770dfb2340057b1936b8`; MIT. Main separately `25b33c10f59c94ef4be8c89b9b404f19e344536e` (September 19).
- Selected implementation: [EchoProvider](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/providers/echo.ts), [echo tests](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/test/providers/echo.test.ts), [eval command](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/commands/eval.ts).
- Concrete opportunity: replay a retained native worker report via `echo` with deterministic citation/schema/forbidden-action assertions and no new inference. Echo returns the input, zero cost and zero token counts; these counters describe replay only, not historical generation or tokens saved.
- Prospective native acceptance: `promptfoo eval -c "$FROZEN_ECHO_CONFIG" --output "$NEW_RESULT_JSON"`, with provider `echo` and only deterministic assertions. Configuration and evaluated report must be hash-bound. No such config was installed or executed here.
- Duplication risk: overlaps current native supervisor/report validation; use only when multiple stable research datasets justify a common regression suite. LLM judges/redteam providers can spend tokens even with a cheap generation provider.

### UKGovernmentBEIS/inspect_ai

- **Fresh PyPI version 0.3.266**, uploaded 2026-09-19T13:11:02Z; the base-bfd03bc catalog recorded 0.3.265; the current card has been updated. No GitHub latest release (404), which is not absence of a PyPI release. Reviewed main `ec4dfc6953784dc45b79de3147530c89868c6e26`, committed 13:10:22Z the same day; MIT. Main source identity is not asserted to be a wheel provenance attestation.
- Selected implementation: [rescore CLI](https://github.com/UKGovernmentBEIS/inspect_ai/blob/ec4dfc6953784dc45b79de3147530c89868c6e26/src/inspect_ai/_cli/score.py), [mock provider](https://github.com/UKGovernmentBEIS/inspect_ai/blob/ec4dfc6953784dc45b79de3147530c89868c6e26/src/inspect_ai/model/_providers/mockllm.py), [score tests](https://github.com/UKGovernmentBEIS/inspect_ai/blob/ec4dfc6953784dc45b79de3147530c89868c6e26/tests/_eval/test_score.py), [package identity](https://pypi.org/project/inspect-ai/0.3.266/).
- Concrete opportunity: rescore a retained evaluation log without rerunning a solver, with an explicit deterministic scorer. Prospective native command: `inspect score "$PRIOR_EVAL_LOG" --scorer "$DETERMINISTIC_SCORER" --output-file "$NEW_SCORED_LOG"`. Model-based scorers still call models; existing native JSON requires a deliberate Inspect log adapter, not relabeling.
- Duplication risk: choose one offline evaluation harness after defining common task outcomes; deploying Inspect plus promptfoo plus another trace stack without datasets is overhead.

## Wave 2: beyond-index finalists

### shisa-ai/MELT — new source-reviewed candidate

- No GitHub release; current main `47c819f417b0d81a57f781ec54d8a5cf84e0c833`, 2026-07-15T14:15:38Z; package source 0.3.1; Apache-2.0. Lifecycle-v5 release document labels its status release-candidate; do not relabel that as our production maturity verdict.
- Selected implementation: [scope validation](https://github.com/shisa-ai/MELT/blob/47c819f417b0d81a57f781ec54d8a5cf84e0c833/src/melt/scope.py), [fake scoped oracle tests](https://github.com/shisa-ai/MELT/blob/47c819f417b0d81a57f781ec54d8a5cf84e0c833/tests/test_fake_scoped_oracle.py), [CLI](https://github.com/shisa-ai/MELT/blob/47c819f417b0d81a57f781ec54d8a5cf84e0c833/src/melt/cli.py), [frozen suite/scorer identity](https://github.com/shisa-ai/MELT/blob/47c819f417b0d81a57f781ec54d8a5cf84e0c833/docs/RELEASE-lifecycle-v5.md).
- Concrete gap: memory recovery and successful search do not test tenant/workspace/project separation, directional sharing, correction, revocation or historical-as-of validity. MELT has explicit B3 scope/visibility contracts, hard leak guards and immutable corpus/scorer identities.
- Prospective source acceptance: `uv run pytest -q tests/test_scope_contract.py tests/test_fake_scoped_oracle.py` from reviewed source. This tests the benchmark/reference oracle only. A real ai-memory B3 adapter and new explicit test scope are required before claiming ecosystem E2E; the fake adapter's perfect scores are not our result. Native run CLI supports `--sut`, `--suite-version`, `--sut-contract-version`, `--answer-mode retrieval_only` and `--no-judge`.
- Duplication risk: complements retrieval tests, but a new custom adapter can introduce semantic mismatch; prefer ai-memory's native acceptance first.

### terrierteam/ir_measures — new deterministic scoring candidate

- Stable v0.4.3; released 2025-11-25T17:35:02Z; tag commit `bb9ece5c1ec6a0027c8a9f7a8ee428614f8a2f44`; Apache-2.0. This is a mature metrics dependency, not a newly released model. Main `64b5afd5cd14f7d8323f9b24a1bfd12afdd1e776` dated February 17, 2026.
- Selected implementation: [CLI/parser and TREC input](https://github.com/terrierteam/ir_measures/blob/bb9ece5c1ec6a0027c8a9f7a8ee428614f8a2f44/ir_measures/__main__.py).
- Concrete gap: conventional exact-document-ID scoring across QMD and semantic RAG avoids QMD-specific suffix and precision conventions. Prospective native command: `ir_measures "$QRELS" "$RUN" R@3 RR P@3 nDCG@10 --by_query`. Keep qrels, ranked IDs, relevance completeness and query sets frozen; no provider required.
- Duplication risk: QMD receipt already includes a narrowly sufficient exact-ID audit. Add this dependency only when comparing multiple retrieval systems or using graded judgments; not required for the current twelve-query baseline.

### ProsusAI/MemEval — new research alternative, defer execution

- No GitHub release; current main `807ae6d7d8a5b76f6fe964d5a581d96c036e2ac4`, 2026-03-16T08:55:12Z; Apache-2.0.
- Selected implementation: [full benchmark runner](https://github.com/ProsusAI/MemEval/blob/807ae6d7d8a5b76f6fe964d5a581d96c036e2ac4/scripts/run_full_benchmark.py).
- Concrete role: compares memory approaches on LoCoMo/LongMemEval and tracks model usage. Native documented command: `uv run python scripts/run_full_benchmark.py --systems propmem --num-samples 1 --skip-judge`. **This still invokes generation/extraction models**; skipping judge does not make it zero-LLM. Source examples use GPT-4.1-mini and are not a recommendation to replace current native models.
- Duplication risk: overlaps ai-memory retrieval and MELT while requiring additional system/provider integration. Defer until evaluating an actual alternative memory architecture with an approved budget and held-out task suite.

## Read-only model freshness check through the installed HF CLI

Executed `hf models list --author nvidia --search Embed --sort created_at --limit 6 --expand sha,createdAt,lastModified,cardData --format json`, and corresponding bounded Jina reranker / Qwen embedding searches. No weights downloaded.

- `nvidia/Nemotron-3-Embed-1B-BF16`: SHA `c0c9fea93ea424587517f2c59e20db9f1d6bf615`, repository created July 14, last modified August 27. `8B-BF16`: `d1f2f25730bbd775b99b29185134bc86653bf2d1`, last modified August 28. NVFP4: `f630128278eb245579d3ea022b4f659fbd614318`, last modified August 28. Model cards declare OpenMDW1.1. All match existing catalog. Created/modified metadata is not a public release date.
- `jinaai/jina-reranker-v3.5`: `e8a93f33f0b22108f8c2364f8484ce3422552fbc`, created July14, modified July30, CC-BY-NC4.0; matches catalog. GGUF/MLX variants exist, but a GGUF label alone does not prove compatibility with QMD's rerank contract or commercial trading use.
- Qwen-author newest embedding search returned Qwen3-VL embeddings from January, not an unambiguously newer text/code replacement. No assertion that the bounded author filters cover every Hub model.
- Direct metadata replay: `hf models info MODEL_ID --expand sha,createdAt,lastModified,cardData --format json`. Keep source card, dimensions, task prefix, pooling, runtime architecture and licensing checks separate from benchmark popularity. Keep the demonstrated 2048-dimensional service until held-out quality and resource use show an improvement.

## Remaining evidence gaps

- QMD top-three recall is 8/12 on a small curated set; no held-out improvement or hybrid comparison was run. Upstream query craft and search/get/reformulation fallback are documented prospectively, not credited as measured accuracy gains.
- Successful native memory backup/restore is accepted independently, but cross-file DB/wiki atomicity and off-host/key escrow remain limitations. Lifecycle isolation and answer-quality evaluation remain separate.
- Native token receipts are actual usage; context/RTK byte estimates are tool-local reduction measures. No causal net provider token or fee savings across comparable full tasks were measured here.
- Findings support these scoped choices. They do not justify 'definitive final SOTA across all repositories' or deployments of all cataloged alternatives.
