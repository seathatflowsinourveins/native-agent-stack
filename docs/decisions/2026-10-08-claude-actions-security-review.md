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
- `timeout-minutes: 30` (R7, below). Grants: `contents: read`, `pull-requests: read` and `id-token: write`.
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
  `--model claude-opus-5-5 --effort max --max-budget-usd 5 --tools Read,Glob,Grep --allowedTools
  Read,Glob,Grep --restricted --permission-prompts none --setting-sources user --strict-mcp-config` (no `--max-turns`
  since R6; the numbers step bounds the assistant turns), a `--settings`
  that turns hooks off, sets `claudeMdExcludes` over `pr-head/` and `blockReadsOutsideWorkingDirectories`, and denies
  seven read patterns (the `.git` directories, `.env` files, `*.pem` and `*.key`), and `--add-dir` for the prompt
  directory.
- The action step pins `ACTIONS_STEP_DEBUG: 'false'` and passes `show_full_output`, `display_report` and
  `track_progress` as `'false'`; the last two are their defaults, declared in the pinned `action.yml` (lines
  136-139 and 152-155 at `2dca132f`).
- A numbers step checks the bounds (an allow-list of Read, Glob and Grep, where a tool-list entry that is not a
  string is a forbidden tool named `non-string tool entry`; tool and MCP lists present, 1 to 30 assistant turns, a
  client cost estimate of at most $5.50, the $5 budget times the measured overrun factor 1.10, a cache read, result
  text; a budget stop at or under that bound is accepted without result text and named; every unmet bound is named),
  and an artifact keeps `usage.json` (numbers only) for 14 days. The review, the last non-empty result, goes to the
  job summary only when the numbers step accepted the run, whatever the review step's own status, with a line naming
  a budget stop, capped at 60,000 bytes on a character boundary with a line saying so when it was longer.
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
shape and is withdrawn. The numbers step checks the turn cap again from the run's own numbers, and the cost against
$5.50, the budget times the measured overrun factor 1.10 (R6 below). Turns are counted after
the run as distinct assistant message ids, because the result's `num_turns` counts transcript messages, tool results
included: a 12-request run on 2.1.295 reported 57. The flag costs nothing.

## Changed existing test contracts

- `tests.test_workflow_policy.RepositoryPolicyTests.test_write_grants_are_the_reviewed_inventory`: a new entry,
  `claude-security-review.yml:review` with `["id-token: write"]`.
- `tests.test_workflow_policy.RepositoryPolicyTests.test_each_exemption_is_still_needed`: a new `id-token-write`
  exemption for `claude-security-review.yml:review`.
- `tests.test_workflow_security_coverage.NewWorkflowSecurityCoverageTests`: the coverage set gains both workflows,
  each with its own offline zizmor test.

New, in `tests/test_claude_security_review_workflow.py` (45 tests): the review workflow's shape, and its steps' shell
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

## The cost bound: the budget times the measured overrun factor (2026-10-09, R6)

The client stops a run only after its cost has crossed `--max-budget-usd`, so a cost bound equal to the budget fails a normal budget stop. Four measured J8 runs on a $5 budget ended above it: $5.46 (9.2% over, the largest overrun), $5.33, $5.16 and $5.0007, on #895, trading #11, #902 and #894. The cost bound is therefore the budget times 1.10, a factor that rounds up the largest measured overrun; the factor is derived again after this workflow's first three hosted runs. A run at or under the bound passes the cost check. A budget stop (result subtype `error_max_budget_usd`) at or under the bound publishes what the run produced, and the summary names the stop. A run above the bound fails closed and names the overrun. This workflow's budget is $5, so its bound is $5.50.

The command center's read of this PR at R5 (5903ceed) asked for this as a P2. The exception for a workflow that must
fail at its budget does not apply: nothing acts on the review, so a budget stop costs only its unfinished text, and
the summary names it. Per the command center, the J8 micro read of R5 found its five findings fixed and none new at
confidence 80 or above, so this round changes nothing else. The changes, by name:

- **The numbers step**, "Keep the run's numbers and check the bounds":
  - It has the id `numbers` and holds the budget and the bound as `budget=5 cost_bound=5.5`; its comment states the
    factor.
  - `usage.json` gains `budget_stop`, true when the result's subtype is `error_max_budget_usd`. The success check
    accepts a budget stop, and its failure now reads "the run did not end in success or in a budget stop".
  - "no result text" no longer applies to a budget stop. The installed Claude Code 2.1.295 writes that result record
    with `is_error` true, an `errors` list and no result text: its result schema has no result field for an error
    subtype. This comes from a reading of the client's code, not a measured budget stop (SOTA sources below).
  - The cost failure reads "client cost estimate <x> USD, above the 5.5 USD bound (the 5 USD budget times its
    measured overrun factor 1.10)". The run-numbers summary gains "Budget stop: the client stopped the run at its 5
    USD budget (error_max_budget_usd)." and "Over the cost bound: the client cost estimate is <x> USD, above 5.5 USD
    (the 5 USD budget times its measured overrun factor 1.10).", in the toolkit read's (#909) wording.
- **The publish step**, "Publish the security review to the job summary":
  - Its condition is now `!cancelled() && steps.numbers.outcome == 'success'`, in place of `success() &&
    steps.claude_review.outputs.execution_file != ''`, the form #892 uses. The pinned action fails its own step on
    any result that is not a plain success, a budget stop among them (`base-action/src/run-claude-sdk.ts`, its result
    check), and keeps its `execution_file` output, so under `success()` an accepted budget stop was never published.
    The numbers step runs only with an execution file, so its outcome implies one, and a cancelled run publishes
    nothing. The job stays failed, with the review published.
  - The same condition publishes a success whose `num_turns` exceeds `--max-turns`, which the action also fails:
    `--max-turns` reaches the SDK as `maxTurns` (`base-action/src/parse-sdk-options.ts`), and `num_turns` counts
    transcript messages (57 for a 12-request run). The assistant-turn bound in the numbers step is the one this
    workflow applies. ("`--max-turns` dropped from `claude_args`" below removes the flag, so this case no longer
    arises.)
  - A budget stop adds the line "Budget stop: the client stopped the run at its budget (error_max_budget_usd) before
    it finished; the text above, if any, is what it wrote before the stop." The step's comment says when it
    publishes.
- **Tests (44; 42 at R5):**
  - New: `test_a_budget_stop_at_or_under_the_bound_is_accepted_and_named`, where budget stops at $5.20 and $5.50
    pass and are named and one at $5.51 fails with the overrun named; `test_a_budget_stop_is_published_and_named`;
    and the helper `budget_stop()`, which builds the record as 2.1.295 writes it.
  - Changed: `test_the_caps_hold_at_the_bound_and_fail_just_above_it` ($5.50 passes; $5.51 fails, named in the
    failure and in the summary), `test_an_unmet_bound_fails_after_the_numbers_were_kept` ($5.51),
    `test_the_step_names_every_unmet_bound` ($6 and the new message),
    `test_a_bounded_cached_read_only_run_is_accepted_and_only_numbers_and_fixed_names_are_kept` (`budget_stop` among
    the record's keys, false), and
    `test_the_review_is_published_only_after_the_bounds_check_passed_and_only_numbers_are_uploaded` (the numbers
    step's id and both steps' conditions, exactly).
- **Weakened copies, 2026-10-09:** fourteen new ones weaken this round's changes. They drop the factor (the bound
  back at the $5 budget), widen it to 1.2, make the cost check refuse the bound itself, stop accepting a budget stop,
  require a budget stop to carry result text, waive the result-text check for every run, read `budget_stop` from
  another subtype, drop the stop or the overrun line from the run-numbers summary, put the publish condition back on
  `success()`, gate it on `always()` instead of `!cancelled()`, leave out `!cancelled()` (so `success()` applies
  again), remove the numbers step's id, or drop the stop line from the publish step. With the nineteen of R5's that
  still apply (its three cost-bound copies targeted the bare check this round replaced), all 33 fail a test with
  PyYAML 6.0.3 present. Without PyYAML, 17 do; four of the sixteen that pass are new, the three publish conditions
  and the numbers step's id, which only a shape test reads. (After the two subsections below: 35 copies, all failing
  a test with PyYAML present; without it 17 fail and 18 pass, the three new copies among those that pass, as the
  other argument copies do.)
- The by-name list above and "Cost of one run" state the bound.
- **The SOTA sources** below gain the action files behind R5 and R6, with their lines and the version they were read
  at, and the installed client's result-record code.

### `--max-turns` dropped from `claude_args` (command center decision, 2026-10-09)

At the pin, anthropics/claude-code-action `2dca132f` (v1.0.247), `base-action/src/run-claude-sdk.ts` lines 241-250
throw "Claude reported a successful result after N turns, exceeding the configured maximum" when a successful result
has `num_turns` above `maxTurns`, the value `--max-turns` sets. The check came in with commit `6ef6450f`, "fix:
enforce max turns from claude args (#1607)", on 2026-08-07. On Claude Code 2.1.295 the result's `num_turns` counts
transcript messages, tool results included: a local run of 12 API requests (distinct assistant message ids) under
`--max-turns 12` reported `num_turns` 57 (the LR entry of `local-parity-receipt.json`, recorded with #892, not carried
in this PR). With `--max-turns 30`, a normal successful review would therefore fail the action step. This is a code
reading of the pinned source plus a local measurement, not a hosted run. Upstream has no fix as of 2026-10-09:
upstream `main` is identical to `2dca132f` on that date.

- `--max-turns 30` is removed from `claude_args`. The runaway bounds that stay are the client budget, checked against
  $5.50 (the budget times 1.10), and the numbers step's own turn bound, 1 to 30 distinct assistant message ids, which
  fails closed. The prompt's sentence "You have at most 30 turns" is unchanged.
- The publish step's comment no longer names a success over `--max-turns` among the results the action fails; it says
  why `claude_args` passes no `--max-turns`.
- `CLAUDE_ARGS` in the test module no longer holds `--max-turns 30`, and
  `test_claude_has_three_read_tools_and_fixed_bounds` no longer expects it and asserts that `--max-turns` is absent.
  The turn-bound and caps tests are unchanged. The module still has 44 tests.
- Record sentences changed with this subsection: the `claude_args` of the by-name list, the publish-step bullet of the
  R6 changes and "Evidence class"; the `docs/github-automation.md` bullet now says 30 assistant turns, checked after
  the run.
- The weakened copy "`--max-turns 30` put back" fails `test_claude_args_are_exactly_the_reviewed_list` and
  `test_claude_has_three_read_tools_and_fixed_bounds` with PyYAML 6.0.3; without PyYAML both skip, as the other
  argument copies do. It replaces the R5 copy "`--max-turns` left at 12", whose anchor text no longer exists; with
  the two copies below, all 35 copies fail a test with PyYAML present, and 17 do without it.

#### Upstream issue (draft, not filed; the owner decides)

> Title: success with num_turns > maxTurns fails the step, but num_turns counts messages, not turns.
> base-action/src/run-claude-sdk.ts:241-250 (v1.0.247, 2dca132f) compares `resultMessage.num_turns` with
> `sdkOptions.maxTurns`. On Claude Code 2.1.295 the result's num_turns counts transcript messages (tool results
> included): a headless run of 12 requests under `--max-turns 12` reported num_turns 57. A normal successful run
> under `--max-turns N` therefore throws "exceeding the configured maximum". Repro: any `claude_args: --max-turns 5`
> run that makes a few tool calls and succeeds.

### The exact pins tell `true` from `1` (2026-10-09)

`test_claude_args_are_exactly_the_reviewed_list` and `test_settings_are_exactly_the_reviewed_json` compared the
decoded `--settings` JSON with the expected dict by `==`; in Python `1 == True`, so `"disableAllHooks": 1` passed both.
Both now compare canonical JSON (the helper `canonical()`: `json.dumps` with `sort_keys=True` and
`separators=(",", ":")`), which tells them apart. The weakened copies `"disableAllHooks":1` and
`"blockReadsOutsideWorkingDirectories":1` (this workflow has no `autoMemoryEnabled` key, so the second copy writes its
other boolean as `1`) each fail both exact pins and
`test_settings_turn_hooks_off_exclude_the_heads_instruction_files_and_confine_reads` with PyYAML 6.0.3; without
PyYAML those shape tests skip.

## R7 (2026-10-09): the job timeout is 30 minutes

The review job's `timeout-minutes` rises from 20 to 30, the command center's decision of 2026-10-09 under its
standing rule to raise any cap that would truncate a normal run:

- With `--max-turns` removed in R6, the numbers step's bound of 30 assistant turns is the turn limit. The job timeout
  is a further limit, and the one that leaves no record: a timeout cancels the review step before it writes
  `execution_file`, so the numbers step is skipped and nothing is published or uploaded.
- The one measured run of this shape, `LR` (Opus 5.5 at max effort; the LR entry of `local-parity-receipt.json`,
  recorded with #892, not carried in this PR), took 512,670 ms for 12 assistant turns, about 43 seconds a turn. At
  that pace 30 turns take 1,281,675 ms, about 21.4 minutes of client time, before checkout and setup, so a 20-minute
  timeout would cancel a run inside the approved bounds.
- #892 and #894 use 30 minutes.
- **Tests (45; 44 at R6):** new, `test_the_job_timeout_leaves_room_for_the_30_turn_bound` pins `timeout-minutes` to
  the integer 30, as #894's test of that name does.
- **Weakened copy, 2026-10-09:** `timeout-minutes` back at 20 fails that test with PyYAML 6.0.3 present. With it, all
  36 copies fail a test with PyYAML present; without PyYAML 17 fail and 19 pass, the new copy among those that pass,
  since only a shape test reads it.

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
`Read(./**/.env.*)`, `Read(./**/*.pem)`, `Read(./**/*.key)`) and runs Opus 5.5 with at most 30 assistant turns
(checked after the run; no `--max-turns`) and $5 through the action; no run of that configuration, local or hosted, is part of this record. What has run is model-free and
local: the shells of the review's guard, binding, symbolic-link, diff, numbers and publish steps and of the flag's
notice step, on synthetic inputs under the unit tests above.
`local_static_analysis`: actionlint 1.17.0 and zizmor 1.30.1 (offline, regular and pedantic), no findings on either
workflow. `local_integration`: the unit tests above with PyYAML 6.0.3 on Python 3.12. `source_review`: the sources
below. No hosted run of either workflow is part of this record.

## SOTA sources

- anthropics/claude-code-action at `2dca132ff0e0c4094ce6048b422c6915a071210b` (v1.0.247): `docs/solutions.md`
  ("Security Review" example), `docs/security.md`, `docs/setup.md`, `action.yml`;
  <https://github.com/anthropics/claude-code-action/tree/2dca132ff0e0c4094ce6048b422c6915a071210b>.
  Read on 2026-10-09 at v1.0.246 (`38c80c1`) for R5 and R6:
  - `base-action/src/run-claude-sdk.ts`: line 222 writes the execution file before the result check; lines 241-256
    and 280-298 fail the step on a success whose `num_turns` exceeds `maxTurns` and on any result other than an
    error-free success.
  - `base-action/src/parse-sdk-options.ts`, lines 207-208 and 318-321: `--max-turns` becomes `maxTurns`.
  - `src/github/operations/git-config.ts`, lines 129-134, and `src/modes/agent/index.ts`, lines 52-61: the R5 shared
    sentence.
  - `src/entrypoints/run.ts`, lines 316-324: a failed run still sets the `execution_file` output.

  Per the command center's compare, v1.0.247 changes only the bundled Claude Code version
  (`base-action/action.yml`, `src/entrypoints/run.ts`, and package and lock files), so the first four files do not
  differ at the pin. The `run.ts` lines were read at `38c80c1` only.
- anthropics/claude-code-security-review at `0c6a49f1fa56a1d472575da86a94dbc1edb78eda`: `action.yml`, `README.md`,
  `claudecode/constants.py`, `scripts/comment-pr-findings.js`;
  <https://github.com/anthropics/claude-code-security-review/tree/0c6a49f1fa56a1d472575da86a94dbc1edb78eda>.
- Anthropic, Model deprecations: <https://platform.claude.com/docs/en/about-claude/model-deprecations>.
- GitHub, OpenID Connect reference: <https://docs.github.com/en/actions/reference/security/oidc>; workflow syntax,
  `on.pull_request.paths`: <https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax>.
- Claude Code 2.1.295 `--help` for `--restricted` and `--permission-prompts`; all read 2026-10-08.
- Claude Code 2.1.295, the installed binary, read on 2026-10-09: its budget-exhausted branch builds the
  `error_max_budget_usd` result with `is_error` true and an `errors` list, and its schema for error results has no
  result field. This is a reading of the client's code, not a measured budget stop.
