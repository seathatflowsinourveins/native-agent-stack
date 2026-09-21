# Retained AAPL replay on native NautilusTrader

The local integration in [run.py](run.py) exercises native
`NautilusTrader 2.0.0rc5` equity execution with 15 retained AAPL daily raw bars,
five fixed roundtrips and final flatness. It advances the existing synthetic
EURUSD-only engine evidence. It does not complete the separate planned SPY/LEAN
parity matrix, validate a trading strategy, or qualify Alpaca/IBKR execution.

The [frozen plan](plan.json) selects August 10–28, 2020, after the recorded August 7
dividend and before the August 31 split. The source is the previously authenticated
[Alpaca acquisition](../../authenticated-data/README.md), anchored to receipt
`a59c6ed74e839ca43ee704033e207865ed938a22e4738afce22ec197e91b6bcd`.
The existing collector verifies every retained body, request/page assessment and
source anchor before any replay. No new data request or credential access occurs.
The interval excludes the recorded actions; full action coverage, original
publication/revisions and historically known identity/universe remain unproven.

Each scenario starts with $100,000 simulated USD cash. It buys ten shares on
bar indices 0/3/6/9/12 and sells ten on 1/4/7/10/13, leaving one final observation.
The baseline uses zero fees and the native default fill model. The stress uses
the native `FixedFeeModel` at $1 per order and `OneTickSlippageFillModel` at one
adverse $0.01 tick per fill. The observed results, repeated in fresh isolated
processes, are:

| Case | Filled orders | Closed roundtrips | Fees | Realized PnL | Ending cash |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | 10 | 5 | $0 | -$133.40 | $99,866.60 |
| Fee/slippage stress | 10 | 5 | $10 | -$144.40 | $99,855.60 |

Every fill matches the frozen date/quantity/side and raw close plus its declared
slippage. Every native cash transition and total realized PnL reconciles with
independent Decimal arithmetic. Both cases finish with zero open orders and
positions. These are losing diagnostics, retained without tuning the schedule.
See [receipt.json](receipt.json) for exact result hashes, command outcomes and
source pins. Account CSVs repeat byte-for-byte; selected economic fill fields,
cash sequences and position PnL match across runs. Generated identities are not
claimed to repeat.

## Execution and liquidity boundaries

This is a retrospective schedule, with completed daily OHLCV assigned to a
16:00 New York diagnostic event. Native market orders fill against the current
completed bar price. It is not an executable closing-auction strategy or a
claim that the provider's final daily values/revisions were available then;
possible extended-session contributions are not separated. No historical signal,
forward test or profitability threshold is evaluated.

The local admission rule limits ten shares to at most 0.01% of each day's
reported volume. This is a scale check, not proof of contemporaneous liquidity.
The stress explicitly enables native `liquidity_consumption`, but pinned
`OneTickSlippageFillModel` constructs a synthetic **unlimited-liquidity** L2 book.
Thus finite liquidity, queue position, partial fills, spread dynamics, impact,
auction execution, halts, rejects and broker/session restrictions are unaccepted.
No borrowing, shorting, dividends, splits, financing or tax model is exercised.

## Reproduce on a configured host

Use the existing pinned Nautilus environment and retained authenticated input.
The output must be a fresh private directory; never publish its raw reports.

```sh
python3 blueprints/us-equities/engine-nautilus/equity-replay/launch.py \
  --python "$NAUTILUS_ENV/bin/python" \
  --run "$RETAINED_ALPACA_RUN" \
  --out "$FRESH_PRIVATE_RUN"
python3 -m unittest tests.test_nautilus_equity_replay -v
```

The launcher reuses the prior upstream-acceptance Bubblewrap isolation: mandatory
new network namespace, cleared environment, read-only runtime/repository/data,
and only an owned output mount. It records exact argv, start/end, exit code and
stdout/stderr with hashes. The child sees only loopback and no credential variables.
There is no network-enabled fallback or broker client. The direct runner exists
for source inspection; the recorded acceptance uses the isolated launcher.

Eight local tests exercise missing/duplicate/reordered sessions, source/action
refusals, price/volume precision, participation, changed fill semantics, duplicate
identity, currency/fees, intermediate cash corruption and final position/PnL.
Those synthetic negative fixtures are local checks, not unchanged upstream tests.
Native integration runs use the retained historical bars. Pandas 3.0.6 warns
that epoch JSON date formatting is deprecated; its warnings and successful native
results are retained. This integration deliberately pins its tested runtime.

## Source choice and review

The bounded gap was historical equity execution on the already-selected engine.
Reusing native `Equity`, `BacktestEngine`, `Strategy`, reports and fee/fill models
avoids a second execution engine or custom order matcher. The official quickstart
and installed v2 interface stubs were inspected before implementation. The v1
module layout does not apply to v2. Upstream source is pinned at
[`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`](https://github.com/nautechsystems/nautilus_trader/tree/1b0a49d2792a9432a3aca3fcb617ce7a630d905e):

- [Official quickstart](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/getting_started/quickstart.py): native strategy, engine and report APIs.
- [Fill models](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/execution/src/models/fill.rs): one-tick model and unlimited synthetic depth.
- [Fee models](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/execution/src/models/fee.rs): native fixed commissions.

The earlier unchanged quickstart acceptance is reused for its original scope;
this diagnostic is explicitly local integration. Independent coordinator source
review required renaming the original `cost_liquidity_stress` label because it
could imply finite-liquidity qualification. The final `fee_slippage_stress` name
and limitations resolve that finding. Prior successful development runs remain
private alongside the final reviewed runs. No failed native execution was hidden.
The separate reviewer independently passed the eight local tests, checked all
source/output hashes and actual native exit codes, and recalculated every CSV
cash transition, fee and position PnL in both final scenarios and repetitions.
No further supported findings remained. Repository and catalog validators passed.
