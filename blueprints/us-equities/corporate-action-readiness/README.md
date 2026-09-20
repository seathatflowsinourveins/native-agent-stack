# Corporate-action readiness: bounded native acceptance

The native LEAN probe verified **25 AAPL sessions from 2020-08-03 through 2020-09-04**, including a dividend and split, using existing bundled data. It establishes factor, mapping, event-date and normalization mechanics. It does not establish historical availability, a trading strategy, position accounting or profitability.

[The frozen plan](plan.json) specifies the window and four input hashes. [The receipt](receipt.json) records the actual native commands, results, source hashes, all five attempts and private artifact hashes. Raw output stays in the private run directory; no market-data files are republished here. LEAN is pinned to `985ef30ad3ac774218c5ac516b4cb0aa2655730f` under Apache-2.0, using the existing accepted remediation build and isolated .NET SDK.

## Direct native results

```text
AAPL sessions=25, native events=2, expected guard rejections=2
```

| Check | Native result |
|---|---|
| Dividend effective date | 2020-08-07 |
| Dividend amount and units | 0.82 USD per raw pre-split share; reference price 455.61 |
| Dividend factor-row date | 2020-08-06, the preceding trading session |
| Split effective date | 2020-08-31 |
| Split factor | 0.25; native `SplitOccurred` event |
| Split factor-row date | 2020-08-28; reference price 499.23 |
| AAPL mapping | AAPL on all 25 observed dates |
| Explicit 2020-08-28 normalization basis | The 2020-08-28 close remains 499.23 |
| Explicit 2020-09-04 normalization basis | That same close becomes 124.8075 |
| Guard rejections | One native API rejection for missing ScaledRaw basis; one adapter rejection for a bar after its decision cutoff |
| Mounted inputs | 2,091 files hashed before execution and unchanged afterward |

The 0.25 split price factor corresponds to four new units per old unit as a unit conversion. This probe does not hold shares or post cash. The dividend is expressed in raw shares at its event, not multiplied by post-split shares. `GetPriceFactor(TotalReturn)` returns the split factor; constructing a total-return series additionally requires dividend accumulation, which this probe does not perform.

`GetScalingFactors` selects the covering factor row. Its row date can be later than the observed bar: for example, the post-split sample selects a November factor row. `Has*EventOnNextTradingDay` reports the row before the event; `GetSplitsAndDividends` uses native exchange hours to produce its effective date. `Raw` returns a zero factor sentinel in this API, so raw prices are retained directly instead of multiplied by zero. These are pinned upstream semantics, not invented adjustment rules.

## Reproduce on an adopted Linux/WSL host

Reuse the accepted [native engine setup](../historical-simulation/README.md) and [isolation helper](../execution-realism/run.py). Supply the matching existing LEAN data/build and isolated SDK paths; the runner does not install or download anything. A fresh private output directory is mandatory.

```bash
LEAN_SOURCE=/path/to/adopted/lean-985ef30-remediation
DOTNET_EXE=/path/to/adopted/dotnet-equity10/dotnet
CORPORATE_RUN=/path/to/private/corporate-actions/new-run
python3 blueprints/us-equities/corporate-action-readiness/run.py \
  --lean-source "$LEAN_SOURCE" --dotnet "$DOTNET_EXE" --out "$CORPORATE_RUN"
python3 -m unittest discover -s tests -p test_corporate_action_readiness.py -v
```

The script freezes plan, adapter and helper hashes before compilation; mounts engine, data and test binaries read-only; removes inherited environment; and isolates networking with bubblewrap. It calls native `CorporateFactorProvider`, `MapFile`, `GetPriceScale` and `GetSplitsAndDividends`. Exact compiler arguments and stdout/stderr are retained for every attempt. Changed input bytes fail before an output directory or calculation is created. Bubblewrap makes this a tested Linux/WSL recipe; macOS execution has not been accepted by this receipt.

Inside the isolated environment, the executed probe command was:

```bash
/dotnet/dotnet exec \
  --runtimeconfig /engine/QuantConnect.Lean.Launcher.runtimeconfig.json \
  --depsfile /engine/QuantConnect.Lean.Launcher.deps.json \
  /run/build/CorporateActionProbe.dll /run/native-results.json
```

Nine focused Python checks pass, including altered input, invalid guard/schema values, missing/empty/failed upstream test evidence, incorrect mapping, wrong basis and scaling. Decimal multiplication uses a stated absolute tolerance of `1e-25` USD to reconcile C# decimal representation with Python; dates, event amounts, split factors and scope booleans remain exact.

## Upstream NUnit acceptance remains unresolved

The real upstream test command was attempted in the same network-isolated environment:

```bash
/dotnet/dotnet vstest /tests/QuantConnect.Tests.dll \
  --TestCaseFilter:FullyQualifiedName~QuantConnect.Tests.Common.Data.Auxiliary.FactorFileTests \
  --ResultsDirectory:/run/test-results \
  '--Logger:trx;LogFileName=factor-tests.trx'
```

Its assembly-wide setup changes the working directory and resets configuration. A read-only local configuration overlay corrected the first relative data path failure. The final attempt emitted a missing `/data/equity/sgx/map_files` error and then aborted with a Python GIL finalizer error. The TRX records **0 executed cases**. This is not upstream NUnit acceptance or full LEAN test-suite success. The direct API probe passed independently; the broader fixture environment remains unresolved. A zero process result for the wrapper means evidence was collected; inspect `upstream_tests.status` separately.

The preserved attempts include the initial compile reference/property errors, a composer mount error, and an overly strict cross-language decimal comparison before the final bounded tolerance was declared. No failed attempt was replaced or counted as passing.

## What still limits historical catalyst research

These are current retrospective sample files. Neither factor/map dates nor an explicit normalization basis establish when metadata first became available. AAPL's map endpoint in 2050 is a source sentinel, not an accepted real delisting date. There is no as-known candidate universe, complete delisting history, point-in-time action feed, extreme-mover coverage or alpha evidence in this sample. Adjusted values use the full available factor file; this follows the documented [normalization semantics](https://www.quantconnect.com/docs/v2/writing-algorithms/securities/asset-classes/us-equity/requesting-data).

Local introspection confirms installed `alpaca-py==0.44.0` remains unchanged. Its `CorporateActionsRequest` exposes symbols, CUSIPs, types, start/end, IDs, limit and sort; it lacks current REST `region` and `data_quality` fields. The [current corporate-actions endpoint](https://docs.alpaca.markets/us/reference/corporateactions-1) defaults to `data_quality=complete`, may omit early incomplete records, and does not guarantee immediate availability. No SDK client was instantiated and no authenticated request was sent. Native historical access remains deferred until local credentials are configured; any later collector needs explicit feed/adjustment, pagination, process/event/observation timestamps and retained raw response provenance.

The next useful acceptance is a small authenticated historical request with those provenance fields and measured coverage, followed by a chronological catalyst-to-price join. Expanding this fixture into a strategy before those data boundaries are resolved would not add valid evidence.

Pinned implementation references: [factor provider](https://github.com/QuantConnect/Lean/blob/985ef30ad3ac774218c5ac516b4cb0aa2655730f/Common/Data/Auxiliary/CorporateFactorProvider.cs), [explicit basis scaling](https://github.com/QuantConnect/Lean/blob/985ef30ad3ac774218c5ac516b4cb0aa2655730f/Common/Data/Auxiliary/PriceScalingExtensions.cs), [mapping](https://github.com/QuantConnect/Lean/blob/985ef30ad3ac774218c5ac516b4cb0aa2655730f/Common/Data/Auxiliary/MapFile.cs), [dividend units and rounding](https://github.com/QuantConnect/Lean/blob/985ef30ad3ac774218c5ac516b4cb0aa2655730f/Common/Data/Market/Dividend.cs), and [attempted upstream tests](https://github.com/QuantConnect/Lean/blob/985ef30ad3ac774218c5ac516b4cb0aa2655730f/Tests/Common/Data/Auxiliary/FactorFileTests.cs).
