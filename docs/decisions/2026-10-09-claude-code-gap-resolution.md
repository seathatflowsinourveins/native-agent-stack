# Claude Code 2.1.296 gap resolution, 2026-10-09

**Clear the upstream-surface backlog to Claude Code 2.1.296 and Codex rust-v0.162.1
with catalog data only, and leave every host, settings and instruction change to
the command center or the owner.** The repository already ships the machinery
that finds new features: the
[upstream-surface watch](../upstream-surface-watch.md), its
[dispositions catalog](../../catalogs/foundation/upstream-surface-dispositions.json)
and the `claude-native-practice` refresh loop. It had fallen behind and was not
scheduled on this host. This record resolves the backlog it had accumulated and
names what remains with its owners. It adds no code, instruction text, setting,
hook, service or unit.

Trigger (2026-10-09): a gap review of the 2.1.296 release, the agent-team and
workflow practice, and the hosted features announced on 2026-10-07 to 2026-10-09
against the repository's native workflow.

## Measured backlog

`python3 scripts/upstream_surface_watch.py --network --dry-run --json` compares
the live upstream surfaces with the baseline of 2026-10-04 (Claude Code 2.1.289,
Codex rust-v0.160.0). It writes nothing.

| Run (UTC) | New | Removed | Stage changes | Unreviewed | Note |
| --- | --- | --- | --- | --- | --- |
| 2026-10-09 23:39:44Z | 40 | 6 | 0 | 38 | `codex:feature` unobserved: `codex --version` timed out at 60 s under host load |
| 2026-10-09 23:51:12Z | 55 | 6 | 2 | 51 | all kinds observed |
| 2026-10-10 00:04:06Z, at the PR base | 55 | 6 | 2 | 51 | 49 names plus two reopened instruction documents |
| 2026-10-10 00:25:49Z, after the rows and the new baseline | 0 | 0 | 0 | 0 | no document changed, all kinds observed |

The 55 new names are one Claude setting, ten Claude environment variables, 29 Codex
configuration keys and 15 Codex features. Six already had rows
(`idleCompaction`, `CLAUDE_CODE_EMIT_SESSION_STATE_EVENTS`,
`CLAUDE_CODE_GZIP_REQUEST_BODIES`, `NODE_EXTRA_CA_CERTS` and two Guardian
features), so 49 were open. The two stage changes are `api_key_model_discovery`
(to stable) and `apply_patch_preserve_line_endings` (removed); neither had a row.
The six removed keys are `plugins.*.mcp_servers.*.ema_auth*`, which had no rows.

## Dispositions written

51 name rows (the 49 open names plus two the docs do not list yet) and two
re-reviewed document rows, each with its primary source pinned and a dated
overturn condition. The catalog now holds 363 rows, and its baseline pointer and
description name this pass.

| Surface | Rows | declined | default-on | not-applicable | defer-user |
| --- | --- | --- | --- | --- | --- |
| Claude environment variables | 9 | 4 | 2 | 3 | 0 |
| Codex features (13) and config keys (29) | 42 | 30 | 0 | 9 | 3 |

Four rows were ruled by the command center on 2026-10-09 and are marked below.

- **Workflow-agent model** (command center ruling).
  `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL` (2.1.296) is `declined` and stays unset, so
  workflow agents inherit the session model. Claude stays on top-quality judgment,
  and cost savings come from routing bulk work to GPT lanes, not from lowering
  Claude subagent models. `CLAUDE_CODE_SUBAGENT_MODEL=opus` already names children
  ([anti-pattern log](../harness-defaults.md)); the precedence between the two is
  undocumented. Overturn needs a frozen-packet quality-parity result and a ruling.
- **Retry tuning.** The 529 backoff variables and the 429/529 watchdog cap are
  declined: retry tuning is a safety net, not the fix, and the watchdog they refine
  is off. Overturn is a measured retry exhaustion in an unattended lane.
- **WebSearch refill.** `CLAUDE_CODE_WEB_SEARCH_REFILLS_PER_HOUR` is `default-on`
  (100 an hour interactive, 0 non-interactive). The project's per-session cap
  stays the bound; the interaction of the two is unverified.
- **Cyber access cluster** (command center ruling; `daybreak`,
  `api_key_cyber_access_programs`): account programs, so `defer-user` as owner
  information only, with no stack change. `cli_daybreak` is declined as native-off.
- **Ultra Fast** (command center ruling; `ultrafast_mode`, stable and on, "Enable
  Ultra Fast mode independently of Fast mode"): `declined`. It is plan-gated, and
  the OmniRoute profile drops it client-side (measured 2026-10-09). Overturn is a
  plan or profile change that makes it reachable from lanes, then a same-work tier
  comparison.
- **Provider capabilities** (command center ruling;
  `model_providers.*.capabilities*`): `declined` for now. A capabilities
  declaration changes what Codex enables on the OmniRoute route, so it needs the
  effort-ladder proof first; the currency lane trials it after #943.
- **Remote message board** (`features.multi_agent_v2.message_board_remote*`):
  declined with its parent `multi_agent_v2`; `bearer_token` is a credential field,
  so if the board is ever adopted the token comes from the secret loader through
  `bearer_token_env_var`, never inline.
- Desktop-app gates (`browser_annotation_api`, `in_app_voice`), voice input and TUI
  preferences are `not-applicable` to headless lanes.

## Document re-reviews

The two reopened rows record that the pages' bodies changed. The earlier audit
([record](2026-10-06-harness-context-budget-completion.md)) kept no old bytes, so
a different digest alone does not show what changed; its digest table is
superseded for these two pages by the digests here, and the rows keep it as their
carrier. Current guidance still preserves the distinctions it tracked:

- `claude:doc:memory`, digest `b4e76ef1` to `52c9ce22`: `@path` imports expand at
  launch; `AGENTS.md` is read only when no `CLAUDE.md` or `CLAUDE.local.md` exists,
  and a `CLAUDE.md` that imports it loads both; auto memory loads the first 200
  lines or 25 KB; `CLAUDE.md` should stay under 200 lines. This repository's
  `CLAUDE.md` (8 lines) imports `AGENTS.md` (14 lines).
- `claude:doc:skills`, digest `cf869f4c` to `3a4428d1`: an invoked skill stays in
  context, and compaction re-attaches the first 5,000 tokens of each recent
  invocation within a combined 25,000 tokens.
- `codex:doc:agents-md` is unchanged.

**Page-digest rows considered and not added.** A new, renamed or removed docs page
is how hosted features appear (the Claude Code Projects page, the Managed Agents
workflow pages), and the Platform release notes carry API, pricing and Managed
Agents changes, so three whole-body `enabled` document rows were tried in memory
against the validator: the docs index
(`https://code.claude.com/docs/llms.txt`), the Platform release notes and the
Projects page. Each body hashes identically across back-to-back fetches with the
watch's `Accept: text/markdown` header, so a digest is usable. They are not added
because of the change rate: a changed digest counts as unreviewed until a digest
update lands, so a page that edits every day or two would keep the daily notice
nonzero. On 2026-10-09 the release notes had 8 dated entries in the previous 14
days and the active-model currency data already cites that page; the index lists
267 links; the Projects page is a beta page that will keep editing. Follow-up, not
built: a report-only page-URL diff of the docs index and a headline diff of the
release notes, which surface new pages without a standing unreviewed count.

## What the watch cannot see

- **Names the changelog lists before the docs do.** `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL`
  and `CLAUDE_CODE_OVERLOADED_RETRY_MAX_DELAY_MS` are in the 2.1.296 changelog and
  binary, and absent from the environment-variable reference the watch reads. They
  have rows here by hand. Follow-up, not built: report `CLAUDE_CODE_*` tokens from
  the changelog's "Added" bullets as report-only items, tested with a synthetic
  changelog.
- **Hosted surfaces and non-name changes** (Projects, Managed Agents, routines;
  subagent frontmatter keys such as `autoCompactWindow`; tool parameters such as
  the Read tool's `allow_large`; defaults and meanings): outside the name diff by
  design ([guide](../upstream-surface-watch.md)). The weekly practice pass reads
  the changelog and release notes for them until the page-URL diff above exists.

## Handed off, not changed here

- **Command center, tools window.** `stack-currency.timer` and
  `upstream-surface-watch.service` are not installed on this host (no unit files,
  no `latest.json`). The install block in
  [lifecycle.md](../../adoption/lifecycle.md) renders `@REPOSITORY@` as
  `~/code/native-agent-stack-live`, a checkout that must track `origin/main`; the
  units read these catalogs from that root, so this change should land before the
  first daily run (otherwise it reports the whole backlog again). The command center
  creates that checkout and installs both units after #943 lands, because that PR's
  collector exits 2 once the committed model manifest is a day old.
- **Settings drift** for the inventory (template, user and local settings
  disagree): `ultracode`, `model`, `advisorModel`, `cleanupPeriodDays`,
  `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` and two plugins present only live. In this
  checkout the gitignored local settings file turns `ultracode` off over the
  project's `true`.
- **cc-native-practice, living page** (draft #923; after it lands, client version
  to 2.1.296): `background-workflows`, `subagent-definitions`,
  `context-compaction`, `headless-sdk`, `agent-teams`, `output-compression`,
  `usage-cost-monitoring` and `model-effort-routing` deltas, and a `hosted-surfaces`
  slot for Projects, Managed Agents, routines, Remote Control, channels and agent
  view. An exact-case search of the draft's pages on 2026-10-09 found no slot for
  any of them.
- **grand-catalog candidates:** Claude Code Projects as WATCH (public beta, Pro and
  Max, hosted only, no CLI surface); Managed Agents dynamic workflows
  (`managed-agents-2026-04-01`, beta since 2026-10-09) as TRIAL, conditional on the
  credits decision; a routines row.
- **Owner items:** the Max-plan API credits ($100 on Max 5x, $200 on Max 20x a
  month, claimed by linking a Console organization; they cover the API, Agent SDK,
  `claude -p` with an API key and Managed Agents, not interactive Claude Code)
  touch credentials and spending. The Codex cyber access programs (`daybreak`,
  `api_key_cyber_access_programs`) are information only. Sonnet 5.5 cache reads fell
  from $0.20 to $0.10 per million tokens on 2026-10-07; cost readings from
  third-party price data may lag.
- **Currency lane:** the `model_providers.*.capabilities*` trial after #943, with
  the effort-ladder proof first.
- **Agent teams** stay as decided: experimental, narrow use, `TeammateIdle` pending
  a first real team run; `TaskCreated` and `TaskCompleted` are already
  `not-applicable`.

## Evidence

Measured on this host: the watch runs above, with the new baseline written through
`--network --write-baseline --force` under a scratch `XDG_STATE_HOME` so the host's
watch state directory stays absent until the units are installed;
`--check-dispositions` (363 rows valid); the targeted unit tests (231 tests,
6 skipped, before and after) and `python3 scripts/validate.py` (passed before and
after). Source-reviewed: the pages, changelog, release notes and source files
listed below. Not run: the behavior of any 2.1.296 change, the daily units, the
precedence of `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL` over
`CLAUDE_CODE_SUBAGENT_MODEL`, and any Managed Agents workflow.

**Inverse:** revert the whole commit. The baseline returns to Claude Code 2.1.289
and Codex rust-v0.160.0, the two reopened rows return to their 2026-10-06 digests,
and the 51 items resurface as unreviewed, which is the intended signal. Reverting
only the rows would leave them silently grandfathered by the new baseline, so do
not do that.

**Overturn:** a row is reopened by a changed document digest, a supported release
that changes the named behavior, or a measured need on a lane.

## SOTA sources

- [anthropics/claude-code CHANGELOG.md at `2301018b`](https://github.com/anthropics/claude-code/blob/2301018b1f61073c501a8e7a4813ef48c239163b/CHANGELOG.md#L3):
  the 2.1.296 section (lines 3 to 84, with the entries at lines 7 and 8 cited by
  rows) and the entries at lines 100 (2.1.295), 299 (2.1.292) and 554 (2.1.290).
- Claude Code docs read 2026-10-09:
  [environment variables](https://code.claude.com/docs/en/env-vars),
  [memory](https://code.claude.com/docs/en/memory),
  [skills](https://code.claude.com/docs/en/skills#skill-content-lifecycle),
  [agent teams](https://code.claude.com/docs/en/agent-teams),
  [workflows](https://code.claude.com/docs/en/workflows) and the
  [page index](https://code.claude.com/docs/llms.txt).
- [Claude Platform release notes](https://platform.claude.com/docs/en/release-notes/overview.md)
  (2026-10-07 Sonnet 5.5 cache-read price; 2026-10-09 Managed Agents dynamic
  workflows) and the
  [API credits article](https://support.claude.com/en/articles/17154008-monthly-api-credits-for-max-and-team-plans).
- `@anthropic-ai/claude-agent-sdk` 0.3.296 `sdk.d.ts` and the installed 2.1.296
  binary for `idleCompaction` (documented in neither the docs nor the changelog).
- [openai/codex rust-v0.162.1](https://github.com/openai/codex/tree/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d)
  at commit `092d3acd`: `codex-rs/features/src/lib.rs` (feature table and doc
  comments) and the `config-schema.json` release asset (sha256 `7933a705`), with the
  [rust-v0.161.0](https://github.com/openai/codex/releases/tag/rust-v0.161.0) and
  [rust-v0.162.0](https://github.com/openai/codex/releases/tag/rust-v0.162.0)
  release notes.
