#!/usr/bin/env python3
"""Partition native unittest discovery by its module-suite entrypoints.

Sources: python/cpython@v3.12.3 Lib/unittest/loader.py:109-129, 229-340,
Lib/unittest/suite.py, and the public TestLoader/TestSuite/TextTestRunner APIs:
https://docs.python.org/3.12/library/unittest.html#unittest.TestLoader
This is assignment/report glue; native unittest owns discovery and execution.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time
import unittest


SCHEMA_VERSION = 1
COUNT_KEYS = ("ran", "failures", "errors", "skipped", "expected_failures", "unexpected_successes")
WEIGHTS = Path(__file__).with_name("validate_shard_weights.json")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def load_json(path):
    def unique(pairs):
        output = {}
        for key, value in pairs:
            if key in output:
                raise ValueError("duplicate JSON key")
            output[key] = value
        return output
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def count_map(value):
    if not isinstance(value, dict) or any(not isinstance(key, str) or not key or type(n) is not int or n <= 0 for key, n in value.items()):
        raise ValueError("invalid identity multiplicities")
    return Counter(value)


def load_weights(path):
    raw = path.read_bytes()
    data = load_json(path)
    fallback = data.get("fallback_seconds")
    weights = data.get("module_weights_seconds")
    if type(fallback) not in (int, float) or not math.isfinite(fallback) or fallback <= 0 or not isinstance(weights, dict):
        raise ValueError("invalid duration fallback")
    for module, seconds in weights.items():
        if not isinstance(module, str) or type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError("invalid module duration")
    return weights, float(fallback), hashlib.sha256(raw).hexdigest()


def leaves(suite):
    if isinstance(suite, unittest.TestSuite):
        for item in suite:
            yield from leaves(item)
    elif isinstance(suite, unittest.TestCase):
        yield suite
    else:
        raise ValueError("unsupported native suite object")


class DiscoveryLoader(unittest.TestLoader):
    """Observe the public module loader; preserve outer load_tests ownership."""

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.records = []

    def loadTestsFromModule(self, module, *, pattern=None):
        outer = self.depth == 0
        self.depth += 1
        try:
            suite = super().loadTestsFromModule(module, pattern=pattern)
        finally:
            self.depth -= 1
        if outer:
            self.records.append((module.__name__, suite))
        return suite


def discover(root):
    loader = DiscoveryLoader()
    suite = loader.discover(str(root), pattern="test*.py", top_level_dir=str(root))
    records = defaultdict(deque)
    for module, owned in loader.records:
        records[id(owned)].append(module)
    owners, inventory = [], []
    for owned in suite:
        kind = "native-module"
        if records[id(owned)]:
            module = records[id(owned)].popleft()
        else:
            items = list(leaves(owned))
            if len(items) != 1:
                raise ValueError("unmatched native discovery suite")
            item = items[0]
            name = type(item).__name__
            # Discovery itself creates these import failure/skip suites without
            # calling loadTestsFromModule. Use public id(), pinned to the source
            # format in CPython v3.12.3 loader.py:22-57; never silently drop one.
            prefix = f"unittest.loader.{name}."
            if type(item).__module__ != "unittest.loader" or name not in ("_FailedTest", "ModuleSkipped") or not item.id().startswith(prefix):
                raise ValueError("unsupported native discovery placeholder")
            module = item.id()[len(prefix):]
            kind = "native-import-error" if name == "_FailedTest" else "native-import-skip"
        items = list(leaves(owned))
        ids = [item.id() for item in items]
        if any(not isinstance(value, str) or not value for value in ids):
            raise ValueError("unrecognized native identity")
        row = {"module": module, "case_count": len(ids), "case_id_counts": dict(Counter(ids)),
               "case_order_sha256": digest(ids), "origins": sorted({type(item).__module__ for item in items}), "kind": kind}
        inventory.append(row)
        owners.append((module, owned))
    if len({row["module"] for row in inventory}) != len(inventory) or any(records.values()):
        raise ValueError("duplicate or unmatched discovery ownership")
    complete = Counter(item.id() for item in leaves(suite))
    owned_ids = Counter()
    for row in inventory:
        owned_ids.update(row["case_id_counts"])
    if complete != owned_ids or sum(complete.values()) != suite.countTestCases():
        raise ValueError("module inventories do not cover native discovery")
    return owners, inventory, len(loader.errors)


def assignment(inventory, shards, weights, fallback):
    origins = defaultdict(set)
    for row in inventory:
        for origin in row["origins"]:
            if origin != "unittest.loader":
                origins[origin].add(row["module"])
    shared = {origin: sorted(modules) for origin, modules in origins.items() if len(modules) > 1}
    if shared:
        # Filtering/parallelizing owners can change native module/class fixture
        # transitions and skip counts. Preserve global serial order, not a
        # deduplicated approximation; report the performance constraint.
        return {row["module"]: 0 for row in inventory}, "serial-native-fixture-fallback", shared
    loads = [0.0] * shards
    seconds = {row["module"]: (weights.get(row["module"], fallback) if row["case_count"] else 0.0) for row in inventory}
    mapping = {}
    for module in sorted(seconds, key=lambda name: (-seconds[name], name)):
        shard = min(range(shards), key=lambda number: (loads[number], number))
        mapping[module] = shard
        loads[shard] += seconds[module]
    return mapping, "duration-weighted-native-modules", {}


class ModuleSuite(unittest.TestSuite):
    def __init__(self, module, suite):
        super().__init__([suite])
        self.module = module

    def run(self, result, debug=False):
        result.executed_modules.append(self.module)
        return super().run(result, debug=debug)


class ShardResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executed_modules = []
        self.case_id_counts = Counter()

    def startTest(self, test):
        self.case_id_counts[test.id()] += 1
        super().startTest(test)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_shard(args):
    began = time.monotonic()
    report = {"schema_version": SCHEMA_VERSION, "shard": args.shard, "shards": args.shards,
              "success": False, "errors": []}
    try:
        root = Path.cwd().resolve()
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                              text=True, capture_output=True).stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{40}", head):
            raise ValueError("invalid checkout identity")
        weights, fallback, weights_sha = load_weights(args.weights)
        owners, inventory, loader_errors = discover(root)
        mapping, strategy, constraints = assignment(inventory, args.shards, weights, fallback)
        assigned = [module for module, _ in owners if mapping[module] == args.shard]
        selected = unittest.TestSuite(ModuleSuite(module, suite) for module, suite in owners if module in assigned)
        expected = Counter()
        for row in inventory:
            if row["module"] in assigned:
                expected.update(row["case_id_counts"])
        report.update(head_commit=head, weights_sha256=weights_sha,
            python_version=list(sys.version_info[:3]), discovery_sha256=digest(inventory), inventory=inventory,
            assigned_modules=assigned, scheduled_case_id_counts=dict(expected), strategy=strategy,
            fixture_constraints=constraints, loader_error_count=loader_errors)
        runner = unittest.TextTestRunner(verbosity=args.verbosity, durations=args.durations, resultclass=ShardResult)
        result = runner.run(selected)
        counts = {"ran": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                  "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
                  "unexpected_successes": len(result.unexpectedSuccesses)}
        report.update(counts=counts, case_id_counts=dict(result.case_id_counts),
                      executed_modules=result.executed_modules, native_should_stop=result.shouldStop)
        if not sum(row["case_count"] for row in inventory):
            report["errors"].append("native discovery loaded no tests")
        if result.executed_modules != assigned:
            report["errors"].append("not every assigned module suite was entered")
        if result.shouldStop:
            report["errors"].append("native runner stopped before coverage could be accepted")
        if result.testsRun != sum(result.case_id_counts.values()) or result.case_id_counts - expected:
            report["errors"].append("native started case counts do not match the scheduled inventory")
        report["success"] = result.wasSuccessful() and not report["errors"]
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        report["errors"].append(type(exc).__name__)
    report["elapsed_seconds"] = round(time.monotonic() - began, 3)
    write_json(args.report, report)
    print(json.dumps({"shard": args.shard, "success": report["success"], "counts": report.get("counts"),
                      "modules": len(report.get("executed_modules", []))}, sort_keys=True))
    return 0 if report["success"] else 1


def validate_report(row, shards):
    if not isinstance(row, dict) or type(row.get("schema_version")) is not int or row["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported report schema")
    if type(row.get("shard")) is not int or not 0 <= row["shard"] < shards or row.get("shards") != shards or type(row.get("shards")) is not int:
        raise ValueError("incorrect shard identity")
    if row.get("success") is not True or row.get("errors") != [] or row.get("native_should_stop") is not False:
        raise ValueError("partial, failed or stopped shard report")
    elapsed = row.get("elapsed_seconds")
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError("invalid elapsed time")
    for key, pattern in (("head_commit", r"[0-9a-f]{40}"), ("weights_sha256", r"[0-9a-f]{64}"), ("discovery_sha256", r"[0-9a-f]{64}")):
        if not isinstance(row.get(key), str) or not re.fullmatch(pattern, row[key]):
            raise ValueError("invalid input binding")
    if not isinstance(row.get("python_version"), list) or len(row["python_version"]) != 3 or any(type(n) is not int or n < 0 for n in row["python_version"]):
        raise ValueError("invalid interpreter binding")
    inventory = row.get("inventory")
    if not isinstance(inventory, list) or digest(inventory) != row["discovery_sha256"]:
        raise ValueError("invalid discovery binding")
    modules = set()
    for entry in inventory:
        if not isinstance(entry, dict) or not isinstance(entry.get("module"), str) or not entry["module"] or entry["module"] in modules:
            raise ValueError("invalid or duplicated discovery owner")
        modules.add(entry["module"])
        cases = count_map(entry.get("case_id_counts"))
        if type(entry.get("case_count")) is not int or entry["case_count"] < 0 or sum(cases.values()) != entry["case_count"]:
            raise ValueError("invalid discovery case count")
        if not isinstance(entry.get("origins"), list) or any(not isinstance(n, str) or not n for n in entry["origins"]):
            raise ValueError("invalid discovery origin")
        if not isinstance(entry.get("case_order_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", entry["case_order_sha256"]):
            raise ValueError("invalid discovery order binding")
        if entry.get("kind") not in ("native-module", "native-import-error", "native-import-skip"):
            raise ValueError("unknown discovery entry kind")
    for key in ("assigned_modules", "executed_modules"):
        values = row.get(key)
        if not isinstance(values, list) or any(not isinstance(n, str) or n not in modules for n in values) or len(set(values)) != len(values):
            raise ValueError("invalid executed module inventory")
    if row["assigned_modules"] != row["executed_modules"]:
        raise ValueError("assigned module coverage missing")
    counts = row.get("counts")
    if not isinstance(counts, dict) or set(counts) != set(COUNT_KEYS) or any(type(n) is not int or n < 0 for n in counts.values()):
        raise ValueError("invalid native counts")
    if counts["failures"] or counts["errors"] or counts["unexpected_successes"]:
        raise ValueError("native failure concealed by report success")
    started, scheduled = count_map(row.get("case_id_counts")), count_map(row.get("scheduled_case_id_counts"))
    if sum(started.values()) != counts["ran"] or started - scheduled:
        raise ValueError("native identity counts disagree")
    expected = Counter()
    for entry in inventory:
        if entry["module"] in row["assigned_modules"]:
            expected.update(entry["case_id_counts"])
    if scheduled != expected:
        raise ValueError("scheduled native case coverage missing")


def aggregate(args):
    output = {"schema_version": SCHEMA_VERSION, "success": False, "errors": [], "job_result": args.job_result}
    paths = sorted(args.reports.rglob("report.json"))
    available, identities, unqualified = defaultdict(list), Counter(), []
    for path in paths:
        try:
            row = load_json(path)
            shard = row.get("shard") if isinstance(row, dict) else None
            counts = row.get("counts") if isinstance(row, dict) else None
            if type(shard) is not int or not 0 <= shard < args.shards:
                raise ValueError("unrecognized shard identity")
            identities[shard] += 1
            if not isinstance(counts, dict) or set(counts) != set(COUNT_KEYS) or any(type(n) is not int or n < 0 for n in counts.values()):
                raise ValueError("no qualified count fields")
            available[shard].append((row, counts))
        except (OSError, ValueError):
            unqualified.append(str(path.relative_to(args.reports)))
    totals = Counter({key: 0 for key in COUNT_KEYS})
    per_shard, unknown = [], []
    for shard in range(args.shards):
        copies = available.get(shard, [])
        if len(copies) == 1 and identities[shard] == 1:
            row, counts = copies[0]
            totals.update(counts)
            per_shard.append({"shard": shard, "counts": counts, "reported_success": row.get("success") is True})
        else:
            # Never sum duplicate receipts for the same execution slot.
            unknown.append(shard)
            per_shard.append({"shard": shard, "counts": None, "reason": "missing-or-duplicate-count-receipt"})
    output.update(counts=dict(totals) if len(unknown) < args.shards else None,
                  counts_complete=not unknown and not unqualified,
                  per_shard_counts=per_shard, unknown_count_shards=unknown,
                  unqualified_count_reports=unqualified)
    try:
        if args.job_result != "success":
            raise ValueError("matrix result is not success")
        if len(paths) != args.shards:
            raise ValueError("missing or extra shard reports")
        rows = [load_json(path) for path in paths]
        for row in rows:
            validate_report(row, args.shards)
        if sorted(row["shard"] for row in rows) != list(range(args.shards)):
            raise ValueError("duplicate or missing shard identity")
        rows.sort(key=lambda row: row["shard"])
        first = rows[0]
        for row in rows[1:]:
            if any(row[key] != first[key] for key in ("head_commit", "weights_sha256", "python_version", "discovery_sha256", "inventory")):
                raise ValueError("shards did not discover the same input")
        weights, fallback, weights_sha = load_weights(args.weights)
        if weights_sha != first["weights_sha256"]:
            raise ValueError("aggregate weights differ from the executed input")
        head = subprocess.run(["git", "rev-parse", "HEAD"], check=True, text=True, capture_output=True).stdout.strip()
        if head != first["head_commit"]:
            raise ValueError("aggregate checkout differs from shard checkout")
        mapping, strategy, constraints = assignment(first["inventory"], args.shards, weights, fallback)
        executed, actual_cases, scheduled_cases = Counter(), Counter(), Counter()
        counts = Counter({key: 0 for key in COUNT_KEYS})
        for row in rows:
            expected_modules = [entry["module"] for entry in first["inventory"] if mapping[entry["module"]] == row["shard"]]
            if row["assigned_modules"] != expected_modules or row.get("strategy") != strategy or row.get("fixture_constraints") != constraints:
                raise ValueError("shard assignment differs from the deterministic plan")
            executed.update(row["executed_modules"])
            actual_cases.update(row["case_id_counts"])
            scheduled_cases.update(row["scheduled_case_id_counts"])
            counts.update(row["counts"])
        expected_cases = Counter()
        for entry in first["inventory"]:
            expected_cases.update(entry["case_id_counts"])
        if not sum(expected_cases.values()) or executed != Counter({entry["module"]: 1 for entry in first["inventory"]}) or scheduled_cases != expected_cases:
            raise ValueError("discovery/module-suite union proof failed")
        output.update(success=True, head_commit=head, weights_sha256=weights_sha,
            discovery_sha256=first["discovery_sha256"], executed_modules=sorted(executed),
            discovered_modules=len(first["inventory"]), counts=dict(counts),
            case_id_counts=dict(actual_cases), scheduled_case_id_counts=dict(scheduled_cases),
            strategy=strategy, fixture_constraints=constraints)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        output["errors"].append(str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
    args.reports.mkdir(parents=True, exist_ok=True)
    write_json(args.reports / "aggregate.json", output)
    text = "## Native unittest shards\n\n"
    text += f"Result: {'success' if output['success'] else 'failure'}; matrix: {args.job_result}.\n\n"
    if output["counts"] is not None:
        text += ("Complete" if output["counts_complete"] else "Partial available") + " native counts: "
        text += ", ".join(f"{key}={output['counts'][key]}" for key in COUNT_KEYS) + ".\n\n"
    else:
        text += "Native counts: UNKNOWN; no qualified count receipts.\n\n"
    for row in output["per_shard_counts"]:
        text += f"- Shard {row['shard']}: "
        text += (", ".join(f"{key}={row['counts'][key]}" for key in COUNT_KEYS) if row["counts"] is not None else "UNKNOWN") + ".\n"
    text += "\n"
    if output["unqualified_count_reports"]:
        text += f"Unqualified count reports: {len(output['unqualified_count_reports'])}.\n\n"
    if output["success"]:
        text += f"Executed/discovered module suites: {len(output['executed_modules'])}/{output['discovered_modules']}.\n\n"
    else:
        text += "Failure: " + "; ".join(output["errors"]) + ".\n"
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    with args.summary.open("a", encoding="utf-8") as handle:
        handle.write(text)
    print(json.dumps({"success": output["success"], "counts": output.get("counts"),
                      "modules": output.get("discovered_modules"), "errors": output["errors"]}, sort_keys=True))
    return 0 if output["success"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--shard", type=int, required=True)
    run.add_argument("--shards", type=int, required=True)
    run.add_argument("--report", type=Path, required=True)
    run.add_argument("--weights", type=Path, default=WEIGHTS)
    run.add_argument("-v", "--verbose", dest="verbosity", action="store_const", const=2, default=2)
    run.add_argument("--durations", type=int, default=50)
    final = sub.add_parser("aggregate")
    final.add_argument("--reports", type=Path, required=True)
    final.add_argument("--shards", type=int, required=True)
    final.add_argument("--job-result", required=True)
    final.add_argument("--summary", type=Path, required=True)
    final.add_argument("--weights", type=Path, default=WEIGHTS)
    args = parser.parse_args(argv)
    if args.shards <= 0 or (args.command == "run" and not 0 <= args.shard < args.shards):
        parser.error("invalid shard range")
    return run_shard(args) if args.command == "run" else aggregate(args)


if __name__ == "__main__":
    sys.exit(main())
