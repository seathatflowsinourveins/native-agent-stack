# Native LEAN dependency resolution and Alpaca compilation

The isolated patched LEAN build completed the **unchanged** upstream backtest: 3,943 data points, three simulated orders, six events, and the same order-list hash as the [original receipt](receipt.json). Native NuGet audits of the built launcher and source-integrated Alpaca library reported no vulnerable packages, including transitive packages, on September 19, 2026. This resolves the seven reported package/advisory pairs for these dependency graphs; it is not a general security certification.

The [resolution receipt](resolution-receipt.json) records successful and failed attempts, package identities, output fingerprints and scope. The original installed engine and historical receipt were preserved. No broker credentials, model calls, paid services, brokerage initialization, orders or Docker were used.

## What changed

Upstream LEAN HEAD still matched `985ef30ad3ac774218c5ac516b4cb0aa2655730f` when checked. The official Alpaca repository still matched `1973f6165bee212acf656ed2f9cb0af86d4f2a18`. These are local integration patches against those exact sources, not fixes claimed to have landed upstream.

| Local change | Reason and evidence |
| --- | --- |
| `DotNetZip 1.16.0` → `ProDotNetZip 1.20.0` in LEAN Compression | The [directory-traversal advisory](https://github.com/advisories/GHSA-xhg6-9j5j-w4vf) lists no patched original DotNetZip release and fixes ProDotNetZip at 1.19.0. The maintained fork preserves the `Ionic.Zip` namespace; [its pinned package source](https://github.com/mihula/ProDotNetZip/tree/0c4ac53a75af4fd2409dc7060477c998aff3bef5) corresponds to the 1.20.0 package. This also removes the old Drawing.Common dependency chain. |
| `NetMQ 4.0.1.6` → `4.0.4.3` in LEAN Messaging and Tests | The [pinned package source](https://github.com/zeromq/netmq/tree/ca87d32d5ca5d8a2675fb7a9925e4b3dc8c35010) supports .NET 10 and resolves ServiceModel.Primitives 10.0.652802 instead of the old WCF chain. The Private.ServiceModel and WinHttpHandler packages disappear from the launcher graph. |
| Alpaca's two floating `QuantConnect.* 2.5.*` package references → sibling LEAN project references | The unmodified adapter builds, but its resolved published QC packages reintroduce DotNetZip/Drawing advisories. This explicitly labeled source-integration variant compiles against the same pinned, patched LEAN source. Brokerage C# logic, the supplied `Alpaca.Markets` binary, subscription checks and account defaults are unchanged. |

The LEAN patch changes exactly three package-reference lines; the Alpaca patch changes exactly two reference lines. The latter is a zero-context patch for the exact pinned adapter source, applied with native Git's `--unidiff-zero` flag. [Patches and NuGet lock files](patches/) are published so the accepted package graph can be restored in locked mode. LEAN and its Alpaca adapter retain Apache-2.0 source licenses. ProDotNetZip retains Ms-PL and included third-party notices; NetMQ is LGPLv3. Keep the complete native package artifacts and their notices. No new linking exception is asserted here.

ProDotNetZip preserves source namespaces but has a different assembly identity from DotNetZip. Rebuild dependent source against this graph; compatibility with unrelated precompiled plugins is not established by this check. The accepted backtest rebuilt upstream LEAN, and the adapter variant rebuilt the adapter source.

## Advisory disposition

| Original package | Report | Disposition in the patched launcher |
| --- | --- | --- |
| DotNetZip 1.16.0 | [CVE-2024-48510](https://github.com/advisories/GHSA-xhg6-9j5j-w4vf), high | Original package removed; fixed ProDotNetZip 1.20.0 installed. |
| System.Drawing.Common 4.7.0 | [CVE-2021-24112](https://github.com/advisories/GHSA-rxg9-xrhp-64gj), critical | Package removed with the old DotNetZip dependency chain. The advisory explicitly affects Linux/macOS graphics parsing; it was not dismissed as Windows-only. |
| System.ServiceModel.Primitives 4.4.0 | [CVE-2018-8356](https://github.com/advisories/GHSA-p9wx-v264-q34p) and [CVE-2018-0786](https://github.com/advisories/GHSA-jc8g-xhw5-6x46) | Replaced by 10.0.652802 through NetMQ. |
| System.Private.ServiceModel 4.4.0 | The same two WCF certificate-validation reports | Package removed. |
| System.Net.Http.WinHttpHandler 4.4.0 | [CVE-2017-0247](https://github.com/advisories/GHSA-6xh7-4v2w-36q6), high | Package removed. |

Seven package/advisory pairs span these five packages. No exploit was run, and no claim is made that the old packages were unreachable. Current dependency absence/replacement and native NuGet results support the narrower remediation claim. NuGet's advisory feed is time-dependent and does not replace code review, input trust or future patch maintenance.

## Portable native replay

These commands reproduce the accepted source and dependency changes in **new physical sibling directories**. They are a replay recipe, not a claim that every command below was rerun from the published repository. Select unused absolute paths and the already verified .NET SDK 10.0.401 described in the [original guide](README.md). `RECIPE` is this repository's `blueprints/us-equities/engine` directory. Shell variables expand in the shell; these are not automatically interpolated configuration placeholders.

```sh
(
set -eu
RECIPE=/absolute/path/to/publication/blueprints/us-equities/engine
RUN_ROOT=/absolute/path/to/new-isolated-engine-prefix
DOTNET_ROOT=/absolute/path/to/dotnet-equity10
LEAN_SOURCE="$RUN_ROOT/Lean"
ALPACA_SOURCE="$RUN_ROOT/Alpaca"
export DOTNET_ROOT
export DOTNET_CLI_TELEMETRY_OPTOUT=1
export DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
export DOTNET_GENERATE_ASPNET_CERTIFICATE=false
export DOTNET_NOLOGO=1
export DOTNET_CLI_HOME="$RUN_ROOT/dotnet-cli-home"
export NUGET_PACKAGES="$RUN_ROOT/nuget-packages"
mkdir -p "$RUN_ROOT"

git clone https://github.com/QuantConnect/Lean.git "$LEAN_SOURCE"
git -C "$LEAN_SOURCE" checkout --detach 985ef30ad3ac774218c5ac516b4cb0aa2655730f
git -C "$LEAN_SOURCE" apply "$RECIPE/patches/lean-dependencies.patch"
cp -R "$RECIPE/patches/lean-locks/." "$LEAN_SOURCE/"

git clone https://github.com/QuantConnect/Lean.Brokerages.Alpaca.git "$ALPACA_SOURCE"
git -C "$ALPACA_SOURCE" checkout --detach 1973f6165bee212acf656ed2f9cb0af86d4f2a18
git -C "$ALPACA_SOURCE" apply --unidiff-zero "$RECIPE/patches/alpaca-source-references.patch"
cp "$RECIPE/patches/alpaca.packages.lock.json" \
  "$ALPACA_SOURCE/QuantConnect.AlpacaBrokerage/packages.lock.json"

"$DOTNET_ROOT/dotnet" restore "$LEAN_SOURCE/QuantConnect.Lean.sln" \
  --locked-mode --disable-parallel -p:NuGetAuditMode=all
"$DOTNET_ROOT/dotnet" build "$LEAN_SOURCE/QuantConnect.Lean.sln" \
  --no-restore --disable-build-servers -m:2 --verbosity minimal -c Debug
"$DOTNET_ROOT/dotnet" restore \
  "$ALPACA_SOURCE/QuantConnect.AlpacaBrokerage/QuantConnect.AlpacaBrokerage.csproj" \
  --locked-mode --disable-parallel -p:NuGetAuditMode=all -p:NoWarn=
"$DOTNET_ROOT/dotnet" build \
  "$ALPACA_SOURCE/QuantConnect.AlpacaBrokerage/QuantConnect.AlpacaBrokerage.csproj" \
  --no-restore --disable-build-servers -m:2 --verbosity minimal -c Debug -p:NoWarn=

"$DOTNET_ROOT/dotnet" list "$LEAN_SOURCE/Launcher/QuantConnect.Lean.Launcher.csproj" \
  package --vulnerable --include-transitive --format json --no-restore
"$DOTNET_ROOT/dotnet" list \
  "$ALPACA_SOURCE/QuantConnect.AlpacaBrokerage/QuantConnect.AlpacaBrokerage.csproj" \
  package --vulnerable --include-transitive --format json --no-restore

git -C "$LEAN_SOURCE" diff --exit-code -- Launcher/config.json \
  Algorithm.CSharp/BasicTemplateFrameworkAlgorithm.cs
cd "$LEAN_SOURCE/Launcher/bin/Debug"
cmp ../../config.json config.json
"$DOTNET_ROOT/dotnet" QuantConnect.Lean.Launcher.dll </dev/null
)
```

The upstream adapter's project suppresses NU1605; `-p:NoWarn=` clears that property during its acceptance builds and replay. No new warning suppression or audit exclusion was added. The full patched LEAN build retained 7,730 compiler/analyzer warnings; the source-integrated adapter build retained 7,471. A zero-error build and an empty vulnerability list do not erase these diagnostics.

The solution-wide package-list audit returned an error because the legacy `Algorithm.Python` project has no restored assets file. Its output is retained. Successful final audits target the actually built launcher and adapter projects, including their transitive dependencies; they do not claim a clean audit of every solution project or a configured Python strategy runtime. Both locked restores succeeded.

Two source-integration attempts through a symlink to a previously built LEAN checkout failed with missing reference-assembly errors, including one attempt with explicit Debug configuration. A fresh physical sibling checkout then built successfully. Preserve the physical layout above. These failures and the original adapter's two advisory warnings remain in the receipt rather than being counted as successes.

## Remaining account and runtime boundaries

Native compilation of the official Alpaca library is now demonstrated. It does **not** establish a paper connection, a data entitlement, an order flow, a configured Alpaca brokerage-model simulation or production readiness. The unchanged backtest uses its upstream default brokerage model.

At the exact pinned source, [`Initialize` invokes `ValidateSubscription`](https://github.com/QuantConnect/Lean.Brokerages.Alpaca/blob/1973f6165bee212acf656ed2f9cb0af86d4f2a18/QuantConnect.AlpacaBrokerage/AlpacaBrokerage.cs#L155). [The validation implementation](https://github.com/QuantConnect/Lean.Brokerages.Alpaca/blob/1973f6165bee212acf656ed2f9cb0af86d4f2a18/QuantConnect.AlpacaBrokerage/AlpacaBrokerage.cs#L994) authenticates using QuantConnect user/token/organization configuration, checks product 347 through `modules/license/read`, and exits on failed validation. Its request includes machine/user/domain/OS and available network-interface identity. That code was read, not invoked or altered. Runtime use requires the operator's valid entitlement, consent to that request, separately authorized Alpaca paper credentials and an explicit paper deployment scope. Building Apache-licensed source does not prove entitlement to the associated service.

The original vulnerable installation still exists as historical evidence. Select the patched checkout for future source-build work; do not mistake the older receipt or an independently restored published QC package for the remediated graph. Neither variant has been deployed as a persistent trading service. Strategy validation, realistic fees/fills, market-data rights, deterministic limits and durable order reconciliation remain outside this engine compilation/backtest check.
