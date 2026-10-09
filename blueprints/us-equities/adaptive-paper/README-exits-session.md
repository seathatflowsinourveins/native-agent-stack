# Explicit extended-session exits

The default exit context and native strategy retain the existing RTH behavior.
The current runner constructs `AlpacaPaperTransport` with
`extended_hours_allowed=session_policy["extended_hours"]` and passes it to
`AdaptiveStrategy`. When that existing flag is true, the strategy now selects
the existing session classifier using its owner-loop clock. Default RTH runs
do not consult a calendar. A diagnostic can supply `exit_session_at` explicitly:

```python
exit_session_at=lambda now: session_at(datetime.fromtimestamp(now, timezone.utc)).kind
```

No wall clock, broker call, or new order adapter is added to the exit decision.
`ExitContext.session` accepts RTH, PRE, POST, OVERNIGHT, or CLOSED. The installed
`sessions.session_at` currently classifies only PRE/RTH/POST/CLOSED; this change
does not establish overnight runtime support. Unknown or closed sessions hold.

Outside RTH, a stale/missing/future quote flags the position and creates no new
submission or replacement. A fresh actionable exit is an explicit marketable
limit, using the existing bid/ask pricing helper. The strategy still uses the
native LIMIT/DAY order factory and its existing instrument, risk, and account
writer controls. Replacements recheck session and quote at cancellation ACK.

`last_exit_decisions` carries submit/attention/limit metadata outside the golden
serialized `Decision`. Flagged holdings retain their targets so allocation cannot
turn a hold into a portfolio-rotation exit. Runtime events include attention
reasons; partial take-profit fractions and the existing RTH thresholds remain.

The existing extended-hours construction activates this behavior without a new
runner or adapter. No frozen N2
source, protocol, STOP latch, qualification evidence, or runner/adapter is changed.
Tests use synthetic quotes and fake native order/cancellation methods; they do
not establish broker acceptance, fills, overnight admission, or live readiness.

The public source-hashes manifest binds the changed implementation bytes. The
registry ID, evidence class SYN, settings and receipt remain unchanged. The base
`strategies_v1.py` source at `3a4cc28840ba7e8a1a9474a989102a669955f243`
was SHA256 `1952be269694485e12e4d927f124adca0ee29667588d6ac6651caede454c92f7`
(27,499 bytes); this implementation is SHA256
`6f434d001489ba605f7a737e25a259be87e97127cd1c8788db504f2313af86eb`
(28,488 bytes). This source-integrity refresh does not rebind any historical
qualification or N2 frozen source pin. Native paper acceptance is **NOT_RUN**.
