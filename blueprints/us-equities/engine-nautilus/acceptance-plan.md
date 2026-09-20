# Equity replay and separate broker acceptance plan

Planned September 20, 2026; **none of the stages below has executed**. The
[current target](../../../catalogs/us-equities/runtime-target.json) selects
NautilusTrader **2.0.0rc5**, source
`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`, native IBKR integration and a separate
Alpaca execution adapter. The [local and hosted acceptance](README.md) establishes
unchanged synthetic EUR/USD quickstart repeatability only. It does not establish
US-equity conversion, corporate actions, strategy quality, broker connectivity or
paper orders. LEAN results remain independent dated evidence.

This plan authorizes no connections or orders. Implementation and offline checks
can proceed within their assigned scope; broker-connected work requires the
particular account, permissions and order/risk scope to be authorized first.
No new framework, model in the execution loop or broad data acquisition is needed.

## 1. Freeze the retained equity comparison

Use the [SPY stress plan](../historical-simulation/plan.json),
[algorithm](../historical-simulation/HistoricalSimulationAlgorithm.cs),
[receipt](../historical-simulation/receipt.json) and
[independent LEAN analyzer](../historical-simulation/analysis.py). The receipt is
`native-historical-leverage-stress-20260919`, observed September 19 at 22:01:06 UTC.
Its LEAN source pin is `985ef30ad3ac774218c5ac516b4cb0aa2655730f`, with the recorded
three-package remediation and .NET 10.0.401. Preserve that variant and all six
outcomes; do not rerun or tune the historical baseline to fit Nautilus.

| Frozen artifact | SHA256 |
| --- | --- |
| Published baseline receipt | `06ec065647abd91a0ca2b13da25dd75c3ccd159a3244a241a3207c58b36f95d9` |
| Historical plan | `60959a050a3b004abf5346d376930b3b2f563096c725dc96e5427703ea203632` |
| Historical algorithm | `a8f0bf3c6b48fdcac8fe756ecb56611e6d54cbe90eeef29cdd901bb502eb1d15` |
| Current baseline analyzer | `cfe0f3411f9893bd76021e24f343888f538223608268ddf90f5a7d5aa7ea14c1` |
| `Data/equity/usa/hour/spy.zip` | `27af83adec03a3dff2bfda0d4edc077a5085f83a8b71f4ac156af3480e2e99d4` |
| `Data/equity/usa/daily/spy.zip` | `aaa1febad0cb8f91011212c92ff7caac6d4d6415a3b7f73c4b98c438db4274ad` |
| `Data/equity/usa/map_files/spy.csv` | `4765f330a156d4b0c521c094abf9747c4c7ccaf8e10c15ca50db16887d36d3cf` |
| `Data/equity/usa/factor_files/spy.csv` | `ad53e292de2e7076ff36721e1dcffd1db0d04fe6813b59aeece8620fb0d4cec1` |
| `Data/alternative/interest-rate/usa/interest-rate.csv` | `1d0e6f2ab20e61a4330e8a38735bc73cde4034e7293a45d23b5ebdc6467f7899` |

These are bundled upstream sample bytes, not an entitled vendor dataset or a
historically available universe. Obtain retained files and native outputs through
the receipt inventory. Fail on missing files or hash mismatch; do not substitute
a fresh provider download. Preserve raw outputs privately and publish appropriate
summaries/hashes. Verify retained LEAN outputs without launching an engine:

```sh
python3 blueprints/us-equities/historical-simulation/analysis.py --run "$PRIVATE_RUN"
python3 -m unittest tests.test_historical_simulation -q
```

The selected window is December 2, 2019–April 30, 2020: 104 daily rows, 725 hourly
rows and 104 expected XNYS sessions. LEAN processed 1,457 data points and recorded
725 hourly callbacks per case; internal event counts are not a required Nautilus
equality. Start with `one_zero`: $100,000 USD, raw prices, integer shares, no
fees/slippage/financing, entry decision December 31 at 16:00 New York and exit
decision April 29 at 16:00. Sizing is `floor(equity * target * 0.98 / price)` at
decision time. This known stress interval is never an untouched holdout.

## 2. Establish mappings before replay

The implementation owner must deliver a small converter, fixture strategy and
independent comparator, with exact argument arrays and hashes frozen before
execution. They do not exist yet. Use the installed 2.0.0rc5 low-level API,
as demonstrated by the [pinned upstream quickstart](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/getting_started/quickstart.py):
`BacktestEngine`, `add_venue`, `add_instrument`, `add_data`, `add_strategy`, `run`
and native report generation before `dispose`. The installed wheel's
`nautilus_trader/model/__init__.pyi` exposes `Equity` and `Bar`; its
`backtest/__init__.pyi` exposes venue fill, fee, margin and liquidation options.
The [pinned installation recipe](README.md) supplies the exact environment. Do
not substitute 1.x examples or invent a native equity-replay CLI.

Record every mapping below in a reviewed machine-readable manifest. An unresolved
mapping blocks its dependent comparison; it cannot silently receive a default.

| Mapping | Required decision and validation |
| --- | --- |
| Instrument identity | SPY, US equity, USD, explicit simulated venue and source map file; integer quantity and declared tick/price precision. The simulation identifier is not an IBKR contract ID or Alpaca asset ID. |
| Raw data decoding | Confirm ZIP member schema, price/volume units and raw normalization from the pinned LEAN reader; preserve original row keys and hashes. Reject malformed, duplicate, nonfinite or unexpected split records; no forward fill or adjusted-price substitution. |
| Sessions and time | Map local bar start/end to integer UTC nanoseconds using America/New_York and the frozen XNYS schedule. Check DST, partial sessions and ordering. Preserve event versus observation time; bundled history has no original availability attestation. |
| Decision visibility | A completed 16:00 bar may trigger an intent; no fill can use that same decision bar. Define equal-time event ordering and test future-row isolation. |
| Market-on-open proxy | LEAN fills discretionary orders at next-session 10:00 New York using the hourly bar's open, not a 09:30 auction. Establish whether pinned Nautilus semantics express this. Label any necessary reviewed fixture integration explicitly; a current-bar market order is not equivalent. |
| Distributions and cash | Derive each dividend amount/time and eligible holdings from retained action/audit evidence. Establish the native cash-posting mechanism before comparison; no invented balancing cash entry. Unexpected splits block this fixture. |
| Costs and rounding | Start at zero costs. Before `one_stress`, map $1/order and 20bp adverse slippage with an explicit rounding stage; LEAN exports more than two price decimals in that case. No post-result tolerance widening. |
| Margin and adaptive state | Later cases need equivalence to `SecurityMarginModel(2m)`, default margin-call timing/quantity, post-processing marks, hourly peak and one-way 5% drawdown latch, or an explicit unsupported finding. Nautilus defaults and its exposed liquidation option do not prove that equivalence. |

Conversion must preserve 104/725 rows, exact session membership, OHLC/volume after
declared unit decoding, and reviewed timestamps/actions, with no missing/extra
rows. Boundary tests reject bad hashes, duplicate timestamps, missing sessions,
unexpected splits, NaN values and look-ahead. Retain every exclusion/failure.
This converts a fixture; it does not make the data point-in-time or market-wide.

## 3. Replay and independent economic oracle

Run the frozen integration twice in fresh processes using accepted read-only
mounts, cleared environment, inaccessible account/home stores and a mandatory
network namespace. Capture commands, versions, input/source hashes, stdout/stderr,
exit codes, isolation proof and cleanup. Collect native orders, fills, positions
and account reports before disposal, plus a decision/distribution ledger. Missing
reports, unaccounted requests or isolation failures fail even with exit zero.

The comparator uses `Decimal` over exported values and matches reviewed economic
keys while retaining native IDs. For `one_zero`, require these exact events and
no extra orders or fills:

| Event | UTC seconds | Signed shares | Fill price USD |
| --- | ---: | ---: | ---: |
| Entry intent | 1577826000 | 304 | — |
| Entry fill | 1577977200 | 304 | 323.58 |
| Exit intent | 1588190400 | -304 | — |
| Exit fill | 1588255200 | -304 | 291.69 |

Instrument/currency, side, integer quantity, decision/fill times and decimal fill
prices must match exactly. Quantity starts and ends at zero. Independently compute
`cash = 100000 - sum(signed_fill_quantity * fill_price) - fees + distributions`
from actual fills/actions. Fees are zero, distributions total $428.64 and final
cash/equity is $90,734.08, a change of -$9,265.92. Check cash at every economic
event, cumulative quantity, the final native account and flat position. Trading
PnL excludes dividends: show the two separately, then reconcile their sum.

Arithmetic is exact on retained decimals. Native exported currency balances/equity
have **at most $0.01 absolute tolerance** per value, matching the baseline analyzer;
other economic fields above are exact. Document precision behind any nonzero
difference. Do not round every intermediate value or discard offsetting errors.

Both Nautilus runs must have equal economic records and ordering. Declare any
generated-ID normalization before execution, validate its format and retain raw
and normalized hashes. The FX verifier's UUID locations do not authorize dropping
equity fields. Timing, prices, quantities, fees, dividends, transitions and decision
order cannot be normalized away.

After `one_zero` passes, freeze separate mappings/checks for `one_stress`,
`two_zero`, `two_stress`, `adaptive_stress` and `over_limit` against each receipt
ledger. Check the leveraged cases' three margin liquidations each, the adaptive
case's single reduction and over-limit's one native buying-power rejection/zero
fills. Stressed costs change quantities; do not impose one shared fill schedule.
Unsupported behavior is a gap, not a pass. A new margin/fill policy needs a
separately named experiment and oracle, never a parity claim against this baseline.

Deliver mapping, conversion, two run and comparison receipts with pass/fail/blocked
status, exact commands, hashes and differences. Independent review reproduces the
comparison from retained outputs without engine/model calls. Equity fixture parity
still proves no alpha or broker behavior.

## 4. Offline broker-state failures

Before either paper adapter submits, implement one durable intent/order/fill journal
and deterministic risk checks per account scope. Exercise each adapter's boundary
with fake transport and injected clock/failures, no credentials or network.
Broker-specific ID/status mappings are explicit fixtures. These are **required
outcomes, not observed results**; no new fault runner is delivered by this plan.

| Deterministic case | Required result |
| --- | --- |
| Duplicate intent | Same intent twice: exactly one transport submission and durable intent. Reject changed payload under the same identity. |
| Accepted submission, lost response | Fake broker accepts then times out; journal becomes unknown. Retry/restart queries durable identity, adopts original order and submits zero additional orders. Unresolvable identity stays blocked. |
| Definitive rejection | Record reason and terminal rejection, zero fills/position change; no automatic retry under a new identity. |
| Partial and duplicate fills | For a 10-share buy, deliver fills 3 and 2, then replay the first event. Position is 5, remaining is 5; cash/fees change once per fill. Old cumulative status cannot reduce filled quantity. |
| Cancel race | From 5 filled, request cancel, then deliver a late 2-share fill and cancellation. Position is 7; remaining 3 is cancelled. A cancel request alone is never terminal. |
| Crash boundaries | Crash before send, after send before acknowledgement, and after fill before checkpoint. Replay journal and reconcile snapshots; unknown orders are never blindly resubmitted. Block new intents until reconciliation completes. |
| Stale/session/risk breach | Test threshold−1ns, threshold and threshold+1ns against a frozen age rule; closed session, exhausted cash/exposure and invalid/nonfinite inputs. Only explicitly allowed cases submit; rejected cases produce zero writes and a reason. |
| Rate exhaustion/disconnect | Exhaust a frozen fake budget; pause submissions, preserve cancel/reconciliation reserve and use bounded backoff. Missing stream events require snapshot reconciliation. Fake budget does not establish broker rate limits. |
| Snapshot contradiction | Unknown open order, position mismatch or missing fill blocks new intents and emits an alert until adjudicated. Never reset an account to make reports agree. |
| Kill switch | Independent of models; stops new submits and follows frozen cancel/retain policy, including cancel failures. Restart cannot silently clear it. |

Freeze numeric test limits and call budgets before execution. Each case retains
journal-before/after, injected sequence, transport calls, positions/cash and
expected-versus-actual assertions. Zero duplicate economic effects and zero
unexplained differences are mandatory; red/skipped cases block that adapter's
paper gate. Existing offline Alpaca guards accept only their own
[recorded scope](../acceptance-wave/README.md), not this new suite.

## 5. IBKR paper procedure

Prerequisites: passed offline suite; authorized paper account and numeric risk,
universe/session limits; native TWS or IB Gateway sign-in; socket API enabled;
explicit host/port and unused API client ID; qualified contract identity, trading
permissions and data subscriptions. Paper defaults are TWS `7497`, Gateway `4002`;
the adapter defaults to `127.0.0.1:4002`. Verify the actual paper application and
account before enabling execution. No IBKR sign-in/connection is established here.
[Official native integration guide](https://nautilustrader.io/docs/latest/integrations/interactive_brokers/).

Installed 2.0.0rc5 stubs expose `InteractiveBrokersDataClientConfig` and
`InteractiveBrokersExecutionClientConfig` in
`nautilus_trader.adapters.interactive_brokers`, with `host`, `port`, `client_id`
and execution `account_id`. Bind implementation to that pin. Keep credentials in
the native signed-in application; no copying into manifests or implicit gateway
container substitution.

1. Begin with read-only socket access and execution disabled. Retain sanitized
   paper-mode/account-scope verification, contract/currency/exchange, clock/session,
   quote source/type/age and positions/open-order snapshots. Unexplained existing
   orders/positions block progress. Delayed data requires explicit test permission.
2. Verify client-ID ownership and broker order/execution-ID mappings. Freeze maximum
   orders, shares/notional, exposure/loss, quote age, request rate, timeouts and
   observation window. Missing values/permissions block submission.
3. In a separately authorized paper run, execute only frozen bounded cases:
   submit/acknowledge, fill or cancel, reconnect with an open order and restart
   reconciliation. Retain actual responses and every outbound request. Unobserved
   partial fills/cancel races stay unobserved at the broker; do not relabel offline
   evidence or force events with added orders.
4. Stop at the declared boundary and apply the predeclared outstanding-order and
   position disposition. Reconcile snapshots, executions, commissions and account
   changes against the journal, including fee-posting timing. Exercise alert and
   kill-switch behavior without extra unapproved trades.

Pass requires every declared case's evidence, zero duplicate submissions/economic
effects, zero unexplained open-order/position/cash differences, no risk breach and
successful reconnect/restart recovery. Quantities/IDs match exactly; money follows
a predeclared currency/rounding and fee-posting rule. Missing fees, unresolved IDs
or skipped required operations stay blocked. Observed paper prices need not equal
the SPY fixture. The operator/reviewer must record actual pass/fail/blocked outcomes.

## 6. Alpaca paper procedure

Alpaca uses a **separate adapter**, not an upstream Nautilus plugin. Retain
`alpaca-py==0.44.0` read-only ingestion and its dated
[AAPL acquisition](../authenticated-data/README.md) and
[FB/META observations](../identity-readiness/README.md). A read-only account request
was previously recorded too. Credentials therefore cannot be described as absent;
current trading/data permissions and Elite activation remain unverified. No
credential store is read by this plan.

1. Use separately authorized private paper configuration and the SDK's
   `TradingClient(..., paper=True)` boundary. Verify paper endpoint/account with
   execution disabled; recheck restrictions/buying power, asset/session, selected
   feed and positions/open orders. Historical SIP GETs do not prove current
   real-time or Elite entitlements.
2. Freeze supported order serialization, durable `client_order_id` mapping,
   stream/status mappings, cancel/replace rules and an independently specified
   Alpaca risk/operation budget. One adapter owns writes. Unknown/dropped fields
   fail locally. The [advanced-instructions probe](../architecture/alpaca-probe.json)
   shows a serialization gap; DMA/VWAP/TWAP stays excluded until separate serialization
   and entitled-provider acceptance passes.
3. After its own offline suite and explicit paper-order scope pass, run bounded
   submit/fill-or-cancel, disconnect and restart cases. Reconcile stream and REST
   snapshots by stable client/broker identity. Use actual account request limits,
   reserving capacity for cancels/reconciliation. Elite's advertised 1,000 API
   calls/minute is not a fill rate or permission to load-test an account.
4. Stop and reconcile final order/position state, cash, fees and account events;
   retain unexpected states and redacted receipts. Apply zero-duplicate and
   zero-unexplained-difference/recovery criteria with separately frozen Alpaca
   currency, timing and status rules. Do not inherit an IBKR pass or interpret
   different paper fills as identical execution.

Follow the [official paper contract](https://docs.alpaca.markets/us/docs/paper-trading)
and [market-data permissions](https://docs.alpaca.markets/us/docs/about-market-data-api).
Paper omits material live-market effects. Report each adapter's scoped outcome
separately; neither result authorizes live trading, establishes capacity or
validates profitability.
