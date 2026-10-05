# NativeStack2604 G4 observability plan repair — 2026-10-04

North-star action served: finish the foundation's native observation and alert
delivery path before US-equities research and historical simulation. This is a
bounded plan repair on PR #684's head, not a new distribution, provider or model run.
The builder leaves working-tree changes and a commit message; the coordinator
owns `manifests/evidence.json`, selection reconciliation and destination execution.

## Inputs and verified sources

The private coordination inputs were read without opening authentication or
credential stores. `fixes.json` and standalone `review-observe-eval-*.json` were
not present at the supplied directory. The original `observe-eval-1.json`,
`observe-eval-2.json`, `adjudication.json`, and the reviews' `final_response` fields
in `review/observe-eval-{1,2}/out.jsonl` supply the bounded findings. The alerting
adjudication overrides its mistaken unit assignment: alerting belongs to
`observe-eval-2`, not `observe-eval-1`. The earlier repair's `report.json`,
`plan-fix.patch` and `apply-2604.sh:31-49` were inspected; only its exact collector
queue migration is ported. Its other owners' changes and host operations are not
part of this patch.

Primary source was fetched again on 2026-10-04. The selected releases remain the
versions already used by the verified E2E, rather than introducing an unqualified
upgrade. The release APIs and annotated tag objects resolve Collector Contrib
v0.162.0 to `ae8c507510f48f433ab47dd1c6b01a59d6c388b5` and Grafana v13.2.3 to
`6193dc03311b631b9727b560d24369e683dc396e`.

- Collector install: [official binary recipe](https://raw.githubusercontent.com/open-telemetry/opentelemetry.io/9f912d59a165ded5dec82d0e1a94c2aef54e5c57/content/en/docs/collector/install/binary/linux.md#L87),
  [v0.162.0 release](https://github.com/open-telemetry/opentelemetry-collector-releases/releases/tag/v0.162.0),
  [native validate/DryRun](https://github.com/open-telemetry/opentelemetry-collector/blob/v0.162.0/otelcol/command_validate.go#L15),
  [file storage creation](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/extension/storage/filestorage/README.md#L39),
  [directory validation](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/extension/storage/filestorage/config.go#L69),
  [file receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/receiver/filelogreceiver/README.md#L164),
  [Prometheus exporter](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/exporter/prometheusexporter/README.md#L20).
- Grafana install: [13.2.3 OSS download/checksum](https://grafana.com/grafana/download/13.2.3?edition=oss&platform=linux),
  [release](https://github.com/grafana/grafana/releases/tag/v13.2.3),
  [native file provisioning](https://github.com/grafana/grafana/blob/v13.2.3/docs/sources/administration/provisioning/index.md#L324),
  [minimum step](https://github.com/grafana/grafana/blob/v13.2.3/docs/sources/datasources/prometheus/query-editor/_index.md#L47),
  [native query API](https://github.com/grafana/grafana/blob/v13.2.3/docs/sources/developer-resources/api-reference/http-api/api-legacy/data_source.md#L657),
  [Alertmanager frontend testDatasource](https://github.com/grafana/grafana/blob/v13.2.3/public/app/plugins/datasource/alertmanager/DataSource.ts#L48).
- Alertmanager install and wiring: [v0.34.1 precompiled binary recipe](https://github.com/prometheus/alertmanager/blob/v0.34.1/README.md#L14),
  [native config validation](https://github.com/prometheus/alertmanager/blob/v0.34.1/docs/configuration.md#L620),
  [webhook url_file](https://github.com/prometheus/alertmanager/blob/v0.34.1/docs/configuration.md#L1939),
  [Telegram file pointers](https://github.com/prometheus/alertmanager/blob/v0.34.1/docs/configuration.md#L1862),
  [native expiring alert](https://github.com/prometheus/alertmanager/blob/v0.34.1/cli/alert_add.go#L46),
  [readiness](https://github.com/prometheus/alertmanager/blob/v0.34.1/docs/management_api.md#L22).
- Alert rules: [Prometheus v3.15.0 native rules](https://github.com/prometheus/prometheus/blob/v3.15.0/docs/configuration/alerting_rules.md#L15),
  [upstream promtool rule-test harness](https://github.com/prometheus/prometheus/blob/v3.15.0/docs/configuration/unit_testing_rules.md#L6),
  [native Alertmanager/file-SD configuration](https://github.com/prometheus/prometheus/blob/v3.15.0/docs/configuration/configuration.md).

Repository reference implementations, verified from original files at
Native Stack at PR #684's head: `observability/backends/configure.py:76`,
`observability/collector/collector.yaml:1`,
`observability/backends/templates/ecosystem-dashboard.json.example:1`,
`observability/backends/templates/ecosystem-prometheus-rules.yml.example:1`,
`observability/backends/README.md:214`,
`examples/omniroute-codex-sdk/worker.py:165,189,395,596`, and
`adoption/new-wsl/client-config-map.json:36`. These are integration references,
not unchanged upstream acceptance tests. Secret pointer placement follows
Native Stack at PR #684's head, `docs/secret-storage.md:39,83`.

## Decision and comparison

**Collector:** synchronize the stack/catalog pin to 0.162.0, the version already
selected by the plan and source profile. Both the native validator and the
service must receive `NS2604_OBSERVABILITY_DATA`, defaulting to
`${XDG_DATA_HOME:-$HOME/.local/share}/new-wsl-native-stack/observability`.
Installation creates the owned queue, event and SDK-receipt directories. A clean
configuration uses the existing repository's privacy and native export pipelines,
adapted to the plan ports, with `file_storage.create_directory: true` and `0700`
permissions. Existing operator pipelines are preserved; only an exact
`directory: /otelcol/queue` is migrated, backed up and passed through the native
validator before replacement. Replacing every retained host configuration with
the former debug-only template would lose the E2E's actual wiring. A native
DryRun or delivery failure with this resolved environment would overturn the
repair and require another bounded source review.

**Grafana:** synchronize the stack/catalog/profile pin to OSS 13.2.3. The archive
SHA256 is unchanged and was found again on the official OSS download page; no
Enterprise asset is substituted. Install native datasource and dashboard
provisioning, preserving the measured token-layer expressions. All six affected
Claude hourly panels use a `1m` minimum step and keep their `[1h]` lookbacks. The
three SDK panels count real receipt IDs/status metadata, with a fresh receipt
from the repository's existing native SDK worker in the after-sign-in stage.
Cumulative native usage snapshots are not exported as incremental usage.
Native `/api/ds/query` assertions require observations from the nine repaired
queries. A coarse hourly step, fabricated receipt, or no-data-to-zero conversion
cannot accept them. If native query API results still lack data after an
exercised workload, acceptance fails and this source change is not promoted to
destination readiness.

Grafana post-install archive/JSON checks are repository integration checks; its
native functional acceptance runs through the upstream HTTP APIs after service
start. The frontend Alertmanager datasource's own test uses `/api/v2/status`;
the generic backend datasource health endpoint returning `Plugin unavailable`
does not by itself prove that the frontend plugin is broken. The default-run
selection is still split/measurement-only in the coordinator's canonical
manifest and `owners.json`, outside this job's editable paths. This patch
therefore retains that selection and provides a complete explicit
`--only grafana` install/acceptance route. The coordinator must reconcile the
selection before describing Grafana as installed by the default run.

The E2E's first-sample counter undercount is a separate Prometheus startup
condition: the maintained backend reference enables
`created-timestamp-zero-ingestion,promql-extended-range-selectors`
(`observability/backends/configure.py:101-108`). This job preserves the recorded
PromQL expressions and labels this limitation rather than adding cumulative
snapshots or overlapping event/counter totals. The Prometheus service owner must
carry the startup condition into destination acceptance.

**Alerting:** retain the current sink until the user chooses a destination and
the corresponding owned `0600` file exists in a `0700` store outside every Git
worktree. The recommended ntfy.sh webhook uses native `url_file`; Telegram uses
native `bot_token_file` and `chat_id_file`. The user chose ntfy.sh on
2026-10-04, accepting the coordinator's recommended gate choices; an on-host
destination would still need its own ruling, as the adjudication says. This builder neither reads those files nor selects a privacy
trade-off for the user. Metadata checks reject unsafe files and preserve the
sink; native amtool validation precedes any receiver configuration replacement.

Prometheus now discovers Alertmanager and loads the two service/fixture rules.
The native `promtool check rules` and `promtool test rules` commands validate
their synthetic firing/resolution cases. Selected delivery acceptance also
uses a confirmed closed loopback file-SD target, observes real native rule
firing/resolution, posts a tagged expiring alert with upstream amtool, and
requires increased notification counters without notification failures. These
local observations still require an independent receiver confirmation of the
tagged firing and resolved notifications before the stage can pass. The sink,
readiness alone or an offline route test cannot establish delivered alerts.

An unchanged upstream validator rejecting the staged configs, native rules not
firing/resolving, a missing tagged receiver receipt, or evidence of unsafe
destination storage overturns acceptance. Loki ruler wiring is explicitly
deferred to its measurement-only owner; this job provisions Prometheus service
alerts and does not silently claim the log ruler passed.

## Verification and boundaries

The bounded regression loop is the existing `check_plan.py`. Before the repair,
the new scoped G4 contracts failed on five named conditions: missing collector
data environment, Grafana version-only acceptance, missing dashboard source,
missing native promtool checks, and missing destination/receipt staging. After
the repair, the same command passes and still checks command/JSON parity, shell
dispatch and real listener collisions. Outgoing datasource/exporter/scrape
references and synthetic rule labels are distinguished from listening sockets.

The source-review profile keeps executable recipes in the canonical install
plan; it does not duplicate the handbook commands. The required handbook
regeneration refreshes its profile and output receipt digests in place.

Shell syntax, the requested four unittest modules, handbook generation,
central validation and whitespace checks are recorded in the builder's final
JSON, including nonzero results. Upstream executables, services, native client
sessions and provider/model calls in the staged recipes were not run by this
builder. No WSL distribution was entered or operated. A version, source fetch,
synthetic rule input or replayed historical receipt is not new-host acceptance.

## Corrections and completeness critic

The final four-module run executes 324 tests and reports 85 failures and 12
errors. The clean copy of PR #684's head reproduces the same 83 client-config
failures, 12 client-config errors and one RTK owner-row mismatch; its total
is 87 failures and 12 errors, including three additional local-model fixture
failures. Those inherited counts are kept separate from the remaining current
profile-generator failure: the coordinator-owned upstream freshness snapshot
requires synchronization after the Collector/Grafana pins move.

The handbook contract rejected duplicated recipe commands in the source-review
profile (`tests/test_new_wsl_handbook.py:1249`). Commands stay in the canonical
plan, generated handbook outputs and their receipt hashes were refreshed, and
the handbook checks now pass. Plan consistency and shell syntax pass; central
validation reports only 15 registry hash mismatches, 14 byte-count mismatches
and nine newly unlisted configuration artifacts. Whitespace checking passes.

The profile's acceptance class is a closed enum: the initial attempted richer
description was rejected by `scripts/new_wsl_profile.py:31,172-174`. It was
corrected to `documented_upstream_example_not_executed`, with the integration
boundary retained in a separate note. The native SDK worker records
`requested_model` (`worker.py:192`); the spool maps that actual field to the
collector's `configured_model`, rather than inventing a missing field. The
Alertmanager unit assignment and frontend health interpretation above follow
the original adjudication and freshly fetched tagged source.

The guessed `api-legacy/dashboard.md` citation returned 404. The tagged contents API locates `http-api/dashboard.md`; the original `pkg/api/dashboard.go:52,74,209-217` verifies the compatibility GET route and provisioned metadata. SOURCES.md now cites that implementation. The fresh latest-release APIs still return v0.162.0 and v13.2.3; the selected Collector tar asset metadata digest equals the plan SHA256. These source/metadata checks are not archive execution.

The critic checked native config-only acceptance, state-directory creation,
operator configuration preservation, both client telemetry endpoints, Grafana
file provisioning and anonymous Viewer, the nine data queries, an actual SDK
producer, native rule tests versus live firing/resolution, webhook and Telegram
file pointers, the explicitly allowed on-host choice, independent receiver
observation, expiring synthetic alerts and restoration of the fixture. Remaining
owner work is destination execution, canonical split/default selection,
Prometheus startup flags and Loki ruler qualification. Shared counts, generated
client carrier source digests and the central evidence registry belong to the
coordinator; this bounded repair does not edit their headers. These omissions
feed the coordinator's next observability and lifecycle acceptance sweep.

> **Coordinator note (2026-10-05).** The host stack pin move named here was withdrawn from PR #704 before landing: `manifests/stack.json` keeps its receipted pin until the currency PR moves it with a qualification receipt. See "Host stack pins withdrawn from this PR" in `docs/decisions/2026-10-04-2604-e2e-fix-wave.md`.
