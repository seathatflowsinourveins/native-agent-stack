# US-equity engines, strategies and research evaluation

Checked **2026-09-19** for an Alpaca-paper, research-first system. The [structured catalog](engines-strategies.json) records **40 repositories**: 7 defaults, 10 conditional additions, 13 alternatives, 8 watch items and 2 exclusions. These are decisions for this project, not a universal ranking or a claim that a strategy is profitable.

**Current selection, reconciled September 22:** the [runtime target](runtime-target.json)
selects NautilusTrader **2.0.0rc5** (tag `v2.0.0rc5`; source pin
`1b0a49d2792a9432a3aca3fcb617ce7a630d905e` from
[`evidence/receipts/native-nautilus-v2-20260920.json`](../../evidence/receipts/native-nautilus-v2-20260920.json))
as the **selected destination runtime**, with native IBKR and a separate Alpaca
path; LEAN is retained as the **frozen historical comparator (oracle), not the
runtime**. Two broker-adapter cards were added at this reconciliation:
`nautilus-ibkr-adapter` (same engine pin, `local_broker_acceptance` `not_established`)
and `adaptive-paper-alpaca-adapter` (custom deterministic adapter in
`blueprints/us-equities/adaptive-paper`, source-reviewed with the synthetic
capacity fixture cited, no live broker fills claimed). The installed skfolio
**1.2.9** acceptance covers its chronological splitter/control study. The earlier
1.231.0 source review is historical, superseded for installation by the
[dated R&D readiness decision](../../docs/foundation-rd-readiness.md). NautilusTrader
remains prerelease: 2.0.0 final has not shipped, and the SPY/LEAN parity gate
**G-a** (`retained-equity-replay`) is recorded as
`reported_execution_blocked_review_incomplete` in
[`runtime-target.json`](runtime-target.json) `next_acceptance`: the retained
[comparison summary](../../evidence/artifacts/comparison-progress-20260922/summary.json)
records a completed **BLOCKED** replay of the historical one_zero case with four
failed checks on the unsupported `distributions_and_cash` and
`market_on_open_proxy` mappings; a completed blocked comparison is not parity
acceptance. The verdict and its 29 checks are on main under
`blueprints/us-equities/engine-nautilus/spy-parity/`; closing the gate needs an
engine-native market-on-open and dividend-cash mechanism or a newly
preregistered mapping manifest (gate `dividend-sim-module`).
The current target also records bounded AAPL replay and Alpaca paper evidence;
neither establishes SPY parity, a strategy edge or complete broker recovery.

At the original September 19 source review, one entry had native execution evidence: LEAN's bundled C# backtest. The other 37 had primary-source review, including README/license review and selected API/source inspection; none was installed, connected to a broker, trained or benchmarked for that review. Later native acceptance is linked by the current selections above. A source-reviewed adapter is not an accepted paper-trading integration.

## The September 19 default stack (historical)

Retain **LEAN**, add its **official Alpaca brokerage adapter** only after the data and risk gates below, use **alpaca-py** for independent account/order reconciliation, and use **QuantStats** to render an explicitly defined return series. The strategy engine should be the only order writer. A separate read-only observer can compare the engine's journal with broker orders, executions, positions and cash.

The existing [LEAN receipt](../../blueprints/us-equities/engine/receipt.json) proves a pinned source build and an unmodified `BasicTemplateFrameworkAlgorithm` run over bundled SPY minute data from October 2013. It completed with 3,943 data points and three simulated orders. It used the default brokerage model, **not Alpaca**, and establishes neither current data quality nor investment performance. Restore reported seven advisory/package pairs across five runtime packages, including high/critical classifications. The [later pinned local patch](../../blueprints/us-equities/engine/resolution.md) removed all seven reported pairs from the accepted launcher graph, with zero vulnerable packages in both checked runtime audits. Exploitability and whole-system security were not certified. The [engine recipe](../../blueprints/us-equities/engine/README.md) retains the exact commands and limitations.

This source-build route is distinct from the [LEAN CLI workflow](https://www.quantconnect.com/docs/v2/lean-cli/key-concepts/getting-started), which requires Docker and paid-organization membership under the documented setup. Do not silently substitute that service workflow for the accepted native source build.

The selected [Alpaca adapter factory](https://github.com/QuantConnect/Lean.Brokerages.Alpaca/blob/1973f6165bee212acf656ed2f9cb0af86d4f2a18/QuantConnect.AlpacaBrokerage/AlpacaBrokerageFactory.cs) reads the paper setting. Its build and paper connection remain unexecuted. LEAN's documented Alpaca brokerage model uses `NullSlippageModel`; realistic costs must therefore be deliberately supplied and calibrated. [Brokerage-model documentation](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/brokerages/supported-models/alpaca).

`alpaca-py` supports paper mode, order queries and trade updates. It is a useful reconciliation interface, not exactly-once order delivery or a durable journal by itself. On an ambiguous submission timeout, do not blindly repeat the order; first establish its broker state and follow the broker's resolution guidance. [SDK source](https://github.com/alpacahq/alpaca-py/blob/v0.44.0/alpaca/trading/client.py), [order guidance](https://docs.alpaca.markets/us/docs/working-with-orders).

## Engine and broker choices

Versions below retain the reviewed snapshots, not current installation instructions
or a promise that every dependency resolves together. Each JSON entry contains its
repository, license, source URLs, requirements and prospective commands. Use the
current runtime target above for the selected engine.

| Catalog ID | Selected version or source | Decision | Reason and boundary |
| --- | --- | --- | --- |
| `lean` | `985ef30` | Default | Frozen historical comparator (oracle), not the runtime; SPY/LEAN parity gate G-a is planned/blocked. |
| `lean-alpaca` | `1973f61` | Default | Official broker adapter; source/build recipe, no accepted paper session. |
| `alpaca-py` | 0.44.0 | Default | Official SDK for read-only broker-state observation and market-data interfaces. |
| `nautilustrader` | `2.0.0rc5` (tag `v2.0.0rc5`; source `1b0a49d2792a9432a3aca3fcb617ce7a630d905e`) | Default | Selected destination runtime (runtime-target.json). Prerelease; SPY/LEAN parity gate G-a completed BLOCKED (four failed checks on the two unsupported mappings; not parity acceptance; per-check verdict retained under `blueprints/us-equities/engine-nautilus/spy-parity/`). Historical `1.231.0` source review below is superseded. |
| `nautilus-ibkr-adapter` | same pin as `nautilustrader` | Default | Native IBKR socket adapter; `local_broker_acceptance` `not_established` (runtime-target.json). |
| `adaptive-paper-alpaca-adapter` | `7e7eefe28315f3de3aa4dc75cc8b6524f70829cb` (`blueprints/us-equities/adaptive-paper`) | Default | Custom deterministic Alpaca adapter for the adaptive-paper lane; source_review with the synthetic capacity fixture cited (180 fills / 90 round trips in 60.4282s, zero broker connections); no live broker fills claimed. |
| `lumibot` | 4.5.91 | Alternative | Direct Python strategy lifecycle and Alpaca broker; unresolved GPL/MIT license metadata conflict. |
| `vectorbt` | 1.1.0 | Alternative | Array-based research sweeps; recheck selected hypotheses in the event engine. |
| `backtrader` | 1.9.78.123 | Alternative | Useful for existing research; package and broker integration age require care. |
| `backtesting-py` | 0.6.6 | Alternative | Small single-instrument prototypes; not the multi-asset broker-state authority. |
| `zipline-reloaded` | 3.1.1 | Alternative | Maintained Zipline/Pipeline research, with explicit data-bundle ingestion. |
| `bt` | 1.2.3 | Alternative | Convenient allocation/rebalance comparisons; no broker execution in this workflow. |
| `ib-async` | 2.1.0 | Alternative | Community IBKR client only if the broker choice later changes. |
| `alpaca-backtrader-legacy` | 0.15.0 | Excluded | Old SDK/data assumptions; README's default is live, not paper. |

The paragraph below is the historical `1.231.0` source review, retained for context; the current selected destination and its IBKR/Alpaca broker cards are the `2.0.0rc5` rows above. Nautilus's stable `1.231.0` source included Interactive Brokers and Databento adapters, but no Alpaca adapter. Its v2 Rust/PyO3 development documentation must not be mixed into a 1.231.0 implementation. The catalog's AAPL example requires separately supplied Databento files; it is not an account-free data promise. [Stable adapter tree](https://github.com/nautechsystems/nautilus_trader/tree/v1.231.0/nautilus_trader/adapters), [example](https://github.com/nautechsystems/nautilus_trader/blob/v1.231.0/examples/backtest/databento_ema_cross_long_only_aapl_bars.py).

Lumibot is the most direct reviewed Python-first alternative for reusing a strategy class between historical simulation and Alpaca paper trading. However, its release [LICENSE](https://github.com/Lumiwealth/lumibot/blob/v4.5.91/LICENSE) and [setup metadata](https://github.com/Lumiwealth/lumibot/blob/v4.5.91/setup.py) disagree. Resolve that before adoption. Some current agent examples also invoke model services and enable trading; the catalog deliberately supplies only a deterministic backtest example.

Vectorbt's public edition is Apache-2.0 **with Commons Clause**, not unrestricted Apache-only software. VectorBT PRO is a separate private commercial product, not another audited open repository; the site advertised 2026.9.5 when checked, but its private implementation was not reviewed. [Public license](https://github.com/polakowo/vectorbt/blob/v1.1.0/LICENSE.md), [PRO terms](https://vectorbt.pro/terms/software-license/).

## Portfolio construction and statistical evaluation

Start with a transparent benchmark and unambiguous accounting. Add an optimizer only when its constraints and objective answer a specific question. Do not install every overlapping report or allocation library.

| Catalog ID | Version | Decision | Useful responsibility |
| --- | --- | --- | --- |
| `quantstats` | 0.0.81 | Default | Return-series report with explicit frequency, benchmark and net-cost accounting. |
| `pyportfolioopt` | 1.6.0 | Alternative | Covariance/shrinkage and conventional constrained portfolio weights. |
| `riskfolio-lib` | 7.3.0 | Alternative | Broader risk measures and allocation formulations when required. |
| `skfolio` | 1.2.9 accepted splitter; 1.2.8 earlier review | Conditional beyond accepted scope | Native chronological splitter/control study is accepted; portfolio optimization and broader validation remain separate. |
| `cvxportfolio` | 1.5.1 | Conditional | Cost-aware, multi-period allocation research. |
| `empyrical-reloaded` | 0.5.12 | Conditional | Reusable metrics where a report is insufficient. |
| `ffn` | 1.2.2 | Alternative | Lightweight price/return analytics, especially alongside `bt`. |
| `statsmodels` | 0.15.0 | Conditional | Regression, residual, stationarity and econometric baselines. |
| `arch` | 8.0.0 | Conditional | Volatility, block-bootstrap and multiple-comparison research. |
| `alphalens-reloaded` | 0.4.6 | Conditional | Factor IC, forward-return, turnover and group diagnostics. |
| `empyrical-legacy` | 0.5.5 | Excluded | Prefer the maintained fork; both use the `empyrical` import namespace. |

`skfolio` exposes walk-forward and purged/embargoed split parameters, but the relevant parameters default to zero. Derive the exclusion window from label overlap and order timing; calling a splitter does not independently prove leakage-free evaluation. [Walk-forward source](https://github.com/skfolio/skfolio/blob/v1.2.8/src/skfolio/model_selection/_walk_forward.py), [combinatorial source](https://github.com/skfolio/skfolio/blob/v1.2.8/src/skfolio/model_selection/_combinatorial.py).

`cvxportfolio` expects return at time *t* to describe the following open-to-open interval. That differs from many reporting tables. Its local recipe supplies an explicit final cash-return column to avoid an implicit risk-free-data download, and intentionally starts with no costs to expose the API. That recipe is **not** a cost-calibrated acceptance run. Its source is GPL-3.0-or-later. [Simulator contract](https://github.com/cvxgrp/cvxportfolio/blob/1.5.1/cvxportfolio/simulator.py).

Metrics do not replace accounting checks. A daily return win rate differs from a trade win rate; annualization depends on actual observation frequency; a gross Sharpe differs from a net, financing-adjusted result. Factor information coefficients omit much of execution feasibility. Keep forward returns in offline labels only. [QuantStats implementation](https://github.com/ranaroussi/quantstats/blob/v0.0.81/quantstats/reports.py), [Alphalens IC implementation](https://github.com/stefan-jansen/alphalens-reloaded/blob/f0a07c22d554e4b4036983cc80320b432714fe7e/src/alphalens/performance.py).

## ML, forecasting and financial agents

| Catalog ID | Selected snapshot | Decision | Role and adoption condition |
| --- | --- | --- | --- |
| `scikit-learn` | 1.9.1 | Conditional | Fold-local classical supervised baselines before complex learners. |
| `qlib` | 0.9.7 | Conditional | Experiment/factor workflows after a US point-in-time dataset exists. |
| `statsforecast` | 2.1.1 | Alternative | Classical forecasting baselines for a defined target. |
| `sktime` | 1.1.0 | Alternative | Temporal estimator/pipeline interoperability when needed. |
| `darts` | 0.47.0 | Alternative | Unified forecasting/anomaly APIs; overlaps other wrappers. |
| `neuralforecast` | 3.2.2 | Watch | Neural forecasts only after simpler baselines justify the added search space. |
| `timesfm` | source v3.0.0; 2.5 model | Conditional | Generic forecasting baseline using eligible 2.5 weights, not 3.0 production use. |
| `chronos` | library 2.3.2; Chronos-2 model | Conditional | Probabilistic forecasts with explicit target, dates and baseline comparison. |
| `mlfinpy` | 0.1.2 | Watch | Selected financial-labeling/sampling helpers after method review. |
| `finrl` | `2334a5f` | Watch | Educational RL experiments; rewards and simulated gains are not execution proof. |
| `finrl-x` | `4409abe` | Watch | FinRL-Trading successor; inspect target weights/executor, independently prove operations. |
| `fingpt` | `cefb3a2` | Watch | Timestamped text features or research assistance, not an order authority. |
| `ai-berkshire` | v1.0.0 | Watch | Company-research/checklist prompts; no verified valuation or trading result. |
| `tradingagents` | v0.5.0 | Watch | Dated multi-agent research experiment; no accepted broker/risk runtime. |
| `dexter` | v1.0.5 | Watch | Financial-source gathering and questions; upstream excludes real trading use. |

QLib supports US configuration, but the reviewed Alpha158/LightGBM workflow defaults to China: CSI300, SH000300 and China-style limits/costs. A US adaptation must replace those assumptions, calendars, universe, data and train/test periods. The command in the catalog requires an already reviewed US configuration; it does not download an unspecified dataset. [Pinned workflow](https://github.com/microsoft/qlib/blob/v0.9.7/examples/benchmarks/LightGBM/workflow_config_lightgbm_Alpha158.yaml).

For TimesFM, the source and 2.5 weights use Apache-2.0, whereas the newer 3.0 weights carry a separate non-commercial license that excludes production use. The catalog therefore pairs reviewed v3.0.0 code, which retains the 2.5 API, with `google/timesfm-2.5-200m-pytorch`. PyPI 3.0.2 was observed but its source/API was not separately audited. [Source README](https://github.com/google-research/timesfm/blob/v3.0.0/README.md), [2.5 model card](https://huggingface.co/google/timesfm-2.5-200m-pytorch).

Chronos-2's `amazon/chronos-2` model announcement was October 20, 2025; the library's 2.3.2 release was September 8, 2026. These are different artifacts and dates. Its prospective example explicitly names the ID column and uses local CPU inference. Both model recipes still require weight revision pins before reproducibility claims, and neither was downloaded or run here. Generic forecasting results are not evidence of equity alpha. [Chronos source](https://github.com/amazon-science/chronos-forecasting/blob/v2.3.2/README.md), [model card](https://huggingface.co/amazon/chronos-2).

FinRL's current source directs deployment work toward FinRL-Trading; neither its older PyPI wheel nor that successor's production wording establishes accepted deployment here. FinGPT's package, source and base-model licenses are separate concerns. Financial agents may produce hypotheses, citations and bounded research artifacts. An LLM debate or a role named “risk manager” is not deterministic pre-trade risk control. Recent-star coverage includes [ai-berkshire](https://github.com/xbtlin/ai-berkshire/tree/v1.0.0), [TradingAgents](https://github.com/TauricResearch/TradingAgents/tree/v0.5.0) and [Dexter](https://github.com/virattt/dexter/tree/v1.0.5) as individual structured watch entries, not installed trading systems.

## September21 adaptive practice extension

The [adaptive paper lane](../../blueprints/us-equities/adaptive-paper/README.md)
wires five baseline policy families through the actual Nautilus2.0.0rc5 LiveNode
and a custom official-SDK Alpaca boundary. Its local synthetic capacity and
unchanged upstream adapter tests are distinct from actual broker acceptance.
The bounded dated news/snapshot collector feeds an advisory research queue;
Claude source-support review does not enable catalyst orders or qualify alpha.
See its [receipt](../../blueprints/us-equities/adaptive-paper/receipt.json) for
observed results, exact source versions and unresolved market-open qualification.

## Strategy families to evaluate as hypotheses

| Family | First comparison | Data and main failure mode |
| --- | --- | --- |
| Passive/allocation baseline | Buy-and-hold, equal weight, cash; monthly rebalance | Total-return accounting, membership changes and rebalance costs. |
| Trend/momentum | Fixed simple rule versus passive exposure | Lag every input; distinguish market beta from incremental return; turnover and gap risk. |
| Mean reversion/pairs | Simple residual/reversion model | Stationarity can fail; selection, borrow and asynchronous prices matter. |
| Cross-sectional factors | Single preregistered factor and neutralized variants | Point-in-time constituents, delistings, sector exposures, publication timestamps and turnover. |
| Risk/volatility targeting | Constant exposure versus volatility-scaled exposure | Forecast calibration, jumps, lagged vol estimates, leverage and financing. |
| Supervised prediction | Regularized model versus naive/linear baseline | Fold-local preprocessing, label overlap and repeated model/feature selection. |
| Text/fundamentals | Auditable lagged feature versus price-only baseline | Publication time, later restatements, source availability and model pretraining contamination. |
| RL/foundation models | Simple supervised/classical models first | Reward misspecification, simulator exploitation, search budget and uncertain pretraining overlap. |

These families describe research questions. No parameter, security selection, forecast or expected return in this catalog is an investment recommendation. Account-free examples on airline data, bundled historical bars or synthetic series inspect APIs; they are not disguised financial benchmarks.

## Gates before paper execution

1. **Data contract.** Freeze licensed sources, instrument identifiers, trading calendar/timezone and adjustment policy. Retain event time and actual availability time, point-in-time constituents, delistings and corporate actions. Record missing/stale bars and revisions. Ensure features are available before the intended order time, not merely dated to the same day.
2. **Chronological experiment design.** Reserve a final untouched period. Keep feature fitting, imputation, normalization and selection inside each training fold. Purge overlapping labels and embargo as justified by the horizon. `TimeSeriesSplit(gap=1)` in the sample is illustrative, not universal. [Temporal split contract](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html).
3. **Search accounting.** Register the hypothesis, all attempted variants and compute budget. Compare the chosen result against simple baselines after costs; report dispersion across windows and regimes, drawdowns, turnover and uncertainty. Statistical procedures cannot undo undisclosed strategy search. [arch comparison tools](https://arch.readthedocs.io/en/latest/multiple-comparison/multiple-comparison_examples.html).
4. **Execution realism.** Specify order timing, spreads, commissions/fees, slippage, volume/participation limits, partial fills, financing and borrow where relevant. Stress delays, gaps and rejected orders. Recheck array-based research in the selected event engine using the same admissible data and strategy rules.
5. **Deterministic safety boundary.** Validate typed target weights/orders against symbol allowlists, position/order notional, exposure, concentration, stale data, buying power and a kill switch. Persist intent and broker identifiers before retry decisions. Research/model workers have no broker credentials and cannot relax these controls.
6. **Paper reconciliation.** Explicitly select paper credentials/environment; prove startup reconciliation, disconnect/restart recovery, partial fills, cancel/replace races and ambiguous submissions. Compare event-stream updates with periodic order/position/account snapshots. Alert and stop new orders on unresolved discrepancies.
7. **Promotion decision.** Predefine a paper observation period and acceptance thresholds before seeing results. This catalog authorizes no live promotion and proves no profitability; live readiness would require a separate operational, data, security and account review.

Alpaca paper is a useful integration environment, but its documented simulation omits effects such as market impact, latency slippage, queue position and several cash/cost events. Paper-only/basic equity data is IEX, not a consolidated full-market feed. Data used for research, signal generation and fills must therefore be compared explicitly; a free-feed backtest and a paper result are not interchangeable. [Paper limitations](https://docs.alpaca.markets/us/docs/paper-trading), [market-data coverage](https://docs.alpaca.markets/us/docs/about-market-data-api).

## How to use the machine-readable recipes

Each `native_workflow` is an ordered list within its own dedicated environment and working directory. Except the linked historical LEAN commands and later native adapter build, the listed workflows are **prospective and unexecuted**. Some only inspect source or APIs; the entry states that scope. Account queries require operator-provided private paper credentials. Local inference/training recipes may download weights or consume compute; agent launches may call configured paid services. None of those operations happened during this catalog review.

Do not concatenate the entries into one installer. Respect the selected package's Python range and dependency lock; broker engines, legacy libraries and model frameworks often need separate environments. Local filenames are input contracts, not bundled datasets: `prices.csv` is a dated price matrix, while `returns.csv` varies by recipe and must follow the stated alignment/cash/benchmark columns. The catalog does not generate or silently fetch those research inputs.

`version_or_commit` identifies the selected package release, reviewed release tag or source commit. `release_date` is the selected package's registry upload timestamp when applicable, otherwise the GitHub publication timestamp; source-only pins use `null`. Source URLs expose when API/license review used a source snapshot rather than the registry artifact. This is not a universal latest-HEAD audit. Notable version-family mismatches are explicit: LEAN's old GitHub release marker versus its current source pin; FinRL/FinGPT source versus old wheels; current `darts` versus legacy `u8darts`; and package releases that differ from GitHub's latest-release marker.

The source and license declarations are recorded for selection, not a legal compatibility certification. Resolve Lumibot's conflicting metadata and Dexter's missing standalone license file before redistribution. Keep data/model terms separate from code licenses. At the September 19 review, open gaps included point-in-time US data acceptance, QuantConnect adapter entitlement, Alpaca paper integration, deterministic risk/reconciliation implementation and any demonstrated strategy edge. The later bounded runner and paper smoke close only their recorded scopes; use the current R&D readiness decision for remaining gates.
