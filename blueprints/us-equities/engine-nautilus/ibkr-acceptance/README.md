# IBKR read-only acceptance (step 1)

Step 1 of `blueprints/us-equities/engine-nautilus/acceptance-plan.md` section 5
("begin with read-only socket access and execution disabled") for the
`ibkr-local-acceptance` gate in `catalogs/us-equities/gates-20260922.json`.
This is partial evidence: step 1 passed on both clients on 2026-09-23
(`evidence/`, receipt `evidence/receipts/ibkr-readonly-acceptance-20260923.json`),
but the gate stays `not_established` because steps 2-4 need NautilusTrader
native paper stock orders, which are blocked upstream (see "Blockers").

## Probes

Both probes are read-only. Neither calls an order method (a source test checks
this), both refuse a port other than the paper defaults 4002 (IB Gateway) and
7497 (TWS), and neither records account ids or balances.

- `ibapi_probe.py` (official IB API client, `ibapi` 10.45.1): paper-account
  check (every managed account starts with `DU`, else disconnect), server time,
  positions and open-order counts, account-summary tag names, SPY contract
  identity, the market-data type actually granted with a snapshot quote, and
  two days of 5-minute bars. Account ids are not hashed either: a paper id is
  `DU` plus a few digits, so its hash is reversible.
- `nautilus_probe.py` (NautilusTrader 2.0.0rc5
  `HistoricalInteractiveBrokersClient`): SPY instrument resolution and
  historical bars through the native adapter. The rc5 Python surface has no
  managed-account query outside a full `TradingNode`, so it runs only after a
  passed `ibapi_probe.py` receipt for the same host and port. The Rust-backed
  client needs an asyncio loop on the calling thread and cannot be moved to a
  worker thread.

`plan.json` is the step-1 plan written before the first run (file time
2026-09-22T22:01:09Z) and kept verbatim. It predeclares the paper ports, the
`DU` prefix, `DELAYED` data mode and a 900 s quote-age ceiling. It was not
independently reviewed before the run, and it names a hand-rolled protocol
probe that failed its handshake and was replaced by `ibapi_probe.py`; the
receipt lists these deviations.

## Usage

With a signed-in paper IB Gateway on this host:

```
IBAPI_PY=~/.local/share/codex-ecosystem/tools/ibkr-lane-20260922/bin/python   # ibapi 10.45.1
NT_PY=~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python  # nautilus_trader 2.0.0rc5
"$IBAPI_PY" ibapi_probe.py --receipt ibapi.json
"$NT_PY" nautilus_probe.py --ibapi-receipt ibapi.json --receipt nautilus.json
```

Exit codes: `0` passed, `1` incomplete or failed, `2` not connected, `3`
refused (non-paper port, non-paper account, or no passed paper receipt).

## Blockers for the gate

- Native bars when data is delayed: rc5 pins the Rust `ibapi` crate at
  `=3.3.0`, which treats IB notice 2188 ("Up-to-the-second historical data
  requires additional subscription for the API") as a hard error and drops the
  bars TWS then sends ([rust-ibapi#764](https://github.com/wboayue/rust-ibapi/issues/764),
  fixed by [#765](https://github.com/wboayue/rust-ibapi/pull/765) in v4.0.0).
  Observed on 2026-09-23: with DELAYED data (13:16Z) the native bar requests
  failed while the official client got bars with the same notice; with
  REALTIME data granted (14:13Z) no 2188 was sent and the native bars
  returned. Open NautilusTrader PR
  [#5041](https://github.com/nautechsystems/nautilus_trader/pull/5041) moves
  the pin to `=4.1.0`.
- Native stock orders (step 3): [nautilus_trader#4983](https://github.com/nautechsystems/nautilus_trader/issues/4983),
  the execution client's `IB` venue never matches the `SMART` instrument venue,
  so every stock order is denied locally.
- Market data: IBKR serves market data to one session per username. While the
  same username is signed in elsewhere (Client Portal, mobile, another TWS), the
  paper session gets `10197 No market data during competing live session` and
  historical requests get error 162.

## Tests

```
python3 -m unittest tests.test_ibkr_acceptance
```

Offline and synthetic: no gateway, `ibapi` or NautilusTrader needed.
