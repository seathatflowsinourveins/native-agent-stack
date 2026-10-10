# Native Fleet tracking observations

The existing Fleet snapshot omits newer hcom lane registrations and has no
per-lane token/MCP rates or scoped local-model service observations. Extend its
maintained collector and view using the native roster, observability APIs and
user-manager property interface. Do not replace the upstream clients,
exporters, metric calculations or dashboards.

The supported hcom projection is selected from installed 0.7.28 at source pin
`b2a7c192003e7fd67ed93265289e4ac36276f965`:
[list.rs](https://github.com/aannoo/hcom/blob/b2a7c192003e7fd67ed93265289e4ac36276f965/src/commands/list.rs).
It captures name, base name, client, tag, status, status age and creation time.
The formatter does not escape delimiters; unexpected field counts and invalid
fields cannot silently become a complete roster. Full JSON private fields,
prompts, configuration and argv are excluded. Historical telemetry labels
remain separate from live roster observations.

Native Prometheus at port 21090 uses the `ecosystem_lane` label without an
`ecosystem_` metric-name prefix. Native Codex token categories are input,
cached_input, cache_write_input, output, reasoning_output and total; native
Claude categories are input, output, cacheCreation and cacheRead. Preserve all
categories separately to avoid double counting. Only the independently
qualified native MCP counter supplies MCP rates; API attempts and tool-result
records do not establish them. Unqualified client counters remain UNKNOWN.

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
The documented old vLLM port 8231 is not independently bound to the named
service. A reference vLLM 0.25.0 health contract at
`702f4814fe54fabff350d43cb753ae3e47c0c276` is a baseline, not an installed-version
claim. HTTP status and independent Prometheus scrape observations retain these
limits; health response bodies are unread.

Grafana's recorded anonymous Viewer API at port 21301 supplies metadata for
the existing cc-lanes, ecosystem-native and native-foundation-data dashboards.
The [documented search API](https://grafana.com/docs/grafana/latest/developer-resources/api-reference/http-api/folder_dashboard_search/)
was fetched 2026-10-09T20:40Z. Links retain the safe recorded origin and supported
dashboard paths; a dashboard lane-variable contract is unqualified, so no
variable parameter is fabricated. No dashboard is rebuilt.

Native source provenance is the repository observability implementation at
`3a4cc28840ba7e8a1a9474a989102a669955f243`, installed client/version metadata,
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
