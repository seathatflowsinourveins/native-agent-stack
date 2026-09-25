# Adaptive paper 1x trial on macOS, 2026-09-24 10:23 ET: second-host pass

Host `macos-m5pro-20260924` (Apple M5 Pro, macOS 26.5.1 build 25F80, arm64), the second physical machine after the
WSL2 workstation that ran trial `20260923g`. Same procedure and limits as that gate receipt: the bounded run-once
`scheduled_trial.sh`, the frozen `config-sip.json` (sha256 `3587653104e6…`, the same bytes as trial g), 1x cash, SIP
feed, one-share orders, 300 s plus 120 s cleanup, at most 180 submits and 200 trading requests per minute.

Source and runtime:
- A read-only `git archive` of main `6f7a77c` (`blueprints/us-equities`, leaving out `mover-v3/`, which the engine
  does not use). `frozen-6f7a77c.SHA256SUMS` lists all 526 files; every hash matches the worktree at `6f7a77c`.
- CPython 3.12.14, uv 0.12.18. The engine environment came from the #176 lock
  `evidence/artifacts/macos-syn-e2e-20260924/requirements-macos-arm64-py312.lock` (sha256 `d756583b…`, 20 packages:
  nautilus-trader 2.0.0rc5, alpaca-py 0.44.0, numpy 2.5.3, pandas 3.0.6). The promotion gate had its own environment
  from `blueprints/us-equities/data/requirements.lock` (21 packages: pandera 0.33.1, pyarrow 25.0.1,
  exchange_calendars 4.13.2, duckdb 1.5.5). Both were installed with `uv pip sync --require-hashes`. Each environment
  matched its lock exactly (20 of 20 and 21 of 21 packages), and `uv pip check` passed for both. The gate's README
  records CPython 3.13.15; here it ran on 3.12.14.
- macOS has no GNU `timeout`, so the script ran unchanged with `macos_timeout.py` first on `PATH` as `timeout`. It
  sends SIGTERM when the time runs out and exits 124. The copy here differs from the file that ran only in its
  shebang.
- The offline checks that gate broker execution passed first in this runtime: 732 adaptive-paper tests (one skip by
  design, `exchange_calendars` is not in the engine environment) and 17 native-faults tests.

Before the run, `runner.py preflight` (`preflight.json`) reported `ready`: the paper endpoint, account `ACTIVE`,
capital available, 0 open orders, 0 positions, and 24 of 24 assets and SIP quotes. The run's own preflight and
start gate found the same, and `ingest-receipt.json` / `gate-result.json` show 480 rows passing every gate check.
This was the first trial in this host's durable ledger (the engine's default state root).

Result (`paper-output.json`, `scheduled-trial.log`):
- Status `passed`, rc 0, 300.4 s elapsed. 149 decisions; `relative_strength` was selected 61 times.
- 33 submits (17 buys, 16 sells), 3 cancels, 50 reads. 30 native fill events, 0 rejections, 0 adapter errors.
  At most 10 submits and 24 trading requests fell in any 60 s window.
- 16 crossed quotes dropped: TSLA 6, INTC 4, CRWV 3, and one each for META, MSFT and QQQ.
- Three cancel-replaces, each after the 10 s order timeout (`ledger-readback.json`):
  - CRWV buy at 87.67 canceled, then re-entered at 87.76 and filled at 87.76.
  - CRWV exit sell at 87.70 canceled, then replaced at 87.56 and filled at 87.58.
  - META buy at 767.74 canceled, then re-entered at 768.58 and filled at 768.42.
- Reconciliation: `cash_match` and `positions_match` true, 0 open orders, 0 positions. Gross loss 1.79 and drawdown
  1.62 USD against the 25 USD limits. No halt.

Fifteen one-share round trips, from the durable ledger:

| # | Symbol | Buy fill | Sell fill | P&L (USD) |
|---|---|---|---|---|
| 1 | IWM | 280.57 | 280.54 | -0.03 |
| 2 | TSLA | 378.18 | 378.08 | -0.10 |
| 3 | QQQ | 737.45 | 737.25 | -0.20 |
| 4 | NVDA | 222.23 | 222.17 | -0.06 |
| 5 | META | 766.50 | 765.98 | -0.52 |
| 6 | INTC | 124.10 | 124.05 | -0.05 |
| 7 | CRWV | 87.76 | 87.58 | -0.18 |
| 8 | META | 767.57 | 767.04 | -0.53 |
| 9 | INTC | 124.11 | 124.09 | -0.02 |
| 10 | META | 768.42 | 768.38 | -0.04 |
| 11 | META | 768.28 | 768.29 | +0.01 |
| 12 | INTC | 124.16 | 124.34 | +0.18 |
| 13 | GOOGL | 339.74 | 339.68 | -0.06 |
| 14 | CRWV | 87.86 | 87.93 | +0.07 |
| 15 | INTC | 124.44 | 124.46 | +0.02 |

Realized P&L was −1.51 USD. The round trips, the ledger's realized P&L and the broker's cash change all agree on
this figure, so no unmodeled fee appeared.

Records and their limits:
- `ledger-readback.json` comes from `ledger_readback.py`, a read-only (`mode=ro`) read of this host's durable
  ledger. It leaves out broker order ids, the ledger path, the account fingerprint and every cash balance.
- `--live-dir` was set (observation only). Its NautilusTrader JSON log is not committed, because it contains
  account-scoped identifiers, balances and venue order ids.
- There is no separate broker readback file like trial g's `broker-orders.json`. Broker state is the engine's own
  reconciliation, recorded above.
- `verify_artifacts.py` re-checks, offline, the committed artifacts of this trial, the STOP drill and the
  native-faults run, and compares the frozen hashes with a fresh `git archive 6f7a77c`. The host receipt
  `evidence/hosts/macos-m5pro-20260924/macos-m5pro-20260924--alpaca-py--use--20260924.json` runs it.
- The paper account is shared with other hosts, and the engine's account lock is host-local. Any order this ledger
  does not own, seen in its history window, freezes a run (`external_order_detected`). None appeared. The
  native-faults harness ran before this trial (`../mac-2026-09-24-native-faults/`), so its SPY order predates this
  ledger's history window.

This shows real engine and broker order flow on a second physical machine: cancel-replace, reconciliation and cleanup
at 1x with 1-share orders over one 5-minute window. It is not evidence of strategy edge; Alpaca paper fills are
simulated. The kill-switch drill that followed in the same ledger is in `../mac-2026-09-24-b-stop-drill/`.
