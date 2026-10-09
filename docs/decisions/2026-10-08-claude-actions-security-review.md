# On-demand security review by the Claude action, and a model-free flag on risky paths — 2026-10-08

Two workflows. `security-review-flag.yml` runs on every pull request that touches `.github/workflows/`,
`scripts/hooks/`, `tools/credentials/`, `adoption/credential-inventory.json` or the paper-trading blueprints, and
writes one notice to its job summary: a security review is due, with the exact `gh workflow run` command for that
commit. It runs no model, checks out nothing, holds no token scope and requests no OIDC token.
`claude-security-review.yml` is that review: dispatched by hand from `main` with the pull request number and the
exact head commit, it runs `anthropics/claude-code-action` v1.0.247 with a security-review prompt. Its
federation, read-only fence, bounds and accounting are stated in full below; the on-demand pull request review
(`docs/decisions/2026-10-08-claude-actions-pr-review.md`, added by #894) uses the same values. It runs only while the repository
variable `CLAUDE_SECURITY_REVIEW_ENABLED` is `true`. Nothing in this change starts a model run.

## What the workflows do, by name

Both workflows are new, so this is all of their behaviour. The list follows the pre-cue read of the sibling
harness-audit PR (#892, 2026-10-09), which found changes its record had not named; the same review was applied here.

- `security-review-flag.yml`: `pull_request` on the listed paths; `permissions: {}` and `cache-mode: none` at the
  workflow level; one notice in the job summary with the `gh workflow run` command for that head; no checkout, model,
  secret, variable or OIDC token.
- `claude-security-review.yml`: `workflow_dispatch` only, with inputs `pr_number`, `head_sha` and optional `paths`;
  a concurrency group per pull request, without cancelling a run in progress.
- Its job condition: this repository (slug guard), the `main` ref, `github.actor` and `github.triggering_actor` both
  the repository owner, the first attempt of a run, and `CLAUDE_SECURITY_REVIEW_ENABLED == 'true'`. A dispatch by
  anyone else, or a re-run, is skipped.
- `timeout-minutes: 20`. Grants: `contents: read`, `pull-requests: read` and `id-token: write`.
- A guard step stops the job with exit 2 on debug signals, a pre-existing `~/.claude/settings.json` (a dangling
  symlink included) or a malformed input; a binding step stops it with exit 2 unless the pull request is open, from
  this repository, targets `main` and has exactly the requested head. The binding step has no step id: its id `bind`
  was referenced nowhere and was removed.
- The head is checked out as data under `pr-head/` with main at the root, and the diff is written by git in the root
  only, with diff drivers off. The optional paths expand as `${scope[@]+"${scope[@]}"}`, so an empty list does not
  trip `set -u` on bash before 4.4 (macOS `/bin/bash` 3.2), which treats an empty array as unset.
- Right after the head checkout, a model-free step, "Remove symbolic links from the pull request head", runs
  `find pr-head -path pr-head/.git -prune -o -type l -exec rm -f {} +` under `set -euo pipefail`: every symbolic link
  under `pr-head/` is deleted before the model starts, and the checkout's own `pr-head/.git` is not entered (added in
  R5, 2026-10-09, below).
- The action step runs `anthropics/claude-code-action@2dca132ff0e0c4094ce6048b422c6915a071210b` (v1.0.247), federated
  through the repository variables `ANTHROPIC_FEDERATION_RULE_ID`, `ANTHROPIC_ORGANIZATION_ID`,
  `ANTHROPIC_SERVICE_ACCOUNT_ID` and `ANTHROPIC_WORKSPACE_ID` (no stored key), with `claude_args`
  `--model claude-opus-5-5 --effort max --max-turns 30 --max-budget-usd 5 --tools Read,Glob,Grep --allowedTools
  Read,Glob,Grep --restricted --permission-prompts none --setting-sources user --strict-mcp-config`, a `--settings`
  that turns hooks off, sets `claudeMdExcludes` over `pr-head/` and `blockReadsOutsideWorkingDirectories`, and denies
  seven read patterns (the `.git` directories, `.env` files, `*.pem` and `*.key`), and `--add-dir` for the prompt
  directory.
- The action step pins `ACTIONS_STEP_DEBUG: 'false'` and passes `show_full_output`, `display_report` and
  `track_progress` as `'false'`; the last two are their defaults, declared in the pinned `action.yml` (lines
  136-139 and 152-155 at `2dca132f`).
- A numbers step checks the bounds (an allow-list of Read, Glob and Grep, where a tool-list entry that is not a
  string is a forbidden tool named `non-string tool entry`; tool and MCP lists present, 1 to 30 assistant turns, at
  most $5, a cache read, result text; every unmet bound is named), and an artifact keeps
  `usage.json` (numbers only) for 14 days. The review, the last non-empty result, goes to the job summary only when
  the bounds passed, capped at 60,000 bytes on a character boundary with a line saying so when it was longer.
  Nothing is posted to the pull request. A final step, "Require the run's execution file", fails the job when the
  review step reports success without an execution file, so a green run always means the bounds were checked.
- The job summary, and with it the published review, is public, as the repository is; a finding that should not be
  public before a fix belongs on the local route instead ("Visibility" below).
- The pin, v1.0.247, is hours old: the user ended the seven-day cooldown for clean releases on 2026-10-03
  (`docs/decisions/2026-10-03-currency-wave-w1.md`, "Holds and cooldown waiver"), which keeps qualification.

Outside this record, `docs/github-automation.md` gains the "Security review on demand" bullet, which states the
action pin, the federation variables, the read-only tools and the bounds itself, and
`docs/decisions/2026-10-04-ci-least-privilege.md` lists the review job in its write-grant table and both workflows in
its per-workflow table, names each exempt job in "Federation exemption (2026-10-08)" and adds an addendum for the
review job's exemption.

The pre-cue read of 459777d6 left these findings standing at df440f48, fixed on 2026-10-09 in two steps. First
(fbe30ad0): the link to the pull request review's record said that file comes with #894 and resolves once #894
lands; the `docs/github-automation.md` bullet named #894 as where the shared pin, federation, fence and bounds are
defined; the binding step's unused id `bind` was removed (no workflow step or test referred to it); this section
named the final step, the bash 3.2 expansion and the Visibility section that df440f48 added, and the documentation
outside this record; and the test count, stale at 32, became 34, with df440f48's two tests named. The J8 micro read
of that step (459777d6 to fbe30ad0) found the cross-PR items only partly fixed, because they still rested on #894
being present. Second: the record and the docs bullet now stand alone. They state the pin, the federation
variables, the fence and the bounds themselves, name the pull request review's record by plain path instead of a
link, and cite `receipt.json` from this PR's own tree.

## Why not `anthropics/claude-code-security-review`

Read at its only pin, `0c6a49f1fa56a1d472575da86a94dbc1edb78eda` (the repository has no release and no tag; last
commit 2026-02-11):

- It authenticates with an API key only (`claude-api-key`, required). This repository authenticates by workload
  identity federation and stores no Anthropic key.
- Its default model is `claude-opus-4-1-20250805` (`claudecode/constants.py`), which Anthropic's model deprecations
  page lists as retired on 2026-08-05.
- It submits a pull request review itself (`scripts/comment-pr-findings.js`, `POST .../pulls/{n}/reviews`) and its
  README asks for `pull-requests: write`; both are refused by this repository's policy tests.
- It installs Claude Code and Python packages unpinned at run time (`npm install -g @anthropic-ai/claude-code`,
  `pip` with `>=` floors) and is not on this repository's action allow-list.
- Its README: "This action is not hardened against prompt injection attacks and should only be used to review
  trusted PRs".

This repository rejected it before (R68, `docs/decisions/2026-09-28-community-sweep.md`). The review here uses the
already-allowed `anthropics/claude-code-action` with a prompt built from that action's own security-review example
(`docs/solutions.md`, "Security Review") and this repository's own risk classes.

## Why the flag and the review are separate

The model cannot run on a `pull_request` event under this repository's federation rule: a pull request run's OIDC
subject ends in `:pull_request` and the rule matches runs on `main` (GitHub, OpenID Connect reference). Widening the
rule would hand a token to a pull request's own workflow text. So the event-driven part has no model and no
credential, and the model run is a manual dispatch from `main`. The flag is not a required check and cannot fail a
pull request; it only says a review is due.

The flag's two event values (pull request number and head commit) reach its shell as environment variables and are
checked as text before they are written. It uses `cache-mode: none` and `permissions: {}`, like the repository's
other pull request workflows.

## The prompt

The review checks what the change touches against two lists. Repository-specific: GitHub Actions (permissions,
write grants, unpinned actions, triggers reachable from untrusted pull requests, untrusted text reaching a shell or
a model, secrets or OIDC tokens within reach of untrusted code, debug or full-output logging); hooks and guards (a
rule that can be bypassed, a pattern that no longer matches, a weakened test); credential tooling (a value that can
reach a log, command line, file or child process; store path, mode or masking changes); the paper-trading path (a
call that could reach a live account, a limit or halt that can be skipped). General, from the action's own example:
the OWASP Top 10 classes, hardcoded secrets, weak cryptography, unsafe deserialization, server-side request forgery
and time-of-check to time-of-use races. Findings must be checked against the files; unconfirmed suspicions are
listed separately; a value that looks like a credential is never printed, only its file and line.

## Visibility

The repository is public, so the job summary of every run, and with it the published review, is readable by anyone.
A security finding that should not be public before a fix (an undisclosed vulnerability) does not belong in this
workflow: the local route on the second key (`api-actions` reader jobs) keeps its report off GitHub, and the model-free
flag workflow says only that a review is due. A review step that reports success without an execution file fails the
job in a final step, so a green run always means the bounds were checked.

## Effort

`--effort max` in `claude_args`, set under the command center's effort mapping of 2026-10-08, which runs judgment work (designated reads, adjudication, pull request and security reviews, audits) at `max`. Every job records its level and the reason, because an unset level is a defect. The level has to be in `claude_args`: `--restricted` ignores the settings files that would otherwise carry a session's level, and on the Claude API Opus 5.5 runs at `medium` when a request leaves effort unset (bundled `claude-api` skill 2.1.295, `shared/model-migration.md`). `claude --help` (2.1.295) lists `low, medium, high, xhigh, max`. At `max`, thinking takes a larger share of the output than at the default level; the figures below come from runs at `max`, and the client budget still bounds each run.

## Cost of one run

Caps from measurement (command center, 2026-10-09): 30 assistant turns and a $5 client budget, each a multiple of
the measured need. A cap bounds a runaway; it does not trim a normal run. This review has no runs of its own yet. It has
the task shape of the on-demand pull request review (#894): the same fence, model and effort, with a security prompt,
so it takes that review's caps until its own runs replace them. That review's prompt and `claude_args`, reading one
pull request in full, used 12 of its 12 assistant turns and cost $2.23 (the client reported $1.87). It used
every turn it had, so 12 is a floor rather than a 95th percentile, and 2.5 times that floor gives 30 turns; twice
$2.23 is about $4.5, rounded up to $5. Four delta re-reads of the same pull request took 5, 6, 7 and 6 turns and cost
$1.75, $1.35, $1.54 and $0.73. Those runs used the installed Claude Code 2.1.295 directly, not the action, and billed
a second Anthropic key; a hosted run bills the federated organization instead, so the caps are the owner's per-run
spend limit once the enabling variable is set. Expected cost per run: about $2, by that shape, not yet measured. The
earlier dry estimate here, $0.70 to $1.30 for a diff of up to about 1,000 lines, was below the measured cost of that
shape and is withdrawn. The numbers step checks both caps again from the run's own numbers. Turns are counted after
the run as distinct assistant message ids, because the result's `num_turns` counts transcript messages, tool results
included: a 12-request run on 2.1.295 reported 57. The flag costs nothing.

## Changed existing test contracts

- `tests.test_workflow_policy.RepositoryPolicyTests.test_write_grants_are_the_reviewed_inventory`: a new entry,
  `claude-security-review.yml:review` with `["id-token: write"]`.
- `tests.test_workflow_policy.RepositoryPolicyTests.test_each_exemption_is_still_needed`: a new `id-token-write`
  exemption for `claude-security-review.yml:review`.
- `tests.test_workflow_security_coverage.NewWorkflowSecurityCoverageTests`: the coverage set gains both workflows,
  each with its own offline zizmor test.

New, in `tests/test_claude_security_review_workflow.py` (42 tests): the review workflow's shape, and its steps' shell
taken from the workflow file and run against a local stand-in for `gh` and a local git repository, and the flag's trigger paths, empty permissions, absence of any secret,
variable, OIDC token, checkout or model, and its notice. Eleven weakened copies of the two workflows each fail at
least one test (measured on 2026-10-08 against that day's bounds). The 2026-10-09 bound changes have their own tests
(an unknown tool, a start record without lists, an empty result, the named failures, the character-safe cap and the
last non-empty result), the turn bound was checked with three mutants, and the step tests no longer skip without
PyYAML. df440f48 added `test_a_green_run_always_has_an_execution_file` and
`test_no_paths_expands_safely_under_set_u_on_old_bash`, and `test_the_action_is_pinned_and_takes_federation_inputs_only`
now also asserts `display_report` and `track_progress` as `'false'`.

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
60,001 bytes (no notice, then the notice); a copy that writes with `jq -r` again fails it. The step's comment now
says it publishes the last non-empty result text, which it does.

## Symbolic links, exact pins, non-string tool entries, caps and what has run (2026-10-09, R5)

The command center's security read and the GPT designated read of this PR, both at f5f1fd22 (2026-10-09), and the
command center's caps from measurement of the same day asked for the changes below; this round keeps to quality and
correctness.

- **Symbolic links in the pull request head (P2).** A link in the head to the job process's environment
  (`/proc/self/environ`) or to `../.git/config` could carry what it points at into the review, and from there into
  the public job summary. `--restricted` confines the file tools to the working directories, `--add-dir` included;
  `claude --help` on 2.1.295 does not say whether a link's target is resolved before that check or the deny rules
  apply. The new step "Remove symbolic links from the pull request head", right after the head checkout, deletes
  every link under `pr-head/` before the model starts; it runs no model and nothing from the head.
- New tests: `test_symbolic_links_in_the_head_are_removed_and_nothing_else` runs the step's shell on a tree holding
  a link to `/proc/self/environ`, a link to `../.git/config`, a link inside a subdirectory to the root `.git`
  directory and a link inside `pr-head/.git`: the first three are gone, and the regular files, both `.git/config`
  files and `pr-head/.git` with its link stay. `test_the_symbolic_link_step_has_no_condition_and_a_fixed_script`
  pins the whole step: no `if:`, no `continue-on-error`, nothing in its shell but the deletion.
- Changed tests: `test_steps_run_in_the_order_the_binding_depends_on` requires the step right after the head
  checkout. `test_no_step_executes_anything_from_the_pull_request_head` exempts that one step by name, as the only
  shell that names `pr-head/`, and pins its script instead; it now checks `working-directory` on every step, that
  one included.
- **Exact pins.** `test_claude_args_are_exactly_the_reviewed_list` compares all of `claude_args`, each line split
  with `shlex.split` as `cli_settings()` splits it, after `${{ runner.temp }}` is replaced by a stand-in path (the
  runner substitutes it before the action reads the text), with the `--settings` value decoded.
  `test_settings_are_exactly_the_reviewed_json` compares the whole `--settings` JSON. A widened or repeated
  `--add-dir`, a repeated budget or turn flag, and `permissions.additionalDirectories` now each fail a test; the
  existing tests checked that each expected line was present, so an added line passed them.
- **What has run.** "Evidence class" said this workflow adds `--setting-sources user` and that it "has not run,
  locally or hosted". Both were wrong by this record's own evidence: the fence smoke's receipt shows that flag in
  two of its three runs, and the review's model-free steps run locally under the unit tests. The paragraph now says
  what ran where, and names `blockReadsOutsideWorkingDirectories`, which the smoke's settings did not hold, among
  this workflow's additions.
- **Non-string tool entries (GPT designated read, P2).** The numbers step filtered entries that are not strings out
  of the session's tool list before checking it, so a start record listing `{"name":"Bash"}`, `null` or `17` passed
  every bound and the review would have been published. That was a synthetic reproduction; it does not show that the
  client emits such entries. Each such entry is now a forbidden tool, named `non-string tool entry` in `usage.json`,
  in the summary's tools column and in the bounds message; string entries are checked against Read, Glob and Grep as
  before, and the step's comment names the new case. `test_a_tool_entry_that_is_not_a_string_is_a_forbidden_tool`
  refuses each of the three; the valid list and a string `Bash` stay covered by the existing tests. Of the tool-list
  shape follow-up below, a non-empty list and the `tool_use` names in assistant messages remain open.
- **Caps from measurement (command center, 2026-10-09).** `--max-turns` goes from 12 to 30 and `--max-budget-usd`
  from 3 to 5, derived in "Cost of one run" above, which now restates the derivation with its measured figures and
  withdraws the earlier dry estimate. The numbers step's bounds follow: 1 to 30 assistant turns and at most $5, and
  the bounds message names each with its new number. The prompt now says "at most 30 turns", and the workflow's
  opening comment, the by-name list, "Evidence class" and the `docs/github-automation.md` bullet carry the new
  values. The last sentence of "Effort" says the figures come from runs at `max` instead of calling the estimate a
  floor. Changed tests: `test_claude_args_are_exactly_the_reviewed_list` and
  `test_claude_has_three_read_tools_and_fixed_bounds` pin the new values, the latter also the prompt's turn count;
  `test_an_unmet_bound_fails_after_the_numbers_were_kept`, `test_the_step_names_every_unmet_bound` and
  `test_the_turn_bound_counts_assistant_turns_not_transcript_messages` go just past the caps (31 turns, $5.01 or
  $5.50). New: `test_the_caps_hold_at_the_bound_and_fail_just_above_it`, where 30 turns and $5 pass and 31 turns and
  $5.01 fail, each named in the bounds message.
- The module has 42 tests (36 before). On 2026-10-09, twenty-two weakened copies of the review workflow were run, by
  a script kept outside the repository, with PyYAML 6.0.3 present, as the Linux validate job has it, and each failed
  at least one of the tests. Six weaken the new step: it is
  removed, skipped with `if: ${{ false }}`, given `continue-on-error: true`, stripped of `-type l` or of the `.git`
  prune, or moved before the head checkout. Six weaken the arguments: a second `--add-dir /`, `--add-dir` widened to
  the whole temporary directory, a repeated `--max-turns 50`, a repeated `--max-budget-usd 30`, an added
  `permissions.additionalDirectories`, or the dropped deny rule `Read(./**/*.key)`; five of these pass f5f1fd22's
  tests, and only the widened `--add-dir` failed one there. Two weaken the tool check: the filter restored, or
  non-string entries named `other` again. Eight weaken the caps: `--max-turns` left at 12 or `--max-budget-usd` at
  3, the turn bound left at 12 or widened to 31, the cost bound left at 3, widened to 6 or refusing $5 itself, and
  the prompt left at 12 turns.
- Without PyYAML, as on the macOS validate job, the module's shape tests skip. Of the new tests, three run there:
  `test_symbolic_links_in_the_head_are_removed_and_nothing_else`,
  `test_a_tool_entry_that_is_not_a_string_is_a_forbidden_tool` and
  `test_the_caps_hold_at_the_bound_and_fail_just_above_it`, with the three changed bounds tests. The three other new
  tests, the step pin and both exact pins, skip, as do the changed order, pull-request-head and fixed-bounds tests.
  Measured the same day without PyYAML, ten of the twenty-two copies still fail a test. The twelve that pass change
  only what the skipped tests read: the step's condition, `continue-on-error` or position, `claude_args`, the
  `--settings` JSON and the prompt's turn count.

In agent mode the action rewrites the checkout's `origin` URL with the job token (`src/github/operations/git-config.ts:129-134`, called from `src/modes/agent/index.ts:52-61` at `2dca132f`), so `persist-credentials: false` does not keep the token out of `.git/config`; the deny rules `Read(./.git/**)` and `Read(./**/.git/**)` are what keep the model from reading it, as two 2026-10-09 probes on the installed 2.1.295 measured.

A link in the head to `../.git/config` would reach that file under a path those rules do not name, which is why the
step above removes links instead of relying on the client.

Security hardening from the 2026-10-09 read (flag-path additions, a fork notice, debug-value widening, tool-list shape, extra deny rules, token-source and guard-step assertions) is filed as follow-ups before any enabling variable is set.

## Alternatives considered

- **`anthropics/claude-code-security-review`.** Rejected above.
- **The built-in `/security-review` command as the prompt.** Not used: the action's docs cover custom commands and
  skills as prompts, and whether the built-in command runs under `--restricted` in a non-interactive session was not
  established.
- **A model review on every pull request touching these paths.** Not possible under the federation rule, and it
  would spend on every push.
- **A required check.** Not proposed: the flag says a review is due; whether a review is required before landing is
  a ruling for the command center and the owner.

## What would overturn it

- The first activated run stops at a bound with the review unfinished: raise that bound with that run's numbers.
- A federation rule appears that can serve pull request runs without exposing the token to the pull request's
  workflow text: reconsider an event-driven review.
- `anthropics/claude-code-security-review` ships releases with federation support and no write path: compare it on
  the same pull requests.

## Evidence class

`native_proven` for the fence flags on the installed client (`--restricted`, `--tools`/`--allowedTools`
Read,Glob,Grep, `--strict-mcp-config`, `--permission-prompts none`, `--settings` with hooks off and three deny rules,
on Claude Haiku 5.5 with 10 turns and $0.50; `evidence/artifacts/claude-actions-fence-smoke-20261008/receipt.json`,
recorded with the pull request review; this PR carries a byte-identical copy of that file, as #892 and #894 do, so
the citation does not depend on which PR lands first). Two of that receipt's three runs also passed
`--setting-sources` (`run2-user` with `user`, `run2-user-project-local` with `user,project,local`), so
`--setting-sources user` has run there. The smoke ran the client directly on the workstation, not through the
action, whose parser path the receipt records as replayed offline, not run. This workflow adds `--add-dir`,
`--effort max`, `blockReadsOutsideWorkingDirectories` and four more deny rules (`Read(./pr-head/.git/**)`,
`Read(./**/.env.*)`, `Read(./**/*.pem)`, `Read(./**/*.key)`) and runs Opus 5.5 with 30 turns and $5 through the
action; no run of that configuration, local or hosted, is part of this record. What has run is model-free and
local: the shells of the review's guard, binding, symbolic-link, diff, numbers and publish steps and of the flag's
notice step, on synthetic inputs under the unit tests above.
`local_static_analysis`: actionlint 1.17.0 and zizmor 1.30.1 (offline, regular and pedantic), no findings on either
workflow. `local_integration`: the unit tests above with PyYAML 6.0.3 on Python 3.12. `source_review`: the sources
below. No hosted run of either workflow is part of this record.

## SOTA sources

- anthropics/claude-code-action at `2dca132ff0e0c4094ce6048b422c6915a071210b` (v1.0.247): `docs/solutions.md`
  ("Security Review" example), `docs/security.md`, `docs/setup.md`, `action.yml`;
  <https://github.com/anthropics/claude-code-action/tree/2dca132ff0e0c4094ce6048b422c6915a071210b>.
- anthropics/claude-code-security-review at `0c6a49f1fa56a1d472575da86a94dbc1edb78eda`: `action.yml`, `README.md`,
  `claudecode/constants.py`, `scripts/comment-pr-findings.js`;
  <https://github.com/anthropics/claude-code-security-review/tree/0c6a49f1fa56a1d472575da86a94dbc1edb78eda>.
- Anthropic, Model deprecations: <https://platform.claude.com/docs/en/about-claude/model-deprecations>.
- GitHub, OpenID Connect reference: <https://docs.github.com/en/actions/reference/security/oidc>; workflow syntax,
  `on.pull_request.paths`: <https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax>.
- Claude Code 2.1.295 `--help` for `--restricted` and `--permission-prompts`; all read 2026-10-08.
