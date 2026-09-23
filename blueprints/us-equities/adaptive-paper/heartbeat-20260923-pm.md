# September 23 afternoon paper qualification

This follow-up preserves the original account ledger/lock and exact prior config
SHA256 `77244c396c407d20f7b21f0e9e8ad9a2c4803ad663247ac210076a47ebbc7eb3`.
The [structured receipt](heartbeat-20260923-pm.json) records current status;
the [morning report](heartbeat-20260923.md) retains both interrupted attempts.

## Account continuity

The17:54UTC read-only broker proof was open-session, flat and free of open orders.
Cash was1.10USD below the original baseline. Separate same-account ledgers had
29intents,28filled orders and35positive cumulative-fill increments:43shares
bought/sold, realized P&L-1.10USD and cumulative realized loss1.41USD. The30th
broker order matched the native-fault ledger by exact client/broker identity:
one canceled SPY buy with zero fills. No unknown order remains untraced in that
dated observation.

The original ledger lacked these later trades and losses. The account-wide STOP
therefore holds entries pending reviewed append-only history consolidation and
fresh reconciliation. Source ledgers and failed receipts stay intact. Zero-order
diagnostic ledgers also contribute request history. Consolidation must retain
partial fills, cumulative loss and the offset account peak, preserve original
limits and baseline, and be idempotent/transactional. The separately used larger
quantity/exposure limits are historical provenance, not this lane's risk policy.
Fresh proof also queries paginated [account activities](https://docs.alpaca.markets/us/reference/getaccountactivities-2)
to match executed fills and detect fees, funding or other nontrade activity;
matching net cash alone cannot establish their absence. Alpaca notes that
nontrade fees can be created the following day, so a current proof does not
establish the eventual absence of later charges.

These historical runs are separate from this heartbeat's submission count.
No new afternoon entry trial is claimed here. A flat account or a successful
history import does not convert any interrupted run into five-minute acceptance.

## Crossed quotes and native review

An independent offline reproduction of the other checkout's count-and-drop
patch retained an executable quote and allowed a mocked POST after a crossing.
It does not meet the requested invalidation contract. The bounded replacement
invalidates executable caches, uses exact nanosecond tombstones on both sides of
the native queue, and preserves ledger valuation marks. Only a strictly newer,
otherwise valid fresh quote can release a symbol within the existing timeout.
Affected held or pending exposure retains the whole-feed stop; other invalid
data remain fatal. Version checks protect unsent orders across invalidation and
recovery. Native fill identifier, pending timer and reconciliation race fixes
are reused as separate bounded changes.

Native Claude identified an unnecessary recovery-port liveness change for valid
same-timestamp quote updates; the correction preserves its previous behavior.
The opted-in native entry path conservatively stops on conflicting equal-time
quotes; collision frequency is unmeasured and that choice can stop a trial early.
The fixed-share limit-order path uses the submitted limit price in the pinned
[Nautilus RiskEngine source](https://github.com/nautechsystems/nautilus_trader/blob/v2.0.0rc5/crates/risk/src/engine/mod.rs#L1503),
while its quote-sized/market-order cache behavior is outside this qualification.
The inspected upstream file SHA256 is
`204e32e8aec96552dbe740a79216813935c82a64c640b3f7aed6410827b80160`.
Benchmark invalidation before the transport receives an already-made policy
decision remains a noted timing boundary; generation checks cover admission
from `port.submit` onward. It is not claimed as decision-time synchronization.

Focused qualification and independent Codex/native Claude reviews passed. The
combined suite ran571checks,570passed and one optional calendar check was skipped;
the final consolidation followups passed32focused tests and independent new
regressions. Local mocked HTTP and native LiveNode fixtures establish only their
tested behavior, not broker throughput or paper strategy profitability.

At18:39:07UTC the actual paper proof matched30orders and35FILL activities, with
no non-FILL activity in the complete queried interval. The account was flat and
idle; cash reconciled to the original baseline minus1.10USD. Consolidation into
the original ledger committed14source histories, retaining777requests,16trials,
30intents and147events including its audit record. Source ledgers remain intact;
flat position rows/stale marks are archived as provenance. Limits, baseline,
halt and STOP were preserved. Original-ledger recovery then passed with zero
unresolved orders and cash-1.10USD matched. Neither action submitted an order.

## Market research

The bounded17:38:37UTC refresh returned50news items and24IEX snapshots through
two successful read-only calls. It retained publication, update and observation
times separately;31article IDs were new since morning. Breadth weakened from
8positive/16negative to5/19. Twenty-three quotes were fresh and12also met the
15bps research spread threshold. ARM's quote was stale at16.61seconds.

SPY/QQQ/IWM/DIA changes versus the same prior closes were-0.758/-1.050/-1.696/
-0.652percent. These day returns do not establish the rolling-window regimes
used by trend momentum, range breakout, mean reversion, relative strength and
defensive cash. All five retain their existing formulas and numeric risk rules.
Catalyst rankings remain advisory; no catalyst orders or automatic leverage
were enabled. IEX research is separate from the SIP execution feed.

The480row/24symbol daily data snapshot through September22 and its12passing
promotion checks remain reusable because the input hash is unchanged. That
daily-data evidence does not qualify live quote handling or strategy returns.

The200shared REST requests/minute and180all-submissions/minute limits remain
ceilings. No result establishes near200actual fills or1000trades per minute.
