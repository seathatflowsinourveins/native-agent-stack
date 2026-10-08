# Bounded harness audit on the current Claude action pin — 2026-10-08

`harness-audit.yml` moves from `anthropics/claude-code-action` v1.0.245 to v1.0.247 and becomes a bounded,
read-only job: Claude gets Read, Glob and Grep, at most 20 turns and a $3 client budget; the job holds
`contents: read` and `id-token: write` and nothing else; a model-free step copies the report to the job summary and
keeps the run's token and cost numbers. The job runs only while the repository variable
`CLAUDE_HARNESS_AUDIT_ENABLED` is `true`. Nothing in this change starts a run, sets a variable or touches the
federation rule.

## What was wrong with the job as landed

Read from `main` at `e48de2e6`:

- `--max-turns 60` and no budget flag, so one run had no cost bound the workflow could show.
- The model's only shell tool was `Bash(gh issue create:*)` and the job held `issues: write`. `gh issue create`
  accepts `--body-file`, so that one prefix let the model read a runner file outside the built-in Read rules and
  publish it in an issue. Removing the tool removes the path; the grant goes with it.
- The result was an issue written by the model. Nothing kept the run's token counts, so a cache read could not be
  shown afterwards: the action's console output keeps cost and turns and reduces model usage to the context
  window and output limit (`sanitizeModelUsage` in `base-action/src/run-claude-sdk.ts` at the pin).

## The pin

| Release | Commit | Published | Change over the previous release |
| --- | --- | --- | --- |
| v1.0.245 (on `main`) | `6fed3ca145920b639991cb756090506e1bcaf515` | | |
| v1.0.246 | `38c80c1a32cdbc0c6f34042464a0669d89363dde` | 2026-10-08T17:29:32Z | one commit: "bump Claude Code to 2.1.294 and Agent SDK to 0.3.294" |
| v1.0.247 (this change) | `2dca132ff0e0c4094ce6048b422c6915a071210b` | 2026-10-08T19:54:20Z | one commit: "bump Claude Code to 2.1.295 and Agent SDK to 0.3.295" |

Both release notes are a changelog link only. `GET repos/anthropics/claude-code-action/compare/v1.0.245...v1.0.246`
and `.../compare/v1.0.246...v1.0.247` (read 2026-10-08, 21:29Z) each list six files: `base-action/action.yml`,
`base-action/bun.lock`, `base-action/package.json`, `bun.lock`, `package.json` and `src/entrypoints/run.ts`. The root
`action.yml`, which defines the inputs this workflow passes, is in neither list. The effective change is the Claude
Code version the action installs, 2.1.295.

## Bounds and how each is enforced

| Bound | Where | Source |
| --- | --- | --- |
| Read, Glob, Grep only | `--tools Read,Glob,Grep` (availability) and `--allowedTools` (no prompt) | Claude Code 2.1.295 `--help`: `--tools` "Specify the list of available tools from the built-in set" |
| 20 turns | `--max-turns 20` | accepted by the 2.1.295 argument parser (`option '--max-turns <turns>'`) |
| $3 per run | `--max-budget-usd 3` | same `--help`: "Maximum dollar amount to spend on API calls"; a client estimate, checked again from the run's own numbers |
| no hooks, no project or local settings, no MCP servers | `settings` `disableAllHooks`, `--setting-sources user`, `--strict-mcp-config` | same `--help`; settings keys present in the 2.1.295 build |
| reads stay in the checkout and the prompt directory | `settings` `permissions.blockReadsOutsideWorkingDirectories` and deny rules for `.git`, `.env`, key files | settings key present in the 2.1.295 build |
| no full model output in a public log | `show_full_output: 'false'`, and a first guard step that refuses a run with step or runner debugging on | `showFullOutput = options.showFullOutput === "true" \|\| isDebugMode`, where `isDebugMode` is `ACTIONS_STEP_DEBUG === "true"` (`base-action/src/parse-sdk-options.ts` at the pin) |
| no key in GitHub | federation inputs only; the workflow passes no `anthropic_api_key` | "a static credential takes precedence and federation will not be used" (`docs/setup.md` at the pin) |

The guard step also refuses a runner that already has `~/.claude/settings.json`: the action's setup logs
`Found existing settings:` followed by that file's content (`base-action/src/setup-claude-code-settings.ts` at the
pin). The guard tests presence only.

After the run, one step reads the action's execution file, writes only numbers (`total_cost_usd`, `num_turns`,
the success flag, and per model the input, output, cache-read and cache-creation token counts and cost) to
`usage.json` and to the job summary, and then fails the job unless the result is a success, used 1 to 20 turns, cost
at most $3 by the client's estimate and read the prompt cache at least once. The numbers are written before the
check, so a failed or over-budget run still leaves its cost. The execution file itself holds the whole transcript
and is never printed or uploaded. A second step, which runs only when the check passed, copies the final result
text to the job summary, escaped, inside `<pre>`, capped at 60,000 bytes.

Prompt caching needs no configuration here: Claude Code caches the tools, the system prompt and the growing
conversation by itself, with a five-minute lifetime when the run is billed to a Console organization. One run of a
few minutes reads its own cache, so the one-hour lifetime (`promptCacheTtl`, twice the base input price to write
against 1.25 times) would cost more and buy nothing.

## Cost of one run

Dry estimate, Claude Opus 5.5 at $4 input, $5 five-minute cache write, $0.20 cache read and $20 output per million
tokens: about 30,000 uncached input, 60,000 to 90,000 cache-written, 300,000 to 500,000 cache-read and 20,000 output
tokens, $0.90 to $1.10. An all-uncached reading of the same volume stays under the $3 budget. These are estimates;
the first activated run's `usage.json` replaces them.

Runs spend from the Console organization that the repository variables `ANTHROPIC_ORGANIZATION_ID`,
`ANTHROPIC_FEDERATION_RULE_ID`, `ANTHROPIC_SERVICE_ACCOUNT_ID` and `ANTHROPIC_WORKSPACE_ID` name (read by name on
2026-10-08, 21:24Z; the repository's only secret is `FOUNDATION_RESTORE_FIXTURE_20260920`).

## Not done here

- Hosted acceptance. Run 37739403956 failed at the token exchange and the Console's reason is not in the retained
  evidence; a bounded run needs that fixed first.
- A tracked issue for the report. If one is wanted, a second job without a model can create it from an artifact
  with `issues: write`; the model keeps no write path.
- Fast mode. Claude Code takes it from `--settings '{"fastMode": true}'` in non-interactive runs, needs the
  organization provisioned, and falls back to standard speed by itself on a rate limit; this job stays standard.

## Changed existing test contracts

- `tests.test_workflow_policy.RepositoryPolicyTests.test_write_grants_are_the_reviewed_inventory`: the inventory
  entry for `harness-audit.yml:audit` changes from `["id-token: write", "issues: write"]` to `["id-token: write"]`.
  No other entry and no exemption changes.

New, in `tests/test_claude_harness_audit_bounds.py`: the job's condition, permissions, pin, inputs, tool list and
settings are asserted from the workflow file, and the guard, numbers and report steps are executed as written on
synthetic inputs (each debug signal, a pre-existing settings file and a dangling link, an accepted run, six unmet
bounds, six unreadable execution files, a hostile report). Six weakened copies of the workflow (a $30 budget check,
a 600,000-byte cap, 60 turns, a settings check that passes a symlink, a cache check that accepts zero, an added
Bash tool) each fail at least one test.

## Alternatives considered

- **Keep `gh issue create`.** Rejected: it is the one write path the model had, and `--body-file` makes it a read
  path too.
- **Eight turns** (the first draft of this bound). Rejected for this prompt: the audit reads many files, and a run
  that stops one turn short is paid for and returns nothing. The budget is the cost bound; the turn limit is the
  second line.
- **A stored API key as an Actions secret.** Not proposed. Federation is the stated route; if the credit sits in
  another Console organization, the route is a federation rule there and a change to the four variables.
- **`anthropics/claude-code-security-review` or another action for the audit.** Not relevant to this job; the
  security-review record covers that action.

## What would overturn it

- A first activated run stops at `error_max_turns` or `error_max_budget_usd` with a useful audit unfinished: raise
  the one bound that stopped it, with that run's numbers.
- The action changes the execution file's shape (the numbers step fails on "unsupported execution shape"): read the
  new shape at the new pin and change the extractor in the same pull request as the pin.
- Upstream ships a supported way to export token counts without the execution file: use it and drop the extractor.

## Evidence class

`local_static_analysis`: actionlint 1.17.0 and zizmor 1.30.1 (offline, no configuration) on the workflow, no
findings. `local_integration`: the unit tests named above, PyYAML 6.0.3 on Python 3.12. `documented_api_check`: the
`gh api` reads named above. No hosted run of this workflow is part of this record.

## SOTA sources

- anthropics/claude-code-action at `2dca132ff0e0c4094ce6048b422c6915a071210b` (v1.0.247): `action.yml` (inputs
  `anthropic_federation_rule_id`, `anthropic_organization_id`, `anthropic_service_account_id`,
  `anthropic_workspace_id`, `settings`, `claude_args`, `show_full_output`; output `execution_file`),
  `docs/setup.md` (authentication precedence), `docs/security.md`, `base-action/src/execution-file.ts`;
  <https://github.com/anthropics/claude-code-action/tree/2dca132ff0e0c4094ce6048b422c6915a071210b>.
- Claude Code 2.1.295 `--help` (the version the pin installs) for `--tools`, `--allowedTools`, `--max-budget-usd`,
  `--setting-sources`, `--strict-mcp-config`, `--add-dir`, `--settings`.
- Anthropic, How Claude Code uses prompt caching, "Cache lifetime":
  <https://code.claude.com/docs/en/prompt-caching>; Pricing:
  <https://platform.claude.com/docs/en/about-claude/pricing>; Claude Code fast mode:
  <https://code.claude.com/docs/en/fast-mode>; all read 2026-10-08.
- GitHub, OpenID Connect reference (subject of a run on a branch):
  <https://docs.github.com/en/actions/reference/security/oidc>.
- The audit prompt: FlorianBruniaux/claude-code-ultimate-guide at `585c2030cd590e991d84dae4d6614cd449f245b1`,
  `tools/audit-prompt.md`, sha256 `1d1fb98d87d40d0141b5243d60afe898d982a14f6e02c1d2d2931df89a7c0ede` (unchanged).
