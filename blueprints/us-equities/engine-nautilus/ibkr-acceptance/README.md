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
7497 (TWS), both refuse to write the gate's flip receipt `receipt.json`, and
neither records account ids or balances.

- `ibapi_probe.py` (official IB API client, `ibapi` 10.45.1): paper-account
  check (every managed account starts with `DU`, else disconnect before any
  other read), server time, positions and open-order counts, account-summary
  tag names, SPY contract identity, the market-data type actually granted with
  a snapshot quote and its last-trade time, and two days of 5-minute bars.
  `passed` needs every request to complete, zero existing positions and open
  orders, and a quote no older than `plan.json`'s 900 s limit (IB times have
  one-second resolution, so down to -2 s counts as current). Account ids are
  not hashed either: a paper id is `DU` plus a few digits, so its hash is
  reversible; id-shaped text in IB error messages is redacted.
- `nautilus_probe.py` (NautilusTrader 2.0.0rc5
  `HistoricalInteractiveBrokersClient`): SPY instrument resolution and
  historical bars through the native adapter. The rc5 Python surface has no
  managed-account query outside a full `TradingNode`, so it runs only on a
  passed `ibapi_probe.py` receipt for the same host and port written at most
  300 s earlier. The Rust-backed client needs an asyncio loop on the calling
  thread and cannot be moved to a worker thread.

`plan.json` is the step-1 plan written before the first run (file time
2026-09-22T22:01:09Z) and kept verbatim. It predeclares the paper ports, the
`DU` prefix, `DELAYED` data mode and a 900 s quote-age ceiling. It was not
independently reviewed before the run, and it names a hand-rolled protocol
probe that failed its handshake and was replaced by `ibapi_probe.py`; the
receipt lists every deviation. Every attempt is retained in
`evidence/attempts/` (redacted where a draft recorded an account-id hash).

## Usage

With a signed-in paper IB Gateway on this host, run the two probes back to back:

```
IBAPI_PY=~/.local/share/codex-ecosystem/tools/ibkr-lane-20260922/bin/python   # ibapi 10.45.1
NT_PY=~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python  # nautilus_trader 2.0.0rc5
"$IBAPI_PY" ibapi_probe.py --receipt ibapi.json
"$NT_PY" nautilus_probe.py --ibapi-receipt ibapi.json --receipt nautilus.json
```

Exit codes: `0` passed; `1` incomplete, failed or instrument only; `2` not
connected; `3` refused (non-paper port, non-paper account, gate receipt path,
or no fresh passed paper receipt); `4` blocked by existing positions or open
orders (ibapi probe).

## Blockers for the gate

- Native stock orders (steps 2-4): [nautilus_trader#4983](https://github.com/nautechsystems/nautilus_trader/issues/4983),
  the execution client's `IB` venue never matches the `SMART` instrument venue,
  so every stock order is denied locally.
- Native bars on notice 2188: rc5 pins the Rust `ibapi` crate at `=3.3.0`,
  which classifies IB notice 2188 ("Up-to-the-second historical data requires
  additional subscription for the API") as a hard error and drops the bars TWS
  then sends ([rust-ibapi#764](https://github.com/wboayue/rust-ibapi/issues/764),
  fixed by [#765](https://github.com/wboayue/rust-ibapi/pull/765) in v4.0.0).
  The mechanism is source-verified. One native failure was observed, at
  13:18-13:19Z from an ad hoc script (retained in `evidence/attempts/`); its
  data mode is inferred as DELAYED from the ibapi run two minutes earlier,
  and the comparison with the later REALTIME runs (no 2188 on the ibapi
  connection, native bars returned) is confounded by the different script and
  pre-market timing. Open NautilusTrader PR
  [#5041](https://github.com/nautechsystems/nautilus_trader/pull/5041) moves
  the pin to `=4.1.0`.
- Market data: IBKR serves market data to one session per username. While the
  same username is signed in elsewhere (Client Portal, mobile, another TWS), the
  paper session gets `10197 No market data during competing live session` and
  historical requests get error 162 (observed at 13:23:58Z).

## Tests

```
python3 -m unittest tests.test_ibkr_acceptance
```

Offline and synthetic: no gateway, `ibapi` or NautilusTrader needed. A fake
client drives the ibapi probe's refusal, not-connected, existing-state and
incomplete-snapshot paths.
