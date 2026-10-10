# Pre-cue read of a pull request by Anthropic's pr-review-toolkit agents, in GitHub Actions — 2026-10-09

`claude-pr-toolkit-review.yml` runs two agents from Anthropic's `pr-review-toolkit` plugin, `pr-test-analyzer` and
`silent-failure-hunter`, on one pull request head, through `anthropics/claude-code-action` v1.0.247. A maintainer
dispatches it by hand from `main` with the pull request number and the exact head commit. Each agent reads the diff,
the changed files and the description, reports every finding with a confidence from 0 to 100, and lists every
behaviour and test change the description does not declare. A model-free step copies both reports to the job
summary; nothing is posted to the pull request. The output is an input to the command center before its cue, never
a designated read. It runs only while the repository variable `CLAUDE_PR_TOOLKIT_ENABLED` is `true`. Nothing in this
change starts a run or sets a variable.

## Why

The command center replayed the toolkit's agents on three defects that both designated first-pass reads had missed on
2026-10-08 (record `research/claude-side-20261008/review-replay/RESULT.md` in the coordination tree). Every catch came
from the explicit list of undeclared behaviour and test changes; no catch would have passed the toolkit's usual
80-confidence cut-off. The command center adopted the two agents as a pre-cue step (job J8), run locally on a second
Anthropic key. Those runs found, before any designated read:

- on #892 (4d0a14da): six behaviour changes its description and record did not name, and four overstated claims, all
  fixed before its reads;
- on #900 (f082159c): two high-severity defects in a verifier, where a malformed digest or a renamed contract path
  still reports PASS, filed as R3-F2. `pr-test-analyzer` ran out of time on that 200 KB diff; this workflow scales
  its time limit for that reason.

This workflow runs the same agents with the same settings inside GitHub, beside the other W4 workflows.

## What the workflow does, by name

The workflow is new, so this is all of its behaviour.

- Trigger: `workflow_dispatch` only, with inputs `pr_number`, `head_sha` and optional `paths`; a concurrency group
  per pull request, without cancelling a run in progress.
- Job condition: this repository (slug guard), the `main` ref, `github.actor` and `github.triggering_actor` both the
  repository owner, the first attempt of a run, and `CLAUDE_PR_TOOLKIT_ENABLED == 'true'`. A dispatch by anyone else,
  or a re-run, is skipped.
- `timeout-minutes: 45` for the job. Grants: `contents: read`, `pull-requests: read` and `id-token: write`.
- A guard step stops the job with exit 2 on debug signals, on a pre-existing `~/.claude/settings.json` (a dangling
  symlink included) or on a malformed input.
- A binding step stops the job with exit 2 unless the pull request is open, from this repository, targets `main` and
  has exactly the requested head. It keeps the title and description, as `pr-body.md`, for the agents, who are asked
  which changes the description does not declare; the rest of the pull request metadata is deleted.
- The head is checked out as data under `pr-head/` with main at the root. Right after that checkout, a model-free
  step, `Remove symbolic links from the pull request head`, runs
  `find pr-head -path pr-head/.git -prune -o -type l -exec rm -f {} +` under `set -euo pipefail`: Git checks a
  symbolic link out as a link, so one in the head could point the agents' file tools at a file outside the tree, such
  as the job's environment under `/proc` or the root checkout's `.git/config`. Every link goes, at any depth; regular
  files and the checkout's own `pr-head/.git` stay. The diff is written by git in the root
  only, with diff drivers off; an empty diff or one over 250,000 bytes is refused. The review step's time limit is 20
  minutes for a diff up to 100,000 bytes and 35 minutes above (a 59 KB diff took about 4 minutes of agent time; a
  200 KB diff did not finish in 15).
- The toolkit: `actions/checkout` of `anthropics/claude-code` at `602df92bf481ed904533e95c09f740f40aab5aed`, sparse
  to `plugins/pr-review-toolkit`. A model-free step checks the commit, moves it to `$RUNNER_TEMP/claude-code`, outside
  the workspace the agents' file tools can reach, verifies three files against SHA-256 values recorded here, and
  refuses a plugin that carries hooks, an MCP configuration or scripts:

  | File | SHA-256 | Git blob (matches GitHub's at the pin) |
  | --- | --- | --- |
  | `agents/pr-test-analyzer.md` | `d369fd3946a814bb7a9d4f32e971722fe259e301878986bc6312d6f6c56014a8` | `9b2de05b90e74f828e58a8874ed17f6eb9372db3` |
  | `agents/silent-failure-hunter.md` | `fa9b0daec5a267e7e66435cc48b3328301fc9f70c3af259fe248881327a1babc` | `b8a8dfa41e18ef6ac801ae64be38b2508aa04f44` |
  | `.claude-plugin/plugin.json` | `9435cc134fc72d56175f222894d401b0cf20f700d5bc0098c4257455314695ca` | `8e293aba91b721773a007919e935af7ce9c3048d` |

  Both agents declare `model: inherit`, so they run on the session's model, now Opus 5.5. An agent that one of them
  starts in turn runs on the model its own Agent call names: in J8 #894 the two agents each started one, both naming
  `haiku`, and the run's usage lists `claude-haiku-5-5` beside the session's model. Pinning the subagents' model
  stays follow-up F-08.
- The action step pins `ACTIONS_STEP_DEBUG: 'false'` and sets `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS: '0'`: in
  `-p` mode Claude Code runs Agent-tool subagents in the background and stops background work after 10 idle minutes
  unless that variable is set, which cut a 607 s pilot; the step's own time limit bounds the wait instead. It passes
  `show_full_output`, `display_report` and `track_progress` as `'false'`, the last two their defaults (the pinned
  `action.yml`, lines 136-139 and 152-155).
- `claude_args`: `--model claude-opus-5-5`, `--effort max`, `--max-turns 12`, `--max-budget-usd 22`, `--tools` and
  `--allowedTools` Read,Glob,Grep,Agent, `--restricted`, `--permission-prompts none`, `--setting-sources user`,
  `--strict-mcp-config`, `--plugin-dir` at the moved toolkit, `--settings` with hooks and auto memory off,
  `claudeMdExcludes` for `pr-head` and the deny rules, and `--add-dir` for the diff directory. The action's own parser
  (`base-action/src/parse-sdk-options.ts` at the pin) keeps `--plugin-dir` as a pass-through argument to the CLI.
- A numbers step (`id: numbers`) checks the bounds and an artifact keeps `usage.json` (numbers only) for 14 days. The
  bounds: every result record is accepted, that is, each is a success without `is_error`, or a budget stop
  (`error_max_budget_usd`) after both agents handed back their reports, and any other error subtype fails; the session
  start record lists its tools and MCP servers; no tool outside Read, Glob, Grep and the Agent tool (which the session
  reports as `Task`), and no entry in that list that is not a string; no MCP server; the coordinator called both
  toolkit agents, each at least once (a retry is allowed), and no other agent; 1 to 12 coordinator turns, counted as
  distinct assistant message ids without a parent
  tool use, because the agents' own turns are theirs; a client cost estimate, the highest any result record reports,
  of at most $24.20, the $22 budget times the measured overrun factor 1.10 (Cost of one run), whether or not the run
  ended in a budget stop; a cache read, checked only when the usage is complete; result text; and both agents'
  handbacks. A handback counts only as a `SubagentHandback` message whose parent is the coordinator's Agent call for
  that agent, once per agent however many calls it had, and it is required whatever the result records say; headings
  in the coordinator's relay never count (R6). The step holds the budget and
  the bound as `budget=22 cost_bound=24.2` and passes both to jq. The step names every bound it finds unmet. The
  costliest result record also supplies `models`. With background agents the client emits several result records, and
  the last can be an empty
  idle tick, so the coordinator's relay is the last result with text. The report step never publishes that relay
  (R6): it publishes each agent's own `SubagentHandback` message from the execution file, pr-test-analyzer's then
  silent-failure-hunter's, each under its own heading, and for an agent called more than once its last handback; it
  runs only after both agents handed back. In J8 #894 the
  coordinator hit `--max-budget-usd 5` (`error_max_budget_usd`) after both agents had handed back their full reports,
  and never relayed them. All three J8 streams so far (#892, #900, #894) carry `SubagentHandback` calls.
- `usage.json` holds `complete`, `total_cost_usd` (the highest over the result records), `num_turns` (the highest
  over the result records, not their sum: J8 #894's five records hold 3, 1, 0, 1 and 0), `assistant_turns`,
  `result_chars`, `report_source` (`handbacks` when any agent handed back, and otherwise `relay`, the relay then
  measured for the record only), `report_sections` (the agents' sections in that text; no longer a bound since R6),
  `agents_called` (the coordinator's Agent calls, sorted, each
  either one of the two toolkit agents or `other`, a retried agent listed once per call), `handbacks` (how many of
  the two agents handed back),
  `result_subtypes`, `tools_listed`, `successful_result` (every result record accepted, as above, whether or not its
  usage was usable), `session_started`,
  `claude_code_version`, `tools`, `forbidden_tools` (each disallowed tool name, and `non-string tool entry` for each
  entry that is not a string), `mcp_servers`, `models` (from the result record with the highest cost) and
  `lower_bound_models`. When there is no result record, or one without a whole cost, turn count and model usage,
  `complete` is false, the cost and turn count are null, `models` is empty, and `lower_bound_models` holds the
  assistant messages' input, output, cache-read and cache-write tokens per model, each message id counted once,
  as a lower bound; the step then fails. An execution file with neither result usage nor assistant usage leaves no
  record.
- The job summary's numbers table shows `none` for a missing cost or turn count, a line
  `Result records: <subtypes>. Agents called: <agents>. Handbacks: <n> of 2.`, and one row per lower-bound model,
  marked `(lower bound from the assistant messages)`. When a result record is a budget stop it adds
  `Budget stop: the client stopped the run at its 22 USD budget (error_max_budget_usd), with <n> of 2 handbacks.`, and
  when the cost is above the bound it adds `Over the cost bound: the client cost estimate is <x> USD, above 24.2 USD
  (the 22 USD budget times its measured overrun factor 1.10).` The failure messages added in R5 are
  `no result record, or one without usable usage: the token counts kept are a lower bound from the assistant messages,
  without a cost`; `the run did not end in success, or in a budget stop after both agents handed back (result
  records: <subtypes>; handbacks: <n> of 2)`, which replaces `the run did not end in success`;
  `the coordinator did not call both toolkit agents and no other agent (agents called: <agents>)`; and
  `client cost estimate <x> USD, above the 24.2 USD bound (the 22 USD budget times its measured overrun factor 1.10)`,
  which replaces `..., above 7`. R6 replaces `<n> of 2 agent reports`, which counted headings, with
  `<n> of 2 agent reports handed back`, which counts handbacks.
- The reports go to the job summary only when the numbers step succeeded: the publish step's condition is
  `!cancelled() && steps.numbers.outcome == 'success'`, not `success()`. The action fails its own step on a first
  result that is not a plain success, which includes a budget stop the numbers step accepts, and on a success whose
  `num_turns` exceeds `--max-turns`, a count the numbers step does not use. The job then stays failed with the reports
  published. A cancelled run publishes nothing (R6). The numbers step runs only when the action set an execution file,
  so its success implies one. The reports are capped at 60,000 bytes on a character boundary, with a line saying so
  when they were longer.

## Why the pinned checkout and not the action's `plugins` input

At the pin, `action.yml` lines 160-167 offer `plugins` and `plugin_marketplaces`. They install from a marketplace Git
URL at run time, at whatever that repository holds then; nothing pins the bytes. The repository pins every action and
dependency to a full commit (`docs/decisions/2026-10-04-ci-least-privilege.md`; the policy tests), so the toolkit comes
from an `actions/checkout` of a full commit, checked file by file, and is loaded with `--plugin-dir`. The test file
fails the workflow if either input appears.

## Visibility

The repository is public, so the job summary of every run, and with it both reports, is readable by anyone. A change
whose findings should not be public before a fix does not belong in this workflow; the local route on the second key
(job J8) keeps its report off GitHub. A read step that reports success without an execution file fails the job in a
final step, so a green run always means the bounds were checked.

## Machine-readable counts

Each agent ends its report with one line, `J8-SUMMARY {"undeclared": <n>, "confidences": [...]}`, so the command
center's "defects caught before a cue" ledger counts from the agents' own numbers and never from prose (command center,
2026-10-09). The line adds nothing to the review itself.

## Effort and model

`--effort max` on Claude Opus 5.5 (`--model claude-opus-5-5`): the owner's direction, relayed by the command center on
2026-10-09, runs every Claude Action on Opus 5.5 at max effort, and the command center's caps of the same day moved
this workflow's coordinator from Sonnet 5.5 to Opus 5.5. The agents' work is judgment (the effort mapping of
2026-10-08). The replay that justified adopting the agents, and every J8 run this record cites, ran them on Sonnet
5.5; no run of these agents on Opus 5.5 is part of this record. The level has to be in `claude_args`, because
`--restricted` ignores the settings files that would otherwise carry it. What the agents themselves run on is under
the toolkit entry above (`model: inherit`); pinning it is follow-up F-08.

## Cost of one run

Measured locally with the same agents and settings on a second Anthropic key, on Sonnet 5.5 and a $5 budget: #892's
59 KB diff cost a client estimate of $4.28 (3.86 million cache-read tokens against 0.42 million written, 245,000
output tokens, about 4 minutes of agent time). A 200 KB diff ran past 15 minutes. Larger diffs should pass `paths`.

The caps come from the command center's derivation of 2026-10-09: a cap bounds a runaway at about twice the measured
95th percentile of its task class and never trims a normal run. The J8 runs of these two agents, on Sonnet 5.5 at max
effort, cost $3.31 to $5.46 each, and the coordinator used about 3 of its 12 turns; #894, #902 and trading #11
stopped at the $5 budget, so the top of that range is censored. The derivation takes Opus 5.5's token prices as twice
Sonnet 5.5's ($4 and $20 for input and output, against $2 and $10), so the same work costs about $6.6 to $10.9 on
Opus, and twice the top of that is about $22. The coordinator's 12 turns stay, the budget is $22, and the expected
cost of a run is about $6.6 to $10.9. A hosted run bills the federated organization, not the second key, so $22 is
the owner's spend limit for one run of this workflow once its variable is enabled.

The client stops a run only after its cost has crossed `--max-budget-usd`, so a cost bound equal to the budget fails a normal budget stop. Four measured J8 runs on a $5 budget ended above it: $5.46 (9.2% over, the largest overrun), $5.33, $5.16 and $5.0007, on #895, trading #11, #902 and #894. The cost bound is therefore the budget times 1.10, a factor that rounds up the largest measured overrun; the factor is derived again after this workflow's first three hosted runs. A run at or under the bound passes the cost check. A budget stop (result subtype `error_max_budget_usd`) at or under the bound publishes what the run produced, and the summary names the stop. A run above the bound fails closed and names the overrun. This workflow's budget is $22, so its bound is $24.20.

Runs spend from the Console organization that the repository variables `ANTHROPIC_ORGANIZATION_ID`,
`ANTHROPIC_FEDERATION_RULE_ID`, `ANTHROPIC_SERVICE_ACCOUNT_ID` and `ANTHROPIC_WORKSPACE_ID` name. Activation is the
same optional owner step as the other W4 workflows (a federation rule in the organization that should pay); until
then the same agents run locally on the second key, which already meets the need.

## Changed existing test contracts

- `tests.test_workflow_policy.RepositoryPolicyTests.test_write_grants_are_the_reviewed_inventory`: a new entry,
  `claude-pr-toolkit-review.yml:review` with `["id-token: write"]`.
- `tests.test_workflow_policy.RepositoryPolicyTests.test_each_exemption_is_still_needed`: a new `id-token-write`
  exemption for that job.
- `tests.test_workflow_security_coverage.NewWorkflowSecurityCoverageTests`: the coverage set gains the workflow, with
  its own offline zizmor test.

New, in `tests/test_claude_pr_toolkit_review_workflow.py` (57 tests): the trigger, condition, permissions, checkout
layout, toolkit checkout, step order, pin, inputs, time limits, flags (exactly, line by line), prompt and settings
(exactly) are asserted from the workflow file; the guard, binding, link removal, diff, toolkit check, numbers and
report steps are executed as written against local stand-ins for `gh` and `git` and a local git repository. They run without PyYAML, through the policy test's own
loader. Eight weakened copies of the workflow each fail at least one test: the report-sections bound removed, the turn
count including the agents' turns, Bash allowed, no time scaling, no hash check, the toolkit ref moved to `main`, the
runtime `plugins` input added, and a $70 cost bound. Three more each fail them for the handback fallback: the
handbacks ignored, the wrong handback tool name, and the handbacks preferred over a complete relay. R6 reverses
that last preference: the handbacks are now always published, and a copy that prefers the relay fails.

## Debug logging set as a repository secret or variable (2026-10-09)

A read of this workflow against official practice for `anthropics/claude-code-action` v1.0.247 (the cc-native-practice
lane's L3 delta, requirement R4) found that the guard step could not see debug logging enabled through a repository
secret or variable. Step debug logging and runner diagnostic logging are each enabled by a secret or a variable named
`ACTIONS_STEP_DEBUG` or `ACTIONS_RUNNER_DEBUG`, the secret taking precedence (GitHub, "Enabling debug logging"), and
neither reaches a step's shell unless it is bound; `runner.debug` reflects step debug logging, a debug re-run
included, but not runner diagnostic logging. The guard now binds
`(secrets.ACTIONS_STEP_DEBUG || vars.ACTIONS_STEP_DEBUG) == 'true'` as `STEP_DEBUG_SETTING` and
`(secrets.ACTIONS_RUNNER_DEBUG || vars.ACTIONS_RUNNER_DEBUG) == 'true'` as `RUNNER_DIAGNOSTICS_SETTING`, so only
`true` or `false` reaches the shell, and refuses either before any token is requested. This is hardening, not a closed
leak: the action step already pins `ACTIONS_STEP_DEBUG: 'false'` in its own environment, which is what the action's
full-output switch reads (`base-action/src/parse-sdk-options.ts`). zizmor's auditor persona reports
`secrets-outside-env` (medium) on the two secret reads; the repository's CI runs the regular persona, pedantic
suppresses it, and each read yields a boolean only. A test pins both bindings and the guard test refuses each
setting; weakened copies are listed with the checks of this change.

## The report notice at the cap (2026-10-09)

The J8 micro read of #892 found an off-by-one in the publish step: `jq -r` adds a newline, so the file it wrote was
one byte longer than the report text, and a report of exactly 60,000 bytes was announced as cut although nothing
was. The step now writes the text with `jq -j`, which adds none, and a test publishes reports of exactly 60,000 and
60,001 bytes (no notice, then the notice); a copy that writes with `jq -r` again fails it. The step's comment says
what it publishes: the coordinator's relay, which is the last non-empty result text, when that relay carries both
agents' sections, and otherwise each agent's own handback; with no handback at all it publishes the relay as it is.
That is what the step did then; R6 replaces it with the two handbacks only (below).

## Round 5: result records, caps, link removal and exact pins (2026-10-09)

The command center's security read of `b80a6eb8`, two later audits and its caps decision of 2026-10-09 asked for the
changes below. Each new or changed step, condition, field and message is also in the by-name list above.

- **Every result record (P2-1).** The numbers step read only the last result record. Read from the client directly,
  the api-actions J8 #894 stream ends in five result records, a success, a budget stop, an idle success, a budget stop
  and an idle success, all at $5.0007; by the command center's read, #902's ends in two errors and an idle success. The
  same run could therefore get either verdict, depending on which record came last. The step now reads every result
  record in the file, so an idle success at the end cannot hide an earlier error. It accepts a run only when every
  record is a success without `is_error`, or a budget stop after both agents handed back, and any other error subtype
  fails. It takes the highest cost of any record, with that record's model usage, and the publish step follows the
  numbers step's outcome (`id: numbers`) instead of `success()`.
  - The pinned action's execution file ends at the first result record: `base-action/src/run-claude-sdk.ts` stops
    reading there (lines 190-209, read at v1.0.246, a file the v1.0.247 compare leaves unchanged). A hosted file
    therefore holds at most one result record, and only what came before it.
  - In the two J8 streams that reached a result record, read from the client directly, both handbacks came before
    the first result record. Counting records from zero: in #894 the handbacks are records 563 and 580, and the
    first result is record 598, already at the whole run's cost; in #892 they are 303 and 323, and the first result
    is 347. #894's first result record carries the coordinator's first-turn note ("Both review agents are running
    in the background..."), but the client emitted it only after both handbacks. A file cut after the first result
    record still holds both handbacks, and the numbers step passes on both cut streams.
  - Whether the client, run through the action's SDK path, also waits for the background agents before its first
    result record is not measured. If it does not, the file ends after the coordinator's first turn, before any
    handback: the report bound fails with `0 of 2 agent reports` (since R6, the handback bound with
    `0 of 2 agent reports handed back`), the numbers step fails, and nothing is published.
    The run fails closed. The first hosted runs measure which happens.
  - A budget stop costs at least the budget (J8 #894: $5.0007 on $5). The cost bound is therefore the budget times
    the measured overrun factor 1.10, $24.20 (the caps below and "Cost of one run"). A budget stop at or under it,
    after both handbacks, passes the numbers step and publishes both reports, and the job summary names the stop. A
    run above it fails whether it stopped on its budget or not, and the summary names the overrun.
- **A run cut off before its result (P3-1).** When the client stops with an error, the action writes the messages it
  has read (`run-claude-sdk.ts` lines 212-216) and sets the `execution_file` output in its catch
  (`setExecutionFileOutputIfPresent`, `src/entrypoints/run.ts`). That file has no result record, and the numbers
  step used to fail on it without keeping any record. It now keeps the assistant messages' token counts, once per
  message id, as `lower_bound_models`, and fails.
  - The sums are a lower bound. On J8 #894's stream, the sums over distinct message ids equal the result's model usage
    for input, cache-read and cache-write tokens (148; 8,370,121; 484,977), but give 448 output tokens against 323,641.
  - J8 #900's stream has no result record and one handback. Replayed on it, the step took this path: it kept the
    lower bound and failed, naming the missing result usage, the missing success and `1 of 2 agent reports`.
  - The action's own comment (lines 200-208) says a step killed at its time limit writes no execution file. Then the
    numbers step does not run and nothing is kept. Whether a hosted step timeout takes the error path or the kill has
    not been measured.
- **The agents called (third audit, P3-4).** The set of agents the coordinator called must be exactly
  `pr-review-toolkit:pr-test-analyzer` and `pr-review-toolkit:silent-failure-hunter`: each at least once, so a
  retried agent passes, and no other agent. This bound decides whether the two intended agents ran; the
  report-sections bound reads only headings, which the coordinator's own text can carry. The step was replayed on
  three J8 streams of 2026-10-09 (#892, #900 and #894). In each, the coordinator called both agents once, in its
  first turn, so the bound passed on all three. The whole step passed on #892 and #894. It failed on #900, a run
  with no result record and one handback, on the lower-bound, result and report bounds.
- **Tool entries that are not strings (GPT designated read of #895, P2).** The tool list used to be filtered to strings
  before the allow-list check, so an entry such as `{"name":"Bash"}`, `null` or `17` passed. Each such entry is now a
  forbidden tool, named `non-string tool entry`. The string allow-list check is unchanged.
- **Symbolic links in the head (common item 1).** The new step `Remove symbolic links from the pull request head`
  follows the head checkout, as described above.
- **Exact pins (common item 2).** A test compares every `claude_args` line, split as a shell would after GitHub
  substitutes `${{ runner.temp }}`, and the whole `--settings` JSON, with fixed values. A widened or repeated
  `--add-dir`, a second budget or turn flag, or `permissions.additionalDirectories` fails it.
- **Model and caps (command center, 2026-10-09).** `--model claude-sonnet-5-5` became `--model claude-opus-5-5`, still
  at `--effort max`. `--max-budget-usd 5` became `--max-budget-usd 22`, and `--max-turns 12` is unchanged. The cost
  bound moved from $7 (the $5 budget and a $2 allowance) to $24.20, the $22 budget times the measured overrun factor
  1.10; the numbers step holds both as `budget=22 cost_bound=24.2`. The turn bound stays 1 to 12. The
  derivation is under "Cost of one run". `docs/github-automation.md` now says Opus 5.5 and $22.
- **Test quality (P3-2, P3-3).**
  - The toolkit test never reached the hooks, MCP and scripts refusal, because the synthetic files fail the hash check
    first. It now runs the step with the synthetic files' own SHA-256 values in place of the recorded ones; each
    recorded value must occur exactly once in the step. The hash check then passes, each of `hooks`, `.mcp.json` and
    `scripts` meets the refusal, and a clean tree passes.
  - The cap test now asserts the published prefix on the iconv path: an 80,001-byte report of `a` and 40,000 `é`
    publishes exactly `a` and 29,999 `é`, with the notice.
  - Run against the `b80a6eb8` tests, a copy without the refusal and a copy that converts to ASCII both passed; the
    new tests fail both.
- **Record corrections.**
  - The report-notice section said the publish step's comment describes the last non-empty result text. The comment
    describes the relay or the handbacks, and that section now says so.
  - The model, budget, cost-bound and evidence-class sentences follow the changes above, and the toolkit entry says
    what the agents run on.
  - "What would overturn it" gains the first Opus 5.5 runs, whose figures replace the Sonnet 5.5 ones the caps were
    derived from. The SOTA sources gain `run-claude-sdk.ts`, `run.ts`, `git-config.ts` and `src/modes/agent/index.ts`.

In agent mode the action rewrites the checkout's `origin` URL with the job token (`src/github/operations/git-config.ts:129-134`, called from `src/modes/agent/index.ts:52-61` at `2dca132f`), so `persist-credentials: false` does not keep the token out of `.git/config`; the deny rules `Read(./.git/**)` and `Read(./**/.git/**)` are what keep the model from reading it, as two 2026-10-09 probes on the installed 2.1.295 measured.

Security hardening from the 2026-10-09 read (transcript tool scanning, subagent model and Agent-tool pins, debug-value widening, tool-list shape, extra deny rules, token-source and guard-step assertions) is filed as follow-ups before any enabling variable is set.
Of the tool-list shape, this round takes only the refusal of entries that are not strings.

Tests:

- New:
  - `test_the_symbolic_links_are_removed_right_after_the_head_checkout_on_every_run`;
  - `test_every_symbolic_link_in_the_head_is_removed_and_nothing_else`. It plants links to `/proc/self/environ`, to
    `../.git/config` and inside a subdirectory;
  - `test_claude_args_and_settings_are_pinned_exactly`;
  - `test_a_toolkit_with_hooks_an_mcp_configuration_or_scripts_is_refused_after_its_hashes_match`;
  - `test_in_the_measured_order_a_budget_stop_after_both_handbacks_passes_wherever_the_file_ends`. It replays the
    five-record sequence, with synthetic text, in J8 #894's measured order: both handbacks before the first result
    record. The file is cut after each record, so it ends at the first result record as at the pinned action, or
    later. It checks that the handbacks come first, that every cut passes, and that the summary names the budget stop
    once a budget-stop record is among those read;
  - `test_a_file_that_ends_before_the_handbacks_fails_closed`, the order not measured: the first result record comes
    after the coordinator's first turn and before the handbacks. Cut there, the step fails with exactly
    `Bounds not met: 0 of 2 agent reports` (since R6, `... handed back`) and keeps no report text; with the rest of
    its records, it passes;
  - `test_the_model_usage_is_the_costliest_result_records`: three records at $4, $23 and $9 with different usage;
    `models` is the $23 record's;
  - `test_a_budget_stop_without_both_handbacks_and_any_other_error_record_fail`;
  - `test_the_cost_is_the_highest_any_result_record_reports`;
  - `test_the_cost_bound_is_the_budget_times_the_measured_overrun_factor`: a success at $24.20 passes and one at
    $24.21 fails, the overrun named in the failure and in the summary;
  - `test_a_budget_stop_after_both_handbacks_publishes_up_to_the_cost_bound`: budget stops at $22.40 and at $24.20,
    in the five-record shape and alone (as a hosted file ending at its first result record holds one), pass, name
    the stop and publish both reports; one at $24.21 fails, named; one with a single handback fails;
  - `test_the_numbers_steps_cost_bound_is_the_budget_in_claude_args_times_1_10`;
  - `test_a_run_cut_off_before_its_result_keeps_a_lower_bound_of_its_usage_and_fails`;
  - `test_the_coordinator_must_call_both_toolkit_agents_and_no_other`: a retried agent passes; a third agent, a
    missing agent, a missing agent with the other retried, and no agent each fail;
  - `test_a_tool_entry_that_is_not_a_string_is_a_forbidden_tool`, covering `{"name":"Bash"}`, `null` and `17`.
- Changed:
  - `test_steps_run_in_the_order_the_binding_depends_on` includes the new step;
  - `test_no_step_executes_anything_from_the_pull_request_head` skips the new step, whose `find` runs nothing from the
    tree and whose exact script the first new test pins;
  - `test_claude_has_read_tools_and_the_agent_tool_with_fixed_bounds` expects Opus 5.5 and $22;
  - `test_the_reports_are_published_only_after_the_bounds_check_passed_and_only_numbers_are_uploaded` pins the
    publish condition and the `numbers` id;
  - `test_a_bounded_cached_run_with_both_reports_is_accepted_and_only_numbers_and_fixed_names_are_kept` covers the new
    fields and the summary line;
  - in `test_an_unmet_bound_fails_after_the_numbers_were_kept`, "over the cost bound" is $24.21 where "over the
    budget and its allowance" was $7.01;
  - `test_the_step_names_every_unmet_bound` uses $24.50 and the new message;
  - `test_names_that_are_not_plain_identifiers_are_replaced` uses the Opus model key;
  - `test_the_cap_never_splits_a_character_and_a_short_report_has_no_notice` asserts the prefix.
- Fixtures:
  - by default the coordinator now calls the two agents in its first turn (`execution(agents=...)`), and `results=`
    replaces the final record;
  - `budget_stop_records()` and `with_message_usage()` are new;
  - `run_step` takes `replacements` and `after`, and `toolkit_tree` takes `extra`.
- The module ran 41 tests before this round and runs 56 now.

36 weakened copies of the workflow each fail at least one test:
- the link step removed, skipped with `if: false`, run without `-type l`, or moved after the review step;
- a second `--max-budget-usd`, a second `--add-dir`, `permissions.additionalDirectories`, the model back to Sonnet
  5.5, or the budget back to $5;
- the overrun factor dropped (the bound back at $22) or widened to 1.5 ($33), the bound at $70 or back at $7, the
  numbers step's budget no longer the `claude_args` budget, the failure check alone widened to $70, the summary's
  budget-stop or overrun line removed, or the turn bound at 13;
- only the last result record read, a budget stop accepted without both handbacks, any error subtype accepted after
  both handbacks, the last record's cost instead of the highest, the model usage of the first or of the last result
  record instead of the costliest, the `numbers` id removed, or publication back on `success()`;
- the lower-bound path removed, each message counted instead of each id, or its failure message dropped;
- the hooks, MCP and scripts refusal removed, or `.mcp.json` no longer refused;
- iconv converting to ASCII;
- the agent bound removed, a third agent allowed, or each agent required exactly once again, so a retry fails;
- the non-string filter restored.

## Round 6: both handbacks required, the shared cost wording and the undeclared changes (2026-10-09)

The command center's R6 round, with the GPT designated read of `7aa2c128` and the J8 R5 micro read of the same head,
asked for the changes below. Each behaviour change below is also in the by-name list above.

- **Both agents must hand back (GPT designated read, P2, reproduced by the reader).**
  - The defect: a plain success was accepted whatever `handbacks` was; only a budget stop needed both. The report
    bound counted two headings in the text the report step would publish, which is the coordinator's relay whenever
    the relay carries both headings. So a run that ended at a success whose relay held both headings passed and
    published with no handback or one. On five synthetic prefixes, each ending at one ordinary success, the reader
    found four incomplete ones that passed and published, headings alone with no handback among them.
  - The fix: the numbers step now fails unless both called agents handed back, whatever the result records say. A
    handback counts only as a `SubagentHandback` message whose parent is the coordinator's Agent call for that agent,
    once per agent however many calls it had. The new message `<n> of 2 agent reports handed back` replaces
    `<n> of 2 agent reports`, which counted headings. Headings in the relay no longer count anywhere. `report_sections`
    stays in `usage.json` but is no longer a bound, and `successful_result` keeps its R5 meaning.
- **The handbacks are published, never the relay (command center decision).** The report step published the
  coordinator's relay whenever it carried both report headings, even with both handbacks present, a preference R3
  chose and its tests enforced. A relay is model text and can be a template or a paraphrase; the handbacks are the
  agents' own reports, and the GPT designated read of `7aa2c128` ruled that relay headings never count as completion.
  The report step now publishes the two agents' handbacks, pr-test-analyzer's then silent-failure-hunter's, each under
  its own heading, whatever order the agents were called in, and for an agent called more than once its last handback.
  It never publishes the relay; the numbers step, whose success it needs, requires both handbacks. In `usage.json`,
  `report_source` is `handbacks` whenever any agent handed back. For an agent called more than once, the published
  handback is the one from its last call in the order the coordinator made the calls, not the one that came last in
  the stream; a background retry can finish before the first attempt, and the command center kept this rule.
- **The coordinator no longer relays (command center decision).** Publishing now uses the handbacks only, so the
  prompt's instruction to output both agents' reports verbatim under their headings was removed: nothing read that
  output, and it spent Opus output tokens on every run. The coordinator is now told not to repeat or summarize the
  reports and, after both agents have handed back, to end with the single line `Both reports handed back.` This saves
  the relay's output tokens on every run; the $24.20 cost bound stays as it is, as an upper bound.
- **A cancelled run publishes nothing (aligned with the other W4 workflows).** The publish step's condition is now
  `!cancelled() && steps.numbers.outcome == 'success'`, where it started with `always()`. The clause on the execution
  file is dropped because the numbers step runs only with one.
- **The exact `--settings` pin tells `true` from `1` (J8 R5 micro read of #894, N1).** The exact-pin test compared
  parsed dicts with `==`, and `1 == True` in Python, so a setting of `1` or `0` where `true` or `false` is pinned
  passed it. It now compares canonical JSON (sorted keys), for the whole argument list and for the settings.
- **The cost factor's shared wording.** The paragraph under "Cost of one run" is now the shared R6 paragraph, verbatim,
  with this workflow's $22 budget and $24.20 bound in its last sentence. It replaces this record's own wording of the
  factor, its four runs and its re-derivation trigger. The rule itself is R5's ($22 × 1.10 = $24.20).
- **Changes the J8 R5 micro read found undeclared.** Section 3 of each agent's report named these behaviour and test
  changes of R5 that the pull request description did not declare. They are declared here, and the by-name list above
  now covers the two it lacked: the cache-read bound checked only on complete usage, and what a cancellation does to
  publication (R6 ends it, below).
  1. `usage.json` values change meaning: `num_turns` is the highest over all result records, not the last record's,
     and `successful_result` is true for an accepted budget stop.
  2. One result record without a whole cost, turn count and model usage puts the whole run on the lower-bound path,
     even when other records are usable: `total_cost_usd` and `num_turns` become null and `models` empty.
  3. The job summary gains, besides the budget-stop and overrun lines, a `Result records … Agents called … Handbacks
     <n> of 2.` line on every run, `none` for a missing cost or turn count, and lower-bound model rows; its `completed`
     column shows `true` for an accepted budget stop.
  4. Failure messages: `the run did not end in success` and `…, above 7` are replaced by longer messages, and two
     messages are new.
  5. The `no cache read` bound is checked only when the usage is complete; before R5 it was always checked.
  6. Publication is broader. Reports publish whenever the numbers step passes, whatever the action step's outcome,
     including a success whose `num_turns` exceeds `--max-turns` and any other failure of the action step after
     `execution_file` was set. The job stays failed. R5's condition started with `always()`, so reports also
     published after a cancellation; R6's `!cancelled()` ends that, and a cancelled run publishes nothing.
  7. `test_no_step_executes_anything_from_the_pull_request_head` skips the link-removal step entirely.
  8. The shared test fixture changed. `execution()` emits both coordinator Agent calls in its first turn under one
     message id, with the handbacks after the coordinator's turns, so unchanged tests run on different input (two
     coordinator turns where there were four). `results=`, `budget_stop_records()`, `with_message_usage()`,
     `run_step(replacements=, after=)` and `toolkit_tree(extra=)` are new. The accepted-run test pinned
     `handbacks == 0` on a passing run, which R6 changes to 2.

Tests:

- New: `test_a_success_before_both_agents_handed_back_fails_and_publishes_nothing`. Each case ends at one ordinary
  success at $0.40 with both agents called, and each fails with exactly `Bounds not met: <n> of 2 agent reports handed
  back`, so the publish step, which needs the numbers step's success, publishes nothing. The cases:
  - both headings alone, no handback;
  - both headings with pending text, no handback;
  - two calls, no handback;
  - one handback, with a relay carrying both headings;
  - one handback carrying the other agent's heading;
  - one agent's two handbacks after a retry, none from the other.
- New: `test_the_handbacks_are_published_never_a_relay_with_both_headings` replaces R3's
  `test_a_relay_with_both_sections_is_preferred_to_the_handbacks`. A relay carrying both headings and template text,
  with both real handbacks: the numbers record says `handbacks`, the published text is exactly the two handbacks in
  order, and the template text never appears. It runs with the agents called in order, called in reverse order, and
  with pr-test-analyzer retried (its first attempt's handback is not published, and each heading appears once).
- Changed:
  - `execution()` gives both agents a handback by default (`BOTH_HANDBACKS`); a test that needs none passes
    `handbacks={}`;
  - `test_a_bounded_cached_run_with_both_reports_is_accepted_and_only_numbers_and_fixed_names_are_kept` expects 2
    handbacks and the handbacks as the report source, and checks that no handback text is kept;
  - in `test_an_unmet_bound_fails_after_the_numbers_were_kept`, "no result text" also has no handback, and "one agent's
    report missing" is now "one agent's handback missing";
  - `test_the_step_names_every_unmet_bound` passes no handback and names the new message;
  - `test_a_file_that_ends_before_the_handbacks_fails_closed` expects the new message;
  - the case "a budget stop after a full relay but no handback" passes no handback;
  - `test_the_coordinator_must_call_both_toolkit_agents_and_no_other` also expects the handback failure where an agent
    is missing;
  - the report-step tests that check escaping, the cap and the character-boundary prefix carry their text in the first
    agent's handback, sized so the published text, headings included, is exactly 60,000 or 60,001 bytes, or cuts an
    `é` in half at the 60,000th byte;
  - R3's `test_the_reports_are_the_last_result_with_text` is now
    `test_an_empty_idle_result_at_the_end_changes_nothing_published`: the handbacks are published and the relay's text
    is not;
  - the publish condition test expects `!cancelled() && steps.numbers.outcome == 'success'`;
  - `test_the_prompt_runs_the_two_toolkit_agents_and_asks_for_undeclared_changes` pins the coordinator's part of the
    prompt exactly, with runs of whitespace folded, and checks that no report heading is left in the prompt;
  - `test_claude_args_and_settings_are_pinned_exactly` compares canonical JSON.
- The module runs 57 tests, where it ran 56 after R5.

49 weakened copies of the workflow each fail at least one test. The R5 copy that turns the publish condition back to
`success()` now starts from the new condition. Seven copies are new for the published text, the relay instruction,
the cancellation and the settings pin:
- the coordinator's relay instruction restored in the prompt: the prompt test;
- the relay preferred again in the publish step when it carries both headings: the new test, the empty-idle-result
  test and the three escaping and cap tests;
- the handbacks published in call order, one per call: the new test;
- the relay preferred again in the numbers record: the accepted-run test and the new test;
- `always()` restored in the publish condition: the publish condition test;
- `"disableAllHooks": 1` and `"autoMemoryEnabled": 0` in `--settings`: each fails the exact-pin test (and the
  settings test's `assertIs` checks).

The six copies new earlier in R6, and the cases of the new handback-bound test each fails:
- the handback bound switched off: all six;
- relay headings counting again: the two headings-only cases and both one-handback cases;
- handbacks required only when the text carries a report heading: two calls, no handback;
- one handback enough: both one-handback cases and the retry case;
- handbacks counted per call, not per agent: the retry case;
- any handback counting for every call, the association to the coordinator's call dropped: both one-handback cases
  and the retry case.

## Authentication by API key (2026-10-10)

Since 2026-10-10 the owner ruled on 2026-10-10 that CI Claude review authenticates with an Anthropic API key, `ANTHROPIC_API_KEY` of the main-only `claude-review` environment, not federation (`docs/decisions/2026-10-08-claude-actions-pr-review.md`, "Authentication by API key"). The toolkit job passes `anthropic_api_key` and no federation input, and holds `contents: read` and `pull-requests: read` only. Dispatch on main by the owner, the bounds and the read-only tools are unchanged.

## Alternatives considered

- **The action's `plugins` and `plugin_marketplaces` inputs.** Rejected: unpinned (above).
- **Folding the agents into #894's review.** Rejected: #894 is a single read-only reviewer on Opus 5.5 with no Agent
  tool; the toolkit needs the Agent tool, a larger budget and a scaled time limit, and the command center ruled it a
  separate draft (W4 f).
- **The toolkit's `code-reviewer` agent as well.** Not chosen: the command center's adoption names
  `pr-test-analyzer` and `silent-failure-hunter`; in the replay, `code-reviewer`'s catches also came only from the
  undeclared-changes list.
- **`openai/codex-action` for a GPT-family read in Actions: WATCH.** Maintained (v1.13 at
  `bdf19a4a223ec2549a3e2274a0cf61556bc07675`, pushed 2026-10-05). It authenticates with `openai-api-key` or a
  `responses-api-endpoint` override; the ecosystem's GPT access is a subscription through a gateway on loopback, which
  GitHub-hosted runners cannot reach. A platform key is a new billing surface and a self-hosted runner a new attack
  surface, so GPT designated reads stay on the co-op's subscription path. Overturn when the owner provides a platform
  key or a reachable endpoint and a frozen A/B shows the CI read at parity with the co-op GPT read.

## What would overturn it

- A designated read that misses a defect the toolkit agents would have caught, or the agents flagging nothing the
  designated reads miss over the next ten pull requests: re-measure against the replay record.
- A newer pinned toolkit with changed agent files: re-verify the hashes and re-run one local read before moving the
  pin.
- A client that counts the agents' turns against `--max-turns`, or that changes the background-task ceiling: re-check
  the bounds against a local run on that version.
- The first runs of these agents on Opus 5.5: their cost and turns replace the Sonnet 5.5 figures the caps were
  derived from (Cost of one run).

## Evidence class

`local_integration`: the unit tests above, actionlint 1.17.0 and zizmor 1.30.1 (offline, pedantic and regular), no
findings; the toolkit's three files compared with GitHub's blob ids at the pin. `native_proven` for the agents and the
other settings on Sonnet 5.5 and a $5 budget, on the installed Claude Code 2.1.295, billed to a second Anthropic key,
in the J8 runs named above (not through the action). Opus 5.5 and the $22 budget have no run of these agents yet, and
no hosted run of this workflow is part of this record.

## SOTA sources

- anthropics/claude-code-action v1.0.247 at `2dca132ff0e0c4094ce6048b422c6915a071210b`: `action.yml` (federation
  inputs, `claude_args`, `plugins` and `plugin_marketplaces` at lines 160-167, `display_report`, `track_progress`) and
  `base-action/src/parse-sdk-options.ts` (pass-through of other flags); the releases API on 2026-10-09 lists v1.0.247
  as the latest. `base-action/src/run-claude-sdk.ts` (the loop that stops at the first result record, lines 190-209;
  the file written on an SDK error, lines 212-216; the step's conclusion, lines 236-298), read at v1.0.246
  (`38c80c1`), which the v1.0.247 compare leaves unchanged; `src/entrypoints/run.ts` (`setExecutionFileOutputIfPresent`
  in its catch); `src/github/operations/git-config.ts` and `src/modes/agent/index.ts` for the `origin` rewrite.
- anthropics/claude-code at `602df92bf481ed904533e95c09f740f40aab5aed`: `plugins/pr-review-toolkit` (the two agents
  and `.claude-plugin/plugin.json`).
- Claude Code 2.1.295 `claude --help` for `--plugin-dir`, `--tools`, `--restricted`, `--permission-prompts`, `--effort`
  and `--max-budget-usd`; the headless documentation for background subagents and
  `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`.
- openai/codex-action v1.13 at `bdf19a4a223ec2549a3e2274a0cf61556bc07675`, `action.yml` inputs (for the WATCH entry).
- GitHub Actions: `actions/checkout` v7.0.1 (`repository`, `ref`, `path`, `sparse-checkout`); step-level
  `timeout-minutes` with the `steps` context.
