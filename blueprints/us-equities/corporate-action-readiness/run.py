#!/usr/bin/env python3
"""Run native LEAN factor APIs and upstream tests using existing isolated binaries."""
import argparse
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from verify import verify, check_upstream_tests

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent/"execution-realism"
sys.path.insert(0, str(PREVIOUS))
SPEC = importlib.util.spec_from_file_location("accepted_native_runner", PREVIOUS/"run.py")
NATIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NATIVE)
sys.path.pop(0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean-source", type=Path, required=True)
    parser.add_argument("--dotnet", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    lean, dotnet, out = args.lean_source.resolve(), args.dotnet.resolve(), args.out.resolve()
    if out.exists() or out.is_relative_to(lean) or out.is_relative_to(dotnet.parent):
        raise ValueError("choose a fresh private directory outside existing installations")
    plan = json.loads((HERE/"plan.json").read_text())
    for name, expected in plan["inputs"].items():
        if NATIVE.digest(lean/name) != expected:
            raise ValueError("frozen input hash mismatch: " + name)
    os.umask(0o077)
    out.mkdir(parents=True, mode=0o700)
    (out/"home").mkdir()
    build = out/"build"
    build.mkdir()
    inputs = sorted({p for root in [lean/"Data", lean/"Launcher/bin/Debug", lean/"Tests/bin/Debug"] for p in root.rglob("*") if p.is_file()})
    before = {str(p.relative_to(lean)): NATIVE.digest(p) for p in inputs}
    NATIVE.save(out/"freeze.json", {"frozen_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "plan": plan,
        "plan_sha256": NATIVE.digest(HERE/"plan.json"),
        "source_hashes": {name: NATIVE.digest(HERE/name) for name in ["run.py", "verify.py", "CorporateActionProbe.cs"]},
        "helper_hashes": {name: NATIVE.digest(PREVIOUS/name) for name in ["run.py", "analyze.py"]},
        "mounted_inputs": before})
    shutil.copyfile(HERE/"CorporateActionProbe.cs", build/"CorporateActionProbe.cs")
    shutil.copyfile(HERE/"plan.json", out/"plan.json")
    # Only explicit public local test configuration is supplied; no host client config.
    NATIVE.save(out/"config.json", {"data-folder": "/data", "composer-dll-directory": "/engine",
        "map-file-provider": "QuantConnect.Data.Auxiliary.LocalDiskMapFileProvider",
        "factor-file-provider": "QuantConnect.Data.Auxiliary.LocalDiskFactorFileProvider",
        "data-provider": "QuantConnect.Lean.Engine.DataFeeds.DefaultDataProvider"})
    prefix = NATIVE.sandbox(lean, dotnet, out)
    compilers = list(dotnet.parent.glob("sdk/*/Roslyn/bincore/csc.dll"))
    packs = list(dotnet.parent.glob("packs/Microsoft.NETCore.App.Ref/*/ref/net10.0"))
    if len(compilers) != 1 or len(packs) != 1:
        raise ValueError("use accepted isolated .NET10 SDK")
    refs = ["/dotnet/"+str(p.relative_to(dotnet.parent)) for p in sorted(packs[0].glob("*.dll"))]
    refs += ["/engine/"+x for x in ["QuantConnect.Common.dll", "QuantConnect.Configuration.dll", "QuantConnect.Logging.dll", "NodaTime.dll", "Python.Runtime.dll"]]
    response = ["/nologo", "/target:exe", "/deterministic+", "/out:/run/build/CorporateActionProbe.dll"]
    response += ['/reference:"'+p+'"' for p in refs] + ["/run/build/CorporateActionProbe.cs"]
    (build/"compiler.rsp").write_text("\n".join(response)+"\n")
    for source in (lean/"Launcher/bin/Debug").glob("*.dll"):
        (build/source.name).symlink_to("/engine/"+source.name)
    NATIVE.execute(prefix, ["/dotnet/dotnet", "/dotnet/"+str(compilers[0].relative_to(dotnet.parent)), "@/run/build/compiler.rsp"], out, "compile", 60)
    NATIVE.execute(prefix, ["/dotnet/dotnet", "exec", "--runtimeconfig", "/engine/QuantConnect.Lean.Launcher.runtimeconfig.json",
        "--depsfile", "/engine/QuantConnect.Lean.Launcher.deps.json", "/run/build/CorporateActionProbe.dll", "/run/native-results.json"], out, "probe", 60)
    native = json.loads((out/"native-results.json").read_text())
    checked = verify(native)
    NATIVE.save(out/"verification.json", checked)
    # NUnit's upstream AssemblyInitialize changes cwd to TestDirectory and resets
    # Config. Overlay the same explicit local configuration at that location.
    test_prefix = prefix+["--ro-bind", str(lean/"Tests/bin/Debug"), "/tests",
                          "--ro-bind", str(out/"config.json"), "/tests/config.json"]
    tests = {"status": "unresolved"}
    try:
        NATIVE.execute(test_prefix, ["/dotnet/dotnet", "vstest", "/tests/QuantConnect.Tests.dll",
            "--TestCaseFilter:"+plan["native_upstream_tests"], "--ResultsDirectory:/run/test-results", "--Logger:trx;LogFileName=factor-tests.trx"], out, "upstream-tests", 90)
        tests["command_exit_zero"] = True
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        tests["failure_type"] = type(exc).__name__
    trx = out/"test-results/factor-tests.trx"
    if trx.exists():
        tree = ET.parse(trx)
        ns = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
        counters = tree.find(".//t:Counters", ns)
        tests["counters"] = counters.attrib if counters is not None else {}
        tests["cases"] = [{k: r.attrib.get(k) for k in ["testName", "outcome"]} for r in tree.findall(".//t:UnitTestResult", ns)]
    if tests.get("command_exit_zero"):
        try:
            check_upstream_tests(tests)
            tests["status"] = "passed"
        except ValueError as exc:
            tests["failure_type"] = str(exc)
    unchanged = all(NATIVE.digest(lean/name) == sha for name, sha in before.items())
    if not unchanged:
        raise ValueError("mounted input changed")
    result = {"probe": checked, "upstream_tests": tests, "mounted_inputs_unchanged": unchanged,
        "mounted_input_files": len(before), "freeze_sha256": NATIVE.digest(out/"freeze.json")}
    NATIVE.save(out/"results.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
