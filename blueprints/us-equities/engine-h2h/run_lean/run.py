#!/usr/bin/env python3
"""LEAN runner for the Alpaca engine head-to-head (paper only; never live).

backtest      Compile H2HOrderScriptAlgorithm.cs with the accepted SDK's own csc and
              run the frozen order script over LEAN's bundled SPY minute data under the
              Alpaca brokerage model. Engine, SDK and data are mounted read-only in a
              no-network bubblewrap sandbox (execution-realism's accepted helpers), and
              every mounted input is re-hashed after the run.
probe-alpaca  The same sandbox plus the official Alpaca plugin build mounted read-only as
              LEAN's plugin-directory. LEAN's own composer must load the factory, and the
              plugin must reference the loaded LEAN assembly versions. No brokerage object
              (network, QuantConnect license check) is created.
paper         Untested boundary. The same algorithm under the official Alpaca brokerage,
              alpaca-paper-trading forced true, network enabled. Refuses unless given this
              engine's dedicated env file and a QuantConnect credential file: the plugin's
              ValidateSubscription() needs a QuantConnect account with its product license
              and sends host identifiers to QuantConnect before any Alpaca call.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
H2H = HERE.parent
if str(H2H) not in sys.path:
    sys.path.insert(0, str(H2H))
import h2h_common as common  # noqa: E402

REALISM_DIR = H2H.parent / "execution-realism"
# execution-realism/run.py imports its sibling "analyze"; load it without letting another
# module of that name (or this one) leak into or out of sys.modules.
_saved_analyze = sys.modules.pop("analyze", None)
sys.path.insert(0, str(REALISM_DIR))
try:
    _spec = importlib.util.spec_from_file_location("h2h_accepted_cost_runner", REALISM_DIR / "run.py")
    NATIVE = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(NATIVE)
finally:
    sys.path.remove(str(REALISM_DIR))
    sys.modules.pop("analyze", None)
    if _saved_analyze is not None:
        sys.modules["analyze"] = _saved_analyze

ALGORITHM = HERE / "H2HOrderScriptAlgorithm.cs"
ENGINE_REFERENCES = ["QuantConnect.Algorithm.dll", "QuantConnect.Common.dll", "QuantConnect.Indicators.dll",
                     "Python.Runtime.dll", "NodaTime.dll"]
BACKTEST_HANDLERS = {
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
}
# The launcher's own live-interactive template with the Alpaca brokerage substituted.
PAPER_HANDLERS = {
    **{k: v for k, v in BACKTEST_HANDLERS.items() if k not in (
        "setup-handler", "result-handler", "data-feed-handler", "real-time-handler", "history-provider",
        "transaction-handler")},
    "live-mode-brokerage": "AlpacaBrokerage",
    "data-queue-handler": ["AlpacaBrokerage"],
    "setup-handler": "QuantConnect.Lean.Engine.Setup.BrokerageSetupHandler",
    "result-handler": "QuantConnect.Lean.Engine.Results.LiveTradingResultHandler",
    "data-feed-handler": "QuantConnect.Lean.Engine.DataFeeds.LiveTradingDataFeed",
    "real-time-handler": "QuantConnect.Lean.Engine.RealTime.LiveTradingRealTimeHandler",
    "transaction-handler": "QuantConnect.Lean.Engine.TransactionHandlers.BrokerageTransactionHandler",
    "history-provider": ["BrokerageHistoryProvider", "SubscriptionDataReaderHistoryProvider"],
}
QUANTCONNECT_VARIABLES = ("QC_JOB_USER_ID", "QC_API_ACCESS_TOKEN", "QC_JOB_ORGANIZATION_ID")


def fresh_output(lean, dotnet, output):
    if output.is_relative_to(lean) or output.is_relative_to(dotnet.parent) or output.exists():
        raise ValueError("use a fresh directory outside the accepted engine and SDK")
    os.umask(0o077)
    output.mkdir(parents=True, mode=0o700)
    (output / "home").mkdir()
    (output / "build").mkdir()
    shutil.copyfile(ALGORITHM, output / "build" / ALGORITHM.name)
    shutil.copyfile(common.SCRIPT_PATH, output / "order_script.json")


def compile_algorithm(prefix, dotnet, output):
    compilers = list(dotnet.parent.glob("sdk/*/Roslyn/bincore/csc.dll"))
    refpacks = list(dotnet.parent.glob("packs/Microsoft.NETCore.App.Ref/*/ref/net10.0"))
    if len(compilers) != 1 or len(refpacks) != 1:
        raise ValueError("select the accepted isolated .NET 10 SDK")
    refs = ["/dotnet/" + str(p.relative_to(dotnet.parent)) for p in sorted(refpacks[0].glob("*.dll"))]
    refs += ["/engine/" + name for name in ENGINE_REFERENCES]
    response = ["/nologo", "/target:library", "/deterministic+", "/nullable:disable", "/out:/run/build/H2HOrderScript.dll"]
    response += ['/reference:"' + p + '"' for p in refs] + ["/run/build/" + ALGORITHM.name]
    (output / "build" / "compiler.rsp").write_text("\n".join(response) + "\n")
    NATIVE.execute(prefix, ["/dotnet/dotnet", "/dotnet/" + str(compilers[0].relative_to(dotnet.parent)),
                            "@/run/build/compiler.rsp"], output, "compile", 120)


def launch(prefix, output, name, config, timeout):
    NATIVE.save(output / (name + ".config.json"), config)
    NATIVE.execute(prefix, ["/dotnet/dotnet", "/engine/QuantConnect.Lean.Launcher.dll", "--config",
                            f"/run/{name}.config.json"], output, name, timeout)


def base_config(name, *, mode, plan, extra=None):
    config = dict(BACKTEST_HANDLERS if mode == "backtest" else PAPER_HANDLERS)
    config.update({
        "environment": "backtesting" if mode == "backtest" else "live-alpaca", "live-mode": mode == "paper",
        "algorithm-type-name": "H2HOrderScriptAlgorithm", "algorithm-language": "CSharp",
        "algorithm-location": "/run/build/H2HOrderScript.dll", "composer-dll-directory": "/engine",
        "data-folder": "/data", "results-destination-folder": f"/run/{name}",
        "object-store-root": f"/run/{name}/storage", "close-automatically": True,
        "job-user-id": "0", "api-access-token": "",
        "parameters": {"script": "/run/order_script.json", "journal": f"/run/{name}/journal.jsonl",
                       "mode": mode, "plan": json.dumps(plan, sort_keys=True), **(extra or {})}})
    return config


def mounted_inputs(lean):
    return [p for root in [lean / "Data", lean / "Launcher/bin/Debug"] for p in root.rglob("*") if p.is_file()]


def read_journal(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def results_from_journal(rows, script):
    """Per-case results from the algorithm's own journal, with the protocol's
    observational rule for R10 applied: without any partial fill it is not_observable."""
    end = next((row for row in reversed(rows) if row["kind"] == "run_end"), None)
    if end is None:
        raise ValueError("journal_without_run_end")
    results = common.finalize_offline_results(end["data"]["results"], script,
                                              partial_fills_seen=end["data"]["partially_filled_orders"] > 0)
    return results, end["data"]


def command_backtest(args):
    lean, dotnet, output = args.lean_source.resolve(), args.dotnet.resolve(), args.out.resolve()
    script = common.load_script()
    fresh_output(lean, dotnet, output)
    before = {str(p.relative_to(lean)): NATIVE.digest(p) for p in sorted(mounted_inputs(lean))}
    prefix = NATIVE.sandbox(lean, dotnet, output)
    compile_algorithm(prefix, dotnet, output)
    (output / "backtest").mkdir()
    launch(prefix, output, "backtest", base_config("backtest", mode="backtest", plan=common.BACKTEST_PLAN), 900)
    unchanged = all(NATIVE.digest(lean / p) == sha for p, sha in before.items())
    rows = read_journal(output / "backtest" / "journal.jsonl")
    results, end = results_from_journal(rows, script)
    summary = common.summarize(results, script=script)
    receipt = {"engine": "lean", "mode": "backtest", "evidence_class": "HIST-backtest (local integration; bundled LEAN data)",
               "script_sha256": common.file_sha256(common.SCRIPT_PATH),
               "algorithm_sha256": common.file_sha256(ALGORITHM),
               "compiled_dll_sha256": NATIVE.digest(output / "build" / "H2HOrderScript.dll"),
               "journal_sha256": NATIVE.digest(output / "backtest" / "journal.jsonl"),
               "mounted_input_files": len(before), "mounted_inputs_unchanged": unchanged,
               "final_quantity": end["final_quantity"], "open_orders": end["open_orders"],
               "partially_filled_orders": end["partially_filled_orders"],
               "results": results, "summary": summary}
    NATIVE.save(output / "results.json", receipt)
    print(json.dumps({"summary": summary, "mounted_inputs_unchanged": unchanged}, indent=2, default=str))
    return 0 if unchanged else 3


def command_probe(args):
    lean, dotnet, output = args.lean_source.resolve(), args.dotnet.resolve(), args.out.resolve()
    plugin = args.plugin.resolve()
    if not (plugin / "QuantConnect.Brokerages.Alpaca.dll").is_file():
        raise ValueError("plugin directory lacks QuantConnect.Brokerages.Alpaca.dll")
    fresh_output(lean, dotnet, output)
    before = {str(p.relative_to(lean)): NATIVE.digest(p) for p in sorted(mounted_inputs(lean))}
    plugin_before = {p.name: NATIVE.digest(p) for p in sorted(plugin.glob("*.dll"))}
    prefix = NATIVE.sandbox(lean, dotnet, output) + ["--ro-bind", str(plugin), "/plugin"]
    compile_algorithm(prefix, dotnet, output)
    (output / "probe").mkdir()
    config = base_config("probe", mode="backtest", plan={}, extra={"probe": "alpaca-plugin"})
    config["plugin-directory"] = "/plugin"
    launch(prefix, output, "probe", config, 600)
    rows = read_journal(output / "probe" / "journal.jsonl")
    probe = next((row["data"] for row in rows if row["kind"] == "alpaca_plugin_probe"), None)
    unchanged = (all(NATIVE.digest(lean / p) == sha for p, sha in before.items())
                 and all(NATIVE.digest(plugin / n) == sha for n, sha in plugin_before.items()))
    result = {"probe": probe, "plugin_dll_sha256": plugin_before.get("QuantConnect.Brokerages.Alpaca.dll"),
              "alpaca_markets_dll_sha256": plugin_before.get("Alpaca.Markets.dll"),
              "mounted_inputs_unchanged": unchanged,
              "compatible": bool(probe and probe["found"] and probe["detail"]["all_references_match"])}
    NATIVE.save(output / "probe-result.json", result)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["compatible"] and unchanged else 3


def quantconnect_credentials(path):
    """The QuantConnect identity the Alpaca plugin's license check needs, read through
    the same fail-closed guard as the Alpaca file (0600, owner, outside worktrees)."""
    if path is None:
        raise common.H2HRefusal("h2h:lean_requires_quantconnect_license_credentials")
    guard = common._adaptive_paper_module("credential_guard")
    reason = None
    try:
        with guard.open_verified(os.fspath(path), follow_symlinks=False) as handle:
            raw = handle.read(guard.MAX_CREDENTIAL_BYTES + 1)
    except guard.CredentialGuardError as error:
        reason = str(error)
    if reason is not None:
        raise common.H2HRefusal(reason)
    values = {}
    for line in raw.decode("ascii", errors="strict").splitlines():
        name, _, value = line.strip().removeprefix("export ").partition("=")
        if name in QUANTCONNECT_VARIABLES and value.strip():
            values[name] = value.strip().strip("'\"")
    if set(values) != set(QUANTCONNECT_VARIABLES):
        raise common.H2HRefusal("h2h:quantconnect_credentials_incomplete")
    return values


def paper_sandbox(lean, dotnet, output, plugin):
    """As execution-realism's sandbox, but with the network namespace shared (the
    paper broker and QuantConnect's license endpoint are remote) and the plugin mounted."""
    prefix = NATIVE.sandbox(lean, dotnet, output)
    prefix.insert(prefix.index("--unshare-all") + 1, "--share-net")
    extra = ["--ro-bind", str(plugin), "/plugin"]
    for path in ("/etc/resolv.conf", "/etc/hosts", "/etc/nsswitch.conf", "/etc/ssl", "/etc/ca-certificates"):
        if Path(path).exists():
            extra += ["--ro-bind", path, path]
    return prefix + extra


def command_paper(args):
    alpaca = common.load_paper_env("lean", args.env_file)
    quantconnect = quantconnect_credentials(args.quantconnect_env_file)
    if not args.acknowledge_quantconnect_license_check:
        raise common.H2HRefusal("h2h:quantconnect_license_check_not_acknowledged")
    lean, dotnet, output = args.lean_source.resolve(), args.dotnet.resolve(), args.out.resolve()
    plugin = args.plugin.resolve()
    fresh_output(lean, dotnet, output)
    prefix = paper_sandbox(lean, dotnet, output, plugin)
    compile_algorithm(prefix, dotnet, output)
    name = "paper"
    (output / name).mkdir()
    plan = {"today": args.phases.split(",")}
    config = base_config(name, mode="paper", plan=plan, extra={"resume": args.resume or ""})
    config.update({"plugin-directory": "/plugin", "alpaca-api-key": alpaca["key_id"],
                   "alpaca-api-secret": alpaca["secret"], "alpaca-access-token": "",
                   "alpaca-paper-trading": "true",
                   "job-user-id": quantconnect["QC_JOB_USER_ID"],
                   "api-access-token": quantconnect["QC_API_ACCESS_TOKEN"],
                   "job-organization-id": quantconnect["QC_JOB_ORGANIZATION_ID"]})
    if config["alpaca-paper-trading"] != "true":
        raise common.H2HRefusal("h2h:not_paper_host")
    try:
        launch(prefix, output, name, config, args.timeout)
    finally:
        # The generated config carried both credential sets; it never outlives the run.
        (output / (name + ".config.json")).unlink(missing_ok=True)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("backtest", "probe-alpaca", "paper"):
        sub = commands.add_parser(name)
        sub.add_argument("--lean-source", type=Path, required=True)
        sub.add_argument("--dotnet", type=Path, required=True)
        sub.add_argument("--out", type=Path, required=True)
        if name != "backtest":
            sub.add_argument("--plugin", type=Path, required=True,
                             help="the official Alpaca plugin's build output directory")
        if name == "paper":
            sub.add_argument("--env-file", type=Path, default=None,
                             help="this engine's dedicated file: " + common.env_file_name("lean"))
            sub.add_argument("--quantconnect-env-file", type=Path, default=None)
            sub.add_argument("--acknowledge-quantconnect-license-check", action="store_true")
            sub.add_argument("--phases", default="pre_open,regular,faults,close,reconcile")
            sub.add_argument("--resume", default=None)
            sub.add_argument("--timeout", type=int, default=8 * 3600)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return {"backtest": command_backtest, "probe-alpaca": command_probe, "paper": command_paper}[args.command](args)
    except common.H2HRefusal as refusal:
        print(json.dumps({"refused": str(refusal)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
