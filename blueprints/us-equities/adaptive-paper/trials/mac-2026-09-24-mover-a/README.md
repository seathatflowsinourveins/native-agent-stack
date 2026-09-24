# Mover paper trial on macOS, 2026-09-24 12:45 ET: first broker run, `needs_attention` on a fill-precision stop

The first Alpaca paper run of the mover trial mode (`README-mover.md`). Host `macos-m5pro-20260924` (Apple M5 Pro,
macOS 26.5.1), this Mac's own paper account (no other host trades it), SIP feed. It is **mechanics-only**: the
protocol `mover-early-entry-v1-20260924` validated no rule (v1: 0 of 768 rule-exits passed development), so its
paper candidate is the most-traded development rule, `10:00|G0.20|V250000|any`, which is expected to lose after costs.

Everything in `FREEZE.md` was fixed before any broker I/O: the source, runtime, config, rule, deviations, numeric
bounds and acceptance. Deviations from the candidate: the 10:00 rule was scanned at trial start, entries followed at
trial start instead of 10:00, and exit X2 (60 minutes) replaced the candidate's X1 because the engine bounds a hold
at about 70 minutes.

## Source and runtime

- A read-only `git archive` of main `3699012` (`blueprints/us-equities`, leaving out `mover-v3/`).
  `frozen-3699012.SHA256SUMS` lists its 562 files.
- CPython 3.12.14 (uv) with the #176 lock `evidence/artifacts/macos-syn-e2e-20260924/requirements-macos-arm64-py312.lock`
  (sha256 `d756583b…`): nautilus-trader 2.0.0rc5, alpaca-py 0.44.0, numpy 2.5.3; 20 of 20 packages, `uv pip check` passed.
- Offline gates before the run, in that runtime: 743 adaptive-paper tests (1 skip by design; the 3 metrics-server
  tests that bind a loopback port errored inside the sandbox and passed outside it, 23 of 23), 25 scanner and
  native-fault tests, and `mover_runner.py synthetic` with this config (passed, flat).
- `config-mover-mac-20260924a.json` (sha256 `13688ae0…`) is `config-mover.json` with only `mover.rule`,
  `session_scope`, `trial_end_et`, `exit` and `notes` changed. `run-trial.sh` is the wrapper that ran
  `mover_scan.py`, `mover_runner.py check` and `mover_runner.py paper --allow-shared-account`.

## Run

`mover_scan.py` ran at 12:44:56 ET and took 7 s: 11 symbols met the rule, and the top five by dollar volume became the
universe (`scan.log`; the scan files stay private, and `scan.sha256` records their hashes). The regime factor was 1.
`check` passed, and `paper` started at 12:45:03 ET.

| Symbol | Qty | Entry (priced on ask) | Exit | Exit reason | P&L (USD) |
| --- | ---: | --- | --- | --- | ---: |
| APUS | 35 | 5.71 (ask 5.69, +35 bps) | 5.29 at the bid | X2, 13:45:06 | -14.70 |
| PFSA | 71 | 2.77 (at the ask) | 3.07 | recovery, 13:45:23 | +21.30 |
| SRZN | 6 | 31.81 (at the ask) | 31.52 | recovery, 13:45:24 | -1.74 |
| GRML | 13 | 15.19 (at the ask) | 15.001538 average (15.00 x 11, 15.01 x 2) | X2, 13:45:08 | -2.45 |
| GCTK | 77 | 2.58 (at the ask) | 2.56 at the bid | X2, 13:45:07 | -1.54 |

All five entries filled within 26 s of the start. Realized P&L was **+0.87 USD** on 983.51 USD bought. The receipt,
the durable ledger (`ledger-readback.json`) and the broker's cash change agree on this figure.

## What stopped the native loop

GRML's X2 sell filled in parts: 11 shares at 15.00, then 1 at 15.01, then 1 at 15.01. Alpaca reported the
cumulative average rounded to six decimals, 15.000833 after 12 shares. The native adapter derived the last share's
price from two cumulative snapshots, (12 x 15.000833 - 165) / 1 = 15.009996, which is not a 4-decimal price. It then
stopped as designed with `cumulative_fill_precision_requires_reconciliation`. That latched the force `adapter_error`
at 13:45:10.657 ET, 21 ms after the fill.

The force path worked as specified:
- one native exit, submitted while the adapter was stopping, was refused before the wire (`native_rejections: 1`);
- the native loop handed PFSA and SRZN to recovery (`recovery_started` 13:45:11);
- `official_sdk_recovery` sold both, and the account reconciled **flat**: `cash_match` and `positions_match` true,
  0 open orders.

`mover_runner.py recover` then took a fresh broker proof (`mover-recovery.json`: passed, flat, cash delta 0.87) and
returned the ledger to `finished`.

## Acceptance against the frozen criteria

- **Operational pass: not met.** The status is `needs_attention` because a forced recovery was needed.
- **Met:** flat at the end; cash and positions matched; `pnl_consistent`; no duplicate or unexplained broker effect;
  no ledger halt; the recover proof passed.
- **Request budget.** At most 23 trading requests and 5 submits fell in any 60 s window (511 requests in the trial,
  10 submits), against the configured 200 and 180 per minute. The paper tier's measured limit is 200/min; Alpaca
  Elite's Smart Router publishes 1,000/min.
- **Paper versus model.** `paper_compare.py` compares against the protocol's 10:00 entry. This trial's deviation
  (entry at 12:45) makes that comparison measure the deviation rather than fill quality, so it was not run. Fill
  quality against the quote each order was priced on is in `ledger-readback.json` (`fill_vs_quote_bps`).

Trial `mover-mac-20260924b` (X1, frozen at 12:46 ET before this trial's exits) did not start. Its frozen
precondition required this trial to end `passed` or `completed_no_signals`.

## Change that follows

`fills.resolve_execution` now gives the native adapter each fill's price:
- The trade-update event's own execution price, when the event's quantity equals the new shares. It must be on the
  grid and agree with the reported average.
- Otherwise, the one whole-tick notional within the average's reporting bound, divided into an on-grid price per share.
- Anything else still stops the adapter.

An independent pre-merge review from a different model family found the first version of this fix too narrow, and
its cases are now tests (`tests/test_adaptive_paper_fills.py`). The native tests reproduce this run's arithmetic and
fail on the previous adapter (`tests/test_adaptive_paper_native.py`). The same review found that the ledger's limit
check can halt falsely on rounded averages exactly at the limit. That check is unchanged here and tracked separately:
loosening it by the rounding bound would let a real one-tick violation pass on large orders.

## Records and their limits

- `verify_mover_trial.py .` re-checks these artifacts offline: config and scan hashes, flat state, reconciliation,
  the recover proof, and readback-versus-receipt totals.
- `mover_ledger_readback.py` read the durable ledger read-only. It leaves out broker order ids, the ledger path, the
  account fingerprint and cash balances. The NautilusTrader JSON log and `live/run.json` are not committed, because
  they hold account-scoped identifiers and local paths.
- `events.jsonl` is the run's `--live-dir` decision stream.
- The adaptive lane shares this account's state root (`--allow-shared-account`). Its next trial on this account will
  refuse with `next_trial_cash_mismatch` until the lanes use separate paper accounts.
- 2026-09-24 lies in the gap Mover v3 never reads (2026-09-21 to N0-1). The exposure is disclosed on #190.
- Alpaca paper fills are the broker's simulation, not exchange executions. This is pipeline evidence, not an edge.
