# Native Workflow writing and recovery qualification

The bounded writing pilot produced correct code in both arms. It did **not**
establish a fully compliant or superior multi-agent workflow: both arms piped
native test output, and the Workflow arm omitted the required authoring skill.
Independent unpiped verification accepted both repairs. Keep a capable single
agent as the economical choice for this small repair; this one ordered pair is
not a cross-task model ranking.

The qualification starts from canonical revision
`3cabcdfd0c3b489867364d9582df8f356586d219` in an owned branch and worktree.
It reuses the existing invoice repair fixture and its corrected independent
seven-case oracle from the September 18 native coding pilot. This is a local
integration fixture, not an upstream product test or a blinded production task.
The fixture instruction update permits only the requested coordinator
to delegate to explicitly owned worktrees. Original invoice code, visible tests,
and the external oracle remain unchanged.

## Frozen comparison

- Task: repair `invoice_summary` for a one-shot iterable in one streaming pass,
  using the existing integer-cents helpers and preserving receipt integration.
- Effects: only `invoice.py` may change. Tracked user sentinel edits and an
  untracked user note must survive. No installs, shared settings or external
  messages are allowed. Each writing worker has its own checkout.
- Baseline A: one native Opus agent at high effort, with no delegation.
- Candidate B: native Fable/Ultracode coordinator, Sonnet/medium implementation
  worker and Opus/high read-only reviewer, at most three total workers if one
  correction is supported. Native Workflow must run; ordinary Agent dispatch
  cannot substitute for it.
- Initial pilot order: A, B in fresh sessions and identical fixture bases.
  Counterbalanced checkouts were prepared but are not automatically dispatched;
  another pair requires a concrete unresolved measurement question. This small
  pilot cannot establish a reliable ranking; cache state, time order and model
  combination remain explicit confounders.
- Acceptance: unchanged visible pytest suite; unchanged independent seven-case
  oracle kept outside worker checkouts; direct source review for helper reuse
  and lack of input materialization; exact changed-path and sentinel checks.
- Usage: retain every native attempt, coordinator and worker usage views,
  correction/review activity and elapsed time. Do not sum cumulative events or
  child categories already included in native totals. Missing coverage stays
  unknown. Subscription usage is not an additional invoice.

The shared native model slot is coordinated with the separate retrieval audit.
Stop new dispatch on a quota response; do not retry an unchanged account failure.

## Observed writing results

| Arm | Actual native models | Reported tokens | Elapsed | Independent acceptance |
| --- | --- | ---: | ---: | --- |
| A | Opus 5/high, no worker | 194,781 | 15.55 s | 29 visible + 7 hidden cases |
| B | Fable 5.1/Ultracode; Sonnet 5/medium writer; Opus 5/high reviewer | 753,508 | 229.20 s | 29 visible + 7 hidden cases in worker and coordinator checkouts |

All accepted diffs compute the subtotal once, pass that value to the existing
tax helper, and derive tax by subtraction. Direct source review confirmed no
materialization or changed helper behavior. Both tracked and untracked user
sentinels survived; immutable fixture files matched their original hashes.
Native Workflow actually ran two workers. Review returned no supported code
finding; no correction worker ran. The reviewer initially produced an invalid
structured output missing required fields, then succeeded. That retry is retained
in the usage total.

The native final `modelUsage` included coordinator, implementation and review
models. Independently deduplicated worker message usage exactly matched those
worker entries. Count the last cumulative result once, including cache-read,
cache-write, ordinary input and output categories; do not add child totals or
thinking tokens a second time. The two sessions total **948,289 reported tokens**.
These are subscription telemetry counts, not additional charges or measured
end-to-end savings. Codex preparation, independent audits, reporting and the
separate recovery exercise are outside this comparison denominator.

Retained protocol failures matter independently of passing code tests:

- Both arms piped some test output through `tail`, obscuring pytest's exit status.
  The failure text was retained, and independent unpiped before/after checks
  supplied actual exits and acceptance.
- B had `workflow-authoring` available but never invoked or loaded it as requested.
  Its native Workflow ran successfully; the required procedure still failed.
- B read its persisted native script and journal outside the literal fixture-only
  read boundary. This was an overstrict boundary for the chosen native procedure,
  not evidence of filesystem isolation. Recovery explicitly permits its own
  saved script and journal.

No replacement or counterbalanced comparison was dispatched. The prepared extra
checkouts remained unused. See the [comparison receipt](../evidence/artifacts/native-workflow-writing-recovery-20260921/comparison.json).

## Recovery qualification

The separate recovery task uses the same original fixture in disposable owned
worktrees. Its native interactive prompt enters through `/workflow-authoring`;
the persisted session records the native slash command followed by the bundled
reference injection before authoring. This directly resolves the comparison's
source-loading gap for recovery without silently rewriting the earlier result.

A Sonnet/medium worker repairs the fixture and records a local checkpoint only
after tests pass. An Opus/high reviewer checks the actual source, then waits on
an operator-controlled local gate. The operator stops the selected reviewer in
the native `/workflows` view, relaunches the unchanged script with
`resumeFromRunId`, then exits through native **Exit and stop tasks** while the
restarted reviewer waits. The final invocation uses `claude --resume` with the
same session ID. New user edits are deliberately added while the coordinator is
stopped. The observed results were:

- The selected reviewer became a failed child, with `review: null`; the script
  itself reported `completed` because it returned that failure object. The
  waiting process exited and the accepted implementation hash stayed unchanged.
- Native replay reused the completed implementation. A restarted reviewer reached
  the gate. Native exit returned zero and all four recorded owned process IDs
  disappeared, including the blocked helper.
- `--resume` restored the same session and Workflow run. The native journal
  records one implementation start and three review starts across three launches.
  The third reviewer completed with no findings. Integration changed only the
  intended source file; both checkouts passed 29 visible and seven hidden cases.
- The operator intentionally replaced both sentinel files while the coordinator
  was stopped. Initial sentinels passed the earlier checkpoint; the new sentinel
  hashes passed final checks. Equality across that deliberate mutation is not
  claimed.
- The independent local ledger records one implementation invocation and three
  reviewer invocations, with one created effect for each phase. All recorded
  helper processes and the owned native CLI had exited at final inspection.
  Disposable worktrees are retained for audit; their deletion is not claimed.

Recovery's final native cumulative total is **2,143,696 reported tokens**, including
the stopped attempts and resumed requests. Its first resumed result restored the
earlier model counters with zero new-turn usage. Deduplicated persisted message
records account for 1,937,995 tokens, leaving an unexplained positive difference
of 205,701 (205,454 Fable; 247 Opus). Both views are retained, without summing
them, and complete reconciliation remains false. Across this task's four native
CLI invocations, the comparison plus recovery reports **3,091,985 tokens**;
Codex preparation, independent review and reporting are outside that total.
See the [recovery receipt](../evidence/artifacts/native-workflow-writing-recovery-20260921/recovery.json).
The [scoped experiment record](../evidence/artifacts/native-workflow-writing-recovery-20260921/experiment.json)
marks both pilot arms as procedural failures and qualifies only the observed
graceful recovery behavior. Its usage coverage remains partial.

The local effect probe records every invocation separately from its exclusive
effect file, so an idempotent file create cannot conceal a repeated worker.
These are disposable filesystem effects, not an external service's exactly-once
guarantee. Graceful native exit/resume is distinct from an OS crash, reboot,
network loss or provider-side cancellation.

## Native commands and retained scope

The private receipts preserve exact absolute paths and arguments. Portable forms
of the observed native entry points are:

```sh
claude -p --model opus --effort high --max-turns 20 \
  --output-format stream-json --verbose --include-hook-events \
  --permission-prompts none
claude -p --model fable --effort ultracode --max-turns 20 \
  --settings examples/claude-native/ultracode.settings.json \
  --add-dir "$OWNED_WORKER" "$OWNED_ARTIFACTS" \
  --output-format stream-json --verbose --include-hook-events \
  --permission-prompts none
claude --model fable --effort ultracode --session-id "$OWNED_SESSION"
claude --resume "$OWNED_SESSION" -p --model fable --effort ultracode \
  --output-format stream-json --verbose --include-hook-events \
  --permission-prompts none
```

The actual recovery launch also supplied the scoped settings/additional paths,
native screen-reader option and a display name. Its positional prompt began
with `/workflow-authoring`. The installed native account and permission mode
were inherited; no API credential, gateway, global permission change or model
fallback was introduced. A disposable folder trust/import prompt was accepted
for the fixture. Explicit task limits constrain behavior; they are not an OS
sandbox. The existing upstream CLI was supervised only to capture output and
retire its owned process group, using the existing repository runner's cleanup.

All test invocations use an existing absolute Python executable with
`-m pytest -q`; they do not rely on a prepended PATH surviving native Bash.

## Scheduling is a separate qualification

Current Claude `/loop` and Cron tasks are session-scoped and fire while the
session is running and idle. Resume restores eligible Cron tasks, with exceptions
for expired recurring tasks, past one-shot tasks and self-paced loops. Desktop
tasks and cloud routines are separate scheduling paths. These are current
source contracts, not scheduling runs performed here. [Native scheduling documentation](https://code.claude.com/docs/en/scheduled-tasks).

The existing Codex **Maintain native foundation and trading catalogs** heartbeat
was inspected as ACTIVE with a daily 9 a.m. schedule. Its persisted registration
is distinct from a native Claude session loop. This task did not mutate or
duplicate either scheduler. A saved registration, manual wake, or successful
Workflow resume does not prove a scheduled fire after app/host restart.

## Native sources and remaining boundaries

The source procedures are the installed Claude Code 2.1.278 Workflow tool,
bundled workflow-authoring skill and [official workflow
documentation](https://code.claude.com/docs/en/workflows). The existing
[Ultracode recipe](../recipes/claude-native-ultracode.md) supplies native model,
session and tool assumptions. Native `/loop`/Cron lifecycle and the existing
Codex maintenance heartbeat are inspected separately; this qualification does
not register, duplicate or modify either automation.

Raw native streams, scoped session journals, terminal recording and exact
machine paths remain private. Compact receipts preserve their hashes and
sanitized observations. This is a local integration qualification on the
observed client/account, not an upstream test-suite result or a universal
foundation certification.

An [independent review](../evidence/artifacts/native-workflow-writing-recovery-20260921/independent-review.json)
rechecked original sources, native records and final acceptance, with no
unresolved material finding after the limitations above were retained. The
scoped convergence validator accepts all three observations; catalog and
foundation validation also pass. Shared receipt registration and final
publication validation belong to the integrating coordinator.
