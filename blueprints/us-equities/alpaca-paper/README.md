# Bounded Alpaca paper order lifecycle

This is a native `alpaca-py==0.44.0` operational smoke adapter. It buys at most one
SPY share, observes the position briefly, then sells only the reconciled filled
quantity. It does not select a strategy or establish profitability. The separate
[paper-lane policy](../../../docs/paper-lane-policy.md) authorizes these bounded
paper orders without another approval token.

[config.json](config.json) freezes the trial. Changing a field requires changing
the reviewed code and tests: arbitrary CLI risk overrides are rejected.

| Boundary | Frozen setting |
| --- | --- |
| Endpoint / SDK / feed | Paper only / alpaca-py 0.44.0 / IEX |
| Instrument / entry | SPY / one share, marketable DAY limit, regular session |
| Allocated paper capital / order notional / gross exposure | $1,000 each |
| Account prerequisite | ACTIVE USD, unblocked, equity at least $25,000, sufficient buying power |
| Initial account | No positions and no open orders |
| Price / data | Positive uncrossed quote, spread at most $0.50; age at most 15s against bounded broker clock |
| Clock / session | Server offset at most 5s; at least 300s before close at entry, 60s at exit |
| Entry / exit offset | $0.05 beyond ask / bid, with exit loss floor |
| Loss bound | $5 maximum gross realized price loss; excludes fees and unrealized gap loss |
| Observation / order / cancel windows | 3s position observation / 20s order / 15s cancel reconciliation |
| Transport / trial | 5s connect and 5s read timeout; 180s trial window per invocation |
| Request / write limits | 120 total HTTP requests per rolling minute; four write attempts over the durable trial |

The paper account's large balance is not allocated to this trial. The target of
1,000 trades/minute is not configured or qualified here. HTTP requests and trades
are different counts; all requests, including reads, share the conservative
budget. The initial read-only account identity lookup precedes account locking;
subsequent request history persists across restart. The rate limit is scoped to
this runner, so an unrelated API client must not use the account concurrently.

Use the installed isolated equity-worker SDK interpreter as `SDK_PYTHON`. Load
the authorized paper credentials into only this process's `APCA_API_KEY_ID` and
`APCA_API_SECRET_KEY` environment variables. Do not write credentials into this
checkout, commands, receipts, or logs.

```bash
"$SDK_PYTHON" blueprints/us-equities/alpaca-paper/paper_runner.py
"$SDK_PYTHON" blueprints/us-equities/alpaca-paper/paper_runner.py --execute --trial smoke-20260921
"$SDK_PYTHON" blueprints/us-equities/alpaca-paper/paper_runner.py --recover --trial smoke-20260921
```

The first command only performs preflight reads. The CLI returns sanitized JSON
and exits zero for successful preflight or a complete round trip. Failed or
incomplete trials exit two. A broker rejection or zero/partial entry fill remains
inconclusive even when cleanup leaves the account flat. Only a complete one-share
buy/sell with observed flat account and no open orders returns `passed`.

State lives under `~/.local/state/native-agent-stack/alpaca-paper/`. All CLI trials
use one fixed account-derived lock namespace, and one durable journal per account.
Each intent and every HTTP write attempt is flushed and fsynced before transport;
the containing directory is fsynced when the journal is opened. Client order IDs
remain stable across restart. An existing trial requires matching `--recover`;
there is no automatic reset, second trial, or automatic entry on recovery. Recovery
has a fresh 180s observation window but retains the original four-write budget.

Create `~/.local/state/native-agent-stack/alpaca-paper/STOP` to block new entry.
Cancellation and the bounded exit remain allowed. Kill state persists across
restart. Ambiguous submissions are queried by client ID and never blindly
resubmitted; cancel acknowledgement does not imply final filled quantity. Recovery
only manages identities recorded by this runner. External orders and positions
are never canceled or closed. This lock coordinates this CLI, not every possible
external account user.

Limits do not guarantee execution: an unfilled exit, broker outage, contradictory
snapshot, expired observation window, or exhausted write budget produces
`needs_attention`. The existing account position/order must then be reconciled.
The runner never claims flatness without observing it and never uses a live
endpoint, market order fallback, or blanket close/cancel to manufacture success.
The price floor bounds gross realized fill loss; it cannot bound unrealized loss
while a position remains open. Fees, realized account P&L, and streaming reconnect
behavior require separate acceptance.

Implementation reuses the original [order contract](../order-contract/order_contract.py)
for whole-share basic-equity intents. A partial-fill exit uses the exact observed
decimal quantity (at most one share), rather than increasing it to a whole share.
The native request models validate that exit too. This partial case has synthetic
coverage; native fractional exit behavior is not established by these tests.

Source reviewed: [alpaca-py v0.44.0](https://github.com/alpacahq/alpaca-py/tree/v0.44.0),
especially `alpaca/common/rest.py`, `alpaca/trading/client.py`, and
`alpaca/data/historical/stock.py`. The pinned private seam sets `_retry=0`, disables
environment proxy inheritance and redirects, and enforces finite timeouts plus
a strict origin/method/path allowlist. The SDK still owns authentication, request
models, serialization and broker response parsing.

```bash
"$SDK_PYTHON" -m unittest discover -s tests -p test_alpaca_paper.py -v
python3 scripts/validate.py
```

The tests are local synthetic adapter failures, including timeout after acceptance,
partial fills and cancel races, rate limits, crash/restart identities, lookup
visibility gaps, stale quote at the final request boundary, malformed risk input,
kill state and account lock contention. They do not establish upstream broker
behavior. A native run must retain its returned receipt and independent account
observations before the paper lane is described as executed.
