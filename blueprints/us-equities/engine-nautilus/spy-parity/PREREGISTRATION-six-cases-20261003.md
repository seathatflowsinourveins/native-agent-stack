# Prospective six-case current-source continuation (2026-10-03)

Status: **UNEXECUTED**. This is locally authored integration glue around official
NautilusTrader 2.0.0rc5 source `1b0a49d2792a9432a3aca3fcb617ce7a630d905e`
and the unchanged LEAN fixture/policy at `985ef30ad3ac774218c5ac516b4cb0aa2655730f`.
No new native, destination-host, broker, or production qualification is asserted.

Only explicit `--mapping-manifest mapping-manifest-six-cases-20261003.json`
selects this source. Old v1/v2/stress/refusal manifests, source snapshots,
receipts, failure histories, deviation acceptance, oracle, plan, five input
files and tolerance sheet remain byte-exact historical evidence. No old review
or engine result seals this changed source. Old CLI defaults keep their old
binding and may refuse changed source; this successor does not renew them.

## Policy and execution authority

All six unchanged plan cases execute on a native NETTING MARGIN account with
instrument initial/maintenance rates 0.5, StandardMarginModel, leverage 2 and
RiskEngine bypass=false. Native rc5 automatic full-position liquidation is
explicitly disabled for this fixture. Its entry-valued maintenance remains an
untouched separately named native diagnostic. Derived `margin_used` and
`margin_remaining` reproduce the frozen LEAN current-value policy; they are
never relabelled native maintenance or paper/production risk behavior.

DefaultMarginCallModel.cs:60-116,134-225 and BuyingPowerModel.cs:333-354,421-518
define the warning/call predicates, strict >110% equity threshold, fee-aware
integer target holdings, no reversal, exchange-open execution and restored
margin stop condition. The single SPY position needs no cross-asset ordering.
MARKET reductions are actual native reduce-only orders. The native fill model
supplies the adverse book before matching, rounded once to six decimals with
HALF_EVEN; the official FixedFeeModel charges the plan fee once per economic
order. No prices/quotes/fills are injected, exports repriced, or account/cache
values mutated. Oracle quantities, dates and outcomes never drive execution.

The completed 16:00 decision freezes floor(equity*target*0.98/close) shares.
The existing native STOP_MARKET/MARKET_IF_TOUCHED OCO proxy retains trigger
spacing 0.0001 and native contingency cancellation. Initial/exit/adaptive fills
must occur causally on a later session. Adaptive peak updates at every settled
hourly mark; only a completed 16:00 close can latch the one-way 5% reduction to
target 0.5. The over-limit case submits one actual MARKET request for native
RiskEngine refusal; native DENIED/reason/event identity is retained verbatim,
never converted to LEAN's Invalid spelling.

## Settlement handshake, awaiting native proof

At pinned engine.rs:1977-2006, commands settle before venue modules and again
after them. exchange.rs:1647-1690 collects all module process results before
posting adjustments/acknowledging them. A second observer returns Completed([])
with zero adjustments, then acts from its acknowledgement **after** the first
DistributionModule's cash acknowledgement. It reads native exposure, evaluates
the frozen LEAN margin policy and queues any immediate MARKET reduction at the
original economic timestamp. No mark/latch is emitted while that fill is pending.

A supported native clock alert at economic timestamp+1ns then admits a mark only
after all requested reduction quantity is filled at the original timestamp and
cached native exposure agrees. Both economic and actual observation timestamps
are retained; no native order/fill time is overwritten. Discretionary OCO intents
may queue at this actual +1ns clock instant, strictly before the next-session bar.
The engine end range explicitly includes the final +1ns alert. Missing, early,
duplicate, partial/lost fills, acknowledgements, observations or callback errors
refuse qualification. Exact module/queue/timer order and price provenance remain
**unproved until an independently reviewed, fenced native probe and replay**.

## Prospective binding and acceptance

The selected manifest seals all eleven source Python files, v1/v2 manifests,
tolerances and the existing official ARM64 dependency lock. The independent
review additionally binds selected manifest/preregistration bytes, exact run and
compare argv arrays, final source commit/snapshot, interpreter/extension/image,
five inputs, oracle/plan/tolerance and the fresh fence. Review completion must
precede every native process. `full_wrapper_freeze_sha256` names the immutable
**pre-review command candidate**; a final owner freeze may add the actual review
digest only while preserving its reviewed executable arrays. This avoids a
circular review-digest/freeze-digest requirement. No retrospective reuse is allowed.

Each of six cases requires two distinct fresh fenced processes, each containing
two fresh native engines, with independent strict comparisons. The comparator
requires `--lean-data` and `--oracle-audit` pointing to the original LEAN case
audit at its receipt-pinned SHA256; every one of 725 marks, all calls/warnings/
distributions/latches/intents/fills, native callback/cache events and monetary
values are checked. No tolerance changes, skip-based qualification or synthetic
engine acceptance is permitted. Preserve every failure and raw native export.

## Destination handoff

This successor supports only the separately evidenced official Linux ARM64
CPython 3.13.16 artifact/lock profile, not an unobserved workstation architecture.
The workstation owner must preregister an official destination-specific
artifact/lock, source/profile successor, input snapshot, fence and independent
review before running any engine. No silent profile fallback or guessed hash
is supported. Current native phase/engine acceptance is UNEXECUTED; workstation,
paper/account/PIT and broker lifecycle gates remain separate and unqualified.
