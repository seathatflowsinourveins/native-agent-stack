# Bounded harness audit on the current Claude action pin — 2026-10-08

`harness-audit.yml` moves from `anthropics/claude-code-action` v1.0.245 to v1.0.247 and becomes a bounded,
read-only job: Claude gets Read, Glob and Grep under `--restricted`, at most 20 turns and a $3 client budget; the
job holds `contents: read` and `id-token: write` and nothing else; a model-free step copies the report to the job
summary and keeps the run's token and cost numbers. The job runs only while the repository variable
`CLAUDE_HARNESS_AUDIT_ENABLED` is `true`, and only on the first attempt of a run. Nothing in this change starts a
run, sets a variable or touches the federation rule.

## What was wrong with the job as landed

Read from `main` at `e48de2e6`:

- `--max-turns 60` and no budget flag, so one run had no cost bound the workflow could show.
- The model's only shell tool was `Bash(gh issue create:*)` and the job held `issues: write`. `gh issue create`
  accepts `--body-file`, so that one prefix let the model read a runner file outside the built-in Read rules and
  publish it in an issue. Removing the tool removes the path; the grant goes with it.
- The result was an issue written by the model. Nothing kept the run's token counts, so a cache read could not be
  shown afterwards: the action's console output keeps cost and turns and reduces model usage to the context
  window and output limit (`sanitizeModelUsage` in `base-action/src/run-claude-sdk.ts` at the pin).
- A re-run of a finished run would have spent again: a re-run keeps `github.actor` and needs no new request.

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
Code version the action installs.

v1.0.247 is taken although it is hours old, for one line of the Claude Code 2.1.295 changelog: "Fixed `--tools`
and `--restricted` not applying to built-in tools that register after launch". This job's read-only property rests
on those two flags. Dependabot's seven-day cooldown (`.github/dependabot.yml`) governs its own update pull requests,
not a reviewed pin like this one; it will propose later releases on its usual schedule.

## Bounds and how each is enforced

| Bound | Where | Source |
| --- | --- | --- |
| Read, Glob, Grep only | `--tools Read,Glob,Grep` (availability) and `--allowedTools` (no prompt) | Claude Code 2.1.295 `--help`: `--tools` "Specify the list of available tools from the built-in set" |
| no code-running tool, no WebFetch, no settings file, file tools inside the working directories | `--restricted` | same `--help`: "removes the built-in tools that run commands or code ... and WebFetch unless --tools names them, and ignores user, project and local settings files (managed settings and --settings still apply; add --strict-mcp-config to skip MCP servers too). Also confines the file tools to the working directories (--add-dir included), refuses bypassPermissions" |
| nothing waits for an answer | `--permission-prompts none` | same `--help`: "nobody: anything that would prompt is denied automatically"; changelog 2.1.259: "for unattended headless hosts" |
| no MCP server | `--strict-mcp-config` | same `--help` |
| hooks off; no read of any `.git` directory, `.env` or key file | `--settings` JSON (`disableAllHooks`, `permissions.deny`) | `--settings` still applies under `--restricted`; the action sets git authentication in the root checkout (`src/github/operations/git-config.ts`) |
| 20 turns | `--max-turns 20` | accepted by the 2.1.295 argument parser (`option '--max-turns <turns>'`); checked again after the run as distinct assistant message ids, because the result's `num_turns` counts transcript messages |
| $3 per run | `--max-budget-usd 3` | same `--help`: "Maximum dollar amount to spend on API calls"; a client estimate, checked again from the run's own numbers |
| no full model output in a public log | `show_full_output: 'false'`, `ACTIONS_STEP_DEBUG: 'false'` in the action step's environment, and a first guard step that refuses a run with runner debugging on | `showFullOutput = options.showFullOutput === "true" \|\| isDebugMode`, where `isDebugMode` is `ACTIONS_STEP_DEBUG === "true"` (`base-action/src/parse-sdk-options.ts` at the pin) |
| no key in GitHub | federation inputs only; the workflow passes no static credential | "a static credential takes precedence and federation will not be used" (`docs/setup.md` at the pin) |
| one spend per request | `github.run_attempt == 1`, and for a dispatch the owner as both actor and triggering actor | GitHub contexts reference: a re-run keeps `github.actor`; `github.triggering_actor` is who re-ran it |

The action's `settings` input is not used: it writes the user settings file, which `--restricted` ignores, so the
same JSON goes to `--settings`. `--setting-sources user` stays, because without it the action asks for user, project
and local sources (`base-action/src/parse-sdk-options.ts`).

The guard step also refuses a runner that already has `~/.claude/settings.json`: the action's setup logs
`Found existing settings:` followed by that file's content (`base-action/src/setup-claude-code-settings.ts` at the
pin). The guard tests presence only.

### What was checked at runtime

The same flag set was run on the installed client (Claude Code 2.1.295, the version the pin installs) against a
throwaway tree: files at the root, an untrusted subdirectory with its own `CLAUDE.md`, a skill and a hook, a root
settings file with a hook, a root `CLAUDE.md`, `.git/config` files and a file outside the tree. In three runs the
session's tools were exactly Glob, Grep and Read; files inside the tree were read; the file outside the tree and
both `.git/config` files were denied; no hook ran; no instruction file changed the answer; there was no shell
(`evidence/artifacts/claude-actions-fence-smoke-20261008/receipt.json`). That is one small model and one prompt: it
shows these controls held there, not that no input can defeat them. The action passes `claude_args` through its own
parser (`shell-quote`); replaying that parser on this workflow's text yields the same flags and the same JSON.

### After the run

One step reads the action's execution file and keeps only numbers and fixed names: cost, turns, the success flag,
the Claude Code version, the session's tool list, the number of MCP servers and per-model token counts. The record
is written before the check, so a failed or over-budget run still leaves its cost. The step then fails the job
unless the run succeeded, used 1 to 20 assistant turns (distinct assistant message ids; the client's `num_turns` counts transcript messages, tool results included, so a 12-request run on 2.1.295 reported 57, and it is only recorded), cost at most $3 by the client's estimate, read the prompt cache, had
no MCP server and had none of Bash, Write, Edit, MultiEdit, NotebookEdit, WebFetch, WebSearch, Task, Agent or an
`mcp__` tool. The execution file itself holds the whole transcript and is never printed or uploaded. A second step,
which runs only when the check passed, copies the final result text to the job summary, escaped, inside `<pre>`,
capped at 60,000 bytes.

Prompt caching needs no configuration here: Claude Code caches the tools, the system prompt and the growing
conversation by itself, with a five-minute lifetime when the run is billed to a Console organization. One run of a
few minutes reads its own cache, so the one-hour lifetime (`promptCacheTtl`, twice the base input price to write
against 1.25 times) would cost more and buy nothing.

## Effort

`--effort max` in `claude_args`, set under the command center's effort mapping of 2026-10-08, which runs judgment work (designated reads, adjudication, pull request and security reviews, audits) at `max`. Every job records its level and the reason, because an unset level is a defect. The level has to be in `claude_args`: `--restricted` ignores the settings files that would otherwise carry a session's level, and on the Claude API Opus 5.5 runs at `medium` when a request leaves effort unset (bundled `claude-api` skill 2.1.295, `shared/model-migration.md`). `claude --help` (2.1.295) lists `low, medium, high, xhigh, max`. A loopback dry run of the installed 2.1.295 client with this workflow's `claude_args` sent `output_config.effort: "max"`, adaptive thinking and no `speed` field on every request. At `max`, thinking takes a larger share of the output than at the default level, so the estimate below is a floor; the client budget still bounds each run.

## Cost of one run

Dry estimate, Claude Opus 5.5 at $4 input, $5 five-minute cache write, $0.20 cache read and $20 output per million
tokens: about 30,000 uncached input, 60,000 to 90,000 cache-written, 300,000 to 500,000 cache-read and 20,000 output
tokens, $0.90 to $1.10. An all-uncached reading of the same volume stays under the $3 budget. These are estimates;
the first activated run's `usage.json` replaces them.

The pinned audit prompt has four phases and eight dimensions and was written for a session with a shell; `main`
gave it 60 turns. Twenty turns without a shell may not finish it. The prompt tells the model its limit, and a run
that stops at the limit fails the bounds check with its numbers kept; that outcome is the measurement that would
raise the limit.

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

New, in `tests/test_claude_harness_audit_bounds.py` (17 tests): the job's condition, permissions, pin, inputs, flags
and settings are asserted from the workflow file, and the guard, numbers and report steps are executed as written on
synthetic inputs. Sixteen weakened copies of the workflow each fail at least one test: a $30 budget check, a
600,000-byte cap, 60 or 200 turns, a settings check that passes a symlink, a cache check that accepts zero, an added
Bash tool, a missing first-attempt or triggering-actor condition, a missing tool, MCP or session-start check,
`--restricted` or `--permission-prompts none` removed, the `.git` deny rule removed, and step debugging set to true.

## Alternatives considered

- **Keep `gh issue create`.** Rejected: it is the one write path the model had, and `--body-file` makes it a read
  path too.
- **Eight turns** (the first draft of this bound). Rejected for this prompt: the audit reads many files, and a run
  that stops one turn short is paid for and returns nothing. The budget is the cost bound; the turn limit is the
  second line.
- **Keep the fence in the action's `settings` input.** Rejected once `--restricted` was chosen: that input writes
  a settings file, which `--restricted` ignores.
- **A stored API key as an Actions secret.** Not proposed. Federation is the stated route; if the credit sits in
  another Console organization, the route is a federation rule there and a change to the four variables.

## What would overturn it

- A first activated run stops at `error_max_turns` or `error_max_budget_usd` with a useful audit unfinished: raise
  the one bound that stopped it, with that run's numbers.
- The numbers step reports a forbidden tool or an MCP server: stop the job and read the action's change.
- The action changes the execution file's shape (the numbers step fails on "unsupported execution shape"): read the
  new shape at the new pin and change the extractor in the same pull request as the pin.
- Upstream ships a supported way to export token counts without the execution file: use it and drop the extractor.

## Evidence class

`native_proven` for the flag set on the installed client (the receipt above; not through the action and not on a
GitHub runner). `local_static_analysis`: actionlint 1.17.0 and zizmor 1.30.1 (offline, regular and pedantic), no
findings. `local_integration`: the unit tests named above, PyYAML 6.0.3 on Python 3.12. `documented_api_check`: the
`gh api` reads named above. No hosted run of this workflow is part of this record.

## SOTA sources

- anthropics/claude-code-action at `2dca132ff0e0c4094ce6048b422c6915a071210b` (v1.0.247): `action.yml` (inputs
  `anthropic_federation_rule_id`, `anthropic_organization_id`, `anthropic_service_account_id`,
  `anthropic_workspace_id`, `claude_args`, `show_full_output`; output `execution_file`), `docs/setup.md`
  (authentication precedence), `docs/security.md`, `base-action/src/parse-sdk-options.ts`,
  `base-action/src/setup-claude-code-settings.ts`, `base-action/src/run-claude-sdk.ts`,
  `base-action/src/execution-file.ts`, `src/github/operations/git-config.ts`;
  <https://github.com/anthropics/claude-code-action/tree/2dca132ff0e0c4094ce6048b422c6915a071210b>.
- Claude Code 2.1.295 `--help` (the version the pin installs) for `--restricted`, `--permission-prompts`, `--tools`,
  `--allowedTools`, `--max-budget-usd`, `--setting-sources`, `--strict-mcp-config`, `--add-dir`, `--settings`; and
  anthropics/claude-code `CHANGELOG.md`, sections 2.1.295, 2.1.259 and 2.1.248
  (<https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md>, read 2026-10-08).
- Anthropic, How Claude Code uses prompt caching, "Cache lifetime":
  <https://code.claude.com/docs/en/prompt-caching>; Pricing:
  <https://platform.claude.com/docs/en/about-claude/pricing>; Claude Code fast mode:
  <https://code.claude.com/docs/en/fast-mode>; all read 2026-10-08.
- GitHub, OpenID Connect reference (subject of a run on a branch):
  <https://docs.github.com/en/actions/reference/security/oidc>; contexts reference (`github.triggering_actor`,
  `github.run_attempt`): <https://docs.github.com/en/actions/reference/workflows-and-actions/contexts>.
- The audit prompt: FlorianBruniaux/claude-code-ultimate-guide at `585c2030cd590e991d84dae4d6614cd449f245b1`,
  `tools/audit-prompt.md`, sha256 `1d1fb98d87d40d0141b5243d60afe898d982a14f6e02c1d2d2931df89a7c0ede` (unchanged).
