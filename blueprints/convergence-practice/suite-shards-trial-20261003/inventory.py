#!/usr/bin/env python3
"""The fail-closed inventory gate of the suite-shards trial (2026-10-03), stdlib only.

  python3 inventory.py --os ubuntu-24.04 --root . --weights weights.json --out DIR

Run it with the interpreter of the arms. It loads the suite twice, each time in a fresh child interpreter
whose working directory is the checkout root and whose import path starts with it, as `python3 -m unittest`
has, and runs no test:

  discovery  unittest.TestLoader().discover(".", "test*.py", None): what the serial arm S collects
             (CPython Lib/unittest/main.py, TestProgram._do_discovery: start ".", pattern "test*.py",
             top-level directory None).
  by name    unittest.TestLoader().loadTestsFromName("tests.<stem>") for every tests/test_*.py file, one
             after the other: what one shard, `python3 -m unittest -v <modules>`, collects. A file that adds
             classes through load_tests under other module names owns those ids.

It exits 0 only when all of these hold, and 1 otherwise (the inventory job then fails and no arm runs):

  (a) parity: the ids loaded by name, over all files, are exactly the discovery ids;
  (b) no id is loaded twice: not by two files, not twice by one file, not twice by discovery;
  (c) no import failure: no loader error and no loader-made id (unittest.loader._FailedTest or
      unittest.loader.ModuleSkipped) in either load, and neither child interpreter fails;
  (d) make_shards.py builds every shard arm of the OS from the frozen weights, and every test file is in
      exactly one shard list or the tail of each arm, read back from the written files.

A child interpreter stopped from outside, by one of EXTERNAL_SIGNALS (the kernel's out-of-memory killer sends
SIGKILL; a runner that stops a job sends SIGINT, SIGTERM or SIGKILL), is an execution problem of the gate, not a
finding: report.json lists it under execution_problems, with parity null, and the gate still fails (exit 1), but
compare.py then counts the run as incomplete rather than as a failed gate. Any other failure of a child (a non-zero
exit, an end by another signal, output that is not JSON) is a finding under (c).

It writes DIR/inventory.txt (the sorted discovery ids), DIR/module_ids.json ({file module: [ids in load
order]}), DIR/shards/<arm>/ (make_shards.py's lists) and DIR/report.json (counts, the interpreter, every
finding under problems and every execution problem). report.json is written whatever the outcome.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import platform
import signal
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import make_shards  # noqa: E402  (this directory's frozen shard generator)

SCHEMA = "suite-shards-inventory/1"
LOADER_MADE = ("unittest.loader._FailedTest.", "unittest.loader.ModuleSkipped.")
LIST_CAP = 50
EXTERNAL_SIGNALS = ("SIGKILL", "SIGTERM", "SIGINT", "SIGHUP")


class ChildStopped(RuntimeError):
    """A child interpreter that one of EXTERNAL_SIGNALS stopped: an execution problem, not a finding."""


def iter_ids(suite):
    """Every test id of a (nested) suite, in load order, without running anything."""
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_ids(item)
        else:
            yield item.id()


def child_phase(phase: str, root: Path) -> dict:
    """The child interpreter's work: one load of the suite at root, nothing run."""
    sys.path[:] = [entry for entry in sys.path if Path(entry or os.curdir).resolve() != HERE]
    sys.path.insert(0, str(root))
    os.chdir(root)
    loader = unittest.TestLoader()
    if phase == "discover":
        ids = list(iter_ids(loader.discover(".", "test*.py", None)))
        return {"ids": ids, "errors": [str(error)[:500] for error in loader.errors]}
    owned, errors = {}, {}
    for module in make_shards.test_modules(root):
        before = len(loader.errors)
        owned[module] = list(iter_ids(loader.loadTestsFromName(module)))
        if len(loader.errors) > before:
            errors[module] = [str(error)[:500] for error in loader.errors[before:]]
    return {"modules": owned, "errors": errors}


def child_failure(phase: str, returncode: int, stderr: str) -> RuntimeError:
    """The error for a child that did not exit 0: ChildStopped when one of EXTERNAL_SIGNALS ended it (subprocess
    gives a negative return code for a signal), a RuntimeError (a finding) otherwise."""
    if returncode < 0:
        try:
            name = signal.Signals(-returncode).name
        except ValueError:
            name = f"signal {-returncode}"
        if name in EXTERNAL_SIGNALS:
            return ChildStopped(f"the {phase} child interpreter was stopped by {name} from outside: {stderr[-2000:]}")
        return RuntimeError(f"the {phase} child interpreter ended by {name}: {stderr[-2000:]}")
    return RuntimeError(f"the {phase} child interpreter exited {returncode}: {stderr[-2000:]}")


def run_child(phase: str, root: Path) -> dict:
    done = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--phase", phase, "--root", str(root)],
                          capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise child_failure(phase, done.returncode, done.stderr)
    return json.loads(done.stdout)


def load_problems(discovered: dict, by_name: dict) -> tuple:
    """(problems, owners): rules (a), (b) and (c) over the two loads; owners maps each id to its file."""
    problems = []
    ids = discovered["ids"]
    if not ids:
        problems.append("discovery found no test")
    if discovered["errors"]:
        problems.append(f"discovery reported {len(discovered['errors'])} loader errors: {discovered['errors'][:3]}")
    made = [item for item in ids if item.startswith(LOADER_MADE)]
    if made:
        problems.append(f"discovery holds {len(made)} loader-made ids (import failures or module skips): "
                        f"{made[:LIST_CAP]}")
    repeated = sorted(item for item, count in collections.Counter(ids).items() if count > 1)
    if repeated:
        problems.append(f"discovery loads {len(repeated)} ids more than once: {repeated[:LIST_CAP]}")
    owners, twice = {}, []
    for module, owned in by_name["modules"].items():
        made = [item for item in owned if item.startswith(LOADER_MADE)]
        if made:
            problems.append(f"{module}: loading it by name gives loader-made ids (an import failure): {made[:5]}")
        for item in owned:
            if item in owners:
                twice.append(f"{item} ({owners[item]} and {module})")
            owners[item] = module
    if by_name["errors"]:
        problems.append(f"loading by name reported loader errors in {sorted(by_name['errors'])[:LIST_CAP]}")
    if twice:
        problems.append(f"{len(twice)} ids are loaded twice by name: {twice[:LIST_CAP]}")
    only_discovery = sorted(set(ids) - set(owners))
    only_by_name = sorted(set(owners) - set(ids))
    if only_discovery:
        problems.append(f"{len(only_discovery)} discovery ids are loaded by no test file by name: "
                        f"{only_discovery[:LIST_CAP]}")
    if only_by_name:
        problems.append(f"{len(only_by_name)} ids loaded by name are not discovery ids: {only_by_name[:LIST_CAP]}")
    return problems, owners


def shard_problems(os_name: str, modules: list, weights_path: Path, out: Path, report: dict) -> list:
    """Rule (d): build and write every arm's lists, read them back, check that each file is listed once."""
    try:
        weights = make_shards.load_weights(weights_path)
        plan = make_shards.plan_for(os_name, modules, weights)
        make_shards.write_plan(plan, out)
        problems = []
        for arm, arm_plan in plan.items():
            written = {"shards": [make_shards.read_list(out / arm / f"shard-{index}.txt")
                                  for index in range(len(arm_plan["shards"]))],
                       "tail": make_shards.read_list(out / arm / "tail.txt")}
            problems += [f"{arm}: {problem}" for problem in make_shards.coverage_problems(modules, written)]
            if written != {"shards": arm_plan["shards"], "tail": arm_plan["tail"]}:
                problems.append(f"{arm}: the written lists differ from the plan")
    except make_shards.ShardError as error:
        return [f"make_shards.py: {error}"]
    report["arms"] = {arm: {"modules_per_shard": [len(members) for members in arm_plan["shards"]],
                            "predicted_seconds": [load / 1000 for load in arm_plan["loads_ms"]],
                            "tail": arm_plan["tail"], "tail_predicted_seconds": arm_plan["tail_ms"] / 1000,
                            "default_weight_modules": arm_plan["defaulted"]} for arm, arm_plan in plan.items()}
    report["default_weight_ms"] = make_shards.default_weight(weights)
    report["stale_weights"] = sorted(set(weights) - set(modules))
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--phase", choices=("discover", "by-name"), help=argparse.SUPPRESS)
    parser.add_argument("--os", choices=sorted(make_shards.ARMS))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--weights", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.phase:
        json.dump(child_phase(args.phase, root), sys.stdout)
        return 0
    if not (args.os and args.weights and args.out):
        parser.error("--os, --weights and --out are required")
    args.out.mkdir(parents=True, exist_ok=True)
    modules = make_shards.test_modules(root)
    report = {"schema": SCHEMA, "os": args.os, "python_version": platform.python_version(),
              "python_implementation": platform.python_implementation(), "platform": platform.platform(),
              "test_files": len(modules), "parity": False, "problems": [], "execution_problems": []}
    problems, execution = report["problems"], report["execution_problems"]
    try:
        discovered = run_child("discover", root)
        by_name = run_child("by-name", root)
    except ChildStopped as error:
        execution.append(str(error))
        report["parity"] = None  # not judged: a child stopped from outside never finished its load
        discovered = by_name = None
    except (RuntimeError, ValueError) as error:
        problems.append(str(error))
        discovered = by_name = None
    if discovered is not None:
        found, owners = load_problems(discovered, by_name)
        problems.extend(found)
        report.update({"discovery_ids": len(discovered["ids"]), "unique_discovery_ids": len(set(discovered["ids"])),
                       "ids_loaded_by_name": sum(len(owned) for owned in by_name["modules"].values()),
                       "test_files_without_tests": sorted(m for m, owned in by_name["modules"].items() if not owned),
                       "parity": not found})
        (args.out / "inventory.txt").write_text("".join(f"{item}\n" for item in sorted(set(discovered["ids"]))),
                                                encoding="utf-8")
        (args.out / "module_ids.json").write_text(json.dumps(by_name["modules"], indent=0, sort_keys=True) + "\n",
                                                  encoding="utf-8")
    problems.extend(shard_problems(args.os, modules, args.weights, args.out / "shards", report))
    report["ok"] = not problems and not execution
    (args.out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"inventory.py: {report['test_files']} test files, {report.get('discovery_ids')} discovery ids, "
          f"{report.get('ids_loaded_by_name')} ids loaded by name, parity {report['parity']}, "
          f"{len(problems)} problems, {len(execution)} execution problems", file=sys.stderr)
    for problem in problems:
        print(f"inventory.py: {problem}", file=sys.stderr)
    for problem in execution:
        print(f"inventory.py: execution problem (not a finding): {problem}", file=sys.stderr)
    for arm, entry in (report.get("arms") or {}).items():
        print(f"inventory.py: {arm}: modules per shard {entry['modules_per_shard']}, predicted seconds "
              f"{[round(value, 1) for value in entry['predicted_seconds']]}, tail {entry['tail'] or 'none'}, "
              f"default weight for {entry['default_weight_modules'] or 'no module'}", file=sys.stderr)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
