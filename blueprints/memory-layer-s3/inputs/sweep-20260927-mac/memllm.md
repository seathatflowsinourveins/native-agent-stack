<!-- Committed verbatim from PR #390 comment https://github.com/seathatflowsinourveins/native-agent-stack/pull/390#issuecomment-5856547320 (posted 2026-09-27T14:04:30Z by the mac-coordinator-64gb-20260925 session). S3 section 2: discovery input only; vendor-reported numbers are motivation, never S3 evidence. -->

**S3 input from mac-coordinator-64gb-20260925, 2026-09-27: `memllm` sweep table** (suggested path: `inputs/sweep-20260927-mac/memllm.md`). Sonnet sweep, independently verified by an Opus pass against primary sources; its "Verification" section lists every correction applied. The published and self-reported numbers here are discovery evidence, not S3 evidence.

<details><summary>Table</summary>

# Local memory-LLM sweep, 2026-09-27 (since 2026-07-01, emphasis last 4-6 weeks)

## Verification (2026-09-27, independent Opus pass)
- Gemma-4 license: removed the "custom Gemma terms" caveat everywhere it appeared (rows 2 and 6, Unknowns, ranking (a) items 2/3) - `license_link` redirects to a plain "Apache License 2.0" page, and the card body itself says "License: Apache 2.0". Source: verify/memllm/raw/gemma_4_license.html (canonical `ai.google.dev/gemma/apache_2`), verify/memllm/raw/README_google_gemma-4-26B-A4B-it.md, verify/memllm/raw/api_google_gemma-4-26B-A4B-it.json (`cardData.license_link`).
- LFM2.5-8B-A1B does have an Ollama tag (row 1, ranking (a) item 1): `lfm2.5:8b` and `lfm2.5:8b-a1b-q4_K_M` both resolve; added the LFM Open License v1.0 terms (US$10M revenue threshold incl. >=50%-controlled affiliates, free non-commercial/local use, automatic termination on breach). Source: verify/memllm/raw/ollama_lfm2.5_tags.html, ollama_lfm2.5_8b_manifest.json; verify/memllm/raw/LICENSE_LiquidAI_LFM2.5-8B-A1B (Sections 1, 5, 11).
- granite-4.2-8b BFCL v4 corrected to 52.39 at the pinned revision f8de16cdcdbc6c779ca517604e050d82cc119e44 (row 3, Sources, ranking (a) item 3) - 50.29 was a superseded 2026-08-18 card. Source: verify/memllm/raw/commits_granite8b.json (commit dated 2026-08-18T19:55:56Z superseded by 2026-09-04T21:02:25Z), verify/memllm/raw/src_eesel.html ("8B is close enough (52.39 BFCL...)").
- Granite speed (row 4, Unknowns, ranking (b) item 3): granite-4.2-30b is 76.6 tok/s on Artificial Analysis's hosted API (not Mac), AA's own label "slower than average" - not "notably slow, 28 tok/s"; granite-4.2-8b is 84.9 tok/s (Unknowns). "Notably slow" is AA's wording for Qwen3.8 (xhigh) at 45.5 tok/s. Source: verify/memllm/raw/src_aa_gr30.html, src_aa_gr8.html, src_aa_qwen38.html (each page's own stat tile).
- Dropped "the only hard instruction-following number" (ranking (a) item 1): Liquid's own comparison card gives Gemma-4-26B-A4B-it IFEval 91.40/IFBench 47.25; AA independently records Gemma IFBench 72.4/45.4 and LFM2.5-8B-A1B approx 55.7. Source: verify/memllm/raw/README_LiquidAI_LFM2.5-8B-A1B.md (Knowledge-and-instruction-following table); verify/memllm/raw/src_aa_gemma26.html (embedded chart JSON, `ifbench` field).
- Credited "Qwen3.8 beats all medium models / ties DeepSeek-V4-Flash" (row 5, ranking (b) item 1) to a Hacker News comment on an older Intelligence Index scale, not to Artificial Analysis. Source: verify/memllm/raw/src_hn.html (https://news.ycombinator.com/item?id=49334544).
- LFM2.5-8B-A1B (public 2026-05-28, row 1) and Gemma-4-26B-A4B-it (public by 2026-04-01, row 2) flagged as released before this sweep's since-2026-07-01 window; only their later touches (Aug/Jul) fall inside it. Source: verify/memllm/raw/api_LiquidAI_LFM2.5-8B-A1B.json, api_google_gemma-4-26B-A4B-it.json (`createdAt`).
- Replaced the "AA-LCR unrecoverable" unknown with the recovered AA-LCR v1.1 scores, reproducing the baseline's Qwen3.5-9B 46.0/70.0, Qwen3.6-35B-A3B 64.3/71.7 and Nemotron 60.3 exactly as a cross-check (Unknowns; rows 2, 4, 5, 6; ranking (b) fully rewritten on this metric). Source: verify/memllm/aa_lcr_parsed.tsv.
- Rewrote ranking (b) in full on AA-LCR (the table's own deciding metric for that role): new order Qwen3.8-27B > Gemma-4-26B-A4B-it > granite-4.2-30b; only Qwen3.8-27B beats both the control and the trial. Re-decided ranking (a)'s #2/#3 now that Gemma's license caveat is gone: Gemma-4-26B-A4B-it moves to #2 on this role's own stated discriminator (throughput: 3.8B active vs granite-8b's 8.8B fully dense), granite-4.2-8b to #3; reasons stated inline. Source: verify/memllm/aa_lcr_parsed.tsv plus the row-level sources above.

Method: Hugging Face API (`/api/models?author=...&sort=createdAt`, then per-repo `/api/models/{id}` for
sha/lastModified/license/gated/safetensors.total, then `resolve/main/config.json`) for architecture;
llama.cpp b11057 = commit `59657a613ab0fa4ab327d6c790123dff30bfbd67` (GitHub tree + raw conversion/*.py at that
commit, matches the catalog pin exactly); Ollama support = `HEAD registry.ollama.ai/v2/library/<name>/manifests/<tag>`
(200/404, read-only, no pull); WebSearch for AA/IFEval/BFCL; primary LICENSE/README/commit-history reads for the
flagged claims below. All revisions are 40-hex shas observed now via the HF API on 2026-09-27 (see Revisions).
Q4/Q8 sizes are exact GGUF blob bytes from `?blobs=true` unless marked otherwise.

**Correction after review:** `config.json` shows the *production control* Qwen3.5-9B is itself
`Qwen3_5ForConditionalGeneration` / pipeline_tag `image-text-to-text` (same wrapper class as Qwen3.8-27B). "VL-wrapped"
is dropped as a loss reason for Qwen3.8-27B and softened for Gemma-4-26B-A4B - not a differentiator from the running control.

## Baseline (catalogs/foundation/memory-stack-20260925.json, non_repository_decisions, role "Memory LLM")

| Model | Repo | Date | Params | License | Mac artifact | Evidence |
|---|---|---|---|---|---|---|
| Qwen3.5-9B (**retain**, control) | Qwen/Qwen3.5-9B | 2026-03-02 | 9B, `qwen3_5`, image-text-to-text tag | Apache-2.0 | Ollama qwen3.5:9b-mlx `203e30078279` / prod tag qwen3.5-9b-64k `5efc0dd55d4a` | D: AA-LCR 46.0 / 70.0(reason). DV LongBench-v2 55.2 |
| Qwen3.6-35B-A3B (**trial**) | Qwen/Qwen3.6-35B-A3B | 2026-04-24 | 35B/A3B MoE | Apache-2.0 | Ollama qwen3.6:35b-a3b `096fdbd02fe6`(GGUF 22.6GB)/-nvfp4 `e92a3e94bbca`(MLX 23.6GB) | D: AA-LCR 64.3/71.7 (+18.3 vs control). No LongMemEval |
| LFM2.5-2.6B (**trial**) | LiquidAI/LFM2.5-2.6B-GGUF | 2026-09-22 | 2.6B dense | LFM1.0 (custom, flag) | no Ollama tag (404) | DV IFStruct 85.49; 220 tok/s M5 Max CPU |
| Nemotron-3.5-Lightning-30B-A3B (**defer**) | nvidia/...-BF16 | 2026-08-24 | 30B/A3B MoE | OpenMDW-1.1 | Ollama nemotron-3.5-lightning:30b-a3b `e7a64ff15fb1` | D: AA-LCR 60.3(reason only). DV 52.0. **In-window artifacts**: Base-BF16 (08-05), NVFP4/DSpark/DFlash (08-04/05) - Blackwell NVFP4 only, no new Mac evidence, decision unchanged |
| MemReader-4B-thinking (**reject**) | IAAR-Shanghai/MemReader-4B-thinking | 2026-04-08 | 4B | Apache-2.0 | - | DV LongMemEval 83.0% (4-tool pipeline, not standalone) |

## New finds since 2026-07-01, in 3-35B class, text-capable (sorted by suitability)

| # | Model | Date (created/lastMod) | Params | License | Mac artifact | llama.cpp b11057 | Q4/Q8 (exact bytes) | Ctx | Key evidence |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **LFM2.5-8B-A1B** | 2026-05-28/08-24 (public 2026-05-28, before this sweep's since-2026-07-01 window; only the Aug touches fall inside it) (DSpark 08-10, DSpark-GGUF 08-19) | 8.47B/~1.5B active MoE (`Lfm2MoeForCausalLM`, 32 experts×top4) | **LFM Open License v1.0**: Commercial Use is unlicensed for a Legal Entity (including affiliates it controls, or that control it, at >=50% ownership) at or above US$10,000,000 annual revenue; non-commercial or local use is free regardless of revenue; any breach terminates the licence automatically | official GGUF+MLX(4/5/6/8bit,bf16)+ONNX+unsloth mirror; **Ollama tag confirmed: `lfm2.5:8b` and `lfm2.5:8b-a1b-q4_K_M` both resolve (200) — corrects the earlier 404 finding** | `Lfm2MoeForCausalLM` registered, conversion/lfm2.py:97 | 5.16GB/9.01GB | 128k | D/DV: IFEval 91.84 (+12.4 over LFM2-8B-A1B's 79.44); vendor claims IFEval parity w/ Gemma-4-26B-A4B. No LongMemEval. AA-LCR: 0 recorded on Artificial Analysis (a literal zero, not a missing value — genuineness unverifiable) |
| 2 | **Gemma-4-26B-A4B-it** | 2026-03-11/07-20 (public by 2026-04-01, before this sweep's since-2026-07-01 window; only the 07-20 touch falls inside it) | 25.2B/3.8B active MoE (`Gemma4ForConditionalGeneration`, 128 experts×top8) | Apache-2.0, plain: the README's `license_link` (`ai.google.dev/gemma/docs/gemma_4_license`) redirects to `ai.google.dev/gemma/apache_2` ("Apache License 2.0"), and the card's own body text reads "License: Apache 2.0" - **corrects the earlier custom-Gemma-terms caveat; no restriction beyond Apache-2.0** | official Google QAT Q4_0 GGUF (14.44GB text+1.19GB mmproj); **ggml-org/gemma-4-26B-A4B-it-GGUF**; **lmstudio-community** GGUF+MLX-4bit; **Ollama gemma4:26b (200)** | `Gemma4ForConditionalGeneration` registered, conversion/gemma.py:631 | Q4(official QAT Q4_0)=14.44GB+1.19GB mmproj; Q8(ggml-org, exact)=26.86GB+0.81GB mmproj | 260k | D: AA Intelligence Index v4.3.2 (reasoning, est.) ~17 - different benchmark version than baseline's plain AA-LCR. **AA-LCR v1.1 recovered on verification: 65.7 (reasoning) / 42.3 (non-reasoning)** - see Unknowns. D-third-party (dev.to/aurigait): "a July 2026 refresh" reportedly cut JSON/parameter errors (Tau2 Telecom +10.1%, TB2 +4.5% on sibling 31B) - **checked the repo's own commit log: the 07-20 commit is "Add response_template to tokenizer_config.json," 07-15 is a chat-template fix ("null handling, reasoning preservation, turn-tag balance, input validation"); these are template/config commits consistent with, but not confirmed as, the specific change the third-party figures describe**. Sibling Gemma-4-31B: 0.798 Value-Accuracy, independent Structured-Output-Benchmark (arXiv 2604.25359). Liquid's own comparison card also lists this model's IFEval 91.40 / IFBench 47.25; Artificial Analysis independently records IFBench 72.4 (reasoning) / 45.4 (non-reasoning) |
| 3 | **granite-4.2-8b** | 2026-08-07/09-04 | 8.79B dense (`GraniteForCausalLM`) | Apache-2.0 | official ibm-granite GGUF+MLX(4/6/8bit); **lmstudio-community** GGUF+MLX; **Ollama granite4.2:8b (200)** | `GraniteForCausalLM` registered, conversion/granite.py:17 (long-supported) | 5.35GB/9.35GB | 128k | DV: BFCL v4 tool-calling **52.39** at the pinned revision (f8de16cdcdbc6c779ca517604e050d82cc119e44, 2026-09-04) - corrects 50.29, which was a superseded 2026-08-18 card; eesel.ai's independent review reports 52.39 too; native "reason-before-call" tool design; thinking on/off switch |
| 4 | **granite-4.2-30b** | 2026-08-07/09-04 | 29.28B dense | Apache-2.0 | same coverage; **Ollama granite4.2:30b (200)** | registered, same class | 17.72GB/31.11GB | 128k | DV: BFCL v4 **61.39** (best of new finds). D (Artificial Analysis hosted API, not a Mac measurement): 76.6 tok/s, AA's own tier label is "slower than average" - corrects an earlier "notably slow, 28 tok/s" misreading; AA reserves "notably slow" for Qwen3.8 (xhigh) at 45.5 tok/s, not this model. **AA-LCR v1.1 recovered on verification: 49.0** - see Unknowns. Latency risk vs the 20s gate remains (fully dense, no MoE discount), just less severe than 28 tok/s implied |
| 5 | **Qwen3.8-27B** | 2026-08-05/08-14 | 27.78B dense, `Qwen3_5ForConditionalGeneration` (**same wrapper class as the production control**) | Apache-2.0 | unsloth+lmstudio-community GGUF(Q4_K_M-UD 16.46GB/Q8_0 29.05GB, exact)+MLX(4/5/6/8bit); **Ollama qwen3.8:27b (200)** | `Qwen3_5ForConditionalGeneration`/`Qwen3_5MoeForCausalLM` registered, conversion/qwen.py:637,643 | 16.46GB/29.05GB (exact) | 260k | D: AA Intelligence Index (xhigh) 34 - composite index, not plain AA-LCR. **AA-LCR v1.1 recovered on verification: 82.0 (xhigh) / 79.7 (medium) / 77.3 (low reasoning), 69.3 (non-reasoning)** - the only new find that beats both the control (46.0/70.0) and the trial (64.3/71.7) on AA-LCR, on both axes; see Unknowns. "Beats all medium 40-150B models, ties DeepSeek-V4-Flash-0731(304B)" is a Hacker News comment's reading of an older Intelligence Index scale (news.ycombinator.com/item?id=49334544), not an Artificial Analysis claim |
| 6 | **Gemma-4-12B-it** | 2026-05-23/07-20 | 11.96B dense, omni (`Gemma4UnifiedForConditionalGeneration`) | Apache-2.0, plain (same correction as row 2 - the license_link caveat is resolved, not a restriction) | official Google QAT Q4_0 GGUF (6.98GB+0.175GB mmproj); **ggml-org/gemma-4-12B-it-GGUF**; **lmstudio-community** GGUF+MLX-4bit+QAT-GGUF; **Ollama gemma4:12b (200)** | `Gemma4UnifiedForConditionalGeneration` registered, conversion/gemma.py:812,933 | Q4(official QAT)=6.98GB+0.175GB; Q8(ggml-org,exact)=12.67GB+0.159GB | 260k | D: AA Intelligence Index non-reasoning 20 / reasoning 14 (v4.3.2, not plain AA-LCR). AA has a direct release-comparison page vs Qwen3.5-9B (Sources). Closest in-class size analogue to the control. **AA-LCR v1.1 recovered on verification: 63.7 (reasoning) / 35.0 (non-reasoning)** - see Unknowns |
| - | granite-swash-3b-a600m (excluded: base-only, short ctx) | card date 2026-07-07 | 3.02B/0.598B active MoE (`GraniteMoeSWAForCausalLM`, 48×top4, SWA+sinks) | Apache-2.0 | none found | `GraniteMoeSWAForCausalLM` registered, conversion/granite.py:124 | n/a | **8192 only** | README states verbatim: "early exploration...small-scale preview for upcoming Granite series," explicitly a **base model, not instruct** - JSON/tool reliability unproven |
| - | ContextPilot-14B/8B/E4B (excluded: license) | 2026-08-27/08-31 | 14.77B dense (`Qwen3ForCausalLM`) | **LICENSE file read directly (primary source, not a paraphrase): body is Apache License 2.0 text with an added "Section 0": "ContextPilot-14B is made available solely for the purpose of scientific research and development. You shall not use it for any other purpose." Hard research-only restriction, confirmed, blocks adoption** | community-only: bartowski/mradermacher GGUF (not ggml-org/unsloth/lmstudio-community); no Ollama tag (404) | `Qwen3ForCausalLM` long-supported | - | 40960 native | DV, likely self-reported (arXiv 2608.28476, Tencent authors): 72.20 avg on 4 long-context benchmarks. On-theme (proactive context mgmt, structured memory, retrieval, "soft context offloading") but license-blocked |
| - | Nemotron-Labs-Audex-30B-A3B (excluded: wrong modality) | created 2026-07-06 | ~30B (shards) | other | - | - | - | - | File tree = whisper/audiogen/VAE/speech-decoder shards - **audio S2S system, not a text memory LLM** despite MoE-like name |
| - | granite-4.2-3b (in-class, not ranked - too small for consolidation, notable for extraction speed) | 2026-08-07/09-02 | 3.66B dense | Apache-2.0 | official+lmstudio-community GGUF/MLX; Ollama tag not probed | registered | 2.24GB/3.89GB | 128k | Same family as rows 3-4, no separate benchmark found |

## Oversized "Flash"-branded releases this window (excluded on total-footprint alone; 64GB unified memory)

| Model | Date | Total params (safetensors, exact) | License tag |
|---|---|---|---|
| Qwen/Qwen3.8-Flash-Next | 2026-08-24/27 | 180.0B | other |
| zai-org/GLM-5.3-Flash | 2026-08-25/09-07 | 321.3B | mit (tag) |
| zai-org/GLM-5.3 | 2026-08-25/09-04 | 753.3B | other |
| deepseek-ai/DeepSeek-V4-Flash-0731 | 2026-07-31/08-01 | 304.2B | mit (tag) |
| XiaomiMiMo/MiMo-V2.6-Flash-RL | 2026-09-21/22 | 310.8B | mit (tag) |

## Memory-specialised releases: dedicated sweep

Searched: (1) `IAAR-Shanghai` (MemReader-4B-thinking's org) full listing; (2) `search=MemReader`; (3) `search=memory&pipeline_tag=text-generation`,
filtered `createdAt>=2026-07-01`, limit 100. Results: IAAR-Shanghai's own follow-up to MemReader is **MemPrivacy-4B/1.7B-RL/SFT** (2026-05-08/09,
privacy-focused, not extraction/consolidation) and **MemReranker-4B** (2026-04-27, a `text-classification` cross-encoder, not a generative LLM) -
both predate the window; IAAR-Shanghai's only in-window releases are Metis-4B/9B/27B (VL, 2026-07-16, no memory framing). The generic memory-keyword
search surfaced ~35 in-window hits, all small independent/research repos with no vendor backing or benchmark evidence meeting the "serious" bar:
domain-siloed SFT variants (`Jiarui-Wang/MemSFT-Qwen3-{Bio,Law,OpenSWI}-Memory-{1.7B..8B}`, 2026-08-01), architecture probes
(`Rubin-Wei/MemoryDecoder-{OLMo,Qwen3,Pythia}-*`, 2026-07-23), and single-author projects (`Jepoxy/LFM2.5-350M-Memory-Extractor`,
`vtava/Laya-MemoryFusion-*`, `OLAResearchX/memoryathena-*`). None outranks ContextPilot (above, license-excluded) or the generalist rows 1-6 on
any documented metric. **No serious vendor-backed memory-specialised LLM release found in-window beyond ContextPilot.**

## Orgs checked with nothing new/relevant since 2026-07-01

- **openai**: gpt-oss-20b/120b unchanged since 2025-08-26 (lastModified); no successor in any window.
- **moonshotai**: only Kimi-K3 touched (lastMod 2026-09-02, createdAt 2026-06-13, pre-window, VL, oversized).
- **meta-llama**: nothing since Llama-4/Llama-Guard-4 (2025-04/05); stalest org checked.
- **baidu**: nothing since ERNIE-4.5 updates (2025-11-26); latest any touch is an OCR model (2026-07-29).
- **stepfun-ai** (org is `stepfun-ai`, not `stepfun`): nothing since Step-3.7-Flash (2026-05-23, VL, pre-window).
- **allenai**: only climate/science models in window (ACE2S, SamudrACE) - no LLM.
- **google, tencent, nvidia, zai-org, deepseek-ai, XiaomiMiMo**: covered above; remainder of their Aug-Sep 2026 output is OCR/embedding/rerank/UI-agent/TTS/robotics/vision, not general memory LLMs.

## Revisions (40-hex, HF API `.sha`, resolved 2026-09-27)

Baseline: Qwen/Qwen3.5-9B `c202236235762e1c871ad0ccb60c8ee5ba337b9a` · Qwen/Qwen3.6-35B-A3B `995ad96eacd98c81ed38be0c5b274b04031597b0` ·
LiquidAI/LFM2.5-2.6B-GGUF `e7caca5d835a3901a8e0d63e94009429bafafdfc` (base LiquidAI/LFM2.5-2.6B `654f9463ce32b05d0429d76fe1f580b27d4c1ac0`) ·
nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16 `a9904d24bcc1d289a1950fa9d2b978c47cf903b9` · IAAR-Shanghai/MemReader-4B-thinking `3fcb57e5653ec5d733eea4df61f4b339d4ac0e92`

New finds: LiquidAI/LFM2.5-8B-A1B `5dd22602c2e9f6a097b1de4c4efe0658b605015c` · google/gemma-4-26B-A4B-it `4d7ae4984b7db7de8f8457170b3f1a419ee76d52` ·
google/gemma-4-12B-it `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7` · ibm-granite/granite-4.2-8b `f8de16cdcdbc6c779ca517604e050d82cc119e44` ·
ibm-granite/granite-4.2-30b `9e668ce1c538387ef24d3644e9b0606647762636` · ibm-granite/granite-4.2-3b `e459acceac81e5fe67c07d9cfc72329a332e7eb1` ·
Qwen/Qwen3.8-27B `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` · ibm-granite/granite-swash-3b-a600m `568a94fcfeff42a8cab9ee2ffea89fde12071282` ·
tencent/ContextPilot-14B `8eafd8356c5c5e713e92e623c8f1d346de6d0f95` · nvidia/Nemotron-Labs-Audex-30B-A3B `4e7e342045736382ddf3e2952c313847a08642b8`

Oversized: Qwen/Qwen3.8-Flash-Next `de4b8e4d43b917e7706784d8bb445c9af86a3540` · zai-org/GLM-5.3-Flash `eb9eb208eb0d988989d07a6a12d0fdeb5f52574a` ·
zai-org/GLM-5.3 `aca966e4e02791568aa6a4ced368624b3d897f42` · deepseek-ai/DeepSeek-V4-Flash-0731 `7872f01b1d1fe23eabc4c98b48bffcef5a386062` ·
XiaomiMiMo/MiMo-V2.6-Flash-RL `5711b268169967567844e1e560e8a3966da959b1`

llama.cpp b11057 pin: `https://github.com/ggml-org/llama.cpp/tree/59657a613ab0fa4ab327d6c790123dff30bfbd67` (tag `b11057`, matches catalog).

## Sources (by row)

- AA pages: https://artificialanalysis.ai/models/gemma-4-26b-a4b-non-reasoning · https://artificialanalysis.ai/models/gemma-4-26b-a4b ·
  https://artificialanalysis.ai/models/gemma-4-12b-non-reasoning · https://artificialanalysis.ai/models/gemma-4-12b ·
  https://artificialanalysis.ai/models/granite-4-2-30b · https://artificialanalysis.ai/models/granite-4-2-8b ·
  https://artificialanalysis.ai/models/qwen3-8-27b-non-reasoning · https://artificialanalysis.ai/models/qwen3-8-27b ·
  https://artificialanalysis.ai/models/releases/comparisons/gemma-4-12b-vs-qwen3-5-9b (direct control comparison) ·
  https://artificialanalysis.ai/articles/gemma-4-everything-you-need-to-know
- LFM2.5-8B-A1B: https://www.liquid.ai/blog/lfm2-5-8b-a1b · https://benchlm.ai/models/lfm2-5-8b-a1b
- Granite 4.2: https://huggingface.co/blog/ibm-granite/granite-4-2 · https://github.com/ibm-granite/granite-4.2-language-models ·
  https://www.eesel.ai/blog/granite-4-2-review (BFCL v4 52.41/52.39/61.39, IBM-reported; corrects the earlier 50.29 for the 8B, superseded 2026-08-18 card; 52.41 not independently attributed to a specific row in this sweep)
- Gemma-4 JSON refresh (third-party, not confirmed against the primary commit log - see row 2 caveat):
  https://dev.to/system_rationale/part-3-making-gemma-4-agents-production-ready-guardrails-structured-outputs-and-self-healing-575n ·
  https://aurigait.com/blog/gemma-4-features-benchmarks-guide/
- Structured Output Benchmark (independent, Gemma-4-31B 0.798): https://arxiv.org/pdf/2604.25359
- ContextPilot: https://huggingface.co/tencent/ContextPilot-14B/raw/main/LICENSE (primary, read directly) · https://arxiv.org/html/2608.28476v1
- Qwen3.8-27B composite-score corroboration: https://news.ycombinator.com/item?id=49334544

## Unknowns / evidence gaps

- **AA-LCR v1.1 recovered on verification** (the client-side-rendered score the first pass could not extract via curl) - recovered directly from the Artificial Analysis page data, not re-derived: Qwen3.5-9B (control) 46.0/70.0(reason), Qwen3.6-35B-A3B (trial) 64.3/71.7, Nemotron-3.5-Lightning 60.3(reason only) all reproduce the baseline/table exactly, cross-validating the recovery method. New finds: Qwen3.8-27B 82.0 (xhigh) / 79.7 (medium) / 77.3 (low reasoning), 69.3 (non-reasoning); Gemma-4-26B-A4B-it 65.7 (reasoning) / 42.3 (non-reasoning); Gemma-4-12B-it 63.7 (reasoning) / 35.0 (non-reasoning); granite-4.2-30b 49.0; granite-4.2-8b 45.0; LFM2.5-8B-A1B 0 (recorded, a literal zero - genuineness unverifiable). Only Qwen3.8-27B beats both the control and the trial on this metric; Gemma-4-26B-A4B-it and granite-4.2-30b both trail the control itself now that their scores are known.
- No LongMemEval / consolidation-specific / listwise-reranking benchmark found for any new candidate (same gap the
  baseline records for Qwen3.6-35B-A3B itself).
- LFM2.5-8B-A1B active params: name implies ~1B, Liquid's blog says "~1.5B" - both reported, not reconciled.
- p95 latency at 4-8K tokens (ai-memory's 20s/5%-fallback gate) was not measured for any candidate; qualitative AA
  speed figures (Artificial Analysis's hosted API, not a Mac measurement) are granite-4.2-30b 76.6 tok/s, AA's own
  label "slower than average" (not "notably slow" as an earlier draft had it - AA reserves "notably slow" for
  Qwen3.8 (xhigh) at 45.5 tok/s), and granite-4.2-8b 84.9 tok/s.

## Ranked top 3

### (a) Hindsight/MemPalace extraction (runs on every retain; throughput + JSON reliability dominate)

1. **LFM2.5-8B-A1B**, conditional on clearing the LFM1.0 license gate (free for non-commercial/local use; commercial
   use unlicensed at/above US$10M annual revenue including >=50%-controlled affiliates; any breach terminates it).
   ~1.5B active beats Qwen3.5-9B's 9B-all-active on per-token cost, and IFEval 91.84 is a strong instruction-following
   number (neither baseline model has one on record) - though not the only one surfaced: Gemma-4-26B-A4B-it also
   carries IFEval 91.40/IFBench 47.25 on Liquid's own comparison card, and AA-LCR is now known for this model too
   (0, recorded - genuineness unverifiable). Vs Qwen3.6-35B-A3B: fewer active params still (1.5B vs 3B), a plausible
   speed win, but zero memory/consolidation evidence (the trial 35B-A3B at least has the +18.3 AA-LCR proxy); Ollama
   now carries a tag (`lfm2.5:8b`, confirmed 200 - corrects the earlier 404 finding).
2. **Gemma-4-26B-A4B-it** - the deciding factor for this role is throughput, and it wins that outright: 3.8B active
   vs granite-4.2-8b's 8.8B fully dense (no speed win over the control at all). Now unambiguous Apache-2.0 (the
   license_link caveat is resolved, no longer a differentiator against granite). Carries IFEval 91.40/IFBench 47.25
   on Liquid's own card (AA independently records IFBench 72.4/45.4) - a closer proxy to JSON-instruction reliability
   than granite's tool-calling BFCL. AA-LCR: this model's 65.7 reasoning / 42.3 non-reasoning vs granite-4.2-8b's
   newly-recovered single-mode 45.0 - Gemma ahead on the reasoning comparison, granite slightly ahead against Gemma's
   non-reasoning figure; not a clean win for either, so throughput remains the deciding factor above. Caveat: fits
   this role only at Q4 (14.44GB+1.19GB mmproj) - the Q8 build (26.86GB+)
   exceeds the 35B-A3B trial's own footprint.
3. **granite-4.2-8b** - same size class as Qwen3.5-9B (8.8B vs 9B dense, no speed win over the control), but new
   (Sept 2026), unambiguous Apache-2.0, and ships fresh native tool-calling evidence (BFCL v4 52.39 at the pinned
   revision) the baseline lacks - the only BFCL number of the two. Vs Qwen3.6-35B-A3B: loses the active-compute race
   (8B active > 3B active) - wins only if Mac memory headroom, not latency, is binding (5.35GB vs 22.6GB Q4 on disk).
   Demoted behind Gemma-4-26B-A4B-it now that Gemma's license caveat is gone and this role's own stated discriminator
   (throughput) favors Gemma's MoE by more than 2x.

### (b) ai-memory consolidation/reranking (bounded 20s / <=5% fallback at 4-8K; quality-bound)

**Rewritten on AA-LCR**, which this table calls the deciding metric for this role, now that the v1.1 scores are
recovered (see Unknowns) instead of "not recoverable." Non-reasoning: Qwen3.8-27B 69.3 > trial Qwen3.6-35B-A3B 64.3 >
control Qwen3.5-9B 46.0 > Gemma-4-26B-A4B-it 42.3. Reasoning: Qwen3.8-27B 82.0 > trial 71.7 > control 70.0 >
Gemma-4-26B-A4B-it 65.7 > granite-4.2-30b 49.0. Only Qwen3.8-27B beats both the control and the trial; Gemma and
granite-30b both now measurably trail the control itself, which was hidden while their scores were unknown.

1. **Qwen3.8-27B** - the only candidate that clears the deciding metric: AA-LCR 82.0 (xhigh) / 79.7 (medium) / 77.3
   (low reasoning), 69.3 (non-reasoning), beating both the control (46.0/70.0) and the trial (64.3/71.7) on every
   reasoning tier and non-reasoning. Same qwen3_5 lineage and same `ForConditionalGeneration` wrapper as the
   production control (prompt/tokenizer compatibility, not a new liability - this was confirmed, not assumed), 260k
   context. "Beats all medium 40-150B models" is a Hacker News reading of an older Intelligence Index scale, not an
   AA claim - dropped as evidence here. Open risk: fully dense (27.78B active vs the trial's 3B active), and p95
   latency against the 20s gate is unmeasured for this model on this Mac - the one thing standing between this pick
   and displacing the trial.
2. **Gemma-4-26B-A4B-it** - longer native context (260k) than the control, MoE 3.8B active vs the control's
   9B-all-active, and the widest Mac tooling of any new find (official QAT GGUF + ggml-org + lmstudio-community +
   Ollama tag, vs the control's single Ollama MLX tag); now unambiguous Apache-2.0. On the deciding metric it loses
   to both the control and the trial (65.7/42.3 vs 70.0/46.0 and 71.7/64.3) - a materially weaker position than "no
   AA-LCR number was recoverable" implied - but it still clears granite-4.2-30b by a wide reasoning margin (65.7 vs
   49.0). A third-party JSON-reliability-refresh claim exists for this window but is **not confirmed against the
   primary commit log** (row 2).
3. **granite-4.2-30b** - best tool-calling score of any new find (BFCL v4 61.39), 128k context, unambiguous
   Apache-2.0. On AA-LCR (49.0) it is the weakest of the three role candidates, trailing the control on reasoning by
   21 points. Vs the 35B-A3B trial: similar total disk (30B vs 35B) but **fully dense** (30B active vs 3B active);
   AA's hosted-API speed figure is 76.6 tok/s labeled "slower than average" (not "notably slow" - that label is
   AA's wording for Qwen3.8 xhigh at 45.5 tok/s) - a real but smaller latency risk against the 20s p95 gate than
   the earlier 28 tok/s figure implied, and one the MoE trial does not carry at all.

**Operating point:** at Q4, every ranked row (1-6) fits well under the Qwen3.6-35B-A3B trial's 22.6GB GGUF footprint
(largest is granite-4.2-30b at 17.72GB); at Q8, rows 2 (26.86GB+), 4 (31.11GB) and 5 (29.05GB) exceed it - this is the
memory-headroom argument behind picks (a)#2 and (b)#2, and it only holds at Q4/QAT-Q4_0, not at Q8.

Evidence classes follow the catalog's own D (discovery/independent) / DV (discovery/vendor) convention; every score
above is one or the other, never NCE (no native Mac harness run was performed in this sweep).

</details>
