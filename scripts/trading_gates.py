#!/usr/bin/env python3
"""Check the sim → paper → live gate ladder arithmetically.

Reads catalogs/us-equities/gates-20260922.json and verifies, without any model
or reviewer opinion, that every gate recorded as ``established`` has its receipt
file in the tree and that the receipt satisfies the gate's flip condition. Gates
recorded in any other status are reported; when their receipt already satisfies
the flip condition they are listed as ``flip_candidates`` so a coordinator can
flip the status with a dated commit (the checker never flips anything itself).

Rung readiness is arithmetic: a rung is ready when every ``required`` gate of
that rung and of every earlier rung is ``established``. Exit status 1 on any
validation error or on an established gate whose evidence is missing or false.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

GATES = "catalogs/us-equities/gates-20260922.json"
STATUSES = {"established", "blocked", "not_established", "paid_entitlement", "user_decision"}
OWNERS = {"this-effort", "peer:sota-workflow-resolution", "user-decision"}
EVIDENCE = {"native_proven", "local_integration", "synthetic", "source_review", "none"}
CONDITIONS = {"exists", "equals", "array_contains_id"}
LAYERS = {
    "market-data-reference", "identity-provenance", "storage-compute", "data-quality-orchestration",
    "research-factors-ml", "backtesting-engine", "execution-broker", "portfolio-risk",
    "evaluation-experiments", "agents-models-workers", "observability-hosting",
    "security-supply-chain", "cross-layer",
}
GATE_FIELDS = {"id", "rung", "layer", "title", "status", "owner", "evidence_class", "required",
               "receipt_path", "flip_condition", "note"}


class GateError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def pointer(document, path: str):
    """RFC 6901 JSON pointer lookup; raises KeyError/IndexError when absent."""
    if path in ("", "/"):
        return document
    require(path.startswith("/"), f"pointer must start with '/': {path!r}")
    node = document
    for raw in path[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list):
            node = node[int(token)]
        elif isinstance(node, dict):
            node = node[token]
        else:
            raise KeyError(token)
    return node


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def condition_holds(root: Path, gate: dict) -> tuple[bool, str]:
    receipt = root / gate["receipt_path"]
    if not receipt.is_file():
        return False, "receipt missing"
    condition = gate["flip_condition"]
    if condition is None or condition["type"] == "exists":
        return True, "receipt present"
    try:
        document = load_json(receipt)
    except (OSError, ValueError) as error:
        return False, f"receipt unreadable: {error.__class__.__name__}"
    try:
        value = pointer(document, condition["pointer"])
    except (KeyError, IndexError, ValueError):
        return False, f"pointer absent: {condition['pointer']}"
    if condition["type"] == "equals":
        return (value == condition["equals"]), f"{condition['pointer']} == {json.dumps(value)[:80]}"
    if condition["type"] == "array_contains_id":
        ids = {item.get("id") for item in value if isinstance(item, dict)} if isinstance(value, list) else set()
        return (condition["id"] in ids), f"{condition['pointer']} contains id {condition['id']!r}: {condition['id'] in ids}"
    return False, "unknown condition"


def validate_document(document: dict) -> list[dict]:
    require(isinstance(document, dict), "gates document must be an object")
    require(document.get("schema_version") == 1, "schema_version must be 1")
    rungs = document.get("rungs")
    require(isinstance(rungs, list) and rungs == ["sim", "paper", "live"], "rungs must be ['sim', 'paper', 'live']")
    gates = document.get("gates")
    require(isinstance(gates, list) and gates, "gates must be a non-empty list")
    seen: set[str] = set()
    for position, gate in enumerate(gates):
        label = f"gates[{position}]"
        require(isinstance(gate, dict), f"{label} must be an object")
        require(set(gate) == GATE_FIELDS, f"{label} fields must be exactly {sorted(GATE_FIELDS)}; got {sorted(gate)}")
        require(isinstance(gate["id"], str) and gate["id"] and gate["id"] not in seen, f"{label} id must be a unique string")
        seen.add(gate["id"])
        require(gate["rung"] in rungs, f"{gate['id']}: rung must be one of {rungs}")
        require(gate["layer"] in LAYERS, f"{gate['id']}: unknown layer {gate['layer']!r}")
        require(gate["status"] in STATUSES, f"{gate['id']}: unknown status {gate['status']!r}")
        require(gate["owner"] in OWNERS, f"{gate['id']}: unknown owner {gate['owner']!r}")
        require(gate["evidence_class"] in EVIDENCE, f"{gate['id']}: unknown evidence_class {gate['evidence_class']!r}")
        require(isinstance(gate["required"], bool), f"{gate['id']}: required must be boolean")
        require(isinstance(gate["title"], str) and gate["title"], f"{gate['id']}: title required")
        require(isinstance(gate["note"], str), f"{gate['id']}: note must be a string")
        path = gate["receipt_path"]
        require(isinstance(path, str) and path and not path.startswith("/") and ".." not in Path(path).parts,
                f"{gate['id']}: receipt_path must be a relative in-tree path")
        condition = gate["flip_condition"]
        if condition is not None:
            require(isinstance(condition, dict) and condition.get("type") in CONDITIONS,
                    f"{gate['id']}: flip_condition.type must be one of {sorted(CONDITIONS)}")
            if condition["type"] == "equals":
                require(set(condition) == {"type", "pointer", "equals"}, f"{gate['id']}: equals condition needs pointer and equals")
            elif condition["type"] == "array_contains_id":
                require(set(condition) == {"type", "pointer", "id"}, f"{gate['id']}: array_contains_id condition needs pointer and id")
            else:
                require(set(condition) == {"type"}, f"{gate['id']}: exists condition takes no other fields")
        if gate["status"] == "established":
            require(gate["evidence_class"] != "none", f"{gate['id']}: an established gate needs an evidence class")
    return gates


def check(root: Path, path: Path) -> dict:
    document = load_json(path)
    gates = validate_document(document)
    errors: list[str] = []
    flip_candidates: list[dict] = []
    rows: list[dict] = []
    for gate in gates:
        holds, detail = condition_holds(root, gate)
        row = {"id": gate["id"], "rung": gate["rung"], "status": gate["status"], "required": gate["required"],
               "owner": gate["owner"], "evidence_class": gate["evidence_class"], "receipt_path": gate["receipt_path"],
               "condition_holds": holds, "detail": detail}
        rows.append(row)
        if gate["status"] == "established" and not holds:
            errors.append(f"{gate['id']}: recorded established but {detail}")
        if gate["status"] != "established" and holds and gate["flip_condition"] is not None:
            flip_candidates.append({"id": gate["id"], "status": gate["status"], "detail": detail})
    ready: dict[str, bool] = {}
    blocking: dict[str, list[str]] = {}
    rungs = document["rungs"]
    for index, rung in enumerate(rungs):
        scope = set(rungs[: index + 1])
        pending = [g["id"] for g in gates if g["required"] and g["rung"] in scope and g["status"] != "established"]
        ready[rung] = not pending
        blocking[rung] = pending
    counts: dict[str, dict[str, int]] = {}
    for gate in gates:
        counts.setdefault(gate["rung"], {})
        counts[gate["rung"]][gate["status"]] = counts[gate["rung"]].get(gate["status"], 0) + 1
    return {
        "status": "passed" if not errors else "failed",
        "gates": len(gates),
        "counts": counts,
        "rung_ready": ready,
        "blocking": blocking,
        "flip_candidates": flip_candidates,
        "errors": errors,
        "rows": rows,
        "scope": "Arithmetic over recorded receipts; no reviewer or model opinion; nothing is flipped by this checker.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--path", default=GATES, help="gates document, relative to --root")
    parser.add_argument("--check", action="store_true", help="(default) validate and check receipts")
    parser.add_argument("--json", action="store_true", help="print the full result including rows")
    args = parser.parse_args(argv)
    try:
        result = check(args.root, args.root / args.path)
    except (GateError, OSError, ValueError) as error:
        print(json.dumps({"status": "failed", "errors": [str(error)]}, indent=2))
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps({key: result[key] for key in ("status", "gates", "counts", "rung_ready", "blocking", "flip_candidates", "errors")}, indent=2, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
