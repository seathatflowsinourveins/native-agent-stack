# User-unit alert lifecycle (F09)

F09's one-shot Alertmanager posts can expire while the originating unit is still
failed. This integration gives the existing Collector and Prometheus one state
policy for the configured user units. It preserves the existing two alert names,
but the message says a unit needs attention because failure **or unknown state**
is possible. A missing exporter, bus observation or unit is never called recovery.

This is source and configuration work. Deployment and the **one** real Telegram
DRILL belong to the CC-authorized window in [WINDOW.md](WINDOW.md). No host,
client, sender template or installer is changed by this directory.

## Native owners and source contracts

Reuse Collector Contrib **0.162.0**, already selected by the stack:
[systemd receiver user scope](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/receiver/systemdreceiver/README.md),
[session-bus implementation](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/receiver/systemdreceiver/scraper.go#L44).
The receiver is alpha; source support is not a newly passed WSL/user-bus test.

Its [state metric](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/receiver/systemdreceiver/metadata.yaml#L89)
uses resource `systemd.unit.name` and point `systemd.unit.active_state`.
The dedicated pipeline copies them into `unit` and `state`, adds the configured
`host`, drops other fields and exports only `ns2604_user_unit_state` as a gauge.
[Ordered transforms](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/processor/transformprocessor/internal/metrics/processor.go#L39)
copy the resource identity before clearing resource attributes. It never feeds
these points through the base privacy allowlist that would remove unit identity.

The Collector exporter normally caches old points for five minutes and omits
timestamps. Here a separate exporter uses `send_timestamps: true`,
`metric_expiration: 1m` and `UnderscoreEscapingWithoutSuffixes`; the Prometheus
scrape honors timestamps. Existing exporters and pipelines are unaffected.
[Pinned exporter contract](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/exporter/prometheusexporter/README.md#L29),
[timestamp implementation/test](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/exporter/prometheusexporter/collector_test.go#L755).

The configured roster produces recurring `vector(1)` recording rules named
`ns2604_user_unit_expected`. These are **configuration expectations**, not unit
observations. They remain present when the exporter vanishes.
[Native recording rules](https://github.com/prometheus/prometheus/blob/v3.15.0/docs/configuration/recording_rules.md).

## Recovery and unknown state

A source point is fresh only if its observed timestamp is between now and
45 seconds ago (three 15-second collection periods) and its scrape target is up.
A fresh value1 for active is recovery evidence. Inactive alone does not prove a
successful completion: this receiver does not export the service Result field.
Fresh failed evidence
takes precedence over a contradictory cached healthy state. Otherwise the
configured identity stays in the alert vector, including after ten minutes or
longer of exporter/bus failure while Prometheus continues evaluating.

Alert labels are only host, unit, severity and the rule's alertname. State,
reason, timestamps and scrape labels do not change that fingerprint. The
30-second `for` is initial debounce and `keep_firing_for` is recovery debounce;
neither is the outage guard. Filtering comparisons are intentional: a zero-valued
`bool` comparison still leaves an element that an alert could interpret as active.
[Alert rules](https://github.com/prometheus/prometheus/blob/v3.15.0/docs/configuration/alerting_rules.md#L35),
[comparison/set operators](https://github.com/prometheus/prometheus/blob/v3.15.0/docs/querying/operators.md#L159).

Active here qualifies the manager's retained state, not application readiness.
Unique one-off units need their owner's supported RemainAfterExit=yes policy so
successful completion remains active; recurring event-style jobs use their own
success/event contract. Until explicit success is represented, inactive and an
unloaded or forgotten unit remain recovery-unverified. Default CollectMode retains failed units;
other collect modes can forget them. [systemd v260](https://github.com/systemd/systemd/blob/v260/man/systemd.unit.xml#L1073).

The roster must cover **every concrete managed unit** whose old sender is retired,
including future job instances. CC/5f owns that installation registration and
same-identity classification. Never deploy the DRILL-only example as the production
roster, remove an unresolved unit from it, or change its severity/class to silence
an incident. An unregistered unit is explicitly outside coverage.

## Render supported native configuration

Use a complete CC/5f-owned policy with concrete service names and the old senders'
matching host/class/severity. The proposed 21890 loopback port needs CC allocation.

```bash
rtk proxy nice -n 19 ionice -c3 python3 observability/alert-lifecycle/render.py \
  --policy <complete-owned-policy.json> \
  --rules-template "$PWD/observability/alert-lifecycle/user-unit-alerts.rules.json" \
  --output-dir <durable-private-staging-directory>
```

Outputs are JSON, which the native YAML loaders accept: receiver.json, rules.json,
and scrape.json. The same roster drives the receiver and independent expectations.
The small renderer fills that multi-format configuration gap; it is not an
exporter, agent, observer, runtime watcher or custom test harness. It rejects
duplicate units, templates/globs, unsupported fields/classes and non-loopback binds.

Append the unique Collector components through its supported second `--config`
file, not by editing #775's base YAML. Add the generated scrape job and rule file
through the CC-owned Prometheus provisioning/configuration path. Stage and validate
the merged configuration before its reviewed reload.
[Collector merge](https://github.com/open-telemetry/opentelemetry-collector/blob/v0.162.0/confmap/confmap.go),
[Prometheus configuration/reload](https://github.com/prometheus/prometheus/blob/v3.15.0/docs/configuration/configuration.md).

## Sender retirement and protocol boundaries

Prometheus refreshes active alerts and supplies EndsAt; at3.15 it uses evaluation
time plus four times the maximum evaluation/resend interval for active validity.
It sends ResolvedAt only after the alert becomes inactive. Alertmanager's
`resolve_timeout` applies only when EndsAt is omitted.
[Prometheus sender](https://github.com/prometheus/prometheus/blob/v3.15.0/rules/manager.go#L497),
[validity](https://github.com/prometheus/prometheus/blob/v3.15.0/rules/alerting.go#L618),
[Alertmanager0.34.1 contract](https://github.com/prometheus/alertmanager/blob/73c6bfe7393929211294c1954f30d8ed78e4d0ad/docs/alerts_api.md#L44).

The CC's later hidden-dependency ruling preserves the accepted paper one-shot
first notice (C1b). Its host/unit/severity/alertname fingerprint must match the
registered state rule, which then owns renewal and recovery. Stack's ntfy hop is
removed by its owner; no additional per-unit drop-ins are added for covered scope.
Only genuinely event-style failures such as DaguDagFailed use a no-resolved route.
Do not lengthen leases or hide unit-rule resolutions. The owner handoff is
[5F-HANDOFF.md](5F-HANDOFF.md); this PR does not edit those pinned files.

An entire Prometheus/sender/link outage can still expire its finite protocol
lease. This rule guards exporter/bus/state staleness while the evaluator and
sender work; it cannot prove recovery during complete sender loss. Sender health
needs independent observation, and an expired Alertmanager lease alone is never
a service-health receipt. No sender-loss guarantee is claimed.

## Evidence and acceptance

The fourteen current rule groups are **locally authored synthetic cases** executed by the
unchanged upstream promtool harness. Renderer tests are local integration checks;
native Collector validation is configuration-only. None is the real notification
DRILL or an unchanged upstream test suite. The single real DRILL remains not run
until the CC applies the window and signals acceptance.

```bash
rtk proxy nice -n 19 ionice -c3 <promtool-3.15.0> test rules observability/alert-lifecycle/user-unit-alerts.test.json
rtk proxy nice -n 19 ionice -c3 python3 -m unittest tests.test_user_unit_alert_renderer
rtk proxy nice -n 19 ionice -c3 python3 observability/alert-lifecycle/render.py --check
```

Preserve past false-RESOLVED observations and the proven Telegram delivery receipt.
Correct their interpretation with a new linked record; do not rewrite their values.

## Event and independent heartbeat examples

`alertmanager-events.example.json` is a CC-rendered route/receiver example: only
the genuinely event-style DaguDagFailed route suppresses resolved notifications.
Unit-state classes keep resolution delivery and the accepted paper first notice.
Private bot/chat file paths must be supplied through existing custody; this
repository contains neither their values nor a live receiver configuration.

`alerting-pipeline.rules.example.json` adapts the pinned upstream notification-
failure ratio with its native15-minute window/5-minute hold. It does not prove
delivery during zero traffic or complete sender death.
[Alertmanager mixin at73c6bfe7](https://github.com/prometheus/alertmanager/blob/73c6bfe7/doc/alertmanager-mixin/alerts.libsonnet#L42).
`pipeline-scrape.example.json` declares the native Alertmanager21093, Grafana21301
and Loki21300 targets; configured source does not assert current endpoint health.

Watchdog's vector1 rule and deadman route fragments are **disabled examples**.
Enable them together only after CC chooses and provisions the independent
heartbeat receiver using url_file. A configured Telegram-failure warning inhibits
Watchdog so that the external receiver detects failed delivery. No local component
can report Alertmanager's own death; a disabled example provides no live coverage.
[Pinned Watchdog](https://github.com/prometheus-operator/kube-prometheus/blob/799f3d73/jsonnet/kube-prometheus/components/mixin/alerts/general.libsonnet#L19),
[native url_file](https://github.com/prometheus/alertmanager/blob/73c6bfe7/docs/configuration.md#L1943).
No external account, secret URL, service or paid hosting is created by this PR.
