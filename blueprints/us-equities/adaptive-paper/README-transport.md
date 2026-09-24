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
required_quote_symbols=None, feed="iex")` on
the owning asyncio loop. The three required callbacks may be synchronous or
asynchronous and run on that same loop. `before_request(kind, client_id=None)`
must reserve the actual attempt. For POST it must reserve atomically and return
`None`/zero or refuse immediately; a positive delay is a pre-wire deferral, never
a wait under locks needed for cancellation. The caller schedules later admission
using a new validated intent. An accidentally sleeping async POST hook is canceled
after 250 ms and its unsent intent is rejected locally, preserving cancellation
access to management capacity. Read/cancel hooks may wait within the caller's
bounded overall budget deadline. Kinds are
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
unless lookup resolves the frozen intent. The one exception is Alpaca's documented
minimum-price-variance refusal: a 422 whose body code is 42210000 and whose message
contains "sub-penny increment does not fulfill minimum pricing criteria", for a
first POST whose limit price really has more than two decimals at or above $1.00
(four below), followed by an absent-ID lookup. Alpaca states such orders "will be
rejected" (https://docs.alpaca.markets/us/docs/orders-at-alpaca.md). That page
documents the body but not the HTTP status. 422 was inferred from the code prefix and
the POST /v2/orders 422 entry. It was observed once on the paper endpoint in the
2026-09-24 native-fault run (`native-faults/receipt.json`, C04). The message, not the
code, is the discriminator. The transport
raises `RejectedSubmission(422, "sub_penny_minimum_price_variance")` and compares
the body with those constants only, never retaining or raising it. The engine's
own Ledger refuses such prices before send, so only the native-fault harness,
which exempts its single C04 client ID, can reach this path. Ambiguous errors
retain unresolved state, freeze admission, and perform at most one lookup without
resubmission. `cancel()` sends the DELETE for every owned order: to the broker ID
it already observed, or, with no observation, to the ID a client-ID lookup
returns. It does not skip the DELETE because a cached or freshly read status is
terminal; the caller asked because it believes the order open or ambiguous. The
answer is data: 204 is only an acknowledgement; 404 or 422 ("The order status is
not cancelable",
https://docs.alpaca.markets/us/reference/deleteorderbyorderid-1.md) is accepted
without a freeze when the follow-up lookup shows the order terminal, and freezes
`cancellation_unresolved` otherwise; a timeout, 429 or 5xx freezes as before. Every
DELETE is followed by a lookup, never treated as a fill or terminal cancellation,
and repeating a known terminal observation changes no ledger state. All observations contain cumulative quantities; stream
observations additionally retain available execution IDs and individual event
quantity/price. Consumers must deduplicate executions and never manufacture
individual fills from a cumulative REST snapshot. A stream fill whose `execution_id`
has not been forwarded yet is forwarded even when a REST read (for example the lookup
after a cancel) already advanced the cumulative quantity past it; the stored
cumulative state never moves back. `fill_activities(order_id)` returns one order's
executions from `GET /v2/account/activities/FILL` filtered by the documented
`order_id` parameter (ascending, 100 per page, the last activity id as `page_token`),
each with its own `qty` and `price` and the order's `cum_qty` after it, and requires
them to tile the filled quantity from zero. It is the only activities read the
guarded session allows: another activity type, filter, page size or method is refused
before any request. An activity id is `<timestamp>::<uuid>`; its 36-character UUID is
the native trade id.

`ready` requires successful native authentication, an observed subscription ACK
from each socket, fresh quotes for the required benchmark basket, and no frozen
health condition. The required basket defaults to all subscribed symbols; set
`required_quote_symbols` explicitly when candidates may be quiet. Every submitted
symbol still needs a fresh quote at the wire boundary and the caller's stricter
per-symbol risk check. `_running` alone is insufficient. One shared quote
connection fans out quotes; one paper account connection receives order events.
The single configured `feed` value (`iex` or `sip`) selects both the REST quote
feed and the `wss://stream.data.alpaca.markets/v2/<feed>` stream endpoint the
connect guard pins; any other value is refused before a client, socket or
endpoint is built. Feed selection is a configuration choice, not evidence of
market-data entitlement. Native callbacks only enqueue into a bounded queue; the
owning loop runs consumer callbacks.

Halt state (E4). On the `sip` feed the quote connection also subscribes trading
statuses and LULD bands for every symbol (alpaca-py 0.44.0's
`subscribe_trading_statuses` and its `lulds` handler slot; the SDK sends every channel
in its one subscribe message per connect), and the subscription ACK must list all
three channels for every symbol (`halt_status_subscription_rejected` otherwise).
`normalize_trading_status` maps Alpaca's documented CTA and UTP status codes: CTA `2`
halts (with reason `M` a LULD pause) and `3` resumes; `5` (price indication) halts,
since the CTA's output specification (CTS Pillar v2.11b) sends it only before a
reopening after a halt; `6` (trading range indication, "a security that is not Trading
Halted"), `E` (short-sale restriction), `F` (LULD limit state) and the imbalance codes
change nothing; UTP `H`, `Q` (quotation only) and `P` (volatility pause) halt and `T`
resumes. Market-wide circuit-breaker reasons (`1`-`3`, `MWC0`-`MWC3`) are labelled; an
unknown or cross-tape code halts until a documented resume. Statuses go to
`sink_status` on the owner loop; LULD bands are kept only for receipts
(`health.luld_bands`), and a malformed band is counted, never a freeze. On `iex`
neither channel is subscribed (their availability there is unverified and a refused
channel would block readiness), so halt state then comes only from the quote-condition
fallback. The stream sends no snapshot at subscribe time: `nasdaq_halt_seed(symbols)`
reads Nasdaq Trader's trade halts RSS once (one https URL, no redirects, a 5 s deadline,
a 4 MB bound; the feed's own TTL is one minute) and returns the symbols whose latest
halt has no resumption trade time or one still ahead. A reconnect loses the status
messages sent during the gap; the next message restores the state.
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
assets and quotes on the configured feed. Its SHA-256 account identity supports
a private account lock without returning the raw account ID. `open_orders_complete=False` on a
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
