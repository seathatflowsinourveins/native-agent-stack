# A landscape candidate is finalized by its vendor's clean install and native use

Date: 2026-10-07. Lane: foundation. Status: decided by the command center on the
owner's direction of 2026-10-07; repository record awaiting independent
cross-family review.

## Context and authority

The [6 October decision](2026-10-06-upstream-evidence-over-local-evaluation.md)
made upstream evidence the selector of foundation components and limited local
evidence to an integration smoke check and organic counters.

On 7 October the command center went beyond it. From zero-call counts and
three-run paired checks it adopted dated exclusions for five tools and gave the
other tools "interim" verdicts with checks due one and two weeks later. The
owner rejected both the same day, before anything was removed from the host.
His direction is paraphrased here from the command center's private item
`coordination/command-center/ITEM-ns2604-coop-20261007T164615Z.md`
(SHA256 `afbd5e059d2c4e94d4be95627669de06fbdefeb5d3ce335d16bacf74adbe85ae`):
a candidate that the landscape names is installed cleanly from its upstream by
the vendor's official installer and kept; the install is evaluated against
upstream and finalized now; nothing is gated on checks dated weeks ahead. This
record contains no verbatim quotation of the owner.

The exclusions were also unsound on their own evidence. Three of the five tools
had never been installed the vendor's full way: SocratiCode had a server
registration only; Headroom was registered against a placeholder proxy address;
jCodeMunch was wired through this repository's instruction text and role files
rather than its installer's own integration. Zero use from a partial install is
an install gap, not a result about the tool.

The action served is completing the native foundation for US-equities research
and historical simulation, whose first unit after the start is the
data-integrity unit. The [trading rules](../../blueprints/us-equities/AGENTS.md)
and [paper policy](../paper-lane-policy.md) keep their own gates.

## Decision

1. **Selection is unchanged.** Upstream evidence selects a candidate for each
   job: the maintainer's organization, release discipline, tests, published
   benchmarks and fit with both clients. The landscape manifest names the
   candidates.
2. **A candidate is installed the vendor's way, in full.** Use the vendor's
   official installer at the maintained release and the vendor's whole
   documented route on each client (registrations, hooks, skills, agents,
   plugins, services), then run the vendor's own verification command. Where
   the installer offers options on where data goes, on self-update, or on model
   calls made on the user's sign-in, choose them deliberately; choosing a
   vendor option is configuration, not a patch.
3. **Readiness is unchanged.** READY needs the source-backed selection, the
   installation, a smoke check in each client and organic counters, exactly as
   the 6 October decision says. Nothing else is asked of a row.
4. **Zero or low use is an install gap first.** Compare what is installed with
   what the vendor's installer writes, complete it, and smoke it. No candidate
   is removed on the strength of our own short checks or call counts.
5. **A component leaves the stack for two reasons only.** The landscape
   replaces it with a better-evidenced upstream candidate for the same job, or
   its official install cannot work on this host, shown from the vendor's own
   sources. Either is recorded with its date and source.
6. **Two candidates for one job are settled by upstream evidence,** as rule 1
   says, not by a local contest.
7. **The monitor informs; it does not gate.** Invoke rates and spend are read
   per client and lane from the clients' own telemetry and published. The first
   request's input tokens of a fresh session are recorded before and after
   every change of the installed stack. A reading that looks wrong prompts an
   install repair or a landscape review. No landing, readiness row or start
   waits on it, and no component's status carries a future check date.
8. **A with-and-without check is evidence, not a verdict.** It may be run on
   fresh sessions when the monitor gives a reason: every difference between the
   arms listed from the launch commands, a mechanical oracle, three runs per
   arm, in an upstream harness where one fits. A check on the host's own client
   is labelled `local paired sessions`. Its result goes to the landscape
   review and decides nothing by itself.

## State on 2026-10-07

The records are private host state, named by path and SHA256. They are source
locators, not files added by this change.

- Fleet invoke manifest, twelve Codex lanes over the 348 minutes after the
  vendor hooks went live:
  `coordination/e2e-truth-20261006/lane-invoke-manifest-20261007T143800Z.json`
  (SHA256 `7b583fceee521fae4683f82d96b96bb672a39a31db693c639cc7f9374bb8fbaf`).
- Both clients' own server listings, read 2026-10-07T16:44Z: every registration
  named below is present; no hook handler names any of the last five rows.

| Component | Job | Install against the vendor's route | Use in the fleet window | State |
| --- | --- | --- | --- | --- |
| context-mode | context supply | plugin and hooks, as the vendor ships them | called by 12 of 12 lanes | final |
| RTK | command output | the vendor's global init | 89% of the lanes' Codex shell calls | final |
| ai-memory | durable memory | the vendor's installer on both clients | called by 10 lanes, fed by hook in 2 | final; its own upgrade to the release of 2026-10-07 follows |
| codebase-memory-mcp | code graph | registration, agents and hooks | called by 1 lane, fed by hook in 11 | final |
| Serena | code navigation | registration and the vendor's hooks | called by 5 lanes | final |
| qmd | document search | registration and the vendor's skill on both clients | called by 1 lane on Codex; none on Claude Code | final; routing on Claude Code to be completed from the vendor's guide |
| semble | code search | registration and the vendor's search agent | called by 1 lane | final; routing to be completed from the vendor's guide |
| jCodeMunch | code index | partial: wired through this repository's text, not the installer's integration | none | the vendor's full install is owed |
| Headroom | output compression | partial: registered against a placeholder proxy address | none | the vendor's full install is owed |
| SocratiCode | code search and graph | partial: a server registration only | none | the vendor's full install is owed |

The two code-search candidates stay installed until upstream evidence settles
the job under rule 6.

One measurement of 7 October stays on record as information for rule 7. On
three short tasks, 27 fresh Claude Code sessions answered equally well in three
arms; with the advisor off, the installed stack cost 1.5, 1.2 and 1.6 times the
no-stack arm on the main model, and a fresh session's first request was 46,866
to 50,499 input tokens with the stack against 35,230 to 35,293 without it
(`coordination/e2e-truth-20261006/stack-effect-claude-3arm-20261007T144045Z.json`,
SHA256 `1fbbac744db62d8d94e016b7743acb77863d198fb3e5a9f679d520ce7acd5449`).
These are short sessions on one client. The figure to watch is the first
request's size, which grows with every server and instruction file; it is why
the always-loaded instruction text is kept short.

## What this amends

- [Upstream evidence over local evaluation](2026-10-06-upstream-evidence-over-local-evaluation.md):
  rules 1 to 5 stand. This record adds how a zero is handled (rule 4), when a
  component leaves (rule 5) and what the monitor is for (rules 7 and 8).
- The five dated exclusions of 7 October (jCodeMunch, semble, SocratiCode,
  Headroom, and qmd on Claude Code) are withdrawn. They were never applied to
  the host.
- [Full-stack token owner default](2026-10-04-token-full-stack-owner-default.md):
  its owner defaults stay installed. Its two measurements for removing a
  component are replaced by rules 4 and 5.
- [Harness defaults](../harness-defaults.md): the section on adopting a
  capability points here.
- [Repository-quality rule](2026-10-04-repository-quality-rule.md): unchanged;
  it chooses among candidates for a job.

## What would overturn it

- The landscape manifest changing a job's candidate, which rule 5 already
  covers for that component.
- A vendor's official installer that cannot be run on this host without a
  change the owner has to approve. The component then waits for that approval.
- The owner withdrawing the direction. The 6 October rule then stands alone.

## SOTA sources

- This repository: the 6 October decision named above, which this record
  applies and extends.
- Anthropic, [Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
  (read 2026-10-07): beside accuracy, collect runtime, the number of tool
  calls, token consumption and tool errors; overlapping tools confuse the
  agent. This is why rule 7 reads use and cost, and why rule 6 keeps one
  candidate per job.
- Anthropic, [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  (published 2025-09-29, read 2026-10-07): find the smallest set of
  high-signal tokens. This is why the first request's size is recorded.
- Claude Code, [Monitoring](https://code.claude.com/docs/en/monitoring-usage)
  (read 2026-10-07): the client's own OpenTelemetry metrics and events for
  usage, cost and tool activity, which rule 7 reads.
- Each component's own installation guide at its release is the source for
  rule 2; the per-component packets cite the file and line.
