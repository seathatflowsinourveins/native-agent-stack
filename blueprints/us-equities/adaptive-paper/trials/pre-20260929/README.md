# Pre-market mover paper series `pre-20260929`, 2026-09-29 PRE: 3 of 3 trials passed, flat

This is the sanitized receipt of a pre-market mover paper series on account 2 (credential inventory id
`alpaca-paper-2`). It ran in the PRE session of 2026-09-29, from 07:00:05 to 09:25:03 ET, started by a timer.
`receipt.json` holds the figures. This directory also holds the broker reconciliation's stdout, sanitized copies of
the three engine receipts, the series console and the frozen SHA256SUMS ([Files](#files)). The freeze note, the
engine ledger, the scan caches and the rest of the trial workspace stay private.

It is metadata plus broker-reconciled evidence, not a frozen gate run. It qualifies no gate. The run was a
mechanics-only test with no validated edge: the protocol's development study passed 0 of 768 rule-exits
([`mover-early-entry`](../../../mover-early-entry/README.md)). No credential, account id, account number, account
fingerprint, broker order id or ref, activity id, execution id or host path is recorded.

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
versions were read from the same environment on 2026-09-30. `FREEZE.md` records the same versions except requests,
which only the private series index records. They were not observed at run time.

**Credential route.** The 0600 env file store through the `$PAPER_ENV_FILE_2` pointer
([docs/secret-storage.md](../../../../../docs/secret-storage.md)). The unit launched through `/bin/bash -ic`, whose
interactive start-up exports the pointer. `run-series-trial.sh` passed it as `--env-file` to the scan, `paper` and
`recover`, and the driver's key probe used the same pointer.

**Config.** Frozen before any broker I/O, sha256 `da2ce5d2f0890b…`:
- protocol `mover-early-entry-v1-20260924`, section `paper_e2e`;
- rule `07:00|G20|V1000000|any` (gain in percent points; `rule.txt` holds the scanner's ratio form `G0.20`), exit X2
  (a 3,600 s hold), scope `pre_market_only`, trial end 09:25 ET;
- SIP feed, extended hours on, no overnight holds, benchmark SPY only;
- capital 4,991.09 USD, at most 5 symbols;
- entry cap 1,000 USD per symbol; ledger caps of 10,000 USD per order, 100 shares and 10,000 USD gross;
- lifetime gross loss 480 USD and drawdown 475 USD for this ledger, which `ext-20260929` shares;
- rung 4 under `leverage-schedule-v1-20260922`, whose PRE cell holds the envelope at 1x;
- at most 150 requests and 130 submits per minute, and at most 20 outstanding orders;
- quotes at most 3 s old, spreads at most 100 bps, limit caps of 50 bps;
- an entry window of 30 s, `stream_quote_timeout_seconds` 30, and a hard flatten at min(start + 68 min, 09:25 ET).

**Procedure.** Each trial ran four steps: `mover_scan.py`, then `mover_runner.py check`, then a synthetic run (SYN)
on the same scan, then `paper`. `recover` was to run on `needs_attention`, but no trial needed it.
- The timer started `paper-pre-20260929.service` at 07:00:05 ET. The unit ran `series-driver.sh pre-20260929 2 1
  0915 6` under `/bin/bash -ic`, with `ENGINE_SHA` set and the state root set to the new account-2 root.
- The driver checks the kill switch, the clone and the SUMS, and probes the key once (`GET /v2/account`: HTTP 200,
  199 of 200 requests remaining). It then runs trials through `retry-benchmark.sh` until the last start, a trial
  that neither passed nor recovered, or any HTTP 429.
- Three trials ran back to back. The series ended at 09:25:03 ET on the 09:15 ET last-start rule: `series ends: past
  last start 0915 ET`.
- A dry run at 01:14:30 ET (05:14:30Z), after the freeze and before any timer, passed the driver's check mode (key
  probe 200), `check` (valid) and `synthetic` (`completed_no_signals`, flat). It had no `paper` stage.

## Attempts

| # | ET | Result | Orders | Fills (engine = ledger = broker) | Realized P&L | Flat at end |
|---|---|---|---|---|---|---|
| 1 | 07:00:05-08:01:00 | **passed** | 8 | 20 | -62.50 USD | yes |
| 2 | 08:01:00-09:07:04 | **passed** | 4 | 14 | +38.00 USD | yes |
| 3 | 09:07:04-09:25:03 | **passed**, hard flatten at 09:25:00 | 6 | 12 | +22.45 USD | yes |

Flat at end means that each trial's end reconciliation showed `cash_match` and `positions_match` true, 0 open orders
and 0 positions.

**Trial 1.** The scan fired 4 symbols: BKYI, YMT, MSGY and SANG. All four entered and exited on `x2_time`, the X2
hold.

| Symbol | Entry | Exit (`x2_time`) | Realized |
|---|---|---|---|
| BKYI | 100 @ 2.475, limit 2.49, 5 fills | 100 @ 2.57, limit 2.56, 3 fills | +9.50 |
| YMT | 100 @ 2.49, limit 2.51, 1 fill | 100 @ 2.05, limit 2.04, 1 fill | -44.00 |
| MSGY | 100 @ 3.95, limit 3.96, 3 fills | 100 @ 3.65, limit 3.64, 4 fills | -30.00 |
| SANG | 100 @ 4.94, limit 4.96, 2 fills | 100 @ 4.96, limit 4.94, 1 fill | +2.00 |

**Trial 2.** The scan fired 2 symbols, BKYI and SANG. Sizing equity was 4,928.59 USD, after trial 1's -62.50.

| Symbol | Entry | Exit (`x2_time`) | Realized |
|---|---|---|---|
| BKYI | 100 @ 2.48, limit 2.49, 5 fills | 100 @ 2.86, limit 2.85, 4 fills | +38.00 |
| SANG | 100 @ 5.00, limit 5.02, 4 fills | 100 @ 5.00, limit 4.98, 1 fill | 0.00 |

**Trial 3.** The scan fired 4 symbols. BKYI, MSGY and YMT entered. SANG was skipped with `no_fresh_quote` when the
30 s entry window closed. The trial started at 09:07:15 ET, so the 09:25:00 ET hard flatten closed all three legs
before X2 could fire.

| Symbol | Entry | Exit (`hard_flatten`) | Realized |
|---|---|---|---|
| BKYI | 100 @ 2.92, limit 2.93, 1 fill | 100 @ 3.299, limit 3.27, 2 fills | +37.90 |
| YMT | 100 @ 2.12, limit 2.13, 1 fill | 100 @ 2.1755, limit 2.15, 6 fills | +5.55 |
| MSGY | 100 @ 4.29, limit 4.31, 1 fill | 100 @ 4.08, limit 4.06, 1 fill | -21.00 |

### Frozen acceptance per trial

The freeze (`FREEZE.md`, private, sha256 `3cd44b…`) fixed the pass rule before the run, "as in `rth-20260929`":
status `passed` or `completed_no_signals`; flat; `cash_match` and `positions_match` true; 0 open orders;
`pnl_consistent` true; no duplicate or unexplained effects; no halt; no HTTP 429. `receipt.json` quotes the clause
text (`frozen_acceptance`) and holds each trial's clause values (`attempts[].acceptance`).

| Clause | Trial 1 | Trial 2 | Trial 3 |
|---|---|---|---|
| status `passed` or `completed_no_signals` | `passed` | `passed` | `passed` |
| flat | yes | yes | yes |
| `cash_match`, `positions_match` | true, true | true, true | true, true |
| 0 open orders | 0 | 0 | 0 |
| `pnl_consistent` | true | true | true |
| no duplicate or unexplained effects | 0 duplicates; 8 of 8 orders agree | 0 duplicates; 4 of 4 agree | 0 duplicates; 6 of 6 agree |
| no ledger halt (`halted_reason`) | null | null | null |
| no HTTP 429 | 0 in 506 observations and 33 scan pages | 0 in 544 and 33 | 0 in 164 and 33 |
| **Verdict** | **pass** | **pass** | **pass** |

Recorded, not thresholded, as the freeze asks:
- **Fills and slippage.** 36 of 46 fills were at the order's reference quote (the ask for a buy, the bid for a
  sell), 10 were better and 0 worse. The better ones: trial 1's BKYI entry (average 2.475 against a 2.48 ask, 1 of 5
  fills better) and YMT entry (2.49 against 2.50), and trial 3's BKYI exit (average 3.299 against a 3.28 bid, 2 of
  2 fills better) and YMT exit (2.1755 against 2.16, 6 of 6).
- **Exit reasons.** `x2_time` for the 6 legs of trials 1 and 2, `hard_flatten` for the 3 legs of trial 3.
- **Realized P&L.** -2.05 USD for the series.
- **Quote waits and stream gaps.** SANG's `no_fresh_quote` skip in trial 3; no data-stream gap line in any engine
  log.
- **Websocket reconnects.** One data-stream and one trading-stream restart line per trial. Every trading-stream line
  completed the closing handshake; every data-stream line sent close code 1000 but received no close frame
  ([Errors](#errors-rejects-and-retries)).
- **Benchmark refusals.** 0.
- **Request peaks.** 21, 17 and 20 requests in the busiest 60 s (cap 150); 4, 2 and 3 submits (cap 130).
- **Average-invariant mismatches.** 0.
- **`paper_compare.py`.** Not run (decision 11: the tool is not checked against `b528bb55` receipts).

## Series totals

- 18 orders: 9 entries and 9 exits. All were `limit`, `day`, `extended_hours` true, and all ended `filled` in the
  engine, the ledger and the broker listing.
- 46 fill events.
- Realized P&L -2.05 USD: trial 1 -62.50, trial 2 +38.00, trial 3 +22.45. The engine receipts, the ledger deltas and
  the broker recompute agree.
- Gross loss 95.00 USD: the losing legs, trial 1 YMT -44.00 and MSGY -30.00, and trial 3 MSGY -21.00. This equals
  trial 3's ledger `lifetime_gross_loss_usd`, because account 2's new ledger began with this series.
- The ledger at 09:25 ET: lifetime realized -2.05, drawdown 2.05, peak P&L 0.00, cash delta -2.05, no halt.
  `ext-20260929` continued the same ledger that afternoon; its receipt states the later figures without repeating
  these.
- Leverage applied: the PRE cell held the engine's leverage multiple at 1 in every trial. Buy notional was 1,385.50,
  748.00 and 933.00 USD, which is 0.278, 0.152 and 0.188 of the trial's sizing equity.
- Fees are not in these figures. The broker posted three FEE activities for 2026-09-29 on account 2: REG -0.19, TAF
  -0.27 and CAT -0.01 USD. They are day totals for this series and `ext-20260929` together; the REG fee's basis,
  8,820.73 USD of proceeds, is all of account 2's sells that day. The frozen engine has no fee model.

## Broker reconciliation (2026-09-30 09:06Z)

This was a fresh read-only read of account 2 by the trading-lane coordinator, GET requests only, on the paper
endpoint. Its stdout is kept byte-identical as `reconcile-pre-20260929.stdout.json`; the private-detail check found
nothing to redact.
- **Tool.** `reconcile_ext_series.py` from [`ext-20260928`](../ext-20260928/README.md) (sha256 `50b9da4c…`), cited
  by path and hash rather than copied. It ran from a byte-identical private copy with the pinned adaptive-paper
  interpreter; the stdout records alpaca-py 0.44.0 and Python 3.12.3. The command line is not recorded. The
  coordinator's brief routes the credential as `--env-file "$PAPER_ENV_FILE_2"` under `/bin/bash -ic`, and the tool
  requires `--env-file` and `--ledger` and prescribes passing both through shell variables, so that neither path
  appears on a recorded command line.
- **Window.** From 2026-09-29T11:00Z (07:00 ET) to 13:45Z, prefix `mvr-pre-20260929-`.

The tool reads the ledger first (sqlite `mode=ro`), then the broker's orders (`status=all`), FILL activities (1
page), positions and open orders, and joins them in memory:
- 18 orders were listed in the window. All 18 carry the series prefix, and there were 0 foreign orders.
- There were 46 FILL activities, none foreign. All 46 ledger executions match an activity on `cum_qty`, `qty` and
  `price`, and also on execution id. The largest time difference was 0.002 s.
- **0 unconfirmed fills.** Any ledger execution without a matching activity would have been listed as unconfirmed.
- All 18 orders agree with the ledger intents on symbol, side, quantity, limit, final status, filled quantity and
  average price.
- Sells minus buys from the broker's activities: -62.50, +38.00 and +22.45 by trial, -2.05 in total. Every trial
  ended flat, so this is the realized P&L, and it equals the engine and ledger figures.
- At the time of the read the account held 1 position, IOVA, with 0 open orders. IOVA is `ext-20260929` trial 4's
  residual on this shared account (68 shares, bought at 16:25 ET), not this series'. This series ended flat at 09:25
  ET.

The read is separate from the engine code and ledger writer. It uses the same broker API and account, so it is
independent of the engine but not of the broker.

## Errors, rejects and retries

- **Rejects, cancels and engine errors.** None. There were no native rejections, pre-wire refusals or cancels, and
  no adapter errors, callback faults, average-invariant mismatches or duplicate executions. No fill gap was open at
  stop and nothing halted; the halt seeds held 20, 20 and 21 items. These figures come from the engine receipts
  alone (`field_provenance`).
- **Retries.** None. Every trial started on its first attempt, with no `benchmark_quotes_not_ready` refusal.
- **HTTP.** 0 HTTP 429 and no transport `rate_limited` mark. The receipts hold 506, 544 and 164 HTTP observations,
  all 200, and the lowest `x-ratelimit-remaining` was 188 of 200. Every scan's 33 pages returned 200.
- **Websocket lines.** Each trial's engine log has one trading-stream and one data-stream restart line, and no
  data-stream gap line. alpaca-py logs every websocket exception this way, clean closes included (`websocket_lines`
  in `receipt.json`).
  - The trading-stream line reads `sent 1000 (OK); then received 1000 (OK)`: the closing handshake completed.
  - The data-stream line reads `sent 1000 (OK); no close frame received`: the client sent close code 1000 but no
    close frame came back, which websockets 17.1 raises as `ConnectionClosedError`. The closing handshake did not
    complete, so `websocket_lines_without_close_frame` is 1 in every trial.
  - The logs carry no timestamps. The 2026-09-23 isolation check's committed output recorded both forms only after
    the engine's `stop()`, 0.016 s and 0.018 s after it; this series neither confirms nor rules that out.
- **Quote freshness.** SANG was skipped in trial 3 with `no_fresh_quote`. Crossed quotes were dropped and counted:
  184, 493 (483 of them BKYI) and 54.
- **Hard flatten.** Trial 3's three legs were closed by the 09:25 ET hard flatten. The freeze accepted this effect:
  X2 fires before the flatten only when the first fill is at or before 08:25.
- **Request counts.** From each trial start the ledger holds exactly the engine-reported requests: 488 reads and 8
  submits, 532 and 4, and 148 and 6.

## Deviations from the freeze

None found.
- The config sha256 matched in every `check.json` and engine receipt.
- The series scripts were unchanged. `series-driver.sh`, `run-series-trial.sh` and `retry-benchmark.sh` predate the
  freeze files, and their sha256 on 2026-09-30 equals the table in the private series index (written 05:20:57Z).
  `FREEZE.md` names the driver arguments and `retry-benchmark.sh` but hashes no script.
- Every start came from the timer and the driver, no attempt needed a retry, and the series ended on the 09:15 ET
  last-start rule.
- The driver's pass rule (engine status `passed` or `completed_no_signals`, or a passed recovery, and no 429) does
  not read the ledger halt that the freeze's stop rules and acceptance name. No halt occurred here.

## Units (systemd user journal and manager)

| Unit | Start (UTC) | Stop (UTC) | Result |
|---|---|---|---|
| `paper-pre-20260929` | 11:00:05 | 13:25:03 | `success`, exit status 0 (manager); no journal exit record |
| `incentive-monitor-20260929` | 07:55:00 | 00:00:14 (09-30) | `success`, exit status 0 (manager); no journal exit record |

The journal was queried on 2026-09-30 with `journalctl --user -o json USER_UNIT=<unit>.service` (systemd 255).
- Both units have start records and a resource-accounting record only. Neither has an `EXIT_STATUS`, `EXIT_CODE` or
  `UNIT_RESULT` record or a success record.
- The systemd user manager still held both results when read with `systemctl --user show` on 2026-09-30 at
  18:57Z: `Result=success`, `ExecMainCode=1` (the process exited on its own) and `ExecMainStatus=0`, with the same
  start and stop times. The manager has run since 2026-09-24, so these are the runs' own results, but a manager
  restart would clear them. The driver's last console line reads `series ends: past last start 0915 ET`, its exit-0
  path.
- The unit and timer files are hashed in `receipt.json`, and each hash matches the private series index.

The incentive monitor ran on account 2's key pair and is data only. Its docstring says it never places, changes or
cancels an order, and the broker listing shows no order without the series prefix in this window.

## Limitations

- **Metadata plus broker-reconciled evidence, not a frozen gate run.** It qualifies no gate. Unconfirmed fills
  would have been marked unconfirmed; there were none.
- **Simulated fills.** Alpaca paper fills are simulated from quotes. They say nothing about live slippage, queue
  position or partial fills.
- **Not a strategy evaluation.** Three trials in one pre-market session evaluate no strategy, and the protocol has
  no validated edge.
- **Account designation.**
  - The series kept its own engine ledger, the new account-2 root, which `ext-20260929` shares.
  - It traded broker account `alpaca-paper-2`. Two records designate that account as the isolated
    incentive-monitor study account:
    [`forward-protocol-v1.json`](../../../incentive-monitor/forward-protocol-v1.json) (line 63) and
    [docs/secret-storage.md](../../../../../docs/secret-storage.md) (line 17).
  - Whether this use fits the forward study's isolation is referred to the forward protocol's owner, the trading
    lane. This receipt does not decide it.
- **Fees.** The frozen engine has no fee model. The REG, TAF and CAT fees posted for 2026-09-29 (-0.47 USD in total
  on account 2) are outside every figure here.
- **Single-source fields.** Some figures come from one source only. Examples are the halt seed counts, the
  crossed-quote drops, the websocket lines, the preflight fields, the HTTP observations and the ledger's peak P&L.
  `receipt.json` `field_provenance` lists every field as asserted across sources, single source, derived or
  literal.

## Paper lane row

The grand-dashboard `paper` lane, "Alpaca paper accounts 1 and 2", cites [`ext-20260928`](../ext-20260928/README.md)
at this branch's base. Pointing it at the 2026-09-29 receipts is the coordinator's step; this branch does not touch
the dashboard. For account 2 this receipt supports a pre-market series on 2026-09-29 with 3 of 3 trials passed,
flat at 09:25 ET. Account 2 did not stay flat that day: [`ext-20260929`](../ext-20260929/README.md) ended holding
IOVA 68.

## Files

| File | What it is |
|---|---|
| `receipt.json` | The series receipt: code identity, config, frozen acceptance and per-trial verdicts, per-attempt results, 18 orders, broker reconciliation, units, totals, field provenance, and hashes of the committed copies and of retained private files that carry no account fingerprint |
| `README.md` | This summary |
| `reconcile-pre-20260929.stdout.json` | The independent broker reconciliation's stdout, byte-identical; the tool is cited by path and sha256 |
| `frozen-b528bb55.SHA256SUMS` | The freeze's hashes of the 70 engine, scanner, order-contract and incentive-monitor files, byte-identical |
| `mover-paper-1.json` to `mover-paper-3.json` | Engine receipts of trials 1 to 3. Each `broker_order_ref` value (8, 4 and 6) is replaced by `withheld`; every other byte is unchanged |
| `series.console` | The series console (run log), byte-identical |

Private and not committed:
- the freeze note and the private series index, which name account fingerprints (cited by sha256);
- the config file and rule file, whose content is in `receipt.json`;
- the scan, check and synthetic files, the engine logs and events, and the scan page ledgers and caches;
- the series scripts and the systemd units (hashed);
- the engine ledger and its snapshot;
- the NautilusTrader logs.
