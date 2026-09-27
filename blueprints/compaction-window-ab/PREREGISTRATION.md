# Claude Workflow auto-compact window: matched A/B/C preregistration

**Status: DRAFT — not frozen, not run.** Written 2026-09-27, foundation lane.
The user chose “A/B test first,” followed by the best quality per token. The
planned start is immediately after the weekly reset on **2026-09-30 at 21:00
America/New_York (2026-10-01 01:00 UTC)**, subject to sealing and readiness.
No host setting changes precede an accepted result. This document does not
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
`341ba64186b5631f52c11bd290a4f32fd405b7b1`. Reuse it unchanged for measurement.
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
not a blinded broad judgment of all review prose. Oracle specifications and
literal expected values are written now; executable adapters must be sealed and
shown to reject wrong/missing outputs offline before a run. No result can rely
on an unimplemented oracle or the model's own `passed` field. The frozen
verification subset must be runnable without provider calls or host
changes; an unsuitable module blocks readiness instead of being omitted.

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

## Measures and decision

Follow [token-practice scopes](../../docs/token-practice.md): every metric in JSON
names its source, observation window and denominator. Per-request context is
uncached input + cache write + cache read; cumulative cache reads are cost,
not context size. Use the sealed `child-usage.mjs` `by_resolved_model` once for
each Workflow, including superseded/failed/interrupted attempts. Never add its
child rows, its per-model rows and its aggregate together. Audit missing fields
independently: the reader's zero defaults do not establish complete usage.
Native message ids are only private deduplication keys, never receipt fields.
Reconcile compaction-generation requests and provider retries explicitly. If
their usage is missing from the sealed accounting, report observed counters
with an unknown remainder and an incomplete comparison; do not treat that
missing cost as zero or fill it with an overlapping coordinator total.

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
| weekly_usage_cap_percentage_points | 20 |
| weekly_usage_cancel_percentage_points | 18 |
| quality_rule | For every task and check, any pass in A requires a pass in every repetition of the candidate. |
| pass_count_rule | Candidate total passed checks and successful tasks must each be at least A's totals. |
| cost_rule | All-attempt weighted child cost per successful task must be at least 10% lower than A, both pooled and for each task. |
| selection_rule | Choose C if eligible, otherwise B if eligible, otherwise retain A. |
| incomplete_rule | Any stopped, invalid, underlength, or unmeasured run is incomplete; no adoption result. |

All 36 attempts and independent checks must be available with valid treatments,
controls and complete accounting before the decision rule applies. Ordinary
completed task failures are scored and retained. Compare unrounded cost ratios
to **0.90 times A**; each compared task/arm must have a success. This is an exact
finite-suite rule, not a statistical non-inferiority confidence claim. No best-of
selection, imputation, arm-dependent repairs or replacement attempts. A complete
run with no eligible candidate retains the default; an incomplete run has no
adoption result and leaves the host as it was.

Reopen a selected window if a matched check regresses, a complete repeat loses
the margin, accounting is found missing/duplicated, or client/model/TTL/carrier
changes break the controls. New contradictory real-task evidence can also reopen
it. Require a dated amendment, independent native accounting and a fresh complete
counterbalanced cohort; anecdotes or selective winner reruns are insufficient.

## Budget and stops

The whole experiment, including readiness/model probes, coordinator and wrapper
requests, failures and interruptions, has a **hard cap of 20 percentage points
of any displayed weekly allowance** from the native `/usage` baseline. Read all
weekly buckets and their reset times before readiness, before and after every
attempt, at most 60 seconds apart while active, and after final shutdown.
Use each bucket's end-minus-baseline delta; never sum overlapping buckets or
cumulative readings. Confirm the named weekly reset actually occurred. Unrelated
Claude activity is prohibited during this window.

Cancel the whole owned process group at **18 points**, reserving two points for
in-flight requests and reporting delay. **Polling alone cannot guarantee a hard
cap.** Before launch, a supported nonmutating quota observation/cancellation path
and a worst-case outstanding-charge bound no greater than that reserve must be
established. This has not been demonstrated. If it cannot be established, the
draft is not executable: do not launch, loosen the cap or claim that monitoring
enforces it. A stale/inaccessible gauge, reset change, usage-limit error, unknown
usage, interruption or cap exhaustion stops the entire run as incomplete.

Each attempt is bounded to 7200 seconds and the whole run to 259200 seconds,
including washouts. A seal/base/control mismatch, forbidden edit, underlength A,
wrong/missing compaction evidence or unsuitable offline check also stops it.
No resume or replacement in this cohort. Preserve known usage and null unknowns,
even after a limit error; no stopped run becomes a comparative result. Whether
these large tasks can fit the cap is unknown, not a promise that 36 attempts fit.

## Evidence and receipt shape

Apply [acceptance-evidence-policy](../../docs/acceptance-evidence-policy.md).
This draft, its contract test and the repository validator are **structural
validation**. Version/help is installation inspection. Future observed native
launches/compactions are **upstream examples or native operations**, with dated
primary references. Task oracles are **local integration checks**; the new
builder vectors are **synthetic fixtures**. A separate observer's original
artifact, process and oracle readback is **independent observation**. No local
test is promoted to an unchanged upstream test or a completed provider run.

A future sanitized receipt contains the seal/input/configuration hashes and
chronology; arm/task/repetition ordinals; requested/resolved client/model/effort;
selected window/unset marker; each check's result and oracle/output hashes;
command/exit/bounded returned result; four usage counters by model and their
denominators; weighted cost; every compaction and adjacent context sizes;
wall times; value-only `/usage` observations/reset; failures, interruption and
unknown fields; evidence classes, sanitizations and independent readback.
Allowed statuses are `not_run`, `incomplete`, `complete_no_change` and
`complete_candidate_selected`. An arbitrary `passed` flag is not evidence.

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
The table below records **candidate byte identities only**. It does not freeze
this DRAFT, establish chronology, or authorize execution. There is no result.
The evidence manifest registers this Markdown's own hash without a self-hash.

| Artifact | SHA256 |
| --- | --- |
| `preregistration.json` | `4a4f08e172dd95ca2998e9a39a6dbebf38dc605f10859d714a1779ca8249ef1b` |
| `motivation-20260927.md` | `7e9b224ddb2874cf4836a7ff1d113c7c6c8abb001a1c64d4b4686e9ac907a365` |
| `../../tests/test_compaction_window_ab_preregistration.py` | `47f04aee9892437b3add023c4cf764056bb6af3c2af4a7f09d75b70b76ae30dd` |

Before running, materialize and hash exact inputs, prompts, original page bytes,
independent oracle adapters, agent definitions, carrier and sanitized MCP/runtime
fingerprints. Qualify every oracle offline with correct and discriminating
wrong/missing inputs. Freeze the treatment instrumentation and resolve hard-cap
feasibility. Runtime inheritance is evaluated inside each sealed attempt, not
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

Draft-authoring anti-pattern log, **2026-09-27**, before any model observation:

| Mistake | Verification and correction |
| --- | --- |
| Requiring zero skips in all 190 modules | At the frozen revision, `tests/test_gitleaks_guarded_macos.py:95` and `:110` contain complementary platform skips, making that condition impossible. Freeze the 97-module subset above instead; its readiness remains untested. |
| Treating source-support prose as a deterministic check | Inspection of the pinned CPython source and `child-usage.mjs:458`, `:460`, `:542` established literal/span predicates. W2 and R1 now use those explicit predicates. |

The contract test was written first and run before either preregistration
artifact existed: `rtk python3 -m unittest discover -s tests -p
test_compaction_window_ab_preregistration.py -v`, exit **1**, one expected failure
on the missing JSON artifact. This establishes the red step only; it was no
Claude session. Final structural command results are retained separately in
[build-evidence.json](build-evidence.json).

Open gates are Workflow inheritance/treatment observation, a supportable hard
quota bound, actual >400K task eligibility and budget feasibility, offline-suite
readiness, resolved host fingerprints and sealed oracle adapters. The source
findings above do not settle these runtime questions. They do not justify any
host setting change before a complete accepted result.
