# Token-efficiency stack inside Ultracode subagents (2026-09-25)

Host: `nativestack-5975wx-20260925`, the WSL2 workstation. Measurement window: 20:47:07Z to 21:15:10Z. Catalog revision: `f5812d3f`.
Machine-readable record: [`receipt.json`](receipt.json).

## Question

Does each selected token-efficiency tool run inside an Ultracode workflow subagent? When it does, what do the tool's own lifetime counters and an exact tokenizer show?

Installing and configuring a tool does not show any saving. This run makes one claim per tool, and each claim has two parts:

- a subagent used the tool on real work, and a check against the plain baseline confirmed its answer;
- the saving comes from the tool's own counter, where the tool has one, and from an exact tokenizer comparison of the same information need.

## Method

1. **Setup.** Five missing tools were installed at their `manifests/stack.json` pins: ast-grep, codebase-memory-mcp, Context Hub, agentsview and otel-tui. Each download was checked against upstream's sha256 checksum file or npm's registry integrity.
2. **MCP servers.** Headroom, codebase-memory and QMD were registered as Claude Code user-scope MCP servers with `claude mcp add --scope user`. codebase-memory's web UI was turned off (`ui_enabled=false`).
3. **Ledger.** The private token-report ledger now reads Context Mode's stats for both clients and has the pinned `gpt-tokenizer@3.4.0` (`o200k_base`).
4. **Before snapshot.** At 20:47:07Z: `rtk gain` globally and for a dedicated worktree only, `headroom savings --json`, jCodeMunch `get_session_stats`, Context Mode stats files, `ccusage daily`, and `token_manifest.py refresh`.
5. **Workflow.** 16 Sonnet 5 workflow subagents, one per tool. Each subagent:
   - worked in a disposable worktree at `origin/main`, or in the session project root where the tool is bound to it;
   - wrote the plain baseline only with a shell redirect;
   - read only the tool's output;
   - answered from that output;
   - ran a deterministic check of the answer against the baseline.

   Three tools failed on the first attempt, each on a real constraint (see [Retained failures](#retained-failures-and-gaps)). They were rerun under that constraint.
6. **After snapshot** at 21:15:10Z. Then each baseline/tool-output pair was compared with `token_manifest.py compare`, and `child-usage.mjs` read the provider usage of every child.
7. **Fresh session.** A new headless Claude Code session (Sonnet 5) listed its MCP servers at start and called one tool on each newly registered server.

## Results

All 16 tools ran inside a subagent, and each subagent's answer passed its baseline check.

The token counts are exact (`o200k_base`). Each covers one task: the tokens the subagent would have read without the tool, minus what it actually read. They are not provider-billed savings.

| Tool | Channel in the subagent | Task | Baseline → tool output (tokens) | Removed |
| --- | --- | --- | --- | --- |
| RTK 0.50.0 | PreToolUse hook on plain Bash | 6 git/grep/ls/unittest commands | 29,986 → 3,786 | 87.4% |
| Context Mode 1.0.169 | native MCP `ctx_execute_file` | summarise a 416 KB handbook | 97,952 → 204 | 99.8% |
| Headroom 0.37.0 | MCP via MCPorter (`headroom_compress`, exact `headroom_retrieve`) | `git log --stat -150` | 237,691 → 56,939 | 76.0% |
| jCodeMunch 1.108.319 | native MCP | locate `register_file` source | 22,043 → 443 | 98.0% |
| Serena (pinned commit) | native MCP | definition and 14 call sites of `register_file` | 17,723 → 1,752 | 90.1% |
| SocratiCode 1.14.0 | native MCP `codebase_search` | explain the host-request trust rule | 16,096 → 4,832 | 70.0% |
| QMD 2.8.3 | CLI (BM25) | find the release re-pin step | 5,756 → 901 | 84.3% |
| ast-grep 0.45.3 | CLI | all `subprocess.run` calls (18 in 10 files) | 105,877 → 10,293 | 90.3% |
| codebase-memory-mcp 0.11.0 | CLI | callers of `register_file` | 22,445 → 19,635 | 12.5% |
| Repomix 1.18.1 | CLI `--compress` | two scripts, 47 functions | 17,935 → 8,799 | 50.9% |
| TOON 4.1.1 | CLI, strict round trip | 60-row table | 1,642 → 907 | 44.8% |
| MarkItDown 0.1.8 | CLI | Claude Code MCP docs page | 503,230 → 28,934 | 94.3% |
| Context Hub 0.1.4 | CLI | a Uvicorn 0.41.0 flag | 70,903 → 2,073 | 97.1% |
| ai-memory 2.4.0 | native MCP `memory_query` / `memory_status` | scoped recall (10 hits) | no baseline (retrieval) | none |
| agentsview 0.43.0 | CLI `sync` / `session list` | observe today's subagent sessions | observation only | none |
| otel-tui 0.7.5 | CLI in a pseudo-terminal, non-default ports | received one OTLP span | observation only | none |

### Upstream counters (each tool's own estimate)

| Counter | Before | After | Delta |
| --- | --- | --- | --- |
| `rtk gain --project`, this run's worktree only | 0 commands / 0 saved | 89 commands / 56,527 saved (59.3%) | **+56,527** |
| `rtk gain`, whole host (other sessions ran at the same time) | 10,790,973 saved | 10,896,793 saved | +105,820 (not attributable to this run) |
| `headroom savings --json`, lifetime | 4,097 saved / 1 call | 188,001 saved / 2 calls | **+183,904** |
| jCodeMunch `get_session_stats` in the subagent's live server | n/a | 23,643 saved over 4 calls | session value |
| jCodeMunch persistent ledger, read through a fresh process | 0 | 68 | +68 (the live session had not been written to the ledger yet) |
| Context Mode stats files, Claude, summed | n/a | n/a | +77 calls, 19,821 bytes kept out |

Headroom's own estimate (+183,904) and the exact tokenizer (180,752 removed) agree to within 2% on the same compression.

### What the run cost (provider-returned, per child)

| Workflow | Children | Output tokens | Cache-read tokens | Cache-creation tokens | Input tokens |
| --- | --- | --- | --- | --- | --- |
| E2E (16 tools) | 16 × Sonnet 5 | 556,956 | 12,116,062 | 990,205 | 396 |
| Reruns (3 tools) | 3 × Sonnet 5 | 92,237 | 1,778,590 | 173,181 | 66 |

`child-usage.mjs` reports both runs complete. Every child requested and resolved Sonnet 5, and the effort level is not recorded in the transcripts. Opus was at its weekly limit for this account.

### Fresh native session

A fresh `claude -p` session on Sonnet 5 listed these MCP servers as `connected` at start: context-mode, ai-memory, serena, jcodemunch, headroom, qmd and the claude.ai Claude Docs connector. codebase-memory was `pending` at start and connected before its call. `headroom_stats`, `qmd status` and codebase-memory `list_projects` all returned. So a new session and its subagents load the new servers without extra steps. SocratiCode is registered for this project only, and the probe ran from `/tmp`.

## Retained failures and gaps

- **Context Mode, attempt 1:** `ctx_execute_file` refused a file outside the session project root. Subagents inherit the parent session's project root.
- **Serena, attempt 1:** it is bound to the session project (`--project-from-cwd`) and has no project switch in this context.
- **Context Hub, attempt 1:** its registry has no Anthropic prompt-caching entry.
- **Codex:** no Codex worker ran. `codex exec` returned the account usage limit until 2026-09-30 23:50.
- **Headroom 0.37.0** has no `compress` CLI. Subagents in this session reached its MCP tools through MCPorter; sessions started after the registration load them natively.
- **jCodeMunch** had not written the live session to its persistent ledger when it was read.
- **Secret guard false positive:** it blocked a heredoc Python checker containing `set(...)` as `environment_dump`. Workers wrote their checkers to files instead.
- **MarkItDown** needs an `.html` extension. On a `.txt` file it exits 0 and passes the HTML through unchanged.
- **Versions differ from the pins** because another session upgraded these tools today: rtk 0.50.0 (pin 0.49.0), markitdown 0.1.8 (0.1.7), ai-memory 2.4.0 (2.3.2), mcporter 0.14.1 (0.13.13).
- **Headroom's beacon was on during the run.** Headroom 0.37.0 uploads an anonymous usage summary by default (`BEACON_DEFAULT_ON = True`), and nothing opted out at the time. So the two `headroom_compress` calls through MCPorter may have sent summaries. Since then, both the Claude user-scope registration and the token-report service set `HEADROOM_OFFLINE=1` and `DO_NOT_TRACK=1` (see `recipes/README.md`).
- **OmniRoute** was not exercised. It reroutes model traffic and needs a provider credential, which is the user's decision.
- **claude-hud and otel-tui** are interactive. otel-tui was exercised headless only.
- **The Macs:** the same coverage check was requested in issue #276, with no result yet.

## Reproduce

Follow `tools/token-report/README.md` for the ledger. The subagent prompts, each tool's commands and the quality-check commands are in `receipt.json` under `tools[].task`, `tools[].answer_excerpt` and `tools[].quality_check`. The baseline and tool-output artifacts are kept by sha256 in the private ledger and are not committed: several are third-party pages, and all of them can be regenerated from the stated commands.
