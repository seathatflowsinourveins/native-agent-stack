# IBKR paper order acceptance on NautilusTrader 1.231.0

A bounded, predeclared paper order run that goes end to end through
NautilusTrader's own Interactive Brokers execution engine (TradingNode, the
Python `InteractiveBrokersDataClient`/`InteractiveBrokersExecutionClient`, the
risk and execution engines, the cache and the portfolio) against a signed-in
**paper** IB Gateway or TWS. It covers a bounded subset of
`../acceptance-plan.md` section 5, steps 2-4: frozen bounds, submit/acknowledge,
cancel, fill, flatten and the end-of-run disposition. It does not cover
reconnecting with an open order or restart reconciliation, so on its own it
cannot establish the `ibkr-local-acceptance` gate.

Evidence class: `native_paper` (paper account only). It is **not** the pinned
destination version (2.0.0rc5), so a passed receipt cannot flip
`ibkr-local-acceptance` unless a dated version-selection record accepts 1.231.0
for that gate.

## Why 1.231.0

The pinned 2.0.0rc5 Rust IB adapter denies every stock order locally: the
execution client's `IB` venue never matches the `SMART` instrument venue
([nautilus_trader#4983](https://github.com/nautechsystems/nautilus_trader/issues/4983),
see `../ibkr-acceptance/README.md`). 1.231.0 is the newest stable release and
still ships the Python adapter on the official `ibapi` client. That adapter
registers its execution client with `venue=None`, so the execution engine uses
it as the default route for `SPY.ARCA` and the #4983 venue mismatch does not
occur.

## Bounds (frozen in `plan.json` before any run)

- Endpoint: `127.0.0.1`, paper ports 4002 (Gateway) and 7497 (TWS) only. Exactly
  one managed account, and it must start with `DU`.
- Client ids: 91 for the node (its data and execution clients share one adapter
  client), 92 for the official-ibapi check. 71/73/76/81/82 belong to other probes.
- SPY `STK`, `SMART` routing, primary exchange `ARCA`, `USD`. Nautilus id `SPY.ARCA`.
- At most 6 orders (checked before every order is created), 1 share and at most
  USD 1000 notional per order, a round-trip loss limit of USD 5, DAY limit orders only.
- Regular trading hours only: the whole run, `[now, now + 420 s]`, must fall
  inside 09:30 to 15:50 America/New_York. SPY `liquidHours` from the pre-run
  check (kept whole, never written to the receipt) can close or shorten that
  window on holidays and early closes. Segments for other days that do not
  parse are skipped; if today's segment is missing or does not parse as
  `YYYYMMDD:HHMM`, the run is refused (`refused_liquid_hours_unavailable`)
  rather than run on the fixed window.
- Quotes: tick-by-tick BidAsk (real time, IB event time) no older than 10 s.
- Timeouts: node start 60 s, 45 s per step, 45 s for cleanup, 420 s overall.
- Order pacing: the harness waits at least 1.5 s between any two orders it
  creates (checked before the budget is reserved). The Nautilus risk-engine
  throttle stays at its default `100/00:00:01`, so it never binds; the plan's
  first revision had `1/00:00:01`, which would deny a C3 or C4 submitted within a
  second of the previous order (`risk/engine.pyx:145-151, 1082-1084`).
- Execution engine: `LiveExecEngineConfig(inflight_check_threshold_ms=5000,
  inflight_check_retries=100)`. With the defaults (5 s x 5 retries) the engine
  fabricates `OrderRejected("UNKNOWN")` or `OrderCanceled` for an order IB has not
  answered after about 30 s (`live/execution_engine.py:736-792`), inside one 45 s
  step. 5 s x 100 = 500 s lies beyond the 420 s run; the venue queries still run.

## Cases (in order; the first failure stops the run)

| Case | Order | Expected |
|---|---|---|
| C1 accept_resting | LIMIT BUY 1 at max(1.00, floor(0.5 x bid, cent)) | `OrderAccepted` (records only whether a venue order id was present) |
| C2 cancel_resting | cancel C1 | `OrderCanceled` |
| C3 fill_buy | LIMIT BUY 1 at ask + 0.05, capped by notional; refused if the cap is below the ask or the worst-case round trip exceeds USD 5 | full `OrderFilled`, position opened |
| C4 flatten | LIMIT SELL filled qty at bid - 0.05 | full `OrderFilled`, flat; realized PnL and commissions |

On any failure, exception, timeout, deadline or SIGINT/SIGTERM/SIGHUP, the strategy
cancels every open order from this run. A cancel is re-sent at most 3 times per
order, 5 s apart, when the order is still open after `OrderCancelRejected` or no
answer; an order stuck in `PENDING_CANCEL` is re-cancelled through
`cancel_all_orders`, because `Strategy.cancel_order` refuses pending-cancel
orders (`trading/strategy.pyx:1649-1653`). It then flattens any SPY quantity this
run bought, using the C4 order builder with a fresh quote and whatever remains
of the order budget. After a flatten order closes without filling (denied,
rejected or canceled) it waits 2 s before the next one. Then it stops the node.
Finishing, for whatever reason, and the strategy's `on_stop` both send a final
cancel for every order of this run that is still open, including a flatten
inside its fill window. `on_stop` runs before the kernel waits
`timeout_post_stop` (5 s) and disconnects the clients (`system/kernel.py:1087-1095`).

Terminal events are handled once per order. IB reports one cancel twice (error
202 and orderStatus `Cancelled`, `client/error.py:325-328`), and the second
report can reach the strategy (`execution/engine.pyx:1335-1344, 1589-1596`); it
is recorded under `duplicate_events` and otherwise ignored. A close the engine
produced itself (`reconciliation=True` on `OrderCanceled`/`OrderRejected`/
`OrderExpired`) never passes a case. While one exists, cleanup sends no further
flatten order, and the run ends as `cleanup_unconfirmed_order_state` for the
independent check to decide. The harness replaces the kernel's
stop-on-signal handler (SIGINT, SIGTERM and SIGHUP) so that the first signal
runs this cleanup; the next signal requests the node stop. A signal or the
hard stop that arrives before the strategy has started marks the run finished,
so the strategy submits nothing if it starts later. A stop that has not
finished 15 s (`node_stop_allowance_seconds`) after it was requested, or a
further signal once it was requested, is forced: the kernel's remaining tasks
are cancelled and the event loop is stopped, so `node.run()` returns. The hard
stop never cuts a graceful stop short; it only guarantees the forced stop by
hard stop + 15 s. Once the node phase has begun, the
official-ibapi check runs again (client 92) as independent proof that the
account is flat: zero non-zero positions and zero open orders. It runs on
every exit path, including an exception or interrupt from the node, and an
attempt that raises is recorded as `error` and retried. An interrupt during
the proof records `interrupted`; a proof that never ran records
`not_attempted`. If the proof does not pass, the status is `cleanup_required`
and the exit code is 3.

## Run

Create the environment with the same uv recipe as the other engine-nautilus probes:

```
uv venv --python /usr/bin/python3.12 "$ENV"
uv pip install --python "$ENV/bin/python" --index-url https://pypi.org/simple 'nautilus_trader[ib]==1.231.0'
```

With a signed-in paper IB Gateway (socket API enabled, "Read-Only API" off),
during regular trading hours:

```
"$ENV/bin/python" run.py check                  # read-only; prints counts, never the account id
"$ENV/bin/python" run.py run --receipt receipt-paper-orders.json
```

`run` refuses the gate's receipt path `../ibkr-acceptance/receipt.json`. Before
the node is built it writes a provisional `cleanup_required` receipt
(`evidence_class` `native_paper`, the run prefix, `provisional: true`) to the
receipt path. If that write fails the run is refused before the node connects
(`refused_receipt_unwritable`, printed, exit 3). Only the final receipt replaces
the provisional one (atomic replace), so SIGKILL, a hang-up or a failed final
write leaves a `cleanup_required` receipt that names the run prefix. It
refuses a port other than 4002/7497 and any start time outside the session
window, both before connecting. It also refuses if the in-process pre-run check
does not pass (non-paper account, more than one account, existing positions or
open orders). `--log-level` (default `WARNING`) controls Nautilus console
logging. Console output is **not** redacted: Nautilus logs the account id, so do
not save or commit it.

Exit codes: `0` passed; `1` failed or incomplete; `2` not connected; `3` refused
(`refused_*`) or `cleanup_required`.

## Receipt

The receipt contains: `schema_version`, `kind` (`ibkr_paper_orders_nautilus_1_231`),
the `nautilus_trader` and `ibapi` versions, `plan_sha256` and `harness_sha256`,
and the sanitized pre-run check. For each case it records the outcome and reason,
the Nautilus event types with their `ts_event`/`ts_init`, and the order price,
quantity and notional. It also records the fills (price, quantity, commission and
its currency), the position opened and closed, the round trip (gross, commissions,
net, the Nautilus realized PnL and whether the loss bound was breached), the
cleanup actions, the flat proof with every attempt, the status and the exit code.

It never records account ids, balances, credentials, host names or home paths.
Error text is redacted with `\b(?:D?[UF]|I)\d{5,}\b`, and IPv4 addresses and
absolute paths are removed. Account amounts in free text are also removed:
bracketed amounts (`[1234.56 USD]`, as in IB 201 margin rejections), amounts
next to a currency code, and numbers after labels such as equity, margin, funds,
cash, balance, buying power or net liquidation. The serialized receipt then gets a final pass that
removes the in-memory account id and any id-shaped text.

`passed` requires C1-C4 all passed, no loss-bound breach and a passed flat proof.

## Known limits

- IB precautionary settings (price-percentage and size limits) can reject C1's
  far-from-market limit order. That is a failed C1, recorded as observed, and is
  not retried with other prices.
- Tick-by-tick quotes need a real-time US equity market-data entitlement. A
  competing session for the same username (error 10197) or delayed-only data
  means no fresh quote, so C1 never submits and the run ends `incomplete`.
- The adapter emits `OrderFilled` only after IB's commission report arrives, but
  it maps an unset or `-1` commission to 0 (`execution.py:2112` in the installed
  1.231.0 package). A zero commission is flagged in the receipt as possibly unreported.
- IB returns the order reference as `clientOrderId:orderId`, and the adapter
  splits on the last `:`. The run's client order ids (`NTP-MMDD-HHMMSS-hex-C1`)
  contain no `:`.
- The flat proof counts open orders from every API client and the GUI
  (`reqAllOpenOrders`), which is deliberately conservative.
- An order that IB has not yet acknowledged (`SUBMITTED`, no venue order id)
  cannot be cancelled through the adapter (`execution.py:1540-1556`). If the run
  ends while one exists, only the independent check can show whether it rested.
- `cancel_all_orders` reaches the adapter's `_cancel_all_orders`, which cancels
  every open `SPY.ARCA` order in the node's cache, not only this strategy's
  (`execution.py:1580-1600`). The pre-run check requires zero open orders, and the
  harness sends it only for its own order stuck in `PENDING_CANCEL`.
- A case order denied by the risk engine is a failed case and is not retried
  under a new id. The 1.5 s spacing makes a throttle denial unreachable under the
  plan's rate.

## Tests

```
python3 -m unittest tests.test_ibkr_paper_orders
"$ENV/bin/python" -m unittest tests.test_ibkr_paper_orders
```

These are offline and synthetic. With plain python3 they cover plan validation,
prices, the order and quantity caps, the session window and close buffer, liquid
hours (a fake ibapi client with today's segment past character 200, broken
segments, a missing or broken today refused), refusal paths, the provisional
receipt and the unwritable receipt path, the flat proof after an interrupt,
`SystemExit` or other `BaseException` from the node and after a check that
raises, the stop controller (a signal before start marks the run finished; a
second signal and the stop allowance force a hung stop on a real asyncio
loop), check verdicts, redaction, the exit codes and AST checks.
The AST checks confirm that the only order-factory calls are the C1, C3 and
flatten builders, that `submit_order` has one call site after the budget
reservation, and that no market or close-position calls exist. Under the 1.231.0
environment, `NautilusBacktestFlow` also runs the strategy in a Nautilus
`BacktestEngine` against a simulated ARCA venue: the happy path (with the
plan's risk-engine rate and the 1.5 s spacing), an abort after the fill
(flattened exactly once), an unfilled C3 that times out and is canceled, a
duplicate C1 cancel report, an engine-generated cancel during C2, a cleanup
deadline with a resting flatten, a dropped finish-time cancel caught by
`on_stop`, a rejected cancel re-sent after the interval, and a denied flatten
retried after the delay. A control test drives two submits 0.5 s apart through
the 1.231.0 `RiskEngine`: `1/00:00:01` denies the second one and the plan's rate
does not. `RunNodeSignalWiring` runs `run_node` with a stand-in `TradingNode`
(no IB client is built) and sends the test process two real SIGHUPs: the first
marks the not-yet-started run finished and the second forces the hung stop. The injected rejections, denials and dropped cancels are synthetic.
That simulated venue is not IBKR evidence.

## Known residuals (pre-live review, 2026-09-23)

None of these lets an order or position go unreported, raises the order, quantity or notional bounds, or allows
trading outside regular hours:
- SIGABRT keeps NautilusTrader's own handler. That handler calls `node.stop()` directly, so no forced stop is armed
  until the hard stop.
- If the `TradingNode` constructor or `build()` raises, the kernel's asyncio signal handlers stay installed until the
  harness restores its own.
- After `TradingNode.dispose()` closes the loop, a SIGTERM or SIGHUP can end the process in a short window before the
  harness's handlers are restored. The provisional `cleanup_required` receipt covers that window.
- A refusal receipt that cannot be written prints `incomplete` rather than the refusal status. Nothing was placed at
  IB on those paths.
- SIGKILL cannot run cleanup or the flat proof. Only the provisional receipt, which names the run prefix, remains.

## Runs, 2026-09-23 (read-only frozen copy of `c23525e6`, hashes in `evidence/frozen-c23525e6.SHA256SUMS`)

`c23525e6` was the harness commit before the branch was rebased onto main. It became `5bf177c0` with byte-identical
`run.py` and `plan.json`. The receipts' `harness_sha256` and `plan_sha256` equal those files' hashes on this branch.

- 12:45 ET, `evidence/receipt-20260923-refused-read-only-api.json`: `incomplete` with `node_start_timeout`. The Gateway
  API was in Read-Only mode (IB 321), so the execution client could not reconcile and the node never started. No
  order was created, and the flat proof passed.
- 13:53 ET, after the user unticked Read-Only API, `evidence/receipt-20260923-passed.json`: **passed** (exit 0, 11.5 s)
  through NautilusTrader 1.231.0's own IB execution engine on the paper Gateway:

  | Case | Nautilus events | Result |
  |---|---|---|
  | C1 resting buy, SPY 1 at half the bid | Initialized, Submitted, Updated, Accepted | accepted |
  | C2 cancel | PendingCancel, Canceled | canceled |
  | C3 marketable buy | through Filled | filled 768.56, commission 1.00 USD |
  | C4 flatten | through Filled | filled 768.50, commission 1.02 USD |

  - Gross −0.06 USD and net −2.08 USD against the 5 USD round-trip bound; Nautilus realized PnL agrees.
  - 3 of 6 orders were used. No cleanup, unconfirmed or duplicate events.
  - The independent official-ibapi flat proof found 0 positions and 0 open orders.

These runs cover acceptance-plan section 5: step 1 (in the pre-check), and from step 3 submit/acknowledge, cancel,
fill and flat. They do not cover reconnect with an open order, restart reconciliation, or the step 4 kill-switch
exercise. 1.231.0 is not the pinned 2.0.0rc5 destination.
