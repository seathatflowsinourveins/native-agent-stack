# Adaptive paper 1x trial, 2026-09-23 (interrupted)

Engine outputs of the bounded run-once trial from a read-only `git archive` of
`41d39b3` (`scheduled_trial.sh`), plus `observations.json` with the operating
session's own observations (timer stop, pre-launch account check, relaunch and
a later clock-offset measurement), labelled as operator observations.

The runner reported `completed_no_signals` (rc 0) but `elapsed_seconds` is
4.15 of the configured 300: three warm-up decisions (regime `unavailable`),
8,512 native quotes, 0 orders, flat, cash delta 0. The log records a
trading-stream websocket reconnect, and `runner.py` at `41d39b3` stops on any
non-stale transport-health reason. An interrupted decision loop is not a trial,
so `adaptive-paper-broker-trial` is unchanged and `41d39b3` is not retried.
`universe-daily.csv` (SIP bars) is not republished; its hash is in
`ingest-receipt.json`.
