# Useful native dashboards and returned evidence

Start with the authoring PC's [native foundation view](http://127.0.0.1:13000/d/native-foundation-data)
(on NativeStack2604, [21301](http://127.0.0.1:21301/d/native-foundation-data); see below the table).
The [rendered dashboard review](dashboard-rendered-acceptance.md) records actual
screenshots, command comparisons, presentation repairs and remaining gaps.
It uses the installed Grafana and Loki with locally provisioned integration panels.
It is not an official prebuilt dashboard from each component's authors.
The component interfaces below are their own upstream UIs, generated views or CLIs.
Another PC must configure its own paths, scope, services and native accounts.

## Open the view that contains the requested information

| Information | Useful interface | What the data means |
| --- | --- | --- |
| Memory pages and search | [ai-memory wiki](http://127.0.0.1:49374/web/w/agent-lab/agent-lab) | Official bundled UI, explicitly selected workspace/project; real page search and navigation |
| Code relationships | [SocratiCode graph](http://127.0.0.1:17500/socraticode-graph.html) | Upstream-generated interactive snapshot; generation is explicit, not a continuously regenerated graph |
| Stored code vectors | [Qdrant collections](http://127.0.0.1:16333/dashboard#/collections) | Official UI over existing local collections; points can contain both dense and sparse vectors |
| Savings and source commands | [Full token report](http://127.0.0.1:17500/token-savings.html#native) | Local report preserving upstream returned counters, source files, scopes and exact artifact comparisons |
| Current native inventory | [Foundation Grafana](http://127.0.0.1:13000/d/native-foundation-data) | Selected read-only native commands plus current Qdrant/vLLM metrics; failed observations are unknown |
| This Codex conversation | [Selected archive](http://127.0.0.1:17384/) | One explicitly refreshed Codex snapshot; select the local session in the archive. The active conversation can advance afterward |
| Two recent native Claude sessions | [Selected archive](http://127.0.0.1:17384/) | Two explicitly selected agent-lab files; local identifiers remain private, and these are not asserted to be this Codex task |
| Actual workflow runs | [Dagu history](http://127.0.0.1:18525/dag-runs) | Select Last 30 days to see retained runs; Today can legitimately be empty. Bundled definitions are not executions |
| Actual local notifications | [ntfy topic](http://127.0.0.1:18080/ecosystem-alerts) | Retained messages in the configured topic; the root page is not the topic feed |
| Optional gateway usage | [OmniRoute analytics](http://127.0.0.1:20128/dashboard/analytics) | Recorded traffic through this gateway only; the former usage route redirects to logs. Direct Codex/Claude traffic is separate |
| Browser operations | [agent-browser](http://127.0.0.1:4848/) | Active browser sessions and streams; empty when no browser session is active |
| Evaluation result | [Promptfoo report](http://127.0.0.1:17500/promptfoo.html) | Official HTML export of two passing retained local echo assertions; no model-quality or new evaluation claim |
| Provider and host telemetry | [Native telemetry](http://127.0.0.1:13000/d/ecosystem-native) | Typed exported counters and host metrics, not estimated savings |
| Research checkpoints | [Research Grafana](http://127.0.0.1:13000/d/research-grand) | Dated coordinator checkpoints, recorded experiment results and bounded native workflow history |

On NativeStack2604 (2026-10-06), port 13000 can reach the legacy distribution's
Grafana while it runs: WSL2 distributions share loopback listeners. Use this host's Grafana at
`http://127.0.0.1:21301` (anonymous Viewer): [research](http://127.0.0.1:21301/d/research-grand)
with Dagu run history, [native telemetry](http://127.0.0.1:21301/d/ecosystem-native),
[native foundation](http://127.0.0.1:21301/d/native-foundation-data) and
[token layer](http://127.0.0.1:21301/d/token-layer), the first three once the
install plan's `grafana` row has run. The foundation view's savings, memory and
coverage tables stay empty there until a native-data collector runs on that host.
Its other loopback UIs are listed in
[native dashboard access](native-dashboards.md#nativestack2604-equivalents-2026-10-06).

### NativeStack2604 token events and hook counter (2026-10-06)

The token-layer dashboard keeps exported log records, native counter increases
and the counts-only rollout census separate. Its GPT MCP panels count retained
`codex.tool_result` records by namespace. Its RTK panels classify retained
request-prefix markers, which do not distinguish explicit prefixes from hook
rewrites. Missing data is unobserved coverage, not zero tool use; the queries
do not manufacture zero-valued series. Loki's
[`count_over_time` at v3.7.8](https://github.com/grafana/loki/blob/v3.7.8/docs/sources/query/metric_queries.md)
counts log entries, not deduplicated rollout calls.

Installed Codex reports 0.160.1; the source checks use its upstream revision
`d27764b82f7118f674371e6d6e76271d9d606edb`. Its native
[`codex.tool_decision` log source](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/otel/src/events/session_telemetry.rs#L1166)
is AutomatedReviewer, Config or User, an approval origin rather than a hook or
RTK identifier. Hook-named log records currently have only qualified partial
diagnostic coverage: an
[`after_agent` failure warning](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/core/src/hook_runtime.rs#L653).
Command-hook instrumentation is a
[`codex.hooks.command` trace span](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/hooks/src/engine/command_runner.rs#L199),
so it is not counted as a firing log.

The completion panel uses the actual native metric owner. The pinned
[`codex.hooks.run` constant](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/otel/src/metrics/names.rs#L61)
(plural `hooks`, not `codex.hook.run`) increments
[once per completed hook run](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/core/src/hook_runtime.rs#L931).
Read-only Prometheus observation returned the actual exported family
`codex_hooks_run_total`; its current labels retained status but not lifecycle.
The coordinated Collector change retains the bounded native metric labels;
until it is applied, absent lifecycle labels display as `unknown`. `hook_name`
is a lifecycle label, not a script or processor identity. Prometheus `increase`
is a scrape-based estimate and can miss the first positive sample or missing
exports. Confirmed RTK rewrite totals and per-processor RTK/ai-memory hook
firings remain unmeasured here. No host deployment is established by these
repository changes.

Claude Code 2.1.291 is separately verified. Its
[official hook completion log schema](https://code.claude.com/docs/en/monitoring-usage#hook-execution-complete-event)
defines `num_success`, `num_blocking`, `num_non_blocking_error` and
`num_cancelled` for all matching hook commands. The Claude hook-outcome panel
sums those native fields instead of treating each completion log as one
command. Lifecycle is grouped by `hook_event`; raw matcher and script names
are not displayed. These sums require native hook event export and the
reviewed Collector numeric-field retention. An empty panel does not establish
zero hook executions.

## What changed after the HTTP-only checks

The [attached native results guide](native-returned-results.md) explains how to
download exact returned text and verified bytes from the token report. The
current-turn Codex/Claude child runs are separate from the historical archives.
AgentsView's default list excludes single-turn sessions: use its supported
filters to include those sessions and all automation scopes. Its native API
supports `include_one_shot=true&automated_scope=all`; top-level rows and child
agent rows are separate counts. Changing a filter does not refresh the archive.

The earlier [access receipt](../evidence/receipts/native-dashboard-access-20260921.json)
verified transport and browser access. It did not establish that every page showed
fresh, useful application data. This follow-up traced the missing information:

- ai-memory's base service enabled its bundled UI, but its active override omitted
  `--enable-web`. Restoring that upstream flag exposed the existing wiki without
  another server, database, authentication mechanism or frontend installation.
- AgentsView intentionally used an old archive with `--no-sync`. Three explicit
  source-file refreshes made the requested conversations visible while preserving
  the previous fourteen archive rows. This is a snapshot, not continuous ingestion.
- Dagu's timeline is sparse because the server does not start a scheduler. The
  existing successful run is in history; five bundled examples had not run.
- ntfy's root is a subscription page. The configured topic already contained
  retained notifications. No artificial notification was created to fill it.
- OmniRoute had recorded usage despite zero compression savings. The correct
  usage page avoids confusing two different meters. No new gateway request was
  made to populate its charts.
- Grafana lacked memory/RAG and savings panels. The small local adapter reads
  actual upstream output and emits only selected metadata through Loki's native
  API. Source time and measurement scope remain visible.

The [data receipt](../evidence/receipts/native-dashboard-data-20260921.json) records
the changed behavior and actual observations. Native UI integration checks and
local adapter tests are separate from the upstream projects' own test suites.

## Memory and RAG: upstream commands

The [current memory/RAG qualification](memory-rag-native-practice.md) enables
upstream local semantic memory, repairs code-index scope and refreshes the
unchanged upstream graph. The memory panel shows embedding mode, stored rows,
missing latest-page vectors and unresolved failures. Stored vectors can include
superseded page versions; compare coverage with latest pages instead of assuming
the two totals must match. Browser wiki search remains FTS5; semantic recall uses
MCP. LLM consolidation remains disabled.

ai-memory 2.3.2 bundles its UI. Keep the existing server's store, scope, authentication
and loopback address; preserve its full command and add the supported `--enable-web`
flag if absent. Check the active service override, not only the base unit.

```sh
ai-memory serve --help
ai-memory status --json
systemctl --user restart ai-memory.service
```

`status --json` reports database-wide counters; it does not select a project.
Use the project-scoped UI or native `memory_status`/`memory_query` MCP calls when
project-specific observations are needed. The bundled browser search is global
FTS search; it does not inherit scope from the project page. The actual UI search returned
existing pages, and opening a result rendered its article. No page body is published
in the receipt. Official instructions:
[ai-memory usage](https://github.com/akitaonrails/ai-memory/blob/v2.3.2/docs/usage.md#browse-the-wiki-in-a-browser).

The adopted QMD collection uses local lexical search without downloaded models:

```sh
qmd --index agent-lab-docs status
qmd --index agent-lab-docs search Qdrant -c agent-lab-docs -n 3 --json
qmd --index agent-lab-docs get qmd://agent-lab-docs/native-rag-runtime.md
```

These are this PC's adopted names. Another repository needs its own explicit
collection and index. A zero embedding count is intentional for this BM25 lane.
[QMD upstream](https://github.com/tobi/qmd).

SocratiCode provides native `codebase_search` and `codebase_graph_visualize` tools.
Use the selected project's installed server and `mode: "interactive", open: false`
for the upstream graph. The retained observation returned real semantic search
hits and generated the interactive file/symbol/call graph. Its source is a snapshot;
the existing MCP watcher continues to maintain the index separately.
[SocratiCode upstream](https://github.com/giancarloerra/SocratiCode).

The adopted CLI bridge now uses an ephemeral SocratiCode entry with
`SOCRATICODE_WATCHER=off` and `SOCRATICODE_AUTO_RESUME=off`. This avoids a retired
MCPorter daemon blocking one-shot reads. Only those three settings changed;
the native Desktop MCP watcher remains active. The repaired documented command
returned three actual hits, independently matched to the MCP result and source:

```sh
mcporter --config "$PROJECT_MCPORTER_CONFIG" call socraticode.codebase_search \
  --args '{"projectPath":"/home/example/code/project","query":"cumulative token savings report native counters","limit":3,"includeLinked":false}' \
  --output json --no-oauth
```

Serena's saved project launchers enable its upstream web dashboard while
keeping automatic browser opening disabled and the listener on loopback. The
current Desktop connection's supported `open_dashboard({})` returned a working
upstream view showing the active project and tools. Its URL differs from the
short-lived native children's expired URL: the port belongs to a particular MCP
process. Discover it from the current connection each time; do not reuse a saved
port or treat a returned URL as proof that a child process remains alive. A
server originally started with the dashboard disabled still needs a normal MCP
reload to enable it; no restart was needed for this current connection.

Qdrant exposes actual collection state and counts through its supported API:

```sh
curl --fail http://127.0.0.1:16333/collections
curl --fail "http://127.0.0.1:16333/collections/$SELECTED_COLLECTION"
```

Use the chosen collection name. Do not sum the same point's dense and sparse vector
metrics as two chunks. The existing native Prometheus scrape supplies Qdrant and
local embedding-server metrics to Grafana without a new inference request.
[Qdrant collection API](https://api.qdrant.tech/api-reference/collections/get-collection).

## Exact native archive refresh

Use an explicitly selected native source file, not a scan of the whole home:

```sh
agentsview session sync "$SELECTED_NATIVE_SESSION_FILE" \
  --server http://127.0.0.1:17384
```

Since 2026-09-27 the workstation's archive unit requires a token
([token on the archive API](native-dashboards.md#token-on-the-archive-api-2026-09-27)).
Set `AGENTSVIEW_DATA_DIR` to the archive and drop `--server`, or add `--server-token-file`.

The installed 0.43.0 command returns a human-readable sync status. It calls the
existing server and does not start another daemon. This wave selected this Codex
conversation and two recent Claude files in the same agent-lab project. The three
native API identities and source metadata were independently checked after import.
Use returned archive IDs for links; Claude IDs are plain UUIDs here, whereas Codex
IDs carry a `codex:` prefix. A file still being written requires another explicit
refresh to include later events. Source:
[upstream single-session sync](https://github.com/kenn-io/agentsview/blob/v0.43.0/cmd/agentsview/session_sync.go).

## Savings: keep each upstream meter separate

```sh
rtk gain --format json
rtk gain --project --format json
headroom savings --json
ecosystem-token-report refresh
```

Run the project RTK command from the chosen working directory. Its result is a
subset of the global retained history, not an additional saving. Headroom's native
report covers its reported window. jCodeMunch's native statistics and the exact
MCPorter call are in the [portable reporter guide](../tools/token-report/README.md).
In the active Context Mode MCP connection use `ctx stats`; its byte/event estimates
and illustrative prices are not measured provider savings. Server-reported session
boundaries can differ from the full Codex conversation.
Context Mode's retained-event estimate and session byte estimate use different
formulas; a larger session estimate does not establish a counter regression or
additional provider savings. Keep the native formula labels with both values.

The foundation view refreshes fresh RTK/database/document/collection observations;
it reads other counter scopes from the existing report and displays their source
times. Its savings trend panel (changed after `v2026.09.26.2`) draws each native
scope as its own series and never adds scopes together; a step whose newest row for
a scope failed or is stale is a gap, and its legend carries no value. A newly
delivered snapshot does not make an old persisted counter current.
Unknown or failed sources never become zero, and a previous successful value does
not silently replace a current failure. The source report retains its native raw
outputs privately. Neither this dashboard nor TOON defines a universal lifetime
provider-savings counter for all repositories.

## Persistent native observation on another PC

The [adapter guide](../observability/native-data/README.md) defines explicit paths,
selected commands and the private state directory. It uses the existing upstream
[Loki JSON ingestion API](https://grafana.com/docs/loki/latest/reference/loki-http-api/#ingest-logs)
and [Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/#dashboards).
Do not copy private databases, sessions or credentials from this machine.

Generate the dashboard into the existing Grafana provisioning directory:

```sh
python3 observability/native-data/render.py --output "$GRAFANA_DASHBOARD_DIRECTORY/native-foundation-data.json"
python3 observability/native-data/snapshot.py --config "$NATIVE_DATA_CONFIG" --publish
```

Use the supplied native user-service/timer examples with absolute paths resolved
on that PC. The adapter guide's [scheduled deployment](../observability/native-data/README.md#scheduled-deployment)
(changed after `v2026.09.26.2`) names the private config and state paths, the unit
placeholders, the `stale_after_seconds` choice and the native undo commands. Its
`report_scopes` and `ai_memory.server_url` keys cover a token report with other
scope labels and an ai-memory server on another port. The timer only observes selected data; it does not run research,
inference, reindexing, session imports or broker orders. It also does not refresh
the whole token ledger on each tick. Run the report's existing refresh command
after meaningful efficiency work or when current full reporting is requested.

The selected HTML artifacts are served unchanged by Python's standard module:

```sh
python3 -m http.server 17500 --bind 127.0.0.1 --directory "$SELECTED_ARTIFACT_DIRECTORY"
```

This directory contains only the intended graph, token report and Promptfoo export.
Use the [native service example](../observability/native-data/native-reports.service.example)
for persistence. It is a local static artifact host, not another agent framework.
[Python upstream HTTP server documentation](https://docs.python.org/3.12/library/http.server.html).

The installed Grafana root now opens the foundation view through upstream
`dashboards.default_home_dashboard_path`; the original dashboard retains a link.
The [home setting](../observability/native-data/grafana-home.ini.example),
[service](../observability/native-data/native-data.service.example) and
[two-minute timer](../observability/native-data/native-data.timer.example) are
portable examples. Resolve placeholders into owned absolute paths, preserve the
existing Grafana settings, then use native lifecycle commands:

```sh
systemd-analyze --user verify "$NATIVE_DATA_SERVICE" "$NATIVE_DATA_TIMER" "$NATIVE_REPORTS_SERVICE"
systemctl --user daemon-reload
systemctl --user enable --now ecosystem-native-data.timer ecosystem-native-reports.service
systemctl --user start ecosystem-native-data.service
systemctl --user show ecosystem-native-data.service --property=Result,ExecMainStatus
systemctl --user show ecosystem-native-data.timer --property=ActiveState,LastTriggerUSec
```

These service names refer to the installed examples on this PC. Native verification,
successful execution, enabled state and later timer execution were observed;
a physical-PC reboot was not tested in this wave.

## Native evaluation report

Promptfoo 0.123.1 can import a retained result into an explicitly selected private
profile and export its own HTML without launching another network listener:

```sh
export PROMPTFOO_CONFIG_DIR="$OWNED_PROMPTFOO_PROFILE"
export PROMPTFOO_LOG_DIR="$OWNED_PROMPTFOO_LOGS"
promptfoo import "$EXISTING_RESULT_JSON"
promptfoo export eval "$RETURNED_EVAL_ID" --output "$SELECTED_ARTIFACT_DIRECTORY/promptfoo.html"
```

This wave imported and exported the existing local deterministic fixture: two
passing assertions, no new evaluation or provider request. The browser rendered
both result rows and the pass count. The native HTML can include fixture-local
paths, so it remains loopback-only and is not committed. Upstream implementation:
[export command](https://github.com/promptfoo/promptfoo/blob/0.123.1/src/commands/export.ts),
[HTML renderer](https://github.com/promptfoo/promptfoo/blob/0.123.1/src/util/output.ts).

## Full foundation coverage

The Grafana repository table and [full HTML report](http://127.0.0.1:17500/token-savings.html#tools)
retain all 68 selected components and their native command/evidence boundaries.
The original audit status and newer canonical receipt count are separate columns.
The table date is report generation, not the date each native check ran; open the
full report and receipt to inspect its exact acceptance scope. A receipt count
alone never means the component passed this session.
Catalog membership, an installed CLI and a populated dashboard are different facts.
The [twenty foundation layers](../catalogs/foundation/README.md) remain the overall map:

| Foundation layer | Appropriate native observation |
| --- | --- |
| Native clients | Codex/Claude interfaces, typed telemetry, selected session archive |
| Instructions and skills | Native discovery and pinned skill files; guidance has no runtime dashboard |
| Workers and ownership | Native client worker views, selected session history, recorded research checkpoints |
| Isolation | Native Git/worktree/process commands; task ownership evidence |
| Code navigation | SocratiCode graph, Serena, structural/search CLI results |
| Documents and ingestion | Scoped QMD search/get, native document-conversion output |
| Semantic RAG | SocratiCode search, official Qdrant UI, local embedding-server metrics |
| Durable memory | Official ai-memory wiki, scoped query and database/project counters |
| Web research | Native Tavily/research CLI results; hosted account dashboards remain account-specific |
| Token efficiency | RTK, Context Mode, Headroom and jCodeMunch native meters; separate provider usage |
| Quality and evaluation | Native evaluation reports and available upstream result viewers |
| CI and supply chain | Actual GitHub Actions runs, native scanner output and retained receipts |
| Scheduling and supervision | Dagu run history and native service/timer state |
| Hosting | Each selected service's own API/UI; unused libraries are not services |
| Recovery and portability | Native backup/restore results and dated independent-host evidence |
| Observation and inference | Grafana/Prometheus/Loki/ntfy and optional inference/gateway views |

This view does not activate unused alternatives or claim all optional/domain
repositories are executing in every conversation. It makes the selected native
data inspectable and leaves untested boundaries visible.
