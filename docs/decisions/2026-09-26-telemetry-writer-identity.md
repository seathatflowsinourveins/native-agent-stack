# Decision: one writer per Prometheus token series: Claude session ids, a Codex identity launcher, aggregation of dropped attributes and Prometheus start timestamps (2026-09-26)

**Status: decided in the repository; host application pending.** The workstation
`nativestack-5975wx-20260925` still runs the previous profile. Applying it rewrites the
host Collector config, one Claude settings key, the Prometheus unit, config and rules, the
provisioned dashboards and the `bin/codex` link, then restarts the Collector and
Prometheus. The settings change reaches only sessions started afterwards. The
[host recipe](../../evidence/artifacts/telemetry-writer-identity-20260926/host/) (`apply.sh`,
`rollback.sh`, `prove.sh`) does this on an existing host; see the
[Collector README](../../observability/collector/README.md#writer-identity-and-counter-integrity).

**Scope:** `observability/collector/collector.yaml`,
`observability/collector/claude-settings.json.example`,
`adoption/templates/claude.settings.template.json`,
`observability/collector/codex-identity-launcher.sh.example`,
`observability/backends/configure.py` (Prometheus features),
`observability/backends/templates/ecosystem-prometheus-rules.yml.example`
(`native-telemetry-integrity`), `observability/backends/templates/ecosystem-prometheus.yml.example`
(Codex bucket drop), `observability/backends/templates/ecosystem-dashboard.json.example`,
`observability/native-data/render.py`, `observability/grand-dashboard/render.py`, the host recipe,
the READMEs that describe them, and their tests. Workflow run attribution (`workflow.run_id` and `agent.name` on the
Loki allowlist) is a separate gap and is not changed here.

## Context

- Prometheus identifies a series by `job` (`service.name`), `instance` (`service.instance.id`) and
  the allowlisted data point labels. The Collector set `instance="unscoped"` for every writer that
  sent no `service.instance.id`, which was every Claude session and every directly started Codex
  process.
- Claude Code: `OTEL_METRICS_INCLUDE_SESSION_ID` defaults to `true`; `/clear` assigns a new
  `session.id` in the same process; a resumed session keeps its `session.id`; the token and cost
  counters also carry `agent.name`, `skill.name`, `plugin.name`, `mcp_server.name` and more; the
  resource carries `service.name`, `service.version`, `os.*`, `host.arch` and no process identity; set
  temporality to cumulative "if your backend expects cumulative"
  ([monitoring](https://code.claude.com/docs/en/monitoring-usage), fetched 2026-09-26T15:01Z,
  sha256 `24bacd25…`). This repository had set session ids off.
- Codex at `rust-v0.157.1` (commit `36650394c5b3`): `codex-rs/otel/src/metrics/client.rs` builds
  the metrics resource with `Resource::builder().with_service_name(..)` plus `service.version`,
  `env`, `os`, `os_version`, and a delta exporter; `metrics/tags.rs` adds only `auth_mode`,
  `session_source`, `originator`, `service_name`, `model`, `app.version`; `provider.rs` builds the
  logs resource the same way. `opentelemetry_sdk` 0.31.0 `Resource::builder()` includes
  `EnvResourceDetector`, so `OTEL_RESOURCE_ATTRIBUTES` reaches both. Codex exports no
  per-process attribute. `core/src/state/turn_token_usage.rs` records a turn's tokens when the
  turn ends.
- otelcol-contrib 0.161.0: `delta_to_cumulative` rejects a point not newer than its stream
  (`ErrOutOfOrder`) or starting before it (`ErrOlderStart`, "consider checking for multiple
  processes sending the exact same series"); `groupbyattrs` moves the named data point attributes
  onto a new resource and removes them from the points; the transform processor's
  `aggregate_on_attributes` keeps the listed attributes and adds together the points that then
  match (delta points only with equal start and end times); the Prometheus exporter sends start
  timestamps as created timestamps for counters, histograms and summaries and drops a series after
  `metric_expiration` (5m).
- Prometheus 3.15.0 feature flags: `created-timestamp-zero-ingestion` injects a zero sample at a
  counter's start timestamp and makes protobuf the preferred scrape format;
  `promql-extended-range-selectors` adds `anchored`, the difference between samples at the range
  boundaries without extrapolation. `st-storage` and `use-start-timestamps` are the planned
  successors; `st-storage` writes a WAL record only 3.11 and later can replay.
- Measured before the change, read-only
  ([host-before-20260926.json](../../evidence/artifacts/telemetry-writer-identity-20260926/host-before-20260926.json)),
  14:51-15:51Z: Claude counter resets 7,216; Prometheus `increase()` 73 to 193 times the Loki
  `api_request` sums per type; `delta_to_cumulative` rejected about 3,518 of 8,160 points
  (`increase()` estimates); 104 Claude and 6 Codex token series were `unscoped`. A later read-only
  count kept in the same receipt: 1,388 of the 1,512 `codex_exec` series were histogram buckets, and
  each codex_exec conversation start had one startup prewarm response (`output_token_count=0`;
  10 of 10 in that hour, 58 of 58 over six hours).

## Decision

1. Claude sends session ids again (the upstream default) in both client templates. The Collector's
   metrics pipeline runs `groupbyattrs/session` (keys `session.id`), then `transform/privacy` sets
   `service.instance.id` to the session id, or appends `/<session.id>` to a launcher-set writer id,
   before the resource allowlist. Temporality stays cumulative.
2. Codex gets `service.instance.id` from `OTEL_RESOURCE_ATTRIBUTES`, set per process by the
   [identity launcher](../../observability/collector/codex-identity-launcher.sh.example) that
   replaces the codex link on `PATH` (local integration). An inherited id becomes the prefix,
   `<inherited>/<fresh>`: every process is its own writer, as the repository's workers give each
   subprocess a fresh id (`blueprints/us-equities/workers/native_worker.py`), and the prefix keeps
   the caller's id for correlation, as the Collector's `<writer>/<session.id>` does.
3. `transform/privacy` aggregates sum and histogram streams on the existing data point allowlist
   (`aggregate_on_attributes("sum", …)`) before the unchanged `keep_keys`.
4. `configure.py` starts Prometheus with `created-timestamp-zero-ingestion` and
   `promql-extended-range-selectors`.
5. Dashboards use `rate()`/`increase()` over writers and exclude `instance="unscoped"`; the
   `native-telemetry-integrity` rules alert on repeated resets of one series (`max by (job)`, so a
   resumed session, which resets each of its series once, stays silent), dropped delta points and
   unscoped writers; the activity log panels include `codex_exec`, `codex_cli_rs` and
   `claude-code-desktop`.
6. The deprecated `deltatocumulative` alias becomes `delta_to_cumulative`.
7. The `collector-native` scrape drops the Codex histogram bucket series except
   `ecosystem_codex_turn_token_usage_bucket` (`metric_relabel_configs`, Prometheus's documented
   way to exclude series too expensive to ingest). Per-process identity multiplies them, no panel or
   rule reads them, and the 512MB size limit applies to every job in this Prometheus.

## Alternatives considered

| Alternative | Why not now |
|---|---|
| Claude delta temporality (the upstream default) and `delta_to_cumulative` | Several writers of one delta stream are the Codex failure above; a Collector restart also loses accumulated state. |
| `session.id` as a separate Prometheus label | Same cardinality; Codex needs `instance` anyway, and `instance` is Prometheus's writer identity. |
| Widen the allowlist (`agent.name`, `phase`, `feature`, …) | More series, and every future client attribute would reopen the collision; aggregation is right for any dropped attribute. It can still add `agent.name` later for attribution. |
| Counters derived from Loki events (`signaltometrics` connector, single writer) | Exact per request, but duplicates the Loki lane and drops the native counters. Kept as the fallback. |
| Prometheus OTLP receiver with native delta ingestion | New metric names, dashboards and rules; larger change than needed. |
| Per-connection identity in the Collector (`client.address`) | Carries the client IP, not the process. |
| `st-storage` with `use-start-timestamps` | Experimental and changes the WAL format; revisit when stable. |
| Drop the unused Codex histograms whole in the Collector (`filter` processor) | Also drops their `_sum` and `_count`; the scrape relabeling removes only the bucket series. |
| Keep every bucket and raise the size limit | Up to about 1,300 bucket series per process (the before-change union of all processes under one identity); the limit is this host's disk budget for every job. |

## Evidence and its class

- Upstream documentation and source at the pinned versions (above): reviewed, not executed.
- Synthetic local integration on the pinned binaries
  ([synthetic-ab-20260926.json](../../evidence/artifacts/telemetry-writer-identity-20260926/synthetic-ab-20260926.json),
  harness beside it): identical input from three Claude-like and three Codex-like concurrent
  writers. Old profile: 4 resets, Claude totals 51.3 percent low, 24 of 70 delta points dropped,
  Codex totals 6.7 percent low. New profile: 0 resets, 0 dropped, `increase(… anchored)` exact for
  both; plain `increase()` 3.0 percent high from edge extrapolation.
- `tests/test_observability_writer_identity.py` runs the committed pipeline on the pinned
  otelcol-contrib (and the rules on promtool) when installed; it fails on the previous profile.
  With the pinned Prometheus installed it also scrapes that Collector through the rendered
  `collector-native` job: the Codex buckets other than token usage are dropped, `_sum` and
  `_count` stay, and `increase(...[5m] anchored)` counts a new series' first value.
- `tests/test_observability_writer_identity_host.py` runs the host recipe on synthetic data: the
  checker against a fake of the Prometheus and Loki query APIs, apply and rollback in a sandbox
  home with fake service managers. All 20 PromQL queries of the checker parse on the pinned
  Prometheus 3.15.0 with both features on, and the loopback Loki accepts its 16 LogQL queries.
  Read-only probes of the host backends fixed three inputs of the checker and apply script
  (`backend_api_observation` in the before-change receipt). On Prometheus 3.15.0,
  `/api/v1/targets` gives the collector-health `scrapeInterval` (15s), and
  `/api/v1/status/runtimeinfo` gives `startTime` in nanoseconds and `lastConfigTime` in whole
  seconds. On Loki 3.7.8, `query_range` refuses more than 11,000 points per series, so the
  1-second activity spans hold up to a 10,000 s window. The host's collector-health scrape had
  240 samples in the probed hour, 15.016 s apart at most.
- Host acceptance after application: not yet run. `host/prove.sh` needs, over one window, at most
  one reset of any Claude token or cost series (a resume), the collector-health scrape up for the
  whole window with no missed scrape (every `up` sample 1, no gap over 1.5 scrape intervals,
  edges included), zero `delta_to_cumulative` errors with accepted points, no unscoped token
  writers; per Claude writer (session) without requests within 30 s of either window edge,
  `increase(… anchored)` within 2 percent of the Loki `api_request` sums per type; and for every
  `codex_exec` process that started in the window, completed a turn and finished 90 s before its
  end, the turn tokens within 2 percent of the Loki `response.completed` sums with the same
  `service_instance_id` (startup prewarm responses excluded; a process missing from Prometheus
  counts as -100 percent; one with no completed turn on either side is listed, not compared). The
  window must hold two compared Claude writers, Ultracode child usage and two compared `codex exec`
  processes whose activity spans (first to last Loki event, 1 s resolution) overlap.

## Overturn when

- The host proof above fails with only scoped writers in the window.
- Claude Code adds a process identity, or changes `session.id` semantics: use that instead.
- Codex adds a per-process resource or data point attribute: drop the launcher.
- Prometheus stabilizes start-timestamp storage or removes `created-timestamp-zero-ingestion`.
- The size limit, not the 7-day time limit, starts deleting blocks:
  `increase(prometheus_tsdb_size_retentions_total[7d]) > 0`, or, on a TSDB older than a week,
  `time() - prometheus_tsdb_lowest_timestamp_seconds < 7 * 86400`. Storage never exceeds the
  limit, so that is the observable sign that per-writer series crowd out other jobs' history;
  `prove.sh` reports both.

## Limits

- Sessions started before the settings change stay `unscoped` until they exit.
- A codex started from the real binary instead of `bin/codex` gets no id of its own: it is
  `unscoped`, or shares the id it inherited with its parent.
- The checker treats a `codex_exec` process without events for 90 s as finished. One that is alive
  but silent that long in the middle of a turn is compared early; that shows as a FAIL to
  investigate, not a PASS.
- A Codex version switch that re-links `bin/codex` removes the launcher until it is reinstalled;
  `EcosystemUnscopedTokenWriters` then fires. It keeps 15 minutes of unscoped samples and fires
  after 5 minutes, so a short run fires it too: the Collector's exporter drops a series five
  minutes after its last export (`metric_expiration`, default `5m`), too soon for an instant
  selector with a longer delay.
- Plain `increase()` extrapolates at window edges (a few percent for short-lived writers);
  `anchored` gives the exact difference.
