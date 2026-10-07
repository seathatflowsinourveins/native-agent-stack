# F09/W2 window — design C, 2026-10-07

CC022242Z supersedes the earlier A/A-prime proposals. Apply only the exact
co-op GPT-read, green-CI, CC-ACKed source after #775. The CC/5f owns host units,
sender pins, registry, user bus and reloads. Lanes install nothing. Announce
the five-minute park; heavy source checks run nice19/ionice3. Keep backups,
queues/cursors, existing config and every recorded observation.

## Source and routing preflight

CC supplies the complete concrete managed roster and checks allocated21890
ownership. Render with render.py and an absolute rules-template to private0700
durable stage. Native Collector validates existing base plus second--config
overlay; native promtool validates the full staged config/rules. Use the
supported existing Prometheus writer/reload, not a second process. Record gaps.
Native systemd.unit.state stays unchanged and renders systemd_unit_state, with
real observed timestamps and unit/host/state labels; up1 is not this proof.

C's unit EVENT Failed routes use an integration-free name-only receiver; the
events remain visible in Alertmanager/metrics and send no human notification.
STATE PaperLaneUnitDown/StackUnitDown alone notify for unit failure with
send_resolved=true. No inhibitor. Dagu's distinct event-only route stays
separate. Quote v3 ExecStart lines unchanged in 5F-HANDOFF.md; no endsAt or ntfy
hop is added. Native amtool must accept the name-only receiver. FallbackA is
retained only if the GPT read refutes C, not simultaneously enabled.

The first unit human notice follows collection plus the rule's for, roughly a
minute. A failure clearing before collection/for can leave only the EVENT record
and no human notice. Missing/stale observations remain needs-attention, never
an inferred recovery; do not claim a brief incident was observed if it was not.
The roster explicitly distinguishes `active` from `failure-cleared` recovery.
Active requires strictly newer active observation time than contradictory fresh
non-active states, with conservative ties and failed precedence. W2 specifically
uses failure-cleared for reset-failed. Application readiness, success, completion
and cadence stay unknown; the separate G2 rows are not covered here. Keep reused
one-shot/timer entries unarmed with their completion/recovery contracts unknown.
Read back configured and armed counts separately; the examples are not coverage.

Never fetch Alertmanager's credential-bearing status/config endpoint or print
unit environment, bot values or chat IDs. Acceptance reads scoped Prometheus
query/alerts and Alertmanager alerts/metrics on21090/21093 plus receiver witness.
Counter deltas alone cannot attribute this drill amid other notifications.

## The one real W2 attempt, CC only

The handler-only old start had no origin. The new proposed source is exactly
paper-drill-w2.service: Type=oneshot, ExecStart=/bin/false,
OnFailure=paper-alert@%n.service. Do not enable it. Verify absence of a conflicting
origin and native syntax before the reviewed installation. Its handler is
paper-alert@paper-drill-w2.service.service; %i is paper-drill-w2.service, matching
the STATE unit label. Keep unit/host label read-back for both families side by side.

A. Stage the receiver/scrape and baseline counters without starting the failing
unit. Keep the scratch expectation disarmed until source readiness is established;
do not start an always-false fixture as a fake healthy baseline. Preserve other
production expectations. Coordinate its registration/arming so missing pre-start
state cannot be mistaken for a measured failure or emit a premature notice.

B. Start the origin exactly once. Retain the actual command exit and require
failed/exit-code/ExecMainStatus=1 from the native unit observation. Do not manually
start an additional handler. Observe the EVENT and fresh failed source point,
then the registered STATE alert. Record the exact two-label equality. Stop on
unmatched labels or missing source; no substitute unit or second attempt.

C. Hold actual FAILED fifteen minutes from the observed STATE firing notice,
using bounded<=60s operator waits. The expected C sequence is:

1. EVENT recorded, with no user notice.
2. One PaperLaneUnitDown firing notice, visibly labelled DRILL by the reviewed
   unit/annotation template. STATE stays firing after6m and15m while the origin
   remains failed; capture refreshed EndsAt, evaluator/Alertmanager states and
   actual notification success/failure counters with UTC times.
3. No EVENT RESOLVED notice. No STATE recovery notice while failed or unknown.

D. CC runs systemctl --user reset-failed paper-drill-w2.service. Record native
unit state and the actual fresh known nonfailed exporter point; a successful
reset command alone does not supply a metric. If the source disappears, keep
needs-attention and retain the partial result instead of inventing recovery.
After freshness/recovery debounce and group timing, record the actual STATE
recovery notice, returned state and counters. No returned RESOLVED object is
fabricated if the API omits ended alerts. Completion/success is not inferred.

Record exactly the real message sequence and receiver witness as a NEW receipt.
Source/config checks are not this drill. If any stage fails, preserve its result
and stop; no repeated real Telegram failure without a new cue.

## Cleanup and rollback

Only after confirmed recovery, CC decommissions the scratch expectation through
the supported writer, verifies it is absent/no scratch firing alert remains,
then removes the scratch unit. Retain all receipts/backups. Never remove a
failed production identity just to silence it. No timer or runtime watcher is
enabled. Restore reviewed config/health on failed application while preserving
data and unknown-state protection. Deadman stays disabled until the owner's
account/receiver exists. Whole evaluator/sender loss still has finite native
leases and is not covered by an in-process immortality claim.

## Supporting pipeline rule and heartbeat read-back

Through the same reviewed owner provisioning path, merge
`pipeline-scrape.example.json` for Alertmanager21093/Grafana21301/Loki21300 and
`alerting-pipeline.rules.example.json`. Preserve existing scrape jobs/rules,
validate the complete staged configuration with native promtool, then use the
existing reload. Read back each target/job and the notification-failure rule
identity/health; configured endpoints alone do not prove target coverage.

Keep `watchdog.disabled.rules.example.json` and
`deadman.disabled.fragments.example.json` disabled until the owner supplies the
independent account/receiver. Neither an empty integration-free EVENT receiver
nor a disabled Watchdog covers host/VM/Alertmanager death. No extra delivery-
failure or down-server drill is run under the single W2 failure authorization.

[Native receiver/routes](https://github.com/prometheus/alertmanager/blob/73c6bfe7393929211294c1954f30d8ed78e4d0ad/docs/configuration.md),
[failed-state reset](https://github.com/systemd/systemd/blob/v259.5/man/systemctl.xml),
[Contrib0.162 state schema](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/receiver/systemdreceiver/metadata.yaml).
