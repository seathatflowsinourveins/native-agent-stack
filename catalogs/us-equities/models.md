# Model choices and recent-release evidence

Checked September 19, 2026. **Keep native GPT-6 Astra / Claude Opus 5, local Nemotron-3-Embed-1B and the demonstrated Qwen3.8-27B quant.** Newer retrieval candidates need a domain evaluation and a compatible serving path; recent large MoE releases are not local-PC upgrades.

The fresh native HF audit returned metadata for 17/17 selected model repositories. Eleven model-card reads also completed. No weights were downloaded and no new model inference is implied. Existing Nemotron and Qwen execution has separate receipts. [Exact command results](research-receipt.json).

| Model | Decision | Dated evidence | Role | License |
| --- | --- | --- | --- | --- |
| [gpt-6-astra](https://developers.openai.com/api/docs/models/gpt-6-astra) | default | 2026-09-03; Official API changelog | Primary native research workers | Proprietary hosted model |
| [claude-opus-5[1m]](https://platform.claude.com/docs/en/models/opus-5/overview) | default | 2026-07-24; Official model overview | Native research/review companion | Proprietary hosted model |
| [claude-fable-5-1](https://platform.claude.com/docs/en/models/overview) | excluded | 2026-09-01; Official model documentation | Newer hosted candidate | Proprietary hosted model |
| [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B/blob/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0/README.md) | conditional | 2026-08-14; Publisher release announcement | Local generation | apache-2.0 |
| [Qwen/Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next/blob/de4b8e4d43b917e7706784d8bb445c9af86a3540/README.md) | watch | 2026-08-26; Publisher release announcement | Cluster generation | qwen-community-1.0 |
| [Qwen/Qwen3.8-2.4T-A95B](https://huggingface.co/Qwen/Qwen3.8-2.4T-A95B/blob/207bd685a7e3696cfaff12ded7c6a7ea0f88c996/README.md) | watch | Unverified; Model card available; exact public launch date not verified | Cluster generation | qwen3.8-max |
| [deepseek-ai/DeepSeek-V4.1-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/blob/dba1be0a40aa45a94ad051997016db3960a90277/README.md) | watch | 2026-09-10; Publisher announcement | Cluster generation | mit |
| [zai-org/GLM-5.3-Flash](https://huggingface.co/zai-org/GLM-5.3-Flash/blob/eb9eb208eb0d988989d07a6a12d0fdeb5f52574a/README.md) | watch | 2026-08-26; First weight uploads; not a verified hosted launch date | Cluster generation | mit |
| [zai-org/GLM-5.3](https://huggingface.co/zai-org/GLM-5.3/blob/aca966e4e02791568aa6a4ced368624b3d897f42/README.md) | watch | 2026-08-27; Initial model tree UTC; August 28 UTC+8 | Cluster generation | glm-5.3 |
| [moonshotai/Kimi-K3](https://huggingface.co/moonshotai/Kimi-K3/blob/f831ab66814297da540d832a5235f8e904f29d06/README.md) | watch | 2026-07-16; Announcement; first HF weight tree July 27 | Cluster generation | kimi-k3 |
| [nvidia/Nemotron-3-Embed-1B-BF16](https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16/blob/c0c9fea93ea424587517f2c59e20db9f1d6bf615/README.md) | default | 2026-07-16; Publisher model-card date and announcement | Local text/code embeddings | openmdw-1.1 |
| [nvidia/Nemotron-3-Embed-8B-BF16](https://huggingface.co/nvidia/Nemotron-3-Embed-8B-BF16/blob/d1f2f25730bbd775b99b29185134bc86653bf2d1/README.md) | conditional | 2026-07-16; Publisher announcement | Larger local/hosted embeddings | openmdw-1.1 |
| [nvidia/Nemotron-3-Embed-1B-NVFP4](https://huggingface.co/nvidia/Nemotron-3-Embed-1B-NVFP4/blob/f630128278eb245579d3ea022b4f659fbd614318/README.md) | watch | 2026-07-16; Parent-family release; no separate quant launch established | Quantized embedding variant | openmdw-1.1 |
| [jinaai/jina-reranker-v3.5](https://huggingface.co/jinaai/jina-reranker-v3.5/blob/e8a93f33f0b22108f8c2364f8484ce3422552fbc/README.md) | excluded | 2026-08-03; Publisher announcement; July 20 paper | Listwise reranking | cc-by-nc-4.0 |
| [Alibaba-NLP/UEmbed-2B](https://huggingface.co/Alibaba-NLP/UEmbed-2B/blob/d02beb2d8b975f8140ebb035bd0e1dbf8afe98c4/README.md) | conditional | 2026-08-03; Author paper states released family; exact weight-publication day unknown | Dense+sparse multimodal retrieval | cc-by-4.0 |
| [Alibaba-NLP/core-emb-2b](https://huggingface.co/Alibaba-NLP/core-emb-2b/blob/cc9870ea92d64ebd5f8f9fc368d1120453564158/README.md) | watch | 2026-09-03; Research paper date, not a verified weight-release announcement | Multimodal compositional embeddings | cc-by-4.0 |
| [Alibaba-NLP/core-reranker-2b](https://huggingface.co/Alibaba-NLP/core-reranker-2b/blob/64e1a36cd6ecace459a4c7cd8f7d0ef5d6fee30b/README.md) | watch | 2026-09-03; Research paper date, not a verified weight-release announcement | Multimodal compositional reranking | cc-by-4.0 |
| [google/timesfm-3.0-pytorch](https://huggingface.co/google/timesfm-3.0-pytorch/blob/43046b85ec22d584a13f8098c2ed39c889e129c2/README.md) | excluded | 2026-08-28; TimesFM v3.0.0 source release; model announcement August 2026 | Time-series forecasting | TimesFM Non-Commercial License v1.0 |
| [google/timesfm-2.5-200m-pytorch](https://huggingface.co/google/timesfm-2.5-200m-pytorch/blob/1d952420fba87f3c6dee4f240de0f1a0fbc790e3/README.md) | conditional | 2025-09-15; Publisher model announcement; older compatible baseline | Time-series forecasting baseline | apache-2.0 |
| [amazon/chronos-2](https://huggingface.co/amazon/chronos-2/blob/29ec3766d36d6f73f0696f85560a422f50e8498c/README.md) | conditional | 2025-10-20; Upstream model announcement; this HF repository created October 30 | Probabilistic time-series baseline | apache-2.0 |

## Apply models by task

- Research/coding: native Astra first; native Opus for the established companion workflow. Use separate bounded workers with selected artifact paths, not copies of the full conversation.
- Code retrieval: retain the measured Nemotron/vLLM/Qdrant pipeline. For filings, compare lexical, dense, sparse and reranked retrieval on held-out questions with source citations and as-of constraints.
- Forecasting: compare simple baselines before foundation models. TimesFM 3.0 weights are non-commercial; Apache TimesFM 2.5 and Chronos-2 are older research alternatives. None has demonstrated trading alpha here.
- QMD: keep current BM25 mode. HF model recency does not override its GGUF, input formatting, pooling and ranking contracts.

## Token and cache discipline

Keep stable instructions/tool definitions before variable task data. Retrieve exact sections and compute tables outside the model. Native cache reuse, compression estimates, selected-artifact token counts and provider usage are separate ledgers. Include failed attempts. The worker receipt records 202,164 input / 176,000 cached input / 1,927 output across three turns; 87.06% cached-input share is not a net-token-savings experiment.

Use [the worker policy](../../blueprints/us-equities/workers/policy.md) and [router fidelity notes](../../blueprints/us-equities/routing/README.md). Direct Astra API caching/output controls must follow its current Responses schema; installing a compatible-looking gateway does not prove those fields survive transport.

## Per-model requirements and pins

### gpt-6-astra

Keep native subscription sign-in and the actual SDK worker path.

Revision: `None`. Actual configured native SDK task receipt; help is not another inference.

- No official HF weights. Native model/route configuration is not independent provider attestation.
- API context/output limits are distinct from native Codex runtime limits. API billing is separate from subscription allowance.
- OmniRoute native Astra text Responses inference has a [dated receipt](../../blueprints/us-equities/routing/astra-receipt.json); output-cap enforcement and native tool/hook/compaction parity remain unproved.

```bash
python blueprints/us-equities/workers/native_worker.py --help
```

### claude-opus-5[1m]

Retain existing native model and account flow with shared scoped memory/retrieval.

Revision: `None`. Readiness commands; the [dated research-runtime receipt](../../blueprints/us-equities/research-runtime/receipt.json) separately proves a real native Opus 5 report and reconciled usage.

- A fresh standalone native Opus 5 research report completed on September 19 with 14,583 tokens; this does not prove a full 1M-context workload or a new paired Astra run. Fresh account allowance is required for another inference.
- A router configured at 200K does not reproduce the native/API 1M context behavior. No official HF weights.

```bash
claude --version
claude auth status
```

### claude-fable-5-1

Record the newer release for landscape completeness; preserve the user-selected exclusion.

Revision: `None`. No execution proposed while excluded.

- No account/model switch or inference performed; latest release is not permission to change native defaults.

### Qwen/Qwen3.8-27B

Practical local generation baseline: historical Ollama quant at 8192 context; research summaries and bounded extraction candidates.

Revision: `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- 27B dense BF16 is larger than the demonstrated quant. Financial extraction accuracy is unmeasured. Card maximum context is not the installed GPU capacity.

```bash
hf models info Qwen/Qwen3.8-27B --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card Qwen/Qwen3.8-27B --text --format human
```

### Qwen/Qwen3.8-Flash-Next

Cluster research candidate; not a PC upgrade solely because active parameters are small.

Revision: `de4b8e4d43b917e7706784d8bb445c9af86a3540`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- About 180B stored parameters including n-gram/MTP despite 6B active language parameters. Custom license and architecture support require review.

```bash
hf models info Qwen/Qwen3.8-Flash-Next --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card Qwen/Qwen3.8-Flash-Next --text --format human
```

### Qwen/Qwen3.8-2.4T-A95B

Large open-weight multimodal generation alternative when cluster capacity and licensing justify it.

Revision: `207bd685a7e3696cfaff12ded7c6a7ea0f88c996`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- 2.4T total/95B active is not a local-memory footprint. Repository creation August 8 is not a verified public release date. Custom Qwen3.8-Max license.

```bash
hf models info Qwen/Qwen3.8-2.4T-A95B --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card Qwen/Qwen3.8-2.4T-A95B --text --format human
```

### deepseek-ai/DeepSeek-V4.1-Flash

Recent high-capacity generation candidate with specialized serving requirements.

Revision: `dba1be0a40aa45a94ad051997016db3960a90277`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- 552B backbone plus 196B Engram; multimodal protocol and runtime compatibility require acceptance. No local inference.

```bash
hf models info deepseek-ai/DeepSeek-V4.1-Flash --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card deepseek-ai/DeepSeek-V4.1-Flash --text --format human
```

### zai-org/GLM-5.3-Flash

320B total/18B active visual coding and agent research option.

Revision: `eb9eb208eb0d988989d07a6a12d0fdeb5f52574a`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- No local serving proof; sparse active parameters do not eliminate checkpoint memory requirements.

```bash
hf models info zai-org/GLM-5.3-Flash --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card zai-org/GLM-5.3-Flash --text --format human
```

### zai-org/GLM-5.3

Large text/coding model candidate subject to custom license.

Revision: `aca966e4e02791568aa6a4ced368624b3d897f42`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- HF tensor elements (~753B) are not a independently verified logical architecture count. No local deployment.

```bash
hf models info zai-org/GLM-5.3 --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card zai-org/GLM-5.3 --text --format human
```

### moonshotai/Kimi-K3

Cluster-class multimodal research model, not a required foundation dependency.

Revision: `f831ab66814297da540d832a5235f8e904f29d06`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- 2.8T total/104B active and custom license. September card changes do not establish a new model release.

```bash
hf models info moonshotai/Kimi-K3 --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card moonshotai/Kimi-K3 --text --format human
```

### nvidia/Nemotron-3-Embed-1B-BF16

Keep the demonstrated 2048-dimensional embedding service powering automatic local code RAG.

Revision: `c0c9fea93ea424587517f2c59e20db9f1d6bf615`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- Use query: and passage: prefixes with trailing spaces and correct pooling. Changing models requires dimension/collection migration.
- Retain working vLLM 0.25.0 on this WSL host; newer 0.29.0 failed GPU UVA initialization. It is not a drop-in QMD GGUF model.

```bash
hf models info nvidia/Nemotron-3-Embed-1B-BF16 --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card nvidia/Nemotron-3-Embed-1B-BF16 --text --format human
```

Prospective inference entry point: Use the existing native RAG recipe and pinned model revision; publisher alternatives require Transformers >=5.2 and SentenceTransformers >=5.4.1.

### nvidia/Nemotron-3-Embed-8B-BF16

Compare only if a held-out retrieval task justifies the greater resource cost.

Revision: `d1f2f25730bbd775b99b29185134bc86653bf2d1`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- 7.95B, 4096 dimensions, about 15.91GB BF16 weights alone. No inference or reindex performed.

```bash
hf models info nvidia/Nemotron-3-Embed-8B-BF16 --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card nvidia/Nemotron-3-Embed-8B-BF16 --text --format human
```

### nvidia/Nemotron-3-Embed-1B-NVFP4

Potential hardware-specific serving option for the same embedding family.

Revision: `f630128278eb245579d3ea022b4f659fbd614318`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- Not a separate newly trained family. NVFP4 hardware/kernel compatibility and quality are unverified on this host.

```bash
hf models info nvidia/Nemotron-3-Embed-1B-NVFP4 --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card nvidia/Nemotron-3-Embed-1B-NVFP4 --text --format human
```

### jinaai/jina-reranker-v3.5

Research comparison only under the available license; not the commercial-trading default.

Revision: `e8a93f33f0b22108f8c2364f8484ce3422552fbc`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- CC-BY-NC-4.0; commercial permission would need separate review. GGUF requires a special projector/scorer and llama.cpp support, not a QMD model-variable swap.

```bash
hf models info jinaai/jina-reranker-v3.5 --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card jinaai/jina-reranker-v3.5 --text --format human
```

### Alibaba-NLP/UEmbed-2B

Financial document/image retrieval candidate when sparse+dense/multimodal signals are useful.

Revision: `d02beb2d8b975f8140ebb035bd0e1dbf8afe98c4`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- CC-BY-4.0 attribution required. Model-specific preprocessing and sparse outputs need a supported pipeline; no local financial evaluation or QMD compatibility proof.

```bash
hf models info Alibaba-NLP/UEmbed-2B --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card Alibaba-NLP/UEmbed-2B --text --format human
```

### Alibaba-NLP/core-emb-2b

Recent research candidate for complex image/text matching; compare on sourced financial tables and filings before adoption.

Revision: `cc9870ea92d64ebd5f8f9fc368d1120453564158`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- CC-BY-4.0 attribution required. Author benchmark does not establish code/financial retrieval superiority.
- Publisher recipe uses custom Qwen3-VL wrappers, Transformers >=4.57, PyTorch/qwen-vl-utils/Pillow. Generic autogenerated HF pipeline is insufficient; no inference run.

```bash
hf models info Alibaba-NLP/core-emb-2b --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card Alibaba-NLP/core-emb-2b --text --format human
```

### Alibaba-NLP/core-reranker-2b

Recent research candidate for complex image/text matching; compare on sourced financial tables and filings before adoption.

Revision: `64e1a36cd6ecace459a4c7cd8f7d0ef5d6fee30b`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- CC-BY-4.0 attribution required. Author benchmark does not establish code/financial retrieval superiority.
- Publisher recipe uses custom Qwen3-VL wrappers, Transformers >=4.57, PyTorch/qwen-vl-utils/Pillow. Generic autogenerated HF pipeline is insufficient; no inference run.

```bash
hf models info Alibaba-NLP/core-reranker-2b --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card Alibaba-NLP/core-reranker-2b --text --format human
```

### google/timesfm-3.0-pytorch

Recent forecasting research only; excluded from the commercial/production path under current weights license.

Revision: `43046b85ec22d584a13f8098c2ed39c889e129c2`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- TimesFM Non-Commercial License v1.0 is separate from Apache source code. Forecast accuracy is not equity alpha or execution evidence.

```bash
hf models info google/timesfm-3.0-pytorch --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card google/timesfm-3.0-pytorch --text --format human
```

### google/timesfm-2.5-200m-pytorch

Apache-licensed 200M forecasting baseline for a properly lagged comparison, despite not being a recent model.

Revision: `1d952420fba87f3c6dee4f240de0f1a0fbc790e3`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- Package 3.0.2 is not model 3.0 permission. No financial out-of-sample evaluation performed. Forecasted prices alone are not a strategy.

```bash
hf models info google/timesfm-2.5-200m-pytorch --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card google/timesfm-2.5-200m-pytorch --text --format human
```

Prospective inference entry point: timesfm.TimesFM_2p5_200M_torch.from_pretrained('google/timesfm-2.5-200m-pytorch'); configure ForecastConfig before forecast.

### amazon/chronos-2

120M probabilistic baseline with covariates for research comparisons; current library release does not make the weights recent.

Revision: `29ec3766d36d6f73f0696f85560a422f50e8498c`. Metadata command passed this session. Model-card command passed only where listed in research-receipt.json. Inference recipe is prospective unless a receipt explicitly proves it.

- Keep covariates available at prediction time, embargo overlaps and evaluate net trading utility separately. No inference or finance benchmark run.

```bash
hf models info amazon/chronos-2 --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card amazon/chronos-2 --text --format human
```

Prospective inference entry point: Chronos2Pipeline.from_pretrained('amazon/chronos-2'); predict_df on versioned, time-ordered data.
