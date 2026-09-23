#!/usr/bin/env python3
"""Gap 14 LEAN arm: replay the gap 4/10 skfolio fold-weight schedule in native LEAN 985ef30 inside the
execution-realism Bubblewrap sandbox (no network, read-only engine/SDK/data, empty environment).

Cases (each for meanrisk_min_variance and hrp_variance):
  no_dividends  fee 1 USD, factor files hidden by a tmpfs, compared with raw/4-10/nautilus-run-fix2
  dividends     fee 1 USD, LEAN raw-mode dividends credited natively, compared with raw/4/nautilus-dividends-run-fix3
  control_fee2  fee 2 USD, factor files hidden (negative control: must differ from nautilus-run-fix2)
No downloads, accounts or broker clients. Adapted from blueprints/us-equities/execution-realism/run.py.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
KEYS = ("meanrisk_min_variance", "hrp_variance")
CASES = {"no_dividends": {"fee": "1", "hide_factor_files": True},
         "dividends": {"fee": "1", "hide_factor_files": False},
         "control_fee2": {"fee": "2", "hide_factor_files": True}}
ASSETS = ("SPY", "QQQ", "IWM")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, default=str) + "\n")


def sandbox(lean, dotnet, output, hide_factor_files):
    command = ["/usr/bin/bwrap", "--unshare-all", "--die-with-parent", "--new-session",
               "--cap-drop", "ALL", "--clearenv"]
    for source, target in [("/usr", "/usr"), ("/lib", "/lib"), ("/lib64", "/lib64"),
                           ("/etc/ld.so.cache", "/etc/ld.so.cache"),
                           (str(dotnet.parent), "/dotnet"),
                           (str(lean / "Launcher/bin/Debug"), "/engine"),
                           (str(lean / "Data"), "/data")]:
        command += ["--ro-bind", source, target]
    if hide_factor_files:
        command += ["--tmpfs", "/data/equity/usa/factor_files"]
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
    with (output / (name + ".stdout.txt")).open("wb") as out, (output / (name + ".stderr.txt")).open("wb") as err:
        try:
            result = subprocess.run(prefix + argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                    timeout=timeout, check=False)
            receipt["exit_code"] = result.returncode
        except subprocess.TimeoutExpired:
            receipt["timeout_seconds"] = timeout
            save(output / (name + ".command.json"), receipt)
            raise
    receipt["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save(output / (name + ".command.json"), receipt)
    if result.returncode:
        raise RuntimeError(f"native command {name} failed; inspect retained output")
    return receipt


def config(case, key, fee):
    return {
        "environment": "backtesting", "live-mode": False,
        "algorithm-type-name": "WeightScheduleParityAlgorithm", "algorithm-language": "CSharp",
        "algorithm-location": "/run/build/WeightScheduleParity.dll",
        "composer-dll-directory": "/engine", "data-folder": "/data",
        "results-destination-folder": f"/run/{case}/{key}", "object-store-root": f"/run/{case}/{key}/storage",
        "parameters": {"fee-usd": fee, "capital": "1000000", "schedule-path": f"/run/build/{key}.csv",
                       "final-close": "2021-03-31", "ledger-path": f"/run/{case}/{key}/parity-ledger.csv"},
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lean-source", type=Path, required=True)
    parser.add_argument("--dotnet", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    lean, dotnet, output = args.lean_source.resolve(), args.dotnet.resolve(), args.out.resolve()
    if output.is_relative_to(lean) or output.is_relative_to(dotnet.parent) or output.exists():
        raise ValueError("output must be a fresh directory outside the engine and SDK installations")
    os.umask(0o077)
    output.mkdir(parents=True, mode=0o700)
    (output / "home").mkdir()
    build = output / "build"
    build.mkdir()
    shutil.copyfile(HERE / "WeightScheduleParityAlgorithm.cs", build / "WeightScheduleParityAlgorithm.cs")
    export = json.loads(args.weights.read_text())
    if export["assets"] != list(ASSETS) or export["final_close"] != "2021-03-31":
        raise ValueError("unexpected weight export")
    for key in KEYS:
        rows = ["rebalance_close," + ",".join(ASSETS)]
        rows += [e["rebalance_close"] + "," + ",".join(repr(e["weights"][key][a]) for a in ASSETS) for e in export["schedule"]]
        (build / f"{key}.csv").write_text("\n".join(rows) + "\n")
    inputs = [p for root in [lean / "Data", lean / "Launcher/bin/Debug"] for p in root.rglob("*") if p.is_file()]
    before = {str(p.relative_to(lean)): digest(p) for p in sorted(inputs)}
    compilers = list(dotnet.parent.glob("sdk/*/Roslyn/bincore/csc.dll"))
    refpacks = list(dotnet.parent.glob("packs/Microsoft.NETCore.App.Ref/*/ref/net10.0"))
    if len(compilers) != 1 or len(refpacks) != 1:
        raise ValueError("select an isolated SDK with exactly one compiler and .NET 10 reference pack")
    references = ["/dotnet/" + str(p.relative_to(dotnet.parent)) for p in sorted(refpacks[0].glob("*.dll"))]
    references += ["/engine/" + name for name in ["QuantConnect.Algorithm.dll", "QuantConnect.Common.dll",
                   "QuantConnect.Indicators.dll", "Python.Runtime.dll", "NodaTime.dll"]]
    response = ["/nologo", "/target:library", "/deterministic+", "/out:/run/build/WeightScheduleParity.dll"]
    response += ['/reference:"' + path + '"' for path in references]
    response += ["/run/build/WeightScheduleParityAlgorithm.cs"]
    (build / "compiler.rsp").write_text("\n".join(response) + "\n")
    commands = [execute(sandbox(lean, dotnet, output, False),
                        ["/dotnet/dotnet", "/dotnet/" + str(compilers[0].relative_to(dotnet.parent)),
                         "@/run/build/compiler.rsp"], output, "compile", 120)]
    for case, spec in CASES.items():
        for key in KEYS:
            sub = output / case / key
            sub.mkdir(parents=True)
            save(sub / "config.json", config(case, key, spec["fee"]))
            commands.append(execute(sandbox(lean, dotnet, output, spec["hide_factor_files"]),
                                    ["/dotnet/dotnet", "/engine/QuantConnect.Lean.Launcher.dll", "--config",
                                     f"/run/{case}/{key}/config.json"], output, f"{case}.{key}", args.timeout))
    unchanged = all(digest(lean / path) == sha for path, sha in before.items())
    save(output / "run.json", {"runner_sha256": digest(__file__), "algorithm_sha256": digest(HERE / "WeightScheduleParityAlgorithm.cs"),
                               "weights_sha256": digest(args.weights), "dll_sha256": digest(build / "WeightScheduleParity.dll"),
                               "mounted_input_files": len(before), "mounted_inputs_unchanged": unchanged,
                               "commands": [{k: v for k, v in c.items() if k != "argv"} | {"argv_tail": c["argv"][-4:]}
                                            for c in commands]})
    if not unchanged:
        raise SystemExit("installed input changed during the run")
    print(json.dumps({"out": str(output), "commands": len(commands), "inputs_unchanged": unchanged}))


if __name__ == "__main__":
    sys.exit(main())
