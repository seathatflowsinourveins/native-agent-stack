# Regular-hours mover paper series `rth-20260929`, 2026-09-29 RTH: 5 of 6 trials passed, trial 6 failed on a ledger halt, flat

This is the sanitized receipt of a regular-hours mover paper series on account 1 (credential inventory id
`alpaca-paper`). It ran in the RTH session of 2026-09-29, from 10:00:05 to 15:44:16 ET, started by a timer.
`receipt.json` holds the figures. This directory also holds the broker reconciliation's stdout, sanitized copies of
the six engine receipts, the series console and the frozen SHA256SUMS ([Files](#files)). The freeze note, the engine
ledger, the scan caches and the rest of the trial workspace stay private.

The engine reported all six trials `passed`, but trial 6 ended with the ledger halted at `gross_loss_cap_reached`
(lifetime gross loss 250.18 of the 250 USD budget). The frozen acceptance requires no halt, so trial 6 fails it and
the series passed 5 of 6. It is metadata plus broker-reconciled evidence, not a frozen gate run, and it qualifies no
gate. The run was a mechanics-only test with no validated edge: the protocol's development study passed 0 of 768
rule-exits ([`mover-early-entry`](../../../mover-early-entry/README.md)). No credential, account id, account number,
account fingerprint, broker order id or ref, activity id, execution id or host path is recorded.

## Setup

**Code.** Main `b528bb55`, run from a durable read-only clone of that SHA under `<private state root>/engines/`.
- At the series start the driver ran `sha256sum -c frozen-b528bb55.SHA256SUMS` against the clone and logged that
  the engine files match.
- The SUMS, committed here, hold 70 entries: the top-level non-README files of `adaptive-paper/` (40),
  `mover-early-entry/` (20), `order-contract/` (5) and `incentive-monitor/` (5). That is 70 of the 208 files these
  four directories hold at `b528bb55`. All 70 equal `git show b528bb55`. They include the 26 `adaptive-paper/*.py`
  sources and `mover-early-entry/mover_scan.py`, whose hashes are in `receipt.json` (`code.engine_sources_sha256`).
- On 2026-09-30 the clone was still at `b528bb55`, `git status --porcelain` was empty and `sha256sum -c` passed
  again. The other 138 files were not hashed at run time.
- The offline gate passed 402 tests with exit 0 (2026-09-29, 05:05:52Z-05:08:34Z), as the freeze notes record. On
  2026-09-30 this receipt re-checked the private gate log (sha256 `1efd458e…`): it reads `Ran 402 tests in
  160.774s` and `OK`, with no FAIL or ERROR line, and the gate's rc record (sha256 `1e5ee31a…`) reads rc 0 for the
  same window. The gate copy's SUMS before and after the run equal the committed SUMS. Both files sit in a temporary
  directory and are cited by hash only.

**Runtime.** NautilusTrader LiveNode 2.0.0rc5, alpaca-py 0.44.0, numpy 2.5.3 and requests 2.34.2 on CPython 3.12.3,
from the pinned adaptive-paper virtual environment. The engine name comes from the trial receipts. The package
versions were read from the same environment on 2026-09-30 and match the freeze's record; they were not observed at
run time.

**Credential route.** The 0600 env file store through the `$PAPER_ENV_FILE` pointer
([docs/secret-storage.md](../../../../../docs/secret-storage.md)). The unit launched through `/bin/bash -ic`, whose
interactive start-up exports the pointer. `run-series-trial.sh` passed it as `--env-file` to the scan, `paper` and
`recover`, and the driver's key probe used the same pointer.

**Config.** Frozen before any broker I/O, sha256 `cbb953d517f18de…`:
- protocol `mover-early-entry-v1-20260924`, section `paper_e2e`;
- rule `10:00|G20|V250000|any` (gain in percent points; `rule.txt` holds the scanner's ratio form `G0.20`), exit X2
  (a 3,600 s hold), scope `any_session`, trial end 15:50 ET;
- SIP feed, extended hours enabled in the config (every order here went out as a regular-session order), no
  overnight holds, benchmark SPY only;
- capital 2,500 USD of ledger equity, at most 5 symbols;
- entry cap 1,000 USD per symbol; ledger caps of 10,000 USD per order, 100 shares and 10,000 USD gross;
- lifetime gross loss 250 USD and drawdown 250 USD for this ledger;
- rung 4 under `leverage-schedule-v1-20260922`, maximum leverage 4 and appreciation allowance 2, so the first
  trial's gross budget was 5,000.00 USD;
- at most 150 requests and 130 submits per minute, and at most 20 outstanding orders;
- quotes at most 3 s old, spreads at most 100 bps, limit caps of 50 bps;
- an entry window of 30 s, `stream_quote_timeout_seconds` 3, and a hard flatten at min(start + 68 min, 15:50 ET).

**Procedure.** Each trial ran four steps: `mover_scan.py`, then `mover_runner.py check`, then a synthetic run (SYN)
on the same scan, then `paper`. `recover` was to run on `needs_attention`, but no trial needed it.
- The timer started `paper-rth-20260929.service` at 10:00:05 ET. The unit ran `series-driver.sh rth-20260929 1 1
  1540 6` under `/bin/bash -ic`, with `ENGINE_SHA` set and the default state root, where the first `paper` stage
  created a fresh account-1 ledger at schema 2.
- The driver checks the kill switch, the clone and the SUMS, and probes the key once (`GET /v2/account`: HTTP 200,
  199 of 200 requests remaining). It then runs trials through `retry-benchmark.sh` until the last start, a trial
  that neither passed nor recovered, or any HTTP 429.
- Six trials ran back to back. The series ended at 15:44:16 ET on the 15:40 ET last-start rule: `series ends: past
  last start 1540 ET`.
- A dry run at 01:14:31 ET (05:14:31Z), after the freeze and before any timer, passed the driver's check mode (key
  probe 200), `check` (valid) and `synthetic` (`completed_no_signals`, flat). It had no `paper` stage.

## Attempts

| # | ET | Result | Orders | Fills (engine = ledger = broker) | Realized P&L | Flat at end |
|---|---|---|---|---|---|---|
| 1 | 10:00:05-11:00:30 | **passed** | 10 | 26 | -54.00 USD | yes |
| 2 | 11:00:30-12:00:53 | **passed** | 10 | 26 | -21.96 USD | yes |
| 3 | 12:00:53-13:01:15 | **passed** | 6 | 14 | +16.71 USD | yes |
| 4 | 13:01:15-14:01:50 | **passed** | 8 | 21 | -5.46 USD | yes |
| 5 | 14:01:50-15:02:19 | **passed**; 2 average-invariant records | 6 | 16 | -5.53 USD | yes |
| 6 | 15:02:19-15:44:16 | engine `passed`; **fail**: ledger halt `gross_loss_cap_reached` | 6 | 10 | -45.70 USD | yes |

Flat at end means that each trial's end reconciliation showed `cash_match` and `positions_match` true, 0 open orders
and 0 positions.

**Trial 1.** The scan fired 13 symbols. The top 5 were BKYI, IOVA, BEX, YMT and AXTX, and all five entered. The
engine's leverage multiple was 4, the gross budget 5,000.00 USD and the sizing equity 2,500.00 USD.

| Symbol | Entry | Exit (`x2_time`) | Realized |
|---|---|---|---|
| BKYI | 100 @ 3.7798, limit 3.78, 5 fills | 100 @ 3.40, limit 3.39, 2 fills | -37.98 |
| IOVA | 71 @ 13.89, limit 13.94, 2 fills | 71 @ 13.85, limit 13.78, 1 fill | -2.84 |
| BEX | 24 @ 40.26, limit 40.46, 1 fill | 24 @ 41.59, limit 41.38, 1 fill | +31.92 |
| YMT | 100 @ 2.169, limit 2.18, 5 fills | 100 @ 1.98, limit 1.98, 2 fills | -18.90 |
| AXTX | 26 @ 38.26, limit 38.33, 2 fills | 26 @ 37.252308, limit 37.09, 5 fills | -26.20 |

**Trial 2.** The scan fired 10 symbols: BKYI, IOVA, BEX, AXTX and SSTI entered. Leverage multiple 2, gross budget
4,892.00 USD.

| Symbol | Entry | Exit (`x2_time`) | Realized |
|---|---|---|---|
| BKYI | 100 @ 3.3998, limit 3.41, 4 fills | 100 @ 3.24, limit 3.24, 2 fills | -15.98 |
| IOVA | 71 @ 13.86, limit 13.92, 1 fill | 71 @ 14.06, limit 13.99, 4 fills | +14.20 |
| BEX | 23 @ 41.683913, limit 41.97, 2 fills | 23 @ 41.21, limit 41.01, 3 fills | -10.90 |
| AXTX | 26 @ 37.34, limit 37.52, 2 fills | 26 @ 37.06, limit 36.88, 5 fills | -7.28 |
| SSTI | 100 @ 8.26, limit 8.30, 1 fill | 100 @ 8.24, limit 8.20, 2 fills | -2.00 |

**Trial 3.** The scan fired 10 symbols. BKYI, IOVA and BEX entered; AXTX and SSTI were skipped with
`notional_below_one_share`. Leverage multiple 1, gross budget 2,424.04 USD.

| Symbol | Entry | Exit (`x2_time`) | Realized |
|---|---|---|---|
| BKYI | 100 @ 3.26, limit 3.27, 1 fill | 100 @ 2.78, limit 2.77, 5 fills | -48.00 |
| IOVA | 70 @ 14.07, limit 14.14, 1 fill | 70 @ 15.032143, limit 14.97, 3 fills | +67.35 |
| BEX | 22 @ 41.35, limit 41.55, 1 fill | 22 @ 41.23, limit 41.03, 3 fills | -2.64 |

**Trial 4.** The scan fired 8 symbols. BKYI, IOVA, BEX and NCPL entered; SSTI was skipped with
`entries_not_enabled`. Leverage multiple 2, gross budget 4,881.50 USD.

| Symbol | Entry | Exit (`x2_time`) | Realized |
|---|---|---|---|
| BKYI | 100 @ 2.78, limit 2.79, 1 fill | 100 @ 2.96, limit 2.95, 2 fills | +18.00 |
| IOVA | 66 @ 15.045455, limit 15.12, 2 fills | 66 @ 14.89, limit 14.82, 4 fills | -10.26 |
| BEX | 24 @ 41.30, limit 41.50, 6 fills | 24 @ 40.666667, limit 40.50, 4 fills | -15.20 |
| NCPL | 100 @ 1.28, limit 1.28, 1 fill | 100 @ 1.30, limit 1.30, 1 fill | +2.00 |

**Trial 5.** The scan fired 8 symbols. IOVA, BEX and NCPL entered; BKYI and SSTI were skipped with
`entries_not_enabled`. Leverage multiple 2, gross budget 4,870.58 USD. BEX's exit average is the engine receipt's
40.702083; the ledger and the broker record 40.702084 (see [Errors](#errors-rejects-and-retries)).

| Symbol | Entry | Exit (`x2_time`) | Realized |
|---|---|---|---|
| IOVA | 66 @ 14.92, limit 14.99, 1 fill | 66 @ 14.87, limit 14.80, 1 fill | -3.30 |
| BEX | 24 @ 40.67, limit 40.87, 2 fills | 24 @ 40.702083, limit 40.47, 4 fills | +0.77 |
| NCPL | 100 @ 1.31, limit 1.31, 1 fill | 100 @ 1.28, limit 1.28, 7 fills | -3.00 |

**Trial 6.** The scan fired 8 symbols. BKYI, IOVA and BEX entered; NCPL and SSTI were skipped with
`notional_below_one_share`. Leverage multiple 1, gross budget 2,429.76 USD. At 15:44:11 ET the ledger latched
`gross_loss_cap_reached` and the engine forced all three legs out with `risk_halt`.

| Symbol | Entry | Exit (`risk_halt`) | Realized |
|---|---|---|---|
| BKYI | 100 @ 3.11, limit 3.12, 1 fill | 100 @ 3.07, limit 3.06, 2 fills | -4.00 |
| IOVA | 66 @ 14.90, limit 14.97, 2 fills | 66 @ 14.56, limit 14.49, 1 fill | -22.44 |
| BEX | 22 @ 40.925455, limit 41.14, 3 fills | 22 @ 40.05, limit 39.85, 1 fill | -19.26 |

`entries_not_enabled` is the leg's last wait reason when the 30 s entry window closed: the engine's per-tick entry
enable was false whenever the leg was evaluated. The receipt does not record which enable condition was false.
`notional_below_one_share` means the sizing left less than one share's notional for the leg.

### Frozen acceptance per trial

The freeze (`FREEZE.md`, private, sha256 `4e595a8dcde…`) fixed the operational pass before the run: status `passed`
or `completed_no_signals`; `flat` true; end reconciliation `cash_match` and `positions_match` true; 0 open orders;
`pnl_consistent` true; no duplicate or unexplained broker effects (`duplicate_executions` 0); no ledger halt; no HTTP
429. `receipt.json` quotes the clause text (`frozen_acceptance`) and holds each trial's clause values
(`attempts[].acceptance`).

| Clause | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| status `passed` or `completed_no_signals` | `passed` | `passed` | `passed` | `passed` | `passed` | `passed` |
| flat | yes | yes | yes | yes | yes | yes |
| `cash_match`, `positions_match` | true | true | true | true | true | true |
| 0 open orders | 0 | 0 | 0 | 0 | 0 | 0 |
| `pnl_consistent` | true | true | true | true | true | true |
| no duplicate or unexplained effects (orders agreeing with the broker) | 10 of 10 | 10 of 10 | 6 of 6 | 8 of 8 | 6 of 6 | 6 of 6 |
| no ledger halt (`halted_reason`) | null | null | null | null | null | **`gross_loss_cap_reached`** |
| no HTTP 429 (HTTP observations; 33 scan pages each) | 0 in 505 | 0 in 505 | 0 in 501 | 0 in 507 | 0 in 501 | 0 in 353 |
| **Verdict** | **pass** | **pass** | **pass** | **pass** | **pass** | **fail** |

Every trial had 0 duplicate executions and 0 unconfirmed fills.

Recorded, not thresholded, as the freeze asks:
- **Fills and slippage.** 83 of 113 fills were at the order's reference quote (the ask for a buy, the bid for a
  sell), 13 were better and 17 worse. The worse fills walked the book within their limits: trial 1's BKYI entry (3 of
  5, average 3.7798 against a 3.77 ask), IOVA entry (2 of 2, 13.89 against 13.88), AXTX entry (2 of 2, 38.26 against
  38.14, the largest adverse average at 0.12 USD per share) and AXTX exit (4 of 5, 37.252308 against a 37.27 bid);
  trial 2's BKYI exit (2 of 2, 3.24 against 3.25); trial 3's IOVA exit (2 of 3, 15.032143 against 15.04); and trial
  4's BEX exit (2 of 4, 40.666667 against 40.70).
- **Exit reasons.** `x2_time` for the 20 legs of trials 1 to 5, `risk_halt` for the 3 legs of trial 6.
- **Realized P&L and fees.** -115.94 USD. Account 1's fees were not read (see [Limitations](#limitations)).
- **Planned versus realized gross/equity.** The engine's leverage multiple was 4, 2, 1, 2, 2 and 1, and the planned
  gross budgets 5,000.00, 4,892.00, 2,424.04, 4,881.50, 4,870.58 and 2,429.76 USD. Buy notional was 3,542.07,
  4,079.61, 2,220.60, 2,390.20, 2,091.80 and 2,194.76 USD, which is 1.417, 1.668, 0.916, 0.979, 0.859 and 0.903 of
  each trial's sizing equity.
- **Request and submit peaks.** 23, 23, 21, 22, 21 and 21 requests in the busiest 60 s (cap 150); 5, 5, 3, 4, 3 and
  3 submits (cap 130). The lowest `x-ratelimit-remaining` in the receipts was 187 of 200.
- **Websocket reconnects, gaps and recoveries.** Trials 1 and 4 logged one trading-stream restart line; the others
  one data-stream and one trading-stream line. The 6 trading-stream lines completed the closing handshake; the 4
  data-stream lines sent close code 1000 but received no close frame ([Errors](#errors-rejects-and-retries)). No
  engine log has a data-stream gap line, and no recovery ran.
- **`paper_compare.py`.** Not run (decision 11: the tool is not checked against `b528bb55` receipts).

## Series totals

- 46 orders: 23 entries and 23 exits. All were `limit`, `day`, `extended_hours` false, and all ended `filled` in the
  engine, the ledger and the broker listing.
- 113 fill events.
- Realized P&L -115.94 USD: -54.00, -21.96, +16.71, -5.46, -5.53 and -45.70 by trial. The engine receipts, the ledger
  deltas and the broker recompute agree.
- Gross loss 250.18 USD, the sum of the losing legs. This equals the ledger's `realized_loss` and trial 6's
  `lifetime_gross_loss_usd`, against a 250 USD budget.
- The ledger's peak P&L was 59.64 USD, a mark-to-market figure reached during trial 1 (trial 1's drawdown 113.64
  equals 59.64 minus its realized -54.00). The final drawdown was 175.58 USD of the 250 USD drawdown budget.
- The ledger at 15:44 ET: lifetime realized -115.94, cash delta -115.94, `halted_reason` `gross_loss_cap_reached`,
  every position 0. The ledger was created fresh by trial 1, so these are this series' figures, and the halt is
  permanent for it.

## Broker reconciliation (2026-09-30 09:06Z)

This was a fresh read-only read of account 1 by the trading-lane coordinator, GET requests only, on the paper
endpoint. Its stdout is kept byte-identical as `reconcile-rth-20260929.stdout.json`; the private-detail check found
nothing to redact.
- **Tool.** `reconcile_ext_series.py` from [`ext-20260928`](../ext-20260928/README.md) (sha256 `50b9da4c…`), cited
  by path and hash rather than copied. It ran from a byte-identical private copy with the pinned adaptive-paper
  interpreter; the stdout records alpaca-py 0.44.0 and Python 3.12.3. The command line is not recorded. The
  coordinator's brief routes the credential as `--env-file "$PAPER_ENV_FILE"` under `/bin/bash -ic`, and the tool
  requires `--env-file` and `--ledger` and prescribes passing both through shell variables, so that neither path
  appears on a recorded command line.
- **Window.** From 2026-09-29T14:00Z (10:00 ET) to 20:20Z, prefix `mvr-rth-20260929-`.

The tool reads the ledger first (sqlite `mode=ro`), then the broker's orders (`status=all`), FILL activities (2
pages), positions and open orders, and joins them in memory:
- 46 orders were listed in the window. All 46 carry the series prefix, and there were 0 foreign orders.
- There were 113 FILL activities, none foreign. All 113 ledger executions match an activity on `cum_qty`, `qty` and
  `price`, and also on execution id. The largest time difference was 0.004 s.
- **0 unconfirmed fills.** Any ledger execution without a matching activity would have been listed as unconfirmed.
- All 46 orders agree with the ledger intents on symbol, side, quantity, limit, final status, filled quantity and
  average price.
- Sells minus buys from the broker's activities: -54.00, -21.96, +16.71, -5.46, -5.53 and -45.70 by trial, -115.94
  in total. Every trial ended flat, so this is the realized P&L, and it equals the engine and ledger figures.
- 0 positions and 0 open orders at the time of the read.

The read is separate from the engine code and ledger writer. It uses the same broker API and account, so it is
independent of the engine but not of the broker.

## Errors, rejects and retries

- **Ledger halt in trial 6.**
  - The ledger's only `risk_halt` event (reason `gross_loss_cap_reached`) follows trial 6's last entry execution
    (15:02:37 ET) and precedes its first exit reservation (15:44:11 ET). The engine latched the force `risk_halt` at
    15:44:11 ET and sold all three legs.
  - How the engine counts it (`safety.py` at `b528bb55`): `_state` (lines 684-699) takes gross loss as the realized
    loss plus each open position's unrealized loss at the bid (line 696), and `_refresh_risk` (lines 752-766)
    latches `gross_loss_cap_reached` once gross loss reaches `max_gross_loss_usd`.
  - The halt latched while trial 6's three positions were open, so the test used realized loss 204.48 plus their
    unrealized loss at the bid. The exits then realized 45.70 of loss (BKYI -4.00, IOVA -22.44, BEX -19.26), leaving
    `realized_loss` at 250.18. The exact mark-to-market figure at 15:44:11 ET is not recorded.
  - The halt is permanent for this ledger: a next trial is refused (`next_trial_cannot_clear_risk_halt`,
    `safety.py` line 628). The engine still reported `passed`, and the driver logged `rth-20260929-6 rc=0: yes`.
- **Average-invariant mismatches in trial 5.** The engine recorded 2 on `mvr-rth-20260929-5-0000005`, the BEX sell
  of 24.
  - What they mean: `native_adapter.py` lines 532-552 at `b528bb55`, the E2 invariant, "recorded and never a freeze".
    Once booked executions tile (0, filled], their notional must equal the filled quantity times the broker's
    reported average within filled times 0.0000005 USD (`AVERAGE_ROUNDING`, line 71), the half-unit of Alpaca's
    6-decimal average.
  - At 22 and at 24 shares filled, the broker's average (40.698637, then 40.702084) was one unit in the 6th decimal
    above the executions' exact average rounded to nearest (40.698636, 40.702083). The differences were 0.000014 and
    0.000016 USD against tolerances of 0.000011 and 0.000012.
  - No frozen clause covers them: the freeze lists no invariant, so they are recorded, not thresholded. They are not
    a duplicate effect. The order's 4 executions match the broker's FILL activities, and the ledger's average equals
    the broker's 40.702084, so the reconciliation shows no unexplained difference. The engine receipt's own average
    for this exit, 40.702083, is the series' only engine-versus-broker average difference.
- **Rejects, cancels and other engine errors.** None. There were no native rejections, pre-wire refusals or cancels,
  and no adapter errors, callback faults or duplicate executions. No fill gap was open at stop. The halt seeds held
  25, 29, 36, 38, 38 and 40 items, none halted. These figures come from the engine receipts alone
  (`field_provenance`).
- **Retries.** None. Every trial started on its first attempt, with no `benchmark_quotes_not_ready` refusal.
- **HTTP.** 0 HTTP 429 and no transport `rate_limited` mark. The receipts hold 505, 505, 501, 507, 501 and 353 HTTP
  observations, all 200, and every scan's 33 pages returned 200.
- **Websocket lines.** alpaca-py logs every websocket exception as a restart line, clean closes included
  (`websocket_lines` in `receipt.json`).
  - The 6 trading-stream lines read `sent 1000 (OK); then received 1000 (OK)`: the closing handshake completed.
  - The 4 data-stream lines, one each in trials 2, 3, 5 and 6, read `sent 1000 (OK); no close frame received`: the
    client sent close code 1000 but no close frame came back, which websockets 17.1 raises as
    `ConnectionClosedError`. The closing handshake did not complete, so `websocket_lines_without_close_frame` is 1 in
    those trials and 0 in trials 1 and 4.
  - The logs carry no timestamps. The 2026-09-23 isolation check's committed output recorded both forms only after
    the engine's `stop()`, 0.016 s and 0.018 s after it; this series neither confirms nor rules that out.
- **Quote handling.** Crossed quotes were dropped and counted: 819 (444 of them IOVA), 523, 316, 227, 382 and 106.
- **Request counts.** From each trial start the ledger holds exactly the engine-reported requests: 484 reads and 10
  submits, 484 and 10, 484 and 6, 488 and 8, 484 and 6, and 336 and 6.

## Deviations from the freeze

- **Ledger-halt stop not implemented by the driver (not exercised).** The freeze stops the series on a ledger halt,
  but `series-driver.sh` reads only the receipts' status and 429s. After trial 6 latched `gross_loss_cap_reached`
  it logged `rth-20260929-6 rc=0: yes`, and the series ended at 15:44:16 ET only because the 15:40 ET last start had
  passed. No trial started after the halt, and the ledger itself refuses one.
- Otherwise none found. The config sha256 matched in every `check.json` and engine receipt, and every start came
  from the timer and the driver. The series scripts were unchanged: `series-driver.sh`, `run-series-trial.sh` and
  `retry-benchmark.sh` predate the freeze files, and their sha256 on 2026-09-30 equals the table in the private
  series index (written 05:20:57Z). `FREEZE.md` names the driver arguments and `retry-benchmark.sh` but hashes no
  script.

## Units (systemd user journal and manager)

| Unit | Start (UTC) | Stop (UTC) | Result |
|---|---|---|---|
| `paper-rth-20260929` | 14:00:05 | 19:44:16 | `success`, exit status 0 (manager); no journal exit record |

The journal was queried on 2026-09-30 with `journalctl --user -o json USER_UNIT=<unit>.service` (systemd 255).
- The unit has start records and a resource-accounting record only: no `EXIT_STATUS`, `EXIT_CODE` or `UNIT_RESULT`
  record and no success record.
- The systemd user manager still held its result when read with `systemctl --user show` on 2026-09-30 at 18:57Z:
  `Result=success`, `ExecMainCode=1` (the process exited on its own) and `ExecMainStatus=0`, with the same start
  and stop times. The manager has run since 2026-09-24, so this is the run's own result, but a manager restart would
  clear it. The driver's last console line reads `series ends: past last start 1540 ET`, its exit-0 path.
- The unit and timer files are hashed in `receipt.json`, and each hash matches the private series index.

The broker listing shows no order without the series prefix on account 1 in the window.

## Limitations

- **Metadata plus broker-reconciled evidence, not a frozen gate run.** It qualifies no gate. Unconfirmed fills
  would have been marked unconfirmed; there were none.
- **Simulated fills.** Alpaca paper fills are simulated from quotes. They say nothing about live slippage, queue
  position or partial fills.
- **Not a strategy evaluation.** Six trials in one regular session evaluate no strategy, and the protocol has no
  validated edge.
- **Fees not read.** Account 1's FEE activities were not read, so any fees the broker posted for 2026-09-29 on
  account 1 are unmeasured here. The engine has no fee model.
- **The halt's trigger value.** The ledger's `risk_halt` event carries no timestamp or amount, and later quotes
  overwrote the marks, so the mark-to-market gross loss at 15:44:11 ET is not recorded.
- **Single-source fields.** Some figures come from one source only. Examples are the halt seed counts, the
  crossed-quote drops, the websocket lines, the preflight fields, the HTTP observations, the leverage multiples and
  the ledger's peak P&L. `receipt.json` `field_provenance` lists every field as asserted across sources, single
  source, derived or literal.

## Paper lane row

The grand-dashboard `paper` lane, "Alpaca paper accounts 1 and 2", cites [`ext-20260928`](../ext-20260928/README.md)
at this branch's base. Pointing it at the 2026-09-29 receipts is the coordinator's step; this branch does not touch
the dashboard. For account 1 this receipt supports an RTH series on 2026-09-29 with 5 of 6 trials passed and trial 6
failed on a ledger halt (`gross_loss_cap_reached`), flat at 15:44 ET. Account 1's ledger is permanently halted.

## Files

| File | What it is |
|---|---|
| `receipt.json` | The series receipt: code identity, config, frozen acceptance and per-trial verdicts, per-attempt results, 46 orders, the halt and the average-invariant records, broker reconciliation, units, totals, field provenance, and hashes of the committed copies and of retained private files that carry no account fingerprint |
| `README.md` | This summary |
| `reconcile-rth-20260929.stdout.json` | The independent broker reconciliation's stdout, byte-identical; the tool is cited by path and sha256 |
| `frozen-b528bb55.SHA256SUMS` | The freeze's hashes of the 70 engine, scanner, order-contract and incentive-monitor files, byte-identical |
| `mover-paper-1.json` to `mover-paper-6.json` | Engine receipts of trials 1 to 6. Each `broker_order_ref` value (10, 10, 6, 8, 6 and 6) is replaced by `withheld`; every other byte is unchanged |
| `series.console` | The series console (run log), byte-identical |

Private and not committed:
- the freeze note and the private series index, which name account fingerprints (cited by sha256);
- the config file and rule file, whose content is in `receipt.json`;
- the scan, check and synthetic files, the engine logs and events, and the scan page ledgers and caches;
- the series scripts and the systemd units (hashed);
- the engine ledger and its snapshot;
- the NautilusTrader logs.
