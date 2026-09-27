# Claude Workflow auto-compact window: matched A/B/C preregistration

**Status: DRAFT — not frozen, not run.** Written 2026-09-27, foundation lane.
The user chose “A/B test first,” followed by the best quality per token. The
planned start is immediately after the weekly reset on **2026-09-30 at 21:00
America/New_York (2026-10-01 01:00 UTC)**, subject to sealing and readiness.
This three-repetition pilot can nominate a candidate for confirmation only.
Since the dated host-condition amendment at the end, the host incumbent is
**A** (window key absent, native default). The pilot grants no authority for
persistent host changes: setting B or C on the host requires the independently
preregistered confirmatory cohort to show non-inferior quality and the
preregistered cost reduction, recorded. This document does not
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
  flag `--autocompact auto` overrides a saved `autoCompactWindow`, but cannot
  unset a window injected through settings `env`. A requires the source isolation below.
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

| Arm | CLAUDE_CODE_AUTO_COMPACT_WINDOW | Expected threshold | Validity band for automatic preTokens |
| --- | --- | --- | --- |
| A | unset | window 1000000 (model); trigger about 967000 tokens | [870300, 1000000] |
| B | 400000 | window 400000; trigger about 367000 tokens | [330300, 870300) |
| C | 200000 | window 200000; trigger about 167000 tokens | [150300, 330300) |

Each expected trigger is the window minus the 33000-token autocompact buffer
that `/context` displays on 2.1.283 (coordinator-supplied; see the host-condition
amendment). The partition bands are explained under treatment proof below.
The sole treatment difference is `CLAUDE_CODE_AUTO_COMPACT_WINDOW`. JSON arms contain only their
ordinal and environment patch; all other controls come from one shared object.
Every task/arm/repetition gets its own fresh `claude -p` coordinator and owned
worktree at the frozen revision.

**Frozen host condition for this draft design (amended 2026-09-27):** the user
settings file `~/.claude/settings.json` has **no**
`env.CLAUDE_CODE_AUTO_COMPACT_WINDOW` entry, so the host incumbent is **A**
(native default window). At the user's request, peer session a9 removed the
entry after its research workflow found no primary source recommending 400K or
40%; a backup of the file exists. The coordinator's value-only read at about
**23:28Z** (`jq -r '.env.CLAUDE_CODE_AUTO_COMPACT_WINDOW // "absent"'`) returned
`absent`. The file's mtime, **2026-09-27T23:21:57Z**, is a modification time,
not the removal instant, which stays unknown. Sessions started before the
removal keep `400000` in their process environment: the coordinator's own shell
read `400000` at 23:28Z, and this amendment builder's shell, a worker of that
session, read `400000` at 23:36:46Z beside a settings readback of `absent`. Any
launcher spawned from such a session would pass 400000 on. These are
coordinator-supplied observations plus one builder value-only corroboration,
not a replay. A is both the host incumbent and the experiment's isolated default
reference. `host_condition` in JSON fixes this input without freezing the
experiment; its `drift_action` still blocks launch until a dated amendment
records any further change, as the host-condition amendment does for this one.

Superseded dated history, retained: from **2026-09-27T18:59:00Z** the user
settings held `env.CLAUDE_CODE_AUTO_COMPACT_WINDOW="400000"`, recorded then as
host condition B for every Claude Code session and subagent on this host. The
coordinator's shell read back `400000`, and its first request after 18:59Z
automatically compacted at **902,612 tokens**, a supplied transition
observation, not a measured B-arm threshold. A value-only repair read confirmed
that entry; the Codex repair builder's shell had the variable unset. JSON keeps
this record under `host_condition.superseded_conditions`.

Use the supported **`--setting-sources project`** on **all three arms**, excluding
user and local settings, and load one byte-identical, sealed non-secret packet
with **`--settings <sealed-common-settings.json>`**. The frozen project's settings
and the explicit packet must omit the window env key. Materialize the common
Ultracode, hook, agent, permission and telemetry settings explicitly and qualify
the same effective fingerprints for every arm. Excluding a source may remove
features as well as the window entry; no equivalence is assumed. Keep native
authentication native, without copying sign-ins or private state.

* **A:** remove the selected key from the launch environment using
  `env -u CLAUDE_CODE_AUTO_COMPACT_WINDOW`. This stays required although the
  user settings no longer hold the key: sessions started before the removal
  keep 400000 in their process environment and pass it to launchers they spawn.
  Source exclusion keeps any user `env` entry from being loaded again. Use the
  common `--autocompact auto`.
* **B:** set the isolated launch environment to `400000`, with the same sources,
  packet and `--autocompact auto`.
* **C:** set it to `200000`, with those identical controls.

This mechanism is supported by installed **2.1.283 `--help`**, the
[tagged changelog](https://github.com/anthropics/claude-code/blob/v2.1.283/CHANGELOG.md),
and the [CLI settings-source flag](https://code.claude.com/docs/en/cli-reference#cli-flags).
[Settings precedence](https://code.claude.com/docs/en/settings#settings-precedence)
puts managed settings above CLI settings, then local/project/user settings.
`--settings` merges with enabled lower scopes: an omitted key keeps its lower
value. Passing an empty `env` object therefore does not erase a host entry.
A supported per-key deletion operation was **not found in** installed 2.1.283
help, that pin's changelog or the inspected settings/model-config/CLI docs.
Do not invent an unset flag or use `null`, an empty string or `auto` as an env
value. Managed or embedding-host injection still blocks readiness.

A separate **`CLAUDE_CONFIG_DIR`** is a documented alternative: it relocates
settings, history and plugins. It would require separately qualified matching
setup and native authentication, so this draft selects settings-source isolation.
See [environment variables](https://code.claude.com/docs/en/env-vars) and
[settings locations](https://code.claude.com/docs/en/settings). No directory,
settings file or launch command was applied to the host during this repair.

The **per-arm readback launch gate** applies to every task/arm/repetition.
Before admitting an attempt, read back only this key from the user settings
(expected absent: incumbent A), the enabled project/explicit/managed sources and
the patched launch environment, plus their sealed digests. Expected launch
values are A **unset**, B **400000**, C **200000**. The same value-only readback
must show `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS` and
`CLAUDE_CODE_DISABLE_1M_CONTEXT` absent in every arm. The
[environment-variable docs](https://code.claude.com/docs/en/env-vars), read
2026-09-27, say the override sets "the percentage (1-100) of the auto-compact
window at which auto-compaction triggers" and "can't raise the threshold", so it
can only lower a trigger. They also say that increasing the output-token cap
"reduces the effective context window available before auto-compaction
triggers". The third variable holds sessions to 200K. An inaccessible source,
conflict or changed host condition blocks launch. A separately qualified value-only native shell
observation must also read the effective coordinator and focal-child variable
after settings application and corroborate the loaded sources. A prelaunch
file read cannot prove inheritance. No undocumented dry-run or effective-window
readback CLI is asserted; this observation path remains **unqualified**, with
`do_not_launch`. In eventual sealed attempts, count all readiness usage, stop
incomplete on mismatches and retain independent native treatment evidence.

All proposed launches also include `--autocompact auto --model claude-opus-5-5
--effort xhigh --output-format stream-json --verbose`, the common settings-source
arguments and the same sealed prompt/MCP packet. These are design arguments,
not commands executed while drafting. Keep coordinator xhigh under Ultracode
and an explicit Workflow stage. Every focal child is Opus 5.5/max with its named
role. Sonnet 5/max is allowed only for pure command wrappers; verification,
build and judgment remain Opus. No global effort override, fast mode, model
fallback or 200K context hold.

Seal byte-identical agent definitions, task packets, token-lane carrier, MCP set,
deferred grants, native caching, permission policy and tool versions. Capture
resolved model/effort in every child. The carrier must actually appear in each
Workflow child's first prompt; Agent-tool acceptance does not prove that.
The isolated scope keeps any user-settings or inherited window value out of
every arm; any remaining conflict is a readiness failure. Persistent host
settings stay A: this pilot changes none.

Prove treatment with both sanitized launch evidence and **child** transcripts:
native `system/compact_boundary`, `compactMetadata.trigger=auto` and `preTokens`,
plus adjacent deduplicated request contexts. B and C each require an automatic
event in every focal child. Every automatic event's preTokens must lie in its
arm's **partition band** from the table above: C **[150300, 330300)**,
B **[330300, 870300)**, A **[870300, 1000000]**. Each lower bound is 0.9 × the
arm's expected trigger (window − 33000 on 2.1.283); each upper bound is the
next-higher arm's lower bound, exclusive, and A's is the model's 1,000,000-token
window, inclusive. An event therefore stays attributable to exactly one arm's
trigger: a misapplied default window (an event at or above 870300) or a lower
window (an event below 0.9 × the trigger) still invalidates the run, while
normal last-request overshoot does not. These bands are an experiment validity
rule, not a claim that upstream guarantees them; a client change can move the
buffer and needs a dated amendment. A must exceed 400000; A's band is unchanged,
around the documented 967K. An A child that finishes before compaction is
right-censored, with no invented 967K event. Manual compaction, missing
treatment evidence, outside-band events or a replacement child invalidate the
run. Record all usage anyway.

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
| B1 | Frozen Git base; porcelain status including untracked/ignored files; ignored-file hashes; actual red/edit/green chronology and original test bytes | Red run follows the edit |
| B2 | Candidate module results on frozen vectors and immutable source coverage | Input mutation |
| W1 | Original RST blobs and native fetch captures | Empty page coverage |
| W2 | Typed original rows, facts and bounded original citation spans | String latency instead of integer |
| V1 | Actual module command captures and ordered round inventory | Zero tests despite exit 0 |
| V2 | Frozen event bytes, partition/validator output | Nonzero partition exit despite a passing summary |
| R1 | Original Git/AST inventory and pinned reader spans | Failed-attempt usage excluded |
| R2 | Original patch and unchanged-worktree observation | 30 hunks instead of 31 |

B1 derives paths with `git status --porcelain=v1 --untracked-files=all
--ignored=traditional -z`, against the frozen HEAD and the predetermined sealed
overlay. Include tracked changes, every untracked file, both rename paths and
new/changed/deleted ignored files. Compare ignored-file path and SHA256 inventories
before and after: an unchanged `!!` status does not imply unchanged bytes. Only
byte-unchanged sealed overlays may be excluded. Any forbidden path fails; the
new regression file cannot disappear from the check merely because it is
untracked. No staging or index writes are needed. Source:
[Git status](https://git-scm.com/docs/git-status); plain
[Git diff](https://git-scm.com/docs/git-diff) alone omits these new files.

Exact digest matching operates on **adapter-computed predicates** for tolerance
rules. B1 emits `red_exit_nonzero` and `changed_paths_subset_including_reader`,
with separate new-test, missing-export and ownership predicates. Red exit 2 is
valid just as 1 is; the subset predicate alone does not satisfy new-test creation.
R1 emits three `citation_predicates` plus `cites_pinned_reader_sha`: spans must
cover 458..458, 460..460 and 542..548, with at most five extra original lines on
either side. For example, 456..460 is valid for the first fact. Require the
specified path/revision and original reader SHA256
`f5ea9c3a1b47cab91e90a515f455bcf6a960fb696db89717e04b7424e4ff42a0`.
Raw exit codes, paths, spans and source identities remain independent evidence;
only actual literal requirements enter the target as literals. See
[Inspect 0.3.271 exact comparison](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0.3.271/src/inspect_ai/scorer/_common.py).
Both contracts and their eight control hashes were regenerated; local predicate
examples check boundaries without claiming executable adapter acceptance.

These fixtures exercise the proposed scorer boundary; reduced synthetic
coverage is explicitly **not** a passing full-corpus extraction test. Full
artifact adapters are still unmaterialized (`executable_sha256: null`), their
pinned Inspect controls are unrun, and the earlier repair inspected a separate installed package at **0.3.266**.
This repair's `python3` package metadata did not find `inspect-ai`; neither
observation qualifies execution at 0.3.271.
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
must be five minutes, with no other Claude usage during the experiment. The
per-request TTL evidence gate below is unqualified; settings alone do not prove
this condition or the adequacy of the washout. Record
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
names its source, observation window and denominator. The proposed instrument
is **native Claude Code OTel `api_request` events → the existing host collector
→ Loki**, plus `api_error` and `api_refusal` coverage records. This is a
**log-only, unqualified** instrument: it does not see individual intermediate
retry attempts. Use emitted input/output/cache-creation/cache-read counters,
mapping OTel `cache_creation_tokens`/`cache_read_tokens` to transcript categories.
Per-request context is input + cache creation + cache read; cumulative cache
reads measure cost, not context size.

Query Loki's `GET /loki/api/v1/query_range` each second with the sealed owned
session selector and overlapping intervals. Fully page/split truncated responses,
retain query/arrival timestamps and re-query the whole interval at shutdown.
A missing page is missing evidence. **Deduplicate by provider and request ID**,
where provider is the sealed run constant **`anthropic_api`**, attached to each
row from the fixed route; it is not a documented `api_request` attribute.
Identical retransmissions count once; conflicting duplicate counters stop the
comparison. Distinct observed provider request IDs count separately. A missing
request ID stays unresolved: retain `session.id`, `event.sequence`, `event.name`
and an observer envelope ordinal as a holding locator, never a usage key.
Sequence numbers are per process, so collisions must not merge records. Missing
IDs stop the pilot incomplete; neither timestamps nor text establish zero charge.

Join request IDs and session/Workflow ownership through the qualified launch
registry, `workflow.run_id` and `query_source`. `agent_id` and `parent_agent_id`
are span fields; this log ledger does not use them. Retain observed compact,
background, terminal-chain, refusal, fallback and interrupted work even without
an assistant message. Ambiguous owners prevent child-cost selection. Check
resolved model, `speed` and refusal `server_fallback_hop`; absent applicable
attributes are **unknown**, never evidence of normal speed or no fallback.

**Retry/error limitation:** `api_request` documents no `attempt` field.
`api_error.attempt` is the total number of attempts including the initial one;
it is a terminal-chain count, not an individual usage row. Intermediate retries
appear as `gen_ai.request.attempt` **trace** events, which this ledger does not
collect. A successful terminal request cannot establish that earlier attempts
were absent or free. `api_error` also documents no token counters. No admissible
counter source is qualified here: **any terminal API error ends the pilot
incomplete**. Complete retry accounting is **not supported until qualified**;
an independently sourced attempt/counter instrument needs an amendment before
launch. Merely adding trace IDs would not prove counters. Sources:
[API error events](https://code.claude.com/docs/en/monitoring-usage#api-error-event),
[API request events](https://code.claude.com/docs/en/monitoring-usage#api-request-event)
and [traces](https://code.claude.com/docs/en/monitoring-usage#traces-beta).

After settled exit, reconcile owned sessions with **ccusage v20.0.26**:
`ccusage claude session --id "$SESSION_ID" --json --offline`. Prove which child
transcripts are included before comparing model/category scopes. Require
`OTel = ccusage + OTel-only - ccusage-only`, enumerating each residual by private
request ID and original evidence. Fully metered OTel-only compaction may be
legitimate; unexplained residuals cannot be discarded. The unchanged baseline
reader supplies a separate attribution cross-check. **Never add ccusage,
transcript or /usage totals to OTel totals.** Equal sums cannot recover missing
intermediate retries or settle counter-less terminal errors.

The actual repository log `keep_keys` allowlist retains `workflow.run_id`,
`query_source`, `attempt`, `model` and the four counters, but drops
**`request_id`, `client_request_id`, `server_fallback_hop`, `speed`**. It also
omits span-only agent/parent IDs, which are excluded from this log-ledger design.
The launch gate now requires all applicable emitted attributes, including event
name/time/sequence and session identity, to survive the **active collector into
Loki** with equal values/types. JSON lists the full requirement and its exact
difference from the template. ID-only checks are insufficient. Read-back must
cover the corresponding request, error, refusal and Workflow event types;
missing applicable fields are unknown. Template membership cannot prove active
preservation or native emission. No collector changes or live observations were
performed in this repair. [Collector template](../../observability/collector/collector.yaml),
[refusal schema](https://code.claude.com/docs/en/monitoring-usage#api-refusal-event).

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
Fast mode, other models or unresolved usage invalidate this comparison. The
one-hour-write exclusion is **not evaluable from the current ledger**:
`cache_creation_tokens` has no TTL split. Official prices charge 1.25x base for
five-minute writes and 2x for one-hour writes. No per-request source is qualified
here, and no claim is made that pinned transcripts retain the split. Configuration
inspection cannot prove five-minute writes. Require a source-backed per-request
split joined by request ID with totals reconciling to the native aggregate; until
qualified by amendment, **W and cost per success remain unknown, no selection is
possible and launch is prohibited**. Aggregate cache-write tokens still count
once in the token budget. The table/formula above are conditional five-minute
weights. Neither model has a >200K premium in this price sheet. Coordinator-only requests, native tool savings estimates and quota
readings have separate scopes and are not added to overlapping child totals.

Record every compaction's trigger, its pre-compaction size (the native
preTokens field), the context size of the requests before and after it, and
the per-child maximum. Supervisor monotonic time gives attempt wall
seconds through full shutdown, with child duration separately corroborated by
the journal. Report failed/interrupted time, all-attempt time per success, and
scheduled elapsed time including washouts separately.

**Secondary descriptive outcome (SIZE-07).** For each task and arm, report the
frozen check outcomes alongside each focal child's **peak prompt tokens** (its
largest deduplicated input + cache creation + cache read) and its **peak
utilization of the model's 1M window** (that peak divided by 1,000,000).
[SIZE-07](../../docs/harness-rules-convergence-20260922.md) keeps the community
"under 40% context utilization" heuristic as unadopted guidance until it is
measured against this project's child-usage records, and the community sweep's
[M3](../../docs/decisions/2026-09-24-community-sweep.md) waits on that trial
(lines 207 and 172, read at b6f36d8c). The existing rule that all 12 A focal
children exceed 400000 prompt tokens already makes the arms a contrast of
utilization above 40% against triggers below it: B at about 36.7% and C at about
16.7%. Last-request overshoot can carry a B peak above 40% (the relayed 432,724
event is 43.3%), so peaks are recorded, not assumed.
This outcome is **not powered** to satisfy SIZE-07's overturn condition, a local
trial correlating utilization above 40% with measurably worse extraction or
review quality. It does not enter selection and adds no quality-superiority
selection path; the decision rule below is unchanged.

The following contract table is checked literally against JSON:

| Key | Value |
| --- | --- |
| default_approx_tokens | 967000 |
| B_window_tokens | 400000 |
| C_window_tokens | 200000 |
| observed_autocompact_buffer_tokens | 33000 |
| B_expected_trigger_tokens | 367000 |
| C_expected_trigger_tokens | 167000 |
| long_child_prompt_tokens_exclusive | 400000 |
| cost_reduction_min_fraction | 0.1 |
| repetitions_per_task_arm | 3 |
| washout_seconds | 360 |
| run_budget_tokens | 1000000000 |
| ledger_poll_seconds | 1 |
| quality_rule | For every task and check, any pass in A requires a pass in every repetition of the candidate. |
| pass_count_rule | Candidate total passed checks and successful tasks must each be at least A's totals. |
| cost_rule | All-attempt weighted child cost per successful task must be at least 10% lower than A, both pooled and for each task. |
| selection_rule | Among quality-eligible candidates meeting the 10% pooled and per-task cost margin versus A, choose the unique lowest pooled all-attempt weighted child cost per successful task; an exact cost tie yields no selection and leaves the incumbent host setting A unchanged. |
| incomplete_rule | Any stopped, invalid, underlength, or unmeasured run is incomplete; no adoption result. |

All 36 attempts and independent checks must be available with valid treatments,
controls and complete accounting before applying this **descriptive pilot**
rule. Ordinary completed failures remain in the numerator; every compared
arm/task needs a success. Candidates must pass the observed quality gates and
cost at most **0.90 times A**, for every task and pooled. Then minimize pooled
all-attempt weighted child cost per success among eligible candidates, using
unrounded exact decimal/rational arithmetic. There is no B/C priority and no
extra margin between them. An exact tie for the lowest cost gives **no
selection**, leaving the host incumbent **A** (key absent, native default)
unchanged. Rounded equality is not an exact tie.

At equal quality, `A=100, B=60, C=89` selects **B**; `A=100, B=89, C=60` selects
**C**. If `B=C=60`, neither wins; the nomination is null and incumbent A is
unchanged. `B=91, C=95` fails
the minimum effect; B=60 with a quality regression cannot beat eligible C=89.
These examples apply to every task as well as pooled cost. They are arithmetic
controls, not model observations.

A selected pilot candidate only informs a separately preregistered confirmatory
cohort; it does not authorize persistent adoption. Setting B or C on the host
requires that cohort to show non-inferior quality and the preregistered cost
reduction, recorded. An incomplete run has no
comparative result. No best-of selection, imputation, arm-dependent repair or
replacement attempts. Preserve every failure. Changed client/model/TTL/carrier
or contradictory independent results require a dated amendment and new cohort;
anecdotes or selectively rerun winners cannot validate this one.

## Budget and stops

The proposed ceiling is **1,000,000,000 native tokens**, summed as input + cache
creation + cache read + output over all deduplicated **owned** requests,
including readiness, coordinators, children, compaction/background work,
wrappers, retries, failures, refusals and fallbacks. This is the required budget
scope, not a claim that the present log instrument observes all of those paths.
Intermediate retries and counter-less errors remain unresolved. This is a fixed proposed
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
Retain unresolved charge as unknown and the run as incomplete. The attempt wall cap stays **7200 seconds**. The whole-run cap must include
**36 attempts + 35 washouts + 36 drains**, plus bounded readiness/orchestration:
`36*7200 + 35*360 + 36*D + H = 271800 + 36*D + H` seconds. `D` must bound delivery
wait, both complete ledger reads and reconciliation; `H` must cover readiness
and overhead outside attempts. Conservatively do not overlap drains and
washouts. Both bounds and the resulting numeric cap remain **null**, with
`do_not_launch`; sealing must supply qualified finite values and a cap at least
this large. The former 259200 seconds is superseded, with no guessed drain
allowance. Preserve every stopped attempt; no in-cohort extension or replacement.

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
denominators; weighted cost; every compaction and adjacent context sizes; each
focal child's peak prompt tokens and peak 1M-window utilization beside its
check outcomes; wall times; request-ledger and reconciliation hashes; measured lag, reserve proof and cancellation records; before/after value-only `/usage` observations/reset; failures, interruption and
unknown fields; evidence classes, sanitizations and independent readback.
Allowed statuses are `not_run`, `incomplete`, `complete_no_change` and
`complete_candidate_selected`. `complete_no_change` means no candidate
nomination and leaves the recorded incumbent **A** (unset) unchanged.
Candidate selection is a nomination for the confirmatory cohort only; it sets
no window on the host. An arbitrary `passed` flag is not evidence.

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
At integrated head **f7cc409a**, the evidence manifest registered the prior
repair's three files at their then-current bytes, plus the unchanged original
build record. A read-only comparison in this cross-family round confirmed those
identities, and the baseline validator passed (7353 hashed files). The older
failure below is dated history. This round changes four files, including the
build record; their final registrations are for the coordinator to refresh.
This builder does not edit `manifests/evidence.json`.

| Artifact | SHA256 |
| --- | --- |
| `preregistration.json` | `4a4f08e172dd95ca2998e9a39a6dbebf38dc605f10859d714a1779ca8249ef1b` |
| `motivation-20260927.md` | `7e9b224ddb2874cf4836a7ff1d113c7c6c8abb001a1c64d4b4686e9ac907a365` |
| `../../tests/test_compaction_window_ab_preregistration.py` | `47f04aee9892437b3add023c4cf764056bb6af3c2af4a7f09d75b70b76ae30dd` |

Before running, materialize and hash exact inputs, prompts, original page bytes,
independent oracle adapters, agent definitions, carrier and sanitized MCP/runtime
fingerprints. Qualify every oracle offline with correct and discriminating
wrong/malformed/missing inputs using Inspect 0.3.271. Freeze the native request instrumentation, prove every applicable required log attribute survives the active collector, and qualify measured lag, an enforceable outstanding-token reserve and owned cancellation. Runtime inheritance is evaluated inside each sealed attempt, not
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

Research for the **earlier GPT-6 review repair**, 2026-09-27, before those repairs: the supplied
`gpt6-review.md` (SHA256 `f27867d62728615952804aa8e04cd540ab0e63ce199545d4893883f0d7c18e2c`)
and W9 in `report2.md` (SHA256 `b5d204ebe070c26b64fe06ea4726181ad695f7f9e4abd7bc41b6b34dcd2ed5a6`)
were checked against primary sources. Reuse the review's installed Claude
2.1.283/changelog inspection; no new Claude session was started.

* Metering: [native API request events](https://code.claude.com/docs/en/monitoring-usage#api-request-event),
  [Loki query API](https://grafana.com/docs/loki/latest/reference/loki-http-api/),
  and [ccusage v20.0.26 session reports](https://github.com/ccusage/ccusage/blob/v20.0.26/docs/guide/session-reports.md).
  The repository [collector template](../../observability/collector/collector.yaml)
  was initially described as missing IDs only. This round checked the actual
  log allowlist: `request_id`, `client_request_id`, `server_fallback_hop` and
  `speed` are the missing required log fields. Span-only agent/parent IDs are
  removed from the join. The template cannot prove active Loki preservation.
* Grading: [Inspect 0.3.271 scorers](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0.3.271/docs/scorers.qmd)
  and its [match implementation](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0.3.271/src/inspect_ai/scorer/_match.py).
  The earlier repair recorded installed metadata **0.3.266**. This builder's
  `python3` metadata does not find `inspect-ai`; no installation or scorer
  execution is inferred from either observation.
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

Open gates include isolated settings and effective per-arm readback, Workflow
treatment, complete log-attribute/child joins, retry and TTL instruments, lag and
proven outstanding-token/drain/readiness bounds, >400K eligibility and budget
feasibility, offline-suite readiness and executable Inspect controls. The source
findings above do not settle these runtime questions. The host incumbent is A
(key absent) since the dated host-condition amendment; this pilot supplies no
authority for persistent host changes, even after a complete result.


## Amendment 2026-09-27 — earlier GPT-6 review repair, still DRAFT

No model results were observed and no Claude session was launched. This
amendment supersedes the original weekly-percent cap, transcript-primary cost
instrument, C-first choice, unspecified grader/control framework and the
three-repeat adoption scope. It preserves the original task packets, arm
windows, common launch controls and ordering. Source identities and the
research disposition are recorded above and in JSON. The original candidate
hash table remains historical; the identities at the end of this earlier
record were subsequently registered at f7cc409a. This is not a seal, merge receipt or execution authorization.

| Review finding | Disposition | Repair and remaining evidence |
| --- | --- | --- |
| Blocker: hard cap lacks observation, cancellation and outstanding-charge bound | **Not supported as a proven hard cap** | Replaced weekly percentages with the 1,000,000,000-token all-owned ledger budget; specified polling, ownership-checked TERM/KILL, late-event settlement and an explicit conservative reserve formula. Actual reporting lag, enforceable request/delivery bounds and cancellation observations are unavailable in this no-session round. They remain null and launch remains prohibited; a five-second export interval cannot fill them. |
| High: compaction/background/retry/refusal/fallback accounting has no request instrument | **Not supported until qualified** (corrected in cross-family round below) | Log events define emitted terminal-chain records only. Intermediate attempts are trace events and counter-less terminal errors end this pilot incomplete. Attribute-complete collector qualification, child ownership, complete attempt/counter evidence and TTL weighting remain open. A specified ledger is not proof of full coverage. |
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

The earlier repair's pre-integration publication command returned exit **1**:

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

Those were the three edited files' stale registrations **at that earlier
pre-integration check**. The coordinator subsequently registered them at
f7cc409a. This cross-family round independently verified those registered bytes
and ran the baseline validator successfully before editing. The earlier exit 1
is preserved as history, not a present-tense status. This round's final output
is retained in `build-evidence.json`; no scorer or native acceptance follows
from structural tests.

Earlier repair candidate identities, registered at f7cc409a (not a freeze):

| Artifact | SHA256 |
| --- | --- |
| `preregistration.json` | `2d335e15a0d0de7bdacd6421261a2cad83971bbd9053450be0b917c42975730c` |
| `../../tests/test_compaction_window_ab_preregistration.py` | `4bc86a6aa52d014e29ace37e25ab74c564b4984d3d20534aae21be39d6ffb155` |

The coordinator records this Markdown's final digest externally to avoid a
self-hash. That earlier list of runtime gates is supplemented by this round's
attribute-complete, retry, TTL, settings-readback and wall-budget gates below.
Three repeats remain a pilot even if those gates are later satisfied.


## Amendment 2026-09-27 — PR #416 cross-family repair, still DRAFT

This round checks the nine findings in `416-review-claude.json` against reviewed
head **f7cc409a3df212375c76f957700b1ebb16ce1e73**, native client help, the
v2.1.283 release/changelog, original reader bytes, the actual collector allowlist,
Git's documented status format, Inspect 0.3.271 source and official Claude docs.
The review file digest is in JSON. Installed search-first/find-skills discovery
retained the existing document/test seam and pinned Inspect approach; the
[Inspect skills listing](https://skills.sh/meridianlabs-ai/inspect-skills) supplies
no replacement for these task oracles. The installed tdd and
verification-before-completion skills govern the fail-first structural check.
No package installation, subagent, model run, Claude session, host setting edit,
Git metadata write or evidence-manifest edit is part of this repair.

The `gh api` release lookup failed on network access; Context Mode fetched the
same [v2.1.283 release record](https://api.github.com/repos/anthropics/claude-code/releases/tags/v2.1.283)
and tagged changelog. Native web open/search was unavailable; Context Mode
fetched the official documents. A direct sandbox HTTP fetch was refused (403)
and was not treated as evidence of source absence. The current Python
interpreter did not find Inspect package metadata; the earlier 0.3.266 result
has been dated to its original environment. No upstream scorer was run.

| Finding | Disposition | Verified repair and boundary |
| --- | --- | --- |
| F1 blocker: live host setting missing | **Fixed in draft** | Record user `env` value 400000, activation 18:59Z, all-session/subagent scope and supplied coordinator readback/902,612 transition. A uses supported source exclusion plus a common explicit packet; every arm gets value-only readback gates. No-selection leaves incumbent B unchanged. [Settings precedence](https://code.claude.com/docs/en/settings#settings-precedence), [CLI](https://code.claude.com/docs/en/cli-reference#cli-flags), [window precedence](https://code.claude.com/docs/en/model-config#set-the-auto-compact-window). Native qualification remains open. |
| F2 major: B1 misses untracked paths | **Fixed** | Porcelain v1 with all untracked and ignored files, before/after ignored-file hashes, frozen base and exact immutable-overlay checks; no index mutation. [Git status](https://git-scm.com/docs/git-status). |
| F3 major: tolerance rules encoded as literals | **Fixed** | B1 exit/set predicates; R1 bounded-span and pinned-reader identity predicates. Rehash both contracts and all eight controls. [Inspect exact branch](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0.3.271/src/inspect_ai/scorer/_common.py); original reader at 341ba641, SHA256 and lines recorded above. Executable adapters remain unqualified. |
| F4 major: ID-only collector gate | **Fixed** | Compare required attributes with actual log `keep_keys`; missing request/client IDs, fallback hop and speed all gate launch. Remove span-only lineage from log joins. [Collector](../../observability/collector/collector.yaml), [monitoring schema](https://code.claude.com/docs/en/monitoring-usage). |
| F5 major: retries/errors overclaimed | **Fixed by narrowing; complete metering not supported until qualified** | Terminal-chain scope only, no intermediate-attempt claim; any terminal API error ends incomplete with no qualified counter source. [API errors](https://code.claude.com/docs/en/monitoring-usage#api-error-event), [traces](https://code.claude.com/docs/en/monitoring-usage#traces-beta). |
| F6 minor: uncaptured provider in key | **Fixed** | Provider is the sealed `anthropic_api` run constant; missing request IDs stay unresolved and cannot become usage dedup keys. [API request fields](https://code.claude.com/docs/en/monitoring-usage#api-request-event). |
| F7 minor: one-hour write rule lacks TTL split | **Fixed by marking not evaluable** | No qualified per-request TTL source; conditional weights remain, W/CPS unknown and no launch/selection. Native aggregate tokens still count. [API request fields](https://code.claude.com/docs/en/monitoring-usage#api-request-event), [pricing multipliers](https://platform.claude.com/docs/en/about-claude/pricing). |
| F8 minor: whole-run wall cap excludes washouts/drains | **Fixed** | Replace 259200 with a seal-time cap at least `271800 + 36*D + H`; D/H and numeric cap stay null until qualified. Arithmetic uses this draft's frozen 36 attempts, 7200-second attempt caps and 35 360-second washouts. |
| F9 minor: stale registration/validation statements | **Fixed** | Date earlier failures; independently confirm all pre-repair registered bytes at f7cc409a and baseline validator exit 0. Current edited-file hash mismatches require coordinator registration. [Build evidence](build-evidence.json). |

All nine corrections and verification paths are also appended to JSON's
anti-pattern log. The new tests ran before changing JSON or this Markdown:
`python3 -m unittest tests.test_compaction_window_ab_preregistration -v`, with
`PYTHONDONTWRITEBYTECODE=1`, returned **exit 1**, **14 tests, 11 failures**.
Failures cover the blocker, all four majors and the structurally checkable
minors, plus existing selection/coverage assertions that encoded the old rules.
The actual red excerpt and final pass/validator outputs are retained in
[build-evidence.json](build-evidence.json), with their command and exit codes.
These checks verify draft structure and predicate examples only. The experiment
remains **DRAFT, not frozen, not run; launch stays prohibited**.


## Amendment 2026-09-27 — host-condition change (incumbent A), still DRAFT

No model results were observed. The builder, a Claude Opus 5.5 isolated-builder
working from base **b6f36d8c**, started no Claude session and made no model call.
Its only client invocation was `claude --version`, an installation inspection
that returned 2.1.283. This amendment is exactly what `drift_action` requires
for a changed host condition, and that rule stays in force for any further
drift. It supersedes three things: the 18:59Z host condition B=400000; the
window-centred bands B 360000–440000 and C 180000–220000; and the wording that
kept B as the host setting after a tie or a complete no-change result. It
preserves the arms, tasks, ordering, A's band, the >400000 A-child eligibility
rule, the 10% margin, the quality, pass-count and cost rules, and every earlier
amendment and table.

Inputs F1–F5 are coordinator-supplied observations or coordinator-relayed peer
observations, dated 2026-09-27; this builder did not replay them. The builder
added one value-only readback and a sandboxed read of the Markdown form of two
official documentation pages.

| Input | Observation and provenance | Change |
| --- | --- | --- |
| F1 host condition | At the user's request, peer session a9 removed `env.CLAUDE_CODE_AUTO_COMPACT_WINDOW` from the user settings. Its research workflow found no primary source recommending 400K or 40%, and a backup of the file exists. The coordinator's value-only read at about 23:28Z returned `absent`. The file mtime, 23:21:57Z, is not the removal instant. The coordinator's shell still read `400000`. Builder corroboration at 23:36:46Z: settings `absent`, builder shell `400000`. | Incumbent A (key absent) in `host_condition`, with the 18:59Z/902,612 record moved to `superseded_conditions`. Arm A keeps `env -u CLAUDE_CODE_AUTO_COMPACT_WINDOW` because sessions started before the removal keep 400000 and pass it to launchers they spawn. Settings-source isolation stays for all arms. |
| F2 autocompact buffer | Installed 2.1.283 ran `claude -p "/context" --model claude-opus-5-5` from a scratch directory. It displayed `Autocompact buffer` **33k** at every window tried: unset (1m), 400000, 200000 and 100000. This is a native display observation, not a compaction event. [Model configuration](https://code.claude.com/docs/en/model-config#set-the-auto-compact-window) calls the window "how full the context window can get before Claude Code compacts the conversation", caps it "at the model's context window" and gives about 967K as the default. It states no buffer. | Expected trigger = window − 33000: A 967000 (1,000,000 − 33,000, matching the documented default), B 367000, C 167000. The buffer and the B/C triggers enter `thresholds` and the contract table. |
| F3 consequence | The old C band, 180000–220000, excluded C's 167000 trigger, so every C focal child would have invalidated the run. B's 360000–440000 held 367000 by only 7000. | Bands re-anchored on the triggers before any observation. |
| F4 native events | Peer a9, value-level, coordinator-relayed: `compactMetadata.preTokens` of automatic `compact_boundary` entries in all main and subagent transcripts (subagents include Workflow children), from 18:59:21Z (key added) to 23:23:33Z. There were 35 events. The 31 from sessions running 400000 span 366,209–432,724 (median 368,563; 18 main, 13 subagent). Four from sessions launched before the switch span 618,371–922,073. Before the switch, every event fell in 966,908–971,662. | Partition bands (below) replace the symmetric ±10% first draft of this amendment. That draft would have set B to 330300–403700 and excluded the real 432,724 event (+17.9%). |
| F5 implementation reading | From the installed 2.1.283 binary, peer a9 reports threshold = (window − min(model max output, 20000)) − 13000. It is undocumented, and the binary offsets are omitted. | Recorded only as a peer-supplied, undocumented implementation reading. Nothing relies on it: the 33k total stands on the `/context` display, the documented "about 967K" and F4. The earlier statement that no undocumented binary reverse engineering filled a gap therefore stays true for everything this draft relies on. |

**Partition bands.** Each arm's lower bound is 0.9 × its trigger, which keeps
the 10% tolerance below the trigger. Each upper bound is the next-higher arm's
lower bound, exclusive; A's upper bound is 1,000,000, inclusive. The bands are
C [150300, 330300), B [330300, 870300) and A [870300, 1000000] (unchanged).
Every event stays attributable to exactly one arm's trigger. A misapplied
default window (an event at or above 870,300) or a lower window (an event below
0.9 × the trigger) still invalidates the run; normal last-request overshoot does
not. Overshoot is an absolute amount, the last request's growth, so a symmetric
band would have hurt C most, and each focal child may compact more than once.
F4's lowest 400000-window event, 366,209, fired 791 tokens below the nominal
367,000; the 0.9 lower bound covers that. The bands remain an experiment
validity rule, not an upstream guarantee.

**Launch gate.** The per-arm value-only readback now also requires
`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS` and
`CLAUDE_CODE_DISABLE_1M_CONTEXT` to be absent in every arm. On 2026-09-27 the
builder fetched the [environment-variable docs](https://code.claude.com/docs/en/env-vars).
They say the override "can't raise the threshold", so it can only lower a
trigger. They also say that increasing the output-token cap "reduces the
effective context window available before auto-compaction triggers". That
documented effect is the primary reason for the second key. F5 corroborates it
but is undocumented, and it caps the reserve at 20000 where the docs state no
cap. The protocol relies on neither beyond requiring the key absent, and
`CLAUDE_CODE_MAX_OUTPUT_TOKENS` joins `must_be_unset`.

**Incumbent wording.** The tie rule is now
`exact_unrounded_tie_no_selection_incumbent_A_unchanged`, and
`no_selection_host_action` is `leave_incumbent_A_unchanged`. `complete_no_change`
leaves incumbent A (unset) unchanged. The phrases "no reversion to A" and "even
if B already runs on the host" are removed as moot. The selection rule still
compares against A, and the 10% margin and the quality, pass-count and cost
rules are unchanged. The pilot grants no authority for persistent host changes:
setting B or C on the host requires the independently preregistered
confirmatory cohort to show non-inferior quality and the preregistered cost
reduction, recorded. Dated history entries keep their original wording.

**SIZE-07.** A descriptive secondary outcome reports, for each task and arm,
the check outcomes beside each focal child's peak prompt tokens and peak
1M-window utilization. It is not powered for SIZE-07's overturn condition, does
not enter selection and adds no quality-superiority selection path.

Residuals this amendment does not resolve:

* The 33k figure is a `/context` display observation, not a measured
  compaction threshold. The buffer may depend on the client version, and a
  client change needs a dated amendment.
* No automatic compaction at the new B or C triggers has been observed in an
  arm. F4 comes from historical host sessions, relayed rather than replayed.
* The four F4 events from sessions launched before the switch (618,371–922,073)
  are unattributed. The relayed description says those sessions still ran the
  default window; if so, an A child could auto-compact below 870,300 and
  invalidate the run. The competing explanation is the superseded record's
  classification of the coordinator's 902,612 event as a transition
  observation. A's band is not widened.
* The removal instant is unknown (file mtime only), and sessions started before
  it still carry 400000.
* F5 is undocumented, and it disagrees with the docs on whether the output
  reserve is capped.

The updated contract test ran first against the base commit's unchanged
blueprint files. `python3 -m unittest tests.test_compaction_window_ab_preregistration -v`,
with `PYTHONDONTWRITEBYTECODE=1`, returned **exit 1**: **21 tests, 10
failures, 0 errors**, with the 11 unaffected tests passing. The actual returned
lines, the green run and the validator output are in
[build-evidence.json](build-evidence.json). The coordinator registers this
round's final bytes. These checks verify draft structure and arithmetic only.
The experiment remains **DRAFT, not frozen, not run; launch stays prohibited**.
