# Adaptive paper 1x trials, 2026-09-23 11:42 and 11:5x ET (reconciliation refusal)

Both runs used integration build `796e3d1`, which is Codex's `1e2c96a` plus the first crossed-quote fix, from a read-only
`git archive` copy. `frozen-796e3d1.SHA256SUMS` lists the frozen files.

- **Trial c** (`trial-c-*`): scheduled run-once script, needs_attention after about 35 s (rc 3) with
  `error_type: TransportError`. There were 0 orders. `flat: false` there means flat was not proven in-run; a read-only
  account check right after found 0 orders since 15:40Z and 0 positions.
- **Diagnostic run d** (`diag-d-*`): the same frozen build, ingest and gate, but the runner was started through
  `trace_runner.py`. That wrapper runs the unchanged `runner.py paper` and only prints the traceback of an exception
  raised in `run_native`. It failed the same way. The traceback shows `runner.py:893 port.mark_reconciled()` raising
  `streams are not ready for reconciliation acknowledgement`.

Cause, from source: `mark_reconciled()` refused unless the transport's event queue was completely empty. On SIP, quotes
arrive continuously (for example 8,914 in 25 s for four benchmarks in `../20260923b-needs-attention/transport-isolation-1e2c96a.json`),
so at the first 30 s periodic reconciliation the queue is essentially never empty. The earlier runs stopped before 30 s,
on the crossed-quote failure, so they never reached it. The fix refuses only while an order event is queued; queued
quotes do not affect a reconciliation acknowledgement.
