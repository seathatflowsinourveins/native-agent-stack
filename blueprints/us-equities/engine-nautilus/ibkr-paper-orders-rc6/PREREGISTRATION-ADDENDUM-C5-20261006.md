# C5: the engine refuses a SMART-routed paper order above its per-order cap (rc6)

Preregistered 2026-10-06, before any NautilusTrader rc6 run. The command center approved this file as a dated addendum
to #754's frozen criteria (item task-native-agent-stack-5f-20261006T155009Z, N4). It adds one stricter check. It changes
none of C1-C4, their bounds or their configuration. The machine-readable terms are in `c5-addendum.json` beside this file.

## Why

Under rc5, the native risk engine's per-order notional cap is configured but not enforced on the SMART/IB route
([#4946](https://github.com/nautechsystems/nautilus_trader/issues/4946)). #754 records this as "engine notional cap
configured, not enforced on this route". The bound was held by quantity 1 and quote admission instead.

The fix (ed6fc8bf) is in v2.0.0rc6 (commit 7b766f88), per #761's cited compare views. In rc6's
`crates/risk/src/engine/mod.rs`:
- `order_account_id` (:1245-1276) gives an order without an assigned account the account of the routed client;
- `check_orders_risk` (:1212-1243) then applies the per-account checks;
- an order whose notional exceeds `max_notional_per_order` is denied with `NotionalExceedsMaxPerOrder` (:2358-2371).

The file's sha256 at that commit is ad16f4bf....

## The check

1. **One C5 node run**, separate from the C1-C4 run and before it, on NativeStack2604:
   - IBKR paper Gateway 127.0.0.1:4002, clients 91 and 92, instrument SPY=STK.SMART;
   - native risk engine enabled.
   - The only parameter that differs from #754's plan: `max_notional_per_order` for SPY=STK.SMART is 100 USD.
2. **The order:** one LIMIT BUY, quantity 1, priced by C1's own rule (about half the bid, so non-marketable), GTD 7 minutes.
   - The runner checks that its notional exceeds 100 USD before the order reaches the engine.
   - If it does not, C5 is refused (exit 3) and never counted as passed.
3. **PASS** needs all four:
   - the engine emits `OrderDenied` for that client order id with reason `NotionalExceedsMaxPerOrder`;
   - no `OrderSubmitted`, `OrderAccepted`, venue rejection or venue order id exists for it;
   - the check client sees no open order and no execution for it;
   - the end disposition is flat, with no open orders.
4. **FAIL:** anything else.
   - If the order reached the venue, cancel it at once through the check client. The 7-minute GTD expiry is the backstop.
   - The rc6 pointer then does not move, and the IBKR paper lane stays on rc5.

## Sequence and slot

- C5 runs first, in the command center's confirmed slot: 10-07 13:45-20:00Z, IBKR paper only, client 92.
- C1-C4 run on rc6 only after C5 passes.
- No rc6 change on 2604 before the 10-07 A2 install and enable are done.
- The pointer moves to rc6 only after C1-C5 pass. Rollback is the pointer back to rc5, which stays installed.

## Limits

- C5 proves the cap on this route for one paper LIMIT BUY opening order only.
- Market orders are exercised by C3 under the base cap of 1000 USD.
- Full position exits are exempt from the per-order cap by design (:2359), so C4 is unaffected.
