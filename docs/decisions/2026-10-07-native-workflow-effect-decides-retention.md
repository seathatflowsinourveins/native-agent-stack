# An installed component stays for its effect on the native workflow

Date: 2026-10-07. Lane: foundation. Status: decided by the command center on the
owner's direction of 2026-10-07; repository record awaiting independent
cross-family review.

## Context and authority

The [6 October decision](2026-10-06-upstream-evidence-over-local-evaluation.md)
made upstream evidence the selector of foundation components and limited local
evidence to an integration smoke check and organic counters. Applying it on
7 October showed two things it did not settle.

- Three tools had a measured paired outcome, three runs per arm, and none
  won: Serena forced into view, qmd named in the task on Claude Code, and
  Headroom on a raw log.
- Two tools had an organic observation after their vendor wiring was in place:
  semble was visible and was not chosen in fresh sessions, and jCodeMunch
  showed no call on either client.
- One tool had a wiring gap: SocratiCode showed no call, and its vendor's
  documented route had never been installed.
- A three-arm check of the whole installed stack on fresh Claude Code sessions
  returned the same answers at higher cost and time, and the advisor model was
  the largest single cost.

The owner's direction of that day is paraphrased here from the command center's
private items `coordination/command-center/ITEM-ns2604-coop-20261007T142046Z.md`
(SHA256 `5c54c05009c5605e2f90fccb94b480121e1e16f374110b8c69d29dae223a5c74`) and
`ITEM-ns2604-coop-20261007T144411Z.md`
(SHA256 `09e4b11b21e1a824ba5324ac69b91e4e55daec1e5d14855a2c89c338456b5e2f`).
Components are installed cleanly and without overlap. A component is judged by
its upstream commands end to end, by how often new sessions call it, and by
whether it improves the native workflow of a new session. It is kept only for a
real, monitored effect on quality and efficiency. Open questions that evidence
can settle are decided from upstream sources and recorded evidence. This record
contains no verbatim quotation of the owner.

The action served is completing the native foundation for US-equities research
and historical simulation, whose first unit after the start is the
data-integrity unit. The [trading rules](../../blueprints/us-equities/AGENTS.md)
and [paper policy](../paper-lane-policy.md) keep their own gates.

## Decision

1. **Selection is unchanged.** Upstream evidence selects a component: the
   maintainer's organization, release discipline, tests, published benchmarks
   and fit with both clients (rule 1 of the 6 October decision).
2. **Installation is unchanged, and wiring is the vendor's.** Install the
   maintained release by its documented command. Wire it on each client by the
   vendor's own mechanism (hooks, skills, a plugin or a server registration) and
   run the vendor's own verification command.
3. **Readiness is unchanged.** READY still needs the source-backed selection,
   the installation, a smoke check in each client and organic counters. The
   check in rule 5 never gates READY and reopens no superseded campaign.
4. **A zero is a wiring defect first.** Organic use is read per client and per
   lane from the clients' own telemetry. When an exposed tool shows no call,
   repair the wiring by the vendor's mechanism and smoke it. A tool that still
   shows no call after that is excluded with a date.
5. **Retention is decided by effect on the native workflow.** An installed
   component stays in the default stack when a bounded check (below) shows it
   improves a fresh session's work, or at least does not cost more for the same
   answers. Until that check exists the component is interim, with the date the
   check is due.
6. **One component per job.** Two components that do the same job do not both
   stay. A stack of several components for one job stays only when it beats its
   best member in the bounded check and every member shows organic use.
7. **Each component carries one verdict.** `keep`, `interim` or `excluded`,
   recorded with its date, its evidence and what would overturn it. The command
   center adopts a verdict from recorded evidence and reports it. Removing a
   component from a host is a separate, reversible step in a tools window. When
   an owner decision installed the component, the exclusion is reported to the
   owner before the window that removes it.
8. **The verdict stays on the monitor.** Invoke rates and spend are read from
   the clients' own telemetry on a schedule and published. The first request's
   input tokens of a fresh session are recorded before and after every change of
   the installed stack, and that number does not grow without a recorded reason.
   A verdict reopens when the monitor contradicts it or when upstream ships a
   release that changes the wiring.

## The bounded check

- **Arms.** The client as installed, against the same client with only the
  component under test switched off for that session by the client's own
  per-session options. For a whole-stack check the second arm is the client
  without the installed stack. Before a result is read, every difference
  between the arms is listed from the launch commands themselves, and an arm is
  added for each difference that is not the thing under test.
- **Tasks.** At most three fixed tasks whose text names no tool, each with a
  mechanical oracle written before the runs.
- **Runs.** Three fresh sessions per arm and task. No retries.
- **What is read.** Correct items, model responses, tokens or the client's own
  cost estimate, wall time, and the calls the component itself made. A win is
  equal or better correctness for fewer responses, tokens or time, with the
  component's own calls doing the work.
- **Harness.** Where an upstream harness fits the component class, it runs the
  check: the skill-creator paired benchmark for a skill; promptfoo for a
  gateway, a model route or headless client sessions (one provider per arm, one
  test per task with literal assertions, `--repeat 3`); Harbor or Inspect for a
  containerized agent task; the vendor's own evaluation runner or a public
  benchmark harness for a memory or retrieval system. No runner of our own is
  kept. The promptfoo form for headless client sessions has not been run in
  this repository yet; it is an untested boundary until its first check, and
  that check's record says whether it reproduced a result of 7 October.
- **Evidence class.** A check on the host's own installed client is
  `local paired sessions`. It is never reported as upstream-harness acceptance,
  and a saving is never claimed from it beyond the tasks it ran.
- **Bound.** One check per component and client per release. It is not a
  campaign, and no landing or readiness row waits for it.

## First application, 2026-10-07

The records are private host state, named by path and SHA256. They are source
locators, not files added by this change.

- Fleet invoke manifest, twelve Codex lanes over the 348 minutes after the
  vendor hooks went live:
  `coordination/e2e-truth-20261006/lane-invoke-manifest-20261007T143800Z.json`
  (SHA256 `7b583fceee521fae4683f82d96b96bb672a39a31db693c639cc7f9374bb8fbaf`).
- Whole-stack check on Claude Code, three arms, three tasks, 27 sessions:
  `coordination/e2e-truth-20261006/stack-effect-claude-3arm-20261007T144045Z.json`
  (SHA256 `1fbbac744db62d8d94e016b7743acb77863d198fb3e5a9f679d520ce7acd5449`).
- Paired checks: `paired-alwaysload-serena-intent-20261007T093838Z.json`
  (SHA256 `77fd69e2d2ffb1bb6f9a7b8557bac3c01dde92966c0450a6ecc2b66b33e28f23`),
  `paired-qmd-named-docs-20261007T101636Z.json`
  (SHA256 `c9f2c1fac73bcc3cc2c324860aaf2dddcda841793740d3ddefdd10ca3e615bc2`),
  and `coordination/ns2604-coop/lanes/overlap-token-durable/headroom-pair-b-20261007T105126Z/RESULT.md`
  (SHA256 `75ef77c1510f6aaa26840e458a96adc6280544b79e38fd55ac23f1e521300729`).

The whole-stack check: all 27 answers were fully correct. With the advisor off,
the installed stack cost 1.5, 1.2 and 1.6 times the no-stack arm on the main
model for the three tasks and took 1.9, 1.3 and 1.8 times as long. A fresh
session's first request was 46,866 to 50,499 input tokens with the stack and
35,230 to 35,293 without it. Seven of nine as-installed sessions called the
advisor, and in all seven it cost more than the main model's whole session.
These are short sessions; the check says nothing about long sessions or
subagents. This first application ran as plain launch scripts with a grading
script; from this record on the check is a harness configuration as stated
above.

| Component | Job | Organic use | Bounded check | Verdict |
| --- | --- | --- | --- | --- |
| context-mode | context supply | called by 12 of 12 lanes; did the work on the large-output task in every fresh session | whole-stack check only | interim |
| RTK | command output | 89% of the lanes' Codex shell calls | none yet | interim |
| ai-memory | durable memory | called by 10 lanes, fed by hook in 2 | none yet; a scored comparison on a public benchmark harness is being prepared | interim |
| codebase-memory-mcp | code graph | called by 1 lane, fed by hook in 11 | none yet | interim |
| Serena | code navigation | called by 5 lanes | forced into view: called every time, answers no better, cost higher | interim, as wired |
| qmd | document search | called by 1 lane; fresh Codex sessions call it on document tasks; none on Claude Code | named in the task on Claude Code: no win | interim on Codex; excluded on Claude Code |
| semble | code search | called by 1 lane; none in fresh sessions | visible and still not chosen | excluded |
| jcodemunch | code index | none | not reached | excluded |
| Headroom | output compression | none | more tokens than context-mode alone in every paired run | excluded |
| SocratiCode | code search and graph | none as wired; the vendor's documented route was not installed | not reached | not selected (see below) |

Each exclusion is dated 2026-10-07. It is overturned by a new upstream release
or a vendor-route installation that shows organic use on the client concerned
and a bounded-check win against the component that now does the job.

SocratiCode's row is a selection ruling under rule 1, not a retention verdict
under rule 4, because its vendor route was never installed and so rule 4's
repair step never ran. The code-search job keeps no additional component for
now: on the find-by-intent task every arm answered fully and the arm without
any stack tool was the cheapest, so no gap is shown that a second search tool
would fill. Its registration is removed as an arm of the comparison that the
6 October decision superseded. The ruling is overturned by a task class on
which the arm with no additional component fails or costs more than a
vendor-wired candidate.

Due dates for the interim rows, as rule 5 requires:

| Row | Check | Due |
| --- | --- | --- |
| context-mode, codebase-memory-mcp, Serena, qmd on Codex | one component removed at a time, on the task where it was called most | 2026-10-14 |
| RTK | a paired check on Codex, where it carries the shell traffic | 2026-10-14 |
| ai-memory | a scored comparison of the memory candidates on a public benchmark harness | 2026-10-21, or a dated re-date in the comparison's own record |
| the stack as a whole | one long-session check | proposed after the board review of 2026-10-08, dated in its own record |

The monitor of rule 8 is read once a day and at every change of the installed
stack.

## What this amends

- [Upstream evidence over local evaluation](2026-10-06-upstream-evidence-over-local-evaluation.md):
  rules 1 to 5 stand. This record adds retention (rules 5 to 8 above) and the
  bounded check, which is not one of the campaigns that record superseded and
  does not gate readiness.
- [Full-stack token owner default](2026-10-04-token-full-stack-owner-default.md):
  its two measurements for keeping or removing a component are now the organic
  use of rule 4 and the bounded check of rule 5. Its owner defaults stay
  installed until a verdict is reported and a window removes them.
- [Harness defaults](../harness-defaults.md): the section on adopting a
  capability points here for retention.
- [Repository-quality rule](2026-10-04-repository-quality-rule.md): unchanged;
  it chooses among candidates, this record decides whether an installed one
  stays.

## What would overturn it

- An upstream-harness result on long sessions or subagents that contradicts a
  verdict reached on short sessions. The verdict then follows that result.
- A bounded check that cannot tell a useful component from a useless one on
  known cases. The check is then replaced by the upstream harness that can.
- The owner withdrawing the direction. The 6 October rule then stands alone.

## SOTA sources

- Anthropic, [Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
  (read 2026-10-07): beside accuracy, collect runtime, the number of tool
  calls, token consumption and tool errors; more tools do not always lead to
  better outcomes; overlapping tools confuse the agent; held-out tasks guard
  against overfitting an evaluation.
- Anthropic, [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  (published 2025-09-29, read 2026-10-07): find the smallest set of
  high-signal tokens that maximizes the likelihood of the desired outcome.
- Claude Code, [Monitoring](https://code.claude.com/docs/en/monitoring-usage)
  (read 2026-10-07): the client's own OpenTelemetry metrics and events for
  usage, cost and tool activity, which rule 8 reads.
- promptfoo at the installed release: `promptfoo eval --help` lists `--repeat`
  and a provider given as the path of a custom module. The repository holds one
  configuration of that form,
  `blueprints/native-skill-practice/p1/promptfooconfig.yaml`, which calls itself
  a skeleton and has not been run against a model; it shows the form, not a
  result.
- This repository: the 6 October decision named above, and the Harbor result
  recorded in [the token layer default](2026-10-04-new-wsl-token-layer-default.md)
  (36 tasks; no tool reduced whole-task cost), with which the 7 October check
  agrees in direction.
