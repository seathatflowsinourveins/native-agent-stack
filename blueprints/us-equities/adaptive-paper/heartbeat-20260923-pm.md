# September 23 afternoon paper qualification

This follow-up preserves the original account ledger/lock and exact prior config
SHA256 `77244c396c407d20f7b21f0e9e8ad9a2c4803ad663247ac210076a47ebbc7eb3`.
The [structured receipt](heartbeat-20260923-pm.json) records current status;
the [morning report](heartbeat-20260923.md) retains both interrupted attempts.

## Measured five-minute paper result

Trial`adaptive-20260923-pm2` from reviewed frozen`93493e7d` PASSED in300.868594s
with normal duration completion. The broker confirmed an open regular session
at19:25:15.873770382UTC; final reconciliation reads ran through19:30:17UTC.
Independent order-level audit excluded all30prior intents.

| Measure | This trial |
| --- | --- |
| Submitted orders / fully filled orders | 10 / 10 |
| Positive fill increments / native fill events | 10 / 10 |
| Roundtrips | 5: AAPL1, INTC3, NVDA1 |
| Incremental executed-price cash/PnL | +0.09USD |
| Final positions / open orders | 0 / 0 |
| Fresh cash reconciliation | Matched; cumulative original-baseline delta-1.01USD |
| Run-recorded requests | 54:44reads,10submits,0cancels |
| Original-ledger request increase including preflight/outer reads | 82:72reads,10submits |
| Peak rolling60seconds account requests / submissions | 38 / 4 |
| Native quotes | 162036 |
| Quarantine episodes / releases | 2084 / 2084 |
| Crossed / timestamp-conflict invalidation events | 27 / 2071 |

Reason counters count events, while episodes can contain several invalidations.
No quarantine remained active and no exposed-symbol escalation occurred. Native
rejections, adapter errors, shutdown failures and reconciliation errors were zero.
Relative strength had21policy selections; the other four families had zero.
Selection counts are not submitted orders. The five families remain wired, but
this run exercised only relative-strength selection at the broker.

Exact fills independently sum to+0.09USD. Incremental gross realized losses were
0.08USD; cumulative realized loss is1.49USD. Separate fees, spread, slippage,
market impact and queue realism were not independently measured. Paper results
do not establish deployable profitability. The ledger retains1055requests,
19trials and40intents, including the30prior intents and all imported history.
No configuration, numeric risk limit, account baseline or state root was reset.

The changed-source catalog/foundation/convergence/hash checks and15dashboard
tests passed before entry. A scoped scan of its three new commits passed with
34466bytes scanned; generated dashboard HTML remained excluded. The failed
1.17second first trial below is preserved, not overwritten by this acceptance.

## Account continuity

The17:54UTC read-only broker proof was open-session, flat and free of open orders.
Cash was1.10USD below the original baseline. Separate same-account ledgers had
29intents,28filled orders and35positive cumulative-fill increments:43shares
bought/sold, realized P&L-1.10USD and cumulative realized loss1.41USD. The30th
broker order matched the native-fault ledger by exact client/broker identity:
one canceled SPY buy with zero fills. No unknown order remains untraced in that
dated observation.

The original ledger lacked these later trades and losses. The account-wide STOP
held entries during reviewed append-only history consolidation and fresh
reconciliation, which subsequently passed. Source ledgers and failed receipts
stay intact. Zero-order
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
A flat account or a successful history import does not convert an interrupted
run into five-minute acceptance. The bounded attempts below remain separate.

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
The first reviewed native entry path conservatively stopped on conflicting
equal-time quotes. This occurred in the actual trial below; a separate read-only
sample measured that category and prompted a bounded qualification followup.
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

## Native trial followup

A different one-shot scheduler released the shared hold and launched source
`fbda2409` at18:56:25UTC. It used the original ledger and correct configuration,
but retained executable quotes after crossed data. Independent exact-source
offline reproduction confirmed that gap. The run ended18:58:56UTC after146.758s,
with65777quotes,3crossed quotes dropped and zero orders/fills/roundtrips. Its
`completed_no_signals` label is not five-minute acceptance. A fresh recovery
through reviewed source passed with no positions/open orders and matched cash.
The service became inactive; no paper timer remained. The shared hold was
restored, and the foundation task was notified to leave this account writer idle.

After these checks, the coordinator ran frozen reviewed`3b252cc1` once, trial
`adaptive-20260923-pm`. It correctly reported`needs_attention` after1.17165s:
SPY`quote_timestamp_conflict`,135native quotes, zero submissions/fills/roundtrips,
eight recorded run reads and no cancel requests. Aggregate quarantine counters
were invalidated1/released1; their causes were not separated, so they do not
prove crossed-quote recovery. A fresh owned recovery passed, flat and cash-matched
at the original baseline minus1.10USD; incremental trial P&L was zero. STOP was
restored pending safe conflict handling and independent review. Neither this
failure nor its flat recovery qualifies five-minute acceptance.

A separate19:04:49–19:05:04UTC read-only SIP sample measured5712quotes in15.0178s:
55equal-timestamp pairs,51otherwise valid fresh conflicts and4identical normalized
quotes. Raw message equality, venue, tape and nonhalt condition differences were
not measured by this normalized executable-field comparison.
No crossed quote or halt was observed. Conflicting field counts were bid-size31,
ask-size18,bid-price5,ask-price1; fields can overlap. All5712raw timestamps were
MessagePack Timestamp values, preserved at nanosecond precision. The
[Alpaca quote schema](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data)
specifies nanosecond timestamps. These observations support testing safe
invalidation and strictly-newer requalification; they do not justify executing
either conflicting quote or silently retaining an old executable price.

The changed quarantine handles otherwise-valid equal-time conflicts through the
same exact-nanosecond tombstone and permanent intent-version path. Claude found
and closed a low-severity availability regression for identical halted duplicates;
these retain baseline behavior while halted conflicts/requalification stay fatal.
The final95focused tests passed in6.172s; independent final regressions passed
3checks in0.850s, after independent91plus2checks on the first candidate. The
combined586test suite passed585with one optional calendar skip in53.810s before
that narrow halted-duplicate correction. Native Claude read original source and
closed its finding at`d5ceaadb`; it did not execute tests or broker calls.

A benchmark conflict after another symbol's POST starts retains per-symbol
exposure handling: it does not automatically stop that whole feed, but the order
remains owned/attempted, a duplicate client ID is lookup-only, and dependent
entries wait for strictly newer benchmark recovery. A mocked accepted-POST/fill
fixture now checks this boundary; native broker fault acceptance remains separate.

Required pretrial source/catalog/foundation/convergence checks and15dashboard
tests passed for`3b252cc1`. The full-range guarded secret scan was terminated
at about4.1GiB RSS(exit143); seven commits excluding generated dashboard HTML
passed,129866bytes scanned. That excluded HTML has incomplete scan coverage;
no guard limits were raised.

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

A second19:07:21UTC bounded refresh returned50items and24snapshots via two200
responses. Eight article IDs were new;42common revisions were unchanged.
Publication times spanned11:37:57–18:46:47UTC; each item retains its separate
update and observation times. Breadth was6positive/18negative, all24quotes fresh,
and14within15bps. Benchmark losses narrowed to SPY-0.678/QQQ-0.858/IWM-1.644/
DIA-0.650percent. These are dated research observations, not executable strategy
signals; the rolling-window families and advisory-only catalyst boundary remain.

The480row/24symbol daily data snapshot through September22 and its12passing
promotion checks remain reusable because the input hash is unchanged. That
daily-data evidence does not qualify live quote handling or strategy returns.

The200shared REST requests/minute and180all-submissions/minute limits remain
ceilings. This trial measured a peak4submissions/minute. No result establishes
near200actual fills or1000trades per minute, or qualifies live trading.
