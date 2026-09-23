# Adaptive paper 1x trial, 2026-09-23 (interrupted)

Engine outputs of the bounded run-once trial from a read-only `git archive` of
`41d39b3` (`scheduled_trial.sh`), plus `observations.json` with the operating
session's own observations (timer stop, pre-launch account check, relaunch and
a later clock-offset measurement), labelled as operator observations.

The runner reported `completed_no_signals` (rc 0) but `elapsed_seconds` is
4.15 of the configured 300: three warm-up decisions (regime `unavailable`),
8,512 native quotes, 0 orders, flat, cash delta 0. The log records a
trading-stream websocket restart message, and `runner.py` at `41d39b3` stops on
any non-stale transport-health reason.

Correction (2026-09-23 11:30 ET): the restart message is emitted when the
engine closes its own streams at shutdown and did not cause the stop; that was
shown for `1e2c96a`'s transport (`../20260923b-needs-attention/transport-isolation-1e2c96a.json`),
not re-run for this build's. The 11:27 rerun with stop diagnostics
(`../20260923b-needs-attention/`) recorded `callback_failure` at
`quote_normalization`: `normalize_quote` raised. A crossed SIP quote is the most
likely reason there. For this 10:11 run it is only a possible explanation. At
the retained crossed-quote rates (1 in 51,116, and 13 in 186,659 in trial f)
the chance of at least one among its 8,512 quotes is about 15 to 45 percent.
This build recorded no stop reason, and other causes were not excluded.
