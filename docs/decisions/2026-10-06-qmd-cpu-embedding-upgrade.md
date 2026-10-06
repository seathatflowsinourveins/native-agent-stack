# Decision: test official Qwen3-Embedding-8B Q8_0 in qmd on CPU (2026-10-06)

Status: selected for native acceptance; host adoption pending the authorized time
window and supported MCP maintenance. This is a model selection record, not a
passed benchmark or installation receipt.

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
Run unchanged `qmd bench` before the model change and after a full
`embed -f --timeout 0`, always on CPU at nice 19. Retain actual returned JSON and
stderr; distinguish fixture checks from upstream tests. Report hit counts,
R@1/R@3/R@5/MRR, vector first-load and subsequent-query latency, and working set.
The [native harness](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/bench/bench.ts#L167)
catches individual backend exceptions and produces zero rows, so independently
require populated vector results and a complete current index.

Shared MCP maintenance is unsettled. Existing stdio stores load the YAML and
create their model once, as shown by
[src/index.ts](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/index.ts#L369).
The documented
[`qmd mcp stop`](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/cli/qmd.ts#L4739)
addresses daemon PID files, not these transports. Resolve an owning-client
shutdown/reconnect route before changing the shared embedding space. No client
configuration edits are included.

Back up the index YAML and preserve the 0.6B weights. YAML rollback must be
paired with a full 0.6B re-embed or a matching native SQLite snapshot; restoring
only YAML leaves incompatible 4096-dimensional vectors. MCP stores must reconnect
to the restored configuration too. Host-specific backup paths and actual before/
after results belong in the private lane status, not this portable record.

The comparison that would overturn this choice is a native catalog regression,
unacceptable CPU latency or RAM behavior compared with 4B, or a clean qmd release
supporting a stronger embedder's complete runtime and prompt contract.

## Completeness critic

A separate bounded reviewer covered missed candidate and modality classes,
quantization evidence, benchmark failure handling, CPU context memory, shared
stdio lifetime and rollback dimensions. Its findings are incorporated above.
The next sweep should prioritize documented MCP maintenance, per-quant CPU and
retrieval measurements, and complete common-task benchmark coverage.

Corrections retained: `qmd mcp status` has no dispatcher branch despite its stale
inline comment; use documented `qmd status`. Current bench rejects missing/empty
collections despite a stale README warning, while individual backend failures
still become zero metrics. These claims were checked in installed 2.8.3 and the
matching pinned upstream source.
