# On-demand security review by the Claude action, and a model-free flag on risky paths — 2026-10-08

Two workflows. `security-review-flag.yml` runs on every pull request that touches `.github/workflows/`,
`scripts/hooks/`, `tools/credentials/`, `adoption/credential-inventory.json` or the paper-trading blueprints, and
writes one notice to its job summary: a security review is due, with the exact `gh workflow run` command for that
commit. It runs no model, checks out nothing, holds no token scope and requests no OIDC token.
`claude-security-review.yml` is that review: dispatched by hand from `main` with the pull request number and the
exact head commit, it runs `anthropics/claude-code-action` v1.0.247 with a security-review prompt and the same
read-only fence, bounds and accounting as the on-demand pull request review
([2026-10-08-claude-actions-pr-review.md](2026-10-08-claude-actions-pr-review.md)). It runs only while the
repository variable `CLAUDE_SECURITY_REVIEW_ENABLED` is `true`. Nothing in this change starts a model run.

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
  this repository, targets `main` and has exactly the requested head.
- The head is checked out as data under `pr-head/` with main at the root, and the diff is written by git in the root
  only, with diff drivers off.
- The action step pins `ACTIONS_STEP_DEBUG: 'false'` and passes `show_full_output`, `display_report` and
  `track_progress` as `'false'`; the last two are their defaults, declared in the pinned `action.yml` (lines
  136-139 and 152-155 at `2dca132f`).
- A numbers step checks the bounds (an allow-list of Read, Glob and Grep, tool and MCP lists present, 1 to 12
  assistant turns, at most $3, a cache read, result text; every unmet bound is named), and an artifact keeps
  `usage.json` (numbers only) for 14 days. The review, the last non-empty result, goes to the job summary only when
  the bounds passed, capped at 60,000 bytes on a character boundary with a line saying so when it was longer.
  Nothing is posted to the pull request.
- The pin, v1.0.247, is hours old: the user ended the seven-day cooldown for clean releases on 2026-10-03
  (`docs/decisions/2026-10-03-currency-wave-w1.md`, "Holds and cooldown waiver"), which keeps qualification.

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

`--effort max` in `claude_args`, set under the command center's effort mapping of 2026-10-08, which runs judgment work (designated reads, adjudication, pull request and security reviews, audits) at `max`. Every job records its level and the reason, because an unset level is a defect. The level has to be in `claude_args`: `--restricted` ignores the settings files that would otherwise carry a session's level, and on the Claude API Opus 5.5 runs at `medium` when a request leaves effort unset (bundled `claude-api` skill 2.1.295, `shared/model-migration.md`). `claude --help` (2.1.295) lists `low, medium, high, xhigh, max`. At `max`, thinking takes a larger share of the output than at the default level, so the estimate below is a floor; the client budget still bounds each run.

## Cost of one run

As for the pull request review: dry estimate $0.70 to $1.30 for a diff up to about 1,000 lines at Claude Opus 5.5's
standard prices, a $3 client budget checked again from the run's own numbers, 12 turns (checked after the run as distinct assistant message ids, because the result's `num_turns` counts transcript messages, tool results included: a 12-request run on 2.1.295 reported 57). The flag costs nothing.

## Changed existing test contracts

- `tests.test_workflow_policy.RepositoryPolicyTests.test_write_grants_are_the_reviewed_inventory`: a new entry,
  `claude-security-review.yml:review` with `["id-token: write"]`.
- `tests.test_workflow_policy.RepositoryPolicyTests.test_each_exemption_is_still_needed`: a new `id-token-write`
  exemption for `claude-security-review.yml:review`.
- `tests.test_workflow_security_coverage.NewWorkflowSecurityCoverageTests`: the coverage set gains both workflows,
  each with its own offline zizmor test.

New, in `tests/test_claude_security_review_workflow.py` (32 tests): the review workflow's shape and steps, tested the
same way as the pull request review's, and the flag's trigger paths, empty permissions, absence of any secret,
variable, OIDC token, checkout or model, and its notice. Eleven weakened copies of the two workflows each fail at
least one test (measured on 2026-10-08 against that day's bounds). The 2026-10-09 bound changes have their own tests
(an unknown tool, a start record without lists, an empty result, the named failures, the character-safe cap and the
last non-empty result), the turn bound was checked with three mutants, and the step tests no longer skip without
PyYAML.

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
recorded with the pull request review). This workflow adds `--setting-sources user`, `--add-dir`, `--effort max` and
more deny rules and runs Opus 5.5 with 12 turns and $3; it has not run, locally or hosted.
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
