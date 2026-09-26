# Native dashboard metadata

This small local adapter projects existing upstream output into Grafana Loki. It
does not provide a new service or replace the native tools, token report, memory
UI or QMD index. It runs no model, embedding, provider usage parser, indexing or
token-report refresh. A snapshot is a current observation of the selected native
commands plus explicitly dated existing report data.

Copy `config.example.json` to a private file outside every checkout, supply
absolute installed binaries and owned paths, and create the state directory
with mode `0700`. A host that uses the [native backends](../backends/README.md)
roots keeps the config at `$STACK_CONFIG_ROOT/native-data.json` (mode `0600`,
normally `~/.config/ecosystem-observability/native-data.json`) and the state at
`$STACK_DATA_ROOT/native-data` (normally
`~/.local/share/codex-ecosystem/observability/native-data`), beside the grand
dashboard's cache. Run from the repository root:

```sh
python3 observability/native-data/snapshot.py --config /absolute/private/config.json
python3 observability/native-data/snapshot.py --config /absolute/private/config.json --publish
```

Publishing uses only `http://127.0.0.1:13100/loki/api/v1/push`. Optional Qdrant
configuration is an explicit literal loopback origin and one collection, for
example `{"url":"http://127.0.0.1:16333","collection":"selected-collection"}`.
HTTP proxies and redirects are disabled. There is no authentication discovery,
collection enumeration or automatic service activation. Native tools retain
their existing account and configuration behavior.

| Source | Supported native read | Published scope |
| --- | --- | --- |
| RTK 0.50.0 | `rtk gain --format json`; `rtk gain --project --format json` | Global retained history and the explicit project working directory, separately (the JSON keys are unchanged from 0.49.0; 0.50.0 clamps negative savings rows to 0) |
| ai-memory 2.4.1 | `ai-memory --data-dir <configured-db> status --json` | Entire configured database: current pages, all versions, sessions, observations; allowlisted embedding mode and native completeness counts; memory LLM status |
| QMD 2.8.3 | `qmd --index <configured-index> status` | Selected collection file count; index file/vector totals kept separately |
| Qdrant | `GET /collections/<allowlisted-collection>` | Native `points_count`, segments and collection status |
| Other token tools | Existing report `native[].latest`, selected by `report_scopes` | Up to three Context Mode runtime roots, Headroom and jCodeMunch |
| Coverage | Existing report `coverage_matrix` | Up to 68 allowlisted public component identifiers, dated historical status |

ai-memory 2.4 `status` is an HTTP client of the running server: it calls
`GET /admin/status` at its configured `server_url`, whose upstream default is
`http://127.0.0.1:49374` (v2.4.1 `commands/status.rs` and `config.rs`). A server
on another loopback port needs `ai_memory.server_url`, an exact
`http://127.0.0.1:<port>` origin that the collector passes to that one command
as `AI_MEMORY_SERVER_URL`. Without it, a server elsewhere leaves the row unknown
after the command deadline. A server that requires a bearer token is out of
scope: the collector never reads credentials.

`report_scopes` maps each report entity id to the exact `scope` of one
`native[]` entry in the token report. A Context Mode scope is that report's
`context_roots[].name`, Headroom's is its `counter_scopes.headroom` (reporter
default `Native / last 30 days`) and jCodeMunch's is always
`Linux / upstream default index`. Leave out an entity whose runtime root the
report does not capture; it then emits no row. Without the key the collector
keeps the authoring host's labels (`Native Codex`, `Native Claude`,
`Desktop WSL`, `Linux / native last 30 days`), and a report with other labels
leaves those rows unknown. The labels stay in the private config: rows carry
only the fixed entity id and title.

The ai-memory CLI status command has no workspace/project selector. Those two
config fields document the intended workspace privately; they do **not** filter
its database-wide counts. The native scoped MCP `memory_status` and the memory
web UI remain the interfaces for project-specific observations. No page content,
provider configuration objects, endpoints, credentials, diagnostic text, database
path or scope name is sent to Loki. The memory row includes only reviewed status
values (`ok`, `disabled`), the `local` embedding provider, the known public model
`all-MiniLM-L6-v2`, bounded dimensions, and native `embedding_rows`,
`latest_pages_missing_embeddings`, and `embed_failures_unresolved` counts. These
are fields returned by the native command, not calculated retrieval scores.
Grafana shows the mode, completeness counts and memory LLM status together.
Missing or unreviewed string fields become `unavailable`; absent or malformed
optional numbers become `null` (displayed as `—`), never zero. An older status
schema therefore preserves its valid inventory without implying embedding
readiness. Extending the provider/model allowlist requires source review.
Complete embedding coverage is not evidence of retrieval relevance, and a
disabled memory LLM means consolidation is not enabled by this collector. QMD can
operate in BM25 mode with zero vectors; the adapter never downloads models or
recommends that zero means failure.

All rows contain `schema_version`, `record_kind`, `entity_id`, `title`, `state`,
`source_updated_at`, `source_unix`, `observed_unix`, `source_command`, `kind` and
`boundary`. Commands in public rows are fixed templates without private paths.
States are `ok`, `stale`, `unknown` or `historical`. Successful measurement rows
include `value` and `unit`; savings rows also include `estimated_saved` and, only
when actually reported, `session_estimated_saved`. Counts use source-specific
fields such as `pages_latest`, `collection_files` or `points_count`.

Stable measurement identifiers are `rtk-global`, `rtk-project`,
`context-mode-native-codex`, `context-mode-native-claude`,
`context-mode-desktop-wsl`, `headroom`, `jcodemunch`, `ai-memory`, `qmd` and optional
`qdrant`; the five report identifiers appear as `report_scopes` selects them.
Coverage identifiers prepend `coverage-` and replace repository `/`
with `--`. A final `snapshot` row carries `row_count` (excluding itself),
`unknown_count` and `stale_count`. Every row shares one `observed_unix` generation.
Consumers must select that latest generation before displaying values; filtering
only successful measurements would resurrect earlier values after a failure.
Only `service_name=agent-stack-native-data` and `record_kind` are Loki labels.
The dashboard's tables show that latest generation. Its savings trend panel
draws each savings row as its own series, grouped only by `entity_id`, with a
three-minute minimum step and no stacking. A step shows a scope's estimate only
when that scope's newest row in the step is ok: the panel keeps
`last_over_time(... | state="ok" | unwrap estimated_saved ... [$__interval]) by (entity_id)`
only where the newest ok row's `observed_unix` equals the newest row's. A step
whose newest row failed or is stale is therefore a gap, never an earlier
success, and no scope is added to another. The legend names the series without
values; the savings table above the panel holds each scope's current value and state.

Fresh native inventory/RTK rows use command completion time. Context Mode uses
its actual persisted `updated_at` milliseconds converted to seconds. Headroom and
jCodeMunch use the native command capture time in the existing report because
their returned counters have no equivalent source-update timestamp. These bases
are explicit in `timestamp_basis`. Report rows retain `source_capture_unix` and
`report_file_unix` separately. A freshly copied report cannot refresh an old
Context Mode counter. Missing, malformed, future or failed measurements are
unknown, with numeric measurement fields omitted; `latest_success` is never a
fallback. Old valid measurements are marked stale after the configured interval.

These estimates overlap. Global RTK includes its project subset. Context Mode's
latest persisted file is one snapshot within a runtime root, not the sum of every
process or session. Retention and restarts can decrease counters. RTK's native
clamped savings value is preserved even when it differs from net input minus
output. No estimate is added to another, converted to money, or called avoided
provider usage. Provider usage belongs in its separately scoped native dashboard.
Historical coverage is not current health or a new acceptance test.
Its original audit status and canonical receipt count are separate fields;
`original_audit_has_record` means a record exists, not that its outcome passed.
Coverage dates use `token_report_generated_at`, not the native execution date.

`snapshot.json`, exact native stdout/stderr, HTTP response bytes and hashes stay
in the private state directory with mode `0600`. Command records include argv,
cwd, start/end timestamps, exit status and failure category. Files describe the
latest attempt, not an accumulating transcript archive. A nonblocking file lock
prevents overlapping collectors. Each command has a finite deadline and each
stream a 1 MiB limit; an overflow retains a declared prefix, never claims a full
output. Timeout/launch/nonzero/parse failures remain unknown. The report read is
bounded to 16 MiB. The compact console result binds generation, snapshot bytes and
SHA-256, payload SHA-256, row states and actual Loki HTTP status. Publishing
requires HTTP 204; source failures still produce a snapshot, while publication
failure exits 1 and invalid configuration exits 2. Keep the entire state directory
out of published artifacts.

The JSON push envelope follows the [official Loki HTTP API](https://grafana.com/docs/loki/latest/reference/loki-http-api/#ingest-logs),
using string nanosecond timestamps and JSON log lines. Source command references:
[RTK analytics](https://github.com/rtk-ai/rtk/blob/develop/docs/guide/analytics/gain.md),
[ai-memory](https://github.com/akitaonrails/ai-memory),
[QMD](https://github.com/tobi/qmd),
[Qdrant collection details](https://api.qdrant.tech/api-reference/collections/get-collection),
[Context Mode](https://github.com/mksglu/context-mode). The projection and guards
are local integration code, not an official upstream dashboard or E2E suite.

## Scheduled deployment

This section, the `report_scopes` and `ai_memory.server_url` keys and the
savings trend panel changed after `v2026.09.26.2`; at that tag the service example
set no `PATH` and the collector read only the authoring host's report labels.

[`native-data.service.example`](native-data.service.example) and
[`native-data.timer.example`](native-data.timer.example) run one collection every
two minutes as a `systemd --user` timer. Replace `@REPOSITORY@` with a checkout that
stays in place at a revision containing this adapter, `@PRIVATE_CONFIG@` with the
private config and `@NODE_DIRECTORY@` with a directory that holds Node 22 or later
for QMD's `env node` launcher. Install the results as
`~/.config/systemd/user/ecosystem-native-data.service` and `.timer`, then use the
native lifecycle commands:

```sh
systemd-analyze --user verify ~/.config/systemd/user/ecosystem-native-data.service ~/.config/systemd/user/ecosystem-native-data.timer
systemctl --user daemon-reload
systemctl --user start ecosystem-native-data.service
systemctl --user show ecosystem-native-data.service --property=Result,ExecMainStatus
systemctl --user show ecosystem-native-data.timer --property=UnitFileState,ActiveState
systemctl --user enable --now ecosystem-native-data.timer
```

Render the dashboard into the backends' dashboard folder. Their file provider
rescans it every 30 seconds, so Grafana needs no restart and no API credential:

```sh
python3 observability/native-data/render.py \
  --output "$STACK_CONFIG_ROOT/ecosystem-grafana-dashboards/native-foundation-data.json"
```

That provider sets `disableDeletion: true`. Deleting the file later only
unprovisions the dashboard (Grafana 13.2.2 `handleMissingDashboardFiles` in
`pkg/services/provisioning/dashboards/file_reader.go`); removing the remaining copy
is an administrator action inside Grafana.

To undo the deployment, disable the timer, remove the installed units and the
dashboard file, then reload the user manager. Undo only what the deployment
changed ([lifecycle](../../adoption/lifecycle.md)): `enable --now` can change
the timer's enablement, its activation or both, so undo each against the state
read before it. Disable the timer only if it was not enabled before, and stop it
only if it was not active before. If it was already enabled, restore its earlier
unit files instead of removing them; if it was enabled but inactive, also stop it
with `systemctl --user stop ecosystem-native-data.timer`.

```sh
systemctl --user disable --now ecosystem-native-data.timer
systemctl --user stop ecosystem-native-data.service
rm ~/.config/systemd/user/ecosystem-native-data.service ~/.config/systemd/user/ecosystem-native-data.timer
rm "$STACK_CONFIG_ROOT/ecosystem-grafana-dashboards/native-foundation-data.json"
systemctl --user daemon-reload
```

The private config and state directory hold no credential and stay until you
remove them. Rows already pushed expire with Loki's retention.

Choose `stale_after_seconds` from the token report's refresh cadence, because
report rows keep their own capture or source time. A daily report needs the
`86400` maximum, which still marks rows stale when one run starts more than a day
after the previous one. The four-times-daily
[refresh template](../../tools/token-report/README.md#optional-scheduled-refresh)
needs `28800`. A Context Mode row is also stale when its runtime wrote no newer
stats file within that interval. Fresh RTK, ai-memory, QMD and Qdrant rows are
unaffected.

Focused offline verification:

```sh
python3 -m unittest discover -s tests -p test_native_dashboard_data.py -v
```

Tests retain source-shaped RTK, ai-memory and QMD metadata examples and cover
failed-latest handling, stale/future timestamps, duplicate sources, numeric
validation, explicit collection selection, report scope selection, the
ai-memory server origin, payload privacy, private files,
command failures/deadlines/output bounds, loopback-only publication, the unit
examples, the per-scope savings series query with its newest-row guard and the
documented undo order. They do
not establish service uptime or an actual Loki publication; deployment and
browser checks belong to the integrating task.

## Per-model Claude token usage

The collector keeps the `model` attribute on Claude Code token counters, so a
per-model view needs only a query change, not a pipeline change. The rendered
dashboard still sums by `type`; the per-model form, kept here as a documented
follow-up for the render step, is:

```promql
sum by (model, type) (increase(ecosystem_claude_code_token_usage_tokens_total{job="claude-code"}[$__range]))
sum by (model, type, query_source) (increase(ecosystem_claude_code_token_usage_tokens_total{job="claude-code"}[$__range]))
```

`query_source` separates the coordinator (`main`) from workflow children
(`subagent`) and auxiliary calls. The collector keeps no session id on metrics and
`instance` is not the session id; to scope one run, launch it with
`OTEL_RESOURCE_ATTRIBUTES=ecosystem.client.scope=<run name>`, which the collector
keeps as the `client_scope` label, and query `{client_scope="<run name>"}`. That is
how the dated qualification scoped its headless runs. Per-child
provider usage inside one native Workflow run comes from
`examples/claude-native/workflows/child-usage.mjs`, which reads the run's
transcript directory; its counters are provider-returned and are not the same
quantity as the exported metric (type names differ, streaming partials are
counted per response by the exporter and once per message id by the script).
