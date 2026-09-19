# Native LEAN execution-cost sensitivity

Three real LEAN backtests completed using the same fixed SPY round trip and
different upstream fee/slippage assumptions. Each processed **3,943 data points**,
filled two simulated market orders, and finished flat. Native exit codes were
zero, stderr was empty, and native missing-data request logs were empty.
[Recorded result and commands](receipt.json).

| Assumption | Entry / exit fill price (USD, native serialized values) | Total fees | Native displayed end equity | Cash change versus zero-cost case, from serialized fills |
| --- | --- | --- | --- | --- |
| $0 per order, zero slippage | 167.72 / 170.05 | $0 | $100,233.00 | $0 |
| $1 per order, 5 basis points slippage | 167.80386 / 169.96497 | $2 | $100,214.11 | −$18.889 |
| $1 per order, 20 basis points slippage | 168.05544 / 169.70988 | $2 | $100,163.44 | −$69.556 |

The fixture buys 100 shares on October 7, 2013 at 10 a.m. New York time and
sells 100 on October 11 at 3 p.m. It starts with $100,000 and uses bundled
minute trade/quote data with raw normalization. The schedule and quantities
are identical across cases. These illustrative assumptions were declared
before the run; they are not estimates of Alpaca's fees or attainable fills.
The five-day fixture is not an investment strategy, alpha test, universe/PIT
validation, calibrated execution model or paper/live deployment.

The analyzer uses decimal arithmetic directly over serialized native JSON,
reconciles fill cash and fees, and requires agreement with native end equity
within half a cent. LEAN serializes some fill prices to five decimal places
and displays account totals in cents: digits in the reconstructed ledger do
not recover unexported internal precision. Native results and all failed
attempts remain private, with hashes retained here.

## Native models and installation

The local C# fixture calls the existing LEAN API and unmodified upstream
[ConstantFeeModel](https://github.com/QuantConnect/Lean/blob/985ef30ad3ac774218c5ac516b4cb0aa2655730f/Common/Orders/Fees/ConstantFeeModel.cs),
[ConstantSlippageModel](https://github.com/QuantConnect/Lean/blob/985ef30ad3ac774218c5ac516b4cb0aa2655730f/Common/Orders/Slippage/ConstantSlippageModel.cs)
and [EquityFillModel](https://github.com/QuantConnect/Lean/blob/985ef30ad3ac774218c5ac516b4cb0aa2655730f/Common/Orders/Fills/EquityFillModel.cs).
The fixture is our integration, not an unchanged upstream regression sample.
It uses the [previously accepted patched engine](../engine/resolution.md),
whose three package-reference changes remain distinct from these model sources.

The installed .NET SDK's native C# compiler builds only the small fixture
against installed .NET reference assemblies and LEAN binaries. The launcher
and accepted source installation are not rebuilt. Linux Bubblewrap gives
each command a separate network/PID namespace, read-only SDK/engine/data and
system-library mounts, empty environment/home, and a fresh writable results
directory. Native account stores are not mounted. No external broker client, API key,
model, download, paid service or external order was used.

[The input manifest](inputs.json) fingerprints all **1,145 mounted data files**
and **331 engine-directory files**, including optional inputs and historical
output files already present in that directory. All 1,476 preexisting hashes
were unchanged after the accepted run. These are mounted-input counts, not
claims that every file was read. The native succeeded-request log identifies
13 data paths per case; map/factor/calendar metadata may be read separately.

## Replay on an adopted Linux/WSL host

Select the remediated LEAN source build and .NET SDK from the engine recipe.
The runner requires Bubblewrap, Python 3.11+ and an isolated .NET 10 SDK with
one C# compiler/reference-pack version. Use an unused output directory outside
both installations; repeated output paths and symlinks into them are rejected.
No additional Python packages are required. This is accepted on this WSL host;
other hosts need their own namespace/runtime acceptance.

```sh
python3 blueprints/us-equities/execution-realism/run.py \
  --lean-source "$LEAN_SOURCE" \
  --dotnet "$DOTNET_ROOT/dotnet" \
  --out "$NEW_PRIVATE_RESULT_DIR"
```

Within the recorded sandbox the accepted native commands are:

```sh
/dotnet/dotnet /dotnet/sdk/10.0.401/Roslyn/bincore/csc.dll @/run/build/compiler.rsp
/dotnet/dotnet /engine/QuantConnect.Lean.Launcher.dll --config /run/zero/config.json
/dotnet/dotnet /engine/QuantConnect.Lean.Launcher.dll --config /run/five_bps/config.json
/dotnet/dotnet /engine/QuantConnect.Lean.Launcher.dll --config /run/twenty_bps/config.json
```

The generated compiler response file selects existing .NET 10 reference
assemblies and five managed LEAN dependencies. It performs no package restore.
The runner retains native stdout/stderr, argument arrays, response/config files,
input hashes, original result files and a compact decimal cash ledger. Each
native command has a 60-second deadline; PID namespace teardown retires its
children when Bubblewrap is killed. Native completion and accounting checks
are required in addition to exit zero.

Two earlier `dotnet build` attempts stalled during restore/workload verification
and hit their 120-second deadlines. A notification/resolver opt-out did not
resolve the second attempt. Both failures are retained and terminated; the
accepted compiler route above replaces that build recipe. No claim is made
that the earlier project-restore path now works or that its root cause was
fully diagnosed.

## Calibration still required

This proves fee and price-slippage sensitivity in the selected engine path.
`EquityFillModel.MarketFill` assumes the entire eligible order quantity fills.
The upstream volume-share slippage model also would not, by itself, impose a
quantity cap. This run exercises neither partial fills nor participation caps,
queue position, latency, impact, spread changes, cancellation, auctions, halts,
borrow fees, broker reconciliation or advanced execution instructions.

Before paper promotion, choose a strategy horizon and entitled data feed;
calibrate quantity, spread/latency and cost assumptions using attributable
observations; and require independent holdout and deterministic risk/order-state
acceptance. This receipt narrows the cost-sensitivity gap and leaves that
calibration/promotion gate open. No token-saving or trading-profit claim follows
from the native runs.

```sh
python3 -m unittest discover -s tests -p test_execution_realism.py -v
```

Seven focused checks cover native failure status, missing/duplicate/unbalanced
fills, currency mismatch, decimal preservation, cash discrepancies and output
isolation. They verify the analyzer and guardrails; native runs provide the
engine evidence separately.
