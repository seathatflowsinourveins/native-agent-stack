---
status: proposed
date: 2026-10-06
decision-makers: [command-center]
review_by: 2027-01-04
---

# Retrieval-first local models on NativeStack2604

NativeStack2604 uses one shared text-embedding endpoint for memory and semantic
code/document search. QMD retains lexical search, query expansion and its bundled
reranker. General local generation has no selected consumer and is retired.
This serves US-equities research and historical simulation through the native
foundation described in [the trading north star](../../blueprints/us-equities/AGENTS.md).

The command center finalized these role choices on 2026-10-06. This proposed
publication records them; it does not perform a host migration, deletion,
benchmark or model acceptance. The [sanitized documentary receipt](../../evidence/receipts/ns2604-local-models-rulings-20261006.json)
identifies the source ruling by SHA256 and separates selection from application.
CURRENT denotes the selected role; NEW and GATED retain their pending gates.
No foundation readiness count is derived.

## Decision and scope

| Role | Disposition and selected artifact | Consumer and application boundary |
| --- | --- | --- |
| Shared text embedding | CURRENT: `nvidia/Nemotron-3-Embed-8B-BF16` at `d1f2f25730bbd775b99b29185134bc86653bf2d1`; model release 2026-07-16 | ai-memory and SocratiCode, 4096 dimensions, exact `query: ` / `passage: ` prefixes. The CC reported the Codex migration; Claude's separate window/read-back remains pending. |
| QMD ranking | NAMED_EXCEPTION: `ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF` at `a02f48bb4f057028298c21fa033da2b30d7742d5`; GGUF repository 2025-10-03 | QMD's upstream in-process ranking default. Pinned local copies and CPU lexical registration are owner steps. This is distinct from the uninstalled external-reranker slot. |
| QMD embedding | RETIRED: no new embedder or vector build | Semantic Markdown search uses SocratiCode's existing shared index. The present Qwen 0.6B file/index remains interim until the cutover gates pass and remains a scoped exception if an executed smoke fails. |
| QMD query expansion | CURRENT: `tobil/qmd-query-expansion-1.7B-gguf` at `7816de0b72572c6c860ca1eddf97ba9e7fb8cc65`; repository created 2026-01-25 | CPU lexical expansion under QMD's upstream grammar. This role does not select a general local generation model. |
| Semble code embedding | CURRENT: `minishlab/potion-code-16M-v2` at `e9d2a44ca6a05ac6685f3b23709ea57eb7352d5b`; repository created 2026-07-04 | Its CPU Model2Vec loader; process version follows the actual relaunch. |
| jCodeMunch semantic embedding | NEW: `ibm-granite/granite-embedding-311m-multilingual-r2` at `44399559930365213510b1ee2eb15ded83374f0e`; card 2026-04-29 | CPU sentence-transformers, 768 dimensions. Exact pin, load/embed proof and two-client activation remain owner-gated. The 97m sibling is fallback only if the load/embed smoke fails. |
| General local generation | RETIRED: no resident or on-demand pick | A named consumer must exist before its owner selects a new model. Swift/Ollama host removal requires the CC's merge and holder gates. Port 21434 remains reserved by the GPU owner. |
| Document parsing | CURRENT: MinerU registry's `jinzhenj/MinerU2.5-Pro-2605-1.2B-GGUF` at `9185688a0495e1577d521a757c7c0b62dd38ca48` and `opendatalab/MinerU-4_models_onnx` at `358310b4f64b95f9fefc372ad899356e4111f376`; model card 2026-05-21 | CPU GGUF/mmproj and ONNX. Native local-source verification/parse belongs to fixwave-defects. A separate side project's docling remains its named exception. |
| Headroom Kompress | GATED: `chopratejas/kompress-v2-base` at `b1563631b35bfdcee37587ad530147497d820d4c`, created 2026-05-30; matched `answerdotai/ModernBERT-base` tokenizer at `8949b909ec900327062f0ebf497f51aef5e6f0c8`, created 2024-12-11 | Headroom remains MCP-only. The tokenizer is a pinned stale exception for the ONNX export; the token owner controls any extra/loader change. |
| Package-bundled assets | NAMED_EXCEPTION: Magika `standard_v3_3`, Codebase Memory's compiled `nomic-embed-code` vectors, and CMU PocketSphinx en-US data bundled by SpeechRecognition 3.16.1 | Keep maintainer-shipped assets. Codebase Memory semantic mode remains opt-in/off. PocketSphinx recognition use was not observed; the critic reported a 29.2 MB package asset and a cache copy. Model release date is not established for that asset. |

Nemotron 1B and the ai-memory MiniLM baseline are superseded on NativeStack2604.
The old workstation's Qwen li26 serving receipt and all earlier acceptance/model
measurements remain historical evidence. This ruling does not describe another
distribution's current state or authorize changing it. MiniLM deletion still
waits for the CC's Gate 3/control ruling and holder check.

## Alternatives and evidence

The retained choices follow the supported consumer loaders. QMD 2.8.3 uses
in-process GGUF models; its lexical role can reuse the shipped ranking and
expansion defaults while semantic catalog search uses the existing shared
index. The older reranker remains a named consumer-limited exception. A future
remote backend may reopen endpoint ranking. The workload catalog's TeleOCR,
PaddleOCR and jina-reranker entries remain a trading-owner handoff.

Published model-card and leaderboard evidence, the CC's retained native
observations, derived scores and this PR's structural checks have distinct
classes under [the acceptance policy](../acceptance-evidence-policy.md#identify-what-each-check-proves).
The CC's RTEB private-13 mean is derived; it is not an official board statistic.
MinerU's published BF16 result is not a measured score for its deployed Q8_0
GGUF, and the PureDocBench comparison uses a sibling rather than the 2605 row.
Prior semantic/code scores behind Granite and Semble were not remeasured here.
No local fixture or model verdict is promoted to upstream acceptance.

The historical 10-01/10-03 settlements keep their original measurement inputs,
results, limitations and receipt hashes. A dated current-ruling projection uses
the existing `resolved`, `not_installed` and `kept` states/outcomes. Current
source choices carry no returned measurement; the old measured row is retained
separately. This fills the assembler's demonstrated gap: at
`native-agent-stack@0d5e6506:assemble_manifest.py:97-101` every settlement was
previously projected as a returned measurement.

## Re-drive and named exceptions

Reopen shared embedding when its official weights, supported serving release,
consumer modality or resource ownership changes. Published LMEB and complete
RTEB rows inform the owner; the private-13 statistic retains its derived status.
The next assigned owner re-drive also considers vendor models without board rows.

Reopen QMD ranking/expansion when upstream changes defaults or loader support,
or supplies stronger same-protocol evidence for a loadable artifact. Reopen the
embedding role on a configurable-prefix remote backend or upstream support for
EmbeddingGemma 2, and reopen the whole lane if its organic usage remains zero.
An executed either-client semantic smoke failure retains the pinned Qwen 0.6B
fallback. A check that has not run does not establish that failure.

Reopen Semble on a vendor code-model successor or new supported loader, and
jCodeMunch on compatible model evidence, prompt support or the upstream L-121
fix. Reopen parsing on newer vendor/registry evidence, a changed comparable
benchmark row, usable spare GPU capacity or an actual native failure. The next
owner re-drive includes the critic's missing vendor classes; this PR does not
decide those unreviewed candidates.

Kompress waits for the token owner's extra decision and loader read at the
installed release. Bundled assets reopen when their maintainer replaces the
model, the consumer package/feature changes, or recognition/semantic use becomes
an owned requirement. PocketSphinx is kept only as SpeechRecognition's bundled
en-US asset in deer-flow; the exception does not claim an installed recognizer,
an observed recognition workload, or an independent model-quality result.

## Application, ownership and open items

- Client templates/examples carry the selected 8B identity and lexical QMD
  settings. The exact existing-index namespace remains the CC's deployment and
  read-back contract; templates do not invent a host binding.
- fixwave-defects owns #723's install-plan retirement/pinned-model rows and its
  synthetic install/server assertions. This PR references that work and does
  not edit its plan. Generated manifest/plan consistency and overlapping test
  ownership require the co-op's integration order (Q27).
- Trading owns `catalogs/us-equities/` under `docs/lanes.md:25`. The PR body
  carries exact pinned model/workload lines, including TeleOCR, PaddleOCR and
  jina-reranker, for its custody read; no trading catalog is edited here.
- Source generation and local tests wait for the paper window to end, run at
  nice 19, and stay separate from the owner's native application checks.
- The CC applies two-client cutovers and gated deletions. Prior index/model
  files are retained until those gates pass. This source PR changes no host
  state and leaves the separate rc6 gate-owner hold in force.

## SOTA sources

- [NVIDIA's pinned 8B card](https://huggingface.co/nvidia/Nemotron-3-Embed-8B-BF16/blob/d1f2f25730bbd775b99b29185134bc86653bf2d1/README.md): dimensions, query/document prefixes and supported serving.
- [QMD v2.8.3 native loaders](https://github.com/tobi/qmd/blob/v2.8.3/src/llm.ts) and [CPU mode](https://github.com/tobi/qmd/blob/v2.8.3/README.md#L1151): upstream default ranking/expansion and supported configuration.
- [SocratiCode v1.15.0 embedding configuration](https://github.com/giancarloerra/SocratiCode/blob/v1.15.0/src/services/embedding-config.ts) and [ai-memory v2.5.2 external embeddings](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/docs/llm-providers.md#L374): consumer interfaces.
- [vLLM v0.31.0 pooling configuration](https://github.com/vllm-project/vllm/blob/v0.31.0/vllm/config/pooler.py): supported pooling/serving parameters.
- [SpeechRecognition 3.16.1 PocketSphinx adapter](https://github.com/Uberi/speech_recognition/blob/3.16.1/speech_recognition/recognizers/pocketsphinx.py): its bundled language-data locator and optional recognizer path. A metadata-only read confirmed this package version.
- Each model repository/revision and kept-artifact SHA256 is listed in the
  [documentary receipt](../../evidence/receipts/ns2604-local-models-rulings-20261006.json).
- `seathatflowsinourveins/native-agent-stack@0d5e6506434fab598dee861c749a22e628beb75a`: `docs/lanes.md:25,96-128`, `docs/acceptance-evidence-policy.md:26-33`, and `evidence/artifacts/new-wsl-definitive-defaults-20261001/assemble_manifest.py:97-101`.
