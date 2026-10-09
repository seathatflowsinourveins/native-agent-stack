# T22 deterministic strategy hypotheses

Ten NautilusTrader `2.0.0rc5` Strategy subclasses and three versioned presets
implement the family predicates in the draft trading-ecosystem §6. Every rule
and parameter remains an untested hypothesis. The same classes have synthetic
BacktestEngine and adaptive-paper LiveNode checks; neither check uses a broker.
[registry.json](registry.json) freezes the grid, factor coordinates, overrides,
controls and target order plans. [source-review.md](source-review.md) records
the upstream pins, demonstrated implementation gap and reference corrections.

The Strategy constructor takes a frozen `StrategySpec`. It accepts only one
instrument and a hash-bound cohort. `FactorSnapshot` records original event
time, availability time, validity, source/cohort hashes and exact decimal factor
values. Missing, future, mismatched, conflicting or unqualified inputs suppress
entry or latch a fault. Observed halt state also suppresses orders and repricing.
The upstream CustomData wrapper schedules snapshots by availability time.

The signal boundary expects available upstream-derived factor and ATR inputs;
it performs no acquisition or ATR reconstruction. It never reads rank rows,
labels or arm outputs from #16. Development use requires release and horizon
qualification plus family-specific OD3/OD4/OD6 gates. The development cutoff is
2026-10-13. This package has no provider client or forward-data mode.

## Class interface

The directory has a hyphenated ancestor, so use Python's supported importlib
module loading:

```python
import importlib

contracts = importlib.import_module("blueprints.us-equities.strategies.contracts")
families = importlib.import_module("blueprints.us-equities.strategies.families")

spec = contracts.StrategySpec(
    instrument_id="SPY.ALPACA",
    cohort_sha256=cohort_hash,
    preset="conservative-v1",
    instance_id="cohort_trial_1",
    position_cap_usd="1000",
    loss_cap_usd="10",
    cash_cap_usd="1000",
)
strategy = families.GapPremarketStrategy(
    spec, ledger=paper_ledger, fault_sink=session_fail
)
```

Backtests call `engine.add_strategy(strategy)`. Hana's adapter accepts the same
instance in `native_adapter.build_node(port, instruments, [strategy])`. Before
adoption, the paper lane must supply its existing durable ledger, failure sink,
qualified factor/cohort bridge and account limits, then review the PR. It retains
the native risk engine and its independent final-wire governor. This lane provides
no paper command and has placed no broker order. Passing the fake-port LiveNode
check does not qualify the bridge or a paper session.

## Execution profiles and R9

`code-managed-limit-v1` is a separately registered simple-order hypothesis. It
uses LIMIT/DAY entries on an observed crossing and reuses adaptive-paper's
existing `exits.py` rule chain for stops, profit, trail and time exits. Position
size is capped by the preset's fractions of frozen notional/loss budgets, whole
shares and available cash. Trail activation, partial profit and per-family hold
overrides are explicit; conservative stays flat at the session close.

Every extended-hours exit is a code-managed limit at the same preset's stop
or trail level. A stale execution quote sends no new order and flags the held
position. Valid fresh two-sided size is required. There is no claim that limit
exits guarantee flatness or a maximum loss through a gap. One in-flight order
prevents buy/sell overlap, and repricing waits for native cancel confirmation.
Partially filled buys are never re-sent. Each fill uses its own quantity/price;
duplicates are ignored, inconsistent owned fills fault, and exit budgets are
bounded. The paper lane's governor budgets all actual submits and cancels.

`native-target-v1` fails closed with
`T15_native_order_capability_unqualified`. §6's pre-placed stop-limit, native
bracket/OCO/OTO/trailing and broker-replacement behaviors need T15's separate
order-contract and adapter acceptance. They are recorded as target plans and
are not silently substituted or reported as accepted. T22 edits no adaptive-paper
file. Overnight quote protection remains limited to sessions supported by its
existing XNYS/session helper; closed sessions are flagged for handoff.

## Synthetic acceptance

Use T13's unchanged runtime installed with `uv sync --locked` from
`ee3883699870d972058516192b1ee1c6e3ffb762`. Candidate screeners have their own
separate locked environment. Run only one heavy job at a time.

```sh
"$ENGINE_PYTHON" -m unittest tests.test_us_equities_strategies -v
"$ENGINE_PYTHON" -m blueprints.us-equities.strategies.simulation \
  --output blueprints/us-equities/strategies/synthetic-receipt.json
python3 scripts/validate.py
```

The matrix uses synthetic FactorSnapshot/QuoteTick data, the upstream
`OneTickSlippageFillModel` with a fixed seed and `StaticLatencyModel`.
Each family/preset has a receipt, along with non-cohort inverses and independently
registered hash-random, `momentum_20`, relative-volume and no-trade controls.
The short fixture has an explicit accelerated cleanup deadline; it tests engine
mechanics, not the multi-session strategy horizon. The LiveNode check reuses the
existing synthetic FakePort and tests individual partial fills and duplicate
wire deliveries for every family.

[synthetic-receipt.json](synthetic-receipt.json) contains each family/preset and
control result with fixture/trace hashes.
[test-acceptance.json](test-acceptance.json) binds the native checks to their
exact source bytes, including the reused adapter and FakePort.
[runtime-acceptance.json](runtime-acceptance.json) records the bounded unchanged
upstream wheel checks and the corrected type-stub/import-path findings.

[cts-acceptance.json](cts-acceptance.json) records the exact vendor install,
six upstream CI matrix checks, six inverse selections and verbatim skill-tree
hashes. These qualify reference screeners, not strategy efficacy or a numeric
decision-maker in the order path.

Historical Layer 1.5 E2E, same-input LEAN strategy-matrix reconciliation,
chronological evaluation, cost/delay sensitivities, overfitting controls,
T16 Pine parity and paper adoption remain separate gates. No strategy performance
number is cited. `run_analysis=False` suppresses performance statistics in these
acceptance receipts.

The later owner-dispatched vectorbt 1.1.2 Rust candidate is qualified separately
in a shared T13/T22 acceptance run, using exact published wheels and upstream
engine/parity/inverse checks. Its environment and licence override are recorded
apart from the strategy runtime. It may support future development sweeps; every
survivor must return to Nautilus/T13 before any strategy claim.
[vectorbt-acceptance.json](vectorbt-acceptance.json) records the precompiled
install, 41 unchanged vendor engine/parity checks and ten overlapping inverse
checks, with licence/owner override and resource limits.

## Restart and multiple instances

Each frozen `instance_id` is part of a hash over family, preset, instrument,
execution profile and cohort. The hash supplies both the configured StrategyId's
unique final tag and the order-ID tag. Different presets and named instances can
share a trader; deploying the same identity twice is refused by rc5. Instance
identity is stable across process restarts, and its sequence is restored at
`on_start` from the durable ledger's maximum matching intent suffix. Orders pass
an explicit `ClientOrderId` to upstream `OrderFactory.limit`; the existing paper
governor journals that ID before any broker request.

An unresolved intent or held position for the instrument refuses startup with a
named reconciliation flag. Terminal prior entry attempts also remain consumed
for that instance, preventing a restart from silently creating another entry.
Recovery stays with the existing paper lane. Development specifications require
a durable ledger; synthetic fixtures may use the explicit empty local boundary.

Standard/aggressive presets remain unqualified for paper overnight operation
until hana or T15 qualifies that session. The current helper treats 20:00–04:00
ET as closed and flags the position; it does not provide overnight exits. PRE
and POST retain the existing code-managed limit protections.

Regenerate the behaviour receipt with the repository generator in the unchanged
T13 runtime, then regenerate the companion matrix:

```sh
"$ENGINE_PYTHON" -m blueprints.us-equities.strategies.acceptance \
  --output blueprints/us-equities/strategies/test-acceptance.json
"$ENGINE_PYTHON" -m blueprints.us-equities.strategies.simulation \
  --output blueprints/us-equities/strategies/synthetic-receipt.json
```
