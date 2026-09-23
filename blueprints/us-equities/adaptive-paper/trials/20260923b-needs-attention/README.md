# Adaptive paper 1x trial, 2026-09-23 11:27 ET (needs_attention)

Engine outputs of the bounded run-once trial from a read-only copy of commit
`1e2c96a` (Codex's stop-diagnostics build, byte-verified against `git archive`),
plus `observations.json` (operator observations) and a reproducible read-only
quote-validity measurement (`measure_quote_validity.py`).

The run correctly reported `needs_attention` (rc 3) after 25.9 s of 300. Flat, 0 orders, cash delta 0.

- Recorded: `decision_exit` is `transport_gap`, with `callback_failure`
  `{stage: quote_normalization, exception_type: TransportError}`. So
  `normalize_quote` raised on a streamed quote; the recorded fields do not say why.
- Most likely cause: a crossed SIP quote (bid above ask across exchanges). In the
  committed read-only measurements, crossed books are the only rejection class
  observed: 1 of 51,116 quotes against this transport, and 1 of 50,633 against
  the fixed one. An earlier 60 s sample (9 of 56,855, all crossed) was not
  retained; it is an operator observation. The fix in this change drops
crossed and one-sided quotes as untradable (counted in `health["dropped_quotes"]`)
instead of failing the transport; malformed quotes still fail it.
`quote-validity-fixed-transport.json` is the same measurement against the fixed
transport.

The "trading stream websocket error, restarting ... sent 1000" log line is a
shutdown artifact. `transport-isolation-1e2c96a.json`, from the committed
read-only `transport_isolation_check.py`, shows the transport alone ready with
no health reasons for 25 s (8,914 quotes). The restart records appear 16-27 ms
after `stop()` is called, and none before. `frozen-1e2c96a.SHA256SUMS` lists
the frozen copy's files, which were byte-compared with `git archive 1e2c96a`.

With crossed quotes tolerated, the next runs reached the 30 s reconciliation and
failed there. That is a second SIP-volume defect; see
`../20260923c-reconcile-refusal/`.
