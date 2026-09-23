# Adaptive paper 1x trial, 2026-09-23 12:47 ET: main-built pass (gate receipt)

This trial ran from a read-only `git archive` of main `843dc8f`, which includes the three engine fixes from #123. The
hashes are in `frozen-843dc8f.SHA256SUMS`, and all 443 match `git archive 843dc8f -- blueprints/us-equities`. It used the bounded run-once
`scheduled_trial.sh`, the frozen `config-sip.json` (sha256 `3587653104e6…`), 1x cash and the SIP feed.

Result (`paper-output.json`):
- Status `passed`, rc 0, 300.5 s elapsed of the configured 300 s. That was checked directly, because main's runner does
  not yet carry Codex's interrupted-run reporting.
- 147 decisions; `relative_strength` was selected twice.
- 5 submits, 1 cancel, 4 native fill events, 0 adapter errors.
- 134 crossed quotes dropped: IWM 85, QQQ 38, AMZN 4, MU 3, and one each for AAPL, CRWD, GOOGL and TSLA.
- Reconciliation: `cash_match` and `positions_match` true, 0 open orders, 0 positions. Realized −0.28 USD.

Broker readback (`broker-orders.json`, read-only; no positions at readback):

| Symbol | Buy fill | Sell fill | Notes |
|---|---|---|---|
| INTC | 120.57 | 120.55 | |
| GOOGL | 338.61 | 338.35 | The first exit limit, 338.42, did not fill and was canceled, then replaced at 338.33 |

This receipt establishes `adaptive-paper-broker-trial`. It is evidence of real engine and broker order flow,
cancel-replace, reconciliation and cleanup at 1x with 1-share orders over one 5-minute window. It is not evidence of
strategy edge.
