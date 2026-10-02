# Prospective SPY over_limit native refusal mapping, 2026-10-02

Preparation only: no engine operation has run under this mapping. Qualification
requires independent review of the exact new package and all ten unchanged
stress sources, declared argument arrays, then root-owned strict Linux replay.
The qualified stress package and frozen LEAN inputs/oracle/tolerances stay sealed.

This mapping covers only frozen `over_limit` no-fill economics. LEAN submits one
MarketOnOpen intent at 1577826000 for 1217 shares, returns native `Invalid` with
insufficient buying power, and produces zero fills, fees and distributions;
cash remains 100000.00 USD. rc5 receives one native MARKET request at that same
decision. Its native `OrderDenied`/`DENIED`, MARKET type and exact reason remain
unmodified. They are compared as one economic refusal, never relabelled as a
native LEAN status or treated as evidence of market-on-open fill equivalence.

Sizing derives from the actual completed 16:00 New York decision bar:
floor(100000 * 4 * 0.98 / close). No expected quantity/event table enters execution.
The native RiskEngine uses the cached external bar close when quote/trade prices
are absent (`crates/risk/src/engine/mod.rs:1976-2013` at official source
1b0a49d2792a9432a3aca3fcb617ce7a630d905e). Its margin branch calculates initial
margin and emits `INITIAL_MARGIN_EXCEEDS_FREE_BALANCE` before venue submission
when initial margin exceeds native free balance (`1647-1724`, `2216-2250`).

Use a real MARGIN account, 100000 USD, default leverage2, native
StandardMarginModel, instrument initial/maintenance rates0.5, and risk bypass
false with no per-order notional cap. Standard ignores leverage; using
LeveragedMarginModel with leverage2 and rates0.5 would incorrectly halve the
requirement again. Native margin's USD Money precision is retained; its displayed
initial requirement must be within half a cent of quantity * actual close *0.5.
This check concerns a new native diagnostic, not a changed frozen tolerance.

Keep native liquidation enabled and the existing native distribution module.
With no opened position, maintenance valuation, partial liquidation and adaptive
state are vacuous for this case. They remain unsupported for other frozen cases.
The existing stressed fee/fill models are reused; no fee or fill hook may run.
The stress fill model rejects native MARKET simulation if risk unexpectedly
admits the order. Any admitted, submitted, accepted, filled, cancelled or multiply
denied request fails this experiment; no balancing cash or export repricing.

Export one raw native cached order, every raw cached order event, every observed
strategy order event, native commissions, fill/account/position reports, native
account events and 725 native account marks. Preserve native IDs and raw logs.
The cached event sequence must be exactly OrderInitialized then OrderDenied;
denial must occur at the original intent instant with its actual native reason.
Every mark must show native total/free100000 USD, native initial/maintenance
margin0 USD and no open position. End open orders/positions, native fills and
commissions must be zero. Independent Decimal comparison checks the frozen
no-fill ledger directly. The historical0.01 cash allowance is unchanged; these
no-fill cash marks require exact100000. Native snapshot `type` and event
`order_type` fields retain rc5's distinct serialization names.

Each authorized run process constructs two fresh native BacktestEngines.
Two separate fresh root-controlled fenced processes are required for acceptance.
Only UUID4 `init_id`/`event_id` fields may be normalized into a separate comparison
value using the existing format-validating normalizer. Raw native files never
change. No timestamps, prices, quantities, statuses, reasons or risk values are
normalized away. Compare rehashes all five LEAN inputs, source/review/mapping,
raw native exports/logs and the pre-engine frozen argument record; `--lean-data`
is mandatory and there is no bars-only qualification path.

Review schema is `spy-over-limit-native-refusal-review/1`, case `over_limit`,
independent_review true, zero unresolved findings, exact reviewed commit and
exact `reviewed_local_source_sha256` for `over_limit.reviewed_files()`. Retain the
new test module's hash and passing log in the review packet. Review must strictly
precede started_utc. Its `authorized_run_argvs` and `authorized_compare_argvs` must
contain the exact argument arrays; the driver rejects other arrays before engine
construction. Root freezes actual commit/path values and retains controller
commands before review; templates below declare the canonical mount layout.

```text
/runtime/bin/python -I /harness/over_limit.py run --lean-data /data --out /out/over-limit-process-1 --review-record /harness/review-record-over-limit-20261002.json --harness-commit SOURCE_REVISION
/runtime/bin/python -I /harness/over_limit.py compare --lean-data /data --receipt /out/over-limit-process-1/receipt.json --out /out/over-limit-process-1/verdict.json --oracle /historical-simulation/receipt.json
```

Process2 uses `over-limit-process-2` in both arrays. Both processes require the
unchanged v2 loopback-only network namespace, cleared documented environment,
read-only source/data/runtime, Python isolated flag, noninitial user namespace
and bwrap PID1. VM, container, mounts and replay authorization remain root-owned.
This source preparation or a component API check does not close acceptance.
