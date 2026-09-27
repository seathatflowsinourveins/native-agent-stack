Source: <scratch>/capability-gate/gateway-ab-designs.md; capture date: 2026-09-27.
# Gateway A/B designs: R02, L02 and D03/D04 (reviewed by token-save-manifest-html 2026-09-27; its two findings are fixed here)

Built on the gateway owner's `ab_design` for each feature in `omniroute-feature-verdict.interim.json`, and hosted in
this session's capability-gate harness.

Rules for every arm:
- one `x-omniroute-session` key per CONVERSATION, never one per arm. An accepted explicit header overrides the body identifiers for affinity, so a per-arm constant pins the whole arm to one account (the owner's GPT-6 RH6/L01 finding; measured 2026-09-27: 8 distinct headers spread over 3 accounts, while 7 calls under one header stayed on 1). The arm is tagged separately, by the `otel.environment` value or an Idempotency-Key prefix;
- a fresh `Idempotency-Key` per call;
- `X-OmniRoute-No-Cache: true` with `stream: true` on FW calls, so neither the legacy exact semantic cache nor in-flight dedup can serve a sample;
- the effective effort is read back from call_logs (`scratchpad/effort_window.py`, effort columns only, read-only).

Each design is frozen before its first scored call, with the list of hashes, and gets a GPT-6 review.

## Harness: upstream, not self-written (user direction 2026-09-27; eval-frameworks/report.md W2 and W5)

- **Runner:** promptfoo 0.123.1, the catalog's quality-evaluation pin.
  - Providers: the OpenAI chat provider with `apiBaseUrl: http://127.0.0.1:20128/v1`, one per arm model (docs site/docs/providers/openai.md#L182 at 0.123.1: base URL, headers, response_format and tools, effort).
  - Session hooks (configuration/reference.md#L365) set a session key per conversation and a fresh Idempotency-Key per request. Static headers alone cannot do this.
  - Run with `promptfoo eval -c <cases.yaml> --repeat N --max-concurrency 1 --no-cache --no-share -o <results.json>`. promptfoo's own `--no-cache` is its response cache, separate from `X-OmniRoute-No-Cache`, so both are set.
- **Quality:**
  - a promptfoo Python assertion (configuration/expected-outputs/python.md#L15) that calls li26's own `parse_items` and `filing_scores`, and returns per-filing TP/FP/FN as named metrics;
  - micro-F1 is aggregated from summed TP/FP/FN, never as an average of filing F1.
- **Cached-input share:** taken from the provider's returned cached-token fields (src/providers/openai/util.ts#L997), not promptfoo's `tokenUsage.cached`. Affinity is still observed in call_logs.
- **Statistics:**
  - scipy 1.18.1 `stats.bootstrap(..., paired=True, method="percentile", alternative="greater", n_resamples=10000)`, over cluster-level aggregates where clusters apply;
  - `stats.permutation_test(permutation_type="samples")` for paired swaps;
  - statsmodels 0.15.0 `multipletests(method="holm")` for any family.
  - li26's own `paired_bootstrap` is not reused.

## R02: FW effort (cx/gpt-6-astra, medium by default, versus cx/gpt-6-astra-max)

- **Question:** does max beat medium for FW (chat/completions) roles by enough to pay for its reasoning tokens?
- **Tasks, two parts:**
  1. **Wire and cost on a deterministic task.**
     - Items: a frozen, seeded subset of li26's 8-K filings. Take 60 filings, stratified by item count, from the li26 acquisition, pinned by the sha256 in `plan.json`.
     - Requests: built with li26's `build_request` and prompt template, with the llama.cpp-only fields (`chat_template_kwargs`) dropped. The gateway's strict `json_schema` needs `additionalProperties: false` on every object: the GPT-6 Responses backend rejected cognee's KnowledgeGraph without it (400). So first send ONE li26 request with the converted schema through the gateway. If it fails, add `additionalProperties: false` to li26's schema in BOTH arms, or use tool calling. Never fall back to `json_object`: through the gateway it needs the word "json" in the input messages, because toResponses.ts L120-136 moves the system prompt into `instructions`.
  - Session keys: one per filing.
     - Scoring: li26's `parse_items`, `filing_scores` and `micro_f1`, plus `paired_bootstrap` (seed 20260926).
     - li26 sits near ceiling for GPT-6 (#359: 0.992–0.995 for every tier). So this part is a cost and wire test with a non-inferiority bound, not a quality ranking.
  2. **Quality where it matters.** The FW lanes are the S3 memory systems' LLM roles: extraction, retain/reflect and consolidation. That comparison runs as S3 r6 development runs on S3's separate development question split, never the confirmatory set, and S3 r6 freezes each role's effort from it.
- **Arms:** A = `cx/gpt-6-astra` (no `reasoning_effort`, so medium); B = `cx/gpt-6-astra-max`. Prompts, schema and order are identical. The two arms are interleaved per filing, with the order alternating.
- **Metrics:**
  - micro-F1;
  - strict-schema validity;
  - reasoning and output tokens from usage;
  - latency p50 and p95;
  - timeouts and 429s;
  - cache-read share (call_logs and `/api/usage/cache-health`, read-only).
- **Wire check** (must pass before scoring): a `-max` call logs `reasoning_effort_upstream = max`, and an effort-less call logs `medium`. These columns are filled only on rows with encrypted reasoning.
- **Decision:**
  - B is adopted for a role only if its quality gain is significant: on the S3 development runs for memory roles, or on li26 by a paired-bootstrap lower bound above 0.
  - Otherwise, where A is non-inferior (lower bound ≥ −0.02) and cheaper, the role keeps medium or moves to `cx/gpt-6-sol` medium (#359's mechanical tier).

## L02: Codex context, compaction and tool-output limits (the omniroute profile, cx/gpt-6-*)

- **Question:** does raising `model_context_window` and `model_auto_compact_token_limit` preserve long-task quality and the prompt cache better than the default?
- **Arms:**
  - control: 272000 / 244800 / 10000;
  - candidate: 872000 / 784800 / 10000;
  - both set with `-c` per run, and `model_max_output_tokens` omitted.
- **Models:** Astra/max and Sol/medium, evaluated independently.
- **Tasks:** matched multi-hour Codex tasks that cross at least one control compaction boundary. Two sources:
  - replays of this repository's real GPT-6 review tasks, meaning PR reviews with frozen heads and frozen expected findings (the findings GPT-6 already confirmed on #404, #410 and #411);
  - one long synthetic task with planted early decisions that must be recalled after compaction.
- **Metrics:**
  - correctness: the recall of expected findings, and of each planted decision;
  - exact evidence recovery;
  - tool-result truncation events;
  - compaction count and trigger;
  - cached versus uncached input and total tokens (from Codex `turn.completed` usage);
  - latency;
  - resolved model metadata.
- **Decision:** the candidate is adopted per model only if correctness is non-inferior AND total billed tokens fall.
- **Known divergence:** both arms sit at Codex's 90% compaction clamp (244800/272000 and 784800/872000; GPT-6's catalog has a 272000 default and an 872000 ceiling, per RH6/L02). OmniRoute's own guide (docs/guides/CODEX-CLI-CONFIGURATION.md:146) recommends 85-88%, "never above 90%". An optional third arm at 88% (767360) tests that advice; otherwise record the divergence.
- **What it measures:** behind the gateway, compaction runs locally, with no remote compaction V2 for a non-OpenAI provider (RH6/L03). So L02 measures local summarization.
- **Cost warning:** this is the costliest A/B, measured in hours per arm. Run it after R02 and D03/D04.

## D03/D04: prompt-cache affinity and singleton combos

- **Question:** can a lane move to a singleton combo (for example `lane-judgment-astra-max`) without losing prompt-cache continuity or changing the resolved model and effort?
- **When:** only before a lane adopts a combo.
- **Arms:**
  - (a) the direct model name;
  - (b) a single-model priority combo;
  - (c) the combo with `promptCacheAffinityEnabled` toggled. This arm is the owner's to apply and restore.
- **Tasks:** the same frozen R02 li26 subset, sent as matched multi-turn conversations. There are 10 conversations of 6 turns, and each turn reuses the growing prefix, so the cache has something to hit. Each conversation gets its own session key, so 10 keys per arm.
- **The singleton combo** needs canonical `codex/` targets (RH2/D04 correction), universal handoff off (D05) and an explicit max tier (G5/D03 correction).
- **Metrics:**
  - the resolved upstream model and effort per call (call_logs);
  - cache-read share per turn;
  - account spread across the 4 accounts;
  - latency;
  - quality: li26 micro-F1, as a non-regression check.
- **Decision:** a lane may adopt its singleton combo if the resolved model and effort are identical, the cache-read share is non-inferior (per-turn paired, lower bound ≥ −5 points), and quality is non-inferior.

## Evidence and receipts

- Each run records its arm identity tags (`otel.environment` or request headers), the call_logs row counts per arm, and the frozen hashes.
- Receipts go through `scripts/host_receipts.py record` at a published main commit.
- Results keep the li26 cost test, the S3 development-run quality, and vendor claims as separate evidence classes.
