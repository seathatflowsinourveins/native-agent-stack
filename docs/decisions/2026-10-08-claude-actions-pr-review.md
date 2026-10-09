# On-demand, read-only pull request review by the Claude action — 2026-10-08

`claude-pr-review.yml` lets a maintainer ask for a review of one pull request head. It is dispatched by hand from
`main` with a pull request number and the exact head commit; Claude reads the diff and the files with Read, Glob and
Grep, within 12 turns and a $3 client budget; a model-free step copies the review to the job summary. Nothing is
posted to the pull request and the job holds no write scope beyond the OIDC token. It runs only while the repository
variable `CLAUDE_PR_REVIEW_ENABLED` is `true`. Nothing in this change starts a run or sets a variable.

## What the workflow does, by name

The workflow is new, so this is all of its behaviour. The list follows the pre-cue read of the sibling harness-audit
PR (#892, 2026-10-09), which found changes its record had not named; the same review was applied here.

- Trigger: `workflow_dispatch` only, with inputs `pr_number`, `head_sha` and optional `paths`. The concurrency group
  is per pull request, without cancelling a run in progress.
- Job condition: this repository (slug guard), the `main` ref, `github.actor` and `github.triggering_actor` both the
  repository owner, the first attempt of a run, and `CLAUDE_PR_REVIEW_ENABLED == 'true'`. A dispatch by anyone else,
  or a re-run, is skipped.
- `timeout-minutes: 20`. Grants: `contents: read`, `pull-requests: read` and `id-token: write`.
- A guard step stops the job with exit 2 when step or runner debugging is on, when `~/.claude/settings.json` already
  exists on the runner (a dangling symlink included), or when an input is malformed.
- A binding step stops the job with exit 2 unless the pull request is open, from this repository, targets `main` and
  has exactly the requested head.
- The head is checked out as data under `pr-head/`, with main at the root; the diff step runs git only in the root,
  with external diff drivers and text conversion off, and refuses an empty diff or one over 250,000 bytes.
- The action step pins `ACTIONS_STEP_DEBUG: 'false'` and passes `show_full_output`, `display_report` and
  `track_progress` as `'false'`; the last two are their defaults, declared in the pinned `action.yml` (lines
  136-139 and 152-155 at `2dca132f`).
- A numbers step checks the bounds (below) and an artifact `pr-review-usage-<run id>-<attempt>` keeps `usage.json`
  (numbers only) for 14 days; the review goes to the job summary only when the bounds passed. Nothing is posted to
  the pull request.
- The pin, v1.0.247, is hours old: the user ended the seven-day cooldown for clean releases on 2026-10-03
  (`docs/decisions/2026-10-03-currency-wave-w1.md`, "Holds and cooldown waiver"), which keeps qualification; the
  fence receipt and the local parity run below are that qualification.

## Why a manual dispatch and no pull request trigger

- **The federation subject.** Runs authenticate by Anthropic workload identity federation, and the rule matches the
  subject of a run on `main`. A `pull_request` run's subject ends in `:pull_request`
  (GitHub, OpenID Connect reference), so it cannot authenticate by this rule, and widening the rule to pull request
  runs would let a pull request's own workflow text ask for the token. `pull_request_target` runs main's workflow
  text but is banned here outright (`dangerous-trigger` in `tests/test_workflow_policy.py`).
- **Who can start it.** `workflow_dispatch` needs write access to the repository. The job also requires this
  repository, `refs/heads/main`, the owner as both actor and triggering actor, and the first attempt of the run: a
  re-run keeps `github.actor` and would spend again without a new request, so it is skipped.
- **Whose code runs.** The workflow text is main's. The pull request head is data.

## How the pull request head is handled

The action's own guidance (`docs/security.md` at the pin): "Do not check out an untrusted ref into the workspace root
before this action", and for a pull request's files, "check out the base ref at the workspace root ... then check out
the head ref into a subdirectory". This workflow does that:

1. A guard step refuses debug logging, a pre-existing Claude settings file and inputs that are not a pull request
   number, a 40-character commit id and, optionally, plain paths.
2. `main` is checked out at the workspace root without credentials.
3. One API read binds the request: the pull request must be open, from a branch of this repository, target `main`
   and have exactly the requested head. The response is deleted; its title and body never reach the model's
   directories. Every later step names the commit by id, so a later push changes nothing.
4. The head is checked out into `pr-head/` without credentials. No step runs anything from it.
5. `git` in the root checkout writes the diff from the merge base, with external diff drivers and text conversion
   off. An empty diff or one over 250,000 bytes is refused; `paths` limits a large pull request to part of it.

## The model's fence, and what was checked at runtime

Claude Code gets `--restricted --permission-prompts none --tools Read,Glob,Grep --allowedTools Read,Glob,Grep
--setting-sources user --strict-mcp-config` and its deny rules through `--settings`.

- `--restricted` (Claude Code 2.1.295 `--help`): "removes the built-in tools that run commands or code ... and
  WebFetch unless --tools names them, and ignores user, project and local settings files (managed settings and
  --settings still apply; add --strict-mcp-config to skip MCP servers too). Also confines the file tools to the
  working directories (--add-dir included), refuses bypassPermissions".
- `--permission-prompts none` (same `--help`): "nobody: anything that would prompt is denied automatically".
- Because `--restricted` ignores settings files, the action's `settings` input (which writes the user settings
  file) would have no effect; the same JSON goes to `--settings`: hooks off, `claudeMdExcludes` for `pr-head`, and
  Read denies for every `.git` directory (the action configures git authentication in the root checkout:
  `src/github/operations/git-config.ts` sets the origin URL with the job token or a credential helper), `.env`
  and key files.
- `pr-head` is not passed to `--add-dir`: it is already inside the working directory, and an added directory's
  `.claude/skills`, commands and agents are loaded.

The fence flags were run on the installed client (Claude Code 2.1.295, the version the pin installs): `--restricted`,
`--tools` and `--allowedTools` Read,Glob,Grep, `--strict-mcp-config`, `--permission-prompts none` and `--settings` with
hooks off, `claudeMdExcludes` for `pr-head` and three deny rules, on Claude Haiku 5.5 with `--max-turns 10` and a
$0.50 budget; the receipt lists them. This workflow adds `--setting-sources user`, `--add-dir`, `--effort max`, four
more deny rules and `blockReadsOutsideWorkingDirectories`, and runs Opus 5.5 with 12 turns and $3. The runs used a
throwaway tree with an untrusted `pr-head` carrying its own `CLAUDE.md`, a skill and a hook, a root settings file
with a hook, a root `CLAUDE.md`, `.git/config` files and a file outside the tree. In three runs the session's tools
were exactly Glob, Grep and Read; the files at the root and under `pr-head` were read; the file outside the tree and
both `.git/config` files were denied; no hook ran; neither instruction file changed the answer; there was no shell
(`evidence/artifacts/claude-actions-fence-smoke-20261008/receipt.json`). That is one small model and one prompt: it
shows these controls held there, not that no input can defeat them. The action passes `claude_args` through its own
parser (`shell-quote`, `base-action/src/parse-sdk-options.ts`); replaying that parser on this workflow's text yields
the same flags and the same JSON. This workflow's own prompt and `claude_args`, read from this file, also ran on
Opus 5.5 at `max` for one real pull request (#897): 12 of 12 assistant turns, a client cost estimate of about
$1.87 of $3, tools Glob, Grep and Read, no MCP server, a report with two blocking findings
(`evidence/artifacts/claude-actions-fence-smoke-20261008/local-parity-receipt.json`, added by #892).

After the run, one step reads the action's execution file and keeps only numbers and fixed names: cost, turns, the
success flag, the Claude Code version, the session's tool list, the number of MCP servers and per-model token
counts. It then fails the job unless the run succeeded, used 1 to 12 assistant turns (distinct assistant message ids; the client's `num_turns` counts transcript messages, tool results included, so a 12-request run on 2.1.295 reported 57, and it is only recorded), cost at most $3 by the client's
estimate, read the prompt cache, had no MCP server, listed its tools and MCP servers in the session start record (a
missing list fails instead of passing as empty), used no tool outside Read, Glob and Grep (an allow-list) and returned
result text; the step names every bound it finds unmet. The review text, the last non-empty result, is published
only when that check passed, escaped, inside `<pre>`, capped at 60,000 bytes on a character boundary, with a line
saying so when the review was longer.

## Effort

`--effort max` in `claude_args`, set under the command center's effort mapping of 2026-10-08, which runs judgment work (designated reads, adjudication, pull request and security reviews, audits) at `max`. Every job records its level and the reason, because an unset level is a defect. The level has to be in `claude_args`: `--restricted` ignores the settings files that would otherwise carry a session's level, and on the Claude API Opus 5.5 runs at `medium` when a request leaves effort unset (bundled `claude-api` skill 2.1.295, `shared/model-migration.md`). `claude --help` (2.1.295) lists `low, medium, high, xhigh, max`. A loopback dry run of the installed 2.1.295 client with this workflow's `claude_args` sent `output_config.effort: "max"`, adaptive thinking and no `speed` field on every request. At `max`, thinking takes a larger share of the output than at the default level, so the estimate below is a floor; the client budget still bounds each run.

## Cost of one run

Dry estimate at Claude Opus 5.5's $4 input, $5 five-minute cache write, $0.20 cache read and $20 output per million
tokens, for a diff of up to about 1,000 lines: $0.70 to $1.30. The $3 budget is a client estimate and is checked
again from the run's own numbers. Prompt caching is automatic in Claude Code, five minutes when billed to a Console
organization; one run reads its own cache, so the one-hour lifetime would cost more to write and buy nothing.
Fast mode is not used: in non-interactive runs it is a setting, it needs the organization provisioned, and Claude
Code falls back to standard speed by itself on a rate limit.

Runs spend from the Console organization that the four `ANTHROPIC_*` repository variables name.

## Changed existing test contracts

- `tests.test_workflow_policy.RepositoryPolicyTests.test_write_grants_are_the_reviewed_inventory`: a new inventory
  entry, `claude-pr-review.yml:review` with `["id-token: write"]`.
- `tests.test_workflow_policy.RepositoryPolicyTests.test_each_exemption_is_still_needed`: a new `id-token-write`
  exemption for `claude-pr-review.yml:review`, which the 2026-10-04 least-privilege record requires for a second
  workflow on the federation rule.
- `tests.test_workflow_security_coverage.NewWorkflowSecurityCoverageTests`: the coverage set gains
  `claude-pr-review.yml`, with its own offline zizmor test.

Unchanged and still passing: `test_pull_requests_write_is_granted_only_to_the_propose_job` and
`test_no_workflow_reviews_or_approves_a_pull_request`.

New, in `tests/test_claude_pr_review_workflow.py` (28 tests): the trigger, condition, permissions, checkout layout,
step order, pin, inputs, flags and settings are asserted from the workflow file, and the guard, binding, diff,
numbers and review steps are executed as written against a local stand-in for `gh` and a local git repository.
Twenty weakened copies of the workflow each fail at least one test: a missing head or repository check, a missing
first-attempt or triggering-actor condition, a 25 MB diff cap, a $30 or 120-turn check, a missing tool, MCP or
session-start check, metadata left in the model's directory, the head checked out at the root, a path check without
`..` or without a leading `-`, diff drivers left on, `--restricted` or `--permission-prompts none` removed, the
`.git` deny rule or `claudeMdExcludes` removed, and Bash added to `--tools` (measured on 2026-10-08 against that
day's bounds). The 2026-10-09 bound changes have their own tests: an unknown tool, a session start record without its
lists, an empty result, the named failure messages, the character-safe cap with its notice and the last non-empty
result; the turn bound was checked with three mutants. The step tests no longer skip without PyYAML: they read the
workflow with the policy test's own loader when PyYAML is absent.

## Alternatives considered

- **Review every pull request automatically** (the action's `docs/solutions.md` example on `pull_request`). Not
  possible under the federation rule, and it would spend on every push.
- **`anthropics/claude-code-security-review`.** Covered by the security-review record; not used.
- **The upstream `/code-review` plugin** (`plugin_marketplaces: https://github.com/anthropics/claude-code.git`).
  The marketplace fetch is unpinned; this repository pins every action by commit.
- **Posting the review as a pull request comment.** It needs `pull-requests: write` and makes a workflow a reviewer;
  both are refused by existing tests. The job summary needs no scope.
- **Comment-triggered runs** (`@claude` in a pull request comment). Anyone can comment; the dispatch form has no
  such surface.

## What would overturn it

- A first activated run stops at the turn limit or the budget with the review unfinished: raise the one bound that
  stopped it, with that run's numbers.
- The numbers step reports a forbidden tool or an MCP server: stop using the workflow and read the action's change.
- GitHub or Anthropic ship a way for a pull request run to authenticate without exposing the token to the pull
  request's workflow text: reconsider an automatic trigger.

## Evidence class

`native_proven` for the flag set on the installed client (the receipt above; not through the action and not on a
GitHub runner). `local_static_analysis`: actionlint 1.17.0 and zizmor 1.30.1 (offline, regular and pedantic), no
findings. `local_integration`: the unit tests above with PyYAML 6.0.3 on Python 3.12. `source_review`: the action
and client sources below. No hosted run of this workflow is part of this record.

## SOTA sources

- anthropics/claude-code-action at `2dca132ff0e0c4094ce6048b422c6915a071210b` (v1.0.247):
  `docs/security.md` (untrusted refs; which files come from the base branch), `docs/setup.md` (federation inputs;
  "a static credential takes precedence and federation will not be used"), `action.yml`,
  `base-action/src/parse-sdk-options.ts` (argument parsing, default setting sources, debug forcing full output),
  `base-action/src/execution-file.ts`;
  <https://github.com/anthropics/claude-code-action/tree/2dca132ff0e0c4094ce6048b422c6915a071210b>.
- Claude Code 2.1.295 `--help` for `--restricted`, `--permission-prompts`, `--tools`, `--settings`,
  `--strict-mcp-config`, `--max-budget-usd`.
- GitHub, OpenID Connect reference, "Filtering for pull_request events" and "Filtering for a specific branch":
  <https://docs.github.com/en/actions/reference/security/oidc>; GitHub Security Lab, Preventing pwn requests:
  <https://securitylab.github.com/research/github-actions-preventing-pwn-requests/>.
- Anthropic: Workload identity federation,
  <https://platform.claude.com/docs/en/manage-claude/workload-identity-federation>; How Claude Code uses prompt
  caching, <https://code.claude.com/docs/en/prompt-caching>; Pricing,
  <https://platform.claude.com/docs/en/about-claude/pricing>; all read 2026-10-08.
