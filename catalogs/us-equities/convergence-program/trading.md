# Trading, data and evaluation convergence — September 19, 2026

This continuation makes **14 bounded repository decisions**: 11 fresh reviews of
selected source sections, one retained LEAN acceptance and two metadata-only
leads. Forty pinned implementation, test, documentation and license files are
recorded in the [machine-readable review](trading.json). It also closes a narrow
offline gap through [native nanosecond replay](../../../blueprints/us-equities/nanosecond-replay/README.md).
These are evidence levels, not fourteen installed or working trading systems.

## Decisions

| Repository | Decision and practical boundary |
| --- | --- |
| [QuantConnect/Lean](https://github.com/QuantConnect/Lean) | Retain primary offline engine and previous native fee/slippage acceptance. Current broker margin rules require separate verification. |
| [QuantConnect/Lean.Brokerages.Alpaca](https://github.com/QuantConnect/Lean.Brokerages.Alpaca) | Retain adapter path; history/order methods and tests reviewed. Account, session, advanced orders and current margin equivalence remain unaccepted. |
| [alpacahq/alpaca-py](https://github.com/alpacahq/alpaca-py) | Retain SDK; preserve raw timestamp payloads before its normal datetime conversion. Existing request-model acceptance is separate from a connected raw-data adapter. |
| [duckdb/duckdb](https://github.com/duckdb/duckdb) | Retain integer temporal replay. Existing 1.5.5 executed the new synthetic SQL/Parquet acceptance. |
| [pandas-dev/pandas](https://github.com/pandas-dev/pandas) | **Add an already installed dependency to the catalog.** Existing 3.0.6 supplies guarded exact UTC nanosecond parsing. |
| [apache/arrow](https://github.com/apache/arrow) | Keep conditional interchange candidate; inspect timestamp coercion on both writer and reader. No installation required for this acceptance. |
| [skfolio/skfolio](https://github.com/skfolio/skfolio) | Retain chronological evaluation candidate; the full event/group/trial/selector policy still needs frozen evaluation. |
| [databento/dbn](https://github.com/databento/dbn) | **Add conditional record-format reference.** Event/capture clocks, source sequence, flags and undefined sentinels improve the future ingestion specification. No data rights inferred. |
| [databento/databento-python](https://github.com/databento/databento-python) | Retain conditional provider SDK; conversions and mapping intervals reviewed. No key or paid historical request used. |
| [stefan-jansen/zipline-reloaded](https://github.com/stefan-jansen/zipline-reloaded) | Keep asset-lifetime/universe semantics reference. Lifetimes alone do not establish when membership information was known. |
| [cvxgrp/cvxportfolio](https://github.com/cvxgrp/cvxportfolio) | Keep turnover/impact-cost challenger; current GPL-3.0-or-later headers and calibration need deliberate integration review. |
| [deepcharles/ruptures](https://github.com/deepcharles/ruptures) | **Add offline regime diagnostics only.** Full-series segmentation cannot guide earlier decisions. |
| [hmmlearn/hmmlearn](https://github.com/hmmlearn/hmmlearn) | Metadata-only regime lead; source, causal filtering and current maintenance need review. Not adopted. |
| [stumpy-dev/stumpy](https://github.com/stumpy-dev/stumpy) | Metadata-only motif/anomaly lead; GitHub license metadata is unresolved and causal-window evaluation is unreviewed. Not adopted. |

Each JSON entry retains the reviewed commit, archive/license metadata, prior
index membership, source URLs, exact `gh api` argument arrays and next acceptance.
Reviewing upstream main does not upgrade an installed package. GitHub's absent
license metadata for the Alpaca adapter was resolved only for selected source:
its pinned README and code headers state Apache-2.0; bundled dependencies remain
a separate consideration.

## Findings that change the next work

The [SDK cast](https://github.com/alpacahq/alpaca-py/blob/232179c19091fd0f70daf0972a90bf8def329ec0/alpaca/data/live/websocket.py#L283)
returns the original message when `raw_data=True`; its normal path converts
timestamp values to Python datetime. Keep raw msgpack seconds/nanoseconds and
source identity before deriving models. This source review did not connect a
WebSocket or validate a production capture adapter.

[Arrow's writer](https://github.com/apache/arrow/blob/c07de67a7c9a43c7c958ffeb08407b66c38df5b5/python/pyarrow/parquet/core.py#L789)
supports nanoseconds with Parquet 2.6 and has explicit coercion controls.
[DuckDB](https://duckdb.org/docs/current/sql/data_types/timestamp) warns that a
timezone-aware nanosecond Parquet column can become microsecond TIMESTAMPTZ.
The new acceptance therefore uses original timestamp text and signed integer
UTC nanoseconds throughout SQL/Parquet; output JSON uses decimal strings.

[DBN records](https://github.com/databento/dbn/blob/aa012adc6502e01b01d7b5c7836742dde21e93d8/rust/dbn/src/record.rs)
distinguish event and capture-server receive time and preserve sequence/flags.
The unsigned timestamp domain and undefined values require explicit conversion
rules before any signed-int64 adapter. Provider capture time is not this user's
historical receipt time. SDK and format licenses do not grant dataset rights.

[Zipline lifetimes](https://github.com/stefan-jansen/zipline-reloaded/blob/943010b9da848e317fc520de87edade2b884d329/src/zipline/assets/assets.py#L1419)
make first-day inclusion explicit. [Cvxportfolio costs](https://github.com/cvxgrp/cvxportfolio/blob/351c782b9b8b395c1a5f886b77e0d55f1bc9396e/cvxportfolio/costs.py#L750)
use traded quantity and distinguish forecast volume during optimization from
realized simulation volume. These are useful controls for complete candidate
universes and strategy switching; neither provides the needed data automatically.

[ruptures](https://github.com/deepcharles/ruptures/blob/ee1c8ff8a548d54c641b2bb471562165931f31c7/README.md)
is explicitly offline change-point detection. It may support development
diagnostics, but causal regime selection still needs fixed fitting windows,
declared detection delay, hysteresis, no-fit/stale states and nested chronological
evaluation of the entire strategy pool. No regime model was trained here.

## Native result

The new [receipt](../../../blueprints/us-equities/nanosecond-replay/receipt.json)
contains **10 command exits**. Inside one microsecond, cutoff nanoseconds
`1738443600000000100` select original value 100; `...0200` selects correction 90
and newly effective member 200; `...0201` selects the higher same-clock source
sequence, value 85. Replaying `...0100` returns original 100 again.
Precision overflow, range overflow, overwrite and corruption each reject.

Twelve focused checks passed using the existing pandas/DuckDB environment.
The [native commands](../../../blueprints/us-equities/nanosecond-replay/README.md#native-replay)
execute upstream timestamp conversion, typed SQL and Parquet APIs. No new
dependency was installed. Value strings are opaque; this is not price-validation,
historical +200% research, authenticated availability or broker acceptance.

## Simulation, paper and later live progression

Keep lane identities and evidence separate. Simulation may explore a declared
leverage stress grid such as 1x, 1.5x, 2x, 3x and 4x with financing, adverse gaps,
concentration, margin changes and forced-deleveraging scenarios. Hypothetical
stress cases outside account limits remain labeled infeasible. No such strategy
stress experiment ran in this wave.

Paper uses actually received source versions, measured latency, feed coverage and
the selected account's current buying power, asset/borrow and session rules.
The same factor definitions can be compared across lanes only when differences
in information, costs and execution are retained. Automatic leverage must stay
inside declared risk caps and actual account capacity; a multiplier is not a
position-size instruction.

Alpaca's [current margin page](https://docs.alpaca.markets/us/docs/margin-and-short-selling)
describes conditional intraday/overnight buying power and security/house margin
requirements. Its [June 4, 2026 update](https://alpaca.markets/blog/finra-retires-the-pdt-rule-introducing-alpacas-new-intraday-margin-framework/)
removed old PDT/count/$25,000 logic and directed integrations toward current
`buying_power`; legacy day-trading fields were scheduled for July 6 removal.
Old versioned documentation and an engine's historical PDT model cannot prove
today's broker behavior. This wave did not inspect an account.

[Paper documentation](https://docs.alpaca.markets/us/docs/paper-trading) says fills
are not constrained by displayed NBBO quantity and dividends are not simulated.
Paper results therefore do not establish live depth, impact or capacity. Later
live progression requires separate frozen criteria, forward evidence, complete
order-state reconciliation, monitoring/recovery and explicit live authority.

## API counts and historical rights

The current [Elite comparison](https://alpaca.markets/elite) lists **200 and 1,000
API calls per minute**, with routing eligibility, fees and personal-use data
terms. These count requests, not trades or fills. Qualifying does not automatically
switch routing. No Elite or paper-account entitlement was verified here.

The [Market Data API table](https://docs.alpaca.markets/us/docs/about-market-data-api)
separately lists Basic/Algo Trader Plus historical limits of **200/10,000 requests
per minute**, different real-time coverage and subscription limits. The
[FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) distinguishes IEX from
SIP, recent-history restrictions, OTC access and symbol mapping. A historical
API, public client or plan name does not grant unlimited acquisition,
redistribution or complete delisted/extreme-mover coverage.

## Two-round stopping evidence

Round one reviewed seven incumbents/dependencies and 20 source files. It located
the precision boundary and selected an existing-package acceptance. Round two
considered seven challengers/leads and 20 further files, adding three source-reviewed
identities across the whole wave and keeping two leads at metadata-only depth.
Root's starred/awesome-list refresh is separate; this lane claims neither all-star
coverage nor an exhaustive landscape.

The remaining work needs accepted original source versions, complete candidate
replay, factor/control comparisons, selector transitions, simulation stresses and
paper lifecycle receipts. More repository names would not close those gates.
