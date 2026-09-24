# Adaptive paper 1x trial, 2026-09-23 11:59 ET: first passed real-engine trial

This trial ran from integration build `5e1d512`: Codex's stop-diagnostics build `1e2c96a` plus the three fixes in #123.
Those fixes drop crossed and one-sided quotes as untradable, refuse reconciliation only while an order event is queued,
and fit the fill TradeId to 36 characters. The run used the bounded run-once `scheduled_trial.sh` from a read-only
`git archive` copy (hashes in `frozen-5e1d512.SHA256SUMS`), with the frozen config `config-sip.json` at 1x.

Result (`paper-output.json`):
- Status `passed`, exit 0, with `decision_exit.reason` `duration_completed` after 300.1 s.
- 147 decisions. The regime moved from `unavailable` to `range`, and `relative_strength` was selected 17 times.
- 8 submits, 8 native fill events, 0 adapter errors and 0 native rejections.
- 13 crossed quotes were dropped (AAPL 3, CRWV 2, INTC 1, MSFT 4, QQQ 2, SPY 1). Before #123, any one of them would
  have ended the run.
- Reconciliation: `cash_match` and `positions_match` true, 0 open orders, 0 positions.
- Realized −0.29 USD, and gross loss 0.30 USD against the 25 USD limit.

Broker readback (`broker-orders.json`, read-only): four 1-share round trips. The fills match the engine's realized
figure.

| Symbol | Buy fill | Sell fill | Result (USD) |
|---|---|---|---|
| GOOGL | 340.70 | 340.56 | −0.14 |
| AAPL | 337.08 | 337.02 | −0.06 |
| AMZN | 250.28 | 250.18 | −0.10 |
| INTC | 120.11 | 120.12 | +0.01 |

The account had no positions at readback.

Limits:
- One 5-minute window at 1x with 1-share orders, so it is evidence of engine and broker order flow, not of strategy
  edge.
- The build includes Codex commits that are not yet on main, so the `adaptive-paper-broker-trial` gate stays
  `not_established` until those commits and #123 are on main and a trial built from main passes.
