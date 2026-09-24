# Native live engine adapter boundary

`native_adapter.py` connects an injected `BrokerPort` to the actual NautilusTrader
2.0.0rc5 `LiveNode`. Python strategy orders pass through native risk, execution,
portfolio and cache processing. This is not a backtest engine or a separate
strategy loop. The injected port alone owns credentials, API calls, streaming,
durable intent/rate/risk gates and observed broker state.

The original upstream `examples/live/_template/{factories,data,execution}.py`,
`python/nautilus_trader/live/clients.py` and
`python/tests/integration/test_python_adapter_template.py` were inspected at
[1b0a49d2792a9432a3aca3fcb617ce7a630d905e](https://github.com/nautechsystems/nautilus_trader/tree/1b0a49d2792a9432a3aca3fcb617ce7a630d905e).
The [official custom-client guide](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/developer_guide/python_adapters.md)
defines owner-loop cache/output access, synchronous factories, supervised async
hooks and native reconciliation. This adapter uses those supported interfaces.

`build_node(port, symbols, strategies, account_id=..., account_type=...)` returns
a `NativeSession` with `.node`, `.handle`, `.run_async()`, `.stop()`, `.errors` and
`.unresolved_orders`. Supply the preflight-derived `ALPACA-...` account identity,
explicit instrument metadata and actual account type. The default native rate
limit is 180 submits/minute; the transport must separately budget **all** broker
requests and reserve cancellations/reconciliation. Neither setting proves fills
or throughput. The observed broker rate, numerical risk and session limits belong
to the coordinator's policy.

The port contract is async `start(on_quote, on_order)`, `stop()`, `submit(dict)`,
`cancel(client_order_id)`, `snapshot()` and `fill_activities(order_id)` (every
execution of one broker order, oldest first, each with its own `qty`, `price` and the
order's `cum_qty` after it). Callbacks run on the native owner loop.
Data and execution clients share one started/stopped port. Metadata has `symbol`,
`currency` (USD), `price_precision`, `price_increment` and `lot_size`; the final
three default to 2, 0.01 and 1. Quotes are native `QuoteTick` values delivered to
`Strategy.on_quote`, after `self.subscribe_quotes(instrument_id)`.

Supported entry commands are whole-share equity LIMIT/DAY. Order tags, strategy
identity and an optional `reason=...` tag remain in the port payload for journal
attribution; the transport strips these before SDK serialization. Native order
submission precedes the awaitable broker request, but acceptance, cancellation
and fills require returned confirmations.

Fills are booked one broker execution at a time (E2 of the 2026-09-24 convergence
record). A `fill` or `partial_fill` trade update that carries `execution_id`, `qty`
and `price` becomes exactly one native `OrderFilled`: `TradeId` is the execution id
(a 36-character UUID, rc5's `TradeId` limit; a longer id is digested to 36
characters) and `last_px` is that execution's price. No price is ever derived from
Alpaca's cumulative `filled_avg_price`, which is rounded to 6 decimals: under the old
cumulative booking the 2026-09-24 APUS sell (26 @ 5.62, 2 @ 5.61, 1 @ 5.61; averages
5.62, 5.619286, 5.618966) derived an off-grid 5.610004 and froze the adapter.
Executions are keyed by the order's cumulative quantity after them, so a repeated,
reordered or REST-overtaken delivery never books twice; a conflicting or overlapping
execution freezes. A cumulative quantity that no booked execution explains is a fill
gap. If it is still open after `fill_gap_grace_seconds` (2 s), the adapter reads the
order's executions once through the port's `fill_activities` (`GET
/v2/account/activities/FILL?order_id=`) and books the missing ones, joined on
cumulative quantity: that an activity id's UUID equals the stream `execution_id` is
not documented. A cancel or expiry reported before its fills (for example by the REST
read after a cancel) waits for them. These still freeze for reconciliation: an
execution after the native terminal event, a changed average at an unchanged
cumulative quantity, a gap the activities cannot close, a replace event, the rare
`done_for_day`, `calculated`, `stopped`, `suspended` and `restated` events, and any
undocumented event string. Trade corrections and busts are not `trade_updates`
events (Alpaca documents them only as activities, `/v2beta1/events/activities`,
which this release does not consume). The executions' notional is compared with
`filled_qty x filled_avg_price` within Alpaca's rounding and a difference is recorded
(`average_invariant_mismatches`), never a freeze. Receipts carry `execution_stats`;
its `fill_events_missing_execution_fields` is E2's overturn metric and must stay 0
on paper.

Only exceptions with `definitive_rejection=True` become native order rejections.
`NativeOrderRejected` is provided for a refusal known to occur before acceptance.
Other submission errors leave the native order unresolved, record an error and
stop new native work; they never cause blind resubmission or fabricated rejection.
Cancel/replace semantics are bounded: confirmed cancels are supported; replacement
is explicitly rejected. Outstanding broker positions/orders are not silently
liquidated or claimed closed by `stop()`; the root recovery path owns disposition.

Startup requires an actually flat broker account with no open orders. Closed
historical rows remain in the external journal rather than being manufactured as
new native fills. Non-flat recovery is reconciliation/liquidation outside this
new native session; resumed native strategy entry is not qualified. Initial
reconciliation uses explicit empty order/fill/position reports only after checking
that snapshot. With `overnight_holds` an adopted open order that has fills reports one
`FillReport` per execution from its FILL activities, which must tile the snapshot's
filled quantity (`historical_fill_ledger_incomplete` otherwise); a port without
`fill_activities` still refuses (`historical_fill_ledger_not_supplied_by_port`). Unknown
stream orders are sent as native status reports, never assigned to a strategy by
guessing an intent.

The native v2 `Equity` model has size precision 0 and size increment 1 even when
given a fractional lot size. A fractional broker fill therefore **freezes this
adapter**, retains the exact incoming row in `.unresolved_orders`, and leaves the
actual fractional residual for the root transport/journal to reconcile and exit.
There is no integer truncation or false flatness. The port does not supply fee
amounts: native events currently book zero commission, explicitly requiring
external fee reconciliation before a net-PnL claim. Account buying power/equity
are preserved as metadata, not relabeled as cash; locked-cash fields are not
supplied by the current port. Automatic leverage is a root risk/account decision,
not something this adapter infers from an account-type flag.

Custom Python clients cannot use Redis/PostgreSQL native cache backing in this
version. This node uses an in-memory cache; durable recovery is the port's journal
and broker reconciliation responsibility. No credential reads, broker client,
data acquisition or external model calls are present in this module.

## Order and position callbacks (E3)

NautilusTrader 2.0.0rc5's `LiveNode` discards an exception raised in a Strategy order
or position callback (upstream issue #5039: `strategy.rs` dispatches with `let _ =`).
`UpstreamCallbackLoss` in `tests/test_adaptive_paper_native.py` reproduces this on the
pinned wheel: nothing reaches the session, dispatch continues, and the raising call's
own bookkeeping is lost. Every `on_order_*` and `on_position_*` handler of
`AdaptiveStrategy`, `MoverStrategy` and `CapacityProbe` is therefore wrapped by
`guarded_callback`. On an exception the guard records the callback name, exception
type and a traceback SHA-256 (`callback_faults`), latches `faulted` (no further submit;
cancels still go out), freezes the ledger with
`strategy_callback_exception_<handler>`, calls the runner's `fault_sink`
(`NativeSession.fail`: the node stops and the adapter denies every submit) and
re-raises. The run ends `needs_attention` and any residual goes to recovery. An AST
test fails on any unwrapped handler. Overturn: a released version that surfaces the
exception or stops the node fails the characterization test, and the guard can then
shrink to record and freeze.

## Verification

```sh
"$NAUTILUS_ENV/bin/python" -m unittest tests.test_adaptive_paper_native -v
```

The pinned installed runtime is Python 3.12.3 / Nautilus 2.0.0rc5. Seven local
checks pass, including real `LiveNode` startup, native strategy quote callbacks,
two submitted/accepted orders, four distinct partial-fill events with repeated
deliveries, and a completed flat roundtrip. Other cases verify actual cancel
confirmation deduplication, definitive refusal, ambiguous submit without retry or
fake rejection, fractional residual preservation, and dirty-startup refusal.
The transport is fake in these tests. They qualify this local native integration,
not upstream acceptance, live connectivity, strategy performance or broker E2E.
On hosts without the native engine the seven tests are explicitly skipped.

Two development failures were retained in session evidence: factories initially
omitted required `DataClientFactory`/`ExecutionClientFactory` inheritance, and a
test used the old cancellation object argument instead of v2's `ClientOrderId`.
Both were corrected against original upstream source before the passing run.

The final 2026-09-21 run also passed all seven checks in 1.386 seconds inside a
fresh `bwrap --unshare-all --clearenv` namespace with only the native runtime,
repository and system libraries mounted: no network interface other than
loopback and no credential stores. Raw stdout/stderr are retained privately at
the private observation folder `adaptive-paper-native-20260921/native-tests-start-order.*`.
The test stderr SHA-256 is
`4561f78cce2993cde3458c842f454ed10b1919e5ef0b1d835eed3665dc1eaf33`;
stdout is empty. Tested adapter SHA-256:
`d95fc8aab6a77adc6d6431d7cbe4566a673afa547b09b4512d1fbaa1f6839206`.
Test source SHA-256:
`92b09a1aadba25266cb143dd7c421f3d7fcd9a77135ad5c7da6266cf11a4610d`.
The execution client's first snapshot now explicitly waits for the shared port's
start, which binds the owner loop used by real transport REST callbacks. The
dirty-startup regression exercises execution connection independently of data
connection to catch reliance on incidental task ordering.

`python3 scripts/validate.py` passed (68 components, 1,396 hashed files, 4
profiles, 125 receipts); `python3 scripts/validate_catalogs.py` passed and
`git diff --check` exited zero. These are repository integrity checks, not native
upstream acceptance or broker qualification.
