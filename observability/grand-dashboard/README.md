# Grand research dashboard

Open [the local dashboard](http://127.0.0.1:13000/d/research-grand?refresh=30s).
It combines live native service health and exported usage with recorded research
lanes, acceptance gates, worker checkpoints, repository decisions and experiment
outcomes. The header links the existing telemetry dashboard, workflow evidence and
published architecture. Local viewing is passwordless through native Grafana
anonymous **Viewer** access. Administrative changes retain native sign-in.
See the [seamless workflow contract](passwordless.md).

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
  --units "$USER_UNIT_ROOT" --data "$OBSERVABILITY_DATA" \
  --dagu-bin "$DAGU_BIN" --dagu-home "$RESEARCH_HOME"
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

The two Dagu flags are optional and must be supplied together, using absolute
native paths. They enable a read-only history query for `research-pair`, limited
to ten runs within 30 days. Without them the workflow table says not configured.
No provider login, workflow start or operator-UI authentication is performed by
this adapter. Query failures replace prior successful observations with an
explicit unavailable state.

## What freshness means

[state.json](state.json) is a coordinator checkpoint. Its timestamp describes
when the lane/gate/worker state was recorded. It is not a live process registry.
Its optional `plan_ref` and `stars_ref` select the current public wave and dated
star refresh within this repository. Old receipts keep their original snapshots;
the dashboard does not mistake a previous completed goal for current work.
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

The emitter sends bounded, validated metadata from explicit public files and,
when configured, allowlisted native Dagu history fields. Workflow state counts,
UTC start/finish times and duration are observed; raw run IDs, private paths,
parameters and errors are excluded.
No environment, credentials, account balances, user prompts, raw memory content,
or provider transcripts are read. Evidence paths must stay within the repository.
Only service and record kind are ingestion labels; entity/state fields are
parsed at query time. A generation cap prevents a growing catalog from silently
flooding telemetry. The generation limit is 128 entities, including the native
history summary and up to ten runs. Oversized and duplicate inventories fail
before publication; no records are silently truncated. Changing the selected
catalog scope requires review.

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

The [passwordless follow-up](passwordless.json) adds a fifteenth panel and the
native workflow adapter. Ten native queries and three generation checks passed;
a fresh browser without credentials displayed two succeeded research runs, each
27 seconds. This bounded history is separate from recorded worker checkpoints.

SDK receipt totals, native client histograms, Claude terminal usage and RTK/
Context Mode estimates have different accounting scopes. They are not summed
into a claimed saving. Missing usage, prewarm, retries and outage loss remain
explicit limits. This local dashboard does not establish exact-once financial
audit, off-host recovery, paper execution or production trading readiness.

The [September 21 capacity repair](capacity-recovery-20260921.json) retains an
actual failure: the combined local foundation/paper inventory reached 81 unique
entities and exceeded the former 80-entry cap. After the bounded increase, the
existing native timer published all 81 entries with exit 0. An independent Loki
query returned the complete same generation with no missing, extra or changed
entities; the [exact returned HTTP body](capacity-loki-result.json) is retained.
The 15 project tests include synthetic capacity/history fixtures and preserve
rejection before HTTP/cache mutation. These tests are local integration evidence.
This timer observation is separate from the daily Codex maintenance schedule and
does not establish restart persistence or acceptance of the displayed work.

Primary interfaces: [Loki push/query API](https://grafana.com/docs/loki/latest/reference/loki-http-api/),
[LogQL metric queries](https://grafana.com/docs/loki/latest/query/metric_queries/),
[Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/),
[systemd timers](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html).
