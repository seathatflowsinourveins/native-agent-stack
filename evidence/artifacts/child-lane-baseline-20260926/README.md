# Child and worker lane baseline, frozen window (2026-09-26)

Host: `nativestack-5975wx-20260925` (the WSL2 workstation). Window: `[2026-09-25T17:18:00Z,
2026-09-26T15:05:00Z)`. Machine-readable provenance: [`provenance.json`](provenance.json).

**Evidence class: `local_integration`.** This is a measurement of native Claude Code and Codex
transcripts by this repository's own tools. No model ran for it. The one native command,
`claude -p "/skill-doctor"`, is a local command (`total_cost_usd` 0, `num_turns` 0). The figures are
not billed cost and not savings.

## Question

Which lanes do Claude workflow and Agent-tool children, and Codex workers, actually use? Lanes here
are Skill calls, ToolSearch loads, MCP calls per server, Bash and RTK rewrites, fetch routing, the
injected routing block and first-prompt size. This is the "before" measurement for the wiring
changes of the 2026-09-26 native-workflow plan (SubagentStart injection, the Codex worker lane,
stack agents).

## Files

| File | Content |
| --- | --- |
| [`claude-lanes.json`](claude-lanes.json) | `child-usage.mjs --lanes-sweep`: 639 Claude child transcripts, grouped by spawn path, agent type and session ordinal, with RTK `hook_decisions` joined |
| [`codex-lanes.json`](codex-lanes.json) | `skill_usage.py --lanes`: 239 Codex rollout sessions, workers apart from negative controls |
| [`skill-invoke-rate.json`](skill-invoke-rate.json) | The skills trial's invoke-rate report: `/skill-doctor` for Claude, rollouts for Codex; a snapshot at capture time, not windowed |
| [`cross_check.py`](cross_check.py), [`cross-check.json`](cross-check.json) | An independent re-derivation of the headline counts |
| [`provenance.json`](provenance.json) | Commands, exit codes, times, tool sha256 and versions |

## Method

1. **Claude.** `node examples/claude-native/workflows/child-usage.mjs --lanes-sweep --root <claude
   config>/projects --since … --until … --rtk-db <rtk data dir>/history.db`. It reads every
   `subagents/**/agent-*.jsonl` under the root: workflow children under `workflows/wf_*` and
   Agent-tool children directly under `subagents/`. Only rows inside the window count. Tool calls are
   `tool_use` blocks deduplicated by id, each counted in the window of its first row. An RTK
   rewrite is a `PreToolUse:Bash` row from `rtk hook` whose stdout carries `updatedInput`. The RTK
   database join opens `hook_decisions` read-only and matches rows 1:1 on `tool_use_id`. `allow`
   plus `ask` is RTK's own "covered" outcome (`HookOutcome::is_covered`, rtk v0.50.0
   `src/core/tracking.rs`). `curl`/`wget` counts only in command position of the text a shell
   runs: quoted strings and heredoc bodies count only under `sh -c`, `eval`, `ssh` or a heredoc fed
   to a shell. The marker is `<context_window_protection>`, the opening tag of Context Mode
   1.0.169's routing block. It is looked for only in the first prompt and in SubagentStart hook
   context, never in tool input or output.
2. **Codex.** `python3 tools/skill-usage/skill_usage.py --lanes --codex-root <codex home>/sessions
   --since … --until … --json`. It counts `item_completed` items (McpToolCall, CommandExecution,
   Extension, FileChange) and `function_call` records. Sessions that did not load the user config
   (`--ignore-user-config`: the landscape sweep and blind lanes) are negative controls. They are
   identified from the session's own skill catalog. Codex applies skill enable/disable rules only
   from the User and SessionFlags config layers (`codex-rs/config/src/skills_config.rs`,
   rust-v0.157.1), and `--ignore-user-config` loads the User layer as an empty table
   (`codex-rs/config/src/loader/mod.rs`). So a catalog listing a `codex_enabled: false` manifest
   skill means that session ran without the user config. A spawned sub-agent's rollout starts with
   records copied from its parent (ordinals below `subagent_history_start_ordinal`); those count
   toward its marker and catalog, never as its own calls.
3. **Skills invoke rate.** `claude -p "/skill-doctor" --output-format json` was captured outside the
   checkout at 16:33:56Z. That capture was fed to `skill_usage.py --claude-skill-doctor <capture>
   --codex-root <codex home>/sessions --json`.
4. **Cross-check.** `cross_check.py` is a separate implementation. It splits Codex sessions by the
   marker instead of by the catalog. It agrees with both reports on every figure it computes (see
   `provenance.json` `reproduction`). Each lane report was also generated twice, at 17:06Z and
   17:08Z, with identical groups.
5. **Review.** One read-only cross-family review (Codex) of the tools found seven defects, and all
   seven were fixed before these files were generated. On this window, the fixes changed only the
   Claude `curl`/`wget` counts (quoted text had been counted) and two Codex worker tool calls
   (counted twice before).

## Results: Claude children (639 in 7 sessions)

| Spawn path | Children | Tool calls | Bash | Children using Context Mode | Marker in first prompt | SubagentStart context | First prompt, median tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Workflow | 597 | 31,199 | 22,740 | 44 (7.4%) | 0 | 0 | 42,686 (n=584) |
| Agent tool | 42 | 3,438 | 2,036 | 29 (69.0%) | 42 (100%) | 0 | 17,337 (n=41) |

| Agent type | Children | Bash | Context Mode calls (children) | Skill calls | WebFetch | First prompt, median |
| --- | --- | --- | --- | --- | --- | --- |
| workflow-subagent (no `agentType`) | 465 | 13,058 | 66 (9) | 351 | 1,000 | 44,026 |
| general-purpose | 107 | 10,265 | 186 (18) | 2 | 16 | 37,970 |
| evidence-reviewer | 33 | 0 | 1,070 (32) | 0 | 0 | 17,237 |
| source-scout | 15 | 700 | 0 (0) | 0 | 0 | 10,029 |
| Explore | 13 | 398 | 353 (12) | 0 | 0 | 16,791 |
| Plan | 3 | 158 | 69 (2) | 0 | 0 | 19,370 |
| isolated-builder | 3 | 197 | 0 (0) | 0 | 0 | 19,810 |

- **RTK.** The 24,776 Bash calls break down as rewritten (`ask`) 8,325 (33.6%), `defer` 16,290,
  `deny` 137, and not logged 24. The transcript's own rewrite rows give the same 8,325. The model
  typed an `rtk` prefix itself 27 times.
- **MCP.** There were 1,744 Context Mode calls, from 73 children. All other servers together
  made 37 calls: jCodeMunch 12, ai-memory 6, Serena 6, SocratiCode 6, Headroom 3, QMD 3 and
  codebase-memory 1. ToolSearch was called 371 times by 310 children. It loaded built-in tools 427
  times, Context Mode tools 227, Serena 29 and jCodeMunch 13.
- **Fetch routing.** WebFetch 1,016, `ctx_fetch_and_index` 24, `curl`/`wget` 614, and a further 96
  that reached loopback URLs only. The `ctx_fetch_and_index` share is therefore 1.5%. 1,000 of the
  WebFetch calls came from workflow-subagent children.
- **Skills.** There were 353 Skill calls, from 122 children. 351 of them came from 120
  workflow-subagent children in one session (`session-05`): verification-before-completion 108,
  supply-chain-risk-auditor 87, fp-check 61, search-first 46, iterative-retrieval 43. The other 2
  (`workflow-authoring` and `claude-api`) came from general-purpose children in `session-03`. An
  earlier scratch analysis that found 0 Skill calls read only `session-03`'s children.
- **Injected block.** The routing block reached every Agent-tool child (42/42) through the prompt
  and no workflow child (0/597). No child received SubagentStart additional context (0/639).
- **SubagentStart hook types.** workflow-subagent 465, general-purpose 107, evidence-reviewer 33,
  source-scout 15, Explore 13, Plan 3, isolated-builder 3.
- **Negative controls.** There were no `blind-*` Claude children in the window. The blind lanes
  ran as Codex `--ignore-user-config` sessions, counted below.

## Results: Codex sessions (239, all `codex_exec`)

| Group | Sessions | Marker | Context Mode calls (sessions) | Other MCP calls | Shell calls, `rtk`-prefixed | Fetch: ctx / page opens / curl | First prompt, median |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Workers, top-level | 114 | 114 | 1,463 (86) | 52 | 440, 171 (38.9%) | 96 / 1 / 2 | 19,368 (n=107) |
| Workers, spawned sub-agents | 18 | 18 | 393 (18) | 0 | 42, 24 (57.1%) | 27 / 4 / 0 | 22,124 (n=18) |
| Negative controls (user config ignored) | 107 | 0 | 0 | 150 (built-in `codex` server only) | 110, 64 (58.2%) | 0 / 1,006 / 0 | 21,805 (n=106) |

- The catalog classification put 132 sessions in `applied`, 107 in `ignored` and none in
  `unknown`. That split equals the marker split exactly.
- **Workers overall.** 94.6% of fetches went through `ctx_fetch_and_index` (123 of 130). 88 of the
  1,856 Context Mode calls failed, and both jCodeMunch calls failed. QMD made 30 calls in 2
  sessions. Workers spawned 18 sub-agents.
- **SKILL.md reads in workers.** verification-before-completion 87, search-first 86,
  security-best-practices 39, find-skills 17, diagnosing-bugs 12, tdd 6, modern-python 5.
  find-skills is `codex_enabled: false`: it is read even though it is not listed.

## Results: skills invoke rate at capture time

`/skill-doctor` (Claude Code 2.1.283) reported these uses:

- verification-before-completion 92
- supply-chain-risk-auditor 73
- fp-check 56
- iterative-retrieval 37
- search-first 36
- property-based-testing 3
- mcp-builder, writing-for-agents and codex:codex-cli-runtime 1 each

Every other listed skill showed 0. `uses` is not windowed. On Codex, 118 of the 383 rollout
sessions on the host at 17:07Z had ignored the user config. The report now keeps them out of the
trial counts and shows them under `excluded_user_config_ignored`. Three Codex-enabled skills drop
to zero 30-day use once those sessions are out:

- iterative-retrieval: 15 reads excluded
- writing-for-agents: 2 reads excluded
- security-threat-model: 1 `$` mention excluded

No skill is a prune candidate yet: every skill is under 30 days old.

## Limitations

- **Evidence class.** This is `local_integration`. It is not an upstream test, not a model run and
  not billed cost. First-prompt tokens are the provider-returned usage recorded in the transcripts.
  Billed cost per successful task, including cache and failed attempts, is not measured here.
- **Window edges.** 11 Claude children started before the window and 28 ran past its end; 2 Codex
  sessions ran past its end. Only their rows inside the window are counted, and only children whose
  first request is inside the window have a first-prompt figure.
- **Mixed workloads.** The window mixes different workloads, and one session (`session-05`, 363
  children) dominates the workflow-subagent figures. Compare later windows by share within
  matching agent types, not by absolute counts.
- **Lexical detection.** `curl`/`wget` counts only in command position of the text a shell runs,
  optionally behind `rtk`, `sudo`, `env`, `command`, `exec` or `timeout N`. It is not a shell
  parser: other wrappers, nested quoting and `gh api` are missed. The Codex `rtk` prefix is the
  first word of the shell script.
- **Codex classification.** It needs the trial's rendered disable list in the host's user config;
  without it, sessions read as `applied` or `unknown`. A spawned sub-agent's rollout begins with
  its parent's developer messages, so its marker reflects inherited context.
- **Reproduction horizon.** The transcripts are retained by the clients (Claude Code's
  `cleanupPeriodDays`, 30 days by default). RTK prunes `hook_decisions` after 90 days. A rerun
  reproduces these groups only while both still hold the window.
- **Session ordinals.** They are assigned per run, in order of each session's earliest child row
  in the window.
