#!/usr/bin/env python3
"""Check the sim → paper → live gate ladder arithmetically.

Reads catalogs/us-equities/gates-20260922.json and verifies, without any model
or reviewer opinion, that every gate recorded as ``established`` has its receipt
file in the tree and that the receipt satisfies the gate's flip condition. Gates
recorded in any other status are reported; when their receipt already satisfies
the flip condition they are listed as ``flip_candidates`` so a coordinator can
flip the status with a dated commit (the checker never flips anything itself).

Condition types: ``exists`` (non-empty file), ``equals`` (type-strict JSON value
at a pointer), ``array_contains_id``, ``greater_than`` (the value at a pointer is
a JSON number or a decimal string strictly greater than ``than``),
``source_matches`` (the receipt names an in-tree source file by path and
sha256 at ``path_pointer``/``sha256_pointer``; the file's bytes must hash to
that value and, for each ``[receipt_pointer, source_pointer]`` in ``pairs``, the
receipt value must equal the source value exactly -- same JSON types, same
contents) and ``all_of`` (every listed
``equals``/``array_contains_id``/``greater_than``/``source_matches``
sub-condition holds against the same receipt; no nesting and no ``exists``).

Rung readiness is arithmetic: a rung is ready when every ``required`` gate of
that rung and of every earlier rung is ``established``. Exit status 1 on any
validation error or on an established gate whose evidence is missing or false.

Source bindings are report-only. For a gate named in ``SOURCE_BINDINGS``, the
sha256 values its receipt records for the source files it ran are compared with
those files in the tree and, where the release manifest lists a file, with that
manifest. Each difference is listed under ``warnings``, with per-gate counts
under ``source_bindings``. A warning never changes a status, rung readiness,
``errors`` or the exit code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

GATES = "catalogs/us-equities/gates-20260922.json"
STATUSES = {"established", "blocked", "not_established", "paid_entitlement", "user_decision"}
OWNERS = {"this-effort", "peer:sota-workflow-resolution", "user-decision"}
EVIDENCE = {"native_proven", "local_integration", "synthetic", "source_review", "none"}
CONDITIONS = {"exists", "equals", "array_contains_id", "greater_than", "source_matches", "all_of"}
# Sub-conditions an all_of may list: conditions judged against one parsed receipt.
COMPOUND_MEMBERS = {"equals", "array_contains_id", "greater_than", "source_matches"}
SHA256_HEX = re.compile(r"[0-9a-f]{64}")
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


def decimal_value(value) -> Decimal | None:
    """A finite Decimal from a JSON number (not a boolean) or a decimal string;
    None for anything else. The adaptive-paper runner records Decimal values as
    strings (``str(Decimal)``) and durations as JSON numbers, so both forms are
    compared exactly rather than through float."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        result = Decimal(value.strip()) if isinstance(value, str) else Decimal(str(value))
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def in_tree_path(value) -> bool:
    """A relative, forward-slash, in-tree path (no absolute path, no '..', no backslash)."""
    return (isinstance(value, str) and bool(value) and not value.startswith("/") and "\\" not in value
            and ".." not in Path(value).parts)


def canonical(value) -> str:
    """Type-strict JSON identity: 1, 1.0, true and "1" all differ."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def source_matches_holds(root: Path, document, condition: dict) -> tuple[bool, str]:
    """The receipt's named source file exists in the tree, hashes to the
    recorded sha256, and agrees with the receipt at every listed pointer pair."""
    try:
        source_path = pointer(document, condition["path_pointer"])
        recorded_sha = pointer(document, condition["sha256_pointer"])
    except (KeyError, IndexError, ValueError):
        return False, "source_matches: source path or sha256 pointer absent"
    if not in_tree_path(source_path):
        return False, f"source_matches: {condition['path_pointer']} is not a relative in-tree path"
    if not (isinstance(recorded_sha, str) and SHA256_HEX.fullmatch(recorded_sha)):
        return False, f"source_matches: {condition['sha256_pointer']} is not a lowercase sha256 hex digest"
    try:
        resolved = (root / source_path).resolve()
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return False, f"source_matches: {source_path} resolves outside the tree"
    if not resolved.is_file():
        return False, f"source_matches: source file missing: {source_path}"
    data = resolved.read_bytes()
    actual_sha = hashlib.sha256(data).hexdigest()
    if actual_sha != recorded_sha:
        return False, f"source_matches: {source_path} sha256 {actual_sha[:12]} != recorded {recorded_sha[:12]}"
    try:
        source_document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        return False, f"source_matches: source unreadable: {error.__class__.__name__}"
    mismatched = []
    for receipt_pointer, source_pointer in condition["pairs"]:
        try:
            left = pointer(document, receipt_pointer)
            right = pointer(source_document, source_pointer)
        except (KeyError, IndexError, ValueError):
            mismatched.append(f"{receipt_pointer} vs source {source_pointer} (absent)")
            continue
        if canonical(left) != canonical(right):
            mismatched.append(f"{receipt_pointer} != source {source_pointer}")
    if mismatched:
        return False, f"source_matches: {source_path}: " + ", ".join(mismatched)
    return True, f"source_matches: {source_path} sha256 {actual_sha[:12]} and {len(condition['pairs'])} pair(s) agree"


def pointer_condition_holds(root: Path, document, condition: dict) -> tuple[bool, str]:
    """Judge one equals/array_contains_id/greater_than/source_matches condition against a parsed receipt."""
    if condition["type"] == "source_matches":
        return source_matches_holds(root, document, condition)
    try:
        value = pointer(document, condition["pointer"])
    except (KeyError, IndexError, ValueError):
        return False, f"pointer absent: {condition['pointer']}"
    if condition["type"] == "equals":
        expected = condition["equals"]
        # Python's == treats bool as a subtype of int (False == 0, True == 1);
        # a type-strict match keeps a receipt value of false/0.0 from
        # satisfying a condition that names an integer or string literal.
        matches = type(value) is type(expected) and value == expected
        return matches, f"{condition['pointer']} == {json.dumps(value)[:80]}"
    if condition["type"] == "array_contains_id":
        ids = {item.get("id") for item in value if isinstance(item, dict)} if isinstance(value, list) else set()
        return (condition["id"] in ids), f"{condition['pointer']} contains id {condition['id']!r}: {condition['id'] in ids}"
    if condition["type"] == "greater_than":
        actual, bound = decimal_value(value), decimal_value(condition["than"])
        if actual is None or bound is None:
            return False, f"{condition['pointer']} not a finite number: {json.dumps(value)[:80]}"
        return actual > bound, f"{condition['pointer']} = {json.dumps(value)[:80]} > {json.dumps(condition['than'])}: {actual > bound}"
    return False, "unknown condition"


def condition_holds(root: Path, gate: dict) -> tuple[bool, str]:
    receipt = root / gate["receipt_path"]
    if not receipt.is_file():
        return False, "receipt missing"
    condition = gate["flip_condition"]
    if condition is None or condition["type"] == "exists":
        if receipt.stat().st_size == 0:
            return False, "receipt present but empty"
        return True, "receipt present (non-empty; content not judged)"
    try:
        document = load_json(receipt)
    except (OSError, ValueError) as error:
        return False, f"receipt unreadable: {error.__class__.__name__}"
    if condition["type"] == "all_of":
        results = [pointer_condition_holds(root, document, member) for member in condition["conditions"]]
        failed = [detail for holds, detail in results if not holds]
        if failed:
            return False, f"all_of: {len(failed)} of {len(results)} failed: " + "; ".join(failed)
        return True, f"all_of: {len(results)} of {len(results)} hold: " + "; ".join(detail for _, detail in results)
    return pointer_condition_holds(root, document, condition)


# Receipts that bind the source files they ran with, keyed by gate id; paths are
# repository-relative. "maps" names a receipt object of {path relative to the
# given directory: sha256}, "files" a receipt sha256 for one named file, and
# "manifest" the release manifest ({repository path: sha256}) that lists some of
# them. Report-only, added 2026-09-25 after the PR #278 review: the
# native-fault-behaviour flip condition checks only /status, so without this a
# later engine change leaves the established gate bound to older files while
# --check keeps passing.
SOURCE_BINDINGS = {
    "native-fault-behaviour": {
        "manifest": "blueprints/us-equities/adaptive-paper/source-hashes.json",
        # native-faults/harness.py writes these keys relative to its ENGINE directory.
        "maps": {"/engine_sources_sha256": "blueprints/us-equities/adaptive-paper"},
        "files": {"/harness_sha256": "blueprints/us-equities/adaptive-paper/native-faults/harness.py",
                  "/plan_sha256": "blueprints/us-equities/adaptive-paper/native-faults/plan.json"},
    },
}


def bound_path(base: str, key) -> str | None:
    """The repository path a binding key names relative to ``base``, or None
    when the key is not a relative forward-slash path that stays in the tree."""
    if not isinstance(key, str) or not key or key.startswith("/") or "\\" in key:
        return None
    parts: list[str] = []
    for part in f"{base}/{key}".split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    path = "/".join(parts)
    return path if in_tree_path(path) else None


def source_binding(root: Path, gate: dict, spec: dict) -> tuple[dict, list[dict]]:
    """Compare the sha256 values a gate's receipt binds with the tree and the
    release manifest. Returns (counts, warnings), and nothing it finds changes
    the gate's status, rung readiness, errors or the exit code. A missing,
    unreadable, malformed, too deeply nested or symlink-looping file becomes a
    warning, not an exception: the reads below catch OSError, ValueError and
    RuntimeError (Python 3.12 and earlier raise RuntimeError from
    Path.resolve() on a symlink loop; RecursionError, raised by json on deep
    nesting, is a RuntimeError)."""
    warnings: list[dict] = []

    def warn(path, detail, recorded=None, tree=None, listed=None):
        warnings.append({"id": gate["id"], "path": path, "receipt_sha256": recorded, "tree_sha256": tree,
                         "manifest_sha256": listed, "detail": detail})

    try:
        receipt = load_json(root / gate["receipt_path"])
    except (OSError, RuntimeError, ValueError) as error:
        warn(gate["receipt_path"], f"receipt unreadable ({error.__class__.__name__}); source binding not checked")
        return {"bound": 0, "stale": 0, "checked": False}, warnings
    manifest: dict = {}
    try:
        loaded = load_json(root / spec["manifest"])
        if isinstance(loaded, dict):
            manifest = loaded
        else:
            warn(spec["manifest"], "release manifest is not an object; bindings compared with the tree only")
    except (OSError, RuntimeError, ValueError) as error:
        warn(spec["manifest"], f"release manifest unreadable ({error.__class__.__name__}); "
                               "bindings compared with the tree only")
    bound: list[tuple[str, str | None, object]] = []
    for map_pointer, base in spec["maps"].items():
        try:
            mapping = pointer(receipt, map_pointer)
        except (KeyError, IndexError, TypeError, ValueError, GateError):
            mapping = None
        if not isinstance(mapping, dict) or not mapping:
            warn(map_pointer, f"receipt has no non-empty {map_pointer} object; its bindings are not checked")
            continue
        bound.extend((f"{map_pointer}: {key}", bound_path(base, key), recorded) for key, recorded in mapping.items())
    for file_pointer, path in spec["files"].items():
        try:
            recorded = pointer(receipt, file_pointer)
        except (KeyError, IndexError, TypeError, ValueError, GateError):
            recorded = None
        bound.append((file_pointer, path, recorded))
    stale = 0
    for label, path, recorded in bound:
        if path is None:
            stale += 1
            warn(label, "binding key is not a relative in-tree path; nothing was read", recorded)
            continue
        if not (isinstance(recorded, str) and SHA256_HEX.fullmatch(recorded)):
            stale += 1
            warn(path, f"receipt value at {label} is absent or not a lowercase sha256 hex digest", recorded)
            continue
        try:
            resolved = (root / path).resolve()
            resolved.relative_to(root.resolve())
        except RuntimeError:
            # Python 3.12 and earlier: a symlink loop. Python 3.13 resolves it without
            # raising, and is_file() below is then False, so it is reported as missing.
            stale += 1
            warn(path, "bound path is a symlink loop; nothing was read", recorded)
            continue
        except (OSError, ValueError):
            stale += 1
            warn(path, "bound path resolves outside the tree; nothing was read", recorded)
            continue
        try:
            actual = hashlib.sha256(resolved.read_bytes()).hexdigest() if resolved.is_file() else None
        except OSError:
            actual = None
        listed = manifest.get(path)
        listed = listed if isinstance(listed, str) else None
        if actual == recorded and listed in (None, recorded):
            continue
        stale += 1
        found = "the file is missing" if actual is None else (
            "the tree still has those bytes" if actual == recorded else f"the tree has {actual[:12]}")
        if listed is not None:
            found += f", and {spec['manifest'].rsplit('/', 1)[-1]} lists {listed[:12]}"
        warn(path, f"receipt binds {recorded[:12]}, but {found}; the receipt qualifies the recorded bytes "
                   "until a re-run rebinds it", recorded, actual, listed)
    return {"bound": len(bound), "stale": stale, "checked": True}, warnings


def validate_pointer_condition(gate_id: str, condition, allowed: set[str]) -> None:
    require(isinstance(condition, dict) and condition.get("type") in allowed,
            f"{gate_id}: flip_condition.type must be one of {sorted(allowed)}")
    kind = condition["type"]
    if kind == "equals":
        require(set(condition) == {"type", "pointer", "equals"}, f"{gate_id}: equals condition needs pointer and equals")
    elif kind == "array_contains_id":
        require(set(condition) == {"type", "pointer", "id"}, f"{gate_id}: array_contains_id condition needs pointer and id")
    elif kind == "greater_than":
        require(set(condition) == {"type", "pointer", "than"}, f"{gate_id}: greater_than condition needs pointer and than")
        require(decimal_value(condition["than"]) is not None,
                f"{gate_id}: greater_than.than must be a finite JSON number or decimal string")
    elif kind == "source_matches":
        require(set(condition) == {"type", "path_pointer", "sha256_pointer", "pairs"},
                f"{gate_id}: source_matches condition needs path_pointer, sha256_pointer and pairs")
        pairs = condition["pairs"]
        require(isinstance(pairs, list) and bool(pairs) and all(
            isinstance(pair, list) and len(pair) == 2 and all(isinstance(p, str) and p.startswith("/") for p in pair)
            for pair in pairs), f"{gate_id}: source_matches.pairs must be a non-empty list of [receipt, source] JSON pointers")
        for key in ("path_pointer", "sha256_pointer"):
            require(isinstance(condition[key], str) and condition[key].startswith("/"),
                    f"{gate_id}: source_matches.{key} must be a JSON pointer starting with '/'")
        return
    else:
        require(set(condition) == {"type"}, f"{gate_id}: exists condition takes no other fields")
    if kind != "exists":
        require(isinstance(condition["pointer"], str) and condition["pointer"].startswith("/"),
                f"{gate_id}: condition pointer must be a JSON pointer starting with '/'")


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
            if condition["type"] == "all_of":
                members = condition.get("conditions")
                require(set(condition) == {"type", "conditions"} and isinstance(members, list) and members,
                        f"{gate['id']}: all_of condition needs a non-empty conditions list")
                for member in members:
                    validate_pointer_condition(gate["id"], member, COMPOUND_MEMBERS)
            else:
                validate_pointer_condition(gate["id"], condition, CONDITIONS - {"all_of"})
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
    # Report-only (module docstring): computed after status, readiness and errors, and never feeds them.
    warnings: list[dict] = []
    source_bindings: dict[str, dict] = {}
    for gate in gates:
        if gate["id"] in SOURCE_BINDINGS:
            source_bindings[gate["id"]], found = source_binding(root, gate, SOURCE_BINDINGS[gate["id"]])
            warnings.extend(found)
    return {
        "status": "passed" if not errors else "failed",
        "gates": len(gates),
        "counts": counts,
        "rung_ready": ready,
        "blocking": blocking,
        "flip_candidates": flip_candidates,
        "errors": errors,
        "warnings": warnings,
        "source_bindings": source_bindings,
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
        print(json.dumps({key: result[key] for key in ("status", "gates", "counts", "rung_ready", "blocking", "flip_candidates", "errors", "warnings", "source_bindings")}, indent=2, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
