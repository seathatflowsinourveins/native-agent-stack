# On-demand, read-only pull request review by the Claude action — 2026-10-08

`claude-pr-review.yml` lets a maintainer ask for a review of one pull request head. It is dispatched by hand from
`main` with a pull request number and the exact head commit; Claude reads the diff and the files with Read, Glob and
Grep, within a $5 client budget and at most 30 assistant turns; a model-free step copies the review to the job
summary. Nothing is
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
- `timeout-minutes: 30` (R6, below). Grants: `contents: read`, `pull-requests: read` and `actions: read`; no
  `id-token` since the API-key ruling (2026-10-10, below).
- A guard step stops the job with exit 2 when step or runner debugging is on (debug logging set as a repository
  secret or variable included, 2026-10-09, below), when `~/.claude/settings.json` already exists on the runner (a
  dangling symlink included), or when an input is malformed.
- A binding step stops the job with exit 2 unless the pull request is open, from this repository, targets `main` and
  has exactly the requested head.
- The head is checked out as data under `pr-head/`, with main at the root, and a model-free step then removes every
  symbolic link under `pr-head/` except in `pr-head/.git` (R5, below). The diff step runs git only in the root, with
  external diff drivers and text conversion off, and refuses an empty diff or one over 250,000 bytes.
- The action step pins `ACTIONS_STEP_DEBUG: 'false'` and passes `show_full_output`, `display_report` and
  `track_progress` as `'false'`; the last two are their defaults, declared in the pinned `action.yml` (lines
  136-139 and 152-155 at `2dca132f`).
- A numbers step checks the bounds (below) and an artifact `claude-pr-review-usage-<run id>-<attempt>` keeps `usage.json`
  (numbers only) for 14 days; the review goes to the job summary only when the bounds passed (after a budget stop
  within the cost bound, the text the model wrote before it; R6 below). Nothing is posted to
  the pull request.
- The pin, v1.0.247, is hours old: the user ended the seven-day cooldown for clean releases on 2026-10-03
  (`docs/decisions/2026-10-03-currency-wave-w1.md`, "Holds and cooldown waiver"), which keeps qualification; the
  fence receipt and the local parity run below are that qualification.

## Why a manual dispatch and no pull request trigger

- **Whose workflow text holds the credential.** Since 2026-10-10 runs authenticate with the repository secret
  `ANTHROPIC_API_KEY` (below). A `pull_request` run would run the pull request's own copy of this file, so a
  pull request trigger would hand the key to text the pull request controls; only main's copy, on a dispatch or the
  schedule, reaches it. `pull_request_target` runs main's workflow text but is banned here outright
  (`dangerous-trigger` in `tests/test_workflow_policy.py`). Until 2026-10-10 the same conclusion followed from the
  federation rule, which matched only the subject of a run on `main`.
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
4. The head is checked out into `pr-head/` without credentials, and a model-free step removes every symbolic link
   in it, `pr-head/.git` aside, before the model runs (R5, below). No step runs anything from it.
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
  Read denies for the files under every `.git` directory (the action configures git authentication in the root checkout:
  `src/github/operations/git-config.ts` sets the origin URL with the job token or a credential helper), `.env`
  and key files.
- `pr-head` is not passed to `--add-dir`: it is already inside the working directory, and an added directory's
  `.claude/skills`, commands and agents are loaded.

The fence flags were run on the installed client (Claude Code 2.1.295, the version the pin installs): `--restricted`,
`--tools` and `--allowedTools` Read,Glob,Grep, `--strict-mcp-config`, `--permission-prompts none` and `--settings` with
hooks off, `claudeMdExcludes` for `pr-head` and three deny rules, on Claude Haiku 5.5 with `--max-turns 10` and a
$0.50 budget; the receipt lists them. This workflow adds `--setting-sources user`, `--add-dir`, `--effort max`, four
more deny rules and `blockReadsOutsideWorkingDirectories` (a settings key present in the 2.1.295 build; the fence
receipt does not exercise it), and runs Opus 5.5 with a $5 budget and no `--max-turns` (R6; 12 turns and $3 before
R5, 30 turns in R5). The runs used a
throwaway tree with an untrusted `pr-head` carrying its own `CLAUDE.md`, a skill and a hook, a root settings file
with a hook, a root `CLAUDE.md`, `.git/config` files and a file outside the tree. In three runs the session's tools
were exactly Glob, Grep and Read; the files at the root and under `pr-head` were read; the file outside the tree and
both `.git/config` files were denied; no hook ran; neither instruction file changed the answer; there was no shell
(`evidence/artifacts/claude-actions-fence-smoke-20261008/receipt.json`). That is one small model and one prompt: it
shows these controls held there, not that no input can defeat them. The action passes `claude_args` through its own
parser (`shell-quote`, `base-action/src/parse-sdk-options.ts`); replaying that parser on this workflow's text yields
the same flags and the same JSON.

This workflow's prompt and `claude_args` also ran once on the installed client (2.1.295), on Opus 5.5 at `max` and
billed to a second API key, not through the action. The record is the `LR` entry of
`evidence/artifacts/claude-actions-fence-smoke-20261008/local-parity-receipt.json`, which this PR carries as a
byte-identical copy of the file #892 adds (sha256 `ba498b82b6b4d2410879f23112da5d1aeaf5dabe008e7207a56e867dc48b1477`), so
the citation does not depend on which PR lands first. The run used this
workflow at commit `a6d2379506b7526ca7f528319cc4b7c65c32f897` (`workflow_commit`; the file at that commit hashes to
the entry's `workflow_sha256`) and reviewed pull request #897 (`target_pull_request`) at head
`24821c572a83091341a4924d506655004811286b` (`target_head`). The entry records 12 assistant turns of 12
(`assistant_turns_distinct_message_ids`, `max_turns`), a client cost estimate of $1.868667 of $3 (`client_cost_usd`),
the session's tools Glob, Grep and Read (`session_tools`), no MCP server (`mcp_servers`) and a `success` result
(`subtype`). Its `report_blocking_findings: 2` is the report's own first line, "Verdict: 2 blocking findings": the
model's verdict, which this record does not check. The report stays outside the repository; the entry keeps its hash,
`report_sha256` `c49bee04b8ce37feba8a812eacf2e883d8dc39b52617769ea9d73b237f857e43`. `target_pull_request`,
`target_head`, `report_blocking_findings` and `report_sha256` were added to the entry on 2026-10-09
(`amended_2026_10_09`), from the same run's harness receipt and that first line; neither is in the repository.

From that commit to this head (`git diff a6d2379506b7526ca7f528319cc4b7c65c32f897 HEAD --
.github/workflows/claude-pr-review.yml`), the prompt and `claude_args` apart from the turn and budget caps, the
action step's pin, environment and other inputs, the trigger, the job condition, its grants, and every
step not named below are unchanged. What changed: R5 raised `--max-turns` from 12 to 30 and `--max-budget-usd` from 3
to 5, the prompt's "You have at most 12 turns" to 30 with them, and the numbers step's bounds to match ("Cost of one
run", below), and R6 drops `--max-turns`, leaving the 30-turn bound to the numbers step, and raises the job's
`timeout-minutes` from 20 to 30 (R6, below); the guard step
also binds debug logging set as a repository secret or variable, as
`STEP_DEBUG_SETTING` and `RUNNER_DIAGNOSTICS_SETTING`, and refuses either (R4, 2026-10-09, below); a new step removes
the symbolic links from the pull request head right after its checkout (R5, below); the diff step expands an empty
`paths` list safely on bash before 4.4; the numbers step bounds assistant turns instead of `num_turns`, checks tools
against an allow-list (since R5 a non-string entry in the list counts as a tool outside it), fails a start record
without its lists or an empty result, names each unmet bound, adds an assistant-turns column to its summary and heads
the `num_turns` column "messages"; the publish step takes the last non-empty result and cuts it on a character
boundary, with a notice when it cuts; a new step fails a success without an execution file. Comments changed with
them, and the header now reads "no write scope beyond the OIDC token". R6 sets the cost bound at $5.50, accepts a
budget stop within it and publishes on the numbers step's outcome (R6, below). The receipt covers the prompt and
`claude_args` on the client, not the workflow's shell steps, so the run is evidence for this head's prompt and flags
apart from the two caps, not for the caps R5 raised or for the steps that changed after it; the tests below cover
those. Its recorded numbers (12 assistant turns, about $1.87, Glob, Grep and Read, no MCP server, `success`, a
`cache_read_share` of 0.8712) are consistent with this head's bounds; the receipt records no run of the numbers step
on them.

After the run, one step reads the action's execution file and keeps only numbers and fixed names: cost, turns, the
success flag, the Claude Code version, the session's tool list, the number of MCP servers and per-model token
counts. It then fails the job unless the run succeeded or stopped at its budget (R6 below), used 1 to 30 assistant
turns (distinct assistant message ids; the client's `num_turns` counts transcript messages, tool results included, so
a 12-request run on 2.1.295 reported 57, and it is only recorded), cost at most $5.50 by the client's estimate (the $5
budget times 1.10, R6 below), read the prompt cache, had no MCP server, listed its tools and MCP servers in the
session start record (a missing list fails instead of passing as empty), used no tool outside Read, Glob and Grep
(an allow-list; a non-string entry in the list is named `non-string tool entry`, R5 below) and returned result text;
the step names every bound it finds unmet. The review text, the last non-empty result (after a budget stop, the text
the model wrote before it), is published only when that check passed, escaped, inside `<pre>`, capped at 60,000
bytes on a character boundary, with a line saying so when the review was longer.

## Visibility

The repository is public, so the job summary of every run, and with it the published review, is readable by anyone.
That is by design: the review names defects in a pull request that is itself public. A review of a change whose
findings should not be public before a fix (an undisclosed vulnerability, for example) does not belong in this
workflow; the local route on the second key (`api-actions` reader jobs) keeps its report off GitHub.

A review step that reports success without an execution file fails the job in a final step, so a green run always
means the bounds were checked.

## Effort

`--effort max` in `claude_args`, set under the command center's effort mapping of 2026-10-08, which runs judgment work (designated reads, adjudication, pull request and security reviews, audits) at `max`. Every job records its level and the reason, because an unset level is a defect. The level has to be in `claude_args`: `--restricted` ignores the settings files that would otherwise carry a session's level, and on the Claude API Opus 5.5 runs at `medium` when a request leaves effort unset (bundled `claude-api` skill 2.1.295, `shared/model-migration.md`). `claude --help` (2.1.295) lists `low, medium, high, xhigh, max`. A loopback dry run of the installed 2.1.295 client with this workflow's `claude_args` sent `output_config.effort: "max"`, adaptive thinking and no `speed` field on every request. At `max`, thinking takes a larger share of the output than at the default level, so the cost below is taken from measured runs, not from a dry estimate; the client budget still bounds each run.

## Cost of one run

Withdrawn (R5, 2026-10-09): before any run, a dry estimate at Claude Opus 5.5's $4 input, $5 five-minute cache write,
$0.20 cache read and $20 output per million tokens put a first read of a diff of up to about 1,000 lines at $0.70 to
$1.30. That was below the measured cost of that shape, a first read at about $1.9 to $2.3 (below), and the measured
figures below replace it. The $5 budget is a client estimate and is checked again from the run's own numbers,
against a cost bound of $5.50 (R6 below). Prompt caching is automatic in Claude Code, five minutes when billed to a
Console organization; one run reads its own cache, so the one-hour lifetime would cost more to write and buy nothing.
Fast mode is not used: in non-interactive runs it is a setting, it needs the organization provisioned, and Claude
Code falls back to standard speed by itself on a rate limit.

Measured on the installed client (2.1.295), billed to the second key and not through the action:
- The `LR` run was a first read of #897 with this workflow's prompt and `claude_args` at `a6d2379`. It used all 12 of
  its 12 assistant turns and cost $2.23 as the command center's caps derivation of 2026-10-09 counts it; the
  receipt's client estimate is $1.87.
- Four delta re-reads of #897 on the same client and key (LR2 to LR5, not carried in this repository) used 5, 6, 7 and
  6 assistant turns and cost $1.75, $1.35, $1.54 and $0.73.

Since R5 (2026-10-09) the caps bound a runaway, not a normal review, at about twice the measured need. `LR` stopped at
its 12-turn limit, so the need is above 12; 2.5 times that floor gives 30 turns (since R6 the numbers step's bound,
with no `--max-turns`; R6 below). Twice `LR`'s $2.23 is about $4.5,
rounded up to $5. A run is expected to cost about $1.9 to $2.3 for a first read and $0.7 to $1.8 for a delta
re-read. Hosted runs bill the federated organization, not the second key, so the caps are the owner's per-run spend
limit once `CLAUDE_PR_REVIEW_ENABLED` is set.

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

New, in `tests/test_claude_pr_review_workflow.py` (44 tests): the trigger, condition, permissions, checkout layout,
step order, pin, inputs, flags and settings are asserted from the workflow file, and the guard, binding, symbolic-link,
diff, numbers and review steps are executed as written against a local stand-in for `gh` and a local git repository.
Twenty weakened copies of the workflow each fail at least one test: a missing head or repository check, a missing
first-attempt or triggering-actor condition, a 25 MB diff cap, a $30 or 120-turn check, a missing tool, MCP or
session-start check, metadata left in the model's directory, the head checked out at the root, a path check without
`..` or without a leading `-`, diff drivers left on, `--restricted` or `--permission-prompts none` removed, the
`.git` deny rule or `claudeMdExcludes` removed, and Bash added to `--tools` (measured on 2026-10-08 against that
day's bounds). The 2026-10-09 bound changes have their own tests: an unknown tool, a session start record without its
lists, an empty result, the named failure messages, the character-safe cap with its notice and the last non-empty
result; the turn bound was checked with three mutants. A test pins the usage artifact's name,
`claude-pr-review-usage-${{ github.run_id }}-${{ github.run_attempt }}`, which the upload check had read only by its
path (like the other workflow-shape tests, it needs PyYAML): three copies with the name weakened (a fixed
`claude-pr-review-usage`, the attempt dropped, `run_number` for `run_id`) each passed the 30 earlier tests and fail
this one. The step tests no longer skip without PyYAML: they read the workflow with the policy test's own loader when
PyYAML is absent.

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

## R5: symbolic links, caps from measurement, a closed flag list and boundary tests (2026-10-09)

The command center's security read of this pull request at `a1bc3bc7` (2026-10-09) and the W4 R5 brief, which the
command center limited to correctness and test quality, led to these changes.

- **Caps from measurement** (approved by the command center on 2026-10-09).
  - `--max-turns` 12 → 30 and `--max-budget-usd` 3 → 5.
  - The prompt's turn sentence now reads "You have at most 30 turns".
  - The numbers step's bounds follow: 1 to 30 assistant turns, with the message "outside 1 to 30", and a client cost
    estimate of at most $5, with the message "above 5".
  - The header comment reads "at most 30 turns and a $5 client budget".
  - The entry for this workflow in `docs/github-automation.md` reads "30 turns and a $5 client budget".
  - The derivation and the expected cost per run are under "Cost of one run" above.

- **New step, `Remove symbolic links from the pull request head`**, right after `Check out the pull request head as
  data`. Under `shell: bash` it runs `set -euo pipefail` and then this command:
  `find pr-head -path pr-head/.git -prune -o -type l -exec rm -f {} +`.
  A pull request can commit a symbolic link, for example to `/proc/self/environ` or to `../.git/config`. Claude Code
  2.1.295's `--help` says `--restricted` "confines the file tools to the working directories (--add-dir included)"
  and does not say whether a link's target is resolved, so every link under `pr-head` is removed before the model
  runs, whatever the client would do with one. `pr-head/.git`, which the checkout wrote and the deny rules cover, is
  pruned and left as it is. The step is model-free, executes nothing from the head, and its comment says why it is
  there.
- **Numbers step: a non-string tool entry is a forbidden tool** (the GPT designated read of #895, P2, applied to all
  five W4 workflows). The jq dropped non-string entries of the session's tool list before the allow-list check, so a
  list holding `{"name":"Bash"}`, `null` or `17` passed the bounds. Each non-string entry now joins `forbidden_tools`
  as `non-string tool entry`, and the step fails with "tools outside Read, Glob and Grep: non-string tool entry". The
  string allow-list check is unchanged. The step's comment names the case.
- **Tests** (the module now runs 41). The workflow-shape tests need PyYAML; there are 15 of them, and all are skipped
  without it. The new or changed pins among them are the symbolic-link step's position and exact text, the exact
  `claude_args` and `--settings`, the exact `if:` strings and the prompt's turn cap. Without PyYAML, as on the macOS
  job, the step tests still run.
  These are the new step tests: the symbolic-link step's shell on planted links, the 59,999-byte report, the three
  non-string tool entries and the caps at 30 turns and $5. The changed step tests run too: the guard with the debug-off
  values, the cut character, the unmet bounds and the turn bound.
  - new: `test_symbolic_links_are_removed_right_after_the_head_checkout` (the new step directly follows the head
    checkout, and the whole step is pinned); `test_symbolic_links_in_the_head_are_removed_and_nothing_else` (runs the
    step's shell on a tree holding links to `/proc/self/environ` and `../.git/config`, plus one in a subdirectory to
    `../..`; the links are gone, while the regular files, `pr-head/.git` with a link inside it and the root's
    `.git/config` stay; a second run on the now link-free head, the usual case, exits 0);
    `test_a_report_one_byte_under_the_cap_is_published_whole_without_a_notice` (59,999 bytes,
    published whole inside `<pre>`, no notice); and `test_an_object_in_the_tool_list_is_refused_and_named`,
    `test_a_null_in_the_tool_list_is_refused_and_named` and `test_a_number_in_the_tool_list_is_refused_and_named`
    (each fails the step, names `non-string tool entry` and keeps it in `forbidden_tools`);
    `test_the_prompt_states_the_turn_cap_the_flags_set` (the prompt's "You have at most N turns" carries the
    `--max-turns` value); and `test_the_caps_hold_at_30_turns_and_5_usd_and_fail_just_above_or_with_no_turn`. That
    last test passes a run of 30 assistant turns at $5. It fails runs of 31 turns, of $5.01 and of no turn, each with
    its message.
  - changed:
    - `test_claude_has_three_read_tools_and_fixed_bounds` asserts the whole `claude_args` list as the action's parser
      receives it: `${{ runner.temp }}` rendered as a stand-in path, `/runner-temp`, each line split as a shell would
      split it, and the `--settings` value compared as the JSON it parses to, with `--max-turns 30` and
      `--max-budget-usd 5`. A widened or second `--add-dir`, or a repeated turn or budget flag, now fails it.
    - `test_an_unmet_bound_fails_after_the_numbers_were_kept` uses $5.01 and 31 turns for its budget and turn cases.
    - `test_the_step_names_every_unmet_bound` uses 31 turns and $5.50, and expects "31 assistant turns, outside 1 to
      30" and "above 5".
    - `test_the_turn_bound_counts_assistant_turns_not_transcript_messages` fails a run of 31 assistant turns whose
      `num_turns` is 30.
    - `test_settings_turn_hooks_off_exclude_the_heads_instruction_files_and_confine_reads` asserts the whole
      `--settings` JSON, so a dropped deny rule, an allow list or `permissions.additionalDirectories` fails it.
    - `test_the_review_is_published_only_after_the_bounds_check_passed_and_only_numbers_are_uploaded` asserts the
      publish and numbers steps' exact `if:` strings instead of substrings.
    - `test_well_formed_inputs_pass_the_guard` and
      `test_each_debug_signal_and_a_pre_existing_settings_file_stop_the_job` run the guard with the values a run
      without debug logging binds (`STEP_DEBUG_SETTING` and `RUNNER_DIAGNOSTICS_SETTING` `false`,
      `RUNNER_DEBUG_SIGNAL` empty), so a guard that refuses those values fails.
    - `test_the_cap_never_splits_a_character_and_a_short_report_has_no_notice` checks three things: the 59,999 bytes
      before the cut character are published whole, the notice gives 80,001 bytes, and the short report is published
      whole.
    - `test_steps_run_in_the_order_the_binding_depends_on` includes the new step.
    - `test_no_step_executes_anything_from_the_pull_request_head` skips the new step by name, because its text names
      `pr-head/.git`; the first new test pins that text whole.
  - The module constants `HEAD_CHECKOUT`, `STRIP`, `DEBUG_OFF`, `RUNNER_TEMP_STAND_IN` and `SETTINGS`, the helper
    `claude_args()` and the assertion `assert_refused_as_a_non_string_tool_entry` are new.
- **Mutants.** Each of 28 weakened copies of the workflow fails at least one test of the module, measured with
  PyYAML 6.0.3 present, as the hosted validate job has it. The script sits outside the repository and ran on
  2026-10-09. Without PyYAML, 15 of the 28 fail a test. The other 13 are caught only by the skipped shape tests:
  - the symbolic-link step skipped or moved;
  - the six `claude_args` and `--settings` copies;
  - the two `if:` copies;
  - the caps left at 12 turns or $3;
  - the prompt still at 12 turns.

  The copies:
  - the new step removed, skipped with `if: ${{ false }}`, run without `-type l` or without the `.git` prune, or
    moved after the diff step;
  - a second `--add-dir /`, `--add-dir` widened to `${{ runner.temp }}`, a repeated `--max-turns 120` or
    `--max-budget-usd 30`, `permissions.additionalDirectories` added, or the `Read(./**/.env)` rule dropped;
  - the publish step's `if:` as `success() || ...`, or the numbers step's with `success()` added;
  - a guard that refuses `STEP_DEBUG_SETTING=false` or an empty `RUNNER_DEBUG_SIGNAL`;
  - a 59,998-byte cap, `iconv` to ASCII, or the notice from 59,999 bytes;
  - the numbers step's `forbidden_tools` as at `a1bc3bc7`, or its non-string filter moved onto the listed tools;
  - the turn bound back at 12 or loosened to 31, the cost bound back at 3 or loosened to 5.5, or the lower turn bound
    dropped;
  - `--max-turns` left at 12, `--max-budget-usd` left at 3, or the prompt still saying 12 turns.

  The first twenty were also run, before the caps change, against the module as it was at `a1bc3bc7`. That module
  caught 3 of them: the widened `--add-dir`, the 59,998-byte cap and the 59,999-byte notice.
- **Record.**
  - The by-name list's guard entry now names debug logging set as a repository secret or variable.
  - The by-name list, step 4 under "How the pull request head is handled" and the paragraph on what changed since
    `a6d2379` name the new step.
  - That paragraph now names the R4 guard change, which it had left out, and the summary's `messages` heading.
  - The paragraph on the numbers step names the non-string entry.
  - The caps read 30 turns and $5 in the opening paragraph, the fence paragraph, the paragraph on what changed since
    `a6d2379` and the paragraph on the numbers step. "Cost of one run" gains the measured runs, the derivation and the
    expected cost per run.
  - The test count reads 41, and the executed steps include the symbolic-link step.
  - "Read denies for every `.git` directory" now reads "for the files under every `.git` directory", because
    `Read(./.git/**)` matches what is under `.git`, not the directory itself (the security read's G2).
  - The action bullet under "SOTA sources" adds `src/github/operations/git-config.ts` and `src/modes/agent/index.ts`,
    which the sentence on the `origin` URL below cites.
  - "Cost of one run" withdraws the dry estimate of $0.70 to $1.30, which was below the measured cost of a first read.
    The "Effort" section says the cost comes from measured runs; it no longer calls the estimate a floor.

Security hardening from the 2026-10-09 read (debug-value widening, tool-list shape, extra deny rules, token-source and guard-step assertions) is filed as follow-ups before any enabling variable is set.
Of the tool-list shape, R5 makes only the non-string entry change above. Requiring a non-empty list and checking the
`tool_use` names stay in that follow-up.

In agent mode the action rewrites the checkout's `origin` URL with the job token (`src/github/operations/git-config.ts:129-134`, called from `src/modes/agent/index.ts:52-61` at `2dca132f`), so `persist-credentials: false` does not keep the token out of `.git/config`; the deny rules `Read(./.git/**)` and `Read(./**/.git/**)` are what keep the model from reading it, as two 2026-10-09 probes on the installed 2.1.295 measured.

Not run in R5: a fence smoke with a planted symbolic link. That needs a model run, and this round makes none. The
tests run the new step's shell, not the client.

## R6: the cost bound, no client turn limit and an exact settings pin (2026-10-09)

R6 bundles three items:

- Item 1: the cost bound. It comes from the command center's read of #895 at R5 (P2).
- Item 3: dropping `--max-turns`. This is the command center's decision, option a.
- Item 4: a `--settings` pin that tells `true` from `1`. It comes from the J8 micro read of this pull request at R5
  (N1).

Item 1 is the rule for all five W4 workflows, with an exception #896 may state; item 3 applies to all but #909, which
keeps its `--max-turns 12`; item 4 applies to all five.

### Item 1: the cost bound is the budget times the measured overrun factor

The paragraph below is the shared one, word for word except its last sentence:

The client stops a run only after its cost has crossed `--max-budget-usd`, so a cost bound equal to the budget fails a normal budget stop. Four measured J8 runs on a $5 budget ended above it: $5.46 (9.2% over, the largest overrun), $5.33, $5.16 and $5.0007, on #895, trading #11, #902 and #894. The cost bound is therefore the budget times 1.10, a factor that rounds up the largest measured overrun; the factor is derived again after this workflow's first three hosted runs. A run at or under the bound passes the cost check. A budget stop (result subtype `error_max_budget_usd`) at or under the bound publishes what the run produced, and the summary names the stop. A run above the bound fails closed and names the overrun. This workflow's budget is $5, so its bound is $5.50.

- **Numbers step** (`Keep the run's numbers and check the bounds`):
  - it gains `id: numbers` and holds the budget and the bound as `budget=5 cost_bound=5.5`;
  - above the bound it fails with "client cost estimate <x> USD, above the 5.5 USD bound (the 5 USD budget times its
    measured overrun factor 1.10)", in place of "above 5";
  - it accepts a budget stop as well as a success; any other ending fails with "the run did not end in success or in
    a budget stop";
  - a budget stop carries no result text, so the text the model wrote before the stop (its `text` blocks, joined by
    blank lines) counts as the result text; a budget stop with no text still fails "no result text";
  - `usage.json` gains the field `budget_stop`;
  - the summary gains two lines, "Budget stop: the client stopped the run at its 5 USD budget (error_max_budget_usd),
    before a final report." and "Over the cost bound: the client cost estimate is <x> USD, above 5.5 USD (the 5 USD
    budget times its measured overrun factor 1.10).";
  - its comment says all of this.
- **Publish step** (`Publish the review to the job summary`):
  - its `if:` changes from `${{ success() && steps.claude_review.outputs.execution_file != '' }}` to
    `${{ !cancelled() && steps.numbers.outcome == 'success' }}`, as #892 now has. The action fails its own step on
    any result other than an error-free success but keeps its `execution_file` output
    (`base-action/src/run-claude-sdk.ts:254-298` and `src/entrypoints/run.ts:316-324`, read at v1.0.246, `38c80c1`;
    #892's builder read the same at the pin). A step gated on `success()` therefore never ran after a budget stop.
  - After a budget stop it publishes the text the numbers step counted, followed by "Budget stop: the client stopped
    the run at its budget (error_max_budget_usd) before a final report; shown is the text the model wrote until
    then."
  - This line and the text fallback are this workflow's own. A single-agent run stopped at its budget has written no
    report, while #909 publishes its agents' handbacks.
  - Its comment says all of this.

### Item 3: no `--max-turns` in `claude_args`

- `claude_args` no longer passes `--max-turns 30`.
- Why, from a code reading plus a local measurement, not a hosted run:
  - The pinned action, anthropics/claude-code-action v1.0.247 at `2dca132f`, throws "Claude reported a successful
    result after N turns, exceeding the configured maximum" when a successful result's `num_turns` is above that
    maximum (`base-action/src/run-claude-sdk.ts:241-250`). `base-action/src/parse-sdk-options.ts:207-208` and
    `318-322` take the maximum from `claude_args`.
  - The check came from commit `6ef6450f`, "fix: enforce max turns from claude args (#1607)", 2026-08-07.
  - R6 read these lines at v1.0.246 (`38c80c1`); the command center's compare shows the file unchanged at
    `2dca132f`.
  - On Claude Code 2.1.295, `num_turns` counts transcript messages, tool results included. The `LR` run made 12
    requests under `--max-turns 12` and reported 57.
  - So a normal successful run would fail the action step.
- Upstream has no fix as of 2026-10-09: the command center found upstream main identical in that file.
- What stays:
  - The runaway bounds are the budget, checked against the $5.50 bound, and the numbers step's own bound of 1 to 30
    assistant turns (distinct message ids), which fails closed.
  - The prompt keeps "You have at most 30 turns".
  - #909 keeps its `--max-turns 12`.
- The job's `timeout-minutes` rises from 20 to 30, the command center's decision of 2026-10-09 under its standing
  rule to raise any cap that would truncate a normal run (it was left open by the J8 micro read of R5, N2):
  - With no `--max-turns`, the numbers step's bound of 30 assistant turns is the turn limit, and the job timeout is
    a third limit, the one that leaves no record. A timeout cancels the review step before it writes
    `execution_file`, so the numbers step is skipped and nothing is published or uploaded.
  - The one measured run of this shape, `LR` (Opus 5.5 at max effort), took 512,670 ms for 12 assistant turns, about
    43 seconds a turn. At that pace 30 turns take 1,281,675 ms, about 21.4 minutes of client time, before checkout
    and setup, so a 20-minute timeout would cancel a run inside the approved bounds.
  - #892 already uses 30 minutes. `test_the_job_timeout_leaves_room_for_the_30_turn_bound` pins it.
- Comments:
  - The header comment now reads "a $5 client budget; a run of more than 30 assistant turns fails its bounds check".
  - The review step's comment says why there is no `--max-turns`.
  - The publish step's comment no longer names the `num_turns` check, which can no longer fire.

### Upstream issue (draft, not filed; the owner decides)

> Title: success with num_turns > maxTurns fails the step, but num_turns counts messages, not turns.
> base-action/src/run-claude-sdk.ts:241-250 (v1.0.247, 2dca132f) compares `resultMessage.num_turns` with
> `sdkOptions.maxTurns`. On Claude Code 2.1.295 the result's num_turns counts transcript messages (tool results
> included): a headless run of 12 requests under `--max-turns 12` reported num_turns 57. A normal successful run
> under `--max-turns N` therefore throws "exceeding the configured maximum". Repro: any `claude_args: --max-turns 5`
> run that makes a few tool calls and succeeds.

### Item 4: the `--settings` pins tell `true` from `1`

- The R5 pins were looser than R5's record said:
  - They compared the parsed `--settings` JSON with Python's `==`, and in Python `1 == True`.
  - A copy with `"disableAllHooks":1` or `"blockReadsOutsideWorkingDirectories":1` passed every test of the R5
    module: both copies were measured surviving the module at `d1bcb6cb`.
  - The tests at `a1bc3bc7` refused both, with `assertIs(..., True)`.
- The fix:
  - Both pins now compare canonical JSON text, `json.dumps(value, sort_keys=True, separators=(",", ":"))`, through
    a new helper, `canonical()`.
  - They are `test_settings_turn_hooks_off_exclude_the_heads_instruction_files_and_confine_reads` and the
    `--settings` element of `test_claude_has_three_read_tools_and_fixed_bounds`.
  - No other exact pin in the module holds a boolean that `==` could take for a number.
- Two new mutants put `1` in place of `true`, one in each key; each now fails both pins.
- This workflow's settings have no `autoMemoryEnabled`, so the brief's mutant for that key does not apply.

### Tests, mutants and the record

- **Tests** (the module now runs 44):
  - new: `test_a_budget_stop_at_or_under_the_bound_publishes_what_the_run_wrote_and_names_the_stop` (budget stops at
    $5.30 and $5.50 pass the numbers step, which records `budget_stop` and counts exactly the text the publish step
    then shows inside `<pre>`; both stop lines appear, and a success shows none) and
    `test_a_budget_stop_above_the_bound_or_without_text_fails` (a budget stop at $5.51 fails, with the overrun named
    and both summary lines; one with no text fails "no result text"; a turn-limit stop fails "did not end in success
    or in a budget stop").
  - changed: `test_the_caps_hold_at_30_turns_and_5_usd_and_fail_just_above_or_with_no_turn` is renamed
    `test_the_bounds_hold_at_30_turns_and_5_50_usd_and_fail_just_above_or_with_no_turn`: a run at $5.50 passes, and
    one at $5.51 fails with the overrun named in the failure and in the summary.
    `test_an_unmet_bound_fails_after_the_numbers_were_kept` uses $5.51 ("over the cost bound");
    `test_the_step_names_every_unmet_bound` uses $6 and expects "above the 5.5 USD bound";
    `test_a_bounded_cached_read_only_run_is_accepted_and_only_numbers_and_fixed_names_are_kept` expects
    `budget_stop` false and no stop or overrun line;
    `test_the_review_is_published_only_after_the_bounds_check_passed_and_only_numbers_are_uploaded` pins the publish
    step's new `if:` and the numbers step's `id`.
    `test_claude_has_three_read_tools_and_fixed_bounds` no longer expects `--max-turns 30` (item 3).
    `test_the_prompt_states_the_turn_cap_the_flags_set` is renamed
    `test_the_prompt_states_the_turn_bound_the_numbers_step_checks`: the prompt's "You have at most N turns" carries
    the numbers step's assistant-turn bound, and `claude_args` holds no `--max-turns` (item 3).
    The two `--settings` pins compare canonical JSON (item 4).
  - new: `test_the_job_timeout_leaves_room_for_the_30_turn_bound` pins `timeout-minutes` to the integer 30 (item 3).
  - The constant `WRITTEN_MARKER`, the fixture `budget_stop()` and the helper `canonical()` are new.
- **Mutants.** 39 weakened copies, measured with PyYAML 6.0.3 present, as the hosted validate job has it; each fails
  at least one test. Without PyYAML, 22 do; the other 17 are the shape tests' pins (follow-up F-16). They now include
  both publish-condition copies and both `1`-for-`true` copies. Against R5's set:
  - two copies are re-anchored: publication gated on `success()` again, and the numbers step's `if:` under its new
    `id`;
  - the cost-bound copies, back at 3 and loosened to 5.5, are replaced by the factor dropped (the bound back at $5)
    and the factor widened to 1.5 ($7.50);
  - "`--max-turns` left at 12" becomes `--max-turns 30` put back (item 3);
  - new copies for item 1:
    - a budget stop not accepted, or exempt from the cost bound;
    - the budget-stop text missing from the numbers step, or from the publish step;
    - the budget-stop line missing from the numbers summary, or from the published review;
    - no overrun line;
    - the publish `if:` without the numbers step's outcome.
  - new copies for item 4: `"disableAllHooks":1` and `"blockReadsOutsideWorkingDirectories":1`. Both survived the R5
    module.
  - a new copy for the timeout: `timeout-minutes` back at 20.
- **Changed test expectations the R5 description did not declare.** These come from section 3 of the J8 micro read of
  R5. This record's R5 section declares U1 to U6; U7 is the change item 4 corrects.
  - U1: `test_no_step_executes_anything_from_the_pull_request_head` skips its `pr-head` token checks for the
    symbolic-link step, by name: an exemption in a security test. Its `working-directory` check moved above the
    skip, so it still applies to that step.
  - U2: `test_steps_run_in_the_order_the_binding_depends_on` expects the symbolic-link step between the head
    checkout and the diff step.
  - U3: `test_an_unmet_bound_fails_after_the_numbers_were_kept` moved its budget case from $3.01 to $5.01 and its
    turn case from 13 to 31. R6 moves the budget case again, to $5.51.
  - U4: `test_the_step_names_every_unmet_bound` moved from 13 turns and $3.50 to 31 turns and $5.50, expecting
    "outside 1 to 30" and "above 5". R6 uses $6 and expects "above the 5.5 USD bound".
  - U5: `test_the_turn_bound_counts_assistant_turns_not_transcript_messages` moved its failing case from 13 turns
    with `num_turns` 13 to 31 turns with `num_turns` 30, so `num_turns` alone is now inside the bound.
  - U6: `test_the_cap_never_splits_a_character_and_a_short_report_has_no_notice` asserts more than the declared
    59,999-byte prefix: also the "The report is 80001 bytes;" notice, exit 0 for the short report, and that report's
    exact `<pre>` block.
  - U7: the two `assertIs(..., True)` checks on `disableAllHooks` and `blockReadsOutsideWorkingDirectories` were
    replaced by the whole-JSON `==` comparison, which accepted `1` for `true`. Item 4 corrects it.
- **Record.**
  - The by-name list, the paragraph on what changed since `a6d2379`, the paragraph on the numbers step and "Cost of
    one run" name the $5.50 bound, the budget stop and the publish condition.
  - The opening paragraph, the fence paragraph, the paragraph on what changed since `a6d2379`, "Cost of one run" and
    "What would overturn it" say the 30-turn bound is now the numbers step's, with no `--max-turns`.
  - The test count reads 44.
  - The by-name list and the paragraph on what changed since `a6d2379` name the 30-minute timeout.
  - The entry for this workflow in `docs/github-automation.md` now reads "a $5 client budget and at most 30
    assistant turns" in place of "30 turns and a $5 client budget".

## Every pull request (2026-10-09)

The owner requires the cross-family review gate to run through the vendor path on every pull request: the Claude
side is this workflow, pinned, with federation and Opus 5.5. The command center ruled the trigger on 2026-10-09
(about 15:3xZ). The review stays advisory until cc-native-practice's blind paired comparison decides. Its runs on real
pull requests give that comparison its vendor arm, and the command center reads the summary before it merges a
non-draft head.

**Trigger: a 15-minute schedule, beside the dispatch.** Two other designs were checked and rejected:
- **A `pull_request` trigger** has the derived immutable form `repo:OWNER@OWNER-ID/REPO@REPO-ID:pull_request`.
  The native repository OIDC REST metadata supplies `sub_claim_prefix`, and the event suffix comes from
  GitHub's "Filtering for pull_request events", [retained OIDC snapshot:332](../../evidence/artifacts/claude-federation-docs-20261010/docs.github.com_actions_reference_security_oidc.txt#L332)
  (revision `sha256:35d79cb17e94732a467c63e59c3a01d18029b47f4b5f9cbf15d92037164b03cd`, retrieved 2026-10-10, 37248 bytes;
  immutable syntax separately at 352–359). Combining that prefix and documented suffix is a derivation, not an example
  quoted from the immutable-subject section. A main-only federation rule does not accept it. It would also run the
  pull request's own copy of the workflow file with the token.
- **`workflow_run`** runs main's copy with main's subject (GitHub's "Events that trigger workflows": GITHUB_REF is
  the default branch). claude-code-action supports it as an automation event at the pin
  (`src/github/context.ts:67, 243`). But zizmor's `dangerous-triggers` audit flags it, and this repository runs
  zizmor with `--no-config --no-ignores`, so no file can suppress that, and `tests/test_workflow_policy.py` bans the
  trigger outright. Weakening either gate was rejected.
- **A `schedule` run** executes main's file with main's subject, the pattern `harness-audit.yml` already uses on the
  same federation rule. It needs no federation change and no exemption, and zizmor 1.30.1 reports nothing at either
  persona.

**How a head is chosen.** A new job, `resolve`, holds no token (`pull-requests: read`, `actions: read`), checks
nothing out and reads no secret.
- **On a dispatch:** it checks the two inputs' format and passes them through. Drafts may be dispatched.
- **On a tick, it lists the open pull requests through the API and keeps each one that:**
  - is not a draft;
  - comes from this repository (a fork never qualifies);
  - targets main;
  - has no completed review of its current head yet, and a new push is a new head.
- **What counts as a completed review.** A review leaves the completion marker `claude-pr-review-done-pr<N>-<sha>`
  only when its bounds check passed and its review was published. A failed or unpublished review leaves only its
  usage record, and the head is tried again on a later tick.
  - A marker counts only when the run that uploaded it is looked up through the API and is this workflow's own
    (`workflow_id`), a `schedule` or `workflow_dispatch` run, on `main`, in this repository. An artifact's name and its
    branch name can come from anywhere, including a fork's branch named `main`.
  - The marker is kept 90 days. A head still open and unchanged after that is reviewed again.
- **Limits:** at most 2 heads per tick, oldest pull request first. None once today's reviews reach the daily ceiling:
  the repository variable `CLAUDE_PR_REVIEW_DAILY_USD`, default 55, counted at the 5.50 USD cost bound per review
  from this workflow's schedule and dispatch runs on main since 00:00 UTC. A tick at the ceiling skips and says so
  in its summary.
- **Every list is read to its last page:** the open pull requests, today's runs, each run's jobs and each marker
  name's artifacts (`gh api --paginate`).
- **Failure:** an API failure fails the job, and nothing is reviewed.

**The review.** The review job runs once per chosen head as a matrix (`max-parallel: 2`), with a concurrency group
per pull request and head.
- **The recheck.** Once it holds its head's group, a scheduled review first looks for a trusted completion marker
  again (`actions: read`). A dispatch of the same head may have completed while it waited, and the scheduled review
  then skips every later step. A dispatch always reviews.
- Its binding step reads the pull request again with its own read before any token step, and fails closed. The pull
  request must be open, from this repository, targeting main and at the chosen commit, and on a scheduled review not
  a draft.
- Everything else is as above:
  - the head is data under `pr-head/` and nothing from it executes;
  - Read, Glob and Grep only;
  - the summary only, nothing posted;
  - the `2dca132f` pin;
  - the 5 USD budget with its 5.50 USD bound;
  - no debug or full output.
- **Switches:** the schedule runs only while `CLAUDE_PR_REVIEW_ENABLED` and `CLAUDE_PR_REVIEW_EVERY_PR` are both
  `true`, and only on a run's first attempt.
- **Cost:** a tick with nothing to review costs runner time only. Each review's spend is in its usage artifact; the
  api-actions lane enters it in its ledger.

**Tests** (tests/test_claude_pr_review_workflow.py: 69 tests; 26 cover the resolve and recheck steps). They run the
resolve step against a stand-in `gh`:
- a fork head, a draft, another base and a closed pull request are never chosen;
- a head already reviewed is skipped, and a new head of the same pull request is chosen;
- at most two heads per tick;
- at the daily ceiling, nothing is chosen and the tick reports it;
- an API failure on any of the three endpoints fails the job;
- a malformed dispatch or ceiling is refused or skipped;
- the binding refuses a draft on a scheduled review and accepts one on a dispatch.

The shape tests pin the triggers, the resolve job's read-only scopes, the matrix and group, and the artifact name. The
id-token exemption in tests/test_workflow_policy.py now names the schedule.

**agentic-actions-auditor (Trail of Bits' skill, run on this change, 2026-10-09).** The workflow has one AI action
instance (claude-code-action at `2dca132f`, job `review`).
- **Vectors D, F, G, H and I: no finding.**
  - No `pull_request_target`.
  - Read, Glob and Grep only; no shell tool.
  - No step evaluates the model's output: it is parsed with jq and published HTML-escaped inside `<pre>`.
  - `--restricted`, no dangerous sandbox, and no `allowed_non_write_users`.
- **Vector B (expressions in the prompt): Info.** The prompt and the job name interpolate `matrix.pr_number` and
  `matrix.head_sha`, which come only from the resolve job's output. That output is the API's numeric `.number` and a
  `.head.sha` that must match `^[0-9a-f]{40}$` (a dispatch passes the same two format checks), so no pull request
  text (title, body, branch name) can reach the prompt, a shell or a job name.
- **Vector A (env intermediaries): no finding.** The only event-derived env values are those two checked fields, the
  dispatch inputs (format-checked) and `paths` (pattern-checked by the guard). The prompt reads no environment
  variable.
- **Vectors C and E (content the agent reads): Low, by design.** The agent reads the diff and the files of the pull
  request head, which a collaborator writes. The prompt calls them material, never instructions, and the agent can
  only read, with reads confined to the workspace and the diff directory. Symbolic links are removed, and the output
  goes only to the job summary. An injection can at most skew the advisory review text.
- **Who can cause a run.** Anyone who can push a branch to this repository and open a non-draft pull request
  against main, which the daily ceiling bounds. A fork never qualifies (`head.repo.full_name` is checked in both
  jobs).
- **Found by the audit before the PR (Medium, gate evasion), and fixed only by the GPT read's round.** The first
  version counted any artifact with the review's name, and any run of `claude-pr-review.yml`, toward the dedupe and
  the ceiling. The pre-PR fix filtered artifacts on `head_branch == "main"`. That filter was not enough: a fork's
  branch can be named `main` (GPT read of a22c483d, P2 1). The uploading run is now looked up and must be this
  workflow's own schedule or dispatch run on main in this repository.

**GPT read of a22c483d (CHANGES_REQUESTED, four P2s), fixed in one commit:**
1. **A fork's branch named `main` passed the marker filter.** Fixed by the run lookup above. Test:
   `test_a_marker_from_anything_but_this_workflows_schedule_or_dispatch_on_main_here_is_ignored` (a fork's branch
   named main, a pull_request run, another workflow, another branch).
2. **No pagination.** Every list now pages to its end. Tests: 101 eligible pull requests with the oldest 100
   completed choose the 101st; 100 newer runs without reviews ahead of an older run with ten still reach the ceiling.
   The stand-in `gh` returns pages of 100.
3. **A failed review's usage record was the dedupe marker.** Fixed with the separate completion marker, gated on the
   bounds check and the publish step (`id: publish`). Tests: the gate, and a head with only a usage record is
   chosen again.
4. **A scheduled review that waited behind a dispatch of the same head reviewed it again.** Fixed by the recheck.
   Tests: a head completed meanwhile is skipped, one not completed goes ahead, a dispatch always reviews, and an API
   failure fails the step.

The two copies of the marker check (resolve and recheck) are held identical by a test. An API failure inside the
check stops the step: the result is assigned first, so the shell's errexit applies. Seven weakened copies each fail
the module:
- any uploading run trusted;
- the old branch-name filter;
- pull requests not paginated;
- runs not paginated;
- the marker written whatever the outcome;
- no recheck;
- the check's result compared inside `[ ]` (which swallowed an API failure in the first draft).

## Authentication by API key (the owner's ruling, 2026-10-10)

On 2026-10-10 at about 13:44Z the owner ruled, relayed by the command center, that CI Claude review authenticates
with an Anthropic API key rather than federation, and that the keys are to be used fully as the repository's
LLM-native practice; federation stays unconfigured. (Paraphrased.) The trigger: the acceptance dispatch of 13:36Z (run
38056354892) was refused like the runs of 2026-10-08, most likely because the federation rule's subject does not
match this repository's immutable OIDC subject.

- **What changed.** `claude-pr-review.yml`, `claude-pr-toolkit-review.yml` and `harness-audit.yml` pass
  `anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}` and no federation input, and none of their jobs holds
  `id-token`. The action requests a GitHub OIDC token for two things only: federation, when its inputs are set
  (`base-action/src/workload-identity.ts:43-47` at `2dca132f`), and its GitHub App token, when no `github_token` is
  given (`src/github/token.ts:160-168`). All three workflows pass `github_token`, so neither applies. The Claude Code
  GitHub Actions page says the same from the other side: `id-token: write` is required for the action's default
  GitHub App authentication, and for the federation exchange.
- **The secret, in an environment.** `ANTHROPIC_API_KEY` holds the inventory entry `anthropic-api-3`, the cold spare,
  so CI spend is separable from the local worker's api-4. It is an environment secret of `claude-review`, whose
  deployment branch policy allows `main` only, and each job that uses the key declares `environment: claude-review`.
  The owner wanted the key kept away from this public repository: a repository secret reaches a workflow pushed on any
  branch and dispatched from there, while an environment secret reaches only a job deploying from an allowed branch.
  The command center set it on the owner's explicit OK, through `credential_run.py anthropic-api-3`, with the value on
  `gh secret set`'s standard input only: first as a repository secret (2026-10-10T13:49:43Z), then in the environment
  (2026-10-10T13:55:05Z, `gh secret list --env claude-review`), and the repository copy was deleted (read back by the
  coordinator at 14:11Z: the environment has the branch policy `main` and the secret; the repository has none of that
  name).
- **What did not change.** Dispatch and schedule on `main` only, never a pull request run; the owner and first-attempt
  guards; the bounds step; the daily ceiling; the read-only tool set; the job summary as the only output.
- **Policy.** The federation exemption from `id-token-write` (`docs/decisions/2026-10-04-ci-least-privilege.md`) and
  the three `id-token: write` write grants are removed from `tests/test_workflow_policy.py`. `tests.test_workflow_hardening.
  ClaudeApiKeyAuthTests` requires the secret once in each of the three workflows, the key-using job in the
  `claude-review` environment and no other job in one, no federation input, no `id-token`, no pull request trigger,
  and the secret in no other workflow; it fails on main before this change and passes after it. zizmor 1.30.1 reports
  nothing in the regular, pedantic and auditor personas (on main the auditor persona reports six `secrets-outside-env`
  findings in these three files).
- **Acceptance.** After this lands, the command center dispatches one review and checks for a successful review,
  `total_cost_usd` above zero and a non-empty `modelUsage`.

## Alternatives considered

- **Workload identity federation** (this record's choice until 2026-10-10). No stored key, but the rule refused every
  run so far; the owner ruled for the API key.
- **Review every pull request on `pull_request` or `workflow_run`** (the action's `docs/solutions.md` example).
  The first would run the pull request's own workflow text with the key; the second is refused by this repository's zizmor gate and
  policy. "Every pull request (2026-10-09)" reaches every head through the schedule instead.
- **`anthropics/claude-code-security-review`.** Covered by the security-review record; not used.
- **The upstream `/code-review` plugin** (`plugin_marketplaces: https://github.com/anthropics/claude-code.git`).
  The marketplace fetch is unpinned; this repository pins every action by commit.
- **Posting the review as a pull request comment.** It needs `pull-requests: write` and makes a workflow a reviewer;
  both are refused by existing tests. The job summary needs no scope.
- **Comment-triggered runs** (`@claude` in a pull request comment). Anyone can comment; the dispatch form has no
  such surface.

## What would overturn it

- A first activated run stops at its budget with the review unfinished, or fails the 30-assistant-turn bound: raise the
  one bound that stopped it, with that run's numbers.
- The numbers step reports a forbidden tool or an MCP server: stop using the workflow and read the action's change.
- GitHub or Anthropic ship a way for a pull request run to authenticate without exposing the token to the pull
  request's workflow text: reconsider the schedule in favour of an event trigger.
- The scheduled reviews reach the daily ceiling on a normal day, or a head waits more than a few ticks: raise the
  ceiling or the per-tick count with that day's numbers.
- cc-native-practice's paired comparison finds the vendor arm worse than the current reads: keep it advisory or
  remove the schedule.

## Evidence class

`native_proven` for the flag set on the installed client (the receipt above; not through the action and not on a
GitHub runner). `local_static_analysis`: actionlint 1.17.0 and zizmor 1.30.1 (offline, regular and pedantic), no
findings. `local_integration`: the unit tests above with PyYAML 6.0.3 on Python 3.12, and the local parity run above
(the installed client in place of the action; the `LR` entry of `local-parity-receipt.json`, carried in this PR). `source_review`:
the action and client sources below. No hosted run of this workflow is part of this record.

## SOTA sources

- anthropics/claude-code-action at `2dca132ff0e0c4094ce6048b422c6915a071210b` (v1.0.247):
  `docs/security.md` (untrusted refs; which files come from the base branch), `docs/setup.md` (federation inputs;
  "a static credential takes precedence and federation will not be used"), `action.yml`,
  `base-action/src/parse-sdk-options.ts` (argument parsing, default setting sources, debug forcing full output),
  `base-action/src/execution-file.ts`, `src/github/operations/git-config.ts` and `src/modes/agent/index.ts` (agent
  mode writes the job token into the checkout's `origin` URL);
  <https://github.com/anthropics/claude-code-action/tree/2dca132ff0e0c4094ce6048b422c6915a071210b>.
- Claude Code 2.1.295 `--help` for `--restricted`, `--permission-prompts`, `--tools`, `--settings`,
  `--strict-mcp-config`, `--max-budget-usd`.
- GitHub, OpenID Connect reference, "Filtering for pull_request events" and "Filtering for a specific branch":
  <https://docs.github.com/en/actions/reference/security/oidc> (read again 2026-10-09T14:43Z); Events that trigger
  workflows, `schedule` and `workflow_run`:
  <https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows> (read
  2026-10-09T14:43Z); zizmor 1.30.1 `dangerous-triggers`, run with `--no-config --no-ignores` (this repository's
  pin); GitHub Security Lab, Preventing pwn requests:
  <https://securitylab.github.com/research/github-actions-preventing-pwn-requests/>.
- Claude Code GitHub Actions, <https://docs.claude.com/en/docs/claude-code/github-actions> (read 2026-10-10T13:48Z):
  the `anthropic_api_key` input and the `${{ secrets.ANTHROPIC_API_KEY }}` setup; workload identity federation as the
  alternative to a stored key; `id-token: write` required for the default GitHub App authentication and for the
  federation exchange. With `2dca132f`'s `src/github/token.ts:160-168` and `base-action/src/workload-identity.ts:43-47`.
- Anthropic: Workload identity federation,
  <https://platform.claude.com/docs/en/manage-claude/workload-identity-federation>; How Claude Code uses prompt
  caching, <https://code.claude.com/docs/en/prompt-caching>; Pricing,
  <https://platform.claude.com/docs/en/about-claude/pricing>; all read 2026-10-08.
