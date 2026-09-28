# Native token tools: session and new-PC handbook

Use the installed tools for the current task; setup is a one-time operation per selected client/project. This handbook covers all **24 topic repositories**: 14 context tools, nine observation tools and one optional gateway. The wider HTML catalog (`ecosystem/index.html`, generated with
`python3 scripts/build_ecosystem.py --write` -- not committed, or download it
from a `publish-catalog.yml` workflow artifact (7-day retention, `workflow_dispatch`/`v*`-tag runs only)) generates current selected-component and repository-identity counts from the canonical manifests. Those are different scopes, and catalog inclusion does not mean installed or active. Pins, exact commands and dated results remain in the [topic manifest](token-efficiency-stack.json), [component manifest](../manifests/stack.json) and [foundation receipt](../evidence/receipts/foundation-native-20260920.json).

## Persistent defaults for future sessions

The [September 21 UTC closure review](foundation-closure-20260921.md) records the
current community/SDK shortlist, selection merits across all sixteen layers,
and fresh interactive Claude context, usage, MCP and HUD observations. Read it
for a foundation decision, not as a startup prompt.

On the authoring Linux/WSL host, the native workflow is now saved in client settings, shell startup files and short global instructions. A copied startup prompt is optional. The [persistent-default receipt](../evidence/receipts/native-session-defaults-20260920.json) records the actual changes and acceptance; another PC must resolve its own paths and collect its own evidence.

| Scope | Persistent setting or behavior | Boundary |
| --- | --- | --- |
| Desktop agent and integrated terminal | Agent environment already WSL; terminal already `wsl`; both settings retained | These are independent settings. Changing the agent environment requires an app restart; this host already uses WSL |
| Desktop WSL and native Codex | Each existing home has `shell_environment_policy.set.PATH` with the native bin first and `RTK_TELEMETRY_DISABLED="1"` | Homes and native sign-ins remain separate |
| Native Claude | User `settings.json` has the same resolved PATH and RTK environment value | Existing model, permission mode, telemetry and other hooks remain intact |
| Linux shells | A small sourced defaults fragment applies before Bash's noninteractive return and after login PATH additions | No model route, credential store, index or service is selected by this fragment |
| Agent instructions | Short global AGENTS/CLAUDE pointers select installed tools when useful | The complete catalog and long prompt are not loaded at every start |
| Project context | The adopted project retains its five configured MCP servers and explicit memory/index scope | Another repository receives the global CLI/plugin defaults; it needs its own project adoption for scoped MCP indexes |
| ai-memory hooks | Upstream 2.3.2 installer refreshed eight Claude entries and seven entries in each Codex home | Capture remains allowlisted by project marker; existing Claude prompt opt-out preserved |

The two Codex homes passed a fresh upstream app-server `config/read` and actual `command/exec` from a directory with **no project configuration**. The parent PATH contained only system directories and the parent RTK flag was absent; the executed child still returned the configured native PATH first and flag `1`. No model turn was started. Login, interactive and noninteractive Bash checks also passed.

The updated hook scripts were compared against all 34 staged upstream assets. The native Codex `/hooks` review controls accepted the seven changed commands in each home; a fresh `hooks/list` returned **13/13 trusted and enabled** in both homes, with no errors. No trust-bypass flag or manual trust-store edit was used. Trust readiness is separate from observing each lifecycle event.

Fresh selected-project launches also returned the native PATH first and RTK flag `1` from an actual Context Mode subprocess in each Codex home and a diagnostic MCP child of native Claude. Claude's native stream joined **four startup hooks to four successful completions**, all exit 0. All three clients exited cleanly, with no remaining owned processes and no model turns. These initialization-only Codex streams did not expose hook completion events; neither client exposed SessionEnd completion. Those lifecycle events remain unverified by this check.

### Continuous upstream checks on GitHub

The [native token CI workflow](../.github/workflows/native-token-e2e.yml) installs pinned RTK, QMD, Repomix, TOON, MarkItDown, ast-grep, ccusage, codebase-memory-mcp, Headroom and jCodeMunch (the last two through a pinned MCPorter bridge) from their upstream release/package channels on a fresh Linux runner; see [the hosted-CI coverage note](token-efficiency-stack.md#hosted-ci-coverage-2026-09-26) for what it does not cover yet. It exercises selected inputs, exact recovery, expected failures, retained fixture state and cleanup through each tool's own commands, with this repository's checks deciding the result (local integration evidence); RTK's `rtk verify --require-all` adds its own inline filter tests. It runs automatically for changes to its tools, pins or fixtures and can also be dispatched manually. Existing catalog and evidence checks continue alongside it.

The [local clean-install receipt](../evidence/receipts/native-token-ci-local-20260920.json) retains actual arguments, returned outputs, exits and hashes for **41 commands and 14 acceptance checks**. Focused unit tests in [`tests/test_native_token_ci.py`](../tests/test_native_token_ci.py) cover rejection and failure handling. RTK's isolated fixture ledger returned `total_commands: 3`, `total_input: 124`, `total_output: 118`, `total_saved: 6`; this small fixture estimate is separate from the host's retained history. QMD has no downloaded model in this lane. The [CI guide](native-token-ci.md) gives the commands and boundaries; each run uploads sanitized evidence for 14 days.

The actual [GitHub Linux run](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/35527455997) also passed all 41 command expectations and 14 checks on September 20, 2026. Its downloaded receipt, five retained fixture artifacts and seven input hashes were verified; the [permanent hosted receipt](../evidence/receipts/native-token-ci-github-20260920.json) and [fixture outputs](../evidence/native-token-ci/20260920/) remain in Git after the temporary Actions artifact expires. This is fresh Linux CLI acceptance; native client launch acceptance is recorded separately above.

### Applying the defaults on another host

First install the selected profile with the pinned upstream recipes. Then resolve that host's native executable directory and stable inherited PATH. Set the following in each intended Codex home's `config.toml`, merging with existing settings:

```toml
[shell_environment_policy.set]
PATH = "/absolute/native/bin:/the/host/resolved/inherited/paths"
RTK_TELEMETRY_DISABLED = "1"
```

For Claude, merge the same two string values into user `settings.json` under `env`. For adopted local-process MCP servers, supply their required PATH and RTK flag through supported `env` fields. These are literal JSON/TOML values; `$PATH` and `~` do not expand there. A Linux PATH is appropriate only for Linux/WSL clients: regenerate it if switching the Desktop agent to native Windows or moving to another PC. Preserve the existing account home, provider route, model and permissions.

Use the normal Linux shell profile for terminal defaults and make its PATH prefix idempotent. Keep generated secrets out of these portable examples. Retain only a short task-routing instruction globally; project markers, collections, indexes and service URLs belong to their adopted scope.

When upgrading ai-memory, use its installed upstream `install-hooks --apply --agent AGENT --config-file TARGET --server-url URL` command with explicit native targets and existing capture choices. Review changed Codex hook commands through `/hooks`. The installer preserves unrelated hooks and writes a backup; command success does not replace trust or runtime acceptance.

No environment recreation is needed for these defaults. New sessions/processes inherit them automatically. A running stdio MCP process keeps its old environment until reconnect; use the supported MCP Restart control only when that process must inherit a changed setting immediately. Keep the current working task if its selected tools already work.

Official guidance: [Codex Windows/WSL agent and terminal settings](https://learn.chatgpt.com/docs/windows/windows-app), [Codex environment settings](https://learn.chatgpt.com/docs/config-file/config-advanced), [Claude settings](https://code.claude.com/docs/en/settings).

## Start or resume work

The [authoring-host environment receipt](../evidence/receipts/codex-session-environment-20260920.json) records a fresh native Codex app-server connecting five selected MCP servers, resolving fourteen native commands and completing five read-only calls with no model turn. It verifies the project PATH setup, not a reload of an already-running Desktop task or acceptance on a new PC.

1. Open the intended project in the intended client. Desktop, native Linux Codex and Claude may use different homes, environments and loaded connections. Keep their existing native sign-ins and model settings.
2. Read the project's short `AGENTS.md`/`CLAUDE.md` routing instructions. Open a detailed recipe only for the chosen operation; do not paste the catalog into every prompt.
3. Select one useful retrieval path. Exact identifier/location: `rg`, an original source read or Serena. Unknown code concept: SocratiCode. Indexed Markdown: QMD search then get. Large selected output: Context Mode. Use the smaller complete representation when an extra layer adds overhead.
4. After a relevant setup change, inspect connected servers with `/mcp`, then make one useful call and check its returned content. `codex mcp list` lists configuration; it does not prove that this task connected or used a tool. No installation sweep or model benchmark is needed at startup.
5. Retain the original output when compressing. Check required facts and source fidelity before relying on the result. Capture counters when reporting a meaningful change, with their actual scope.

A short project instruction can be: “Choose one suitable context tool; use scoped QMD for indexed docs, Serena for symbols and SocratiCode for conceptual code search. Preserve original output and separate native estimates from provider usage. Read `docs/token-session-handbook.md` only for setup or accounting.” Point to the actual handbook location when the project is another checkout.

## Verified Desktop continuation — September 20, 2026

The [post-restart receipt](../evidence/receipts/codex-desktop-live-20260920.json) records direct calls through the restarted Desktop task's loaded connections. All five configured MCP servers returned successful results. The current shell and Context Mode subprocess both resolved the native tool directory first; fourteen checked commands resolved inside Context Mode. This is executable discovery for fourteen commands and useful retrieval through the selected lanes, not fourteen new lifecycle or provider trials.

The native plugin inventory then exposed an empty Desktop Context Mode cache. The supported `codex plugin add context-mode@context-mode --json` command restored version `1.0.169` and its six hook definitions; the private global configuration was semantically unchanged. Restored definitions and successful direct MCP calls do not by themselves prove that every hook fired in this ongoing turn.

These are selected fields or bounded excerpts from actual upstream returns; complete private responses and their hashes are retained in the receipt.

| Actual upstream command or MCP request | Returned result | Meaning |
| --- | --- | --- |
| `codex plugin add context-mode@context-mode --json` | `pluginId=context-mode@context-mode; version=1.0.169`, exit 0 | Repairs the observed missing Desktop cache; native accounts/configuration preserved |
| jCodeMunch `order({"action":"get_session_stats","args":{}})`, selected `get_symbol_source`, stats again | `session_tokens_saved: 0 → 4970`; `session_calls: 0 → 1`; `total_tokens_saved: 54670 → 59640` | Same process; upstream estimate includes this verification retrieval |
| jCodeMunch `get_symbol_source` for the selected `parse_codex` function | `_freshness: "fresh"`; 2,255 source bytes match the original exactly | Independent AST comparison; SHA256 `da3277537bf59cb63bc0b7bd2b25f86422d8f79679d382147d72863f9dc1dfd5` |
| `rtk gain --format json` | `total_commands: 55; total_input: 18054; total_output: 16332; total_saved: 1722`, exit 0 | Retained estimate; no exact current-session partition; retention limit remains 90 days |
| `headroom savings --json` | `lifetime.tokens_saved: 0; lifetime.calls: 0`, exit 0 | Actual ledger is empty; upstream “lifetime” query is at most 30 days |
| Context Mode `ctx_stats({})` | `Without context-mode 50.3 KB`; `With context-mode 1.1 KB`; `This chat: 989 KB`; `All your work: 1.7 MB` | Identical before/after mixed historical/Claude-labelled output; current-task saved tokens unavailable. An upstream-rendered figure: upstream defines these bytes as measured diverted output, but on Claude Code the kept-out side also books `read-redirected` rows at full file size for Reads context-mode did not block ([notes](#context-mode-executor-and-session-store)); not verified avoidance or provider usage, so derive no ratios |
| SocratiCode `codebase_status({projectPath})`, then selected `codebase_search` | `Status: green; Indexed chunks: 196; File watcher: active`; search returned two scoped matches | Current retrieval works; counts are not token savings |
| Serena `find_symbol` for `parse_claude` | Function found; zero-based source lines 142–169 | Current symbol service works |
| ai-memory `memory_query` and scoped `memory_status` | Query returned two hits; `pages_latest: 40; pages_all: 123; sessions: 52; observations: 25705` | Current scoped retrieval and health; no savings counter |
| `qmd --index agent-lab-docs search 'token session setup' -c agent-lab-docs -n 3`, then selected `get ... --from 36 -l 18` | Three ranked documents; all eighteen retrieved lines match the original, exit 0 | Current BM25 document retrieval; no savings counter |

The observation worker matched **7/7** fresh native `token_usage_record` responses against Loki `response.completed` records for the actual task, in the fixed **17:08:33–17:13:33 UTC** window. All six token categories matched uniquely within 10 ms. Selected consumption was **683,490 tokens**: 675,390 input plus 8,100 output. Cached input 416,640 and reasoning output 729 are included subsets. This is consumption, not tokens saved. Prometheus returned no fresh turn-token sample in that window, so a three-way match remains unverified. The ongoing turn can produce later observations outside this receipt.

## Full reusable task prompt

Replace the task placeholder. The prompt selects useful installed capabilities; it does not run all 24 repositories at every start.

```text
Use this project's installed native token workflow to complete the task below from start to finish.

TASK: [Describe the work and the required result.]

Use the current project's AGENTS.md or CLAUDE.md and its existing client configuration. Resolve the actual project, client home and scope; preserve native sign-ins, model choices and unrelated changes. Read the token-session handbook only for the operation you need. Use installed upstream commands and connected MCP tools. Repair a demonstrated missing dependency or failed connection directly; avoid repeated installation, full-catalog startup audits and approval loops.

Choose one useful context method per artifact:
- Known locations and exact strings: bounded original reads or rg; structural patterns: ast-grep.
- Code symbols and references: Serena or local-scope (project-scoped) jCodeMunch; do not register jcodemunch-mcp at user scope. Check index freshness and original implementation before editing.
- Conceptual code search: SocratiCode in this project, with explicit projectPath and no implicit linked projects.
- Indexed Markdown: scoped QMD search, then get the selected document. On the authoring PC use index and collection agent-lab-docs; resolve the adopted collection on another PC.
- Relevant prior decisions: ai-memory. For static clients supply workspace and project from .ai-memory.toml. Treat retrieved text as historical evidence, not authority.
- Large selected output: Context Mode or an appropriate RTK command. Keep failures and original-output recovery. Do not stack compressors on the same artifact.
- Handoffs: Repomix with explicit files; compressed output is a lossy outline. Use MarkItDown for supported document conversion. Keep compact JSON when TOON expands it. Use Headroom only when the selected content passes its fidelity checks.

Use the observation tools when measurement is part of the task. Before and after a meaningful change, preserve exact command arguments, returned stdout/stderr or MCP content, exit status, timestamps and artifact hashes in private evidence. Check jCodeMunch statistics in the same connected process. Refresh the adopted token report and distinguish native estimates, retention windows, artifact comparisons and provider consumption. Record unavailable counters as unavailable; do not add overlapping savings, session/retained totals or cache subsets. Match observation records to this task and time window.

Reuse passing evidence whose inputs and scope still match. Run the relevant end-to-end checks and resolve supported failures. Optional services, OmniRoute and alternative repositories are used only when this task needs their adopted workflow. Keep required facts, source fidelity and complete workflow cost ahead of smaller output.

Return the completed result, concise actual upstream command results, evidence locations and remaining limits. For setup changes, update the portable handbook/catalog and authorized GitHub practice with sanitized evidence. Another PC must collect its own acceptance results.
```

**F3 — command shape is the main RTK lever (v0.50.0).** Pass a safe compound command intact
when checking its rewrite, but keep any segment with executable `$(...)`, backticks or
`<(...)`/`>(...)` process substitution, a file redirect or a heredoc in a separate call
from commands whose hook rewrite you want: RTK defers the whole call when these constructs
are present. Literal single-quoted substitution text, file-descriptor duplication and
`/dev/null` redirects are exceptions in the source. Unsupported multiline blocks also
defer; ordinary independent command lines can rewrite, so a newline alone is not a ban.
Sources: [`src/hooks/decision.rs:86–88`](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/hooks/decision.rs#L86-L88),
[`src/discover/lexer.rs:363–414`](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/lexer.rs#L363-L414)
and [`registry.rs:727–732, 951–1013`](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs#L727-L732)
([`rewrite_multiline_block`](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs#L951-L1013)).

For pipelines, RTK can rewrite a supported final `grep`/`rg` stage; otherwise it can rewrite
only a producer whose rule is producer-safe, with every consumer `cat`, `head` or
non-following `tail`. `gh` is not producer-safe: `gh pr view 1 | head -n 5` gets
`No rewrite for: gh pr view 1 | head -n 5`, while `gh pr view 1` becomes
`rtk gh pr view 1`. A rewritten git segment elsewhere in that call does not prove the
`gh` segment rewrote. Sources: [`registry.rs:1087–1345`](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs#L1087-L1345),
[`safe consumers:1451–1468`](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs#L1451-L1468),
[`producer gate:1761–1767`](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs#L1761-L1767)
and [`producer-safe rule test:2523`](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs#L2523).
The [recipe's five exclusions](../recipes/README.md#native-context-mode-and-hooks) still apply
per segment; choose Context Mode for large output needing processing.

## What runs automatically and what you select

“Native MCP” means available after registration and connection, with calls selected as needed. It does not mean every prompt passes through that tool. Automatic hooks/watchers require their configured process and scope. Observation tools measure or display activity; they do not themselves reduce provider consumption.

| Repository ID / upstream | Activation and useful operation | Verify or limitation |
| --- | --- | --- |
| [`rtk`](https://github.com/rtk-ai/rtk) | Explicit Codex CLI: `rtk git log -3`, as the [Codex worker lane](../recipes/README.md#codex-worker-lane)'s global `AGENTS.md` block asks (upstream's awareness text plus this catalog's exceptions; changed after `v2026.09.26.2`); configured Claude Bash hook can rewrite supported commands | `rtk gain --format json`; recover original with `rtk proxy git log -3`; Codex: `codex debug prompt-input` holds the block once |
| [`context-mode`](https://github.com/mksglu/context-mode) | Native plugin/MCP on demand; configured lifecycle hooks automatic. Codex: the user-scope server that the worker lane writes, bound to each session's own directory | `ctx_execute_file` reads the selected project file; `ctx_stats` uses this server/session scope; [executor and session-store limits](#context-mode-executor-and-session-store); Codex: `codex mcp get context-mode --json` shows `"cwd": null` |
| [`headroom`](https://github.com/chopratejas/headroom) | On-demand offline selected-artifact MCP compression/retrieval; no native prompt interception established | `headroom_compress` then `headroom_retrieve`; include recovery cost; `headroom savings --json` |
| [`jcodemunch-mcp`](https://github.com/jgravelle/jcodemunch-mcp) | Local-scope (project-scoped) native MCP: explicitly index selected code, search, retrieve returned symbol ID; [F6 scope decision](decisions/2026-09-26-token-practice-f1-f9.md#f6-jcodemunch-scope-2026-09-26) | `order` actions `get_session_stats`, `search_symbols`, `get_symbol_source`; compare exact original |
| [`qmd`](https://github.com/tobi/qmd) | On-demand CLI, named BM25 index/collection | `qmd --index "$QMD_INDEX" status`; update changed docs; search then get returned URI; over MCP, typed `lex` searches with `rerank: false` ([limits](#known-upstream-limits-behind-the-lanes)) |
| [`serena`](https://github.com/oraios/serena) | Native MCP symbols/references; project language servers | `get_current_config`, `find_symbol`; test actual Python/TypeScript/CJS file support |
| [`socraticode`](https://github.com/giancarloerra/SocratiCode) | Native MCP semantic search; automatic watcher while adopted owner runs | `codebase_health`, `codebase_status({projectPath})`, exact search; watcher behavior needs actual change evidence |
| [`ai-memory`](https://github.com/akitaonrails/ai-memory) | Native MCP retrieval; project-marker-gated lifecycle capture automatic | `memory_status`, scoped page read and fresh event metadata; durable writes deliberate |
| [`repomix`](https://github.com/yamadashy/repomix) | On-demand selected-file handoff | `repomix "$PROJECT_ROOT" --include "$SELECTED_FILES" --compress --output "$PACK_FILE"`; compressed output omits implementation details and can drop a whole multi-line definition ([limits](#known-upstream-limits-behind-the-lanes)) |
| [`toon`](https://github.com/toon-format/toon) | On-demand structured-data conversion | `toon "$INPUT_JSON" --stats -o "$OUTPUT_TOON"`; decode with `toon "$OUTPUT_TOON" --decode --strict -o "$RECOVERED_JSON"`; compare compact JSON |
| [`ast-grep`](https://github.com/ast-grep/ast-grep) | On-demand structural source search | `ast-grep run --lang javascript --pattern 'function $NAME($$$ARGS) { $$$BODY }' --json=compact --stdin < "$SOURCE_FILE"` |
| [`codebase-memory-mcp`](https://github.com/DeusData/codebase-memory-mcp) | On-demand native MCP/bridge static graph | `search_graph`, `trace_path`; use returned project/node IDs and original source |
| [`context-hub`](https://github.com/andrewyng/context-hub) | On-demand curated documentation | `chub search "python pytest" --json`, then `chub get "$DOC_ID" --lang py` |
| [`markitdown`](https://github.com/microsoft/markitdown) | On-demand selected document conversion | `markitdown "$INPUT_HTML" -o "$OUTPUT_MD"`; base installation does not include every PDF/Office extra |
| [`mcporter`](https://github.com/openclaw/mcporter) | On-demand MCP CLI bridge with explicit config | `mcporter --config "$MCPORTER_CONFIG" list socraticode --brief --no-oauth`; a listing is not a successful search, and a successful call is transport acceptance, not a token saving |
| [`ccusage`](https://github.com/ccusage/ccusage) | On-demand native history accounting | `ccusage codex daily --offline --no-cost --json --timezone UTC --config /dev/null`; select the intended native home; token-only while any model is unpriced ([recipe row](../recipes/README.md#component-catalog-install-and-check)) |
| [`agentsview`](https://github.com/kenn-io/agentsview) | Optional selected-history archive/viewer | Configure allowed source directories before `agentsview sync`; query returned project ID; refresh explicitly; add `--include-children --include-automated --include-one-shot` for worker sessions ([history recipe](../recipes/README.md#history-and-usage)) |
| [`claude-hud`](https://github.com/jarrodwatts/claude-hud) | Optional automatic Claude statusline after `/claude-hud:setup` | Inspect actual interactive Claude; not a Codex HUD or independent billing ledger |
| [`otel-tui`](https://github.com/ymtdzzz/otel-tui) | On-demand local telemetry viewer | `otel-tui --host 127.0.0.1 --grpc 24317 --http 24318`; route only a selected producer to unused ports |
| [`opentelemetry-collector-contrib`](https://github.com/open-telemetry/opentelemetry-collector-contrib) | Observation service, automatic only after configuration/start | `otelcol-contrib validate --config="$OTEL_CONFIG"`; verify actual event delivery separately |
| [`prometheus`](https://github.com/prometheus/prometheus) | Observation service, configured scraping | `promtool check config "$PROMETHEUS_CONFIG"`; `promtool query instant http://127.0.0.1:19090 up` |
| [`loki`](https://github.com/grafana/loki) | Observation service, configured log retention/query | `loki -config.file="$LOKI_CONFIG" -verify-config=true`; query exact task/writer and bounded timestamps |
| [`grafana`](https://github.com/grafana/grafana) | Optional observation UI over configured data sources | `curl --fail --silent http://127.0.0.1:13000/api/health`; healthy UI is not matched task usage |
| [`omniroute`](https://github.com/diegosouzapw/OmniRoute) | Optional explicit native-client gateway route | Owned service health and authenticated statistics; local lifecycle/preview does not establish provider acceptance |

These commands assume the corresponding installation/configuration and deliberately selected input. Use the [24-row command manifest](token-efficiency-stack.json) and [native recipes](../recipes/README.md) for complete arguments, pins, checksums and installation of each row. The [lifecycle matrix](../blueprints/token-native-focus/saturation-audit.json) records accepted, partial and unestablished stages individually.

### Context Mode executor and session store

Checked on 2026-09-26 against Context Mode 1.0.169 at the reviewed revision `6f0cc684`; the paths below are upstream files at that revision. That day upstream `main` differed from it only in `stats.json`, and no newer release existed. These are the working rules for coordinators, Agent and Workflow children and Codex workers. Upstream issue and pull-request numbers are read-only references to where upstream tracks a behaviour.

- **Code runs in a real directory, and its writes persist.** Every `ctx_execute` language except Rust runs in the project root, or in the `cwd` you pass; only the script file sits in a temporary directory (`src/executor.ts:295-312`, since v1.0.163). Rust is compiled and run inside that temporary directory whatever `cwd` says (`src/executor.ts:290-292, 406`), so give Rust code absolute project paths. The routing block (`hooks/routing-block.mjs:46, 50`) and the `cwd` parameter text (`src/server.ts:1731`) describe a discarded sandbox file system; the executor is what runs, so plan for persistent writes. Keep the policy that block carries: write deliverables with native Edit or Write (upstream #201), and run nothing destructive through `ctx_*` code, which is unsandboxed and has the server's file access (`README.md:1575`).
- **Which directory the code runs in.** On Claude Code, the PreToolUse hook fills in the caller's working directory for shell `ctx_execute` and for every `ctx_batch_execute` without a `cwd` (`hooks/core/routing.mjs:939-941, 993-995`). JavaScript and Python `ctx_execute` without a `cwd`, and every `ctx_execute_file`, run at the server's project root (`src/executor.ts:306, 321-329`). Agent and Workflow children call the parent session's server, so for them that root is the coordinator's checkout, not the child's worktree. Pass `cwd` for non-shell code. `ctx_execute_file` has no `cwd`: pass it an absolute path inside the server's project root, which covers a writer worktree at `<checkout>/.claude/worktrees/<name>` (git-ignored in this repository). Codex PreToolUse hooks can deny a call but cannot rewrite its input (`README.md:1392`), so pass `cwd` there every time.
- **Files outside the server root.** Keep no `Read(...)` allow rules. `ctx_execute_file` refuses a path outside the project root unless a `Read(...)` allow rule opts it in (`src/server.ts:1164-1209, 2118`; `README.md:1559-1573`; upstream #852). In 1.0.169 an allow rule goes through the deny matcher, which accepts a path when any of its raw, resolved or canonical forms matches (`src/security.ts:616-655, 759-781`), so an allowed tree's `..` path or outward symlink passes as well, while Claude Code's own allow rules need both a symlink and its target to match ([permissions](https://code.claude.com/docs/en/permissions)). For a file outside the root, use native Read for a small file, `ctx_index` then `ctx_search` for a large one (`ctx_index` applies the Read deny rules but not the root check, `src/server.ts:2327`), or produce and process the output inside one `ctx_execute`. Upstream's skill Workflows B and C save browser output under `/tmp` and pass it to `ctx_execute_file` (`skills/context-mode/SKILL.md:238, 254, 257`); with no allow rule that path is refused, so take the `ctx_index` form Workflow C also names. Create writer worktrees under `<checkout>/.claude/worktrees/<name>`, or run each worker as its own session in its worktree.
- **Batch command shape.** `ctx_batch_execute` puts an inline `NODE_OPTIONS='--require …'` prefix in front of each command (`src/server.ts:3786-3789`), so a command that starts with `for`, `if`, `while`, `{` or `(` fails with a shell syntax error (upstream #1117 and #925). Begin with a simple command, such as `cd "$DIR" && for ...`, or wrap the command in `bash -c '...'`. Shell code sent to `ctx_execute` is not affected.
- **MCP calls on Claude Code.** On Claude Code, context-mode 1.0.169, from any install source, records no MCP tool calls or responses and gives no external-MCP nudge. Its MCP catch-all is the bare matcher `mcp__` (`hooks/hooks.json:6, 100`), written for substring matching (`src/adapters/claude-code/hooks.ts:41-54`); on Claude Code a matcher made only of letters, digits, `_`, `-`, spaces, `,` and `|` is compared as an exact string, so `mcp__` matches no tool ([hooks](https://code.claude.com/docs/en/hooks), matcher patterns and MCP tools). The exact `ctx_execute`, `ctx_execute_file` and `ctx_batch_execute` PreToolUse entries (`hooks/hooks.json:73, 82, 91`) and the Bash, Read, Grep, WebFetch and Agent routing do run. To make an MCP result searchable, route it through `ctx_execute`, `ctx_batch_execute` or `ctx_index`. No `mcp` or `mcp_tool_call` rows in a Claude Code session database (upstream's `src/session/retrieval-marker.ts:4-8` notes the same for its own tools) and leftover `context-mode-latency-*-mcp__plugin_context-mode_*` files in the temporary directory are expected, not install faults. Add no `^mcp__` or `mcp__.*` hook of your own and edit no `hooks.json`: a PostToolUse capture keeps nothing out of context (`hooks/posttooluse.mjs:224`), and a wider PreToolUse matcher would run `pretooluse.mjs` twice for the three `ctx_*` tools.
- **Codex workers.** Codex uses the user-scope `[mcp_servers.context-mode]` entry in [`adoption/templates/codex.config.template.toml`](../adoption/templates/codex.config.template.toml): upstream `start.mjs` from the pinned npm install, with no `cwd` and `default_tools_approval_mode = "approve"`, and the plugin's own server turned off. Codex starts a server that has no `cwd` in the session's own directory, and `start.mjs` binds that directory as `CONTEXT_MODE_PROJECT_DIR` and `CLAUDE_PROJECT_DIR` (`start.mjs:38-51`; [retained comparison](../evidence/artifacts/context-mode-codex-binding-20260926/README.md)). Start each worker with its working directory, or `codex exec -C`, set to its own tree, and a main-checkout session from the repository root: the bound root is the launch directory, not the git root. Codex 0.157.1 compares a matcher made only of letters, digits, `_` and `|` exactly, one alternative at a time ([`codex-rs/hooks/src/events/common.rs:137-152, 169-173`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/hooks/src/events/common.rs#L137-L173)), so the plugin's PreToolUse matcher never matches an MCP tool name; upstream notes that its literal `mcp__` is "a no-op under exact-matcher mode but kept for parity" (`src/adapters/codex/index.ts:80-99`). Project `Bash(...)` denies therefore reach `ctx_*` calls only inside the server, through the `CLAUDE_PROJECT_DIR` that `start.mjs` sets (`src/server.ts:1111-1120`). Never run `context-mode upgrade` or `ctx_upgrade`: they remove the user-scope entry (`src/adapters/codex/index.ts:879-887`).
- **Session memory is a recent window, not wave continuity.** The store keys a session on the Claude Code session id taken from the `transcript_path` file name (`hooks/session-helpers.mjs:364-368`). Claude Code runs the same hooks for Agent and Workflow children, adding `agent_id` and `agent_type`, and names a subagent's own transcript separately as `agent_transcript_path`, while `transcript_path` stays the main session's ([hooks](https://code.claude.com/docs/en/hooks)); children's events therefore land in their parent's session. A session keeps at most 1,000 events (`src/session/db.ts:639`). At the cap the store deletes the row with the lowest `priority` value first (`src/session/db.ts:970-974`), and the capture hooks write 1 for their most critical rows, such as prompts, rules, file edits and tasks (`src/session/extract.ts:24`), so those leave first; upstream tracks the ordering as #1156, with fix pull requests #1158 and #1181. `event_count` counts every insertion (`src/session/db.ts:976-979`); count the stored rows (`COUNT(*)`) to see what is kept. Use `ctx_search(sort: "timeline")` only as a recent-window aid, and carry a wave's continuity in receipts, pull requests, handoffs and ai-memory.
- **Retention.** Each fresh `startup` runs `cleanupOldSessions(7)` on the project's store (`hooks/sessionstart.mjs:296-306`; Codex `hooks/codex/sessionstart.mjs:98-104`), which selects sessions by their start time (`src/session/db.ts:1096-1097`), so a session that started more than seven days earlier is deleted even while it is still active; upstream tracks this as #1140, with fix pull request #1143. `/clear`, resume and compaction do not run the sweep. Start a fresh session, or run `/clear`, for each wave, and do not stretch one session id across days with `--continue` or `/resume`.
- **Compaction and snapshots.** On Claude Code, compaction injects the routing block and a `<session_knowledge>` guide built from the stored events, not the XML resume snapshot; the snapshot is injected only when `/resume` hands over a new session id (`hooks/sessionstart.mjs:285-288`). On Codex, compaction injects the guide and also appends the stored snapshot (`hooks/codex/sessionstart.mjs:66-95`). The guide shortens individual entries but has no overall size limit. The snapshot builder keeps `maxBytes` for compatibility and ignores it (`src/session/snapshot.ts:30, 470`; reference-based since upstream commit `a0b53c0`), and it copies decisions untruncated, so plan for no fixed snapshot size; the README's "≤2 KB" tiered snapshot (`README.md:1294, 1305`) describes the earlier design. The guide's "Last Request" section reads events of category `prompt` (`hooks/session-directive.mjs:59`), while the prompt hook stores `user-prompt` (`hooks/userpromptsubmit.mjs:64`), so on Claude Code context-mode's post-compaction injection carries no copy of the last prompt; on Codex it arrives through the snapshot.
- **No settings, and no purge workaround.** The event cap, the eviction order and the retention period are constants in the code, and the snapshot has no size limit. `CONTEXT_MODE_DIR` is the one storage setting that both the hooks and the server honor; `CONTEXT_MODE_SESSION_SUFFIX` changes only the per-project session file names (the database, the events file and the cleanup flag, `hooks/session-helpers.mjs:78-92, 391-427`). Do not set `CONTEXT_MODE_DATA_DIR` (upstream #649; not in the README): the server honors it but the Claude Code hooks do not, so it splits the store. `ctx_purge` permanently deletes a session's or the project's records; upstream reserves it for an explicit user request and advises against purging to free capacity (`src/server.ts:4465`).
- **`ctx_stats` figures.** `ctx_stats` renders upstream estimates for this server's session and for retained history. Quote any of its figures as an upstream-rendered figure: upstream defines the Without/kept-out bytes as measured diverted output (`src/session/analytics.ts:1025-1034, 2173-2180`), but on Claude Code they also include `read-redirected` rows that book a large file's full size for a Read that context-mode only advised against and did not block (`hooks/core/routing.mjs:848-862`; `hooks/posttooluse.mjs:94-141`; upstream #950, comment 5412624311). Such a figure is not verified avoidance and not provider usage, so derive no ratios from it; savings claims use exact artifact comparisons and native provider counters ([counter limits](token-practice.md#why-the-context-mode-lifetime-dollar-line-can-be-small)).

### Token lanes carried into subagents

The following sentences are the source of truth for the portable
[`token-lanes-block.md`](../adoption/hooks/claude/token-lanes-block.md) carrier and its role blocks.
Tool contracts cite upstream; selection thresholds and accounting rules are local
policy, as recorded in the [carrier decision](decisions/2026-09-27-token-lanes-subagent-start.md).

The hook chooses one block by the exact `agent_type` value. A shipped role whose `tools:` line is an explicit
allowlist gets a role block that names only the lanes that allowlist grants: an allowlist admits only the tools it
lists ([sub-agents](https://code.claude.com/docs/en/sub-agents)) and ToolSearch returns only granted tools, so the
full block told these roles to load tools they cannot call
([role-matched addendum](decisions/2026-09-27-token-lanes-subagent-start.md#addendum-2026-09-27-role-matched-blocks)).
A role block copies its lines from the full block below, except for the role variants listed after the table.
Types that inherit their tools keep the full block. The
[text contract test](../tests/test_token_lanes_subagent_start.py) checks, for every shipped agent with a `tools:`
line, that each lane tool its injected text names or needs (ToolSearch, Bash for the RTK line, and the Context Mode, Serena, jCodeMunch, SocratiCode, QMD, ai-memory, codebase-memory and Headroom tools) is in that line; a tool the text only prohibits, such as WebFetch, is not checked.

| `agent_type` | Block | Lines, in order |
| --- | --- | --- |
| `stack-researcher` | [`token-lanes-block.researcher.md`](../adoption/hooks/claude/token-lanes-block.researcher.md) | researcher bootstrap, fetch, `ctx_search`, output, RTK, researcher code line, QMD and ai-memory, TOON, one lane |
| `stack-verifier` | [`token-lanes-block.verifier.md`](../adoption/hooks/claude/token-lanes-block.verifier.md) | verifier bootstrap, `ctx_search`, output, RTK, TOON, one lane |
| `evidence-reviewer`, `security-reviewer` | [`token-lanes-block.reviewer.md`](../adoption/hooks/claude/token-lanes-block.reviewer.md) | reviewer and builder bootstrap, `ctx_search`, output, reviewer and builder code line, memory line, TOON, one lane |
| `isolated-builder` | [`token-lanes-block.builder.md`](../adoption/hooks/claude/token-lanes-block.builder.md) | reviewer and builder bootstrap, `ctx_search`, builder output, RTK, reviewer and builder code line, memory line, TOON, one lane |
| `source-scout` | [`token-lanes-block.scout.md`](../adoption/hooks/claude/token-lanes-block.scout.md) | scout RTK, TOON, one lane |
| `semantic-evidence-reviewer` and every `blind-*` type | none (0 bytes) | none |
| any other value, or none: `general-purpose`, Workflow children without an `agentType`, `Explore`, `landscape-sweep-worker`, teammates, plugin-scoped names | [`token-lanes-block.md`](../adoption/hooks/claude/token-lanes-block.md) | every line below |

Role variants, each replacing the full-block line on the same topic:

- Researcher bootstrap (no SocratiCode, codebase-memory or Headroom grant): Load deferred token tools in ONE ToolSearch call before first use: "select:mcp__plugin_context-mode_context-mode__ctx_execute,mcp__plugin_context-mode_context-mode__ctx_batch_execute,mcp__plugin_context-mode_context-mode__ctx_search,mcp__plugin_context-mode_context-mode__ctx_fetch_and_index,mcp__serena__find_symbol,mcp__serena__find_referencing_symbols"; append task-needed ids to that same call: mcp__jcodemunch__route,mcp__jcodemunch__menu,mcp__jcodemunch__order,mcp__qmd__query,mcp__qmd__get,mcp__ai-memory__memory_query. ToolSearch returns only tools the agent is granted. Select names exposed by the active client.
- Verifier bootstrap (Context Mode only; its body names `ctx_execute_file`): Load deferred token tools in ONE ToolSearch call before first use: "select:mcp__plugin_context-mode_context-mode__ctx_execute,mcp__plugin_context-mode_context-mode__ctx_batch_execute,mcp__plugin_context-mode_context-mode__ctx_search"; append task-needed ids to that same call: mcp__plugin_context-mode_context-mode__ctx_execute_file. ToolSearch returns only tools the agent is granted. Select names exposed by the active client.
- Reviewer and builder bootstrap (no fetch, QMD, codebase-memory, Headroom or jCodeMunch `menu` grant): Load deferred token tools in ONE ToolSearch call before first use: "select:mcp__plugin_context-mode_context-mode__ctx_execute,mcp__plugin_context-mode_context-mode__ctx_batch_execute,mcp__plugin_context-mode_context-mode__ctx_search,mcp__serena__find_symbol,mcp__serena__find_referencing_symbols"; append task-needed ids to that same call: mcp__jcodemunch__route,mcp__jcodemunch__order,mcp__socraticode__codebase_search,mcp__ai-memory__memory_query. ToolSearch returns only tools the agent is granted. Select names exposed by the active client.
- Builder output (the builder starts in the coordinator's working directory and works in the owned worktree, per `isolated-builder.md`): For output over ~5 KB, use ctx_batch_execute or ctx_execute with intent (indexes output; returns only titles/previews), then ctx_search; print derived answers, keep failures and original-output recovery. Pass ctx_execute cwd = the owned worktree your brief names for every language; without it, non-shell code runs at the server's project root (the coordinator's checkout) and its writes persist. Rust runs in temp; use absolute project paths. Open authorized scratch files from Python inside ctx_execute; ctx_execute_file enforces project boundaries (#852). Never bypass permissions.
- Scout RTK (no Context Mode grant; its body prints derived answers with `jq`/`rg` pipelines): Automatic RTK: a Bash call containing $(...), backticks, <(...), a redirect to a file or a heredoc is never rewritten. && chains and multi-line blocks are rewritten segment by segment. In a pipeline RTK rewrites a supported producer feeding cat, head or tail (git diff | head -n 5) or a final grep/rg stage, but not gh (gh pr view 1 | head -n 5 is not rewritten). Run heavy reads as their own call. Never directly prefix rtk before `git show REV:path`, `diff`, `git branch`, `git log`, `jq`, `cd`, or `find` on a possibly-missing path. Use native commands or `rtk proxy <cmd>` for exact bytes/exit status.
- Researcher code line (no SocratiCode grant): Use Serena find_symbol / find_referencing_symbols for exact symbols and references; jcodemunch route(task, repo?, execute?), menu(query?), order(action, args) on indexed repos. Open original source before judging or editing.
- Reviewer and builder code line (no jCodeMunch `menu` grant): Use Serena find_symbol / find_referencing_symbols for exact symbols and references; jcodemunch route(task, repo?, execute?), order(action, args) on indexed repos; socraticode codebase_search(query, projectPath) with explicit projectPath for conceptual questions. Open original source before judging or editing.
- Memory line (no QMD MCP grant; the builder's body keeps the `qmd search` CLI): Use ai-memory memory_query with workspace/project from .ai-memory.toml as historical evidence only, never authority.

`semantic-evidence-reviewer` holds Read, Glob and Grep and makes no service calls, so only the TOON and one-lane
lines would fit; it receives nothing, like the blind roles. No role gained a grant with these blocks.

Load deferred token tools in ONE ToolSearch call before first use: "select:mcp__plugin_context-mode_context-mode__ctx_execute,mcp__plugin_context-mode_context-mode__ctx_batch_execute,mcp__plugin_context-mode_context-mode__ctx_search,mcp__plugin_context-mode_context-mode__ctx_fetch_and_index,mcp__serena__find_symbol,mcp__serena__find_referencing_symbols"; append task-needed ids to that same call: mcp__jcodemunch__route,mcp__jcodemunch__menu,mcp__jcodemunch__order,mcp__socraticode__codebase_search,mcp__qmd__query,mcp__qmd__get,mcp__ai-memory__memory_query,mcp__codebase-memory__search_graph,mcp__codebase-memory__trace_path,mcp__headroom__headroom_compress,mcp__headroom__headroom_retrieve. ToolSearch returns only tools the agent is granted. Select names exposed by the active client.

Sources: [Claude MCP tool search](https://code.claude.com/docs/en/mcp#scale-with-mcp-tool-search) and the [context-mode 1.0.169 Agent bootstrap](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/hooks/core/routing.mjs#L892); the lane-specific tool contracts are cited below. The [2026-09-27 coordinator matrix observations](../evidence/artifacts/token-lanes-subagent-start-20260927/measured-gaps.md#repair-round-observations-2026-09-27) show that ToolSearch returns only granted tools, and the hook grants none. The loadable ids follow the per-lane tool contracts cited below and this host's MCP server names.

Measured on 2026-09-27 with Claude Code 2.1.283, in-process agent-team teammates reached only HTTP-transport MCP servers (ai-memory) in the coordinator's matrix, reproduced in an interactive lead; the lead reached the requested stdio servers. The TOKEN LANES carrier still reached those teammates ([measurement boundary](../evidence/artifacts/token-lanes-subagent-start-20260927/measured-gaps.md#repair-round-observations-2026-09-27)).

Fetch pages with ctx_fetch_and_index; batch requests with concurrency for several URLs, then quote with ctx_search. Do not use WebFetch for evidence: it answers from a small fast model's reading of the page.

Sources: the [context-mode 1.0.169 fetch contract and batch schema](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts#L3423-L3478) stores fetched content for retrieval through `ctx_search`; `requests` accepts `{url, source?}` entries and `concurrency` accepts 1-8 (use more than 1 for parallel fetching). The [Claude Code WebFetch contract](https://code.claude.com/docs/en/tools-reference#webfetch-tool-behavior), read 2026-09-27 and consistent with the supplied installed 2.1.283 description, documents model-mediated extraction rather than ordinary page-text returns. Routing evidence fetches through context-mode is this carrier's policy; it does not establish model compliance. `ctx_fetch_and_index` uses HTTP fetching and cannot render JavaScript-dependent pages.

Use ctx_search with specific queries and limit <=3.

Source: context-mode 1.0.169 [`ctx_search` schema, L88-94](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/search/ctx-search-schema.ts#L88-L94) defaults to 3 results per query. Keeping that limit or lower is local retrieval policy, not a byte-size guarantee. The [coordinator's peer smoke-3 observation](../evidence/artifacts/token-lanes-subagent-start-20260927/measured-gaps.md#repair-round-observations-2026-09-27) reports 11/20 `ctx_search` and 27/52 `ctx_execute` results over 5 KB; retrieval needs containment too.

For output over ~5 KB, use ctx_batch_execute or ctx_execute with intent (indexes output; returns only titles/previews), then ctx_search; print derived answers, keep failures and original-output recovery. Pass ctx_execute cwd = your working directory for every language; without it, non-shell code runs at the server's project root (the coordinator's checkout) and its writes persist. Rust runs in temp; use absolute project paths. Open authorized scratch files from Python inside ctx_execute; ctx_execute_file enforces project boundaries (#852). Never bypass permissions.

Sources: context-mode 1.0.169's [executor, `src/executor.ts` L295-312](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/executor.ts#L295-L312) runs code at `cwdOverride ?? projectRoot` (#788), and the [handler at L1822](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts#L1822) passes `cwd` for every language. The [Claude routing hook, L939-941](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/hooks/core/routing.mjs#L939-L941) already pins shell calls to the caller's directory. The original carrier's "server is bound to the main checkout" is correct for non-shell child calls without `cwd`; the schema's shell-only wording at `src/server.ts:1731` is stale. [Rust's execution branch](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/executor.ts#L290-L292) still runs in the temporary directory, so use absolute project paths there. The [`intent` contract](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts#L1733-L1740) enables indexed previews; [execution guidance](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts#L1675-L1690) retains printing derived answers. The measurement counter uses strictly over 5,120 bytes, whereas this revision's [`intent` threshold is 5,000 bytes](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts#L1979-L1980); neither is a hard result-size cap. File boundaries remain governed by [context-mode security](https://github.com/mksglu/context-mode/blob/v1.0.169/README.md#security) and [#852](https://github.com/mksglu/context-mode/issues/852). Python opens are for paths the task already authorizes; a refused read requires checking the documented permissions, not switching tools to evade them.

Automatic RTK: a Bash call containing $(...), backticks, <(...), a redirect to a file or a heredoc is never rewritten. && chains and multi-line blocks are rewritten segment by segment. In a pipeline RTK rewrites a supported producer feeding cat, head or tail (git diff | head -n 5) or a final grep/rg stage, but not gh (gh pr view 1 | head -n 5 is not rewritten). Run heavy reads as their own call. Never directly prefix rtk before `git show REV:path`, `diff`, `git branch`, `git log`, `jq`, `cd`, or `find` on a possibly-missing path. Use native commands or `rtk proxy <cmd>` for exact bytes/exit status; process large results in ctx_execute.

Sources: RTK 0.50.0, tag commit `1d87b8e719ce0a50c223cd93ca64dd16921f9aec`. [`src/hooks/decision.rs` L86-88](https://github.com/rtk-ai/rtk/blob/1d87b8e719ce0a50c223cd93ca64dd16921f9aec/src/hooks/decision.rs#L86-L88) leaves a call containing any of those constructs unrewritten; [`rewrite_multiline_block`, `src/discover/registry.rs` L951-1013](https://github.com/rtk-ai/rtk/blob/1d87b8e719ce0a50c223cd93ca64dd16921f9aec/src/discover/registry.rs#L951-L1013), added by [rtk-ai/rtk#3319](https://github.com/rtk-ai/rtk/pull/3319) (commit [`fc8054eb`](https://github.com/rtk-ai/rtk/commit/fc8054eb0b357d32cb0457094d142de52c3db0e7)), rewrites each line; [L1087-1345](https://github.com/rtk-ai/rtk/blob/1d87b8e719ce0a50c223cd93ca64dd16921f9aec/src/discover/registry.rs#L1087-L1345) rewrite pipeline stages and `&&`, `||` and `;` segments. The [carrier receipt](../evidence/artifacts/token-lanes-subagent-start-20260927/README.md) retains 17 inputs run on 2026-09-27 through both `rtk hook check` and the `rtk hook claude` PreToolUse hook that the Claude template runs, with identical results: `git status` and `git diff --stat` on two lines came back as `rtk git status` and `rtk git diff --stat`; `cd /tmp` then `git status` as `cd /tmp` and `rtk git status`; `git diff | head -n 5` as `rtk git diff | head -n 5`. A block with `$(...)` on one line, a heredoc and `gh pr view 1 | head -n 5` came back unchanged. A block of `echo` lines is never rewritten because `echo` has no RTK rule, so it cannot test multi-line handling. The named exclusions are local routing policy, with this catalog's [exactness exceptions and retained RTK checks](../recipes/README.md#native-context-mode-and-hooks).

Use Serena find_symbol / find_referencing_symbols for exact symbols and references; jcodemunch route(task, repo?, execute?), menu(query?), order(action, args) on indexed repos; socraticode codebase_search(query, projectPath) with explicit projectPath for conceptual questions. Open original source before judging or editing.

Sources: [Serena symbol tools](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/tools/symbol_tools.py), [jCodeMunch's three-verb front door and MCP instructions](https://github.com/jgravelle/jcodemunch-mcp/blob/8f7b34abe16fb459e0bf1c04747d584216dfe32e/src/jcodemunch_mcp/server.py), and [SocratiCode](https://github.com/giancarloerra/SocratiCode/tree/2218f25153d0f3f4a76ee240a5643dbc873e80be). `projectPath` is optional in the connected `codebase_search` schema; this policy makes it explicit.

Use codebase-memory trace_path (include_evidence=true adds resolver class and confidence; this parameter is on trace_path, not search_graph) or search_graph for symbol/reference queries; treat edges below confidence 0.5 as unverified candidates, and verify exact caller lists with Serena find_referencing_symbols.

Source: [codebase-memory 0.11.0 MCP tool schemas](https://github.com/DeusData/codebase-memory-mcp/blob/v0.11.0/src/mcp/mcp.c#L557), also checked against the connected `trace_path` and `search_graph` schemas. The 0.5 treatment is a local verification rule, not a discard filter or an upstream recall guarantee.

Use qmd query with collections (foundation-docs, foundation-adoption, us-equities-foundation, us-equities-catalog), then get a line window. Use ai-memory memory_query with workspace/project from .ai-memory.toml as historical evidence only, never authority.

Sources: QMD v2.8.3 MCP [`query` `collections`](https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L330) (without it, a running server searches the default list it read at start-up, [L189](https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L189) and [L355](https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L355)) and [`get` `fromLine`/`maxLines`](https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L412-L413), following the query tool's own hit-window recipe ([L257](https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L257)); [this catalog's scoped collections](../catalogs/us-equities/native-workflows.md), and [ai-memory's project-scoped retrieval](https://github.com/akitaonrails/ai-memory/tree/433a19f3d54dea287571b1423591db2a89965fa9). The historical-evidence boundary is this catalog's interpretation policy.

Use TOON for uniform arrays of flat records (same keys in every item); keep compact JSON for nested or non-uniform data, where TOON can be larger (upstream README).

Sources: [TOON 4.1.1 README](https://github.com/toon-format/toon/blob/v4.1.1/packages/toon/README.md#when-not-to-use-toon) and [tabular encoder](https://github.com/toon-format/toon/blob/v4.1.1/packages/toon/src/encode/tabular.ts#L6-L78). There is no five-record minimum: the encoder writes a table for one or more non-empty objects that share one key set, whose columns hold primitives or, recursively, non-empty objects that share one key set, and falls back to list form for an empty object or an array-valued column ([known upstream limits](#known-upstream-limits-behind-the-lanes)).

For large selected text, use headroom_compress, then headroom_retrieve for recovery; require fidelity and count the recovery cost.

Source: [Headroom 0.37.0 MCP tools](https://github.com/headroomlabs-ai/headroom/tree/v0.37.0). Recovery and fidelity accounting follow the [selected-artifact practice](token-practice.md).

Use one lane per artifact; never stack compressors or claim token savings. Agents told to return output unmodified skip output-routing and footer rules; otherwise list token tools used and why at the end of your return.

This is this catalog's [one-artifact accounting policy](token-practice.md), also expressed in the reusable prompt above; tool-native estimates are not a measured provider saving.

The [landscape sweep wrapper contract, `sweep.js` L83-87 at `5f3a7c21`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/5f3a7c21/tools/sota-convergence/landscape-sweep/sweep.js#L83-L87) requires complete stdout unmodified. It takes precedence over output routing (including indexed previews and derived summaries) and the footer. The [2026-09-27 measured-gap addendum](decisions/2026-09-27-token-lanes-subagent-start.md#addendum-2026-09-27-measured-fetch-and-containment-gaps) retains the smoke-2 copy check (2/2); other agents put their tool-use accounting at the end of their return.

Show evidence before a success claim: the command and what it returned, or the file:line read (code.claude.com best practices). Research upstream first with the installed search-first skill before writing custom code. Source: skillOverrides in adoption/templates/claude.settings.template.json.

Sources: the evidence sentence follows [Claude Code best practices, L52](https://code.claude.com/docs/en/best-practices.md) ("the command it ran and what it returned", read 2026-09-28). The carrier names no verification step or skill: the [Opus 5 prompting guide, L61 and L81](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5.md), which the [Opus 5.5 guide, L9](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5.md) carries forward, says to remove explicit verification instructions, and [prompting best practices, L780](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices.md) makes Opus 5 the exception to self-check prompts ([verification-line addendum](decisions/2026-09-27-token-lanes-subagent-start.md#addendum-2026-09-28-verification-line)). Already installed: [`skillOverrides` in `adoption/templates/claude.settings.template.json`](../adoption/templates/claude.settings.template.json) sets `search-first` to `name-only`. It is adopted; this hook adds no skill dependency and changes no setting.

### Known upstream limits behind the lanes

These routing rules, added 2026-09-27, stay outside the carrier text above. Each answers a limit that the pinned upstream source shows or a retained receipt recorded; the linked recipe rows hold the commands.

- **QMD.** Over MCP at v2.8.3, `query` expands plain text with a model and reranks by default. For a lexical lane, pass `searches: [{"type": "lex", "query": "..."}]`, the named `collections` (an array), a small `limit` and `rerank: false`, then `get` a bounded range ([MCP tool parameters](https://github.com/tobi/qmd/blob/v2.8.3/README.md#mcp-tool-parameters)). The catalog index holds only the two us-equities collections, so adoption and new-machine questions, such as the release re-pin step, are answered by a bounded read of `adoption/update.md` ([Codex run correction](../evidence/artifacts/token-e2e-codex-20260926/README.md#correction-to-296)). Before a scheduled update, check that every collection root exists, and afterwards compare a returned passage with disk ([#989](https://github.com/tobi/qmd/issues/989), [#991](https://github.com/tobi/qmd/issues/991); [document recipe](../recipes/README.md#documents-and-selected-artifacts)).
- **codebase-memory.** Index the selected repository explicitly. `trace_path` leaves out tests and resolver evidence by default ([v0.11.0 `trace_path` schema](https://github.com/DeusData/codebase-memory-mcp/blob/v0.11.0/src/mcp/mcp.c#L532-L560)), and `search_code` is a graph-ranked text search, so a literal hit can be a mention rather than a call ([`search_code` schema](https://github.com/DeusData/codebase-memory-mcp/blob/v0.11.0/src/mcp/mcp.c#L632-L659)). Before reporting a complete caller set, request `include_evidence` (and `include_tests` when tests count), keep edges below 0.5 as candidates and check each against the original source or Serena ([static code graph](../recipes/README.md#static-code-graph)).
- **Repomix.** `--compress` drops a Python definition whose signature spans several lines, without notice ([v1.18.1 `PythonParseStrategy.ts` L81-86](https://github.com/yamadashy/repomix/blob/v1.18.1/src/core/treeSitter/parseStrategies/PythonParseStrategy.ts#L81-L86)); both E2E receipts lost `status_body`. Route exact-definition, signature and inventory tasks to an uncompressed pack or the original source, and count that recovery read.
- **TOON.** The flat-record wording above and the preregistered five-row metric are local selection policy. 4.1.1 has no row minimum: it encodes an array as a table when its objects are non-empty and share one key set, and each column holds only primitives or, recursively, non-empty objects that share one key set. An empty object, or a column holding arrays, falls back to list form ([`tabular.ts` L6-78](https://github.com/toon-format/toon/blob/v4.1.1/packages/toon/src/encode/tabular.ts#L6-L78)). Choose by exact encoded size and a value-equal strict decode, and keep the original JSON otherwise: a root string that starts with U+FEFF does not survive a round trip (open [#339](https://github.com/toon-format/toon/issues/339)).
- **Headroom.** Use it only when the compressed text keeps the facts the task needs. Report compression, the response envelope and any recovery separately, because a task that needs the full original pays for compression and full retrieval, which can exceed the original ([laptop run](../evidence/artifacts/token-e2e-ultracode-laptop-20260926/README.md#what-baseline_kind-means)). Through MCPorter, pass `--server` with `--name`, or a positional argument becomes the server selector ([MCPorter row](../recipes/README.md#component-catalog-install-and-check)).
- **Serena and SocratiCode.** A passing Python fixture does not establish complete references in other languages or paths. In the laptop run, Serena's TypeScript server missed six of eight call sites of a function under `.claude/` until an explicit `.claude` include, because TypeScript's default include skips dot-directories; SocratiCode's semantic search skips dot-directories while `INCLUDE_DOT_FILES` is `false` ([laptop run](../evidence/artifacts/token-e2e-ultracode-laptop-20260926/README.md#retained-failures-and-gaps); [v1.14.0 Indexing Behaviour](https://github.com/giancarloerra/SocratiCode/blob/v1.14.0/README.md#indexing-behaviour)). Check project inclusion for the language and path before relying on a complete reference or search result, and read known excluded files directly.
- **Context Hub, MarkItDown and ast-grep.** Check a curated document's `metadata.versions` before accepting it. Give MarkItDown the input type (`-x html`) when the extension is not the format's own, and qualify each optional extra a workload needs. Run ast-grep from a directory with no unreviewed `sgconfig.yml` above it, and check `outline` or YAML-rule tasks against the original source. The [component catalog](../recipes/README.md#component-catalog-install-and-check) rows carry the sources.

## Choose the new-PC profile and install once

Clone [the canonical repository](https://github.com/seathatflowsinourveins/native-agent-stack), select a reviewed revision, and record `git rev-parse HEAD`. Read [adoption](../adoption/README.md), its [manifest](../adoption/manifest.json) and [update protocol](../adoption/update.md). Linux/WSL2 x86_64 is the accepted portability target; other hosts need matching assets and their own checks.

| Profile | Install/verify through its native recipes |
| --- | --- |
| `foundation-cpu` | Codex, Claude, Context Mode, RTK, QMD BM25, scoped ai-memory, MCPorter; [CPU setup](../recipes/README.md#native-context-mode-and-hooks) |
| `semantic-rag` | Add local Qdrant, compatible vLLM/model and SocratiCode; [foundation setup](foundation-stack.md#local-semantic-code-search-and-exact-symbols). Serena is selected separately for symbols. |
| `observability` | Add Collector/Prometheus/Loki/Grafana and selected alert tools; [backend setup](../observability/backends/README.md). Keep loopback endpoints and exact producer scope. |

Run the nonmutating prerequisite report for the chosen profile; it reports missing commands, not installations or live acceptance:

```sh
uv run --no-project --python 3.13 python scripts/adoption_status.py --profile foundation-cpu --json
```

Use [owned installation recipes](../adoption/lifecycle.md) for new prefixes and rollback. Set absolute private `STACK_HOME` and project paths first. This selected QMD example refuses an existing prefix; do not rerun it against a working installation:

```sh
(
  set -eu
  : "${STACK_HOME:?Set an absolute private stack location}"
  case "$STACK_HOME" in /*) ;; *) exit 2 ;; esac
  prefix="$STACK_HOME/tools/qmd-2.8.3"
  test ! -e "$prefix"
  npm install --global --prefix "$prefix" @tobilu/qmd@2.8.3
  "$prefix/bin/qmd" --version
)
```

For selected Python tools, use separate owned uv tool directories; the upstream package specifications are `uv tool install jcodemunch-mcp==1.108.319`, `uv tool install --python 3.13 'headroom-ai[mcp]==0.37.0'` and `uv tool install markitdown==0.1.8`. Installing jcodemunch-mcp does not choose its MCP scope: opt it into the selected project at local scope, following the [Claude profile addendum](decisions/2026-09-23-claude-user-profile.md#addendum-2026-09-25-jcodemunch-registers-per-project-not-at-user-scope). Apply the lifecycle guide's `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` guards before installation. Archive tools use upstream release assets and their published checksum, as in the [archive procedure](../recipes/README.md#official-release-archives). Preserve required, reviewed package postinstall behavior.

The native Context Mode plugin setup below is reviewed at `6f0cc6841c687e754059f36714a11233fda1a02b`: a reviewed revision, not a pin both clients enforce. Codex's `--ref` checks that commit out when it adds the marketplace. A Claude marketplace source takes a branch or tag and never a commit, and the former `@<commit>` form exited 1 on Claude Code 2.1.281 ([retained runs](../evidence/artifacts/community-sweep-20260924/plugin-marketplace-refs.json)). The Claude commands therefore take no ref and install the default-branch head, and the last command compares the installed `gitCommitSha` with the reviewed revision. It accepts a different installed revision by content only: GitHub's compare API (`gh api`, signed in at [bootstrap step 3](../adoption/bootstrap.md)) must report it `ahead` of the reviewed revision with `stats.json` as the only changed file, which is what upstream's default branch has added since the review:

```sh
codex plugin marketplace add mksglu/context-mode --ref 6f0cc6841c687e754059f36714a11233fda1a02b --json
codex plugin add context-mode@context-mode --json
codex features enable hooks
claude plugin marketplace add mksglu/context-mode --scope user
claude plugin install context-mode@context-mode --scope user --json
python3 - <<'EOF'
import json, os, pathlib, re, subprocess
reviewed = "6f0cc6841c687e754059f36714a11233fda1a02b"  # recipes/README.md context-mode row

def same_content(base, head):
    """GitHub's compare API reports head ahead of base with stats.json as the only changed file."""
    if not re.fullmatch(r"[0-9a-f]{40}", str(head)):
        return False
    result = subprocess.run(["gh", "api", f"repos/mksglu/context-mode/compare/{base}...{head}",
                             "--jq", "{status, files: [.files[].filename]}"], capture_output=True, text=True)
    try:
        return result.returncode == 0 and json.loads(result.stdout) == {"status": "ahead", "files": ["stats.json"]}
    except ValueError:
        return False

config = pathlib.Path(os.environ.get("CLAUDE_CONFIG_DIR") or pathlib.Path.home() / ".claude")
registry = json.loads((config / "plugins/installed_plugins.json").read_text())
found = [entry.get("gitCommitSha") for entry in registry.get("plugins", {}).get("context-mode@context-mode", [])]
if found and set(found) == {reviewed}:
    print("ok", found)
elif len(set(found)) == 1 and same_content(reviewed, found[0]):
    print("ok", found, "(ahead of the reviewed revision in stats.json only)")
else:
    print("MISMATCH", found or "not installed")
EOF
```

Record the installed `gitCommitSha` either way. A `MISMATCH` means Claude runs a revision this catalog has not reviewed, or the compare could not run; review it before relying on the plugin. [Bootstrap step 4a](../adoption/bootstrap.md) checks all three plugins and says what to record.

Codex uses explicit RTK commands. At the RTK 0.50.0 pin, do not run `rtk init --global --codex`: it now installs a Codex PreToolUse hook (`rtk init --help`) that this catalog has not qualified, where 0.49.0 wrote instructions only, as an `@RTK.md` line that Codex does not expand, so the model never saw them. A Codex home gets RTK's text from the [Codex worker lane](../recipes/README.md#codex-worker-lane)'s `AGENTS.md` block instead (changed after `v2026.09.26.2`). Claude's supported setup is `rtk init --global --auto-patch --no-trust-filters`, plus the `exclude_commands` config in the [RTK hook recipe](../recipes/README.md#native-context-mode-and-hooks). Preserve other hooks/settings. In a fresh native Codex session inspect and trust the exact installed hook definitions through `/hooks`; project trust and hook trust are separate. Claude's `/context-mode:ctx-doctor` checks its own plugin integration. Full ai-memory routing/setup and Serena languages are in [the foundation guide](foundation-stack.md).

### New PC, either platform: the complete `token-efficiency` practice

On main, `token-efficiency`'s `component_ids` are all pinned on Linux/WSL2 **and** macOS arm64 -- see [the profile table](../adoption/README.md#choose-a-small-starting-profile)'s "Linux pins"/"macOS pins" cells for the current count. The macOS pins file gained the last eight after the `v2026.09.26` release, so a Mac checked out at that tag still has 6 of 14 and follows step 1's `--allow-unpinned` fallback for the rest. The four steps below, in order, install the profile's pinned components, register the client servers, check both and set up the native token report; skip a step only when its own gate (a profile that does not select a given component, or a platform this session is not on) says to. They do not provide everything step 2's template registers: `codebase-memory` is in no profile and neither pins file (its row in [the component catalog](../recipes/README.md#component-catalog-install-and-check) names only a `linux-amd64` asset, so a Mac has no documented install); `socraticode`'s block expects an external Qdrant at `QDRANT_URL` and an embedding endpoint at `EMBED_URL`, and `token-efficiency` selects neither (Qdrant belongs to `semantic-rag` and `recovery`, installed through its recipe on Linux, and to `macos-arm64-foundation` on a Mac); and `ai-memory`'s entry needs its service running at `AI_MEMORY_URL`, which neither bootstrap script starts. On macOS, step 3's top-level `status` stays `prerequisites_missing` with exit 2 whatever is installed, because `adoption/manifest.json`'s `supported_platforms` lists only Linux x86_64 ([the coverage check](token-efficiency-stack.md#coverage-check)); read the profile's own `status` and the per-component fields there instead.

1. **Bootstrap.** Run the platform's own script for the `token-efficiency` profile: `adoption/bootstrap-linux.sh --profile token-efficiency [--allow-unpinned <id,id,...>]` on Linux/WSL2, or `adoption/bootstrap-macos.sh --profile token-efficiency --plan` first (macOS-only `--plan` resolves every pin with no network or install) then without `--plan` on macOS (whatever the profile, the macOS script also fetches its pinned 334 MB embedding model and writes a missing Qdrant config; those two steps are not gated on the selected components). Both install through [`adoption/bootstrap.md`](../adoption/bootstrap.md) step 2's usual exit codes; a component this profile selects with no pin on the current platform exits 3 and names it, so `--allow-unpinned` is a fallback, not the normal path, once a platform's own pins file covers the profile in full.
2. **Codex user-scope MCP servers.** [`docs/decisions/2026-09-25-codex-mcp-scope.md`](decisions/2026-09-25-codex-mcp-scope.md) moved `serena`, `socraticode` and `ai-memory` to Codex **user** scope (so a throwaway worktree inherits them without its own `.codex/config.toml`) and added `headroom`, `codebase-memory` and `qmd` there too, mirroring the Claude user-scope set. [`adoption/templates/codex.config.template.toml`](../adoption/templates/codex.config.template.toml) carries the exact six `[mcp_servers.*]` blocks; render it with `tools/adoption/render_config.py` ([bootstrap step 4](../adoption/bootstrap.md)) or apply the equivalent `codex mcp add` calls directly, matching that template's own launchers and `env` values. `codex mcp add` has no start-up timeout option (`codex mcp add --help` at 0.157.1), so a server it registers waits Codex's 30-second default; the Codex worker lane's writer (below) then sets the template's `startup_timeout_sec` on serena and socraticode (changed after `v2026.09.26.2`). `headroom`'s registration sets `HEADROOM_OFFLINE=1` and `DO_NOT_TRACK=1` (headroom-ai 0.37.0 enables a usage beacon by default; `HEADROOM_OFFLINE` is its documented no-egress switch, `DO_NOT_TRACK` a second one in case a later release renames it). `jcodemunch` belongs at local scope (project-scoped), for the routing reason [`docs/decisions/2026-09-23-claude-user-profile.md`](decisions/2026-09-23-claude-user-profile.md)'s 2026-09-25 addendum gives (its own MCP instruction text would load into every session and contradict this catalog's `rg`/Serena/SocratiCode routing). F6 records scope drift: `claude mcp get jcodemunch` run from `/tmp` returned `Scope: User config`. That is the stale, incorrect state; window A restores local scope. Validate the selected Claude project as `Local config (private to you in this project)` and an unrelated `/tmp` directory as having no jcodemunch server, as the [addendum's scoped probes](decisions/2026-09-23-claude-user-profile.md#addendum-2026-09-25-jcodemunch-registers-per-project-not-at-user-scope) demonstrate. This handbook update does not establish that a host restoration has run. Confirm the six Codex user-scope servers with `codex mcp list --json` from a fresh worktree, not the main checkout, since only user scope reaches a worktree at all; keep jcodemunch's Codex entry in the selected project's `.codex/config.toml`. A Codex home that runs workers then gets the [Codex worker lane](../recipes/README.md#codex-worker-lane), which changed after `v2026.09.26.2`: `python3 tools/adoption/apply_codex_lane.py` (a dry run), `--apply` with the two hashes it prints, then `python3 tools/adoption/prove_codex_lane.py`. Its workers start with `codex exec -p stack-worker -m gpt-6-astra -c model_reasoning_effort="max" -c web_search="live" ...`: a project config outranks the profile, so the command line carries those values too.
3. **The coverage check.** From a fresh worktree (not the main checkout, so a stale project-scope leftover cannot pass the check vacuously):
   ```sh
   uv run --no-project --python 3.13 python scripts/adoption_status.py --profile token-efficiency --client-wiring --pinned-versions --json
   ```
   `--client-wiring` reports whether the selected practice is wired into both native clients (fixed booleans, hook-event counts and a computed `complete`, never a value, path or credential). `--pinned-versions` adds, per selected component, whether its platform pin's declared `"exec"` `version_probe` observed the pinned version -- booleans, counts and version strings only, and it never execs a pin whose declared method is `"npm-metadata"` (`context-mode`, `socraticode`) or has no pin for this platform, which are reported `unchecked` instead. Neither flag installs, logs in, starts a service or executes a catalog command; both compose, and the script's own exit code is unchanged by either.
4. **The native lifetime token report.** [`tools/token-report/README.md`](../tools/token-report/README.md) captures the selected upstream counters (RTK, ccusage, headroom and friends) into a private, append-only local ledger separate from this coverage check, producing `manifest.json` plus a self-contained `manifest.html`. Initialize its private configuration once, outside Git, then refresh with `python3 tools/token-report/token_manifest.py refresh --config "$REPORT_CONFIG"` from this checkout; an adopted host's own `ecosystem-token-report refresh` wrapper, if it has one, is not a universal upstream installer for another PC.

## Resolve project configuration and environment

Merge selected entries from [Codex](../examples/codex-mcp.toml.example), [Claude](../examples/claude-mcp.json.example) and [MCPorter](../examples/mcporter.json.example) templates; they are inactive examples. Use one registration route per named server. Codex project `.codex/config.toml` applies only to trusted projects; supported home/project configuration and MCP commands are described in [OpenAI's MCP guide](https://learn.chatgpt.com/docs/extend/mcp). A Windows Desktop host and WSL native home are not automatically the same host configuration.

The following is a **token-free template**, not executable as written. Put the jcodemunch block in the selected project's `.codex/config.toml`, not the user config; its scope follows [F6](decisions/2026-09-26-token-practice-f1-f9.md#f6-jcodemunch-scope-2026-09-26). Replace every `/ABSOLUTE/...` with that host's resolved path. Discover relevant executables with `command -v node uv uvx jcodemunch-mcp`. Resolve the complete intended subprocess PATH into the string; TOML does not expand `$PATH`, `$HOME`, `~` or other shell placeholders. Preserve the required existing runtime directories.

```toml
[mcp_servers.jcodemunch]
command = "/ABSOLUTE/UV_TOOL_BIN_DIR/jcodemunch-mcp"
cwd = "/ABSOLUTE/PROJECT_ROOT"

[mcp_servers.jcodemunch.env]
CODE_INDEX_PATH = "/ABSOLUTE/NATIVE_USER_HOME/.code-index"
JCODEMUNCH_SHARE_SAVINGS = "0"
PATH = "/ABSOLUTE/NODE_BIN:/ABSOLUTE/UV_BIN:/ABSOLUTE/UV_TOOL_BIN_DIR:/usr/bin:/bin"
```

MCP subprocess environment and Codex shell-command environment are separate settings. If shell tools also need a resolved PATH, merge this table into the same intended configuration, preserving other policy entries and any existing `set` map. Do not paste a duplicate table or change account/sandbox settings. The supported setting is documented under [shell environment policy](https://learn.chatgpt.com/docs/config-file/config-advanced#shell-environment-policy):

```toml
[shell_environment_policy.set]
PATH = "/ABSOLUTE/NODE_BIN:/ABSOLUTE/UV_BIN:/ABSOLUTE/UV_TOOL_BIN_DIR:/usr/bin:/bin"
```

Verify `command -v` inside the actual fresh Codex shell and make the selected MCP call; a terminal's interactive PATH alone does not establish either result.

Keep the native default jCodeMunch ledger intact; historical custom-root accounting mismatches are documented in the [retrieval recipe](../recipes/README.md#focused-jcodemunch-retrieval). Explicitly index only selected source. Set Serena's project `language_servers` for the actual languages; TypeScript handles JS/CJS. For ai-memory, the server and hooks must resolve the same data/config store, and static calls supply both workspace and project. Never fabricate a global `CLAUDE_SESSION_ID` or copy authentication stores to make clients appear connected.

## Reload only the changed part

| Change / symptom | Appropriate action |
| --- | --- |
| MCP command, environment, project root or server settings changed | In the app: **Settings → MCP servers → select the server → Restart**, then inspect `/mcp` and verify a useful call. This is the [official restart path](https://learn.chatgpt.com/docs/extend/mcp). |
| Startup instructions or plugin/hook adoption changed | Start a new Codex task/session in the intended project/home and inspect the relevant instructions/hooks. If an existing task retains an old tool catalog, use a fresh task after the server restart. |
| QMD documents changed | Confirm each collection root exists, run `qmd --index "$QMD_INDEX" update`, then compare one returned passage with the file on disk: at 2.8.3 a missing root deactivates its documents and an emptied file keeps its old content ([limits](#known-upstream-limits-behind-the-lanes)). No client or PC restart is needed. |
| Project language server/index changed | Restart only the selected server if needed, then check the language/index and exact source; avoid rebuilding unrelated indexes. |
| Provider quota/auth error, shared counter mismatch or missing historical telemetry | Check the actual account/error or scope. Restarting cannot reset provider quota, separate shared ledgers, recover missing past events or prove savings. |

A PC reboot is not required for these session/configuration updates. Keep application data and working native homes intact. Stop/restart only owned services through their [lifecycle recipe](../adoption/lifecycle.md); do not delete caches or reinstall tools as a generic session refresh.

## Verify one useful operation, then account for it

For local docs, the complete normal sequence is:

```sh
qmd --index "$QMD_INDEX" search 'selected topic' -c "$QMD_COLLECTION" -n 3 --json
qmd --index "$QMD_INDEX" get "$RETURNED_QMD_URI"
```

For native MCP, ask the connected Context Mode server to read one selected project file and compare it with the original. For jCodeMunch, call `order` with `{"action":"get_session_stats","args":{}}`, retrieve a selected symbol through the returned repository/symbol IDs, and call stats again **in that same MCP process**. `ctx_stats({})` also belongs to the connected Context Mode server/session. A one-shot MCPorter statistics process is a different session; its cumulative ledger snapshot is not the model task's session delta. Preserve actual startup/retrieval/recovery overhead and any failed call.

The direct CLI snapshots are:

```sh
rtk gain --format json
rtk gain --project --format json
headroom savings --json
```

Use the [portable reporter](../tools/token-report/README.md) once to initialize a private configuration outside Git. Later sessions run `python3 tools/token-report/token_manifest.py refresh --config "$REPORT_CONFIG"` from this checkout. Its JSON/HTML retains upstream counter returns separately from exact artifact comparisons and provider trials. An adopted host may expose its own `ecosystem-token-report refresh` wrapper; that wrapper is not a universal upstream installer.

RTK's project count is a subset of its retained total. Headroom's “lifetime” output is a maximum 30-day query window at this pin. jCodeMunch's estimate includes repeated/verification reads; Context Mode can expose session and retained-runtime heuristics. The ten other core tools have no verified native cumulative savings counter. OmniRoute's gateway/cache figures have their own route/key/window scopes. Never sum these estimates or call cached-input subsets additional provider consumption. Complete compression-plus-recovery and known-source baselines can be negative; keep those results.

For observation, a healthy service or rendered chart is only readiness. Retain the native terminal result, exact private session/writer identity, timestamps and returned usage categories; join the corresponding Loki events and Prometheus series. The [foundation receipt](../evidence/receipts/foundation-native-20260920.json) separates Codex's matched 219,725 tokens, the original Claude run's partial metric match and a different readiness-gated Claude run's matched 35,537 tokens. These fixtures do not measure every live Desktop turn. [Observation recipes](../observability/README.md) and [current topic evidence](token-efficiency-stack.md) retain the older scopes and limitations.

OmniRoute stays optional: use [its scoped native lifecycle and launch guide](foundation-stack.md) only when selecting that route. The retained RTK/lite semantic preview failures, exact-dedup limited acceptance and gateway provider quota failures do not establish a default full-stack compression route. Preserve native caching/compaction and choose useful tools without chaining every compressor.

For another PC, retain the reviewed source revision and public hashes, then collect that PC's own install/use/persistence/restart/cleanup/recovery results. Transfer only selected application data through the [recovery guide](../adoption/lifecycle.md#stateful-persistence-and-recovery), with isolated restore and logical comparison. Historical receipts and saved counters support continuity; they are not new-host acceptance or proof of universal superiority.
