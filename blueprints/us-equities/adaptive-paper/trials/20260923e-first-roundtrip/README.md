# Adaptive paper 1x trial, 2026-09-23 11:54 ET: first real engine round trip (needs_attention)

Integration build `885663a` is `1e2c96a` plus both SIP fixes from #123. It ran from a read-only `git archive` copy,
hashes in `frozen-885663a.SHA256SUMS`. The outputs are the engine's own files plus `broker-orders.json`, a read-only
readback of the broker's orders for the window.

What happened:
- The run passed the 30 s reconciliation. The regime moved from `unavailable` to `range`, and `relative_strength` was
  selected.
- The engine submitted a real paper order: INTC buy 1, limit 120.43, DAY. It filled at 120.40.
- At 43.3 s the run stopped with `decision_exit: adapter_error` (`order_ValueError`, then `unknown_cancel:ValueError`).
- Recovery exited the owned residual: INTC sell 1, limit 120.37, filled at 120.39. The run's own reconciliation
  reports flat. Net −0.01 USD.

Cause, reproduced offline: the adapter built `TradeId(broker_order_id + ":cum:" + qty)`. Alpaca order ids are
36-character UUIDs (`broker_order_id_length` in the readback), so the id was 42 characters. Nautilus caps a TradeId at
36 ("String exceeds maximum length of 36 characters"), so every real fill raised. The offline fake port uses short ids,
so the suite never hit it. Fixed with a deterministic 36-character digest per fill.
