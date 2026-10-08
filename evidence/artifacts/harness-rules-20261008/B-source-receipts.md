# B. Primary-source and installed-client receipts

Collected on **2026-10-08** for G6. Exact source hashes below came from the named public pinned files; live docs were fetched through `ctx_fetch_and_index` with fresh retrieval. Local reads were limited to public launcher code, installed client code/version/help, the task documents, report outputs and selected non-secret research receipts. No client configuration, credential file, environment dump or raw log was copied.

## Installed clients and release pins

| Client | Installed observation | Published primary source |
| --- | --- | --- |
| Claude Code | `2.1.294 (Claude Code)` from the installed entrypoint; binary `<author-home>/.local/share/claude/versions/2.1.294`, 252,755,128 bytes, SHA-256 `27122ca7b624f537546fbef35b80c66370d974ff258f3d9b10ac50bb8771f262` | `anthropics/claude-code@71cdddec623889d38af14b7a489670a03186f659`; [v2.1.294 release](https://github.com/anthropics/claude-code/releases/tag/v2.1.294), published **2026-10-08T05:03:54Z** |
| Codex | `codex-cli 0.161.0` from installed entrypoint; binary `<author-home>/.codex/packages/standalone/releases/0.161.0-x86_64-unknown-linux-musl/bin/codex`, 292,309,256 bytes, SHA-256 `9a820c17865fa825d04db416818679a9d63bd72e50835c396f496e5684626c9c` | `openai/codex@979011409de0a60b52f179721948e65531d26144`; annotated tag object `7e21416b38834816c224ea0dfd135c3de94b2f15`; [rust-v0.161.0 release](https://github.com/openai/codex/releases/tag/rust-v0.161.0), published **2026-10-07T15:58:45Z** |

Version observations establish installed release identity. Source inspection establishes the named code at the release commit. A binary fingerprint is not a claim that every runtime behavior was retested.

## Pinned Claude changelog anchors

Source: [`anthropics/claude-code@71cdddec623889d38af14b7a489670a03186f659:CHANGELOG.md`](https://github.com/anthropics/claude-code/blob/71cdddec623889d38af14b7a489670a03186f659/CHANGELOG.md), SHA-256 `b60a2efb867f7de45d3dc026bdeb29b0c03a70128bc3d290889bec96451522b9`.

| Line | Release entry | Evidence |
| --- | --- | --- |
| 5–6 | 2.1.294 | Fixes instruction-form prompt/agent blocking hooks and Stop/SubagentStop judging |
| 20 | 2.1.293 | Edited synced skill descriptions reach the model |
| 30 | 2.1.293 | Plugin hook worker behavior during restarts |
| 38 | 2.1.293 | Path-scoped rules/nested CLAUDE loading for single-file Bash cat/head/tail/sed/grep |
| 114 | 2.1.292 | `claude plugin validate` behavior |
| 191 | 2.1.290 | Instruction symlink read boundaries |
| 269 | 2.1.290 | Subdirectory AGENTS attachment for @-mentioned files |
| 444 | 2.1.288 | Path-scoped rules/nested CLAUDE load on Write/Edit |
| 452 | 2.1.288 | InstructionsLoaded metadata for subagents |
| 621 | 2.1.286 | Duplicate worktree CLAUDE imports corrected |
| 640 | 2.1.286 | Output style picker improvement |
| 1150 | 2.1.281 | Settings-source restrictions forwarded to spawned sessions |
| 1249 | 2.1.281 | AGENTS support on gateways and telemetry-disabled sessions |
| 1414 | 2.1.277 | AGENTS fallback support and Project instructions selector |
| 1892 | 2.1.269 | `/output-style` in headless/cloud sessions |
| 2211 | 2.1.261 | `/skill-doctor` for unused-skill/context cost |

These older entries are cited from the **installed release's immutable October changelog**, not used as an unverified historical installation recommendation.

## Supplemental installed Claude code observations

The compiled binary at the fingerprint above contains public schema/code strings at these zero-based byte offsets. These observations prove literal/schema presence; only the accompanying pinned changelog or executed native result establishes a behavioral claim. No original source line number is invented for a compiled bundle.

| Literal or schema | Byte offset | Interpretation and limit |
| --- | --- | --- |
| `AGENTS.md` fallback description | 104707848 | Describes loading where the project has no CLAUDE.md and selection through the instruction-files option; independently consistent with changelog line 1414 |
| `instructionFiles` | 99388640 | Supported selector schema literal |
| `claude-md-or-agents-md` default assignment | 239605205 | Bundle assigns the fallback default; adjacent mapping includes managed-only, CLAUDE-only and both-file modes |
| `claude-md-and-agents-md` mapping | 239605325 | Both-file mode recognized |
| `omitClaudeMd` schema | 205765672 | Describes excluding user/project/local instruction files while retaining managed policy for a subagent |
| `keep-coding-instructions` frontmatter schema | 208420711 | Recognized style/agent field; exact prompt interaction was not independently executed |
| `SLASH_COMMAND_TOOL_CHAR_BUDGET` | 98731272 | Native skill-list budget variable exists |
| `skillListingBudgetFraction` | 99151512 | Native skill-list budget key exists |
| `--plugin-dir` | 93301590 | Native CLI plugin path option exists; installed help also advertises it |
| `--settings` | 93323672 | Native CLI settings option exists; installed help also advertises settings behavior |
| `PreToolUse`, `SubagentStop` | 94016112, 94019200 | Native hook event literals |
| `get_context_usage` control schema | 206023999 | Describes `full` as per-category token-count API calls and `summary` as last-response usage plus local estimates; default `full`. This is an interface contract, not proof that a particular `/context` response made a remote counting call. |

Current official [commands documentation](https://code.claude.com/docs/en/commands), fetched **2026-10-08**, describes `/context`. Deliverable D records the actual installed `/context` output and its native estimate/provider distinctions. No headless counter experiment was performed by this B worker.

## Pinned Codex source receipts

Every path in this table is at `openai/codex@979011409de0a60b52f179721948e65531d26144`. URLs use that commit, not `main`.

| Path and useful lines | SHA-256 |
| --- | --- |
| [`codex-rs/codex-home/src/instructions/mod.rs:43`](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/codex-home/src/instructions/mod.rs#L43) — override/default, first non-empty at 70 | `5f900d536d2a085345178e4311ab55c801ce90df50db49f15d05c4525a3b5c2e` |
| [`codex-rs/core/src/agents_md.rs:10`](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/core/src/agents_md.rs#L10) — project-root-to-cwd; budget at 68; override/default/fallback at 272 | `97427a870741b904a3f3c143f5990eaaa65b5bfa99ddac1808b2980052b5fc78` |
| [`codex-rs/core/src/agents_md_manager.rs:84`](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/core/src/agents_md_manager.rs#L84) — cache invalidation; provider refresh at 100 | `6e15ec972549b0dbdc3b64b40e04b8e88e7e28a01a9d355e17b083cecf2d59b7` |
| [`codex-rs/core/src/config/mod.rs:255`](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/core/src/config/mod.rs#L255) — default 32 KiB; project-only budget definition at 920 | `45250dde1184d339a3ceb3100f18caee86ccd04de22b5d044b03f79a17b8bc97` |
| [`codex-rs/features/src/lib.rs:1254`](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/features/src/lib.rs#L1254) — native hooks stable/default-on | `caee3c3e0385cf457b53476d3b7135de8646f7bb362142574b6443a473b07062` |
| [`codex-rs/config/src/hook_config.rs:36`](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/config/src/hook_config.rs#L36) — twelve event groups; command/MCP/placeholder handler schemas at 163 | `b7ac42b2a895a00b6aa491eee1d3eb04d8a147ba0e77e016bde42381e067d1c0` |
| [`codex-rs/hooks/src/engine/discovery.rs:159`](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/hooks/src/engine/discovery.rs#L159) — duplicate JSON/TOML warning; hooks.json at 339; unsupported prompt/agent at 637/647; hash trust at 798 | `763704f5ae5f227d186dae8f5339edd6fde4f4a54c88c8ffb5ef9ad1b5a368eb` |
| [`codex-rs/hooks/src/declarations.rs:1`](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/hooks/src/declarations.rs#L1) — bundled plugin hook declarations | `9eb3068f41ed965258195220074530d44934681da7d69b821b84e87ab76e3af1` |
| [`codex-rs/skills/src/loading.rs:21`](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/skills/src/loading.rs#L21) — discovered metadata contract | `2278998af22d9a887d50dd5704858706398d46590f1689d68079414015aa60ad` |
| [`codex-rs/ext/skills/src/loader/host.rs:164`](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/ext/skills/src/loader/host.rs#L164) — scope-dependent discovery; metadata at 352 | `a5f6ea8decd1998ca22e68a1ed4170caa31f1cb300e7a80b6dbeb0b165cbaf58` |
| [`codex-rs/ext/skills/src/host_prompt.rs:61`](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/ext/skills/src/host_prompt.rs#L61) — selected skill bodies and plugin prompt limit | `b9fbe070beb71f6b4ebcdd2d3f1593098cfd21fda5a58c1ae0f8538219682159` |
| [`codex-rs/ext/skills/src/render.rs:19`](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/ext/skills/src/render.rs#L19) — catalog budgets and approximation constant at 25 | `d8ed87dc2db37fda4f63c06f05f1f1e5324fc1e23358a7bb4007abd40f3ae932` |
| [`codex-rs/exec/src/event_processor_with_jsonl_output.rs:118`](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/exec/src/event_processor_with_jsonl_output.rs#L118) — native usage conversion; server usage update at 509; turn.completed emission at 533 | `bc296541b385f9b4ca2c28cc638e25a8d6b1332b2cd67f5a03eaa97a3d612b19` |
| [`sdk/typescript/src/events.ts:20`](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/sdk/typescript/src/events.ts#L20) — usage fields; turn.completed at 35 | `dca9d5a0c216eff99f242067814be1985c027e64bf38ab4a6b6fe5c2571a4403` |

The JSON event processor stores the latest `ThreadTokenUsage` notification and emits its `total` counters. For a fresh isolated one-turn request this is the native request total. A reused multi-turn thread can expose cumulative totals; do not assume a fresh per-turn delta merely from the event name. The fields for input, cache read, cache write, output and reasoning remain separate. This is source evidence supporting D's measurement boundary, not an additional B token measurement.

## Live official documentation fetched this month

Each URL below was actually fetched on **2026-10-08**. The HTML page and its `.md` representation were used where available. A fetch date is not a publication date or an immutable version pin. Exact details not connected to the pinned sources above are marked **UNVERIFIED at the installed version** in the main report.

| Topic | Official URL |
| --- | --- |
| Claude memory/CLAUDE/AGENTS | https://code.claude.com/docs/en/memory |
| Claude settings and key reference | https://code.claude.com/docs/en/settings ; https://code.claude.com/docs/en/settings-reference |
| Claude hooks | https://code.claude.com/docs/en/hooks |
| Claude skills | https://code.claude.com/docs/en/skills |
| Claude subagents | https://code.claude.com/docs/en/sub-agents |
| Claude plugins and manifest | https://code.claude.com/docs/en/plugins ; https://code.claude.com/docs/en/plugins-reference |
| Claude output styles | https://code.claude.com/docs/en/output-styles |
| Claude engineering guidance and commands | https://code.claude.com/docs/en/best-practices ; https://code.claude.com/docs/en/commands |
| Codex instruction discovery | https://developers.openai.com/codex/guides/agents-md |
| Codex config | https://developers.openai.com/codex/config-reference ; https://developers.openai.com/codex/config-basic |
| Codex hooks | https://developers.openai.com/codex/hooks |
| Codex skills | https://developers.openai.com/codex/skills |
| AGENTS open format | https://agents.md/ ; repository HEAD observed `d001185d792eb6402a58e4cbef1c228b309ec25d` |
| Agent Skills specification | https://agentskills.io/specification |
| GitHub rulesets and available rules | https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets ; https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets |
| GitHub schedules | https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule |
| GitHub execution logs | https://docs.github.com/en/actions/how-tos/monitor-workflows/use-workflow-run-logs |

The first official-domain Google search returned a search-access interstitial rather than useful results. The official OpenAI pages were then fetched directly before installed Codex source inspection. Those actual pages, not the unusable search or remembered guidance, supported the subsequent investigation.

## Research tooling and baseline receipts

| Surface | Revision or fingerprint |
| --- | --- |
| Working repository baseline | `native-agent-stack@8ee8b3bd796c738592e92acd94d7902db3692311` |
| Installed and repository GPT launcher | `<author-home>/.config/new-wsl-native-stack/gpt-researcher.sh` equals `tools/research/gpt_researcher.sh`; SHA-256 `af4f3a075679f00a2b10b1502fe5ebf2dbe8c1491276e66d8cd5b5f522b56af2` |
| Installed GPT Researcher checkout | `assafelovic/gpt-researcher@0957c301ed06c2a5857b834358c7227c739041d4` |
| Installed DeerFlow checkout | `bytedance/deer-flow@345f08be00c8a9495079b732a39b46aa9af1584e` |
| Installed embedded DeerFlow launcher | `<author-home>/.config/new-wsl-native-stack/deer-flow-research.sh`; SHA-256 `beefa76dfa36dfc1a768c7328d0c3412f72bb08a39b40f5d2d7363575dee276b` |
| DeerFlow native runtime readback | deerflow-harness 2.1.0; langchain-core 1.4.9; langchain-openai 1.2.1; langgraph 1.2.9; ddgs 9.14.1 |

The existing repository launcher owns provider scrubbing, loopback routing and a watchdog; it was reused. The embedded launcher was reused without service startup, package installation or configuration mutation. Supported upstream routes are the GPT Researcher CLI and DeerFlow SDK; no replacement gatherer was built. Their actual report/answer/receipt paths and retrieval failures are in [B-run-receipts.json](B-run-receipts.json).

The three specified repository decision records were inspected as prior-art leads, including their relevant disclosure/token/render sections. Their September claims and the October amendment were not substituted for live vendor evidence. Baseline layout claims in B refer specifically to `native-agent-stack@8ee8b3bd796c738592e92acd94d7902db3692311:AGENTS.md:12` and `:CLAUDE.md:1`; A owns the full inventory and last-change census.

## Corrections and unchecked boundaries

- The old Codex `core/src/project_doc.rs` URL returned 404. The pinned tree identified `core/src/agents_md.rs`; only the recovered source is cited as implementation evidence.
- Direct Python urllib access to Claude docs returned 403. The required pages had already been fetched successfully through the supported context-mode fetch route; this failure does not erase the successful source read.
- Current Claude docs' simplified Read-based descriptions are qualified by the pinned Write/Edit/Bash changelog fixes.
- Native Codex lifecycle hooks are stable/default-on; prompt/agent handlers remain unsupported in discovery despite schema placeholders.
- A schedule may be delayed or dropped; a disabled ruleset does not gate anything; a skill listing still consumes context; an eager import is not progressive disclosure.
- **UNVERIFIED:** complete automation of source-quality/SOTA judgment, complete semantic owner-quote recognition, every live rule's actual enforcement state, and unexecuted current-doc details at the requested installed versions.
- No effect on live startup or F9 is claimed. The proposal remains subject to the required owner review and command-center landing cue.

Publication copy: personal home prefixes and local session IDs are anonymized. Original sealed source SHA-256: 8fe5cfa5132b15a6631dcdfd348553828e96e635aeffc53779f80bab93d9fb0e.
