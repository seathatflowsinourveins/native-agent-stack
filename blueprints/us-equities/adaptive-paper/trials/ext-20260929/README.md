# Extended-hours mover paper series `ext-20260929`, 2026-09-29 POST: 3 of 4 trials passed (trial 1 with no fill), trial 4 needs attention, IOVA 68 left open

This is the sanitized receipt of an extended-hours mover paper series on account 2 (credential inventory id
`alpaca-paper-2`). It ran in the POST session of 2026-09-29, from 16:00:05 to 17:11:31 ET, started by a timer.
`receipt.json` holds the figures. This directory also holds the two broker reconciliation stdouts, sanitized copies
of the four engine receipts, the recovery receipt, the series console and the frozen SHA256SUMS ([Files](#files)).
The freeze note, the engine ledger, the scan caches and the rest of the trial workspace stay private.

The engine reported trial 1 `completed_no_signals` (its five entries were canceled unfilled), trials 2 and 3
`passed` and trial 4 `needs_attention`. Trial 4's exits were forced by a transport gap; its BEX leg was sold by the
recovery, but the recovery's IOVA sale was refused before any HTTP request, so the series stopped at 17:11:31 ET on
its failed-recovery rule, holding IOVA 68. Under the frozen acceptance trials 1 to 3 pass and trial 4 is
`needs_attention`: it ended not flat, with the ledger halted at `recovery_only` and `pnl_consistent` false. The
residual's recovery on 2026-09-30 is [pending](#residual-recovery-on-2026-09-30). It is metadata plus
broker-reconciled evidence, not a frozen gate run, and it qualifies no gate. The run was a mechanics-only test with
no validated edge: the protocol's development study passed 0 of 768 rule-exits
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
versions were read from the same environment on 2026-09-30. `FREEZE.md` takes the runtime "as in `rth-20260929`"
and names no version; `rth-20260929`'s freeze note and the private series index record these versions. They were not
observed at run time.

**Credential route.** The 0600 env file store through the `$PAPER_ENV_FILE_2` pointer
([docs/secret-storage.md](../../../../../docs/secret-storage.md)). The unit launched through `/bin/bash -ic`, whose
interactive start-up exports the pointer. `run-series-trial.sh` passed it as `--env-file` to the scan, `paper` and
`recover`, and the driver's key probe used the same pointer.

**Config.** Frozen before any broker I/O, sha256 `3a35221a3cea0b…`. The config file was written at 01:06:11 ET and
`FREEZE.md` at 01:12:32 ET; this series' first broker request was its dry run's key probe at 01:14:31 ET.
- protocol `mover-early-entry-v1-20260924`, section `paper_e2e`;
- rule `10:00|G20|V1000000|any` (gain in percent points; `rule.txt` holds the scanner's ratio form `G0.20`), exit X2
  (a 3,600 s hold), scope `any_session`, trial end 19:45 ET;
- SIP feed, extended hours on, no overnight holds, benchmark SPY only;
- capital 4,991.09 USD, at most 5 symbols;
- entry cap 1,000 USD per symbol; ledger caps of 10,000 USD per order, 100 shares and 10,000 USD gross;
- lifetime gross loss 480 USD and drawdown 475 USD for this ledger, which `pre-20260929` shares;
- rung 4 under `leverage-schedule-v1-20260922`, whose POST cell holds the envelope at 1x;
- at most 150 requests and 130 submits per minute, and at most 20 outstanding orders;
- quotes at most 3 s old, spreads at most 100 bps, limit caps of 50 bps;
- an entry window of 30 s and an entry timeout of 60 s, an exit timeout of 10 s, `stream_quote_timeout_seconds` 30,
  and a hard flatten at min(start + 68 min, 19:45 ET).

**Procedure.** Each trial ran four steps: `mover_scan.py`, then `mover_runner.py check`, then a synthetic run (SYN)
on the same scan, then `paper`, and `recover` when `paper` ended `needs_attention`.
- The timer started `paper-ext-20260929.service` at 16:00:05 ET. The unit ran `series-driver.sh ext-20260929 2 1
  1830 6` under `/bin/bash -ic`, with `ENGINE_SHA` set and the state root set to the account-2 root that
  `pre-20260929` had used that morning. The unit refuses to start while the pre-market unit is active.
- The driver checks the kill switch, the clone and the SUMS, and probes the key once (`GET /v2/account`: HTTP 200,
  199 of 200 requests remaining). It then runs trials through `retry-benchmark.sh` until the last start, a trial
  that neither passed nor recovered, or any HTTP 429.
- Four trials ran back to back. Trial 4's `paper` and `recover` both ended `needs_attention`, and the series stopped
  at 17:11:31 ET: `series stops: ext-20260929-4 no paper=needs_attention recovery=needs_attention`.
- A dry run at 01:14:31 ET (05:14:31Z), after the freeze and before any timer, passed the driver's check mode (key
  probe 200), `check` (valid) and `synthetic` (`completed_no_signals`, flat). It had no `paper` stage.

## Attempts

| # | ET | Result | Orders sent | Fills (engine = ledger = broker) | Realized P&L | Flat at end |
|---|---|---|---|---|---|---|
| 1 | 16:00:05-16:01:35 | `completed_no_signals` (**pass**): 5 entries canceled unfilled | 5 | 0 | 0.00 USD | yes |
| 2 | 16:01:35-16:18:32 | **passed**; exits forced by `controller_stop` at 16:18:14 | 8 | 20 | -14.22 USD | yes |
| 3 | 16:18:32-16:21:32 | **passed**; exits forced by `controller_stop` at 16:21:14 | 4 | 6 | -2.84 USD | yes |
| 4 | 16:21:32-17:11:31 | **needs_attention**: `transport_gap` at 17:08:39, paper rc 3, recover rc 3 | 4, and 1 by the recovery | 7, and 2 in the recovery | +1.68 USD | no: IOVA 68 |

Flat at end means, for trials 1 to 3, that the trial's end reconciliation showed `cash_match` and `positions_match`
true, 0 open orders and 0 positions. Trial 4 has no end reconciliation ([Frozen acceptance per
trial](#frozen-acceptance-per-trial)).

**Trial 1.** The scan fired 7 symbols; the top 5 were BKYI, IOVA, BEX, SSTI and BEG. The engine's leverage multiple
was 1 (the POST cell) and the gross budget 4,989.04 USD, the sizing equity after `pre-20260929`'s -2.05. All five
entries went out and each was canceled after the 60 s entry timeout with no fill; the broker lists all five
`canceled` with 0 filled. The engine reports a reconciled, flat end with 0 open orders, no session error and 0 fills
as `completed_no_signals` (`runner.py:1945-1946`), which the freeze counts as a pass.

| Symbol | Entry order | Reference ask | Outcome |
|---|---|---|---|
| SSTI | 100, limit 8.28 | 8.24 | canceled (`entry_timeout`), 0 filled |
| BKYI | 100, limit 3.10 | 3.09 | canceled (`entry_timeout`), 0 filled |
| BEG | 17, limit 56.36 | 56.08 | canceled (`entry_timeout`), 0 filled |
| IOVA | 68, limit 14.52 | 14.45 | canceled (`entry_timeout`), 0 filled |
| BEX | 24, limit 40.60 | 40.40 | canceled (`entry_timeout`), 0 filled |

**Trial 2.** The scan fired 7 symbols: BKYI, IOVA, BEX and BEG entered; SSTI was skipped with `spread_exceeds_cap`.
Gross budget 4,989.04 USD. At 16:18:14 ET the engine forced all four legs out with `controller_stop`.

| Symbol | Entry | Exit (`controller_stop`) | Realized |
|---|---|---|---|
| BKYI | 100 @ 3.0996, limit 3.11, 7 fills | 100 @ 3.06, limit 3.05, 3 fills | -3.96 |
| IOVA | 68 @ 14.50, limit 14.57, 1 fill | 68 @ 14.47, limit 14.40, 4 fills | -2.04 |
| BEX | 24 @ 40.30, limit 40.59, 1 fill | 24 @ 40.17, limit 39.97, 1 fill | -3.12 |
| BEG | 17 @ 55.94, limit 56.37, 1 fill | 17 @ 55.64, limit 55.37, 2 fills | -5.10 |

**Trial 3.** The scan fired 8 symbols. BKYI and BEX entered; IOVA, NCPL and SSTI were skipped with
`entries_not_enabled`. Gross budget 4,974.82 USD. At 16:21:14 ET the engine forced both legs out with
`controller_stop`.

| Symbol | Entry | Exit (`controller_stop`) | Realized |
|---|---|---|---|
| BKYI | 100 @ 3.11, limit 3.12, 3 fills | 100 @ 3.12, limit 3.11, 1 fill | +1.00 |
| BEX | 24 @ 40.36, limit 40.56, 1 fill | 24 @ 40.20, limit 40.00, 1 fill | -3.84 |

**Trial 4.** The scan fired 8 symbols. BKYI, BEX and IOVA entered; NCPL was skipped with `spread_exceeds_cap` and
SSTI with `no_fresh_quote`. Gross budget 4,971.98 USD. At 17:08:39 ET the engine forced all three legs out with
`transport_gap`; the recover command sold BEX; IOVA stayed open
([Errors](#errors-rejects-and-retries)).

| Symbol | Entry | Exit | Realized |
|---|---|---|---|
| BKYI | 100 @ 3.09, limit 3.10, 3 fills | 100 @ 3.09, limit 3.08, 1 fill (`transport_gap`) | 0.00 |
| BEX | 24 @ 40.37, limit 40.57, 2 fills | engine exit (limit 40.21) reserved, never sent; recovery 24 @ 40.44, limit 40.42, 2 fills | +1.68 |
| IOVA | 68 @ 14.46, limit 14.53, 1 fill | no engine exit (no fresh quote); recovery exit (limit 14.38) refused before HTTP | open, cost 983.28 |

`entries_not_enabled` is the leg's last wait reason when the 30 s entry window closed: the engine's per-tick entry
enable was false whenever the leg was evaluated. The receipt does not record which enable condition was false.

### Frozen acceptance per trial

The freeze (`FREEZE.md`, private, sha256 `c72bbfedf528…`) fixed the pass before the run, "the same operational pass
as `ext-20260928`, plus no HTTP 429": status `passed` or `completed_no_signals`; flat; `cash_match` and
`positions_match` true; 0 open orders; `pnl_consistent` true; no duplicate or unexplained effects; no halt.
"Anything else is recorded as `needs_attention` or failed, with its reason." `receipt.json` quotes the clause text
(`frozen_acceptance`) and holds each trial's clause values (`attempts[].acceptance`).

| Clause | Trial 1 | Trial 2 | Trial 3 | Trial 4 |
|---|---|---|---|---|
| status `passed` or `completed_no_signals` | `completed_no_signals` | `passed` | `passed` | **`needs_attention`** (paper and recover) |
| flat | yes | yes | yes | **no**: IOVA 68 |
| `cash_match`, `positions_match` | true, true | true, true | true, true | not evaluable: no end reconciliation (the recovery's snapshot before the BEX sale: true, true, 2 positions) |
| 0 open orders | 0 | 0 | 0 | not evaluable: no end reconciliation (0 at the recovery's snapshot and in the ledger) |
| `pnl_consistent` | true | true | true | **false** |
| no duplicate or unexplained effects | 0 duplicates; 5 of 5 orders agree | 0; 8 of 8 | 0; 4 of 4 | 0 duplicates; 4 of 4 and the recovery's 1 of 1 agree; the 2 unlisted intents were never sent (`submit_attempted` 0) |
| no ledger halt (`halted_reason`) | null | null | null | **`recovery_only`** |
| no HTTP 429 (HTTP observations; 33 scan pages each) | 0 in 38 | 0 in 151 | 0 in 31 | 0 in 351 |
| **Verdict** | **pass** | **pass** | **pass** | **needs_attention** |

Trial 4's verdict rests on the four failed clauses (status, flat, `pnl_consistent`, halt), not on the three it
cannot evaluate. `recovery_only` is the latch the engine sets when a recovery begins (`safety.py:563-581`), not a
loss cap. The freeze accepted this path as a known effect ("a residual can stay open overnight", #215 part 2 and the
run-loop stall), which explains the residual but does not make the trial a pass.

Recorded, not thresholded, as the freeze asks:
- **Fills and slippage.** 29 of 33 fills were at the order's reference quote (the ask for a buy, the bid for a sell),
  4 were better and 0 worse. The better ones were all trial 2 entries: BKYI (2 of 7 fills, average 3.0996 against a
  3.10 ask), BEG (55.94 against 56.09) and BEX (40.30 against 40.39). The recovery's 2 BEX fills were at the bid,
  40.44.
- **Exit reasons.** `controller_stop` for the 4 legs of trial 2 and the 2 legs of trial 3, `transport_gap` for the 3
  legs of trial 4.
- **Realized P&L.** -15.38 USD for the series, with IOVA 68 still open at a cost of 983.28 USD. Fees are excluded:
  account 2's fees for the day, -0.47 USD, cover `pre-20260929` and this series together and cannot be split between
  them; the two series' joint realized P&L is -17.43 USD before fees and -17.90 USD including them
  ([Series totals](#series-totals)).
- **Quote-freshness waits and stream gaps.** Trial 4 skipped SSTI with `no_fresh_quote`, and its IOVA exit waited on
  `no_fresh_quote` until the handoff. Trials 2, 3 and 4 each logged one data-stream gap line.
- **Websocket reconnects.** Trial 1 logged one data-stream and one trading-stream restart line, trial 2 one and two,
  trial 3 one and one, trial 4 two and three. alpaca-py logs every websocket exception this way, clean closes
  included (`websocket_lines` in `receipt.json`).
  - All 5 data-stream lines read `sent 1000 (OK); no close frame received`: the client sent close code 1000 but no
    close frame came back, which websockets 17.1 raises as `ConnectionClosedError` (the closing handshake did not
    complete).
  - Of the 7 trading-stream lines, 5 read `sent 1000 (OK); then received 1000 (OK)`, a completed closing handshake.
    One line in trial 2 and one in trial 4 read `no close frame received or sent`: no close frame either way.
  - So `websocket_lines_without_close_frame` is 1, 2, 1 and 3, and the subset with no close frame either way
    (`websocket_lines_no_close_frame_either_way`) is 0, 1, 0 and 1. The recover command's log for trial 4 adds one
    more data-stream line of the first kind.
  - The logs carry no timestamps. The 2026-09-23 isolation check's committed output recorded a completed
    trading-stream handshake and a data-stream line without a close frame only after the engine's `stop()`, 0.016 s
    and 0.018 s after it. It has no line with no close frame either way.
- **Benchmark refusals.** 0.
- **Request peaks.** 19, 22, 20 and 21 requests in the busiest 60 s (cap 150); 5, 4, 2 and 3 submits (cap 130). The
  lowest `x-ratelimit-remaining` in the receipts was 190 of 200.
- **Planned versus realized gross.** The engine's leverage multiple was 1 in every trial, and the gross budgets were
  4,989.04, 4,989.04, 4,974.82 and 4,971.98 USD. Buy notional was 0.00, 3,214.14, 1,279.64 and 2,261.16 USD, which
  is 0.000, 0.644, 0.257 and 0.455 of each trial's sizing equity.
- **Average-invariant mismatches.** 0.
- **`paper_compare.py`.** Not run (decision 11: the tool is not checked against `b528bb55` receipts).

## Series totals

- 22 orders submitted by the engine: 14 entries (trial 1's 5 canceled unfilled, 9 filled) and 8 exits (7 filled;
  trial 4's BEX exit was reserved but never sent). The 21 that reached the broker were all `limit`, `day`,
  `extended_hours` true, and ended 16 `filled` and 5 `canceled` in the engine, the ledger and the broker listing.
- The recover command reserved 2 exits: BEX 24, filled, and IOVA 68, refused before HTTP.
- 33 fill events, and 2 more in the recovery (35).
- Realized P&L -15.38 USD: 0.00, -14.22, -2.84 and +1.68 by trial. Trial 4's +1.68 is the recovery's BEX sale
  (40.44 against a 40.37 entry); its paper stage realized 0.00 on BKYI. The engine receipts of trials 1 to 3, the
  ledger (lifetime -17.43 less `pre-20260929`'s -2.05) and the broker recompute agree.
- Open at the series end: IOVA 68, bought at 14.46 (16:25:48 ET), cost 983.28 USD. Its mark-to-market at the series
  end is not recorded.
- Cash flow -998.66 USD: the broker's sells minus buys, -1969.22 under the series prefix and +970.56 under the
  recovery prefix. That is the realized -15.38 less the IOVA cost.
- Gross loss 18.06 USD, the sum of the losing legs: trial 2 BKYI -3.96, IOVA -2.04, BEX -3.12 and BEG -5.10, and
  trial 3 BEX -3.84. The ledger's realized loss, 113.06, is this plus `pre-20260929`'s 95.00.
- The ledger at the series end (the 2026-09-30 09:08Z snapshot holds no request or event after 17:11:14 ET):
  lifetime realized -17.43, realized loss 113.06, cash delta -1000.71, peak P&L 0.00, `halted_reason`
  `recovery_only`, and IOVA 68 at cost 983.28. At trial 4's paper end the engine's gross loss was 117.14 and its
  drawdown 23.19, against budgets of 480 and 475; both include the open legs' unrealized loss at the bid.
- Fees are not in these figures. The broker posted three FEE activities for 2026-09-29 on account 2: REG -0.19, TAF
  -0.27 and CAT -0.01 USD, -0.47 in total. The frozen engine has no fee model.
  - Sources: the cash-gap output (`cash-gap-account2-20260930.json`, sha256 `c309e914…`) and the coordinator's
    FEE-activity read of 2026-09-30T18:13Z (`fee-activities-20260929.json`, sha256 `2d02c55b…`), a read-only GET on
    the paper endpoint whose record keeps no activity id. Both are private, under `<private state root>`, and list
    the same three activities.
  - They are day totals for `pre-20260929` and this series together; their bases, 8,820.73 USD of proceeds, 1,357
    shares in 38 sell executions and 81 executions, are all of account 2's executions that day. The broker posts one
    activity per fee type per day for the account, so its records cannot split the -0.47 between the two series, and
    this receipt makes no split.
  - The two series' joint realized P&L is -17.43 USD before fees (-2.05 in `pre-20260929` and -15.38 here), the
    ledger's lifetime realized at the series end, and -17.90 USD including them.

## Broker reconciliation (2026-09-30 09:06Z)

This was a fresh read-only read of account 2 by the trading-lane coordinator, GET requests only, on the paper
endpoint, in two runs of the same tool over the same window: one per client-id prefix. Their stdouts are kept
byte-identical as `reconcile-ext-20260929.stdout.json` and `reconcile-rec-ext-20260929.stdout.json`; the
private-detail check found nothing to redact.
- **Tool.** `reconcile_ext_series.py` from [`ext-20260928`](../ext-20260928/README.md) (sha256 `50b9da4c…`), cited
  by path and hash rather than copied. It ran from a byte-identical private copy with the pinned adaptive-paper
  interpreter; both stdouts record alpaca-py 0.44.0 and Python 3.12.3. The command lines are not recorded. The
  coordinator's brief routes the credential as `--env-file "$PAPER_ENV_FILE_2"` under `/bin/bash -ic`, and the tool
  requires `--env-file` and `--ledger` and prescribes passing both through shell variables, so that neither path
  appears on a recorded command line.
- **Window.** From 2026-09-29T20:00Z (16:00 ET) to 2026-09-30T00:10Z, prefixes `mvr-ext-20260929-` and
  `rec-ext-20260929-`.

The tool reads the ledger first (sqlite `mode=ro`), then the broker's orders (`status=all`), FILL activities (1
page), positions and open orders, and joins them in memory:
- 22 orders were listed in the window: 21 with the series prefix and 1 with the recovery prefix. Each run counts the
  other's as orders without its prefix, so there were 0 foreign orders.
- There were 35 FILL activities: 33 joined to series orders and 2 to the recovery's, none foreign. All 35 ledger
  executions match an activity on `cum_qty`, `qty` and `price`, and also on execution id. The largest time
  difference was 0.003 s.
- **0 unconfirmed fills.** Any ledger execution without a matching activity would have been listed as unconfirmed.
- All 21 series orders and the recovery's 1 agree with the ledger intents on symbol, side, quantity, limit, final
  status, filled quantity and average price.
- The broker lists neither of the two intents the ledger marks `not_sent`, `mvr-ext-20260929-4-0000005` (BEX) and
  `rec-ext-20260929-4-0000002` (IOVA). Both have `submit_attempted` 0 in the ledger.
- Sells minus buys from the broker's activities: -14.22 and -2.84 for trials 2 and 3 (trial 1 had no fill), -1952.16
  for trial 4, -1969.22 in total, and +970.56 for the recovery. Trials 2 and 3 ended flat, so their figures are
  realized P&L and equal the engine and ledger figures. Trial 4's -1952.16 plus 970.56 is -981.60, which is its
  +1.68 realized less the 983.28 USD IOVA cost.
- At the time of the read: 1 position, IOVA, which is also the ledger's only nonzero position, and 0 open orders.

The read is separate from the engine code and ledger writer. It uses the same broker API and account, so it is
independent of the engine but not of the broker.

## Errors, rejects and retries

- **Trial 4: forced exits and handoff.**
  - At 17:08:39 ET the engine forced BKYI, IOVA and BEX out with `transport_gap`: its loop found a transport health
    reason other than a stale quote (`mover_runner.py:304-306`). The engine log has one line "no data received on
    data stream for 30.0s, reconnecting", from alpaca-py's data websocket; the logs carry no timestamps.
  - BKYI's exit went out at 17:08:42 ET (bid 3.09, limit 3.08) and filled 100 at 3.09 at 17:08:43 ET. IOVA's exit
    was never submitted: its exit wait reason at the end was `no_fresh_quote`. BEX's exit (bid 40.41, limit 40.21)
    was reserved in the ledger at 17:09:12 ET but never reached the durable request budget (no request row,
    `submit_attempted` 0).
  - At 17:09:13 ET, 30 s after the BKYI fill with no further fall in the held quantity (3 exit timeouts of 10 s,
    `mover.py:1276-1292`), the engine handed off to recovery with `no_exit_progress`.
- **Trial 4: the recoveries on 2026-09-29.**
  - The paper stage's own forced recovery (`mover_runner.py:783-787`) started at 17:09:13 ET. It marked the BEX exit
    `not_sent` (`recovery_proven_never_attempted`) and ended with a `TransportError` before any broker snapshot and
    without an exit attempt; the receipt records only the exception type. `paper` ended rc 3 at 17:09:47 ET.
  - The recover command began its recovery at 17:10:04 ET, after 12 reads at 17:09:48 ET. Its snapshot showed
    `cash_match` and `positions_match` true with BEX 24 and IOVA 68 and 0 open orders. It sold BEX 24 at limit 40.42
    (the bid, 40.44, less 0.02); both fills were at 40.44 at 17:10:09 ET, +1.68 against the 40.37 entry.
  - The IOVA exit came 64.4 s after the BEX sale filled: recovery exits a held symbol only on a fresh quote, and the
    IOVA quote it used is stamped 17:11:14.023 ET. It reserved IOVA 68 at limit 14.38 (the bid, 14.40, less 0.02) at
    17:11:14.044 ET, and the transport refused it before any HTTP request. The ledger marks it
    `transport_proven_not_sent`, and the recover receipt records the error `SubmissionNotSent`. `recover` ended rc 3
    at 17:11:31 ET and the series stopped, holding IOVA 68.
- **Why the IOVA sale was refused: what the files can and cannot exclude.** The refusal's reason is not recorded.
  The transport raises `SubmissionNotSent("submission prevented before HTTP request")` for any exception in its
  submit hooks (the budget hook, then the wire guard) and for a deferred budget (`transport.py:804-818`), and the
  recovery keeps only the exception type. The discriminator is the durable budget (`safety.py:1299-1311`): it
  writes the request row and sets `submit_attempted` in one transaction, or returns a delay without writing only
  when the prior 60 s hold 150 requests or 130 submits. The IOVA intent has `submit_attempted` 0 and no request
  row; the ledger's last request is the BEX sale's submit at 17:10:09.024 ET, and the 60 s before the IOVA
  reservation hold 0 requests. So:
  - **Excluded:** the 150 and 130 per-minute caps (0 requests in the prior 60 s cannot defer; from the recover
    command's recovery start (17:10:04 ET) to the IOVA reservation the ledger holds 4 reads and 1 submit); the
    transport wire guard, which runs only after a durable reservation (`transport.py:1173-1179`); the order-contract
    gates, which record `order_contract_refused` instead; the recovery's own exit-budget guard, which would end the
    recovery with its own error code; and `validate_pending`'s session, window, outstanding-order and owned-position
    checks, which the recorded state passes. `validate_pending` checks no price bound for a sell.
  - **Not excluded:** `validate_pending`'s quote check (`quote_not_fresh`, `safety.py:658-662`), since the quote was
    0.021 s old at the reservation but the refusal's time is not recorded; and the transport's 0.25 s deadline for
    the submit hook (`transport.py:1148-1167`), which is sanitized the same way. The files cannot distinguish these
    two. The deadline is a path in the source beyond the two candidates the coordinator's brief named
    (`validate_pending` in `Controller.before_request`, and the transport wire guard).
- **`controller_stop` in trials 2 and 3.** At 16:18:14 and 16:21:14 ET the engine's loop found its stop flag already
  set. The receipts do not record what set it.
  - Setters in the source: the 30 s reconciliation, when the transport health after its snapshot holds a reason
    without "stale" (`mover_runner.py:323-335`; a stream close adds one, `transport.py:1129`); a mark-to-market
    failure; a broker refusal; an external order; or a SIGINT or SIGTERM.
  - Excluded: a broker refusal (no `broker_refused` intent, 0 rejections), an external order (0 foreign orders, no
    ledger freeze or halt) and a mark-to-market failure (it carries its own force reason).
  - Not excluded: the reconciliation's health stop and a signal. Each of the two engine logs has one data-stream gap
    line, so a data-stream disconnect is consistent with the stop, but that is inferred, not measured.
- **Trial 1's cancels.** The 5 cancels are trial 1's entry timeouts, each answered by the broker with HTTP 204 and
  confirmed as `canceled` with 0 filled.
- **Rejects and other engine errors.** None. There were no native rejections or pre-wire refusals, and no adapter
  errors, callback faults, average-invariant mismatches or duplicate executions. No fill gap was open at stop. The
  halt seeds held 42 items each, none halted. These figures come from the engine receipts alone
  (`field_provenance`).
- **Retries.** None. Every trial started on its first attempt, with no `benchmark_quotes_not_ready` refusal.
- **HTTP.** 0 HTTP 429 and no transport `rate_limited` mark. The receipts hold 38, 151, 31 and 351 HTTP
  observations, all 200 except trial 1's five 204 cancels, and every scan's 33 pages returned 200.
- **Quote handling.** Crossed quotes were dropped and counted: 24 (20 of them SPY), 37 (34 SPY), 0 and 34 (18 BKYI,
  16 SPY).
- **Request counts.** From each trial start the ledger holds exactly the engine-reported requests: 17 reads, 5
  submits and 5 cancels; 132 reads and 8 submits; 16 and 4; and 336 and 4.

## Residual recovery on 2026-09-30

The pre-market recovery of the IOVA 68 residual (`paper-recover-a2-pre-20260930`) made 17 attempts from 06:00:05 to
06:51:39 ET and sent 0 orders. Each attempt ended `needs_attention` with the error `cash_mismatch_or_unmodeled_fees`.
The broker posted three FEE activities for 2026-09-29 on account 2: REG -0.19, TAF -0.27 and CAT -0.01 USD, as both
the cash-gap output (`cash-gap-account2-20260930.json`, sha256 `c309e914…`) and the coordinator's FEE-activity read
(`fee-activities-20260929.json`, sha256 `2d02c55b…`) record ([Series totals](#series-totals)). Broker cash minus the
trial's baseline cash minus the ledger's execution cash flow, from the cash-gap output, is -0.47 USD, exactly their
sum. The frozen engine has no fee model, and its reconciliation fails closed on a cash difference above 0.01 USD
(`runner.py:761-763`). `receipt.json` holds these facts (`residual_recovery_20260930`, status `pending`).

PENDING: final disposition filled in by the coordinator after the engine fee fix and its recovery

## Deviations from the freeze

None found.
- The config sha256 matched in every `check.json` and engine receipt.
- The series scripts were unchanged. `series-driver.sh`, `run-series-trial.sh` and `retry-benchmark.sh` predate the
  freeze files, and their sha256 on 2026-09-30 equals the table in the private series index (written 05:20:57Z).
  `FREEZE.md` names the driver arguments and `retry-benchmark.sh` but hashes no script.
- Every start came from the timer and the driver, no trial needed a retry, and the series stopped on the freeze's
  failed-recovery rule.
- The driver's pass rule (engine status `passed` or `completed_no_signals`, or a passed recovery, and no 429) does
  not read the ledger halt that the freeze's stop rules and acceptance name. Here the `recovery_only` halt came with
  a failed recovery, which the driver's rule catches.
- The IOVA residual was handled as the freeze's boundary disposition provides: it stays open and is recorded, and
  `recover` ran again at the next pre-market. The disposition does not make trial 4 a pass.

## Units (systemd user journal and manager)

| Unit | Start (UTC) | Stop (UTC) | Result |
|---|---|---|---|
| `paper-ext-20260929` | 20:00:05 | 21:11:31 | exit status 3 (`exit-code`), in the journal and the manager; OnFailure alert sent |
| `incentive-monitor-20260929` | 07:55:00 | 00:00:14 (09-30) | `success`, exit status 0 (manager); no journal exit record |

The journal was queried on 2026-09-30 with `journalctl --user -o json USER_UNIT=<unit>.service` (systemd 255), and
the systemd user manager with `systemctl --user show` at 18:57Z.
- The series unit has an exit record (`EXIT_STATUS` 3, the driver's "series stopped" code) and a result record
  (`exit-code`), and the manager holds the same (`Result=exit-code`, `ExecMainStatus=3`). It triggered its OnFailure
  alert unit (`paper-alert@%n.service`), which ran 17:11:31-17:11:37 ET and posted to the ntfy `paper-lane` topic.
- The incentive monitor has start records and a resource-accounting record only. The manager still held its result:
  `Result=success`, `ExecMainCode=1` (the process exited on its own) and `ExecMainStatus=0`. The manager has run
  since 2026-09-24, so both are the runs' own results, but a manager restart would clear them.
- The unit and timer files are hashed in `receipt.json`, and each hash matches the private series index.

The incentive monitor ran on account 2's key pair and is data only. Its docstring says it never places, changes or
cancels an order, and the broker listing shows no order outside the series and recovery prefixes in this window.

## Limitations

- **Metadata plus broker-reconciled evidence, not a frozen gate run.** It qualifies no gate. Unconfirmed fills
  would have been marked unconfirmed; there were none.
- **Simulated fills.** Alpaca paper fills are simulated from quotes. They say nothing about live slippage, queue
  position or partial fills.
- **Not a strategy evaluation.** Four trials in one after-hours session evaluate no strategy, and the protocol has no
  validated edge. In POST the scanner selects the day's 10:00 movers, not after-hours catalysts.
- **Unrecorded causes.** The IOVA refusal's reason is not recorded; the files narrow it to two paths they cannot
  distinguish. What set trials 2 and 3's `controller_stop` is not recorded either.
- **Recovery evidence.** The 2026-09-30 09:08Z ledger snapshot predates the 06:00 ET recovery attempts, so their 0
  orders rest on the 17 attempt receipts and the recovery console, not on the ledger.
- **Account designation.**
  - The series kept its own engine ledger, the account-2 root it shares with `pre-20260929`.
  - It traded broker account `alpaca-paper-2`. Two records designate that account as the isolated
    incentive-monitor study account:
    [`forward-protocol-v1.json`](../../../incentive-monitor/forward-protocol-v1.json) (line 63) and
    [docs/secret-storage.md](../../../../../docs/secret-storage.md) (line 17).
  - Whether this use fits the forward study's isolation is referred to the forward protocol's owner, the trading
    lane. This receipt does not decide it.
- **Fees.** The frozen engine has no fee model. The REG, TAF and CAT fees posted for 2026-09-29 (-0.47 USD in total
  on account 2) are outside every figure here except the joint fee-inclusive figure, -17.90 USD for
  `pre-20260929` and this series together. The broker's records cannot split them between the two series.
- **Single-source fields.** Some figures come from one source only. Examples are the halt seed counts, the
  crossed-quote drops, the websocket lines, the preflight fields, the HTTP observations, the in-process recovery's
  error and the ledger's peak P&L. `receipt.json` `field_provenance` lists every field as asserted across sources,
  single source, derived or literal.

## Paper lane row

The grand-dashboard `paper` lane, "Alpaca paper accounts 1 and 2", cites [`ext-20260928`](../ext-20260928/README.md)
at this branch's base. Pointing it at the 2026-09-29 receipts is the coordinator's step; this branch does not touch
the dashboard. For account 2 this receipt supports a POST series on 2026-09-29 with 3 of 4 trials passed (trial 1
with no fill) and trial 4 `needs_attention`. Account 2 ended the day holding IOVA 68 (cost 983.28 USD), still held at
the 2026-09-30 09:06Z read, and its ledger is at `recovery_only`; the residual's recovery is pending.

## Files

| File | What it is |
|---|---|
| `receipt.json` | The series receipt: code identity, config, frozen acceptance and per-trial verdicts, per-attempt results, 22 engine orders and 2 recovery orders, the trial 4 recoveries and the refusal analysis, the pending residual recovery, broker reconciliation, units, totals, field provenance, and hashes of the committed copies and of retained private files that carry no account fingerprint |
| `README.md` | This summary |
| `reconcile-ext-20260929.stdout.json`, `reconcile-rec-ext-20260929.stdout.json` | The independent broker reconciliation's two stdouts (series and recovery prefix), byte-identical; the tool is cited by path and sha256 |
| `frozen-b528bb55.SHA256SUMS` | The freeze's hashes of the 70 engine, scanner, order-contract and incentive-monitor files, byte-identical |
| `mover-paper-1.json` to `mover-paper-4.json` | Engine receipts of trials 1 to 4. Each `broker_order_ref` value (5, 8, 4 and 4) is replaced by `withheld` (trial 4's never-sent BEX exit has a null ref, kept null); every other byte is unchanged |
| `mover-recovery-4.json` | The recover command's receipt for trial 4, byte-identical (it holds no broker order ref) |
| `series.console` | The series console (run log), byte-identical |

Private and not committed:
- the freeze note, which names a private host path (the account-2 state root's full path), and the private series
  index, which names account fingerprints (both cited by sha256);
- the config file and rule file, whose content is in `receipt.json`;
- the scan, check and synthetic files, the engine logs and events, and the scan page ledgers and caches;
- trial 4's recover log, the 2026-09-30 recovery plan, outcome note, attempt receipts, logs and console (hashed);
- the cash-gap output and its tool (hashed);
- the coordinator's FEE-activity read (hashed);
- the series scripts and the systemd units (hashed);
- the engine ledger and its snapshot;
- the NautilusTrader logs.
