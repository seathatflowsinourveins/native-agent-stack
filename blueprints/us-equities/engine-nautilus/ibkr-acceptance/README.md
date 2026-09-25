# IBKR read-only acceptance (step 1)

Step 1 of `blueprints/us-equities/engine-nautilus/acceptance-plan.md` section 5
("begin with read-only socket access and execution disabled") for the
`ibkr-local-acceptance` gate in `catalogs/us-equities/gates-20260922.json`.
This is partial evidence: step 1 passed on both clients on 2026-09-23
(`evidence/`, receipt `evidence/receipts/ibkr-readonly-acceptance-20260923.json`),
but the gate stays `not_established` because steps 2-4 need NautilusTrader
native paper stock orders, which are blocked upstream (see "Blockers").
Since 2026-09-25 a dated keep-but-compare record
(`docs/decisions/2026-09-25-ibkr-local-acceptance-version-selection.md`) selects
NautilusTrader 1.231.0's Python adapter for local acceptance. The remaining
steps run through `local_acceptance.py` (see "Steps 2-4: local acceptance runner").

## Probes

Both probes are read-only. Neither calls an order method (a source test checks
this), both refuse a port other than the paper defaults 4002 (IB Gateway) and
7497 (TWS), both refuse to write the gate's flip receipt `receipt.json`, and
neither records account ids or balances; account ids, IPv4 endpoints and
absolute paths in IB message text are redacted.

- `ibapi_probe.py` (official IB API client, `ibapi` 10.45.1): paper-account
  check (every managed account starts with `DU`, else disconnect before any
  other read; the refusal is latched and checked before every request, so a
  later non-paper account callback also stops the run), server time, positions and open-order counts, account-summary
  tag names, SPY contract identity, the market-data type actually granted with
  a snapshot quote and its last-trade time, and two days of 5-minute bars.
  `passed` needs every request to complete, zero existing positions and open
  orders, and a quote no older than `plan.json`'s 900 s limit (IB times have
  one-second resolution, so down to -2 s counts as current). Account ids are
  not hashed either: a paper id is `DU` plus a few digits, so its hash is
  reversible.
- `nautilus_probe.py` (NautilusTrader 2.0.0rc5
  `HistoricalInteractiveBrokersClient`): SPY instrument resolution and
  historical bars through the native adapter. The rc5 Python surface has no
  managed-account query outside a full `TradingNode`, so it runs only on a
  passed `ibapi_probe.py` receipt for the same host and port written at most
  300 s earlier. The Rust-backed client needs an asyncio loop on the calling
  thread and cannot be moved to a worker thread. It is dropped inside that
  loop: left to interpreter shutdown, it aborted the process (a tokio worker's
  non-unwinding panic, exit 134) in 2 of 6 observed runs, after the receipt was
  written; with the drop, 0 of 8 study runs aborted
  (`evidence/attempts/20260923T1500Z-nautilus-teardown-abort-study.json`).

`plan.json` is the step-1 plan written before the first run (file time
2026-09-22T22:01:09Z) and kept verbatim. It predeclares the paper ports, the
`DU` prefix, `DELAYED` data mode and a 900 s quote-age ceiling. It was not
independently reviewed before the run, and it names a hand-rolled protocol
probe that failed its handshake and was replaced by `ibapi_probe.py`; the
receipt lists every deviation. Every attempt is retained in
`evidence/attempts/` (redacted where a draft recorded an account-id hash).

## Usage

Two isolated environments, created with the same uv recipe as
`engine-nautilus/README.md` (the `trading-nautilus` adoption profile):

```
uv venv --python /usr/bin/python3.12 "$IBAPI_ENV"
uv pip install --python "$IBAPI_ENV/bin/python" --index-url https://pypi.org/simple nautilus-ibapi==10.45.1
uv venv --python /usr/bin/python3.12 "$NAUTILUS_ENV"
uv pip install --python "$NAUTILUS_ENV/bin/python" --index-url https://pypi.org/simple --pre nautilus_trader==2.0.0rc5
```

`nautilus-ibapi` is the PyPI distribution of IB's official TWS API Python
client used by NautilusTrader (import name `ibapi`; its project URLs point to
IB's tws-api; version 10.45.1 in the published run). With a signed-in
paper IB Gateway on this host, run the two probes back to back:

```
"$IBAPI_ENV/bin/python" ibapi_probe.py --receipt ibapi.json
"$NAUTILUS_ENV/bin/python" nautilus_probe.py --ibapi-receipt ibapi.json --receipt nautilus.json
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

Update, 2026-09-25 (source check, not observed). #4983 was filed against
v1.227.0. The pinned rc5 source already routes around the venue check the
issue describes: the IB execution client's `handles_order_venue` returns
`true`, added by #4129 on 2026-05-25. So the first blocker is unconfirmed for
rc5 until an rc5 stock order is tried. PR #5041 now pins `=4.2.0`, not
`=4.1.0`. It remains open and unreleased, and lists six open IB restart and
reconnect issues as covered. Details and the comparison that would overturn the
1.231.0 selection are in
`docs/decisions/2026-09-25-ibkr-local-acceptance-version-selection.md`.

## Tests

```
python3 -m unittest tests.test_ibkr_acceptance
```

Offline and synthetic: no gateway, `ibapi` or NautilusTrader needed. A fake
client drives the ibapi probe's refusal, not-connected, existing-state and
incomplete-snapshot paths.

## Steps 2-4: local acceptance runner

`local_acceptance.py` runs the cases of acceptance-plan section 5 that the
2026-09-23 paper-order receipt (`../ibkr-paper-orders/`) left open. It uses
NautilusTrader 1.231.0's own IB execution engine, selected as keep-but-compare
in `docs/decisions/2026-09-25-ibkr-local-acceptance-version-selection.md`.
The frozen plan is `local-acceptance-plan.json` (regular session). Its
after-hours twin, `local-acceptance-plan-post.json`, changes only the session:
16:00-20:00 with `outsideRth`.

The run has three phases. Each phase is a fresh `TradingNode` process on client
id 93. The runner's independent official-ibapi observer runs on client 98.

| Case | Phase | What must happen |
|---|---|---|
| A1 accept_resting | A | R1, a resting BUY 1 SPY at half the bid, is accepted by IB |
| A2 client_id_ownership | A | A contender connection on client id 93 is refused with IB 326. The observer lists R1 with clientId 93, an orderRef ending `:<orderId>`, and the permId behind the node's `PERM-` venue id |
| A3 reconnect_open_order | A | The adapter's socket is shut down while R1 works. The adapter reconnects on id 93, R1 stays open with the same permId, and the node's cancel ends in an IB-confirmed `OrderCanceled` |
| A4 restart_setup | A | R2, the same resting buy, is accepted. Phase A stops with R2 working |
| B1 restart_reconciliation | B | After a fresh-process restart, reconciliation adopts R2 for the strategy (`external_order_claims`) with the same ids, side, quantity, price and time in force. Nothing is resubmitted |
| B2 kill_switch | B | The latch is written, the risk engine is set `HALTED` and an alert is raised. P1 is denied locally (`TradingState.HALTED`) and R2 is cancelled at IB |
| C1 kill_switch_persists | C | After another restart, the latch keeps the risk engine `HALTED` before the node runs, no order of the run is open, and P2 is denied locally |

Checkpoints with the observer:

- **Before the run:** a paper account (every managed account `DU`, exactly one),
  zero positions, zero open orders, today's contract hours, and client id 93 free.
- **After A:** only R2 works.
- **After B:** nothing is open, and IB's completed orders show R1 and R2
  cancelled. That shows the list covers this run, so P1 missing from it means
  P1 never reached IB.
- **Final:** flat, no execution of the run, R1 and R2 listed cancelled, and
  neither probe order at IB.

It refuses by default:

- `run` connects nothing without `--enable-paper-orders`.
- Live ports 4001 and 7496 are refused as `refused_live_port`, and any other
  port except 4002 and 7497 as `refused_not_paper_port`, both before connecting.
- A non-`DU` or multi-account Gateway, existing positions or orders, a busy
  client id, an engaged kill-switch latch, a second concurrent run, missing
  prerequisite receipts, an unpinned runtime (anything but 1.231.0 on
  ibapi 10.45.1) and a start outside the session window are all refused.

Every order is a non-marketable resting limit, with at most four orders per run
and two of them reaching IB. The runner has no marketable or flattening order.
A fill would end the run `cleanup_required`, with the position left for a
manual flatten.

On any failure the phase cancels its own orders. After the phase process has
exited, the runner cancels leftovers of this run through ibapi:

- The observer (client 98) lists which client ids hold orders whose `orderRef`
  carries the run prefix.
- Each holder inside the adapter's fallback band (93-97) cancels its own orders.
- Only a complete listing without an order of the run counts as clean.

The gate receipt `receipt.json` (preregistered schema
`{"schema_version": 1, "kind": "native_ibkr_local_acceptance", "status": "passed", "broker": "ibkr"}`)
is written only when:

- every case and checkpoint passed, and
- both prerequisite receipts (`evidence/ibapi-readonly-20260923.json` and
  `../ibkr-paper-orders/evidence/receipt-20260923-passed.json`) exist with status
  `passed`.

That receipt makes the gate a flip candidate only. The flip itself stays a
manual, dated commit after qualification.

### What you do first (once per session)

1. Start IB Gateway in paper mode. Either run `~/ibc/start-paper-gateway.sh`
   (IBC 3.24.2 `gatewaystart.sh -inline`, `TradingMode=paper`, port 4002), or
   start IB Gateway 10.50 from `~/Jts/ibgateway/1050` and choose **IB API** and
   **Paper Trading**.
2. Sign in with the **paper** username and approve the second factor (IBKR
   Mobile). Confirm the window shows the paper/simulated-trading banner.
3. In Gateway **Configure > Settings > API > Settings**:
   - **Read-Only API: off.** IBC applies a non-empty `ReadOnlyApi` from
     `~/ibc/config.ini` at every start. The 2026-09-22 setup record (agent-lab
     grand-catalog handbook) lists `ReadOnlyApi=yes`, and the 2026-09-23 12:45 ET
     paper-order run was refused with IB 321 (Read-Only). Set it to `no`, or leave
     it empty and untick the box, so a restart does not re-tick it.
   - **Socket port: 4002** (IBC `OverrideTwsApiPort=4002`).
   - **Trusted IPs: 127.0.0.1.** Keep "Allow connections from localhost only"
     on; the Gateway always admits 127.0.0.1.
   - **Master API client ID: empty** (IBC `OverrideTwsMasterClientID=` empty), or
     any id outside 93-98. The node must see only its own orders.
4. Sign out of every other session of the same username (Client Portal, mobile
   trading, another TWS). A competing session gets IB 10197, which means no
   quotes, so A1 never submits and the run ends `incomplete`.

### Then run (regular session, 09:30 to about 15:30 New York time)

```sh
ENV="$HOME/.local/share/codex-ecosystem/tools/nautilus-1.231.0-ib"
RUNNER=blueprints/us-equities/engine-nautilus/ibkr-acceptance/local_acceptance.py
"$ENV/bin/python" "$RUNNER" preflight --port 4002
"$ENV/bin/python" "$RUNNER" run --port 4002 --enable-paper-orders \
  --receipt blueprints/us-equities/engine-nautilus/ibkr-acceptance/evidence/local-acceptance-$(date -u +%Y%m%dT%H%MZ).json
```

Run these from the repository root. `preflight` is read-only and prints
`"status": "ready"` when `run` would start. A typical run takes a few minutes,
but the whole worst case (1,500 s, `worst_case_seconds` in the runner) must fit
the session window, so a regular-session run starts by about 15:25 ET. After
16:00 add `--plan local-acceptance-plan-post.json` to both commands; the latest
start is then about 19:25 ET.

Keep `--receipt` inside the repository, as above. A steps receipt elsewhere
still records the run, but no gate receipt is written for it, because nobody
qualifying the flip could check it.

`--state-dir` (default `~/.local/state/native-agent-stack/ibkr-local-acceptance`,
created 0700) holds the run lock, the phase files and the kill-switch latch.

Exit codes:

- `0` passed
- `1` failed or incomplete
- `2` not connected
- `3` refused or `cleanup_required`

Nautilus console output is **not** redacted and contains the account id, so do
not save or commit it. The receipts never record account ids, balances, host
names or home paths.

### After the run

The latch stays engaged by design, because a restart must not clear it. Any
later `run` refuses until you clear it explicitly. The clear writes an audit line
first:

```sh
"$ENV/bin/python" "$RUNNER" kill-switch status
"$ENV/bin/python" "$RUNNER" kill-switch clear --confirm --reason "reviewed run <run_prefix>"
```

Then commit the steps receipt and, on a pass, `receipt.json`, for independent
qualification.

### Tests

```
python3 -m unittest tests.test_ibkr_local_acceptance
"$ENV/bin/python" -m unittest tests.test_ibkr_local_acceptance
```

The tests are offline and synthetic.

- With plain `python3` they cover plan validation, the refusals, the latch,
  the verdicts, the phase handshake, receipts and the gate receipt, and source
  checks.
- Under the 1.231.0 environment, the strategy also runs in a `BacktestEngine`
  against a simulated ARCA venue. That covers the phase A order flow with R2
  left working, and the real 1.231.0 risk engine denying P1/P2 with
  `TradingState.HALTED` while a cancel still passes.

None of this is IBKR evidence.
