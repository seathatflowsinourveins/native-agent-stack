# Native token tools: session and new-PC handbook

Use the installed tools for the current task; setup is a one-time operation per selected client/project. This handbook covers all **24 topic repositories**: 14 context tools, nine observation tools and one optional gateway. The wider catalog has 66 selected components and 512 recorded repository identities; those are different scopes, and catalog inclusion does not mean installed or active. Pins, exact commands and dated results remain in the [topic manifest](token-efficiency-stack.json), [component manifest](../manifests/stack.json) and [foundation receipt](../evidence/receipts/foundation-native-20260920.json).

## Start or resume work

The [authoring-host environment receipt](../evidence/receipts/codex-session-environment-20260920.json) records a fresh native Codex app-server connecting five selected MCP servers, resolving fourteen native commands and completing five read-only calls with no model turn. It verifies the project PATH setup, not a reload of an already-running Desktop task or acceptance on a new PC.

1. Open the intended project in the intended client. Desktop, native Linux Codex and Claude may use different homes, environments and loaded connections. Keep their existing native sign-ins and model settings.
2. Read the project's short `AGENTS.md`/`CLAUDE.md` routing instructions. Open a detailed recipe only for the chosen operation; do not paste the catalog into every prompt.
3. Select one useful retrieval path. Exact identifier/location: `rg`, an original source read or Serena. Unknown code concept: SocratiCode. Indexed Markdown: QMD search then get. Large selected output: Context Mode. Use the smaller complete representation when an extra layer adds overhead.
4. After a relevant setup change, inspect connected servers with `/mcp`, then make one useful call and check its returned content. `codex mcp list` lists configuration; it does not prove that this task connected or used a tool. No installation sweep or model benchmark is needed at startup.
5. Retain the original output when compressing. Check required facts and source fidelity before relying on the result. Capture counters when reporting a meaningful change, with their actual scope.

A short project instruction can be: “Choose one suitable context tool; use scoped QMD for indexed docs, Serena for symbols and SocratiCode for conceptual code search. Preserve original output and separate native estimates from provider usage. Read `docs/token-session-handbook.md` only for setup or accounting.” Point to the actual handbook location when the project is another checkout.

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

For selected Python tools, use separate owned uv tool directories; the upstream package specifications are `uv tool install jcodemunch-mcp==1.108.319`, `uv tool install --python 3.13 'headroom-ai[mcp]==0.37.0'` and `uv tool install markitdown==0.1.7`. Apply the lifecycle guide's `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` guards before installation. Archive tools use upstream release assets and their published checksum, as in the [archive procedure](../recipes/README.md#official-release-archives). Preserve required, reviewed package postinstall behavior.

The pinned native Context Mode plugin setup is:

```sh
codex plugin marketplace add mksglu/context-mode --ref 6f0cc6841c687e754059f36714a11233fda1a02b --json
codex plugin add context-mode@context-mode --json
codex features enable hooks
codex features enable plugin_hooks
claude plugin marketplace add mksglu/context-mode@6f0cc6841c687e754059f36714a11233fda1a02b --scope user
claude plugin install context-mode@context-mode --scope user --json
```

Install RTK awareness once with `rtk init --global --codex` in each intended Codex home; this writes instructions, not a Codex command-rewriting hook. Claude's supported setup is `rtk init --global --auto-patch --no-trust-filters`. Preserve other hooks/settings. In a fresh native Codex session inspect and trust the exact installed hook definitions through `/hooks`; project trust and hook trust are separate. Claude's `/context-mode:ctx-doctor` checks its own plugin integration. Full ai-memory routing/setup and Serena languages are in [the foundation guide](foundation-stack.md).

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
