#!/usr/bin/env python3
"""Draw the explicit G5 START profile; generation never establishes read acceptance.

The immutable R3 generator (80e69ff9...) supplies its supported select helper,
canonical JSON, SHA256 and source-reference matching. compact_manifest.py supplies
native identities, profile row validation and archive-member confinement. This
adapter supplies only the CC-approved final-action/closure-flag population seam.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
from jsonschema.exceptions import ValidationError

PROFILE = "start-closure/1"
SEED = 202610081850
QUOTA = 59
R3_SHA256 = "80e69ff94f97fffdf906583fa280f2a60a7487a54f0b58b05342264a5adf9627"
CONTRACT = Path(__file__).with_name("start-closure-stratum-contract.json")
CONTRACT_SHA256 = "d00ed22f6973cf3f2416b6c36d09caa9d8c829f427bd6f7854418f69e3fc292a"
PROTOCOL = Path(__file__).with_name("compact_manifest.py")
ROW_SCHEMA = "tools/sota-convergence/schemas/compact-decision-start-closure-1.json"
ACTION = ("ADOPT-NOW", "TRIAL")
FLAGS = {"PENDING-PIN": "pending_pin", "PENDING-LOCATOR": "pending_locator"}
SHA = re.compile(r"[0-9a-f]{64}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pinned_bytes(path, expected, limit=100 * 1024**2):
    require(isinstance(expected, str) and SHA.fullmatch(expected), "Expected hash must be a lowercase SHA256")
    path = Path(path)
    require(path.is_file() and path.stat().st_size <= limit, "Missing or oversized pinned input: " + path.name)
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected, "Pinned input changed: " + path.name)
    return raw


def import_verified(path, expected, name):
    raw = pinned_bytes(path, expected)
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "Pinned module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    # Execute the verified bytes, rather than ask a loader to reread the file.
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def load_r3(path):
    r3 = import_verified(Path(path), R3_SHA256, "g5_sealed_r3_sampler")
    require(sys.version_info[:3] == (3, 14, 4), "The sealed R3 stream requires native Python 3.14.4")
    pinned_bytes(Path(r3.random.__file__), r3.PINS["random"])
    require(r3.SEED == SEED and r3.QUOTA == QUOTA, "Sealed R3 seed or quota differs")
    return r3


def load_native(protocol, expected, r3):
    protocol = Path(protocol).resolve()
    repo = protocol.parents[2]
    for relative, pin in (("tools/sota-convergence/landscape-sweep/sweep_common.py", "common"),
                          ("scripts/catalog_decisions.py", "catalog")):
        pinned_bytes(repo / relative, r3.PINS[pin])
    native = import_verified(protocol, expected, "g5_start_closure_native")
    require(getattr(native, "START_CLOSURE_PROFILE", None) == PROFILE,
            "Native protocol does not expose the approved START profile")
    return native, repo


def declared_capture_index(rows, origin_map, native):
    """Bind declarations already checked by the exact PASS manifest, without a new byte-read claim."""
    index = {}

    def visit(value):
        if isinstance(value, dict):
            if "archive_member" in value:
                expected = value.get("capture_sha256", value.get("sha256", value.get("artifact_sha256")))
                require(expected is not None, "Archive declaration lacks its capture hash")
                member = native.member_name(value["archive_member"])
                native.sha(expected, "declared capture SHA256")
                require(member not in index or index[member]["sha256"] == expected,
                        "Hash-mismatched capture declarations: " + member)
                index[member] = {"sha256": expected}
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(rows)
    visit(origin_map)
    return index


def rows_and_origins(manifest, origin_map, manifest_sha, native, validator, r3):
    require(manifest.get("kind") == "g5-compact-landscape" and manifest.get("schema_version") == 1,
            "Input is not a native compact manifest")
    validation = manifest.get("validation", {})
    require(validation.get("status") == "PASS" and validation.get("blockers") == [], "Manifest is not native PASS")
    require(validation.get("profile") == PROFILE, "Manifest validation profile is not start-closure/1")
    require(manifest.get("release_tag") == "v2026.10.08", "Unexpected G5 release tag")
    require(isinstance(manifest.get("rows"), list), "Manifest rows are missing")
    native.sha(manifest.get("asset", {}).get("sha256"), "manifest asset SHA256")
    require(origin_map.get("schema_version") == 1 and origin_map.get("manifest_sha256") == manifest_sha,
            "Origin map does not bind the exact manifest")
    require(origin_map.get("stratum_contract_sha256") == CONTRACT_SHA256,
            "Origin map does not bind the START stratum contract")
    require(isinstance(origin_map.get("origins"), list), "Original fragment bindings are missing")
    index = declared_capture_index(manifest["rows"], origin_map, native)
    reference_validator = validator.evolve(schema={**validator.schema["$defs"]["sourceRef"],
                                                 "$defs": validator.schema["$defs"]})
    rows, origins, fragments = {}, {}, {}
    for position, row in enumerate(manifest["rows"]):
        validator.validate(row)
        require(not native.validate_row(row, index, profile=PROFILE), "Native profile row validation blocked")
        key = native.decision_key(row)
        require(key not in rows, "Duplicate native identity+slot+qualification key")
        if row["disposition"] in ACTION:
            require(row["pin"] is not None and all(s["pin"] is not None for s in row["primary_sources"]),
                    "An action row or primary source has a null pin")
            require(not any(flag in row.get("closure", {}) for flag in FLAGS.values()),
                    "An action row has closure residue")
        rows[key] = {"manifest_pointer": f"/rows/{position}",
                     "row_sha256": r3.digest(r3.canonical(row).encode()), "row": row}
    for binding in origin_map["origins"]:
        key = native.key(binding["key"])
        require(key in rows and key not in origins, "Duplicate or orphan origin key")
        require(isinstance(binding.get("fragments"), list) and binding["fragments"], "Origin has no fragment")
        origins[key] = binding["fragments"]
        row = rows[key]["row"]
        original_refs = row.get("source_refs", []) + [ref for choice in row.get("choices", []) for ref in choice["source_refs"]]
        for fragment in binding["fragments"]:
            name = native.text(fragment.get("fragment"), "origin fragment")
            artifact_sha = native.sha(fragment.get("artifact_sha256"), "origin fragment SHA256")
            owner = native.text(fragment.get("owner_lane"), "origin owner")
            parent = fragment.get("parent_family")
            require(parent in r3.PARENT_FAMILIES, "Unknown explicit parent-family rollup")
            metadata = {"fragment": name, "artifact_sha256": artifact_sha,
                        "owner_lane": owner, "parent_family": parent}
            fragment_key = (name, artifact_sha)
            require(fragment_key not in fragments or fragments[fragment_key] == metadata,
                    "Fragment has inconsistent owner or family")
            fragments[fragment_key] = metadata
            refs = fragment.get("source_refs")
            require(isinstance(refs, list) and refs, "Fragment has no original source-reference proof")
            for ref in refs:
                r3.checked_source_ref(ref, reference_validator)
                native.validate_ref(ref, index)
                require(ref["sha256"] == artifact_sha and ref.get("source_id") == name,
                        "Source proof does not bind its literal fragment and hash")
                require("owner_lane" not in ref or ref["owner_lane"] == owner, "Source proof owner differs")
                require(any(r3.source_ref_matches(ref, old) for old in original_refs),
                        "Fragment source proof is not an original row reference")
    require(set(origins) == set(rows), "Origin map does not cover every final row")
    return rows, origins, fragments


def select(rows, origins, fragments, classes, r3):
    """Call the sealed draw helper and restore original, unprojected evidence."""
    draw_origins = copy.deepcopy(origins)
    for bindings in draw_origins.values():
        for fragment in bindings:
            fragment["held_action_claims"] = []
    packets = [p for p in r3.select(rows, draw_origins, fragments, classes, SEED, QUOTA)
               if p["stratum"]["bucket_kind"] == r3.FINAL_BUCKET]
    for label, flag in FLAGS.items():
        projected = {}
        for key, item in rows.items():
            if flag in item["row"].get("closure", {}):
                projected[key] = {**item, "row": {**item["row"], "disposition": label}}
        packets.extend(p for p in r3.select(projected, draw_origins, fragments, [label], SEED, QUOTA)
                       if p["stratum"]["bucket_kind"] == r3.FINAL_BUCKET)
    for packet in packets:
        packet.pop("held_action_source_witnesses", None)
        packet.update(profile=PROFILE, stratum_contract_sha256=CONTRACT_SHA256,
                      acceptance_number=0, family_review={"status": "NOT_RUN", "required_distinct_model_families": 2,
                                                         "zero_defects_established": False})
        for selected in packet["selected"]:
            key = tuple(selected["native_key"])
            selected.update(copy.deepcopy(rows[key]))
            selected["origin_bindings"] = copy.deepcopy(origins[key])
            selected["matching_origin_bindings"] = [copy.deepcopy(f) for f in origins[key]
                if (f["fragment"], f["artifact_sha256"]) == (packet["stratum"]["fragment"], packet["stratum"]["artifact_sha256"])]
    return sorted(packets, key=lambda p: p["stratum_id"])


def packet_counts(packets, rows):
    samples = [p for p in packets if p["selection_mode"] == "SAMPLED"]
    sampled_keys = {tuple(i["native_key"]) for p in samples for i in p["selected"]}
    selected_keys = {tuple(i["native_key"]) for p in packets for i in p["selected"]}
    memberships = sum(p["selected_count"] for p in samples)
    return {"strata": len(packets), "empty_strata": sum(p["population_size"] == 0 for p in packets),
            "unique_final_action_rows": sum(i["row"]["disposition"] in ACTION for i in rows.values()),
            "final_action_census_memberships": sum(p["selected_count"] for p in packets if p["selection_mode"] == "FULL-CENSUS"),
            "sample_memberships": memberships, "unique_sampled_rows": len(sampled_keys),
            "sample_overlap_memberships": memberships - len(sampled_keys), "unique_selected_rows": len(selected_keys),
            "rows_with_both_closure_flags": sum(all(f in i["row"].get("closure", {}) for f in FLAGS.values()) for i in rows.values()),
            "counting_note": "Memberships are not distinct observations. Unique row counts remove fragment and closure-stratum overlap."}


def action_read_set(rows, manifest, manifest_sha, head):
    return {"schema_version": 1, "kind": "g5-final-action-read-set", "profile": PROFILE,
            "manifest_sha256": manifest_sha, "asset_sha256": manifest["asset"]["sha256"], "head": head,
            "row_id_definition": "Native decision_key: canonical repository_or_entry, literal slot, canonical qualification",
            "rows": [{"row_id": list(key), "pin": item["row"]["pin"],
                      "locator": [s["locator"] for s in item["row"]["primary_sources"]],
                      "capture_sha256": item["row"]["capture_sha256"]}
                     for key, item in sorted(rows.items()) if item["row"]["disposition"] in ACTION]}


def output_directory(root, name):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink() and ".." not in root.parts, "Output root must be an existing, canonical directory")
    require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name), "Output must be a single safe directory name")
    output = root.resolve() / name
    require(not output.exists() and not output.is_symlink(), "Output already exists")
    return output


def build_packet(*, profile, manifest_path, manifest_sha256, origin_map_path, origin_map_sha256,
                 protocol_sha256, r3_generator, head, output_root, output_name, protocol=PROTOCOL):
    require(profile == PROFILE, "Select --profile start-closure/1 explicitly")
    require(isinstance(head, str) and re.fullmatch(r"[0-9a-f]{40}", head), "Head must be a full lowercase commit ID")
    output = output_directory(output_root, output_name)
    r3 = load_r3(r3_generator)
    native, repo = load_native(protocol, protocol_sha256, r3)
    manifest_raw = pinned_bytes(manifest_path, manifest_sha256)
    origin_raw = pinned_bytes(origin_map_path, origin_map_sha256)
    contract_raw = pinned_bytes(CONTRACT, CONTRACT_SHA256)
    manifest, origin_map = native.load(manifest_raw), native.load(origin_raw)
    require(manifest.get("row_schema", {}).get("path") == ROW_SCHEMA, "Manifest does not bind the profile row schema")
    schema_raw = pinned_bytes(repo / ROW_SCHEMA, manifest["row_schema"]["sha256"])
    from jsonschema import Draft202012Validator
    validator = Draft202012Validator(native.load(schema_raw))
    rows, origins, fragments = rows_and_origins(manifest, origin_map, manifest_sha256, native, validator, r3)
    classes = validator.schema["properties"]["disposition"]["enum"]
    packets = select(rows, origins, fragments, classes, r3)
    actions = action_read_set(rows, manifest, manifest_sha256, head)
    actions["count"] = len(actions["rows"])
    files = {"inputs/manifest.json": manifest_raw, "inputs/origin-map.json": origin_raw,
             "inputs/row-schema.json": schema_raw, "stratum-contract.json": contract_raw,
             "action-read-set.json": (r3.canonical(actions) + "\n").encode()}
    review_sources = {
        "compact_manifest.py": Path(protocol),
        "test_compact_manifest.py": repo / "tests/test_compact_manifest.py",
        "start_closure_sampler.py": Path(__file__),
        "test_start_closure_sampler.py": Path(__file__).resolve().parents[2] / "tests/test_start_closure_sampler.py",
    }
    for name, path in review_sources.items():
        require(path.is_file() and path.stat().st_size < 100 * 1024**2, "Profile review source is missing or oversized: " + name)
        files["profile-code/" + name] = path.read_bytes()
    require(r3.digest(files["profile-code/compact_manifest.py"]) == protocol_sha256,
            "Native protocol changed while assembling its review packet")
    for packet in packets:
        files["strata/" + packet["stratum_id"] + ".json"] = (r3.canonical(packet) + "\n").encode()
    counts = packet_counts(packets, rows)
    summary = {"schema_version": 1, "kind": "g5-start-closure-sample-packet", "profile": PROFILE,
               "seed": SEED, "head": head, "manifest_sha256": manifest_sha256,
               "asset_sha256": manifest["asset"]["sha256"], "origin_map_sha256": origin_map_sha256,
               "stratum_contract_sha256": CONTRACT_SHA256,
               "implementations": {"sealed_r3_generator_sha256": R3_SHA256, "native_protocol_sha256": protocol_sha256,
                                   "random_sha256": r3.PINS["random"], "sampler_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
               "action_read_set": {"path": "action-read-set.json", "rows": len(actions["rows"]),
                                   "sha256": r3.digest(files["action-read-set.json"])},
               "counts": counts, "family_review": {"status": "NOT_RUN", "required_distinct_model_families": 2,
                                                     "profile_code_and_tests": "NOT_RUN", "zero_defects_established": False},
               "profile_review_sources": [{"path": "profile-code/" + name, "sha256": r3.digest(files["profile-code/" + name])}
                                          for name in sorted(review_sources)],
               "capture_verification": "The exact PASS manifest binds prior full-asset validation; this draw verifies declarations and input file hashes and does not claim a new full-asset byte check.",
               "strata": [{"stratum": p["stratum"], "path": "strata/" + p["stratum_id"] + ".json",
                           "sha256": r3.digest(files["strata/" + p["stratum_id"] + ".json"])} for p in packets]}
    files["manifest.json"] = (r3.canonical(summary) + "\n").encode()
    files["manifest.sha256"] = "".join(r3.digest(raw) + "  " + name + "\n" for name, raw in sorted(files.items())).encode()
    output.mkdir()
    try:
        for name, raw in sorted(files.items()):
            path = output / native.member_name(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(raw)
    except BaseException:
        shutil.rmtree(output)
        raise
    return {"output": str(output), "profile": PROFILE, "action_rows": len(actions["rows"]),
            "action_read_set_sha256": summary["action_read_set"]["sha256"],
            "packet_manifest_sha256": r3.digest(files["manifest.json"]), "counts": counts, "reads": "NOT_RUN"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=[PROFILE], required=True)
    for name in ("manifest", "manifest-sha256", "origin-map", "origin-map-sha256", "protocol-sha256", "r3-generator", "head", "output-root", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    try:
        result = build_packet(profile=args.profile, manifest_path=args.manifest, manifest_sha256=args.manifest_sha256,
                              origin_map_path=args.origin_map, origin_map_sha256=args.origin_map_sha256,
                              protocol_sha256=args.protocol_sha256, r3_generator=args.r3_generator, head=args.head,
                              output_root=args.output_root, output_name=args.output)
    except (ValueError, OSError, KeyError, TypeError, ValidationError) as error:
        parser.exit(2, "start_closure_sampler: " + str(error) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
