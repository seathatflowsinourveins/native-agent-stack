# Command center guide

Read this when a session acts as the command center of a host, or takes that
role over. It is loaded on demand and is not part of any client's startup text.
The tool choices behind it are decided in the
[orchestration composition record](decisions/2026-10-06-cc-orchestration-composition.md);
this guide says how the role is done with them.

## The role

One coordinator integrates. The command center decides and records, the lanes
do the work, and one named session lands pull requests.

It owns five things:

1. **Lane lifecycle:** starting, stopping, relaunching and assigning lanes, each
   in an owned worktree ([lanes](lanes.md)).
2. **Rulings:** decisions with their evidence, written as items and relayed.
3. **Landing cues:** a pull request lands only on the command center's explicit
   cue to the landing session, or by the command center itself while that
   session is out ([current role holders](#current-role-holders)).
4. **Tools windows:** every change of stored client configuration, hooks, hook
   trust, instruction files or services on the host.
5. **Evidence for the owner:** what new sessions call, what it costs, and how
   ready the foundation is, each read from records.

It never hands a lane a step that touches hook trust, permissions or stored
configuration. Those are the command center's own acts, and only under a direct
owner instruction. Credentials and sign-ins, spending, retiring a host, live
trading and model choices are the owner's alone; the command center does not
take them either ([secret storage](secret-storage.md)).

## Current role holders

These assignments name sessions and lanes, so they change. Each change is
ruled, recorded in the coordination ledger and carried into this section by the
next pull request. As of 2026-10-09:

- **Landing.** The landing session is out until its usage window resets at
  2026-10-12 09:00 UTC. Until then the command center lands, under the landing
  session's rules unchanged: an explicit cue, one rebase at the landing turn,
  the checks read at that head, the cross-family read and, where it applies, the
  trading acknowledgement. Pull requests in another host's session custody stay
  parked until that custody is transferred.
- **Trading acknowledgement.** A pull request that touches trading work
  (research, data acquisition, strategy gates, decision registration, paper or
  broker operation; [trading lane rules](../blueprints/us-equities/AGENTS.md))
  lands only with the trading acknowledger's acknowledgement at its final head.
  While the landing session is out, the paper-operation lane (`paper-open-e2e`)
  gives it.
- **Holdout custodian.** The command center holds the north-star study's
  prospective holdout. It seals the frozen model before the holdout opens, and
  on each trading day it commits that day's rank rows by SHA-256 before 09:25
  America/New_York, so no row can be revised after the open. Lanes produce the
  rows; they never hold or reseal the custody record.
- **Cross-family review gate.** A head is read by the other model family before
  it lands. A Codex-authored head (a `codex/` branch) gets the command center's
  Claude read; a Claude-authored head (a `claude/` branch) gets the co-op's GPT
  read. The branch prefix decides the family, not custody. A read names the head
  it read, and a later push needs a micro-read of the delta. Each family's
  precision is tracked. Lanes never start headless Claude runs to get a read of
  their own: a run on the shared subscription spends every session's usage
  window. The vendor paths are the Claude Code GitHub Action
  ([`claude-pr-review.yml`](../.github/workflows/claude-pr-review.yml), in the
  [GitHub automation guide](github-automation.md)) and `codex review`.
- **Co-op.** The session that orchestrates the lanes dispatches workstream
  slices to them, keeps the read queue in landing order, runs the GPT reads and
  tracks the program's exit criteria in one file. It messages the command center
  only for decisions, landing cues, incidents and owner items; progress goes to
  the lanes' status files.
- **API keys.** The Anthropic API keys are spent on demand, on work the
  subscription cannot carry and on north-star work first; spend never caps
  quality. A key reaches one command at a time through the credential runner
  (`tools/credentials/credential_run.py`, [secret storage](secret-storage.md))
  and is never set in a session's environment. When a key runs out of credit,
  work fails over to the next key in a fixed order. Claude Code sessions stay on
  the subscription.

## Decide from evidence

A question that upstream sources and recorded evidence can settle, and that is
already inside the command center's authority, is decided, recorded and
relayed instead of being handed back to the owner. This widens nothing: an act
reserved above stays reserved however clear the evidence is. Check a capability
claim in the order of the
[harness defaults](harness-defaults.md#check-a-capability-claim-in-order):
the installed client, its changelog for that version, its source at that tag,
then its documentation. How a candidate is installed and finalized follows the
[clean-install decision](decisions/2026-10-07-clean-upstream-install-finalizes-a-candidate.md).
Record a correction the same turn it is found.

## Where each answer comes from

| Question | Source | Read it with |
| --- | --- | --- |
| Which lanes are live, and in what state | the lane messenger's own instance list | `hcom list --json` |
| Which Claude Code sessions are live | the client | `claude agents --json --all` |
| What a lane says it is doing | the lane's own status file | its latest headed section |
| What is waiting on a decision | the coordination ledger | rows since the last read, decision rows first |
| What each lane or session called | both clients' OpenTelemetry events in the log store | one query set pinned to a single evaluation time |
| What it cost | both clients' own token and cost counters in the metrics store | the same window; counter classes are never summed |
| What a single session did | the session archive | agentsview, by session |
| Whether a pull request is green | GitHub | `gh pr checks <number>`, read by the command center itself |
| Whether a tool is current | the tool's own version command and its vendor's latest release | one read per vendor repository |

The [dashboard guide](../observability/grand-dashboard/README.md#checkpoint-and-observation-rules)
gives the observation rules, and the
[session handbook](token-session-handbook.md) each tool's own verification
command. A telemetry label names the lane; a session with no label is mapped by
a recorded roster, never by guess.

## Direction and messages

The owner retired the standing-delegation protocol (item files with envelopes, SHA256-carrying ledger rows and the `standing-delegation` skill's checks) on 2026-10-08.

Batch rows: at most one row to the orchestrating session per quarter hour, with
decisions, failures and owner asks marked as such. In a fix dispatch, list every
finding by number and check the count.

## Dispatch

Choose the cheapest mode that fits the work: the coordinator alone, one
subagent, a bounded workflow, or an agent team
([workflow mechanics](../examples/claude-native/workflows/README.md),
[dispatch and spend](decisions/2026-10-04-coordinator-dispatch-and-spend.md)).
Fan-out research goes to the GPT lanes. A reviewer is given the artifact, not
the conclusion.

## Landing

- The landing session lands on an explicit cue, in the same turn the cue's
  conditions are met: the landing read, the checks read by the command center
  at that head, and the line fields.
- A head is rebased once, at its landing turn. A head that already sits on
  main's tip and has a passing hosted run needs no second full run.
- Main's own version of every test file a pull request modifies is run against
  the head. Additions that leave main's version passing need nothing. A changed
  expectation is declared test by test with the record that rules it; an
  undeclared failure blocks. An assertion is relaxed only by a ruling.
- The [GitHub automation guide](github-automation.md) carries the required
  checks; a rule that reviewers apply by hand is moved into a required check as
  soon as it is stable.

### Codex cloud review thread triage

Before declaring a head landing-ready under the command center's standing cue,
the lane reads every `chatgpt-codex-connector` review thread on that pull request
and records its disposition. Codex cloud review remains enabled; this step uses
the [official GitHub review integration](https://developers.openai.com/codex/integrations/github)
and GitHub's existing conversation controls.

Read the PR head SHA and all review threads, including resolved and outdated
threads, in GitHub or through the native `gh api graphql` interface. Match the
connector's author login, including its `[bot]` spelling when returned. With the
API, finish every `reviewThreads` page and every thread's `comments` page;
`first: 100` alone is not a complete read. The native
[gh pagination contract](https://cli.github.com/manual/gh_api) requires the
cursor and `pageInfo` for the connection being paged.

For every connector thread, retain its original comment URL, the current landing
head SHA (and the original reviewed commit when returned), and one of these
dispositions in the lane's landing record:

| Disposition | Evidence the lane records |
| --- | --- |
| `fixed` | The fixing commit or file/line, the change that answers the finding and its relevant check. |
| `replied` | A substantive answer in that thread and its reply URL; name any remaining work. A reply alone does not resolve a finding. |
| `not-applicable` | A reason grounded in the actual code or scoped contract, with the supporting reference and an answer in the original thread. |

Record answers with native replies; use **Resolve conversation** only after the
finding's disposition is justified. An outdated flag, a bot summary, a resolved flag or
green CI does not supply that justification. Hold a thread with a remaining
valid finding; do not mark it resolved merely to clear the merge condition.
If no connector thread exists, record `0` after the complete read.

Re-read the PR head and all review threads and comments immediately before the
landing-ready declaration: the head must match the triage record, every connector
thread must have its current disposition and every review thread must be resolved.
A new push, review thread or comment requires an updated read. GitHub's native
[GraphQL pagination](https://docs.github.com/en/graphql/guides/using-pagination-in-the-graphql-api)
and [conversation-resolution controls](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/commenting-on-a-pull-request#resolving-conversations)
carry the thread state; this procedure adds no workflow, bot or ruleset change.

## Tools windows

A window script is read before it runs: a dry run in every flag combination,
every read-only assertion executed, and an independent review. Each step has a
backup, a read-back and an inverse, and can be skipped by name. A step that has
not passed its reads moves to the next window. Never edit a running script in
place. After a window, record the first request's input tokens of one fresh
session per client, so the window's effect on context is a number.

## Evidence the command center publishes

- **Invoke evidence:** which installed tools new sessions and working lanes
  call, per client and lane, with the paired checks.
- **Roadmap and readiness:** the dated road to the research start, the board by
  layer, each lane's state and next step, spend, and versions against each
  vendor's latest release.

Both are built by a script from named records, with each record's SHA256 on the
page. A figure that is not in a record is not on the page. Times are given in
the host's local zone first with UTC beside them, read from the clock.

## Taking over

1. Read this guide (its current role holders first), [lanes](lanes.md) and the
   decisions of the last three days.
2. Read the ledger's tail, the lanes' status files and the live lane list.
3. Query the shared memory for maintained decisions before describing the
   deployed architecture.
4. Rebuild the live lane record and compare it with the last published roadmap.
5. Re-arm the watches on the ledger and on lane lifecycle.
6. Name the north-star action the next unit serves, then act.
