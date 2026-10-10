#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Typed review strata over explicit fragment artifacts and literal classes.

Primary implementations: native compact_manifest.py decision_key (7c4171...);
CPython 3.14.4 random.Random.sample (random.py 62dca8...). No compact builder,
identity canonicalizer, source parser, acceptance checker or RNG is rebuilt.
Run with the existing native /usr/bin/python3 -I runtime. Real draws require a
PASS manifest and an exact check0 CATALOG-PR-RESHAPED + CC read-item receipt.
Final actions and held source action claims are complete censuses. Only the
five nonaction final buckets use random samples. Packet creation runs no reads
by the two required model families and establishes no new acceptance.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import shutil
import sys
from collections import defaultdict

SEED = 202610081850
QUOTA = 59
PROTOCOL = Path(__file__).with_name("compact_manifest.py")
SCHEMA = PROTOCOL.parent / "schemas/compact-decision.json"
STRATUM_CONTRACT = Path(__file__).with_name("sealed_r3_stratum_contract.json")
FINAL_BUCKET = "FINAL-DISPOSITION"
CLAIM_BUCKET = "SOURCE-CLAIM-ONLY"
ACTION_CLASSES = ("ADOPT-NOW", "TRIAL")
PARENT_FAMILIES = ("a-stars", "b-field-landscape", "c-slot-index")
REQUIRED_MODEL_FAMILIES = 2
PINS = {
    "protocol": "7c4171e400c2f067c9833c85af83059594cfd8798d331143618887f34f1d0569",
    "common": "e8ee10a5e527125af8ddd3c2fda0322510c8c81d0b7cfa1c1bd73fc483f8f117",
    "catalog": "004a08b524c92a9ba3280f361f063ab9079797da0066998ab730149a220d8729",
    "row_schema": "716f69bb20ed4b60b21e8d32b6fb44902b069eb2cb2acaf6c6a109fdceed2e27",
    "random": "62dca8cdae7482513b99bb093ff038afd5131954e7eb78166d673a772cee871c",
    "stratum_contract": "c12428493bd8aa76785a6b08f15b1e0e20b5cc169f2bcd6831c7d75ea84573fd",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def pinned_bytes(path: Path, expected: str, limit: int = 100 * 1024**2) -> bytes:
    require(path.is_file() and path.stat().st_size <= limit, f"Missing or oversized input: {path}")
    raw = path.read_bytes()
    require(digest(raw) == expected, f"Pinned input changed: {path}")
    return raw


def load_native(protocol_path: Path, schema_path: Path):
    require(sys.version_info[:3] == (3, 14, 4), "Use pinned native /usr/bin/python3 3.14.4")
    random_path = Path(random.__file__)
    require(digest(random_path.read_bytes()) == PINS["random"], "Installed random.py changed")
    repo = protocol_path.resolve().parents[2]
    for path, pin in [(protocol_path, PINS["protocol"]),
                      (repo / "tools/sota-convergence/landscape-sweep/sweep_common.py", PINS["common"]),
                      (repo / "scripts/catalog_decisions.py", PINS["catalog"])]:
        pinned_bytes(path, pin)
    schema_raw = pinned_bytes(schema_path, PINS["row_schema"])
    spec = importlib.util.spec_from_file_location("g5_pinned_native_compact", protocol_path)
    require(spec is not None and spec.loader is not None, "Native protocol import unavailable")
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    from jsonschema import Draft202012Validator
    schema = native.load(schema_raw)
    validator = Draft202012Validator(schema)
    return native, validator, schema


def rows_and_origins(manifest: dict, origin_map: dict, manifest_sha: str, native, validator):
    require(manifest.get("kind") == "g5-compact-landscape" and manifest.get("schema_version") == 1,
            "Input is not the native compact manifest contract")
    require(manifest.get("release_tag") == "v2026.10.08", "Unexpected compact release contract")
    require(manifest.get("validation", {}).get("status") == "PASS", "Manifest is not native PASS")
    require(manifest.get("row_schema", {}).get("sha256") == PINS["row_schema"], "Manifest row schema differs")
    require(origin_map.get("schema_version") == 1 and origin_map.get("manifest_sha256") == manifest_sha,
            "Origin map does not bind this exact manifest")
    require(origin_map.get("stratum_contract_sha256") == PINS["stratum_contract"],
            "Origin map does not bind the full action census policy")
    require(origin_map.get("held_action_claims_complete") is True,
            "Original held action source claims have no completeness declaration")
    require(isinstance(manifest.get("rows"), list), "Native manifest rows are absent")
    reference_validator = validator.evolve(schema={**validator.schema["$defs"]["sourceRef"],
                                                 "$defs": validator.schema["$defs"]})
    rows = {}
    for index, row in enumerate(manifest["rows"]):
        validator.validate(row)
        key = native.decision_key(row)
        require(key not in rows, "Duplicate native identity+slot+qualification key")
        rows[key] = {"row": row, "manifest_pointer": f"/rows/{index}",
                     "row_sha256": digest(canonical(row).encode())}
    origins = {}
    fragments = {}
    require(isinstance(origin_map.get("origins"), list), "Explicit origin bindings absent")
    for binding in origin_map["origins"]:
        key = native.key(binding["key"])
        require(key in rows and key not in origins, "Duplicate or orphan origin key")
        require(isinstance(binding.get("fragments"), list) and binding["fragments"], "Origin has no explicit fragment")
        origins[key] = binding["fragments"]
        row = rows[key]["row"]
        original_actions = held_action_witnesses(row)
        original_refs = row.get("source_refs", []) + [r for c in row.get("choices", []) for r in c["source_refs"]]
        for witness in original_actions:
            checked_source_ref(witness["source_ref"], reference_validator)
        declared_refs = []
        for fragment in binding["fragments"]:
            name = native.text(fragment["fragment"], "origin fragment")
            sha = native.sha(fragment["artifact_sha256"], "origin fragment artifact SHA")
            owner = native.text(fragment["owner_lane"], "origin owner_lane")
            parent = fragment.get("parent_family")
            require(parent in PARENT_FAMILIES, "Missing or unknown explicit parent-family rollup")
            metadata = {"fragment": name, "artifact_sha256": sha, "owner_lane": owner, "parent_family": parent}
            require((name, sha) not in fragments or fragments[(name, sha)] == metadata,
                    "One fragment artifact has inconsistent owner or parent-family metadata")
            fragments[(name, sha)] = metadata
            origin_refs = fragment.get("source_refs")
            require(isinstance(origin_refs, list) and origin_refs,
                    "Fragment has no nonempty original array provenance proof list")
            for origin_reference in origin_refs:
                checked_source_ref(origin_reference, reference_validator)
                require(origin_reference["sha256"] == sha and origin_reference.get("source_id") == name,
                        "Original array proof does not bind this fragment artifact and literal source ID")
                require("owner_lane" not in origin_reference or origin_reference["owner_lane"] == owner,
                        "Original array proof owner differs from the explicit fragment owner")
                require(any(source_ref_matches(origin_reference, r) for r in original_refs),
                        "Fragment array proof does not preserve an original row source reference")
            claims = fragment.get("held_action_claims")
            require(isinstance(claims, list), "Fragment has no explicit held action claim list")
            require(not claims or row["disposition"] == "PENDING", "Non-PENDING row has held action claims")
            for claim in claims:
                require(isinstance(claim, dict) and claim.get("disposition") in ACTION_CLASSES,
                        "Held source claim is not literal ADOPT-NOW or TRIAL")
                require(isinstance(claim.get("source_refs"), list) and claim["source_refs"],
                        "Held action claim has no original source witness")
                claim_origins = claim.get("origin_source_refs")
                require(isinstance(claim_origins, list) and claim_origins,
                        "Held action claim has no explicit original-array to nested-source crosswalk")
                for claim_origin in claim_origins:
                    checked_source_ref(claim_origin, reference_validator)
                    require(any(source_ref_matches(claim_origin, r) for r in origin_refs),
                            "Held action crosswalk belongs to a different fragment origin")
                for reference in claim["source_refs"]:
                    checked_source_ref(reference, reference_validator)
                    require(any(w["disposition"] == claim["disposition"] and
                                source_ref_matches(reference, w["source_ref"]) for w in original_actions),
                            "Declared held action source ref/class does not match the original PENDING choices")
                    declared_refs.append((claim["disposition"], reference))
        for witness in original_actions:
            require(any(disposition == witness["disposition"] and
                        source_ref_matches(reference, witness["source_ref"])
                        for disposition, reference in declared_refs),
                    "Original held action witness is omitted from every origin binding")
    require(rows.keys() == origins.keys(), "Missing origin binding for a native row")
    return rows, origins, fragments


def checked_source_ref(reference: dict, validator) -> None:
    validator.validate(reference)
    require(isinstance(reference.get("archive_member"), str) and reference["archive_member"],
            "Action source witness needs its exact original archive member")


def source_ref_matches(declared: dict, original: dict) -> bool:
    required = ("sha256", "archive_member", "pointer")
    optional = ("source_id", "owner_lane", "occurrence_id")
    return (all(declared.get(k) == original.get(k) for k in required) and
            all(declared.get(k) == original.get(k) for k in optional))


def held_action_witnesses(row: dict) -> list[dict]:
    if row["disposition"] != "PENDING":
        return []
    return [{"disposition": choice["disposition"], "choice_pointer": f"/choices/{ci}",
             "source_ref_pointer": f"/choices/{ci}/source_refs/{ri}", "source_ref": reference}
            for ci, choice in enumerate(row.get("choices", [])) if choice["disposition"] in ACTION_CLASSES
            for ri, reference in enumerate(choice["source_refs"])]


def family_review() -> dict:
    return {"required_distinct_model_families": REQUIRED_MODEL_FAMILIES, "status": "NOT-RUN",
            "designated_model_families": [],
            "action_coverage_required_per_family": "100 percent of all final action and held source action censuses"}


def select(rows: dict, origins: dict, fragments: dict, classes: list[str], seed: int, quota: int):
    populations = defaultdict(dict)
    for key, item in rows.items():
        disposition = item["row"]["disposition"]
        require(disposition in classes, "Disposition is outside the pinned compact vocabulary")
        for fragment in origins[key]:
            # Same decision contributes once per artifact. Repeated provenance
            # records stay intact in the selected origin_bindings; never vote.
            stratum = (fragment["fragment"], fragment["artifact_sha256"], FINAL_BUCKET, disposition)
            populations[stratum][key] = item
            for claim in fragment["held_action_claims"]:
                stratum = (fragment["fragment"], fragment["artifact_sha256"], CLAIM_BUCKET, claim["disposition"])
                populations[stratum][key] = item
    packets = []
    for name, artifact_sha in sorted(fragments):
        for bucket_kind, disposition in [(FINAL_BUCKET, d) for d in sorted(classes)] + [
                (CLAIM_BUCKET, d) for d in ACTION_CLASSES]:
            stratum = (name, artifact_sha, bucket_kind, disposition)
            population = populations[stratum]
            keys = sorted(population)
            derived_seed = int(digest(canonical([seed, *stratum]).encode()), 16)
            census = bucket_kind == CLAIM_BUCKET or disposition in ACTION_CLASSES
            chosen = keys if census else sorted(random.Random(derived_seed).sample(keys, min(quota, len(keys))))
            selected = []
            witness_count = 0
            for key in chosen:
                item = population[key]
                matching_origins = [f for f in origins[key]
                                    if (f["fragment"], f["artifact_sha256"]) == (name, artifact_sha)]
                selected_item = {"native_key": list(key), **item, "origin_bindings": origins[key],
                                 "matching_origin_bindings": matching_origins}
                if bucket_kind == CLAIM_BUCKET:
                    claims = [c for f in matching_origins for c in f["held_action_claims"]
                              if c["disposition"] == disposition]
                    original_witnesses = [w for w in held_action_witnesses(item["row"])
                                          if w["disposition"] == disposition and
                                          any(source_ref_matches(r, w["source_ref"])
                                              for c in claims for r in c["source_refs"])]
                    require(claims and original_witnesses and item["row"]["disposition"] == "PENDING",
                            "Source action census lost its same-origin witnesses or final PENDING state")
                    selected_item.update(held_action_claims=claims, held_action_source_witnesses=original_witnesses)
                    witness_count += len(original_witnesses)
                selected.append(selected_item)
            packets.append({"stratum": {"fragment": name, "artifact_sha256": artifact_sha,
                                        "bucket_kind": bucket_kind, "disposition": disposition},
                            "parent_family": fragments[(name, artifact_sha)]["parent_family"],
                            "owner_lane": fragments[(name, artifact_sha)]["owner_lane"],
                            "stratum_id": digest(canonical(stratum).encode()),
                            "seed": seed, "derived_seed": derived_seed, "population_size": len(keys),
                            "selected_count": len(chosen), "quota": "ALL" if census else quota,
                            "selection_mode": "FULL-CENSUS" if census else "SAMPLED",
                            "held_action_source_witnesses": witness_count,
                            "stratum_contract_sha256": PINS["stratum_contract"], "family_review": family_review(),
                            "population_key_sha256": digest(canonical(keys).encode()), "selected": selected})
    return packets


def check_cue(cue: dict, manifest_sha: str, origin_sha: str, expected_head: str) -> None:
    require(cue.get("kind") == "CATALOG-PR-RESHAPED", "Final reshape declaration absent")
    code = cue.get("check_exit_code")
    require(type(code) is int and code == 0, "Reshape progress/check1 is not a literal check0 draw cue")
    require(isinstance(cue.get("cc_read_item"), str) and cue["cc_read_item"].strip(), "CC read item absent")
    require(cue.get("manifest_sha256") == manifest_sha and cue.get("origin_map_sha256") == origin_sha,
            "Reshape cue does not bind the final manifest and origin map")
    require(cue.get("stratum_contract_sha256") == PINS["stratum_contract"],
            "Reshape cue does not bind the full action census policy")
    require(isinstance(expected_head, str) and len(expected_head) == 40 and
            all(c in "0123456789abcdef" for c in expected_head) and cue.get("head") == expected_head,
            "Reshape cue does not bind the designated exact head")
    require(isinstance(cue.get("source_declaration"), dict) and cue["source_declaration"],
            "Cue needs the root declaration locator/receipt")


def packet_counts(packets: list) -> dict:
    selected_keys = {tuple(item["native_key"]) for packet in packets for item in packet["selected"]}
    final_actions = [p for p in packets if p["stratum"]["bucket_kind"] == FINAL_BUCKET and
                     p["stratum"]["disposition"] in ACTION_CLASSES]
    held_actions = [p for p in packets if p["stratum"]["bucket_kind"] == CLAIM_BUCKET]
    nonactions = [p for p in packets if p["selection_mode"] == "SAMPLED"]
    return {"strata": len(packets), "nonempty_strata": sum(p["population_size"] > 0 for p in packets),
            "empty_strata": sum(p["population_size"] == 0 for p in packets),
            "sample_memberships": sum(p["selected_count"] for p in packets),
            "unique_sampled_rows": len(selected_keys),
            "population_memberships": sum(p["population_size"] for p in packets),
            "nonaction_sample_memberships": sum(p["selected_count"] for p in nonactions),
            "final_action_census_memberships": sum(p["selected_count"] for p in final_actions),
            "held_action_census_memberships": sum(p["selected_count"] for p in held_actions),
            "held_action_source_witnesses": sum(p["held_action_source_witnesses"] for p in held_actions)}


def publish(path: Path, packets: list, inputs: dict) -> dict:
    require(not path.exists(), "Sample packet revision already exists")
    staging = path.with_name(path.name + ".tmp")
    require(not staging.exists(), "Sample packet staging already exists")
    staging.mkdir(parents=True)
    files = []
    try:
        (staging / "strata").mkdir()
        for packet in packets:
            name = "strata/" + packet["stratum_id"] + ".json"
            raw = (json.dumps(packet, indent=2, sort_keys=True) + "\n").encode()
            (staging / name).write_bytes(raw)
            files.append({"path": name, "sha256": digest(raw), "bytes": len(raw)})
        parent_rollups = {family: packet_counts([p for p in packets if p["parent_family"] == family])
                          for family in PARENT_FAMILIES}
        summary = {"schema_version": 1, "kind": "g5-seeded-stratified-review-samples",
                   "seed": SEED, "nonaction_quota": QUOTA, "action_quota": "ALL", "inputs": inputs,
                   "stratum_contract_sha256": PINS["stratum_contract"], "family_review": family_review(),
                   "counts": packet_counts(packets), "parent_family_rollups": parent_rollups,
                   "policy": {"strata": "explicit fragment ID+artifact SHA × bucket kind × literal disposition",
                              "sampling": "min(59,N) only for five nonaction final buckets; all final and held source actions are complete censuses",
                              "rng": "CPython random.Random.sample for nonactions; independent SHA256-derived seed includes bucket kind",
                              "multi_origin": "Keep each decision in every explicit fragment; identical provenance records retained but not extra population votes",
                              "pending": "literal PENDING stays its own bucket; selected full row/choices/provisional/measurement/owner unchanged",
                              "held_action": "SOURCE-CLAIM-ONLY census retains original fragment-array proof, its explicit crosswalk to nested action sources, every same-class witness and all known source IDs",
                              "family_review": "Two root-designated model families must each review the complete action censuses; no family read is run or asserted by packet creation",
                              "limits": "Review packets only; not asset rows, not native --rows equality witness, not new acceptance or conflict clearance"},
                   "strata": [{k: v for k, v in p.items() if k != "selected"} for p in packets], "files": files}
        raw = (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode()
        (staging / "sample-summary.json").write_bytes(raw)
        files.append({"path": "sample-summary.json", "sha256": digest(raw), "bytes": len(raw)})
        manifest = "".join(f["sha256"] + "  " + f["path"] + "\n" for f in files)
        (staging / "manifest.sha256").write_text(manifest)
        for file in files:
            require(digest((staging / file["path"]).read_bytes()) == file["sha256"], "Staged sample file changed")
        os.replace(staging, path)
        return {"path": str(path), "manifest_sha256": digest(manifest.encode()), **summary["counts"],
                "seed": SEED, "nonaction_quota": QUOTA, "action_quota": "ALL", "family_review": family_review()}
    except BaseException:
        shutil.rmtree(staging)
        raise


def fixture_row(index: int, disposition: str = "WATCH") -> dict:
    row = {"repository_or_entry": f"fixture/entry-{index:04d}", "slot": "native-clients",
           "qualification": {}, "disposition": disposition, "evidence_class": "UNKNOWN", "pin": None,
           "primary_sources": [{"locator": "fixture-source:retained-record", "pin": None, "subject": "reference"}],
           "capture_sha256": "0" * 64, "archive_member": "fixture/capture.json",
           "owner_lane": "fixture", "refresh_date": "2026-10-08"}
    if disposition == "PENDING":
        row["pending"] = {"provisional_disposition": "WATCH", "measurement": "Synthetic check only", "owner": "fixture"}
    if disposition == "ADOPT-NOW":
        row["evidence_class"] = "RECORDED-LIVE-ACCEPTANCE"
        row["acceptance_witness"] = {"archive_member": "fixture/acceptance.json", "sha256": "0" * 64, "pointer": "/pass"}
    return row


def fixture_fragment(name: str, sha: str, parent: str, claims: list | None = None) -> dict:
    return {"fragment": name, "artifact_sha256": sha, "parent_family": parent, "owner_lane": "fixture",
            "source_refs": [], "held_action_claims": claims if claims is not None else []}


def fixture_inputs(rows_list: list, fragments: list, manifest_sha: str) -> tuple[dict, dict]:
    manifest = {"kind": "g5-compact-landscape", "schema_version": 1, "release_tag": "v2026.10.08",
                "row_schema": {"sha256": PINS["row_schema"]}, "validation": {"status": "PASS"}, "rows": rows_list}
    origin_map = {"schema_version": 1, "manifest_sha256": manifest_sha,
                  "stratum_contract_sha256": PINS["stratum_contract"], "held_action_claims_complete": True,
                  "origins": [{"key": {n: row[n] for n in ["repository_or_entry", "slot", "qualification"]},
                               "fragments": copy.deepcopy(fragments)} for row in rows_list]}
    for index, binding in enumerate(origin_map["origins"]):
        rows_list[index]["source_refs"] = []
        for fragment in binding["fragments"]:
            proof = {"sha256": fragment["artifact_sha256"], "archive_member": f"fixture/{fragment['fragment']}.json",
                     "pointer": f"/{index}", "source_id": fragment["fragment"], "owner_lane": fragment["owner_lane"]}
            fragment["source_refs"] = [proof]
            rows_list[index]["source_refs"].append(copy.deepcopy(proof))
    return manifest, origin_map


def self_check(native, validator, classes: list[str]) -> dict:
    checks = []
    single = fixture_fragment("fixture", "1" * 64, "a-stars")
    fragments = {("fixture", "1" * 64): single}
    for size in [0, 1, 58, 59, 60]:
        rows = {native.decision_key(fixture_row(i)): {"row": fixture_row(i), "manifest_pointer": f"/rows/{i}",
                                                    "row_sha256": digest(canonical(fixture_row(i)).encode())}
                for i in range(size)}
        origins = {k: [single] for k in rows}
        before = canonical(rows and [v["row"] for v in rows.values()] or [])
        first = select(rows, origins, fragments, classes, SEED, QUOTA)
        shuffled = dict(reversed(list(rows.items())))
        second = select(shuffled, origins, fragments, classes, SEED, QUOTA)
        require(canonical(first) == canonical(second), "Input-order invariant failed")
        require(sum(p["selected_count"] for p in first) == min(59, size), "Boundary quota failed")
        require(before == canonical([v["row"] for v in rows.values()]), "Sampling mutated rows")
        for p in first:
            require(len({tuple(x["native_key"]) for x in p["selected"]}) == p["selected_count"], "Repeated selection")
        checks.append(f"quota-and-order-{size}")
    manifest_sha = "2" * 64
    a = fixture_fragment("a", "3" * 64, "a-stars")
    b = fixture_fragment("b", "4" * 64, "b-field-landscape")
    rows_list = ([fixture_row(i, "TRIAL") for i in range(60)] +
                 [fixture_row(i, "ADOPT-NOW") for i in range(60, 120)] +
                 [fixture_row(i) for i in range(120, 180)] +
                 [fixture_row(i, "PENDING") for i in range(180, 240)])
    manifest, origin_map = fixture_inputs(rows_list, [a, b], manifest_sha)
    for index in range(180, 240):
        row = rows_list[index]
        row["choices"] = []
        for disposition in ACTION_CLASSES:
            references = [{"sha256": str(fi + 5) * 64, "archive_member": f"fixture/{name}-claims.json",
                           "pointer": f"/actions/{index}/{disposition}", "source_id": f"fixture-nested-{name}"}
                          for fi, name in enumerate(["a", "b"])]
            if index == 180 and disposition == "TRIAL":
                references.insert(1, copy.deepcopy(references[0]))
            row["choices"].append({"disposition": disposition, "source_refs": references})
            for fi, fragment in enumerate(origin_map["origins"][index]["fragments"]):
                ref = next(r for r in references if r["source_id"] == f"fixture-nested-{fragment['fragment']}")
                fragment["held_action_claims"].append({"disposition": disposition, "source_refs": [ref],
                                                      "origin_source_refs": copy.deepcopy(fragment["source_refs"])})
    origin_map["origins"][180]["fragments"].append(copy.deepcopy(origin_map["origins"][180]["fragments"][0]))
    before = canonical([manifest, origin_map])
    rows, origins, fragments = rows_and_origins(manifest, origin_map, manifest_sha, native, validator)
    packets = select(rows, origins, fragments, classes, SEED, QUOTA)
    require(before == canonical([manifest, origin_map]), "Origin validation or census mutated original records")
    require(len(packets) == 18, "Nine typed strata per artifact are not retained")
    for packet in packets:
        stratum = packet["stratum"]
        if stratum["disposition"] in ACTION_CLASSES:
            require(packet["population_size"] == 60 and packet["selected_count"] == 60 and
                    packet["selection_mode"] == "FULL-CENSUS" and packet["quota"] == "ALL",
                    "Action population was capped at 59")
        require(packet["family_review"]["required_distinct_model_families"] == 2 and
                packet["family_review"]["status"] == "NOT-RUN" and
                not packet["family_review"]["designated_model_families"], "Family read or quality result was fabricated")
        for item in packet["selected"]:
            require(item["row"] == rows[tuple(item["native_key"])]["row"], "Selected full row changed")
    totals = packet_counts(packets)
    require(totals["final_action_census_memberships"] == 240 and
            totals["held_action_census_memberships"] == 240 and totals["nonaction_sample_memberships"] == 236,
            "Action/nonaction membership denominators differ")
    require(totals["held_action_source_witnesses"] == 241, "Original duplicate held source witness was lost or voted twice")
    require(totals["sample_memberships"] == 716 and totals["unique_sampled_rows"] <= 240,
            "Sample memberships were confused with unique native rows")
    original_duplicate = next(x for p in packets if p["stratum"]["bucket_kind"] == CLAIM_BUCKET and
                              p["stratum"]["fragment"] == "a" and p["stratum"]["disposition"] == "TRIAL"
                              for x in p["selected"] if x["row"]["repository_or_entry"] == "fixture/entry-0180")
    require(len(original_duplicate["held_action_claims"]) == 2 and
            len(original_duplicate["held_action_source_witnesses"]) == 2,
            "Declared repeated claims or original repeated witnesses were not retained")
    checks += ["full-final-actions-60", "full-held-actions-60", "nine-typed-buckets", "multi-fragment",
               "pending-unchanged", "duplicate-claim-and-witness-retained", "membership-denominators",
               "two-family-requirement-not-run", "input-records-unchanged"]
    require(canonical(packets) == canonical(select(dict(reversed(list(rows.items()))), origins, fragments,
                                                  classes, SEED, QUOTA)), "Census order stability failed")
    checks.append("typed-census-order")
    smaller_origins = {k: [v[0]] for k, v in origins.items()}
    only_a = select(rows, smaller_origins, {("a", "3" * 64): fragments[("a", "3" * 64)]}, classes, SEED, QUOTA)
    signature = lambda p: (p["stratum_id"], p["derived_seed"], p["population_key_sha256"],
                           [(x["native_key"], x["row_sha256"]) for x in p["selected"]])
    require([signature(p) for p in only_a] ==
            [signature(p) for p in packets if p["stratum"]["fragment"] == "a"],
            "Unrelated stratum changed draw")
    checks.append("independent-strata")
    isolated_row = fixture_row(999, "PENDING")
    isolated_row["choices"] = copy.deepcopy(rows_list[180]["choices"])
    isolated_manifest, isolated_map = fixture_inputs([isolated_row], [a, b], manifest_sha)
    for fragment, disposition in zip(isolated_map["origins"][0]["fragments"], ["TRIAL", "ADOPT-NOW"]):
        ref = next(r for c in isolated_row["choices"] if c["disposition"] == disposition
                   for r in c["source_refs"] if r["source_id"] == f"fixture-nested-{fragment['fragment']}")
        fragment["held_action_claims"] = [{"disposition": disposition, "source_refs": [ref],
                                           "origin_source_refs": copy.deepcopy(fragment["source_refs"])}]
    # Cover the other witnesses through a third explicit origin, not by
    # attributing their literal class to either of the first two origins.
    c = fixture_fragment("c", "8" * 64, "c-slot-index")
    c["source_refs"] = [{"sha256": "8" * 64, "archive_member": "fixture/c.json", "pointer": "/0",
                         "source_id": "c", "owner_lane": "fixture"}]
    c["held_action_claims"] = [{"disposition": choice["disposition"], "source_refs": choice["source_refs"],
                                "origin_source_refs": copy.deepcopy(c["source_refs"])}
                               for choice in isolated_row["choices"]]
    isolated_row["source_refs"].extend(copy.deepcopy(c["source_refs"]))
    isolated_map["origins"][0]["fragments"].append(c)
    ir, io, iff = rows_and_origins(isolated_manifest, isolated_map, manifest_sha, native, validator)
    isolated_packets = select(ir, io, iff, classes, SEED, QUOTA)
    require(all(p["population_size"] == 0 for p in isolated_packets if
                p["stratum"]["bucket_kind"] == CLAIM_BUCKET and
                ((p["stratum"]["fragment"] == "a" and p["stratum"]["disposition"] == "ADOPT-NOW") or
                 (p["stratum"]["fragment"] == "b" and p["stratum"]["disposition"] == "TRIAL"))),
            "Another origin or provisional class leaked into an action census")
    checks.append("no-cross-origin-action-inference")
    require(all(r["sha256"] != origin["sha256"] for fragment in isolated_map["origins"][0]["fragments"]
                for claim in fragment["held_action_claims"] for r in claim["source_refs"]
                for origin in claim["origin_source_refs"]), "Cross-domain fixture does not distinguish array and nested sources")
    checks.append("cross-domain-origin-to-nested-source")
    cue_head = "a" * 40
    cue = {"kind": "CATALOG-PR-RESHAPED", "check_exit_code": 0, "head": cue_head,
           "cc_read_item": "fixture", "manifest_sha256": manifest_sha, "origin_map_sha256": "7" * 64,
           "stratum_contract_sha256": PINS["stratum_contract"], "source_declaration": {"fixture": True}}
    check_cue(cue, manifest_sha, "7" * 64, cue_head)
    missing_witness = copy.deepcopy(origin_map)
    missing_witness["origins"][181]["fragments"][0]["held_action_claims"] = []
    bad_optional = copy.deepcopy(origin_map)
    bad_optional["origins"][181]["fragments"][0]["held_action_claims"][0]["source_refs"][0]["source_id"] = "another-origin"
    omitted_optional = copy.deepcopy(origin_map)
    del omitted_optional["origins"][181]["fragments"][0]["held_action_claims"][0]["source_refs"][0]["source_id"]
    swapped_claims = copy.deepcopy(origin_map)
    swapped_fragments = swapped_claims["origins"][181]["fragments"]
    swapped_fragments[0]["held_action_claims"], swapped_fragments[1]["held_action_claims"] = (
        swapped_fragments[1]["held_action_claims"], swapped_fragments[0]["held_action_claims"])
    missing_proof = copy.deepcopy(origin_map)
    del missing_proof["origins"][181]["fragments"][0]["source_refs"]
    empty_final_action_proof = copy.deepcopy(origin_map)
    empty_final_action_proof["origins"][0]["fragments"][0]["source_refs"] = []
    empty_nonaction_proof = copy.deepcopy(origin_map)
    empty_nonaction_proof["origins"][120]["fragments"][0]["source_refs"] = []
    bad_proof = copy.deepcopy(origin_map)
    bad_proof["origins"][181]["fragments"][0]["source_refs"][0]["source_id"] = "b"
    omitted_crosswalk = copy.deepcopy(origin_map)
    del omitted_crosswalk["origins"][181]["fragments"][0]["held_action_claims"][0]["origin_source_refs"]
    omitted_origin_lane = copy.deepcopy(origin_map)
    del omitted_origin_lane["origins"][181]["fragments"][0]["held_action_claims"][0]["origin_source_refs"][0]["owner_lane"]
    bad_class = copy.deepcopy(origin_map)
    bad_class["origins"][181]["fragments"][0]["held_action_claims"][0]["disposition"] = "TRIAL"
    bad_family = copy.deepcopy(origin_map)
    bad_family["origins"][0]["fragments"][0]["parent_family"] = "guess-from-lane"
    nonpending_claim = copy.deepcopy(origin_map)
    nonpending_claim["origins"][0]["fragments"][0]["held_action_claims"] = copy.deepcopy(
        origin_map["origins"][181]["fragments"][0]["held_action_claims"])
    for label, action in [
        ("missing-origin", lambda: rows_and_origins(manifest, {**origin_map, "origins": []}, manifest_sha, native, validator)),
        ("origin-digest-drift", lambda: rows_and_origins(manifest, origin_map, "5" * 64, native, validator)),
        ("duplicate-native-key", lambda: rows_and_origins({**manifest, "rows": rows_list + [rows_list[0]]}, origin_map, manifest_sha, native, validator)),
        ("blocked-manifest", lambda: rows_and_origins({**manifest, "validation": {"status": "BLOCKED"}}, origin_map, manifest_sha, native, validator)),
        ("schema-drift", lambda: rows_and_origins({**manifest, "row_schema": {"sha256": "6" * 64}}, origin_map, manifest_sha, native, validator)),
        ("wrong-manifest-contract", lambda: rows_and_origins({**manifest, "kind": "fixture-other"}, origin_map, manifest_sha, native, validator)),
        ("policy-drift", lambda: rows_and_origins(manifest, {**origin_map, "stratum_contract_sha256": "9" * 64}, manifest_sha, native, validator)),
        ("missing-held-completeness", lambda: rows_and_origins(manifest, {**origin_map, "held_action_claims_complete": False}, manifest_sha, native, validator)),
        ("held-witness-omitted", lambda: rows_and_origins(manifest, missing_witness, manifest_sha, native, validator)),
        ("held-optional-id-mismatch", lambda: rows_and_origins(manifest, bad_optional, manifest_sha, native, validator)),
        ("held-known-id-omitted", lambda: rows_and_origins(manifest, omitted_optional, manifest_sha, native, validator)),
        ("valid-row-claim-swapped-origins", lambda: rows_and_origins(manifest, swapped_claims, manifest_sha, native, validator)),
        ("missing-original-origin-proof", lambda: rows_and_origins(manifest, missing_proof, manifest_sha, native, validator)),
        ("empty-final-action-origin-proof", lambda: rows_and_origins(manifest, empty_final_action_proof, manifest_sha, native, validator)),
        ("empty-nonaction-origin-proof", lambda: rows_and_origins(manifest, empty_nonaction_proof, manifest_sha, native, validator)),
        ("incorrect-original-origin-proof", lambda: rows_and_origins(manifest, bad_proof, manifest_sha, native, validator)),
        ("missing-origin-nested-crosswalk", lambda: rows_and_origins(manifest, omitted_crosswalk, manifest_sha, native, validator)),
        ("known-origin-lane-omitted", lambda: rows_and_origins(manifest, omitted_origin_lane, manifest_sha, native, validator)),
        ("held-class-mismatch", lambda: rows_and_origins(manifest, bad_class, manifest_sha, native, validator)),
        ("missing-explicit-family", lambda: rows_and_origins(manifest, bad_family, manifest_sha, native, validator)),
        ("nonpending-held-claim", lambda: rows_and_origins(manifest, nonpending_claim, manifest_sha, native, validator)),
        ("missing-cue", lambda: check_cue({}, manifest_sha, "7" * 64, cue_head)),
        ("progress-check1", lambda: check_cue({**cue, "check_exit_code": 1}, manifest_sha, "7" * 64, cue_head)),
        ("boolean-cue-code", lambda: check_cue({**cue, "check_exit_code": False}, manifest_sha, "7" * 64, cue_head)),
        ("float-cue-code", lambda: check_cue({**cue, "check_exit_code": 0.0}, manifest_sha, "7" * 64, cue_head)),
        ("cue-policy-drift", lambda: check_cue({**cue, "stratum_contract_sha256": "9" * 64}, manifest_sha, "7" * 64, cue_head)),
        ("cue-head-drift", lambda: check_cue({**cue, "head": "b" * 40}, manifest_sha, "7" * 64, cue_head)),
    ]:
        try:
            action()
        except ValueError:
            checks.append(label)
        else:
            raise ValueError("Missing rejection: " + label)
    return {"kind": "SYNTHETIC-SAMPLER-PREPARATION-CHECK", "checks": checks, "checks_passed": len(checks),
            "seed": SEED, "nonaction_quota": QUOTA, "action_quota": "ALL", "synthetic_counts": totals,
            "family_review": family_review(), "stratum_contract_sha256": PINS["stratum_contract"],
            "python": sys.version.split()[0], "random_sha256": PINS["random"],
            "real_manifest_read": False, "real_samples_published": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--row-schema", type=Path, default=SCHEMA)
    parser.add_argument("--stratum-contract", type=Path, default=STRATUM_CONTRACT)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--origin-map", type=Path)
    parser.add_argument("--origin-map-sha256")
    parser.add_argument("--reshape-cue", type=Path)
    parser.add_argument("--reshape-cue-sha256")
    parser.add_argument("--head", help="Designated exact 40-character root head; must match the final reshape cue")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    pinned_bytes(args.stratum_contract, PINS["stratum_contract"], limit=1024**2)
    native, validator, schema = load_native(args.native_protocol, args.row_schema)
    classes = schema["properties"]["disposition"]["enum"]
    if args.self_check:
        require(not any([args.manifest, args.origin_map, args.reshape_cue, args.output, args.head]), "Self-check cannot consume a real population")
        print(json.dumps(self_check(native, validator, classes), sort_keys=True))
        return
    require(all([args.manifest, args.manifest_sha256, args.origin_map, args.origin_map_sha256,
                 args.reshape_cue, args.reshape_cue_sha256, args.output, args.head]), "Real sampling requires final pinned inputs, designated head and root cue")
    cue = native.load(pinned_bytes(args.reshape_cue, args.reshape_cue_sha256, limit=1024**2))
    check_cue(cue, args.manifest_sha256, args.origin_map_sha256, args.head)
    raw = pinned_bytes(args.manifest, args.manifest_sha256)
    origin_raw = pinned_bytes(args.origin_map, args.origin_map_sha256)
    manifest, origin_map = native.load(raw), native.load(origin_raw)
    rows, origins, fragments = rows_and_origins(manifest, origin_map, args.manifest_sha256, native, validator)
    packets = select(rows, origins, fragments, classes, SEED, QUOTA)
    require(digest(args.manifest.read_bytes()) == args.manifest_sha256 and
            digest(args.origin_map.read_bytes()) == args.origin_map_sha256 and
            digest(args.reshape_cue.read_bytes()) == args.reshape_cue_sha256 and
            digest(args.stratum_contract.read_bytes()) == PINS["stratum_contract"], "Input changed during sampling")
    inputs = {"manifest": {"path": str(args.manifest), "sha256": args.manifest_sha256},
              "origin_map": {"path": str(args.origin_map), "sha256": args.origin_map_sha256},
              "reshape_cue": {"path": str(args.reshape_cue), "sha256": args.reshape_cue_sha256, "cc_read_item": cue["cc_read_item"]},
              "stratum_contract": {"path": str(args.stratum_contract), "sha256": PINS["stratum_contract"]},
              "designated_head": args.head,
              "generator_sha256": digest(Path(__file__).read_bytes()), "native_pins": PINS,
              "python": sys.version.split()[0], "random_module": str(Path(random.__file__)),
              "population_rows": len(rows), "fragment_artifacts": len(fragments)}
    print(json.dumps(publish(args.output, packets, inputs), sort_keys=True))


if __name__ == "__main__":
    main()
