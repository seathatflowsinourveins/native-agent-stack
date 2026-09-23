# obs-compare: executed comparison for us-equities observability-hosting

Unit `obs-compare` of the 2026-09-23 SOTA refresh evidence wave. Executed the
discriminating test the coordinator specified for the contested
`observability-hosting` row (`catalogs/landscape/us-equities.json`,
`verdict_status: pending_lanes`, `open_gaps` recording a 2-2 order-swapped
adjudication split between Claude's set
{opentelemetry-collector-contrib, loki, prometheus} and Codex's set
{opentelemetry-collector-contrib, restic, sandbox-runtime}).

This unit does not change the row. It reports what the executed evidence
shows for each contested candidate; the coordinator re-judges.

## Version check

`gh api repos/<owner>/<repo>/releases/latest` was run for all four
version-pinned tools. All four pins already equal the newest published
release (otelcol-contrib v0.161.0, loki v3.7.8, prometheus v3.14.0,
restic v0.19.1). This is therefore an executed same-version comparison of
the contested set, not a version-upgrade qualification.

## What was run

All five parts of the coordinator's discriminating test were executed
natively, on this host, in a scratch area under
`<host-cache-path>/sota-refresh-20260923/obs-compare/` with unique loopback
ports, entirely separate from the live production observability stack
(confirmed by binding-conflict detection before choosing ports, and by
leaving that stack's ports/processes untouched throughout):

1. **Ingest**: a Python emitter (`emit_otlp.py`, kept alongside this
   receipt's evidence, not committed to the repo) sent OTLP JSON
   metrics/logs/traces shaped like trading-runtime events (order-fill
   latency, order-filled/risk-check logs with `receipt_id`, a `place_order`
   span) to a pinned `otelcol-contrib` instance over loopback HTTP.
2. **Storage and query-back**: the collector forwarded metrics to a pinned
   Prometheus via `prometheusremotewrite` and logs to a pinned Loki via its
   native OTLP endpoint (`otlphttp` exporter, not a dedicated `loki`
   exporter — this 0.161.0 contrib build has no exporter literally named
   `loki`). Both were queried back successfully with original attributes
   intact.
3. **Retention across kill -9 + restart**: `kill -9` on the collector and
   both backends simultaneously, then relaunching against the same data
   directories. Pre-kill data was present unchanged after restart; both
   backends accepted and served new data after restart.
4. **Off-host-style recovery**: `restic backup`/`check --read-data`/`restore
   --verify` on the live Prometheus and Loki data directories (not just
   static files), a byte-identical `diff -rq` between original and restored
   directories, and query parity from fresh backend instances reading the
   restored data.
5. **Sandbox confinement**: launched the collector under `srt` (sandbox-
   runtime) with default settings and tried to reach its OTLP receiver from
   the host.

## Key finding

Steps 1-4 passed for opentelemetry-collector-contrib, Prometheus, Loki and
Restic — each is directly, natively demonstrated to work for this
requirement, including exactly the live-database/off-host recovery gap both
sealed lanes had flagged as unproven for Restic (it is now proven for the
observability backends' own data, though not for a broker/order journal).

Step 5 failed: sandbox-runtime's default `bwrap --unshare-net` isolates the
sandboxed collector into a private network namespace, so its OTLP receiver
becomes unreachable from outside the sandbox. The collector starts and logs
"ready," but no external emitter — including the trading runtime this layer
exists to observe — can reach it. This is native, directly executed
evidence that sandbox-runtime's default configuration is not currently a
working way to confine this specific always-on, network-facing collector
process, independent of its already-demonstrated filesystem/env
restriction value (`evidence/receipts/runtime-tools.json`).

## Per-candidate read (full detail and quoted output in the JSON receipt)

- **c14 opentelemetry-collector-contrib** — qualified, native_proven. Common
  to both contested sets; end-to-end ingest confirmed.
- **c5 Prometheus** (Claude's set) — qualified, native_proven. Storage,
  query-back, kill-9 retention and restic-restore query parity all pass.
- **c6 Loki** (Claude's set) — qualified, native_proven, after fixing
  `allow_structured_metadata` (off by default; OTLP logs are rejected with
  HTTP 400 otherwise — neither sealed lane's receipt names this).
- **c8 Restic** (Codex's set) — qualified, native_proven for the
  observability backends specifically; closes the "live_databases 0" gap
  both lanes flagged, for Prometheus/Loki data (not for a broker journal).
- **c3 sandbox-runtime** (Codex's set) — regression, native_proven: default
  network isolation breaks inbound OTLP ingest for the collector it was
  meant to confine.

## Limits

See `limits` in the JSON receipt: no trace backend was in either contested
set so trace storage/query-back was not exercised beyond debug-exporter
acceptance; the kill-9 test used one simultaneous kill with nothing in
flight; restic coverage does not extend to a live broker/order-journal
database, off-host destination or key escrow; only sandbox-runtime's
default settings were tried (a settings-file configuration that shares
network namespace was not searched for or ruled out); Grafana/Alertmanager/
ntfy were not re-exercised since they are not in either contested set.

## Files

- `evidence/artifacts/sota-refresh-20260923/obs-compare/observability-hosting-comparison.json`
  — full receipt with preregistration, exact commands, quoted results and
  per-candidate verdicts.
