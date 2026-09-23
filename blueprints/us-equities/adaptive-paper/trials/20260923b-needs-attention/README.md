# Adaptive paper 1x trial, 2026-09-23 11:27 ET (needs_attention)

Engine outputs of the bounded run-once trial from a read-only copy of commit
`1e2c96a` (Codex's stop-diagnostics build, byte-verified against `git archive`),
plus `observations.json` (operator observations) and a reproducible read-only
quote-validity measurement (`measure_quote_validity.py`).

The run correctly reported `needs_attention` (rc 3) after 25.9 s of 300: its
`decision_exit` is `transport_gap` with `callback_failure` at stage
`quote_normalization`. `transport.normalize_quote` rejected a crossed SIP quote
(bid above ask across exchanges), the consume loop treated that as a transport
integrity failure, and the runner stopped. Flat, 0 orders, cash delta 0.

Crossed books are brief but routine on SIP: one 60 s sample over the trial
universe rejected 9 of 56,855 quotes, all crossed; the committed measurement
against the same transport found 1 of 51,116. The fix in this change drops
crossed and one-sided quotes as untradable (counted in `health["dropped_quotes"]`)
instead of failing the transport; malformed quotes still fail it.
`quote-validity-fixed-transport.json` is the same measurement against the fixed
transport.

The "trading stream websocket error, restarting ... sent 1000" log line is a
shutdown artifact: the transport alone stayed healthy for 25 s and emitted it
only when its own `stop()` closed the streams.
