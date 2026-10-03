# Mac-native model hosting on `mac-coordinator-64gb-20260925` (host request #379)

**Corrected 2026-10-03 (port of #410).** These are the Mac coordinator session's
2026-09-27 outputs, ported from `14b5c52145d9cc42d4c9da36df53ac994009856a` as
descriptive reference evidence. They are not a qualification or host acceptance.
The [port record](port-record-20261003.md) records provenance, corrections, unresolved
conditions and the boundaries of reuse. No new Mac run was performed for this port.

Measured on 2026-09-27 on the 64 GB coordinator Mac (Apple M5 Pro, macOS 27.0, `arm64`). A normal
coordinator session was active throughout: Claude Code with its subagents, the ai-memory, Ollama and
Qdrant services, and ordinary desktop applications. The request is
[#379](https://github.com/seathatflowsinourveins/native-agent-stack/issues/379).
**Corrected 2026-10-03 (port of #410).** The recording session's
[decision record at `14b5c521`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/14b5c52145d9cc42d4c9da36df53ac994009856a/docs/decisions/2026-09-27-mac-native-model-hosting.md)
is historical context and is not ported as a live decision. All descriptions below
refer to that session and date.

## What this Mac hosts natively, and what exceeds it

**Corrected 2026-10-03 (port of #410). Hosted in the session's recorded probes under coordinator load:**
- the then-pinned RAG embedder (embeddinggemma-300M-Q8_0 on llama.cpp Metal, port 8232), whose local check
  returned pass with all layers reported on Metal; no discriminating control was retained;
- the memory stack's own models (Ollama `qwen3-embedding:4b` and `qwen3.5-9b-64k`), with the 9B inside
  ai-memory's 20 s reranker gate at 8K tokens (5.5 s);
- Qdrant;
- one 27B-class 4-bit generation model, Qwen3.8-27B UD-Q4_K_M on llama.cpp Metal. The session's li26 summary
  reports micro-F1 0.9909 at 15.7 tokens/s, or 23.9 tokens/s with MTP drafting; the quality and prediction
  equality cannot be checked independently from the retained aggregates;
- together, with the generation server at a 32K context (19.4 GiB peak RSS): 53% system memory free, no swap
  growth, 0 memorystatus kills;
- GPT-6 through this Mac's own OmniRoute gateway, for S3's LLM roles: 4.7-9.6 s on rerank-shaped prompts.

**Corrected 2026-10-03 (port of #410). Timing limits and overlapping load observed in this session:**
- **A 27B-class reranker LLM at 8K tokens.** Qwen3.8-27B answers in 27-28 s on llama.cpp Metal and 18.5 s
  median (20.7 s max) on Ollama's MLX engine, against ai-memory's 20 s gate. It fits in memory but not in time.
- **A heavy build overlapping the full model set.** Swap peaked at 13.9 GB, with no kills, while a Next.js
  production build overlapped the model loads. Attribution to the build is an inference from temporal overlap;
  no isolating comparison establishes which load caused it.
- **Not a memory limit:** Nemotron-3-Embed has no supported Mac runtime at all.
- **A projection, not measured:** the 64 GB profile's generation allowance is about 38 GB (64 × 0.6). It holds
  the measured 19.4 GiB comfortably. The 30B-class challengers in the verified sweep (granite-4.2-30b, about
  27.8 GB, and Nemotron-3.5-Lightning, about 27 GB at 32K) would fit that allowance alone, but with less
  headroom once the memory stack's 12.5 GiB is resident.

## Step 1: the pinned macOS local RAG profile

**Guard first.** Before any launchd step, `launchctl list | grep -E 'agent-ecosystem|native-stack'` showed
four pre-existing agents: `local.agent-ecosystem.ai-memory`, `.ollama` and `.qdrant` running, and
`.maintenance` stopped with last exit 1. No second Qdrant or ai-memory was started. The one agent this
request added is `com.native-stack.llama-embed`, rendered from
[`adoption/launchd/com.native-stack.llama-embed.plist.template`](../../../adoption/launchd/com.native-stack.llama-embed.plist.template).

| Port (loopback) | Served by | Origin |
| --- | --- | --- |
| 6333 | Qdrant 1.19.1, `local.agent-ecosystem.qdrant` | pre-existing (#253); its use receipt is `mac-coordinator-64gb-20260925--qdrant--use--20260925` |
| 8232 | `llama-server --embedding`, recorded as llama.cpp b11057 (version unverified), embeddinggemma-300M-Q8_0, `com.native-stack.llama-embed` | added for this request; Corrected 2026-10-03 (port of #410) |
| 11434 | Ollama 0.34.4, `local.agent-ecosystem.ollama` | pre-existing |
| 49374 | ai-memory, `local.agent-ecosystem.ai-memory` | pre-existing |
| 16333 | nothing | the template's `com.native-stack.qdrant` port; not started, because the pre-existing Qdrant serves this host |

**Embedding acceptance** ([`embed-acceptance.json`](embed-acceptance.json)), with the page's own command:

```sh
python3 tools/adoption/embed_acceptance.py http://127.0.0.1:8232 \
  evidence/artifacts/macos-embed-reference-20260923/macos-embed-reference-20260923.json
```

**Corrected 2026-10-03 (port of #410).** The check returned pass: 768 dimensions,
cosine 0.99966 against the Linux reference (threshold 0.99). No wrong-reference
embedding or other discriminating control was run or retained. Under the
[Discriminating controls rule](../../../docs/acceptance-evidence-policy.md#identify-what-each-check-proves),
this is an observation from a **Local integration check**, not acceptance. The served file is
`ggml-org/embeddinggemma-300M-GGUF@0f741b5a` `embeddinggemma-300M-Q8_0.gguf`, sha256 `b5ce9d77…0d63`.

**Corrected 2026-10-03 (port of #410).** The unported host receipt's version probe
used `--version | head -1` and retained only `llama_server: initializing ...`.
It does not verify the embedding server's recorded b11057 build; the separately
invoked benchmark does not establish this executable's identity (P2-4 remains open).

**Metal or CPU**, from llama-server's own startup log (the acceptance script cannot tell): each of the three
model loads in the log reports `using device MTL0 (Apple M5 Pro)` and `offloaded 25/25 layers to GPU`, and
no layer line names the CPU. The layers run on Metal.

## Step 2: Nemotron-3-Embed-1B has no supported Mac runtime

NVIDIA publishes no Mac-native form of `nvidia/Nemotron-3-Embed-1B-BF16@c0c9fea9`, and the supported
llama.cpp converter does not accept its architecture. Nothing was downloaded or converted.

- Its `config.json` declares `architectures: ["Ministral3Model"]`, `is_causal: false`, hidden size 2048.
  Its base model is `mistralai/Ministral-3-3B-Instruct-2512`.
- NVIDIA's four `Nemotron-3-Embed` repositories carry no `gguf`, `mlx` or `onnx` tag.
- llama.cpp registers only `Mistral3ForConditionalGeneration` and `Ministral3ForCausalLM`
  (`conversion/mistral3.py` lines 14-16 at v0.5.0 and at b11146 `7fe450e1`). At b11146 the bare
  `Ministral3Model` makes `conversion/__init__.py` raise and `convert_hf_to_gguf.py` exit 1 with
  "not supported".
- Community GGUF and MLX conversions exist. They are not upstream, the request excludes self-conversion,
  and their fidelity to the average-pooled bidirectional model is untested.

This reopens when llama.cpp registers `Ministral3Model` or NVIDIA publishes a GGUF or MLX artifact.

## Step 3: capacity under coordinator load

**Model.** `unsloth/Qwen3.8-27B-GGUF@4ca720788d1e01f1bff70c033e0d0028fd02e502`,
`Qwen3.8-27B-UD-Q4_K_M.gguf`, 16,464,440,224 bytes, sha256 `322e194f…3482`. It is 27.8B dense at 4 bits,
the smallest file of the request's 32B class. It is also the li26 production generation model, so the Mac
runs can be compared with the workstation's li26 results.

### Upstream throughput and serving ([`capacity.json`](capacity.json))

**Corrected 2026-10-03 (port of #410).** The table uses the class names from the
[acceptance evidence policy](../../../docs/acceptance-evidence-policy.md#identify-what-each-check-proves).
`capacity.json` remains byte-identical, including its embedded `evidence_class`
values `native_proven` and `local_integration`. Those are the recording session's
labels, not accepted policy classes or a qualification claim.

| Measure | Result | Evidence class |
| --- | --- | --- |
| `llama-bench -p 512,4096 -n 128 -ngl 99 -fa on -r 3` (b11057, Metal) | pp512 371.5 ± 1.1, pp4096 341.7 ± 15.3, tg128 15.9 ± 0.6 tokens/s | Upstream example or native operation, on this host on 2026-09-27 |
| llama-server, 32,768-token unified context (4 default slots), 9 requests, `cache_prompt: false` | median time to first token 4.67 s at a median 1,603 prompt tokens; 15.1 s at 5,189 tokens; median decode 15.8 tokens/s | Local integration check (the prompts are this repository's own docs) |
| Server peak RSS | 22,941 MiB | measured, 72 one-second samples |
| System free memory (`memory_pressure -Q`) | 89% before, 61% loaded, 89% after | measured |
| Swap | 16.81 MB used before, during and after (no change) | measured |
| Jetsam | 0 memorystatus kills | measured: 66 log lines matched, 63 were runningboardd "Ignoring jetsam update", 2 runningboard diagnostics, 1 the `log show` query itself |

The memory stack's own Ollama models were idle-unloaded during this probe. The worst case with them loaded
is measured below.

### li26 on real SEC filings, descriptive ([`li26-mac-descriptive.json`](li26-mac-descriptive.json))

The frozen li26 protocol
([`blueprints/convergence-practice/local-inference-latest-20260926`](../../../blueprints/convergence-practice/local-inference-latest-20260926/))
ran unchanged through `eval_arm.py` on the frozen inputs (360 SEC 8-K filings of 2020-03-02, acquired on
this host with EdgarTools 5.58.0 under the private SEC contact; inputs sha256 `2a5c8c9b…`). This Mac is not
the preregistered host: every number below describes this host and none is a parity or replacement
result. `metrics.json`'s `profile` field repeats the plan's declaration for each arm. What actually ran
here is full Metal offload (`--gpu-layers 99`) with the plan's other serving values, and C2 without
`--n-cpu-ffn`.

**Corrected 2026-10-03 (port of #410).** Evidence class: **Local integration check**.
No corrupted-li26 discriminating control was run or retained, so the reported
passes are observations, not acceptance (P1-1). `li26-mac-descriptive.json` contains
only aggregates: per-filing gold/prediction/status rows and hashes of the private
files read by `li26_mac_descriptive.py` were not retained. Micro-F1, JSON-valid,
exact match and "identical predictions" below are the session's reported summary
and cannot be checked independently (P1-2). The recorded input checksum and
reducer output do not identify those private run files.

| Run | Build | micro-F1 | JSON-valid | Exact match | Median decode | Median time to first token | Server peak RSS | Errors / memory kills |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | b11057 (the macOS pin) | 0.9909 | 1.0 | 0.975 | 15.73 tokens/s | 5.61 s | 16,300 MiB | 0 / 0 |
| C0 | b11146 (the plan's runtime) | 0.9909 | 1.0 | 0.975 | 15.80 tokens/s | 5.49 s | 16,530 MiB | 0 / 0 |
| C2, MTP drafting (`--spec-type draft-mtp --spec-draft-n-max 3`) | b11146 | 0.9909 | 1.0 | 0.975 | 23.94 tokens/s | 5.80 s | 17,606 MiB | 0 / 0 |

- **Corrected 2026-10-03 (port of #410). C2 vs C0, same build:** the session reports identical predictions
  on all 360 filings (paired bootstrap difference 0.0, 95% interval [0.0, 0.0]), 1.52× the median decode
  speed and four passing descriptive criteria. These aggregates do not independently establish acceptance.
- **Corrected 2026-10-03 (port of #410). b11146 vs b11057, same model and flags:** the session reports
  identical predictions on all 360 filings and 1.004× decode. Output equality is unverified.
- **For comparison only, not parity:** the workstation's frozen li26 run (RTX 4090, with partial offload for C0)
  recorded micro-F1 0.9909 for C0 and C2, and median decode 5.25 (C0) and 26.28 (C2) tokens/s
  ([`results/decision.json`](../../../blueprints/convergence-practice/local-inference-latest-20260926/results/decision.json)).
- **The memory stack was live throughout:** [`li26-window-samples.json`](li26-window-samples.json) has 118
  minute samples taken while the li26 servers ran.
  - In 6 of them, ai-memory's Ollama models (`qwen3-embedding:4b`, `qwen3.5-9b-64k`) were resident, up to
    14.95 GiB.
  - System free memory ranged from 34% to 63%.

**Corrected 2026-10-03 (port of #410).** C2 was not run on the Mac's b11057 install,
and no help or attempted-failure output was retained. This is installation-scoped
untested behavior, not an absent upstream capability. Upstream b11057
(`59657a613ab0fa4ab327d6c790123dff30bfbd67`) registers `--spec-type` in
[`common/arg.cpp` L4235](https://github.com/ggml-org/llama.cpp/blob/59657a613ab0fa4ab327d6c790123dff30bfbd67/common/arg.cpp#L4235)
and `draft-mtp` in
[`common/speculative.cpp` L37](https://github.com/ggml-org/llama.cpp/blob/59657a613ab0fa4ab327d6c790123dff30bfbd67/common/speculative.cpp#L37).
C0 and C2 also ran on the plan's own runtime, official b11146 (`llama-b11146-bin-macos-arm64.tar.gz`, GitHub asset
digest sha256 `1ad3f9ef…5711`, verified before use). It was unpacked into an isolated trial directory,
outside the staging and production prefixes. The narrative and `gate.json` identify b11214
(`llama-b11214-bin-macos-arm64.tar.gz`, GitHub asset digest sha256 `ea650e93…8219`, recorded as verified
before use) in that isolated trial directory. **Corrected 2026-10-03 (port of #410).**
The co-residency build is unresolved: `coresidency.json` names b11146, while the original
README and PR body name b11214. Startup/version output was not retained; neither build
is selected by this port.

### Worst-case co-residency ([`coresidency.json`](coresidency.json))

All model servers were resident at once and driven concurrently for 96 s under coordinator load:
- **Corrected 2026-10-03 (port of #410).** The li26 C2 profile of Qwen3.8-27B at a 32,768-token
  context; llama.cpp build unresolved between b11146 in the artifact and b11214 in the narrative;
- the memory stack's own Ollama models, `qwen3-embedding:4b` (4.07 GiB) and `qwen3.5-9b-64k` at a 64K
  context (8.38-9.1 GiB);
- the RAG embedder on port 8232, and Qdrant.

| Measure | Result |
| --- | --- |
| 27B generation server peak RSS | 19,436 MiB |
| System free memory | 70% (memory stack resident), 53% (all resident), 54% (after requests), 68% (27B server stopped) |
| Swap during the probe | no further growth (4,977 MB before, 4,953 MB after); this does not establish that the model set never swaps. Corrected 2026-10-03 (port of #410) |
| Memorystatus kills | 0 |
| 27B requests | 4, 0 errors, median 5,556 prompt tokens, median time to first token 21.0 s, median decode 16.2 tokens/s, 177 of 275 drafted tokens accepted |
| 9B memory-LLM requests (Ollama) | 4, 0 errors, median 7.9 tokens/s while sharing the GPU |
| 4B embedding batches (Ollama) | 5, 0 errors, 40 vectors of 2,560 dimensions, median 4.5 s per batch of 8 |

### The one swap event ([`swap-event.json`](swap-event.json))

Swap stayed at 16.81 MB through both C0 runs and the first 16 minutes of C2. At 10:37 it jumped to a peak of
13,934 MB and was back under 6 GB within 40 s. It then drained slowly to about 5 GB. Three loads overlapped in
that minute:
- the li26 C2 server, at 16.9 GiB RSS;
- ai-memory loading its two Ollama models (12.5 GiB), which were absent at 10:36:56 and present at 10:37:56;
- an OmniRoute Next.js production build (`npm run build:release`, between 10:34:40 and 10:38:22 by file birth
  times) for the GPT-6 gateway being installed on this host.

**Corrected 2026-10-03 (port of #410).** The session recorded no memorystatus kills
and reported 0 errors and the same li26 predictions as C0; the aggregates do not
independently verify output equality. Attribution of the swap event to the build
is an inference from temporal overlap in minute samples and file birth times.
No isolating comparison supports a causal claim. The later 4,977→4,953 MB reading
shows only that swap did not grow further.

### Reranker-gate timing for S3 section 5 ([`gate.json`](gate.json))

ai-memory's C4 reranker must answer within 20 s per call at 4-8K-token prompts. These rerank-shaped prompts
were a query plus numbered 600-character passages taken from this repository's own docs; the answers were not
scored. Each local configuration got one warm-up call, then three calls at each size, with one model resident at
a time. **Corrected 2026-10-03 (port of #410).** `gate.json` records the llama.cpp
configurations as b11214; retained startup/version output does not resolve the
co-residency conflict above.

**Corrected 2026-10-03 (port of #410).** Retained conditions are the per-call
timings, `argv_extra`, the narrative's warm-up note and gateway `providerConcurrency 4`
as a configured limit. Complete launch and request parameters, local generation
limits, cache settings, observed concurrency, and probe-driver or payload hashes
are unknown. The gateway note records `max_tokens 64`, but is not a complete
request record. These timings are a **Local integration check** with incomplete
reproducibility, not a reusable host qualification (P2-7).

| Configuration | ~4.4K tokens, median (max) | ~7.5K tokens, median (max) | Over 20 s at ~7.5K |
| --- | --- | --- | --- |
| Qwen3.8-27B UD-Q4_K_M, llama.cpp Metal | 17.6 s (18.0) | 27.9 s (30.0) | 3 of 3 |
| The same with MTP drafting (li26 C2 profile) | 16.9 s (17.4) | 27.1 s (29.1) | 3 of 3 |
| Qwen3.8-27B nvfp4, Ollama 0.34.4 MLX engine | 11.4 s (12.5) | 18.5 s (20.7) | 1 of 3 |
| Production `qwen3.5-9b-64k`, Ollama MLX engine | 3.3 s (3.3) | 5.5 s (5.8) | 0 |
| `ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF@a02f48bb`, llama.cpp `--rerank` (27 and 54 passages) | 0.7 s (0.8) | 1.4 s (1.4) | 0 |
| GPT-6 astra / sol / luna through this Mac's OmniRoute gateway (one 4K and two 8K calls each) | 6.6 / 9.3 / 9.6 s | 5.1 / 7.3 / 6.8 s | 0 |

- **Qwen3.8-27B misses the gate on llama.cpp.** It leads the memory-LLM sweep on AA-LCR, but prompt processing
  dominates at 8K, so on this Mac it cannot meet the gate through llama.cpp. MTP drafting speeds decoding, not
  prefill.
- **Ollama's MLX build is 1.5× faster at prefill,** which is still borderline at 8K.
- **Three options clear the gate here:** the production 9B, a dedicated cross-encoder (about 20× faster than an
  LLM reranker), and GPT-6 through the gateway, which S3 uses for its LLM roles.

## Step 5 guards and findings

**Pin drift, recorded and not fixed** (the request's guard: no re-pin without native evidence):

- **Corrected 2026-10-03 (port of #410). llama.cpp:** C2 was not run on this Mac's b11057 install;
  no help or failure output was retained. Upstream b11057 registers `--spec-type` and `draft-mtp`
  at the source links above. The session ran C2 on b11146 and reported b11214 as the newest build
  on 2026-09-27. Neither trial re-pins macOS, and the co-residency build remains unresolved.
- **codex:** the macOS pin is 0.155.1 and Linux runs 0.157.1. This Mac runs the ChatGPT-bundled
  0.158.0-alpha.2.1.
- **ai-memory:** the macOS pin is 2.3.2 and the hook template names 2.4.1. The running build, `19b6429`
  (a local build reporting 2.4.0), is 46 commits ahead of and 62 behind official v2.4.1, and official
  v2.4.0 is its ancestor.
- **Embeddings:** the memory stack embeds with Ollama `qwen3-embedding:4b` (2,560 dimensions, Q4_K_M,
  through Ollama's bundled llama-server). It consolidates and reranks with `qwen3.5-9b-64k` (nvfp4
  safetensors on Ollama's MLX engine). The pinned RAG profile is llama.cpp embeddinggemma-300M
  (768 dimensions) on port 8232. These are two consumers with two embedding spaces, and both run.

**Other findings.**

- `local.agent-ecosystem.maintenance` last exited 1; it predates this request.
- The Hindsight memory trial cannot use its embedded Postgres on a Mac without Homebrew. The latest
  `pg0-embedded` 0.15.2 ships a macOS Postgres 18.1.0 linked to `/opt/homebrew/opt/openssl@3`. `initdb`
  runs `postgres -V` through `popen` and `/bin/sh`, so macOS strips any `DYLD_*` fallback.
  - The trial resolved this with the macOS profile's own Postgres choice: Apple Container 1.4.1 (the
    Apple-signed, notarized installer, sha256-verified, installed on 2026-09-27) running the official
    `pgvector/pgvector:0.8.6-pg18-trixie` image, pinned by digest.
  - Hindsight 0.10.1 starts against it and both health endpoints return 200.
  - Apple Container's loopback `--publish` proxy dropped Hindsight's migration connections, while the
    container's host-only address worked.
  - This concerns the memory trials, not this request.

**Host value file.** `adoption/hosts/mac-coordinator-64gb-20260925.json` was created for
`tools/adoption/render_config.py` from the measured profile and stays private. Its path keys (`HOME`,
`ECO_ROOT`, `PROJECT_ROOT`, `HOST_PATH`, `CODE_INDEX_PATH`, `EMBED_MODEL_PATH`) all carry this host's
personal paths, so under the request's own rule it is not committed.

## What is not claimed

- No li26 parity with the workstation, and no replacement or serving-profile decision for this host.
- No retrieval-quality comparison of embedders or memory systems. Those belong to the S3 preregistration
  (#390), which runs only after it freezes.
- The b11146 runtime is a trial install. It is not a new macOS pin.
- **Corrected 2026-10-03 (port of #410).** No host acceptance, no qualification,
  no host-roles change, and no transfer of these numbers to the workstation or
  the new-WSL target.

## Files

| File | What it is |
| --- | --- |
| `README.md` | this summary, Corrected 2026-10-03 (port of #410) |
| `embed-acceptance.json` | the acceptance output, the model, the Metal lines from the startup log, and the launchd state before step 1 |
| `capacity.json` | llama-bench results, serving timings, memory snapshots and the jetsam classification |
| `li26-mac-descriptive.json` | the session's aggregate li26 descriptive summary; independent re-derivation is unavailable without retained per-filing rows and private-run hashes. Corrected 2026-10-03 (port of #410) |
| `li26_mac_descriptive.py` | scores the private runs with the frozen `analyze.py` functions |
| `coresidency.json` | the worst-case co-residency probe |
| `gate.json` | reranker-gate timing per candidate model and runtime, including GPT-6 through this Mac's OmniRoute gateway |
| `swap-event.json` | the one swap event: timeline, what was co-resident, and the OmniRoute build window from file birth times |
| `li26-window-samples.json` | minute samples of co-resident Ollama models, free memory and swap while the li26 runs were active |
| `port-record-20261003.md` | provenance, scope comparison, correction status and reopening requirements. Corrected 2026-10-03 (port of #410) |
