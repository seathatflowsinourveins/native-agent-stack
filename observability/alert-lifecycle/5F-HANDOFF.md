# CC/5f sender handoff, design C

CC022242Z supersedes the shared-fingerprint/A-prime proposals. Keep the staged
v3 senders byte-identical. Unit EVENT Failed routes to a name-only receiver with
no integrations; STATE Down alone sends unit-failure firing/recovery. No inhibitor.
Dagu's distinct event route is unchanged. Source applies nothing; CC/5f owns
units, installer hashes, user bus, roster and native reloads.

Paper source SHA3578e8b4580601425afb2277f6f8604a7a0d2da4dd131799de9d1f1e2510eb23:

```ini
ExecStart=/usr/bin/curl -fsS -m 10 -H "Content-Type: application/json" -d '[{"labels":{"alertname":"PaperLaneUnitFailed","severity":"critical","unit":"%i","host":"NativeStack2604"},"annotations":{"summary":"paper lane: %i failed","description":"see journalctl --user -u %i on NativeStack2604"}}]' http://127.0.0.1:21093/api/v2/alerts
```

Stack source SHAfd67734ce3cfaa57a1f67113ebe70b1b2df23037cd0eee02782878d55a17a138:

```ini
ExecStart=/usr/bin/curl -fsS -m 10 -H "Content-Type: application/json" -d '[{"labels":{"alertname":"StackUnitFailed","severity":"critical","unit":"%i","host":"NativeStack2604"},"annotations":{"summary":"stack unit failed: %i","description":"see journalctl --user -u %i on NativeStack2604"}}]' http://127.0.0.1:21093/api/v2/alerts
```

No ntfy hop/endsAt is added. EVENT and STATE alertname families intentionally
differ; do not pretend they share renewal fingerprints. Register concrete
unit/host/class/severity from the same owner input that renders observations
and independent expectations. Missing/stale state cannot qualify recovery.
Clearing failed is not readiness/completion/cadence; G2 remains separate.

Register the explicit unit kind, armed flag, recovery contract and completion
contract. Continuous services may require latest-active recovery; the named W2
drill requires failure-cleared for reset-failed. Reused one-shot/timer services
remain unarmed with both contracts unknown. Neither their successful inactive
state nor a last-trigger timestamp is proof of successful completion. Do not
expand the armed roster from a version check or an example entry.

W2's proposed paper-drill-w2.service uses Type=oneshot, ExecStart=/bin/false,
OnFailure=paper-alert@%n.service. The handler is
paper-alert@paper-drill-w2.service.service and %i equals paper-drill-w2.service.
Read EVENT/STATE host and unit side by side. The old handler-only attempt had no
origin and is not state qualification. CC alone installs/starts one deliberate
failure, holds fifteen minutes, resets failed, records fresh source and actual
STATE recovery, then removes the scratch scope. No second drill or production
unit change. See WINDOW.md; prior receipts are retained.

First human notice is delayed by collection/for; shorter unobserved failures can
have EVENT record only. Native amtool accepts C's integration-free receiver.
FallbackA stays a separate source variant for GPT refutation, not live at once.
[Pinned receiver/route contract](https://github.com/prometheus/alertmanager/blob/73c6bfe7393929211294c1954f30d8ed78e4d0ad/docs/configuration.md).
