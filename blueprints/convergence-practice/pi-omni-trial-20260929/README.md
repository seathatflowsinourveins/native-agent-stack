# pi behind OmniRoute with the token-save practice: trial record, 2026-09-29 and 2026-09-30

**Status: observed, decision `trial`.** pi v0.99.1 ran 28 real tasks through the OmniRoute framework lane (20129, chained to 20128;
model `sharedgw/gpt-6.1-sol` at thinking `xhigh`) on the gateway owner's corrected token-save configuration: S1 wiring smoke (3 runs),
S2 (24 runs: 3 tasks x 4 arms x 2 attempts) and R1 (one run killed at its second model response and resumed). All 28 passed their
fixture checks. On these small fixtures the token-save stack used more tokens than plain pi, not fewer, and the gateway lane removed
192 of 413,153 input tokens on the stack arm; its effect on uncached input is not resolved.
[`experiment.json`](experiment.json) is the record, [`evidence/`](evidence/) holds the sanitized per-run files, and the kit in
[`kit/`](kit/) rebuilds the environment from pinned upstream sources and re-runs every offline check.

## Why this exists

- On 2026-09-26 the landscape sweep recorded `earendil-works/pi` as `not_adopted` for the native-clients layer (no demonstrated
  gap; its GPT-6 fit vote never returned; `catalogs/sota-convergence/manifest-20260926.json`). Its overturn condition allowed
  reopening if the requirement admits API-key or multi-provider billing.
- On 2026-09-29 the user allowed a trial of pi through OmniRoute with the ecosystem's token-save practice enabled, and ordered
  that OmniRoute run the latest models and the full token-save practice **before** the pi practice. That is the billing branch,
  for GPT-6 through the local gateway only. pi's Anthropic OAuth path is out of scope: at the pinned source it presents
  itself as Claude Code (`packages/ai/src/api/anthropic-messages.ts`), and
  <https://code.claude.com/docs/en/legal-and-compliance> (fetched 2026-09-29) names the unmodified Claude Code binary and the
  customer's own API keys as the sanctioned routes.

## What moved on 2026-09-29 and 2026-09-30

- **pi:** v0.99.1 (2026-09-29) ships built-in MCP, `codemode` and `tool_search` (no extension needed) and adds `gpt-6.1-sol`. The trial builds the tag.
- **gpt-6.1-sol via OmniRoute:** alive since 2026-09-29T22:59Z. OmniRoute builds the codex catalog with `client_version=<CODEX_CLIENT_VERSION>` and the 20128
  unit announced 0.157.1 while 6.1 Sol needs 0.159.x; an interim drop-in set 0.159.1, and the gateway owner's switch absorbed it into both unit files.
  Callers that report a Codex version keep it on inference, so the host's Codex 0.157.1 CLI is refused for 6.1 Sol even through the gateway
  (HTTP 400 "not supported when using Codex with a ChatGPT account"); pi reports no Codex version and is unaffected.
- **Gateways rebuilt (2026-09-30T00:06Z):** the gateway owner moved both to upstream `release/v3.8.51` `2f42a9ac1` (20128 build `ae5539a56` with a local affinity
  patch, 20129 build `87c4c488d`, both plus #13788) and applied a nine-step token-save plan. Upstream main `c1e30b76` has the same tree as `2f42a9ac1`
  (`0f58d8df20c0c2ae4336b432b3f39837119b6eed`, read with `gh api repos/diegosouzapw/OmniRoute/commits/<sha> --jq .commit.tree.sha`).
- **Scope corrected (2026-09-30T00:43:52Z):** the first apply left the headerless lane at stacked `[ccr]` (a no-op unless a request carries the retrieve tool)
  plus an output style; a tiny chain request cost 97 input tokens then and 23 after the correction (`evidence/gateway-readback-20260930T0009Z-first-apply.json`,
  `evidence/gateway-readback-20260930T0159Z.json`). The user asked for upstream as the source of truth. Upstream's shipped default is compression off with no engine on
  (`open-sse/services/compression/types.ts:421-443`); its documented headerless lane is `[session-dedup, lite]` (`docs/compression/COMPRESSION_GUIDE.md:233-239`); lossy
  engines (rtk, codex-responses, caveman, aggressive, ultra, relevance, llmlingua, omniglyph) run only when the request header opts in with `allow-lossy`, `engine:<id>`
  or a stored combo named in the header (`lossyRequestPolicy.ts:29-47`), which is upstream's own rule. The delta the owner applied: engines on session-dedup, ccr, lite,
  rtk (minimal), codex-responses, relevance, caveman (lite), aggressive, llmlingua, ultra; off headroom (it re-encodes large numbers) and omniglyph (acts only on direct
  Anthropic transport); output styles none; liveZone off; upstream's values elsewhere, with two defect mitigations kept (`sessionDedup.minBlockChars` 512 instead of 80,
  `lite.compressToolResults` false instead of true). The headerless plan is `[session-dedup, ccr, lite]`: upstream's documented lane plus `ccr`, not upstream's shipped default.
  20128 stays compression-off with `codex/*` excluded, which is upstream's default. Every run below ran on this state.

## Sources and pins

| Component | Pin | Used for |
| --- | --- | --- |
| earendil-works/pi | tag `v0.99.1` = `d86654abb8862e201933517d6f1fce9f88dd117f` | the harness under trial; `npm ci --ignore-scripts && npm run build` |
| rtk-ai/rtk | 0.50.0 (installed) | `rtk init -g --agent pi` installs pi's RTK extension; `rtk init -g --no-patch` regenerates the awareness text |
| context-mode | 1.0.169 (installed) | tools through MCP (`stack`) or through its pi extension (`stack-ext`) |
| OmniRoute | upstream `2f42a9ac19d1a247ec9ce5473b790843724b3061` (20128 build `ae5539a56`, 20129 build `87c4c488d`) | model `sharedgw/gpt-6.1-sol` at effort `xhigh` |
| MCP set | context-mode (MCP arms), serena, jcodemunch (route/menu/order), qmd, headroom, all but context-mode deferred behind `tool_search` | the OpenHands runtime worker's policy (`config/mcp-policy.json`) plus headroom as the Codex worker profile enables it |
| Instruction file | top rule (`codex.AGENTS.template.md` lines 3-8), rtk awareness, the general token-lanes block minus the bullets for absent tools | one non-canonical sentence (pi loads deferred tools with `tool_search`); the MCP arms name the tools `mcp__context-mode__ctx_*` |

## Four arms

| | `plain` | `stack` | `stack-gwoff` | `stack-ext` |
| --- | --- | --- | --- | --- |
| context-mode | none | MCP server, tools declared directly, no hooks | same as `stack` | its pi extension (upstream README's recommended install) |
| RTK on bash | raw | extension, with the recipe's five `exclude_commands` | same | same |
| serena, jcodemunch, qmd, headroom | none | deferred behind `tool_search` | same | same |
| instructions | none | generated `AGENTS.md` | same | same (short tool names) |
| `x-omniroute-compression` | `off` | none (the gateway's headerless lane) | `off` | none |
| all arms | `X-OmniRoute-Session-Id` and `X-Correlation-Id` = run id; `x-omniroute-no-cache: true` (identical first turns would otherwise be replayed); model `sharedgw/gpt-6.1-sol`, thinking `xhigh`; `cacheWarming` streaming, cache-miss notices on; no telemetry | | | |

`stack-gwoff` separates the gateway lane from the client stack: it is the `stack` arm of a second state directory staged with `--stack-compression off`.
`stack-ext` is kept because context-mode's pi extension appends a transient user message to each prompt's first request.

## Prompt cache: design and measurements

- **Client (pi, `openai-responses.ts:327-337`):** sends `prompt_cache_key` = session id, `session_id` and `x-client-request-id` headers, `store: false`; sends
  `prompt_cache_retention`/`prompt_cache_options` only when the model opts in, which the ChatGPT-backed route rejects, so both stay off.
- **Gateway (OmniRoute `codex.ts:1195-1215,1504-1512`, `stripPassthroughRejectedParams.ts`):** uses `prompt_cache_key` as the Codex session id and strips `prompt_cache_retention`.
- **Provider (OpenAI guide, GPT-5.6+):** the implicit breakpoint sits at the end of the latest eligible message.
- **Archived synthetic reading** (`evidence/gateway-readback-20260930T0009Z-first-apply.json`, append-only conversation, 6k-token first message): on 20129 turns 2 to 4 read
  5,888, 5,888 and 6,016 of 6,123, 6,147 and 6,171 input tokens from cache (share 0.965); on 20128 turn 2 read 0 and turns 3 and 4 read 5,888 (share 0.647). Earlier figures of
  2026-09-29 (about 97% for the same shape, 0% for static plus changing text in one message, 0% at request 2 after a transient trailing message) came from ad-hoc scripts and are not archived.
- **Real pi runs:** request 1 of the stack-family runs already read cached tokens (6,016 for `stack` and `stack-gwoff`, 5,632 for `stack-ext`; `plain` read 1,024 from its
  third run on): the provider cache is warm across neighbouring runs although each run has its own `prompt_cache_key`, so cache shares across arms are confounded by run order.
  The second request of `stack-ext` read cached tokens in 6 of its 7 runs (S1 and S2), `stack` in 6 of 7 and `stack-gwoff` in 5 of 6; one run of each read 0 (cause not established). The synthetic
  transient-message miss was therefore not consistently reproduced. S2-only mean shares at request 2 were 0.71 (`stack-ext`), 0.69 (`stack`) and 0.61 (`stack-gwoff`).
  Over S2 each arm read 0.72 to 0.82 of its input from cache, and the share rises with the request index (`plain`: 0.57 at request 1 and 0.84 at request 5, which four of its six runs reached).

## What the offline checks established (scripted stub, no gateway, no quota)

`kit/probes.py` on pi v0.99.1, three arms, rerun 2026-09-30 after restaging for the new lane: 96 PASS lines, 4 KNOWN-FAIL lines and no FAIL line; it ends `ok (0 failed checks of 98)`
(the runner's own tally; some PASS lines come from the staging self-check it calls). `stage.py --check` passes.

- The request pi sends: `POST /v1/responses`, model `sharedgw/gpt-6.1-sol`, effort `xhigh`, run-id headers, `x-omniroute-no-cache`, the arm's compression header (none for the stack arms), a stable `prompt_cache_key`.
- Across a scripted tool loop the declared tools, instructions, cache key and session id stay identical; the input only grows for `stack` and `plain`.
- The `stack-ext` arm sends the transient trailing message (probe line KNOWN-FAIL, `src/adapters/pi/extension.ts:740-753` of context-mode 1.0.169); `tool_search` grows the declared tools (15 to 18) once per load in both stack arms.
- SIGKILL during the first turn (K1) and the second (K2): the session file keeps the prompt and any saved tool result, `pi --continue` resumes with them, and no descendant process survives 3 s.
- The probes can fail: three mutants each fail exactly their rule; `run_task.py` passes a scripted solver and fails a no-op; the fixtures have known-pass, known-fail, tamper and malformed controls (16 of 16).

## Results (real gateway, 2026-09-30)

Entry-gateway tokens (20129 call-log rows per run id; `tokens.in` includes cached tokens: pi's input plus cacheRead equals the gateway's `in` for all 27 S1 and S2 runs), summed
over the six S2 runs of each arm:

| Arm | Passed | Requests | Uncached input | Cache read | Cache share | Output | Compressed | Mean wall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `plain` | 6/6 | 27 | 14,842 | 37,248 | 0.715 | 3,388 | 0 | 29.2 s |
| `stack-gwoff` | 6/6 | 41 | 87,840 | 323,584 | 0.786 | 5,597 | 0 | 52.1 s |
| `stack` | 6/6 | 42 | 72,929 | 340,224 | 0.823 | 6,467 | 192 | 57.6 s |
| `stack-ext` | 6/6 | 45 | 108,018 | 492,544 | 0.820 | 9,102 | 200 | 72.8 s |

- **Quality:** 6 of 6 in every S2 arm, 3 of 3 S1 runs and the R1 run passed their fixture checks. There is no quality difference to report at n=2 per cell.
- **Cost:** on these small fixtures plain pi is the cheapest arm by a wide margin: `stack` used 4.9 times the uncached input, 1.9 times the output and 2.0 times the wall time of `plain`. No savings were measured, so none is claimed.
  A plausible cause is the stack's fixed prefix (instructions and about 15 tool schemas), which these runs do not isolate. `stack-ext` used 45% more input (48% more uncached) and 41% more output than `stack` for the same pass rate.
- **Gateway lane:** it removed 192 of 413,153 input tokens on `stack` and 200 on `stack-ext` (session-dedup needs repeated blocks of 512+ characters in history). Its effect on uncached input is unresolved:
  paired `stack` minus `stack-gwoff` differences per task and attempt run from -11,751 to +6,871 tokens (four of six negative), and the two arms share a warmed cache. The measurement covers the
  20129 to 20128 hop for pi, not 20128's native Codex CLI traffic.
- **Layer use:** across six runs per arm the model called context-mode tools 2 to 3 times in the MCP arms and 10 times in `stack-ext`, loaded a deferred MCP tool through `tool_search` 7 to 8 times, and RTK's
  tracker counted 18 to 25 commands against 10 to 11 bash calls; most work used pi's built-in read, bash and edit.
- **R1:** the `stack` arm was killed with SIGKILL after its second model response (9 descendants, none alive 3 s later; the session file kept the prompt and both tool results) and resumed with
  `pi --continue`; the resumed run finished and passed. The first resumed request read 6,016 tokens from cache, the size of the static prefix every stack run reads at request 1, so it does not show reuse of the
  resumed history. The killed in-flight request is a status 499 row at the gateway.
- **Pool:** the account behind these runs showed 1% of its weekly window used at 01:39Z after all of the above, seven finished parallel vote jobs and three more in flight (`evidence/pool-readings-20260930.json`).

## Stages and gates

| Stage | What | State |
| --- | --- | --- |
| S0 | stage the arms, offline probes, fixtures | done (96 PASS, 4 KNOWN-FAIL, 0 FAIL) |
| G | OmniRoute with 6.1 Sol and the token-save settings | done: 6.1 Sol 2026-09-29, corrective delta 2026-09-30T00:43:52Z, read back by `omni_verify.py` at 01:59Z (`evidence/gateway-readback-20260930T0159Z.json`: enabled, defaultMode, enginesExplicit, engines and levels, outputStyles, liveZone, sessionDedup, lite, headroom, contextBudget mode, cacheMinutes, exclusions) |
| S1 | wiring smoke: `wiring-smoke` (bash, `ctx_stats`, `tool_search` then a deferred tool, bash) per arm | passed on `plain`, `stack`, `stack-ext` (the earlier attempt on the superseded kit failed for capacity and is kept) |
| S2 | 3 tasks x 4 arms x 2 attempts, arm order reversed on attempt 2 | 24 of 24 passed |
| R1 | one real run killed mid-turn and resumed | passed |
| S2b | a large-output fixture with the same four arms | not run: the next decision-changing test |
| S3 | graded comparison against `codex exec` through Harbor v0.23.0 (its `pi` agent needs a subclass for the stack arms) | deferred: container isolation and its own preregistered record |

S1 criteria and outcome: the gateway answered 200 for the model id (all runs); the entry gateway logged a row per request under the run id (3, 6 and 6 rows); cache reads appeared from the second request
(0.976 for both stack arms, 0.0 at the request after the `tool_search` load); the compression state before each run was recorded; the RTK tracker delta was 1 for both stack arms; one `ctx_*` call and one deferred tool
loaded through `tool_search` succeeded in both. The plan itself is evidenced by `tokens.compressed` in the call logs (nonzero on header-less arms, zero on header-off arms), not by the read-back's `stacked_pipeline`
key, which is the configured stacked-mode pipeline.

## Running it

```sh
python3 kit/stage.py --pi-src <pi v0.99.1 build> --state <state dir> [--stack-compression <header value>]
python3 kit/stage.py --pi-src <pi v0.99.1 build> --state <second state dir> --stack-compression off   # the stack-gwoff control; link its runs/ to the first state's
python3 kit/probes.py --state <state dir>                      # offline, spends nothing
python3 kit/omni_verify.py --json <out>                        # gateway read-back, probe trio, cache share (a few cached tokens)
python3 kit/fixtures.py selftest && python3 kit/fixtures.py manifest
python3 kit/run_task.py --state <state dir> --arm stack|stack-ext|plain --task wiring-smoke --attempt 1
bash kit/run_s2.sh <kit dir> <state dir> <second state dir> <log>          # S2: 24 runs
python3 kit/run_r1.py --state <state dir> --arm stack --task multi-file-rename --kill-after 2
python3 kit/gateway_usage.py <run id>
python3 kit/summarize_runs.py --state <state dir> --json <out>
python3 kit/build_evidence.py --state <state dir> --out evidence
```

Gateway terms from the owner that the trial follows: a unique `X-OmniRoute-Session-Id` per run (pi sends it), client timeouts of at least 900 s (the runner allows 1,800 s), no gateway setting, combo or key writes,
and a live look at the pool before each stage. OmniRoute's `GET /api/usage/provider-limits` is a cache that syncs every 70 minutes; upstream's `POST /api/usage/provider-limits` refreshes that cache (no setting) and is
what `run_s2.sh` calls before each attempt. `gateway_usage.py` never prints the account, connection or key fields that call logs carry.

## Limits

- Fixtures are synthetic and small, n is two per cell: S2 shows layer invocation, complete usage, cache behaviour and possible regressions, never efficacy. The stack's mechanism for large outputs is not exercised.
- Cache shares are confounded by warmth across runs (above); arm order was reversed on attempt 2 but n is two.
- Usage below the entry gateway is unknown: the `sharedgw` hop does not carry the run id, so no 20128 row joins to a run. `usage_assessment` coverage stays partial.
- Outbound effort is not observable while gateway detail capture is off. pi asks for `xhigh` because OmniRoute clamps `max` for models without a registry entry.
- Attempt numbers in `experiment.json` count per task, role and condition, so two runs differ from the runner's label (the S1 `stack-ext` run is attempt 2 after the failed 14:12Z run of the same shape, R1 is attempt 3); each such scope says so.
- Host mode: pi has no permission system and shares the host's loopback services with the model. This is not container isolation.
- `codemode` is available in pi but not exercised. ai-memory and socraticode are not in the arms, and there is no Claude arm.
- pi `main` moves several times a day; the pin is a tag, and a later release is a different candidate.
