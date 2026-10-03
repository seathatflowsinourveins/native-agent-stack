# IBKR rc5 offline state freeze — 2026-10-03

This is the synthetic Section 4 integration fixture, frozen before execution.
It supplies no native account, qualified contract, entitlement, execution plan,
broker pacing claim or broker qualification. Transport and clock are injected;
no broker library, authentication state or network is used by the suite.

Binding: broker `IBKR`; literal endpoint `127.0.0.1:4002`; synthetic paper account
fingerprint `ba8321e3eb5d7d550215e79e1070cd7b2e2324e6684e4704cfe5b808b12be468`
(SHA256 of `OFFLINE-SYNTHETIC-PAPER-ACCOUNT-TASK1`); synthetic client owner `176`;
schema `1`. The plan digest is SHA256 of this entire file. All limit fields are
also immutable journal bindings. The fixture symbol is `SYNTH.TEST`, not a
qualified IBKR instrument. Initial cash is `10000.00` USD, initial position zero.

Use whole shares, price tick `0.01`, USD cents, `Decimal` and `ROUND_HALF_EVEN`.
Round each execution's quantity × price and each final commission posting to
cents. Keep the original decimal commission payload for replay comparison.
Negative final commissions are rebates; raw IB pending sentinel `-1` is pending,
never final zero or a rebate. Commission identity is execution ID, currency must
be explicitly `USD`, and posting must be explicitly `final`; all executions
require final commission observations before snapshots can reconcile. Zero is
accepted only when explicitly observed as final. No FX or balancing entries.

Maximum order: 10 shares and `2000.00`; aggregate gross exposure `2000.00`;
gross realized loss and drawdown caps `100.00`. Equality with a maximum is
allowed; a breach is greater than the maximum. Long-only cash orders: no short
position, margin or sell larger than unreserved holdings. Reserve worst-case
buy cash at the limit, reduce reservations as fills arrive, and release unfilled
reservation only on definitive rejection or confirmed cancellation. Gross
exposure includes marked holdings and pending buy reservation.

Quote age is integer nanoseconds in `[0, 3_000_000_000]` (test max−1, max,
max+1); future, missing/nonfinite, nonpositive and off-tick prices are refused.
Injected session is `[1_000_000_000_000, 2_000_000_000_000)`; injected baseline
time is `1_500_000_000_000`. No native calendar/feed assumption is implied.

Fake request window is `60_000_000_000` ns, maximum 8 calls with 3 reserved for
cancel/reconciliation: submits consume at most the first 5 calls; control calls
can consume the remaining 3. Requests and window persist across restart. On
exhaustion record next eligible time with exponential backoff starting at
`1_000_000_000` ns, capped at `8_000_000_000` ns and never earlier than the next
window. There is no sleep loop or automatic submit retry. Each durable attempt
has one immutable identity/payload, stable client reference, risk reservation
and exactly one committed pre-send marker; even crash-before-send never causes
blind resend. Lookup is explicit and uses the saved reference.

Acquire a per-account `flock` before journal mutation, including across separate
database paths. Use SQLite WAL, synchronous FULL, explicit transactions and
fsync of newly created database parent metadata. Reopening checks the complete
binding read-only before mutable connection/PRAGMAs. Changed broker, endpoint,
account, client, plan, source, version, limits or schema is refused unchanged.

Kill policy is persistent `cancel-owned`: independent STOP or numeric breach
latches halt before further submissions; cancellation is attempted only for
owned nonterminal orders with observed identity. Cancel requests are pending,
never terminal. Failed or unknown cancellation remains blocked across restart.
Outstanding positions remain represented; cancellation cannot manufacture
flatness. Halt has no clearing API. Disconnect requires complete order,
execution, commission, position and USD cash snapshots; all unknown identities,
missing fees/currency, contradictory payloads or economics remain blocked and
produce a retained alert. A complete agreeing snapshot can clear recoverable
stream blocking, never permanent STOP/risk halt or unknown attempted orders.

Source: `nautechsystems/nautilus_trader` Python `2.0.0rc5`, revision
`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`, execution `parse.rs` 55–73,
85–147 and `core_updates.rs` 240–280. Installed `model/__init__.pyi` has SHA256
`fb2491805ad2331d2c08d0d2f04ed79107195655dc0fce9b8c68cff64b5f92c0`;
adapter stub SHA256
`edf80aacbf93888ad7f9b518f660e0b1f874263e16d5dcbe9c582d601cfec7f6`.
Public reports expose client_order_id, venue_order_id and trade_id; raw
orderId/permId/orderRef are stored only when supplied by an actual observation.
`PERM-n` reports supply only permId; decimal venue IDs supply only orderId.
Order status supplies lifecycle and cumulative progress, never economic fills.

Durability primitives selectively follow `adaptive-paper/safety.py` at
`2673696c94037b0d9454b9fa108ac7eb32618858`: account lock 387–411, WAL/FULL and
parent fsync 427–499, reservation 817–894, request reserve 1354–1385 and halt
1402–1408. No Alpaca statuses, average-price accounting or adoption semantics
are carried into IBKR. These are locally authored integration tests, not
unchanged upstream tests. rc5 recovery holds 5057/5060 and the prefixed-account
fill query remain; source/offline evidence cannot clear them.
