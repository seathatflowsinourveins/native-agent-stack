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
across one controlled restart. The persistence check writes a clearly labeled
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
