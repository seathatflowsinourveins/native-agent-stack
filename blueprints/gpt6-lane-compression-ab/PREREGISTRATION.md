# GPT-6 lane compression A/B preregistration

**DRAFT — not sealed, not frozen, not run.** Repair round for draft PR #431 at
`f201e07b`, 2026-09-27, foundation lane. No execution or adoption authority.
The machine-readable contract is [preregistration.json](preregistration.json).
All model results, route qualification, pilot measurements, powered sample
sizes and confirmatory resource allocations remain `null`.

This experiment compares all-attempt entry-gateway input plus output tokens,
subject to paired quality, exact-record and transport gates. Its ceiling is
**the six named task domains per role**. It cannot authorize moving a production
builder, reviewer or researcher role. Reviewer/researcher output-style conclusions
cover **JSON-only records**; prose verdicts, research narrative and evidence-writing
need representative frozen tasks in a new preregistration.

Research used installed search-first inline, find-skills discovery, TDD and
verification-before-completion at the user-specified document/test seam. The
installed Codex reports 0.157.1 and its prompt-input help describes a renderer.
No model was called, including no prompt-input invocation in this repair.
Seventeen installed OmniRoute source hashes were recomputed: all 17 match the
retained pinned upstream bindings. This is source identity, not live acceptance.
Direct shell gh failed to connect; read-only gh API through Context Mode supplied
release notes and pinned source. No installed skills/tools or host configuration
were changed. Sources and the exact review dispositions appear below and in JSON.

The historical original authoring evidence is retained in JSON. This round uses
the dated checks/findings/remaining-gates structure from
[PR #416 build evidence](https://github.com/seathatflowsinourveins/native-agent-stack/blob/b6f36d8cac660b47cafc827ee4595cf0bc74459a/blueprints/compaction-window-ab/build-evidence.json).
That file was absent in this worktree and read at the cited upstream revision.

## Runner and native configuration

**Choose Harbor v0.23.0 conditionally, under option (b).** Harbor at `1e5c5c6d`
passes only the final slash-separated segment to `--model`. Main `3c823808` does
the same; no release after v0.23.0 was found in the releases API checked on
2026-09-27. The canonical models below are therefore **not what Harbor currently
emits**. The emitted argument for every cell is `gpt-6-astra-max`. A working
20129-side route for that argument has not been identified or qualified.
The established built-in `gpt-6-astra*` precedence rules out assuming an ordinary
stored alias fixes it. This is an open sealing gate, not a fabricated mapping.
[Harbor command](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/codex.py#L1339-L1449), [inspected main](https://github.com/harbor-framework/harbor/blob/3c82380859d187957cfd5cd64802b076d9779550/src/harbor/agents/installed/codex.py#L1502-L1605).

| Alternative | Source-backed comparison |
| --- | --- |
| Later Harbor release/main | Release query returned v0.23.0 as latest; inspected main still strips prefixes. An upgrade alone is not a demonstrated repair. |
| Inspect inspect_swe 0.2.71 | Resolves a catalog slug into `--model` and routes through its own OpenAI bridge. Profile, wire and correlation equivalence require qualification. [Command and bridge](https://github.com/meridianlabs-ai/inspect_swe/blob/7eb8dd64309db4cd0f6bdf1d0ffd9786a74a4088/src/inspect_swe/_codex_cli/codex_cli.py#L483-L637). |
| promptfoo Codex SDK 0.123.1 | `config.model` passes intact into thread options; Codex SDK passes it intact to `--model`. Explicit thread resume exists, while deep tracing forces fresh threads. This is the strongest alternate for prefix preservation; native task/verifier/container integration is unqualified. [Provider](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/providers/openai/codex-sdk.ts#L1034-L1134), [SDK](https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/sdk/typescript/src/exec.ts#L91-L178). |

Harbor retains the existing native task/verifier/multi-step route without a new
runner implementation. **Overturn this choice** before confirmation if promptfoo's
Codex SDK passes the same merged-config, prompt-input, three-turn tool/verifier,
correlation and both-hop effort checks while Harbor has no supported route or
has unequal native semantics. Amend once before data; never pool runners.

Route qualification belongs to the coordinator. Compare
`codex debug prompt-input` for the slashless candidate against the canonical
one-slash slug with identical semantic settings. Require the expected five items
and equivalent template, tools, Responses Lite and multi-agent metadata after
declared identity/path normalization; item count alone is insufficient. Then
require one attributable live 200 at max through 20129 and prove C's emitted
bare route equivalent to `cx/gpt-6-astra-max`. Reuse the user's established
one-namespace metadata fact; do not re-probe it during repair.

Adopt the **native semantic deep merge** of frozen `config.toml` followed by
`stack-worker.config.toml`, with no `profile` or `profiles` keys. Hash both inputs,
merged TOML, uploaded config and resolved effective settings. Codex's merge has
normalization and replacement rules beyond a shallow dictionary update. Harbor
uploads this file via `config`, then applies its runtime/MCP overrides.
[Profile loader](https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/codex-rs/config/src/loader/mod.rs#L286-L340), [merge implementation](https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/codex-rs/config/src/merge.rs#L56-L185),
[Harbor upload](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/codex.py#L1207-L1296).

Equivalence gate: same binary/model/cwd/project/system layers and effective
forced flags, compare **resolved configuration and prompt-input** from the
`-p stack-worker` base-plus-profile reference to the merged-file run without `-p`.
Repeat after Harbor upload. Configuration provenance paths may differ; semantic
settings, prompt content and tool definitions must match. Freeze the native
resolved-config inspection command before qualification; it was not run here.

Harbor's actual command contract is:

```text
codex exec [resume --last on turns 2/3]
  --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check
  --model gpt-6-astra-max --json --enable unified_exec
  -c model_reasoning_effort=max -- <shell-quoted-step-instruction>
```

The upstream wrapper optionally sources NVM, redirects `2>&1 </dev/null` and
pipes to `tee`. Freeze bypassed approvals/sandbox, git-check bypass, unified_exec,
JSON output, runner home and MCP overrides as equal deviations across arms.
This is not acceptance of stack-worker's sandbox. A tee exit alone does not
prove Codex or verifier success. [Launch and options](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/codex.py#L1339-L1449).

The job uses `environment.extra_docker_compose` with the proposed overlay below,
hashed before use. This is a supported integration shape, not a deployed file.
[Compose implementation](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/environments/docker/docker.py#L350-L420), [upstream example](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/examples/jobs/extra-docker-compose/config.yaml#L1-L8).

```yaml
services:
  main:
    network_mode: host
```

From the actual main container, probe TCP reachability to both loopback ports and
an unauthenticated non-inference health URL, discard the body and retain only
status/latency. Verify actual WSL2/Docker behavior. A successful TCP connection
is not provider acceptance. Host networking and sandbox bypass expose the
**passwordless management APIs**; the inference key does not protect them.
Frozen trusted synthetic tasks, no hostile/internet task input, no host mounts
or Docker socket, one session and independent before/after settings observations
bound scope and detect changes, but do not form a security boundary. Execution
also requires a source-supported, host-qualified network restriction preventing
management and alternate-route access. No such containment is accepted here;
if unavailable, amend to an isolated host/gateway arrangement before running.

## Cells, authentication and wire contract

| Cell | Canonical client entry | Input engines | Output styles |
| --- | --- | --- | --- |
| C | `20128/v1`, `cx/gpt-6-astra-max` | Globally off, `codex/*` excluded | Off |
| D0 | `20129/v1`, `sharedgw/gpt-6-astra-max` | Headerless defaults | Off |
| D1 | Same 20129 route | Headerless defaults | On |
| A0 | Same 20129 route | All 12; `x-omniroute-compression: allow-lossy` | Off |
| A1 | Same 20129 route | All 12; same header | On |

Both gateway URLs are host loopback. The logical model per hop is
client→20129 **`sharedgw/gpt-6-astra-max`**, 20129→20128 **`gpt-6-astra-max`**,
and control C **`cx/gpt-6-astra-max`**. Harbor's stripped argument requires the
route gate above; a config model cannot override its forced `--model`.
Freeze sharedgw **Responses→Responses**, including actual source/target format.
No Chat fallback is confirmatory. Preserve real encrypted reasoning/custom items,
`store=false`, effective include and call IDs at both hops.
[Compression stages/translation](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L1425-L1449), [adapter](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/bodyAdapter.ts#L116-L145).

Headerless engines are `session-dedup`, `ccr`, `lite`, `headroom`. The remaining
eight are `rtk`, `codex-responses`, `relevance`, `caveman`, `aggressive`,
`llmlingua`, `ultra`, `omniglyph`. Freeze upstream order, thresholds and model
dependencies. A safe label is not proof of exact preservation. Explicit styles
are `terse-prose`, `less-code`, `ponytail`, `i-have-adhd`, all full. Nonempty
explicit styles override legacy caveman; styles-off clears them and disables
legacy output mode. A header-off 20129 request is never clean C because reactive
context fitting remains possible. [Policy](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/lossyRequestPolicy.ts#L29-L67),
[style precedence](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/outputStyles/backCompat.ts#L13-L28), [context fitting](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L1425-L1449).

All four D/A cells use the **existing registered lane principal and 60-minute
live zone confirmatorily**. Native Codex uses `env_key = "OMNIROUTE_FW_API_KEY"`;
Harbor uses `extra_env` with the literal variable template
`${OMNIROUTE_FW_API_KEY}`. No key is in static headers, files or CLI arguments.
The owner supplies the existing private 0600 secret through the runner's secret
environment; this repair never opens it. C omits that key and provider env_key.
Require `OPENAI_API_KEY`, `CODEX_AUTH_JSON_PATH`, `CODEX_FORCE_AUTH_JSON` and
ambient `OPENAI_BASE_URL` unset in the Harbor parent process. Harbor may itself
supply an empty OpenAI key/auth stub; verify absence/emptiness predicates only,
never inspect or print a real credential value.
Harbor's KEY redaction can expose partial values when falling back to redaction,
so preserve the environment template and verify no literal/partial secret logs.
[Environment](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/base.py#L560-L648), [redaction](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/utils/env.py#L4-L65),
[principal/session requirement](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/liveZone.ts#L127-L132).

Existing key registration and TTL are user-established facts; observed live-zone
reuse is still a qualification result. The optional keyed exploration was
removed. Single-engine exploratory work cannot promote: each repetition is one
persistent three-turn session per task/cell, three repetitions × six tasks ×
three roles, paired with D0, in fixed engine order and complete blocks only.

## Exactness, tasks and native turns

Every session, including C and sessions with no applied engine, scores exact
numeric lexemes, pins, hashes and records. Engine application is a separate
coverage gate; no-op is not engine acceptance and never silently removes an
outcome. Zero exact-record corruption is mandatory. [Engine eligibility](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/engines/codexResponses/index.ts#L137-L145),
[stage gating](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/strategySelector.ts#L367-L386).

The numeric canary includes `1234567890123456711`, `1.50`, `-0.0100`, pins and
hashes, padded beyond the 512-byte threshold. Four separate native shapes are
specified: shell, MCP text, MCP structuredContent and custom tool. For each,
retain pre-compression output shape/hash, eligibility, whole-string JSON parse,
actual rewrite and delivered exactness. Unified exec and legacy shell prepend
headers, so the whole shell output is not JSON: report the minifier unreachable
on that shape, without stripping headers to manufacture eligibility. MCP and
custom-tool reachability remains open. StructuredContent numeric serialization
can lose scale before compression; use string lexemes and a raw text block to
separate client serialization from engine damage.
[Whole-string minification](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/engines/codexResponses/index.ts#L137-L145), [native tool shapes](https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/codex-rs/core/src/tools/context.rs#L524-L601),
[legacy shell](https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/codex-rs/core/src/tools/mod.rs#L97-L124).

The corrected direct-Chat dedup stimulus has message 0 with padding part 0 and
an independent earlier-pin part 1; message 1 is string block B and message 2
repeats B. Both message 0 part 1 and message 2 use key **2**. Assert
`messages[0].content[1].text` unchanged. The original single-part stimulus could
not trigger that rewrite. Native Responses `input_text` may never meet the
engine's `type=text` condition: record native reachability separately, without
presenting a direct-Chat reproduction as a native lane finding.
[Dedup](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/engines/session-dedup/index.ts#L291-L345), [adapter](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/bodyAdapter.ts#L116-L145), [stage selection](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/strategySelector.ts#L367-L386).

The long canary retains tail sentinels beyond 2,000 characters for lite's
truncation path. Optional dependencies that never fire remain uncovered; setting
all 12 engine names does not prove all 12 ran. Output-style findings remain
within JSON-only reviewer/researcher records. [Lite](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/lite.ts#L148-L168),
[style catalog](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/outputStyles/catalog.ts#L32-L194).

Each role retains six task packets with explicit expected answers and negative
controls. Builder core source directories/verifiers remain pinned; their 52-file
source manifests are historical byte evidence. Canaries and three-step envelopes
are **local integration additions**, not unchanged upstream acceptance. The
native two-step builder runs `create-file`, `append-content`, then one new
`exact-record` step as turns 1/2/3. Other tasks use original-core-and-evidence,
recall-with-fresh-tool, exact-record. Use native Harbor `[[steps]]` and
`agent.resume_trajectory=true`; retain one Codex session, not three independent
jobs. Hash and qualify the wrappers and graders before pilot.
[Native trial](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/trial/multi_step.py#L25-L110), [two-step source](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/examples/tasks/hello-multi-step-simple/task.toml#L15-L31).

| Packet | SHA256 |
| --- | --- |
| Builder | `4ddbb5aae74a1fa6b613d836f62120abf28f3ffd1091ae90e496edb9b879444b` |
| Reviewer | `336a23603b7c31e0f5c8b6a2f6f49f9b27ab77f79c12d3ab7df5ab016fcc6198` |
| Researcher | `eda4967d6e0dfb1bf9d433c0fbf55c04c14a3603299d3937488d109daa07b056` |
| Shared canaries | `8bf066389d8523cbfa1d3593d399a986083b6e875e652901f266469dce5a6d07` |

Hash UTF-8 JSON `packet` values with sorted keys, ASCII escapes, compact
separators, no NaN or trailing newline. Structural tests independently recompute
the hashes. Known-pass, known-fail, malformed, missing/nonfinite rewards, duplicate
keys, missing/extra fields and zero-test controls must run through the native
extraction path. Structural validation cannot close those runtime gates.

One fixed schema-reminder retry is allowed within the original session budget.
Final recovered task/canary success is primary; initial schema, patch and verifier
failures remain secondary events and retain all cost. Only **unrecovered**
operational failures at final termination enter the co-primary endpoint. An
exact-value corruption still vetoes the cell regardless of later recovery.

## Accounting, effort and cache identity

**Count at the entry gateway exactly once:** C uses `20128.call_logs`; D0/D1/A0/A1
use `20129.call_logs`. Exclude the chained 20128 usage row. Required fields include
`correlation_id`, row ID, timestamp/path/status/model/duration, input/output/cache/
reasoning tokens, nullable effort columns and `tokens_compressed`. Join returned
**`X-Correlation-Id`** to that entry row, privately mapping task/session/turn/request
ordinals. Never join by model and time or sum cumulative polls.
[Usage fields](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/usage/callLogs.ts#L90-L107), [response header](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/sse/handlers/chatHelpers.ts#L1172-L1184).

Native Codex's inspected SSE reader exposes selected response headers; no
X-Correlation-Id exporter was found in that path. Preregister a client-side
**mitmproxy 12.2.3 reverse listener** with a minimal header-only adapter following
upstream `responseheaders` and streaming examples. Codex's base URL points to the
owned listener, which forwards model/body unchanged to its entry gateway.
The adapter emits only correlation ID, status, request/flow ordinal and assigned
trial/turn ordinal. It does not read or persist authorization values, request
header dumps, bodies or complete flows. Use identical observation in all arms;
hash the adapter and qualify SSE/cache/tool behavior and error joins before use.
No observer was installed or run here. A second, exact observed downstream-flow
join is required for 20128 effort evidence, with no unrelated lane traffic;
timestamps/model cannot substitute. That join remains open.
[Codex reader](https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/codex-rs/codex-api/src/sse/responses.rs#L30-L101), [header hooks](https://github.com/mitmproxy/mitmproxy/blob/6c09d56e4c29a92f5ad01b03199977584b8ea14f/mitmproxy/proxy/layers/http/_hooks.py#L7-L39),
[stream example](https://github.com/mitmproxy/mitmproxy/blob/6c09d56e4c29a92f5ad01b03199977584b8ea14f/examples/addons/http-stream-simple.py#L1-L14), [reverse mode](https://github.com/mitmproxy/mitmproxy/blob/6c09d56e4c29a92f5ad01b03199977584b8ea14f/docs/src/content/concepts/modes.md#L178-L257).

For effort, GET `/api/usage/call-logs/<id>` at each joined hop and inspect the
stored client/provider request body's **`reasoning.effort`**, printing only that
field. Freeze actual detail selectors during qualification. Null effort columns
are expected without encrypted reasoning and **never prove drift**; they only
corroborate. Missing body evidence stays unknown, observed non-max is drift.
[Conditional columns](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/usage/callLogs.ts#L628-L653), [detail API](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/app/api/usage/call-logs/[id]/route.ts#L1-L22).

| Quantity | Boundary |
| --- | --- |
| Uncached input | `sum(tokens_in - tokens_cache_read)` |
| Total positions | `sum(tokens_in + tokens_out)` at the entry only |
| Weighted input | uncached input + cache ratio × cached input |
| Weighted total | weighted input + output ratio × total output |
| Reasoning | Output subset, reported separately, never added again |
| Compression diagnostic | Joined 20129 `tokens_compressed`; includes reactive compaction, not billed savings |

Exclusive-window analytics can corroborate compression diagnostics but are
optional and never additive with per-call savings. Retain failures, retries and
cancellations. Null usage remains null, with a lower/upper interval only if
supported by stored nonsecret request size **and** provider serialization/context
and output caps. Request bytes alone cannot bound total tokens; pilot maxima
are not hard caps. Without a defensible upper bound, cost is inconclusive.
Require the winner to remain cheaper under candidate upper/control lower totals
and all sensitivity weights. This replaces automatic rejection of every null
499 row while preserving uncertainty. [Nullable counters](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/usage/callLogs.ts#L90-L107).

Actual subscription prices remain unknown. Preregister sensitivity assumptions
**cache ratio [0,1], output ratio [1,10]**, with uncached input as unit weight.
Require the economic guard at all four corners for whole-session and turn 1/2/3
strata; test weighted candidate minus 1.01×C using simultaneous paired bounds.
The weighted inequality is linear in weights, so the corner checks cover the
rectangle. Report crossover weights. This is robustness to stated assumptions,
not GPT-6 dollar pricing or a measured subscription-limit meter.

`x-omniroute-connection` is a **connection pin**, not session affinity. Affinity
uses `x-codex-session-id`, `x-session-id`, `x-omniroute-session`, then body session
identifiers, `prompt_cache_key`, then first-input hash. Live zone instead uses
`x-omniroute-session-id` or a generated body/provider/connection fingerprint.
Trace cache keys at both hops, salted accounts and per-arm account spread/cache
read rates. The review's account-collapse risk remains unobserved; verify it in
qualification. [Affinity](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/sse/services/sessionAffinityPin.ts#L197-L221), [live-zone fallback](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/sessionManager.ts#L103-L145).

## Pilot, statistics and resources

Run no confirmation until an **excluded pre-confirmatory qualification pilot**
has measured each cell. Proposed pilot: 12 paired draws per role, two per task,
all five cells, 180 native three-turn sessions, zero primes. Its provisional
24M-token/seven-day/30-minute-session ceilings are monitored planning limits,
not evidence it fits or execution authority. Preflight native request/output
bounds and reserve before starting. An incomplete pilot cannot size confirmation.
Keep all its usage, wall time, failures and refusals.

Retain joint five-arm final success/unrecovered-failure patterns and per-cell
tokens, wall time, cache by turn, account spread and null-usage bounds. Then use
the pinned NumPy/SciPy algorithms in JSON to simulate power and margin-null
calibration. Candidate n grid: 120, 240, 480, 960, 1920, 3840; 10,000 simulations
per law, seed 20260929. The random primitives are pinned to
[NumPy 2.4.0](https://github.com/numpy/numpy/blob/c5ab79c14c98bfda1e60770ffa23a6130f8267b7/numpy/random/_generator.pyx#L299-L310). Preserve empirical joint dependence and a declared
sensitivity grid. For harmless-arm power, permute all five arm labels within
a resampled pilot draw, preserving joint outcomes with equal marginal rates.
Sensitivity laws use shared-or-independent uniform draws with fixed success and
unrecovered-failure thresholds; exact laws and feasibility rules are in JSON. Choose the smallest n whose lower 95% exact power bound is at least .80
for jointly qualifying four harmless candidates per role, and whose upper
family false-promotion bound at margin-null is at most .055 (Monte Carlo
tolerance .005 around .05). If none qualifies, keep the gate open. No statistical
simulation or pilot result is claimed by this repair.

Primary success harm is `mean(C_success - candidate_success)`; failure harm is
`mean(candidate_unrecovered_failure - C_unrecovered_failure)`. Both margins are
five percentage points. Use `scipy.stats.bootstrap(paired=True, method="percentile")`,
99,999 whole-draw resamples, `alternative="less"`, fixed seed 20260927. Invert the one-sided upper
percentile interval against +.05. This is approximate and must pass the pre-data
calibration; a nonsignificant equality test is not non-inferiority.
[SciPy bootstrap](https://github.com/scipy/scipy/blob/e4e854eaa8f18d807cd3496028e257e36caa93cc/scipy/stats/_resampling.py#L300-L394). Tango's paired-proportions score interval is a
source-backed alternative, recorded but not implemented with a new solver.
[Tango 1998](https://doi.org/10.1002/(SICI)1097-0258(19980430)17:8%3C891::AID-SIM780%3E3.0.CO;2-B).

Exact fallback when fewer than 20 discordant draws, degenerate or nonfinite
bootstrap: h counts harmful discordance and b counts beneficial discordance.
At test level a use one-sided Clopper-Pearson `U(h,n,1-a/2) - L(b,n,1-a/2)`.
This union-bound upper limit covers **net harm**, without independence between
h and b. Require it below .05; invert monotonically for p. All-concordant data
have a nonzero exact uncertainty bound. Unsupported results get p=1.
[SciPy exact interval](https://github.com/scipy/scipy/blob/e4e854eaa8f18d807cd3496028e257e36caa93cc/scipy/stats/_binomtest.py#L52-L115).

Combine the two required endpoints with candidate `p=max(p_success,p_failure)`
(intersection-union), then Holm across **12 role-candidate hypotheses** at .05;
missing/unrun hypotheses get p=1. This avoids treating each mandatory component
as a separate promotion claim. [Intersection-union reference](https://doi.org/10.1214/ss/1032280304),
[Holm implementation](https://github.com/statsmodels/statsmodels/blob/278ff9950636cdd4939b4055e339a8e681d79cab/statsmodels/stats/multitest.py#L99-L149). Control and candidate still need observed
combined success ≥.90, at least one success for each task, zero exact-record
corruption and valid native controls.

Confirmation uses independent uniform draws over each role's six tasks, paired
across all five cells. Retain the Williams orders and their reversals recorded
in JSON. Freeze realized schedule after the pilot and before confirmatory data;
no outcome-driven balancing, replacement or extra sampling. There are **zero
priming sessions**, no cold/warm labels and no cache flush. Analyze measured
cache state by user turn 1, 2 and 3, keeping all requests/retries attached to the
session. Fresh per-arm/draw identities do not prove a cold cache.

Sample size, confirmation token cap and wall allowance remain null until sizing.
Use pilot per-cell one-sided upper mean cost/wall estimates ×1.25 and the larger
99% resampled aggregate schedule estimate. Add pilot/control/exploration costs,
setup/teardown and a separately qualified inflight/cancellation reserve. With
one session at a time, sum all five cells' wall time. A statistical forecast
does not create a hard provider charge cap. Never reduce powered n to fit an
insufficient resource envelope. The old 5,400-session plan allowed only 3,703.70
tokens and 112 seconds per session; that arithmetic is verified, but the cited
13,806-token request came from a different invocation and was not a measured
minimum for this cohort.

Pilot-calibrate routine error/cancellation thresholds over rolling 20-session
blocks using conservative exact rate bounds and a .01 whole-run false-stop
allocation. Freeze finalization/reconciliation delays from pilot timing. Immediate
stops remain corruption, authentication/quota refusal, observed model/effort/config
drift, failed controls, ambiguous joins and insufficient resource reserve.
Null effort columns and recovered transient failures are not drift.

Use native Harbor cancellation, then only the owned recorded process group with
bounded interrupt/TERM/KILL escalation; verify local termination and reconcile
entry-gateway rows. Never stop gateways or unrelated sessions. Restore only the
owned 20129 settings snapshot. Unknown remote cancellation/trailing usage stays
unknown. None of this lifecycle work executes while drafting.

After quality gates, rank complete all-attempt total tokens, with the preregistered
1% tie preference C, D0, D1, A0, A1 and evidence of positive paired saving. Economic
guards use simultaneous bounds across candidates, rectangle corners and turn/
session strata. Incomplete, underpowered or weight-sensitive results retain C.

## Review repair dispositions

“Fixed by gating” means the protocol defect is repaired but an explicitly open
qualification result prevents sealing. It is not passed host acceptance.
PLAUSIBLE findings remain marked as unobserved where source inspection cannot
establish their occurrence. No whole finding was declined; the unsupported
request-size-only total usage bound in M9 was specifically declined.

| Finding | Disposition | Repair, verification and source |
| --- | --- | --- |
| B1 | fixed by gating | Canonical hop names fixed; retain Harbor option (b) with unresolved supported route, full prompt equivalence and live-200-max gates; compare three alternatives. Verified stripping in v0.23.0/main. Established namespace/route facts reused. PLAUSIBLE bare-name 401 not re-probed; no working route asserted. [Source 1](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/codex.py#L1339-L1449) [Source 2](https://github.com/harbor-framework/harbor/blob/3c82380859d187957cfd5cd64802b076d9779550/src/harbor/agents/installed/codex.py#L1502-L1605) [Source 3](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/providers/openai/codex-sdk.ts#L1034-L1134) [Source 4](https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/sdk/typescript/src/exec.ts#L91-L178) [Source 5](https://github.com/meridianlabs-ai/inspect_swe/blob/7eb8dd64309db4cd0f6bdf1d0ffd9786a74a4088/src/inspect_swe/_codex_cli/codex_cli.py#L483-L637) |
| B2 | fixed by gating | Merged semantic config, actual forced command, equal-arm deviations, host-network overlay/probe, admin containment gate and native [[steps]] mapping. Read loader/merge, Harbor upload/command/compose/multi-step code. WSL2 reachability and config equivalence unobserved, gated. [Source 1](https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/codex-rs/config/src/loader/mod.rs#L286-L340) [Source 2](https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/codex-rs/config/src/merge.rs#L56-L185) [Source 3](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/codex.py#L1339-L1449) [Source 4](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/environments/docker/docker.py#L350-L420) [Source 5](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/trial/multi_step.py#L25-L110) |
| B3 | fixed by gating | Pre-confirmatory pilot measures all cell costs/wall times; powered n, confirmation budget/reserve/wall fields now null pending sizing. Zero primes. Old arithmetic verified: 5,400 sessions, 3,703.70 tokens/session, 112 s/session. Historical 13,806-token row is a different invocation, not a measured lower bound for this cohort; no new host receipt read. [Source 1](https://github.com/scipy/scipy/blob/e4e854eaa8f18d807cd3496028e257e36caa93cc/scipy/stats/_resampling.py#L300-L394) [Source 2](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/trial/multi_step.py#L25-L110) |
| B4 | fixed by gating | Usage at entry only joined on X-Correlation-Id; upstream-hook observer specified; no hop summation. Request-body effort at both hops; nullable columns corroborate only. Verified call_logs schema/conditional effort and header emission; native Codex header export not found in inspected SSE path. Observer and second-hop exact join remain unqualified. [Source 1](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/usage/callLogs.ts#L90-L107) [Source 2](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/sse/handlers/chatHelpers.ts#L1172-L1184) [Source 3](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/usage/callLogs.ts#L628-L653) [Source 4](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/app/api/usage/call-logs/[id]/route.ts#L1-L22) [Source 5](https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/codex-rs/codex-api/src/sse/responses.rs#L30-L101) [Source 6](https://github.com/mitmproxy/mitmproxy/blob/6c09d56e4c29a92f5ad01b03199977584b8ea14f/mitmproxy/proxy/layers/http/_hooks.py#L7-L39) |
| B5 | fixed by gating | Paired net-harm bootstrap with explicit conservative exact fallback; 12 candidate intersection-union Holm tests, unrecovered failures, pilot power and null calibration. Recomputed reviewer's old-gate probabilities .003102/.306404/.784372; cited pinned bootstrap/exact/Holm code. No power result claimed without pilot. [Source 1](https://github.com/scipy/scipy/blob/e4e854eaa8f18d807cd3496028e257e36caa93cc/scipy/stats/_resampling.py#L300-L394) [Source 2](https://github.com/scipy/scipy/blob/e4e854eaa8f18d807cd3496028e257e36caa93cc/scipy/stats/_binomtest.py#L52-L115) [Source 3](https://github.com/statsmodels/statsmodels/blob/278ff9950636cdd4939b4055e339a8e681d79cab/statsmodels/stats/multitest.py#L99-L149) [Source 4](https://doi.org/10.1002/(SICI)1097-0258(19980430)17:8%3C891::AID-SIM780%3E3.0.CO;2-B) [Source 5](https://doi.org/10.1214/ss/1032280304) [Source 6](https://github.com/numpy/numpy/blob/c5ab79c14c98bfda1e60770ffa23a6130f8267b7/numpy/random/_generator.pyx#L299-L310). |
| M1 | fixed by gating | Registered-key D/A cells and TTL 60 are confirmatory; key name through env_key/extra_env templates only; reuse acceptance gated. Established host configuration reused; inspected principal/session and environment-template source, no key file access. [Source 1](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/liveZone.ts#L127-L132) [Source 2](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L1425-L1449) [Source 3](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/base.py#L560-L648) [Source 4](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/utils/env.py#L4-L65) |
| M2 | fixed | Sensitivity cache ratio [0,1], output ratio [1,10]; robust all-corner/turn guard without claiming actual prices or subscription meter. These ranges are explicit protocol assumptions over source-defined token components; actual price fields remain null. [Source 1](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/usage/callLogs.ts#L90-L107) [Source 2](https://github.com/scipy/scipy/blob/e4e854eaa8f18d807cd3496028e257e36caa93cc/scipy/stats/_resampling.py#L300-L394) |
| M3 | fixed by gating | Four native output-shape canaries with whole-string eligibility and native-reachability results; shell minifier nonreachability cannot count as engine acceptance. Verified shell/unified_exec headers and whole-string JSON.parse. MCP/custom shapes and actual engine application remain qualification results. [Source 1](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/engines/codexResponses/index.ts#L137-L145) [Source 2](https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/codex-rs/core/src/tools/context.rs#L524-L601) [Source 3](https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/codex-rs/core/src/tools/mod.rs#L97-L124) [Source 4](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/bodyAdapter.ts#L116-L145) |
| M4 | fixed by gating | Direct Chat key-2 collision stimulus rebuilt; assert multipart pin part unchanged; native Responses reachability and wire format independently gated. Source key construction/owner ordering/replacement verified. input_text bypass is source-supported concern; no native collision observed. [Source 1](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/engines/session-dedup/index.ts#L291-L345) [Source 2](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/bodyAdapter.ts#L116-L145) [Source 3](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/strategySelector.ts#L367-L386) |
| M5 | fixed | Reviewer/researcher style conclusions restricted to JSON-only records; no prose-verdict/evidence harmlessness claim. All 12 task schemas inspected; style catalog targets prose/code. PLAUSIBLE effect magnitude remains unmeasured; narrowed scope uses reviewer's alternative fix. [Source 1](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/outputStyles/catalog.ts#L32-L194) [Source 2](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L1425-L1449) |
| M6 | fixed by gating | Connection pin separated from session affinity; prompt_cache_key at both hops, account spread/cache reads by arm, prior false correction repaired. Header/body/fallback precedence verified. PLAUSIBLE account collapse not observed and not claimed; qualification required. [Source 1](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/sse/services/sessionAffinityPin.ts#L197-L221) [Source 2](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/executors/codex.ts#L1498-L1573) |
| M7 | fixed | Every session including C scores exact values; application/reachability is separate engine coverage, never exclusion or vacuous pass. Source allows no-op/ineligible engine paths; public document contract now explicitly defines both outcomes. [Source 1](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/engines/codexResponses/index.ts#L137-L145) [Source 2](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/strategySelector.ts#L367-L386) |
| M8 | fixed | Drop all separate priming and cold/warm labels; stratify measured cache analysis by turn. PLAUSIBLE lack of warming not established experimentally; native session/affinity source supports avoiding an unverified priming benefit. No cache-effect claim. [Source 1](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/sse/services/sessionAffinityPin.ts#L197-L221) [Source 2](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/executors/codex.ts#L1498-L1573) |
| M9 | fixed by gating | Pilot-calibrated operational stops; null usage intervals and worst-case ranking. Request size alone is declined as a bound on total input+output usage. Nullable input/output/reasoning schema verified. Routine error prevalence unmeasured. Require supported output/serialization caps as well as stored request size; without them cost gate stays open. [Source 1](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/usage/callLogs.ts#L90-L107) [Source 2](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/usage/callLogs.ts#L628-L653) [Source 3](https://github.com/scipy/scipy/blob/e4e854eaa8f18d807cd3496028e257e36caa93cc/scipy/stats/_binomtest.py#L52-L115) |
| M10 | fixed | Explicit ceiling: named synthetic task domains only, no production role migration or prose-record adoption. Six-task packets and four builder smoke cases inspected; narrower scope states the design's limitation without adding representative tasks. [Source 1](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/verifier/verifier.py#L165-L250) [Source 2](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/outputStyles/catalog.ts#L32-L194) |
| m1 | fixed | Replace Nine with Seventeen installed source files in correction log. Recomputed all 17 retained installed SHA256 bindings: 17 matched. No new live acceptance implied. [Source 1](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/usage/callLogs.ts#L90-L107) [Source 2](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/engines/codexResponses/index.ts#L137-L145) |
| m2 | fixed | Per-call tokens_compressed primary diagnostic; includes reactive compaction, not billed savings. Analytics optional, never additive. Inspected callLogs L107 and chatCore L1916-1919/L2164; source-backed attribution improvement. [Source 1](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/usage/callLogs.ts#L90-L107) [Source 2](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L1425-L1449) |
| m3 | fixed | promptfoo gateway example uses sharedgw/gpt-6-astra-max; Codex SDK alternate preserves the same one-slash slug. Verified provider model propagation and SDK --model code path; no promptfoo execution. [Source 1](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/providers/openai/responses.ts#L1195-L1210) [Source 2](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/providers/openai/codex-sdk.ts#L1034-L1134) [Source 3](https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/sdk/typescript/src/exec.ts#L91-L178) |
| m4 | fixed by gating | Require ambient OPENAI_API_KEY/auth-copy switches unset and use OMNIROUTE_FW_API_KEY template; verify no literal/partial secret logs. Harbor can inject OpenAI credentials and KEY-sensitive env handling verified. Presence checks and redaction runtime acceptance left to coordinator; no values opened. [Source 1](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/codex.py#L1339-L1449) [Source 2](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/base.py#L560-L648) [Source 3](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/utils/env.py#L4-L65) |
| m5 | fixed by gating | Responses->Responses sharedgw format specified; no Chat fallback; real encrypted/custom-item preservation gated. Adapter and pre/post-translation stage source inspected; configured/actual node format still unobserved. [Source 1](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L1425-L1449) [Source 2](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/bodyAdapter.ts#L116-L145) [Source 3](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/compression/strategySelector.ts#L367-L386) |
| m6 | fixed | Live-zone session fallback derived from request body/provider/connection is explicit and distinct from affinity extraction. Inspected chatCore L1868-1881 and sessionManager L103-145. [Source 1](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/sessionManager.ts#L103-L145) [Source 2](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L1425-L1449) |
| m7 | fixed | Tests now enforce canonical model hops and entry gateway ledger, plus all structurally checkable blockers. Before document repair: requested unittest command exit 1, 10 tests, 12 failures, including old L61/L122 expectations. [Source 1](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/agents/installed/codex.py#L1339-L1449) [Source 2](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/sse/handlers/chatHelpers.ts#L1172-L1184) [Source 3](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/usage/callLogs.ts#L90-L107) |
| m8 | fixed | Exploratory repetition unit explicit; keyed exploratory cell removed; original two builder steps are turns 1/2 and record step is turn 3. Pinned task.toml contains exactly create-file and append-content; native resume implementation inspected. Wrapper remains local integration, not unchanged upstream execution. [Source 1](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/examples/tasks/hello-multi-step-simple/task.toml#L15-L31) [Source 2](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/trial/multi_step.py#L25-L110) |

## Open sealing gates

- **runner-route**: Supported 20129 slashless route preserving canonical native metadata, five-item/full prompt equivalence and coordinator live 200 at max; C route equivalence too. No mapping has been found/qualified.
- **merged-profile**: Materialize/hash native semantic base+stack-worker merge; no profile/profiles keys; same resolved config and prompt-input versus -p reference before/after Harbor forced flags.
- **network-containment**: Hash extra_docker_compose overlay; prove actual container reachability and separately qualify upstream-supported containment of passwordless admin APIs; trusted-task constraints alone are not a security boundary.
- **header-capture**: Materialize/hash upstream-hook response-header observer, qualify privacy/SSE/cache semantics and X-Correlation-Id entry joins including failures; demonstrate a separate exact second-hop effort join.
- **effort-detail**: Qualify detail-API selectors and inspect only reasoning.effort at joined hops; null corroboration columns are allowed, missing body stays unknown.
- **two-hop**: Freeze Responses wire format and prove three native steps, genuine call IDs/encrypted reasoning replay, prompt_cache_key, session/account affinity and arm account spread/cache rate.
- **effective-config**: Read back C off/exclusions; keyed D/A engine/style plans, 60-minute live zone, optional dependencies and safety compaction. Existing key/TTL are facts, reuse is not accepted.
- **native-harnesses**: Harbor 0.23.0, Codex 0.157.1, chosen observer, statistics, actual task dependencies/images and exact build/config hashes through supported upstream commands.
- **native-controls**: Materialize/hash three-turn wrappers and graders; native known-pass/fail/malformed controls, four numeric output shapes, rebuilt Chat collision plus separately observed native reachability.
- **pilot-power-resources**: Complete excluded pre-confirmatory pilot; calibrate NI at margin, simulate power and operational stops; freeze powered n, complete token budget, reserve, wall time and schedule.
- **usage-sensitivity**: Confirm usage fields and finalization, missing-row input/output bounds, all-corner sensitivity and simultaneous cost bounds; actual dollar prices remain unknown.

Qualification inputs/ceilings must be frozen by the coordinator before live
qualification; confirmation inputs/schedule/resources only after excluded pilot
results. This document freezes neither. All open gate results are null, and
material changes after confirmatory data require a new cohort. Wider role/prose
adoption is outside this experiment's ceiling, not a gate this cohort can close.

## Local structural verification

The new tests ran before changing either protocol file. The requested command
with `PYTHONDONTWRITEBYTECODE=1`, `TMPDIR=/var/tmp/claude-431` and
`GIT_OPTIONAL_LOCKS=0` returned **exit 1**: `Ran 10 tests in 0.009s`,
`FAILED (failures=12)`. It rejected the old model/usage assertions and all missing
blocker contracts. Full sanitized returned output and subsequent acceptance
commands are retained in `repair_round_20260927.checks` in JSON.

After repair, the same contract command returned **exit 0**:
`Ran 10 tests in 0.011s`, `OK`.

The required broader command
`python3 -m unittest tests.test_osv_lockfile_coverage tests.test_blind_checkout tests.test_workflow_security_coverage`
returned **exit 1**: `Ran 57 tests in 24.869s`, `FAILED (errors=11)`.
All eleven errors are blind-export ancestor refusals: the requested
`/var/tmp/claude-431` also has an existing read-only `.git` directory. The guard
at `tools/sota-convergence/blind_checkout.py:970-973` checks its presence even
when empty. No metadata was removed and no test was weakened. The separate
`tests.test_blind_checkout.RepositoryClassificationTests -v` command returned
**exit 0**, `Ran 2 tests in 0.151s`, `OK`; there are no new unclassified strings.

`python3 scripts/validate.py` returned **exit 0**:
`{"components": 69, "hashed_files": 7348, "profiles": 4, "receipts": 159, "status": "passed"}`
and `Integrity and scope checks only; no live provider or GPU execution.`
`git diff --check` returned **exit 0** with no output. Every Python command used
the requested TMPDIR and bytecode suppression. Final post-record checks are
appended in the JSON round record; the failed broader run remains retained.

These are local structural/integrity checks, not Harbor upstream acceptance,
gateway probes, model trials or statistical power evidence. The coordinator
owns any hash re-registration and commit; no git metadata or evidence manifest
is written by this repair. Corrections, including the earlier false affinity
correction and the seventeen-file count, remain in the draft's anti-pattern log.
