# Grand research dashboard

Open [the local dashboard](http://127.0.0.1:13000/d/research-grand?refresh=30s).
On NativeStack2604 (2026-10-06) the same dashboard is
[http://127.0.0.1:21301/d/research-grand?refresh=30s](http://127.0.0.1:21301/d/research-grand?refresh=30s),
provisioned by the install plan's `grafana` row once it has run; see
[NativeStack2604](#nativestack2604) below.
It combines live native service health and exported usage with recorded research
lanes, acceptance gates, worker checkpoints, repository decisions and experiment
outcomes. The header links the existing telemetry dashboard, workflow evidence and
published architecture. Local viewing is passwordless through native Grafana
anonymous **Viewer** access. Administrative changes retain native sign-in.
See the [seamless workflow contract](passwordless.md).

Simulation/backtesting and a bounded Alpaca paper trial now have separate
measured receipts. The [September21 paper roundtrip](../../blueprints/us-equities/paper-e2e-20260921/README.md)
finished flat and reconciled; continuous operation, native broker faults and
Elite throughput remain unqualified. Live trading has no authority. Engineering
fixtures and service health do not establish financial readiness.

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

`progress.py --dagu-dag <name>` (repeatable, up to four) reads other DAGs instead
of `research-pair`, each with its own summary row and up to ten runs; one DAG that
fails reads as unavailable without hiding the others. With more than one DAG the
entity IDs carry the DAG name. `progress.py --loki-url` sets the push endpoint,
which must be `http://127.0.0.1:<port>/loki/api/v1/push` (default port 13100), and
`render.py --dagu-dag` names the same DAGs in the workflow table.

## NativeStack2604

NativeStack2604's install plan renders this dashboard for its own Grafana (21301,
anonymous Viewer) instead of using `install.py`: `observability/ns2604_dashboards.py`
writes it, with `ecosystem-native` and `native-foundation-data`, into the plan's
`config/` with the datasource UIDs `ns2604-prometheus` and `ns2604-loki` and
metric names without the workstation collector's `ecosystem_` namespace. The plan's
`grafana` row provisions them in an Ecosystem folder and installs the emitter as
`ns2604-research-progress.service` and `.timer`, which run `progress.py` every 30
seconds against Loki on 21300 for the DAGs `restic-backup`, `restic-restore-check`
and `tz-currency-check`. The emitter reads Dagu history with
`dagu history <dag> --format json` (Dagu 2.18.2), so the Dagu UI keeps its own
login and nothing in Dagu changes. Apply, read-back and rollback commands are in
the plan's [README](../../evidence/artifacts/new-wsl-install-plan-20261002/README.md).

Manual NativeStack2604 calls to `progress.py` must pass
`--loki-url http://127.0.0.1:21300/loki/api/v1/push`. Its default uses port
13100, which can reach the other WSL distribution through the shared network
namespace. The installed NativeStack2604 service already passes the explicit
21300 address.

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
flooding telemetry. The generation limit is 192 entities, including each
configured DAG's history summary and up to ten runs. It was 128 until 2026-10-06,
when the catalog alone produced 117 rows and NativeStack2604 needed three DAG
histories (four at most: 117 + 4 x 11 = 161). Oversized and duplicate inventories
fail before publication; no records are silently truncated. Changing the selected
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

## Checkpoint and observation rules

- Keep the public grand-dashboard checkpoint current when accepted work changes a lane, worker or gate. Its timer publishes bounded metadata; emitter freshness is distinct from checkpoint age and process liveness.

- Normal local observation uses Grafana anonymous Viewer on loopback; native model clients retain their own sign-ins. Keep Dagu operator authentication distinct from the passwordless observation path; auth:none is not a global Viewer role.
