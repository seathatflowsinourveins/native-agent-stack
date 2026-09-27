<!-- Committed verbatim from PR #390 comment https://github.com/seathatflowsinourveins/native-agent-stack/pull/390#issuecomment-5856546630 (posted 2026-09-27T14:04:25Z by the mac-coordinator-64gb-20260925 session). S3 section 2: discovery input only; vendor-reported numbers are motivation, never S3 evidence. -->

**S3 section 2 input from `mac-coordinator-64gb-20260925` (2026-09-27): five verified sweep tables**

The five tables follow as separate comments. Each suggests a path under `inputs/sweep-20260927-mac/`. Every table came from a Sonnet sweep against primary sources: the Hugging Face API, the model cards and LICENSE files, the llama.cpp source at b11146 and b11214, registry JSON, and the GitHub releases API. An independent Opus pass then checked the claims that decide each ranking, and the tables were corrected. Each table's "Verification" section lists the corrections and their sources. Per the S3 merit rules, the published and self-reported scores here (LMEB, AA-LCR, vendor cards, and the MemReranker paper's Table 6) are discovery evidence, not S3 evidence.

What changes inputs:

- **Memory LLM (consolidation/rerank).** The AA-LCR v1.1 scores are recoverable from Artificial Analysis's page data. The mapping reproduces the baseline's own figures exactly (Qwen3.5-9B 46.0/70.0, Qwen3.6-35B-A3B 64.3/71.7, Nemotron 60.3).
  - Non-reasoning: Qwen3.8-27B 69.3, trial 64.3, control 46.0, Gemma-4-26B-A4B 42.3.
  - Reasoning: Qwen3.8-27B 82.0, trial 71.7, control 70.0, Gemma 65.7, granite-4.2-30b 49.0, granite-4.2-8b 45.0.
  - Qwen3.8-27B's open risk is ai-memory's 20 s reranker gate. This Mac's measured timing goes into #379.
- **Gemma-4 license.** `license_link` resolves to plain Apache-2.0.
- **LFM2.5-8B-A1B.** It has an Ollama tag, `lfm2.5:8b`. Its LFM Open License v1.0 withholds commercial use from entities with US$10M or more in annual revenue.
- **Embedders.** No new dense text embedder in the last 4-6 weeks.
  - Nemotron-3-Embed-1B beats F2LLM-v2-4B on every LMEB figure, but has no llama.cpp or Mac path (`Ministral3Model` is unregistered at b11146).
  - F2LLM-v2-4B leads only for a llama.cpp deployment: Apache-2.0, `Qwen3Model` registered, the same path as production.
  - "LMEB rank" is the leaderboard's Borda rank.
- **Rerankers.** MemReranker-4B has the best LongMemEval NDCG@10/MAP (0.8354/0.8043, self-reported, community MLX only). Qwen3-Reranker-0.6B is the only one with a maintainer-demonstrated stock GGUF (b11057 untested). BGE-v2-m3 vs Qwen3-Reranker-0.6B is effectively a tie.
- **ai-memory lineage.** `19b6429` is 46 commits ahead of and 62 behind v2.4.1 (merge base `8ee81bed`), and v2.4.0 is its ancestor. This goes into the reference-arm rationale.
- **Generation.** No in-window model has task-level evidence against Qwen3.8-27B.
  - granite-4.2-30b: official GGUF, MLX and Ollama, about 27.8 GB at 32K.
  - Nemotron-3.5-Lightning-30B-A3B: about 27.0 GB at 32K, KV 0.20 GB.
  - Either one would need the li26 protocol.
- **Memory systems.** Trial pins unchanged: agentmemory 0.9.29, MemPalace 3.10.0, Hindsight 0.10.1. For Hindsight's capture path, pin `integrations/coding-agents/v0.7.0`.
  - Mac Hindsight is `pending` (Apple Container, the owner's install).
  - claude-mem's interactive installer pre-selects hosted CMEM Pro.
  - GBrain's hang issues #5284 and #5449 are still open.
  - Memorix v1.9.6 and mcp-memory-service v11.14.0 are Apache-2.0 defer candidates.
