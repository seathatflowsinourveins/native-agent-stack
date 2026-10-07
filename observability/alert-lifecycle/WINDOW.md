# ALERT-F09 window and single DRILL acceptance — 2026-10-07

Owner: overlap-token source; host/configuration cue: CC. Sender/installer changes:
CC/5f under [5F-HANDOFF.md](5F-HANDOFF.md). Do not apply this item from a lane
before the source's GPT read, required green CI and CC ACK. Queue the PR after
#775 and its ordered #723 rebase. No paper clock holds apply; heavy commands use
nice19/idleIO. Announce the normal brief park five minutes ahead.

## Scope and readiness

The window configures an existing Contrib0.162.0 receiver/pipeline, one new
loopback metrics endpoint and a native Prometheus scrape/rule file. It installs
no new collector process, exporter binary, client hook or agent. Proposed21890
requires CC allocation and a repeated value-free listener/ownership check.

The caller must supply a complete registered managed-unit roster, stable old
class/severity labels and final source head. The committed policy.example.json
is DRILL-only. The unit name, same-user bus access, exact metric name/labels and
observation timestamps are read-back gates. Validate/review is not their proof.

Do not fetch Alertmanager's status/config endpoint or read receiver credentials.
Allowed acceptance routes: Prometheus21090 query/alerts and Alertmanager21093
filtered alerts/metrics. Keep all returned bodies/counters private/durable.
Never print bot tokens, chat IDs or unit environment.

## Stage with native tools; preserve all live configuration

1. Retain value-free hashes and private backups of the CC-owned Collector unit,
   its base config and Prometheus config/rules. Preserve queues/cursors and all
   historical data. No lane deletes or rewrites records.
2. Render the full owned roster to a durable0700 stage:

```bash
rtk proxy nice -n 19 ionice -c3 python3 observability/alert-lifecycle/render.py \
  --policy <complete-owned-policy.json> \
  --rules-template "$PWD/observability/alert-lifecycle/user-unit-alerts.rules.json" \
  --output-dir <private-durable-stage>
rtk proxy nice -n 19 ionice -c3 <otelcol-0.162.0> validate \
  --config=<ACKed-existing-base.yaml> --config=<private-durable-stage/receiver.json>
rtk proxy nice -n 19 ionice -c3 <promtool-3.15.0> check rules <private-durable-stage/rules.json>
```

3. Through CC's supported provisioning path, add the overlay as a **second**
   Collector --config argument; preserve the original base and arguments.
   The native confmap merge adds uniquely named components/pipeline, not a
   hand-merged #775 YAML. Confirm the same user's session bus; if necessary CC
   adds only the nonsecret `DBUS_SESSION_BUS_ADDRESS=unix:path=%t/bus` to the
   owned user unit. Preserve its existing observability data/queue location.
4. Prepare the healthy scratch baseline in stageA below BEFORE enabling any
   expectation/rule entry for DRILL: mode file must already contain healthy,
   the unit must be active and its fresh source point must exist. Do not start
   it against a missing control file. Add the scrape job first and warm its
   observations; keep DRILL rules disarmed until that gate passes. Then add
   the generated rule file through the supported config writer. Preserve
   existing jobs/rules. Validate
   the complete staged config with native promtool before the reviewed reload.
   Use Prometheus's documented SIGHUP or existing reload path, not a second
   Prometheus instance. Record any Collector restart's exact UTC gap.
5. Warm source observations and compare the complete roster with installed
   managed sender scope. Before cutover the new endpoint must yield
   ns2604_user_unit_state with host/unit/state, real observation timestamps
   and declared gauge semantics; up1 alone is insufficient. No fabricated
   observations or renamed guesses qualify this gate.
6. Apply only the CC/5f-approved sender changes after full registration and state
   path read-back. Preserve C1b's accepted paper first-notice sender; its matching
   fingerprint is renewed by the primary state rule. Remove Stack's ntfy hop
   through its owner. Correct Telegram text must include unit identity and the summary/
   description so failure-versus-unknown and DRILL are visible. Retain native
   route/receiver custody and resolved delivery; do not copy its secrets.

## ONE real deliberate failure; no rerun by default

Do this only after all above gates pass. Source tests are not this drill.
Use `ns2604-F09-DRILL.service.example` as the persistent scratch user unit;
no transient unit or /tmp state. Its only native command is grep of an owned
nonsecret control file. Its OnFailure calls the accepted paper first-notice
sender so this ONE fault also tests renewal of the original missing-EndsAt alert.
The policy uses PaperLaneUnitFailed/critical, matching its current labels. Match
effective external labels before arming; otherwise stop before any real message.

A. **Establish healthy baseline without a failure, before stage4 arms DRILL.** Install the scratch unit
via the reviewed owner operation. Using native Write/Edit, create
`~/.local/state/native-agent-stack/coordination/ns2604-coop/lanes/overlap-token-durable/f09-alert-lifecycle-20261007/drill-mode`
with exactly `healthy\n` BEFORE its first start. Start the unit; it must return0 and stay active with
RemainAfterExit. Observe its fresh active state and absence of its alert before
arming this roster/rules entry. After the rules are armed, confirm no DRILL alert
and snapshot Telegram notification success/failure
counters and the filtered native evaluator/Alertmanager state.

B. **Fail it exactly once.** Edit that control file to exactly `fail\n`,
then restart only the DRILL unit. Record the expected nonzero exit, actual
ActiveState=failed, Result=exit-code and ExecMainStatus. Do not call a production
paper/embedding service and do not create another failed unit. The first real
firing message must visibly contain DRILL.

C. **Wait at least six minutes from observed firing delivery.** Use bounded
<=60-second waits in the operator's native communication/clock tool; no
background watcher. At the six-minute point capture again:
- the scratch unit is still failed;
- Prometheus's matching alert is firing;
- Alertmanager's matching EndsAt is still in the future/active;
- the receiver saw the DRILL firing message and no DRILL RESOLVED in that span;
- notification success/failure counters with observation timestamps.
Do not use global counter differences as proof of this one unit when other
alerts were delivered. Unit-filtered states and the receiver witness bind it.

D. **Recover once.** Edit control back to `healthy\n` and restart the same
unit. Record exit0, ActiveState=active and a fresh active observation. The alert
may stay firing through its deliberate30-second keep_firing_for and notification
group delay; record them. A real DRILL RESOLVED must arrive only after this
confirmed recovery. Snapshot returned states and counters again.

Do not invent a returned RESOLVED object if a native API omits ended alerts:
retain its actual response/empty result plus the real resolved notification and
the earlier firing responses. Alertmanager resolved is protocol lifecycle; it is
not by itself the unit's healthy-state witness. Keep the one-drill ledger, exact
unit/callback timestamps, sender states and receiver observation as a NEW receipt.
If a stage fails, preserve its partial result and stop; a second live drill needs
an explicit new cue. Never rewrite this attempt as passed.

## Rollback and unknown state

A failed staged validation changes nothing. If the receiver/cutover fails after
application, CC restores the prior Collector unit/config and health, preserving
all files and data. Keep the expected-roster/unknown-state protection while
observations are unavailable; removing rules merely to hide failure can itself
send a false resolution. Do not silently restore the defective one-shot lifecycle
POSTs. CC chooses an explicit administrative fallback with its source/observations
recorded; no affected unit is declared recovered without fresh evidence.

Exporter/bus outages are covered by the rule fixtures. A complete evaluator or
sender-link outage still has finite Alertmanager leases; this item does not claim
an impossible in-process guarantee across that loss. Independent sender health
observation remains with CC. No such outage or extra live drill is induced here.
