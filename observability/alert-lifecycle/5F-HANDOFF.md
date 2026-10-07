# CC/5f handoff: primary state rule, accepted first notice

Owned targets remain CC/5f's; this PR edits none of them:
- `~/.config/systemd/user/paper-alert@.service.d/10-alertmanager.conf`
- `~/.config/systemd/user/stack-alert@.service`
- their installer and SHA256 pins.

## Registration and exact label contract

Supply the complete concrete managed-unit policy before activating the source.
Retain host, unit, severity and alertname as stable identity. The current POSTs
use NativeStack2604 and severity critical for both classes. The paper first notice
must match the effective Prometheus alert after external labels/relabeling, not
just its rule expression. Do not assume deduplication without that returned check.
Register future concrete job instances before launch; template/glob names are not
incident identities. The DRILL-only policy is not a production inventory.

The same roster generates both receiver units and recurring configuration
expectations, independent of disappeared telemetry. Match all active legacy
fingerprints before cutover so a forgotten manual lease cannot expire as a
false recovery.

## Sender changes under the later CC rulings

Preserve C1b's accepted paper POST without EndsAt. Prometheus is the PRIMARY
state lifecycle and refreshes that same fingerprint. Do not add a no-resolved
route for PaperLaneUnitFailed or StackUnitFailed.

For the Stack template, remove only its old ntfy ExecStart hop (legacy18080).
Keep its existing local Alertmanager POST and Type=oneshot, including these
unchanged labels in the POST body:

```json
{"alertname":"StackUnitFailed","severity":"critical","unit":"%i","host":"NativeStack2604"}
```

The target is the owned NativeStack2604 Alertmanager21093 route. The owner updates
SHA pins from its exact new bytes and uses its supported install/read-back.
Do not add per-unit OnFailure drop-ins for coverage supplied by the state rule.
The lane neither edits these files nor fabricates their new hashes.

Genuine event-style DaguDagFailed uses the separate no-resolved route in
alertmanager-events.example.json. A job event contains no continuous recovery
observation. The state classes retain send_resolved=true.

## One-offs and silent stops

Contrib0.162 state classification does not expose service Result. Inactive alone
therefore never qualifies recovery in this policy. For unique one-off units whose
successful completion must stay healthy under this state rule, the unit owner
uses the systemd-native retained-success form:

```ini
[Service]
Type=oneshot
RemainAfterExit=yes
```

Successful completion remains active; failure remains failed. Do not impose this
on recurring reused timer services without checking their start contract. Such
event-style jobs need their own explicit completion/event semantics. An inactive
unit without completion proof stays recovery-unverified, catching silent stops.
No hidden-dependency class is declared accepted from an unobserved Result value.

CC owns same-user bus access, port allocation, full roster and native reloads.
No unresolved roster identity or class/severity is removed/changed merely to
silence it; that changes a fingerprint, not health. Preserve the original
Telegram delivery receipt and append new semantic/cutover evidence.
