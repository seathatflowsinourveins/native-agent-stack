#!/usr/bin/env python3
"""Six frozen historical stress cases using existing native compiler/isolation helpers."""
import argparse
from decimal import Decimal
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

from analysis import inspect_case

SOURCE = Path(__file__).resolve().parent
PREVIOUS = SOURCE.parent / "execution-realism"
sys.path.insert(0, str(PREVIOUS))
_spec = importlib.util.spec_from_file_location("accepted_cost_runner", PREVIOUS / "run.py")
NATIVE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(NATIVE)
sys.path.pop(0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean-source", type=Path, required=True)
    parser.add_argument("--dotnet", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    lean, dotnet, output = args.lean_source.resolve(), args.dotnet.resolve(), args.out.resolve()
    if output.is_relative_to(lean) or output.is_relative_to(dotnet.parent) or output.exists():
        raise ValueError("use a fresh directory outside the accepted engine and SDK")
    plan = json.loads((SOURCE / "plan.json").read_text())
    os.umask(0o077)
    output.mkdir(parents=True, mode=0o700)
    (output / "home").mkdir()
    build = output / "build"
    build.mkdir()
    shutil.copyfile(SOURCE / "plan.json", output / "plan.json")
    shutil.copyfile(SOURCE / "HistoricalSimulationAlgorithm.cs", build / "HistoricalSimulationAlgorithm.cs")
    inputs = [p for root in [lean / "Data", lean / "Launcher/bin/Debug"] for p in root.rglob("*") if p.is_file()]
    before = {str(p.relative_to(lean)): NATIVE.digest(p) for p in sorted(inputs)}
    NATIVE.save(output / "input-hashes.private.json", before)
    prefix = NATIVE.sandbox(lean, dotnet, output)
    compilers = list(dotnet.parent.glob("sdk/*/Roslyn/bincore/csc.dll"))
    refpacks = list(dotnet.parent.glob("packs/Microsoft.NETCore.App.Ref/*/ref/net10.0"))
    if len(compilers) != 1 or len(refpacks) != 1:
        raise ValueError("select the accepted isolated .NET 10 SDK")
    refs = ["/dotnet/" + str(p.relative_to(dotnet.parent)) for p in sorted(refpacks[0].glob("*.dll"))]
    refs += ["/engine/" + n for n in ["QuantConnect.Algorithm.dll", "QuantConnect.Common.dll", "QuantConnect.Indicators.dll", "Python.Runtime.dll", "NodaTime.dll"]]
    response = ["/nologo", "/target:library", "/deterministic+", "/out:/run/build/HistoricalSimulation.dll"]
    response += ['/reference:"' + p + '"' for p in refs]
    response += ["/run/build/HistoricalSimulationAlgorithm.cs"]
    (build / "compiler.rsp").write_text("\n".join(response) + "\n")
    NATIVE.execute(prefix, ["/dotnet/dotnet", "/dotnet/" + str(compilers[0].relative_to(dotnet.parent)), "@/run/build/compiler.rsp"], output, "compile", 60)
    results = []
    for case_spec in plan["cases"]:
        name = case_spec["id"]
        case = output / name
        case.mkdir()
        # Explicit local handlers; do not import arbitrary host configuration or credentials.
        config = {
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
            "transaction-handler": "QuantConnect.Lean.Engine.TransactionHandlers.BacktestingTransactionHandler"
        }
        config.update({"environment": "backtesting", "live-mode": False,
            "algorithm-type-name": "HistoricalSimulationAlgorithm", "algorithm-language": "CSharp",
            "algorithm-location": "/run/build/HistoricalSimulation.dll", "composer-dll-directory": "/engine",
            "data-folder": "/data", "results-destination-folder": "/run/" + name,
            "object-store-root": "/run/" + name + "/storage", "close-automatically": True,
            "job-user-id": "0", "api-access-token": "",
            "parameters": {"fee-usd": case_spec["fee_usd"], "slippage": case_spec["slippage"],
                "target": case_spec["target"], "adaptive": int(case_spec["adaptive"]),
                "reject": int(case_spec["reject"]), "ledger": "/run/" + name + "/audit.jsonl"}})
        NATIVE.save(case / "config.json", config)
        NATIVE.execute(prefix, ["/dotnet/dotnet", "/engine/QuantConnect.Lean.Launcher.dll", "--config", "/run/" + name + "/config.json"], output, name, 60)
        result = inspect_case(case, case_spec)
        results.append(result)
        NATIVE.save(output / "partial-results.json", results)
    unchanged = all(NATIVE.digest(lean / p) == sha for p, sha in before.items())
    NATIVE.save(output / "results.json", {"cases": results, "mounted_input_files": len(before), "mounted_inputs_unchanged": unchanged,
        "frozen_plan_sha256": NATIVE.digest(output / "plan.json")})
    if not unchanged:
        raise ValueError("mounted input changed")
    print(json.dumps({"cases": [{k: r[k] for k in ["id", "native_end_equity_usd", "fill_count", "invalid_count", "max_observed_drawdown"]} for r in results], "mounted_inputs_unchanged": unchanged}, indent=2))


if __name__ == "__main__":
    main()
