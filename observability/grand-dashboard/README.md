# Grand research dashboard

Open [the local dashboard](http://127.0.0.1:13000/d/research-grand?refresh=30s).
It combines live native service health and exported usage with recorded research
lanes, acceptance gates, worker checkpoints, repository decisions and experiment
outcomes. The header links the existing telemetry dashboard, Dagu history and
published architecture. Grafana's existing private sign-in remains in effect.

Simulation/backtesting is the selected lane. Dedicated paper credentials are
pending; live trading has no authority. A successful engineering fixture or a
healthy service does not mark those financial gates complete. Historical results
are clearly labeled; no fabricated live P&L, position count or fill rate appears.

## Native workflow

Use the already accepted [native backends](../backends/README.md). The renderer
targets their datasource UIDs and adds only `research-grand.json`; it preserves
the existing dashboard, datasource provisioning and authentication.

```sh
python3 observability/grand-dashboard/install.py \
  --repo "$STACK_REPO" --config "$OBSERVABILITY_CONFIG" \
  --units "$USER_UNIT_ROOT" --data "$OBSERVABILITY_DATA"
systemctl --user daemon-reload
systemctl --user enable --now ecosystem-research-progress.timer
systemctl --user show ecosystem-research-progress.timer \
  ecosystem-research-progress.service -p Id -p ActiveState -p Result -p ExecMainStatus

python3 observability/grand-dashboard/progress.py --repo "$STACK_REPO" \
  --cache "$OBSERVABILITY_DATA/grand-dashboard/progress-cache.json"
python3 observability/grand-dashboard/acceptance.py --output "$NEW_PRIVATE_ACCEPTANCE"
```

`install.py` renders files and units; the explicit native activation commands
start the timer. The timer checks every 30 seconds and emits only changed data
or a ten-minute heartbeat. The one-shot service is normally inactive after a
successful run. An active user manager/WSL VM and these local backends are
required; this is not an always-on remote hosting promise. Stop this feature with
`systemctl --user disable --now ecosystem-research-progress.timer`.

## What freshness means

[state.json](state.json) is a coordinator checkpoint. Its timestamp describes
when the lane/gate/worker state was recorded. It is not a live process registry.
The emitter also reads the public program plan and three decision matrices;
review their own dates and source pins before reopening a decision. The dashboard
refreshes every 30 seconds. Changing its JSON definition requires Grafana's
provisioning scan and a page reload; ordinary emitted data does not.

Every emitted generation includes a marker and one shared observation timestamp.
Queries select only that newest generation, so removed entities disappear and
re-added entities show the new state. The marker and rows share a bounded native
Loki push; Loki is not claimed to offer a transactional multi-stream commit.
If input validation or ingestion fails, the cache does not advance. Emission
age grows; after the 24-hour query window the table reports no matching data.
No matching data is not success or a count of zero.

The emitter sends only bounded, validated metadata from explicit public files.
No environment, credentials, account balances, user prompts, raw memory content,
or provider transcripts are read. Evidence paths must stay within the repository.
Only service and record kind are ingestion labels; entity/state fields are
parsed at query time. A generation cap prevents a growing catalog from silently
flooding telemetry. Changing the selected catalog scope requires review.

## Native acceptance and limits

Native Loki table/stat queries succeeded. A separate synthetic service stream
verified initial presence, deletion and re-addition with changed state. Native
Prometheus returned six memory-state series. The timer was enabled/active; its
one-shot result was success with exit 0. Browser inspection confirmed the tables,
source timestamps, evidence links and 30-second refresh selection.

Two integration failures were retained and corrected: Loki rejected PromQL's
`time()` function, so Grafana now renders the observed timestamp as relative age;
15 seconds was not in Grafana's configured interval choices, so this dashboard
uses the supported 30-second interval. The generation filter and reference-path
containment fixes were independently reviewed. Final counts and hashes are in
the [receipt](receipt.json).

SDK receipt totals, native client histograms, Claude terminal usage and RTK/
Context Mode estimates have different accounting scopes. They are not summed
into a claimed saving. Missing usage, prewarm, retries and outage loss remain
explicit limits. This local dashboard does not establish exact-once financial
audit, off-host recovery, paper execution or production trading readiness.

Primary interfaces: [Loki push/query API](https://grafana.com/docs/loki/latest/reference/loki-http-api/),
[LogQL metric queries](https://grafana.com/docs/loki/latest/query/metric_queries/),
[Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/),
[systemd timers](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html).
