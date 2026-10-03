Source: <scratch>/s3-r6-inputs.md; capture date: 2026-09-27.
# S3 r6 inputs collected 2026-09-27 (for the r6 revision of blueprints/memory-layer-s3/PREREGISTRATION.md)

## Gateway requirements for every GPT-6 FW role (token-save-manifest-html's verified gateway verdict)
- **Effort:**
  - chat/completions without `reasoning_effort` runs at MEDIUM;
  - `cx/gpt-6-astra-max` pins max (codex.ts L1451-1456; the suffix wins over the body);
  - per-role effort is frozen from the R02 development runs (see capability-gate/gateway-ab-designs.md).
- **Cache and dedup:**
  - the legacy exact semantic cache is armed (temperature 0 is eligible);
  - in-flight dedup covers temperature ≤0.1 non-stream requests;
  - so scored calls send `X-OmniRoute-No-Cache: true` plus `stream: true` (or omit temperature), with a fresh Idempotency-Key per call, sample and arm.
- **Affinity:** a stable `x-omniroute-session` per arm or conversation. Without it, calls scatter across the 4 accounts and lose the prompt cache.
- **Compression:** all OmniRoute compression engines stay OFF, and `codex/*` stays excluded, so the byte-identical path is kept.

## cognee 1.6.1 (setup-only smoke passed, token-save-manifest-html)
- Receipt: `~/.local/state/native-agent-stack/s3-arms/receipts/cognee-install-smoke-20260927.json`.
- **Install:** bare metal from tag v1.6.1 eb90d037's uv.lock (`uv sync --python 3.12 --frozen --no-dev --no-editable`, mirroring the upstream Dockerfile); lane-owned CPython 3.12.14; `env -i`; CPU only.
- **Config:**
  - `LLM_PROVIDER=custom`, `LLM_MODEL=openai/cx/gpt-6-astra-max`, the gateway endpoint and a placeholder key;
  - fastembed `BAAI/bge-small-en-v1.5` (upstream's local default);
  - shipped sqlite, lancedb and ladybug stores;
  - `ENABLE_BACKEND_ACCESS_CONTROL=true`, `TELEMETRY_DISABLED=1`;
  - `DataItem(data_id=uuid5)` pinned per session.
- **Structured output: use instructor `tool_call` mode.**
  - The shipped litellm_native json_object fallback fails at the gateway with 400. The chat→Responses translator moves the system message into `instructions` (OmniRoute toResponses.ts L120-136), and the backend requires "json" in the input messages.
  - Strict `json_schema` also fails with 400, because cognee's KnowledgeGraph lacks `additionalProperties: false`.
- **Per-role models:** `LLM_EXTRACTION_MODEL`, `LLM_SUMMARIZATION_MODEL` and `LLM_QUERY_MODEL`.
- **Hygiene:**
  - cognee folds `llm_temperature=0.0` into every call (config.py L271-298), which makes it cache- and dedup-eligible;
  - fix with `LLM_ARGS={"temperature":1.0,"extra_headers":{"x-omniroute-session":"<arm>","X-OmniRoute-No-Cache":"true"}}` (LLM_ARGS wins, L287);
  - the gateway strips temperature for codex models, so this changes cache eligibility only;
  - cognee CAN send headers.
- **Registration:** cognee is not in manifests/stack.json, so `host_receipts.py` can't file its receipt until r6 registers the candidate. Do that in the r6 PR.
- **Measured:** add 5.2 s and cognify 50.0 s on the canary; recall persisted across a fresh process; 7 calls all at effort_upstream=max; 7,237 tokens in and 2,045 reasoning.

## Live deployments (token-save-manifest-html, 2026-09-27 ~18:15Z)
These are hosting evidence for r6. They are never used as scored arms.
- **Receipts:** `~/.local/state/native-agent-stack/s3-arms/receipts/cognee-live-deploy-20260927.json` and `hindsight-live-deploy-20260927.json`.
- **cognee-live:**
  - runs from the pinned digest on rootless Docker 29.8.1, at 127.0.0.1:3800, with auth on;
  - reaches GPT-6 at max through the container gateway address 10.0.2.2:20128;
  - uses instructor tool_call, LLM_ARGS temperature 1.0 with the session and No-Cache headers, and fastembed on CPU;
  - its lifecycle checks passed: install, use, restart, recovery and persistence;
  - it made 13 gateway calls, all at max, all on 1 account.
- **hindsight-live:**
  - runs the existing lane install as an enabled systemd --user unit on 3710/5433, with LLM `cx/gpt-6-astra-max`;
  - `HINDSIGHT_API_LLM_TEMPERATURE=none` omits temperature everywhere;
  - its default headers carry the session key and No-Cache, and cache affinity uses `openai_prompt_cache_key`;
  - its lifecycle checks passed: install, use, restart, persistence, and recovery after a guard fix (a same-boot stale postmaster.pid with a dead PID is cleared). The failed first attempt is kept.
- **Hindsight per-role knobs, for r6's arm:**
  - `HINDSIGHT_API_{RETAIN,REFLECT,CONSOLIDATION}_LLM_MODEL`;
  - `HINDSIGHT_API_{RETAIN,REFLECT,CONSOLIDATION}_REASONING_EFFORT`;
  - per-operation temperatures.

## Hindsight 0.10.1 (token-stack-e2e-proof, installed earlier today)
- Bare metal from the tag's uv.lock with pg0-embedded, the GPT-6 backbone via OmniRoute; retain worked end to end, and recall persisted across a restart.
- Its request shapes (temperature, max_tokens up to 64000, json_object with the schema in the system message, tools with tool_choice required) returned 9/9 at 200 on sol, luna and astra (this session's probe at 16:05Z).
