# User-unit failed-state lifecycle (F09), design C

CC022242Z supersedes A/A-prime. Unit EVENT PaperLaneUnitFailed/StackUnitFailed
uses a name-only receiver without integrations: immediate Alertmanager record,
no human notice. STATE PaperLaneUnitDown/StackUnitDown notifies with resolved
delivery enabled. No inhibitor. Dagu keeps its distinct event-only route.
C and fallbackA pass native amtool; A is enabled only if the GPT read refutes C.
[Alertmanager0.34.1 receivers/routes](https://github.com/prometheus/alertmanager/blob/73c6bfe7393929211294c1954f30d8ed78e4d0ad/docs/configuration.md).

Reuse installed Contrib0.162 user-scope systemd receiver. Preserve its
systemd.unit.state name/native unit, using no-suffix Prometheus rendering as
systemd_unit_state. The dedicated timestamp-preserving exporter and registered
configuration expectations prevent stale/exporter/bus/missing data from being
recovery. Expectations are not observed states. No new collector, binary,
runtime watcher, client configuration or exporter is installed by this source.
[Native receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/receiver/systemdreceiver/README.md),
[metric/enum](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/receiver/systemdreceiver/metadata.yaml),
[exporter](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/exporter/prometheusexporter/README.md).

The roster names each recovery contract. `active` requires fresh active evidence
strictly newer than every contradictory fresh non-active observation; ties are
conservative and fresh failed evidence always wins. `failure-cleared` accepts
a fresh recognized nonfailed state, including inactive, but does not prove
application readiness, success, job completion or cadence. The named W2 drill
uses this latter contract for the CC's reset-failed recovery. Empty/unknown/
foreign/future/old observations do not qualify either contract. Recording rules
carry the original observation timestamp as a value; a recording rule's own
evaluation timestamp is not the source observation time. Data loss stays
needs-attention while the evaluator works. Whole sender/evaluator outage still
has finite protocol leases; disabled deadman is not independent protection.

The native receiver emits one for the current state and zero for each other
enumerated state on every successful scrape. The contradictory cached-series
fixtures therefore defend against transport/cache overlap; they are not a claim
that a normal successful receiver scrape omits those zeros.
[Contrib0.162 state emission](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/receiver/systemdreceiver/scraper.go#L150).
[systemd259.5 reset](https://github.com/systemd/systemd/blob/v259.5/man/systemctl.xml),
[native rules/staleness](https://github.com/prometheus/prometheus/blob/v3.15.0/docs/configuration/alerting_rules.md).

render.py only compiles the complete CC-owned concrete roster into native
receiver/rule/scrape JSON; it neither observes units nor invents timer metrics.
Use its absolute rules-template and supported second Collector --config through
the CC's existing provisioning path. Port21890 is allocated, with custody
rechecked. The example is not production coverage; unregistered units remain
outside scope. Do not remove failed identities just to silence them.

The first unit human notice follows collection/for, roughly a minute. A shorter
unobserved failure may leave only its EVENT record. Native source tests and
config validation are integration evidence, not real delivery or organic use.
Earlier active-only/A-prime observations remain unchanged in separate records.

WINDOW.md specifies the one pending CC-only W2 origin paper-drill-w2.service,
oneshot/binfalse/OnFailure=paper-alert@%n.service, with reset-failed recovery.
EVENT/STATE unit and host are read back side by side. Record actual fifteen-minute
STATE firing/recovery sequence and no EVENT notice, then reviewed removal.
Install nothing from a lane. Private bot/chat files stay under existing custody;
never fetch the credential-bearing status/config endpoint.

G2 completion/cadence remains unknown: Contrib's selected receiver supplies no
LastTriggerUSec metric. No custom or aged exporter is added. Watchdog/deadman
stay disabled pending the owner's independent account and CC decision. Historical
delivery/false-RESOLVED values stay unchanged; correct them with new evidence.

The policy enumerates continuous services, reused one-shots, timer-triggered
services and the named W2 drill. Reused one-shot/timer entries have
`completion_contract: unknown`, `recovery_contract: unknown`, and `armed: false`.
Their configuration expectation is zero, so neither successful inactive
completion nor failed completion manufactures a resolution. No last-trigger
gauge would itself prove successful completion. These held examples are not
additional managed-unit coverage; the CC must supply the actual contract before
arming them. W2's armed failure-clearing contract is separate from completion.

## Supporting pipeline and disabled independent heartbeat assets

`pipeline-scrape.example.json` declares Alertmanager21093, Grafana21301 and
Loki21300. `alerting-pipeline.rules.example.json` retains the native15-minute
notification-failure ratio and5-minute hold; it does not prove delivery during
zero traffic or sender death. The window merges these through the existing
owner provisioning path and reads back targets/rule identity.
[Alertmanager73c6bfe7 mixin](https://github.com/prometheus/alertmanager/blob/73c6bfe7393929211294c1954f30d8ed78e4d0ad/doc/alertmanager-mixin/alerts.libsonnet#L42).

`watchdog.disabled.rules.example.json` and
`deadman.disabled.fragments.example.json` remain disabled, paired examples.
Enable both only after the owner's independent heartbeat account/receiver and
private url_file exist under CC custody. A native Telegram-delivery-failure
condition may inhibit Watchdog so an external receiver detects loss; no local
component reports its own host/Alertmanager death. No new account or live
coverage is implied by these source assets.
[Pinned Watchdog](https://github.com/prometheus-operator/kube-prometheus/blob/799f3d73/jsonnet/kube-prometheus/components/mixin/alerts/general.libsonnet#L19),
[native webhook url_file](https://github.com/prometheus/alertmanager/blob/73c6bfe7393929211294c1954f30d8ed78e4d0ad/docs/configuration.md).
