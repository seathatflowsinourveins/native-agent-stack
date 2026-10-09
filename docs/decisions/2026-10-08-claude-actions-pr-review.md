# On-demand, read-only pull request review by the Claude action — 2026-10-08

`claude-pr-review.yml` lets a maintainer ask for a review of one pull request head. It is dispatched by hand from
`main` with a pull request number and the exact head commit; Claude reads the diff and the files with Read, Glob and
Grep, within 30 turns and a $5 client budget; a model-free step copies the review to the job summary. Nothing is
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
receipt does not exercise it), and runs Opus 5.5 with 30 turns and $5 (12 and $3 before R5). The runs used a
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
action step's pin, environment and other inputs, the trigger, the job condition, its grants and timeout, and every
step not named below are unchanged. What changed: R5 raised `--max-turns` from 12 to 30 and `--max-budget-usd` from 3
to 5, the prompt's "You have at most 12 turns" to 30 with them, and the numbers step's bounds to match ("Cost of one
run", below); the guard step also binds debug logging set as a repository secret or variable, as
`STEP_DEBUG_SETTING` and `RUNNER_DIAGNOSTICS_SETTING`, and refuses either (R4, 2026-10-09, below); a new step removes
the symbolic links from the pull request head right after its checkout (R5, below); the diff step expands an empty
`paths` list safely on bash before 4.4; the numbers step bounds assistant turns instead of `num_turns`, checks tools
against an allow-list (since R5 a non-string entry in the list counts as a tool outside it), fails a start record
without its lists or an empty result, names each unmet bound, adds an assistant-turns column to its summary and heads
the `num_turns` column "messages"; the publish step takes the last non-empty result and cuts it on a character
boundary, with a notice when it cuts; a new step fails a success without an execution file. Comments changed with
them, and the header now reads "no write scope beyond the OIDC token". The receipt covers the prompt and
`claude_args` on the client, not the workflow's shell steps, so the run is evidence for this head's prompt and flags
apart from the two caps, not for the caps R5 raised or for the steps that changed after it; the tests below cover
those. Its recorded numbers (12 assistant turns, about $1.87, Glob, Grep and Read, no MCP server, `success`, a
`cache_read_share` of 0.8712) are consistent with this head's bounds; the receipt records no run of the numbers step
on them.

After the run, one step reads the action's execution file and keeps only numbers and fixed names: cost, turns, the
success flag, the Claude Code version, the session's tool list, the number of MCP servers and per-model token
counts. It then fails the job unless the run succeeded, used 1 to 30 assistant turns (distinct assistant message ids; the client's `num_turns` counts transcript messages, tool results included, so a 12-request run on 2.1.295 reported 57, and it is only recorded), cost at most $5 by the client's
estimate, read the prompt cache, had no MCP server, listed its tools and MCP servers in the session start record (a
missing list fails instead of passing as empty), used no tool outside Read, Glob and Grep (an allow-list; a non-string
entry in the list is named `non-string tool entry`, R5 below) and returned result text; the step names every bound it
finds unmet. The review text, the last non-empty result, is published only when that check passed, escaped, inside
`<pre>`, capped at 60,000 bytes on a character boundary, with a line saying so when the review was longer.

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
figures below replace it. The $5 budget is a client estimate and is checked
again from the run's own numbers. Prompt caching is automatic in Claude Code, five minutes when billed to a Console
organization; one run reads its own cache, so the one-hour lifetime would cost more to write and buy nothing.
Fast mode is not used: in non-interactive runs it is a setting, it needs the organization provisioned, and Claude
Code falls back to standard speed by itself on a rate limit.

Measured on the installed client (2.1.295), billed to the second key and not through the action:
- The `LR` run was a first read of #897 with this workflow's prompt and `claude_args` at `a6d2379`. It used all 12 of
  its 12 assistant turns and cost $2.23 as the command center's caps derivation of 2026-10-09 counts it; the
  receipt's client estimate is $1.87.
- Four delta re-reads of #897 on the same client and key (LR2 to LR5, not carried in this repository) used 5, 6, 7 and
  6 assistant turns and cost $1.75, $1.35, $1.54 and $0.73.

Since R5 (2026-10-09) the caps bound a runaway, not a normal review, at about twice the measured need. `LR` stopped at
its 12-turn limit, so the need is above 12; 2.5 times that floor gives 30 turns. Twice `LR`'s $2.23 is about $4.5,
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

New, in `tests/test_claude_pr_review_workflow.py` (41 tests): the trigger, condition, permissions, checkout layout,
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
  <https://docs.github.com/en/actions/reference/security/oidc>; GitHub Security Lab, Preventing pwn requests:
  <https://securitylab.github.com/research/github-actions-preventing-pwn-requests/>.
- Anthropic: Workload identity federation,
  <https://platform.claude.com/docs/en/manage-claude/workload-identity-federation>; How Claude Code uses prompt
  caching, <https://code.claude.com/docs/en/prompt-caching>; Pricing,
  <https://platform.claude.com/docs/en/about-claude/pricing>; all read 2026-10-08.
