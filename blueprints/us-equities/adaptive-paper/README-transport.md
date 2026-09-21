# Paper transport and measured rate boundary

`transport.py` composes the native **alpaca-py 0.44.0** REST client, TradingStream
and StockDataStream. The reviewed upstream revision is
[`cc4cb3b7ba50ae250e621983c2779047fb16bb28`](https://github.com/alpacahq/alpaca-py/tree/cc4cb3b7ba50ae250e621983c2779047fb16bb28).
Runtime version checking does not attest to an installed package's file hashes.
The caller supplies explicit paper credentials, holds the account writer lock,
and owns durable numeric risk, execution accounting and request reservations.
This module does not load environment files or discover credentials.

## Contract

Construct `AlpacaPaperTransport(api_key, secret_key, symbols, *, before_request,
before_submit, sink_observation, request_observer=None, history_start=None,
required_quote_symbols=None)` on
the owning asyncio loop. The three required callbacks may be synchronous or
asynchronous and run on that same loop. `before_request(kind, client_id=None)`
must reserve the actual attempt, waiting within the caller's deadline or raising;
a positive delay return value does **not** cause an automatic wait. Kinds are
`submit`, `cancel`, `read`, and `data_read`; POST supplies its stable client ID.
Every Trading HTTP attempt, including reconciliation and unsuccessful requests,
passes that hook under one shared request lock. The optional request observer
receives only `{kind, status, headers}` with an explicit rate-header allowlist.

`before_submit(intent)` must durably record and validate the frozen intent before
it returns. Tags, strategy and reason are available to this hook and excluded
from the SDK payload. Whole-share buys and decimal owned-position exits use
regular-session DAY limits. The caller verifies fractionability and available
owned quantity. Current [fractional order documentation](https://docs.alpaca.markets/us/docs/fractional-trading)
supports fractional DAY limits; quantities are never truncated to integers.

The async methods are `start(on_quote, on_order)`, `submit(order)`,
`cancel(client_order_id)`, `snapshot()` and `stop()`. `adopt_intents()` imports
the caller's recovered durable intents. A repeated ID is looked up, never posted
again. Broker 401/403/404 refusals with a confirming absent-ID lookup, and a
locally prevented request, expose `definitive_rejection=True`. A 400 or 422 may
mean a duplicate ID whose earlier order is not visible yet; it remains ambiguous
unless lookup resolves the frozen intent. Ambiguous errors retain unresolved
state, freeze admission, and perform at most one lookup without resubmission.
Cancellation acknowledgements are followed by a lookup, not treated as fills or
terminal cancellations. All observations contain cumulative quantities; stream
observations additionally retain available execution IDs and individual event
quantity/price. Consumers must deduplicate executions and never manufacture
individual fills from a cumulative REST snapshot.

`ready` requires successful native authentication, an observed subscription ACK
from each socket, fresh quotes for the required benchmark basket, and no frozen
health condition. The required basket defaults to all subscribed symbols; set
`required_quote_symbols` explicitly when candidates may be quiet. Every submitted
symbol still needs a fresh quote at the wire boundary and the caller's stricter
per-symbol risk check. `_running` alone is insufficient. One shared IEX connection fans out
quotes; one paper account connection receives order events. Native callbacks
only enqueue into a bounded queue; the owning loop runs consumer callbacks.
Reconnect, stale quotes, missing initial order updates, malformed callbacks and
overflow stop new exposure. After inspecting and reconciling a fresh complete
snapshot, the caller may explicitly call `mark_reconciled()`. Queue loss or
callback failures require a new transport and durable recovery. Risk-reducing
sells still require the caller's numeric validation and a fresh quote immediately
before the wire request. Shutdown joins owned non-daemon stream threads and
reports failure if they do not terminate. Await in-flight REST operations before
stopping the owner loop.

Snapshots include **all open account orders**, all orders since `history_start`,
and any adopted owned IDs missing from those lists. The caller must provide its
original run start when resuming. Official ID-cursor pagination is used through
the SDK's native `get`; a repeated page or the bounded page ceiling fails
completeness instead of returning success. A snapshot does not atomically freeze
broker state; the caller reconciles concurrent stream observations. Synchronous
`preflight()` uses only guarded GETs for account, clock, positions, open orders,
assets and IEX quotes. Its SHA-256 account identity supports a private account
lock without returning the raw account ID. `open_orders_complete=False` on a
full 500-order page prevents claiming an empty account from a truncated list.
Missing or invalid per-symbol quotes are returned as sanitized `quote_errors`
alongside the valid quotes, preserving clock/account/asset readiness evidence
after hours. The caller still requires valid fresh benchmark and execution quotes
before admitting any order; a closed-session report is not paper execution.
The clock includes `received_at_ns`, captured immediately after its GET, so
later asset requests do not contaminate clock-offset checks. Transport quote
checks use the same 250 ms future-timestamp tolerance as the safety layer.

## Upstream constraints and benchmark interpretation

The current [Trading API limit](https://alpaca.markets/support/usage-limit-api-calls)
is 200 calls per minute per account unless a different entitlement is observed.
[Alpaca staff](https://forum.alpaca.markets/t/what-constitutes-an-api-call/16502/3)
includes order submissions, account state and order queries under that common
Trading budget. Cancels also call the same API. A 180 POST/minute budget with
20 calls reserved for management includes **both buys and sells**: its ideal
ceiling is 90 two-order round trips, and neither acceptance nor fills are
guaranteed. Other clients can consume the same quota. Data quotas are separate;
counting data reads conservatively in the local budget is allowed.

[Order push events](https://docs.alpaca.markets/us/docs/websocket-streaming)
remove repeated REST polling; no blanket handshake quota exemption is assumed.
The [market-data stream](https://docs.alpaca.markets/us/docs/streaming-market-data)
normally allows one connection per endpoint, and slow consumers can be dropped.
The pinned SDK already reconnects with jittered exponential backoff, closes
half-open sockets and optionally detects muted stock streams; this adapter sets
that watchdog and adds explicit ACK health. A small handshake protocol guard
rejects WebSocket redirects before credentials can be sent to another endpoint.
REST disables retries after construction (the pinned constructor ignores zero),
environment proxies and redirects, with finite connect/read timeouts.

The official legacy
[`example-hftish` revision `39205cc265e9964c927f8f660fac3c7d0ee516ce`](https://github.com/alpacahq/example-hftish/tree/39205cc265e9964c927f8f660fac3c7d0ee516ce)
uses an old SDK and submit-then-cancel flow: at least two calls per attempt.
It is a conceptual strategy reference, not the transport chosen here.
Official [Elite advanced order documentation](https://docs.alpaca.markets/us/docs/alpaca-elite-smart-router)
says accepted paper `advanced_instructions` orders are not simulated; this
transport therefore rejects that field. Paper fill behavior also omits several
real-market effects documented in [paper trading](https://docs.alpaca.markets/us/docs/paper-trading).

A bounded broker trial should freeze symbols, position/loss limits, maximum
duration, cleanup reserve and its measurement window before starting; verify
stream ACKs and fresh quotes; increase its submission cap only within those
limits; stop admissions on rate/stream/state failures; then reconcile owned
orders, cash and positions. Report HTTP attempts, POST attempts, accepted orders,
fully filled orders, individual execution events and completed round trips
separately, including elapsed time and the largest rolling 60-second totals.
No target rate should force a trade or erase a risk check. These are procedure
constraints, not a claim of an executed benchmark.

## Verification scope

With the reviewed isolated SDK runtime, run:

```sh
python -m unittest discover -s tests -p test_adaptive_paper_transport.py -v
```

These are local synthetic integration/failure tests with mocked HTTP and streams.
They exercise the real SDK's HTTP serialization and exception behavior but do
not establish authenticated connectivity, fill throughput, a profitable strategy
or a complete native trading engine. The first run had one mistaken duplicate
ID in the pagination success fixture, correctly rejected by the implementation;
the fixture was corrected. Public-run thread lifecycle uses a local fake stream;
actual network shutdown/reconnect still requires bounded paper acceptance.
