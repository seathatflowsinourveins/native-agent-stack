# Native token-efficiency stack: commands and returned evidence

This is the topic-specific entry point for the selected stack on September 20,
2026. The [machine-readable list](token-efficiency-stack.json) contains the full
upstream install, use and statistics commands, versioned sources, returned results,
baseline comparisons and lifecycle limits for each tool. The
[offline HTML](ecosystem/index.html#efficiency) embeds this guide and those rows;
its Setup view contains all 65 selected components across ten layers. The broader
512-repository catalog includes alternatives and references, not 512 installations.

The installed commands are usable in their recorded native lanes. Four tools
have upstream savings estimates. The other ten core tools have no established
native session/lifetime savings counter; their useful evidence is retrieved
content, conversion correctness, or a scoped artifact comparison. An installation
does not guarantee a reduction against the cheapest adequate baseline.

## Core list

Commands below name the upstream operation; full arguments and portable path
variables are in the machine list and each linked recipe. MCP operations use the
installed native client or the upstream MCPorter bridge. Measurements are dated
source-host observations. Arrows compare the exact retained representations,
not provider bills, and lossy representations require the documented quality check.

| Repository | Upstream use / statistics | Returned evidence |
|---|---|---|
| [RTK](https://github.com/rtk-ai/rtk) | `rtk git log -3`; `rtk gain --format json` | Latest retained probe: 55 commands, 1,722 estimated tokens saved; independent SQLite row: 118 input, 104 output, 14 saved. No separate session savings counter. |
| [Context Mode](https://github.com/mksglu/context-mode) | `ctx_execute_file`, `ctx_search`, `ctx_stats` | Recorded Desktop stats: rounded 1.1M estimated saved, 98.9%; the native project bridge returned the independently matched file hash. The older loaded Desktop file connection retains its scope error. |
| [Headroom](https://github.com/chopratejas/headroom) | `headroom compress`; MCP `headroom_compress`, `headroom_retrieve`; `headroom savings --json` | Default ledger: 0 calls / 0 saved. Separate clean-prefix trial: 9,616→2,128 upstream estimated tokens, 7,488 saved; exact recovery and restart passed. |
| [jCodeMunch](https://github.com/jgravelle/jcodemunch-mcp) | MCP `order` with `search_symbols`, `get_symbol_source`, `get_session_stats` | Latest default retained estimate: 39,760 saved (earlier 29,820). Clean-prefix ledger: 0→2,781→2,781 after restart→5,562 after a second exact source read. |
| [QMD](https://github.com/tobi/qmd) | `qmd --index "$QMD_INDEX" search … -c "$QMD_COLLECTION"`; scoped `get` | BM25 returned the intended runtime document at score 0.86 and the requested section. No downloaded embedding models in this profile. |
| [Serena](https://github.com/oraios/serena) | `find_symbol`, `find_referencing_symbols`, `search_for_pattern` | Native symbol retrieval passed; this Desktop query returned `172:def parse_codex(stream, env):`. Selected artifact 3,129→214 tokens. |
| [SocratiCode](https://github.com/giancarloerra/SocratiCode) | `codebase_health`, `codebase_status`, `codebase_search` | Healthy local Qdrant/embedding services; 196 chunks, active watcher, intended source match. Separate retained artifact 2,731→491 tokens. |
| [ai-memory](https://github.com/akitaonrails/ai-memory) | `ai-memory status`; scoped `memory_search`, `memory_get_session` | Native version/status and scoped search passed; current Desktop parent is active with bounded lifecycle observations. These are not complete transcripts. |
| [Repomix](https://github.com/yamadashy/repomix) | `repomix … --include … --compress` | Selected paths present; retained outline artifact 3,697→663 tokens. Read original implementation before editing or judging correctness. |
| [TOON](https://github.com/toon-format/toon) | `toon --encode`; `toon --decode --strict` | Exact JSON round trip passed. Small fixture 1,664→1,307; catalog compact JSON 59,792→66,815, so compact JSON wins for that catalog. |
| [ast-grep](https://github.com/ast-grep/ast-grep) | `ast-grep run --stdin --lang javascript --pattern …` | Eight structural matches, exit 0. Original capture 1,818→674 tokens; later output variant 1,818→686. |
| [codebase-memory](https://github.com/DeusData/codebase-memory-mcp) | `search_graph`, `trace_path` | Intended function and four static callees returned. Artifact 2,731→186 tokens; static edges do not establish runtime execution. |
| [Context Hub](https://github.com/andrewyng/context-hub) | `chub search`; `chub get` | Selected documentation returned, exit 0. Response 2,070→2,155 tokens grew by 85; useful retrieval is not necessarily smaller. |
| [MarkItDown](https://github.com/microsoft/markitdown) | `markitdown "$INPUT_HTML" -o "$OUTPUT_MD"` | Expected heading returned, exit 0; selected HTML 10,322→1,360 tokens. PDF/Office extras are absent. |

The latest final capture is in the machine list and final receipt. Earlier
numbers above retain their original scopes and times. Estimates can include
verification reads, overlap across scopes and expire under native retention.
Do not sum them or label them exact lifetime provider savings.

## Fresh native Codex and Claude acceptance

The [final receipt](../evidence/receipts/native-token-stack-final-20260920.json)
retains the native returned results, independent source checks, observation
correlations and hashes of private command captures.

Native Codex 0.155.1 and Claude 2.1.278 each read the actual project through
Context Mode, searched for the requested function through jCodeMunch, retrieved
its source and continued in the same native session. They used their existing
native sign-ins and configured models. No provider/account configuration changed.

Codex's first launch accidentally used a read-only sandbox instead of the
installed native launch policy. Two MCP calls were refused even though the CLI
exited 0. The corrected same-session launch completed all three MCP calls and
returned byte-exact source. Both process groups ended cleanly. Returned usage is
session-cumulative: **161,720 consumed tokens**, including the failed first
attempt's 64,820; the corrected turn's delta is 96,900. Cached input is already
included. Adding the first attempt again would double-count it.

Claude's functional source and continuity checks passed with three successful
initial MCP calls. Its strict initial JSON-only format check failed because the
response included extra prose; that defect remains recorded. Its first two
invocations consumed 201,200 tokens. One later minimal continuation verified the
observation join and consumed 46,011 more, for **247,211 consumed tokens** across
the three invocations. The latter operation passed its exact marker check.

These are functional/observation acceptance runs, not paired provider-savings
trials. Neither total is avoided tokens. Per-process Context Mode and jCodeMunch
savings statistics were not collected in the initial two-client task, so the
receipt records them as unavailable rather than substituting a global counter.

## Observation that can be independently matched

The earlier [Desktop observation guide](current-session-observation.md) records
four exact-parent tool correlations, live retained hook observations, six active
monitoring services and seven healthy scrape targets. It also retains the initial
Loki readiness failure and the limits on exact Desktop task-to-metric attribution.

For native Claude, telemetry was already arriving. The installed session-ID
privacy setting also removes the session label from its log events, so a raw
session-ID query correctly returned zero matches. Directly invoking the CLI had
also omitted the native launcher's process and client labels. The corrected
continuation supplied the supported resource attributes in that process only:
unique `service.instance.id`, `ecosystem.client.scope=native-claude`, and a stable
SHA-256 task label in `ecosystem.task.id`. Raw session/account suppression stayed
enabled. There was no synthetic event or persistent configuration change.

The resulting native CLI usage matched **both Loki's api_request and Prometheus's
writer-scoped series** in all four categories: input 2, cache creation 2,300,
cache read 43,698, output 11. Total 46,011. The final receipt contains the exact
queries, time bounds, returned values and independent comparison results, with
raw local identities kept private. These checks establish this accepted writer's
delivery and accounting, not universal fleet observability or causal savings.

Codex's two writer-scoped Prometheus totals also match the returned native
64,820 and 96,900 tokens, and Loki records both refused calls and all three
successful calls. Seven per-request completion events reconcile to 161,720.
Two additional startup completion events report 12,886 input and zero output
each: **25,772 additional, unattributed tokens in the raw event stream**. The
receipt preserves them separately; they are absent from the returned turn totals
and Prometheus turn histograms. Summing all nine Loki completion events gives
187,492, so whole-stream equality and final provider billing remain unestablished.

The Collector, Loki, Prometheus and Grafana form the persistent observation path.
MCPorter transports selected MCP calls; ccusage reports consumed usage; AgentsView
is a scoped archive viewer; Claude HUD is native Claude UI; otel-tui is an optional
local telemetry viewer. Viewers are not savings engines. Their separate rows say
whether they were active, tested on demand, or limited by the current UI/account
state. Native Claude HUD is not a Codex Desktop panel.

## Reproduce on another PC

1. Clone the canonical repository and open the offline HTML. Choose the relevant
   [adoption profile](../adoption/README.md); follow each component's pinned
   upstream recipe using prefixes and state directories owned by that installation.
2. Keep native Claude and Codex sign-in/configuration separate from Desktop.
   Use the documented native launcher environment, including telemetry writer,
   client and hashed task labels. Do not copy another PC's authentication stores.
3. Run the component's actual upstream use command against that PC's selected
   project. Verify expected content, errors and owned-process cleanup. For
   persistence tools, run the documented restart/recovery check. Preserve the
   [six-stage lifecycle matrix](../blueprints/token-native-focus/saturation-audit.json):
   stages marked unestablished are not silently accepted by an installation.
4. Record upstream session/retained-history counters separately from exact artifact
   comparisons and native consumed usage. Compare against the cheapest adequate
   representation. Headroom compression plus full recovery grew 5,105→18,777
   tokens; a known 40-token function grew to 324 with search/source envelopes.
   Use direct reads when those satisfy the task more cheaply.
5. Match returned native results with actual writer/task-scoped monitor records,
   retaining bounded failures and private hashes. Run the
   [portable token reporter](../tools/token-report/README.md) to refresh that PC's
   manifest. Source-host results are reference evidence, not that PC's acceptance.

The published snapshot is definitive about the selected versions, commands and
recorded evidence. It does not prove a universally optimal repository set,
guaranteed savings for every task, or all lifecycle stages for every component.
