"""Synthetic sampler controls; these tests run no designated reads or upstream acceptance.

Set G5_R3_GENERATOR to the original SHA-pinned R3 generator. G5_PROFILE_PROTOCOL
may point at the read-only profile worker source before its commit is integrated.
Neither environment variable supplies a credential or changes the required pins.
"""
from __future__ import annotations

import copy
from contextlib import redirect_stderr
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator, ValidationError

TOOL = Path(__file__).resolve().parents[1] / "tools/sota-convergence/start_closure_sampler.py"
SPEC = importlib.util.spec_from_file_location("start_closure_sampler_test", TOOL)
sampler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sampler)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def raw(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


class FileGuardTests(unittest.TestCase):
    def test_changed_pinned_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_bytes(b"original")
            expected = digest(path.read_bytes())
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Pinned input changed"):
                sampler.pinned_bytes(path, expected)

    def test_stratum_contract_exact_hash(self):
        contract = json.loads(sampler.pinned_bytes(sampler.CONTRACT, sampler.CONTRACT_SHA256))
        self.assertEqual(contract["profile"], sampler.PROFILE)
        self.assertEqual(contract["seed"], 202610081850)
        self.assertEqual(contract["r3_generator_sha256"], sampler.R3_CUSTODY_SHA256)

    def test_accepted_reseal_pin_matches_tracked_bytes_and_keeps_historical_contract(self):
        source = sampler.PROTOCOL.with_name("sealed_r3_generator.py")
        self.assertEqual(digest(source.read_bytes()), sampler.R3_SHA256)
        self.assertNotEqual(sampler.R3_SHA256, sampler.R3_CUSTODY_SHA256)

    def test_profile_must_be_explicit(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            sampler.main([])
        self.assertEqual(error.exception.code, 2)
        with self.assertRaisesRegex(ValueError, "explicitly"):
            sampler.build_packet(profile=None, manifest_path=None, manifest_sha256=None,
                origin_map_path=None, origin_map_sha256=None, protocol_sha256=None, r3_generator=None,
                head="a" * 40, output_root=None, output_name=None)

    def test_output_confinement_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("../escape", "/absolute", ".", "..", "nested/output", "C:\\escape"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    sampler.output_directory(root, name)
            (root / "existing").mkdir()
            with self.assertRaisesRegex(ValueError, "already exists"):
                sampler.output_directory(root, "existing")
            (root / "link").symlink_to(root / "existing", target_is_directory=True)
            with self.assertRaises(ValueError):
                sampler.output_directory(root / "link", "packet")
            self.assertEqual(sampler.output_directory(root, "new-packet"), root / "new-packet")

    def test_oversized_or_invalid_hash_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input"
            path.write_bytes(b"bytes")
            with self.assertRaisesRegex(ValueError, "oversized"):
                sampler.pinned_bytes(path, digest(b"bytes"), limit=1)
            with self.assertRaisesRegex(ValueError, "lowercase SHA256"):
                sampler.pinned_bytes(path, "not-a-hash")


class NativeSamplerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = os.environ.get("G5_R3_GENERATOR")
        if not source:
            raise unittest.SkipTest("Set G5_R3_GENERATOR to the original sealed generator for native draw controls")
        cls.r3_path = Path(source)
        cls.r3 = sampler.load_r3(cls.r3_path)
        cls.protocol = Path(os.environ.get("G5_PROFILE_PROTOCOL", str(sampler.PROTOCOL)))
        cls.protocol_sha = digest(cls.protocol.read_bytes())
        cls.native, cls.repo = sampler.load_native(cls.protocol, cls.protocol_sha, cls.r3)
        cls.schema_raw = (cls.repo / sampler.ROW_SCHEMA).read_bytes()
        cls.validator = Draft202012Validator(cls.native.load(cls.schema_raw))
        print("G5_SAMPLER_TEST_INPUTS " + json.dumps({"protocol_sha256": cls.protocol_sha,
            "row_schema_sha256": digest(cls.schema_raw), "r3_generator_sha256": sampler.R3_SHA256}, sort_keys=True))

    def setUp(self):
        self.rows = []
        self.bindings = []
        self.fragment_sha = digest(b"synthetic original fragment bytes")
        self.fragment_ref = {"source_id": "fixture-fragment", "sha256": self.fragment_sha,
            "archive_member": "captures/original-fragment.json", "pointer": "/rows/0",
            "owner_lane": "synthetic-controls"}

    def add_row(self, disposition="WATCH", *, flags=(), held_action=False, conflict=False, origin_pointer=None):
        number = len(self.rows)
        repository = f"example/project-{number:03d}"
        pin = {"kind": "commit", "version_or_commit": "a" * 40,
            "repository_or_source": repository, "subject": "implementation"}
        ref = {**self.fragment_ref, "pointer": f"/rows/{number}"}
        row = {"repository_or_entry": repository, "slot": "native-clients", "disposition": disposition,
            "evidence_class": "SOURCE-REVIEW", "pin": pin,
            "primary_sources": [{"locator": f"https://github.com/{repository}/blob/{'a' * 40}/README.md",
                "pin": pin, "subject": "pinned implementation README",
                "capture_sha256": self.fragment_sha, "archive_member": ref["archive_member"]}],
            "capture_sha256": self.fragment_sha, "archive_member": ref["archive_member"],
            "owner_lane": "synthetic-controls", "refresh_date": "2026-10-08", "source_refs": [ref]}
        if disposition == "PENDING":
            row["pending"] = {"provisional_disposition": "WATCH", "measurement": "Read the pinned primary README", "owner": "synthetic-controls"}
        if disposition == "REJECT":
            row["searched"] = "Pinned primary README"
        if disposition == "ADOPT-NOW":
            row["evidence_class"] = "RECORDED-LIVE-ACCEPTANCE"
            row["acceptance_witness"] = {"archive_member": ref["archive_member"], "sha256": self.fragment_sha, "pointer": "/acceptance"}
        if "pending_pin" in flags:
            row["pin"] = row["primary_sources"][0]["pin"] = None
            row.setdefault("closure", {})["pending_pin"] = {"reason_code": "no-match", "measurement": "Find a tree containing the captured blob"}
        if "pending_locator" in flags:
            row["primary_sources"][0]["locator"] = "UNKNOWN"
            row.setdefault("closure", {})["pending_locator"] = {"reason_code": "unsupported-transport", "measurement": "Establish the primary locator"}
        fragment = {"fragment": "fixture-fragment", "artifact_sha256": self.fragment_sha,
            "owner_lane": "synthetic-controls", "parent_family": "a-stars", "source_refs": [ref]}
        if held_action or conflict:
            row["choices"] = [{"disposition": "ADOPT-NOW", "source_refs": [ref]}]
            fragment["held_action_claims"] = [{"disposition": "ADOPT-NOW", "source_refs": [ref]}]
        if conflict:
            row["choices"].append({"disposition": "WATCH", "source_refs": [ref]})
            row.setdefault("closure", {})[sampler.CONFLICT_FLAG] = {
                "provisional_disposition": row["pending"]["provisional_disposition"],
                "measurement": row["pending"]["measurement"],
                "action_side_row_ids": [f"baseline-action-{number:03d}"]}
        if origin_pointer is not None:
            row["origin_pointer"] = copy.deepcopy(origin_pointer)
        self.rows.append(row)
        self.bindings.append({"key": {"repository_or_entry": repository, "slot": "native-clients"}, "fragments": [fragment]})
        return row

    def inputs(self):
        manifest = {"schema_version": 1, "kind": "g5-compact-landscape", "release_tag": "v2026.10.08",
            "validation": {"status": "PASS", "profile": sampler.PROFILE, "blockers": []},
            "row_schema": {"path": sampler.ROW_SCHEMA, "sha256": digest(self.schema_raw)},
            "asset": {"sha256": digest(b"synthetic declared release asset")}, "rows": copy.deepcopy(self.rows)}
        manifest_sha = digest(raw(manifest))
        origins = {"schema_version": 1, "manifest_sha256": manifest_sha,
            "stratum_contract_sha256": sampler.CONTRACT_SHA256, "origins": copy.deepcopy(self.bindings)}
        return manifest, origins, manifest_sha

    def validated(self, manifest=None, origins=None, manifest_sha=None):
        if manifest is None:
            manifest, origins, manifest_sha = self.inputs()
        return sampler.rows_and_origins(manifest, origins, manifest_sha, self.native, self.validator, self.r3)

    def draw(self):
        rows, origins, fragments = self.validated()
        return rows, sampler.select(rows, origins, fragments, list(self.native.CLASSES), self.r3)

    @staticmethod
    def bucket(packets, name):
        return next(p for p in packets if p["stratum"]["disposition"] == name)

    def test_native_r3_stream_repeatable_and_minimum_population(self):
        for _ in range(70):
            self.add_row("WATCH")
        for _ in range(4):
            self.add_row("REJECT")
        rows, origins, fragments = self.validated()
        classes = self.validator.schema["properties"]["disposition"]["enum"]
        first = sampler.select(rows, origins, fragments, classes, self.r3)
        second = sampler.select(dict(reversed(list(rows.items()))), origins, fragments, classes, self.r3)
        self.assertEqual(first, second)
        self.assertEqual(self.bucket(first, "WATCH")["selected_count"], 59)
        self.assertEqual(self.bucket(first, "REJECT")["selected_count"], 4)
        direct = self.r3.select(rows, {key: [{**f, "held_action_claims": []} for f in value] for key, value in origins.items()}, fragments, classes, sampler.SEED, 59)
        self.assertEqual([i["native_key"] for i in self.bucket(first, "WATCH")["selected"]],
            [i["native_key"] for i in self.bucket(direct, "WATCH")["selected"]])

    def test_final_actions_are_full_census_and_held_claims_do_not_qualify(self):
        for _ in range(70):
            self.add_row("TRIAL")
        self.add_row("ADOPT-NOW")
        pending = self.add_row("PENDING", held_action=True)
        rows, packets = self.draw()
        self.assertEqual(self.bucket(packets, "TRIAL")["selected_count"], 70)
        self.assertEqual(self.bucket(packets, "ADOPT-NOW")["selected_count"], 1)
        self.assertTrue(all(p["stratum"]["bucket_kind"] == "FINAL-DISPOSITION" for p in packets))
        manifest, _, manifest_sha = self.inputs()
        actions = sampler.action_read_set(rows, manifest, manifest_sha, "f" * 40)
        self.assertEqual(len(actions["rows"]), 71)
        self.assertNotIn(list(self.native.decision_key(pending)), [r["row_id"] for r in actions["rows"]])
        selected_pending = self.bucket(packets, "PENDING")["selected"][0]
        self.assertEqual(selected_pending["row"], pending)
        self.assertEqual(selected_pending["origin_bindings"], self.bindings[-1]["fragments"])

    def test_each_closure_flag_is_a_seeded_overlapping_stratum(self):
        for _ in range(70):
            self.add_row("PENDING", flags=("pending_pin", "pending_locator"))
        rows, packets = self.draw()
        for label in ("PENDING", "PENDING-PIN", "PENDING-LOCATOR"):
            packet = self.bucket(packets, label)
            self.assertEqual(packet["population_size"], 70)
            self.assertEqual(packet["selected_count"], 59)
            self.assertEqual(packet["selection_mode"], "SAMPLED")
            self.assertTrue(all(i["row"]["disposition"] == "PENDING" for i in packet["selected"]))
            self.assertTrue(all(i["row"] == rows[tuple(i["native_key"])]["row"] for i in packet["selected"]))
        counts = sampler.packet_counts(packets, rows)
        self.assertEqual(counts["sample_memberships"], 177)
        self.assertEqual(counts["rows_with_both_closure_flags"], 70)
        self.assertLessEqual(counts["unique_sampled_rows"], 70)
        self.assertEqual(counts["sample_overlap_memberships"], 177 - counts["unique_sampled_rows"])

    def test_no_family_read_or_zero_defect_acceptance_is_inferred(self):
        self.add_row()
        _, packets = self.draw()
        for packet in packets:
            self.assertEqual(packet["family_review"]["status"], "NOT_RUN")
            self.assertFalse(packet["family_review"]["zero_defects_established"])
            self.assertEqual(packet["acceptance_number"], 0)

    def test_source_residue_buckets_join_seeded_pin_and_locator_strata(self):
        for bucket, reason in (("PENDING-PIN", "foreign-primary-pin-scope-unqualified"), ("PENDING-LOCATOR", "unsupported-json-pointer-capture")):
            row = self.add_row("WATCH")
            row["closure"] = {"residue": [{"reason_code": reason, "bucket": bucket, "count": 1, "measurement": "Verify retained primary source"}]}
        rows, origins, fragments = self.validated()
        packets = sampler.select(rows, origins, fragments, list(self.native.CLASSES), self.r3)
        for bucket in ("PENDING-PIN", "PENDING-LOCATOR"):
            self.assertEqual(self.bucket(packets, bucket)["selected_count"], 1)
        for row in self.rows:
            row["disposition"] = "TRIAL"
        with self.assertRaises((ValueError, ValidationError, self.native.CompactError)):
            self.validated()

    def test_conflicts_are_uncapped_census_and_excluded_from_all_samples(self):
        for _ in range(70):
            self.add_row("PENDING", flags=("pending_pin", "pending_locator"), conflict=True)
        for _ in range(4):
            self.add_row("PENDING", flags=("pending_pin", "pending_locator"))
        self.add_row("TRIAL", origin_pointer="unresolved")
        rows, origins, fragments = self.validated()
        packets = sampler.select(rows, origins, fragments, list(self.native.CLASSES), self.r3)
        conflicts = {key for key, item in rows.items() if sampler.CONFLICT_FLAG in item["row"].get("closure", {})}
        for label in ("PENDING", "PENDING-PIN", "PENDING-LOCATOR"):
            bucket = self.bucket(packets, label)
            self.assertEqual(bucket["population_size"], 4)
            self.assertEqual(bucket["selected_count"], 4)
            self.assertFalse(conflicts & {tuple(i["native_key"]) for i in bucket["selected"]})
        counts = sampler.packet_counts(packets, rows)
        self.assertEqual(counts["unique_pending_conflict_rows"], 70)
        self.assertEqual(counts["unique_census_rows"], 71)
        self.assertEqual(counts["unique_selected_rows"], 75)
        self.assertEqual(counts["sample_memberships"], 12)
        self.assertEqual(counts["unique_sampled_rows"], 4)
        self.assertEqual(counts["pending_conflict_excluded_from_samples"], 70)
        self.assertEqual(counts["conflict_sample_flag_exclusions"], {"PENDING-PIN": 70, "PENDING-LOCATOR": 70})
        manifest, _, manifest_sha = self.inputs()
        census = sampler.pending_conflict_census(rows, origins, manifest, manifest_sha, "f" * 40)
        self.assertEqual(census["count"], 70)
        self.assertEqual(census["family_review"]["status"], "NOT_RUN")
        for entry in census["rows"]:
            key = tuple(entry["row_id"])
            self.assertEqual(entry["row"], rows[key]["row"])
            self.assertEqual(entry["row"]["disposition"], "PENDING")
            self.assertEqual(entry["action_side_row_ids"], rows[key]["row"]["closure"][sampler.CONFLICT_FLAG]["action_side_row_ids"])
            self.assertEqual(entry["origin_bindings"], origins[key])
        self.assertEqual(len(sampler.action_read_set(rows, manifest, manifest_sha, "f" * 40)["rows"]), 1)

    def test_conflict_metadata_requires_evidenced_action_conflict_and_measurement(self):
        self.add_row("PENDING", conflict=True)
        cases = ("single_choice", "no_action_choice", "different_measurement", "action_provisional", "duplicate_claim_ids", "action_disposition")
        for case in cases:
            manifest, origins, manifest_sha = self.inputs()
            row = manifest["rows"][0]
            flag = row["closure"][sampler.CONFLICT_FLAG]
            if case == "single_choice":
                row["choices"] = row["choices"][:1]
            elif case == "no_action_choice":
                row["choices"][0]["disposition"] = "REJECT"
            elif case == "different_measurement":
                flag["measurement"] = "A different settling measurement"
            elif case == "action_provisional":
                flag["provisional_disposition"] = row["pending"]["provisional_disposition"] = "TRIAL"
            elif case == "duplicate_claim_ids":
                flag["action_side_row_ids"] *= 2
            else:
                row["disposition"] = "TRIAL"
                del row["pending"]
            with self.subTest(case=case), self.assertRaises((ValueError, ValidationError)):
                self.validated(manifest, origins, manifest_sha)

    def test_unresolved_origin_keeps_action_and_bound_origin_is_preserved(self):
        action = self.add_row("TRIAL", origin_pointer="unresolved")
        bound = self.add_row("PENDING", conflict=True, origin_pointer=self.fragment_ref)
        rows, packets = self.draw()
        manifest, origins, manifest_sha = self.inputs()
        final = sampler.action_read_set(rows, manifest, manifest_sha, "f" * 40)
        self.assertEqual([r["row_id"] for r in final["rows"]], [list(self.native.decision_key(action))])
        counts = sampler.packet_counts(packets, rows)
        self.assertEqual(counts["origin_pointer_unresolved_rows"], 1)
        self.assertEqual(counts["action_origin_pointer_unresolved_rows"], 1)
        original_origins = self.validated(manifest, origins, manifest_sha)[1]
        census = sampler.pending_conflict_census(rows, original_origins, manifest, manifest_sha, "f" * 40)
        self.assertEqual(census["rows"][0]["row"]["origin_pointer"], bound["origin_pointer"])
        manifest["rows"][1]["origin_pointer"]["archive_member"] = "../escape"
        with self.assertRaises((ValueError, ValidationError)):
            self.validated(manifest, origins, manifest_sha)

    def test_profile_pass_and_exact_manifest_binding_are_required(self):
        self.add_row()
        for field, value in (("status", "BLOCKED"), ("profile", "default"), ("blockers", ["defect"])):
            manifest, origins, manifest_sha = self.inputs()
            manifest["validation"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validated(manifest, origins, manifest_sha)
        manifest, origins, manifest_sha = self.inputs()
        origins["manifest_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "exact manifest"):
            self.validated(manifest, origins, manifest_sha)

    def test_native_key_uniqueness_and_full_origin_coverage(self):
        self.add_row()
        manifest, origins, manifest_sha = self.inputs()
        manifest["rows"].append(copy.deepcopy(manifest["rows"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate native"):
            self.validated(manifest, origins, manifest_sha)
        manifest, origins, manifest_sha = self.inputs()
        origins["origins"] = []
        with self.assertRaisesRegex(ValueError, "every final row"):
            self.validated(manifest, origins, manifest_sha)

    def test_declared_pending_action_origin_remains_full_census_without_sample_inference(self):
        self.add_row("TRIAL", origin_pointer="unresolved")
        self.add_row("WATCH")
        manifest, origins, manifest_sha = self.inputs()
        missing = origins["origins"].pop(0)
        origins["pending_origins"] = [{"key": missing["key"], "status": "PENDING", "reason_code": "retained-provenance-missing", "measurement": "Recover original fragment provenance"}]
        rows, provenance, fragments = self.validated(manifest, origins, manifest_sha)
        packets = sampler.select(rows, provenance, fragments, list(self.native.CLASSES), self.r3)
        actions = sampler.action_read_set(rows, manifest, manifest_sha, "a" * 40)
        self.assertEqual(len(actions["rows"]), 1)
        self.assertFalse(any(item["row"]["disposition"] == "TRIAL" for packet in packets for item in packet["selected"]))
        counts = sampler.packet_counts(packets, rows)
        self.assertEqual(counts["unique_final_action_rows"], 1)
        self.assertEqual(counts["pending_origin_census_rows"], 1)
        self.assertEqual(counts["unique_selected_rows"], 2)

    def test_pending_origin_cannot_exempt_sampled_rows_or_omit_reason_and_measurement(self):
        self.add_row("WATCH")
        manifest, origins, manifest_sha = self.inputs()
        missing = origins["origins"].pop()
        declaration = {"key": missing["key"], "status": "PENDING", "reason_code": "retained-provenance-missing", "measurement": "Recover original provenance"}
        origins["pending_origins"] = [declaration]
        with self.assertRaisesRegex(ValueError, "sampled row"):
            self.validated(manifest, origins, manifest_sha)
        self.add_row("TRIAL")
        manifest, origins, manifest_sha = self.inputs()
        missing = origins["origins"].pop()
        origins["pending_origins"] = [{"key": missing["key"], "status": "PENDING", "reason_code": "retained-provenance-missing", "measurement": ""}]
        with self.assertRaisesRegex(ValueError, "reason and measurement"):
            self.validated(manifest, origins, manifest_sha)

    def test_native_origin_derivation_preserves_exact_refs_and_explicit_rollups(self):
        self.add_row("WATCH")
        self.add_row("TRIAL")
        manifest, origins, manifest_sha = self.inputs()
        binding = origins["origins"][0]
        fragment = binding["fragments"][0]
        provenance = {"schema_version": 1, "origins": [{**binding["key"], "fragments": [fragment["fragment"]], "source_refs": fragment["source_refs"]}]}
        provenance_sha = digest(raw(provenance))
        declarations = {"source_provenance_sha256": provenance_sha, "declarations": [{name: fragment[name] for name in ("fragment", "artifact_sha256", "owner_lane", "parent_family")}]}
        derived = sampler.derive_origin_map(manifest, manifest_sha, provenance, provenance_sha, declarations, self.native, self.r3)
        self.assertEqual(derived["counts"]["origins_retained"], 1)
        self.assertEqual(derived["counts"]["origins_pending"], 1)
        self.assertEqual(derived["counts"]["unreachable_sampled_rows"], 0)
        self.assertEqual(derived["origins"][0]["fragments"][0]["source_refs"], fragment["source_refs"])
        self.validated(manifest, derived, manifest_sha)
        declarations["declarations"][0]["owner_lane"] = "invented-owner"
        with self.assertRaisesRegex(ValueError, "owner differs"):
            sampler.derive_origin_map(manifest, manifest_sha, provenance, provenance_sha, declarations, self.native, self.r3)

    def test_native_draw_proof_uses_exact_inputs_and_preserves_population_hashes(self):
        self.add_row("WATCH")
        self.add_row("TRIAL")
        manifest, origins, manifest_sha = self.inputs()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        manifest_path = directory / "manifest.json"
        origin_path = directory / "origins.json"
        manifest_path.write_bytes(raw(manifest))
        origin_path.write_bytes(raw(origins))
        result = sampler.draw_proof(manifest_path=manifest_path, manifest_sha256=manifest_sha,
            origin_map_path=origin_path, origin_map_sha256=digest(origin_path.read_bytes()),
            protocol_sha256=self.protocol_sha, r3_generator=self.r3_path, r3_sha256=sampler.R3_SHA256,
            head="a" * 40, output=directory / "proof.json")
        packets = json.loads((directory / "proof.json").read_bytes())
        self.assertEqual(result["packet_sha256"], digest((directory / "proof.json").read_bytes()))
        self.assertEqual(packets["manifest_sha256"], manifest_sha)
        self.assertEqual(packets["origin_map_sha256"], digest(origin_path.read_bytes()))
        self.assertTrue(all(len(p["population_key_sha256"]) == 64 for p in packets["packets"]))
        with self.assertRaisesRegex(ValueError, "changed"):
            sampler.draw_proof(manifest_path=manifest_path, manifest_sha256="d" * 64,
                origin_map_path=origin_path, origin_map_sha256=digest(origin_path.read_bytes()),
                protocol_sha256=self.protocol_sha, r3_generator=self.r3_path, r3_sha256=sampler.R3_SHA256,
                head="a" * 40, output=directory / "invalid-proof.json")

    def test_action_row_and_every_primary_source_remain_pinned(self):
        self.add_row("TRIAL")
        for target in ("row", "source"):
            manifest, origins, manifest_sha = self.inputs()
            row = manifest["rows"][0]
            if target == "row":
                row["pin"] = None
            else:
                row["primary_sources"][0]["pin"] = None
            with self.subTest(target=target), self.assertRaises((ValueError, ValidationError)):
                self.validated(manifest, origins, manifest_sha)

    def test_action_row_cannot_carry_pending_closure_flag(self):
        self.add_row("TRIAL")
        manifest, origins, manifest_sha = self.inputs()
        manifest["rows"][0]["closure"] = {"pending_pin": {"reason_code": "no-match", "measurement": "settle"}}
        with self.assertRaises((ValueError, ValidationError)):
            self.validated(manifest, origins, manifest_sha)

    def test_unsafe_locator_and_archive_reference_are_rejected(self):
        self.add_row("PENDING", flags=("pending_locator",))
        for locator in ("file:/private", "/private", "https://name:secret@github.com/example/repo", "https://github.com/example/repo/blob/main/README.md"):
            manifest, origins, manifest_sha = self.inputs()
            manifest["rows"][0]["primary_sources"][0]["locator"] = locator
            with self.subTest(locator=locator), self.assertRaises(ValueError):
                self.validated(manifest, origins, manifest_sha)
        manifest, origins, manifest_sha = self.inputs()
        origins["origins"][0]["fragments"][0]["source_refs"][0]["archive_member"] = "../escape"
        with self.assertRaises(ValueError):
            self.validated(manifest, origins, manifest_sha)

    def test_capture_and_original_fragment_evidence_cannot_drift(self):
        self.add_row()
        manifest, origins, manifest_sha = self.inputs()
        manifest["rows"][0]["capture_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Hash-mismatched"):
            self.validated(manifest, origins, manifest_sha)
        manifest, origins, manifest_sha = self.inputs()
        origins["origins"][0]["fragments"][0]["source_refs"][0]["pointer"] = "/unbound"
        with self.assertRaisesRegex(ValueError, "original row reference"):
            self.validated(manifest, origins, manifest_sha)

    def test_packet_hashes_projection_and_not_run_status(self):
        self.add_row("TRIAL", origin_pointer="unresolved")
        self.add_row("PENDING", held_action=True)
        self.add_row("PENDING", conflict=True)
        manifest, origins, manifest_sha = self.inputs()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path, origin_path = root / "input.json", root / "origin.json"
            manifest_path.write_bytes(raw(manifest))
            origin_path.write_bytes(raw(origins))
            kwargs = dict(profile=sampler.PROFILE, manifest_path=manifest_path, manifest_sha256=manifest_sha,
                origin_map_path=origin_path, origin_map_sha256=digest(raw(origins)), protocol_sha256=self.protocol_sha,
                r3_generator=self.r3_path, head="f" * 40, output_root=root, output_name="packet", protocol=self.protocol)
            result = sampler.build_packet(**kwargs)
            packet = root / "packet"
            summary = json.loads((packet / "manifest.json").read_bytes())
            actions = json.loads((packet / "action-read-set.json").read_bytes())
            conflicts = json.loads((packet / "pending-conflict-census.json").read_bytes())
            combined = json.loads((packet / "census-read-set.json").read_bytes())
            self.assertEqual(result["action_rows"], 1)
            self.assertEqual(result["pending_conflict_rows"], 1)
            self.assertEqual(result["census_rows"], 2)
            self.assertEqual(result["reads"], "NOT_RUN")
            self.assertEqual(result["action_read_set_sha256"], digest((packet / "action-read-set.json").read_bytes()))
            self.assertEqual(actions["asset_sha256"], manifest["asset"]["sha256"])
            self.assertEqual(actions["head"], "f" * 40)
            self.assertEqual(actions["rows"][0]["row_id"], list(self.native.decision_key(self.rows[0])))
            self.assertEqual(actions["rows"][0]["locator"], [s["locator"] for s in self.rows[0]["primary_sources"]])
            self.assertEqual(conflicts["rows"][0]["row"], self.rows[2])
            self.assertEqual(conflicts["family_review"]["status"], "NOT_RUN")
            self.assertEqual(combined["counts_by_type"], {"FINAL-ACTION": 1, "PENDING-CONFLICT": 1})
            self.assertEqual(combined["family_review"]["status"], "NOT_RUN")
            self.assertEqual(combined["rows"][0]["origin_pointer"], "unresolved")
            self.assertEqual({r["census_type"] for r in combined["rows"]}, {"FINAL-ACTION", "PENDING-CONFLICT"})
            self.assertEqual(summary["action_read_set"]["reads"], "NOT_RUN")
            self.assertEqual(summary["pending_conflict_census"]["reads"], "NOT_RUN")
            self.assertEqual(summary["census_read_set"]["reads"], "NOT_RUN")
            self.assertEqual(result["pending_conflict_census_sha256"], digest((packet / "pending-conflict-census.json").read_bytes()))
            self.assertEqual(result["census_read_set_sha256"], digest((packet / "census-read-set.json").read_bytes()))
            for source in combined["sources"]:
                self.assertEqual(digest((packet / source["path"]).read_bytes()), source["sha256"])
            self.assertEqual(summary["family_review"]["profile_code_and_tests"], "NOT_RUN")
            self.assertEqual(len(summary["profile_review_sources"]), 4)
            for source in summary["profile_review_sources"]:
                self.assertEqual(digest((packet / source["path"]).read_bytes()), source["sha256"])
            for line in (packet / "manifest.sha256").read_text().splitlines():
                expected, name = line.split("  ", 1)
                self.assertEqual(digest((packet / name).read_bytes()), expected)
            with self.assertRaisesRegex(ValueError, "already exists"):
                sampler.build_packet(**kwargs)
            manifest_path.write_bytes(raw({**manifest, "tampered": True}))
            kwargs["output_name"] = "second"
            with self.assertRaisesRegex(ValueError, "Pinned input changed"):
                sampler.build_packet(**kwargs)
            self.assertFalse((root / "second").exists())


if __name__ == "__main__":
    unittest.main()
