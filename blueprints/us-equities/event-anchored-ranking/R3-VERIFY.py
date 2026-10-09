#!/usr/bin/env python3
"""R3-VERIFY structural glue; not an upstream or scientific acceptance test.

Sources: CPython v3.12.3 Lib/json/__init__.py (load) and Lib/hashlib.py
(file_digest), and native uutils-coreutils 0.10.0 sha256sum --check format.
R3-F2: CPython v3.13.16 json.JSONDecodeError, pathlib/OSError and re.fullmatch;
mandatory schema from this packet at native-agent-stack@36e36ea4.
Gap: native carrier integrity does not compare JSON's embedded normative
path/hash references with that carrier. This verifier adds only that join.
It reads declared current candidate members, never external credentials,
raw study outcome stores, archived ledgers or provider/runtime state.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

HEX = re.compile(r"[0-9a-f]{64}\Z")
CONTRACTS = {
    "construction": "R2-CONSTRUCTION.json",
    "comparison": "R2-COMPARISON.json",
    "logit_operators": "R2-LOGIT-OPERATORS.json",
    "inspection": "R2-INSPECTION.json",
    "survivorship": "R2-SURVIVORSHIP.json",
}
MANDATORY_OBJECTS = {
    "protocol.draft.json": {
        **{("R2_bound_contracts", role): name for role, name in CONTRACTS.items()},
        ("freeze_prerequisites", "inspection_registry"): "inspection-registry.draft.json",
    },
    "inspection-registry.draft.json": {("exclusion_contract",): "R2-INSPECTION.json"},
    "ROW14-SUBMISSION-R3.json": {
        ("protocol",): "protocol.draft.json",
        ("registry",): "inspection-registry.draft.json",
        ("unchanged_logit_operators",): "R2-LOGIT-OPERATORS.json",
        ("runtime_acceptance",): "R3-RUNTIME-ACCEPTANCE.json",
        ("runtime_lock_verification",): "R3-RUNTIME-LOCK-VERIFICATION.json",
        ("R3B_corrections", "verifier"): "R3-VERIFY.py",
    },
}
ROW_CONTRACTS = tuple(name for role, name in CONTRACTS.items() if role != "logit_operators")
# These two declared unaccepted PIT-04 inputs have both path and digest null in
# the published contract; they are placeholders, not satisfied binding claims.
UNFILLED_INPUTS = {
    ("R2-SURVIVORSHIP.json", "/native_PIT04_exclusions/accepted_layer15_receipt"),
    ("R2-SURVIVORSHIP.json", "/native_PIT04_exclusions/accepted_layer15_manifest"),
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(root):
    errors, bindings, boundaries = [], [], []
    manifest, semantic = {}, {}
    manifest_hash = None

    def result():
        return {"status": "PASS" if not errors else "FAIL", "carrier_entries": len(manifest),
                "manifest_sha256": manifest_hash, "internal_bindings": bindings,
                "internal_binding_count": len(bindings),
                "binding_count_scope": "Distinct source file and digest JSON-pointer locations; repeated checks of one location count once.",
                "semantic_checks": semantic, "external_or_historical_boundaries": boundaries,
                "errors": errors,
                "scope": "Structural carrier/internal-reference/status checks only; no source truth, reviewer PASS, native strategy or data/execution acceptance."}

    def read_bytes(name):
        path = root / name
        if path.is_symlink():
            errors.append(f"file is a symlink: {name}")
            return None
        if not path.is_file():
            errors.append(f"missing or not a regular file: {name}")
            return None
        try:
            return path.read_bytes()
        except OSError as error:
            errors.append(f"cannot read file: {name}: {error.strerror}")
            return None

    carrier_bytes = read_bytes("SHA256SUMS")
    for carrier in ("SHA256SUMS.R3", "SHA256SUMS.R3B"):
        alternate = read_bytes(carrier)
        if alternate is not None and carrier_bytes is not None and alternate != carrier_bytes:
            errors.append(f"carrier differs: {carrier}")
    if carrier_bytes is None:
        return result()
    manifest_hash = hashlib.sha256(carrier_bytes).hexdigest()
    try:
        carrier_text = carrier_bytes.decode("utf-8")
    except UnicodeDecodeError:
        errors.append("invalid UTF-8: SHA256SUMS")
        return result()

    contents = {}
    for number, line in enumerate(carrier_text.splitlines(), 1):
        if not line or len(line) < 67 or line[64:66] != "  ":
            errors.append(f"manifest line {number}: invalid native text format")
            continue
        declared, name = line[:64], line[66:]
        relative = Path(name)
        if not HEX.fullmatch(declared) or not name or relative == Path(".") or relative.is_absolute() or ".." in relative.parts or name in manifest:
            errors.append(f"manifest line {number}: invalid or duplicate entry")
            continue
        manifest[name] = declared
        raw = read_bytes(name)
        if raw is None:
            continue
        contents[name] = raw
        if hashlib.sha256(raw).hexdigest() != declared:
            errors.append(f"carrier mismatch: {name}")

    seen = set()
    def binding(file, pointer, reference, declared, mandatory_target=None):
        location = (file, pointer)
        if location in seen:
            return
        seen.add(location)
        if not isinstance(declared, str) or not HEX.fullmatch(declared):
            errors.append(f"invalid digest: {file}{pointer}; expected 64 lowercase hex")
            return
        if not isinstance(reference, str) or not reference:
            errors.append(f"invalid binding target: {file}{pointer}")
            return
        if mandatory_target is not None and (reference != mandatory_target or reference not in contents):
            errors.append(f"mandatory target missing or invalid: {file}{pointer} -> {mandatory_target}")
            return
        if reference in manifest:
            equal = manifest[reference] == declared
            bindings.append({"file": file, "pointer": pointer, "target": reference, "matches_manifest": equal})
            if not equal:
                errors.append(f"internal binding mismatch: {file}{pointer} -> {reference}")
        elif not Path(reference).is_absolute() and not reference.startswith("attempt-") and (root / reference).is_file():
            errors.append(f"current local binding absent from carrier: {file}{pointer} -> {reference}")
        else:
            boundaries.append({"file": file, "pointer": pointer, "reference": reference,
                               "scope": "external, historical or separately pinned source; not read by this verifier"})

    def walk(file, obj, pointer=""):
        if isinstance(obj, dict):
            if "sha256" in obj:
                for key in ("path", "artifact", "pdf", "receipt"):
                    if key in obj:
                        if (file, pointer) in UNFILLED_INPUTS and obj[key] is None and obj["sha256"] is None:
                            break
                        binding(file, pointer + "/sha256", obj[key], obj["sha256"])
                        break
                else:
                    # A standalone metadata digest is not a path/digest join.
                    if not isinstance(obj["sha256"], str) or not HEX.fullmatch(obj["sha256"]):
                        errors.append(f"invalid digest: {file}{pointer}/sha256; expected 64 lowercase hex")
            if "pdf" in obj and "pdf_sha256" in obj:
                binding(file, pointer + "/pdf_sha256", obj["pdf"], obj["pdf_sha256"])
            if "earlier_checkpoint" in obj or "earlier_sha256" in obj:
                binding(file, pointer + "/earlier_sha256", obj.get("earlier_checkpoint"), obj.get("earlier_sha256"))
            for key, value in obj.items():
                if key in manifest:
                    binding(file, pointer + "/" + key, key, value)
                elif isinstance(value, (dict, list)):
                    walk(file, value, pointer + "/" + key)
        elif isinstance(obj, list):
            for index, value in enumerate(obj):
                walk(file, value, pointer + "/" + str(index))

    documents = {}
    for name in manifest:
        if name.endswith(".json") and name in contents:
            try:
                document = json.loads(contents[name].decode("utf-8"))
            except UnicodeDecodeError:
                errors.append(f"invalid UTF-8: {name}")
                continue
            except json.JSONDecodeError as error:
                errors.append(f"invalid JSON: {name}: {error.msg} at line {error.lineno}, column {error.colno}")
                continue
            if not isinstance(document, dict):
                errors.append(f"expected JSON object: {name}")
                continue
            documents[name] = document

    def at(file, keys):
        value = documents[file]
        for key in keys:
            value = value[key]
        return value

    # These are current-packet normative edges, not optional external evidence.
    # Use the same digest-leaf pointer as walk() so repeated checks are counted once.
    for file, joins in MANDATORY_OBJECTS.items():
        for keys, target in joins.items():
            pointer = "/" + "/".join(keys)
            try:
                row = at(file, keys)
                if not isinstance(row, dict):
                    raise TypeError
            except (KeyError, TypeError):
                errors.append(f"mandatory join missing or invalid: {file}{pointer}")
                continue
            binding(file, pointer + "/sha256", row.get("path"), row.get("sha256"), target)
    for name in ROW_CONTRACTS:
        pointer = "/contracts/" + name
        try:
            declared = at("ROW14-SUBMISSION-R3.json", ("contracts", name))
        except (KeyError, TypeError):
            errors.append(f"mandatory join missing or invalid: ROW14-SUBMISSION-R3.json{pointer}")
            continue
        binding("ROW14-SUBMISSION-R3.json", pointer, name, declared, name)
    # Extra entries in these mandatory containers cannot evade the schema by
    # falling through to optional external evidence or an unrecognised map key.
    for file, keys, allowed in (
        ("protocol.draft.json", ("R2_bound_contracts",), set(CONTRACTS) | {"rule"}),
        ("ROW14-SUBMISSION-R3.json", ("contracts",), set(ROW_CONTRACTS)),
    ):
        try:
            rows = at(file, keys)
            if not isinstance(rows, dict):
                raise TypeError
        except (KeyError, TypeError):
            errors.append(f"mandatory contract container missing or invalid: {file}/{'/'.join(keys)}")
            continue
        for key in sorted(rows.keys() - allowed):
            errors.append(f"unexpected mandatory contract: {file}/{'/'.join(keys)}/{key}")
    for file, document in documents.items():
        walk(file, document)

    required_documents = set(MANDATORY_OBJECTS) | {
        target for joins in MANDATORY_OBJECTS.values() for target in joins.values() if target.endswith(".json")
    }
    for name in sorted(required_documents - documents.keys()):
        errors.append(f"required JSON document unavailable: {name}")
    if not required_documents.issubset(documents):
        return result()
    protocol = documents["protocol.draft.json"]
    registry = documents["inspection-registry.draft.json"]
    submission = documents["ROW14-SUBMISSION-R3.json"]

    checks = {
        "conservative_disposition_applied": lambda: "APPLIED" in registry["status"],
        "identity_gap_separate": lambda: "unproven" in registry["status"],
        "no_stale_provisional_policy": lambda: "provisional_policy" not in registry["CC_completeness_disposition"],
        "runtime_install_flags_agree": lambda: documents["R2-SURVIVORSHIP.json"]["current_candidate"]["runtime_install_performed"] == submission["runtime_install_performed"],
        "original_install_receipt_scope": lambda: "current_runtime_lock_sha256" not in documents["R3-RUNTIME-ACCEPTANCE.json"]["install"],
        "current_runtime_binding_agrees": lambda: protocol["models"]["main"]["runtime_state"]["runtime_lock_sha256"] == submission["runtime_lock_sha256"] == documents["R3-RUNTIME-LOCK-VERIFICATION.json"]["runtime_lock_sha256"],
        "single_entry_rule_agrees": lambda: documents["R2-CONSTRUCTION.json"]["clocks"]["entry"] == documents["R2-COMPARISON.json"]["portfolio"].get("entry_fill_rule"),
        "study_fit_still_false": lambda: submission["model_fit_run"] is False,
        "accepted_PIT04_still_null": lambda: submission["accepted_layer15_receipt"] is None and submission["native_PIT04_exclusion_count"] is None,
    }
    for name, check in checks.items():
        try:
            passed = bool(check())
        except (KeyError, TypeError, AttributeError):
            errors.append("semantic input missing or invalid: " + name)
            passed = False
        semantic[name] = passed
        if not passed:
            errors.append("semantic mismatch: " + name)
    return result()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result = verify(args.root.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
