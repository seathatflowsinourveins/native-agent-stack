# GPT-6 lane compression A/B preregistration

**DRAFT — not sealed, not run, no execution or adoption authority.** Foundation
lane, 2026-09-27, reference base `0f76651d`. The machine-readable contract is
[preregistration.json](preregistration.json). All live results, usage, pricing
ratios, runtime qualification and role decisions remain `null`.

The intended decision is the configuration with the fewest total billed token
positions among quality-qualified configurations, separately for builders,
reviewers and researchers. Exact numbers, pins, hashes and record contents are
hard gates. Compression analytics cannot establish either correctness or lower
billing. This document proposes an experiment; it does not change either gateway,
install tools, start clients, register keys or schedule a run.

## Research and capability boundaries

The recorded harness mapping is in
[the convergence source review](../../catalogs/convergence-practice/source-review.json),
[Harbor's source record](../../catalogs/convergence-practice/architecture-wave/harbor-framework__harbor.json),
[the September 26 catalog](../../catalogs/sota-convergence/manifest-20260926.json)
and [the stack manifest](../../manifests/stack.json). Catalog inclusion is not
host acceptance. The sibling #416 compaction-window draft supplied document and
receipt structure only. Its task results and thresholds are not evidence here.
The local test extends the document boundary used by
[test_token_e2e_preregistration.py](../../tests/test_token_e2e_preregistration.py)
at the reference base.

Research used the installed search-first, find-skills, tdd and verification
skills. The user had already specified the test/document seam. Installed skill
sources were sufficient for this extension; no installation was attempted.
Direct shell GitHub access failed, but read-only `rtk gh api` through the installed
research tool succeeded. Release/tag checks preceded the source decisions below.
The source inventory in JSON records immutable revisions, file spans and the
evidence class. Sources establish available interfaces; no native harness or
provider acceptance run occurred.

| Component | Pinned finding | Consequence |
| --- | --- | --- |
| Harbor v0.23.0, `1e5c5c6db929a10a140d05e606882c671ae20729` | Native TOML/inline config is accepted and uploaded after runtime overrides. [Loader/merge, L1207–1296](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/codex.py#L1207-L1296) | Provider base URL and static headers can be carried in native config; prove the actual resulting request. |
| Harbor native Codex | Harbor chooses its own `CODEX_HOME`; it retains native sessions. [Home/environment, L1352–1359](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/codex.py#L1352-L1359), [retention, L1452–1476](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/codex.py#L1452-L1476) | Use native transcripts for exact output, with ATIF as a cross-check. Do not copy the coordinator's home or authentication store. |
| Required `-p stack-worker` | Forwarding **not found in** v0.23.0 [CodexOptions, L38–59](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/codex.py#L38-L59), [shared options, L50–70](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/options.py#L50-L70) or [launch, L1432–1448](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/codex.py#L1432-L1448). Harbor was not found on PATH. | **Sealing blocker.** Native config support does not prove this literal invocation. Resolve with a supported upstream route or a pre-data protocol/pin amendment; do not invent `extra_args`, a custom runner or silently flatten the profile. |
| Harbor verifier and Rewardkit | [Native verifier, L165–250](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/verifier/verifier.py#L165-L250) runs task tests. The bundled Rewardkit package is 0.2.0, but the unchanged [example verifier, L1–2](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/examples/tasks/reward-kit-example/tests/test.sh#L1-L2) pins 0.1.8. | Freeze the actual criteria/dependency; do not describe the example as 0.2.0 acceptance. |
| promptfoo 0.123.1, `34f74d34e140b5e17d23770dfb2340057b1936b8` | OpenAI [base URL, L111–128](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/providers/openai/index.ts#L111-L128) and **Responses** [headers, L1195–1210](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/providers/openai/responses.ts#L1195-L1210) are supported. | Use `openai:responses:<model>`, `apiBaseUrl` and `headers` for gateway diagnostics. |
| promptfoo repetition/grading | [CLI, L54–97](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/commands/eval.ts#L54-L97) has `--repeat`, `--no-cache`, concurrency and `--model-outputs`; [Python assertions, L32–63](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/assertions/python.ts#L32-L63) normalize results and fail exceptions. | Grade retained native Codex outputs offline. Direct promptfoo repetitions are separate gateway checks; they do not prove a persistent Codex tool session. |
| Inspect 0.3.271 / inspect_swe 0.2.71 | The tagged [Inspect changelog, L1–4](https://github.com/UKGovernmentBEIS/inspect_ai/blob/c2b63a0b0560f9c3b5b5230365e0a8fe08cd3df0/CHANGELOG.md#L1-L4) adds extra headers/body. The installed CLI reports 0.3.266. [inspect_swe, L619–637](https://github.com/meridianlabs-ai/inspect_swe/blob/7eb8dd64309db4cd0f6bdf1d0ffd9786a74a4088/src/inspect_swe/_codex_cli/codex_cli.py#L619-L637) rewrites routing through its bridge. | Runner-up only. Substitution requires a pre-data amendment and transport/profile requalification; never pool different runners. |

Codex reports 0.157.1. Every eventual native arm must use `-p stack-worker` and
max effort with identical lane-local effective configuration except its provider
definition and routed model. Freeze profile/project precedence, binary and config
hashes. The `-max` model names below are mandatory. The unsuffixed name is locked
out until a separate 20128 observation proves `reasoning_effort_upstream=max`
through the openai-compatible node, followed by an amendment before data.

## Five confirmatory cells and bounded exploratory work

| Cell | Route/model | Input engines | Output styles |
| --- | --- | --- | --- |
| C | `20128/v1`, `cx/gpt-6-astra-max` | Compression globally off; `codex/*` excluded | Off |
| D0 | `20129/v1`, `sharedgw/cx/gpt-6-astra-max` | Headerless defaults | Off |
| D1 | Same framework route | Headerless defaults | On |
| A0 | Same framework route | All 12, static `x-omniroute-compression: allow-lossy` | Off |
| A1 | Same framework route | All 12, same static header | On |

Both URLs use `http://127.0.0.1`. The framework instance chains through provider
node `sharedgw` to 20128. The headerless set is `session-dedup`, `ccr`, `lite`,
`headroom`. “Lossless defaults” is an upstream label, not this experiment's
finding. The full set adds `rtk`, `codex-responses`, `relevance`, `caveman`,
`aggressive`, `llmlingua`, `ultra`, `omniglyph`. Preserve upstream engine order
and freeze all thresholds, models, preservation rules and fallback settings.

Styles-on selects `terse-prose`, `less-code`, `ponytail`, `i-have-adhd`, all at
`full`, with legacy caveman output configured `lite`. Inspection corrects an
additive interpretation: explicit nonempty styles **override** legacy caveman.
Styles-off sets both `outputStyles=[]` and `cavemanOutputMode.enabled=false`;
clearing only the list re-enables its legacy fallback. This comes from
[backCompat.ts L13–28](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/outputStyles/backCompat.ts#L13-L28).

These five cells are the economical direct-control-plus-2×2 design. All four
candidate-versus-C comparisons are confirmatory for each role. D1–D0 and A1–A0
separate output-style effects at each input setting; A0–D0 and A1–D1 describe
input-engine effects. These internal contrasts and interactions are explanatory.
C versus a framework cell also includes the extra hop; it cannot identify a
pure compression effect independently of routing.

The future host owner must reserve exclusive 20129 experiment windows, snapshot
settings, apply/read back the exact cell, and restore the snapshot. No shared
settings race is permissible. Freeze applied/skipped/no-eligible engine evidence;
an enabled toggle does not show that an optional engine actually ran. Failure
to isolate styles or traffic leaves the factor untested.

Only after a complete confirmatory cohort, reserved budget may fund exploratory
D0-plus-one-engine cells in this fixed order: `codex-responses`, `rtk`,
`relevance`, `caveman`, `aggressive`, `llmlingua`, `ultra`, `omniglyph`. Each uses
styles off and three paired repetitions of all six tasks per role against D0.
Do not choose engines after looking at outcomes. No exploratory cell promotes
a role without fresh confirmation.

Optional exploratory D0-keyed and A1-keyed cells compare their corresponding
keyless cells with a registered 20129 principal and `cacheMinutes=60`. A future
host owner keeps that key in a private per-provider **0600** store, outside the
checkout, never printing it. Match account/session conditions and retain only
sanitized identity checks. Key registration and live-zone reuse are separate
facts. No registration occurs in this draft.

## H1–H6: installed-source checks and required experiments

The installed package's `dist/BUILD_SHA` is `dd6e9607e`, corresponding to the
recorded build `dd6e9607e4884ec75c9bc0d96e60b01e9483d84e`. Its compression source
matches upstream base `a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3` byte-for-byte for
the seventeen files listed with SHA256s in JSON. Public citations use that verified
upstream base, rather than assuming the local cherry-pick commit is published.
This is source verification of peer report #423, not a new gateway observation.

**H1, cache.** [liveZone.ts L127–132](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/liveZone.ts#L127-L132)
requires principal, session and variant. [chatCore.ts L1793](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L1793)
derives the principal from caller API-key identity. Without a live-zone context,
[L376–395](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/liveZone.ts#L376-L395)
calls compression again. Prefix damage is a hypothesis: deterministic results
or other memoization can still preserve cacheability. The reported **about 94%**
20128 cache rate is historical peer context, with current measurement `null`.
Measure input, cached subset, uncached input and priced billed-input equivalent
for each complete user turn, including all its tool continuations and retries.

**H2, exact content.** The minifier uses `JSON.parse`/`JSON.stringify` at
[codexResponses/index.ts L137–145](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/engines/codexResponses/index.ts#L137-L145).
Canaries require exact lexemes `1234567890123456711`, `1.50`, `-0.0100`, pin
`dd6e9607e` and a complete 64-character hash. A rounded integer or `1.5` fails.
Qualify the minifier's size thresholds before claiming its path was exercised.

Lite's default maximum is 2,000 characters, and its
[tool truncation L148–168](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/lite.ts#L148-L168)
retains only a prefix. The peer's unknown Responses path is now source-traced:
[bodyAdapter.ts L116–145](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/bodyAdapter.ts#L116-L145)
maps `function_call_output` to `role: tool`, and
[strategySelector.ts L367–386](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/strategySelector.ts#L367-L386)
adapts and restores the lite/stacked paths. Actual configured truncation remains
a host check. Do not transfer codex-responses eligibility guards to lite.

The dedup defect is an index-key collision: string message 1 and multipart
message 0, part 0, both use key 1 in
[session-dedup/index.ts L291–345](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/engines/session-dedup/index.ts#L291-L345).
The probe preserves a distinct earlier user pin alongside repeated multiline
blocks, then checks the earlier message bytes and the turn-3 answer. Test it
in headerless cells too. Caveman rewrites, relevance sentence selection,
aggressive summarization, LLMLingua and ultra pruning have separate installed
file/line references in JSON. Run exactness checks against the effective pipeline,
not merely its safety labels.

**H3, styles.** The enabled/header-not-off condition at
[chatCore.ts L1689–1734](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L1689-L1734)
does not require `allow-lossy`. “Every request” therefore means configured,
eligible requests, not unconditional injection. Check complete deliverables,
all required patch hunks/explanations, schema fields and exact record values.

**H4, control.** Header/per-key opt-out leaves independent context-fit safety
enabled at [chatCore.ts L1443–1449](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L1443-L1449).
Proactive and last-resort passes additionally require
`!nativeCodexPassthrough` at
[L2134–2160](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L2134-L2160)
and [L2210–2231](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L2210-L2231).
Framework-route reachability must be observed. An exploratory bounded threshold
probe compares histories below/above the resolved thresholds, including header
off. **20129 with header off is never C.**

**H5, both hops.** Source supports configured Responses `include`, `store`,
`previous_response_id`, `prompt_cache_key` in
[promptfoo L1003–1040](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/providers/openai/responses.ts#L1003-L1040).
OmniRoute applies cache-key, session and conditional reasoning transformations at
[codex.ts L1498–1573](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/executors/codex.ts#L1498-L1573).
Neither fact proves chain continuity. Observe client→20129→20128→provider
boundaries privately: stable prompt-cache/session identity, supported affinity
carriers (including `x-omniroute-connection`), actual account, `store=false`, effective encrypted-reasoning `include`,
byte-identical real encrypted items and matching call IDs on turn 2. An absent
reasoning item leaves that check `null`; never fabricate one. Freeze actual
supported affinity headers before use; candidate names in JSON are a checklist,
not a claim that each is forwarded.

**H6, roles.** This is the user's policy, not a package feature. Only builders
may canary early, in isolated reversible work after deterministic exactness and
transport gates. Reviewer/researcher experimental outputs remain quarantined;
production judgment, verification, review, research and evidence use C until
their own role/domain passes. Any output that becomes a record needs exact-value
preservation. A successful task score cannot waive a corrupted verdict or pin.

## Task packets, controls and multi-turn unit

Each role has six fixed tasks. The JSON contains task prompts/source bindings,
known answers, schemas, literal input files, source-derived synthetic defects
and canary bytes. Hashes bind the entire packet, including oracle/control
contracts. They do not pretend that executable adapters or containers exist.

| Packet | SHA256 |
| --- | --- |
| Builder | `e42a388f70cf7b94b2a59b6b19bc625911df44716c52d857fa8c65985256ec74` |
| Reviewer | `8ca985caea25ee2c62ca1640d64b0be55faeed505a702dd964c9e6662ff7476b` |
| Researcher | `eda4967d6e0dfb1bf9d433c0fbf55c04c14a3603299d3937488d109daa07b056` |
| Shared canaries | `f06487b5af0fdab5a12dbb35cae00b4b6b0e6ec938311a961c9f5ea332446b43` |

Packet serialization is UTF-8 JSON, sorted keys, ASCII escapes, compact
separators, no NaN, no trailing newline. Hash only the `packet` member. The
structural test independently recomputes these hashes.

Builder tasks reuse unchanged Harbor examples: TOML table conversion,
Rewardkit text statistics, native multi-step file work, MCP exact output,
working-directory capture and a separate verifier environment. All **52 source
files** were fetched through `gh api`, and per-directory SHA256 manifests were
independently recomputed. The manifest hashes sorted records
`relative_path + NUL + sha256(file_bytes) + LF`; each selected directory and
digest is in JSON. Run original instructions/step files and original verifiers;
the short descriptions are indexes, not replacement prompts. Four tasks are
smoke/tool-chain checks. They cannot justify broad builder adoption.

Reviewer tasks contain one source-derived planted defect each: numeric rounding,
multipart-key collision, long-output truncation, cache double-counting, legacy
style fallback and discarded encrypted reasoning. Grade exact defect identity,
file and evidence values. These are synthetic tasks, not new security findings
or unchanged upstream test cases.

Researcher tasks extract number lexemes, pins/hashes, long-output tail fields,
honest unknowns, non-overlapping usage and style precedence. Every output has an
explicit schema and exact expected typed object. One fixed-reminder schema retry
is permitted and counted; the initial failure remains in the primary endpoint.

Builder controls are Harbor's native oracle and nop agents plus malformed,
missing or nonfinite reward artifacts. Reviewer/researcher controls feed the
complete expected answer, an intentionally wrong value and malformed output
through the same extraction/grading path. Also reject duplicate keys, extra
fields, missing output, zero tests and exit-zero-without-reward. The numeric
controls specifically distinguish `1234567890123456800` and `1.5` from the
required values. Native control runs and adapter hashes remain unresolved;
this repository test is structural evidence only.

Every scored attempt includes **one persistent native Codex session with three
user turns**, tools on every turn, and the original role task. Turn 1 completes
the native task and captures tool evidence; turn 2 uses earlier tool outputs and
a real function-call/output pair while making another tool action; turn 3 returns
the exact record using earlier provenance and tail values. The canary artifact
is separate from the original builder deliverable, and the task's original reward
is retained. Primary success requires both core task and mandatory canary success.
Capture pre-compression tool bytes, final wire/transcript evidence and delivered
record independently. A failed trigger is untested, not a passing canary.

Harbor's exact profile/continuation protocol must be qualified before use. The
draft creates no replacement orchestration. A loop of promptfoo calls or repeated
single-turn jobs cannot satisfy this requirement.

## Accounting and operational metrics

**Count usage exactly once at 20128.** Required columns are `timestamp`, `path`,
`status`, `model`, `reasoning_effort_requested`, `reasoning_effort_upstream`,
`tokens_in`, `tokens_cache_read`, `tokens_reasoning`. Also require a stable request
row ID, **`tokens_out`** and duration. Source declares these at
[callLogs.ts L90–107](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/usage/callLogs.ts#L90-L107);
the actual host database has not been inspected. Without output tokens, output
style costs and total billed tokens are unknowable.

Use finalized request IDs, mapped privately to task/session/user-turn ordinals.
Sum all calls within the user turn, including retries/tool continuations. Update
an unfinished row on the next poll instead of adding cumulative snapshots.
Timestamp/model matching alone is insufficient with shared traffic. Include
failed, cancelled and retried attempts; no automatic replacement of bad trials.
Missing 499 usage stays `null`, making cost comparison incomplete.

| Quantity | Formula/boundary |
| --- | --- |
| Uncached input | `sum(tokens_in - tokens_cache_read)` |
| Total billed token positions | `sum(tokens_in + tokens_out)`; cached input included once |
| Billed-input equivalent | `sum(tokens_in - tokens_cache_read + cache_price_ratio * tokens_cache_read)` |
| Priced total equivalent | Uncached input + weighted cache reads + weighted total output |
| Reasoning | Display `tokens_reasoning` separately; it is an output subset |
| Compression savings | Isolated before/after deltas from **20129 `GET /api/analytics/compression`**, never added to 20128 usage |

Total token positions are not dollars. Freeze applicable cache/output price
ratios before a billing conclusion; both remain `null` now. Never add cached
input to total input, reasoning to total output, engine savings to overlapping
pipeline savings or 20129 usage to the downstream ledger. Contaminated analytics
windows leave savings unknown.

Report original verifier success, combined success, rejected `apply_patch`
invocations, verification failures, schema retries and tool-output recall.
Recall means an unrequested second read of an unchanged file and overlapping
byte range after a successful first read; changed-file verification and scheduled
canary reads are excluded. Unresolvable file identity is unknown. Preserve both
event counts and session-any-failure indicators. Latency is monotonic end-to-end
task/turn duration including tools, grading and retries. Count 499 request rows
and cancelled sessions separately, including local cancellations with no row.

## Repetitions, analysis and role decisions

The fixed confirmatory allocation is **240 paired session draws per role per
cell**, 3,600 scored native attempts plus assigned priming sessions. Each draw selects from the frozen six-task
role mixture and a cold-labelled/warm-labelled condition with equal probability,
using the pinned random generator and seed defined in JSON. Expected repetition
is 40 per task per cell. Seal the realized schedule before any provider probe;
there is no outcome-driven task balancing or extra sampling. The same draw runs
all five cells. Counterbalance their order with the five specified Williams
orders and their reversals, rotated by role ordinal.

Fresh sessions isolate arms/repetitions; stable identity preserves within-session
affinity. Warm-labelled attempts get a fixed same-arm priming sequence, fully
charged to their attempt, including failed primes. The expected 1,800 additional
priming sessions are not hidden inside the 3,600 scored-session count; the sealed
schedule fixes their actual count. Cold-labelled attempts have no prime and a fresh
namespace. These are assigned conditions, not proof of provider cache state:
measure actual warmth, session/account routing and timing on every turn. Never
flush the shared gateway or assume a delay guarantees a cold provider cache.

Success and operational-failure non-inferiority margins are both **5 percentage
points**, separately for each role. Operational failure is any unexpected patch
or verifier error, schema retry, invalid tool round trip, cancellation or missing
output in a session. Task-success and operational-failure details remain visible.

For a conservative paired gate, count harmful discordances: C passes/candidate
fails for success; candidate has operational failure/C does not for failure.
Their probabilities upper-bound net harm. Require one-sided
`scipy.stats.binomtest(k, n, p=.05, alternative="less")` rejection for each
co-primary endpoint after `statsmodels.stats.multitest.multipletests(method="holm")`
over **24** tests (3 roles × 4 candidates × 2 endpoints). Missing tests get
`p=1`. Also require observed net differences within the margins and **zero exact
record/canary corruptions**. Paired attempts are the units, never calls. Control and candidate must also each achieve at least **90% combined success**,
with at least one successful attempt of every task. An all-failing control cannot
qualify a cheap treatment. Independent
draws from the frozen mixture and independent provider attempts are assumptions;
temporal dependence or failed randomization makes the result inconclusive.

Use pinned **SciPy 1.18.1** [bootstrap](https://github.com/scipy/scipy/blob/e4e854eaa8f18d807cd3496028e257e36caa93cc/scipy/stats/_resampling.py#L300-L394)
and [permutation_test](https://github.com/scipy/scipy/blob/e4e854eaa8f18d807cd3496028e257e36caa93cc/scipy/stats/_resampling.py#L1679-L1780)
for paired whole-session difference/cost intervals and explanatory paired cost
permutations. Keep every turn, retry and warm-up attached to its session. Exact
binomial bounds guard zero-width/undefined bootstrap intervals; a nonsignificant
equality test never establishes non-inferiority. Holm is supplied by
[statsmodels 0.15.0](https://github.com/statsmodels/statsmodels/blob/278ff9950636cdd4939b4055e339a8e681d79cab/statsmodels/stats/multitest.py#L99-L149).
Seeds, resample counts and alternatives are in JSON. No custom statistics engine
is proposed. No power or precision outcome is claimed in advance.

Among complete quality-qualified cells, choose the minimum **all-attempt total
billed tokens** on the identical role schedule. Values within **1%** of the
minimum are a practical tie: prefer C, then D0, D1, A0, A1. If the paired cost
interval does not establish any saving, retain C. Promotion also requires the
upper one-sided 95% bound on both warm-stratum priced input and priced total
ratios versus C to be at most **1.01**. Unknown billing weights cannot justify
economic promotion. This catches a shorter compressed prompt that destroys a
valuable cache prefix.

Only a whole tested configuration in its qualified role/task domain may move.
A1 can qualify for a research domain while builders retain C. Exploratory
one-engine evidence cannot identify every engine interaction or authorize broad
adoption. Broad judgment/review/evidence use needs representative tasks beyond
this narrow six-task pack and exact-value tests on the records it creates.
Underpowered, incomplete or invalid cohorts retain C and keep all costs visible.

## Budget, cancellation, validity and sealing

The planned ceiling is **24,000,000** downstream input-plus-output token
positions: 2,000,000 qualification/controls, 20,000,000 confirmation including
priming, 2,000,000 exploration. Use one owned session at a time, a 600,000-token
inflight reserve, five-second ledger polls, 30-minute session and seven-day whole
run wall limits. No starts when a conservatively bounded next session cannot fit.
Before confirmation, use qualification usage to check whether the entire fixed
cohort can fit; no optimistic partial-cohort promotion. Native request/output
bounds are a sealing gate. Until enforceable charge bounds are demonstrated,
describe the cap as monitored with possible cancellation overshoot.

Stop on record corruption, budget/reserve threshold, authentication/quota refusal,
model/effort/config drift, ambiguous usage, ledger delay beyond 30 seconds,
failed controls, uncontrolled traffic, five consecutive 499/error requests or
three cancelled sessions within ten owned sessions. A corruption veto stops that
treatment immediately; do not continue spending merely to estimate its rate.
Retain the incomplete cohort and every failed attempt.

Use Harbor's native cancellation first. Record owned job/container/process-group
identities at launch; stop new work, interrupt only that group, allow ten seconds,
then TERM and another ten seconds before KILL of surviving owned descendants.
Clean only owned resources through Harbor. Never stop either gateway or use a
broad process-name kill. Observe local termination independently and reconcile
downstream terminal/499 rows for up to 60 seconds. Remote provider cancellation
and unknown trailing usage remain unproved when not observed. Restore only the
owned 20129 settings snapshot. None of these operations occurs while drafting.

Main validity threats are cache warmth, both-hop affinity/reasoning continuity,
provider nondeterminism and time/order effects, configuration time slicing,
optional engines that never apply, promptfoo's result cache, narrow task coverage
and ambiguous repeated reads. No result can resolve a threat merely because its
receipt has valid JSON. Use `--no-cache` for promptfoo's own result cache while
preserving native provider caching. Keep salted correlation identifiers and raw
conversations private; publish bounded sanitized artifacts and source hashes.

Before the first model capability probe, the coordinator must seal source/task
bytes, runtime images/dependencies, exact graders and their negative controls,
native profile/three-turn invocation, realized order/prime schedule, effective
configuration, both-hop transport and ledger mappings. Unknown executable hashes,
image digests and readiness results stay null. Changes after sealing require an
append-only dated amendment preserving old/new hashes and whether data existed;
material changes require a fresh cohort. This draft cannot supply that seal.

Open host items are explicitly enumerated in JSON: the Harbor profile gap,
native two-hop acceptance, effective settings/max effort, request/output billing
fields and pricing, native pinned harness readiness, full grader controls,
representative domain coverage and optional keyed live-zone reuse. These are
future verification requirements, not fabricated passed checks.

## Local structural evidence and corrections

The requested test was written before either draft file. The command was:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_gpt6_lane_compression_ab_preregistration.py -v
```

It returned **exit 1**, `Ran 1 test; FAILED (failures=1)`, specifically
`preregistration.json does not exist yet`. After the files were written, the same
command returned **exit 0**, `Ran 1 test; OK`. This checks the document contract
only; it is never Harbor, promptfoo, model or gateway acceptance.

`rtk env PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0 python3 scripts/validate.py`
also returned **exit 0**, `status: passed` (69 components, 7,348 hashed files,
4 profiles, 159 receipts). Its tracked publication scope is separate from the
untracked draft contract; all three new files also receive an explicit
publication scan before handoff.

The scoped anti-pattern log in JSON preserves the corrections from this work:
safe labels are not preservation evidence; explicit styles override legacy mode;
Responses can reach lite via the adapter; configurable native config does not
prove profile-flag forwarding; and shell network failure was not research
unavailability. One research preflight wrongly assumed `promptfoo --help` was
observational: it attempted log cleanup/database migration and failed with
read-only/database errors, exit 1. No successful host write was observed.
[Startup migration L63–64](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/main.ts#L63-L64)
precedes parsing, and [logger L224–247](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/logger.ts#L224-L247)
explains cleanup. Subsequent inspection used package metadata/source. The
coordinator can carry this correction into the shared anti-pattern log; this
builder's file ownership is limited to the requested deliverables and test.
