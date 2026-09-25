# Local native observability backends

This profile runs five upstream binaries as Linux user services. It observes the
agent runtime; it does not submit model requests, broker orders, or external
notifications. The Collector and client exporters are configured separately.
All listeners bind to `127.0.0.1`; Alertmanager cluster gossip is disabled.

| Component | Pinned release | Local endpoint | Persistent state |
|---|---|---|---|
| Prometheus | 3.14.0 | `http://127.0.0.1:19090` | TSDB, seven-day / 512 MiB retention |
| Loki | 3.7.8 | `http://127.0.0.1:13100` | TSDB v13, filesystem chunks, WAL, 72-hour retention |
| Grafana OSS | 13.2.2 | `http://127.0.0.1:13000` | SQLite settings, provisioned dashboard and data sources |
| Alertmanager | 0.34.1 | `http://127.0.0.1:19093` | Silences and notification history, 72-hour retention |
| ntfy | 2.28.0 | `http://127.0.0.1:18080` | SQLite notification cache, 72-hour retention |

[pins.json](pins.json) contains exact archive URLs, publisher SHA256 checksums,
source tag commits, and licenses. Grafana's OSS archive checksum is published on
its version-specific download page. Its packaged build commit and source tag
commit differ; both are retained in the receipt rather than equated. Loki's binary
archive lacks a license file, so the installer retains the hash-pinned license
from the corresponding source tag. Other package contents remain intact.

## Install and configure

Requirements: Linux x86-64, Python 3.12 or later, a running systemd user manager,
network access to upstream release hosts, and free loopback ports listed above
plus Loki's internal gRPC port `19095`. These commands reproduce the local
installation. They do not change shell profiles, client accounts, model choices,
Collector configuration, or existing retrieval services.

Run from the repository root. Pick persistent directories on a local Linux
filesystem. The installer refuses to overwrite any existing version prefix;
keep older prefixes for rollback. It caches archives in the evidence directory
and verifies each one before extraction.

```bash
export STACK_TOOLS_ROOT="$HOME/.local/share/codex-ecosystem/tools"
export STACK_CONFIG_ROOT="$HOME/.config/ecosystem-observability"
export STACK_DATA_ROOT="$HOME/.local/share/codex-ecosystem/observability"
export STACK_EVIDENCE_ROOT="$HOME/.local/state/ecosystem-backend-install"
python3 observability/backends/install.py \
  --tools-root "$STACK_TOOLS_ROOT" --evidence-dir "$STACK_EVIDENCE_ROOT"
python3 observability/backends/configure.py \
  --tools-root "$STACK_TOOLS_ROOT" --config-root "$STACK_CONFIG_ROOT" \
  --data-root "$STACK_DATA_ROOT" --unit-root "$HOME/.config/systemd/user"
```

`configure.py` is an installation renderer, not a proxy or runtime. It replaces
`@CONFIG_ROOT@` and `@DATA_ROOT@` in inactive `.example` files with literal absolute
paths and writes the five `ecosystem-*.service` units. YAML and INI files do not
expand these placeholders themselves. Paths with spaces, quotes, percent signs,
or line breaks are deliberately rejected. Re-running this renderer replaces its
owned configuration and unit files; preserve deliberate local edits first.

The renderer generates a random Grafana administrator password and secret key in
`$STACK_CONFIG_ROOT/ecosystem-grafana.env`, mode `0600`, if absent. It preserves an
existing credential file. Read it privately for sign-in; never paste it into a
prompt, terminal transcript, repository, or public receipt. Do not delete or
regenerate it during an ordinary upgrade of an existing Grafana database.

The loopback-only Grafana template now enables native anonymous `Viewer` access
for `Main Org.`. Dashboard observation needs no password; the stored administrator
credential is for administrative operations. Verify the configured organization
name if it was renamed. This recipe binds `127.0.0.1`; it is not a public-host
anonymous-access deployment. The [native passwordless acceptance](../grand-dashboard/passwordless.md)
records fresh-session reads and denied administrative access.

Validate the native configurations before starting services:

```bash
"$STACK_TOOLS_ROOT/ecosystem-prometheus-3.14.0/promtool" check config \
  "$STACK_CONFIG_ROOT/ecosystem-prometheus.yml"
"$STACK_TOOLS_ROOT/ecosystem-loki-3.7.8/loki-linux-amd64" \
  -config.file="$STACK_CONFIG_ROOT/ecosystem-loki.yml" -verify-config=true
"$STACK_TOOLS_ROOT/ecosystem-alertmanager-0.34.1/amtool" check-config \
  "$STACK_CONFIG_ROOT/ecosystem-alertmanager.yml"
systemd-analyze --user verify "$HOME/.config/systemd/user/"ecosystem-{prometheus,loki,grafana,alertmanager,ntfy}.service
systemctl --user daemon-reload
systemctl --user enable --now ecosystem-{prometheus,loki,grafana,alertmanager,ntfy}.service
```

These user units start with the user manager. This does not provision an always-on
host, enable system-level lingering, or establish high availability. Stop only
these units with `systemctl --user stop ecosystem-{prometheus,loki,grafana,alertmanager,ntfy}.service`;
retain their data when upgrading or rolling back. Back up stopped stores before
trying a downgrade that may change their schema.

## Data flow and dashboard

Prometheus scrapes the Collector exporter at `18889`, Collector self-metrics at
`18888`, Qdrant at `16333`, vLLM at `8231`, and the new Prometheus, Loki, and
Alertmanager services. Adjust the explicit target list for another host; missing
services correctly appear down. No remote-write destination is configured.

The Collector's native OTLP HTTP exporter uses `http://127.0.0.1:13100/otlp` as its
Loki base endpoint. Loki accepts structured metadata using TSDB schema v13.
Do not send raw prompts, credentials, tool bodies, or full session archives.
Content sanitization and metadata allowlists belong at the Collector boundary;
the separate Collector profile defines that policy.

Grafana provisions three data sources and dashboard UID `ecosystem-native`:
`http://127.0.0.1:13000/d/ecosystem-native`. Panels show exported token counters,
scrape health, active alerts, Collector rejection/failure counters, and sanitized
logs. Codex uses `ecosystem_codex_turn_token_usage_sum` grouped by `token_type`;
Claude uses `ecosystem_claude_code_token_usage_tokens_total` grouped by `type`.
The two panels preserve their different native schemas. Histogram bucket/count
series are excluded. Collector scrapes use `honor_labels: true` to preserve the
exported service identity. Native token counters are not
provider invoices or estimates of tokens saved. A missing series is not zero
usage, and cached tokens may be a subset of input tokens. An empty panel before
a real client exports data is expected.

Prometheus alerts when a normal scrape remains down for two minutes. Four
Collector HTTP probes expect 2xx from the local OmniRoute, FreeLLMAPI, and
Collector endpoints, and 401 from the protected Dagu API. Missing or unexpected
responses alert after two minutes. These probes establish local transport and
authentication protection only, not provider access or job execution.

A separate `acceptance-fixture` scrape reads `acceptance-targets.json`, initially
`[]`, every five seconds. `EcosystemAcceptanceTargetDown` fires after ten seconds
of an unavailable synthetic target. The coordinator temporarily adds a confirmed
closed loopback port to exercise the route, then restores the empty list and
checks the resolved notification. Never put a production service into this
fixture or deliberately stop one. The renderer preserves an existing fixture
file; leave it empty outside acceptance.

 Alertmanager sends
its native webhook directly to
`http://127.0.0.1:18080/ecosystem-alerts?template=alertmanager`.
ntfy's bundled `alertmanager` template formats firing and resolved payloads. No
custom bridge, SMTP, hosted relay, Firebase, or browser Web Push credentials are
configured. Open `http://127.0.0.1:18080/ecosystem-alerts` locally to subscribe, or
poll stored notifications:

```bash
curl --fail --silent 'http://127.0.0.1:18080/ecosystem-alerts/json?poll=1&since=all'
```

Grafana anonymous access and sign-up are disabled. Optional Grafana and Loki
analytics/update checks are disabled. The other backend endpoints intentionally
rely on loopback and local-user trust, not authentication. Do not expose these
ports through a public reverse proxy without separately designing authentication,
TLS, ingress policy, and notification permissions.

## Native acceptance and limits

The committed [receipt](receipt.json) records archive verification, configuration
checks, five HTTP readiness checks, seven healthy scrape targets, and six checks
across one controlled restart. Grafana checks establish that provisioned views
remain available; they do not independently prove unique SQLite-only user state. The persistence check writes a clearly labeled
synthetic Loki log and local ntfy message, creates a temporary silence matching
only `EcosystemPersistenceFixture`, restarts the five new backends, and reads the
same data back. It expires the temporary silence afterward. It does not stop the
Collector, Qdrant, vLLM, or another application.

To explicitly repeat this acceptance during a maintenance window:

```bash
python3 observability/backends/check_persistence.py \
  --grafana-env "$STACK_CONFIG_ROOT/ecosystem-grafana.env" \
  --evidence-dir "$STACK_EVIDENCE_ROOT"
```

This is a one-shot acceptance script, not a daemon or runtime adapter. Keep its
raw API receipts private: they contain local operational metadata. Failed runs
remain evidence; do not replace them with a successful result under the same
evidence directory when comparing attempts. Client token telemetry, dashboard UI,
and the complete failure-to-notification chain are separate acceptance scopes.

Retention is configured and native-schema validated, not proven by waiting days.
Prometheus's block limit is not a strict total-disk quota: WAL, head chunks and
compaction need extra space. Loki filesystem retention is time-based, not a disk
quota. Its ingestion rate and stream count are bounded, but monitor free disk.
Grafana stores configuration rather than a second copy of metric/log history.
The host's journal retention remains an operating-system setting. This profile
has no replication, off-host backup, outage paging while the host is off, or
production availability guarantee.

## Primary references

- [Prometheus 3.14.0 release](https://github.com/prometheus/prometheus/releases/tag/v3.14.0) and [storage semantics](https://prometheus.io/docs/prometheus/latest/storage/).
- [Loki 3.7.8 release](https://github.com/grafana/loki/releases/tag/v3.7.8), [OpenTelemetry ingestion](https://grafana.com/docs/loki/latest/send-data/otel/), and [retention](https://grafana.com/docs/loki/latest/operations/storage/retention/).
- [Grafana OSS 13.2.2 binaries and checksums](https://grafana.com/grafana/download/13.2.2?edition=oss&platform=linux) and [native provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/).
- [Alertmanager 0.34.1 release](https://github.com/prometheus/alertmanager/releases/tag/v0.34.1) and [webhook configuration](https://prometheus.io/docs/alerting/latest/configuration/#webhook_config).
- [ntfy 2.28.0 release](https://github.com/binwiederhier/ntfy/releases/tag/v2.28.0), [configuration](https://docs.ntfy.sh/config/), and [bundled webhook templates](https://docs.ntfy.sh/publish/#message-templating).

Each persistence attempt requires a fresh evidence directory. Existing `persistence-*.json` files cause refusal before network calls or restarts. A reserved attempt marker also prevents simultaneous runs from overwriting the same evidence.

## Later observation follow-up

The [current-session receipt](../followup-receipt.json) adds real SDK native
histogram delivery, a fresh automatically published result receipt, and WSL
host metrics from the existing Collector. Dashboard receipt aggregation follows
the selected range; empty unreported-usage results remain “No matching data.”
Two native root-filesystem rules bring the rule count to 8. Their configuration
and live inputs were checked without inducing disk exhaustion. The original
six backend restart checks retain their earlier scope.

## Adaptive-paper broker-path alerts

`ecosystem-prometheus.yml.example` adds scrape job `adaptive-paper`. It
scrapes only the targets listed in `adaptive-paper-targets.json`, a `file_sd`
list that Prometheus re-reads on every change and every 30 s. `configure.py`
ships the list as `[]` and never overwrites an existing one.

Each target is a separate, read-only
[`blueprints/us-equities/adaptive-paper/metrics.py`](../../blueprints/us-equities/adaptive-paper/metrics.py#L1)
exporter for that lane's durable ledger. It is not installed or started by
`install.py`/`configure.py`. Run it explicitly alongside a paper trial with
`--file-sd <config-root>/adaptive-paper-targets.json`.

The registration lifecycle:

- Registration. The exporter adds its own `127.0.0.1:<port>` target once its
  listener binds. The write goes through a lock and an atomic replace. The
  exporter refuses to start if the list is not a `file_sd` target list.
- Required. The exporter serves only with `--file-sd`. The explicit
  `--no-file-sd` opts into an unscraped exporter for local inspection.
- Clean removal. The exporter removes its target only on a clean stop
  (SIGTERM or SIGINT) of a trial that finished with a passing status: phase
  `finished` with `passed` or `completed_no_signals`.
- Kept registered. A target stays registered in every other case: its
  exporter crashes or is killed, its trial was left at `starting`,
  `needs_attention` or `held_overnight`, or its trial finished with any
  other, missing or unknown status.
- Recovery. After recovering such a trial, remove the target with
  `metrics.py --deregister --port <port> --file-sd <list>`.

`EquitiesPaperMetricsMissing` uses the expression
`up{job="adaptive-paper"} unless on(job, instance) paper_trial_active`, held
for 2m. It fires when a registered exporter is down or unreachable, or when
another process answers on its port. With nothing registered it stays silent.
It replaced `absent(paper_trial_active)` on 2026-09-25, which fired
permanently on every host with no trial running.

`ecosystem-prometheus-rules.yml.example` adds an `equities-broker-path` group
(bringing the rendered total from 8 to 14 rules): `EquitiesOrderStateDivergence`,
`EquitiesReconciliationFailed`, `EquitiesRequestBudgetExhausted`,
`EquitiesLedgerFrozen`, `EquitiesPaperMetricsMissing`, and
`EquitiesLedgerUnreadable`, each labelled `scope: equities-broker`.
`ecosystem-alertmanager.yml.example` adds an explicit `routes:` entry matching
`scope: equities-broker` to the same `local-ntfy` receiver the default route
already used, so equities-broker alerts are independently identifiable rather
than depending on the unmatched default.

A fix round closed three interaction gaps found in review of the first pass:
the pre-existing `EcosystemServiceUnavailable` rule (`up{job!="acceptance-fixture"} == 0`)
now also excludes `job="adaptive-paper"`, since that exporter is a separate
process not started by `install.py`/`configure.py` and would otherwise leave
that generic alert firing permanently whenever no paper trial is running.
`metrics.py` now always exports `paper_ledger_readable` (1/0, independent of
ledger content) so a wrong `--ledger` path, a permissions problem, or a failed
read-only sqlite open -- which previously left `paper_order_state_divergence_total`,
`paper_ledger_frozen`, and the `paper_request_budget_*` series silently absent
with nothing to alert on -- is guarded by the new `EquitiesLedgerUnreadable`
alert; `EquitiesPaperMetricsMissing`'s description no longer claims to cover
that case, since `paper_trial_active` stays exported even when the ledger is
unreadable. `EquitiesReconciliationFailed` now also fires on
`paper_reconciliation_status{result="needs_attention"} == 1`, because
`runner.py` can end a trial at `phase=finished`/`status=needs_attention` (a
failed run that was then recovered flat), which the original
`paper_needs_attention`-only clause missed. A hard-killed runner whose
`trial.json` stays stuck at `phase=starting` remains an unguarded gap while
its exporter keeps running: the only clause that would catch it needs
`paper_reconciliation_last_success_timestamp_seconds`, which is not currently
exportable (see the schema-gap note below). Since 2026-09-25, stopping that
exporter no longer hides the stuck trial: the unfinished trial keeps its
target registered, so `EquitiesPaperMetricsMissing` fires.

[`broker-path-rules-receipt.json`](broker-path-rules-receipt.json) records the
`promtool check rules`/`promtool check config`/`amtool check-config` runs
against these templates rendered into a temporary directory by this profile's
own `configure.py`, plus the fixture-ledger scenarios `tests/test_adaptive_paper_metrics.py`
exercises. `evidence_class: synthetic` there: only a fixture ledger built from
`safety.Ledger`'s own serialisation was used, never a live broker connection
or credentials. `paper_reconciliation_last_success_timestamp_seconds` and
`paper_request_budget_wait_exceeded_total` are not exported by `metrics.py` --
see its module docstring for the exact schema gap -- so the corresponding
`or` clauses in `EquitiesReconciliationFailed` and
`EquitiesRequestBudgetExhausted` are syntactically valid but currently
dormant; each alert still fires from its other clause
(`paper_needs_attention` / `paper_request_budget_remaining`). That receipt
predates the 2026-09-25 `file_sd` change: it records the static
`127.0.0.1:18890` target and the earlier `absent()` rule. The current rule and
registration are checked by `tests/test_observability_backends_alerts.py`,
which runs `promtool test rules` over the rendered rule, and by
`tests/test_adaptive_paper_metrics.py`, whose `FileSdRegistrationTests` run
real exporter processes.

The WSL workstation's post-merge rollout is recorded in
[`paper-alert-file-sd-host-20260925.json`](paper-alert-file-sd-host-20260925.json).
It was applied surgically, keeping the host's shifted loopback ports, and the
rule read back empty with nothing registered. Silence 87eabf8a was then
expired early.
