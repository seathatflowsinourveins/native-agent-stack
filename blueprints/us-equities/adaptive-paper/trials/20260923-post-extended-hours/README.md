# Adaptive paper after-hours trial, 2026-09-23 19:01 ET: first extended-hours run, stopped after 10.9 s (data-timeout path)

This is the first paper run of the extended-hours session path, the `sessions` block that `sessions.validate_session_policy`
enforces. It ran from a read-only `git archive` of main `40828dfe`; all 452 hashes in `frozen-40828dfe.SHA256SUMS`
match `git archive 40828dfe -- blueprints/us-equities`. It used `scheduled_trial.sh` with `LIVE_DIR` set.

Config: `config-post-liquid-9967f44d.json` (sha256 `9967f44d5ec2…`). Its `notes` field names "config-sip.json
77244c39"; that means the durable ledger's frozen copy (see trial 20260923j), not the repository's `config-sip.json`
(`3587653104e6…`). Compared with the durable ledger's `77244c39` config:
- the risk limits are the same (1x, 1-share orders, 25 USD loss and drawdown, 3 s quote age, 15 bps spread) except
  `max_held_symbols`, which is 4 instead of 10 to match the 4-symbol universe;
- `sessions.extended_hours` is true, with `regular_session_only` false and `extended_hours_enabled` true;
- the universe is QQQ, META, SPY and NVDA, with QQQ as the only regime benchmark.

The universe was narrowed because of the after-hours SIP quotes sampled read-only at about 18:50 ET: 8 samples 2.5 s apart,
24 configured symbols, 3 s limit.

| Symbol | Samples no older than 3 s | Median age | Max age | Median spread |
|---|---|---|---|---|
| QQQ | 8/8 | 0.9 s | 1.8 s | 0.5 bps |
| META | 8/8 | 0.9 s | 2.8 s | 1.3 bps |
| SPY | 3/8 | 4.6 s | 10.0 s | 0.5 bps |
| NVDA | 3/8 | 6.4 s | 13.3 s | 4.4 bps |
| IWM | 2/8 | 6.8 s | 16.0 s | 1.8 bps |
| DIA | 2/8 | 7.9 s | 15.5 s | 2.1 bps |

Of the other 18 symbols, none met the limit in more than 2 of 8 samples, and ten were never fresh. Their median ages
ranged from 6.5 s (CRWD) to 363 s (PG).

This trial used its own state root, because the durable ledger refuses any config change
(`next_trial_config_differs_from_frozen_limits`). It filled nothing, so the durable ledger still reconciles with the
broker.

Result (`paper-output.json`):
- Preflight: flat, no open orders, config sha matched. A separate read-only `runner.py preflight` run just before the
  trial returned `ready`; that output is not committed.
- Status `completed_no_signals`, rc 0, 10.9 s elapsed. 16 native quotes and 6 decisions, all regime `unavailable`
  because warm-up was not finished. No order was sent, and 1 crossed quote (META) was dropped.
- Reconciliation: `cash_match` and `positions_match` true, cash delta 0.00 USD, 0 open orders, 0 positions.
- `scheduled-trial.log` line 4 is `no data received on data stream for 3.0s, reconnecting`. That line comes from
  alpaca-py's data websocket (`alpaca/data/live/websocket.py`). `transport.py` passes `data_timeout=quote_timeout`,
  which is the config's 3 s quote age, and a close marks the quotes stream disconnected. Once the strategy has
  started, the runner stops on any freeze reason other than stale quotes. The result is consistent with that path:
  a 3 s pause across all four symbols, a reconnect, then a stop. `paper-output.json` records neither the freeze
  reason nor whether the strategy had started, so the cause is inferred, not measured. The `trading stream websocket
  error` on line 5 is the shutdown close seen in earlier trials.

Finding: the engine, as built, trades only in the regular session.
- `RiskLimits` caps `quote_max_age_seconds` at 3 s.
- The alpaca-py data timeout equals that quote age.
- Preflight requires every benchmark quote to be no older than it.

After hours, those assumptions fail on real quote cadence. Trading pre-market or after hours needs a session-aware
liquidity design: a per-session quote age, data timeout and benchmark basket, with its own preregistered limits, tests
and independent review, which in turn needs a limits decision. It is not a configuration flag. Until then, the
extended-hours path is not qualified on paper.
