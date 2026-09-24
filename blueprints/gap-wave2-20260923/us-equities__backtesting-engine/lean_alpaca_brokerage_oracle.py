#!/usr/bin/env python3
"""Gap-wave-2 check (us-equities/backtesting-engine gap 4).

Runs the six frozen LEAN SPY oracle cases twice, offline and in the existing bwrap
sandbox: a control with the unchanged HistoricalSimulationAlgorithm.cs, and a
variant whose only change is one inserted line,
    SetBrokerageModel(QuantConnect.Brokerages.BrokerageName.Alpaca, AccountType.Margin);
placed before AddEquity. No broker adapter, network or credential is used; the
Alpaca adapter paper-endpoint arm is out of scope here (broker contact).

Unlike the original runner, a failing native command does not abort the loop:
every case's exit code, stderr, order events and the original analysis verdict
(or its exception) are recorded.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
HIST = REPO / "blueprints/us-equities/historical-simulation"
sys.path.insert(0, str(HIST))
from analysis import inspect_case  # noqa: E402
PREVIOUS = REPO / "blueprints/us-equities/execution-realism"
sys.path.insert(0, str(PREVIOUS))
_spec = importlib.util.spec_from_file_location("accepted_cost_runner", PREVIOUS / "run.py")
NATIVE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(NATIVE)
sys.path.pop(0)

ANCHOR = "        SetTimeZone(TimeZones.NewYork);\n"
INSERT = "        SetBrokerageModel(QuantConnect.Brokerages.BrokerageName.Alpaca, AccountType.Margin);\n"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(prefix, argv, output, name, timeout):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        p = subprocess.run(prefix + argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, check=False)
        code, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as exc:
        code, out, err = 124, exc.stdout or b"", exc.stderr or b""
    (output / (name + ".stdout.txt")).write_bytes(out)
    (output / (name + ".stderr.txt")).write_bytes(err)
    return {"name": name, "argv": prefix + argv, "started_utc": started, "exit_code": code,
            "stdout": {"bytes": len(out), "sha256": sha(out)}, "stderr": {"bytes": len(err), "sha256": sha(err)}}


def compile_variant(prefix, dotnet, lean, output, variant):
    build = output / variant / "build"
    build.mkdir(parents=True)
    source = (HIST / "HistoricalSimulationAlgorithm.cs").read_text()
    if variant == "alpaca":
        if source.count(ANCHOR) != 1:
            raise ValueError("anchor not unique")
        source = source.replace(ANCHOR, ANCHOR + INSERT)
    (build / "HistoricalSimulationAlgorithm.cs").write_text(source)
    compilers = list(dotnet.parent.glob("sdk/*/Roslyn/bincore/csc.dll"))
    refpacks = list(dotnet.parent.glob("packs/Microsoft.NETCore.App.Ref/*/ref/net10.0"))
    if len(compilers) != 1 or len(refpacks) != 1:
        raise ValueError("select the accepted isolated .NET 10 SDK")
    refs = ["/dotnet/" + str(p.relative_to(dotnet.parent)) for p in sorted(refpacks[0].glob("*.dll"))]
    refs += ["/engine/" + n for n in ["QuantConnect.Algorithm.dll", "QuantConnect.Common.dll",
                                     "QuantConnect.Indicators.dll", "Python.Runtime.dll", "NodaTime.dll"]]
    rel = f"/run/{variant}/build"
    response = ["/nologo", "/target:library", "/deterministic+", f"/out:{rel}/HistoricalSimulation.dll"]
    response += ['/reference:"' + p + '"' for p in refs] + [f"{rel}/HistoricalSimulationAlgorithm.cs"]
    (build / "compiler.rsp").write_text("\n".join(response) + "\n")
    rec = run(prefix, ["/dotnet/dotnet", "/dotnet/" + str(compilers[0].relative_to(dotnet.parent)), f"@{rel}/compiler.rsp"],
              output / variant, "compile", 120)
    rec["source_sha256"] = sha(source.encode())
    return rec


def config_for(variant, name, spec):
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
        "transaction-handler": "QuantConnect.Lean.Engine.TransactionHandlers.BacktestingTransactionHandler"}
    base = f"/run/{variant}/{name}"
    config.update({"environment": "backtesting", "live-mode": False,
                   "algorithm-type-name": "HistoricalSimulationAlgorithm", "algorithm-language": "CSharp",
                   "algorithm-location": f"/run/{variant}/build/HistoricalSimulation.dll", "composer-dll-directory": "/engine",
                   "data-folder": "/data", "results-destination-folder": base,
                   "object-store-root": base + "/storage", "close-automatically": True,
                   "job-user-id": "0", "api-access-token": "",
                   "parameters": {"fee-usd": spec["fee_usd"], "slippage": spec["slippage"], "target": spec["target"],
                                  "adaptive": int(spec["adaptive"]), "reject": int(spec["reject"]),
                                  "ledger": base + "/audit.jsonl"}})
    return config


def ledger_summary(case_dir):
    audit_path = case_dir / "audit.jsonl"
    if not audit_path.exists():
        return {"audit_present": False}
    rows = [json.loads(s) for s in audit_path.read_text().splitlines()]
    orders = [r for r in rows if r["kind"] == "order"]
    final = [r for r in rows if r["kind"] == "final"]
    return {"audit_present": True, "audit_sha256": sha(audit_path.read_bytes()),
            "intents": [{k: r.get(k) for k in ("local", "order_id", "quantity", "reason", "status")} for r in rows if r["kind"] == "intent"],
            "order_events": [{k: r.get(k) for k in ("order_id", "status", "message", "quantity", "price")} for r in orders],
            "fills": sum(1 for r in orders if r["status"] == "Filled"),
            "invalid": sum(1 for r in orders if r["status"] == "Invalid"),
            "dividends": sum(1 for r in rows if r["kind"] == "dividend"),
            "margin_calls": sum(1 for r in rows if r["kind"] == "margin_call"),
            "final": final[-1] if final else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean-source", type=Path, required=True)
    parser.add_argument("--dotnet", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    lean, dotnet, output = args.lean_source.resolve(), args.dotnet.resolve(), args.out.resolve()
    if output.is_relative_to(lean) or output.is_relative_to(dotnet.parent) or output.exists():
        raise ValueError("use a fresh directory outside the engine and SDK")
    plan = json.loads((HIST / "plan.json").read_text())
    os.umask(0o077)
    output.mkdir(parents=True, mode=0o700)
    (output / "home").mkdir()
    prefix = NATIVE.sandbox(lean, dotnet, output)
    report = {"plan_sha256": sha((HIST / "plan.json").read_bytes()),
              "algorithm_sha256": sha((HIST / "HistoricalSimulationAlgorithm.cs").read_bytes()),
              "inserted_line": INSERT.strip(), "variants": {}}
    for variant in ("control", "alpaca"):
        (output / variant).mkdir()
        entry = {"compile": compile_variant(prefix, dotnet, lean, output, variant), "cases": []}
        report["variants"][variant] = entry
        if entry["compile"]["exit_code"]:
            continue
        for spec in plan["cases"]:
            case = output / variant / spec["id"]
            case.mkdir()
            NATIVE.save(case / "config.json", config_for(variant, spec["id"], spec))
            rec = run(prefix, ["/dotnet/dotnet", "/engine/QuantConnect.Lean.Launcher.dll", "--config",
                               f"/run/{variant}/{spec['id']}/config.json"], output / variant, spec["id"], 120)
            rec["ledger"] = ledger_summary(case)
            try:
                result = inspect_case(case, spec)
                rec["original_analysis"] = {"accepted": True, "native_end_equity_usd": str(result.get("native_end_equity_usd")),
                                            "fill_count": result.get("fill_count"), "invalid_count": result.get("invalid_count")}
            except Exception as exc:  # recorded, never hidden
                rec["original_analysis"] = {"accepted": False, "error": f"{type(exc).__name__}: {exc}"}
            summary_path = case / "HistoricalSimulationAlgorithm-summary.json"
            if summary_path.exists():
                state = json.loads(summary_path.read_text()).get("state", {})
                rec["native_state"] = {"Status": state.get("Status"), "RuntimeError": state.get("RuntimeError")}
            entry["cases"].append(rec)
            NATIVE.save(output / "report.json", report)
    NATIVE.save(output / "report.json", report)
    print(json.dumps({v: [{"id": c["name"], "exit": c["exit_code"], "fills": c["ledger"].get("fills"),
                           "invalid": c["ledger"].get("invalid"), "accepted": c["original_analysis"]["accepted"]}
                          for c in e["cases"]] for v, e in report["variants"].items()}, indent=1))


if __name__ == "__main__":
    main()
