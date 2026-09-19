# Native LEAN backtest foundation

This blueprint selects [QuantConnect LEAN](https://github.com/QuantConnect/Lean) for the user's research-first, Alpaca-paper-first US-equities workflow. It has an official [Alpaca brokerage integration](https://github.com/QuantConnect/Lean.Brokerages.Alpaca), allowing a strategy to use the engine's backtest and brokerage execution paths. That integration is a deployment option, not a paper-account connection demonstrated by this receipt.

The native check uses the upstream C# `BasicTemplateFrameworkAlgorithm`, its unchanged default backtesting configuration, and bundled SPY minute data for October 7–11, 2013. The sample is an engine acceptance fixture, not a selected investment strategy or evidence of profitable trading. See [the sanitized execution receipt](receipt.json) for the actual result and limitations.

For the current dependency-resolved build, use [the native resolution recipe](resolution.md) and [its separate receipt](resolution-receipt.json). A three-reference local dependency patch removes the seven originally reported package/advisory pairs from the built launcher graph; the unchanged bundled backtest passed again. The official Alpaca adapter also compiled, including a separately labeled variant referencing the patched LEAN source. Its real initialization still requires QuantConnect product-subscription validation and broker authorization. The original source installation and receipt below remain historical evidence, not the recommended dependency graph for new runs.

## Pins and installation scope

| Component | Recorded identity | Scope |
| --- | --- | --- |
| LEAN engine | `985ef30ad3ac774218c5ac516b4cb0aa2655730f`, source commit September 18, 2026 | Unmodified upstream source, including its Apache-2.0 license |
| Microsoft .NET SDK | `10.0.401`, release September 8, 2026 | Official Linux x64 SDK archive, isolated prefix; publisher SHA-512 verified |
| Alpaca integration | `1973f6165bee212acf656ed2f9cb0af86d4f2a18`, source commit September 15, 2026 | Primary-source review only; not installed or connected by this check |

LEAN's old GitHub `releases/latest` entry is not the identity of this source build. The exact commit is the engine pin. The SDK archive retains Microsoft's license and third-party notices; the engine clone retains its upstream license. No source patches, global PATH changes, Docker installation, client-account changes or paid QuantConnect subscription were used.

The SDK came from [Microsoft's official .NET 10 release metadata](https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json). Select the `10.0.401` Linux x64 SDK asset, verify its published SHA-512 before extracting it into an unused prefix, and preserve the complete archive contents. The recorded archive hash is in the receipt.

The original build passed with **7,855 upstream warnings and zero errors**. NuGet reported seven package/advisory pairs across five packages, including a critical report for `System.Drawing.Common 4.7.0` and high-severity reports involving `DotNetZip`, `WinHttpHandler` and `ServiceModel`. These packages also appear in that launcher's resolved dependency manifests. The original receipt preserves the advisory links; the separate resolution documents the replacements and replay instead of rewriting this historical result. Neither build establishes security approval for unattended deployment or untrusted inputs.

## Reproduce the original native sample

Use an explicitly selected clone and SDK prefix. The following are native upstream commands, not a replacement backtesting engine. Dependencies are downloaded during the initial build; the sample data are bundled in the source repository.

```sh
(
set -eu
LEAN_SOURCE=/absolute/path/to/lean-985ef30
DOTNET_ROOT=/absolute/path/to/dotnet-equity10
export DOTNET_ROOT
export DOTNET_CLI_TELEMETRY_OPTOUT=1
export DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
export DOTNET_GENERATE_ASPNET_CERTIFICATE=false
export DOTNET_NOLOGO=1
export DOTNET_CLI_HOME="$DOTNET_ROOT/cli-home"
export NUGET_PACKAGES="$DOTNET_ROOT/nuget-packages"

git clone https://github.com/QuantConnect/Lean.git "$LEAN_SOURCE"
git -C "$LEAN_SOURCE" checkout --detach 985ef30ad3ac774218c5ac516b4cb0aa2655730f
cd "$LEAN_SOURCE"
"$DOTNET_ROOT/dotnet" build QuantConnect.Lean.sln --disable-build-servers -m:2 --verbosity minimal
# Verify the pinned, unmodified source configuration before using its build output.
git diff --exit-code -- Launcher/config.json
test "$(git rev-parse HEAD)" = 985ef30ad3ac774218c5ac516b4cb0aa2655730f
cd Launcher/bin/Debug
cmp ../../config.json config.json
# The verified pinned default selects backtesting, with live-mode false.
"$DOTNET_ROOT/dotnet" QuantConnect.Lean.Launcher.dll
)
```

Keep the default `environment` set to `backtesting`. Its selected environment has `live-mode: false`, local data/map/factor providers and no brokerage credentials. Inspect the native completion status, data-point and order counts, error output and saved result files. Preserve warnings and failures. A successful compilation alone does not establish a successful backtest, and the backtest does not establish broker connectivity.

These source-build commands follow [the pinned upstream Linux instructions](https://github.com/QuantConnect/Lean/blob/985ef30ad3ac774218c5ac516b4cb0aa2655730f/readme.md). C# avoids adding LEAN's separate Python/Python.NET environment for this first check. Python strategies require the pinned upstream Python setup in addition to the engine.

## Before Alpaca paper execution

The documented [LEAN CLI workflow](https://www.quantconnect.com/docs/v2/lean-cli/key-concepts/getting-started) requires a paid QuantConnect organization and Docker. The account-free source build above is a different supported route; it does not grant those services or data entitlements. Choosing local versus managed paper deployment is a separate operational decision.

Alpaca's official [Python SDK](https://github.com/alpacahq/alpaca-py/releases/tag/v0.44.0) is an optional account/data/reconciliation client, not an additional strategy engine or a second order writer. Paper access requires the user's paper credentials and an explicit paper endpoint. [Basic equities data covers IEX](https://docs.alpaca.markets/us/docs/about-market-data-api); it is not the consolidated US market. Historical research needs explicit adjustment, corporate-action, calendar, symbol-history and feed provenance. Bundled sample data do not establish production data coverage.

Keep research workers outside the execution boundary: they can propose hypotheses, code and evidence for review. Deterministic code must own account/endpoint checks, instrument permissions, stale-data checks, exposure/order limits, unique order identifiers, persistence and reconciliation. After a timeout or reconnect, reconcile broker order state before considering another submission; a timeout is not proof that no order exists. Alpaca documents this boundary in [its order workflow](https://docs.alpaca.markets/us/docs/working-with-orders).

A broker adapter needs its separately configured paper account and execution scope. Paper fills do not establish live execution quality: [Alpaca's simulation limitations](https://docs.alpaca.markets/us/docs/paper-trading) exclude important latency, liquidity and market-impact effects. No strategy, return, market-data entitlement, live-order authority or autonomous deployment readiness is established by the native sample.

The pinned adapter also invokes QuantConnect's product-347 subscription check during initialization, before establishing its Alpaca clients. Source compilation does not remove this entitlement check. See the [source-backed account boundary](resolution.md#remaining-account-and-runtime-boundaries); neither subscription validation nor brokerage initialization was invoked during native acceptance.
