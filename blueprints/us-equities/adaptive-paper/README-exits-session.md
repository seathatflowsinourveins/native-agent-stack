# Measured exit candidates and current session limits

The default exit context and native strategy retain the existing RTH behavior.
The current runner passes its validated `session_policy` to `AdaptiveStrategy`.
When `session_policy["extended_hours"]` is true, the strategy selects the existing
session classifier using its owner-loop clock for every transport, including
`SimulatedPort`. Default RTH runs do not consult a calendar, regardless of a
transport attribute. A diagnostic can supply `exit_session_at` explicitly:

```python
exit_session_at=lambda now: session_at(datetime.fromtimestamp(now, timezone.utc)).kind
```

No wall clock, broker call, or new order adapter is added to the exit decision.
The owning runtime supplies `ExitContext.session`. The current actionable
classes are RTH, PRE and POST. A fresh OVERNIGHT label produces a flagged hold
with reason `overnight_unqualified`: native classification, adapter support
and owned T15 paper acceptance remain **NOT_RUN**. This preserves OVERNIGHT as
an evidence-gated research candidate rather than declaring it permanently
ineligible. The installed `sessions.session_at` still classifies only
PRE/RTH/POST/CLOSED; its defaults and unrelated entry callers are unchanged.

CLOSED and unknown labels hold **every sell**, including stop-loss and forced
cleanup, with `session_unavailable`. A classifier `ValueError` becomes the
distinct `session_classification_failed` attention reason, at both policy-tick
and cancellation-ACK revalidation. A failed classifier supplies no permission
to assume RTH. The classification failure remains visible even if the quote
is also stale. Other non-RTH stale/missing/future quotes retain `quote_stale`.

Outside RTH, a stale/missing/future quote flags the position and creates no new
submission or replacement. A fresh PRE/POST exit is an explicit marketable
limit, using the existing bid/ask pricing helper. The strategy still uses the
native LIMIT/DAY order factory and its existing instrument, risk, and account
writer controls. Replacements recheck session and quote at cancellation ACK.
Validated extended-hours runs also reclassify each native SELL at the execution
client's clock immediately before asynchronous dispatch. Only RTH/PRE/POST may
reach the broker. An unavailable/unqualified session or classifier `ValueError`
produces a native denial before submission and records a session fault that
stops the node. The held residual remains visible and ends `needs_attention`
with exit 3, preventing a plain LIMIT/DAY exit from queuing for the next session.

`last_exit_decisions` carries submit/attention/limit metadata outside the golden
serialized `Decision`. Flagged holdings retain their targets so allocation cannot
turn a hold into a portfolio-rotation exit. Runtime events include attention
reasons; partial take-profit fractions and the existing RTH thresholds remain.
An `exit_attention` event is emitted only when that symbol's active reason
changes. Repeated cleanup ticks preserve the reason without emitting it again;
clearing the active hold allows the same reason to be emitted if it returns.
Native sell dispatch and replacement ACK also flag stale quotes in RTH, while
the historical RTH policy rule ordering stays unchanged. Active attention is
retained across throttled ticks, cleared by a new unflagged policy disposition,
and intersected with final held symbols. It joins the final
`pending_needs_attention_held` set even when the corporate-action guard is off.
A forced sell left held for a stale quote or unavailable session therefore
ends `needs_attention` with exit 3, not an intentional `held_overnight` success.

Leverage ceiling-change receipts bind `regime` to the `Decision` returned by
that same rebalance tick. A later intent/attention event cannot replace it.
A throttled tick returns no `Decision` and produces no new ceiling-change row;
the cached operational ceiling still describes the current exposure limit.
No second policy evaluation is used to fill receipt metadata.

## Candidate metadata and admission

The landed scope record is us-equities-trading
`2e0860ccd1d485593d1bd31b8a97c12198ca6b3d`,
[`docs/decisions/2026-10-09-equities-intraday-scope.md`](https://github.com/seathatflowsinourveins/us-equities-trading/blob/2e0860ccd1d485593d1bd31b8a97c12198ca6b3d/docs/decisions/2026-10-09-equities-intraday-scope.md).
09:35/10:00 entries have priority; historical evidence determines exit timing.
T22 owns four versioned hypotheses: `regular-close-v1`, `after-hours-v1`,
`overnight-v1` and `next-premarket-v1`. Their descriptor identity includes
resolved numeric parameters, units, session settings, policy version and
evidence digest. A digest alone does not validate its evidence contents.
No measured preset is loaded or qualified by this patch, and no universal
flat-by-close requirement is introduced. The existing bounded trial/cleanup
deadline remains distinct from any future admitted strategy exit horizon.

T22's `StrategySpec.exit_policy` and `exit_evidence_sha256` resolve its immutable
`Preset.exit_policy`. At the CC-cued integration it supplies the same tick's
session/bid/ask and consumes `ExitDecision.reason`, `fraction`, `submit`,
`flag_position`, `price_rule` and `limit_price`. Flagged holdings keep their
targets and create neither an order nor a rotation. `last_exit_decisions` is
metadata outside golden serialization and is consumed only with that tick's
non-None `Decision`. Submit/ACK revalidation retains the original reason and
quantity; it does not choose a horizon or recompute strategy thresholds.

Orders remain simple equities, native LIMIT/DAY and admitted instruments;
options, multi-leg and crypto execution are outside this scope. Current
ticker syntax and construction of a native `Equity` are not broker asset-class
attestation. Before a new native admission, preserve the vendor's raw `class`
as `asset_class` through preflight and instrument metadata, and require
`us_equity` without a missing-field default. This still-open shared transport/
runner/instrument obligation and its current broker observation are distinct
from historical universe membership. No broker asset lookup was run here.

The existing extended-hours construction activates the supported PRE/POST
behavior. The shared runner now consumes exit attention and binds its receipt
to the same-tick decision. No new runner or adapter is added. No frozen N2
source, bundle, protocol, STOP latch or historical qualification is changed.
Tests use synthetic quotes and fake broker operations. Runner regressions drive
the real rc5 LiveNode, including a POST owner tick dispatched at 20:00 through
the native execution client; existing caller tests also use fake native
order/cancellation methods. These establish neither broker acceptance nor
overnight admission or live readiness.

The public source-hashes manifest binds the changed implementation bytes. The
registry ID, evidence class SYN, settings and receipt remain unchanged. The base
`strategies_v1.py` source at `3a4cc28840ba7e8a1a9474a989102a669955f243`
was SHA256 `1952be269694485e12e4d927f124adca0ee29667588d6ac6651caede454c92f7`
(27,499 bytes); this implementation is SHA256
`6f434d001489ba605f7a737e25a259be87e97127cd1c8788db504f2313af86eb`
(28,488 bytes). This source-integrity refresh does not rebind any historical
qualification or N2 frozen source pin. Native paper acceptance is **NOT_RUN**.

## Primary sources

NautilusTrader 2.0.0rc5 is pinned to
[`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`](https://github.com/nautechsystems/nautilus_trader/tree/1b0a49d2792a9432a3aca3fcb617ce7a630d905e).
Its native
[`generate_order_denied`](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/live/clients.py#L451)
uses the owning execution client's clock and native event output. The dispatch
refusal reuses that event path, and the boundary regression uses rc5's
`Clock.new_test()` without replacing the engine or adapter.

Alpaca's [official order rules](https://docs.alpaca.markets/docs/trading/orders),
fetched 2026-10-09T23:10:15Z, describe overnight 20:00–04:00 ET and PRE/POST
support. PRE/POST-only is this runtime's current classifier/flag boundary,
not a claim that the vendor lacks overnight trading. Extended-hours execution
requires the vendor's eligible order flag; a plain DAY order outside its
eligible session can be queued for the next trading day.

The installed SDK pin is alpaca-py 0.44.0,
[`cc4cb3b7ba50ae250e621983c2779047fb16bb28`](https://github.com/alpacahq/alpaca-py/tree/cc4cb3b7ba50ae250e621983c2779047fb16bb28).
[`OrderRequest.extended_hours`](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/trading/requests.py#L347)
is an optional flag. That schema and its overnight data-feed enum do not prove
native order-session qualification. The
[`Asset` alias](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/trading/models.py#L54)
and [`US_EQUITY` enum](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/trading/enums.py#L175)
were verified at the pin on 2026-10-09T22:51:57Z–22:52:35Z. Synthetic tests use
the installed rc5/SDK runtime with fake broker methods; the CC's runtime-gate
re-run, actual paper/journal lifecycle and review remain separate receipts.
