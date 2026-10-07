# User-unit failure lifecycle — 2026-10-07

Status: source/configuration decision for ALERT-F09, under the user's current fix
direction and the repository quality rule. Deployment, bus/metric-shape read-back
and one real Telegram DRILL remain pending. Existing delivery evidence stays valid;
delivery and truthful recovery semantics are separate.

## Problem and pinned evidence

A one-shot direct client that omits EndsAt gets Alertmanager's five-minute default
lease. Repeat interval does not renew it. The user reported a real failed paper
unit followed by a RESOLVED Telegram message without unit recovery. Installed
sender/disk-config source matches that contract; loaded runtime settings were not
retrieved from the credential-bearing status/config endpoint.
[Alertmanager0.34.1 /73c6bfe7](https://github.com/prometheus/alertmanager/blob/73c6bfe7393929211294c1954f30d8ed78e4d0ad/docs/configuration.md#L144).

The bounded read-only Prometheus name snapshot contained no explicit user-unit
state metric. Endpoint up and process health cannot substitute for manager state.
This is scoped discovery evidence, not a global absence claim.

## DECIDED

Use the already selected Collector Contrib0.162.0 systemd receiver with documented
user scope; configure only the authoritative managed-unit roster. Keep a dedicated
timestamp-preserving state export separate from the existing privacy/counter
pipelines. No new exporter process or client agent is adopted.

Use a native Prometheus expected-unit recording roster independent of telemetry.
Require fresh observed active manager state for recovery; fresh failed
state takes precedence. Missing units, stale cached points, bus failures, up0 and
absent targets remain recovery-unverified. Stable host/unit/severity/alertname
labels survive the failed-to-unknown transition. Unknown can raise a conservative
attention alert even without an earlier observed failure; its text says so.

For30 seconds and keep_firing_for30 seconds debounce activation/recovery. A
45-second freshness budget is three15-second collection periods; it is a policy
constant with explicit cases, not a measured optimum or an indefinite grace
claim. The expected roster, not keep_firing_for, prevents disappearance from
resolving an incident while Prometheus continues evaluating.

The CC's later ruling keeps C1b's accepted paper one-shot first notice. Match its
fingerprint to the registered state rule, which owns continued renewal/recovery.
Stack loses its old ntfy hop through its owner; no extra per-unit drop-ins are
introduced for covered units. A no-resolved route applies only to genuine events,
such as DaguDagFailed. CC/5f applies the handoff through its SHA-pinned installer;
this lane changes neither sender nor host configuration.

The state receiver does not export service Result. Inactive alone therefore
does not establish successful completion. Unique one-off units require their
owner's native RemainAfterExit=yes successful-state retention; recurring jobs
keep their event/success contract. An inactive unit without explicit success
remains attention/unknown rather than causing a guessed recovery. The broader
hidden-dependency coverage must not be claimed from the state gauge alone.

Prometheus's own outage or lost sender link remains a distinct finite-lease
boundary. A notification lifecycle transition is not independent health evidence.
Independent sender observation is owned by CC; no in-process indefinite sender
loss guarantee is claimed.

## Alternatives and repository quality

- prometheus-community/systemd_exporter v0.7.0 has the explicit user flag and
  maintained tests, but its2025-03-14 clean release fails the180-day release gate.
  [Release](https://github.com/prometheus-community/systemd_exporter/releases/tag/v0.7.0),
  [user connection](https://github.com/prometheus-community/systemd_exporter/blob/v0.7.0/systemd/systemd.go#L696).
- node_exporter v1.12.1 has current release/tests, but the inspected native
  collector uses the system/private bus, not a documented user scope. No claim
  about an uninspected custom environment workaround is needed.
  [Source](https://github.com/prometheus/node_exporter/blob/v1.12.1/collector/systemd_linux.go#L448).
- Contrib0.162.0 is already installed/selected, current, self-hosted and Linux
  distributed, with receiver and mixed-context tests. Its user receiver is alpha,
  which remains a limitation until the authorized runtime read-back.
  [User scope](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/receiver/systemdreceiver/scraper.go#L44),
  [receiver tests](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/receiver/systemdreceiver/scraper_test.go#L131).
- A longer resolve_timeout does not fix Prometheus alerts, which supply EndsAt.
  Far-future EndsAt and send_resolved=false conceal expiry without proving recovery.
- A finite keep_firing_for alone eventually resolves during a longer outage.
  A disappeared failed metric, up0 or missing unit is not an explicit healthy state.
  [Native staleness](https://github.com/prometheus/prometheus/blob/v3.15.0/docs/querying/basics.md#L469).
- A separate polling notifier/controller adds a second lifecycle owner despite
  existing native receiver/rule capabilities; it is unnecessary.

No star counts, new candidate trial or benchmark result decides this selection.
The source quality comparison follows
[the repository rule](2026-10-04-repository-quality-rule.md).

## Validation and remaining gates

Native promtool fixture groups cover failure beyond6 minutes, explicit recovery,
ten-minute exporter outages, missing/stale/cached observations, pending
cancellation, overlapping states, future timestamps and unregistered identity.
These are synthetic rule tests, not live Telegram messages. Native Collector
validation does not start its user-bus receiver. Renderer checks protect input and
roster consistency; no native state is fabricated by expectation vector1.

CC/5f must provide the full registered scope and stable old label classification,
allocate the proposed listener, establish same-user bus access and apply the
reviewed source. One persistent scratch unit, marked DRILL, then fails once.
Observe firing delivery, still-firing after6 minutes without RESOLVED, and a
resolved delivery only after explicit fresh terminal recovery. Retain native
states/counters and the receiver witness. Do not rerun the live drill silently.

## Overturn

Replace the chosen receiver if documented user scope does not operate in the
target window, if timestamp/label fidelity fails, or if a qualified clean-release
candidate supplies stronger tested semantics with fewer moving parts. Refine
freshness/healthy states only through a reviewed policy change with preserved
failed conditions. Roster removal or label churn is not a recovery mechanism.

## Amendment (2026-10-07): wider hidden-dependency routing

The later CC ruling keeps the paper first-notice path accepted by5f and makes
state rules primary for continuous unit lifecycle. Dagu job events alone use
the separate no-resolved receiver. Stack's old ntfy hop is an owned installation
change; no new per-unit OnFailure drop-ins are introduced for covered units.

The current policy requires fresh active state; inactive alone never proves
success because the chosen metric lacks Result. Owner-managed retained-success
one-offs are the native supported form; other completion contracts remain
explicit, not inferred. Fourteen current synthetic groups include an inactive
silent-stop case. The earlier thirteen-group active-or-inactive result is a dated
earlier-policy result and is not current-policy acceptance.

The PR carries the maintained Alertmanager notification-failure mixin and
disabled paired Watchdog/deadman examples, with external custody owned byCC.
Disabled examples are not independent failure detection. No new start-gating
row or old-distribution dependency is adopted; stale live-guidance edits that
overlap #775 wait for that owned landing chain.
