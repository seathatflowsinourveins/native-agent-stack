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
- The head is checked out as data under `pr-head/` with main at the root. The diff is written by git in the root
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

  Both agents declare `model: inherit`, so they run on the session's model.
- The action step pins `ACTIONS_STEP_DEBUG: 'false'` and sets `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS: '0'`: in
  `-p` mode Claude Code runs Agent-tool subagents in the background and stops background work after 10 idle minutes
  unless that variable is set, which cut a 607 s pilot; the step's own time limit bounds the wait instead. It passes
  `show_full_output`, `display_report` and `track_progress` as `'false'`, the last two their defaults (the pinned
  `action.yml`, lines 136-139 and 152-155).
- `claude_args`: `--model claude-sonnet-5-5`, `--effort max`, `--max-turns 12`, `--max-budget-usd 5`, `--tools` and
  `--allowedTools` Read,Glob,Grep,Agent, `--restricted`, `--permission-prompts none`, `--setting-sources user`,
  `--strict-mcp-config`, `--plugin-dir` at the moved toolkit, `--settings` with hooks and auto memory off,
  `claudeMdExcludes` for `pr-head` and the deny rules, and `--add-dir` for the diff directory. The action's own parser
  (`base-action/src/parse-sdk-options.ts` at the pin) keeps `--plugin-dir` as a pass-through argument to the CLI.
- A numbers step checks the bounds and an artifact keeps `usage.json` (numbers only) for 14 days. The bounds: the run
  succeeded; the session start record lists its tools and MCP servers; no tool outside Read, Glob, Grep and the Agent
  tool (which the session reports as `Task`); no MCP server; 1 to 12 coordinator turns, counted as distinct assistant
  message ids without a parent tool use, because the agents' own turns are theirs; a client cost estimate of at most
  $7, the $5 budget plus a $2 allowance, because the client checks its budget after a turn and the background agents'
  last requests can land after that check; a cache read; result text; and both agents' report sections. The step
  names every bound it finds unmet. With background agents the client emits several result records, and the last can
  be an empty idle tick, so the coordinator's relay is the last result with text. When that relay lacks an agent's
  section, the reports are assembled from each agent's own `SubagentHandback` message in the execution file: in J8
  #894 the coordinator hit `--max-budget-usd 5` (`error_max_budget_usd`) after both agents had handed back their full
  reports, and never relayed them. All three J8 streams so far (#892, #900, #894) carry `SubagentHandback` calls.
- The reports go to the job summary only when the bounds passed, capped at 60,000 bytes on a character boundary,
  with a line saying so when they were longer.

## Why the pinned checkout and not the action's `plugins` input

At the pin, `action.yml` lines 160-167 offer `plugins` and `plugin_marketplaces`. They install from a marketplace Git
URL at run time, at whatever that repository holds then; nothing pins the bytes. The repository pins every action and
dependency to a full commit (`docs/decisions/2026-10-04-ci-least-privilege.md`; the policy tests), so the toolkit comes
from an `actions/checkout` of a full commit, checked file by file, and is loaded with `--plugin-dir`. The test file
fails the workflow if either input appears.

## Effort and model

`--effort max` on Claude Sonnet 5.5, as the command center set J8: the agents' work is judgment (the effort mapping of
2026-10-08), and the replay that justified adopting them ran these agents on Sonnet 5.5. The level has to be in
`claude_args`, because `--restricted` ignores the settings files that would otherwise carry it.

## Cost of one run

Measured locally with the same agents and settings on a second Anthropic key: #892's 59 KB diff cost a client
estimate of $4.28 (3.86 million cache-read tokens against 0.42 million written, 245,000 output tokens, about 4
minutes of agent time). A 200 KB diff ran past 15 minutes. Larger diffs should pass `paths`.

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

New, in `tests/test_claude_pr_toolkit_review_workflow.py` (37 tests): the trigger, condition, permissions, checkout
layout, toolkit checkout, step order, pin, inputs, time limits, flags, prompt and settings are asserted from the
workflow file; the guard, binding, diff, toolkit check, numbers and report steps are executed as written against
local stand-ins for `gh` and `git` and a local git repository. They run without PyYAML, through the policy test's own
loader. Eight weakened copies of the workflow each fail at least one test: the report-sections bound removed, the turn
count including the agents' turns, Bash allowed, no time scaling, no hash check, the toolkit ref moved to `main`, the
runtime `plugins` input added, and a $70 cost bound. Three more each fail them for the handback fallback: the
handbacks ignored, the wrong handback tool name, and the handbacks preferred over a complete relay.

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

## Evidence class

`local_integration`: the unit tests above, actionlint 1.17.0 and zizmor 1.30.1 (offline, pedantic), no findings; the
toolkit's three files compared with GitHub's blob ids at the pin. `native_proven` for the agents and settings on the
installed Claude Code 2.1.295, billed to a second Anthropic key, in the J8 runs named above (not through the action).
No hosted run of this workflow is part of this record.

## SOTA sources

- anthropics/claude-code-action v1.0.247 at `2dca132ff0e0c4094ce6048b422c6915a071210b`: `action.yml` (federation
  inputs, `claude_args`, `plugins` and `plugin_marketplaces` at lines 160-167, `display_report`, `track_progress`) and
  `base-action/src/parse-sdk-options.ts` (pass-through of other flags); the releases API on 2026-10-09 lists v1.0.247
  as the latest.
- anthropics/claude-code at `602df92bf481ed904533e95c09f740f40aab5aed`: `plugins/pr-review-toolkit` (the two agents
  and `.claude-plugin/plugin.json`).
- Claude Code 2.1.295 `claude --help` for `--plugin-dir`, `--tools`, `--restricted`, `--permission-prompts`, `--effort`
  and `--max-budget-usd`; the headless documentation for background subagents and
  `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`.
- openai/codex-action v1.13 at `bdf19a4a223ec2549a3e2274a0cf61556bc07675`, `action.yml` inputs (for the WATCH entry).
- GitHub Actions: `actions/checkout` v7.0.1 (`repository`, `ref`, `path`, `sparse-checkout`); step-level
  `timeout-minutes` with the `steps` context.
