#!/usr/bin/env python3
"""R3-VERIFY structural glue; not an upstream or scientific acceptance test.

Sources: CPython v3.12.3 Lib/json/__init__.py (load) and Lib/hashlib.py
(file_digest), and native uutils-coreutils 0.10.0 sha256sum --check format.
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


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(root):
    errors, bindings, boundaries = [], [], []
    manifest = {}
    for number, line in enumerate((root / "SHA256SUMS").read_text().splitlines(), 1):
        if not line or len(line) < 67 or line[64:66] != "  ":
            errors.append(f"manifest line {number}: invalid native text format")
            continue
        declared, name = line[:64], line[66:]
        relative = Path(name)
        if not HEX.fullmatch(declared) or relative.is_absolute() or ".." in relative.parts or name in manifest:
            errors.append(f"manifest line {number}: invalid or duplicate entry")
            continue
        manifest[name] = declared
        path = root / relative
        if not path.is_file() or path.is_symlink() or digest(path) != declared:
            errors.append(f"carrier mismatch: {name}")
    for carrier in ("SHA256SUMS.R3", "SHA256SUMS.R3B"):
        if (root / carrier).exists() and (root / carrier).read_bytes() != (root / "SHA256SUMS").read_bytes():
            errors.append(f"carrier differs: {carrier}")

    def binding(file, pointer, reference, declared):
        if not isinstance(reference, str) or not isinstance(declared, str) or not HEX.fullmatch(declared):
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
            if isinstance(obj.get("sha256"), str):
                for key in ("path", "artifact", "pdf", "receipt"):
                    if isinstance(obj.get(key), str):
                        binding(file, pointer + "/sha256", obj[key], obj["sha256"])
                        break
            if isinstance(obj.get("pdf"), str) and "pdf_sha256" in obj:
                binding(file, pointer + "/pdf_sha256", obj["pdf"], obj["pdf_sha256"])
            for key, value in obj.items():
                if key in manifest and isinstance(value, str) and HEX.fullmatch(value):
                    binding(file, pointer + "/" + key, key, value)
                elif isinstance(value, (dict, list)):
                    walk(file, value, pointer + "/" + key)
        elif isinstance(obj, list):
            for index, value in enumerate(obj):
                walk(file, value, pointer + "/" + str(index))

    documents = {}
    for name in manifest:
        if name.endswith(".json"):
            with (root / name).open() as stream:
                documents[name] = json.load(stream)
            walk(name, documents[name])
    protocol = documents["protocol.draft.json"]
    registry = documents["inspection-registry.draft.json"]
    submission = documents["ROW14-SUBMISSION-R3.json"]
    for name, row in protocol["R2_bound_contracts"].items():
        if name != "rule":
            binding("protocol.draft.json", "/R2_bound_contracts/" + name, row["path"], row["sha256"])
    binding("protocol.draft.json", "/freeze_prerequisites/inspection_registry",
            "inspection-registry.draft.json", protocol["freeze_prerequisites"]["inspection_registry"]["sha256"])
    for name, declared in submission["contracts"].items():
        binding("ROW14-SUBMISSION-R3.json", "/contracts/" + name, name, declared)

    semantic = {
        "conservative_disposition_applied": "APPLIED" in registry["status"],
        "identity_gap_separate": "unproven" in registry["status"],
        "no_stale_provisional_policy": "provisional_policy" not in registry["CC_completeness_disposition"],
        "runtime_install_flags_agree": documents["R2-SURVIVORSHIP.json"]["current_candidate"]["runtime_install_performed"] == submission["runtime_install_performed"],
        "original_install_receipt_scope": "current_runtime_lock_sha256" not in documents["R3-RUNTIME-ACCEPTANCE.json"]["install"],
        "current_runtime_binding_agrees": protocol["models"]["main"]["runtime_state"]["runtime_lock_sha256"] == submission["runtime_lock_sha256"] == documents["R3-RUNTIME-LOCK-VERIFICATION.json"]["runtime_lock_sha256"],
        "single_entry_rule_agrees": documents["R2-CONSTRUCTION.json"]["clocks"]["entry"] == documents["R2-COMPARISON.json"]["portfolio"].get("entry_fill_rule"),
        "study_fit_still_false": submission["model_fit_run"] is False,
        "accepted_PIT04_still_null": submission["accepted_layer15_receipt"] is None and submission["native_PIT04_exclusion_count"] is None,
    }
    for name, passed in semantic.items():
        if not passed:
            errors.append("semantic mismatch: " + name)
    return {"status": "PASS" if not errors else "FAIL", "carrier_entries": len(manifest),
            "manifest_sha256": digest(root / "SHA256SUMS"), "internal_bindings": bindings,
            "semantic_checks": semantic, "external_or_historical_boundaries": boundaries,
            "errors": errors,
            "scope": "Structural carrier/internal-reference/status checks only; no source truth, reviewer PASS, native strategy or data/execution acceptance."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result = verify(args.root.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
