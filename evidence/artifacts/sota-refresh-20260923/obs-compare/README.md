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
  observability backends specifically, for BOTH a cold backup (original
  round, backends stopped) and a genuine hot/concurrent-write backup (fix
  round, backends left running with an active emitter loop confirmed alive
  at backup time). Not for a broker/order journal, an off-host destination
  or key escrow.
- **c3 sandbox-runtime** (Codex's set) — **not_comparable**, native_proven
  (corrected from an original "regression" verdict — see Fix round below).
  The default-settings inbound-unreachable result for a wrapped collector
  stands as a real observation, but it does not evaluate the role Codex
  actually selected srt for (denying a research worker's egress/broker
  authority, not confining the always-on collector). A fix-round egress test
  found srt does deny a sandboxed worker's outbound network access by
  default and does so controllably via an explicit allowlist — evidence
  that supports, not contradicts, the row's broker-authority-denial
  language, so this is not a regression.

## Fix round (independent Opus review resolution)

An independent review of the original receipt found two major and three
minor issues, all supported by re-inspection. This round re-executed the
affected checks with genuinely new commands (not re-labeling without new
evidence) and corrected the record:

1. **c3 sandbox-runtime scoped to the wrong role.** The original test wrapped
   the always-on collector in `srt` and called the resulting inbound
   unreachability a "regression." Codex selected `srt` to confine research
   workers' broker execution authority, not to wrap the collector, and the
   row's requirement text ("...without granting research workers broker
   execution authority") makes worker-egress confinement part of what this
   row judges. Re-ran the actually-discriminating test from the owned
   worktree (correcting a cwd bug: the original run had `srt`'s deny-path
   enumeration touching the coordinator's main checkout,
   `<coordinator-checkout>`, rather than this worktree): a generic
   sandboxed worker's outbound `curl` to an external host was denied by
   default (`curl: (56) CONNECT tunnel failed, response 403`,
   `No matching config rule, denying: example.com:443`), then allowed once
   that host was explicitly allow-listed in an `-s` settings file, while a
   second, non-allow-listed host stayed denied under the same settings.
   c3's verdict is now `not_comparable` (needed=true, works_under_requirement
   for its actual selected role=true) rather than `regression`.
2. **c8 restic overclaimed "live" backup.** The original backup ran after
   both backends were cleanly stopped (SIGTERM) — a cold backup, not a live
   one, despite claiming to close the "live_databases 0" gap. Re-ran with
   fresh Prometheus/Loki/otelcol instances left running, a background
   emitter loop confirmed alive via process listing, and `restic backup`
   issued mid-loop. `restic check --read-data` found no errors and
   `restore --verify` succeeded; a fresh instance against the restored
   (mid-loop) snapshot returned a smaller, internally consistent subset of
   the data (27/54 vs. the eventual live 41/82 series/streams) — exactly the
   expected behavior of a correct point-in-time snapshot under concurrent
   writes, not evidence of corruption or loss.
3. **Preregistration timing overclaimed as verified.** The original
   `written_at` was presented as if independently verifiable; it is an
   unverifiable self-report (no separate pre-run artifact exists for that
   round). The receipt now discloses this explicitly (`preregistration.post_hoc:
   true`) and a genuinely pre-run preregistration file for this fix round is
   committed at `fixround-preregistration.md`.
4. **Scratch directory wrongly described as "fully cleaned up."** Test
   processes and ports were freed, but the data on disk (configs, logs,
   the restic repository, restored data) was never deleted. The receipt now
   states this correctly and treats that directory as the raw-output
   recovery path; the fix round's egress-test logs are additionally
   committed under `logs-fixround/` in this evidence directory.
5. **"pid 386/386-successor" wording and the srt cwd bug.** Verified via
   `ps -p 370,381,386` before and after this fix round: the live production
   loki/otelcol/prometheus processes (370/381/386) have run continuously
   since `2026-09-22T11:04:18` — there was no successor PID and the
   production stack was never touched or restarted by this comparison. The
   original phrasing was simply inaccurate and is corrected. The cwd issue
   (srt run from the coordinator's checkout instead of this worktree) is
   fixed for the fix-round commands; no write occurred in the original run,
   only path enumeration, per that run's own debug log.

## Limits

See `limits` in the JSON receipt (updated for the fix round): no trace
backend was in either contested set so trace storage/query-back was not
exercised beyond debug-exporter acceptance; the kill-9 test used one
simultaneous kill with nothing in flight; restic coverage (cold and hot)
does not extend to a live broker/order-journal database, an off-host
destination or key escrow, or a longer/heavier concurrent-write window; the
sandbox-runtime egress test used a generic `curl` process, not an actual
research-worker binary, and only two settings-file configurations; the
scratch directory was retained (not deleted) as the recovery path;
Grafana/Alertmanager/ntfy were not re-exercised since they are not in either
contested set.

## Files

- `evidence/artifacts/sota-refresh-20260923/obs-compare/observability-hosting-comparison.json`
  — full receipt with preregistration (original and fix-round), exact
  commands, quoted results and per-candidate verdicts.
- `evidence/artifacts/sota-refresh-20260923/obs-compare/fixround-preregistration.md`
  — genuine pre-run preregistration for the fix round's two re-tests.
- `evidence/artifacts/sota-refresh-20260923/obs-compare/logs-fixround/`
  — raw `srt` egress-test logs (default-deny race and retry, allow-listed,
  non-allow-listed-host-denied).
