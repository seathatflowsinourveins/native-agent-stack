# Adaptive paper 1x trial, 2026-09-23 14:56 ET: clean run, no signals, early loop exit (partial evidence)

This trial ran from a read-only `git archive` of `fbda2409`, the head of PR #138 at the time. That commit was main
`9e643b1d` plus the optional `--live-dir` live record, and the PR later merged as `40828dfe` after review fixes. The
hashes are in `frozen-fbda2409.SHA256SUMS`, and all 452 match `git archive fbda2409 -- blueprints/us-equities`. It
used the bounded run-once `scheduled_trial.sh` with `LIVE_DIR` set, on the account's original durable ledger. The
config was that ledger's own frozen config, `config-sip-77244c39.json` (sha256 `77244c396c40…`): 1x cash, SIP feed,
1-share orders, 25 USD loss and drawdown limits. That config is not the repository's `config-sip.json`.

Before it ran, the ledger's owner (the afternoon heartbeat) had consolidated the day's separate-state-root trials into
the ledger and recovered it. Its STOP hold was archived with a release record citing both of the hold's conditions.

Result (`paper-output.json`):
- Status `completed_no_signals`, rc 0. The run left its loop after 146.8 s of the configured 300 s, while flat.
- 72 decisions: regime `unavailable` 48 times and `range` 24 times, alternating in 14 runs (15 `unavailable`, 3
  `range`, 20 `unavailable`, ...), and ending on 4 `range`. So `unavailable` was not only warm-up. No strategy
  produced a target, and no order was sent.
- 65,777 native SIP quotes, 3 crossed quotes dropped (TSLA 2, AAPL 1), 0 rejections, 0 adapter errors.
- Reconciliation: `cash_match` and `positions_match` true, 0 open orders, 0 positions. The ledger's cash delta stays
  -1.10 USD, which is the day's consolidated history. The ledger's phase is `finished`.
- Live record: decisions streamed to `events.jsonl`, and NautilusTrader's JSON log went through the collector into Loki.
  The Prometheus scrape of `live_manifest.py` was `up`. The AccountState log line arrived in Loki with its balances and
  account id redacted.

Limitation: main's runner does not record why its loop ended. `paper-output.json` shows no STOP file, no halt and no
session error. `scheduled-trial.log` line 4, `data websocket error, restarting connection: sent 1000 (OK)`, is a
normal-close (1000) record. An isolation check earlier the same day
(`../20260923b-needs-attention/transport-isolation-1e2c96a.json`) found these restart records only after `stop()`. This
run did not record the line's timing, so it neither identifies nor rules out the cause. A transport health freeze is
the likely cause. A later heartbeat build that records
`decision_exit` stopped another trial on `transport_gap` / `quote_timestamp_conflict` 1.2 s after its start, which
suggests the same class, but this run's cause is unmeasured.

This is evidence of a clean start, a clean stop and reconciliation through the live record. It is not evidence of
order flow; `adaptive-paper-broker-trial` rests on trial 20260923g.
