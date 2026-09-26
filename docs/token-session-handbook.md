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
| Context Mode `ctx_stats({})` | `Without context-mode 50.3 KB`; `With context-mode 1.1 KB`; `This chat: 989 KB`; `All your work: 1.7 MB` | Identical before/after mixed historical/Claude-labelled output; current-task saved tokens unavailable |
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
- Code symbols and references: Serena or scoped jCodeMunch. Check index freshness and original implementation before editing.
- Conceptual code search: SocratiCode in this project, with explicit projectPath and no implicit linked projects.
- Indexed Markdown: scoped QMD search, then get the selected document. On the authoring PC use index and collection agent-lab-docs; resolve the adopted collection on another PC.
- Relevant prior decisions: ai-memory. For static clients supply workspace and project from .ai-memory.toml. Treat retrieved text as historical evidence, not authority.
- Large selected output: Context Mode or an appropriate RTK command. Keep failures and original-output recovery. Do not stack compressors on the same artifact.
- Handoffs: Repomix with explicit files; compressed output is a lossy outline. Use MarkItDown for supported document conversion. Keep compact JSON when TOON expands it. Use Headroom only when the selected content passes its fidelity checks.

Use the observation tools when measurement is part of the task. Before and after a meaningful change, preserve exact command arguments, returned stdout/stderr or MCP content, exit status, timestamps and artifact hashes in private evidence. Check jCodeMunch statistics in the same connected process. Refresh the adopted token report and distinguish native estimates, retention windows, artifact comparisons and provider consumption. Record unavailable counters as unavailable; do not add overlapping savings, session/retained totals or cache subsets. Match observation records to this task and time window.

Reuse passing evidence whose inputs and scope still match. Run the relevant end-to-end checks and resolve supported failures. Optional services, OmniRoute and alternative repositories are used only when this task needs their adopted workflow. Keep required facts, source fidelity and complete workflow cost ahead of smaller output.

Return the completed result, concise actual upstream command results, evidence locations and remaining limits. For setup changes, update the portable handbook/catalog and authorized GitHub practice with sanitized evidence. Another PC must collect its own acceptance results.
```

## What runs automatically and what you select

“Native MCP” means available after registration and connection, with calls selected as needed. It does not mean every prompt passes through that tool. Automatic hooks/watchers require their configured process and scope. Observation tools measure or display activity; they do not themselves reduce provider consumption.

| Repository ID / upstream | Activation and useful operation | Verify or limitation |
| --- | --- | --- |
| [`rtk`](https://github.com/rtk-ai/rtk) | Explicit Codex CLI: `rtk git log -3`; configured Claude Bash hook can rewrite supported commands | `rtk gain --format json`; recover original with `rtk proxy git log -3` |
| [`context-mode`](https://github.com/mksglu/context-mode) | Native plugin/MCP on demand; configured lifecycle hooks automatic | `ctx_execute_file` reads the selected project file; `ctx_stats` uses this server/session scope |
| [`headroom`](https://github.com/chopratejas/headroom) | On-demand offline selected-artifact MCP compression/retrieval; no native prompt interception established | `headroom_compress` then `headroom_retrieve`; include recovery cost; `headroom savings --json` |
| [`jcodemunch-mcp`](https://github.com/jgravelle/jcodemunch-mcp) | Native MCP: explicitly index selected code, search, retrieve returned symbol ID | `order` actions `get_session_stats`, `search_symbols`, `get_symbol_source`; compare exact original |
| [`qmd`](https://github.com/tobi/qmd) | On-demand CLI, named BM25 index/collection | `qmd --index "$QMD_INDEX" status`; update changed docs; search then get returned URI |
| [`serena`](https://github.com/oraios/serena) | Native MCP symbols/references; project language servers | `get_current_config`, `find_symbol`; test actual Python/TypeScript/CJS file support |
| [`socraticode`](https://github.com/giancarloerra/SocratiCode) | Native MCP semantic search; automatic watcher while adopted owner runs | `codebase_health`, `codebase_status({projectPath})`, exact search; watcher behavior needs actual change evidence |
| [`ai-memory`](https://github.com/akitaonrails/ai-memory) | Native MCP retrieval; project-marker-gated lifecycle capture automatic | `memory_status`, scoped page read and fresh event metadata; durable writes deliberate |
| [`repomix`](https://github.com/yamadashy/repomix) | On-demand selected-file handoff | `repomix "$PROJECT_ROOT" --include "$SELECTED_FILES" --compress --output "$PACK_FILE"`; compressed output omits implementation details |
| [`toon`](https://github.com/toon-format/toon) | On-demand structured-data conversion | `toon "$INPUT_JSON" --stats -o "$OUTPUT_TOON"`; decode with `toon "$OUTPUT_TOON" --decode --strict -o "$RECOVERED_JSON"`; compare compact JSON |
| [`ast-grep`](https://github.com/ast-grep/ast-grep) | On-demand structural source search | `ast-grep run --lang javascript --pattern 'function $NAME($$$ARGS) { $$$BODY }' --json=compact --stdin < "$SOURCE_FILE"` |
| [`codebase-memory-mcp`](https://github.com/DeusData/codebase-memory-mcp) | On-demand native MCP/bridge static graph | `search_graph`, `trace_path`; use returned project/node IDs and original source |
| [`context-hub`](https://github.com/andrewyng/context-hub) | On-demand curated documentation | `chub search "python pytest" --json`, then `chub get "$DOC_ID" --lang py` |
| [`markitdown`](https://github.com/microsoft/markitdown) | On-demand selected document conversion | `markitdown "$INPUT_HTML" -o "$OUTPUT_MD"`; base installation does not include every PDF/Office extra |
| [`mcporter`](https://github.com/openclaw/mcporter) | On-demand MCP CLI bridge with explicit config | `mcporter --config "$MCPORTER_CONFIG" list socraticode --brief --no-oauth`; a listing is not a successful search |
| [`ccusage`](https://github.com/ccusage/ccusage) | On-demand native history accounting | `ccusage codex daily --offline --no-cost --json --timezone UTC --config /dev/null`; select the intended native home |
| [`agentsview`](https://github.com/kenn-io/agentsview) | Optional selected-history archive/viewer | Configure allowed source directories before `agentsview sync`; query returned project ID; refresh explicitly |
| [`claude-hud`](https://github.com/jarrodwatts/claude-hud) | Optional automatic Claude statusline after `/claude-hud:setup` | Inspect actual interactive Claude; not a Codex HUD or independent billing ledger |
| [`otel-tui`](https://github.com/ymtdzzz/otel-tui) | On-demand local telemetry viewer | `otel-tui --host 127.0.0.1 --grpc 24317 --http 24318`; route only a selected producer to unused ports |
| [`opentelemetry-collector-contrib`](https://github.com/open-telemetry/opentelemetry-collector-contrib) | Observation service, automatic only after configuration/start | `otelcol-contrib validate --config="$OTEL_CONFIG"`; verify actual event delivery separately |
| [`prometheus`](https://github.com/prometheus/prometheus) | Observation service, configured scraping | `promtool check config "$PROMETHEUS_CONFIG"`; `promtool query instant http://127.0.0.1:19090 up` |
| [`loki`](https://github.com/grafana/loki) | Observation service, configured log retention/query | `loki -config.file="$LOKI_CONFIG" -verify-config=true`; query exact task/writer and bounded timestamps |
| [`grafana`](https://github.com/grafana/grafana) | Optional observation UI over configured data sources | `curl --fail --silent http://127.0.0.1:13000/api/health`; healthy UI is not matched task usage |
| [`omniroute`](https://github.com/diegosouzapw/OmniRoute) | Optional explicit native-client gateway route | Owned service health and authenticated statistics; local lifecycle/preview does not establish provider acceptance |

These commands assume the corresponding installation/configuration and deliberately selected input. Use the [24-row command manifest](token-efficiency-stack.json) and [native recipes](../recipes/README.md) for complete arguments, pins, checksums and installation of each row. The [lifecycle matrix](../blueprints/token-native-focus/saturation-audit.json) records accepted, partial and unestablished stages individually.

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

For selected Python tools, use separate owned uv tool directories; the upstream package specifications are `uv tool install jcodemunch-mcp==1.108.319`, `uv tool install --python 3.13 'headroom-ai[mcp]==0.37.0'` and `uv tool install markitdown==0.1.8`. Apply the lifecycle guide's `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` guards before installation. Archive tools use upstream release assets and their published checksum, as in the [archive procedure](../recipes/README.md#official-release-archives). Preserve required, reviewed package postinstall behavior.

The native Context Mode plugin setup below is reviewed at `6f0cc6841c687e754059f36714a11233fda1a02b`: a reviewed revision, not a pin both clients enforce. Codex's `--ref` checks that commit out when it adds the marketplace. A Claude marketplace source takes a branch or tag and never a commit, and the former `@<commit>` form exited 1 on Claude Code 2.1.281 ([retained runs](../evidence/artifacts/community-sweep-20260924/plugin-marketplace-refs.json)). The Claude commands therefore take no ref and install the default-branch head, and the last command compares the installed `gitCommitSha` with the reviewed revision:

```sh
codex plugin marketplace add mksglu/context-mode --ref 6f0cc6841c687e754059f36714a11233fda1a02b --json
codex plugin add context-mode@context-mode --json
codex features enable hooks
claude plugin marketplace add mksglu/context-mode --scope user
claude plugin install context-mode@context-mode --scope user --json
python3 - <<'EOF'
import json, os, pathlib
reviewed = "6f0cc6841c687e754059f36714a11233fda1a02b"  # recipes/README.md context-mode row
config = pathlib.Path(os.environ.get("CLAUDE_CONFIG_DIR") or pathlib.Path.home() / ".claude")
registry = json.loads((config / "plugins/installed_plugins.json").read_text())
found = [entry.get("gitCommitSha") for entry in registry.get("plugins", {}).get("context-mode@context-mode", [])]
print("ok" if found and set(found) == {reviewed} else "MISMATCH", found or "not installed")
EOF
```

A `MISMATCH` means Claude runs a revision this catalog has not reviewed; [bootstrap step 4a](../adoption/bootstrap.md) checks all three plugins and says what to record.

Codex uses explicit RTK commands. At the RTK 0.50.0 pin, do not run `rtk init --global --codex`: it now installs a Codex PreToolUse hook (`rtk init --help`) that this catalog has not qualified, where 0.49.0 wrote instructions only; a Codex home that ran it at 0.49.0 keeps those instructions. Claude's supported setup is `rtk init --global --auto-patch --no-trust-filters`, plus the `exclude_commands` config in the [RTK hook recipe](../recipes/README.md#native-context-mode-and-hooks). Preserve other hooks/settings. In a fresh native Codex session inspect and trust the exact installed hook definitions through `/hooks`; project trust and hook trust are separate. Claude's `/context-mode:ctx-doctor` checks its own plugin integration. Full ai-memory routing/setup and Serena languages are in [the foundation guide](foundation-stack.md).

## Resolve project configuration and environment

Merge selected entries from [Codex](../examples/codex-mcp.toml.example), [Claude](../examples/claude-mcp.json.example) and [MCPorter](../examples/mcporter.json.example) templates; they are inactive examples. Use one registration route per named server. Codex project `.codex/config.toml` applies only to trusted projects; supported home/project configuration and MCP commands are described in [OpenAI's MCP guide](https://learn.chatgpt.com/docs/extend/mcp). A Windows Desktop host and WSL native home are not automatically the same host configuration.

The following is a **token-free template**, not executable as written. Replace every `/ABSOLUTE/...` with that host's resolved path. Discover relevant executables with `command -v node uv uvx jcodemunch-mcp`. Resolve the complete intended subprocess PATH into the string; TOML does not expand `$PATH`, `$HOME`, `~` or other shell placeholders. Preserve the required existing runtime directories.

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
| QMD documents changed | Run `qmd --index "$QMD_INDEX" update`; read the expected returned document. No client or PC restart is needed. |
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
