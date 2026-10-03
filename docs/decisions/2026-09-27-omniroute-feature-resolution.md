# Decision: every OmniRoute gateway feature resolved from upstream source, with cross-family refutation, and what each lane may enable (2026-09-27)

**Status: research verdict, recorded 2026-09-27.** This record changes no host setting. Gateway enactment (the unit, settings writes and their read-backs) belongs to the session that installed the gateway (`docs/decisions/2026-09-27-omniroute-account-pool.md`); it takes this verdict as its input. Later builds changed several resolutions; the dated status section at the end settles each remeasurement promise.

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
2. **Judgment roles use `cx/gpt-6-astra-max`.** Codex CLI lanes send `reasoning.effort=max` on every request, but part of their turns return no reasoning.
   - History (2026-09-27): this action first said Codex CLI lanes "already pass `model_reasoning_effort=max` and logged max/max". A correction at about 20:00Z then said 616 of their rows "carried no effort". That correction was itself wrong, and it is withdrawn.
   - **What the gateway logs.** `call_logs` fills its two effort columns only when the response carried encrypted reasoning (OR `src/lib/usage/callLogs.ts` L646-653). A turn that returned no reasoning therefore logs no effort, whatever the request sent.
   - **What was sent** (`probes/codex-sent-effort-20260927.json`, from the stored request bodies through the gateway's own detail API). Every no-reasoning row that kept a body carries `reasoning.effort=max`: 541 of 541, and 77 rows kept no body. The executor applies an explicit effort or a `-max` suffix on both the native and the translated path (OR `open-sse/executors/codex.ts` L1425-1464). So upstream was asked for max; that is inferred from source, because these rows kept no upstream body.
   - **What came back** (`probes/codex-effort-coverage-20260927.json`, `codex/gpt-6-astra` `/v1/responses`, 12:00-20:00Z):
     - 617 turns logged 0 reasoning tokens. 464 of them completed (status 200); 148 were cancelled by the client (499) and 5 failed upstream (4×502, 1×503). All 3,825 turns that reasoned completed. Among successful turns, then, 464 of 4,289 (10.8%) returned no reasoning (status split per the cards review).
     - The zero-reasoning turns are full task turns: median input 28k tokens, median output 190 (an immediate tool call).
     - `token-save-practice-gpt6` matched rows to rollouts and found them on first and `spawn_agent` turns. By gateway conversation, 72 start with one and 89 mix them in otherwise, while 94 multi-row conversations always reasoned.
     - A `-max` request (19:55:49Z) shows the same pattern, so the suffix does not change it.
   - **Consequence:** this is upstream model behaviour under max, not a transport defect, and the gateway has nothing to fix. Whether it costs quality has to be measured on those turns; the effort columns cannot show it.
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
- **Some GPT-6 turns of this run returned no reasoning.** The GPT-6 dives and refutations ran as Codex CLI jobs configured for `cx/gpt-6-astra` at max (`gpt6-job-usage.json`). Every job window contains turns that returned 0 reasoning tokens at max (`probes/codex-effort-coverage-20260927.json`). The shared gateway carried other lanes at the same time, so no row is attributed to a job. Their records stand as written.
- **Same-family refutation.** The GPT-6 dives were refuted by GPT-6 (adversarial, fresh context); the Claude dives were refuted cross-family. The deterministic merge takes the refuter's state and config wherever a refutation corrected or refuted a proposal.
- **One host.** None of this certifies another host.

## Status on 2026-10-03: later builds and each remeasurement promise

This appended settlement preserves the 2026-09-27 research verdict and its evidence. Repository sources below were re-read from main at `9b0b8d6d25f9e3fb8f71770500e774170423315e`; the original record and its two evidence directories are pinned at `e2e048053b151ac9c2ba269864cb4adf035058d3`. Upstream issue/PR state was read with `gh api --method GET`, stamped by `date -u` in the same command at **2026-10-03T10:34:43Z**. The destination gateway's build and posture are **reported by its owner**, from the #608 comment re-read at that time, rather than independently observed here.

| Promise | Record lines at `e2e04805` | Settlement | Source |
| --- | --- | --- | --- |
| Turn off `UNIVERSAL_CONTEXT_HANDOFF_ENABLED` and `OMNIROUTE_EMERGENCY_FALLBACK` | 25, 106 | **Partly re-checked on NativeStack 20129; inferred, not printed, for 20128.** On 20129 the 2026-09-30 pre-apply tail prints the handoff flag off (`["false", "db"]`), and the routing lane's record notes that a separate 20129 workflow set both flags false and read them back at 2026-09-28T03:50:11Z-03:50:26Z. The pre/post aggregates each report 36 checks with 0 failures, but the script version that printed them is not retained. The published `post_apply_checks.py`, whose definition tests both flags on both ports, is the 00:40:42Z rewrite: it printed `checks=40` when section C ran it, and its check names differ from the printed lines. The 20128 flags, and the 20129 emergency-fallback flag at the apply, are therefore inferred from that later definition, not printed. Section C's eight listed failures are compression checks; flag and cache results are not printed there, so that section does not establish their outcomes. **Open with the destination gateway's owner:** neither flag is observed on that gateway here. | [Recorded outputs:6-7,14,18-19,25,39,42-56][checks]; [retained definition:178,194-196][check-definition], [its check names:206,240 and output:277][retained-script]; [script provenance:172-176,187-189][rebuild]; [20129 read-back record:136-137][routing-decisions]. |
| K02 exact/semantic cache and K04 in-flight dedup: client mitigation and mechanism re-check | 43-50, 92-94 | **Partly re-checked.** That the legacy exact cache stayed armed on both ports at the `2f42a9ac1` rebuild is inferred, not printed: only the retained 00:40:42Z rewrite of the check script asserts it, and the 36-check version behind the pre/post aggregates is not retained. The last printed read of its armed state found on main is in the routing lane's route map at the earlier `dd6e9607e` build, whose measurement window ended about 2026-09-28T00:13Z: exact cache on for 20128, the same configuration on 20129. The A/B-arm rule remains per-request mitigation: omit numeric `temperature: 0` or send `x-omniroute-no-cache: true`; the original action also requires streaming and fresh idempotency keys. Upstream #14484 is open. **Open with the destination gateway's owner:** cache-key composition and K04's resolved defects have not been re-checked here at `2f42a9ac1` or v3.8.52; an armed-cache assertion does not revalidate either mechanism. | [Retained check:178,191-193][check-definition]; [aggregates:25,39][checks]; [script provenance:172-176,187-189][rebuild]; [`dd6e9607e` cache read:159-160][route-mapper-cache]; [PLAN.md:166][plan]; [original action:91-94][original]; [#14484 GET](https://api.github.com/repos/diegosouzapw/OmniRoute/issues/14484), stamped 2026-10-03T10:34:43Z. |
| C00-C20 compression hold | 31-42 | **Superseded by the user-directed 2026-09-30 rebuild on 20129.** It enabled ten engines at upstream's per-engine settings with the recorded defect mitigations; this was direction, not an A/B overturn of the quality holds. On 20128 the master remained off and `codex/*` remained excluded. | [Rebuild record:1-8,64-80][rebuild]; [20128 read-back:18][checks]. |
| Re-pin or a resolved mechanism changes: re-run affected features | 107-113, 135 | **Partly re-checked; the overturn condition fired.** #13788 remains open. #14904 closed unmerged and was covered by #14886, merged 09-28; #14720, #14721 and #14652 merged 09-29, and #14651 closed. #14907, #14908, #14484 and #15167 remain open; #14866 closed at 2026-09-27T08:46:47Z. NativeStack's later source base is `2f42a9ac1`, and npm 3.8.51 has a separate package qualification. The peeled `v3.8.51` commit is `c1e30b7676975feb298b49eff6ff58923c04b89e`. Its effort-cap source is unchanged from the record's `a58000c7` pin: `open-sse/executors/codex/reasoningSuffix.ts` is the same blob, `627f2a339fb0c3ddd5d26c35056842684dd8e1a1`, at both commits, and `codex.ts`'s `MAX_EFFORT_BY_MODEL` and `clampEffort` are identical. The effort-cap trigger therefore did not fire; the condition fired on the re-pin. GPT-6.1 Sol is in neither alias set there, so `clampEffort` caps it at `xhigh`; on NativeStack, `max` reaches the wire for it through the upstream PR 15167 carry on 20128 (`cf6748d04`). The destination owner reports `release/v3.8.52` at `23a11484` plus `24bbadba`, `6c799005`, `0585aba5`, BUILD_SHA `720e881a4`. The partial re-checks are the rebuild's post-apply checks and the GPT-6.1 Sol effort qualification at `cf6748d04`: offline executor-body checks (nothing sent) plus historical live probes whose returned call-log effort read-backs show max. **Open with the destination gateway's owner:** the complete 55-feature re-run is not recorded for either later gateway build. | [Rebuild record:45-55,87-101][rebuild]; [npm receipt:9-15,121-128][npm-qualification]; [post-apply outputs:27-56][checks]; [Sol record:3-16][sol-max], [offline wire:1-53][wire], [live probes:3-85][probe]; [destination report][destination]. [#13788](https://api.github.com/repos/diegosouzapw/OmniRoute/issues/13788), [#14904](https://api.github.com/repos/diegosouzapw/OmniRoute/issues/14904), [#14886](https://api.github.com/repos/diegosouzapw/OmniRoute/issues/14886), [#14720](https://api.github.com/repos/diegosouzapw/OmniRoute/issues/14720), [#14721](https://api.github.com/repos/diegosouzapw/OmniRoute/issues/14721), [#14652](https://api.github.com/repos/diegosouzapw/OmniRoute/issues/14652), [#14651](https://api.github.com/repos/diegosouzapw/OmniRoute/issues/14651), [#14907](https://api.github.com/repos/diegosouzapw/OmniRoute/issues/14907), [#14908](https://api.github.com/repos/diegosouzapw/OmniRoute/issues/14908), [#14484](https://api.github.com/repos/diegosouzapw/OmniRoute/issues/14484), [#15167](https://api.github.com/repos/diegosouzapw/OmniRoute/issues/15167), [#14866](https://api.github.com/repos/diegosouzapw/OmniRoute/issues/14866) GETs at the stamp above; [#14904 replacement comment](https://github.com/diegosouzapw/OmniRoute/pull/14904#issuecomment-5880896394), GET stamped 2026-10-03T10:35:45Z; [peeled tag GET](https://api.github.com/repos/diegosouzapw/OmniRoute/git/tags/770faa7144f58ada625afc6efe572c8335484ec4), stamped 2026-10-03T10:35:05Z; [pinned effort-cap source:11-30,38-49][effort-caps] and [its copy at `a58000c7`][effort-caps-pin], one blob by contents GETs [at `a58000c7`](https://api.github.com/repos/diegosouzapw/OmniRoute/contents/open-sse/executors/codex/reasoningSuffix.ts?ref=a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3) and [at `c1e30b76`](https://api.github.com/repos/diegosouzapw/OmniRoute/contents/open-sse/executors/codex/reasoningSuffix.ts?ref=c1e30b7676975feb298b49eff6ff58923c04b89e), stamped 2026-10-03T12:58:08Z-12:58:11Z with the `codex.ts` reads; [`clampEffort` at `c1e30b76`:319-340][clamp-effort], identical to [`a58000c7`:342-363][clamp-effort-pin]; [PR 15167 carry:126][rebuild] and [`cf6748d04`:3-4][sol-max]. |
| `enable_after_ab` features and routing holds | 55-66, 136 | **Open with unit D3's routing A/B owner and each consuming lane.** D04, D06 and D11 stay held pending unit D3's promptfoo A/B reports; D11 additionally needs a result that answers its hold reason. Wave unit D3 is distinct from feature D03 (prompt-cache affinity), and no main source places D03 on unit D3's A/B: the routing lane's adjudication defers its prompt-cache placement practice (P4) to a D03 combo A/B. For D03, R02, L01, L02, L04, S01 and S04, no qualifying lane A/B report was found in main at the SHA above. The partial effort checks do not measure non-inferior task quality with fewer upstream tokens. Each of these seven features therefore remains open with its consuming lane's owner. | [Original feature list and gate:55-66,136][original]; [routing record:45-50,93-95,205-208][routing]; [routing adjudication, `groups[0].items[3]` (P4)][routing-adjudication]; [A/B requirements:5-10,20-37][ab-requirements]. |
| A framework-only instance exists, so test framework-lane holds there | 115, 137 | **Enacted for the instance; open with its framework-lane owner for the A/B.** 20129 exists as `omniroute-fw.service`. Its compression was enabled by direction, not A/B-tested against these holds. The K02 and K04 dispositions are unchanged. That the legacy exact cache is still armed there is inferred, not printed: the retained 00:40:42Z rewrite of the rebuild's check asserts it, the 36-check version behind the printed aggregates is not retained, and the routing lane's last printed read, at `dd6e9607e`, showed 20129 with the same cache configuration as 20128. That check does not qualify dedup. | [Rebuild scope:10-13 and settings:64-80][rebuild]; [recorded unit read-back:8-13,31,37][unit-readback]; [retained cache check:178,191-193][check-definition] and [aggregates:25,39][checks]; [script provenance:172-176,187-189][rebuild]; [`dd6e9607e` cache read:159-160][route-mapper-cache]. |
| Multi-user, non-loopback or API-key posture triggers K02/K04/C00 re-resolution | 138 | **Partly re-checked; the overturn condition was not triggered.** NativeStack's keyless loopback posture stands in the rebuild record. The destination owner reports listeners on 127.0.0.1 and `REQUIRE_API_KEY=false`. That report is not an independent destination read-back by this builder. | [Rebuild record:6-8][rebuild]; [destination report][destination], GET stamped 2026-10-03T10:34:43Z. |
| Quality of zero-reasoning turns; net token effects and search recall still unmeasured | 104, 143-144 | **Open with the GPT quality-measurement lane and the feature/search consuming lanes.** No measurement closing zero-reasoning task quality, the net token effect of the gated features, or DuckDuckGo recall beyond the earlier probe was found in main at the SHA above. Effort metadata and a successful smoke are not those measurements. | [Original quality and limitations:104,143-144][original]; [account-pool search limitation:512][account-main]; [deterministic A/B requirements:5-10][ab-requirements]. |
| Structured-output handling after a mechanism or build change | 81-84, 105 | **Open with the destination gateway's owner.** The recorded measurement is only on `dd6e9607e`: the cognee smoke's `json_object` and strict-schema failures, with tool calling working. The deciding mechanism remains `toResponses.ts`'s first-system-message handling. No later measurement closing this re-check was found in main at the SHA above. | [Original build and measurement:7,81-84,105][original]; [structured-output smoke:49-99][structured-smoke]. |
| qmd scope, directional A/B and the claimed #381 Amendment 3 configuration | qmd README:3,45 (companion evidence) | **Partly re-checked; the E2E baseline plan supersedes this host configuration.** The collection scope is enacted in the main carrier record. The qmd A/B is directional only, not lane acceptance. The README's claim that this work was "recorded for #381 Amendment 3" is incorrect as a statement about main: Amendment 3 has no qmd configuration. Its sealed history stays intact, and the later Amendment 4 plan assigns the E2E host baseline to the new distribution. The frozen README is corrected here, not rewritten; qualification on that baseline remains open with the Gate A owner. | [Scope record:341-361][scope-carrier]; [qmd README:3,40-45][qmd]; [Amendment 3:702-776 and pre-run record:777-784][amendment3]; [new-baseline plan:395-408][new-baseline]. |
| #14866 and the account-pool record's red-CI limitation | 113 | **Superseded by the issue's closure at 2026-09-27T08:46:47Z.** The account-pool record now has one dated `Update 2026-10-03` sub-bullet; its older lines 102 and 489 remain historical. The build stayed a canary because its head was off the release line, and the 2026-09-30 rebuild replaced it. | [Retained closure artifact][issue14866]; [#14866 GET](https://api.github.com/repos/diegosouzapw/OmniRoute/issues/14866), stamped 2026-10-03T10:34:43Z; [account-pool update](2026-09-27-omniroute-account-pool.md#limitations-and-residuals); [rebuild record:3-8][rebuild]. |

Searches of all tracked main paths used the feature identifiers, client/framework A/B terms, zero-reasoning quality, and search/structured-output mechanisms; selected related dated records were read at the pinned revision. A requirement, source review, offline payload check or implementation smoke does not close the preregistered quality/token comparison. The next feature sweep must cover the complete later-build matrix, cache keys/dedup, structured output, quality and search recall, and each consumer lane's A/B; the qmd lifecycle sweep must qualify scope and retrieval on the new E2E baseline.

[checks]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/omniroute-rebuild-20260930/checks/recorded-outputs.txt#L12-L56
[check-definition]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/omniroute-rebuild-20260930/scripts/post_apply_checks.py.txt#L178-L196
[retained-script]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/omniroute-rebuild-20260930/scripts/post_apply_checks.py.txt#L206-L277
[routing-decisions]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/omniroute-routing-20260928/decisions.json#L136-L137
[route-mapper-cache]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/omniroute-routing-20260928/route-mapper-final.json#L159-L160
[routing-adjudication]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/omniroute-routing-20260928/adjudication.json
[plan]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/omniroute-rebuild-20260930/PLAN.md#L166
[original]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/e2e048053b151ac9c2ba269864cb4adf035058d3/docs/decisions/2026-09-27-omniroute-feature-resolution.md
[rebuild]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-30-omniroute-rebuild.md
[npm-qualification]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/receipts/omniroute-3851-npm-qualification-20260930.json#L9-L15
[sol-max]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/omniroute-sol-max-20260930/README.md#L3-L16
[wire]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/omniroute-sol-max-20260930/checks/effort-wire-candidate-B3.json#L1-L53
[probe]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/omniroute-sol-max-20260930/checks/probe-gate-after-switch.json#L3-L85
[destination]: https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5966048242
[effort-caps]: https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/executors/codex/reasoningSuffix.ts#L11-L49
[effort-caps-pin]: https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/executors/codex/reasoningSuffix.ts#L11-L49
[clamp-effort]: https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/executors/codex.ts#L319-L340
[clamp-effort-pin]: https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/executors/codex.ts#L342-L363
[routing]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-30-task-model-routing.md
[ab-requirements]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/omniroute-routing-20260928/ab-requirements.md#L5-L37
[unit-readback]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/omniroute-sol-max-20260930/checks/readback-after-switch.txt#L8-L37
[account-main]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-27-omniroute-account-pool.md#L512
[structured-smoke]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/e2e048053b151ac9c2ba269864cb4adf035058d3/evidence/artifacts/omniroute-features-20260927/records/cognee-structured-output-smoke.json#L49-L99
[scope-carrier]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-27-token-lanes-subagent-start.md#L341-L361
[qmd]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/e2e048053b151ac9c2ba269864cb4adf035058d3/evidence/artifacts/qmd-scope-embed-20260927/README.md
[amendment3]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/evidence/artifacts/token-adoption-e2e-20260926/README.md#L702-L784
[new-baseline]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-10-01-definitive-sota-wsl-program.md#L395-L408
[issue14866]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/e2e048053b151ac9c2ba269864cb4adf035058d3/evidence/artifacts/omniroute-features-20260927/upstream-issue-14866.json

Nothing in this status section is a new run.
The recorded execution results cover one host only; destination statements remain reported rather than independently observed here.
