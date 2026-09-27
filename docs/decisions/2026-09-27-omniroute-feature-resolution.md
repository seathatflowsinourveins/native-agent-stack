# Decision: every OmniRoute gateway feature resolved from upstream source, with cross-family refutation, and what each lane may enable (2026-09-27)

**Status: research verdict, recorded 2026-09-27.** This record changes no host setting. Gateway enactment (the unit, settings writes and their read-backs) belongs to the session that installed the gateway (`docs/decisions/2026-09-27-omniroute-account-pool.md`); it takes this verdict as its input.

The user asked on 2026-09-27 for "full landscape advanced sota practice" for the gateway at `http://127.0.0.1:20128`, with every token-saving and routing feature resolved and enabled to the highest quality, powering GPT-6 runtime workers. Two later directions followed: every feature resolved and each lane opting in only after its own A/B, and GPT-6 carrying the heavy work through the gateway.

**Build under review:** `release/v3.8.51` `a58000c7` + #14904 + #13788 (BUILD_SHA `dd6e9607e`). Upstream prefix used below: `OR` = https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3.

Evidence: [`evidence/artifacts/omniroute-features-20260927/`](../../evidence/artifacts/omniroute-features-20260927/README.md).

## Method

- **Features.** 55 features in 8 groups: compression engines and guards (C00–C20), caching (K01–K05), reasoning and effort (R01–R04), routing (D01–D12), search (S01), other gateway surfaces (S02–S07), client wiring (L01–L04) and operations (O01–O02). The list came from the live settings routes, the 80 feature flags, the 721 API routes and the dashboard pages.
- **Proposals.** Each feature got a deep dive at the pin, giving the default, the control, CX/FW applicability, quality and prompt-cache effect, a resolution state and the exact config. 32 dives came from Claude (Opus 5.5, `stack-researcher`) and 23 from GPT-6 (`gpt-6-astra`, effort max).
- **Adversarial refutation.** GPT-6 refuted every proposal in grouped jobs through two lenses: quality/fidelity and token/prompt-cache. It read deterministic evidence packets (the cited line ranges, extracted by script) plus the source checkout. It verified that all packet lines match the pin, and reproduced defects by running the pinned helpers in isolation. Verdicts are upheld, corrected (config or claims fixed) or refuted (state changed).
- **Merge.** The final position of each feature is its proposal as amended by its refutation. It was merged deterministically (`scripts/build_verdict.py.txt`), which is the final verdict. Each corrected or refuted feature carries the refuter's material findings in `refutation_findings`; they override any conflicting sentence in the proposal's descriptive fields. A GPT-6 wording pass (`synth-r1`) did not return: two stream disconnects, then the runner's 3000 s cap (exit 124, no usage reported; `synth-r1-errors.json`, `gpt6-job-usage.json`). It is kept as a failed attempt.
- **Where the GPT-6 work ran.** On the packaged landscape-sweep lane (`codex_call.sh` / `codex_job.py`, `--gpt6-provider omniroute`, lane-local `CODEX_HOME`, read-only sandbox) against the pooled accounts.

**States are recommended dispositions, not the gateway's current configuration.** Observed state and enactment are separate:
- `enabled_verified`: recommended on, and observed live and verified.
- `enable_after_ab`: recommended per lane, and only after that lane's own measured A/B. Nothing is configured by this record.
- `hold`: recommended off, for a quality, security or cache reason from source. Some holds are on by default in the live gateway; see "Observed state" below.
- `not_applicable`: no consumer, or no provider connected.

**Observed state that differs from the recommendation.** The feature flags `UNIVERSAL_CONTEXT_HANDOFF_ENABLED` (D05) and `OMNIROUTE_EMERGENCY_FALLBACK` (D10) are on by default (`gateway-snapshot-redacted.json`). Both are inert today: there are no user combos for handoff, and no Nvidia connection for the fallback. Turning them off is a top action for the gateway operator.

## Result: 32 hold, 7 enabled and verified, 9 after a lane A/B, 7 not applicable

The feature matrix with sources and lineage is [`omniroute-feature-verdict.json`](../../evidence/artifacts/omniroute-features-20260927/omniroute-feature-verdict.json).

- **Compression (C00–C20): 17 hold, 3 not applicable (C13 OmniGlyph, C15 MCP accessibility output, C19 context editing) and 1 enabled and verified (C20, the unconditional cache-aware downgrade).** Every engine that can run on CX or FW traffic is hold.
  - The labels "safe default" and `lossy:false` do not hold for coding-agent or extraction traffic:
    - `lite` truncates tool outputs over 2000 characters (OR `open-sse/services/compression/lite.ts` L148-169; the 2000-character default at L24);
    - the `codex-responses` minifier changes large integers and decimals (`1234567890123456711` → `…800`, `1.50` → `1.5`), reproduced;
    - `session-dedup` keys collide between multipart and string messages and rewrite an earlier user message, reproduced;
    - caveman, relevance, aggressive, llmlingua and ultra rewrite or prune content;
    - the headroom engine parses numbers into JS doubles.
  - **The current configuration allows no per-lane opt-in (C00, refuted from ON-OPT-IN).**
    - An exclusion overrides the request header (OR `open-sse/handlers/chatCore.ts` L1439-1450), and the live `codex/*` exclusion covers every GPT-6 lane.
    - Exclusions match the bare model id or `provider/model` (OR `open-sse/services/compression/exclusions.ts` L50-70), and effort suffixes survive until after the compression gate. So a narrower exact-model exclusion (for example `codex/gpt-6-astra`, `codex/gpt-6-sol`) would leave suffixed variants such as `-max` eligible (review of this record, reproduced with the pinned helper). That is a possible lane selector, but it is untested, and CX lanes that send suffixed ids would also become eligible.
    - Enabling the master without the exclusion turns on proactive and last-resort compaction for FW chat, which neither `x-omniroute-compression: off` nor a per-key opt-out stops (#11255).
  - The live state (compression off, `codex/*` excluded) is therefore the resolution, not a gap.
- **Semantic cache (K02: hold) and in-flight dedup (K04: hold).**
  - **The legacy exact cache is armed today:** OR `open-sse/handlers/chatCore.ts` L1249, `settings.semanticCacheEnabled !== false`.
    - There is no supported global switch for it: `PUT /api/settings/cache-config` writes the `databaseSettings` namespace, which chatCore never reads, and `PUT /api/settings` strips unknown keys.
    - Its key omits effort, instructions and tool-call identity, and the executor strips temperature, so a hit replays one stochastic sample, possibly at another effort.
    - A promoted entry can live about 90 minutes, and hits are counted twice, both reproduced.
  - **`OMNIROUTE_SEMANTIC_CACHE_ENABLED` controls only the vector layer**, which is already off (OR `open-sse/config/semanticCacheConfig.ts` L14-19, L120-123).
  - **In-flight dedup** accepts non-streaming requests at temperature ≤0.1, and its hash omits `text.format`. The idempotency fingerprint omits Chat `reasoning_effort`.
  - **The protection is per request, at the client** (top actions below).
- **Routing.**
  - Session affinity (4 h) with the codex round-robin sticky-1 strategy is `enabled_verified` (D01, D02).
  - The upstream prompt cache (K01) is the only live saving: about 94% of input tokens are served from cache, from the gateway's own `/api/cache` (`own-reports-before.json`).
  - Emergency fallback, the task-aware router, fallback chains, universal handoff, reasoning routing rules and quota preflight are hold. Each can silently change the model, the effort or the cached prefix.
- **`enable_after_ab` (9):**
  - D03 prompt-cache affinity, which applies to combos only;
  - D04 singleton combos, which need canonical `codex/` targets and an explicit effort tier per role (max for judgment, sol medium for mechanical work);
  - D06 lane aliases;
  - L01 Codex provider transport fields;
  - L02 Codex context and compaction keys, 272000/244800 against 872000/784800 (GPT-6 catalog default 272000, ceiling 872000; Codex clamps compaction at 90%);
  - L04 framework client configuration;
  - R02 the `-max` suffix for framework effort;
  - S01 the search backend (bake-off; no Tavily);
  - S04 observability wiring.

  The designs for R02, L02 and D03/D04 are hosted by the capability-gate harness of `token-efficiency-gpt6-workers`, reviewed against these records.

## Measured through the gateway today

- **Effort** on `/v1/chat/completions`, read back from the gateway's own `call_logs` effort columns (read-only; `probes/effort-readback-20260927T1720Z.json`, requests in `probes/probe-max*.json`):

  | request | upstream effort | reasoning tokens |
  |---|---|---|
  | `cx/gpt-6-astra` without `reasoning_effort` | **medium** | 105 |
  | `cx/gpt-6-astra-max` | **max** | 279 |
  | `-max` plus one tool | **max** | 675 (tool call returned) |
  | `reasoning_effort=xhigh` plus tool | xhigh | 330 (tool call returned) |

  So a framework that sends no effort runs at medium. The `-max` suffix needs no alias (OR `open-sse/executors/codex.ts` L1451-1456). The OpenHands SDK caveat (tools plus reasoning rejected on chat/completions) does not occur through the gateway.
- **A tool-bearing request with no system or developer message carried about 2,515 extra prompt tokens.** That is the executor's default instructions, which it injects only when tools are present and `instructions` is empty (OR `open-sse/executors/codex.ts` L1374). The probe sent only a user message, and repeats were mostly served from prompt cache. A request that carries its own system message is not measured here.
- **Structured output through the gateway** (cognee 1.6.1 smoke; `records/cognee-structured-output-smoke.json`):
  - `response_format: json_object` returns 400 unless "json" appears in the input messages. The chat→Responses translator moves the first system message into `instructions` (OR `open-sse/translator/request/openai-responses/toResponses.ts` L120-136).
  - Strict `json_schema` returns 400 unless every object sets `additionalProperties:false`.
  - Tool calling works.
- **Session affinity.** The affinity key is the first of: the session headers, body metadata or session ids, `conversation_id`, `prompt_cache_key`, then a sha256 of the first input (OR `src/sse/services/sessionAffinityPin.ts` L197-221). So a caller without a header still gets affinity, keyed on its first input.
  - `call_logs.session_tag` is the conversation id tracked across turns (OR `open-sse/services/conversationTracker.ts`; `chatCore.ts` L1134), not the header.
  - Measured account spread (`probes/account-spread.json`): one shared header gave 1 account over 7 calls; 8 distinct headers gave 3 accounts over 8 calls.

## Top actions

1. **Framework callers on `cx/*`:**
   - omit temperature, or send `X-OmniRoute-No-Cache: true` with `stream: true`;
   - use a fresh `Idempotency-Key` per call, sample, effort or experiment arm;
   - when sending `x-omniroute-session`, use one stable value per conversation. An explicit header overrides the body keys, so a constant shared by independent workers pins them all to one account.
2. **Direct-HTTP judgment roles use `cx/gpt-6-astra-max`.** Codex CLI lanes already pass `model_reasoning_effort=max` and logged max/max.
3. **Structured output from frameworks:** tool calling, or schemas with `additionalProperties:false`. `json_object` needs "json" in a user message.
4. **Keep compression off with `codex/*` excluded.** Set the flags `UNIVERSAL_CONTEXT_HANDOFF_ENABLED=false` and `OMNIROUTE_EMERGENCY_FALLBACK=false` (no restart needed). Any combo keeps prompt-cache affinity on, universal handoff off, canonical `codex/` targets and an explicit effort tier per role.
5. **Watch upstream:**
   - #14904 and #13788 merging, or a 3.8.51 tag, means a re-pin;
   - #14907/#14908 (thread-scoped `prompt_cache_key`);
   - #14720, #14721, #14651/#14652 (effort handling);
   - #14484 (semantic cache).

   Issue #14866 ("release branch not green") closed on 2026-09-27 at 08:46:47Z, with the comment "release-green again at a58000c76" (`upstream-issue-14866.json`). The account-pool record's lines about red CI date from before that; the build stays a canary because it is off the release line.

A framework-only second instance (its own `DATA_DIR` and port, upstream's documented scale-out) is the clean way to give framework traffic settings that differ from the CX default; the exact-model exclusion above is an untested alternative. It needs the user's own OAuth sign-ins in that instance, and is raised separately.

## Token practice of this run (counted per client, never summed)

- **Attempt 1:** a Claude Ultracode workflow with 55 deep dives and two refuters each.
  - 37 Opus children ran before the old account's weekly limit; 89 agents returned null. Retained with their usage in `phase0-attempt1-child-usage.json`.
  - Usage: 328,452,485 cache-read, 7,979,357 cache-creation, 2,632,554 output tokens.
  - A median of 63 requests per child, from a median first prompt of 20,467 tokens.
  - Tool mix: Bash 54.7%, Read 24.4%, context-mode 18.3% of 2,716 calls (`phase0-attempt1-tool-counts.json`). No code-index tool was used, because the OmniRoute checkout was not indexed.
- **The redesign:**
  - reused the 32 completed dives;
  - indexed the checkout in jcodemunch and codebase-memory;
  - extracted evidence packets by script;
  - grouped items;
  - moved the remaining research and every refutation to the pooled GPT-6 lane.

  Per-job GPT-6 usage is in `gpt6-job-usage.json`.

## Overturn conditions

- Upstream merges the re-pin changes, or any change to a resolved mechanism: `chatCore.ts` compression gating, the semantic-cache toggle split, `toResponses.ts` system handling, or the effort caps. Re-run the affected features.
- A lane's preregistered A/B shows an `enable_after_ab` feature is non-inferior in quality with fewer upstream tokens: that lane adopts it.
- A framework-only instance exists: the framework-lane holds (compression, semantic cache, dedup) can be tested there without touching the CX default.
- The posture changes (multi-user, non-loopback, API keys): per-key namespaces and per-key compression opt-outs become available and K02, K04 and C00 are re-resolved.

## Limitations

- **Structural checks only on this host.** The byte-identity of the default path is established from source and from the live settings read-back, not from a captured request body.
- **Unmeasured:** the net token effect of any `enable_after_ab` feature, and the recall of the duckduckgo-free search backend beyond the earlier probe.
- **Same-family refutation.** The GPT-6 dives were refuted by GPT-6 (adversarial, fresh context); the Claude dives were refuted cross-family. The deterministic merge takes the refuter's state and config wherever a refutation corrected or refuted a proposal.
- **One host.** None of this certifies another host.
