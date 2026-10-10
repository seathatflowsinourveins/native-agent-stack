# Native Fleet tracking observations

Fleet presents current hcom registrations separately from historical telemetry
labels, native token categories, per-lane invocation observations and scoped
local service observations. Its maintained collector and view use native
roster, Prometheus, Loki and user-manager interfaces without replacing the
upstream clients, exporters, metric calculations or dashboards.

The supported hcom projection is selected from installed 0.7.28 at source pin
`b2a7c192003e7fd67ed93265289e4ac36276f965`:
[list.rs](https://github.com/aannoo/hcom/blob/b2a7c192003e7fd67ed93265289e4ac36276f965/src/commands/list.rs).
It captures name, base name, client, tag, status, status age and creation time.
The formatter does not escape delimiters; unexpected field counts and invalid
fields cannot silently become a complete roster. The command needs no fixed
sender identity; launching/error are valid states, malformed rows are rejected
individually with partial coverage explicit, and creation epochs display as
UTC. Full JSON private fields,
prompts, configuration and argv are excluded. Historical telemetry labels
remain separate from live roster observations.

Native Prometheus at port 21090 uses the `ecosystem_lane` label without an
`ecosystem_` metric-name prefix. Native Codex token categories are input,
cached_input, cache_write_input, output, reasoning_output and total; native
Claude categories are input, output, cacheCreation and cacheRead. Preserve all
categories separately to avoid double counting. Codex API attempts, general
tool calls and MCP calls use distinct independently qualified counters. Codex
token and invocation counter rates remain lower bounds until deployed
start-timestamp ingestion and the newly born writer reconciliation pass.
Unqualified rate zeros remain UNKNOWN; valid service-state zeros stay reported.
API events and tool-result records cannot establish MCP-call counts.
Unqualified skill/agent and Claude MCP sources remain UNKNOWN.

The supported Prometheus `rate` function handles counter resets before
aggregation. The five-minute window is explicit. The freshness companion
`timestamp(counter)` returns the selected scrape timestamp as its sample value;
the API timestamp remains query evaluation time. Successful empty results are
missing data rather than zero, and stale/future/nonfinite observations are
unknown. Freshness is the latest selected writer scrape, not last usage or
proof that every writer was observed. Primary API/functions/lookback docs:
[API](https://prometheus.io/docs/prometheus/latest/querying/api/),
[functions](https://prometheus.io/docs/prometheus/latest/querying/functions/),
[lookback](https://prometheus.io/docs/prometheus/latest/querying/basics/),
fetched 2026-10-09T20:31:32Z through 20:31:52Z.

Native Loki is on port 21300, selected by
observability/grand-dashboard/README.md; default port 13100 can reach the other
distribution. The existing lanes_dashboard.py selections provide Claude
api_request and tool_result records. Numeric instant queries use native
`rate(...[5m])` before grouping by ecosystem_lane, excluding empty lane labels
and instance="unscoped". Loki returns reported exported records/second within
the explicit query window; these are distinct from all API attempts, completed
turns or MCP calls. Failed results and outer code-mode result records remain
within the tool-result scope. Missing, invalid or zero rates remain UNKNOWN.

Loki's vector timestamp is query evaluation time, not last event time. The page
shows `(evaluation - 300 seconds, evaluation]` and leaves event freshness
unreported. Native log rate includes the first event; it is distinct from
Prometheus counter-rate startup behavior. Primary Loki 3.7.8 source pin
`09e6ce2ff1bdc19763a10265b870c86f51c98655` supplies the
[metric instant API](https://github.com/grafana/loki/blob/09e6ce2ff1bdc19763a10265b870c86f51c98655/docs/sources/reference/loki-http-api.md),
[LogQL functions](https://github.com/grafana/loki/blob/09e6ce2ff1bdc19763a10265b870c86f51c98655/docs/sources/query/metric_queries.md)
and [native log-rate implementation](https://github.com/grafana/loki/blob/09e6ce2ff1bdc19763a10265b870c86f51c98655/pkg/logql/range_vector.go).
Only bounded numeric vectors are requested; raw log streams and diagnostics
are never projected. HTTP protocol failures use safe exception categories.

Existing recorded endpoints and native metadata distinguish service scopes.
The installed systemd 259 client restricts `show` to LoadState, ActiveState,
SubState and UnitFileState of `vllm-embed.service`. It never requests unit
bodies, Environment, ExecStart, argv or paths. Those states do not establish
model readiness or an endpoint binding. Hindsight's port 8888 `/health` is a
DB-reachability check at primary source pin
`5fc4ce20917b916240cef27c212c387a177f115b`:
[monitoring contract](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs/developer/monitoring.md).
Installed ai-memory 2.6.0 supersedes the repository's 2.4.1 lead; its recorded
port 29374 `/healthz` measures process-listening liveness only at source pin
`89bd8ded3c1ab8b769cf99417d038ed0364403c8`:
[serve contract](https://github.com/akitaonrails/ai-memory/blob/89bd8ded3c1ab8b769cf99417d038ed0364403c8/crates/ai-memory-cli/src/commands/serve.rs).
The current vLLM port 28231 is measured by the command center. Its body-unread
`/v1/models` status probe observes model-list API reachability, independently
of named-unit state and the Prometheus scrape. The vLLM 0.25.0
[model-list handler](https://github.com/vllm-project/vllm/blob/702f4814fe54fabff350d43cb753ae3e47c0c276/vllm/entrypoints/openai/models/api_router.py)
at `702f4814fe54fabff350d43cb753ae3e47c0c276` is a reference baseline, not an
installed-version or model-identity claim. No HTTP status establishes inference
or embedding readiness. Health/model-list response bodies remain unread.

The optional workstation memory reader also catches HTTPException alongside
transport failures, preserving the original CC values and their dates. Public
error observations contain exception categories without transport payloads.

Grafana at port 21301 retains the existing verified dashboard navigation and
per-lane Explore links. PromQL uses ns2604-prometheus; Claude LogQL uses
ns2604-loki. Each pane carries its datasource, query and observation range.
The pinned Grafana 13.2.3 source
`6193dc03311b631b9727b560d24369e683dc396e` documents
[panes JSON, schemaVersion=1 and epoch-millisecond ranges](https://github.com/grafana/grafana/blob/6193dc03311b631b9727b560d24369e683dc396e/docs/sources/visualizations/explore/get-started-with-explore.md),
with the [native URL serializer](https://github.com/grafana/grafana/blob/6193dc03311b631b9727b560d24369e683dc396e/public/app/core/utils/explore.ts)
and [state types](https://github.com/grafana/grafana/blob/6193dc03311b631b9727b560d24369e683dc396e/packages/grafana-data/src/types/explore.ts).
No dashboard variables, organization ID or live availability are invented.

Native source provenance is the repository observability implementation at
`a7bb4a51eea9cc321dd06dd6243a5b2654a5f805`, installed client/version metadata,
primary source pins/docs and bounded anonymous read-back. The stdlib/native
HTTP and CLI seams introduce no package or billing surface. Independent
synthetic transports test empty/failed/invalid/stale sources, row conservation,
counter categories, private field projection, links and complete markup.
Actual native receipts establish only the source observations at their UTC;
they do not promote trading gates, platform acceptance or model readiness.

Rejected alternatives: rebuilding native dashboards/exporters, scanning raw
agent transcripts/configuration/unit bodies, adding a general monitoring
client for fixed supported APIs, guessing missing counters or interpreting
scrape success as model readiness. A maintained upstream interface that covers
these exact source scopes with a smaller tested surface, or a reproduced
counterexample under the native/synthetic checks, would overturn the seam.
