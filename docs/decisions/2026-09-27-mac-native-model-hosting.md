# Decision: the 64 GB coordinator Mac hosts its own memory/RAG models natively (2026-09-27)

**Decided by:** the user, 2026-09-27, in host request
[#379](https://github.com/seathatflowsinourveins/native-agent-stack/issues/379): memory/RAG is a native
foundation layer on every host, not a service borrowed from the workstation. This record gives the
measured basis on `mac-coordinator-64gb-20260925` and the proposed role change. It was written by the Mac
coordinator session on branch `claude/mac-model-hosting-20260927` (base `origin/main@8bb52541`).

**Scope:** [`adoption/host-roles.json`](../../adoption/host-roles.json) (the proposal below) and the
evidence in
[`evidence/artifacts/mac-model-hosting-20260927/`](../../evidence/artifacts/mac-model-hosting-20260927/README.md)
with its host receipt. Lane: `lane:foundation`. Nothing here changes a pin, a production service or the
memory-layer decision: retrieval quality belongs to the S3 preregistration (#390).

## Context

Measured on this Mac (Apple M5 Pro, 64 GB unified memory, macOS 27.0) with a normal coordinator session
active. The full numbers and their evidence classes are in the artifact README.

- **RAG embedder.** The pinned profile's `com.native-stack.llama-embed` LaunchAgent (llama.cpp b11057
  `--embedding`, embeddinggemma-300M-Q8_0, port 8232) passes
  `tools/adoption/embed_acceptance.py` against the Linux reference: 768 dimensions, cosine 0.99966. All 25
  layers run on Metal (`MTL0`), per llama-server's own log.
- **Memory stack.** ai-memory, Ollama (qwen3-embedding:4b, qwen3.5-9b-64k) and Qdrant already ran here as
  `local.agent-ecosystem.*` agents. No second Qdrant or ai-memory was started.
- **Generation.** `unsloth/Qwen3.8-27B-GGUF@4ca7207` UD-Q4_K_M (16.46 GB, 27.8B dense) runs fully on
  Metal.
  - llama-bench: pp512 371.5, pp4096 341.7, tg128 15.9 tokens/s.
  - Serving at a 32K context: peak RSS 22.9 GiB, swap unchanged, 0 memorystatus kills.
  - li26 on 360 real 8-K filings, descriptive: micro-F1 0.9909 and JSON-valid 1.0 for C0 on b11057 and b11146
    and for C2 with MTP drafting on b11146. Predictions are identical on all 360 filings. Median decode is
    15.7, 15.8 and 23.9 tokens/s respectively, peak RSS stays at or under 17.6 GiB, and there are 0 memory
    kills.
- **Worst case.** The C2 profile at a 32K context on b11214 (19.4 GiB peak RSS) and ai-memory's two Ollama
  models (12.5 GiB) were resident and driven at once, next to the RAG embedder and Qdrant. System free
  memory was 53%, swap did not grow, there were 0 kills, and every request succeeded.
- **The one swap event.** Swap grew only once, peaking at 13.9 GB for about 40 s with no kills. That was
  when an OmniRoute Next.js production build and ai-memory's model load overlapped a li26 run.
- **Workstation embedder.** Nemotron-3-Embed-1B has no supported Mac runtime. Its `Ministral3Model` is not
  registered in llama.cpp's converter at b11146, and NVIDIA publishes no GGUF or MLX artifact.

## Decision

1. **This Mac hosts, natively and together:**
   - the pinned RAG embedder (embeddinggemma-300M on llama.cpp Metal, port 8232);
   - the memory stack's own models (Ollama qwen3-embedding:4b and qwen3.5-9b-64k);
   - Qdrant;
   - one 27B-class 4-bit generation model on llama.cpp Metal.
   The measured budget for this co-resident set is a generation server of up to 19.4 GiB RSS at a 32K context, plus 12.5 GiB of memory-stack models, the embedder and Qdrant, with 53% of system memory still free, no swap growth and no memorystatus kills.
2. **`adoption/host-roles.json`:** `mac-coordinator` also owns `model-hosting`, `memory-e2e` and `rag-e2e`
   for its own foundation layer. GPU runtime qualification, cross-host model qualification and independent
   review stay with the workstation. Routing is unchanged, because `scripts/host_requests.py` routes on the
   request label alone. `owns` records what the host accepts.
3. **What exceeds this Mac** (the trigger for a larger one): a 27B-class LLM as ai-memory's reranker at 8K tokens, which runs 27-28 s on llama.cpp Metal and 18.5 s median on Ollama's MLX engine against the 20 s gate. Also a heavy build overlapping the full model set, which pushed the host into swap (peak 13.9 GB, no kills). A model with no supported Mac runtime, such as Nemotron-3-Embed today, is a runtime gap, not a memory limit. The 30B-class challengers would fit the 38 GB generation allowance alone, which is projected, not measured

## Alternatives considered

- **Borrow the workstation's models over the network.** Rejected by the user's decision, and by the
  memory-stack rule "never depend on another host's localhost service".
- **Serve the workstation's embedder (Nemotron-3-Embed-1B) on the Mac.** It has no supported Mac runtime
  (step 2). Community conversions are not upstream and are untested for this model's pooling.
- **Ollama's MLX engine for generation.** This Mac's Ollama 0.34.4 already holds nvfp4 builds of
  Qwen3.8-27B. The frozen li26 harness cannot score them, because `eval_arm.py` checks llama.cpp's
  `/props`. Only its latency was measured, for the reranker gate: at about 7.5K prompt tokens it answered in 18.5 s median against llama.cpp Metal's 27.9 s, 1.5× faster at prefill but still borderline against the 20 s gate (1 of 3 calls over)
- **MLX-LM or LM Studio.** Considered in the macOS page's embedding decision and not activated. There is
  still no measured comparison on this project's workload.
- **Re-pin llama.cpp to b11146 on macOS for MTP drafting.** Recorded as a finding with this host's b11146
  runs as native evidence, but not done here. A pin change is its own reviewed change.

## Overturn conditions

This decision is revisited when any one of these is measured on this Mac:

- swap growth or a memorystatus kill under normal coordinator load with the co-resident set above;
- a required model set whose weights and KV cache exceed the measured headroom;
- the chosen memory reranker LLM missing ai-memory's 20 s gate at 4-8K tokens (more than 5% fallback)
  while a larger machine would meet it;
- a Mac-native Nemotron-3-Embed (llama.cpp registration or an NVIDIA GGUF/MLX) that beats embeddinggemma
  on this project's own retrieval comparison, with the headroom to serve it.
