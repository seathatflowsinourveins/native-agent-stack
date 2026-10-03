#!/usr/bin/env python3
"""Deterministic test-file shards for the suite-shards trial (2026-10-03), stdlib only.

  python3 make_shards.py --os ubuntu-24.04 --root . --weights weights.json --out DIR

For each shard arm of the OS (ARMS) it assigns every test file tests/test_*.py of the checkout at --root,
named as the dotted module tests.<stem>, to exactly one shard list or to the arm's serial tail, and writes

  DIR/<arm>/shard-<i>.txt   the modules of shard i (i = 0 .. shards-1), sorted, one per line
  DIR/<arm>/tail.txt        the tail modules, sorted, one per line (an empty file when the arm has no tail)
  DIR/plan.json             every list, its predicted load and the modules that took the default weight

Shards are built from files, never from id prefixes: a file such as tests/test_native_maintenance.py adds
test classes through load_tests under other module names, and those ids belong to the file that loads them.

The assignment is longest-processing-time-first: modules in order of decreasing weight, ties by module
name, each to the shard with the smallest load so far, ties to the lowest shard index. Weights are whole
milliseconds, so every comparison is exact integer arithmetic and the lists depend only on the module set
and the weights file. A module missing from the weights file (one added after the weights were measured)
takes DEFAULT: the mean of the file's weights, rounded down to a millisecond; it is assigned like any other
module, so a new module can never drop out of the lists. A weights entry for a file that no longer exists
is ignored and reported.

Fails closed (exit 1, nothing written for the arm) when a shard would be empty (`python3 -m unittest -v`
with no module runs the whole suite by discovery), when a tail module does not exist, or when a module is
not exactly once in the lists of an arm.

Provenance: the weights rule and the LPT loop follow the coordinator's local preflight script pf_prepare.py
of 2026-10-03 (lines 24-55), which is not in this repository; README.md records the check that these
lists reproduce that script's lists for the same 233 modules.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

SCHEMA = "suite-shards-plan/1"
WEIGHTS_SCHEMA = "suite-shards-weights/1"
SERIAL_TAIL = ("tests.test_secret_path_guard",)
# The preregistered arms (README.md, "Arms"). S is the serial production command and has no lists.
ARMS = {
    "ubuntu-24.04": {"G4": {"shards": 4, "tail": ()}, "G4T": {"shards": 4, "tail": SERIAL_TAIL}},
    "macos-15": {"G3": {"shards": 3, "tail": ()}, "G3T": {"shards": 3, "tail": SERIAL_TAIL}},
}
MODULE_RE = re.compile(r"tests\.test_[A-Za-z0-9_]+")
MILLI = Decimal(1000)


class ShardError(Exception):
    """A plan that cannot be used (exit 1)."""


def test_modules(root: Path) -> list:
    """The dotted names of tests/test_*.py at root, sorted by code point."""
    return sorted(f"tests.{path.stem}" for path in (root / "tests").glob("test_*.py") if path.is_file())


def load_weights(path: Path) -> dict:
    """{module: whole milliseconds} from the frozen weights file; every value a non-negative number with at
    most three decimals."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal, parse_int=Decimal)
    except (OSError, ValueError) as error:
        raise ShardError(f"{path.name}: unreadable weights file ({error})") from None
    if not isinstance(data, dict) or data.get("schema") != WEIGHTS_SCHEMA or not isinstance(data.get("weights"), dict):
        raise ShardError(f"{path.name}: not a {WEIGHTS_SCHEMA} file")
    weights = {}
    for module, value in data["weights"].items():
        if not MODULE_RE.fullmatch(module):
            raise ShardError(f"{path.name}: {module!r} is not a tests.test_* module name")
        try:
            milliseconds = value * MILLI
        except (TypeError, InvalidOperation):
            raise ShardError(f"{path.name}: the weight of {module} is not a number") from None
        if not isinstance(value, Decimal) or value < 0 or milliseconds != milliseconds.to_integral_value():
            raise ShardError(f"{path.name}: the weight of {module} is not a non-negative number of whole milliseconds")
        weights[module] = int(milliseconds)
    if not weights:
        raise ShardError(f"{path.name}: no weights")
    return weights


def default_weight(weights: dict) -> int:
    """The weight of a module the file does not list: the mean of the file's weights, rounded down (0 for none;
    load_weights never returns an empty mapping)."""
    return sum(weights.values()) // len(weights) if weights else 0


def assign(modules: list, weights: dict, shards: int, tail: tuple, default: int) -> dict:
    """One arm's lists: {"shards": [[module, ...], ...], "tail": [...], "loads_ms": [...], "defaulted": [...]}."""
    if shards < 1:
        raise ShardError("an arm needs at least one shard")
    missing_tail = sorted(set(tail) - set(modules))
    if missing_tail:
        raise ShardError(f"tail modules not in the checkout: {missing_tail}")
    movable = [module for module in modules if module not in tail]
    lists = [[] for _ in range(shards)]
    loads = [0] * shards
    weight = {module: weights.get(module, default) for module in modules}
    for module in sorted(movable, key=lambda name: (-weight[name], name)):
        index = min(range(shards), key=lambda k: (loads[k], k))
        lists[index].append(module)
        loads[index] += weight[module]
    if any(not members for members in lists):
        raise ShardError(f"{shards} shards for {len(movable)} modules: a shard would be empty")
    return {"shards": [sorted(members) for members in lists], "tail": sorted(tail), "loads_ms": loads,
            "tail_ms": sum(weight[module] for module in tail),
            "defaulted": sorted(module for module in modules if module not in weights)}


def coverage_problems(modules: list, arm_plan: dict) -> list:
    """Every module exactly once across the arm's shard lists and tail, nothing else."""
    listed = [module for members in arm_plan["shards"] for module in members] + list(arm_plan["tail"])
    problems = []
    seen = set()
    for module in listed:
        if module in seen:
            problems.append(f"{module} is listed twice")
        seen.add(module)
    problems += [f"{module} is in no list" for module in modules if module not in seen]
    problems += [f"{module} is not a test file of the checkout" for module in sorted(seen - set(modules))]
    problems += [f"shard {index} is empty" for index, members in enumerate(arm_plan["shards"]) if not members]
    return problems


def plan_for(os_name: str, modules: list, weights: dict) -> dict:
    """{arm: arm plan} for every shard arm of the OS."""
    if os_name not in ARMS:
        raise ShardError(f"unknown OS {os_name!r}; preregistered: {sorted(ARMS)}")
    if not modules:
        raise ShardError("no tests/test_*.py module in the checkout")
    bad = [module for module in modules if not MODULE_RE.fullmatch(module)]
    if bad:
        raise ShardError(f"test file names outside tests.test_[A-Za-z0-9_]+: {bad}")
    default = default_weight(weights)
    plan = {}
    for arm, spec in ARMS[os_name].items():
        arm_plan = assign(modules, weights, spec["shards"], spec["tail"], default)
        problems = coverage_problems(modules, arm_plan)
        if problems:
            raise ShardError(f"{arm}: {'; '.join(problems)}")
        plan[arm] = arm_plan
    return plan


def write_plan(plan: dict, out: Path) -> None:
    for arm, arm_plan in plan.items():
        directory = out / arm
        directory.mkdir(parents=True, exist_ok=True)
        for index, members in enumerate(arm_plan["shards"]):
            (directory / f"shard-{index}.txt").write_text("".join(f"{module}\n" for module in members), encoding="utf-8")
        (directory / "tail.txt").write_text("".join(f"{module}\n" for module in arm_plan["tail"]), encoding="utf-8")


def read_list(path: Path) -> list:
    """The modules of one written list file, in file order (blank lines are not allowed)."""
    text = path.read_text(encoding="utf-8")
    if text == "":
        return []
    if not text.endswith("\n"):
        raise ShardError(f"{path.name}: no final newline")
    lines = text[:-1].split("\n")
    if any(not MODULE_RE.fullmatch(line) for line in lines):
        raise ShardError(f"{path.name}: a line is not a tests.test_* module name")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--os", required=True, choices=sorted(ARMS))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        modules = test_modules(args.root)
        weights = load_weights(args.weights)
        plan = plan_for(args.os, modules, weights)
    except ShardError as error:
        print(f"make_shards.py: {error}", file=sys.stderr)
        return 1
    write_plan(plan, args.out)
    summary = {"schema": SCHEMA, "os": args.os, "modules": len(modules),
               "weights_sha256": hashlib.sha256(args.weights.read_bytes()).hexdigest(),
               "default_weight_ms": default_weight(weights),
               "stale_weights": sorted(set(weights) - set(modules)), "arms": plan}
    (args.out / "plan.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for arm, arm_plan in plan.items():
        loads = ", ".join(f"{load / 1000:.1f}" for load in arm_plan["loads_ms"])
        print(f"{arm}: {len(arm_plan['shards'])} shards, predicted seconds [{loads}], tail "
              f"{arm_plan['tail'] or 'none'} ({arm_plan['tail_ms'] / 1000:.1f} s); "
              f"default weight for {arm_plan['defaulted'] or 'no module'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
