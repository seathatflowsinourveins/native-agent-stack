# Native dashboard metadata

This small local adapter projects existing upstream output into Grafana Loki. It
does not provide a new service or replace the native tools, token report, memory
UI or QMD index. It runs no model, embedding, provider usage parser, indexing or
token-report refresh. A snapshot is a current observation of the selected native
commands plus explicitly dated existing report data.

Copy `config.example.json` to a private location, supply absolute installed
binaries and owned paths, and create the state directory with mode `0700`.
Run from the repository root:

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
| RTK 0.49.0 | `rtk gain --format json`; `rtk gain --project --format json` | Global retained history and the explicit project working directory, separately |
| ai-memory 2.3.2 | `ai-memory --data-dir <configured-db> status --json` | Entire configured database: current pages, all versions, sessions, observations; allowlisted embedding mode and native completeness counts; memory LLM status |
| QMD 2.8.3 | `qmd --index <configured-index> status` | Selected collection file count; index file/vector totals kept separately |
| Qdrant | `GET /collections/<allowlisted-collection>` | Native `points_count`, segments and collection status |
| Other token tools | Existing report `native[].latest` | Three Context Mode runtime roots, Headroom and jCodeMunch |
| Coverage | Existing report `coverage_matrix` | Up to 68 allowlisted public component identifiers, dated historical status |

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
`qdrant`. Coverage identifiers prepend `coverage-` and replace repository `/`
with `--`. A final `snapshot` row carries `row_count` (excluding itself),
`unknown_count` and `stale_count`. Every row shares one `observed_unix` generation.
Consumers must select that latest generation before displaying values; filtering
only successful measurements would resurrect earlier values after a failure.
Only `service_name=agent-stack-native-data` and `record_kind` are Loki labels.

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

Focused offline verification:

```sh
python3 -m unittest discover -s tests -p test_native_dashboard_data.py -v
```

Tests retain source-shaped RTK, ai-memory and QMD metadata examples and cover
failed-latest handling, stale/future timestamps, duplicate sources, numeric
validation, explicit collection selection, payload privacy, private files,
command failures/deadlines/output bounds and loopback-only publication. They do
not establish service uptime or an actual Loki publication; deployment and
browser checks belong to the integrating task.
