#!/usr/bin/env python3
"""Offline independent review; --root names the native-worker fixture directory."""

import argparse
import copy
import hashlib
import io
import itertools
import json
from pathlib import Path
import sys
import types
import unittest


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def load_module(path, name):
    module = types.ModuleType(name)
    exec(compile(path.read_text(), path.name, "exec"), module.__dict__)
    return module


def run(root):
    reviewed = (
        "seed/planner.py", "seed/test_planner.py", "seed/TASK.md",
        "accepted/planner.py", "prompt.txt", "plan.json", "usage.json",
    )
    before = {name: sha256(root / name) for name in reviewed}
    plan = json.loads((root / "plan.json").read_text())
    for name, expected_hash in plan["fixture_hashes"].items():
        require(name in {"planner.py", "test_planner.py", "TASK.md"},
                "unexpected seed filename in plan")
        require(sha256(root / "seed" / name) == expected_hash,
                "seed hash does not match plan")
    require(sha256(root / "prompt.txt") == plan["prompt_sha256"],
            "prompt hash does not match plan")

    accepted = load_module(root / "accepted/planner.py", "planner")
    implementation = accepted.order_tasks
    names = ("a", "b", "c", "d")
    edges = tuple(itertools.product(names, repeat=2))
    # Independent oracle: enumerate every candidate output permutation in
    # lexicographic order. A permutation permits only edges from earlier
    # prerequisites to later tasks, so no self-edge is permitted.
    orders = []
    for permutation in itertools.permutations(names):
        positions = {name: i for i, name in enumerate(permutation)}
        allowed = sum(1 << i for i, (task, prerequisite) in enumerate(edges)
                      if positions[prerequisite] < positions[task])
        orders.append((allowed, permutation))

    acyclic = cyclic = representations = 0
    for mask in range(1 << len(edges)):
        expected = next((list(order) for allowed, order in orders
                         if not mask & ~allowed), None)
        acyclic += expected is not None
        cyclic += expected is None
        original = {
            task: [prerequisite for i, (target, prerequisite) in enumerate(edges)
                   if target == task and mask & (1 << i)]
            for task in names
        }
        variants = (
            original,
            {key: list(reversed(value)) + value
             for key, value in reversed(list(original.items()))},
        )
        for dependencies in variants:
            snapshot = copy.deepcopy(dependencies)
            try:
                actual = implementation(dependencies)
            except ValueError:
                require(expected is None, "valid graph was rejected")
            else:
                require(actual == expected, "ordering differs from oracle")
            require(dependencies == snapshot, "input was mutated")
            representations += 1

    unknown_cases = 0
    for unknown in ("unknown", "", "\u03bb"):
        for dependencies in (
            {"a": [unknown]},
            {"a": [], "b": ["a", unknown, unknown]},
        ):
            snapshot = copy.deepcopy(dependencies)
            try:
                implementation(dependencies)
            except ValueError:
                pass
            else:
                raise AssertionError("undeclared prerequisite accepted")
            require(dependencies == snapshot, "invalid input was mutated")
            unknown_cases += 1

    sys.modules["planner"] = accepted
    frozen_tests = load_module(root / "seed/test_planner.py", "acceptance_oracle")

    def test_result(function):
        frozen_tests.order_tasks = function
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.defaultTestLoader.loadTestsFromModule(frozen_tests)
        )
        return {
            "tests": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "passed": result.wasSuccessful(),
        }

    accepted_tests = test_result(implementation)
    seed = load_module(root / "seed/planner.py", "seed")
    seed_tests = test_result(seed.order_tasks)
    require(accepted_tests == {"tests": 12, "failures": 0, "errors": 0,
                              "passed": True}, "accepted frozen tests failed")
    require(seed_tests == {"tests": 12, "failures": 8, "errors": 0,
                          "passed": False}, "seed negative control changed")

    usage = json.loads((root / "usage.json").read_text())
    terminal = usage["native_terminal_usage"]
    model = usage["native_model_usage"]["claude-opus-5"]
    accounting = {
        "terminal_category_sum": sum(terminal[key] for key in (
            "input_tokens", "cache_creation_input_tokens",
            "cache_read_input_tokens", "output_tokens")),
        "model_usage_category_sum": sum(model[key] for key in (
            "inputTokens", "cacheCreationInputTokens",
            "cacheReadInputTokens", "outputTokens")),
        "child_summary_total": usage["native_child_task_summary_usage"][0]["total_tokens"],
        "relationship": "Different native scopes remain unreconciled; do not add these totals.",
        "cost_basis": model["costBasis"],
        "native_retries": usage["native_retries"],
        "whole_desktop_task_usage": usage["whole_desktop_task_usage"],
        "savings_claim": usage["savings_claim"],
    }
    require(before == {name: sha256(root / name) for name in reviewed},
            "reviewed fixture bytes changed")
    return {
        "schema_version": 1,
        "kind": "offline_independent_planner_review",
        "outcome": "passed",
        "reviewer_script_sha256": sha256(Path(__file__)),
        "reviewed_files_sha256": before,
        "graph_oracle": "First valid permutation in independently enumerated lexicographic order.",
        "graph_nodes": list(names),
        "directed_graphs_including_self_edges": 1 << len(edges),
        "acyclic_graphs": acyclic,
        "cyclic_graphs": cyclic,
        "representations_checked": representations,
        "second_representation": "Reversed mapping/prerequisite order with duplicated prerequisites.",
        "undeclared_prerequisite_cases": unknown_cases,
        "input_immutability_checked_on_success_and_rejection": True,
        "accepted_frozen_tests": accepted_tests,
        "seed_negative_control": seed_tests,
        "plan_seed_and_prompt_hashes_match": True,
        "reviewed_bytes_unchanged": True,
        "usage_scope_review": accounting,
        "limitations": [
            "Exhaustive only for directed graphs over four named nodes; larger graphs are not exhaustively tested.",
            "Input contract is string task names mapped to lists of string prerequisites; malformed types are outside scope.",
            "Independent offline code/oracle review; no native model, account, remote host or provider call was repeated.",
            "Matching plan hashes verifies current bytes, not independently attested pre-execution chronology.",
            "Native worker/runtime claims rely on their separate execution evidence.",
            "No matched model baseline, whole-workflow token savings or billing reduction is established.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    print(json.dumps(run(args.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
