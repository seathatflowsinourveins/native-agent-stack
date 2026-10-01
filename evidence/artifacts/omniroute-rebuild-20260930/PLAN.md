# Plan P: OmniRoute token-save enablement for GPT-6 on 20129 and 20128 (2026-09-29)

**Status: written, not applied.** Nothing in this plan has touched a gateway. The plan runs only after the coordinator switches both units: 20129 to variant A 24496b2ba and 20128 to variant B c19983a66. The compression tree is identical in A, B and the tip 0e2908097.

- **Executable plan:** `plan.json` (contract version 1, nine steps). `gateway_apply.py plan.json --check` returns 0 problems [executed].
- **Evidence tags:** [source-read] means read at c19983a66 (the checkout at `<scratch>/wt/B`). [executed] means run offline on B's own code with the network blocked. [observed-live] means read-only reads of the pre-switch gateways. [inferred] means a conclusion from those sources.

## 1. Outcome

### 20129 (framework and runtime-worker lane)

**Default lane: lossless only.** Requests with no header get:
- stacked `[ccr]`, which is byte-identical for every caller that does not advertise `omniroute_ccr_retrieve`;
- the `terse-prose:lite` output instruction.

**Lossy engines: per-request opt-in only.** Every lossy engine is switched on, but only for requests that ask for it:
- with `x-omniroute-compression: engine:rtk`, `engine:codex-responses` or `engine:caveman`;
- or with one of three new context combos:
  - `gpt6-agent-safe`: Responses agent lanes;
  - `gpt6-memory-safe`: prose and memory-extraction chat;
  - `gpt6-safe-lossy`: explicit loss tolerance.

**Global settings of each engine:** set to the safest values measured. This also makes the peers' `allow-lossy` and `fw-*` combos safer.

**Hop connection and confinement:**
- The sharedgw hop gets the prompt-cache declaration (K06), a 1200 s header timeout (GC12) and fixed hop headers (GC13).
- The sharedgw node gets search and fetch passthrough (GC5).
- `sharedgw/gpt-6-astra-max` gets a context_length override of 872000 (GC9).

### 20128 (CX lane)

- One confinement write: the Codex app-server transport flag goes off (GC8).
- Compression stays off, and `codex/*` stays excluded (section 5).

### Outside this plan

- **GC6/GC7** (blockedProviders) cannot be expressed in contract v1: no secret-free GET route exposes those keys. They are user decision 1, with exact bodies in section 9.

### Expected savings on the seeded corpus [executed]

These use S1's corpus and scorer; `P/matrix-screen3.json`, 444 runs, 0 errors, 0 network attempts, 36/36 planted-corruption controls caught.

| Traffic | Saving | Needles lost |
|---|---|---|
| No header | 0% | 0, except on the retrieval-tool caller (Bccr) |
| `gpt6-agent-safe` | 39.0–45.6% on the agent payloads | 2 needle ids: `e4-output`, the second copy of an identical run output whose first copy is kept; `f-frame`, a traceback frame in the dropped middle of a 43k-character log |
| `gpt6-memory-safe` | 0.03% on the memory payload | `doc-exact`, a signature's trailing space |

## 2. Decision rule applied

The owner's rule (2026-09-29) sets the bar:
- lossless features go ON;
- a lossy feature goes ON in the configuration the screen shows keeps every critical needle class and removes only bulk;
- otherwise it stays OFF for that traffic and goes ON in the smallest scope that can carry it.

**Critical needle classes:** exact numbers and identifiers, code and diffs, error/FATAL/exit-code lines, tool_call ids and pairing, JSON validity, system and developer instructions.

**The upstream lossy policy fixes the widest possible scope.** Lossy-catalog engines never run on a request without a header. The policy strips rtk, codex-responses, relevance, caveman, aggressive, llmlingua, ultra and omniglyph unless a qualifying header is sent (`open-sse/services/compression/lossyRequestPolicy.ts:31-71`; catalog flags `engineCatalog.ts:41-186`) [source-read, executed plan table `P/out-screen1/plans.json`]. So for those engines the per-request header is the widest scope available, not a narrowing chosen here.

## 3. Feature carriers (20129 compression)

| Feature | After the plan | Carrier / scope | Measured effect [executed, P screen] | Why this configuration |
|---|---|---|---|---|
| ccr | ON | engines map, so every request without a header | Byte-identical on A1, A2, B, C and D: the engine reports `compressed=false` and never mutates its input, and chatCore forwards a replacement body only when `compressed` is true (`chatCore.ts:1912-1913`). Only the response meta header and a no_savings analytics row change. A caller that advertises `omniroute_ccr_retrieve` (Bccr) gets its blocks of 600+ characters behind retrieval markers (8 needles, system and developer text) | Lossless for every current caller. Advertising the tool is the caller's own opt-in (`engines/ccr/index.ts:942-962`) |
| session-dedup | ON per request: `gpt6-agent-safe`, `gpt6-memory-safe`, `gpt6-safe-lossy`; peer `fw-session-dedup` and `default-caveman` now at 512 | Stacked step, `minBlockChars 512`, fuzzy off; global 512 | At 512: `e4-output` only (duplicate copy), prefix changes once (A1 item 25, 94.5% of prefix kept; B item 17, 93.9%). At 80 it also lost `doc-exact` and `x-user-part-b` (the key collision) | OFF with no header. The upstream key collision still reproduces (`engines/session-dedup/index.ts:317-325, 355-366`; Xcollide). The engines map cannot be limited to Responses or system-first chat, which are immune |
| lite whitespace folding | ON per request: `gpt6-memory-safe` only | Stacked step (lite steps take no config, so global `lite.compressToolResults=false` is a precondition) | On code payloads: `g-diff-exact`, `c-settle-block`, `c-quantize-trailing`; on chat also `agents-exact` and `agents-lint-hardbreak`. On prose (C): `doc-exact` whitespace only | Breaks diffs and exact-match edits, so it is kept off coding traffic (`lite.ts:50-81`) |
| lite tool-result truncation | OFF | none | S1: 80 needles, JSON cut mid-document, latest A2 output cut | Keeps only the head (`lite.ts:148-175`). The current-turn guard misses Responses tool loops (`bodyAdapter.ts:28-34, 116-152`) |
| rtk | ON per request: `engine:rtk`, `gpt6-agent-safe`, `gpt6-safe-lossy`; peer `fw-rtk` now the same | Global and step config: all 55 built-in filters disabled, caps 400 lines (x1.5 at minimal) / 40000 characters, collapse runs of 5+ identical lines, no custom filters, raw retention never | 38.9–42.8% saved on A1, A2, B and Bccr; only `f-frame` lost. Exit lines, FATAL/ERROR/Traceback, diffs and JSON are kept | Filter packs drop exit-code lines and diff headers (S1: 34 needles; with `test-pytest` and `git-diff` off, still 6: the Codex `Exit code:` header and log tail). Head 24 + tail 24 + severity lines is the owner's "bounded head and tail" (`engines/rtk/index.ts:228-403`; `smartTruncate.ts:8-80`) |
| codex-responses | ON per request: `engine:codex-responses`, `gpt6-safe-lossy`; peer `fw-codex-responses` now the same | Global: floor 4096 bytes, search/log compaction off, shell and editor tools preserved | 0 changes on the corpus | Can still round numbers in JSON of 4 KB or more from unpreserved tools (S1: 1234567890123456711 became ...800), so it stays opt-in (`engines/codexResponses/index.ts:147-228`) |
| headroom | ON per request: `fw-headroom`, `gpt6-safe-lossy` | Global and step `minRows 16` | 0 changes (the 12-row array stays JSON) | Catalog-lossless but rounds ints above 2^53 and decimals on arrays of 16+ rows (`smartcrusher.ts`). Kept out of the map, because a lossless-catalog engine runs with no header |
| relevance | ON per request: `gpt6-safe-lossy` (budget 0.9, threshold 0) | Stacked step only | 0 losses on the corpus | Single-mode relevance is an upstream no-op (no `SINGLE_MODE_OF` entry, `deriveDefaultPlan.ts:5-13`). S1 at 0.5 dropped instruction sentences |
| caveman | ON per request: `engine:caveman` (runs `standard`), `gpt6-safe-lossy` | Global: lite, assistant role only, 200-character floor, default six preserve patterns | 0 changes on the corpus | S1 on the user role turned "I'm not sure" into "I'm not". Global roles override step roles (`engines/cavemanAdapter.ts:330-356`) |
| aggressive, ultra | ON per request inside stacked combos only (`gpt6-safe-lossy`, `allow-lossy`) | Step config; globals near-inert (thresholds 100; keep 0.9, 8192-token floor) | 0 changes on the corpus | Left off in the map because K06 turns the single-mode header path into `standard`/caveman (`cachingAware.ts:112-126`; `strategySelector.ts:252-257`) |
| llmlingua | ON per request: `gpt6-safe-lossy` (floor 100k tokens, keep 0.9) | Stacked step only | Not triggered at corpus sizes | `engine:llmlingua` would run the 0.5 default (`engines/llmlingua/index.ts:468-505`) |
| omniglyph | OFF | none | S1: skipped for every GPT-6 route | Cannot act on GPT-6 (`imageTransportPolicy.ts:17-33`) |
| output styles | ON: `terse-prose:lite` | Every request that does not send `off` (`chatCore.ts:1692`) | Not payload-testable (it changes the reply); deferred canary | Least steering style. Code, errors, URLs and identifiers are kept exact; security and irreversible-action text stays normal (`outputMode.ts:28-36`) |
| legacy cavemanOutputMode | superseded | `outputStyles` takes precedence (`outputStyles/backCompat.ts:20-28`) | same text | No separate switch needed |
| languageConfig | ON, fixed `en`, no auto-detect | global | byte-stable instruction text | Behaviour identical to today's English default, and stays byte-stable |
| liveZone | ON (`cacheMinutes` 60 unchanged) | API-key callers only (`liveZone.ts:127-133`) | 1 of 79 20129 rows is keyed [observed-live], so mostly inert | Freezes compressed items for keyed opt-in lanes |
| contextBudget | OFF | none | S1 p16, p17, p19, p20: escalation overrides `off` | Upstream defect (`adaptiveCompression/resolveAdaptivePlan.ts:36-104`) |
| auto-trigger | OFF (`autoTriggerTokens` 0) | none | — | Every selectable mode is lossy on code (lite folds diffs; others lossy), and it would change requests with no header |
| reactive compaction | already ON | master switch (`chatCore.ts:1445-1448`) | S1 forced threshold: tool outputs cut to 2000 characters | T01 moves its threshold for `sharedgw/gpt-6-astra-max` from about 280k to about 610k message tokens [inferred from `chatCore.ts:2114-2122`] |
| K06 cache declaration | ON (T07) | sharedgw connection | no body change in the screen | Latent guard. It rewrites only single-mode aggressive/ultra, which are unreachable here |
| fidelity/risk gate, QuantumLock, breaker, memo, prefix freeze | OFF | none | — | No settings key at this build (strict schema `compressionConfigSchemas.ts:366-405`); the env-only ones need a restart |

### Where this departs from R1

- **Default lane.** R1's default lane was `[session-dedup, ccr, lite]`. The screen shows lite breaks diffs and developer text, and session-dedup carries the upstream collision, so both moved to opt-in combos.
- **rtk filters.** All filters are off, where R1 kept them. The R1-like variant `rtkB` still lost exit headers, the log tail and code-block whitespace.
- **aggressive and ultra.** Off in the map because of K06.
- **`gpt6-safe-lossy`.** It has no lite step (lite only harms code), and it has a new rtk configuration.
- **codex-responses.** Added `terminal`, `execute_bash`, `bash` and `shell` to `preserveToolNames`.
- **Two scoped combos added:** `gpt6-agent-safe` and `gpt6-memory-safe`.
- **Context-length overrides.** Only `sharedgw/gpt-6-astra-max` gets one. It is the only id seen in 20129 `call_logs.requested_model` (79 rows, 2026-09-27T18:53Z to 2026-09-29T22:42Z) that has no override [observed-live]. R1 listed 9 candidates.

## 4. The writes (execute with `gateway_apply.py`; exact bodies in `plan.json`)

**Stop rule:** the first failed precondition stops with no write. The first non-2xx write or failed read-back stops the run, rolls back that step and runs its `rollback_verify`. Earlier steps stay applied; `--rollback <ids>` undoes them in reverse order.

| Id | Gw | Write | Features | Capture | Read-back | Rollback (verify) | Other clients | Risk |
|---|---|---|---|---|---|---|---|---|
| T01 | 20129 | `PATCH /api/model-capability-overrides` `{target: sharedgw/gpt-6-astra-max, key: context_length, value: 872000}` | GC9, C-CTX | GET overrides, keep `overrides`. Pre: exactly 3, all `sharedgw/cx/gpt-6-*` | 4 entries; index 0 is the new target at 872000 (newest `refreshedAt` first, `route.ts:57-92`) | `DELETE ?target=sharedgw/gpt-6-astra-max&key=context_length`, which removes only that row (`modelContextOverrides.ts:125-134`). Verify: exactly 3 rows, all `sharedgw/cx/gpt-6-*` | Requests for that id: compaction and the context check at 872000 | low |
| T02 | 20129 | `POST /api/context/combos` `gpt6-agent-safe` `[session-dedup 512, ccr, rtk all-filters-off]` | dedup, ccr, rtk per request | GET list, keep `combos`. Pre: id 404 | Combo equals the body (id, name, not default, pipeline) | `DELETE /api/context/combos/gpt6-agent-safe`, this combo only. Verify: 404 and list equals the capture | None until a client sends the header | low |
| T03 | 20129 | `POST` `gpt6-memory-safe` `[session-dedup 512, ccr, lite]` | dedup, ccr, lite per request | as T02 | as T02 | as T02 | as T02 | low |
| T04 | 20129 | `POST` `gpt6-safe-lossy` (10 steps, safest step configs) | every lossy engine per request | as T02 | as T02 | as T02 | as T02 | low |
| T05 | 20128 | `PUT /api/settings/feature-flags` `{key: OMNIROUTE_CODEX_APP_SERVER_ENABLED, value: "false"}` | GC8 | GET flags, keep `flags.46` (index at c19983a66 [executed]). Pre: key guard, `default`/`"true"`, `requiresRestart` false | `"false"`/`db` | `PUT {key}` with no value, which removes only this override (`feature-flags/route.ts:156-157`; `featureFlags.ts:115-121`). Never `DELETE`, which clears every override. Verify: value and source equal the capture | None: 0 of 6 codex connections set `codexTransport` [observed-live] | low |
| T06 | 20129 | `PUT /api/providers/<sharedgw node>/interception-rules` `{interceptSearch: false, interceptFetch: false}` | GC5 | GET rules, keep search/fetch/backend only, never `fetchProxyUrl`. Sqlite row count kept as a record. Pre: body is `{}` (checked by length, so no value is ever printed) | both false, exactly 2 keys | `DELETE` same route, this provider only (`interceptionRules.ts:169-178`). Verify: `{}` | sharedgw requests that carry built-in web tools in a non-passthrough shape (none observed) | low |
| T07 | 20129 | `PATCH /api/providers/<conn 3eea0518…>` `{providerSpecificData: {timeoutMs: 1200000, cache: {supportsPromptCaching: true}}}` | K06, GC12/O03 | GET conn, keep id, provider, the four existing psd keys, timeoutMs, cache. Pre: timeoutMs and cache absent (a JSON null fails the absent check, so null is never mistaken for absent) | 1200000, `{supportsPromptCaching: true}`, other psd keys equal the capture | `PATCH {timeoutMs: null, cache: {}}`. The validator skips null and the normalizer deletes both keys [executed `P/psd-roundtrip.json`]. Verify: both absent, others equal | Every sharedgw request: header wait up to 1200 s (calls under 600 s unchanged, unless the environment sets a larger budget, gate G5) | medium |
| T08 | 20129 | `PATCH` same connection `{providerSpecificData: {customHeaders: {x-omniroute-no-memory: "true", x-omniroute-disabled-guardrails: "vision-bridge,audio-bridge,video-bridge", x-omniroute-no-cache: "true"}}}` | GC13 | GET conn, keep id, provider and the four psd keys; never header values. Pre: customHeaders absent | 3 headers with exact values, others equal | `PATCH {customHeaders: null}`, deleted by the normalizer. Verify: absent | Every hop request to 20128: no memory, no bridges, no exact-cache reads or writes at 20128. The 20129 entry cache is unchanged | medium |
| T09 | 20129 | `PUT /api/settings/compression` with 11 keys: `engines`, `outputStyles`, `liveZone`, `languageConfig`, `rtkConfig`, `codexResponsesConfig`, `cavemanConfig`, `sessionDedup`, `headroom`, `aggressive`, `ultra` | ccr default lane, output style, `engine:*` opt-ins, safest globals | GET compression, keep the 11 keys plus the invariants. Pre: invariants (master on, `defaultMode` off, auto-trigger 0, `contextBudget` off, no active or combo id, no exclusions, lite truncation off with no cap, non-builtin `stackedPipeline`, preserve-system always, legacy style off, heuristic ultra) and the all-off engines map | Every key equals the body; invariants unchanged | `PUT body_from_capture` of the 11 keys. The rollback body passes the strict schema and restores GET exactly [executed `P/db-roundtrip.json`]. Verify: the 11 keys equal the capture | See section 7 (pi must send `off`, OpenHands arms change) | medium |

**Order and gates.**
- **Order:** T01–T06 are additive or inert; T07 and T08 change the hop; T09 changes the default lane. T07 (K06) must land before T09 (R2).
- **Grouping:** K06 and GC12 share one PATCH, as R2 recommended. GC13 is separate so it can be held.
- **Pre-apply gates** (in `plan.json` `post_apply.pre_apply_gates`):
  - G1: the switch is done and the database copies are taken.
  - G2: a fresh `TOKENSAVE_STATE_DIR`.
  - G3: announcements; hold T09 until the pi peer acknowledges.
  - G4: a value-free check that `CLOUD_URL` is unset for `omniroute-fw.service`, because each provider PATCH calls `syncToCloudIfEnabled`. The installed build compiled `NEXT_PUBLIC_CLOUD_URL` to `""` [executed grep].
  - G5: optional timeout comparison.
  - G6: the Gate A settle window.

**The context-window reconciler and T01** [source-read, observed-live]. OmniRoute runs a context-window reconciler at startup, every 24 h and after model syncs (`src/lib/contextWindowResolver.ts:30-110`; `src/instrumentation-node.ts:724`). It writes and removes `auto:discovery` override rows but never touches `manual` ones. On 20128 it wrote six rows on 2026-09-29 (19:27:48, then 22:59:03), including `codex/gpt-6.1-sol` at 872000. On 20129 only the three manual rows exist today.
- If the post-switch start adds auto rows for sharedgw models, T01's precondition stops the step before any write. In that case, rebuild T01 against the observed list (`P/build_plan.py`).
- T01's own row is `manual`, so the reconciler cannot overwrite it.

**Mock rehearsal [executed, simulation]** (`P/mock_rehearsal.py`, `P/mock-rehearsal.json`). `gateway_apply.py`'s own `Run` class was driven against an in-memory server built from the handlers as read:
- all 9 steps applied;
- all 9 rolled back in reverse order with a verified restore;
- the final state equals the initial state;
- three negative controls behaved correctly: a dropped field on T09 triggered rollback and restore; a dropped cache on T07 did the same; override drift on T01 stopped the run before the write.

## 5. 20128 (CX lane)

Only T05 (GC8) is written.

**Compression stays off (master switch and `codex/*` exclusion).** The owner's condition for changing them is not met:
- R1's source reading does show that the adapter keeps Codex Responses items intact: S1's adapter identity is exact, and no engine touched reasoning items, `encrypted_content` or `previous_response_id`. It also shows that compaction skips native Codex passthrough (`chatCore.ts:2137-2141`).
- But with `codex/*` removed and the master on, three problems follow:
  - sharedgw traffic would be compressed a second time at the hop. The route review flagged this as PATH-4.
  - The only plan 20128 could run with no header is the fallback `default-caveman` (`enginesExplicit` false, builtin `stackedPipeline`, `chatCore.ts:1654-1687`). That is session-dedup plus lite, which loses code and diff needles.
  - Per-lane opt-in is impossible while `codex/*` precedes header parsing (`chatCore.ts:1438-1441`), and a routing-combo carrier is ruled out while the affinity patch is live (F1).
- The only style the lane could gain overlaps what Codex CLI already sends: GPT-6 verbosity low (R2 L02c).

**Codex fast service tier:** untouched. `codexServiceTier` is absent on both stores [observed-live], and no step writes it.

## 6. What `x-omniroute-compression: off` does at c19983a66

- **What it stops:**
  - the plan becomes `off` before any engine runs (`planResolution.ts:41`);
  - output styles are skipped (`chatCore.ts:1692`);
  - liveZone does not run.
- **What it does not stop:** reactive, proactive and last-resort compaction. These stay armed whenever the master switch is on and the model is not excluded (`chatCore.ts:1445-1448`; the only skip is native Codex passthrough, `:2137-2141`).
- **`contextBudget` escalation** would override `off` (upstream defect). That is why `contextBudget` stays off; it cannot fire under this plan.
- **Result:** after the plan, a request that sends `off` is exactly as uncompressed as a request with no header is today. Compaction is armed in both cases.

## 7. Peer notices (the coordinator sends these before T09; full text in `plan.json` `post_apply.peer_notices`)

- **pi (native-agent-stack-5f).** The baseline arm must send `x-omniroute-compression: off` on every request from T09 on. Send the peer the post-apply `/api/settings/compression` state (the C2 output).
- **OpenHands arms.**
  - Every request that does not send `off` gets the `terse-prose:lite` instruction, including combo-header requests.
  - A Responses body with `input` but no `instructions` (for example, SDK condenser calls) now gets the style text as its entire instructions (`outputStyles/apply.ts:171-190`). The Codex placeholder instructions therefore no longer apply to those calls.
  - The global changes alter `allow-lossy` and `fw-*`: `allow-lossy` drops from 243 to 225 needles lost; `fw-rtk` drops to `f-frame` only; `fw-codex-responses` and `fw-headroom` make no change on the corpus [executed].
  - `allow-lossy`'s relevance and llmlingua steps keep their 0.5 defaults, because those step configs live in the peer-owned rows.
- **hindsight, cognee and research frameworks.** Requests with no header get the style instruction in the system message; the chat path keeps its auto-clarity bypass. They may opt into `gpt6-memory-safe`.
- **All A/B arms.** Unchanged, but restated: numeric `temperature: 0` bodies engage the exact cache and in-flight dedup (R2 K02/K04), so omit `temperature` or send `x-omniroute-no-cache: true`.

## 8. Post-apply checks (no model call)

- **C1** `gateway_apply.py plan.json --verify` re-runs every read-back.
- **C2** `post_apply_checks.py --phase post` runs 36 value-free checks: GET named fields plus sqlite named paths, with header values and proxy URLs compared in code. The pre-phase run against the pre-switch builds passed 36/36 at 2026-09-29T23:24Z [observed-live].
- **C3** `S1-screen/scripts/verify_effective_plan.py <dir>` must reproduce the plan table in section 1: with no header, `default`, `safe` or an unknown value, the result is `[ccr]`; `off` gives off; the `engine:*` headers and the combos give their pipelines.
- **C4** Gate A report: what to send and how to read it.
  - **The digest files.** The split apply (T01–T08, then T09) overwrites the fixed digest file names, so copy `digests-before.json` and `digests-after.json` to `-run1` names between the runs (the command is in `plan.json`). Send `digests-before-run1.json`, the final `digests-after.json` for the four routes on both gateways, the C2 output and the step timestamps. `/api/resilience` returns configuration only (`route.ts:129-161`).
  - **Drift without a write.** `/api/model-capability-overrides` can change with no gateway write, through the reconciler's `auto:discovery` rows. Gate A should compare the manual rows (sqlite `WHERE source = 'manual'`) rather than the raw digest.
  - **Coverage.** The digests do not cover the connection, the interception rule or the 20128 flag; C2 covers them.
- **Deferred live canary:** at most 12 requests, not before 2026-10-04T00:35Z. Commands are in `plan.json` `post_apply.deferred_live_canary`:
  - 6 cases with no header, on `/v1/responses`;
  - 3 cases (tail, exit code, 64-bit id) with `gpt6-agent-safe`;
  - 3 cases (decimals, strict schema, instruction) with `gpt6-memory-safe` on chat;
  - plus a sqlite read of 20128 `reasoning_effort_upstream` = max for the canary's correlation ids.

## 9. Not in `plan.json`: GC6/GC7 (blockedProviders, noAuthFallbackDisabledProviders)

**Why they are not in the plan.** The contract's read-back is GET-only, and at c19983a66 only `GET /api/settings` returns these keys. That route returns decrypted secrets and is forbidden here. `/api/providers/{id}/models` fetches upstream when the provider is not blocked, so it cannot serve either [source-read: `src/app/api/v1/models/catalog.ts:344`, `src/app/api/providers/[id]/models/modelRouteProjection.ts:77-80`].

**Current state:** both keys are absent on both stores [observed-live 2026-09-29T23:24Z].

**Body (20128 and 20129, each with its own revision):**
```
PATCH /api/settings
{"expectedRevision": <sqlite settings/_settingsRevision>,
 "blockedProviders": ["devin-cli-agentic","opencode","duckduckgo-web","cloudflare-playground","veoaifree-web","auggie","zcode","codex-app-server","uncloseai","aihorde"],
 "noAuthFallbackDisabledProviders": ["kilocode","opencode-zen","opencode-go","pollinations"]}
```

**Procedure:**
- **Precondition:** both keys absent. PATCH replaces the arrays (`src/lib/db/settings.ts:316-345` stores each key with INSERT OR REPLACE), so if either key is present, write the union instead.
- **Read-back:** sqlite named keys.
- **Response handling:** parse the response in code and print only the status and revision; it carries decrypted settings (`src/app/api/settings/route.ts:569-580`).
- **Rollback:** write `[]`, which behaves the same as absent (`noAuthProviders.ts:8-31`). The exact "absent" state can only be restored from the stop-time database copy.

## 10. User decisions that remain

1. **GC6/GC7 route.** Choose one:
   - (a) extend the apply contract with a sqlite_ro read-back assertion type; or
   - (b) apply them through the route-convergence tooling, with a union-or-absent precondition and a sqlite named-key read-back.

   Without them the merged OpenHands G5 checks (C1, C3) keep failing, so the runtime workers cannot proceed.
2. **Settle without the canary?** Settle the whole change without the live canary, or hold T09. GPT-6 capacity returns 2026-10-04T00:35Z, after the Gate A settle point, and no write is allowed inside the Gate A window. T09 is the only step with an unmeasured effect that a model would show: the `terse-prose:lite` instruction on every request that does not send `off`. T01–T08 carry no model-visible default-lane change.

## 11. Residual risks

- **Output style.** The effect of `terse-prose:lite` is unmeasured. Its "drop hedging" wording may flatten stated uncertainty in judgment prose. There is no style-only opt-out per request: header-selected combos do not apply `outputMode`, and routing combos are ruled out (F1/G5).
- **rtk truncation.** rtk in the opt-in lanes drops traceback frames and other lines from the middle of outputs above 600 lines or 40000 characters. Head 24, tail 24 and every severity line are kept.
- **session-dedup collision.** The upstream collision still exists in the combos for multipart-first chat, although 512-character blocks make it rarer. `gpt6-memory-safe` is advised only for system-first or string-content chat.
- **Number rounding.** codex-responses (JSON of 4 KB or more) and headroom (16+ rows) round large numbers when an opt-in request triggers them. `allow-lossy` stays highly lossy (225 needles) because its relevance and llmlingua step defaults live in peer-owned rows.
- **Rollback leaves rows behind.** T09's rollback writes back the prior values of keys that had no row before (`rtkConfig`, `codexResponsesConfig`, `aggressive`, `ultra`, `headroom`, `sessionDedup`, `languageConfig`). GET is identical afterwards; exact row absence can only come back from the stop-time database copy. GC6/GC7 would have the same property.
- **T01 rollback_verify.** It compares the full override list, including `refreshedAt`. A concurrent refresh of another override would show NOT-VERIFIED even after a correct restore.
- **Evidence class.** The evidence is a synthetic seeded corpus through the pinned engines, a mock server rehearsal, scratch-database round trips and source reading. No live request was made. The apply's own read-back is the first live evidence.
- **Housekeeping (my own run).** My first screen run wrote its output directory into the B checkout, because of a relative path. I moved it out; B's status is clean apart from the coordinator's pre-existing `bin/cli` outputs.

## 12. Files (all under `<scratch>/tokensave`)

- **Plan:** `plan.json`, `PLAN.md`.
- **Post-apply checks:** `post_apply_checks.py`.
- **Evidence:**
  - screen: `P/matrix-screen3.json`, `P/screen3-summary.json`, `P/out-screen3/`, `P/out-screen1/plans.json`;
  - scratch-database round trips: `P/db-roundtrip.json`, `P/combos-roundtrip.json`, `P/psd-roundtrip.json`;
  - mock rehearsal: `P/mock-rehearsal.json`.
- **Builders and harness:** `P/build_candidate.py`, `P/build_plan.py`, `P/candidate/`, `P/harness/`.
