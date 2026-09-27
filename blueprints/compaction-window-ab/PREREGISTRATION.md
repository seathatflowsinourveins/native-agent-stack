# Claude Workflow auto-compact window: matched A/B/C preregistration

**Status: DRAFT — not frozen, not run.** Written 2026-09-27, foundation lane.
The user chose “A/B test first,” followed by the best quality per token. The
planned start is immediately after the weekly reset on **2026-09-30 at 21:00
America/New_York (2026-10-01 01:00 UTC)**, subject to sealing and readiness.
This three-repetition pilot can nominate a candidate for confirmation only; it cannot authorize persistent host changes. This document does not
launch or schedule anything. [preregistration.json](preregistration.json) holds
the complete task packets, exact oracle specifications, controls and receipt
contract; the tables here are checked against it.

## Motivation and sources

[motivation-20260927.md](motivation-20260927.md) preserves the supplied historical
diagnosis: 52 Workflow children, 4,781 requests, 398,038,533 cache-read tokens,
largest context 936,520, thinking the largest transcript component, and 69% of
tool-result bytes in results over 5,120 bytes. These are historical measurements,
not a new run or an A/B result. Its combined input/cache-write value cannot be
split or priced retrospectively. Transcript bytes are not provider token counts.
Native identifiers are replaced by local ordinals; there were no personal paths
to preserve. The root input copy was removed.

Research and source inspection on **2026-09-27**, before artifact writing:

* Installed `claude --version` returned **2.1.283**; `claude --help` exposes
  `--autocompact <auto|tokens>`, `-p`, model and effort controls. The version's
  [pinned upstream changelog](https://github.com/anthropics/claude-code/blob/v2.1.283/CHANGELOG.md)
  was located through `gh api` and fetched with `ctx_fetch_and_index`. It includes
  Workflow fallback fixes, so resolved models must be observed in every attempt.
* [Model configuration](https://code.claude.com/docs/en/model-config#set-the-auto-compact-window)
  and [default thresholds](https://code.claude.com/docs/en/model-config#default-auto-compact-thresholds)
  document native 1M for Opus 4.7 and later on Anthropic API and Sonnet 5, with
  default auto-compaction around 967K. The plain-integer environment variable
  overrides the command, launch flag and saved setting. The identical launch
  flag `--autocompact auto` gives A the tuned default despite a saved window.
  `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` instead holds sessions to 200K; it must be absent.
* [Environment variables](https://code.claude.com/docs/en/env-vars),
  [Workflows](https://code.claude.com/docs/en/workflows) and
  [subagent compaction](https://code.claude.com/docs/en/sub-agents#auto-compaction)
  support a session-level design, but do **not explicitly establish inheritance
  of this exact variable by Workflow children**. Ordinary subagents share main
  compaction logic; extending that statement to this variable is an inference.
  A per-launch flag exists. A per-agent window field was not found in the
  installed help, changelog through this pin, or those documented configuration
  fields. This is a scoped finding, not exhaustive absence.
* [Native transcript examples](https://code.claude.com/docs/en/sub-agents#auto-compaction)
  use `compactMetadata.preTokens`; the
  [SDK schema](https://code.claude.com/docs/en/agent-sdk/typescript#sdkcompactboundarymessage)
  uses `compact_metadata.pre_tokens`. Mixing those field names would lose evidence.
* [Workflow caching](https://code.claude.com/docs/en/workflows#prompt-caching-in-a-fan-out)
  and [TTL precedence](https://code.claude.com/docs/en/prompt-caching#choose-the-ttl-yourself)
  document five-minute Workflow-child caching, including subscriptions. The
  coordinator can retain one-hour cache effects. Read model-specific weights
  from [official pricing](https://platform.claude.com/docs/en/about-claude/pricing),
  rather than assuming all cache reads have the same multiplier.

All web sources above were read through `ctx_fetch_and_index` on 2026-09-27;
live documentation is dated evidence, not a versioned implementation guarantee.
The source order was installed client, version changelog/pinned upstream record,
then official docs. No undocumented binary reverse engineering or model probe
was used to fill the inheritance gap.

The maintained reference implementation is the existing
[child usage reader](../../examples/claude-native/workflows/child-usage.mjs), with
[its tests](../../examples/claude-native/workflows/test-child-usage.mjs), at
`341ba64186b5631f52c11bd290a4f32fd405b7b1`. Reuse it unchanged for a transcript cross-check; the request ledger below is the cost instrument.
The document/test pattern extends
[token-adoption E2E](../../evidence/artifacts/token-adoption-e2e-20260926/README.md)
and [its contract tests](../../tests/test_token_e2e_preregistration.py), at that
same pin. Research-first discovery selected the installed search-first, tdd,
context-mode and verification-before-completion skills; this bounded extension
requires no package installation or replacement orchestrator.

## Arms and controls

| Arm | CLAUDE_CODE_AUTO_COMPACT_WINDOW | Expected threshold |
| --- | --- | --- |
| A | unset | about 967000 tokens |
| B | 400000 | 400000 tokens |
| C | 200000 | 200000 tokens |

The sole treatment difference is that variable. JSON arms contain only their
ordinal and environment patch; all other controls come from one shared object.
Every task/arm/repetition gets its own fresh `claude -p` coordinator and owned
worktree at the frozen revision. A deletes the selected variable from its
launch environment; B and C assign their plain integer. All launches include
`--autocompact auto --model claude-opus-5-5 --effort xhigh --output-format stream-json
--verbose` and the same sealed prompt/settings/MCP packet. These are proposed
launch arguments, not a command executed while drafting. Use the existing
Ultracode configuration, retaining coordinator xhigh and an explicit Workflow
stage. Every focal child is Opus 5.5/max with the named role. Sonnet 5/max is
allowed only for pure command wrappers; verification, build and judgment remain
Opus. No global effort override, fast mode, model fallback or 200K context hold.

Seal byte-identical agent definitions, task packets, token-lane carrier, MCP set,
deferred grants, native caching, permission policy and tool versions. Capture
resolved model/effort in every child. The carrier must actually appear in each
Workflow child's first prompt; Agent-tool acceptance does not prove that.
An inherited settings `env` block must not replace the intended arm value. A
conflict is a readiness failure, not permission to edit host settings.

Prove treatment with both sanitized launch evidence and **child** transcripts:
native `system/compact_boundary`, `compactMetadata.trigger=auto` and `preTokens`,
plus adjacent deduplicated request contexts. B and C each require an automatic
event in every focal child; all such events must be within the preregistered
bands B **360000–440000**, C **180000–220000**. These ±10% bands are an experiment
validity rule, not a claim that upstream guarantees that tolerance. A must exceed
400000; any A automatic boundary must be **870300–1000000**, around the documented
967K. An A child that finishes before compaction is right-censored, with no
invented 967K event. Manual compaction, missing treatment evidence, outside-band
events or a replacement child invalidate the run. Record all usage anyway.

## Fixed task bundles and independent checks

The four **proposed frozen** bundles in JSON are completely specified but are
not sealed by this draft. Every input derives from the literal Git revision,
not the current working tree. Sorted inventory hashes identify the exact 224
Python sources, 97 selected test modules and 26 Workflow files. Freeze those inventories,
task/oracle bytes and source captures before any capability probe or arm.

| Task | Existing task reused | Fixed workload and deterministic quality checks |
| --- | --- | --- |
| builder | `seed-builder-1` isolation contract | One child reviews 250 sources and test-first adds `compactionSummary(rows)` to the existing native usage reader. B1 checks actual base, allowed paths and red-before-green chronology with unchanged existing tests. B2 checks all literal JSON vectors, purity and exact original source coverage. |
| web | `seed-web-table-2` facts and table oracle | One child reviews all 319 primary CPython library pages through `ctx_fetch_and_index`. W1 checks exact source inventory, captures and module declarations. W2 checks JSON/pathlib facts, citations, typed rows 5–12 and latency sum. |
| verification | `seed-acceptance-5` command and oracle | One child inspects and runs 97 candidate offline test modules in two fixed ordered rounds, then the inherited partition command and validator. V1 compares all 194 actual command results with the frozen list; V2 requires the original partition result and validator status. |
| review | `seed-review-diff` unchanged patch oracle | One child reviews 250 sources and the original 52,631-byte patch. R1 checks source/AST inventories and deduplication/failed-attempt facts; R2 requires 31 hunks, 166 additions, 581 deletions and the exact interrupt-contract facts. |

All inherited ids refer to the
[existing preregistration](../../evidence/artifacts/token-adoption-e2e-20260926/preregistration.json).
The short historical tasks alone do not recreate expensive long children. These
are explicitly expanded bundles, not unchanged historical executions. Their
ordered source checkpoints concern distinct real files/pages; no repeated
context padding or dumping long tool output is allowed. The builder is a real
accounting feature based on the existing reader and documented native event
schema; the experiment never uses its candidate code to measure its own result.

The web corpus is [python/cpython v3.13.15](https://github.com/python/cpython/tree/v3.13.15/Doc/library),
peeled via `gh api` to commit `4061bc4c35f7c26f25264666d4ba083b93d2f6f9` on
2026-09-27: 319 `.rst` pages, 6,905,092 source bytes. The task uses commit-pinned
raw URLs and original blob identities, not mutable documentation pages. Its
JSON/pathlib checks extend the repository's existing Python-tooling research.
Every arm starts an empty task-scoped Context Mode index; no arm sees another
arm's answers or retained retrieval state. Acquisition refusal, missing source
bytes or changed content cannot silently shrink the corpus.

Each bundle stays in **one persistent focal child**, across natural automatic
compactions. Long input bytes or many commands cannot guarantee retained context,
especially with max-effort variability and output containment. Qualification
therefore requires **all 12 A focal children to exceed 400000 actual prompt
tokens**. No eligible claim is made before observation. If even one does not,
stop and report **incomplete**, keeping its checks and cost; do not replace it,
increase its work, or select only the long repetitions. A larger workload needs
a dated amendment and a fresh cohort. The strict bands also require B/C to have
actually exercised their lower window. This prevents a short-task comparison
from answering a question about the long-child cost population.

The verification subset excludes the 93 original modules whose source matches
the fixed skip-marker expression in JSON; its 97-module inventory hash is fixed
now. This conservative selector also excludes markers in test strings. It does
not establish dependency readiness or rule out indirect skips. No module may be
added or dropped after model observations. W2 citations are checked by literal
substrings in bounded original RST spans; R1 citations must cover specified
original source lines. There is no subjective citation-support scoring.

Quality covers the frozen behavioral, extraction and accounting checks. It is
not a blinded broad judgment of all review prose. The graders are pinned to
**Inspect AI 0.3.271**, using upstream `inspect_ai.scorer.match(location="exact",
ignore_case=False, numeric=False)` over SHA256 digests of canonical typed
observed/target records. Comparing digests prevents the scorer's whitespace
normalization from weakening literal JSON/string checks. No model grader is
used. The thin adapters must derive facts from independent original artifacts
and process captures; a model's `passed` field cannot supply truth. Inspect
scores exported native results offline; **do not use inspect_swe's Claude Code
bridge**, which changes launch defaults/context-window selection.

`oracle_framework` in JSON materializes all eight adapter **contracts** and
**32 hashed synthetic control fixtures**, one known-pass, known-fail, malformed
output and missing output for each check. Every control binds its complete
input and target; each contract binds the full original check procedure,
expected result and required fields. Hashing uses UTF-8 JSON with sorted keys,
compact separators, ASCII escapes, no NaN and no final newline. A malformed
record feeds an invalid marker to the same scorer and must receive `I`;
missing independent source evidence blocks readiness, never passes.

| Check | Independent adapter inputs | Known-fail control |
| --- | --- | --- |
| B1 | Git base/diff, actual red/edit/green chronology and original test bytes | Red run follows the edit |
| B2 | Candidate module results on frozen vectors and immutable source coverage | Input mutation |
| W1 | Original RST blobs and native fetch captures | Empty page coverage |
| W2 | Typed original rows, facts and bounded original citation spans | String latency instead of integer |
| V1 | Actual module command captures and ordered round inventory | Zero tests despite exit 0 |
| V2 | Frozen event bytes, partition/validator output | Nonzero partition exit despite a passing summary |
| R1 | Original Git/AST inventory and pinned reader spans | Failed-attempt usage excluded |
| R2 | Original patch and unchanged-worktree observation | 30 hunks instead of 31 |

These fixtures exercise the proposed scorer boundary; reduced synthetic
coverage is explicitly **not** a passing full-corpus extraction test. Full
artifact adapters are still unmaterialized (`executable_sha256: null`), their
pinned Inspect controls are unrun, and the installed package is **0.3.266**.
A source-backed contract does not close that runtime gap. Before sealing,
materialize and hash each executable adapter, exercise native-artifact positive,
negative, malformed and missing-output cases through its entire extraction path,
and retain actual Inspect 0.3.271 results. Also establish readiness of the
unchanged 97-module offline subset. No unsuitable module may be dropped. This
round does not install packages or substitute local structural tests for those
upstream scorer runs.

## Replication, order and cache

Three repetitions per task per arm give **36 attempts**, sequentially, with a
fresh process, worktree and task index for each. Task order rotates by repetition
as specified in JSON; within each task block the arm orders are:

| Task | Repetition 1 | Repetition 2 | Repetition 3 |
| --- | --- | --- | --- |
| builder | ABC | BCA | CAB |
| web | ACB | CBA | BAC |
| verification | BCA | CAB | ABC |
| review | CBA | BAC | ACB |

Each arm occupies each position once for every task; each of the six orderings
appears twice across the design. Wait **360 seconds** after the prior attempt's
last request and process-group termination before the next launch. Child TTL
must be five minutes, with no other Claude usage during the experiment. Record
first-request cache reads; do not equate a fresh process with a cache miss.
Within-child caching stays native. Coordinator cache can last one hour and is
reported separately from the child-only cost estimand. Worktree path differences
can also affect prefix reuse and are recorded as a limitation, not a saving.

The sample-size claim is reduced to an **exploratory frozen-suite pilot**.
Three repetitions provide position balance and an observed range; they do not
establish statistical quality non-inferiority, repeatable 10% savings or a
confidence level. No independent estimate of paired cost variance exists.
Variation can come from max-effort output, tool trajectories, compaction and
cache reuse. The paired unit is task × repetition; four different tasks are not
four extra independent repetitions of any one task.

For scale only, [NIST's t-interval](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm)
for independent approximately normal paired relative differences has half-width
`t(0.975, n-1) * s_d / sqrt(n)` at two-sided 95% confidence. With `n=3`, this is
`4.303 * s_d / sqrt(3) = 2.484 * s_d`: even a 0.10 half-width would require
`s_d <= 0.0403`, which has not been measured. This is an illustration, **not**
a confidence interval for the failure-inclusive ratio of cost sums to successes,
and not a power calculation. There is no justified confirmatory repetition
count or claimed confidence level in this draft.

Report all paired costs/check outcomes and ranges; recompute the same ranking
leaving out each whole repetition block in turn, preserving all arms/tasks.
A changed ranking or lost margin is unstable. That sensitivity check cannot
turn a pilot ranking into adoption evidence. Confirmation requires independent
variance/failure data and a new preregistered cohort, with precision and
simultaneous inference matched to the ratio-per-success estimand and all
candidate/per-task gates. Keep this cohort and its failures as pilot evidence.

## Measures and decision

Follow [token-practice scopes](../../docs/token-practice.md): every metric in JSON
names its source, observation window and denominator. The authoritative
instrument is **native Claude Code OTel `api_request` events → the existing
host collector → Loki**, with `api_error` and `api_refusal` events for coverage.
Use the native request's input/output/cache-creation/cache-read counters, mapping
OTel `cache_creation_tokens`/`cache_read_tokens` to the transcript category names.
Per-request context is input + cache creation + cache read; cumulative cache
reads measure cost, not context size.

Query Loki's `GET /loki/api/v1/query_range` every second with the sealed owned
session selector and overlapping time intervals. Fully page/split truncated
responses, retain query/arrival timestamps and re-query the complete interval
at shutdown. A missing page is missing evidence. **Deduplicate by provider and
request ID**: identical retransmissions count once; conflicting duplicate
counters stop the comparison. Distinct provider request IDs in one retry chain
count separately. Join error/refusal rows by request ID without adding their
counters a second time. Do not deduplicate by message ID, timestamp or text.

Join native transcript request IDs and the session/Workflow/agent lineage to
one owner per request. Include **compaction, background preparation, retries,
refusals, fallbacks and failed/interrupted attempts**, even when an assistant
message is absent. A compaction boundary is treatment evidence, not a token
record. Check the resolved model and refusal `server_fallback_hop`; any fallback
invalidates the matched comparison while its usage remains in the budget.
Unattributed requests stay in the whole-run ledger and prevent child-cost
selection. Missing counters or unreported failed-request charge remain unknown.

After settled exit, reconcile each owned session using **ccusage v20.0.26**:
`ccusage claude session --id "$SESSION_ID" --json --offline`. Prove which child
transcripts are included before comparing the same model/category scopes.
Require `OTel = ccusage + OTel-only - ccusage-only`, enumerating every residual
by private request ID and original evidence. Fully metered OTel-only compaction
requests can legitimately lack transcript rows; unexplained residuals cannot.
The unchanged baseline `child-usage.mjs` supplies an additional attribution
cross-check. **Never add ccusage, transcript totals or /usage to OTel totals.**
Equal totals alone do not prove that both instruments captured every request.

The repository collector template currently drops request/client/agent IDs.
Its active host configuration and retained native joins have not been observed
in this repair. Required-ID preservation is therefore an explicit launch gate;
no host configuration is changed and session aggregates are no substitute.

Retain input, cache creation, cache read and output separately. The primary cost
is the all-attempt weighted total divided by successful tasks, for each task and
pooled within the arm. A task succeeds only if both frozen checks pass. Include
failed attempts in the numerator; zero successes makes the ratio undefined.
Thinking is already part of output, so do not add it again. These dated standard
API dollar-equivalent weights are a common token-cost proxy, not subscription
charges or a conversion of weekly `/usage` percentages:

| Model | Input / million | 5m write / million | Read / million | Output / million |
| --- | --- | --- | --- | --- |
| Opus 5.5 | $4 | $5 | $0.20 | $20 |
| Sonnet 5 | $2 | $2.50 | $0.20 | $10 |

Thus `W = sum_models((pI*I + pW*Wcache + pR*R + pO*O) / 1000000)`.
Normalized weights are Opus **1, 1.25, 0.05, 5**, Sonnet **1, 1.25, 0.1, 5**;
only the dollar-equivalent total combines models on one basis. Source:
[official pricing, read 2026-09-27](https://platform.claude.com/docs/en/about-claude/pricing).
Fast mode, other models, one-hour child writes or unresolved usage invalidate
this fixed price comparison. Neither model has a >200K price premium in this
price sheet. Coordinator-only requests, native tool savings estimates and quota
readings have separate scopes and are not added to overlapping child totals.

Record every compaction's trigger, its pre-compaction size (the native
preTokens field), the context size of the requests before and after it, and
the per-child maximum. Supervisor monotonic time gives attempt wall
seconds through full shutdown, with child duration separately corroborated by
the journal. Report failed/interrupted time, all-attempt time per success, and
scheduled elapsed time including washouts separately.

The following contract table is checked literally against JSON:

| Key | Value |
| --- | --- |
| default_approx_tokens | 967000 |
| B_window_tokens | 400000 |
| C_window_tokens | 200000 |
| long_child_prompt_tokens_exclusive | 400000 |
| cost_reduction_min_fraction | 0.1 |
| repetitions_per_task_arm | 3 |
| washout_seconds | 360 |
| run_budget_tokens | 1000000000 |
| ledger_poll_seconds | 1 |
| quality_rule | For every task and check, any pass in A requires a pass in every repetition of the candidate. |
| pass_count_rule | Candidate total passed checks and successful tasks must each be at least A's totals. |
| cost_rule | All-attempt weighted child cost per successful task must be at least 10% lower than A, both pooled and for each task. |
| selection_rule | Among quality-eligible candidates meeting the 10% pooled and per-task cost margin versus A, choose the unique lowest pooled all-attempt weighted child cost per successful task; an exact cost tie yields no selection and retains A. |
| incomplete_rule | Any stopped, invalid, underlength, or unmeasured run is incomplete; no adoption result. |

All 36 attempts and independent checks must be available with valid treatments,
controls and complete accounting before applying this **descriptive pilot**
rule. Ordinary completed failures remain in the numerator; every compared
arm/task needs a success. Candidates must pass the observed quality gates and
cost at most **0.90 times A**, for every task and pooled. Then minimize pooled
all-attempt weighted child cost per success among eligible candidates, using
unrounded exact decimal/rational arithmetic. There is no B/C priority and no
extra margin between them. An exact tie for the lowest cost gives **no
selection**, retaining A. Rounded display equality is not an exact tie.

At equal quality, `A=100, B=60, C=89` selects **B**; `A=100, B=89, C=60` selects
**C**. If `B=C=60`, neither wins the tie and A is retained. `B=91, C=95` fails
the minimum effect; B=60 with a quality regression cannot beat eligible C=89.
These examples apply to every task as well as pooled cost. They are arithmetic
controls, not model observations.

A selected pilot candidate only informs a separately preregistered confirmatory
cohort; it does not authorize persistent adoption. An incomplete run has no
comparative result. No best-of selection, imputation, arm-dependent repair or
replacement attempts. Preserve every failure. Changed client/model/TTL/carrier
or contradictory independent results require a dated amendment and new cohort;
anecdotes or selectively rerun winners cannot validate this one.

## Budget and stops

The proposed ceiling is **1,000,000,000 native tokens**, summed as input + cache
creation + cache read + output over all deduplicated **owned** requests,
including readiness, coordinators, children, compaction/background work,
wrappers, retries, failures, refusals and fallbacks. This is a fixed proposed
resource ceiling, not a conversion from the superseded weekly-percentage cap,
a subscription billing guarantee, or evidence that 36 attempts fit.

Keep `/usage` **before readiness and after settled shutdown only as a
descriptive cross-check**, with bucket/reset/reading-age metadata. Missing or
cached values stay unknown; they do not drive cancellation. Do not sum
overlapping weekly buckets or use them to infer token charges.

The observer polls the request ledger each second (`P=1`). Before each launch,
require `observed_tokens + outstanding_reserve_tokens < limit_tokens`; cancel
when the sum reaches the limit. Stop scheduling on any counter/ID gap, failed
query, truncation, unexplained residual, control drift, usage-limit error or
observer/watchdog failure. No unmetered calibration request is permitted.

The preregistered conservative reserve formula is:

`reserve = R_max * (N_active_max + ceil(lambda_max * (L_bound + P + K_bound)))`

`R_max` bounds all four token categories for any permitted provider request;
`N_active_max` bounds simultaneous active requests across coordinator, child,
background and retry paths; `lambda_max` bounds request completions per second
with bursts covered; `L_bound` bounds completion-to-observer delivery/query
lag; `K_bound` bounds stop-trigger-to-last-request admission. The reserve must
cover **full server-accepted requests**, including charge after client exit.
One coordinator/one child does not bound background requests. These quantities
need enforceable upstream/admission evidence, not observed averages or a guessed
output cap. A native pre-admission reservation that accounts for all unreported
requests could replace the formula only by a new explicit amendment.

Reporting lag is **unmeasured: null, zero samples**. The prescribed measurement
joins original request completion/OTel timestamps to first query-visible Loki
arrival, recording clock uncertainty and min/p50/p95/max for ordinary and hidden
request paths. The documented five-second log export interval is **not** a
measured lag or worst-case delivery guarantee. Sample maxima cannot establish
`L_bound`; exporter retries can outlast them. No historical session or host
record is inspected or invented here to fill that gap.

For a future qualified launch, the supervisor uses CPython
`Popen(..., start_new_session=True)`, recording PID, PGID, start identity and
owned descendants. On a trigger it latches stop, verifies ownership and sends
`os.killpg(pgid, SIGTERM)`, waits at most five seconds, then sends `SIGKILL` to
surviving owned members. Reap and independently verify the group is gone;
never signal unrelated processes or the collector. Escaping descendants block
readiness. Keep the observer alive to drain late events and reconcile ccusage;
client death does not prove server work or charge stopped. An offline disposable
process test must qualify membership, escalation, durations and observer
survival before sealing. None was run in this repair.

**A proven hard cap is not supported yet.** Request admission/rate/concurrency,
delivery and cancellation bounds, the measured lag and reserve are all
unqualified; `reserve_tokens` remains null and the action is **do not launch**.
OTel post-response monitoring alone cannot bound future in-flight charge. This
repair removes the fictitious percentage reserve and specifies the token stop
procedure without claiming it is now safe to execute.

After eventual qualified shutdown, drain for at least the proven delivery
bound and take two complete ledger snapshots one polling period apart plus
ccusage reconciliation. Stable snapshots alone do not establish no lost events.
Retain unresolved charge as unknown and the run as incomplete. Attempt and
whole-run wall limits remain 7200 and 259200 seconds. Preserve every stopped
attempt; never resume, replace or increase the ceiling within this cohort.

## Evidence and receipt shape

Apply [acceptance-evidence-policy](../../docs/acceptance-evidence-policy.md).
This draft, its contract test and the repository validator are **structural
validation**. Version/help is installation inspection. Future observed native
launches/compactions are **upstream examples or native operations**, with dated
primary references. Task adapters using pinned Inspect scorers are **local integration checks**; the new
builder vectors are **synthetic fixtures**. A separate observer's original
artifact, process and oracle readback is **independent observation**. No local
test is promoted to an unchanged upstream test or a completed provider run.

A future sanitized receipt contains the seal/input/configuration hashes and
chronology; arm/task/repetition ordinals; requested/resolved client/model/effort;
selected window/unset marker; each check's result and oracle/output hashes;
command/exit/bounded returned result; four usage counters by model and their
denominators; weighted cost; every compaction and adjacent context sizes;
wall times; request-ledger and reconciliation hashes; measured lag, reserve proof and cancellation records; before/after value-only `/usage` observations/reset; failures, interruption and
unknown fields; evidence classes, sanitizations and independent readback.
Allowed statuses are `not_run`, `incomplete`, `complete_no_change` and
`complete_candidate_selected`; the last denotes a pilot nomination only. An arbitrary `passed` flag is not evidence.

Original conversations, complete tool output, source captures and native ids
stay private. Publish no sessions, native run/agent/message ids, personal paths,
credentials, sign-ins, or environment dumps. Use ordinal labels and digests;
retain actual sanitized command output, not only generated summaries. Independent
readback must corroborate both native execution and the frozen oracle outcomes.
Offline positive/negative oracle controls must reject empty, wrong and missing
data before any arm is launched.

## Sealing and Amendments

Follow [retrieval-quality-v2 Sealing](../retrieval-quality-v2/PREREGISTRATION.md#sealing)
and [token-adoption E2E Sealing](../../evidence/artifacts/token-adoption-e2e-20260926/README.md#sealing).
The table below retains the **original draft candidate byte identities**,
superseded by the repair Amendment below. It does not freeze
this DRAFT, establish chronology, or authorize execution. There is no result.
The existing evidence manifest records the original draft hashes. The coordinator must refresh all three changed file registrations after integrating this repair; that shared manifest is outside this builder's three-file ownership.

| Artifact | SHA256 |
| --- | --- |
| `preregistration.json` | `4a4f08e172dd95ca2998e9a39a6dbebf38dc605f10859d714a1779ca8249ef1b` |
| `motivation-20260927.md` | `7e9b224ddb2874cf4836a7ff1d113c7c6c8abb001a1c64d4b4686e9ac907a365` |
| `../../tests/test_compaction_window_ab_preregistration.py` | `47f04aee9892437b3add023c4cf764056bb6af3c2af4a7f09d75b70b76ae30dd` |

Before running, materialize and hash exact inputs, prompts, original page bytes,
independent oracle adapters, agent definitions, carrier and sanitized MCP/runtime
fingerprints. Qualify every oracle offline with correct and discriminating
wrong/malformed/missing inputs using Inspect 0.3.271. Freeze the native request instrumentation, prove active collector ID preservation, and qualify measured lag, an enforceable outstanding-token reserve and owned cancellation. Runtime inheritance is evaluated inside each sealed attempt, not
claimed from a pre-seal model probe. Record a separate
seal commit and actual merge revision/time, with independent ordering evidence
showing that sealing preceded **all** native probes and arms. Rehash before each
launch; a mismatch stops it. Hash equality alone proves bytes, not ordering.

Any subsequent change requires an **append-only, dated Amendment section**.
Preserve prior amendments and tables; name superseded artifacts/rules, explain
why, state whether results were already observed, and provide replacement hashes
and merge/execution chronology before execution. Never silently revise thresholds,
eligibility, workload or failed outcomes. A change after model observation needs
a new cohort and retains the old failed/incomplete record. The sealing amendment
must explicitly change the draft status; this commit leaves it DRAFT.

## Draft validation and unresolved gates

Research for the one repair round, **2026-09-27**, before repairs: the supplied
`gpt6-review.md` (SHA256 `f27867d62728615952804aa8e04cd540ab0e63ce199545d4893883f0d7c18e2c`)
and W9 in `report2.md` (SHA256 `b5d204ebe070c26b64fe06ea4726181ad695f7f9e4abd7bc41b6b34dcd2ed5a6`)
were checked against primary sources. Reuse the review's installed Claude
2.1.283/changelog inspection; no new Claude session was started.

* Metering: [native API request events](https://code.claude.com/docs/en/monitoring-usage#api-request-event),
  [Loki query API](https://grafana.com/docs/loki/latest/reference/loki-http-api/),
  and [ccusage v20.0.26 session reports](https://github.com/ccusage/ccusage/blob/v20.0.26/docs/guide/session-reports.md).
  The repository [collector template](../../observability/collector/collector.yaml)
  currently omits `request_id`, `client_request_id` and `agent_id` from its
  attribute allowlist. The existing host collector is the intended route;
  the template is not proof that its active Loki records preserve these fields.
* Grading: [Inspect 0.3.271 scorers](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0.3.271/docs/scorers.qmd)
  and its [match implementation](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0.3.271/src/inspect_ai/scorer/_match.py).
  Package metadata of the existing installation reports **0.3.266**; this round
  does not install or substitute that version for the requested pin.
* Skill discovery: the [Inspect skills directory](https://skills.sh/meridianlabs-ai/inspect-skills)
  and [v0.4.5 source](https://github.com/meridianlabs-ai/inspect-skills/blob/v0.4.5/README.md)
  offer package selection and log analysis, not these task oracles. No skill
  installation closes the adapter gap. The installed search-first, find-skills,
  tdd and verification-before-completion skills guide this bounded repair.
* Cancellation follows [CPython's pinned process interface](https://github.com/python/cpython/blob/4061bc4c35f7c26f25264666d4ba083b93d2f6f9/Doc/library/subprocess.rst).
  Precision reasoning uses the [NIST confidence-interval reference](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm).

Native web open/search was unavailable in this environment; primary documents
and pinned sources were fetched with Context Mode instead. A guessed Inspect
`_exact.py` URL returned 404; the pinned package exports and `_match.py` resolved
the actual scorer interface before any adapter contract was written. No new
runtime, installation, host setting or experiment is part of this repair.

Draft-authoring anti-pattern log, **2026-09-27**, before any model observation:

| Mistake | Verification and correction |
| --- | --- |
| Requiring zero skips in all 190 modules | At the frozen revision, `tests/test_gitleaks_guarded_macos.py:95` and `:110` contain complementary platform skips, making that condition impossible. Freeze the 97-module subset above instead; its readiness remains untested. |
| Treating source-support prose as a deterministic check | Inspection of the pinned CPython source and `child-usage.mjs:458`, `:460`, `:542` established literal/span predicates. W2 and R1 now use those explicit predicates. |

The contract test was written first and run before either preregistration
artifact existed: `rtk python3 -m unittest discover -s tests -p
test_compaction_window_ab_preregistration.py -v`, exit **1**, one expected failure
on the missing JSON artifact. This establishes the red step only; it was no
Claude session. Original draft structural results are retained separately in
[build-evidence.json](build-evidence.json); they do not validate this repair.
The new red/green output is recorded in the Amendment below.

Open gates are Workflow inheritance/treatment observation, native request-ID/child joins, measured lag and a proven outstanding-token bound, actual >400K task eligibility and budget feasibility, offline-suite readiness, resolved host fingerprints and executable Inspect adapters with returned control evidence. The source
findings above do not settle these runtime questions. They do not justify any persistent host setting change; this pilot requires separate confirmation even after a complete result.


## Amendment 2026-09-27 — one repair round, still DRAFT

No model results were observed and no Claude session was launched. This
amendment supersedes the original weekly-percent cap, transcript-primary cost
instrument, C-first choice, unspecified grader/control framework and the
three-repeat adoption scope. It preserves the original task packets, arm
windows, common launch controls and ordering. Source identities and the
research disposition are recorded above and in JSON. The original candidate
hash table remains historical; current byte identities follow this repair
record. This is not a seal, merge receipt or execution authorization.

| Review finding | Disposition | Repair and remaining evidence |
| --- | --- | --- |
| Blocker: hard cap lacks observation, cancellation and outstanding-charge bound | **Not supported as a proven hard cap** | Replaced weekly percentages with the 1,000,000,000-token all-owned ledger budget; specified polling, ownership-checked TERM/KILL, late-event settlement and an explicit conservative reserve formula. Actual reporting lag, enforceable request/delivery bounds and cancellation observations are unavailable in this no-session round. They remain null and launch remains prohibited; a five-second export interval cannot fill them. |
| High: compaction/background/retry/refusal/fallback accounting has no request instrument | **Fixed at protocol level** | Native OTel request events through the existing collector into Loki, provider/request-ID deduplication, private child/Workflow joins, model/fallback checks, and ccusage v20.0.26 per-category residual reconciliation now define one authoritative ledger. Active ID preservation and complete-path qualification remain open; the repository collector template drops required IDs. |
| High: C can beat cheaper B at equal quality | **Fixed** | Minimize pooled all-attempt weighted child cost per success among observed non-inferior arms meeting the 10% per-task and pooled margin; exact tied minima yield no selection. The A=100/B=60/C=89 counterexample now selects B. |
| High: executable oracle adapters and controls lack qualification | **Not supported as executable readiness** | Pin Inspect 0.3.271 scorers; define eight independent adapter contracts and 32 hashed known-pass, known-fail, malformed and missing-output fixtures. Full extraction adapters and their actual pinned-scorer control outputs remain absent; installed 0.3.266 is not substituted. Structural fixture/hash checks cannot establish these or the fixed 97-module suite's readiness. |
| Medium: three repetitions have no precision/stability justification for 10% | **Fixed by narrowing the claim** | Three repeats are an exploratory frozen-suite pilot only. State the missing variance, paired unit and illustrative 95% t half-width; prescribe block-deletion sensitivity. No claimed confidence, confirmatory sample size or persistent adoption follows from this design. |

Each proven mistake and its correction is appended to JSON's `anti_pattern_log`.
No unresolved runtime gate is represented as passing because a structural test
passes.

Fail-first command, before the JSON/protocol repair:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_compaction_window_ab_preregistration.py -v
exit code: 1
```

Bounded actual returned output (tracebacks and local paths omitted):

```text
test_budget_uses_native_tokens_and_does_not_invent_a_charge_bound (test_compaction_window_ab_preregistration.CompactionWindowPreregistrationTests.test_budget_uses_native_tokens_and_does_not_invent_a_charge_bound) ... FAIL
test_draft_contract (test_compaction_window_ab_preregistration.CompactionWindowPreregistrationTests.test_draft_contract) ... FAIL
test_inspect_oracle_contracts_have_hashed_discriminating_controls (test_compaction_window_ab_preregistration.CompactionWindowPreregistrationTests.test_inspect_oracle_contracts_have_hashed_discriminating_controls) ... FAIL
test_request_ledger_covers_hidden_requests_and_reconciles_once (test_compaction_window_ab_preregistration.CompactionWindowPreregistrationTests.test_request_ledger_covers_hidden_requests_and_reconciles_once) ... FAIL
test_selection_optimizes_cost_instead_of_arm_order (test_compaction_window_ab_preregistration.CompactionWindowPreregistrationTests.test_selection_optimizes_cost_instead_of_arm_order) ... FAIL
test_three_repetitions_are_an_exploratory_pilot_not_adoption_evidence (test_compaction_window_ab_preregistration.CompactionWindowPreregistrationTests.test_three_repetitions_are_an_exploratory_pilot_not_adoption_evidence) ... FAIL
Ran 6 tests in 0.003s
FAILED (failures=6)
```

The five finding-specific checks failed respectively on absent budget,
request-ledger, oracle and precision contracts and the incorrect C-first rule.
The existing aggregate contract also rejected the changed threshold contract.
These failures predate the repairs; fixture hash checks remain structural,
not executions of the proposed Inspect graders.

The first post-repair structural run used the same command, exit **0**:

```text
Ran 6 tests in 0.009s
OK
```

The required publication command was run, exit **1**:

```text
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate.py
Publication validation failed:
blueprints/compaction-window-ab/PREREGISTRATION.md: SHA-256 mismatch
blueprints/compaction-window-ab/PREREGISTRATION.md: byte count mismatch
blueprints/compaction-window-ab/preregistration.json: SHA-256 mismatch
blueprints/compaction-window-ab/preregistration.json: byte count mismatch
tests/test_compaction_window_ab_preregistration.py: SHA-256 mismatch
tests/test_compaction_window_ab_preregistration.py: byte count mismatch
```

These are the three edited files' stale registrations in the shared
`manifests/evidence.json`, which this builder did not edit. The coordinator must
register their final SHA256/byte counts and rerun `python3 scripts/validate.py`
before committing. The validator is **not passing** in this worktree; no
upstream scorer run or new native acceptance is claimed by the six local tests.

Current repair candidate identities (not a freeze):

| Artifact | SHA256 |
| --- | --- |
| `preregistration.json` | `2d335e15a0d0de7bdacd6421261a2cad83971bbd9053450be0b917c42975730c` |
| `../../tests/test_compaction_window_ab_preregistration.py` | `4bc86a6aa52d014e29ace37e25ab74c564b4984d3d20534aae21be39d6ffb155` |

The coordinator records this Markdown's final digest externally to avoid a
self-hash. Open runtime gates are native request-ID preservation and complete
child attribution, measured lag and enforceable outstanding-charge bounds,
owned-process cancellation qualification, full Inspect adapter/control
execution, the unchanged offline suite, and treatment/host fingerprints.
Three repeats remain a pilot even if those gates are later satisfied.
