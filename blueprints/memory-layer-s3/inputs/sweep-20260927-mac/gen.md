<!-- Committed verbatim from PR #390 comment https://github.com/seathatflowsinourveins/native-agent-stack/pull/390#issuecomment-5856547532 (posted 2026-09-27T14:04:32Z by the mac-coordinator-64gb-20260925 session). S3 section 2: discovery input only; vendor-reported numbers are motivation, never S3 evidence. -->

**S3 input from mac-coordinator-64gb-20260925, 2026-09-27: `gen` sweep table** (suggested path: `inputs/sweep-20260927-mac/gen.md`). Sonnet sweep, independently verified by an Opus pass against primary sources; its "Verification" section lists every correction applied. The published and self-reported numbers here are discovery evidence, not S3 evidence.

<details><summary>Table</summary>

# Local-generation model sweep, 2026-08-01 to 2026-09-27 (revised after review)

## Verification (2026-09-27, independent Opus pass)
- Nemotron-3.5-Lightning-30B-A3B KV at 32K recomputed from the real layer split (6 attention / 23 mamba / 23 moe of 52 layers, 2 kv heads x head_dim 128) instead of an all-52-layers-as-attention upper bound: 0.20GB, not <=1.74GB; total revised to approx 27.0GB (25.27 + 0.20 + 1.49), below granite-4.2-30b's 27.8GB, so the two rows are swapped into ascending-fit order and the "KV split not resolved" unknown is removed. Source: verify/gen/cfg_nemotron_bf16.json (`layers_block_type`).
- Corrected the two HF slugs that 401 under their short form to the slugs that actually resolve: nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16 and prism-ml/Ternary-Bonsai-2-27B-gguf. Source: verify/gen/api_nvidia_NVIDIA-Nemotron-3.5-Lightning-30B-A3B.json and api_prism-ml_Ternary-Bonsai-2-27B.json (both `{"error":"Invalid username or password."}`) vs. api_nvidia_NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16.json / api_prism-ml_Ternary-Bonsai-2-27B-gguf.json (both resolve).
- Bonsai 2 27B: stock llama.cpp rejects the shipped PQ2_0/PTQ1_0 files outright (unknown types); "garbage output" is specific to the separate, generic Q2_0 type it silently loads with no Hadamard runtime — these are not the same claim. Added the card's own M5 Pro throughput (approx 28 tok/s), the Mac target chip, ahead of the M5 Max aside. Source: verify/gen/readme_bonsai2_27b_gguf.md lines 139-141 (rejection wording), 191 and 206 (M5 Pro tok/s).
- Qwen3.8-27B's "smallest 32K footprint" claim qualified to "among rows with a worked-out KV" — Muse-Glimmer-30B's KV was never resolved in this sweep, so it is not a counted comparison (see this table's own Unknowns).
- Newest llama.cpp tag is b11214 (2026-09-27T12:45:21Z); reconfirmed Xing4_0ForCausalLM absent at both b11146 and b11214 via a fresh architecture-registry scan (previously only checked at b11057/b11214). Source: verify/gen/archs_b11146.txt, archs_b11214.txt, scan2_b11146.txt, scan2_b11214.txt (0 files contain `xing4` at either tag).
- Hosted models: confirmed claude-opus-5-5 (releasedOn 2026-09-22) and claude-fable-5-1 (releasedOn 2026-09-01) directly against the Anthropic docs' embedded page JSON; sharpened the OpenAI entry to state the docs page itself carries no release-date field for gpt-6-sol/gpt-6-luna (only knowledge-cutoff dates), and that 2026-09-22 is CNBC/secondary-source only. Source: verify/gen/anth_models_opus-5-5_overview.html, anth_about-claude_models_overview.html (`\"releasedOn\":\"2026-09-22\"`, `\"releasedOn\":\"2026-09-01\"`); verify/gen/oai_developers.openai.com_api_docs_models.html.

Mac target: M5 Pro, 64GB unified memory, about 53 GiB Metal-available, budget about 40GB at Q4 including KV for 32K context.
llama.cpp floor: b11057. Diffed against b11214 (2026-09-27T12:45:21Z, newest tag at sweep time); only 2 new HF-arch registrations appeared between them (BailingMoeV3VL, Gemma4DSparkModel), neither relevant here.
Method: HF API createdAt-desc sweep of 18 orgs (plus corrected slugs stepfun-ai, prism-ml, XingChen-AGI), then a second lastModified-desc sweep of the same 18 to catch updates to pre-window repos (44 hits reviewed, listed below).
Evidence labels: [doc]=publisher documentation/card, [obs]=observed this session (HF API/config/tree/Ollama fetch), [self]=publisher-reported benchmark, [vendor-harness]=publisher-run but against third-party baselines, [unk]=not verified this session.
Release date vs createdAt: HF repo createdAt often precedes the publisher-stated public Release Date on the card. Where the card states one, both are given.

## Sorted by Mac fit, ascending estimated total footprint within each bucket

| Model | Org (in 18-list?) | Repo created [obs] | Card Release Date [doc] | Revision (sha, 12-hex) | Total / Active params [obs] | License [obs+doc] | Mac artifact | Ollama tag [obs] | llama.cpp arch @ b11057 [obs] | Q4 weight | KV f16 @32K | Total est | Fit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ibm-granite/granite-4.2-3b | ibm-granite (yes) | 2026-08-07 | unk | e459acceac81 | 3.66B dense | apache-2.0 | Official GGUF + official MLX | granite4.2:3b, 2.2GB | GraniteForCausalLM: yes | 2.24GB [obs] | 2.68GB | 6.4GB | Fits comfortably |
| tencent/ContextPilot-E4B | tencent (yes) | 2026-08-27 | unk | a7ba41c18ddc | 7.94B (Gemma4 MatFormer effective-4B) | Tencent custom LICENSE file (HF tag: other) | mradermacher GGUF (i1 imatrix) | none found | Gemma4ForConditionalGeneration: yes | 5.30GB [obs] | not resolved, nested config | approx 8-9GB | Fits comfortably |
| tencent/ContextPilot-8B | tencent (yes) | 2026-08-27 | unk | 595abeaed72e | 8.19B dense (Qwen3-8B base) | Tencent custom LICENSE file (HF tag: other) | mradermacher GGUF (i1 imatrix) | none found | Qwen3ForCausalLM: yes | 5.03GB [obs] | 4.83GB | 11.4GB | Fits comfortably |
| XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B | XiaomiMiMo (yes) | 2026-09-21 | unk | 2367e865d009 | 9.41B (Qwen3.5-9B distill) | mit | bartowski+ggml-org GGUF, mlx-community 4bit | none found | Qwen3_5ForConditionalGeneration: yes | approx 5.6GB (Q4_K_M est; Q8_0 used in baseline test) | approx 4.8GB | approx 11-12GB | Fits comfortably; ALREADY TESTED, see note |
| ibm-granite/granite-4.2-8b | ibm-granite (yes) | 2026-08-07 | unk | f8de16cdcdbc | 8.79B dense | apache-2.0 | Official GGUF + official MLX | granite4.2:8b, 5.3GB | GraniteForCausalLM: yes | 5.35GB [obs] | 5.37GB | 12.2GB | Fits comfortably |
| tencent/ContextPilot-14B | tencent (yes) | 2026-08-27 | unk | 8eafd8356c5c | 14.77B dense (Qwen3-14B base) | Tencent custom LICENSE file (HF tag: other) | mradermacher + bartowski GGUF | none found | Qwen3ForCausalLM: yes | 9.00GB [obs] | 5.37GB | 15.9GB | Fits comfortably |
| meta-models/Muse-Glimmer-30B (NOT in 18-org list) | meta-models | 2026-08-09 | unk | a4e59da52a7b | 29.78B (nested config) | apache-2.0 | unsloth GGUF, mlx-community 8bit | none found | MuseGlimmerForConditionalGeneration: yes | 15.88GB [obs, UD-Q4_K_XL] | not resolved | approx 18-20GB | Fits comfortably; NO benchmark gathered |
| Qwen/Qwen3.8-27B (REFERENCE: existing default, in-window release) | Qwen (yes) | 2026-08-05 | unk | 1d4bf0f2ff60 | 27.78B, HYBRID attention (16 of 64 layers full-attention, interval 4; rest linear/SSM-style with O(1) state) | apache-2.0 | Official; unsloth GGUF (proven quant) | qwen3.8:27b, 18GB | Qwen3_5ForConditionalGeneration: yes (proven) | 16.46GB [obs, unsloth UD-Q4_K_M] | approx 2.15GB (only 16 full-attn layers, 4 kv heads, head_dim 256; linear layers add a small constant state, not context-scaling) | approx 20.1GB | Fits comfortably; smallest 32K footprint among rows with a worked-out KV in the approx 27-30B class here (Muse-Glimmer-30B's KV is not worked out, so it is not a counted comparison) |
| nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16 | nvidia (yes) | 2026-08-01 | 2026-08-11 [doc, card Release Date field] | a9904d24bcc1 | 31.58B total / 3B active, hybrid Mamba+MoE (NemotronH) | OpenMDW-1.1 | unsloth/bartowski/ggml-org/lmstudio-community GGUF (no official) | nemotron-3.5-lightning:30b-a3b, 25GB | NemotronHForCausalLM: yes | 25.27GB [obs, unsloth UD-Q4_K_M] | 0.20GB [obs, config `layers_block_type`: 6 attention / 23 mamba / 23 moe of 52 layers; 2 kv heads x head_dim 128, only the 6 attention layers scale with context] | approx 27.0GB (25.27 + 0.20 + 1.49) | Fits comfortably; below granite-4.2-30b's 27.8GB at 32K, but still 6.9GB above Qwen/Qwen3.8-27B's 20.1GB two rows up - not the smallest of the class |
| ibm-granite/granite-4.2-30b | ibm-granite (yes) | 2026-08-07 | 2026-08-25 [doc, card Release Date field] | 9e668ce1c538 | 29.28B dense | apache-2.0 | Official GGUF + official MLX, also lmstudio-community/bartowski/mradermacher | granite4.2:30b, 18GB | GraniteForCausalLM: yes | 17.72GB [obs] | 8.59GB (plain GQA, all 64 layers full-attention; no hybrid discount) | 27.8GB | Fits comfortably; costs approx 7.7GB MORE than Qwen3.8-27B at 32K despite similar weight size |

### runtime_unsupported (mainline llama.cpp b11057 or b11214)

| Model | Org | Created [obs] | Revision | Params | License | Why unsupported | Note |
|---|---|---|---|---|---|---|---|
| XingChen-AGI/Xing4.0-29B-A4B (NOT in 18-org list) | XingChen-AGI | 2026-09-16 | baae3c3e813c | 31.2B total/4B active MoE, full MHA (32 kv=32 attn heads, no GQA) | apache-2.0 | Xing4_0ForCausalLM not registered at b11057; reconfirmed absent at b11146 and b11214 (2026-09-27T12:45:21Z, the newest tag) via a fresh architecture-registry scan | Even if supported, full-MHA 32K KV alone is approx 18.79GB, worst of this table |
| prism-ml/Ternary-Bonsai-2-27B-gguf (base Qwen/Qwen3.8-27B) | prism-ml (closest match to task's PrismML) | 2026-09-16 | b072e1d3b35a | approx 27B ternary, 1.72-2.13 bits/weight | apache-2.0 | Custom ternary hybrid-attention kernel; own card confirms stock llama.cpp rejects the shipped PQ2_0/PTQ1_0 files outright as unknown types (does not run at all) and silently loads the unrelated generic Q2_0 type with no Hadamard activation runtime, producing garbage output — "produces garbage" applies only to that Q2_0 fallback, not to PQ2_0/PTQ1_0; needs the PrismML-Eng/llama.cpp FORK | approx 5.9-7.2GB per card [self]; card measures approx 28 tok/s TG128 on an Apple M5 Pro (this Mac's target chip: 28.1 tok/s PQ2_0 current build, 28.7 tok/s on an earlier pre-rotation 7.2GB build pending re-measurement — readme_bonsai2_27b_gguf.md lines 191/206); a separate figure of approx 47 tok/s is claimed for the wider Apple M5 Max, publisher-claimed and not independently verified |

## Too large for this Mac regardless of quant (total safetensors element counts [obs]; MoE = total, not active)

New since 2026-08-01: deepseek-ai/DeepSeek-V4-Pro-0813 1650.5B mit (approx 990GB@Q4); XiaomiMiMo/MiMo-V2.6-Pro-RL 1024.2B mit (approx 615GB); deepseek-ai/DeepSeek-V4.1-Flash 763.2B mit (approx 458GB, baseline watch); zai-org/GLM-5.3 753.3B glm-5.3-custom (approx 452GB, baseline watch); tencent/Hy4-preview 780.0B apache-2.0 (approx 468GB, new Hunyuan successor); nvidia/Nemotron-3-Labs-Ultra-Math-SFT+RL and nvidia/NVIDIA-Nemotron-Labs-Teacher x5 (STEM/General-Reasoning/Instruction-Following/Competition-Coding/Chat), all 560.5B, license other (approx 336GB each); XiaomiMiMo/MiMo-V2.6-Flash-RL 310.8B mit (approx 186GB); zai-org/GLM-5.3-Flash 321.3B mit (approx 193GB, baseline watch); deepseek-ai/DeepSeek-V4-Flash-Vision-Exp 304.6B mit (approx 183GB).
Unchanged from baseline watch list, still too large: Qwen/Qwen3.8-2.4T-A95B (2.4T/95B active); moonshotai/Kimi-K3 (2.8T/104B active; lastModified moved to 2026-09-02, no new repo -- card-level change only); Qwen/Qwen3.8-Flash-Next (approx 180B stored/6B active).

## Official alt-quants of the existing default (not new models)

- Qwen/Qwen3.8-27B-FP8 (created 2026-08-13, 27.78B, apache-2.0): official FP8 of the same Qwen3.8-27B; approx 27.8GB at FP8, larger than the proven UD-Q4_K_M. nvidia/Qwen3.8-27B-NVFP4 (created 2026-09-04) is a CUDA-kernel-specific mirror, not a Metal/llama.cpp path.

## lastModified sweep (catches update-not-create; 44 in-window lastModified hits reviewed across the 18 orgs, createdAt before 2026-08-01)

No previously-unknown Mac-fit foundation model surfaced this way; all 44 hits were either (a) already-covered too-large siblings getting card/file touches (GLM-5.2, Nemotron-3-Ultra-550B-A55B, Nemotron-3-Super-120B-A12B, Kimi-K2-Thinking-NVFP4, Qwen3.6-35B-A3B-NVFP4, GLM-5.2-NVFP4, DeepSeek-V4-* NVFP4 mirrors), (b) non-generation models (OCR, guardian/safety, parse, calibration, audio), or (c) small older items just touched (Phi-4-reasoning-vision-15B, Ternary-Bonsai-27B-gguf original). Two items worth naming: deepseek-ai/DeepSeek-V4-Flash-0731 was created 2026-07-31 (one day before the window) and only touched 2026-08-01, a boundary case not otherwise counted here. nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning (created April 2026, 30B/3B active, touched 2026-08-24/25) is an older same-size-class sibling of the Lightning-30B-A3B row above.
Cross-reference: the Nemotron-3.5-Lightning card benchmark table names Qwen-3.6-35B-A3B and Nemotron 3 Super as stronger peers and Nemotron 3 Nano / GPT-OSS-20B as weaker; nvidia/NVIDIA-Nemotron-3-Super-120B-A12B (120B/12B active) and nvidia/Qwen3.6-35B-A3B-NVFP4 (mirror) confirm those identities but both are pre-window and/or too large for this Mac at Q4.

## Orgs checked with no new generation-model release in the window

| Org | Newest relevant repo observed | Created [obs] |
|---|---|---|
| meta-llama | Llama-Guard-4-12B | 2025-04-23, nothing since |
| openai (HF weights) | gpt-oss-safeguard-20b/120b | 2025-09-18 |
| mistralai | Magistral-Small-2507-GGUF | 2025-07-23 |
| google (generation family) | gemma-4 QAT variants | 2026-06-05 (timesfm-3.0 2026-08-24 is forecasting, non-commercial, baseline) |
| baidu | ERNIE-4.5-VL-28B-A3B-Thinking | 2025-11-07 |
| MiniMaxAI | MiniMax-M3 / M3-MXFP8 | 2026-06-02 |
| microsoft (chat/text LLM) | Fara1.5-27B/4B agent VLM | 2026-07-17 (Phi newest Phi-Ground-Any 2026-05-07) |
| allenai | OLMo-3 family | 2026-02-19 to 02-28 (Sept HF OLMo-3 activity is third-party fine-tunes) |
| stepfun-ai | Step-3.7-Flash family | 2026-05-23 to 05-28 |
| PrismML / prism-ml | ternary GGUF/MLX/AWQ only, no plain safetensors base | newest gguf-dev 2026-09-17 |

## Hosted models (release dates only, per task; primary source fetched 2026-09-27)

- OpenAI, https://developers.openai.com/api/docs/models (fetched 2026-09-27): gpt-6-astra still the flagship, same model ID, knowledge cutoff Apr 30 2026 shown; the page has no version/snapshot field so unchanged-vs-refreshed cannot be fully confirmed from it alone. Two new siblings are live on the same index: gpt-6-sol (knowledge cutoff Apr 20 2026) and gpt-6-luna (May 18 2026), both absent from the baseline record. The OpenAI docs page itself carries no release-date field for either — only the knowledge-cutoff dates above are on-page; the 2026-09-22 expansion date is secondary-source only (WebSearch, CNBC), not corroborated by developers.openai.com.
- Anthropic, https://platform.claude.com/docs/en/models/overview and .../opus-5-5/overview (fetched 2026-09-27; releasedOn fields read directly from the pages' embedded JSON, confirmed against the raw page source): claude-opus-5-5, releasedOn 2026-09-22, lifecycle active, latest true -- newer than the baseline-pinned claude-opus-5[1m] (2026-07-24). claude-fable-5-1, releasedOn 2026-09-01, matches baseline exactly, remains user-excluded (not re-argued here). claude-sonnet-5, releasedOn 2026-06-30. The same release wave also names claude-mythos-5-1 (paired with Fable 5.1 in the announcement link); not independently investigated.

## Unknowns

- No independent (non-publisher) benchmark located this session for granite-4.2-30b, Nemotron-3.5-Lightning-30B-A3B, ContextPilot, or Muse-Glimmer-30B; all quality evidence above is publisher self-reported or publisher-run-harness (Nemotron explicitly: NeMo Gym/Evaluator, publisher-run against third-party baselines).
- ContextPilot-E4B and Muse-Glimmer-30B use nested multimodal configs; exact per-layer KV math not resolved this session.
- Whether Xing4.0-29B-A4B or Ternary-Bonsai-2-27B work on any mainline llama.cpp branch newer than b11214, or only on forks/custom builds, was not re-verified beyond the architecture-registry check.
- Exact Q4_K_M file size for the current MiMo-V2.6-Distill-Qwen-9B revision was not refetched (baseline receipt used Q8_0); figure above is an estimate.
- meta-models (Muse-Glimmer) and XingChen-AGI are outside the mandated 18-org list; included because they surfaced via the nvidia/prism-ml mirror trail.
- Publisher Release Date fields were found only on the granite-4.2-30b and Nemotron-3.5-Lightning cards; other rows show HF createdAt only, which can precede the public announcement.

## Revisions (40-hex), exact repo id : sha

- deepseek-ai/DeepSeek-V4-Flash-Vision-Exp: 6821d6ad3681a4b137b066b76094fa82ebd0a380
- deepseek-ai/DeepSeek-V4-Pro-0813: 72e1d3230f6c080a530b0a1d46f8eb4602340597
- deepseek-ai/DeepSeek-V4.1-Flash: dba1be0a40aa45a94ad051997016db3960a90277
- ibm-granite/granite-4.2-30b-GGUF: 27b350a791e81d9a4d1ddca1c49282e9ec533768
- ibm-granite/granite-4.2-30b-q4-mlx: d3f143b440062060eb05f7b8677ced5b4d9a8946
- ibm-granite/granite-4.2-30b: 9e668ce1c538387ef24d3644e9b0606647762636
- ibm-granite/granite-4.2-3b-q4-mlx: 0c6f39b1827afd5eb2c1c3b13751929857434953
- ibm-granite/granite-4.2-3b: e459acceac81e5fe67c07d9cfc72329a332e7eb1
- ibm-granite/granite-4.2-8b-q4-mlx: 9047f073e46c527f70dade07bb55b1700d728e36
- ibm-granite/granite-4.2-8b: f8de16cdcdbc6c779ca517604e050d82cc119e44
- nvidia/Muse-Glimmer-30B-NVFP4: 47818374517751c48c55cde2621594926b1888b6
- nvidia/Nemotron-3-Labs-Ultra-Math-SFT: c6337c397cc7ea2cf7b594e0b880bc874558e20d
- nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-Base-BF16: 434456c9a6753f29d24e23c95d622aaf17111b3b
- nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16: a9904d24bcc1d289a1950fa9d2b978c47cf903b9
- nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4: bee7596271d1495f6992ae224aefde4410e816b8
- nvidia/NVIDIA-Nemotron-Labs-Teacher-Chat: 7fbf767583dfd7f18f11734626ce1fb311d6acb1
- prism-ml/Ternary-Bonsai-2-27B-gguf: b072e1d3b35a0a630cece372c2127528e0994386
- Qwen/Qwen3.8-27B-FP8: 017b9c7af6b5689d5dd426a76e0bc077eb5ca20a
- tencent/ContextPilot-14B: 8eafd8356c5c5e713e92e623c8f1d346de6d0f95
- tencent/ContextPilot-8B: 595abeaed72e4a4d9da94d04917f0618989a5553
- tencent/ContextPilot-E4B: a7ba41c18ddcd334f23f63ef7a608ca46bfe3aa4
- tencent/Hy4-preview-FP8: 4215ec29de873a998e849cee902654490c7ff4d1
- tencent/Hy4-preview: 705d81ee51566a186d645b74c974d642ef2828fe
- tencent/UI-Mate-27B: 3ade2378fc84032d5017c1a9c93c4eaa77d65e57
- tencent/UI-Mate-9B: 05dd5f2975195a5bb03d4363e8767f12158c8421
- XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B: 2367e865d009c13ac81713a2878291d33ab28177
- XiaomiMiMo/MiMo-V2.6-Flash-RL: 5711b268169967567844e1e560e8a3966da959b1
- XiaomiMiMo/MiMo-V2.6-Pro-RL: 73875d00b30a89ef8cc353a0b60b0e9f9561952d
- XingChen-AGI/Xing4.0-29B-A4B: baae3c3e813cad5f888f1f485cfff659c89076c5
- zai-org/GLM-5.3-Flash: eb9eb208eb0d988989d07a6a12d0fdeb5f52574a
- zai-org/GLM-5.3: aca966e4e02791568aa6a4ced368624b3d897f42
- Qwen/Qwen3.8-27B: 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0 (base card)
- unsloth/Qwen3.8-27B-GGUF: 4ca720788d1e01f1bff70c033e0d0028fd02e502 (proven quant, per baseline)
- meta-models/Muse-Glimmer-30B: a4e59da52a7bc87ae7251dd5545c0dd437c44b68
- moonshotai/Kimi-K3: f831ab66814297da540d832a5235f8e904f29d06 (per baseline, unchanged)
- Qwen/Qwen3.8-Flash-Next: de4b8e4d43b917e7706784d8bb445c9af86a3540 (per baseline, unchanged)
- Qwen/Qwen3.8-2.4T-A95B: 207bd685a7e3696cfaff12ded7c6a7ea0f88c996 (per baseline, unchanged)

## Protocol caveats (added after review)

- granite-4.2-30b README line 347 states thinking is enabled by default; the card benchmarks quoted above (AIME25 89.17, GPQA 66.41, MMLU-Pro 77.60) are THINKING-MODE scores. The baseline proven extraction protocol for Qwen3.8-27B runs thinking DISABLED at about 17 output tokens per filing. These numbers do not transfer to that protocol; granite-4.2-30b has no thinking-off, task-matched evidence.
- Ternary-Bonsai-2-27B self-reported 84.78 average is likewise across 14 THINKING-MODE benchmarks per its own card; same non-transfer caveat, on top of it being runtime_unsupported on mainline.
- tencent/ContextPilot-E4B license was read from the sibling ContextPilot-8B repo LICENSE file (Tencent custom terms); E4B itself is Gemma4-based and was not individually read this session. Mark E4B license as [unk: LICENSE file present, not opened] rather than assuming it matches the 8B terms.

</details>
