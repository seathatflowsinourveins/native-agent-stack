# Leverage-ladder 1x attempt, 2026-09-24 15:27 ET (needs_attention)

This is the first native attempt at the `leverage-ladder-1x` rung. It is retained
as a failed attempt. It is not a flip receipt: `../../ladder/1x/receipt.json` was
not written, and the gate stays `not_established`.

**Setup.**
- The run used the bounded run-once `scheduled_trial.sh` from a read-only
  `git archive` of main `3b7ae710` (after #197, #198 and #199).
  `frozen-3b7ae710.SHA256SUMS` lists all 584 files of
  `git archive 3b7ae710 -- blueprints/us-equities scripts/credential_status.py adoption/credential-inventory.json`.
- It ran `config-leverage-1x.json` (sha256 `2138f6f7...`) on the SIP feed against
  the WSL host's dedicated paper account. No account id, credential or host path
  is recorded.
- Trial id `ladder-1x-20260924a`. Started 19:27:31Z and ended 19:30:44Z, runner
  rc 3.

**Promotion gate.** A fresh snapshot passed the gate: 480 rows, sessions
2026-08-26 to 2026-09-23 (`ingest-receipt.json`, `gate-result.json`). The gate
runtime was missing on this host, so it was installed the same day at the path
`scheduled_trial.sh` expects. It came from `blueprints/us-equities/data/requirements.lock`
via `uv pip sync --require-hashes`, with uv 0.12.17 on CPython 3.13.15, and
resolved pandera 0.33.1, pandas 3.0.6, pyarrow 25.0.1, exchange_calendars 4.13.2
and duckdb 1.5.5.

## Result (`paper-output.json`)

**Status.** `needs_attention` after 189.96 s of the configured 300 s. The single
adapter error was `order_cumulative_fill_precision_requires_reconciliation`.

**Account.** Flat and reconciled: `cash_match` and `positions_match` true, 0 open
orders, 0 positions.
- Four orders, all filled.
- The engine reports 4 native fill events. The broker lists 5 fill activities,
  because the INTC sell filled 6 shares and then 1.
- Realized P&L: INTC +1.45 USD, AMD −0.25 USD, net +1.20. The engine's
  1.200001 carries the 0.000001 residue explained below.
- 37 crossed quotes were dropped: IWM 25, GOOGL 9, and one each for AMD, INTC
  and MU.

**Leverage.**
- `config_max_leverage` 1, `next_lower_rung_ceiling` 0.5.
- `peak_achieved_leverage` 0.1511, a peak gross exposure of $1,511.37.
- `seconds_above_next_lower_rung_ceiling` 0.
- Account multiplier 4, margin not used.

So this attempt misses the rung's flip condition on exposure as well as on
status.

## Why it stopped: a false-positive fill-precision refusal

The INTC sell was 7 shares with a limit of 126.31 (`ledger-readback.json`,
events 17 and 18):

1. Alpaca first reported `partially_filled`: 6 shares at an average of 126.33.
2. It then reported `filled`: 7 shares at an average of 126.327143, rounded to
   six decimals.
3. The adapter derived the last share's price as
   `7 x 126.327143 - 757.98 = 126.310001`. That is off the cent grid, so the
   adapter refused.

The broker's own FILL activities in the independent readback show executions of
6 at 126.33 and 1 at 126.31, both on the grid. The true price was 126.31, and
884.29 / 7 = 126.327142857..., which Alpaca rounds to 126.327143. The refusal was
therefore a false positive, and the run stopped with a correct flat
reconciliation.

This is the defect class that open PR #205 addresses (`fills.resolve_execution`,
first seen in a Mac mover-mode run). Here it reproduced natively on the WSL host
in the adaptive 1x lane. The sequence (6 at 126.33, then 7 at an average of
126.327143, expected last price 126.31) makes a concrete regression case for that
fix.

## Two further observations

Both come from this one run and are hypotheses to test, not conclusions.

**Regime availability.**
- The leverage ceiling was 0.0 for 98.3 s of the 189.2 s after the first
  decision: 48 of 93 decisions had `regime: unavailable`.
- The first 55.0 s were warm-up. The rest was repeated flapping between
  `range` and `unavailable`.
- `strategies_v1` marks the regime `unavailable` whenever any of the four
  benchmarks (SPY, QQQ, IWM, DIA) has no features. With `quote_max_age_seconds`
  3, a benchmark whose recent quotes were dropped as crossed can go stale. IWM
  had 25 of the 37 crossed drops.
- The decision events do not record which benchmark was missing, so IWM is the
  likely cause, not a proven one.

**Reachability.**
- Entries were INTC 7 ($883) and AMD 1 ($627), under the $1,000 per-order cap.
- `portfolio_rotation` sold them about 35 s and 6 s after their fills.
- The 1x rung needs more than $5,000 gross on $10,000 of capital, which means at
  least six concurrent positions of about $880.
- `README-safety.md` (F2) already states that a rung's configuration is an
  envelope, not a target. This run is consistent with that.
- A rung attempt that can meet the flip condition needs a policy or duration
  that holds enough positions long enough. That is the rung owner's design
  choice, and this record does not change it.

## Independent observation

`observe_ladder_trial.py` is a read-only alpaca-py 0.44.0 script on Python 3.12.3.
It is separate from the engine transport and ledger. It made these GETs:
- orders by the client-id prefix `adp-ladder-1x-20260924a-`;
- `/v2/account/activities/FILL` joined to those orders;
- positions;
- open orders.

It ran at 19:33:47Z. Its stdout is retained byte-identical as
`observe-ladder-trial.stdout.json`; stderr was empty and the exit code 0. It saw
4 orders, all `filled`, with the same quantities and average prices as the
engine ledger. It saw 5 fill activities (above), 0 positions and 0 open orders.
It uses the same broker API and account, so it is independent of the engine code
but not of the broker.

## Files

| File | What it is |
|---|---|
| `paper-output.json` | Engine output, copied unchanged |
| `scheduled-trial.log` | The run-once script's log, copied unchanged |
| `ingest-receipt.json` | Promotion-gate input, copied unchanged |
| `gate-result.json` | Promotion-gate result, copied unchanged |
| `frozen-3b7ae710.SHA256SUMS` | Hashes of the frozen tree the run used |
| `ledger-readback.json` | Read-only query (`mode=ro`) of the run's engine ledger (intents and events), with broker order ids removed |
| `observe_ladder_trial.py`, `observe-ladder-trial.stdout.json` | Independent broker readback: the script and its stdout |

The universe snapshot CSV and the NautilusTrader JSON log stay private.
