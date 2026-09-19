#!/usr/bin/env python3
"""Run three isolated native LEAN cases; no downloads, accounts or broker clients."""
import argparse
import datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from analyze import number, summarize

CASES = [("zero", "0", "0"), ("five_bps", "1", "0.0005"),
         ("twenty_bps", "1", "0.002")]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + "\n")


def sandbox(lean, dotnet, output):
    command = ["/usr/bin/bwrap", "--unshare-all", "--die-with-parent", "--new-session",
               "--cap-drop", "ALL", "--clearenv"]
    for source, target in [("/usr", "/usr"), ("/lib", "/lib"), ("/lib64", "/lib64"),
                           ("/etc/ld.so.cache", "/etc/ld.so.cache"),
                           (str(dotnet.parent), "/dotnet"),
                           (str(lean / "Launcher/bin/Debug"), "/engine"),
                           (str(lean / "Data"), "/data")]:
        command += ["--ro-bind", source, target]
    command += ["--bind", str(output), "/run", "--proc", "/proc", "--dev", "/dev",
                "--tmpfs", "/tmp", "--chdir", "/run", "--setenv", "HOME", "/run/home",
                "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "DOTNET_ROOT", "/dotnet",
                "--setenv", "DOTNET_CLI_HOME", "/run/home", "--setenv", "LANG", "C.UTF-8",
                "--setenv", "DOTNET_CLI_TELEMETRY_OPTOUT", "1",
                "--setenv", "DOTNET_SKIP_FIRST_TIME_EXPERIENCE", "1",
                "--setenv", "DOTNET_GENERATE_ASPNET_CERTIFICATE", "false",
                "--setenv", "DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE", "true",
                "--setenv", "MSBuildEnableWorkloadResolver", "false",
                "--setenv", "DOTNET_NOLOGO", "1"]
    return command


def execute(prefix, argv, output, name, timeout):
    receipt = {"argv": prefix + argv, "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with (output / (name + ".stdout.txt")).open("wb") as stdout, (output / (name + ".stderr.txt")).open("wb") as stderr:
        try:
            result = subprocess.run(prefix + argv, stdin=subprocess.DEVNULL, stdout=stdout,
                                    stderr=stderr, timeout=timeout, check=False)
            receipt["exit_code"] = result.returncode
        except subprocess.TimeoutExpired:
            receipt["timeout_seconds"] = timeout
            save(output / (name + ".command.private.json"), receipt)
            raise
    save(output / (name + ".command.private.json"), receipt)
    if result.returncode:
        raise RuntimeError(f"native command {name} failed; inspect retained output")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lean-source", type=Path, required=True)
    parser.add_argument("--dotnet", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    lean, dotnet, output = args.lean_source.resolve(), args.dotnet.resolve(), args.out.resolve()
    if output.is_relative_to(lean) or output.is_relative_to(dotnet.parent):
        raise ValueError("output must be outside accepted engine and SDK installations")
    if output.exists():
        raise ValueError("output must be a fresh directory")
    os.umask(0o077)
    output.mkdir(parents=True, mode=0o700)
    (output / "home").mkdir()
    build = output / "build"
    build.mkdir()
    source = Path(__file__).resolve().parent
    for name in ["ExecutionSensitivityAlgorithm.cs"]:
        shutil.copyfile(source / name, build / name)
    # Pin every mounted data file and every engine binary/config input, including optional reads.
    inputs = [p for root in [lean / "Data", lean / "Launcher/bin/Debug"] for p in root.rglob("*") if p.is_file()]
    before = {str(p.relative_to(lean)): digest(p) for p in sorted(inputs)}
    save(output / "input-hashes.private.json", before)
    prefix = sandbox(lean, dotnet, output)
    compilers = list(dotnet.parent.glob("sdk/*/Roslyn/bincore/csc.dll"))
    refpacks = list(dotnet.parent.glob("packs/Microsoft.NETCore.App.Ref/*/ref/net10.0"))
    if len(compilers) != 1 or len(refpacks) != 1:
        raise ValueError("select an isolated SDK with exactly one compiler and .NET 10 reference pack")
    references = ["/dotnet/" + str(p.relative_to(dotnet.parent)) for p in sorted(refpacks[0].glob("*.dll"))]
    references += ["/engine/" + name for name in ["QuantConnect.Algorithm.dll", "QuantConnect.Common.dll",
                   "QuantConnect.Indicators.dll", "Python.Runtime.dll", "NodaTime.dll"]]
    response = ["/nologo", "/target:library", "/deterministic+", "/out:/run/build/ExecutionSensitivity.dll"]
    response += ['/reference:"' + path + '"' for path in references]
    response += ["/run/build/ExecutionSensitivityAlgorithm.cs"]
    (build / "compiler.rsp").write_text("\n".join(response) + "\n")
    execute(prefix, ["/dotnet/dotnet", "/dotnet/" + str(compilers[0].relative_to(dotnet.parent)),
                    "@/run/build/compiler.rsp"], output, "compile", 60)
    results = []
    for name, fee, slip in CASES:
        case = output / name
        case.mkdir()
        config = {
            "environment": "backtesting", "live-mode": False,
            "algorithm-type-name": "ExecutionSensitivityAlgorithm", "algorithm-language": "CSharp",
            "algorithm-location": "/run/build/ExecutionSensitivity.dll",
            "composer-dll-directory": "/engine", "data-folder": "/data",
            "results-destination-folder": "/run/" + name, "object-store-root": "/run/" + name + "/storage",
            "parameters": {"fee-usd": fee, "slippage": slip},
            "log-handler": "QuantConnect.Logging.CompositeLogHandler",
            "messaging-handler": "QuantConnect.Messaging.Messaging",
            "job-queue-handler": "QuantConnect.Queues.JobQueue", "api-handler": "QuantConnect.Api.Api",
            "map-file-provider": "QuantConnect.Data.Auxiliary.LocalDiskMapFileProvider",
            "factor-file-provider": "QuantConnect.Data.Auxiliary.LocalDiskFactorFileProvider",
            "data-provider": "QuantConnect.Lean.Engine.DataFeeds.DefaultDataProvider",
            "data-channel-provider": "DataChannelProvider",
            "object-store": "QuantConnect.Lean.Engine.Storage.LocalObjectStore",
            "data-aggregator": "QuantConnect.Lean.Engine.DataFeeds.AggregationManager",
            "setup-handler": "QuantConnect.Lean.Engine.Setup.BacktestingSetupHandler",
            "result-handler": "QuantConnect.Lean.Engine.Results.BacktestingResultHandler",
            "data-feed-handler": "QuantConnect.Lean.Engine.DataFeeds.FileSystemDataFeed",
            "real-time-handler": "QuantConnect.Lean.Engine.RealTime.BacktestingRealTimeHandler",
            "history-provider": ["QuantConnect.Lean.Engine.HistoricalData.SubscriptionDataReaderHistoryProvider"],
            "transaction-handler": "QuantConnect.Lean.Engine.TransactionHandlers.BacktestingTransactionHandler",
            "close-automatically": True, "job-user-id": "0", "api-access-token": "",
        }
        save(case / "config.json", config)
        execute(prefix, ["/dotnet/dotnet", "/engine/QuantConnect.Lean.Launcher.dll", "--config",
                        "/run/" + name + "/config.json"], output, name, 60)
        native_summary = case / "ExecutionSensitivityAlgorithm-summary.json"
        native_events = case / "ExecutionSensitivityAlgorithm-order-events.json"
        item = summarize(json.loads(native_summary.read_text(), parse_float=Decimal),
                         json.loads(native_events.read_text(), parse_float=Decimal))
        item.update({"case": name, "fee_usd_per_order": fee, "slippage_fraction": slip,
                     "summary_sha256": digest(native_summary), "events_sha256": digest(native_events)})
        results.append(item)
    baseline = results[0]
    for item in results:
        if [(e["time"], e["fillQuantity"]) for e in item["fills"]] != [(e["time"], e["fillQuantity"]) for e in baseline["fills"]]:
            raise ValueError("cases changed order timing or quantity")
        item["cash_delta_vs_zero_usd"] = str(number(item["cash_pnl_usd"]) - number(baseline["cash_pnl_usd"]))
    if not number(results[0]["end_cash_usd"]) > number(results[1]["end_cash_usd"]) > number(results[2]["end_cash_usd"]):
        raise ValueError("adverse assumptions did not lower cash monotonically")
    unchanged = all(digest(lean / path) == sha for path, sha in before.items())
    save(output / "results.json", {"cases": results, "mounted_input_files": len(before), "mounted_inputs_unchanged": unchanged})
    if not unchanged:
        raise ValueError("installed input changed during acceptance")
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
