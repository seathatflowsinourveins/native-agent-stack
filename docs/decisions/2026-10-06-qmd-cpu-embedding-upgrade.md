# Decision: test official Qwen3-Embedding-8B Q8_0 in qmd on CPU (2026-10-06)

Status: superseded by the 2026-10-06 retrieval-first local-model ruling. The CPU
8B experiment stopped before completion; no AFTER benchmark or accepted 8B
embedding index exists. The selection and acceptance plan below are historical
and withdrawn, including the proposed 8B client registration switch.

The accepted direction retires qmd's embedding role. Semantic catalog Markdown
retrieval moves to SocratiCode on the shared Nemotron endpoint; qmd keeps lexical
search, its own upstream default reranker as a named exception, and query
expansion. Client cutover and final deletion remain command-center owned.

## Replacement backend and next review

The separate lexical index was built with native qmd 2.8.3 update on CPU, at
nice 19 and idle I/O priority, preserving the live collection patterns and the
ecosystem ignore. Native status and independent read-only SQLite observation
showed 425 documents, zero vectors and zero excluded ecosystem documents.
A declared title-based lexical query returned its expected acceptance-policy
document at rank 1 with actual reranking and no unavailable warning. An earlier
credential query missed its expected document; its output is retained separately.
This is a local integration smoke, not embedding or ranking-quality acceptance.

Kept files use immutable upstream revisions: the
[reranker](https://huggingface.co/ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF/tree/a02f48bb4f057028298c21fa033da2b30d7742d5)
hashes to `22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48`;
the [expansion model](https://huggingface.co/tobil/qmd-query-expansion-1.7B-gguf/tree/7816de0b72572c6c860ca1eddf97ba9e7fb8cc65)
hashes to `000dfb1c06efa6a049e9f64ba921c3740e2454f62abab6fa10e77bd30bb2bcc0`.
The native node-llama-cpp reader confirmed reranker pooling type 4 and the
`cls.output.weight` tensor. Host-specific receipts stay in private lane state.

Future embedding and reranker discovery includes every vendor organization and
models without leaderboard rows. Contextual chunk encoders form a distinct
candidate class. The one-card re-drive of
[Perplexity's preview](https://huggingface.co/perplexity-ai/pplx-embed-v2-context-9b-preview/blob/b667039ee8b438a6350fbc91bbcecd86f9d363ba/README.md)
found separate query/document encoding methods, contextual chunk outputs, and
preview identity constraints. Its card supplies no comparative result rows;
it is a discovery candidate, not evidence for replacing the shared endpoint.
Task-relevant quality evidence and a supported runtime/encoding contract would
be required to overturn the kept retrieval direction.

## Historical 8B selection and withdrawn acceptance plan

The north-star action is source-backed catalog retrieval for complex engineering
and US-equities research and historical simulation. No trading operation or
strategy gate changes belong to this unit.

## Supported upstream contract

The installed client reports qmd 2.8.3 (`facd35e`). GitHub's latest clean release
is also [v2.8.3](https://github.com/tobi/qmd/releases/tag/v2.8.3), resolving to
`facd35e01359e59d938bc9418e93fb9318addee3`. Its pinned
[changelog](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/CHANGELOG.md)
and installed source expose local GGUF embeddings through node-llama-cpp, with
Qwen3 instruction formatting or the embeddinggemma/nomic-style default. No remote
OpenAI embedding route or Nemotron prefix adapter was found in those sources.
The Qwen filename/URI must preserve the detection pattern documented in
[src/llm.ts](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/llm.ts#L90).
Retain this client release and its supported contract.

## Candidate and comparison

Choose the vendor's [Qwen3-Embedding-8B-GGUF](https://huggingface.co/Qwen/Qwen3-Embedding-8B-GGUF/tree/69d0e58a13e463cd99a9b83e3f5fee7c10265fab)
at revision `69d0e58a13e463cd99a9b83e3f5fee7c10265fab`, file
`Qwen3-Embedding-8B-Q8_0.gguf`, 8,047,105,824 bytes (about 7.495 GiB), SHA256
`d20ddc71e8a5c4344f2343481e242233a997dc5eaff442427a945836c97b4deb`.
The official Hub blob metadata provides the size and hash. Use supported native
`hf download` with that revision and filename; verify the resulting SHA256.
Run qmd with documented `QMD_FORCE_CPU=1` / `--no-gpu`; the GPU serves vLLM.
The initial host observation was 55 GiB available RAM and 32 physical CPU cores.
Measure actual working set because qmd's CPU context pool is core-bound.

The [official full-model card](https://huggingface.co/Qwen/Qwen3-Embedding-8B/blob/1d8ad4ca9b3dd8059ad90a75d4983776a23d44af/README.md)
reports English retrieval 61.83, 68.46 and 69.44 for 0.6B, 4B and 8B. The results
repository's current HEAD is still the prior decision's
[`76c02342e832b8f24a7eb814f7144634f36b8b4d`](https://github.com/embeddings-benchmark/results/tree/76c02342e832b8f24a7eb814f7144634f36b8b4d/results).
The common rows were re-read at that pin:

| Task, nDCG@10 | 0.6B | 4B | 8B |
| --- | ---: | ---: | ---: |
| NFCorpus | .36709 | .41100 | .41448 |
| NQ | .53461 | .63133 | .65247 |
| CQADupstackUnixRetrieval | .51494 | .59603 | .61211 |
| RTEB AppsRetrieval | .75344 | .89176 | .91071 |

The exact model row revisions are `b22da495047858cce924d27d76261e96be6febc0`,
`636cd9bf47d976946cdbb2b0c3ca0cb2f8eea5ff` and
`4e423935c619ae4df87b646a3ce949610c66241c` respectively. This is a common-task
comparison, not a complete current RTEB aggregate. The models lack different
newer code-task rows. 8B also trails 4B on multilingual instruction retrieval
(10.06 versus 11.56); this catalog is primarily English technical documentation.

Quantization evidence comes from the maintained
[Sentence Transformers comparison](https://github.com/huggingface/sentence-transformers/blob/4e1fb7221a5097a03e281ca1a42525c396c3acb2/docs/sentence_transformer/usage/efficiency.rst#L685).
It checks embedding agreement on 552 texts, uses BF16 as the 8B reference, and
includes Q8_0 and Q4_K_M. It supplies no numeric Qwen Q8 retrieval-loss result.
Its GPU throughput favors Q8 over Q4 on 8B and does not establish CPU latency.
The official GGUF card's model scores are not measured per-quant scores.

Alternatives are official 4B Q8_0 if the larger CPU model is too slow or exceeds
the observed working-set headroom; official 8B F16, which also fits the initial
RAM snapshot but has unknown CPU latency; and 0.6B as rollback. Nemotron's remote
route requires a supported qmd release with its exact query/passage prefixes.
New Qwen-VL multimodal models are outside this text-only embedding path.

## Acceptance and recovery

After the authorized time gate, freeze one known-answer catalog fixture in
qmd's [native format](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/bench/fixtures/example.json).
Run unchanged `qmd bench` against the existing 0.6B index and the separate 8B index
after its native `update` and full `embed -f --timeout 0`, always on CPU at nice 19.
Retain actual returned JSON and
stderr; distinguish fixture checks from upstream tests. Report hit counts,
R@1/R@3/R@5/MRR, vector first-load and subsequent-query latency, and working set.
The [native harness](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/bench/bench.ts#L167)
catches individual backend exceptions and produces zero rows, so independently
require populated vector results and a complete current index.

Build a separate named index by copying the existing YAML and changing only
`models.embed`. Named-index configuration is supported in the
[README](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/README.md#L710).
Explicitly unset `INDEX_PATH` for build/benchmark commands: the
[database resolver](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/store.ts#L636)
gives that variable precedence over the index name. Verify distinct actual
database paths. Model download caches remain shared. Compare the two indexes'
active document names and content hashes before attributing a gain solely to the
model; preserve any corpus difference rather than silently mixing conditions.

The user's A1 replaces in-place migration with separate indexes. Existing stdio
stores load the YAML and create their model once, as shown by
[src/index.ts](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/index.ts#L369).
The documented
[`qmd mcp stop`](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/cli/qmd.ts#L4739)
addresses daemon PID files, not these transports. The existing sessions retain
their consistent 0.6B index. No process is quiesced or killed. After acceptance,
prepare the exact MCP registration argument/database-route difference for the
command center; it applies client configuration and sessions adopt the 8B index
as they restart naturally. Intended new registrations must force CPU mode and
avoid an inherited old `INDEX_PATH`. No client configuration edits are included
in this lane.

Preserve the existing YAML, database and 0.6B weights as rollback. Its vector
space remains intact, so returning future client registrations to the old index
needs no old-index re-embed. Host-specific index paths, the registration diff and
actual before/after results belong in the private lane status, not this portable
record.

The comparison that would overturn this choice is a native catalog regression,
unacceptable CPU latency or RAM behavior compared with 4B, or a clean qmd release
supporting a stronger embedder's complete runtime and prompt contract.

## Completeness critic

A separate bounded reviewer covered missed candidate and modality classes,
quantization evidence, benchmark failure handling, CPU context memory, shared
stdio lifetime and rollback dimensions. Its findings are incorporated above.
The next sweep should prioritize per-quant CPU and retrieval measurements,
complete common-task benchmark coverage and named-index migration preflight.

Corrections retained: `qmd mcp status` has no dispatcher branch despite its stale
inline comment; use documented `qmd status`. Current bench rejects missing/empty
collections despite a stale README warning, while individual backend failures
still become zero metrics. These claims were checked in installed 2.8.3 and the
matching pinned upstream source.
